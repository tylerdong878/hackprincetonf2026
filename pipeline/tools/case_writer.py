"""`write_case`: assemble, safety-check and validate the four case files (CONTRACT §2).

The forger passes a compact spec (which saved source / forgery / honest chart each post uses, which made-up
persona posts it, plus its own wording). Numbers, quotes, diffs, evidence, account cards and source labels are
filled in here from the run's verified material, so the model never retypes a real quote or a number.

So that metadata never gives the answer away (scripts/build_daily_cases.py enforces the same for hand-built days):
- Every post carries a source_label. A doctored post's label cites the outlet it misquotes, so "has a link" no
  longer means "real". New Jersey Monitor is CC BY-NC-ND (no derivatives), so a doctored NJ Monitor post gets none.
- Made-up accounts come from a fixed persona list (invented handle-style names, never realistic personal names),
  each with its own account card, used for real and doctored posts alike.
- A daily needs at least one REAL post from a made-up persona, and is refused if the only posts without a
  source_label are doctored ones.
- The forger's own words on a doctored post add no numbers, no conclusions the source doesn't state, and never
  credit the edited text to a real outlet.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlparse

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
    outlet_attribution_hits,
    outlet_speaker_problem,
    overclaim_hits,
    person_name_part,
    personal_name_problems,
)
from pipeline.schemas import _RANGE_RE, daily_briefing_problems, validate_bundle
from pipeline.textutil import clip, find_verbatim, is_verbatim, normalize, numbers_in, source_date_label, word_count
from pipeline.tools.forging import (
    CON_CLEAN,
    CON_FALSE_ALARM,
    CON_FALSE_ALARM_SUSPICIOUS,
    CON_LINES,
    check_numbers,
    quote_text,
)

AGENT = "forger"
DATA_LABEL = "Data: U.S. EIA"
NO_DERIVATIVES_DOMAINS = ("newjerseymonitor.com",)  # CC BY-NC-ND: a doctored version carries no source label
MAX_OWN_WORDS = 25  # the forger's own words around a crop / claim / detail / repost


# --------------------------------------------------------------------------------------
# Made-up personas (CONTRACT §2.1: author.kind "person"; SPEC §8.2)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Persona:
    """A made-up account: an invented handle-style name, never a real person, outlet or realistic personal name.
    Its account card (age, followers, voice) is fixed, and the same for its real and doctored posts."""

    name: str
    handle: str
    color: str
    created: str
    followers: int
    bio: str
    recent: tuple[str, ...]

    def author(self) -> dict:
        return {"name": self.name, "handle": self.handle, "kind": "person", "verified": False,
                "avatar_color": self.color}

    def account(self) -> dict:
        return {"name": self.name, "handle": self.handle, "created": self.created, "followers": self.followers,
                "verified": False, "bio": self.bio, "recent_posts": list(self.recent)}


# Ages, follower counts and voices are deliberately mixed (new and loud, old and calm), so the account card never
# says which posts are doctored. Topic-neutral, so any persona fits any daily theme.
PERSONAS: tuple[Persona, ...] = (
    Persona("Jersey Bill Watch", "@jerseybills", "#E3A42B", "October 2026", 1840,
            "Exposing what they don't want you to know about your bills.",
            ("Your utility bill is a SCAM. Thread \U0001F9F5", "Share before they delete this!")),
    Persona("Turnpike Tea", "@turnpiketea", "#8B5CF6", "March 2021", 6200, "Jersey gossip, exit by exit. ☕",
            ("Exit 9 drama: a thread \U0001F9F5", "Who else is stuck on the Parkway?")),
    Persona("Scroll Patrol", "@scrollpatrol", "#DB2777", "June 2019", 22400,
            "I read the whole feed so you don't have to. \U0001F4F1", ("Today's feed, ranked.", "Not a bot. Probably.")),
    Persona("Fact Snack", "@factsnack", "#0891B2", "September 2026", 930, "Bite-size facts, served daily. \U0001F37F",
            ("Did you know? A thread \U0001F9F5", "Snack-size news for your lunch break.")),
    Persona("Headline Hound", "@headlinehound", "#65A30D", "January 2020", 15100,
            "Sniffing out the day's strangest headlines. \U0001F436",
            ("Weirdest headline of the week?", "Good news only today.")),
    Persona("Plot Twist Daily", "@plottwistdaily", "#EA580C", "August 2026", 2700, "Every story has a twist. \U0001F300",
            ("Wait for the twist...", "Part 2 tomorrow.")),
    Persona("Group Chat Gazette", "@groupchatgazette", "#4F46E5", "April 2022", 8800,
            "What your group chat is arguing about today.", ("Settle this for us \U0001F447", "Send this to the group.")),
    Persona("Mildly Alarmed", "@mildlyalarmed", "#059669", "November 2023", 4100,
            "Concerned about everything. A little. \U0001F62C", ("Is it just me, or...", "Okay, this one bugs me.")),
    Persona("Side Eye Report", "@sideeyereport", "#B91C1C", "February 2021", 12900,
            "Reading the news with one eyebrow up. \U0001F928", ("Hmm. Interesting timing.", "Sources, please.")),
    Persona("Couch Coach", "@couchcoach_", "#2563EB", "January 2022", 5400,
            "Sports takes from the sofa. \U0001F6CB️\U0001F3C8",
            ("Fantasy lineup locked. Snacks loaded.", "Halftime is a sport.")),
    Persona("Snack Attack Weekly", "@snackattackwkly", "#CA8A04", "July 2024", 3300,
            "Food news and hot takes. \U0001F32E", ("Best gas station snack? Go.", "Rating today's lunch.")),
    Persona("Lab Notes Lite", "@labnoteslite", "#0E7490", "May 2020", 18700,
            "Science news for people who skipped chem. \U0001F52C",
            ("Science thread incoming \U0001F9F5", "Space is weird, part 12.")),
    Persona("Boardwalk Buzz", "@boardwalkbuzz", "#0369A1", "June 2018", 26100, "Shore news, all year round. \U0001F30A",
            ("Boardwalk fries ranking, round 3 \U0001F35F", "Beach badge thread \U0001F9F5")),
    Persona("Wi-Fi Whisperer", "@wifiwhisperer", "#7C3AED", "October 2025", 1500,
            "Tech news without the jargon. \U0001F4BB", ("Update your phone. Seriously.", "App of the week \U0001F4F1")),
    Persona("Trivia Tornado", "@triviatornado", "#C2410C", "September 2026", 640, "Facts that sound fake. \U0001F32A️",
            ("Bet you didn't know this one.", "Trivia night prep \U0001F9E0")),
    Persona("Morning Scroll", "@morningscroll_", "#475569", "March 2017", 31800, "Your news, before coffee. ☕",
            ("Good morning. Here's what's going on.", "Three stories to start your day.")),
    Persona("Hot Take Hotline", "@hottakehotline", "#BE185D", "October 2026", 420, "All takes. Mostly hot. \U0001F525",
            ("Unpopular opinion incoming.", "Fight me in the replies \U0001F525")),
    Persona("Calm Down Daily", "@calmdowndaily", "#15803D", "December 2019", 9300, "The news, minus the panic.",
            ("Deep breath. Here's the actual story.", "Read past the headline.")),
)


def _k(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize(s or "").lower())


def persona_named(name: str, handle: str = "") -> Persona | None:
    nk, hk = _k(name), _k(handle)
    for per in PERSONAS:
        if (nk and nk == _k(per.name)) or (hk and hk == _k(per.handle)):
            return per
    return None


def persona_list_text() -> str:
    return "; ".join(f"{p.name} ({p.handle})" for p in PERSONAS)


# --------------------------------------------------------------------------------------
# Spec
# --------------------------------------------------------------------------------------


class PostIn(BaseModel):
    """One post of the case, as the forger specifies it."""

    id: str = Field(description="p1, p2, ...")
    role: Literal["real", "real_suspicious", "doctored"] = Field(
        description="real | real_suspicious (real but looks fake) | doctored")
    source_id: str = Field("", description="real posts: a saved source id (s#). Text is copied verbatim for you.")
    forgery_id: str = Field("", description="doctored posts: the f# from crop_quote / make_chart / make_stat_claim / "
                                            "edit_detail")
    chart_id: str = Field("", description="real posts by a made-up persona: an honest chart c# from make_chart")
    by_persona: bool = Field(False, description="real source_id posts: true = shared by a made-up persona (verbatim, "
                                                "source label cites the outlet) instead of by the outlet itself")
    author_name: str = Field("", description="made-up persona from the list (doctored, persona and chart posts). "
                                             "Leave empty to get one assigned")
    author_handle: str = Field("", description="optional: the persona's @handle")
    body: str = Field("", description="doctored / persona posts: your short reaction (no new numbers or claims); "
                                      "outlet posts: optional verbatim lead")
    posted_at: str = Field("", description="optional ISO time, e.g. 2026-11-12T15:20:00Z")
    tell: str = Field("", description="doctored: one sentence, what gives it away")
    explanation: str = Field("", description="2-3 sentences for the reveal")
    con_line_fooled: str = ""
    con_line_caught: str = ""
    con_line_false_alarm: str = ""


class CaseBuildError(ValueError):
    pass


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _iso(dt: Any) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _account_time(ctx: RunContext, hours_ago: int, src: SavedSource | None) -> str:
    """When a made-up account posted: `hours_ago` before now, but never before the story it shares."""
    t = ctx.now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours_ago)
    published = src.published_at or (f"{src.date}T16:00:00Z" if src.date else None) if src else None
    if published:
        try:
            pub = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except ValueError:
            pub = None
        if pub and t <= pub:
            t = min(pub + timedelta(hours=1), ctx.now.replace(microsecond=0))
    return _iso(t)


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
        if s.outlet and s.outlet != o.name:
            extra.append(RealEntity(s.outlet))
        if s.speaker:
            extra.append(RealEntity(person_name_part(s.speaker), None, is_person=True))
    return known_entities(extra)


def pick_persona(ctx: RunContext, p: PostIn, used: dict[str, str], entities: list[RealEntity]) -> Persona:
    """The forger's chosen persona (must be on the list), or a free one assigned deterministically."""
    where = f"{p.id}: "
    name, handle = p.author_name.strip(), p.author_handle.strip()
    free = [per for per in PERSONAS if per.name not in used and not fictional_author_problems(per.name, per.handle,
                                                                                               entities)]
    if name or handle:
        per = persona_named(name, handle)
        if per is None:
            probs = personal_name_problems(name, handle) + fictional_author_problems(name or handle, handle or name,
                                                                                      entities)
            why = "; ".join(probs) if probs else f"'{name or handle}' is not on the persona list"
            raise SafetyError(where + "posts by made-up accounts must use a listed persona (invented handle-style "
                              f"names, never realistic personal names or real outlets): {why}. Leave author_name "
                              f"empty to get one assigned, or pick one of: {', '.join(x.name for x in free)}")
        if per.name in used:
            raise CaseBuildError(where + f"persona {per.name} already posts {used[per.name]}; each made-up account "
                                 "posts once. Leave author_name empty to get a free one.")
        if probs := fictional_author_problems(per.name, per.handle, entities):
            raise SafetyError(where + f"persona {per.name} collides with this run's real material: {'; '.join(probs)}")
    else:
        if not free:
            raise CaseBuildError(where + "no persona left for this post")
        start = int(hashlib.sha1(f"{ctx.case_id}:{p.id}".encode()).hexdigest(), 16)
        per = free[start % len(free)]
    used[per.name] = p.id
    return per


def label_for(src: SavedSource) -> str:
    o = outlet_for(src.url)
    d = source_date_label(src.date)
    return f"{o.label} · {d}" if d else o.label


def no_derivatives(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in NO_DERIVATIVES_DOMAINS)


def _outlet_card(src: SavedSource) -> dict:
    o = outlet_for(src.url)
    return {"name": o.name, "handle": o.handle, "created": None, "followers": None, "verified": True,
            "bio": o.bio, "recent_posts": []}


def _source_evidence(src: SavedSource) -> dict:
    return {"outlet": src.outlet, "date": src.date, "url": src.url, "before": src.before,
            "highlight": src.highlight, "after": src.after}


def _evidence_text(src: SavedSource) -> str:
    return " ".join(x for x in (src.title, src.before, src.highlight, src.after) if x)


def _tools(ev: dict) -> list[str]:
    return [t for t in ("source", "data", "account") if t in ev]


def _without(body: str, made: str) -> str:
    """`body` minus the code-made text inside it (what's left is the forger's own words)."""
    span = find_verbatim(made, body) if made else None
    return (body[:span[0]] + " " + body[span[1]:]).strip() if span else body


def own_words_problems(text: str, allowed: set[float], support: str, entities: list[RealEntity], *,
                       doctored: bool) -> list[str]:
    """What's wrong with the forger's own words on a post: they may react, never add facts or credit an outlet."""
    t = (text or "").strip(" \"'“”")
    if not t:
        return []
    probs: list[str] = []
    if word_count(t) > MAX_OWN_WORDS:
        probs.append(f"keep your own words to {MAX_OWN_WORDS} words or fewer")
    if bad := check_numbers(t, allowed):
        probs.append(f"your words add numbers the source doesn't have ({', '.join(f'{x:g}' for x in bad)})")
    if loud := overclaim_hits(t, support):
        probs.append(f"your words claim more than the source says ({', '.join(loud)})")
    if doctored and (who := outlet_attribution_hits(t, entities)):
        probs.append(f"your words credit the edited text to {', '.join(who)}; a doctored post never presents "
                     "edited words as said by a real outlet (the source label already cites it)")
    return probs


def card_style_for(post: dict, src: SavedSource | None = None) -> str:
    """§7.1 display hint for a Daily card: headline | quote | chart | stat."""
    if post.get("chart"):
        return "chart"
    if post.get("quote"):
        return "quote"
    if src is not None and src.headline:
        return "headline"
    return "stat" if re.search(r"\d", post.get("body", "")) else "headline"


# --------------------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------------------


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
    used_personas: dict[str, str] = {}
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
            persona = pick_persona(ctx, p, used_personas, entities)
            src = ctx.source(art.get("source_id") or "")
            post: dict[str, Any] = {"id": p.id, "author": persona.author(),
                                    "posted_at": stamp or _account_time(ctx, 2 + 3 * i, src),
                                    "body": "", "quote": None, "chart": None, "source_label": None}
            ev: dict[str, Any] = {}
            allowed = set(art.get("allowed_numbers", []))
            body = p.body.strip()
            support = _evidence_text(src) if src else ""
            if trick == "out-of-context-quote" and art.get("quote"):
                if prob := outlet_speaker_problem(art["quote"]["speaker"], entities):
                    raise SafetyError(where + prob)
                post["quote"] = dict(art["quote"])
                post["body"], own = body, body
            elif trick == "misleading-chart":
                post["chart"] = dict(art["chart"])
                post["body"] = body or art["suggested_body"]
                own = "" if post["body"] == art["suggested_body"] else post["body"]
                if bad := check_numbers(post["body"], allowed):
                    raise CaseBuildError(where + f"body numbers {bad} don't come from the chart; allowed: "
                                         + ", ".join(f"{x:g}" for x in sorted(allowed)))
            else:  # code-made text in the body: a cropped sentence/headline, an edited detail, a stat claim
                made = art.get("shown") if trick != "cherry-picked-stat" else art["claim"]
                post["body"] = body if body and normalize(made) in normalize(body) else made
                own = _without(post["body"], made)
            if probs := own_words_problems(own, allowed, support, entities, doctored=True):
                raise CaseBuildError(where + "; ".join(probs))
            if "data" in art:  # EIA chart or EIA stat
                ev["data"] = art["data"]
                urls.append(EIA_URL)
                post["source_label"] = DATA_LABEL
            else:
                assert src is not None
                ev["source"] = _source_evidence(src)
                urls.append(src.url)
                post["source_label"] = None if no_derivatives(src.url) else label_for(src)
            ev["account"] = persona.account()
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
                label_date = source_date_label(src.date)
                text = src.text.strip()
                excerpt = ("…" + text) if src.starts_mid_sentence and not text.startswith("…") else text
                quote = {"text": quote_text(src.text), "speaker": src.speaker} if src.speaker else None
                default_time = src.published_at or (f"{src.date}T16:00:00Z" if src.date else _iso(base_time))
                ev = {"source": _source_evidence(src)}
                lead = p.body.strip()
                if p.by_persona or p.author_name.strip() or p.author_handle.strip():
                    # REAL post from a made-up account: the verbatim passage, plus at most a short reaction
                    persona = pick_persona(ctx, p, used_personas, entities)
                    own = _without(lead, text) if not quote else lead
                    allowed = set(numbers_in(_evidence_text(src)))
                    if probs := own_words_problems(own, allowed, _evidence_text(src), entities, doctored=False):
                        raise CaseBuildError(where + "; ".join(probs))
                    if quote:
                        body = lead
                    elif lead and normalize(text) in normalize(lead):
                        body = lead
                    else:
                        body = f"{lead} “{excerpt}”" if lead else excerpt
                    author = persona.author()
                    ev["account"] = persona.account()
                    posted = stamp or _account_time(ctx, 1 + 3 * i, src)
                    default_expl = (f"Real. A random account shared it, but the words are exactly {src.outlet}'s"
                                    + (f" ({label_date})" if label_date else "") + ", as the source label says.")
                else:
                    doc = ctx.doc_for(src.url)
                    if lead and not (doc and is_verbatim(lead, doc.text)):
                        raise CaseBuildError(where + "a real post's body must be verbatim from its source (or empty)")
                    body = lead if (lead or quote) else excerpt
                    author = {"name": o.name, "handle": o.handle, "kind": o.kind, "verified": True,
                              "avatar_color": o.avatar_color}
                    ev["account"] = _outlet_card(src)
                    posted = stamp or default_time
                    default_expl = (f"Real and word for word, from {src.outlet}"
                                    + (f" ({label_date})." if label_date else "."))
                post = {"id": p.id, "author": author, "posted_at": posted, "body": body, "quote": quote,
                        "chart": None, "source_label": label_for(src)}
                urls.append(src.url)
            else:
                art = ctx.artifacts.get(p.chart_id)
                if not art or art.get("kind") != "honest_chart":
                    raise CaseBuildError(where + f"chart_id '{p.chart_id}' is not an honest chart made in this run")
                persona = pick_persona(ctx, p, used_personas, entities)
                body = p.body.strip() or art["suggested_body"]
                if bad := check_numbers(body, set(art["allowed_numbers"])):
                    raise CaseBuildError(where + f"an honest post can't use numbers {bad} that aren't in its chart")
                post = {"id": p.id, "author": persona.author(),
                        "posted_at": stamp or _iso(base_time - timedelta(hours=1 + 3 * i)),
                        "body": body, "quote": None, "chart": dict(art["chart"]), "source_label": DATA_LABEL}
                ev = {"data": art["data"], "account": persona.account()}
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

    if ctx.is_daily:
        daily_metadata_check(case_posts, answers)

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
    notes.append("verbatim real posts, made-up persona accounts, every post sourced, topic blocklist clear, "
                 "CONTRACT §2 schema valid")
    return case, evidence, answer_key, meta, notes


def daily_metadata_check(case_posts: list[dict], answers: dict[str, dict]) -> None:
    """Who posted a card, and whether it has a source label, must never give the answer away."""
    if not any(p["author"]["kind"] == "person" and not answers[p["id"]]["doctored"] for p in case_posts):
        raise CaseBuildError(
            "a daily needs at least one REAL post from a made-up persona, otherwise 'made-up account' means "
            "'doctored' (or, on a clean day, the outlets-only lineup says nothing is doctored). Turn a real post "
            "into a persona repost: keep its source_id and set by_persona=true (a persona is assigned; the text "
            "stays verbatim and its source label cites the outlet).")
    unlabeled = [p["id"] for p in case_posts if not p["source_label"]]
    if unlabeled and all(answers[i]["doctored"] for i in unlabeled):
        raise CaseBuildError(
            f"{', '.join(unlabeled)} would be the only post(s) without a source label, which gives the answer "
            "away: a doctored New Jersey Monitor post carries no label (CC BY-NC-ND, no derivatives), while every "
            "real post has one. Doctor a different source; NJ Monitor passages can still be real posts.")


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

        posts: the case shape's posts. A real post uses source_id (verbatim; by the outlet, or by a made-up persona
        with by_persona=true) or chart_id (honest chart by a persona). A doctored post uses forgery_id and is
        posted by a persona. Personas come from the listed set (leave author_name empty to get one). Quotes,
        numbers, evidence, account cards and source labels are filled in from the run's material; you write the
        title, briefing, short reactions, tells, explanations and Con lines. Your words never add numbers or
        conclusions, and never credit edited words to a real outlet.
        """
        return write_case_impl(ctx, title, briefing, posts, con_line_clean)

    return [write_case]
