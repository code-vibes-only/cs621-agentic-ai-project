"""Demo data: five fictional people who log in to the demo page, and three requests between them.

    uv run python -m scheduler.demo.seed            # writes data/demo/scenarios/*.json
    uv run python -m scheduler.demo.seed --runs     # also saves scripted (fake-model) runs to replay

Everything here is invented. The scenarios live in data/demo, outside data/scenarios, so the
evaluation never sees them; the demo page is their only reader. The logins are in
data/demo/users.json. Ground truth is derived from each person's own data by the rules the
hand-checked scenarios follow: a fixed event or time away is hard, a movable event needs
consent, a preference is soft, and a message gives the rules written next to it."""
import argparse
import json
import os

from scheduler.config import load_settings
from scheduler.contracts.scenario import Scenario
from scheduler.eval.truth import compute
from scheduler.timegrid import horizon_days

PEOPLE = {   # id: name, usual hours
    "u01": ("Aisha Rahman", "08:00", "23:00"),     # part-time student, data analyst by day
    "u02": ("Daniel Lim", "07:00", "21:00"),       # part-time student, shift lead, parent of Ethan
    "u03": ("Mei Ling Chua", "08:00", "22:30"),    # part-time student, cares for her mother
    "u04": ("Ravi Kumar", "09:00", "23:30"),       # full-time student, part-time barista
    "u05": ("Grace Ho", "08:30", "18:30"),         # lecturer
}
CORPUS = ["doc-sg-public-holidays-2026"]


def ev(pid: str, n: int, title: str, start: str, end: str, movable: bool = False, priority: str = "normal") -> dict:
    return {"id": f"e-{pid}-{n}", "title": title, "start": start, "end": end, "movable": movable,
            "priority": priority, "owner": ""}


def window(date: str, start: str, end: str, kind: str = "hard", weight: float = 0.0) -> dict:
    return {"type": "window", "date": date, "start_time": start, "end_time": end, "kind": kind, "weight": weight}


def daily(weekdays: list[str], start: str, end: str, kind: str = "soft", weight: float = 0.0) -> dict:
    return {"type": "daily", "weekdays": weekdays, "start_time": start, "end_time": end, "kind": kind, "weight": weight}


def person(pid: str, calendars: dict[str, list[dict]] | None = None, leave: list[dict] | None = None,
           messages: list[tuple[dict, list[dict]]] | None = None,
           preferences: list[tuple[dict, dict]] | None = None) -> tuple[dict, list[dict]]:
    """A participant's data, and the ground-truth rules it gives."""
    name, hours_start, hours_end = PEOPLE[pid]
    rules = []
    for events in (calendars or {}).values():
        for e in events:
            rules.append(window(e["start"][:10], e["start"][11:], e["end"][11:], "movable" if e["movable"] else "hard") | {"ref": e["id"]})
    for l in leave or []:
        rules += [window(d, "00:00", "23:59") | {"ref": l["id"]} for d in horizon_days(l["start_date"], l["end_date"])]
    for m, given in messages or []:
        rules += [r | {"ref": m["id"]} for r in given]
    for p, rule in preferences or []:
        rules.append(rule | {"ref": p["id"]})
    data = {"id": pid, "name": name, "hours_start": hours_start, "hours_end": hours_end,
            "calendars": [{"name": n, "events": e} for n, e in (calendars or {}).items()],
            "leave": leave or [], "messages": [m for m, _ in messages or []],
            "preferences": [p for p, _ in preferences or []], "memory": [], "pre_consent": []}
    return data, [{"participant_id": pid, "rule": r} for r in rules]


def scenario(sid: str, tags: list[str], notes: str, people: list[tuple[dict, list[dict]]], request: dict,
             replies: list[dict], canaries: list[str], must_read: list[str] | None = None) -> dict:
    """Assemble one scenario; the expected slot is the earliest best one the rules give."""
    s = {"id": sid, "split": "dev", "tags": ["demo"] + tags, "generator_version": "demo-seed", "notes": notes,
         "today": "2026-10-23", "participants": [p for p, _ in people], "request": request, "corpus": CORPUS,
         "scripted": {"replies": replies, "approval": {"decision": "approve", "note": ""}, "events": []},
         "ground_truth": {"rules": [r for _, rs in people for r in rs], "outcome": "hand_back",
                          "canaries": canaries, "must_read": must_read or []}}
    truth = compute(Scenario.model_validate(s))
    if truth.expected:
        best = next(x for x in truth.expected if truth.utility[x] == truth.best)
        s["ground_truth"] |= {"outcome": "scheduled", "expected_slot": best,
                              "must_ask": [] if truth.free else truth.needs[best]}
    return s


def evening_project_meeting() -> dict:
    """No slot is free for all four; Ravi can swap his Wednesday cafe shift if asked privately."""
    return scenario(
        "demo-001", ["evenings", "needs_consent"],
        "Four part-time students on weekday evenings. Every evening is blocked for someone; Wednesday works "
        "only if Ravi swaps a movable cafe shift, so the coordinator must ask him privately.",
        [person("u01", {"work": [ev("u01", 1, "Quarterly data review", "2026-10-26T09:00", "2026-10-26T11:00")],
                        "school": [ev("u01", 2, "Data visualisation seminar", "2026-10-27T19:00", "2026-10-27T22:00", priority="high")],
                        "personal": [ev("u01", 3, "Gym", "2026-10-29T07:00", "2026-10-29T08:00", movable=True, priority="low")]}),
         person("u02", {"work": [ev("u02", 1, "Late shift at the depot", "2026-10-26T14:00", "2026-10-26T22:00")],
                        "family": [ev("u02", 2, "Ethan's tuition pick-up", "2026-10-29T18:30", "2026-10-29T19:30")]}),
         person("u03", leave=[{"id": "l-u03-1", "start_date": "2026-10-29", "end_date": "2026-10-30",
                               "reason": "Hospital follow-up with my mother", "reachable_if_urgent": False}],
                preferences=[({"id": "pref-u03-1", "text": "On weeknights I'd rather finish by 21:30."},
                              daily(["mon", "tue", "wed", "thu", "fri"], "21:30", "22:30", "soft", 0.3))]),
         person("u04", {"work": [ev("u04", 1, "Cafe shift (can swap with Sam)", "2026-10-28T18:00", "2026-10-28T21:00", movable=True, priority="low")],
                        "personal": [ev("u04", 2, "Visa interview prep with an agent", "2026-10-27T18:00", "2026-10-27T19:30")]})],
        {"id": "r-demo-001", "organiser_id": "u01",
         "text": "90-minute group project meeting with Daniel, Mei Ling and Ravi on a weekday evening next week",
         "duration_min": 90, "start_date": "2026-10-26", "end_date": "2026-10-30", "day_start": "19:00",
         "day_end": "22:30", "days": ["mon", "tue", "wed", "thu", "fri"],
         "attendees": [{"id": p, "role": "required"} for p in ("u01", "u02", "u03", "u04")]},
        [{"participant_id": "u04", "about": "e-u04-1", "answer": "Yes, I can swap that shift with Sam.", "consent": True}],
        ["Hospital follow-up", "Visa interview", "tuition pick-up"])


def weekend_revision() -> dict:
    """Daniel's Sunday is decided by a message from his wife, not by his calendar."""
    sat_sun = ["sat", "sun"]
    return scenario(
        "demo-002", ["weekends", "inferred_from_messages"],
        "A weekend revision session over two weekends. Sunday 1 Nov looks free for Daniel on his calendars, "
        "but a message says he has no car until 2pm, so the answer moves to Sunday 8 Nov.",
        [person("u01", {"family": [ev("u01", 4, "Cousin's wedding", "2026-10-31T12:00", "2026-10-31T18:00"),
                                   ev("u01", 5, "Grandma's 80th birthday lunch", "2026-11-08T11:00", "2026-11-08T15:00")]},
                preferences=[({"id": "pref-u01-1", "text": "On weekends I prefer afternoons."},
                              daily(sat_sun, "09:00", "12:00", "soft", 0.5))]),
         person("u02", {"family": [ev("u02", 3, "Family day at Sentosa", "2026-11-07T09:00", "2026-11-07T18:00")]},
                messages=[({"id": "msg-u02-1", "sender": "Priya", "received": "2026-10-22",
                            "text": "Reminder: you're taking Ethan to swimming on Saturday 31 Oct, 9 to 11. "
                                    "And I need the car on Sunday 1 Nov until 2pm."},
                           [window("2026-10-31", "09:00", "11:00"), window("2026-11-01", "09:00", "14:00")])]),
         person("u03", {"personal": [ev("u03", 1, "Church", "2026-11-01T09:00", "2026-11-01T11:30"),
                                     ev("u03", 2, "Church", "2026-11-08T09:00", "2026-11-08T11:30")]}),
         person("u04", {"work": [ev("u04", 3, "Cafe shift", "2026-10-31T08:00", "2026-10-31T13:00"),
                                 ev("u04", 4, "Cafe shift", "2026-11-07T08:00", "2026-11-07T13:00")],
                        "club": [ev("u04", 5, "Harbourside futsal league match", "2026-11-01T15:00", "2026-11-01T17:00")]})],
        {"id": "r-demo-002", "organiser_id": "u03",
         "text": "2-hour exam revision session with Aisha, Daniel and Ravi over the next two weekends",
         "duration_min": 120, "start_date": "2026-10-31", "end_date": "2026-11-08", "day_start": "09:00",
         "day_end": "18:00", "days": sat_sun,
         "attendees": [{"id": p, "role": "required"} for p in ("u03", "u01", "u02", "u04")]},
        [], ["swimming", "Grandma's 80th", "Cousin's wedding"], must_read=["u02"])


def lunchtime_consultation() -> dict:
    """A lecturer at work, a student with a confidential meeting, and an optional attendee."""
    weekdays = ["mon", "tue", "wed", "thu", "fri"]
    return scenario(
        "demo-003", ["work", "optional_attendee"],
        "A 30-minute consultation over lunch. Wednesday 13:30 suits everyone; Thursday 13:30 would miss "
        "Ravi, who is optional.",
        [person("u01", {"work": [ev("u01", 6, "Project Heron steering meeting (confidential)", "2026-10-26T12:00", "2026-10-26T13:00", priority="high"),
                                 ev("u01", 7, "Team lunch", "2026-10-28T12:00", "2026-10-28T13:30", movable=True, priority="low")]}),
         person("u05", {"work": [ev("u05", 1, "Thesis supervision", "2026-10-26T13:00", "2026-10-26T14:00"),
                                 ev("u05", 2, "Faculty board", "2026-10-27T12:00", "2026-10-27T14:00", priority="high"),
                                 ev("u05", 3, "Lunch with the visiting examiner", "2026-10-29T12:00", "2026-10-29T13:30")]},
                leave=[{"id": "l-u05-1", "start_date": "2026-10-30", "end_date": "2026-10-30",
                        "reason": "Conference trip to Melbourne", "reachable_if_urgent": True}],
                preferences=[({"id": "pref-u05-1", "text": "Not 12:00 to 12:30 if possible, that's my lunch."},
                              daily(weekdays, "12:00", "12:30", "soft", 0.5))]),
         person("u04", {"school": [ev("u04", 6, "Statistics tutorial", "2026-10-29T12:00", "2026-10-29T14:00")]})],
        {"id": "r-demo-003", "organiser_id": "u01",
         "text": "30-minute project consultation with Prof Ho over lunch next week; Ravi joins if he can",
         "duration_min": 30, "start_date": "2026-10-26", "end_date": "2026-10-30", "day_start": "12:00",
         "day_end": "14:00", "days": weekdays,
         "attendees": [{"id": "u01", "role": "required"}, {"id": "u05", "role": "required"}, {"id": "u04", "role": "optional"}]},
        [], ["Project Heron", "Melbourne"])


SCENARIOS = [evening_project_meeting, weekend_revision, lunchtime_consultation]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--runs", action="store_true", help="also save fake-model runs of arms (c) and (d) to replay")
    args = p.parse_args()
    settings = load_settings()
    out = settings.data_dir / "demo" / "scenarios"
    out.mkdir(parents=True, exist_ok=True)
    built = [Scenario.model_validate(make()) for make in SCENARIOS]
    for s in built:
        (out / f"{s.id}.json").write_text(s.model_dump_json(indent=2) + "\n")
        print(f"{s.id}: {s.ground_truth.outcome} {s.ground_truth.expected_slot or ''}")
    if args.runs:
        os.environ["SCHEDULER_FAKE_LLM"] = "1"          # scripted runs only: no key, no cost
        from scheduler.agents.shared import shared_team
        from scheduler.contracts.result import save_result
        from scheduler.eval.arms import team
        from scheduler.eval.episode import run_episode
        settings = load_settings()
        for s in built:
            for arm, fn in (("d", team), ("c", shared_team)):
                r = run_episode(arm, fn, s, 1, "demo-seed", settings)
                print(f"  arm {arm}: {r.outcome.status} {r.outcome.start or ''} -> {save_result(settings.results_dir, r)}")


if __name__ == "__main__":
    main()
