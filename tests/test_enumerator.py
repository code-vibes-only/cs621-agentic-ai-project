from scheduler.contracts.availability import AvailabilitySummary, Window
from scheduler.engine.enumerator import enumerate_slots

SLOTS = [("2026-10-19T10:00", "2026-10-19T11:00"), ("2026-10-19T11:00", "2026-10-19T12:00")]


def summ(pid, *statuses):
    return AvailabilitySummary(participant_id=pid, request_id="r", slots=[
        {"start": s, "end": e, **st} for (s, e), st in zip(SLOTS, statuses)])


def test_required_unavailable_blocks_and_optional_never_does():
    out = enumerate_slots({"p1": summ("p1", {"status": "unavailable"}, {"status": "available"}),
                           "p2": summ("p2", {"status": "available"}, {"status": "unavailable"})},
                          {"p1": "required", "p2": "optional"}, SLOTS)
    assert [c.start for c in out] == ["2026-10-19T11:00"] and out[0].utility == 1.5


def test_relaxable_slot_names_its_blocker_and_ranks_after_free_ones():
    out = enumerate_slots({"p1": summ("p1", {"status": "unavailable", "relaxable": True}, {"status": "prefer_not", "weight": 0.5})},
                          {"p1": "required"}, SLOTS)
    assert [(c.start, c.blockers) for c in out] == [("2026-10-19T11:00", []), ("2026-10-19T10:00", ["p1"])]


def test_unknown_is_never_free():
    s = summ("p1", {"status": "available"}, {"status": "available"})
    s.unknown = [Window(start="2026-10-19T10:30", end="2026-10-19T11:30")]
    assert enumerate_slots({"p1": s}, {"p1": "required"}, SLOTS) == []
