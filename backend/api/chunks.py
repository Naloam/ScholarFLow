from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config.deps import get_db
from schemas.chunks import ChunkPage
from services.embedding.embeddings import embed_texts
from services.embedding.vector_index import search
from services.reader.repository import list_chunks

router = APIRouter(prefix="/api/projects/{project_id}/chunks", tags=["chunks"])


@router.get("", response_model=ChunkPage)
def list_chunks_endpoint(
    project_id: str,
    paper_id: str | None = Query(default=None),
    section: str | None = Query(default=None),
    page_num: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ChunkPage:
    items, total = list_chunks(db, project_id, paper_id, section, page_num, page, size)
    return ChunkPage(items=items, page=page, size=size, total=total)


@router.get("/search", response_model=ChunkPage)
def search_chunks(
    project_id: str,
    q: str = Query(...),
    k: int = Query(default=5, ge=1, le=50),
) -> ChunkPage:
    vec = embed_texts([q])[0]
    results = search(project_id, vec, k)
    items = []
    for chunk_id, _score in results:
        items.append(
            {
                "chunk_id": chunk_id,
                "text": "",
                "section": None,
                "page": None,
                "type": None,
                "embedding_id": None,
                "paper_id": None,
                "project_id": project_id,
            }
        )
    return ChunkPage(items=items, page=1, size=k, total=len(items))
