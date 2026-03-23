from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config.db import SessionLocal
from config.deps import get_db, get_identity, require_project_access
from schemas.autoresearch import (
    AutoResearchBundleIndexRead,
    AutoResearchCandidateRegistryRead,
    AutoResearchExecutionCommandResponse,
    AutoResearchNoveltyStatus,
    AutoResearchOperatorConsoleRead,
    AutoResearchPublishStatus,
    AutoResearchPublishExportRead,
    AutoResearchPublishPackageRead,
    AutoResearchRunConfig,
    AutoResearchRunList,
    AutoResearchRunRead,
    AutoResearchRunStatus,
    AutoResearchRunReviewRead,
    AutoResearchRunRegistryRead,
    AutoResearchRunRegistryViewsRead,
    AutoResearchRunRequest,
    AutoResearchRunExecutionRead,
    AutoResearchUnsupportedClaimRisk,
)
from schemas.common import IdResponse
from services.autoresearch.console import build_operator_console
from services.autoresearch.execution import AutoResearchExecutionPlane
from services.autoresearch.review_publish import (
    build_publish_package,
    build_run_review,
    export_publish_package,
    get_publish_archive_path,
)
from services.autoresearch.repository import (
    create_run,
    list_runs,
    load_candidate_registry,
    load_run_bundle_index,
    load_run,
    load_run_registry,
    load_run_registry_views,
)
from services.security.audit import write_task_audit_log
from services.security.auth import AuthIdentity

router = APIRouter(
    prefix="/api/projects/{project_id}/auto-research",
    tags=["auto-research"],
    dependencies=[Depends(require_project_access)],
)


@router.post("/run", response_model=IdResponse)
def run_auto_research(
    project_id: str,
    payload: AutoResearchRunRequest,
    background_tasks: BackgroundTasks,
    identity: AuthIdentity | None = Depends(get_identity),
) -> IdResponse:
    execution_plane = AutoResearchExecutionPlane()
    request_snapshot = AutoResearchRunConfig.from_request(payload)
    run = create_run(
        project_id,
        payload.topic,
        request=request_snapshot,
    )
    job, _created = execution_plane.enqueue(project_id=project_id, run_id=run.id, action="run")
    write_task_audit_log(
        SessionLocal,
        correlation_id=run.id,
        task_name="autoresearch.run",
        project_id=project_id,
        action="queued",
        status_code=202,
        user_id=identity.user_id if identity else None,
        detail=f"job_id={job.id} action=run topic={payload.topic}",
    )
    background_tasks.add_task(execution_plane.drain)
    return IdResponse(id=run.id)


@router.get("", response_model=AutoResearchRunList)
def list_auto_research_runs(
    project_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchRunList:
    del db
    return AutoResearchRunList(items=list_runs(project_id))


@router.get("/console", response_model=AutoResearchOperatorConsoleRead)
def get_auto_research_operator_console(
    project_id: str,
    run_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    status: AutoResearchRunStatus | None = Query(default=None),
    publish_status: AutoResearchPublishStatus | None = Query(default=None),
    review_risk: AutoResearchUnsupportedClaimRisk | None = Query(default=None),
    novelty_status: AutoResearchNoveltyStatus | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AutoResearchOperatorConsoleRead:
    del db
    return build_operator_console(
        project_id,
        run_id=run_id,
        search=search,
        status=status,
        publish_status=publish_status,
        review_risk=review_risk,
        novelty_status=novelty_status,
    )


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


@router.get("/{run_id}/execution", response_model=AutoResearchRunExecutionRead)
def get_auto_research_execution(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchRunExecutionRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return AutoResearchExecutionPlane().get_run_execution(project_id, run_id)


@router.get("/{run_id}/registry", response_model=AutoResearchRunRegistryRead)
def get_auto_research_registry(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchRunRegistryRead:
    del db
    registry = load_run_registry(project_id, run_id)
    if registry is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return registry


@router.get(
    "/{run_id}/registry/candidates/{candidate_id}",
    response_model=AutoResearchCandidateRegistryRead,
)
def get_auto_research_candidate_registry(
    project_id: str,
    run_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchCandidateRegistryRead:
    del db
    candidate = load_candidate_registry(project_id, run_id, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Auto research candidate not found")
    return candidate


@router.get("/{run_id}/registry/bundles", response_model=AutoResearchBundleIndexRead)
def get_auto_research_bundle_index(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchBundleIndexRead:
    del db
    bundle_index = load_run_bundle_index(project_id, run_id)
    if bundle_index is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return bundle_index


@router.get("/{run_id}/registry/views", response_model=AutoResearchRunRegistryViewsRead)
def get_auto_research_registry_views(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchRunRegistryViewsRead:
    del db
    views = load_run_registry_views(project_id, run_id)
    if views is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return views


@router.get("/{run_id}/review", response_model=AutoResearchRunReviewRead)
def get_auto_research_run_review(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchRunReviewRead:
    del db
    review = build_run_review(project_id, run_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return review


@router.get("/{run_id}/publish", response_model=AutoResearchPublishPackageRead)
def get_auto_research_publish_package(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchPublishPackageRead:
    del db
    package = build_publish_package(project_id, run_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return package


@router.post("/{run_id}/publish/export", response_model=AutoResearchPublishExportRead)
def export_auto_research_publish_package(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchPublishExportRead:
    del db
    export_result = export_publish_package(project_id, run_id)
    if export_result is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return export_result


@router.get("/{run_id}/publish/download")
def download_auto_research_publish_package(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    del db
    archive_path = get_publish_archive_path(project_id, run_id).resolve()
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    if not archive_path.is_file():
        raise HTTPException(status_code=409, detail="Publish package has not been exported yet")
    return FileResponse(
        path=archive_path,
        filename=archive_path.name,
        media_type="application/zip",
    )


def _queue_existing_run(
    *,
    project_id: str,
    run_id: str,
    action: str,
    background_tasks: BackgroundTasks,
    identity: AuthIdentity | None,
) -> AutoResearchExecutionCommandResponse:
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    plane = AutoResearchExecutionPlane()
    if action == "resume" and run.status == "done":
        execution = plane.get_run_execution(project_id, run_id)
        latest_job = execution.jobs[-1] if execution.jobs else None
        return AutoResearchExecutionCommandResponse(
            run_id=run_id,
            job_id=latest_job.id if latest_job is not None else None,
            status="noop",
            execution=execution,
        )
    job, created = plane.enqueue(
        project_id=project_id,
        run_id=run_id,
        action=str(action),
    )
    if created:
        write_task_audit_log(
            SessionLocal,
            correlation_id=run_id,
            task_name="autoresearch.run",
            project_id=project_id,
            action="queued",
            status_code=202,
            user_id=identity.user_id if identity else None,
            detail=f"job_id={job.id} action={action} topic={run.topic}",
        )
    background_tasks.add_task(plane.drain)
    execution = plane.get_run_execution(project_id, run_id)
    return AutoResearchExecutionCommandResponse(
        run_id=run_id,
        job_id=job.id,
        status="accepted" if created else "noop",
        execution=execution,
    )


@router.post("/{run_id}/resume", response_model=AutoResearchExecutionCommandResponse)
def resume_auto_research_run(
    project_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> AutoResearchExecutionCommandResponse:
    del db
    return _queue_existing_run(
        project_id=project_id,
        run_id=run_id,
        action="resume",
        background_tasks=background_tasks,
        identity=identity,
    )


@router.post("/{run_id}/retry", response_model=AutoResearchExecutionCommandResponse)
def retry_auto_research_run(
    project_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> AutoResearchExecutionCommandResponse:
    del db
    return _queue_existing_run(
        project_id=project_id,
        run_id=run_id,
        action="retry",
        background_tasks=background_tasks,
        identity=identity,
    )


@router.post("/{run_id}/cancel", response_model=AutoResearchExecutionCommandResponse)
def cancel_auto_research_run(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchExecutionCommandResponse:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    try:
        execution = AutoResearchExecutionPlane().request_cancel(project_id=project_id, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    latest_job = execution.jobs[-1] if execution.jobs else None
    return AutoResearchExecutionCommandResponse(
        run_id=run_id,
        job_id=latest_job.id if latest_job is not None else None,
        status="accepted",
        execution=execution,
    )
