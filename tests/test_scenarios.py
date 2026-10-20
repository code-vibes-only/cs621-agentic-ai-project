from scheduler.config import load_settings
from scheduler.contracts.scenario import load_split


def test_every_scenario_file_is_valid():
    settings = load_settings()
    assert len(load_split(settings.data_dir, "dev")) >= 5
