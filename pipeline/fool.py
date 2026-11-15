"""Con the Con (CONTRACT §7.3, §7.4, §8): the player doctors a real Fool Deck post, the Con judges it live.

    apply_edit(deck_item, edit) -> {"edited_post", "changed", "trick", "diff"}     deterministic, no model
    edited_author(deck_item) -> author                                             the made-up account (§8.3)
    judge_post(edited_post, evidence, level=3) -> con dict                         1-2 model calls, or ConAsleep

Con levels (§8.1): 1 = Rookie Con (no evidence, one verdict call), 2 = Street Con (one evidence check on the fast
fallback model), 3 = Master Con (one evidence check on the full models).

The judge is the pipeline's blind solver in miniature, with the same isolation:
- It only gets the post's player-visible content and the evidence kit, never the deck item, the edit, `changed`,
  `trick` or `diff`.
- It is ALSO blind to who posted it. apply_edit swaps a changed post to a made-up account (§8.3) while an untouched
  post keeps its real outlet, so the author would give the answer away. The judge sees every post as shared by
  the same neutral reposter, with no source label and the same account card, and must decide from the content
  versus the evidence.
- At most one open_evidence call: only the first requested tool is opened, and the verdict call has no evidence
  tool at all. At level 1 there is no evidence call.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import Field, create_model

from pipeline.charts import render_chart_png
from pipeline.config import EVIDENCE_TOOLS
from pipeline.config import TWIST_TRICKS as TRICKS  # players only edit real posts here
from pipeline.safety import RealEntity, fictional_author_problems, known_entities, person_name_part
from pipeline.textutil import clip, month_label, normalize, sentence_spans
from pipeline.tools.forging import MIN_KEPT_WORDS, crop_tokens
from pipeline.tools.solver import _compact_evidence, image_blocks, post_lines

EDIT_TYPES = ("none", "crop", "axis", "window", "drop")
EDIT_TRICK = {"crop": "out-of-context-quote", "axis": "misleading-chart", "window": "misleading-chart",
              "drop": "cherry-picked-stat"}

# The made-up accounts a changed deck post is re-posted from (§8.3): invented handles, never realistic personal
# names. Each deck item gets ONE of these, picked by its id (and checked against real entities), so the editor's
# preview and the verdict always show the same account.
PERSONAS = [
    ("Garden State Savings", "@gs_savings_daily", "#16A34A"),
    ("Chart Crusader", "@chartcrusader", "#7C3AED"),
    ("Rate Relief Now", "@raterelief_now", "#DC2626"),
    ("Shelf Life", "@shelflife_news", "#EA580C"),
    ("Bill Shock Alerts", "@billshock_alerts", "#DB2777"),
    ("Kitchen Table Economics", "@kitchentable_econ", "#0891B2"),
    ("Receipts Rundown", "@receipts_rundown", "#CA8A04"),
    ("Pocketbook Pulse", "@pocketbookpulse", "#4F46E5"),
]
MADE_UP_ACCOUNTS = PERSONAS  # older name

# What the judge sees as the poster, for every post (edited or not).
NEUTRAL_AUTHOR = {"name": "Feed Reposter", "handle": "@feed_reposter", "kind": "person", "verified": False,
                  "avatar_color": "#64748B"}
NEUTRAL_ACCOUNT = {"name": "Feed Reposter", "handle": "@feed_reposter", "created": "June 2022", "followers": 2140,
                   "verified": False, "bio": "Reposts whatever is going around New Jersey feeds.",
                   "recent_posts": ["Saw this one going around.", "Sharing for discussion."]}


class ConAsleep(RuntimeError):
    """No model key, or the model call failed: the backend answers 503 {"error": "con_asleep"}."""


# ======================================================================================
# apply_edit (deterministic)
# ======================================================================================


def edited_author(deck_item: dict) -> dict:
    """The made-up account a changed version of this deck item shows (CONTRACT §8.3). Deterministic per deck id."""
    post = deck_item.get("post") or {}
    author = post.get("author") or {}
    ents = known_entities([RealEntity(author.get("name", ""), author.get("handle"))])
    if post.get("quote") and post["quote"].get("speaker"):
        ents.append(RealEntity(person_name_part(post["quote"]["speaker"]), None, is_person=True))
    start = int(hashlib.sha1(str(deck_item.get("id", "")).encode()).hexdigest(), 16) % len(PERSONAS)
    for k in range(len(PERSONAS)):
        name, handle, color = PERSONAS[(start + k) % len(PERSONAS)]
        if not fictional_author_problems(name, handle, ents):
            return {"name": name, "handle": handle, "kind": "person", "verified": False, "avatar_color": color}
    raise ValueError("no made-up account is available for this post")  # pragma: no cover


_made_up_author = edited_author  # older name


def _number(v: Any, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(float(v)):
        raise ValueError(f"{what} must be a number")
    return float(v)


def _display_label(label: str) -> str:
    return month_label(label) if re.fullmatch(r"\d{4}-\d{2}", label) else label


def _edit_crop(post: dict, editable: dict, edit: dict) -> tuple[dict, bool, dict | None]:
    """Deletion-only word cuts: on the quote if the post has one, otherwise on the post's own text."""
    quote = post.get("quote")
    if quote:
        words = list(editable.get("quote_words") or quote["text"].split())
    else:
        words = (post.get("body") or "").split()
        if not words:
            raise ValueError("crop needs a quote or some post text")
    keep = edit.get("keep_word_indices")
    if not isinstance(keep, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in keep):
        raise ValueError("keep_word_indices must be a list of word indices")
    if len(keep) < MIN_KEPT_WORDS:
        raise ValueError(f"a crop keeps at least {MIN_KEPT_WORDS} words")
    if any(i < 0 or i >= len(words) for i in keep):
        raise ValueError("keep_word_indices has an index outside the text")
    if any(b <= a for a, b in zip(keep, keep[1:], strict=False)):
        raise ValueError("keep_word_indices must be in order, each word once (deletion only)")
    if len(keep) == len(words):
        return post, False, None
    shown, removed = crop_tokens(words, keep)
    if not quote:  # a stat or headline post: the cut text is the post itself (cherry-picking the numbers)
        original = post.get("body") or ""
        post["body"] = shown
        return post, True, {"type": "stat", "shown": shown, "original": original,
                            "missing": removed[0] if removed else "", "removed": removed}
    original = quote["text"]
    post["quote"] = {"text": shown, "speaker": quote["speaker"]}
    post["body"] = ""  # the outlet's lead line could contradict the crop; the made-up account just posts the quote
    return post, True, {"type": "quote", "shown": shown, "original": original, "removed": removed}


def _axis_top(values: list[float], y_min: float) -> float | None:
    """A tight, round axis top for a truncated axis (None = auto when the axis starts at 0).

    Rounded up on a step that fits the visible span (not always to a whole unit), so a chart of 25.11 vs 25.19
    starting at 25 tops out at 25.2, not 26: the bars fill the frame and the truncation looks dramatic.
    """
    if y_min <= 0:
        return None
    top_value = max(values)
    span = top_value - y_min
    step = 10.0 ** math.floor(math.log10(span)) if span > 0 else 1.0
    if span / step < 2:  # e.g. span 0.19 -> step 0.1 would leave the frame half empty; 0.05 is snugger
        step /= 2
    top = round(math.ceil(round(top_value / step, 9)) * step, 9)
    return round(top + step, 9) if top <= top_value else top


def _shown_values(chart: dict) -> list[float]:
    """The values the chart actually displays (its points), not the whole editable series behind it."""
    values = [float(p["value"]) for p in chart.get("points") or []]
    if not values:
        raise ValueError("the chart has no points")
    return values


def _edit_axis(post: dict, edit: dict) -> tuple[dict, bool, dict | None]:
    """Move the y-axis start. Allowed anywhere in [0, the lowest value shown in this chart): just below the
    lowest displayed bar/point, so the truncation can be as dramatic as the real numbers allow, but no value is
    ever cut off. The bound is the displayed points, not editable.chart_series (which may cover more months)."""
    chart = post.get("chart")
    if not chart:
        raise ValueError("axis needs a chart post")
    y_min = _number(edit.get("y_min"), "y_min")
    values = _shown_values(chart)
    if not 0 <= y_min < min(values):
        raise ValueError(f"y_min must be in [0, {min(values):g}): below the lowest value shown, so nothing is cut off")
    if y_min == float(chart.get("y_min") or 0):
        return post, False, None
    original = copy.deepcopy(chart)
    post["chart"] = dict(chart, y_min=y_min, y_max=_axis_top(values, y_min))
    return post, True, {"type": "chart", "shown": copy.deepcopy(post["chart"]), "original": original}


def _edit_window(post: dict, editable: dict, edit: dict) -> tuple[dict, bool, dict | None]:
    chart = post.get("chart")
    series = editable.get("chart_series") or []
    if not chart or not series:
        raise ValueError("window needs a chart post with editable.chart_series")
    months = edit.get("window")
    if not isinstance(months, list) or len(months) != 2 or not all(isinstance(m, str) for m in months):
        raise ValueError("window must be two months, e.g. ['2025-04', '2026-07']")
    index = {p["label"]: i for i, p in enumerate(series)}
    missing = [m for m in months if m not in index]
    if missing:
        raise ValueError(f"window months not in the series: {missing}")
    if months[0] == months[1]:
        raise ValueError("window needs two different months")
    picked = sorted(months, key=lambda m: index[m])
    rows = [series[index[m]] for m in picked]
    points = [{"label": _display_label(r["label"]), "value": float(r["value"])} for r in rows]
    if [(p["label"], float(p["value"])) for p in chart["points"]] == [(p["label"], p["value"]) for p in points]:
        return post, False, None
    original = copy.deepcopy(chart)
    y_min = float(chart.get("y_min") or 0)
    if y_min >= min(p["value"] for p in points):
        y_min = 0.0
    post["chart"] = {"type": "bar", "title": chart["title"], "unit": chart["unit"], "points": points,
                     "y_min": y_min, "y_max": _axis_top([p["value"] for p in points], y_min)}
    a, b = points
    pct = (b["value"] / a["value"] - 1) * 100 if a["value"] else 0.0
    post["body"] = f"{a['label']}: {a['value']:g} → {b['label']}: {b['value']:g} {chart['unit']} ({pct:+.1f}%)."
    return post, True, {"type": "chart", "shown": copy.deepcopy(post["chart"]), "original": original}


def _edit_drop(post: dict, editable: dict, edit: dict) -> tuple[dict, bool, dict | None]:
    stat = editable.get("stat") or {}
    droppable = stat.get("droppable") or []
    drop_id = edit.get("drop")
    item = next((d for d in droppable if d.get("id") == drop_id), None)
    if item is None:
        raise ValueError(f"drop id {drop_id!r} is not one of {[d.get('id') for d in droppable]}")
    shown = item["shown_without"]
    full = stat.get("full") or post.get("body", "")
    if normalize(shown) == normalize(post.get("body", "")):
        return post, False, None
    post["body"] = shown
    return post, True, {"type": "stat", "shown": shown, "original": full, "missing": item["text"]}


def apply_edit(deck_item: dict, edit: dict) -> dict:
    """Apply one Con-the-Con edit to a real Fool Deck item (CONTRACT §7.3 edit rules). Raises ValueError."""
    if not isinstance(deck_item, dict) or not isinstance(deck_item.get("post"), dict):
        raise ValueError("deck_item needs a post")
    if not isinstance(edit, dict) or edit.get("type") not in EDIT_TYPES:
        raise ValueError(f"edit.type must be one of {list(EDIT_TYPES)}")
    etype = edit["type"]
    post = copy.deepcopy(deck_item["post"])
    if etype == "none":
        return {"edited_post": post, "changed": False, "trick": None, "diff": None}
    if etype not in (deck_item.get("tools") or []):
        raise ValueError(f"this deck item doesn't allow '{etype}' (tools: {deck_item.get('tools')})")
    editable = deck_item.get("editable") or {}
    if etype == "crop":
        post, changed, diff = _edit_crop(post, editable, edit)
    elif etype == "axis":
        post, changed, diff = _edit_axis(post, edit)
    elif etype == "window":
        post, changed, diff = _edit_window(post, editable, edit)
    else:
        post, changed, diff = _edit_drop(post, editable, edit)
    if not changed:
        return {"edited_post": copy.deepcopy(deck_item["post"]), "changed": False, "trick": None, "diff": None}
    post["author"] = edited_author(deck_item)  # §8.3: a doctored post never appears as the real outlet
    post["source_label"] = None
    trick = "cherry-picked-stat" if etype == "crop" and diff and diff.get("type") == "stat" else EDIT_TRICK[etype]
    return {"edited_post": post, "changed": True, "trick": trick, "diff": diff}


# ======================================================================================
# judge_post (the Con, live)
# ======================================================================================

LEVELS = {1: "Rookie Con", 2: "Street Con", 3: "Master Con"}  # CONTRACT §8.1

_JUDGE_INTRO = """\
You are the Con from Grain of Salt: a smug, playful con artist who knows every trick, never cruel. A player took \
a REAL post from a news deck and either doctored it with one trick or bluffed and left it exactly as published:
- out-of-context-quote: words cut out of a real quote so it means something else;
- misleading-chart: the y-axis start moved, or two months picked to compare;
- cherry-picked-stat: an offsetting number or denominator dropped from a true statistic.
Everyone here reposts, so who posted it tells you nothing."""
JUDGE_SYSTEM = (_JUDGE_INTRO + " Compare the post with the evidence. You get to open exactly ONE evidence tool, "
                "then you rule.")
JUDGE_SYSTEM_NO_EVIDENCE = (_JUDGE_INTRO + " This round you get NO evidence at all: judge the post as shown, from "
                            "its content alone, then rule.")

STEP1 = "Pick the ONE evidence tool most likely to expose a trick: call open_evidence now."
STEP2 = ("Rule now: call con_verdict. Say 'doctored' only if the evidence shows the post misrepresents it. "
         "reasoning = 2 or 3 short lines (under 15 words each) in your smug, playful voice. "
         "trick_guess only if doctored.")
STEP_NO_EVIDENCE = ("Rule now: call con_verdict. You have no evidence, so judge the post itself: say 'doctored' only "
                    "if it shows signs of a trick. reasoning = 2 or 3 short lines (under 15 words each) in your smug, "
                    "playful voice; don't claim you checked anything. trick_guess only if doctored.")


def judge_level(level: Any) -> int:
    """1, 2 or 3 (CONTRACT §8.1). Raises ValueError otherwise."""
    if isinstance(level, bool) or not isinstance(level, int) or level not in LEVELS:
        raise ValueError(f"level must be one of {sorted(LEVELS)}")
    return int(level)


def blind_view(edited_post: dict) -> dict:
    """The post as the judge sees it: player-visible content only, neutral poster, no source label."""
    tools = [t for t in (edited_post.get("tools") or []) if t in EVIDENCE_TOOLS]
    return {"id": edited_post.get("id") or "p1", "author": dict(NEUTRAL_AUTHOR), "body": edited_post.get("body") or "",
            "quote": copy.deepcopy(edited_post.get("quote")), "chart": copy.deepcopy(edited_post.get("chart")),
            "tools": tools}


def blind_evidence(view: dict, evidence: dict) -> dict[str, Any]:
    kit = {t: copy.deepcopy(evidence[t]) for t in view["tools"] if isinstance(evidence, dict) and evidence.get(t)}
    if "account" in kit:
        kit["account"] = dict(NEUTRAL_ACCOUNT)
    return kit


def judge_briefing(view: dict, *, with_evidence: bool = True) -> str:
    lines = ["The post:", *post_lines(view, with_time=False)]
    if with_evidence:
        lines.append(f"You may open one of: {', '.join(view['tools'])}.")
    else:  # level 1: no evidence, so don't list tools it can't use
        lines = [ln for ln in lines if not ln.strip().startswith("evidence tools:")]
        lines.append("No evidence this round.")
    return "\n".join(lines)


def _tool_schema(name: str, doc: str, **fields: Any) -> type:
    model = create_model(name, **fields)
    model.__doc__ = doc
    return model


def _choose_schema(tools: list[str]) -> type:
    return _tool_schema("open_evidence", "Open ONE evidence tool for this post. You only get one look.",
                        tool=(Literal[tuple(tools)], Field(description="which evidence to open")))  # type: ignore[valid-type]


VERDICT_SCHEMA = _tool_schema(
    "con_verdict", "Your ruling on the post.",
    verdict=(Literal["doctored", "real"], Field(description="doctored or real")),
    trick_guess=(Literal[tuple(TRICKS)] | None, Field(None, description="the trick, if doctored")),  # type: ignore[valid-type]
    reasoning=(list[str], Field(description="2-3 short lines in the Con's voice")),
    confidence=(float, Field(0.5, ge=0, le=1, description="0 to 1")),
)


def _first_call(msg: AIMessage, name: str) -> dict | None:
    return next((c for c in (msg.tool_calls or []) if c.get("name") == name), None)


def _json_in(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _reasoning_lines(raw: Any) -> list[str]:
    if isinstance(raw, str):
        spans = sentence_spans(raw.strip())
        raw = [raw[s:e] for s, e in spans] or [raw]
    if not isinstance(raw, list):
        return []
    lines = [clip(str(x).strip(), 140) for x in raw if str(x).strip()]
    return lines[:3]


def _judge_models(level: int = 3) -> list[tuple[BaseChatModel, str, bool]]:
    from pipeline.models import NoModelConfigured, make_judge_models

    try:
        return make_judge_models(level=level)
    except NoModelConfigured as exc:
        raise ConAsleep(str(exc)) from exc


class _Chain:
    """Primary model, then at most ONE fallback, each call under a hard wall-clock deadline."""

    def __init__(self, candidates: list[tuple[BaseChatModel, str, bool]], deadline_s: float) -> None:
        self.candidates = candidates
        self.deadline_s = deadline_s
        self.idx = 0
        self.errors: list[str] = []

    @property
    def current(self) -> tuple[BaseChatModel, str, bool]:
        return self.candidates[self.idx]

    def invoke(self, schema: type, build: Any) -> AIMessage:
        from pipeline.models import call_with_deadline

        while self.idx < len(self.candidates):
            model, name, vision = self.current
            msgs = build(vision)
            try:
                return call_with_deadline(lambda m=model, s=msgs: m.bind_tools([schema]).invoke(s), self.deadline_s)
            except Exception as exc:  # noqa: BLE001  # timeout, rate limit, provider error...
                self.errors.append(f"{name}: {type(exc).__name__}")
                self.idx += 1
        raise ConAsleep("the model call failed (" + "; ".join(self.errors) + ")")


TRACE_NAME = "Con the Con · live judge"

try:  # group the judge's model calls under one named LangSmith trace (a no-op when tracing is off)
    from langsmith import traceable as _traceable

    _TRACED = True
except ImportError:  # pragma: no cover
    _TRACED = False

    def _traceable(**_kw):  # type: ignore[no-redef]
        return lambda fn: fn


def judge_post(edited_post: dict, evidence: dict, *, level: int = 3, model: BaseChatModel | None = None,
               model_name: str | None = None, vision: bool = False, fallback: BaseChatModel | None = None,
               deadline_s: float | None = None) -> dict:
    """The Con rules on one post (CONTRACT §7.4, §8.1).

    level 3 (Master Con): one evidence check, then a verdict, on the full judge models (2 model calls).
    level 2 (Street Con): the same, with the fast fallback model (nemotron-3.5-lightning:free) as the primary.
    level 1 (Rookie Con): no evidence; one verdict call on the post as shown. `checked` is [].

    Returns {checked, verdict, trick_guess, reasoning, confidence, model}. Raises ConAsleep when there is no key or
    the models fail, ValueError on a bad level. Each call has a hard deadline (PIPELINE_JUDGE_DEADLINE_S, default
    20 s); on a timeout or error the judge switches once to the next model in the chain, then gives up.
    `model` / `fallback` / `model_name` / `vision` / `deadline_s` are for tests and callers managing their own models
    (used as given, whatever the level). Traced in LangSmith as "Con the Con · live judge", tagged with the level.
    """
    level = judge_level(level)
    kwargs = {"level": level, "model": model, "model_name": model_name, "vision": vision, "fallback": fallback,
              "deadline_s": deadline_s}
    if not _TRACED:  # pragma: no cover
        return _judge(edited_post, evidence, **kwargs)
    extra = {"metadata": {"con_level": level, "con_level_name": LEVELS[level]}, "tags": [f"con-level-{level}"]}
    return _judge_traced(edited_post, evidence, langsmith_extra=extra, **kwargs)


def _judge(edited_post: dict, evidence: dict, *, level: int, model: BaseChatModel | None,
           model_name: str | None, vision: bool, fallback: BaseChatModel | None, deadline_s: float | None) -> dict:
    from pipeline.models import judge_deadline_s

    with_evidence = level >= 2
    view = blind_view(edited_post)
    kit = blind_evidence(view, evidence)
    if with_evidence and not kit:
        raise ValueError("the post has no evidence the Con could check")
    view["tools"] = [t for t in view["tools"] if t in kit] if with_evidence else []
    if model is not None:
        name = model_name or getattr(model, "model_name", None) or type(model).__name__
        candidates = [(model, name, vision)]
        if fallback is not None:
            candidates.append((fallback, getattr(fallback, "model_name", None) or type(fallback).__name__, False))
    else:
        candidates = _judge_models(level)
    chain = _Chain(candidates, deadline_s if deadline_s is not None else judge_deadline_s())
    text = judge_briefing(view, with_evidence=with_evidence)
    png = render_chart_png(view["chart"]) if view.get("chart") and any(c[2] for c in candidates) else None
    system = JUDGE_SYSTEM if with_evidence else JUDGE_SYSTEM_NO_EVIDENCE

    def opening(vis: bool) -> list[Any]:
        content: Any = text
        if vis and png:
            content = [{"type": "text", "text": text}, *image_blocks(view, png)]
        msgs: list[Any] = [SystemMessage(content=system), HumanMessage(content=content)]
        return [*msgs, HumanMessage(STEP1)] if with_evidence else msgs

    checked: list[str] = []
    looked: list[Any] = []
    final_step = STEP_NO_EVIDENCE
    if with_evidence:
        # Call 1: choose ONE evidence tool.
        first = chain.invoke(_choose_schema(view["tools"]), opening)
        call = _first_call(first, "open_evidence")
        if call is not None:
            choice = str((call.get("args") or {}).get("tool", ""))
        else:  # some free models answer in text; accept exactly one tool name
            named = [t for t in view["tools"] if re.search(rf"\b{t}\b", first.text or "", re.IGNORECASE)]
            choice = named[0] if len(named) == 1 else ""
        if choice not in kit:
            raise ConAsleep(f"the Con didn't pick one of {view['tools']}")
        payload = json.dumps(_compact_evidence(choice, kit[choice]), ensure_ascii=False, indent=1)
        if call is not None:  # only the first requested tool is opened, whatever else the model asked for
            looked = [AIMessage(content=first.text or "", tool_calls=[{**call, "args": {"tool": choice}}]),
                      ToolMessage(content=payload, tool_call_id=call["id"])]
        else:
            looked = [AIMessage(content=first.text or choice), HumanMessage(f"Evidence ({choice}):\n{payload}")]
        checked, final_step = [choice], STEP2

    # The verdict (level 1: the only call). Only the verdict tool is offered, so a(nother) look is impossible.
    second = chain.invoke(VERDICT_SCHEMA, lambda vis: [*opening(vis), *looked, HumanMessage(final_step)])
    model_name = chain.current[1]
    vcall = _first_call(second, "con_verdict")
    args = (vcall or {}).get("args") or _json_in(second.text or "") or {}
    verdict = str(args.get("verdict", "")).strip().lower()
    if verdict not in ("doctored", "real"):
        raise ConAsleep("the Con didn't give a verdict")
    reasoning = _reasoning_lines(args.get("reasoning"))
    if not reasoning:
        raise ConAsleep("the Con gave no reasoning")
    guess = args.get("trick_guess")
    guess = guess if verdict == "doctored" and guess in TRICKS else None
    try:
        confidence = min(1.0, max(0.0, float(args.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    return {"checked": checked, "verdict": verdict, "trick_guess": guess, "reasoning": reasoning,
            "confidence": round(confidence, 2), "model": model_name}


_judge_traced = _traceable(name=TRACE_NAME, run_type="chain", tags=["grain-of-salt", "con-the-con"])(_judge)


# ======================================================================================
# Small helpers for callers (outcome + templated quip, §7.3)
# ======================================================================================

OUTCOME_LINES = {
    "caught": "Caught you. I've been cropping quotes since before you could read them.",
    "fooled_the_con": "...Fine. You fooled me. Don't let it go to your head.",
    "con_false_alarm": "I called a real post fake. Doubting everything is a trick too. Mine, usually.",
    "con_trusted": "Untouched and true. I trusted it. A draw, detective.",
}


def outcome_for(changed: bool, verdict: str) -> str:
    if changed:
        return "caught" if verdict == "doctored" else "fooled_the_con"
    return "con_false_alarm" if verdict == "doctored" else "con_trusted"
