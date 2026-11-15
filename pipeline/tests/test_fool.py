"""Con the Con (CONTRACT §7.3/§7.4): apply_edit (deterministic) and judge_post (scripted models only)."""

from __future__ import annotations

import copy
import json
import time

import pytest
from langchain_core.messages import ToolMessage

from pipeline.fakes import ScriptedChatModel, ai, tool_call
import pipeline.fool as fool_mod
from pipeline.fool import (
    NEUTRAL_ACCOUNT,
    PERSONAS,
    TRACE_NAME,
    ConAsleep,
    apply_edit,
    blind_view,
    edited_author,
    judge_post,
    outcome_for,
)
from pipeline.safety import fictional_author_problems, known_entities
from pipeline.schemas import ChartDiff, Post, QuoteDiff, StatDiff
from pipeline.tests import fixtures as fx
from pipeline.tools.research import load_eia

QUOTE = ("Taken together with the items on the agenda earlier this month, these actions will result in no net "
         "increase in electricity rates and a slight decrease in gas rates.")
NJM = {"name": "New Jersey Monitor", "handle": "@NJMonitor", "kind": "outlet", "verified": True,
       "avatar_color": "#2F9E6A"}
NJM_ACCOUNT = {"name": "New Jersey Monitor", "handle": "@NJMonitor", "created": None, "followers": None,
               "verified": True, "bio": "News outlet · newjerseymonitor.com", "recent_posts": []}
SOURCE_EV = {"outlet": "New Jersey Monitor", "date": "2026-09-24", "url": fx.STORY_URL, "before": "",
             "highlight": "“" + QUOTE[:-1] + ",” said the board's president.", "after": ""}
ACE_FULL = ("Shore Electric's average monthly bills will rise by $4.09 because of transmission charges, but will fall "
            "by $4.14 due to other changes, leaving the average bill 5 cents cheaper.")
ACE_WITHOUT = "Shore Electric's average monthly bills will rise by $4.09 because of transmission charges."


def quote_item() -> dict:
    return {
        "id": "hs-net-increase", "kind": "quote",
        "post": {"id": "p1", "author": NJM, "posted_at": "2026-09-24T19:48:00Z", "body": "",
                 "quote": {"text": QUOTE, "speaker": "Dana Example, Board President"}, "chart": None,
                 "source_label": "New Jersey Monitor · Sept 24, 2026", "tools": ["source", "account"]},
        "evidence": {"source": SOURCE_EV, "account": NJM_ACCOUNT},
        "editable": {"quote_words": QUOTE.split()},
        "tools": ["crop"],
    }


def chart_item() -> dict:
    prices = load_eia(__import__("pipeline.config", fromlist=["EIA_FILE"]).EIA_FILE)
    series = [{"label": p, "value": v} for p, v in prices.items() if p >= "2025-01"]
    chart = {"type": "bar", "title": "July vs. July", "unit": "¢/kWh",
             "points": [{"label": "Jul 2025", "value": 25.11}, {"label": "Jul 2026", "value": 25.19}],
             "y_min": 0, "y_max": None}
    eia = {"name": "U.S. Energy Information Administration", "handle": "@EIAgov", "kind": "official",
           "verified": True, "avatar_color": "#0E7490"}
    data_ev = {"title": "NJ residential average electricity price (EIA)", "unit": "¢/kWh",
               "url": "https://www.eia.gov/electricity/data/browser/", "table": series,
               "honest_chart": dict(chart, type="line", points=[{"label": s["label"], "value": s["value"]}
                                                                for s in series]),
               "note": "July to July: 25.11 → 25.19 (+0.3%)."}
    return {
        "id": "eia-july-july", "kind": "chart",
        "post": {"id": "p1", "author": eia, "posted_at": "2026-10-01T16:00:00Z",
                 "body": "July vs July: 25.11¢ → 25.19¢ per kWh.", "quote": None, "chart": chart,
                 "source_label": "EIA · Oct 1, 2026", "tools": ["data", "account"]},
        "evidence": {"data": data_ev, "account": {**NJM_ACCOUNT, "name": eia["name"], "handle": "@EIAgov"}},
        "editable": {"chart_series": series},
        "tools": ["axis", "window"],
    }


def stat_item() -> dict:
    return {
        "id": "ace-offset", "kind": "stat",
        "post": {"id": "p1", "author": NJM, "posted_at": "2026-09-24T20:00:00Z", "body": ACE_FULL, "quote": None,
                 "chart": None, "source_label": "New Jersey Monitor · Sept 24, 2026", "tools": ["source", "account"]},
        "evidence": {"source": dict(SOURCE_EV, highlight=ACE_FULL), "account": NJM_ACCOUNT},
        "editable": {"stat": {"full": ACE_FULL, "droppable": [
            {"id": "offset", "text": "but will fall by $4.14 due to other changes", "shown_without": ACE_WITHOUT}]}},
        "tools": ["drop"],
    }


def no_net_indices() -> list[int]:
    words = QUOTE.split()
    return [i for i, w in enumerate(words) if w != "net"]


def assert_made_up(post: dict) -> None:
    a = post["author"]
    assert a["kind"] == "person" and a["verified"] is False
    assert not fictional_author_problems(a["name"], a["handle"], known_entities())
    assert post["source_label"] is None
    Post.model_validate(post)


# ======================================================================================
# apply_edit
# ======================================================================================


def test_none_is_untouched():
    item = quote_item()
    out = apply_edit(item, {"type": "none"})
    assert out == {"edited_post": item["post"], "changed": False, "trick": None, "diff": None}
    assert out["edited_post"] is not item["post"]  # a copy


def test_crop_drops_net():
    item = quote_item()
    before = copy.deepcopy(item)
    out = apply_edit(item, {"type": "crop", "keep_word_indices": no_net_indices()})
    assert out["changed"] is True and out["trick"] == "out-of-context-quote"
    diff = QuoteDiff.model_validate(out["diff"])
    assert diff.removed == ["net"] and diff.original == QUOTE
    assert "no increase in electricity rates" in out["edited_post"]["quote"]["text"]
    assert out["edited_post"]["quote"]["speaker"] == "Dana Example, Board President"
    assert_made_up(out["edited_post"])
    assert item == before  # input untouched
    assert apply_edit(item, {"type": "crop", "keep_word_indices": no_net_indices()}) == out  # deterministic


def test_crop_keeping_every_word_is_not_a_change():
    item = quote_item()
    out = apply_edit(item, {"type": "crop", "keep_word_indices": list(range(len(QUOTE.split())))})
    assert out["changed"] is False and out["edited_post"]["author"] == NJM and out["diff"] is None


@pytest.mark.parametrize("keep", [
    [0, 1, 2],                      # fewer than 4 words
    [3, 2, 5, 6],                   # out of order
    [0, 1, 1, 2, 3],                # a word twice (adding)
    [0, 1, 2, 999],                 # outside the quote
    [0, 1, "2", 3],                 # not indices
    "0,1,2,3",                      # not a list
])
def test_crop_illegal(keep):
    with pytest.raises(ValueError):
        apply_edit(quote_item(), {"type": "crop", "keep_word_indices": keep})


def test_axis_truncation():
    item = chart_item()
    out = apply_edit(item, {"type": "axis", "y_min": 25})
    assert out["changed"] and out["trick"] == "misleading-chart"
    diff = ChartDiff.model_validate(out["diff"])
    # The top hugs the data (25.2, not 26), so a 0.08 difference fills the frame.
    assert diff.shown.y_min == 25 and diff.shown.y_max == 25.2 and diff.original.y_min == 0
    assert out["edited_post"]["body"] == item["post"]["body"]
    assert_made_up(out["edited_post"])
    assert apply_edit(item, {"type": "axis", "y_min": 0})["changed"] is False


@pytest.mark.parametrize("y_min", [25.11, 30, -1, "19", True, None, float("nan")])
def test_axis_illegal(y_min):
    with pytest.raises(ValueError):
        apply_edit(chart_item(), {"type": "axis", "y_min": y_min})


def test_window_picks_months():
    out = apply_edit(chart_item(), {"type": "window", "window": ["2026-07", "2025-04"]})
    assert out["changed"] and out["trick"] == "misleading-chart"
    pts = out["edited_post"]["chart"]["points"]
    assert pts == [{"label": "Apr 2025", "value": 19.91}, {"label": "Jul 2026", "value": 25.19}]  # sorted
    assert "+26.5%" in out["edited_post"]["body"]
    ChartDiff.model_validate(out["diff"])
    assert_made_up(out["edited_post"])


@pytest.mark.parametrize("window", [["2025-04", "2031-01"], ["2025-04", "2025-04"], ["2025-04"],
                                    ["2025-04", "2025-05", "2025-06"], "2025-04", [202504, 202607]])
def test_window_illegal(window):
    with pytest.raises(ValueError):
        apply_edit(chart_item(), {"type": "window", "window": window})


def test_drop_context():
    out = apply_edit(stat_item(), {"type": "drop", "drop": "offset"})
    assert out["changed"] and out["trick"] == "cherry-picked-stat"
    diff = StatDiff.model_validate(out["diff"])
    assert out["edited_post"]["body"] == ACE_WITHOUT == diff.shown and diff.original == ACE_FULL
    assert "4.14" in diff.missing
    assert_made_up(out["edited_post"])
    with pytest.raises(ValueError):
        apply_edit(stat_item(), {"type": "drop", "drop": "denominator"})


@pytest.mark.parametrize("item_fn,edit", [
    (quote_item, {"type": "axis", "y_min": 1}),           # tool not offered for this deck item
    (chart_item, {"type": "crop", "keep_word_indices": [0, 1, 2, 3]}),
    (stat_item, {"type": "window", "window": ["2025-04", "2026-07"]}),
    (quote_item, {"type": "rewrite", "text": "anything"}),  # unknown edit type
    (quote_item, {}),
])
def test_edit_must_match_deck_tools(item_fn, edit):
    with pytest.raises(ValueError):
        apply_edit(item_fn(), edit)


# ======================================================================================
# judge_post (scripted models; no network)
# ======================================================================================


def verdict_call(verdict="doctored", trick="out-of-context-quote", lines=None, confidence=0.8):
    return ai("", tool_call("con_verdict", {"verdict": verdict, "trick_guess": trick,
                                            "reasoning": lines or ["You trimmed one word.", "Net. Cute.",
                                                                   "I read the whole sentence."],
                                            "confidence": confidence}))


def test_judge_catches_crop_with_one_look():
    edited = apply_edit(quote_item(), {"type": "crop", "keep_word_indices": no_net_indices()})["edited_post"]
    model = ScriptedChatModel(script=[ai("", tool_call("open_evidence", {"tool": "source"})), verdict_call()],
                              model_name="scripted-con")
    con = judge_post(edited, quote_item()["evidence"], model=model)
    assert con == {"checked": ["source"], "verdict": "doctored", "trick_guess": "out-of-context-quote",
                   "reasoning": ["You trimmed one word.", "Net. Cute.", "I read the whole sentence."],
                   "confidence": 0.8, "model": "scripted-con"}
    assert model.calls == 2
    assert outcome_for(True, con["verdict"]) == "caught"


def test_judge_enforces_exactly_one_evidence_call():
    edited = apply_edit(quote_item(), {"type": "crop", "keep_word_indices": no_net_indices()})["edited_post"]
    greedy = ai("", tool_call("open_evidence", {"tool": "source"}), tool_call("open_evidence", {"tool": "account"}))
    model = ScriptedChatModel(script=[greedy, verdict_call()])
    con = judge_post(edited, quote_item()["evidence"], model=model)
    assert con["checked"] == ["source"]
    second_prompt = model.seen[1]
    tool_msgs = [m for m in second_prompt if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1 and "said the board" in tool_msgs[0].text
    ai_msgs = [m for m in second_prompt if getattr(m, "tool_calls", None)]
    assert len(ai_msgs[0].tool_calls) == 1


def test_judge_cannot_take_a_second_look():
    edited = quote_item()["post"]
    model = ScriptedChatModel(script=[ai("", tool_call("open_evidence", {"tool": "source"})),
                                      ai("", tool_call("open_evidence", {"tool": "account"}))])
    with pytest.raises(ConAsleep):
        judge_post(edited, quote_item()["evidence"], model=model)


def test_judge_rejects_unavailable_tool():
    model = ScriptedChatModel(script=[ai("", tool_call("open_evidence", {"tool": "data"})), verdict_call()])
    with pytest.raises(ConAsleep):
        judge_post(quote_item()["post"], quote_item()["evidence"], model=model)


def test_judge_text_fallbacks_and_real_verdict():
    model = ScriptedChatModel(script=[
        ai("Let me check the source."),
        ai('{"verdict": "real", "trick_guess": "misleading-chart", "reasoning": "Matches word for word. Annoying.", '
           '"confidence": 1.7}'),
    ])
    con = judge_post(quote_item()["post"], quote_item()["evidence"], model=model)
    assert con["checked"] == ["source"] and con["verdict"] == "real" and con["trick_guess"] is None
    assert con["reasoning"] == ["Matches word for word.", "Annoying."] and con["confidence"] == 1.0
    assert outcome_for(False, "real") == "con_trusted" and outcome_for(False, "doctored") == "con_false_alarm"
    assert outcome_for(True, "real") == "fooled_the_con"


def test_judge_is_blind_to_author_label_and_edit():
    """Edited and untouched versions look identical to the Con apart from the content itself."""
    item = quote_item()
    untouched = apply_edit(item, {"type": "none"})
    cropped = apply_edit(item, {"type": "crop", "keep_word_indices": no_net_indices()})
    prompts = []
    for out in (untouched, cropped):
        model = ScriptedChatModel(script=[ai("", tool_call("open_evidence", {"tool": "account"})),
                                          verdict_call(verdict="real", trick=None)])
        judge_post(out["edited_post"], item["evidence"], model=model)
        first = json.dumps([m.content for m in model.seen[0]], default=str)
        prompts.append(first)
        for leak in ("New Jersey Monitor", "@NJMonitor", "Sept 24", out["edited_post"]["author"]["name"],
                     "changed", "diff", "hs-net-increase", "crop"):
            assert leak not in first, leak
        account_msg = [m for m in model.seen[1] if isinstance(m, ToolMessage)][0]
        assert json.loads(account_msg.text) == NEUTRAL_ACCOUNT  # same card either way
    assert prompts[0].replace(QUOTE, "<Q>") != prompts[1]  # content differs...
    strip = lambda s: s.split("quote:")[0]  # noqa: E731  # ...but the poster line is identical
    assert strip(prompts[0]) == strip(prompts[1])
    assert blind_view(cropped["edited_post"])["author"] == blind_view(untouched["edited_post"])["author"]


def test_judge_sleeps_without_key(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "PIPELINE_PROVIDER"):
        monkeypatch.setenv(k, "")
    monkeypatch.setattr("pipeline.models.load_env", lambda: None)
    with pytest.raises(ConAsleep):
        judge_post(quote_item()["post"], quote_item()["evidence"])


def test_judge_sleeps_when_the_model_fails():
    broken = ScriptedChatModel(script=[])  # raises on first call
    with pytest.raises(ConAsleep):
        judge_post(quote_item()["post"], quote_item()["evidence"], model=broken)


class SlowModel(ScriptedChatModel):
    delay: float = 1.0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001
        time.sleep(self.delay)
        return super()._generate(messages, stop, run_manager, **kwargs)


def test_judge_hard_deadline_then_one_fallback():
    slow = SlowModel(script=[ai("", tool_call("open_evidence", {"tool": "source"}))] * 2, model_name="ultra")
    quick = ScriptedChatModel(script=[ai("", tool_call("open_evidence", {"tool": "source"})), verdict_call()],
                              model_name="lightning")
    t0 = time.monotonic()
    con = judge_post(quote_item()["post"], quote_item()["evidence"], model=slow, fallback=quick, deadline_s=0.2)
    assert time.monotonic() - t0 < 0.9  # didn't wait for the slow model
    assert con["model"] == "lightning" and quick.calls == 2
    slow2 = SlowModel(script=[ai("x")] * 2, model_name="ultra")
    slow3 = SlowModel(script=[ai("x")] * 2, model_name="lightning")
    with pytest.raises(ConAsleep, match="ultra: DeadlineExceeded; lightning: DeadlineExceeded"):
        judge_post(quote_item()["post"], quote_item()["evidence"], model=slow2, fallback=slow3, deadline_s=0.1)


def test_judge_models_default_chain(monkeypatch):
    from pipeline.models import make_judge_models

    monkeypatch.setattr("pipeline.models.load_env", lambda: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-not-real")
    for k in ("PIPELINE_PROVIDER", "PIPELINE_JUDGE_MODEL", "PIPELINE_JUDGE_FALLBACK_MODEL", "PIPELINE_SOLVER_MODEL"):
        monkeypatch.delenv(k, raising=False)
    chain = make_judge_models()
    assert [(n, v) for _, n, v in chain] == [("nvidia/nemotron-3.5-super-vl:free", True),
                                            ("nvidia/nemotron-3.5-lightning:free", False)]
    assert all(m.max_retries == 0 for m, _, _ in chain)


# ======================================================================================
# v2.1 (CONTRACT §8): made-up account per deck item, dramatic axis, Con levels
# ======================================================================================


def test_edited_author_is_fixed_per_deck_item_and_used_by_apply_edit():
    item = quote_item()
    author = edited_author(item)
    assert author == edited_author(copy.deepcopy(item))  # deterministic
    assert (author["name"], author["handle"], author["avatar_color"]) in PERSONAS
    out = apply_edit(item, {"type": "crop", "keep_word_indices": no_net_indices()})
    assert out["edited_post"]["author"] == author  # exactly the account the editor previews
    for fn, edit in ((chart_item, {"type": "axis", "y_min": 25}), (stat_item, {"type": "drop", "drop": "offset"})):
        assert apply_edit(fn(), edit)["edited_post"]["author"] == edited_author(fn())
    # Different deck ids spread over the persona list.
    picks = {edited_author(dict(item, id=f"deck-{i}"))["handle"] for i in range(40)}
    assert len(picks) >= 4


def test_personas_are_invented_handles():
    ents = known_entities()
    for name, handle, color in PERSONAS:
        assert handle.startswith("@") and color.startswith("#")
        assert not fictional_author_problems(name, handle, ents), name


def test_edited_author_skips_a_persona_that_collides_with_the_real_poster():
    item = quote_item()
    first = edited_author(item)
    item["post"]["author"] = dict(NJM, name=first["name"], handle=first["handle"])  # pretend it's real
    other = edited_author(item)
    assert other["handle"] != first["handle"]
    assert not fictional_author_problems(other["name"], other["handle"], known_entities())


def test_axis_bound_is_the_lowest_value_shown_not_the_whole_series():
    item = chart_item()
    series = item["editable"]["chart_series"]
    assert min(s["value"] for s in series) < 20  # the series dips to ~19.6 in early 2025...
    shown = [{"label": "Jul 2026", "value": 25.19}, {"label": "Aug 2026", "value": 25.4}]
    item["post"]["chart"] = dict(item["post"]["chart"], points=shown)  # ...but the post only shows two months
    out = apply_edit(item, {"type": "axis", "y_min": 25.1})  # far above the series minimum: allowed
    chart = out["edited_post"]["chart"]
    assert out["changed"] and chart["y_min"] == 25.1 and chart["points"] == shown
    assert 25.4 < chart["y_max"] <= 25.5  # a tight top: the bars fill the frame
    ChartDiff.model_validate(out["diff"])
    for bad in (25.19, 25.3):  # at or above the lowest bar shown would cut it off
        with pytest.raises(ValueError, match="25.19"):
            apply_edit(item, {"type": "axis", "y_min": bad})


def test_axis_top_on_the_real_deck_scale():
    from pipeline.fool import _axis_top

    assert _axis_top([19.65, 25.19], 19.5) == 26
    assert _axis_top([2.141, 6.227], 2.0) == 7
    assert _axis_top([25.11, 25.19], 25) == 25.2
    assert _axis_top([1, 5], 0) is None  # an honest axis stays auto


class RecordingModel(ScriptedChatModel):
    bound: list = []

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001
        self.bound.append([getattr(t, "__name__", str(t)) for t in tools])
        return self


def test_level1_rookie_con_gets_no_evidence_and_one_verdict_call():
    edited = apply_edit(quote_item(), {"type": "crop", "keep_word_indices": no_net_indices()})["edited_post"]
    model = RecordingModel(script=[verdict_call(verdict="real", trick=None)], model_name="scripted-con")
    con = judge_post(edited, quote_item()["evidence"], level=1, model=model)
    assert model.calls == 1 and model.bound == [["con_verdict"]]  # verdict schema only
    assert con["checked"] == [] and con["verdict"] == "real" and con["model"] == "scripted-con"
    prompt = json.dumps([m.content for m in model.seen[0]], default=str)
    assert not [m for m in model.seen[0] if isinstance(m, ToolMessage)]
    for leak in ("said the board", "open_evidence", "evidence tools:", "You may open"):
        assert leak not in prompt, leak
    assert "NO evidence" in prompt
    # Level 1 doesn't need an evidence kit at all.
    model = RecordingModel(script=[verdict_call()])
    assert judge_post(edited, {}, level=1, model=model)["checked"] == []


def test_level3_is_the_default_and_level2_still_checks_once():
    for level in (2, 3):
        model = RecordingModel(script=[ai("", tool_call("open_evidence", {"tool": "source"})), verdict_call()])
        con = judge_post(quote_item()["post"], quote_item()["evidence"], level=level, model=model)
        assert con["checked"] == ["source"] and model.calls == 2
        assert model.bound == [["open_evidence"], ["con_verdict"]]


@pytest.mark.parametrize("level", [0, 4, "2", None, True, 2.5])
def test_bad_level(level):
    with pytest.raises(ValueError):
        judge_post(quote_item()["post"], quote_item()["evidence"], level=level,
                   model=ScriptedChatModel(script=[verdict_call()]))


def test_level2_uses_the_fast_model_first(monkeypatch):
    from pipeline.models import make_judge_models

    monkeypatch.setattr("pipeline.models.load_env", lambda: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-not-real")
    for k in ("PIPELINE_PROVIDER", "PIPELINE_JUDGE_MODEL", "PIPELINE_JUDGE_FALLBACK_MODEL", "PIPELINE_SOLVER_MODEL"):
        monkeypatch.delenv(k, raising=False)
    names = lambda lv: [n for _, n, _ in make_judge_models(level=lv)]  # noqa: E731
    full, fast = "nvidia/nemotron-3.5-super-vl:free", "nvidia/nemotron-3.5-lightning:free"
    assert names(3) == names(1) == [full, fast]
    assert names(2) == [fast, full]
    seen = []
    monkeypatch.setattr(fool_mod, "_judge_models", lambda level=3: seen.append(level) or [
        (ScriptedChatModel(script=[ai("", tool_call("open_evidence", {"tool": "source"})), verdict_call()],
                           model_name="lightning"), "lightning", False)])
    con = judge_post(quote_item()["post"], quote_item()["evidence"], level=2)
    assert seen == [2] and con["model"] == "lightning"


def test_trace_keeps_its_name_and_is_tagged_with_the_level(monkeypatch):
    assert TRACE_NAME == "Con the Con · live judge"
    got = {}

    def fake_traced(edited_post, evidence, *, langsmith_extra, **kwargs):  # noqa: ANN001
        got.update(extra=langsmith_extra, kwargs=kwargs)
        return {"checked": [], "verdict": "real"}

    monkeypatch.setattr(fool_mod, "_judge_traced", fake_traced)
    judge_post(quote_item()["post"], quote_item()["evidence"], level=1)
    assert got["extra"]["metadata"] == {"con_level": 1, "con_level_name": "Rookie Con"}
    assert "con-level-1" in got["extra"]["tags"] and got["kwargs"]["level"] == 1


def test_crop_cuts_words_from_a_stat_post_too():
    item = stat_item()
    item["tools"] = ["crop", "drop"]
    words = ACE_FULL.split()
    cut_from = next(i for i, w in enumerate(words) if w.lower().startswith("but"))
    out = apply_edit(item, {"type": "crop", "keep_word_indices": list(range(cut_from))})
    assert out["changed"] and out["trick"] == "cherry-picked-stat"
    post = out["edited_post"]
    assert post["quote"] is None and post["body"].rstrip(".,") == " ".join(words[:cut_from]).rstrip(".,")
    assert out["diff"]["type"] == "stat" and out["diff"]["original"] == ACE_FULL and out["diff"]["removed"]
    assert_made_up(post)
    # deletion only: out of order or too short is refused
    with pytest.raises(ValueError):
        apply_edit(item, {"type": "crop", "keep_word_indices": [3, 1, 2, 4]})
    with pytest.raises(ValueError):
        apply_edit(item, {"type": "crop", "keep_word_indices": [0, 1]})
    # keeping every word is no change
    assert apply_edit(item, {"type": "crop", "keep_word_indices": list(range(len(words)))})["changed"] is False
