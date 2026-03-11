from __future__ import annotations

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    chunk_id: str
    text: str
    section: str | None = None
    page: int | None = None
    type: str | None = None
    embedding_id: str | None = None
    paper_id: str | None = None
    project_id: str | None = None


class FetchItem(BaseModel):
    paper_id: str
    pdf_url: str | None = None


class FetchResult(BaseModel):
    paper_id: str
    pdf_path: str | None = None
    grobid_xml_path: str | None = None
    status: str


class ReadResult(BaseModel):
    paper_id: str
    chunks: list[Chunk] = Field(default_factory=list)
