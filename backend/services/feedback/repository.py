from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.feedback_entry import FeedbackEntry
from schemas.beta import FeedbackCreate, FeedbackRead


def create_feedback(
    db: Session,
    project_id: str,
    payload: FeedbackCreate,
    user_id: str | None = None,
) -> FeedbackRead:
    row = FeedbackEntry(
        id=f"feedback_{uuid4().hex}",
        project_id=project_id,
        user_id=user_id,
        rating=payload.rating,
        category=payload.category.strip().lower(),
        comment=payload.comment.strip(),
        status="new",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return FeedbackRead(
        id=row.id,
        project_id=row.project_id,
        user_id=row.user_id,
        rating=row.rating,
        category=row.category,
        comment=row.comment,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_feedback(db: Session, project_id: str) -> list[FeedbackRead]:
    rows = list(
        db.execute(
            select(FeedbackEntry)
            .where(FeedbackEntry.project_id == project_id)
            .order_by(FeedbackEntry.created_at.desc())
        ).scalars()
    )
    return [
        FeedbackRead(
            id=row.id,
            project_id=row.project_id,
            user_id=row.user_id,
            rating=row.rating,
            category=row.category,
            comment=row.comment,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
