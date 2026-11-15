"""The conversation: one phone number <-> one Grain of Salt player, driven through the game's own /api routes.

`Engine.handle(handle, text)` returns the replies for one incoming text. All scoring, clue budgets, streaks and
answer keys stay in the game server; the bot only remembers where each phone is in today's Daily.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Protocol

from . import render
from .parse import parse
from .partner import Partner
from .render import Out

TOOL_ORDER = ("data", "source", "account")  # what CHECK opens when no tool is named
MAX_NUDGE_TRIES = 5  # failed reminder sends per player per day before giving up until tomorrow

log = logging.getLogger("gos.imessage")


class HttpClient(Protocol):  # httpx.Client and fastapi's TestClient both fit
    def get(self, url: str, **kw: Any) -> Any: ...
    def post(self, url: str, **kw: Any) -> Any: ...


class ApiError(Exception):
    def __init__(self, status: int, detail: str = ""):
        super().__init__(f"{status} {detail}")
        self.status, self.detail = status, detail


class GameAPI:
    def __init__(self, http: HttpClient):
        self.http = http

    def _ok(self, r: Any) -> dict:
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", "")
            except Exception:
                detail = ""
            raise ApiError(r.status_code, str(detail))
        return r.json()

    def new_player(self) -> str:
        return self._ok(self.http.post("/api/players", json={}))["player_id"]

    def player(self, pid: str) -> dict:
        return self._ok(self.http.get(f"/api/players/{pid}"))

    def daily(self, pid: str) -> dict:
        return self._ok(self.http.get("/api/daily", params={"player_id": pid}))

    def evidence(self, case_id: str, pid: str, post_id: str, tool: str) -> dict:
        return self._ok(self.http.post(f"/api/cases/{case_id}/evidence",
                                       json={"player_id": pid, "post_id": post_id, "tool": tool}))

    def answer(self, case_id: str, pid: str, post_id: str, doctored: bool, trick: str | None) -> dict:
        return self._ok(self.http.post(f"/api/cases/{case_id}/answer",
                                       json={"player_id": pid, "post_id": post_id, "doctored": doctored,
                                             "trick": trick}))

    def verdict(self, case_id: str, pid: str) -> dict:
        return self._ok(self.http.post(f"/api/cases/{case_id}/verdict", json={"player_id": pid}))


@dataclass
class Session:
    handle: str
    player_id: str
    case_id: str | None = None
    awaiting_trick: str | None = None  # post id we asked "which trick?" for
    opened: dict[str, list[str]] = field(default_factory=dict)  # post id -> tools opened (this case)
    muted: bool = False
    last_nudge: str | None = None  # ISO date
    space_id: str | None = None  # Photon conversation, for nudges
    agent_id: str | None = None
    history: list[list[str]] = field(default_factory=list)  # partner chat: [role, text], last few turns
    last_reveal: dict | None = None  # the post just revealed, so the partner can discuss it
    partner_day: str | None = None
    partner_count: int = 0  # partner replies today (capped: the free model tier is small)


class Sessions:
    """Phone -> Session, saved as one JSON file (small: one row per player)."""

    def __init__(self, path: Path | None):
        self.path, self.lock = path, threading.Lock()
        self.rows: dict[str, Session] = {}
        if path and path.exists():
            for h, row in json.loads(path.read_text(encoding="utf-8")).items():
                self.rows[h] = Session(**row)

    def get(self, handle: str) -> Session | None:
        return self.rows.get(handle)

    def put(self, s: Session) -> None:
        with self.lock:
            self.rows[s.handle] = s
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps({h: asdict(r) for h, r in self.rows.items()}, indent=1), encoding="utf-8")
                os.replace(tmp, self.path)

    def all(self) -> list[Session]:
        return list(self.rows.values())


class Engine:
    def __init__(self, api: GameAPI, sessions: Sessions, partner: Partner | None = None,
                 answer_key: Callable[[str], dict] | None = None):
        """partner: free-form replies (None -> commands only). answer_key(case_id) -> {post_id: key}, read
        locally so the partner's hints point the right way; it is never shown to the player."""
        self.api, self.sessions = api, sessions
        self.partner, self.answer_key = partner, answer_key
        self.nudge_failures: dict[tuple[str, str], int] = {}  # (handle, ISO day) -> failed reminder sends

    # ---- entry point ---------------------------------------------------------------

    def handle(self, handle: str, text: str, *, space_id: str | None = None, agent_id: str | None = None) -> list[Out]:
        s = self.sessions.get(handle)
        first = s is None
        if s is None:
            s = Session(handle=handle, player_id=self.api.new_player())
        if space_id:
            s.space_id, s.agent_id = space_id, agent_id
        try:
            if first:
                out = [Out.t(render.WELCOME)] + self.play(s)
            else:
                out = self.dispatch(s, text)
        except ApiError as e:
            out = [Out.t(self.api_trouble(e))]
        self.sessions.put(s)
        return out

    def dispatch(self, s: Session, text: str) -> list[Out]:
        daily = self.api.daily(s.player_id)
        intent = parse(text, daily["case"].get("trick_options"))
        if intent.kind == "help":
            return [Out.t(render.HELP)]
        if intent.kind == "stats":
            return [render.stats(self.api.player(s.player_id))]
        if intent.kind == "mute":
            s.muted = True
            return [Out.t("Reminders paused. Text PLAY anytime to play, or REMIND to turn them back on.")]
        if intent.kind == "unmute":
            s.muted = False
            return [Out.t("Reminders on: I'll text you when a new Daily drops.")]
        if intent.kind == "play":
            return self.play(s, daily)
        if intent.kind == "reset":  # a fresh detective (handy between demo players)
            s.player_id, s.case_id, s.opened, s.awaiting_trick = self.api.new_player(), None, {}, None
            s.history, s.last_reveal = [], None
            return [Out.t("New detective, clean record.\n\n" + render.WELCOME)] + self.play(s)
        post, index = self.current(s, daily)
        if post is None:
            # Done for today: chat about it. Not started yet: any other text means "play".
            if daily.get("already_played") and intent.kind in ("unknown", "hint"):
                return self.chat(s, daily, text, None, None) or self.play(s, daily)
            return self.play(s, daily)
        if intent.kind == "real":
            return self.answer(s, daily, post, False, None)
        if intent.kind == "fake":
            if intent.trick or intent.not_sure:
                return self.answer(s, daily, post, True, intent.trick)
            s.awaiting_trick = post["id"]
            return [render.trick_question(daily["case"].get("trick_options") or [])]
        if intent.kind == "trick" and s.awaiting_trick == post["id"]:
            if intent.trick or intent.not_sure:
                return self.answer(s, daily, post, True, intent.trick)
            return [Out.t("Pick a number from the list, or 0 if you're not sure.")]
        if intent.kind == "check":
            return self.check(s, daily, post, intent.tool)
        if intent.kind == "hint":
            return self.chat(s, daily, text, post, index, ask_hint=True) or \
                [Out.t("My hint: spend a 🔍. Text CHECK.")]
        if s.awaiting_trick == post["id"]:
            said = self.chat(s, daily, text, post, index) or []
            return said + [render.trick_question(daily["case"].get("trick_options") or [])]
        return self.chat(s, daily, text, post, index) or [Out.t("Didn't catch that. " + render.COMMANDS)]

    def chat(self, s: Session, daily: dict, text: str, post: dict | None, index: int | None,
             ask_hint: bool = False) -> list[Out] | None:
        """A partner reply, or None when there is no partner, it failed, or today's cap is used up."""
        if self.partner is None or not self.partner.available():
            return None
        today = daily.get("date") or ""
        if s.partner_day != today:
            s.partner_day, s.partner_count = today, 0
        if s.partner_count >= self.partner.daily_cap:
            return [Out.t("I'm out of words for today. 🧂 Commands still work: " + render.COMMANDS)]
        case = daily["case"]
        key, opened = None, {}
        if post is not None:
            if self.answer_key:
                try:
                    key = (self.answer_key(case["id"]) or {}).get(post["id"])
                except Exception:
                    key = None
            for tool in s.opened.get(post["id"], []):  # re-opening is free
                try:
                    opened[tool] = self.api.evidence(case["id"], s.player_id, post["id"], tool)["evidence"]
                except ApiError:
                    pass
        reply = self.partner.reply(text=text, history=[(r, t) for r, t in s.history], post=post, index=index,
                                   key=key, opened=opened, last_reveal=s.last_reveal,
                                   options=case.get("trick_options") or [], ask_hint=ask_hint)
        if not reply:
            return None
        s.partner_count += 1
        s.history = (s.history + [["user", text], ["assistant", reply]])[-12:]
        return [Out.t(reply)]

    # ---- steps ---------------------------------------------------------------------

    def current(self, s: Session, daily: dict) -> tuple[dict | None, int]:
        """The first unanswered post of today's Daily, or (None, -1) when done/not started."""
        if daily.get("already_played") or s.case_id != daily["case"]["id"]:
            return None, -1
        answered = daily.get("answered") or {}
        for i, p in enumerate(daily["case"]["posts"]):
            if p["id"] not in answered:
                return p, i
        return None, -1

    def play(self, s: Session, daily: dict | None = None) -> list[Out]:
        daily = daily or self.api.daily(s.player_id)
        case = daily["case"]
        if daily.get("already_played"):
            result = daily.get("result") or {}
            return [Out.t(f"You've played Daily #{daily.get('daily_number')} today. Next one at midnight ET."),
                    Out.t(result.get("share_text", ""))] if result.get("share_text") else \
                [Out.t("You've played today's Daily. Next one at midnight ET.")]
        out: list[Out] = []
        if s.case_id != case["id"]:
            s.case_id, s.opened, s.awaiting_trick = case["id"], {}, None
        post, index = self.current(s, daily)
        if index <= 0:
            out.append(render.intro(daily))
        else:
            out.append(Out.t(f"Picking up where you left off: Daily #{daily.get('daily_number')}."))
        out += self.show(daily, index if index >= 0 else 0)
        return out

    def show(self, daily: dict, index: int) -> list[Out]:
        posts = daily["case"]["posts"]
        return render.card(posts[index], index, len(posts), int(daily.get("clues_left") or 0))

    def answer(self, s: Session, daily: dict, post: dict, doctored: bool, trick: str | None) -> list[Out]:
        s.awaiting_trick = None
        case = daily["case"]
        try:
            res = self.api.answer(case["id"], s.player_id, post["id"], doctored, trick)
            out = render.reveal(res["result"], trick)
            r = res["result"]
            s.last_reveal = {"body": post.get("body"), "outcome": r.get("outcome"), "doctored": r.get("doctored"),
                             "trick": r.get("trick"), "tell": r.get("tell"), "explanation": r.get("explanation")}
        except ApiError as e:
            if e.status != 409:  # 409: answered already (e.g. from another device); just move on
                raise
            out = []
        daily = self.api.daily(s.player_id)
        nxt, index = self.current(s, daily)
        if nxt is not None:
            return out + self.show(daily, index)
        return out + render.finish(self.api.verdict(case["id"], s.player_id))

    def check(self, s: Session, daily: dict, post: dict, tool: str | None) -> list[Out]:
        tools = post.get("tools") or []
        opened = s.opened.setdefault(post["id"], [])
        if tool and tool not in tools:
            names = ", ".join(t.upper() for t in tools) or "nothing"
            return [Out.t(f"No {tool} for this post. You can check: {names}.")]
        if tool is None:
            fresh = [t for t in TOOL_ORDER if t in tools and t not in opened]
            if not fresh:
                return [Out.t("You've opened everything for this post. REAL or FAKE?")]
            tool = fresh[0]
        try:
            res = self.api.evidence(daily["case"]["id"], s.player_id, post["id"], tool)
        except ApiError as e:
            if e.status == 409:
                return [Out.t("Out of 🔍 for today. Trust your gut: REAL or FAKE?")]
            raise
        if tool not in opened:
            opened.append(tool)
        return render.evidence(tool, res["evidence"], int(res.get("clues_left") or 0))

    # ---- reminders -----------------------------------------------------------------

    def due_nudges(self, today: date) -> list[tuple[Session, list[Out]]]:
        """Players to remind today: they have a conversation, aren't muted, haven't played or been reminded, and
        haven't hit MAX_NUDGE_TRIES. Read-only: send_reminders() marks a player only once their text is sent."""
        day = today.isoformat()
        due = []
        for s in self.sessions.all():
            if s.muted or not s.space_id or s.last_nudge == day:
                continue
            if self.nudge_failures.get((s.handle, day), 0) >= MAX_NUDGE_TRIES:
                continue
            try:
                daily = self.api.daily(s.player_id)
            except ApiError:
                continue
            if daily.get("already_played") or daily.get("date") != day:
                continue
            theme = f": {daily['theme']}" if daily.get("theme") else ""
            msg = f"🧂 Daily #{daily.get('daily_number')} is up{theme}. 5 posts, 0–3 doctored. Text PLAY."
            due.append((s, [Out.t(msg)]))
        return due

    def send_reminders(self, today: date, send: Callable[[Session, list[Out]], None]) -> int:
        """Text today's reminder to everyone due; returns how many were sent. A player is marked reminded only
        after `send` returns, so a failed send is retried at the next check instead of lost, and one failure
        doesn't stop the rest. `send` should use one idempotency key per player per day (photon_io.nudge_key), so
        retrying a send that did land doesn't text them twice."""
        day = today.isoformat()
        sent = 0
        for s, outs in self.due_nudges(today):
            try:
                send(s, outs)
            except Exception as e:
                tries = self.nudge_failures[(s.handle, day)] = self.nudge_failures.get((s.handle, day), 0) + 1
                log.warning("reminder to %s failed (%s), try %d of %d", s.handle[-4:], type(e).__name__, tries,
                            MAX_NUDGE_TRIES)
                continue
            s.last_nudge = day
            self.sessions.put(s)
            sent += 1
            log.info("-> %s: daily reminder", s.handle[-4:])
        return sent

    @staticmethod
    def api_trouble(e: ApiError) -> str:
        if e.status == 404:
            return "No Daily is out yet. Check back soon!"
        if e.status == 429:
            return "Whoa, that's fast. Give it a minute and try again."
        return "Something went wrong on my end. Try again in a moment."
