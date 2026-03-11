from datetime import datetime
from pydantic import BaseModel


class ReviewScore(BaseModel):
    originality: int
    importance: int
    evidence_support: int
    soundness: int
    clarity: int
    value: int
    contextualization: int


class ReviewRequest(BaseModel):
    draft_version: int


class ReviewReport(BaseModel):
    id: str | None = None
    project_id: str | None = None
    draft_version: int | None = None
    scores: ReviewScore
    suggestions: list[str]
    created_at: datetime | None = None
