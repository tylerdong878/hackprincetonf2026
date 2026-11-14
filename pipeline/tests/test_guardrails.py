"""Content guardrails added after the Nov 20-23 nightly dailies (the editor's six findings).

1. Metadata never gives the answer away: every post has a source_label (doctored ones cite the outlet they
   misquote; doctored NJ Monitor gets none), and a daily has a REAL post from a made-up persona.
2. Made-up accounts are listed personas, never realistic personal names ("Jenna K.").
3. Edited words are never credited to a real outlet (quote speaker "NPR", "NPR says ...").
4. EIA tools only on data topics; doctored claims never say more than their source.
5. Disasters and deaths are blocked (passage, headline, surrounding story); research stays on the topic's feeds.
6. The last model calls are kept for the orchestrator's hand-off.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage

from pipeline.context import FetchedDoc, RunContext
from pipeline.events import EventLog
from pipeline.middleware import BudgetGuardMiddleware, forger_context
from pipeline.models import CallBudgetExceeded, CallStats
from pipeline.safety import (
    SafetyError,
    blocklist_hits,
    fictional_author_problems,
    known_entities,
    outlet_attribution_hits,
    outlet_speaker_problem,
    personal_name_problems,
    unsupported_words,
)
from pipeline.tests import fixtures as fx
from pipeline.tests.conftest import make_ctx, research
from pipeline.textutil import html_to_text, normalize
from pipeline.tools.case_writer import PERSONAS, CaseBuildError, build_case_bundle, write_case_impl
from pipeline.tools.forging import (
    crop_quote_impl,
    edit_detail_impl,
    forging_tools,
    make_chart_impl,
    make_stat_claim_impl,
)
from pipeline.tools.research import (
    fetch_article_impl,
    fetch_rss_impl,
    get_eia_series_impl,
    research_tools,
    save_source_impl,
)
from pipeline.topics import TOPIC_HINTS, plan_daily

NJM_URL = "https://newjerseymonitor.com/2026/09/24/utilities-board-votes-electric-rates/"
PERSONA_NAMES = {p.name for p in PERSONAS}
ACE_CROP = "Shore Electric's average monthly bills will rise by $4.09"  # drops "for example" and the cause


def headline(ctx) -> str:
    fetch_rss_impl(ctx, fx.FEED2_URL, "batteries")
    out = save_source_impl(ctx, fx.STORY3_URL, fx.HEADLINE3)
    assert "HEADLINE" in out, out
    return out.split()[1]


def daily(tmp_path, tricks, topic="food news", **kw):
    ctx = make_ctx(tmp_path, case_id="daily-2026-11-20", mode="daily", daily_date="2026-11-20", theme="Food Fight",
                   topic=topic, tricks=tricks, trick=None, **kw)
    ids = research(ctx)
    ids["head"] = headline(ctx)
    return ctx, ids


def cropped_daily(tmp_path, **p1):
    """A food daily: one speakerless crop (p1), one REAL persona repost (p3), the rest by the outlets."""
    ctx, ids = daily(tmp_path, ["out-of-context-quote"])
    assert crop_quote_impl(ctx, ids["ace"], ACE_CROP).startswith("Made f1"), "crop"
    posts = [
        {"id": "p1", "role": "doctored", "forgery_id": "f1", **p1},
        {"id": "p2", "role": "real_suspicious", "source_id": ids["bpu20"]},
        {"id": "p3", "role": "real", "source_id": ids["net"], "by_persona": True},
        {"id": "p4", "role": "real", "source_id": ids["peak"]},
        {"id": "p5", "role": "real", "source_id": ids["head"]},
    ]
    return ctx, ids, posts


def add_doc(ctx, url, title, paragraphs, outlet="Example"):
    ctx.add_doc(FetchedDoc(url=url, title=title, outlet=outlet, published="2026-11-10T15:00:00Z",
                           paragraphs=paragraphs, via="rss"))


# ======================================================================================
# 1. Metadata never gives the answer away
# ======================================================================================


def test_every_post_cites_its_source_and_a_persona_posts_a_real_card(tmp_path):
    ctx, ids, posts = cropped_daily(tmp_path)
    out = write_case_impl(ctx, "Food Fight", "Five plates. I may have seasoned a few.", posts)
    assert out.startswith("Wrote"), out
    case = json.loads((ctx.case_dir / "case.json").read_text(encoding="utf-8"))
    ev = json.loads((ctx.case_dir / "evidence.json").read_text(encoding="utf-8"))
    p1, p2, p3 = case["posts"][:3]
    assert all(p["source_label"] for p in case["posts"])  # "has a link" no longer means "real"
    assert p1["source_label"] == "example-news.test · Sept 24, 2026"  # the doctored post cites what it crops
    # the REAL persona repost: made-up account, verbatim quote, label citing the real source
    assert p3["author"]["kind"] == "person" and p3["author"]["name"] in PERSONA_NAMES
    assert p3["quote"] == {"text": fx.QUOTE_NET + ".", "speaker": fx.SPEAKER_NET}
    assert p3["source_label"] == "example-news.test · Sept 24, 2026"
    assert ev["p3"]["source"]["url"] == fx.STORY_URL
    # personas carry their own account cards, the same whether the post is real or doctored
    by_name = {p.name: p for p in PERSONAS}
    for pid, post in (("p1", p1), ("p3", p3)):
        assert ev[pid]["account"] == by_name[post["author"]["name"]].account()
    assert p1["author"]["name"] != p3["author"]["name"]
    assert p2["author"]["kind"] == "official"


def test_persona_repost_of_a_plain_sentence_keeps_it_verbatim(tmp_path):
    ctx, ids, posts = cropped_daily(tmp_path)
    posts[1] = {"id": "p2", "role": "real_suspicious", "source_id": ids["bpu20"], "by_persona": True,
                "body": "Wait, what? \U0001F633"}
    case, *_ = build_case_bundle(ctx, "T", "Five plates.", posts)
    body = case["posts"][1]["body"]
    assert body.startswith("Wait, what?") and normalize(fx.BPU_20) in normalize(body)
    assert case["posts"][1]["source_label"] == "NJBPU press release · Aug 13, 2026"


@pytest.mark.parametrize("clean", [False, True])
def test_daily_needs_a_real_post_from_a_made_up_persona(tmp_path, clean):
    ctx, ids, posts = cropped_daily(tmp_path)
    posts[2].pop("by_persona")  # every real post is now by an outlet
    if clean:  # a clean day of outlets only would say "nothing is doctored"
        ctx.tricks = []
        posts[0] = {"id": "p1", "role": "real", "source_id": ids["ace"]}
    with pytest.raises(CaseBuildError, match="REAL post from a made-up persona"):
        build_case_bundle(ctx, "T", "Five plates.", posts)
    assert "by_persona=true" in write_case_impl(ctx, "T", "Five plates.", posts)


def _njm_source(ctx) -> str:
    paras, _, _ = html_to_text(fx.STORY_HTML)
    add_doc(ctx, NJM_URL, "Board votes to keep electricity rates level", paras, outlet="New Jersey Monitor")
    out = save_source_impl(ctx, NJM_URL, fx.QUOTE_NET, fx.SPEAKER_NET)
    assert out.startswith("Saved"), out
    return out.split()[1]


def test_doctored_nj_monitor_post_has_no_label_so_a_daily_refuses_it(tmp_path):
    ctx, ids = daily(tmp_path, ["out-of-context-quote"])
    njm = _njm_source(ctx)
    assert crop_quote_impl(ctx, njm, "these actions will result in no increase in electricity rates").startswith("Made")
    posts = [{"id": "p1", "role": "doctored", "forgery_id": "f1"},
             {"id": "p2", "role": "real_suspicious", "source_id": ids["bpu20"]},
             {"id": "p3", "role": "real", "source_id": ids["ace"], "by_persona": True},
             {"id": "p4", "role": "real", "source_id": ids["peak"]},
             {"id": "p5", "role": "real", "source_id": ids["head"]}]
    with pytest.raises(CaseBuildError, match="only post.* without a source label") as exc:
        build_case_bundle(ctx, "T", "Five plates.", posts)
    assert "CC BY-NC-ND" in str(exc.value) and "Doctor a different source" in str(exc.value)


def test_doctored_nj_monitor_post_carries_no_label_in_a_case_file(tmp_path):
    ctx = make_ctx(tmp_path, trick="out-of-context-quote")
    ids = research(ctx)
    njm = _njm_source(ctx)
    crop_quote_impl(ctx, njm, "these actions will result in no increase in electricity rates")
    posts = [{"id": "p1", "role": "doctored", "forgery_id": "f1"},
             {"id": "p2", "role": "real_suspicious", "source_id": ids["bpu20"]},
             {"id": "p3", "role": "real", "source_id": ids["ace"]},
             {"id": "p4", "role": "real", "source_id": ids["peak"]}]
    case, *_ = build_case_bundle(ctx, "T", "Four posts.", posts)
    assert case["posts"][0]["source_label"] is None  # no derivatives of NJ Monitor under its name
    assert all(p["source_label"] for p in case["posts"][1:])


# ======================================================================================
# 2. Made-up accounts: listed personas, never realistic personal names
# ======================================================================================


@pytest.mark.parametrize("name,handle", [
    ("Jenna K.", "@jenna_k_sports"), ("Mike R.", "@mike_r_hockey"), ("Sarah T.", "@sarah_t_energy"),
    ("Sarah Thompson", "@sarahthompson"), ("Dr. Volt", "@drvolt_daily"), ("Sports Desk", "@mike_r_hockey"),
])
def test_realistic_personal_names_are_refused(tmp_path, name, handle):
    assert personal_name_problems(name, handle)
    ctx, _, posts = cropped_daily(tmp_path, author_name=name, author_handle=handle)
    with pytest.raises(SafetyError, match="made-up account"):
        build_case_bundle(ctx, "T", "Five plates.", posts)
    assert write_case_impl(ctx, "T", "Five plates.", posts).startswith("Rejected (safety)")


def test_unlisted_invented_name_is_refused_with_the_persona_list(tmp_path):
    ctx, _, posts = cropped_daily(tmp_path, author_name="Snack Truth", author_handle="@snacktruth")
    out = write_case_impl(ctx, "T", "Five plates.", posts)
    assert "not on the persona list" in out and "Fact Snack" in out


def test_personas_are_invented_handles_and_never_real_entities():
    from pipeline.fool import PERSONAS as DECK_PERSONAS

    for p in PERSONAS:
        assert personal_name_problems(p.name, p.handle) == [], p
        assert fictional_author_problems(p.name, p.handle, known_entities()) == [], p
        assert not blocklist_hits([p.bio, *p.recent]), p
    for name, handle, _ in DECK_PERSONAS:
        assert personal_name_problems(name, handle) == [], name
    assert len({p.handle for p in PERSONAS}) == len(PERSONAS)
    ages = {p.created[-4:] for p in PERSONAS}
    assert len(ages) >= 5  # mixed ages, so account age says nothing


def test_personas_are_assigned_once_each(tmp_path):
    ctx, ids, posts = cropped_daily(tmp_path)
    case, *_ = build_case_bundle(ctx, "T", "Five plates.", posts)
    assert case["posts"][0]["author"]["name"] in PERSONA_NAMES  # empty author_name: assigned
    posts[0].update(author_name="Turnpike Tea")
    posts[2].update(author_name="Turnpike Tea")
    with pytest.raises(CaseBuildError, match="already posts p1"):
        build_case_bundle(ctx, "T", "Five plates.", posts)


# ======================================================================================
# 3. Edited words are never credited to a real outlet
# ======================================================================================


def test_crop_of_a_speakerless_sentence_is_never_a_quote_by_the_outlet(tmp_path):
    ctx, _, posts = cropped_daily(tmp_path)
    art = ctx.artifacts["f1"]
    assert art["quote"] is None and art["speaker"] is None
    case, _, key, _, _ = build_case_bundle(ctx, "T", "Five plates.", posts)
    p1 = case["posts"][0]
    assert p1["quote"] is None and p1["body"] == key["posts"]["p1"]["diff"]["shown"]
    assert normalize(p1["body"]).startswith("Shore Electric's average monthly bills")


def test_doctored_quote_credited_to_an_outlet_is_refused(tmp_path):
    ctx, ids, posts = cropped_daily(tmp_path)
    crop_quote_impl(ctx, ids["peak"], "really unsustainable price hikes in the utility and electricity bills")
    for speaker in ("NPR", "example-news.test"):
        ctx.artifacts["f2"]["quote"]["speaker"] = speaker  # e.g. what the Nov 20/21 dailies shipped
        posts[0]["forgery_id"] = "f2"
        posts[3] = {"id": "p4", "role": "real", "source_id": ids["ace"]}
        with pytest.raises(SafetyError, match="real outlet"):
            build_case_bundle(ctx, "T", "Five plates.", posts)


def test_outlet_speaker_and_attribution_units():
    ents = known_entities()
    assert outlet_speaker_problem("NPR", ents) and outlet_speaker_problem("New Jersey Monitor", ents)
    assert outlet_speaker_problem("NPR staff", ents)
    assert outlet_speaker_problem("Ben Hertz-Shargel, NJBPU President", ents) is None
    assert outlet_attribution_hits("NPR: candy prices up 18%", ents) == ["NPR"]
    assert outlet_attribution_hits("According to NPR, it's over", ents) == ["NPR"]
    assert outlet_attribution_hits("BPU just promised NO increase", ents) == ["BPU"]
    assert outlet_attribution_hits("Screenshot this before it's gone", ents) == []


def test_save_source_refuses_an_outlet_as_speaker(ctx):
    url = "https://www.npr.org/2026/11/07/nx-s1-1/league-adds-teams"
    add_doc(ctx, url, "League adds two teams", ["NPR reports that the league will add two teams next season."])
    out = save_source_impl(ctx, url, "the league will add two teams next season", "NPR")
    assert out.startswith("Rejected") and "real outlet" in out
    assert save_source_impl(ctx, url, "the league will add two teams next season").startswith("Saved")


@pytest.mark.parametrize("body", ["NPR: {shown}", "According to NPR, {shown}", "{shown} (per @NPR)"])
def test_doctored_text_credited_to_an_outlet_is_refused(tmp_path, body):
    ctx, _, posts = cropped_daily(tmp_path)
    posts[0]["body"] = body.format(shown=ctx.artifacts["f1"]["shown"])
    with pytest.raises(CaseBuildError, match="credit the edited text to NPR"):
        build_case_bundle(ctx, "T", "Five plates.", posts)


# ======================================================================================
# 4. EIA data only on data topics; doctored claims never say more than the source
# ======================================================================================


def test_fun_topics_have_no_eia_tools(tmp_path):
    food = make_ctx(tmp_path, topic="food news")
    energy = make_ctx(tmp_path / "e")
    assert food.has_data is False and energy.has_data is True
    names = lambda tools: {t.name for t in tools}  # noqa: E731
    assert "get_eia_series" not in names(research_tools(food)) and "get_eia_series" in names(research_tools(energy))
    assert "make_chart" not in names(forging_tools(food)) and "make_chart" in names(forging_tools(energy))
    assert "no data series" in next(t for t in forging_tools(food) if t.name == "make_stat_claim").description
    assert get_eia_series_impl(food).startswith("Refused")
    assert "no chart data" in make_chart_impl(food, months=["2025-04", "2026-07"], y_min=19)
    out = make_stat_claim_impl(food, start_month="2024-06", end_month="2025-06")
    assert "no data series" in out and food.artifacts == {}
    text = forger_context(food)
    assert "EIA NJ residential price" not in text and "No data series" in text and "Turnpike Tea" in text
    assert "EIA NJ residential price" in forger_context(energy)


def test_fun_topics_never_plan_misleading_chart():
    for topic, hints in TOPIC_HINTS.items():
        if hints.get("data"):
            continue
        assert "misleading-chart" not in hints["tricks"], topic
        for day in ("2026-11-16", "2026-11-20", "2026-11-21", "2026-11-22"):
            assert "misleading-chart" not in plan_daily(day, 3, hints["tricks"])[0]


def test_cli_refuses_a_trick_the_topic_cant_support(tmp_path):
    from pipeline.build_case import parse_args, run_settings
    from datetime import UTC, datetime

    args = parse_args(["--mode", "daily", "--topic", "food news", "--trick", "misleading-chart"])
    with pytest.raises(SystemExit, match="doesn't fit topic"):
        run_settings(args, datetime(2026, 11, 15, tzinfo=UTC), tmp_path)


def test_dry_run_for_a_food_day_has_no_eia_tools(capsys):
    from pipeline.build_case import main

    assert main(["--mode", "daily", "--daily-date", "2026-11-30", "--topic", "food news", "--dry-run"]) == 0
    out = capsys.readouterr().out
    tool_lines = [line for line in out.splitlines() if "tools:" in line]
    assert tool_lines and not any("get_eia_series" in line or "make_chart" in line for line in tool_lines)
    assert "data none" in out and "kept for the orchestrator's hand-off" in out


def test_stat_claim_may_not_add_a_conclusion(researched):
    ctx, ids = researched
    out = make_stat_claim_impl(ctx, claim="Science says NJ residential electricity prices surged 24% — the data "
                                          "proves the grid is collapsing.", start_month="2024-06", end_month="2025-06")
    assert "says more than its data" in out and "collapsing" in out and ctx.artifacts == {}
    base = dict(source_id=ids["ace"], kept_fact="will rise by $4.09", omitted_fact=fx.ACE_FALL)
    out = make_stat_claim_impl(ctx, claim="Shore Electric bills UP $4.09. The grid is collapsing.", **base)
    assert "says more than its source" in out and "grid" in out
    assert make_stat_claim_impl(ctx, claim="Shore Electric bills are going UP $4.09 a month.", **base).startswith("Made")


def test_unsupported_words_unit():
    src = ("Prices for candy, the most popular Halloween purchase, and gum have risen 7.7% in one year and are up "
           "more than 18% in two years, according to the latest federal data.")
    assert unsupported_words("Candy and gum prices are up more than 18%.", src) == []
    assert unsupported_words("Candy prices are up 18%, which proves stores are gouging", src) == ["proves", "stores",
                                                                                                 "gouging"]


@pytest.mark.parametrize("body,why", [
    ("This proves bills will never go up again.", "claim more than the source says"),
    ("That's a total ban on rate hikes across every utility.", "claim more than the source says"),
    ("Rates frozen until 2030 and bills down 40%!", "add numbers"),
])
def test_doctored_reaction_may_not_add_claims_or_numbers(tmp_path, body, why):
    ctx, ids, posts = cropped_daily(tmp_path)
    crop_quote_impl(ctx, ids["net"], "these actions will result in no increase in electricity rates")
    posts[0].update(forgery_id="f2", body=body)
    posts[2] = {"id": "p3", "role": "real", "source_id": ids["ace"], "by_persona": True}
    with pytest.raises(CaseBuildError, match=why):
        build_case_bundle(ctx, "T", "Five plates.", posts)


def test_edited_detail_reaction_may_not_add_numbers(tmp_path):
    ctx, ids = daily(tmp_path, ["edited-detail"])
    edit_detail_impl(ctx, ids["head"], "$4 million", "$40 million")
    posts = [{"id": "p1", "role": "doctored", "forgery_id": "f1",
              "body": f"{ctx.artifacts['f1']['shown']} That's 900% more!"},
             {"id": "p2", "role": "real_suspicious", "source_id": ids["bpu20"]},
             {"id": "p3", "role": "real", "source_id": ids["net"], "by_persona": True},
             {"id": "p4", "role": "real", "source_id": ids["peak"]},
             {"id": "p5", "role": "real", "source_id": ids["ace"]}]
    with pytest.raises(CaseBuildError, match="add numbers"):
        build_case_bundle(ctx, "T", "Five plates.", posts)


# ======================================================================================
# 5. Disasters and deaths are blocked; research stays on the topic's feeds
# ======================================================================================


@pytest.mark.parametrize("text", [
    "The Mystery of the Morro Castle ship fire", "a 1934 shipwreck off the Jersey Shore",
    "the over 26 cases of people who have disappeared there since 1971", "two men drowned in the lake",
    "the inventor died in 1931", "a deadly crash on the Turnpike", "crew members escaped in under-filled lifeboats",
    "four hikers went missing", "It was a disaster",
])
def test_blocklist_covers_disasters_and_deaths(text):
    assert {c for c, _ in blocklist_hits([text])} & {"disasters and deaths", "ongoing tragedies"}, text


@pytest.mark.parametrize("text", [
    "Candy and gum prices are up more than 18%", "Robots used during search and rescue operations",
    "LIV Golf is shutting down after four years", "How octopuses squeeze through teeny tiny holes",
    "The app crashed twice during the update", "A dead heat at the finish line",
])
def test_blocklist_leaves_fun_news_alone(text):
    assert blocklist_hits([text]) == []


def test_save_source_refuses_passages_from_tragedy_stories(ctx):
    url = "https://example-news.test/2026/09/07/morro-castle/"
    add_doc(ctx, url, "The Mystery of the Morro Castle", [
        "Neither the passengers nor the crew underwent safety drills.",
        "These crew members were the first to leave passengers to fend for themselves.",
        "It was a disaster, and by the time ships in the area arrived to help, it was too late for many."])
    out = save_source_impl(ctx, url, "These crew members were the first to leave passengers to fend for themselves.")
    assert out.startswith("Rejected") and "story around this passage" in out and "disaster" in out
    titled = "https://example-news.test/2026/06/05/reservoir/"
    add_doc(ctx, titled, "Two boaters vanished at the reservoir, never found",
            ["The reservoir reaches depths of 180 feet.", "Its clear blue waters are popular with anglers."])
    assert "headline touches a blocked topic" in save_source_impl(ctx, titled, "The reservoir reaches depths of 180 feet.")
    story = "https://example-news.test/2026/06/06/lake/"
    add_doc(ctx, story, "The lake mystery nobody can explain",
            ["Six of those lost have never been found.", "Two boaters went missing in 1973."])
    assert "story under this headline" in save_source_impl(ctx, story, "The lake mystery nobody can explain")
    assert ctx.sources == []


def test_research_stays_on_the_topics_feeds(ctx):
    out = fetch_rss_impl(ctx, "https://www.weirdnj.com/feed/", "weird")
    assert out.startswith("Refused") and fx.FEED_URL in out and ctx.fetch.calls == []
    out = fetch_article_impl(ctx, "https://weirdnj.com/weird-news/morro-castle/")
    assert out.startswith("Refused") and ctx.fetch.calls == []
    fetch_rss_impl(ctx, fx.FEED_URL + "?paged=2", "electricity")  # a page of a listed feed is fine
    assert ctx.fetch.calls == [fx.FEED_URL + "?paged=2"]
    fetch_rss_impl(ctx, fx.FEED_URL, "electricity")
    assert fetch_article_impl(ctx, fx.STORY_URL).startswith("(from this run's cache")  # linked from the feed
    assert "NJ Board of Public Utilities" in fetch_article_impl(ctx, fx.PRESS_URL)  # a listed page


def test_research_scope_defaults_to_the_topic_hints():
    weird = RunContext(case_id="x", topic="new jersey weird news", persist=False, events=EventLog(None))
    assert weird.feeds == TOPIC_HINTS["new jersey weird news"]["feeds"] and weird.has_data is False
    energy = RunContext(case_id="x", topic="NJ electricity prices", persist=False, events=EventLog(None))
    assert energy.has_data is True and "https://nj.gov/bpu/newsroom/2026/approved/20260813.html" in energy.articles
    assert any("utilities-board-votes-electric-rates" in a for a in energy.articles)  # known stories count


# ======================================================================================
# 6. The last model calls are kept for the hand-off
# ======================================================================================


def test_call_reserve_is_for_the_orchestrator_only():
    stats = CallStats(max_calls=5, rpm=0)
    for _ in range(3):
        stats.before_call("blind-solver")
    with pytest.raises(CallBudgetExceeded, match="kept for the orchestrator"):
        stats.before_call("blind-solver")
    stats.before_call("orchestrator")
    stats.before_call("orchestrator")
    with pytest.raises(CallBudgetExceeded, match="used up"):
        stats.before_call("orchestrator")


def _call(name="task", sub="forger"):
    return SimpleNamespace(tool_call={"name": name, "id": "call_1", "args": {"subagent_type": sub}})


def test_budget_guard_refuses_new_tasks_and_ends_cut_short_ones(tmp_path):
    ctx = make_ctx(tmp_path, stats=CallStats(max_calls=10, rpm=0))
    guard = BudgetGuardMiddleware(ctx)
    ctx.stats.total, ctx.write_count = 8, 1
    out = guard.wrap_tool_call(_call(), lambda r: pytest.fail("the sub-agent must not start"))
    assert isinstance(out, ToolMessage) and out.text.startswith("Refused") and "submit_for_review" in out.text
    assert guard.wrap_tool_call(_call("submit_for_review"), lambda r: "ran") == "ran"  # the hand-off still runs
    ctx.stats.total = 5

    def runs_out(_req):
        raise CallBudgetExceeded("Model-call budget for sub-agents used up")

    out = guard.wrap_tool_call(_call(sub="blind-solver"), runs_out)
    assert out.text.startswith("Stopped: blind-solver") and "submit_for_review" in out.text
    with pytest.raises(CallBudgetExceeded):
        guard.wrap_tool_call(_call("write_todos"), runs_out)


@pytest.mark.parametrize("max_calls,solver_calls", [(13, 1), (12, 0)])
def test_tight_budget_still_hands_the_case_to_the_editor(tmp_path, max_calls, solver_calls):
    """Nov 21/23 stopped after the solver with no calls left for submit_for_review. Now the solver is cut short
    (13) or never started (12), and the orchestrator still submits."""
    from pipeline.agent import build_agent
    from pipeline.build_case import run
    from pipeline.tests.test_e2e_scripted import CASE_ID, SOLVER_PASS, scripted_models

    ctx = make_ctx(tmp_path, case_id=CASE_ID, stats=CallStats(max_calls=max_calls, rpm=0))
    models = scripted_models(SOLVER_PASS)
    bundle = build_agent(ctx, models)
    assert run(bundle.agent, ctx, "Build case.", "hold") == "awaiting_approval"
    assert models["solver"].calls == solver_calls and ctx.stats.total <= max_calls
    finished = [e for e in ctx.events.events if e["type"] == "subagent_finished" and e["name"] == "blind-solver"]
    assert finished and ("Stopped" in finished[0]["summary"] or "Refused" in finished[0]["summary"])
