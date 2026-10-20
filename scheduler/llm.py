"""Every model call goes through call(): one place that checks the per-episode caps (calls,
tokens, USD, seconds) before the call, adds up tokens and cost, and swaps in a scripted fake
when SCHEDULER_FAKE_LLM=1 so tests cost nothing. The same model and settings serve every arm."""
import time
from functools import cache

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage

from scheduler.config import load_settings

# USD per 1M tokens (OpenAI model page, checked 15 Oct 2026). Reasoning tokens bill as output.
PRICES = {"gpt-5-mini": (0.25, 2.00), "gpt-5.4-mini": (0.75, 4.50)}

USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "started": time.perf_counter()}


class BudgetExceeded(RuntimeError):
    """The episode reached one of its caps: the run stops here, on purpose."""


def reset_usage() -> None:
    USAGE.update(calls=0, input_tokens=0, output_tokens=0, started=time.perf_counter())


def over_cap(settings) -> str | None:
    """The first cap this episode has reached, or None."""
    used = {"model-call": (USAGE["calls"], settings.max_llm_calls),
            "token": (USAGE["input_tokens"] + USAGE["output_tokens"], settings.max_tokens),
            "USD": (cost_usd(), settings.max_usd),
            "seconds": (time.perf_counter() - USAGE["started"], settings.max_seconds)}
    return next((f"{name} cap of {cap} reached" for name, (value, cap) in used.items() if value >= cap), None)


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
    if reached := over_cap(settings):
        raise BudgetExceeded(reached)
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
