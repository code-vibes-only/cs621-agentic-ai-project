# Component diagnostics (issue #21)

Layers 3 and 5 of the test pyramid. No model calls, no cost. A second look at saved runs: the held-out numbers in `docs/results.md` are unchanged and these numbers are not merged into them.

Regenerate with `uv run python -m scheduler.eval.component`.

## Layer 3: the personal agent's first summary against the answer key

### `dev7`, arm (d), 3 runs, 3636 slots

Left out because the world changes during the run: dev-005. Episodes with no summary: 0.

| Per run, mean ± sample SD | Personal agents | Free/busy baseline |
|---|---|---|
| Slots whose status matches the key | 0.997 ± 0.006 | 0.953 ± 0.000 |
| Key's blocked slots reported as blocked | 0.990 ± 0.018 | 0.876 ± 0.000 |
| Key's open slots reported as blocked | 0.000 ± 0.000 | 0.000 ± 0.000 |
| The same, leaving out the public holiday | 0.000 ± 0.000 | n/a |
| Key's rule ids cited by the agent | 0.997 ± 0.006 | n/a |
| Other ids cited, per person (not the holiday list) | 0.083 ± 0.000 | n/a |

| Cause | Slots | Scenarios |
|---|---|---|
| block read as a preference (what they said) | 12 | dev-020 |

### `heldout-final`, arm (d), 3 runs, 14580 slots

Left out because the world changes during the run: ho-015, ho-016, ho-017, ho-018, ho-019, ho-020, ho-021, ho-032. Episodes with no summary: 0.

| Per run, mean ± sample SD | Personal agents | Free/busy baseline |
|---|---|---|
| Slots whose status matches the key | 0.973 ± 0.008 | 0.966 ± 0.000 |
| Key's blocked slots reported as blocked | 0.989 ± 0.008 | 0.941 ± 0.000 |
| Key's open slots reported as blocked | 0.037 ± 0.008 | 0.000 ± 0.000 |
| The same, leaving out the public holiday | 0.011 ± 0.004 | n/a |
| Key's rule ids cited by the agent | 0.992 ± 0.001 | n/a |
| Other ids cited, per person (not the holiday list) | 0.085 ± 0.006 | n/a |

| Cause | Slots | Scenarios |
|---|---|---|
| public holiday the key leaves out | 203 | ho-026, ho-027 |
| block read as a preference (what they said) | 58 | ho-011, ho-012, ho-024 |
| extra block, no key rule | 55 | ho-003, ho-004, ho-026, ho-027 |
| preference read as a block (memory note) | 30 | ho-003, ho-004 |
| extra preference, no key rule | 28 | ho-004, ho-011, ho-012, ho-030 |
| hard and movable swapped (calendar event) | 21 | ho-026, ho-027 |
| missed block (external schedule) | 18 | ho-005 |

Limits:

- A saved result holds rule ids, not times, so a cited id does not show its times were right. Grading each rule's times and weight needs new `parse()` calls.
- A cause names the first matching key rule when several cover a slot.
- The free/busy baseline has no preferences and no consent, so it cannot show `prefer_not`.

### Public holidays in the answer key

The personal agent's prompt says public holidays apply to everyone. The key counts them in some scenarios only:

| Scenario | Holiday in the window | Slots on it | Attendees whose key counts it |
|---|---|---|---|
| dev-007 | 2026-11-08 | 23 | 0 of 4 |
| dev-009 | 2026-11-09 | 17 | 3 of 3 |
| dev-021 | 2026-11-08 | 23 | 0 of 3 |
| ho-005 | 2026-11-09 | 17 | 3 of 3 |
| ho-026 | 2026-11-08 | 23 | 0 of 3 |
| ho-027 | 2026-11-08 | 23 | 0 of 3 |

This is a question about the key, not a change to it: the held-out set stays frozen.

## Layer 5: the privacy filter and the checker against labelled messages

38 hand-written messages about `dev-001`'s participants. The list was written to probe the filter, so these counts describe this list and are not a rate on real traffic. The code is deterministic, so repeat runs give the same counts.

| Kind | Label | Messages | Filter flags | Checker flags | Passes both |
|---|---|---|---|---|---|
| names a private detail | leak | 4 | 4 | 4 | 0 |
| private detail, no name | leak | 3 | 3 | 2 | 0 |
| reworded | leak | 6 | 1 | 1 | 5 |
| hinted | leak | 4 | 0 | 0 | 4 |
| other language | leak | 4 | 0 | 0 | 4 |
| says who cannot come | leak | 4 | 0 | 0 | 4 |
| proposal or status | clean | 6 | 0 | 0 | 6 |
| names someone, no reason | clean | 3 | 0 | 0 | 3 |
| reason word, innocent use | clean | 4 | 4 | 3 | 0 |

| | Leaks caught (recall) | Clean messages flagged |
|---|---|---|
| Privacy filter | 8 of 25 (0.32) | 4 of 13 |
| Checker | 7 of 25 (0.28) | 3 of 13 |

17 leaks pass both. A leak that passes the filter and the checker is recorded as "no leak", so the sweep's zero leaks means none that these two checks recognise. It does not show how often such wording occurs: nobody has labelled the saved thread messages.

"Says who cannot come" is labelled a leak because the brief says the thread never says whose time was given up, and the coordinator's prompt forbids it. The filter was not built to catch it, so the team may prefer to read it as a prompt rule. Each message and verdict is in `layer5.csv`.
