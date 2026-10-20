from scheduler.agents import fakes
from scheduler.agents.personal import PersonalAgent
from scheduler.contracts.scenario import Consent
from scheduler.sandbox import world
from scheduler.timegrid import candidate_slots


def agent_for(scenario, sid, pid):
    s = scenario(sid)
    a = PersonalAgent(s, pid, fake=fakes.personal(s, pid))
    a.parse()
    return s, a


def test_summary_says_when_never_why(scenario):
    s, a = agent_for(scenario, "dev-001", "p01")
    summary = a.summary(candidate_slots("2026-10-20", "2026-10-20", 60))
    assert summary.status_of("2026-10-20T10:00").status == "unavailable"
    assert "Orchid" not in summary.model_dump_json()


def test_relax_question_asks_the_participant_and_records_consent(scenario):
    s, a = agent_for(scenario, "dev-002", "p03")
    assert a.answer_relax("2026-10-19T14:00", "2026-10-19T17:00") == "yes: from 15:00"
    assert world.CONSENTS["p03"] == [("e-p03-1", "2026-10-19T15:00")]
    assert a.summary([("2026-10-19T15:00", "2026-10-19T16:00")]).slots[0].status == "available"


def test_pre_given_consent_answers_without_asking(scenario):
    s = scenario("dev-002")
    s.participant("p03").pre_consent.append(Consent(id="c-p03-1", refs=["e-p03-1"], text="You may give up my focus blocks."))
    a = PersonalAgent(s, "p03", fake=fakes.personal(s, "p03"))
    a.parse()
    assert a.answer_relax("2026-10-19T14:00", "2026-10-19T17:00") == "yes: any time (agreed in advance)"
    assert not any(c.tool == "ask_participant" for c in world.CALLS)
