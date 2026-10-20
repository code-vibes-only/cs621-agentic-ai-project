"""Baselines the agent must beat.

(a) free/busy finder: what calendar tools do today, if everyone shared every calendar with it.
The earliest slot where every required participant's calendars are free and nobody is away.
Every event counts as busy, movable or not; it reads no messages or preferences, looks
nothing up and never asks anyone."""
from scheduler.contracts.result import Outcome
from scheduler.contracts.scenario import Scenario
from scheduler.sandbox import world
from scheduler.timegrid import overlaps


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
