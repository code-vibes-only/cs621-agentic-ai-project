# Handoff

The shared state of the project, for team members and for AI agent sessions (Claude Code,
Codex, Cursor and similar). Read it at the start of a session; update it at the end.

Last updated: **15 Oct 2026**, by Kenneth (with Claude Code). Stage: **brief drafted (v0.4);
team confirms brief and scope by Fri 16 Oct night.**

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
| Current state, owners, next actions, session history | this file |
| Rules for AI agents working in the repo | [AGENTS.md](AGENTS.md) |
| Evaluation results | result files committed under `results/` (once they exist); every number in the report traces to one |

## Current state

- **Repo:** contains `brief.md` (draft v0.4), `.gitignore`, this file and `AGENTS.md` /
  `CLAUDE.md`. There is no code, `pyproject.toml` or data yet.
- **Topic (agreed):** Agentic Natural Language Scheduler. Workplace meetings are the primary
  domain; social groups are a small generalisation family.
- **Design status:** every design choice in the brief is *proposed* until the team agrees it.
- **Provider and budget:** OpenAI, one key per team member, capped at USD 10 per calendar month.
  No API calls have been made yet and no money has been spent.
- **Results:** none. Nothing has been measured.

## Milestones

From brief §14. Internal completion target **Fri 30 Oct**; submission and presentation **Tue
3 Nov**.

| By | Milestone | Status |
|---|---|---|
| Fri 16 Oct (night) | Team members have read the brief and replied on scope and the open questions | In progress: brief shared for review |
| Sat 17 Oct | Brief and scope agreed; work plan (swimlanes, owners, reviewers) agreed; build starts | Not started |
| Mon 19 Oct | Availability summary schema and scenario format frozen; 5 hand-checked scenarios; free/busy baseline; first measured cost per episode | Not started |
| Thu 22 Oct | End to end on the dev set; checker; single-call baseline | Not started |
| Sat 24 Oct | Held-out set frozen; shared-context ablation; privacy probes | Not started |
| Tue 27 Oct | All arms × 3 runs on held-out (split across keys); failure analysis | Not started |
| Thu 29 Oct | Report/deck draft; demo recorded | Not started |
| Fri 30 Oct | Complete | Not started |
| 31 Oct – 2 Nov | Buffer | — |
| Tue 3 Nov | Submit and present | — |

## Team and work plan

The work plan is drafted from the agreed brief on Sat 17 Oct (next action 4). Record the
swimlanes, owners and reviewers here once they are agreed.

## Next actions

| # | Action | Owner | Due |
|---|---|---|---|
| 1 | Everyone accepts their repo invite (invites and the brief were sent on 15 Oct) | All | Fri 16 Oct |
| 2 | Everyone reads the brief and replies on the scope and §15 (open questions) | All | Fri 16 Oct night |
| 3 | Agree the brief: move accepted §16 rows to "Agreed"; remove answered questions from §15 | All | Sat 17 Oct |
| 4 | Plan the work from the agreed brief: swimlanes, owners and reviewers | Kenneth drafts; all agree | Sat 17 Oct |
| 5 | Set up the project skeleton: `uv init`, `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, package layout following the brief's "keep it portable" rules | From the work plan | Mon 19 Oct |
| 6 | Freeze the availability summary schema and the scenario file format | From the work plan | Mon 19 Oct |
| 7 | Hand-check 5 scenarios and run the free/busy baseline | From the work plan | Mon 19 Oct |
| 8 | Confirm `gpt-5-mini` is still available; measure real cost on the first 10 dev episodes | From the work plan | Mon 19 Oct |
| 9 | When the Week 8 (safety, oversight, governance) lecture is released on 20 Oct, update the brief's §11 Week 8 row | TBD | Wed 21 Oct |

## Risks and blockers

- **Budget is per key and cannot be pooled.** A debugging loop can burn one person's USD 10.
  Cap model calls per episode and log tokens from the first run.
- **The model may be deprecated.** OpenAI's page shows a "Deprecated" label on `gpt-5-mini`
  (checked 15 Oct). Confirm availability before freezing the model.
- **Tight timeline.** It is 15 days to the internal target. Scope cuts, in this order if needed:
  the Streamlit UI (keep the CLI), then meeting rooms (pending Q7), then the social-group family.
- **Public repo.** No keys, no course PDFs or slides, and no real personal data.

## Comms log

Messages sent to the team or the instructors. Log a message once it has actually been sent.

| Date | To | Channel | Summary |
|---|---|---|---|
| 2026-10-15 | Team (all team members) | Team chat | Shared brief v0.4 with a summary. Asked everyone to read it (start with §0), reply on scope and §15 (esp. report vs. deck) and accept the repo invite by Fri 16 Oct night. Brief locked and work split on Sat 17 Oct; build starts that weekend. House rules: public repo, keys in local `.env`; AI tools read AGENTS.md and update HANDOFF.md |

## Session log

Newest last. One row per working session, human or agent.

| Date | Who | What changed | Commits | Next |
|---|---|---|---|---|
| 2026-10-15 | Kenneth + Claude Code | Created the repo clone; drafted brief v0.1 → v0.3. Answered: due 3 Nov with a 30 Oct target; OpenAI with per-person USD 10 keys; workplace-first domain; participant/team-member naming; uv now with Docker optional. Added `.gitignore`, this handoff and the agent instructions | `751c3fb` brief v0.3; `b781274` .gitignore; `a62dbd8` handoff and agent instructions | Team review of the brief (next actions 1–3) |
| 2026-10-15 | Kenneth + Claude Code | Brief v0.4: workstreams removed until the brief and scope are agreed; review brought forward to Fri 16 Oct night; work plan on Sat 17 Oct so the build starts that weekend. Q8 (roster and owners) moved to the work plan | brief v0.4 (this commit) | Team replies by Fri 16 Oct night (next actions 1–2) |
