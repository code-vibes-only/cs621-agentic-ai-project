"""Layer 1 of the issue #21 test pyramid: every tool on its own, no model, no cost.

Each tool is marked read or write, and the tests hold it to that mark: a read tool leaves the
sandbox's state exactly as it was and logs exactly one call; a write tool adds exactly one
record to the write log, and only when the gate allows it. Each tool gets a valid call, a bad
reference, an empty answer and a call the gate must refuse."""
import copy

import pytest

from scheduler.contracts.scenario import Message
from scheduler.sandbox import world
from scheduler.sandbox.tools import personal_tools, shared_tools

SLOT = ("2026-10-19T11:00", "2026-10-19T12:00")
OTHER = ("2026-10-19T12:00", "2026-10-19T13:00")


def state():
    """Everything a read tool must leave alone."""
    return (copy.deepcopy(world.CALENDARS), copy.deepcopy(world.HOLDS), copy.deepcopy(world.APPROVALS),
            copy.deepcopy(world.CONSENTS), list(world.WRITES), list(world.THREAD), list(world.BLOCKED))


def by_name(tools):
    return {t.name: t for t in tools}


# ---------------------------------------------------------------- read tools
# (tool, arguments, the name it logs): the shared agent's reads log under the personal agent's names
PERSONAL_READS = [
    ("read_my_calendar", {}, "read_my_calendar"),
    ("get_leave", {}, "get_leave"),
    ("read_my_messages", {}, "read_my_messages"),
    ("search_schedules", {"query": "public holidays October 2026"}, "search_schedules"),
    ("ask_my_participant", {"question": "Which hours do you mean?"}, "ask_participant"),
]
SHARED_READS = [
    ("read_calendar", {"participant_id": "p05"}, "read_my_calendar"),
    ("get_leave", {"participant_id": "p02"}, "get_leave"),
    ("read_messages", {"participant_id": "p01"}, "read_my_messages"),
    ("search_schedules", {"query": "public holidays October 2026"}, "search_schedules"),
    ("ask_participant", {"participant_id": "p01", "question": "Which hours do you mean?"}, "ask_participant"),
]


@pytest.mark.parametrize("name, args, logged", PERSONAL_READS)
def test_a_personal_read_tool_changes_nothing_and_logs_one_call(scenario, name, args, logged):
    scenario("dev-001")
    before = state()
    by_name(personal_tools("p01"))[name].invoke(args)
    assert state() == before and [c.tool for c in world.CALLS] == [logged]
    assert world.CALLS[0].caller == "personal:p01"


@pytest.mark.parametrize("name, args, logged", SHARED_READS)
def test_a_shared_read_tool_changes_nothing_and_logs_one_call(scenario, name, args, logged):
    scenario("dev-001")
    before = state()
    by_name(shared_tools())[name].invoke(args)
    assert state() == before and [c.tool for c in world.CALLS] == [logged]
    # a question goes out under the name of the person it is put to; every other read is the shared agent's
    assert world.CALLS[0].caller == ("personal:p01" if name == "ask_participant" else "shared")


def test_the_personal_agent_has_exactly_these_five_tools_and_none_writes(scenario):
    scenario("dev-001")
    assert sorted(by_name(personal_tools("p01"))) == sorted(n for n, _, _ in PERSONAL_READS)
    assert sorted(by_name(shared_tools())) == sorted(n for n, _, _ in SHARED_READS)


# valid: what a good call returns
def test_read_calendar_lists_events_one_per_line_with_their_calendar(scenario):
    scenario("dev-001")
    line = by_name(personal_tools("p05"))["read_my_calendar"].invoke({})
    assert line.startswith("e-p05-1 | ") and "2026-10-19T10:00" in line and "movable=False" in line and "Project Falcon" in line


def test_get_leave_shows_the_dates_and_whether_the_person_can_be_reached(scenario):
    scenario("dev-001")
    text = by_name(personal_tools("p02"))["get_leave"].invoke({})
    assert "2026-10-21 | 2026-10-22" in text and "reachable_if_urgent=" in text and "Tampines flat handover" in text


def test_read_messages_shows_sender_and_text(scenario):
    s = scenario("dev-001")
    s.participant("p02").messages.append(Message(id="msg-p02-1", sender="Banyan Clinic", received="2026-10-10", text="Confirmed for 20 Oct, 15:00."))
    text = by_name(personal_tools("p02"))["read_my_messages"].invoke({})
    assert text == "msg-p02-1 | 2026-10-10 | Banyan Clinic | Confirmed for 20 Oct, 15:00."


def test_search_returns_the_document_with_its_id_date_and_source(scenario):
    scenario("dev-001")
    text = by_name(personal_tools("p01"))["search_schedules"].invoke({"query": "public holidays October 2026"})
    assert text.startswith("[doc-sg-public-holidays-2026] ") and "as of " in text and "source: " in text


def test_a_clarifying_question_returns_the_scripted_answer(scenario):
    s = scenario("dev-015")
    reply = next(r for r in s.scripted.replies if r.about == "clarify")
    assert by_name(personal_tools(reply.participant_id))["ask_my_participant"].invoke({"question": "Which hours?"}) == reply.answer


# empty: nothing to return is said in words, never an empty string or an error
@pytest.mark.parametrize("name, args, empty", [
    ("read_my_calendar", {}, "no events"),
    ("get_leave", {}, "no leave"),
    ("read_my_messages", {}, "no messages"),
    ("ask_my_participant", {"question": "Which hours do you mean?"}, "no reply"),
])
def test_an_empty_answer_says_so(scenario, name, args, empty):
    scenario("dev-001")
    world.CALENDARS["p01"] = []
    assert by_name(personal_tools("p01"))[name].invoke(args) == empty


@pytest.mark.parametrize("query", ["zzzz qqqq", "", "a b", "   "])
def test_a_search_with_no_close_match_says_so(scenario, query):
    scenario("dev-001")
    assert by_name(personal_tools("p01"))["search_schedules"].invoke({"query": query}) == f"no matching documents for '{query}'"
    assert world.CALLS[-1].args["hits"] == []


def test_the_shared_tools_say_so_when_empty(scenario):
    scenario("dev-001")
    world.CALENDARS["p01"] = []
    tools = by_name(shared_tools())
    assert tools["read_calendar"].invoke({"participant_id": "p01"}) == "no events"
    assert tools["get_leave"].invoke({"participant_id": "p01"}) == "no leave"
    assert tools["read_messages"].invoke({"participant_id": "p01"}) == "no messages"


# bad reference: an unknown participant is an error that names the valid ones
@pytest.mark.parametrize("name, args", [
    ("read_calendar", {"participant_id": "p99"}),
    ("get_leave", {"participant_id": "p99"}),
    ("read_messages", {"participant_id": "p99"}),
    ("ask_participant", {"participant_id": "p99", "question": "Which hours?"}),
])
def test_a_shared_tool_refuses_an_unknown_participant(scenario, name, args):
    scenario("dev-001")
    with pytest.raises(ValueError, match="unknown participant p99; participants: p01, p02"):
        by_name(shared_tools())[name].invoke(args)


@pytest.mark.parametrize("name", ["read_my_calendar", "get_leave", "read_my_messages"])
def test_a_personal_tool_bound_to_an_unknown_participant_refuses(scenario, name):
    scenario("dev-001")
    with pytest.raises(ValueError, match="unknown participant p99"):
        by_name(personal_tools("p99"))[name].invoke({})


def test_a_personal_tool_takes_no_participant_argument(scenario):
    """The id is fixed in code, so no argument the model writes can reach another calendar."""
    scenario("dev-001")
    for tool in personal_tools("p01"):
        assert "participant_id" not in tool.args


# ---------------------------------------------------------------- write tools
def test_place_hold_writes_once_per_key(scenario):
    s = scenario("dev-001")
    assert world.place_hold(s.request.id, *SLOT, "k1", "coordinator") == "hold k1 on 2026-10-19T11:00-12:00"
    world.place_hold(s.request.id, *SLOT, "k1", "coordinator")                         # same key again
    assert [w.tool for w in world.WRITES] == ["place_hold"] and list(world.HOLDS) == ["k1"]
    world.place_hold(s.request.id, *OTHER, "k2", "coordinator")
    assert [w.key for w in world.WRITES] == ["k1", "k2"]


def test_release_hold_writes_only_for_a_hold_that_exists(scenario):
    s = scenario("dev-001")
    world.release_hold(s.request.id, "nothing-here", "coordinator")
    assert not world.WRITES
    world.place_hold(s.request.id, *SLOT, "k1", "coordinator")
    world.release_hold(s.request.id, "k1", "coordinator")
    world.release_hold(s.request.id, "k1", "coordinator")
    assert [w.tool for w in world.WRITES] == ["place_hold", "release_hold"] and not world.HOLDS


def test_a_hold_never_touches_a_calendar(scenario):
    s = scenario("dev-001")
    before = copy.deepcopy(world.CALENDARS)
    world.place_hold(s.request.id, *SLOT, "k1", "coordinator")
    assert world.CALENDARS == before


def test_store_approval_is_a_stored_decision_not_a_write(scenario):
    scenario("dev-001")
    first = world.store_approval(*SLOT, "approve")
    second = world.store_approval(*OTHER, "reject")
    assert (first, second) == ("approval-1", "approval-2") and not world.WRITES
    assert world.APPROVALS["approval-2"] == {"start": OTHER[0], "end": OTHER[1], "decision": "reject"}


def test_an_approved_invite_lands_on_every_attendee_calendar(scenario):
    s = scenario("dev-001")
    approval = world.store_approval(*SLOT, "approve")
    assert world.send_invite(s.request.id, *SLOT, approval, "k") == "invite sent for 2026-10-19T11:00-12:00"
    assert [(w.tool, w.approval_id) for w in world.WRITES] == [("send_invite", approval)]
    assert set(world.read_back(s.request.id, "gate").values()) == {SLOT}


@pytest.mark.parametrize("why, approval, slot", [
    ("no such approval", "approval-9", SLOT),
    ("approval for another slot", "other", SLOT),
    ("approval is a rejection", "rejected", SLOT),
    ("same start, different end", "shorter", SLOT),
])
def test_the_gate_refuses_an_invite_without_an_approval_for_that_exact_slot(scenario, why, approval, slot):
    s = scenario("dev-001")
    stored = {"other": world.store_approval(*OTHER, "approve") if approval == "other" else None,
              "rejected": world.store_approval(*SLOT, "reject") if approval == "rejected" else None,
              "shorter": world.store_approval(SLOT[0], "2026-10-19T11:30", "approve") if approval == "shorter" else None}
    before = state()
    with pytest.raises(PermissionError, match="no stored approval for 2026-10-19T11:00-2026-10-19T12:00"):
        world.send_invite(s.request.id, *slot, stored.get(approval) or approval, "k")
    assert state() == before and not world.WRITES                       # nothing written, no calendar touched
    assert [(g.name, g.passed) for g in world.GUARDRAILS] == [("stored approval", False)]


def test_an_invite_replaces_the_earlier_one_for_the_same_request(scenario):
    s = scenario("dev-001")
    world.send_invite(s.request.id, *SLOT, world.store_approval(*SLOT, "approve"), "k1")
    world.send_invite(s.request.id, *OTHER, world.store_approval(*OTHER, "approve"), "k2")
    landed = world.read_back(s.request.id, "gate")
    assert set(landed.values()) == {OTHER}                                # a replan moves it, never doubles it
    assert sum(e["id"] == f"invite-{s.request.id}" for e in world.CALENDARS["p01"]) == 1


def test_read_back_reports_none_before_any_invite(scenario):
    s = scenario("dev-001")
    assert set(world.read_back(s.request.id, "gate").values()) == {None}
