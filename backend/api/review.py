from fastapi import APIRouter

from schemas.common import IdResponse
from schemas.review import ReviewReport, ReviewRequest, ReviewScore

router = APIRouter(prefix="/api/projects/{project_id}/review", tags=["review"])


@router.post("", response_model=IdResponse)
def run_review(project_id: str, payload: ReviewRequest) -> IdResponse:
    return IdResponse(id="review_todo")


@router.get("/{review_id}", response_model=ReviewReport)
def get_review(project_id: str, review_id: str) -> ReviewReport:
    scores = ReviewScore(
        originality=0,
        importance=0,
        evidence_support=0,
        soundness=0,
        clarity=0,
        value=0,
        contextualization=0,
    )
    return ReviewReport(id=review_id, project_id=project_id, scores=scores, suggestions=[])
