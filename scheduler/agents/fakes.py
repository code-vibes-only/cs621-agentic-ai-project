"""Scripted stand-ins for the model, used only when SCHEDULER_FAKE_LLM=1.

They let the tests run the whole pipeline (tools, summaries, privacy filter, graph, approval
gate, checker) at no cost. They read the scenario's ground truth, so a fake run measures the
plumbing, never the model: no fake result is ever reported as a result."""
from langchain_core.messages import AIMessage

from scheduler.sandbox import world


def reply(*calls: tuple[str, dict]) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": n, "args": a, "id": f"fake-{len(world.CALLS)}-{i}"}
                                             for i, (n, a) in enumerate(calls)])


def personal(scenario, pid: str):
    """Read, look up what the ground truth needed, clarify if needed, then submit the true rules."""
    gt = scenario.ground_truth
    rules = [t.rule.model_dump() for t in gt.rules if t.participant_id == pid]
    my_docs = {r["ref"] for r in rules if r.get("ref", "") and r["ref"].startswith("doc-")}

    def fake(messages):
        if not any(isinstance(m, AIMessage) for m in messages):
            calls = [("read_my_calendar", {}), ("get_leave", {}), ("read_my_messages", {}),
                     ("search_schedules", {"query": "public holidays"})]
            calls += [("search_schedules", {"query": world.CORPUS[d].title}) for d in sorted(my_docs) if d in world.CORPUS]
            if pid in gt.must_clarify:
                calls.append(("ask_my_participant", {"question": "Which hours do you mean?"}))
            return reply(*calls)
        return reply(("submit_constraints", {"rules": rules, "unknown": []}))
    return fake
