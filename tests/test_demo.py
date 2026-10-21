"""The demo runs end to end in fake mode: signing in, a replay of a saved episode, what each
person may see, and a live run where the test plays the organiser. Needs the demo group:
`uv run --group demo pytest`."""
import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from scheduler.config import load_settings  # noqa: E402
from scheduler.contracts.result import save_result  # noqa: E402
from scheduler.contracts.scenario import load_scenario  # noqa: E402
from scheduler.eval.arms import ARMS  # noqa: E402
from scheduler.eval.episode import run_episode  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "scheduler" / "demo" / "app.py")
DEMO = load_settings().data_dir / "demo"
USERS = {u["username"]: u for u in json.loads((DEMO / "users.json").read_text())["users"]}


@pytest.fixture(autouse=True)
def results_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHEDULER_RESULTS_DIR", str(tmp_path))
    return tmp_path


def signed_in(username: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="username").input(username)
    at.text_input(key="password").input(USERS[username]["password"])
    at.button[0].click().run()
    assert not at.exception
    return at


def everything(at: AppTest) -> str:
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption] + [c.value for c in at.text])


def saved_demo_run(sid: str, arm: str = "d") -> None:
    from scheduler.sandbox import world
    s = load_scenario(DEMO / "scenarios" / f"{sid}.json")
    world.reset(s, load_settings().data_dir / "corpus")
    save_result(load_settings().results_dir, run_episode(arm, ARMS[arm], s, 1, "demo", load_settings()))


def test_a_wrong_password_is_refused():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="username").input("part_time_student1")
    at.text_input(key="password").input("not-the-password")
    at.button[0].click().run()
    assert "wrong password" in at.error[0].value and "user" not in at.session_state


def test_admin_replay_shows_every_view_on_a_dev_scenario(scenario):
    s = scenario("dev-002")
    save_result(load_settings().results_dir, run_episode("d", ARMS["d"], s, 1, "demo", load_settings()))
    at = signed_in("demo_admin")
    at.sidebar.radio(key="set").set_value("Dev").run()
    at.sidebar.selectbox(key="scenario").set_value("dev-002").run()
    assert not at.exception
    assert {"Chat", "Calendars", "Tasks", "Participants", "Admin trace"} <= {t.label for t in at.tabs}
    text = everything(at)
    assert "Request thread" in text and "Private details in the coordinator's window:** none" in text
    assert "Outcome: scheduled" in at.success[0].value


def test_a_participant_sees_only_their_own_private_data():
    saved_demo_run("demo-001")
    at = signed_in("full_time_student1")                 # Ravi, who is asked privately
    at.sidebar.selectbox(key="scenario").set_value("demo-001").run()
    assert not at.exception
    labels = [t.label for t in at.tabs]
    assert "Admin trace" not in labels and "My data" in labels
    text = everything(at)
    assert "Visa interview" in text                      # his own calendar
    assert "I can swap that shift" in text               # his own private answer
    for other in ("Hospital follow-up", "tuition pick-up", "Data visualisation seminar"):
        assert other not in text, other                  # nobody else's private details


def test_a_participant_only_gets_their_requests():
    at = signed_in("lecturer1")
    options = at.sidebar.selectbox(key="scenario").options
    assert [o.split(":")[0] for o in options] == ["demo-003"]


def test_only_the_organiser_can_start_a_live_run():
    at = signed_in("part_time_student2")                 # Daniel organises none of his requests
    at.sidebar.radio(key="mode").set_value("Live").run()
    assert "Only the organiser" in at.info[0].value and not any(b.key == "run" for b in at.sidebar.button)


def test_live_run_waits_for_the_organiser(results_dir):
    at = signed_in("part_time_student1")                 # Aisha organises demo-001
    at.sidebar.selectbox(key="scenario").set_value("demo-001").run()
    at.sidebar.radio(key="mode").set_value("Live").run()
    at.sidebar.button(key="run").click().run()
    assert "Approve the invite" in at.warning[0].value
    at.button(key="approve").click().run()
    assert not at.exception and "Outcome: scheduled" in at.success[0].value
    assert list(results_dir.glob("demo-live/d/demo-001/run1.json"))
