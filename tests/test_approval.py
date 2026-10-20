from scheduler.engine.approval import commit, recheck
from scheduler.sandbox import world


class Agent:
    """Stands in for a personal agent: records what the gate tells it."""
    def __init__(self):
        self.declined = []

    def decline(self, start, end):
        self.declined.append((start, end))


def test_the_gate_refuses_movable_time_without_consent(scenario):
    s = scenario("dev-002")
    assert recheck(s, "2026-10-19T15:00", "2026-10-19T16:00") == ([], ["p03"])
    world.record_consent("p03", "e-p03-1", "2026-10-19T15:00")
    assert recheck(s, "2026-10-19T15:00", "2026-10-19T16:00") == ([], [])


def test_a_hard_meeting_makes_the_slot_stale(scenario):
    s = scenario("dev-001")
    assert recheck(s, "2026-10-19T10:00", "2026-10-19T11:00") == (["p05"], [])


def test_commit_sends_verifies_and_reports_a_required_decline(scenario):
    s = scenario("dev-005")
    agents = {a.id: Agent() for a in s.request.attendees}
    a, b = "2026-10-19T09:00", "2026-10-19T10:00"
    result = commit(s, a, b, world.store_approval(a, b, "approve"), agents)
    assert result == {"status": "sent", "declined_required": ["p02"], "declined_optional": []}
    assert agents["p02"].declined == [(a, b)]
