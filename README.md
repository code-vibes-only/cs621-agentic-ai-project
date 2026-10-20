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

### Held-out sweep (one subset per team member)

Each team member runs every LLM arm on their own 7 held-out scenarios, 3 runs (attack cases
5 runs), on their own key:

```sh
uv run python -m scheduler.eval --sweep 1 --tag heldout-final     # member 1: ho-001..ho-007; members 2-5: --sweep 2..5
```

Commit your `results/heldout-final/` files; anyone can then merge and report:

```sh
uv run python -m scheduler.eval --report heldout-final
```

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
| `docs/` | The security review |
| `data/` | The frozen corpus and the dev and held-out scenarios |
| `results/` | Result files from real runs; every reported number comes from one |
