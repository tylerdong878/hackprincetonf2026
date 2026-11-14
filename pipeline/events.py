"""`pipeline_log.jsonl` writer. Event shapes follow CONTRACT.md §6 exactly."""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Required fields per event type (CONTRACT §6). `t`, `type` and optional `spoiler` are added.
EVENT_FIELDS: dict[str, tuple[str, ...]] = {
    "plan_updated": ("todos",),
    "subagent_started": ("name", "task"),
    "tool_called": ("agent", "tool", "summary"),
    "file_written": ("agent", "path"),
    "subagent_finished": ("name", "summary"),
    "solver_result": ("pass", "tools_used", "difficulty", "attempt"),
    "awaiting_approval": (),
    "case_status": ("status",),
}
TODO_STATUSES = ("pending", "in_progress", "completed")
CASE_STATUSES = ("draft", "awaiting_approval", "approved", "rejected")

_SPOILER_RE = re.compile(
    r"\b(?:p\d|post\s*#?\d|out-of-context|misleading[- ]chart|cherry[- ]pick\w*|crop\w*|truncat\w*|doctor\w*|"
    r"forg(?:ed|ery)|y_min|axis|answer[_ ]key|tell)\b",
    re.IGNORECASE,
)


def looks_like_spoiler(*texts: str | None) -> bool:
    """Heuristic: does free text name a post, a trick, or how it was faked?"""
    return any(t and _SPOILER_RE.search(t) for t in texts)


def make_event(type_: str, t: float, *, spoiler: bool = False, **fields: Any) -> dict[str, Any]:
    """Build one event dict with keys in contract order; raises on a malformed event."""
    if type_ not in EVENT_FIELDS:
        raise ValueError(f"unknown event type {type_!r}")
    required = EVENT_FIELDS[type_]
    missing = [f for f in required if f not in fields]
    extra = [f for f in fields if f not in required]
    if missing or extra:
        raise ValueError(f"{type_}: missing {missing}, unexpected {extra}")
    if type_ == "plan_updated":
        todos = []
        for td in fields["todos"]:
            status = td.get("status", "pending")
            if status not in TODO_STATUSES:
                status = "pending"
            todos.append({"content": str(td.get("content", "")), "status": status})
        fields["todos"] = todos
    if type_ == "case_status" and fields["status"] not in CASE_STATUSES:
        raise ValueError(f"bad case status {fields['status']!r}")
    if type_ == "solver_result":
        fields["pass"] = bool(fields["pass"])
        fields["tools_used"] = list(fields["tools_used"])
        fields["attempt"] = int(fields["attempt"])
    event: dict[str, Any] = {"t": round(float(t), 2), "type": type_}
    for f in required:
        event[f] = fields[f]
    if spoiler:
        event["spoiler"] = True
    return event


class EventLog:
    """Appends events to `pipeline_log.jsonl` (if a path is given) and keeps them in memory."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        echo: Callable[[dict[str, Any]], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.path = path
        self.echo = echo
        self._clock = clock
        self._t0 = clock()
        self._lock = threading.Lock()
        self.events: list[dict[str, Any]] = []

    def elapsed(self) -> float:
        return self._clock() - self._t0

    def emit(self, type_: str, *, spoiler: bool = False, **fields: Any) -> dict[str, Any]:
        event = make_event(type_, self.elapsed(), spoiler=spoiler, **fields)
        with self._lock:
            self.events.append(event)
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        if self.echo is not None:
            try:
                self.echo(event)
            except Exception:  # noqa: BLE001  # printing must never break a run
                pass
        return event


def read_log(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
