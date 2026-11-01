"""Run with: uv run pytest scheduler/visualisation

The scenario viewer's data must agree with the repo's own answer key and saved results."""
import json
from pathlib import Path

import pytest

from scheduler.visualisation import scenario_viewer as sv

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def built():
    return sv.build(ROOT)


def test_covers_every_scenario_and_agrees_with_truth(built):
    data, problems = built
    assert data["meta"]["n"] == 59
    assert problems == []


def test_families_are_the_last_tag(built):
    data, _ = built
    assert all(s["family"] == s["tags"][-1] for s in data["scen"].values())


def test_every_attack_scenario_has_its_payload_text(built):
    data, _ = built
    attacks = [s for s in data["scen"].values() if s["gt"]["attack"]]
    assert attacks and all(s["attack"] and s["attack"]["text"] for s in attacks)


def test_brief_reader_marks_drafts(tmp_path):
    (tmp_path / "x.md").write_text("<!-- draft -->\n## What this tests\nA\n## Why it matters\nB\n## What a good run does\n- C\n", encoding="utf-8")
    b = sv.read_brief(tmp_path / "x.md")
    assert b == dict(tests="A", why="B", good="- C", draft=True)
    assert sv.read_brief(tmp_path / "missing.md") is None


def test_every_scenario_gets_a_brief_without_any_saved_file(built):
    data, _ = built
    assert all(s["brief"] and s["brief"]["tests"] and s["brief"]["good"] for s in data["scen"].values())


def test_html_is_one_self_contained_file(built):
    html = sv.render(built[0])
    assert html.startswith("<!doctype html>") and "__DATA__" not in html and "<link " not in html and "<script src" not in html and "@import" not in html


def test_scenario_files_are_not_touched():
    before = {p: p.read_bytes() for p in (ROOT / "data" / "scenarios").glob("*/*.json")}
    sv.build(ROOT)
    assert before == {p: p.read_bytes() for p in before}
