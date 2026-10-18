# Work plan

Status: **Proposed, 18 Oct 2026**, drafted by Kenneth from [brief v0.5](brief.md). It becomes
agreed once every lane has an owner and the team has had its review window (until Mon 19 Oct
morning).

**Claiming a lane.** Reply in the team chat with the lane you want. Kenneth records the owner
here. Kenneth leads, and also takes whichever lane is left after the others are claimed.

Terms follow [brief §0](brief.md#0-definitions). Rules for AI agents are in
[AGENTS.md](AGENTS.md). Current state and next actions are in [HANDOFF.md](HANDOFF.md).

---

## Lanes at a glance

| Lane | Owns | Owner | Reviewer lane | First task (start now) |
|---|---|---|---|---|
| L1 Platform and harness | Skeleton, Dockerfile, config, sandbox, episode runner, result files | | L5 | Skeleton + Dockerfile; stub of the sandbox interface (C3) |
| L2 World and data | Scenario format, generator, schedule corpus, scripted replies and events, ground truth, dev and held-out sets | | L5 | Draft C2; hand-write the 5 G1 scenarios |
| L3 Personal agent and privacy | Availability summary and constraint types, personal agent, privacy filter, privacy probes | | L4 | Freeze C1 and C5; the privacy filter's schema validator |
| L4 Coordinator and control | Enumerator and scorer, coordinator agent loop, approval gate, write and verify, RSVP handling | | L3 | The enumerator over C5 and C3 (no LLM, no spend) |
| L5 Evaluation and baselines | Checker, metrics, arms (a)–(c), sweep plan, failure analysis, results tables | | L2 | Free/busy baseline and a checker skeleton on the 5 G1 scenarios |
| Lead (Kenneth, on top of a lane) | Contract sign-off, integration, gate reviews, Week 8 update, deck structure, demo script | Kenneth | — | Sign off C1–C5 at G1 |

The reviewer lane is the lane that consumes the output, so the reviewer is the person who will
notice when something they depend on is wrong.

## How we work

- **One branch and one pull request per task.** Keep pull requests small. The reviewer comes
  from the reviewer lane above. Merge after one approval.
- **Reviews within about 24 hours**, and the same day in the 24 hours before a gate.
- **Every change has a class:**
  - **Internal:** nothing another lane consumes changes. The lane reviewer is enough.
  - **Additive:** a new optional field, tool or file that existing consumers can ignore. Tell
    the consuming lanes in the pull request.
  - **Breaking:** an existing contract field, signature or meaning changes. This needs the
    consuming lanes to agree, a version bump in the contract file and a row in brief §16. Do it
    at a gate where possible.
- **Spend.** LLM calls come from your own key (USD 10 per calendar month). Keep development to
  about USD 5 per key. Cap model calls per episode and log tokens from the first run. No sweeps
  without telling the team first. See [brief §12](brief.md#12-stack-and-budget).
- **Public repo.** No keys, `.env` files, course PDFs or slides, or real personal data.
- **AI agents** read [AGENTS.md](AGENTS.md) and [HANDOFF.md](HANDOFF.md) first, and add a
  session-log row to HANDOFF at the end.
- **Status.** Update your lane's checklist in this file in the same pull request as the work.

## Contracts (frozen at G1, Mon 19 Oct)

Every lane builds against these. Until G1 they are drafts: use them, and raise any problem in
the contract's pull request. After G1, changes follow the change classes above.

| # | Contract | Owner lane | File | Consumed by |
|---|---|---|---|---|
| C1 | Availability summary schema (brief §4) | L3 | `scheduler/contracts/availability.py` | L4, L5 |
| C2 | Scenario file format: personas (work and personal calendars, leave with the reachable-if-urgent flag, preferences, pre-given consent), request (participants and roles), corpus state, scripted replies and events, ground truth, canaries, seed and generator version | L2 | `scheduler/contracts/scenario.py` | L1, L3, L4, L5 |
| C3 | Sandbox and tool interface: `read_my_calendar`, `get_leave`, `search_schedules`, place/release hold, send invite, read back, write log | L1 | `scheduler/contracts/tools.py` | L3, L4, L5 |
| C4 | Episode result file: arm, scenario, run, model and settings, trajectory, writes, tokens, cost, latency, outcome | L1 | `scheduler/contracts/result.py` | L5 |
| C5 | Constraint representation: typed hard and soft constraints over slots, with weights and the relaxable flag | L3 | `scheduler/contracts/constraints.py` | L4, L5 |

## Package layout (proposed)

```text
scheduler/
  config.py            # all settings from environment variables (L1)
  contracts/           # C1-C5 (owner lanes above)
  sandbox/             # calendars, holds, invites, write log (L1)
  world/               # generator, corpus builder (L2)
  agents/
    personal.py        # personal agent (L3)
    privacy.py         # privacy filter (L3)
    coordinator.py     # coordinator agent loop (L4)
  engine/
    enumerator.py      # enumerator and scorer (L4)
    approval.py        # approval gate, write and verify (L4)
  eval/
    runner.py          # one episode per command; one result file per episode (L1)
    checker.py         # independent checker (L5)
    baselines.py       # arms (a) and (b) (L5)
    metrics.py         # mean ± sample SD across runs; merge step (L5)
data/
  scenarios/dev/       # committed (synthetic only)
  scenarios/heldout/   # committed; frozen at G3
  corpus/              # frozen schedule corpus
results/               # committed result files; every reported number traces to one
```

Everything follows the "keep it portable" rules in [brief §12](brief.md#12-stack-and-budget).

---

## L1 Platform and harness

**Owner:** _unclaimed_ · **Reviewer lane:** L5

- **Consumes:** C2 (to load scenarios).
- **Produces:** the skeleton, C3, C4, the sandbox and the episode runner.

**First task (start now): skeleton and Dockerfile**

- `uv init`; Python version pinned in `.python-version`; `uv add` LangGraph, the OpenAI SDK and
  a test runner; `uv.lock` committed.
- `.env.example` listing `OPENAI_API_KEY`, the model name, and the data and results
  directories.
- `scheduler/config.py` reads those variables. Nothing is hard-coded, and paths are relative to
  the repo root.
- A Dockerfile that installs with `uv sync --frozen` and runs the same commands as `uv run`. Keys
  come in with `docker run --env-file .env`, never baked into the image.
- A stub of C3 with typed signatures and an in-memory implementation, so L3 and L4 can call it
  on day one.
- Done when: `uv run python -m scheduler.eval.runner --help` and the same command in Docker
  both work on a clean clone.

**Later**

- [ ] G1: the JSON/SQLite sandbox behind C3, with idempotent hold and invite writes, read-back
  and a write log.
- [ ] G1: C4, plus the runner writing one result file per episode, with a per-episode
  model-call cap and token and cost logging.
- [ ] G2: run an arm over a scenario range in parallel (asyncio or a process pool); reset
  between runs.
- [ ] G4: help L5 run the held-out sweep across keys.
- [ ] Stretch: the Streamlit demo (one pane per participant plus the request thread). The CLI
  comes first.

**Deck:** the architecture slide (with L3 and L4).

## L2 World and data

**Owner:** _unclaimed_ · **Reviewer lane:** L5

- **Consumes:** C1 and C5 (ground truth uses the same constraint types).
- **Produces:** C2, the generator, the schedule corpus, the scenarios and their ground truth.

**First task (start now): scenario format and 5 hand-checked scenarios**

- Draft C2 (see the contracts table).
- Hand-write 5 scenarios as C2 files:
  1. the brief §5 worked example (simple feasible);
  2. its "nobody fully free" variant (ask C, relax, replan);
  3. a lookup-required case (DataSummit);
  4. a required/optional case, where an optional participant's conflict must not block;
  5. a required decline after the invite (replan and new approval).
- Write the ground truth for each by hand. L5's checker must agree with it.

**Later**

- [ ] G1: the schedule corpus:
  - a dated snapshot of Singapore public holidays, with the source and date recorded;
  - fictional conference and training agendas;
  - an all-hands calendar;
  - a fictional league's fixture list;
  - the misleading items (an outdated agenda, a rescheduled session) and the page with an
    injected instruction.
- [ ] G2: the generator for personas (about 15), groups (about 8) and requests, with seeds and
  a generator version. It covers:
  - work and personal calendars;
  - leave, some marked reachable if urgent;
  - pre-given consent;
  - optional attendees;
  - canaries.
- [ ] G2: the dev set (about 20), covering every family in
  [brief §8](brief.md#8-eval-sets-and-metrics).
- [ ] G2: scripted participant replies and scripted events (new meetings, RSVPs).
- [ ] G2: write down the generation assumptions (density, leave frequency, shares of focus
  blocks, movable meetings, pre-given consent and optional attendees).
- [ ] G3: the held-out set (about 30, including about 4 social-group scenarios), frozen before
  anyone looks at held-out outputs.

**Deck:** the datasets slide.

## L3 Personal agent and privacy

**Owner:** _unclaimed_ · **Reviewer lane:** L4

- **Consumes:** C2, C3.
- **Produces:** C1, C5, the personal agent and the privacy filter.

**First task (start now): C1, C5 and the schema validator**

- C1 from the draft in [brief §4](brief.md#4-architecture):
  - `status` takes `available`, `prefer_not` or `unavailable`;
  - `weight` and `relaxable` fields;
  - an `unknown` list;
  - **no reason or title field**.
- C5: typed hard and soft constraints over slots. The personal agent produces them; the
  enumerator and the checker read them.
- The privacy filter's first half: reject any summary that does not match C1 exactly, including
  free text. This is plain code with unit tests and no LLM.

**Later**

- [ ] G1: the privacy filter's second half: scan every request-thread message for canaries and
  attribution ("B is on leave").
- [ ] G2: the personal agent:
  - turns natural language into C5 constraints;
  - decides movability (from the flag, or by asking);
  - calls `search_schedules` when needed;
  - remembers preferences, respecting expiry and scope;
  - answers from pre-given consent only for the commitment it names;
  - alerts its participant about clashes.
- [ ] G2: the summary builder (C5 → C1), treating unresolved windows as `unknown`, never free.
- [ ] G3: the privacy probe scenarios with L2 ("Why can't E do Monday 10?", repeated probing,
  the injected agenda).

**Deck:** the privacy result slide (with L5); the user experience slide (with the lead).

## L4 Coordinator and control

**Owner:** _unclaimed_ · **Reviewer lane:** L3

- **Consumes:** C1, C3, C5, the request's roles from C2.
- **Produces:** the enumerator, the coordinator agent, and the approval gate with write and
  verify.

**First task (start now): the enumerator**

- Lists every 30-minute slot in the planning horizon that satisfies the hard constraints of the
  **required** participants.
- Scores the soft constraints, including optional participants' availability, relaxable time
  and preferences.
- Never relaxes a hard constraint. This is enforced here, not in a prompt.
- Plain code with unit tests on the 5 G1 scenarios, so it needs no key and costs nothing.

**Later**

- [ ] G2: the coordinator agent as a LangGraph loop:
  - choose candidates;
  - ask only the blocking participant, privately, within the question budget (≤ 2 per
    participant per request);
  - relax with consent;
  - replan, with a round cap;
  - hand back when nothing works.
- [ ] G2: the approval gate:
  - approvals and consents stored outside model text;
  - availability rechecked at commit;
  - idempotent writes;
  - read-back before anything is reported "scheduled".
- [ ] G2: tentative holds (autonomous, auto-expiring, released on replan).
- [ ] G2: RSVP declines. A required decline means replan and a new approval; an optional
  decline keeps the meeting.
- [ ] Stretch (after G3, if ahead): backups, RSVP tentative and no response, multi-timezone.

**Deck:** the autonomy slide; the autonomy evidence slide (with L5).

## L5 Evaluation and baselines

**Owner:** _unclaimed_ · **Reviewer lane:** L2

- **Consumes:** C2 (ground truth), C4 (result files), C5.
- **Produces:**
  - the checker and metrics;
  - arms (a), (b) and (c);
  - the sweep plan;
  - failure analysis;
  - the results tables.

**First task (start now): free/busy baseline and checker skeleton**

- Arm (a): the earliest slot where every required participant's work and personal calendars
  are free. No preferences, no lookups, no relaxation.
- A checker that recomputes hard-constraint violations and slot quality from a scenario's ground
  truth. It never trusts the agent's or the enumerator's own "valid" flag.
- Run both on the 5 G1 scenarios and compare with L2's hand-written answers.

**Later**

- [ ] G1: the first measured cost per episode (with L1), once any LLM path runs. Replace the
  brief's estimate after the first 10 dev episodes.
- [ ] G2: the full metric set from [brief §8](brief.md#8-eval-sets-and-metrics):
  - pass rate (outcome and trajectory);
  - hard-constraint violations;
  - slot quality;
  - privacy leakage;
  - unnecessary and missed questions;
  - unconsented relaxations;
  - approval compliance;
  - tokens, cost and latency.
  - Each is reported as mean ± sample SD over at least 3 runs.
- [ ] G2: arm (b), the single grounded call.
- [ ] G3: arm (c), the single agent with shared context and the same privacy filter on its
  output.
- [ ] G3: fix the promotion threshold (mean − 1 SD ≥ 90%, zero critical violations), and note
  any change in brief §16.
- [ ] G4: the held-out sweep. Each team member runs 6 scenarios × arms (b), (c) and (d) × 3
  runs on their own key. Results are merged into one table.
- [ ] G4: read at least 5 passes, 5 failures and every critical violation before trusting the
  numbers; then the failure analysis.

**Deck:** the eval sets and baselines slides; the results slides.

## Lead (Kenneth)

On top of his own lane, Kenneth does the following:

- [ ] G1: sign off C1–C5 and freeze them.
- [ ] G2: integrate the lanes into one end-to-end run on the dev set.
- [ ] Run every gate review and record re-plans in HANDOFF.
- [ ] Wed 21 Oct: update brief §11's Week 8 row after the 20 Oct lecture.
- [ ] G5: deck structure and assembly, and the demo script.
- [ ] Keep HANDOFF's comms and session logs current.

---

## Gates

Dates follow [brief §14](brief.md#14-timeline). The lead checks each gate together with the
lanes that consume its outputs.

| Gate | Date | Exit criteria |
|---|---|---|
| G1 | Mon 19 Oct | C1–C5 frozen; the skeleton and Dockerfile run from a clean clone; 5 hand-checked scenarios; the free/busy baseline and checker agree with the hand-written answers; first measured cost per episode (if an LLM path runs) |
| G2 | Thu 22 Oct | Personal agents + coordinator agent run end to end on the dev set; the checker computes every metric; arm (b) runs |
| G3 | Sat 24 Oct | Held-out set frozen; arm (c) runs; privacy probes in place; promotion threshold fixed |
| G4 | Tue 27 Oct | All arms × 3 runs on the held-out set, split across keys; results merged; failure analysis done |
| G5 | Thu 29 Oct | Deck draft (12 slides); demo recorded |
| Done | Fri 30 Oct | Final deck and demo complete. Sat 31 Oct – Mon 2 Nov is buffer |

**Dependencies.** All five lanes can start their first task today against the draft contracts:
L1 ships a C3 stub, and L3 and L2 publish draft C1, C5 and C2 within the first day. The critical
path is C2 + C5 → the enumerator and the checker → the G1 comparison on 5 scenarios →
the coordinator agent → G2.

**If we slip:** the stretch items go first, then the Streamlit UI (keep the CLI), then the
social-group family. A slipped gate moves the work that depends on it, not the dates promised
in brief §14. Re-plans are logged in HANDOFF.

## Budget by lane

- L1 and L2 need no LLM calls. If L2 uses an LLM to vary preference wording, it keeps that
  capped and logged.
- L3, L4 and L5 spend from their own keys during development (about USD 5 each at most).
- The held-out sweep is split by scenario subset, not by lane: every team member runs their 6
  scenarios × arms (b), (c) and (d) × 3 runs (about USD 1.6 per key, estimated).
- November caps reset on 1 Nov and cover reruns in the buffer.

## Deck (12 slides)

The project spec requires: problem, objectives, autonomy level, datasets, eval sets, agent
evaluation, user experience, and the gaps found and how they were handled. Kenneth assembles
the deck. Each lane supplies the content for its slides by G5.

| # | Slide | Content from |
|---|---|---|
| 1 | Problem and end users | Lead |
| 2 | Objectives and research question | Lead |
| 3 | Architecture: personal agents, availability summary, coordinator agent | L1, L3, L4 |
| 4 | Autonomy level per action and per agent | L4 |
| 5 | Datasets and how they were generated | L2 |
| 6 | Eval sets and metrics | L5 |
| 7 | Baselines and ablation | L5 |
| 8 | Results: slot quality and pass rate against the baselines | L5 |
| 9 | Results: privacy, isolation against shared context | L3, L5 |
| 10 | Autonomy evidence: which action classes clear the threshold | L4, L5 |
| 11 | User experience: how participants' and organisers' work changes | Lead, L3 |
| 12 | Failure modes, gaps, how we handled them, and future work | All |
