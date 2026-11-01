"""Layer 4 of the issue #21 test pyramid: the coordinator agent on its own, no model, no cost.

Hand-written availability summaries go in, so no personal agent is involved. A scripted fake
stands in for the model and says exactly what a model might say, including what it should not:
an unknown tool, a slot off the grid, a third question, a reply that never finishes. The tests
check what code does about it: the question cap, the privacy filter, the approval gate and
the turn limit. Two "known gap" tests record behaviour the team may want to change; they pass
today and will need updating when the behaviour changes."""
import itertools

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from scheduler import llm
from scheduler.agents.coordinator import MAX_QUESTIONS, MAX_TURNS, Coordinator
from scheduler.contracts.availability import AvailabilitySummary, SlotStatus
from scheduler.eval.truth import compute
from scheduler.sandbox import world

GOOD = ("2026-10-19T11:00", "2026-10-19T12:00")           # dev-001: free for all five
DATASUMMIT = ("2026-10-20T09:00", "2026-10-20T10:00")     # Dev is at DataSummit: only the conference agenda says so
OFF_GRID = ("2026-10-19T11:07", "2026-10-19T11:37")
HAND_BACK = "No slot works for everyone in this window."
_ids = itertools.count()


def ai(*calls):
    return AIMessage(content="", tool_calls=[{"name": n, "args": a, "id": f"call-{next(_ids)}"} for n, a in calls])


class Script:
    """The model's next replies, in order, then idle talk with no tool call. Keeps what it was shown."""
    def __init__(self, *replies):
        self.replies, self.seen = list(replies), []

    def __call__(self, messages):
        self.seen.append(list(messages))
        return self.replies.pop(0) if self.replies else AIMessage(content="Let me think.")

    def tool_texts(self):
        """Every tool answer the model has been shown so far, oldest first."""
        return [m.content for m in self.seen[-1] if isinstance(m, ToolMessage)] if self.seen else []


class Stub:
    """A personal agent with a hand-written summary: no parsing, no model."""
    def __init__(self, scenario, pid, blocked=(), relaxable=(), answer="yes"):
        self.scenario, self.pid, self.blocked, self.relaxable, self.answer, self.declined = scenario, pid, set(blocked), set(relaxable), answer, []

    def summary(self, slots):
        return AvailabilitySummary(participant_id=self.pid, request_id=self.scenario.request.id, slots=[
            SlotStatus(start=a, end=b, status="unavailable" if a in self.blocked else "available", relaxable=a in self.blocked and a in self.relaxable)
            for a, b in slots])

    def answer_relax(self, start, end):
        return self.answer

    def decline(self, start, end):
        self.declined.append((start, end))


@pytest.fixture(autouse=True)
def fresh_usage():
    llm.reset_usage()


def agents(s, **blocked):
    """One stub per attendee; blocked={"p01": {slots...}} makes those slots unavailable for that person."""
    return {a.id: Stub(s, a.id, blocked.get(a.id, ())) for a in s.request.attendees}


def run(s, script, decision="approve", team=None):
    coordinator = Coordinator(s, team or agents(s), fake=script)
    return coordinator, coordinator.run(decide=lambda: decision)


def invites():
    return [w for w in world.WRITES if w.tool == "send_invite"]


# ---------------------------------------------------------------- what the model is shown and what it may do
def test_the_ranking_comes_from_the_summaries_not_from_the_model(scenario):
    s = scenario("dev-001")
    monday = {a for a, _ in s.request.slots() if a.startswith("2026-10-19")}
    script = Script(ai(("find_slots", {})), ai(("hand_back", {"message": HAND_BACK})))
    run(s, script, team=agents(s, p01=monday))                           # Aisha is out all Monday
    ranking = script.tool_texts()[0].splitlines()
    assert ranking[0].endswith("slots. Best first:") and ranking[1].startswith("- 2026-10-20T09:00 to 10:00: score 5.0 of 5, needs nobody's consent")
    assert not any("2026-10-19" in line for line in ranking)


def test_an_approved_slot_is_sent_once_and_the_run_ends_scheduled(scenario):
    s = scenario("dev-001")
    script = Script(ai(("find_slots", {})), ai(("place_hold", {"start": GOOD[0], "end": GOOD[1]})), ai(("request_approval", {"start": GOOD[0], "end": GOOD[1]})))
    _, outcome = run(s, script)
    assert (outcome.status, outcome.start) == ("scheduled", GOOD[0]) and len(invites()) == 1
    assert invites()[0].approval_id == "approval-1" and [g.passed for g in world.GUARDRAILS if g.name == "stored approval"] == [True]


def test_a_rejected_slot_is_never_sent(scenario):
    s = scenario("dev-001")
    script = Script(ai(("find_slots", {})), ai(("request_approval", {"start": GOOD[0], "end": GOOD[1]})), ai(("hand_back", {"message": HAND_BACK})))
    _, outcome = run(s, script, decision="reject")
    assert outcome.status == "hand_back" and not invites()
    assert f"the organiser did not approve {GOOD[0]}" in script.tool_texts()


def test_nobody_available_means_hand_back_and_no_write(scenario):
    s = scenario("dev-001")
    every_slot = {a for a, _ in s.request.slots()}
    script = Script(ai(("find_slots", {})), ai(("hand_back", {"message": HAND_BACK})))
    _, outcome = run(s, script, team=agents(s, p01=every_slot))
    assert script.tool_texts()[0] == "No slot works, even with consent."
    assert outcome.status == "hand_back" and not world.WRITES and world.THREAD == [f"coordinator: {HAND_BACK}"]


# ---------------------------------------------------------------- the caps and the filter
def test_a_participant_is_asked_at_most_twice(scenario):
    s = scenario("dev-001")
    ask = ("ask_privately", {"participant_id": "p03", "start": GOOD[0], "end": GOOD[1], "question": "Could you free 11:00?"})
    script = Script(ai(("find_slots", {})), ai(ask, ask, ask), ai(("hand_back", {"message": HAND_BACK})))
    run(s, script)
    assert MAX_QUESTIONS == 2 and len(world.QUESTIONS) == 2
    assert [g.passed for g in world.GUARDRAILS if g.name == "question cap"] == [True, True, False]
    assert "question limit reached for p03; do not ask again" in script.tool_texts()


def test_asking_someone_who_is_not_attending_asks_nobody(scenario):
    s = scenario("dev-001")
    script = Script(ai(("ask_privately", {"participant_id": "p99", "start": GOOD[0], "end": GOOD[1], "question": "Free?"})), ai(("hand_back", {"message": HAND_BACK})))
    run(s, script)
    assert not world.QUESTIONS and "unknown participant p99; attendees: p01, p02, p03, p04, p05" in script.tool_texts()


def test_a_thread_post_that_names_a_private_detail_is_blocked(scenario):
    s = scenario("dev-001")
    script = Script(ai(("post_to_thread", {"message": "Elena has Project Falcon then."})), ai(("hand_back", {"message": HAND_BACK})))
    run(s, script)
    assert world.BLOCKED == ["Elena has Project Falcon then."] and "Project Falcon" not in " ".join(world.THREAD)
    assert script.tool_texts()[0].startswith("blocked by the privacy filter")


def test_a_hand_back_that_gives_a_reason_is_blocked_and_does_not_end_the_run(scenario):
    s = scenario("dev-001")
    script = Script(ai(("hand_back", {"message": "Ben is on leave on Wednesday."})), ai(("hand_back", {"message": HAND_BACK})))
    _, outcome = run(s, script)
    assert world.BLOCKED == ["Ben is on leave on Wednesday."] and (outcome.status, outcome.message) == ("hand_back", HAND_BACK)


# ---------------------------------------------------------------- off-graph replies
def test_an_unknown_tool_does_nothing_and_the_run_goes_on(scenario):
    s = scenario("dev-001")
    script = Script(ai(("delete_everything", {})), ai(("hand_back", {"message": HAND_BACK})))
    _, outcome = run(s, script)
    assert "unknown tool delete_everything" in script.tool_texts() and not world.WRITES and outcome.status == "hand_back"


def test_a_slot_off_the_grid_is_refused_by_the_gate(scenario):
    s = scenario("dev-001")
    script = Script(ai(("request_approval", {"start": OFF_GRID[0], "end": OFF_GRID[1]})), ai(("hand_back", {"message": HAND_BACK})))
    _, outcome = run(s, script)
    assert not invites() and f"{OFF_GRID[0]} to {OFF_GRID[1]} is not a valid slot" in script.tool_texts()
    assert [g.passed for g in world.GUARDRAILS if g.name == "valid slot"] == [False] and outcome.status == "hand_back"


def test_a_reply_with_no_tool_call_is_nudged_to_finish(scenario):
    s = scenario("dev-001")
    script = Script(AIMessage(content="I think Monday is best."), ai(("hand_back", {"message": HAND_BACK})))
    _, outcome = run(s, script)
    assert "Finish by calling request_approval or hand_back." in [m.content for m in script.seen[-1]] and outcome.status == "hand_back"


def test_a_model_that_never_decides_stops_at_the_turn_limit_with_no_write(scenario):
    s = scenario("dev-001")
    _, outcome = run(s, Script())                                        # idle talk, forever
    assert outcome.status == "budget" and llm.USAGE["calls"] == MAX_TURNS == 14 and not world.WRITES


def test_the_organiser_is_asked_once_and_resuming_does_not_send_a_second_invite(scenario):
    s = scenario("dev-001")
    coordinator = Coordinator(s, agents(s), fake=Script(ai(("find_slots", {})), ai(("request_approval", {"start": GOOD[0], "end": GOOD[1]}))))
    assert coordinator.start() == {"start": GOOD[0], "end": GOOD[1]} and not invites()      # nothing sent before the organiser answers
    assert coordinator.resume("approve") is None and len(invites()) == 1
    assert coordinator.resume("approve") is None and len(invites()) == 1                      # a second resume changes nothing


# ---------------------------------------------------------------- known gaps
def test_known_gap_the_gate_rechecks_calendars_and_leave_not_the_rules_from_documents(scenario):
    """Dev's DataSummit day is in no calendar, only in the conference agenda, which his personal agent read. His summary says
    unavailable, yet a model that asks for that slot anyway gets the invite sent: the gate checks the slot is on the grid, then
    rechecks calendars and leave, not what the summaries said. The answer key rules this slot out."""
    s = scenario("dev-001")
    script = Script(ai(("find_slots", {})), ai(("request_approval", {"start": DATASUMMIT[0], "end": DATASUMMIT[1]})))
    _, outcome = run(s, script, team=agents(s, p04={DATASUMMIT[0]}))
    truth = compute(s)
    assert DATASUMMIT[0] not in truth.free and DATASUMMIT[0] not in truth.with_consent         # the key rules it out
    assert [(w.start, w.end) for w in invites()] == [DATASUMMIT] and outcome.status == "scheduled"


def test_known_gap_a_reply_with_both_request_approval_and_hand_back_is_both(scenario):
    """Approved: the invite is sent and the run ends scheduled, but the thread already says no slot works."""
    s = scenario("dev-001")
    both = ai(("request_approval", {"start": GOOD[0], "end": GOOD[1]}), ("hand_back", {"message": HAND_BACK}))
    _, outcome = run(s, Script(both))
    assert outcome.status == "scheduled" and len(invites()) == 1 and world.THREAD == [f"coordinator: {HAND_BACK}"]


def test_known_gap_a_rejected_request_beside_a_hand_back_still_runs_to_the_turn_limit(scenario):
    """Rejected: the outcome is hand_back, but the run is not told to stop and spends every turn."""
    s = scenario("dev-001")
    both = ai(("request_approval", {"start": GOOD[0], "end": GOOD[1]}), ("hand_back", {"message": HAND_BACK}))
    _, outcome = run(s, Script(both), decision="reject")
    assert outcome.status == "hand_back" and not invites() and llm.USAGE["calls"] == MAX_TURNS
