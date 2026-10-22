"""Add and Analyse: your personal agent reads a new calendar item before it goes on your calendar.

You describe it ("Gym, 1 hour, Wednesday evening, flexible"). The agent reads that (the real
model, or a rule-based reader with model calls off), reads your calendars, and asks you only
what it cannot settle alone: which free slot you prefer, whether a clash is fine, whether the item
could move if someone asks, and which calendar it belongs on. Every step goes into the request's
trace, so the added event can show "View trace". Nothing here leaves your own agent."""
import os
import re
import threading
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from scheduler import llm
from scheduler.demo import store
from scheduler.demo.engine import DAY_NAMES, TODAY, nice_day, nice_slot
from scheduler.sandbox import world
from scheduler.timegrid import WEEKDAYS, Clock, Day, Weekday, candidate_slots, overlaps

Kind = Literal["work", "family", "academic", "personal", "club"]
KEYWORDS = {"work": r"meeting|shift|office|client|work|sync|review|stand-?up",
            "academic": r"class|lecture|lab|study|exam|assignment|tutorial|revision|seminar|project",
            "family": r"family|mum|mom|dad|birthday|dinner|kids?|sister|brother|wedding",
            "club": r"match|league|club|training|practice",
            "personal": r"gym|run|doctor|dentist|haircut|yoga|swim|movie"}


class ItemAsk(BaseModel):
    title: str
    kind: Kind = "personal"
    duration_min: int = 60
    start: str | None = None         # an exact start, 'YYYY-MM-DDTHH:MM', when the text gives one
    start_date: Day
    end_date: Day
    day_start: Clock = "08:00"
    day_end: Clock = "20:00"
    days: list[Weekday] = WEEKDAYS
    flexibility: int = Field(1, ge=0, le=3)


@tool(args_schema=ItemAsk)
def add_item(**kwargs) -> str:
    """Record the calendar item the person described."""
    return "recorded"


READER = """You are the private personal agent of {name}. Today is {today} ({weekday}). {name} wants to add
something to their calendar. Read it and call add_item once.
- title: short, as they would write it. kind: work, family, academic, personal or club.
- duration_min: 60 unless they say otherwise.
- start: only if they gave an exact day and time ('YYYY-MM-DDTHH:MM'). Otherwise leave it out and give the window:
  start_date and end_date (default: tomorrow to a week from today), day_start and day_end (evenings 19:00-22:30,
  mornings 08:00-12:00, lunchtime 12:00-14:00, afternoons 13:00-18:00, otherwise 08:00-20:00), and days.
- flexibility: """ + "{flex_guide}"


FLEX_GUIDE = """how easily it could move for someone else's meeting: 0 fixed (an appointment, exam, interview,
  flight, class or anything booked with others), 1 ask first (work shifts, practices, pick-ups: could move for
  something important), 2 flexible (gym, errands, personal time they'd rather keep), 3 easy to move (they say it is
  flexible, optional or doesn't matter). Their own words win over the kind of item."""


class FlexGuess(BaseModel):
    level: int = Field(ge=0, le=3)


@tool(args_schema=FlexGuess)
def rate_flexibility(**kwargs) -> str:
    """Record how easily the item could move."""
    return "recorded"


FLEX_READER = """You are the private personal agent of {name}. They are adding "{title}" to their calendar. Judge
how easily it could move, and call rate_flexibility once. Level: """ + FLEX_GUIDE


@lru_cache(maxsize=256)
def guess_flex(title: str, person: str, mode: str) -> int:
    """The agent's first guess at an item's flexibility, for the Add dialog: the model in real mode
    (once per title), the keyword rules when mocked, or if the model can't be reached."""
    if mode == "mock" or not title.strip() or world.__dict__.get("_demo_lock", threading.Lock()).locked():
        return suggest_flex(title)                    # a run is using the model's budget: don't disturb it
    os.environ["SCHEDULER_FAKE_LLM"] = "0"
    llm.reset_usage()
    try:
        reply = llm.call([SystemMessage(FLEX_READER.format(name=store.name(person), title=title)),
                          HumanMessage(title)], [rate_flexibility], tool_choice="rate_flexibility")
        return FlexGuess.model_validate(reply.tool_calls[0]["args"]).level
    except Exception:                                  # no key, no network, a malformed answer: the rules
        return suggest_flex(title)


FIXED = r"doctor|dentist|clinic|hospital|appointment|exam|test|interview|flight|train(?!ing)|lecture|class|seminar|wedding|" \
        r"funeral|recital|birthday|deadline|court|booking|reservation"
ASK_FIRST = r"shift|work|meeting|sync|practice|training|lesson|tuition|pick.?up|drop.?off|match|rehearsal|lab|call"
FLEXIBLE = r"gym|run|jog|swim|yoga|walk|errand|groceries|shopping|laundry|reading|study|focus|admin|haircut|coffee"


def suggest_flex(text: str) -> int:
    """The agent's first guess at how easily an item could move, from its words; the person decides."""
    t = text.lower()
    if re.search(r"flexible|can move|movable|if needed|optional|doesn't matter|anytime|any time", t):
        return 3
    if re.search(r"can't move|fixed|must|important|urgent", t):
        return 0
    for level, words in ((0, FIXED), (1, ASK_FIRST), (2, FLEXIBLE)):
        if re.search(rf"\b({words})", t):
            return level
    return 1


def read_by_rules(text: str) -> dict:
    """The mocked reader, for phrasings like "Gym, 1 hour, Wednesday evening, flexible" or
    "Dentist on Thursday at 3pm"."""
    t, today = text.lower(), date.fromisoformat(TODAY)
    title = re.split(r",| for \d| on | at | next | this | tomorrow| sometime| some time| -", text, maxsplit=1)[0].strip()
    kind = next((k for k, pattern in KEYWORDS.items() if re.search(rf"\b({pattern})", t)), "personal")
    m = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*(minutes?|mins?|hours?|hrs?|h)\b", t)
    duration = (float(m[1]) * (60 if m[2].startswith("h") else 1)) if m else 30 if "half an hour" in t else 60
    duration = max(15, int(round(duration / 15) * 15))
    named = [d for d, full in zip(WEEKDAYS, DAY_NAMES) if re.search(rf"\b({full}|{d})\b", t)]
    if "tomorrow" in t:
        first_day = last_day = today + timedelta(days=1)
    elif named:
        first_day = today + timedelta(days=(WEEKDAYS.index(named[0]) - today.weekday()) % 7 or 7)
        last_day = first_day if len(named) == 1 else first_day + timedelta(days=6)
    elif "next week" in t:
        first_day = today + timedelta(days=7 - today.weekday())
        last_day = first_day + timedelta(days=6)
    elif "weekend" in t:
        first_day = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
        last_day = first_day + timedelta(days=1)
    else:
        first_day, last_day = today + timedelta(days=1), today + timedelta(days=7)
    twelve = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t)
    clock = re.search(r"\b(\d{1,2}):(\d{2})\b", t)
    start = None
    if first_day == last_day and (twelve or clock):
        hour, minute = ((int(twelve[1]) % 12 + (12 if twelve[3] == "pm" else 0), int(twelve[2] or 0)) if twelve
                        else (int(clock[1]), int(clock[2])))
        start = f"{first_day.isoformat()}T{hour:02d}:{minute:02d}"
    hours = (("19:00", "22:30") if re.search(r"evening|tonight|night", t) else ("12:00", "14:00") if "lunch" in t
             else ("08:00", "12:00") if "morning" in t else ("13:00", "18:00") if "afternoon" in t else ("08:00", "20:00"))
    return {"title": title[:1].upper() + title[1:] or "New item", "kind": kind, "duration_min": duration, "start": start,
            "start_date": first_day.isoformat(), "end_date": last_day.isoformat(), "day_start": hours[0],
            "day_end": hours[1], "days": named or WEEKDAYS,
            "flexibility": suggest_flex(text)}


def read_item(text: str, person: str) -> ItemAsk:
    system = READER.format(name=store.name(person), today=TODAY, weekday=nice_day(TODAY)[:3], flex_guide=FLEX_GUIDE)

    def fake(messages):
        return AIMessage(content="", tool_calls=[{"name": "add_item", "args": read_by_rules(text), "id": "mock-item"}])
    reply = llm.call([SystemMessage(system), HumanMessage(text)], [add_item], fake=fake, tool_choice="add_item")
    return ItemAsk.model_validate(reply.tool_calls[0]["args"])


def mentioned(person: str, text: str) -> list[dict]:
    """People the person knows (anyone in their chats) whose name appears in the text, with
    where they know them from, so the agent can ask "did you mean ...?"."""
    out = []
    for c in store.chats(person):
        for pid in store.members(c["id"]):
            if pid == person or any(m["id"] == pid for m in out):
                continue
            given, full = store.given(pid), store.name(pid)
            if re.search(rf"\b({re.escape(given)}|{re.escape(full)})\b", text, re.I):
                where = [ch["title"] or "your direct chat" for ch in store.chats(person) if pid in store.members(ch["id"])]
                out.append({"id": pid, "name": given, "label": f"{full} ({', '.join(where)})"})
    return out


def send(person: str, proposal: dict, choice: int | None, people: list[str], flexible: bool,
         chat_id: str | None = None) -> str:
    """Hand the item to the agents as a meeting request with these people, in the group you
    chose (or your chat with them): the coordinator asks their agents, and it lands on everyone's
    calendar once you approve. Returns the meeting request's id."""
    from scheduler.demo import engine
    rid = proposal["rid"]
    if flexible or choice is None:
        window = proposal["window"]
    else:
        s, e = proposal["options"][choice]
        window = {"start_date": s[:10], "end_date": s[:10], "day_start": s[11:16], "day_end": e[11:16],
                  "days": [WEEKDAYS[date.fromisoformat(s[:10]).weekday()]]}
    names = ", ".join(store.given(p) for p in people)
    if chat_id and not set(people) <= set(store.members(chat_id)):
        chat_id = None                                # someone outside the chosen group: a chat with exactly them
    chat_id = chat_id or (store.direct_chat(person, people[0]) if len(people) == 1 else
                          store.group_with({person, *people})) or store.new_chat(names, "group", [person, *people],
                                                             tags=[proposal["kind"] if proposal["kind"] in store.TAGS else "others"])
    ask = {"attendees": [person, *people], "optional": [], "topic": proposal["title"],
           "duration_min": proposal["duration_min"], **window}
    meeting = engine.send_meeting(person, chat_id, ask, f"{proposal['title']}, from the calendar",
                                  exact=not (flexible or choice is None))
    store.add_trace(rid, person, "answer", f"Chose to send it to {names}: meeting request {meeting}", [person])
    store.add_trace(rid, f"personal:{person}", "outcome", f"handed to the agents as meeting request {meeting}", [person])
    store.update_request(rid, status="sent to the agents", outcome={"status": "sent", "meeting": meeting})
    return meeting


def end_of(start: str, minutes: int) -> str:
    return (datetime.fromisoformat(start) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M")


def start(person: str, text: str, when: tuple[str, str] | None = None) -> dict:
    """Read the item and the person's calendars; return the agent's questions as a proposal.
    `when` is a time the person already picked on the calendar: the agent checks it for clashes
    and, if it clashes, offers the nearest free times that day instead."""
    mode = store.setting("llm_mode", "mock")
    rid = store.new_request(person, text, mode, kind="analyse")
    os.environ["SCHEDULER_FAKE_LLM"] = "1" if mode == "mock" else "0"
    llm.reset_usage()
    store.add_trace(rid, person, "initiated", f"{store.name(person)} asked their agent, privately, to add: \"{text}\"",
                    [person])
    if mode == "real" and not os.environ.get("OPENAI_API_KEY"):
        store.update_request(rid, status="error")
        store.add_trace(rid, "system", "error", "no OpenAI key in .env", [person])
        raise RuntimeError("No OpenAI key: add OPENAI_API_KEY to .env, or turn off Enable model calls.")
    ask = read_item(text, person)
    if when:
        ask.start = when[0]
        ask.duration_min = int((datetime.fromisoformat(when[1]) - datetime.fromisoformat(when[0])).total_seconds() // 60)
    p = store.one("select * from people where id = ?", (person,))
    window = nice_slot(ask.start, end_of(ask.start, ask.duration_min)) if ask.start else \
        f"{', '.join(d.capitalize() for d in ask.days) if ask.days != WEEKDAYS else 'any day'} " \
        f"{ask.day_start}-{ask.day_end}, {nice_day(ask.start_date)} to {nice_day(ask.end_date)}"
    store.add_trace(rid, f"host:{person}", "read", f"Read it as: {ask.title}, {ask.duration_min} minutes, {window}", [person])
    mine = store.events(person)
    store.add_trace(rid, f"personal:{person}", "call", f"read_my_calendar participant_id={person}", [person])
    clashes: list[str] = []
    if ask.start:
        options = [(ask.start, end_of(ask.start, ask.duration_min))]
        clashes = [e["title"] for e in mine if overlaps(e["start_at"], e["end_at"], *options[0])]
        if clashes:                                       # the nearest free times that day, as alternatives
            day = ask.start[:10]
            near = [(s, e) for s, e in candidate_slots(day, day, ask.duration_min, p["hours_start"], p["hours_end"], WEEKDAYS)
                    if not any(overlaps(x["start_at"], x["end_at"], s, e) for x in mine)]
            near.sort(key=lambda se: abs(datetime.fromisoformat(se[0]) - datetime.fromisoformat(ask.start)))
            options += near[:2]
        store.add_trace(rid, f"personal:{person}", "check", f"{len(clashes)} clash(es) at {nice_slot(*options[0])}"
                        + (f": {', '.join(clashes)}; nearest free: "
                           + (", ".join(nice_slot(s, e) for s, e in options[1:]) or "none") if clashes else ""), [person])
    else:
        free =[(s, e) for s, e in candidate_slots(ask.start_date, ask.end_date, ask.duration_min, ask.day_start,
                                                   ask.day_end, ask.days)
                if p["hours_start"] <= s[11:] and e[11:] <= p["hours_end"]
                and not any(overlaps(x["start_at"], x["end_at"], s, e) for x in mine)]
        by_day = list({s[:10]: (s, e) for s, e in reversed(free)}.values())[::-1]   # the first free slot of each day
        options = (by_day + [f for f in free if f not in by_day])[:3]
        store.add_trace(rid, f"personal:{person}", "check", f"{len(free)} free slots; offering "
                        + (", ".join(nice_slot(s, e) for s, e in options) or "none"), [person])
    mentions = mentioned(person, text)
    if mentions:
        store.add_trace(rid, f"personal:{person}", "check", "Mentions " + ", ".join(m["label"] for m in mentions)
                        + ": their calendars are private to their own agents", [person])
    questions = (["It clashes: keep this time, or take a nearby free one?"] if clashes else
                 ["Which of these times do you prefer?"] if len(options) > 1 else [])
    questions += [f"Who's coming? You mentioned {', '.join(m['name'] for m in mentions)}: invite them, or a group "
                  "they're in?" if mentions else "Who's coming: just you, or a group?"]
    questions += ["How easily could it move if someone needs the time?", "Which calendar does it belong on?"]
    store.add_trace(rid, f"personal:{person}", "ask", "Asked you: " + " ".join(questions), [person])
    day = (ask.start or ask.start_date)[:10]
    proposal = {"rid": rid, "title": ask.title, "kind": ask.kind, "duration_min": ask.duration_min,
                "options": options, "clashes": clashes, "flex": ask.flexibility, "exact": bool(ask.start),
                "questions": questions, "mentions": mentions,
                "window": {"start_date": ask.start_date if not ask.start else day,
                           "end_date": ask.end_date if not ask.start else day,
                           "day_start": ask.day_start if not ask.start else "08:00",
                           "day_end": ask.day_end if not ask.start else "22:00",
                           "days": ask.days if not ask.start else WEEKDAYS}}
    store.update_request(rid, status="waiting for you", parsed=proposal | {"topic": ask.title, "summary": window,
                                                                           "attendee_ids": [person]})
    return proposal


def commit(person: str, proposal: dict, choice: int | None, flex: int, calendar_id: str) -> str | None:
    """Add the item as the person answered, or record that they chose not to. Returns the event id."""
    rid = proposal["rid"]
    if choice is None:
        store.add_trace(rid, person, "answer", "Chose not to add it", [person])
        store.update_request(rid, status="not added")
        return None
    s, e = proposal["options"][choice]
    calendar = next(c["name"] for c in store.calendars(person) if c["id"] == calendar_id)
    store.add_trace(rid, person, "answer", f"Chose {nice_slot(s, e)}; {store.FLEX[flex].lower()}; "
                                           f"{calendar} calendar", [person])
    eid = store.add_event(calendar_id, proposal["title"], s, e, flex, request_id=rid)
    store.add_trace(rid, f"personal:{person}", "outcome", f"added \"{proposal['title']}\" {s} to {e[11:]}", [person])
    store.update_request(rid, status="added", outcome={"status": "added", "start": s, "end": e, "event_id": eid})
    return eid
