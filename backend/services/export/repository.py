from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.export_file import ExportFile
from schemas.export import ExportResult
from services.projects.repository import touch_project


def create_export(db: Session, project_id: str, fmt: str) -> str:
    row = ExportFile(
        id=f"exp_{uuid4().hex}",
        project_id=project_id,
        format=fmt,
        status="running",
    )
    db.add(row)
    touch_project(db, project_id)
    db.commit()
    return row.id


def set_export_status(db: Session, export_id: str, status: str, file_path: str | None) -> None:
    row = db.execute(select(ExportFile).where(ExportFile.id == export_id)).scalar_one_or_none()
    if row is None:
        return
    row.status = status
    row.file_path = file_path
    touch_project(db, row.project_id)
    db.commit()


def get_export(db: Session, export_id: str) -> ExportResult | None:
    row = db.execute(select(ExportFile).where(ExportFile.id == export_id)).scalar_one_or_none()
    if row is None:
        return None
    return ExportResult(file_id=row.id, status=row.status, created_at=row.created_at)
