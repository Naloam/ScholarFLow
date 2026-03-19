from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.fetcher_agent import FetcherAgent
from agents.reader_agent import ReaderAgent
from config.deps import get_db, get_identity, require_project_access
from config.db import SessionLocal
from schemas.agents import FetchItem, FetchResult, ReadResult
from schemas.common import IdResponse
from schemas.papers import PaperCreate, PaperMeta, PaperSummary
from services.embedding.embeddings import embed_texts
from services.embedding.vector_index import add_vectors
from services.papers.repository import (
    add_paper,
    get_paper_summary,
    list_papers,
    update_paper_paths,
)
from services.projects.repository import set_project_status
from services.reader.repository import save_chunks, update_embeddings
from services.security.audit import write_task_audit_log
from services.security.auth import AuthIdentity
from services.telemetry.context import telemetry_context
from services.tasks import create_task, set_task

router = APIRouter(
    prefix="/api/projects/{project_id}/papers",
    tags=["papers"],
    dependencies=[Depends(require_project_access)],
)


def _run_fetch_read_task(task_id: str, project_id: str, paper_id: str, user_id: str | None) -> None:
    write_task_audit_log(
        SessionLocal,
        correlation_id=task_id,
        task_name="papers.fetch_read",
        project_id=project_id,
        action="running",
        status_code=102,
        user_id=user_id,
        detail=f"paper_id={paper_id}",
    )
    db = SessionLocal()
    try:
        set_project_status(db, project_id, "fetch")
        set_task(db, task_id, "running")
        items = list_papers(db, project_id)
        target = next((p for p in items if p.id == paper_id), None)
        if target is None:
            set_task(db, task_id, "failed", "Paper not found")
            write_task_audit_log(
                SessionLocal,
                correlation_id=task_id,
                task_name="papers.fetch_read",
                project_id=project_id,
                action="failed",
                status_code=404,
                user_id=user_id,
                detail=f"paper_not_found:{paper_id}",
            )
            return
        if not target.pdf_url:
            set_task(db, task_id, "failed", "No pdf_url")
            write_task_audit_log(
                SessionLocal,
                correlation_id=task_id,
                task_name="papers.fetch_read",
                project_id=project_id,
                action="failed",
                status_code=400,
                user_id=user_id,
                detail=f"missing_pdf_url:{paper_id}",
            )
            return

        with telemetry_context(
            project_id=project_id,
            user_id=user_id,
            operation="papers.fetch_read",
        ):
            fetcher = FetcherAgent()
            fetch_payload = {
                "project_id": project_id,
                "items": [FetchItem(paper_id=paper_id, pdf_url=target.pdf_url).model_dump()],
            }
            fetch_result = fetcher.run(fetch_payload)
            fr = FetchResult(**(fetch_result.get("items") or [{}])[0])
            if fr.status != "ok" or not fr.grobid_xml_path:
                set_task(db, task_id, "failed", f"Fetch/parse failed: {fr.status}")
                write_task_audit_log(
                    SessionLocal,
                    correlation_id=task_id,
                    task_name="papers.fetch_read",
                    project_id=project_id,
                    action="failed",
                    status_code=400,
                    user_id=user_id,
                    detail=f"fetch_parse_failed:{fr.status}",
                )
                return

            update_paper_paths(db, paper_id, target.pdf_url, fr.grobid_xml_path)

            reader = ReaderAgent()
            read_result = ReadResult(
                **reader.run({"paper_id": paper_id, "grobid_xml_path": fr.grobid_xml_path})
            )
            saved = save_chunks(db, project_id, paper_id, read_result.chunks)

            texts = [c.text for c in saved]
            vectors = embed_texts(texts)
            add_vectors(project_id, vectors, [c.chunk_id for c in saved])
            update_embeddings(db, [c.chunk_id for c in saved], [c.chunk_id for c in saved])

        set_project_status(db, project_id, "read")
        set_task(db, task_id, "done")
        write_task_audit_log(
            SessionLocal,
            correlation_id=task_id,
            task_name="papers.fetch_read",
            project_id=project_id,
            action="done",
            status_code=200,
            user_id=user_id,
            detail=f"paper_id={paper_id}",
        )
    except Exception as exc:
        set_task(db, task_id, "failed", str(exc))
        write_task_audit_log(
            SessionLocal,
            correlation_id=task_id,
            task_name="papers.fetch_read",
            project_id=project_id,
            action="failed",
            status_code=500,
            user_id=user_id,
            detail=str(exc),
        )
    finally:
        db.close()


@router.post("", response_model=IdResponse)
def add_paper_endpoint(
    project_id: str,
    payload: PaperCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> IdResponse:
    paper_id = add_paper(db, project_id, payload)
    if payload.auto_fetch:
        task_id = create_task(db)
        write_task_audit_log(
            SessionLocal,
            correlation_id=task_id,
            task_name="papers.fetch_read",
            project_id=project_id,
            action="queued",
            status_code=202,
            user_id=identity.user_id if identity else None,
            detail=f"paper_id={paper_id}",
        )
        background_tasks.add_task(
            _run_fetch_read_task,
            task_id,
            project_id,
            paper_id,
            identity.user_id if identity else None,
        )
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
    project_id: str,
    paper_id: str,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> ReadResult:
    set_project_status(db, project_id, "fetch")
    items = list_papers(db, project_id)
    target = next((p for p in items if p.id == paper_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    with telemetry_context(
        project_id=project_id,
        user_id=identity.user_id if identity else None,
        operation="papers.fetch_read",
    ):
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
        result = ReadResult(**reader.run(read_payload))
        saved = save_chunks(db, project_id, paper_id, result.chunks)

        texts = [c.text for c in saved]
        vectors = embed_texts(texts)
        add_vectors(project_id, vectors, [c.chunk_id for c in saved])
        update_embeddings(db, [c.chunk_id for c in saved], [c.chunk_id for c in saved])

    set_project_status(db, project_id, "read")
    return result


@router.post("/{paper_id}/fetch_read_async", response_model=IdResponse)
def fetch_and_read_async(
    project_id: str,
    paper_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> IdResponse:
    task_id = create_task(db)
    write_task_audit_log(
        SessionLocal,
        correlation_id=task_id,
        task_name="papers.fetch_read",
        project_id=project_id,
        action="queued",
        status_code=202,
        user_id=identity.user_id if identity else None,
        detail=f"paper_id={paper_id}",
    )
    background_tasks.add_task(
        _run_fetch_read_task,
        task_id,
        project_id,
        paper_id,
        identity.user_id if identity else None,
    )
    return IdResponse(id=task_id)
