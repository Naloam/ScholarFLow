from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.review_report import ReviewReport as ReviewReportModel
from schemas.review import ReviewReport, ReviewScore
from services.projects.repository import touch_project


def create_review_placeholder(db: Session, project_id: str, draft_version: int) -> str:
    row = ReviewReportModel(
        id=f"rev_{uuid4().hex}",
        project_id=project_id,
        draft_version=draft_version,
        scores={},
        suggestions=[],
    )
    db.add(row)
    touch_project(db, project_id)
    db.commit()
    return row.id


def update_review(
    db: Session,
    review_id: str,
    scores: ReviewScore,
    suggestions: list[str],
) -> ReviewReport | None:
    row = db.execute(select(ReviewReportModel).where(ReviewReportModel.id == review_id)).scalar_one_or_none()
    if row is None:
        return None
    row.scores = scores.model_dump()
    row.suggestions = suggestions
    touch_project(db, row.project_id)
    db.commit()
    return ReviewReport(
        id=row.id,
        project_id=row.project_id,
        draft_version=row.draft_version,
        scores=scores,
        suggestions=suggestions,
        created_at=row.created_at,
    )


def get_review(db: Session, project_id: str, review_id: str) -> ReviewReport | None:
    row = db.execute(
        select(ReviewReportModel).where(
            ReviewReportModel.project_id == project_id,
            ReviewReportModel.id == review_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    scores = row.scores or {}
    if not scores:
        scores = {
            "originality": 0,
            "importance": 0,
            "evidence_support": 0,
            "soundness": 0,
            "clarity": 0,
            "value": 0,
            "contextualization": 0,
        }
    return ReviewReport(
        id=row.id,
        project_id=row.project_id,
        draft_version=row.draft_version,
        scores=ReviewScore(**scores),
        suggestions=row.suggestions,
        created_at=row.created_at,
    )


def list_reviews(db: Session, project_id: str) -> list[ReviewReport]:
    rows = (
        db.execute(
            select(ReviewReportModel)
            .where(ReviewReportModel.project_id == project_id)
            .order_by(ReviewReportModel.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        ReviewReport(
            id=row.id,
            project_id=row.project_id,
            draft_version=row.draft_version,
            scores=ReviewScore(
                **(
                    row.scores
                    or {
                        "originality": 0,
                        "importance": 0,
                        "evidence_support": 0,
                        "soundness": 0,
                        "clarity": 0,
                        "value": 0,
                        "contextualization": 0,
                    }
                )
            ),
            suggestions=row.suggestions,
            created_at=row.created_at,
        )
        for row in rows
    ]
