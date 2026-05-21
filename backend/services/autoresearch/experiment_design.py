from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchExperimentAblationPlanRead,
    AutoResearchExperimentBaselinePlanRead,
    AutoResearchExperimentDesignRead,
    AutoResearchExperimentFailureModeRead,
    AutoResearchExperimentSeedPlanRead,
    AutoResearchExperimentStatisticalTestPlanRead,
    AutoResearchExperimentSweepPlanRead,
    AutoResearchRunRead,
)
from services.autoresearch.research_readiness import PUBLICATION_MIN_COMPLETED_SEEDS


_NAIVE_BASELINE_MARKERS = ("majority", "random", "dummy", "constant", "chance")
_STRONG_BASELINE_MARKERS = (
    "bm25",
    "keyword",
    "logistic",
    "naive_bayes",
    "ridge",
    "svm",
    "tfidf",
    "xgboost",
)
_METHOD_COMPONENT_MARKERS = (
    "ablation",
    "calibration",
    "classifier",
    "encoder",
    "feature",
    "filter",
    "memory",
    "planner",
    "policy",
    "prompt",
    "ranker",
    "reranker",
    "retriever",
    "scorer",
    "tool",
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:80] or "component"


def _profile(run: AutoResearchRunRead) -> str:
    return run.request.execution_profile if run.request is not None else "exploratory"


def _primary_metric(run: AutoResearchRunRead) -> str | None:
    if run.spec is not None and run.spec.metrics:
        return run.spec.metrics[0].name
    if run.artifact is not None:
        return run.artifact.primary_metric
    return None


def _observed_systems(run: AutoResearchRunRead) -> set[str]:
    artifact = run.artifact
    if artifact is None:
        return set()
    systems: set[str] = set()
    for name in (artifact.best_system, artifact.objective_system):
        if name:
            systems.add(name)
    for item in artifact.system_results:
        if item.system:
            systems.add(item.system)
    for item in artifact.aggregate_system_results:
        if item.system:
            systems.add(item.system)
    for seed in artifact.per_seed_results:
        for item in seed.system_results:
            if item.system:
                systems.add(item.system)
    for sweep in artifact.sweep_results:
        for name in (sweep.best_system, sweep.objective_system):
            if name:
                systems.add(name)
        for item in sweep.aggregate_system_results:
            if item.system:
                systems.add(item.system)
    return systems


def _observed_sweeps(run: AutoResearchRunRead) -> list[str]:
    artifact = run.artifact
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


def _candidate_method_name(run: AutoResearchRunRead) -> str:
    if run.artifact is not None:
        for name in (run.artifact.objective_system, run.artifact.best_system):
            if name:
                return name
    if run.portfolio is not None and run.portfolio.selected_candidate_id:
        candidate = next(
            (item for item in run.candidates if item.id == run.portfolio.selected_candidate_id),
            None,
        )
        if candidate is not None:
            return candidate.title
    return "candidate_method"


def _baseline_type(name: str) -> str:
    normalized = name.lower()
    if any(marker in normalized for marker in _NAIVE_BASELINE_MARKERS):
        return "naive"
    if any(marker in normalized for marker in _STRONG_BASELINE_MARKERS):
        return "strong_conventional"
    return "strong_conventional"


def _baseline_plan(run: AutoResearchRunRead) -> list[AutoResearchExperimentBaselinePlanRead]:
    spec = run.spec
    observed = _observed_systems(run)
    metric = _primary_metric(run)
    planned_seed_count = len(spec.seeds) if spec is not None else 0
    items: list[AutoResearchExperimentBaselinePlanRead] = []
    seen: set[str] = set()
    for baseline in (spec.baselines if spec is not None else []):
        baseline_type = _baseline_type(baseline.name)
        fair = bool(metric and planned_seed_count)
        items.append(
            AutoResearchExperimentBaselinePlanRead(
                name=baseline.name,
                baseline_type=baseline_type,
                required=True,
                present_in_spec=True,
                present_in_results=baseline.name in observed,
                fair_comparison=fair,
                rationale=(
                    f"Compare `{baseline.name}` on the same benchmark, primary metric `{metric or 'missing'}`, "
                    f"and {planned_seed_count} planned seed(s)."
                ),
            )
        )
        seen.add(baseline.name)
    candidate_name = _candidate_method_name(run)
    items.append(
        AutoResearchExperimentBaselinePlanRead(
            name=candidate_name,
            baseline_type="candidate_method",
            required=True,
            present_in_spec=True,
            present_in_results=not observed or candidate_name in observed,
            fair_comparison=bool(metric and planned_seed_count),
            rationale=(
                "The candidate method is the intervention whose claims must be compared against baselines, "
                "even when its executed system name also appears in baseline metadata."
            ),
        )
    )
    return items


def _selected_candidate_text(run: AutoResearchRunRead) -> str:
    selected_id = run.portfolio.selected_candidate_id if run.portfolio is not None else None
    candidate = next((item for item in run.candidates if item.id == selected_id), None) if selected_id else None
    if candidate is None:
        candidate = next((item for item in run.candidates if item.selected_round_index is not None), None)
    if candidate is not None:
        return " ".join(
            [
                candidate.title,
                candidate.hypothesis,
                candidate.proposed_method,
                " ".join(candidate.planned_contributions),
                " ".join(candidate.differentiators),
            ]
        )
    if run.plan is not None:
        return " ".join(
            [
                run.plan.proposed_method,
                " ".join(run.plan.planned_contributions),
                " ".join(run.plan.experiment_outline),
            ]
        )
    return " ".join(run.spec.implementation_notes if run.spec is not None else [])


def _method_components(run: AutoResearchRunRead) -> list[str]:
    text = _selected_candidate_text(run)
    components: list[str] = []
    for raw in re.split(r"[,;/]|\band\b|\bplus\b|\bwith\b|\busing\b", text, flags=re.IGNORECASE):
        cleaned = " ".join(raw.split()).strip(" .")
        lowered = cleaned.lower()
        if len(cleaned) < 4:
            continue
        if any(marker in lowered for marker in _METHOD_COMPONENT_MARKERS):
            components.append(cleaned[:96])
    if not components and run.spec is not None:
        components = [item.description or item.name for item in run.spec.ablations]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in components:
        key = _slug(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:6]


def _ablation_plan(run: AutoResearchRunRead, observed_systems: set[str]) -> list[AutoResearchExperimentAblationPlanRead]:
    ablations = run.spec.ablations if run.spec is not None else []
    components = _method_components(run)
    if not components:
        components = [item.name for item in ablations]
    items: list[AutoResearchExperimentAblationPlanRead] = []
    used: set[str] = set()
    for index, component in enumerate(components, start=1):
        component_terms = set(_slug(component).split("_"))
        match = next(
            (
                item
                for item in ablations
                if item.name not in used
                and (component_terms & set(_slug(f"{item.name} {item.description}").split("_")))
            ),
            None,
        )
        if match is None and index <= len(ablations):
            match = ablations[index - 1]
        if match is not None:
            used.add(match.name)
        items.append(
            AutoResearchExperimentAblationPlanRead(
                component_id=f"component_{index}",
                component=component,
                ablation_name=match.name if match is not None else None,
                planned=match is not None,
                observed=bool(match is not None and match.name in observed_systems),
                rationale=(
                    f"Ablate `{component}` to test whether the method component is needed for the claimed effect."
                ),
            )
        )
    return items


def _planned_statistics(run: AutoResearchRunRead) -> set[str]:
    if run.spec is None:
        return set()
    return {
        statistic
        for rule in run.spec.acceptance_criteria
        for statistic in rule.required_statistics
    }


def _has_significance_rule(run: AutoResearchRunRead) -> bool:
    if run.spec is None:
        return False
    return any(
        rule.kind == "significance_test_reporting" or "significance" in rule.description.lower()
        for rule in run.spec.acceptance_criteria
    )


def _statistical_test_choice(run: AutoResearchRunRead) -> str:
    planned_seed_count = len(run.spec.seeds) if run.spec is not None else 0
    if planned_seed_count >= 5:
        return "paired_t_test"
    if planned_seed_count >= 2:
        return "permutation_test"
    return "bootstrap"


def build_experiment_design(run: AutoResearchRunRead) -> AutoResearchExperimentDesignRead:
    spec = run.spec
    profile = _profile(run)
    publication_profile = profile == "publication"
    observed_systems = _observed_systems(run)
    baseline_plan = _baseline_plan(run)
    ablation_plan = _ablation_plan(run, observed_systems)
    planned_seed_count = len(spec.seeds) if spec is not None else 0
    completed_seed_count = len(run.artifact.per_seed_results) if run.artifact is not None else 0
    minimum_completed_seed_count = PUBLICATION_MIN_COMPLETED_SEEDS if publication_profile else 1
    seed_plan = AutoResearchExperimentSeedPlanRead(
        planned_seeds=list(spec.seeds) if spec is not None else [],
        planned_seed_count=planned_seed_count,
        minimum_completed_seed_count=minimum_completed_seed_count,
        completed_seed_count=completed_seed_count,
        sufficient_for_profile=planned_seed_count >= minimum_completed_seed_count,
        rationale=(
            f"Plan {planned_seed_count} seed(s); profile `{profile}` requires at least "
            f"{minimum_completed_seed_count} completed seed(s) before strong claims."
        ),
    )
    observed_sweeps = _observed_sweeps(run)
    planned_sweeps = [item.label for item in spec.sweeps] if spec is not None else []
    sweep_plan = AutoResearchExperimentSweepPlanRead(
        planned_sweeps=planned_sweeps,
        planned_sweep_count=len(planned_sweeps),
        observed_sweeps=observed_sweeps,
        covers_search_space=bool(planned_sweeps),
        rationale=(
            "Sweeps define the planned configuration space before results are interpreted."
            if planned_sweeps
            else "No sweep is registered; treat the run as a fixed-configuration experiment."
        ),
    )
    planned_statistics = _planned_statistics(run)
    significance_planned = _has_significance_rule(run) or planned_seed_count >= 2
    statistical_test_plan = AutoResearchExperimentStatisticalTestPlanRead(
        primary_metric=_primary_metric(run),
        recommended_test=_statistical_test_choice(run),
        comparison_unit="seed" if planned_seed_count >= 2 else "aggregate",
        requires_confidence_interval=True,
        requires_effect_size=True,
        requires_power_note=publication_profile,
        planned_statistic_count=len(planned_statistics),
        observed_significance_test_count=(
            len(run.artifact.significance_tests) if run.artifact is not None else 0
        ),
        complete=bool(
            _primary_metric(run)
            and (not publication_profile or "confidence_interval" in planned_statistics)
            and (not publication_profile or significance_planned)
        ),
        rationale=(
            "Use paired tests when multiple seeds are planned; require confidence intervals, "
            "effect sizes, and a power note for publication claims."
        ),
    )
    naive_present = any(item.baseline_type == "naive" for item in baseline_plan)
    strong_present = any(item.baseline_type == "strong_conventional" for item in baseline_plan)
    candidate_present = any(item.baseline_type == "candidate_method" for item in baseline_plan)
    fair_baseline_count = sum(
        1 for item in baseline_plan if item.baseline_type != "candidate_method" and item.fair_comparison
    )
    ablation_coverage = (
        sum(1 for item in ablation_plan if item.planned) / len(ablation_plan)
        if ablation_plan
        else 0.0
    )
    blockers: list[str] = []
    warnings: list[str] = []
    if spec is None:
        blockers.append("Experiment design requires a persisted experiment spec.")
    if not candidate_present:
        blockers.append("Experiment design requires an explicit candidate method.")
    if not naive_present:
        (blockers if publication_profile else warnings).append(
            "Experiment design requires a naive baseline such as majority, random, or dummy."
        )
    if not strong_present:
        (blockers if publication_profile else warnings).append(
            "Experiment design requires a strong conventional baseline, not just a naive baseline."
        )
    if publication_profile and fair_baseline_count < 2:
        blockers.append("Publication design requires at least two fair baselines: one naive and one strong conventional.")
    if publication_profile and not seed_plan.sufficient_for_profile:
        blockers.append("Publication design does not plan enough seeds for statistical claims.")
    complex_method = len(ablation_plan) > 1 or bool(ablation_plan and spec is not None and len(spec.ablations) > 1)
    if publication_profile and complex_method and ablation_coverage < 1.0:
        blockers.append("Complex publication methods require an ablation for every planned method component.")
    elif not ablation_plan:
        (blockers if publication_profile else warnings).append(
            "Experiment design has no ablation or sensitivity plan."
        )
    if publication_profile and not statistical_test_plan.complete:
        blockers.append("Publication design lacks a complete statistical test plan with CI and significance requirements.")
    if not sweep_plan.covers_search_space:
        warnings.append("No sweep plan was registered; conclusions should avoid hyperparameter robustness claims.")

    failure_modes = [
        AutoResearchExperimentFailureModeRead(
            mode_id="performance_failure",
            category="performance_failure",
            trigger="Candidate fails to outperform the strongest planned baseline.",
            planned_response="Replan the hypothesis, add diagnostics, or downgrade the contribution claim.",
            severity="high",
        ),
        AutoResearchExperimentFailureModeRead(
            mode_id="baseline_fairness_failure",
            category="baseline_fairness_failure",
            trigger="A baseline uses a different dataset split, metric, or seed protocol.",
            planned_response="Normalize the baseline protocol before interpreting any candidate gain.",
            severity="high",
        ),
        AutoResearchExperimentFailureModeRead(
            mode_id="ablation_coverage_failure",
            category="ablation_coverage_failure",
            trigger="A claimed method component has no matching ablation.",
            planned_response="Add the ablation or remove the mechanism claim from the paper.",
            severity="medium",
        ),
        AutoResearchExperimentFailureModeRead(
            mode_id="statistical_power_failure",
            category="statistical_power_failure",
            trigger="Effect estimates are underpowered or confidence intervals overlap the null effect.",
            planned_response="Increase seeds, switch to a nonparametric test, or report an inconclusive result.",
            severity="high",
        ),
        AutoResearchExperimentFailureModeRead(
            mode_id="artifact_failure",
            category="artifact_failure",
            trigger="Runtime, metric, data, or artifact contract failures prevent a complete result package.",
            planned_response="Repair execution artifacts before paper or contribution claims are strengthened.",
            severity="medium",
        ),
    ]
    scored_checks = [
        spec is not None,
        candidate_present,
        naive_present,
        strong_present,
        fair_baseline_count >= 2 if publication_profile else fair_baseline_count >= 1,
        seed_plan.sufficient_for_profile,
        bool(ablation_plan),
        statistical_test_plan.complete,
        bool(failure_modes),
    ]
    completeness_score = round(100 * sum(1 for item in scored_checks if item) / len(scored_checks))
    completeness = "complete" if not blockers else "blocked" if publication_profile else "partial"
    payload = {
        "design_id": "experiment_design_v1",
        "project_id": run.project_id,
        "run_id": run.id,
        "execution_profile": profile,
        "baseline_plan": [item.model_dump(mode="json") for item in baseline_plan],
        "ablation_plan": [item.model_dump(mode="json") for item in ablation_plan],
        "seed_plan": seed_plan.model_dump(mode="json"),
        "sweep_plan": sweep_plan.model_dump(mode="json"),
        "statistical_test_plan": statistical_test_plan.model_dump(mode="json"),
        "failure_mode_analysis": [item.model_dump(mode="json") for item in failure_modes],
        "naive_baseline_present": naive_present,
        "strong_baseline_present": strong_present,
        "candidate_method_present": candidate_present,
        "fair_baseline_count": fair_baseline_count,
        "ablation_coverage": round(ablation_coverage, 4),
        "completeness_score": completeness_score,
        "completeness": completeness,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchExperimentDesignRead(
        generated_at=_utcnow(),
        design_fingerprint=_fingerprint(payload),
        **payload,
    )
