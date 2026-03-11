from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.evidence import Evidence
from schemas.evidence import EvidenceItem


def save_evidence_items(db: Session, items: list[EvidenceItem]) -> list[EvidenceItem]:
    saved: list[EvidenceItem] = []
    for item in items:
        row = Evidence(
            id=str(uuid4()),
            project_id=item.project_id or "",
            claim_text=item.claim_text,
            paper_id=item.paper_id,
            chunk_id=item.chunk_id,
            draft_version=item.draft_version,
            page=item.page,
            section=item.section,
            snippet=item.snippet,
            confidence=item.confidence,
            type=item.type,
        )
        db.add(row)
        db.flush()
        saved.append(
            EvidenceItem(
                id=row.id,
                project_id=row.project_id,
                claim_text=row.claim_text,
                paper_id=row.paper_id,
                chunk_id=row.chunk_id,
                draft_version=row.draft_version,
                page=row.page,
                section=row.section,
                snippet=row.snippet,
                confidence=row.confidence,
                type=row.type,
                created_at=row.created_at,
            )
        )
    db.commit()
    return saved


def list_evidence_items(db: Session, project_id: str) -> list[EvidenceItem]:
    stmt = select(Evidence).where(Evidence.project_id == project_id)
    rows = db.execute(stmt).scalars().all()
    return [
        EvidenceItem(
            id=row.id,
            project_id=row.project_id,
            claim_text=row.claim_text,
            paper_id=row.paper_id,
            chunk_id=row.chunk_id,
            draft_version=row.draft_version,
            page=row.page,
            section=row.section,
            snippet=row.snippet,
            confidence=row.confidence,
            type=row.type,
            created_at=row.created_at,
        )
        for row in rows
    ]


def list_evidence_claims(db: Session, project_id: str) -> set[str]:
    stmt = select(Evidence.claim_text).where(Evidence.project_id == project_id)
    rows = db.execute(stmt).scalars().all()
    return {r for r in rows if r}
