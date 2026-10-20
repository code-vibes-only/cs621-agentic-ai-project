"""A demo of one scheduling episode, to show what each person sees and does.

    uv run --group demo python -m streamlit run scheduler/demo/app.py

Replay steps through a saved result file: no cost, no waiting. Live runs one episode now, with
you as the organiser: the run pauses before the invite until you approve or reject it. Only dev
scenarios are offered, so nobody sees an agent's output on the held-out set before the sweep.
Nothing here produces a reported number; those come only from `python -m scheduler.eval --report`."""
import json

import streamlit as st

from scheduler import llm
from scheduler.agents.shared import shared_coordinator
from scheduler.config import load_settings
from scheduler.contracts.result import EpisodeResult, Outcome, save_result
from scheduler.contracts.scenario import load_split
from scheduler.eval.arms import team_coordinator
from scheduler.eval.episode import begin, collect
from scheduler.sandbox import world

ARMS = {"d": ("Personal agents + coordinator agent (our design)", team_coordinator),
        "c": ("One agent that sees everyone's data (the ablation)", shared_coordinator)}
LIVE_TAG = "demo-live"

settings = load_settings()
scenarios = {s.id: s for s in load_split(settings.data_dir, "dev")}

st.set_page_config(page_title="Scheduler demo", layout="wide")
mode = st.sidebar.radio("Mode", ["Replay", "Live"], key="mode")
sid = st.sidebar.selectbox("Scenario", list(scenarios), key="scenario",
                           format_func=lambda i: f"{i}: {scenarios[i].request.text[:48]}")
arm = st.sidebar.selectbox("Arm", list(ARMS), key="arm", format_func=lambda a: ARMS[a][0])
scenario = scenarios[sid]


def line(e) -> str:
    return f"**{e.actor}** · {e.kind}: {e.text}"


def seen_by(events, who: str, arm: str) -> list:
    """The events one audience saw. The shared agent of arm (c) is the coordinator."""
    return [e for e in events if who in e.visible_to or (who == "coordinator" and arm == "c" and "shared" in e.visible_to)]


def render(timeline: list, arm: str, result: EpisodeResult | None) -> None:
    r = scenario.request
    st.subheader(r.text)
    st.caption(f"{r.duration_min} minutes, {r.day_start}-{r.day_end} on {', '.join(r.days)}, "
               f"{r.start_date} to {r.end_date} · " + ", ".join(f"{a.id} ({a.role})" for a in r.attendees))
    if not timeline:
        return
    k = st.slider("Step", 1, len(timeline), len(timeline), key=f"step-{len(timeline)}") if len(timeline) > 1 else 1
    shown = timeline[:k]
    thread, coord, people = st.columns([1, 1, 1.3])
    with thread:
        st.markdown("#### Request thread · everyone sees this")
        for e in seen_by(shown, "thread", arm):
            st.markdown(line(e))
        st.markdown("#### Organiser")
        for e in seen_by(shown, "organiser", arm):
            st.markdown(line(e))
    with coord:
        st.markdown("#### The coordinator sees")
        for e in seen_by(shown, "coordinator", arm):
            st.markdown(line(e))
        if result is not None:
            seen = [c for c in scenario.ground_truth.canaries if c.lower() in result.coordinator_context.lower()]
            st.markdown("**Private details in its window:** " + (", ".join(seen) if seen else "none"))
    with people:
        st.markdown("#### Each participant, privately")
        for tab, a in zip(st.tabs([a.id for a in r.attendees]), r.attendees):
            p = scenario.participant(a.id)
            with tab:
                st.markdown(f"**{p.name}**, usual hours {p.hours_start}-{p.hours_end}")
                with st.expander("Their own data (only their personal agent reads it)"):
                    for c in p.calendars:
                        st.markdown(f"*{c.name} calendar*: " + "; ".join(f"{e.start[5:]}-{e.end[11:]} {e.title}" for e in c.events))
                    for l in p.leave:
                        st.markdown(f"*away* {l.start_date} to {l.end_date}: {l.reason}")
                    for m in p.messages:
                        st.markdown(f"*message from {m.sender}*: {m.text}")
                    for s in p.preferences:
                        st.markdown(f"*said*: {s.text}")
                for e in seen_by(shown, a.id, arm):
                    st.markdown(line(e))
    with st.expander("Guardrails: checks in code, every verdict"):
        for e in shown:
            if e.kind == "guardrail":
                st.markdown(("✅ " if e.text.startswith("pass") else "⛔ ") + f"{e.actor.removeprefix('guardrail:')}: {e.text}")
    if result is not None and k == len(timeline):
        st.success(f"Outcome: {result.outcome.status} {result.outcome.start or ''}  ·  {result.llm_calls} model calls, "
                   f"{result.input_tokens + result.output_tokens} tokens, USD {result.cost_usd:.4f}, {result.latency_s:.0f} s")


if mode == "Replay":
    files = sorted(settings.results_dir.glob(f"*/{arm}/{sid}/run*.json"))
    if not files:
        st.info(f"No saved runs of arm {arm} on {sid} under {settings.results_dir}. Run one with "
                f"`python -m scheduler.eval --arm {arm} --scenarios {sid} --tag demo`, or use Live.")
    else:
        path = st.sidebar.selectbox("Saved run", files, key="file",
                                    format_func=lambda f: str(f.relative_to(settings.results_dir)))
        result = EpisodeResult.model_validate(json.loads(path.read_text()))
        render(result.timeline, arm, result)
else:
    live = st.session_state.get("live")
    if live and (live["sid"], live["arm"]) != (sid, arm):
        live = st.session_state["live"] = None
    if st.sidebar.button("Run this scenario now", key="run"):
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
        st.warning(f"You are the organiser. Approve the invite for {slot['start']} to {slot['end'][11:]}?")
        approve, reject = st.columns(2)
        decision = ("approve" if approve.button("Approve", key="approve") else
                    "reject" if reject.button("Reject", key="reject") else None)
        if decision:
            with st.spinner("Recheck, send, read back..."):
                live["asked"] = live["coordinator"].resume(decision)
    if live and not live.get("asked") and live["result"] is None:
        outcome = live.get("outcome") or live["coordinator"].outcome
        run = 1 + len(list(settings.results_dir.glob(f"{LIVE_TAG}/{arm}/{sid}/run*.json")))
        live["result"] = collect(arm, scenario, run, LIVE_TAG, settings, outcome, live["started"])
        save_result(settings.results_dir, live["result"])
    if live:
        render(live["result"].timeline if live["result"] else list(world.TIMELINE), arm, live["result"])
    else:
        st.info("Press **Run this scenario now** in the sidebar. The run pauses for your approval before the invite.")
