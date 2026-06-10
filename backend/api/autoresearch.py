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
    AutoResearchCrossRunMetaAnalysisRead,
    AutoResearchExecutionCommandResponse,
    AutoResearchEvaluationCaseSuiteRead,
    AutoResearchExperimentBridgeRead,
    AutoResearchExperimentExecutionImportRequest,
    AutoResearchExperimentExecutionPlanRead,
    AutoResearchExperimentExecutionPlanRequest,
    AutoResearchExperimentExecutionResultRead,
    AutoResearchExperimentFactoryExecutionRead,
    AutoResearchExperimentFactoryImportRequest,
    AutoResearchExperimentFactoryMaterializeRequest,
    AutoResearchExperimentFactoryPlanRead,
    AutoResearchIdeaRequest,
    AutoResearchIdeaRunCreateRequest,
    AutoResearchHypothesisBankRead,
    AutoResearchLiteratureScoutRequest,
    AutoResearchLiteratureScoutResultRead,
    AutoResearchNoveltyStatus,
    AutoResearchOperatorActionRequest,
    AutoResearchOperatorActionResultRead,
    AutoResearchOperatorConsoleRead,
    AutoResearchOperatorRunStatusRead,
    AutoResearchOperatorStateAuditRead,
    AutoResearchProjectPaperOrchestrationRead,
    AutoResearchPublicationTier,
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
    AutoResearchResearchBriefList,
    AutoResearchResearchBriefRead,
    AutoResearchRunStatus,
    AutoResearchRunReviewRead,
    AutoResearchSubmissionPackageRead,
    AutoResearchReviewLoopRead,
    AutoResearchReviewLoopAutoApplyRead,
    AutoResearchReviewLoopAutoApplyRequest,
    AutoResearchReviewLoopApplyRead,
    AutoResearchReviewLoopApplyRequest,
    AutoResearchResearchReplanApplyRead,
    AutoResearchRunRegistryRead,
    AutoResearchRunRegistryViewsRead,
    AutoResearchRunRequest,
    AutoResearchRunExecutionRead,
    AutoResearchSystemEvaluationRead,
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
from services.autoresearch.evaluation_cases import build_evaluation_case_suite
from services.autoresearch.experiment_factory import (
    build_experiment_factory_plan,
    execute_imported_experiment_factory,
    execute_toy_experiment_factory,
    materialize_factory_execution,
)
from services.autoresearch.experiment_execution import (
    build_experiment_execution_plan,
    execute_experiment_execution_plan,
    merge_execution_evidence_ledger,
)
from services.autoresearch.idea_brief import (
    build_research_brief,
    hypothesis_bank_from_brief,
    selected_hypothesis_from_brief,
    run_request_from_selected_hypothesis,
)
from services.autoresearch.literature_scout import scout_and_mine_gaps
from services.autoresearch.meta_analysis import build_cross_run_meta_analysis
from services.autoresearch.operator_control import (
    apply_operator_action,
    build_operator_run_status,
    build_operator_state_audit,
    get_or_build_operator_state_audit,
)
from services.autoresearch.orchestrator import AutoResearchOrchestrator
from services.autoresearch.project_paper_orchestrator import (
    build_project_paper_orchestration,
    get_project_submission_archive_path,
    load_project_submission_package,
)
from services.autoresearch.review_publish import (
    build_publish_package,
    build_publication_manifest,
    build_review_loop,
    build_run_review,
    export_publish_package,
    get_publish_archive_path,
)
from services.autoresearch.system_evaluation import build_system_evaluation
from services.autoresearch.repository import (
    create_run,
    list_research_briefs,
    list_runs,
    load_candidate_registry,
    load_research_brief,
    load_run_bundle_index,
    load_run,
    load_run_registry,
    load_run_registry_views,
    save_run,
    save_research_brief,
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


@router.post("/ideas", response_model=AutoResearchResearchBriefRead)
def create_auto_research_idea_brief(
    project_id: str,
    payload: AutoResearchIdeaRequest,
    identity: AuthIdentity | None = Depends(get_identity),
    db: Session = Depends(get_db),
) -> AutoResearchResearchBriefRead:
    del db
    brief = save_research_brief(
        build_research_brief(
            project_id=project_id,
            payload=payload,
        )
    )
    write_task_audit_log(
        SessionLocal,
        correlation_id=brief.brief_id,
        task_name="autoresearch.idea",
        project_id=project_id,
        action="brief_created",
        status_code=200,
        user_id=identity.user_id if identity else None,
        detail=(
            f"brief_id={brief.brief_id} directions={brief.direction_count} "
            f"domain={brief.domain_decision.domain_id if brief.domain_decision is not None else 'unknown'} "
            f"status={brief.status}"
        ),
    )
    return brief


@router.get("/ideas", response_model=AutoResearchResearchBriefList)
def list_auto_research_idea_briefs(
    project_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchResearchBriefList:
    del db
    return AutoResearchResearchBriefList(items=list_research_briefs(project_id))


@router.get("/ideas/{brief_id}/hypotheses", response_model=AutoResearchHypothesisBankRead)
def get_auto_research_idea_hypothesis_bank(
    project_id: str,
    brief_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchHypothesisBankRead:
    del db
    brief = load_research_brief(project_id, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Auto research idea brief not found")
    bank, selection = hypothesis_bank_from_brief(brief)
    return AutoResearchHypothesisBankRead(
        brief_id=brief.brief_id,
        project_id=brief.project_id,
        hypothesis_count=len(bank),
        hypotheses=bank,
        selected_hypothesis_id=selection.selected_hypothesis_id,
        direction_selection=selection,
    )


@router.post("/ideas/{brief_id}/literature-scout", response_model=AutoResearchLiteratureScoutResultRead)
def run_auto_research_idea_literature_scout(
    project_id: str,
    brief_id: str,
    payload: AutoResearchLiteratureScoutRequest | None = Body(default=None),
    identity: AuthIdentity | None = Depends(get_identity),
    db: Session = Depends(get_db),
) -> AutoResearchLiteratureScoutResultRead:
    del db
    brief = load_research_brief(project_id, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Auto research idea brief not found")
    payload = payload or AutoResearchLiteratureScoutRequest()
    updated = save_research_brief(
        scout_and_mine_gaps(
            brief,
            sources=payload.sources,
            limit_per_source=payload.limit_per_source,
            cache_enabled=payload.cache_enabled,
            network_enabled=payload.allow_network,
        )
    )
    if updated.literature_scout is None or updated.gap_miner is None:
        raise HTTPException(status_code=500, detail="Literature scout did not produce results")
    write_task_audit_log(
        SessionLocal,
        correlation_id=updated.brief_id,
        task_name="autoresearch.literature_scout",
        project_id=project_id,
        action="scouted",
        status_code=200,
        user_id=identity.user_id if identity else None,
        detail=(
            f"brief_id={updated.brief_id} queries={len(updated.literature_scout.search_queries)} "
            f"gaps={len(updated.gap_miner.gap_candidates)}"
        ),
    )
    return AutoResearchLiteratureScoutResultRead(
        brief_id=updated.brief_id,
        project_id=updated.project_id,
        literature_scout=updated.literature_scout,
        gap_miner=updated.gap_miner,
        updated_brief=updated,
    )


@router.post("/ideas/{brief_id}/run", response_model=IdResponse)
def create_auto_research_run_from_idea_brief(
    project_id: str,
    brief_id: str,
    background_tasks: BackgroundTasks,
    payload: AutoResearchIdeaRunCreateRequest | None = Body(default=None),
    identity: AuthIdentity | None = Depends(get_identity),
    db: Session = Depends(get_db),
) -> IdResponse:
    del db
    brief = load_research_brief(project_id, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Auto research idea brief not found")
    if brief.next_action == "blocked" or brief.status == "blocked" or brief.domain_blockers:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This idea brief is blocked by domain routing and cannot create a run.",
                "domain_decision": (
                    brief.domain_decision.model_dump(mode="json")
                    if brief.domain_decision is not None
                    else None
                ),
                "blockers": brief.domain_blockers or brief.feasibility_assessment.blockers,
            },
        )
    if not brief.allow_experiments:
        raise HTTPException(
            status_code=409,
            detail="This idea brief does not allow experiment execution",
        )
    payload = payload or AutoResearchIdeaRunCreateRequest()
    try:
        run_request, hypothesis = run_request_from_selected_hypothesis(
            brief,
            hypothesis_id=payload.hypothesis_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    updates: dict[str, object] = {}
    if payload.max_rounds is not None:
        updates["max_rounds"] = payload.max_rounds
    if payload.candidate_execution_limit is not None:
        updates["candidate_execution_limit"] = payload.candidate_execution_limit
    if payload.queue_priority is not None:
        updates["queue_priority"] = payload.queue_priority
    if payload.execution_profile is not None:
        updates["execution_profile"] = payload.execution_profile
    if updates:
        run_request = run_request.model_copy(update=updates)

    execution_plane = AutoResearchExecutionPlane()
    request_snapshot = AutoResearchRunConfig.from_request(run_request)
    selection_reason = (
        brief.direction_selection.selection_reason
        if brief.direction_selection is not None
        else brief.selection_reason
    )
    run = create_run(
        project_id,
        run_request.topic,
        request=request_snapshot,
        brief_id=brief.brief_id,
        hypothesis_id=hypothesis.hypothesis_id,
        direction_selection_reason=selection_reason,
    )
    job, _created = execution_plane.enqueue(project_id=project_id, run_id=run.id, action="run")
    write_task_audit_log(
        SessionLocal,
        correlation_id=run.id,
        task_name="autoresearch.idea_run",
        project_id=project_id,
        action="queued",
        status_code=202,
        user_id=identity.user_id if identity else None,
        detail=(
            f"job_id={job.id} brief_id={brief.brief_id} "
            f"hypothesis_id={hypothesis.hypothesis_id}"
        ),
    )
    if request_snapshot.experiment_bridge is not None and request_snapshot.experiment_bridge.enabled:
        execution_plane.drain()
    else:
        background_tasks.add_task(execution_plane.drain)
    return IdResponse(id=run.id)


@router.post("/ideas/{brief_id}/experiment-factory", response_model=AutoResearchExperimentFactoryPlanRead)
def build_auto_research_idea_experiment_factory(
    project_id: str,
    brief_id: str,
    hypothesis_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AutoResearchExperimentFactoryPlanRead:
    del db
    brief = load_research_brief(project_id, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Auto research idea brief not found")
    if brief.next_action == "blocked" or brief.status == "blocked" or brief.domain_blockers:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This idea brief is blocked by domain routing and cannot create an experiment plan.",
                "domain_decision": (
                    brief.domain_decision.model_dump(mode="json")
                    if brief.domain_decision is not None
                    else None
                ),
                "blockers": brief.domain_blockers or brief.feasibility_assessment.blockers,
            },
        )
    try:
        hypothesis = selected_hypothesis_from_brief(brief, hypothesis_id=hypothesis_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return build_experiment_factory_plan(
        project_id=project_id,
        brief=brief,
        hypothesis=hypothesis,
    )


@router.get("/ideas/{brief_id}", response_model=AutoResearchResearchBriefRead)
def get_auto_research_idea_brief(
    project_id: str,
    brief_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchResearchBriefRead:
    del db
    brief = load_research_brief(project_id, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Auto research idea brief not found")
    return brief


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
    publication_tier: AutoResearchPublicationTier | None = Query(default=None),
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
        publication_tier=publication_tier,
        review_risk=review_risk,
        novelty_status=novelty_status,
        budget_status=budget_status,
        queue_priority=queue_priority,
    )


@router.get("/operator/audit", response_model=AutoResearchOperatorStateAuditRead)
def get_auto_research_operator_state_audit(
    project_id: str,
    rebuild: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> AutoResearchOperatorStateAuditRead:
    del db
    return build_operator_state_audit(project_id) if rebuild else get_or_build_operator_state_audit(project_id)


@router.get("/meta-analysis", response_model=AutoResearchCrossRunMetaAnalysisRead)
def get_auto_research_meta_analysis(
    project_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchCrossRunMetaAnalysisRead:
    del db
    return build_cross_run_meta_analysis(project_id)


@router.get("/project-paper", response_model=AutoResearchProjectPaperOrchestrationRead)
def get_auto_research_project_paper_orchestration(
    project_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchProjectPaperOrchestrationRead:
    del db
    return build_project_paper_orchestration(project_id)


@router.get("/project-paper/submission", response_model=AutoResearchSubmissionPackageRead)
def get_auto_research_project_submission_package(
    project_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchSubmissionPackageRead:
    del db
    package = load_project_submission_package(project_id)
    if package is None:
        orchestration = build_project_paper_orchestration(project_id)
        package = orchestration.project_submission_package
    if package is None:
        raise HTTPException(status_code=404, detail="Project submission package not found")
    return package


@router.get("/project-paper/submission/download")
def download_auto_research_project_submission_archive(
    project_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    del db
    package = load_project_submission_package(project_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Project submission package not found")
    decision = package.final_publish_decision
    archive_manifest = package.archive_manifest
    if decision is None or not decision.final_publish_ready:
        raise HTTPException(
            status_code=409,
            detail="Project submission archive is not final-publish-ready",
        )
    if archive_manifest is None or not archive_manifest.complete or not archive_manifest.current:
        raise HTTPException(
            status_code=409,
            detail="Project submission archive is incomplete or stale",
        )
    archive_path = get_project_submission_archive_path(project_id).resolve()
    if Path(archive_manifest.archive_path).resolve() != archive_path:
        raise HTTPException(status_code=409, detail="Project submission archive path is invalid")
    if not archive_path.is_file():
        raise HTTPException(status_code=409, detail="Project submission archive is missing")
    return FileResponse(
        path=archive_path,
        filename=archive_path.name,
        media_type="application/zip",
    )


@router.get("/system-evaluation", response_model=AutoResearchSystemEvaluationRead)
def get_auto_research_system_evaluation(
    project_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchSystemEvaluationRead:
    del db
    return build_system_evaluation(project_id)


@router.get("/evaluation-cases", response_model=AutoResearchEvaluationCaseSuiteRead)
def get_auto_research_evaluation_cases(
    project_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchEvaluationCaseSuiteRead:
    del db
    return build_evaluation_case_suite(project_id)


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


def _experiment_factory_plan_for_run(
    project_id: str,
    run: AutoResearchRunRead,
) -> tuple[AutoResearchExperimentFactoryPlanRead, AutoResearchResearchBriefRead | None]:
    brief = load_research_brief(project_id, run.brief_id) if run.brief_id else None
    hypothesis = None
    if brief is not None:
        try:
            hypothesis = selected_hypothesis_from_brief(brief, hypothesis_id=run.hypothesis_id)
        except ValueError:
            hypothesis = None
    return (
        build_experiment_factory_plan(
            project_id=project_id,
            brief=brief,
            hypothesis=hypothesis,
            run=run,
            experiment_design=getattr(run, "experiment_design", None),
        ),
        brief,
    )


@router.post("/{run_id}/experiment-factory", response_model=AutoResearchExperimentFactoryPlanRead)
def build_auto_research_run_experiment_factory(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchExperimentFactoryPlanRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    brief = load_research_brief(project_id, run.brief_id) if run.brief_id else None
    hypothesis = None
    if brief is not None:
        try:
            hypothesis = selected_hypothesis_from_brief(brief, hypothesis_id=run.hypothesis_id)
        except ValueError:
            hypothesis = None
    return build_experiment_factory_plan(
        project_id=project_id,
        brief=brief,
        hypothesis=hypothesis,
        run=run,
        experiment_design=getattr(run, "experiment_design", None),
    )


@router.post("/{run_id}/experiment-execution/plan", response_model=AutoResearchExperimentExecutionPlanRead)
def build_auto_research_run_experiment_execution_plan(
    project_id: str,
    run_id: str,
    payload: AutoResearchExperimentExecutionPlanRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> AutoResearchExperimentExecutionPlanRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    factory_plan, brief = _experiment_factory_plan_for_run(project_id, run)
    plan = build_experiment_execution_plan(
        factory_plan=factory_plan,
        brief=brief,
        request=payload or AutoResearchExperimentExecutionPlanRequest(),
    )
    save_run(
        run.model_copy(
            update={
                "experiment_factory_plan": factory_plan,
                "experiment_execution_plan": plan,
            }
        )
    )
    return plan


@router.post("/{run_id}/experiment-execution/execute", response_model=AutoResearchExperimentExecutionResultRead)
def execute_auto_research_run_experiment_execution(
    project_id: str,
    run_id: str,
    payload: AutoResearchExperimentExecutionPlanRequest | None = Body(default=None),
    identity: AuthIdentity | None = Depends(get_identity),
    db: Session = Depends(get_db),
) -> AutoResearchExperimentExecutionResultRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    factory_plan, brief = _experiment_factory_plan_for_run(project_id, run)
    plan = build_experiment_execution_plan(
        factory_plan=factory_plan,
        brief=brief,
        request=payload or AutoResearchExperimentExecutionPlanRequest(),
    )
    result = execute_experiment_execution_plan(plan)
    merged_ledger = merge_execution_evidence_ledger(run.evidence_ledger, result.evidence_ledger)
    save_run(
        run.model_copy(
            update={
                "status": "done" if result.status == "succeeded" else "failed",
                "error": None if result.status == "succeeded" else "; ".join(result.repair_reasons[:3]) or result.failure_classification,
                "experiment_factory_plan": factory_plan,
                "experiment_execution_plan": plan,
                "experiment_execution_result": result,
                "artifact": result.result_artifact or run.artifact,
                "evidence_ledger": merged_ledger,
            }
        )
    )
    write_task_audit_log(
        SessionLocal,
        correlation_id=run.id,
        task_name="autoresearch.experiment_execution",
        project_id=project_id,
        action="executed",
        status_code=200,
        user_id=identity.user_id if identity else None,
        detail=(
            f"run_id={run.id} status={result.status} "
            f"failure={result.failure_classification} jobs={plan.job_count}"
        ),
    )
    return result


@router.post("/{run_id}/experiment-execution/import", response_model=AutoResearchExperimentExecutionResultRead)
def import_auto_research_run_experiment_execution_result(
    project_id: str,
    run_id: str,
    payload: AutoResearchExperimentExecutionImportRequest,
    identity: AuthIdentity | None = Depends(get_identity),
    db: Session = Depends(get_db),
) -> AutoResearchExperimentExecutionResultRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    factory_plan, brief = _experiment_factory_plan_for_run(project_id, run)
    plan = build_experiment_execution_plan(
        factory_plan=factory_plan,
        brief=brief,
        request=AutoResearchExperimentExecutionPlanRequest(execution_route="external_import"),
    )
    result = execute_experiment_execution_plan(plan, import_request=payload)
    merged_ledger = merge_execution_evidence_ledger(run.evidence_ledger, result.evidence_ledger)
    save_run(
        run.model_copy(
            update={
                "status": "done" if result.status == "succeeded" else "failed",
                "error": None if result.status == "succeeded" else "; ".join(result.repair_reasons[:3]) or result.failure_classification,
                "experiment_factory_plan": factory_plan,
                "experiment_execution_plan": plan,
                "experiment_execution_result": result,
                "artifact": result.result_artifact or run.artifact,
                "evidence_ledger": merged_ledger,
            }
        )
    )
    write_task_audit_log(
        SessionLocal,
        correlation_id=run.id,
        task_name="autoresearch.experiment_execution",
        project_id=project_id,
        action="external_imported",
        status_code=200,
        user_id=identity.user_id if identity else None,
        detail=(
            f"run_id={run.id} status={result.status} "
            f"failure={result.failure_classification} jobs={plan.job_count}"
        ),
    )
    return result


@router.post("/{run_id}/experiment-factory/toy-execute", response_model=AutoResearchExperimentFactoryExecutionRead)
def execute_auto_research_run_experiment_factory_toy(
    project_id: str,
    run_id: str,
    identity: AuthIdentity | None = Depends(get_identity),
    db: Session = Depends(get_db),
) -> AutoResearchExperimentFactoryExecutionRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    brief = load_research_brief(project_id, run.brief_id) if run.brief_id else None
    hypothesis = None
    if brief is not None:
        try:
            hypothesis = selected_hypothesis_from_brief(brief, hypothesis_id=run.hypothesis_id)
        except ValueError:
            hypothesis = None
    plan = build_experiment_factory_plan(
        project_id=project_id,
        brief=brief,
        hypothesis=hypothesis,
        run=run,
        experiment_design=getattr(run, "experiment_design", None),
    )
    execution = execute_toy_experiment_factory(plan)
    save_run(
        run.model_copy(
            update={
                "status": "done",
                "error": None,
                "experiment_factory_plan": execution.execution_plan,
                "experiment_factory_environment_manifest": execution.environment_manifest,
                "experiment_factory_materialized_jobs": execution.materialized_jobs,
                "artifact": execution.result_artifact,
                "evidence_ledger": execution.evidence_ledger,
                "experiment_factory_repair_plan": execution.repair_plan,
            }
        )
    )
    write_task_audit_log(
        SessionLocal,
        correlation_id=run.id,
        task_name="autoresearch.experiment_factory",
        project_id=project_id,
        action="toy_executed",
        status_code=200,
        user_id=identity.user_id if identity else None,
        detail=f"run_id={run.id} jobs={plan.job_count} ledger_entries={execution.evidence_ledger.entry_count}",
    )
    return execution


@router.post("/{run_id}/experiment-factory/materialize", response_model=AutoResearchExperimentFactoryExecutionRead)
def materialize_auto_research_run_experiment_factory(
    project_id: str,
    run_id: str,
    payload: AutoResearchExperimentFactoryMaterializeRequest | None = Body(default=None),
    identity: AuthIdentity | None = Depends(get_identity),
    db: Session = Depends(get_db),
) -> AutoResearchExperimentFactoryExecutionRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    payload = payload or AutoResearchExperimentFactoryMaterializeRequest()
    brief = load_research_brief(project_id, run.brief_id) if run.brief_id else None
    hypothesis = None
    if brief is not None:
        try:
            hypothesis = selected_hypothesis_from_brief(brief, hypothesis_id=run.hypothesis_id)
        except ValueError:
            hypothesis = None
    plan = build_experiment_factory_plan(
        project_id=project_id,
        brief=brief,
        hypothesis=hypothesis,
        run=run,
        experiment_design=getattr(run, "experiment_design", None),
    )
    execution = materialize_factory_execution(
        plan,
        executor_mode=payload.executor_mode,
    )
    save_run(
        run.model_copy(
            update={
                "status": "running" if run.status in {"queued", "running"} else run.status,
                "experiment_factory_plan": execution.execution_plan,
                "experiment_factory_environment_manifest": execution.environment_manifest,
                "experiment_factory_materialized_jobs": execution.materialized_jobs,
                "evidence_ledger": execution.evidence_ledger,
            }
        )
    )
    write_task_audit_log(
        SessionLocal,
        correlation_id=run.id,
        task_name="autoresearch.experiment_factory",
        project_id=project_id,
        action=f"{payload.executor_mode}_materialized",
        status_code=200,
        user_id=identity.user_id if identity else None,
        detail=f"run_id={run.id} jobs={plan.job_count}",
    )
    return execution


@router.post("/{run_id}/experiment-factory/import", response_model=AutoResearchExperimentFactoryExecutionRead)
def import_auto_research_run_experiment_factory_result(
    project_id: str,
    run_id: str,
    payload: AutoResearchExperimentFactoryImportRequest,
    identity: AuthIdentity | None = Depends(get_identity),
    db: Session = Depends(get_db),
) -> AutoResearchExperimentFactoryExecutionRead:
    del db
    run = load_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Auto research run not found")
    brief = load_research_brief(project_id, run.brief_id) if run.brief_id else None
    hypothesis = None
    if brief is not None:
        try:
            hypothesis = selected_hypothesis_from_brief(brief, hypothesis_id=run.hypothesis_id)
        except ValueError:
            hypothesis = None
    plan = build_experiment_factory_plan(
        project_id=project_id,
        brief=brief,
        hypothesis=hypothesis,
        run=run,
        experiment_design=getattr(run, "experiment_design", None),
    )
    execution = execute_imported_experiment_factory(
        plan,
        summary=payload.summary,
        primary_metric=payload.primary_metric,
        objective_system=payload.objective_system,
        objective_score=payload.objective_score,
        baseline_system=payload.baseline_system,
        baseline_score=payload.baseline_score,
        key_findings=payload.key_findings,
        ablation_scores=payload.ablation_scores,
        seed_count=payload.seed_count,
        significance_p_value=payload.significance_p_value,
        failed_job_ids=payload.failed_job_ids,
        failed_job_kinds=list(payload.failed_job_kinds),
        runtime_failure_notes=payload.runtime_failure_notes,
        notes=payload.notes,
    )
    save_run(
        run.model_copy(
            update={
                "status": "done" if execution.result_artifact.status == "done" else "failed",
                "error": None if execution.result_artifact.status == "done" else execution.result_artifact.summary,
                "experiment_factory_plan": execution.execution_plan,
                "experiment_factory_environment_manifest": execution.environment_manifest,
                "experiment_factory_materialized_jobs": execution.materialized_jobs,
                "artifact": execution.result_artifact,
                "evidence_ledger": execution.evidence_ledger,
                "experiment_factory_repair_plan": execution.repair_plan,
            }
        )
    )
    write_task_audit_log(
        SessionLocal,
        correlation_id=run.id,
        task_name="autoresearch.experiment_factory",
        project_id=project_id,
        action="external_imported",
        status_code=200,
        user_id=identity.user_id if identity else None,
        detail=(
            f"run_id={run.id} jobs={plan.job_count} "
            f"ledger_entries={execution.evidence_ledger.entry_count}"
        ),
    )
    return execution


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


@router.get("/{run_id}/operator/status", response_model=AutoResearchOperatorRunStatusRead)
def get_auto_research_operator_run_status(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AutoResearchOperatorRunStatusRead:
    del db
    try:
        return build_operator_run_status(project_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{run_id}/operator/actions", response_model=AutoResearchOperatorActionResultRead)
def apply_auto_research_operator_action(
    project_id: str,
    run_id: str,
    payload: AutoResearchOperatorActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> AutoResearchOperatorActionResultRead:
    del db
    try:
        result = apply_operator_action(
            project_id,
            run_id,
            payload,
            background_tasks=background_tasks,
            identity_user_id=identity.user_id if identity else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not result.accepted and result.policy_error is not None:
        raise HTTPException(
            status_code=409,
            detail=result.policy_error.model_dump(mode="json"),
        )
    return result


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
        run, repair_execution, applied_action_ids, queued_rerun_required = (
            AutoResearchOrchestrator().apply_review_actions(
                db=db,
                project_id=project_id,
                run_id=run_id,
                expected_round=payload.expected_round,
                expected_review_fingerprint=payload.expected_review_fingerprint,
            )
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
        repair_execution=repair_execution,
        applied_action_ids=applied_action_ids,
        queued_rerun_required=queued_rerun_required,
    )


@router.post("/{run_id}/review-loop/auto-apply", response_model=AutoResearchReviewLoopAutoApplyRead)
def auto_apply_auto_research_review_loop_actions(
    project_id: str,
    run_id: str,
    payload: AutoResearchReviewLoopAutoApplyRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> AutoResearchReviewLoopAutoApplyRead:
    payload = payload or AutoResearchReviewLoopAutoApplyRequest()
    try:
        return AutoResearchOrchestrator().auto_apply_review_loop(
            db=db,
            project_id=project_id,
            run_id=run_id,
            max_rounds=payload.max_rounds,
            expected_review_fingerprint=payload.expected_review_fingerprint,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/{run_id}/research-replan/apply", response_model=AutoResearchResearchReplanApplyRead)
def apply_auto_research_research_replan(
    project_id: str,
    run_id: str,
    payload: AutoResearchReviewLoopApplyRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> AutoResearchResearchReplanApplyRead:
    try:
        (
            run,
            review,
            review_loop,
            repair_execution,
            applied_action_ids,
            queued_rerun_required,
        ) = AutoResearchOrchestrator().apply_research_replan(
            db=db,
            project_id=project_id,
            run_id=run_id,
            expected_review_fingerprint=(
                payload.expected_review_fingerprint
                if payload is not None
                else None
            ),
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return AutoResearchResearchReplanApplyRead(
        run=run,
        review=review,
        review_loop=review_loop,
        repair_execution=repair_execution,
        applied_action_ids=applied_action_ids,
        queued_rerun_required=queued_rerun_required,
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
    try:
        export_result = export_publish_package(
            project_id,
            run_id,
            deployment_id=payload.deployment_id if payload is not None else None,
            deployment_label=payload.deployment_label if payload is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
    if package.archive_ready and archive_path.is_file() and not package.archive_current:
        raise HTTPException(
            status_code=409,
            detail="Publish package export is stale; export again for the current review state",
        )
    if not package.final_publish_ready:
        raise HTTPException(
            status_code=409,
            detail="Auto research run is not final publish ready; export is only available for publish-ready runs",
        )
    if not package.archive_ready or not archive_path.is_file():
        raise HTTPException(status_code=409, detail="Publish package has not been exported yet")
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
    try:
        result = apply_operator_action(
            project_id,
            run_id,
            AutoResearchOperatorActionRequest(action=action),  # type: ignore[arg-type]
            background_tasks=background_tasks,
            identity_user_id=identity.user_id if identity else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if result.policy_error is not None:
        if action == "resume" and bridge_is_waiting_for_result(project_id, run_id):
            raise HTTPException(
                status_code=409,
                detail="Auto research run is waiting for bridge result import before it can resume",
            )
        raise HTTPException(
            status_code=409,
            detail=result.policy_error.model_dump(mode="json"),
        )
    execution = result.execution or AutoResearchExecutionPlane().get_run_execution(project_id, run_id)
    if result.status == "accepted":
        write_task_audit_log(
            SessionLocal,
            correlation_id=run_id,
            task_name="autoresearch.run",
            project_id=project_id,
            action="queued",
            status_code=202,
            user_id=identity.user_id if identity else None,
            detail=f"job_id={result.job_id} action={action}",
        )
    return AutoResearchExecutionCommandResponse(
        run_id=run_id,
        job_id=result.job_id,
        status="accepted" if result.status == "accepted" else "noop",
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> AutoResearchExecutionCommandResponse:
    del db
    try:
        result = apply_operator_action(
            project_id,
            run_id,
            AutoResearchOperatorActionRequest(action="cancel"),
            background_tasks=background_tasks,
            identity_user_id=identity.user_id if identity else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if result.policy_error is not None:
        raise HTTPException(
            status_code=409,
            detail=result.policy_error.model_dump(mode="json"),
        )
    execution = result.execution or AutoResearchExecutionPlane().get_run_execution(project_id, run_id)
    return AutoResearchExecutionCommandResponse(
        run_id=run_id,
        job_id=result.job_id,
        status="accepted" if result.status == "accepted" else "noop",
        execution=execution,
    )
