"""The conversation: one phone number <-> one Grain of Salt player, driven through the game's own /api routes.

`Engine.handle(handle, text)` returns the replies for one incoming text. All scoring, clue budgets, streaks and
answer keys stay in the game server; the bot only remembers where each phone is in today's Daily.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from . import render
from .parse import parse
from .render import Out

TOOL_ORDER = ("data", "source", "account")  # what CHECK opens when no tool is named


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
    def __init__(self, api: GameAPI, sessions: Sessions):
        self.api, self.sessions = api, sessions

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
            return [Out.t("New detective, clean record.\n\n" + render.WELCOME)] + self.play(s)
        post, index = self.current(s, daily)
        if post is None:  # nothing in progress: any other text means "play"
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
        if s.awaiting_trick == post["id"]:
            return [render.trick_question(daily["case"].get("trick_options") or [])]
        return [Out.t("Didn't catch that. " + render.COMMANDS)]

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
        """Players to remind today: they have a conversation, aren't muted, haven't played or been nudged."""
        due = []
        for s in self.sessions.all():
            if s.muted or not s.space_id or s.last_nudge == today.isoformat():
                continue
            try:
                daily = self.api.daily(s.player_id)
            except ApiError:
                continue
            if daily.get("already_played") or daily.get("date") != today.isoformat():
                continue
            theme = f": {daily['theme']}" if daily.get("theme") else ""
            msg = f"🧂 Daily #{daily.get('daily_number')} is up{theme}. 5 posts, 0–3 doctored. Text PLAY."
            s.last_nudge = today.isoformat()
            self.sessions.put(s)
            due.append((s, [Out.t(msg)]))
        return due

    @staticmethod
    def api_trouble(e: ApiError) -> str:
        if e.status == 404:
            return "No Daily is out yet. Check back soon!"
        if e.status == 429:
            return "Whoa, that's fast. Give it a minute and try again."
        return "Something went wrong on my end. Try again in a moment."
