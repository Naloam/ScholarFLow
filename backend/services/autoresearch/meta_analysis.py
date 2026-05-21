from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchConclusionStability,
    AutoResearchCrossRunMetaAnalysisRead,
    AutoResearchMetaAnalysisComparisonRead,
    AutoResearchMetaAnalysisRunSummaryRead,
    AutoResearchNoveltyRiskLevel,
    AutoResearchRunRead,
    AutoResearchStableConclusionRead,
)
from services.autoresearch.repository import list_runs


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:72] or "group"


def _topic_key(value: str) -> str:
    terms = re.findall(r"[a-z0-9]+", value.lower())
    return " ".join(terms[:8])


def _primary_metric(run: AutoResearchRunRead) -> str | None:
    if run.artifact is not None and run.artifact.primary_metric:
        return run.artifact.primary_metric
    if run.spec is not None and run.spec.metrics:
        return run.spec.metrics[0].name
    return None


def _objective_score(run: AutoResearchRunRead) -> float | None:
    if run.artifact is not None and isinstance(run.artifact.objective_score, (int, float)):
        return float(run.artifact.objective_score)
    selected = next((item for item in run.candidates if item.selected_round_index is not None), None)
    if selected is not None and selected.score is not None:
        return float(selected.score)
    return None


def _method(run: AutoResearchRunRead) -> str | None:
    if run.artifact is not None and run.artifact.objective_system:
        return run.artifact.objective_system
    if run.artifact is not None and run.artifact.best_system:
        return run.artifact.best_system
    selected = next((item for item in run.candidates if item.selected_round_index is not None), None)
    return selected.title if selected is not None else None


def _dataset(run: AutoResearchRunRead) -> str | None:
    if run.spec is not None and run.spec.benchmark_name:
        return run.spec.benchmark_name
    if run.program is not None and run.program.benchmark_name:
        return run.program.benchmark_name
    return run.benchmark.name if run.benchmark is not None else None


def _hypothesis(run: AutoResearchRunRead) -> str | None:
    if run.spec is not None and run.spec.hypothesis:
        return run.spec.hypothesis
    if run.plan is not None and run.plan.hypotheses:
        return run.plan.hypotheses[0]
    return None


def _novelty_risk(run: AutoResearchRunRead) -> AutoResearchNoveltyRiskLevel:
    validation = getattr(run, "novelty_validation", None)
    if validation is not None:
        if validation.duplicate_risk == "high" or validation.incremental_risk == "high":
            return "high"
        if validation.duplicate_risk == "low" and validation.incremental_risk == "low":
            return "low"
    assessment = getattr(run, "contribution_assessment", None)
    if assessment is not None and assessment.novelty_risks:
        if any(item.severity == "high" for item in assessment.novelty_risks):
            return "high"
        if any(item.severity == "medium" for item in assessment.novelty_risks):
            return "medium"
        return "low"
    return "medium"


def _summary(run: AutoResearchRunRead) -> AutoResearchMetaAnalysisRunSummaryRead:
    artifact = run.artifact
    contribution = getattr(run, "contribution_assessment", None)
    readiness = getattr(run, "publication_readiness", None)
    return AutoResearchMetaAnalysisRunSummaryRead(
        run_id=run.id,
        topic=run.topic,
        hypothesis=_hypothesis(run),
        method=_method(run),
        dataset=_dataset(run),
        primary_metric=_primary_metric(run),
        objective_score=_objective_score(run),
        seed_count=len(artifact.per_seed_results) if artifact is not None else 0,
        significant_result_count=(
            sum(1 for item in artifact.significance_tests if item.significant)
            if artifact is not None
            else 0
        ),
        contribution_score=contribution.publishability_score if contribution is not None else 0,
        novelty_risk=_novelty_risk(run),
        publication_tier=readiness.tier if readiness is not None else None,
        final_publish_ready=readiness.final_publish_ready if readiness is not None else False,
    )


def _stability(scores: list[float], significant_counts: list[int]) -> AutoResearchConclusionStability:
    if len(scores) < 2:
        return "conditional"
    if max(scores) - min(scores) <= 0.05 and any(count > 0 for count in significant_counts):
        return "stable"
    if max(scores) - min(scores) > 0.2:
        return "unreproducible"
    return "conditional"


def _comparison(
    *,
    axis: str,
    label: str,
    group: list[AutoResearchMetaAnalysisRunSummaryRead],
) -> AutoResearchMetaAnalysisComparisonRead:
    scored = [item for item in group if item.objective_score is not None]
    scores = [float(item.objective_score) for item in scored if item.objective_score is not None]
    best = max(scored, key=lambda item: item.objective_score or float("-inf")) if scored else None
    stability = _stability(scores, [item.significant_result_count for item in group])
    metric = next((item.primary_metric for item in group if item.primary_metric), None)
    return AutoResearchMetaAnalysisComparisonRead(
        comparison_id=f"comparison_{axis}_{_slug(label)}",
        axis=axis,  # type: ignore[arg-type]
        label=label,
        run_ids=[item.run_id for item in group],
        best_run_id=best.run_id if best is not None else None,
        metric=metric,
        score_range=[min(scores), max(scores)] if scores else [],
        stability=stability,
        rationale=(
            f"Compared {len(group)} run(s) on {axis.replace('_', ' ')}; "
            f"stability={stability}, metric={metric or 'n/a'}."
        ),
    )


def build_cross_run_meta_analysis(project_id: str) -> AutoResearchCrossRunMetaAnalysisRead:
    runs = [run for run in list_runs(project_id) if run.status == "done"]
    summaries = [_summary(run) for run in runs]
    comparisons: list[AutoResearchMetaAnalysisComparisonRead] = []

    def add_grouped(axis: str, key_fn) -> None:
        groups: dict[str, list[AutoResearchMetaAnalysisRunSummaryRead]] = defaultdict(list)
        for item in summaries:
            key = key_fn(item)
            if key:
                groups[str(key)].append(item)
        for label, group in sorted(groups.items()):
            if len(group) >= 2:
                comparisons.append(_comparison(axis=axis, label=label, group=group))

    add_grouped("topic_hypothesis", lambda item: _topic_key(item.topic))
    add_grouped("method_dataset", lambda item: f"{item.method or 'unknown'}::{item.dataset or 'unknown'}")
    add_grouped("dataset_method", lambda item: item.dataset)

    conclusions: list[AutoResearchStableConclusionRead] = []
    for comparison in comparisons:
        if comparison.best_run_id is None:
            continue
        caveats = [] if comparison.stability == "stable" else ["Conclusion is benchmark- or seed-conditional."]
        if comparison.stability == "unreproducible":
            caveats = ["Observed scores vary too much to claim a stable cross-run result."]
        conclusions.append(
            AutoResearchStableConclusionRead(
                conclusion_id=f"conclusion_{comparison.comparison_id}",
                text=(
                    f"Best current evidence for {comparison.label} is run {comparison.best_run_id} "
                    f"under {comparison.metric or 'the primary metric'}."
                ),
                stability=comparison.stability,
                supporting_run_ids=list(comparison.run_ids),
                scope=comparison.axis.replace("_", " "),
                caveats=caveats,
            )
        )

    blockers: list[str] = []
    if len(summaries) < 2:
        blockers.append("Cross-run meta-analysis requires at least two completed runs.")
    if not comparisons and len(summaries) >= 2:
        blockers.append("No comparable topic, method, or dataset groups were found.")
    warnings = []
    if summaries and not any(item.final_publish_ready for item in summaries):
        warnings.append("No run is final-publish ready; project-level paper should remain a technical report.")

    project_level = any(item.stability == "stable" for item in conclusions) and len(summaries) >= 2
    recommended_ids = sorted(
        {
            run_id
            for conclusion in conclusions
            if conclusion.stability in {"stable", "conditional"}
            for run_id in conclusion.supporting_run_ids
        }
    )
    payload = {
        "analysis_id": "cross_run_meta_analysis_v1",
        "project_id": project_id,
        "topic_key": _topic_key(summaries[0].topic) if summaries else None,
        "run_count": len(runs),
        "comparable_run_count": len({run_id for item in comparisons for run_id in item.run_ids}),
        "publication_ready_run_count": sum(1 for item in summaries if item.final_publish_ready),
        "run_summaries": [item.model_dump(mode="json") for item in summaries],
        "comparisons": [item.model_dump(mode="json") for item in comparisons],
        "stable_conclusions": [item.model_dump(mode="json") for item in conclusions],
        "project_level_paper_recommended": project_level,
        "recommended_run_ids": recommended_ids,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchCrossRunMetaAnalysisRead(
        generated_at=_utcnow(),
        analysis_fingerprint=_fingerprint(payload),
        **payload,
    )
