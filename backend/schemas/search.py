from datetime import datetime
from pydantic import BaseModel

from schemas.papers import PaperMeta


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    year_from: int | None = None
    year_to: int | None = None
    sources: list[str] | None = None


class SearchResult(BaseModel):
    query: str
    items: list[PaperMeta]
    created_at: datetime | None = None


class SearchResponse(BaseModel):
    result: SearchResult


class SearchResultsPage(BaseModel):
    items: list[SearchResult]
    page: int
    size: int
    total: int
