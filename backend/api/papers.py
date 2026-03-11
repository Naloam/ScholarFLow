from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.common import IdResponse
from schemas.papers import PaperCreate, PaperMeta, PaperSummary
from config.deps import get_db
from services.papers.repository import add_paper, get_paper_summary, list_papers

router = APIRouter(prefix="/api/projects/{project_id}/papers", tags=["papers"])


@router.post("", response_model=IdResponse)
def add_paper_endpoint(
    project_id: str, payload: PaperCreate, db: Session = Depends(get_db)
) -> IdResponse:
    paper_id = add_paper(db, project_id, payload)
    return IdResponse(id=paper_id)


@router.get("", response_model=list[PaperMeta])
def list_papers_endpoint(project_id: str, db: Session = Depends(get_db)) -> list[PaperMeta]:
    return list_papers(db, project_id)


@router.get("/{paper_id}/summary", response_model=PaperSummary)
def get_paper_summary_endpoint(
    project_id: str, paper_id: str, db: Session = Depends(get_db)
) -> PaperSummary:
    summary = get_paper_summary(db, project_id, paper_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return summary
