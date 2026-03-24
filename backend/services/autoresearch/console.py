from __future__ import annotations

from schemas.autoresearch import (
    AutoResearchBudgetStatus,
    AutoResearchOperatorConsoleRead,
    AutoResearchOperatorConsoleFiltersRead,
    AutoResearchOperatorProjectActionsRead,
    AutoResearchOperatorRunActionsRead,
    AutoResearchOperatorRunDetailRead,
    AutoResearchOperatorRunSummaryRead,
    AutoResearchPublishStatus,
    AutoResearchQueuePriority,
    AutoResearchRunStatus,
    AutoResearchRunExecutionRead,
    AutoResearchRunRead,
    AutoResearchUnsupportedClaimRisk,
    AutoResearchNoveltyStatus,
    AutoResearchRunReviewRead,
    AutoResearchPublishPackageRead,
)
from services.autoresearch.execution import AutoResearchExecutionPlane
from services.autoresearch.repository import list_runs, load_run_registry, load_run_registry_views
from services.autoresearch.review_publish import build_publish_package, build_run_review, get_publish_archive_path


def _run_actions(
    *,
    run: AutoResearchRunRead,
    execution: AutoResearchRunExecutionRead,
    has_publish_archive: bool,
) -> AutoResearchOperatorRunActionsRead:
    active_or_queued = any(job.status in {"queued", "leased", "running"} for job in execution.jobs)
    return AutoResearchOperatorRunActionsRead(
        resume=run.status != "done",
        retry=run.status in {"done", "failed", "canceled"},
        cancel=active_or_queued and not execution.cancel_requested,
        rebuild_paper=run.status == "done",
        export_publish=run.status == "done",
        download_publish=has_publish_archive,
        update_controls=True,
    )


def _run_summary(
    *,
    run: AutoResearchRunRead,
    execution: AutoResearchRunExecutionRead,
    review: AutoResearchRunReviewRead | None,
    publish: AutoResearchPublishPackageRead | None,
) -> AutoResearchOperatorRunSummaryRead:
    registry_views = load_run_registry_views(run.project_id, run.id)
    counts = registry_views.counts if registry_views is not None else None
    latest_job = execution.jobs[-1] if execution.jobs else None
    request = run.request
    candidate_count = counts.total_candidates if counts is not None else len(run.candidates)
    budget_status = (
        "constrained"
        if request is not None
        and (
            request.candidate_execution_limit is not None
            or request.max_rounds != 3
        )
        else "default"
    )
    return AutoResearchOperatorRunSummaryRead(
        run_id=run.id,
        topic=run.topic,
        status=run.status,
        created_at=run.created_at,
        updated_at=run.updated_at,
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
        executed_candidate_count=len(run.portfolio.executed_candidate_ids) if run.portfolio is not None else 0,
        recovery_count=max((job.recovery_count for job in execution.jobs), default=0),
        publish_status=publish.status if publish is not None else None,
        publish_ready=publish.publish_ready if publish is not None else False,
        review_risk=review.unsupported_claim_risk if review is not None else None,
        novelty_status=review.novelty_assessment.status if review is not None and review.novelty_assessment is not None else None,
        blocker_count=publish.blocker_count if publish is not None else 0,
        revision_count=publish.revision_count if publish is not None else 0,
    )


def _matches_search(run: AutoResearchRunRead, query: str | None) -> bool:
    if not query:
        return True
    lowered = query.strip().lower()
    if not lowered:
        return True
    return lowered in run.id.lower() or lowered in run.topic.lower()


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
    review_risk: AutoResearchUnsupportedClaimRisk | None = None,
    novelty_status: AutoResearchNoveltyStatus | None = None,
    budget_status: AutoResearchBudgetStatus | None = None,
    queue_priority: AutoResearchQueuePriority | None = None,
) -> AutoResearchOperatorConsoleRead:
    runs = list_runs(project_id)
    filters = AutoResearchOperatorConsoleFiltersRead(
        search=search.strip() if search and search.strip() else None,
        status=status,
        publish_status=publish_status,
        review_risk=review_risk,
        novelty_status=novelty_status,
        budget_status=budget_status,
        queue_priority=queue_priority,
    )
    execution_plane = AutoResearchExecutionPlane()
    summaries: list[AutoResearchOperatorRunSummaryRead] = []
    execution_by_run: dict[str, AutoResearchRunExecutionRead] = {}
    filtered_runs: list[AutoResearchRunRead] = []
    review_by_run: dict[str, AutoResearchRunReviewRead | None] = {}
    publish_by_run: dict[str, AutoResearchPublishPackageRead | None] = {}

    for run in runs:
        execution = execution_plane.get_run_execution(project_id, run.id)
        execution_by_run[run.id] = execution
        review = build_run_review(run.project_id, run.id) if run.status == "done" else None
        publish = build_publish_package(run.project_id, run.id) if run.status == "done" else None
        review_by_run[run.id] = review
        publish_by_run[run.id] = publish
        if not _matches_filters(run=run, review=review, publish=publish, filters=filters):
            continue
        filtered_runs.append(run)
        summaries.append(
            _run_summary(
                run=run,
                execution=execution,
                review=review,
                publish=publish,
            )
        )

    selected_run = next((item for item in filtered_runs if item.id == run_id), None) if run_id else None
    if selected_run is None and filtered_runs:
        selected_run = filtered_runs[0]

    current_run = None
    if selected_run is not None:
        execution = execution_by_run[selected_run.id]
        registry = load_run_registry(project_id, selected_run.id)
        registry_views = load_run_registry_views(project_id, selected_run.id)
        if registry is not None and registry_views is not None:
            review = review_by_run[selected_run.id]
            publish = publish_by_run[selected_run.id]
            has_publish_archive = get_publish_archive_path(project_id, selected_run.id).is_file()
            current_run = AutoResearchOperatorRunDetailRead(
                run=selected_run,
                execution=execution,
                registry=registry,
                registry_views=registry_views,
                review=review,
                publish=publish,
                actions=_run_actions(
                    run=selected_run,
                    execution=execution,
                    has_publish_archive=has_publish_archive,
                ),
            )

    return AutoResearchOperatorConsoleRead(
        project_id=project_id,
        run_count=len(runs),
        filtered_run_count=len(filtered_runs),
        latest_run_id=runs[0].id if runs else None,
        selected_run_id=current_run.run.id if current_run is not None else None,
        filters=filters,
        actions=AutoResearchOperatorProjectActionsRead(start_run=True),
        runs=summaries,
        current_run=current_run,
    )
