"""The Con's adaptation message after a verdict. Template-based, no LLM.

Voice: smug, playful, theatrical. Never mean, never political.
"""
from __future__ import annotations

import hashlib

from .scoring import FORMAT_TRICK

# A correct call made WITHOUT opening any evidence for that post (CONTRACT §8.4): the answer key's lines may say
# "you checked the data", so these generic ones are used instead. They never claim the player looked.
NO_RECEIPTS = [
    "Good eye. No receipts needed.",
    "Gut call. Correct gut.",
    "Didn't even check. Annoyingly right.",
    "No evidence, right answer. Lucky, or good? I'm watching.",
]


def no_receipts_line(seed: str) -> str:
    """One of NO_RECEIPTS, picked deterministically (the same card always gets the same line)."""
    return NO_RECEIPTS[int(hashlib.sha1(seed.encode("utf-8")).hexdigest(), 16) % len(NO_RECEIPTS)]


def honest_result(result: dict, looked: bool, seed: str) -> dict:
    """A card's result with an honest con_line: caught/trusted without any evidence opened -> a generic line."""
    if looked or result.get("outcome") not in ("caught", "trusted"):
        return result
    return {**result, "con_line": no_receipts_line(seed)}

# What the player falls for, per trick (when fooled).
TRUSTS = {
    "misleading-chart": "trust official-looking charts",
    "out-of-context-quote": "take a quote at its word without reading the rest",
    "cherry-picked-stat": "believe a big number without asking \"out of what?\"",
    "edited-detail": "trust a headline's details without checking the original",
}
# What the player wrongly doubts, per post format (on a false alarm).
DOUBTS = {
    "chart": "doubt honest charts",
    "quote": "doubt real quotes",
    "stat": "doubt real numbers",
    "text": "doubt real numbers",
}


def adaptation_message(scored: dict, profile: dict) -> str:
    """Built from the case just recorded (already in `profile`) plus all-time profile stats.

    Up to two clauses, in priority order: fooled -> false alarm -> no evidence used.
    "still" is added when the same weakness has shown up at least twice overall.
    """
    tricks = profile.get("tricks", {})
    records = scored["records"]
    clauses = []

    fooled = [r["trick"] for r in records if r["outcome"] == "fooled"]
    if fooled:
        t = fooled[0]
        still = tricks.get(t, {}).get("missed", 0) >= 2
        clauses.append(f"you {'still ' if still else ''}{TRUSTS.get(t, 'trust what looks official')}")

    alarms = [r["format"] for r in records if r["outcome"] == "false_alarm"]
    if alarms:
        fmt = alarms[0]
        still = tricks.get(FORMAT_TRICK[fmt], {}).get("false_alarms", 0) >= 2
        clauses.append(f"you {'still ' if still else ''}{DOUBTS[fmt]}")

    history = profile.get("history", [])
    if history and not history[-1].get("tools_used"):
        last3 = history[-3:]
        if all(not h.get("tools_used") for h in last3):
            clauses.append("you never open the source")
        else:
            clauses.append("you skipped the evidence this time")

    if not clauses:
        if scored.get("clean_case"):
            return "The Con has noticed: you didn't flinch at a clean feed. How annoying."
        return "The Con has noticed: you check before you trust. I'll have to get craftier."

    clauses = clauses[:2]
    body = clauses[0] if len(clauses) == 1 else f"{clauses[0]}, and {clauses[1]}"
    suffix = " Interesting." if len(clauses) == 1 and "never open" in body else ""
    return f"The Con has noticed: {body}.{suffix}"
