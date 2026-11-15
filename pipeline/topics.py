"""Research hints per topic, trick choice (with player memory), and case ids."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime
from pathlib import Path

from pipeline.config import TRICKS
from pipeline.textutil import slugify

TOPIC_HINTS: dict[str, dict[str, list[str]]] = {
    "nj electricity prices": {
        "feeds": ["https://newjerseymonitor.com/feed/", "https://www.njspotlightnews.org/feed/"],
        "articles": ["https://nj.gov/bpu/newsroom/2026/approved/20260813.html"],
        "known_stories": [
            "https://newjerseymonitor.com/2026/09/24/utilities-board-votes-electric-rates/ (in the NJ Monitor feed, page 2)",
            "https://newjerseymonitor.com/2026/11/12/nj-virtual-power-plant-battery-storage/ (NJ Monitor feed, page 1)",
        ],
        "query": ["electricity rates bills utilities BPU"],
        "data": ["get_eia_series (NJ residential price, monthly, through 2026-08)"],
        "theme": ["Your Bills"],
    },
    # Fun daily themes (entertainment first). No chart data source for these, so no misleading-chart trick.
    "weird science news": {
        "feeds": ["https://feeds.npr.org/1007/rss.xml"],
        "articles": [], "known_stories": [],
        "query": ["scientists discovered study found animals space fossils"],
        "data": [], "theme": ["Science Says"],
        "tricks": ["out-of-context-quote", "cherry-picked-stat", "edited-detail"],
    },
    "food news": {
        "feeds": ["https://feeds.npr.org/1053/rss.xml"],
        "articles": [], "known_stories": [],
        "query": ["food prices restaurant recipe snack coffee"],
        "data": [], "theme": ["Food Fight"],
        "tricks": ["out-of-context-quote", "cherry-picked-stat", "edited-detail"],
    },
    "sports news": {
        "feeds": ["https://feeds.npr.org/1055/rss.xml"],
        "articles": [], "known_stories": [],
        "query": ["record season fans league marathon game"],
        "data": [], "theme": ["Game Day"],
        "tricks": ["out-of-context-quote", "cherry-picked-stat", "edited-detail"],
    },
    "tech and internet news": {
        "feeds": ["https://feeds.npr.org/1019/rss.xml"],
        "articles": [], "known_stories": [],
        "query": ["app online internet robot video game phone"],
        "data": [], "theme": ["Logged On"],
        "tricks": ["out-of-context-quote", "cherry-picked-stat", "edited-detail"],
    },
    "new jersey weird news": {
        "feeds": ["https://nj1015.com/feed/", "https://whyy.org/feed/"],
        "articles": [], "known_stories": [],
        "query": ["New Jersey weird strange record diner boardwalk"],
        "data": [], "theme": ["Jersey Weird"],
        "tricks": ["out-of-context-quote", "cherry-picked-stat", "edited-detail"],
    },
}

# HackPrinceton judging-day daily: odd science, food and Jersey news, plus NJ power data for one chart trick.
TOPIC_HINTS["hackprinceton special"] = {
    "feeds": ["https://feeds.npr.org/1007/rss.xml", "https://feeds.npr.org/1053/rss.xml", "https://nj1015.com/feed/"],
    "articles": [], "known_stories": [],
    "query": ["Princeton study scientists strange record prices New Jersey"],
    "data": ["get_eia_series (NJ residential price, monthly, through 2026-08)"],
    "theme": ["HackPrinceton Special"],
    "tricks": ["misleading-chart", "out-of-context-quote", "cherry-picked-stat", "edited-detail"],
}

# The same mix with no chart data: odd science, food and Jersey stories only, so nothing repeats the power-bill chart.
TOPIC_HINTS["hackprinceton fun"] = {
    "feeds": ["https://feeds.npr.org/1007/rss.xml", "https://feeds.npr.org/1053/rss.xml", "https://nj1015.com/feed/"],
    "articles": [], "known_stories": [],
    "query": ["Princeton study scientists strange record weird New Jersey food"],
    "data": [], "theme": ["HackPrinceton Special"],
    "tricks": ["out-of-context-quote", "cherry-picked-stat", "edited-detail"],
}

# Doctored posts per weekday, like NYT puzzles (Monday easy ... Saturday hard). Mon=0.
DAILY_DOCTORED_BY_WEEKDAY = {0: (0, 1), 1: (1, 1), 2: (1, 2), 3: (1, 2), 4: (2, 2), 5: (2, 3), 6: (0, 2)}


def plan_daily(daily_date: str, n_doctored: int | None = None,
               allowed: list[str] | None = None) -> tuple[list[str], str]:
    """(tricks, reason) for a Daily Grain: 0-3 doctored posts, seeded by the date so a re-run plans the same day.

    `allowed` limits the tricks (e.g. no misleading-chart for a topic with no chart data)."""
    day = datetime.strptime(daily_date, "%Y-%m-%d")
    rng = random.Random(f"grain-of-salt-daily-{daily_date}")
    lo, hi = DAILY_DOCTORED_BY_WEEKDAY[day.weekday()]
    n = rng.randint(lo, hi) if n_doctored is None else n_doctored
    if not 0 <= n <= 3:
        raise ValueError("a daily has 0-3 doctored posts")
    pool = [t for t in TRICKS if allowed is None or t in allowed]
    tricks = rng.sample(pool, k=min(n, len(pool)))
    reason = f"{day:%A}: {n} doctored" + (" (set by the operator)" if n_doctored is not None else "")
    return tricks, reason


def theme_for(topic: str) -> str:
    return (hints_for(topic).get("theme") or [topic])[0]


def hints_for(topic: str) -> dict[str, list[str]]:
    key = topic.strip().lower()
    for k, v in TOPIC_HINTS.items():
        if k in key or key in k:
            return v
    return {"feeds": ["https://newjerseymonitor.com/feed/", "https://www.njspotlightnews.org/feed/"],
            "articles": [], "known_stories": [], "query": [topic], "data": []}


def story_urls(hints: dict[str, list[str]]) -> list[str]:
    """The URLs inside `known_stories` entries ('https://... (in the NJ Monitor feed, page 2)')."""
    return [m.group(0) for s in hints.get("known_stories") or [] for m in re.finditer(r"https?://\S+", s)]


def used_story_urls(cases_dir: Path | None = None, limit: int | None = 40, exclude: str | None = None) -> list[str]:
    """Source URLs already used by approved or pending puzzles, newest first, so a new build picks fresh stories.

    `exclude` skips one case folder (the build's own); `limit=None` returns every URL.
    """
    from pipeline.config import DATA_DIR

    root = cases_dir or (DATA_DIR / "cases")
    seen: dict[str, float] = {}
    for f in root.glob("*/sources.json"):
        if exclude and f.parent.name == exclude:
            continue
        try:
            meta = json.loads((f.parent / "meta.json").read_text(encoding="utf-8"))
            if meta.get("status") == "rejected":
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for s in data if isinstance(data, list) else data.get("sources", []):
            url = (s or {}).get("url")
            if url:
                seen[url] = max(seen.get(url, 0.0), f.stat().st_mtime)
    ordered = [u for u, _ in sorted(seen.items(), key=lambda kv: -kv[1])]
    return ordered if limit is None else ordered[:limit]


def hints_text(topic: str, used: list[str] | None = None) -> str:
    h = hints_for(topic)
    lines = []
    if h.get("feeds"):
        lines.append("- feeds: " + ", ".join(h["feeds"]) + f" (query: \"{(h.get('query') or [topic])[0]}\")")
    if h.get("articles"):
        lines.append("- official pages: " + ", ".join(h["articles"]))
    if h.get("known_stories"):
        lines.append("- known stories: " + "; ".join(h["known_stories"]))
    if h.get("data"):
        lines.append("- data: " + "; ".join(h["data"]))
    else:
        lines.append("- data: none for this topic (no EIA tool; any stat comes from a saved source's own numbers)")
    lines.append("- only these feeds, the stories they link to and the pages listed here can be fetched")
    used = used_story_urls() if used is None else used
    if used:
        lines.append("- already used in other puzzles, so pick DIFFERENT stories (never these URLs): " + ", ".join(used))
    return "\n".join(lines)


def make_case_id(topic: str, cases_dir: Path, *, clean: bool, now: datetime) -> str:
    base = f"{now:%Y-%m-%d}-{slugify(topic, 32)}" + ("-clean" if clean else "")
    cid, n = base, 2
    while (cases_dir / cid).exists():
        cid, n = f"{base}-{n}", n + 1
    return cid


def choose_trick(profile_path: Path | None = None, rng: random.Random | None = None) -> tuple[str, str]:
    """(trick, reason). With a player profile: 70% weakest trick, 20% a mastered one, 10% new (SPEC §7.3)."""
    rng = rng or random.Random()
    if profile_path is None or not profile_path.exists():
        t = rng.choice(TRICKS)
        return t, "no player profile: random trick"
    prof = json.loads(profile_path.read_text(encoding="utf-8"))
    stats = prof.get("tricks", {})
    seen = [t for t in TRICKS if stats.get(t, {}).get("shown", 0) > 0]
    unseen = [t for t in TRICKS if t not in seen]

    def miss_rate(t: str) -> float:
        s = stats.get(t, {})
        return s.get("missed", 0) / max(1, s.get("shown", 0))

    roll = rng.random()
    if seen and roll < 0.7:
        t = max(seen, key=miss_rate)
        return t, f"weakest trick for this player (miss rate {miss_rate(t):.0%})"
    if seen and roll < 0.9:
        t = min(seen, key=miss_rate)
        return t, "retention check on a mastered trick"
    t = rng.choice(unseen or list(TRICKS))
    return t, "a trick this player hasn't seen yet" if unseen else "random trick"
