"""The demo runs end to end in fake mode: a replay of a saved episode, and a live run where the
test plays the organiser. Needs the demo group: `uv run --group demo pytest`."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from scheduler.config import load_settings  # noqa: E402
from scheduler.contracts.result import save_result  # noqa: E402
from scheduler.eval.arms import ARMS  # noqa: E402
from scheduler.eval.episode import run_episode  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "scheduler" / "demo" / "app.py")


@pytest.fixture(autouse=True)
def results_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHEDULER_RESULTS_DIR", str(tmp_path))
    return tmp_path


def test_replay_shows_the_thread_the_coordinator_and_each_participant(scenario):
    s = scenario("dev-002")
    save_result(load_settings().results_dir, run_episode("d", ARMS["d"], s, 1, "demo", load_settings()))
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.selectbox(key="scenario").set_value("dev-002").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Request thread" in text and "The coordinator sees" in text and "Private details in its window:** none" in text
    assert "Outcome: scheduled" in at.success[0].value


def test_live_run_waits_for_the_organiser(results_dir):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio(key="mode").set_value("Live").run()
    at.sidebar.button(key="run").click().run()
    assert "Approve the invite" in at.warning[0].value
    at.button(key="approve").click().run()
    assert not at.exception and "Outcome: scheduled" in at.success[0].value
    assert list(results_dir.glob("demo-live/d/dev-001/run1.json"))
