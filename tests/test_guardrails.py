"""Guardrails: checks outside the model, each verdict recorded; attack cases graded inverted."""
import pytest

from scheduler.config import load_settings
from scheduler.eval.arms import ARMS
from scheduler.eval.checker import grade
from scheduler.eval.episode import run_episode
from scheduler.sandbox import world


def test_every_verdict_is_recorded_passes_included(scenario):
    s = scenario("dev-001")
    result = run_episode("d", ARMS["d"], s, 1, "test", load_settings())
    names = {g.name for g in result.guardrails}
    assert {"summary schema", "privacy filter", "recheck", "consent", "stored approval", "read-back", "budget"} <= names
    assert all(g.passed for g in result.guardrails)
    assert any(e.kind == "guardrail" for e in result.timeline)


def test_a_refused_invite_is_recorded_as_a_stop(scenario):
    s = scenario("dev-001")
    with pytest.raises(PermissionError):
        world.send_invite(s.request.id, "2026-10-19T11:00", "2026-10-19T12:00", "approval-9", "k")
    assert [(g.name, g.passed) for g in world.GUARDRAILS] == [("stored approval", False)]


@pytest.mark.parametrize("sid", ["dev-024", "dev-025", "dev-026"])
def test_attack_cases_are_graded_inverted(scenario, sid):
    s = scenario(sid)
    assert s.ground_truth.attack is not None
    g = grade(s, run_episode("d", ARMS["d"], s, 1, "test", load_settings()))
    assert g.attack == s.ground_truth.attack.kind and g.attack_worked is False and g.passed


def test_an_attack_that_works_is_counted(scenario):
    s = scenario("dev-025")                  # the thread asks to book a slot its owner never gave up
    result = run_episode("d", ARMS["d"], s, 1, "test", load_settings())
    refused = s.scripted.replies[0]
    event = next(e for c in s.participant(refused.participant_id).calendars for e in c.events if e.id == refused.about)
    end = next(e for st, e in s.request.slots() if st == event.start)
    invite = next(w for w in result.writes if w.tool == "send_invite")
    result.writes = [invite.model_copy(update={"start": event.start, "end": end})]      # as if it had obeyed
    g = grade(s, result)
    assert g.attack_worked is True and g.unconsented == 1 and not g.passed
