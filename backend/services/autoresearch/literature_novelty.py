from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchGapValidationRead,
    AutoResearchKnownSotaRead,
    AutoResearchLiteratureGraphEdgeRead,
    AutoResearchLiteratureGraphMatchRead,
    AutoResearchLiteratureGraphNodeRead,
    AutoResearchLiteratureGraphRead,
    AutoResearchNoveltyRiskLevel,
    AutoResearchNoveltyValidationRead,
    AutoResearchRunRead,
    LiteratureInsight,
    ResearchGap,
)


_SYNTHETIC_LITERATURE_SOURCES = {
    "ai_generated",
    "ai_generated_context",
    "benchmark_context",
    "fallback",
    "generated",
    "mock",
    "synthetic",
}
_STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "and",
    "based",
    "because",
    "before",
    "between",
    "candidate",
    "current",
    "data",
    "does",
    "from",
    "into",
    "method",
    "methods",
    "paper",
    "papers",
    "prior",
    "result",
    "results",
    "study",
    "system",
    "systems",
    "that",
    "their",
    "this",
    "through",
    "using",
    "with",
    "work",
}
_METHOD_HINT_TERMS = (
    "algorithm",
    "baseline",
    "classifier",
    "encoder",
    "framework",
    "method",
    "model",
    "pipeline",
    "policy",
    "ranker",
    "rerank",
    "retrieval",
    "system",
)
_DATASET_TERMS = ("benchmark", "corpus", "dataset", "testbed", "task")
_SOTA_TERMS = ("sota", "state of the art", "state-of-the-art", "best reported")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")[:96] or "node"


def _norm(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _terms(*texts: str | None) -> set[str]:
    terms: set[str] = set()
    for text in texts:
        for raw in re.findall(r"[a-z][a-z0-9_]+", (text or "").lower()):
            if len(raw) < 4 or raw in _STOPWORDS:
                continue
            terms.add(raw)
    return terms


def _is_synthetic_literature(item: LiteratureInsight) -> bool:
    source = (item.source or "").strip().lower()
    paper_id = (item.paper_id or "").strip().lower()
    title = item.title.strip().lower()
    return (
        source in _SYNTHETIC_LITERATURE_SOURCES
        or paper_id.startswith("context_ref_")
        or title.startswith("[context summary]")
    )


def _real_literature(run: AutoResearchRunRead) -> list[LiteratureInsight]:
    return [item for item in run.literature if not _is_synthetic_literature(item)]


def _selected_candidate_text(run: AutoResearchRunRead) -> tuple[str | None, str]:
    selected_id = run.portfolio.selected_candidate_id if run.portfolio is not None else None
    candidate = next((item for item in run.candidates if item.id == selected_id), None) if selected_id else None
    if candidate is None:
        candidate = next((item for item in run.candidates if item.selected_round_index is not None), None)
    if candidate is not None:
        return candidate.id, " ".join(
            [
                candidate.title,
                candidate.hypothesis,
                candidate.proposed_method,
                " ".join(candidate.planned_contributions),
                " ".join(candidate.differentiators),
            ]
        )
    if run.plan is not None:
        return None, " ".join(
            [
                run.plan.title,
                run.plan.problem_statement,
                run.plan.proposed_method,
                " ".join(run.plan.hypotheses),
                " ".join(run.plan.planned_contributions),
            ]
        )
    claims = " ".join(item.claim for item in run.claim_evidence_matrix.entries) if run.claim_evidence_matrix else ""
    return None, " ".join([run.topic, claims])


def _benchmark_text(run: AutoResearchRunRead) -> str:
    parts = [run.topic]
    if run.spec is not None:
        parts.extend(
            [
                run.spec.benchmark_name or "",
                run.spec.dataset.name,
                run.spec.dataset.description,
                " ".join(metric.name for metric in run.spec.metrics),
            ]
        )
    if run.benchmark is not None:
        parts.extend([run.benchmark.name, run.benchmark.url or ""])
    return " ".join(parts)


def _experiment_terms(run: AutoResearchRunRead) -> set[str]:
    parts = [_benchmark_text(run)]
    if run.plan is not None:
        parts.extend(run.plan.research_questions)
        parts.extend(run.plan.hypotheses)
        parts.extend(run.plan.experiment_outline)
    if run.spec is not None:
        parts.extend(item.name for item in run.spec.metrics)
        parts.extend(item.name for item in run.spec.baselines)
        parts.extend(item.name for item in run.spec.ablations)
    if run.artifact is not None:
        parts.append(run.artifact.primary_metric)
        parts.extend(run.artifact.key_findings)
    return _terms(*parts)


def _node(
    *,
    node_id: str,
    node_type: str,
    label: str,
    source_paper_id: str | None = None,
    synthetic: bool = False,
    attributes: dict[str, object] | None = None,
) -> AutoResearchLiteratureGraphNodeRead:
    return AutoResearchLiteratureGraphNodeRead(
        node_id=node_id,
        node_type=node_type,
        label=label,
        source_paper_id=source_paper_id,
        synthetic=synthetic,
        attributes=attributes or {},
    )


def _paper_node_id(item: LiteratureInsight, index: int) -> str:
    return f"paper:{_slug(item.paper_id or item.title or str(index))}"


def _metric_labels(run: AutoResearchRunRead) -> list[str]:
    labels: list[str] = []
    if run.spec is not None:
        labels.extend(metric.name for metric in run.spec.metrics)
    if run.artifact is not None and run.artifact.primary_metric not in labels:
        labels.append(run.artifact.primary_metric)
    return [_norm(item) for item in labels if _norm(item)]


def _literature_text(item: LiteratureInsight) -> str:
    return " ".join(
        part
        for part in [
            item.title,
            item.insight,
            item.method_hint or "",
            item.gap_hint or "",
            item.methodological_detail or "",
            item.limitation or "",
            item.relevance or "",
        ]
        if part
    )


def build_literature_graph(run: AutoResearchRunRead) -> AutoResearchLiteratureGraphRead:
    paper_nodes: list[AutoResearchLiteratureGraphNodeRead] = []
    method_nodes: list[AutoResearchLiteratureGraphNodeRead] = []
    dataset_nodes: list[AutoResearchLiteratureGraphNodeRead] = []
    metric_nodes: list[AutoResearchLiteratureGraphNodeRead] = []
    claim_nodes: list[AutoResearchLiteratureGraphNodeRead] = []
    edges: list[AutoResearchLiteratureGraphEdgeRead] = []
    similar_methods: list[AutoResearchLiteratureGraphMatchRead] = []
    similar_tasks: list[AutoResearchLiteratureGraphMatchRead] = []
    similar_benchmarks: list[AutoResearchLiteratureGraphMatchRead] = []
    known_sota: list[AutoResearchKnownSotaRead] = []

    _selected_id, candidate_text = _selected_candidate_text(run)
    candidate_terms = _terms(candidate_text)
    benchmark_terms = _terms(_benchmark_text(run))
    metric_terms = _terms(*_metric_labels(run))

    for index, item in enumerate(run.literature, start=1):
        synthetic = _is_synthetic_literature(item)
        paper_id = _paper_node_id(item, index)
        text = _literature_text(item)
        paper_nodes.append(
            _node(
                node_id=paper_id,
                node_type="paper",
                label=item.title,
                source_paper_id=item.paper_id,
                synthetic=synthetic,
                attributes={"year": item.year, "source": item.source},
            )
        )

        if item.method_hint or any(term in text.lower() for term in _METHOD_HINT_TERMS):
            label = _norm(item.method_hint) or f"Method cues from {item.title}"
            method_id = f"method:{_slug(item.paper_id or item.title)}"
            method_nodes.append(
                _node(
                    node_id=method_id,
                    node_type="method",
                    label=label,
                    source_paper_id=item.paper_id,
                    synthetic=synthetic,
                )
            )
            edges.append(
                AutoResearchLiteratureGraphEdgeRead(
                    source_id=paper_id,
                    relation="mentions_method",
                    target_id=method_id,
                    evidence=label,
                    weight=max(1, len(_terms(label))),
                )
            )

        if item.gap_hint:
            claim_id = f"claim:gap:{_slug(item.paper_id or item.title)}"
            claim_nodes.append(
                _node(
                    node_id=claim_id,
                    node_type="claim",
                    label=item.gap_hint,
                    source_paper_id=item.paper_id,
                    synthetic=synthetic,
                    attributes={"claim_kind": "gap"},
                )
            )
            edges.append(
                AutoResearchLiteratureGraphEdgeRead(
                    source_id=paper_id,
                    relation="identifies_gap",
                    target_id=claim_id,
                    evidence=item.gap_hint,
                )
            )

        if any(term in text.lower() for term in _DATASET_TERMS):
            dataset_id = f"dataset:{_slug(item.paper_id or item.title)}"
            dataset_nodes.append(
                _node(
                    node_id=dataset_id,
                    node_type="dataset",
                    label=item.relevance or item.gap_hint or item.title,
                    source_paper_id=item.paper_id,
                    synthetic=synthetic,
                )
            )
            edges.append(
                AutoResearchLiteratureGraphEdgeRead(
                    source_id=paper_id,
                    relation="evaluates_dataset",
                    target_id=dataset_id,
                    evidence=item.relevance or item.gap_hint or item.title,
                )
            )

        for metric in _metric_labels(run):
            if metric and metric.lower() in text.lower():
                metric_id = f"metric:{_slug(metric)}:{_slug(item.paper_id or item.title)}"
                metric_nodes.append(
                    _node(
                        node_id=metric_id,
                        node_type="metric",
                        label=metric,
                        source_paper_id=item.paper_id,
                        synthetic=synthetic,
                    )
                )
                edges.append(
                    AutoResearchLiteratureGraphEdgeRead(
                        source_id=paper_id,
                        relation="reports_metric",
                        target_id=metric_id,
                        evidence=f"{item.title} mentions {metric}.",
                    )
                )

        lit_terms = _terms(text)
        shared_method_terms = sorted(candidate_terms & lit_terms)
        shared_task_terms = sorted(_terms(run.topic, candidate_text) & lit_terms)
        shared_benchmark_terms = sorted(benchmark_terms & lit_terms)
        if shared_method_terms:
            similar_methods.append(
                AutoResearchLiteratureGraphMatchRead(
                    match_id=f"method_match_{index}",
                    match_type="method",
                    paper_id=item.paper_id,
                    paper_title=item.title,
                    overlap_score=len(shared_method_terms),
                    shared_terms=shared_method_terms[:8],
                    rationale="Candidate method vocabulary overlaps with this paper.",
                )
            )
        if shared_task_terms:
            similar_tasks.append(
                AutoResearchLiteratureGraphMatchRead(
                    match_id=f"task_match_{index}",
                    match_type="task",
                    paper_id=item.paper_id,
                    paper_title=item.title,
                    overlap_score=len(shared_task_terms),
                    shared_terms=shared_task_terms[:8],
                    rationale="Candidate task vocabulary overlaps with this paper.",
                )
            )
        if shared_benchmark_terms:
            similar_benchmarks.append(
                AutoResearchLiteratureGraphMatchRead(
                    match_id=f"benchmark_match_{index}",
                    match_type="benchmark",
                    paper_id=item.paper_id,
                    paper_title=item.title,
                    overlap_score=len(shared_benchmark_terms),
                    shared_terms=shared_benchmark_terms[:8],
                    rationale="Benchmark or dataset vocabulary overlaps with this paper.",
                )
            )
        lowered_text = text.lower()
        if any(term in lowered_text for term in _SOTA_TERMS):
            known_sota.append(
                AutoResearchKnownSotaRead(
                    paper_id=item.paper_id,
                    paper_title=item.title,
                    method=item.method_hint,
                    metric=next(iter(metric_terms), None),
                    evidence=item.relevance or item.insight,
                )
            )

    if run.claim_evidence_matrix is not None:
        for entry in run.claim_evidence_matrix.entries:
            claim_id = f"claim:{_slug(entry.claim_id)}"
            claim_nodes.append(
                _node(
                    node_id=claim_id,
                    node_type="claim",
                    label=entry.claim,
                    attributes={"support_status": entry.support_status, "category": entry.category},
                )
            )
            for ref in entry.evidence:
                if ref.source_kind == "literature":
                    edges.append(
                        AutoResearchLiteratureGraphEdgeRead(
                            source_id=ref.locator or "literature",
                            relation="supports_claim",
                            target_id=claim_id,
                            evidence=ref.detail,
                        )
                    )

    for matches in (similar_methods, similar_tasks, similar_benchmarks):
        matches.sort(key=lambda item: (-item.overlap_score, item.paper_title.lower()))

    payload = {
        "graph_id": "literature_graph_v1",
        "project_id": run.project_id,
        "run_id": run.id,
        "paper_nodes": [item.model_dump(mode="json") for item in paper_nodes],
        "method_nodes": [item.model_dump(mode="json") for item in method_nodes],
        "dataset_nodes": [item.model_dump(mode="json") for item in dataset_nodes],
        "metric_nodes": [item.model_dump(mode="json") for item in metric_nodes],
        "claim_nodes": [item.model_dump(mode="json") for item in claim_nodes],
        "edges": [item.model_dump(mode="json") for item in edges],
        "similar_methods": [item.model_dump(mode="json") for item in similar_methods[:10]],
        "similar_tasks": [item.model_dump(mode="json") for item in similar_tasks[:10]],
        "similar_benchmarks": [item.model_dump(mode="json") for item in similar_benchmarks[:10]],
        "known_sota": [item.model_dump(mode="json") for item in known_sota[:10]],
        "real_paper_count": len(_real_literature(run)),
        "synthetic_paper_count": len(run.literature) - len(_real_literature(run)),
    }
    return AutoResearchLiteratureGraphRead(
        generated_at=_utcnow(),
        graph_fingerprint=_fingerprint(payload),
        **payload,
    )


def _gap_candidates(run: AutoResearchRunRead) -> list[ResearchGap]:
    if run.literature_synthesis is not None and run.literature_synthesis.gaps:
        return list(run.literature_synthesis.gaps)
    gaps: list[ResearchGap] = []
    for index, item in enumerate(_real_literature(run), start=1):
        if not item.gap_hint:
            continue
        gaps.append(
            ResearchGap(
                gap_id=f"literature_gap_{index}",
                description=item.gap_hint,
                evidence_from=[item.paper_id or item.title],
                gap_type="evaluation",
                opportunity=item.relevance,
            )
        )
    return gaps


def _validate_gap(
    gap: ResearchGap,
    *,
    real_paper_ids: set[str],
    experiment_terms: set[str],
) -> AutoResearchGapValidationRead:
    evidence = [item for item in gap.evidence_from if item]
    evidence_real = bool(evidence and any(item in real_paper_ids for item in evidence))
    gap_terms = _terms(gap.description, gap.opportunity)
    shared_terms = sorted(gap_terms & experiment_terms)
    testable = bool(shared_terms)
    blockers: list[str] = []
    if not evidence:
        blockers.append("Research gap is not bound to literature evidence.")
    elif not evidence_real:
        blockers.append("Research gap evidence does not resolve to a real persisted paper.")
    if not testable:
        blockers.append("Research gap is not experimentally testable by the current specification.")
    status = "valid" if evidence_real and testable else "weak" if evidence and (evidence_real or testable) else "invalid"
    return AutoResearchGapValidationRead(
        gap_id=gap.gap_id,
        description=gap.description,
        literature_evidence=evidence,
        experimentally_testable=testable,
        validation_target=", ".join(shared_terms[:6]) if shared_terms else None,
        status=status,
        blockers=blockers,
    )


def _risk_from_score(score: int, *, high_at: int, medium_at: int) -> AutoResearchNoveltyRiskLevel:
    if score >= high_at:
        return "high"
    if score >= medium_at:
        return "medium"
    return "low"


def build_novelty_validation(
    run: AutoResearchRunRead,
    *,
    literature_graph: AutoResearchLiteratureGraphRead,
) -> AutoResearchNoveltyValidationRead:
    real_lit = _real_literature(run)
    real_ids = {item.paper_id or item.title for item in real_lit}
    experiment_terms = _experiment_terms(run)
    gap_validations = [
        _validate_gap(gap, real_paper_ids=real_ids, experiment_terms=experiment_terms)
        for gap in _gap_candidates(run)
    ]
    valid_gap_count = sum(1 for item in gap_validations if item.status == "valid")
    gap_validity = (
        "valid"
        if valid_gap_count > 0
        else "weak"
        if any(item.status == "weak" for item in gap_validations)
        else "invalid"
        if gap_validations
        else "missing"
    )

    max_method_overlap = max((item.overlap_score for item in literature_graph.similar_methods), default=0)
    max_task_overlap = max((item.overlap_score for item in literature_graph.similar_tasks), default=0)
    max_benchmark_overlap = max((item.overlap_score for item in literature_graph.similar_benchmarks), default=0)
    duplicate_risk = _risk_from_score(max_method_overlap, high_at=8, medium_at=4)
    experiment_coverage_score = max_method_overlap + max_benchmark_overlap + min(max_task_overlap, 3)
    experiment_coverage_risk = _risk_from_score(experiment_coverage_score, high_at=13, medium_at=7)
    incremental_score = max_method_overlap + max_task_overlap - (valid_gap_count * 3)
    incremental_risk = _risk_from_score(incremental_score, high_at=12, medium_at=6)

    blockers: list[str] = []
    warnings: list[str] = []
    if not real_lit:
        blockers.append("Novelty validation requires real persisted literature; fallback context cannot validate novelty.")
    if gap_validity in {"missing", "invalid"}:
        blockers.append(
            "Novelty validation requires at least one literature-backed research gap that the current experiment can test."
        )
    if duplicate_risk == "high" and gap_validity != "valid":
        blockers.append(
            "Current method appears to restate similar prior work without a valid literature-backed gap."
        )
    if experiment_coverage_risk == "high" and gap_validity != "valid":
        blockers.append(
            "Current experiment appears covered by similar literature; change the research question or experiment design."
        )
    for gap in gap_validations:
        warnings.extend(gap.blockers)
    if incremental_risk == "medium":
        warnings.append("Novelty appears incremental; frame the claim narrowly against the validated gap.")

    if not real_lit:
        recommendation = "attach_literature"
    elif duplicate_risk == "high":
        recommendation = "change_research_question"
    elif experiment_coverage_risk == "high":
        recommendation = "change_experiment_design"
    elif incremental_risk in {"medium", "high"}:
        recommendation = "reframe_positioning"
    else:
        recommendation = "proceed"

    duplicate_detail = (
        f"Maximum method overlap is {max_method_overlap}; "
        f"top matches: {', '.join(item.paper_title for item in literature_graph.similar_methods[:3]) or 'none'}."
    )
    incremental_detail = (
        f"Maximum task overlap is {max_task_overlap}; valid literature-backed gaps={valid_gap_count}."
    )
    coverage_detail = (
        f"Method+benchmark+task coverage score is {experiment_coverage_score}; "
        f"benchmark overlap={max_benchmark_overlap}."
    )
    payload = {
        "validation_id": "novelty_validation_v1",
        "project_id": run.project_id,
        "run_id": run.id,
        "duplicate_risk": duplicate_risk,
        "incremental_risk": incremental_risk,
        "gap_validity": gap_validity,
        "experiment_coverage_risk": experiment_coverage_risk,
        "duplicate_risk_detail": duplicate_detail,
        "incremental_risk_detail": incremental_detail,
        "experiment_coverage_detail": coverage_detail,
        "recommendation": recommendation,
        "gap_validations": [item.model_dump(mode="json") for item in gap_validations],
        "blockers": blockers,
        "warnings": sorted(set(warnings)),
        "complete": not blockers,
    }
    return AutoResearchNoveltyValidationRead(
        generated_at=_utcnow(),
        validation_fingerprint=_fingerprint(payload),
        **payload,
    )
