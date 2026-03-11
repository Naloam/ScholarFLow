from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.draft import Draft


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
