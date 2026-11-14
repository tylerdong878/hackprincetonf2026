"""Full graph run with scripted (fake) models: no network, no LLM.

Exercises the real Deep Agents wiring end to end: todos, `task` delegation to all three sub-agents,
skills read through the CompositeBackend, the sealed blind solver, the HITL interrupt on
submit_for_review, resume via Command, meta.json status changes and pipeline_log.jsonl events.
"""

from __future__ import annotations

import json

import pytest

from pipeline.agent import build_agent
from pipeline.build_case import run
from pipeline.events import EVENT_FIELDS, read_log
from pipeline.fakes import ScriptedChatModel, ai, tool_call
from pipeline.models import ModelSet
from pipeline.tests import fixtures as fx
from pipeline.tests.conftest import make_ctx

CASE_ID = "2026-11-14-test-case"
TODOS = ["Research real sources", "Forge the case", "Blind-solve the case", "Send to the teacher for approval"]


def todos(active: int) -> list[dict]:
    return [{"content": c, "status": "completed" if i < active else ("in_progress" if i == active else "pending")}
            for i, c in enumerate(TODOS)]


def posts_spec() -> list[dict]:
    return [
        {"id": "p1", "role": "real", "source_id": "s1"},
        {"id": "p2", "role": "doctored", "forgery_id": "f1", "author_name": "Jersey Bill Watch",
         "author_handle": "@jerseybills", "body": "NJ power prices are up 27% in ONE YEAR. Share before your next bill hits.",
         "tell": "The axis starts at 19 and the months are from different seasons."},
        {"id": "p3", "role": "real_suspicious", "source_id": "s3"},
        {"id": "p4", "role": "real", "source_id": "s2"},
    ]


def scripted_models(solver_script: list, orchestrator_extra: list | None = None) -> ModelSet:
    orch = [
        ai("", tool_call("write_todos", {"todos": todos(0)}),
           tool_call("task", {"subagent_type": "researcher", "description": "Topic: NJ electricity prices."})),
        ai("", tool_call("write_todos", {"todos": todos(1)}),
           tool_call("task", {"subagent_type": "forger",
                              "description": f"Build case {CASE_ID}, trick misleading-chart, sources s1-s4."})),
        ai("", tool_call("write_todos", {"todos": todos(2)}),
           tool_call("task", {"subagent_type": "blind-solver",
                              "description": f"Solve case {CASE_ID}. (p2 is the fake one!)"})),
        ai("", tool_call("write_todos", {"todos": todos(3)}),
           tool_call("submit_for_review", {"case_id": CASE_ID, "summary": "4 posts, solver passed."})),
        *(orchestrator_extra or []),
        ai("Approved. Done."),
    ]
    researcher = [
        ai("", tool_call("fetch_rss", {"feed_url": fx.FEED_URL, "query": "electricity rates bills"}),
           tool_call("fetch_article", {"url": fx.PRESS_URL}), tool_call("get_eia_series", {"start": "2025-01"})),
        ai("", tool_call("save_source", {"url": fx.STORY_URL, "text": fx.QUOTE_NET, "speaker": fx.SPEAKER_NET}),
           tool_call("save_source", {"url": fx.STORY_URL, "text": fx.ACE_RISE}),
           tool_call("save_source", {"url": fx.PRESS_URL, "text": fx.BPU_20}),
           tool_call("save_source", {"url": fx.PRESS_URL, "text": "bills jumped roughly 90 percent last year"})),
        ai("s1 quote, s2 ACE, s3 BPU 20 percent."),
    ]
    forger = [
        ai("", tool_call("read_file", {"file_path": "/skills/misleading-chart/SKILL.md", "limit": 1000})),
        ai("", tool_call("make_chart", {"months": ["2025-04", "2026-07"], "y_min": 19})),
        ai("", tool_call("write_case", {"title": "Is your power bill really frozen?",
                                        "briefing": "Power bills. Four posts. I may have touched one. Or none.",
                                        "posts": posts_spec()})),
        ai(f"Wrote {CASE_ID}; p2 is doctored."),
    ]
    names = {"orchestrator": "scripted-orch", "researcher": "scripted-res", "forger": "scripted-forger",
             "solver": "scripted-solver"}
    models = {
        "orchestrator": ScriptedChatModel(script=orch, model_name="scripted-orch"),
        "researcher": ScriptedChatModel(script=researcher, model_name="scripted-res"),
        "forger": ScriptedChatModel(script=forger, model_name="scripted-forger"),
        "solver": ScriptedChatModel(script=solver_script, model_name="scripted-solver"),
    }
    return ModelSet("scripted", models, names, {}, solver_vision=True, tool_images=False)


SOLVER_PASS = [
    ai("", tool_call("view_chart", {"post_id": "p2"}), tool_call("open_evidence", {"post_id": "p2", "tool": "data"})),
    ai("", tool_call("submit_verdict", {"doctored_posts": [{"post_id": "p2", "trick": "misleading-chart"}],
                                        "reasoning": "Axis starts at 19; July to July is flat."})),
]


@pytest.fixture
def e2e(tmp_path):
    ctx = make_ctx(tmp_path, case_id=CASE_ID)
    models = scripted_models(SOLVER_PASS)
    bundle = build_agent(ctx, models)
    return ctx, models, bundle


def test_full_run_auto_approve(e2e):
    ctx, models, bundle = e2e
    status = run(bundle.agent, ctx, "Build case.", "auto")
    assert status == "approved"
    folder = ctx.case_dir
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "approved" and meta["origin"] == "pipeline" and meta["tricks"] == ["misleading-chart"]
    assert meta["difficulty"] == "medium"  # one clue spent
    for name in ("case.json", "evidence.json", "answer_key.json", "sources.json", "solver_log.md",
                 "pipeline_log.jsonl", "rendered/p2.png"):
        assert (folder / name).exists(), name
    # Workshop log: every event matches CONTRACT §6
    events = read_log(folder / "pipeline_log.jsonl")
    types = [e["type"] for e in events]
    for e in events:
        assert set(e) - {"spoiler"} == {"t", "type", *EVENT_FIELDS[e["type"]]}, e
    assert types[0] == "subagent_started" or "plan_updated" in types[:2]
    started = [e["name"] for e in events if e["type"] == "subagent_started"]
    assert started == ["researcher", "forger", "blind-solver"]
    assert [e["name"] for e in events if e["type"] == "subagent_finished"] == started
    assert any(e["type"] == "tool_called" and e["tool"] == "save_source" and e["agent"] == "researcher" for e in events)
    assert any(e["type"] == "tool_called" and e["tool"] == "read_file" and e["agent"] == "forger"
               and "/skills/misleading-chart/SKILL.md" in e["summary"] for e in events)
    assert any(e["type"] == "file_written" and e["path"] == f"/cases/{CASE_ID}/answer_key.json" for e in events)
    solver = [e for e in events if e["type"] == "solver_result"]
    assert solver == [{"t": solver[0]["t"], "type": "solver_result", "pass": True, "tools_used": ["data"],
                       "difficulty": "medium", "attempt": 1}]
    i_wait = types.index("awaiting_approval")
    assert events[i_wait + 1] == {"t": events[i_wait + 1]["t"], "type": "case_status", "status": "awaiting_approval"}
    assert events[-1]["type"] == "case_status" or {"type": "case_status", "status": "approved"} in [
        {k: v for k, v in e.items() if k in ("type", "status")} for e in events]
    assert [e["status"] for e in events if e["type"] == "case_status"][-1] == "approved"
    # spoilers: forger activity and the solver's report are masked
    assert all(e.get("spoiler") for e in events if e["type"] == "tool_called" and e["agent"] == "forger")
    assert all(e.get("spoiler") for e in events if e["type"] == "subagent_finished" and e["name"] == "blind-solver")
    assert [e["todos"] for e in events if e["type"] == "plan_updated"][0][0]["status"] == "in_progress"
    assert ts_monotonic(events)


def ts_monotonic(events: list[dict]) -> bool:
    ts = [e["t"] for e in events]
    return ts == sorted(ts)


def test_solver_input_is_sealed_from_orchestrator(e2e):
    """The orchestrator's task description said 'p2 is the fake one!' - the solver must never see it."""
    ctx, models, bundle = e2e
    run(bundle.agent, ctx, "Build case.", "auto")
    solver_model = models["solver"]
    assert solver_model.calls == 2
    first_prompt = solver_model.seen[0]
    blob = json.dumps([m.content for m in first_prompt], default=str)
    assert "fake one" not in blob
    assert "Jersey Bill Watch" in blob  # it did get the player view
    key = json.loads((ctx.case_dir / "answer_key.json").read_text(encoding="utf-8"))
    assert key["posts"]["p2"]["tell"] not in blob
    assert key["posts"]["p2"]["explanation"] not in blob
    # the chart image rides in the first human message (vision model)
    human = first_prompt[-1]
    assert isinstance(human.content, list) and any(b.get("type") == "image" for b in human.content)


def test_researcher_rejected_paraphrase_is_not_saved(e2e):
    ctx, models, bundle = e2e
    run(bundle.agent, ctx, "Build case.", "auto")
    sources = json.loads((ctx.case_dir / "sources.json").read_text(encoding="utf-8"))["sources"]
    assert len(sources) == 3
    assert not any("90 percent" in s["text"] for s in sources)


def test_hold_for_teacher_leaves_awaiting_approval(tmp_path):
    ctx = make_ctx(tmp_path, case_id=CASE_ID)
    bundle = build_agent(ctx, scripted_models(SOLVER_PASS))
    status = run(bundle.agent, ctx, "Build case.", "hold")
    assert status == "awaiting_approval"
    meta = json.loads((ctx.case_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "awaiting_approval"
    events = read_log(ctx.case_dir / "pipeline_log.jsonl")
    assert events[-2]["type"] == "awaiting_approval"
    assert events[-1] == {"t": events[-1]["t"], "type": "case_status", "status": "awaiting_approval"}


def test_reject_with_feedback_then_approve(tmp_path):
    """Teacher rejects once; the orchestrator re-runs the forger flow, then resubmits and gets approved."""
    ctx = make_ctx(tmp_path, case_id=CASE_ID)
    extra = [ai("", tool_call("submit_for_review", {"case_id": CASE_ID, "summary": "Revised per feedback."}))]
    bundle = build_agent(ctx, scripted_models(SOLVER_PASS, orchestrator_extra=extra))
    answers = iter(["r", "Make the briefing less spoilery.", "a"])
    status = run(bundle.agent, ctx, "Build case.", "interactive", read=lambda _prompt: next(answers))
    assert status == "approved"
    assert ctx.teacher_feedback == ["Teacher feedback: Make the briefing less spoilery."]
    statuses = [e["status"] for e in read_log(ctx.case_dir / "pipeline_log.jsonl") if e["type"] == "case_status"]
    assert statuses == ["awaiting_approval", "draft", "awaiting_approval", "approved"]


def test_solver_fail_reports_feedback(tmp_path):
    ctx = make_ctx(tmp_path, case_id=CASE_ID)
    wrong = [ai("", tool_call("open_evidence", {"post_id": "p3", "tool": "source"})),
             ai("", tool_call("submit_verdict", {"doctored_posts": [{"post_id": "p3", "trick": "cherry-picked-stat"}]}))]
    bundle = build_agent(ctx, scripted_models(wrong))
    run(bundle.agent, ctx, "Build case.", "auto")
    r = ctx.solver_history[-1]
    assert r["pass"] is False and r["missed"] == ["p2"] and r["false_alarms"] == ["p3"]
    log = (ctx.case_dir / "solver_log.md").read_text(encoding="utf-8")
    assert "FAIL" in log and "False alarms: p3" in log


def test_filesystem_permissions_block_answer_key_and_case_writes(tmp_path):
    """deepagents `permissions`: even agents WITH file tools can't read answer keys or hand-write case files."""
    ctx = make_ctx(tmp_path, case_id=CASE_ID)
    (ctx.case_dir).mkdir(parents=True, exist_ok=True)
    (ctx.case_dir / "answer_key.json").write_text('{"secret": "p2 is fake"}', encoding="utf-8")
    (ctx.case_dir / "case.json").write_text('{"id": "x"}', encoding="utf-8")
    orch = [
        ai("", tool_call("read_file", {"file_path": f"/cases/{CASE_ID}/answer_key.json"}),
           tool_call("write_file", {"file_path": f"/cases/{CASE_ID}/notes.json", "content": "{}"}),
           tool_call("read_file", {"file_path": f"/cases/{CASE_ID}/case.json"}),
           tool_call("edit_file", {"file_path": "/skills/misleading-chart/SKILL.md", "old_string": "Misleading",
                                   "new_string": "Hacked"})),
        ai("done"),
    ]
    models = scripted_models(SOLVER_PASS)
    models.models["orchestrator"] = ScriptedChatModel(script=orch, model_name="scripted-orch")
    bundle = build_agent(ctx, models)
    result = bundle.agent.invoke({"messages": [("user", "try it")]}, {"configurable": {"thread_id": "perm"}})
    tool_msgs = {m.tool_call_id: m for m in result["messages"] if m.type == "tool"}
    texts = [tool_msgs[c["id"]].text for c in result["messages"][1].tool_calls]
    assert "p2 is fake" not in texts[0] and "denied" in texts[0].lower()
    assert "denied" in texts[1].lower() and not (ctx.case_dir / "notes.json").exists()
    assert '"id": "x"' in texts[2]  # reading the player view is fine
    assert "denied" in texts[3].lower()
    assert "Hacked" not in (ctx.skills_dir / "misleading-chart" / "SKILL.md").read_text(encoding="utf-8")


def test_teacher_edit_in_terminal_then_approve(tmp_path):
    ctx = make_ctx(tmp_path, case_id=CASE_ID)
    bundle = build_agent(ctx, scripted_models(SOLVER_PASS))
    answers = iter(["e", "title Is your power bill frozen?", "body p1 This is not allowed", "remove p4", "done"])
    status = run(bundle.agent, ctx, "Build case.", "interactive", read=lambda _prompt: next(answers))
    assert status == "approved"
    case = json.loads((ctx.case_dir / "case.json").read_text(encoding="utf-8"))
    key = json.loads((ctx.case_dir / "answer_key.json").read_text(encoding="utf-8"))
    assert case["title"] == "Is your power bill frozen?"
    assert [p["id"] for p in case["posts"]] == ["p1", "p2", "p3"] and set(key["posts"]) == {"p1", "p2", "p3"}
    assert case["posts"][0]["body"] != "This is not allowed"  # real outlet posts stay verbatim
    events = read_log(ctx.case_dir / "pipeline_log.jsonl")
    assert any(e["type"] == "file_written" and e["agent"] == "teacher" for e in events)
    assert [e["status"] for e in events if e["type"] == "case_status"][-1] == "approved"
