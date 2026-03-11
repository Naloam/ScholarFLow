from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.common import IdResponse
from agents.fetcher_agent import FetcherAgent
from agents.reader_agent import ReaderAgent
from schemas.agents import FetchItem, FetchResult, ReadResult
from schemas.papers import PaperCreate, PaperMeta, PaperSummary
from config.deps import get_db
from services.papers.repository import (
    add_paper,
    get_paper_summary,
    list_papers,
    update_paper_paths,
)

router = APIRouter(prefix="/api/projects/{project_id}/papers", tags=["papers"])


@router.post("", response_model=IdResponse)
def add_paper_endpoint(
    project_id: str, payload: PaperCreate, db: Session = Depends(get_db)
) -> IdResponse:
    paper_id = add_paper(db, project_id, payload)
    if payload.auto_fetch:
        items = list_papers(db, project_id)
        target = next((p for p in items if p.id == paper_id), None)
        if target and target.pdf_url:
            fetcher = FetcherAgent()
            fetch_payload = {\n                \"project_id\": project_id,\n                \"items\": [FetchItem(paper_id=paper_id, pdf_url=target.pdf_url).model_dump()],\n            }\n            fetch_result = fetcher.run(fetch_payload)\n            fr = FetchResult(**(fetch_result.get(\"items\") or [{}])[0])\n            if fr.status == \"ok\" and fr.grobid_xml_path:\n                update_paper_paths(db, paper_id, target.pdf_url, fr.grobid_xml_path)\n     return IdResponse(id=paper_id)
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


@router.post("/{paper_id}/fetch_read", response_model=ReadResult)
def fetch_and_read(
    project_id: str, paper_id: str, db: Session = Depends(get_db)
) -> ReadResult:
    items = list_papers(db, project_id)
    target = next((p for p in items if p.id == paper_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    fetcher = FetcherAgent()
    fetch_payload = {\n        \"project_id\": project_id,\n        \"items\": [FetchItem(paper_id=paper_id, pdf_url=target.pdf_url).model_dump()],\n    }\n    fetch_result = fetcher.run(fetch_payload)\n    fr = FetchResult(**(fetch_result.get(\"items\") or [{}])[0])\n    if fr.status != \"ok\" or not fr.grobid_xml_path:\n        raise HTTPException(status_code=400, detail=f\"Fetch/parse failed: {fr.status}\")\n\n    update_paper_paths(db, paper_id, target.pdf_url, fr.grobid_xml_path)\n\n    reader = ReaderAgent()\n    read_payload = {\n        \"paper_id\": paper_id,\n        \"grobid_xml_path\": fr.grobid_xml_path,\n    }\n    return ReadResult(**reader.run(read_payload))
