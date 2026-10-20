"""Every test runs in fake mode: no model call, no cost, no key needed."""
import pytest

from scheduler.config import load_settings
from scheduler.contracts.scenario import load_split
from scheduler.sandbox import world


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    monkeypatch.setenv("SCHEDULER_FAKE_LLM", "1")


@pytest.fixture
def scenario():
    """Return a loader: scenario("dev-001") installs that scenario in a fresh sandbox."""
    settings = load_settings()
    by_id = {s.id: s for split in ("dev", "heldout") for s in load_split(settings.data_dir, split)}

    def load(sid):
        world.reset(by_id[sid], settings.data_dir / "corpus")
        return by_id[sid]
    return load
