"""Request bodies (CONTRACT §5 and §7)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .store import ID_PATTERN


class EvidenceRequest(BaseModel):
    player_id: str = Field(pattern=ID_PATTERN)
    post_id: str
    tool: str


class PostVerdict(BaseModel):
    doctored: bool
    trick: str | None = None
    confidence: float | None = Field(default=None, ge=0.5, le=1.0)


class VerdictRequest(BaseModel):
    player_id: str = Field(pattern=ID_PATTERN)
    verdicts: dict[str, PostVerdict] | None = None  # omitted -> use the recorded per-card answers


class AnswerRequest(BaseModel):
    player_id: str = Field(pattern=ID_PATTERN)
    post_id: str
    doctored: bool
    trick: str | None = None
    confidence: float | None = Field(default=None, ge=0.5, le=1.0)


class RejectRequest(BaseModel):
    reason: str | None = None


class FoolJudgeRequest(BaseModel):
    player_id: str = Field(pattern=ID_PATTERN)
    deck_id: str = Field(pattern=ID_PATTERN)
    edit: dict
