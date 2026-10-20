from scheduler.config import load_settings
from scheduler.contracts.result import save_result
from scheduler.contracts.scenario import load_split
from scheduler.eval.arms import ARMS
from scheduler.eval.episode import run_episode
from scheduler.eval.metrics import mean_sd, report


def test_mean_sd_uses_the_sample_sd():
    assert mean_sd([0.6, 0.8, 1.0]) == "0.80 ± 0.20"


def test_report_over_three_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHEDULER_RESULTS_DIR", str(tmp_path))
    settings = load_settings()
    for s in load_split(settings.data_dir, "dev")[:2]:
        for run in (1, 2, 3):
            save_result(settings.results_dir, run_episode("a", ARMS["a"], s, run, "t", settings))
    text = report(settings, "t")
    assert "| a | 6 | 3 |" in text and (tmp_path / "t" / "grades.csv").exists()
