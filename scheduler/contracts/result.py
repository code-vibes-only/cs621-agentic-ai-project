"""The episode result file: one per arm x scenario x run. Grades are not stored here; the
checker computes them from this file and the scenario's ground truth, so changing a grader
never needs a rerun."""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from scheduler.contracts.availability import AvailabilitySummary
from scheduler.contracts.tools import Call, Write


class Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["scheduled", "hand_back", "error", "budget"]
    start: str | None = None
    end: str | None = None
    message: str = ""


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: str
    text: str
    channel: Literal["private", "thread"] = "private"


class TimelineEvent(BaseModel):
    """One step of an episode, in order, with who may see it: "thread" (every participant),
    a participant id, "coordinator", "organiser" or "system"."""
    model_config = ConfigDict(extra="forbid")
    seq: int
    actor: str
    kind: str
    text: str
    visible_to: list[str]


class GuardrailCheck(BaseModel):
    """One verdict of a check that runs outside the model, on what the model produced. Passes
    are recorded too, so a past run can be reconstructed from the record."""
    model_config = ConfigDict(extra="forbid")
    name: str
    where: Literal["input", "tool result", "tool call", "output", "runtime"]
    reads: str
    passed: bool
    detail: str = ""


class EpisodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    arm: str
    scenario_id: str
    run: int
    run_tag: str
    model: str
    reasoning_effort: str
    fake_llm: bool
    code_version: str
    outcome: Outcome
    thread: list[str] = []                 # every message posted in the request thread
    blocked_messages: list[str] = []       # messages the privacy filter stopped
    questions: list[Question] = []
    summaries: list[AvailabilitySummary] = []
    calls: list[Call] = []
    writes: list[Write] = []
    timeline: list[TimelineEvent] = []     # every step in order, for replaying an episode
    guardrails: list[GuardrailCheck] = []  # every guardrail verdict, passes included
    coordinator_context: str = ""          # what the coordinator saw, for the leak scan
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    error: str | None = None


def result_path(results_dir: Path, run_tag: str, arm: str, scenario_id: str, run: int) -> Path:
    return results_dir / run_tag / arm / scenario_id / f"run{run}.json"


def save_result(results_dir: Path, result: EpisodeResult) -> Path:
    path = result_path(results_dir, result.run_tag, result.arm, result.scenario_id, result.run)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2))
    return path


def load_results(results_dir: Path, run_tag: str) -> list[EpisodeResult]:
    return [EpisodeResult.model_validate(json.loads(p.read_text()))
            for p in sorted((results_dir / run_tag).glob("*/*/run*.json"))]
