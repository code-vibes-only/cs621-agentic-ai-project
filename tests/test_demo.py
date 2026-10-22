"""The demo app in mocked mode: the starting world, reading requests, a full group meeting with a
private question and a host's choice of time, Add and Analyse, and the pages themselves.
Needs the demo group: `uv run --group demo pytest`."""
import json
import time
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from scheduler.config import load_settings  # noqa: E402
from scheduler.demo import analyse, engine, store  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "scheduler" / "demo" / "app.py")
USERS = json.loads((load_settings().data_dir / "demo" / "users.json").read_text())["users"]
ACADEMIC = "Let's have a 90-minute meeting to plan the deck next week, evenings"


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHEDULER_DEMO_DB", str(tmp_path / "app.db"))
    monkeypatch.setenv("SCHEDULER_RESULTS_DIR", str(tmp_path / "results"))
    store.reset()
    store.set_setting("llm_mode", "mock")
    store.set_setting("check_first:bob", "0")         # on in the seed; the demo-script test turns it back on


def wait_for(fn, what: str, timeout: float = 30):
    end = time.time() + timeout
    while time.time() < end:
        if got := fn():
            return got
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


def signed_in(username: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="username").input(username)
    at.text_input(key="password").input(username)
    at.button[0].click().run()
    assert not at.exception
    return at


def test_every_login_is_a_person_in_the_world_and_alice_is_in_every_circle():
    assert {u["participant_id"] for u in USERS} == {p["id"] for p in store.people()}
    tags = {t for c in store.chats("alice") for t in c["tags"].split(",")}
    assert {"academic", "work", "family", "others"} <= tags


def test_the_mocked_reader_invites_the_group_and_reads_the_window():
    ask = engine.read_by_rules(ACADEMIC, "alice", "chat-cs621")
    assert ask["attendees"] == ["alice", "bob", "charlie", "damian", "eve"]
    assert (ask["duration_min"], ask["start_date"], ask["end_date"], ask["day_start"]) == (90, "2026-10-26", "2026-10-30", "19:00")
    work = engine.read_by_rules("30-minute sync on the Q4 dashboard with George next week at lunchtime", "alice",
                                "chat-data-team")
    assert work["attendees"] == ["alice", "george"] and (work["duration_min"], work["day_start"]) == (30, "12:00")


def test_a_group_meeting_asks_privately_lets_the_host_choose_and_lands_on_every_calendar():
    run = engine.handle_agent_message("alice", ACADEMIC, "chat-cs621")
    ask = wait_for(lambda: store.tasks("charlie"), "Charlie's private question")[0]
    assert "cafe shift" in ask["prompt"] and store.open_count("charlie", "chat-cs621") == 1
    store.answer_task(ask["id"], "Yes")
    approval = wait_for(lambda: store.tasks("alice"), "Alice's approval")[0]
    other = approval["payload"]["options"][0]
    store.answer_task(approval["id"], f"Prefer {other['start']}")
    run.join(30)
    r = next(r for r in store.requests() if r["kind"] == "meeting")
    assert r["status"] == "scheduled" and r["outcome"]["start"] == other["start"]
    for pid in ("alice", "bob", "charlie", "damian", "eve"):
        assert any(e["request_id"] == r["id"] and e["start_at"] == other["start"] for e in store.events(pid)), pid
    steps = store.trace(r["id"])
    assert steps[0]["kind"] == "initiated" and steps[0]["visible_to"] == ["alice"]
    assert {"read", "ask", "preference", "approval", "gate", "outcome"} <= {s["kind"] for s in steps}
    shared = " ".join(s["text"] for s in steps if {"coordinator", "thread"} & set(s["visible_to"]))
    for private in ("Cafe shift", "Visa interview", "hospital follow-up", "swap with Sam", "futsal", "Ethan", "mother"):
        assert private.lower() not in shared.lower(), private
    assert any(m["text"].startswith("✅ Invite sent") for m in store.messages("chat-cs621"))
    said = [m["text"] for m in store.agent_messages("alice", "chat-cs621")]
    assert any(t.startswith("Heard back from Bob, Charlie, Damian and Eve's agents (4 of 4)") for t in said)
    assert sum(t.startswith("Heard back") for t in said) == 1                     # one line, updated in place
    assert "The coordinator is asking Charlie privately about a time. I'll tell you when they answer." in said
    assert "Charlie agreed. The coordinator is checking the times again." in said
    assert not any("Cafe" in t or "shift" in t for t in said)                    # whether, never why


def test_no_hours_named_means_the_hours_everyone_keeps():
    ask = engine.read_by_rules("Let's plan for a project rehearsal next week", "alice", "chat-cs621")
    assert ask["day_start"] is None and ask["day_end"] is None
    assert engine.shared_hours(ask["attendees"]) == ("09:00", "21:00")      # Charlie starts at 9, Damian stops at 9pm


def test_when_nothing_fits_the_agents_give_their_next_best_times_and_preferences_steer_them():
    run = engine.handle_agent_message("alice", "Let's plan a project rehearsal next week, mornings", "chat-cs621")
    approval = wait_for(lambda: store.tasks("alice"), "Alice's approval", 60)[0]
    assert approval["payload"]["start"] == "2026-11-02T18:00"       # a weekday: Damian's weekends are family time
    store.answer_task(approval["id"], "Yes")
    run.join(30)
    r = next(r for r in store.requests("alice") if r["kind"] == "meeting")
    assert r["status"] == "scheduled" and r["parsed"]["end_date"] == "2026-11-08"
    said = [m["text"] for m in store.agent_messages("alice", "chat-cs621")]
    assert any(t.startswith("Nothing fits Mon 26 Oct to Fri 30 Oct, 09:00-12:00. Rather than give up") for t in said)
    summaries = [s["text"] for s in store.trace(r["id"]) if s["kind"] == "summary"]
    assert any(", 0 prefer not" not in t for t in summaries)               # some agent said "prefer not", never why


def test_the_organiser_can_cancel_a_request_and_nothing_lands_anywhere():
    run = engine.handle_agent_message("alice", ACADEMIC, "chat-cs621")
    ask = wait_for(lambda: store.tasks("charlie"), "Charlie's private question")[0]
    r = store.requests("alice")[0]
    assert not engine.cancel(r["id"], "bob")                                   # only the organiser can
    assert engine.cancel(r["id"], "alice")
    run.join(30)
    assert not run.is_alive() and store.request(r["id"])["status"] == "cancelled"
    assert store.task(ask["id"])["status"] == "expired" and not store.tasks("alice")
    assert not any(e["request_id"] == r["id"] for p in ("alice", "charlie") for e in store.events(p))
    assert store.messages("chat-cs621")[-1]["text"].startswith('Alice cancelled "Plan the deck"')


def test_your_agent_tells_you_when_it_answered_for_you_and_it_shows_as_a_notification():
    run = engine.handle_agent_message("alice", ACADEMIC, "chat-cs621")
    wait_for(lambda: store.tasks("charlie"), "Charlie's private question")
    engine.cancel(store.requests("alice")[0]["id"], "alice")
    run.join(30)
    news = [m["text"] for m in store.unread("bob")]
    assert any("answered for you" in t and "never sees why" in t for t in news)
    assert any(t.startswith('Alice cancelled "Plan the deck"') for t in news)
    at = signed_in("bob")
    assert any(p.proto.popover.label == f"🔔 Notifications ({len(news)})" for p in at.sidebar.get("popover"))
    at.button(key="open-chat-cs621").click().run()
    at.button(key="tab-agent-chat-cs621").click().run()                    # reading your agent chat clears them
    assert not at.exception and not store.unread("bob", "chat-cs621")


def test_a_question_from_your_agent_comes_with_your_own_free_times():
    ask = engine.MeetingAsk(**engine.read_by_rules(ACADEMIC, "alice", "chat-cs621"))
    free = engine.free_times("bob", ask)
    assert free and not any(f.startswith("Mon 26 Oct") for f in free)      # Bob's late shift runs to 22:00
    assert free[0] == "Tue 27 Oct 19:00 to 22:30"


def test_maybe_frees_the_time_only_as_a_strong_prefer_not():
    run = engine.handle_agent_message("alice", ACADEMIC, "chat-cs621")
    ask = wait_for(lambda: store.tasks("charlie"), "Charlie's private question")[0]
    store.answer_task(ask["id"], "Maybe")
    approval = wait_for(lambda: store.tasks("alice"), "Alice's approval")[0]
    assert approval["payload"]["start"].startswith("2026-10-28T19")          # nothing better, so Wednesday after all
    r = store.requests("alice")[0]
    charlie = [s["text"] for s in store.trace(r["id"]) if s["actor"] == "personal:charlie" and s["kind"] == "summary"]
    assert ", 0 prefer not" in charlie[0] and ", 0 prefer not" not in charlie[-1]
    assert any(m["text"].startswith("Thanks. I told the coordinator: maybe.") for m in store.agent_messages("charlie"))
    store.answer_task(approval["id"], "Yes")
    run.join(30)


def test_no_with_a_suggested_day_steers_the_next_best_round_and_charlie_hears_how_it_went():
    run = engine.handle_agent_message("alice", ACADEMIC.replace(", evenings", ""), "chat-cs621")
    ask = wait_for(lambda: store.tasks("charlie"), "Charlie's private question")[0]
    store.answer_task(ask["id"], "No: prefer not to, what about Thursday?")
    approval = wait_for(lambda: store.tasks("alice"), "Alice's approval", 60)[0]
    assert approval["payload"]["start"].startswith("2026-11-05")             # Thursday in the next week: Eve is away on the 29th
    assert len(store.tasks("charlie", history=True)) == 1                   # his no was remembered, never asked twice
    store.answer_task(approval["id"], "Yes")
    run.join(30)
    said = [m["text"] for m in store.agent_messages("charlie")]
    assert any("I steered it towards Thu 29 Oct" in t for t in said)
    assert any(m["role"] == "coordinator" and "and the time you suggested instead (Thu 29 Oct" in m["text"]
               for m in store.agent_messages("charlie"))
    assert any(t.startswith("The time you suggested") and t.endswith("is the one that was picked.") for t in said)
    assert any(m["text"].startswith("Someone suggested a different time within what you asked for")
               for m in store.agent_messages("alice"))


def test_flexibility_is_a_scale_the_agents_understand_and_the_agent_suggests_it():
    assert [analyse.suggest_flex(t) for t in ("Dentist", "Cafe shift", "Gym", "Movie night (flexible)")] == [0, 1, 2, 3]
    ask = engine.MeetingAsk(**engine.read_by_rules(ACADEMIC, "alice", "chat-cs621"))
    scenario = engine.build_scenario("r-test", ask)
    alice = scenario.participant("alice")
    on_calendar = {e.id for c in alice.calendars for e in c.events}
    assert "e-alice-2" not in on_calendar and any(m.id == "e-alice-2" for m in alice.memory)   # the gym: flexible
    gym = next(t.rule for t in scenario.ground_truth.rules if t.rule.ref == "e-alice-2")
    assert (gym.kind, gym.weight) == ("soft", 0.5)
    cafe = next(e for c in scenario.participant("charlie").calendars for e in c.events if e.id == "e-charlie-0")
    assert cafe.movable                                                      # ask me first: the coordinator asks


def test_when_the_agent_had_to_guess_it_checks_with_you_before_asking_anyone(monkeypatch):
    rules = engine.read_by_rules
    monkeypatch.setattr(engine, "read_by_rules", lambda *a: rules(*a) | {"assumed": "the slides are done by Fri 30 Oct"})
    engine.handle_agent_message("alice", "Rehearsal after the slides are confirmed", "chat-cs621").join(30)
    r = store.requests("alice")[0]
    assert r["status"] == "check with you" and not store.tasks("charlie")      # nobody else asked yet
    assert "I assumed the slides are done by Fri 30 Oct. Shall I go ahead?" in store.agent_messages("alice")[-1]["text"]
    engine.handle_agent_message("alice", "No, the slides are confirmed on Wed 28 Oct", "chat-cs621").join(30)
    assert store.request(r["id"])["text"].endswith("confirmed on Wed 28 Oct")      # a correction: read again with it
    assert store.request(r["id"])["status"] == "check with you"
    run = engine.confirm(r["id"], "alice")
    wait_for(lambda: store.tasks("charlie"), "Charlie's private question")         # now the agents are asked
    assert any(m["text"].startswith("Going ahead") for m in store.agent_messages("alice"))
    engine.cancel(r["id"], "alice")
    run.join(30)


def test_what_someone_already_answered_reaches_their_agent_in_a_later_round():
    engine.CURRENT["said"] = {"bob": [("Which hours are weekend mornings?", "08:00 to 12:00")]}
    try:
        ask = engine.MeetingAsk(**engine.read_by_rules(ACADEMIC, "alice", "chat-cs621"))
        bob = engine.build_scenario("r-test", ask).participant("bob")
    finally:
        engine.CURRENT.pop("said", None)
    assert [p.text for p in bob.preferences] == ['Asked "Which hours are weekend mornings?", they answered: "08:00 to 12:00"']


def test_a_suggestion_outside_the_window_wins_when_it_works_better_for_everyone():
    run = engine.handle_agent_message("alice", ACADEMIC, "chat-cs621")              # weekday evenings only
    ask = wait_for(lambda: store.tasks("charlie"), "Charlie's private question")[0]
    store.answer_task(ask["id"], "No: what about Saturday afternoon?")
    approval = wait_for(lambda: store.tasks("alice"), "Alice's approval", 60)[0]
    assert approval["payload"]["start"].startswith("2026-10-31T1")                 # Saturday: nothing asked for works
    assert "outside what you asked for: someone suggested it" in approval["prompt"]
    assert any(m["text"].startswith("Someone suggested a time outside what you asked for: Sat 31 Oct")
               for m in store.agent_messages("alice"))
    assert len(store.tasks("charlie", history=True)) == 1                          # the search restarted; not re-asked
    store.answer_task(approval["id"], "Yes")
    run.join(30)


def test_a_suggestion_that_works_worse_for_everyone_goes_back_to_who_suggested_it():
    run = engine.handle_agent_message("alice", ACADEMIC.replace(", evenings", ""), "chat-cs621")
    ask = wait_for(lambda: store.tasks("charlie"), "Charlie's private question")[0]
    store.answer_task(ask["id"], "Maybe: what about Sunday 1 Nov at lunch?")       # Alice has Mum's lunch then
    approval = wait_for(lambda: store.tasks("alice"), "Alice's approval", 60)[0]
    assert approval["payload"]["start"] == "2026-10-28T18:00" and "outside" not in approval["prompt"]
    store.answer_task(approval["id"], "Yes")
    run.join(30)
    assert any(m["text"].startswith("The time you suggested") and "didn't work for everyone" in m["text"]
               for m in store.agent_messages("charlie"))


def test_add_and_analyse_finds_a_clash_and_adds_the_item_with_its_trace():
    proposal = analyse.start("alice", "Dentist on Thursday at 3pm")
    assert tuple(proposal["options"][0]) == ("2026-10-29T15:00", "2026-10-29T16:00")
    assert proposal["clashes"] == ["Office (data team)"] and len(proposal["options"]) == 3   # plus two nearby free times
    eid = analyse.commit("alice", proposal, 0, 0, "cal-alice-personal")
    assert store.event(eid)["request_id"] == proposal["rid"]
    kinds = [s["kind"] for s in store.trace(proposal["rid"])]
    assert kinds[0] == "initiated" and kinds[-1] == "outcome" and "ask" in kinds


def test_a_wrong_password_is_refused():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="username").input("alice")
    at.text_input(key="password").input("not-alice")
    at.button[0].click().run()
    assert "wrong password" in at.error[0].value and "user" not in at.session_state


def test_groups_and_calendar_are_the_only_pages_and_a_message_reaches_the_group():
    at = signed_in("alice")
    assert len(at.button_group(key="page").options) == 2 and not at.tabs
    at.button(key="open-chat-cs621").click().run()
    at.chat_input(key="input-chat-cs621").set_value("See you all next week").run()
    assert not at.exception and store.messages("chat-cs621")[-1]["text"] == "See you all next week"
    at.button(key="to-agent-chat-cs621").click().run()                       # the way to your private agent
    assert not at.exception and "#### 🔒 Your private agent" in [m.value for m in at.markdown]
    at.button(key="open-chat-cs621").click().run()                         # clicking the open group closes it
    assert "group" not in at.session_state and at.button(key="open-chat-cs621").label == "Open"


def test_a_meeting_typed_in_the_group_chat_is_nudged_to_your_agent():
    at = signed_in("alice")
    at.button(key="open-chat-cs621").click().run()
    at.chat_input(key="input-chat-cs621").set_value(ACADEMIC).run()
    assert "Want your agent to set it up?" in at.info[0].value
    at.button(key="nudge-go-chat-cs621").click().run()
    assert not at.exception
    r = wait_for(lambda: store.requests("alice"), "the forwarded request")[0]
    assert r["chat_id"] == "chat-cs621" and r["text"] == ACADEMIC
    ask = wait_for(lambda: store.tasks("charlie"), "Charlie's private question")[0]   # the run goes on as usual
    store.answer_task(ask["id"], "No")                                              # so the agents look further
    approval = wait_for(lambda: store.tasks("alice"), "Alice's approval of a next best time", 60)[0]
    store.answer_task(approval["id"], "Yes")
    wait_for(lambda: store.request(r["id"])["status"] == "scheduled", "the run to end", 60)


def test_a_group_can_get_a_new_tag_and_the_filter_offers_it():
    at = signed_in("alice")
    at.button(key="open-chat-cs621").click().run()
    at.text_input(key="tag-new-chat-cs621").input("Deck, Week 9").run()
    at.button(key="tags-save-chat-cs621").click().run()
    assert not at.exception
    assert store.chat("chat-cs621")["tags"].split(",") == ["academic", "deck week 9"]
    assert any("deck week 9" in o for o in at.button_group(key="filter-tags").options)
    assert store.all_tags("bob")[-1] == "deck week 9"            # shared: Bob's filter has it too


def test_the_calendar_shows_your_private_calendar_next_to_what_others_see():
    at = signed_in("alice")
    at.button_group(key="page").set_value("📅 Calendar").run()
    headings = [m.value for m in at.markdown if m.value.startswith("#####")]
    assert not at.exception and headings == ["##### 🔒 My calendar", "##### 👥 What others see"]
    blocks = store.busy_blocks("alice")
    assert blocks and all(s < e for s, e in blocks) and all(a[1] < b[0] for a, b in zip(blocks, blocks[1:]))


def test_add_and_analyse_at_a_clicked_time_offers_nearby_free_times_on_a_clash():
    proposal = analyse.start("alice", "Dentist", ("2026-10-29T10:00", "2026-10-29T11:00"))
    assert proposal["clashes"] == ["Office (data team)"] and len(proposal["options"]) == 3
    assert all(not store.query("select 1 from events e join calendars c on c.id = e.calendar_id where c.owner = 'alice' "
                               "and e.start_at < ? and e.end_at > ?", (e, s)) for s, e in proposal["options"][1:])


def test_add_and_analyse_notices_a_person_and_can_send_it_to_their_agent():
    brunch = ("2026-10-31T10:00", "2026-10-31T11:00")
    proposal = analyse.start("alice", "Brunch with Hannah", brunch)
    assert [m["id"] for m in proposal["mentions"]] == ["hannah"] and "Friends & family" in proposal["mentions"][0]["label"]
    exact = analyse.send("alice", proposal, 0, ["hannah"], flexible=False)          # Hannah has a recital then
    wait_for(lambda: store.request(exact)["status"] in ("hand_back", "scheduled"), "the exact-time run")
    assert store.request(exact)["status"] == "hand_back"
    flexible = analyse.send("alice", analyse.start("alice", "Brunch with Hannah", brunch), 0, ["hannah"], flexible=True)
    approval = wait_for(lambda: store.tasks("alice"), "Alice's approval")[0]
    store.answer_task(approval["id"], "Yes")
    wait_for(lambda: store.request(flexible)["status"] == "scheduled", "the flexible run")
    r = store.request(flexible)
    assert r["chat_id"] == store.direct_chat("alice", "hannah") and r["outcome"]["start"].startswith("2026-10-31")
    for pid in ("alice", "hannah"):
        assert any(e["request_id"] == flexible for e in store.events(pid)), pid
    assert store.trace(flexible)[0]["text"].endswith('from their calendar: "Brunch with Hannah" with Hannah')


def test_a_calendar_item_can_go_to_a_group_and_falls_back_to_a_chat_with_exactly_those_people():
    proposal = analyse.start("alice", "Dinner with Hannah, Saturday evening")
    friends = analyse.send("alice", proposal, 0, ["hannah", "ignatius", "jack"], True, "chat-friends")
    assert store.request(friends)["chat_id"] == "chat-friends"
    mixed = analyse.send("alice", analyse.start("alice", "Dinner with Hannah, Saturday evening"), 0,
                         ["hannah", "bob"], True, "chat-friends")       # Bob isn't in Friends & family
    chat = store.request(mixed)["chat_id"]
    assert chat != "chat-friends" and set(store.members(chat)) == {"alice", "hannah", "bob"}
    def settled(rid: str) -> bool:                                      # approve whatever is asked until the run ends
        for t in store.tasks("alice") + store.tasks("hannah") + store.tasks("bob"):
            store.answer_task(t["id"], "Yes")
        return store.request(rid)["status"] in ("hand_back", "scheduled", "error", "budget")
    for rid in (friends, mixed):                                        # let both runs end before the next test
        wait_for(lambda: settled(rid), rid, 60)


DEMO = "Can we meet next week to split the slides?"


def test_the_demo_script_bob_checks_first_charlie_decides_and_alice_sees_it_all():
    store.set_setting("check_first:bob", "1")
    run = engine.handle_agent_message("alice", DEMO, "chat-cs621")
    bob = wait_for(lambda: store.tasks("bob"), "Bob's yes or no")[0]
    charlie = wait_for(lambda: store.tasks("charlie"), "Charlie's question")[0]   # both open at once, any order
    rid = bob["request_id"]
    assert "Wed 28 Oct 18:00 to 19:00" in bob["prompt"] and "check with you before accepting" in bob["prompt"]
    assert [o["answer"] for o in bob["payload"]["options"]] == ["yes", "no"]
    assert charlie["prompt"].startswith("Your group usually meets on Wednesdays, but this week you have your cafe shift then")
    assert "you've swapped it before and the deck is due Fri 30 Oct" in charlie["prompt"]
    assert charlie["prompt"].endswith("do you want to check with Sam whether a swap works this time, and get back to "
                                      "me, or should I try for Thursday instead?")
    assert "happy" not in charlie["prompt"]                                   # nothing his notes don't say
    assert charlie["payload"]["options"][0] == {"label": "I'll check with Sam", "answer": "check", "suggest": ""}
    assert {"label": "Try Thursday instead", "answer": "no", "suggest": "Thu 29 Oct"} in charlie["payload"]["options"]
    assert engine.responses(rid) == {"bob": "waiting", "charlie": "waiting", "damian": "answered", "eve": "answered"}
    said = [m for m in store.agent_messages("alice", "chat-cs621")]
    assert [m["role"] for m in said].count("coordinator") == 1 and "Got it" in next(m["text"] for m in said
                                                                                   if m["role"] == "coordinator")
    store.answer_task(charlie["id"], "Check")                             # he checks with Sam first
    again = wait_for(lambda: [t for t in store.tasks("charlie") if t["id"] != charlie["id"]], "Charlie's follow-up")[0]
    assert again["prompt"] == "Can Sam swap your cafe shift with you?"
    assert [o["label"] for o in again["payload"]["options"]] == ["Yes, it's sorted", "No, keep it", "Try Thursday instead"]
    assert engine.responses(rid)["charlie"] == "waiting" and not store.tasks("alice")
    assert any(t.startswith("Charlie needs a moment to check something") for t in
               [m["text"] for m in store.agent_messages("alice")])
    store.answer_task(again["id"], "Reply: swap, and accept if all groupmates concur")   # Charlie first this time
    wait_for(lambda: engine.responses(rid).get("charlie") == "agreed", "Charlie's yes")
    assert engine.responses(rid)["bob"] == "waiting" and not store.tasks("alice")          # still waiting for Bob
    store.answer_task(bob["id"], "Yes")
    approval = wait_for(lambda: store.tasks("alice"), "Alice's approval")[0]
    assert approval["payload"]["start"] == "2026-10-28T18:00"
    assert set(engine.responses(rid).values()) == {"agreed", "answered"}
    store.answer_task(approval["id"], "Yes")
    run.join(30)
    assert store.request(rid)["status"] == "scheduled"
    to_charlie = [m["text"] for m in store.agent_messages("charlie")]
    assert any("Noted: only if all groupmates concur." in t for t in to_charlie)
    assert any("remember to sort out \"Cafe shift\"" in t for t in to_charlie)
    assert any("any time needs your OK first" in m["text"] for m in store.agent_messages("bob"))
    for pid in ("bob", "charlie"):                      # the coordinator confirms what reached it, once
        acks = [m["text"] for m in store.agent_messages(pid) if m["role"] == "coordinator"]
        assert acks == ["Got your yes for Wed 28 Oct 18:00 to 19:00. Nothing is booked until everyone has agreed and "
                        "Alice approves: I'll tell you when a time is set."], pid
    alice = [m["text"] for m in store.unread("alice")]
    assert any(t.startswith("Done: the invite for Wed 28 Oct 18:00 to 19:00") for t in alice)
    assert "Bob agreed. The coordinator is checking the times again." in alice
    shared = " ".join(s["text"] for s in store.trace(rid) if {"coordinator", "thread"} & set(s["visible_to"]))
    for private in ("Cafe", "swap", "Sam", "groupmates", "concur"):
        assert private.lower() not in shared.lower(), private
    at = signed_in("alice")
    at.session_state["trace"] = rid
    at.run()
    assert not at.exception and len(at.tabs) == 2
    assert any("ask_privately" in str(row) for df in at.dataframe for row in df.value.to_dict("records"))


def test_the_actions_dialog_offers_your_agents_answers_and_your_own_words():
    rid = store.new_request("alice", DEMO, "mock", chat_id="chat-cs621")
    options = [{"label": "I can swap it", "answer": "yes"}, {"label": "Try Thursday instead", "answer": "no", "suggest": "Thu 29 Oct"}]
    tid = store.add_task("charlie", rid, "consent", "Would you swap it?", {"about": "e-charlie-0", "options": options})
    at = signed_in("charlie")
    at.button(key="open-chat-cs621").click().run()
    at.button(key="actions-chat-cs621").click().run()       # a click inside the dialog needs a browser: AppTest can't
    assert not at.exception
    assert [b.label for b in at.button if b.key and b.key.startswith(f"opt-{tid}-")] == ["I can swap it", "Try Thursday instead"]
    assert at.text_input(key=f"own-{tid}").label == "Or answer in your own words" and at.button(key=f"own-send-{tid}")


def test_your_agent_reads_an_answer_in_your_own_words():
    assert engine.reading_by_rules("swap, and accept if all groupmates concur") == {
        "answer": "yes", "suggestion": "", "condition": "all groupmates concur"}
    assert engine.reading_by_rules("Only if nothing else works")["answer"] == "maybe"
    assert engine.reading_by_rules("Let me check with Sam and get back to you")["answer"] == "check"
    assert engine.reading_by_rules("Prefer not to, what about Thursday?") == {
        "answer": "no", "suggestion": "Prefer not to, what about Thursday?", "condition": ""}


def test_a_run_lost_in_a_restart_stops_cleanly_and_can_run_again():
    ask = engine.read_by_rules(DEMO, "alice", "chat-cs621") | {"day_start": "09:00", "day_end": "21:00"}
    rid = store.new_request("alice", DEMO, "mock", chat_id="chat-cs621")    # as a dead server process left it
    store.update_request(rid, status="waiting for approval", parsed=ask | {"attendee_ids": ask["attendees"]})
    store.execute("update requests set created = created - 60 where id = ?", (rid,))
    tid = store.add_task("alice", rid, "approval", "Send the invite?", {"start": "2026-10-28T18:00", "end": "2026-10-28T19:00"})
    assert engine.recover() == [rid] and engine.recover() == []
    assert store.request(rid)["status"] == "interrupted" and store.task(tid)["status"] == "expired"
    assert any("Press ↻ Run again" in m["text"] for m in store.agent_messages("alice"))
    assert any("stopped when the app restarted" in m["text"] for m in store.agent_messages("charlie"))
    assert engine.run_again(rid, "bob") is None                                   # only the organiser can
    run = engine.run_again(rid, "alice")
    wait_for(lambda: store.tasks("charlie"), "Charlie's question, asked again")
    assert engine.recover() == []                                                 # a live run is never touched
    engine.cancel(rid, "alice")
    run.join(30)


def test_the_trace_page_replays_a_request():
    proposal = analyse.start("alice", "Gym, 1 hour, Wednesday evening, flexible")
    analyse.commit("alice", proposal, 0, 2, "cal-alice-personal")
    at = signed_in("alice")
    at.session_state["trace"] = proposal["rid"]
    at.run()
    assert not at.exception and "Gym" in at.title[0].value
    assert any("asked their agent, privately" in m.value for m in at.markdown)
