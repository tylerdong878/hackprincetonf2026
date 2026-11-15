"""iMessage bot: parsing and a whole Daily played over 'texts' against the real game server (no Photon)."""
import json
import shutil
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.imessage.engine import Engine, GameAPI, Sessions
from backend.imessage.parse import parse

from .conftest import REPO

DAILY = "2026-11-14-daily-food-prices"
DAY = date(2026, 11, 14)
OPTS = ["out-of-context-quote", "misleading-chart", "cherry-picked-stat", "edited-detail"]
PHONE = "+15555550100"


@pytest.mark.parametrize("text,kind,trick", [
    ("real", "real", None), ("R", "real", None), ("👍", "real", None), ("  Legit! ", "real", None),
    ("fake", "fake", None), ("FAKE 2", "fake", "misleading-chart"), ("d2", "fake", "misleading-chart"),
    ("sus chart", "fake", "misleading-chart"), ("doctored, quote", "fake", "out-of-context-quote"),
    ("3", "trick", "cherry-picked-stat"), ("edited", "trick", "edited-detail"),
    ("check", "check", None), ("🔍", "check", None), ("play", "play", None), ("help", "help", None),
    ("?", "help", None), ("stats", "stats", None), ("STOP", "mute", None), ("remind", "unmute", None),
    ("what is this", "unknown", None), ("real quick question about the chart", "unknown", None),
    ("fake news is everywhere lol", "unknown", None), ("fake, not sure which", "fake", None),
])
def test_parse(text, kind, trick):
    i = parse(text, OPTS)
    assert (i.kind, i.trick) == (kind, trick)


def test_parse_not_sure_and_tool():
    assert parse("fake 0", OPTS).not_sure
    assert parse("not sure", OPTS).not_sure
    assert parse("check source", OPTS).tool == "source"
    assert parse("c data", OPTS).tool == "data"


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.imessage.render.chart_png", lambda chart: b"\x89PNG fake")
    d = tmp_path / "data"
    shutil.copytree(REPO / "data" / "cases" / DAILY, d / "cases" / DAILY)
    client = TestClient(create_app(data_dir=d, frontend_dist=tmp_path / "x", today=lambda: DAY))
    return Engine(GameAPI(client), Sessions(tmp_path / "imessage" / "sessions.json"))


def texts(outs):
    return "\n---\n".join(o.text for o in outs if o.text)


def key():
    return json.loads((REPO / "data" / "cases" / DAILY / "answer_key.json").read_text())["posts"]


def test_whole_daily_over_text(engine):
    first = engine.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    t = texts(first)
    assert "Commands:" in t and "STATS" in t
    assert "I'm Grain of Salt" in t and "Daily #" in t and "Post 1/5" in t
    assert any(o.image for o in first)  # p1 is a chart post -> sent as an image

    out = engine.handle(PHONE, "check")
    assert "📊" in texts(out) and "2 🔍 left" in texts(out)

    answers = key()
    last = None
    for i, pid in enumerate(["p1", "p2", "p3", "p4", "p5"]):
        k = answers[pid]
        if k["doctored"]:
            out = engine.handle(PHONE, "fake")
            assert "Which trick?" in texts(out)
            n = OPTS.index(k["trick"]) + 1
            out = engine.handle(PHONE, str(n))
            assert "Caught it" in texts(out)
        else:
            out = engine.handle(PHONE, "real")
            assert "That one's real" in texts(out)
        if i < 4:
            assert f"Post {i + 2}/5" in texts(out)
        last = out
    assert "Done! Score" in texts(last)
    assert "Grain of Salt #" in texts(last) and "5/5" in texts(last)

    again = texts(engine.handle(PHONE, "play"))
    assert "You've played Daily" in again
    assert "Streak: 1" in texts(engine.handle(PHONE, "stats"))


def test_sessions_survive_restart(engine, tmp_path):
    engine.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    engine.handle(PHONE, "real")
    fresh = Engine(engine.api, Sessions(tmp_path / "imessage" / "sessions.json"))
    out = texts(fresh.handle(PHONE, "play"))
    assert "Picking up where you left off" in out and "Post 2/5" in out


def test_unknown_text_hints_and_out_of_clues(engine):
    engine.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    hint = texts(engine.handle(PHONE, "banana"))
    assert "Didn't catch that" in hint and "RESET" in hint
    assert "No data for this post" not in texts(engine.handle(PHONE, "check data"))
    engine.handle(PHONE, "check account")
    engine.handle(PHONE, "real")
    engine.handle(PHONE, "check")
    assert "Out of 🔍" in texts(engine.handle(PHONE, "check account"))


def test_nudges_once_and_respect_mute(engine):
    engine.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    engine.handle("+15555550101", "hi", space_id="sp2", agent_id="ag1")
    engine.handle("+15555550101", "stop")
    due = engine.due_nudges(DAY)
    assert [s.handle for s, _ in due] == [PHONE]
    assert "Text PLAY" in due[0][1][0].text
    assert [s.handle for s, _ in engine.due_nudges(DAY)] == [PHONE]  # asking doesn't mark anyone
    sent = []
    assert engine.send_reminders(DAY, lambda s, outs: sent.append(s.handle)) == 1
    assert sent == [PHONE]
    assert engine.due_nudges(DAY) == []  # once a day
    assert Sessions(engine.sessions.path).get(PHONE).last_nudge == DAY.isoformat()  # saved to disk


def test_failed_reminder_is_retried_not_lost(engine):
    other = "+15555550102"
    engine.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    engine.handle(other, "hi", space_id="sp2", agent_id="ag1")
    sent = []

    def flaky(s, outs):
        if s.handle == PHONE:
            raise ConnectionError("network blip")
        sent.append(s.handle)

    assert engine.send_reminders(DAY, flaky) == 1
    assert sent == [other]  # one failed send doesn't stop the rest
    assert engine.sessions.get(PHONE).last_nudge is None  # and the failed one isn't marked as reminded
    assert engine.send_reminders(DAY, lambda s, outs: sent.append(s.handle)) == 1
    assert sent == [other, PHONE]  # retried at the next check; `other` isn't texted twice


def test_reminder_gives_up_for_the_day_after_a_few_tries(engine):
    from backend.imessage.engine import MAX_NUDGE_TRIES
    engine.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")

    def down(s, outs):
        raise ConnectionError("chat is gone")

    for _ in range(MAX_NUDGE_TRIES):
        assert engine.send_reminders(DAY, down) == 0
    assert engine.due_nudges(DAY) == []  # a dead chat isn't retried every minute all day
    assert engine.sessions.get(PHONE).last_nudge is None  # never marked: it was never sent


def test_merge_texts_keeps_images_in_place():
    from backend.imessage.photon_io import merge_texts
    from backend.imessage.render import Out
    outs = [Out.t("a"), Out.t("b"), Out(image=b"png"), Out.t("c"), Out.t("d"), Out.t("")]
    assert merge_texts(outs) == [Out.t("a\n\nb"), Out(image=b"png"), Out.t("c\n\nd")]


def test_reset_starts_a_fresh_daily(engine):
    engine.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    engine.handle(PHONE, "real")
    old = engine.sessions.get(PHONE).player_id
    out = texts(engine.handle(PHONE, "reset"))
    assert "New detective" in out and "Post 1/5" in out
    assert engine.sessions.get(PHONE).player_id != old


# ---- the detective partner (fake model: no network) ---------------------------------

class FakeChat:
    def __init__(self, reply="Hm. Look at where that axis starts."):
        self.reply, self.calls = reply, []

    def __call__(self, system, turns):
        self.calls.append((system, turns))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def partner_engine(engine, chat, cap=40):
    from backend.imessage.partner import Partner
    keys = key()
    return Engine(engine.api, engine.sessions, Partner(chat, daily_cap=cap), lambda case_id: keys)


def test_partner_answers_free_text_with_case_notes(engine):
    chat = FakeChat()
    e = partner_engine(engine, chat)
    e.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    out = texts(e.handle(PHONE, "who even posts this stuff"))
    assert out == "Hm. Look at where that axis starts."
    system, turns = chat.calls[-1]
    assert "CURRENT POST (post 1 of 5" in system and "Egg prices" in system
    assert "SECRET, for aiming hints only" in system  # the key aims hints ...
    assert turns[-1] == ("user", "who even posts this stuff")
    assert len(chat.calls) == 1  # ... and commands never reach the model
    e.handle(PHONE, "check")
    assert len(chat.calls) == 1


def test_partner_hint_and_history(engine):
    chat = FakeChat("Dates. Check the dates.")
    e = partner_engine(engine, chat)
    e.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    assert texts(e.handle(PHONE, "hint")) == "Dates. Check the dates."
    e.handle(PHONE, "still lost")
    _, turns = chat.calls[-1]
    assert ("assistant", "Dates. Check the dates.") in turns


@pytest.mark.parametrize("leaky", ["It's fake, obviously.", "That one's real.", "Classic misleading chart.",
                                   "The answer is doctored.", "I'd go with real on this one."])
def test_partner_never_gives_the_answer_before_you_answer(engine, leaky):
    from backend.imessage.partner import SAFE_HINT
    e = partner_engine(engine, FakeChat(leaky))
    e.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    assert texts(e.handle(PHONE, "just tell me")) == SAFE_HINT


def test_partner_explains_freely_after_the_reveal(engine):
    chat = FakeChat("It was a misleading chart: the axis starts at $2.10.")
    e = partner_engine(engine, chat)
    e.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    for pid in ["p1", "p2", "p3", "p4", "p5"]:
        e.handle(PHONE, "fake 0" if key()[pid]["doctored"] else "real")
    out = texts(e.handle(PHONE, "wait why was the egg one fake"))
    assert "misleading chart" in out  # no post pending -> no leak guard
    assert "LAST REVEALED POST" in chat.calls[-1][0]


def test_partner_failure_and_cap_fall_back(engine):
    e = partner_engine(engine, FakeChat(RuntimeError("down")))
    e.handle(PHONE, "hi", space_id="sp1", agent_id="ag1")
    assert "Didn't catch that" in texts(e.handle(PHONE, "hmm"))
    e2 = partner_engine(engine, FakeChat("ok"), cap=1)
    assert texts(e2.handle(PHONE, "hmm")) == "ok"
    assert "out of words" in texts(e2.handle(PHONE, "hmm again"))


def test_parse_hint():
    assert parse("hint", OPTS).kind == "hint"
    assert parse("I'm stuck", OPTS).kind == "hint"
    assert parse("help me", OPTS).kind == "hint"
    assert parse("help", OPTS).kind == "help"
