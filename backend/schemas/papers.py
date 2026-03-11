from datetime import datetime
from pydantic import BaseModel, Field


class PaperMeta(BaseModel):
    id: str | None = None
    doi: str | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    pdf_url: str | None = None
    url: str | None = None
    bibtex: str | None = None
    source: str | None = None


class PaperCreate(BaseModel):
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    upload_id: str | None = None
    auto_fetch: bool = False


class PaperSummary(BaseModel):
    id: str
    title: str
    abstract: str | None = None
    summary: str | None = None
    created_at: datetime | None = None
