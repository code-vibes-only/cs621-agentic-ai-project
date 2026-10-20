"""Settings, read from environment variables so the same code runs locally, in Docker and on
any team member's machine. Nothing here is a secret except the API key, which is never
stored in the repo."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # the repo root: paths are relative to it


@dataclass(frozen=True)
class Settings:
    model: str
    reasoning_effort: str
    fake_llm: bool
    max_llm_calls: int          # the four caps per episode: model calls, tokens, USD and seconds
    max_tokens: int
    max_usd: float
    max_seconds: float
    data_dir: Path
    results_dir: Path


def load_settings() -> Settings:
    """Read the settings now, so a test or a command can change the environment first."""
    return Settings(
        model=os.environ.get("SCHEDULER_MODEL", "gpt-5-mini"),
        reasoning_effort=os.environ.get("SCHEDULER_REASONING_EFFORT", "low"),
        fake_llm=os.environ.get("SCHEDULER_FAKE_LLM", "0") == "1",
        max_llm_calls=int(os.environ.get("SCHEDULER_MAX_LLM_CALLS", "40")),
        max_tokens=int(os.environ.get("SCHEDULER_MAX_TOKENS", "150000")),
        max_usd=float(os.environ.get("SCHEDULER_MAX_USD", "0.08")),
        max_seconds=float(os.environ.get("SCHEDULER_MAX_SECONDS", "300")),
        data_dir=ROOT / os.environ.get("SCHEDULER_DATA_DIR", "data"),
        results_dir=ROOT / os.environ.get("SCHEDULER_RESULTS_DIR", "results"),
    )
