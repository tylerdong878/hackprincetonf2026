"""Per-run state shared by the deterministic tools (fetched docs, saved sources, forgeries)."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pipeline.config import (
    CASES_DIR,
    DAILY_POSTS,
    DAILY_RANGE_TEXT,
    DAILY_SOLVER_ATTEMPTS,
    DEFAULT_CLUE_BUDGET,
    EIA_FILE,
    MAX_SOLVER_ATTEMPTS,
    SKILLS_DIR,
)
from pipeline.events import EventLog
from pipeline.models import CallStats


@dataclass
class FetchedDoc:
    url: str
    title: str
    outlet: str
    published: str | None  # ISO date or datetime
    paragraphs: list[str]
    via: str  # "rss" | "article" | "data"

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


@dataclass
class SavedSource:
    id: str
    url: str
    outlet: str
    kind: str  # "outlet" | "official"
    date: str | None  # local (New Jersey) publication date, YYYY-MM-DD
    published_at: str | None  # ISO datetime (UTC, "Z") when known
    title: str
    text: str  # exact characters from the fetched document
    speaker: str | None
    before: str
    highlight: str
    after: str
    starts_mid_sentence: bool
    headline: bool = False  # the passage is the article's exact title

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class HttpFetcher(Protocol):
    def __call__(self, url: str) -> tuple[int, bytes, str]:
        """Return (status, body bytes, content-type)."""
        ...


def default_fetcher(url: str) -> tuple[int, bytes, str]:
    import httpx

    headers = {"User-Agent": "Mozilla/5.0 (compatible; case-builder/0.1)", "Accept": "*/*"}
    r = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
    return r.status_code, r.content, r.headers.get("content-type", "")


@dataclass
class SolverSession:
    attempt: int = 0
    opened: list[tuple[str, str]] = field(default_factory=list)  # (post_id, tool) in order, unique
    verdict: dict[str, Any] | None = None
    viewed_charts: list[str] = field(default_factory=list)


@dataclass
class RunContext:
    case_id: str
    topic: str
    clean: bool = False
    trick: str | None = None
    mode: str = "casefile"  # "casefile" (v1 feed, 4 posts, 1 trick) | "daily" (§7.1: 5 posts, 0-3 doctored)
    daily_date: str | None = None
    theme: str | None = None
    tricks: list[str] = field(default_factory=list)  # daily: the planned trick for each doctored post
    cases_dir: Path = CASES_DIR
    skills_dir: Path = SKILLS_DIR
    eia_path: Path = EIA_FILE
    events: EventLog = field(default_factory=EventLog)
    stats: CallStats = field(default_factory=CallStats)
    fetch: HttpFetcher = default_fetcher
    now: datetime = field(default_factory=lambda: datetime.now(UTC))
    clue_budget: int = DEFAULT_CLUE_BUDGET
    solver_vision: bool = True
    tool_images: bool = False
    persist: bool = True  # False for --dry-run: never touch data/
    docs: dict[str, FetchedDoc] = field(default_factory=dict)
    sources: list[SavedSource] = field(default_factory=list)
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    solver: SolverSession = field(default_factory=SolverSession)
    solver_history: list[dict[str, Any]] = field(default_factory=list)
    solver_round_base: int = 0  # attempts before the latest teacher rejection (retry limit is per round)
    write_count: int = 0
    safety_notes: list[str] = field(default_factory=list)
    teacher_feedback: list[str] = field(default_factory=list)
    _counters: dict[str, int] = field(default_factory=dict)
    # Parallel tool calls in one model turn run in threads: guard ids, lists and file writes.
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # -- case shape (casefile vs daily)
    @property
    def is_daily(self) -> bool:
        return self.mode == "daily"

    @property
    def expected_doctored(self) -> int:
        if self.is_daily:
            return len(self.tricks)
        return 0 if self.clean else 1

    @property
    def allowed_tricks(self) -> set[str] | None:
        if self.is_daily:
            return set(self.tricks)
        return {self.trick} if self.trick else None

    @property
    def post_count_range(self) -> tuple[int, int]:
        return (DAILY_POSTS, DAILY_POSTS) if self.is_daily else (3, 5)

    @property
    def max_solver_attempts(self) -> int:
        return DAILY_SOLVER_ATTEMPTS if self.is_daily else MAX_SOLVER_ATTEMPTS

    def case_shape(self) -> str:
        """One paragraph describing the case to build (goes to the orchestrator and the forger)."""
        if self.is_daily:
            tricks = ", ".join(self.tricks) if self.tricks else "none: every post is real today"
            return (f"Daily Grain for {self.daily_date} (theme: {self.theme}). Exactly {DAILY_POSTS} posts: "
                    f"{len(self.tricks)} doctored (tricks: {tricks}), at least one real post that sounds absurd but "
                    f"is true (real_suspicious), the rest plainly real. The briefing states the range "
                    f"'{DAILY_RANGE_TEXT}', never the count.")
        if self.clean:
            return "Case file: 4 posts, NO doctored post (all real), at least one real post that looks suspicious."
        return (f"Case file: 4 posts: exactly one doctored post (trick: {self.trick or 'your choice'}), at least one "
                "real post that looks suspicious, the rest real.")

    # -- paths
    @property
    def case_dir(self) -> Path:
        return self.cases_dir / self.case_id

    def vpath(self, name: str) -> str:
        """Virtual (agent-visible) path of a file in this case folder."""
        return f"/cases/{self.case_id}/{name}"

    def next_id(self, prefix: str) -> str:
        with self.lock:
            n = self._counters.get(prefix, 0) + 1
            self._counters[prefix] = n
            return f"{prefix}{n}"

    # -- lookups
    def doc_for(self, url: str) -> FetchedDoc | None:
        return self.docs.get(canonical_url(url))

    def add_doc(self, doc: FetchedDoc) -> None:
        with self.lock:
            self.docs[canonical_url(doc.url)] = doc

    def source(self, source_id: str) -> SavedSource | None:
        return next((s for s in self.sources if s.id == source_id), None)

    # -- files
    def write_json(self, name: str, obj: Any, agent: str, *, spoiler: bool = False) -> None:
        if not self.persist:
            return
        self.case_dir.mkdir(parents=True, exist_ok=True)
        (self.case_dir / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.events.emit("file_written", agent=agent, path=self.vpath(name), spoiler=spoiler)

    def read_json(self, name: str) -> Any:
        return json.loads((self.case_dir / name).read_text(encoding="utf-8"))


def canonical_url(url: str) -> str:
    u = url.strip()
    if "#" in u:
        u = u.split("#", 1)[0]
    u = u.replace("http://", "https://", 1)
    u = u.replace("://www.", "://", 1)
    return u.rstrip("/")
