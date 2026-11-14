"""The Daily Grain (CONTRACT §7.2): which daily is today's, numbering, streaks, crowd stats."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .store import CaseRecord


def today_et() -> date:
    """Today's date in US Eastern (the day resets at midnight ET).

    Windows Pythons may ship without tzdata; then use a fixed UTC-5 (EST, right for November).
    """
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/New_York")
    except Exception:
        tz = timezone(timedelta(hours=-5))
    return datetime.now(tz).date()


def parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def is_daily(rec: CaseRecord) -> bool:
    return rec.meta.get("mode") == "daily"


def released(rec: CaseRecord, today: date) -> bool:
    """Case Files are always released; a daily only from its daily_date on (no peeking ahead)."""
    if not is_daily(rec):
        return True
    d = parse_date(rec.meta.get("daily_date"))
    return d is not None and d <= today


def dailies(approved: list[CaseRecord]) -> list[tuple[date, CaseRecord]]:
    """Approved dailies with a valid daily_date, oldest first."""
    out = [(parse_date(r.meta.get("daily_date")), r) for r in approved if is_daily(r)]
    return sorted([(d, r) for d, r in out if d], key=lambda x: (x[0], x[1].number, x[1].id))


def daily_number(rec: CaseRecord, all_dailies: list[tuple[date, CaseRecord]]) -> int | None:
    """meta.daily_number if set, else the case's 1-based position among approved dailies by date."""
    if not is_daily(rec):
        return None
    if isinstance(rec.meta.get("daily_number"), int):
        return rec.meta["daily_number"]
    ids = [r.id for _, r in all_dailies]
    return ids.index(rec.id) + 1 if rec.id in ids else None


def current_daily(all_dailies: list[tuple[date, CaseRecord]], today: date) -> CaseRecord | None:
    """The daily dated today, else the latest one dated before today."""
    past = [(d, r) for d, r in all_dailies if d <= today]
    exact = [r for d, r in past if d == today]
    if exact:
        return exact[0]
    return past[-1][1] if past else None


def streak(days_played: list[str], today: date) -> int:
    """Consecutive days played, ending today (or yesterday, if today isn't played yet)."""
    played = {d for d in (parse_date(x) for x in days_played) if d}
    day = today if today in played else today - timedelta(days=1)
    count = 0
    while day in played:
        count += 1
        day -= timedelta(days=1)
    return count


# Rarity bonus (CONTRACT §8.7): (max correct_pct, label, points), rarest first.
RARITY_TIERS = ((10, "One in a shaker", 100), (25, "Rare catch", 50))


def rarity_bonus(counts_before: dict, crowd_min: int, correct: bool) -> dict | None:
    """The bonus for a correct card, from the crowd stats BEFORE this answer was counted.

    None for a wrong card, or below crowd_min (never from made-up numbers). correct_pct is rounded the same way the
    crowd stats are shown.
    """
    n = int((counts_before or {}).get("n", 0))
    if not correct or n == 0 or n < crowd_min:
        return None
    pct = round(100 * counts_before.get("correct", 0) / n)
    for cap, label, points in RARITY_TIERS:
        if pct <= cap:
            return {"label": label, "points": points}
    return None


def crowd_view(counts: dict, crowd_min: int) -> tuple[dict | None, dict | None]:
    """(crowd, rarity) from real answer counts; both null below crowd_min. Never invented."""
    n = int(counts.get("n", 0))
    if n < crowd_min or n == 0:
        return None, None
    correct = round(100 * counts.get("correct", 0) / n)
    crowd = {"said_doctored_pct": round(100 * counts.get("said_doctored", 0) / n), "correct_pct": correct, "n": n}
    return crowd, {"correct_pct": correct, "n": n}
