from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models.project import Project
from models.project_mentor_access import ProjectMentorAccess
from schemas.projects import ProjectCreate, ProjectListItem, ProjectRead, ProjectUpdate
from services.projects.status import validate_status


def _to_project_read(row: Project) -> ProjectRead:
    return ProjectRead(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        topic=row.topic,
        template_id=row.template_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_project_list_item(row: Project, access_mode: str) -> ProjectListItem:
    return ProjectListItem(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        topic=row.topic,
        template_id=row.template_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        access_mode=access_mode,
    )


def touch_project(db: Session, project_id: str) -> None:
    row = db.get(Project, project_id)
    if row is None:
        return
    row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(row)


def create_project(db: Session, payload: ProjectCreate) -> ProjectRead:
    status = validate_status(payload.status)
    row = Project(
        id=str(uuid4()),
        user_id=payload.user_id,
        title=payload.title,
        topic=payload.topic,
        template_id=payload.template_id,
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_project_read(row)


def get_project(db: Session, project_id: str) -> ProjectRead | None:
    row = db.get(Project, project_id)
    if row is None:
        return None
    return _to_project_read(row)


def list_projects_for_user(
    db: Session,
    *,
    user_id: str,
    email: str | None,
) -> list[ProjectListItem]:
    entries_by_id: dict[str, ProjectListItem] = {}
    owned_rows = list(
        db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.updated_at.desc(), Project.created_at.desc())
        ).scalars()
    )
    for row in owned_rows:
        entries_by_id[row.id] = _to_project_list_item(row, "owner")

    mentor_filters = [ProjectMentorAccess.mentor_user_id == user_id]
    normalized_email = email.strip().lower() if email else None
    if normalized_email:
        mentor_filters.append(ProjectMentorAccess.mentor_email == normalized_email)

    mentor_rows = list(
        db.execute(
            select(Project)
            .join(ProjectMentorAccess, ProjectMentorAccess.project_id == Project.id)
            .where(
                ProjectMentorAccess.status == "active",
                or_(*mentor_filters),
            )
            .order_by(Project.updated_at.desc(), Project.created_at.desc())
        ).scalars()
    )
    for row in mentor_rows:
        if row.id not in entries_by_id:
            entries_by_id[row.id] = _to_project_list_item(row, "mentor")

    return sorted(
        entries_by_id.values(),
        key=lambda entry: entry.updated_at or entry.created_at or datetime.min,
        reverse=True,
    )


def get_project_owner_id(db: Session, project_id: str) -> str | None:
    row = db.get(Project, project_id)
    if row is None:
        return None
    return row.user_id


def update_project(db: Session, project_id: str, payload: ProjectUpdate) -> ProjectRead | None:
    row = db.get(Project, project_id)
    if row is None:
        return None
    touched = False
    if payload.title is not None:
        row.title = payload.title
        touched = True
    if payload.topic is not None:
        row.topic = payload.topic
        touched = True
    if payload.template_id is not None:
        row.template_id = payload.template_id
        touched = True
    if payload.status is not None:
        row.status = validate_status(payload.status)
        touched = True
    if touched:
        row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_project_read(row)


def set_project_status(db: Session, project_id: str, status: str) -> None:
    row = db.get(Project, project_id)
    if row is None:
        return
    row.status = validate_status(status)
    row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(row)
    db.commit()
