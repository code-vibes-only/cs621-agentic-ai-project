"""The demo app's shared state: people, calendars, chats, private agent chats, requests, tasks
and each request's trace, in one SQLite file that every browser session reads and writes.

It is runtime state, not data: `data/demo/app.db` is gitignored and `reset()` rebuilds it from
the demo seed. Set SCHEDULER_DEMO_DB to use another file (the tests do)."""
import json
import os
import sqlite3
import threading
import time
from contextlib import closing

from scheduler.config import ROOT

SCHEMA = """
create table if not exists people (id text primary key, name text, hours_start text, hours_end text,
                                   contact integer default 0);
create table if not exists calendars (id text primary key, owner text, name text, kind text, color text);
create table if not exists events (id text primary key, calendar_id text, title text, start_at text, end_at text,
                                   flex integer default 0, request_id text);
create table if not exists chats (id text primary key, title text, kind text, request_id text, tags text default '');
create table if not exists members (chat_id text, member text);
create table if not exists messages (id integer primary key autoincrement, chat_id text, sender text, text text, ts real);
create table if not exists agent_messages (id integer primary key autoincrement, person text, role text, text text,
                                           request_id text, chat_id text, ts real);
create table if not exists requests (id text primary key, organiser text, text text, status text, mode text,
                                     parsed text, outcome text, chat_id text, created real, kind text default 'meeting');
create table if not exists tasks (id integer primary key autoincrement, person text, request_id text, kind text,
                                  prompt text, payload text, status text default 'open', answer text,
                                  created real, answered real);
create table if not exists trace (id integer primary key autoincrement, request_id text, seq integer, actor text,
                                  kind text, text text, visible_to text, ts real);
create table if not exists settings (key text primary key, value text);
"""

SCHEMA_VERSION = "6"     # a changed schema rebuilds the demo state from the seed
TABLES = ("people", "calendars", "events", "chats", "members", "messages", "agent_messages", "requests", "tasks", "trace")
TAGS = ["academic", "work", "family", "others"]   # what groups can be filtered by
# How easily an item could move, a scale rather than yes or no. What each level means to the agents:
# 0 hard (nobody asks), 1 movable (the coordinator asks you privately first), 2 and 3 soft at weight
# 0.5 and 0.3 ("prefer not": usable without asking, ranked below free time).
FLEX = ["Fixed", "Ask me first", "Flexible", "Easy to move"]
FLEX_HELP = ["Can't move. Nobody is asked about it.",
             "Could move for something important: your agent asks you first.",
             "You'd rather keep it, but your agent may offer the time without asking (only as \"prefer not\").",
             "Hardly matters: your agent treats the time as nearly free."]

# Calendar kinds and their default colours; a person can add more calendars of any kind.
KINDS = {"work": ("Work", "#3b82f6"), "family": ("Family & friends", "#22c55e"), "academic": ("Academic", "#a855f7"),
         "personal": ("Personal", "#f59e0b"), "club": ("Club", "#14b8a6"), "meetings": ("Meetings", "#ef4444"),
         "other": ("Other", "#64748b")}


def path() -> str:
    return os.environ.get("SCHEDULER_DEMO_DB") or str(ROOT / "data" / "demo" / "app.db")


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(path(), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("pragma journal_mode=wal")
    return con


def query(sql: str, args: tuple = ()) -> list[dict]:
    with closing(connect()) as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def execute(sql: str, args: tuple = ()) -> int:
    with closing(connect()) as con, con:
        return con.execute(sql, args).lastrowid


def one(sql: str, args: tuple = ()) -> dict | None:
    rows = query(sql, args)
    return rows[0] if rows else None


def ensure() -> None:
    """Create the tables, and seed them the first time or after a schema change."""
    with closing(connect()) as con, con:
        con.execute("create table if not exists settings (key text primary key, value text)")
        row = con.execute("select value from settings where key = 'schema'").fetchone()
        if not row or row[0] != SCHEMA_VERSION:
            for table in TABLES:
                con.execute(f"drop table if exists {table}")
        con.executescript(SCHEMA)
        con.execute("insert into settings values ('schema', ?) on conflict(key) do update set value = excluded.value",
                    (SCHEMA_VERSION,))
    if not query("select id from people limit 1"):
        reset()


def reset() -> None:
    """Empty every table and load the demo seed again."""
    from scheduler.demo.seed import world_data
    with closing(connect()) as con, con:
        for table in TABLES:
            con.execute(f"drop table if exists {table}")
        con.executescript(SCHEMA)
        con.execute("insert into settings values ('schema', ?) on conflict(key) do update set value = excluded.value",
                    (SCHEMA_VERSION,))
        data = world_data()
        con.execute("delete from settings where key like 'check_first:%' or key like 'responses:%'")
        con.executemany("insert into settings values (?, '1')", [(f"check_first:{pid}",) for pid in data["check_first"]])
        con.executemany("insert into people values (?, ?, ?, ?, ?)",
                        [(p["id"], p["name"], p["hours_start"], p["hours_end"], int(p.get("contact", False)))
                         for p in data["people"]])
        con.executemany("insert into calendars values (?, ?, ?, ?, ?)",
                        [(c["id"], c["owner"], c["name"], c["kind"], c["color"]) for c in data["calendars"]])
        con.executemany("insert into events values (?, ?, ?, ?, ?, ?, null)",
                        [(e["id"], e["calendar_id"], e["title"], e["start"], e["end"], int(e["flex"]))
                         for e in data["events"]])
        for i, chat in enumerate(data["chats"]):
            con.execute("insert into chats values (?, ?, ?, null, ?)", (chat["id"], chat["title"], chat["kind"],
                                                                     ",".join(chat["tags"])))
            con.executemany("insert into members values (?, ?)", [(chat["id"], m) for m in chat["members"]])
            for j, (sender, text) in enumerate(chat["messages"]):
                con.execute("insert into messages (chat_id, sender, text, ts) values (?, ?, ?, ?)",
                            (chat["id"], sender, text, time.time() - 3600 * (len(data["chats"]) - i) + j))


# ------------------------------------------------------------------ people and settings
def people(contacts: bool = True) -> list[dict]:
    return query("select * from people" + ("" if contacts else " where contact = 0") + " order by name")


def name(pid: str) -> str:
    row = one("select name from people where id = ?", (pid,))
    return row["name"] if row else pid


def given(pid: str) -> str:
    """The name a person goes by: everything but the family name ("Mei Ling Chua" -> "Mei Ling")."""
    full = name(pid)
    return full.rsplit(" ", 1)[0] if " " in full else full


def setting(key: str, default: str) -> str:
    row = one("select value from settings where key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    execute("insert into settings values (?, ?) on conflict(key) do update set value = excluded.value", (key, value))


# ------------------------------------------------------------------ calendars
def calendars(owner: str) -> list[dict]:
    return query("select * from calendars where owner = ? order by rowid", (owner,))


def add_calendar(owner: str, name_: str, kind: str, color: str) -> str:
    cid = f"cal-{owner}-{int(time.time() * 1000)}"
    execute("insert into calendars values (?, ?, ?, ?, ?)", (cid, owner, name_, kind, color))
    return cid


def update_calendar(cid: str, name_: str, color: str) -> None:
    execute("update calendars set name = ?, color = ? where id = ?", (name_, color, cid))


def delete_calendar(cid: str) -> None:
    execute("delete from events where calendar_id = ?", (cid,))
    execute("delete from calendars where id = ?", (cid,))


def meetings_calendar(owner: str) -> str:
    row = one("select id from calendars where owner = ? and kind = 'meetings'", (owner,))
    return row["id"] if row else add_calendar(owner, KINDS["meetings"][0], "meetings", KINDS["meetings"][1])


def events(owner: str) -> list[dict]:
    return query("select e.*, c.name as calendar, c.kind, c.color from events e join calendars c on c.id = e.calendar_id "
                 "where c.owner = ? order by e.start_at", (owner,))


def busy_blocks(person: str) -> list[tuple[str, str]]:
    """Everything on the person's calendars, merged into busy blocks: what others may see."""
    blocks: list[list[str]] = []
    for e in sorted(events(person), key=lambda e: e["start_at"]):
        if blocks and e["start_at"] <= blocks[-1][1]:
            blocks[-1][1] = max(blocks[-1][1], e["end_at"])
        else:
            blocks.append([e["start_at"], e["end_at"]])
    return [(s, e) for s, e in blocks]


def event(eid: str) -> dict | None:
    return one("select e.*, c.owner, c.name as calendar from events e join calendars c on c.id = e.calendar_id "
               "where e.id = ?", (eid,))


def add_event(calendar_id: str, title: str, start: str, end: str, flex: int = 0,
              request_id: str | None = None) -> str:
    eid = f"ev-{int(time.time() * 1000)}-{abs(hash((calendar_id, title, start))) % 10000}"
    execute("insert into events values (?, ?, ?, ?, ?, ?, ?)", (eid, calendar_id, title, start, end, int(flex), request_id))
    return eid


def update_event(eid: str, **fields) -> None:
    cols = {"title": "title", "start": "start_at", "end": "end_at", "flex": "flex", "calendar_id": "calendar_id"}
    sets = [(cols[k], int(v) if k == "flex" else v) for k, v in fields.items() if k in cols]
    if sets:
        execute(f"update events set {', '.join(f'{c} = ?' for c, _ in sets)} where id = ?", tuple(v for _, v in sets) + (eid,))


def delete_event(eid: str) -> None:
    execute("delete from events where id = ?", (eid,))


# ------------------------------------------------------------------ chats
def chats(person: str) -> list[dict]:
    """The person's chats, most recent first, with the last message."""
    return query("""select c.*, (select text from messages m where m.chat_id = c.id order by m.id desc limit 1) as last,
                           (select max(ts) from messages m where m.chat_id = c.id) as last_ts
                    from chats c join members k on k.chat_id = c.id where k.member = ?
                    order by coalesce(last_ts, 0) desc""", (person,))


def chat(chat_id: str) -> dict | None:
    return one("select * from chats where id = ?", (chat_id,))


def members(chat_id: str) -> list[str]:
    return [r["member"] for r in query("select member from members where chat_id = ? order by rowid", (chat_id,))]


def messages(chat_id: str) -> list[dict]:
    return query("select * from messages where chat_id = ? order by id", (chat_id,))


def send(chat_id: str, sender: str, text: str) -> None:
    execute("insert into messages (chat_id, sender, text, ts) values (?, ?, ?, ?)", (chat_id, sender, text, time.time()))


def new_chat(title: str, kind: str, people_: list[str], request_id: str | None = None,
             tags: list[str] | None = None) -> str:
    cid = f"chat-{int(time.time() * 1000)}"
    execute("insert into chats values (?, ?, ?, ?, ?)", (cid, title, kind, request_id, ",".join(tags or [])))
    for p in people_:
        execute("insert into members values (?, ?)", (cid, p))
    return cid


def clean_tag(tag: str) -> str:
    """A tag as stored: lower case, no commas (they separate tags), trimmed."""
    return " ".join(tag.replace(",", " ").split()).lower()[:24]


def set_tags(chat_id: str, tags: list[str]) -> None:
    """A group's tags, shared by everyone in it."""
    tags = [t for t in dict.fromkeys(clean_tag(t) for t in tags) if t]
    execute("update chats set tags = ? where id = ?", (",".join(tags), chat_id))


def all_tags(person: str) -> list[str]:
    """The built-in tags, then any custom ones on the person's groups."""
    custom = sorted({t for c in chats(person) for t in (c["tags"] or "").split(",") if t and t not in TAGS})
    return TAGS + custom


def direct_chat(a: str, b: str) -> str:
    """The one-to-one chat between two people, created if needed."""
    for c in query("select id from chats where kind = 'dm'"):
        if sorted(members(c["id"])) == sorted([a, b]):
            return c["id"]
    return new_chat("", "dm", [a, b])


def group_with(people_: set[str]) -> str | None:
    """An existing group chat with exactly these members."""
    for c in query("select id from chats where kind = 'group'"):
        if set(members(c["id"])) == people_:
            return c["id"]
    return None


def inbox(person: str, limit: int = 15) -> list[dict]:
    """Messages other people sent in this person's chats: what their personal agent may read."""
    return query("""select m.*, c.title, c.kind from messages m join chats c on c.id = m.chat_id
                    join members k on k.chat_id = c.id
                    where k.member = ? and m.sender != ? and m.sender not like 'agent:%' and m.sender != 'coordinator'
                    order by m.id desc limit ?""", (person, person, limit))


# ------------------------------------------------------------------ the private agent chat
def agent_messages(person: str, chat_id: str | None = None) -> list[dict]:
    """The person's private agent chat: for one group, or all of it."""
    if chat_id is None:
        return query("select * from agent_messages where person = ? order by id", (person,))
    return query("select * from agent_messages where person = ? and chat_id = ? order by id", (person, chat_id))


def agent_say(person: str, role: str, text: str, request_id: str | None = None, chat_id: str | None = None) -> int:
    """A line in the person's private agent chat, filed under the request's group. Returns its id."""
    if chat_id is None and request_id:
        chat_id = (one("select chat_id from requests where id = ?", (request_id,)) or {}).get("chat_id")
    return execute("insert into agent_messages (person, role, text, request_id, chat_id, ts) values (?, ?, ?, ?, ?, ?)",
                   (person, role, text, request_id, chat_id, time.time()))


def unread(person: str, chat_id: str | None = None) -> list[dict]:
    """What the person's agent told them that they have not seen yet, newest first: the
    notifications. Seen means they opened that group's agent chat since."""
    rows = query("select * from agent_messages where person = ? and role != 'me' order by id desc", (person,))
    return [m for m in rows if (chat_id is None or m["chat_id"] == chat_id)
            and m["id"] > int(setting(f"seen:{person}:{m['chat_id']}", "0"))]


def mark_seen(person: str, chat_id: str) -> None:
    last = one("select max(id) as id from agent_messages where person = ? and chat_id = ?", (person, chat_id))
    if last and last["id"]:
        set_setting(f"seen:{person}:{chat_id}", str(last["id"]))


def update_agent_message(mid: int, text: str) -> None:
    """Rewrite one agent line in place, e.g. a progress line that grows as replies arrive."""
    execute("update agent_messages set text = ?, ts = ? where id = ?", (text, time.time(), mid))


# ------------------------------------------------------------------ requests, tasks and traces
def new_request(organiser: str, text: str, mode: str, kind: str = "meeting", chat_id: str | None = None) -> str:
    """kind "meeting" is a group request run by the agents; "analyse" is one person's calendar item."""
    rid = f"r-{int(time.time() * 1000)}"
    execute("insert into requests values (?, ?, ?, 'queued', ?, null, null, ?, ?, ?)",
            (rid, organiser, text, mode, chat_id, time.time(), kind))
    return rid


def request(rid: str) -> dict | None:
    row = one("select * from requests where id = ?", (rid,))
    if row:
        row["parsed"] = json.loads(row["parsed"]) if row["parsed"] else None
        row["outcome"] = json.loads(row["outcome"]) if row["outcome"] else None
    return row


def requests(person: str | None = None) -> list[dict]:
    rows = query("select id from requests order by created desc")
    out = [request(r["id"]) for r in rows]
    if person is None:
        return out
    return [r for r in out if r["organiser"] == person or person in ((r["parsed"] or {}).get("attendee_ids") or [])]


def update_request(rid: str, **fields) -> None:
    if "status" in fields and (request(rid) or {}).get("status") == "cancelled":
        fields.pop("status")                        # a cancelled request stays cancelled, whatever the run says next
        if not fields:
            return
    sets = [(k, json.dumps(v) if k in ("parsed", "outcome") else v) for k, v in fields.items()]
    execute(f"update requests set {', '.join(f'{k} = ?' for k, _ in sets)} where id = ?", tuple(v for _, v in sets) + (rid,))


def add_task(person: str, rid: str, kind: str, prompt: str, payload: dict | None = None) -> int:
    return execute("insert into tasks (person, request_id, kind, prompt, payload, created) values (?, ?, ?, ?, ?, ?)",
                   (person, rid, kind, prompt, json.dumps(payload or {}), time.time()))


def task(tid: int) -> dict | None:
    row = one("select * from tasks where id = ?", (tid,))
    if row:
        row["payload"] = json.loads(row["payload"] or "{}")
    return row


def tasks(person: str, history: bool = False) -> list[dict]:
    rows = query("select id from tasks where person = ? and status " + ("!= 'open'" if history else "= 'open'")
                 + " order by id desc", (person,))
    return [task(r["id"]) for r in rows]


def answer_task(tid: int, answer: str) -> None:
    execute("update tasks set status = 'done', answer = ?, answered = ? where id = ? and status = 'open'",
            (answer, time.time(), tid))


def open_count(person: str, chat_id: str) -> int:
    """How many of the person's tasks wait in this group: the red number."""
    return query("select count(*) as n from tasks t join requests r on r.id = t.request_id "
                 "where t.person = ? and t.status = 'open' and r.chat_id = ?", (person, chat_id))[0]["n"]


def group_tasks(person: str, chat_id: str, history: bool = False) -> list[dict]:
    rows = query("select t.id from tasks t join requests r on r.id = t.request_id where t.person = ? and r.chat_id = ? "
                 "and t.status " + ("!= 'open'" if history else "= 'open'") + " order by t.id desc", (person, chat_id))
    return [task(r["id"]) for r in rows]


def open_tasks(rid: str) -> int:
    """How many questions about this request still wait for someone."""
    return query("select count(*) as n from tasks where request_id = ? and status = 'open'", (rid,))[0]["n"]


def expire_task(tid: int) -> None:
    execute("update tasks set status = 'expired', answered = ? where id = ? and status = 'open'", (time.time(), tid))


def expire_tasks(rid: str) -> None:
    execute("update tasks set status = 'expired', answered = ? where request_id = ? and status = 'open'", (time.time(), rid))


TRACING = threading.Lock()                   # steps can arrive from several threads at once


def add_trace(rid: str, actor: str, kind: str, text: str, visible_to: list[str]) -> None:
    with TRACING, closing(connect()) as con, con:
        seq = con.execute("select coalesce(max(seq), 0) + 1 from trace where request_id = ?", (rid,)).fetchone()[0]
        con.execute("insert into trace (request_id, seq, actor, kind, text, visible_to, ts) values (?, ?, ?, ?, ?, ?, ?)",
                    (rid, seq, actor, kind, text, json.dumps(visible_to), time.time()))


def trace(rid: str) -> list[dict]:
    rows = query("select * from trace where request_id = ? order by seq", (rid,))
    for r in rows:
        r["visible_to"] = json.loads(r["visible_to"])
    return rows
