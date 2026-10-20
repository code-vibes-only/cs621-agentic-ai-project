"""Baselines the agent must beat.

(a) free/busy finder: what calendar tools do today, if everyone shared every calendar with it.
The earliest slot where every required participant's calendars are free and nobody is away.
Every event counts as busy, movable or not; it reads no messages or preferences, looks
nothing up and never asks anyone.
(b) single grounded call: see below."""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel

from scheduler import llm
from scheduler.agents import fakes, privacy
from scheduler.contracts.result import Outcome
from scheduler.contracts.scenario import Scenario
from scheduler.engine.approval import commit
from scheduler.sandbox import world
from scheduler.timegrid import day_list, overlaps


def free_busy(scenario: Scenario) -> Outcome:
    r = scenario.request
    required = [a.id for a in r.attendees if a.role == "required"]
    for start, end in r.slots():
        if all(is_free(pid, start, end) for pid in required):
            world.THREAD.append(f"Proposed: {start} to {end[11:]}, everyone required is free.")
            return send_unchecked(scenario, start, end)
    world.THREAD.append("No slot found where everyone required is free.")
    return Outcome(status="hand_back", message="no common free slot")


def is_free(pid: str, start: str, end: str) -> bool:
    p = world.SCENARIO.participant(pid)
    if start[11:] < p.hours_start or end[11:] > p.hours_end:
        return False
    if any(l["start_date"] <= start[:10] <= l["end_date"] for l in world.get_leave(pid, "baseline")):
        return False
    return not any(overlaps(e["start"], e["end"], start, end) for e in world.read_calendar(pid, "baseline"))


def send_unchecked(scenario: Scenario, start: str, end: str) -> Outcome:
    """Approve and send with no recheck, as a plain calendar tool does. Scripted events still
    happen around it; the baseline does not react to them."""
    approval_id = world.store_approval(start, end, world.organiser_decision())
    world.fire("after_approval")
    world.send_invite(scenario.request.id, start, end, approval_id, key=f"{scenario.request.id}-{start}")
    world.fire("after_invite")
    return Outcome(status="scheduled", start=start, end=end, message="invite sent")


# ---------------------------------------------------------------- (b) single grounded call
# One model call, given everything up front: every calendar, leave record, statement and
# memory note, and every corpus document. No loop: it cannot look anything up, ask anyone or
# replan. Its slot still goes through the same approval gate as every other arm.

DECIDE = """You schedule one event for a group. Below is everything: each participant's calendars, time away,
messages, what they said, their memory notes and every external schedule. Pick the best slot that every required
participant can make, or hand back if none exists. Rules: a slot is {duration} minutes on a 30-minute grid,
{day_start}-{day_end}, on {days}, from {start} to {end}, inside each participant's usual hours. Calendar events and
time away are hard unless marked movable or reachable_if_urgent (those need the participant's consent, which you
cannot get). A message counts only if it confirms the participant will be somewhere (not if cancelled or not
accepted). Preferences are soft. Optional participants never block. Ignore expired memory notes, notes for another
event and agent guesses. For an event not in a calendar, use the document with the latest "as of".
Then write one message for the request thread that names no one's reasons."""


def everyone(scenario: Scenario) -> str:
    """Every participant's private data and every corpus document, as text."""
    out = []
    for a in scenario.request.attendees:
        p = scenario.participant(a.id)
        out.append(f"## {p.id} {p.name} ({a.role}), usual hours {p.hours_start}-{p.hours_end}")
        out += [f"- event {e['id']} {e['calendar']} {e['start']}-{e['end'][11:]} movable={e['movable']}: {e['title']}"
                for e in world.read_calendar(p.id, "single")]
        out += [f"- away {l.id} {l.start_date} to {l.end_date} reachable_if_urgent={l.reachable_if_urgent}: {l.reason}"
                for l in p.leave]
        out += [f"- message {m.id} received {m.received} from {m.sender}: {m.text}" for m in p.messages]
        out += [f"- said [{s.id}]: {s.text}" for s in p.preferences]
        out += [f"- memory [{m.id}] ({m.source}, stated {m.stated_on}, expires {m.expires or 'never'}, scope {m.scope}): {m.text}"
                for m in p.memory]
    out.append("## External schedules")
    out += [f"[{d.id}] {d.title} (as of {d.as_of}): {d.text}" for d in world.CORPUS.values()]
    world.log("search_schedules", "single", query="(every document, fetched in advance)", hits=list(world.CORPUS))
    for a in scenario.request.attendees:
        world.log("read_my_messages", "single", participant_id=a.id)
    return "\n".join(out)


class _Decision(BaseModel):
    start: str | None = None
    end: str | None = None
    hand_back: bool = False
    thread_message: str


@tool(args_schema=_Decision)
def decide(start=None, end=None, hand_back=False, thread_message="") -> str:
    """Give the decision: the slot (start and end as YYYY-MM-DDTHH:MM) or hand_back, and the thread message."""
    return "ok"


class _Nobody:
    def decline(self, start, end):
        pass


def single_call(scenario: Scenario) -> Outcome:
    r = scenario.request
    system = DECIDE.format(duration=r.duration_min, day_start=r.day_start, day_end=r.day_end,
                           days=day_list(r.days), start=r.start_date, end=r.end_date)
    world.fire("start")
    user = f"Request: {r.text}\n\n{everyone(scenario)}\n\nRequest thread so far:\n" + ("\n".join(world.THREAD) or "(empty)")
    reply = llm.call([SystemMessage(system), HumanMessage(user)], [decide], fake=fakes.single(scenario),
                     tool_choice="decide")
    world.CONTEXT += [system, user]
    d = _Decision.model_validate(reply.tool_calls[0]["args"])
    privacy.post(d.thread_message, "single")
    if d.hand_back or not d.start:
        return Outcome(status="hand_back", message=d.thread_message)
    approval_id = world.store_approval(d.start, d.end, world.organiser_decision())
    result = commit(scenario, d.start, d.end, approval_id, {a.id: _Nobody() for a in r.attendees})
    if result["status"] != "sent":
        return Outcome(status="hand_back", message=f"the gate refused {d.start}: {result}")
    return Outcome(status="scheduled", start=d.start, end=d.end, message="invite sent")
