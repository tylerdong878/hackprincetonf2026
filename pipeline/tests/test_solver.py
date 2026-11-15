"""Blind solver: structurally unable to read the answer key; graded in code."""

from __future__ import annotations

import json

import pytest

from pipeline.agent import FILE_TOOL_NAMES, build_agent, graph_tool_names
from pipeline.models import placeholder_models
from pipeline.tests.conftest import research
from pipeline.tests.test_case_writer import chart_case
from pipeline.tools.case_writer import write_case_impl
from pipeline.tools.solver import (
    difficulty_for,
    grade_attempt,
    open_evidence_impl,
    sealed_briefing,
    submit_verdict_impl,
    verdict_from_text,
    view_chart_impl,
)

READ_TOOLS = FILE_TOOL_NAMES | {"task", "read_answer_key"}


@pytest.fixture
def written(ctx):
    ids = research(ctx)
    out = write_case_impl(ctx, "Is your power bill really frozen?", "Four posts. Maybe one is mine.",
                          chart_case(ctx, ids))
    assert out.startswith("Wrote"), out
    ctx.solver.attempt = 1
    return ctx


# ---------------------------------------------------------------- isolation (structural)


def test_blind_solver_has_no_file_reading_tools(tmp_path):
    """Read off the COMPILED graphs: the solver sub-agent the orchestrator calls has only player tools."""
    from pipeline.tests.conftest import make_ctx

    ctx = make_ctx(tmp_path)
    bundle = build_agent(ctx, placeholder_models())
    solver_tools = set(bundle.tools_by_agent["blind-solver"])
    assert solver_tools == {"open_evidence", "view_chart", "submit_verdict"}
    assert not solver_tools & READ_TOOLS
    assert set(graph_tool_names(bundle.solver_graph)) == solver_tools
    # contrast: the declarative sub-agents DO get deepagents' file tools (that's what the solver avoids)
    assert {"read_file", "ls", "grep"} <= set(bundle.tools_by_agent["forger"])
    assert "general-purpose" not in bundle.tools_by_agent


def test_open_evidence_reads_evidence_only_and_spends_clues(written):
    ctx = written
    out = open_evidence_impl(ctx, "p2", "data")
    assert out.startswith("Clue 1/3 (p2/data)")
    assert "doctored" not in out and "tell" not in out and "con_line" not in out
    assert open_evidence_impl(ctx, "p2", "data").startswith("Clue 1/3")  # re-open is free
    open_evidence_impl(ctx, "p1", "source")
    open_evidence_impl(ctx, "p3", "source")
    assert open_evidence_impl(ctx, "p4", "source").startswith("Out of clue tokens")
    assert [f"{p}/{t}" for p, t in ctx.solver.opened] == ["p2/data", "p1/source", "p3/source"]


@pytest.mark.parametrize("post_id,tool", [("../answer_key", "source"), ("p2", "answer_key"), ("p9", "source"),
                                          ("p2", "source")])
def test_open_evidence_rejects_bad_requests(written, post_id, tool):
    out = open_evidence_impl(written, post_id, tool)
    assert out.startswith("Error")
    assert written.solver.opened == []


def test_sealed_briefing_is_player_view_only(written):
    ctx = written
    key = json.loads((ctx.case_dir / "answer_key.json").read_text(encoding="utf-8"))
    msg = sealed_briefing(ctx, attach_images=False)
    text = msg.content
    assert "Jersey Bill Watch" in text and "Y-axis from 19 to 26" in text
    for ans in key["posts"].values():
        assert ans["explanation"] not in text
    assert key["posts"]["p2"]["tell"] not in text
    with_images = sealed_briefing(ctx, attach_images=True)
    images = [b for b in with_images.content if b.get("type") == "image"]
    assert len(images) == 1 and images[0]["mime_type"] == "image/png"


def test_sealed_briefing_images_survive_openrouter_formatting(written):
    """ChatOpenRouter turns the briefing's image block into an OpenAI-style image_url part."""
    from langchain_openrouter.chat_models import _convert_message_to_dict

    msg = sealed_briefing(written, attach_images=True)
    d = _convert_message_to_dict(msg)
    parts = d["content"]
    assert any(p.get("type") == "image_url" and p["image_url"]["url"].startswith("data:image/png;base64,")
               for p in parts)


def test_view_chart_text_and_image_modes(written):
    ctx = written
    out = view_chart_impl(ctx, "p2")
    assert isinstance(out, str) and "Apr 2025 = 19.91" in out
    assert (ctx.case_dir / "rendered" / "p2.png").read_bytes()[:4] == b"\x89PNG"
    ctx.tool_images = True
    blocks = view_chart_impl(ctx, "p2")
    assert [b["type"] for b in blocks] == ["text", "image"]
    assert view_chart_impl(ctx, "p1").startswith("Error")


# ---------------------------------------------------------------- grading (code only)


def test_grade_pass_and_difficulty(written):
    ctx = written
    open_evidence_impl(ctx, "p2", "data")
    submit_verdict_impl(ctx, [{"post_id": "p2", "trick": "misleading-chart"}], "axis")
    r = grade_attempt(ctx)
    assert r["pass"] and r["difficulty"] == "medium" and r["tools_used"] == ["data"] and r["trick_named"]


def test_grade_fail_missed_and_false_alarm(written):
    ctx = written
    submit_verdict_impl(ctx, [{"post_id": "p3", "trick": "cherry-picked-stat"}])
    r = grade_attempt(ctx)
    assert not r["pass"] and r["missed"] == ["p2"] and r["false_alarms"] == ["p3"] and r["difficulty"] == "hard"


def test_grade_without_verdict_is_fail(written):
    r = grade_attempt(written, "I think something is off.")
    assert r["pass"] is False


def test_difficulty_mapping():
    assert [difficulty_for(True, n) for n in (0, 1, 2, 3)] == ["easy", "medium", "hard", "hard"]
    assert difficulty_for(False, 0) == "hard"


def test_verdict_from_text():
    assert verdict_from_text("Doctored: p2 (misleading-chart).")["flagged"] == [
        {"post_id": "p2", "trick": "misleading-chart"}]
    assert verdict_from_text("None of the posts are doctored.")["flagged"] == []
    assert verdict_from_text("hmm") is None


def test_clean_case_pass_when_nothing_flagged(tmp_path):
    from pipeline.tests.conftest import make_ctx
    from pipeline.tools.forging import make_chart_impl

    ctx = make_ctx(tmp_path, clean=True, trick=None)
    ids = research(ctx)
    make_chart_impl(ctx, months=["2025-07", "2026-07"], honest=True)
    posts = [{"id": "p1", "role": "real", "source_id": ids["net"]},
             {"id": "p2", "role": "real_suspicious", "chart_id": "c1", "author_name": "Calm Down Daily",
              "author_handle": "@calmdowndaily"},
             {"id": "p3", "role": "real", "source_id": ids["bpu20"]}]
    assert write_case_impl(ctx, "Who's driving your bill?", "Three posts. Mine? Maybe.", posts).startswith("Wrote")
    ctx.solver.attempt = 1
    submit_verdict_impl(ctx, [], "All sourced and consistent with EIA.")
    r = grade_attempt(ctx)
    assert r["pass"] and r["difficulty"] == "easy" and r["truth"] == {}
