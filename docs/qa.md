# Presentation Q&A

Questions the audience may ask, with the answer we give and where the evidence is. Add new ones
from issue #14 or the deck reviews. Every number quoted must come from a committed result file.

| # | Question | Our answer | Evidence |
|---|---|---|---|
| 1 | Does the agent allow for lunch, breaks or travel time between meetings? | Not by itself. It schedules from what each participant's calendars, messages and words say. A rule like "lunch is 12:00–13:00" or "a 15-minute break after two hours of meetings" works if someone states it, because the personal agent turns statements into constraints. Travel time needs meeting locations (online or in person), which the scenarios do not have. Built-in breaks and travel time are future work | Brief §0 and §4 (statements become typed constraints); `scheduler/agents/personal.py`; issue #14 |
