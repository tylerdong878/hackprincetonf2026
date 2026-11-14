"""Daily Grain cases (CONTRACT §7.1) and the edited-detail trick."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

import pytest

from pipeline.schemas import DetailDiff, daily_briefing_problems, validate_bundle
from pipeline.tests import fixtures as fx
from pipeline.tests.conftest import make_ctx, research
from pipeline.tools.case_writer import CaseBuildError, build_case_bundle, write_case_impl
from pipeline.tools.forging import detail_kind, edit_detail_impl, make_chart_impl
from pipeline.tools.research import fetch_rss_impl, save_source_impl
from pipeline.topics import DAILY_DOCTORED_BY_WEEKDAY, plan_daily


def headline(ctx) -> str:
    fetch_rss_impl(ctx, fx.FEED2_URL, "batteries")
    out = save_source_impl(ctx, fx.STORY3_URL, fx.HEADLINE3)
    assert "HEADLINE" in out, out
    return out.split()[1]


@pytest.fixture
def daily_ctx(tmp_path):
    ctx = make_ctx(tmp_path, case_id="daily-2026-11-15", mode="daily", daily_date="2026-11-15", theme="Your Bills",
                   tricks=["misleading-chart", "edited-detail"], trick=None)
    ids = research(ctx)
    ids["head"] = headline(ctx)
    return ctx, ids


def daily_posts(ctx, ids) -> list[dict]:
    make_chart_impl(ctx, months=["2025-04", "2026-07"], y_min=19)
    out = edit_detail_impl(ctx, ids["head"], "$4 million", "$40 million")
    assert out.startswith("Made f2"), out
    return [
        {"id": "p1", "role": "real", "source_id": ids["net"]},
        {"id": "p2", "role": "doctored", "forgery_id": "f1", "author_name": "Jersey Bill Watch",
         "author_handle": "@jerseybills", "body": "NJ power prices are up 27% in ONE YEAR."},
        {"id": "p3", "role": "real_suspicious", "source_id": ids["bpu20"]},
        {"id": "p4", "role": "doctored", "forgery_id": "f2", "author_name": "Turnpike Tea",
         "author_handle": "@turnpiketea"},
        {"id": "p5", "role": "real", "source_id": ids["peak"], "by_persona": True},  # real, by a persona
    ]


# ---------------------------------------------------------------- edited-detail tool


def test_headline_sources_are_verbatim_titles(ctx):
    fetch_rss_impl(ctx, fx.FEED2_URL, "batteries")
    assert save_source_impl(ctx, fx.STORY3_URL, "Trenton board approves $5 million for home batteries on Thursday"
                            ).startswith("Rejected")
    out = save_source_impl(ctx, fx.STORY3_URL, f"“{fx.HEADLINE3}”")
    assert "HEADLINE" in out
    s = ctx.sources[-1]
    assert s.headline and s.text == fx.HEADLINE3 and s.highlight == fx.HEADLINE3 and "pilot" in s.after


def test_detail_kinds():
    assert detail_kind("$4 million") == "number"
    assert detail_kind("Thursday") == "date" and detail_kind("Nov. 12") == "date"
    assert detail_kind("Trenton") == "place" and detail_kind("Atlantic City") == "place"
    assert detail_kind("approves") is None and detail_kind("a very long phrase here now") is None


@pytest.mark.parametrize("find,replace,shown_part", [
    ("$4 million", "$40 million", "approves $40 million for"),
    ("Trenton", "Newark", "Newark board approves"),
    ("Thursday", "Monday", "on Monday"),
])
def test_edit_detail_swaps_one_detail(ctx, find, replace, shown_part):
    hid = headline(ctx)
    out = edit_detail_impl(ctx, hid, find, replace)
    assert out.startswith("Made f1 (edited-detail)"), out
    art = ctx.artifacts["f1"]
    diff = DetailDiff.model_validate(art["diff"])
    assert diff.original == fx.HEADLINE3 and shown_part in diff.shown
    assert art["diff"]["changed"] == [{"from": find, "to": replace}]
    assert diff.shown.replace(replace, find, 1) == diff.original  # nothing else changed
    assert art["evidence_tools"] == ["source"]


@pytest.mark.parametrize("find,replace,why", [
    ("$4 million", "Newark", "must be a number too"),
    ("Trenton", "Monday", "must be a place too"),
    ("$9 million", "$90 million", "is not in"),
    ("Tren", "Newa", "whole word"),
    ("approves", "rejects", "isn't a swappable detail"),
    ("Trenton", "Trenton", "same as the original"),
    ("Trenton", "Shooting", "blocked topic"),
])
def test_edit_detail_guards(ctx, find, replace, why):
    hid = headline(ctx)
    out = edit_detail_impl(ctx, hid, find, replace)
    assert out.startswith("Rejected") and why in out, out
    assert ctx.artifacts == {}


def test_edit_detail_never_on_quotes(researched):
    ctx, ids = researched
    assert "not on quotes" in edit_detail_impl(ctx, ids["net"], "Thursday", "Monday")


def test_edited_detail_only_on_made_up_accounts():
    from pipeline.schemas import validate_bundle as vb

    # the contract check: an edited-detail answer on an outlet-authored post is invalid
    case = {"id": "x", "number": 1, "title": "T", "topic": "t", "briefing": "B", "clue_budget": 3,
            "trick_options": ["edited-detail"],
            "posts": [{"id": "p1", "author": {"name": "Real Outlet", "handle": "@real", "kind": "outlet",
                                              "verified": True, "avatar_color": "#000000"},
                       "posted_at": "2026-11-14T10:00:00Z", "body": "x", "quote": None, "chart": None,
                       "source_label": None, "tools": ["source"]}]}
    ev = {"p1": {"source": {"outlet": "o", "date": None, "url": "https://x.test", "before": "", "highlight": "h",
                            "after": ""}}}
    key = {"clean_case": False, "con_line_clean": None, "posts": {"p1": {
        "doctored": True, "trick": "edited-detail", "tell": "t", "explanation": "e", "con_line_fooled": "f",
        "con_line_caught": "c", "diff": {"type": "detail", "shown": "a", "original": "b",
                                         "changed": [{"from": "1", "to": "2"}]}}}}
    meta = {"status": "draft", "origin": "pipeline", "daily": False, "difficulty": "easy",
            "created_at": "2026-11-14T10:00:00Z", "tricks": ["edited-detail"], "sources": [], "rejection_reason": None}
    with pytest.raises(ValueError, match="made-up-account"):
        vb(case, ev, key, meta)


# ---------------------------------------------------------------- daily cases


def test_daily_case_files(daily_ctx):
    ctx, ids = daily_ctx
    out = write_case_impl(ctx, "Grain of Salt: Your Bills", "Five posts about your power bill. Good luck, detective.",
                          daily_posts(ctx, ids))
    assert out.startswith("Wrote"), out
    load = lambda n: json.loads((ctx.case_dir / n).read_text(encoding="utf-8"))  # noqa: E731
    case, ev, key, meta = load("case.json"), load("evidence.json"), load("answer_key.json"), load("meta.json")
    validate_bundle(case, ev, key, meta)
    assert len(case["posts"]) == 5 and case["clue_budget"] == 3
    assert "0–3 doctored today" in case["briefing"]  # the range, added for the forger
    assert meta["mode"] == "daily" and meta["daily_date"] == "2026-11-15" and meta["theme"] == "Your Bills"
    assert sorted(meta["tricks"]) == ["edited-detail", "misleading-chart"]
    assert [p["card_style"] for p in case["posts"]] == ["quote", "chart", "stat", "headline", "quote"]
    assert "edited-detail" in case["trick_options"]
    p4 = case["posts"][3]
    assert p4["body"] == fx.HEADLINE3.replace("$4 million", "$40 million") and p4["author"]["kind"] == "person"
    assert key["posts"]["p4"]["diff"]["type"] == "detail"
    assert ev["p4"]["source"]["highlight"] == fx.HEADLINE3  # the player can open the real headline
    assert key["clean_case"] is False


@pytest.mark.parametrize("briefing", ["Two of these are doctored today. 0–3 doctored today.",
                                      "Five posts, 0-3 doctored today, but only one is fake."])
def test_daily_briefing_never_states_the_count(daily_ctx, briefing):
    ctx, ids = daily_ctx
    with pytest.raises(CaseBuildError, match="must not state how many"):
        build_case_bundle(ctx, "T", briefing, daily_posts(ctx, ids))


def test_daily_shape_rules(daily_ctx):
    ctx, ids = daily_ctx
    posts = daily_posts(ctx, ids)
    with pytest.raises(CaseBuildError, match="5 posts"):
        build_case_bundle(ctx, "T", "B", posts[:4])
    with pytest.raises(CaseBuildError, match="exactly 2 doctored"):
        build_case_bundle(ctx, "T", "B", [p if p["id"] != "p4" else
                                          {"id": "p4", "role": "real", "source_id": ids["ace"]} for p in posts])
    ctx.tricks = ["misleading-chart", "cherry-picked-stat"]
    with pytest.raises(CaseBuildError, match="tricks are"):
        build_case_bundle(ctx, "T", "B", posts)


def test_daily_with_nothing_doctored(tmp_path):
    ctx = make_ctx(tmp_path, case_id="daily-2026-11-16", mode="daily", daily_date="2026-11-16", theme="Your Bills",
                   tricks=[], trick=None)
    ids = research(ctx)
    ids["head"] = headline(ctx)
    make_chart_impl(ctx, months=["2025-07", "2026-07"], honest=True)
    posts = [{"id": "p1", "role": "real", "source_id": ids["net"]},
             {"id": "p2", "role": "real_suspicious", "chart_id": "c1", "author_name": "Calm Down Daily",
              "author_handle": "@calmdowndaily"},
             {"id": "p3", "role": "real", "source_id": ids["bpu20"]},
             {"id": "p4", "role": "real", "source_id": ids["head"]},
             {"id": "p5", "role": "real", "source_id": ids["ace"]}]
    case, ev, key, meta, _ = build_case_bundle(ctx, "T", "Nothing up my sleeve. Probably.", posts)
    assert key["clean_case"] is True and key["con_line_clean"] and meta["tricks"] == []
    assert case["posts"][3]["card_style"] == "headline"


def test_daily_contract_checks_catch_tampering(daily_ctx):
    ctx, ids = daily_ctx
    case, ev, key, meta, _ = build_case_bundle(ctx, "T", "B", daily_posts(ctx, ids))
    with pytest.raises(ValueError, match="clue_budget 3"):
        validate_bundle(dict(case, clue_budget=4), ev, key, meta)
    with pytest.raises(ValueError, match="daily_date"):
        validate_bundle(case, ev, key, dict(meta, daily_date=None))
    with pytest.raises(ValueError, match="range"):
        validate_bundle(dict(case, briefing="Five posts."), ev, key, meta)


def test_daily_briefing_problems():
    assert daily_briefing_problems("Five cards. 0–3 doctored today.") == []
    assert daily_briefing_problems("Five cards. 0-3 doctored today. Spot one?") == []
    assert daily_briefing_problems("No fakes today. 0–3 doctored today.")
    assert daily_briefing_problems("Five cards.")


# ---------------------------------------------------------------- planning + CLI


def test_plan_daily_is_deterministic_and_follows_weekday():
    for day in ("2026-11-16", "2026-11-17", "2026-11-20", "2026-11-21", "2026-11-22"):
        tricks, _ = plan_daily(day)
        assert plan_daily(day)[0] == tricks
        lo, hi = DAILY_DOCTORED_BY_WEEKDAY[datetime.strptime(day, "%Y-%m-%d").weekday()]
        assert lo <= len(tricks) <= hi and len(set(tricks)) == len(tricks)
    assert plan_daily("2026-11-21", 3)[0].__len__() == 3
    with pytest.raises(ValueError):
        plan_daily("2026-11-21", 4)


def _args(**kw) -> argparse.Namespace:
    from pipeline.build_case import parse_args

    return parse_args([*sum(([f"--{k.replace('_', '-')}", str(v)] for k, v in kw.items() if v is not True), []),
                       *[f"--{k.replace('_', '-')}" for k, v in kw.items() if v is True]])


def test_run_settings_daily(tmp_path):
    from pipeline.build_case import run_settings

    now = datetime(2026, 11, 15, 12, tzinfo=UTC)
    s = run_settings(_args(mode="daily", daily_date="2026-11-21", theme="Sports Stats", doctored=2), now, tmp_path)
    assert s["case_id"] == "daily-2026-11-21" and s["mode"] == "daily" and len(s["tricks"]) == 2
    assert s["theme"] == "Sports Stats" and s["clean"] is False
    (tmp_path / "daily-2026-11-21").mkdir()
    assert run_settings(_args(mode="daily", daily_date="2026-11-21"), now, tmp_path)["case_id"] == "daily-2026-11-21-2"
    clean = run_settings(_args(mode="daily", daily_date="2026-11-21", clean=True), now, tmp_path)
    assert clean["tricks"] == [] and clean["clean"] is True
    default = run_settings(_args(mode="daily"), now, tmp_path)
    assert default["daily_date"] == "2026-11-15" and default["theme"] == "Your Bills"
    v1 = run_settings(_args(trick="misleading-chart"), now, tmp_path)
    assert v1["mode"] == "casefile" and v1["trick"] == "misleading-chart"


def test_hold_for_editor_flag_and_its_hidden_old_name(capsys):
    from pipeline.build_case import parse_args

    assert parse_args(["--hold-for-editor"]).hold_for_editor is True
    assert parse_args(["--hold-for-teacher"]).hold_for_editor is True  # old name, kept as a hidden alias
    assert parse_args([]).hold_for_editor is False
    for flag in ("--hold-for-editor", "--hold-for-teacher"):
        with pytest.raises(SystemExit):
            parse_args([flag, "--auto-approve"])  # still mutually exclusive with --auto-approve
    capsys.readouterr()
    with pytest.raises(SystemExit):
        parse_args(["--help"])
    help_text = capsys.readouterr().out
    assert "--hold-for-editor" in help_text and "--hold-for-teacher" not in help_text


def test_nightly_build_holds_for_the_editor(monkeypatch):
    from datetime import date

    from pipeline.build_case import parse_args
    from scripts import nightly_build

    calls = []
    monkeypatch.setattr(nightly_build, "next_missing", lambda _days: date(2026, 11, 23))
    monkeypatch.setattr(nightly_build.subprocess, "run",
                        lambda cmd, cwd=None: calls.append(cmd) or argparse.Namespace(returncode=0))
    assert nightly_build.main([]) == 0
    (cmd,) = calls
    assert cmd[1:3] == ["-m", "pipeline.build_case"]
    args = parse_args(cmd[3:])
    assert args.hold_for_editor is True and args.auto_approve is False and args.mode == "daily"


def test_user_request_and_ctx_shape_for_daily(daily_ctx):
    from pipeline.build_case import user_request

    ctx, _ = daily_ctx
    req = user_request(ctx, "- feeds: x", "Sunday: 2 doctored")
    assert "Exactly 5 posts" in req and "0–3 doctored today" in req and "retries allowed: 1" in req
    assert ctx.max_solver_attempts == 2


def test_cli_daily_dry_run(capsys):
    from pipeline.build_case import main

    assert main(["--dry-run", "--mode", "daily", "--daily-date", "2026-11-21", "--theme", "Your Bills"]) == 0
    out = capsys.readouterr().out
    assert "Daily Grain for 2026-11-21 (theme: Your Bills)" in out and "Blind-solver isolation: OK" in out
    assert "edited-detail" in out
