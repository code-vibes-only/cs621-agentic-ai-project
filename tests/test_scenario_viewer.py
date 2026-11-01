from pathlib import Path

from scheduler.contracts.scenario import load_scenario
from scheduler.scenario_viewer import format_scenario


def test_scenario_viewer_explains_attack_case():
    scenario_path = Path("data/scenarios/dev/dev-026.json")
    text = format_scenario(load_scenario(scenario_path))

    assert "SCENARIO dev-026  [DEV]" in text
    assert "Owen Goh (p15): required" in text
    assert "Calendar: work" in text
    assert "Focus: board memo [movable, low priority]" in text
    assert "Please keep Friday afternoons clear." in text
    assert "Expected slot: 2026-11-03T09:00" in text
    assert "from e-p14-1 (Customer workshop)" in text
    assert "Attack test:" in text
    assert "Kind: poisoned_memory" in text
    assert "Payload location: mem-p15-9 (Calendar sync note:" in text
    assert "Must not happen: hard_violation" in text


def test_scenario_viewer_handles_empty_optional_sections():
    scenario_path = Path("data/scenarios/dev/dev-001.json")
    text = format_scenario(load_scenario(scenario_path))

    assert "Participant replies: none" in text
    assert "Events during the episode: none" in text
