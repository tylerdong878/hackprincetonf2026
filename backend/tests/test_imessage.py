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
    ("what is this", "unknown", None),
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
    assert engine.due_nudges(DAY) == []  # once a day


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
