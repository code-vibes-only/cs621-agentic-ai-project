# Handoff

The shared state of the project, for team members and for AI agent sessions (Claude Code,
Codex, Cursor and similar). Read it at the start of a session; update it at the end.

Last updated: **18 Oct 2026**, by Kenneth (with Claude Code). Stage: **brief v0.5 records the
decisions from the team sync on Sat 17 Oct (GitHub issues #1–#8 and the open questions); the
work plan is next.**

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

- **Repo:** contains `brief.md` (draft v0.5), `work-plan.md` (proposed), `issue-review.md`, `.gitignore`, this file and `AGENTS.md` /
  `CLAUDE.md`. There is no code, `pyproject.toml` or data yet.
- **Topic (agreed):** Agentic Natural Language Scheduler. Workplace meetings are the primary
  domain; social groups are a small generalisation family.
- **Design status:** agreed at the team sync on Sat 17 Oct. Every brief §16 row is agreed or
  overturned; changes need the team's agreement and a new §16 row.
- **Scope changes at the sync:** no meeting rooms (time slots only); a personal calendar per
  participant; required/optional attendees; leave reachable if urgent; pre-given consent; RSVP
  decline handling; a Dockerfile in the skeleton. Stretch: backups, RSVP tentative/no response,
  multi-timezone.
- **Provider and budget:** OpenAI, one key per team member, capped at USD 10 per calendar month.
  No API calls have been made yet and no money has been spent.
- **Results:** none. Nothing has been measured.

## Milestones

From brief §14. Internal completion target **Fri 30 Oct**; submission and presentation **Tue
3 Nov**.

| By | Milestone | Status |
|---|---|---|
| Fri 16 Oct (night) | Team members have read the brief and replied on scope and the open questions | Done: replies came as GitHub issues #1–#8; §15 questions answered at the 17 Oct sync |
| Sat 17 Oct | Brief and scope agreed; work plan (swimlanes, owners, reviewers) agreed; build starts | Partly done: brief and scope agreed at the 17 Oct sync (brief v0.5); work plan moved to Sun 18 Oct |
| Mon 19 Oct | Project skeleton with Dockerfile; availability summary schema and scenario format frozen; 5 hand-checked scenarios; free/busy baseline; first measured cost per episode | Not started |
| Thu 22 Oct | End to end on the dev set; checker; single-call baseline | Not started |
| Sat 24 Oct | Held-out set frozen; shared-context ablation; privacy probes | Not started |
| Tue 27 Oct | All arms × 3 runs on held-out (split across keys); failure analysis | Not started |
| Thu 29 Oct | Deck draft (12 slides); demo recorded | Not started |
| Fri 30 Oct | Complete | Not started |
| 31 Oct – 2 Nov | Buffer | — |
| Tue 3 Nov | Submit and present | — |

## Team and work plan

The work plan is in [work-plan.md](work-plan.md): five lanes (L1 platform and harness, L2
world and data, L3 personal agent and privacy, L4 coordinator and control, L5 evaluation and
baselines), contracts C1–C5 frozen at G1, gates G1–G5 and the deck slides. It is **proposed**
until every lane has an owner. Owners are recorded there, not here.

## Next actions

| # | Action | Owner | Due |
|---|---|---|---|
| 1 | Everyone accepts their repo invite (invites and the brief were sent on 15 Oct) | All | Fri 16 Oct |
| 3 | Close issues #1–#8, each with a link to the brief v0.5 commit | Kenneth | After the v0.5 commit |
| 4 | Review [work-plan.md](work-plan.md) and claim a lane in the team chat; Kenneth records the owners | All | Mon 19 Oct morning |
| 5 | Set up the project skeleton: `uv init`, `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, a Dockerfile built from `uv.lock` (`uv sync --frozen`), package layout following the brief's "keep it portable" rules | L1 | Mon 19 Oct |
| 6 | Freeze contracts C1–C5 (availability summary, scenario format, tools, result file, constraints) | L3, L2, L1; Kenneth signs off | Mon 19 Oct |
| 7 | Hand-check 5 scenarios and run the free/busy baseline and checker on them | L2, L5 | Mon 19 Oct |
| 8 | Confirm `gpt-5-mini` is still available; measure real cost on the first 10 dev episodes | L5 with L1 | Mon 19 Oct |
| 9 | When the Week 8 (safety, oversight, governance) lecture is released on 20 Oct, update the brief's §11 Week 8 row | Kenneth | Wed 21 Oct |

## Risks and blockers

- **Budget is per key and cannot be pooled.** A debugging loop can burn one person's USD 10.
  Cap model calls per episode and log tokens from the first run.
- **The model may be deprecated.** OpenAI's page shows a "Deprecated" label on `gpt-5-mini`
  (checked 15 Oct). Confirm availability before freezing the model.
- **Tight timeline.** It is 12 days to the internal target. Stretch goals are dropped first.
  Then, in this order if needed: the Streamlit UI (keep the CLI), then the social-group family.
  Meeting rooms are already out.
- **More MVP scope since the sync.** Attendee roles, pre-given consent, reachable-if-urgent leave
  and RSVP declines each need ground truth, scripted events and checker support before the
  held-out set is frozen on Sat 24 Oct.
- **Public repo.** No keys, no course PDFs or slides, and no real personal data.

## Comms log

Messages sent to the team or the instructors. Log a message once it has actually been sent.

| Date | To | Channel | Summary |
|---|---|---|---|
| 2026-10-15 | Team (all team members) | Team chat | Shared brief v0.4 with a summary. Asked everyone to read it (start with §0), reply on scope and §15 (esp. report vs. deck) and accept the repo invite by Fri 16 Oct night. Brief locked and work split on Sat 17 Oct; build starts that weekend. House rules: public repo, keys in local `.env`; AI tools read AGENTS.md and update HANDOFF.md |
| 2026-10-17 | Team (all team members) | WhatsApp | Shared the link to `issue-review.md` (issues #1–#8 with suggested defaults). Asked everyone to go through the issues today, and proposed a quick sync tonight (around 23:00) to close them out. After that, Kenneth updates the brief to v0.5, closes the issues and drafts the work plan |

## Session log

Newest last. One row per working session, human or agent.

| Date | Who | What changed | Commits | Next |
|---|---|---|---|---|
| 2026-10-15 | Kenneth + Claude Code | Created the repo clone; drafted brief v0.1 → v0.3. Answered: due 3 Nov with a 30 Oct target; OpenAI with per-person USD 10 keys; workplace-first domain; participant/team-member naming; uv now with Docker optional. Added `.gitignore`, this handoff and the agent instructions | `751c3fb` brief v0.3; `b781274` .gitignore; `a62dbd8` handoff and agent instructions | Team review of the brief (next actions 1–3) |
| 2026-10-15 | Kenneth + Claude Code | Brief v0.4: workstreams removed until the brief and scope are agreed; review brought forward to Fri 16 Oct night; work plan on Sat 17 Oct so the build starts that weekend. Q8 (roster and owners) moved to the work plan | brief v0.4 (this commit) | Team replies by Fri 16 Oct night (next actions 1–2) |
| 2026-10-17 | Kenneth + Claude Code | Team feedback arrived as GitHub issues #1–#8. Summarised them in `issue-review.md`: 9 decisions (D1–D9) with suggested defaults, plus the remaining §15 questions and a scope check. Brief unchanged until the team decides | `2b029b0` issue review and handoff | Team resolves `issue-review.md` (next action 3a); then brief v0.5 and the work plan |
| 2026-10-18 | Kenneth + Claude Code | Team sync (Sat 17 Oct night) resolved D1–D9 and §15 Q1, Q3–Q7; Kenneth filled in `issue-review.md`. Brief v0.5 records them: 12-slide deck; no meeting rooms; personal calendar per participant; required/optional attendees; leave reachable if urgent; pre-given consent and an acting-agent column in §6; RSVP decline handling; Dockerfile in the skeleton; promotion threshold mean − 1 SD ≥ 90%. Older §16 rows agreed, except environment, highest action and report/deck, which the sync overturned | brief v0.5 (this commit) | Close issues #1–#8 (next action 3); draft the work plan (next action 4) |
| 2026-10-18 | Kenneth + Claude Code | Committed and pushed brief v0.5. Drafted `work-plan.md` (proposed): five lanes with Consumes/Produces, first tasks and reviewer lanes; contracts C1–C5 frozen at G1; gates G1–G5; budget by lane; 12-slide deck map. Owners left blank for the team to claim. Brief §13 and HANDOFF now point to it | `dad3b3d` brief v0.5; work plan (this commit) | Team claims lanes by Mon 19 Oct morning (next action 4); close issues #1–#8 (next action 3) |
