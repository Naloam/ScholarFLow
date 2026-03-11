from fastapi import APIRouter

from schemas.common import IdResponse
from schemas.drafts import DraftCreate, DraftGenerateRequest, DraftRead

router = APIRouter(prefix="/api/projects/{project_id}/drafts", tags=["drafts"])


@router.post("/generate", response_model=IdResponse)
def generate_draft(project_id: str, payload: DraftGenerateRequest) -> IdResponse:
    return IdResponse(id="draft_todo")


@router.get("", response_model=list[DraftRead])
def list_drafts(project_id: str) -> list[DraftRead]:
    return []


@router.get("/{version}", response_model=DraftRead)
def get_draft(project_id: str, version: int) -> DraftRead:
    return DraftRead(version=version, content="")


@router.put("/{version}", response_model=DraftRead)
def update_draft(project_id: str, version: int, payload: DraftCreate) -> DraftRead:
    return DraftRead(version=version, content=payload.content)
