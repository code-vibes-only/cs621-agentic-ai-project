from scheduler.config import load_settings
from scheduler.contracts.scenario import load_split
from scheduler.eval.truth import compute


def test_every_scenario_file_is_valid():
    settings = load_settings()
    assert len(load_split(settings.data_dir, "dev")) >= 5


def test_hand_checked_answers_match_the_rules():
    """The answer written by hand must be one of the best slots the rules give."""
    for s in load_split(load_settings().data_dir, "dev"):
        if s.generator_version == "hand" and s.ground_truth.expected_slot:
            t = compute(s)
            assert s.ground_truth.expected_slot in t.expected, s.id
            assert t.utility[s.ground_truth.expected_slot] == t.best, s.id
