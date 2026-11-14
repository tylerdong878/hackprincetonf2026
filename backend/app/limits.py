"""Limits for a public server (CONTRACT §8.5, §8.6).

- LiveUsage: live (uncached) Con the Con judge calls per server day (ET), across everyone and per player.
  In memory, and persisted to data/stats/con_live_usage.json so a restart doesn't hand out a fresh budget.
- RateLimiter: a loose fixed-window limit per client IP (public mode, /cases/*/answer).
"""
from __future__ import annotations

import hmac
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Request

from .store import read_json, write_json

CON_RESTING = {"error": "con_resting",
               "message": "The Con is resting. Try a saved round, or come back tomorrow."}


def token_matches(given: str | None, expected: str | None) -> bool:
    """Constant-time header check. An unset/empty expected token never matches."""
    if not expected or given is None:
        return False
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def client_ip(request: Request) -> str:
    """CF-Connecting-IP (Cloudflare tunnel), else the rightmost X-Forwarded-For entry (the one our own proxy
    appended; entries to its left are client-supplied), else the socket peer."""
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf
    xff = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    if xff:
        return xff[-1]
    return request.client.host if request.client else "unknown"


@dataclass
class LiveUsage:
    """Live judge calls per day. `reserve` before a live call, `release` the player's slot if it fails."""

    path: Path
    daily_cap: int
    per_player: int
    lock: threading.RLock = field(default_factory=threading.RLock)
    day: str = ""
    live: int = 0
    demo: int = 0
    players: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            saved = read_json(self.path, {}) or {}
        except (ValueError, OSError):
            saved = {}
        if isinstance(saved, dict):
            self.day = str(saved.get("date") or "")
            self.live = int(saved.get("live") or 0)
            self.demo = int(saved.get("demo") or 0)
            self.players = {str(k): int(v) for k, v in (saved.get("players") or {}).items()}

    def _roll(self, day: str) -> None:
        if day != self.day:
            self.day, self.live, self.demo, self.players = day, 0, 0, {}

    def _save(self) -> None:
        try:
            write_json(self.path, {"date": self.day, "live": self.live, "demo": self.demo, "players": self.players})
        except OSError:
            pass  # the in-memory count still holds

    def reserve(self, day: str, player_id: str, demo: bool) -> bool:
        """Count one live call. False (and nothing counted) when a cap is reached; demo calls skip the caps."""
        with self.lock:
            self._roll(day)
            if demo:
                self.demo += 1
            else:
                if self.live >= self.daily_cap or self.players.get(player_id, 0) >= self.per_player:
                    return False
                self.live += 1
                self.players[player_id] = self.players.get(player_id, 0) + 1
            self._save()
            return True

    def release(self, day: str, player_id: str, demo: bool) -> None:
        """A live call that failed doesn't use up the player's round. The global count stays: the provider
        still counted the request against the free quota."""
        if demo:
            return
        with self.lock:
            if day == self.day and self.players.get(player_id, 0) > 0:
                self.players[player_id] -= 1
                self._save()

    def snapshot(self) -> dict:
        with self.lock:
            return {"date": self.day, "live": self.live, "demo": self.demo, "players": dict(self.players)}


@dataclass
class RateLimiter:
    """At most `limit` hits per `window_s` seconds per key (fixed window). In memory."""

    limit: int
    window_s: float = 60.0
    clock: Callable[[], float] = time.monotonic
    lock: threading.Lock = field(default_factory=threading.Lock)
    hits: dict[str, tuple[float, int]] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self.lock:
            if len(self.hits) > 10_000:  # forget windows that are over
                self.hits = {k: v for k, v in self.hits.items() if now - v[0] < self.window_s}
            start, n = self.hits.get(key, (now, 0))
            if now - start >= self.window_s:
                start, n = now, 0
            if n >= self.limit:
                return False
            self.hits[key] = (start, n + 1)
            return True
