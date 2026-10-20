"""The enumerator and scorer: deterministic code that lists slots from the availability
summaries and ranks them. The model never does this arithmetic.

A required participant's "unavailable" blocks a slot; the enumerator never relaxes it. If it
is relaxable, the slot is listed as "needs consent" with that participant as a blocker, so
the coordinator agent knows exactly whom to ask. An optional participant never blocks: an
optional "unavailable" only costs OPTIONAL_MISS."""
from dataclasses import dataclass, field

from scheduler.contracts.availability import AvailabilitySummary
from scheduler.timegrid import overlaps

OPTIONAL_MISS = 0.5


@dataclass
class Candidate:
    start: str
    end: str
    utility: float                                    # higher is better; one point per attendee
    blockers: list[str] = field(default_factory=list) # required participants whose consent is needed

    @property
    def feasible(self) -> bool:
        return not self.blockers


def enumerate_slots(summaries: dict[str, AvailabilitySummary], roles: dict[str, str],
                    slots: list[tuple[str, str]]) -> list[Candidate]:
    """Every slot that no required participant rules out, best first: feasible slots before
    slots that need consent, then by utility, then earliest."""
    out = []
    for start, end in slots:
        utility, blockers, ruled_out = 0.0, [], False
        for pid, role in roles.items():
            summary = summaries[pid]
            slot = summary.status_of(start)
            unknown = any(overlaps(w.start, w.end, start, end) for w in summary.unknown)
            if slot is None or unknown or slot.status == "unavailable":
                if role == "optional":
                    utility += 1 - OPTIONAL_MISS
                elif slot is not None and not unknown and slot.relaxable:
                    blockers.append(pid)
                    utility += 1
                else:
                    ruled_out = True                  # a hard "unavailable", or unknown: never free
                    break
            else:
                utility += 1 - slot.weight
        if not ruled_out:
            out.append(Candidate(start, end, round(utility, 3), blockers))
    return sorted(out, key=lambda c: (len(c.blockers) > 0, -c.utility, len(c.blockers), c.start))
