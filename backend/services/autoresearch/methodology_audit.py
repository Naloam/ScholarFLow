from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from schemas.autoresearch import (
    AcceptanceStatistic,
    AutoResearchMethodologyAuditRead,
    AutoResearchReadinessCategory,
    AutoResearchReadinessCheckRead,
    AutoResearchResearchProtocolRead,
    AutoResearchRunRead,
    ResultArtifact,
)
from services.autoresearch.research_readiness import (
    real_literature_items,
    synthetic_literature_count,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _add_check(
    checks: list[AutoResearchReadinessCheckRead],
    *,
    check_id: str,
    category: AutoResearchReadinessCategory,
    passed: bool,
    summary: str,
    detail: str,
    required_for_final_publish: bool,
) -> None:
    checks.append(
        AutoResearchReadinessCheckRead(
            check_id=check_id,
            category=category,
            passed=passed,
            required_for_final_publish=required_for_final_publish,
            summary=summary,
            detail=detail,
        )
    )


def _artifact_system_names(artifact: ResultArtifact | None) -> set[str]:
    if artifact is None:
        return set()
    names: set[str] = set()
    for name in (artifact.best_system, artifact.objective_system):
        if name:
            names.add(name)
    for item in artifact.system_results:
        if item.system:
            names.add(item.system)
    for item in artifact.aggregate_system_results:
        if item.system:
            names.add(item.system)
    for sweep in artifact.sweep_results:
        for name in (sweep.best_system, sweep.objective_system):
            if name:
                names.add(name)
        for item in sweep.aggregate_system_results:
            if item.system:
                names.add(item.system)
    return names


def _observed_sweep_labels(artifact: ResultArtifact | None) -> list[str]:
    if artifact is None:
        return []
    labels = {item.label for item in artifact.sweep_results if item.label}
    labels.update(item.sweep_label for item in artifact.per_seed_results if item.sweep_label)
    evaluated = artifact.environment.get("sweeps_evaluated")
    if isinstance(evaluated, list):
        labels.update(str(item) for item in evaluated if item)
    selected = artifact.environment.get("selected_sweep")
    if selected:
        labels.add(str(selected))
    return sorted(labels)


def _observed_statistics(
    artifact: ResultArtifact | None,
    *,
    primary_metric: str | None,
) -> list[AcceptanceStatistic]:
    if artifact is None or primary_metric is None:
        return []
    observed: set[AcceptanceStatistic] = set()
    for item in artifact.aggregate_system_results:
        if primary_metric in item.mean_metrics:
            observed.add("mean")
        if primary_metric in item.std_metrics:
            observed.add("std")
        if primary_metric in item.confidence_intervals:
            observed.add("confidence_interval")
    order: list[AcceptanceStatistic] = ["mean", "std", "confidence_interval"]
    return [item for item in order if item in observed]


def _satisfied_acceptance_rule_ids(artifact: ResultArtifact | None) -> list[str]:
    if artifact is None:
        return []
    return sorted(
        {
            item.rule_id
            for item in artifact.acceptance_checks
            if item.rule_id and item.passed
        }
    )


def build_methodology_audit(
    run: AutoResearchRunRead,
    *,
    protocol: AutoResearchResearchProtocolRead,
) -> AutoResearchMethodologyAuditRead:
    artifact = run.artifact
    spec = run.spec
    publication_profile = protocol.execution_profile == "publication"
    primary_metric = protocol.primary_metric or (artifact.primary_metric if artifact is not None else None)
    completed_seed_count = len(artifact.per_seed_results) if artifact is not None else 0
    planned_sweep_labels = [item.label for item in spec.sweeps] if spec is not None else []
    observed_sweep_labels = _observed_sweep_labels(artifact)
    observed_systems = _artifact_system_names(artifact)
    planned_ablation_systems = list(protocol.ablation_systems)
    observed_ablation_systems = sorted(
        name for name in planned_ablation_systems if name in observed_systems
    )
    acceptance_rule_ids = list(protocol.acceptance_rule_ids)
    satisfied_acceptance_rule_ids = _satisfied_acceptance_rule_ids(artifact)
    required_statistics = list(protocol.required_statistics)
    observed_statistics = _observed_statistics(artifact, primary_metric=primary_metric)
    significance_test_count = len(artifact.significance_tests) if artifact is not None else 0
    adequately_powered_test_count = (
        sum(1 for item in artifact.significance_tests if item.adequately_powered is True)
        if artifact is not None
        else 0
    )
    power_analysis_reported_count = (
        sum(
            1
            for item in artifact.significance_tests
            if item.adequately_powered is not None
            or item.recommended_sample_count is not None
            or bool(item.power_detail)
        )
        if artifact is not None
        else 0
    )
    real_lit_count = len(real_literature_items(run))
    synthetic_count = synthetic_literature_count(run)
    unsupported_claim_count = 0
    partial_claim_count = 0
    if run.claim_evidence_matrix is not None:
        unsupported_claim_count = sum(
            1 for item in run.claim_evidence_matrix.entries if item.support_status == "unsupported"
        )
        partial_claim_count = sum(
            1 for item in run.claim_evidence_matrix.entries if item.support_status == "partial"
        )
    compile_ready = bool(run.paper_compile_report is not None and run.paper_compile_report.ready_for_compile)
    source_package_complete = bool(
        run.paper_compile_report is not None and run.paper_compile_report.source_package_complete
    )

    checks: list[AutoResearchReadinessCheckRead] = []
    _add_check(
        checks,
        check_id="protocol_complete",
        category="evidence",
        passed=protocol.complete,
        summary="The registered protocol is complete for the execution profile.",
        detail=(
            "Protocol complete."
            if protocol.complete
            else f"Protocol blockers={'; '.join(protocol.blockers) or 'none recorded'}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="minimum_seed_compliance",
        category="statistics",
        passed=completed_seed_count >= protocol.minimum_completed_seed_count,
        summary="Completed seeds meet the protocol minimum.",
        detail=(
            f"Completed seeds={completed_seed_count}; protocol minimum="
            f"{protocol.minimum_completed_seed_count}; planned seeds={protocol.planned_seed_count}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="planned_seed_coverage",
        category="statistics",
        passed=completed_seed_count >= protocol.planned_seed_count,
        summary="Completed seeds cover the full planned seed set.",
        detail=f"Completed seeds={completed_seed_count}; planned seeds={protocol.planned_seed_count}.",
        required_for_final_publish=False,
    )
    _add_check(
        checks,
        check_id="sweep_compliance",
        category="statistics",
        passed=not planned_sweep_labels or set(planned_sweep_labels).issubset(observed_sweep_labels),
        summary="Observed sweeps cover the planned sweep protocol.",
        detail=(
            f"Planned sweeps={', '.join(planned_sweep_labels) if planned_sweep_labels else 'none'}; "
            f"observed sweeps={', '.join(observed_sweep_labels) if observed_sweep_labels else 'none'}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="ablation_compliance",
        category="statistics",
        passed=set(planned_ablation_systems).issubset(observed_ablation_systems),
        summary="Observed systems cover planned ablations.",
        detail=(
            f"Observed ablations={len(observed_ablation_systems)}/{len(planned_ablation_systems)}; "
            f"planned={', '.join(planned_ablation_systems) if planned_ablation_systems else 'none'}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="acceptance_rule_compliance",
        category="evidence",
        passed=set(acceptance_rule_ids).issubset(satisfied_acceptance_rule_ids),
        summary="Artifact satisfies registered acceptance criteria.",
        detail=(
            f"Satisfied acceptance rules={len(satisfied_acceptance_rule_ids)}/{len(acceptance_rule_ids)}; "
            f"missing={', '.join(sorted(set(acceptance_rule_ids) - set(satisfied_acceptance_rule_ids))) or 'none'}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="required_statistics_observed",
        category="statistics",
        passed=set(required_statistics).issubset(observed_statistics),
        summary="Artifact reports statistics required by the protocol.",
        detail=(
            f"Required statistics={', '.join(required_statistics) if required_statistics else 'none'}; "
            f"observed={', '.join(observed_statistics) if observed_statistics else 'none'}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="significance_and_power_reported",
        category="statistics",
        passed=(
            (not protocol.significance_required or significance_test_count > 0)
            and (not protocol.power_analysis_required or power_analysis_reported_count > 0)
        ),
        summary="Artifact reports required significance and power evidence.",
        detail=(
            f"Significance tests={significance_test_count}; power analyses reported="
            f"{power_analysis_reported_count}; adequately powered tests={adequately_powered_test_count}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="literature_compliance",
        category="literature",
        passed=real_lit_count >= protocol.literature_minimum,
        summary="Run persists the real literature required by the protocol.",
        detail=(
            f"Real literature={real_lit_count}; synthetic literature={synthetic_count}; "
            f"minimum={protocol.literature_minimum}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="claim_evidence_compliance",
        category="evidence",
        passed=run.claim_evidence_matrix is not None and unsupported_claim_count == 0,
        summary="Claim-evidence matrix supports publish-facing claims.",
        detail=(
            f"Unsupported claims={unsupported_claim_count}; partial claims={partial_claim_count}."
            if run.claim_evidence_matrix is not None
            else "No claim-evidence matrix was persisted."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="paper_source_compliance",
        category="reproducibility",
        passed=compile_ready and source_package_complete,
        summary="Paper source package is complete and compile-ready.",
        detail=(
            f"compile_ready={compile_ready}; source_package_complete={source_package_complete}."
        ),
        required_for_final_publish=publication_profile,
    )

    required_checks = [item for item in checks if item.required_for_final_publish]
    blockers = [item.detail for item in required_checks if not item.passed]
    warnings = [item.detail for item in checks if not item.passed and not item.required_for_final_publish]
    passed_count = sum(1 for item in checks if item.passed)
    score = round(100 * passed_count / len(checks)) if checks else 0
    payload = {
        "audit_id": "methodology_audit_v1",
        "protocol_fingerprint": protocol.protocol_fingerprint,
        "execution_profile": protocol.execution_profile,
        "primary_metric": primary_metric,
        "planned_seed_count": protocol.planned_seed_count,
        "completed_seed_count": completed_seed_count,
        "minimum_completed_seed_count": protocol.minimum_completed_seed_count,
        "planned_sweep_labels": planned_sweep_labels,
        "observed_sweep_labels": observed_sweep_labels,
        "planned_ablation_systems": planned_ablation_systems,
        "observed_ablation_systems": observed_ablation_systems,
        "acceptance_rule_ids": acceptance_rule_ids,
        "satisfied_acceptance_rule_ids": satisfied_acceptance_rule_ids,
        "required_statistics": required_statistics,
        "observed_statistics": observed_statistics,
        "significance_test_count": significance_test_count,
        "adequately_powered_test_count": adequately_powered_test_count,
        "power_analysis_reported_count": power_analysis_reported_count,
        "real_literature_count": real_lit_count,
        "synthetic_literature_count": synthetic_count,
        "literature_minimum": protocol.literature_minimum,
        "unsupported_claim_count": unsupported_claim_count,
        "partial_claim_count": partial_claim_count,
        "compile_ready": compile_ready,
        "paper_source_package_complete": source_package_complete,
        "checks": [item.model_dump(mode="json") for item in checks],
        "score": score,
        "compliant": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchMethodologyAuditRead(
        generated_at=_utcnow(),
        audit_fingerprint=_fingerprint(payload),
        **payload,
    )
