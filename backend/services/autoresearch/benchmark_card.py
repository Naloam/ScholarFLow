from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchBenchmarkCardRead,
    AutoResearchReadinessCategory,
    AutoResearchReadinessCheckRead,
    AutoResearchRunRead,
)
from services.autoresearch.benchmark_source_metadata import materialize_file_backed_benchmark_source
from services.autoresearch.research_readiness import PUBLICATION_MIN_DATASET_EXAMPLES


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


def build_benchmark_card(run: AutoResearchRunRead) -> AutoResearchBenchmarkCardRead:
    materialized_benchmark = materialize_file_backed_benchmark_source(run)
    spec = run.spec or (materialized_benchmark.spec if materialized_benchmark is not None else None)
    dataset = spec.dataset if spec is not None else None
    source_kind = (
        run.benchmark.kind
        if run.benchmark is not None
        else dataset.source_kind
        if dataset is not None
        else None
    )
    source_url = (
        dataset.source_url
        if dataset is not None and dataset.source_url
        else run.benchmark.url
        if run.benchmark is not None
        else None
    )
    source_dataset_id = (
        dataset.source_dataset_id
        if dataset is not None and dataset.source_dataset_id
        else run.benchmark.dataset_id
        if run.benchmark is not None
        else None
    )
    total_examples = (dataset.train_size + dataset.test_size) if dataset is not None else 0
    publication_profile = run.request is not None and run.request.execution_profile == "publication"
    publication_grade = bool(dataset is not None and dataset.publication_grade)
    provenance_complete = bool(dataset is not None and dataset.provenance_complete)
    eligibility_blockers = list(dataset.publication_grade_blockers) if dataset is not None else []
    checks: list[AutoResearchReadinessCheckRead] = []
    _add_check(
        checks,
        check_id="external_benchmark_source",
        category="benchmark",
        passed=bool(source_kind and source_kind != "builtin"),
        summary="Benchmark card records an external benchmark source.",
        detail=f"source_kind={source_kind or 'missing'}.",
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="benchmark_provenance",
        category="benchmark",
        passed=provenance_complete,
        summary="Benchmark card preserves source provenance.",
        detail=(
            f"source_url={source_url}; source_dataset_id={source_dataset_id}; "
            f"source_revision={dataset.source_revision if dataset is not None else None}; "
            f"source_license={dataset.source_license if dataset is not None else None}; "
            f"source_fingerprint={dataset.source_fingerprint if dataset is not None else None}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="dataset_size_floor",
        category="benchmark",
        passed=total_examples >= PUBLICATION_MIN_DATASET_EXAMPLES,
        summary="Benchmark card records enough examples for publication review.",
        detail=f"total_examples={total_examples}; minimum={PUBLICATION_MIN_DATASET_EXAMPLES}.",
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="dataset_split_documented",
        category="reproducibility",
        passed=bool(dataset is not None and dataset.train_size > 0 and dataset.test_size > 0),
        summary="Benchmark card records train/test split sizes.",
        detail=(
            f"train_size={dataset.train_size if dataset is not None else 0}; "
            f"test_size={dataset.test_size if dataset is not None else 0}."
        ),
        required_for_final_publish=publication_profile,
    )
    _add_check(
        checks,
        check_id="dataset_license_recorded",
        category="reproducibility",
        passed=bool(dataset is not None and dataset.source_license),
        summary="Benchmark card records dataset license metadata.",
        detail=f"source_license={dataset.source_license if dataset is not None else None}.",
        required_for_final_publish=False,
    )
    required_checks = [item for item in checks if item.required_for_final_publish]
    blockers = [item.detail for item in required_checks if not item.passed]
    warnings = [item.detail for item in checks if not item.passed and not item.required_for_final_publish]
    limitations = [
        "Benchmark conclusions are bounded by the persisted train/test split and label space.",
        "External validity depends on how closely the benchmark source matches the requested research topic.",
        "License metadata should be reviewed before public redistribution of dataset-derived artifacts.",
    ]
    recommended_use = [
        "Use this card as the dataset/provenance source for paper method and reproducibility sections.",
        "Preserve the source fingerprint and split sizes in final publication packages.",
        "Treat built-in or provenance-missing benchmarks as exploratory evidence only.",
    ]
    payload = {
        "card_id": "benchmark_card_v1",
        "topic": run.topic,
        "task_family": run.task_family,
        "benchmark_name": spec.benchmark_name if spec is not None else None,
        "benchmark_description": spec.benchmark_description if spec is not None else None,
        "dataset_name": dataset.name if dataset is not None else None,
        "dataset_description": dataset.description if dataset is not None else None,
        "train_size": dataset.train_size if dataset is not None else 0,
        "test_size": dataset.test_size if dataset is not None else 0,
        "total_examples": total_examples,
        "sample_count": dataset.sample_count if dataset is not None else 0,
        "split_count": dataset.split_count if dataset is not None else 0,
        "supports_claim_verification": (
            dataset.supports_claim_verification if dataset is not None else False
        ),
        "verification_label_space": (
            dataset.verification_label_space if dataset is not None else []
        ),
        "label_space": dataset.label_space if dataset is not None else [],
        "input_fields": dataset.input_fields if dataset is not None else [],
        "source_kind": source_kind,
        "source_url": source_url,
        "source_dataset_id": source_dataset_id,
        "source_revision": dataset.source_revision if dataset is not None else None,
        "source_license": dataset.source_license if dataset is not None else None,
        "source_fingerprint": dataset.source_fingerprint if dataset is not None else None,
        "source_content_origin": dataset.source_content_origin if dataset is not None else None,
        "source_content_note": dataset.source_content_note if dataset is not None else None,
        "source_class": dataset.source_class if dataset is not None else None,
        "publication_grade_eligibility": (
            dataset.publication_grade_eligibility if dataset is not None else {}
        ),
        "publication_grade_blockers": eligibility_blockers,
        "publication_grade": publication_grade,
        "provenance_complete": provenance_complete,
        "checks": [item.model_dump(mode="json") for item in checks],
        "limitations": limitations,
        "recommended_use": recommended_use,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchBenchmarkCardRead(
        generated_at=_utcnow(),
        card_fingerprint=_fingerprint(payload),
        **payload,
    )
