# Work plan

Status: **Proposed, 18 Oct 2026** (Kenneth), pending the team. It replaces the 18 Oct draft that
had each lane build its own part in parallel.

**Why it changed.** Most of the build depends on the step before it:
- the contracts come first;
- the sandbox and data need the contracts;
- the enumerator needs the summaries;
- the agents need the enumerator, the filter and the gate;
- the checker and arms need all of it.

Five lanes in parallel would mostly wait on each other. So the build is **one guided solution in
16 steps**:
- **Kenneth replays** every step into this repo, one branch and pull request per step.
- **Each lane owns a section of the steps for review**: you read your steps before or while they
  are replayed, review the PR on GitHub, and raise changes. You also present that part in the
  deck and Q&A.
- **The team agrees changes centrally** before they are made. A change to a contract between
  parts needs the lanes that use it to agree.

**Claiming a lane.** Reply in the team chat with the lane you want. Kenneth records the owner
below and takes whichever lane is left. Terms follow [brief §0](brief.md#0-definitions). Current
state and next actions are in [HANDOFF.md](HANDOFF.md).

---

## Lanes: what each one reviews

| Lane | Section of the build | Steps you review | Owner |
|---|---|---|---|
| L1 Platform and harness | The uv project and settings, the sandbox, the model client and runner, Docker, the sweep command | 01 Skeleton · 02 (tools and result contracts) · 04 Sandbox · 07 Runner and Docker · 16 Sweep rehearsal | |
| L2 World and data | The scenario format, the five hand-checked scenarios, the corpus, the generator, the dev and held-out sets | 02 (scenario contract) · 03 Scenarios and corpus · 12 Generator · 15 Held-out freeze | |
| L3 Personal agent and privacy | The availability summary and constraints, the personal agent, the privacy filter, the privacy probes | 02 (availability and constraints contracts) · 08 Personal agent · 09 Privacy filter · 15 (probes) | |
| L4 Coordinator and control | The enumerator, the approval gate, the coordinator agent | 05 Enumerator · 10 Approval gate · 11 Coordinator agent | |
| L5 Evaluation and baselines | The checker, the baselines and ablation, the metrics, the sweep results | 06 Checker and free/busy · 13 Metrics and single-call baseline · 14 Shared-context ablation | |
| Lead (Kenneth, on top of a lane) | Replays every step, merges, runs the gates, assembles the deck | all | Kenneth |

## How a review works

1. The steps live in a **private guide repo**, `code-vibes-only/cs621-scheduler-guide`, where
   every team member is a collaborator (accept the invite). Its `main` is protected: raise
   changes as issues there, don't push. Each step:
   - gives every file in full and explains every line;
   - shows the real output to expect;
   - ends with "Share for review": the questions the review must answer.
2. When Kenneth opens a step's pull request here, the lane owner reviews it on GitHub. Check the
   code against the step, and answer the step's review questions in the PR thread.
3. A change you want goes in as an issue on the guide repo, or a PR comment. Small fixes inside one
   lane are fine to agree in the PR. Anything that changes what another lane uses waits for that
   lane's owner.
4. Kenneth merges after your approval, and tags the gates.

Reviews within about 24 hours, and the same day in the 24 hours before a gate.

## Contracts (frozen at G1)

These are what one part hands the next. They are typed models under `scheduler/contracts/`, and
the guide repo's `contracts.md` summarises them.

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
| G1 | Mon 19 Oct | `v0.1.0` | Steps 01–07 merged: contracts frozen; tests and the Docker run pass from a clean clone; 5 hand-checked scenarios; the free/busy baseline and checker agree with the hand-written answers; `gpt-5-mini` checked and a first cost measured |
| G2 | Thu 22 Oct | `v0.2.0` | Steps 08–13 merged: personal agents + coordinator agent end to end on the dev set; every metric reported as mean ± sample SD over 3 runs; the single-call baseline runs |
| G3 | Sat 24 Oct | `v0.3.0` | Steps 14–15 merged: the shared-context ablation runs; held-out set frozen with the privacy probes; promotion threshold fixed |
| Sweep | Tue 27 Oct | — | Step 16 merged; each team member runs their held-out subset (`--sweep N`, see README) on their own key and commits the results |
| Done | Fri 30 Oct | — | Deck and demo complete; 31 Oct – 2 Nov is buffer |

**If we slip:** stretch items go first, then the Streamlit UI (keep the CLI), then the social-group
family. A slipped gate moves the work that depends on it, not the dates promised in brief §14.

## Budget

- Building the guided solution spends at most USD 2 of Kenneth's key.
- Replaying the steps costs a few dollars of Kenneth's key: step 13's dev sweep is the largest, and
  it states its expected cost before you run it.
- The held-out sweep is split by scenario subset: every team member runs their 6 scenarios × arms
  b, c and d × 3 runs (54 episodes) on their own key.

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
| 3 | Architecture: personal agents, availability summary, coordinator agent | L1, L3, L4 |
| 4 | Autonomy level per action class (A0–A4) and per agent | L4 |
| 5 | Datasets and how they were generated | L2 |
| 6 | Eval sets and metrics | L5 |
| 7 | Baselines and ablation | L5 |
| 8 | Results: slot quality and pass rate against the baselines | L5 |
| 9 | Results: privacy, isolation against shared context | L3, L5 |
| 10 | Autonomy evidence: which action classes clear the threshold | L4, L5 |
| 11 | User experience: how participants' and organisers' work changes | Lead, L3 |
| 12 | Failure modes, gaps, how we handled them, and future work | All |
