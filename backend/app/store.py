"""File-backed storage: cases (data/cases/<id>/) and player profiles (data/players/<id>/).

Cases are re-read from disk on every request so the pipeline can add or approve
cases while the server runs. The files are tiny, so no cache is needed.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scoring import TRICKS, empty_counters

# Ids become directory names, so only allow a safe charset (no dots, no slashes).
ID_PATTERN = r"^[A-Za-z0-9_-]{1,128}$"
_ID_RE = re.compile(ID_PATTERN)


def valid_id(value: str) -> bool:
    return bool(_ID_RE.fullmatch(value or ""))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path: Path, data: Any) -> None:
    """Atomic write: temp file + replace, so readers never see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


@dataclass
class CaseRecord:
    id: str
    dir: Path
    case: dict
    meta: dict

    @property
    def approved(self) -> bool:
        return self.meta.get("status") == "approved"

    @property
    def number(self) -> float:
        n = self.case.get("number")
        return n if isinstance(n, (int, float)) else float("inf")

    def answer_key(self) -> dict:
        return read_json(self.dir / "answer_key.json", {}) or {}

    def evidence(self) -> dict:
        return read_json(self.dir / "evidence.json", {}) or {}

    def solver_log(self) -> str | None:
        path = self.dir / "solver_log.md"
        return path.read_text(encoding="utf-8") if path.is_file() else None


def is_clean(answer_key: dict, meta: dict) -> bool:
    if "clean_case" in answer_key:
        return bool(answer_key["clean_case"])
    return not meta.get("tricks")


def read_jsonl(path: Path) -> list[dict] | None:
    """Parse a .jsonl file; None if it doesn't exist. Bad lines are skipped."""
    if not path.is_file():
        return None
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # e.g. a half-written last line while the pipeline is running
    return events


@dataclass
class Store:
    data_dir: Path
    lock: threading.RLock = field(default_factory=threading.RLock)
    # (player_id, case_id) -> set of (post_id, tool) already opened. In memory by design.
    sessions: dict[tuple[str, str], set[tuple[str, str]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)

    @property
    def cases_dir(self) -> Path:
        return self.data_dir / "cases"

    @property
    def players_dir(self) -> Path:
        return self.data_dir / "players"

    # ---- cases -------------------------------------------------------------

    def get_case(self, case_id: str) -> CaseRecord | None:
        if not valid_id(case_id):
            return None
        d = self.cases_dir / case_id
        try:
            case = read_json(d / "case.json")
            meta = read_json(d / "meta.json")
        except (ValueError, OSError):
            return None  # e.g. being written by the pipeline right now
        if not isinstance(case, dict) or not isinstance(meta, dict):
            return None
        return CaseRecord(id=case_id, dir=d, case=case, meta=meta)

    def all_cases(self) -> list[CaseRecord]:
        if not self.cases_dir.is_dir():
            return []
        recs = [self.get_case(d.name) for d in self.cases_dir.iterdir() if d.is_dir()]
        recs = [r for r in recs if r is not None]
        return sorted(recs, key=lambda r: (r.number, r.id))

    def approved_cases(self) -> list[CaseRecord]:
        return [r for r in self.all_cases() if r.approved]

    def playable_case(self, case_id: str) -> CaseRecord | None:
        rec = self.get_case(case_id)
        return rec if rec and rec.approved else None

    def case_file(self, case_id: str, name: str) -> Path | None:
        """Path to a file in a case folder, even if case.json/meta.json aren't written yet."""
        return self.cases_dir / case_id / name if valid_id(case_id) else None

    def save_meta(self, rec: CaseRecord) -> None:
        write_json(rec.dir / "meta.json", rec.meta)

    # ---- crowd stats: data/stats/<case_id>.json --------------------------------

    def _stats_path(self, case_id: str) -> Path:
        if not valid_id(case_id):
            raise ValueError("invalid case id")
        return self.data_dir / "stats" / f"{case_id}.json"

    def case_stats(self, case_id: str) -> dict:
        """post_id -> {n, said_doctored, correct} for a case (empty if none yet)."""
        try:
            stats = read_json(self._stats_path(case_id), {}) or {}
        except (ValueError, OSError):
            return {}
        posts = stats.get("posts") if isinstance(stats, dict) else None
        return posts if isinstance(posts, dict) else {}

    def bump_stats(self, case_id: str, post_id: str, said_doctored: bool, correct: bool) -> dict:
        """Count one real answer and return that post's updated counts."""
        with self.lock:
            path = self._stats_path(case_id)
            stats = read_json(path, {}) or {}
            post = stats.setdefault("posts", {}).setdefault(post_id, {"n": 0, "said_doctored": 0, "correct": 0})
            post["n"] += 1
            post["said_doctored"] += int(said_doctored)
            post["correct"] += int(correct)
            write_json(path, stats)
            return dict(post)

    # ---- Con the Con: data/fool_deck/*.json and data/fool_cache/ ------------------

    def fool_deck(self) -> list[dict]:
        d = self.data_dir / "fool_deck"
        items = []
        for path in sorted(d.glob("*.json")) if d.is_dir() else []:
            try:
                item = read_json(path)
            except (ValueError, OSError):
                continue
            if isinstance(item, dict) and isinstance(item.get("post"), dict):
                item.setdefault("id", path.stem)
                items.append(item)
        return items

    def fool_item(self, deck_id: str) -> dict | None:
        return next((i for i in self.fool_deck() if i.get("id") == deck_id), None)

    def _fool_cache_path(self, key: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("bad cache key")
        return self.data_dir / "fool_cache" / f"{key}.json"

    def fool_cache_get(self, key: str) -> dict | None:
        try:
            con = read_json(self._fool_cache_path(key))
        except ValueError:
            return None
        return con if isinstance(con, dict) else None

    def fool_cache_put(self, key: str, con: dict) -> None:
        write_json(self._fool_cache_path(key), con)

    # ---- players -----------------------------------------------------------

    def _profile_path(self, player_id: str) -> Path:
        if not valid_id(player_id):
            raise ValueError("invalid player id")
        return self.players_dir / player_id / "profile.json"

    def load_profile(self, player_id: str) -> dict | None:
        profile = read_json(self._profile_path(player_id))
        if not isinstance(profile, dict):
            return None
        profile.setdefault("player_id", player_id)
        profile.setdefault("created_at", now_iso())
        tricks = profile.setdefault("tricks", {})
        for t in TRICKS:
            tricks.setdefault(t, empty_counters())
        for counters in tricks.values():
            for k, v in empty_counters().items():
                counters.setdefault(k, v)
        for k, v in new_profile(player_id).items():
            profile.setdefault(k, v)
        return profile

    def save_profile(self, profile: dict) -> None:
        write_json(self._profile_path(profile["player_id"]), profile)

    def create_profile(self) -> dict:
        with self.lock:
            while True:
                pid = secrets.token_hex(5)  # 10 hex chars
                if not self._profile_path(pid).exists():
                    break
            profile = new_profile(pid)
            self.save_profile(profile)
        return profile


def new_profile(player_id: str) -> dict:
    return {
        "player_id": player_id,
        "created_at": now_iso(),
        "tricks": {t: empty_counters() for t in TRICKS},
        "recent": [],
        "history": [],
        # v2 (CONTRACT §7)
        "answers": {},        # case_id -> post_id -> {doctored, trick, at}: per-card answers
        "daily_played": [],   # ET dates (YYYY-MM-DD) on which the player finished a daily
        "daily_results": {},  # case_id -> the stored verdict response for a finished daily
        "fool_rounds": [],    # Con the Con: [{deck_id, outcome, at}], last 50
    }
