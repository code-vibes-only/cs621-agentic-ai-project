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

The final numbers in the deck come from this run. Each team member runs every LLM arm (b, c, d)
on their own 7 held-out scenarios, 3 runs each (attack cases 5 runs), on their own key: about 63
episodes, about USD 0.60 and about an hour. Keys cannot be pooled, so the work is split by
scenario, not by arm.

| N | Team member | Scenarios |
|---|---|---|
| 1 | huongiangbui | ho-001 to ho-007 |
| 2 | Andreojk | ho-008 to ho-014 |
| 3 | zexellew2024 | ho-015 to ho-021 |
| 4 | Kenneth | ho-022 to ho-028, plus arm (a) on all 33 (no model, no cost) |
| 5 | NJYao | ho-029 to ho-033 |

**1. Get the latest code and your key in place.**

```sh
git switch main && git pull
uv sync
cp .env.example .env          # Windows: copy .env.example .env
```

Put your own `OPENAI_API_KEY` in `.env` (gitignored: never commit it). Leave the other settings
as they are: every member must run the same model, reasoning effort and caps.

**2. Check the key and the model (one tiny call, under USD 0.001).**

```sh
uv run --env-file .env python -m scheduler.eval --check-model
```

**3. Rehearse your subset for free (scripted model, a few seconds).**

```sh
SCHEDULER_FAKE_LLM=1 uv run python -m scheduler.eval --sweep N --tag rehearsal
```

On Windows PowerShell: `$env:SCHEDULER_FAKE_LLM=1; uv run python -m scheduler.eval --sweep N --tag rehearsal; Remove-Item Env:SCHEDULER_FAKE_LLM`.
Then delete `results/rehearsal/`; it is not committed.

**4. Run it for real (about an hour; keep the laptop awake).**

```sh
uv run --env-file .env python -m scheduler.eval --sweep N --tag heldout-final
```

Each episode prints one line and writes one file under `results/heldout-final/<arm>/<scenario>/`.
A `fail` line is a result, not an error: do not rerun to get a pass. If the command itself stops
part-way (a crash, a lost connection, the laptop sleeping), tell the team before rerunning: a
rerun starts your subset from the beginning and costs the full amount again.

Member 4 also runs the free/busy baseline, which makes no model calls:

```sh
uv run python -m scheduler.eval --arm a --split heldout --scenarios all --runs 3 --tag heldout-final
```

**5. Hand in your results by pull request (`main` is protected).**

```sh
git switch -c sweep/N
git add results/heldout-final
git commit -m "Held-out sweep, member N"
git push -u origin sweep/N
```

Open a pull request into `main`. Commit only `results/heldout-final/`: no `.env`, no
`report.md`, no other changes. Each member's files are separate, so the pull requests do not
clash.

**6. Report (once all five are merged; anyone can run it).**

```sh
uv run python -m scheduler.eval --report heldout-final
```

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
