"""The privacy filter: code between the agents and everyone else.

1. Every availability summary must match the schema exactly: no extra field, no free text.
2. Every message for the request thread is checked before it is posted. It is blocked if it
   carries a private detail (a word from a calendar title or a reason for time away, or a name
   in a message, that is not an everyday word and not in the public request) or attributes a
   reason to a participant ("Ben is on leave")."""
import re

from pydantic import ValidationError

from scheduler.contracts.availability import AvailabilitySummary
from scheduler.sandbox import world

REASONS = (r"(leave|away|sick|ill|clinic|doctor|dentist|appointment|medical|hospital|holiday|vacation|"
           r"conference|summit|training|steering|confidential|family|personal|private|focus|busy with)")
EVERYDAY = set("""meeting meetings review call sync focus block planning session project weekly team client lunch
monday tuesday wednesday thursday friday october november morning afternoon evening with from about kickoff
appointment model forecast notes update board pack preparation quarter close regional audit walkthrough
sprint vendor budget leadership retro design dentist family personal matter handover saturday sunday weekend
dinner drinks practice game match booking confirmed invitation plans move skip flexible""".split())


def validate_summary(raw: dict) -> AvailabilitySummary:
    """Reject any summary that is not exactly the schema."""
    try:
        summary = AvailabilitySummary.model_validate(raw)
    except ValidationError as e:
        world.guard("summary schema", "tool result", f"summary from {raw.get('participant_id')}", False, str(e)[:200])
        raise
    world.guard("summary schema", "tool result", f"summary from {summary.participant_id}", True)
    return summary


def names_in(text: str) -> list[str]:
    """Capitalised words that do not start a sentence: the names in a message ("Banyan Clinic"),
    not its ordinary words."""
    return [w for sentence in re.split(r"[.!?:]\s+", text) for w in sentence.split()[1:] if w[:1].isupper()]


def private_words() -> set[str]:
    """Distinctive words from every calendar title and reason for time away, and the names in
    every message. Words of the request itself are public: everyone in the thread has read it."""
    texts = [e["title"] for events in world.CALENDARS.values() for e in events if not e["id"].startswith("invite-")]
    texts += [l.reason for p in world.SCENARIO.participants for l in p.leave]
    texts += [" ".join(names_in(m.text)) for p in world.SCENARIO.participants for m in p.messages]
    words = set()
    for text in texts:
        for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text):
            if word.lower() not in EVERYDAY:
                words.add(word.lower())
    names = {part.lower() for p in world.SCENARIO.participants for part in p.name.split()}
    public = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", world.SCENARIO.request.text)}
    return words - names - public


def why_blocked(text: str) -> str | None:
    """The reason a thread message must not be posted, or None if it is clean."""
    low = text.lower()
    for word in private_words():
        if re.search(rf"\b{re.escape(word)}\b", low):
            return f"private detail '{word}'"
    for p in world.SCENARIO.participants:
        for name in (p.name.split()[0].lower(), p.id):
            if re.search(rf"\b{re.escape(name)}\b[^.]{{0,40}}\b{REASONS}\b", low):
                return f"attributes a reason to {p.id}"
    return None


def post(text: str, sender: str) -> str:
    """Post to the request thread if clean; otherwise block it and say why (to the sender only)."""
    reason = why_blocked(text)
    world.log("post_to_thread", sender, text=text, blocked=reason)
    world.guard("privacy filter", "output", f"thread message from {sender}", reason is None, reason or "")
    if reason:
        world.BLOCKED.append(text)
        world.note("privacy filter", "blocked", f"stopped a message from {sender}: {reason}", [sender, "system"])
        return f"blocked by the privacy filter ({reason}); rewrite it without anyone's reasons or details"
    world.THREAD.append(f"{sender}: {text}")
    world.note(sender, "thread", text, ["thread"])
    return "posted"
