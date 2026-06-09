from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchGapCandidateRead,
    AutoResearchGapMinerRead,
    AutoResearchLiteratureScoutPaperRead,
    AutoResearchLiteratureScoutRead,
    AutoResearchResearchBriefRead,
    LiteratureInsight,
)
from services.autoresearch.literature_connectors import (
    deduplicate_literature_papers,
    search_literature_connectors,
)
from services.autoresearch.domain_evidence import (
    build_domain_experiment_protocol,
    build_domain_literature_result,
    build_domain_literature_strategy,
    domain_claim_ceiling,
    domain_readiness_status,
)


_STOPWORDS = {
    "about",
    "against",
    "and",
    "autonomous",
    "based",
    "better",
    "candidate",
    "data",
    "dataset",
    "datasets",
    "evidence",
    "experiment",
    "for",
    "from",
    "idea",
    "improve",
    "method",
    "methods",
    "metric",
    "paper",
    "research",
    "study",
    "system",
    "systems",
    "task",
    "the",
    "this",
    "using",
    "with",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str, *, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug[:80] or fallback


def _norm(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _terms(*texts: str | None) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for text in texts:
        for raw in re.findall(r"[a-z][a-z0-9_]+", (text or "").lower()):
            if len(raw) < 4 or raw in _STOPWORDS or raw in seen:
                continue
            seen.add(raw)
            terms.append(raw)
    return terms


def _direction_text(brief: AutoResearchResearchBriefRead) -> str:
    return " ".join(
        [
            brief.original_idea,
            brief.polished_idea,
            " ".join(brief.research_questions),
            " ".join(brief.candidate_hypotheses),
            " ".join(brief.candidate_datasets),
            " ".join(brief.candidate_metrics),
            " ".join(brief.candidate_baselines),
        ]
    )


def _search_queries(brief: AutoResearchResearchBriefRead) -> list[str]:
    queries = [
        f'"{brief.original_idea}"',
        f"{brief.original_idea} literature survey",
    ]
    for direction in brief.research_directions[:4]:
        queries.extend(
            [
                f"{direction.title} {direction.candidate_dataset} {direction.primary_metric}",
                f"{direction.hypothesis} baseline ablation",
            ]
        )
    if brief.selected_hypothesis_id:
        selected = next(
            (item for item in brief.hypothesis_bank if item.hypothesis_id == brief.selected_hypothesis_id),
            None,
        )
        if selected is not None:
            queries.append(f"{selected.research_question} {selected.required_metrics[0] if selected.required_metrics else ''}")
    domain_strategy = brief.domain_literature_strategy or build_domain_literature_strategy(brief)
    if domain_strategy is not None:
        queries.extend(domain_strategy.query_strings)
    return _dedupe(queries)[: max(3, min(10, len(queries)))]


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _norm(item)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _offline_papers(brief: AutoResearchResearchBriefRead) -> list[AutoResearchLiteratureScoutPaperRead]:
    idea_terms = set(_terms(_direction_text(brief)))
    papers: list[AutoResearchLiteratureScoutPaperRead] = []
    for index, direction in enumerate(brief.research_directions, start=1):
        text = " ".join(
            [
                direction.title,
                direction.research_question,
                direction.method_sketch,
                direction.candidate_dataset,
                " ".join(direction.candidate_metrics),
                " ".join(direction.required_baselines),
            ]
        )
        shared = sorted(idea_terms & set(_terms(text)))
        paper_payload = {
            "source": "offline_project_context",
            "source_id": direction.direction_id,
            "title": f"Prior {direction.task_family.replace('_', ' ')} work near {direction.candidate_dataset}",
            "direction_id": direction.direction_id,
            "candidate_dataset": direction.candidate_dataset,
            "metrics": direction.candidate_metrics,
            "baselines": direction.required_baselines,
            "method": direction.method_sketch,
        }
        papers.append(
            AutoResearchLiteratureScoutPaperRead(
                paper_id=f"offline_related_{index}_{_slug(direction.direction_id)}",
                title=paper_payload["title"],
                source="offline_project_context",
                source_id=direction.direction_id,
                authors=["ScholarFlow offline scout"],
                year=2025,
                venue="Project context",
                abstract=(
                    f"Offline project-context signal for {direction.target_task} on "
                    f"{direction.candidate_dataset}, comparing "
                    f"{', '.join(direction.required_baselines[:2])} "
                    f"with {direction.method_sketch} under {direction.primary_metric}."
                ),
                method=direction.method_sketch,
                methods=[direction.method_sketch],
                datasets=[direction.candidate_dataset],
                metrics=direction.candidate_metrics,
                reported_results=[
                    f"Offline context requires reporting {direction.primary_metric} against "
                    f"{', '.join(direction.required_baselines[:2])}."
                ],
                known_sota=(
                    f"Known baselines include {', '.join(direction.required_baselines[:2])} "
                    f"on {direction.primary_metric}."
                ),
                relevance_score=min(1.0, 0.30 + len(shared) * 0.05),
                novelty_risk_signal=direction.novelty_risk,
                overlap_score=len(shared),
                shared_terms=shared[:10],
                cache_status="offline",
                cache_key=_fingerprint(
                    {
                        "source": "offline_project_context",
                        "brief_id": brief.brief_id,
                        "direction_id": direction.direction_id,
                    }
                ),
                fingerprint=_fingerprint(paper_payload),
                extraction_status="abstract_only",
                evidence=(
                    "Offline scout synthesized this risk from the brief's benchmark, baseline, "
                    "metric, and method obligations; live literature is still required before publish claims."
                ),
            )
        )
    papers.sort(key=lambda item: (-item.overlap_score, item.title.lower()))
    return papers


def build_literature_scout(brief: AutoResearchResearchBriefRead) -> AutoResearchLiteratureScoutRead:
    return build_literature_scout_with_options(brief)


def build_literature_scout_with_options(
    brief: AutoResearchResearchBriefRead,
    *,
    sources: list[str] | None = None,
    limit_per_source: int = 3,
    cache_enabled: bool = True,
    network_enabled: bool | None = None,
) -> AutoResearchLiteratureScoutRead:
    domain_strategy = brief.domain_literature_strategy or build_domain_literature_strategy(brief)
    search_queries = _search_queries(brief)
    effective_network_enabled = brief.allow_web if network_enabled is None else bool(
        network_enabled and brief.allow_web
    )
    connector_papers, source_statuses = search_literature_connectors(
        brief,
        search_queries=search_queries,
        sources=sources,
        limit_per_source=limit_per_source,
        network_enabled=effective_network_enabled,
        cache_enabled=cache_enabled,
    )
    papers = deduplicate_literature_papers([*connector_papers, *_offline_papers(brief)])
    source_counts = dict(Counter(item.source for item in papers))
    connector_errors = [
        error
        for status in source_statuses
        for error in status.errors
    ]
    cache_hit_count = sum(status.cache_hit_count for status in source_statuses)
    payload = {
        "scout_id": "literature_scout_v1",
        "project_id": brief.project_id,
        "brief_id": brief.brief_id,
        "domain_literature_strategy": (
            domain_strategy.model_dump(mode="json")
            if domain_strategy is not None
            else None
        ),
        "search_queries": search_queries,
        "similar_papers": [item.model_dump(mode="json") for item in papers],
        "source_statuses": [item.model_dump(mode="json") for item in source_statuses],
        "source_counts": source_counts,
        "cache_hit_count": cache_hit_count,
        "network_enabled": effective_network_enabled,
        "connector_errors": connector_errors,
        "methods": _dedupe(
            [
                method
                for item in papers
                for method in (item.methods or ([item.method] if item.method else []))
            ]
        ),
        "datasets": _dedupe([dataset for item in papers for dataset in item.datasets]),
        "metrics": _dedupe([metric for item in papers for metric in item.metrics]),
        "known_sota": _dedupe([item.known_sota or "" for item in papers]),
    }
    scout = AutoResearchLiteratureScoutRead(
        generated_at=_utcnow(),
        scout_fingerprint=_fingerprint(payload),
        **payload,
    )
    domain_result = build_domain_literature_result(
        strategy=domain_strategy,
        scout=scout,
    )
    if domain_result is None:
        return scout
    payload["domain_literature_result"] = domain_result.model_dump(mode="json")
    return AutoResearchLiteratureScoutRead(
        generated_at=_utcnow(),
        scout_fingerprint=_fingerprint(payload),
        **payload,
    )


def literature_insights_from_scout(
    scout: AutoResearchLiteratureScoutRead,
    *,
    include_offline: bool = False,
) -> list[LiteratureInsight]:
    synthetic_sources = {"offline_project_context", "fixture_offline"}
    insights: list[LiteratureInsight] = []
    for paper in scout.similar_papers:
        if not include_offline and paper.source in synthetic_sources:
            continue
        methods = paper.methods or ([paper.method] if paper.method else [])
        metric_label = ", ".join(paper.metrics[:3]) or "the target metric"
        dataset_label = ", ".join(paper.datasets[:3]) or "the target dataset"
        result_text = " ".join(paper.reported_results[:2])
        insight_parts = [
            paper.abstract,
            paper.full_text_excerpt,
            result_text,
            paper.known_sota,
        ]
        insight = _norm(" ".join(part for part in insight_parts if part))
        if not insight:
            insight = paper.evidence
        gap_hint = (
            f"Test whether {dataset_label} still has an unresolved, experimentally testable gap "
            f"around {metric_label}."
        )
        insights.append(
            LiteratureInsight(
                paper_id=paper.paper_id,
                title=paper.title,
                year=paper.year,
                source=paper.source,
                insight=insight,
                method_hint=", ".join(methods[:2]) or None,
                gap_hint=gap_hint,
                methodological_detail=", ".join(methods[:4]) or None,
                limitation=(
                    "Literature scout metadata is abstract-level only; "
                    "claims need full-paper verification."
                    if paper.abstract
                    else (
                        "Literature scout metadata lacks an abstract; "
                        "verify before publish positioning."
                    )
                ),
                relevance=(
                    f"relevance_score={paper.relevance_score}; datasets={dataset_label}; "
                    f"metrics={metric_label}; extraction_level={paper.extraction_level}; "
                    f"novelty_risk_signal={paper.novelty_risk_signal}."
                ),
            )
        )
    return insights


def _gap_for_hypothesis(
    brief: AutoResearchResearchBriefRead,
    scout: AutoResearchLiteratureScoutRead,
    *,
    hypothesis_id: str | None,
    index: int,
) -> AutoResearchGapCandidateRead:
    hypothesis = next((item for item in brief.hypothesis_bank if item.hypothesis_id == hypothesis_id), None)
    if hypothesis is None:
        hypothesis = brief.hypothesis_bank[index - 1] if index - 1 < len(brief.hypothesis_bank) else None
    direction = (
        next((item for item in brief.research_directions if hypothesis is not None and item.direction_id == hypothesis.direction_id), None)
        if hypothesis is not None
        else None
    )
    direction_id = direction.direction_id if direction is not None else None
    target = direction.candidate_dataset if direction is not None else (brief.candidate_datasets[0] if brief.candidate_datasets else "selected dataset")
    metric = direction.primary_metric if direction is not None else (brief.candidate_metrics[0] if brief.candidate_metrics else "primary metric")
    evidence = [
        paper.paper_id
        for paper in scout.similar_papers
        if direction is None or target in paper.datasets or metric in paper.metrics
    ][:3]
    recommendation = (
        "change_research_question"
        if brief.idea_too_generic
        else "change_experiment_design"
        if direction is not None and direction.novelty_risk == "high"
        else "proceed"
    )
    return AutoResearchGapCandidateRead(
        gap_id=f"gap_{index}_{_slug(direction_id or hypothesis_id or brief.brief_id)}",
        description=(
            f"Test whether the idea has contribution only after narrowing to `{target}` with `{metric}` "
            "and explicit baseline/ablation evidence."
        ),
        literature_evidence=evidence,
        experimentally_testable=bool(direction is not None and direction.required_baselines and direction.candidate_metrics),
        validation_target=f"{target} / {metric}",
        recommended_direction_id=direction_id,
        recommended_hypothesis_id=hypothesis.hypothesis_id if hypothesis is not None else None,
        recommendation=recommendation,
        rationale=(
            "The broader idea overlaps with existing method/task framing; the narrower gap is testable "
            "because the brief already binds dataset, metric, baselines, and ablations."
        ),
    )


def build_gap_miner(
    brief: AutoResearchResearchBriefRead,
    *,
    literature_scout: AutoResearchLiteratureScoutRead,
) -> AutoResearchGapMinerRead:
    gap_candidates = [
        _gap_for_hypothesis(
            brief,
            literature_scout,
            hypothesis_id=item.hypothesis_id,
            index=index,
        )
        for index, item in enumerate(brief.hypothesis_bank[:5], start=1)
    ]
    max_overlap = max((item.overlap_score for item in literature_scout.similar_papers), default=0)
    idea_duplicate_risk = "high" if brief.idea_too_generic or max_overlap >= 8 else "medium" if max_overlap >= 4 else "low"
    restatement = any(
        baseline.lower() in brief.original_idea.lower()
        for baseline in brief.candidate_baselines
    )
    recommended = next((item for item in gap_candidates if item.experimentally_testable), None)
    blockers: list[str] = []
    warnings: list[str] = []
    if not literature_scout.similar_papers:
        blockers.append("No offline or cached literature signals are available for this brief.")
    if idea_duplicate_risk == "high":
        warnings.append("The idea appears too broad or highly overlapping before gap narrowing.")
    if restatement:
        warnings.append("The idea may restate an existing baseline; require a changed research question.")
    if recommended is None:
        blockers.append("No gap candidate is currently tied to executable dataset/metric/baseline evidence.")
    payload = {
        "miner_id": "gap_miner_v1",
        "project_id": brief.project_id,
        "brief_id": brief.brief_id,
        "idea_duplicate_risk": idea_duplicate_risk,
        "idea_is_existing_method_restatement": restatement,
        "change_research_question": bool(brief.idea_too_generic or restatement or idea_duplicate_risk == "high"),
        "change_experiment_design": any(item.recommendation == "change_experiment_design" for item in gap_candidates),
        "recommended_narrower_gap": recommended.description if recommended is not None else None,
        "gap_candidates": [item.model_dump(mode="json") for item in gap_candidates],
        "warnings": sorted(set(warnings)),
        "blockers": blockers,
    }
    return AutoResearchGapMinerRead(
        generated_at=_utcnow(),
        miner_fingerprint=_fingerprint(payload),
        **payload,
    )


def scout_and_mine_gaps(
    brief: AutoResearchResearchBriefRead,
    *,
    sources: list[str] | None = None,
    limit_per_source: int = 3,
    cache_enabled: bool = True,
    network_enabled: bool | None = None,
) -> AutoResearchResearchBriefRead:
    scout = build_literature_scout_with_options(
        brief,
        sources=sources,
        limit_per_source=limit_per_source,
        cache_enabled=cache_enabled,
        network_enabled=network_enabled,
    )
    miner = build_gap_miner(brief, literature_scout=scout)
    domain_literature_result = scout.domain_literature_result
    domain_protocol = build_domain_experiment_protocol(
        brief,
        benchmark_resolver=brief.domain_benchmark_resolver,
    )
    domain_status = domain_readiness_status(
        literature_result=domain_literature_result,
        benchmark_resolver=brief.domain_benchmark_resolver,
        protocol=domain_protocol,
    )
    claim_ceiling = domain_claim_ceiling(
        literature_result=domain_literature_result,
        benchmark_resolver=brief.domain_benchmark_resolver,
        protocol=domain_protocol,
    )
    next_action = (
        "blocked"
        if brief.status == "blocked" or brief.next_action == "blocked" or brief.domain_blockers
        else "create_run"
        if brief.allow_experiments and not miner.blockers
        else "select_direction"
    )
    return brief.model_copy(
        update={
            "literature_scout": scout,
            "gap_miner": miner,
            "domain_literature_strategy": scout.domain_literature_strategy or brief.domain_literature_strategy,
            "domain_literature_result": domain_literature_result,
            "domain_experiment_protocol": domain_protocol,
            "domain_readiness_status": domain_status,
            "domain_claim_ceiling": claim_ceiling,
            "domain_required_followups": _dedupe(
                [
                    *brief.domain_required_followups,
                    *(
                        domain_literature_result.required_followups
                        if domain_literature_result is not None
                        else []
                    ),
                    *(domain_protocol.required_followups if domain_protocol is not None else []),
                ]
            ),
            "domain_kill_criteria": _dedupe(
                [
                    *brief.domain_kill_criteria,
                    *(
                        domain_literature_result.kill_criteria
                        if domain_literature_result is not None
                        else []
                    ),
                    *(domain_protocol.kill_criteria if domain_protocol is not None else []),
                ]
            ),
            "novelty_search_plan": _dedupe([*brief.novelty_search_plan, *scout.search_queries]),
            "updated_at": _utcnow(),
            "next_action": next_action,
        }
    )
