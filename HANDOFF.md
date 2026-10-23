# Handoff

The shared state of the project, for team members and for AI agent sessions (Claude Code,
Codex, Cursor and similar). Read it at the start of a session; update it at the end.

Last updated: **21 Oct 2026**, by Kenneth (with Claude Code). Stage: **brief v0.7. The whole
build is in this repo, one commit per step (18), tagged `v0.1.0`–`v0.3.0`: a general-purpose
scheduler with Week 8 guardrails, attack cases, a frozen held-out set and a demo page. Next: the
team reviews by lane, then runs the held-out sweep (Tue 27 Oct).**

## How to use this file

**Starting a session**

1. Read this file top to bottom.
2. Read the parts of [brief.md](brief.md) your task touches. Always read §0 (definitions). Read
   §15 (open questions) and §16 (decision log) before changing anything that a decision covers.
3. Run `git pull` and skim `git log --oneline -15` for changes since the last session log entry.

**Ending a session**

1. Update [Current state](#current-state), [Milestones](#milestones) and
   [Next actions](#next-actions) so they describe the state *after* your session.
2. Add one row to the [session log](#session-log): what changed, which commits, what is next.
3. Record design decisions in **brief.md §16**, not here. When a team decision answers an open
   question, remove it from §15.
4. Commit the handoff update together with the work it describes.

**Where things live (one source of truth each)**

| What | Where |
|---|---|
| Design, definitions, scope, evaluation plan, budget | [brief.md](brief.md) |
| Decisions and their status (proposed / agreed) | brief.md §16 |
| Open questions | brief.md §15 |
| Record of the GitHub issue discussions (resolved at the 17 Oct sync; decisions now in brief §16) | [issue-review.md](issue-review.md) |
| Work plan: lanes, owners, contracts, gates, deck slides | [work-plan.md](work-plan.md) |
| Current state, next actions, session history | this file |
| Rules for AI agents working in the repo | [AGENTS.md](AGENTS.md) |
| Evaluation results | result files committed under `results/` (once they exist); every number in the report traces to one |

## Current state

- **Repo:** the project docs, plus the full build, one commit per step on `main` (`a4b5578` …
  `2269de6`), tags `v0.1.0` (step 07), `v0.2.0` (13) and `v0.3.0` (16). 62 tests pass from a clean
  clone (`uv sync --group demo && uv run pytest`); the Docker image runs the same commands.
- **Build approach (20 Oct):** built end to end and committed step by step; nobody replays it. The
  steps (learning material, one per commit, with real outputs) are in the private guide repo
  `code-vibes-only/cs621-scheduler-guide`. Lane owners review their steps next to the commits; the
  team improves the product by PR or issue. See [work-plan.md](work-plan.md).
- **Topic (agreed, reframed 20 Oct):** a general-purpose Agentic Natural Language Scheduler: any
  number of named calendars per participant, messages as a source the personal agent infers from,
  slots on any weekday. Scenarios cover work, evenings out and family weekends (about half outside
  work). Brief v0.7 §0–§3, §16.
- **Data:** 26 dev scenarios (5 hand-checked) and 33 held-out (frozen at `v0.3.0`, including three
  privacy probes and three attack cases). Nobody has run an agent on the held-out set.
- **Week 8 (guardrails):** every check in code records its verdict; caps on calls, tokens, USD and
  seconds; attack cases graded inverted; `docs/security-review.md`.
- **Demo:** `uv run --group demo python -m streamlit run scheduler/demo/app.py` replays a saved
  episode pane by pane (a real dev-022 episode is in `results/demo/`), or runs one live with you
  approving. On branch `feat/demo-tabs` (local, not yet proposed to the team): a live, shared demo
  world instead (`run-demo.bat`, or the command above): ten fictional people in three circles,
  group chats with a private "My agent" chat each, calendars, Actions, and a trace with a
  timeline. A request runs the real personal agents and coordinator agent; people answer their
  own agent's questions. "Enable model calls" is off by default (scripted agents, no cost).
- **Results so far (dev, real `gpt-5-mini`, mean ± sample SD over 3 runs; files under `results/`):**
  - seven dev scenarios (`results/dev7/`): our design (d) 0.95 ± 0.08, single call (b)
    0.62 ± 0.08, free/busy (a) 0.29 ± 0.00; (d) costs about USD 0.011 and 49 s per episode;
  - privacy, dev-001 and the dev probe (`results/privacy-dev/`): no leak from either arm; the
    shared-context arm (c) passed 0.33 ± 0.29 against (d)'s 0.83 ± 0.29, failing mostly on
    over-asking;
  - attacks, three dev cases (`results/attack-dev/`): no attack worked on either arm; in one run (c)
    obeyed an injected message and drafted a post of everyone's calendar entries, which the privacy
    filter blocked.

  These are dev numbers; the deck reports the held-out sweep.
- **Spend:** building the solution used about USD 1.35 of Kenneth's key (cap USD 2). No team key
  has been used.

## Milestones

From brief §14. Internal completion target **Fri 30 Oct**; submission and presentation **Tue
3 Nov**.

| By | Milestone | Status |
|---|---|---|
| Fri 16 Oct (night) | Team members have read the brief and replied on scope and the open questions | Done: replies came as GitHub issues #1–#8; §15 questions answered at the 17 Oct sync |
| Sat 17 Oct | Brief and scope agreed; work plan (swimlanes, owners, reviewers) agreed; build starts | Partly done: brief and scope agreed at the 17 Oct sync (brief v0.5); work plan moved to Sun 18 Oct |
| Mon 19 Oct | Project skeleton with Dockerfile; availability summary schema and scenario format frozen; 5 hand-checked scenarios; free/busy baseline; first measured cost per episode | Done late (21 Oct), rebuilt for the 20 Oct reframe: tag `v0.1.0` |
| Thu 22 Oct | End to end on the dev set; checker; single-call baseline | Done early (21 Oct): tag `v0.2.0` |
| Sat 24 Oct | Held-out set frozen; shared-context ablation; privacy probes | Done early (21 Oct), with guardrails and attack cases: tag `v0.3.0`. The team confirms the promotion threshold and reviews by lane by Sat 24 Oct |
| Tue 27 Oct | All arms × 3 runs on held-out (split across keys); failure analysis | Not started |
| Thu 29 Oct | Deck draft (12 slides); demo recorded | Not started; the demo page is built (step 18) |
| Fri 30 Oct | Complete | Not started |
| 31 Oct – 2 Nov | Buffer | — |
| Tue 3 Nov | Submit and present | — |

## Team and work plan

The work plan is in [work-plan.md](work-plan.md). It covers:
- the five lanes as **review ownership**, with the steps each lane reviews;
- how a review works;
- the contracts, which freeze at G1;
- the gates G1–G3 with tags `v0.1.0` to `v0.3.0`;
- the budget and the deck slides.

Lanes were assigned at random on 18 Oct; the final pairing, after any swaps, is recorded there,
not here.

## Next actions

| # | Action | Owner | Due |
|---|---|---|---|
| 1 | Everyone accepts their repo invites: this repo (still pending for zexellew2024, huongiangbui, Andreojk) and the guide repo | All | Thu 22 Oct |
| 2 | Confirm your assigned review lane or report a swap; Kenneth records the final owners in work-plan.md | All | Thu 22 Oct |
| 3 | Close issues #1–#8, each with a link to the brief v0.5 commit | Kenneth | Thu 22 Oct |
| 4 | Review your lane's steps against their commits (guide repo); raise changes as PRs or issues here | L1–L5 owners | Sat 24 Oct |
| 5 | Confirm the promotion threshold (mean − 1 SD ≥ 90%, zero critical) or agree a change with dev evidence; object to the A0–A4 rename or the reframe if you disagree (brief v0.7 §16) | All | Sat 24 Oct |
| 6 | Optional: the full dev run (23 × 3 runs × arms b, d, about USD 1; guide step 13 §5) | Any one member | Sat 24 Oct |
| 7 | Held-out sweep: each member runs `--sweep N --tag heldout-final` on their own key (7 scenarios, about 63 episodes, about USD 0.6, about an hour) and commits the results; anyone runs arm (a) once | All | Tue 27 Oct |
| 8 | Record the demo: replay `results/demo/` (and an arm (c) run) on the demo page | Kenneth | Thu 29 Oct |

## Risks and blockers

- **Budget is per key and cannot be pooled.** A debugging loop can burn one person's USD 10.
  Cap model calls per episode and log tokens from the first run.
- **The model may be deprecated.** OpenAI's page shows a "Deprecated" label on `gpt-5-mini`
  (checked 15 Oct). Confirm availability before freezing the model.
- **The held-out set is frozen.** A change to prompts, code or the threshold now needs dev evidence,
  a §16 row and a full held-out rerun. Keep changes before the sweep small.
- **Sweep time.** About an hour per member (our design takes 50–70 s an episode). Start early on
  Tue 27 Oct.
- **Public repo.** No keys, no course PDFs or slides, and no real personal data.

## Comms log

Messages sent to the team or the instructors. Log a message once it has actually been sent.

| Date | To | Channel | Summary |
|---|---|---|---|
| 2026-10-15 | Team (all team members) | Team chat | Shared brief v0.4 with a summary. Asked everyone to read it (start with §0), reply on scope and §15 (esp. report vs. deck) and accept the repo invite by Fri 16 Oct night. Brief locked and work split on Sat 17 Oct; build starts that weekend. House rules: public repo, keys in local `.env`; AI tools read AGENTS.md and update HANDOFF.md |
| 2026-10-17 | Team (all team members) | WhatsApp | Shared the link to `issue-review.md` (issues #1–#8 with suggested defaults). Asked everyone to go through the issues today, and proposed a quick sync tonight (around 23:00) to close them out. After that, Kenneth updates the brief to v0.5, closes the issues and drafts the work plan |
| 2026-10-18 | Team (all team members) | WhatsApp | Change of plan: one guided solution in 16 steps, which Kenneth replays into the repo one PR per step; lanes are now review ownership. Linked `work-plan.md` and the private guide repo, and asked people to raise changes as issues or PR comments, not pushes. Review lanes randomly assigned (L1 huongiangbui, L2 Andreojk, L3 zexellew2024, L4 Kenneth, L5 NJYao); team may swap among themselves and report the final pairing. By Mon 19 Oct morning: accept both invites (nudged zexellew2024, huongiangbui, Andreojk on the pending project-repo invite), confirm lanes, raise objections to the approach or the A0–A4 rename. G1 Mon 19 Oct |

## Session log

Newest last. One row per working session, human or agent.

| Date | Who | What changed | Commits | Next |
|---|---|---|---|---|
| 2026-10-15 | Kenneth + Claude Code | Created the repo clone; drafted brief v0.1 → v0.3. Answered: due 3 Nov with a 30 Oct target; OpenAI with per-person USD 10 keys; workplace-first domain; participant/team-member naming; uv now with Docker optional. Added `.gitignore`, this handoff and the agent instructions | `751c3fb` brief v0.3; `b781274` .gitignore; `a62dbd8` handoff and agent instructions | Team review of the brief (next actions 1–3) |
| 2026-10-15 | Kenneth + Claude Code | Brief v0.4: workstreams removed until the brief and scope are agreed; review brought forward to Fri 16 Oct night; work plan on Sat 17 Oct so the build starts that weekend. Q8 (roster and owners) moved to the work plan | brief v0.4 (this commit) | Team replies by Fri 16 Oct night (next actions 1–2) |
| 2026-10-17 | Kenneth + Claude Code | Team feedback arrived as GitHub issues #1–#8. Summarised them in `issue-review.md`: 9 decisions (D1–D9) with suggested defaults, plus the remaining §15 questions and a scope check. Brief unchanged until the team decides | `2b029b0` issue review and handoff | Team resolves `issue-review.md` (next action 3a); then brief v0.5 and the work plan |
| 2026-10-18 | Kenneth + Claude Code | Team sync (Sat 17 Oct night) resolved D1–D9 and §15 Q1, Q3–Q7; Kenneth filled in `issue-review.md`. Brief v0.5 records them: 12-slide deck; no meeting rooms; personal calendar per participant; required/optional attendees; leave reachable if urgent; pre-given consent and an acting-agent column in §6; RSVP decline handling; Dockerfile in the skeleton; promotion threshold mean − 1 SD ≥ 90%. Older §16 rows agreed, except environment, highest action and report/deck, which the sync overturned | brief v0.5 (this commit) | Close issues #1–#8 (next action 3); draft the work plan (next action 4) |
| 2026-10-18 | Kenneth + Claude Code | Committed and pushed brief v0.5. Drafted `work-plan.md` (proposed): five lanes with Consumes/Produces, first tasks and reviewer lanes; contracts C1–C5 frozen at G1; gates G1–G5; budget by lane; 12-slide deck map. Owners left blank for the team to claim. Brief §13 and HANDOFF now point to it | `dad3b3d` brief v0.5; work plan (this commit) | Team claims lanes by Mon 19 Oct morning (next action 4); close issues #1–#8 (next action 3) |
| 2026-10-18 | Kenneth + Claude Code | Switched the build to one guided solution (`/guided-task`). The steps, contracts and a tested solution live in a private guide repo, not here. The solution is complete: 47 tests pass, the 16 steps align with it exactly, and every example output comes from a real run (about USD 0.48). On the five hand-checked scenarios, 3 runs: our design 1.00 ± 0.00, single call 0.60, free/busy 0.20. Brief v0.6 adds the build-approach row and the A0–A4 rename (both proposed, pending team); work-plan.md is reframed as review ownership | guide released to `code-vibes-only/cs621-scheduler-guide`; brief v0.6 (this commit) | Team agrees the approach and claims review lanes (next action 4); everyone accepts the invites (1); Kenneth replays from step 01 (6) |
| 2026-10-21 | Kenneth + Claude Code | The team reframed the scheduler as general-purpose (20 Oct). Built end to end: named calendars, messages, any weekday, three settings and three new scenario families; Week 8 guardrails (verdict record, four caps, attack cases graded inverted, security review); a demo page. 18 steps aligned with real outputs; landed here one commit per step with tags `v0.1.0`–`v0.3.0`. Brief v0.7, `work-plan.md` and `AGENTS.md` updated. Real runs about USD 0.87 this session (USD 1.35 in all) | `a4b5578`…`2269de6`; tags; docs (this commit) | Team review by lane and threshold confirmation by Sat 24 Oct (next actions 2, 4, 5); held-out sweep Tue 27 Oct (7) |
| 2026-10-21 | zexellew2024 + Claude Code | On local branch `feat/demo-tabs`: the demo page gets a sign-in (five fictional people plus `demo_admin`, logins in `data/demo/users.json`) and role-based tabs: chat (the thread, private questions, organiser-only steps), calendars (each person's private calendar next to the availability summary their agent shared, and a group overlap grid for the organiser), tasks, private data, and an admin trace (timeline, guardrails, tool calls, writes, leak check). `scheduler/demo/seed.py` writes three demo requests (evenings with a private consent question, weekends decided by a message, a lunchtime with an optional attendee) to `data/demo/`, outside the evaluation sets, and scripted fake-model runs to `results/demo-seed/`. 66 tests pass. No model spend | (this commit) | Propose it to Kenneth as an issue before a PR (the demo is L1's and the lead's) |
| 2026-10-23 | zexellew2024 + Claude Code | Still local on `feat/demo-tabs`: the demo becomes one live, shared world (`scheduler/demo/`: `store.py` SQLite state, `seed.py` ten people and three circles, `engine.py` a request as a real run, `analyse.py` Add and analyse, `app.py` Groups and Calendar). A private message to your agent is read (dates from the group chat), sent to the coordinator agent, which acknowledges it; personal agents answer from their calendars and ask their person only what they need: a yes/maybe/no on an "ask me first" item (a 0-3 flexibility scale), "I'll check and get back to you", or a time suggested instead (inside the window it steers the ranking; outside, the search restarts with it and everyone's availability decides). "Check with me before accepting" is enforced in code. Questions asked together run in parallel; the organiser sees who has answered, never why; a run lost in a server restart stops cleanly. When nothing fits, the host's agent widens the search once. Trace adds a timeline (who called which tool, when). Two core changes, to flag to Kenneth: `world.scripted_reply` and `ask_my_participant` pass the agent's question through (no behaviour change for the scripts). The old saved demo scenarios and `results/demo-seed/` are removed. 89 tests pass. Real-model checks about USD 0.05 in all, plus the person's own browser runs | (this commit) | Propose it to Kenneth as an issue before a PR; ideas for him: round 2 re-reads every calendar (a shared board would save about half its calls), and the demo can hit the 40-call cap |
