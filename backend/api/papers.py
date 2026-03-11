from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.fetcher_agent import FetcherAgent
from agents.reader_agent import ReaderAgent
from config.deps import get_db
from config.db import SessionLocal
from schemas.agents import FetchItem, FetchResult, ReadResult
from schemas.common import IdResponse, TaskStatusResponse
from schemas.papers import PaperCreate, PaperMeta, PaperSummary
from services.papers.repository import (
    add_paper,
    get_paper_summary,
    list_papers,
    update_paper_paths,
)
from services.tasks import task_store

router = APIRouter(prefix="/api/projects/{project_id}/papers", tags=["papers"])


def _run_fetch_read_task(task_id: str, project_id: str, paper_id: str) -> None:
    db = SessionLocal()
    try:
        task_store.set(task_id, "running")
        items = list_papers(db, project_id)
        target = next((p for p in items if p.id == paper_id), None)
        if target is None:
            task_store.set(task_id, "failed", "Paper not found")
            return
        if not target.pdf_url:
            task_store.set(task_id, "failed", "No pdf_url")
            return

        fetcher = FetcherAgent()
        fetch_payload = {
            "project_id": project_id,
            "items": [FetchItem(paper_id=paper_id, pdf_url=target.pdf_url).model_dump()],
        }
        fetch_result = fetcher.run(fetch_payload)
        fr = FetchResult(**(fetch_result.get("items") or [{}])[0])
        if fr.status != "ok" or not fr.grobid_xml_path:
            task_store.set(task_id, "failed", f"Fetch/parse failed: {fr.status}")
            return

        update_paper_paths(db, paper_id, target.pdf_url, fr.grobid_xml_path)

        reader = ReaderAgent()
        reader.run({"paper_id": paper_id, "grobid_xml_path": fr.grobid_xml_path})
        task_store.set(task_id, "done")
    except Exception as exc:
        task_store.set(task_id, "failed", str(exc))
    finally:
        db.close()


@router.post("", response_model=IdResponse)
def add_paper_endpoint(
    project_id: str,
    payload: PaperCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> IdResponse:
    paper_id = add_paper(db, project_id, payload)
    if payload.auto_fetch:
        task_id = task_store.create()
        background_tasks.add_task(_run_fetch_read_task, task_id, project_id, paper_id)
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
    fetch_payload = {
        "project_id": project_id,
        "items": [FetchItem(paper_id=paper_id, pdf_url=target.pdf_url).model_dump()],
    }
    fetch_result = fetcher.run(fetch_payload)
    fr = FetchResult(**(fetch_result.get("items") or [{}])[0])
    if fr.status != "ok" or not fr.grobid_xml_path:
        raise HTTPException(status_code=400, detail=f"Fetch/parse failed: {fr.status}")

    update_paper_paths(db, paper_id, target.pdf_url, fr.grobid_xml_path)

    reader = ReaderAgent()
    read_payload = {"paper_id": paper_id, "grobid_xml_path": fr.grobid_xml_path}
    return ReadResult(**reader.run(read_payload))


@router.post("/{paper_id}/fetch_read_async", response_model=IdResponse)
def fetch_and_read_async(
    project_id: str, paper_id: str, background_tasks: BackgroundTasks
) -> IdResponse:
    task_id = task_store.create()
    background_tasks.add_task(_run_fetch_read_task, task_id, project_id, paper_id)
    return IdResponse(id=task_id)


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    status = task_store.get(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(status=status.status, detail=status.detail)
