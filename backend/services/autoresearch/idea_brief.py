from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchDirectionSelectionRead,
    AutoResearchHypothesisBankEntryRead,
    AutoResearchIdeaFeasibilityAssessmentRead,
    AutoResearchIdeaRequest,
    AutoResearchRejectedDirectionRead,
    AutoResearchResearchBriefRead,
    AutoResearchResearchDirectionRead,
    AutoResearchRunRequest,
    AutoResearchContributionType,
    AutoResearchPaperTier,
    BenchmarkSource,
    TaskFamily,
)
from services.autoresearch.benchmarks import build_experiment_spec, builtin_benchmark, infer_task_family
from services.autoresearch.domain_router import (
    benchmark_source_for_template,
    get_domain_template,
    route_domain,
)


_GENERIC_IDEA_TERMS = {
    "ai",
    "agent",
    "agents",
    "better",
    "deep",
    "improve",
    "improving",
    "llm",
    "llms",
    "machine",
    "model",
    "models",
    "novel",
    "research",
    "system",
    "systems",
}
_STOPWORDS = {
    "about",
    "after",
    "against",
    "and",
    "better",
    "build",
    "for",
    "from",
    "how",
    "into",
    "make",
    "more",
    "new",
    "novel",
    "research",
    "study",
    "the",
    "this",
    "using",
    "with",
}
_TASK_FAMILY_ORDER: tuple[TaskFamily, ...] = (
    "text_classification",
    "ir_reranking",
    "tabular_classification",
    "llm_evaluation",
)
_PAPER_TIER_ORDER: dict[AutoResearchPaperTier, int] = {
    "technical_report": 0,
    "workshop_candidate": 1,
    "conference_candidate": 2,
    "strong_conference_candidate": 3,
}
_DIRECTION_SELECTOR_WEIGHTS: dict[str, float] = {
    "novelty": 0.2,
    "feasibility": 0.3,
    "evidence_availability": 0.2,
    "resource_cost": 0.1,
    "publish_potential": 0.2,
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str, *, fallback: str = "idea") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug[:64] or fallback


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _terms(value: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for term in re.findall(r"[a-z][a-z0-9_]+", value.lower()):
        if len(term) < 3 or term in _STOPWORDS:
            continue
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _is_generic_idea(idea: str) -> bool:
    normalized = idea.lower()
    terms = _terms(normalized)
    concrete_terms = [term for term in terms if term not in _GENERIC_IDEA_TERMS]
    has_task_anchor = any(
        marker in normalized
        for marker in (
            "classification",
            "dataset",
            "benchmark",
            "retrieval",
            "reranking",
            "ranking",
            "metric",
            "ablation",
            "failure",
            "stability",
            "tabular",
            "evidence",
            "citation",
            "agent",
            "tool",
            "memory",
            "planning",
        )
    )
    return len(idea.split()) < 7 or len(concrete_terms) < 3 or not has_task_anchor


def _title_case(value: str) -> str:
    cleaned = _normalize_text(value).strip(".")
    if not cleaned:
        return "Scoped Research Idea"
    return cleaned[0].upper() + cleaned[1:]


def _preferred_task_families(
    *,
    idea: str,
    task_family_hint: TaskFamily | None,
) -> list[TaskFamily]:
    inferred = infer_task_family(idea, task_family_hint)
    families = [inferred]
    lowered = idea.lower()
    if any(marker in lowered for marker in ("paper", "citation", "evidence", "retrieval", "search", "rank")):
        families.append("ir_reranking")
    if any(marker in lowered for marker in ("feature", "tabular", "stability", "configuration", "telemetry")):
        families.append("tabular_classification")
    if any(marker in lowered for marker in ("agent", "llm", "prompt", "tool", "memory", "planning")):
        families.append("text_classification")
    for family in _TASK_FAMILY_ORDER:
        families.append(family)

    ordered: list[TaskFamily] = []
    seen: set[TaskFamily] = set()
    for family in families:
        if family in seen:
            continue
        seen.add(family)
        ordered.append(family)
    return ordered[:4]


def _topic_for_family(idea: str, domain: str | None, family: TaskFamily, index: int) -> str:
    base = _title_case(idea)
    domain_fragment = f" in {domain}" if domain else ""
    if family == "ir_reranking":
        return f"{base}: evidence reranking{domain_fragment}"
    if family == "tabular_classification":
        return f"{base}: measurable stability classification{domain_fragment}"
    if family == "llm_evaluation":
        return f"{base}: prompting strategy evaluation{domain_fragment}"
    if index == 1:
        return f"{base}: scoped text benchmark{domain_fragment}"
    return f"{base}: lightweight classification study{domain_fragment}"


def _contribution_type_for_family(family: TaskFamily, index: int) -> AutoResearchContributionType:
    if family == "ir_reranking":
        return "new_method" if index == 1 else "experimental_finding"
    if family == "tabular_classification":
        return "analysis_framework"
    if family == "llm_evaluation":
        return "experimental_finding"
    return "new_benchmark" if index >= 3 else "experimental_finding"


def _direction_publish_potential(
    *,
    target_tier: AutoResearchPaperTier,
    feasibility_score: float,
    budget_label: str,
    allow_experiments: bool,
) -> AutoResearchPaperTier:
    if not allow_experiments or feasibility_score < 0.45:
        return "technical_report"
    cap = "workshop_candidate" if budget_label == "toy" else "conference_candidate"
    target_rank = _PAPER_TIER_ORDER[target_tier]
    cap_rank = _PAPER_TIER_ORDER[cap]
    desired = min(target_rank, cap_rank)
    if feasibility_score >= 0.8 and budget_label == "publication":
        desired = min(target_rank, _PAPER_TIER_ORDER["strong_conference_candidate"])
    for tier, rank in _PAPER_TIER_ORDER.items():
        if rank == desired:
            return tier
    return "technical_report"


def _score_direction(
    *,
    family: TaskFamily,
    direction_index: int,
    allow_experiments: bool,
    budget_label: str,
    idea_too_generic: bool,
) -> float:
    base = 0.72
    if family == "ir_reranking":
        base += 0.04
    if family == "tabular_classification":
        base += 0.02
    if family == "llm_evaluation":
        base -= 0.08
    base -= (direction_index - 1) * 0.045
    if not allow_experiments:
        base -= 0.28
    if budget_label == "toy":
        base -= 0.08
    elif budget_label == "publication":
        base += 0.08
    if idea_too_generic:
        base -= 0.04
    return round(min(0.95, max(0.15, base)), 2)


def _novelty_risk(
    *,
    idea_too_generic: bool,
    family: TaskFamily,
    allow_web: bool,
) -> str:
    if idea_too_generic and not allow_web:
        return "high"
    if family == "llm_evaluation" and not allow_web:
        return "high"
    if idea_too_generic:
        return "medium"
    return "medium" if not allow_web else "low"


def _direction_from_family(
    *,
    project_id: str,
    idea: str,
    polished_idea: str,
    domain: str | None,
    family: TaskFamily,
    index: int,
    source: BenchmarkSource | None,
    target_tier: AutoResearchPaperTier,
    allow_web: bool,
    allow_experiments: bool,
    budget_label: str,
    idea_too_generic: bool,
) -> AutoResearchResearchDirectionRead:
    topic = _topic_for_family(polished_idea, domain, family, index)
    benchmark = builtin_benchmark(family, source=source, topic=topic)
    spec = build_experiment_spec(family, benchmark)
    contribution_type = _contribution_type_for_family(family, index)
    metric_names = [metric.name for metric in spec.metrics]
    baseline_names = [baseline.name for baseline in spec.baselines]
    ablation_names = [ablation.name for ablation in spec.ablations]
    primary_metric = metric_names[0] if metric_names else "primary_metric"
    feasibility_score = _score_direction(
        family=family,
        direction_index=index,
        allow_experiments=allow_experiments,
        budget_label=budget_label,
        idea_too_generic=idea_too_generic,
    )
    publish_potential = _direction_publish_potential(
        target_tier=target_tier,
        feasibility_score=feasibility_score,
        budget_label=budget_label,
        allow_experiments=allow_experiments,
    )
    direction_id = f"dir_{index}_{_slug(family)}_{_slug(spec.benchmark_name, fallback='benchmark')}"
    risk = _novelty_risk(idea_too_generic=idea_too_generic, family=family, allow_web=allow_web)
    research_question = (
        f"Can `{polished_idea}` be tested on `{spec.benchmark_name}` using {primary_metric} "
        f"against {', '.join(baseline_names[:2])}?"
    )
    hypothesis = spec.hypothesis
    method_sketch = (
        "Use the existing deterministic benchmark adapter to compare the candidate method with "
        f"{', '.join(baseline_names)} and preserve ablations"
        + (f" ({', '.join(ablation_names)})." if ablation_names else ".")
    )
    expected_evidence = [
        f"Per-system {primary_metric} result table on `{spec.dataset.name}`.",
        "Preserved run artifact with acceptance checks and environment metadata.",
        "Baseline comparison against " + ", ".join(baseline_names[:2]) + ".",
    ]
    if ablation_names:
        expected_evidence.append("Ablation evidence for " + ", ".join(ablation_names) + ".")
    if budget_label == "publication":
        expected_evidence.append("Multi-seed aggregate statistics and confidence intervals.")
    kill_criteria = [
        f"Abandon this direction if the candidate does not beat the strongest baseline on {primary_metric}.",
        "Abandon or reframe if literature scout finds a direct duplicate with no narrower gap.",
        "Downgrade to technical report if ablations or required baselines cannot be produced.",
    ]
    if not allow_experiments:
        kill_criteria.insert(0, "Do not create an execution run until experiments are allowed.")
    estimated_cost = (
        "toy built-in benchmark"
        if budget_label == "toy"
        else "standard local benchmark"
        if budget_label == "standard"
        else "publication profile with broader seed and literature requirements"
    )
    return AutoResearchResearchDirectionRead(
        direction_id=direction_id,
        title=f"{_title_case(polished_idea)} on {spec.benchmark_name}",
        research_question=research_question,
        hypothesis=hypothesis,
        task_family=family,
        target_task=spec.benchmark_description,
        candidate_dataset=spec.dataset.name,
        primary_metric=primary_metric,
        candidate_metrics=metric_names,
        required_baselines=baseline_names,
        required_ablations=ablation_names,
        method_sketch=method_sketch,
        expected_evidence=expected_evidence,
        expected_contribution_type=contribution_type,
        novelty_risk=risk,  # type: ignore[arg-type]
        feasibility_score=feasibility_score,
        estimated_cost=estimated_cost,
        publish_potential=publish_potential,
        kill_criteria=kill_criteria,
        rationale=(
            f"Direction {direction_id} narrows `{idea}` to task family `{family}`, dataset "
            f"`{spec.dataset.name}`, metric `{primary_metric}`, and explicit baseline obligations."
        ),
        run_topic=topic,
    )


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _normalize_text(item)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _feasibility(
    *,
    directions: list[AutoResearchResearchDirectionRead],
    allow_experiments: bool,
    allow_web: bool,
    budget_label: str,
    idea_too_generic: bool,
) -> AutoResearchIdeaFeasibilityAssessmentRead:
    score = round(sum(item.feasibility_score for item in directions) / max(len(directions), 1), 2)
    blockers: list[str] = []
    warnings: list[str] = []
    if not allow_experiments:
        blockers.append("Experiment execution is disabled; the brief can only prepare literature and protocol work.")
    if idea_too_generic:
        warnings.append("The original idea is too broad until anchored to a task, dataset, and metric.")
    if not allow_web:
        warnings.append("Novelty remains provisional because live literature scouting is disabled.")
    if budget_label == "toy":
        warnings.append("Toy budget limits publish potential to a technical report or workshop-style package.")
    level = "high" if score >= 0.75 and not blockers else "medium" if score >= 0.45 else "low"
    summary = (
        f"{len(directions)} executable direction(s) can be formed under a `{budget_label}` budget; "
        f"average feasibility={score:.2f}."
    )
    return AutoResearchIdeaFeasibilityAssessmentRead(
        score=score,
        level=level,  # type: ignore[arg-type]
        summary=summary,
        blockers=blockers,
        warnings=warnings,
    )


def _selection_key(direction: AutoResearchResearchDirectionRead) -> tuple[float, int, int, float]:
    novelty_penalty = {"low": 0, "medium": 1, "high": 2}[direction.novelty_risk]
    publish_rank = _PAPER_TIER_ORDER[direction.publish_potential]
    return (
        direction.feasibility_score,
        publish_rank,
        -novelty_penalty,
        1.0 / max(len(direction.required_baselines) + len(direction.required_ablations), 1),
    )


def _novelty_score(risk: str) -> float:
    return {"low": 1.0, "medium": 0.62, "high": 0.22}.get(risk, 0.5)


def _cost_score(estimated_cost: str) -> float:
    lowered = estimated_cost.lower()
    if "toy" in lowered:
        return 1.0
    if "standard" in lowered or "local" in lowered:
        return 0.78
    if "publication" in lowered:
        return 0.55
    return 0.65


def _evidence_availability_score(direction: AutoResearchResearchDirectionRead) -> float:
    evidence_units = (
        len(direction.expected_evidence)
        + len(direction.required_baselines)
        + len(direction.required_ablations)
        + len(direction.candidate_metrics)
    )
    return round(min(1.0, evidence_units / 8), 2)


def _publish_score(tier: AutoResearchPaperTier) -> float:
    return round(_PAPER_TIER_ORDER[tier] / max(_PAPER_TIER_ORDER.values()), 2)


def _selector_score(
    direction: AutoResearchResearchDirectionRead,
) -> tuple[float, dict[str, float]]:
    factors = {
        "novelty": _novelty_score(direction.novelty_risk),
        "feasibility": direction.feasibility_score,
        "evidence_availability": _evidence_availability_score(direction),
        "resource_cost": _cost_score(direction.estimated_cost),
        "publish_potential": _publish_score(direction.publish_potential),
    }
    score = sum(
        factors[key] * weight
        for key, weight in _DIRECTION_SELECTOR_WEIGHTS.items()
    )
    return round(score, 3), factors


def _hypothesis_from_direction(
    direction: AutoResearchResearchDirectionRead,
    *,
    rank: int,
) -> AutoResearchHypothesisBankEntryRead:
    score, factors = _selector_score(direction)
    evidence_requirements = _dedupe(
        [
            *direction.expected_evidence,
            *[f"Baseline: {item}" for item in direction.required_baselines],
            *[f"Ablation: {item}" for item in direction.required_ablations],
            *[f"Metric: {item}" for item in direction.candidate_metrics],
            f"Dataset: {direction.candidate_dataset}",
        ]
    )
    return AutoResearchHypothesisBankEntryRead(
        hypothesis_id=f"hyp_{rank}_{_slug(direction.direction_id, fallback='direction')}",
        direction_id=direction.direction_id,
        rank=rank,
        research_question=direction.research_question,
        hypothesis=direction.hypothesis,
        method_sketch=direction.method_sketch,
        expected_evidence=direction.expected_evidence,
        required_baselines=direction.required_baselines,
        required_ablations=direction.required_ablations,
        required_datasets=[direction.candidate_dataset],
        required_metrics=direction.candidate_metrics,
        novelty_risk=direction.novelty_risk,
        feasibility_score=direction.feasibility_score,
        evidence_requirements=evidence_requirements,
        estimated_cost=direction.estimated_cost,
        publish_potential=direction.publish_potential,
        kill_criteria=direction.kill_criteria,
        selection_score=score,
        selector_factors=factors,
        run_topic=direction.run_topic,
    )


def _rejection_reasons(
    candidate: AutoResearchHypothesisBankEntryRead,
    selected: AutoResearchHypothesisBankEntryRead,
) -> list[str]:
    reasons: list[str] = []
    if candidate.novelty_risk != "low":
        reasons.append(f"Novelty risk is `{candidate.novelty_risk}` and needs more scouting.")
    if candidate.feasibility_score < selected.feasibility_score:
        reasons.append(
            f"Feasibility score {candidate.feasibility_score:.2f} is below the selected "
            f"{selected.feasibility_score:.2f}."
        )
    if candidate.selector_factors.get("evidence_availability", 0) < selected.selector_factors.get("evidence_availability", 0):
        reasons.append("Evidence requirements are less immediately executable.")
    if _PAPER_TIER_ORDER[candidate.publish_potential] < _PAPER_TIER_ORDER[selected.publish_potential]:
        reasons.append(f"Publish potential is capped at `{candidate.publish_potential}`.")
    if candidate.selection_score < selected.selection_score:
        reasons.append(
            f"Overall selector score {candidate.selection_score:.3f} trails the selected "
            f"{selected.selection_score:.3f}."
        )
    return _dedupe(reasons)[:3] or ["Lower combined novelty, feasibility, evidence, cost, and publish score."]


def _build_hypothesis_bank_and_selection(
    directions: list[AutoResearchResearchDirectionRead],
) -> tuple[list[AutoResearchHypothesisBankEntryRead], AutoResearchDirectionSelectionRead]:
    raw_bank = [
        _hypothesis_from_direction(direction, rank=index)
        for index, direction in enumerate(directions, start=1)
    ]
    ranked_bank = sorted(
        raw_bank,
        key=lambda item: (
            item.selection_score,
            item.feasibility_score,
            _PAPER_TIER_ORDER[item.publish_potential],
            _novelty_score(item.novelty_risk),
        ),
        reverse=True,
    )
    bank = [
        item.model_copy(
            update={
                "rank": index,
                "selection_reason": (
                    f"Rank {index}: selector score {item.selection_score:.3f} from novelty "
                    f"{item.selector_factors.get('novelty', 0):.2f}, feasibility "
                    f"{item.selector_factors.get('feasibility', 0):.2f}, evidence "
                    f"{item.selector_factors.get('evidence_availability', 0):.2f}, cost "
                    f"{item.selector_factors.get('resource_cost', 0):.2f}, and publish "
                    f"{item.selector_factors.get('publish_potential', 0):.2f}."
                ),
            }
        )
        for index, item in enumerate(ranked_bank, start=1)
    ]
    selected = bank[0] if bank else None
    selection = AutoResearchDirectionSelectionRead(
        selected_hypothesis_id=selected.hypothesis_id if selected is not None else None,
        selected_direction_id=selected.direction_id if selected is not None else None,
        selection_score=selected.selection_score if selected is not None else 0.0,
        selection_reason=(
            f"Selected `{selected.hypothesis_id}` because it maximizes the weighted selector "
            "over novelty, feasibility, evidence availability, resource cost, and publish potential."
            if selected is not None
            else None
        ),
        criteria_weights=_DIRECTION_SELECTOR_WEIGHTS,
        rejected_directions=[
            AutoResearchRejectedDirectionRead(
                hypothesis_id=item.hypothesis_id,
                direction_id=item.direction_id,
                rank=item.rank,
                selection_score=item.selection_score,
                reasons=_rejection_reasons(item, selected),
            )
            for item in bank[1:]
            if selected is not None
        ],
    )
    return bank, selection


def build_research_brief(
    *,
    project_id: str,
    payload: AutoResearchIdeaRequest,
) -> AutoResearchResearchBriefRead:
    original_idea = _normalize_text(payload.idea)
    domain = payload.domain
    domain_decision = route_domain(payload)
    domain_template = get_domain_template(domain_decision.domain_id)
    idea_too_generic = _is_generic_idea(original_idea)
    domain_supported = (
        domain_decision.is_supported
        and domain_template is not None
        and domain_template.template_complete
    )
    domain_blockers = (
        []
        if domain_supported
        else _dedupe(
            [
                *domain_decision.default_blockers,
                *(domain_template.blockers if domain_template is not None else []),
            ]
        )
    )
    now = _utcnow()
    if not domain_supported:
        payload_for_fingerprint = {
            "project_id": project_id,
            "original_idea": original_idea,
            "domain": domain,
            "domain_decision": domain_decision.model_dump(mode="json"),
            "domain_template": (
                domain_template.model_dump(mode="json")
                if domain_template is not None
                else None
            ),
            "resource_budget": payload.resource_budget.model_dump(mode="json"),
            "target_tier": payload.target_tier,
            "allow_web": payload.allow_web,
            "allow_experiments": payload.allow_experiments,
        }
        brief_id = f"brief_{_slug(original_idea, fallback='idea')}_{_fingerprint(payload_for_fingerprint)[:10]}"
        blocker = (
            domain_decision.unsupported_reason
            or "Domain template is incomplete; no executable benchmark resolver can be selected."
        )
        feasibility = AutoResearchIdeaFeasibilityAssessmentRead(
            score=0.0,
            level="low",
            summary=(
                "The idea was preserved as an auditable unsupported-domain record; "
                "no hypothesis bank or experiment protocol was generated."
            ),
            blockers=_dedupe([blocker, *domain_blockers]),
            warnings=[
                "Unsupported domains must not be downgraded to unrelated toy experiments.",
            ],
        )
        return AutoResearchResearchBriefRead(
            brief_id=brief_id,
            project_id=project_id,
            generated_at=now,
            updated_at=now,
            status="blocked",
            original_idea=original_idea,
            polished_idea=_title_case(original_idea),
            domain=domain,
            domain_decision=domain_decision,
            domain_template=domain_template,
            domain_blockers=feasibility.blockers,
            idea_too_generic=idea_too_generic,
            specificity_assessment="too_generic" if idea_too_generic else "broad_but_actionable",
            scope_narrowing_recommendation=(
                "Define or select a supported ScholarFlow domain template with a deterministic "
                "benchmark resolver before creating hypotheses or experiment outputs."
            ),
            research_questions=[],
            candidate_hypotheses=[],
            expected_contribution_types=[],
            target_tasks=[],
            candidate_datasets=[],
            candidate_metrics=[],
            candidate_baselines=[],
            novelty_search_plan=[
                f"Route audit for unsupported idea: {original_idea}.",
                "Do not run literature or experiment generation until a supported domain template exists.",
            ],
            feasibility_assessment=feasibility,
            resource_assumptions=[
                f"Budget label: {payload.resource_budget.budget_label}.",
                "No execution budget was consumed because domain routing blocked the idea.",
            ],
            kill_criteria=[
                "Kill execution until the idea matches a supported domain template and benchmark resolver.",
                "Kill publication claims until real evidence exists for the requested domain.",
            ],
            publish_potential="technical_report",
            research_directions=[],
            direction_count=0,
            hypothesis_bank=[],
            hypothesis_count=0,
            selected_direction_id=None,
            selected_hypothesis_id=None,
            selection_reason=None,
            direction_selection=AutoResearchDirectionSelectionRead(
                selection_score=0.0,
                selection_reason=(
                    "No direction selected because domain routing produced an auditable blocker."
                ),
                criteria_weights=_DIRECTION_SELECTOR_WEIGHTS,
                rejected_directions=[],
            ),
            next_action="blocked",
            allow_web=payload.allow_web,
            allow_experiments=False,
            target_tier=payload.target_tier,
            resource_budget=payload.resource_budget,
            brief_fingerprint=_fingerprint(payload_for_fingerprint),
        )

    assert domain_template is not None
    family_source = (
        payload.benchmark
        if payload.benchmark is not None
        else benchmark_source_for_template(domain_template)
    )
    task_families = [domain_template.task_family] * 3
    directions = [
        _direction_from_family(
            project_id=project_id,
            idea=original_idea,
            polished_idea=(
                f"{original_idea} evaluated as a measurable benchmark study"
                if idea_too_generic
                else original_idea
            ),
            domain=domain,
            family=family,
            index=index,
            source=family_source if family == domain_template.task_family else payload.benchmark,
            target_tier=payload.target_tier,
            allow_web=payload.allow_web,
            allow_experiments=payload.allow_experiments,
            budget_label=payload.resource_budget.budget_label,
            idea_too_generic=idea_too_generic,
        )
        for index, family in enumerate(task_families, start=1)
    ][:3]
    if len(directions) < 2:
        for family in _TASK_FAMILY_ORDER:
            if any(item.task_family == family for item in directions):
                continue
            directions.append(
                _direction_from_family(
                    project_id=project_id,
                    idea=original_idea,
                    polished_idea=original_idea,
                    domain=domain,
                    family=family,
                    index=len(directions) + 1,
                    source=family_source,
                    target_tier=payload.target_tier,
                    allow_web=payload.allow_web,
                    allow_experiments=payload.allow_experiments,
                    budget_label=payload.resource_budget.budget_label,
                    idea_too_generic=idea_too_generic,
                )
            )
            if len(directions) >= 2:
                break

    hypothesis_bank, direction_selection = _build_hypothesis_bank_and_selection(directions)
    selected_hypothesis = hypothesis_bank[0] if hypothesis_bank else None
    selected = (
        next(
            (
                direction
                for direction in directions
                if selected_hypothesis is not None and direction.direction_id == selected_hypothesis.direction_id
            ),
            None,
        )
        if selected_hypothesis is not None
        else max(directions, key=_selection_key) if directions else None
    )
    polished_idea = (
        f"{_title_case(original_idea)} scoped to benchmarkable tasks with explicit datasets, metrics, baselines, and kill criteria."
        if idea_too_generic
        else f"{_title_case(original_idea)} with explicit task, dataset, metric, baseline, and ablation constraints."
    )
    scope_narrowing = (
        "The original idea is too broad; narrow it to one selected task/dataset/metric direction before creating a run."
        if idea_too_generic
        else "The idea is broad but executable once the selected direction fixes the task, dataset, metric, and baselines."
    )
    novelty_search_plan = _dedupe(
        [
            f"Search for exact duplicates of: {original_idea}.",
            *[
                f"Search `{direction.title}` with `{direction.candidate_dataset}` and `{direction.primary_metric}`."
                for direction in directions[:3]
            ],
            "Check whether the proposed method is only a restatement of an existing baseline.",
            "Mine narrower gaps that are tied to a dataset, metric, and executable ablation.",
        ]
    )[: payload.resource_budget.max_literature_queries + 2]
    feasibility = _feasibility(
        directions=directions,
        allow_experiments=payload.allow_experiments,
        allow_web=payload.allow_web,
        budget_label=payload.resource_budget.budget_label,
        idea_too_generic=idea_too_generic,
    )
    publish_potential = (
        selected.publish_potential
        if selected is not None
        else "technical_report"
    )
    selection_reason = direction_selection.selection_reason
    payload_for_fingerprint = {
        "project_id": project_id,
        "original_idea": original_idea,
        "domain": domain,
        "domain_decision": domain_decision.model_dump(mode="json"),
        "domain_template": domain_template.model_dump(mode="json"),
        "allow_web": payload.allow_web,
        "allow_experiments": payload.allow_experiments,
        "target_tier": payload.target_tier,
        "resource_budget": payload.resource_budget.model_dump(mode="json"),
        "directions": [item.model_dump(mode="json") for item in directions],
        "hypothesis_bank": [item.model_dump(mode="json") for item in hypothesis_bank],
        "direction_selection": direction_selection.model_dump(mode="json"),
    }
    brief_id = f"brief_{_slug(original_idea, fallback='idea')}_{_fingerprint(payload_for_fingerprint)[:10]}"
    brief = AutoResearchResearchBriefRead(
        brief_id=brief_id,
        project_id=project_id,
        generated_at=now,
        updated_at=now,
        original_idea=original_idea,
        polished_idea=polished_idea,
        domain=domain,
        domain_decision=domain_decision,
        domain_template=domain_template,
        domain_blockers=domain_blockers,
        idea_too_generic=idea_too_generic,
        specificity_assessment=(
            "too_generic"
            if idea_too_generic
            else "broad_but_actionable"
            if len(directions) > 1
            else "scoped"
        ),
        scope_narrowing_recommendation=scope_narrowing,
        research_questions=[item.research_question for item in directions],
        candidate_hypotheses=[item.hypothesis for item in directions],
        expected_contribution_types=_dedupe([item.expected_contribution_type for item in directions]),  # type: ignore[list-item]
        target_tasks=_dedupe([item.target_task for item in directions]),
        candidate_datasets=_dedupe([item.candidate_dataset for item in directions]),
        candidate_metrics=_dedupe([metric for item in directions for metric in item.candidate_metrics]),
        candidate_baselines=_dedupe([baseline for item in directions for baseline in item.required_baselines]),
        novelty_search_plan=novelty_search_plan,
        feasibility_assessment=feasibility,
        resource_assumptions=[
            f"Budget label: {payload.resource_budget.budget_label}.",
            f"Max rounds: {payload.resource_budget.max_rounds}.",
            f"Candidate execution limit: {payload.resource_budget.candidate_execution_limit or 'not fixed'}.",
            "No GPU is assumed unless explicitly enabled." if not payload.resource_budget.allow_gpu else "GPU may be used if the later run requests it.",
            "Literature scouting may use network search." if payload.allow_web else "Literature scouting must use offline/project context until network is allowed.",
            f"Domain template: {domain_template.template_id}.",
            *domain_decision.default_blockers,
        ],
        kill_criteria=_dedupe(
            [
                *[criterion for item in directions for criterion in item.kill_criteria],
                *domain_template.publish_readiness_constraints,
            ]
        ),
        publish_potential=publish_potential,
        research_directions=directions,
        direction_count=len(directions),
        hypothesis_bank=hypothesis_bank,
        hypothesis_count=len(hypothesis_bank),
        selected_direction_id=selected.direction_id if selected is not None else None,
        selected_hypothesis_id=selected_hypothesis.hypothesis_id if selected_hypothesis is not None else None,
        selection_reason=selection_reason,
        direction_selection=direction_selection,
        next_action="create_run" if payload.allow_experiments else "select_direction",
        allow_web=payload.allow_web,
        allow_experiments=payload.allow_experiments,
        target_tier=payload.target_tier,
        resource_budget=payload.resource_budget,
        brief_fingerprint=_fingerprint(payload_for_fingerprint),
    )
    return brief


def hypothesis_bank_from_brief(
    brief: AutoResearchResearchBriefRead,
) -> tuple[list[AutoResearchHypothesisBankEntryRead], AutoResearchDirectionSelectionRead]:
    if brief.hypothesis_bank and brief.direction_selection is not None:
        return brief.hypothesis_bank, brief.direction_selection
    return _build_hypothesis_bank_and_selection(brief.research_directions)


def selected_hypothesis_from_brief(
    brief: AutoResearchResearchBriefRead,
    *,
    hypothesis_id: str | None = None,
) -> AutoResearchHypothesisBankEntryRead:
    bank, selection = hypothesis_bank_from_brief(brief)
    selected_id = hypothesis_id or brief.selected_hypothesis_id or selection.selected_hypothesis_id
    hypothesis = next((item for item in bank if item.hypothesis_id == selected_id), None)
    if hypothesis is None:
        raise ValueError(f"Hypothesis not found: {selected_id}")
    return hypothesis


def run_request_from_selected_direction(
    brief: AutoResearchResearchBriefRead,
    *,
    direction_id: str | None = None,
    payload: AutoResearchIdeaRequest | None = None,
) -> AutoResearchRunRequest:
    selected_id = direction_id or brief.selected_direction_id
    direction = next((item for item in brief.research_directions if item.direction_id == selected_id), None)
    if direction is None:
        raise ValueError(f"Research direction not found: {selected_id}")
    resource_budget = payload.resource_budget if payload is not None else brief.resource_budget
    return AutoResearchRunRequest(
        topic=direction.run_topic,
        task_family_hint=direction.task_family,
        max_rounds=resource_budget.max_rounds,
        candidate_execution_limit=resource_budget.candidate_execution_limit,
        queue_priority=payload.queue_priority if payload is not None else "normal",
        benchmark=payload.benchmark if payload is not None else None,
        execution_backend=payload.execution_backend if payload is not None else None,
        experiment_bridge=payload.experiment_bridge if payload is not None else None,
        auto_search_literature=brief.allow_web,
        auto_fetch_literature=False,
        execution_profile=payload.execution_profile if payload is not None else "exploratory",
    )


def run_request_from_selected_hypothesis(
    brief: AutoResearchResearchBriefRead,
    *,
    hypothesis_id: str | None = None,
    payload: AutoResearchIdeaRequest | None = None,
) -> tuple[AutoResearchRunRequest, AutoResearchHypothesisBankEntryRead]:
    hypothesis = selected_hypothesis_from_brief(brief, hypothesis_id=hypothesis_id)
    run_request = run_request_from_selected_direction(
        brief,
        direction_id=hypothesis.direction_id,
        payload=payload,
    )
    return run_request, hypothesis
