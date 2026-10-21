"""A demo of one scheduling episode, seen through each person's eyes.

    uv run --group demo python -m streamlit run scheduler/demo/app.py

Sign in as one of the demo people (data/demo/users.json) to see only what they would see: the
request thread, their private questions, their own calendars next to what their personal agent
shared, and their tasks. Sign in as demo_admin to see everyone, the dev scenarios and the full
trace. The demo people and their requests come from `python -m scheduler.demo.seed`.

Replay steps through a saved result file: no cost, no waiting. Live runs one episode now: the
run pauses before the invite until the organiser (or the admin) approves or rejects it. Only dev
and demo scenarios are offered, so nobody sees an agent's output on the held-out set before the
sweep. Nothing here produces a reported number; those come only from
`python -m scheduler.eval --report`."""
import hmac
import html
import json
import re
from datetime import date, timedelta

import streamlit as st

from scheduler import llm
from scheduler.agents.shared import shared_coordinator
from scheduler.config import load_settings
from scheduler.contracts.result import EpisodeResult, Outcome, save_result
from scheduler.contracts.scenario import load_scenario, load_split
from scheduler.eval.arms import team_coordinator
from scheduler.eval.episode import begin, collect
from scheduler.sandbox import world
from scheduler.timegrid import at, horizon_days, overlaps, parse

ARMS = {"d": ("Personal agents + coordinator agent (our design)", team_coordinator),
        "c": ("One agent that sees everyone's data (the ablation)", shared_coordinator)}
LIVE_TAG = "demo-live"
CHATTY = ("request", "thread", "outcome")          # what the request thread shows

settings = load_settings()
DEMO = settings.data_dir / "demo"
USERS = {u["username"]: u for u in json.loads((DEMO / "users.json").read_text())["users"]}
SETS = {"Demo": [load_scenario(p) for p in sorted((DEMO / "scenarios").glob("*.json"))],
        "Dev": load_split(settings.data_dir, "dev")}

st.set_page_config(page_title="Scheduler demo", layout="wide")
st.markdown("""<style>
.grid {border-collapse: collapse; font-size: 0.78rem; width: 100%; table-layout: fixed}
.grid th, .grid td {border: 1px solid rgba(128,128,128,.25); padding: 2px 4px; text-align: center;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; height: 1.6rem}
.grid th {font-weight: 600} .grid td.t {width: 3.5rem; font-variant-numeric: tabular-nums}
.ok {background: rgba(46,160,67,.35)} .soft {background: rgba(212,160,23,.40)}
.no {background: rgba(218,54,51,.30)} .ask {background: repeating-linear-gradient(45deg,
  rgba(230,126,34,.45) 0 6px, rgba(230,126,34,.15) 6px 12px)}
.busy {background: rgba(88,110,190,.35)} .away {background: rgba(128,128,128,.40)}
.pick {outline: 3px solid rgba(46,160,67,1); outline-offset: -3px; font-weight: 700}
.legend span {display: inline-block; padding: 0 .5rem; margin-right: .3rem; border-radius: .25rem}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ signing in
def sign_in() -> None:
    st.title("Scheduler demo")
    st.caption("Sign in as one of the demo people; their logins are in `data/demo/users.json`. "
               "Everyone here is fictional.")
    with st.form("login"):
        name = st.text_input("Username", key="username")
        word = st.text_input("Password", type="password", key="password")
        if st.form_submit_button("Sign in"):
            u = USERS.get(name.strip())
            if u and hmac.compare_digest(u["password"].encode(), word.encode()):
                st.session_state["user"] = u
                st.rerun()
            st.error("Unknown username or wrong password.")


user = st.session_state.get("user")
if user is None:
    sign_in()
    st.stop()
me, admin = user["participant_id"], user["role"] == "admin"

st.sidebar.markdown(f"Signed in as **{user['username']}**  \n{user['about']}")
if st.sidebar.button("Sign out", key="logout"):
    st.session_state.clear()
    st.rerun()
if admin:
    pool = SETS[st.sidebar.radio("Scenarios", list(SETS), key="set", horizontal=True)]
else:
    pool = [s for s in SETS["Demo"] if any(a.id == me for a in s.request.attendees)]
if not pool:
    st.info("No requests include you yet. Run `python -m scheduler.demo.seed` to create the demo requests.")
    st.stop()
scenarios = {s.id: s for s in pool}
mode = st.sidebar.radio("Mode", ["Replay", "Live"], key="mode")
sid = st.sidebar.selectbox("Request", list(scenarios), key="scenario",
                           format_func=lambda i: f"{i}: {scenarios[i].request.text[:48]}")
arm = st.sidebar.selectbox("Arm", list(ARMS), key="arm", format_func=lambda a: ARMS[a][0])
scenario = scenarios[sid]
names = {p.id: p.name for p in scenario.participants}
organiser = admin or me == scenario.request.organiser_id
st.sidebar.caption(f"Model: {'scripted fake (no cost)' if settings.fake_llm else settings.model}")


# ------------------------------------------------------------------ helpers
def first(pid: str) -> str:
    return names.get(pid, pid).split()[0]


def who(actor: str) -> str:
    if actor.startswith("personal:"):
        return f"{first(actor.removeprefix('personal:'))}'s personal agent"
    if actor.startswith("guardrail:"):
        return f"Guardrail: {actor.removeprefix('guardrail:')}"
    return names.get(actor) or {"coordinator": "Coordinator agent", "organiser": "Organiser", "gate": "Approval gate",
                                "privacy filter": "Privacy filter", "shared": "Shared agent"}.get(actor, actor)


def named(text: str) -> str:
    """Participant ids in a message, replaced by first names."""
    return re.sub(r"\b[a-z]\d{2}\b", lambda m: first(m[0]) if m[0] in names else m[0], text)


def can_see(e) -> bool:
    if admin:
        return True
    return bool(({"thread", me} | ({"organiser"} if organiser else set())) & set(e.visible_to))


def nice_day(d: str) -> str:
    return date.fromisoformat(d).strftime("%a %d %b")


def nice_slot(start: str | None, end: str | None = None) -> str:
    if not start:
        return ""
    return f"{nice_day(start[:10])} {start[11:]}" + (f" to {end[11:]}" if end else "")


def live_record() -> EpisodeResult:
    """What the sandbox has recorded so far, for a run still in progress."""
    return EpisodeResult(arm=arm, scenario_id=sid, run=0, run_tag=LIVE_TAG, model=settings.model,
                         reasoning_effort=settings.reasoning_effort, fake_llm=settings.fake_llm, code_version="",
                         outcome=Outcome(status="budget", message="in progress"), thread=list(world.THREAD),
                         blocked_messages=list(world.BLOCKED), questions=list(world.QUESTIONS),
                         summaries=list(world.SUMMARIES), calls=list(world.CALLS), writes=list(world.WRITES),
                         timeline=list(world.TIMELINE), guardrails=list(world.GUARDRAILS),
                         coordinator_context="\n".join(world.CONTEXT))


# ------------------------------------------------------------------ the calendar grids
def rows() -> tuple[list[str], list[str]]:
    r = scenario.request
    days = horizon_days(r.start_date, r.end_date, r.days)
    t, close, times = parse(at(r.start_date, r.day_start)), parse(at(r.start_date, r.day_end)), []
    while t < close:
        times.append(t.strftime("%H:%M"))
        t += timedelta(minutes=30)
    return days, times


def table(cells: dict[tuple[str, str], tuple[str, str]], pick: str | None = None) -> str:
    """cells: (day, HH:MM) -> (label, css class). `pick` outlines the agreed slot's start."""
    days, times = rows()
    head = "".join(f"<th>{nice_day(d)}</th>" for d in days)
    body = ""
    for t in times:
        tds = ""
        for d in days:
            label, css = cells.get((d, t), ("", ""))
            css += " pick" if pick == at(d, t) else ""
            tds += f'<td class="{css}" title="{html.escape(label)}">{html.escape(label)}</td>'
        body += f'<tr><td class="t">{t}</td>{tds}</tr>'
    return f'<table class="grid"><tr><th></th>{head}</tr>{body}</table>'


def private_cells(pid: str) -> dict:
    """What the person's own calendars and time away hold, per half hour: only their agent reads this."""
    p, (days, times) = scenario.participant(pid), rows()
    cells = {}
    for d in days:
        away = next((l for l in p.leave if l.start_date <= d <= l.end_date), None)
        for t in times:
            start, end = at(d, t), (parse(at(d, t)) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M")
            if away:
                cells[(d, t)] = (f"Away: {away.reason}", "away")
                continue
            hits = [(c.name, e) for c in p.calendars for e in c.events if overlaps(e.start, e.end, start, end)]
            if hits:
                cal, e = hits[0]
                cells[(d, t)] = (e.title + (" (movable)" if e.movable else ""), "ask" if e.movable else "busy")
            elif not p.hours_start <= t < p.hours_end:
                cells[(d, t)] = ("outside usual hours", "away")
    return cells


def summary_cells(summary) -> dict:
    """One availability summary, per slot start: when, never why."""
    out = {}
    for s in summary.slots:
        if s.status == "available":
            out[(s.start[:10], s.start[11:])] = ("free", "ok")
        elif s.status == "prefer_not":
            out[(s.start[:10], s.start[11:])] = (f"prefer not ({s.weight:g})", "soft")
        else:
            out[(s.start[:10], s.start[11:])] = ("could free" if s.relaxable else "busy", "ask" if s.relaxable else "no")
    return out


def group_cells(latest: dict) -> dict:
    """How many required attendees can make each slot start, from the summaries alone."""
    required = [a.id for a in scenario.request.attendees if a.role == "required"]
    out = {}
    for start, _ in scenario.request.slots():
        got = [latest[pid].status_of(start) for pid in required if pid in latest]
        if len(got) < len(required) or None in got:
            continue
        free = sum(s.status != "unavailable" for s in got)
        relax = sum(s.relaxable for s in got)
        css = "ok" if free == len(required) else "ask" if free + relax == len(required) else "no"
        out[(start[:10], start[11:])] = (f"{free}/{len(required)}" + (f" +{relax}?" if relax else ""), css)
    return out


LEGEND = ('<div class="legend"><span class="ok">free</span><span class="soft">prefer not</span>'
          '<span class="ask">could free, if asked</span><span class="no">busy</span>'
          '<span class="busy">private event</span><span class="away">away / outside hours</span></div>')


def calendars_tab(latest: dict, pick: str | None) -> None:
    st.markdown(LEGEND, unsafe_allow_html=True)
    if arm == "c":
        st.warning("In this arm one shared agent read everyone's calendars and messages directly.")
    if organiser:
        st.markdown("#### Everyone, as the coordinator sees it")
        st.caption("How many required attendees can make each start time, from the availability summaries. "
                   "No names, no reasons. \"+1?\" means one more could free the time if asked.")
        st.markdown(table(group_cells(latest), pick), unsafe_allow_html=True)
    people = [a.id for a in scenario.request.attendees]
    pid = st.selectbox("Whose calendar", people, key="who", format_func=lambda p: names[p]) if admin else me
    whose = "your" if pid == me else f"{first(pid)}'s"
    left, right = st.columns(2)
    with left:
        st.markdown(f"#### {whose.capitalize()} calendars")
        st.caption("Private: only this person's personal agent reads them.")
        st.markdown(table(private_cells(pid), pick), unsafe_allow_html=True)
        p = scenario.participant(pid)
        for m in p.messages:
            st.caption(f"Message from {m.sender}: {m.text}")
        for s in p.preferences:
            st.caption(f"Said: {s.text}")
    with right:
        st.markdown(f"#### What {whose} agent shared")
        st.caption("The availability summary the coordinator receives: per start time, free or not, never why.")
        if pid in latest:
            st.markdown(table(summary_cells(latest[pid]), pick), unsafe_allow_html=True)
        else:
            st.info("Nothing shared yet at this step.")


# ------------------------------------------------------------------ the other tabs
def bubble(e, me_is_actor: bool = False) -> None:
    avatar = "🛡️" if e.actor == "privacy filter" else "🤖" if e.actor in ("coordinator", "shared", "gate") or e.actor.startswith("personal:") else "🧑"
    with st.chat_message("user" if me_is_actor else who(e.actor), avatar=avatar):
        st.markdown(f"**{who(e.actor)}**  \n{named(e.text)}")


def chat_tab(shown: list) -> None:
    st.markdown("#### Request thread · everyone sees this")
    for e in shown:
        if "thread" in e.visible_to and e.kind in CHATTY:
            bubble(e, e.actor == me)
    if organiser:
        org = [e for e in shown if "organiser" in e.visible_to and e.kind in ("approval", "gate")]
        if org:
            st.markdown("#### Organiser only")
            for e in org:
                bubble(e)
    pids = [a.id for a in scenario.request.attendees] if admin else [me]
    for pid in pids:
        private = [e for e in shown if e.kind in ("ask", "answer") and pid in e.visible_to]
        if private:
            st.markdown(f"#### Private · {'you and your personal agent' if pid == me else first(pid) + ' and their personal agent'}")
            for e in private:
                bubble(e, e.actor == me)


def tick(done: bool, text: str) -> str:
    return f"{'✅' if done else '⬜'} {text}"


def tasks_tab(shown: list, asked: dict | None) -> None:
    r = scenario.request
    if organiser:
        st.markdown("#### Organiser")
        approvals = [e for e in shown if e.kind == "approval"]
        sent = next((e for e in shown if e.kind == "gate"), None)
        lines = [tick(any(e.kind == "request" for e in shown), f"Ask: \"{r.text}\""),
                 tick(bool(approvals) or asked is not None, "The agents find a time and propose it")]
        if asked is not None:
            lines.append(tick(False, f"**Approve or reject the invite for {nice_slot(asked['start'], asked['end'])}** (waiting for you, above)"))
        for e in approvals:
            lines.append(tick(True, f"You decided: {named(e.text)}"))
        lines.append(tick(sent is not None, f"Invite sent and checked on every calendar{': ' + sent.text if sent else ''}"))
        st.markdown("  \n".join(lines))
    outcome = next((e for e in shown if e.kind == "outcome"), None)
    for pid in ([a.id for a in r.attendees] if admin else [me]):
        st.markdown(f"#### {'You' if pid == me else names[pid]}")
        lines = []
        shared = [e for e in shown if e.kind == "summary" and e.actor == f"personal:{pid}"]
        lines.append(tick(bool(shared), "Your personal agent shares when you are free, never why"))
        for e in shown:
            if e.kind == "ask" and pid in e.visible_to:
                reply = next((x for x in shown if x.kind == "answer" and x.actor == pid and x.seq > e.seq), None)
                lines.append(tick(reply is not None, f"Answer privately: {named(e.text.split(': ', 1)[-1])}"
                                  + (f" You said: \"{reply.text}\"" if reply else "")))
        if outcome is not None:
            ok = outcome.text.startswith("scheduled")
            lines.append(tick(ok, f"Invite on your calendar: {nice_slot(*outcome.text.split()[1:2])}" if ok
                              else "No time found: the request went back to the organiser"))
        st.markdown("  \n".join(lines))
    if admin:
        st.markdown("#### Coordinator agent")
        for e in shown:
            if e.kind == "ranking":
                with st.expander(f"Shortlist at step {e.seq}"):
                    st.text(named(e.text))


def data_tab(shown: list) -> None:
    pids = [a.id for a in scenario.request.attendees] if admin else [me]
    for tab, pid in zip(st.tabs([names[p] for p in pids]), pids):
        p = scenario.participant(pid)
        with tab:
            st.markdown(f"**{p.name}**, usual hours {p.hours_start}-{p.hours_end}")
            with st.expander("Their own data (only their personal agent reads it)" if pid != me else
                             "Your own data (only your personal agent reads it)", expanded=True):
                for c in p.calendars:
                    st.markdown(f"*{c.name} calendar*: " + "; ".join(f"{e.start[5:]}-{e.end[11:]} {e.title}" for e in c.events))
                for l in p.leave:
                    st.markdown(f"*away* {l.start_date} to {l.end_date}: {l.reason}")
                for m in p.messages:
                    st.markdown(f"*message from {m.sender}*: {m.text}")
                for s in p.preferences:
                    st.markdown(f"*said*: {s.text}")
            st.markdown("**What the personal agent did**")
            for e in shown:
                if e.actor == f"personal:{pid}":
                    st.markdown(f"- {e.kind}: {named(e.text)}")


def trace_tab(shown: list, rec: EpisodeResult) -> None:
    cols = st.columns(5)
    cols[0].metric("Model calls", rec.llm_calls)
    cols[1].metric("Tokens", rec.input_tokens + rec.output_tokens)
    cols[2].metric("Cost (USD)", f"{rec.cost_usd:.4f}")
    cols[3].metric("Seconds", f"{rec.latency_s:.0f}")
    cols[4].metric("Model", "fake" if rec.fake_llm else rec.model)
    seen = [c for c in scenario.ground_truth.canaries if c.lower() in rec.coordinator_context.lower()]
    st.markdown("**Private details in the coordinator's window:** " + (", ".join(seen) if seen else "none"))
    kinds = st.multiselect("Show kinds", sorted({e.kind for e in shown}), key="kinds")
    actors = st.multiselect("Show actors", sorted({e.actor for e in shown}), key="actors", format_func=who)
    st.dataframe([{"#": e.seq, "actor": who(e.actor), "kind": e.kind, "visible to": ", ".join(e.visible_to), "text": e.text}
                  for e in shown if (not kinds or e.kind in kinds) and (not actors or e.actor in actors)],
                 hide_index=True, width="stretch")
    st.markdown("**Guardrails: checks in code, every verdict**")
    st.dataframe([g.model_dump() for g in rec.guardrails], hide_index=True, width="stretch")
    st.markdown("**Tool calls**")
    st.dataframe([{"tool": c.tool, "caller": who(c.caller), "args": json.dumps(c.args)} for c in rec.calls],
                 hide_index=True, width="stretch")
    st.markdown("**Writes to calendars**")
    st.dataframe([w.model_dump() for w in rec.writes], hide_index=True, width="stretch")
    if rec.blocked_messages:
        st.markdown("**Stopped by the privacy filter**")
        for m in rec.blocked_messages:
            st.markdown(f"- {m}")
    st.download_button("Download this run as JSON", rec.model_dump_json(indent=2), file_name=f"{arm}-{sid}.json",
                       key="download")


# ------------------------------------------------------------------ the page
def render(rec: EpisodeResult, done: bool, asked: dict | None = None) -> None:
    r = scenario.request
    st.subheader(r.text)
    st.caption(f"Organised by {names[r.organiser_id]} · {r.duration_min} minutes, {r.day_start}-{r.day_end} on "
               f"{', '.join(r.days)}, {r.start_date} to {r.end_date} · "
               + ", ".join(f"{names[a.id]} ({a.role})" for a in r.attendees))
    if rec.fake_llm:
        st.caption("Scripted run (fake model): it shows the plumbing and the views, not the model's own choices.")
    timeline = rec.timeline
    if not timeline:
        return
    k = st.slider("Step", 1, len(timeline), len(timeline), key=f"step-{len(timeline)}") if len(timeline) > 1 else 1
    shown = timeline[:k]
    n = sum(e.kind == "summary" for e in shown)
    latest = {s.participant_id: s for s in rec.summaries[:n]}
    pick = next((e.text.split()[1] for e in shown if e.kind == "outcome" and e.text.startswith("scheduled")), None)
    if done and k == len(timeline):
        cost = (f"  ·  {rec.llm_calls} model calls, {rec.input_tokens + rec.output_tokens} tokens, "
                f"USD {rec.cost_usd:.4f}, {rec.latency_s:.0f} s") if admin else ""
        message = f"Outcome: {rec.outcome.status} {nice_slot(rec.outcome.start, rec.outcome.end)}{cost}"
        (st.success if rec.outcome.status == "scheduled" else st.warning)(message)
    labels = ["Chat", "Calendars", "Tasks", "Participants" if admin else "My data"] + (["Admin trace"] if admin else [])
    tabs = st.tabs(labels)
    with tabs[0]:
        chat_tab([e for e in shown if can_see(e)])
    with tabs[1]:
        calendars_tab(latest, pick)
    with tabs[2]:
        tasks_tab([e for e in shown if can_see(e)], asked)
    with tabs[3]:
        data_tab([e for e in shown if can_see(e)])
    if admin:
        with tabs[4]:
            trace_tab(shown, rec)


if mode == "Replay":
    files = sorted(settings.results_dir.glob(f"*/{arm}/{sid}/run*.json"))
    if not files:
        st.info(f"No saved runs of arm {arm} on {sid} under {settings.results_dir}. Run "
                f"`python -m scheduler.demo.seed --runs` for the demo requests, or use Live.")
    else:
        path = st.sidebar.selectbox("Saved run", files, key="file",
                                    format_func=lambda f: str(f.relative_to(settings.results_dir)))
        render(EpisodeResult.model_validate(json.loads(path.read_text())), True)
elif not organiser:
    st.info(f"Only the organiser of this request, {names[scenario.request.organiser_id]}, can start a live run. "
            "Sign in as them or as demo_admin, or replay a saved run.")
else:
    live = st.session_state.get("live")
    if live and (live["sid"], live["arm"]) != (sid, arm):
        live = st.session_state["live"] = None
    if st.sidebar.button("Run this request now", key="run"):
        started = begin(scenario, settings)
        live = st.session_state["live"] = {"sid": sid, "arm": arm, "started": started, "result": None}
        try:
            with st.spinner("The agents are working (about a minute with a real model)..."):
                live["coordinator"] = ARMS[arm][1](scenario)
                live["asked"] = live["coordinator"].start()
        except llm.BudgetExceeded as e:
            live["outcome"], live["asked"] = Outcome(status="budget", message=str(e)), None
    if live and live.get("asked"):
        slot = live["asked"]
        st.warning(f"You are the organiser. Approve the invite for {nice_slot(slot['start'], slot['end'])}?")
        approve, reject = st.columns(2)
        decision = ("approve" if approve.button("Approve", key="approve") else
                    "reject" if reject.button("Reject", key="reject") else None)
        if decision:
            with st.spinner("Recheck, send, read back..."):
                live["asked"] = live["coordinator"].resume(decision)
            st.rerun()
    if live and not live.get("asked") and live["result"] is None:
        outcome = live.get("outcome") or live["coordinator"].outcome
        run = 1 + len(list(settings.results_dir.glob(f"{LIVE_TAG}/{arm}/{sid}/run*.json")))
        live["result"] = collect(arm, scenario, run, LIVE_TAG, settings, outcome, live["started"])
        save_result(settings.results_dir, live["result"])
    if live:
        render(live["result"] or live_record(), live["result"] is not None, live.get("asked"))
    else:
        st.info("Press **Run this request now** in the sidebar. The run pauses for your approval before the invite.")
