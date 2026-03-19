from __future__ import annotations

from pathlib import Path
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


def _to_export_result(row: ExportFile) -> ExportResult:
    file_name = Path(row.file_path).name if row.file_path else None
    return ExportResult(
        file_id=row.id,
        format=row.format,
        status=row.status,
        file_name=file_name,
        download_ready=bool(row.file_path and row.status == "done"),
        created_at=row.created_at,
    )


def get_export_row(db: Session, project_id: str, export_id: str) -> ExportFile | None:
    return db.execute(
        select(ExportFile).where(
            ExportFile.project_id == project_id,
            ExportFile.id == export_id,
        )
    ).scalar_one_or_none()


def get_export(db: Session, project_id: str, export_id: str) -> ExportResult | None:
    row = get_export_row(db, project_id, export_id)
    if row is None:
        return None
    return _to_export_result(row)
