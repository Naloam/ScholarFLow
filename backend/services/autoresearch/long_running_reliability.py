from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from schemas.autoresearch import (
    AutoResearchExternalCapabilityManifestRead,
    AutoResearchJobStatus,
    AutoResearchLongRunningArtifactStateRead,
    AutoResearchLongRunningAttemptLedgerRead,
    AutoResearchLongRunningAttemptRecordRead,
    AutoResearchLongRunningBranchReadiness,
    AutoResearchLongRunningMigrationRecordRead,
    AutoResearchLongRunningRepairCandidateRead,
    AutoResearchOperatorActionRecordRead,
    AutoResearchOperatorBudgetRead,
    AutoResearchOperatorFinalGateStatusRead,
    AutoResearchOperatorPackageStatusRead,
    AutoResearchOperatorRunStatusRead,
    AutoResearchProjectBranchRead,
    AutoResearchProjectBranchStateRead,
    AutoResearchProjectRunbookRead,
    AutoResearchProjectStateManifestRead,
    AutoResearchProjectTimelineEventRead,
    AutoResearchProjectTimelineRead,
    AutoResearchRegistryAssetRef,
    AutoResearchRunExecutionRead,
    AutoResearchRunRead,
    AutoResearchRunRegistryRead,
)
from services.autoresearch.repository import (
    load_long_running_attempt_ledger,
    load_operator_action_log,
    load_project_branch_state,
    load_project_runbook,
    load_project_state_manifest,
    load_project_timeline,
    long_running_attempt_ledger_file_path,
    project_branch_state_file_path,
    project_runbook_file_path,
    project_state_manifest_file_path,
    project_timeline_file_path,
    save_long_running_attempt_ledger,
    save_project_branch_state,
    save_project_runbook,
    save_project_state_manifest,
    save_project_timeline,
)


POLICY_VERSION = "goal11_long_running_reliability_v1"
CURRENT_SCHEMA_BY_KIND = {
    "run_json": "auto_research_run_v1",
    "program_json": "research_program_v1",
    "plan_json": "research_plan_v1",
    "spec_json": "experiment_spec_v1",
    "portfolio_json": "portfolio_summary_v1",
    "artifact_json": "result_artifact_v1",
    "experiment_execution_plan_json": "experiment_execution_plan_v1",
    "experiment_execution_result_json": "experiment_execution_result_v1",
    "evidence_ledger_json": "evidence_ledger_v1",
    "paper_sources_manifest_json": "paper_sources_manifest_v1",
    "publication_evidence_index_json": "publication_evidence_index_v1",
    "artifact_integrity_audit_json": "artifact_integrity_audit_v1",
    "candidate_candidate_json": "hypothesis_candidate_v1",
    "candidate_plan_json": "research_plan_v1",
    "candidate_spec_json": "experiment_spec_v1",
    "candidate_attempts_json": "candidate_attempts_v1",
    "candidate_artifact_json": "result_artifact_v1",
    "candidate_manifest_json": "candidate_manifest_v1",
}
FINAL_GATE_KINDS = {
    "run_json",
    "artifact_json",
    "experiment_execution_result_json",
    "evidence_ledger_json",
    "paper_sources_manifest_json",
    "publication_evidence_index_json",
    "artifact_integrity_audit_json",
}
UNSAFE_RESUME_SCHEMA_REQUIRED_KINDS = {
    "artifact_json",
    "experiment_execution_result_json",
    "evidence_ledger_json",
    "paper_sources_manifest_json",
    "publication_evidence_index_json",
    "artifact_integrity_audit_json",
    "candidate_attempts_json",
    "candidate_artifact_json",
}
EVIDENCE_ORIGINS = {
    "fixture",
    "toy",
    "local_smoke",
    "deterministic_replay",
    "stale_cache",
    "fresh_cache",
    "imported_real_artifact",
    "frozen_snapshot",
    "live_source",
    "docker_execution",
    "bridge_execution",
}
SERVICE_OWNER_BY_KIND = {
    "run_json": "backend/services/autoresearch/repository.py",
    "program_json": "backend/services/autoresearch/planner.py",
    "plan_json": "backend/services/autoresearch/planner.py",
    "spec_json": "backend/services/autoresearch/benchmarks.py",
    "portfolio_json": "backend/services/autoresearch/orchestrator.py",
    "artifact_json": "backend/services/autoresearch/runner.py",
    "experiment_execution_plan_json": "backend/services/autoresearch/experiment_execution.py",
    "experiment_execution_result_json": "backend/services/autoresearch/experiment_execution.py",
    "evidence_ledger_json": "backend/services/autoresearch/experiment_execution.py",
    "paper_sources_manifest_json": "backend/services/autoresearch/writer.py",
    "publication_evidence_index_json": "backend/services/autoresearch/publication_evidence_index.py",
    "artifact_integrity_audit_json": "backend/services/autoresearch/artifact_integrity_audit.py",
    "candidate_candidate_json": "backend/services/autoresearch/repository.py",
    "candidate_plan_json": "backend/services/autoresearch/orchestrator.py",
    "candidate_spec_json": "backend/services/autoresearch/orchestrator.py",
    "candidate_attempts_json": "backend/services/autoresearch/orchestrator.py",
    "candidate_artifact_json": "backend/services/autoresearch/runner.py",
    "candidate_manifest_json": "backend/services/autoresearch/repository.py",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_file():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _schema_version(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    for key in (
        "schema_version",
        "manifest_schema_version",
        "policy_version",
        "ledger_schema_version",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _source_origin(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    for key in ("evidence_origin", "execution_route", "source_class", "cache_freshness"):
        value = payload.get(key)
        if isinstance(value, str) and value in EVIDENCE_ORIGINS:
            return value
    nested = payload.get("environment_manifest")
    if isinstance(nested, dict):
        value = nested.get("execution_route")
        if isinstance(value, str) and value in EVIDENCE_ORIGINS:
            return value
    return None


def _asset_refs(registry: AutoResearchRunRegistryRead | None) -> list[tuple[str, AutoResearchRegistryAssetRef]]:
    if registry is None:
        return []
    refs: list[tuple[str, AutoResearchRegistryAssetRef]] = []
    for key, value in registry.files.model_dump().items():
        if not isinstance(value, dict):
            continue
        try:
            refs.append((key, AutoResearchRegistryAssetRef.model_validate(value)))
        except Exception:
            continue
    for candidate in registry.candidates:
        for key, value in candidate.files.model_dump().items():
            if not isinstance(value, dict):
                continue
            try:
                refs.append((f"candidate_{key}", AutoResearchRegistryAssetRef.model_validate(value)))
            except Exception:
                continue
    return refs


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _refresh_ref(ref: AutoResearchRegistryAssetRef) -> AutoResearchRegistryAssetRef:
    candidate = Path(ref.path)
    exists = candidate.exists()
    size_bytes = candidate.stat().st_size if exists and candidate.is_file() else None
    return ref.model_copy(
        update={
            "exists": exists,
            "size_bytes": size_bytes,
            "sha256": _sha256_file(candidate) if exists and candidate.is_file() else None,
        }
    )


def _expected_fingerprint(
    *,
    ref: AutoResearchRegistryAssetRef,
    expected_fingerprints: dict[str, str] | None,
) -> str | None:
    if expected_fingerprints and ref.path in expected_fingerprints:
        return expected_fingerprints[ref.path]
    return ref.sha256


def _migration_record_for(
    artifact: AutoResearchLongRunningArtifactStateRead,
) -> AutoResearchLongRunningMigrationRecordRead:
    target = artifact.expected_schema_version or CURRENT_SCHEMA_BY_KIND.get(
        artifact.artifact_kind,
        "unknown_v1",
    )
    supported = artifact.schema_version is not None and artifact.schema_version in {
        target,
        "project_state_manifest_v1",
        "project_timeline_v1",
        "project_runbook_v1",
    }
    return AutoResearchLongRunningMigrationRecordRead(
        migration_id=f"migration:{artifact.artifact_id}:{target}",
        artifact_ref=artifact.artifact_ref,
        source_schema_version=artifact.schema_version,
        target_schema_version=target,
        supported=supported,
        status="supported" if supported else "unsupported",
        hash_before=artifact.fingerprint,
        hash_after=artifact.fingerprint if supported else None,
        migration_artifact_refs=[artifact.artifact_ref] if supported else [],
        policy_version=POLICY_VERSION,
        blockers=[]
        if supported
        else [f"{artifact.artifact_kind} has no supported schema migration path."],
    )


def build_artifact_states(
    *,
    registry: AutoResearchRunRegistryRead | None,
    expected_fingerprints: dict[str, str] | None = None,
) -> list[AutoResearchLongRunningArtifactStateRead]:
    states: list[AutoResearchLongRunningArtifactStateRead] = []
    seen_paths: set[str] = set()
    for key, raw_ref in _asset_refs(registry):
        ref = _refresh_ref(raw_ref)
        path = ref.path
        if path in seen_paths:
            status = "superseded"
        else:
            status = "active"
        seen_paths.add(path)
        blockers: list[str] = []
        payload = _read_json(path) if ref.exists and Path(path).is_file() else None
        schema_version = _schema_version(payload)
        if key == "run_json" and payload is not None and schema_version is None:
            schema_version = CURRENT_SCHEMA_BY_KIND[key]
        expected_schema = CURRENT_SCHEMA_BY_KIND.get(key)
        expected_hash = _expected_fingerprint(ref=ref, expected_fingerprints=expected_fingerprints)
        if not ref.exists:
            status = "missing"
            blockers.append(f"Missing persisted artifact `{path}`.")
        elif expected_hash and ref.sha256 and expected_hash != ref.sha256:
            status = "fingerprint_mismatch"
            blockers.append(f"Artifact fingerprint mismatch for `{path}`.")
        elif (
            key in CURRENT_SCHEMA_BY_KIND
            and key in UNSAFE_RESUME_SCHEMA_REQUIRED_KINDS
            and schema_version is None
        ):
            status = "migration_needed"
            blockers.append(f"Artifact `{key}` is missing schema_version.")
        elif expected_schema is not None and schema_version not in {None, expected_schema}:
            status = "migration_needed"
            blockers.append(
                f"Artifact `{key}` schema `{schema_version}` requires migration to `{expected_schema}`."
            )
        states.append(
            AutoResearchLongRunningArtifactStateRead(
                artifact_id=f"{key}:{_fingerprint(path)[:12]}",
                artifact_kind=key,
                artifact_ref=path,
                owning_service=SERVICE_OWNER_BY_KIND.get(key, "backend/services/autoresearch/repository.py"),
                status=status,
                schema_version=schema_version,
                expected_schema_version=expected_schema,
                fingerprint=ref.sha256,
                expected_fingerprint=expected_hash,
                parent_refs=[registry.root_path] if registry is not None else [],
                superseded_by=None,
                reconstructable_after_restart=bool(ref.exists),
                migration_status="needed" if status == "migration_needed" else "not_required",
                final_gate_relevance=key in FINAL_GATE_KINDS,
                evidence_origin=_source_origin(payload),  # type: ignore[arg-type]
                blockers=blockers,
            )
        )
    return states


def _repair_for_artifact(
    artifact: AutoResearchLongRunningArtifactStateRead,
) -> AutoResearchLongRunningRepairCandidateRead | None:
    if artifact.status == "active":
        return None
    workflow = "terminal_blocker"
    action = "inspect_artifact"
    if artifact.status == "missing":
        workflow = "rerun"
        action = "rebuild_or_reimport_missing_artifact"
    elif artifact.status == "fingerprint_mismatch":
        workflow = "revalidate"
        action = "revalidate_artifact_fingerprint"
    elif artifact.status == "migration_needed":
        workflow = "migrate"
        action = "run_supported_schema_migration_or_block"
    elif artifact.status == "stale":
        workflow = "revalidate"
        action = "refresh_or_rebuild_stale_artifact"
    elif artifact.status == "superseded":
        workflow = "downgrade_claim"
        action = "exclude_superseded_artifact_from_new_claims"
    return AutoResearchLongRunningRepairCandidateRead(
        repair_id=f"repair:{artifact.artifact_id}:{artifact.status}",
        artifact_ref=artifact.artifact_ref,
        workflow=workflow,  # type: ignore[arg-type]
        reason=artifact.blockers[0] if artifact.blockers else f"Artifact is {artifact.status}.",
        required_action=action,
        status="blocked" if workflow == "terminal_blocker" else "pending",
        blockers=artifact.blockers,
        related_refs=[artifact.artifact_ref],
    )


def _manifest_blockers(
    *,
    states: list[AutoResearchLongRunningArtifactStateRead],
) -> list[str]:
    blockers: list[str] = []
    for artifact in states:
        if artifact.status in {"fingerprint_mismatch", "migration_needed"}:
            blockers.extend(artifact.blockers)
    return _dedupe(blockers)


def build_project_state_manifest(
    *,
    run: AutoResearchRunRead,
    registry: AutoResearchRunRegistryRead | None,
    package_status: AutoResearchOperatorPackageStatusRead | None,
    final_gate_status: AutoResearchOperatorFinalGateStatusRead | None,
    expected_fingerprints: dict[str, str] | None = None,
    persist: bool = True,
) -> AutoResearchProjectStateManifestRead:
    states = build_artifact_states(
        registry=registry,
        expected_fingerprints=expected_fingerprints,
    )
    stale = [item for item in states if item.status == "stale"]
    superseded = [item for item in states if item.status == "superseded"]
    missing = [item for item in states if item.status == "missing"]
    migration_needed = [item for item in states if item.status in {"migration_needed", "fingerprint_mismatch"}]
    repair_candidates = [
        item for item in (_repair_for_artifact(artifact) for artifact in states) if item is not None
    ]
    migration_records = [
        _migration_record_for(item)
        for item in states
        if item.status == "migration_needed"
    ]
    unsafe_resume_blockers = _manifest_blockers(states=states)
    if unsafe_resume_blockers and final_gate_status is not None:
        final_gate_status = final_gate_status.model_copy(
            update={
                "final_publish_ready": False,
                "final_archive_download_allowed": False,
                "blockers": _dedupe(
                    [*final_gate_status.blockers, *unsafe_resume_blockers]
                ),
            }
        )
    if unsafe_resume_blockers and package_status is not None:
        package_status = package_status.model_copy(
            update={
                "final_publish_ready": False,
                "final_archive_download_allowed": False,
                "blockers": _dedupe([*package_status.blockers, *unsafe_resume_blockers]),
            }
        )
    manifest = AutoResearchProjectStateManifestRead(
        manifest_id=f"state_manifest:{run.project_id}:{run.id}",
        project_id=run.project_id,
        run_id=run.id,
        rebuilt_at=_utcnow(),
        policy_version=POLICY_VERSION,
        active_artifacts=[item for item in states if item.status == "active"],
        stale_artifacts=stale,
        superseded_artifacts=superseded,
        missing_artifacts=missing,
        migration_needed_artifacts=migration_needed,
        unsafe_resume_blockers=unsafe_resume_blockers,
        current_final_gate_state=final_gate_status,
        current_package_state=package_status,
        repair_candidates=repair_candidates,
        migration_records=migration_records,
        manifest_path=project_state_manifest_file_path(run.project_id, run.id),
    )
    return save_project_state_manifest(manifest) if persist else manifest


def _event(
    *,
    run: AutoResearchRunRead,
    event_id: str,
    event_type: str,
    timestamp: datetime,
    source: str,
    summary: str,
    status: str,
    actor: str = "system",
    artifact_refs: list[str] | None = None,
    parent_event_refs: list[str] | None = None,
    blockers: list[str] | None = None,
    risks: list[str] | None = None,
) -> AutoResearchProjectTimelineEventRead:
    return AutoResearchProjectTimelineEventRead(
        event_id=event_id,
        event_type=event_type,  # type: ignore[arg-type]
        timestamp=timestamp,
        actor=actor,
        source=source,
        artifact_refs=artifact_refs or [],
        parent_event_refs=parent_event_refs or [],
        policy_version=POLICY_VERSION,
        summary=summary,
        status=status,
        blockers=blockers or [],
        risks=risks or [],
    )


def build_project_timeline(
    *,
    run: AutoResearchRunRead,
    registry: AutoResearchRunRegistryRead | None,
    execution: AutoResearchRunExecutionRead,
    state_manifest: AutoResearchProjectStateManifestRead,
    external_capabilities: AutoResearchExternalCapabilityManifestRead | None,
    persist: bool = True,
) -> AutoResearchProjectTimelineRead:
    events: list[AutoResearchProjectTimelineEventRead] = [
        _event(
            run=run,
            event_id=f"idea:{run.id}",
            event_type="idea",
            timestamp=run.created_at,
            source="AutoResearchRunRead.topic",
            summary=run.topic,
            status="created",
            artifact_refs=[f"run:{run.id}"],
        ),
        _event(
            run=run,
            event_id=f"domain_routing:{run.id}",
            event_type="domain_routing",
            timestamp=run.created_at,
            source="AutoResearchRunRead.task_family",
            summary=run.task_family or "Domain routing has not completed.",
            status="complete" if run.task_family else "missing",
            blockers=[] if run.task_family else ["Domain routing artifact is missing."],
        ),
    ]
    if run.brief_id:
        events.append(
            _event(
                run=run,
                event_id=f"research_brief:{run.brief_id}",
                event_type="research_brief",
                timestamp=run.created_at,
                source="idea_brief",
                summary=f"Research brief `{run.brief_id}` selected for run.",
                status="complete",
                artifact_refs=[f"brief:{run.brief_id}"],
                parent_event_refs=[f"idea:{run.id}"],
            )
        )
    if run.literature or run.literature_synthesis is not None:
        events.append(
            _event(
                run=run,
                event_id=f"literature_scout:{run.id}",
                event_type="literature_scout",
                timestamp=run.updated_at,
                source="literature_scout",
                summary=f"{len(run.literature)} literature insights are attached.",
                status="complete",
                artifact_refs=["run.literature"],
            )
        )
    if run.benchmark is not None or run.spec is not None:
        spec_ref = registry.files.spec_json.path if registry is not None and registry.files.spec_json is not None else "spec.json"
        events.append(
            _event(
                run=run,
                event_id=f"benchmark_source_validation:{run.id}",
                event_type="benchmark_source_validation",
                timestamp=run.updated_at,
                source="benchmarks",
                summary=run.spec.benchmark_name if run.spec is not None else "Benchmark source attached.",
                status="complete",
                artifact_refs=[spec_ref],
            )
        )
    if run.candidates:
        events.append(
            _event(
                run=run,
                event_id=f"hypothesis_bank:{run.id}",
                event_type="hypothesis_bank",
                timestamp=run.updated_at,
                source="orchestrator",
                summary=f"{len(run.candidates)} hypothesis candidates persisted.",
                status="complete",
                artifact_refs=[f"candidate:{item.id}" for item in run.candidates],
            )
        )
    if run.portfolio is not None:
        events.append(
            _event(
                run=run,
                event_id=f"direction_selection:{run.id}",
                event_type="direction_selection",
                timestamp=run.updated_at,
                source="portfolio",
                summary=run.portfolio.decision_summary,
                status=run.portfolio.status,
                artifact_refs=[run.portfolio.selected_candidate_id or "portfolio"],
            )
        )
    if run.experiment_execution_plan is not None:
        events.append(
            _event(
                run=run,
                event_id=f"protocol:{run.id}",
                event_type="protocol",
                timestamp=run.updated_at,
                source="experiment_execution",
                summary=(
                    f"{run.experiment_execution_plan.job_count} typed execution jobs planned."
                ),
                status=run.experiment_execution_plan.status,
                artifact_refs=[run.experiment_execution_plan_path or "experiment_execution_plan.json"],
                blockers=[blocker.reason for blocker in run.experiment_execution_plan.blockers],
            )
        )
    if run.experiment_execution_result is not None:
        events.append(
            _event(
                run=run,
                event_id=f"execution_import:{run.experiment_execution_result.result_id}",
                event_type="execution_import",
                timestamp=run.updated_at,
                source="experiment_execution",
                summary=(
                    "Experiment execution result "
                    f"{run.experiment_execution_result.status}; "
                    f"failure_classification={run.experiment_execution_result.failure_classification}."
                ),
                status=run.experiment_execution_result.status,
                artifact_refs=run.experiment_execution_result.output_artifact_refs,
                blockers=[blocker.reason for blocker in run.experiment_execution_result.blockers],
            )
        )
    if run.evidence_ledger is not None:
        events.append(
            _event(
                run=run,
                event_id=f"evidence_ledger:{run.evidence_ledger.ledger_id}",
                event_type="evidence_ledger",
                timestamp=run.updated_at,
                source="evidence_ledger",
                summary=f"{run.evidence_ledger.entry_count} evidence entries persisted.",
                status="complete",
                artifact_refs=[run.evidence_ledger_path or "evidence_ledger.json"],
            )
        )
    if run.paper_sources_manifest is not None or run.paper_markdown is not None:
        events.append(
            _event(
                run=run,
                event_id=f"manuscript_source_package:{run.id}",
                event_type="manuscript_source_package",
                timestamp=run.updated_at,
                source="writer",
                summary="Paper/source package state was materialized.",
                status="complete" if run.paper_sources_manifest is not None else "partial",
                artifact_refs=[run.paper_sources_manifest_path or run.paper_path or "paper.md"],
            )
        )
    for job in execution.jobs:
        events.append(
            _event(
                run=run,
                event_id=f"attempt:{job.id}",
                event_type="attempt",
                timestamp=job.finished_at or job.started_at or job.enqueued_at,
                source="execution_queue",
                summary=f"{job.action} job `{job.id}` is {job.status}.",
                status=job.status,
                artifact_refs=[f"queue_job:{job.id}"],
                blockers=[job.error] if job.error else [],
            )
        )
    action_log = load_operator_action_log(run.project_id, run.id)
    for record in action_log.records if action_log is not None else []:
        events.append(
            _event(
                run=run,
                event_id=f"operator_action:{record.action_id}",
                event_type="operator_action",
                timestamp=record.requested_at,
                source="operator_control",
                actor=record.operator_id or "operator",
                summary=record.reason or f"Operator {record.action} action.",
                status=record.status,
                artifact_refs=record.related_refs,
                blockers=[record.terminal_blocker.reason] if record.terminal_blocker else [],
            )
        )
    if external_capabilities is not None:
        events.append(
            _event(
                run=run,
                event_id=f"external_capability_check:{external_capabilities.manifest_fingerprint}",
                event_type="external_capability_check",
                timestamp=external_capabilities.generated_at,
                source="external_capabilities",
                summary=f"{external_capabilities.ready_count} capabilities ready.",
                status="blocked" if external_capabilities.blockers else "complete",
                artifact_refs=[external_capabilities.manifest_path or "external_capability_manifest.json"],
                blockers=external_capabilities.blockers,
            )
        )
    if state_manifest.current_package_state is not None:
        events.append(
            _event(
                run=run,
                event_id=f"submission_package:{run.id}",
                event_type="submission_package",
                timestamp=run.updated_at,
                source="review_publish",
                summary=state_manifest.current_package_state.publish_status or "Publish package state.",
                status="complete"
                if state_manifest.current_package_state.publish_ready
                else "blocked",
                artifact_refs=state_manifest.current_package_state.related_refs,
                blockers=state_manifest.current_package_state.blockers,
            )
        )
    if state_manifest.current_final_gate_state is not None:
        events.append(
            _event(
                run=run,
                event_id=f"final_decision:{run.id}",
                event_type="final_decision",
                timestamp=run.updated_at,
                source="review_publish",
                summary="Final publish gate is ready."
                if state_manifest.current_final_gate_state.final_publish_ready
                else "Final publish gate is blocked.",
                status="ready"
                if state_manifest.current_final_gate_state.final_publish_ready
                else "blocked",
                artifact_refs=state_manifest.current_final_gate_state.evidence_refs,
                blockers=state_manifest.current_final_gate_state.blockers,
            )
        )
    events.append(
        _event(
            run=run,
            event_id=f"human_compliance_placeholder:{run.id}",
            event_type="human_compliance_placeholder",
            timestamp=run.updated_at,
            source="goal13_placeholder",
            summary="Human review and compliance records are not implemented before Goal 13.",
            status="placeholder",
            risks=["Release export remains gated until human/compliance records exist."],
        )
    )
    for blocker in state_manifest.unsafe_resume_blockers:
        events.append(
            _event(
                run=run,
                event_id=f"blocker_failure:{_fingerprint(blocker)[:12]}",
                event_type="blocker_failure",
                timestamp=run.updated_at,
                source="project_state_manifest",
                summary=blocker,
                status="blocked",
                blockers=[blocker],
            )
        )
    timeline = AutoResearchProjectTimelineRead(
        timeline_id=f"timeline:{run.project_id}:{run.id}",
        project_id=run.project_id,
        run_id=run.id,
        rebuilt_at=_utcnow(),
        policy_version=POLICY_VERSION,
        events=sorted(events, key=lambda item: (item.timestamp, item.event_id)),
        event_count=len(events),
        timeline_path=project_timeline_file_path(run.project_id, run.id),
    )
    return save_project_timeline(timeline) if persist else timeline


def _dedupe(items: list[Any]) -> list[str]:
    result: list[str] = []
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
        result.append(cleaned)
    return result


def build_project_runbook(
    *,
    run: AutoResearchRunRead,
    state_manifest: AutoResearchProjectStateManifestRead,
    operator_status: AutoResearchOperatorRunStatusRead | None = None,
    persist: bool = True,
) -> AutoResearchProjectRunbookRead:
    next_actions: list[str] = []
    blocked_actions: list[str] = []
    required_approvals: list[str] = []
    if operator_status is not None:
        for action, policy in operator_status.action_policy.items():
            if policy.allowed and policy.required_next_action:
                next_actions.append(policy.required_next_action)
            elif not policy.allowed:
                blocked_actions.append(f"{action}: {policy.reason}")
        for approval in operator_status.approvals:
            if approval.required and approval.status == "pending":
                required_approvals.append(approval.reason)
    if state_manifest.repair_candidates:
        next_actions.extend(item.required_action for item in state_manifest.repair_candidates)
    if state_manifest.current_final_gate_state is not None and state_manifest.current_final_gate_state.final_publish_ready:
        next_actions.append("export_publish")
    elif state_manifest.current_final_gate_state is not None:
        next_actions.append("resolve_final_gate_blockers")
    if run.status in {"failed", "canceled"}:
        next_actions.append("retry_or_fork_direction")
    claim_ceiling = (
        state_manifest.current_final_gate_state.claim_ceiling
        if state_manifest.current_final_gate_state is not None
        else None
    )
    kill_criteria = (
        state_manifest.current_final_gate_state.kill_criteria
        if state_manifest.current_final_gate_state is not None
        else []
    )
    runbook = AutoResearchProjectRunbookRead(
        runbook_id=f"runbook:{run.project_id}:{run.id}",
        project_id=run.project_id,
        run_id=run.id,
        rebuilt_at=_utcnow(),
        policy_version=POLICY_VERSION,
        next_actions=_dedupe(next_actions) or ["inspect_project_state_manifest"],
        required_approvals=_dedupe(required_approvals),
        blocked_actions=_dedupe(blocked_actions),
        repair_candidates=state_manifest.repair_candidates,
        claim_ceiling=claim_ceiling,
        package_status=state_manifest.current_package_state,
        final_gate_status=state_manifest.current_final_gate_state,
        kill_criteria=kill_criteria,
        stale_artifacts=[item.artifact_ref for item in state_manifest.stale_artifacts],
        migration_needed_artifacts=[
            item.artifact_ref for item in state_manifest.migration_needed_artifacts
        ],
        owner_refs=_dedupe([item.owning_service for item in state_manifest.active_artifacts]),
        source_refs=_dedupe(
            [
                item.artifact_ref
                for item in [
                    *state_manifest.active_artifacts,
                    *state_manifest.missing_artifacts,
                    *state_manifest.migration_needed_artifacts,
                ]
            ]
        ),
        blockers=state_manifest.unsafe_resume_blockers,
        runbook_path=project_runbook_file_path(run.project_id, run.id),
    )
    return save_project_runbook(runbook) if persist else runbook


def _status_from_job_status(status: AutoResearchJobStatus) -> str:
    if status == "succeeded":
        return "succeeded"
    if status == "canceled":
        return "canceled"
    if status == "failed":
        return "failed"
    if status in {"queued", "leased"}:
        return "queued"
    return "running"


def build_attempt_ledger(
    *,
    run: AutoResearchRunRead,
    execution: AutoResearchRunExecutionRead,
    operator_status: AutoResearchOperatorRunStatusRead | None,
    external_capabilities: AutoResearchExternalCapabilityManifestRead | None,
    persist: bool = True,
) -> AutoResearchLongRunningAttemptLedgerRead:
    attempts: list[AutoResearchLongRunningAttemptRecordRead] = []
    capability_snapshot = {
        record.capability_id: record.state
        for record in (external_capabilities.records if external_capabilities is not None else [])
    }
    budget = operator_status.budget if operator_status is not None else None
    approval_status = (
        operator_status.approvals[0].status
        if operator_status is not None and operator_status.approvals
        else None
    )
    for index, job in enumerate(execution.jobs):
        attempts.append(
            AutoResearchLongRunningAttemptRecordRead(
                attempt_id=f"queue_attempt:{job.id}",
                parent_attempt_id=f"queue_attempt:{execution.jobs[index - 1].id}" if index > 0 else None,
                branch_id=f"branch:{run.portfolio.selected_candidate_id}"
                if run.portfolio is not None and run.portfolio.selected_candidate_id
                else f"branch:{run.id}:default",
                action=job.action,
                job_id=job.id,
                trigger="execution_queue",
                decision=job.detail,
                approval_state=approval_status,
                budget_state=budget.mode if budget is not None else None,
                capability_state_snapshot=capability_snapshot,
                inputs=[run.id],
                outputs=[],
                failure_classification=job.error,
                repair_action="retry" if job.status in {"failed", "canceled"} else None,
                artifact_refs=[f"queue_job:{job.id}"],
                negative_evidence_refs=[],
                stale_detection=operator_status.stale_refs if operator_status is not None else [],
                status=_status_from_job_status(job.status),  # type: ignore[arg-type]
                terminal=job.status in {"succeeded", "failed", "canceled"},
                timestamp=job.finished_at or job.started_at or job.enqueued_at,
                blockers=[job.error] if job.error else [],
            )
        )
    action_log = load_operator_action_log(run.project_id, run.id)
    for record in action_log.records if action_log is not None else []:
        status = "blocked" if record.status == "blocked" else "noop" if record.status == "noop" else "succeeded"
        if record.action == "cancel" and record.terminal_blocker is not None:
            status = "canceled"
        elif record.action == "reject" and record.terminal_blocker is not None:
            status = "rejected"
        attempts.append(
            AutoResearchLongRunningAttemptRecordRead(
                attempt_id=f"operator_attempt:{record.action_id}",
                parent_attempt_id=record.parent_attempt_id,
                branch_id=f"branch:{run.portfolio.selected_candidate_id}"
                if run.portfolio is not None and run.portfolio.selected_candidate_id
                else f"branch:{run.id}:default",
                action=record.action,
                job_id=record.job_id,
                trigger="operator_action",
                decision=record.reason,
                approval_state=approval_status,
                budget_state=budget.mode if budget is not None else None,
                capability_state_snapshot=capability_snapshot,
                inputs=record.preserved_artifact_refs,
                outputs=record.related_refs,
                failure_classification=record.terminal_blocker.blocker_code
                if record.terminal_blocker is not None
                else None,
                repair_action=record.terminal_blocker.required_next_action
                if record.terminal_blocker is not None
                else None,
                artifact_refs=record.related_refs,
                negative_evidence_refs=record.negative_evidence_refs,
                stale_detection=operator_status.stale_refs if operator_status is not None else [],
                status=status,  # type: ignore[arg-type]
                terminal=record.action in {"cancel", "reject"} or record.status == "blocked",
                timestamp=record.requested_at,
                operator_id=record.operator_id,
                blockers=[record.terminal_blocker.reason] if record.terminal_blocker else [],
            )
        )
    if run.experiment_execution_result is not None:
        attempts.append(
            AutoResearchLongRunningAttemptRecordRead(
                attempt_id=f"typed_execution:{run.experiment_execution_result.result_id}",
                branch_id=f"branch:{run.portfolio.selected_candidate_id}"
                if run.portfolio is not None and run.portfolio.selected_candidate_id
                else f"branch:{run.id}:default",
                action="run",
                trigger="typed_experiment_execution",
                approval_state=approval_status,
                budget_state=budget.mode if budget is not None else None,
                capability_state_snapshot=capability_snapshot,
                inputs=run.experiment_execution_result.lineage_refs,
                outputs=run.experiment_execution_result.output_artifact_refs,
                failure_classification=run.experiment_execution_result.failure_classification,
                repair_action=run.experiment_execution_result.repair_recommendation,
                artifact_refs=run.experiment_execution_result.output_artifact_refs,
                negative_evidence_refs=[
                    f"negative_evidence:{item.get('category', 'unknown')}"
                    for item in run.experiment_execution_result.negative_evidence
                    if isinstance(item, dict)
                ],
                stale_detection=operator_status.stale_refs if operator_status is not None else [],
                status=(
                    "succeeded"
                    if run.experiment_execution_result.status == "succeeded"
                    else "blocked"
                    if run.experiment_execution_result.status == "needs_approval"
                    else run.experiment_execution_result.status
                ),  # type: ignore[arg-type]
                terminal=run.experiment_execution_result.status
                in {"succeeded", "failed", "blocked"},
                timestamp=run.updated_at,
                blockers=[blocker.reason for blocker in run.experiment_execution_result.blockers],
            )
        )
    negative_refs = _dedupe(
        [
            ref
            for attempt in attempts
            for ref in attempt.negative_evidence_refs
        ]
    )
    ledger = AutoResearchLongRunningAttemptLedgerRead(
        ledger_id=f"attempt_ledger:{run.project_id}:{run.id}",
        project_id=run.project_id,
        run_id=run.id,
        rebuilt_at=_utcnow(),
        policy_version=POLICY_VERSION,
        attempts=sorted(attempts, key=lambda item: (item.timestamp, item.attempt_id)),
        attempt_count=len(attempts),
        terminal_attempt_count=sum(1 for item in attempts if item.terminal),
        negative_evidence_refs=negative_refs,
        ledger_path=long_running_attempt_ledger_file_path(run.project_id, run.id),
    )
    return save_long_running_attempt_ledger(ledger) if persist else ledger


def record_attempt_transition(
    *,
    run: AutoResearchRunRead,
    record: AutoResearchOperatorActionRecordRead,
    operator_status: AutoResearchOperatorRunStatusRead | None = None,
    external_capabilities: AutoResearchExternalCapabilityManifestRead | None = None,
) -> AutoResearchLongRunningAttemptLedgerRead:
    existing = load_long_running_attempt_ledger(run.project_id, run.id)
    attempts = list(existing.attempts if existing is not None else [])
    status = "blocked" if record.status == "blocked" else "noop" if record.status == "noop" else "succeeded"
    if record.action == "cancel" and record.terminal_blocker is not None:
        status = "canceled"
    elif record.action == "reject" and record.terminal_blocker is not None:
        status = "rejected"
    capability_snapshot = {
        capability.capability_id: capability.state
        for capability in (
            external_capabilities.records if external_capabilities is not None else []
        )
    }
    budget: AutoResearchOperatorBudgetRead | None = (
        operator_status.budget if operator_status is not None else None
    )
    attempts.append(
        AutoResearchLongRunningAttemptRecordRead(
            attempt_id=f"operator_attempt:{record.action_id}",
            parent_attempt_id=record.parent_attempt_id,
            branch_id=f"branch:{run.portfolio.selected_candidate_id}"
            if run.portfolio is not None and run.portfolio.selected_candidate_id
            else f"branch:{run.id}:default",
            action=record.action,
            job_id=record.job_id,
            trigger="operator_action",
            decision=record.reason,
            approval_state=operator_status.approvals[0].status
            if operator_status is not None and operator_status.approvals
            else None,
            budget_state=budget.mode if budget is not None else None,
            capability_state_snapshot=capability_snapshot,
            inputs=record.preserved_artifact_refs,
            outputs=record.related_refs,
            failure_classification=record.terminal_blocker.blocker_code
            if record.terminal_blocker is not None
            else None,
            repair_action=record.terminal_blocker.required_next_action
            if record.terminal_blocker is not None
            else None,
            artifact_refs=record.related_refs,
            negative_evidence_refs=record.negative_evidence_refs,
            stale_detection=operator_status.stale_refs if operator_status is not None else [],
            status=status,  # type: ignore[arg-type]
            terminal=record.action in {"cancel", "reject"} or record.status == "blocked",
            timestamp=record.requested_at,
            operator_id=record.operator_id,
            blockers=[record.terminal_blocker.reason] if record.terminal_blocker else [],
        )
    )
    ledger = AutoResearchLongRunningAttemptLedgerRead(
        ledger_id=f"attempt_ledger:{run.project_id}:{run.id}",
        project_id=run.project_id,
        run_id=run.id,
        rebuilt_at=_utcnow(),
        policy_version=POLICY_VERSION,
        attempts=attempts,
        negative_evidence_refs=_dedupe(
            [
                ref
                for attempt in attempts
                for ref in attempt.negative_evidence_refs
            ]
        ),
    )
    return save_long_running_attempt_ledger(ledger)


def build_branch_state(
    *,
    run: AutoResearchRunRead,
    state_manifest: AutoResearchProjectStateManifestRead,
    persist: bool = True,
) -> AutoResearchProjectBranchStateRead:
    selected_candidate_id = (
        run.portfolio.selected_candidate_id if run.portfolio is not None else None
    )
    branches: list[AutoResearchProjectBranchRead] = []
    if run.candidates:
        for candidate in sorted(run.candidates, key=lambda item: (item.rank, item.id)):
            branch_id = f"branch:{candidate.id}"
            selected = candidate.id == selected_candidate_id
            invalidated = [
                item.artifact_ref
                for item in state_manifest.migration_needed_artifacts
                if selected
            ]
            readiness: AutoResearchLongRunningBranchReadiness = (
                "selected"
                if selected
                else "blocked"
                if candidate.status in {"failed", "deferred"}
                else "active"
            )
            branches.append(
                AutoResearchProjectBranchRead(
                    branch_id=branch_id,
                    parent_branch_id=None,
                    parent_hypothesis_id=candidate.id,
                    selected_direction_refs=[candidate.id],
                    inherited_evidence_scope=["discovery_only_from_parent_run"],
                    invalidated_evidence=invalidated,
                    branch_specific_artifacts=[
                        item.artifact_ref
                        for item in [
                            *state_manifest.active_artifacts,
                            *state_manifest.stale_artifacts,
                            *state_manifest.migration_needed_artifacts,
                        ]
                        if selected and item.final_gate_relevance and item.status != "missing"
                    ],
                    branch_readiness=readiness,
                    claim_ceiling=state_manifest.current_final_gate_state.claim_ceiling
                    if state_manifest.current_final_gate_state is not None
                    else None,
                    final_gate_blockers=state_manifest.current_final_gate_state.blockers
                    if selected and state_manifest.current_final_gate_state is not None
                    else [],
                    comparison_summary=(
                        "Selected branch is the only branch eligible for final-gate evidence."
                        if selected
                        else "Non-selected branch keeps lineage but cannot support selected-branch final claims."
                    ),
                )
            )
    else:
        branches.append(
            AutoResearchProjectBranchRead(
                branch_id=f"branch:{run.id}:default",
                selected_direction_refs=[run.hypothesis_id or run.id],
                inherited_evidence_scope=[],
                invalidated_evidence=[
                    item.artifact_ref for item in state_manifest.migration_needed_artifacts
                ],
                branch_specific_artifacts=[
                    item.artifact_ref
                    for item in [
                        *state_manifest.active_artifacts,
                        *state_manifest.stale_artifacts,
                        *state_manifest.migration_needed_artifacts,
                    ]
                    if item.final_gate_relevance
                ],
                branch_readiness="selected",
                claim_ceiling=state_manifest.current_final_gate_state.claim_ceiling
                if state_manifest.current_final_gate_state is not None
                else None,
                final_gate_blockers=state_manifest.current_final_gate_state.blockers
                if state_manifest.current_final_gate_state is not None
                else [],
                comparison_summary="Default run branch; final gate is scoped to this run only.",
            )
        )
    selected_branch_id = (
        f"branch:{selected_candidate_id}"
        if selected_candidate_id
        else branches[0].branch_id
    )
    comparison = [
        {
            "branch_id": branch.branch_id,
            "performance": "not_selected_for_final_gate"
            if branch.branch_id != selected_branch_id
            else "available"
            if branch.branch_specific_artifacts
            else "not_available",
            "evidence_sufficiency": (
                "not_selected_for_final_gate"
                if branch.branch_id != selected_branch_id
                else "blocked"
                if branch.final_gate_blockers
                else "sufficient_for_current_gate_scope"
            ),
            "literature_benchmark_source_sufficiency": "requires_current_project_validation"
            if branch.invalidated_evidence
            else "current_project_artifacts_only",
            "risk": "migration_or_stale_artifacts"
            if branch.invalidated_evidence
            else "none_detected",
            "negative_evidence": branch.invalidated_evidence,
            "claim_ceiling": branch.claim_ceiling,
            "final_gate_blockers": branch.final_gate_blockers,
        }
        for branch in branches
    ]
    branch_state = AutoResearchProjectBranchStateRead(
        branch_state_id=f"branch_state:{run.project_id}:{run.id}",
        project_id=run.project_id,
        run_id=run.id,
        rebuilt_at=_utcnow(),
        policy_version=POLICY_VERSION,
        selected_branch_id=selected_branch_id,
        branches=branches,
        comparison=comparison,
        branch_state_path=project_branch_state_file_path(run.project_id, run.id),
    )
    return save_project_branch_state(branch_state) if persist else branch_state


def build_long_running_state(
    *,
    run: AutoResearchRunRead,
    registry: AutoResearchRunRegistryRead | None,
    execution: AutoResearchRunExecutionRead,
    package_status: AutoResearchOperatorPackageStatusRead | None,
    final_gate_status: AutoResearchOperatorFinalGateStatusRead | None,
    external_capabilities: AutoResearchExternalCapabilityManifestRead | None,
    operator_status: AutoResearchOperatorRunStatusRead | None = None,
    expected_fingerprints: dict[str, str] | None = None,
    persist: bool = True,
) -> tuple[
    AutoResearchProjectStateManifestRead,
    AutoResearchProjectTimelineRead,
    AutoResearchProjectRunbookRead,
    AutoResearchLongRunningAttemptLedgerRead,
    AutoResearchProjectBranchStateRead,
]:
    manifest = build_project_state_manifest(
        run=run,
        registry=registry,
        package_status=package_status,
        final_gate_status=final_gate_status,
        expected_fingerprints=expected_fingerprints,
        persist=persist,
    )
    timeline = build_project_timeline(
        run=run,
        registry=registry,
        execution=execution,
        state_manifest=manifest,
        external_capabilities=external_capabilities,
        persist=persist,
    )
    runbook = build_project_runbook(
        run=run,
        state_manifest=manifest,
        operator_status=operator_status,
        persist=persist,
    )
    attempts = build_attempt_ledger(
        run=run,
        execution=execution,
        operator_status=operator_status,
        external_capabilities=external_capabilities,
        persist=persist,
    )
    branches = build_branch_state(
        run=run,
        state_manifest=manifest,
        persist=persist,
    )
    return manifest, timeline, runbook, attempts, branches


def load_persisted_long_running_state(
    project_id: str,
    run_id: str,
) -> tuple[
    AutoResearchProjectStateManifestRead | None,
    AutoResearchProjectTimelineRead | None,
    AutoResearchProjectRunbookRead | None,
    AutoResearchLongRunningAttemptLedgerRead | None,
    AutoResearchProjectBranchStateRead | None,
]:
    return (
        load_project_state_manifest(project_id, run_id),
        load_project_timeline(project_id, run_id),
        load_project_runbook(project_id, run_id),
        load_long_running_attempt_ledger(project_id, run_id),
        load_project_branch_state(project_id, run_id),
    )
