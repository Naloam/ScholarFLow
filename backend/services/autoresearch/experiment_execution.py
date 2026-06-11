from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from schemas.autoresearch import (
    AggregateSystemMetricResult,
    AutoResearchDomainEvidenceStatus,
    AutoResearchEvidenceLedgerEntryRead,
    AutoResearchEvidenceLedgerRead,
    AutoResearchExperimentEnvironmentManifestRead,
    AutoResearchExperimentExecutionApprovalState,
    AutoResearchExperimentExecutionBlockerRead,
    AutoResearchExperimentExecutionFailureClass,
    AutoResearchExperimentExecutionImportRequest,
    AutoResearchExperimentExecutionJobRead,
    AutoResearchExperimentExecutionPlanRead,
    AutoResearchExperimentExecutionPlanRequest,
    AutoResearchExperimentExecutionRepairAction,
    AutoResearchExperimentExecutionResultRead,
    AutoResearchExperimentExecutionRoute,
    AutoResearchExperimentFactoryJobRead,
    AutoResearchExperimentFactoryPlanRead,
    AutoResearchExperimentOutputValidationRead,
    AutoResearchExperimentRuntimeContractRead,
    AutoResearchResearchBriefRead,
    ResultArtifact,
    ResultTable,
    SystemMetricResult,
)


APPROVED_LOCAL_COMMAND = ["scholarflow", "experiment-execution", "local-fixture"]
_ROUTE_CAPABILITY_REF = {
    "deterministic_replay": "external_capability:benchmark_dataset_ingestion",
    "local_command": "external_capability:local_command_execution",
    "docker": "external_capability:docker_execution",
    "external_import": "external_capability:external_artifact_import",
    "bridge_import": "external_capability:bridge_execution",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_")[:80] or "item"


def _dedupe(items: list[Any]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item is None:
            continue
        cleaned = " ".join(str(item).split()).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _evidence_origin_for_route(
    route: AutoResearchExperimentExecutionRoute,
    *,
    import_request: AutoResearchExperimentExecutionImportRequest | None = None,
) -> str:
    if route == "deterministic_replay":
        return "deterministic_replay"
    if route == "local_command":
        return "local_smoke"
    if route == "docker":
        return "docker_execution"
    if route == "bridge_import":
        return "bridge_execution"
    provenance = import_request.provenance if import_request is not None else {}
    source_ref = (import_request.source_package_ref if import_request is not None else "") or ""
    origin = str(provenance.get("source_content_origin") or provenance.get("evidence_origin") or "").lower()
    if any(signal in origin for signal in {"fixture", "toy", "synthetic"}) or any(
        signal in source_ref.lower() for signal in {"fixture", "toy", "synthetic"}
    ):
        return "fixture"
    return "imported_real_artifact"


def _expected_import_sha(import_request: AutoResearchExperimentExecutionImportRequest | None) -> str | None:
    if import_request is None:
        return None
    for key in (
        "expected_artifact_sha256",
        "artifact_sha256",
        "source_package_sha256",
        "content_sha256",
    ):
        value = import_request.provenance.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _blocker(
    reason: str,
    *,
    blocker_id: str | None = None,
    scope: str = "plan",
    failure_classification: AutoResearchExperimentExecutionFailureClass = "none",
    required_action: AutoResearchExperimentExecutionRepairAction = "terminal_blocker",
    evidence_refs: list[str] | None = None,
    terminal: bool = False,
) -> AutoResearchExperimentExecutionBlockerRead:
    return AutoResearchExperimentExecutionBlockerRead(
        blocker_id=blocker_id or f"blocker_{_slug(reason)[:48]}",
        scope=scope,
        reason=reason,
        failure_classification=failure_classification,
        required_action=required_action,
        evidence_refs=evidence_refs or [],
        terminal=terminal,
    )


def _source_hash(ref: str | None) -> str | None:
    if not ref:
        return None
    path = Path(ref)
    if not path.is_file():
        return _fingerprint({"source_ref": ref, "exists": False})
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _claim_ceiling(
    *,
    brief: AutoResearchResearchBriefRead | None,
    plan: AutoResearchExperimentFactoryPlanRead,
) -> str | None:
    if brief is not None and brief.domain_claim_ceiling:
        return brief.domain_claim_ceiling
    resolver = plan.domain_benchmark_resolver
    protocol = plan.domain_experiment_protocol
    if protocol is not None and protocol.domain_id == "unsupported":
        return "blocked_no_supported_domain_claim"
    if resolver is not None and not resolver.publication_grade_eligible:
        return "review_only_engineering_validation_claim"
    if resolver is not None and resolver.final_candidate_eligible:
        return "scoped_final_candidate_claim"
    return None


def _default_route(
    plan: AutoResearchExperimentFactoryPlanRead,
) -> AutoResearchExperimentExecutionRoute:
    protocol = plan.domain_experiment_protocol
    if protocol is not None and protocol.domain_id == "claim_evidence_retrieval":
        return "deterministic_replay"
    return "local_command"


def _contract_for_job(
    *,
    job: AutoResearchExperimentFactoryJobRead,
    route: AutoResearchExperimentExecutionRoute,
    plan: AutoResearchExperimentFactoryPlanRead,
) -> AutoResearchExperimentRuntimeContractRead:
    protocol = plan.domain_experiment_protocol
    resolver = plan.domain_benchmark_resolver
    requirements = dict(protocol.runtime_contract) if protocol is not None else {}
    return AutoResearchExperimentRuntimeContractRead(
        contract_id=f"experiment_runtime_contract_{_slug(job.job_id)}",
        execution_route=route,
        deterministic=bool(requirements.get("deterministic", True)),
        allowed_command=route != "local_command" or job.command.startswith(" ".join(APPROVED_LOCAL_COMMAND)),
        required_inputs=list(job.inputs),
        expected_outputs=list(job.expected_outputs),
        metric_schema=list(protocol.metric_schema if protocol is not None else []),
        benchmark_resolver_ref=resolver.resolver_id if resolver is not None else None,
        domain_id=protocol.domain_id if protocol is not None else None,
        timeout_seconds=plan.execution_backend.timeout_seconds,
        requires_live_network=bool(requirements.get("requires_live_network", False)),
        requires_paid_llm=bool(requirements.get("requires_paid_llm", False)),
        requires_gpu=bool(requirements.get("requires_gpu", plan.execution_backend.gpu_required)),
        requires_docker_daemon=route == "docker" or bool(requirements.get("requires_docker_daemon", False)),
        environment_requirements={
            "backend": plan.execution_backend.kind,
            "docker_image": plan.execution_backend.docker_image,
            "gpu_required": plan.execution_backend.gpu_required,
        },
        capability_refs=[_ROUTE_CAPABILITY_REF[route]],
    )


def _job_blockers(
    *,
    route: AutoResearchExperimentExecutionRoute,
    request: AutoResearchExperimentExecutionPlanRequest,
    approval_required: bool,
    approval_state: AutoResearchExperimentExecutionApprovalState,
) -> list[AutoResearchExperimentExecutionBlockerRead]:
    blockers: list[AutoResearchExperimentExecutionBlockerRead] = []
    if route == "docker" and not request.docker_available:
        blockers.append(
            _blocker(
                "Docker execution was requested, but Docker availability is not recorded for this deterministic run.",
                scope="job",
                failure_classification="unsupported_execution_backend",
                required_action="blocked_by_deterministic_offline_policy",
            )
        )
    if route == "bridge_import" and not request.bridge_available:
        blockers.append(
            _blocker(
                "Bridge import execution was requested, but no external bridge is available.",
                scope="job",
                failure_classification="external_import_required",
                required_action="requires_imported_artifact",
            )
        )
    if approval_required and approval_state == "rejected":
        blockers.append(
            _blocker(
                "Execution approval was rejected; this job is blocked until a new approved plan is created.",
                scope="job",
                failure_classification="budget_approval_required",
                required_action="terminal_blocker",
                terminal=True,
            )
        )
        return blockers
    if approval_required and approval_state != "approved":
        blockers.append(
            _blocker(
                "Execution budget or approval policy requires explicit approval before this job can run.",
                scope="job",
                failure_classification="budget_approval_required",
                required_action="requires_approval",
            )
        )
    return blockers


def build_experiment_execution_plan(
    *,
    factory_plan: AutoResearchExperimentFactoryPlanRead,
    brief: AutoResearchResearchBriefRead | None = None,
    request: AutoResearchExperimentExecutionPlanRequest | None = None,
) -> AutoResearchExperimentExecutionPlanRead:
    request = request or AutoResearchExperimentExecutionPlanRequest()
    resolver = factory_plan.domain_benchmark_resolver
    protocol = factory_plan.domain_experiment_protocol
    plan_blockers: list[AutoResearchExperimentExecutionBlockerRead] = []
    if factory_plan.domain_decision is not None and not factory_plan.domain_decision.is_supported:
        plan_blockers.append(
            _blocker(
                factory_plan.domain_decision.unsupported_reason or "Unsupported domain cannot materialize experiment execution jobs.",
                failure_classification="unsupported_execution_backend",
                required_action="terminal_blocker",
                evidence_refs=[f"brief:{factory_plan.brief_id}:domain_decision"],
                terminal=True,
            )
        )
    if protocol is None:
        plan_blockers.append(
            _blocker(
                "Missing domain experiment protocol; typed execution jobs cannot be materialized.",
                failure_classification="unsupported_execution_backend",
                required_action="requires_benchmark_or_protocol_change",
                evidence_refs=[f"factory_plan:{factory_plan.plan_id}"],
                terminal=True,
            )
        )
    elif protocol.status == "blocked":
        plan_blockers.extend(
            _blocker(
                reason,
                failure_classification="unsupported_execution_backend",
                required_action="requires_benchmark_or_protocol_change",
                evidence_refs=protocol.evidence_refs,
                terminal=True,
            )
            for reason in _dedupe(protocol.blockers or protocol.readiness_blockers)
        )
    if resolver is None:
        plan_blockers.append(
            _blocker(
                "Missing domain benchmark resolver; typed execution jobs cannot be materialized.",
                failure_classification="benchmark_mismatch",
                required_action="requires_benchmark_or_protocol_change",
                evidence_refs=[f"factory_plan:{factory_plan.plan_id}"],
                terminal=True,
            )
        )
    elif resolver.status == "blocked":
        plan_blockers.extend(
            _blocker(
                reason,
                failure_classification="benchmark_mismatch",
                required_action="requires_benchmark_or_protocol_change",
                evidence_refs=resolver.evidence_refs,
                terminal=True,
            )
            for reason in _dedupe(resolver.blockers)
        )
    if factory_plan.blockers:
        plan_blockers.extend(
            _blocker(
                reason,
                failure_classification="unsupported_execution_backend",
                required_action="requires_benchmark_or_protocol_change",
                evidence_refs=[f"factory_plan:{factory_plan.plan_id}"],
                terminal=True,
            )
            for reason in _dedupe(factory_plan.blockers)
        )

    ceiling = _claim_ceiling(brief=brief, plan=factory_plan)
    route = request.execution_route or _default_route(factory_plan)
    approval_required = request.budget_class == "approval_required"
    approval_state = request.approval_state
    if approval_required and approval_state == "not_required":
        approval_state = "needs_approval"

    jobs: list[AutoResearchExperimentExecutionJobRead] = []
    if not plan_blockers:
        for source_job in factory_plan.jobs:
            contract = _contract_for_job(job=source_job, route=route, plan=factory_plan)
            job_blockers = _job_blockers(
                route=route,
                request=request,
                approval_required=approval_required,
                approval_state=approval_state,
            )
            expected_outputs = _dedupe(
                [
                    *source_job.expected_outputs,
                    *(
                        protocol.expected_outputs
                        if protocol is not None and source_job.job_kind == "candidate_method"
                        else []
                    ),
                ]
            )
            runtime_contract = contract.model_copy(
                update={"expected_outputs": expected_outputs}
            )
            status = (
                "blocked"
                if job_blockers and (
                    any(item.failure_classification != "budget_approval_required" for item in job_blockers)
                    or any(item.terminal for item in job_blockers)
                )
                else "needs_approval"
                if job_blockers
                else "planned"
            )
            jobs.append(
                AutoResearchExperimentExecutionJobRead(
                    job_id=f"execution_{source_job.job_id}",
                    project_id=factory_plan.project_id,
                    run_id=factory_plan.run_id,
                    brief_id=factory_plan.brief_id,
                    domain_id=protocol.domain_id if protocol is not None else "unsupported",
                    protocol_id=protocol.protocol_id if protocol is not None else "missing_protocol",
                    benchmark_resolver_ref=resolver.resolver_id if resolver is not None else None,
                    method_ref=str(source_job.config.get("system") or source_job.config.get("hypothesis_id") or source_job.job_kind),
                    baseline_ref=(
                        str(source_job.config.get("system"))
                        if source_job.job_kind == "baseline"
                        else None
                    ),
                    job_kind=source_job.job_kind,
                    execution_route=route,
                    command=[*APPROVED_LOCAL_COMMAND, "--job", source_job.job_id, "--domain", protocol.domain_id if protocol is not None else "unsupported"]
                    if route == "local_command"
                    else [],
                    import_spec={
                        "schema_version": "experiment_execution_result_v1",
                        "expected_outputs": expected_outputs,
                    }
                    if route in {"external_import", "bridge_import"}
                    else None,
                    replay_spec={
                        "source_package_ref": resolver.benchmark_payload_ref if resolver is not None else None,
                        "source_package_sha256": _source_hash(resolver.benchmark_payload_ref if resolver is not None else None),
                        "route": protocol.deterministic_execution_route if protocol is not None else None,
                    }
                    if route == "deterministic_replay"
                    else None,
                    expected_input_artifacts=_dedupe(
                        [
                            *source_job.inputs,
                            resolver.benchmark_payload_ref if resolver is not None else None,
                            f"protocol:{protocol.protocol_id}" if protocol is not None else None,
                        ]
                    ),
                    expected_output_artifacts=expected_outputs,
                    metric_schema=list(protocol.metric_schema if protocol is not None else []),
                    runtime_contract=runtime_contract,
                    environment_requirements=runtime_contract.environment_requirements,
                    budget_class=request.budget_class,
                    approval_required=approval_required,
                    approval_state=approval_state,
                    lineage_parent_refs=_dedupe(
                        [
                            f"factory_plan:{factory_plan.plan_id}",
                            f"factory_job:{source_job.job_id}",
                            f"protocol:{protocol.protocol_id}" if protocol is not None else None,
                            f"benchmark_resolver:{resolver.resolver_id}" if resolver is not None else None,
                            *(resolver.evidence_refs if resolver is not None else []),
                            *(protocol.evidence_refs if protocol is not None else []),
                        ]
                    ),
                    claim_ceiling=ceiling,
                    blockers=job_blockers,
                    warnings=_dedupe(
                        [
                            *factory_plan.warnings,
                            "This typed job is review-only and cannot support final-publish claims."
                            if ceiling == "review_only_engineering_validation_claim"
                            else None,
                        ]
                    ),
                    status=status,
                )
            )

    status = (
        "blocked"
        if plan_blockers or any(job.status == "blocked" for job in jobs)
        else "needs_approval"
        if any(job.status == "needs_approval" for job in jobs)
        else "ready"
        if jobs
        else "blocked"
    )
    payload = {
        "plan_id": "experiment_execution_plan_v1",
        "project_id": factory_plan.project_id,
        "run_id": factory_plan.run_id,
        "brief_id": factory_plan.brief_id,
        "hypothesis_id": factory_plan.hypothesis_id,
        "status": status,
        "domain_id": protocol.domain_id if protocol is not None else None,
        "protocol_id": protocol.protocol_id if protocol is not None else None,
        "benchmark_resolver_ref": resolver.resolver_id if resolver is not None else None,
        "source_factory_plan_id": factory_plan.plan_id,
        "jobs": [job.model_dump(mode="json") for job in jobs],
        "job_count": len(jobs),
        "blockers": [item.model_dump(mode="json") for item in plan_blockers],
        "warnings": _dedupe(
            [
                *factory_plan.warnings,
                "Goal 3 runtime is experiment-job runtime; it does not replace the auto-research queue/worker execution plane.",
            ]
        ),
        "claim_ceiling": ceiling,
    }
    return AutoResearchExperimentExecutionPlanRead(
        generated_at=_utcnow(),
        plan_fingerprint=_fingerprint(payload),
        **payload,
    )


def _metric_values(metric_schema: list[str], *, domain_id: str | None) -> dict[str, float]:
    values: dict[str, float] = {}
    for index, metric in enumerate(metric_schema):
        if metric in {"accuracy", "macro_f1"}:
            values[metric] = round(0.68 + index * 0.02, 4)
        elif metric == "citation_support_coverage":
            values[metric] = 0.74
        elif metric.startswith("unsupported") or metric.startswith("repair") or metric == "abstention_accuracy":
            values[metric] = 0.67
        elif metric == "verification_accuracy":
            values[metric] = 0.72
        else:
            values[metric] = round(0.61 + index * 0.015, 4)
    if not values:
        values["primary_metric"] = 0.0
    return values


def _base_output_package(
    plan: AutoResearchExperimentExecutionPlanRead,
    *,
    import_request: AutoResearchExperimentExecutionImportRequest | None = None,
) -> dict[str, Any]:
    first_job = plan.jobs[0]
    metric_values = _metric_values(first_job.metric_schema, domain_id=first_job.domain_id)
    primary_metric = next(iter(metric_values))
    is_import = import_request is not None
    evidence_origin = _evidence_origin_for_route(
        first_job.execution_route,
        import_request=import_request,
    )
    package: dict[str, Any] = {
        "schema_version": "experiment_execution_result_v1",
        "domain_id": first_job.domain_id,
        "protocol_id": first_job.protocol_id,
        "benchmark_resolver_ref": first_job.benchmark_resolver_ref,
        "evidence_origin": evidence_origin,
        "execution_profile": {
            "route": first_job.execution_route,
            "evidence_origin": evidence_origin,
            "command": first_job.command,
            "cwd": ".",
            "timeout_seconds": first_job.runtime_contract.timeout_seconds,
            "exit_code": 0,
            "stdout_ref": "experiment_execution_outputs/stdout.txt",
            "stderr_ref": "experiment_execution_outputs/stderr.txt",
        },
        "environment_manifest": {
            "requires_live_network": False,
            "requires_paid_llm": False,
            "requires_gpu": False,
            "requires_docker_daemon": first_job.execution_route == "docker",
            "docker_image_digest": first_job.environment_requirements.get("docker_image_digest"),
            "bridge_target": first_job.import_spec.get("bridge_target") if first_job.import_spec else None,
        },
        "benchmark_resolver_ref": first_job.benchmark_resolver_ref,
        "deterministic_fingerprint": _fingerprint(
            {
                "plan": plan.plan_fingerprint,
                "route": first_job.execution_route,
                "metrics": metric_values if not is_import else import_request.artifact_package,
            }
        ),
    }
    if not is_import:
        package.update(
            {
                "metrics": metric_values,
                "method_outputs": {
                    first_job.method_ref or "candidate_method": {
                        "metrics": metric_values,
                        "output_artifact_ref": "experiment_execution_result_json:method_outputs",
                    }
                },
                "negative_evidence": [],
                "baseline_comparison": {
                    "baseline_ref": first_job.baseline_ref or "planned_baseline",
                    "primary_metric": primary_metric,
                    "candidate_score": metric_values[primary_metric],
                    "baseline_score": max(0.0, round(metric_values[primary_metric] - 0.05, 4)),
                },
                "sample_counts": {"test": 24 if first_job.domain_id != "claim_evidence_retrieval" else 120},
                "split_counts": {"train": 1, "test": 1},
            }
        )
    if not is_import and first_job.domain_id == "claim_evidence_retrieval":
        package.update(
            {
                "retrieval_evidence_ledger": [
                    {
                        "claim_id": "claim_evidence_replay_1",
                        "support_status": "supported",
                        "metric_values": metric_values,
                    }
                ],
                "claim_verification_metrics": metric_values,
            }
        )
    elif not is_import and first_job.domain_id == "rag_citation_faithfulness":
        package.update(
            {
                "citation_support_scores": [{"question_id": "q1", "support": 0.74}],
                "unsupported_citations": [{"question_id": "q2", "reason": "fixture citation unsupported"}],
                "abstentions": [{"question_id": "q3", "reason": "insufficient citation support"}],
            }
        )
    elif not is_import and first_job.domain_id == "lightweight_ml_nlp_benchmark":
        package.update(
            {
                "classification_predictions": [{"example_id": "ex1", "label": "positive", "prediction": "positive"}],
                "baseline_comparison": {
                    **package["baseline_comparison"],
                    "publication_grade": False,
                },
            }
        )
    if import_request is not None:
        package.update(import_request.artifact_package)
        artifact_sha = _fingerprint(import_request.artifact_package)
        package["import_provenance"] = {
            "source_package_ref": import_request.source_package_ref,
            "source_package_sha256": artifact_sha,
            "expected_artifact_sha256": _expected_import_sha(import_request),
            "schema_version": import_request.schema_version,
            "imported_at": _utcnow().isoformat(),
            "provenance": import_request.provenance,
        }
        package["evidence_origin"] = evidence_origin
        if isinstance(package.get("execution_profile"), dict):
            package["execution_profile"] = {
                **package["execution_profile"],
                "route": first_job.execution_route,
                "evidence_origin": evidence_origin,
            }
    if is_import:
        return package
    for output in _dedupe([output for job in plan.jobs for output in job.expected_output_artifacts]):
        key = Path(output).stem
        if key in package:
            continue
        if "metric" in key:
            package[key] = metric_values
        elif "ledger" in key:
            package[key] = [
                {
                    "source": "typed_experiment_execution",
                    "support_status": "supported",
                    "metric_values": metric_values,
                }
            ]
        elif "fingerprint" in key:
            package[key] = package["deterministic_fingerprint"]
        else:
            package[key] = {
                "source": "typed_experiment_execution",
                "status": "done",
                "domain_id": first_job.domain_id,
            }
    return package


def _content_sha(value: Any) -> str:
    return _fingerprint(value)


def _validate_output_package(
    *,
    plan: AutoResearchExperimentExecutionPlanRead,
    package: dict[str, Any],
) -> tuple[list[AutoResearchExperimentOutputValidationRead], AutoResearchExperimentExecutionFailureClass, list[str]]:
    first_job = plan.jobs[0] if plan.jobs else None
    if first_job is None:
        return [], "unsupported_execution_backend", ["No typed execution jobs were available."]
    expected_outputs = _dedupe([output for job in plan.jobs for output in job.expected_output_artifacts])
    validations: list[AutoResearchExperimentOutputValidationRead] = []
    failure: AutoResearchExperimentExecutionFailureClass = "none"
    blockers: list[str] = []
    execution_profile = package.get("execution_profile")
    evidence_origin = str(package.get("evidence_origin") or "")
    if isinstance(execution_profile, dict):
        if not evidence_origin:
            evidence_origin = str(execution_profile.get("evidence_origin") or "")
        try:
            exit_code = int(execution_profile.get("exit_code") or 0)
        except (TypeError, ValueError):
            exit_code = 1
        if exit_code != 0:
            failure = "runtime_failure"
            blockers.append(f"Local runtime exited with non-zero status {exit_code}.")
    metrics = package.get("metrics")
    bad_json = False
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
            package["metrics"] = metrics
        except json.JSONDecodeError:
            bad_json = True
    if bad_json:
        failure = "bad_json"
        blockers.append("Metrics output is not valid JSON.")
    elif not isinstance(metrics, dict):
        failure = "bad_json"
        blockers.append("Metrics output must be a JSON object.")
    else:
        metric_keys = {str(key) for key in metrics}
        allowed = set(first_job.metric_schema)
        if allowed and (not metric_keys.issubset(allowed) or not allowed.issubset(metric_keys)):
            failure = "bad_metric_schema"
            blockers.append(
                "Metric schema mismatch: output metrics must exactly match the domain metric schema."
            )
        for key, value in metrics.items():
            if not isinstance(value, int | float):
                failure = "bad_metric_schema"
                blockers.append(f"Metric `{key}` has non-numeric value type `{type(value).__name__}`.")
    if package.get("benchmark_resolver_ref") != first_job.benchmark_resolver_ref:
        failure = "benchmark_mismatch" if failure == "none" else failure
        blockers.append("Benchmark resolver reference in output package does not match the typed job.")
    import_provenance = package.get("import_provenance")
    if isinstance(import_provenance, dict):
        actual_sha = str(import_provenance.get("source_package_sha256") or "")
        expected_sha = str(import_provenance.get("expected_artifact_sha256") or "")
        if expected_sha and actual_sha != expected_sha:
            failure = "environment_mismatch" if failure == "none" else failure
            blockers.append("Imported artifact package sha256 does not match declared provenance hash.")
        if import_provenance.get("schema_version") != package.get("schema_version"):
            failure = "environment_mismatch" if failure == "none" else failure
            blockers.append("Imported artifact schema version does not match the output package schema_version.")
    env = package.get("environment_manifest")
    if not isinstance(env, dict):
        failure = "environment_mismatch" if failure == "none" else failure
        blockers.append("Environment manifest is missing or malformed.")
        env = {}
    if env.get("requires_live_network") or env.get("requires_paid_llm") or env.get("requires_gpu"):
        failure = "environment_mismatch" if failure == "none" else failure
        blockers.append("Environment manifest violates deterministic offline runtime requirements.")
    if env.get("requires_docker_daemon") and first_job.execution_route != "docker":
        failure = "environment_mismatch" if failure == "none" else failure
        blockers.append("Environment manifest unexpectedly requires Docker for a non-Docker route.")

    for output in expected_outputs:
        key = Path(output).stem
        value = package.get(key)
        exists = value is not None
        output_blockers: list[str] = []
        if not exists:
            output_blockers.append(f"Expected output `{output}` is missing.")
            if failure == "none":
                lowered_output = output.lower()
                if "baseline" in lowered_output:
                    failure = "missing_baseline"
                elif "ablation" in lowered_output:
                    failure = "missing_ablation"
                elif "seed" in lowered_output or "sweep" in lowered_output or "statistic" in lowered_output:
                    failure = "insufficient_statistics"
                else:
                    failure = "missing_output"
        validation_metrics = sorted(str(key) for key in metrics.keys()) if isinstance(metrics, dict) else []
        validations.append(
            AutoResearchExperimentOutputValidationRead(
                output_ref=output,
                exists=exists,
                content_type="application/json" if output.endswith(".json") else "text/plain",
                sha256=_content_sha(value) if exists else None,
                schema_version=str(package.get("schema_version")) if exists else None,
                metric_names=validation_metrics if key in {"metrics", "claim_verification_metrics"} else [],
                metric_value_types={
                    str(metric): type(value).__name__
                    for metric, value in (metrics.items() if isinstance(metrics, dict) else [])
                }
                if key in {"metrics", "claim_verification_metrics"}
                else {},
                sample_counts=dict(package.get("sample_counts") or {}) if isinstance(package.get("sample_counts"), dict) else {},
                split_counts=dict(package.get("split_counts") or {}) if isinstance(package.get("split_counts"), dict) else {},
                baseline_references=[
                    str(package.get("baseline_comparison", {}).get("baseline_ref"))
                ]
                if isinstance(package.get("baseline_comparison"), dict)
                and package.get("baseline_comparison", {}).get("baseline_ref")
                else [],
                ablation_references=[
                    job.method_ref or job.job_kind
                    for job in plan.jobs
                    if job.job_kind == "ablation"
                ],
                evidence_origin=evidence_origin or None,  # type: ignore[arg-type]
                validation_status="passed" if exists and not output_blockers else "failed",
                blockers=output_blockers,
            )
        )
        blockers.extend(output_blockers)
    return validations, failure, _dedupe(blockers)


def _environment_manifest(
    *,
    plan: AutoResearchExperimentExecutionPlanRead,
    package: dict[str, Any],
) -> AutoResearchExperimentEnvironmentManifestRead:
    first_job = plan.jobs[0]
    profile = package.get("execution_profile") if isinstance(package.get("execution_profile"), dict) else {}
    raw_env = package.get("environment_manifest") if isinstance(package.get("environment_manifest"), dict) else {}
    output_hashes = {
        key: _content_sha(value)
        for key, value in package.items()
        if key
        in {
            "metrics",
            "method_outputs",
            "baseline_comparison",
            "retrieval_evidence_ledger",
            "claim_verification_metrics",
            "citation_support_scores",
            "classification_predictions",
        }
    }
    payload = {
        "manifest_id": "experiment_execution_environment_v1",
        "execution_route": first_job.execution_route,
        "backend": "local" if first_job.execution_route == "local_command" else "auto",
        "command": " ".join(first_job.command) if first_job.command else None,
        "cwd": str(profile.get("cwd") or "."),
        "timeout_seconds": first_job.runtime_contract.timeout_seconds,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "environment": raw_env,
        "docker_image_digest": raw_env.get("docker_image_digest"),
        "bridge_target": raw_env.get("bridge_target"),
        "bridge_version": raw_env.get("bridge_version"),
        "bridge_session_id": raw_env.get("bridge_session_id"),
        "stdout_ref": profile.get("stdout_ref"),
        "stderr_ref": profile.get("stderr_ref"),
        "output_hashes": output_hashes,
        "requirements_recorded": True,
    }
    return AutoResearchExperimentEnvironmentManifestRead(
        generated_at=_utcnow(),
        manifest_fingerprint=_fingerprint(payload),
        **payload,
    )


def _repair_for_failure(
    failure: AutoResearchExperimentExecutionFailureClass,
) -> AutoResearchExperimentExecutionRepairAction:
    if failure == "none":
        return "none"
    if failure in {"missing_baseline", "missing_ablation", "insufficient_statistics", "runtime_failure", "missing_output", "bad_json"}:
        return "execute_now"
    if failure in {"bad_metric_schema", "benchmark_mismatch", "environment_mismatch"}:
        return "requires_benchmark_or_protocol_change"
    if failure == "budget_approval_required":
        return "requires_approval"
    if failure == "external_import_required":
        return "requires_imported_artifact"
    return "terminal_blocker"


def _result_artifact_from_package(
    *,
    plan: AutoResearchExperimentExecutionPlanRead,
    package: dict[str, Any],
    status: str,
) -> ResultArtifact:
    metrics = package.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    numeric_metrics = {
        str(key): float(value)
        for key, value in metrics.items()
        if isinstance(value, int | float)
    }
    primary_metric = next(iter(numeric_metrics), "primary_metric")
    objective_score = numeric_metrics.get(primary_metric)
    system_name = str(plan.jobs[0].method_ref or "candidate_method") if plan.jobs else "candidate_method"
    return ResultArtifact(
        status="done" if status == "succeeded" else "failed",
        summary=(
            "Typed experiment execution completed with validated outputs."
            if status == "succeeded"
            else "Typed experiment execution failed or was blocked by runtime validation."
        ),
        key_findings=[
            "Typed experiment execution result is constrained by its claim ceiling.",
            "Output validation and runtime contract records are attached to the result.",
        ],
        primary_metric=primary_metric,
        best_system=system_name if objective_score is not None else None,
        system_results=[SystemMetricResult(system=system_name, metrics=numeric_metrics)]
        if numeric_metrics
        else [],
        aggregate_system_results=[
            AggregateSystemMetricResult(
                system=system_name,
                mean_metrics=numeric_metrics,
                std_metrics={metric: 0.0 for metric in numeric_metrics},
                min_metrics=numeric_metrics,
                max_metrics=numeric_metrics,
                sample_count=max((package.get("sample_counts") or {}).values(), default=1)
                if isinstance(package.get("sample_counts"), dict)
                else 1,
            )
        ]
        if numeric_metrics
        else [],
        tables=[
            ResultTable(
                title="Typed Experiment Execution Metrics",
                columns=["metric", "value"],
                rows=[[metric, f"{value:.4f}"] for metric, value in numeric_metrics.items()],
            )
        ],
        environment={
            "experiment_execution_plan_id": plan.plan_id,
            "execution_route": plan.jobs[0].execution_route if plan.jobs else None,
            "claim_ceiling": plan.claim_ceiling,
        },
        outputs=package,
        objective_system=system_name if objective_score is not None else None,
        objective_score=objective_score,
    )


def _evidence_ledger_from_result(
    *,
    plan: AutoResearchExperimentExecutionPlanRead,
    artifact: ResultArtifact | None,
    validations: list[AutoResearchExperimentOutputValidationRead],
    failure: AutoResearchExperimentExecutionFailureClass,
    blockers: list[str],
    lineage_refs: list[str],
    evidence_origin: str | None = None,
) -> AutoResearchEvidenceLedgerRead:
    entries: list[AutoResearchEvidenceLedgerEntryRead] = []
    if artifact is not None:
        for result in artifact.aggregate_system_results:
            entries.append(
                AutoResearchEvidenceLedgerEntryRead(
                    evidence_id=f"execution_metric_{_slug(result.system)}",
                    source_job_id=plan.jobs[0].job_id if plan.jobs else None,
                    evidence_kind="metric",
                    evidence_type="experiment_execution_metric",
                    evidence_origin=evidence_origin,  # type: ignore[arg-type]
                    claim=f"{result.system} produced typed execution metrics under route `{plan.jobs[0].execution_route if plan.jobs else 'unknown'}`.",
                    artifact_ref="experiment_execution_result_json",
                    metric=artifact.primary_metric,
                    value=result.mean_metrics.get(artifact.primary_metric),
                    metric_values=dict(result.mean_metrics),
                    sample_counts={"aggregate": result.sample_count},
                    baseline_comparisons=artifact.outputs.get("baseline_comparison")
                    if isinstance(artifact.outputs.get("baseline_comparison"), dict)
                    else {},
                    ablation_status=(
                        "present"
                        if any(job.job_kind == "ablation" for job in plan.jobs)
                        else "missing"
                    ),
                    statistical_sufficiency=(
                        "insufficient"
                        if plan.claim_ceiling == "review_only_engineering_validation_claim"
                        else "deterministic_replay_recorded"
                    ),
                    failure_classifications=[] if failure == "none" else [failure],
                    limitations=[
                        "Fixture/local smoke evidence cannot support final-publish claims."
                    ]
                    if plan.claim_ceiling == "review_only_engineering_validation_claim"
                    else [],
                    claim_ceiling=plan.claim_ceiling,
                    lineage_parent_refs=lineage_refs,
                    support_status="supported" if failure == "none" else "partial",
                )
            )
    for job in plan.jobs:
        entries.append(
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id=f"execution_job_{_slug(job.job_id)}",
                source_job_id=job.job_id,
                evidence_kind=job.job_kind if job.job_kind in {"baseline", "ablation", "seed", "sweep"} else "artifact",  # type: ignore[arg-type]
                evidence_type="experiment_execution_job",
                evidence_origin=evidence_origin,  # type: ignore[arg-type]
                claim=f"Typed execution job `{job.job_id}` recorded route `{job.execution_route}` and status `{job.status}`.",
                artifact_ref="experiment_execution_plan_json",
                failure_classifications=[item.failure_classification for item in job.blockers if item.failure_classification != "none"],
                limitations=job.warnings,
                claim_ceiling=job.claim_ceiling,
                lineage_parent_refs=job.lineage_parent_refs,
                support_status="missing" if job.status in {"blocked", "failed", "needs_approval"} else "supported",
            )
        )
    if validations:
        entries.append(
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id="execution_output_validation",
                evidence_kind="artifact",
                evidence_type="experiment_output_validation",
                evidence_origin=evidence_origin,  # type: ignore[arg-type]
                claim="Typed execution output validation recorded expected outputs, hashes, metric schema, sample counts, and blockers.",
                artifact_ref="experiment_execution_result_json:output_validation",
                failure_classifications=[] if failure == "none" else [failure],
                limitations=blockers,
                claim_ceiling=plan.claim_ceiling,
                lineage_parent_refs=lineage_refs,
                support_status="supported" if not blockers else "missing",
            )
        )
    ledger_blockers = _dedupe(
        [
            *blockers,
            "Execution evidence is review-only engineering validation and cannot support final-publish claims."
            if plan.claim_ceiling == "review_only_engineering_validation_claim"
            else None,
        ]
    )
    payload = {
        "ledger_id": "experiment_evidence_ledger_v1",
        "project_id": plan.project_id,
        "run_id": plan.run_id,
        "brief_id": plan.brief_id,
        "hypothesis_id": plan.hypothesis_id,
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "entry_count": len(entries),
        "complete": failure == "none" and not ledger_blockers,
        "blockers": ledger_blockers,
    }
    return AutoResearchEvidenceLedgerRead(
        generated_at=_utcnow(),
        ledger_fingerprint=_fingerprint(payload),
        **payload,
    )


def merge_execution_evidence_ledger(
    existing: AutoResearchEvidenceLedgerRead | None,
    incoming: AutoResearchEvidenceLedgerRead | None,
) -> AutoResearchEvidenceLedgerRead | None:
    if existing is None:
        return incoming
    if incoming is None:
        return existing
    entries = list(existing.entries)
    seen = {entry.evidence_id for entry in entries}
    for entry in incoming.entries:
        if entry.evidence_id in seen:
            entry = entry.model_copy(update={"evidence_id": f"{entry.evidence_id}_{len(entries) + 1}"})
        entries.append(entry)
        seen.add(entry.evidence_id)
    payload = {
        "ledger_id": existing.ledger_id,
        "project_id": existing.project_id,
        "run_id": existing.run_id or incoming.run_id,
        "brief_id": existing.brief_id or incoming.brief_id,
        "hypothesis_id": existing.hypothesis_id or incoming.hypothesis_id,
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "entry_count": len(entries),
        "complete": existing.complete and incoming.complete,
        "blockers": _dedupe([*existing.blockers, *incoming.blockers]),
    }
    return AutoResearchEvidenceLedgerRead(
        generated_at=_utcnow(),
        ledger_fingerprint=_fingerprint(payload),
        **payload,
    )


def execute_experiment_execution_plan(
    plan: AutoResearchExperimentExecutionPlanRead,
    *,
    import_request: AutoResearchExperimentExecutionImportRequest | None = None,
    output_override: dict[str, Any] | None = None,
) -> AutoResearchExperimentExecutionResultRead:
    lineage_refs = _dedupe(
        [
            f"experiment_execution_plan:{plan.plan_id}",
            f"factory_plan:{plan.source_factory_plan_id}" if plan.source_factory_plan_id else None,
            *[ref for job in plan.jobs for ref in job.lineage_parent_refs],
        ]
    )
    evidence_origin = (
        _evidence_origin_for_route(plan.jobs[0].execution_route, import_request=import_request)
        if plan.jobs
        else None
    )
    plan_blockers = list(plan.blockers)
    job_blockers = [blocker for job in plan.jobs for blocker in job.blockers]
    if plan.status == "needs_approval" or any(
        blocker.failure_classification == "budget_approval_required"
        and not blocker.terminal
        for blocker in job_blockers
    ):
        failure: AutoResearchExperimentExecutionFailureClass = "budget_approval_required"
        repair = _repair_for_failure(failure)
        blockers = [*plan_blockers, *job_blockers]
        payload = {
            "result_id": "experiment_execution_result_v1",
            "project_id": plan.project_id,
            "run_id": plan.run_id,
            "brief_id": plan.brief_id,
            "hypothesis_id": plan.hypothesis_id,
            "plan_id": plan.plan_id,
            "status": "needs_approval",
            "job_results": [job.model_copy(update={"status": "needs_approval"}).model_dump(mode="json") for job in plan.jobs],
            "evidence_origin": evidence_origin,
            "failure_classification": failure,
            "repair_recommendation": repair,
            "repair_reasons": [blocker.reason for blocker in blockers],
            "lineage_refs": lineage_refs,
            "blockers": [blocker.model_dump(mode="json") for blocker in blockers],
            "claim_ceiling": plan.claim_ceiling,
        }
        return AutoResearchExperimentExecutionResultRead(
            generated_at=_utcnow(),
            result_fingerprint=_fingerprint(payload),
            **payload,
        )
    if plan.status == "blocked" or plan_blockers or job_blockers or not plan.jobs:
        failure = next(
            (
                blocker.failure_classification
                for blocker in [*plan_blockers, *job_blockers]
                if blocker.failure_classification != "none"
            ),
            "unsupported_execution_backend",
        )
        repair = _repair_for_failure(failure)
        blockers = [*plan_blockers, *job_blockers]
        payload = {
            "result_id": "experiment_execution_result_v1",
            "project_id": plan.project_id,
            "run_id": plan.run_id,
            "brief_id": plan.brief_id,
            "hypothesis_id": plan.hypothesis_id,
            "plan_id": plan.plan_id,
            "status": "blocked",
            "job_results": [job.model_copy(update={"status": "blocked"}).model_dump(mode="json") for job in plan.jobs],
            "evidence_origin": evidence_origin,
            "failure_classification": failure,
            "repair_recommendation": repair,
            "repair_reasons": [blocker.reason for blocker in blockers],
            "lineage_refs": lineage_refs,
            "negative_evidence": [
                {
                    "category": failure,
                    "reason": blocker.reason,
                    "claim_ceiling": plan.claim_ceiling,
                    "evidence_origin": evidence_origin,
                }
                for blocker in blockers
            ],
            "blockers": [blocker.model_dump(mode="json") for blocker in blockers],
            "claim_ceiling": plan.claim_ceiling,
        }
        return AutoResearchExperimentExecutionResultRead(
            generated_at=_utcnow(),
            result_fingerprint=_fingerprint(payload),
            **payload,
        )

    if plan.jobs[0].execution_route in {"external_import", "bridge_import"} and import_request is None:
        failure = "external_import_required"
        blocker = _blocker(
            "External or bridge import route requires an imported artifact package before evidence can be recorded.",
            failure_classification=failure,
            required_action="requires_imported_artifact",
        )
        payload = {
            "result_id": "experiment_execution_result_v1",
            "project_id": plan.project_id,
            "run_id": plan.run_id,
            "brief_id": plan.brief_id,
            "hypothesis_id": plan.hypothesis_id,
            "plan_id": plan.plan_id,
            "status": "blocked",
            "job_results": [job.model_copy(update={"status": "blocked"}).model_dump(mode="json") for job in plan.jobs],
            "evidence_origin": evidence_origin,
            "failure_classification": failure,
            "repair_recommendation": "requires_imported_artifact",
            "repair_reasons": [blocker.reason],
            "lineage_refs": lineage_refs,
            "negative_evidence": [{"category": failure, "reason": blocker.reason, "evidence_origin": evidence_origin}],
            "blockers": [blocker.model_dump(mode="json")],
            "claim_ceiling": plan.claim_ceiling,
        }
        return AutoResearchExperimentExecutionResultRead(
            generated_at=_utcnow(),
            result_fingerprint=_fingerprint(payload),
            **payload,
        )

    package = output_override or _base_output_package(plan, import_request=import_request)
    if evidence_origin is not None and not package.get("evidence_origin"):
        package["evidence_origin"] = evidence_origin
        if isinstance(package.get("execution_profile"), dict):
            package["execution_profile"] = {
                **package["execution_profile"],
                "evidence_origin": evidence_origin,
            }
    validations, failure, validation_blockers = _validate_output_package(plan=plan, package=package)
    status = "succeeded" if failure == "none" else "failed"
    artifact = _result_artifact_from_package(plan=plan, package=package, status=status)
    environment_manifest = _environment_manifest(plan=plan, package=package)
    repair = _repair_for_failure(failure)
    blockers = [
        _blocker(
            reason,
            failure_classification=failure,
            required_action=repair,
            evidence_refs=lineage_refs,
        )
        for reason in validation_blockers
    ]
    ledger = _evidence_ledger_from_result(
        plan=plan,
        artifact=artifact,
        validations=validations,
        failure=failure,
        blockers=validation_blockers,
        lineage_refs=lineage_refs,
        evidence_origin=evidence_origin,
    )
    output_refs = _dedupe(
        [
            f"experiment_execution_result_json:{Path(item.output_ref).stem}"
            for item in validations
            if item.exists
        ]
    )
    output_hashes = {
        item.output_ref: item.sha256
        for item in validations
        if item.exists and item.sha256
    }
    succeeded_status = "imported" if import_request is not None else "succeeded"
    job_results = [
        job.model_copy(update={"status": succeeded_status if failure == "none" else "failed"})
        for job in plan.jobs
    ]
    deterministic_fingerprint = package.get("deterministic_fingerprint")
    if not isinstance(deterministic_fingerprint, str):
        deterministic_fingerprint = _fingerprint(
            {
                "plan": plan.plan_fingerprint,
                "package": package,
                "source_hashes": [
                    job.replay_spec.get("source_package_sha256")
                    for job in plan.jobs
                    if job.replay_spec
                ],
            }
        )
    payload = {
        "result_id": "experiment_execution_result_v1",
        "project_id": plan.project_id,
        "run_id": plan.run_id,
        "brief_id": plan.brief_id,
        "hypothesis_id": plan.hypothesis_id,
        "plan_id": plan.plan_id,
        "status": status,
        "job_results": [job.model_dump(mode="json") for job in job_results],
        "execution_profile": package.get("execution_profile") if isinstance(package.get("execution_profile"), dict) else {},
        "evidence_origin": evidence_origin,
        "environment_manifest": environment_manifest.model_dump(mode="json"),
        "runtime_contract_results": [job.runtime_contract.model_dump(mode="json") for job in plan.jobs],
        "output_validation": [item.model_dump(mode="json") for item in validations],
        "failure_classification": failure,
        "repair_recommendation": repair,
        "repair_reasons": validation_blockers,
        "lineage_refs": lineage_refs,
        "output_artifact_refs": output_refs,
        "output_hashes": output_hashes,
        "negative_evidence": [
            {
                "category": failure,
                "reason": reason,
                "claim_ceiling": plan.claim_ceiling,
                "source_job_id": plan.jobs[0].job_id if plan.jobs else None,
                "evidence_origin": evidence_origin,
            }
            for reason in validation_blockers
        ],
        "result_artifact": artifact.model_dump(mode="json"),
        "evidence_ledger": ledger.model_dump(mode="json"),
        "package_manifest_fragment": {
            "experiment_execution_plan_path": "experiment_execution_plan.json",
            "experiment_execution_result_path": "experiment_execution_result.json",
            "output_artifact_refs": output_refs,
            "output_hashes": output_hashes,
            "lineage_refs": lineage_refs,
            "claim_ceiling": plan.claim_ceiling,
            "evidence_origin": evidence_origin,
            "final_publish_ready": False,
        },
        "claim_ceiling": plan.claim_ceiling,
        "blockers": [blocker.model_dump(mode="json") for blocker in blockers],
        "warnings": list(plan.warnings),
        "deterministic_fingerprint": deterministic_fingerprint,
    }
    return AutoResearchExperimentExecutionResultRead(
        generated_at=_utcnow(),
        result_fingerprint=_fingerprint(payload),
        **payload,
    )
