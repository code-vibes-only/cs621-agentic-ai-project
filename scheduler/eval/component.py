"""Component diagnostics that need no model: which layer a problem sits in, from saved result
files and a labelled message list. Nothing here changes a scenario, a result file, a guardrail
or a held-out number; everything it writes goes to results/component/.

Layer 3, the personal agent alone: each participant's first availability summary against the
answer key, slot by slot, with every disagreement sorted by cause. A saved result holds only the
ids a rule cited, not its times, so rules are compared by id and the rest by their effect on slots.
Layer 5, the filter and the checker: both against data/component/leak_labels.json.

    uv run python -m scheduler.eval.component
"""
import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from scheduler.agents import privacy
from scheduler.config import Settings, load_settings
from scheduler.contracts.constraints import Constraint
from scheduler.contracts.result import EpisodeResult, load_results
from scheduler.contracts.scenario import Scenario, load_split
from scheduler.eval.checker import leaks
from scheduler.eval.metrics import mean_sd
from scheduler.eval.truth import truth_constraints
from scheduler.sandbox import world
from scheduler.timegrid import overlaps

TAGS = ("dev7", "heldout-final")       # the real-model sweeps of our design with saved summaries
ARM = "d"                              # the only arm with one personal agent per participant
HOLIDAY_DOC = "doc-sg-public-holidays-2026"
LABEL_SCENARIO = "dev-001"             # the labelled messages are written about its participants
SOURCES = {"e": "calendar event", "l": "time away", "msg": "message", "pref": "what they said", "mem": "memory note",
           "doc": "external schedule", "usual": "usual hours"}


# ---------------------------------------------------------------- layer 3: summaries against the key
def key_status(windows: list[Constraint], start: str, end: str) -> tuple[str, bool, str | None]:
    """(status, relaxable, ref) the answer key gives one slot. The key's own arithmetic, like
    eval/truth.py: it does not call slot_status, so a bug there cannot hide here."""
    hits = [c for c in windows if overlaps(c.start, c.end, start, end)]
    hard = [c for c in hits if c.kind == "hard"]
    movable = [c for c in hits if c.kind == "movable"]
    soft = [c for c in hits if c.kind == "soft"]
    if hard:
        return "unavailable", False, hard[0].ref
    if movable:
        return "unavailable", True, movable[0].ref
    return ("prefer_not", False, soft[0].ref) if soft else ("available", False, None)


def source(ref: str | None) -> str:
    return SOURCES.get(re.split(r"[-_]", ref or "")[0], "other")


def cause(key: str, key_relaxable: bool, got: str, got_relaxable: bool, ref: str | None, holiday: bool) -> str | None:
    """Why a summary's slot differs from the key, or None if it does not. `holiday` means the
    slot is on a public holiday and the agent's rules cite the holiday list."""
    if key == got:
        if key == "unavailable" and key_relaxable != got_relaxable:
            return f"hard and movable swapped ({source(ref)})"
        return None
    if got == "unavailable":
        if holiday:
            return "public holiday the key leaves out"
        return f"preference read as a block ({source(ref)})" if key == "prefer_not" else "extra block, no key rule"
    if key == "unavailable":
        return f"block read as a preference ({source(ref)})" if got == "prefer_not" else f"missed block ({source(ref)})"
    return f"missed preference ({source(ref)})" if key == "prefer_not" else "extra preference, no key rule"


def public_holidays(data_dir: Path) -> set[str]:
    """The dates the corpus lists as public holidays, not the "no holiday between" dates."""
    doc = json.loads((data_dir / "corpus" / f"{HOLIDAY_DOC}.json").read_text(encoding="utf-8"))
    return set(re.findall(r"\d{4}-\d{2}-\d{2}(?= (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b)|(?<=Mon )\d{4}-\d{2}-\d{2}", doc["text"]))


def cited_refs(result: EpisodeResult, pid: str) -> set[str]:
    """The ids a personal agent's rules cited, from its "N rules (from a, b); ..." timeline note."""
    notes = [e.text for e in result.timeline if e.actor == f"personal:{pid}" and e.kind == "rules"]
    found = re.search(r"\(from (.*?)\);", notes[-1]) if notes else None
    refs = set(found.group(1).split(", ")) if found else set()
    return refs - {"nothing", "-"}


def free_busy_status(scenario: Scenario, pid: str, start: str, end: str) -> str:
    """The baseline: what the free/busy finder sees, the calendars, time away and usual hours."""
    p = scenario.participant(pid)
    busy = (start[11:] < p.hours_start or end[11:] > p.hours_end
            or any(l.start_date <= start[:10] <= l.end_date for l in p.leave)
            or any(overlaps(e.start, e.end, start, end) for c in p.calendars for e in c.events))
    return "unavailable" if busy else "available"


@dataclass
class Layer3:
    tag: str
    rows: list[dict]                   # one row per run, participant, status pair and cause
    per_run: dict[int, Counter]
    skipped_events: list[str]          # scenarios that change during the run: the key is the final world
    no_summary: int


def compare_episode(scenario: Scenario, result: EpisodeResult, holidays: set[str], counts: Counter) -> list[dict]:
    """Every first summary of one episode against the key: before any consent or decline."""
    windows = truth_constraints(scenario)
    key_refs = {}
    for t in scenario.ground_truth.rules:
        key_refs.setdefault(t.participant_id, set()).add(t.rule.ref)
    grouped, seen = Counter(), set()
    for summary in result.summaries:
        pid = summary.participant_id
        if pid in seen:
            continue
        seen.add(pid)
        cited = cited_refs(result, pid)
        wanted = {r for r in key_refs.get(pid, set()) if r}
        counts["refs_key"] += len(wanted)
        counts["refs_found"] += len(wanted & cited)
        counts["refs_extra_other"] += len(cited - wanted - {HOLIDAY_DOC})
        counts["people"] += 1
        for slot in summary.slots:
            key, relaxable, ref = key_status(windows[pid], slot.start, slot.end)
            holiday = slot.start[:10] in holidays and HOLIDAY_DOC in cited
            why = cause(key, relaxable, slot.status, slot.relaxable, ref, holiday)
            base = free_busy_status(scenario, pid, slot.start, slot.end)
            counts["slots"] += 1
            counts["agree"] += key == slot.status
            counts["base_agree"] += key == base
            blocked, says = key == "unavailable", slot.status == "unavailable"
            counts["key_blocked"] += blocked
            counts["found"] += blocked and says
            counts["base_found"] += blocked and base == "unavailable"
            counts["key_open"] += not blocked
            counts["extra"] += says and not blocked
            counts["extra_holiday"] += says and not blocked and why == "public holiday the key leaves out"
            counts["base_extra"] += base == "unavailable" and not blocked
            if why:
                grouped[(pid, key, slot.status, why)] += 1
    return [{"scenario": scenario.id, "run": result.run, "participant": pid, "key": key, "agent": got, "cause": why, "slots": n}
            for (pid, key, got, why), n in sorted(grouped.items())]


def layer3(settings: Settings, tag: str, scenarios: dict[str, Scenario]) -> Layer3:
    results = [r for r in load_results(settings.results_dir, tag) if r.arm == ARM and not r.fake_llm]
    episodes = Counter(r.run for r in results)
    runs = sorted(run for run, n in episodes.items() if n == max(episodes.values()))           # attack cases run extra times
    holidays = public_holidays(settings.data_dir)
    rows, per_run, skipped, no_summary = [], {run: Counter() for run in runs}, set(), 0
    for r in results:
        s = scenarios[r.scenario_id]
        if r.run not in per_run:
            continue
        if s.scripted.events:
            skipped.add(s.id)
        elif not r.summaries:
            no_summary += 1
        else:
            rows += compare_episode(s, r, holidays, per_run[r.run])
    return Layer3(tag, rows, per_run, sorted(skipped), no_summary)


def holiday_gaps(scenarios: dict[str, Scenario], holidays: set[str]) -> list[dict]:
    """Scenarios whose slots include a public holiday, and whether their key counts it."""
    out = []
    for s in scenarios.values():
        on_holiday = [start for start, _ in s.request.slots() if start[:10] in holidays]
        if on_holiday:
            counted = {t.participant_id for t in s.ground_truth.rules if t.rule.ref == HOLIDAY_DOC}
            out.append({"scenario": s.id, "days": sorted({x[:10] for x in on_holiday}), "slots": len(on_holiday),
                        "counted_for": len(counted), "attendees": len(s.request.attendees)})
    return sorted(out, key=lambda g: g["scenario"])


# ---------------------------------------------------------------- layer 5: filter and checker
def load_labels(data_dir: Path) -> list[dict]:
    return json.loads((data_dir / "component" / "leak_labels.json").read_text(encoding="utf-8"))


def layer5(settings: Settings, scenarios: dict[str, Scenario]) -> list[dict]:
    """Each labelled message through the filter and the checker. Both run on a scenario with
    real private details; the filter reads them from the sandbox."""
    s = scenarios[LABEL_SCENARIO]
    world.reset(s, settings.data_dir / "corpus")
    return [{"label": m["label"], "kind": m["kind"], "filter": bool(privacy.why_blocked(m["text"])),
             "checker": leaks([m["text"]], s) > 0, "text": m["text"]} for m in load_labels(settings.data_dir)]


def rates(rows: list[dict], who: str) -> tuple[int, int, int, int]:
    """(leaks caught, leaks, clean messages flagged, clean messages)."""
    leak, clean = [r for r in rows if r["label"] == "leak"], [r for r in rows if r["label"] == "clean"]
    return sum(r[who] for r in leak), len(leak), sum(r[who] for r in clean), len(clean)


# ---------------------------------------------------------------- the report
def values(result: Layer3, top: str, bottom: str, minus: str | None = None) -> list[float]:
    return [(c[top] - (c[minus] if minus else 0)) / c[bottom] for c in result.per_run.values() if c[bottom]]


def layer3_section(r: Layer3) -> list[str]:
    runs = len(r.per_run)
    total = sum(c["slots"] for c in r.per_run.values())
    causes, cases = Counter(), {}
    for row in r.rows:
        causes[row["cause"]] += row["slots"]
        cases.setdefault(row["cause"], set()).add(row["scenario"])
    per = lambda top, bottom, minus=None: mean_sd(values(r, top, bottom, minus), 3)
    lines = [f"### `{r.tag}`, arm ({ARM}), {runs} runs, {total} slots", "",
             f"Left out because the world changes during the run: {', '.join(r.skipped_events) or 'none'}. "
             f"Episodes with no summary: {r.no_summary}.", "",
             "| Per run, mean ± sample SD | Personal agents | Free/busy baseline |", "|---|---|---|",
             f"| Slots whose status matches the key | {per('agree', 'slots')} | {per('base_agree', 'slots')} |",
             f"| Key's blocked slots reported as blocked | {per('found', 'key_blocked')} | {per('base_found', 'key_blocked')} |",
             f"| Key's open slots reported as blocked | {per('extra', 'key_open')} | {per('base_extra', 'key_open')} |",
             f"| The same, leaving out the public holiday | {per('extra', 'key_open', 'extra_holiday')} | n/a |",
             f"| Key's rule ids cited by the agent | {per('refs_found', 'refs_key')} | n/a |",
             f"| Other ids cited, per person (not the holiday list) | {per('refs_extra_other', 'people')} | n/a |", "",
             "| Cause | Slots | Scenarios |", "|---|---|---|"]
    lines += [f"| {why} | {n} | {', '.join(sorted(cases[why]))} |" for why, n in causes.most_common()]
    return lines + [""]


def report(layers: list[Layer3], gaps: list[dict], messages: list[dict]) -> str:
    lines = ["# Component diagnostics (issue #21)", "",
             "Layers 3 and 5 of the test pyramid. No model calls, no cost. A second look at saved runs: the held-out "
             "numbers in `docs/results.md` are unchanged and these numbers are not merged into them.", "",
             "Regenerate with `uv run python -m scheduler.eval.component`.", "",
             "## Layer 3: the personal agent's first summary against the answer key", ""]
    for r in layers:
        lines += layer3_section(r)
    lines += ["Limits:", "",
              "- A saved result holds rule ids, not times, so a cited id does not show its times were right. Grading each "
              "rule's times and weight needs new `parse()` calls.",
              "- A cause names the first matching key rule when several cover a slot.",
              "- The free/busy baseline has no preferences and no consent, so it cannot show `prefer_not`.", "",
              "### Public holidays in the answer key", "",
              "The personal agent's prompt says public holidays apply to everyone. The key counts them in some scenarios only:",
              "", "| Scenario | Holiday in the window | Slots on it | Attendees whose key counts it |", "|---|---|---|---|"]
    lines += [f"| {g['scenario']} | {', '.join(g['days'])} | {g['slots']} | {g['counted_for']} of {g['attendees']} |" for g in gaps]
    lines += ["", "This is a question about the key, not a change to it: the held-out set stays frozen.", "",
              "## Layer 5: the privacy filter and the checker against labelled messages", "",
              f"{len(messages)} hand-written messages about `{LABEL_SCENARIO}`'s participants. The list was written to probe "
              "the filter, so these counts describe this list and are not a rate on real traffic. The code is "
              "deterministic, so repeat runs give the same counts.", "",
              "| Kind | Label | Messages | Filter flags | Checker flags | Passes both |", "|---|---|---|---|---|---|"]
    kinds = {}
    for m in messages:
        kinds.setdefault((m["label"], m["kind"]), []).append(m)
    for (label, kind), rows in kinds.items():
        lines.append(f"| {kind} | {label} | {len(rows)} | {sum(m['filter'] for m in rows)} | {sum(m['checker'] for m in rows)} | "
                     f"{sum(not m['filter'] and not m['checker'] for m in rows)} |")
    lines += ["", "| | Leaks caught (recall) | Clean messages flagged |", "|---|---|---|"]
    for who, name in (("filter", "Privacy filter"), ("checker", "Checker")):
        caught, leak, flagged, clean = rates(messages, who)
        lines.append(f"| {name} | {caught} of {leak} ({caught / leak:.2f}) | {flagged} of {clean} |")
    missed = [m for m in messages if m["label"] == "leak" and not m["filter"] and not m["checker"]]
    lines += ["", f"{len(missed)} leaks pass both. A leak that passes the filter and the checker is recorded as \"no leak\", "
              "so the sweep's zero leaks means none that these two checks recognise. It does not show how often such "
              "wording occurs: nobody has labelled the saved thread messages.", "",
              "\"Says who cannot come\" is labelled a leak because the brief says the thread never says whose time was "
              "given up, and the coordinator's prompt forbids it. The filter was not built to catch it, so the team may "
              "prefer to read it as a prompt rule. Each message and verdict is in `layer5.csv`.", ""]
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(settings: Settings) -> tuple[list[Layer3], list[dict], str]:
    scenarios = {s.id: s for split in ("dev", "heldout") for s in load_split(settings.data_dir, split)}
    layers = [layer3(settings, tag, scenarios) for tag in TAGS]
    gaps = holiday_gaps(scenarios, public_holidays(settings.data_dir))
    messages = layer5(settings, scenarios)
    return layers, messages, report(layers, gaps, messages)


def main(argv=None) -> int:
    argparse.ArgumentParser(prog="python -m scheduler.eval.component", description=__doc__).parse_args(argv)
    settings = load_settings()
    layers, messages, text = build(settings)
    out = settings.results_dir / "component"
    out.mkdir(parents=True, exist_ok=True)
    for r in layers:
        write_csv(out / f"layer3-{r.tag}.csv", r.rows, ["scenario", "run", "participant", "key", "agent", "cause", "slots"])
    write_csv(out / "layer5.csv", messages, ["label", "kind", "filter", "checker", "text"])
    (out / "report.md").write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
