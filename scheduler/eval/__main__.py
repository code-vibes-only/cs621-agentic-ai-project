"""One command per job:

    uv run python -m scheduler.eval --arm a --split dev --scenarios dev-001,dev-002 --runs 3 --tag dev-try
    uv run python -m scheduler.eval --check-model

Each episode writes one result file under results/<tag>/<arm>/<scenario>/run<k>.json and prints
the checker's verdict on one line."""
import argparse
import sys

from scheduler import llm
from scheduler.config import load_settings
from scheduler.contracts.result import save_result
from scheduler.contracts.scenario import load_split
from scheduler.eval.arms import ARMS
from scheduler.eval.checker import grade
from scheduler.eval.episode import run_episode


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m scheduler.eval")
    p.add_argument("--arm", choices=sorted(ARMS))
    p.add_argument("--split", default="dev", choices=["dev", "heldout"])
    p.add_argument("--scenarios", default="all", help="comma-separated ids, or 'all'")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--tag", default="scratch", help="names the sweep; results go to results/<tag>/")
    p.add_argument("--check-model", action="store_true", help="one tiny call: is the model available, what does it cost?")
    args = p.parse_args(argv)
    settings = load_settings()

    if args.check_model:
        from langchain_core.messages import AIMessage, HumanMessage
        reply = llm.call([HumanMessage("Reply with the single word: ready")],
                         fake=lambda m: AIMessage(content="ready"))
        print(f"{settings.model} (effort {settings.reasoning_effort}): {reply.content!r}; "
              f"{llm.USAGE['input_tokens']} in / {llm.USAGE['output_tokens']} out tokens; USD {llm.cost_usd():.6f}")
        return 0
    if not args.arm:
        p.error("--arm is required")

    scenarios = load_split(settings.data_dir, args.split)
    if args.scenarios != "all":
        wanted = args.scenarios.split(",")
        scenarios = [s for s in scenarios if s.id in wanted]
    run_all(args.arm, scenarios, args.runs, args.tag, settings)
    return 0


def run_all(arm, scenarios, runs, tag, settings) -> None:
    for run in range(1, runs + 1):
        for scenario in scenarios:
            result = run_episode(arm, ARMS[arm], scenario, run, tag, settings)
            path = save_result(settings.results_dir, result)
            g = grade(scenario, result)
            print(f"{arm} {scenario.id} run{run}: {'PASS' if g.passed else 'fail'} "
                  f"({result.outcome.status} {result.outcome.start or ''}) "
                  f"calls {result.llm_calls} tokens {g.tokens} USD {result.cost_usd:.4f} -> {path.relative_to(settings.results_dir.parent)}")


if __name__ == "__main__":
    sys.exit(main())
