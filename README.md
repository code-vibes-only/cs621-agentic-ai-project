# Agentic Natural Language Scheduler

A scheduler for any group, at work or outside it, where each participant has a private
personal agent. The personal agent reads its participant's calendars (work, family, club and
so on) and messages, remembers what they said, looks up events that are in no calendar, and
tells a coordinator agent only *when* they can meet, never *why*. The coordinator agent ranks
slots, asks only the people blocking a slot (privately), replans, and sends an invite only after
the organiser approves. Everything runs in a sandbox: no real calendar or message is read or
written. The design is in [brief.md](brief.md); the security review is in
[docs/security-review.md](docs/security-review.md).

## Set up

You need [uv](https://docs.astral.sh/uv/). From the repo root:

```sh
uv sync                                     # installs the pinned Python and packages from uv.lock
SCHEDULER_FAKE_LLM=1 uv run pytest          # the tests use a scripted fake model: no key, no cost
```

For real runs, put your own OpenAI key in your shell, or in a local `.env` (gitignored; never commit it):

```sh
export OPENAI_API_KEY=sk-...                # see .env.example for every setting
uv run python -m scheduler.eval --check-model
```

## Run

One command per job. Each episode writes one result file under `results/<tag>/`.

```sh
# one arm on some dev scenarios, 3 runs
uv run python -m scheduler.eval --arm d --split dev --scenarios dev-001,dev-002 --runs 3 --tag my-try
# grade everything under a tag: mean ± sample SD per arm, action classes, failure clusters
uv run python -m scheduler.eval --report my-try
```

Arms: `a` free/busy finder, `b` single grounded call, `c` one agent with shared context,
`d` personal agents + coordinator agent (our design).

### Held-out sweep (run centrally)

The final numbers in the deck come from this run. The team agreed on 23 Oct to run it centrally
on Kenneth's machine, with the team sharing the OpenAI cost (brief §16). The arms are (b), (c)
and (d); the free/busy finder (a) makes no model calls and runs once.

**What runs.** The 33 frozen held-out scenarios in `data/scenarios/heldout/` (frozen at tag
`v0.3.0`) are split into five subsets of 7. Each subset runs every LLM arm, 3 runs each, and
attack cases 5 runs. That is about 63 episodes and USD 0.60 a subset, so about USD 3 in all. The
five subsets run side by side, which takes about an hour.

| Subset | Scenarios | Command |
|---|---|---|
| 1 | ho-001 to ho-007 | `--sweep 1` |
| 2 | ho-008 to ho-014 | `--sweep 2` |
| 3 | ho-015 to ho-021 | `--sweep 3` |
| 4 | ho-022 to ho-028 | `--sweep 4` |
| 5 | ho-029 to ho-033 | `--sweep 5` |

```sh
git switch main && git pull && uv sync
uv run --env-file .env python -m scheduler.eval --check-model                 # one tiny call
SCHEDULER_FAKE_LLM=1 uv run python -m scheduler.eval --sweep 1 --tag rehearsal  # free rehearsal; delete results/rehearsal/ after
for n in 1 2 3 4 5; do                                                           # the real run, five subsets side by side
  uv run --env-file .env python -m scheduler.eval --sweep $n --tag heldout-final > sweep-$n.log 2>&1 &
done; wait
uv run python -m scheduler.eval --arm a --split heldout --scenarios all --runs 3 --tag heldout-final
uv run python -m scheduler.eval --report heldout-final
```

Each episode prints one line to its log and writes one file under
`results/heldout-final/<arm>/<scenario>/run<k>.json`. A `fail` line is a result, not an error:
nothing is rerun to get a pass. If a subset's command stops part-way, only that subset is rerun,
from the beginning, and the rerun is noted in HANDOFF.

**Where to follow it.** The results go to the branch `sweep/heldout-final` and a pull request
into `main`, so every result file, and finally `report.md`, can be read there. The run uses `main`.
Since the freeze (tag `v0.3.0`) the code has gained only the `--sweep` command and the demo app;
neither changes how an agent or the checker behaves (fake-mode grades checked identical, 23 Oct).
`scheduler/eval/__main__.py` holds the `--sweep` command; the arms are in
`scheduler/eval/arms.py`, and the checker that grades each episode is in `scheduler/eval/checker.py`.

Do not change prompts, code, data or the threshold before or during the sweep: the held-out set
and the threshold are frozen (brief §16). Anything you notice goes in an issue for the failure
analysis.

### Demo

A small group-chat and calendar app on top of the agents, for ten fictional people. Ask your own
agent, privately inside a group, to set up a meeting; the others' agents answer from their own
calendars, people answer their agent's private questions, and the organiser approves the time.
**View trace** replays any request step by step, lane by lane. Sign in as `alice`, `bob`,
`charlie`, `damian`, `eve` (a part-time study group), `felicia`, `george` (Alice's data team),
`hannah`, `ignatius` or `jack` (her friends and family); each password is the username.

There is no separate backend: the agents, the coordinator and the demo's SQLite store
(`data/demo/app.db`, gitignored) all run inside the one Streamlit process. With **Enable model calls**
off (the default, under 🧪 Demo tools in the sidebar) the agents are scripted, at no cost; turned on, the
real model runs on the key in your `.env`, at about USD 0.01-0.04 per meeting request.

On Windows, double-click `run-demo.bat`: it opens on http://localhost:8501 (the port is set at its top). Elsewhere:

```sh
uv sync --group demo
uv run --group demo python -m streamlit run scheduler/demo/app.py --server.address localhost --browser.gatherUsageStats false
```

`--server.address localhost` keeps the app off your network, since the demo passwords are the usernames.

### Docker

The image runs the same commands from the same lockfile. The key comes in at run time.

```sh
docker build -t scheduler .
docker run --rm --env-file .env -v "$PWD/results:/app/results" scheduler --arm d --scenarios dev-001
```

## Layout

| Path | What |
|---|---|
| `scheduler/contracts/` | What each part hands the next: availability summary, constraints, scenario file, tool records, episode result |
| `scheduler/sandbox/` | The simulated world: calendars, time away, messages, the request thread, holds, invites, and the call, write, guardrail and timeline records |
| `scheduler/agents/` | Personal agent, privacy filter, coordinator agent, the shared-context ablation, and the fakes used in tests |
| `scheduler/engine/` | Enumerator and scorer; approval gate, write and verify |
| `scheduler/eval/` | Arms, baselines, the episode runner, the independent checker and the metrics |
| `scheduler/world/` | The scenario generator and its assumptions (work, evening and weekend settings; attack cases) |
| `scheduler/demo/` | The demo app: groups, private agent chats, calendars and the trace replay |
| `docs/` | The security review |
| `data/` | The frozen corpus and the dev and held-out scenarios |
| `results/` | Result files from real runs; every reported number comes from one |
