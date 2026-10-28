from datetime import date

from scheduler.world.generate import PLAN, generate


def test_generator_is_deterministic():
    first, second = generate("dev"), generate("dev")
    assert [s.model_dump() for s in first] == [s.model_dump() for s in second]


def test_heldout_covers_every_family_and_differs_from_dev():
    heldout, dev = generate("heldout"), generate("dev")
    assert len(heldout) == sum(n for _, _, n in PLAN.values()) == 33
    assert not {s.seed for s in heldout} & {s.seed for s in dev}
    tags = {t for s in heldout for t in s.tags}
    assert {"lookup_required", "nobody_free_relax", "pre_consent", "attendee_roles", "memory", "clarify",
            "infeasible", "privacy_probe", "approval_rsvp", "social", "weekend_family", "mixed_sources",
            "inferred_from_messages", "attack"} <= tags


def test_about_half_of_the_held_out_set_is_outside_work():
    heldout = generate("heldout")
    outside = [s for s in heldout if s.request.days == ["sat", "sun"] or s.request.day_start >= "18:00"]
    assert 0.4 <= len(outside) / len(heldout) <= 0.6


def test_the_words_match_the_data():
    for s in generate("dev") + generate("heldout"):
        days = (date.fromisoformat(s.request.end_date) - date.fromisoformat(s.request.start_date)).days + 1
        if "next week" in s.request.text and days < 5:
            assert "(Monday to" in s.request.text, s.id                     # a shorter week names its days
        for r in s.scripted.replies:
            if r.consent and r.slot is None:
                assert not any(ch.isdigit() for ch in r.answer), s.id        # consent for any slot names no time
