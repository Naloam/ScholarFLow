from datetime import datetime
from pydantic import BaseModel, Field


class ClaimRef(BaseModel):
    claim: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float | None = None


class DraftGenerateRequest(BaseModel):
    topic: str | None = None
    scope: str | None = None
    paper_ids: list[str] | None = None
    template_id: str | None = None
    language: str | None = None
    outline: list[str] | None = None


class DraftCreate(BaseModel):
    content: str
    section: str | None = None


class DraftRead(DraftCreate):
    id: str | None = None
    project_id: str | None = None
    version: int
    claims: list[ClaimRef] = Field(default_factory=list)
    created_at: datetime | None = None
