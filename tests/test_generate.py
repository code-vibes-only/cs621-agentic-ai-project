from scheduler.world.generate import PLAN, generate


def test_generator_is_deterministic():
    first, second = generate("dev"), generate("dev")
    assert [s.model_dump() for s in first] == [s.model_dump() for s in second]


def test_dev_set_has_every_family():
    dev = generate("dev")
    assert len(dev) == sum(n for _, n, _ in PLAN.values()) == 18
    tags = {t for s in dev for t in s.tags}
    assert {"simple_feasible", "lookup_required", "nobody_free_relax", "pre_consent", "attendee_roles", "memory",
            "clarify", "infeasible", "privacy_probe", "approval_rsvp", "social", "weekend_family", "mixed_sources",
            "inferred_from_messages"} <= tags


def test_dev_set_reaches_beyond_work():
    dev = generate("dev")
    assert sum(s.request.days == ["sat", "sun"] for s in dev) >= 5
    assert sum(s.request.day_start >= "18:00" for s in dev) >= 2
