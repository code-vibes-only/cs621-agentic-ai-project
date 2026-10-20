"""Scripted stand-ins for the model, used only when SCHEDULER_FAKE_LLM=1.

They let the tests run the whole pipeline (tools, summaries, privacy filter, graph, approval
gate, checker) at no cost. They read the scenario's ground truth, so a fake run measures the
plumbing, never the model: no fake result is ever reported as a result."""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

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


def coordinator(team):
    """Find slots; propose the top free one; ask the named blockers; replan on refusal or decline."""
    def fake(messages):
        last = messages[-1]
        if isinstance(last, HumanMessage) and "Finish by calling" in last.content:
            return reply(("hand_back", {"message": "No slot works for everyone in this window."}))
        if not isinstance(last, ToolMessage):
            return reply(("find_slots", {}))
        if last.name == "find_slots":
            for c in team.candidates:
                if c.feasible:
                    return reply(("post_to_thread", {"message": f"Proposed: {c.start} to {c.end[11:]}."}),
                                 ("place_hold", {"start": c.start, "end": c.end}))
                waiting = [p for p in c.blockers if team.asked.get(p, 0) == 0]
                if waiting:
                    return reply(*[("ask_privately", {"participant_id": p, "start": c.start, "end": c.end,
                                                      "question": f"Could you free {c.start} to {c.end[11:]}?"})
                                   for p in waiting])
            return reply(("hand_back", {"message": "No slot works for everyone in this window."}))
        if last.name == "place_hold":
            hold = next(iter(world.HOLDS.values()))
            return reply(("request_approval", {"start": hold["start"], "end": hold["end"]}))
        return reply(("find_slots", {}))
    return fake


def single(scenario):
    """The single call's decision: the best slot that needs nobody's consent, or hand back."""
    from scheduler.eval.truth import compute

    def fake(messages):
        truth = compute(scenario)
        if not truth.free:
            return reply(("decide", {"hand_back": True, "thread_message": "No slot works for everyone."}))
        best = max(truth.free, key=lambda s: (truth.utility[s], -truth.free.index(s)))
        return reply(("decide", {"start": best, "end": truth.ends[best], "thread_message": f"Proposed: {best}."}))
    return fake


def shared(scenario):
    """The shared-context agent: read everyone, look up what the ground truth needed, submit everyone's rules."""
    gt = scenario.ground_truth
    ids = [a.id for a in scenario.request.attendees]

    def fake(messages):
        if not any(isinstance(m, AIMessage) for m in messages):
            calls = [c for pid in ids for c in [("read_calendar", {"participant_id": pid}), ("get_leave", {"participant_id": pid}),
                                                ("read_messages", {"participant_id": pid})]]
            docs = sorted({t.rule.ref for t in gt.rules if (t.rule.ref or "").startswith("doc-")} & set(world.CORPUS))
            calls += [("search_schedules", {"query": "public holidays"})] + [("search_schedules", {"query": world.CORPUS[d].title}) for d in docs]
            calls += [("ask_participant", {"participant_id": pid, "question": "Which hours do you mean?"}) for pid in gt.must_clarify]
            return reply(*calls)
        return reply(*[("submit_constraints", {"participant_id": pid, "unknown": [],
                                               "rules": [t.rule.model_dump() for t in gt.rules if t.participant_id == pid]})
                       for pid in ids])
    return fake
