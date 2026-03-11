from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.draft import Draft
from schemas.drafts import DraftCreate, DraftRead


def _extract_claims(row: Draft) -> list[str]:
    if not row.claims:
        return []
    claims = []
    for c in row.claims:
        claim = c.get("claim") if isinstance(c, dict) else None
        if claim:
            claims.append(claim)
    return claims


def get_latest_claims(db: Session, project_id: str) -> list[str]:
    stmt = (
        select(Draft)
        .where(Draft.project_id == project_id)
        .order_by(Draft.created_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        return []
    return _extract_claims(row)


def get_claims_by_version(db: Session, project_id: str, version: int) -> list[str]:
    stmt = select(Draft).where(Draft.project_id == project_id, Draft.version == version)
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        return []
    return _extract_claims(row)


def _next_version(db: Session, project_id: str) -> int:
    stmt = select(func.max(Draft.version)).where(Draft.project_id == project_id)
    max_ver = db.execute(stmt).scalar_one()
    if max_ver is None:
        return 1
    return int(max_ver) + 1


def create_draft(
    db: Session,
    project_id: str,
    content: str,
    claims: list[dict] | None = None,
    section: str | None = None,
) -> DraftRead:
    version = _next_version(db, project_id)
    row = Draft(
        id=f"draft_{uuid4().hex}",
        project_id=project_id,
        version=version,
        section=section,
        content=content,
        claims=claims,
    )
    db.add(row)
    db.commit()
    return DraftRead(
        id=row.id,
        project_id=row.project_id,
        version=row.version,
        section=row.section,
        content=row.content,
        claims=row.claims or [],
        created_at=row.created_at,
    )


def list_drafts(db: Session, project_id: str) -> list[DraftRead]:
    rows = (
        db.execute(
            select(Draft)
            .where(Draft.project_id == project_id)
            .order_by(Draft.version.desc())
        )
        .scalars()
        .all()
    )
    return [
        DraftRead(
            id=row.id,
            project_id=row.project_id,
            version=row.version,
            section=row.section,
            content=row.content,
            claims=row.claims or [],
            created_at=row.created_at,
        )
        for row in rows
    ]


def get_draft(db: Session, project_id: str, version: int) -> DraftRead | None:
    row = (
        db.execute(select(Draft).where(Draft.project_id == project_id, Draft.version == version))
        .scalars()
        .first()
    )
    if row is None:
        return None
    return DraftRead(
        id=row.id,
        project_id=row.project_id,
        version=row.version,
        section=row.section,
        content=row.content,
        claims=row.claims or [],
        created_at=row.created_at,
    )


def update_draft(
    db: Session, project_id: str, version: int, payload: DraftCreate
) -> DraftRead | None:
    row = (
        db.execute(select(Draft).where(Draft.project_id == project_id, Draft.version == version))
        .scalars()
        .first()
    )
    if row is None:
        return None
    row.content = payload.content
    row.section = payload.section
    db.commit()
    return DraftRead(
        id=row.id,
        project_id=row.project_id,
        version=row.version,
        section=row.section,
        content=row.content,
        claims=row.claims or [],
        created_at=row.created_at,
    )
