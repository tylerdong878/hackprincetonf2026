"""Forging tools: tricks applied by code to real material, with the reveal diffs."""

from __future__ import annotations

from pipeline.schemas import ChartDiff, QuoteDiff, StatDiff
from pipeline.tests import fixtures as fx
from pipeline.tools.forging import crop_quote_impl, make_chart_impl, make_stat_claim_impl, quote_text


# ---------------------------------------------------------------- crop_quote -> quote diff


def test_crop_quote_drops_net(researched):
    ctx, ids = researched
    out = crop_quote_impl(ctx, ids["net"], "these actions will result in no increase in electricity rates")
    assert out.startswith("Made f1"), out
    art = ctx.artifacts["f1"]
    assert art["quote"] == {"text": "These actions will result in no increase in electricity rates.",
                            "speaker": fx.SPEAKER_NET}
    diff = QuoteDiff.model_validate(art["diff"])
    assert diff.original == quote_text(fx.QUOTE_NET)
    assert "net" in diff.removed
    assert diff.removed[0].startswith("Taken together")  # the leading context cut is reported too
    assert diff.removed[-1] == "and a slight decrease in gas rates"
    assert art["evidence_tools"] == ["source"]


def test_crop_quote_contiguous_substring(researched):
    ctx, ids = researched
    out = crop_quote_impl(ctx, ids["peak"], "really unsustainable price hikes in the utility and electricity bills")
    assert out.startswith("Made"), out
    art = ctx.artifacts[out.split()[1]]
    assert art["quote"]["text"] == "Really unsustainable price hikes in the utility and electricity bills."


def test_crop_quote_rejects_added_or_reordered_words(researched):
    ctx, ids = researched
    assert crop_quote_impl(ctx, ids["net"], "these actions will result in no huge increase").startswith("Rejected")
    assert crop_quote_impl(ctx, ids["net"], "increase in electricity rates will result").startswith("Rejected")
    assert ctx.artifacts == {}


def test_crop_quote_rejects_splicing_and_no_op(researched):
    ctx, ids = researched
    spliced = "Taken together the agenda month actions result no increase"
    assert "cuts inside the quote" in crop_quote_impl(ctx, ids["net"], spliced)
    assert "keeps the whole quote" in crop_quote_impl(ctx, ids["net"], fx.QUOTE_NET)
    assert "at least 4 words" in crop_quote_impl(ctx, ids["net"], "no increase")
    assert crop_quote_impl(ctx, "s99", "anything at all here").startswith("Rejected: no saved source")


# ---------------------------------------------------------------- make_chart -> chart diff


def test_make_chart_misleading_matches_seed_case(ctx):
    out = make_chart_impl(ctx, months=["2025-04", "2026-07"], y_min=19)
    assert out.startswith("Made f1 (misleading-chart)"), out
    art = ctx.artifacts["f1"]
    assert art["chart"] == {"type": "bar", "title": "NJ residential electricity price", "unit": "¢/kWh",
                            "points": [{"label": "Apr 2025", "value": 19.91}, {"label": "Jul 2026", "value": 25.19}],
                            "y_min": 19.0, "y_max": 26.0}
    diff = ChartDiff.model_validate(art["diff"])
    assert diff.original.y_min == 0
    assert [(p.label, p.value) for p in diff.original.points] == [("Jul 2025", 25.11), ("Jul 2026", 25.19)]
    data = art["data"]
    assert data["table"][0]["label"] <= "2025-01" and data["table"][-1] == {"label": "2026-08", "value": 24.61}
    assert data["honest_chart"]["y_min"] == 0 and data["honest_chart"]["type"] == "line"
    assert "+0.3%" in data["note"]
    assert "axis starts at 19" in art["default_tell"].lower()
    assert 27.0 in art["allowed_numbers"] and 26.5 in art["allowed_numbers"]


def test_make_chart_rejects_honest_looking_or_hidden_data(ctx):
    assert "isn't misleading" in make_chart_impl(ctx, months=["2025-07", "2026-07"], y_min=0)
    assert "y_min must be between" in make_chart_impl(ctx, months=["2025-04", "2026-07"], y_min=21)
    assert "no EIA data" in make_chart_impl(ctx, months=["2030-01", "2026-07"], y_min=0)
    assert ctx.artifacts == {}


def test_make_chart_honest_for_real_posts(ctx):
    out = make_chart_impl(ctx, months=["2025-07", "2026-07"], honest=True)
    assert out.startswith("Made honest chart c1"), out
    art = ctx.artifacts["c1"]
    assert art["kind"] == "honest_chart" and art["chart"]["y_min"] == 0 and art["chart"]["y_max"] is None
    assert "same month one year apart" in make_chart_impl(ctx, months=["2025-04", "2026-07"], honest=True)
    assert "starts its axis at 0" in make_chart_impl(ctx, months=["2025-07", "2026-07"], y_min=20, honest=True)


def test_make_chart_line_window(ctx):
    out = make_chart_impl(ctx, start="2025-05", end="2025-07", chart_type="line", y_min=20)
    assert out.startswith("Made"), out
    art = ctx.artifacts["f1"]
    assert len(art["chart"]["points"]) == 3 and art["diff"]["original"]["type"] == "line"


# ---------------------------------------------------------------- make_stat_claim -> stat diff


def test_stat_claim_data_mode(ctx):
    out = make_stat_claim_impl(ctx, start_month="2024-06", end_month="2025-06")
    assert out.startswith("Made f1 (cherry-picked-stat, data)"), out
    art = ctx.artifacts["f1"]
    diff = StatDiff.model_validate(art["diff"])
    assert diff.shown == "NJ electricity prices are up 24% in a year."
    assert "19.9" in diff.original and "24.65" in diff.original and "-0.4%" in diff.missing
    assert art["evidence_tools"] == ["data"]


def test_stat_claim_data_mode_rejects_honest_window_and_invented_numbers(ctx):
    assert "would not mislead" in make_stat_claim_impl(ctx, start_month="2025-08", end_month="2026-08")
    out = make_stat_claim_impl(ctx, claim="Prices up 40% in a year!", start_month="2024-06", end_month="2025-06")
    assert "not in the data" in out


def test_stat_claim_source_mode_missing_offset(researched):
    ctx, ids = researched
    out = make_stat_claim_impl(ctx, claim="Shore Electric bills are going UP $4.09 a month.", source_id=ids["ace"],
                               kept_fact="will rise by $4.09", omitted_fact=fx.ACE_FALL)
    assert out.startswith("Made f1"), out
    diff = StatDiff.model_validate(ctx.artifacts["f1"]["diff"])
    assert "4.09" in diff.original and "4.14" in diff.original
    assert diff.missing == "will fall by $4.14."
    assert ctx.artifacts["f1"]["evidence_tools"] == ["source"]


def test_stat_claim_source_mode_guards(researched):
    ctx, ids = researched
    base = dict(source_id=ids["ace"], kept_fact="will rise by $4.09", omitted_fact=fx.ACE_FALL)
    assert "not in kept_fact" in make_stat_claim_impl(ctx, claim="Bills UP $9.99 a month!", **base)
    assert "must be word for word" in make_stat_claim_impl(
        ctx, claim="Bills UP $4.09!", source_id=ids["ace"], kept_fact="will rise by $4.09",
        omitted_fact="will drop by $4.14")
    assert "must contain the number" in make_stat_claim_impl(
        ctx, claim="Bills UP $4.09!", source_id=ids["ace"], kept_fact="will rise by $4.09",
        omitted_fact="will rise by $4.09")
