from __future__ import annotations

from schemas.autoresearch import (
    AutoResearchOperatorConsoleRead,
    AutoResearchOperatorProjectActionsRead,
    AutoResearchOperatorRunActionsRead,
    AutoResearchOperatorRunDetailRead,
    AutoResearchOperatorRunSummaryRead,
    AutoResearchRunExecutionRead,
    AutoResearchRunRead,
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
        export_publish=run.status == "done",
        download_publish=has_publish_archive,
    )


def _run_summary(
    *,
    run: AutoResearchRunRead,
    execution: AutoResearchRunExecutionRead,
) -> AutoResearchOperatorRunSummaryRead:
    registry_views = load_run_registry_views(run.project_id, run.id)
    publish = build_publish_package(run.project_id, run.id) if run.status == "done" else None
    counts = registry_views.counts if registry_views is not None else None
    latest_job = execution.jobs[-1] if execution.jobs else None
    return AutoResearchOperatorRunSummaryRead(
        run_id=run.id,
        topic=run.topic,
        status=run.status,
        created_at=run.created_at,
        updated_at=run.updated_at,
        selected_candidate_id=run.portfolio.selected_candidate_id if run.portfolio is not None else None,
        candidate_count=counts.total_candidates if counts is not None else len(run.candidates),
        selected_count=counts.selected if counts is not None else 0,
        active_count=counts.active if counts is not None else 0,
        failed_count=counts.failed if counts is not None else 0,
        eliminated_count=counts.eliminated if counts is not None else 0,
        latest_job_status=latest_job.status if latest_job is not None else None,
        active_job_id=execution.active_job_id,
        cancel_requested=execution.cancel_requested,
        publish_status=publish.status if publish is not None else None,
        publish_ready=publish.publish_ready if publish is not None else False,
        blocker_count=publish.blocker_count if publish is not None else 0,
        revision_count=publish.revision_count if publish is not None else 0,
    )


def build_operator_console(
    project_id: str,
    *,
    run_id: str | None = None,
) -> AutoResearchOperatorConsoleRead:
    runs = list_runs(project_id)
    execution_plane = AutoResearchExecutionPlane()
    summaries: list[AutoResearchOperatorRunSummaryRead] = []
    execution_by_run: dict[str, AutoResearchRunExecutionRead] = {}

    for run in runs:
        execution = execution_plane.get_run_execution(project_id, run.id)
        execution_by_run[run.id] = execution
        summaries.append(
            _run_summary(
                run=run,
                execution=execution,
            )
        )

    selected_run = next((item for item in runs if item.id == run_id), None) if run_id else None
    if selected_run is None and runs:
        selected_run = runs[0]

    current_run = None
    if selected_run is not None:
        execution = execution_by_run[selected_run.id]
        registry = load_run_registry(project_id, selected_run.id)
        registry_views = load_run_registry_views(project_id, selected_run.id)
        if registry is not None and registry_views is not None:
            review = build_run_review(project_id, selected_run.id) if selected_run.status == "done" else None
            publish = build_publish_package(project_id, selected_run.id) if selected_run.status == "done" else None
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
        latest_run_id=runs[0].id if runs else None,
        selected_run_id=current_run.run.id if current_run is not None else None,
        actions=AutoResearchOperatorProjectActionsRead(start_run=True),
        runs=summaries,
        current_run=current_run,
    )
