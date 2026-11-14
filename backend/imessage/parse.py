"""Turn a player's text into an intent. Loose on purpose: people type "R", "fake 2", "sus", "👍"."""
from __future__ import annotations

import re
from dataclasses import dataclass

TRICK_WORDS = {
    "out-of-context-quote": ("context", "quote", "ooc", "cropped", "crop", "misquote"),
    "misleading-chart": ("chart", "axis", "graph", "scale"),
    "cherry-picked-stat": ("stat", "cherry", "number", "numbers", "statistic", "cherrypicked", "cherry-picked"),
    "edited-detail": ("edit", "edited", "detail", "headline", "photoshop", "altered"),
}

REAL = {"real", "r", "legit", "true", "trust", "trusted", "genuine", "honest", "fine", "👍", "✅", "🟩"}
FAKE = {"fake", "f", "doctored", "d", "sus", "cap", "false", "lie", "bs", "👎", "❌", "🚩", "🟥"}
CHECK = {"check", "c", "evidence", "e", "clue", "magnify", "magnifier", "🔍", "🔎", "investigate"}
PLAY = {"play", "daily", "today", "go", "next", "start", "begin", "again", "resume", "continue", "hi", "hey",
        "hello", "yo", "sup"}
STATS = {"stats", "me", "score", "dossier", "streak", "profile", "rank"}
HELP = {"help", "?", "how", "rules", "commands", "menu", "h"}
MUTE = {"stop", "mute", "quiet", "unsubscribe", "pause"}
RESET = {"reset", "restart", "newgame", "new"}
UNMUTE = {"unmute", "remind", "reminders", "nudge", "subscribe"}
NOT_SURE = {"0", "unsure", "idk", "dunno", "skip", "notsure", "?"}
TOOLS = {"source": ("source", "article", "original", "📄"), "data": ("data", "table", "numbers", "📊"),
         "account": ("account", "author", "who", "profile", "poster", "👤")}


@dataclass(frozen=True)
class Intent:
    kind: str  # real | fake | trick | check | play | stats | help | mute | unmute | reset | unknown
    trick: str | None = None  # a trick id, for fake/trick
    choice: int | None = None  # a bare number 0-9, for picking from a list
    tool: str | None = None  # for check
    not_sure: bool = False  # "fake, not sure which trick"


def words(text: str) -> list[str]:
    t = text.strip().lower().replace("’", "'")
    # Keep emoji and "?" as their own tokens; split letters from digits ("d2" -> "d 2").
    t = re.sub(r"([a-z])(\d)", r"\1 \2", t)
    return [w for w in re.split(r"[\s,.!:;\"()\-]+", t) if w] or ([t] if t else [])


def trick_from(tokens: list[str], options: list[str]) -> tuple[str | None, int | None, bool]:
    """(trick id, bare number, not sure) from the words after 'fake' (or a reply to 'which trick?')."""
    for w in tokens:
        if w.isdigit():
            n = int(w)
            if n == 0:
                return None, 0, True
            if 1 <= n <= len(options):
                return options[n - 1], n, False
            return None, n, False
        if w in NOT_SURE or w in ("sure", "know"):
            return None, None, True
        for trick, keys in TRICK_WORDS.items():
            if w in keys and trick in options:
                return trick, None, False
    return None, None, False


def parse(text: str, trick_options: list[str] | None = None) -> Intent:
    tokens = words(text)
    options = trick_options or list(TRICK_WORDS)
    if not tokens:
        return Intent("unknown")
    head, rest = tokens[0], tokens[1:]
    joined = " ".join(tokens)
    if joined in ("not sure", "no idea", "dont know", "don't know", "i don't know", "idk"):
        return Intent("trick", not_sure=True)
    if head in REAL:
        return Intent("real")
    if head in FAKE or joined.startswith(("it's fake", "its fake", "thats fake", "that's fake")):
        trick, choice, not_sure = trick_from(rest, options)
        return Intent("fake", trick=trick, choice=choice, not_sure=not_sure)
    if head in CHECK:
        tool = next((t for t, keys in TOOLS.items() for w in rest if w in keys), None)
        return Intent("check", tool=tool)
    if head in RESET:
        return Intent("reset")
    if head in MUTE:
        return Intent("mute")
    if head in UNMUTE or joined in ("turn on reminders", "reminders on"):
        return Intent("unmute")
    if head in STATS:
        return Intent("stats")
    if head in HELP and head != "?" or joined == "?":
        return Intent("help")
    if head in PLAY:
        return Intent("play")
    # A bare trick answer ("2", "chart", "not sure") to "which trick?".
    trick, choice, not_sure = trick_from(tokens, options)
    if trick or choice is not None or not_sure:
        return Intent("trick", trick=trick, choice=choice, not_sure=not_sure)
    return Intent("unknown")
