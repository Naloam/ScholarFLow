from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from config.deps import get_db, require_project_access
from config.db import SessionLocal
from schemas.chunks import ChunkPage
from services.embedding.embeddings import embed_texts
from services.embedding.index_manager import rebuild_index
from services.embedding.vector_index import search
from services.reader.repository import get_chunks_by_ids, list_all_chunks, list_chunks
from services.tasks import create_task, set_task

router = APIRouter(
    prefix="/api/projects/{project_id}/chunks",
    tags=["chunks"],
    dependencies=[Depends(require_project_access)],
)


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
    db: Session = Depends(get_db),
) -> ChunkPage:
    vec = embed_texts([q])[0]
    results = search(project_id, vec, k)
    chunk_ids = [chunk_id for chunk_id, _score in results]
    items = get_chunks_by_ids(db, project_id, chunk_ids)
    return ChunkPage(items=items, page=1, size=k, total=len(items))


def _rebuild_task(task_id: str, project_id: str) -> None:
    db = SessionLocal()
    try:
        set_task(db, task_id, "running")
        chunks = list_all_chunks(db, project_id)
        rebuild_index(project_id, [c.chunk_id for c in chunks], [c.text for c in chunks])
        set_task(db, task_id, "done")
    except Exception as exc:
        set_task(db, task_id, "failed", str(exc))
    finally:
        db.close()


@router.post("/rebuild", response_model=dict)
def rebuild_index_endpoint(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    task_id = create_task(db)
    background_tasks.add_task(_rebuild_task, task_id, project_id)
    return {"task_id": task_id}
