"""Times and the slot grid. Every time is a naive local Asia/Singapore time written
'YYYY-MM-DDTHH:MM', and every slot sits on a 30-minute grid, on the weekdays the request allows."""
from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from pydantic import Field

SLOT_MINUTES = 30
FMT = "%Y-%m-%dT%H:%M"

# The three string shapes the contracts accept; anything else (seconds, a timezone) is rejected.
Moment = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$", description="YYYY-MM-DDTHH:MM")]
Day = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")]
Clock = Annotated[str, Field(pattern=r"^\d{2}:\d{2}$", description="HH:MM")]

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def parse(text: str) -> datetime:
    return datetime.strptime(text, FMT)


def fmt(moment: datetime) -> str:
    return moment.strftime(FMT)


def at(day: str, hhmm: str) -> str:
    """'2026-10-19', '10:00' -> '2026-10-19T10:00'."""
    return f"{day}T{hhmm}"


def weekday(day: str) -> str:
    """'2026-10-24' -> 'sat'."""
    return WEEKDAYS[date.fromisoformat(day).weekday()]


def day_list(weekdays: list[str]) -> str:
    """['sat', 'sun'] -> 'Sat, Sun'."""
    return ", ".join(d.capitalize() for d in weekdays)


def horizon_days(start_date: str, end_date: str, weekdays: list[str] | None = None) -> list[str]:
    """Dates from start_date to end_date, inclusive; only the given weekdays if any are named."""
    day, last = date.fromisoformat(start_date), date.fromisoformat(end_date)
    days = []
    while day <= last:
        if weekdays is None or WEEKDAYS[day.weekday()] in weekdays:
            days.append(day.isoformat())
        day += timedelta(days=1)
    return days


def overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    """Two half-open windows [start, end) share at least one minute."""
    return parse(a_start) < parse(b_end) and parse(b_start) < parse(a_end)


def candidate_slots(start_date: str, end_date: str, duration_min: int, day_start: str = "09:00",
                    day_end: str = "18:00", weekdays: list[str] = WEEKDAYS[:5]) -> list[tuple[str, str]]:
    """Every (start, end) on the grid that fits between day_start and day_end on an allowed weekday."""
    slots = []
    for day in horizon_days(start_date, end_date, weekdays):
        moment, close = parse(at(day, day_start)), parse(at(day, day_end))
        while moment + timedelta(minutes=duration_min) <= close:
            slots.append((fmt(moment), fmt(moment + timedelta(minutes=duration_min))))
            moment += timedelta(minutes=SLOT_MINUTES)
    return slots
