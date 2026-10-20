"""Constraints: a commitment or preference turned into a checkable rule over slots.

hard     never usable (time away, a fixed commitment, outside the participant's usual hours)
movable  blocks the slot unless the participant consents (a movable commitment such as a focus
         block or a flexible gym session, time away marked reachable if urgent)
soft     usable, at a penalty of `weight` (a preference such as "no meetings before 10")

The model only ever emits Rules; code expands them into windows over the planning horizon,
so the model never does date arithmetic."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

from scheduler.timegrid import Clock, Day, Moment, Weekday, at, horizon_days, overlaps, weekday

Kind = Literal["hard", "movable", "soft"]


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    participant_id: str
    start: Moment
    end: Moment
    kind: Kind
    weight: float = 0.0
    ref: str | None = None          # the commitment or preference it came from (private)


class WindowRule(BaseModel):
    """One window on one date, e.g. a meeting, a booking or a conference day."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["window"] = "window"
    date: Day
    start_time: Clock
    end_time: Clock
    kind: Kind
    weight: float = 0.0
    ref: str | None = None


class DailyRule(BaseModel):
    """The same window on chosen weekdays, e.g. "no meetings before 10" every day, or "Sunday mornings are out"."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["daily"] = "daily"
    weekdays: list[Weekday]
    start_time: Clock
    end_time: Clock
    kind: Kind
    weight: float = 0.0
    ref: str | None = None


Rule = WindowRule | DailyRule


def expand(participant_id: str, rules: list[Rule], start_date: str, end_date: str) -> list[Constraint]:
    """Turn rules into dated windows inside the planning horizon (every date, weekends included)."""
    days = horizon_days(start_date, end_date)
    out = []
    for rule in rules:
        if isinstance(rule, WindowRule):
            dates = [rule.date] if rule.date in days else []
        else:
            dates = [d for d in days if weekday(d) in rule.weekdays]
        for d in dates:
            out.append(Constraint(participant_id=participant_id, start=at(d, rule.start_time),
                                  end=at(d, rule.end_time), kind=rule.kind,
                                  weight=rule.weight if rule.kind == "soft" else 0.0, ref=rule.ref))
    return out


def outside_hours(participant_id: str, start_date: str, end_date: str,
                  hours_start: str, hours_end: str) -> list[Constraint]:
    """Usual hours as hard windows: before the start and after the end of each day."""
    out = []
    for d in horizon_days(start_date, end_date):
        out.append(Constraint(participant_id=participant_id, start=at(d, "00:00"),
                              end=at(d, hours_start), kind="hard", ref="usual-hours"))
        out.append(Constraint(participant_id=participant_id, start=at(d, hours_end),
                              end=at(d, "23:59"), kind="hard", ref="usual-hours"))
    return out


def slot_status(constraints: list[Constraint], start: str, end: str,
                consented: set[str] = frozenset()) -> tuple[str, float, bool]:
    """(status, weight, relaxable) of one slot for one participant.

    Any hard overlap makes it unavailable. A movable overlap makes it unavailable but
    relaxable, unless the participant consented to that commitment (its ref). Otherwise a
    soft overlap makes it prefer_not, at the largest overlapping weight."""
    hits = [c for c in constraints if overlaps(c.start, c.end, start, end)]
    if any(c.kind == "hard" for c in hits):
        return "unavailable", 0.0, False
    if any(c.kind == "movable" and c.ref not in consented for c in hits):
        return "unavailable", 0.0, True
    soft = [c.weight for c in hits if c.kind == "soft"]
    return ("prefer_not", max(soft), False) if soft else ("available", 0.0, False)
