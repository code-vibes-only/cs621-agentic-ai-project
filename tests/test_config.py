from scheduler.config import ROOT, load_settings


def test_defaults(monkeypatch):
    for key in ("SCHEDULER_MODEL", "SCHEDULER_REASONING_EFFORT", "SCHEDULER_MAX_LLM_CALLS", "SCHEDULER_MAX_TOKENS",
                "SCHEDULER_MAX_USD", "SCHEDULER_MAX_SECONDS"):
        monkeypatch.delenv(key, raising=False)
    s = load_settings()
    assert s.model == "gpt-5-mini" and s.reasoning_effort == "low" and s.max_llm_calls == 40
    assert (s.max_tokens, s.max_usd, s.max_seconds) == (150000, 0.08, 300)
    assert s.data_dir == ROOT / "data"


def test_environment_wins(monkeypatch):
    monkeypatch.setenv("SCHEDULER_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("SCHEDULER_RESULTS_DIR", "results-test")
    s = load_settings()
    assert s.model == "gpt-5.4-mini" and s.results_dir == ROOT / "results-test"
