from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agents.tutor_agent import TutorAgent
from schemas.tutor import TutorRequest, TutorResponse
from config.deps import get_db
from services.drafts.repository import get_draft, get_latest_draft
from services.drafts.analysis import infer_stage, needs_evidence_count

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


@router.post("", response_model=TutorResponse)
def get_guidance(payload: TutorRequest, db: Session = Depends(get_db)) -> TutorResponse:
    stage = payload.stage
    context = payload.context or ""
    if payload.project_id:
        draft = (
            get_draft(db, payload.project_id, payload.draft_version)
            if payload.draft_version
            else get_latest_draft(db, payload.project_id)
        )
        if draft:
            stage = stage or infer_stage(draft.content)
            context = (
                context
                + f"\nDraft version: {draft.version}\n"
                + f"Needs evidence count: {needs_evidence_count(draft.content)}"
            ).strip()
    agent = TutorAgent()
    result = agent.run(
        {
            "stage": stage,
            "topic": payload.topic,
            "context": context,
        }
    )
    return TutorResponse(stage=result.get("stage", stage or "outline"), guidance=result.get("guidance", ""))
