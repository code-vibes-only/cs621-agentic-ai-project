# Instructions for AI agents

These instructions apply to every AI coding agent working in this repo (Claude Code, Codex,
Cursor and others).

## The project

CS621 group project: an **Agentic Natural Language Scheduler** for any group, at work or outside
it. Each participant has a private personal agent that reads their calendars and messages; a
coordinator agent schedules from availability summaries that never contain reasons. Invites need
approval. The full design is in [brief.md](brief.md); the security review is in
`docs/security-review.md`.

## At the start and end of every session

- **Start:** read [HANDOFF.md](HANDOFF.md), then the sections of brief.md your task touches.
  Always read brief §0 (definitions).
- **End:** update HANDOFF.md as its "Ending a session" section describes, including one session
  log row. Record decisions in brief §16, never only in chat.

## Hard rules

1. **This repo is public.** Never commit API keys, `.env` files, course PDFs or slides, or real
   personal data. Keys live in each team member's local `.env`; commit only `.env.example`.
2. **LLM calls cost real money from a team member's own USD 10 monthly cap.** Do not start
   evaluation sweeps or long loops unless the person asked for them. Cap model calls per episode,
   log tokens, and tell the person the expected cost before a large run.
3. **Never invent results.** Every number in a report, deck or README must come from a committed
   result file. Every claimed metric is a mean ± sample SD over at least 3 runs, compared with a
   baseline.
4. **Proposed is not agreed.** Do not treat a brief §16 row marked *Proposed* as settled. Do not
   change a decision without the team's agreement.
5. **Use the naming rules from brief §0.** *Participant* means an end user. *Team member* means
   one of the five students. The agents are the *personal agent* and the *coordinator agent*,
   and the hand-off between them is the *availability summary*.
6. **Privacy and safety live in code, not in prompts.** Hard constraints, the privacy filter and
   approval gates are enforced by deterministic code. The agent never writes to a participant's
   existing commitments.

## Environment

- Python via **uv**. Run with `uv run ...` and add packages with `uv add <pkg>`; do not use
  `pip install`. Commit `uv.lock` and `.python-version`.
- Follow the "keep it portable" rules in brief §12:
  - configuration comes from environment variables;
  - paths are relative to the repo root;
  - each job is one command;
  - results are written to one file per episode, then merged.

## Git

- Keep commits small, with descriptive messages.
- Commit or push only when the person you are working with asks you to.
- Pull before starting work. Do not rewrite history on `main`.
