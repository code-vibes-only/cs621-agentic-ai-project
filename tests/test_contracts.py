import pytest
from pydantic import ValidationError

from scheduler.contracts.availability import AvailabilitySummary
from scheduler.contracts.constraints import Constraint, DailyRule, expand, slot_status
from scheduler.timegrid import candidate_slots


def summary(**slot):
    return {"participant_id": "p01", "request_id": "r-1", "slots": [{"start": "2026-10-19T10:00", "end": "2026-10-19T11:00", **slot}]}


def test_summary_has_nowhere_to_put_a_reason():
    with pytest.raises(ValidationError):
        AvailabilitySummary.model_validate(summary(status="unavailable", reason="clinic"))
    with pytest.raises(ValidationError):
        AvailabilitySummary.model_validate({**summary(status="available"), "note": "on leave"})


def test_weight_and_relaxable_belong_to_one_status_each():
    with pytest.raises(ValidationError):
        AvailabilitySummary.model_validate(summary(status="available", weight=0.5))
    with pytest.raises(ValidationError):
        AvailabilitySummary.model_validate(summary(status="prefer_not", weight=0.5, relaxable=True))
    AvailabilitySummary.model_validate(summary(status="unavailable", relaxable=True))


def test_daily_rule_expands_to_its_own_weekdays():
    rule = DailyRule(weekdays=["mon", "fri", "sun"], start_time="09:00", end_time="10:00", kind="soft", weight=0.5)
    windows = expand("p01", [rule], "2026-10-19", "2026-10-25")       # Mon 19 to Sun 25
    assert [c.start for c in windows] == ["2026-10-19T09:00", "2026-10-23T09:00", "2026-10-25T09:00"]


def test_slots_fall_only_on_the_weekdays_the_request_allows():
    weekend = candidate_slots("2026-10-19", "2026-10-25", 60, "10:00", "12:00", ["sat", "sun"])
    assert [s for s, _ in weekend] == ["2026-10-24T10:00", "2026-10-24T10:30", "2026-10-24T11:00",
                                      "2026-10-25T10:00", "2026-10-25T10:30", "2026-10-25T11:00"]
    assert {s[:10] for s, _ in candidate_slots("2026-10-19", "2026-10-25", 60)} == {
        "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"}


def test_slot_status_hard_beats_movable_beats_soft():
    c = [Constraint(participant_id="p01", start="2026-10-19T10:00", end="2026-10-19T12:00", kind="movable", ref="e1"),
         Constraint(participant_id="p01", start="2026-10-19T09:00", end="2026-10-19T11:00", kind="soft", weight=0.5)]
    assert slot_status(c, "2026-10-19T10:00", "2026-10-19T11:00") == ("unavailable", 0.0, True)
    assert slot_status(c, "2026-10-19T10:00", "2026-10-19T11:00", {"e1"}) == ("prefer_not", 0.5, False)
    hard = c + [Constraint(participant_id="p01", start="2026-10-19T10:30", end="2026-10-19T11:00", kind="hard")]
    assert slot_status(hard, "2026-10-19T10:00", "2026-10-19T11:00", {"e1"}) == ("unavailable", 0.0, False)


def test_times_must_be_in_the_one_format():
    with pytest.raises(ValidationError):
        AvailabilitySummary.model_validate({**summary(status="available"), "unknown": [{"start": "2026-10-20T00:00:00", "end": "2026-10-20T23:59:00"}]})
    with pytest.raises(ValidationError):
        DailyRule(weekdays=["mon"], start_time="9am", end_time="10:00", kind="soft", weight=0.5)
