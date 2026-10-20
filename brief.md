# Project brief: Agentic Natural Language Scheduler

CS621 Agentic AI for Intelligent Autonomy, group project.
Final deck (12 slides) and presentation: **Tue 3 Nov 2026** (assumed). Internal completion
target: **Fri 30 Oct 2026**.

Status: **draft v0.7, 21 Oct 2026.** v0.5 recorded the decisions from the team sync on Sat 17
Oct, which settled GitHub issues #1–#8 and the open questions (discussion in
[issue-review.md](issue-review.md)). v0.6 proposed one guided build and the A0–A4 rename. v0.7
records the team's decisions of 20 Oct (§16):
- the scheduler is **general-purpose**, not workplace-first: a work calendar is one input among
  several, and a participant's messages are another (§0–§3, §7–§9);
- Week 8 (guardrails) is in scope where time allows (§6, §8, §11), and a demo page is built last
  (§12);
- the solution is built end to end and committed step by step, with no replay (§13).

Every other row in the [decision log](#16-decision-log) is agreed or overturned. Changing a decision needs the team's agreement and a new row in the
decision log. Put anything unresolved in [open questions](#15-open-questions). Terms are defined
in [§0](#0-definitions).

---

## 0. Definitions

**Naming rule.** *Team* and *team member* mean only the five of us building this project.
The people the app schedules for are always called **participants**.

**People and agents**

| Term | Meaning |
|---|---|
| Meeting | Anything a group schedules together: a work meeting, a dinner with friends, a family lunch. The brief says "meeting" for all of them. |
| Participant | A person invited to the meeting being scheduled: an end user. Each participant has their own calendars and messages, private preferences, and an attendee role in each meeting. |
| Organiser | The participant who asks for the meeting: a project lead, a friend planning a dinner, a parent planning a family lunch. The organiser sets each participant's attendee role and approves the invite. |
| Attendee role | Set by the organiser in the request. A **required** participant must attend: a slot one of them cannot make does not work. An **optional** participant's availability counts as soft: it improves a slot's score but never blocks it. |
| Group | The participants of one meeting. A participant can be in many groups. |
| Request thread | The shared conversation where the organiser asks for the meeting and sees options, like a Slack/Teams thread or a group chat. Everything posted here is visible to every participant in the group. |
| Personal agent | One private agent per participant. It reads that participant's calendars, messages and preferences, does lookups for them, and talks to the coordinator agent only through an availability summary. |
| Coordinator agent | The agent that schedules for the whole group. It sees each participant's availability summary, never calendars, preferences or reasons. |
| Availability summary | A fixed-format message from a personal agent to the coordinator agent. For each candidate slot it says *available*, *prefer not* or *unavailable*, and it has no field for reasons. Week 7 calls this kind of hand-off a "Brief". |

**Time, commitments and preferences**

| Term | Meaning |
|---|---|
| Commitment | Anything already occupying a participant's time: an **entry on one of their calendars** (a work meeting, a school pickup, a club practice; with a priority and a movable flag), **time away** (leave, a trip, a holiday), a **focus block** or other time they blocked for themselves, an **external event** (a conference, a training, a club fixture, whose times may need looking up), or a **booking or plan in their messages** (an appointment confirmation, a dinner agreed in a chat). |
| Calendar | Each participant keeps any number of named sandbox calendars: work, family, club, study, personal. A work calendar is one input among several. Only their own personal agent reads them. Titles can be private, e.g. "Clinic appointment" or a confidential project name. |
| Message | A message in a participant's own inbox or chats: a booking confirmation, an invitation, a plan agreed with friends. Someone else wrote it. The personal agent infers availability from it (a confirmed booking is a commitment; a cancelled one or an invitation never accepted is not) and never takes instructions from it. Only their own personal agent reads it. |
| Free/busy | The standard calendar view that shows *when* someone is busy but not *what* they are doing. Outlook and Google Calendar scheduling assistants use it. |
| Usual hours | The hours a participant normally accepts plans, on any day, e.g. 09:00–18:00 at work or 18:00–23:00 for evenings out. |
| Movable commitment | A commitment the participant says they could shift or give up if asked, typically a focus block, a low-priority internal meeting or a flexible gym session. The agent never moves it itself; it can only ask. |
| Reachable if urgent | A flag a participant can set on time away. Time away is a hard constraint by default. Time away marked reachable if urgent is treated like a movable commitment: relaxable for one meeting, only with the participant's consent. The reason stays private. |
| Preference | What a participant says in natural language, e.g. "no meetings before 10" or "keep Friday afternoons clear". |
| Constraint | A commitment or preference translated into a checkable rule over slots. A **hard** constraint must hold, e.g. "on leave Wed–Thu". A **soft** constraint should hold where possible and carries a weight, e.g. "prefer not before 10:00". |
| Relax | To drop or weaken a soft constraint, or treat a movable commitment or time away marked reachable if urgent as free, for one meeting. This happens only with the participant's consent, given live or in advance. |
| Pre-given consent | Consent a participant records in advance for relaxing a named movable commitment, e.g. "you may give up my Monday focus blocks without asking". It is stored in their preference memory. Their personal agent can then answer a relax question about that commitment itself; anything else is still asked. |
| Slot | A candidate start/end time for the meeting, on a 30-minute grid, on the weekdays the request allows (Mon–Fri unless it says otherwise, e.g. Sat–Sun for a family lunch). |
| Planning horizon | The window the app searches, e.g. the next 5–10 working days, or the next two weekends. |

**Lookups**

| Term | Meaning |
|---|---|
| External schedule | A source of times that is not in anyone's calendar: public holidays, a conference agenda, a company all-hands calendar, a training timetable, a club's fixture list. "I'm at DataSummit on Tuesday" becomes a constraint only after the personal agent looks the event up. |
| Schedule corpus | Our frozen collection of external schedules, served by the `search_schedules` tool. Freezing it keeps evaluation reproducible. |
| A note on sports | The original pitch mentioned "catching weekly sports events". That is one example of an external schedule: fictional leagues' fixture lists (a **fixture** is one scheduled match with a date and kick-off time) appear in the evening and weekend scenarios. |

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
| Canary | A unique made-up string planted in private data, such as a confidential meeting title, a personal-calendar entry, a clinic named in a message or a reason for time away. If it appears anywhere it should not, that is a measured leak. |
| Enumerator | Deterministic code that lists every slot satisfying the hard constraints of the required participants and scores the soft ones, including optional participants' availability. |
| Guardrail | Week 8: a check that runs outside the model, reads what the model produced, and can stop the run. Every guardrail here records its verdict, passes included. |
| Attack case | A scenario with hostile text planted where an agent will read it (a corpus page, a message, the thread, a memory note), graded inverted: it passes when the attack did not work. |

---

## 1. Pitch and research question

Scheduling anything across several people is slow, at work and outside it: a project kickoff, a
dinner with friends, a family lunch. Even when everyone's calendar is shared, a free/busy finder
sees blocks of busy time, but it cannot tell an immovable client meeting from a focus block
someone would happily give up. It cannot apply "I'd rather not meet before 10" and
it does not know that someone is at a conference on Tuesday. When nobody is fully free, it
returns nothing, and the organiser starts a long thread. Outside work it is worse: friends and
families rarely share calendars at all, and half of what decides a weekend is in people's messages
(a confirmed appointment, a booking, a plan agreed in a chat). People also have reasons they would
rather not share: a medical appointment, a confidential project, a personal matter.

We build an assistant where **each participant has a private personal agent**. It reads all their
calendars (work, family, club…) and their messages, remembers their stated preferences across
meetings, and looks up commitments that are in no calendar. Because the personal agent reads them
privately, family, study and medical commitments count without anyone sharing them. It tells a
**coordinator agent** only *when* the participant can or cannot meet, never *why*. When no slot
works, the coordinator agent privately asks only the participants whose movable commitment or
soft preference is blocking, relaxes one with consent, and replans. Invites go out only with
approval.

The scheduler is **general-purpose** (team decision, 20 Oct): work meetings, evenings out and
family weekends are all first-class, and about half the evaluation scenarios are outside work.

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
  someone is attending, a club's fixtures, a booking that is only in someone's messages.
- No negotiation. The back-and-forth moves to chat, where people end up explaining their reasons
  in front of colleagues, friends or family.

Our value is the combination: natural-language preferences, lookups and relaxing with consent,
**while keeping reasons private**.

| User | Today | With the agent |
|---|---|---|
| Participant (anyone in the group) | Receives clashing invites, explains in the thread why a slot doesn't work, gets pressured into giving up focus time or a weekend plan | States preferences once; reasons stay private; asked privately, and only when their movable time is the one blocking the group |
| Organiser (a project lead, a friend, a parent) | Checks free/busy where it exists, or polls a group chat; finds nothing, chases people one by one, re-sends invites | Asks in one line ("60 min kickoff with A–E next week; D and E optional", "family lunch over the next two weekends"), reviews a short list, approves the invite |

What changes for them (the "user experience" part of the final deck, described rather than
measured):

- Fewer messages per scheduled meeting than the free/busy finder plus manual follow-up.
- Nobody has to justify a constraint.
- Giving up focus time, or a weekend plan, becomes an explicit, private choice rather than social
  pressure in a thread.

## 3. Scope

**MVP (in scope)**

- One meeting per request, with 3–6 participants. The organiser marks each participant
  **required** or **optional** in the request.
- A planning horizon of 5–10 days (working days, evenings, or weekends, as the request says), in
  30-minute slots inside each participant's usual hours, in one timezone (Asia/Singapore). Time
  slots only; no meeting rooms.
- Each participant has any number of named sandbox **calendars** (work, family, club, personal),
  time away, sandbox **messages** (bookings, invitations, plans agreed in chats), and
  natural-language preferences.
- Time away is hard by default. A participant can mark it **reachable if urgent**, which makes it
  relaxable with their consent.
- A participant can give **pre-given consent** to relaxing named movable commitments.
- External schedules (public holidays, conferences, all-hands, club fixtures) are available via
  `search_schedules`.
- Preferences and pre-given consent persist per participant across meetings.
- **After the invite.** A scripted RSVP decline from a required participant triggers a replan and
  a new approval. A decline from an optional participant keeps the meeting. The agent never ranks
  meetings against each other.
- **Clashes with an agreed meeting.** When a new commitment clashes with a meeting already
  agreed, the personal agent only alerts its participant. If the participant declines the
  meeting themselves, that is an RSVP decline, handled as above.
- A simulated request thread plus one private pane per participant: the CLI, and a Streamlit demo
  page built last (§12).
- Three settings in the scenarios: work (weekdays), evenings out, family weekends.
- **Guardrails (Week 8), where time allows:** every check in code records its verdict; caps on
  model calls, tokens, cost and time; attack cases graded inverted; a written security review.

**Stretch** (only after the held-out set is frozen (§14), and only if ahead of plan.
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

- Real Outlook/Google calendar integration, and real email, chat or Slack/Teams messages.
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
        P1 --> K1["read_my_calendar (every calendar) / get_leave / read_my_messages"]
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
    - `read_my_calendar`: its own participant's calendars only (all of them), including private
      titles;
    - `get_leave`: time away, including the reachable-if-urgent flag;
    - `read_my_messages`: its own participant's messages, text other people wrote;
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
  - Checks every message in the request thread for private details and for attribution ("E has a
    steering meeting on Monday", "B is on leave"). It reads the sandbox's calendar titles,
    reasons for time away and the names in messages, never the test canaries.
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

- each personal agent needs only its own participant's calendars, messages and history;
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

**Outside work.** Four friends want 2 hours for dinner next week. One "never misses their
football club's matches", so the personal agent looks up the fictional fixture list; another says
"Tuesdays are out". A family wants a lunch over the next two weekends: one says "Sundays before 1pm
are out, every week", and another's confirmed clinic appointment is only in their messages, next
to a cancelled badminton booking that must not count. Same engine, same privacy rules, no shared
calendars.

## 6. Autonomy level per action class

Autonomy is set per action and per agent. Personal agents read and answer for one participant
and have no write tools. The coordinator agent acts for the organiser, and it is the only agent
that places holds or, with approval, sends invites. A participant can widen what their own
personal agent may do only through pre-given consent. The "Never" rows hold whatever any setting
says.

The action classes are labelled A0–A4 so they are not confused with the course's autonomy levels
(week 1: L1 Operator … L5 Observer). In the course's terms:
- A0–A3 act within limits without a person (the coordinator agent works at Consultant level for
  A2: it consults the participant on a judgement);
- A4 is Approver: one interrupt before the write.

*(Rename proposed, pending team.)*

Week 8 asks what evidence justifies each level (08 p. 47): Collaborator needs a pass rate on the
cases that matter, Consultant needs evidence that it asks, Approver needs the refusal rate and
what gets through, and Observer needs containment and an attack suite it survives. Our claims stop
at Approver for A4: the evidence is the held-out pass rate per action class, the approvals asked
and refused, and the attack table (§8).

| Class | Action | Acting agent | Autonomy | Guard |
|---|---|---|---|---|
| A0 | Read own participant's calendars, messages and memory, look up external schedules; read availability summaries and call the enumerator | Personal agent (calendars, messages, memory, lookups); coordinator agent (summaries, enumerator) | Autonomous | Read-only tools; a personal agent can read only its own participant's data; its only output is a typed summary, so text it reads cannot reach the thread |
| A1 | Propose slots in the request thread | Coordinator agent | Autonomous | Privacy filter on every message in the request thread |
| A2 | Ask a participant a private relax/clarify question | Coordinator agent, through the participant's personal agent | Autonomous within a budget (e.g. ≤ 2 questions per participant per request) | Question cap; never in the request thread |
| A2 | Answer a relax question from pre-given consent | Personal agent | Autonomous, only for the commitment the consent names | Consent stored in preference memory, outside model text; the approval gate checks it |
| A2 | Alert own participant about a clash with an agreed meeting | Personal agent | Autonomous, informational only | No write; the participant decides |
| A3 | Place a tentative hold on sandbox calendars | Coordinator agent | Autonomous, reversible, auto-expires | Idempotent; released on replan |
| A4 | Send invites | Coordinator agent | **Supervised**: the organiser approves; participants whose relaxable time is used must have consented, live or pre-given. A replan after a required decline needs a new approval | Approval stored outside model text; revalidated at commit; read-back verification |
| — | Relax a *hard* constraint | Neither | **Never** | Enforced in the enumerator, not the prompt |
| — | Move, decline or shorten a participant's existing commitment | Neither | **Never**: the agent only asks; the participant acts | No such write tool exists. Moving another meeting would affect people outside the request |

**Defended level:** autonomous investigation and proposals, supervised commitments. The project
spec prefers "supervised with strong evidence" to "delegated with none". An action class moves
up a level only if two conditions hold:

- its measured pass rate on that action class's scenarios has **mean − 1 SD ≥ 90%** over at
  least 3 runs;
- it has zero critical violations: no privacy leak, no unconsented relaxation and no write
  without approval.

The team may tune the 90% until the held-out set is frozen (§14). After that it is fixed.

## 7. Datasets (synthetic; the generation process is documented)

Synthetic data is allowed if the generation process uses reasonable assumptions and is explained
in the presentation and deck.

- **Personas (~15 people).** Each persona is one simulated participant and has:
  - usual hours, which depend on the setting (work, evenings, weekends);
  - generated sandbox **calendars** (work, family, club, personal) with entries (title, priority,
    movable flag), time away (some marked reachable if urgent) and focus blocks;
  - in some scenarios, **messages**: a confirmed appointment that counts, and a cancelled booking
    or an unanswered invitation that does not;
  - natural-language preferences in varied wording, and pre-given consent for some movable
    commitments;
  - a hidden **ground-truth constraint set**, authored independently of the agent;
  - planted **canaries**: confidential meeting titles, personal-calendar titles, clinics named in
    messages, and medical or personal reasons for time away.
- **Requests (~8 recurring groups).** Each request sets the attendee roles (required/optional).
  Groups overlap, so one participant's preference memory is reused across meetings.
- **External schedule corpus (frozen).** Synthetic, except where a real source is easy to get and
  stable: Singapore public holidays come from a dated snapshot of the official list, with the
  source and date recorded. Served by `search_schedules`:
  - Singapore public holidays;
  - fictional conference and training agendas;
  - a company all-hands calendar;
  - two fictional leagues' fixture lists (weekday evenings, Sundays).

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
  - the three settings (work, evenings, weekends) and their windows;
  - calendar density, e.g. 40–70% of the window booked;
  - leave frequency, and the share of leave marked reachable if urgent;
  - share of focus blocks;
  - share of movable meetings, and the share covered by pre-given consent;
  - share of optional attendees;
  - ranges for meeting length and participant count.
- **Reproducibility.** Every scenario records its seed, parameters and generator version. The
  pattern follows the Week 7 lab's travel world: tool calls and writes are logged, and ground
  truth is computed from the same rules.

## 8. Eval sets and metrics

About **25 dev + 33 held-out scenarios** (built: 26 dev, 33 held-out, about half of each outside
work), frozen before we look at held-out outputs. Every LLM
arm gets **≥ 3 runs**, reset between runs. Scenario families (tags):

| Family | What it tests |
|---|---|
| Simple feasible | Baseline sanity; the agent should not add questions |
| Time away and usual hours | Hard boundaries from time away and usual hours; time away not marked reachable if urgent is never relaxed |
| Lookup-required | A constraint depends on an external schedule (conference, public holiday, all-hands) |
| Nobody fully free → ask → relax → replan | Asks the *right* participant, privately, about a movable commitment, a soft preference or leave marked reachable if urgent |
| Pre-given consent | Relaxes without asking only where recorded consent covers the commitment; asks otherwise |
| Attendee roles | An optional participant's conflict never blocks a slot; a required participant's always does |
| Memory across meetings | Reuses valid preferences; respects expiry and meeting-specific scope |
| Ambiguous → clarify | Asks instead of guessing; does not ask when the calendar answers it |
| Truly infeasible | Hands back with a reason-free explanation |
| Privacy probes | "Why can't E do Monday 10?"; repeated probing; an injected instruction in an external agenda |
| Approval, stale slot and RSVP decline | A new meeting lands in the slot after approval → no write, replan, new approval. A required participant declines the sent invite → replan, new approval; an optional participant declines → the meeting is kept |
| An evening out | Friends with no shared calendars; a club's fixture list that must be looked up |
| A family weekend | Saturday and Sunday slots; "Sundays before 1pm are out" |
| Mixed sources | A work trip on one person's work calendar, another's league fixtures, family calendars, all deciding one weekend plan |
| Availability from messages | A confirmed booking that counts, next to a cancelled one or an unanswered invitation that does not |
| Attacks (Week 8) | Hostile text where an agent reads it: an injected corpus page, a booking message with an instruction, a thread message claiming someone's consent ("send it now"), a poisoned memory note. Graded inverted; run 5 times each in the held-out sweep |

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
- **Approvals asked and refused** per episode (Week 8: a gate nobody refuses is placed wrongly).
- **Attack success** per attack and arm, reported next to task completion.

**Grading.** An independent checker recomputes every constraint from the ground truth. It never
trusts the agent's or the enumerator's own "valid" flag. Before trusting the numbers, we read at
least 5 passes and 5 failures, plus every critical violation.

## 9. Baselines and ablations

| Arm | What it is | Answers |
|---|---|---|
| (a) Free/busy finder | Deterministic: the earliest slot where every required participant's calendars (all of them) are free; optional participants are ignored, as in a real scheduling assistant. No natural-language preferences, no messages, no lookups, no relaxation. It assumes everyone shares every calendar: realistic at work, generous for friends and families, who rarely share any | Is the agent better than today's calendar tools? Expected to fail when only movable time, a message or an external event decides the answer |
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
- **Prompt injection via tool output.** An external agenda page, or a message, tells the agent
  to reveal calendars.
- **Misreading messages.** A cancelled booking or an invitation never accepted is treated as a
  commitment, or a confirmed appointment is missed.
- **Confused deputy** (Week 8). A thread message claims someone already agreed, and asks for an
  invite at once.
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
| 6 | Explicit control flow, approval interrupts | LangGraph graph with an approval interrupt before A4, and a new approval after an RSVP replan |
| 7 | Multi-agent: isolation, permissions, what gets passed on ("Brief"), MAST failures | Personal agents + coordinator agent; single-agent ablation |
| 8 | Guardrails, attacks on agents, the lethal trifecta, the ten-step review, evidence for autonomy | Every check in code records its verdict; caps on calls, tokens, cost and time; attack cases graded inverted; `docs/security-review.md`; arm (c) as the trifecta (private data, untrusted text and a way out in one agent) |

## 12. Stack and budget

- Python with uv, and LangGraph (as in the Week 6–7 labs).
- **OpenAI** as the LLM provider, using the course-provided keys.
- JSON sandbox: named calendars, time away, messages, holds, invites, a write log, a timeline
  and a guardrail record.
- A CLI first, and a Streamlit demo page built last, in its own dependency group: one pane per
  participant plus the request thread, the coordinator's view and the guardrails. It replays a
  saved episode for the UX recording, or runs one live with a person approving.
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
  - Each team member runs every LLM arm (b, c, d) on their 7 of the 33 held-out scenarios × 3
    runs (attack cases 5 runs), about 63 episodes.
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
| Held-out sweep | about 63 episodes per key; about 320 in total | ~USD 0.7 (measured per-episode cost, 20 Oct) | ~USD 3.5 |
| Dev iteration | Cap | ≤ USD 5 | ≤ USD 25 |
| Demo, including live web search | Hosted web search is USD 10 per 1,000 calls plus tokens; demo volume is small (one key) | — | < USD 2 |
| Reserve | Remainder of each October cap | ~USD 3 | ~USD 15 |

**Cost controls.**

- Set the reasoning effort explicitly.
- Cap model calls, tokens, cost and time per episode.
- Log tokens per episode.
- After the first 10 dev episodes, replace this estimate with measured cost and re-plan the
  sweeps.

## 13. Work plan (after the brief is agreed)

The team agreed this brief and its scope at the sync on Sat 17 Oct. Most of the build depends on
the step before it, so lanes working in parallel would wait on each other. Instead (20 Oct):
- the solution is **built end to end**, with the assistant, and committed to this repo **one
  commit per step** (18 steps), with tags at the gates. Nobody replays it;
- the steps stay as learning material, in the private guide repo: each explains its code line by
  line and quotes real outputs;
- each lane owns a section of the steps for review and presents that section;
- the team improves the finished product: changes go in as pull requests or issues, agreed
  centrally. The GitHub repo is version history for rollback, not the submission.

Lanes, owners and the steps each lane reviews are in [work-plan.md](work-plan.md).

## 14. Timeline

Work back from the internal target of **Fri 30 Oct**, leaving 31 Oct–2 Nov as buffer.

| By | Milestone |
|---|---|
| Fri 16 Oct (night) | Team members have read the brief and replied on scope and the open questions (done: GitHub issues #1–#8) |
| Sat 17 Oct | Brief and scope agreed (done at the team sync) |
| Sun 18 Oct | Work plan (lanes, owners, reviewers) agreed; build starts |
| ~~Mon 19 Oct~~ | Skeleton, contracts, 5 hand-checked scenarios, free/busy baseline (G1). Slipped: rebuilt for the 20 Oct reframe and landed with everything below |
| Thu 22 Oct | The whole build committed, one commit per step: G1 (`v0.1.0`), G2 (`v0.2.0`: end to end on dev, checker, single-call baseline) and G3 (`v0.3.0`: shared-context ablation, guardrails and attacks, held-out set frozen) |
| Sat 24 Oct | Team review of the steps by lane done; promotion threshold confirmed (the freeze stands unless the team changes the threshold before the sweep) |
| Tue 27 Oct | All arms × 3 runs on the held-out set (split across keys); failure analysis done |
| Thu 29 Oct | Deck draft; demo recorded (replay of a saved real episode) |
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
| 2026-10-15 | Workplace meetings are the primary domain; social groups are a small generalisation family. Sports is only an example of an external schedule | Overturned on 20 Oct (general-purpose); see the 2026-10-20 row |
| 2026-10-15 | Held-out sweep split across keys by scenario subset (6 scenarios per team member, all LLM arms) | Agreed by team (17 Oct sync); now 7 per member with 33 held-out scenarios (2026-10-20 rows) |
| 2026-10-15 | The agent never moves, declines or shortens a participant's existing commitments; it only asks | Agreed by team (17 Oct sync); confirmed by D7 and D8 below |
| 2026-10-15 | Environment: uv with a committed lockfile; Docker optional later, built from the same lockfile; code follows the "keep it portable" rules in §12 | Overturned at the 17 Oct sync (D3); see the 2026-10-17 row |
| 2026-10-15 | Brief and scope are confirmed first (replies by Fri 16 Oct night); swimlanes, owners and reviewers are planned from the agreed brief on Sat 17 Oct | Agreed by team (17 Oct sync); work plan moved to Sun 18 Oct |
| 2026-10-17 | Final deliverable is a 12-slide deck (not the 4-page report), due Tue 3 Nov (date assumed); internal completion target Fri 30 Oct (Q1) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Highest action: send invites, gated by the organiser's approval and stored consent; tentative holds autonomous. No room booking (Q7) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Environment: uv for development with a committed `uv.lock` and `.python-version`; a Dockerfile in the Mon 19 Oct skeleton, built from the same lockfile; keys passed at run time; code follows the "keep it portable" rules in §12 (D3, issue #3) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Workplace meetings are primary. Each participant has a sandbox work calendar and a sandbox personal calendar (family, study, medical), read only by their personal agent. No real calendar connection; the social-group family stays (D1, issue #1) | Overturned on 20 Oct (general-purpose, named calendars); see the 2026-10-20 row. "Read only by their personal agent" and "no real calendar connection" stand |
| 2026-10-17 | Autonomy is set per action and per agent (acting-agent column in §6). A participant may give pre-given consent to relaxing named movable commitments; the "Never" rows and invite approval are unchanged (D2, issue #2) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Leave is hard by default. A participant may mark a leave period reachable if urgent, which makes it relaxable only with their consent. Leave reasons stay private (D4, issue #4) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Required/optional attendee roles in the MVP, set by the organiser in the request; optional attendees count as soft (D5, issue #5) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Backup attendees are a stretch goal: named by the organiser, or proposed by the coordinator agent from a synthetic org chart; used only with the organiser's approval (D6, issues #4 and #5) | Agreed by team (17 Oct sync) |
| 2026-10-17 | After the invite: a required participant's decline triggers a replan and a new approval; an optional participant's decline keeps the meeting. Tentative and no response hand back to the organiser (stretch). The agent never ranks meetings against each other (D7, issue #6) | Agreed by team (17 Oct sync) |
| 2026-10-17 | No agent-initiated rescheduling of agreed meetings. The personal agent only alerts its participant about a clash; the participant's own decline is handled as in D7. Named as future work (D8, issue #7) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Multi-timezone meetings are out of the MVP; a stretch goal after Sat 24 Oct, only if ahead of plan (D9, issue #8) | Agreed by team (17 Oct sync) |
| 2026-10-17 | External schedules are synthetic; calendars change during an episode through scripted events; easy, stable real sources (e.g. Singapore public holidays) are used as dated snapshots (Q3) | Agreed by team (17 Oct sync) |
| 2026-10-17 | The coordinator agent sees each participant's availability summary, not only per-slot counts (Q4) | Agreed by team (17 Oct sync) |
| 2026-10-17 | Promotion threshold for an action class: mean − 1 SD ≥ 90% pass rate and zero critical violations; tunable until the held-out set is frozen (Q5) | Agreed by team (17 Oct sync) |
| 2026-10-17 | User-experience claims are described, not measured (Q6) | Agreed by team (17 Oct sync) |
| 2026-10-17 | No meeting rooms in the MVP; time slots only (Q7) | Agreed by team (17 Oct sync) |
| 2026-10-18 | Build: one guided solution in 16 steps, replayed by Kenneth into this repo (one branch and PR per step, tags at the gates); lanes become review ownership of sections of the steps; the team reviews centrally | Superseded on 20 Oct (no replay); see the 2026-10-20 row |
| 2026-10-18 | The action classes in §6 are renamed A0–A4, mapped to the course's autonomy levels, so they are not confused with week 1's L1–L5 | Proposed (Kenneth), pending team |
| 2026-10-20 | The scheduler is general-purpose, not workplace-first: any number of named calendars per participant (work is one), messages as a source the personal agent infers availability from (synthetic and sandboxed), slots on any weekday the request allows, usual hours instead of working hours, time away instead of leave. Scenarios cover work, evenings out and family weekends, about half outside work. The architecture and the availability summary are unchanged | Agreed by team (20 Oct) |
| 2026-10-20 | Week 8 (guardrails) is in scope where time allows, with weeks 1–7 the focus: every check in code records its verdict; caps on model calls, tokens, cost and time; attack cases graded inverted, run 5 times in the held-out sweep; a written security review | Agreed by team (20 Oct) |
| 2026-10-20 | A demo page (Streamlit, its own dependency group), built last, for the UX recording: it replays a saved episode pane by pane, or runs one live with a person approving. Not part of the evaluation | Agreed by team (20 Oct) |
| 2026-10-20 | Build: the solution is built end to end and committed to this repo one commit per step, with tags at the gates; no replay. The steps stay as learning material and the map for lane review; the team improves the finished product by PR or issue. The repo is version history, not the submission | Decided by Kenneth (lead), 20 Oct |
