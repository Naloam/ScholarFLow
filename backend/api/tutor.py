from fastapi import APIRouter

from agents.tutor_agent import TutorAgent
from schemas.tutor import TutorRequest, TutorResponse

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


@router.post("", response_model=TutorResponse)
def get_guidance(payload: TutorRequest) -> TutorResponse:
    agent = TutorAgent()
    result = agent.run(payload.model_dump())
    return TutorResponse(stage=result.get("stage", payload.stage or "outline"), guidance=result.get("guidance", ""))
