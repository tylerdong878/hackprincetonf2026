"""Build one Grain of Salt case with the Deep Agents pipeline.

  uv run python -m pipeline.build_case --topic "NJ electricity prices"
  uv run python -m pipeline.build_case --topic "NJ electricity prices" --clean --auto-approve
  uv run python -m pipeline.build_case --hold-for-teacher        # teacher approves later in the web UI
  uv run python -m pipeline.build_case --mode daily --daily-date 2026-11-15 --theme "Your Bills"
  uv run python -m pipeline.build_case --dry-run                 # build the graph, no model calls

Writes data/cases/<id>/{sources.json, case.json, evidence.json, answer_key.json, meta.json,
solver_log.md, pipeline_log.jsonl, rendered/*.png}. Needs OPENROUTER_API_KEY (or GEMINI_API_KEY) in .env.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.config import CASES_DIR, DATA_DIR, TRICKS, load_env

DAILY_MAX_CALLS = 25  # PLAN_V2 §1A: one daily = one pipeline run of about 15-25 model calls
from pipeline.context import RunContext
from pipeline.events import EventLog
from pipeline.safety import SafetyError, check_blocklist
from pipeline.textutil import clip

APPROVAL_MODES = ("interactive", "auto", "hold")


# --------------------------------------------------------------------------------------
# Terminal output
# --------------------------------------------------------------------------------------


def _echo(event: dict[str, Any]) -> None:
    t, kind = event["t"], event["type"]
    if kind == "plan_updated":
        marks = {"completed": "x", "in_progress": ">", "pending": " "}
        line = "plan: " + " | ".join(f"[{marks[td['status']]}] {td['content']}" for td in event["todos"])
    elif kind == "subagent_started":
        line = f"-> {event['name']} started: {clip(event['task'], 120)}"
    elif kind == "subagent_finished":
        line = f"<- {event['name']} finished: {clip(event['summary'], 160)}"
    elif kind == "tool_called":
        line = f"   {event['agent']}.{event['tool']}: {clip(event['summary'], 140)}"
    elif kind == "file_written":
        line = f"   {event['agent']} wrote {event['path']}"
    elif kind == "solver_result":
        line = (f"** solver attempt {event['attempt']}: {'PASS' if event['pass'] else 'FAIL'} "
                f"(difficulty {event['difficulty']}, tools {event['tools_used']})")
    elif kind == "case_status":
        line = f"** case status: {event['status']}"
    else:
        line = f"** {kind}"
    print(f"[{t:7.1f}s] {line}", flush=True)


def _setup_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


# --------------------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------------------


def user_request(ctx: RunContext, hints: str, trick_reason: str) -> str:
    extra = ("\nDaily build: keep the whole run within about 25 model calls. The researcher should save 6-7 short "
             "passages, including at least one exact headline." if ctx.is_daily else "")
    return (f"Build case {ctx.case_id}.\nTopic: {ctx.topic}\nCase shape: {ctx.case_shape()} ({trick_reason})\n"
            f"Research hints:\n{hints}\nBlind-solver retries allowed: {ctx.max_solver_attempts - 1}.{extra}")


def run_settings(args: argparse.Namespace, now: datetime, cases_dir: Path = CASES_DIR) -> dict[str, Any]:
    """RunContext fields + the trick reason for these CLI args (no model, no files written)."""
    from pipeline.topics import choose_trick, make_case_id, plan_daily, theme_for

    if args.mode == "daily":
        daily_date = args.daily_date or now.astimezone(_eastern()).strftime("%Y-%m-%d")
        try:
            datetime.strptime(daily_date, "%Y-%m-%d")
        except ValueError as exc:
            raise SystemExit(f"--daily-date must be YYYY-MM-DD (got {daily_date!r})") from exc
        n = 0 if args.clean else args.doctored
        tricks, reason = plan_daily(daily_date, n)
        if args.trick and tricks:
            tricks[0] = args.trick
        case_id = args.case_id or _unique(f"daily-{daily_date}", cases_dir)
        return {"case_id": case_id, "mode": "daily", "daily_date": daily_date, "tricks": tricks,
                "theme": args.theme or theme_for(args.topic), "clean": not tricks, "trick": None, "reason": reason}
    case_id = args.case_id or make_case_id(args.topic, cases_dir, clean=args.clean, now=now)
    if args.clean:
        trick, reason = None, "clean case"
    elif args.trick:
        trick, reason = args.trick, "chosen by the operator"
    else:
        profile = DATA_DIR / "players" / args.player / "profile.json" if args.player else None
        trick, reason = choose_trick(profile)
    return {"case_id": case_id, "mode": "casefile", "clean": args.clean, "trick": trick, "reason": reason}


def _unique(base: str, cases_dir: Path) -> str:
    cid, n = base, 2
    while (cases_dir / cid).exists():
        cid, n = f"{base}-{n}", n + 1
    return cid


def _eastern() -> Any:
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("America/New_York")  # the Daily resets at midnight ET (PLAN_V2 §1A)
    except Exception:  # noqa: BLE001
        return UTC


def case_files_exist(ctx: RunContext) -> bool:
    return all((ctx.case_dir / n).exists() for n in ("case.json", "evidence.json", "answer_key.json", "meta.json"))


def review_summary(ctx: RunContext, action: dict[str, Any]) -> str:
    case, key = ctx.read_json("case.json"), ctx.read_json("answer_key.json")
    lines = [f"\n=== Teacher review: {case['id']} (#{case['number']}) \"{case['title']}\" ===",
             f"Briefing: {case['briefing']}"]
    for p in case["posts"]:
        a = key["posts"][p["id"]]
        tag = f"DOCTORED {a['trick']}" if a["doctored"] else ("real (looks suspicious)" if a["suspicious_real"] else "real")
        content = p["body"] or ""
        if p.get("quote"):
            content += f" “{p['quote']['text']}” — {p['quote']['speaker']}"
        if p.get("chart"):
            ch = p["chart"]
            content += " [chart " + ", ".join(f"{pt['label']} {pt['value']}" for pt in ch["points"][:4]) \
                       + f"; axis from {ch['y_min']:g}]"
        lines.append(f"  {p['id']} {p['author']['name']} ({p['author']['kind']}): {tag}\n      {clip(content, 220)}")
        if a["doctored"]:
            lines.append(f"      tell: {clip(a['tell'], 200)}")
    if ctx.solver_history:
        r = ctx.solver_history[-1]
        lines.append(f"Blind solver: {'PASS' if r['pass'] else 'FAIL'} on attempt {r['attempt']}, difficulty "
                     f"{r['difficulty']}, opened {', '.join(r['opened']) or 'nothing'}")
    lines.append(f"Agent's summary: {clip(str(action.get('args', {}).get('summary', '')), 400)}")
    lines.append(f"Files: {ctx.case_dir}")
    return "\n".join(lines)


def _apply_meta_status(ctx: RunContext, status: str, reason: str | None = None) -> None:
    from pipeline.tools.review import set_meta_status

    set_meta_status(ctx, status, reason)
    ctx.events.emit("case_status", status=status)


def terminal_edit(ctx: RunContext, read: Callable[[str], str] = input) -> str | None:
    """Minimal in-terminal editor. Returns a note describing the edits, or None if cancelled."""
    from pipeline.tools.forging import CON_CLEAN
    from pipeline.schemas import validate_bundle

    case, ev, key, meta = (ctx.read_json(n) for n in ("case.json", "evidence.json", "answer_key.json", "meta.json"))
    notes: list[str] = []
    print("Edit commands: title <text> | briefing <text> | body <post> <text> | remove <post> | done | cancel\n"
          "(real posts are verbatim and can't be re-worded; you can remove them)")
    while True:
        cmd = read("edit> ").strip()
        if not cmd:
            continue
        op, _, rest = cmd.partition(" ")
        if op == "cancel":
            return None
        if op == "done":
            break
        if op in ("title", "briefing") and rest:
            case[op] = rest.strip()
            notes.append(f"{op} edited")
        elif op == "body":
            pid, _, text = rest.partition(" ")
            post = next((p for p in case["posts"] if p["id"] == pid), None)
            if post is None:
                print("no such post")
                continue
            if not key["posts"][pid]["doctored"] and post["author"]["kind"] != "person":
                print("real outlet posts are verbatim; remove the post instead")
                continue
            post["body"] = text.strip()
            notes.append(f"{pid} body edited")
        elif op == "remove":
            pid = rest.strip()
            if pid not in key["posts"] or len(case["posts"]) <= 3:
                print("can't remove (unknown post, or a case needs at least 3 posts)")
                continue
            case["posts"] = [p for p in case["posts"] if p["id"] != pid]
            ev.pop(pid, None)
            removed = key["posts"].pop(pid)
            if removed.get("doctored"):
                key["clean_case"], key["con_line_clean"] = True, CON_CLEAN
                meta["tricks"] = []
            notes.append(f"{pid} removed")
        else:
            print("unknown command")
    try:
        texts = [case["title"], case["briefing"]] + [p["body"] for p in case["posts"]]
        check_blocklist(texts, what="edited case")
        validate_bundle(case, ev, key, meta)
    except (SafetyError, ValueError) as exc:
        print(f"Edits not saved: {exc}")
        return None
    for name, obj in (("case.json", case), ("evidence.json", ev), ("answer_key.json", key), ("meta.json", meta)):
        ctx.write_json(name, obj, "teacher")
    return "; ".join(notes) or "no changes"


def decide(ctx: RunContext, action: dict[str, Any], mode: str, read: Callable[[str], str] = input
           ) -> dict[str, Any] | str:
    """Return a HITL decision dict, or 'hold' / 'discard'."""
    if mode == "auto":
        print("--auto-approve: approving.")
        return {"type": "approve"}
    if mode == "hold":
        return "hold"
    while True:
        choice = read("[a]pprove  [r]eject with feedback (agent revises)  [e]dit here  [x] reject & stop  "
                      "[h]old for the web UI > ").strip().lower()
        if choice in ("a", "approve"):
            return {"type": "approve"}
        if choice in ("r", "reject"):
            fb = read("Feedback for the agent: ").strip() or "Please revise the case."
            return {"type": "reject", "message": f"Teacher feedback: {fb}"}
        if choice in ("e", "edit"):
            note = terminal_edit(ctx, read)
            if note is None:
                continue
            args = dict(action.get("args") or {})
            args["summary"] = f"{args.get('summary', '')} [Teacher edits: {note}]".strip()
            return {"type": "edit", "edited_action": {"name": action.get("name", "submit_for_review"), "args": args}}
        if choice in ("x",):
            return "discard"
        if choice in ("h", "hold"):
            return "hold"


def run(agent: Any, ctx: RunContext, request: str, mode: str, read: Callable[[str], str] = input) -> str:
    """Drive the agent to completion or to a hold. Returns the final meta status."""
    from langchain_core.messages import HumanMessage
    from langgraph.types import Command

    # Named, tagged run so it's easy to find and show in LangSmith (ignored when tracing is off).
    config = {
        "configurable": {"thread_id": ctx.case_id},
        "run_name": f"Grain of Salt · build {ctx.case_id}",
        "tags": ["grain-of-salt", "case-builder", ctx.mode],
        "metadata": {"case_id": ctx.case_id, "topic": ctx.topic, "mode": ctx.mode,
                     "daily_date": ctx.daily_date, "theme": ctx.theme},
    }
    payload: Any = {"messages": [HumanMessage(content=request)]}
    while True:
        for _chunk in agent.stream(payload, config, stream_mode="updates"):
            pass  # Workshop events are emitted by the agents' middleware as tools run
        snapshot = agent.get_state(config)
        interrupts = list(getattr(snapshot, "interrupts", ()) or ())
        if not interrupts:
            break
        value = interrupts[0].value or {}
        actions = value.get("action_requests") or []
        action = actions[0] if actions else {"name": "submit_for_review", "args": {}}
        if not case_files_exist(ctx):
            payload = Command(resume={"decisions": [{"type": "reject", "message":
                                                     "No case files exist yet. Run the forger and the blind solver first."}
                                                    for _ in actions]})
            continue
        ctx.events.emit("awaiting_approval")
        _apply_meta_status(ctx, "awaiting_approval")
        print(review_summary(ctx, action))
        decision = decide(ctx, action, mode, read)
        if decision == "hold":
            print(f"Holding for the teacher: meta.status stays 'awaiting_approval'. Approve in the web UI "
                  f"(teacher queue) or edit {ctx.case_dir / 'meta.json'}.")
            return "awaiting_approval"
        if decision == "discard":
            _apply_meta_status(ctx, "rejected", "Rejected by the teacher in the terminal.")
            return "rejected"
        if decision["type"] == "reject":
            ctx.teacher_feedback.append(decision["message"])
            ctx.solver_round_base = len(ctx.solver_history)
            _apply_meta_status(ctx, "draft")
        payload = Command(resume={"decisions": [decision] + [{"type": "approve"} for _ in actions[1:]]})
    if (ctx.case_dir / "meta.json").exists():
        return ctx.read_json("meta.json")["status"]
    return "draft"


# --------------------------------------------------------------------------------------
# Dry run
# --------------------------------------------------------------------------------------


def dry_run(topic: str, settings: dict[str, Any]) -> int:
    from pipeline.agent import FILE_TOOL_NAMES, INTERRUPT_ON, PERMISSIONS, SKILL_SOURCES, build_agent
    from pipeline.models import placeholder_models

    models = placeholder_models()
    ctx = RunContext(topic=topic, persist=False, events=EventLog(None), **dict(settings, case_id="dry-run-case"))
    bundle = build_agent(ctx, models)
    tools = bundle.tools_by_agent
    print("Grain of Salt case builder: DRY RUN (placeholder models; no network, nothing written)\n")
    print(f"Case shape: {ctx.case_shape()}")
    print(f"Blind-solver attempts: {ctx.max_solver_attempts}; Con the Con judge: pipeline.fool.judge_post "
          "(1 evidence check, 2 model calls)\n")
    print(f"Orchestrator  model={models.names['orchestrator']}")
    print(f"  tools: {', '.join(tools.get('orchestrator', []))}")
    print("  middleware: TodoListMiddleware (planning), WorkshopEventMiddleware, ModelCallMiddleware "
          "(count/throttle/retry), Nemotron repair; deepagents adds Filesystem, SubAgent, Summarization, "
          "HumanInTheLoop, ModelRefusal")
    print("Sub-agents (via the `task` tool):")
    for spec in bundle.subagents:
        name = spec["name"]
        kind = "CompiledSubAgent (sealed: seal -> solve -> grade)" if "runnable" in spec else "SubAgent"
        model = models.names["solver" if name == "blind-solver" else name]
        print(f"  {name:13s} {kind}  model={model}")
        print(f"    tools: {', '.join(tools.get(name, []))}")
        if spec.get("skills"):
            print(f"    skills: {spec['skills']} -> {', '.join(bundle.skills)}")
    print("Backend: CompositeBackend(default=StateBackend)")
    for prefix, be in bundle.backend.routes.items():
        print(f"  {prefix:9s} -> FilesystemBackend(root_dir={be.cwd}, virtual_mode={be.virtual_mode})")
    print("Permissions: " + "; ".join(f"{p.mode} {'/'.join(p.operations)} {p.paths}" for p in PERMISSIONS))
    cfg = INTERRUPT_ON["submit_for_review"]
    print(f"Human-in-the-loop: interrupt_on submit_for_review {cfg['allowed_decisions']}, checkpointer=MemorySaver")
    print(f"Skills found under {SKILL_SOURCES[0]}: {', '.join(bundle.skills) or 'NONE'}")
    leaked = sorted(set(tools.get("blind-solver", [])) & (FILE_TOOL_NAMES | {"task"}))
    ok = not leaked and set(tools.get("blind-solver", [])) == {"open_evidence", "view_chart", "submit_verdict"}
    print(f"Blind-solver isolation: {'OK (no file tools, no task tool)' if ok else 'FAILED: ' + str(leaked)}")
    print(f"Skills OK: {set(bundle.skills) == set(TRICKS)}")
    return 0 if ok and set(bundle.skills) == set(TRICKS) else 1


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="python -m pipeline.build_case", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic", default="NJ electricity prices")
    ap.add_argument("--mode", choices=("casefile", "daily"), default="casefile",
                    help="casefile = v1 4-post feed; daily = Daily Grain (5 posts, 0-3 doctored, CONTRACT §7.1)")
    ap.add_argument("--daily-date", help="daily mode: YYYY-MM-DD (default: today, New Jersey time)")
    ap.add_argument("--theme", help="daily mode: display theme, e.g. 'Your Bills' (default from the topic)")
    ap.add_argument("--doctored", type=int, choices=(0, 1, 2, 3),
                    help="daily mode: number of doctored posts (default: planned from the weekday)")
    ap.add_argument("--clean", action="store_true", help="build a clean case (no doctored post)")
    ap.add_argument("--trick", choices=TRICKS, help="force a trick (default: from --player profile, else random)")
    ap.add_argument("--player", help="player id: pick the trick from data/players/<id>/profile.json (SPEC §7.3)")
    ap.add_argument("--case-id", help="override the case id (default <date>-<topic-slug>)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--auto-approve", action="store_true", help="approve at the human-in-the-loop pause")
    g.add_argument("--hold-for-teacher", action="store_true",
                   help="stop at the pause; meta.status stays awaiting_approval for the web UI")
    ap.add_argument("--dry-run", action="store_true", help="build the agent graph with a placeholder model and exit")
    ap.add_argument("--max-calls", type=int, help="cap on model requests this run (default PIPELINE_MAX_CALLS or 45)")
    ap.add_argument("--quiet", action="store_true", help="don't print events as they happen")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _setup_console()
    args = parse_args(argv)
    load_env()
    try:
        check_blocklist([args.topic], what="topic")
    except SafetyError as exc:
        print(exc)
        return 2
    now = datetime.now(UTC)
    settings = run_settings(args, now)
    reason = settings.pop("reason")
    if args.dry_run:
        return dry_run(args.topic, settings)

    from pipeline.agent import build_agent
    from pipeline.models import CallBudgetExceeded, CallStats, DailyCapReached, NoModelConfigured, make_models
    from pipeline.topics import hints_text

    try:
        models = make_models()
    except NoModelConfigured as exc:
        print(exc)
        return 2
    case_id = settings["case_id"]
    stats = CallStats.from_env()
    if args.max_calls:
        stats.max_calls = args.max_calls
    elif settings["mode"] == "daily" and "PIPELINE_MAX_CALLS" not in os.environ:
        stats.max_calls = DAILY_MAX_CALLS
    log_path = CASES_DIR / case_id / "pipeline_log.jsonl"
    events = EventLog(log_path, echo=None if args.quiet else _echo)
    ctx = RunContext(topic=args.topic, events=events, stats=stats, now=now, **settings)
    mode = "auto" if args.auto_approve else ("hold" if args.hold_for_teacher else "interactive")
    print(f"Building {case_id} · topic '{args.topic}' · {ctx.case_shape()} · provider {models.provider} "
          f"({models.names['orchestrator']}; solver {models.names['solver']}) · approval {mode} · "
          f"cap {stats.max_calls} calls")
    bundle = build_agent(ctx, models)
    status = "draft"
    try:
        status = run(bundle.agent, ctx, user_request(ctx, hints_text(args.topic), reason), mode)
    except (CallBudgetExceeded, DailyCapReached) as exc:
        print(f"\nStopped: {exc}")
        if case_files_exist(ctx):
            _apply_meta_status(ctx, "draft")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
        if case_files_exist(ctx):
            _apply_meta_status(ctx, "draft")
        return 130
    except Exception as exc:  # noqa: BLE001  # e.g. ModelRefusalError, provider outage
        print(f"\nRun failed: {type(exc).__name__}: {clip(str(exc), 500)}")
        if case_files_exist(ctx):
            _apply_meta_status(ctx, "draft")
        return 1
    finally:
        print(f"\nModel usage: {stats.summary()}")
    print(f"Case {case_id}: status {status}. Folder: {ctx.case_dir}")
    if log_path.exists():
        print(f"Workshop log: {log_path} ({len(events.events)} events)")
    return 0 if status in ("approved", "awaiting_approval") else 1


if __name__ == "__main__":
    sys.exit(main())
