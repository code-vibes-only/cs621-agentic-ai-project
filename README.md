# Agentic Natural Language Scheduler

A scheduler for any group, at work or outside it, where each participant has a private
personal agent. The personal agent reads its participant's calendars (work, family, club and
so on) and messages, remembers what they said, looks up events that are in no calendar, and
tells a coordinator agent only *when* they can meet, never *why*. The coordinator agent ranks
slots, asks only the people blocking a slot (privately), replans, and sends an invite only after
the organiser approves. Everything runs in a sandbox: no real calendar or message is read or
written. The design is in [brief.md](brief.md).

## Set up

You need [uv](https://docs.astral.sh/uv/). From the repo root:

```sh
uv sync                                     # installs the pinned Python and packages from uv.lock
SCHEDULER_FAKE_LLM=1 uv run pytest          # the tests use a scripted fake model: no key, no cost
```

For real runs, put your own OpenAI key in your shell, or in a local `.env` (gitignored; never commit it):

```sh
export OPENAI_API_KEY=sk-...                # see .env.example for every setting
uv run python -m scheduler.eval --check-model
```
