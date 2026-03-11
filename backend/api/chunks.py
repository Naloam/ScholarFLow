from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config.deps import get_db
from schemas.chunks import ChunkPage
from services.reader.repository import list_chunks

router = APIRouter(prefix="/api/projects/{project_id}/chunks", tags=["chunks"])


@router.get("", response_model=ChunkPage)
def list_chunks_endpoint(
    project_id: str,
    paper_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ChunkPage:
    items, total = list_chunks(db, project_id, paper_id, page, size)
    return ChunkPage(items=items, page=page, size=size, total=total)
