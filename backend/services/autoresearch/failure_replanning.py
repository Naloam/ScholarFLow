from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchClaimStrength,
    AutoResearchContributionAssessmentRead,
    AutoResearchExperimentDesignRead,
    AutoResearchFailureAnalysisRead,
    AutoResearchFailureFindingRead,
    AutoResearchFailureType,
    AutoResearchNoveltyValidationRead,
    AutoResearchPublicationReadinessRead,
    AutoResearchResearchActionKind,
    AutoResearchResearchReplanActionRead,
    AutoResearchResearchReplanRead,
    AutoResearchRevisionPriority,
    AutoResearchRunRead,
)


_STRONG_CLAIM_STRENGTHS: set[AutoResearchClaimStrength] = {
    "statistically_supported",
    "literature_positioned",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:96] or "item"


def _publication_profile(run: AutoResearchRunRead) -> bool:
    return bool(run.request is not None and run.request.execution_profile == "publication")


def _selected_candidate_id(run: AutoResearchRunRead) -> str | None:
    if run.portfolio is not None and run.portfolio.selected_candidate_id:
        return run.portfolio.selected_candidate_id
    selected = next((item for item in run.candidates if item.selected_round_index is not None), None)
    return selected.id if selected is not None else None


def _primary_metric(run: AutoResearchRunRead) -> str | None:
    if run.artifact is not None and run.artifact.primary_metric:
        return run.artifact.primary_metric
    if run.spec is not None and run.spec.metrics:
        return run.spec.metrics[0].name
    return None


def _metric_goal(run: AutoResearchRunRead, metric: str | None) -> str:
    if run.spec is not None and metric is not None:
        found = next((item for item in run.spec.metrics if item.name == metric), None)
        if found is not None:
            return found.goal.lower()
    return "maximize"


def _objective_system(run: AutoResearchRunRead) -> str | None:
    artifact = run.artifact
    if artifact is not None:
        return artifact.objective_system or artifact.best_system
    return None


def _system_score(run: AutoResearchRunRead, system: str, metric: str) -> float | None:
    artifact = run.artifact
    if artifact is None:
        return None
    for item in artifact.aggregate_system_results:
        value = item.mean_metrics.get(metric)
        if item.system == system and isinstance(value, (int, float)):
            return float(value)
    for item in artifact.system_results:
        value = item.metrics.get(metric)
        if item.system == system and isinstance(value, (int, float)):
            return float(value)
    return None


def _baseline_scores(run: AutoResearchRunRead, *, metric: str) -> dict[str, float]:
    if run.spec is None:
        return {}
    scores: dict[str, float] = {}
    for baseline in run.spec.baselines:
        score = _system_score(run, baseline.name, metric)
        if score is not None:
            scores[baseline.name] = score
    return scores


def _candidate_underperforms_baseline(
    run: AutoResearchRunRead,
) -> tuple[str, float, str, float] | None:
    metric = _primary_metric(run)
    candidate = _objective_system(run)
    if metric is None or candidate is None:
        return None
    candidate_score = _system_score(run, candidate, metric)
    if candidate_score is None and run.artifact is not None and isinstance(run.artifact.objective_score, (int, float)):
        candidate_score = float(run.artifact.objective_score)
    if candidate_score is None:
        return None
    baseline_scores = _baseline_scores(run, metric=metric)
    if not baseline_scores:
        return None
    goal = _metric_goal(run, metric)
    if "min" in goal or "lower" in goal:
        best_baseline_name, best_baseline_score = min(baseline_scores.items(), key=lambda item: item[1])
        underperforms = candidate_score > best_baseline_score
    else:
        best_baseline_name, best_baseline_score = max(baseline_scores.items(), key=lambda item: item[1])
        underperforms = candidate_score < best_baseline_score
    if underperforms:
        return candidate, candidate_score, best_baseline_name, best_baseline_score
    return None


def _finding(
    *,
    index: int,
    failure_type: AutoResearchFailureType,
    severity: str,
    summary: str,
    detail: str,
    trigger: str,
    evidence_refs: list[str],
    recommended_action: AutoResearchResearchActionKind,
    blocks_publication: bool,
) -> AutoResearchFailureFindingRead:
    return AutoResearchFailureFindingRead(
        failure_id=f"failure_{index}_{_slug(failure_type)}",
        failure_type=failure_type,
        severity=severity,
        summary=summary,
        detail=detail,
        trigger=trigger,
        evidence_refs=evidence_refs,
        recommended_action=recommended_action,
        blocks_publication=blocks_publication,
    )


def build_failure_analysis(
    run: AutoResearchRunRead,
    *,
    experiment_design: AutoResearchExperimentDesignRead | None = None,
    contribution_assessment: AutoResearchContributionAssessmentRead | None = None,
    novelty_validation: AutoResearchNoveltyValidationRead | None = None,
    publication_readiness: AutoResearchPublicationReadinessRead | None = None,
) -> AutoResearchFailureAnalysisRead:
    publication_profile = _publication_profile(run)
    findings: list[AutoResearchFailureFindingRead] = []

    def add(
        failure_type: AutoResearchFailureType,
        *,
        severity: str,
        summary: str,
        detail: str,
        trigger: str,
        evidence_refs: list[str],
        recommended_action: AutoResearchResearchActionKind,
        blocks_publication: bool | None = None,
    ) -> None:
        findings.append(
            _finding(
                index=len(findings) + 1,
                failure_type=failure_type,
                severity=severity,
                summary=summary,
                detail=detail,
                trigger=trigger,
                evidence_refs=evidence_refs,
                recommended_action=recommended_action,
                blocks_publication=publication_profile if blocks_publication is None else blocks_publication,
            )
        )

    artifact = run.artifact
    if run.status in {"failed", "canceled"}:
        add(
            "artifact_incomplete",
            severity="high",
            summary="Run did not complete successfully.",
            detail=f"Run status is `{run.status}`; research claims cannot be promoted until execution finishes.",
            trigger="run_status",
            evidence_refs=["run_json"],
            recommended_action="rerun_plan",
            blocks_publication=True,
        )
    if artifact is None:
        add(
            "artifact_incomplete",
            severity="high",
            summary="Experiment artifact is missing.",
            detail="No persisted result artifact is available for failure diagnosis or publication evidence.",
            trigger="missing_artifact",
            evidence_refs=["run_artifact_json"],
            recommended_action="rerun_plan",
            blocks_publication=True,
        )
    elif artifact.status != "done":
        add(
            "artifact_incomplete",
            severity="high",
            summary="Experiment artifact is not complete.",
            detail=f"Artifact status is `{artifact.status}`; rerun or repair execution before interpreting the result.",
            trigger="artifact_status",
            evidence_refs=["run_artifact_json"],
            recommended_action="rerun_plan",
            blocks_publication=True,
        )
    elif artifact.failed_trials:
        failed_examples = "; ".join(item.summary for item in artifact.failed_trials[:3])
        add(
            "artifact_incomplete",
            severity="medium",
            summary="Experiment contains failed trials.",
            detail=f"{len(artifact.failed_trials)} failed trial(s) remain in the artifact. Examples: {failed_examples}",
            trigger="failed_trials",
            evidence_refs=["run_artifact_json"],
            recommended_action="rerun_plan",
        )

    if experiment_design is not None:
        baseline_blockers = [
            item
            for item in experiment_design.blockers
            if "baseline" in item.lower() or "fair" in item.lower()
        ]
        if baseline_blockers:
            add(
                "baseline_insufficient",
                severity="high",
                summary="Baseline plan is insufficient for publication claims.",
                detail="; ".join(baseline_blockers),
                trigger="experiment_design_baseline_gate",
                evidence_refs=["run_experiment_design_json", "run_spec_json"],
                recommended_action="add_baseline",
            )
        elif publication_profile and experiment_design.fair_baseline_count < 2:
            add(
                "baseline_insufficient",
                severity="high",
                summary="Publication design lacks two fair baselines.",
                detail="A publishable run needs at least a naive baseline and a strong conventional baseline under the same metric/seed protocol.",
                trigger="fair_baseline_count",
                evidence_refs=["run_experiment_design_json"],
                recommended_action="add_baseline",
            )

        missing_ablations = [
            item
            for item in experiment_design.ablation_plan
            if item.planned and not item.observed
        ]
        if missing_ablations:
            labels = ", ".join(item.ablation_name or item.component for item in missing_ablations[:5])
            add(
                "ablation_unsupported_claim",
                severity="high" if publication_profile else "medium",
                summary="Planned ablations do not support the current claim set.",
                detail=f"Missing observed ablation result(s): {labels}. Mechanism claims should be downgraded or the ablations rerun.",
                trigger="ablation_observation_gap",
                evidence_refs=["run_experiment_design_json", "run_artifact_json"],
                recommended_action="add_ablation",
            )

    if contribution_assessment is not None and contribution_assessment.contribution_claims:
        unsupported_core = [
            item
            for item in contribution_assessment.contribution_claims
            if item.core
            and item.contribution_type in {"new_method", "new_system", "analysis_framework"}
            and item.claim_strength not in _STRONG_CLAIM_STRENGTHS
        ]
        if unsupported_core and experiment_design is not None and not any(
            item.observed for item in experiment_design.ablation_plan
        ):
            examples = "; ".join(item.text for item in unsupported_core[:3])
            add(
                "ablation_unsupported_claim",
                severity="medium",
                summary="Core method/system claims lack ablation support.",
                detail=f"{len(unsupported_core)} core claim(s) are not statistically or literature positioned and no observed ablation supports the mechanism. Examples: {examples}",
                trigger="claim_strength_ablation_gap",
                evidence_refs=["run_contribution_assessment_json", "run_experiment_design_json"],
                recommended_action="downgrade_contribution_claim",
            )

    if artifact is not None:
        failed_acceptance = [
            item
            for item in artifact.acceptance_checks
            if not item.passed and item.rule_kind in {"objective_metric_comparison", "significance_test_reporting"}
        ]
        if failed_acceptance:
            details = "; ".join(item.detail for item in failed_acceptance[:3])
            add(
                "performance_failure",
                severity="high",
                summary="Objective acceptance checks failed.",
                detail=details,
                trigger="acceptance_checks",
                evidence_refs=["run_artifact_json", "run_spec_json"],
                recommended_action="modify_hypothesis",
            )

        underperformance = _candidate_underperforms_baseline(run)
        if underperformance is not None:
            candidate, candidate_score, baseline, baseline_score = underperformance
            metric = _primary_metric(run) or "primary_metric"
            add(
                "performance_failure",
                severity="high",
                summary="Candidate does not beat the strongest observed baseline.",
                detail=(
                    f"`{candidate}` has {metric}={candidate_score:.4g}, while `{baseline}` has "
                    f"{metric}={baseline_score:.4g}; the current hypothesis should be revised or abandoned."
                ),
                trigger="candidate_vs_baseline_score",
                evidence_refs=["run_artifact_json", "run_experiment_design_json"],
                recommended_action="modify_hypothesis",
            )

        objective = (_objective_system(run) or "").lower()
        negative_candidate_results = [
            item
            for item in artifact.negative_results
            if item.subject.lower() == objective
            or item.subject.lower() in {"candidate", "candidate_method", "candidate_system"}
        ]
        metric_goal = _metric_goal(run, _primary_metric(run))
        negative_candidate_results = [
            item
            for item in negative_candidate_results
            if item.delta is not None
            and (
                item.delta > 0
                if ("min" in metric_goal or "lower" in metric_goal)
                else item.delta < 0
            )
        ]
        if negative_candidate_results:
            examples = "; ".join(item.detail for item in negative_candidate_results[:3])
            add(
                "performance_failure",
                severity="high",
                summary="Negative result applies to the candidate method.",
                detail=examples,
                trigger="negative_candidate_result",
                evidence_refs=["run_artifact_json"],
                recommended_action="downgrade_contribution_claim",
            )

        failed_or_underpowered_tests = [
            item
            for item in artifact.significance_tests
            if not item.significant or item.adequately_powered is False
        ]
        supported_tests = [
            item
            for item in artifact.significance_tests
            if item.significant and item.adequately_powered is not False
        ]
        if failed_or_underpowered_tests:
            examples = "; ".join(item.detail for item in failed_or_underpowered_tests[:3])
            significance_acceptance = [
                item
                for item in artifact.acceptance_checks
                if item.rule_kind == "significance_test_reporting"
            ]
            significance_acceptance_failed = any(not item.passed for item in significance_acceptance)
            literature_positioned_core = bool(
                contribution_assessment is not None
                and any(
                    item.core and item.claim_strength == "literature_positioned"
                    for item in contribution_assessment.contribution_claims
                )
            )
            blocks_statistical_publish = publication_profile and not supported_tests and (
                significance_acceptance_failed
                or (not significance_acceptance and not literature_positioned_core)
            )
            add(
                "statistical_not_significant",
                severity="high" if blocks_statistical_publish else "medium",
                summary=(
                    "Statistical evidence does not support the claim."
                    if blocks_statistical_publish
                    else "Some statistical comparisons are not significant."
                ),
                detail=examples,
                trigger="significance_tests",
                evidence_refs=["run_artifact_json"],
                recommended_action="rerun_plan",
                blocks_publication=blocks_statistical_publish,
            )
        elif publication_profile and experiment_design is not None and experiment_design.statistical_test_plan.observed_significance_test_count < 1:
            add(
                "statistical_not_significant",
                severity="high",
                summary="Publication run has no observed significance test.",
                detail="The experiment design requires statistical tests, but the artifact does not contain a completed significance result.",
                trigger="missing_significance_test",
                evidence_refs=["run_experiment_design_json", "run_artifact_json"],
                recommended_action="rerun_plan",
            )

    if novelty_validation is not None:
        novelty_blockers = list(novelty_validation.blockers)
        weak_novelty_warning = (
            novelty_validation.duplicate_risk == "high"
            or novelty_validation.gap_validity in {"invalid", "missing"}
            or novelty_validation.recommendation in {"change_research_question", "change_experiment_design"}
        )
        if novelty_blockers or weak_novelty_warning:
            detail_parts = []
            if novelty_blockers:
                detail_parts.append("; ".join(novelty_blockers))
            detail_parts.append(
                f"duplicate_risk={novelty_validation.duplicate_risk}, "
                f"incremental_risk={novelty_validation.incremental_risk}, "
                f"gap_validity={novelty_validation.gap_validity}, "
                f"recommendation={novelty_validation.recommendation}"
            )
            add(
                "novelty_insufficient",
                severity="high" if novelty_blockers else "medium",
                summary="Novelty validation does not support the current paper framing.",
                detail=" ".join(detail_parts),
                trigger="novelty_validation_gate",
                evidence_refs=["run_literature_graph_json", "run_novelty_validation_json"],
                recommended_action=(
                    "abandon_direction"
                    if novelty_blockers and novelty_validation.duplicate_risk == "high"
                    else "adjust_task_scope"
                ),
                blocks_publication=bool(novelty_blockers),
            )

    if publication_readiness is not None:
        artifact_blockers = [
            item
            for item in publication_readiness.blockers
            if any(marker in item.lower() for marker in ("artifact", "seed", "significance", "ablation"))
        ]
        if artifact_blockers and not any(
            finding.failure_type in {"artifact_incomplete", "statistical_not_significant", "ablation_unsupported_claim"}
            for finding in findings
        ):
            add(
                "artifact_incomplete",
                severity="medium",
                summary="Readiness gate reports incomplete experimental evidence.",
                detail="; ".join(artifact_blockers[:5]),
                trigger="publication_readiness",
                evidence_refs=["run_publication_readiness_json"],
                recommended_action="rerun_plan",
            )

    blockers = [item.summary for item in findings if item.blocks_publication]
    warnings = [item.summary for item in findings if not item.blocks_publication]
    payload = {
        "analysis_id": "failure_analysis_v1",
        "project_id": run.project_id,
        "run_id": run.id,
        "selected_candidate_id": _selected_candidate_id(run),
        "findings": [item.model_dump(mode="json") for item in findings],
        "complete": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchFailureAnalysisRead(
        generated_at=_utcnow(),
        finding_count=len(findings),
        high_severity_count=sum(1 for item in findings if item.severity == "high"),
        publication_blocker_count=len(blockers),
        performance_failure_count=sum(1 for item in findings if item.failure_type == "performance_failure"),
        baseline_failure_count=sum(1 for item in findings if item.failure_type == "baseline_insufficient"),
        ablation_failure_count=sum(1 for item in findings if item.failure_type == "ablation_unsupported_claim"),
        statistical_failure_count=sum(1 for item in findings if item.failure_type == "statistical_not_significant"),
        novelty_failure_count=sum(1 for item in findings if item.failure_type == "novelty_insufficient"),
        artifact_failure_count=sum(1 for item in findings if item.failure_type == "artifact_incomplete"),
        analysis_fingerprint=_fingerprint(payload),
        **payload,
    )


def _action(
    *,
    action_kind: AutoResearchResearchActionKind,
    priority: AutoResearchRevisionPriority,
    title: str,
    rationale: str,
    source_failure_ids: list[str],
    expected_outputs: list[str],
    target: str | None = None,
) -> AutoResearchResearchReplanActionRead:
    return AutoResearchResearchReplanActionRead(
        action_id=f"research_action_{_slug(action_kind)}_{_slug('_'.join(source_failure_ids) or title)}",
        action_kind=action_kind,
        priority=priority,
        title=title,
        rationale=rationale,
        target=target,
        source_failure_ids=source_failure_ids,
        expected_outputs=expected_outputs,
    )


def build_research_replan(
    run: AutoResearchRunRead,
    *,
    failure_analysis: AutoResearchFailureAnalysisRead,
    experiment_design: AutoResearchExperimentDesignRead | None = None,
    contribution_assessment: AutoResearchContributionAssessmentRead | None = None,
    novelty_validation: AutoResearchNoveltyValidationRead | None = None,
) -> AutoResearchResearchReplanRead:
    findings_by_type: dict[AutoResearchFailureType, list[AutoResearchFailureFindingRead]] = {}
    for finding in failure_analysis.findings:
        findings_by_type.setdefault(finding.failure_type, []).append(finding)

    actions: list[AutoResearchResearchReplanActionRead] = []

    def add_once(action: AutoResearchResearchReplanActionRead) -> None:
        if any(item.action_id == action.action_id for item in actions):
            return
        actions.append(action)

    if findings_by_type.get("performance_failure"):
        source_ids = [item.failure_id for item in findings_by_type["performance_failure"]]
        add_once(
            _action(
                action_kind="modify_hypothesis",
                priority="high",
                title="Revise the hypothesis around observed performance limits",
                rationale="The candidate did not satisfy objective performance evidence; the next run should test a narrower or different causal claim.",
                target=run.spec.hypothesis if run.spec is not None else run.topic,
                source_failure_ids=source_ids,
                expected_outputs=["run_spec_json", "run_experiment_design_json", "run_artifact_json"],
            )
        )
        add_once(
            _action(
                action_kind="rerun_plan",
                priority="high",
                title="Run a follow-up experiment after hypothesis repair",
                rationale="A failed objective claim needs new experimental evidence rather than a stronger paper narrative.",
                source_failure_ids=source_ids,
                expected_outputs=["run_artifact_json", "run_methodology_audit_json", "run_publication_readiness_json"],
            )
        )

    if findings_by_type.get("baseline_insufficient"):
        source_ids = [item.failure_id for item in findings_by_type["baseline_insufficient"]]
        add_once(
            _action(
                action_kind="add_baseline",
                priority="high",
                title="Add fair naive and strong conventional baselines",
                rationale="The current baseline set cannot justify a publication-level comparison.",
                source_failure_ids=source_ids,
                expected_outputs=["run_spec_json", "run_experiment_design_json", "run_artifact_json"],
            )
        )
        add_once(
            _action(
                action_kind="repair_experiment_design",
                priority="high",
                title="Repair the experiment protocol before rerun",
                rationale="Baseline fairness must be fixed before interpreting candidate gains.",
                source_failure_ids=source_ids,
                expected_outputs=["run_experiment_design_json", "run_research_protocol_json"],
            )
        )

    if findings_by_type.get("ablation_unsupported_claim"):
        source_ids = [item.failure_id for item in findings_by_type["ablation_unsupported_claim"]]
        add_once(
            _action(
                action_kind="add_ablation",
                priority="high",
                title="Add ablations for unsupported method components",
                rationale="Mechanism claims require component-level evidence; otherwise the method claim must be weakened.",
                source_failure_ids=source_ids,
                expected_outputs=["run_spec_json", "run_experiment_design_json", "run_artifact_json"],
            )
        )
        add_once(
            _action(
                action_kind="downgrade_contribution_claim",
                priority="medium",
                title="Downgrade unsupported mechanism claims",
                rationale="Claims should not be stronger than the observed ablation evidence.",
                source_failure_ids=source_ids,
                expected_outputs=["run_contribution_assessment_json", "run_claim_evidence_matrix_json", "run_paper_markdown"],
            )
        )

    if findings_by_type.get("statistical_not_significant"):
        source_ids = [item.failure_id for item in findings_by_type["statistical_not_significant"]]
        add_once(
            _action(
                action_kind="rerun_plan",
                priority="high",
                title="Rerun with a statistical recovery plan",
                rationale="A non-significant or missing test requires additional seeds, a declared test, confidence intervals, and effect size reporting.",
                source_failure_ids=source_ids,
                expected_outputs=["run_spec_json", "run_artifact_json", "run_methodology_audit_json"],
            )
        )
        add_once(
            _action(
                action_kind="downgrade_contribution_claim",
                priority="medium",
                title="Downgrade result claims until statistical support exists",
                rationale="The paper should not present an unsupported effect as a publication contribution.",
                source_failure_ids=source_ids,
                expected_outputs=["run_contribution_assessment_json", "run_paper_markdown"],
            )
        )

    if findings_by_type.get("novelty_insufficient"):
        source_ids = [item.failure_id for item in findings_by_type["novelty_insufficient"]]
        action_kind: AutoResearchResearchActionKind = (
            "abandon_direction"
            if any(item.recommended_action == "abandon_direction" for item in findings_by_type["novelty_insufficient"])
            else "adjust_task_scope"
        )
        add_once(
            _action(
                action_kind=action_kind,
                priority="high",
                title=(
                    "Abandon the current direction because novelty is duplicated"
                    if action_kind == "abandon_direction"
                    else "Refocus the research question around a validated literature gap"
                ),
                rationale="Novelty validation indicates that the current framing is not a publishable contribution without changing the question or design.",
                source_failure_ids=source_ids,
                expected_outputs=["run_literature_graph_json", "run_novelty_validation_json", "run_spec_json"],
            )
        )

    if findings_by_type.get("artifact_incomplete"):
        source_ids = [item.failure_id for item in findings_by_type["artifact_incomplete"]]
        add_once(
            _action(
                action_kind="rerun_plan",
                priority="high",
                title="Rerun or repair incomplete experiment artifacts",
                rationale="Incomplete artifacts cannot support claims or publication readiness.",
                source_failure_ids=source_ids,
                expected_outputs=["run_artifact_json", "run_generated_code", "run_methodology_audit_json"],
            )
        )
        add_once(
            _action(
                action_kind="repair_experiment_design",
                priority="medium",
                title="Add failure-mode controls to the experiment design",
                rationale="The next protocol should explicitly address the observed artifact failure modes.",
                source_failure_ids=source_ids,
                expected_outputs=["run_experiment_design_json", "run_research_protocol_json"],
            )
        )

    hypothesis_update = None
    if any(action.action_kind == "modify_hypothesis" for action in actions):
        hypothesis_update = "Revise the hypothesis to match observed baseline and statistical evidence before the next run."
    elif contribution_assessment is not None and contribution_assessment.blockers:
        hypothesis_update = "Downgrade or restate contribution claims that are not currently supported."

    task_scope_update = None
    if any(action.action_kind in {"adjust_task_scope", "abandon_direction"} for action in actions):
        task_scope_update = "Re-anchor the task scope to a literature-backed, experimentally testable gap."
    elif novelty_validation is not None and novelty_validation.warnings:
        task_scope_update = "Clarify the literature gap before treating this run as a paper candidate."

    rerun_required = any(
        action.action_kind in {"rerun_plan", "add_baseline", "add_ablation", "repair_experiment_design"}
        for action in actions
    )
    abandon_recommended = any(action.action_kind == "abandon_direction" for action in actions)
    claim_downgrade_required = any(action.action_kind == "downgrade_contribution_claim" for action in actions)
    experiment_design_repair_required = any(
        action.action_kind in {"repair_experiment_design", "add_baseline", "add_ablation"}
        for action in actions
    )
    blockers: list[str] = []
    if failure_analysis.publication_blocker_count > 0 and not actions:
        blockers.append("Failure analysis found publication blockers but no research action could be generated.")
    if failure_analysis.publication_blocker_count > 0 and rerun_required:
        blockers.append("Final publish is blocked until the research replan is executed and new evidence is reviewed.")
    if abandon_recommended:
        blockers.append("Final publish is blocked because the current research direction should be abandoned or reframed.")
    warnings: list[str] = []
    if not actions:
        warnings.append("No failure-driven research actions were needed for this run.")

    payload = {
        "replan_id": "research_replan_v1",
        "project_id": run.project_id,
        "run_id": run.id,
        "selected_candidate_id": failure_analysis.selected_candidate_id,
        "hypothesis_update": hypothesis_update,
        "task_scope_update": task_scope_update,
        "actions": [item.model_dump(mode="json") for item in actions],
        "rerun_required": rerun_required,
        "abandon_recommended": abandon_recommended,
        "claim_downgrade_required": claim_downgrade_required,
        "experiment_design_repair_required": experiment_design_repair_required,
        "complete": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchResearchReplanRead(
        generated_at=_utcnow(),
        action_count=len(actions),
        replan_fingerprint=_fingerprint(payload),
        **payload,
    )
