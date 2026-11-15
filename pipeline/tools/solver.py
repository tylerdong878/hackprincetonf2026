"""Blind solver: plays the case like a player, with no access to the answer key.

Isolation is structural, not a prompt instruction:
- The solver is a `CompiledSubAgent` built with plain `langchain.agents.create_agent`, so it gets
  NO filesystem middleware (no ls/read_file/glob/grep) and no `task` tool.
- Its only tools read `case.json` (the player view) and `evidence.json`, by fixed file name.
- A `seal` node discards whatever the orchestrator wrote in the task description and rebuilds the
  solver's input from `case.json` alone, so the orchestrator cannot leak the answer either.
- Grading happens afterwards, in code (`grade` node), which is the only reader of answer_key.json.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from pydantic import BaseModel, Field

from pipeline.charts import render_chart_png
from pipeline.config import EVIDENCE_TOOLS, TRICKS
from pipeline.context import RunContext, SolverSession
from pipeline.textutil import clip

AGENT = "blind-solver"
TrickOrUnknown = Literal["out-of-context-quote", "misleading-chart", "cherry-picked-stat", "edited-detail",
                         "made-up-story", "unknown"]


# --------------------------------------------------------------------------------------
# Tools (player-equivalent)
# --------------------------------------------------------------------------------------


def _case(ctx: RunContext) -> dict:
    return ctx.read_json("case.json")


def _post(case: dict, post_id: str) -> dict | None:
    return next((p for p in case["posts"] if p["id"] == post_id), None)


def _compact_evidence(tool_id: str, payload: dict) -> dict:
    if tool_id != "data":
        return payload
    hc = payload.get("honest_chart") or {}
    pts = hc.get("points") or []
    return {
        "title": payload.get("title"), "unit": payload.get("unit"), "url": payload.get("url"),
        "table": payload.get("table"), "note": payload.get("note"),
        "honest_chart": {"type": hc.get("type"), "y_min": hc.get("y_min"), "points": len(pts),
                         "first": pts[0] if pts else None, "last": pts[-1] if pts else None},
    }


def open_evidence_impl(ctx: RunContext, post_id: str, tool_id: str) -> str:
    if not re.fullmatch(r"p\d+", post_id or "") or tool_id not in EVIDENCE_TOOLS:
        return f"Error: post_id looks like 'p2' and tool is one of {list(EVIDENCE_TOOLS)}."
    case = _case(ctx)
    post = _post(case, post_id)
    if post is None:
        return f"Error: no post {post_id}. Posts: {[p['id'] for p in case['posts']]}."
    if tool_id not in post["tools"]:
        return f"Error: {post_id} has no '{tool_id}' evidence. Available: {post['tools']}."
    key = (post_id, tool_id)
    budget = int(case.get("clue_budget", 3))
    with ctx.lock:  # parallel opens in one turn must not overspend the budget
        if key not in ctx.solver.opened:
            if len(ctx.solver.opened) >= budget:
                return (f"Out of clue tokens ({budget}/{budget} used). Decide with what you have and call "
                        "submit_verdict.")
            ctx.solver.opened.append(key)
        used = len(ctx.solver.opened)
    evidence = ctx.read_json("evidence.json")  # never answer_key.json
    payload = evidence[post_id][tool_id]
    return (f"Clue {used}/{budget} ({post_id}/{tool_id}).\n"
            + json.dumps(_compact_evidence(tool_id, payload), ensure_ascii=False, indent=1))


def chart_spec_text(post_id: str, chart: dict) -> str:
    pts = ", ".join(f"{p['label']} = {p['value']}" for p in chart["points"])
    top = chart.get("y_max")
    return (f"{post_id} chart: {chart['type']} '{chart['title']}' ({chart['unit']}). Points: {pts}. "
            f"Y-axis from {chart['y_min']:g} to {'auto' if top is None else f'{top:g}'}.")


def render_post_chart(ctx: RunContext, post_id: str) -> bytes | None:
    post = _post(_case(ctx), post_id)
    if not post or not post.get("chart"):
        return None
    path = ctx.case_dir / "rendered" / f"{post_id}.png" if ctx.persist else None
    return render_chart_png(post["chart"], path)


def view_chart_impl(ctx: RunContext, post_id: str) -> str | list[dict[str, Any]]:
    post = _post(_case(ctx), post_id)
    if post is None or not post.get("chart"):
        return f"Error: {post_id} has no chart."
    spec = chart_spec_text(post_id, post["chart"]) + " (Free: players can see this chart.)"
    png = render_post_chart(ctx, post_id)
    if post_id not in ctx.solver.viewed_charts:
        ctx.solver.viewed_charts.append(post_id)
        if ctx.persist:
            ctx.events.emit("file_written", agent=AGENT, path=ctx.vpath(f"rendered/{post_id}.png"))
    if ctx.tool_images and png:
        return [{"type": "text", "text": spec},
                {"type": "image", "base64": base64.b64encode(png).decode(), "mime_type": "image/png"}]
    return spec + (" The rendered image is attached to your briefing." if ctx.solver_vision else "")


class Flag(BaseModel):
    post_id: str = Field(description="e.g. p2")
    trick: TrickOrUnknown = Field(description="the trick you think was used")


def submit_verdict_impl(ctx: RunContext, doctored_posts: list[Flag | dict], reasoning: str = "") -> str:
    flags = []
    for f in doctored_posts or []:
        f = f if isinstance(f, Flag) else Flag.model_validate(f)
        flags.append({"post_id": f.post_id, "trick": f.trick})
    ctx.solver.verdict = {"flagged": flags, "reasoning": clip(reasoning, 600)}
    return "Verdict recorded."


def solver_tools(ctx: RunContext) -> list[BaseTool]:
    @tool
    def open_evidence(post_id: str, tool: str) -> str:
        """Open one evidence tool for one post: 'source' (the original article passage), 'data' (the real
        dataset), or 'account' (the poster's profile). Costs 1 clue token the first time; reopening is free."""
        return open_evidence_impl(ctx, post_id, tool)

    @tool
    def view_chart(post_id: str) -> str | list:
        """Look at a post's chart exactly as players see it (numbers + axis range; image when supported). Free."""
        return view_chart_impl(ctx, post_id)

    @tool(return_direct=True)
    def submit_verdict(doctored_posts: list[Flag], reasoning: str = "") -> str:
        """Final answer, call once: the posts you believe are doctored, each with a trick (empty list if every
        post is real), plus one or two sentences of reasoning."""
        return submit_verdict_impl(ctx, doctored_posts, reasoning)

    return [open_evidence, view_chart, submit_verdict]


# --------------------------------------------------------------------------------------
# The sealed briefing (built from case.json only)
# --------------------------------------------------------------------------------------


TRICK_GUIDE = (
    "Tricks the Con uses: out-of-context-quote (a real quote cut so it changes meaning; check the source), "
    "misleading-chart (cropped axis or cherry-picked months; check the data), cherry-picked-stat (a true number "
    "missing its offset, baseline or denominator; check the data or source), edited-detail (one number, date or "
    "place swapped in a real headline; check the source)."
)


MADE_UP_GUIDE = (" made-up-story (a whole claim the Con invented, posted by a made-up account with no source; "
                 "real news can be strange too, so check the source before calling it).")


def post_lines(p: dict, *, with_time: bool = True) -> list[str]:
    """A post as plain text, using only player-visible fields (shared by the case solver and the Con judge)."""
    a = p["author"]
    head = f"[{p['id']}] {a['name']} ({a['handle']}, {a['kind']}{', verified' if a.get('verified') else ''})"
    if with_time and p.get("posted_at"):
        head += f" · {p['posted_at']}"
    if p.get("source_label"):
        head += f" · cites: {p['source_label']}"
    lines = [head]
    if p.get("body"):
        lines.append(f"  text: {p['body']}")
    if p.get("quote"):
        lines.append(f"  quote: \"{p['quote']['text']}\" — {p['quote']['speaker']}")
    if p.get("chart"):
        lines.append("  " + chart_spec_text(p["id"], p["chart"]))
    lines.append(f"  evidence tools: {', '.join(p['tools'])}")
    return lines


def image_blocks(post: dict, png: bytes | None) -> list[dict[str, Any]]:
    if not png:
        return []
    return [{"type": "text", "text": f"Chart in {post['id']} as players see it:"},
            {"type": "image", "base64": base64.b64encode(png).decode(), "mime_type": "image/png"}]


def sealed_briefing(ctx: RunContext, *, attach_images: bool) -> HumanMessage:
    case = _case(ctx)
    lines = [
        f"Case {case['id']}: \"{case['title']}\". The Con says: \"{case['briefing']}\"",
        f"You have {case['clue_budget']} clue tokens. open_evidence(post_id, tool) spends one per new "
        "(post, tool) pair; view_chart is free.",
        TRICK_GUIDE + (MADE_UP_GUIDE if "made-up-story" in (case.get("trick_options") or []) else "")
        + " Some cases have NO doctored post at all, and real posts can look dramatic.",
        "",
        "Feed:",
    ]
    for p in case["posts"]:
        lines.extend(post_lines(p))
    lines += ["", "Investigate, then call submit_verdict exactly once."]
    text = "\n".join(lines)
    if not attach_images:
        return HumanMessage(content=text)
    blocks: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for p in case["posts"]:
        if p.get("chart"):
            blocks.extend(image_blocks(p, render_post_chart(ctx, p["id"])))
    return HumanMessage(content=blocks)


# --------------------------------------------------------------------------------------
# Grading (code only)
# --------------------------------------------------------------------------------------

_PAIR_RE = re.compile(r"\b(p\d)\b[^\n]{0,60}?\b(" + "|".join(TRICKS) + r")\b", re.IGNORECASE)
_NONE_RE = re.compile(r"\b(?:no|none of the)\s+posts?\s+(?:are|is|was|were|look)\s+(?:doctored|fake)|"
                      r"\ball\s+(?:\w+\s+)?(?:posts\s+)?(?:are\s+)?real\b", re.IGNORECASE)


def verdict_from_text(text: str) -> dict | None:
    pairs = _PAIR_RE.findall(text or "")
    if pairs:
        return {"flagged": [{"post_id": p.lower(), "trick": t.lower()} for p, t in dict(pairs).items()],
                "reasoning": "(parsed from the solver's reply; it did not call submit_verdict)"}
    if _NONE_RE.search(text or ""):
        return {"flagged": [], "reasoning": "(parsed: solver said every post is real)"}
    return None


def difficulty_for(passed: bool, clues: int) -> str:
    if not passed:
        return "hard"
    return "easy" if clues == 0 else ("medium" if clues == 1 else "hard")


def grade_attempt(ctx: RunContext, final_text: str = "") -> dict[str, Any]:
    key = ctx.read_json("answer_key.json")
    truth = {pid: a["trick"] for pid, a in key["posts"].items() if a["doctored"]}
    verdict = ctx.solver.verdict or verdict_from_text(final_text)
    session = ctx.solver
    opened = [f"{p}/{t}" for p, t in session.opened]
    tools_used = [t for t in EVIDENCE_TOOLS if any(x == t for _, x in session.opened)]
    if verdict is None:
        passed, missed, false_alarms, flagged = False, sorted(truth), [], {}
    else:
        flagged = {f["post_id"]: f["trick"] for f in verdict["flagged"]}
        missed = sorted(set(truth) - set(flagged))
        false_alarms = sorted(set(flagged) - set(truth))
        passed = not missed and not false_alarms
    trick_ok = all(flagged.get(pid) == trick for pid, trick in truth.items()) if verdict else False
    result = {
        "attempt": session.attempt, "pass": passed, "difficulty": difficulty_for(passed, len(session.opened)),
        "tools_used": tools_used, "opened": opened, "clues": len(session.opened),
        "flagged": flagged, "truth": truth, "missed": missed, "false_alarms": false_alarms,
        "trick_named": trick_ok, "reasoning": (verdict or {}).get("reasoning", "(no verdict submitted)"),
    }
    ctx.solver_history.append(result)
    return result


def feedback_text(ctx: RunContext, r: dict[str, Any]) -> str:
    round_attempt = r["attempt"] - ctx.solver_round_base
    left = ctx.max_solver_attempts - round_attempt
    head = f"Blind solver attempt {round_attempt}/{ctx.max_solver_attempts}: {'PASS' if r['pass'] else 'FAIL'}"
    opened = ", ".join(r["opened"]) or "no evidence"
    if r["pass"]:
        what = (", ".join(f"{p} as {t}" for p, t in r["flagged"].items()) or "nothing (clean case)")
        return (f"{head} (difficulty {r['difficulty']}). It flagged {what} after opening {opened}"
                f"{'' if r['trick_named'] or not r['truth'] else ' (trick name was off; still a pass)'}. "
                "Next: submit_for_review.")
    parts = [f"{head}. Opened: {opened}. Its reasoning: {clip(r['reasoning'], 240)}"]
    for pid in r["missed"]:
        parts.append(f"Missed doctored post {pid} ({r['truth'][pid]}): its evidence kit doesn't expose the trick "
                     "clearly enough. Make the tell checkable with the post's evidence (bigger crop / clearer "
                     "omission / a window the data table contradicts).")
    for pid in r["false_alarms"]:
        parts.append(f"False alarm on real post {pid}: make sure its evidence plainly confirms it, or use a less "
                     "ambiguous real post.")
    parts.append(f"Retries left: {left}." if left > 0 else
                 "No retries left: call submit_for_review and say the solver failed.")
    return " ".join(parts)


def append_solver_log(ctx: RunContext, r: dict[str, Any]) -> None:
    if not ctx.persist:
        return
    path = ctx.case_dir / "solver_log.md"
    new = not path.exists()
    with path.open("a", encoding="utf-8") as fh:
        if new:
            fh.write(f"# Blind solver log: {ctx.case_id}\n\n")
            fh.write("The blind solver plays the case with the player's tools only (case.json + evidence.json, "
                     f"{ctx.clue_budget} clue tokens). It cannot read answer_key.json; grading is done in code.\n\n")
            if ctx.safety_notes:
                fh.write(f"Safety checks at write time: {'; '.join(ctx.safety_notes)}.\n\n")
        fh.write(f"## Attempt {r['attempt']}: {'PASS' if r['pass'] else 'FAIL'} (difficulty {r['difficulty']})\n\n")
        fh.write(f"- Evidence opened ({r['clues']} clues): {', '.join(r['opened']) or 'none'}\n")
        fh.write(f"- Flagged as doctored: {', '.join(f'{p} ({t})' for p, t in r['flagged'].items()) or 'none'}\n")
        fh.write(f"- Actually doctored: {', '.join(f'{p} ({t})' for p, t in r['truth'].items()) or 'none (clean case)'}\n")
        if r["missed"]:
            fh.write(f"- Missed: {', '.join(r['missed'])}\n")
        if r["false_alarms"]:
            fh.write(f"- False alarms: {', '.join(r['false_alarms'])}\n")
        fh.write(f"- Trick named correctly: {'yes' if r['trick_named'] else 'no'}\n")
        fh.write(f"- Solver's reasoning: {r['reasoning']}\n\n")
    ctx.events.emit("file_written", agent=AGENT, path=ctx.vpath("solver_log.md"))


def _update_meta_difficulty(ctx: RunContext, difficulty: str) -> None:
    if not ctx.persist or not (ctx.case_dir / "meta.json").exists():
        return
    meta = ctx.read_json("meta.json")
    meta["difficulty"] = difficulty
    (ctx.case_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------
# The compiled, sealed sub-agent
# --------------------------------------------------------------------------------------


class SolverOutput(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class SolverState(SolverOutput, total=False):
    ready: bool  # internal: never returned to the orchestrator


def build_blind_solver(ctx: RunContext, inner_agent: Any) -> Any:
    """seal -> solve (inner create_agent graph) -> grade. Returns a compiled LangGraph graph."""

    def seal(state: SolverState) -> dict[str, Any]:
        reset = [RemoveMessage(id=REMOVE_ALL_MESSAGES)]
        attempt = len(ctx.solver_history) + 1
        if not (ctx.case_dir / "case.json").exists():
            return {"messages": reset + [HumanMessage(content="(no case)")], "ready": False}
        if attempt - ctx.solver_round_base > ctx.max_solver_attempts:
            return {"messages": reset + [HumanMessage(content="(retry limit)")], "ready": False}
        ctx.solver = SolverSession(attempt=attempt)
        return {"messages": reset + [sealed_briefing(ctx, attach_images=ctx.solver_vision)], "ready": True}

    def route(state: SolverState) -> str:
        return "solve" if state.get("ready") else "grade"

    def grade(state: SolverState) -> dict[str, Any]:
        if not state.get("ready"):
            if not (ctx.case_dir / "case.json").exists():
                msg = "No case files yet: run the forger (write_case) before the blind solver."
            else:
                msg = (f"Retry limit reached ({ctx.max_solver_attempts} attempts). Call submit_for_review and report "
                       "the last solver result.")
            return {"messages": [AIMessage(content=msg)]}
        final_text = ""
        for m in reversed(state.get("messages", [])):
            if isinstance(m, AIMessage) and m.text:
                final_text = m.text
                break
        r = grade_attempt(ctx, final_text)
        ctx.events.emit("solver_result", **{"pass": r["pass"]}, tools_used=r["tools_used"],
                        difficulty=r["difficulty"], attempt=r["attempt"])
        _update_meta_difficulty(ctx, r["difficulty"])
        append_solver_log(ctx, r)
        return {"messages": [AIMessage(content=feedback_text(ctx, r))]}

    g = StateGraph(SolverState, input_schema=SolverOutput, output_schema=SolverOutput)
    g.add_node("seal", seal)
    g.add_node("solve", inner_agent)
    g.add_node("grade", grade)
    g.add_edge(START, "seal")
    g.add_conditional_edges("seal", route, {"solve": "solve", "grade": "grade"})
    g.add_edge("solve", "grade")
    g.add_edge("grade", END)
    return g.compile(name=AGENT)
