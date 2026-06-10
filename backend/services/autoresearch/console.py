from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schemas.autoresearch import (
    AutoResearchBudgetStatus,
    AutoResearchExperimentBridgeRead,
    AutoResearchOperatorConsoleRead,
    AutoResearchOperatorConsoleFiltersRead,
    AutoResearchOperatorProjectActionsRead,
    AutoResearchOperatorPublicationCaseRead,
    AutoResearchOperatorRunActionsRead,
    AutoResearchOperatorRunDetailRead,
    AutoResearchOperatorRunStatusRead,
    AutoResearchOperatorRunSummaryRead,
    AutoResearchPublicationTier,
    AutoResearchPublishStatus,
    AutoResearchQueuePriority,
    AutoResearchRunStatus,
    AutoResearchRunExecutionRead,
    AutoResearchRunRead,
    AutoResearchUnsupportedClaimRisk,
    AutoResearchNoveltyStatus,
    AutoResearchRunReviewRead,
    AutoResearchReviewLoopRead,
    AutoResearchPublishPackageRead,
)
from services.autoresearch.bridge import build_bridge_state
from services.autoresearch.execution import AutoResearchExecutionPlane
from services.autoresearch.meta_analysis import build_cross_run_meta_analysis
from services.autoresearch.operator_control import (
    build_operator_run_status,
    get_or_build_operator_state_audit,
)
from services.autoresearch.project_paper_orchestrator import build_project_paper_orchestration
from services.autoresearch.publication_repair_plan import (
    repair_plan_allows_paper_pipeline_rebuild,
)
from services.autoresearch.repository import (
    list_research_briefs,
    list_runs,
    load_run,
    load_run_registry,
    load_run_registry_views,
)
from services.autoresearch.review_publish import build_publish_package, build_review_loop, build_run_review
from services.autoresearch.system_evaluation import build_system_evaluation


def _read_json(path: str | None) -> dict:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.is_file():
        return {}
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _benchmark_name(run: AutoResearchRunRead) -> str | None:
    if run.spec is not None and run.spec.benchmark_name:
        return run.spec.benchmark_name
    if run.program is not None and run.program.benchmark_name:
        return run.program.benchmark_name
    return None


def _run_actions(
    *,
    run: AutoResearchRunRead,
    execution: AutoResearchRunExecutionRead,
    bridge: AutoResearchExperimentBridgeRead | None,
    review: AutoResearchRunReviewRead | None,
    review_loop: AutoResearchReviewLoopRead | None,
    publish: AutoResearchPublishPackageRead | None,
    operator_status: AutoResearchOperatorRunStatusRead | None = None,
) -> AutoResearchOperatorRunActionsRead:
    active_or_queued = any(job.status in {"queued", "leased", "running"} for job in execution.jobs)
    bridge_waiting = bool(bridge is not None and bridge.current_session is not None and bridge.current_session.status == "waiting_result")
    final_publish_ready = bool(publish is not None and publish.final_publish_ready)
    repair_plan = review.publication_repair_plan if review is not None else None
    can_rebuild_paper = (
        run.status == "done"
        and repair_plan_allows_paper_pipeline_rebuild(repair_plan)
    )
    can_apply_review_actions = (
        run.status == "done"
        and review_loop is not None
        and review_loop.pending_action_count > 0
        and can_rebuild_paper
    )
    can_replan_research = bool(
        run.status == "done"
        and review is not None
        and (
            (review.research_replan is not None and review.research_replan.action_count > 0)
            or (
                review.reviewer_simulation is not None
                and review.reviewer_simulation.response_plan_action_count > 0
            )
        )
    )
    resume_allowed = (
        operator_status.action_policy["resume"].allowed
        if operator_status is not None and "resume" in operator_status.action_policy
        else run.status != "done" and not bridge_waiting
    )
    retry_allowed = (
        operator_status.action_policy["retry"].allowed
        if operator_status is not None and "retry" in operator_status.action_policy
        else run.status in {"done", "failed", "canceled"}
    )
    cancel_allowed = (
        operator_status.action_policy["cancel"].allowed
        if operator_status is not None and "cancel" in operator_status.action_policy
        else (active_or_queued and not execution.cancel_requested) or bridge_waiting
    )
    return AutoResearchOperatorRunActionsRead(
        resume=resume_allowed,
        retry=retry_allowed,
        cancel=cancel_allowed,
        refresh_bridge=bool(bridge is not None and bridge.enabled),
        import_bridge_result=bridge_waiting,
        refresh_review=run.status == "done",
        apply_review_actions=can_apply_review_actions,
        rebuild_paper=can_rebuild_paper,
        export_publish=run.status == "done" and final_publish_ready,
        download_publish=bool(
            publish is not None
            and publish.final_publish_ready
            and publish.archive_ready
            and publish.archive_current
        ),
        replan_research=can_replan_research,
        update_controls=True,
    )


def _weakest_reviewer_role(review: AutoResearchRunReviewRead | None):
    simulation = review.reviewer_simulation if review is not None else None
    if simulation is None or not simulation.reviews:
        return None
    return min(simulation.reviews, key=lambda item: item.score).role


def _next_research_action(
    *,
    run: AutoResearchRunRead,
    review: AutoResearchRunReviewRead | None,
    publish: AutoResearchPublishPackageRead | None,
) -> tuple[str | None, str | None]:
    if run.status != "done":
        return "wait_for_execution", "Run execution is not complete."
    if review is None:
        return "refresh_review", "Build the research review and publish gates."
    if review.experiment_design is not None and review.experiment_design.blockers:
        return "repair_experiment_design", review.experiment_design.blockers[0]
    if review.research_replan is not None and review.research_replan.rerun_required:
        return "rerun_experiments", "Research replan requires new experiment evidence."
    if review.research_replan is not None and review.research_replan.action_count > 0:
        return "research_replan", review.research_replan.actions[0].title
    if review.reviewer_simulation is not None and review.reviewer_simulation.response_plan:
        action = review.reviewer_simulation.response_plan[0]
        if action.action_kind == "paper":
            return "rebuild_paper", action.title
        if action.action_kind == "research_replan":
            return "research_replan", action.title
        if action.action_kind == "experiment":
            return "rerun_experiments", action.title
        return "repair_experiment_design", action.title
    if publish is not None and publish.final_publish_ready:
        return "export_publish", "Final publish gate is ready."
    if publish is not None and publish.final_blockers:
        return "rebuild_paper", publish.final_blockers[0]
    return "meta_analyze", "Compare this run with related project runs."


def _run_summary(
    *,
    run: AutoResearchRunRead,
    execution: AutoResearchRunExecutionRead,
    bridge: AutoResearchExperimentBridgeRead | None,
    review: AutoResearchRunReviewRead | None,
    review_loop: AutoResearchReviewLoopRead | None,
    publish: AutoResearchPublishPackageRead | None,
) -> AutoResearchOperatorRunSummaryRead:
    registry_views = load_run_registry_views(run.project_id, run.id)
    counts = registry_views.counts if registry_views is not None else None
    latest_job = execution.jobs[-1] if execution.jobs else None
    request = run.request
    candidate_count = counts.total_candidates if counts is not None else len(run.candidates)
    protocol = review.research_protocol if review is not None else None
    benchmark_card = review.benchmark_card if review is not None else None
    methodology_audit = review.methodology_audit if review is not None else None
    revision_dossier = review.revision_dossier if review is not None else None
    publication_evidence_index = (
        review.publication_evidence_index if review is not None else None
    )
    artifact_integrity_audit = (
        review.artifact_integrity_audit if review is not None else None
    )
    publication_repair_plan = (
        review.publication_repair_plan if review is not None else None
    )
    publication_repair_execution = (
        review.publication_repair_execution if review is not None else None
    )
    reviewer_simulation = review.reviewer_simulation if review is not None else None
    contribution_assessment = review.contribution_assessment if review is not None else None
    novelty_validation = review.novelty_validation if review is not None else None
    experiment_design = review.experiment_design if review is not None else None
    readiness = review.publication_readiness if review is not None else None
    audit_checks = methodology_audit.checks if methodology_audit is not None else []
    readiness_checks = readiness.checks if readiness is not None else []
    publication_tier = (
        publish.publication_tier
        if publish is not None
        else readiness.tier
        if readiness is not None
        else None
    )
    publication_readiness_score = (
        publish.publication_readiness_score
        if publish is not None
        else readiness.score
        if readiness is not None
        else 0
    )
    publication_blockers = (
        publish.final_blockers[:3]
        if publish is not None and publish.final_blockers
        else readiness.blockers[:3]
        if readiness is not None
        else []
    )
    publication_blocker_count = (
        publish.final_blocker_count
        if publish is not None
        else len(readiness.blockers)
        if readiness is not None
        else 0
    )
    budget_status = (
        "constrained"
        if request is not None
        and (
            request.candidate_execution_limit is not None
            or request.max_rounds != 3
        )
        else "default"
    )
    next_action, next_action_detail = _next_research_action(
        run=run,
        review=review,
        publish=publish,
    )
    return AutoResearchOperatorRunSummaryRead(
        run_id=run.id,
        topic=run.topic,
        status=run.status,
        created_at=run.created_at,
        updated_at=run.updated_at,
        task_family=run.task_family,
        benchmark_name=_benchmark_name(run),
        selected_candidate_id=run.portfolio.selected_candidate_id if run.portfolio is not None else None,
        candidate_count=candidate_count,
        selected_count=counts.selected if counts is not None else 0,
        active_count=counts.active if counts is not None else 0,
        failed_count=counts.failed if counts is not None else 0,
        eliminated_count=counts.eliminated if counts is not None else 0,
        latest_job_status=latest_job.status if latest_job is not None else None,
        active_job_id=execution.active_job_id,
        cancel_requested=execution.cancel_requested,
        queue_priority=request.queue_priority if request is not None else "normal",
        budget_status=budget_status,
        max_rounds=request.max_rounds if request is not None else 3,
        candidate_execution_limit=request.candidate_execution_limit if request is not None else None,
        execution_profile=request.execution_profile if request is not None else "exploratory",
        executed_candidate_count=len(run.portfolio.executed_candidate_ids) if run.portfolio is not None else 0,
        recovery_count=max((job.recovery_count for job in execution.jobs), default=0),
        bridge_status=bridge.status if bridge is not None and bridge.enabled else None,
        bridge_target_label=(
            bridge.config.target_label
            if bridge is not None and bridge.config is not None
            else None
        ),
        bridge_session_status=bridge.current_session.status if bridge is not None and bridge.current_session is not None else None,
        bridge_session_count=bridge.session_count if bridge is not None else 0,
        review_round=review_loop.current_round if review_loop is not None else 0,
        open_issue_count=review_loop.open_issue_count if review_loop is not None else 0,
        pending_action_count=review_loop.pending_action_count if review_loop is not None else 0,
        completed_action_count=review_loop.completed_action_count if review_loop is not None else 0,
        publish_status=publish.status if publish is not None else None,
        publish_ready=publish.publish_ready if publish is not None else False,
        review_bundle_ready=publish.review_bundle_ready if publish is not None else False,
        final_publish_ready=publish.final_publish_ready if publish is not None else False,
        publication_tier=publication_tier,
        publication_readiness_score=publication_readiness_score,
        research_protocol_complete=protocol.complete if protocol is not None else False,
        research_protocol_blocker_count=len(protocol.blockers) if protocol is not None else 0,
        research_protocol_blockers=protocol.blockers[:3] if protocol is not None else [],
        methodology_audit_score=methodology_audit.score if methodology_audit is not None else 0,
        methodology_audit_compliant=methodology_audit.compliant if methodology_audit is not None else False,
        methodology_audit_blocker_count=len(methodology_audit.blockers) if methodology_audit is not None else 0,
        methodology_audit_blockers=methodology_audit.blockers[:3] if methodology_audit is not None else [],
        methodology_audit_checks_passed=sum(1 for item in audit_checks if item.passed),
        methodology_audit_checks_total=len(audit_checks),
        revision_dossier_complete=revision_dossier.complete if revision_dossier is not None else False,
        revision_dossier_blocker_count=(
            revision_dossier.final_blocker_count if revision_dossier is not None else 0
        ),
        revision_dossier_required_actions=(
            revision_dossier.required_action_titles[:3] if revision_dossier is not None else []
        ),
        benchmark_card_publication_grade=(
            benchmark_card.publication_grade if benchmark_card is not None else False
        ),
        benchmark_card_provenance_complete=(
            benchmark_card.provenance_complete if benchmark_card is not None else False
        ),
        benchmark_card_total_examples=(
            benchmark_card.total_examples if benchmark_card is not None else 0
        ),
        benchmark_card_blocker_count=(
            len(benchmark_card.blockers) if benchmark_card is not None else 0
        ),
        benchmark_card_blockers=(
            benchmark_card.blockers[:3] if benchmark_card is not None else []
        ),
        publication_evidence_index_complete=(
            publication_evidence_index.complete
            if publication_evidence_index is not None
            else False
        ),
        publication_evidence_index_missing_count=(
            publication_evidence_index.missing_required_evidence_count
            if publication_evidence_index is not None
            else 0
        ),
        publication_evidence_index_blockers=(
            publication_evidence_index.blockers[:3]
            if publication_evidence_index is not None
            else []
        ),
        reviewer_simulation_complete=(
            reviewer_simulation.complete if reviewer_simulation is not None else False
        ),
        reviewer_simulation_average_score=(
            reviewer_simulation.average_score if reviewer_simulation is not None else 0.0
        ),
        reviewer_simulation_minimum_score=(
            reviewer_simulation.minimum_score if reviewer_simulation is not None else 0
        ),
        reviewer_simulation_minimum_decision=(
            reviewer_simulation.minimum_decision if reviewer_simulation is not None else None
        ),
        reviewer_simulation_weak_reject_or_worse_count=(
            reviewer_simulation.weak_reject_or_worse_count if reviewer_simulation is not None else 0
        ),
        reviewer_simulation_publication_blocker_count=(
            reviewer_simulation.publication_blocker_count if reviewer_simulation is not None else 0
        ),
        reviewer_simulation_response_plan_action_count=(
            reviewer_simulation.response_plan_action_count if reviewer_simulation is not None else 0
        ),
        reviewer_simulation_blockers=(
            reviewer_simulation.blockers[:3] if reviewer_simulation is not None else []
        ),
        weakest_reviewer_role=_weakest_reviewer_role(review),
        contribution_score=(
            contribution_assessment.publishability_score if contribution_assessment is not None else 0
        ),
        novelty_duplicate_risk=(
            novelty_validation.duplicate_risk if novelty_validation is not None else None
        ),
        novelty_incremental_risk=(
            novelty_validation.incremental_risk if novelty_validation is not None else None
        ),
        experiment_design_completeness=(
            experiment_design.completeness if experiment_design is not None else None
        ),
        next_research_action=next_action,
        next_research_action_detail=next_action_detail,
        artifact_integrity_audit_complete=(
            artifact_integrity_audit.complete
            if artifact_integrity_audit is not None
            else False
        ),
        artifact_integrity_audit_blocker_count=(
            artifact_integrity_audit.blocker_count
            if artifact_integrity_audit is not None
            else 0
        ),
        artifact_integrity_audit_warning_count=(
            artifact_integrity_audit.warning_count
            if artifact_integrity_audit is not None
            else 0
        ),
        artifact_integrity_audit_untraced_asset_count=(
            artifact_integrity_audit.untraced_existing_asset_count
            if artifact_integrity_audit is not None
            else 0
        ),
        artifact_integrity_audit_missing_lineage_target_count=(
            artifact_integrity_audit.missing_lineage_target_count
            if artifact_integrity_audit is not None
            else 0
        ),
        artifact_integrity_audit_blockers=(
            artifact_integrity_audit.blockers[:3]
            if artifact_integrity_audit is not None
            else []
        ),
        publication_repair_plan_complete=(
            publication_repair_plan.complete
            if publication_repair_plan is not None
            else False
        ),
        publication_repair_plan_pending_count=(
            publication_repair_plan.pending_action_count
            if publication_repair_plan is not None
            else 0
        ),
        publication_repair_plan_blocked_count=(
            publication_repair_plan.blocked_action_count
            if publication_repair_plan is not None
            else 0
        ),
        publication_repair_plan_auto_applicable_count=(
            publication_repair_plan.auto_applicable_action_count
            if publication_repair_plan is not None
            else 0
        ),
        publication_repair_plan_next_actions=(
            [
                item.title
                for item in publication_repair_plan.actions
                if item.action_id in set(publication_repair_plan.next_action_ids)
            ][:3]
            if publication_repair_plan is not None
            else []
        ),
        publication_repair_execution_success=(
            publication_repair_execution.success
            if publication_repair_execution is not None
            else False
        ),
        publication_repair_execution_attempted_count=(
            publication_repair_execution.attempted_action_count
            if publication_repair_execution is not None
            else 0
        ),
        publication_repair_execution_executed_count=(
            publication_repair_execution.executed_action_count
            if publication_repair_execution is not None
            else 0
        ),
        publication_repair_execution_partial_count=(
            publication_repair_execution.partial_action_count
            if publication_repair_execution is not None
            else 0
        ),
        publication_repair_execution_blocked_count=(
            publication_repair_execution.blocked_action_count
            if publication_repair_execution is not None
            else 0
        ),
        publication_repair_execution_missing_outputs=(
            publication_repair_execution.missing_output_asset_ids[:3]
            if publication_repair_execution is not None
            else []
        ),
        publication_grade_benchmark=(
            readiness.publication_grade_benchmark
            if readiness is not None
            else False
        ),
        publication_blocker_count=publication_blocker_count,
        publication_blockers=publication_blockers,
        readiness_checks_passed=sum(1 for item in readiness_checks if item.passed),
        readiness_checks_total=len(readiness_checks),
        archive_ready=publish.archive_ready if publish is not None else False,
        review_risk=review.unsupported_claim_risk if review is not None else None,
        novelty_status=review.novelty_assessment.status if review is not None and review.novelty_assessment is not None else None,
        blocker_count=publish.blocker_count if publish is not None else 0,
        final_blocker_count=publish.final_blocker_count if publish is not None else 0,
        revision_count=publish.revision_count if publish is not None else 0,
        revision_actions=publish.revision_actions[:3] if publish is not None else [],
    )


def _matches_search(run: AutoResearchRunRead, query: str | None) -> bool:
    if not query:
        return True
    lowered = query.strip().lower()
    if not lowered:
        return True
    benchmark_name = _benchmark_name(run)
    task_family = run.task_family
    return any(
        lowered in value.lower()
        for value in [run.id, run.topic, benchmark_name, task_family]
        if value
    )


def _matches_filters(
    *,
    run: AutoResearchRunRead,
    review: AutoResearchRunReviewRead | None,
    publish: AutoResearchPublishPackageRead | None,
    filters: AutoResearchOperatorConsoleFiltersRead,
) -> bool:
    if not _matches_search(run, filters.search):
        return False
    if filters.status is not None and run.status != filters.status:
        return False
    if filters.publish_status is not None:
        if publish is None or publish.status != filters.publish_status:
            return False
    if filters.publication_tier is not None:
        readiness = review.publication_readiness if review is not None else None
        publication_tier = (
            publish.publication_tier
            if publish is not None
            else readiness.tier
            if readiness is not None
            else None
        )
        if publication_tier != filters.publication_tier:
            return False
    if filters.review_risk is not None:
        if review is None or review.unsupported_claim_risk != filters.review_risk:
            return False
    if filters.novelty_status is not None:
        novelty_status = review.novelty_assessment.status if review is not None and review.novelty_assessment is not None else None
        if novelty_status != filters.novelty_status:
            return False
    if filters.budget_status is not None:
        request = run.request
        budget_status = (
            "constrained"
            if request is not None
            and (
                request.candidate_execution_limit is not None
                or request.max_rounds != 3
            )
            else "default"
        )
        if budget_status != filters.budget_status:
            return False
    if filters.queue_priority is not None:
        queue_priority = run.request.queue_priority if run.request is not None else "normal"
        if queue_priority != filters.queue_priority:
            return False
    return True


def _publication_case_summary(project_id: str) -> AutoResearchOperatorPublicationCaseRead | None:
    project_paper = build_project_paper_orchestration(project_id)
    if project_paper.project_submission_manifest_path is None:
        return None
    submission_manifest = _read_json(project_paper.project_submission_manifest_path)
    readiness_report = _read_json(project_paper.project_publication_readiness_report_path)
    statistics_report = _read_json(project_paper.project_statistics_report_path)
    negative_evidence_report = _read_json(project_paper.project_negative_evidence_report_path)
    experiment_repair_index = _read_json(project_paper.project_experiment_repair_index_path)
    repair_execution_log = _read_json(project_paper.project_repair_execution_log_path)
    review_findings = _read_json(project_paper.project_review_findings_path)
    rereview_report = _read_json(project_paper.project_revision_rereview_path)
    offline_audit = _read_json(project_paper.project_offline_publication_audit_path)
    evidence_profile = readiness_report.get("evidence_profile", {})
    final_publish_gap_audit = offline_audit.get("final_publish_gap_audit", {})
    if not isinstance(final_publish_gap_audit, dict):
        final_publish_gap_audit = {}
    benchmark_schema_coverage = readiness_report.get("benchmark_schema_coverage", {})
    if not isinstance(benchmark_schema_coverage, dict):
        benchmark_schema_coverage = {}
    benchmark_source_observation_coverage = readiness_report.get(
        "benchmark_source_observation_coverage", {}
    )
    if not isinstance(benchmark_source_observation_coverage, dict):
        benchmark_source_observation_coverage = {}
    benchmark_source_independence_audit = readiness_report.get(
        "benchmark_source_independence_audit", {}
    )
    if not isinstance(benchmark_source_independence_audit, dict):
        benchmark_source_independence_audit = {}
    if not benchmark_source_independence_audit:
        fallback_source_independence_audit = final_publish_gap_audit.get(
            "benchmark_source_independence_audit", {}
        )
        benchmark_source_independence_audit = (
            fallback_source_independence_audit
            if isinstance(fallback_source_independence_audit, dict)
            else {}
        )
    generated_assets = [
        item
        for item in submission_manifest.get("generated_assets", [])
        if isinstance(item, dict)
    ]
    archive_manifest = (
        project_paper.project_submission_archive_manifest.model_dump(mode="json")
        if project_paper.project_submission_archive_manifest is not None
        else _read_json(project_paper.project_submission_archive_manifest_path)
    )
    reproducibility_checklist = (
        project_paper.project_reproducibility_checklist.model_dump(mode="json")
        if project_paper.project_reproducibility_checklist is not None
        else _read_json(project_paper.project_reproducibility_checklist_json_path)
    )
    artifact_integrity_audit = (
        project_paper.project_artifact_integrity_audit.model_dump(mode="json")
        if project_paper.project_artifact_integrity_audit is not None
        else _read_json(project_paper.project_artifact_integrity_audit_path)
    )
    final_publish_decision = (
        project_paper.project_final_publish_decision.model_dump(mode="json")
        if project_paper.project_final_publish_decision is not None
        else _read_json(project_paper.project_final_publish_decision_path)
    )
    final_publish_failed_check_ids = [
        str(item.get("check_id"))
        for item in final_publish_decision.get("failed_checks", [])
        if isinstance(item, dict) and item.get("check_id")
    ]
    asset_statuses = [
        {
            "role": item.get("role"),
            "path": item.get("path"),
            "missing_status": item.get("missing_status"),
            "blocked_status": item.get("blocked_status"),
            "final_publish_blocking": item.get("final_publish_blocking"),
            "blocking_check_ids": item.get("blocking_check_ids", []),
            "blocking_reasons": item.get("blocking_reasons", []),
            "readiness_contribution": item.get("readiness_contribution"),
            "source_action": item.get("source_action"),
        }
        for item in generated_assets
    ]
    blocked_asset_roles = [
        str(item.get("role"))
        for item in generated_assets
        if item.get("final_publish_blocking") and item.get("role") is not None
    ]
    repair_status_counts: dict[str, int] = {}
    for entry in repair_execution_log.get("entries", []):
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "unknown")
        repair_status_counts[status] = repair_status_counts.get(status, 0) + 1
    final_publish_ready = bool(project_paper.project_final_publish_ready)
    review_bundle_ready = bool(project_paper.project_review_bundle_ready)
    status = (
        "final_publish_ready"
        if final_publish_ready
        else "review_ready"
        if review_bundle_ready
        else "blocked"
        if project_paper.project_submission_blockers
        else "not_started"
    )
    return AutoResearchOperatorPublicationCaseRead(
        status=status,
        domain_decision=project_paper.latest_brief_domain_decision,
        domain_template=project_paper.latest_brief_domain_template,
        domain_literature_strategy=project_paper.latest_brief_domain_literature_strategy,
        domain_literature_result=project_paper.latest_brief_domain_literature_result,
        domain_benchmark_resolver=project_paper.latest_brief_domain_benchmark_resolver,
        domain_experiment_protocol=project_paper.latest_brief_domain_experiment_protocol,
        domain_readiness_status=project_paper.latest_brief_domain_readiness_status,
        domain_claim_ceiling=project_paper.latest_brief_domain_claim_ceiling,
        review_bundle_ready=review_bundle_ready,
        final_publish_ready=final_publish_ready,
        submission_bundle_kind=project_paper.project_submission_manifest.get("bundle_kind")
        if project_paper.project_submission_manifest is not None
        else submission_manifest.get("bundle_kind"),
        submission_asset_count=project_paper.project_submission_asset_count,
        missing_asset_roles=[
            item.get("role")
            for item in generated_assets
            if item.get("missing_status") != "present" and item.get("role") is not None
        ],
        blocked_asset_count=int(submission_manifest.get("blocked_asset_count") or len(blocked_asset_roles)),
        blocked_asset_roles=blocked_asset_roles,
        final_publish_blocking_asset_roles=list(
            submission_manifest.get("final_publish_blocking_asset_roles", blocked_asset_roles)
        ),
        package_asset_statuses=asset_statuses,
        submission_archive_manifest_path=project_paper.project_submission_archive_manifest_path,
        submission_archive_path=project_paper.project_submission_archive_path,
        submission_archive_complete=bool(archive_manifest.get("complete")),
        submission_archive_current=bool(archive_manifest.get("current")),
        submission_archive_ready_for_final_download=bool(
            archive_manifest.get("ready_for_final_download")
        ),
        submission_archive_entry_count=int(archive_manifest.get("entry_count") or 0),
        submission_archive_missing_required_entry_count=int(
            archive_manifest.get("missing_required_entry_count") or 0
        ),
        submission_archive_hash_mismatch_entry_count=int(
            archive_manifest.get("hash_mismatch_entry_count") or 0
        ),
        submission_archive_stale_entry_count=int(
            archive_manifest.get("stale_entry_count") or 0
        ),
        reproducibility_checklist_json_path=project_paper.project_reproducibility_checklist_json_path,
        reproducibility_checklist_complete=bool(reproducibility_checklist.get("complete")),
        reproducibility_checklist_missing_required_count=int(
            reproducibility_checklist.get("missing_required_count") or 0
        ),
        reproducibility_checklist_partial_required_count=int(
            reproducibility_checklist.get("partial_required_count") or 0
        ),
        artifact_integrity_audit_path=project_paper.project_artifact_integrity_audit_path,
        artifact_integrity_audit_complete=bool(artifact_integrity_audit.get("complete")),
        artifact_integrity_unresolved_issue_count=int(
            artifact_integrity_audit.get("unresolved_issue_count") or 0
        ),
        final_publish_decision_path=project_paper.project_final_publish_decision_path,
        final_publish_policy_version=(
            str(final_publish_decision.get("policy_version"))
            if final_publish_decision.get("policy_version") is not None
            else None
        ),
        final_publish_failed_check_ids=final_publish_failed_check_ids,
        repair_action_status_counts=repair_status_counts,
        repair_action_recommendations={
            str(key): str(value)
            for key, value in rereview_report.get("recommendations", {}).items()
        },
        review_finding_count=int(review_findings.get("finding_count") or 0),
        review_findings_path=project_paper.project_review_findings_path,
        execution_source_counts={
            str(key): int(value)
            for key, value in experiment_repair_index.get("execution_source_counts", {}).items()
        },
        imported_replay_run_ids=list(experiment_repair_index.get("imported_result_replay_run_ids", [])),
        materialized_execution_run_ids=list(experiment_repair_index.get("materialized_execution_run_ids", [])),
        literature_source_counts={
            str(key): int(value)
            for key, value in evidence_profile.get("literature_source_counts", {}).items()
        },
        real_literature_count=int(evidence_profile.get("real_literature_count") or 0),
        benchmark_provenance_ready=bool(evidence_profile.get("benchmark_provenance_ready")),
        benchmark_publication_ready=bool(evidence_profile.get("benchmark_publication_ready")),
        statistics_claim_ceiling=statistics_report.get("claim_ceiling_recommendation"),
        statistics_complete=bool(statistics_report.get("complete")),
        negative_evidence_count=int(negative_evidence_report.get("entry_count") or 0),
        negative_evidence_blocking_count=int(
            negative_evidence_report.get("blocking_entry_count") or 0
        ),
        phase6_negative_evidence_categories=_string_list(
            negative_evidence_report.get("phase6_categories")
        ),
        phase6_negative_evidence_missing_categories=_string_list(
            negative_evidence_report.get("phase6_missing_categories")
        ),
        phase6_negative_evidence_required_categories=_string_list(
            negative_evidence_report.get("phase6_required_categories")
        ),
        phase6_negative_evidence_coverage_complete=bool(
            negative_evidence_report.get("phase6_coverage_complete")
        ),
        phase6_negative_evidence_runtime_failure_observed=bool(
            negative_evidence_report.get("phase6_runtime_failure_observed")
        ),
        final_publish_package_artifacts_complete=bool(
            final_publish_gap_audit.get("package_artifacts_complete")
        ),
        final_publish_engineering_gap_count=int(
            final_publish_gap_audit.get("engineering_gap_count") or 0
        ),
        final_publish_scientific_evidence_gap_count=int(
            final_publish_gap_audit.get("scientific_evidence_gap_count") or 0
        ),
        final_publish_engineering_gaps=_dict_list(
            final_publish_gap_audit.get("engineering_gaps")
        ),
        final_publish_scientific_evidence_gaps=_dict_list(
            final_publish_gap_audit.get("scientific_evidence_gaps")
        ),
        final_publish_blocker_classification=_dict_list(
            final_publish_gap_audit.get("final_publish_blocker_classification")
        ),
        final_publish_phase1_blocked_requirement_ids=_string_list(
            final_publish_gap_audit.get("phase1_blocked_requirement_ids")
        ),
        benchmark_schema_coverage_complete=bool(
            benchmark_schema_coverage.get("schema_coverage_complete")
        ),
        benchmark_schema_coverage_blockers=_string_list(
            benchmark_schema_coverage.get("schema_blockers")
        ),
        benchmark_source_observation_coverage_complete=bool(
            benchmark_source_observation_coverage.get("observation_coverage_complete")
        ),
        benchmark_source_observation_blockers=_string_list(
            benchmark_source_observation_coverage.get("observation_blockers")
        ),
        benchmark_final_publish_candidate_coverage_complete=bool(
            final_publish_gap_audit.get("benchmark_final_publish_candidate_coverage_complete")
        ),
        benchmark_final_publish_candidate_blockers=_string_list(
            final_publish_gap_audit.get("benchmark_final_publish_candidate_blockers")
        ),
        benchmark_source_independence_ready=bool(
            final_publish_gap_audit.get(
                "benchmark_source_independence_ready",
                benchmark_source_independence_audit.get("complete"),
            )
        ),
        benchmark_source_independence_blockers=_string_list(
            final_publish_gap_audit.get(
                "benchmark_source_independence_blockers",
                benchmark_source_independence_audit.get("blockers"),
            )
        ),
        benchmark_snapshot_artifact_materialized=bool(
            final_publish_gap_audit.get("benchmark_snapshot_artifact_materialized")
        ),
        benchmark_snapshot_artifact_record_count=int(
            final_publish_gap_audit.get("benchmark_snapshot_artifact_record_count") or 0
        ),
        benchmark_snapshot_artifact_materialized_count=int(
            final_publish_gap_audit.get("benchmark_snapshot_artifact_materialized_count")
            or 0
        ),
        benchmark_snapshot_artifact_all_required_materialized=bool(
            final_publish_gap_audit.get(
                "benchmark_snapshot_artifact_all_required_materialized"
            )
        ),
        benchmark_snapshot_artifact_unmaterialized_run_ids=_string_list(
            final_publish_gap_audit.get(
                "benchmark_snapshot_artifact_unmaterialized_run_ids"
            )
        ),
        rereview_complete=bool(rereview_report.get("rereview_complete")),
        rereview_recommendations={
            str(key): str(value)
            for key, value in rereview_report.get("recommendations", {}).items()
        },
        publish_blockers=list(project_paper.project_submission_blockers),
        required_followups=list(readiness_report.get("required_followups", [])),
        kill_criteria=list(readiness_report.get("kill_criteria", [])),
        offline_publication_case_path=project_paper.project_offline_publication_case_path,
        offline_publication_audit_path=project_paper.project_offline_publication_audit_path,
        submission_manifest_path=project_paper.project_submission_manifest_path,
        publication_readiness_report_path=project_paper.project_publication_readiness_report_path,
        statistics_report_path=project_paper.project_statistics_report_path,
        negative_evidence_report_path=project_paper.project_negative_evidence_report_path,
    )


def build_operator_console(
    project_id: str,
    *,
    run_id: str | None = None,
    search: str | None = None,
    status: AutoResearchRunStatus | None = None,
    publish_status: AutoResearchPublishStatus | None = None,
    publication_tier: AutoResearchPublicationTier | None = None,
    review_risk: AutoResearchUnsupportedClaimRisk | None = None,
    novelty_status: AutoResearchNoveltyStatus | None = None,
    budget_status: AutoResearchBudgetStatus | None = None,
    queue_priority: AutoResearchQueuePriority | None = None,
) -> AutoResearchOperatorConsoleRead:
    runs = list_runs(project_id)
    briefs = list_research_briefs(project_id)
    latest_brief = briefs[0] if briefs else None
    filters = AutoResearchOperatorConsoleFiltersRead(
        search=search.strip() if search and search.strip() else None,
        status=status,
        publish_status=publish_status,
        publication_tier=publication_tier,
        review_risk=review_risk,
        novelty_status=novelty_status,
        budget_status=budget_status,
        queue_priority=queue_priority,
    )
    execution_plane = AutoResearchExecutionPlane()
    queue_telemetry, workers = execution_plane.get_queue_snapshot()
    summaries: list[AutoResearchOperatorRunSummaryRead] = []
    execution_by_run: dict[str, AutoResearchRunExecutionRead] = {}
    filtered_runs: list[AutoResearchRunRead] = []
    bridge_by_run: dict[str, AutoResearchExperimentBridgeRead | None] = {}
    review_by_run: dict[str, AutoResearchRunReviewRead | None] = {}
    review_loop_by_run: dict[str, AutoResearchReviewLoopRead | None] = {}
    publish_by_run: dict[str, AutoResearchPublishPackageRead | None] = {}

    for run in runs:
        execution = execution_plane.get_run_execution(project_id, run.id)
        execution_by_run[run.id] = execution
        bridge = build_bridge_state(run.project_id, run.id)
        bridge_by_run[run.id] = bridge
        review = build_run_review(run.project_id, run.id) if run.status == "done" else None
        review_loop = build_review_loop(run.project_id, run.id) if run.status == "done" else None
        publish = build_publish_package(run.project_id, run.id) if run.status == "done" else None
        review_by_run[run.id] = review
        review_loop_by_run[run.id] = review_loop
        publish_by_run[run.id] = publish
        if not _matches_filters(run=run, review=review, publish=publish, filters=filters):
            continue
        filtered_runs.append(run)
        summaries.append(
            _run_summary(
                run=run,
                execution=execution,
                bridge=bridge,
                review=review,
                review_loop=review_loop,
                publish=publish,
            )
        )

    selected_run = next((item for item in filtered_runs if item.id == run_id), None) if run_id else None
    if selected_run is None and filtered_runs:
        selected_run = filtered_runs[0]

    current_run = None
    if selected_run is not None:
        latest_run = load_run(project_id, selected_run.id)
        if latest_run is not None:
            selected_run = latest_run
        execution = execution_by_run[selected_run.id]
        registry = load_run_registry(project_id, selected_run.id)
        registry_views = load_run_registry_views(project_id, selected_run.id)
        if registry is not None and registry_views is not None:
            bridge = bridge_by_run[selected_run.id]
            review = review_by_run[selected_run.id]
            review_loop = review_loop_by_run[selected_run.id]
            publish = publish_by_run[selected_run.id]
            operator_status = build_operator_run_status(project_id, selected_run.id)
            current_run = AutoResearchOperatorRunDetailRead(
                run=selected_run,
                execution=execution,
                bridge=bridge,
                registry=registry,
                registry_views=registry_views,
                review=review,
                review_loop=review_loop,
                publish=publish,
                actions=_run_actions(
                    run=selected_run,
                    execution=execution,
                    bridge=bridge,
                    review=review,
                    review_loop=review_loop,
                    publish=publish,
                    operator_status=operator_status,
                ),
                operator_status=operator_status,
            )

    meta_analysis = build_cross_run_meta_analysis(project_id)
    system_evaluation = build_system_evaluation(project_id)
    publication_case = _publication_case_summary(project_id) if runs else None
    operator_audit = get_or_build_operator_state_audit(project_id) if runs else None
    latest_domain_decision = (
        latest_brief.domain_decision if latest_brief is not None else None
    )
    return AutoResearchOperatorConsoleRead(
        project_id=project_id,
        run_count=len(runs),
        brief_count=len(briefs),
        latest_brief_id=latest_brief.brief_id if latest_brief is not None else None,
        latest_brief_status=latest_brief.status if latest_brief is not None else None,
        latest_brief_original_idea=latest_brief.original_idea if latest_brief is not None else None,
        latest_brief_domain_id=(
            latest_domain_decision.domain_id if latest_domain_decision is not None else None
        ),
        latest_brief_domain_label=(
            latest_domain_decision.domain_label if latest_domain_decision is not None else None
        ),
        latest_brief_domain_confidence=(
            latest_domain_decision.confidence if latest_domain_decision is not None else 0.0
        ),
        latest_brief_domain_supported=bool(
            latest_domain_decision is not None and latest_domain_decision.is_supported
        ),
        latest_brief_domain_blockers=(
            latest_brief.domain_blockers if latest_brief is not None else []
        ),
        latest_brief_domain_literature_status=(
            latest_brief.domain_literature_result.status
            if latest_brief is not None and latest_brief.domain_literature_result is not None
            else "blocked"
        ),
        latest_brief_domain_benchmark_status=(
            latest_brief.domain_benchmark_resolver.status
            if latest_brief is not None and latest_brief.domain_benchmark_resolver is not None
            else "blocked"
        ),
        latest_brief_domain_protocol_status=(
            latest_brief.domain_experiment_protocol.status
            if latest_brief is not None and latest_brief.domain_experiment_protocol is not None
            else "blocked"
        ),
        latest_brief_domain_claim_ceiling=(
            latest_brief.domain_claim_ceiling if latest_brief is not None else None
        ),
        latest_brief_domain_required_followups=(
            list(latest_brief.domain_required_followups) if latest_brief is not None else []
        ),
        latest_brief_domain_kill_criteria=(
            list(latest_brief.domain_kill_criteria) if latest_brief is not None else []
        ),
        latest_brief_hypothesis_count=(
            latest_brief.hypothesis_count if latest_brief is not None else 0
        ),
        latest_brief_selected_direction_id=(
            latest_brief.selected_direction_id if latest_brief is not None else None
        ),
        latest_brief_selected_hypothesis_id=(
            latest_brief.selected_hypothesis_id if latest_brief is not None else None
        ),
        latest_brief_next_action=latest_brief.next_action if latest_brief is not None else None,
        latest_brief_literature_scout_ready=bool(
            latest_brief is not None and latest_brief.literature_scout is not None
        ),
        latest_brief_gap_count=(
            len(latest_brief.gap_miner.gap_candidates)
            if latest_brief is not None and latest_brief.gap_miner is not None
            else 0
        ),
        latest_brief_recommended_gap=(
            latest_brief.gap_miner.recommended_narrower_gap
            if latest_brief is not None and latest_brief.gap_miner is not None
            else None
        ),
        filtered_run_count=len(filtered_runs),
        latest_run_id=runs[0].id if runs else None,
        selected_run_id=current_run.run.id if current_run is not None else None,
        filters=filters,
        actions=AutoResearchOperatorProjectActionsRead(
            start_run=True,
            create_idea_brief=True,
            create_run_from_brief=bool(
                latest_brief is not None
                and latest_brief.next_action == "create_run"
                and latest_brief.allow_experiments
                and latest_brief.selected_hypothesis_id
            ),
            build_meta_analysis=True,
            build_system_evaluation=True,
        ),
        queue=queue_telemetry,
        workers=workers,
        meta_analysis=meta_analysis,
        system_evaluation=system_evaluation,
        publication_case=publication_case,
        operator_audit=operator_audit,
        runs=summaries,
        current_run=current_run,
    )
