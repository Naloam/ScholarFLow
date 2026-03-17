from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.deps import get_db, get_identity, require_project_access
from schemas.beta import BetaSummary, FeedbackCreate, FeedbackRead
from services.beta.summary import build_beta_summary
from services.feedback.repository import create_feedback, list_feedback
from services.security.auth import AuthIdentity

router = APIRouter(
    prefix="/api/projects/{project_id}/beta",
    tags=["beta"],
    dependencies=[Depends(require_project_access)],
)


@router.get("/summary", response_model=BetaSummary)
def get_beta_summary(project_id: str, db: Session = Depends(get_db)) -> BetaSummary:
    return build_beta_summary(db, project_id)


@router.get("/feedback", response_model=list[FeedbackRead])
def get_feedback(project_id: str, db: Session = Depends(get_db)) -> list[FeedbackRead]:
    return list_feedback(db, project_id)


@router.post("/feedback", response_model=FeedbackRead)
def create_feedback_entry(
    project_id: str,
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> FeedbackRead:
    return create_feedback(
        db,
        project_id,
        payload,
        user_id=identity.user_id if identity else None,
    )
