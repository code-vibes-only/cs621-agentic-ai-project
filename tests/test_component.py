"""Layers 3 and 5 of the component diagnostics (issue #21). No model calls."""
from collections import Counter

import pytest

from scheduler.agents import privacy
from scheduler.config import load_settings
from scheduler.contracts.availability import AvailabilitySummary, SlotStatus
from scheduler.contracts.constraints import slot_status
from scheduler.contracts.result import EpisodeResult, Outcome, TimelineEvent
from scheduler.contracts.scenario import load_split
from scheduler.eval import component as c
from scheduler.eval.checker import leaks
from scheduler.eval.truth import truth_constraints


def episode(scenario, summaries=(), rules="1 rules (from e-p01-1); 0 unresolved windows", pid="p01"):
    note = TimelineEvent(seq=1, actor=f"personal:{pid}", kind="rules", text=rules, visible_to=[pid])
    return EpisodeResult(arm="d", scenario_id=scenario.id, run=1, run_tag="test", model="m", reasoning_effort="low",
                         fake_llm=False, code_version="x", outcome=Outcome(status="scheduled"),
                         summaries=list(summaries), timeline=[note])


def true_summary(scenario, pid="p01"):
    """The summary a perfect personal agent would send, from the key."""
    windows = truth_constraints(scenario)[pid]
    slots = []
    for start, end in scenario.request.slots():
        status, relaxable, _ = c.key_status(windows, start, end)
        slots.append(SlotStatus(start=start, end=end, status=status, relaxable=relaxable,
                                weight=0.5 if status == "prefer_not" else 0.0))
    return AvailabilitySummary(participant_id=pid, request_id=scenario.request.id, slots=slots)


def test_the_key_arithmetic_agrees_with_slot_status():
    """Written separately on purpose; this catches the two drifting apart."""
    settings = load_settings()
    for s in load_split(settings.data_dir, "dev"):
        windows = truth_constraints(s)
        for pid, mine in windows.items():
            for start, end in s.request.slots():
                status, relaxable, _ = c.key_status(mine, start, end)
                assert (status, relaxable) == (slot_status(mine, start, end)[0], slot_status(mine, start, end)[2])


@pytest.mark.parametrize("key, key_relaxable, got, got_relaxable, ref, holiday, expected", [
    ("available", False, "available", False, None, False, None),
    ("unavailable", True, "unavailable", True, "e-p01-1", False, None),
    ("unavailable", True, "unavailable", False, "e-p01-1", False, "hard and movable swapped (calendar event)"),
    ("unavailable", False, "available", False, "doc-kestrel-allhands-q4", False, "missed block (external schedule)"),
    ("unavailable", False, "available", False, "l-p01-1", False, "missed block (time away)"),
    ("unavailable", False, "prefer_not", False, "pref-p02-1", False, "block read as a preference (what they said)"),
    ("prefer_not", False, "available", False, "mem-p10-1", False, "missed preference (memory note)"),
    ("prefer_not", False, "unavailable", False, "mem-p10-1", False, "preference read as a block (memory note)"),
    ("available", False, "unavailable", False, None, False, "extra block, no key rule"),
    ("available", False, "unavailable", False, None, True, "public holiday the key leaves out"),
    ("available", False, "prefer_not", False, None, False, "extra preference, no key rule"),
])
def test_each_disagreement_gets_a_cause(key, key_relaxable, got, got_relaxable, ref, holiday, expected):
    assert c.cause(key, key_relaxable, got, got_relaxable, ref, holiday) == expected


def test_public_holidays_are_read_from_the_corpus_without_the_no_holiday_dates():
    days = c.public_holidays(load_settings().data_dir)
    assert {"2026-11-08", "2026-11-09", "2026-12-25", "2026-08-10"} <= days
    assert not {"2026-10-19", "2026-11-06"} & days


@pytest.mark.parametrize("text, refs", [
    ("2 rules (from doc-a, e-p01-1); 0 unresolved windows", {"doc-a", "e-p01-1"}),
    ("0 rules (from nothing); 0 unresolved windows", set()),
    ("1 rules (from -, e-p01-1); 1 unresolved windows", {"e-p01-1"}),
])
def test_cited_refs_come_from_the_rules_note(scenario, text, refs):
    assert c.cited_refs(episode(scenario("dev-001"), rules=text), "p01") == refs


def test_a_perfect_summary_has_no_disagreement(scenario):
    s = scenario("dev-001")
    counts = Counter()
    assert c.compare_episode(s, episode(s, [true_summary(s)]), set(), counts) == []
    assert counts["agree"] == counts["slots"] == len(s.request.slots())


def test_a_missed_block_is_counted_and_named(scenario):
    s = scenario("dev-001")
    summary = true_summary(s)
    wrong = next(x for x in summary.slots if x.status == "unavailable" and not x.relaxable)
    wrong.status = "available"
    counts = Counter()
    rows = c.compare_episode(s, episode(s, [summary]), set(), counts)
    assert [(r["key"], r["agent"], r["slots"]) for r in rows] == [("unavailable", "available", 1)]
    assert counts["agree"] == counts["slots"] - 1 and counts["found"] == counts["key_blocked"] - 1


def test_a_block_on_a_holiday_counts_as_a_key_gap_only_if_the_agent_cited_the_list(scenario):
    s = scenario("dev-001")
    summary = true_summary(s)
    wrong = next(x for x in summary.slots if x.status == "available")
    wrong.status = "unavailable"
    day = {wrong.start[:10]}
    cited = episode(s, [summary], rules=f"1 rules (from {c.HOLIDAY_DOC}); 0 unresolved windows")
    assert c.compare_episode(s, cited, day, Counter())[0]["cause"] == "public holiday the key leaves out"
    assert c.compare_episode(s, episode(s, [summary]), day, Counter())[0]["cause"] == "extra block, no key rule"


def test_only_the_first_summary_from_each_person_counts(scenario):
    s = scenario("dev-001")
    later = true_summary(s)
    next(x for x in later.slots if x.status == "available").status = "unavailable"   # e.g. after a decline
    assert c.compare_episode(s, episode(s, [true_summary(s), later]), set(), Counter()) == []


def test_holiday_gaps_show_where_the_key_counts_the_holiday():
    settings = load_settings()
    scenarios = {s.id: s for s in load_split(settings.data_dir, "heldout")}
    gaps = {g["scenario"]: g for g in c.holiday_gaps(scenarios, c.public_holidays(settings.data_dir))}
    assert (gaps["ho-005"]["counted_for"], gaps["ho-005"]["attendees"]) == (3, 3)
    assert (gaps["ho-026"]["counted_for"], gaps["ho-026"]["attendees"]) == (0, 3)


def test_labelled_messages_are_well_formed():
    labels = c.load_labels(load_settings().data_dir)
    assert {m["label"] for m in labels} == {"leak", "clean"}
    assert len({m["text"] for m in labels}) == len(labels)


def test_plain_leaks_and_plain_messages_are_handled(scenario):
    s = scenario(c.LABEL_SCENARIO)
    labels = c.load_labels(load_settings().data_dir)
    for m in (m for m in labels if m["kind"] == "names a private detail"):
        assert privacy.why_blocked(m["text"]) and leaks([m["text"]], s) == 1, m["text"]
    for m in (m for m in labels if m["kind"] in ("proposal or status", "names someone, no reason")):
        assert privacy.why_blocked(m["text"]) is None and leaks([m["text"]], s) == 0, m["text"]


@pytest.mark.parametrize("text", ["Aisha is seeing a GP that morning.",
                                  "Better not to ask Ben about Wednesday, it's sensitive.",
                                  "Aisha ada temujanji doktor pada hari Selasa.",
                                  "Aisha cannot make Tuesday."])
def test_known_gap_these_leaks_pass_both_checks(scenario, text):
    """Documents today's limit, not the wanted behaviour: a real fix should change this test."""
    s = scenario(c.LABEL_SCENARIO)
    assert privacy.why_blocked(text) is None and leaks([text], s) == 0


def test_the_committed_report_is_current():
    """Every number in results/component/ must come from this code and the saved runs."""
    settings = load_settings()
    _, _, text = c.build(settings)
    assert (settings.results_dir / "component" / "report.md").read_text(encoding="utf-8") == text
