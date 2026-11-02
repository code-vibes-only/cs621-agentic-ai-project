# Presentation Q&A

Questions the audience may ask, with the answer we give and where the evidence is. Add new ones
from issue #14 or the deck reviews. Every number quoted must come from a committed result file.

| # | Question | Our answer | Evidence |
|---|---|---|---|
| 1 | Does the agent allow for lunch, breaks or travel time between meetings? | Not by itself. It schedules from what each participant's calendars, messages and words say. A rule like "lunch is 12:00–13:00" or "a 15-minute break after two hours of meetings" works if someone states it, because the personal agent turns statements into constraints. Travel time needs meeting locations (online or in person), which the scenarios do not have. Built-in breaks and travel time are future work | Brief §0 and §4 (statements become typed constraints); `scheduler/agents/personal.py`; issue #14 |
| 2 | Did the guardrails hold, or did the model simply not obey? | Mostly the model did not obey. A guardrail fired in 5 of the 138 saved attack runs. So we test the code separately: a scripted model does exactly what each attack asks, and each test checks what stops it. Turning a guardrail off makes those tests fail | `results/`, attack runs' `guardrails` lists; `docs/results.md` "After the final run"; `tests/test_attack_obedient.py` |
| 3 | Did you test more attacks after the final run? | Yes, three thread attacks on new held-out seeds, arms (c) and (d), 5 runs each, reported apart from the final numbers. None worked in 30 episodes, but one case cannot show success by construction, so that is at most 20 episodes of evidence | `results/heldout-attack2/report.md`; brief §16 |
| 4 | What is left open in the attack suite? | A private question is neither filtered nor graded, and a reworded leak can pass the filter and the checker alike. Both are recorded as known gaps | `docs/attack-coverage.md`; `results/component/report.md` |
