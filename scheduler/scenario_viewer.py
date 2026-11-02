"""Render a scenario JSON as a readable, labeled briefing."""
import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from scheduler.contracts.constraints import DailyRule
from scheduler.contracts.scenario import Scenario, load_scenario


_WEEKDAYS = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


def _show(value: str | None) -> str:
    return value if value else "none"


def _date_time(value: str) -> tuple[str, str]:
    date, _, time = value.partition("T")
    return date, time


def _participant_names(scenario: Scenario) -> dict[str, str]:
    return {p.id: p.name for p in scenario.participants}


def _reference_labels(scenario: Scenario) -> dict[str, str]:
    labels = {}
    for participant in scenario.participants:
        for calendar in participant.calendars:
            labels.update({event.id: event.title for event in calendar.events})
        labels.update({leave.id: leave.reason for leave in participant.leave})
        labels.update({message.id: message.text for message in participant.messages})
        labels.update({preference.id: preference.text for preference in participant.preferences})
        labels.update({note.id: note.text for note in participant.memory})
    return labels


def _format_list(lines: list[str], label: str, values: list[str], names: dict[str, str]) -> None:
    rendered = [f"{names.get(value, value)} ({value})" for value in values]
    lines.append(f"  {label}: {', '.join(rendered) if rendered else 'none'}")


def format_scenario(scenario: Scenario) -> str:
    """Return a human-readable view without dropping scenario or grading details."""
    names = _participant_names(scenario)
    references = _reference_labels(scenario)
    request = scenario.request
    lines = [
        f"SCENARIO {scenario.id}  [{scenario.split.upper()}]",
        f"Tags: {', '.join(scenario.tags) or 'none'}",
        f"Seed: {scenario.seed} | Generator: {scenario.generator_version} | Today: {scenario.today}",
        f"Notes: {_show(scenario.notes)}",
        "",
        "REQUEST",
        f"  {request.text}",
        f"  Window: {request.start_date} to {request.end_date}",
        f"  Candidate days: {', '.join(_WEEKDAYS.get(day, day) for day in request.days)}",
        f"  Meeting: {request.duration_min} minutes, {request.day_start}-{request.day_end}",
        f"  Organiser: {names.get(request.organiser_id, request.organiser_id)} ({request.organiser_id})",
        "  Attendees:",
    ]
    for attendee in request.attendees:
        lines.append(
            f"    - {names.get(attendee.id, attendee.id)} ({attendee.id}): {attendee.role}"
        )

    lines.extend(["", "PARTICIPANTS"])
    for participant in scenario.participants:
        role = next(
            (a.role for a in request.attendees if a.id == participant.id),
            "not attending",
        )
        organiser = ", organiser" if participant.id == request.organiser_id else ""
        lines.append(
            f"  {participant.name} ({participant.id}) - {role}{organiser}; "
            f"usual hours {participant.hours_start}-{participant.hours_end}"
        )
        if participant.calendars:
            for calendar in participant.calendars:
                lines.append(f"    Calendar: {calendar.name}")
                if not calendar.events:
                    lines.append("      (empty)")
                for event in sorted(calendar.events, key=lambda e: (e.start, e.end, e.id)):
                    date, start = _date_time(event.start)
                    _, end = _date_time(event.end)
                    detail = []
                    if event.movable:
                        detail.append("movable")
                    if event.priority != "normal":
                        detail.append(f"{event.priority} priority")
                    suffix = f" [{', '.join(detail)}]" if detail else ""
                    lines.append(f"      {date} {start}-{end}  {event.title}{suffix}")
        else:
            lines.append("    Calendars: none")

        if participant.leave:
            lines.append("    Time away:")
            for leave in participant.leave:
                reachability = "reachable if urgent" if leave.reachable_if_urgent else "not relaxable"
                lines.append(
                    f"      {leave.start_date} to {leave.end_date}: {leave.reason} "
                    f"({reachability})"
                )
        if participant.messages:
            lines.append("    Messages:")
            for message in participant.messages:
                lines.append(
                    f"      {message.received} from {message.sender}: {message.text}"
                )
        if participant.preferences:
            lines.append("    Request preferences:")
            for preference in participant.preferences:
                lines.append(f"      {preference.text}")
        if participant.memory:
            lines.append("    Memory:")
            for note in participant.memory:
                expiry = f", expires {note.expires}" if note.expires else ""
                lines.append(
                    f"      {note.text} [source={note.source}, stated={note.stated_on}, "
                    f"scope={note.scope}{expiry}]"
                )
        if participant.pre_consent:
            lines.append("    Pre-given consent:")
            for consent in participant.pre_consent:
                lines.append(f"      {consent.text} [covers: {', '.join(consent.refs)}]")

    lines.extend(["", "CORPUS", f"  Documents available: {', '.join(scenario.corpus) or 'none'}"])

    lines.extend(["", "SCRIPTED BEHAVIOUR"])
    if scenario.scripted.replies:
        lines.append("  Participant replies:")
        for reply in scenario.scripted.replies:
            consent = "yes" if reply.consent else "no"
            slot = f", only for slot {reply.slot}" if reply.slot else ""
            lines.append(
                f"    {names.get(reply.participant_id, reply.participant_id)} "
                f"about {reply.about}: {reply.answer} (consent={consent}{slot})"
            )
    else:
        lines.append("  Participant replies: none")
    lines.append(
        f"  Organiser approval: {scenario.scripted.approval.decision}"
        + (f" - {scenario.scripted.approval.note}" if scenario.scripted.approval.note else "")
    )
    if scenario.scripted.events:
        lines.append("  Events during the episode:")
        for event in scenario.scripted.events:
            who = names.get(event.participant_id, event.participant_id)
            detail = event.type
            if event.meeting:
                detail += f": {event.meeting.title} ({event.meeting.start}-{event.meeting.end})"
            if event.response:
                detail += f": {event.response}"
            if event.text:
                detail += f": {event.text}"
            lines.append(f"    {event.at}, {who}: {detail}")
    else:
        lines.append("  Events during the episode: none")

    truth = scenario.ground_truth
    lines.extend(
        [
            "",
            "GROUND TRUTH (the answer key)",
            f"  Expected outcome: {truth.outcome}",
            f"  Expected slot: {_show(truth.expected_slot)}",
            f"  Slot rule: {truth.final_slot_rule}",
            "  Rule meanings: hard = blocks; movable = requires consent; soft = allowed with a score penalty.",
        ]
    )
    if truth.rules:
        lines.append("  Constraint rules:")
        for item in truth.rules:
            rule = item.rule
            who = names.get(item.participant_id, item.participant_id)
            if isinstance(rule, DailyRule):
                days = ", ".join(_WEEKDAYS.get(day, day) for day in rule.weekdays)
                when = f"{days} {rule.start_time}-{rule.end_time}"
            else:
                when = f"{rule.date} {rule.start_time}-{rule.end_time}"
            weight = f", weight {rule.weight:g}" if rule.kind == "soft" else ""
            label = references.get(rule.ref) if rule.ref else None
            reference = f", from {rule.ref} ({label})" if rule.ref and label else (
                f", ref {rule.ref}" if rule.ref else ""
            )
            lines.append(f"    - {who}: {rule.kind} {when}{weight}{reference}")
    else:
        lines.append("  Constraint rules: none")

    _format_list(lines, "Must ask privately", truth.must_ask, names)
    _format_list(lines, "Must clarify", truth.must_clarify, names)
    _format_list(lines, "Must read messages", truth.must_read, names)
    _format_list(lines, "Must look up", truth.must_lookup, names)
    _format_list(lines, "Must alert", truth.must_alert, names)
    lines.append(f"  Private canaries (must not leak): {', '.join(truth.canaries) or 'none'}")
    if truth.attack:
        payload_label = references.get(truth.attack.payload)
        payload = truth.attack.payload
        if payload_label:
            payload += f" ({payload_label})"
        lines.extend(
            [
                "  Attack test:",
                f"    Kind: {truth.attack.kind}",
                f"    Payload location: {payload}",
                f"    Must not happen: {', '.join(truth.attack.must_not)}",
                f"    Severity weight: {truth.attack.weight:g}",
            ]
        )
    else:
        lines.append("  Attack test: none")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scheduler.scenario_viewer",
        description="Show a scenario JSON as a readable scheduling brief.",
    )
    parser.add_argument("scenario", type=Path, help="path to a scenario JSON file")
    args = parser.parse_args(argv)
    try:
        scenario = load_scenario(args.scenario)
    except (OSError, ValueError, ValidationError) as exc:
        parser.error(f"cannot read a valid scenario from {args.scenario}: {exc}")
    print(format_scenario(scenario))


if __name__ == "__main__":
    main()
