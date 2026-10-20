import pytest
from langchain_core.messages import AIMessage, HumanMessage

from scheduler import llm


def test_fake_mode_makes_no_call_and_counts_it():
    llm.reset_usage()
    reply = llm.call([HumanMessage("hi")], fake=lambda m: AIMessage(content="ok"))
    assert reply.content == "ok" and llm.USAGE["calls"] == 1 and llm.cost_usd() == 0


def test_the_call_cap_stops_the_episode(monkeypatch):
    monkeypatch.setenv("SCHEDULER_MAX_LLM_CALLS", "2")
    llm.reset_usage()
    for _ in range(2):
        llm.call([HumanMessage("hi")], fake=lambda m: AIMessage(content="ok"))
    with pytest.raises(llm.BudgetExceeded):
        llm.call([HumanMessage("hi")], fake=lambda m: AIMessage(content="ok"))


def test_the_token_and_money_caps_stop_it_too(monkeypatch):
    monkeypatch.setenv("SCHEDULER_MAX_TOKENS", "1000")
    llm.reset_usage()
    llm.USAGE.update(input_tokens=900, output_tokens=100)
    with pytest.raises(llm.BudgetExceeded, match="token cap"):
        llm.call([HumanMessage("hi")], fake=lambda m: AIMessage(content="ok"))
    monkeypatch.setenv("SCHEDULER_MAX_TOKENS", "10000000")
    monkeypatch.setenv("SCHEDULER_MAX_USD", "0.001")
    llm.USAGE.update(input_tokens=0, output_tokens=1000)                  # USD 0.002 at gpt-5-mini prices
    with pytest.raises(llm.BudgetExceeded, match="USD cap"):
        llm.call([HumanMessage("hi")], fake=lambda m: AIMessage(content="ok"))


def test_cost_uses_the_price_table():
    llm.USAGE.update(calls=1, input_tokens=1_000_000, output_tokens=1_000_000)
    assert llm.cost_usd() == 2.25                  # gpt-5-mini: 0.25 in + 2.00 out per 1M
