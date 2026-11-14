"""Agent middleware: Workshop event logging and the forger's dynamic context."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.types import Command

from pipeline.context import RunContext
from pipeline.events import looks_like_spoiler
from pipeline.textutil import clip
from pipeline.tools.research import load_eia

SPOILER_AGENTS = {"forger", "blind-solver"}
FILE_WRITE_TOOLS = {"write_file", "edit_file"}


def result_text(result: Any) -> str:
    if isinstance(result, ToolMessage):
        return result.text if hasattr(result, "text") else str(result.content)
    if isinstance(result, Command):
        update = result.update if isinstance(result.update, dict) else {}
        msgs = update.get("messages") or []
        if msgs:
            last = msgs[-1]
            return getattr(last, "text", None) or str(getattr(last, "content", ""))
    return str(result) if result is not None else ""


def _builtin_summary(name: str, args: dict[str, Any]) -> str | None:
    if name in ("read_file", "write_file", "edit_file"):
        return f"{name} {args.get('file_path') or args.get('path', '')}"
    if name == "ls":
        return f"ls {args.get('path', '/')}"
    if name in ("glob", "grep"):
        return f"{name} {args.get('pattern', '')} {args.get('path', '')}".strip()
    return None


class EventMiddleware(AgentMiddleware):
    """Turns this agent's tool calls into CONTRACT §6 events (plan, sub-agents, tools, files)."""

    def __init__(self, agent_name: str, ctx: RunContext) -> None:
        super().__init__()
        self.agent_name = agent_name
        self.ctx = ctx

    @property
    def name(self) -> str:
        return "WorkshopEventMiddleware"

    def _before(self, call: dict[str, Any]) -> None:
        if call["name"] == "task":
            args = call.get("args") or {}
            sub = str(args.get("subagent_type", "?"))
            desc = str(args.get("description", ""))
            self.ctx.events.emit("subagent_started", name=sub, task=clip(desc, 300),
                                 spoiler=sub == "forger" or looks_like_spoiler(desc))

    def _after(self, call: dict[str, Any], result: Any) -> None:
        name, args = call["name"], call.get("args") or {}
        text = result_text(result)
        ev = self.ctx.events
        if name == "task":
            sub = str(args.get("subagent_type", "?"))
            ev.emit("subagent_finished", name=sub, summary=clip(text, 300),
                    spoiler=sub in SPOILER_AGENTS or looks_like_spoiler(text))
            return
        if name == "write_todos":
            todos = args.get("todos") or []
            ev.emit("plan_updated", todos=todos,
                    spoiler=looks_like_spoiler(*(str(t.get("content", "")) for t in todos if isinstance(t, dict))))
            return
        summary = _builtin_summary(name, args) or clip(text.splitlines()[0] if text else "", 200)
        spoiler = (self.agent_name in SPOILER_AGENTS or name == "submit_for_review"
                   or (self.agent_name == "orchestrator" and looks_like_spoiler(summary)))
        ev.emit("tool_called", agent=self.agent_name, tool=name, summary=summary, spoiler=spoiler)
        if name in FILE_WRITE_TOOLS and not text.lower().startswith("error"):
            ev.emit("file_written", agent=self.agent_name, path=str(args.get("file_path", "")),
                    spoiler=self.agent_name in SPOILER_AGENTS)

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        self._before(request.tool_call)
        result = handler(request)
        self._after(request.tool_call, result)
        return result

    async def awrap_tool_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        self._before(request.tool_call)
        result = await handler(request)
        self._after(request.tool_call, result)
        return result


def forger_context(ctx: RunContext) -> str:
    """The researcher's saved material + EIA numbers + forgeries so far, for the forger's prompt."""
    lines = [f"## This run\nCase id: {ctx.case_id} · topic: {ctx.topic}\nCase shape: {ctx.case_shape()}"]
    lines.append("\n## Saved real sources (verbatim; use these ids)")
    if not ctx.sources:
        lines.append("(none yet)")
    for s in ctx.sources:
        who = f"quote by {s.speaker}" if s.speaker else ("headline" if s.headline else "text")
        lines.append(f"- {s.id} · {s.outlet} · {s.date or 'undated'} · {who}: “{s.text}”"
                     + (f"\n  context after: {clip(s.after, 260)}" if s.after else ""))
    try:
        prices = load_eia(ctx.eia_path)
        recent = [(p, v) for p, v in prices.items() if p >= "2024-01"]
        lines.append("\n## EIA NJ residential price, ¢/kWh (make_chart / make_stat_claim use these)")
        lines.append(" ".join(f"{p}={v}" for p, v in recent))
    except (OSError, KeyError, ValueError):
        pass
    made = [a for a in ctx.artifacts.values()]
    if made:
        lines.append("\n## Made so far")
        for a in made:
            lines.append(f"- {a['id']}: {a.get('trick', a['kind'])}")
    if ctx.solver_history:
        last = ctx.solver_history[-1]
        lines.append(f"\n## Last blind-solver result: {'PASS' if last['pass'] else 'FAIL'}; missed {last['missed']}, "
                     f"false alarms {last['false_alarms']}")
    if ctx.teacher_feedback:
        lines.append("\n## Teacher feedback to address\n" + "\n".join(f"- {f}" for f in ctx.teacher_feedback))
    return "\n".join(lines)


class ForgerContextMiddleware(AgentMiddleware):
    """Appends the run's verified material to the forger's system prompt on every model call.

    Saves a model call (no `list_sources` round-trip) and means the forger never has to retype quotes.
    """

    def __init__(self, ctx: RunContext) -> None:
        super().__init__()
        self.ctx = ctx

    def _override(self, request: Any) -> Any:
        extra = forger_context(self.ctx)
        sm = request.system_message
        base = sm.text if isinstance(sm, SystemMessage) else ""
        return request.override(system_message=SystemMessage(content=(base + "\n\n" + extra).strip()))

    def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        return handler(self._override(request))

    async def awrap_model_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        return await handler(self._override(request))
