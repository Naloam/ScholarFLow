from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchReadinessCategory,
    AutoResearchReadinessCheckRead,
    AutoResearchResearchProtocolRead,
    AutoResearchRunRead,
)
from services.autoresearch.research_readiness import (
    PUBLICATION_MIN_COMPLETED_SEEDS,
    PUBLICATION_MIN_REAL_LITERATURE,
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
    required_for_final_publish: bool = True,
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


def build_research_protocol(run: AutoResearchRunRead) -> AutoResearchResearchProtocolRead:
    spec = run.spec
    plan = run.plan
    profile = run.request.execution_profile if run.request is not None else "exploratory"
    publication_profile = profile == "publication"
    minimum_completed_seed_count = PUBLICATION_MIN_COMPLETED_SEEDS if publication_profile else 1
    literature_minimum = PUBLICATION_MIN_REAL_LITERATURE if publication_profile else 1
    primary_metric = spec.metrics[0].name if spec is not None and spec.metrics else None
    baseline_systems = [item.name for item in spec.baselines] if spec is not None else []
    ablation_systems = [item.name for item in spec.ablations] if spec is not None else []
    acceptance_rules = spec.acceptance_criteria if spec is not None else []
    required_statistics = sorted(
        {
            statistic
            for rule in acceptance_rules
            for statistic in rule.required_statistics
        }
    )
    planned_seed_count = len(spec.seeds) if spec is not None else 0
    planned_sweep_count = len(spec.sweeps) if spec is not None else 0
    benchmark_publication_grade = bool(spec is not None and spec.dataset.publication_grade)
    has_dataset_provenance = bool(
        spec is not None
        and (
            spec.dataset.source_url
            or spec.dataset.source_dataset_id
            or spec.dataset.source_fingerprint
        )
    )
    checks: list[AutoResearchReadinessCheckRead] = []
    _add_check(
        checks,
        check_id="hypothesis_registered",
        category="evidence",
        passed=bool(spec is not None and spec.hypothesis.strip()),
        summary="Protocol registers a falsifiable hypothesis.",
        detail=spec.hypothesis if spec is not None else "No experiment spec is available.",
    )
    _add_check(
        checks,
        check_id="primary_metric_registered",
        category="statistics",
        passed=bool(primary_metric),
        summary="Protocol registers a primary metric.",
        detail=f"Primary metric={primary_metric or 'missing'}.",
    )
    _add_check(
        checks,
        check_id="baseline_plan_registered",
        category="statistics",
        passed=bool(baseline_systems),
        summary="Protocol registers baseline systems.",
        detail=f"Baselines={', '.join(baseline_systems) if baseline_systems else 'none'}.",
    )
    _add_check(
        checks,
        check_id="seed_protocol_registered",
        category="statistics",
        passed=planned_seed_count >= minimum_completed_seed_count,
        summary="Protocol registers enough planned seeds for its execution profile.",
        detail=(
            f"Planned seeds={planned_seed_count}; required completed seeds for profile "
            f"`{profile}`={minimum_completed_seed_count}."
        ),
    )
    _add_check(
        checks,
        check_id="ablation_or_sensitivity_plan_registered",
        category="statistics",
        passed=bool(ablation_systems),
        summary="Protocol registers ablation or sensitivity analysis.",
        detail=f"Planned ablations={', '.join(ablation_systems) if ablation_systems else 'none'}.",
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="acceptance_rules_registered",
        category="evidence",
        passed=bool(acceptance_rules),
        summary="Protocol registers acceptance criteria.",
        detail=f"Acceptance rules={len(acceptance_rules)}.",
    )
    _add_check(
        checks,
        check_id="benchmark_provenance_registered",
        category="benchmark",
        passed=(benchmark_publication_grade and has_dataset_provenance) if publication_profile else spec is not None,
        summary="Protocol registers benchmark provenance suitable for the execution profile.",
        detail=(
            f"publication_grade={benchmark_publication_grade}; "
            f"source_kind={spec.dataset.source_kind if spec is not None else 'missing'}; "
            f"source_url={spec.dataset.source_url if spec is not None else None}; "
            f"source_dataset_id={spec.dataset.source_dataset_id if spec is not None else None}."
        ),
        required_for_final_publish=publication_profile,
    )
    required_checks = [item for item in checks if item.required_for_final_publish]
    blockers = [item.detail for item in required_checks if not item.passed]
    warnings = [item.detail for item in checks if not item.passed and not item.required_for_final_publish]
    threat_model = [
        "Benchmark scope limits external validity beyond the persisted dataset and task family.",
        "Seed count and effect sizes determine whether observed gains can support stability claims.",
        "Ablation coverage constrains mechanism and contribution claims.",
        "Literature coverage constrains novelty and related-work positioning.",
        "Compile-ready paper sources and artifact hashes are required for independent audit.",
    ]
    evidence_requirements = [
        "Persist run/spec/artifact snapshots before review.",
        "Map publish-facing claims to claim-evidence entries.",
        "Preserve aggregate metrics, per-seed results, and significance tests.",
        "Preserve paper sources and compile readiness reports.",
    ]
    reproducibility_requirements = [
        "Record requested seeds and sweep labels.",
        "Preserve candidate code and selected candidate manifest.",
        "Persist benchmark provenance and dataset fingerprint.",
        "Keep review, readiness, and protocol artifacts in the export bundle.",
    ]
    payload = {
        "protocol_id": "research_protocol_v1",
        "execution_profile": profile,
        "topic": run.topic,
        "title": plan.title if plan is not None else None,
        "task_family": run.task_family,
        "benchmark_name": spec.benchmark_name if spec is not None else None,
        "benchmark_publication_grade": benchmark_publication_grade,
        "dataset_source_kind": spec.dataset.source_kind if spec is not None else None,
        "dataset_source_url": spec.dataset.source_url if spec is not None else None,
        "dataset_source_dataset_id": spec.dataset.source_dataset_id if spec is not None else None,
        "dataset_fingerprint": spec.dataset.source_fingerprint if spec is not None else None,
        "hypothesis": spec.hypothesis if spec is not None else None,
        "research_questions": plan.research_questions if plan is not None else [],
        "primary_metric": primary_metric,
        "baseline_systems": baseline_systems,
        "ablation_systems": ablation_systems,
        "planned_seed_count": planned_seed_count,
        "minimum_completed_seed_count": minimum_completed_seed_count,
        "planned_sweep_count": planned_sweep_count,
        "acceptance_rule_count": len(acceptance_rules),
        "acceptance_rule_ids": [item.id for item in acceptance_rules],
        "required_statistics": required_statistics,
        "significance_required": planned_seed_count >= 2,
        "power_analysis_required": publication_profile,
        "literature_minimum": literature_minimum,
        "evidence_requirements": evidence_requirements,
        "reproducibility_requirements": reproducibility_requirements,
        "threat_model": threat_model,
        "checks": [item.model_dump(mode="json") for item in checks],
        "complete": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchResearchProtocolRead(
        generated_at=_utcnow(),
        protocol_fingerprint=_fingerprint(payload),
        **payload,
    )
