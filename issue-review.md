# Issue review: open discussions before brief v0.5

This page summarises the 8 open [GitHub issues](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues)
as of **Sat 17 Oct 2026**, so the team can settle them before the brief is updated to v0.5.

**How to resolve.** For each decision below, reply on the linked issue with your choice, or say
"agree with the suggested default". Once a decision is settled, Kenneth will:

1. update the brief: scope, the agent's decisions, autonomy and stack;
2. record the decision in brief §16 and remove any answered §15 questions;
3. close the issue with a link to the commit.

The **suggested defaults** are Kenneth's starting points and are not decisions. Each one tries
to keep the idea while protecting the brief's core rules:

- reasons stay private;
- hard constraints are never relaxed by the agent;
- the agent never moves, declines or shortens a participant's existing commitments;
- invites need approval.

Terms follow [brief §0](brief.md#0-definitions).

---

## Decisions at a glance

| # | Issue | Question | Suggested default | Decided |
|---|---|---|---|---|
| D1 | [#1](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/1) | Who is the primary user? | Keep workplace meetings primary. Add a part-time student persona whose groups span work, study and family | |
| D2 | [#2](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/2) | Should autonomy differ by agent and by participant? | Yes, within limits. Name the acting agent in §6. A participant may pre-consent to relaxing named movable commitments; the "Never" rows still hold | |
| D3 | [#3](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/3) | Docker now, or later? | Add a Dockerfile to the Mon 19 Oct skeleton, built from `uv.lock`. Keep uv for day-to-day work | |
| D4 | [#4](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/4) | Is leave hard or soft? | Hard by default. A participant can mark a leave period "reachable if urgent", which makes it relaxable only with their private consent | |
| D5 | [#5](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/5) | Should there be required and optional attendees? | Yes, in the MVP. The organiser sets the roles in the request; optional attendees count as soft | |
| D6 | [#5](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/5), [#4](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/4) | Should there be backup attendees? | Stretch goal only. The organiser names the backup in the request, and it is used only with the organiser's approval. No hierarchy chart | |
| D7 | [#6](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/6) | How are RSVPs handled after the invite? | A required decline triggers a replan and a new approval; an optional decline keeps the meeting. Tentative or no response goes back to the organiser. No automatic ranking of meetings | |
| D8 | [#7](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/7) | Can the agent reschedule an agreed meeting when a clash arrives? | No. The personal agent alerts its participant; if they decline meeting A themselves, D7 applies. Mention it as future work | |
| D9 | [#8](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/8) | Multi-timezone meetings? | Out of the MVP. Stretch goal only if ahead of plan after Sat 24 Oct; prepare a one-line answer for Q&A | |

The brief's own open questions are still unanswered as well; see
[Still-open brief questions](#f-still-open-brief-questions-15). Q1 (report or deck) and Q7
(rooms) affect the work plan the most.

---

## A. Framing

### #1 Primary use cases: a part-time student's perspective

*[Issue #1](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/1), zexellew2024. No comments.*

**Proposed.** Frame the project around a part-time student who juggles academic, work and family
commitments, each with different kinds of constraints. Show that the agent's memory persists
across the three.

**What the brief says.**

- Workplace meetings are the primary domain, and social groups are a small generalisation family
  ([§1](brief.md#1-pitch-and-research-question); the §16 row is marked "Decided (Kenneth)").
- Preference memory per participant already persists across meetings, and groups overlap
  ([§3](brief.md#3-scope), [§7](brief.md#7-datasets-synthetic-the-generation-process-is-documented)).

**Fit or conflict.**

- The memory-across-contexts idea fits the current design.
- Making a student the *primary* user would change the pitch, the personas and the baselines,
  because free/busy finders are a workplace tool.

**Options**

1. Keep workplace meetings primary, and add one or two part-time student personas whose groups
   span work, a study group and family.
2. Replace the social-group family with a "part-time student" family.
3. Make the part-time student the primary user.

**Suggested default:** option 1. It shows memory carrying across contexts at almost no cost and
needs no re-scoping. Option 2 is also cheap if the team prefers it to the social-group family.

**Scope cost:** low for options 1 and 2. Option 3 would re-open the brief.

---

## B. Autonomy and environment

### #2 Autonomy levels: coordinator agent vs. personal agent, and per participant

*[Issue #2](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/2), zexellew2024. No comments.*

**Proposed.**

- Discuss how autonomy differs between the coordinator agent and the personal agents.
- Let each participant choose the autonomy level of their own personal agent.

**What the brief says.** [§6](brief.md#6-autonomy-level-per-action-class-proposed) sets autonomy
per *action class* (L0–L4 plus two "Never" rows). It does not say which agent acts, and
participants cannot change it.

**Fit or conflict.**

- Fits §6 well. Per-participant autonomy would also give the report a strong discussion point.
- The risk is a setting that lets a participant's agent reach the "Never" rows. Those must stay
  enforced in code whatever the setting.

**Options**

1. Add an "acting agent" column to §6 only.
2. Do option 1, and also allow one per-participant setting: **pre-given consent**. For example,
   "you may give up my focus blocks without asking me". The personal agent then answers a relax
   question itself.
3. A full autonomy profile per participant, covering several settings.

**Suggested default:** option 2. It keeps the setting small and testable. Pre-given consent is
recorded in the participant's preference memory, and the approval gate still checks it. The
"Never" rows do not change.

**Scope cost:** one new scenario family tag (pre-given consent, compared with asking), plus a
check that consent was recorded before any relaxation.

### #3 DevOps: Docker

*[Issue #3](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/3), zexellew2024. No comments.*

**Proposed.** Use Docker, because it is better industry practice than uv alone.

**What the brief says.** [§12](brief.md#12-stack-and-budget-proposed) proposes uv now and an
optional Dockerfile later, installed from the same lockfile. The "keep it portable" rules make
adding Docker about an hour's work. Keys are passed at run time and never baked into the image.

**Fit or conflict.** uv and Docker are not alternatives:

- uv manages Python and packages;
- Docker packages the result.

The only real question is *when* to add the Dockerfile.

**Options**

1. Keep §12 as it is: add a Dockerfile only when one of the listed triggers happens.
2. Add a Dockerfile to the Mon 19 Oct project skeleton. It installs with `uv sync --frozen`, and
   the demo runs with one `docker run --env-file .env ...` command.

**Suggested default:** option 2. It is cheap, it answers the industry-practice point, and it
gives the demo a one-command start. Day-to-day development stays on `uv run`.

**Scope cost:** about an hour, plus keeping the image building as dependencies change.

---

## C. Who matters and how firm constraints are

### #4 Constraint level for leave

*[Issue #4](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/4), huongiangbui.
One comment.*

**Proposed.**

- Make leave a *soft* constraint, because an urgent and important meeting may come up while
  someone is on leave.
- For short leave, the agent prioritises a slot within 1–2 days after the participant returns.
- For long leave, it informs the participant and asks for approval to meet during the leave.

**Comment (Andreojk).** Add a backup person: for example, an assistant manager covers for a
manager. The agent checks the backup's availability. If there is no backup (the CEO, say), the
agent asks for approval. Backups are covered under #5 below.

**What the brief says.**

- Leave is a hard constraint ([§0](brief.md#0-definitions), worked example in
  [§5](brief.md#5-decisions-the-agent-makes)).
- [§6](brief.md#6-autonomy-level-per-action-class-proposed) says the agent **never** relaxes a
  hard constraint.
- Relaxing a soft constraint or a movable commitment always needs the participant's private
  consent.

**Fit or conflict.**

- Plain "leave is soft" conflicts with the "Never" row, because the agent could then schedule
  into someone's leave on its own judgement.
- The intent fits the existing *relax with consent* mechanism. The participant, not the agent,
  decides that a given leave period can be interrupted.

**Options**

1. Leave stays hard. Hand back to the organiser when leave blocks every slot.
2. Leave is hard by default. A participant can mark a leave period **"reachable if urgent"**,
   which makes it relaxable with their private consent, exactly like a movable focus block. The
   leave reason stays private.
3. Leave is soft everywhere, scored by distance from the return date.

**Suggested default:** option 2. It keeps the "never relax a hard constraint" rule, and it still
covers the urgent case. "Prefer the first 1–2 days after the participant returns" can be a soft
preference the organiser adds to the request.

**Scope cost:** the enumerator treats marked leave as relaxable. Add scenarios to the existing
"nobody fully free → ask → relax → replan" family. The privacy filter must stop "B is on leave"
from appearing in the request thread; it already checks for this.

### #5 Required / optional / backup attendee roles

*[Issue #5](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/5), Andreojk.
One comment.*

**Proposed.** Participants are not equally important, so give each one a role. The organiser
still gives final approval.

1. **Required:** the meeting cannot go ahead without them, e.g. the lead analyst.
2. **Optional:** useful but not needed.
3. **Backup:** stands in for a required participant who is unavailable, e.g. when the manager is
   on leave. The scheduler checks whether an approved backup can attend before pushing the
   meeting back.

**Comment (NJYao).** For backups, either assume every participant has one listed, or give the
coordinator agent a hierarchy chart. It would then invite someone at the same or the next level
when the original participant cannot attend.

**What the brief says.**

- Every participant counts equally today.
- The organiser's request already carries room needs, and these do not go through the
  availability summaries ([§4](brief.md#4-architecture-proposed)).

**Fit or conflict.**

- **Required/optional fits cleanly.** The organiser states roles in the request. The enumerator
  treats an optional participant's availability as soft. The availability summary does not
  change.
- **Backups raise two issues:**
  - **Privacy:** substituting a backup tells the group that the original participant can't
    attend, so the request thread must not say *why*.
  - **Approval:** a backup changes who is invited, so the organiser must approve it, and §6
    already gates invites.
- **A hierarchy chart** is new data, and choosing a substitute from it would be the agent
  deciding who represents someone. That is a larger autonomy question.

**Options**

1. Required/optional only.
2. Required/optional in the MVP, plus **organiser-named backups as a stretch goal**. The
   organiser names a backup in the request ("B, or B's deputy B2"). The coordinator agent
   proposes the backup only when no slot works with the required participant, and only with the
   organiser's approval.
3. All three roles plus a hierarchy chart.

**Suggested default:** option 2. Required/optional is cheap and makes the slot choice more
realistic. Backups are useful but add a new approval path, so they wait until the core
evaluation runs. No hierarchy chart.

**Scope cost:**

- Required/optional: a role field in the request, an enumerator change, and one scenario family
  tag.
- Backups (stretch): an approval path, scenarios, and privacy probes for "why was B replaced?".

---

## D. After the invite

### #6 RSVP calendar handling

*[Issue #6](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/6), Andreojk.
One comment.*

**Proposed.** Outlook and Teams invites can be accepted, marked tentative, declined, or left
unanswered. After an invite goes out:

1. a required participant declines → re-plan;
2. an optional participant declines → keep the meeting;
3. a required participant is tentative → the organiser decides whether to go ahead;
4. a required participant does not respond by a deadline → loop back without chasing them.

**Comment (NJYao).** Use the required/optional roles to rank meetings when two clash:

- if the participant is required in one meeting and not the other, decline the other;
- if they are required in both, score the meetings (e.g. by the number of confirmed
  participants or another importance measure), or escalate to the participant.

**What the brief says.**

- The "Approval / stale slot" scenario family ([§8](brief.md#8-eval-sets-and-metrics)) already
  covers a change after approval: no write, replan, new approval.
- "Replan" is one of the agent's decisions ([§5](brief.md#5-decisions-the-agent-makes)).
- The agent never declines a participant's commitments ([§3](brief.md#3-scope),
  [§6](brief.md#6-autonomy-level-per-action-class-proposed)).

**Fit or conflict.**

- Cases 1–3 fit the existing replan and hand-back decisions well.
- Case 4 needs simulated time passing, which the scenarios do not model yet.
- The comment's idea of the agent declining one of two clashing meetings conflicts with the
  "never declines" rule. Escalating to the participant fits.

**Options**

1. Out of scope: the run ends when the invite is sent and verified.
2. **Decline only:**
   - a scripted RSVP event in the scenario;
   - a required decline triggers a replan and a new approval;
   - an optional decline keeps the meeting.
3. Do option 2, plus tentative and no-response. Both hand back to the organiser; no-response
   needs a simulated deadline.

**Suggested default:** option 2, with option 3 as a stretch goal. For clashes, the agent never
picks a winner; the personal agent tells its participant, who decides (see #7).

**Scope cost:** a scripted post-invite event type, and one scenario family tag (or an extension
of "Approval / stale slot"). The checker verifies that the meeting is replanned and re-approved
after a required decline and that no write happens without a new approval.

### #7 Rescheduling after the initial schedule is settled

*[Issue #7](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/7), NJYao. No comments.*

**Proposed.**

- Meeting A is agreed first. Later, a participant is invited to meeting B, which clashes with A.
- If the participant's personal agent judges B more important, should it trigger meeting A's
  coordinator agent to reschedule A?

Suggested rules:

- If A is less than 5 days away, or a tool gives it a high importance score, the personal agent
  must ask the participant. The choices are: accept B and decline A, decline B, or another
  option.
- Alternatively, limit the scope to first-time scheduling, with no feedback loop.

**What the brief says.**

- "Several meetings scheduled together" is out of scope ([§3](brief.md#3-scope)).
- The agent never moves, declines or shortens an existing commitment; it only asks
  ([§3](brief.md#3-scope), [§6](brief.md#6-autonomy-level-per-action-class-proposed)).

**Fit or conflict.**

- A personal agent that judges B more important and acts on it conflicts with the "never
  declines" rule.
- It would also mean the agent decides between two organisers' meetings, which affects people
  outside the request.
- The "ask the participant" version fits.

**Options**

1. Out of scope: first-time scheduling only. Name it as future work in the report.
2. **The personal agent alerts its participant** about the clash and does nothing else. If the
   participant declines A themselves, that is a required decline on A, which #6 already covers:
   meeting A replans and needs a new approval.
3. Agent-initiated cross-meeting rescheduling with an importance score.

**Suggested default:** option 2. If #6 is not adopted, fall back to option 1. Option 3 breaks a
core rule and is a different project.

**Scope cost:** almost none on top of #6. It reuses the required-decline replan.

---

## E. Stretch

### #8 Multi-timezone

*[Issue #8](https://github.com/code-vibes-only/cs621-agentic-ai-project/issues/8), Andreojk. No comments.*

**Proposed.** This is a stretch idea, noted in case the professor asks. When Singapore
participants must meet required decision makers in the US or UK, the agent should:

1. identify the infeasible hours and who they affect;
2. find the least disruptive slot for both sides;
3. ask the affected Singapore participants for explicit approval.

**What the brief says.** Multi-timezone meetings are out of scope
([§3](brief.md#3-scope)), and the MVP uses one timezone (Asia/Singapore).

**Fit or conflict.** It fits the design. Each participant has working hours in their own
timezone, and slots outside those hours become soft and relaxable only with consent: the same
relax mechanism. The cost is in the data and the checker, because every timestamp and
working-hours rule becomes timezone-aware.

**Options**

1. Keep it out of scope and prepare a one-line answer for Q&A.
2. Stretch goal: start it after Sat 24 Oct (held-out set frozen) only if ahead of plan, with
   2–3 extra scenarios.
3. Add it to the MVP now.

**Suggested default:** option 1 for the MVP and option 2 if time allows. For Q&A: "The design
supports it, because out-of-hours slots are just relaxable time with consent. We kept one
timezone so that we could evaluate the core question properly."

**Scope cost:** medium. It touches timestamps everywhere, the scenario generator and the checker.

---

## F. Still-open brief questions (§15)

None of the issues answers these yet. Please answer them in the same pass, on a new issue or in
the team chat.

| # | Question (from [brief §15](brief.md#15-open-questions)) | Decided |
|---|---|---|
| 1 | Final format: 4-page report or 12-slide deck? | |
| 3 | External schedules: fictional sources, or dated snapshots of real ones? Singapore public holidays, for example, are real and stable | |
| 4 | Should the coordinator agent see each participant's availability summary, or only the count of available participants per slot? Per-participant summaries let it ask the right participant before relaxing; counts are more private | |
| 5 | Promotion threshold for an action class (e.g. mean − 1 SD ≥ 90%, 0 critical violations)? | |
| 6 | How do we measure the user-experience claims: a small walkthrough with classmates, or descriptive only? | |
| 7 | Meeting rooms in the MVP, or time slots only? | |

Q1 sets the shape of the final deliverable, and Q7 decides whether rooms are worked on at all.
Both are needed for the work plan.

**Note on Q4.**

- Required/optional roles (#5) and backups both assume the coordinator agent knows *which*
  participant is unavailable. That needs per-participant summaries.
- Choosing "counts only" for Q4 would rule out #5 and #6 as suggested.

---

## Scope check

If every suggested default is adopted, the MVP gains:

- 2–3 scenario family tags: attendee roles, required decline after the invite, and pre-given
  consent;
- "reachable if urgent" leave as a new relaxable case in an existing family;
- enumerator support for optional attendees;
- a Dockerfile in the skeleton.

Stretch goals, only if ahead of plan after Sat 24 Oct:

- organiser-named backups;
- RSVP tentative and no-response handling;
- multi-timezone.

**Risk.** Every addition needs ground truth, scripted replies and checker support before the
held-out set is frozen on **Sat 24 Oct**. If the plan slips, the agreed scope-cut order still
applies:

1. the Streamlit UI (keep the CLI);
2. meeting rooms;
3. the social-group family.

Stretch items are dropped before any of these.
