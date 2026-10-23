"""The sandbox: simulated calendars, a request thread, holds and invites for one scenario.
No real calendar is read or written and no real message is sent.

reset(scenario) installs one scenario and clears every log, so run 2 never inherits run 1's
state. Every call is logged in CALLS, every write in WRITES. Writes take an idempotency key:
the same key twice writes once."""
import json
from pathlib import Path

from scheduler.contracts.availability import AvailabilitySummary
from scheduler.contracts.result import GuardrailCheck, Question, TimelineEvent
from scheduler.contracts.scenario import Reply, Scenario
from scheduler.contracts.tools import Call, CorpusDoc, Write
from scheduler.timegrid import overlaps

SCENARIO: Scenario | None = None
CORPUS: dict[str, CorpusDoc] = {}
CALENDARS: dict[str, list[dict]] = {}      # participant -> events, each tagged with its calendar's name
CONSENTS: dict[str, list[tuple[str, str | None]]] = {}   # participant -> (ref, slot) they agreed to free
APPROVALS: dict[str, dict] = {}            # approval id -> {"start", "end", "decision"}
HOLDS: dict[str, dict] = {}                # key -> {"start", "end"}
THREAD: list[str] = []                    # the request thread, seen by every participant
BLOCKED: list[str] = []                   # messages the privacy filter stopped
QUESTIONS: list[Question] = []
SUMMARIES: list[AvailabilitySummary] = []
CONTEXT: list[str] = []                   # what the coordinator agent was shown
CALLS: list[Call] = []
WRITES: list[Write] = []
TIMELINE: list[TimelineEvent] = []         # every step, in order, with who may see it
GUARDRAILS: list[GuardrailCheck] = []      # every guardrail verdict
FIRED: set[int] = set()                    # scripted events already applied


def reset(scenario: Scenario, corpus_dir: Path) -> None:
    global SCENARIO, CORPUS, CALENDARS, CONSENTS, APPROVALS, HOLDS
    SCENARIO = scenario
    CORPUS = {}
    for doc_id in scenario.corpus:
        doc = CorpusDoc.model_validate(json.loads((corpus_dir / f"{doc_id}.json").read_text()))
        CORPUS[doc.id] = doc
    CALENDARS = {}
    for p in scenario.participants:
        CALENDARS[p.id] = [{**e.model_dump(), "calendar": c.name} for c in p.calendars for e in c.events]
    CONSENTS = {p.id: [] for p in scenario.participants}
    APPROVALS, HOLDS = {}, {}
    for log in (THREAD, BLOCKED, QUESTIONS, SUMMARIES, CONTEXT, CALLS, WRITES, TIMELINE, GUARDRAILS):
        log.clear()
    FIRED.clear()


def audience(actor: str) -> list[str]:
    """Who may see what an actor does: a personal agent's steps are its participant's alone."""
    if actor.startswith("personal:"):
        return [actor.removeprefix("personal:")]
    return [actor] if actor in ("coordinator", "organiser", "shared", "single", "baseline") else ["system"]


def note(actor: str, kind: str, text: str, visible_to: list[str] | None = None) -> None:
    TIMELINE.append(TimelineEvent(seq=len(TIMELINE) + 1, actor=actor, kind=kind, text=text,
                                  visible_to=visible_to or audience(actor)))


def guard(name: str, where: str, reads: str, passed: bool, detail: str = "") -> bool:
    """Record one guardrail verdict (passes included) and return it."""
    GUARDRAILS.append(GuardrailCheck(name=name, where=where, reads=reads, passed=passed, detail=detail))
    note(f"guardrail:{name}", "guardrail", f"{'pass' if passed else 'STOP'}: {detail or reads}", ["system"])
    return passed


def log(tool: str, caller: str, **args) -> None:
    CALLS.append(Call(tool=tool, caller=caller, args=args))
    note(caller, "call", f"{tool} " + ", ".join(f"{k}={v}" for k, v in args.items()))


def check_participant(pid: str) -> None:
    """An unknown id is an error that names the valid ones, never an empty answer."""
    if pid not in CALENDARS:
        raise ValueError(f"unknown participant {pid}; participants: {', '.join(CALENDARS)}")


def read_calendar(pid: str, caller: str) -> list[dict]:
    check_participant(pid)
    log("read_my_calendar", caller, participant_id=pid)
    return list(CALENDARS[pid])


def get_leave(pid: str, caller: str) -> list[dict]:
    check_participant(pid)
    log("get_leave", caller, participant_id=pid)
    return [leave.model_dump() for leave in SCENARIO.participant(pid).leave]


def read_messages(pid: str, caller: str) -> list[dict]:
    check_participant(pid)
    log("read_my_messages", caller, participant_id=pid)
    return [m.model_dump() for m in SCENARIO.participant(pid).messages]


def search(query: str, caller: str) -> list[CorpusDoc]:
    """Up to 3 corpus documents, best first: those containing at least three quarters as many
    query words as the best match. A document sharing only a month or a year with the query
    does not ride along with the one that matches it."""
    words = [w for w in query.lower().split() if len(w) > 2]
    scored = []
    for doc in CORPUS.values():
        text = f"{doc.title} {doc.text}".lower()
        score = sum(w in text for w in words)
        if score:
            scored.append((score, doc.id, doc))
    best = max((score for score, _, _ in scored), default=0)
    hits = [doc for score, _, doc in sorted(scored, key=lambda s: (-s[0], s[1])) if score >= 0.75 * best][:3]
    log("search_schedules", caller, query=query, hits=[d.id for d in hits])
    return hits


def scripted_reply(pid: str, about: str, caller: str, question: str = "") -> Reply | None:
    """The participant's scripted answer. `question` is the agent's own wording: a script ignores
    it, but a live front end (the demo app) shows it to the real person."""
    log("ask_participant", caller, participant_id=pid, about=about)
    return next((r for r in SCENARIO.scripted.replies if r.participant_id == pid and r.about == about), None)


def record_consent(pid: str, ref: str, slot: str | None) -> None:
    CONSENTS[pid].append((ref, slot))


def organiser_decision() -> str:
    """The organiser's answer to an approval request (scripted per scenario)."""
    return SCENARIO.scripted.approval.decision


def store_approval(start: str, end: str, decision: str) -> str:
    """The organiser's decision, stored in code, outside any model's text."""
    approval_id = f"approval-{len(APPROVALS) + 1}"
    APPROVALS[approval_id] = {"start": start, "end": end, "decision": decision}
    log("store_approval", "gate", approval_id=approval_id, start=start, end=end, decision=decision)
    return approval_id


def place_hold(request_id: str, start: str, end: str, key: str, caller: str) -> str:
    log("place_hold", caller, start=start, end=end, key=key)
    if key not in HOLDS:
        HOLDS[key] = {"start": start, "end": end}
        WRITES.append(Write(tool="place_hold", request_id=request_id, start=start, end=end, key=key))
    return f"hold {key} on {start}-{end[11:]}"


def release_hold(request_id: str, key: str, caller: str) -> str:
    log("release_hold", caller, key=key)
    if key in HOLDS:
        del HOLDS[key]
        WRITES.append(Write(tool="release_hold", request_id=request_id, key=key))
    return f"hold {key} released"


def send_invite(request_id: str, start: str, end: str, approval_id: str, key: str) -> str:
    """Refused unless an approval for exactly this slot is stored. Idempotent on key. A new
    invite for the same request replaces the old one on every calendar (a replan)."""
    log("send_invite", "gate", start=start, end=end, approval_id=approval_id, key=key)
    approval = APPROVALS.get(approval_id)
    ok = bool(approval) and approval["decision"] == "approve" and (approval["start"], approval["end"]) == (start, end)
    if not guard("stored approval", "tool call", f"approval {approval_id} for {start}", ok,
                 "" if ok else f"no stored approval for {start}-{end}"):
        raise PermissionError(f"no stored approval for {start}-{end}")
    if any(w.key == key for w in WRITES if w.tool == "send_invite"):
        return "already sent"
    for pid in CALENDARS:
        CALENDARS[pid] = [e for e in CALENDARS[pid] if e["id"] != f"invite-{request_id}"]
    for attendee in SCENARIO.request.attendees:
        CALENDARS[attendee.id].append({"id": f"invite-{request_id}", "title": SCENARIO.request.text,
                                       "start": start, "end": end, "movable": False,
                                       "priority": "normal", "owner": SCENARIO.request.organiser_id,
                                       "calendar": "invites"})
    WRITES.append(Write(tool="send_invite", request_id=request_id, start=start, end=end,
                        key=key, approval_id=approval_id))
    return f"invite sent for {start}-{end[11:]}"


def read_back(request_id: str, caller: str) -> dict[str, tuple[str, str] | None]:
    """What is actually on each attendee's calendar for this request."""
    log("read_back", caller, request_id=request_id)
    out = {}
    for attendee in SCENARIO.request.attendees:
        event = next((e for e in CALENDARS[attendee.id] if e["id"] == f"invite-{request_id}"), None)
        out[attendee.id] = (event["start"], event["end"]) if event else None
    return out


def busy_events(pid: str, start: str, end: str) -> list[dict]:
    """Calendar events, on any of the participant's calendars, overlapping a window (this
    request's own invite excluded)."""
    return [e for e in CALENDARS[pid]
            if not e["id"].startswith("invite-") and overlaps(e["start"], e["end"], start, end)]


def fire(at: str) -> list[dict]:
    """Apply the scripted events due at this point; return what happened."""
    happened = []
    for i, event in enumerate(SCENARIO.scripted.events):
        if event.at != at or i in FIRED:
            continue
        FIRED.add(i)
        if event.type == "new_meeting":
            CALENDARS[event.participant_id].append({**event.meeting.model_dump(), "calendar": event.calendar})
        elif event.type == "thread_message":
            THREAD.append(f"{event.participant_id}: {event.text}")
            note(event.participant_id, "thread", event.text, ["thread"])
        happened.append(event.model_dump())
        log("scripted_event", "harness", at=at, type=event.type, participant_id=event.participant_id)
    return happened
