"""v2.1 (CONTRACT §8): Con levels, grid emoji, one made-up account per deck item, honest lines, live caps,
public mode, rarity bonus. No real model calls: judge_post is always a stand-in."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app import con_the_con as ctc
from backend.app.con_lines import NO_RECEIPTS
from backend.app.limits import RateLimiter, client_ip
from backend.app.main import create_app
from backend.app.scoring import share_grid

from .conftest import DEMO, load
from .test_v2 import CROP, DAY, QUOTE_ID, answer, deck, fool, judge, make_daily, new_player, set_today  # noqa: F401

USAGE = "con_live_usage.json"


def make_client(data_dir, tmp_path, **kw):
    return TestClient(create_app(data_dir=data_dir, frontend_dist=tmp_path / "no-dist", today=lambda: DAY, **kw))


def judge_lv(client, edit, level=None, player="judge01", headers=None, deck_id=QUOTE_ID):
    body = {"player_id": player, "deck_id": deck_id, "edit": edit}
    if level is not None:
        body["level"] = level
    return client.post("/api/fool/judge", json=body, headers=headers or {})


# ---- §8.1 Con levels ------------------------------------------------------------------------------

def test_levels_reach_the_judge_and_the_scoreboard(client, deck, fool):
    fool.verdict = "real"
    r1 = judge_lv(client, CROP, level=1).json()
    assert r1["level"] == 1 and r1["con"]["checked"] == [] and r1["outcome"] == "fooled_the_con"
    r2 = judge_lv(client, CROP, level=2).json()
    fool.verdict = "doctored"
    r3 = judge_lv(client, CROP).json()  # default: 3
    assert (r2["level"], r3["level"]) == (2, 3) and fool.levels == [1, 2, 3]
    assert r3["scoreboard"] == {"fooled": 2, "played": 3, "by_level": {
        "1": {"fooled": 1, "played": 1}, "2": {"fooled": 1, "played": 1}, "3": {"fooled": 0, "played": 1}}}
    rounds = client.get("/api/players/judge01").json()["fool_rounds"]
    assert [r["level"] for r in rounds] == [1, 2, 3]


def test_cache_key_includes_the_level(client, deck, fool, data_dir):
    judge_lv(client, CROP, level=1)
    judge_lv(client, CROP, level=3)
    assert len(fool.calls) == 2  # a level-1 verdict is not reused for level 3
    again = judge_lv(client, CROP, level=1).json()
    assert again["con"]["cached"] is True and again["con"]["checked"] == [] and len(fool.calls) == 2
    edited = again["edited_post"]
    keys = {ctc.cache_key(edited, deck[0]["evidence"], lv) for lv in (1, 2, 3)}
    assert len(keys) == 3
    assert {p.stem for p in (data_dir / "fool_cache").iterdir()} == {
        ctc.cache_key(edited, deck[0]["evidence"], 1), ctc.cache_key(edited, deck[0]["evidence"], 3)}


def test_a_cached_level3_verdict_is_never_served_as_level1(client, deck, fool, data_dir):
    judge_lv(client, CROP, level=3)
    edited = judge_lv(client, CROP, level=3).json()["edited_post"]
    # Even a stray file under the level-1 key that has a checked tool is not a valid level-1 verdict.
    (data_dir / "fool_cache" / f"{ctc.cache_key(edited, deck[0]['evidence'], 1)}.json").write_text(
        json.dumps({"checked": ["source"], "verdict": "doctored", "reasoning": ["x"], "model": "m"}), encoding="utf-8")
    r = judge_lv(client, CROP, level=1).json()
    assert r["con"]["cached"] is False and r["con"]["checked"] == []


@pytest.mark.parametrize("level", [0, 4, "3", 2.5])
def test_bad_level_is_422(client, deck, fool, level):
    assert judge_lv(client, CROP, level=level).status_code == 422
    assert fool.calls == []


def test_null_level_means_master_con(client, deck, fool):
    r = client.post("/api/fool/judge", json={"player_id": "p1", "deck_id": QUOTE_ID, "edit": CROP, "level": None})
    assert r.json()["level"] == 3


# ---- §8.4 Con the Con lines only say what happened -------------------------------------------------

@pytest.mark.parametrize("edit,verdict", [(CROP, "doctored"), (CROP, "real"), ({"type": "none"}, "doctored"),
                                          ({"type": "none"}, "real")])
def test_con_line_is_honest_about_the_level(client, deck, fool, edit, verdict):
    fool.verdict = verdict
    l1 = judge_lv(client, edit, level=1).json()["con_line"]
    assert "source" not in l1 and "checked " not in l1 and "One look" not in l1
    assert "without" in l1 or "looks alone" in l1
    l3 = judge_lv(client, edit, level=3).json()["con_line"]
    assert "the original source" in l3  # the one tool the (fake) Con opened
    if edit["type"] == "crop":
        assert "crop" in l1 and "crop" in l3
    else:
        assert "crop" not in l1 + l3 and "untouched" in (l1 + l3).lower()


def test_con_line_unit():
    assert "the real data" in ctc.con_line("caught", "axis", 2, ["data"]) and "axis" in ctc.con_line(
        "caught", "axis", 2, ["data"])
    assert "two-month window" in ctc.con_line("fooled_the_con", "window", 3, ["data"])
    assert "missing number" in ctc.con_line("caught", "drop", 1, [])
    assert "Master Con" in ctc.con_line("caught", "crop", 3, ["source"])


# ---- §8.2 grid ----------------------------------------------------------------------------------------

def test_grid_emoji():
    outcomes = ["trusted", "caught", "false_alarm", "fooled"]
    assert share_grid([{"outcome": o} for o in outcomes]) == "🟩🧂🟨🟥"


# ---- §8.3 one made-up account per deck item ---------------------------------------------------------

def test_deck_shows_the_edited_author_and_apply_edit_uses_it(client, deck, monkeypatch):
    """The real pipeline.fool (apply_edit, edited_author); only judge_post is a stand-in."""
    import pipeline.fool as real

    def fake_judge(edited_post, evidence, level=3):
        return {"checked": [] if level == 1 else ["source"], "verdict": "real", "trick_guess": None,
                "reasoning": ["Looks fine to me."], "confidence": 0.6, "model": "test/fake-con"}

    monkeypatch.setattr(real, "judge_post", fake_judge)
    items = {i["id"]: i for i in client.get("/api/fool/deck").json()}
    author = items[QUOTE_ID]["edited_author"]
    assert author == real.edited_author(deck[0])
    assert author["kind"] == "person" and author["verified"] is False
    assert author["handle"] != deck[0]["post"]["author"]["handle"]
    assert client.get("/api/fool/deck").json()[0]["edited_author"] == author  # stable
    r = judge_lv(client, CROP).json()
    assert r["changed"] is True and r["edited_post"]["author"] == author
    untouched = judge_lv(client, {"type": "none"}).json()
    assert untouched["edited_post"]["author"] == deck[0]["post"]["author"]


def test_deck_without_the_pipeline_still_loads(client, deck, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "pipeline.fool", None)
    body = client.get("/api/fool/deck").json()
    assert body[0]["edited_author"] is None and body[0]["id"] == QUOTE_ID


# ---- §8.4 honest daily lines --------------------------------------------------------------------------

def test_correct_without_evidence_gets_a_generic_line(client, player, daily_case, data_dir):
    ak = load(data_dir, daily_case, "answer_key.json")
    caught = answer(client, player, daily_case, "p2", True, "misleading-chart").json()["result"]
    assert caught["outcome"] == "caught" and caught["con_line"] in NO_RECEIPTS
    assert caught["tell"] == ak["posts"]["p2"]["tell"]  # the reveal itself is unchanged
    trusted = answer(client, player, daily_case, "p1", False).json()["result"]
    assert trusted["outcome"] == "trusted" and trusted["con_line"] in NO_RECEIPTS
    # Wrong answers keep the answer key's lines (they don't claim the player checked anything).
    fooled_player = new_player(client)
    fooled = answer(client, fooled_player, daily_case, "p2", False).json()["result"]
    assert fooled["con_line"] == ak["posts"]["p2"]["con_line_fooled"]
    # Opening evidence for the post first -> the answer key's line.
    checker = new_player(client)
    client.post(f"/api/cases/{daily_case}/evidence", json={"player_id": checker, "post_id": "p2", "tool": "data"})
    assert answer(client, checker, daily_case, "p2", True).json()["result"]["con_line"] == \
        ak["posts"]["p2"]["con_line_caught"]
    # Evidence for a DIFFERENT post doesn't count.
    assert answer(client, checker, daily_case, "p1", False).json()["result"]["con_line"] in NO_RECEIPTS

    # Resuming and the final verdict show the same lines as the reveal.
    state = client.get(f"/api/daily?player_id={player}").json()
    assert state["answered"]["p2"]["con_line"] == caught["con_line"]
    for pid in ("p3", "p4", "p5"):
        answer(client, player, daily_case, pid, False)
    res = {x["post_id"]: x for x in client.post(f"/api/cases/{daily_case}/verdict",
                                                json={"player_id": player}).json()["results"]}
    assert res["p2"]["con_line"] == caught["con_line"] and res["p1"]["con_line"] == trusted["con_line"]


def test_evidence_opened_after_answering_does_not_rewrite_the_line(client, player, daily_case):
    first = answer(client, player, daily_case, "p2", True).json()["result"]["con_line"]
    client.post(f"/api/cases/{daily_case}/evidence", json={"player_id": player, "post_id": "p2", "tool": "data"})
    for pid in ("p1", "p3", "p4", "p5"):
        answer(client, player, daily_case, pid, False)
    body = client.post(f"/api/cases/{daily_case}/verdict", json={"player_id": player}).json()
    assert body["results"][1]["con_line"] == first in NO_RECEIPTS


@pytest.fixture
def daily_case(data_dir, client):
    set_today(client, DAY)
    return make_daily(data_dir, "daily-1114", "2026-11-14")


# ---- §8.5 live caps -----------------------------------------------------------------------------------

def edits(n):
    """n different crops of the test quote (each a fresh cache key)."""
    return [{"type": "crop", "keep_word_indices": list(range(4 + i))} for i in range(n)]


def test_daily_cap_across_players(data_dir, tmp_path, deck, fool, monkeypatch):
    monkeypatch.setenv("CON_LIVE_DAILY_CAP", "2")
    client = make_client(data_dir, tmp_path)
    e = edits(3)
    assert judge(client, e[0], player="a1").status_code == 200
    assert judge(client, e[1], player="a2").status_code == 200
    r = judge(client, e[2], player="a3")
    assert r.status_code == 429
    assert r.json() == {"error": "con_resting",
                        "message": "The Con is resting. Try a saved round, or come back tomorrow."}
    assert len(fool.calls) == 2
    # Cached verdicts are always free and always allowed.
    again = judge(client, e[0], player="a3")
    assert again.status_code == 200 and again.json()["con"]["cached"] is True
    saved = json.loads((data_dir / "stats" / USAGE).read_text(encoding="utf-8"))
    assert saved == {"date": "2026-11-14", "live": 2, "demo": 0, "players": {"a1": 1, "a2": 1}}
    # Persisted: a restart doesn't hand out a fresh budget...
    restarted = make_client(data_dir, tmp_path)
    assert judge(restarted, e[2], player="a4").status_code == 429
    # ...but a new ET day does.
    nextday = TestClient(create_app(data_dir=data_dir, frontend_dist=tmp_path / "x", today=lambda: date(2026, 11, 15)))
    assert judge(nextday, e[2], player="a4").status_code == 200


def test_per_player_cap(data_dir, tmp_path, deck, fool, monkeypatch):
    monkeypatch.setenv("CON_LIVE_PER_PLAYER", "2")
    client = make_client(data_dir, tmp_path)
    e = edits(4)
    assert [judge(client, x, player="solo").status_code for x in e[:3]] == [200, 200, 429]
    assert judge(client, e[3], player="other").status_code == 200
    assert judge(client, e[0], player="solo").status_code == 200  # cached: still fine


def test_defaults_are_30_and_3(client):
    usage = client.app.state.live_usage
    assert (usage.daily_cap, usage.per_player) == (30, 3)


def test_failed_live_call_does_not_use_up_the_players_round(data_dir, tmp_path, deck, fool, monkeypatch):
    monkeypatch.setenv("CON_LIVE_PER_PLAYER", "1")
    client = make_client(data_dir, tmp_path)
    fool.asleep = True
    assert judge(client, CROP, player="unlucky").status_code == 503
    fool.asleep = False
    assert judge(client, CROP, player="unlucky").status_code == 200
    assert judge(client, edits(1)[0], player="unlucky").status_code == 429


def test_demo_token_skips_both_caps(data_dir, tmp_path, deck, fool, monkeypatch):
    monkeypatch.setenv("CON_LIVE_DAILY_CAP", "1")
    monkeypatch.setenv("CON_LIVE_PER_PLAYER", "1")
    monkeypatch.setenv("DEMO_TOKEN", "s3cret-demo")
    client = make_client(data_dir, tmp_path)
    e = edits(4)
    assert judge(client, e[0]).status_code == 200
    assert judge_lv(client, e[1]).status_code == 429
    assert judge_lv(client, e[1], headers={"X-Demo-Token": "wrong"}).status_code == 429
    ok = [judge_lv(client, x, headers={"X-Demo-Token": "s3cret-demo"}).status_code for x in e[1:]]
    assert ok == [200, 200, 200]
    assert client.app.state.live_usage.snapshot()["demo"] == 3  # counted, but not against the public cap


def test_no_demo_token_configured_means_no_bypass(data_dir, tmp_path, deck, fool, monkeypatch):
    monkeypatch.setenv("CON_LIVE_DAILY_CAP", "0")
    client = make_client(data_dir, tmp_path)
    assert judge_lv(client, CROP, headers={"X-Demo-Token": ""}).status_code == 429


# ---- §8.6 public mode -----------------------------------------------------------------------------------

DOCS = ("/docs", "/redoc", "/openapi.json")


def test_local_mode_unchanged(client):
    for path in DOCS:
        assert client.get(path).status_code == 200, path
    assert client.get("/api/editor/queue").status_code == 200
    assert client.get("/api/editor/queue", headers={"X-Editor-Token": "nope"}).status_code == 200


def test_public_mode_hides_docs(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("GOS_PUBLIC", "1")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
    client = TestClient(create_app(data_dir=data_dir, frontend_dist=dist))
    for path in (*DOCS, "/docs/oauth2-redirect"):
        assert client.get(path).status_code == 404, path  # not even the SPA fallback
    assert client.get("/daily").status_code == 200  # the SPA itself still works
    assert client.get("/api/health").json() == {"ok": True}


def test_public_mode_without_editor_token_disables_editor_routes(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("GOS_PUBLIC", "1")
    client = make_client(data_dir, tmp_path)
    for prefix in ("/api/editor", "/api/teacher"):  # /api/teacher: hidden back-compat alias
        assert client.get(f"{prefix}/queue").status_code == 404
        assert client.get(f"{prefix}/cases/{DEMO}", headers={"X-Editor-Token": ""}).status_code == 404
        assert client.post(f"{prefix}/cases/{DEMO}/approve", json={}).status_code == 404


def editor_calls(prefix):
    return [("get", f"{prefix}/queue", None), ("get", f"{prefix}/cases/{DEMO}", None),
            ("post", f"{prefix}/cases/{DEMO}/reject", {"reason": "x"}),
            ("post", f"{prefix}/cases/{DEMO}/approve", {})]


def test_public_mode_editor_token(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("GOS_PUBLIC", "1")
    monkeypatch.setenv("EDITOR_TOKEN", "editor-desk-42")
    client = make_client(data_dir, tmp_path)
    good = {"X-Editor-Token": "editor-desk-42"}
    for method, path, body in editor_calls("/api/editor"):
        call = getattr(client, method)
        kw = {"json": body} if body is not None else {}
        assert call(path, **kw).status_code == 401, path
        assert call(path, headers={"X-Editor-Token": "editor-desk-4"}, **kw).status_code == 401, path
        assert call(path, headers=good, **kw).status_code == 200, path
    assert client.get("/api/editor/cases/..%2Fx").status_code in (401, 404)


# Back-compat: TEACHER_TOKEN / X-Teacher-Token / /api/teacher/* are the old names and still work.

@pytest.mark.parametrize("prefix", ["/api/editor", "/api/teacher"])
@pytest.mark.parametrize("header", ["X-Editor-Token", "X-Teacher-Token"])
def test_public_mode_accepts_old_token_header_and_old_paths(data_dir, tmp_path, monkeypatch, prefix, header):
    monkeypatch.setenv("GOS_PUBLIC", "1")
    monkeypatch.setenv("EDITOR_TOKEN", "editor-desk-42")
    client = make_client(data_dir, tmp_path)
    for method, path, body in editor_calls(prefix):
        call = getattr(client, method)
        kw = {"json": body} if body is not None else {}
        assert call(path, **kw).status_code == 401, path
        assert call(path, headers={header: "editor-desk-4"}, **kw).status_code == 401, path
        assert call(path, headers={header: "editor-desk-42"}, **kw).status_code == 200, path


def test_old_teacher_token_env_is_a_fallback(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("GOS_PUBLIC", "1")
    monkeypatch.setenv("TEACHER_TOKEN", "old-name-7")
    client = make_client(data_dir, tmp_path)
    assert client.get("/api/editor/queue").status_code == 401
    assert client.get("/api/editor/queue", headers={"X-Editor-Token": "old-name-7"}).status_code == 200


def test_editor_token_env_wins_over_the_old_name(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("GOS_PUBLIC", "1")
    monkeypatch.setenv("EDITOR_TOKEN", "new-name-9")
    monkeypatch.setenv("TEACHER_TOKEN", "old-name-7")
    client = make_client(data_dir, tmp_path)
    assert client.get("/api/editor/queue", headers={"X-Editor-Token": "new-name-9"}).status_code == 200
    assert client.get("/api/editor/queue", headers={"X-Editor-Token": "old-name-7"}).status_code == 401


def test_public_mode_rate_limits_answers_per_ip(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("GOS_PUBLIC", "1")
    monkeypatch.setenv("ANSWER_RATE_PER_MIN", "3")
    client = make_client(data_dir, tmp_path)
    ip = {"CF-Connecting-IP": "203.0.113.7"}
    codes = [answer_h(client, new_player(client), "p1", ip).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert answer_h(client, new_player(client), "p1", {"CF-Connecting-IP": "203.0.113.8"}).status_code == 200
    # X-Forwarded-For: keyed on the rightmost entry (the one the proxy added), so a client can't rotate it.
    for spoof in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
        assert answer_h(client, new_player(client), "p1", {"X-Forwarded-For": f"{spoof}, 198.51.100.4"}).status_code \
            == 200
    assert answer_h(client, new_player(client), "p1", {"X-Forwarded-For": "9.9.9.9, 198.51.100.4"}).status_code == 429


def test_rate_limit_off_locally(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("ANSWER_RATE_PER_MIN", "1")
    client = make_client(data_dir, tmp_path)
    assert [answer_h(client, new_player(client), "p1", {}).status_code for _ in range(3)] == [200, 200, 200]


def answer_h(client, player, post_id, headers):
    return client.post(f"/api/cases/{DEMO}/answer", headers=headers,
                       json={"player_id": player, "post_id": post_id, "doctored": False, "trick": None})


def test_rate_limiter_window():
    now = [0.0]
    rl = RateLimiter(limit=2, window_s=60, clock=lambda: now[0])
    assert [rl.allow("a"), rl.allow("a"), rl.allow("a"), rl.allow("b")] == [True, True, False, True]
    now[0] = 60.0
    assert rl.allow("a") is True


def test_client_ip_order():
    class Req:
        def __init__(self, headers, host="10.0.0.1"):
            self.headers, self.client = headers, type("C", (), {"host": host})()

    assert client_ip(Req({"cf-connecting-ip": "1.2.3.4", "x-forwarded-for": "5.6.7.8"})) == "1.2.3.4"
    assert client_ip(Req({"x-forwarded-for": "5.6.7.8, 9.9.9.9 "})) == "9.9.9.9"
    assert client_ip(Req({})) == "10.0.0.1"


# ---- §8.7 rarity bonus -----------------------------------------------------------------------------------

def seed_stats(data_dir, case_id, post_id, n, correct):
    path = data_dir / "stats" / f"{case_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"posts": {}}
    stats["posts"][post_id] = {"n": n, "said_doctored": 0, "correct": correct}
    path.write_text(json.dumps(stats), encoding="utf-8")


@pytest.fixture
def rare(data_dir, tmp_path):
    client = make_client(data_dir, tmp_path, crowd_min=10)
    case_id = make_daily(data_dir, "daily-1114", "2026-11-14")
    seed_stats(data_dir, case_id, "p2", n=20, correct=2)   # 10% -> One in a shaker
    seed_stats(data_dir, case_id, "p1", n=20, correct=5)   # 25% -> Rare catch
    seed_stats(data_dir, case_id, "p3", n=20, correct=6)   # 30% -> none
    seed_stats(data_dir, case_id, "p4", n=9, correct=0)    # 0%, but n < CROWD_MIN before this answer -> none
    return client, case_id


def test_rarity_bonus_on_answers_and_in_the_score(rare):
    client, case_id = rare
    player = new_player(client)
    got = {}
    for pid, doctored, trick in [("p1", False, None), ("p2", True, "misleading-chart"), ("p3", False, None),
                                 ("p4", False, None), ("p5", False, None)]:
        got[pid] = answer(client, player, case_id, pid, doctored, trick).json()["result"]
    assert got["p2"]["rarity_bonus"] == {"label": "One in a shaker", "points": 100}
    assert got["p1"]["rarity_bonus"] == {"label": "Rare catch", "points": 50}
    assert got["p3"]["rarity_bonus"] is None
    assert got["p4"]["rarity_bonus"] is None  # 9 earlier answers: below CROWD_MIN (10), never faked
    assert got["p5"]["rarity_bonus"] is None  # no stats at all
    assert got["p2"]["points"] == 150  # the card's own points; the bonus is separate...
    body = client.post(f"/api/cases/{case_id}/verdict", json={"player_id": player}).json()
    res = {x["post_id"]: x for x in body["results"]}
    assert res["p2"]["rarity_bonus"]["points"] == 100 and res["p1"]["rarity_bonus"]["points"] == 50
    assert res["p3"]["rarity_bonus"] is None
    assert body["score"] == 550 + 60 + 150  # ...and counts toward the score
    state = client.get(f"/api/daily?player_id={player}").json()
    assert state["result"]["score"] == body["score"]


def test_no_rarity_bonus_for_a_wrong_answer(rare):
    client, case_id = rare
    player = new_player(client)
    r = answer(client, player, case_id, "p2", False).json()["result"]
    assert r["outcome"] == "fooled" and r["rarity_bonus"] is None


def test_rarity_uses_stats_from_before_this_answer(rare, data_dir):
    client, case_id = rare
    # First answer on p4 makes n = 10 (>= CROWD_MIN) but the bonus looks at the 9 before it.
    assert answer(client, new_player(client), case_id, "p4", False).json()["result"]["rarity_bonus"] is None
    # Now 10 earlier answers, 1 correct (10%): the next correct answer is a One in a shaker.
    assert answer(client, new_player(client), case_id, "p4", False).json()["result"]["rarity_bonus"] == \
        {"label": "One in a shaker", "points": 100}


def test_rarity_bonus_in_a_one_shot_verdict(data_dir, tmp_path):
    client = make_client(data_dir, tmp_path, crowd_min=3)
    seed_stats(data_dir, DEMO, "p2", n=10, correct=2)  # 20% -> Rare catch
    player = new_player(client)
    v = {"p1": {"doctored": False}, "p2": {"doctored": True, "trick": "misleading-chart"},
         "p3": {"doctored": False}, "p4": {"doctored": False}}
    body = client.post(f"/api/cases/{DEMO}/verdict", json={"player_id": player, "verdicts": v}).json()
    assert body["results"][1]["rarity_bonus"] == {"label": "Rare catch", "points": 50}
    assert body["score"] == 450 + 60 + 50
    v["p2"] = {"doctored": False}
    body = client.post(f"/api/cases/{DEMO}/verdict", json={"player_id": player, "verdicts": v}).json()
    assert body["results"][1]["rarity_bonus"] is None and body["score"] == 300 + 60
