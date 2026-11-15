"""v2: the Daily Grain, per-card answers, crowd stats, lean, streaks, share text, Con the Con."""
import copy
import hashlib
import json
import shutil
import sys
import types
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app.daily import streak
from backend.app.main import create_app
from backend.app.scoring import lean, lean_label

from .conftest import DEMO, load, save, submit, verdicts
from .test_api import _dump, _keys, answer_strings, evidence_strings

DAY = date(2026, 11, 14)
PERFECT5 = verdicts(real=["p1", "p3", "p4", "p5"], doctored={"p2": "misleading-chart"})


def make_daily(data_dir, case_id, daily_date, status="approved", **meta_extra):
    """A 5-card daily built from the seed demo case (p5 = a second copy of the real p4)."""
    dst = data_dir / "cases" / case_id
    shutil.copytree(data_dir / "cases" / DEMO, dst)
    case = load(data_dir, case_id, "case.json")
    case["id"], case["briefing"] = case_id, "Five cards. 0–3 doctored today."
    case["posts"].append(dict(copy.deepcopy(case["posts"][3]), id="p5"))
    save(data_dir, case_id, "case.json", case)
    ak = load(data_dir, case_id, "answer_key.json")
    ak["posts"]["p5"] = copy.deepcopy(ak["posts"]["p4"])
    save(data_dir, case_id, "answer_key.json", ak)
    ev = load(data_dir, case_id, "evidence.json")
    ev["p5"] = copy.deepcopy(ev["p4"])
    save(data_dir, case_id, "evidence.json", ev)
    meta = load(data_dir, case_id, "meta.json")
    meta.update(status=status, daily=False, mode="daily", daily_date=daily_date, theme="Your Bills", **meta_extra)
    save(data_dir, case_id, "meta.json", meta)
    return case_id


def set_today(client, d):
    client.app.state.today = lambda: d


def answer(client, player, case_id, post_id, doctored, trick=None):
    return client.post(f"/api/cases/{case_id}/answer",
                       json={"player_id": player, "post_id": post_id, "doctored": doctored, "trick": trick})


def new_player(client):
    return client.post("/api/players", json={}).json()["player_id"]


@pytest.fixture
def daily(data_dir, client):
    set_today(client, DAY)
    return make_daily(data_dir, "daily-1114", "2026-11-14")


# ---- daily selection ----------------------------------------------------------

def test_daily_selection_by_date(client, data_dir):
    make_daily(data_dir, "d13", "2026-11-13")
    make_daily(data_dir, "d14", "2026-11-14")
    make_daily(data_dir, "d16", "2026-11-16")
    make_daily(data_dir, "d12-draft", "2026-11-12", status="awaiting_approval")

    set_today(client, date(2026, 11, 14))
    body = client.get("/api/daily").json()
    assert body["case"]["id"] == "d14" and body["date"] == "2026-11-14" and body["daily_number"] == 2
    assert body["theme"] == "Your Bills" and body["already_played"] is False and body["result"] is None
    assert len(body["case"]["posts"]) == 5 and all("card_style" in p for p in body["case"]["posts"])

    set_today(client, date(2026, 11, 15))  # no daily today -> latest one before today
    assert client.get("/api/daily").json()["case"]["id"] == "d14"
    assert client.get("/api/cases/d16").status_code == 404  # no peeking at tomorrow
    archive = client.get("/api/daily/archive").json()
    assert archive == [
        {"date": "2026-11-14", "daily_number": 2, "title": archive[0]["title"], "theme": "Your Bills", "case_id": "d14"},
        {"date": "2026-11-13", "daily_number": 1, "title": archive[1]["title"], "theme": "Your Bills", "case_id": "d13"},
    ]

    set_today(client, date(2026, 11, 16))
    assert client.get("/api/daily").json()["daily_number"] == 4  # days since launch: Nov 15 has no puzzle, so Nov 16 is #4
    assert client.get("/api/cases/d16").status_code == 200

    set_today(client, date(2026, 11, 12))  # the only one dated <= today is a draft
    assert client.get("/api/daily").status_code == 404
    # Dailies stay out of the Case Files list.
    assert all(not c["id"].startswith("d1") for c in client.get("/api/cases").json())


def test_daily_numbers_count_days_since_launch_so_gaps_never_renumber(client, data_dir, monkeypatch):
    monkeypatch.delenv("GOS_LAUNCH_DATE", raising=False)
    make_daily(data_dir, "d13", "2026-11-13")
    make_daily(data_dir, "d16", "2026-11-16")  # Nov 14 and 15 have no puzzle yet
    set_today(client, date(2026, 11, 16))
    assert client.get("/api/daily").json()["daily_number"] == 4
    archive = {a["case_id"]: a["daily_number"] for a in client.get("/api/daily/archive").json()}
    assert archive == {"d16": 4, "d13": 1}


def test_launch_date_can_be_pinned(client, data_dir, monkeypatch):
    monkeypatch.setenv("GOS_LAUNCH_DATE", "2026-11-10")
    make_daily(data_dir, "d14", "2026-11-14")
    set_today(client, date(2026, 11, 14))
    assert client.get("/api/daily").json()["daily_number"] == 5


def test_daily_number_override(client, data_dir):
    make_daily(data_dir, "d14", "2026-11-14", daily_number=12)
    set_today(client, DAY)
    assert client.get("/api/daily").json()["daily_number"] == 12


# ---- per-card answers ---------------------------------------------------------

def test_answer_reveals_at_once_and_409_on_repeat(client, player, daily, data_dir):
    ak = load(data_dir, daily, "answer_key.json")
    client.post(f"/api/cases/{daily}/evidence", json={"player_id": player, "post_id": "p2", "tool": "data"})
    r = answer(client, player, daily, "p2", True, "misleading-chart")
    assert r.status_code == 200
    body = r.json()
    res = body["result"]
    assert res["outcome"] == "caught" and res["points"] == 150 and res["trick_named_correctly"] is True
    assert res["tell"] == ak["posts"]["p2"]["tell"] and res["con_line"] == ak["posts"]["p2"]["con_line_caught"]
    assert res["rarity"] is None and body["crowd"] is None  # 1 answer < CROWD_MIN (10)
    assert body["clues_left"] == 2

    assert answer(client, player, daily, "p2", False).status_code == 409
    assert answer(client, player, daily, "p9", False).status_code == 404
    fa = answer(client, player, daily, "p3", True, "cherry-picked-stat").json()["result"]
    assert fa["outcome"] == "false_alarm" and fa["con_line"] == ak["posts"]["p3"]["con_line_false_alarm"]

    # /daily lets a reloaded page resume: answered cards come back revealed, the rest stay hidden.
    state = client.get(f"/api/daily?player_id={player}").json()
    assert set(state["answered"]) == {"p2", "p3"} and state["clues_left"] == 2


def test_crowd_stats_only_from_crowd_min(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("CROWD_MIN", "7")
    assert create_app(data_dir=data_dir).state.crowd_min == 7
    client = TestClient(create_app(data_dir=data_dir, frontend_dist=tmp_path / "x", today=lambda: DAY, crowd_min=3))
    case_id = make_daily(data_dir, "daily-1114", "2026-11-14")
    said = [True, True, False]
    bodies = [answer(client, new_player(client), case_id, "p2", s, "misleading-chart").json() for s in said]
    assert bodies[0]["crowd"] is None and bodies[1]["crowd"] is None
    assert bodies[1]["result"]["rarity"] is None
    assert bodies[2]["crowd"] == {"said_doctored_pct": 67, "correct_pct": 67, "n": 3}
    assert bodies[2]["result"]["rarity"] == {"correct_pct": 67, "n": 3}
    stats = json.loads((data_dir / "stats" / f"{case_id}.json").read_text(encoding="utf-8"))
    assert stats == {"posts": {"p2": {"n": 3, "said_doctored": 2, "correct": 2}}}


# ---- verdict from recorded answers ----------------------------------------------------

def test_verdict_from_recorded_answers(client, player, daily):
    for pid, v in PERFECT5.items():
        answer(client, player, daily, pid, v["doctored"], v["trick"])
    # Recorded answers win over a different verdict sent at the end.
    r = client.post(f"/api/cases/{daily}/verdict", json={"player_id": player, "verdicts": {"p2": {"doctored": False}}})
    assert r.status_code == 200
    body = r.json()
    assert [x["outcome"] for x in body["results"]] == ["trusted", "caught", "trusted", "trusted", "trusted"]
    assert body["score"] == 550 + 60 and body["daily_number"] == 1 and body["streak"] == 1

    state = client.get(f"/api/daily?player_id={player}").json()
    assert state["already_played"] is True and state["result"] == body
    # One play per daily: the same stored result comes back, nothing is counted twice.
    again = client.post(f"/api/cases/{daily}/verdict", json={"player_id": player})
    assert again.json() == body
    assert len(client.get(f"/api/players/{player}").json()["history"]) == 1
    assert answer(client, player, daily, "p1", True).status_code == 409


def test_verdict_without_answers_is_422(client, player, daily):
    assert client.post(f"/api/cases/{daily}/verdict", json={"player_id": player}).status_code == 422
    answer(client, player, daily, "p1", False)
    r = client.post(f"/api/cases/{daily}/verdict", json={"player_id": player})
    assert r.status_code == 422 and "p2" in r.json()["detail"]


def test_case_files_still_work_with_answers_and_replay(client, player):
    for pid, v in verdicts(real=["p1", "p3", "p4"], doctored={"p2": "misleading-chart"}).items():
        assert answer(client, player, DEMO, pid, v["doctored"], v["trick"]).status_code == 200
    body = client.post(f"/api/cases/{DEMO}/verdict", json={"player_id": player}).json()
    assert body["daily_number"] is None and body["streak"] == 0
    assert body["share_text"] == "Grain of Salt Case #0001 🧂 4/4\n🟩🧂🟩🟩\nBalanced detective"
    # Case Files can be replayed: answers are cleared after the verdict.
    assert answer(client, player, DEMO, "p1", False).status_code == 200


# ---- lean, streak, share text --------------------------------------------------------

@pytest.mark.parametrize("value,label", [
    (-1, "Gullible"), (-0.5, "Gullible"), (-0.49, "Trusting"), (-0.15, "Trusting"), (-0.14, "Balanced"),
    (0, "Balanced"), (0.149, "Balanced"), (0.15, "Suspicious"), (0.49, "Suspicious"), (0.5, "Paranoid"), (1, "Paranoid"),
])
def test_lean_labels(value, label):
    assert lean_label(value) == label


def test_lean_formula():
    real = lambda o: {"doctored": False, "outcome": o}  # noqa: E731
    fake = lambda o: {"doctored": True, "outcome": o}   # noqa: E731
    assert lean([]) == 0
    assert lean([fake("fooled"), real("trusted")]) == -1
    assert lean([fake("caught"), real("false_alarm")]) == 1
    assert lean([fake("fooled"), fake("caught"), real("false_alarm"), real("trusted"), real("trusted"), real("trusted")]) == -0.25
    assert lean([real("false_alarm")] * 40 + [real("trusted")] * 30) == 0  # last 30 only


def test_lean_in_verdict(client, daily):
    gullible = new_player(client)
    body = submit(client, gullible, daily, verdicts(real=["p1", "p2", "p3", "p4", "p5"])).json()
    assert body["lean"] == -1 and body["lean_label"] == "Gullible"
    paranoid = new_player(client)
    body = submit(client, paranoid, daily, verdicts(doctored={p: None for p in ["p1", "p2", "p3", "p4", "p5"]})).json()
    assert body["lean"] == 1 and body["lean_label"] == "Paranoid"
    assert client.get(f"/api/players/{paranoid}").json()["lean_label"] == "Paranoid"


def test_streak_unit():
    t = date(2026, 11, 14)
    assert streak([], t) == 0
    assert streak(["2026-11-14"], t) == 1
    assert streak(["2026-11-13"], t) == 1                      # not played yet today: still alive
    assert streak(["2026-11-12", "2026-11-13", "2026-11-14"], t) == 3
    assert streak(["2026-11-10", "2026-11-13", "2026-11-14"], t) == 2
    assert streak(["2026-11-11"], t) == 0


def test_streak_counts_days_played(client, player, data_dir):
    for cid, d in [("d13", "2026-11-13"), ("d14", "2026-11-14"), ("d16", "2026-11-16")]:
        make_daily(data_dir, cid, d)
    set_today(client, date(2026, 11, 13))
    assert submit(client, player, "d13", verdicts(real=["p1", "p2", "p3", "p4", "p5"])).json()["streak"] == 1
    set_today(client, date(2026, 11, 14))  # a bad day still counts: streaks are forgiving
    body = submit(client, player, "d14", verdicts(doctored={p: None for p in ["p1", "p2", "p3", "p4", "p5"]})).json()
    assert body["streak"] == 2
    set_today(client, date(2026, 11, 16))  # skipped the 15th
    assert submit(client, player, "d16", PERFECT5).json()["streak"] == 1
    assert client.get(f"/api/players/{player}").json()["daily_played"] == ["2026-11-13", "2026-11-14", "2026-11-16"]


def test_share_text_v2(client, player, daily, data_dir):
    body = submit(client, player, daily, PERFECT5).json()
    assert body["share_grid"] == "🟩🧂🟩🟩🟩"
    assert body["share_text"] == "Grain of Salt #1 🧂 5/5 🔥1\n🟩🧂🟩🟩🟩\nBalanced detective"
    other = new_player(client)
    v = verdicts(real=["p1", "p2", "p4", "p5"], doctored={"p3": None})
    assert submit(client, other, daily, v).json()["share_grid"] == "🟩🟥🟨🟩🟩"  # §8.2 grid
    case = load(data_dir, daily, "case.json")
    for p in case["posts"]:  # never any post content
        for text in [p["body"], (p.get("quote") or {}).get("text", "")]:
            assert not text or text not in body["share_text"]


# ---- no answer leakage ------------------------------------------------------------------

def test_no_answer_leakage_in_daily(client, player, daily, data_dir):
    forbidden = answer_strings(data_dir, daily) | evidence_strings(data_dir, daily)
    bad_keys = {"doctored", "trick", "tell", "explanation", "con_line", "diff", "suspicious_real",
                "clean_case", "answer_key", "evidence", "tricks", "meta"}
    for r in [client.get("/api/daily"), client.get(f"/api/daily?player_id={player}"), client.get("/api/daily/archive")]:
        assert r.status_code == 200
        text = _dump(r.json())
        assert not (set(_keys(r.json())) & bad_keys)
        for s in forbidden:
            assert s not in text, s[:60]


# ---- Con the Con ------------------------------------------------------------------------

QUOTE_ID, CHART_ID = "hs-net-increase", "nj-price-chart"


@pytest.fixture
def deck(data_dir):
    case, ev = load(data_dir, DEMO, "case.json"), load(data_dir, DEMO, "evidence.json")
    d = data_dir / "fool_deck"
    d.mkdir()
    quote_post = copy.deepcopy(case["posts"][0])
    items = [
        {"id": QUOTE_ID, "kind": "quote", "post": quote_post, "evidence": {"source": ev["p1"]["source"]},
         "editable": {"quote_words": quote_post["quote"]["text"].split()}, "tools": ["crop"]},
        {"id": CHART_ID, "kind": "chart", "post": copy.deepcopy(case["posts"][1]),
         "evidence": {"data": ev["p2"]["data"]},
         "editable": {"chart_series": ev["p2"]["data"]["table"]}, "tools": ["axis", "window"]},
    ]
    for item in items:
        (d / f"{item['id']}.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
    return items


@pytest.fixture
def fool(monkeypatch):
    """A stand-in for pipeline/fool.py: deterministic apply_edit, scripted judge_post."""
    mod = types.ModuleType("pipeline.fool")

    class ConAsleep(Exception):
        pass

    mod.ConAsleep, mod.calls, mod.levels, mod.verdict, mod.asleep = ConAsleep, [], [], "doctored", False

    def edited_author(item):
        return {"name": "Garden State Truths", "handle": "@gstruths", "kind": "person",
                "verified": False, "avatar_color": "#777777"}

    def apply_edit(item, edit):
        post = copy.deepcopy(item["post"])
        if edit["type"] == "none":
            return {"edited_post": post, "changed": False, "trick": None, "diff": None}
        if edit["type"] == "crop":
            words, keep = item["editable"]["quote_words"], edit.get("keep_word_indices") or []
            if len(keep) < 4 or keep != sorted(set(keep)) or keep[0] < 0 or keep[-1] >= len(words):
                raise ValueError("A crop keeps at least 4 words, in order.")
            post["quote"]["text"] = " ".join(words[i] for i in keep)
            post["author"] = edited_author(item)
            diff = {"type": "quote", "shown": post["quote"]["text"], "original": item["post"]["quote"]["text"],
                    "removed": [w for i, w in enumerate(words) if i not in keep]}
            return {"edited_post": post, "changed": True, "trick": "out-of-context-quote", "diff": diff}
        raise ValueError("unsupported edit")

    def judge_post(edited_post, evidence, level=3):
        mod.calls.append(edited_post)
        mod.levels.append(level)
        if mod.asleep:
            raise ConAsleep("no key")
        return {"checked": [] if level == 1 else ["source"], "verdict": mod.verdict,
                "trick_guess": "out-of-context-quote" if mod.verdict == "doctored" else None,
                "reasoning": ["The source keeps going.", "The cut changes the meaning."],
                "confidence": 0.8, "model": "test/fake-con"}

    mod.apply_edit, mod.judge_post, mod.edited_author = apply_edit, judge_post, edited_author
    monkeypatch.setitem(sys.modules, "pipeline.fool", mod)
    return mod


CROP = {"type": "crop", "keep_word_indices": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}


def judge(client, edit, deck_id=QUOTE_ID, player="judge01"):
    return client.post("/api/fool/judge", json={"player_id": player, "deck_id": deck_id, "edit": edit})


def test_fool_deck_hides_evidence(client, deck):
    body = client.get("/api/fool/deck").json()
    assert [i["id"] for i in body] == [QUOTE_ID, CHART_ID]
    assert set(body[0]) == {"id", "kind", "post", "tools", "editable", "edited_author"} and body[0]["tools"] == ["crop"]
    assert body[0]["post"]["card_style"] == "quote"
    assert "evidence" not in set(_keys(body))
    text = _dump(body)
    for item in deck:
        visible = _dump([item["post"], item["editable"]])
        for s in evidence_strings_of(item["evidence"]):
            if s not in visible:
                assert s not in text, s[:60]


def evidence_strings_of(obj):
    if isinstance(obj, str):
        return {obj} if len(obj) >= 12 else set()
    if isinstance(obj, dict):
        return set().union(*[evidence_strings_of(v) for v in obj.values()]) if obj else set()
    if isinstance(obj, list):
        return set().union(*[evidence_strings_of(v) for v in obj]) if obj else set()
    return set()


@pytest.mark.parametrize("edit,verdict,expected,win", [
    (CROP, "doctored", "caught", False),
    (CROP, "real", "fooled_the_con", True),
    ({"type": "none"}, "doctored", "con_false_alarm", True),
    ({"type": "none"}, "real", "con_trusted", False),
])
def test_fool_judge_outcomes(client, deck, fool, edit, verdict, expected, win):
    fool.verdict = verdict
    r = judge(client, edit)
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == expected and isinstance(body["con_line"], str) and body["con_line"]
    assert body["changed"] is (edit["type"] != "none")
    assert body["con"]["verdict"] == verdict and body["con"]["cached"] is False
    assert body["con"]["model"] == "test/fake-con" and body["con"]["reasoning"]
    assert body["level"] == 3 and fool.levels == [3]  # default: Master Con
    assert body["scoreboard"]["fooled"] == int(win) and body["scoreboard"]["played"] == 1
    assert body["scoreboard"]["by_level"]["3"] == {"fooled": int(win), "played": 1}
    if edit["type"] == "crop":
        assert body["trick"] == "out-of-context-quote" and body["diff"]["type"] == "quote"
        assert body["edited_post"]["author"]["handle"] == "@gstruths"


def test_fool_judge_cache(client, deck, fool, data_dir):
    first = judge(client, CROP).json()
    second = judge(client, CROP).json()
    assert first["con"]["cached"] is False and second["con"]["cached"] is True
    assert len(fool.calls) == 1
    assert {k: v for k, v in second["con"].items() if k != "cached"} == \
        {k: v for k, v in first["con"].items() if k != "cached"}
    key = hashlib.sha256(json.dumps([first["edited_post"], deck[0]["evidence"]], sort_keys=True,
                                    separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    assert (data_dir / "fool_cache" / f"{key}.json").is_file()
    fool.asleep = True  # no key now, but the cached real verdict can still be shown
    assert judge(client, CROP).json()["con"]["cached"] is True


def test_fool_judge_con_asleep(client, deck, fool, monkeypatch, data_dir):
    fool.asleep = True
    r = judge(client, CROP)
    assert r.status_code == 503 and r.json() == {"error": "con_asleep"}
    fool.asleep, fool.verdict = False, "maybe"  # malformed model answer: never passed off as a verdict
    assert judge(client, CROP).status_code == 503
    assert not (data_dir / "fool_cache").exists() or not any((data_dir / "fool_cache").iterdir())
    monkeypatch.setitem(sys.modules, "pipeline.fool", None)  # module missing
    assert judge(client, {"type": "none"}).json() == {"error": "con_asleep"}


def test_fool_judge_illegal_edits(client, deck, fool):
    assert judge(client, {"type": "crop", "keep_word_indices": [0, 1]}).status_code == 422
    assert judge(client, {"type": "crop", "keep_word_indices": [5, 4, 3, 2, 1]}).status_code == 422
    assert judge(client, {"type": "axis", "y_min": 19}).status_code == 422          # not a tool for this post
    assert judge(client, {"type": "rewrite", "text": "anything"}).status_code == 422
    assert judge(client, CROP, deck_id="nope").status_code == 404
    assert judge(client, CROP, player="../x").status_code == 422
    assert fool.calls == []  # the Con never saw an illegal edit


def test_approving_a_daily_schedules_it_on_the_next_open_day(client, data_dir, monkeypatch):
    monkeypatch.delenv("GOS_LAUNCH_DATE", raising=False)
    make_daily(data_dir, "d15", "2026-11-15")  # already approved: today's puzzle, No. 1
    make_daily(data_dir, "d18", "2026-11-18", status="awaiting_approval")
    make_daily(data_dir, "d20", "2026-11-20", status="awaiting_approval")
    set_today(client, date(2026, 11, 15))
    assert client.post("/api/editor/cases/d20/approve").status_code == 200  # approved first -> next open day
    assert client.post("/api/editor/cases/d18/approve").status_code == 200
    q = {i["id"]: i for i in client.get("/api/editor/queue").json()}
    assert (q["d15"]["meta"]["daily_date"], q["d15"]["daily_number"]) == ("2026-11-15", 1)
    assert (q["d20"]["meta"]["daily_date"], q["d20"]["daily_number"]) == ("2026-11-16", 2)
    assert (q["d18"]["meta"]["daily_date"], q["d18"]["daily_number"]) == ("2026-11-17", 3)
    assert q["d20"]["meta"]["planned_date"] == "2026-11-20"  # the date the agents built it for is kept
    assert client.post("/api/editor/cases/d20/approve").json()["daily_date"] == "2026-11-16"  # re-approving keeps its day
