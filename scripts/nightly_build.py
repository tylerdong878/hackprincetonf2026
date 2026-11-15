"""Nightly puzzle build: adds one AI-built Daily Grain to the backlog per run.

It finds the earliest date, from tomorrow (New Jersey time) up to --days-ahead, that has no daily case yet. It
picks that weekday's theme, builds the puzzle with the Deep Agents pipeline, and holds it for the Editor's Desk
(meta.status stays "awaiting_approval"). Nothing goes live until a human approves it.

Run (use the build key, so builds never spend the game server's live-judging quota):
  uv run --env-file .env.build python scripts/nightly_build.py            # build one puzzle
  uv run --env-file .env.build python scripts/nightly_build.py --dry-run  # just say what it would build
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "cases"

# Weekday -> topic (keys of pipeline.topics.TOPIC_HINTS). Mon=0. Fun topics first.
THEMES = {
    0: "new jersey weird news",
    1: "tech and internet news",
    2: "weird science news",
    3: "sports news",
    4: "food news",
    5: "weird science news",
    6: "food news",
}


def today_nj() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:  # Windows without tzdata: EST is right for November
        return datetime.now(timezone(timedelta(hours=-5))).date()


def covered_dates() -> set[str]:
    """Dates that already have a daily case (approved or waiting), so we don't build them twice."""
    out = set()
    for meta in CASES.glob("*/meta.json"):
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if m.get("mode") == "daily" and m.get("daily_date") and m.get("status") != "rejected":
            out.add(str(m["daily_date"]))
    return out


def next_missing(days_ahead: int) -> date | None:
    have, start = covered_dates(), today_nj() + timedelta(days=1)
    for i in range(days_ahead):
        d = start + timedelta(days=i)
        if d.isoformat() not in have:
            return d
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days-ahead", type=int, default=14, help="how far ahead to keep the backlog filled")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; no model calls")
    args = ap.parse_args(argv)

    d = next_missing(args.days_ahead)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if d is None:
        print(f"[{stamp}] backlog full for the next {args.days_ahead} days; nothing to build")
        return 0
    topic = THEMES[d.weekday()]
    print(f"[{stamp}] building {d} ({d:%A}): {topic}", flush=True)
    if args.dry_run:
        return 0
    # 30 calls: a clean run is ~18, and guardrail rejections can push a hard day past the default 25.
    cmd = [sys.executable, "-m", "pipeline.build_case", "--mode", "daily", "--daily-date", d.isoformat(),
           "--topic", topic, "--hold-for-editor", "--max-calls", "30"]
    return subprocess.run(cmd, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
