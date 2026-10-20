"""A plain tool loop: the model calls tools, the results go back into its window, and it stops
by calling a finish tool whose arguments are validated in code. A bad submission is returned
as the tool's error, so the model can correct it (every tool call gets exactly one answer)."""
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from scheduler import llm


def tool_loop(system: str, user: str, tools: list, finish, done, fake=None, max_turns: int = 8) -> list:
    """Run until done() is true after a finish call. `finish(args)` validates and stores one
    submission and returns the text the model sees. Returns the whole window."""
    by_name = {t.name: t for t in tools}
    messages = [SystemMessage(system), HumanMessage(user)]
    for _ in range(max_turns):
        reply = llm.call(messages, tools, fake)
        messages.append(reply)
        if not reply.tool_calls:
            messages.append(HumanMessage("Finish by calling the submit tool."))
            continue
        for tool_call in reply.tool_calls:
            if tool_call["name"] not in by_name:
                text = f"unknown tool {tool_call['name']}; tools: {', '.join(by_name)}"
            elif by_name[tool_call["name"]].metadata and by_name[tool_call["name"]].metadata.get("finish"):
                try:
                    text = finish(tool_call["args"])
                except (ValidationError, ValueError) as e:
                    text = f"rejected, fix and resubmit: {e}"
            else:
                try:
                    text = str(by_name[tool_call["name"]].invoke(tool_call["args"]))
                except (ValidationError, ValueError) as e:
                    text = f"error: {e}"
            messages.append(ToolMessage(text, tool_call_id=tool_call["id"], name=tool_call["name"]))
        if done():
            return messages
    raise RuntimeError(f"no complete submission after {max_turns} turns")
