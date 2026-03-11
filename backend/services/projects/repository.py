from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from models.project import Project
from schemas.projects import ProjectCreate, ProjectRead, ProjectUpdate
from services.projects.status import validate_status


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


def get_project(db: Session, project_id: str) -> ProjectRead | None:
    row = db.get(Project, project_id)
    if row is None:
        return None
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


def update_project(db: Session, project_id: str, payload: ProjectUpdate) -> ProjectRead | None:
    row = db.get(Project, project_id)
    if row is None:
        return None
    if payload.title is not None:
        row.title = payload.title
    if payload.topic is not None:
        row.topic = payload.topic
    if payload.template_id is not None:
        row.template_id = payload.template_id
    if payload.status is not None:
        row.status = validate_status(payload.status)
    db.add(row)
    db.commit()
    db.refresh(row)
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
