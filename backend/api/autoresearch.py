from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config.db import SessionLocal
from config.deps import get_db, get_identity, require_project_access
from schemas.autoresearch import (
    AutoResearchBridgeImportRequest,
    AutoResearchBridgeUpdateRead,
    AutoResearchBudgetStatus,
    AutoResearchBundleIndexRead,
    AutoResearchCandidateRegistryRead,
    AutoResearchExecutionCommandResponse,
    AutoResearchExperimentBridgeRead,
    AutoResearchNoveltyStatus,
    AutoResearchOperatorConsoleRead,
    AutoResearchPublicationManifestRead,
    AutoResearchPublishExportRequest,
    AutoResearchPublishStatus,
    AutoResearchPublishExportRead,
    AutoResearchPublishPackageRead,
    AutoResearchQueuePriority,
    AutoResearchRunConfig,
    AutoResearchRunControlPatch,
    AutoResearchRunControlUpdateRead,
    AutoResearchRunList,
    AutoResearchRunRead,
    AutoResearchRunStatus,
    AutoResearchRunReviewRead,
    AutoResearchReviewLoopRead,
    AutoResearchReviewLoopApplyRead,
    AutoResearchReviewLoopApplyRequest,
    AutoResearchRunRegistryRead,
    AutoResearchRunRegistryViewsRead,
    AutoResearchRunRequest,
    AutoResearchRunExecutionRead,
    AutoResearchUnsupportedClaimRisk,
)
from schemas.common import IdResponse
from services.autoresearch.bridge import (
    AutoResearchExperimentBridgeService,
    bridge_is_waiting_for_result,
    build_bridge_state,
)
from services.autoresearch.console import build_operator_console
from services.autoresearch.execution import AutoResearchExecutionPlane
from services.autoresearch.orchestrator import AutoResearchOrchestrator
from services.autoresearch.review_publish import (
    build_publish_package,
    build_publication_manifest,
    build_review_loop,
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
    if request_snapshot.experiment_bridge is not None and request_snapshot.experiment_bridge.enabled:
        execution_plane.drain()
    else:
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
    budget_status: AutoResearchBudgetStatus | None = Query(default=None),
    queue_priority: AutoResearchQueuePriority | None = Query(default=None),
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
        budget_status=budget_status,
        queue_priority=queue_priority,
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


@router.patch("/{run_id}/controls", response_model=AutoResearchRunControlUpdateRead)
def patch_auto_research_run_controls(
    project_id: str,
    run_id: str,
    payload: AutoResearchRunControlPatch,
    db: Session = Depends(get_db),
) -> AutoResearchRunControlUpdateRead:
    del db
    plane = AutoResearchExecutionPlane()
    try:
        run = plane.update_run_controls(project_id=project_id, run_id=run_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AutoResearchRunControlUpdateRead(
        run=run,
        execution=plane.get_run_execution(project_id, run_id),
    )


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


@router.get("/{run_id}/bridge", response_model=AutoResearchExperimentBridgeRead)
def get_auto_research_bridge(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchExperimentBridgeRead:
    del db
    bridge = build_bridge_state(project_id, run_id)
    if bridge is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return bridge


@router.post("/{run_id}/bridge/refresh", response_model=AutoResearchBridgeUpdateRead)
def refresh_auto_research_bridge(
    project_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AutoResearchBridgeUpdateRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    bridge_service = AutoResearchExperimentBridgeService()
    try:
        bridge, artifact, source = bridge_service.refresh_waiting_session(
            project_id=project_id,
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    imported = False
    resumed = False
    if artifact is not None:
        bridge, run = bridge_service.import_result(
            project_id=project_id,
            run_id=run_id,
            session_id=bridge.current_session.session_id if bridge.current_session is not None else None,
            artifact=artifact,
            source=source,
        )
        imported = True
        if bridge.config is not None and bridge.config.auto_resume_on_result:
            plane = AutoResearchExecutionPlane()
            _job, created = plane.enqueue(project_id=project_id, run_id=run_id, action="resume")
            if created:
                bridge = bridge_service.record_resume_enqueued(project_id=project_id, run_id=run_id)
                plane.drain()
                resumed = True
    execution = AutoResearchExecutionPlane().get_run_execution(project_id, run_id)
    latest_run = load_run(project_id, run_id)
    if latest_run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    latest_bridge = build_bridge_state(project_id, run_id)
    if latest_bridge is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return AutoResearchBridgeUpdateRead(
        bridge=latest_bridge,
        run=latest_run,
        execution=execution,
        imported=imported,
        resumed=resumed,
        source=source,  # type: ignore[arg-type]
    )


@router.post("/{run_id}/bridge/import", response_model=AutoResearchBridgeUpdateRead)
def import_auto_research_bridge_result(
    project_id: str,
    run_id: str,
    payload: AutoResearchBridgeImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AutoResearchBridgeUpdateRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    bridge_service = AutoResearchExperimentBridgeService()
    try:
        bridge, _run = bridge_service.import_inline_result(
            project_id=project_id,
            run_id=run_id,
            session_id=payload.session_id,
            summary=payload.summary,
            objective_score=payload.objective_score,
            primary_metric=payload.primary_metric,
            objective_system=payload.objective_system,
            baseline_system=payload.baseline_system,
            baseline_score=payload.baseline_score,
            key_findings=payload.key_findings,
            notes=payload.notes,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc

    resumed = False
    if bridge.config is not None and bridge.config.auto_resume_on_result:
        plane = AutoResearchExecutionPlane()
        _job, created = plane.enqueue(project_id=project_id, run_id=run_id, action="resume")
        if created:
            bridge = bridge_service.record_resume_enqueued(project_id=project_id, run_id=run_id)
            plane.drain()
            resumed = True
    execution = AutoResearchExecutionPlane().get_run_execution(project_id, run_id)
    latest_run = load_run(project_id, run_id)
    if latest_run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    latest_bridge = build_bridge_state(project_id, run_id)
    if latest_bridge is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return AutoResearchBridgeUpdateRead(
        bridge=latest_bridge,
        run=latest_run,
        execution=execution,
        imported=True,
        resumed=resumed,
        source="inline",
    )


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


@router.get("/{run_id}/review-loop", response_model=AutoResearchReviewLoopRead)
def get_auto_research_review_loop(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchReviewLoopRead:
    del db
    loop = build_review_loop(project_id, run_id)
    if loop is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return loop


@router.post("/{run_id}/review-loop/refresh", response_model=AutoResearchReviewLoopRead)
def refresh_auto_research_review_loop(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchReviewLoopRead:
    del db
    loop = build_review_loop(project_id, run_id)
    if loop is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return loop


@router.post("/{run_id}/review-loop/apply", response_model=AutoResearchReviewLoopApplyRead)
def apply_auto_research_review_loop_actions(
    project_id: str,
    run_id: str,
    payload: AutoResearchReviewLoopApplyRequest,
    db: Session = Depends(get_db),
) -> AutoResearchReviewLoopApplyRead:
    try:
        run = AutoResearchOrchestrator().apply_review_actions(
            db=db,
            project_id=project_id,
            run_id=run_id,
            expected_round=payload.expected_round,
            expected_review_fingerprint=payload.expected_review_fingerprint,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc
    review = build_run_review(project_id, run_id)
    review_loop = build_review_loop(project_id, run_id)
    if review is None or review_loop is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    return AutoResearchReviewLoopApplyRead(
        run=run,
        review=review,
        review_loop=review_loop,
    )


@router.post("/{run_id}/paper/rebuild", response_model=AutoResearchRunRead)
def rebuild_auto_research_paper_pipeline(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchRunRead:
    try:
        return AutoResearchOrchestrator().rebuild_paper_pipeline(
            db=db,
            project_id=project_id,
            run_id=run_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc


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


@router.get("/{run_id}/publish/manifest", response_model=AutoResearchPublicationManifestRead)
def get_auto_research_publication_manifest(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchPublicationManifestRead:
    del db
    manifest = build_publication_manifest(project_id, run_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Auto research publication manifest not found")
    return manifest


@router.post("/{run_id}/publish/export", response_model=AutoResearchPublishExportRead)
def export_auto_research_publish_package(
    project_id: str,
    run_id: str,
    payload: AutoResearchPublishExportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> AutoResearchPublishExportRead:
    del db
    export_result = export_publish_package(
        project_id,
        run_id,
        deployment_id=payload.deployment_id if payload is not None else None,
        deployment_label=payload.deployment_label if payload is not None else None,
    )
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
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    package = build_publish_package(project_id, run_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    archive_path = get_publish_archive_path(project_id, run_id).resolve()
    if not package.archive_ready or not archive_path.is_file():
        raise HTTPException(status_code=409, detail="Publish package has not been exported yet")
    if not package.archive_current:
        raise HTTPException(
            status_code=409,
            detail="Publish package export is stale; export again for the current review state",
        )
    return FileResponse(
        path=archive_path,
        filename=archive_path.name,
        media_type="application/zip",
    )


@router.get("/{run_id}/publish/code/download")
def download_auto_research_code_package(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    del db
    manifest = build_publication_manifest(project_id, run_id)
    if manifest is None or manifest.code_package_path is None:
        raise HTTPException(status_code=404, detail="Auto research code package not found")
    code_package_path = Path(manifest.code_package_path).resolve()
    if not code_package_path.is_file():
        raise HTTPException(status_code=404, detail="Auto research code package not found")
    return FileResponse(
        path=code_package_path,
        filename=code_package_path.name,
        media_type="application/zip",
    )


@router.get("/{run_id}/publish/paper/download")
def download_auto_research_paper_asset(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    del db
    manifest = build_publication_manifest(project_id, run_id)
    if manifest is None or manifest.paper_path is None:
        raise HTTPException(status_code=404, detail="Auto research paper asset not found")
    paper_path = Path(manifest.paper_path).resolve()
    if not paper_path.is_file():
        raise HTTPException(status_code=404, detail="Auto research paper asset not found")
    return FileResponse(
        path=paper_path,
        filename=paper_path.name,
        media_type="text/markdown",
    )


@router.get("/{run_id}/publish/paper/compiled/download")
def download_auto_research_compiled_paper_asset(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    del db
    manifest = build_publication_manifest(project_id, run_id)
    if manifest is None or manifest.compiled_paper_path is None:
        raise HTTPException(status_code=404, detail="Auto research compiled paper asset not found")
    compiled_paper_path = Path(manifest.compiled_paper_path).resolve()
    if not compiled_paper_path.is_file():
        raise HTTPException(status_code=404, detail="Auto research compiled paper asset not found")
    return FileResponse(
        path=compiled_paper_path,
        filename=compiled_paper_path.name,
        media_type="application/pdf",
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
    if action == "resume" and bridge_is_waiting_for_result(project_id, run_id):
        raise HTTPException(
            status_code=409,
            detail="Auto research run is waiting for bridge result import before it can resume",
        )
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
        if bridge_is_waiting_for_result(project_id, run_id):
            try:
                AutoResearchExperimentBridgeService().cancel_waiting_session(
                    project_id=project_id,
                    run_id=run_id,
                )
            except ValueError as bridge_exc:
                raise HTTPException(status_code=409, detail=str(bridge_exc)) from bridge_exc
            execution = AutoResearchExecutionPlane().get_run_execution(project_id, run_id)
        else:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    latest_job = execution.jobs[-1] if execution.jobs else None
    return AutoResearchExecutionCommandResponse(
        run_id=run_id,
        job_id=latest_job.id if latest_job is not None else None,
        status="accepted",
        execution=execution,
    )
