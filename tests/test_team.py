"""The whole pipeline in fake mode: tools, summaries, filter, graph, gate, checker."""
import pytest

from scheduler.config import load_settings
from scheduler.eval.arms import ARMS
from scheduler.eval.checker import grade
from scheduler.eval.episode import run_episode


@pytest.mark.parametrize("sid", ["dev-001", "dev-002", "dev-003", "dev-004", "dev-005"])
def test_team_passes_the_hand_checked_scenarios(scenario, sid):
    s = scenario(sid)
    result = run_episode("d", ARMS["d"], s, 1, "test", load_settings())
    assert grade(s, result).passed, result.outcome


def test_a_required_decline_moves_the_meeting_with_a_new_approval(scenario):
    s = scenario("dev-005")
    result = run_episode("d", ARMS["d"], s, 1, "test", load_settings())
    invites = [w for w in result.writes if w.tool == "send_invite"]
    assert len(invites) == 2 and invites[0].approval_id != invites[1].approval_id
    assert invites[0].start != invites[1].start


def test_only_the_shared_context_arm_sees_private_details(scenario):
    s = scenario("dev-001")
    shared = grade(s, run_episode("c", ARMS["c"], s, 1, "test", load_settings()))
    isolated = grade(s, run_episode("d", ARMS["d"], scenario("dev-001"), 1, "test", load_settings()))
    assert shared.leaks_context > 0 and isolated.leaks_context == 0
