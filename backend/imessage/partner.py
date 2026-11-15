"""The detective partner: free-form replies for texts that aren't commands.

Commands never reach here (they're instant and free). The partner sees the current post, the evidence the player
has opened, the reveal once they've answered, and a short chat history. Before an answer it also sees the answer
key so its hints point the right way, but it must never give the verdict or name the trick; `leaks()` checks
every pre-answer reply in code and swaps a leaky one for a safe hint.
"""
from __future__ import annotations

import concurrent.futures
import logging
import os
import re
from typing import Callable

log = logging.getLogger("gos.imessage")

ChatFn = Callable[[str, list[tuple[str, str]]], str]  # (system prompt, [(role, text), ...]) -> reply

MAX_REPLY = 480
SAFE_HINT = "Not saying. 🧂 But I'd spend a 🔍 before trusting it. Text CHECK."

SYSTEM = """You are the player's detective partner in Grain of Salt, a daily iMessage game about spotting \
doctored news posts (cropped quotes, chart axis tricks, cherry-picked stats, edited details). Five posts a day, \
0 to 3 doctored. The player replies REAL or FAKE.

Voice: a dry, deadpan detective partner. Short, wry, warm underneath. Texts, not essays: 1 to 3 short \
sentences, under 300 characters. Plain text, no markdown, at most one emoji.

Rules:
- Before the player answers the current post, NEVER say or imply whether it is real or doctored, and never name \
the trick. You may hint: point at where to look (the axis, the dates, the source, the account, what the quote \
leaves out) and suggest a CHECK. Hint harder only if they ask again or say they're stuck. If they beg for the \
answer, refuse with humor.
- After a reveal, explain freely and plainly.
- Small talk is fine for a line or two, then steer back to the case, gently and in character.
- Refuse anything harmful, hateful or private. You're a partner, not a search engine.
- Commands the player can text: REAL, FAKE, CHECK, HINT, PLAY, STATS, HELP, RESET, STOP.
- Never invent facts about the post. Use only the case notes below."""


def default_chat() -> ChatFn | None:
    """OpenRouter (GOS_PARTNER_MODEL), then Gemini, from the repo's model factory. None when no key is set."""
    try:
        from pipeline.config import load_env
        load_env()
        from pipeline.models import DEFAULT_FALLBACK_MODEL, DEFAULT_GEMINI_MODEL, make_gemini, make_openrouter
    except Exception:
        log.exception("partner: model setup unavailable")
        return None
    timeout = float(os.environ.get("GOS_PARTNER_TIMEOUT_S", "15"))
    available = {}
    if os.environ.get("OPENROUTER_API_KEY", "").strip():
        available["openrouter"] = lambda: make_openrouter(
            os.environ.get("GOS_PARTNER_MODEL", DEFAULT_FALLBACK_MODEL), timeout_ms=int(timeout * 1000))
    if (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip():
        available["gemini"] = lambda: make_gemini(
            os.environ.get("GOS_PARTNER_GEMINI_MODEL") or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            timeout_s=timeout)
    # GOS_PARTNER_ORDER: which model to try first (default Gemini: faster replies feel like texting a person).
    order = [n.strip() for n in os.environ.get("GOS_PARTNER_ORDER", "gemini,openrouter").split(",")]
    models = [(n, available[n]) for n in order if n in available]
    models += [(n, m) for n, m in available.items() if n not in order]
    if not models:
        return None
    log.info("partner models, in order: %s", ", ".join(n for n, _ in models))
    cache: dict[str, object] = {}
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def chat(system: str, turns: list[tuple[str, str]]) -> str:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        msgs = [SystemMessage(system)] + [HumanMessage(t) if r == "user" else AIMessage(t) for r, t in turns]
        for name, make in models:
            try:  # a hard wall-clock deadline: a slow free model must not stall the whole bot
                model = cache.get(name) or cache.setdefault(name, make())
                reply = pool.submit(model.invoke, msgs).result(timeout=timeout)
                text = reply.content if isinstance(reply.content, str) else " ".join(
                    p.get("text", "") for p in reply.content if isinstance(p, dict))
                if text.strip():
                    return text
            except Exception as e:
                log.warning("partner: %s failed (%s)", name, type(e).__name__)
        raise RuntimeError("no model answered")

    return chat


def trick_words(options: list[str]) -> list[str]:
    from .render import trick_label
    return [trick_label(t).lower() for t in options] + ["cherry-pick", "cherry pick", "out of context"]


VERDICT = re.compile(r"\b(it'?s|this is|that'?s|that one'?s|this one'?s|definitely|probably|totally|is|looks|"
                     r"seems)\s+(a\s+)?(fake|real|doctored|legit|genuine|honest|true|false|made up|edited)\b"
                     r"|\b(answer|verdict) is\b|\bit was (fake|real|doctored)\b|\b(say|text|reply|go with) "
                     r"(real|fake)\b", re.I)


def leaks(reply: str, options: list[str]) -> bool:
    low = reply.lower()
    return bool(VERDICT.search(low)) or any(w in low for w in trick_words(options))


def clip(text: str) -> str:
    text = re.sub(r"[*_`#]+", "", text).strip()
    if len(text) <= MAX_REPLY:
        return text
    cut = text[:MAX_REPLY]
    return cut[: max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! ")) + 1] or cut.rstrip() + "…"


def describe_post(post: dict) -> str:
    a = post.get("author") or {}
    lines = [f"Author: {a.get('name')} {a.get('handle')} ({'verified ' if a.get('verified') else ''}{a.get('kind')})",
             f"Text: {post.get('body')}"]
    if post.get("quote"):
        lines.append(f"Quote: \"{post['quote'].get('text')}\" (attributed to {post['quote'].get('speaker')})")
    if post.get("chart"):
        c = post["chart"]
        pts = ", ".join(f"{p['label']}={p['value']}" for p in c.get("points", []))
        lines.append(f"Chart ({c.get('type')}): {c.get('title')} [{c.get('unit')}] {pts}; "
                     f"y-axis {c.get('y_min')} to {c.get('y_max') or 'auto'}")
    if post.get("source_label"):
        lines.append(f"Source label: {post['source_label']}")
    lines.append(f"Evidence the player can CHECK: {', '.join(post.get('tools') or []) or 'none'}")
    return "\n".join(lines)


def describe_evidence(opened: dict[str, dict]) -> str:
    out = []
    for tool, ev in opened.items():
        if tool == "source":
            out.append(f"Source ({ev.get('outlet')}, {ev.get('date')}): ...{ev.get('before', '')} "
                       f"[{ev.get('highlight', '')}] {ev.get('after', '')}...")
        elif tool == "data":
            out.append(f"Data: {ev.get('title')}. {ev.get('note', '')}")
        elif tool == "account":
            out.append(f"Account: {ev.get('name')} {ev.get('handle')}, created {ev.get('created')}, "
                       f"{ev.get('followers')} followers, bio: {ev.get('bio')}")
    return "\n".join(out)


class Partner:
    def __init__(self, chat: ChatFn | None, daily_cap: int | None = None):
        self.chat = chat
        self.daily_cap = daily_cap if daily_cap is not None else int(os.environ.get("GOS_PARTNER_DAILY", "40"))

    def available(self) -> bool:
        return self.chat is not None

    def reply(self, *, text: str, history: list[tuple[str, str]], post: dict | None, index: int | None,
              key: dict | None, opened: dict[str, dict], last_reveal: dict | None, options: list[str],
              ask_hint: bool = False) -> str | None:
        """One partner text, or None (no model, model failed): the caller falls back to the command list."""
        if self.chat is None:
            return None
        notes = []
        if post is not None:
            notes.append(f"CURRENT POST (post {index + 1} of 5, not answered yet):\n{describe_post(post)}")
            if opened:
                notes.append("EVIDENCE THE PLAYER HAS OPENED:\n" + describe_evidence(opened))
            if key:
                verdict = f"doctored ({key.get('trick')})" if key.get("doctored") else "real"
                notes.append("SECRET, for aiming hints only. Never reveal, never name the trick: this post is "
                             f"{verdict}. Why: {key.get('tell') or key.get('explanation') or ''}")
        else:
            notes.append("No post is waiting for an answer right now.")
        if last_reveal:
            notes.append(f"LAST REVEALED POST (free to discuss): {last_reveal.get('body', '')}\n"
                         f"Outcome for the player: {last_reveal.get('outcome')}; "
                         f"{'doctored, trick: ' + str(last_reveal.get('trick')) if last_reveal.get('doctored') else 'real'}. "
                         f"Why: {last_reveal.get('tell') or ''} {last_reveal.get('explanation') or ''}")
        system = SYSTEM + "\n\nCASE NOTES\n" + "\n\n".join(notes)
        user = "I'm stuck. Give me a hint." if ask_hint and not text.strip() else text
        try:
            out = clip(self.chat(system, history[-8:] + [("user", user)]))
        except Exception:
            return None
        if not out:
            return None
        if post is not None and leaks(out, options):
            log.info("partner: blocked a reply that gave the answer away")
            return SAFE_HINT
        return out
