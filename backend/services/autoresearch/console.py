from __future__ import annotations

from schemas.autoresearch import (
    AutoResearchBudgetStatus,
    AutoResearchExperimentBridgeRead,
    AutoResearchOperatorConsoleRead,
    AutoResearchOperatorConsoleFiltersRead,
    AutoResearchOperatorProjectActionsRead,
    AutoResearchOperatorRunActionsRead,
    AutoResearchOperatorRunDetailRead,
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
    return AutoResearchOperatorRunActionsRead(
        resume=run.status != "done" and not bridge_waiting,
        retry=run.status in {"done", "failed", "canceled"},
        cancel=(active_or_queued and not execution.cancel_requested) or bridge_waiting,
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
                ),
            )

    meta_analysis = build_cross_run_meta_analysis(project_id)
    system_evaluation = build_system_evaluation(project_id)
    return AutoResearchOperatorConsoleRead(
        project_id=project_id,
        run_count=len(runs),
        brief_count=len(briefs),
        latest_brief_id=latest_brief.brief_id if latest_brief is not None else None,
        latest_brief_status=latest_brief.status if latest_brief is not None else None,
        latest_brief_original_idea=latest_brief.original_idea if latest_brief is not None else None,
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
        filtered_run_count=len(filtered_runs),
        latest_run_id=runs[0].id if runs else None,
        selected_run_id=current_run.run.id if current_run is not None else None,
        filters=filters,
        actions=AutoResearchOperatorProjectActionsRead(
            start_run=True,
            create_idea_brief=True,
            create_run_from_brief=True,
            build_meta_analysis=True,
            build_system_evaluation=True,
        ),
        queue=queue_telemetry,
        workers=workers,
        meta_analysis=meta_analysis,
        system_evaluation=system_evaluation,
        runs=summaries,
        current_run=current_run,
    )
