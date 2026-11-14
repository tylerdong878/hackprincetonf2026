"""Verdict scoring, profile updates, Detective rating and ranks (CONTRACT §3-§4)."""
from __future__ import annotations

TRICKS = ("out-of-context-quote", "misleading-chart", "cherry-picked-stat", "edited-detail")

# A real post's format counts toward honest_shown / false_alarms of the matching trick.
FORMAT_TRICK = {
    "chart": "misleading-chart",
    "quote": "out-of-context-quote",
    "stat": "cherry-picked-stat",
    "text": "cherry-picked-stat",
}

POINTS = {"trusted": 100, "caught": 100, "fooled": 0, "false_alarm": -50}
TRICK_BONUS = 50
CLUE_BONUS = 20
RECENT_LIMIT = 30
# v2 grid (CONTRACT §7.2), used by share_grid and share_text.
GRID = {"trusted": "🟩", "caught": "🧂", "fooled": "⬛", "false_alarm": "🟥"}

RANKS = [(90, "Untouchable"), (80, "Chief"), (60, "Inspector"), (40, "Gumshoe"), (0, "Rookie")]


def empty_counters() -> dict:
    return {"shown": 0, "caught": 0, "missed": 0, "named": 0, "honest_shown": 0, "false_alarms": 0}


def post_format(post: dict) -> str:
    """chart present -> chart, quote present -> quote, else text."""
    if post.get("chart"):
        return "chart"
    if post.get("quote"):
        return "quote"
    return "text"


def score_post(post: dict, key: dict, said_doctored: bool, said_trick: str | None) -> tuple[dict, dict]:
    """Score one card. Returns (result item for the API, record for the profile)."""
    pid = post["id"]
    doctored = bool(key.get("doctored"))
    if doctored:
        outcome = "caught" if said_doctored else "fooled"
        named = outcome == "caught" and said_trick is not None and said_trick == key.get("trick")
        result = {
            "post_id": pid, "outcome": outcome, "points": POINTS[outcome] + (TRICK_BONUS if named else 0),
            "doctored": True, "trick": key.get("trick"), "trick_named_correctly": named,
            "tell": key.get("tell"), "explanation": key.get("explanation"),
            "con_line": key.get("con_line_caught") if outcome == "caught" else key.get("con_line_fooled"),
            "diff": key.get("diff"),
        }
    else:
        outcome = "false_alarm" if said_doctored else "trusted"
        named = False
        result = {
            "post_id": pid, "outcome": outcome, "points": POINTS[outcome], "doctored": False,
            "suspicious_real": bool(key.get("suspicious_real")),
            "explanation": key.get("explanation"),
            "con_line": key.get("con_line_false_alarm") if outcome == "false_alarm" else None,
        }
    record = {"post_id": pid, "doctored": doctored, "outcome": outcome, "format": post_format(post),
              "trick": key.get("trick") if doctored else None, "named": named}
    return result, record


def score_case(case: dict, answer_key: dict, verdicts: dict, clues_used: int) -> dict:
    """Score a full set of verdicts.

    `verdicts` maps post_id -> object with `.doctored` and `.trick` (the request model).
    Returns the response fields plus `records` (per-post info used to update the profile).
    """
    keys = answer_key.get("posts", {})
    results, records = [], []
    for post in case.get("posts", []):
        v = verdicts[post["id"]]
        result, record = score_post(post, keys.get(post["id"], {}), v.doctored, v.trick)
        results.append(result)
        records.append(record)

    budget = int(case.get("clue_budget") or 0)
    clue_bonus = CLUE_BONUS * max(0, budget - clues_used)
    clean = bool(answer_key.get("clean_case"))
    return {
        "score": sum(r["points"] for r in results) + clue_bonus,
        "clue_bonus": clue_bonus,
        "clean_case": clean,
        "con_line_clean": answer_key.get("con_line_clean") if clean else None,
        "results": results,
        "share_grid": share_grid(results),
        "records": records,
    }


def share_grid(results: list[dict]) -> str:
    return "".join(GRID[r["outcome"]] for r in results)


def share_text(results: list[dict], lean_label: str, daily_number: int | None, streak: int,
               case_number: int | None = None) -> str:
    """Text-only share card (never post content), e.g. 'Grain of Salt #3 🧂 4/5 🔥3'."""
    correct = sum(r["outcome"] in ("trusted", "caught") for r in results)
    if daily_number is not None:
        head = f"Grain of Salt #{daily_number} 🧂 {correct}/{len(results)} 🔥{streak}"
    else:
        name = f"Case #{case_number:04d}" if isinstance(case_number, int) else "Case File"
        head = f"Grain of Salt {name} 🧂 {correct}/{len(results)}"
    return "\n".join([head, share_grid(results), f"{lean_label} detective"])


def record_verdict(profile: dict, case_id: str, scored: dict, tools_used: list[str], at: str) -> None:
    """Update per-trick counters, `recent` (last 30 posts) and `history` in place."""
    tricks = profile.setdefault("tricks", {})
    for rec in scored["records"]:
        if rec["doctored"]:
            c = tricks.setdefault(rec["trick"] or "unknown", empty_counters())
            c["shown"] += 1
            if rec["outcome"] == "caught":
                c["caught"] += 1
                c["named"] += int(rec["named"])
            else:
                c["missed"] += 1
        else:
            c = tricks.setdefault(FORMAT_TRICK[rec["format"]], empty_counters())
            c["honest_shown"] += 1
            c["false_alarms"] += int(rec["outcome"] == "false_alarm")
    recent = profile.setdefault("recent", [])
    recent.extend({"doctored": r["doctored"], "outcome": r["outcome"], "format": r["format"]}
                  for r in scored["records"])
    del recent[:-RECENT_LIMIT]
    profile.setdefault("history", []).append({
        "case_id": case_id, "at": at, "score": scored["score"],
        "outcomes": {r["post_id"]: r["outcome"] for r in scored["records"]},
        "tools_used": sorted(set(tools_used)),
    })


def _rate(num: int, den: int) -> float:
    return num / den if den else 0.0


def rating(recent: list[dict]) -> int:
    """rating = clamp(round(50 + 50 * (hit_rate - fa_rate)), 0, 100); a 0 denominator -> rate 0."""
    window = recent[-RECENT_LIMIT:]
    doctored = [r for r in window if r.get("doctored")]
    real = [r for r in window if not r.get("doctored")]
    hit = _rate(sum(r.get("outcome") == "caught" for r in doctored), len(doctored))
    fa = _rate(sum(r.get("outcome") == "false_alarm" for r in real), len(real))
    return max(0, min(100, round(50 + 50 * (hit - fa))))


def lean(recent: list[dict]) -> float:
    """-1 (gullible) .. +1 (paranoid): false_alarm_rate - miss_rate over the last 30 posts."""
    window = recent[-RECENT_LIMIT:]
    doctored = [r for r in window if r.get("doctored")]
    real = [r for r in window if not r.get("doctored")]
    miss = _rate(sum(r.get("outcome") == "fooled" for r in doctored), len(doctored))
    fa = _rate(sum(r.get("outcome") == "false_alarm" for r in real), len(real))
    return round(fa - miss, 3)


def lean_label(value: float) -> str:
    if value <= -0.5:
        return "Gullible"
    if value <= -0.15:
        return "Trusting"
    if value < 0.15:
        return "Balanced"
    if value < 0.5:
        return "Suspicious"
    return "Paranoid"


def rank(value: int) -> str:
    for floor, name in RANKS:
        if value >= floor:
            return name
    return "Rookie"


def mastery(c: dict) -> int:
    """0-3 mastery per trick (all-time counters).

    3 = caught >= 3, miss rate <= 25% and false-alarm rate <= 25%
    2 = caught >= 2 and miss rate <= 50%
    1 = caught at least once
    0 = never caught one (or never seen)
    """
    miss = _rate(c["missed"], c["shown"])
    fa = _rate(c["false_alarms"], c["honest_shown"])
    if c["caught"] >= 3 and miss <= 0.25 and fa <= 0.25:
        return 3
    if c["caught"] >= 2 and miss <= 0.5:
        return 2
    return 1 if c["caught"] >= 1 else 0


def per_trick(tricks: dict) -> dict:
    return {
        t: {
            "miss_rate": round(_rate(c["missed"], c["shown"]), 3),
            "false_alarm_rate": round(_rate(c["false_alarms"], c["honest_shown"]), 3),
            "mastery": mastery(c),
        }
        for t, c in tricks.items()
    }
