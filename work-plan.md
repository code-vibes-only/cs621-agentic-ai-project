# Work plan

Status: **updated 21 Oct 2026** for the team's 20 Oct decisions (brief v0.7 §16): the scheduler
is general-purpose, Week 8 guardrails are in, a demo page is built last, and the build lands as
one commit per step with no replay. It replaced the 18 Oct draft that had each lane build its own
part in parallel.

**Why it changed.** Most of the build depends on the step before it:
- the contracts come first;
- the sandbox and data need the contracts;
- the enumerator needs the summaries;
- the agents need the enumerator, the filter and the gate;
- the checker and arms need all of it.

Five lanes in parallel would mostly wait on each other. So the build is **one guided solution in
18 steps**, already built and tested:
- **The code is in this repo, one commit per step** on `main`, with tags `v0.1.0`, `v0.2.0` and
  `v0.3.0` at the gates. Nobody replays it.
- **Each lane owns a section of the steps for review**: you read your steps in the private guide
  repo next to their commits here, and raise changes. You also present that part in the deck and
  Q&A.
- **The team improves the finished product**: changes go in as pull requests or issues, agreed
  centrally. A change to a contract between parts needs the lanes that use it to agree.

**Lanes were assigned at random on 18 Oct** (Kenneth took L4); swap among yourselves and tell
Kenneth the final pairing, and he records it below. Terms follow [brief §0](brief.md#0-definitions). Current
state and next actions are in [HANDOFF.md](HANDOFF.md).

---

## Lanes: what each one reviews

| Lane | Section of the build | Steps you review | Owner |
|---|---|---|---|
| L1 Platform and harness | The uv project and settings, the sandbox (calendars, messages, the timeline), the model client and runner, Docker, the sweep command, the demo's packaging | 01 Skeleton · 02 (tools and result contracts) · 04 Sandbox · 07 Runner and Docker · 17 Sweep rehearsal · 18 (demo packaging) | huongiangbui (assigned) |
| L2 World and data | The scenario format, the five hand-checked scenarios, the corpus, the generator (three settings, new families), the dev and held-out sets | 02 (scenario contract) · 03 Scenarios and corpus · 12 Generator · 16 Held-out freeze | Andreojk (assigned) |
| L3 Personal agent and privacy | The availability summary and constraints, the personal agent (calendars and messages), the privacy filter, the privacy probes, the attack cases | 02 (availability and constraints contracts) · 08 Personal agent · 09 Privacy filter · 15 (attack cases) · 16 (probes) | zexellew2024 (assigned) |
| L4 Coordinator and control | The enumerator, the approval gate, the coordinator agent, the caps and guardrails | 05 Enumerator · 10 Approval gate · 11 Coordinator agent · 15 (caps, guardrails) | Kenneth |
| L5 Evaluation and baselines | The checker, the baselines and ablation, the metrics and attack report, the sweep results | 06 Checker and free/busy · 13 Metrics and single-call baseline · 14 Shared-context ablation | NJYao (assigned) |
| Lead (Kenneth, on top of L4) | Lands the build, runs the gates, assembles the deck and the demo recording | all · 18 (what the demo shows) | Kenneth |

## How a review works

1. The steps live in a **private guide repo**, `code-vibes-only/cs621-scheduler-guide`, where
   every team member is a collaborator (accept the invite). Its `main` is protected: raise
   changes as issues there, don't push. Each step:
   - names its commit in this repo;
   - gives every file in full and explains every line;
   - shows the real output to expect;
   - ends with "Share for review": the questions the review must answer.
2. Read your steps next to their commits here (each step links its commit). Answer the step's
   review questions as a comment on the commit, or in the team chat.
3. A change you want goes in as a pull request here (or an issue, if you'd rather discuss it
   first). Small fixes inside one lane are fine to agree in the PR. Anything that changes what
   another lane uses waits for that lane's owner.
4. Kenneth merges after your approval.

Reviews within about 24 hours, and the same day in the 24 hours before a gate.

## Contracts (frozen at G1)

These are what one part hands the next: typed models under `scheduler/contracts/`, summarised in
the guide repo's `contracts.md` (v1.1 since the 20 Oct reframe: named calendars, messages, request
weekdays, the timeline and the guardrail record).

| Contract | Module | Reviewed by |
|---|---|---|
| Availability summary (when, never why) | `scheduler/contracts/availability.py` | L3 |
| Constraints and rules (hard, movable, soft) | `scheduler/contracts/constraints.py` | L3 |
| Scenario file, with ground truth | `scheduler/contracts/scenario.py` | L2 |
| Sandbox records (corpus documents, calls, writes) | `scheduler/contracts/tools.py` | L1 |
| Episode result file | `scheduler/contracts/result.py` | L1 |

## Gates

| Gate | Date | Tag | Exit criteria |
|---|---|---|---|
| G1 | Thu 22 Oct (slipped from Mon 19) | `v0.1.0` | Steps 01–07: contracts frozen; tests and the Docker run pass from a clean clone; 5 hand-checked scenarios; the free/busy baseline and checker agree with the hand-written answers; `gpt-5-mini` checked and a first cost measured |
| G2 | Thu 22 Oct | `v0.2.0` | Steps 08–13: personal agents + coordinator agent end to end on dev, inside and outside work; every metric reported as mean ± sample SD over 3 runs; the single-call baseline runs |
| G3 | Thu 22 Oct (lands); review by Sat 24 Oct | `v0.3.0` | Steps 14–16: the shared-context ablation; guardrails and attack cases; held-out set frozen with the probes and attacks; promotion threshold confirmed by the team before the sweep |
| Sweep | Tue 27 Oct | — | Steps 17–18 in: each team member runs their held-out subset (`--sweep N`, see README) on their own key and commits the results |
| Done | Fri 30 Oct | — | Deck and demo complete; 31 Oct – 2 Nov is buffer |

**If we slip:** stretch items go first, then the Streamlit UI (keep the CLI), then the social-group
family. A slipped gate moves the work that depends on it, not the dates promised in brief §14.

## Budget

- Building the guided solution spends at most USD 2 of Kenneth's key.
- There is no replay. Re-running a step's real commands is optional, and each states its cost first.
- The held-out sweep is split by scenario subset: every team member runs their 7 scenarios × arms
  b, c and d × 3 runs, attack cases 5 runs (about 63 episodes, under USD 1) on their own key.

## Deck (12 slides)

The project spec requires these items:
- problem;
- objectives;
- autonomy level;
- datasets;
- eval sets;
- agent evaluation;
- user experience;
- the gaps found and how they were handled.

Each lane supplies the slides for its section, and Kenneth assembles them.

| # | Slide | Content from |
|---|---|---|
| 1 | Problem and end users | Lead |
| 2 | Objectives and research question | Lead |
| 3 | Architecture: personal agents, availability summary, coordinator agent; guardrails in code | L1, L3, L4 |
| 4 | Autonomy level per action class (A0–A4) and per agent | L4 |
| 5 | Datasets and how they were generated: work, evenings, weekends; calendars and messages | L2 |
| 6 | Eval sets and metrics | L5 |
| 7 | Baselines and ablation | L5 |
| 8 | Results: slot quality and pass rate against the baselines | L5 |
| 9 | Results: privacy and attacks, isolation against shared context (the trifecta) | L3, L5 |
| 10 | Autonomy evidence: which action classes clear the threshold; approvals asked and refused | L4, L5 |
| 11 | User experience: the demo recording; how participants' and organisers' work changes | Lead, L3 |
| 12 | Failure modes, gaps, how we handled them, and future work | All |
