from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user import User
from schemas.auth import UserRead


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> UserRead | None:
    normalized = _normalize_email(email)
    row = db.execute(select(User).where(User.email == normalized)).scalar_one_or_none()
    if row is None:
        return None
    return UserRead(
        id=row.id,
        email=row.email,
        name=row.name,
        role=row.role,
        created_at=row.created_at,
    )


def get_user_by_id(db: Session, user_id: str) -> UserRead | None:
    row = db.get(User, user_id)
    if row is None:
        return None
    return UserRead(
        id=row.id,
        email=row.email,
        name=row.name,
        role=row.role,
        created_at=row.created_at,
    )


def get_or_create_user_by_email(db: Session, email: str, name: str | None = None) -> UserRead:
    normalized = _normalize_email(email)
    existing = db.execute(select(User).where(User.email == normalized)).scalar_one_or_none()
    if existing is not None:
        if name and not existing.name:
            existing.name = name
            db.add(existing)
            db.commit()
            db.refresh(existing)
        return UserRead(
            id=existing.id,
            email=existing.email,
            name=existing.name,
            role=existing.role,
            created_at=existing.created_at,
        )

    row = User(
        id=f"user_{uuid4().hex}",
        email=normalized,
        name=name,
        role="student",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserRead(
        id=row.id,
        email=row.email,
        name=row.name,
        role=row.role,
        created_at=row.created_at,
    )
