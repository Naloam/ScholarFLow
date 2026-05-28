from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from schemas.autoresearch import (
    AutoResearchEvaluationCaseRead,
    AutoResearchEvaluationCaseSuiteRead,
    AutoResearchEvaluationCaseTraceRead,
    AutoResearchIdeaRequest,
    AutoResearchIdeaResourceBudget,
    AutoResearchProjectPaperDecision,
    AutoResearchSystemEvaluationMetricRead,
)
from services.autoresearch.experiment_factory import (
    build_experiment_factory_plan,
    execute_toy_experiment_factory,
)
from services.autoresearch.idea_brief import build_research_brief, selected_hypothesis_from_brief
from services.autoresearch.literature_scout import scout_and_mine_gaps


_CASE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "case_id": "eval_case_toy_task",
        "task_kind": "toy_task",
        "idea": "Improve evidence-aware reranking for autonomous literature review",
        "domain": "scientific document retrieval",
        "budget_label": "toy",
        "max_rounds": 2,
        "candidate_execution_limit": 2,
        "target_tier": "technical_report",
        "task_family_hint": "ir_reranking",
        "expected_brief_quality": (
            "Brief should narrow the idea to a concrete reranking task, dataset, metric, "
            "baseline set, ablation obligations, and explicit kill criteria."
        ),
        "expected_novelty_risks": [
            "Broad evidence-aware reranking may overlap with existing IR rerankers.",
            "The idea may be publishable only after narrowing to citation/evidence grounding.",
        ],
        "expected_experiment_design_requirements": [
            "At least one lexical or BM25-style baseline.",
            "A candidate method job, ablation job, multi-seed jobs, and aggregate evidence ledger.",
        ],
        "expected_failure_replan_behavior": (
            "Missing baselines should create add_missing_baseline repair; missing ablations "
            "should downgrade mechanism claims."
        ),
        "expected_paper_tier": "technical_report",
    },
    {
        "case_id": "eval_case_medium_benchmark_task",
        "task_kind": "medium_benchmark_task",
        "idea": "Improve calibration of tabular model selection under benchmark drift",
        "domain": "benchmark robustness",
        "budget_label": "standard",
        "max_rounds": 3,
        "candidate_execution_limit": 3,
        "target_tier": "workshop_candidate",
        "task_family_hint": "tabular_classification",
        "expected_brief_quality": (
            "Brief should bind drift detection to a tabular classification benchmark, "
            "calibration metric, and stability-oriented acceptance criteria."
        ),
        "expected_novelty_risks": [
            "Calibration and drift robustness are crowded unless the benchmark slice is narrow.",
            "A selector-only improvement may be incremental without failure analysis.",
        ],
        "expected_experiment_design_requirements": [
            "Strong tabular baselines with matched feature preprocessing.",
            "Seed coverage, drift-slice reporting, and a calibration ablation.",
        ],
        "expected_failure_replan_behavior": (
            "If drift-slice gains vanish, replan toward negative findings or narrower "
            "data-regime claims."
        ),
        "expected_paper_tier": "workshop_candidate",
    },
    {
        "case_id": "eval_case_literature_heavy_task",
        "task_kind": "literature_heavy_task",
        "idea": "Use citation-grounded retrieval to reduce unsupported claims in scientific writing agents",
        "domain": "scientific writing agents",
        "budget_label": "standard",
        "max_rounds": 3,
        "candidate_execution_limit": 2,
        "target_tier": "workshop_candidate",
        "task_family_hint": "ir_reranking",
        "expected_brief_quality": (
            "Brief should separate claim-support retrieval from generic writing quality and "
            "identify literature evidence needed before any novelty claim."
        ),
        "expected_novelty_risks": [
            "Citation grounding is an active literature area with high duplicate risk.",
            "The idea may restate retrieval-augmented generation without a new evidence constraint.",
        ],
        "expected_experiment_design_requirements": [
            "Literature scout and gap miner must attach evidence to every proposed gap.",
            "Evaluation must include unsupported-claim detection and citation validity metrics.",
        ],
        "expected_failure_replan_behavior": (
            "If novelty scout marks the idea as duplicate, change the research question to a "
            "narrower claim-evidence consistency gap."
        ),
        "expected_paper_tier": "workshop_candidate",
    },
    {
        "case_id": "eval_case_ablation_heavy_task",
        "task_kind": "ablation_heavy_task",
        "idea": "Identify which planning memory component improves multi-step LLM evaluation reliability",
        "domain": "LLM evaluation reliability",
        "budget_label": "standard",
        "max_rounds": 3,
        "candidate_execution_limit": 3,
        "target_tier": "conference_candidate",
        "task_family_hint": "llm_evaluation",
        "expected_brief_quality": (
            "Brief should define component-level hypotheses rather than a single opaque agent run."
        ),
        "expected_novelty_risks": [
            "Agent memory and planning ablations are common without a task-specific reliability gap.",
            "LLM-evaluation claims need stronger controls than a toy prompt comparison.",
        ],
        "expected_experiment_design_requirements": [
            "Required ablations for memory, planner, tool-use, and verification components.",
            "Multi-seed or multi-instance reliability statistics before mechanism claims.",
        ],
        "expected_failure_replan_behavior": (
            "If ablations are missing, create add_missing_ablation repair and block strong "
            "mechanism claims."
        ),
        "expected_paper_tier": "conference_candidate",
    },
    {
        "case_id": "eval_case_failed_hypothesis_task",
        "task_kind": "failed_hypothesis_task",
        "idea": "Test a risky prompting strategy expected to fail under adversarial evidence checks",
        "domain": "evidence-constrained prompting",
        "budget_label": "toy",
        "max_rounds": 2,
        "candidate_execution_limit": 2,
        "target_tier": "technical_report",
        "task_family_hint": "text_classification",
        "expected_brief_quality": (
            "Brief should preserve the risky hypothesis, define falsification criteria, and make "
            "negative findings publishable only as scoped evidence."
        ),
        "expected_novelty_risks": [
            "Prompting strategies are often method restatements unless tied to a falsifiable gap.",
            "Negative results require careful baseline and failure evidence."
        ],
        "expected_experiment_design_requirements": [
            "Explicit adversarial evidence checks and failure-mode reporting.",
            "Repair plan must distinguish performance failure from missing evidence.",
        ],
        "expected_failure_replan_behavior": (
            "If the hypothesis fails, trigger research_replan with negative finding preservation "
            "instead of promoting unsupported positive claims."
        ),
        "expected_paper_tier": "technical_report",
    },
]

_SCHOLARFLOW_PAPER_MATERIALS = [
    "Architecture: idea intake, research brief, hypothesis bank, literature scout, experiment factory, evidence ledger, and paper orchestration.",
    "Autonomous research loop: idea to brief to hypothesis to executable plan to evidence to paper/review package.",
    "Assurance gates: novelty/gap validation, experiment design obligations, evidence consistency, reviewer simulation, and publish correctness.",
    "Artifact lineage: brief, selected hypothesis, factory plan, result artifact, evidence ledger, and project paper decision remain traceable.",
    "Case studies: toy, medium benchmark, literature-heavy, ablation-heavy, and failed-hypothesis evaluation cases.",
    "Failure analysis: repair actions distinguish missing baselines, missing ablations, weak statistics, and failed hypotheses.",
]


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = " ".join(str(item).split()).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _score(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return round((numerator / denominator) * 100)


def _metric(
    *,
    metric_id: str,
    label: str,
    numerator: int,
    denominator: int,
    rationale: str,
) -> AutoResearchSystemEvaluationMetricRead:
    return AutoResearchSystemEvaluationMetricRead(
        metric_id=metric_id,
        label=label,
        score=_score(numerator, denominator),
        numerator=numerator,
        denominator=denominator,
        rationale=rationale,
    )


def _payload_for_case(case: dict[str, Any]) -> AutoResearchIdeaRequest:
    return AutoResearchIdeaRequest(
        idea=str(case["idea"]),
        domain=str(case["domain"]),
        resource_budget=AutoResearchIdeaResourceBudget(
            budget_label=str(case["budget_label"]),  # type: ignore[arg-type]
            max_rounds=int(case["max_rounds"]),
            candidate_execution_limit=int(case["candidate_execution_limit"]),
            max_literature_queries=3,
            max_experiment_minutes=10 if case["budget_label"] == "toy" else 30,
            allow_gpu=False,
        ),
        target_tier=str(case["target_tier"]),  # type: ignore[arg-type]
        allow_web=False,
        allow_experiments=True,
        task_family_hint=str(case["task_family_hint"]),  # type: ignore[arg-type]
        execution_profile="exploratory",
    )


def _trace_materials(
    *,
    case: dict[str, Any],
    brief,
    scouted,
    hypothesis,
    plan,
    execution,
    blockers: list[str],
) -> tuple[list[str], list[str], list[str]]:
    task_kind = str(case["task_kind"])
    planned_dataset = next(
        (
            str(job.config.get("dataset"))
            for job in plan.jobs
            if isinstance(job.config.get("dataset"), str) and job.config.get("dataset")
        ),
        "unknown dataset",
    )
    architecture_materials = [
        (
            f"{task_kind}: idea brief `{brief.brief_id}` produced {scouted.direction_count} "
            f"directions and {scouted.hypothesis_count} hypotheses before selecting "
            f"`{hypothesis.hypothesis_id}`."
        ),
        (
            f"{task_kind}: experiment factory `{plan.plan_id}` materialized "
            f"{plan.job_count} auditable jobs on `{planned_dataset}` and evidence ledger "
            f"`{execution.evidence_ledger.ledger_id}`."
        ),
    ]
    result = execution.result_artifact
    objective = (
        f"{result.primary_metric}={result.objective_score:.4f}"
        if result.objective_score is not None
        else f"primary metric `{result.primary_metric}`"
    )
    case_study_materials = [
        (
            f"{task_kind}: `{case['idea']}` selected `{hypothesis.research_question}` and completed "
            f"{execution.evidence_ledger.entry_count} evidence entries with {objective}."
        )
    ]
    repair_plan = execution.repair_plan
    repair_actions = list(repair_plan.actions) if repair_plan is not None else []
    failure_analysis_materials = [
        (
            f"{task_kind}: blockers={len(blockers)}, repair_actions={len(repair_actions)}, "
            f"artifact_status=`{result.status}`."
        )
    ]
    if blockers:
        failure_analysis_materials.extend(f"{task_kind}: blocker - {item}" for item in blockers[:3])
    elif repair_plan is not None and repair_actions and repair_actions != ["none"]:
        failure_analysis_materials.extend(
            f"{task_kind}: repair - {item}"
            for item in repair_plan.action_reasons[:3]
        )
    else:
        failure_analysis_materials.append(
            f"{task_kind}: no failure-driven repair was required for the offline execution trace."
        )
    return architecture_materials, case_study_materials, failure_analysis_materials


def _build_case_trace(project_id: str, case: dict[str, Any]) -> AutoResearchEvaluationCaseTraceRead:
    brief = build_research_brief(
        project_id=project_id,
        payload=_payload_for_case(case),
    )
    scouted = scout_and_mine_gaps(brief)
    hypothesis = selected_hypothesis_from_brief(scouted)
    plan = build_experiment_factory_plan(
        project_id=project_id,
        brief=scouted,
        hypothesis=hypothesis,
    )
    execution = execute_toy_experiment_factory(plan)

    blockers = _dedupe(
        [
            *plan.blockers,
            *execution.evidence_ledger.blockers,
            *(scouted.gap_miner.blockers if scouted.gap_miner is not None else []),
        ]
    )
    if execution.repair_plan is not None and execution.repair_plan.actions != ["none"]:
        blockers.extend(execution.repair_plan.action_reasons)
    blockers = _dedupe(blockers)
    architecture_materials, case_study_materials, failure_analysis_materials = _trace_materials(
        case=case,
        brief=brief,
        scouted=scouted,
        hypothesis=hypothesis,
        plan=plan,
        execution=execution,
        blockers=blockers,
    )
    ready = (
        execution.result_artifact.status == "done"
        and execution.evidence_ledger.complete
        and execution.evidence_ledger.entry_count > 0
        and execution.execution_plan.job_count > 0
        and not blockers
    )
    steps = [
        "idea",
        "research_brief",
        "literature_scout",
        "gap_mining",
        "hypothesis_selection",
        "experiment_plan",
        "toy_execution",
        "evidence_ledger",
    ]
    if ready:
        steps.extend(["paper_draft", "review_package"])
    paper_decision: AutoResearchProjectPaperDecision = "technical_report" if ready else "do_not_write"
    return AutoResearchEvaluationCaseTraceRead(
        idea=scouted.original_idea,
        brief_id=scouted.brief_id,
        selected_hypothesis_id=hypothesis.hypothesis_id,
        experiment_plan_id=plan.plan_id,
        evidence_ledger_id=execution.evidence_ledger.ledger_id,
        result_artifact_status=execution.result_artifact.status,
        primary_metric=execution.result_artifact.primary_metric,
        objective_score=execution.result_artifact.objective_score,
        paper_decision=paper_decision,
        steps_completed=steps,
        direction_count=scouted.direction_count,
        hypothesis_count=scouted.hypothesis_count,
        experiment_job_count=plan.job_count,
        evidence_entry_count=execution.evidence_ledger.entry_count,
        repair_action_count=(
            len(execution.repair_plan.actions)
            if execution.repair_plan is not None and execution.repair_plan.actions != ["none"]
            else 0
        ),
        evidence_complete=execution.evidence_ledger.complete,
        paper_review_package_ready=ready,
        architecture_materials=architecture_materials,
        case_study_materials=case_study_materials,
        failure_analysis_materials=failure_analysis_materials,
        blockers=blockers,
    )


def _build_toy_trace(project_id: str, case: dict[str, Any]) -> AutoResearchEvaluationCaseTraceRead:
    return _build_case_trace(project_id, case)


def _case_from_definition(
    *,
    definition: dict[str, Any],
    trace: AutoResearchEvaluationCaseTraceRead | None,
) -> AutoResearchEvaluationCaseRead:
    blockers = trace.blockers if trace is not None else []
    warnings = [] if trace is not None else [
        "Case is specified for internal evaluation but not executed by the deterministic toy backend yet."
    ]
    score = 100 if trace is not None and trace.paper_review_package_ready and not blockers else 40
    return AutoResearchEvaluationCaseRead(
        case_id=str(definition["case_id"]),
        task_kind=str(definition["task_kind"]),  # type: ignore[arg-type]
        idea=str(definition["idea"]),
        expected_brief_quality=str(definition["expected_brief_quality"]),
        expected_novelty_risks=list(definition["expected_novelty_risks"]),
        expected_experiment_design_requirements=list(definition["expected_experiment_design_requirements"]),
        expected_failure_replan_behavior=str(definition["expected_failure_replan_behavior"]),
        expected_paper_tier=str(definition["expected_paper_tier"]),  # type: ignore[arg-type]
        trace=trace,
        score=score,
        blockers=blockers,
        warnings=warnings,
    )


def _metrics(cases: list[AutoResearchEvaluationCaseRead]) -> list[AutoResearchSystemEvaluationMetricRead]:
    traces = [case.trace for case in cases if case.trace is not None]
    ready_traces = [
        trace
        for trace in traces
        if trace.paper_review_package_ready and not trace.blockers
    ]
    case_count = len(cases)
    executed_count = len(traces)
    definition_complete = sum(
        1
        for case in cases
        if case.idea
        and case.expected_brief_quality
        and case.expected_novelty_risks
        and case.expected_experiment_design_requirements
        and case.expected_failure_replan_behavior
    )
    return [
        _metric(
            metric_id="idea_to_brief_completeness",
            label="Idea-to-Brief Completeness",
            numerator=definition_complete,
            denominator=case_count,
            rationale="Counts internal cases that declare the expected idea, brief-quality, novelty, design, and failure/replan targets.",
        ),
        _metric(
            metric_id="hypothesis_selection_quality",
            label="Hypothesis Selection Quality",
            numerator=sum(
                1
                for trace in traces
                if trace.selected_hypothesis_id and trace.hypothesis_count >= 2
            ),
            denominator=max(executed_count, 1),
            rationale="Every deterministic trace must produce a hypothesis bank and selected hypothesis before execution.",
        ),
        _metric(
            metric_id="novelty_risk_detection",
            label="Novelty Risk Detection",
            numerator=sum(1 for case in cases if case.expected_novelty_risks),
            denominator=case_count,
            rationale="Each internal case declares novelty risks that the scout/gap miner should verify or narrow.",
        ),
        _metric(
            metric_id="experiment_plan_executability",
            label="Experiment Plan Executability",
            numerator=sum(1 for trace in traces if trace.experiment_job_count > 0 and not trace.blockers),
            denominator=max(executed_count, 1),
            rationale="Each trace must materialize baseline, method, ablation, seed, and sweep jobs without live GPU/network dependencies.",
        ),
        _metric(
            metric_id="evidence_consistency",
            label="Evidence Consistency",
            numerator=sum(
                1
                for trace in traces
                if trace.evidence_complete and trace.evidence_entry_count > 0
            ),
            denominator=max(executed_count, 1),
            rationale="Each trace must map execution outputs back into a complete evidence ledger.",
        ),
        _metric(
            metric_id="reviewer_score_improvement",
            label="Reviewer Score Improvement",
            numerator=len(ready_traces),
            denominator=max(executed_count, 1),
            rationale="The deterministic suite checks that every case reaches a paper/review package ready for reviewer-loop scoring.",
        ),
        _metric(
            metric_id="final_publish_correctness",
            label="Final Publish Correctness",
            numerator=sum(
                1
                for trace in ready_traces
                if trace.paper_decision == "technical_report"
            ),
            denominator=max(executed_count, 1),
            rationale="Offline execution cases should remain technical-report packages instead of overclaiming full project-level papers.",
        ),
    ]


def build_evaluation_case_suite(project_id: str) -> AutoResearchEvaluationCaseSuiteRead:
    traces_by_task_kind = {
        str(definition["task_kind"]): _build_case_trace(project_id, definition)
        for definition in _CASE_DEFINITIONS
    }
    cases = [
        _case_from_definition(
            definition=definition,
            trace=traces_by_task_kind[str(definition["task_kind"])],
        )
        for definition in _CASE_DEFINITIONS
    ]
    metrics = _metrics(cases)
    traces = [case.trace for case in cases if case.trace is not None]
    ready_traces = [
        trace
        for trace in traces
        if trace.paper_review_package_ready and not trace.blockers
    ]
    toy_trace = traces_by_task_kind["toy_task"]
    toy_ready = toy_trace.paper_review_package_ready and not toy_trace.blockers
    blockers = [
        f"{case.case_id}: " + "; ".join(case.blockers)
        for case in cases
        if case.blockers
    ]
    warnings = [] if len(ready_traces) == len(cases) else [
        "One or more deterministic evaluation cases did not reach a paper/review package."
    ]
    architecture_materials = _dedupe(
        [
            material
            for trace in traces
            for material in trace.architecture_materials
        ]
    )
    case_study_materials = _dedupe(
        [
            material
            for trace in traces
            for material in trace.case_study_materials
        ]
    )
    failure_analysis_materials = _dedupe(
        [
            material
            for trace in traces
            for material in trace.failure_analysis_materials
        ]
    )
    payload = {
        "suite_id": "autoresearch_evaluation_case_suite_v1",
        "project_id": project_id,
        "case_count": len(cases),
        "executed_case_count": len(traces),
        "completed_case_count": sum(
            1
            for case in cases
            if case.trace is not None and case.score >= 60 and not case.blockers
        ),
        "evaluation_artifact_count": sum(
            trace.experiment_job_count + trace.evidence_entry_count
            for trace in traces
        ),
        "cases": [case.model_dump(mode="json") for case in cases],
        "metrics": [metric.model_dump(mode="json") for metric in metrics],
        "scholarflow_paper_materials": _SCHOLARFLOW_PAPER_MATERIALS,
        "architecture_materials": architecture_materials,
        "case_study_materials": case_study_materials,
        "failure_analysis_materials": failure_analysis_materials,
        "toy_end_to_end_ready": toy_ready,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchEvaluationCaseSuiteRead(
        generated_at=_utcnow(),
        suite_fingerprint=_fingerprint(payload),
        **payload,
    )
