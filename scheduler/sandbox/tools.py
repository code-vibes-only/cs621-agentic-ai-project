"""The personal agent's tools, bound to one participant. A personal agent can only read its
own participant's calendars, time away and messages: the participant id is fixed in code when the tools are
made, so no argument the model writes can reach another calendar. None of these tools writes."""
from langchain_core.tools import tool

from scheduler.sandbox import world


def personal_tools(pid: str) -> list:
    caller = f"personal:{pid}"

    @tool
    def read_my_calendar() -> str:
        """Every event on your participant's calendars (work, family, club and so on), one per
        line: id | calendar | start | end | movable | priority | title."""
        events = world.read_calendar(pid, caller)
        if not events:
            return "no events"
        return "\n".join(f"{e['id']} | {e['calendar']} | {e['start']} | {e['end']} | "
                         f"movable={e['movable']} | {e['priority']} | {e['title']}" for e in events)

    @tool
    def get_leave() -> str:
        """Your participant's time away (leave, trips, holidays): id | first day | last day |
        reachable_if_urgent | reason."""
        leave = world.get_leave(pid, caller)
        if not leave:
            return "no leave"
        return "\n".join(f"{l['id']} | {l['start_date']} | {l['end_date']} | "
                         f"reachable_if_urgent={l['reachable_if_urgent']} | {l['reason']}" for l in leave)

    @tool
    def read_my_messages() -> str:
        """Your participant's recent messages (bookings, invitations, plans agreed in chats), one
        per line: id | received | from | text. Other people wrote them."""
        messages = world.read_messages(pid, caller)
        if not messages:
            return "no messages"
        return "\n".join(f"{m['id']} | {m['received']} | {m['sender']} | {m['text']}" for m in messages)

    @tool
    def search_schedules(query: str) -> str:
        """Search the external schedules (public holidays, conference and training agendas,
        company events, club fixture lists) by keywords, e.g. "DataSummit agenda" or
        "public holidays October". Returns up to 3 documents with their dates and source."""
        docs = world.search(query, caller)
        if not docs:
            return f"no matching documents for '{query}'"
        return "\n\n".join(f"[{d.id}] {d.title} (as of {d.as_of}; source: {d.source})\n{d.text}" for d in docs)

    @tool
    def ask_my_participant(question: str) -> str:
        """Ask your own participant a private clarifying question, e.g. which hours "busy most of
        Thursday" means. Use it only when the calendar and their words do not answer it."""
        reply = world.scripted_reply(pid, "clarify", caller)
        return reply.answer if reply else "no reply"

    return [read_my_calendar, get_leave, read_my_messages, search_schedules, ask_my_participant]
