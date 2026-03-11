from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agents.search_agent import SearchAgent
from config.deps import get_db
from schemas.search import SearchRequest, SearchResponse, SearchResult, SearchResultsPage
from services.search.repository import (
    get_latest_search_result,
    list_search_results,
    save_search_result,
)

router = APIRouter(prefix="/api/projects/{project_id}/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def run_search(
    project_id: str, payload: SearchRequest, db: Session = Depends(get_db)
) -> SearchResponse:
    agent = SearchAgent()
    result_dict = agent.run(payload.model_dump())
    result = SearchResult(**result_dict["result"], created_at=datetime.utcnow())
    save_search_result(db, project_id, result)
    return SearchResponse(result=result)


@router.get("/results", response_model=SearchResultsPage)
def get_search_results(
    project_id: str,
    query: str | None = Query(default=None, description="Case-insensitive fuzzy match"),
    sources: list[str] | None = Query(default=None),
    year_from: int | None = Query(default=None),
    year_to: int | None = Query(default=None),
    exact: bool = Query(default=False, description="Use exact query match when true"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> SearchResultsPage:
    # list results stored in DB; sources/year filters apply to new searches only
    items, total = list_search_results(db, project_id, page=page, size=size, query=query, exact=exact)
    return SearchResultsPage(items=items, page=page, size=size, total=total)


@router.get("/results/latest", response_model=SearchResponse)
def get_latest_result(
    project_id: str,
    query: str | None = Query(default=None, description="Case-insensitive fuzzy match"),
    sources: list[str] | None = Query(default=None),
    year_from: int | None = Query(default=None),
    year_to: int | None = Query(default=None),
    exact: bool = Query(default=False, description="Use exact query match when true"),
    db: Session = Depends(get_db),
) -> SearchResponse:
    items, _ = list_search_results(db, project_id, page=1, size=1, query=query, exact=exact)
    result = items[0] if items else SearchResult(query="", items=[], created_at=None)
    return SearchResponse(result=result)
