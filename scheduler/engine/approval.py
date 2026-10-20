"""The approval gate, the write and its verification: code, never a prompt.

commit() runs only after the organiser approved. It rechecks the slot against what is on the
calendars now, refuses relaxable time nobody consented to, sends the invite with an
idempotency key, reads the calendars back, and only then reports "sent". RSVPs and clashes
that arrive after the invite are reported back so the coordinator agent can replan."""
from scheduler.contracts.scenario import Scenario
from scheduler.sandbox import world
from scheduler.timegrid import overlaps


def recheck(scenario: Scenario, start: str, end: str) -> tuple[list[str], list[str]]:
    """(participants the slot is no longer free for, participants whose time lacks consent)."""
    stale, unconsented = [], []
    for a in scenario.request.attendees:
        if a.role != "required":
            continue
        ok = {ref for ref, slot in world.CONSENTS[a.id] if slot in (None, start)}
        for e in world.busy_events(a.id, start, end):
            if not e["movable"]:
                stale.append(a.id)
            elif e["id"] not in ok:
                unconsented.append(a.id)
        for leave in scenario.participant(a.id).leave:
            if leave.start_date <= start[:10] <= leave.end_date:
                if not leave.reachable_if_urgent:
                    stale.append(a.id)
                elif leave.id not in ok:
                    unconsented.append(a.id)
    return sorted(set(stale)), sorted(set(unconsented))


def commit(scenario: Scenario, start: str, end: str, approval_id: str, agents: dict) -> dict:
    """Recheck, write, verify; then apply what happens after the invite."""
    r = scenario.request
    world.fire("after_approval")
    stale, unconsented = recheck(scenario, start, end)
    world.guard("recheck", "tool call", f"calendars at {start}", not stale, f"no longer free for {stale}" if stale else "")
    world.guard("consent", "tool call", f"consents at {start}", not unconsented,
                f"no consent from {unconsented}" if unconsented else "")
    if stale or unconsented:
        for pid in stale:
            agents[pid].decline(start, end)          # the personal agent now sees the clash
        return {"status": "refused", "stale": stale, "unconsented": unconsented}
    world.send_invite(r.id, start, end, approval_id, key=f"{r.id}-{approval_id}")
    landed = world.read_back(r.id, "gate")
    if not world.guard("read-back", "output", f"invite on {len(landed)} calendars",
                       all(landed[a.id] == (start, end) for a in r.attendees)):
        return {"status": "unverified", "landed": landed}
    happened = world.fire("after_invite")
    declined = {"required": [], "optional": []}
    for event in happened:
        pid = event["participant_id"]
        if event["type"] == "rsvp" and event["response"] == "decline":
            declined[scenario.role(pid)].append(pid)
            if scenario.role(pid) == "required":
                agents[pid].decline(start, end)
        elif event["type"] == "new_meeting" and overlaps(event["meeting"]["start"], event["meeting"]["end"], start, end):
            world.log("alert_participant", f"personal:{pid}", about="clash with the agreed meeting")
    return {"status": "sent", "declined_required": declined["required"], "declined_optional": declined["optional"]}
