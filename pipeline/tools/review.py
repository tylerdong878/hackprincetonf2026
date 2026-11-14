"""`submit_for_review`: the human-in-the-loop gate.

The orchestrator calls it when a case is ready. `interrupt_on={"submit_for_review": ...}` pauses the
graph BEFORE the tool runs; the teacher's decision resumes it:
  approve -> this tool runs and flips meta.status to "approved"
  edit    -> the teacher edited the case files; this tool runs with the edited summary
  reject  -> the tool never runs; the feedback goes back to the orchestrator, which revises
"""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, tool

from pipeline.context import RunContext

AGENT = "orchestrator"


def set_meta_status(ctx: RunContext, status: str, reason: str | None = None) -> dict | None:
    path = ctx.case_dir / "meta.json"
    if not ctx.persist or not path.exists():
        return None
    meta = json.loads(path.read_text(encoding="utf-8"))
    meta["status"] = status
    meta["rejection_reason"] = reason if status == "rejected" else None
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def submit_for_review_impl(ctx: RunContext, case_id: str, summary: str) -> str:
    if case_id != ctx.case_id:
        return f"Error: this run builds case {ctx.case_id}, not {case_id}."
    if not (ctx.case_dir / "meta.json").exists():
        return "Error: no case files yet. Run the forger (write_case) and the blind solver first."
    set_meta_status(ctx, "approved")
    ctx.events.emit("case_status", status="approved")
    return f"Approved by the teacher. Case {case_id} is now in the case bank. Reply with one line and stop."


def review_tools(ctx: RunContext) -> list[BaseTool]:
    @tool
    def submit_for_review(case_id: str, summary: str) -> str:
        """Send the finished case to a teacher for approval (pauses for a human decision).
        summary: 2-3 lines covering the posts, the trick, the blind-solver result and difficulty."""
        return submit_for_review_impl(ctx, case_id, summary)

    return [submit_for_review]
