from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from config.db import SessionLocal
from config.deps import get_db, get_identity, require_project_access
from schemas.autoresearch import (
    AutoResearchRunList,
    AutoResearchRunRead,
    AutoResearchRunRequest,
    BenchmarkSource,
    TaskFamily,
)
from schemas.common import IdResponse
from services.autoresearch.orchestrator import AutoResearchOrchestrator
from services.autoresearch.repository import create_run, list_runs, load_run
from services.security.audit import write_task_audit_log
from services.security.auth import AuthIdentity

router = APIRouter(
    prefix="/api/projects/{project_id}/auto-research",
    tags=["auto-research"],
    dependencies=[Depends(require_project_access)],
)


def _run_autoresearch(
    project_id: str,
    run_id: str,
    topic: str,
    task_family_hint: TaskFamily | None,
    paper_ids: list[str] | None,
    max_rounds: int,
    benchmark: dict | None,
    docker_image: str | None,
    user_id: str | None,
) -> None:
    write_task_audit_log(
        SessionLocal,
        correlation_id=run_id,
        task_name="autoresearch.run",
        project_id=project_id,
        action="running",
        status_code=102,
        user_id=user_id,
        detail=f"topic={topic}",
    )
    db = SessionLocal()
    try:
        result = AutoResearchOrchestrator().execute(
            db=db,
            project_id=project_id,
            run_id=run_id,
            topic=topic,
            task_family_hint=task_family_hint,
            paper_ids=paper_ids,
            max_rounds=max_rounds,
            benchmark_source=BenchmarkSource.model_validate(benchmark) if benchmark else None,
            docker_image=docker_image,
        )
        status_code = 200 if result.status == "done" else 500
        action = "done" if result.status == "done" else "failed"
        detail = result.error or f"task_family={result.task_family}"
        write_task_audit_log(
            SessionLocal,
            correlation_id=run_id,
            task_name="autoresearch.run",
            project_id=project_id,
            action=action,
            status_code=status_code,
            user_id=user_id,
            detail=detail,
        )
    finally:
        db.close()


@router.post("/run", response_model=IdResponse)
def run_auto_research(
    project_id: str,
    payload: AutoResearchRunRequest,
    background_tasks: BackgroundTasks,
    identity: AuthIdentity | None = Depends(get_identity),
) -> IdResponse:
    run = create_run(project_id, payload.topic, payload.docker_image)
    write_task_audit_log(
        SessionLocal,
        correlation_id=run.id,
        task_name="autoresearch.run",
        project_id=project_id,
        action="queued",
        status_code=202,
        user_id=identity.user_id if identity else None,
        detail=f"topic={payload.topic}",
    )
    background_tasks.add_task(
        _run_autoresearch,
        project_id,
        run.id,
        payload.topic,
        payload.task_family_hint,
        payload.paper_ids,
        payload.max_rounds,
        payload.benchmark.model_dump(mode="json") if payload.benchmark else None,
        payload.docker_image,
        identity.user_id if identity else None,
    )
    return IdResponse(id=run.id)


@router.get("", response_model=AutoResearchRunList)
def list_auto_research_runs(
    project_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchRunList:
    del db
    return AutoResearchRunList(items=list_runs(project_id))


@router.get("/{run_id}", response_model=AutoResearchRunRead)
def get_auto_research_run(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchRunRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return run
