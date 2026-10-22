"""The demo app's starting world: ten fictional people, their calendars and their groups.

Alice is in all three circles: her CS621 project group (Bob, Charlie, Damian, Eve), her data
team at work (Felicia, George), and her friends and family (Hannah, Ignatius, Jack). Everything
here is invented; the logins are in data/demo/users.json. `store.reset()` loads this world.

The week of Mon 26 Oct is set up so the academic demo has a story: every weekday evening is
blocked for someone, and Wednesday works only if Charlie swaps a cafe shift he marked "ask me first", so the
coordinator has to ask him privately. The group has met on the last two Wednesdays, Charlie swapped that shift
once before, and Bob asked his agent to check with him before accepting anything."""
from datetime import datetime, timedelta

from scheduler.timegrid import horizon_days

CORPUS = ["doc-sg-public-holidays-2026"]   # what the personal agents may look up

PEOPLE = {   # id: name, usual hours, who they are
    "alice": ("Alice Tan", "08:00", "23:00", "Part-time student, data analyst by day"),
    "bob": ("Bob Lee", "07:00", "23:00", "Part-time student, logistics shift lead"),
    "charlie": ("Charlie Ng", "09:00", "23:30", "Full-time student, part-time barista"),
    "damian": ("Damian Koh", "07:00", "21:00", "Part-time student, parent of Ethan"),
    "eve": ("Eve Lim", "08:00", "22:30", "Part-time student, cares for her mother"),
    "felicia": ("Felicia Wong", "08:30", "18:30", "Alice's manager"),
    "george": ("George Ong", "09:00", "18:00", "Alice's colleague"),
    "hannah": ("Hannah Tan", "08:00", "22:00", "Alice's sister, a nurse"),
    "ignatius": ("Ignatius Chua", "09:00", "23:00", "Alice's friend"),
    "jack": ("Jack Lim", "09:00", "23:00", "Alice's friend"),
}

# person: [(calendar kind, title, start, end, flexibility 0-3: see store.FLEX)]
EVENTS = {
    "alice": [("work", "Quarterly data review", "2026-10-26T09:00", "2026-10-26T11:00", 0),
              ("academic", "Data visualisation seminar", "2026-10-27T19:00", "2026-10-27T22:00", 0),
              ("personal", "Gym", "2026-10-29T07:00", "2026-10-29T08:00", 2),
              ("family", "Mum's birthday lunch", "2026-11-01T12:00", "2026-11-01T15:00", 0)],
    "bob": [("work", "Late shift at the depot", "2026-10-26T14:00", "2026-10-26T22:00", 0),
            ("personal", "Futsal", "2026-10-31T09:00", "2026-10-31T11:00", 1)],
    "charlie": [("work", "Cafe shift", "2026-10-28T18:00", "2026-10-28T21:00", 1),
                ("personal", "Visa interview prep", "2026-10-27T18:00", "2026-10-27T19:30", 0)],
    "damian": [("family", "Ethan's tuition pick-up", "2026-10-29T18:30", "2026-10-29T19:30", 0),
               ("family", "Ethan's swimming lesson", "2026-10-31T09:00", "2026-10-31T11:00", 0)],
    "eve": [("personal", "Away: hospital follow-up with my mother", "2026-10-29T00:00", "2026-10-29T23:59", 0),
            ("personal", "Away: hospital follow-up with my mother", "2026-10-30T00:00", "2026-10-30T23:59", 0)],
    "felicia": [("work", "Leadership offsite", "2026-10-29T09:00", "2026-10-29T18:00", 0),
                ("work", "Budget review with finance", "2026-10-27T12:00", "2026-10-27T13:30", 0)],
    "george": [("work", "Client workshop", "2026-10-28T09:00", "2026-10-28T13:00", 0),
               ("personal", "Dentist", "2026-10-26T12:30", "2026-10-26T13:30", 0)],
    "hannah": [("family", "Kids' piano recital", "2026-10-31T10:00", "2026-10-31T12:00", 0),
               ("work", "Night shift", "2026-10-30T19:00", "2026-10-30T23:59", 0)],
    "ignatius": [("club", "Football league match", "2026-10-31T16:00", "2026-10-31T18:00", 0)],
    "jack": [("work", "Weekend shift", "2026-11-01T10:00", "2026-11-01T18:00", 0),
             ("personal", "Movie night (flexible)", "2026-10-31T19:00", "2026-10-31T22:00", 3)],
}

# person: [(calendar kind, title, weekdays, start, end)], for the two weeks from Mon 26 Oct
ROUTINES = {
    "alice": [("work", "Office (data team)", "mon tue wed thu fri", "09:00", "12:00"),
              ("work", "Office (data team)", "mon tue wed thu fri", "14:00", "18:00")],
    "bob": [("work", "Early shift at the depot", "tue wed thu fri", "07:00", "15:00")],
    "charlie": [("academic", "Lecture: Machine Learning", "mon wed", "10:00", "12:00"),
                ("academic", "Lab: Data Engineering", "tue", "14:00", "17:00")],
    "damian": [("work", "Office", "mon tue wed thu fri", "09:00", "17:00")],
    "eve": [("work", "Clinic admin shift", "mon tue wed", "09:00", "17:30")],
    "felicia": [("work", "Leadership sync", "mon", "09:00", "10:00")],
    "george": [("work", "Stand-up", "mon tue wed thu fri", "09:30", "10:00")],
    "hannah": [("work", "Ward shift", "mon tue wed thu", "07:00", "19:00")],
    "ignatius": [("work", "Office", "mon tue wed thu fri", "09:00", "18:00")],
    "jack": [("work", "Office", "mon tue wed thu", "10:00", "19:00")],
}

# person: [(what they told their agent, weekdays, start, end, weight)]. The words name the exact days and
# hours, so their agent never has to ask what they meant. Their agent keeps these as
# memory notes and turns them into soft rules: the coordinator sees only "prefer not" on those
# slots, never why, and ranks them below free ones. Weight 0.3 mild, 0.5 normal, 0.8 strong.
PREFERENCES = {
    "alice": [("Any day, I'd rather not have meetings after 21:30: I start work early", "mon tue wed thu fri sat sun",
               "21:30", "23:59", 0.3)],
    "bob": [("Saturday and Sunday mornings, 08:00 to 12:00, are for futsal: I'd rather not meet then", "sat sun",
             "08:00", "12:00", 0.5)],
    "charlie": [("Any day, I'd rather not meet before 10:00: I'm not a morning person", "mon tue wed thu fri sat sun",
                 "00:00", "10:00", 0.3)],
    "damian": [("Saturdays and Sundays, all day, are family time with Ethan: only if it really can't be helped", "sat sun",
                "00:00", "23:59", 0.8)],
    "eve": [("Sundays, all day, I'm with my mother: I'd rather keep them free", "sun", "00:00", "23:59", 0.8)],
    "hannah": [("Monday to Thursday after 19:00 I've just finished a ward shift: I'd rather not meet then",
                "mon tue wed thu", "19:00", "23:59", 0.5)],
}

# person: what they told their agent once, kept as a memory note: facts, not times.
NOTES = {
    "charlie": ["On Wed 14 Oct I swapped my cafe shift with Sam so I could make the CS621 meeting."],
}

# Who asked their agent never to accept a meeting without checking with them first. Kept in code: their
# agent tells the coordinator that every time needs their yes, and asks them about the exact time.
CHECK_FIRST = {"bob": "Don't accept anything without checking with me first."}

# Meetings a group already had: (chat, title, starts, minutes), on every member's Meetings calendar.
PAST = [("chat-cs621", "CS621 project meeting", ["2026-10-14T19:00", "2026-10-21T19:00"], 90)]

GROUPS = [
    {"id": "chat-cs621", "title": "CS621 project group", "kind": "group", "tags": ["academic"],
     "members": ["alice", "bob", "charlie", "damian", "eve"],
     "messages": [("alice", "Hi all, the deck is due Fri 30 Oct. We should meet next week to split the slides."),
                  ("charlie", "Evenings work best for me, I'm on campus most days."),
                  ("damian", "Weeknights are tricky with Ethan, but I'll make it work."),
                  ("eve", "Earlier in the week is better for me."),
                  ("bob", "Same, anything but Monday.")]},
    {"id": "chat-data-team", "title": "Data team", "kind": "group", "tags": ["work"],
     "members": ["alice", "felicia", "george"],
     "messages": [("felicia", "Let's do a 30-minute sync on the Q4 dashboard next week."),
                  ("george", "Lunchtime works for me, mornings are packed."),
                  ("alice", "I'll get my agent to find a slot.")]},
    {"id": "chat-friends", "title": "Friends & family", "kind": "group", "tags": ["family"],
     "members": ["alice", "hannah", "ignatius", "jack"],
     "messages": [("hannah", "Dinner this weekend? It's been ages."),
                  ("jack", "I'm in. Sunday I work till 6 though."),
                  ("ignatius", "Saturday afternoon I have a match, evening is fine.")]},
    {"id": "chat-alice-bob", "title": "", "kind": "dm", "tags": ["academic"], "members": ["alice", "bob"],
     "messages": [("bob", "Did you finish the metrics section?"), ("alice", "Almost, I'll push it tonight.")]},
    {"id": "chat-alice-hannah", "title": "", "kind": "dm", "tags": ["family"], "members": ["alice", "hannah"],
     "messages": [("hannah", "Don't forget Mum's birthday lunch on Sunday 1 Nov, 12 to 3!"),
                  ("alice", "Wouldn't miss it.")]},
    {"id": "chat-badminton", "title": "Badminton kakis", "kind": "group", "tags": ["others"],
     "members": ["alice", "charlie", "jack"],
     "messages": [("jack", "Court's booked for next Thursday 8pm, who's coming?")]},
]


def world_data() -> dict:
    """Everyone's calendars, events and groups, ready for store.reset()."""
    from scheduler.demo.store import KINDS
    people = [{"id": pid, "name": n, "hours_start": hs, "hours_end": he} for pid, (n, hs, he, _) in PEOPLE.items()]
    calendars = [{"id": f"cal-{pid}-{kind}", "owner": pid, "name": KINDS[kind][0], "kind": kind, "color": KINDS[kind][1]}
                 for pid in PEOPLE for kind in ("work", "family", "academic", "personal", "meetings")]
    calendars += [{"id": "cal-ignatius-club", "owner": "ignatius", "name": KINDS["club"][0], "kind": "club",
                   "color": KINDS["club"][1]}]
    events = []
    for pid, items in EVENTS.items():
        for i, (kind, title, start, end, flex) in enumerate(items):
            events.append({"id": f"e-{pid}-{i}", "calendar_id": f"cal-{pid}-{kind}", "title": title,
                           "start": start, "end": end, "flex": int(flex)})
    for pid, routines in ROUTINES.items():
        for i, (kind, title, days, start, end) in enumerate(routines):
            for d in horizon_days("2026-10-26", "2026-11-06", days.split()):
                events.append({"id": f"e-{pid}-r{i}-{d}", "calendar_id": f"cal-{pid}-{kind}", "title": title,
                               "start": f"{d}T{start}", "end": f"{d}T{end}", "flex": 0})
    members = {g["id"]: g["members"] for g in GROUPS}
    for chat, title, starts, minutes in PAST:
        for start in starts:
            end = (datetime.fromisoformat(start) + timedelta(minutes=minutes)).isoformat(timespec="minutes")
            events += [{"id": f"e-{pid}-past-{start}", "calendar_id": f"cal-{pid}-meetings", "title": title,
                        "start": start, "end": end, "flex": 0} for pid in members[chat]]
    return {"people": people, "calendars": calendars, "events": events, "chats": GROUPS, "check_first": list(CHECK_FIRST)}
