"""`write_case`: assemble, safety-check and validate the four case files (CONTRACT §2).

The forger passes a compact spec (which saved source / forgery / honest chart each post uses,
plus made-up account names and its own wording). Numbers, quotes, diffs and evidence are filled
in here from the run's verified material, so the model never retypes a real quote or a number.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta
from typing import Any, Literal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field, ValidationError

from pipeline.config import DAILY_RANGE_TEXT, EIA_URL, TRICKS, V1_TRICKS
from pipeline.context import RunContext, SavedSource
from pipeline.outlets import outlet_for
from pipeline.safety import (
    RealEntity,
    SafetyError,
    check_blocklist,
    fictional_author_problems,
    known_entities,
    person_name_part,
)
from pipeline.schemas import _RANGE_RE, daily_briefing_problems, validate_bundle
from pipeline.textutil import clip, is_verbatim, normalize, source_date_label
from pipeline.tools.forging import (
    CON_CLEAN,
    CON_FALSE_ALARM,
    CON_FALSE_ALARM_SUSPICIOUS,
    CON_LINES,
    check_numbers,
    quote_text,
)

AGENT = "forger"
PERSON_COLORS = ["#E3A42B", "#8B5CF6", "#DB2777", "#0891B2", "#65A30D", "#EA580C", "#4F46E5", "#059669"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]


class AccountIn(BaseModel):
    bio: str = ""
    created: str = ""
    followers: int | None = None
    recent_posts: list[str] = Field(default_factory=list)


class PostIn(BaseModel):
    """One post of the case, as the forger specifies it."""

    id: str = Field(description="p1, p2, ...")
    role: Literal["real", "real_suspicious", "doctored"] = Field(
        description="real | real_suspicious (real but looks fake) | doctored")
    source_id: str = Field("", description="real posts: a saved source id (s#). Text is copied verbatim for you.")
    forgery_id: str = Field("", description="doctored posts: the f# from crop_quote / make_chart / make_stat_claim")
    chart_id: str = Field("", description="real posts by a made-up person: an honest chart c# from make_chart")
    author_name: str = Field("", description="made-up display name (doctored and chart posts only)")
    author_handle: str = Field("", description="made-up @handle (doctored and chart posts only)")
    body: str = Field("", description="post text for doctored/person posts; optional verbatim lead for real posts")
    posted_at: str = Field("", description="optional ISO time, e.g. 2026-11-12T15:20:00Z")
    account: AccountIn | None = Field(None, description="optional made-up account card (bio, created, followers)")
    tell: str = Field("", description="doctored: one sentence, what gives it away")
    explanation: str = Field("", description="2-3 sentences for the reveal")
    con_line_fooled: str = ""
    con_line_caught: str = ""
    con_line_false_alarm: str = ""


class CaseBuildError(ValueError):
    pass


def _iso(dt: Any) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _color(seed: str) -> str:
    return PERSON_COLORS[int(hashlib.sha1(seed.encode()).hexdigest(), 16) % len(PERSON_COLORS)]


def _handle(h: str) -> str:
    h = re.sub(r"\s+", "", h.strip())
    return h if h.startswith("@") else "@" + h


def next_case_number(ctx: RunContext) -> int:
    nums = []
    own = None
    if ctx.cases_dir.exists():
        for f in ctx.cases_dir.glob("*/case.json"):
            try:
                n = int(json.loads(f.read_text(encoding="utf-8")).get("number", 0))
            except (ValueError, json.JSONDecodeError, OSError):
                continue
            if f.parent.name == ctx.case_id:
                own = n
            else:
                nums.append(n)
    return own or (max(nums, default=0) + 1)


def _real_entities(ctx: RunContext) -> list[RealEntity]:
    extra: list[RealEntity] = []
    for s in ctx.sources:
        o = outlet_for(s.url)
        extra.append(RealEntity(o.name, o.handle))
        if s.speaker:
            extra.append(RealEntity(person_name_part(s.speaker), None, is_person=True))
    return known_entities(extra)


def _account_card(name: str, handle: str, acc: AccountIn | None, *, doctored: bool, ctx: RunContext) -> dict:
    acc = acc or AccountIn()
    h = int(hashlib.sha1(handle.encode()).hexdigest(), 16)
    if doctored:
        prev = ctx.now.replace(day=1) - timedelta(days=1)
        created = f"{MONTH_NAMES[prev.month - 1]} {prev.year}"
        followers, bio = 600 + h % 4000, "Saying what they won't tell you about your bills."
        recent = ["Share before they delete this!", "Do your own research."]
    else:
        created, followers = f"March {ctx.now.year - 7}", 150 + h % 900
        bio, recent = "Charts with sources, always.", ["Source for every chart: EIA electricity data browser."]
    return {"name": name, "handle": handle, "created": acc.created or created,
            "followers": acc.followers if acc.followers is not None else followers, "verified": False,
            "bio": acc.bio or bio, "recent_posts": acc.recent_posts or recent}


def _outlet_card(src: SavedSource) -> dict:
    o = outlet_for(src.url)
    return {"name": o.name, "handle": o.handle, "created": None, "followers": None, "verified": True,
            "bio": o.bio, "recent_posts": []}


def _source_evidence(src: SavedSource) -> dict:
    return {"outlet": src.outlet, "date": src.date, "url": src.url, "before": src.before,
            "highlight": src.highlight, "after": src.after}


def _tools(ev: dict) -> list[str]:
    return [t for t in ("source", "data", "account") if t in ev]


def card_style_for(post: dict, src: SavedSource | None = None) -> str:
    """§7.1 display hint for a Daily card: headline | quote | chart | stat."""
    if post.get("chart"):
        return "chart"
    if post.get("quote"):
        return "quote"
    if src is not None and src.headline:
        return "headline"
    return "stat" if re.search(r"\d", post.get("body", "")) else "headline"


def build_case_bundle(ctx: RunContext, title: str, briefing: str, posts: list[PostIn | dict],
                      con_line_clean: str = "") -> tuple[dict, dict, dict, dict, list[str]]:
    """Return (case, evidence, answer_key, meta, notes). Raises CaseBuildError / SafetyError."""
    specs = [p if isinstance(p, PostIn) else PostIn.model_validate(p) for p in posts]
    errors: list[str] = []
    lo, hi = ctx.post_count_range
    if not lo <= len(specs) <= hi:
        errors.append(f"this case has {lo if lo == hi else f'{lo}-{hi}'} posts (got {len(specs)})")
    ids = [p.id for p in specs]
    if len(set(ids)) != len(ids) or not all(re.fullmatch(r"p\d", i) for i in ids):
        errors.append(f"post ids must be unique p1..p5 (got {ids})")
    doctored = [p for p in specs if p.role == "doctored"]
    expected = ctx.expected_doctored
    if len(doctored) != expected:
        errors.append(f"this case needs exactly {expected} doctored post(s) (got {len(doctored)})")
    if not any(p.role == "real_suspicious" for p in specs):
        errors.append("include at least one real_suspicious post (real, but looks fake)")
    if errors:
        raise CaseBuildError("; ".join(errors))

    entities = _real_entities(ctx)
    forged_sources = {ctx.artifacts[p.forgery_id].get("source_id") for p in doctored if p.forgery_id in ctx.artifacts}
    used_sources: set[str] = set()
    used_artifacts: set[str] = set()
    case_posts: list[dict] = []
    evidence: dict[str, dict] = {}
    answers: dict[str, dict] = {}
    urls: list[str] = []
    notes: list[str] = []
    base_time = ctx.now.replace(minute=0, second=0, microsecond=0)

    for i, p in enumerate(specs):
        where = f"{p.id}: "
        stamp = p.posted_at if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", p.posted_at or "") else ""
        if p.role == "doctored":
            art = ctx.artifacts.get(p.forgery_id)
            if not art or art.get("kind") != "forgery":
                raise CaseBuildError(where + f"forgery_id '{p.forgery_id}' is not a forgery made in this run")
            if p.forgery_id in used_artifacts:
                raise CaseBuildError(where + f"forgery {p.forgery_id} is used twice")
            used_artifacts.add(p.forgery_id)
            trick = art["trick"]
            allowed_tricks = ctx.allowed_tricks
            if allowed_tricks and trick not in allowed_tricks:
                raise CaseBuildError(where + f"this case's trick{'s are' if len(allowed_tricks) > 1 else ' is'} "
                                     f"{', '.join(sorted(allowed_tricks))}, but {p.forgery_id} is {trick}")
            name, handle = p.author_name.strip(), _handle(p.author_handle) if p.author_handle.strip() else ""
            probs = fictional_author_problems(name, handle, entities)
            if probs:
                raise SafetyError(where + "doctored posts must come from a made-up account: " + "; ".join(probs))
            author = {"name": name, "handle": handle, "kind": "person", "verified": False, "avatar_color": _color(handle)}
            post: dict[str, Any] = {"id": p.id, "author": author,
                                    "posted_at": stamp or _iso(base_time - timedelta(hours=2 + 3 * i)),
                                    "body": "", "quote": None, "chart": None, "source_label": None}
            ev: dict[str, Any] = {}
            allowed = set(art.get("allowed_numbers", []))
            if trick == "out-of-context-quote":
                post["quote"] = dict(art["quote"])
                body = p.body.strip()
                if body and (bad := check_numbers(body, allowed)):
                    raise CaseBuildError(where + f"body has numbers not in the real quote: {bad}")
                post["body"] = body
                src = ctx.source(art["source_id"])
                assert src is not None
                ev["source"] = _source_evidence(src)
                urls.append(src.url)
            elif trick == "misleading-chart":
                post["chart"] = dict(art["chart"])
                body = p.body.strip() or art["suggested_body"]
                if bad := check_numbers(body, allowed):
                    raise CaseBuildError(where + f"body numbers {bad} don't come from the chart; allowed: "
                                         + ", ".join(f"{x:g}" for x in sorted(allowed)))
                post["body"] = body
                ev["data"] = art["data"]
                urls.append(EIA_URL)
            elif trick == "edited-detail":  # §7.1: made-up accounts only (this branch always is one)
                shown = art["shown"]
                body = p.body.strip()
                post["body"] = body if body and normalize(shown) in normalize(body) else shown
                src = ctx.source(art["source_id"])
                assert src is not None
                ev["source"] = _source_evidence(src)
                urls.append(src.url)
            else:  # cherry-picked-stat
                claim = art["claim"]
                body = p.body.strip()
                post["body"] = body if body and normalize(claim) in normalize(body) else claim
                if "data" in art:
                    ev["data"] = art["data"]
                    urls.append(EIA_URL)
                else:
                    src = ctx.source(art["source_id"])
                    assert src is not None
                    ev["source"] = _source_evidence(src)
                    urls.append(src.url)
            ev["account"] = _account_card(name, handle, p.account, doctored=True, ctx=ctx)
            fooled, caught = CON_LINES[trick]
            answers[p.id] = {
                "doctored": True, "trick": trick,
                "tell": p.tell.strip() or art["default_tell"],
                "explanation": p.explanation.strip() or art["default_explanation"],
                "con_line_fooled": p.con_line_fooled.strip() or fooled,
                "con_line_caught": p.con_line_caught.strip() or caught,
                "diff": art["diff"],
            }
        else:
            suspicious = p.role == "real_suspicious"
            if bool(p.source_id) == bool(p.chart_id):
                raise CaseBuildError(where + "a real post uses exactly one of source_id (verbatim) or chart_id (honest chart)")
            if p.source_id:
                src = ctx.source(p.source_id)
                if src is None:
                    raise CaseBuildError(where + f"no saved source '{p.source_id}'")
                if p.source_id in used_sources or p.source_id in forged_sources:
                    raise CaseBuildError(where + f"source {p.source_id} is already used by another post")
                used_sources.add(p.source_id)
                o = outlet_for(src.url)
                author = {"name": o.name, "handle": o.handle, "kind": o.kind, "verified": True,
                          "avatar_color": o.avatar_color}
                lead = p.body.strip()
                doc = ctx.doc_for(src.url)
                if lead and not (doc and is_verbatim(lead, doc.text)):
                    raise CaseBuildError(where + "a real post's body must be verbatim from its source (or empty)")
                if src.speaker:
                    quote = {"text": quote_text(src.text), "speaker": src.speaker}
                    body = lead
                else:
                    quote = None
                    text = src.text.strip()
                    body = ("…" + text) if src.starts_mid_sentence and not text.startswith("…") else text
                    if lead:
                        body = lead
                default_time = src.published_at or (f"{src.date}T16:00:00Z" if src.date else _iso(base_time))
                label_date = source_date_label(src.date)
                post = {"id": p.id, "author": author, "posted_at": stamp or default_time, "body": body,
                        "quote": quote, "chart": None,
                        "source_label": f"{o.label} · {label_date}" if label_date else o.label}
                ev = {"source": _source_evidence(src), "account": _outlet_card(src)}
                urls.append(src.url)
                default_expl = (f"Real and word for word, from {src.outlet}"
                                + (f" ({label_date})." if label_date else "."))
            else:
                art = ctx.artifacts.get(p.chart_id)
                if not art or art.get("kind") != "honest_chart":
                    raise CaseBuildError(where + f"chart_id '{p.chart_id}' is not an honest chart made in this run")
                name, handle = p.author_name.strip(), _handle(p.author_handle) if p.author_handle.strip() else ""
                probs = fictional_author_problems(name, handle, entities)
                if probs:
                    raise SafetyError(where + "person accounts are always made up: " + "; ".join(probs))
                body = p.body.strip() or art["suggested_body"]
                if bad := check_numbers(body, set(art["allowed_numbers"])):
                    raise CaseBuildError(where + f"an honest post can't use numbers {bad} that aren't in its chart")
                author = {"name": name, "handle": handle, "kind": "person", "verified": False,
                          "avatar_color": _color(handle)}
                post = {"id": p.id, "author": author, "posted_at": stamp or _iso(base_time - timedelta(hours=1 + 3 * i)),
                        "body": body, "quote": None, "chart": dict(art["chart"]), "source_label": None}
                ev = {"data": art["data"], "account": _account_card(name, handle, p.account, doctored=False, ctx=ctx)}
                urls.append(EIA_URL)
                default_expl = art["default_explanation"]
            answers[p.id] = {
                "doctored": False, "suspicious_real": suspicious,
                "explanation": p.explanation.strip() or default_expl,
                "con_line_false_alarm": p.con_line_false_alarm.strip()
                or (CON_FALSE_ALARM_SUSPICIOUS if suspicious else CON_FALSE_ALARM),
            }
        post["tools"] = _tools(ev)
        if ctx.is_daily:
            src_used = ctx.source(p.source_id) if p.source_id else None
            if p.role == "doctored":
                src_used = ctx.source(ctx.artifacts[p.forgery_id].get("source_id") or "")
            post["card_style"] = card_style_for(post, src_used)
        case_posts.append(post)
        evidence[p.id] = {k: ev[k] for k in ("source", "data", "account") if k in ev}

    title, briefing = title.strip(), briefing.strip()
    if ctx.is_daily and not _RANGE_RE.search(briefing):
        briefing = f"{briefing.rstrip('. ')}. {DAILY_RANGE_TEXT[0].upper()}{DAILY_RANGE_TEXT[1:]}." if briefing \
            else f"Five posts. {DAILY_RANGE_TEXT[0].upper()}{DAILY_RANGE_TEXT[1:]}."
    if not title or len(title) > 80:
        raise CaseBuildError("title must be 1-80 characters")
    if not briefing or len(briefing) > 220:
        raise CaseBuildError("briefing must be 1-220 characters")
    if ctx.is_daily and (probs := daily_briefing_problems(briefing)):
        raise CaseBuildError("; ".join(probs))
    tricks = sorted({a["trick"] for a in answers.values() if a["doctored"]})
    clean = not tricks
    options = list(TRICKS) if ctx.is_daily else list(V1_TRICKS) + [t for t in tricks if t not in V1_TRICKS]
    case = {"id": ctx.case_id, "number": next_case_number(ctx), "title": title, "topic": ctx.topic,
            "briefing": briefing, "clue_budget": ctx.clue_budget, "trick_options": options, "posts": case_posts}
    answer_key = {"clean_case": clean, "posts": answers,
                  "con_line_clean": (con_line_clean.strip() or CON_CLEAN) if clean else None}
    difficulty = ctx.solver_history[-1]["difficulty"] if ctx.solver_history else "medium"
    meta = {"status": "awaiting_approval", "origin": "pipeline", "daily": False, "difficulty": difficulty,
            "created_at": _iso(ctx.now), "tricks": tricks, "sources": list(dict.fromkeys(urls)),
            "rejection_reason": None}
    if ctx.is_daily:
        meta.update({"mode": "daily", "daily_date": ctx.daily_date, "theme": ctx.theme or ctx.topic})

    visible = [title, briefing, ctx.topic]
    for post in case_posts:
        visible += [post["body"], post["author"]["name"], post["author"]["handle"]]
        if post["quote"]:
            visible += [post["quote"]["text"], post["quote"]["speaker"]]
        if post["chart"]:
            visible.append(post["chart"]["title"])
    for ev in evidence.values():
        if "source" in ev:
            visible += [ev["source"]["before"], ev["source"]["highlight"], ev["source"]["after"]]
        if "account" in ev:
            visible += [ev["account"]["bio"], *ev["account"]["recent_posts"]]
    check_blocklist(visible, what="case text")
    try:
        validate_bundle(case, evidence, answer_key, meta)
    except (ValidationError, ValueError) as exc:
        raise CaseBuildError(f"contract validation failed: {clip(str(exc), 600)}") from exc
    notes.append("verbatim real posts, made-up person accounts, topic blocklist clear, CONTRACT §2 schema valid")
    return case, evidence, answer_key, meta, notes


def write_case_impl(ctx: RunContext, title: str, briefing: str, posts: list[PostIn | dict],
                    con_line_clean: str = "") -> str:
    try:
        case, evidence, answer_key, meta, notes = build_case_bundle(ctx, title, briefing, posts, con_line_clean)
    except SafetyError as exc:
        return f"Rejected (safety): {exc}"
    except (CaseBuildError, ValidationError) as exc:
        return f"Rejected: {exc}"
    ctx.write_json("case.json", case, AGENT)
    ctx.write_json("evidence.json", evidence, AGENT)
    ctx.write_json("answer_key.json", answer_key, AGENT)
    ctx.write_json("meta.json", meta, AGENT)
    ctx.write_count += 1
    ctx.safety_notes = notes
    lines = [f"Wrote case {ctx.case_id} (#{case['number']}, revision {ctx.write_count}): {len(case['posts'])} posts."]
    for post in case["posts"]:
        a = answer_key["posts"][post["id"]]
        role = f"DOCTORED ({a['trick']})" if a["doctored"] else ("real, looks suspicious" if a["suspicious_real"] else "real")
        lines.append(f"- {post['id']} {post['author']['name']}: {role}; evidence {post['tools']}")
    lines.append("Safety checks passed: " + "; ".join(notes) + ".")
    lines.append(f"Files: {ctx.vpath('case.json')}, evidence.json, answer_key.json, meta.json (status awaiting_approval).")
    return "\n".join(lines)


def case_tools(ctx: RunContext) -> list[BaseTool]:
    @tool
    def write_case(title: str, briefing: str, posts: list[PostIn], con_line_clean: str = "") -> str:
        """Write the case files (case.json, evidence.json, answer_key.json, meta.json) after safety checks.

        posts: 4 posts. Each real post uses source_id (verbatim, author = the real outlet, filled in) or chart_id
        (honest chart by a made-up person). The doctored post uses forgery_id and a made-up author_name/handle.
        Quotes, numbers, evidence and diffs are filled in from the run's material; you write title, briefing,
        made-up account names, post bodies, tells, explanations and Con lines. Never name a real outlet or person
        as the author of a doctored post.
        """
        return write_case_impl(ctx, title, briefing, posts, con_line_clean)

    return [write_case]
