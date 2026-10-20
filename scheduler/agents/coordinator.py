"""The coordinator agent: a LangGraph graph that schedules for the whole group.

It sees availability summaries, never calendars. The model decides which slot to propose,
whom to ask privately and when to replan or hand back; code ranks the slots, filters every
thread message, and gates the only irreversible write behind interrupt(): nothing above the
interrupt has a side effect, because on resume the node runs again from its first line."""
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt

from scheduler import llm
from scheduler.agents import privacy
from scheduler.contracts.result import Outcome, Question
from scheduler.engine.approval import commit
from scheduler.engine.enumerator import enumerate_slots
from scheduler.sandbox import world

MAX_TURNS = 14          # coordinator model turns per episode
MAX_QUESTIONS = 2       # private questions per participant per request

SYSTEM = """You are the coordinator agent for one scheduling request, working for the organiser.
You see availability summaries only: when each participant can meet, never why. Never guess, mention or ask
about anyone's reasons, and never say in the thread whose time was given up or who cannot come.
How to work:
1. Call find_slots.
2. If the top slot needs nobody's consent: post it to the thread (the time, and how many can attend),
   place a hold on it, then call request_approval for it.
3. If every slot needs consent: ask privately only the participants named for the top slot, one question
   each (at most 2 per person), e.g. "Could you free 15:00-16:00 on Sat 24 Oct for this?". Then call
   find_slots again.
4. If no slot works: call hand_back with a short explanation that gives no one's reasons.
5. If request_approval reports that the slot is no longer free or that a required attendee declined, call
   find_slots again and handle the new top slot as above. That needs a new approval.
Answer questions in the thread briefly and without anyone's reasons. Never ask anything in the thread."""


class State(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    turns: int
    done: bool


class Coordinator:
    def __init__(self, scenario, agents: dict, background: str = "", fake=None):
        self.scenario, self.agents, self.fake = scenario, agents, fake
        r = scenario.request
        self.slots = r.slots()
        self.roles = {a.id: a.role for a in r.attendees}
        self.system = SYSTEM + (f"\n\nBackground:\n{background}" if background else "")
        self.candidates, self.asked = [], {}
        self.outcome = Outcome(status="budget", message="stopped without a decision")
        self.tools = self.make_tools()

    def make_tools(self) -> list:
        r, names = self.scenario.request, {p.id: p.name for p in self.scenario.participants}

        @tool
        def find_slots() -> str:
            """Rank every slot from the participants' current availability summaries."""
            summaries = {}
            for pid in self.roles:
                summary = privacy.validate_summary(self.agents[pid].summary(self.slots).model_dump())
                world.SUMMARIES.append(summary)
                summaries[pid] = summary
                counts = {s: sum(x.status == s for x in summary.slots) for s in ("available", "prefer_not", "unavailable")}
                world.note(f"personal:{pid}", "summary", f"{counts['available']} available, {counts['prefer_not']} prefer not, "
                           f"{counts['unavailable']} unavailable ({sum(x.relaxable for x in summary.slots)} relaxable)",
                           [pid, "coordinator"])
            self.candidates = enumerate_slots(summaries, self.roles, self.slots)
            if not self.candidates:
                text = "No slot works, even with consent."
            else:
                lines = [f"{len(self.candidates)} slots. Best first:"]
                for c in self.candidates[:6]:
                    need = (", needs consent from " + ", ".join(f"{p} ({names[p]})" for p in c.blockers)) if c.blockers else ", needs nobody's consent"
                    lines.append(f"- {c.start} to {c.end[11:]}: score {c.utility} of {len(self.roles)}{need}")
                text = "\n".join(lines)
            world.note("coordinator", "ranking", text)
            return text

        @tool
        def ask_privately(participant_id: str, start: str, end: str, question: str) -> str:
            """Ask one participant, privately, whether they could free the time from start to end
            ('YYYY-MM-DDTHH:MM'). Their personal agent answers yes or no, never why."""
            if participant_id not in self.roles:
                return f"unknown participant {participant_id}; attendees: {', '.join(self.roles)}"
            if not world.guard("question cap", "tool call", f"questions to {participant_id}: {self.asked.get(participant_id, 0)}",
                               self.asked.get(participant_id, 0) < MAX_QUESTIONS):
                return f"question limit reached for {participant_id}; do not ask again"
            self.asked[participant_id] = self.asked.get(participant_id, 0) + 1
            world.QUESTIONS.append(Question(to=participant_id, text=question, channel="private"))
            world.note("coordinator", "ask", f"to {participant_id}: {question}", [participant_id, "coordinator"])
            answer = self.agents[participant_id].answer_relax(start, end)
            world.note(f"personal:{participant_id}", "answer", answer, [participant_id, "coordinator"])
            return answer

        @tool
        def post_to_thread(message: str) -> str:
            """Post a message in the request thread, which every participant sees."""
            return privacy.post(message, "coordinator")

        @tool
        def place_hold(start: str, end: str) -> str:
            """Place a tentative, auto-expiring hold on everyone's calendar; it replaces any earlier hold."""
            for key in list(world.HOLDS):
                world.release_hold(r.id, key, "coordinator")
            return world.place_hold(r.id, start, end, key=f"{r.id}-hold-{start}", caller="coordinator")

        @tool
        def request_approval(start: str, end: str) -> str:
            """Ask the organiser to approve the invite for this slot. Only an approved slot is sent."""
            return "handled by the approval gate"

        @tool
        def hand_back(message: str) -> str:
            """Give up and hand the request back to the organiser, with a reason-free explanation."""
            posted = privacy.post(message, "coordinator")
            if posted != "posted":
                return posted
            self.outcome = Outcome(status="hand_back", message=message)
            return "handed back"

        return [find_slots, ask_privately, post_to_thread, place_hold, request_approval, hand_back]

    # ---------------------------------------------------------------- the graph
    def agent(self, state: State):
        if state.get("turns", 0) >= MAX_TURNS:
            return {"done": True}
        reply = llm.call([SystemMessage(self.system)] + state["messages"], self.tools, self.fake)
        return {"messages": [reply], "turns": state.get("turns", 0) + 1}

    def route(self, state: State) -> str:
        if state.get("done"):
            return END
        calls = state["messages"][-1].tool_calls
        if not calls:
            return "nudge"
        return "approve" if any(c["name"] == "request_approval" for c in calls) else "tools"

    def run_tools(self, state: State):
        by_name = {t.name: t for t in self.tools}
        out = []
        for c in state["messages"][-1].tool_calls:
            if c["name"] not in by_name:
                text = f"unknown tool {c['name']}"
            else:
                try:
                    text = str(by_name[c["name"]].invoke(c["args"]))
                except Exception as e:                      # a bad argument goes back as the tool's answer
                    text = f"error: {e}"
            out.append(ToolMessage(text, tool_call_id=c["id"], name=c["name"]))
        return {"messages": out, "done": self.outcome.status == "hand_back"}

    def approve(self, state: State):
        calls = state["messages"][-1].tool_calls
        gated = next(c for c in calls if c["name"] == "request_approval")
        start, end = gated["args"].get("start", ""), gated["args"].get("end", "")
        decision = interrupt({"start": start, "end": end})          # the organiser decides here
        world.note("organiser", "approval", f"{decision} {start} to {end[11:]}", ["organiser", "coordinator"])
        rest = self.run_tools({"messages": [state["messages"][-1].model_copy(
            update={"tool_calls": [c for c in calls if c is not gated]})]})["messages"]
        if not world.guard("valid slot", "tool call", f"{start} to {end}", (start, end) in self.slots):
            text, done = f"{start} to {end} is not a valid slot", False
        elif decision != "approve":
            text, done = f"the organiser did not approve {start}", False
        else:
            result = commit(self.scenario, start, end, world.store_approval(start, end, decision), self.agents)
            text, done = self.describe(result), result["status"] == "sent" and not result["declined_required"]
            world.note("gate", "gate", text, ["coordinator", "organiser"])
            if done:
                self.outcome = Outcome(status="scheduled", start=start, end=end, message=text)
        return {"messages": rest + [ToolMessage(text, tool_call_id=gated["id"], name="request_approval")], "done": done}

    @staticmethod
    def describe(result: dict) -> str:
        if result["status"] == "refused":
            return (f"not sent: the slot is no longer free for {result['stale'] or 'nobody'}; "
                    f"consent missing from {result['unconsented'] or 'nobody'}. Find another slot.")
        if result["status"] == "unverified":
            return "not verified: the invite is not on every calendar"
        if result["declined_required"]:
            return f"invite sent, but required attendee(s) {result['declined_required']} declined. Replan."
        return "invite sent and verified" + (f"; optional {result['declined_optional']} declined" if result["declined_optional"] else "")

    def nudge(self, state: State):
        return {"messages": [HumanMessage("Finish by calling request_approval or hand_back.")]}

    def start(self) -> dict | None:
        """Build the graph and run it until the organiser must decide. Returns what they are
        asked to approve ({"start", "end"}), or None when the run has ended."""
        g = StateGraph(State)
        for name, fn in [("agent", self.agent), ("tools", self.run_tools), ("approve", self.approve), ("nudge", self.nudge)]:
            g.add_node(name, fn)
        g.add_edge(START, "agent")
        g.add_conditional_edges("agent", self.route, ["tools", "approve", "nudge", END])
        g.add_conditional_edges("tools", lambda s: END if s.get("done") else "agent", ["agent", END])
        g.add_conditional_edges("approve", lambda s: END if s.get("done") else "agent", ["agent", END])
        g.add_edge("nudge", "agent")
        self.graph = g.compile(checkpointer=InMemorySaver())

        world.fire("start")
        r = self.scenario.request
        who = "\n".join(f"- {a.id} {self.scenario.participant(a.id).name} ({a.role})" for a in r.attendees)
        thread = "\n".join(world.THREAD) or "(empty)"
        first = HumanMessage(f"Request from {r.organiser_id}: {r.text}\nDuration {r.duration_min} min, "
                             f"{r.start_date} to {r.end_date}, {r.day_start}-{r.day_end}.\nAttendees:\n{who}\n"
                             f"Request thread so far:\n{thread}")
        world.note(r.organiser_id, "request", r.text, ["thread"])
        self.config = {"configurable": {"thread_id": r.id}, "recursion_limit": 80}
        return self.pending(self.graph.invoke({"messages": [first]}, self.config))

    def resume(self, decision: str) -> dict | None:
        """Continue after the organiser's decision ("approve" or "reject")."""
        return self.pending(self.graph.invoke(Command(resume=decision), self.config))

    def pending(self, out) -> dict | None:
        if "__interrupt__" in out:
            return out["__interrupt__"][0].value
        world.CONTEXT.append(self.system)
        world.CONTEXT += [str(m.content) for m in out["messages"]]
        world.note("coordinator", "outcome", f"{self.outcome.status} {self.outcome.start or ''} {self.outcome.message}".strip(),
                   ["thread"])
        return None

    def run(self, decide=world.organiser_decision) -> Outcome:
        """The whole episode; `decide()` gives the organiser's answer each time one is needed."""
        asked = self.start()
        while asked is not None:
            asked = self.resume(decide())
        return self.outcome
