from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config.deps import (
    get_db,
    require_project_access,
    require_project_mentor,
    require_project_owner,
)
from schemas.mentor import (
    MentorAccessCreate,
    MentorAccessRead,
    MentorFeedbackCreate,
    MentorFeedbackRead,
)
from services.mentor.repository import (
    create_mentor_feedback,
    grant_mentor_access,
    list_mentor_access,
    list_mentor_feedback,
)
from services.security.auth import AuthIdentity
from services.users.repository import get_or_create_user_by_email, get_user_by_id

router = APIRouter(prefix="/api/projects/{project_id}/mentor", tags=["mentor"])


@router.get("/access", response_model=list[MentorAccessRead], dependencies=[Depends(require_project_access)])
def list_project_mentor_access(
    project_id: str,
    db: Session = Depends(get_db),
) -> list[MentorAccessRead]:
    return list_mentor_access(db, project_id)


@router.post("/access", response_model=MentorAccessRead)
def create_project_mentor_access(
    project_id: str,
    payload: MentorAccessCreate,
    db: Session = Depends(get_db),
    identity: AuthIdentity = Depends(require_project_owner),
) -> MentorAccessRead:
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid mentor email")
    if payload.email.strip().lower() == (identity.email or "").strip().lower():
        raise HTTPException(status_code=400, detail="Project owner cannot invite the same email as mentor")
    mentor_user = get_or_create_user_by_email(
        db,
        payload.email,
        payload.name,
        role="tutor",
    )
    return grant_mentor_access(
        db,
        project_id=project_id,
        mentor_user_id=mentor_user.id,
        mentor_email=mentor_user.email,
        mentor_name=mentor_user.name,
        invited_by_user_id=identity.user_id or "",
    )


@router.get("/feedback", response_model=list[MentorFeedbackRead], dependencies=[Depends(require_project_access)])
def list_project_mentor_feedback(
    project_id: str,
    db: Session = Depends(get_db),
) -> list[MentorFeedbackRead]:
    return list_mentor_feedback(db, project_id)


@router.post("/feedback", response_model=MentorFeedbackRead)
def create_project_mentor_feedback(
    project_id: str,
    payload: MentorFeedbackCreate,
    db: Session = Depends(get_db),
    identity: AuthIdentity = Depends(require_project_mentor),
) -> MentorFeedbackRead:
    user = get_user_by_id(db, identity.user_id or "")
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid session")
    return create_mentor_feedback(
        db,
        project_id=project_id,
        mentor_user_id=user.id,
        mentor_email=user.email,
        mentor_name=user.name,
        payload=payload,
    )
