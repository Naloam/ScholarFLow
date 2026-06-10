from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchEvaluationTaskKind,
    AutoResearchSystemEvaluationMetricRead,
    AutoResearchSystemEvaluationRead,
    AutoResearchSystemEvaluationTaskRead,
)
from services.autoresearch.meta_analysis import build_cross_run_meta_analysis
from services.autoresearch.repository import (
    evaluation_case_audit_file_path,
    evaluation_case_suite_file_path,
    load_evaluation_case_audit,
    load_evaluation_case_suite,
    load_evaluation_metrics,
    load_system_paper_material,
    list_runs,
    system_paper_material_file_path,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _score(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return round((numerator / denominator) * 100)


def _task(
    *,
    task_kind: AutoResearchEvaluationTaskKind,
    title: str,
    description: str,
    target_capabilities: list[str],
    required_artifacts: list[str],
    mapped_run_ids: list[str],
    score: int,
    blockers: list[str],
) -> AutoResearchSystemEvaluationTaskRead:
    return AutoResearchSystemEvaluationTaskRead(
        task_id=f"eval_{task_kind}",
        task_kind=task_kind,
        title=title,
        description=description,
        target_capabilities=target_capabilities,
        required_artifacts=required_artifacts,
        mapped_run_ids=mapped_run_ids,
        score=score,
        blockers=blockers,
    )


def _suite_tasks(persisted_suite) -> list[AutoResearchSystemEvaluationTaskRead]:
    titles = {
        "toy_task": "Toy Task",
        "medium_benchmark_task": "Medium Benchmark Task",
        "literature_heavy_task": "Literature-Heavy Task",
        "claim_evidence_vertical_task": "Claim-Evidence Vertical Task",
        "ablation_heavy_task": "Ablation-Heavy Task",
        "failed_hypothesis_task": "Failed-Hypothesis Task",
    }
    descriptions = {
        "toy_task": "Deterministic trace verifies idea-to-evidence review package behavior.",
        "medium_benchmark_task": "Deterministic trace verifies benchmark/protocol/package readiness behavior.",
        "literature_heavy_task": "Deterministic trace verifies literature/gap validation and scoped review package behavior.",
        "claim_evidence_vertical_task": "Deterministic trace verifies claim-evidence vertical, revision, package, and final-gate honesty.",
        "ablation_heavy_task": "Deterministic trace verifies ablation-heavy planning and claim-ceiling preservation.",
        "failed_hypothesis_task": "Deterministic trace verifies failed execution or blocker evidence retention.",
    }
    capabilities = {
        "toy_task": ["stage timeline", "evidence ledger", "review package"],
        "medium_benchmark_task": ["benchmark resolver", "typed execution", "package readiness"],
        "literature_heavy_task": ["literature scout", "gap validation", "claim ceiling"],
        "claim_evidence_vertical_task": ["revision loop", "submission package", "final gate"],
        "ablation_heavy_task": ["ablation planning", "repair readiness", "claim evidence"],
        "failed_hypothesis_task": ["failure timeline", "negative evidence", "blocker honesty"],
    }
    tasks: list[AutoResearchSystemEvaluationTaskRead] = []
    for task_kind in titles:
        task_cases = [
            case for case in persisted_suite.cases if case.task_kind == task_kind
        ]
        completed = [
            case
            for case in task_cases
            if case.score >= 100 and not case.blockers and case.trace is not None
        ]
        blockers = [
            f"{case.case_id}: " + "; ".join(case.blockers)
            for case in task_cases
            if case.blockers
        ]
        tasks.append(
            _task(
                task_kind=task_kind,
                title=titles[task_kind],
                description=descriptions[task_kind],
                target_capabilities=capabilities[task_kind],
                required_artifacts=[
                    "evaluation_trace_json",
                    "evaluation_case_audit_json",
                    "system_metrics_json",
                ],
                mapped_run_ids=[
                    str(case.trace.case_id)
                    for case in task_cases
                    if case.trace is not None and case.trace.case_id is not None
                ],
                score=_score(len(completed), max(len(task_cases), 1)),
                blockers=blockers,
            )
        )
    return tasks


def build_system_evaluation(project_id: str) -> AutoResearchSystemEvaluationRead:
    persisted_suite = load_evaluation_case_suite(project_id)
    persisted_metrics = load_evaluation_metrics(project_id)
    persisted_audit = load_evaluation_case_audit(project_id)
    persisted_material = load_system_paper_material(project_id)
    runs = [run for run in list_runs(project_id) if run.status == "done"]
    run_count = len(runs)
    contribution_runs = [run for run in runs if getattr(run, "reviewer_simulation", None) is not None]
    novelty_runs = [run for run in runs if getattr(run, "reviewer_simulation", None) is not None]
    design_runs = [
        run
        for run in runs
        if run.artifact is not None and run.paper_compile_report is not None
    ]
    failed_signal_runs = [
        run
        for run in runs
        if run.artifact is not None and (run.artifact.failed_trials or run.artifact.negative_results)
    ]
    meta = build_cross_run_meta_analysis(project_id)

    legacy_tasks = [
        _task(
            task_kind="toy_task",
            title="Toy Task",
            description="Small controlled run verifies the end-to-end autonomous research loop.",
            target_capabilities=["artifact persistence", "review gate", "publish package"],
            required_artifacts=["run_json", "run_artifact_json", "review_json"],
            mapped_run_ids=[run.id for run in runs[:1]],
            score=_score(1 if runs else 0, 1),
            blockers=[] if runs else ["No completed run is available for the toy task."],
        ),
        _task(
            task_kind="medium_benchmark_task",
            title="Medium Benchmark Task",
            description="Benchmark-backed run verifies publication-grade evidence handling.",
            target_capabilities=["benchmark card", "methodology audit", "publication readiness"],
            required_artifacts=["benchmark_json", "run_benchmark_card_json", "run_methodology_audit_json"],
            mapped_run_ids=[run.id for run in design_runs],
            score=_score(len(design_runs), max(run_count, 1)),
            blockers=[] if design_runs else ["No completed run has both artifacts and paper compile evidence."],
        ),
        _task(
            task_kind="literature_heavy_task",
            title="Literature-Heavy Task",
            description="Literature-grounded run verifies novelty and contribution screening.",
            target_capabilities=["contribution detection", "novelty risk detection", "literature positioning"],
            required_artifacts=["run_contribution_assessment_json", "run_literature_graph_json", "run_novelty_validation_json"],
            mapped_run_ids=[run.id for run in novelty_runs],
            score=_score(len(novelty_runs), max(run_count, 1)),
            blockers=[] if novelty_runs else ["No completed run has reviewer simulation evidence."],
        ),
        _task(
            task_kind="ablation_heavy_task",
            title="Ablation-Heavy Task",
            description="Ablation-aware run verifies component-level claim support.",
            target_capabilities=["ablation coverage", "claim-evidence consistency"],
            required_artifacts=["run_experiment_design_json", "run_claim_evidence_matrix_json"],
            mapped_run_ids=[
                run.id
                for run in runs
                if run.spec is not None and run.spec.ablations
            ],
            score=_score(
                sum(1 for run in runs if run.spec is not None and run.spec.ablations),
                max(run_count, 1),
            ),
            blockers=[] if any(run.spec is not None and run.spec.ablations for run in runs) else ["No completed run includes ablation specs."],
        ),
        _task(
            task_kind="failed_hypothesis_task",
            title="Failed-Hypothesis Task",
            description="Failure-bearing run verifies failure-driven replanning.",
            target_capabilities=["failure analysis", "research replan", "rerun plan"],
            required_artifacts=["run_failure_analysis_json", "run_research_replan_json"],
            mapped_run_ids=[run.id for run in failed_signal_runs],
            score=_score(len(failed_signal_runs), max(run_count, 1)),
            blockers=[] if failed_signal_runs else ["No completed run currently exercises failed-hypothesis evidence."],
        ),
    ]
    tasks = _suite_tasks(persisted_suite) if persisted_suite is not None else legacy_tasks

    legacy_metrics = [
        AutoResearchSystemEvaluationMetricRead(
            metric_id="contribution_detection_accuracy",
            label="Contribution Detection Accuracy",
            score=_score(len(contribution_runs), max(run_count, 1)),
            numerator=len(contribution_runs),
            denominator=max(run_count, 1),
            rationale="Uses completed runs with reviewer simulation as audited contribution-detection cases.",
        ),
        AutoResearchSystemEvaluationMetricRead(
            metric_id="novelty_risk_detection",
            label="Novelty Risk Detection",
            score=_score(len(novelty_runs), max(run_count, 1)),
            numerator=len(novelty_runs),
            denominator=max(run_count, 1),
            rationale="Counts completed runs that passed through literature/novelty-aware reviewer simulation.",
        ),
        AutoResearchSystemEvaluationMetricRead(
            metric_id="experiment_design_completeness",
            label="Experiment Design Completeness",
            score=_score(len(design_runs), max(run_count, 1)),
            numerator=len(design_runs),
            denominator=max(run_count, 1),
            rationale="Counts runs with executable artifact evidence and paper compile evidence.",
        ),
        AutoResearchSystemEvaluationMetricRead(
            metric_id="claim_evidence_consistency",
            label="Claim-Evidence Consistency",
            score=_score(sum(1 for run in runs if run.claim_evidence_matrix is not None), max(run_count, 1)),
            numerator=sum(1 for run in runs if run.claim_evidence_matrix is not None),
            denominator=max(run_count, 1),
            rationale="Counts runs with persisted claim-evidence ledgers.",
        ),
        AutoResearchSystemEvaluationMetricRead(
            metric_id="reviewer_score_improvement",
            label="Reviewer Score Improvement",
            score=_score(sum(1 for run in runs if getattr(run, "reviewer_simulation", None) is not None), max(run_count, 1)),
            numerator=sum(1 for run in runs if getattr(run, "reviewer_simulation", None) is not None),
            denominator=max(run_count, 1),
            rationale="Counts runs that have standardized reviewer simulation outputs.",
        ),
        AutoResearchSystemEvaluationMetricRead(
            metric_id="reproducibility_package_completeness",
            label="Reproducibility Package Completeness",
            score=_score(sum(1 for run in runs if run.generated_code_path and run.artifact is not None), max(run_count, 1)),
            numerator=sum(1 for run in runs if run.generated_code_path and run.artifact is not None),
            denominator=max(run_count, 1),
            rationale="Counts runs with code and artifact evidence required for reproduction.",
        ),
    ]
    metrics = persisted_metrics or legacy_metrics

    completed = [task for task in tasks if task.score >= 60 and not task.blockers]
    blockers = [blocker for task in tasks for blocker in task.blockers]
    if persisted_suite is None:
        blockers.append(
            "Goal 8 deterministic evaluation suite has not been materialized; run /evaluation-cases first."
        )
    elif persisted_audit is not None and persisted_audit.missing_case_classes:
        blockers.append(
            "Goal 8 evaluation case audit is missing required classes: "
            + ", ".join(persisted_audit.missing_case_classes)
        )
    warnings = []
    if persisted_suite is None and meta.blockers:
        warnings.extend(meta.blockers)
    if persisted_suite is None:
        warnings.append(
            "System-level metrics are using run-level legacy evidence until Goal 8 suite artifacts exist."
        )
    overall_score = round(sum(metric.score for metric in metrics) / len(metrics)) if metrics else 0
    materials = (
        [
            section.title
            for section in persisted_material.sections
        ]
        if persisted_material is not None
        else [
            "System architecture",
            "Autonomous research loop",
            "Artifact integrity design",
            "Publish gate",
            "Case studies",
        ]
    )
    payload = {
        "evaluation_id": "system_level_evaluation_v1",
        "project_id": project_id,
        "task_count": len(tasks),
        "completed_task_count": len(completed),
        "overall_score": overall_score,
        "tasks": [task.model_dump(mode="json") for task in tasks],
        "metrics": [metric.model_dump(mode="json") for metric in metrics],
        "evaluation_suite_artifact_path": (
            evaluation_case_suite_file_path(project_id) if persisted_suite is not None else None
        ),
        "evaluation_case_audit_path": (
            persisted_audit.audit_artifact_path
            if persisted_audit is not None
            else (
                evaluation_case_audit_file_path(project_id)
                if persisted_suite is not None
                else None
            )
        ),
        "system_paper_material_path": (
            persisted_material.material_artifact_path
            if persisted_material is not None
            else (
                system_paper_material_file_path(project_id)
                if persisted_suite is not None
                else None
            )
        ),
        "scholarflow_paper_materials": materials,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchSystemEvaluationRead(
        generated_at=_utcnow(),
        evaluation_fingerprint=_fingerprint(payload),
        **payload,
    )
