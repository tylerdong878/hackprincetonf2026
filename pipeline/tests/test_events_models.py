"""pipeline_log.jsonl formatting (CONTRACT §6) and model-call accounting."""

from __future__ import annotations

import json

import pytest

from pipeline.events import EVENT_FIELDS, EventLog, looks_like_spoiler, make_event, read_log
from pipeline.models import (
    CallBudgetExceeded,
    CallStats,
    DailyCapReached,
    ModelCallMiddleware,
    NoModelConfigured,
    classify_error,
    make_models,
)

# ---------------------------------------------------------------- events


def test_make_event_matches_contract_shapes():
    assert make_event("plan_updated", 1.416, todos=[{"content": "Research", "status": "in_progress"}]) == {
        "t": 1.42, "type": "plan_updated", "todos": [{"content": "Research", "status": "in_progress"}]}
    assert make_event("solver_result", 30, **{"pass": 1}, tools_used=("data",), difficulty="medium", attempt="1") == {
        "t": 30.0, "type": "solver_result", "pass": True, "tools_used": ["data"], "difficulty": "medium", "attempt": 1}
    assert make_event("awaiting_approval", 31) == {"t": 31.0, "type": "awaiting_approval"}
    assert make_event("tool_called", 2, agent="forger", tool="make_chart", summary="x", spoiler=True)["spoiler"] is True
    assert "spoiler" not in make_event("case_status", 3, status="approved")
    assert list(make_event("file_written", 1, agent="forger", path="/cases/x/case.json")) == [
        "t", "type", "agent", "path"]


def test_make_event_rejects_malformed():
    with pytest.raises(ValueError):
        make_event("made_up", 1)
    with pytest.raises(ValueError):
        make_event("tool_called", 1, agent="x", tool="y")  # missing summary
    with pytest.raises(ValueError):
        make_event("case_status", 1, status="live")
    with pytest.raises(ValueError):
        make_event("subagent_started", 1, name="r", task="t", extra="nope")


def test_todo_status_is_coerced():
    ev = make_event("plan_updated", 0, todos=[{"content": "A", "status": "done"}, {"content": "B"}])
    assert [t["status"] for t in ev["todos"]] == ["pending", "pending"]


def test_event_log_writes_jsonl_with_elapsed_time(tmp_path):
    clock = iter([100.0, 101.5, 103.25])
    log = EventLog(tmp_path / "c" / "pipeline_log.jsonl", clock=lambda: next(clock))
    log.emit("subagent_started", name="researcher", task="Find sources")
    log.emit("case_status", status="awaiting_approval")
    lines = (tmp_path / "c" / "pipeline_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["t"] for x in lines] == [1.5, 3.25]
    for e in read_log(tmp_path / "c" / "pipeline_log.jsonl"):
        assert set(e) - {"spoiler"} == {"t", "type", *EVENT_FIELDS[e["type"]]}


def test_spoiler_heuristic():
    assert looks_like_spoiler("Forge a misleading chart for p2")
    assert looks_like_spoiler("crop the quote")
    assert not looks_like_spoiler("Research real sources")
    assert not looks_like_spoiler("Send to the teacher for approval")


# ---------------------------------------------------------------- model calls


class Err(Exception):
    def __init__(self, msg: str, status: int | None = None) -> None:
        super().__init__(msg)
        self.status_code = status


def test_classify_error():
    assert classify_error(Err("Rate limit exceeded: free-models-per-min", 429)) == "rate"
    assert classify_error(Err("Rate limit exceeded: free-models-per-day", 429)) == "daily"
    assert classify_error(Err("upstream overloaded", 503)) == "transient"
    assert classify_error(Err("bad request", 400)) == "other"


def test_call_budget_and_throttle():
    now = [0.0]
    slept: list[float] = []
    stats = CallStats(max_calls=2, rpm=20, reserve=0, sleep=lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)),
                      clock=lambda: now[0])
    stats.before_call("orchestrator")
    stats.before_call("forger")
    assert slept == [3.0]  # 60 / 20 rpm
    with pytest.raises(CallBudgetExceeded):
        stats.before_call("forger")
    assert stats.by_agent == {"orchestrator": 1, "forger": 1}


def test_middleware_retries_rate_limits_and_counts_every_request():
    stats = CallStats(max_calls=10, rpm=0, sleep=lambda s: None)
    mw = ModelCallMiddleware("researcher", stats, retry_delays=(1, 1))
    attempts = iter([Err("rate limit", 429), Err("upstream", 502), "ok"])

    def handler(_req):
        v = next(attempts)
        if isinstance(v, Exception):
            raise v
        return v

    assert mw.wrap_model_call(object(), handler) == "ok"
    assert stats.total == 3 and stats.failed == 2 and stats.retries == 2


def test_middleware_stops_on_daily_cap_and_other_errors():
    stats = CallStats(max_calls=10, rpm=0, sleep=lambda s: None)
    mw = ModelCallMiddleware("researcher", stats)
    with pytest.raises(DailyCapReached):
        mw.wrap_model_call(object(), lambda r: (_ for _ in ()).throw(Err("free-models-per-day", 429)))
    with pytest.raises(Err):
        mw.wrap_model_call(object(), lambda r: (_ for _ in ()).throw(Err("bad", 400)))
    assert stats.total == 2


def test_make_models_requires_a_key(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "PIPELINE_PROVIDER"):
        monkeypatch.setenv(k, "")
    monkeypatch.setattr("pipeline.models.load_env", lambda: None)
    with pytest.raises(NoModelConfigured):
        make_models()


def test_make_models_openrouter_config(monkeypatch):
    monkeypatch.setattr("pipeline.models.load_env", lambda: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-not-real")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("PIPELINE_PROVIDER", "")
    monkeypatch.delenv("PIPELINE_FALLBACK_MODEL", raising=False)
    ms = make_models()
    assert ms.provider == "openrouter"
    orch, solver = ms["orchestrator"], ms["solver"]
    assert orch.model_name == "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert solver.model_name == "nvidia/nemotron-3.5-super-vl:free"
    assert orch.openrouter_provider == {"require_parameters": True} and orch.max_retries == 0
    # default fallback on timeouts/errors: the fast Lightning model
    assert [m.model_name for m in ms.fallback["orchestrator"]] == ["nvidia/nemotron-3.5-lightning:free"]
    assert ms.fallback["orchestrator"][0].max_retries == 0
    mws = ms.middleware_for("orchestrator", "orchestrator", CallStats())
    assert [m.name for m in mws][:2] == ["ModelFallbackMiddleware", "ModelCallMiddleware"]
    assert mws[1].retry_timeouts is False  # a timeout switches model instead of waiting again
    assert "NemotronTextToolCallParser" in [m.name for m in mws]
    monkeypatch.setenv("PIPELINE_FALLBACK_MODEL", "")
    no_fb = make_models()
    assert not no_fb.fallback
    mws = no_fb.middleware_for("orchestrator", "orchestrator", CallStats())
    assert mws[0].name == "ModelCallMiddleware" and mws[0].retry_timeouts is True


def test_make_models_gemini_fallback(monkeypatch):
    monkeypatch.setattr("pipeline.models.load_env", lambda: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-not-real")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test-not-real")
    monkeypatch.setenv("PIPELINE_PROVIDER", "")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    ms = make_models()
    assert set(ms.fallback) == {"orchestrator", "researcher", "forger", "solver"}
    chain = [getattr(m, "model_name", None) or m.model for m in ms.fallback["forger"]]
    assert chain[0] == "nvidia/nemotron-3.5-lightning:free" and chain[-1].endswith("gemini-test-model")
    names = [m.name for m in ms.middleware_for("forger", "forger", CallStats())]
    assert names[:2] == ["ModelFallbackMiddleware", "ModelCallMiddleware"]
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    only_gemini = make_models()
    assert only_gemini.provider == "gemini" and only_gemini.tool_images is True
    assert only_gemini.names["orchestrator"] == "gemini-test-model"  # GEMINI_MODEL, never hard-coded


def test_call_with_deadline():
    import time

    from pipeline.models import DeadlineExceeded, call_with_deadline

    assert call_with_deadline(lambda: 42, 1.0) == 42
    with pytest.raises(DeadlineExceeded):
        call_with_deadline(lambda: time.sleep(2), 0.05)
    with pytest.raises(KeyError):
        call_with_deadline(lambda: {}["missing"], 1.0)


def test_middleware_deadline_retries_once_then_gives_up():
    import time

    from pipeline.models import DeadlineExceeded

    stats = CallStats(max_calls=10, rpm=0, sleep=lambda s: None)
    mw = ModelCallMiddleware("forger", stats, retry_delays=(0, 0, 0), deadline_s=0.05, retry_timeouts=True)
    with pytest.raises(DeadlineExceeded):
        mw.wrap_model_call(object(), lambda r: time.sleep(1))
    assert stats.total == 2  # first try + one retry on the same model, both counted
    stats2 = CallStats(max_calls=10, rpm=0, sleep=lambda s: None)
    mw2 = ModelCallMiddleware("forger", stats2, deadline_s=0.05, retry_timeouts=False)
    with pytest.raises(DeadlineExceeded):
        mw2.wrap_model_call(object(), lambda r: time.sleep(1))
    assert stats2.total == 1  # with a fallback configured, switch models at once
    assert mw2.wrap_model_call(object(), lambda r: "fast") == "fast"
