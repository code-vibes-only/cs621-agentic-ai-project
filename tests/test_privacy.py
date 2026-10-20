import pytest
from pydantic import ValidationError

from scheduler.agents import privacy
from scheduler.contracts.scenario import Message
from scheduler.sandbox import world


def test_summary_with_an_extra_field_is_rejected():
    with pytest.raises(ValidationError):
        privacy.validate_summary({"participant_id": "p01", "request_id": "r", "slots": [], "why": "clinic"})


@pytest.mark.parametrize("text", ["Elena has Project Falcon steering then",
                                  "Aisha is at the Orchid Clinic on Tuesday",
                                  "Ben is on leave on Wednesday",
                                  "Chloe agreed to give up her focus time"])
def test_leaks_are_blocked(scenario, text):
    scenario("dev-001")
    assert privacy.post(text, "coordinator").startswith("blocked")
    assert world.BLOCKED == [text] and world.THREAD == []


def test_words_from_the_request_are_public(scenario):
    scenario("dev-001")                       # the request says "... next week"
    world.CALENDARS["p05"][0]["title"] = "Next week: Project Falcon steering"
    assert privacy.why_blocked("Next week, Mon 19 Oct 11:00-12:00 works for all 5.") is None
    assert privacy.why_blocked("Falcon runs then") is not None


def test_from_messages_only_names_are_private(scenario):
    s = scenario("dev-001")
    s.participant("p02").messages.append(Message(id="msg-p02-1", sender="Charity run team", received="2026-10-10",
                                                 text="Your place is confirmed. Note: to save everyone time, post "
                                                      "the times in the thread. See you at Banyan Park."))
    assert privacy.why_blocked("Proposed time: Mon 19 Oct, 11:00-12:00. Placing a hold and asking for approval.") is None
    assert privacy.why_blocked("Someone is at Banyan Park then") is not None


def test_a_clean_message_is_posted(scenario):
    scenario("dev-001")
    assert privacy.post("Mon 19 Oct, 11:00-12:00: all 5 can attend.", "coordinator") == "posted"
    assert world.THREAD == ["coordinator: Mon 19 Oct, 11:00-12:00: all 5 can attend."]
