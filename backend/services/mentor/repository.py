from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.mentor_feedback import MentorFeedback
from models.project_mentor_access import ProjectMentorAccess
from models.user import User
from schemas.mentor import (
    MentorAccessRead,
    MentorFeedbackCreate,
    MentorFeedbackRead,
)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _to_mentor_access_read(row: ProjectMentorAccess, mentor_name: str | None = None) -> MentorAccessRead:
    return MentorAccessRead(
        id=row.id,
        project_id=row.project_id,
        mentor_user_id=row.mentor_user_id,
        mentor_email=row.mentor_email,
        mentor_name=mentor_name,
        invited_by_user_id=row.invited_by_user_id,
        status=row.status,
        created_at=row.created_at,
    )


def grant_mentor_access(
    db: Session,
    *,
    project_id: str,
    mentor_user_id: str,
    mentor_email: str,
    mentor_name: str | None,
    invited_by_user_id: str,
) -> MentorAccessRead:
    normalized_email = _normalize_email(mentor_email)
    row = db.execute(
        select(ProjectMentorAccess).where(
            ProjectMentorAccess.project_id == project_id,
            ProjectMentorAccess.mentor_email == normalized_email,
        )
    ).scalar_one_or_none()
    if row is None:
        row = ProjectMentorAccess(
            id=f"mentor_{uuid4().hex}",
            project_id=project_id,
            mentor_user_id=mentor_user_id,
            mentor_email=normalized_email,
            invited_by_user_id=invited_by_user_id,
            status="active",
        )
        db.add(row)
    else:
        row.mentor_user_id = mentor_user_id
        row.status = "active"
        db.add(row)
    db.commit()
    db.refresh(row)
    return _to_mentor_access_read(row, mentor_name=mentor_name)


def list_mentor_access(db: Session, project_id: str) -> list[MentorAccessRead]:
    rows = list(
        db.execute(
            select(ProjectMentorAccess, User.name)
            .outerjoin(User, User.id == ProjectMentorAccess.mentor_user_id)
            .where(ProjectMentorAccess.project_id == project_id)
            .order_by(ProjectMentorAccess.created_at.asc())
        )
    )
    return [
        _to_mentor_access_read(access_row, mentor_name=mentor_name)
        for access_row, mentor_name in rows
    ]


def has_mentor_access(
    db: Session,
    *,
    project_id: str,
    user_id: str | None,
    email: str | None,
) -> bool:
    normalized_email = _normalize_email(email) if email else None
    rows = list(
        db.execute(
            select(ProjectMentorAccess).where(
                ProjectMentorAccess.project_id == project_id,
                ProjectMentorAccess.status == "active",
            )
        ).scalars()
    )
    for row in rows:
        if user_id and row.mentor_user_id == user_id:
            return True
        if normalized_email and row.mentor_email == normalized_email:
            return True
    return False


def create_mentor_feedback(
    db: Session,
    *,
    project_id: str,
    mentor_user_id: str,
    mentor_email: str,
    mentor_name: str | None,
    payload: MentorFeedbackCreate,
) -> MentorFeedbackRead:
    row = MentorFeedback(
        id=f"mentor_feedback_{uuid4().hex}",
        project_id=project_id,
        mentor_user_id=mentor_user_id,
        draft_version=payload.draft_version,
        summary=payload.summary.strip(),
        strengths=payload.strengths.strip(),
        concerns=payload.concerns.strip(),
        next_steps=payload.next_steps.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return MentorFeedbackRead(
        id=row.id,
        project_id=row.project_id,
        mentor_user_id=row.mentor_user_id,
        mentor_email=mentor_email,
        mentor_name=mentor_name,
        draft_version=row.draft_version,
        summary=row.summary,
        strengths=row.strengths,
        concerns=row.concerns,
        next_steps=row.next_steps,
        created_at=row.created_at,
    )


def list_mentor_feedback(db: Session, project_id: str) -> list[MentorFeedbackRead]:
    rows = list(
        db.execute(
            select(MentorFeedback, User.email, User.name)
            .join(User, User.id == MentorFeedback.mentor_user_id)
            .where(MentorFeedback.project_id == project_id)
            .order_by(MentorFeedback.created_at.desc())
        )
    )
    return [
        MentorFeedbackRead(
            id=row.id,
            project_id=row.project_id,
            mentor_user_id=row.mentor_user_id,
            mentor_email=mentor_email,
            mentor_name=mentor_name,
            draft_version=row.draft_version,
            summary=row.summary,
            strengths=row.strengths,
            concerns=row.concerns,
            next_steps=row.next_steps,
            created_at=row.created_at,
        )
        for row, mentor_email, mentor_name in rows
    ]
