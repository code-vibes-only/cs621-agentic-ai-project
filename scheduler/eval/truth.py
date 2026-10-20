"""The answer key, recomputed from a scenario's ground truth for every grade. This is the
checker's own arithmetic: it never calls the enumerator or the agents' code, so a bug there
cannot hide here."""
from dataclasses import dataclass

from scheduler.contracts.constraints import Constraint, expand, outside_hours
from scheduler.contracts.scenario import Scenario
from scheduler.timegrid import overlaps

OPTIONAL_MISS = 0.5


def truth_constraints(scenario: Scenario) -> dict[str, list[Constraint]]:
    """Every participant's ground-truth windows, usual hours included."""
    r = scenario.request
    out = {}
    for p in scenario.participants:
        rules = [t.rule for t in scenario.ground_truth.rules if t.participant_id == p.id]
        out[p.id] = (expand(p.id, rules, r.start_date, r.end_date)
                     + outside_hours(p.id, r.start_date, r.end_date, p.hours_start, p.hours_end))
    return out


def consentable(scenario: Scenario) -> dict[str, list[tuple[str, str | None]]]:
    """(ref, slot) pairs each participant would agree to free: pre-given consent covers any
    slot; a scripted "yes" covers the slot it names, or any slot if it names none."""
    out = {p.id: [(ref, None) for c in p.pre_consent for ref in c.refs] for p in scenario.participants}
    for reply in scenario.scripted.replies:
        if reply.consent:
            out[reply.participant_id].append((reply.about, reply.slot))
    return out


@dataclass
class Truth:
    utility: dict[str, float]          # slot start -> utility, for every slot no required hard window rules out
    free: list[str]                    # slots that need nobody's consent
    with_consent: list[str]            # slots that need consent that would be given
    needs: dict[str, list[str]]        # slot start -> participants whose consent it needs
    ends: dict[str, str]

    @property
    def expected(self) -> list[str]:
        """The slots a correct run may end on: the free ones if any, else the consented ones."""
        return self.free or self.with_consent

    @property
    def best(self) -> float | None:
        return max((self.utility[s] for s in self.expected), default=None)


def compute(scenario: Scenario, extra_hard: dict[str, list[tuple[str, str]]] | None = None) -> Truth:
    """extra_hard adds windows that became impossible during the run (e.g. a declined invite)."""
    r = scenario.request
    windows = truth_constraints(scenario)
    agree = consentable(scenario)
    utility, free, with_consent, needs, ends = {}, [], [], {}, {}
    for start, end in r.slots():
        total, blocked, need = 0.0, False, []
        for a in r.attendees:
            hits = [c for c in windows[a.id] if overlaps(c.start, c.end, start, end)]
            hard = any(c.kind == "hard" for c in hits) or any(
                overlaps(s, e, start, end) for s, e in (extra_hard or {}).get(a.id, []))
            movable = [c for c in hits if c.kind == "movable"]
            if a.role == "optional":
                total += 1 - OPTIONAL_MISS if (hard or movable) else 1 - max([c.weight for c in hits] + [0])
                continue
            if hard:
                blocked = True
                break
            if movable:
                if all(any(ref == c.ref and slot in (None, start) for ref, slot in agree[a.id]) for c in movable):
                    need.append(a.id)
                else:
                    blocked = True
                    break
            total += 1 - max([c.weight for c in hits if c.kind == "soft"] + [0])
        if blocked:
            continue
        utility[start], ends[start] = round(total, 3), end
        (with_consent if need else free).append(start)
        needs[start] = need
    return Truth(utility, free, with_consent, needs, ends)
