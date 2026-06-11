from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from schemas.autoresearch import (
    AutoResearchBridgeStatus,
    AutoResearchExperimentBridgeRead,
    AutoResearchExperimentExecutionResultRead,
    AutoResearchJobStatus,
    AutoResearchOperatorAction,
    AutoResearchOperatorActionLogRead,
    AutoResearchOperatorActionPolicyRead,
    AutoResearchOperatorActionRecordRead,
    AutoResearchOperatorActionRequest,
    AutoResearchOperatorActionResultRead,
    AutoResearchOperatorApprovalRead,
    AutoResearchOperatorArtifactLineageRead,
    AutoResearchOperatorBudgetRead,
    AutoResearchOperatorControlState,
    AutoResearchOperatorDecisionEvidenceRead,
    AutoResearchOperatorFinalGateStatusRead,
    AutoResearchOperatorJobStatusRead,
    AutoResearchOperatorPackageStatusRead,
    AutoResearchOperatorPolicyErrorRead,
    AutoResearchOperatorRepairQueueItemRead,
    AutoResearchOperatorRepairQueueRead,
    AutoResearchOperatorRunStatusRead,
    AutoResearchOperatorStateAuditItemRead,
    AutoResearchOperatorStateAuditRead,
    AutoResearchPublishPackageRead,
    AutoResearchRegistryAssetRef,
    AutoResearchReviewLoopRead,
    AutoResearchRunExecutionRead,
    AutoResearchRunRead,
    AutoResearchRunReviewRead,
    AutoResearchRunStatus,
    AutoResearchRunRegistryRead,
)
from services.autoresearch.bridge import (
    AutoResearchExperimentBridgeService,
    bridge_is_waiting_for_result,
    build_bridge_state,
)
from services.autoresearch.execution import AutoResearchExecutionPlane
from services.autoresearch.external_capabilities import get_or_build_external_capability_manifest
from services.autoresearch.repository import (
    evaluation_case_suite_file_path,
    load_operator_action_log,
    load_operator_state_audit,
    load_run,
    load_run_registry,
    operator_state_audit_file_path,
    save_operator_action_log,
    save_operator_state_audit,
)
from services.autoresearch.review_publish import build_publish_package, build_review_loop, build_run_review


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _first_line(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    return " ".join(str(value).split())[:240] or fallback


def _asset_ref_path(ref: AutoResearchRegistryAssetRef | None) -> str | None:
    if ref is None:
        return None
    return ref.path


def _dedupe(items: list[Any]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item is None:
            continue
        cleaned = " ".join(str(item).split()).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _policy(
    action: AutoResearchOperatorAction,
    *,
    allowed: bool,
    reason: str,
    blocker_code: str | None = None,
    recoverable: bool = False,
    required_next_action: str | None = None,
    related_refs: list[str] | None = None,
) -> AutoResearchOperatorActionPolicyRead:
    return AutoResearchOperatorActionPolicyRead(
        action=action,
        allowed=allowed,
        reason=reason,
        blocker_code=blocker_code,
        recoverable=recoverable,
        required_next_action=required_next_action,
        related_refs=related_refs or [],
    )


def _policy_error(
    policy: AutoResearchOperatorActionPolicyRead,
    *,
    current_state: str,
) -> AutoResearchOperatorPolicyErrorRead:
    return AutoResearchOperatorPolicyErrorRead(
        action=policy.action,
        current_state=current_state,
        reason=policy.reason,
        blocker_code=policy.blocker_code or "transition_not_allowed",
        recoverable=policy.recoverable,
        required_next_action=policy.required_next_action,
        related_refs=list(policy.related_refs),
    )


def _active_or_queued_jobs(execution: AutoResearchRunExecutionRead) -> list:
    return [
        job
        for job in execution.jobs
        if job.status in {"queued", "leased", "running"}
    ]


def _latest_job_status(execution: AutoResearchRunExecutionRead) -> AutoResearchJobStatus | None:
    return execution.jobs[-1].status if execution.jobs else None


def _latest_approval_record(
    action_log: AutoResearchOperatorActionLogRead | None,
) -> AutoResearchOperatorActionRecordRead | None:
    if action_log is None:
        return None
    for record in reversed(action_log.records):
        if record.action in {"approve", "reject"} and record.status in {"accepted", "noop"}:
            return record
    return None


def _control_state(
    *,
    run: AutoResearchRunRead,
    execution: AutoResearchRunExecutionRead,
    bridge: AutoResearchExperimentBridgeRead | None,
    result: AutoResearchExperimentExecutionResultRead | None,
    stale_refs: list[str],
    approval_record: AutoResearchOperatorActionRecordRead | None = None,
) -> AutoResearchOperatorControlState:
    if stale_refs:
        return "stale"
    if bridge is not None and bridge.current_session is not None and bridge.current_session.status == "waiting_result":
        return "blocked"
    if (
        result is not None
        and result.failure_classification == "budget_approval_required"
        and approval_record is not None
        and approval_record.action == "reject"
    ):
        return "blocked"
    if (
        result is not None
        and result.status == "needs_approval"
        and (approval_record is None or approval_record.action != "approve")
    ):
        return "needs_approval"
    if _active_or_queued_jobs(execution):
        return "running" if any(job.status == "running" for job in execution.jobs) else "pending"
    if run.status == "done":
        return "completed"
    if run.status == "failed":
        return "failed"
    if run.status == "canceled":
        return "canceled"
    if run.status == "queued":
        return "pending"
    if run.status == "running":
        return "running"
    return "not_started"


def _artifact_refs(registry: AutoResearchRunRegistryRead | None) -> list[AutoResearchRegistryAssetRef]:
    if registry is None:
        return []
    refs: list[AutoResearchRegistryAssetRef] = []
    for value in registry.files.model_dump().values():
        if not isinstance(value, dict):
            continue
        try:
            refs.append(AutoResearchRegistryAssetRef.model_validate(value))
        except Exception:
            continue
    return refs


def _missing_refs(registry: AutoResearchRunRegistryRead | None) -> list[str]:
    required_names = {
        "root",
        "run_json",
    }
    if registry is None:
        return ["run_registry"]
    refs_by_path = {
        ref.path: ref
        for ref in _artifact_refs(registry)
    }
    missing: list[str] = []
    files = registry.files.model_dump()
    for name in required_names:
        value = files.get(name)
        if not isinstance(value, dict):
            continue
        path = value.get("path")
        if not isinstance(path, str):
            continue
        ref = refs_by_path.get(path)
        if ref is not None and not ref.exists:
            missing.append(ref.path)
    return missing


def _stale_refs(
    *,
    publish: AutoResearchPublishPackageRead | None,
    expected_fingerprints: dict[str, str] | None = None,
) -> list[str]:
    stale: list[str] = []
    if publish is not None:
        if publish.archive_ready and not publish.archive_current:
            stale.append(publish.archive_path or "publish_archive")
        if getattr(publish, "archive_status", None) == "stale":
            stale.append(publish.archive_path or "publish_archive")
    if expected_fingerprints:
        for path, expected in expected_fingerprints.items():
            candidate = Path(path)
            if not candidate.is_file():
                stale.append(path)
                continue
            # A caller-supplied fingerprint is a freshness precondition; if it
            # does not match current artifact content, resume must be refused.
            import hashlib

            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if digest != expected:
                stale.append(path)
    return _dedupe(stale)


def _lineage_status(
    *,
    project_id: str,
    run_id: str,
    registry: AutoResearchRunRegistryRead | None,
    publish: AutoResearchPublishPackageRead | None,
    result: AutoResearchExperimentExecutionResultRead | None,
) -> AutoResearchOperatorArtifactLineageRead:
    refs = _artifact_refs(registry)
    missing = _missing_refs(registry)
    package_refs = _dedupe(
        [
            publish.manifest_path if publish is not None else None,
            publish.submission_manifest_path if publish is not None else None,
            publish.claim_evidence_index_path if publish is not None else None,
            publish.lineage_archive_path if publish is not None else None,
            publish.publication_readiness_path if publish is not None else None,
        ]
    )
    final_gate_refs = _dedupe(
        [
            getattr(publish, "final_publish_decision_path", None)
            if publish is not None
            else None,
            publish.manifest_path if publish is not None else None,
        ]
    )
    negative_refs = [
        f"experiment_execution_result:{item.get('category', 'negative_evidence')}"
        for item in (result.negative_evidence if result is not None else [])
        if isinstance(item, dict)
    ]
    return AutoResearchOperatorArtifactLineageRead(
        project_id=project_id,
        run_id=run_id,
        selected_artifact_id=registry.selected_candidate_id if registry is not None else None,
        root_path=registry.root_path if registry is not None else None,
        artifact_refs=refs,
        lineage_edges=registry.lineage.edges if registry is not None else [],
        package_refs=package_refs,
        final_gate_refs=final_gate_refs,
        negative_evidence_refs=negative_refs,
        missing_refs=missing,
        stale_refs=[],
    )


def _package_status(
    *,
    project_id: str,
    run_id: str,
    publish: AutoResearchPublishPackageRead | None,
) -> AutoResearchOperatorPackageStatusRead:
    if publish is None:
        return AutoResearchOperatorPackageStatusRead(
            project_id=project_id,
            run_id=run_id,
            blockers=["Publish package has not been built from persisted run state."],
        )
    blockers = _dedupe(
        [
            *publish.final_blockers,
            *publish.blockers,
            "Archive is stale; export again after repairing artifacts."
            if publish.archive_ready and not publish.archive_current
            else None,
        ]
    )
    return AutoResearchOperatorPackageStatusRead(
        project_id=project_id,
        run_id=run_id,
        publish_status=publish.status,
        publish_ready=publish.publish_ready,
        review_bundle_ready=publish.review_bundle_ready,
        final_publish_ready=publish.final_publish_ready,
        publication_tier=publish.publication_tier,
        archive_ready=publish.archive_ready,
        archive_current=publish.archive_current,
        archive_status=getattr(publish, "archive_status", None),
        package_fingerprint=publish.package_fingerprint,
        package_path=publish.archive_path,
        final_archive_download_allowed=bool(
            publish.final_publish_ready
            and publish.archive_ready
            and publish.archive_current
        ),
        blockers=blockers,
        related_refs=_dedupe(
            [
                publish.manifest_path,
                publish.submission_manifest_path,
                publish.claim_evidence_index_path,
                publish.lineage_archive_path,
                publish.publication_readiness_path,
            ]
        ),
    )


def _final_gate_status(
    *,
    project_id: str,
    run_id: str,
    publish: AutoResearchPublishPackageRead | None,
    external_capability_manifest_path: str | None = None,
    external_capability_blockers: list[str] | None = None,
) -> AutoResearchOperatorFinalGateStatusRead:
    return AutoResearchOperatorFinalGateStatusRead(
        project_id=project_id,
        run_id=run_id,
        final_publish_ready=bool(publish is not None and publish.final_publish_ready),
        review_bundle_ready=bool(publish is not None and publish.review_bundle_ready),
        paper_tier=None,
        policy_version=None,
        final_publish_decision_path=None,
        failed_check_ids=[],
        blockers=_dedupe(
            [
                *list(
                    publish.final_blockers
                    if publish is not None
                    else ["Run publish package has not been built."]
                ),
                *(external_capability_blockers or []),
            ]
        ),
        required_followups=list(publish.revision_actions if publish is not None else []),
        kill_criteria=[],
        claim_ceiling=None,
        evidence_refs=_dedupe(
            [
                publish.publication_readiness_path if publish is not None else None,
                publish.publication_evidence_index_path if publish is not None else None,
                publish.claim_evidence_index_path if publish is not None else None,
                publish.lineage_archive_path if publish is not None else None,
                external_capability_manifest_path,
            ]
        ),
        final_archive_download_allowed=bool(
            publish is not None
            and publish.final_publish_ready
            and publish.archive_ready
            and publish.archive_current
        ),
    )


def _budget_status(run: AutoResearchRunRead, result: AutoResearchExperimentExecutionResultRead | None) -> AutoResearchOperatorBudgetRead:
    request = run.request
    mode = "default"
    max_rounds = 3
    candidate_execution_limit = None
    queue_priority = "normal"
    if request is not None:
        max_rounds = request.max_rounds
        candidate_execution_limit = request.candidate_execution_limit
        queue_priority = request.queue_priority
        if candidate_execution_limit is not None or request.max_rounds != 3:
            mode = "bounded"
    approval_required = bool(
        result is not None
        and (
            result.status == "needs_approval"
            or result.failure_classification == "budget_approval_required"
        )
    )
    if approval_required:
        mode = "approval_required"
    return AutoResearchOperatorBudgetRead(
        project_id=run.project_id,
        run_id=run.id,
        mode=mode,
        queue_priority=queue_priority,
        max_rounds=max_rounds,
        candidate_execution_limit=candidate_execution_limit,
        approval_required=approval_required,
        exhausted=False,
        blockers=[
            "Typed execution requires explicit operator approval."
        ]
        if approval_required
        else [],
    )


def _approval_status(
    *,
    run: AutoResearchRunRead,
    result: AutoResearchExperimentExecutionResultRead | None,
    approval_record: AutoResearchOperatorActionRecordRead | None,
    action_policy: dict[str, AutoResearchOperatorActionPolicyRead],
) -> list[AutoResearchOperatorApprovalRead]:
    if result is None or result.failure_classification != "budget_approval_required":
        return [
            AutoResearchOperatorApprovalRead(
                approval_id=f"approval:{run.id}:not_required",
                project_id=run.project_id,
                run_id=run.id,
                required=False,
                status="not_required",
                reason="No persisted approval-gated typed execution job is pending.",
                actions={},
            )
        ]
    status = (
        "approved"
        if approval_record is not None and approval_record.action == "approve"
        else "rejected"
        if approval_record is not None and approval_record.action == "reject"
        else "pending"
        if result.status == "needs_approval"
        else "rejected"
    )
    return [
        AutoResearchOperatorApprovalRead(
            approval_id=f"approval:{run.id}:typed_execution",
            project_id=run.project_id,
            run_id=run.id,
            job_id=result.job_results[0].job_id if result.job_results else None,
            required=True,
            status=status,
            reason=_first_line(
                result.repair_reasons[0] if result.repair_reasons else None,
                "Typed execution budget policy requires explicit approval.",
            ),
            blockers=[blocker.reason for blocker in result.blockers],
            related_refs=result.lineage_refs,
            actions={
                key: value
                for key, value in action_policy.items()
                if key in {"approve", "reject"}
            },
        )
    ]


def _jobs_status(
    *,
    execution: AutoResearchRunExecutionRead,
    result: AutoResearchExperimentExecutionResultRead | None,
    action_policy: dict[str, AutoResearchOperatorActionPolicyRead],
) -> list[AutoResearchOperatorJobStatusRead]:
    jobs: list[AutoResearchOperatorJobStatusRead] = []
    for job in execution.jobs:
        jobs.append(
            AutoResearchOperatorJobStatusRead(
                job_id=job.id,
                project_id=job.project_id,
                run_id=job.run_id,
                job_source="execution_queue",
                action=job.action,
                status=job.status,
                detail=job.detail or job.error,
                worker_id=job.worker_id,
                enqueued_at=job.enqueued_at,
                started_at=job.started_at,
                finished_at=job.finished_at,
                attempt_count=job.attempt_count,
                recovery_count=job.recovery_count,
                blockers=[job.error] if job.error else [],
                policy_actions={
                    key: value
                    for key, value in action_policy.items()
                    if key in {"cancel", "retry", "resume"}
                },
            )
        )
    if result is not None:
        for job in result.job_results:
            jobs.append(
                AutoResearchOperatorJobStatusRead(
                    job_id=job.job_id,
                    project_id=job.project_id,
                    run_id=job.run_id or "",
                    job_source="typed_experiment_execution",
                    job_kind=job.job_kind,
                    execution_route=job.execution_route,
                    status=job.status,
                    approval_state=job.approval_state,
                    budget_class=job.budget_class,
                    blockers=[
                        *[blocker.reason for blocker in job.blockers],
                        *result.repair_reasons,
                    ],
                    lineage_parent_refs=job.lineage_parent_refs,
                    output_artifact_refs=result.output_artifact_refs,
                    negative_evidence_refs=[
                        f"experiment_execution_result:{item.get('category', 'negative_evidence')}"
                        for item in result.negative_evidence
                        if isinstance(item, dict)
                    ],
                    policy_actions={
                        key: value
                        for key, value in action_policy.items()
                        if key in {"approve", "reject", "retry"}
                    },
                )
            )
    return jobs


def _repair_queue(
    *,
    run: AutoResearchRunRead,
    review: AutoResearchRunReviewRead | None,
    review_loop: AutoResearchReviewLoopRead | None,
    publish: AutoResearchPublishPackageRead | None,
    result: AutoResearchExperimentExecutionResultRead | None,
    action_log: AutoResearchOperatorActionLogRead | None,
) -> AutoResearchOperatorRepairQueueRead:
    items: list[AutoResearchOperatorRepairQueueItemRead] = []
    del publish
    repair_plan = review.publication_repair_plan if review is not None else None
    if repair_plan is not None:
        for action in repair_plan.actions:
            items.append(
                AutoResearchOperatorRepairQueueItemRead(
                    repair_id=action.action_id,
                    source="publication_repair_plan",
                    title=action.title,
                    status=action.status,
                    detail=action.detail,
                    blockers=action.blockers,
                    required_action=action.kind,
                    related_refs=action.supporting_asset_ids,
                )
            )
    if review_loop is not None:
        for action in review_loop.actions:
            if action.status != "pending":
                continue
            items.append(
                AutoResearchOperatorRepairQueueItemRead(
                    repair_id=action.action_id,
                    source="review_loop",
                    title=action.title,
                    status=action.status,
                    detail=action.detail,
                    blockers=action.residual_blockers,
                    required_action=action.execution_route,
                    related_refs=action.input_artifact_refs,
                )
            )
    if result is not None and result.status in {"failed", "blocked", "needs_approval"}:
        items.append(
            AutoResearchOperatorRepairQueueItemRead(
                repair_id=f"typed_execution:{result.result_id}:{result.failure_classification}",
                source="typed_execution_result",
                title="Typed experiment execution requires operator attention.",
                status=result.status,
                detail=_first_line(
                    result.repair_reasons[0] if result.repair_reasons else None,
                    "Typed execution did not produce publishable evidence.",
                ),
                blockers=[blocker.reason for blocker in result.blockers],
                required_action=result.repair_recommendation,
                related_refs=result.lineage_refs,
            )
        )
    if action_log is not None:
        for record in action_log.records:
            if record.terminal_blocker is None:
                continue
            items.append(
                AutoResearchOperatorRepairQueueItemRead(
                    repair_id=f"operator_decision:{record.action_id}",
                    source="operator_decision",
                    title=f"Operator {record.action} decision created terminal evidence.",
                    status="blocked",
                    detail=record.terminal_blocker.reason,
                    blockers=[record.terminal_blocker.reason],
                    required_action=record.terminal_blocker.required_next_action,
                    related_refs=record.related_refs,
                )
            )
    pending = sum(1 for item in items if item.status in {"pending", "needs_approval"})
    blocked = sum(1 for item in items if item.status in {"blocked", "failed", "rejected"})
    failed_execution = sum(1 for item in items if item.source == "typed_execution_result")
    return AutoResearchOperatorRepairQueueRead(
        project_id=run.project_id,
        run_id=run.id,
        item_count=len(items),
        pending_count=pending,
        blocked_count=blocked,
        failed_execution_count=failed_execution,
        items=items,
    )


def _failure_refs(result: AutoResearchExperimentExecutionResultRead | None) -> tuple[list[str], list[str]]:
    if result is None:
        return [], []
    failure_refs = _dedupe(
        [
            f"experiment_execution_result:{result.result_id}:{result.failure_classification}"
            if result.failure_classification != "none"
            else None,
            *result.repair_reasons,
        ]
    )
    negative_refs = _dedupe(
        [
            f"negative_evidence:{item.get('category', 'unknown')}"
            for item in result.negative_evidence
            if isinstance(item, dict)
        ]
    )
    return failure_refs, negative_refs


def _preserved_refs(
    *,
    registry: AutoResearchRunRegistryRead | None,
    publish: AutoResearchPublishPackageRead | None,
    result: AutoResearchExperimentExecutionResultRead | None,
) -> list[str]:
    return _dedupe(
        [
            *[
                ref.path
                for ref in _artifact_refs(registry)
                if ref.exists and ref.path.endswith((".json", ".md", ".zip"))
            ],
            *(result.lineage_refs if result is not None else []),
            publish.manifest_path if publish is not None else None,
            publish.lineage_archive_path if publish is not None else None,
        ]
    )


def _build_action_policy(
    *,
    run: AutoResearchRunRead,
    execution: AutoResearchRunExecutionRead,
    bridge: AutoResearchExperimentBridgeRead | None,
    publish: AutoResearchPublishPackageRead | None,
    result: AutoResearchExperimentExecutionResultRead | None,
    registry: AutoResearchRunRegistryRead | None,
    action_log: AutoResearchOperatorActionLogRead | None = None,
    expected_fingerprints: dict[str, str] | None = None,
) -> dict[str, AutoResearchOperatorActionPolicyRead]:
    stale = _stale_refs(publish=publish, expected_fingerprints=expected_fingerprints)
    missing = _missing_refs(registry)
    active_jobs = _active_or_queued_jobs(execution)
    bridge_waiting = bool(
        bridge is not None
        and bridge.current_session is not None
        and bridge.current_session.status == "waiting_result"
    )
    approval_record = _latest_approval_record(action_log)
    approval_granted = bool(
        approval_record is not None and approval_record.action == "approve"
    )
    approval_rejected = bool(
        approval_record is not None and approval_record.action == "reject"
    )
    approval_needed = bool(
        result is not None
        and result.status == "needs_approval"
        and result.failure_classification == "budget_approval_required"
        and not approval_granted
        and not approval_rejected
    )
    latest_job_status = _latest_job_status(execution)
    can_cancel = bool(active_jobs or bridge_waiting)
    can_retry = bool(
        run.status in {"done", "failed", "canceled"}
        or latest_job_status in {"failed", "canceled"}
        or (result is not None and result.status in {"failed", "blocked"})
    )
    queued_resume_noop = bool(
        run.status == "queued"
        and latest_job_status == "queued"
        and not bridge_waiting
        and not approval_needed
        and not approval_rejected
        and not stale
        and not missing
    )
    can_resume = bool(
        run.status in {"queued", "running", "failed", "canceled"}
        and not active_jobs
        and not bridge_waiting
        and not approval_needed
        and not approval_rejected
        and not stale
        and not missing
    ) or queued_resume_noop
    if run.status == "done":
        can_resume = False
    return {
        "approve": _policy(
            "approve",
            allowed=approval_needed,
            reason=(
                "Typed execution approval can be granted."
                if approval_needed
                else "Typed execution approval was already granted."
                if approval_granted
                else "Typed execution approval was rejected and requires a new plan or retry."
                if approval_rejected
                else "No persisted approval-gated typed execution job is pending."
            ),
            blocker_code=None
            if approval_needed
            else "approval_already_granted"
            if approval_granted
            else "approval_rejected"
            if approval_rejected
            else "no_pending_approval",
            recoverable=not approval_needed,
            required_next_action="resume" if approval_needed else None,
            related_refs=result.lineage_refs if result is not None else [],
        ),
        "reject": _policy(
            "reject",
            allowed=approval_needed,
            reason=(
                "Typed execution approval can be rejected with terminal blocker evidence."
                if approval_needed
                else "Typed execution approval was already granted."
                if approval_granted
                else "Typed execution approval was already rejected."
                if approval_rejected
                else "No persisted approval-gated typed execution job is pending."
            ),
            blocker_code=None
            if approval_needed
            else "approval_already_granted"
            if approval_granted
            else "approval_rejected"
            if approval_rejected
            else "no_pending_approval",
            recoverable=not approval_needed,
            required_next_action="inspect_approval_queue",
            related_refs=result.lineage_refs if result is not None else [],
        ),
        "retry": _policy(
            "retry",
            allowed=can_retry and not active_jobs,
            reason=(
                "Failed or terminal run can be retried as a new queued attempt."
                if can_retry and not active_jobs
                else "Retry requires a failed, canceled, or completed run with no active queue job."
            ),
            blocker_code=None if can_retry and not active_jobs else "retry_not_allowed",
            recoverable=not (can_retry and not active_jobs),
            required_next_action="cancel" if active_jobs else "inspect_failure",
            related_refs=_dedupe(
                [
                    run.id,
                    *(result.lineage_refs if result is not None else []),
                ]
            ),
        ),
        "resume": _policy(
            "resume",
            allowed=can_resume,
            reason=(
                "Run can resume from persisted checkpoint state."
                if can_resume
                else "Resume is blocked by current state, stale artifacts, missing refs, approval, or bridge import."
            ),
            blocker_code=None
            if can_resume
            else "resume_blocked_by_policy",
            recoverable=not can_resume,
            required_next_action=(
                "refresh_or_rebuild_stale_artifacts"
                if stale
                else "repair_missing_refs"
                if missing
                else "create_new_approved_plan_or_retry"
                if approval_rejected
                else "approve_or_reject"
                if approval_needed
                else "import_bridge_result"
                if bridge_waiting
                else "inspect_run"
            ),
            related_refs=_dedupe([*stale, *missing, run.id]),
        ),
        "cancel": _policy(
            "cancel",
            allowed=can_cancel,
            reason=(
                "Active queue job or bridge waiting session can be canceled."
                if can_cancel
                else "Cancel requires an active queued/running job or bridge waiting session."
            ),
            blocker_code=None if can_cancel else "cancel_not_allowed",
            recoverable=not can_cancel,
            required_next_action="inspect_execution",
            related_refs=[job.id for job in active_jobs],
        ),
    }


def build_operator_run_status(
    project_id: str,
    run_id: str,
    *,
    expected_fingerprints: dict[str, str] | None = None,
) -> AutoResearchOperatorRunStatusRead:
    run = load_run(project_id, run_id)
    if run is None:
        raise ValueError(f"Auto research run not found: {run_id}")
    execution_plane = AutoResearchExecutionPlane()
    execution = execution_plane.get_run_execution(project_id, run_id)
    bridge = build_bridge_state(project_id, run_id)
    registry = load_run_registry(project_id, run_id)
    publish = build_publish_package(project_id, run_id) if run.status == "done" else None
    review = build_run_review(project_id, run_id) if run.status == "done" else None
    review_loop = build_review_loop(project_id, run_id) if run.status == "done" else None
    result = run.experiment_execution_result
    action_log = load_operator_action_log(project_id, run_id)
    external_capabilities = get_or_build_external_capability_manifest(project_id)
    approval_record = _latest_approval_record(action_log)
    stale = _stale_refs(publish=publish, expected_fingerprints=expected_fingerprints)
    policy = _build_action_policy(
        run=run,
        execution=execution,
        bridge=bridge,
        publish=publish,
        result=result,
        registry=registry,
        action_log=action_log,
        expected_fingerprints=expected_fingerprints,
    )
    lineage = _lineage_status(
        project_id=project_id,
        run_id=run_id,
        registry=registry,
        publish=publish,
        result=result,
    )
    lineage = lineage.model_copy(update={"stale_refs": stale})
    package = _package_status(project_id=project_id, run_id=run_id, publish=publish)
    final_gate = _final_gate_status(
        project_id=project_id,
        run_id=run_id,
        publish=publish,
        external_capability_manifest_path=external_capabilities.manifest_path,
        external_capability_blockers=external_capabilities.blockers,
    )
    budget = _budget_status(run, result)
    approvals = _approval_status(
        run=run,
        result=result,
        approval_record=approval_record,
        action_policy=policy,
    )
    repair_queue = _repair_queue(
        run=run,
        review=review,
        review_loop=review_loop,
        publish=publish,
        result=result,
        action_log=action_log,
    )
    jobs = _jobs_status(execution=execution, result=result, action_policy=policy)
    control_state = _control_state(
        run=run,
        execution=execution,
        bridge=bridge,
        result=result,
        stale_refs=stale,
        approval_record=approval_record,
    )
    blockers = _dedupe(
        [
            run.error,
            *stale,
            *lineage.missing_refs,
            *package.blockers,
            *final_gate.blockers,
            *budget.blockers,
            *external_capabilities.blockers,
        ]
    )
    timeline = [
        {
            "event_id": "run_created",
            "timestamp": run.created_at.isoformat(),
            "status": "created",
            "related_refs": [f"run:{run.id}"],
        },
        {
            "event_id": f"run_{run.status}",
            "timestamp": run.updated_at.isoformat(),
            "status": run.status,
            "related_refs": [f"run:{run.id}"],
        },
        *[
            {
                "event_id": f"job_{job.status}_{job.id}",
                "timestamp": (job.finished_at or job.started_at or job.enqueued_at).isoformat(),
                "status": job.status,
                "related_refs": [f"queue_job:{job.id}"],
            }
            for job in execution.jobs
        ],
        *[
            {
                "event_id": f"operator_{record.action}_{record.action_id}",
                "timestamp": record.requested_at.isoformat(),
                "status": record.status,
                "related_refs": record.related_refs,
            }
            for record in (action_log.records if action_log is not None else [])
        ],
    ]
    timeline.sort(key=lambda item: (str(item.get("timestamp")), str(item.get("event_id"))))
    return AutoResearchOperatorRunStatusRead(
        project_id=project_id,
        run_id=run_id,
        run_status=run.status,
        control_state=control_state,
        persisted_reconstructable=registry is not None,
        current_attempt=len(execution.jobs),
        blockers=blockers,
        stale_refs=stale,
        missing_refs=lineage.missing_refs,
        timeline=timeline,
        action_policy=policy,
        jobs=jobs,
        approvals=approvals,
        budget=budget,
        repair_queue=repair_queue,
        artifact_lineage=lineage,
        package_status=package,
        final_gate_status=final_gate,
        external_capability_manifest=external_capabilities,
        action_log=action_log,
        audit_artifact_ref=operator_state_audit_file_path(project_id),
    )


def _append_action_record(
    *,
    project_id: str,
    run_id: str,
    record: AutoResearchOperatorActionRecordRead,
) -> AutoResearchOperatorActionLogRead:
    existing = load_operator_action_log(project_id, run_id)
    records = list(existing.records if existing is not None else [])
    records.append(record)
    return save_operator_action_log(
        AutoResearchOperatorActionLogRead(
            project_id=project_id,
            run_id=run_id,
            generated_at=_utcnow(),
            records=records,
            record_count=len(records),
        )
    )


def _operator_decision(
    *,
    action: AutoResearchOperatorAction,
    reason: str,
    terminal: bool,
    blocker_code: str | None,
    related_refs: list[str],
) -> AutoResearchOperatorDecisionEvidenceRead:
    return AutoResearchOperatorDecisionEvidenceRead(
        evidence_id=f"operator_decision_{uuid4().hex}",
        action=action,
        created_at=_utcnow(),
        reason=reason,
        terminal=terminal,
        blocker_code=blocker_code,
        related_refs=related_refs,
    )


def apply_operator_action(
    project_id: str,
    run_id: str,
    request: AutoResearchOperatorActionRequest,
    *,
    background_tasks: Any | None = None,
    identity_user_id: str | None = None,
) -> AutoResearchOperatorActionResultRead:
    run = load_run(project_id, run_id)
    if run is None:
        raise ValueError(f"Auto research run not found: {run_id}")
    status = build_operator_run_status(
        project_id,
        run_id,
        expected_fingerprints=request.expected_artifact_fingerprints,
    )
    policy = status.action_policy[request.action]
    preserved_refs = _preserved_refs(
        registry=load_run_registry(project_id, run_id),
        publish=build_publish_package(project_id, run_id) if run.status == "done" else None,
        result=run.experiment_execution_result,
    )
    failure_refs, negative_refs = _failure_refs(run.experiment_execution_result)
    operator_id = request.operator_id or identity_user_id
    if not policy.allowed:
        error = _policy_error(policy, current_state=status.control_state)
        record = AutoResearchOperatorActionRecordRead(
            action_id=f"operator_action_{uuid4().hex}",
            project_id=project_id,
            run_id=run_id,
            action=request.action,
            requested_at=_utcnow(),
            status="blocked",
            operator_id=operator_id,
            target_id=request.target_id,
            reason=request.reason or policy.reason,
            attempt_number=status.current_attempt,
            preserved_artifact_refs=preserved_refs,
            failure_evidence_refs=failure_refs,
            negative_evidence_refs=negative_refs,
            terminal_blocker=error,
            decision_evidence=_operator_decision(
                action=request.action,
                reason=policy.reason,
                terminal=False,
                blocker_code=error.blocker_code,
                related_refs=policy.related_refs,
            ),
            related_refs=policy.related_refs,
        )
        _append_action_record(project_id=project_id, run_id=run_id, record=record)
        return AutoResearchOperatorActionResultRead(
            project_id=project_id,
            run_id=run_id,
            action=request.action,
            accepted=False,
            status="blocked",
            action_record=record,
            policy_error=error,
            run_status=build_operator_run_status(project_id, run_id),
        )

    plane = AutoResearchExecutionPlane()
    job_id: str | None = None
    execution: AutoResearchRunExecutionRead | None = None
    action_status: str = "accepted"
    terminal_error: AutoResearchOperatorPolicyErrorRead | None = None
    decision_reason = request.reason or policy.reason

    if request.action in {"retry", "resume"}:
        job, created = plane.enqueue(project_id=project_id, run_id=run_id, action=request.action)
        job_id = job.id
        action_status = "accepted" if created else "noop"
        if created and background_tasks is not None:
            background_tasks.add_task(plane.drain)
        execution = plane.get_run_execution(project_id, run_id)
    elif request.action == "cancel":
        try:
            execution = plane.request_cancel(project_id=project_id, run_id=run_id)
        except ValueError:
            if bridge_is_waiting_for_result(project_id, run_id):
                AutoResearchExperimentBridgeService().cancel_waiting_session(
                    project_id=project_id,
                    run_id=run_id,
                )
                execution = plane.get_run_execution(project_id, run_id)
            else:
                raise
        latest_job = execution.jobs[-1] if execution.jobs else None
        job_id = latest_job.id if latest_job is not None else None
        terminal_error = AutoResearchOperatorPolicyErrorRead(
            action="cancel",
            current_state=status.control_state,
            reason=decision_reason,
            blocker_code="operator_canceled",
            recoverable=False,
            required_next_action="retry",
            related_refs=policy.related_refs,
        )
    elif request.action == "reject":
        terminal_error = AutoResearchOperatorPolicyErrorRead(
            action="reject",
            current_state=status.control_state,
            reason=decision_reason,
            blocker_code="operator_rejected_approval",
            recoverable=True,
            required_next_action="create_new_approved_plan_or_retry",
            related_refs=policy.related_refs,
        )
        execution = plane.get_run_execution(project_id, run_id)
    elif request.action == "approve":
        # Goal 9 records approval as persisted operator evidence. It does not
        # fabricate typed execution output; a later resume/retry must still
        # rebuild or import real artifacts through the existing runtime.
        execution = plane.get_run_execution(project_id, run_id)

    record = AutoResearchOperatorActionRecordRead(
        action_id=f"operator_action_{uuid4().hex}",
        project_id=project_id,
        run_id=run_id,
        action=request.action,
        requested_at=_utcnow(),
        status=action_status,
        operator_id=operator_id,
        target_id=request.target_id or request.approval_id,
        reason=decision_reason,
        job_id=job_id,
        attempt_number=status.current_attempt + (1 if request.action in {"retry", "resume"} and action_status == "accepted" else 0),
        parent_attempt_id=status.jobs[-1].job_id if status.jobs else None,
        preserved_artifact_refs=preserved_refs,
        failure_evidence_refs=failure_refs,
        negative_evidence_refs=negative_refs,
        terminal_blocker=terminal_error,
        decision_evidence=_operator_decision(
            action=request.action,
            reason=decision_reason,
            terminal=request.action in {"cancel", "reject"},
            blocker_code=terminal_error.blocker_code if terminal_error is not None else None,
            related_refs=policy.related_refs,
        ),
        related_refs=policy.related_refs,
    )
    _append_action_record(project_id=project_id, run_id=run_id, record=record)
    return AutoResearchOperatorActionResultRead(
        project_id=project_id,
        run_id=run_id,
        action=request.action,
        accepted=action_status in {"accepted", "noop"},
        status=action_status,
        job_id=job_id,
        action_record=record,
        execution=execution,
        run_status=build_operator_run_status(project_id, run_id),
    )


def build_operator_state_audit(project_id: str) -> AutoResearchOperatorStateAuditRead:
    from services.autoresearch.evaluation_cases import build_evaluation_case_suite
    from services.autoresearch.project_paper_orchestrator import build_project_paper_orchestration
    from services.autoresearch.repository import list_runs

    runs = list_runs(project_id)
    execution_plane = AutoResearchExecutionPlane()
    queue, _workers = execution_plane.get_queue_snapshot()
    project_package = build_project_paper_orchestration(project_id) if runs else None
    evaluation_suite = build_evaluation_case_suite(project_id)
    items: list[AutoResearchOperatorStateAuditItemRead] = [
        AutoResearchOperatorStateAuditItemRead(
            state_id="auto_research_queue",
            category="run_queue",
            state_source="queue_file",
            state_owner="backend/services/autoresearch/execution.py",
            current_state=f"queued={queue.queued_jobs};running={queue.running_jobs};failed={queue.failed_jobs};canceled={queue.canceled_jobs}",
            reconstructable_after_restart=True,
            allowed_transitions=["resume", "retry", "cancel"],
            known_blockers=[] if queue.total_jobs else ["No queue jobs have been persisted for this project yet."],
            missing_operator_controls=[],
            related_artifact_refs=["queue.json"],
        )
    ]
    case_coverage: set[str] = set()
    blockers: list[str] = []
    for run in runs:
        status = build_operator_run_status(project_id, run.id)
        if status.run_status == "done":
            case_coverage.add("success")
        if status.control_state in {"blocked", "needs_approval"} or status.blockers:
            case_coverage.add("blocked")
        if status.repair_queue.failed_execution_count or run.status == "failed":
            case_coverage.add("failed_execution")
        if status.repair_queue.item_count or status.repair_queue.pending_count or status.repair_queue.blocked_count:
            case_coverage.add("revision")
        if status.package_status.review_bundle_ready or status.package_status.final_publish_ready:
            case_coverage.add("package/final_gate")
        if status.artifact_lineage.lineage_edges:
            case_coverage.add("artifact_lineage")
        if status.final_gate_status.final_publish_ready is False and status.final_gate_status.blockers:
            case_coverage.add("final_gate_blocked")
        result = run.experiment_execution_result
        if result is not None and result.failure_classification == "unsupported_execution_backend":
            case_coverage.add("unsupported_domain")
        items.append(
            AutoResearchOperatorStateAuditItemRead(
                state_id=f"run:{run.id}",
                category="run_queue",
                state_source="repository_artifact",
                state_owner="backend/services/autoresearch/repository.py",
                current_state=status.control_state,
                reconstructable_after_restart=status.persisted_reconstructable,
                allowed_transitions=[
                    action
                    for action, policy in status.action_policy.items()
                    if policy.allowed
                ],
                known_blockers=status.blockers,
                missing_operator_controls=[],
                related_artifact_refs=[status.audit_artifact_ref or "", *status.artifact_lineage.package_refs],
                source_path=status.artifact_lineage.root_path,
            )
        )
        for job in status.jobs:
            items.append(
                AutoResearchOperatorStateAuditItemRead(
                    state_id=f"job:{job.job_id}",
                    category="typed_execution_job"
                    if job.job_source == "typed_experiment_execution"
                    else "run_queue",
                    state_source="repository_artifact"
                    if job.job_source == "typed_experiment_execution"
                    else "queue_file",
                    state_owner="backend/services/autoresearch/experiment_execution.py"
                    if job.job_source == "typed_experiment_execution"
                    else "backend/services/autoresearch/execution.py",
                    current_state=job.status,
                    reconstructable_after_restart=True,
                    allowed_transitions=[
                        action
                        for action, policy in job.policy_actions.items()
                        if policy.allowed
                    ],
                    known_blockers=job.blockers,
                    missing_operator_controls=[],
                    related_artifact_refs=[
                        *job.lineage_parent_refs,
                        *job.output_artifact_refs,
                        *job.negative_evidence_refs,
                    ],
                )
            )
        if status.approvals:
            items.append(
                AutoResearchOperatorStateAuditItemRead(
                    state_id=f"approval_budget:{run.id}",
                    category="approval_budget",
                    state_source="derived",
                    state_owner="backend/services/autoresearch/operator_control.py",
                    current_state=status.budget.mode,
                    reconstructable_after_restart=True,
                    allowed_transitions=[
                        action
                        for action, policy in status.action_policy.items()
                        if action in {"approve", "reject"} and policy.allowed
                    ],
                    known_blockers=status.budget.blockers,
                    missing_operator_controls=[],
                    related_artifact_refs=[
                        ref
                        for approval in status.approvals
                        for ref in approval.related_refs
                    ],
                )
            )
        bridge_state = build_bridge_state(project_id, run.id)
        if bridge_state is not None and bridge_state.enabled:
            items.append(
                AutoResearchOperatorStateAuditItemRead(
                    state_id=f"bridge:{run.id}",
                    category="bridge_import",
                    state_source="repository_artifact",
                    state_owner="backend/services/autoresearch/bridge.py",
                    current_state=bridge_state.status,
                    reconstructable_after_restart=True,
                    allowed_transitions=["resume", "cancel"],
                    known_blockers=[
                        "Bridge result import is required before resume."
                    ]
                    if bridge_state.status == "waiting_result"
                    else [],
                    missing_operator_controls=[],
                    related_artifact_refs=[
                        bridge_state.persisted_path or "",
                        bridge_state.current_session.result_path
                        if bridge_state.current_session is not None
                        else "",
                    ],
                )
            )
        items.append(
            AutoResearchOperatorStateAuditItemRead(
                state_id=f"repair_revision:{run.id}",
                category="repair_revision",
                state_source="repository_artifact",
                state_owner="backend/services/autoresearch/review_publish.py",
                current_state=f"items={status.repair_queue.item_count};blocked={status.repair_queue.blocked_count}",
                reconstructable_after_restart=True,
                allowed_transitions=["retry", "resume"],
                known_blockers=[
                    blocker
                    for item in status.repair_queue.items
                    for blocker in item.blockers
                ],
                missing_operator_controls=[],
                related_artifact_refs=[
                    ref
                    for item in status.repair_queue.items
                    for ref in item.related_refs
                ],
            )
        )
        items.append(
            AutoResearchOperatorStateAuditItemRead(
                state_id=f"package_final_gate:{run.id}",
                category="package_final_gate",
                state_source="repository_artifact",
                state_owner="backend/services/autoresearch/review_publish.py",
                current_state=(
                    "final_publish_ready"
                    if status.final_gate_status.final_publish_ready
                    else "review_ready"
                    if status.package_status.review_bundle_ready
                    else "blocked"
                ),
                reconstructable_after_restart=True,
                allowed_transitions=[],
                known_blockers=status.final_gate_status.blockers,
                missing_operator_controls=[],
                related_artifact_refs=[
                    *status.package_status.related_refs,
                    status.final_gate_status.final_publish_decision_path or "",
                ],
            )
        )
        items.append(
            AutoResearchOperatorStateAuditItemRead(
                state_id=f"artifact_lineage:{run.id}",
                category="artifact_lineage",
                state_source="repository_artifact",
                state_owner="backend/services/autoresearch/repository.py",
                current_state=f"edges={len(status.artifact_lineage.lineage_edges)};missing={len(status.artifact_lineage.missing_refs)}",
                reconstructable_after_restart=True,
                allowed_transitions=[],
                known_blockers=status.artifact_lineage.missing_refs,
                missing_operator_controls=[],
                related_artifact_refs=[
                    ref.path for ref in status.artifact_lineage.artifact_refs if ref.exists
                ],
            )
        )
        blockers.extend(status.blockers)

    if evaluation_suite.cases:
        case_coverage.update(
            case.case_id
            for case in evaluation_suite.cases
            if case.case_id in {"unsupported_domain_case", "failed_execution_case"}
            or "unsupported" in case.case_id
            or "failed" in case.case_id
        )
        if any(
            case.trace is not None
            and (
                case.trace.project_revision_action_count > 0
                or case.trace.project_revision_action_plan_path
                or case.trace.project_revision_response_dossier_path
            )
            for case in evaluation_suite.cases
        ):
            case_coverage.add("revision")
        items.append(
            AutoResearchOperatorStateAuditItemRead(
                state_id="goal8_evaluation_suite",
                category="evaluation_artifact",
                state_source="repository_artifact",
                state_owner="backend/services/autoresearch/evaluation_cases.py",
                current_state=f"cases={evaluation_suite.case_count};completed={evaluation_suite.completed_case_count}",
                reconstructable_after_restart=True,
                allowed_transitions=[],
                known_blockers=evaluation_suite.blockers,
                missing_operator_controls=[],
                related_artifact_refs=[
                    evaluation_case_suite_file_path(project_id),
                    *[
                        case.trace.trace_artifact_path
                        for case in evaluation_suite.cases
                        if case.trace is not None and case.trace.trace_artifact_path
                    ],
                ],
                source_path=evaluation_case_suite_file_path(project_id),
            )
        )

    if project_package is not None and project_package.project_submission_manifest_path:
        case_coverage.add("package/final_gate")
    required_coverage = {
        "success",
        "blocked",
        "failed_execution",
        "package/final_gate",
        "unsupported_domain",
        "artifact_lineage",
    }
    missing_coverage = sorted(required_coverage - case_coverage)
    if missing_coverage:
        blockers.append(
            "Operator audit has not observed required deterministic cases: "
            + ", ".join(missing_coverage)
        )
    audit = AutoResearchOperatorStateAuditRead(
        project_id=project_id,
        generated_at=_utcnow(),
        state_items=items,
        state_item_count=len(items),
        case_coverage=sorted(case_coverage),
        blockers=_dedupe(blockers),
        conclusion=(
            "Operator state is reconstructed from queue, repository artifacts, and derived final-gate state; "
            "missing cases remain blockers and are not treated as success."
        ),
    )
    return save_operator_state_audit(audit)


def get_or_build_operator_state_audit(project_id: str) -> AutoResearchOperatorStateAuditRead:
    audit = load_operator_state_audit(project_id)
    if audit is not None:
        return audit
    return build_operator_state_audit(project_id)
