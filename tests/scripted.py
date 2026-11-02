"""Scripted stand-ins shared by the tests that drive the coordinator without a model."""
import itertools

from langchain_core.messages import AIMessage, ToolMessage

from scheduler.contracts.availability import AvailabilitySummary, SlotStatus

_ids = itertools.count()


def ai(*calls):
    return AIMessage(content="", tool_calls=[{"name": n, "args": a, "id": f"call-{next(_ids)}"} for n, a in calls])


class Script:
    """The model's next replies, in order, then idle talk with no tool call. Keeps what it was shown."""
    def __init__(self, *replies):
        self.replies, self.seen = list(replies), []

    def __call__(self, messages):
        self.seen.append(list(messages))
        return self.replies.pop(0) if self.replies else AIMessage(content="Let me think.")

    def tool_texts(self):
        """Every tool answer the model has been shown so far, oldest first."""
        return [m.content for m in self.seen[-1] if isinstance(m, ToolMessage)] if self.seen else []


class Stub:
    """A personal agent with a hand-written summary: no parsing, no model."""
    def __init__(self, scenario, pid, blocked=(), relaxable=(), answer="yes"):
        self.scenario, self.pid, self.blocked, self.relaxable, self.answer, self.declined = scenario, pid, set(blocked), set(relaxable), answer, []

    def summary(self, slots):
        return AvailabilitySummary(participant_id=self.pid, request_id=self.scenario.request.id, slots=[
            SlotStatus(start=a, end=b, status="unavailable" if a in self.blocked else "available", relaxable=a in self.blocked and a in self.relaxable)
            for a, b in slots])

    def answer_relax(self, start, end):
        return self.answer

    def decline(self, start, end):
        self.declined.append((start, end))


def agents(s, **blocked):
    """One stub per attendee; blocked={"p01": {slots...}} makes those slots unavailable for that person."""
    return {a.id: Stub(s, a.id, blocked.get(a.id, ())) for a in s.request.attendees}
