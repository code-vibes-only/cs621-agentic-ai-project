"""Every model call goes through call(): one place that counts calls against the per-episode
cap, adds up tokens and cost, and swaps in a scripted fake when SCHEDULER_FAKE_LLM=1 so tests
cost nothing. The same model and settings serve every arm."""
from functools import cache

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage

from scheduler.config import load_settings

# USD per 1M tokens (OpenAI model page, checked 15 Oct 2026). Reasoning tokens bill as output.
PRICES = {"gpt-5-mini": (0.25, 2.00), "gpt-5.4-mini": (0.75, 4.50)}

USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0}


class BudgetExceeded(RuntimeError):
    """The episode hit SCHEDULER_MAX_LLM_CALLS: the run stops here, on purpose."""


def reset_usage() -> None:
    USAGE.update(calls=0, input_tokens=0, output_tokens=0)


def cost_usd() -> float:
    price_in, price_out = PRICES.get(load_settings().model, (0.0, 0.0))
    return round((USAGE["input_tokens"] * price_in + USAGE["output_tokens"] * price_out) / 1e6, 6)


@cache
def chat_model(model: str, effort: str):
    return init_chat_model(f"openai:{model}", reasoning_effort=effort, timeout=120, max_retries=3)


def call(messages: list, tools: list | None = None, fake=None, tool_choice: str | None = None) -> AIMessage:
    """One model call. `fake(messages)` returns the AIMessage to use in fake mode;
    tool_choice="name" forces that tool, for a structured answer."""
    settings = load_settings()
    if USAGE["calls"] >= settings.max_llm_calls:
        raise BudgetExceeded(f"model-call cap of {settings.max_llm_calls} reached")
    USAGE["calls"] += 1
    if settings.fake_llm:
        if fake is None:
            raise RuntimeError("no fake reply for this call in fake mode")
        return fake(messages)
    model = chat_model(settings.model, settings.reasoning_effort)
    if tools:
        model = model.bind_tools(tools, tool_choice=tool_choice) if tool_choice else model.bind_tools(tools)
    reply = model.invoke(messages)
    usage = reply.usage_metadata or {}
    USAGE["input_tokens"] += usage.get("input_tokens", 0)
    USAGE["output_tokens"] += usage.get("output_tokens", 0)
    return reply
