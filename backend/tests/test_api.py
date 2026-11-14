import json

from fastapi.testclient import TestClient

from backend.app.main import create_app

from .conftest import CLEAN, DEMO, load, save, submit, verdicts

ALL_REAL_DEMO = verdicts(real=["p1", "p2", "p3", "p4"])
PERFECT_DEMO = verdicts(real=["p1", "p3", "p4"], doctored={"p2": "misleading-chart"})


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False)


def answer_strings(data_dir, case_id):
    """Every reveal-only string in answer_key.json that isn't already visible in case.json."""
    case_text = _dump(load(data_dir, case_id, "case.json"))
    ak = load(data_dir, case_id, "answer_key.json")
    out = set()
    for key in ak["posts"].values():
        for f in ("tell", "explanation", "con_line_fooled", "con_line_caught", "con_line_false_alarm"):
            if key.get(f):
                out.add(key[f])
        diff = key.get("diff") or {}
        out |= {s for s in _strings(diff.get("original")) if len(s) >= 12 and s not in case_text}
    if ak.get("con_line_clean"):
        out.add(ak["con_line_clean"])
    return out


def evidence_strings(data_dir, case_id):
    case_text = _dump(load(data_dir, case_id, "case.json"))
    ev = load(data_dir, case_id, "evidence.json")
    return {s for s in _strings(ev) if len(s) >= 12 and s not in case_text}


# ---- basics ---------------------------------------------------------------

def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_cors_allows_vite_dev_server(client):
    r = client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                               "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_list_and_today(client):
    cases = client.get("/api/cases").json()
    assert [c["id"] for c in cases] == [DEMO, CLEAN]
    assert set(cases[0]) == {"id", "number", "title", "topic", "daily", "origin", "difficulty"}
    assert cases[0]["daily"] is True
    assert client.get("/api/cases/today").json()["id"] == DEMO
    assert client.get(f"/api/cases/{CLEAN}").json()["id"] == CLEAN
    assert client.get("/api/cases/nope").status_code == 404


# ---- no answer leakage ------------------------------------------------------

def test_no_answer_leakage_before_verdict(client, player, data_dir):
    forbidden_keys = {"doctored", "trick", "tell", "explanation", "con_line", "con_line_fooled",
                      "con_line_caught", "con_line_false_alarm", "con_line_clean", "diff",
                      "suspicious_real", "clean_case", "answer_key", "evidence", "tricks", "meta"}
    case_responses = [client.get("/api/cases"), client.get("/api/cases/today"),
                      client.get(f"/api/cases/next?player_id={player}"), client.get("/api/cases/next")]
    case_responses += [client.get(f"/api/cases/{cid}") for cid in (DEMO, CLEAN)]
    other = [client.post("/api/players", json={}), client.get(f"/api/players/{player}")]

    forbidden = set()
    for cid in (DEMO, CLEAN):
        forbidden |= answer_strings(data_dir, cid)
    assert any("axis starts at 19" in s for s in forbidden)  # the tell is in the list
    case_forbidden = forbidden | evidence_strings(data_dir, DEMO) | evidence_strings(data_dir, CLEAN)

    for r in case_responses:
        assert r.status_code == 200
        text = _dump(r.json())
        assert "doctored" not in text.lower()
        assert not (set(_keys(r.json())) & forbidden_keys)
        for s in case_forbidden:
            assert s not in text, f"leaked: {s[:60]}"
    for r in other:
        text = _dump(r.json())
        for s in forbidden:
            assert s not in text

    # Evidence is released on purpose, but it must never carry answer-key text.
    for post, tool in [("p2", "data"), ("p2", "account"), ("p1", "source")]:
        r = client.post(f"/api/cases/{DEMO}/evidence", json={"player_id": player, "post_id": post, "tool": tool})
        assert r.status_code == 200
        text = _dump(r.json())
        assert "doctored" not in text.lower()
        for s in forbidden:
            assert s not in text


def test_stray_answer_fields_in_case_json_are_stripped(client, data_dir):
    case = load(data_dir, DEMO, "case.json")
    case["answer_key"] = {"p2": "doctored"}
    case["posts"][1]["doctored"] = True
    case["posts"][1]["trick"] = "misleading-chart"
    case["posts"][1]["author"]["fictional"] = True
    save(data_dir, DEMO, "case.json", case)
    body = client.get(f"/api/cases/{DEMO}").json()
    text = _dump(body)
    assert "doctored" not in text and "fictional" not in text
    assert set(body["posts"][1]) == {"id", "author", "posted_at", "body", "quote", "chart", "source_label", "tools",
                                      "card_style"}
    assert body["posts"][1]["card_style"] == "chart"


# ---- evidence ----------------------------------------------------------------

def test_evidence_budget_reopen_and_409(client, player):
    def open_(post, tool, pid=player, case=DEMO):
        return client.post(f"/api/cases/{case}/evidence", json={"player_id": pid, "post_id": post, "tool": tool})

    r = open_("p2", "data")
    assert r.status_code == 200
    assert r.json()["clues_left"] == 2
    assert r.json()["evidence"]["table"][0]["label"] == "2025-01"
    assert open_("p1", "source").json()["clues_left"] == 1
    assert open_("p2", "account").json()["clues_left"] == 0
    again = open_("p2", "data")  # re-opening is free
    assert again.status_code == 200 and again.json()["clues_left"] == 0
    assert again.json()["evidence"] == r.json()["evidence"]
    assert open_("p3", "source").status_code == 409

    assert open_("p1", "data").status_code == 404  # tool not in this post's tools
    assert open_("p9", "source").status_code == 404
    assert client.post("/api/cases/nope/evidence", json={"player_id": player, "post_id": "p1", "tool": "source"}).status_code == 404

    # Budgets are per (player, case).
    assert open_("p1", "source", case=CLEAN).json()["clues_left"] == 2
    other = client.post("/api/players", json={}).json()["player_id"]
    assert open_("p3", "source", pid=other).json()["clues_left"] == 2


# ---- verdict scoring -----------------------------------------------------------

def test_perfect_demo_with_trick_bonus_and_clue_bonus(client, player, data_dir):
    ak = load(data_dir, DEMO, "answer_key.json")
    r = submit(client, player, DEMO, PERFECT_DEMO)
    assert r.status_code == 200
    body = r.json()
    res = {x["post_id"]: x for x in body["results"]}
    assert [x["post_id"] for x in body["results"]] == ["p1", "p2", "p3", "p4"]
    assert [x["outcome"] for x in body["results"]] == ["trusted", "caught", "trusted", "trusted"]
    assert res["p2"]["points"] == 150
    assert res["p2"]["trick_named_correctly"] is True
    assert res["p2"]["trick"] == "misleading-chart"
    assert res["p2"]["tell"] == ak["posts"]["p2"]["tell"]
    assert res["p2"]["con_line"] == ak["posts"]["p2"]["con_line_caught"]
    assert res["p2"]["diff"]["type"] == "chart"
    assert res["p1"]["con_line"] is None and res["p1"]["points"] == 100
    assert res["p3"]["suspicious_real"] is True
    assert body["clue_bonus"] == 60
    assert body["score"] == 450 + 60
    assert body["clean_case"] is False and body["con_line_clean"] is None
    assert body["share_grid"] == "🟩🧂🟩🟩"  # v2 grid
    assert body["rating"] == 100 and body["rank"] == "Untouchable"
    assert body["adaptation_message"].startswith("The Con has noticed:")
    assert "never open the source" in body["adaptation_message"]


def test_clue_bonus_counts_unused_tokens(client, player):
    client.post(f"/api/cases/{DEMO}/evidence", json={"player_id": player, "post_id": "p2", "tool": "data"})
    client.post(f"/api/cases/{DEMO}/evidence", json={"player_id": player, "post_id": "p2", "tool": "data"})
    body = submit(client, player, DEMO, PERFECT_DEMO).json()
    assert body["clue_bonus"] == 40
    assert body["score"] == 490
    assert "craftier" in body["adaptation_message"]
    # The clue session resets after a verdict, so a replay starts with a full budget.
    assert submit(client, player, DEMO, PERFECT_DEMO).json()["clue_bonus"] == 60


def test_fooled_and_false_alarm(client, player, data_dir):
    ak = load(data_dir, DEMO, "answer_key.json")
    v = verdicts(real=["p1", "p2", "p4"], doctored={"p3": "cherry-picked-stat"})
    body = submit(client, player, DEMO, v).json()
    res = {x["post_id"]: x for x in body["results"]}
    assert res["p2"]["outcome"] == "fooled" and res["p2"]["points"] == 0
    assert res["p2"]["con_line"] == ak["posts"]["p2"]["con_line_fooled"]
    assert res["p2"]["trick_named_correctly"] is False
    assert res["p2"]["tell"] and res["p2"]["diff"]
    assert res["p3"]["outcome"] == "false_alarm" and res["p3"]["points"] == -50
    assert res["p3"]["con_line"] == ak["posts"]["p3"]["con_line_false_alarm"]
    assert body["score"] == 100 + 0 - 50 + 100 + 60
    assert body["share_grid"] == "🟩⬛🟥🟩"
    # hit 0/1, false alarms 1/3 -> round(50 - 16.67) = 33
    assert body["rating"] == 33 and body["rank"] == "Rookie"
    msg = body["adaptation_message"]
    assert "trust official-looking charts" in msg and "doubt real numbers" in msg


def test_caught_with_wrong_or_no_trick(client, player):
    for trick in ("cherry-picked-stat", None):
        v = verdicts(real=["p1", "p3", "p4"], doctored={"p2": trick})
        p2 = submit(client, player, DEMO, v).json()["results"][1]
        assert p2["outcome"] == "caught" and p2["points"] == 100 and p2["trick_named_correctly"] is False


def test_marking_everything_doctored_rates_about_50(client, player):
    v = verdicts(doctored={p: "misleading-chart" for p in ("p1", "p2", "p3", "p4")})
    body = submit(client, player, DEMO, v).json()
    assert [x["outcome"] for x in body["results"]] == ["false_alarm", "caught", "false_alarm", "false_alarm"]
    assert body["score"] == -150 + 150 + 60
    assert body["rating"] == 50 and body["rank"] == "Gumshoe"
    assert body["share_grid"] == "🟥🧂🟥🟥"


def test_clean_case(client, player, data_dir):
    ak = load(data_dir, CLEAN, "answer_key.json")
    body = submit(client, player, CLEAN, verdicts(real=["p1", "p2", "p3", "p4"])).json()
    assert body["clean_case"] is True
    assert body["con_line_clean"] == ak["con_line_clean"]
    assert all(x["outcome"] == "trusted" and x["con_line"] is None for x in body["results"])
    assert body["score"] == 400 + 60
    # A false alarm on the real-but-suspicious post gets its own line.
    body = submit(client, player, CLEAN, verdicts(real=["p1", "p3", "p4"], doctored={"p2": "misleading-chart"})).json()
    p2 = body["results"][1]
    assert p2["outcome"] == "false_alarm" and p2["suspicious_real"] is True
    assert p2["con_line"] == ak["posts"]["p2"]["con_line_false_alarm"]
    assert "doubt honest charts" in body["adaptation_message"]


def test_missing_verdict_is_422(client, player):
    v = verdicts(real=["p1", "p3"], doctored={"p2": "misleading-chart"})
    r = submit(client, player, DEMO, v)
    assert r.status_code == 422 and "p4" in r.json()["detail"]
    bad_conf = dict(PERFECT_DEMO, p1={"doctored": False, "trick": None, "confidence": 0.2})
    assert submit(client, player, DEMO, bad_conf).status_code == 422


# ---- profiles ------------------------------------------------------------------

def test_profile_counters_after_verdict(client, player, data_dir):
    assert (data_dir / "players" / player / "profile.json").is_file()
    submit(client, player, DEMO, PERFECT_DEMO)
    p = client.get(f"/api/players/{player}").json()
    t = p["tricks"]
    assert t["misleading-chart"] == {"shown": 1, "caught": 1, "missed": 0, "named": 1, "honest_shown": 0, "false_alarms": 0}
    assert t["out-of-context-quote"]["honest_shown"] == 2  # p1 and p4 are quotes
    assert t["cherry-picked-stat"]["honest_shown"] == 1    # p3 is plain text
    assert [r["format"] for r in p["recent"]] == ["quote", "chart", "text", "quote"]
    assert p["history"][0]["case_id"] == DEMO and p["history"][0]["score"] == 510
    assert p["history"][0]["outcomes"] == {"p1": "trusted", "p2": "caught", "p3": "trusted", "p4": "trusted"}
    assert p["rating"] == 100 and p["rank"] == "Untouchable"
    assert p["per_trick"]["misleading-chart"] == {"miss_rate": 0.0, "false_alarm_rate": 0.0, "mastery": 1}

    # A false alarm on the honest chart counts against misleading-chart.
    submit(client, player, CLEAN, verdicts(real=["p1", "p3", "p4"], doctored={"p2": None}))
    p = client.get(f"/api/players/{player}").json()
    assert p["tricks"]["misleading-chart"]["honest_shown"] == 1
    assert p["tricks"]["misleading-chart"]["false_alarms"] == 1
    assert p["per_trick"]["misleading-chart"]["false_alarm_rate"] == 1.0


def test_recent_keeps_last_30(client, player):
    for _ in range(8):
        submit(client, player, DEMO, ALL_REAL_DEMO)
    p = client.get(f"/api/players/{player}").json()
    assert len(p["recent"]) == 30 and len(p["history"]) == 8
    assert p["tricks"]["misleading-chart"]["missed"] == 8
    assert p["rating"] == 50  # trusting everything: hit 0, false alarms 0


def test_unknown_player_404_but_verdict_creates_profile(client):
    assert client.get("/api/players/doesnotexist").status_code == 404
    assert submit(client, "freshid123", DEMO, PERFECT_DEMO).status_code == 200
    assert client.get("/api/players/freshid123").json()["history"][0]["case_id"] == DEMO


# ---- adaptive next ---------------------------------------------------------------

def test_next_skips_finished_cases(client, player):
    assert client.get(f"/api/cases/next?player_id={player}").status_code == 200
    submit(client, player, DEMO, PERFECT_DEMO)
    assert client.get(f"/api/cases/next?player_id={player}").json()["id"] == CLEAN
    submit(client, player, CLEAN, verdicts(real=["p1", "p2", "p3", "p4"]))
    # Everything finished: fall back to any approved case.
    assert client.get(f"/api/cases/next?player_id={player}").json()["id"] in (DEMO, CLEAN)
    assert client.get("/api/cases/next").status_code == 200
    assert client.get("/api/cases/next?player_id=").status_code == 200


def test_next_only_serves_approved(client, player, data_dir):
    meta = load(data_dir, CLEAN, "meta.json")
    save(data_dir, CLEAN, "meta.json", dict(meta, status="awaiting_approval"))
    submit(client, player, DEMO, PERFECT_DEMO)
    assert client.get(f"/api/cases/next?player_id={player}").json()["id"] == DEMO


# ---- teacher & pipeline log -----------------------------------------------------------

def test_non_approved_cases_hidden_from_players(client, player, data_dir):
    meta = load(data_dir, CLEAN, "meta.json")
    save(data_dir, CLEAN, "meta.json", dict(meta, status="draft"))
    assert client.get(f"/api/cases/{CLEAN}").status_code == 404
    assert [c["id"] for c in client.get("/api/cases").json()] == [DEMO]
    assert client.post(f"/api/cases/{CLEAN}/evidence", json={"player_id": player, "post_id": "p1", "tool": "source"}).status_code == 404
    assert submit(client, player, CLEAN, verdicts(real=["p1", "p2", "p3", "p4"])).status_code == 404
    queue = client.get("/api/teacher/queue").json()
    assert {q["id"]: q["meta"]["status"] for q in queue} == {DEMO: "approved", CLEAN: "draft"}
    assert client.get(f"/api/teacher/cases/{CLEAN}").status_code == 200


def test_teacher_reject_and_approve(client, data_dir):
    r = client.post(f"/api/teacher/cases/{DEMO}/reject", json={"reason": "Axis note unclear"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected" and r.json()["rejection_reason"] == "Axis note unclear"
    assert load(data_dir, DEMO, "meta.json")["rejection_reason"] == "Axis note unclear"
    assert client.get(f"/api/cases/{DEMO}").status_code == 404
    assert client.get("/api/cases/today").json()["id"] == CLEAN  # no daily left -> first approved

    r = client.post(f"/api/teacher/cases/{DEMO}/approve", json={})
    assert r.json()["status"] == "approved" and r.json()["rejection_reason"] is None
    assert load(data_dir, DEMO, "meta.json")["status"] == "approved"
    assert client.get(f"/api/cases/{DEMO}").status_code == 200
    assert client.post("/api/teacher/cases/nope/approve", json={}).status_code == 404


def test_teacher_case_detail_and_solver_log(client, data_dir):
    body = client.get(f"/api/teacher/cases/{DEMO}").json()
    assert set(body) == {"case", "evidence", "answer_key", "meta", "solver_log"}
    assert body["answer_key"]["posts"]["p2"]["doctored"] is True
    assert body["solver_log"] is None
    (data_dir / "cases" / DEMO / "solver_log.md").write_text("# Solver\nPASS using data", encoding="utf-8")
    assert client.get(f"/api/teacher/cases/{DEMO}").json()["solver_log"].startswith("# Solver")


def test_pipeline_log(client, data_dir):
    assert client.get(f"/api/cases/{DEMO}/pipeline-log").status_code == 404
    events = [{"t": 1.4, "type": "plan_updated", "todos": []}, {"t": 31.0, "type": "awaiting_approval"}]
    lines = "\n".join(json.dumps(e) for e in events) + "\n\n"
    (data_dir / "cases" / DEMO / "pipeline_log.jsonl").write_text(lines, encoding="utf-8")
    assert client.get(f"/api/cases/{DEMO}/pipeline-log").json() == events


# ---- path traversal & static files -------------------------------------------------

def test_path_traversal_rejected(client, player, data_dir, tmp_path):
    (tmp_path / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    before = {p for p in tmp_path.rglob("*")}
    for url in ["/api/players/..%2F..%2Fsecret", "/api/players/bad.id", "/api/players/..",
                "/api/cases/..%2F..%2Fsecret", "/api/cases/..%5C..%5Csecret", "/api/teacher/cases/..%2Fx",
                "/api/cases/next?player_id=..%2F..%2Fx"]:
        r = client.get(url)
        assert r.status_code in (400, 404, 422), url
        assert "TOP SECRET" not in r.text
    for bad in ["../../evil", "..\\evil", "a/b", "x.y", ""]:
        r = client.post(f"/api/cases/{DEMO}/evidence", json={"player_id": bad, "post_id": "p1", "tool": "source"})
        assert r.status_code == 422, bad
        assert submit(client, bad, DEMO, PERFECT_DEMO).status_code == 422, bad
    assert client.post("/api/teacher/cases/..%2F..%2Fx/approve", json={}).status_code in (404, 405, 422)
    assert {p for p in tmp_path.rglob("*")} == before  # nothing written anywhere


def test_static_frontend_with_spa_fallback(data_dir, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>grain of salt</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    c = TestClient(create_app(data_dir=data_dir, frontend_dist=dist))
    assert "grain of salt" in c.get("/").text
    assert "grain of salt" in c.get("/dossier/abc").text
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert "TOP SECRET" not in c.get("/..%2Fsecret.txt").text
    assert c.get("/api/nope").status_code == 404
    assert c.get("/api/health").json() == {"ok": True}


def test_no_frontend_build_is_fine(client):
    assert client.get("/").status_code == 404
    assert client.get("/api/health").status_code == 200
