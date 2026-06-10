from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from schemas.autoresearch import (
    AutoResearchEvaluationCaseRead,
    AutoResearchEvaluationCaseSuiteRead,
    AutoResearchEvaluationCaseTraceRead,
    AutoResearchIdeaRequest,
    AutoResearchIdeaResourceBudget,
    AutoResearchProjectPaperDecision,
    AutoResearchRunRead,
    AutoResearchSystemEvaluationMetricRead,
    BenchmarkSource,
)
from services.autoresearch.benchmarks import ResolvedBenchmark, build_experiment_spec, builtin_benchmark
from services.autoresearch.experiment_factory import (
    build_experiment_factory_plan,
    execute_cached_claim_evidence_experiment_factory,
    execute_toy_experiment_factory,
)
from services.autoresearch.experiment_execution import (
    build_experiment_execution_plan,
    execute_experiment_execution_plan,
)
from services.autoresearch.idea_brief import build_research_brief, selected_hypothesis_from_brief
from services.autoresearch.literature_scout import (
    literature_insights_from_scout,
    scout_and_mine_gaps,
)
from services.autoresearch.project_paper_orchestrator import (
    PROJECT_SUBMISSION_PACKAGE_ROLES,
    build_project_paper_orchestration,
)
from services.autoresearch.repository import (
    save_literature_scout_cache,
    save_research_brief,
    save_run,
)


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
        "case_id": "eval_case_claim_evidence_vertical_task",
        "task_kind": "claim_evidence_vertical_task",
        "idea": (
            "Use claim-evidence ledgers to guide retrieval and verification in autonomous "
            "scientific writing, reducing unsupported claims without training a new large model."
        ),
        "domain": "claim-evidence retrieval for scientific writing",
        "budget_label": "standard",
        "max_rounds": 3,
        "candidate_execution_limit": 3,
        "target_tier": "workshop_candidate",
        "task_family_hint": "ir_reranking",
        "expected_brief_quality": (
            "Brief should bind generated manuscript claims to evidence retrieval, support "
            "verification, abstention, and claim-repair obligations rather than generic RAG quality."
        ),
        "expected_novelty_risks": [
            "Scientific claim verification is a known task; novelty depends on ledger-constrained repair.",
            "Citation-grounded writing overlaps RAG unless claim downgrading and reviewer-loop routing are evaluated.",
        ],
        "expected_experiment_design_requirements": [
            "Run BM25/lexical and ledger-aware reranking baselines on a claim-evidence benchmark.",
            "Report MRR, Recall@1, evidence support coverage, unsupported-claim detection, and abstention behavior.",
            "Persist retrieved evidence into the claim-evidence ledger and trigger repair when support is missing.",
        ],
        "expected_failure_replan_behavior": (
            "If retrieved evidence is missing or contradicts a generated claim, demote the claim, "
            "attach an abstention rationale, or queue a bounded retrieval/experiment repair."
        ),
        "expected_paper_tier": "workshop_candidate",
    },
    {
        "case_id": "claim_evidence_generalized_idea",
        "task_kind": "claim_evidence_vertical_task",
        "idea": (
            "Evaluate whether claim-evidence ledgers can route scientific writing claims "
            "through retrieval, verification, abstention, and repair without inflating "
            "unsupported manuscript claims."
        ),
        "domain": "claim_evidence_retrieval",
        "budget_label": "standard",
        "max_rounds": 3,
        "candidate_execution_limit": 3,
        "target_tier": "workshop_candidate",
        "task_family_hint": "ir_reranking",
        "expected_brief_quality": (
            "Brief should select a claim-evidence retrieval direction that remains compatible "
            "with the repository-local SciFact frozen benchmark path and reviewer repair loop."
        ),
        "expected_novelty_risks": [
            "Scientific claim verification and retrieval have existing baselines.",
            "A ledger interface is not a paper claim unless linked to evidence retrieval, abstention, and repair outcomes.",
        ],
        "expected_experiment_design_requirements": [
            "Resolve the SciFact frozen snapshot metadata and preserve source lineage.",
            "Execute or replay claim retrieval/verification metrics with evidence-ledger entries.",
            "Keep source-independence and negative-evidence blockers visible in package readiness.",
        ],
        "expected_failure_replan_behavior": (
            "Missing support evidence should route to claim downgrades, retrieval repair, or "
            "literature refresh rather than promoted manuscript claims."
        ),
        "expected_paper_tier": "workshop_candidate",
    },
    {
        "case_id": "rag_citation_faithfulness_review_case",
        "task_kind": "literature_heavy_task",
        "idea": (
            "Measure citation faithfulness in retrieval augmented generation by scoring whether "
            "answer claims are supported by retrieved citation passages and abstaining when "
            "support is missing."
        ),
        "domain": "citation faithfulness",
        "budget_label": "standard",
        "max_rounds": 3,
        "candidate_execution_limit": 2,
        "target_tier": "workshop_candidate",
        "task_family_hint": "ir_reranking",
        "seed_cached_literature": True,
        "build_project_package": True,
        "expected_brief_quality": (
            "Brief should bind RAG citation faithfulness to citation-support scoring, unsupported "
            "citation evidence, abstention, and review-only fixture limits."
        ),
        "expected_novelty_risks": [
            "Citation-faithfulness evaluation overlaps active RAG attribution work.",
            "Repository-local citation fixtures cannot establish final-publish novelty.",
        ],
        "expected_experiment_design_requirements": [
            "Resolve a citation-faithfulness benchmark fixture with explicit non-final blockers.",
            "Record citation support scores, unsupported citations, abstentions, and evidence ledger entries.",
            "Propagate fixture-only benchmark limitations into package readiness and claim ceiling.",
        ],
        "expected_failure_replan_behavior": (
            "Unsupported citations should remain negative evidence and route to citation-support "
            "repair or benchmark import follow-up before final-publish claims."
        ),
        "expected_paper_tier": "workshop_candidate",
    },
    {
        "case_id": "lightweight_ml_nlp_review_case",
        "task_kind": "medium_benchmark_task",
        "idea": (
            "Compare deterministic local text classifiers for lightweight ML/NLP benchmarking "
            "with accuracy, macro F1, baseline comparison, and explicit fixture-only claim limits."
        ),
        "domain": "lightweight ml nlp benchmark",
        "budget_label": "standard",
        "max_rounds": 3,
        "candidate_execution_limit": 2,
        "target_tier": "technical_report",
        "task_family_hint": "text_classification",
        "seed_cached_literature": True,
        "build_project_package": True,
        "expected_brief_quality": (
            "Brief should bind the lightweight ML/NLP idea to deterministic local text classification, "
            "macro F1, baseline comparison, and publication-grade provenance blockers."
        ),
        "expected_novelty_risks": [
            "Small text-classification benchmarks are unlikely to be novel without real benchmark provenance.",
            "Fixture-only local metrics can validate engineering but cannot support publication-grade benchmark claims.",
        ],
        "expected_experiment_design_requirements": [
            "Resolve the local fixture benchmark as review-only evidence.",
            "Record accuracy, macro F1, predictions, baseline comparison, and evidence ledger entries.",
            "Propagate missing real benchmark provenance to package/readiness blockers.",
        ],
        "expected_failure_replan_behavior": (
            "Missing real benchmark scale or statistics should remain required follow-up rather "
            "than being repaired by synthetic benchmark claims."
        ),
        "expected_paper_tier": "technical_report",
    },
    {
        "case_id": "unsupported_domain_case",
        "task_kind": "failed_hypothesis_task",
        "idea": "Design a wet-lab CRISPR assay for cancer organoids requiring live lab equipment",
        "domain": "wet lab biology",
        "budget_label": "toy",
        "max_rounds": 2,
        "candidate_execution_limit": 1,
        "target_tier": "technical_report",
        "task_family_hint": "text_classification",
        "expected_blocked": True,
        "expected_brief_quality": (
            "Brief should produce an auditable unsupported-domain blocker with no selected "
            "hypothesis, no experiment plan, and no toy outputs."
        ),
        "expected_novelty_risks": [
            "Unsupported wet-lab work has no deterministic ScholarFlow domain template.",
            "Any toy/software output would be unrelated evidence and must be blocked.",
        ],
        "expected_experiment_design_requirements": [
            "Do not generate factory jobs for unsupported domains.",
            "Return structured benchmark resolver and experiment protocol blockers.",
            "Propagate blockers to project readiness and evaluation trace.",
        ],
        "expected_failure_replan_behavior": (
            "The run should stop at domain routing and require a new supported-domain template "
            "instead of attempting fake execution."
        ),
        "expected_paper_tier": "technical_report",
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
    "Claim-evidence vertical package: IR metrics, per-query diagnostics, review-loop repair actions, reproducibility assets, and scoped limitations.",
    "Failure analysis: repair actions distinguish missing baselines, missing ablations, weak statistics, and failed hypotheses.",
]

_OFFLINE_PUBLICATION_CASE_REQUIRED_PACKAGE_ROLES = set(PROJECT_SUBMISSION_PACKAGE_ROLES) - {
    "project_submission_manifest",
}


def _read_json_file(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.is_file():
        return {}
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _project_source_trace_fields(project_paper: Any) -> dict[str, Any]:
    sources_manifest = getattr(project_paper, "project_paper_sources_manifest", None)
    manifest_path = getattr(project_paper, "project_paper_sources_manifest_path", None)
    manifest_payload = (
        sources_manifest.model_dump(mode="json")
        if hasattr(sources_manifest, "model_dump")
        else sources_manifest
        if isinstance(sources_manifest, dict)
        else _read_json_file(manifest_path)
    )
    if not isinstance(manifest_payload, dict):
        manifest_payload = {}
    context_path = getattr(project_paper, "project_manuscript_context_path", None)
    context_payload = _read_json_file(context_path)
    context_fingerprint = getattr(project_paper, "project_manuscript_context_fingerprint", None)
    return {
        "project_paper_sources_manifest_path": manifest_path,
        "project_paper_sources_reconstructable": bool(manifest_payload.get("reconstructable")),
        "project_paper_source_package_ready": bool(manifest_payload.get("source_package_ready")),
        "project_paper_missing_source_files": [
            str(item)
            for item in manifest_payload.get("missing_files", [])
            if isinstance(item, str)
        ],
        "project_paper_missing_external_artifacts": [
            str(item)
            for item in manifest_payload.get("missing_external_artifacts", [])
            if isinstance(item, str)
        ],
        "project_manuscript_context_path": context_path,
        "project_manuscript_context_complete": bool(
            getattr(project_paper, "project_manuscript_context_complete", False)
            or context_payload.get("context_id") == "project_manuscript_context_v2"
        ),
        "project_manuscript_context_fingerprint": (
            str(context_fingerprint)
            if context_fingerprint is not None
            else (
                str(context_payload.get("context_fingerprint"))
                if context_payload.get("context_fingerprint") is not None
                else None
            )
        ),
    }


def _submission_trace_fields(project_paper: Any) -> dict[str, Any]:
    manifest = getattr(project_paper, "project_submission_manifest", None)
    if not isinstance(manifest, dict):
        manifest = _read_json_file(getattr(project_paper, "project_submission_manifest_path", None))
    archive_manifest = getattr(project_paper, "project_submission_archive_manifest", None)
    if hasattr(archive_manifest, "model_dump"):
        archive_manifest = archive_manifest.model_dump(mode="json")
    if not isinstance(archive_manifest, dict):
        archive_manifest = _read_json_file(
            getattr(project_paper, "project_submission_archive_manifest_path", None)
        )
    reproducibility_checklist = getattr(
        project_paper,
        "project_reproducibility_checklist",
        None,
    )
    if hasattr(reproducibility_checklist, "model_dump"):
        reproducibility_checklist = reproducibility_checklist.model_dump(mode="json")
    if not isinstance(reproducibility_checklist, dict):
        reproducibility_checklist = _read_json_file(
            getattr(project_paper, "project_reproducibility_checklist_json_path", None)
        )
    artifact_integrity_audit = getattr(
        project_paper,
        "project_artifact_integrity_audit",
        None,
    )
    if hasattr(artifact_integrity_audit, "model_dump"):
        artifact_integrity_audit = artifact_integrity_audit.model_dump(mode="json")
    if not isinstance(artifact_integrity_audit, dict):
        artifact_integrity_audit = _read_json_file(
            getattr(project_paper, "project_artifact_integrity_audit_path", None)
        )
    final_publish_decision = getattr(
        project_paper,
        "project_final_publish_decision",
        None,
    )
    if hasattr(final_publish_decision, "model_dump"):
        final_publish_decision = final_publish_decision.model_dump(mode="json")
    if not isinstance(final_publish_decision, dict):
        final_publish_decision = _read_json_file(
            getattr(project_paper, "project_final_publish_decision_path", None)
        )
    failed_check_ids = [
        str(item.get("check_id"))
        for item in final_publish_decision.get("failed_checks", [])
        if isinstance(item, dict) and item.get("check_id")
    ]
    assets = [
        item
        for item in manifest.get("generated_assets", [])
        if isinstance(item, dict)
    ]
    roles = sorted(
        {
            str(item.get("role"))
            for item in assets
            if item.get("role")
        }
    )
    explicit_missing_roles = {
        str(item.get("role"))
        for item in assets
        if item.get("role")
        and (
            item.get("missing_status") != "present"
            or item.get("exists") is False
        )
    }
    missing_roles = sorted(
        (_OFFLINE_PUBLICATION_CASE_REQUIRED_PACKAGE_ROLES - set(roles))
        | explicit_missing_roles
    )
    review_findings = getattr(project_paper, "project_review_findings", None)
    if not isinstance(review_findings, dict):
        review_findings = _read_json_file(getattr(project_paper, "project_review_findings_path", None))
    finding_records = review_findings.get("findings", [])
    if isinstance(finding_records, list):
        project_review_finding_count = len(
            [item for item in finding_records if isinstance(item, dict)]
        )
        mapped_action_ids = {
            str(item.get("mapped_revision_action_id"))
            for item in finding_records
            if isinstance(item, dict) and item.get("mapped_revision_action_id")
        }
    else:
        project_review_finding_count = int(review_findings.get("finding_count") or 0)
        mapped_action_ids = set()
    action_ids = {
        action.action_id
        for action in getattr(project_paper, "project_paper_revision_actions", [])
        if getattr(action, "action_id", None)
    }
    revision_action_plan = getattr(project_paper, "project_revision_action_plan", None)
    if hasattr(revision_action_plan, "model_dump"):
        revision_action_plan = revision_action_plan.model_dump(mode="json")
    if not isinstance(revision_action_plan, dict):
        revision_action_plan = _read_json_file(getattr(project_paper, "project_revision_action_plan_path", None))
    revision_round = getattr(project_paper, "project_revision_round", None)
    if hasattr(revision_round, "model_dump"):
        revision_round = revision_round.model_dump(mode="json")
    if not isinstance(revision_round, dict):
        revision_round = _read_json_file(getattr(project_paper, "project_revision_round_path", None))
    response_dossier = getattr(project_paper, "project_revision_response_dossier", None)
    if hasattr(response_dossier, "model_dump"):
        response_dossier = response_dossier.model_dump(mode="json")
    if not isinstance(response_dossier, dict):
        response_dossier = _read_json_file(
            getattr(project_paper, "project_revision_response_dossier_path", None)
        )
    plan_actions = [
        item for item in revision_action_plan.get("actions", []) if isinstance(item, dict)
    ]
    paper_only_action_ids = [
        str(item.get("action_id"))
        for item in plan_actions
        if item.get("scope") in {"manuscript", "claim_evidence_index"}
    ]
    blocked_evidence_action_ids = [
        str(item.get("action_id"))
        for item in plan_actions
        if item.get("action_kind")
        in {
            "experiment_repair_request",
            "literature_followup_request",
            "benchmark_provenance_followup_request",
        }
        and item.get("status") != "executed"
    ]
    return {
        "project_review_finding_count": project_review_finding_count,
        "project_review_findings_mapped_to_actions": bool(action_ids)
        and mapped_action_ids == action_ids,
        "project_revision_action_plan_path": getattr(project_paper, "project_revision_action_plan_path", None),
        "project_revision_response_dossier_path": getattr(
            project_paper,
            "project_revision_response_dossier_path",
            None,
        ),
        "project_revision_round_path": getattr(project_paper, "project_revision_round_path", None),
        "project_revision_selected_action_ids": [
            str(item.get("action_id")) for item in plan_actions if item.get("action_id")
        ],
        "project_revision_paper_only_action_ids": paper_only_action_ids,
        "project_revision_blocked_evidence_action_ids": blocked_evidence_action_ids,
        "project_revision_response_item_count": int(response_dossier.get("item_count") or 0),
        "project_revision_rereview_resolved_count": int(revision_round.get("resolved_count") or 0),
        "project_revision_rereview_partially_resolved_count": int(
            revision_round.get("partially_resolved_count") or 0
        ),
        "project_revision_rereview_unresolved_count": int(revision_round.get("unresolved_count") or 0),
        "project_revision_rereview_regressed_count": int(revision_round.get("regressed_count") or 0),
        "project_revision_terminal_status": str(
            revision_round.get("terminal_status") or "needs_revision"
        ),
        "project_revision_readiness_impact": revision_round.get("readiness_impact"),
        "project_submission_bundle_kind": (
            str(manifest.get("bundle_kind"))
            if manifest.get("bundle_kind") is not None
            else None
        ),
        "project_submission_asset_roles": roles,
        "project_submission_missing_asset_roles": missing_roles,
        "project_submission_required_roles_present": bool(roles) and not missing_roles,
        "project_submission_archive_manifest_path": getattr(
            project_paper,
            "project_submission_archive_manifest_path",
            None,
        ),
        "project_submission_archive_path": getattr(
            project_paper,
            "project_submission_archive_path",
            None,
        ),
        "project_reproducibility_checklist_json_path": getattr(
            project_paper,
            "project_reproducibility_checklist_json_path",
            None,
        ),
        "project_artifact_integrity_audit_path": getattr(
            project_paper,
            "project_artifact_integrity_audit_path",
            None,
        ),
        "project_final_publish_decision_path": getattr(
            project_paper,
            "project_final_publish_decision_path",
            None,
        ),
        "project_submission_archive_complete": bool(archive_manifest.get("complete")),
        "project_submission_archive_current": bool(archive_manifest.get("current")),
        "project_submission_archive_ready_for_final_download": bool(
            archive_manifest.get("ready_for_final_download")
        ),
        "project_submission_archive_entry_count": int(
            archive_manifest.get("entry_count") or 0
        ),
        "project_submission_archive_missing_required_entry_count": int(
            archive_manifest.get("missing_required_entry_count") or 0
        ),
        "project_submission_archive_hash_mismatch_entry_count": int(
            archive_manifest.get("hash_mismatch_entry_count") or 0
        ),
        "project_submission_archive_stale_entry_count": int(
            archive_manifest.get("stale_entry_count") or 0
        ),
        "project_reproducibility_checklist_complete": bool(
            reproducibility_checklist.get("complete")
        ),
        "project_reproducibility_checklist_missing_required_count": int(
            reproducibility_checklist.get("missing_required_count") or 0
        ),
        "project_reproducibility_checklist_partial_required_count": int(
            reproducibility_checklist.get("partial_required_count") or 0
        ),
        "project_artifact_integrity_audit_complete": bool(
            artifact_integrity_audit.get("complete")
        ),
        "project_artifact_integrity_unresolved_issue_count": int(
            artifact_integrity_audit.get("unresolved_issue_count") or 0
        ),
        "project_final_publish_policy_version": (
            str(final_publish_decision.get("policy_version"))
            if final_publish_decision.get("policy_version") is not None
            else None
        ),
        "project_final_publish_failed_check_ids": failed_check_ids,
    }


def _artifact_negative_evidence_count(artifact: Any) -> int:
    outputs = getattr(artifact, "outputs", {}) or {}
    objective_failures = outputs.get("objective_failure_cases", [])
    diagnostics = outputs.get("objective_query_diagnostics", [])
    retrieval_ledger = outputs.get("retrieval_evidence_ledger", [])
    count = len(getattr(artifact, "negative_results", []) or [])
    count += len(getattr(artifact, "failed_trials", []) or [])
    count += len(objective_failures) if isinstance(objective_failures, list) else 0
    if isinstance(diagnostics, list):
        count += sum(
            1
            for item in diagnostics
            if isinstance(item, dict)
            and (
                item.get("failure_modes")
                or item.get("claim_label") in {"refuted", "not_enough_info"}
                or item.get("retrieval_applicable") is False
            )
        )
    if isinstance(retrieval_ledger, list):
        count += sum(
            1
            for item in retrieval_ledger
            if isinstance(item, dict)
            and (
                item.get("failure_modes")
                or item.get("support_status") in {"partial", "missing"}
            )
        )
    return count


def _claim_ceiling_from_artifacts(
    *,
    final_publish_ready: bool,
    readiness_report: dict[str, Any],
    compiler_evidence: dict[str, Any],
    negative_evidence_count: int,
) -> str:
    if final_publish_ready:
        return "final_publish_claim"
    benchmark_ready = bool(
        readiness_report.get("evidence_profile", {}).get("benchmark_publication_ready")
    )
    claim_support = compiler_evidence.get("claim_support_coverage", {})
    claim_support_complete = bool(claim_support.get("complete"))
    if benchmark_ready and claim_support_complete and negative_evidence_count == 0:
        return "conference_candidate_claim"
    if compiler_evidence.get("section_coverage", {}).get("complete"):
        return "workshop_case_study_claim"
    if readiness_report.get("blockers"):
        return "technical_report_only"
    return "blocked_claim"

def _cached_scifact_record(index: int, *, split: str) -> dict[str, Any]:
    label_cycle = ("supported", "refuted", "not_enough_info")
    label = label_cycle[index % len(label_cycle)]
    claim_id = f"{split}_{label}_{index:02d}"
    topic = [
        "claim evidence ledgers",
        "reviewer repair routing",
        "citation grounded retrieval",
        "autonomous manuscript checking",
        "evidence abstention",
    ][index % 5]
    if label == "supported":
        query = f"{topic} improve supported evidence retrieval for scientific writing agents."
        relevant_id = f"doc_support_{index:02d}"
        candidates = [
            {
                "id": relevant_id,
                "text": (
                    f"Supported Evidence {index}. {topic} improve supported evidence retrieval "
                    "for scientific writing agents with explicit claim-evidence links."
                ),
            },
            {
                "id": f"doc_neutral_{index:02d}",
                "text": f"Neutral Background {index}. Scientific writing systems discuss workflow UX without evidence routing.",
            },
            {
                "id": f"doc_refute_distractor_{index:02d}",
                "text": f"Refutation Distractor {index}. Unsupported automation can increase unverified claims.",
            },
        ]
        relevant_ids = [relevant_id]
    elif label == "refuted":
        query = f"{topic} eliminate unsupported claims in all autonomous writing settings."
        relevant_id = f"doc_refute_{index:02d}"
        candidates = [
            {
                "id": relevant_id,
                "text": (
                    f"Refuting Evidence {index}. {topic} do not eliminate unsupported claims "
                    "in all autonomous writing settings and require reviewer repair."
                ),
            },
            {
                "id": f"doc_support_distractor_{index:02d}",
                "text": f"Support Distractor {index}. Evidence ledgers improve retrieval on scoped benchmark claims.",
            },
            {
                "id": f"doc_neutral_{index:02d}",
                "text": f"Neutral Background {index}. Citation graph tools are adjacent but do not test this universal claim.",
            },
        ]
        relevant_ids = [relevant_id]
    else:
        query = f"{topic} prove fully autonomous publication readiness without experiments."
        candidates = [
            {
                "id": f"doc_nei_{index:02d}",
                "text": (
                    f"Insufficient Evidence {index}. Prior work gives general background on editorial workflows, "
                    "dataset curation, and reproducibility checklists."
                ),
            },
            {
                "id": f"doc_support_distractor_{index:02d}",
                "text": f"Support Distractor {index}. Scoped retrieval evidence can support bounded manuscript claims.",
            },
            {
                "id": f"doc_refute_distractor_{index:02d}",
                "text": f"Refutation Distractor {index}. Some unsupported claims are caught by reviewer simulation.",
            },
        ]
        relevant_ids = []
    return {
        "claim_id": claim_id,
        "query": query,
        "candidates": candidates,
        "relevant_ids": relevant_ids,
        "claim_label": label,
        "unsupported_claim": label != "supported",
    }


SCIFACT_FROZEN_SNAPSHOT_MIN_EXAMPLES = 100
SCIFACT_FROZEN_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "frozen_benchmarks"
    / "scifact_claim_verification_frozen_snapshot_v1.json"
)
SCIFACT_RETRIEVAL_FROZEN_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "frozen_benchmarks"
    / "scifact_claim_retrieval_frozen_snapshot_v1.json"
)


_CACHED_SCIFACT_VERTICAL_PAYLOAD: dict[str, Any] = {
    "name": "Cached SciFact-style Claim Evidence Evaluation",
    "description": (
        "Offline cached support/refute/not-enough-info benchmark for claim-evidence vertical evaluation. "
        "This deterministic cache meets the minimum example-count gate for package readiness checks, "
        "but remains a bounded case-study benchmark rather than broad publication evidence."
    ),
    "source_url": "file://scholarflow-fixtures/cached-scifact-claim-evidence-eval.json",
    "source_dataset_id": "scholarflow:cached_scifact_claim_evidence_eval",
    "source_revision": "v1.1.0",
    "supports_claim_verification": True,
    "train": [_cached_scifact_record(index, split="train") for index in range(8)],
    "test": [_cached_scifact_record(index, split="test") for index in range(8, 24)],
    "verification_label_space": ["not_enough_info", "refuted", "supported"],
}


_CACHED_SCIFACT_VERTICAL_SOURCE = BenchmarkSource(
    kind="scifact_json",
    name="Cached SciFact-style Claim Evidence Evaluation",
    url="file://scholarflow-fixtures/cached-scifact-claim-evidence-eval.json",
    dataset_id="scholarflow:cached_scifact_claim_evidence_eval",
    revision="v1.1.0",
    license="cached-fixture-for-deterministic-evaluation",
    task_family_hint="ir_reranking",
)


def _cached_beir_record(index: int, *, split: str) -> dict[str, Any]:
    claim_id = f"{split}_beir_{index:02d}"
    topic = [
        "ledger guided retrieval",
        "claim evidence ranking",
        "autonomous manuscript support",
        "reviewer repair evidence",
    ][index % 4]
    relevant_id = f"beir_doc_relevant_{index:02d}"
    return {
        "claim_id": claim_id,
        "query": f"{topic} retrieve evidence passages for scientific writing agents.",
        "candidates": [
            {
                "id": relevant_id,
                "text": (
                    f"Relevant BEIR-style Evidence {index}. {topic} retrieves evidence passages "
                    "for scientific writing agents and preserves audit trails for manuscript claims."
                ),
            },
            {
                "id": f"beir_doc_workflow_{index:02d}",
                "text": (
                    f"Workflow Distractor {index}. Editorial workflow tools track tasks but do not "
                    "evaluate evidence retrieval quality."
                ),
            },
            {
                "id": f"beir_doc_citation_{index:02d}",
                "text": (
                    f"Citation Distractor {index}. Citation formatting checks improve bibliographies "
                    "without ranking claim support passages."
                ),
            },
        ],
        "relevant_ids": [relevant_id],
    }


_CACHED_BEIR_VERTICAL_PAYLOAD: dict[str, Any] = {
    "name": "Cached BEIR-style Claim Evidence Retrieval Evaluation",
    "description": (
        "Offline cached BEIR-style retrieval benchmark for the claim-evidence vertical. "
        "It exercises the retrieval-only branch of the benchmark ladder and remains a deterministic "
        "fixture, not publication-grade evidence."
    ),
    "source_url": "file://scholarflow-fixtures/cached-beir-claim-evidence-eval.json",
    "source_dataset_id": "scholarflow:cached_beir_claim_evidence_eval",
    "source_revision": "v1.0.0",
    "supports_claim_verification": False,
    "train": [_cached_beir_record(index, split="train") for index in range(8)],
    "test": [_cached_beir_record(index, split="test") for index in range(8, 24)],
}


SCIFACT_FROZEN_SNAPSHOT_SOURCE_URL = (
    "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
)
SCIFACT_FROZEN_SNAPSHOT_SOURCE_SHA256 = (
    "11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be"
)
SCIFACT_FROZEN_SNAPSHOT_REVISION = (
    "release-latest-data-tarball-sha256-"
    "11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be"
)
SCIFACT_FROZEN_SNAPSHOT_LICENSE = (
    "claims/evidence annotations: CC BY 4.0; corpus abstracts: S2ORC/ODC-By 1.0"
)


def _load_imported_scifact_vertical_payload() -> dict[str, Any]:
    return json.loads(SCIFACT_FROZEN_SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _load_imported_scifact_retrieval_vertical_payload() -> dict[str, Any]:
    return json.loads(SCIFACT_RETRIEVAL_FROZEN_SNAPSHOT_PATH.read_text(encoding="utf-8"))


_IMPORTED_SCIFACT_VERTICAL_SOURCE = BenchmarkSource(
    kind="scifact_json",
    name="SciFact Claim Verification Frozen Snapshot",
    url=SCIFACT_FROZEN_SNAPSHOT_SOURCE_URL,
    file_path=str(SCIFACT_FROZEN_SNAPSHOT_PATH),
    dataset_id="allenai/scifact",
    revision=SCIFACT_FROZEN_SNAPSHOT_REVISION,
    license=SCIFACT_FROZEN_SNAPSHOT_LICENSE,
    task_family_hint="ir_reranking",
)


_IMPORTED_SCIFACT_RETRIEVAL_VERTICAL_SOURCE = BenchmarkSource(
    kind="beir_json",
    name="SciFact Claim Retrieval Frozen Snapshot",
    url=SCIFACT_FROZEN_SNAPSHOT_SOURCE_URL,
    file_path=str(SCIFACT_RETRIEVAL_FROZEN_SNAPSHOT_PATH),
    dataset_id="allenai/scifact-retrieval-view",
    revision=SCIFACT_FROZEN_SNAPSHOT_REVISION,
    license=SCIFACT_FROZEN_SNAPSHOT_LICENSE,
    task_family_hint="ir_reranking",
)


_CACHED_BEIR_VERTICAL_SOURCE = BenchmarkSource(
    kind="beir_json",
    name="Cached BEIR-style Claim Evidence Retrieval Evaluation",
    url="file://scholarflow-fixtures/cached-beir-claim-evidence-eval.json",
    dataset_id="scholarflow:cached_beir_claim_evidence_eval",
    revision="v1.0.0",
    license="cached-fixture-for-deterministic-evaluation",
    task_family_hint="ir_reranking",
)


_CACHED_REAL_LITERATURE_PAYLOAD: dict[str, Any] = {
    "data": [
        {
            "paperId": "semantic-scholar-ledger-claim-evidence",
            "title": "Evidence Ledger Guided Claim Verification for Scientific Writing Agents",
            "abstract": (
                "Claim-evidence ledgers can connect generated scientific writing claims to retrieved support, "
                "abstention decisions, and reviewer-facing repair actions."
            ),
            "year": 2026,
            "venue": "Cached Semantic Scholar Fixture",
            "url": "https://example.test/evidence-ledger-claim-verification",
            "externalIds": {"DOI": "10.0000/scholarflow.cached.ledger", "ArXiv": "2601.00001"},
            "authors": [{"name": "Cached Literature Fixture"}],
            "fieldsOfStudy": ["Computer Science", "Information Retrieval"],
        }
    ]
}


_CACHED_REAL_ARXIV_PAYLOAD = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2601.00002</id>
    <title>Claim-Evidence Retrieval for Autonomous Scientific Manuscripts</title>
    <summary>Cached arXiv fixture describing claim-evidence retrieval benchmarks, ledger-guided reranking, MRR, recall, nDCG, and abstention analysis for scientific writing agents.</summary>
    <published>2026-01-03T00:00:00Z</published>
    <author><name>Cached ArXiv Fixture</name></author>
    <arxiv:doi>10.0000/scholarflow.cached.arxiv</arxiv:doi>
  </entry>
</feed>
"""


_CACHED_REAL_CROSSREF_PAYLOAD: dict[str, Any] = {
    "message": {
        "items": [
            {
                "DOI": "10.0000/scholarflow.cached.crossref",
                "title": ["Auditable Evidence Ledgers for Research Agent Paper Drafts"],
                "container-title": ["Cached Crossref Fixture"],
                "abstract": (
                    "<p>Cached Crossref fixture covering reproducibility checklists, reviewer repair "
                    "loops, unsupported-claim detection, and benchmark reporting for autonomous "
                    "research agents.</p>"
                ),
                "issued": {"date-parts": [[2026, 1, 4]]},
                "author": [{"given": "Cached", "family": "Crossref Fixture"}],
                "URL": "https://example.test/auditable-evidence-ledgers",
            }
        ]
    }
}


_CACHED_RAG_SEMANTIC_PAYLOAD: dict[str, Any] = {
    "data": [
        {
            "paperId": "semantic-scholar-rag-citation-faithfulness",
            "title": "Citation Faithfulness Evaluation for Retrieval Augmented Generation",
            "abstract": (
                "Retrieval augmented generation systems can be evaluated with attribution, citation "
                "support scoring, grounding metrics, unsupported citation detection, and abstention "
                "on knowledge intensive QA benchmarks."
            ),
            "year": 2026,
            "venue": "Cached Semantic Scholar Fixture",
            "url": "https://example.test/rag-citation-faithfulness",
            "externalIds": {"DOI": "10.0000/scholarflow.cached.rag", "ArXiv": "2602.00001"},
            "authors": [{"name": "Cached RAG Fixture"}],
            "fieldsOfStudy": ["Computer Science", "Natural Language Processing"],
        }
    ]
}


_CACHED_RAG_ARXIV_PAYLOAD = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2602.00002</id>
    <title>RAG Attribution and Citation Grounding Metrics for Knowledge Intensive QA</title>
    <summary>Cached arXiv fixture describing retrieval augmented generation attribution, citation faithfulness, grounding, citation support coverage, precision, recall, and abstention metrics for knowledge intensive QA.</summary>
    <published>2026-02-03T00:00:00Z</published>
    <author><name>Cached RAG ArXiv Fixture</name></author>
    <arxiv:doi>10.0000/scholarflow.cached.rag.arxiv</arxiv:doi>
  </entry>
</feed>
"""


_CACHED_RAG_CROSSREF_PAYLOAD: dict[str, Any] = {
    "message": {
        "items": [
            {
                "DOI": "10.0000/scholarflow.cached.rag.crossref",
                "title": ["Related Systems for RAG Citation Support and Attribution"],
                "container-title": ["Cached Crossref Fixture"],
                "abstract": (
                    "<p>Cached Crossref fixture covering RAG attribution, citation support "
                    "benchmarks, faithful grounding, unsupported citations, abstention, precision, "
                    "and recall for knowledge-intensive QA.</p>"
                ),
                "issued": {"date-parts": [[2026, 2, 4]]},
                "author": [{"given": "Cached", "family": "RAG Fixture"}],
                "URL": "https://example.test/rag-citation-support",
            }
        ]
    }
}


_CACHED_LIGHTWEIGHT_SEMANTIC_PAYLOAD: dict[str, Any] = {
    "data": [
        {
            "paperId": "semantic-scholar-lightweight-ml-nlp",
            "title": "Lightweight Text Classification Benchmarks with Local Baselines",
            "abstract": (
                "Lightweight NLP benchmark comparisons should report deterministic local baselines, "
                "text classification accuracy, macro F1, reproducibility limits, and fixture-only "
                "claim ceilings before publication-grade claims."
            ),
            "year": 2026,
            "venue": "Cached Semantic Scholar Fixture",
            "url": "https://example.test/lightweight-ml-nlp",
            "externalIds": {"DOI": "10.0000/scholarflow.cached.lightweight", "ArXiv": "2603.00001"},
            "authors": [{"name": "Cached Lightweight Fixture"}],
            "fieldsOfStudy": ["Computer Science", "Machine Learning"],
        }
    ]
}


_CACHED_LIGHTWEIGHT_ARXIV_PAYLOAD = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2603.00002</id>
    <title>Deterministic Local Text Classification Baselines for Lightweight NLP Benchmarks</title>
    <summary>Cached arXiv fixture describing lightweight benchmark reproducibility, text classification, local baseline comparison, accuracy, macro F1, and small benchmark limitations.</summary>
    <published>2026-03-03T00:00:00Z</published>
    <author><name>Cached Lightweight ArXiv Fixture</name></author>
    <arxiv:doi>10.0000/scholarflow.cached.lightweight.arxiv</arxiv:doi>
  </entry>
</feed>
"""


_CACHED_LIGHTWEIGHT_CROSSREF_PAYLOAD: dict[str, Any] = {
    "message": {
        "items": [
            {
                "DOI": "10.0000/scholarflow.cached.lightweight.crossref",
                "title": ["Reproducible Small Benchmark Reporting for Local NLP Classifiers"],
                "container-title": ["Cached Crossref Fixture"],
                "abstract": (
                    "<p>Cached Crossref fixture covering lightweight benchmark reporting, "
                    "machine learning reproducibility, text classification baselines, accuracy, "
                    "macro F1, and local deterministic metric limits.</p>"
                ),
                "issued": {"date-parts": [[2026, 3, 4]]},
                "author": [{"given": "Cached", "family": "Lightweight Fixture"}],
                "URL": "https://example.test/lightweight-text-classification",
            }
        ]
    }
}


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


def _literature_cache_queries(brief) -> list[str]:
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
            metric = selected.required_metrics[0] if selected.required_metrics else ""
            queries.append(f"{selected.research_question} {metric}")
    domain_strategy = getattr(brief, "domain_literature_strategy", None)
    if domain_strategy is not None:
        queries.extend(domain_strategy.query_strings)
    return _dedupe(queries)[: max(3, min(8, len(queries)))]


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


def _domain_cached_literature_payloads(brief) -> dict[str, Any]:
    domain_id = (
        brief.domain_decision.domain_id
        if brief.domain_decision is not None
        else "unsupported"
    )
    if domain_id == "rag_citation_faithfulness":
        return {
            "arxiv": _CACHED_RAG_ARXIV_PAYLOAD,
            "semantic_scholar": _CACHED_RAG_SEMANTIC_PAYLOAD,
            "crossref": _CACHED_RAG_CROSSREF_PAYLOAD,
        }
    if domain_id == "lightweight_ml_nlp_benchmark":
        return {
            "arxiv": _CACHED_LIGHTWEIGHT_ARXIV_PAYLOAD,
            "semantic_scholar": _CACHED_LIGHTWEIGHT_SEMANTIC_PAYLOAD,
            "crossref": _CACHED_LIGHTWEIGHT_CROSSREF_PAYLOAD,
        }
    return {
        "arxiv": _CACHED_REAL_ARXIV_PAYLOAD,
        "semantic_scholar": _CACHED_REAL_LITERATURE_PAYLOAD,
        "crossref": _CACHED_REAL_CROSSREF_PAYLOAD,
    }


def _seed_domain_cached_literature(brief) -> None:
    payloads = _domain_cached_literature_payloads(brief)
    for query in _literature_cache_queries(brief):
        for source, raw in payloads.items():
            save_literature_scout_cache(
                brief.project_id,
                source=source,
                query=query,
                limit=3,
                payload={
                    "fetched_at": _utcnow().isoformat(),
                    "raw": raw,
                },
            )


def _seed_claim_evidence_cached_literature(brief) -> None:
    _seed_domain_cached_literature(brief)


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
    if task_kind == "claim_evidence_vertical_task":
        case_study_materials.append(
            (
                f"{task_kind}: cached benchmark `{result.environment.get('benchmark_name') or 'claim-evidence fixture'}` "
                "reports IR metrics, per-query failure cases, claim-evidence index entries, "
                "repair actions, reproducibility assets, and fixture limitations."
            )
        )
        failure_analysis_materials.append(
            (
                f"{task_kind}: retrieval failures must route to claim downgrades or literature refreshes before "
                "paper claims are promoted."
            )
        )
    return architecture_materials, case_study_materials, failure_analysis_materials


def _blocked_domain_trace(
    *,
    project_id: str,
    case: dict[str, Any],
) -> AutoResearchEvaluationCaseTraceRead:
    brief = build_research_brief(
        project_id=project_id,
        payload=_payload_for_case(case),
    )
    scouted = scout_and_mine_gaps(
        brief,
        sources=[],
        cache_enabled=False,
        network_enabled=False,
    )
    save_research_brief(scouted)
    project_paper = build_project_paper_orchestration(project_id)
    factory_plan = build_experiment_factory_plan(
        project_id=project_id,
        brief=scouted,
    )
    experiment_execution_plan = build_experiment_execution_plan(
        factory_plan=factory_plan,
        brief=scouted,
    )
    experiment_execution_result = execute_experiment_execution_plan(
        experiment_execution_plan
    )
    literature_scout = scouted.literature_scout
    domain_benchmark_blockers = (
        scouted.domain_benchmark_resolver.blockers
        if scouted.domain_benchmark_resolver is not None
        else []
    )
    domain_protocol_blockers = (
        scouted.domain_experiment_protocol.blockers
        or scouted.domain_experiment_protocol.readiness_blockers
        if scouted.domain_experiment_protocol is not None
        else []
    )
    blockers = _dedupe(
        [
            *scouted.domain_blockers,
            *domain_benchmark_blockers,
            *domain_protocol_blockers,
            *project_paper.blockers,
        ]
    )
    task_kind = str(case["task_kind"])
    submission_fields = _submission_trace_fields(project_paper)
    source_trace_fields = _project_source_trace_fields(project_paper)
    return AutoResearchEvaluationCaseTraceRead(
        idea=scouted.original_idea,
        brief_id=scouted.brief_id,
        domain_decision=scouted.domain_decision,
        domain_template=scouted.domain_template,
        domain_blockers=scouted.domain_blockers,
        domain_literature_strategy=scouted.domain_literature_strategy,
        domain_literature_result=scouted.domain_literature_result,
        domain_benchmark_resolver=scouted.domain_benchmark_resolver,
        domain_experiment_protocol=scouted.domain_experiment_protocol,
        domain_readiness_status=scouted.domain_readiness_status,
        domain_claim_ceiling=scouted.domain_claim_ceiling,
        experiment_execution_plan_id=experiment_execution_plan.plan_id,
        experiment_execution_job_count=experiment_execution_plan.job_count,
        experiment_execution_routes=[
            job.execution_route for job in experiment_execution_plan.jobs
        ],
        experiment_execution_status=experiment_execution_result.status,
        experiment_execution_approval_states=[
            job.approval_state for job in experiment_execution_plan.jobs
        ],
        experiment_execution_output_validation=experiment_execution_result.output_validation,
        experiment_execution_failure_classification=experiment_execution_result.failure_classification,
        experiment_execution_repair_recommendation=experiment_execution_result.repair_recommendation,
        experiment_execution_blockers=[
            blocker.reason for blocker in experiment_execution_result.blockers
        ],
        experiment_execution_claim_ceiling=experiment_execution_result.claim_ceiling,
        experiment_execution_package_manifest_fragment=(
            experiment_execution_result.package_manifest_fragment
        ),
        paper_decision=project_paper.paper_decision,
        steps_completed=[
            "idea",
            "research_brief",
            "domain_routing_blocker",
            "literature_scout",
            "gap_mining",
            "project_paper_orchestration",
            "project_revision_action_plan",
            "project_reviewer_response_dossier",
            "project_rereview",
            "publication_readiness_blocker",
        ],
        direction_count=scouted.direction_count,
        hypothesis_count=scouted.hypothesis_count,
        literature_cache_hit_count=(
            literature_scout.cache_hit_count if literature_scout is not None else 0
        ),
        real_literature_count=0,
        literature_source_counts=(
            dict(literature_scout.source_counts) if literature_scout is not None else {}
        ),
        literature_source_sufficiency_ready=(
            bool(scouted.domain_literature_result.source_sufficiency_ready)
            if scouted.domain_literature_result is not None
            else False
        ),
        literature_connector_availability=(
            [
                {
                    "source": status.source,
                    "availability_status": status.availability_status,
                    "cache_hit_count": status.cache_hit_count,
                    "cache_miss_count": status.cache_miss_count,
                    "network_request_count": status.network_request_count,
                    "paper_count": status.paper_count,
                    "unavailable_reason": status.unavailable_reason,
                }
                for status in literature_scout.source_statuses
            ]
            if literature_scout is not None
            else []
        ),
        literature_extraction_limitations=(
            list(scouted.domain_literature_result.extraction_limitations)
            if scouted.domain_literature_result is not None
            else []
        ),
        literature_network_enabled=False,
        evidence_complete=False,
        paper_review_package_ready=False,
        project_paper_path=project_paper.project_paper_path,
        project_submission_manifest_path=project_paper.project_submission_manifest_path,
        project_publication_manifest_path=project_paper.project_publication_manifest_path,
        project_publication_readiness_report_path=project_paper.project_publication_readiness_report_path,
        project_experiment_repair_index_path=project_paper.project_experiment_repair_index_path,
        project_statistics_report_path=project_paper.project_statistics_report_path,
        project_repair_execution_log_path=project_paper.project_repair_execution_log_path,
        project_review_findings_path=project_paper.project_review_findings_path,
        project_retrieval_evidence_ledger_path=project_paper.project_retrieval_evidence_ledger_path,
        project_negative_evidence_report_path=project_paper.project_negative_evidence_report_path,
        project_offline_publication_case_path=project_paper.project_offline_publication_case_path,
        project_offline_publication_audit_path=project_paper.project_offline_publication_audit_path,
        **source_trace_fields,
        project_review_bundle_ready=project_paper.project_review_bundle_ready,
        project_final_publish_ready=project_paper.project_final_publish_ready,
        project_revision_action_count=project_paper.project_paper_revision_action_count,
        project_review_finding_count=submission_fields["project_review_finding_count"],
        project_review_findings_mapped_to_actions=submission_fields[
            "project_review_findings_mapped_to_actions"
        ],
        project_revision_action_plan_path=submission_fields["project_revision_action_plan_path"],
        project_revision_response_dossier_path=submission_fields[
            "project_revision_response_dossier_path"
        ],
        project_revision_round_path=submission_fields["project_revision_round_path"],
        project_revision_selected_action_ids=submission_fields[
            "project_revision_selected_action_ids"
        ],
        project_revision_paper_only_action_ids=submission_fields[
            "project_revision_paper_only_action_ids"
        ],
        project_revision_blocked_evidence_action_ids=submission_fields[
            "project_revision_blocked_evidence_action_ids"
        ],
        project_revision_response_item_count=submission_fields[
            "project_revision_response_item_count"
        ],
        project_revision_rereview_resolved_count=submission_fields[
            "project_revision_rereview_resolved_count"
        ],
        project_revision_rereview_partially_resolved_count=submission_fields[
            "project_revision_rereview_partially_resolved_count"
        ],
        project_revision_rereview_unresolved_count=submission_fields[
            "project_revision_rereview_unresolved_count"
        ],
        project_revision_rereview_regressed_count=submission_fields[
            "project_revision_rereview_regressed_count"
        ],
        project_revision_terminal_status=submission_fields["project_revision_terminal_status"],
        project_revision_readiness_impact=submission_fields[
            "project_revision_readiness_impact"
        ],
        project_submission_blockers=list(project_paper.project_submission_blockers),
        project_submission_bundle_kind=submission_fields["project_submission_bundle_kind"],
        project_submission_asset_roles=submission_fields["project_submission_asset_roles"],
        project_submission_missing_asset_roles=submission_fields[
            "project_submission_missing_asset_roles"
        ],
        project_submission_required_roles_present=submission_fields[
            "project_submission_required_roles_present"
        ],
        project_paper_section_coverage_complete=not project_paper.project_paper_missing_sections,
        project_paper_present_sections=list(project_paper.project_paper_sections),
        project_paper_missing_sections=list(project_paper.project_paper_missing_sections),
        project_claim_ceiling=scouted.domain_claim_ceiling,
        project_kill_criteria=list(scouted.domain_kill_criteria),
        project_required_followups=list(scouted.domain_required_followups),
        architecture_materials=[
            (
                f"{task_kind}: unsupported-domain brief `{scouted.brief_id}` preserved "
                "a structured domain-routing audit and created no hypotheses."
            )
        ],
        case_study_materials=[
            (
                f"{task_kind}: project readiness artifact `{project_paper.project_publication_readiness_report_path}` "
                "records the unsupported-domain blocker without experiment outputs."
            )
        ],
        failure_analysis_materials=[
            f"{task_kind}: blocked audit - {item}" for item in blockers[:5]
        ],
        blockers=blockers,
    )


def _benchmark_for_domain_trace(scouted, plan) -> tuple[BenchmarkSource | None, Any | None]:
    resolver = plan.domain_benchmark_resolver
    if resolver is None or resolver.benchmark_name is None or resolver.task_family is None:
        return None, None
    source = BenchmarkSource(
        kind=resolver.source_kind or "builtin",
        name=resolver.benchmark_name,
        dataset_id=resolver.dataset_id,
        revision=resolver.revision,
        license=resolver.license,
        file_path=resolver.source_locator if resolver.source_kind not in {"builtin"} else None,
        task_family_hint=resolver.task_family,
    )
    benchmark = builtin_benchmark(
        resolver.task_family,
        source=source,
        topic=scouted.original_idea,
    )
    return source, build_experiment_spec(resolver.task_family, benchmark)


def _build_case_trace(project_id: str, case: dict[str, Any]) -> AutoResearchEvaluationCaseTraceRead:
    brief = build_research_brief(
        project_id=project_id,
        payload=_payload_for_case(case),
    )
    if case.get("expected_blocked"):
        return _blocked_domain_trace(project_id=project_id, case=case)
    if str(case["task_kind"]) == "claim_evidence_vertical_task" or case.get("seed_cached_literature"):
        _seed_domain_cached_literature(brief)
    scouted = scout_and_mine_gaps(brief)
    save_research_brief(scouted)
    hypothesis = selected_hypothesis_from_brief(scouted)
    plan = build_experiment_factory_plan(
        project_id=project_id,
        brief=scouted,
        hypothesis=hypothesis,
    )
    domain_id = (
        scouted.domain_decision.domain_id
        if scouted.domain_decision is not None
        else None
    )
    if domain_id == "claim_evidence_retrieval":
        imported_scifact_payload = _load_imported_scifact_vertical_payload()
        execution = execute_cached_claim_evidence_experiment_factory(
            plan,
            benchmark_payload=imported_scifact_payload,
            executor_mode="local",
        )
        execution_step = "imported_frozen_benchmark_execution"
    else:
        execution = execute_toy_experiment_factory(plan)
        execution_step = "toy_execution"
    experiment_execution_plan = build_experiment_execution_plan(
        factory_plan=plan,
        brief=scouted,
    )
    experiment_execution_result = execute_experiment_execution_plan(
        experiment_execution_plan
    )

    scientific_evidence_blockers = list(execution.evidence_ledger.blockers)
    blockers = _dedupe(
        [
            *plan.blockers,
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
    if scientific_evidence_blockers:
        failure_analysis_materials.extend(
            (
                f"{case['task_kind']}: scientific evidence limitation retained - {item}"
            )
            for item in scientific_evidence_blockers[:5]
        )
    ready = (
        execution.result_artifact.status == "done"
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
        execution_step,
        "evidence_ledger",
    ]
    if ready:
        steps.extend(["paper_draft", "review_package"])
    project_paper_path = None
    project_submission_manifest_path = None
    project_publication_manifest_path = None
    project_publication_readiness_report_path = None
    project_experiment_repair_index_path = None
    project_statistics_report_path = None
    project_repair_execution_log_path = None
    project_review_findings_path = None
    project_retrieval_evidence_ledger_path = None
    project_negative_evidence_report_path = None
    project_offline_publication_case_path = None
    project_offline_publication_audit_path = None
    project_source_trace_fields: dict[str, Any] = {
        "project_paper_sources_manifest_path": None,
        "project_paper_sources_reconstructable": False,
        "project_paper_source_package_ready": False,
        "project_paper_missing_source_files": [],
        "project_paper_missing_external_artifacts": [],
        "project_manuscript_context_path": None,
        "project_manuscript_context_complete": False,
        "project_manuscript_context_fingerprint": None,
    }
    project_submission_trace_fields: dict[str, Any] = {
        "project_revision_action_plan_path": None,
        "project_revision_response_dossier_path": None,
        "project_revision_round_path": None,
        "project_revision_selected_action_ids": [],
        "project_revision_paper_only_action_ids": [],
        "project_revision_blocked_evidence_action_ids": [],
        "project_revision_response_item_count": 0,
        "project_revision_rereview_resolved_count": 0,
        "project_revision_rereview_partially_resolved_count": 0,
        "project_revision_rereview_unresolved_count": 0,
        "project_revision_rereview_regressed_count": 0,
        "project_revision_terminal_status": "needs_revision",
        "project_revision_readiness_impact": None,
        "project_submission_bundle_kind": None,
        "project_submission_asset_roles": [],
        "project_submission_missing_asset_roles": [],
        "project_submission_required_roles_present": False,
        "project_submission_archive_manifest_path": None,
        "project_submission_archive_path": None,
        "project_reproducibility_checklist_json_path": None,
        "project_artifact_integrity_audit_path": None,
        "project_final_publish_decision_path": None,
        "project_submission_archive_complete": False,
        "project_submission_archive_current": False,
        "project_submission_archive_ready_for_final_download": False,
        "project_submission_archive_entry_count": 0,
        "project_submission_archive_missing_required_entry_count": 0,
        "project_submission_archive_hash_mismatch_entry_count": 0,
        "project_submission_archive_stale_entry_count": 0,
        "project_reproducibility_checklist_complete": False,
        "project_reproducibility_checklist_missing_required_count": 0,
        "project_reproducibility_checklist_partial_required_count": 0,
        "project_artifact_integrity_audit_complete": False,
        "project_artifact_integrity_unresolved_issue_count": 0,
        "project_final_publish_policy_version": None,
        "project_final_publish_failed_check_ids": [],
    }
    project_review_bundle_ready = False
    project_final_publish_ready = False
    project_revision_action_count = 0
    project_review_finding_count = 0
    project_review_findings_mapped_to_actions = False
    project_submission_blockers: list[str] = []
    project_submission_bundle_kind = None
    project_submission_asset_roles: list[str] = []
    project_submission_missing_asset_roles: list[str] = []
    project_submission_required_roles_present = False
    project_experiment_execution_source_counts: dict[str, int] = {}
    project_imported_replay_run_ids: list[str] = []
    project_materialized_execution_run_ids: list[str] = []
    project_paper_section_coverage_complete = False
    project_paper_present_sections: list[str] = []
    project_paper_missing_sections: list[str] = []
    project_claim_support_complete = False
    project_supported_core_claim_count = 0
    project_partial_or_unsupported_core_claim_count = 0
    project_claim_ceiling: str | None = None
    project_negative_evidence_coverage_complete = False
    project_negative_evidence_count = _artifact_negative_evidence_count(execution.result_artifact)
    project_phase6_negative_evidence_categories: list[str] = []
    project_phase6_negative_evidence_missing_categories: list[str] = []
    project_phase6_negative_evidence_required_categories: list[str] = []
    project_phase6_negative_evidence_category_counts: dict[str, int] = {}
    project_phase6_negative_evidence_coverage_complete = False
    project_phase6_negative_evidence_runtime_failure_observed = False
    project_final_publish_package_artifacts_complete = False
    project_final_publish_engineering_gap_count = 0
    project_final_publish_scientific_evidence_gap_count = 0
    project_final_publish_engineering_gaps: list[dict[str, Any]] = []
    project_final_publish_scientific_evidence_gaps: list[dict[str, Any]] = []
    project_final_publish_blocker_classification: list[dict[str, Any]] = []
    project_final_publish_phase1_blocked_requirement_ids: list[str] = []
    project_benchmark_schema_coverage_complete = False
    project_benchmark_schema_coverage_blockers: list[str] = []
    project_benchmark_source_observation_coverage_complete = False
    project_benchmark_source_observation_blockers: list[str] = []
    project_benchmark_final_publish_candidate_coverage_complete = False
    project_benchmark_final_publish_candidate_blockers: list[str] = []
    project_benchmark_source_independence_ready = False
    project_benchmark_source_independence_blockers: list[str] = []
    project_benchmark_snapshot_artifact_materialized = False
    project_benchmark_snapshot_artifact_record_count = 0
    project_benchmark_snapshot_artifact_materialized_count = 0
    project_benchmark_snapshot_artifact_all_required_materialized = False
    project_benchmark_snapshot_artifact_unmaterialized_run_ids: list[str] = []
    project_kill_criteria: list[str] = []
    project_required_followups: list[str] = []
    end_to_end_package_ready = False
    literature_scout = scouted.literature_scout
    real_literature = (
        literature_insights_from_scout(literature_scout)
        if literature_scout is not None
        else []
    )
    if str(case["task_kind"]) == "claim_evidence_vertical_task":
        run_id = f"eval_{case['case_id']}_run"
        imported_scifact_payload = _load_imported_scifact_vertical_payload()
        benchmark = ResolvedBenchmark(
            source=_IMPORTED_SCIFACT_VERTICAL_SOURCE,
            task_family="ir_reranking",
            payload=imported_scifact_payload,
            benchmark_name=str(imported_scifact_payload["name"]),
            benchmark_description=str(imported_scifact_payload["description"]),
        )
        spec = build_experiment_spec("ir_reranking", benchmark)
        run = AutoResearchRunRead(
            id=run_id,
            project_id=project_id,
            topic=str(case["idea"]),
            status="done",
            brief_id=scouted.brief_id,
            hypothesis_id=hypothesis.hypothesis_id,
            direction_selection_reason=scouted.selection_reason,
            task_family="ir_reranking",
            benchmark=_IMPORTED_SCIFACT_VERTICAL_SOURCE,
            spec=spec,
            execution_backend=plan.execution_backend,
            literature=real_literature,
            artifact=execution.result_artifact,
            experiment_factory_plan=plan,
            experiment_factory_environment_manifest=execution.environment_manifest,
            experiment_factory_materialized_jobs=execution.materialized_jobs,
            experiment_execution_plan=experiment_execution_plan,
            experiment_execution_result=experiment_execution_result,
            evidence_ledger=execution.evidence_ledger,
            experiment_factory_repair_plan=execution.repair_plan,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        save_run(run)
        imported_scifact_retrieval_payload = (
            _load_imported_scifact_retrieval_vertical_payload()
        )
        beir_execution = execute_cached_claim_evidence_experiment_factory(
            plan,
            benchmark_payload=imported_scifact_retrieval_payload,
            executor_mode="local",
        )
        project_negative_evidence_count += _artifact_negative_evidence_count(beir_execution.result_artifact)
        beir_benchmark = ResolvedBenchmark(
            source=_IMPORTED_SCIFACT_RETRIEVAL_VERTICAL_SOURCE,
            task_family="ir_reranking",
            payload=imported_scifact_retrieval_payload,
            benchmark_name=str(imported_scifact_retrieval_payload["name"]),
            benchmark_description=str(imported_scifact_retrieval_payload["description"]),
        )
        beir_spec = build_experiment_spec("ir_reranking", beir_benchmark)
        beir_run = AutoResearchRunRead(
            id=f"{run_id}_beir",
            project_id=project_id,
            topic=str(case["idea"]),
            status="done",
            brief_id=scouted.brief_id,
            hypothesis_id=hypothesis.hypothesis_id,
            direction_selection_reason=(
                "Second benchmark-ladder run for a repository-local SciFact retrieval-only frozen view; "
                "kept separate from SciFact-style verification evidence but not treated as an independent source dataset."
            ),
            task_family="ir_reranking",
            benchmark=_IMPORTED_SCIFACT_RETRIEVAL_VERTICAL_SOURCE,
            spec=beir_spec,
            execution_backend=plan.execution_backend,
            literature=real_literature,
            artifact=beir_execution.result_artifact,
            experiment_factory_plan=plan,
            experiment_factory_environment_manifest=beir_execution.environment_manifest,
            experiment_factory_materialized_jobs=beir_execution.materialized_jobs,
            evidence_ledger=beir_execution.evidence_ledger,
            experiment_factory_repair_plan=beir_execution.repair_plan,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        save_run(beir_run)
        project_paper = build_project_paper_orchestration(project_id)
        project_paper_path = project_paper.project_paper_path
        project_submission_manifest_path = project_paper.project_submission_manifest_path
        project_publication_manifest_path = project_paper.project_publication_manifest_path
        project_publication_readiness_report_path = project_paper.project_publication_readiness_report_path
        project_experiment_repair_index_path = project_paper.project_experiment_repair_index_path
        project_statistics_report_path = project_paper.project_statistics_report_path
        project_repair_execution_log_path = project_paper.project_repair_execution_log_path
        project_review_findings_path = project_paper.project_review_findings_path
        project_retrieval_evidence_ledger_path = project_paper.project_retrieval_evidence_ledger_path
        project_negative_evidence_report_path = project_paper.project_negative_evidence_report_path
        project_offline_publication_case_path = project_paper.project_offline_publication_case_path
        project_offline_publication_audit_path = project_paper.project_offline_publication_audit_path
        project_source_trace_fields = _project_source_trace_fields(project_paper)
        project_submission_trace_fields = _submission_trace_fields(project_paper)
        project_review_bundle_ready = project_paper.project_review_bundle_ready
        project_final_publish_ready = project_paper.project_final_publish_ready
        project_revision_action_count = project_paper.project_paper_revision_action_count
        project_submission_blockers = list(project_paper.project_submission_blockers)
        review_findings = _read_json_file(project_review_findings_path)
        finding_records = review_findings.get("findings", [])
        if isinstance(finding_records, list):
            project_review_finding_count = len(
                [item for item in finding_records if isinstance(item, dict)]
            )
            mapped_action_ids = {
                str(item.get("mapped_revision_action_id"))
                for item in finding_records
                if isinstance(item, dict) and item.get("mapped_revision_action_id")
            }
            project_review_findings_mapped_to_actions = (
                bool(mapped_action_ids)
                and mapped_action_ids
                == {action.action_id for action in project_paper.project_paper_revision_actions}
            )
        submission_manifest = _read_json_file(project_submission_manifest_path)
        experiment_repair_index = _read_json_file(project_experiment_repair_index_path)
        compiler_evidence = _read_json_file(project_paper.project_paper_compiler_evidence_path)
        readiness_report = _read_json_file(project_publication_readiness_report_path)
        negative_evidence_report = _read_json_file(project_negative_evidence_report_path)
        offline_publication_audit = _read_json_file(project_offline_publication_audit_path)
        generated_assets = submission_manifest.get("generated_assets", [])
        if isinstance(generated_assets, list):
            project_submission_asset_roles = sorted(
                {
                    str(item.get("role"))
                    for item in generated_assets
                    if isinstance(item, dict) and item.get("role")
                }
            )
            missing_roles = {
                str(item.get("role"))
                for item in generated_assets
                if isinstance(item, dict) and item.get("role") and not item.get("exists", False)
            }
        else:
            project_submission_asset_roles = []
            missing_roles = set()
        project_submission_missing_asset_roles = sorted(
            (_OFFLINE_PUBLICATION_CASE_REQUIRED_PACKAGE_ROLES - set(project_submission_asset_roles))
            | missing_roles
        )
        project_submission_required_roles_present = (
            not project_submission_missing_asset_roles
            and bool(project_submission_asset_roles)
        )
        project_submission_bundle_kind = (
            str(submission_manifest.get("bundle_kind"))
            if submission_manifest.get("bundle_kind") is not None
            else None
        )
        execution_source_counts = experiment_repair_index.get("execution_source_counts", {})
        project_experiment_execution_source_counts = (
            {
                str(key): int(value)
                for key, value in execution_source_counts.items()
                if isinstance(value, int)
            }
            if isinstance(execution_source_counts, dict)
            else {}
        )
        imported_run_ids = experiment_repair_index.get("imported_result_replay_run_ids", [])
        project_imported_replay_run_ids = [
            str(item) for item in imported_run_ids if isinstance(item, str)
        ] if isinstance(imported_run_ids, list) else []
        materialized_run_ids = experiment_repair_index.get("materialized_execution_run_ids", [])
        project_materialized_execution_run_ids = [
            str(item) for item in materialized_run_ids if isinstance(item, str)
        ] if isinstance(materialized_run_ids, list) else []
        section_coverage = compiler_evidence.get("section_coverage", {})
        if isinstance(section_coverage, dict):
            project_paper_section_coverage_complete = bool(section_coverage.get("complete"))
            present_sections = section_coverage.get("present_sections", [])
            missing_sections = section_coverage.get("missing_sections", [])
            project_paper_present_sections = [
                str(item) for item in present_sections if isinstance(item, str)
            ] if isinstance(present_sections, list) else []
            project_paper_missing_sections = [
                str(item) for item in missing_sections if isinstance(item, str)
            ] if isinstance(missing_sections, list) else []
        claim_support = compiler_evidence.get("claim_support_coverage", {})
        if isinstance(claim_support, dict):
            project_claim_support_complete = bool(claim_support.get("complete"))
            project_supported_core_claim_count = int(claim_support.get("supported_core_claim_count") or 0)
            project_partial_or_unsupported_core_claim_count = int(
                claim_support.get("partial_or_unsupported_core_claim_count") or 0
            )
        statistics_coverage = compiler_evidence.get("statistics_coverage", {})
        if isinstance(statistics_coverage, dict):
            statistics_negative_count = int(statistics_coverage.get("negative_result_count") or 0)
            statistics_failure_count = int(statistics_coverage.get("failure_case_count") or 0)
            project_negative_evidence_count = max(
                project_negative_evidence_count,
                statistics_negative_count + statistics_failure_count,
            )
        limitations_coverage = compiler_evidence.get("limitations_coverage", {})
        project_negative_evidence_coverage_complete = bool(
            isinstance(limitations_coverage, dict)
            and limitations_coverage.get("complete")
            and project_negative_evidence_count > 0
        )
        if negative_evidence_report:
            project_negative_evidence_count = max(
                project_negative_evidence_count,
                int(negative_evidence_report.get("entry_count") or 0),
            )
            phase6_categories = negative_evidence_report.get("phase6_categories", [])
            project_phase6_negative_evidence_categories = _dedupe(
                [str(item) for item in phase6_categories if isinstance(item, str)]
            ) if isinstance(phase6_categories, list) else []
            phase6_missing_categories = negative_evidence_report.get(
                "phase6_missing_categories", []
            )
            project_phase6_negative_evidence_missing_categories = _dedupe(
                [str(item) for item in phase6_missing_categories if isinstance(item, str)]
            ) if isinstance(phase6_missing_categories, list) else []
            phase6_required_categories = negative_evidence_report.get(
                "phase6_required_categories", []
            )
            project_phase6_negative_evidence_required_categories = _dedupe(
                [str(item) for item in phase6_required_categories if isinstance(item, str)]
            ) if isinstance(phase6_required_categories, list) else []
            phase6_category_counts = negative_evidence_report.get(
                "phase6_category_counts", {}
            )
            project_phase6_negative_evidence_category_counts = (
                {
                    str(key): int(value)
                    for key, value in phase6_category_counts.items()
                    if isinstance(value, int)
                }
                if isinstance(phase6_category_counts, dict)
                else {}
            )
            project_phase6_negative_evidence_coverage_complete = bool(
                negative_evidence_report.get("phase6_coverage_complete")
            )
            project_phase6_negative_evidence_runtime_failure_observed = bool(
                negative_evidence_report.get("phase6_runtime_failure_observed")
            )
        final_publish_gap_audit = (
            offline_publication_audit.get("final_publish_gap_audit", {})
            if isinstance(offline_publication_audit, dict)
            else {}
        )
        if isinstance(final_publish_gap_audit, dict):
            project_final_publish_package_artifacts_complete = bool(
                final_publish_gap_audit.get("package_artifacts_complete")
            )
            project_final_publish_engineering_gap_count = int(
                final_publish_gap_audit.get("engineering_gap_count") or 0
            )
            project_final_publish_scientific_evidence_gap_count = int(
                final_publish_gap_audit.get("scientific_evidence_gap_count") or 0
            )
            engineering_gaps = final_publish_gap_audit.get("engineering_gaps", [])
            project_final_publish_engineering_gaps = (
                [item for item in engineering_gaps if isinstance(item, dict)]
                if isinstance(engineering_gaps, list)
                else []
            )
            scientific_gaps = final_publish_gap_audit.get("scientific_evidence_gaps", [])
            project_final_publish_scientific_evidence_gaps = (
                [item for item in scientific_gaps if isinstance(item, dict)]
                if isinstance(scientific_gaps, list)
                else []
            )
            blocker_classification = final_publish_gap_audit.get(
                "final_publish_blocker_classification", []
            )
            project_final_publish_blocker_classification = (
                [item for item in blocker_classification if isinstance(item, dict)]
                if isinstance(blocker_classification, list)
                else []
            )
            phase1_blocked = final_publish_gap_audit.get("phase1_blocked_requirement_ids", [])
            project_final_publish_phase1_blocked_requirement_ids = (
                [str(item) for item in phase1_blocked if isinstance(item, str)]
                if isinstance(phase1_blocked, list)
                else []
            )
            project_benchmark_final_publish_candidate_coverage_complete = bool(
                final_publish_gap_audit.get(
                    "benchmark_final_publish_candidate_coverage_complete"
                )
            )
            benchmark_blockers = final_publish_gap_audit.get(
                "benchmark_final_publish_candidate_blockers", []
            )
            project_benchmark_final_publish_candidate_blockers = (
                [str(item) for item in benchmark_blockers if isinstance(item, str)]
                if isinstance(benchmark_blockers, list)
                else []
            )
            project_benchmark_source_independence_ready = bool(
                final_publish_gap_audit.get("benchmark_source_independence_ready")
            )
            source_independence_blockers = final_publish_gap_audit.get(
                "benchmark_source_independence_blockers", []
            )
            project_benchmark_source_independence_blockers = (
                [str(item) for item in source_independence_blockers if isinstance(item, str)]
                if isinstance(source_independence_blockers, list)
                else []
            )
            project_benchmark_snapshot_artifact_materialized = bool(
                final_publish_gap_audit.get("benchmark_snapshot_artifact_materialized")
            )
            project_benchmark_snapshot_artifact_record_count = int(
                final_publish_gap_audit.get("benchmark_snapshot_artifact_record_count")
                or 0
            )
            project_benchmark_snapshot_artifact_materialized_count = int(
                final_publish_gap_audit.get(
                    "benchmark_snapshot_artifact_materialized_count"
                )
                or 0
            )
            project_benchmark_snapshot_artifact_all_required_materialized = bool(
                final_publish_gap_audit.get(
                    "benchmark_snapshot_artifact_all_required_materialized"
                )
            )
            unmaterialized_run_ids = final_publish_gap_audit.get(
                "benchmark_snapshot_artifact_unmaterialized_run_ids", []
            )
            project_benchmark_snapshot_artifact_unmaterialized_run_ids = (
                [str(item) for item in unmaterialized_run_ids if isinstance(item, str)]
                if isinstance(unmaterialized_run_ids, list)
                else []
            )
        benchmark_schema_coverage = readiness_report.get("benchmark_schema_coverage", {})
        if isinstance(benchmark_schema_coverage, dict):
            project_benchmark_schema_coverage_complete = bool(
                benchmark_schema_coverage.get("schema_coverage_complete")
            )
            schema_blockers = benchmark_schema_coverage.get("schema_blockers", [])
            project_benchmark_schema_coverage_blockers = (
                [str(item) for item in schema_blockers if isinstance(item, str)]
                if isinstance(schema_blockers, list)
                else []
            )
        benchmark_observation_coverage = readiness_report.get(
            "benchmark_source_observation_coverage", {}
        )
        if isinstance(benchmark_observation_coverage, dict):
            project_benchmark_source_observation_coverage_complete = bool(
                benchmark_observation_coverage.get("observation_coverage_complete")
            )
            observation_blockers = benchmark_observation_coverage.get(
                "observation_blockers", []
            )
            project_benchmark_source_observation_blockers = (
                [str(item) for item in observation_blockers if isinstance(item, str)]
                if isinstance(observation_blockers, list)
                else []
            )
        kill_criteria = readiness_report.get("kill_criteria", [])
        project_kill_criteria = [
            str(item) for item in kill_criteria if isinstance(item, str)
        ] if isinstance(kill_criteria, list) else []
        required_followups = readiness_report.get("required_followups", [])
        project_required_followups = [
            str(item) for item in required_followups if isinstance(item, str)
        ] if isinstance(required_followups, list) else []
        project_claim_ceiling = _claim_ceiling_from_artifacts(
            final_publish_ready=project_final_publish_ready,
            readiness_report=readiness_report,
            compiler_evidence=compiler_evidence,
            negative_evidence_count=project_negative_evidence_count,
        )
        end_to_end_package_ready = (
            project_review_bundle_ready
            and project_submission_manifest_path is not None
            and project_submission_required_roles_present
        )
        steps.extend(
            [
                "project_paper_orchestration",
                "project_revision_actions",
                "project_revision_action_plan",
                "project_reviewer_response_dossier",
                "project_rereview",
                "project_submission_package",
                "submission_package_v3_asset_manifest",
            ]
        )
        case_study_materials.append(
            (
                f"{case['task_kind']}: project-level manuscript `{project_paper_path}` and submission manifest "
                f"`{project_submission_manifest_path}` were materialized with review_bundle_ready="
                f"{project_review_bundle_ready} and final_publish_ready={project_final_publish_ready}."
            )
        )
        case_study_materials.append(
            (
                f"{case['task_kind']}: benchmark ladder includes repository-local SciFact "
                f"verification snapshot run `{run.id}` normalized from original benchmark records with "
                f"{len(imported_scifact_payload['train']) + len(imported_scifact_payload['test'])} "
                f"normalized examples plus repository-local SciFact retrieval-view run "
                f"`{beir_run.id}` with "
                f"{len(imported_scifact_retrieval_payload['train']) + len(imported_scifact_retrieval_payload['test'])} "
                "retrieval-only examples."
            )
        )
        case_study_materials.append(
            (
                f"{case['task_kind']}: submission package V3 asset roles present="
                f"{len(project_submission_asset_roles)}; missing_roles={project_submission_missing_asset_roles}."
            )
        )
        case_study_materials.append(
            (
                f"{case['task_kind']}: experiment repair index records execution sources "
                f"{project_experiment_execution_source_counts} with imported replay runs "
                f"{project_imported_replay_run_ids} and materialized execution runs "
                f"{project_materialized_execution_run_ids}."
            )
        )
        case_study_materials.append(
            (
                f"{case['task_kind']}: paper sections complete={project_paper_section_coverage_complete}, "
                f"claim_support_complete={project_claim_support_complete}, "
                f"claim_ceiling={project_claim_ceiling}, negative_evidence_count="
                f"{project_negative_evidence_count}."
            )
        )
        failure_analysis_materials.append(
            (
                f"{case['task_kind']}: Phase 6 negative evidence categories covered="
                f"{project_phase6_negative_evidence_categories}; missing="
                f"{project_phase6_negative_evidence_missing_categories}; "
                f"coverage_complete={project_phase6_negative_evidence_coverage_complete}."
            )
        )
        failure_analysis_materials.append(
            (
                f"{case['task_kind']}: final-publish gap audit reports engineering_gaps="
                f"{project_final_publish_engineering_gap_count}, scientific_evidence_gaps="
                f"{project_final_publish_scientific_evidence_gap_count}, blocked_phase1="
                f"{project_final_publish_phase1_blocked_requirement_ids}, "
                f"benchmark_schema_complete={project_benchmark_schema_coverage_complete}, "
                f"benchmark_observation_complete="
                f"{project_benchmark_source_observation_coverage_complete}, "
                f"benchmark_final_candidate_complete="
                f"{project_benchmark_final_publish_candidate_coverage_complete}, "
                f"benchmark_source_independence_ready="
                f"{project_benchmark_source_independence_ready}, "
                f"benchmark_source_independence_blockers="
                f"{project_benchmark_source_independence_blockers}, "
                f"snapshot_materialized="
                f"{project_benchmark_snapshot_artifact_materialized}, "
                f"snapshot_unmaterialized_run_ids="
                f"{project_benchmark_snapshot_artifact_unmaterialized_run_ids}."
            )
        )
        if project_submission_blockers:
            failure_analysis_materials.append(
                (
                    f"{case['task_kind']}: project submission blockers preserve publication honesty: "
                    + "; ".join(project_submission_blockers[:3])
                )
            )
    elif case.get("build_project_package"):
        run_id = f"eval_{case['case_id']}_run"
        benchmark_source, spec = _benchmark_for_domain_trace(scouted, plan)
        run = AutoResearchRunRead(
            id=run_id,
            project_id=project_id,
            topic=str(case["idea"]),
            status="done",
            brief_id=scouted.brief_id,
            hypothesis_id=hypothesis.hypothesis_id,
            direction_selection_reason=scouted.selection_reason,
            task_family=(
                plan.domain_benchmark_resolver.task_family
                if plan.domain_benchmark_resolver is not None
                else None
            ),
            benchmark=benchmark_source,
            spec=spec,
            execution_backend=plan.execution_backend,
            literature=real_literature,
            artifact=execution.result_artifact,
            experiment_factory_plan=plan,
            experiment_factory_environment_manifest=execution.environment_manifest,
            experiment_factory_materialized_jobs=execution.materialized_jobs,
            evidence_ledger=execution.evidence_ledger,
            experiment_factory_repair_plan=execution.repair_plan,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        save_run(run)
        project_paper = build_project_paper_orchestration(project_id)
        project_paper_path = project_paper.project_paper_path
        project_submission_manifest_path = project_paper.project_submission_manifest_path
        project_publication_manifest_path = project_paper.project_publication_manifest_path
        project_publication_readiness_report_path = project_paper.project_publication_readiness_report_path
        project_experiment_repair_index_path = project_paper.project_experiment_repair_index_path
        project_statistics_report_path = project_paper.project_statistics_report_path
        project_repair_execution_log_path = project_paper.project_repair_execution_log_path
        project_review_findings_path = project_paper.project_review_findings_path
        project_retrieval_evidence_ledger_path = project_paper.project_retrieval_evidence_ledger_path
        project_negative_evidence_report_path = project_paper.project_negative_evidence_report_path
        project_offline_publication_case_path = project_paper.project_offline_publication_case_path
        project_offline_publication_audit_path = project_paper.project_offline_publication_audit_path
        project_source_trace_fields = _project_source_trace_fields(project_paper)
        project_review_bundle_ready = project_paper.project_review_bundle_ready
        project_final_publish_ready = project_paper.project_final_publish_ready
        project_revision_action_count = project_paper.project_paper_revision_action_count
        project_submission_blockers = list(project_paper.project_submission_blockers)
        submission_fields = _submission_trace_fields(project_paper)
        project_review_finding_count = submission_fields["project_review_finding_count"]
        project_review_findings_mapped_to_actions = submission_fields[
            "project_review_findings_mapped_to_actions"
        ]
        project_submission_bundle_kind = submission_fields["project_submission_bundle_kind"]
        project_submission_asset_roles = submission_fields["project_submission_asset_roles"]
        project_submission_missing_asset_roles = submission_fields[
            "project_submission_missing_asset_roles"
        ]
        project_submission_required_roles_present = submission_fields[
            "project_submission_required_roles_present"
        ]
        project_paper_section_coverage_complete = not project_paper.project_paper_missing_sections
        project_paper_present_sections = list(project_paper.project_paper_sections)
        project_paper_missing_sections = list(project_paper.project_paper_missing_sections)
        project_claim_ceiling = (
            project_paper.latest_brief_domain_claim_ceiling
            or scouted.domain_claim_ceiling
        )
        project_kill_criteria = list(project_paper.latest_brief_domain_kill_criteria)
        project_required_followups = list(project_paper.latest_brief_domain_required_followups)
        end_to_end_package_ready = bool(
            project_review_bundle_ready and project_submission_manifest_path is not None
        )
        steps.extend(
            [
                "project_paper_orchestration",
                "project_revision_action_plan",
                "project_reviewer_response_dossier",
                "project_rereview",
                "project_submission_package",
                "domain_package_readiness",
            ]
        )
        case_study_materials.append(
            (
                f"{case['task_kind']}: domain package context for "
                f"`{scouted.domain_decision.domain_id if scouted.domain_decision is not None else 'unknown'}` "
                f"was materialized at `{project_publication_readiness_report_path}`."
            )
        )
        if project_submission_blockers:
            failure_analysis_materials.append(
                (
                    f"{case['task_kind']}: package blockers preserve non-final evidence limits: "
                    + "; ".join(project_submission_blockers[:3])
                )
            )
    trace_evidence_complete = bool(
        execution.result_artifact.status == "done"
        and execution.evidence_ledger.entry_count > 0
    )
    if str(case["task_kind"]) == "claim_evidence_vertical_task":
        trace_evidence_complete = bool(
            project_review_bundle_ready
            and project_submission_required_roles_present
            and project_final_publish_package_artifacts_complete
            and project_final_publish_engineering_gap_count == 0
            and project_paper_section_coverage_complete
            and project_claim_support_complete
            and project_negative_evidence_coverage_complete
            and project_phase6_negative_evidence_coverage_complete
            and project_benchmark_final_publish_candidate_coverage_complete
            and project_benchmark_schema_coverage_complete
            and project_benchmark_source_observation_coverage_complete
            and project_experiment_execution_source_counts
            and project_materialized_execution_run_ids
            and project_statistics_report_path is not None
            and project_negative_evidence_report_path is not None
            and project_retrieval_evidence_ledger_path is not None
        )
    paper_decision: AutoResearchProjectPaperDecision = "technical_report" if ready else "do_not_write"
    return AutoResearchEvaluationCaseTraceRead(
        idea=scouted.original_idea,
        brief_id=scouted.brief_id,
        domain_decision=scouted.domain_decision,
        domain_template=scouted.domain_template,
        domain_blockers=scouted.domain_blockers,
        domain_literature_strategy=scouted.domain_literature_strategy,
        domain_literature_result=scouted.domain_literature_result,
        domain_benchmark_resolver=scouted.domain_benchmark_resolver,
        domain_experiment_protocol=scouted.domain_experiment_protocol,
        domain_readiness_status=scouted.domain_readiness_status,
        domain_claim_ceiling=scouted.domain_claim_ceiling,
        selected_hypothesis_id=hypothesis.hypothesis_id,
        experiment_plan_id=plan.plan_id,
        experiment_execution_plan_id=experiment_execution_plan.plan_id,
        experiment_execution_job_count=experiment_execution_plan.job_count,
        experiment_execution_routes=[
            job.execution_route for job in experiment_execution_plan.jobs
        ],
        experiment_execution_status=experiment_execution_result.status,
        experiment_execution_budget_class=(
            experiment_execution_plan.jobs[0].budget_class
            if experiment_execution_plan.jobs
            else None
        ),
        experiment_execution_approval_states=[
            job.approval_state for job in experiment_execution_plan.jobs
        ],
        experiment_execution_output_validation=experiment_execution_result.output_validation,
        experiment_execution_failure_classification=experiment_execution_result.failure_classification,
        experiment_execution_repair_recommendation=experiment_execution_result.repair_recommendation,
        experiment_execution_blockers=[
            blocker.reason for blocker in experiment_execution_result.blockers
        ],
        experiment_execution_claim_ceiling=experiment_execution_result.claim_ceiling,
        experiment_execution_package_manifest_fragment=(
            experiment_execution_result.package_manifest_fragment
        ),
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
        literature_cache_hit_count=(
            literature_scout.cache_hit_count if literature_scout is not None else 0
        ),
        real_literature_count=len(real_literature),
        literature_source_counts=(
            dict(literature_scout.source_counts) if literature_scout is not None else {}
        ),
        literature_source_sufficiency_ready=(
            bool(scouted.domain_literature_result.source_sufficiency_ready)
            if scouted.domain_literature_result is not None
            else False
        ),
        literature_connector_availability=(
            [
                {
                    "source": status.source,
                    "availability_status": status.availability_status,
                    "cache_hit_count": status.cache_hit_count,
                    "cache_miss_count": status.cache_miss_count,
                    "network_request_count": status.network_request_count,
                    "paper_count": status.paper_count,
                    "unavailable_reason": status.unavailable_reason,
                }
                for status in literature_scout.source_statuses
            ]
            if literature_scout is not None
            else []
        ),
        literature_extraction_limitations=(
            list(scouted.domain_literature_result.extraction_limitations)
            if scouted.domain_literature_result is not None
            else []
        ),
        literature_network_enabled=(
            literature_scout.network_enabled if literature_scout is not None else False
        ),
        evidence_complete=trace_evidence_complete,
        paper_review_package_ready=ready,
        project_paper_path=project_paper_path,
        project_submission_manifest_path=project_submission_manifest_path,
        project_publication_manifest_path=project_publication_manifest_path,
        project_publication_readiness_report_path=project_publication_readiness_report_path,
        project_experiment_repair_index_path=project_experiment_repair_index_path,
        project_statistics_report_path=project_statistics_report_path,
        project_repair_execution_log_path=project_repair_execution_log_path,
        project_review_findings_path=project_review_findings_path,
        project_retrieval_evidence_ledger_path=project_retrieval_evidence_ledger_path,
        project_negative_evidence_report_path=project_negative_evidence_report_path,
        project_offline_publication_case_path=project_offline_publication_case_path,
        project_offline_publication_audit_path=project_offline_publication_audit_path,
        **project_source_trace_fields,
        project_review_bundle_ready=project_review_bundle_ready,
        project_final_publish_ready=project_final_publish_ready,
        project_revision_action_count=project_revision_action_count,
        project_review_finding_count=project_review_finding_count,
        project_review_findings_mapped_to_actions=project_review_findings_mapped_to_actions,
        project_revision_action_plan_path=project_submission_trace_fields[
            "project_revision_action_plan_path"
        ],
        project_revision_response_dossier_path=project_submission_trace_fields[
            "project_revision_response_dossier_path"
        ],
        project_revision_round_path=project_submission_trace_fields[
            "project_revision_round_path"
        ],
        project_revision_selected_action_ids=project_submission_trace_fields[
            "project_revision_selected_action_ids"
        ],
        project_revision_paper_only_action_ids=project_submission_trace_fields[
            "project_revision_paper_only_action_ids"
        ],
        project_revision_blocked_evidence_action_ids=project_submission_trace_fields[
            "project_revision_blocked_evidence_action_ids"
        ],
        project_revision_response_item_count=project_submission_trace_fields[
            "project_revision_response_item_count"
        ],
        project_revision_rereview_resolved_count=project_submission_trace_fields[
            "project_revision_rereview_resolved_count"
        ],
        project_revision_rereview_partially_resolved_count=project_submission_trace_fields[
            "project_revision_rereview_partially_resolved_count"
        ],
        project_revision_rereview_unresolved_count=project_submission_trace_fields[
            "project_revision_rereview_unresolved_count"
        ],
        project_revision_rereview_regressed_count=project_submission_trace_fields[
            "project_revision_rereview_regressed_count"
        ],
        project_revision_terminal_status=project_submission_trace_fields[
            "project_revision_terminal_status"
        ],
        project_revision_readiness_impact=project_submission_trace_fields[
            "project_revision_readiness_impact"
        ],
        project_submission_blockers=project_submission_blockers,
        project_submission_bundle_kind=project_submission_bundle_kind,
        project_submission_asset_roles=project_submission_asset_roles,
        project_submission_missing_asset_roles=project_submission_missing_asset_roles,
        project_submission_required_roles_present=project_submission_required_roles_present,
        project_submission_archive_manifest_path=project_submission_trace_fields[
            "project_submission_archive_manifest_path"
        ],
        project_submission_archive_path=project_submission_trace_fields[
            "project_submission_archive_path"
        ],
        project_reproducibility_checklist_json_path=project_submission_trace_fields[
            "project_reproducibility_checklist_json_path"
        ],
        project_artifact_integrity_audit_path=project_submission_trace_fields[
            "project_artifact_integrity_audit_path"
        ],
        project_final_publish_decision_path=project_submission_trace_fields[
            "project_final_publish_decision_path"
        ],
        project_submission_archive_complete=project_submission_trace_fields[
            "project_submission_archive_complete"
        ],
        project_submission_archive_current=project_submission_trace_fields[
            "project_submission_archive_current"
        ],
        project_submission_archive_ready_for_final_download=project_submission_trace_fields[
            "project_submission_archive_ready_for_final_download"
        ],
        project_submission_archive_entry_count=project_submission_trace_fields[
            "project_submission_archive_entry_count"
        ],
        project_submission_archive_missing_required_entry_count=project_submission_trace_fields[
            "project_submission_archive_missing_required_entry_count"
        ],
        project_submission_archive_hash_mismatch_entry_count=project_submission_trace_fields[
            "project_submission_archive_hash_mismatch_entry_count"
        ],
        project_submission_archive_stale_entry_count=project_submission_trace_fields[
            "project_submission_archive_stale_entry_count"
        ],
        project_reproducibility_checklist_complete=project_submission_trace_fields[
            "project_reproducibility_checklist_complete"
        ],
        project_reproducibility_checklist_missing_required_count=project_submission_trace_fields[
            "project_reproducibility_checklist_missing_required_count"
        ],
        project_reproducibility_checklist_partial_required_count=project_submission_trace_fields[
            "project_reproducibility_checklist_partial_required_count"
        ],
        project_artifact_integrity_audit_complete=project_submission_trace_fields[
            "project_artifact_integrity_audit_complete"
        ],
        project_artifact_integrity_unresolved_issue_count=project_submission_trace_fields[
            "project_artifact_integrity_unresolved_issue_count"
        ],
        project_final_publish_policy_version=project_submission_trace_fields[
            "project_final_publish_policy_version"
        ],
        project_final_publish_failed_check_ids=project_submission_trace_fields[
            "project_final_publish_failed_check_ids"
        ],
        project_experiment_execution_source_counts=project_experiment_execution_source_counts,
        project_imported_replay_run_ids=project_imported_replay_run_ids,
        project_materialized_execution_run_ids=project_materialized_execution_run_ids,
        project_paper_section_coverage_complete=project_paper_section_coverage_complete,
        project_paper_present_sections=project_paper_present_sections,
        project_paper_missing_sections=project_paper_missing_sections,
        project_claim_support_complete=project_claim_support_complete,
        project_supported_core_claim_count=project_supported_core_claim_count,
        project_partial_or_unsupported_core_claim_count=project_partial_or_unsupported_core_claim_count,
        project_claim_ceiling=project_claim_ceiling,
        project_negative_evidence_coverage_complete=project_negative_evidence_coverage_complete,
        project_negative_evidence_count=project_negative_evidence_count,
        project_phase6_negative_evidence_categories=project_phase6_negative_evidence_categories,
        project_phase6_negative_evidence_missing_categories=project_phase6_negative_evidence_missing_categories,
        project_phase6_negative_evidence_required_categories=project_phase6_negative_evidence_required_categories,
        project_phase6_negative_evidence_category_counts=project_phase6_negative_evidence_category_counts,
        project_phase6_negative_evidence_coverage_complete=project_phase6_negative_evidence_coverage_complete,
        project_phase6_negative_evidence_runtime_failure_observed=project_phase6_negative_evidence_runtime_failure_observed,
        project_final_publish_package_artifacts_complete=project_final_publish_package_artifacts_complete,
        project_final_publish_engineering_gap_count=project_final_publish_engineering_gap_count,
        project_final_publish_scientific_evidence_gap_count=project_final_publish_scientific_evidence_gap_count,
        project_final_publish_engineering_gaps=project_final_publish_engineering_gaps,
        project_final_publish_scientific_evidence_gaps=project_final_publish_scientific_evidence_gaps,
        project_final_publish_blocker_classification=project_final_publish_blocker_classification,
        project_final_publish_phase1_blocked_requirement_ids=project_final_publish_phase1_blocked_requirement_ids,
        project_benchmark_schema_coverage_complete=project_benchmark_schema_coverage_complete,
        project_benchmark_schema_coverage_blockers=project_benchmark_schema_coverage_blockers,
        project_benchmark_source_observation_coverage_complete=project_benchmark_source_observation_coverage_complete,
        project_benchmark_source_observation_blockers=project_benchmark_source_observation_blockers,
        project_benchmark_final_publish_candidate_coverage_complete=project_benchmark_final_publish_candidate_coverage_complete,
        project_benchmark_final_publish_candidate_blockers=project_benchmark_final_publish_candidate_blockers,
        project_benchmark_source_independence_ready=project_benchmark_source_independence_ready,
        project_benchmark_source_independence_blockers=project_benchmark_source_independence_blockers,
        project_benchmark_snapshot_artifact_materialized=project_benchmark_snapshot_artifact_materialized,
        project_benchmark_snapshot_artifact_record_count=project_benchmark_snapshot_artifact_record_count,
        project_benchmark_snapshot_artifact_materialized_count=project_benchmark_snapshot_artifact_materialized_count,
        project_benchmark_snapshot_artifact_all_required_materialized=project_benchmark_snapshot_artifact_all_required_materialized,
        project_benchmark_snapshot_artifact_unmaterialized_run_ids=project_benchmark_snapshot_artifact_unmaterialized_run_ids,
        project_kill_criteria=project_kill_criteria,
        project_required_followups=project_required_followups,
        end_to_end_package_ready=end_to_end_package_ready,
        architecture_materials=architecture_materials,
        case_study_materials=case_study_materials,
        failure_analysis_materials=failure_analysis_materials,
        blockers=blockers,
    )


def _build_toy_trace(project_id: str, case: dict[str, Any]) -> AutoResearchEvaluationCaseTraceRead:
    return _build_case_trace(project_id, case)


def _expected_blocked_trace_succeeded(trace: AutoResearchEvaluationCaseTraceRead | None) -> bool:
    if trace is None:
        return False
    domain_id = (
        trace.domain_decision.domain_id
        if trace.domain_decision is not None
        else None
    )
    resolver_status = (
        trace.domain_benchmark_resolver.status
        if trace.domain_benchmark_resolver is not None
        else None
    )
    protocol_status = (
        trace.domain_experiment_protocol.status
        if trace.domain_experiment_protocol is not None
        else None
    )
    return bool(
        domain_id == "unsupported"
        and trace.domain_readiness_status == "blocked"
        and resolver_status == "blocked"
        and protocol_status == "blocked"
        and trace.selected_hypothesis_id is None
        and trace.experiment_plan_id is None
        and trace.experiment_job_count == 0
        and trace.evidence_ledger_id is None
        and trace.evidence_entry_count == 0
        and trace.result_artifact_status is None
        and not trace.paper_review_package_ready
        and trace.blockers
    )


def _case_trace_succeeded(
    *,
    definition: dict[str, Any],
    trace: AutoResearchEvaluationCaseTraceRead | None,
) -> bool:
    if trace is None:
        return False
    if definition.get("expected_blocked"):
        return _expected_blocked_trace_succeeded(trace)
    if definition.get("build_project_package"):
        return bool(
            trace.result_artifact_status == "done"
            and trace.experiment_job_count > 0
            and trace.evidence_entry_count > 0
            and trace.project_publication_readiness_report_path
            and trace.project_paper_path
            and trace.project_review_bundle_ready
            and trace.project_submission_bundle_kind == "review_bundle"
            and not trace.project_final_publish_ready
            and not trace.blockers
        )
    return bool(trace.paper_review_package_ready and not trace.blockers)


def _case_has_auditable_blocker(case: AutoResearchEvaluationCaseRead) -> bool:
    return case.case_id == "unsupported_domain_case" and _expected_blocked_trace_succeeded(case.trace)


def _case_from_definition(
    *,
    definition: dict[str, Any],
    trace: AutoResearchEvaluationCaseTraceRead | None,
) -> AutoResearchEvaluationCaseRead:
    succeeded = _case_trace_succeeded(definition=definition, trace=trace)
    if trace is None:
        blockers = []
    elif succeeded:
        blockers = []
    elif definition.get("expected_blocked"):
        blockers = [
            "Expected an auditable unsupported-domain blocker with no hypothesis, plan, or execution outputs."
        ]
    else:
        blockers = trace.blockers or [
            "Evaluation case did not reach the required deterministic review/package state."
        ]
    warnings = [] if trace is not None else [
        "Case is specified for internal evaluation but not executed by the deterministic toy backend yet."
    ]
    score = 100 if succeeded else 40
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
    successful_cases = [
        case for case in cases if case.trace is not None and case.score == 100 and not case.blockers
    ]
    case_count = len(cases)
    executed_count = len(traces)
    claim_vertical_traces = [
        case.trace
        for case in cases
        if case.task_kind == "claim_evidence_vertical_task" and case.trace is not None
    ]
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
                for case in cases
                if case.trace is not None
                and (
                    (
                        case.trace.selected_hypothesis_id
                        and case.trace.hypothesis_count >= 2
                    )
                    or _case_has_auditable_blocker(case)
                )
            ),
            denominator=max(executed_count, 1),
            rationale="Supported deterministic traces must produce a selected hypothesis; unsupported-domain traces must stop with an auditable blocker before hypothesis selection.",
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
            numerator=sum(
                1
                for case in cases
                if case.trace is not None
                and (
                    (
                        case.trace.experiment_job_count > 0
                        and not case.trace.blockers
                    )
                    or _case_has_auditable_blocker(case)
                )
            ),
            denominator=max(executed_count, 1),
            rationale="Supported traces must materialize deterministic jobs; unsupported domains must block before fake experiment generation.",
        ),
        _metric(
            metric_id="evidence_consistency",
            label="Evidence Consistency",
            numerator=sum(
                1
                for case in cases
                if case.trace is not None
                and (
                    case.trace.evidence_entry_count > 0
                    or _case_has_auditable_blocker(case)
                )
            ),
            denominator=max(executed_count, 1),
            rationale=(
                "Each trace must map execution outputs back into an evidence ledger; "
                "scientific gaps remain in negative-evidence/readiness artifacts rather than "
                "being treated as pipeline failures."
            ),
        ),
        _metric(
            metric_id="reviewer_score_improvement",
            label="Reviewer Score Improvement",
            numerator=len(successful_cases),
            denominator=max(executed_count, 1),
            rationale="The deterministic suite checks that supported cases reach review/package readiness and unsupported-domain cases stop with auditable blockers.",
        ),
        _metric(
            metric_id="final_publish_correctness",
            label="Final Publish Correctness",
            numerator=sum(
                1
                for case in successful_cases
                if (
                    case.trace is not None
                    and (
                        case.trace.paper_decision == "technical_report"
                        or _case_has_auditable_blocker(case)
                    )
                )
            ),
            denominator=max(executed_count, 1),
            rationale="Offline execution cases should remain technical-report packages, while unsupported domains should produce do-not-write blockers instead of overclaiming.",
        ),
        _metric(
            metric_id="offline_end_to_end_submission_package",
            label="Offline End-to-End Submission Package",
            numerator=sum(1 for trace in claim_vertical_traces if trace.end_to_end_package_ready),
            denominator=max(len(claim_vertical_traces), 1),
            rationale="Counts traces that run idea-to-brief, cached benchmark execution, evidence ledger, project paper, revision actions, and project submission package without live services.",
        ),
    ]


def build_evaluation_case_suite(project_id: str) -> AutoResearchEvaluationCaseSuiteRead:
    traces_by_case_id = {
        str(definition["case_id"]): _build_case_trace(
            f"{project_id}_{str(definition['case_id'])}",
            definition,
        )
        for definition in _CASE_DEFINITIONS
    }
    cases = [
        _case_from_definition(
            definition=definition,
            trace=traces_by_case_id[str(definition["case_id"])],
        )
        for definition in _CASE_DEFINITIONS
    ]
    metrics = _metrics(cases)
    traces = [case.trace for case in cases if case.trace is not None]
    successful_cases = [
        case
        for case in cases
        if case.trace is not None and case.score == 100 and not case.blockers
    ]
    toy_trace = traces_by_case_id["eval_case_toy_task"]
    toy_ready = toy_trace.paper_review_package_ready and not toy_trace.blockers
    blockers = [
        f"{case.case_id}: " + "; ".join(case.blockers)
        for case in cases
        if case.blockers
    ]
    warnings = [] if len(successful_cases) == len(cases) else [
        "One or more deterministic evaluation cases did not reach the required review/package or auditable-blocker state."
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
