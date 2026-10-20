"""The arms being compared. Each takes a scenario on a freshly reset sandbox and returns its
outcome; the episode wrapper collects everything else from the sandbox's records.

(a) free/busy finder               scheduler.eval.baselines.free_busy
(b) single grounded call           scheduler.eval.baselines.single_call
(c) one agent, shared context      scheduler.agents.shared.shared_team
(d) personal agents + coordinator  one private personal agent per participant, then the coordinator"""
from scheduler.agents import fakes
from scheduler.agents.coordinator import Coordinator
from scheduler.agents.personal import PersonalAgent
from scheduler.agents.shared import shared_team
from scheduler.eval.baselines import free_busy, single_call


def team_coordinator(scenario) -> Coordinator:
    """One private personal agent per attendee parses its participant; then the coordinator."""
    agents = {}
    for a in scenario.request.attendees:
        agents[a.id] = PersonalAgent(scenario, a.id, fake=fakes.personal(scenario, a.id))
        agents[a.id].parse()
    coordinator = Coordinator(scenario, agents)
    coordinator.fake = fakes.coordinator(coordinator)
    return coordinator


def team(scenario):
    return team_coordinator(scenario).run()


ARMS = {"a": free_busy, "b": single_call, "c": shared_team, "d": team}
