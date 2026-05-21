from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchPublicationReadinessRead,
    AutoResearchReadinessCategory,
    AutoResearchReadinessCheckRead,
    ExperimentSpec,
    ResultArtifact,
    AutoResearchRunRead,
)


PUBLICATION_SEEDS = [7, 13, 23, 31, 47]
PUBLICATION_MIN_COMPLETED_SEEDS = 3
PUBLICATION_MIN_REAL_LITERATURE = 2
PUBLICATION_MIN_DATASET_EXAMPLES = 20
SYNTHETIC_LITERATURE_SOURCES = {"ai_generated_context", "benchmark_context"}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint_payload(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def enforce_publication_protocol(spec: ExperimentSpec) -> ExperimentSpec:
    """Raise an experiment spec from a smoke-test protocol to a publication protocol."""
    updates = {}
    if len(spec.seeds) < len(PUBLICATION_SEEDS):
        updates["seeds"] = PUBLICATION_SEEDS
    notes = list(spec.implementation_notes)
    publication_note = (
        "Publication profile: preserve at least three completed seeds, all planned ablations, "
        "and enough aggregate evidence for final-publish review gates."
    )
    if publication_note not in notes:
        notes.append(publication_note)
    updates["implementation_notes"] = notes
    return spec.model_copy(update=updates)


def dataset_source_fingerprint(dataset_payload: dict) -> str:
    relevant = {
        "name": dataset_payload.get("name"),
        "description": dataset_payload.get("description"),
        "source_url": dataset_payload.get("source_url"),
        "train": dataset_payload.get("train", []),
        "test": dataset_payload.get("test", []),
    }
    return _fingerprint_payload(relevant)


def is_synthetic_literature(item) -> bool:
    source = (getattr(item, "source", None) or "").strip().lower()
    paper_id = (getattr(item, "paper_id", None) or "").strip().lower()
    title = (getattr(item, "title", None) or "").strip().lower()
    return (
        source in SYNTHETIC_LITERATURE_SOURCES
        or paper_id.startswith("context_ref_")
        or title.startswith("[context summary]")
    )


def real_literature_items(run: AutoResearchRunRead) -> list:
    return [item for item in run.literature if not is_synthetic_literature(item)]


def synthetic_literature_count(run: AutoResearchRunRead) -> int:
    return len(run.literature) - len(real_literature_items(run))


def _artifact_system_names(artifact: ResultArtifact | None) -> set[str]:
    if artifact is None:
        return set()
    names: set[str] = set()
    for name in (artifact.best_system, artifact.objective_system):
        if name:
            names.add(name)
    for collection_name in ("system_results", "aggregate_system_results"):
        for item in getattr(artifact, collection_name, []) or []:
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


def _publication_grade_benchmark(run: AutoResearchRunRead) -> tuple[bool, str]:
    spec = run.spec
    if spec is None:
        return False, "No experiment specification was persisted."
    benchmark_kind = run.benchmark.kind if run.benchmark is not None else spec.dataset.source_kind
    dataset_name = spec.dataset.name or ""
    benchmark_name = spec.benchmark_name or ""
    total_examples = spec.dataset.train_size + spec.dataset.test_size
    if benchmark_kind == "builtin" or benchmark_name.startswith("toy_") or dataset_name.lower().startswith("toy "):
        return (
            False,
            "Final publish requires a real external benchmark; built-in toy benchmarks are limited to exploratory or review bundles.",
        )
    if total_examples < PUBLICATION_MIN_DATASET_EXAMPLES:
        return (
            False,
            f"Final publish requires at least {PUBLICATION_MIN_DATASET_EXAMPLES} benchmark examples; this run has {total_examples}.",
        )
    if not (
        spec.dataset.source_url
        or spec.dataset.source_dataset_id
        or (run.benchmark.url if run.benchmark is not None else None)
        or (run.benchmark.dataset_id if run.benchmark is not None else None)
    ):
        return False, "Final publish requires a persisted benchmark source URL or dataset identifier."
    return True, "The run uses an external benchmark with persisted provenance."


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


def build_publication_readiness(
    run: AutoResearchRunRead,
    *,
    paper_markdown: str | None = None,
) -> AutoResearchPublicationReadinessRead:
    checks: list[AutoResearchReadinessCheckRead] = []
    artifact = run.artifact
    spec = run.spec
    real_lit_count = len(real_literature_items(run))
    synthetic_count = synthetic_literature_count(run)
    completed_seed_count = len(artifact.per_seed_results) if artifact is not None else 0
    requested_seed_count = len(spec.seeds) if spec is not None else 0
    significance_count = len(artifact.significance_tests) if artifact is not None else 0
    if run.claim_evidence_matrix is not None:
        unsupported_claim_count = sum(
            1
            for item in run.claim_evidence_matrix.entries
            if item.support_status == "unsupported"
        )
        partial_claim_count = sum(
            1
            for item in run.claim_evidence_matrix.entries
            if item.support_status == "partial"
        )
    else:
        unsupported_claim_count = 0
        partial_claim_count = 0
    planned_ablation_names = [item.name for item in spec.ablations] if spec is not None else []
    observed_systems = _artifact_system_names(run.artifact)
    observed_ablation_count = sum(1 for name in planned_ablation_names if name in observed_systems)
    benchmark_ok, benchmark_detail = _publication_grade_benchmark(run)

    _add_check(
        checks,
        check_id="publication_grade_benchmark",
        category="benchmark",
        passed=benchmark_ok,
        summary="Run uses a publication-grade benchmark.",
        detail=benchmark_detail,
    )
    _add_check(
        checks,
        check_id="real_literature_context",
        category="literature",
        passed=real_lit_count >= PUBLICATION_MIN_REAL_LITERATURE,
        summary="Run persists enough real literature for novelty framing.",
        detail=(
            f"Real literature records={real_lit_count}; synthetic context records={synthetic_count}; "
            f"minimum real literature for final publish={PUBLICATION_MIN_REAL_LITERATURE}."
        ),
    )
    _add_check(
        checks,
        check_id="completed_seed_floor",
        category="statistics",
        passed=completed_seed_count >= PUBLICATION_MIN_COMPLETED_SEEDS,
        summary="Run has publication-level seed coverage.",
        detail=(
            f"Completed seed results={completed_seed_count}; requested seeds={requested_seed_count}; "
            f"minimum completed seeds for final publish={PUBLICATION_MIN_COMPLETED_SEEDS}."
        ),
    )
    _add_check(
        checks,
        check_id="significance_tests_present",
        category="statistics",
        passed=significance_count > 0,
        summary="Run preserves significance comparisons.",
        detail=f"Significance comparisons recorded={significance_count}.",
    )
    _add_check(
        checks,
        check_id="planned_ablations_observed",
        category="statistics",
        passed=not planned_ablation_names or observed_ablation_count == len(planned_ablation_names),
        summary="Planned ablations are represented in executed evidence.",
        detail=(
            f"Observed ablations={observed_ablation_count}/{len(planned_ablation_names)}; "
            f"planned={', '.join(planned_ablation_names) if planned_ablation_names else 'none'}."
        ),
    )
    _add_check(
        checks,
        check_id="claim_evidence_supported",
        category="evidence",
        passed=run.claim_evidence_matrix is not None and unsupported_claim_count == 0,
        summary="Publish-facing claims are supported by the evidence matrix.",
        detail=(
            f"Unsupported claim count={unsupported_claim_count}; partial claim count={partial_claim_count}."
            if run.claim_evidence_matrix is not None
            else "No claim-evidence matrix was persisted."
        ),
    )
    _add_check(
        checks,
        check_id="compile_ready_sources",
        category="reproducibility",
        passed=run.paper_compile_report is not None and run.paper_compile_report.ready_for_compile,
        summary="Paper source package is ready for compilation.",
        detail=(
            "Compile report is ready."
            if run.paper_compile_report is not None and run.paper_compile_report.ready_for_compile
            else "Paper compile report is missing or not ready."
        ),
    )
    _add_check(
        checks,
        check_id="paper_markdown_present",
        category="paper",
        passed=bool((paper_markdown if paper_markdown is not None else run.paper_markdown) or ""),
        summary="Grounded paper markdown is present.",
        detail="Paper markdown is persisted." if (paper_markdown or run.paper_markdown) else "No paper markdown was found.",
        required_for_final_publish=False,
    )

    required_checks = [item for item in checks if item.required_for_final_publish]
    blockers = [item.detail for item in required_checks if not item.passed]
    warnings = [item.detail for item in checks if not item.passed and not item.required_for_final_publish]
    passed_required = sum(1 for item in required_checks if item.passed)
    score = int(round(100 * passed_required / max(len(required_checks), 1)))
    has_artifact_and_paper = artifact is not None and artifact.status == "done" and bool(paper_markdown or run.paper_markdown)
    final_ready = not blockers and has_artifact_and_paper
    if final_ready:
        tier = "publish_ready"
    elif benchmark_ok and real_lit_count >= 1 and has_artifact_and_paper:
        tier = "publish_candidate"
    elif has_artifact_and_paper:
        tier = "review_ready"
    else:
        tier = "exploratory"

    return AutoResearchPublicationReadinessRead(
        generated_at=_utcnow(),
        tier=tier,  # type: ignore[arg-type]
        score=score,
        summary=(
            f"Publication readiness tier={tier}; score={score}/100; "
            f"blocking checks={len(blockers)}."
        ),
        final_publish_ready=final_ready,
        publication_grade_benchmark=benchmark_ok,
        real_literature_count=real_lit_count,
        synthetic_literature_count=synthetic_count,
        completed_seed_count=completed_seed_count,
        requested_seed_count=requested_seed_count,
        significance_test_count=significance_count,
        planned_ablation_count=len(planned_ablation_names),
        observed_ablation_count=observed_ablation_count,
        unsupported_claim_count=unsupported_claim_count,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
    )
