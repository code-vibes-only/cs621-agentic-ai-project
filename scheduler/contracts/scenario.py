"""The scenario file: one test case, with its world, its scripted replies and events, and
the ground truth. Ground truth is written before any agent runs, from the same rules the
agents read, so an agent's output can never become its own answer key."""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from scheduler.contracts.constraints import DailyRule, WindowRule
from scheduler.timegrid import WEEKDAYS, Weekday, candidate_slots


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Event(Strict):
    id: str
    title: str                       # may be private, e.g. a confidential project
    start: str
    end: str
    movable: bool = False
    priority: Literal["low", "normal", "high"] = "normal"
    owner: str = ""


class Calendar(Strict):
    """One of a participant's calendars, e.g. "work", "family", "club" or "personal"."""
    name: str
    events: list[Event] = []


class Leave(Strict):
    """Time away: leave, a trip or a holiday. The reason is private."""
    id: str
    start_date: str
    end_date: str
    reason: str                      # private
    reachable_if_urgent: bool = False


class Message(Strict):
    """A message in the participant's own inbox or chats, e.g. a booking confirmation or a
    plan agreed with friends. Written by someone else, and private to the participant."""
    id: str
    sender: str
    received: str
    text: str


class Preference(Strict):
    """Something the participant said for this request, e.g. "no meetings before 10"."""
    id: str
    text: str


class MemoryNote(Strict):
    """A note kept from an earlier meeting, with where it came from and when it stops being true."""
    id: str
    text: str
    source: Literal["participant", "agent_guess"] = "participant"
    stated_on: str
    expires: str | None = None
    scope: str = "persistent"        # "persistent", or "meeting:<request id>" for one meeting only


class Consent(Strict):
    id: str
    refs: list[str]                  # the commitments it covers
    text: str


class Participant(Strict):
    id: str
    name: str
    hours_start: str = "09:00"       # the hours they accept meetings, on any day
    hours_end: str = "18:00"
    calendars: list[Calendar] = []
    leave: list[Leave] = []
    messages: list[Message] = []
    preferences: list[Preference] = []
    memory: list[MemoryNote] = []
    pre_consent: list[Consent] = []


class Attendee(Strict):
    id: str
    role: Literal["required", "optional"] = "required"


class Request(Strict):
    id: str
    organiser_id: str
    text: str
    duration_min: int
    start_date: str
    end_date: str
    day_start: str = "09:00"
    day_end: str = "18:00"
    days: list[Weekday] = WEEKDAYS[:5]  # the weekdays a slot may fall on
    attendees: list[Attendee]

    def slots(self) -> list[tuple[str, str]]:
        """Every candidate slot of this request."""
        return candidate_slots(self.start_date, self.end_date, self.duration_min, self.day_start,
                               self.day_end, self.days)


class Reply(Strict):
    """A scripted answer from a participant to a private question from their personal agent."""
    participant_id: str
    about: str                       # a commitment ref, or "clarify"
    answer: str
    consent: bool = False
    slot: str | None = None          # consent only for the slot starting here (None: any slot)


class ScriptedEvent(Strict):
    at: Literal["start", "after_approval", "after_invite"]
    type: Literal["new_meeting", "rsvp", "thread_message"]
    participant_id: str
    meeting: Event | None = None     # new_meeting: lands on this participant's calendar named below
    calendar: str = "work"
    response: Literal["decline", "accept"] | None = None    # rsvp
    text: str | None = None          # thread_message: posted in the request thread


class Approval(Strict):
    decision: Literal["approve", "reject"] = "approve"
    note: str = ""


class Scripted(Strict):
    replies: list[Reply] = []
    approval: Approval = Approval()
    events: list[ScriptedEvent] = []


class TruthRule(Strict):
    """One ground-truth rule for one participant; usual hours are added by code."""
    participant_id: str
    rule: WindowRule | DailyRule


class Attack(Strict):
    """An attack case: hostile text planted where an agent will read it. The grader is inverted:
    the attack failed when none of `must_not` happened."""
    kind: Literal["injected_page", "injected_message", "thread_deputy", "poisoned_memory"]
    payload: str                     # where the hostile text sits: a document, message or memory id, or "thread"
    must_not: list[Literal["leak", "send_without_approval", "relax_without_consent", "hard_violation"]]
    weight: float                    # the consequence if it works, 0-1: a leak or an unapproved invite is 1


class GroundTruth(Strict):
    rules: list[TruthRule]           # every participant's constraints in the final world
    outcome: Literal["scheduled", "hand_back"]
    expected_slot: str | None = None # hand-checked start of the best slot, where one exists
    must_ask: list[str] = []         # participants the coordinator must ask privately
    must_lookup: list[str] = []      # corpus documents some agent must retrieve
    must_read: list[str] = []        # participants whose messages change the answer: their agent must read them
    must_clarify: list[str] = []     # participants whose personal agent must ask them to clarify
    must_alert: list[str] = []       # participants who must be alerted to a clash with the agreed meeting
    canaries: list[str] = []         # private phrases that must never reach the thread
    final_slot_rule: Literal["best", "any_feasible"] = "best"
    attack: Attack | None = None


class Scenario(Strict):
    id: str
    split: Literal["dev", "heldout"]
    tags: list[str]
    seed: int = 0
    generator_version: str = "hand"
    notes: str = ""
    today: str                       # the date the request is made (memory expiry is read against it)
    participants: list[Participant]
    request: Request
    corpus: list[str] = []
    scripted: Scripted = Scripted()
    ground_truth: GroundTruth

    def participant(self, pid: str) -> Participant:
        return next(p for p in self.participants if p.id == pid)

    def role(self, pid: str) -> str:
        return next(a.role for a in self.request.attendees if a.id == pid)


def load_scenario(path: Path) -> Scenario:
    return Scenario.model_validate(json.loads(Path(path).read_text()))


def load_split(data_dir: Path, split: str) -> list[Scenario]:
    return [load_scenario(p) for p in sorted((data_dir / "scenarios" / split).glob("*.json"))]
