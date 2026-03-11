from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.chunk import Chunk as ChunkModel
from schemas.agents import Chunk


def save_chunks(db: Session, project_id: str, paper_id: str, chunks: list[Chunk]) -> list[Chunk]:
    saved: list[Chunk] = []
    for ch in chunks:
        row = ChunkModel(
            id=ch.chunk_id or f"ch_{uuid4().hex}",
            project_id=project_id,
            paper_id=paper_id,
            text=ch.text,
            section=ch.section,
            page=ch.page,
            type=ch.type,
            embedding_id=ch.embedding_id,
        )
        db.add(row)
        saved.append(
            Chunk(
                chunk_id=row.id,
                text=row.text,
                section=row.section,
                page=row.page,
                type=row.type,
                embedding_id=row.embedding_id,
                paper_id=row.paper_id,
                project_id=row.project_id,
            )
        )
    db.commit()
    return saved


def list_chunks(
    db: Session,
    project_id: str,
    paper_id: str | None,
    page: int,
    size: int,
) -> tuple[list[Chunk], int]:
    stmt = select(ChunkModel).where(ChunkModel.project_id == project_id)
    count_stmt = select(func.count()).select_from(ChunkModel).where(
        ChunkModel.project_id == project_id
    )
    if paper_id:
        stmt = stmt.where(ChunkModel.paper_id == paper_id)
        count_stmt = count_stmt.where(ChunkModel.paper_id == paper_id)

    total = db.execute(count_stmt).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(ChunkModel.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    items = [
        Chunk(
            chunk_id=row.id,
            text=row.text,
            section=row.section,
            page=row.page,
            type=row.type,
            embedding_id=row.embedding_id,
            paper_id=row.paper_id,
            project_id=row.project_id,
        )
        for row in rows
    ]
    return items, int(total)
