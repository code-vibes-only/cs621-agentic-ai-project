import pytest

from scheduler.contracts.scenario import Message
from scheduler.sandbox import world
from scheduler.sandbox.tools import personal_tools


def test_reset_clears_every_log(scenario):
    s = scenario("dev-001")
    world.place_hold(s.request.id, "2026-10-19T11:00", "2026-10-19T12:00", "k1", "test")
    world.note("coordinator", "test", "left over")
    world.guard("test check", "output", "left over", False)
    for log in (world.THREAD, world.BLOCKED, world.CONTEXT):
        log.append("left over")
    world.FIRED.add(0)
    scenario("dev-001")
    assert not world.WRITES and not world.CALLS and not world.HOLDS
    assert not (world.THREAD or world.BLOCKED or world.QUESTIONS or world.SUMMARIES or world.CONTEXT
                or world.TIMELINE or world.GUARDRAILS or world.FIRED)        # nothing carries into the next scenario


def test_personal_tools_reach_only_their_own_participant(scenario):
    scenario("dev-001")
    calendar = {t.name: t for t in personal_tools("p05")}["read_my_calendar"].invoke({})
    assert "Project Falcon" in calendar and "Orchid" not in calendar


def test_messages_reach_only_their_own_participant(scenario):
    s = scenario("dev-001")
    s.participant("p02").messages.append(Message(id="msg-p02-1", sender="Banyan Clinic", received="2026-10-10",
                                                 text="Your appointment at Banyan Clinic is confirmed for 20 Oct, 15:00."))
    tools = {pid: {t.name: t for t in personal_tools(pid)} for pid in ("p01", "p02")}
    assert "Banyan Clinic" in tools["p02"]["read_my_messages"].invoke({})
    assert tools["p01"]["read_my_messages"].invoke({}) == "no messages"
    assert world.CALLS[-1].tool == "read_my_messages" and world.CALLS[-1].caller == "personal:p01"


def test_every_step_is_on_the_timeline_with_its_audience(scenario):
    scenario("dev-001")
    {t.name: t for t in personal_tools("p01")}["read_my_calendar"].invoke({})
    world.note("coordinator", "thread", "Proposed: Mon 11:00.", ["thread"])
    assert [(e.seq, e.actor, e.visible_to) for e in world.TIMELINE] == [
        (1, "personal:p01", ["p01"]), (2, "coordinator", ["thread"])]


def test_unknown_participant_is_a_loud_error(scenario):
    scenario("dev-001")
    with pytest.raises(ValueError, match="participants: p01"):
        world.read_calendar("p99", "test")


def test_invite_needs_an_approval_for_that_exact_slot(scenario):
    s = scenario("dev-001")
    a, b = "2026-10-19T11:00", "2026-10-19T12:00"
    with pytest.raises(PermissionError):
        world.send_invite(s.request.id, a, b, "approval-9", "k")
    approval = world.store_approval("2026-10-19T12:00", "2026-10-19T13:00", "approve")
    with pytest.raises(PermissionError):
        world.send_invite(s.request.id, a, b, approval, "k")


def test_invite_is_idempotent_and_read_back(scenario):
    s = scenario("dev-001")
    a, b = "2026-10-19T11:00", "2026-10-19T12:00"
    approval = world.store_approval(a, b, "approve")
    world.send_invite(s.request.id, a, b, approval, "k")
    assert world.send_invite(s.request.id, a, b, approval, "k") == "already sent"
    assert sum(w.tool == "send_invite" for w in world.WRITES) == 1
    assert set(world.read_back(s.request.id, "test").values()) == {(a, b)}


def test_search_keeps_only_close_matches(scenario):
    scenario("dev-001")
    assert [d.id for d in world.search("public holidays October 2026", "test")] == ["doc-sg-public-holidays-2026"]
    assert [d.id for d in world.search("DataSummit agenda 2026 October Aisha Ben Chloe Dev Nair", "test")] == ["doc-datasummit-2026"]
