from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.draft import Draft
from models.evidence import Evidence
from models.export_file import ExportFile
from models.project import Project
from models.review_report import ReviewReport
from services.projects.status import get_status_info, normalize_status


def _count_for_project(db: Session, model: type, project_id: str) -> int:
    stmt = select(func.count()).select_from(model).where(model.project_id == project_id)
    return int(db.execute(stmt).scalar_one())


def _review_status(latest_review: ReviewReport | None) -> str | None:
    if latest_review is None:
        return None
    return "ready" if latest_review.scores else "pending"


def build_progress_snapshot(db: Session, project_id: str) -> dict | None:
    project = db.get(Project, project_id)
    if project is None:
        return None

    status = normalize_status(project.status)
    info = get_status_info(status)

    latest_draft = (
        db.execute(
            select(Draft)
            .where(Draft.project_id == project_id)
            .order_by(Draft.version.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    latest_review = (
        db.execute(
            select(ReviewReport)
            .where(ReviewReport.project_id == project_id)
            .order_by(ReviewReport.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    latest_export = (
        db.execute(
            select(ExportFile)
            .where(ExportFile.project_id == project_id)
            .order_by(ExportFile.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )

    updated_at = project.updated_at or project.created_at or datetime.now(UTC).replace(tzinfo=None)
    draft_count = _count_for_project(db, Draft, project_id)
    evidence_count = _count_for_project(db, Evidence, project_id)
    review_count = _count_for_project(db, ReviewReport, project_id)
    export_count = _count_for_project(db, ExportFile, project_id)
    latest_review_status = _review_status(latest_review)
    signature = ":".join(
        [
            project_id,
            status,
            str(draft_count),
            str(latest_draft.version if latest_draft else 0),
            latest_draft.created_at.isoformat() if latest_draft and latest_draft.created_at else "",
            str(evidence_count),
            str(review_count),
            str(latest_review.id if latest_review else ""),
            latest_review_status or "",
            latest_review.created_at.isoformat()
            if latest_review and latest_review.created_at
            else "",
            str(export_count),
            str(latest_export.id if latest_export else ""),
            latest_export.status if latest_export else "",
            updated_at.isoformat(),
        ]
    )

    return {
        "project_id": project_id,
        "status": status,
        "phase": info.phase,
        "progress": info.progress,
        "draft_count": draft_count,
        "latest_draft_version": latest_draft.version if latest_draft else None,
        "latest_draft_created_at": (
            latest_draft.created_at.isoformat() if latest_draft and latest_draft.created_at else None
        ),
        "evidence_count": evidence_count,
        "review_count": review_count,
        "latest_review_id": latest_review.id if latest_review else None,
        "latest_review_status": latest_review_status,
        "latest_review_created_at": (
            latest_review.created_at.isoformat()
            if latest_review and latest_review.created_at
            else None
        ),
        "export_count": export_count,
        "latest_export_id": latest_export.id if latest_export else None,
        "latest_export_status": latest_export.status if latest_export else None,
        "updated_at": updated_at.isoformat(),
        "signature": signature,
    }
