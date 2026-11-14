"""write_case: CONTRACT §2 validation, fictional-author rule, blocklist, verbatim real posts."""

from __future__ import annotations

import json

import pytest

from pipeline.config import CASES_DIR
from pipeline.safety import SafetyError, blocklist_hits, check_blocklist, fictional_author_problems, known_entities
from pipeline.schemas import validate_bundle
from pipeline.tests.conftest import make_ctx, research
from pipeline.tools.case_writer import CaseBuildError, build_case_bundle, write_case_impl
from pipeline.tools.forging import crop_quote_impl, make_chart_impl


def chart_case(ctx, ids, **overrides):
    make_chart_impl(ctx, months=["2025-04", "2026-07"], y_min=19)
    posts = [
        {"id": "p1", "role": "real", "source_id": ids["net"]},
        {"id": "p2", "role": "doctored", "forgery_id": "f1", "author_name": "Jersey Bill Watch",
         "author_handle": "jerseybills", "body": "NJ power prices are up 27% in ONE YEAR."},
        {"id": "p3", "role": "real_suspicious", "source_id": ids["bpu20"]},
        {"id": "p4", "role": "real", "source_id": ids["peak"]},
    ]
    for i, patch in overrides.items():
        posts[int(i[1]) - 1].update(patch)
    return posts


# ---------------------------------------------------------------- happy path


def test_write_case_writes_valid_contract_files(researched):
    ctx, ids = researched
    out = write_case_impl(ctx, "Is your power bill really frozen?", "Four posts. I may have touched one. Or none.",
                          chart_case(ctx, ids))
    assert out.startswith("Wrote case"), out
    files = {n: json.loads((ctx.case_dir / n).read_text(encoding="utf-8"))
             for n in ("case.json", "evidence.json", "answer_key.json", "meta.json")}
    validate_bundle(files["case.json"], files["evidence.json"], files["answer_key.json"], files["meta.json"])
    meta = files["meta.json"]
    assert meta["status"] == "awaiting_approval" and meta["origin"] == "pipeline" and meta["daily"] is False
    assert meta["tricks"] == ["misleading-chart"]
    case = files["case.json"]
    p1, p2 = case["posts"][0], case["posts"][1]
    assert p1["author"]["kind"] == "outlet" and p1["quote"]["text"].startswith("Taken together")
    assert p2["author"] == {"name": "Jersey Bill Watch", "handle": "@jerseybills", "kind": "person",
                            "verified": False, "avatar_color": p2["author"]["avatar_color"]}
    assert p2["tools"] == ["data", "account"] and p2["source_label"] == "Data: U.S. EIA"  # doctored posts cite too
    p3 = case["posts"][2]
    assert p3["author"]["name"] == "NJ Board of Public Utilities" and p3["body"].startswith("…New Jersey")
    assert p3["source_label"] == "NJBPU press release · Aug 13, 2026"
    key = files["answer_key.json"]
    assert key["posts"]["p2"]["diff"]["type"] == "chart" and key["posts"]["p3"]["suspicious_real"] is True
    assert "case.json" not in json.dumps(case) and "tell" not in json.dumps(case)  # no answers in the player view
    written = [e["path"] for e in ctx.events.events if e["type"] == "file_written"]
    assert f"/cases/{ctx.case_id}/answer_key.json" in written


def test_clean_case(tmp_path):
    ctx = make_ctx(tmp_path, clean=True, trick=None)
    ids = research(ctx)
    make_chart_impl(ctx, months=["2025-07", "2026-07"], honest=True)
    posts = [
        {"id": "p1", "role": "real", "source_id": ids["net"]},
        {"id": "p2", "role": "real_suspicious", "chart_id": "c1", "author_name": "Calm Down Daily",
         "author_handle": "@calmdowndaily", "body": "July vs July: 25.11¢ → 25.19¢ per kWh (EIA)."},
        {"id": "p3", "role": "real", "source_id": ids["bpu20"]},
        {"id": "p4", "role": "real", "source_id": ids["ace"]},
    ]
    case, ev, key, meta, _ = build_case_bundle(ctx, "Who's driving your bill?", "Four posts. Some mine. Maybe.", posts)
    assert key["clean_case"] is True and key["con_line_clean"] and meta["tricks"] == []
    assert ev["p2"]["data"]["honest_chart"]["y_min"] == 0
    assert case["posts"][1]["chart"]["y_min"] == 0


# ---------------------------------------------------------------- structural rules


def test_requires_exactly_one_doctored_and_a_suspicious_real(researched):
    ctx, ids = researched
    posts = chart_case(ctx, ids)
    no_suspicious = [dict(p, role="real") if p["role"] == "real_suspicious" else p for p in posts]
    with pytest.raises(CaseBuildError, match="real_suspicious"):
        build_case_bundle(ctx, "T", "B", no_suspicious)
    two_fakes = posts + [{"id": "p5", "role": "doctored", "forgery_id": "f1", "author_name": "X Y",
                          "author_handle": "@xy"}]
    with pytest.raises(CaseBuildError, match="exactly 1 doctored"):
        build_case_bundle(ctx, "T", "B", two_fakes)


def test_rejects_unknown_forgery_wrong_trick_and_reused_source(researched):
    ctx, ids = researched
    with pytest.raises(CaseBuildError, match="not a forgery"):
        build_case_bundle(ctx, "T", "B", chart_case(ctx, ids, p2={"forgery_id": "f9"}))
    out = crop_quote_impl(ctx, ids["peak"], "really unsustainable price hikes in the utility and electricity bills")
    quote_fid = out.split()[1]
    with pytest.raises(CaseBuildError, match="trick is misleading-chart"):
        build_case_bundle(ctx, "T", "B", chart_case(ctx, ids, p2={"forgery_id": quote_fid},
                                                    p4={"source_id": ids["ace"]}))
    # a source that was cropped can't also appear as a real post
    with pytest.raises(CaseBuildError, match="already used"):
        ctx.trick = "out-of-context-quote"
        build_case_bundle(ctx, "T", "B", chart_case(ctx, ids, p2={"forgery_id": quote_fid, "body": ""}))
    ctx.trick = "misleading-chart"
    with pytest.raises(CaseBuildError, match="already used"):
        build_case_bundle(ctx, "T", "B", chart_case(ctx, ids, p4={"source_id": ids["net"]}))


def test_real_posts_must_stay_verbatim(researched):
    ctx, ids = researched
    with pytest.raises(CaseBuildError, match="verbatim"):
        build_case_bundle(ctx, "T", "B", chart_case(ctx, ids, p3={"body": "Bills jumped 20% last year!!"}))


def test_doctored_chart_body_numbers_must_come_from_chart(researched):
    ctx, ids = researched
    with pytest.raises(CaseBuildError, match="don't come from the chart"):
        build_case_bundle(ctx, "T", "B", chart_case(ctx, ids, p2={"body": "Prices up 41% in ONE YEAR."}))


# ---------------------------------------------------------------- fictional-author rule


@pytest.mark.parametrize("name,handle", [
    ("New Jersey Monitor", "@realnews"),
    ("NJ Monitor Daily", "@njmd"),
    ("Bill Watch", "@NJBPU"),
    ("Dana Example Fans", "@fans"),          # the quoted speaker's name
    ("The Example Report", "@exreport"),     # the quoted speaker's surname
    ("NJ Board of Public Utilities", "@bpu_updates"),
])
def test_doctored_author_must_be_made_up(researched, name, handle):
    ctx, ids = researched
    posts = chart_case(ctx, ids, p2={"author_name": name, "author_handle": handle})
    with pytest.raises(SafetyError, match="made-up account"):
        build_case_bundle(ctx, "T", "B", posts)
    assert write_case_impl(ctx, "T", "B", posts).startswith("Rejected (safety)")


def test_fictional_author_problems_unit():
    ents = known_entities()
    assert fictional_author_problems("Jersey Bill Watch", "@jerseybills", ents) == []
    assert fictional_author_problems("Priya (watt nerd)", "@wattnerd", ents) == []
    assert fictional_author_problems("EIA", "@data", ents)
    assert fictional_author_problems("", "", ents)


# ---------------------------------------------------------------- topic blocklist (SPEC §8.5)


@pytest.mark.parametrize("text,category", [
    ("Vote before the election on Tuesday", "elections near voting day"),
    ("Candidates promise lower bills", "elections near voting day"),
    ("The shooting left two victims", "ongoing tragedies"),
    ("Measles outbreak in the county", "public-health emergencies"),
    ("Students and their teachers protest bills", "minors as subjects"),
])
def test_blocklist_categories(text, category):
    assert category in {c for c, _ in blocklist_hits([text])}
    with pytest.raises(SafetyError):
        check_blocklist([text])


def test_blocklist_allows_demo_topic_and_board_votes():
    check_blocklist(["NJ electricity prices", "The utilities board votes to keep electricity rates level",
                     "Power bills. Four posts. I may have touched one."])


def test_write_case_blocks_blocklisted_text(researched):
    ctx, ids = researched
    posts = chart_case(ctx, ids, p2={"body": "Election day is coming: prices up 27% in ONE YEAR."})
    assert write_case_impl(ctx, "T", "B", posts).startswith("Rejected (safety)")
    assert not (ctx.case_dir / "case.json").exists()


# ---------------------------------------------------------------- schema + numbering


@pytest.mark.parametrize("case_id", ["2026-11-14-power-bills", "2026-11-14-power-bills-clean"])
def test_seed_cases_validate_against_contract_models(case_id):
    folder = CASES_DIR / case_id
    load = lambda n: json.loads((folder / n).read_text(encoding="utf-8"))  # noqa: E731
    validate_bundle(load("case.json"), load("evidence.json"), load("answer_key.json"), load("meta.json"))


def test_contract_models_reject_extra_keys_and_bad_values(researched):
    ctx, ids = researched
    case, ev, key, meta, _ = build_case_bundle(ctx, "T", "B", chart_case(ctx, ids))
    with pytest.raises(ValueError):
        validate_bundle(dict(case, answers="leak"), ev, key, meta)
    with pytest.raises(ValueError):
        validate_bundle(case, ev, key, dict(meta, status="live"))
    bad_key = json.loads(json.dumps(key))
    bad_key["posts"]["p2"]["diff"]["type"] = "quote"
    with pytest.raises(ValueError):
        validate_bundle(case, ev, bad_key, meta)


def test_case_number_follows_existing_cases(tmp_path):
    ctx = make_ctx(tmp_path)
    other = ctx.cases_dir / "older-case"
    other.mkdir(parents=True)
    (other / "case.json").write_text(json.dumps({"number": 7}), encoding="utf-8")
    ids = research(ctx)
    case, *_ = build_case_bundle(ctx, "T", "B", chart_case(ctx, ids))
    assert case["number"] == 8
