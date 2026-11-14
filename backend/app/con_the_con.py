"""Con the Con (CONTRACT §7.3, §8): the player doctors a real post and the live Con judges it.

The model work lives in `pipeline.fool` (apply_edit, edited_author, judge_post), imported lazily so the game
server still runs when the pipeline module is missing or broken. We never invent a verdict.
"""
from __future__ import annotations

import hashlib
import importlib
import json

from .views import post_view

EDIT_TYPES = ("none", "crop", "axis", "window", "drop")
WINS = ("fooled_the_con", "con_false_alarm")  # the Con got it wrong
LEVELS = (1, 2, 3)
DEFAULT_LEVEL = 3
LEVEL_NAMES = {1: "Rookie Con", 2: "Street Con", 3: "Master Con"}


def load_fool():
    """pipeline.fool, or None if it can't be imported (not written yet, syntax error, missing dep)."""
    try:
        return importlib.import_module("pipeline.fool")
    except Exception:
        return None


def edited_author(item: dict) -> dict | None:
    """The made-up account a changed version of this item shows (§8.3), from pipeline.fool (the same function
    apply_edit uses), or None when the pipeline can't be loaded (then nothing can be judged either)."""
    fool = load_fool()
    fn = getattr(fool, "edited_author", None) if fool else None
    if fn is None:
        return None
    try:
        return fn(item)
    except Exception:
        return None


def deck_view(item: dict) -> dict:
    """A Fool Deck item for the browser: evidence stays on the server."""
    return {"id": item.get("id"), "kind": item.get("kind"), "post": post_view(item.get("post") or {}),
            "tools": item.get("tools") or [], "editable": item.get("editable") or {},
            "edited_author": edited_author(item)}


def cache_key(edited_post: dict, evidence: dict, level: int = DEFAULT_LEVEL) -> str:
    """sha256 of the canonical (edited post + evidence), plus the level (§8.1).

    Level 3 keeps the v2 key (no level entry), so verdicts cached before levels existed still count.
    """
    parts: list = [edited_post, evidence]
    if level != DEFAULT_LEVEL:
        parts.append({"level": level})
    canonical = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def valid_con(con, level: int = DEFAULT_LEVEL) -> bool:
    if not isinstance(con, dict) or con.get("verdict") not in ("doctored", "real"):
        return False
    checked = con.get("checked")
    if not isinstance(checked, list):
        return False
    return not checked if level == 1 else len(checked) == 1  # level 1 never opens evidence


def outcome(changed: bool, verdict: str) -> str:
    """PLAN_V2 table: rows = what the player did, columns = what the Con said."""
    if changed:
        return "caught" if verdict == "doctored" else "fooled_the_con"
    return "con_false_alarm" if verdict == "doctored" else "con_trusted"


def round_level(r: dict) -> int:
    lv = r.get("level")
    return lv if lv in LEVELS else DEFAULT_LEVEL  # rounds from before levels were all Master Con


def scoreboard(rounds: list[dict]) -> dict:
    """{fooled, played, by_level: {"1": {fooled, played}, ...}} over the kept rounds."""
    by_level = {str(lv): {"fooled": 0, "played": 0} for lv in LEVELS}
    for r in rounds:
        row = by_level[str(round_level(r))]
        row["played"] += 1
        row["fooled"] += int(r.get("outcome") in WINS)
    return {"fooled": sum(v["fooled"] for v in by_level.values()),
            "played": sum(v["played"] for v in by_level.values()), "by_level": by_level}


# ---- the Con's quip (§8.4): only what actually happened -- the edit, the level, what the Con checked -------------

EDIT_NOUN = {"crop": "crop", "axis": "axis trick", "window": "two-month window", "drop": "missing number"}
CHECKED_NOUN = {"source": "the original source", "data": "the real data", "account": "the account"}


def con_line(result: str, edit_type: str | None, level: int, checked: list[str] | None) -> str:
    """A templated quip. Level 1 lines never claim the Con looked at anything; level 2-3 lines name the one
    evidence tool the Con actually opened. Nothing about the post's content or the answer is invented."""
    noun = EDIT_NOUN.get(edit_type or "", "edit")
    looked = CHECKED_NOUN.get((checked or [None])[0] or "", "")
    rank = LEVEL_NAMES.get(level, "the Con")
    if level == 1 or not looked:
        return {
            "caught": f"Caught your {noun} on looks alone. No evidence needed. Rookie Con, my foot.",
            "fooled_the_con": f"I judged your {noun} on looks alone, and it looked fine. Rookie mistake. Mine.",
            "con_false_alarm": "I called an untouched post a fake without checking a thing. Even I over-doubt.",
        }.get(result, "Untouched, and I trusted it without checking. A draw. Bluffing with the truth takes nerve.")
    return {
        "caught": f"One look at {looked} and your {noun} fell apart. {rank}, darling.",
        "fooled_the_con": f"I checked {looked} and still bought your {noun}. Well played. Don't let it go to your head.",
        "con_false_alarm": f"I checked {looked} and still called an untouched post a fake. Don't tell anyone.",
    }.get(result, f"Untouched. I checked {looked} and trusted it. A draw, detective.")
