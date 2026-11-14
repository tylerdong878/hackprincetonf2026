"""Assemble the Deep Agents case builder.

Deep Agents features used here (see README "Pipeline"):
- Planning: `TodoListMiddleware` on the orchestrator (off by default in deepagents 0.7).
- Sub-agents: `researcher` and `forger` (declarative `SubAgent` dicts) and `blind-solver` (a
  `CompiledSubAgent` with no filesystem access), all called through the built-in `task` tool.
- File system: `CompositeBackend` routes `/cases/` and `/skills/` to `FilesystemBackend`s on data/
  (absolute roots, `virtual_mode=True`); scratch stays in agent state. `FilesystemPermission` rules
  deny reading answer keys and writing case/skill files through the file tools.
- Skills: one SKILL.md per trick under data/skills/, given to the forger with `skills=["/skills/"]`.
- Human-in-the-loop: `interrupt_on={"submit_for_review": ...}` + `MemorySaver` checkpointer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from deepagents import (
    CompiledSubAgent,
    FilesystemPermission,
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    SubAgent,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.middleware import UnsupportedContentMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver

from pipeline.context import RunContext
from pipeline.middleware import EventMiddleware, ForgerContextMiddleware
from pipeline.models import ModelSet
from pipeline.prompts import (
    FORGER_DESCRIPTION,
    FORGER_PROMPT,
    ORCHESTRATOR_PROMPT,
    RESEARCHER_DESCRIPTION,
    RESEARCHER_PROMPT,
    SOLVER_DESCRIPTION,
    SOLVER_PROMPT,
)
from pipeline.tools.case_writer import case_tools
from pipeline.tools.forging import forging_tools
from pipeline.tools.research import research_tools
from pipeline.tools.review import review_tools
from pipeline.tools.solver import build_blind_solver, solver_tools

SKILL_SOURCES = ["/skills/"]
FILE_TOOL_NAMES = {"ls", "read_file", "write_file", "edit_file", "glob", "grep", "execute", "delete"}

# Applied to every agent that has the built-in file tools (orchestrator, researcher, forger).
# The blind solver has no file tools at all.
PERMISSIONS = [
    FilesystemPermission(operations=["read", "write"], paths=["/cases/**/answer_key.json"], mode="deny"),
    FilesystemPermission(operations=["write"], paths=["/cases/**", "/skills/**"], mode="deny"),
]

INTERRUPT_ON = {
    "submit_for_review": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": "Teacher approval: the case goes live only after a human approves it.",
    }
}


@dataclass
class AgentBundle:
    agent: Any
    backend: CompositeBackend
    subagents: list[dict[str, Any]]
    solver_graph: Any
    tools_by_agent: dict[str, list[str]] = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)


def make_backend(ctx: RunContext) -> CompositeBackend:
    """`/cases/` -> data/cases, `/skills/` -> data/skills. CompositeBackend strips the route prefix, so each
    route needs its own FilesystemBackend rooted at that folder."""
    cases_root = ctx.cases_dir.resolve()
    skills_root = ctx.skills_dir.resolve()
    if ctx.persist:
        cases_root.mkdir(parents=True, exist_ok=True)
    return CompositeBackend(
        default=StateBackend(),
        routes={
            "/cases/": FilesystemBackend(root_dir=str(cases_root), virtual_mode=True),
            "/skills/": FilesystemBackend(root_dir=str(skills_root), virtual_mode=True),
        },
    )


def _profile_key(model: BaseChatModel) -> str | None:
    from deepagents._models import get_model_identifier, get_model_provider

    ident, prov = get_model_identifier(model), get_model_provider(model)
    if ident and prov:
        return f"{prov}:{ident}"
    return prov or ident


def disable_general_purpose_subagent(model: BaseChatModel) -> None:
    """Drop deepagents' auto-added `general-purpose` sub-agent (it would get every tool plus file access);
    this pipeline uses exactly three purpose-built sub-agents."""
    key = _profile_key(model)
    if key:
        register_harness_profile(key, HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))


def build_solver_runnable(ctx: RunContext, models: ModelSet) -> tuple[Any, list[str]]:
    tools = solver_tools(ctx)
    inner = create_agent(
        models["solver"],
        tools=tools,
        system_prompt=SOLVER_PROMPT,
        # UnsupportedContentMiddleware last: if the text-only fallback model takes over, chart images become notes
        middleware=[EventMiddleware("blind-solver", ctx), *models.middleware_for("solver", "blind-solver", ctx.stats),
                    UnsupportedContentMiddleware()],
        name="blind-solver-agent",
    )
    return build_blind_solver(ctx, inner), [t.name for t in tools]


def build_agent(ctx: RunContext, models: ModelSet, *, checkpointer: Any | None = None) -> AgentBundle:
    ctx.solver_vision = models.solver_vision
    ctx.tool_images = models.tool_images
    backend = make_backend(ctx)
    r_tools = research_tools(ctx)
    f_tools = forging_tools(ctx) + case_tools(ctx)
    o_tools = review_tools(ctx)

    researcher: SubAgent = {
        "name": "researcher",
        "description": RESEARCHER_DESCRIPTION,
        "system_prompt": RESEARCHER_PROMPT,
        "tools": r_tools,
        "model": models["researcher"],
        "middleware": [EventMiddleware("researcher", ctx), *models.middleware_for("researcher", "researcher", ctx.stats)],
        "interrupt_on": {},
    }
    forger: SubAgent = {
        "name": "forger",
        "description": FORGER_DESCRIPTION,
        "system_prompt": FORGER_PROMPT,
        "tools": f_tools,
        "model": models["forger"],
        "skills": SKILL_SOURCES,
        "middleware": [EventMiddleware("forger", ctx), ForgerContextMiddleware(ctx),
                       *models.middleware_for("forger", "forger", ctx.stats)],
        "interrupt_on": {},
    }
    solver_graph, solver_tool_names = build_solver_runnable(ctx, models)
    blind_solver: CompiledSubAgent = {
        "name": "blind-solver",
        "description": SOLVER_DESCRIPTION,
        "runnable": solver_graph,
    }

    disable_general_purpose_subagent(models["orchestrator"])
    agent = create_deep_agent(
        model=models["orchestrator"],
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=o_tools,
        subagents=[researcher, forger, blind_solver],
        middleware=[TodoListMiddleware(), EventMiddleware("orchestrator", ctx),
                    *models.middleware_for("orchestrator", "orchestrator", ctx.stats)],
        backend=backend,
        permissions=PERMISSIONS,
        interrupt_on=INTERRUPT_ON,
        checkpointer=checkpointer if checkpointer is not None else MemorySaver(),
        name="case-builder",
    )
    bundle = AgentBundle(agent=agent, backend=backend, subagents=[researcher, forger, blind_solver],
                         solver_graph=solver_graph)
    bundle.tools_by_agent = introspect_tools(agent)
    bundle.tools_by_agent.setdefault("blind-solver", solver_tool_names)
    bundle.skills = list_skill_names(backend)
    return bundle


# --------------------------------------------------------------------------------------
# Introspection (dry-run + tests): read the tool lists off the COMPILED graphs
# --------------------------------------------------------------------------------------


def _tool_nodes(graph: Any, depth: int = 0) -> list[Any]:
    from langgraph.prebuilt import ToolNode

    found: list[Any] = []
    g = getattr(graph, "bound", graph)
    nodes = getattr(g, "nodes", None) or {}
    for node in nodes.values():
        bound = getattr(node, "bound", None)
        if isinstance(bound, ToolNode):
            found.append(bound)
        elif bound is not None and depth < 4 and hasattr(getattr(bound, "bound", bound), "nodes"):
            found.extend(_tool_nodes(bound, depth + 1))
    return found


def graph_tool_names(graph: Any) -> list[str]:
    names: list[str] = []
    for tn in _tool_nodes(graph):
        names.extend(tn.tools_by_name.keys())
    return sorted(set(names))


def _task_subagent_graphs(agent: Any) -> dict[str, Any]:
    for tn in _tool_nodes(agent):
        task = tn.tools_by_name.get("task")
        if task is None:
            continue
        fn = getattr(task, "func", None)
        if fn is None or not fn.__closure__:
            continue
        for name, cell in zip(fn.__code__.co_freevars, fn.__closure__, strict=False):
            if name == "subagent_graphs":
                return dict(cell.cell_contents)
    return {}


def introspect_tools(agent: Any) -> dict[str, list[str]]:
    out = {"orchestrator": graph_tool_names(agent)}
    for name, runnable in _task_subagent_graphs(agent).items():
        out[name] = graph_tool_names(runnable)
    return out


def list_skill_names(backend: Any) -> list[str]:
    try:
        from deepagents.middleware.skills import _list_skills

        return sorted(s["name"] for s in _list_skills(backend, SKILL_SOURCES[0]))
    except Exception:  # noqa: BLE001
        return []
