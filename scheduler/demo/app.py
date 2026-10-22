"""The scheduler demo app: one live, shared world that several people use at once.

    uv run --group demo python -m streamlit run scheduler/demo/app.py

Sign in as one of ten fictional people (alice ... jack; each password is the username). Open a
second browser to be someone else at the same time.

- Groups: your group chats, filtered by people or tag. In a group, "My agent" is your private
  chat with your own personal agent: "Let's have a 90-minute meeting to plan the deck next week,
  evenings" starts a scheduling run for that group (scheduler/demo/engine.py). A meeting-like
  message in the group chat itself gets a nudge to hand it to your agent. A red number means
  your agent needs you there: a yes or no, or which time you prefer.
- Calendar: your calendars by colour. "Add only" adds an item as you type it; "Add and analyse"
  lets your agent check your calendars and ask you a few questions first
  (scheduler/demo/analyse.py). Click an item the agents added (✨) to view its trace.
- Trace: a replay of one request, step by step: the host's agent, the coordinator agent and
  yours on top, everyone else's agents below. It shows every agent's steps, private ones
  included, so it is a demo view, not something a participant would see.

With "Enable model calls" off (the default, under Demo tools) the agents are scripted, at no cost;
switch it on to use the real model with the OPENAI_API_KEY in your local .env. Nothing here produces a reported number; those
come only from `python -m scheduler.eval --report`."""
import hmac
import html
import json
import os
import re
from datetime import date, datetime, time, timedelta

import streamlit as st
from streamlit_calendar import calendar

from scheduler.config import load_settings
from scheduler.demo import analyse, engine, store
from scheduler.demo.engine import nice_day, nice_slot
from scheduler.demo.seed import NOTES, PEOPLE, PREFERENCES

settings = load_settings()
st.set_page_config(page_title="Scheduler demo", page_icon="📅", layout="wide")
store.ensure()
engine.recover()                 # runs that died with an earlier server process stop cleanly, never half-way
USERS = {u["username"]: u for u in json.loads((settings.data_dir / "demo" / "users.json").read_text())["users"]}
TAG_ICON = {"academic": "🎓", "work": "💼", "family": "🏠", "others": "✨"}
DONE = ("scheduled", "hand_back", "error", "budget", "cancelled", "interrupted", "added", "not added")
st.markdown("""<style>
.badge {display: inline-block; min-width: 1.4rem; padding: 0 .4rem; border-radius: 1rem; background: #e5383b;
        color: #fff; font-weight: 700; text-align: center; font-size: .85rem}
.chip {display: inline-block; padding: 0 .45rem; margin-right: .25rem; border-radius: .6rem; font-size: .75rem;
       background: rgba(128,128,128,.18)}
.badge.news {background: #3b82f6}
.dot {display: inline-block; width: .8rem; height: .8rem; border-radius: 50%; vertical-align: middle}
.step {padding: .2rem .45rem; margin: .1rem 0; border-radius: .35rem; font-size: .85rem; opacity: .75}
.step.now {opacity: 1; background: rgba(255, 193, 7, .28); outline: 1px solid rgba(255, 193, 7, .9); font-weight: 600}
.step .seq {display: inline-block; min-width: 1.8rem; color: rgba(128,128,128,.9); font-variant-numeric: tabular-nums}
.step.quiet {opacity: .45}
[class*="st-key-agent-panel"] {background: rgba(124, 58, 237, .07); border: 2px solid rgba(124, 58, 237, .55);
                               border-radius: .8rem; padding: .8rem 1rem}
[class*="st-key-group-panel"] {border: 1px solid rgba(128, 128, 128, .35); border-radius: .8rem; padding: .8rem 1rem}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ signing in
def sign_in() -> None:
    st.title("📅 Scheduler demo")
    st.caption("Sign in as one of the demo people: alice, bob, charlie, damian, eve (CS621 project group), "
               "felicia, george (Alice's data team), hannah, ignatius, jack (Alice's friends and family). "
               "Each password is the username. Everyone here is fictional.")
    with st.form("login"):
        name = st.text_input("Username", key="username")
        word = st.text_input("Password", type="password", key="password")
        if st.form_submit_button("Sign in", type="primary"):
            u = USERS.get(name.strip().lower())
            if u and hmac.compare_digest(u["password"].encode(), word.encode()):
                st.session_state["user"] = u
                st.rerun()
            st.error("Unknown username or wrong password.")


user = st.session_state.get("user")
if user is None:
    sign_in()
    st.stop()
me = user["participant_id"]

st.sidebar.markdown(f"### {store.name(me)}\n{PEOPLE[me][3]}")
if st.sidebar.button("Sign out", key="logout"):
    st.session_state.clear()
    st.rerun()
bell = st.sidebar.container()             # filled at the end of the page, once everything below is defined
with st.sidebar.expander("🔒 What my agent knows about me"):
    for text, *_ in PREFERENCES.get(me, []):
        st.caption(f"“{text}”")
    for text in NOTES.get(me, []):
        st.caption(f"📝 “{text}”")
    if not PREFERENCES.get(me) and not NOTES.get(me):
        st.caption("Nothing yet beyond your calendars.")
    st.caption("Others' agents and the coordinator only ever see when you're free, never why.")
with st.sidebar.expander("⚙️ Preferences"):
    first_ask = st.toggle("Check with me before accepting any meeting", value=engine.check_first(me), key="check-first",
                          help="Your agent tells the coordinator that every time needs your OK, and asks you about the "
                               "exact time before saying yes.")
    if first_ask != engine.check_first(me):
        store.set_setting(f"check_first:{me}", "1" if first_ask else "0")
    st.caption("Others only see that you need asking first, never why.")
with st.sidebar.expander("🧪 Demo tools"):
    real = st.toggle("Enable model calls", value=store.setting("llm_mode", "mock") == "real", key="real-model")
    store.set_setting("llm_mode", "real" if real else "mock")
    if real:
        st.caption(f"Real model ({settings.model}): about USD 0.01 per request, from your own key. New requests use "
                   "this.")
        if not os.environ.get("OPENAI_API_KEY"):
            st.warning("No OPENAI_API_KEY in .env: real-model requests will stop with an error.")
    else:
        st.caption("Off: scripted agents, no API calls, no cost. New requests use this.")
    st.caption(f"Demo date: {nice_day(engine.TODAY)} 2026")
    with st.popover("Reset demo data", width="stretch"):
        st.write("Deletes every message, event, task and request for everyone, and loads the starting world again.")
        if st.button("Reset everything", type="primary", key="reset"):
            store.reset()
            for key in ("group", "trace", "analysis"):
                st.session_state.pop(key, None)
            st.rerun()


# ------------------------------------------------------------------ helpers
def label(actor: str) -> str:
    """How a sender or actor is shown."""
    if actor.startswith(("agent:", "host:")):
        return f"{store.given(actor.split(':', 1)[1])}'s agent"
    if actor.startswith("personal:"):
        return f"{store.given(actor.removeprefix('personal:'))}'s agent"
    if actor.startswith("guardrail:"):
        return f"Guardrail: {actor.removeprefix('guardrail:')}"
    return {"coordinator": "Coordinator agent", "organiser": "Organiser", "gate": "Approval gate",
            "privacy filter": "Privacy filter", "system": "System", "thread": "the group"}.get(actor) or store.name(actor)


def pretty(text: str) -> str:
    """Times as "Wed 28 Oct 19:00", and participant ids as names."""
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", lambda m: nice_slot(m[0]), text)
    return re.sub(r"\b(" + "|".join(PEOPLE) + r")\b", lambda m: store.given(m[0]), text)


def chat_title(c: dict) -> str:
    if c["kind"] == "dm":
        others = [m for m in store.members(c["id"]) if m != me]
        return store.name(others[0]) if others else "Just you"
    return c["title"]


def tag_label(tag: str) -> str:
    return f"{TAG_ICON.get(tag, '🏷️')} {tag}"


def chips(tags: str) -> str:
    return "".join(f'<span class="chip">{html.escape(tag_label(t))}</span>' for t in tags.split(",") if t)


def stamp(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def open_trace(rid: str) -> None:
    st.session_state["trace"] = rid
    st.rerun()


# ------------------------------------------------------------------ groups
@st.fragment(run_every="2s")
def watch_badges() -> None:
    """Redraw the page only when one of your red numbers changes, so buttons never vanish mid-click."""
    counts = [[store.open_count(me, c["id"]), len(store.unread(me, c["id"]))] for c in store.chats(me)]
    if st.session_state.get("badges", counts) != counts:
        st.session_state["badges"] = counts
        st.rerun()
    st.session_state["badges"] = counts


def group_list(groups: list[dict]) -> None:
    if not groups:
        st.caption("No groups match these filters.")
    for c in groups:
        n = store.open_count(me, c["id"])
        with st.container(border=True):
            text, badge = st.columns([5, 1], vertical_alignment="center")
            people = ", ".join(store.given(m) for m in store.members(c["id"]) if m != me)
            text.markdown(f"**{'👥' if c['kind'] == 'group' else '💬'} {html.escape(chat_title(c))}** {chips(c['tags'])}"
                          f"<br><small>{html.escape(people)}</small>", unsafe_allow_html=True)
            news = len(store.unread(me, c["id"]))
            badge.markdown((f'<span class="badge" title="actions">{n}</span> ' if n else "")
                           + (f'<span class="badge news" title="updates from your agent">{news}</span>' if news else ""),
                           unsafe_allow_html=True)
            is_open = st.session_state.get("group") == c["id"]
            if st.button("Close" if is_open else "Open", key=f"open-{c['id']}", width="stretch",
                         type="primary" if is_open else "secondary"):
                if is_open:
                    st.session_state.pop("group")
                else:
                    st.session_state["group"] = c["id"]
                st.rerun()


@st.fragment(run_every="2s")
def messages(cid: str) -> None:
    for m in store.messages(cid):
        mine = m["sender"] == me
        bot = m["sender"].startswith("agent:") or m["sender"] == "coordinator"
        with st.chat_message("user" if mine else label(m["sender"]), avatar=None if mine else "🤖" if bot else "🧑"):
            st.markdown(f"**{'You' if mine else label(m['sender'])}** · {stamp(m['ts'])}  \n{pretty(m['text'])}")


@st.fragment(run_every="2s")
def agent_messages(cid: str) -> None:
    for r in [r for r in store.requests(me) if r["organiser"] == me and r["chat_id"] == cid
              and r["kind"] == "meeting" and r["status"] not in DONE]:
        check = r["status"] == "check with you"
        if check:
            info, go, stop = st.columns([3.6, 1.1, 1.3], vertical_alignment="center")
        else:
            info, stop = st.columns([4, 1.3], vertical_alignment="center")
        topic = (r["parsed"] or {}).get("topic") or ((r["parsed"] or {}).get("ask") or {}).get("topic") or r["text"][:50]
        info.info(f"⏳ **{html.escape(topic)}**: {r['status']}" + (f"  \n{board(r['id'])}" if engine.responses(r["id"]) else ""))
        if check:
            go.button("✅ Go ahead", key=f"confirm-{r['id']}", type="primary", width="stretch", on_click=engine.confirm,
                      args=(r["id"], me), help="Your agent understood it right: start asking everyone's agents.")
        stop.button("✖ Cancel request", key=f"cancel-{r['id']}", width="stretch", on_click=engine.cancel,
                    args=(r["id"], me), help="Stop it before the invite goes out. Nothing reaches anyone's calendar.")
    done = [r for r in store.requests(me) if r["organiser"] == me and r["chat_id"] == cid and r["kind"] == "meeting"
            and r["status"] in DONE]
    if done:                                     # the latest finished request: how it ended, and its trace
        r = done[0]
        out = r["outcome"] or {}
        topic = (r["parsed"] or {}).get("topic") or r["text"][:50]
        stopped = r["status"] == "interrupted"
        if stopped:
            info, again, view = st.columns([3.4, 1.3, 1.3], vertical_alignment="center")
            info.warning(f"**{html.escape(topic)}**: stopped when the app restarted. Nothing was sent.")
            again.button("↻ Run again", key=f"again-{r['id']}", type="primary", width="stretch", on_click=engine.run_again,
                         args=(r["id"], me), help="Start it over. Everyone gets asked again.")
        else:
            info, view = st.columns([4, 1.3], vertical_alignment="center")
            line = (f"✅ **{html.escape(topic)}**: scheduled, {nice_slot(out.get('start'), out.get('end'))}"
                    if r["status"] == "scheduled" else f"**{html.escape(topic)}**: {r['status']}")
            info.success(line + (f"  \n{board(r['id'])}" if engine.responses(r["id"]) else ""))
        if view.button("🔍 View trace", key=f"done-trace-{r['id']}", width="stretch"):
            open_trace(r["id"])
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(f"**Your agent**  \nHi {store.given(me)}. What you tell me here stays private: I only ever share "
                    "when you're free, never why. Ask me to set up a meeting with this group, for example: "
                    "*\"Let's have a 90-minute meeting to plan the deck next week, evenings.\"*")
    for m in store.agent_messages(me, cid):
        mine, coordinator = m["role"] == "me", m["role"] == "coordinator"
        with st.chat_message("user" if mine else "assistant", avatar=None if mine else "🧭" if coordinator else "🤖"):
            st.markdown(f"**{'You' if mine else 'Coordinator agent' if coordinator else 'Your agent'}** · {stamp(m['ts'])}"
                        f"  \n{pretty(m['text'])}")
    store.mark_seen(me, cid)                     # you have read it: no longer a notification


def board(rid: str) -> str:
    """Where each attendee's answer stands: whether they answered, never why."""
    return " · ".join(f"{store.given(pid)} {engine.STATES.get(state, state)}" for pid, state in engine.responses(rid).items())


@st.dialog("Actions", width="large")
def actions(cid: str) -> None:
    tasks = store.group_tasks(me, cid)
    st.markdown(f"#### Needs you ({len(tasks)})")
    if not tasks:
        st.caption("Nothing needs you in this group right now.")
    for t in tasks:
        with st.container(border=True):
            if t["kind"] == "approval":
                st.markdown(f"📨 **Your agent found a time.** {pretty(t['prompt'])}")
                options = [t["payload"]["start"]] + [o["start"] for o in t["payload"].get("options", [])]
                ends = {t["payload"]["start"]: t["payload"]["end"]} | {o["start"]: o["end"] for o in t["payload"].get("options", [])}
                pick = st.radio("Which time do you prefer?", options, key=f"pick-{t['id']}",
                                format_func=lambda s: nice_slot(s, ends[s]) + (" (proposed)" if s == options[0] else ""))
                yes, no, _ = st.columns([1.4, 1, 2])
                if yes.button("Send the invite", type="primary", key=f"yes-{t['id']}", width="stretch"):
                    store.answer_task(t["id"], "Yes" if pick == options[0] else f"Prefer {pick}")
                    store.agent_say(me, "agent", f"Approved {nice_slot(pick, ends[pick])}. I'll send the invite and check "
                                                 "it landed on every calendar.", t["request_id"])
                    st.rerun()
                if no.button("Not now", key=f"no-{t['id']}", width="stretch"):
                    store.answer_task(t["id"], "No")
                    store.agent_say(me, "agent", "Rejected. I'll look for another time.", t["request_id"])
                    st.rerun()
            elif t["kind"] == "consent":
                st.markdown(f"🔒 **Your agent asks you.** {pretty(t['prompt'])}")
                options = t["payload"].get("options") or [{"label": "Yes, I can free it", "answer": "yes"},
                                                          {"label": "Only if nothing else works", "answer": "maybe"},
                                                          {"label": "No, keep it", "answer": "no"}]
                for col, (i, o) in zip(st.columns(len(options)), enumerate(options)):
                    if col.button(o["label"], type="primary" if i == 0 else "secondary", key=f"opt-{t['id']}-{i}",
                                  width="stretch"):
                        store.answer_task(t["id"], o["answer"].capitalize() + (f": {o['suggest']}" if o.get("suggest") else ""))
                        st.rerun()
                own, send = st.columns([4, 1], vertical_alignment="bottom")
                words = own.text_input("Or answer in your own words", key=f"own-{t['id']}",
                                       placeholder="e.g. Swap, but only if everyone else agrees")
                # Never disabled while empty: typing then clicking Send at once must not lose the click.
                if send.button("Send", key=f"own-send-{t['id']}", width="stretch") and words.strip():
                    store.answer_task(t["id"], f"Reply: {words.strip()}")
                    st.rerun()
                st.caption("Your agent reads your answer. Only yes, maybe or no, and any time you suggest, reach the "
                           "coordinator: never your words.")
            else:
                st.markdown(f"❓ **Your agent has a question.** {pretty(t['prompt'])}")
                reply = st.text_input("Your answer", key=f"answer-{t['id']}")
                send, skip, _ = st.columns([1, 1.6, 1.4])
                if send.button("Send", key=f"send-{t['id']}", type="primary", width="stretch") and reply.strip():
                    store.answer_task(t["id"], reply)
                    st.rerun()
                if skip.button("Skip: use your best guess", key=f"skip-{t['id']}", width="stretch",
                               help="Your agent works it out from your calendar and notes, and won't ask again."):
                    store.answer_task(t["id"], "No more detail: use your best judgement from my calendar and notes.")
                    st.rerun()
    if st.toggle("Show history", key=f"history-{cid}"):
        done = store.group_tasks(me, cid, history=True)
        if not done:
            st.caption("No finished actions yet.")
        for t in done:
            mark = "⌛" if t["status"] == "expired" else "⛔" if (t["answer"] or "").startswith("No") else "✅"
            st.markdown(f"{mark} {pretty(t['prompt'])}  \n*{pretty(t['answer'] or 'expired: the request ended first')}*")
    reqs = [r for r in store.requests(me) if r["chat_id"] == cid and r["kind"] == "meeting"]
    if reqs:
        st.markdown("#### Requests in this group")
    for r in reqs:
        topic = (r["parsed"] or {}).get("topic") or r["text"][:50]
        a, b, c = st.columns([3.2, 1, 1], vertical_alignment="center")
        a.markdown(f"**{html.escape(topic)}** · by {store.given(r['organiser'])} · {r['status']}")
        if b.button("🔍 View trace", key=f"trace-{r['id']}"):
            open_trace(r["id"])
        if r["organiser"] == me and r["status"] not in DONE and c.button("✖ Cancel", key=f"cancel-dlg-{r['id']}"):
            engine.cancel(r["id"], me)
            st.rerun()


CHAT, AGENT = "💬 Group chat", "🔒 My agent"
MEETING_WORDS = re.compile(r"\b(meet|meeting|catch ?up|schedule|set up|sync|session|call|get together|dinner|lunch)\b", re.I)


def group_view(cid: str) -> None:
    c = store.chat(cid)
    if c is None or me not in store.members(cid):
        st.session_state.pop("group", None)
        st.rerun()
    head, buttons = st.columns([3, 2], vertical_alignment="center")
    head.markdown(f"### {html.escape(chat_title(c))} {chips(c['tags'])}", unsafe_allow_html=True)
    head.caption(", ".join(store.name(m) for m in store.members(cid)))
    with head.popover("🏷️ Tags"):
        current = [t for t in c["tags"].split(",") if t]
        keep = st.multiselect("Tags", list(dict.fromkeys(store.all_tags(me) + current)), default=current,
                              key=f"tags-{cid}", format_func=tag_label)
        extra = st.text_input("New tag", key=f"tag-new-{cid}", placeholder="e.g. volunteering")
        st.caption("Tags are shared: everyone in the group sees them.")
        if st.button("Save tags", type="primary", key=f"tags-save-{cid}"):
            store.set_tags(cid, keep + ([extra] if extra.strip() else []))
            st.rerun()
    n = store.open_count(me, cid)
    if buttons.button(f"🔴 {n} action{'s need' if n != 1 else ' needs'} you" if n else "Actions and requests",
                      key=f"actions-{cid}", type="primary" if n else "secondary", width="stretch"):
        actions(cid)
    mode = st.session_state.setdefault(f"mode-{cid}", CHAT)
    left, right = st.columns(2)
    left.button(f"{CHAT} · everyone sees it", key=f"tab-chat-{cid}", width="stretch",
                type="primary" if mode == CHAT else "secondary", on_click=switch, args=(cid, CHAT))
    news = len(store.unread(me, cid)) if mode != AGENT else 0
    right.button(f"{AGENT}{f' ({news} new)' if news else ''} · private, sets up meetings", key=f"tab-agent-{cid}",
                 width="stretch",
                 type="primary" if mode == AGENT else "secondary", on_click=switch, args=(cid, AGENT))
    if mode == AGENT:
        with st.container(key=f"agent-panel-{cid}"):
            st.markdown("#### 🔒 Your private agent")
            st.caption("Only you see this chat. Tell your agent what meeting you need: it works it out with the "
                       "others' agents, and only ever shares when you're free, never why.")
            agent_messages(cid)
        text = st.chat_input("🔒 Tell your agent, privately: e.g. Let's have a 90-minute meeting to plan the deck "
                             "next week, evenings", key=f"agent-input-{cid}")
        if text:
            engine.handle_agent_message(me, text, cid)
            st.rerun()
        return
    with st.container(key=f"group-panel-{cid}"):
        title, ask = st.columns([3, 1.6], vertical_alignment="center")
        title.markdown("#### 💬 Group chat")
        ask.button("🔒 Set up a meeting? Ask my agent →", key=f"to-agent-{cid}", width="stretch",
                   on_click=switch, args=(cid, AGENT))
        st.caption(f"Everyone in {chat_title(c)} sees these messages.")
        messages(cid)
    nudge = st.session_state.get(f"nudge-{cid}")
    if nudge:
        hint, go, no = st.columns([3.2, 1.4, 0.8], vertical_alignment="center")
        hint.info("That sounds like a meeting. Want your agent to set it up? It works it out with everyone's agents, "
                  "privately.")
        go.button("🤖 Ask my agent", type="primary", key=f"nudge-go-{cid}", width="stretch", on_click=ask_agent,
                  args=(cid, nudge))
        no.button("No", key=f"nudge-no-{cid}", width="stretch", on_click=lambda: st.session_state.pop(f"nudge-{cid}", None))
    text = st.chat_input(f"💬 Message everyone in {chat_title(c)}", key=f"input-{cid}")
    if text:
        store.send(cid, me, text)
        if MEETING_WORDS.search(text):
            st.session_state[f"nudge-{cid}"] = text
        st.rerun()


def switch(cid: str, mode: str) -> None:
    st.session_state[f"mode-{cid}"] = mode


def ask_agent(cid: str, text: str) -> None:
    """The nudge: forward a group message to your agent, privately, and switch to it."""
    st.session_state.pop(f"nudge-{cid}", None)
    st.session_state[f"mode-{cid}"] = AGENT
    engine.handle_agent_message(me, text, cid)


def groups_tab() -> None:
    mine = store.chats(me)
    others = sorted({m for c in mine for m in store.members(c["id"]) if m != me}, key=store.name)
    left, right = st.columns([1.15, 2.4], gap="medium")
    with left:
        tags = st.pills("Tags", store.all_tags(me), selection_mode="multi", key="filter-tags", format_func=tag_label)
        people = st.multiselect("People", others, format_func=store.name, key="filter-people", placeholder="Anyone")
        shown = [c for c in mine if (not tags or set(tags) & set(c["tags"].split(",")))
                 and (not people or set(people) <= set(store.members(c["id"])))]
        group_list(shown)
        watch_badges()
        with st.popover("➕ New group", width="stretch"):
            who = st.multiselect("Members", others, format_func=store.name, key="new-who")
            title = st.text_input("Name", key="new-title")
            new_tags = st.pills("Tags", store.all_tags(me), selection_mode="multi", key="new-tags",
                                format_func=tag_label)
            extra = st.text_input("New tag", key="new-tag", placeholder="e.g. volunteering")
            if st.button("Create", key="new-go", disabled=not who):
                tags = (new_tags or []) + ([extra] if extra.strip() else [])
                st.session_state["group"] = store.new_chat(title or ", ".join(store.given(p) for p in who),
                                                           "group" if len(who) > 1 or title else "dm", [me] + who)
                store.set_tags(st.session_state["group"], tags or ["others"])
                st.rerun()
    with right:
        if cid := st.session_state.get("group"):
            group_view(cid)


# ------------------------------------------------------------------ calendar
OPTIONS = {"firstDay": 1, "slotMinTime": "07:00:00", "slotMaxTime": "24:00:00", "scrollTime": "08:00:00",
           "allDaySlot": False, "nowIndicator": True, "timeZone": "UTC", "height": 700, "slotDuration": "00:30:00",
           "expandRows": True, "headerToolbar": False, "dayMaxEvents": 3,
           "dayHeaderFormat": {"weekday": "short", "day": "numeric"},
           "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
           "slotLabelFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False}}
BUSY = "#94a3b8"


def moment(d: date, t: time) -> str:
    return f"{d.isoformat()}T{t.strftime('%H:%M')}"


def calendar_names() -> tuple[list[str], dict[str, str]]:
    cals = store.calendars(me)
    return [c["id"] for c in cals], {c["id"]: c["name"] for c in cals}


def who_is_coming(proposal: dict) -> tuple[list[str], str | None]:
    """Just you, or a group you're in (groups with anyone you mentioned first), with the people
    editable. Returns the people to invite and the group to send it in."""
    st.markdown("**Who's coming?**")
    mentioned = [m["id"] for m in proposal.get("mentions", [])]
    if mentioned:
        st.caption(f"You mentioned {', '.join(store.given(p) for p in mentioned)}: here are the groups you share with "
                   f"{'them' if len(mentioned) > 1 else store.given(mentioned[0])}, or pick people yourself.")
    groups = sorted((c for c in store.chats(me) if not c["request_id"]),
                    key=lambda c: -len(set(mentioned) & set(store.members(c["id"]))))
    shared = [c["id"] for c in groups if set(mentioned) & set(store.members(c["id"]))]
    choices = [None, "pick"] + [c["id"] for c in groups]

    def describe(choice: str | None) -> str:
        if choice is None:
            return "🙋 Just me: add it to my calendar"
        if choice == "pick":
            return "🧑‍🤝‍🧑 People I pick"
        c = store.chat(choice)
        people = ", ".join(store.given(m) for m in store.members(choice) if m != me)
        return (f"💬 {chat_title(c)}" if c["kind"] == "dm" else f"👥 {c['title']} · {people}") + \
            ("  ⭐" if choice in shared else "")
    where = st.selectbox("Send it to", choices, index=choices.index(shared[0]) if shared else 0, key="an-where",
                         format_func=describe)
    if where is None:
        return [], None
    others = sorted({m for c in store.chats(me) for m in store.members(c["id"]) if m != me}, key=store.name)
    default = mentioned if where == "pick" else [m for m in store.members(where) if m != me]
    people = st.multiselect("People", others, default=default, key=f"an-people-{where}", format_func=store.name,
                            help="Add or remove anyone you know. If they aren't all in this group, it goes to a chat "
                                 "with exactly them.")
    return people, None if where == "pick" else where


def agent_questions(proposal: dict) -> None:
    """The agent's questions about a new item, with the answer buttons at the bottom. When the
    item mentions people you know, it asks who you mean and whether to send it to them now."""
    st.markdown(f"#### 🤖 Your agent checked \"{html.escape(proposal['title'])}\"")
    options = proposal["options"]
    choice = None
    if proposal["clashes"]:
        st.warning(f"{nice_slot(*options[0])} clashes with: {', '.join(proposal['clashes'])}.")
        choice = st.radio("Keep this time, or take a nearby free one?", list(range(len(options))), key="an-choice",
                          format_func=lambda i: nice_slot(*options[i]) + (" (clashes)" if i == 0 else " (free)"))
    elif not options:
        st.warning("I couldn't find free time on your calendar in that window.")
    elif len(options) == 1:
        st.success(f"{nice_slot(*options[0])} is free on your calendar.")
        choice = 0
    else:
        choice = st.radio("Which of these free times do you prefer?", list(range(len(options))), key="an-choice",
                          format_func=lambda i: nice_slot(*options[i]))
    people, where = who_is_coming(proposal)
    send, flexible = bool(people), False
    if people:
        names = ", ".join(store.given(p) for p in people)
        st.info(f"🔒 I can't see {names}'s calendar{'s' if len(people) > 1 else ''}: only their own agents can. "
                "When you send it, I ask their agents when they're free (never why), and you approve the time in the group.")
        w = proposal["window"]
        span = (f"on {nice_day(w['start_date'])}" if w["start_date"] == w["end_date"]
                else f"{nice_day(w['start_date'])} to {nice_day(w['end_date'])}") + f", {w['day_start']}-{w['day_end']}"
        anytime = f"Any time {span} that suits everyone"
        flexible = choice is None or st.radio(
            "How flexible is the time?", [f"Only {nice_slot(*options[choice])}", anytime], key="an-flex") == anytime
    flex, cal = proposal["flex"], None
    if not send:
        flex = flex_picker("an-flex-level", proposal["flex"], suggested=True)
        ids, names_of = calendar_names()
        guess = next((c["id"] for c in store.calendars(me) if c["kind"] == proposal["kind"]), ids[0])
        cal = st.selectbox("Which calendar does it belong on?", ids, index=ids.index(guess), key="an-cal",
                           format_func=names_of.get)
    go, stop = st.columns(2)
    if send:
        if go.button(f"Send to {', '.join(store.given(p) for p in people)}", type="primary", width="stretch",
                     key="an-send-go"):
            meeting = analyse.send(me, proposal, choice, people, flexible, where)
            st.session_state.pop("analysis", None)
            chat = store.chat(store.request(meeting)["chat_id"])
            st.session_state["flash"] = (f"Sent to {', '.join(store.given(p) for p in people)}. Their agents are being "
                                         f"asked now; the approval will appear in \"{chat_title(chat)}\" in Groups.")
            st.session_state["group"] = store.request(meeting)["chat_id"]
            st.rerun()
    elif go.button("Add it", type="primary", width="stretch", key="an-add", disabled=choice is None):
        eid = analyse.commit(me, proposal, choice, flex, cal)
        st.session_state.pop("analysis", None)
        st.session_state["cal-week"] = store.event(eid)["start_at"][:10]
        st.rerun()
    if stop.button("Don't add it", width="stretch", key="an-cancel"):
        analyse.commit(me, proposal, None, flex, cal or "")
        st.session_state.pop("analysis", None)
        st.rerun()


def run_analysis(text: str, when: tuple[str, str] | None) -> None:
    try:
        st.session_state["analysis"] = analyse.start(me, text, when)
    except RuntimeError as err:
        st.error(str(err))
        return
    st.rerun(scope="fragment")


@st.dialog("Calendar item", width="large")
def flex_picker(key: str, value: int, suggested: bool = False) -> int:
    """How easily an item could move, as a scale: what each level lets the agents do is spelled out."""
    level = st.select_slider("How easily could it move if someone needs the time?", options=list(range(len(store.FLEX))),
                             value=value, format_func=lambda i: store.FLEX[i], key=key)
    st.caption(("✨ Your agent suggested this from the title; you decide. " if suggested and level == value else "")
               + store.FLEX_HELP[level])
    return level


def item_dialog(eid: str | None = None, start: str | None = None, end: str | None = None, describe: bool = False) -> None:
    """One dialog for everything on the calendar: view, edit or delete an item; add one at the
    time you clicked; or describe one and let your agent pick the time."""
    if st.session_state.get("analysis"):
        agent_questions(st.session_state["analysis"])
        return
    e = store.event(eid) if eid else None
    if e and not st.session_state.get(f"edit-{eid}"):
        st.markdown(f"### {'✨ ' if e['request_id'] else ''}{html.escape(e['title'])}")
        st.markdown(f"{nice_slot(e['start_at'], e['end_at'])} · {e['calendar']} calendar"
                    + f" · {store.FLEX[e['flex']].lower()}")
        if e["request_id"]:
            r = store.request(e["request_id"])
            st.caption("Added by " + ("your agent, after checking your calendar" if r and r["kind"] == "analyse"
                                      else f"the agents, for a request by {store.given(r['organiser'])}" if r else "an agent"))
        view, edit, delete = st.columns(3)
        if e["request_id"] and view.button("🔍 View trace", type="primary", width="stretch", key="ev-trace"):
            open_trace(e["request_id"])
        if edit.button("✏️ Edit", width="stretch", key="ev-edit"):
            st.session_state[f"edit-{eid}"] = True
            st.rerun(scope="fragment")
        if delete.button("🗑️ Delete", width="stretch", key="ev-delete"):
            store.delete_event(eid)
            st.rerun()
        return
    if describe:
        st.caption("Describe it, and your agent finds free times on your calendars and asks you a few questions "
                   "before adding it. Nothing leaves your own agent.")
        text = st.text_area("What do you want to add?", key="an-text", placeholder="Gym, 1 hour, Wednesday evening, flexible")
        if st.button("✨ Add and analyse", type="primary", width="stretch", key="an-go", disabled=not text):
            run_analysis(text, None)
        return
    ids, names = calendar_names()
    start = e["start_at"] if e else start or f"{engine.TODAY}T09:00"
    end = e["end_at"] if e else end or (datetime.fromisoformat(start) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    title = st.text_input("Title", e["title"] if e else "", key="ev-title", placeholder="e.g. Dentist")
    day = st.date_input("Date", date.fromisoformat(start[:10]), key="ev-day")
    a, b = st.columns(2)
    t1 = a.time_input("Start", time.fromisoformat(start[11:16]), step=timedelta(minutes=15), key="ev-start")
    t2 = b.time_input("End", time.fromisoformat(end[11:16]), step=timedelta(minutes=15), key="ev-end")
    default = e["calendar_id"] if e else next((c["id"] for c in store.calendars(me) if c["kind"] == "personal"), ids[0])
    cal = st.selectbox("Calendar", ids, index=ids.index(default), key="ev-cal", format_func=names.get)
    if e:
        flex = flex_picker("ev-flex", e["flex"])
    else:
        with st.spinner("Your agent is judging how flexible it is…"):
            guess = analyse.guess_flex(title.strip(), me, store.setting("llm_mode", "mock"))
        flex = flex_picker(f"ev-flex-{guess}", guess, suggested=bool(title.strip()))
    ok = bool(title.strip()) and t2 > t1
    if e:
        if st.button("Save", type="primary", width="stretch", key="ev-save", disabled=not ok):
            store.update_event(e["id"], title=title.strip(), start=moment(day, t1), end=moment(day, t2),
                               flex=flex, calendar_id=cal)
            st.session_state.pop(f"edit-{eid}", None)
            st.rerun()
        return
    st.caption("**Add** puts it on your calendar as it is. **Add and analyse** lets your agent check the time first "
               "and ask you a few questions.")
    add, analyse_it = st.columns(2)
    if add.button("Add", width="stretch", key="ev-add", disabled=not ok):
        store.add_event(cal, title.strip(), moment(day, t1), moment(day, t2), flex)
        st.session_state["cal-week"] = day.isoformat()
        st.rerun()
    if analyse_it.button("✨ Add and analyse", type="primary", width="stretch", key="ev-analyse", disabled=not ok):
        run_analysis(title.strip(), (moment(day, t1), moment(day, t2)))


DOTS = {"🔴": "#ef4444", "🟠": "#f59e0b", "🟡": "#eab308", "🟢": "#22c55e", "🔵": "#3b82f6", "🟣": "#a855f7",
        "🟤": "#92400e", "⚫": "#1f2937", "⚪": "#cbd5e1"}


def dot(color: str) -> str:
    """The coloured circle closest to a calendar's colour, for the filter chips."""
    rgb = [int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return min(DOTS, key=lambda d: sum((a - int(DOTS[d][1 + 2 * i:3 + 2 * i], 16)) ** 2 for i, a in enumerate(rgb)))


def calendar_filter() -> dict[str, bool]:
    """A row of chips, one per calendar, all on: click one to hide or show it."""
    cals = store.calendars(me)
    ids = [c["id"] for c in cals]
    names = {c["id"]: f"{dot(c['color'])} {c['name']}" for c in cals}
    picked = st.pills("Calendars", ids, selection_mode="multi", default=ids, format_func=names.get,
                      key=f"cal-filter-{me}-{len(ids)}", label_visibility="collapsed")
    return {i: i in (picked or []) for i in ids}


def manage_calendars() -> None:
    """Rename, recolour or delete a calendar, or add one: one small form."""
    with st.popover("⚙️", help="Manage calendars"):
        cals = store.calendars(me)
        ids = [c["id"] for c in cals]
        cid = st.selectbox("Calendar", ids + ["new"], key="manage-cal",
                           format_func=lambda i: "➕ Add a calendar" if i == "new" else
                           next(f"{dot(c['color'])} {c['name']}" for c in cals if c["id"] == i))
        if cid == "new":
            kinds = [k for k in store.KINDS if k != "meetings"]
            kind = st.selectbox("Type", kinds, format_func=lambda k: store.KINDS[k][0], key="newcal-kind")
            name = st.text_input("Name", store.KINDS[kind][0], key=f"newcal-name-{kind}")
            color = st.color_picker("Colour", store.KINDS[kind][1], key=f"newcal-color-{kind}")
            if st.button("Add calendar", type="primary", key="newcal-go"):
                store.add_calendar(me, name, kind, color)
                st.rerun()
            return
        c = next(c for c in cals if c["id"] == cid)
        name = st.text_input("Name", c["name"], key=f"cal-name-{cid}")
        color = st.color_picker("Colour", c["color"], key=f"cal-color-{cid}")
        save, delete = st.columns(2)
        if save.button("Save", type="primary", key=f"cal-save-{cid}", width="stretch"):
            store.update_calendar(cid, name, color)
            st.rerun()
        if c["kind"] != "meetings" and delete.button("Delete", key=f"cal-del-{cid}", width="stretch",
                                                     help="Deletes the calendar and everything on it"):
            store.delete_calendar(cid)
            st.rerun()


def shift(days: int) -> None:
    d = date.fromisoformat(st.session_state["cal-week"]) + timedelta(days=days)
    st.session_state["cal-week"] = d.isoformat()


def calendar_page() -> None:
    if flash := st.session_state.pop("flash", None):
        st.success(flash)
    week = st.session_state.setdefault("cal-week", "2026-10-26")
    month = st.session_state.get("cal-view") == "Month"
    monday = date.fromisoformat(week) - timedelta(days=date.fromisoformat(week).weekday())
    nav, actions_ = st.columns([1.2, 1], vertical_alignment="center")
    with nav:
        back, today, fwd, title = st.columns([1, 1.6, 1, 6], vertical_alignment="center")
        back.button("◀", key="cal-back", on_click=shift, args=(-28 if month else -7,))
        today.button("Today", key="cal-today", on_click=lambda: st.session_state.update({"cal-week": engine.TODAY}))
        fwd.button("▶", key="cal-fwd", on_click=shift, args=(28 if month else 7,))
        title.markdown(f"#### {monday.strftime('%B %Y')}" if month else
                       f"#### {monday.strftime('%d %b')} – {(monday + timedelta(days=6)).strftime('%d %b %Y')}")
    with actions_:
        view, gear, ai = st.columns([1.2, 0.45, 1.6], vertical_alignment="center")
        view.segmented_control("View", ["Week", "Month"], default="Week", key="cal-view", label_visibility="collapsed")
        with gear:
            manage_calendars()
        if ai.button("✨ Add and analyse", type="primary", width="stretch", key="add-ai"):
            item_dialog(describe=True)
    shown = calendar_filter()
    options = OPTIONS | {"initialView": "dayGridMonth" if month else "timeGridWeek", "initialDate": week,
                         "now": f"{engine.TODAY}T09:00:00"}
    nonce = st.session_state.setdefault("cal-nonce", 0)
    private, public = st.columns([1.35, 1], gap="medium")
    with private:
        st.markdown("##### 🔒 My calendar")
        st.caption("Only you and your agent see this. Click or drag on empty space to add an item; click an item to "
                   "open it (✨ items show their trace); drag an item to move it.")
        events = [{"id": e["id"], "title": ("✨ " if e["request_id"] else "") + e["title"] + ("", " ↔", " ≈", " ~")[e["flex"]],
                   "start": e["start_at"], "end": e["end_at"], "backgroundColor": e["color"], "borderColor": e["color"]}
                  for e in store.events(me) if shown.get(e["calendar_id"], True)]
        state = calendar(events=events, options=options | {"editable": True, "selectable": True},
                         callbacks=["eventClick", "eventChange", "select", "dateClick"],
                         key=f"cal-private-{me}-{week}-{month}-{nonce}")
    with public:
        st.markdown("##### 👥 What others see")
        st.caption("Free or busy, never why. Read-only: it changes when your own calendar does.")
        busy = [{"title": "Busy", "start": s, "end": e, "backgroundColor": BUSY, "borderColor": BUSY}
                for s, e in store.busy_blocks(me)]
        calendar(events=busy, options=options | {"editable": False, "selectable": False}, callbacks=[],
                 key=f"cal-public-{me}-{week}-{month}-{nonce}")
    if not (state and state.get("callback")):
        return
    st.session_state["cal-nonce"] = nonce + 1                  # a fresh widget, so the same click works twice
    cb = state["callback"]
    if cb == "eventClick":
        e = state["eventClick"]["event"]
        st.session_state["cal-week"] = e["start"][:10]
        item_dialog(eid=e["id"])
    elif cb == "eventChange":
        e = state["eventChange"]["event"]
        store.update_event(e["id"], start=e["start"][:16], end=(e.get("end") or e["start"])[:16])
        st.session_state["cal-week"] = e["start"][:10]
        st.rerun()
    elif cb in ("select", "dateClick"):
        s = state["select"]["start"][:16] if cb == "select" else state["dateClick"]["date"][:16]
        e = state["select"]["end"][:16] if cb == "select" else None
        if s.endswith("T00:00"):                                # a day in month view: start at 9am
            s, e = s[:10] + "T09:00", s[:10] + "T10:00"
        st.session_state["cal-week"] = s[:10]
        item_dialog(start=s, end=e)


# ------------------------------------------------------------------ the trace replay
def preference(ref: str) -> str:
    """A memory note's words ("mem-bob-0"), shown only in that person's own lane."""
    _, pid, i = ref.split("-", 2)
    notes = PREFERENCES.get(pid, [])
    return f"preference “{notes[int(i)][0]}”" if i.isdigit() and int(i) < len(notes) else ref


def step_line(s: dict) -> str:
    """One step, written from where it happened."""
    kind, actor, text = s["kind"], s["actor"], pretty(s["text"])
    if kind == "call":
        tool, _, args = s["text"].partition(" ")
        return f"🔧 {label(actor)} called {tool}" + (f" ({pretty(args)[:70]})" if args and "participant_id" not in args else "")
    if kind == "rules":
        refs = re.findall(r"\b(?:e|ev|msg|mem)-[\w-]+", s["text"])
        titles = [preference(r) if r.startswith("mem-") else (store.event(r) or {}).get("title") or r for r in refs]
        return f"🔒 {label(actor)} recorded privately: " + (", ".join(dict.fromkeys(titles)) or "nothing")
    if kind == "summary":
        return f"📤 {label(actor)} → Coordinator: {text}"
    if kind == "ask" and actor.startswith("personal:"):     # Add and analyse: your agent asks you
        return f"❓ {label(actor)} asked {store.given(actor.split(':', 1)[1])}: {text.removeprefix('Asked you: ')}"
    if kind == "ask":
        to, _, question = text.partition(": ")
        return f"❓ Coordinator → {to.removeprefix('to ')}'s agent: {question}"
    if kind == "answer":
        return f"📤 {label(actor)} → Coordinator: {text}" if actor.startswith("personal:") else \
            f"🗣️ {label(actor)} told their agent, privately: {text}"
    icons = {"initiated": "💬", "read": "🤖", "ranking": "📊", "thread": "📢", "request": "📢", "approval": "📨",
             "preference": "⭐", "gate": "✅", "outcome": "🏁", "guardrail": "🛡️", "check": "🔎", "error": "⚠️",
             "blocked": "⛔", "ack": "📨", "suggest": "💡", "cancelled": "✖"}
    if kind == "ranking":
        text = text.split("\n")[0] + " " + (text.split("\n")[1] if "\n" in text else "")
    if kind in ("thread", "request"):
        return f"📢 {label(actor)} → the group: {text}"
    return f"{icons.get(kind, '•')} {label(actor)}: {text}"


def in_lane(s: dict, owner: str, organiser: str) -> bool:
    if owner == "coordinator":
        return (s["actor"] in ("coordinator", "gate", "organiser", "privacy filter") or s["actor"].startswith("guardrail:")
                or bool({"coordinator", "thread"} & set(s["visible_to"])))
    return (s["actor"] in (owner, f"personal:{owner}", f"host:{owner}") or owner in s["visible_to"]
            or (owner == organiser and "organiser" in s["visible_to"]))


def lane(title: str, caption: str, steps: list[dict], now: int, height: int) -> None:
    with st.container(border=True, height=height):
        st.markdown(f"**{title}**")
        st.caption(caption)
        if not steps:
            st.caption("Nothing yet at this step.")
        for s in steps[-12:]:
            css = "now" if s["seq"] == now else "quiet" if s["kind"] == "guardrail" else ""
            st.markdown(f'<div class="step {css}"><span class="seq">{s["seq"]}</span>{html.escape(step_line(s))}</div>',
                        unsafe_allow_html=True)


def agent_lanes(shown: list[dict], current: dict, organiser: str, attendees: list[str], kind: str) -> None:
    """The host's agent, the coordinator agent and yours on top; everyone else's agents below."""
    you = me if me in attendees else organiser
    top = [organiser] + (["coordinator"] if kind == "meeting" else []) + ([you] if you != organiser else [])
    for col, owner in zip(st.columns(len(top)), top):
        with col:
            if owner == "coordinator":
                lane("🧭 Coordinator agent", "Sees availability summaries only, never calendars",
                     [s for s in shown if in_lane(s, owner, organiser)], current["seq"], 430)
            else:
                role = ("Host" if owner == organiser else "") + (" · you" if owner == me else "")
                lane(f"🤖 {store.given(owner)}'s agent ({role.strip(' ·')})", "Private to " + store.given(owner),
                     [s for s in shown if in_lane(s, owner, organiser)], current["seq"], 430)
    others = [a for a in attendees if a not in top]
    if others:
        st.markdown("##### Other participants' agents")
        for col, owner in zip(st.columns(len(others)), others):
            with col:
                lane(f"🤖 {store.given(owner)}'s agent", "Private to " + store.given(owner),
                     [s for s in shown if in_lane(s, owner, organiser)], current["seq"], 260)


# What a step that is not a plain tool call stands for, on the timeline: (tool or action, type).
ACTIONS = {"ranking": ("find_slots", "tool call"), "rules": ("submit_constraints", "tool call"),
           "ask": ("ask_privately", "tool call"), "thread": ("post_to_thread", "tool call"),
           "gate": ("approval gate: commit", "tool call"), "summary": ("availability summary", "message"),
           "ack": ("acknowledge", "message"), "request": ("request to the group", "message"),
           "initiated": ("asks own agent", "person"), "approval": ("approves", "person"),
           "preference": ("picks a time", "person"), "cancelled": ("cancels", "person"),
           "guardrail": ("check", "guardrail")}
TYPES = {"tool call": "#3b82f6", "message": "#a855f7", "person": "#22c55e", "guardrail": "#94a3b8", "step": "#ec4899"}


def row_of(actor: str, organiser: str) -> str:
    """The timeline row a step goes on: a person, their agent, the coordinator, the gate or the checks."""
    if actor.startswith(("personal:", "host:")):
        return f"{store.given(actor.split(':', 1)[1])}'s agent"
    if actor == "organiser":
        return store.given(organiser)
    if actor in PEOPLE:
        return store.given(actor)
    if actor.startswith("guardrail:") or actor == "privacy filter":
        return "Guardrails"
    return {"coordinator": "Coordinator agent", "gate": "Approval gate"}.get(actor, "System")


def action_of(s: dict) -> tuple[str, str]:
    if s["kind"] == "call":
        return s["text"].split(" ", 1)[0], "tool call"
    if s["kind"] == "answer":
        return ("answers the coordinator", "message") if s["actor"].startswith("personal:") else ("answers own agent", "person")
    return ACTIONS.get(s["kind"], (s["kind"], "step"))


def arrow_of(s: dict, organiser: str) -> tuple[str, str] | None:
    """Who a step went from and to, when it went between two rows."""
    actor, kind = s["actor"], s["kind"]
    if kind == "ask" and actor == "coordinator":
        return "Coordinator agent", f"{store.given(s['text'].removeprefix('to ').split(':')[0])}'s agent"
    if kind in ("summary", "answer") and actor.startswith("personal:"):
        return row_of(actor, organiser), "Coordinator agent"
    if kind == "answer" and actor in PEOPLE:
        return store.given(actor), f"{store.given(actor)}'s agent"
    if kind == "initiated":
        return store.given(organiser), f"{store.given(organiser)}'s agent"
    if kind == "ack":
        return "Coordinator agent", f"{store.given(organiser)}'s agent"
    if kind == "approval":
        return store.given(organiser), "Coordinator agent"
    return None


def timeline(rid: str, steps: list[dict], current: dict, organiser: str, attendees: list[str], key: str) -> None:
    """Every step on one time axis, a row per person, agent and check: who called which tool, and
    which messages went between whom. Click a point to replay to it."""
    import altair as alt
    import pandas as pd

    clock = st.segmented_control("Space the steps by", ["Order", "Clock time"], default="Order", key="trace-axis")
    rows, arrows = [], []
    for s in steps:
        action, kind = action_of(s)
        at = datetime.fromtimestamp(s["ts"])
        rows.append({"step": s["seq"], "at": at, "time": at.strftime("%H:%M:%S"), "row": row_of(s["actor"], organiser),
                     "action": action, "type": kind, "what": step_line(s)[:160], "now": s["seq"] == current["seq"]})
        if link := arrow_of(s, organiser):
            arrows.append({"step": s["seq"], "at": at, "from": link[0], "to": link[1]})
    order = [store.given(organiser), f"{store.given(organiser)}'s agent", "Coordinator agent"]
    for pid in attendees[1:]:
        order += [f"{store.given(pid)}'s agent", store.given(pid)]
    order += ["Approval gate", "Guardrails", "System"]
    used = {r["row"] for r in rows} | {a["from"] for a in arrows} | {a["to"] for a in arrows}
    order = [o for o in order if o in used] + sorted(used - set(order))
    x = (alt.X("at:T", title="Clock time", axis=alt.Axis(format="%H:%M:%S")) if clock == "Clock time"
         else alt.X("step:Q", title="Step", scale=alt.Scale(nice=False)))
    y = alt.Y("row:N", sort=order, title=None, scale=alt.Scale(domain=order))
    pick = alt.selection_point(name="pick", fields=["step"], on="click")
    points = alt.Chart(pd.DataFrame(rows)).mark_point(filled=True, opacity=.9).encode(
        x=x, y=y, color=alt.Color("type:N", title=None, scale=alt.Scale(domain=list(TYPES), range=list(TYPES.values())),
                                  legend=alt.Legend(orient="top")),
        size=alt.condition("datum.now", alt.value(260), alt.value(70)),
        tooltip=[alt.Tooltip("step:Q", title="Step"), alt.Tooltip("time:N", title="At"), alt.Tooltip("row:N", title="Who"),
                 alt.Tooltip("action:N", title="Tool or action"), alt.Tooltip("what:N", title="What")]).add_params(pick)
    layers = [alt.Chart(pd.DataFrame([{"step": current["seq"], "at": datetime.fromtimestamp(current["ts"])}]))
              .mark_rule(color="#f59e0b", strokeWidth=2).encode(x=x)]
    if arrows:
        layers.append(alt.Chart(pd.DataFrame(arrows)).mark_rule(strokeDash=[4, 3], opacity=.45).encode(
            x=x, y=alt.Y("from:N", sort=order, scale=alt.Scale(domain=order)), y2="to:N"))
    chart = alt.layer(*layers, points).properties(height=34 * len(order) + 60)
    chart_key = f"timeline-{rid}"

    def jump() -> None:
        picked = st.session_state[chart_key].selection.get("pick") or []
        if picked and "step" in picked[0]:
            st.session_state[key] = next((i + 1 for i, s in enumerate(steps) if s["seq"] == picked[0]["step"]),
                                         st.session_state[key])
    st.altair_chart(chart, width="stretch", key=chart_key, on_select=jump, selection_mode="pick")
    st.caption("Hover a point for the step; click one to replay to it. Dashed lines are messages between two rows. "
               "Blue points are tool calls.")
    calls: dict[str, dict[str, int]] = {}
    for r in rows:
        if r["type"] == "tool call" and r["step"] <= current["seq"]:
            calls.setdefault(r["row"], {}).setdefault(r["action"], 0)
            calls[r["row"]][r["action"]] += 1
    st.markdown(f"**Tool calls up to step {current['seq']}**")
    st.dataframe([{"who": who, "tools called": ", ".join(f"{t} ×{n}" if n > 1 else t for t, n in tools.items())}
                  for who, tools in sorted(calls.items(), key=lambda c: order.index(c[0]) if c[0] in order else 99)],
                 hide_index=True, width="stretch")


def trace_page(rid: str) -> None:
    r = store.request(rid)
    if st.button("← Back", key="trace-back"):
        st.session_state.pop("trace", None)
        st.rerun()
    if r is None:
        st.error("That request no longer exists.")
        return
    parsed = r["parsed"] or {}
    st.title(f"🔍 {parsed.get('topic') or r['text'][:60]}")
    st.caption(f"{'Meeting request' if r['kind'] == 'meeting' else 'Add and analyse'} by {store.name(r['organiser'])} · "
               f"{r['status']} · {'mocked LLM' if r['mode'] == 'mock' else settings.model}"
               + (f" · {parsed['summary']}" if parsed.get("summary") else ""))
    st.caption("Demo view: every agent's steps, including other people's private ones. "
               "Drag the replay bar to follow the request from the moment it was initiated.")
    all_steps = store.trace(rid)
    guards = st.toggle("Show guardrail checks", key="trace-guards")
    steps = [s for s in all_steps if guards or s["kind"] != "guardrail"]
    if not steps:
        st.info("No steps yet.")
        return
    key = f"replay-{rid}-{guards}"
    st.session_state.setdefault(key, len(steps))
    st.session_state[key] = min(st.session_state[key], len(steps))

    def move(delta: int) -> None:
        st.session_state[key] = max(1, min(len(steps), st.session_state[key] + delta))
    back, bar, fwd = st.columns([0.6, 10, 0.6], vertical_alignment="bottom")
    back.button("◀", key="replay-back", on_click=move, args=(-1,))
    fwd.button("▶", key="replay-fwd", on_click=move, args=(1,))
    k = bar.slider("Replay", 1, len(steps), key=key) if len(steps) > 1 else 1
    current = steps[k - 1]
    shown = [s for s in steps if s["seq"] <= current["seq"]]
    seen_by = [label(v) for v in current["visible_to"] if v not in ("system",)]
    st.info(f"**Step {current['seq']} of {all_steps[-1]['seq']}** · {step_line(current)}  \n"
            f"Seen by: {', '.join(seen_by) or 'the system only'}")
    organiser = r["organiser"]
    attendees = parsed.get("attendee_ids") or [organiser]
    by_agent, by_time = st.tabs(["🤖 By agent", "🕒 Timeline: who called what, when"], key="trace-tab", on_change="rerun")
    with by_agent:
        agent_lanes(shown, current, organiser, attendees, r["kind"])
    with by_time:
        timeline(rid, steps, current, organiser, attendees, key)
    private = {e["title"] for pid in attendees for e in store.events(pid) if e["request_id"] != rid and len(e["title"]) > 3}
    shared = " ".join(s["text"] for s in all_steps if {"coordinator", "thread"} & set(s["visible_to"])
                      and s["kind"] not in ("initiated",))
    leaked = sorted(t for t in private if t.lower() in shared.lower()) if r["kind"] == "meeting" else []
    if r["kind"] == "meeting":
        st.markdown("**Private details seen by the coordinator or the group:** " + (", ".join(leaked) if leaked else "none ✅"))
    with st.expander("Full log"):
        st.dataframe([{"step": s["seq"], "actor": label(s["actor"]), "kind": s["kind"],
                       "seen by": ", ".join(label(v) for v in s["visible_to"]), "text": s["text"]} for s in all_steps],
                     hide_index=True, width="stretch")


# ------------------------------------------------------------------ the page
if st.session_state.get("trace"):
    trace_page(st.session_state["trace"])
    st.stop()
def open_agent(cid: str) -> None:
    """A notification's Open: that group's private agent chat, on the Groups page."""
    st.session_state.update({"group": cid, f"mode-{cid}": AGENT, "page": "👥 Groups"})


def mark_all_read(chat_ids: set[str]) -> None:
    for cid in chat_ids:
        store.mark_seen(me, cid)


with bell:
    news = [m for m in store.unread(me) if m["chat_id"]]
    with st.popover(f"🔔 Notifications ({len(news)})" if news else "🔔 Notifications", width="stretch"):
        if not news:
            st.caption("You're all caught up.")
        for m in news[:8]:
            c = store.chat(m["chat_id"])
            text = m["text"] if len(m["text"]) < 200 else m["text"][:200] + "…"
            st.markdown(f"**{html.escape(chat_title(c)) if c else 'Your agent'}** · {stamp(m['ts'])}  \n{pretty(text)}")
            st.button("Open", key=f"note-{m['id']}", on_click=open_agent, args=(m["chat_id"],))
        if news:
            st.button("Mark all as read", key="notes-read", on_click=mark_all_read, args=({m["chat_id"] for m in news},))
page = st.segmented_control("Page", ["👥 Groups", "📅 Calendar"], default="👥 Groups", key="page",
                            label_visibility="collapsed")
if page == "📅 Calendar":
    calendar_page()
else:
    groups_tab()
