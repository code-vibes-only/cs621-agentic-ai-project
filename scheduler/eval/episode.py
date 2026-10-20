"""One episode: reset the sandbox, run one arm on one scenario, and collect the record of what
happened into a result file. The world is reset first, so run 2 never inherits run 1's state."""
import subprocess
import time

from scheduler.config import ROOT, Settings
from scheduler.contracts.result import EpisodeResult, Outcome
from scheduler.contracts.scenario import Scenario
from scheduler.sandbox import world


def code_version() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def begin(scenario: Scenario, settings: Settings) -> float:
    """A fresh sandbox for one episode; returns the start time."""
    world.reset(scenario, settings.data_dir / "corpus")
    return time.perf_counter()


def collect(arm: str, scenario: Scenario, run: int, run_tag: str, settings: Settings, outcome: Outcome,
            started: float, error: str | None = None) -> EpisodeResult:
    """Everything the sandbox recorded during the episode, as one result."""
    return EpisodeResult(
        arm=arm, scenario_id=scenario.id, run=run, run_tag=run_tag, model=settings.model,
        reasoning_effort=settings.reasoning_effort, fake_llm=settings.fake_llm,
        code_version=code_version(), outcome=outcome, thread=list(world.THREAD),
        blocked_messages=list(world.BLOCKED), questions=list(world.QUESTIONS),
        summaries=list(world.SUMMARIES), calls=list(world.CALLS), writes=list(world.WRITES),
        timeline=list(world.TIMELINE), guardrails=list(world.GUARDRAILS),
        coordinator_context="\n".join(world.CONTEXT),
        latency_s=round(time.perf_counter() - started, 2), error=error)


def run_episode(arm: str, arm_fn, scenario: Scenario, run: int, run_tag: str, settings: Settings) -> EpisodeResult:
    started = begin(scenario, settings)
    error = None
    try:
        outcome = arm_fn(scenario)
    except Exception as e:                       # the harness must not stop: a crash is a failed episode
        outcome, error = Outcome(status="error", message=str(e)), f"{type(e).__name__}: {e}"
    return collect(arm, scenario, run, run_tag, settings, outcome, started, error)
