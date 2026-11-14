"""Con the Con (CONTRACT §7.3): the player doctors a real post and the live Con judges it.

The model work lives in `pipeline.fool` (apply_edit, judge_post), imported lazily so the game
server still runs when the pipeline module is missing or broken. We never invent a verdict.
"""
from __future__ import annotations

import hashlib
import importlib
import json

from .views import post_view

EDIT_TYPES = ("none", "crop", "axis", "window", "drop")
WINS = ("fooled_the_con", "con_false_alarm")  # the Con got it wrong


def load_fool():
    """pipeline.fool, or None if it can't be imported (not written yet, syntax error, missing dep)."""
    try:
        return importlib.import_module("pipeline.fool")
    except Exception:
        return None


def deck_view(item: dict) -> dict:
    """A Fool Deck item for the browser: evidence stays on the server."""
    return {"id": item.get("id"), "kind": item.get("kind"), "post": post_view(item.get("post") or {}),
            "tools": item.get("tools") or [], "editable": item.get("editable") or {}}


def cache_key(edited_post: dict, evidence: dict) -> str:
    canonical = json.dumps([edited_post, evidence], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def valid_con(con) -> bool:
    return isinstance(con, dict) and con.get("verdict") in ("doctored", "real")


def outcome(changed: bool, verdict: str) -> str:
    """PLAN_V2 table: rows = what the player did, columns = what the Con said."""
    if changed:
        return "caught" if verdict == "doctored" else "fooled_the_con"
    return "con_false_alarm" if verdict == "doctored" else "con_trusted"


CAUGHT = {
    "out-of-context-quote": "You snipped the words that mattered. I read the whole quote. Amateur scissors.",
    "misleading-chart": "Nudging the axis? Darling, I invented that move.",
    "cherry-picked-stat": "A number without its other half. I know my own signature when I see it.",
    "edited-detail": "Swapped a little detail and hoped I wouldn't check? I always check.",
}
FOOLED = {
    "out-of-context-quote": "I trusted that quote. You cut it so cleanly I never saw the seam. Well played.",
    "misleading-chart": "I bought the chart. Don't let it go to your head. ...Too late, I see.",
    "cherry-picked-stat": "I took that number at face value. That's supposed to be your mistake, not mine.",
    "edited-detail": "One tiny detail, and I swallowed it whole. Clever.",
}


def con_line(result: str, trick: str | None) -> str:
    if result == "caught":
        return CAUGHT.get(trick, "Caught you. Flattering imitation, sloppy execution.")
    if result == "fooled_the_con":
        return FOOLED.get(trick, "You fooled me. I'll be studying your technique. Purely professionally.")
    if result == "con_false_alarm":
        return "I called the truth a fake. Even I over-doubt sometimes. Don't tell anyone."
    return "Real, and I said real. A draw. Bluffing with the truth takes nerve, I'll give you that."
