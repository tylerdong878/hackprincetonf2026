"""Research hints per topic, trick choice (with player memory), and case ids."""

from __future__ import annotations

import json
import random
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
}

# Doctored posts per weekday, like NYT puzzles (Monday easy ... Saturday hard). Mon=0.
DAILY_DOCTORED_BY_WEEKDAY = {0: (0, 1), 1: (1, 1), 2: (1, 2), 3: (1, 2), 4: (2, 2), 5: (2, 3), 6: (0, 2)}


def plan_daily(daily_date: str, n_doctored: int | None = None) -> tuple[list[str], str]:
    """(tricks, reason) for a Daily Grain: 0-3 doctored posts, seeded by the date so a re-run plans the same day."""
    day = datetime.strptime(daily_date, "%Y-%m-%d")
    rng = random.Random(f"grain-of-salt-daily-{daily_date}")
    lo, hi = DAILY_DOCTORED_BY_WEEKDAY[day.weekday()]
    n = rng.randint(lo, hi) if n_doctored is None else n_doctored
    if not 0 <= n <= 3:
        raise ValueError("a daily has 0-3 doctored posts")
    tricks = rng.sample(list(TRICKS), k=n)
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


def hints_text(topic: str) -> str:
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
