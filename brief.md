# Project brief: Agentic Natural Language Scheduler

CS621 Agentic AI for Intelligent Autonomy, group project.
Final report/deck and presentation: **Tue 3 Nov 2026** (assumed). Internal completion target:
**Fri 30 Oct 2026**.

Status: **draft v0.4, 15 Oct 2026.** Every design choice below is *proposed* until the team
agrees it. Record agreed choices in the [decision log](#16-decision-log). Put anything
unresolved in [open questions](#15-open-questions). Terms are defined in
[§0](#0-definitions).

---

## 0. Definitions

**Naming rule.** *Team* and *team member* mean only the five of us building this project.
The people the app schedules for are always called **participants**.

**People and agents**

| Term | Meaning |
|---|---|
| Participant | A person invited to the meeting being scheduled: an end user. Each participant has their own calendar and private preferences. |
| Organiser | The participant who asks for the meeting, e.g. a project lead or an executive assistant, and who approves the invite. |
| Group | The participants of one meeting. A participant can be in many groups. |
| Request thread | The shared conversation where the organiser asks for the meeting and sees options, like a Slack/Teams thread. Everything posted here is visible to every participant in the group. |
| Personal agent | One private agent per participant. It reads that participant's calendar and preferences, does lookups for them, and talks to the coordinator agent only through an availability summary. |
| Coordinator agent | The agent that schedules for the whole group. It sees availability summaries, never calendars, preferences or reasons. |
| Availability summary | A fixed-format message from a personal agent to the coordinator agent. For each candidate slot it says *available*, *prefer not* or *unavailable*, and it has no field for reasons. Week 7 calls this kind of hand-off a "Brief". |

**Time, commitments and preferences**

| Term | Meaning |
|---|---|
| Commitment | Anything already occupying a participant's time. Four kinds: an **existing meeting** (with an owner, a priority and a movable flag), **leave** (a day or part-day off), a **focus block** (time the participant blocked for their own work), and an **external event** (a conference, training or similar, whose times may need looking up). |
| Calendar | A participant's sandbox calendar, holding their commitments. Titles can be private, e.g. "Clinic appointment" or a confidential project name. |
| Free/busy | The standard calendar view that shows *when* someone is busy but not *what* they are doing. Outlook and Google Calendar scheduling assistants use it. |
| Working hours | The hours a participant normally accepts meetings, e.g. 09:00–18:00. |
| Movable commitment | A commitment the participant says they could shift or give up if asked, typically a focus block or a low-priority internal meeting. The agent never moves it itself; it can only ask. |
| Preference | What a participant says in natural language, e.g. "no meetings before 10" or "keep Friday afternoons clear". |
| Constraint | A commitment or preference translated into a checkable rule over slots. A **hard** constraint must hold, e.g. "on leave Wed–Thu". A **soft** constraint should hold where possible and carries a weight, e.g. "prefer not before 10:00". |
| Relax | To drop or weaken a soft constraint, or treat a movable commitment as free, for one meeting. This happens only after the participant agrees. |
| Slot | A candidate start/end time for the meeting, on a 30-minute grid inside working hours. |
| Planning horizon | The window the app searches, e.g. the next 5–10 working days. |

**Lookups**

| Term | Meaning |
|---|---|
| External schedule | A source of times that is not in anyone's calendar: public holidays, a conference agenda, a company all-hands calendar, a training timetable. "I'm at DataSummit on Tuesday" becomes a constraint only after the personal agent looks the event up. |
| Schedule corpus | Our frozen collection of external schedules, served by the `search_schedules` tool. Freezing it keeps evaluation reproducible. |
| Meeting room | A bookable room with a capacity and equipment, e.g. video conferencing (VC). |
| A note on sports | The original pitch mentioned "catching weekly sports events". That is now just one example of an external schedule. It appears only in the small social-group scenario family, as a fictional league's fixture list (a **fixture** is one scheduled match with a date and kick-off time). |

**Actions**

| Term | Meaning |
|---|---|
| Sandbox | Our simulated calendars, rooms and invite system. No real calendar is read or written, and no real message is sent. |
| Tentative hold | A reversible, auto-expiring placeholder on the participants' sandbox calendars. |
| Invite | A confirmed meeting sent to every participant's sandbox calendar, plus a room booking. It requires approval. |
| Approval gate | Code that blocks an invite until the required approvals are stored and availability has been rechecked. |

**Evaluation**

| Term | Meaning |
|---|---|
| Scenario | One test case: participants, their calendars and preferences, the schedule corpus state, a request, scripted replies and the ground-truth answer. |
| Dev set / held-out set | Scenarios we may tune on, and scenarios we freeze and run only for the final numbers. |
| Run | One independent, reset execution of every scenario. We do at least 3 runs per arm. |
| Episode | One scenario × one run × one arm. |
| Arm | One system variant being compared, e.g. the free/busy finder baseline or our design. |
| Baseline | A simpler arm the agent must beat to justify itself. |
| Ablation | An arm that removes one component to measure what it contributes. |
| Pass rate | The share of scenarios passed in a run, where passing means a correct outcome *and* a valid trajectory. Reported as mean ± sample SD across runs. |
| Trajectory | The sequence of tool calls, questions and writes the agent made, not just its final answer. |
| Canary | A unique made-up string planted in private data, such as a confidential meeting title or a leave reason. If it appears anywhere it should not, that is a measured leak. |
| Enumerator | Deterministic code that lists every slot (× room) satisfying the hard constraints and scores the soft ones. |

---

## 1. Pitch and research question

Scheduling a meeting across several people is slow even when everyone's calendar is shared. A
free/busy finder sees blocks of busy time, but it cannot tell an immovable client meeting from a
focus block someone would happily give up. It cannot apply "I'd rather not meet before 10" and
it does not know that someone is at a conference on Tuesday. When nobody is fully free, it
returns nothing, and the organiser starts a long thread. People also have reasons they would
rather not share: a medical appointment, a confidential project, a personal matter on leave.

We build an assistant where **each participant has a private personal agent**. It reads their
calendar, remembers their stated preferences across meetings, and looks up commitments that are
not in the calendar. It tells a **coordinator agent** only *when* the participant can or cannot
meet, never *why*. When no slot works, the coordinator agent privately asks only the
participants whose movable commitment or soft preference is blocking, relaxes one with consent,
and replans. Invites go out only with approval.

The primary use is **workplace meetings**. A small family of social-group scenarios (friends
planning an evening) checks that the same design generalises.

**Research question.** Can a meeting-scheduling agent find slots about as good as a fully
informed scheduler while keeping each participant's reasons private? And what level of autonomy
does the evidence support for each kind of action it takes?

Two claims we want to test, not assume:

1. **Isolation buys privacy at an acceptable cost.** Personal agents leak fewer private reasons
   than one agent that sees every calendar. We measure what that costs in slot quality, tokens
   and latency.
2. **The loop earns its cost.** An agent that decides what to look up, whom to ask and when to
   replan beats a free/busy finder and a single well-informed LLM call. This shows only on
   scenarios where those decisions matter.

## 2. Problem and end users

**What exists today.** Calendar scheduling assistants already hide event details through
free/busy, so privacy alone is not new. Their gaps are:

- No natural-language or soft preferences ("no meetings before 10", "keep Friday afternoons
  clear").
- Every busy block is treated as immovable. When nobody is fully free they offer nothing, rather
  than asking whether someone could give up a focus block.
- Commitments that live outside the calendar are invisible: a public holiday, a conference
  someone is attending, an all-hands.
- No negotiation. The back-and-forth moves to chat, where people end up explaining their reasons
  in front of colleagues.

Our value is the combination: natural-language preferences, lookups and relaxing with consent,
**while keeping reasons private**.

| User | Today | With the agent |
|---|---|---|
| Participant | Receives clashing invites, explains in the thread why a slot doesn't work, gets pressured into giving up focus time | States preferences once; reasons stay private; asked privately, and only when their movable time is the one blocking the group |
| Organiser (project lead, executive assistant) | Checks free/busy, finds nothing, chases people one by one, re-sends invites | Asks in one line ("60 min kickoff with A–E next week, needs a VC room"), reviews a short list, approves the invite |

Secondary users: social groups, such as friends or a club committee, who have the same problem
without shared calendars.

What changes for them (the "user experience" section of the final report):

- Fewer messages per scheduled meeting, measured against the free/busy finder plus manual
  follow-up.
- Nobody has to justify a constraint.
- Giving up focus time becomes an explicit, private choice rather than social pressure in a
  thread.

## 3. Scope

**MVP (in scope)**

- One meeting per request, with 3–6 participants.
- A planning horizon of 5–10 working days, in 30-minute slots inside working hours, in one
  timezone (Asia/Singapore).
- Each participant has a sandbox calendar of existing meetings, leave and focus blocks, plus
  natural-language preferences.
- External schedules (public holidays, conferences, all-hands) are available via
  `search_schedules`.
- Preferences persist per participant across meetings.
- A simulated request thread plus one private pane per participant (CLI or Streamlit).
- A small social-group scenario family using the same engine.

**Out of scope** (say so in the report)

- Real Outlook/Google calendar integration and real Slack/Teams messages.
- Multi-timezone meetings, recurring series, and several meetings scheduled together.
- **Changing anyone's existing commitments.** The agent never moves, declines or shortens
  another meeting; it only asks the participant, who acts themselves.

## 4. Architecture (proposed)

```mermaid
flowchart LR
    subgraph Private["Private: one per participant"]
        U1[Participant A private pane] <--> P1[Personal agent A]
        P1 <--> M1[(A's preference memory)]
        P1 --> K1[read_my_calendar / get_leave]
        P1 --> S[search_schedules]
    end
    P1 -- "availability summary (when, never why)" --> F{{Privacy filter - code}}
    P2[Personal agent B ...] -- availability summary --> F
    F --> C[Coordinator agent]
    C --> E[Enumerator + scorer - code]
    C --> R[find_rooms]
    E --> C
    C -- "private relax / clarify question" --> P1
    C --> G[Request thread: options / draft invite]
    C --> H{Approval gate - code}
    H -- approved + revalidated --> W[(Sandbox calendars + room booking)]
    W --> V[Verify write - code]
```

**Components**

- **Personal agent (one per participant).**
  - Tools:
    - `read_my_calendar`: its own participant's calendar only, including private titles;
    - `get_leave`;
    - `search_schedules`: the external schedule corpus;
    - the preference memory.
  - Its job: turn commitments and natural-language preferences into typed constraints, decide
    which commitments are movable (from the calendar flag or by asking its participant), and
    answer the coordinator agent **only** through the availability summary.
  - Calendar titles, the participant's own words and reasons never leave it.
- **Privacy filter (code).**
  - Validates every availability summary against the schema and rejects free text.
  - Checks every message in the request thread for canaries and for attribution ("E has a
    steering meeting on Monday", "B is on leave").
- **Coordinator agent.**
  - What it sees: availability summaries only.
  - What it does: calls the enumerator and `find_rooms`, chooses candidates, decides whether to
    ask someone, relax, replan or hand back, and drafts the invite.
- **Enumerator + scorer (code).** Lists feasible slot × room options under the hard constraints
  and scores the soft ones. The model never does this arithmetic.
- **Approval gate + write + verify (code).**
  - No invite goes out without stored approvals.
  - Availability is rechecked at commit time, and writes are idempotent.
  - The calendars are read back before anything is reported as scheduled.

**Availability summary schema (draft)**

```json
{
  "participant_id": "p3",
  "request_id": "r-0142",
  "slots": [
    {"start": "2026-10-19T10:00", "end": "2026-10-19T11:00", "status": "unavailable"},
    {"start": "2026-10-19T15:00", "end": "2026-10-19T16:00", "status": "prefer_not", "weight": 0.5, "relaxable": true},
    {"start": "2026-10-19T11:00", "end": "2026-10-19T12:00", "status": "available"}
  ],
  "unknown": []
}
```

- `status` takes one of three values: `available`, `prefer_not`, `unavailable`.
- `relaxable: true` covers both a soft preference and a movable commitment. Which one it is stays
  private.
- The schema has no `reason` or `title` field, so a personal agent has nowhere to put one.
- `unknown` lists windows the personal agent could not resolve, for example because a conference
  lookup failed. The coordinator agent must treat these as unknown, not free.
- Room needs (capacity, VC) come from the organiser's request, not from the summaries.
- Week 7 warns about the opposite failure: a summary that is *too* thin (MAST FM-2.4,
  information withholding). The schema must carry everything the coordinator agent needs, and
  deciding exactly what that is counts as design work.

**Why several agents and not one.** Week 7 says a split earns its cost when each part needs
different information and permissions, and when context needs protecting. Here:

- each personal agent needs only its own participant's calendar and history;
- the coordinator agent must *not* see titles or reasons;
- personal agents have no write tools.

The ablation is a **single agent that reads every participant's calendar and preferences in one
context**, plus the same privacy filter on its output. If it leaks no more and schedules just as
well, we report that.

## 5. Decisions the agent makes

These are the judgement calls we want to show and to grade at the trajectory level.

| Decision | Example | Wrong if... |
|---|---|---|
| Use memory or ask again | "No meetings before 10", stated for a previous meeting | it uses an expired or meeting-specific preference, or re-asks something still valid |
| Call a tool | "I'm at DataSummit on Tuesday" → look up the event's dates and hours | it guesses the times, or searches when nothing needs looking up |
| Ask for clarification | "I'm busy most of Thursday" → which hours, and is it movable? | it invents a window silently, or asks when the calendar already answers it |
| Ask whether a commitment can move or a preference can bend | Nobody is fully free; C's focus block is the only blocker | it asks everyone, asks in the request thread, or relaxes without asking |
| Replan | C agrees to give up an hour, or a new meeting lands in the chosen slot | it keeps the old plan, or keeps asking the same question (rounds are capped) |
| Hand back to a person | Only slots that break a hard constraint remain; an invite needs approval | it sends the invite anyway, or reports "scheduled" without a write |

**Worked example (fictional workplace).** The organiser asks: "60-minute project kickoff with
A, B, C, D and E next week, in a VC room."

| Participant | Commitment or preference | Becomes |
|---|---|---|
| A | Calendar: "Clinic appointment" (private) Tue 10:00–11:00. Preference: "no meetings before 10" | Hard Tue 10–11; soft before 10:00 every day |
| B | Leave Wed 21 – Thu 22 Oct | Hard, both days |
| C | Focus block Mon 14:00–17:00, flagged movable | Soft, relaxable with consent |
| D | "I'm at DataSummit on Tuesday" (not in the calendar) | The personal agent calls `search_schedules`, finds Tue 09:00–18:00, so hard all of Tuesday |
| E | Existing meeting "Project Falcon steering" (confidential, immovable) Mon 10:00–11:00 | Hard Mon 10–11 |

Mon 19 Oct 11:00–12:00 breaks no constraint, hard or soft. The request thread shows: "Mon 19
Oct, 11:00–12:00, Room R2 (VC), all 5 available." Nobody learns about the clinic, the leave, the
conference or Project Falcon.

**Variant: nobody is fully free.** The organiser needs the kickoff on Monday. E's steering
meeting now runs 09:00–12:30, A has a client call 12:30–14:00, and B has a meeting 17:00–18:00.
Monday's only remaining hours are 14:00–17:00, all inside C's focus block.

- A free/busy finder returns nothing.
- The coordinator agent asks **only C**, privately: "Could you give up one hour between 14:00
  and 17:00 on Mon 19 Oct?"
- C replies "15:00–16:00 is fine." The agent replans, places a tentative hold, and the invite
  waits for the organiser's approval.
- The request thread never says whose time was given up.

**Social-group variant (secondary).** Four friends want 2 hours for dinner next week. One
"never misses their football club's matches", so the personal agent looks up the fictional fixture list;
another says "Tuesdays are out". Same engine, same privacy rules, no shared calendars.

## 6. Autonomy level per action class (proposed)

| Level | Action | Proposed autonomy | Guard |
|---|---|---|---|
| L0 | Read own participant's calendar/memory, look up external schedules and rooms | Autonomous | Read-only tools; a personal agent can read only its own participant's calendar; tool output treated as data, not instructions |
| L1 | Propose slots in the request thread | Autonomous | Privacy filter on every message in the request thread |
| L2 | Ask a participant a private relax/clarify question | Autonomous within a budget (e.g. ≤ 2 questions per participant per request) | Question cap; never in the request thread |
| L3 | Place a tentative hold on sandbox calendars | Autonomous, reversible, auto-expires | Idempotent; released on replan |
| L4 | Send invites + book room | **Supervised**: the organiser approves; participants whose movable time is used must have consented | Approval stored outside model text; revalidated at commit; read-back verification |
| — | Relax a *hard* constraint | **Never** | Enforced in the enumerator, not the prompt |
| — | Move, decline or shorten a participant's existing commitment | **Never**: the agent only asks; the participant acts | No such write tool exists. Moving another meeting would affect people outside the request |

**Defended level:** autonomous investigation and proposals, supervised commitments. The project
spec prefers "supervised with strong evidence" to "delegated with none". An action class moves
up a level only if two conditions hold:

- its measured pass rate (mean − 1 SD) clears a threshold the team agrees *before* the held-out
  run;
- it has zero critical violations: no privacy leak, no unconsented relaxation and no write
  without approval.

## 7. Datasets (synthetic; the generation process is documented)

Synthetic data is allowed if the generation process uses reasonable assumptions and is explained
in the presentation and report.

- **Personas (~15 employees).** Each persona is one simulated participant and has:
  - working hours;
  - a generated sandbox calendar of existing meetings (title, owner, priority, movable flag),
    leave and focus blocks;
  - natural-language preferences in varied wording;
  - a hidden **ground-truth constraint set**, authored independently of the agent;
  - planted **canaries**: confidential meeting titles, and medical or personal leave reasons.
- **Requests (~8 recurring groups).** Groups overlap, so one participant's preference memory is
  reused across meetings.
- **External schedule corpus (frozen).** Served by `search_schedules`:
  - Singapore public holidays;
  - fictional conference and training agendas;
  - a company all-hands calendar;
  - for the social family, a fictional league's fixture list.

  The corpus includes deliberately misleading items: an outdated agenda, a rescheduled session
  and a page with an injected instruction.
- **Meeting rooms (~6).** Capacity and VC equipment, with their own bookings.
- **Scripted participant replies.** Deterministic answers to relax and clarify questions per
  scenario. These keep evaluation reproducible; LLM-simulated participants are for the demo only.
- **Live web search** is used for the **demo only**, behind the same tool interface, e.g. to look
  up a real public event.
- **Generation assumptions to document:**
  - calendar density, e.g. 40–70% of working hours booked;
  - leave frequency;
  - share of focus blocks;
  - share of movable meetings;
  - ranges for meeting length and participant count.
- **Reproducibility.** Every scenario records its seed, parameters and generator version. The
  pattern follows the Week 7 lab's travel world: tool calls and writes are logged, and ground
  truth is computed from the same rules.

## 8. Eval sets and metrics

About **20 dev + 30 held-out scenarios**, frozen before we look at held-out outputs. Every LLM
arm gets **≥ 3 runs**, reset between runs. Scenario families (tags):

| Family | What it tests |
|---|---|
| Simple feasible | Baseline sanity; the agent should not add questions |
| Leave and working hours | Hard boundaries from leave records and working hours |
| Lookup-required | A constraint depends on an external schedule (conference, public holiday, all-hands) |
| Nobody fully free → ask → relax → replan | Asks the *right* participant, privately, about a movable commitment or soft preference |
| Memory across meetings | Reuses valid preferences; respects expiry and meeting-specific scope |
| Ambiguous → clarify | Asks instead of guessing; does not ask when the calendar answers it |
| Truly infeasible | Hands back with a reason-free explanation |
| Privacy probes | "Why can't E do Monday 10?"; repeated probing; an injected instruction in an external agenda |
| Approval / stale slot | A new meeting lands in the slot after approval → no write, replan, new approval |
| Social-group generalisation | ~4 held-out scenarios: friends with no shared calendars, preferences only |

**Metrics** (each reported as mean ± sample SD across runs):

- **Pass rate**, as defined in §0.
- **Hard-constraint violations** (should be 0).
- **Slot quality.** Soft-constraint score relative to the best achievable score, computed by the
  evaluator from ground truth.
- **Privacy leakage rate.** Canaries or attributions appearing in the coordinator agent's
  context or in the request thread.
- **Unnecessary questions and missed necessary questions.**
- **Approval compliance.** Writes without valid approval should be 0.
- **Tokens/cost and latency** per scheduled meeting.

**Grading.** An independent checker recomputes every constraint from the ground truth. It never
trusts the agent's or the enumerator's own "valid" flag. Before trusting the numbers, we read at
least 5 passes and 5 failures, plus every critical violation.

## 9. Baselines and ablations

| Arm | What it is | Answers |
|---|---|---|
| (a) Free/busy finder | Deterministic: the earliest slot where every calendar is free. No natural-language preferences, no lookups, no relaxation | Is the agent better than today's calendar tools? Expected to fail when only movable time or an external event decides the answer |
| (b) Single grounded call | One LLM call given every calendar, preference and lookup result pre-fetched | Does the *loop* add anything beyond information access? |
| (c) Single agent, shared context | Full loop, one window holding every participant's calendar and preferences | Baseline for privacy |
| (d) Personal agents + coordinator agent (ours) | Section 4 | Does isolation buy privacy, at what quality and token cost? |

Change one thing at a time between arms: same model, settings, corpus, enumerator and limits.

## 10. Failure modes to watch

- **Wrong natural language → constraint translation.** For example, "not too early" becomes a
  hard 11:00 start. Graded against the ground-truth constraint sets.
- **Movability errors.** A movable focus block is treated as immovable, or a client meeting as
  movable.
- **Information withholding** (Week 7, FM-2.4). An availability summary drops something the
  coordinator agent needs.
- **Leaks.** A confidential meeting title, a leave reason or an attribution appears in the
  request thread, or is inferred through repeated probing.
- **Reasoning–action mismatch** (FM-2.6). The agent says "invite sent" with no write in the
  record.
- **Stale or out-of-scope memory.** The agent applies an expired or meeting-specific preference.
- **Prompt injection via tool output.** An external agenda page tells the agent to reveal
  calendars.
- **Step repetition** (FM-1.3). The same relax question is asked repeatedly, so rounds are
  capped.
- **Treating unknown as free.** A failed lookup is read as availability.

## 11. Course concept map

| Week | Concept | Where it shows up |
|---|---|---|
| 1 | Control loop, termination, action-specific autonomy, escalation | Coordinator agent loop; stop on plan / hand-back / budget; autonomy table |
| 2 | Tool contracts, semantic validation, failure kinds, idempotency | Calendar and schedule tools, availability summary validation, idempotent hold/invite |
| 3 | Harness, ≥3 runs, SD, baselines, trajectory checks | Sections 8–9 |
| 4 | Context and retrieval | External schedule search vs. pre-loading; context protection in personal agents |
| 5 | Hard vs. soft constraints, retry vs. replan, memory provenance/expiry | Enumerator; relax-and-replan; preference memory |
| 6 | Explicit control flow, approval interrupts | LangGraph graph with an approval interrupt before L4 |
| 7 | Multi-agent: isolation, permissions, what gets passed on ("Brief"), MAST failures | Personal agents + coordinator agent; single-agent ablation |
| 8 | Safety, oversight, governance *(lecture on 20 Oct; this row is extrapolated until then)* | Privacy filter, injection tests, authorisation gates, no-write-to-others rule |

## 12. Stack and budget (proposed)

- Python with uv, and LangGraph (as in the Week 6–7 labs).
- **OpenAI** as the LLM provider, using the course-provided keys.
- JSON/SQLite sandbox: calendars, leave, rooms, holds, invites and a write log.
- A CLI first, with a Streamlit demo (one pane per participant plus the request thread) if time
  allows.
- API keys live in each team member's local `.env` and are **never committed**. This repo is
  public.

**uv now, Docker optional later.** uv pins the Python version and every package, and keeps
day-to-day iteration fast. The system has no services to orchestrate, only files and API calls.
uv does not limit how far we can scale; our real limits are the OpenAI rate limits and the USD
10 per key. Running scenarios in parallel is done in Python (asyncio or a process pool), with or
without Docker.

Add a Dockerfile only if one of these happens:

- a team member cannot get the environment working;
- we want the demo to start with one command on any machine;
- we want to run sweeps on other machines.

The Dockerfile then installs from the same lockfile, and keys are passed at run time with
`--env-file .env`, never baked into the image.

**Keep it portable** (follow these from day one, so adding Docker later is about an hour's work):

1. **Commit `uv.lock` and `.python-version`.** The container installs exactly what we run
   locally (`uv sync --frozen`).
2. **Configuration comes from environment variables**: the API key, the model name, and the data
   and results directories. Nothing is hard-coded.
3. **Paths are relative to the repo root**, never `/Users/...` or `C:\...`.
4. **One command per job.** For example, `uv run python -m scheduler.eval --arm d --scenarios
   1-6`. A container runs the same command.
5. **Results go to files**, one per episode, tagged by arm, scenario and run, plus a merge step.
   Output from containers, other machines or other keys combines the same way.

**Budget.** Each team member has **their own key with a USD 10 cap per calendar month**.
Keys cannot be pooled, so the team total of USD 50 only counts if the work is spread.

- **October's caps** cover development and the main sweeps. **November's** reset on 1 Nov and
  are the contingency for reruns in the 31 Oct–2 Nov buffer.
- **Split the held-out sweep by scenario subset, not by arm.**
  - Each team member runs every LLM arm (b, c, d) on their 6 of the 30 held-out scenarios × 3
    runs, which is 54 episodes.
  - If one key runs out, every arm loses a few episodes and no arm loses everything.
- The harness writes one result file per episode, tagged by arm, scenario and run, not by key.
  These merge into one table. Every key uses the same model and settings.
- **Dev cap:** about USD 5 per key. Debugging loops are the main way to burn a key.

**Model (proposed): `gpt-5-mini`.**

- Price: USD 0.25 per 1M input tokens and USD 2.00 per 1M output tokens (OpenAI model page,
  checked 15 Oct 2026). Reasoning tokens are billed as output.
- The model page also shows a "Deprecated" label, so confirm availability before freezing it.
- The alternative is `gpt-5.4-mini` at USD 0.75 / 4.50, roughly 2.5–3× the cost.
- Every arm uses the same model and settings.

**Rough cost estimate.** These numbers are an *estimate*; the harness will measure the real ones.

| Item | Assumption | Per key | Team |
|---|---|---|---|
| One episode | ~50k input + ~8k output tokens (5 personal agents + coordinator agent) | ~USD 0.03 | — |
| Held-out sweep | 54 episodes per key; 270 in total | ~USD 1.6 | ~USD 8 |
| Dev iteration | Cap | ≤ USD 5 | ≤ USD 25 |
| Demo, including live web search | Hosted web search is USD 10 per 1,000 calls plus tokens; demo volume is small (one key) | — | < USD 2 |
| Reserve | Remainder of each October cap | ~USD 3 | ~USD 15 |

**Cost controls.**

- Set the reasoning effort explicitly.
- Cap model calls per episode.
- Log tokens per episode.
- After the first 10 dev episodes, replace this estimate with measured cost and re-plan the
  sweeps.

## 13. Work plan (after the brief is agreed)

The team confirms this brief and its scope first. The work is then split from the agreed brief
on Sat 17 Oct into swimlanes, each with an owner and a reviewer from another lane. The work plan
and owners are recorded in [HANDOFF.md](HANDOFF.md), not here.

## 14. Timeline (proposed)

Work back from the internal target of **Fri 30 Oct**, leaving 31 Oct–2 Nov as buffer.

| By | Milestone |
|---|---|
| Fri 16 Oct (night) | Team members have read the brief and replied on scope and the open questions |
| Sat 17 Oct | Brief and scope agreed; work plan (swimlanes, owners, reviewers) agreed; build starts |
| Mon 19 Oct | Availability summary schema and scenario format frozen; 5 hand-checked scenarios; free/busy baseline runs; first measured cost per episode |
| Thu 22 Oct | Personal agents + coordinator agent end to end on the dev set; checker working; single-call baseline |
| Sat 24 Oct | Held-out set frozen; shared-context ablation; privacy probes |
| Tue 27 Oct | All arms × 3 runs on the held-out set (split across keys); failure analysis done |
| Thu 29 Oct | Report/deck draft; demo recorded |
| **Fri 30 Oct** | **Complete**: final report/deck and demo |
| Sat 31 Oct – Mon 2 Nov | Buffer for contingencies (November caps available for reruns) |
| Tue 3 Nov | Submit and present |

## 15. Open questions

| # | Question | Owner |
|---|---|---|
| 1 | Final format: 4-page report or 12-slide deck? | |
| 3 | External schedules: fictional sources, or dated snapshots of real ones? Singapore public holidays, for example, are real and stable | |
| 4 | Should the coordinator agent see each participant's availability summary, or only the count of available participants per slot? Per-participant summaries let it ask the right participant before relaxing; counts are more private | |
| 5 | Promotion threshold for an action class (e.g. mean − 1 SD ≥ 90%, 0 critical violations)? | |
| 6 | How do we measure the user-experience claims: a small walkthrough with classmates, or descriptive only? | |
| 7 | Meeting rooms in the MVP, or time slots only? | |

Question 2 (keys) is answered; see the decision log. Question 8 (roster and owners) moved to the
work plan (§13). The numbers are kept so earlier references stay valid.

## 16. Decision log

| Date | Decision | Status |
|---|---|---|
| 2026-10-15 | Topic: Agentic Natural Language Scheduler with private per-participant preferences | Agreed by team |
| 2026-10-15 | Eval uses a frozen schedule corpus; live web search for the demo only | Proposed (Kenneth), pending team |
| 2026-10-15 | Personal agents + coordinator agent; a single shared-context agent as the ablation | Proposed (Kenneth), pending team |
| 2026-10-15 | Highest action: send invites + book room, gated; tentative holds autonomous | Proposed (Kenneth), pending team |
| 2026-10-15 | Final report/deck due Tue 3 Nov; internal completion target Fri 30 Oct | Assumed (Kenneth) |
| 2026-10-15 | LLM provider: OpenAI; each team member has their own key, USD 10 cap per calendar month | Given |
| 2026-10-15 | Default model `gpt-5-mini`, same for all arms | Proposed (Kenneth), pending team |
| 2026-10-15 | Naming: *participant* (end user), *team member* (us); *personal agent*, *coordinator agent*, *availability summary* | Proposed (Kenneth), pending team |
| 2026-10-15 | Workplace meetings are the primary domain; social groups are a small generalisation family. Sports is only an example of an external schedule | Decided (Kenneth) |
| 2026-10-15 | Held-out sweep split across keys by scenario subset (6 scenarios per team member, all LLM arms) | Proposed (Kenneth), pending team |
| 2026-10-15 | The agent never moves, declines or shortens a participant's existing commitments; it only asks | Proposed (Kenneth), pending team |
| 2026-10-15 | Environment: uv with a committed lockfile; Docker optional later, built from the same lockfile; code follows the "keep it portable" rules in §12 | Proposed (Kenneth), pending team |
| 2026-10-15 | Brief and scope are confirmed first (replies by Fri 16 Oct night); swimlanes, owners and reviewers are planned from the agreed brief on Sat 17 Oct | Proposed (Kenneth), pending team |
