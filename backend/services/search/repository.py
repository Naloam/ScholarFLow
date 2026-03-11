from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.search_result import SearchResult as SearchResultModel
from schemas.search import SearchResult as SearchResultSchema


def normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def save_search_result(db: Session, project_id: str, result: SearchResultSchema) -> str:
    raw_query = result.query or ""
    normalized = normalize_query(raw_query)
    row = SearchResultModel(
        id=str(uuid4()),
        project_id=project_id,
        query=raw_query,
        query_normalized=normalized,
        results=result.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def get_latest_search_result(
    db: Session, project_id: str, query: str | None = None, exact: bool = False
) -> SearchResultSchema | None:
    stmt = select(SearchResultModel).where(SearchResultModel.project_id == project_id)
    if query:
        qn = normalize_query(query)
        if exact:
            stmt = stmt.where(SearchResultModel.query_normalized == qn)
        else:
            stmt = stmt.where(SearchResultModel.query_normalized.ilike(f"%{qn}%"))
    stmt = stmt.order_by(SearchResultModel.created_at.desc()).limit(1)
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        return None
    return SearchResultSchema(**row.results)


def list_search_results(
    db: Session,
    project_id: str,
    page: int,
    size: int,
    query: str | None = None,
    exact: bool = False,
) -> tuple[list[SearchResultSchema], int]:
    base = select(SearchResultModel).where(SearchResultModel.project_id == project_id)
    count_stmt = select(func.count()).select_from(SearchResultModel).where(
        SearchResultModel.project_id == project_id
    )
    if query:
        qn = normalize_query(query)
        if exact:
            base = base.where(SearchResultModel.query_normalized == qn)
            count_stmt = count_stmt.where(SearchResultModel.query_normalized == qn)
        else:
            base = base.where(SearchResultModel.query_normalized.ilike(f"%{qn}%"))
            count_stmt = count_stmt.where(SearchResultModel.query_normalized.ilike(f"%{qn}%"))

    total = db.execute(count_stmt).scalar_one()
    stmt = (
        base.order_by(SearchResultModel.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    items = [SearchResultSchema(**row.results) for row in rows]
    return items, int(total)
