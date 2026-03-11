from __future__ import annotations

from uuid import uuid4

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
