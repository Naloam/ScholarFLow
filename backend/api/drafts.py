from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.writing_agent import WritingAgent
from config.deps import get_db
from schemas.common import IdResponse
from schemas.drafts import DraftCreate, DraftGenerateRequest, DraftRead
from services.drafts.repository import create_draft, get_draft, list_drafts, update_draft
from services.papers.repository import list_papers
from services.templates.repository import get_template_content

router = APIRouter(prefix="/api/projects/{project_id}/drafts", tags=["drafts"])


@router.post("/generate", response_model=IdResponse)
def generate_draft(
    project_id: str, payload: DraftGenerateRequest, db: Session = Depends(get_db)
) -> IdResponse:
    papers = list_papers(db, project_id)
    if payload.paper_ids:
        papers = [p for p in papers if p.id in payload.paper_ids]
    template = get_template_content(db, payload.template_id)
    agent = WritingAgent()
    result = agent.run(
        {
            "topic": payload.topic or "Untitled Topic",
            "scope": payload.scope or "",
            "papers": [p.model_dump() for p in papers],
            "template": template or "",
        }
    )
    draft = create_draft(db, project_id, result.get("content", ""), result.get("claims"))
    return IdResponse(id=draft.id or "")


@router.get("", response_model=list[DraftRead])
def list_drafts_endpoint(project_id: str, db: Session = Depends(get_db)) -> list[DraftRead]:
    return list_drafts(db, project_id)


@router.get("/{version}", response_model=DraftRead)
def get_draft_endpoint(
    project_id: str, version: int, db: Session = Depends(get_db)
) -> DraftRead:
    draft = get_draft(db, project_id, version)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.put("/{version}", response_model=DraftRead)
def update_draft_endpoint(
    project_id: str, version: int, payload: DraftCreate, db: Session = Depends(get_db)
) -> DraftRead:
    draft = update_draft(db, project_id, version, payload)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft
