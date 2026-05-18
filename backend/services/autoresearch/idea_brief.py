from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchIdeaFeasibilityAssessmentRead,
    AutoResearchIdeaRequest,
    AutoResearchResearchBriefRead,
    AutoResearchResearchDirectionRead,
    AutoResearchRunRequest,
    AutoResearchContributionType,
    AutoResearchPaperTier,
    BenchmarkSource,
    TaskFamily,
)
from services.autoresearch.benchmarks import build_experiment_spec, builtin_benchmark, infer_task_family


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


def build_research_brief(
    *,
    project_id: str,
    payload: AutoResearchIdeaRequest,
) -> AutoResearchResearchBriefRead:
    original_idea = _normalize_text(payload.idea)
    domain = payload.domain
    idea_too_generic = _is_generic_idea(original_idea)
    family_source = payload.benchmark if payload.benchmark is not None else None
    task_families = _preferred_task_families(
        idea=f"{original_idea} {domain or ''}",
        task_family_hint=payload.task_family_hint,
    )
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
            source=family_source,
            target_tier=payload.target_tier,
            allow_web=payload.allow_web,
            allow_experiments=payload.allow_experiments,
            budget_label=payload.resource_budget.budget_label,
            idea_too_generic=idea_too_generic,
        )
        for index, family in enumerate(task_families, start=1)
    ][:5]
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

    selected = max(directions, key=_selection_key) if directions else None
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
    selection_reason = (
        f"Selected `{selected.direction_id}` because it has the best balance of feasibility "
        f"({selected.feasibility_score:.2f}), novelty risk `{selected.novelty_risk}`, executable evidence, "
        f"and publish potential `{selected.publish_potential}`."
        if selected is not None
        else None
    )
    now = _utcnow()
    payload_for_fingerprint = {
        "project_id": project_id,
        "original_idea": original_idea,
        "domain": domain,
        "allow_web": payload.allow_web,
        "allow_experiments": payload.allow_experiments,
        "target_tier": payload.target_tier,
        "resource_budget": payload.resource_budget.model_dump(mode="json"),
        "directions": [item.model_dump(mode="json") for item in directions],
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
        ],
        kill_criteria=_dedupe([criterion for item in directions for criterion in item.kill_criteria]),
        publish_potential=publish_potential,
        research_directions=directions,
        direction_count=len(directions),
        selected_direction_id=selected.direction_id if selected is not None else None,
        selection_reason=selection_reason,
        next_action="build_hypothesis_bank",
        allow_web=payload.allow_web,
        allow_experiments=payload.allow_experiments,
        target_tier=payload.target_tier,
        resource_budget=payload.resource_budget,
        brief_fingerprint=_fingerprint(payload_for_fingerprint),
    )
    return brief


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
