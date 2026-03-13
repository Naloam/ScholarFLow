from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.review_agent import ReviewAgent
from config.deps import get_db
from config.db import SessionLocal
from schemas.common import IdResponse
from schemas.review import ReviewReport, ReviewRequest, ReviewScore
from services.drafts.repository import get_draft, get_latest_draft
from services.review.repository import (
    create_review_placeholder,
    get_review,
    list_reviews,
    update_review,
)
from services.evidence.repository import list_evidence_items
from services.projects.repository import get_project

router = APIRouter(prefix="/api/projects/{project_id}/review", tags=["review"])


@router.post("", response_model=IdResponse)
def run_review(
    project_id: str,
    payload: ReviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> IdResponse:
    draft = get_draft(db, project_id, payload.draft_version)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    review_id = create_review_placeholder(db, project_id, payload.draft_version)

    def _run_review_task() -> None:
        local = SessionLocal()
        try:
            draft_local = get_draft(local, project_id, payload.draft_version)
            if draft_local is None:
                return
            evidence = list_evidence_items(local, project_id)
            references = [e.paper_id for e in evidence]
            agent = ReviewAgent()
            result = agent.run({"draft": draft_local.content, "references": references})
            scores = result.get("scores", {})
            suggestions = result.get("suggestions", [])
            update_review(local, review_id, ReviewScore(**scores), suggestions)
        finally:
            local.close()

    background_tasks.add_task(_run_review_task)
    return IdResponse(id=review_id or "")


@router.get("/{review_id}", response_model=ReviewReport)
@router.get("", response_model=list[ReviewReport])
def list_review_reports(project_id: str, db: Session = Depends(get_db)) -> list[ReviewReport]:
    return list_reviews(db, project_id)


@router.get("/{review_id}", response_model=ReviewReport)
def get_review_report(project_id: str, review_id: str, db: Session = Depends(get_db)) -> ReviewReport:
    report = get_review(db, review_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return report


@router.get("/{review_id}/followups", response_model=list[str])
def get_followups(project_id: str, review_id: str, db: Session = Depends(get_db)) -> list[str]:
    report = get_review(db, review_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Review not found")
    project = get_project(db, project_id)
    topic = project.topic if project else ""
    followups = []
    for s in report.suggestions:
        if "证据" in s or "引用" in s:
            followups.append(f"{topic} supporting evidence literature")
        if "相关工作" in s or "上下文化" in s:
            followups.append(f"{topic} related work survey")
    return followups or [f"{topic} recent papers"] if topic else []
