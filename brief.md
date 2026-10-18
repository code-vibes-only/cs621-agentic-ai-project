# Project brief: Agentic Natural Language Scheduler

CS621 Agentic AI for Intelligent Autonomy, group project.
Final deck (12 slides) and presentation: **Tue 3 Nov 2026** (assumed). Internal completion
target: **Fri 30 Oct 2026**.

Status: **draft v0.5, 18 Oct 2026.** It records the decisions from the team sync on Sat 17 Oct,
which settled GitHub issues #1–#8 and the open questions (discussion in
[issue-review.md](issue-review.md)). Every row in the [decision log](#16-decision-log) is now
agreed or overturned. Changing a decision needs the team's agreement and a new row in the
decision log. Put anything unresolved in [open questions](#15-open-questions). Terms are defined
in [§0](#0-definitions).

---

## 0. Definitions

**Naming rule.** *Team* and *team member* mean only the five of us building this project.
The people the app schedules for are always called **participants**.

**People and agents**

| Term | Meaning |
|---|---|
| Participant | A person invited to the meeting being scheduled: an end user. Each participant has their own work and personal calendars, private preferences, and an attendee role in each meeting. |
| Organiser | The participant who asks for the meeting, e.g. a project lead or an executive assistant. The organiser sets each participant's attendee role and approves the invite. |
| Attendee role | Set by the organiser in the request. A **required** participant must attend: a slot one of them cannot make does not work. An **optional** participant's availability counts as soft: it improves a slot's score but never blocks it. |
| Group | The participants of one meeting. A participant can be in many groups. |
| Request thread | The shared conversation where the organiser asks for the meeting and sees options, like a Slack/Teams thread. Everything posted here is visible to every participant in the group. |
| Personal agent | One private agent per participant. It reads that participant's work and personal calendars and preferences, does lookups for them, and talks to the coordinator agent only through an availability summary. |
| Coordinator agent | The agent that schedules for the whole group. It sees each participant's availability summary, never calendars, preferences or reasons. |
| Availability summary | A fixed-format message from a personal agent to the coordinator agent. For each candidate slot it says *available*, *prefer not* or *unavailable*, and it has no field for reasons. Week 7 calls this kind of hand-off a "Brief". |

**Time, commitments and preferences**

| Term | Meaning |
|---|---|
| Commitment | Anything already occupying a participant's time. Five kinds: an **existing meeting** (with an owner, a priority and a movable flag), **leave** (a day or part-day off), a **focus block** (time the participant blocked for their own work), an **external event** (a conference, training or similar, whose times may need looking up), and a **personal event** (an entry on the personal calendar, e.g. a school pickup, an evening class or a medical appointment). |
| Calendar | Each participant has two sandbox calendars: a **work calendar** and a **personal calendar** (family, study, medical). Only their own personal agent reads them. Titles can be private, e.g. "Clinic appointment" or a confidential project name. |
| Free/busy | The standard calendar view that shows *when* someone is busy but not *what* they are doing. Outlook and Google Calendar scheduling assistants use it. |
| Working hours | The hours a participant normally accepts meetings, e.g. 09:00–18:00. |
| Movable commitment | A commitment the participant says they could shift or give up if asked, typically a focus block or a low-priority internal meeting. The agent never moves it itself; it can only ask. |
| Reachable if urgent | A flag a participant can set on a leave period. Leave is a hard constraint by default. Leave marked reachable if urgent is treated like a movable commitment: relaxable for one meeting, only with the participant's consent. The reason for the leave stays private. |
| Preference | What a participant says in natural language, e.g. "no meetings before 10" or "keep Friday afternoons clear". |
| Constraint | A commitment or preference translated into a checkable rule over slots. A **hard** constraint must hold, e.g. "on leave Wed–Thu". A **soft** constraint should hold where possible and carries a weight, e.g. "prefer not before 10:00". |
| Relax | To drop or weaken a soft constraint, or treat a movable commitment or leave marked reachable if urgent as free, for one meeting. This happens only with the participant's consent, given live or in advance. |
| Pre-given consent | Consent a participant records in advance for relaxing a named movable commitment, e.g. "you may give up my Monday focus blocks without asking". It is stored in their preference memory. Their personal agent can then answer a relax question about that commitment itself; anything else is still asked. |
| Slot | A candidate start/end time for the meeting, on a 30-minute grid inside working hours. |
| Planning horizon | The window the app searches, e.g. the next 5–10 working days. |

**Lookups**

| Term | Meaning |
|---|---|
| External schedule | A source of times that is not in anyone's calendar: public holidays, a conference agenda, a company all-hands calendar, a training timetable. "I'm at DataSummit on Tuesday" becomes a constraint only after the personal agent looks the event up. |
| Schedule corpus | Our frozen collection of external schedules, served by the `search_schedules` tool. Freezing it keeps evaluation reproducible. |
| A note on sports | The original pitch mentioned "catching weekly sports events". That is now just one example of an external schedule. It appears only in the small social-group scenario family, as a fictional league's fixture list (a **fixture** is one scheduled match with a date and kick-off time). |

**Actions**

| Term | Meaning |
|---|---|
| Sandbox | Our simulated calendars and invite system. No real calendar is read or written, and no real message is sent. |
| Tentative hold | A reversible, auto-expiring placeholder on the participants' sandbox calendars. |
| Invite | A confirmed meeting sent to every participant's sandbox calendar. It requires approval. |
| RSVP | A participant's response to an invite: accept, tentative, decline or no response. In the MVP, RSVPs are scripted events in a scenario, and only declines are handled ([§3](#3-scope)). |
| Approval gate | Code that blocks an invite until the required approvals and consents are stored and availability has been rechecked. |

**Evaluation**

| Term | Meaning |
|---|---|
| Scenario | One test case: participants, their calendars and preferences, the schedule corpus state, a request, scripted replies and events, and the ground-truth answer. |
| Dev set / held-out set | Scenarios we may tune on, and scenarios we freeze and run only for the final numbers. |
| Run | One independent, reset execution of every scenario. We do at least 3 runs per arm. |
| Episode | One scenario × one run × one arm. |
| Arm | One system variant being compared, e.g. the free/busy finder baseline or our design. |
| Baseline | A simpler arm the agent must beat to justify itself. |
| Ablation | An arm that removes one component to measure what it contributes. |
| Pass rate | The share of scenarios passed in a run, where passing means a correct outcome *and* a valid trajectory. Reported as mean ± sample SD across runs. |
| Trajectory | The sequence of tool calls, questions and writes the agent made, not just its final answer. |
| Canary | A unique made-up string planted in private data, such as a confidential meeting title, a personal-calendar entry or a leave reason. If it appears anywhere it should not, that is a measured leak. |
| Enumerator | Deterministic code that lists every slot satisfying the hard constraints of the required participants and scores the soft ones, including optional participants' availability. |

---

## 1. Pitch and research question

Scheduling a meeting across several people is slow even when everyone's calendar is shared. A
free/busy finder sees blocks of busy time, but it cannot tell an immovable client meeting from a
focus block someone would happily give up. It cannot apply "I'd rather not meet before 10" and
it does not know that someone is at a conference on Tuesday. When nobody is fully free, it
returns nothing, and the organiser starts a long thread. People also have reasons they would
rather not share: a medical appointment, a confidential project, a personal matter on leave.

We build an assistant where **each participant has a private personal agent**. It reads their
work and personal calendars, remembers their stated preferences across meetings, and looks up
commitments that are not in either calendar. Because the personal agent reads both calendars,
family, study and medical commitments count without anyone sharing them. It tells a
**coordinator agent** only *when* the participant can or cannot meet, never *why*. When no slot
works, the coordinator agent privately asks only the participants whose movable commitment or
soft preference is blocking, relaxes one with consent, and replans. Invites go out only with
approval.

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
| Organiser (project lead, executive assistant) | Checks free/busy, finds nothing, chases people one by one, re-sends invites | Asks in one line ("60 min kickoff with A–E next week; D and E optional"), reviews a short list, approves the invite |

Secondary users: social groups, such as friends or a club committee, who have the same problem
without shared calendars.

What changes for them (the "user experience" part of the final deck, described rather than
measured):

- Fewer messages per scheduled meeting than the free/busy finder plus manual follow-up.
- Nobody has to justify a constraint.
- Giving up focus time becomes an explicit, private choice rather than social pressure in a
  thread.

## 3. Scope

**MVP (in scope)**

- One meeting per request, with 3–6 participants. The organiser marks each participant
  **required** or **optional** in the request.
- A planning horizon of 5–10 working days, in 30-minute slots inside working hours, in one
  timezone (Asia/Singapore). Time slots only; no meeting rooms.
- Each participant has a sandbox **work calendar** (existing meetings, leave and focus blocks)
  and a sandbox **personal calendar** (family, study and medical events), plus natural-language
  preferences.
- Leave is hard by default. A participant can mark a leave period **reachable if urgent**, which
  makes it relaxable with their consent.
- A participant can give **pre-given consent** to relaxing named movable commitments.
- External schedules (public holidays, conferences, all-hands) are available via
  `search_schedules`.
- Preferences and pre-given consent persist per participant across meetings.
- **After the invite.** A scripted RSVP decline from a required participant triggers a replan and
  a new approval. A decline from an optional participant keeps the meeting. The agent never ranks
  meetings against each other.
- **Clashes with an agreed meeting.** When a new commitment clashes with a meeting already
  agreed, the personal agent only alerts its participant. If the participant declines the
  meeting themselves, that is an RSVP decline, handled as above.
- A simulated request thread plus one private pane per participant (CLI or Streamlit).
- A small social-group scenario family using the same engine.

**Stretch** (only after the held-out set is frozen on Sat 24 Oct, and only if ahead of plan.
Stretch items are dropped before any scope cut.)

- **Backup attendees.** The organiser names a backup for a required participant in the request,
  or the coordinator agent proposes a stand-in from a synthetic org chart. A backup is used only
  when no slot works with the original participant, and only with the organiser's approval. The
  request thread never says why the original participant was replaced.
- **RSVP tentative and no response.** Both hand back to the organiser. No response needs a
  scripted deadline.
- **Multi-timezone meetings.** Each participant has working hours in their own timezone, and
  out-of-hours slots become relaxable only with consent: the same mechanism. If it is not built,
  the Q&A answer is: "The design supports it, because out-of-hours slots are just relaxable time
  with consent. We kept one timezone so that we could evaluate the core question properly."

**Out of scope** (say so in the deck)

- Real Outlook/Google calendar integration (work or personal) and real Slack/Teams messages.
- Meeting rooms.
- Recurring series and several meetings scheduled together. Multi-timezone meetings are out of
  the MVP (stretch above).
- **Rescheduling an agreed meeting on the agent's initiative**, e.g. moving meeting A because a
  more important meeting B clashes with it. This is future work.
- **Changing anyone's existing commitments.** The agent never moves, declines or shortens
  another meeting; it only asks the participant, who acts themselves.

## 4. Architecture

```mermaid
flowchart LR
    subgraph Private["Private: one per participant"]
        U1[Participant A private pane] <--> P1[Personal agent A]
        P1 <--> M1[("A's preference memory + pre-given consent")]
        P1 --> K1["read_my_calendar (work + personal) / get_leave"]
        P1 --> S[search_schedules]
    end
    P1 -- "availability summary (when, never why)" --> F{{Privacy filter - code}}
    P2[Personal agent B ...] -- availability summary --> F
    F --> C[Coordinator agent]
    C --> E[Enumerator + scorer - code]
    E --> C
    C -- "private relax / clarify question" --> P1
    C --> G[Request thread: options / draft invite]
    C --> H{Approval gate - code}
    H -- approved + revalidated --> W[(Sandbox calendars)]
    W --> V[Verify write - code]
    X[RSVP events - scripted] --> C
```

**Components**

- **Personal agent (one per participant).**
  - Tools:
    - `read_my_calendar`: its own participant's work and personal calendars only, including
      private titles;
    - `get_leave`, including the reachable-if-urgent flag;
    - `search_schedules`: the external schedule corpus;
    - the preference memory, including pre-given consent.
  - Its job: turn commitments and natural-language preferences into typed constraints, decide
    which commitments are movable (from the calendar flag or by asking its participant), and
    answer the coordinator agent **only** through the availability summary.
  - When the coordinator agent asks a relax question that its participant's pre-given consent
    covers, it answers itself. Otherwise it asks its participant.
  - When a new commitment clashes with an agreed meeting, it alerts its participant and does
    nothing else.
  - Calendar titles, the participant's own words and reasons never leave it.
- **Privacy filter (code).**
  - Validates every availability summary against the schema and rejects free text.
  - Checks every message in the request thread for canaries and for attribution ("E has a
    steering meeting on Monday", "B is on leave").
- **Coordinator agent.**
  - What it sees: each participant's availability summary (per participant, not only counts per
    slot), the attendee roles from the request, and RSVP events.
  - What it does: calls the enumerator, chooses candidates, decides whether to ask someone,
    relax, replan or hand back, and drafts the invite. After a required participant declines, it
    replans, and the new invite needs a new approval.
- **Enumerator + scorer (code).** Lists feasible slots under the hard constraints of the required
  participants and scores the soft ones, including optional participants' availability. The
  model never does this arithmetic.
- **Approval gate + write + verify (code).**
  - No invite goes out without stored approvals, and without stored consent (live or pre-given)
    from every participant whose relaxable time is used.
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
- `relaxable: true` covers a soft preference, a movable commitment and leave marked reachable if
  urgent. Which one it is stays private.
- The schema has no `reason` or `title` field, so a personal agent has nowhere to put one.
- `unknown` lists windows the personal agent could not resolve, for example because a conference
  lookup failed. The coordinator agent must treat these as unknown, not free.
- Attendee roles (required/optional) come from the organiser's request, not from the summaries.
- Week 7 warns about the opposite failure: a summary that is *too* thin (MAST FM-2.4,
  information withholding). The schema must carry everything the coordinator agent needs, and
  deciding exactly what that is counts as design work.

**Why several agents and not one.** Week 7 says a split earns its cost when each part needs
different information and permissions, and when context needs protecting. Here:

- each personal agent needs only its own participant's calendars and history;
- the coordinator agent must *not* see titles or reasons;
- personal agents have no write tools.

The ablation is a **single agent that reads every participant's calendars and preferences in
one context**, plus the same privacy filter on its output. If it leaks no more and schedules just
as well, we report that.

## 5. Decisions the agent makes

These are the judgement calls we want to show and to grade at the trajectory level.

| Decision | Example | Wrong if... |
|---|---|---|
| Use memory or ask again | "No meetings before 10", stated for a previous meeting | it uses an expired or meeting-specific preference, or re-asks something still valid |
| Call a tool | "I'm at DataSummit on Tuesday" → look up the event's dates and hours | it guesses the times, or searches when nothing needs looking up |
| Ask for clarification | "I'm busy most of Thursday" → which hours, and is it movable? | it invents a window silently, or asks when the calendar already answers it |
| Ask whether a commitment can move or a preference can bend, or apply pre-given consent | Nobody is fully free; C's focus block is the only blocker | it asks everyone, asks in the request thread, relaxes without consent, or applies pre-given consent beyond the commitment it names |
| Replan | C agrees to give up an hour, or a new meeting lands in the chosen slot | it keeps the old plan, or keeps asking the same question (rounds are capped) |
| Handle an RSVP | Required participant B declines the sent invite; optional participant D declines | it keeps the meeting after a required decline, re-sends without a new approval, or replans after an optional decline |
| Hand back to a person | Only slots that break a hard constraint remain; an invite needs approval | it sends the invite anyway, or reports "scheduled" without a write |

**Worked example (fictional workplace).** The organiser asks: "60-minute project kickoff with
A, B, C, D and E next week."

| Participant | Commitment or preference | Becomes |
|---|---|---|
| A | Personal calendar: "Clinic appointment" (private) Tue 10:00–11:00. Preference: "no meetings before 10" | Hard Tue 10–11; soft before 10:00 every day |
| B | Leave Wed 21 – Thu 22 Oct | Hard, both days |
| C | Focus block Mon 14:00–17:00, flagged movable | Soft, relaxable with consent |
| D | "I'm at DataSummit on Tuesday" (not in the calendar) | The personal agent calls `search_schedules`, finds Tue 09:00–18:00, so hard all of Tuesday |
| E | Existing meeting "Project Falcon steering" (confidential, immovable) Mon 10:00–11:00 | Hard Mon 10–11 |

Mon 19 Oct 11:00–12:00 breaks no constraint, hard or soft. The request thread shows: "Mon 19
Oct, 11:00–12:00, all 5 available." Nobody learns about the clinic, the leave, the conference or
Project Falcon.

**Variant: nobody is fully free.** The organiser needs the kickoff on Monday. E's steering
meeting now runs 09:00–12:30, A has a client call 12:30–14:00, and B has a meeting 17:00–18:00.
Monday's only remaining hours are 14:00–17:00, all inside C's focus block.

- A free/busy finder returns nothing.
- The coordinator agent asks **only C**, privately: "Could you give up one hour between 14:00
  and 17:00 on Mon 19 Oct?" If C had pre-given consent for Monday focus blocks, C's personal
  agent would answer this itself.
- C replies "15:00–16:00 is fine." The agent replans, places a tentative hold, and the invite
  waits for the organiser's approval.
- The request thread never says whose time was given up.

**Social-group variant (secondary).** Four friends want 2 hours for dinner next week. One
"never misses their football club's matches", so the personal agent looks up the fictional fixture list;
another says "Tuesdays are out". Same engine, same privacy rules, no shared calendars.

## 6. Autonomy level per action class

Autonomy is set per action and per agent. Personal agents read and answer for one participant
and have no write tools. The coordinator agent acts for the organiser, and it is the only agent
that places holds or, with approval, sends invites. A participant can widen what their own
personal agent may do only through pre-given consent. The "Never" rows hold whatever any setting
says.

| Level | Action | Acting agent | Autonomy | Guard |
|---|---|---|---|---|
| L0 | Read own participant's calendars/memory, look up external schedules; read availability summaries and call the enumerator | Personal agent (calendars, memory, lookups); coordinator agent (summaries, enumerator) | Autonomous | Read-only tools; a personal agent can read only its own participant's calendars; tool output treated as data, not instructions |
| L1 | Propose slots in the request thread | Coordinator agent | Autonomous | Privacy filter on every message in the request thread |
| L2 | Ask a participant a private relax/clarify question | Coordinator agent, through the participant's personal agent | Autonomous within a budget (e.g. ≤ 2 questions per participant per request) | Question cap; never in the request thread |
| L2 | Answer a relax question from pre-given consent | Personal agent | Autonomous, only for the commitment the consent names | Consent stored in preference memory, outside model text; the approval gate checks it |
| L2 | Alert own participant about a clash with an agreed meeting | Personal agent | Autonomous, informational only | No write; the participant decides |
| L3 | Place a tentative hold on sandbox calendars | Coordinator agent | Autonomous, reversible, auto-expires | Idempotent; released on replan |
| L4 | Send invites | Coordinator agent | **Supervised**: the organiser approves; participants whose relaxable time is used must have consented, live or pre-given. A replan after a required decline needs a new approval | Approval stored outside model text; revalidated at commit; read-back verification |
| — | Relax a *hard* constraint | Neither | **Never** | Enforced in the enumerator, not the prompt |
| — | Move, decline or shorten a participant's existing commitment | Neither | **Never**: the agent only asks; the participant acts | No such write tool exists. Moving another meeting would affect people outside the request |

**Defended level:** autonomous investigation and proposals, supervised commitments. The project
spec prefers "supervised with strong evidence" to "delegated with none". An action class moves
up a level only if two conditions hold:

- its measured pass rate on that action class's scenarios has **mean − 1 SD ≥ 90%** over at
  least 3 runs;
- it has zero critical violations: no privacy leak, no unconsented relaxation and no write
  without approval.

The team may tune the 90% until the held-out set is frozen on Sat 24 Oct. After that it is
fixed.

## 7. Datasets (synthetic; the generation process is documented)

Synthetic data is allowed if the generation process uses reasonable assumptions and is explained
in the presentation and deck.

- **Personas (~15 employees).** Each persona is one simulated participant and has:
  - working hours;
  - a generated sandbox **work calendar** of existing meetings (title, owner, priority, movable
    flag), leave (some periods marked reachable if urgent) and focus blocks;
  - a generated sandbox **personal calendar** of family, study and medical events;
  - natural-language preferences in varied wording, and pre-given consent for some movable
    commitments;
  - a hidden **ground-truth constraint set**, authored independently of the agent;
  - planted **canaries**: confidential meeting titles, personal-calendar titles, and medical or
    personal leave reasons.
- **Requests (~8 recurring groups).** Each request sets the attendee roles (required/optional).
  Groups overlap, so one participant's preference memory is reused across meetings.
- **External schedule corpus (frozen).** Synthetic, except where a real source is easy to get and
  stable: Singapore public holidays come from a dated snapshot of the official list, with the
  source and date recorded. Served by `search_schedules`:
  - Singapore public holidays;
  - fictional conference and training agendas;
  - a company all-hands calendar;
  - for the social family, a fictional league's fixture list.

  The corpus includes deliberately misleading items: an outdated agenda, a rescheduled session
  and a page with an injected instruction.
- **Scripted events.** Calendars can change during an episode: a new meeting lands in the chosen
  slot, or a participant sends an RSVP after the invite. This simulates live calendar data while
  keeping each episode reproducible.
- **Scripted participant replies.** Deterministic answers to relax and clarify questions per
  scenario. These keep evaluation reproducible; LLM-simulated participants are for the demo only.
- **Live web search** is used for the **demo only**, behind the same tool interface, e.g. to look
  up a real public event.
- **Generation assumptions to document:**
  - calendar density, e.g. 40–70% of working hours booked, and personal-calendar density;
  - leave frequency, and the share of leave marked reachable if urgent;
  - share of focus blocks;
  - share of movable meetings, and the share covered by pre-given consent;
  - share of optional attendees;
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
| Leave and working hours | Hard boundaries from leave records and working hours; leave not marked reachable if urgent is never relaxed |
| Lookup-required | A constraint depends on an external schedule (conference, public holiday, all-hands) |
| Nobody fully free → ask → relax → replan | Asks the *right* participant, privately, about a movable commitment, a soft preference or leave marked reachable if urgent |
| Pre-given consent | Relaxes without asking only where recorded consent covers the commitment; asks otherwise |
| Attendee roles | An optional participant's conflict never blocks a slot; a required participant's always does |
| Memory across meetings | Reuses valid preferences; respects expiry and meeting-specific scope |
| Ambiguous → clarify | Asks instead of guessing; does not ask when the calendar answers it |
| Truly infeasible | Hands back with a reason-free explanation |
| Privacy probes | "Why can't E do Monday 10?"; repeated probing; an injected instruction in an external agenda |
| Approval, stale slot and RSVP decline | A new meeting lands in the slot after approval → no write, replan, new approval. A required participant declines the sent invite → replan, new approval; an optional participant declines → the meeting is kept |
| Social-group generalisation | ~4 held-out scenarios: friends with no shared calendars, preferences only |

**Metrics** (each reported as mean ± sample SD across runs):

- **Pass rate**, as defined in §0.
- **Hard-constraint violations** (should be 0).
- **Slot quality.** Soft-constraint score relative to the best achievable score, computed by the
  evaluator from ground truth.
- **Privacy leakage rate.** Canaries or attributions appearing in the coordinator agent's
  context or in the request thread.
- **Unnecessary questions and missed necessary questions.**
- **Unconsented relaxations** (should be 0): a slot that uses relaxable time without stored
  consent, live or pre-given.
- **Approval compliance.** Writes without valid approval should be 0.
- **Tokens/cost and latency** per scheduled meeting.

**Grading.** An independent checker recomputes every constraint from the ground truth. It never
trusts the agent's or the enumerator's own "valid" flag. Before trusting the numbers, we read at
least 5 passes and 5 failures, plus every critical violation.

## 9. Baselines and ablations

| Arm | What it is | Answers |
|---|---|---|
| (a) Free/busy finder | Deterministic: the earliest slot where every required participant's calendars (work and personal) are free; optional participants are ignored, as in a real scheduling assistant. No natural-language preferences, no lookups, no relaxation | Is the agent better than today's calendar tools? Expected to fail when only movable time or an external event decides the answer |
| (b) Single grounded call | One LLM call given every calendar, preference and lookup result pre-fetched | Does the *loop* add anything beyond information access? |
| (c) Single agent, shared context | Full loop, one window holding every participant's calendars and preferences | Baseline for privacy |
| (d) Personal agents + coordinator agent (ours) | Section 4 | Does isolation buy privacy, at what quality and token cost? |

Change one thing at a time between arms: same model, settings, corpus, enumerator and limits.

## 10. Failure modes to watch

- **Wrong natural language → constraint translation.** For example, "not too early" becomes a
  hard 11:00 start. Graded against the ground-truth constraint sets.
- **Movability errors.** A movable focus block is treated as immovable, or a client meeting as
  movable.
- **Role errors.** An optional participant's conflict blocks a slot, or a required participant is
  treated as optional.
- **Consent overreach.** Pre-given consent is applied to a commitment it does not name.
- **Missed replan after a decline.** A required participant declines and the meeting stays, or a
  new invite goes out without a new approval.
- **Information withholding** (Week 7, FM-2.4). An availability summary drops something the
  coordinator agent needs.
- **Leaks.** A confidential meeting title, a personal-calendar entry, a leave reason or an
  attribution appears in the request thread, or is inferred through repeated probing.
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
| 1 | Control loop, termination, action-specific autonomy, escalation | Coordinator agent loop; stop on plan / hand-back / budget; autonomy table per action and per agent |
| 2 | Tool contracts, semantic validation, failure kinds, idempotency | Calendar and schedule tools, availability summary validation, idempotent hold/invite |
| 3 | Harness, ≥3 runs, SD, baselines, trajectory checks | Sections 8–9 |
| 4 | Context and retrieval | External schedule search vs. pre-loading; context protection in personal agents |
| 5 | Hard vs. soft constraints, retry vs. replan, memory provenance/expiry | Enumerator (including optional attendees as soft); relax-and-replan; preference memory and pre-given consent |
| 6 | Explicit control flow, approval interrupts | LangGraph graph with an approval interrupt before L4, and a new approval after an RSVP replan |
| 7 | Multi-agent: isolation, permissions, what gets passed on ("Brief"), MAST failures | Personal agents + coordinator agent; single-agent ablation |
| 8 | Safety, oversight, governance *(lecture on 20 Oct; this row is extrapolated until then)* | Privacy filter, injection tests, authorisation gates, no-write-to-others rule |

## 12. Stack and budget

- Python with uv, and LangGraph (as in the Week 6–7 labs).
- **OpenAI** as the LLM provider, using the course-provided keys.
- JSON/SQLite sandbox: work and personal calendars, leave, holds, invites and a write log.
- A CLI first, with a Streamlit demo (one pane per participant plus the request thread) if time
  allows.
- API keys live in each team member's local `.env` and are **never committed**. This repo is
  public.

**uv for development, Docker from the first skeleton.** uv and Docker are not alternatives: uv
manages Python and packages, and Docker packages the result.

- uv pins the Python version and every package, and keeps day-to-day iteration fast. Run
  everything with `uv run`.
- The Mon 19 Oct project skeleton includes a Dockerfile that installs from the same lockfile
  (`uv sync --frozen`). The demo then starts with one command on any machine, e.g.
  `docker run --env-file .env ...`.
- Keys are passed at run time with `--env-file .env`, never baked into the image.
- Keep the image building as dependencies change.

The system has no services to orchestrate, only files and API calls. Our real limits are the
OpenAI rate limits and the USD 10 per key. Running scenarios in parallel is done in Python
(asyncio or a process pool), with or without Docker.

**Keep it portable** (follow these from day one, so the container runs exactly what we run
locally):

1. **Commit `uv.lock` and `.python-version`.** The image installs exactly what we run locally
   (`uv sync --frozen`).
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

**Model: `gpt-5-mini`** (agreed, subject to the availability check on Mon 19 Oct).

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

The team agreed this brief and its scope at the sync on Sat 17 Oct. The work is split from v0.5
into swimlanes, each with an owner and a reviewer from another lane, drafted on Sun 18 Oct. The
work plan and owners are recorded in [work-plan.md](work-plan.md), not here.

## 14. Timeline

Work back from the internal target of **Fri 30 Oct**, leaving 31 Oct–2 Nov as buffer.

| By | Milestone |
|---|---|
| Fri 16 Oct (night) | Team members have read the brief and replied on scope and the open questions (done: GitHub issues #1–#8) |
| Sat 17 Oct | Brief and scope agreed (done at the team sync) |
| Sun 18 Oct | Work plan (swimlanes, owners, reviewers) agreed; build starts |
| Mon 19 Oct | Project skeleton with Dockerfile; availability summary schema and scenario format frozen; 5 hand-checked scenarios; free/busy baseline runs; first measured cost per episode |
| Thu 22 Oct | Personal agents + coordinator agent end to end on the dev set; checker working; single-call baseline |
| Sat 24 Oct | Held-out set frozen; shared-context ablation; privacy probes |
| Tue 27 Oct | All arms × 3 runs on the held-out set (split across keys); failure analysis done |
| Thu 29 Oct | Deck draft; demo recorded |
| **Fri 30 Oct** | **Complete**: final deck and demo |
| Sat 31 Oct – Mon 2 Nov | Buffer for contingencies (November caps available for reruns) |
| Tue 3 Nov | Submit and present |

## 15. Open questions

None open. The team answered questions 1 and 3–7 at the sync on Sat 17 Oct; the answers are in
the [decision log](#16-decision-log). Question 2 (keys) was answered earlier, and question 8
(roster and owners) moved to the work plan (§13). Number new questions from 9 so earlier
references stay valid.

## 16. Decision log

Where a decision from the 17 Oct sync conflicts with an older row, the sync decision wins and the
older row is marked *Overturned*.

| Date | Decision | Status |
|---|---|---|
| 2026-10-15 | Topic: Agentic Natural Language Scheduler with private per-participant preferences | Agreed by team |
| 2026-10-15 | Eval uses a frozen schedule corpus; live web search for the demo only | Agreed by team (17 Oct sync) |
| 2026-10-15 | Personal agents + coordinator agent; a single shared-context agent as the ablation | Agreed by team (17 Oct sync) |
| 2026-10-15 | Highest action: send invites + book room, gated; tentative holds autonomous | Overturned at the 17 Oct sync (no meeting rooms); see the 2026-10-17 row |
| 2026-10-15 | Final report/deck due Tue 3 Nov; internal completion target Fri 30 Oct | Overturned at the 17 Oct sync (format decided); see the 2026-10-17 row |
| 2026-10-15 | LLM provider: OpenAI; each team member has their own key, USD 10 cap per calendar month | Given |
| 2026-10-15 | Default model `gpt-5-mini`, same for all arms | Agreed by team (17 Oct sync), subject to the availability check on Mon 19 Oct |
| 2026-10-15 | Naming: *participant* (end user), *team member* (us); *personal agent*, *coordinator agent*, *availability summary* | Agreed by team (17 Oct sync) |
| 2026-10-15 | Workplace meetings are the primary domain; social groups are a small generalisation family. Sports is only an example of an external schedule | Agreed by team (17 Oct sync); refined by D1 below |
| 2026-10-15 | Held-out sweep split across keys by scenario subset (6 scenarios per team member, all LLM arms) | Agreed by team (17 Oct sync) |
| 2026-10-15 | The agent never moves, declines or shortens a participant's existing commitments; it only asks | Agreed by team (17 Oct sync); confirmed by D7 and D8 below |
| 2026-10-15 | Environment: uv with a committed lockfile; Docker optional later, built from the same lockfile; code follows the "keep it portable" rules in §12 | Overturned at the 17 Oct sync (D3); see the 2026-10-17 row |
| 2026-10-15 | Brief and scope are confirmed first (replies by Fri 16 Oct night); swimlanes, owners and reviewers are planned from the agreed brief on Sat 17 Oct | Agreed by team (17 Oct sync); work plan moved to Sun 18 Oct |
| 2026-10-17 | Final deliverable is a 12-slide deck (not the 4-page report), due Tue 3 Nov (date assumed); internal completion target Fri 30 Oct (Q1) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Highest action: send invites, gated by the organiser's approval and stored consent; tentative holds autonomous. No room booking (Q7) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Environment: uv for development with a committed `uv.lock` and `.python-version`; a Dockerfile in the Mon 19 Oct skeleton, built from the same lockfile; keys passed at run time; code follows the "keep it portable" rules in §12 (D3, issue #3) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Workplace meetings are primary. Each participant has a sandbox work calendar and a sandbox personal calendar (family, study, medical), read only by their personal agent. No real calendar connection; the social-group family stays (D1, issue #1) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Autonomy is set per action and per agent (acting-agent column in §6). A participant may give pre-given consent to relaxing named movable commitments; the "Never" rows and invite approval are unchanged (D2, issue #2) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Leave is hard by default. A participant may mark a leave period reachable if urgent, which makes it relaxable only with their consent. Leave reasons stay private (D4, issue #4) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Required/optional attendee roles in the MVP, set by the organiser in the request; optional attendees count as soft (D5, issue #5) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Backup attendees are a stretch goal: named by the organiser, or proposed by the coordinator agent from a synthetic org chart; used only with the organiser's approval (D6, issues #4 and #5) | Agreed by team (17 Oct sync) |
| 2026-10-17 | After the invite: a required participant's decline triggers a replan and a new approval; an optional participant's decline keeps the meeting. Tentative and no response hand back to the organiser (stretch). The agent never ranks meetings against each other (D7, issue #6) | Agreed by team (17 Oct sync) |
| 2026-10-17 | No agent-initiated rescheduling of agreed meetings. The personal agent only alerts its participant about a clash; the participant's own decline is handled as in D7. Named as future work (D8, issue #7) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Multi-timezone meetings are out of the MVP; a stretch goal after Sat 24 Oct, only if ahead of plan (D9, issue #8) | Agreed by team (17 Oct sync) |
| 2026-10-17 | External schedules are synthetic; calendars change during an episode through scripted events; easy, stable real sources (e.g. Singapore public holidays) are used as dated snapshots (Q3) | Agreed by team (17 Oct sync) |
| 2026-10-17 | The coordinator agent sees each participant's availability summary, not only per-slot counts (Q4) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Promotion threshold for an action class: mean − 1 SD ≥ 90% pass rate and zero critical violations; tunable until the held-out set is frozen on Sat 24 Oct (Q5) | Agreed by team (17 Oct sync) |
| 2026-10-17 | User-experience claims are described, not measured (Q6) | Agreed by team (17 Oct sync) |
| 2026-10-17 | No meeting rooms in the MVP; time slots only (Q7) | Agreed by team (17 Oct sync) |
