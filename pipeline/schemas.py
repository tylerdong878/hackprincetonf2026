"""Pydantic models that mirror CONTRACT.md §2 exactly (extra keys are rejected)."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

TrickId = Literal["out-of-context-quote", "misleading-chart", "cherry-picked-stat", "edited-detail"]
ToolId = Literal["source", "data", "account"]
Status = Literal["draft", "awaiting_approval", "approved", "rejected"]
Difficulty = Literal["easy", "medium", "hard"]
CardStyle = Literal["headline", "quote", "chart", "stat"]

_ISO_Z = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
_HEX = r"^#[0-9A-Fa-f]{6}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- case.json (§2.1)


class Author(_Strict):
    name: str = Field(min_length=1)
    handle: str = Field(min_length=2, pattern=r"^@\S+$")
    kind: Literal["outlet", "official", "person"]
    verified: bool
    avatar_color: str = Field(pattern=_HEX)


class Quote(_Strict):
    text: str = Field(min_length=1)
    speaker: str = Field(min_length=1)


class ChartPoint(_Strict):
    label: str = Field(min_length=1)
    value: float


class Chart(_Strict):
    type: Literal["bar", "line"]
    title: str
    unit: str
    points: list[ChartPoint] = Field(min_length=2)
    y_min: float
    y_max: float | None = None

    @model_validator(mode="after")
    def _axis(self) -> Chart:
        if self.y_max is not None and self.y_max <= self.y_min:
            raise ValueError("y_max must be greater than y_min")
        if any(p.value < self.y_min for p in self.points):
            raise ValueError("y_min cuts off data points (values below the axis start)")
        return self


class Post(_Strict):
    id: str = Field(pattern=r"^p\d+$")
    author: Author
    posted_at: str = Field(pattern=_ISO_Z)
    body: str
    quote: Quote | None = None
    chart: Chart | None = None
    source_label: str | None = None
    tools: list[ToolId] = Field(min_length=1)
    card_style: CardStyle | None = None  # §7.1, optional display hint for Daily cards

    @model_validator(mode="after")
    def _content(self) -> Post:
        if not (self.body.strip() or self.quote or self.chart):
            raise ValueError(f"post {self.id} has no body, quote or chart")
        if len(set(self.tools)) != len(self.tools):
            raise ValueError(f"post {self.id} lists a tool twice")
        return self


class Case(_Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    number: int = Field(ge=1)
    title: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    briefing: str = Field(min_length=1)
    clue_budget: int = Field(ge=0)
    trick_options: list[TrickId]
    posts: list[Post] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> Case:
        ids = [p.id for p in self.posts]
        if len(ids) != len(set(ids)):
            raise ValueError("post ids must be unique")
        return self


# ---------------------------------------------------------------- evidence.json (§2.2)


class SourceEvidence(_Strict):
    outlet: str
    date: str | None
    url: str = Field(pattern=r"^https?://")
    before: str
    highlight: str = Field(min_length=1)
    after: str


class DataEvidence(_Strict):
    title: str
    unit: str
    url: str = Field(pattern=r"^https?://")
    table: list[ChartPoint] = Field(min_length=1)
    honest_chart: Chart
    note: str


class AccountEvidence(_Strict):
    name: str
    handle: str
    created: str | None
    followers: int | None
    verified: bool
    bio: str
    recent_posts: list[str]


class PostEvidence(_Strict):
    source: SourceEvidence | None = None
    data: DataEvidence | None = None
    account: AccountEvidence | None = None

    def tool_ids(self) -> list[str]:
        return [t for t in ("source", "data", "account") if getattr(self, t) is not None]


class Evidence(RootModel[dict[str, PostEvidence]]):
    pass


# ---------------------------------------------------------------- answer_key.json (§2.3)


class ChartDiff(_Strict):
    type: Literal["chart"]
    shown: Chart
    original: Chart


class QuoteDiff(_Strict):
    type: Literal["quote"]
    shown: str
    original: str
    removed: list[str] = Field(min_length=1)


class StatDiff(_Strict):
    type: Literal["stat"]
    shown: str
    original: str
    missing: str


class DetailChange(_Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_: str = Field(alias="from", min_length=1)
    to: str = Field(min_length=1)


class DetailDiff(_Strict):
    """§7.1 edited-detail: a number, date or place swapped in a real headline."""

    type: Literal["detail"]
    shown: str
    original: str
    changed: list[DetailChange] = Field(min_length=1)


Diff = Annotated[ChartDiff | QuoteDiff | StatDiff | DetailDiff, Field(discriminator="type")]


class DoctoredAnswer(_Strict):
    doctored: Literal[True]
    trick: TrickId
    tell: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    con_line_fooled: str = Field(min_length=1)
    con_line_caught: str = Field(min_length=1)
    diff: Diff


class RealAnswer(_Strict):
    doctored: Literal[False]
    suspicious_real: bool
    explanation: str = Field(min_length=1)
    con_line_false_alarm: str = Field(min_length=1)


PostAnswer = Annotated[DoctoredAnswer | RealAnswer, Field(discriminator="doctored")]


class AnswerKey(_Strict):
    clean_case: bool
    posts: dict[str, PostAnswer]
    con_line_clean: str | None = None


# ---------------------------------------------------------------- meta.json (§2.4)


class Meta(_Strict):
    status: Status
    origin: Literal["seed", "pipeline"]
    daily: bool
    difficulty: Difficulty
    created_at: str = Field(pattern=_ISO_Z)
    tricks: list[TrickId]
    sources: list[str]
    rejection_reason: str | None = None
    mode: Literal["daily", "casefile"] | None = None  # §7.1 (absent = "casefile")
    daily_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    theme: str | None = None


# ---------------------------------------------------------------- cross-file checks


_DIFF_FOR_TRICK = {"out-of-context-quote": "quote", "misleading-chart": "chart", "cherry-picked-stat": "stat",
                   "edited-detail": "detail"}
_RANGE_RE = re.compile(r"\b0\s*[–-]\s*3\b")
_COUNT_RE = re.compile(r"\b(?:\d+|no|zero|one|two|three|four|five|a single|only one)\s+(?:of\s+(?:them|these)\s+)?"
                       r"(?:is\s+|are\s+)?(?:doctored|fakes?|forg\w*|lies?)\b", re.IGNORECASE)


def daily_briefing_problems(briefing: str) -> list[str]:
    """§7.1: a daily briefing states the range ("0–3 doctored today"), never the exact count."""
    probs = []
    if not _RANGE_RE.search(briefing):
        probs.append("the daily briefing must state the range '0–3 doctored today'")
    if _COUNT_RE.search(_RANGE_RE.sub(" ", briefing)):
        probs.append("the daily briefing must not state how many posts are doctored")
    return probs


def validate_bundle(case: dict, evidence: dict, answer_key: dict, meta: dict) -> tuple[Case, Evidence, AnswerKey, Meta]:
    """Validate the four files and their consistency. Raises ValueError on any problem."""
    c = Case.model_validate(case)
    e = Evidence.model_validate(evidence)
    a = AnswerKey.model_validate(answer_key)
    m = Meta.model_validate(meta)
    problems: list[str] = []
    post_ids = [p.id for p in c.posts]
    if set(post_ids) != set(e.root):
        problems.append(f"evidence posts {sorted(e.root)} != case posts {sorted(post_ids)}")
    if set(post_ids) != set(a.posts):
        problems.append(f"answer_key posts {sorted(a.posts)} != case posts {sorted(post_ids)}")
    for p in c.posts:
        ev = e.root.get(p.id)
        if ev is None:
            continue
        if sorted(p.tools) != sorted(ev.tool_ids()):
            problems.append(f"{p.id}: tools {p.tools} != evidence tools {ev.tool_ids()}")
        if ev.account is not None and ev.account.name != p.author.name:
            problems.append(f"{p.id}: account card name '{ev.account.name}' != author '{p.author.name}'")
    doctored = {pid: ans for pid, ans in a.posts.items() if isinstance(ans, DoctoredAnswer)}
    if a.clean_case and doctored:
        problems.append("clean_case is true but some posts are doctored")
    if not a.clean_case and not doctored:
        problems.append("clean_case is false but no post is doctored")
    if a.clean_case and not a.con_line_clean:
        problems.append("clean cases need con_line_clean")
    for pid, ans in doctored.items():
        if ans.diff.type != _DIFF_FOR_TRICK[ans.trick]:
            problems.append(f"{pid}: trick {ans.trick} needs a '{_DIFF_FOR_TRICK[ans.trick]}' diff, got '{ans.diff.type}'")
    if sorted(set(m.tricks)) != sorted({ans.trick for ans in doctored.values()}):
        problems.append(f"meta.tricks {m.tricks} != tricks used {sorted({x.trick for x in doctored.values()})}")
    if c.id and m and not c.trick_options:
        problems.append("trick_options is empty")
    for pid, ans in doctored.items():
        post = next((p for p in c.posts if p.id == pid), None)
        if post is not None and ans.trick == "edited-detail" and post.author.kind != "person":
            problems.append(f"{pid}: edited-detail is only allowed on made-up-account posts")
    if m.mode == "daily":
        if len(c.posts) != 5:
            problems.append(f"a daily case has 5 posts (got {len(c.posts)})")
        if c.clue_budget != 3:
            problems.append("a daily case has clue_budget 3")
        if len(doctored) > 3:
            problems.append(f"a daily case has 0-3 doctored posts (got {len(doctored)})")
        if not any(isinstance(x, RealAnswer) and x.suspicious_real for x in a.posts.values()):
            problems.append("a daily case needs at least one real-but-suspicious post")
        if not m.daily_date:
            problems.append("a daily case needs meta.daily_date")
        problems.extend(daily_briefing_problems(c.briefing))
    if problems:
        raise ValueError("; ".join(problems))
    return c, e, a, m
