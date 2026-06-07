from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from schemas.autoresearch import (
    AutoResearchClaimEvidenceEntryRead,
    AutoResearchCrossRunMetaAnalysisRead,
    AutoResearchEvidenceLedgerEntryRead,
    AutoResearchPaperCompileReportRead,
    AutoResearchPaperRevisionActionEntryRead,
    AutoResearchPaperRevisionActionIndexRead,
    AutoResearchPaperSourceFileRead,
    AutoResearchPaperSourcesManifestRead,
    AutoResearchPaperTier,
    AutoResearchProjectClaimTraceRead,
    AutoResearchProjectConclusionEntryRead,
    AutoResearchProjectConclusionLedgerRead,
    AutoResearchProjectPaperDecision,
    AutoResearchProjectPaperOrchestrationRead,
    AutoResearchProjectPaperSourceStrategy,
    AutoResearchResearchBriefRead,
    AutoResearchReviewLoopActionRead,
    AutoResearchRunRead,
    LiteratureInsight,
)
from services.autoresearch.meta_analysis import build_cross_run_meta_analysis
from services.autoresearch.repository import list_research_briefs, list_runs
from services.autoresearch.research_readiness import PUBLICATION_MIN_DATASET_EXAMPLES
from services.autoresearch.writer import PaperWriter
from services.workspace import autoresearch_dir


PROJECT_PAPER_DIRNAME = "project_paper"
PROJECT_PAPER_FILENAME = "paper.md"
PROJECT_PAPER_SOURCES_DIRNAME = "paper_sources"
PROJECT_PAPER_LATEX_FILENAME = "main.tex"
PROJECT_PAPER_BIB_FILENAME = "references.bib"
PROJECT_PAPER_MANIFEST_FILENAME = "manifest.json"
PROJECT_PAPER_COMPILE_REPORT_FILENAME = "paper_compile_report.json"
PROJECT_PAPER_COMPILER_EVIDENCE_FILENAME = "paper_compiler_evidence.json"
PROJECT_PAPER_BUILD_SCRIPT_FILENAME = "build.sh"
PROJECT_PAPER_REVISION_ACTION_INDEX_FILENAME = "project_revision_action_index.json"
PROJECT_PAPER_REVISION_ACTION_NOTE_FILENAME = "revision_actions.md"
PROJECT_PAPER_REVISED_FILENAME = "paper_revised.md"
PROJECT_REVIEW_FINDINGS_FILENAME = "project_review_findings.json"
PROJECT_PAPER_REVISION_APPLICATION_FILENAME = "project_revision_application.json"
PROJECT_PAPER_REREVIEW_REPORT_FILENAME = "project_rereview_report.json"
PROJECT_SUBMISSION_DIRNAME = "submission_package"
PROJECT_SUBMISSION_MANIFEST_FILENAME = "submission_manifest.json"
PROJECT_REPRODUCIBILITY_CHECKLIST_FILENAME = "reproducibility_checklist.md"
PROJECT_REVIEWER_RESPONSE_FILENAME = "reviewer_response.md"
PROJECT_REPAIR_EXECUTION_LOG_FILENAME = "repair_execution_log.json"
PROJECT_CLAIM_EVIDENCE_INDEX_FILENAME = "claim_evidence_index.md"
PROJECT_RETRIEVAL_EVIDENCE_LEDGER_FILENAME = "retrieval_evidence_ledger.json"
PROJECT_LITERATURE_SUPPORT_INDEX_FILENAME = "literature_support_index.json"
PROJECT_LINEAGE_ARCHIVE_FILENAME = "lineage_archive.json"
PROJECT_SUPPLEMENTAL_ARTIFACTS_FILENAME = "supplemental_artifacts.json"
PROJECT_PUBLICATION_READINESS_REPORT_FILENAME = "publication_readiness_report.json"
PROJECT_PUBLICATION_EVIDENCE_INDEX_FILENAME = "publication_evidence_index.json"
PROJECT_CODE_PACKAGE_FILENAME = "code_package.zip"
PROJECT_BENCHMARK_CARD_FILENAME = "benchmark_card.json"
PROJECT_BENCHMARK_PROVENANCE_MANIFEST_FILENAME = "benchmark_provenance_manifest.json"
PROJECT_BENCHMARK_PROVENANCE_REPAIR_INDEX_FILENAME = "benchmark_provenance_repair_index.json"
PROJECT_BENCHMARK_SOURCE_INDEPENDENCE_REPAIR_FILENAME = "benchmark_source_independence_repair.json"
PROJECT_STATISTICS_REPORT_FILENAME = "statistics_report.json"
PROJECT_EXPERIMENT_REPAIR_INDEX_FILENAME = "experiment_repair_index.json"
PROJECT_NEGATIVE_EVIDENCE_REPORT_FILENAME = "negative_evidence_report.json"
PROJECT_OFFLINE_PUBLICATION_CASE_FILENAME = "offline_publication_case.json"
PROJECT_OFFLINE_PUBLICATION_AUDIT_FILENAME = "offline_publication_audit.json"
PROJECT_PUBLICATION_MANIFEST_FILENAME = "publication_manifest.json"
FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES = 100
FINAL_PUBLISH_CANDIDATE_COVERAGE_POLICY = (
    "This stricter coverage is separate from baseline publication_grade_eligible. "
    "A source can pass the base provenance gate but still fail final-publish-candidate "
    "coverage when it is fixture/toy, under 100 normalized examples, lacks materialized "
    "frozen/imported provenance, or otherwise cannot support final-publish evidence claims."
)
SCHEMA_DERIVED_CONTENT_ORIGINS = {
    "schema_derived",
    "schema_derived_template",
    "template_generated",
}
PROJECT_BENCHMARK_SCHEMA_COVERAGE_POLICY = (
    "Final-publish candidate benchmark sources must expose task-aware "
    "query/document/evidence/label/split schema instead of relying on implicit "
    "or manuscript-inferred benchmark structure."
)
PROJECT_BENCHMARK_OBSERVATION_COVERAGE_POLICY = (
    "Final-publish candidate benchmark sources must expose task-aware query, "
    "document, evidence-annotation, or retrieval-relevance observations instead of "
    "relying on manuscript-inferred benchmark counts."
)
PROJECT_COMPILER_AUDITED_TERMINAL_REPAIR_ACTION_IDS = {
    "project_benchmark_source_independence_repair",
}
GOAL1_FIXED_AUDIT_FILE_PATHS = [
    "backend/services/autoresearch/project_paper_orchestrator.py",
    "backend/services/autoresearch/evaluation_cases.py",
    "backend/services/autoresearch/experiment_factory.py",
    "backend/services/autoresearch/benchmarks.py",
    "backend/services/autoresearch/literature_scout.py",
    "backend/services/autoresearch/literature_connectors.py",
    "backend/services/autoresearch/research_readiness.py",
    "backend/services/autoresearch/review_publish.py",
    "backend/services/autoresearch/console.py",
    "backend/schemas/autoresearch.py",
    "frontend/src/api/types.ts",
    "backend/tests/test_autoresearch_regressions.py",
    "docs/api-reference.md",
    "docs/claim-evidence-vertical-loop.md",
]
GOAL1_FIXED_AUDIT_FILE_SCOPES = {
    "backend/services/autoresearch/project_paper_orchestrator.py": (
        "Builds the project package, final-publish gap audit, benchmark provenance/readiness "
        "manifests, repair-output rereview, negative evidence report, and publication manifest."
    ),
    "backend/services/autoresearch/evaluation_cases.py": (
        "Runs the deterministic fixed claim-evidence vertical with cached/imported literature, "
        "repository-local SciFact verification/retrieval frozen views, and trace proof fields."
    ),
    "backend/services/autoresearch/experiment_factory.py": (
        "Produces deterministic execution/import-replay evidence, method outputs, metrics, "
        "runtime contracts, and negative evidence categories from run artifacts."
    ),
    "backend/services/autoresearch/benchmarks.py": (
        "Preserves benchmark payload provenance into DatasetSpec and enforces source eligibility "
        "without promoting toy, fixture, under-scale, or schema-derived sources."
    ),
    "backend/services/autoresearch/literature_scout.py": (
        "Summarizes cached/imported literature evidence and keeps fixture/offline-only support "
        "from satisfying final-publish related-work claims."
    ),
    "backend/services/autoresearch/literature_connectors.py": (
        "Parses cached arXiv, Semantic Scholar, and Crossref metadata deterministically and "
        "separates real connector sources from fixture sources."
    ),
    "backend/services/autoresearch/research_readiness.py": (
        "Keeps run-level publication readiness tied to benchmark provenance, literature support, "
        "statistics, and grounded artifacts."
    ),
    "backend/services/autoresearch/review_publish.py": (
        "Keeps review/publish decisions evidence-constrained and prevents weak literature or "
        "ungrounded claims from becoming final-publish claims."
    ),
    "backend/services/autoresearch/console.py": (
        "Mirrors the project publication-case audit to operators, including benchmark schema, "
        "observation, snapshot materialization, and blocker classifications."
    ),
    "backend/schemas/autoresearch.py": (
        "Defines persisted API/read models for benchmark provenance, final-publish readiness, "
        "Phase 1/2 audit fields, and package artifact state."
    ),
    "frontend/src/api/types.ts": (
        "Mirrors backend API contract fields for benchmark provenance, final-publish candidate "
        "coverage, and publication-case audit visibility."
    ),
    "backend/tests/test_autoresearch_regressions.py": (
        "Covers deterministic adapter provenance, frozen snapshot scale/provenance, blocker "
        "visibility, and package/readiness/manifest audit propagation."
    ),
    "docs/api-reference.md": (
        "Documents API-facing publication-case, benchmark provenance, readiness, and payload-owned "
        "metadata behavior."
    ),
    "docs/claim-evidence-vertical-loop.md": (
        "Documents the claim-evidence vertical flow, remaining publication-grade gaps, and the "
        "review-ready versus final-publish distinction."
    ),
}
PROJECT_STATISTICS_REQUIRED_METRICS = [
    "mrr",
    "recall_at_1",
    "recall_at_10",
    "ndcg_at_10",
    "evidence_coverage",
    "verification_accuracy",
    "unsupported_claim_precision",
    "unsupported_claim_recall",
    "abstention_accuracy",
    "repair_precision",
    "repair_recall",
]
PROJECT_STATISTICS_RETRIEVAL_METRICS = {
    "mrr",
    "recall_at_1",
    "recall_at_10",
    "ndcg_at_10",
    "evidence_coverage",
}
PROJECT_STATISTICS_VERIFICATION_METRICS = {
    "verification_accuracy",
    "unsupported_claim_precision",
    "unsupported_claim_recall",
    "abstention_accuracy",
}
PROJECT_STATISTICS_REPAIR_METRICS = {"repair_precision", "repair_recall"}
PROJECT_NEGATIVE_EVIDENCE_REQUIRED_CATEGORIES = [
    "ledger_aware_non_improving_query",
    "unsupported_claim_false_negative",
    "unsupported_claim_false_positive",
    "retrieval_miss",
    "contradiction_refutation_ambiguity",
    "insufficient_evidence_case",
    "abstention_failure",
    "repair_router_failure",
    "failed_or_blocked_repair_attempt",
]
PROJECT_NEGATIVE_EVIDENCE_CONDITIONAL_CATEGORIES = ["runtime_failure"]
PROJECT_NEGATIVE_EVIDENCE_CATEGORY_LABELS = {
    "ledger_aware_non_improving_query": "Ledger-aware query did not improve over the comparator.",
    "unsupported_claim_false_negative": "Unsupported claim was predicted as supported.",
    "unsupported_claim_false_positive": "Supported claim was incorrectly flagged as unsupported.",
    "retrieval_miss": "Gold or required evidence was missing from retrieved support.",
    "contradiction_refutation_ambiguity": "Refutation/contradiction evidence requires careful handling.",
    "insufficient_evidence_case": "The benchmark marks the claim as not enough information.",
    "abstention_failure": "The system failed to abstain on an insufficient-evidence claim.",
    "repair_router_failure": "The repair router missed or over-routed a needed repair.",
    "failed_or_blocked_repair_attempt": "A repair attempt failed or remains blocked.",
    "blocked_repair_attempt": "A repair attempt is blocked by missing evidence or scale.",
    "failed_repair_attempt": "A materialized repair or trial failed.",
    "runtime_failure": "A failed trial records runtime or process failure evidence.",
    "claim_support_gap": "A project or manuscript claim remains unsupported or partial.",
    "project_negative_finding": "A project-level negative finding is retained.",
    "statistical_non_significance": "A deterministic comparison was not statistically significant.",
}
PROJECT_PAPER_REQUIRED_SECTIONS = [
    "Abstract",
    "Introduction",
    "Research Question",
    "Related Work",
    "Method",
    "Benchmark And Data",
    "Experimental Setup",
    "Results",
    "Analysis",
    "Negative Evidence",
    "Limitations",
    "Reproducibility",
    "Conclusion",
    "References",
]


PROJECT_SUBMISSION_PACKAGE_ROLES = [
    "project_reproducibility_checklist",
    "project_reviewer_response",
    "project_review_findings",
    "project_repair_execution_log",
    "project_claim_evidence_index",
    "project_retrieval_evidence_ledger",
    "project_lineage_archive",
    "project_literature_support_index",
    "project_paper_compiler_evidence",
    "project_publication_evidence_index",
    "project_publication_readiness_report",
    "project_supplemental_artifacts",
    "project_manuscript_markdown",
    "project_paper_sources",
    "project_revised_manuscript_markdown",
    "project_revision_application",
    "project_revision_rereview_report",
    "project_code_package",
    "project_benchmark_card",
    "project_benchmark_provenance_manifest",
    "project_benchmark_provenance_repair_index",
    "project_statistics_report",
    "project_experiment_repair_index",
    "project_negative_evidence_report",
    "project_offline_publication_case",
    "project_offline_publication_audit",
    "project_publication_manifest",
]


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str, *, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug[:72] or fallback


def _paper_tier_from_decision(decision: AutoResearchProjectPaperDecision) -> AutoResearchPaperTier:
    if decision == "conference_candidate":
        return "conference_candidate"
    if decision == "workshop_candidate":
        return "workshop_candidate"
    return "technical_report"


def _claim_evidence_refs(run: AutoResearchRunRead) -> list[str]:
    refs: list[str] = []
    if run.artifact is not None and run.artifact.status == "done":
        refs.append(f"{run.id}:artifact:{run.artifact.primary_metric}")
    if run.evidence_ledger is not None and run.evidence_ledger.entries:
        refs.extend(f"{run.id}:evidence_ledger:{item.evidence_id}" for item in run.evidence_ledger.entries[:6])
    if run.claim_evidence_matrix is not None:
        supported = [
            item
            for item in run.claim_evidence_matrix.entries
            if item.support_status in {"supported", "partial"} and item.evidence
        ]
        refs.extend(f"{run.id}:claim_matrix:{item.claim_id}" for item in supported[:6])
    if run.paper_compile_report is not None:
        strong = [
            item
            for item in run.paper_compile_report.claim_ledger
            if item.support_status in {"supported", "partial"} and item.evidence_count > 0
        ]
        refs.extend(f"{run.id}:paper_claim_ledger:{item.claim_id}" for item in strong[:6])
    return _dedupe(refs)


def _run_has_evidence(run: AutoResearchRunRead) -> bool:
    return bool(_claim_evidence_refs(run))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = " ".join(str(item).split()).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _negative_category_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return _dedupe([value])
    if not isinstance(value, list):
        return []
    return _dedupe([str(item) for item in value if item])


def _is_runtime_failure_record(record: dict[str, Any]) -> bool:
    text = " ".join(
        str(record.get(key) or "")
        for key in ("category", "scope", "summary", "detail", "diagnosis", "likely_fix")
    ).lower()
    return bool(record.get("returncode") is not None) or any(
        signal in text
        for signal in (
            "runtime",
            "returncode",
            "exception",
            "traceback",
            "timeout",
            "process",
            "crash",
        )
    )


def _phase6_category_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    entry_refs_by_category: dict[str, list[str]] = {}
    runtime_observed = False
    for entry in entries:
        categories = _negative_category_list(entry.get("phase6_categories"))
        if not categories:
            categories = _negative_category_list(entry.get("category"))
        for category in categories:
            counts[category] = counts.get(category, 0) + 1
            entry_id = str(entry.get("entry_id") or entry.get("case_id") or "")
            if entry_id:
                entry_refs_by_category.setdefault(category, [])
                if entry_id not in entry_refs_by_category[category]:
                    entry_refs_by_category[category].append(entry_id)
        runtime_observed = runtime_observed or "runtime_failure" in categories
    required = list(PROJECT_NEGATIVE_EVIDENCE_REQUIRED_CATEGORIES)
    if runtime_observed:
        required.extend(PROJECT_NEGATIVE_EVIDENCE_CONDITIONAL_CATEGORIES)
    coverage = [
        {
            "category": category,
            "label": PROJECT_NEGATIVE_EVIDENCE_CATEGORY_LABELS.get(category, category),
            "required": True,
            "covered": counts.get(category, 0) > 0,
            "entry_count": counts.get(category, 0),
            "entry_refs": entry_refs_by_category.get(category, []),
        }
        for category in required
    ]
    missing = [item["category"] for item in coverage if not item["covered"]]
    return {
        "required_categories": required,
        "conditional_categories": list(PROJECT_NEGATIVE_EVIDENCE_CONDITIONAL_CATEGORIES),
        "runtime_failure_observed": runtime_observed,
        "category_counts": dict(sorted(counts.items())),
        "entries_by_category": {
            category: entry_refs_by_category.get(category, [])
            for category in sorted(counts)
        },
        "coverage": coverage,
        "missing_categories": missing,
        "coverage_complete": not missing,
        "policy": (
            "Phase 6 negative-evidence coverage is audited from execution artifacts, "
            "diagnostics, repair records, and claim traces. Runtime failure is required only "
            "when a failed trial actually records runtime/process failure evidence."
        ),
    }


def _project_negative_evidence_phase6_entries(
    *,
    selected_runs: list[AutoResearchRunRead],
    ledger: AutoResearchProjectConclusionLedgerRead | None = None,
    traces: list[AutoResearchProjectClaimTraceRead] | None = None,
    experiment_repair_index: dict[str, Any] | None = None,
    repair_execution_log: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for run in selected_runs:
        artifact = run.artifact
        if artifact is not None:
            outputs = artifact.outputs or {}
            diagnostics = outputs.get("objective_query_diagnostics", [])
            if isinstance(diagnostics, list):
                for index, item in enumerate(diagnostics, start=1):
                    if not isinstance(item, dict):
                        continue
                    categories = _negative_category_list(
                        item.get("negative_evidence_categories")
                    )
                    if not categories:
                        continue
                    entries.append(
                        {
                            "entry_id": f"{run.id}:phase6_query:{item.get('claim_id') or index}",
                            "run_id": run.id,
                            "evidence_kind": "phase6_query_diagnostic",
                            "phase6_categories": categories,
                            "category": categories[0],
                            "subject": item.get("query") or item.get("claim_id"),
                            "reference": "run_artifact.outputs.objective_query_diagnostics",
                            "metric": "per_query_diagnostic",
                            "detail": (
                                f"Claim label={item.get('claim_label')}; predicted="
                                f"{item.get('predicted_claim_label')}; failures="
                                f"{', '.join(_negative_category_list(item.get('failure_modes')))}."
                            ),
                            "failure_modes": _negative_category_list(item.get("failure_modes")),
                            "claim_label": item.get("claim_label"),
                            "predicted_claim_label": item.get("predicted_claim_label"),
                            "artifact_ref": f"{run.id}:artifact:objective_query_diagnostics:{index}",
                            "blocks_publication": bool(
                                {
                                    "unsupported_claim_false_negative",
                                    "retrieval_miss",
                                    "abstention_failure",
                                    "repair_router_failure",
                                }
                                & set(categories)
                            ),
                        }
                    )
            comparisons = outputs.get("paired_query_comparisons", [])
            if isinstance(comparisons, list):
                for index, item in enumerate(comparisons, start=1):
                    if not isinstance(item, dict):
                        continue
                    try:
                        delta = float(item.get("delta") or 0.0)
                    except (TypeError, ValueError):
                        delta = 0.0
                    if delta > 0:
                        continue
                    entries.append(
                        {
                            "entry_id": f"{run.id}:phase6_non_improving_query:{item.get('claim_id') or index}",
                            "run_id": run.id,
                            "evidence_kind": "paired_query_comparison",
                            "phase6_categories": ["ledger_aware_non_improving_query"],
                            "category": "ledger_aware_non_improving_query",
                            "subject": item.get("claim_id"),
                            "reference": item.get("baseline") or item.get("comparator"),
                            "metric": "per_query_mrr_delta",
                            "observed_score": item.get("objective_mrr"),
                            "reference_score": item.get("comparator_mrr"),
                            "delta": delta,
                            "detail": (
                                "Ledger-aware retrieval did not improve this paired query "
                                "over the comparator."
                            ),
                            "artifact_ref": f"{run.id}:artifact:paired_query_comparisons:{index}",
                            "blocks_publication": False,
                        }
                    )
            for index, item in enumerate(artifact.negative_results, start=1):
                categories: list[str] = []
                if item.metric == "per_query_mrr_delta":
                    categories.append("ledger_aware_non_improving_query")
                if item.metric == "paired_sign_flip_exact":
                    categories.append("statistical_non_significance")
                if not categories:
                    continue
                entries.append(
                    {
                        "entry_id": f"{run.id}:phase6_negative_result:{index}",
                        "run_id": run.id,
                        "evidence_kind": "negative_result",
                        "phase6_categories": categories,
                        "category": categories[0],
                        "subject": item.subject,
                        "reference": item.reference,
                        "metric": item.metric,
                        "observed_score": item.observed_score,
                        "reference_score": item.reference_score,
                        "delta": item.delta,
                        "detail": item.detail,
                        "artifact_ref": f"{run.id}:artifact:negative_results:{index}",
                        "blocks_publication": False,
                    }
                )
            for index, item in enumerate(artifact.failed_trials, start=1):
                raw = item.model_dump(mode="json")
                categories = ["failed_repair_attempt", "failed_or_blocked_repair_attempt"]
                if _is_runtime_failure_record(raw):
                    categories.append("runtime_failure")
                entries.append(
                    {
                        "entry_id": f"{run.id}:phase6_failed_trial:{index}",
                        "run_id": run.id,
                        "evidence_kind": "failed_trial",
                        "phase6_categories": categories,
                        "category": categories[0],
                        "subject": item.sweep_label,
                        "reference": item.scope,
                        "metric": "runtime_contract",
                        "detail": item.detail,
                        "diagnosis": item.diagnosis,
                        "likely_fix": item.likely_fix,
                        "returncode": item.returncode,
                        "artifact_ref": f"{run.id}:artifact:failed_trials:{index}",
                        "blocks_publication": True,
                    }
                )
        if run.evidence_ledger is not None:
            for entry in run.evidence_ledger.entries:
                categories = [
                    category
                    for category in PROJECT_NEGATIVE_EVIDENCE_REQUIRED_CATEGORIES
                    if category in entry.claim
                ]
                if entry.support_status == "missing":
                    categories.append("retrieval_miss")
                categories = _dedupe(categories)
                if not categories:
                    continue
                entries.append(
                    {
                        "entry_id": f"{run.id}:phase6_ledger:{entry.evidence_id}",
                        "run_id": run.id,
                        "evidence_kind": "evidence_ledger_negative_signal",
                        "phase6_categories": categories,
                        "category": categories[0],
                        "subject": entry.claim,
                        "reference": entry.artifact_ref,
                        "metric": entry.metric or "claim_evidence_support",
                        "detail": entry.claim,
                        "artifact_ref": f"{run.id}:evidence_ledger:{entry.evidence_id}",
                        "blocks_publication": entry.support_status == "missing",
                    }
                )
    if ledger is not None:
        for item in ledger.negative_findings:
            entries.append(
                {
                    "entry_id": f"phase6_project_negative:{item.conclusion_id}",
                    "run_id": ",".join(item.supporting_run_ids),
                    "evidence_kind": "project_negative_finding",
                    "phase6_categories": ["project_negative_finding"],
                    "category": "project_negative_finding",
                    "subject": item.text,
                    "reference": ",".join(item.evidence_refs),
                    "metric": "project_conclusion",
                    "detail": "; ".join(item.caveats) if item.caveats else item.text,
                    "artifact_ref": f"project_conclusion_ledger:{item.conclusion_id}",
                    "blocks_publication": False,
                }
            )
    for trace in traces or []:
        if trace.support_status == "supported":
            continue
        entries.append(
            {
                "entry_id": f"phase6_trace_gap:{trace.claim_id}",
                "run_id": ",".join(trace.supporting_run_ids),
                "evidence_kind": "claim_support_gap",
                "phase6_categories": ["claim_support_gap"],
                "category": "claim_support_gap",
                "subject": trace.claim,
                "reference": trace.source_conclusion_id,
                "metric": "project_claim_support",
                "detail": "; ".join(trace.unsupported_reasons)
                if trace.unsupported_reasons
                else "Project claim is not fully supported.",
                "artifact_ref": f"project_claim_trace:{trace.claim_id}",
                "blocks_publication": trace.strong_claim or trace.support_status == "unsupported",
            }
        )
    repair_blockers = list((experiment_repair_index or {}).get("blockers", []))
    for index, blocker in enumerate(repair_blockers, start=1):
        entries.append(
            {
                "entry_id": f"phase6_experiment_repair_blocker:{index}",
                "run_id": "",
                "evidence_kind": "blocked_repair",
                "phase6_categories": [
                    "blocked_repair_attempt",
                    "failed_or_blocked_repair_attempt",
                ],
                "category": "blocked_repair_attempt",
                "subject": str(blocker),
                "reference": "experiment_repair_index",
                "metric": "repair_completion",
                "detail": str(blocker),
                "artifact_ref": "project_experiment_repair_index_json",
                "blocks_publication": True,
            }
        )
    repair_log_entries = (
        repair_execution_log.get("entries", [])
        if isinstance(repair_execution_log, dict)
        else []
    )
    if isinstance(repair_log_entries, list):
        for index, item in enumerate(repair_log_entries, start=1):
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").lower()
            if status not in {"blocked", "failed"}:
                continue
            raw_categories = (
                ["blocked_repair_attempt", "failed_or_blocked_repair_attempt"]
                if status == "blocked"
                else ["failed_repair_attempt", "failed_or_blocked_repair_attempt"]
            )
            if _is_runtime_failure_record(item):
                raw_categories.append("runtime_failure")
            categories = _dedupe(raw_categories)
            residual_blockers = [
                str(blocker)
                for blocker in item.get("residual_blockers", [])
                if blocker
            ] if isinstance(item.get("residual_blockers", []), list) else []
            detail = (
                "; ".join(residual_blockers)
                if residual_blockers
                else str(item.get("failure_classification") or item.get("terminal_condition") or "")
            )
            entries.append(
                {
                    "entry_id": (
                        "phase6_repair_execution:"
                        f"{item.get('action_id') or index}"
                    ),
                    "run_id": "",
                    "evidence_kind": "repair_execution_log_entry",
                    "phase6_categories": categories,
                    "category": categories[0],
                    "subject": item.get("title") or item.get("action_id"),
                    "reference": "project_repair_execution_log",
                    "metric": "repair_execution_status",
                    "detail": detail or f"Repair action status is {status}.",
                    "status": status,
                    "failure_classification": item.get("failure_classification"),
                    "residual_blockers": residual_blockers,
                    "artifact_ref": f"project_repair_execution_log_json:entries:{index}",
                    "blocks_publication": True,
                }
            )
    return entries


def _phase6_negative_evidence_audit_payload(
    *,
    selected_runs: list[AutoResearchRunRead],
    ledger: AutoResearchProjectConclusionLedgerRead | None = None,
    traces: list[AutoResearchProjectClaimTraceRead] | None = None,
    experiment_repair_index: dict[str, Any] | None = None,
    repair_execution_log: dict[str, Any] | None = None,
    report_ref: str = "submission_package/negative_evidence_report.json",
    include_entries: bool = False,
) -> dict[str, Any]:
    entries = _project_negative_evidence_phase6_entries(
        selected_runs=selected_runs,
        ledger=ledger,
        traces=traces,
        experiment_repair_index=experiment_repair_index,
        repair_execution_log=repair_execution_log,
    )
    summary = _phase6_category_summary(entries)
    payload = {
        "entry_count": len(entries),
        "categories": sorted(summary["category_counts"].keys()),
        "category_counts": summary["category_counts"],
        "required_categories": summary["required_categories"],
        "conditional_categories": summary["conditional_categories"],
        "category_coverage": summary["coverage"],
        "missing_categories": summary["missing_categories"],
        "coverage_complete": summary["coverage_complete"],
        "runtime_failure_observed": summary["runtime_failure_observed"],
        "negative_evidence_report_ref": report_ref,
        "policy": summary["policy"],
    }
    if include_entries:
        payload["entries"] = entries
    return payload


def _phase6_negative_evidence_report_audit(
    negative_evidence_report: dict[str, Any] | None,
    *,
    report_ref: str = "submission_package/negative_evidence_report.json",
) -> dict[str, Any]:
    report = negative_evidence_report or {}
    category_counts = report.get("phase6_category_counts", {})
    if not isinstance(category_counts, dict):
        category_counts = {}
    coverage = report.get("phase6_category_coverage", [])
    if not isinstance(coverage, list):
        coverage = []
    categories = _negative_category_list(report.get("phase6_categories"))
    required_categories = _negative_category_list(report.get("phase6_required_categories"))
    conditional_categories = _negative_category_list(report.get("phase6_conditional_categories"))
    missing_categories = _negative_category_list(report.get("phase6_missing_categories"))
    return {
        "entry_count": int(report.get("entry_count") or 0),
        "blocking_entry_count": int(report.get("blocking_entry_count") or 0),
        "categories": categories,
        "category_counts": {
            str(key): int(value)
            for key, value in category_counts.items()
            if isinstance(value, int)
        },
        "required_categories": required_categories,
        "conditional_categories": conditional_categories,
        "category_coverage": coverage,
        "missing_categories": missing_categories,
        "coverage_complete": bool(report.get("phase6_coverage_complete")),
        "runtime_failure_observed": bool(report.get("phase6_runtime_failure_observed")),
        "negative_evidence_report_ref": report_ref,
        "policy": (
            "Phase 6 taxonomy coverage is read from negative_evidence_report.json. "
            "Missing categories remain blockers or follow-ups; runtime_failure is conditional "
            "on observed runtime/process failure artifacts."
        ),
    }


def _project_paper_dir(project_id: str) -> Path:
    path = autoresearch_dir(project_id) / PROJECT_PAPER_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _project_paper_path(project_id: str) -> Path:
    return _project_paper_dir(project_id) / PROJECT_PAPER_FILENAME


def _project_paper_sources_dir(project_id: str) -> Path:
    path = _project_paper_dir(project_id) / PROJECT_PAPER_SOURCES_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _project_submission_dir(project_id: str) -> Path:
    path = _project_paper_dir(project_id) / PROJECT_SUBMISSION_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sentence(value: str | None, *, fallback: str) -> str:
    cleaned = " ".join((value or "").split()).strip()
    if not cleaned:
        return fallback
    return cleaned


def _markdown_list(items: list[str], *, empty: str) -> str:
    cleaned = _dedupe(items)
    if not cleaned:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in cleaned)


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _submission_asset_metadata(
    role: str,
    *,
    selected_run_ids: list[str] | None = None,
) -> dict[str, Any]:
    source_action_by_role = {
        "project_submission_manifest": "materialize_submission_package_v3",
        "project_reproducibility_checklist": "build_reproducibility_checklist",
        "project_reviewer_response": "build_reviewer_response",
        "project_review_findings": "run_project_reviewer_simulator",
        "project_repair_execution_log": "materialize_repair_execution_log",
        "project_claim_evidence_index": "build_claim_evidence_index",
        "project_retrieval_evidence_ledger": "build_retrieval_evidence_ledger",
        "project_lineage_archive": "build_lineage_archive",
        "project_literature_support_index": "execute_literature_refresh_repair",
        "project_paper_compiler_evidence": "compile_project_paper_evidence",
        "project_publication_evidence_index": "build_publication_evidence_index",
        "project_publication_readiness_report": "build_publication_readiness_report",
        "project_supplemental_artifacts": "materialize_supplemental_artifacts",
        "project_manuscript_markdown": "render_project_manuscript",
        "project_paper_sources": "materialize_project_paper_sources",
        "project_revised_manuscript_markdown": "apply_project_revision_actions",
        "project_revision_application": "apply_project_revision_actions",
        "project_revision_rereview_report": "rerun_project_rereview",
        "project_code_package": "materialize_code_package",
        "project_benchmark_card": "build_project_benchmark_card",
        "project_benchmark_provenance_manifest": "build_benchmark_provenance_manifest",
        "project_benchmark_provenance_repair_index": "execute_benchmark_provenance_repair",
        "project_statistics_report": "build_project_statistics_report",
        "project_experiment_repair_index": "execute_experiment_statistics_repair",
        "project_negative_evidence_report": "build_negative_evidence_report",
        "project_offline_publication_case": "define_offline_publication_case",
        "project_offline_publication_audit": "audit_offline_publication_case",
        "project_publication_manifest": "build_publication_manifest",
    }
    evidence_refs_by_role = {
        "project_literature_support_index": ["latest_project_research_brief", "project_literature_scout_json"],
        "project_paper_compiler_evidence": ["project_claim_traces", "selected_run_result_artifacts"],
        "project_publication_evidence_index": ["project_claim_traces", "project_paper_compiler_evidence_json"],
        "project_benchmark_card": ["selected_run_experiment_specs"],
        "project_benchmark_provenance_manifest": ["selected_run_experiment_specs", "project_publication_evidence_profile"],
        "project_benchmark_provenance_repair_index": ["project_benchmark_provenance_manifest_json"],
        "project_statistics_report": ["selected_run_result_artifacts", "project_paper_compiler_evidence_json"],
        "project_experiment_repair_index": ["selected_run_execution_profiles", "project_statistics_profiles"],
        "project_negative_evidence_report": ["selected_run_result_artifacts", "project_evidence_ledgers", "project_statistics_report_json"],
        "project_retrieval_evidence_ledger": ["selected_run_evidence_ledgers", "selected_run_result_artifacts"],
        "project_offline_publication_case": ["latest_project_research_brief", "selected_run_experiment_specs", "project_submission_assets"],
        "project_offline_publication_audit": ["project_offline_publication_case_json", "project_readiness_report_json", "project_submission_manifest_json"],
        "project_repair_execution_log": ["project_revision_action_index_json"],
        "project_review_findings": ["project_claim_traces", "project_publication_evidence_profile"],
        "project_publication_readiness_report": ["project_publication_evidence_index_json", "project_repair_execution_log_json"],
        "project_lineage_archive": ["selected_run_ids", "project_artifact_paths"],
        "project_claim_evidence_index": ["project_claim_traces"],
    }
    readiness_by_role = {
        "project_submission_manifest": "package_index",
        "project_reproducibility_checklist": "reproducibility",
        "project_reviewer_response": "review_bundle",
        "project_review_findings": "review_findings",
        "project_repair_execution_log": "repair_readiness",
        "project_claim_evidence_index": "claim_evidence",
        "project_retrieval_evidence_ledger": "retrieval_evidence",
        "project_lineage_archive": "artifact_lineage",
        "project_literature_support_index": "literature_coverage",
        "project_paper_compiler_evidence": "compiler_evidence",
        "project_publication_evidence_index": "claim_evidence",
        "project_publication_readiness_report": "publish_gate",
        "project_supplemental_artifacts": "supplemental_package",
        "project_manuscript_markdown": "manuscript",
        "project_paper_sources": "source_package",
        "project_revised_manuscript_markdown": "revision_loop",
        "project_revision_application": "revision_loop",
        "project_revision_rereview_report": "rereview",
        "project_code_package": "reproducibility",
        "project_benchmark_card": "benchmark_provenance",
        "project_benchmark_provenance_manifest": "benchmark_provenance",
        "project_benchmark_provenance_repair_index": "benchmark_repair",
        "project_statistics_report": "statistics_strength",
        "project_experiment_repair_index": "experiment_repair",
        "project_negative_evidence_report": "negative_evidence",
        "project_offline_publication_case": "offline_publication_case",
        "project_offline_publication_audit": "capability_audit",
        "project_publication_manifest": "publication_package",
    }
    return {
        "source_action": source_action_by_role.get(role, "materialize_project_artifact"),
        "source_run_ids": list(selected_run_ids or []),
        "source_evidence_refs": evidence_refs_by_role.get(role, []),
        "readiness_contribution": readiness_by_role.get(role, "supporting_artifact"),
    }


def _submission_asset_ref(
    role: str,
    path: Path,
    *,
    required: bool = True,
    selected_run_ids: list[str] | None = None,
) -> dict[str, Any]:
    exists = path.exists()
    missing_status = "present" if exists else "missing_required" if required else "missing_optional"
    return {
        "role": role,
        "path": str(path),
        "required": required,
        "exists": exists,
        "missing_status": missing_status,
        "kind": "directory" if path.is_dir() else "file",
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "sha256": _file_sha256(path),
        **_submission_asset_metadata(role, selected_run_ids=selected_run_ids),
    }


def _package_asset_blocking_check_ids(asset: dict[str, Any]) -> list[str]:
    contribution = str(asset.get("readiness_contribution") or "")
    role = str(asset.get("role") or "")
    checks_by_contribution = {
        "package_index": ["submission_blockers"],
        "review_bundle": ["reviewer_response"],
        "review_findings": ["revision_actions"],
        "repair_readiness": ["repair_execution_log", "revision_actions"],
        "claim_evidence": ["claim_evidence_index"],
        "retrieval_evidence": ["claim_evidence_index"],
        "literature_coverage": ["real_literature_coverage"],
        "compiler_evidence": ["paper_compiler_evidence", "execution_evidence"],
        "publish_gate": ["project_publish_gate", "submission_blockers"],
        "supplemental_package": ["submission_blockers"],
        "manuscript": ["paper_compiler_evidence"],
        "source_package": ["paper_compiler_evidence"],
        "revision_loop": ["revision_actions"],
        "rereview": ["revision_actions", "repair_execution_log"],
        "reproducibility": ["submission_blockers"],
        "benchmark_provenance": [
            "benchmark_scale",
            "benchmark_provenance",
            "benchmark_schema_coverage",
            "benchmark_source_observation_coverage",
            "benchmark_publication_grade",
            "benchmark_final_publish_candidate_coverage",
            "benchmark_source_independence",
        ],
        "benchmark_repair": [
            "benchmark_scale",
            "benchmark_provenance",
            "benchmark_schema_coverage",
            "benchmark_source_observation_coverage",
            "benchmark_publication_grade",
            "benchmark_final_publish_candidate_coverage",
            "benchmark_source_independence",
        ],
        "statistics_strength": ["paper_compiler_evidence", "execution_evidence"],
        "experiment_repair": ["repair_execution_log", "execution_evidence"],
        "negative_evidence": ["paper_compiler_evidence"],
        "offline_publication_case": ["submission_blockers"],
        "capability_audit": ["submission_blockers"],
        "publication_package": ["project_publish_gate", "submission_blockers"],
    }
    role_overrides = {
        "project_publication_readiness_report": ["project_publish_gate", "submission_blockers"],
        "project_publication_manifest": ["project_publish_gate", "submission_blockers"],
        "project_submission_manifest": ["submission_blockers"],
    }
    return _dedupe([*checks_by_contribution.get(contribution, []), *role_overrides.get(role, [])])


def _enrich_submission_asset_statuses(
    assets: list[dict[str, Any]],
    *,
    readiness_report: dict[str, Any],
    final_publish_ready: bool,
) -> list[dict[str, Any]]:
    failed_checks_by_id = {
        str(item.get("check_id")): item
        for item in readiness_report.get("checks", [])
        if isinstance(item, dict) and not item.get("passed")
    }
    enriched = []
    for asset in assets:
        blocking_check_ids = [
            check_id
            for check_id in _package_asset_blocking_check_ids(asset)
            if check_id in failed_checks_by_id
        ]
        blocking_reasons = _dedupe(
            [
                str(failed_checks_by_id[check_id].get("detail") or check_id)
                for check_id in blocking_check_ids
            ]
        )
        if asset.get("missing_status") != "present":
            blocked_status = "missing_required" if asset.get("required") else "missing_optional"
        elif final_publish_ready:
            blocked_status = "final_publish_ready"
        elif blocking_check_ids:
            blocked_status = "blocked_for_final_publish"
        else:
            blocked_status = "available_for_review"
        enriched.append(
            {
                **asset,
                "blocked_status": blocked_status,
                "final_publish_blocking": bool(blocking_check_ids) or asset.get("missing_status") != "present",
                "blocking_check_ids": blocking_check_ids,
                "blocking_reasons": blocking_reasons,
            }
        )
    return enriched


def _add_path_to_project_zip(
    handle: ZipFile,
    *,
    project_root: Path,
    path: Path,
    added: set[str],
) -> None:
    if not path.exists():
        return
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                _add_path_to_project_zip(handle, project_root=project_root, path=child, added=added)
        return
    relative = path.relative_to(project_root).as_posix() if path.is_relative_to(project_root) else path.name
    if relative in added:
        return
    added.add(relative)
    handle.write(path, relative)


def _brief_title(latest_brief: AutoResearchResearchBriefRead | None) -> str:
    if latest_brief is None:
        return "Evidence-Constrained Autonomous Research Report"
    domain = _sentence(latest_brief.domain, fallback="Autonomous Research")
    if latest_brief.selected_hypothesis_id:
        return f"Evidence-Constrained {domain} Study"
    return f"Evidence-Constrained {domain} Research Report"


def _literature_reference_lines(latest_brief: AutoResearchResearchBriefRead | None) -> list[str]:
    if latest_brief is None or latest_brief.literature_scout is None:
        return [
            "No structured literature scout is attached to the latest brief; publication requires a real literature refresh."
        ]
    refs: list[str] = []
    for paper in latest_brief.literature_scout.similar_papers[:12]:
        authors = ", ".join(paper.authors[:3]) if paper.authors else "Unknown authors"
        year = f" ({paper.year})" if paper.year is not None else ""
        venue = f", {paper.venue}" if paper.venue else ""
        identifier = paper.doi or paper.arxiv_id or paper.url or paper.paper_id
        refs.append(f"{authors}{year}. {paper.title}.{venue} Source: {paper.source}; id: {identifier}.")
    if not refs:
        refs.append("Literature scout returned no similar papers; publication requires a real literature refresh.")
    return refs


def _literature_insights(latest_brief: AutoResearchResearchBriefRead | None) -> list[LiteratureInsight]:
    if latest_brief is None or latest_brief.literature_scout is None:
        return []
    insights: list[LiteratureInsight] = []
    for paper in latest_brief.literature_scout.similar_papers[:12]:
        insight = paper.evidence or paper.abstract or "Structured literature scout metadata."
        insights.append(
            LiteratureInsight(
                paper_id=paper.paper_id,
                title=paper.title,
                year=paper.year,
                source=paper.source,
                insight=insight,
                method_hint=paper.method or ", ".join(paper.methods[:3]) or None,
                methodological_detail=", ".join(_dedupe(paper.methods + paper.datasets + paper.metrics)[:6]) or None,
                limitation=paper.known_sota,
                relevance=f"relevance_score={paper.relevance_score:.2f}; cache_status={paper.cache_status}",
            )
        )
    return insights


def _is_real_literature_paper(paper: Any) -> bool:
    return (
        getattr(paper, "source", None) not in {"fixture", "offline_project_context"}
        and getattr(paper, "cache_status", None) in {"cache_hit", "network"}
    )


def _literature_source_class(paper: Any) -> str:
    if not _is_real_literature_paper(paper):
        return "fixture_or_offline_context"
    if getattr(paper, "cache_status", None) == "network":
        return "network_real_connector"
    return "cached_real_connector"


def _project_related_system_coverage(papers: list[Any], known_sota: list[str]) -> dict[str, Any]:
    expected_systems = ["FARS", "ARIS"]
    search_records = []
    missing_systems = []
    for system in expected_systems:
        needle = system.lower()
        matched_papers = []
        for paper in papers:
            paper_text = " ".join(
                [
                    getattr(paper, "title", "") or "",
                    getattr(paper, "abstract", "") or "",
                    getattr(paper, "evidence", "") or "",
                    " ".join(getattr(paper, "methods", []) or []),
                    " ".join(getattr(paper, "datasets", []) or []),
                    " ".join(getattr(paper, "metrics", []) or []),
                    getattr(paper, "known_sota", "") or "",
                ]
            ).lower()
            if needle in paper_text:
                matched_papers.append(
                    {
                        "paper_id": getattr(paper, "paper_id", None),
                        "title": getattr(paper, "title", None),
                        "source": getattr(paper, "source", None),
                        "source_class": _literature_source_class(paper),
                        "cache_status": getattr(paper, "cache_status", None),
                    }
                )
        known_sota_mentions = [item for item in known_sota if needle in item.lower()]
        covered = bool(matched_papers or known_sota_mentions)
        if not covered:
            missing_systems.append(system)
        search_records.append(
            {
                "system": system,
                "present_in_literature": covered,
                "matched_papers": matched_papers,
                "known_sota_mentions": known_sota_mentions,
                "coverage_status": "covered" if covered else "missing",
                "limitation": (
                    None
                    if covered
                    else f"No cached/imported literature record in this support index explicitly mentions {system}."
                ),
            }
        )
    return {
        "expected_systems": expected_systems,
        "covered_systems": [
            item["system"] for item in search_records if item["present_in_literature"]
        ],
        "missing_systems": missing_systems,
        "systems": search_records,
        "complete": not missing_systems,
        "policy": (
            "Related-system coverage is read from cached/imported literature metadata and known-SOTA fields. "
            "Missing FARS/ARIS coverage is recorded as a limitation or follow-up rather than inferred."
        ),
    }


def _build_project_literature_support_index(
    *,
    project_id: str,
    latest_brief: AutoResearchResearchBriefRead | None,
    traces: list[AutoResearchProjectClaimTraceRead],
    evidence_profile: dict[str, Any],
) -> dict[str, Any]:
    scout = latest_brief.literature_scout if latest_brief is not None else None
    papers = list(scout.similar_papers) if scout is not None else []
    real_papers = [paper for paper in papers if _is_real_literature_paper(paper)]
    real_sources = sorted({paper.source for paper in real_papers})
    known_sota = list(scout.known_sota) if scout is not None else []
    related_system_coverage = _project_related_system_coverage(papers, known_sota)
    source_classes: dict[str, int] = {}
    for paper in papers:
        source_class = _literature_source_class(paper)
        source_classes[source_class] = source_classes.get(source_class, 0) + 1
    claim_support_map = []
    for trace in traces:
        matched_papers = []
        claim_terms = {
            term
            for term in re.findall(r"[a-z0-9]{4,}", trace.claim.lower())
            if term not in {"with", "that", "this", "from", "paper", "project"}
        }
        for paper in real_papers:
            paper_text = " ".join(
                [
                    paper.title,
                    paper.abstract or "",
                    paper.evidence,
                    " ".join(paper.methods),
                    " ".join(paper.datasets),
                    " ".join(paper.metrics),
                ]
            ).lower()
            overlap = sorted(term for term in claim_terms if term in paper_text)
            if overlap:
                matched_papers.append(
                    {
                        "paper_id": paper.paper_id,
                        "source": paper.source,
                        "overlap_terms": overlap[:8],
                    }
                )
        claim_support_map.append(
            {
                "claim_id": trace.claim_id,
                "support_status": trace.support_status,
                "matched_real_literature_count": len(matched_papers),
                "matched_papers": matched_papers[:8],
                "complete": bool(matched_papers) or trace.support_status != "supported",
            }
        )
    blockers = _dedupe(
        [
            *(
                ["No latest project brief with a structured literature scout is available."]
                if latest_brief is None or scout is None
                else []
            ),
            *(
                ["Literature repair requires real cached/network papers from at least two non-fixture sources."]
                if len(real_sources) < 2
                else []
            ),
            *(
                ["Literature repair still has no real cached/network papers."]
                if not real_papers
                else []
            ),
        ]
    )
    return {
        "index_id": "project_literature_support_index_v1",
        "project_id": project_id,
        "brief_id": latest_brief.brief_id if latest_brief is not None else None,
        "generated_at": _utcnow().isoformat(),
        "search_queries": list(scout.search_queries) if scout is not None else [],
        "paper_count": len(papers),
        "real_literature_count": len(real_papers),
        "real_literature_sources": real_sources,
        "source_counts": dict(scout.source_counts) if scout is not None else {},
        "source_class_counts": source_classes,
        "connector_statuses": [
            item.model_dump(mode="json")
            for item in (scout.source_statuses if scout is not None else [])
        ],
        "methods": list(scout.methods) if scout is not None else [],
        "datasets": list(scout.datasets) if scout is not None else [],
        "metrics": list(scout.metrics) if scout is not None else [],
        "known_sota": known_sota,
        "related_system_coverage": related_system_coverage,
        "papers": [
            {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "source": paper.source,
                "source_class": _literature_source_class(paper),
                "cache_status": paper.cache_status,
                "year": paper.year,
                "doi": paper.doi,
                "arxiv_id": paper.arxiv_id,
                "url": paper.url,
                "methods": list(paper.methods),
                "datasets": list(paper.datasets),
                "metrics": list(paper.metrics),
                "evidence": paper.evidence,
            }
            for paper in papers[:50]
        ],
        "claim_support_map": claim_support_map,
        "unsupported_or_weak_literature_claims": [
            {
                "claim_id": item["claim_id"],
                "support_status": item["support_status"],
                "reason": "No matched real literature record was found for this claim."
                if item["matched_real_literature_count"] == 0
                else "Claim has only partial/non-strong project support and must remain scoped.",
            }
            for item in claim_support_map
            if item["matched_real_literature_count"] == 0 or item["support_status"] != "supported"
        ],
        "complete": not blockers,
        "blockers": blockers,
        "fingerprint": _fingerprint(
            {
                "brief_id": latest_brief.brief_id if latest_brief is not None else None,
                "real_sources": real_sources,
                "paper_ids": [paper.paper_id for paper in real_papers],
                "claim_ids": [trace.claim_id for trace in traces],
            }
        ),
    }


def _benchmark_provenance_failure_classification(repair_index: dict[str, Any]) -> str | None:
    if repair_index.get("complete"):
        return None
    run_profiles = repair_index.get("run_profiles", [])
    source_classes = {str(item.get("source_class") or "") for item in run_profiles}
    blockers = " ".join(repair_index.get("blockers", [])).lower()
    if source_classes & {"toy_builtin", "cached_fixture"} or "fixture" in blockers or "toy" in blockers:
        return "non_publication_benchmark_source"
    if "fewer than" in blockers or "sample" in blockers or "scale" in blockers:
        return "insufficient_benchmark_scale"
    if "provenance" in blockers or "dataset_id" in blockers or "revision" in blockers or "license" in blockers:
        return "missing_benchmark_provenance"
    return "benchmark_provenance_not_publication_grade"


def _benchmark_query_document_evidence_schema(profile: dict[str, Any]) -> dict[str, Any]:
    input_fields = [str(item) for item in profile.get("input_fields", []) if item]
    normalized_fields = {item.lower() for item in input_fields}
    supports_claim_verification = bool(profile.get("supports_claim_verification"))
    label_space = [str(item) for item in profile.get("verification_label_space", []) if item]
    retrieval_label_space = [str(item) for item in profile.get("label_space", []) if item]

    def _matched_fields(candidates: set[str]) -> list[str]:
        return [field for field in input_fields if field.lower() in candidates]

    query_fields = _matched_fields({"claim", "query", "question", "hypothesis"})
    document_fields = _matched_fields({"document", "abstract", "title", "paragraph", "context"})
    evidence_fields = _matched_fields({"evidence", "evidence_text", "citation", "rationale", "sentences"})
    label_fields = _matched_fields({"label", "verification_label", "support_status", "stance"})
    split_fields = _matched_fields({"split", "fold"})

    inferred = False
    if not input_fields and supports_claim_verification and label_space:
        inferred = True
        query_fields = ["claim"]
        document_fields = ["document"]
        evidence_fields = ["evidence"]
        label_fields = ["verification_label"]
        split_fields = ["split"]
    elif not input_fields and not supports_claim_verification:
        inferred = True
        query_fields = ["query"]
        document_fields = ["document"]
        evidence_fields = ["relevant_ids"]
        label_fields = ["qrels"]
        split_fields = ["split"]

    verification_schema_complete = bool(
        query_fields
        and document_fields
        and evidence_fields
        and label_fields
        and label_space
        and supports_claim_verification
    )
    split_count = int(profile.get("split_count") or 0)
    retrieval_schema_complete = bool(
        query_fields and document_fields and evidence_fields and split_count >= 2
    )
    schema_complete = verification_schema_complete if supports_claim_verification else retrieval_schema_complete
    missing_roles = [
        role
        for role, fields in {
            "query": query_fields,
            "document": document_fields,
            "evidence": evidence_fields,
            "label": label_fields,
        }.items()
        if not fields
    ]
    if supports_claim_verification and not label_space:
        missing_roles.append("verification_label_space")
    if split_count < 2:
        missing_roles.append("split")

    return {
        "query_fields": query_fields,
        "document_fields": document_fields,
        "evidence_fields": evidence_fields,
        "label_fields": label_fields,
        "split_fields": split_fields,
        "label_space": label_space or retrieval_label_space,
        "verification_schema_complete": verification_schema_complete,
        "retrieval_schema_complete": retrieval_schema_complete,
        "requires_claim_verification_schema": supports_claim_verification,
        "split_count": split_count,
        "input_fields": input_fields,
        "schema_source": "dataset_input_fields"
        if input_fields
        else "claim_verification_profile"
        if inferred and supports_claim_verification
        else "retrieval_relevance_profile"
        if inferred
        else "unknown",
        "inferred_from_claim_verification_profile": inferred,
        "schema_complete": schema_complete,
        "missing_schema_roles": _dedupe(missing_roles),
    }


def _benchmark_observation_profile(run: AutoResearchRunRead) -> dict[str, Any]:
    artifact = run.artifact
    outputs = artifact.outputs if artifact is not None else {}
    diagnostics = outputs.get("objective_query_diagnostics", [])
    retrieval_ledger = outputs.get("retrieval_evidence_ledger", [])
    if not isinstance(diagnostics, list):
        diagnostics = []
    if not isinstance(retrieval_ledger, list):
        retrieval_ledger = []
    query_ids = {
        str(item.get("claim_id") or item.get("query"))
        for item in diagnostics
        if isinstance(item, dict) and (item.get("claim_id") or item.get("query"))
    }
    ranked_ids = {
        str(doc_id)
        for item in diagnostics
        if isinstance(item, dict)
        for doc_id in item.get("ranked_ids_at_10", [])
    }
    relevant_ids = {
        str(doc_id)
        for item in diagnostics
        if isinstance(item, dict)
        for doc_id in item.get("relevant_ids", [])
    }
    label_distribution: dict[str, int] = {}
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        label = str(item.get("claim_label") or "").strip()
        if not label:
            continue
        label_distribution[label] = label_distribution.get(label, 0) + 1
    ledger_status_distribution: dict[str, int] = {}
    for item in retrieval_ledger:
        if not isinstance(item, dict):
            continue
        status = str(item.get("support_status") or "unknown")
        ledger_status_distribution[status] = ledger_status_distribution.get(status, 0) + 1
    spec = run.spec
    dataset = spec.dataset if spec is not None else None
    supports_claim_verification = bool(
        dataset is not None and dataset.supports_claim_verification
    )
    train_size = dataset.train_size if dataset is not None else 0
    test_size = dataset.test_size if dataset is not None else 0
    split_distribution = {
        "train": train_size,
        "test": test_size,
    }
    return {
        "split_distribution": split_distribution,
        "label_distribution": dict(sorted(label_distribution.items())),
        "ledger_status_distribution": dict(sorted(ledger_status_distribution.items())),
        "query_count": len(query_ids) or test_size,
        "document_count": len(ranked_ids | relevant_ids),
        "evidence_annotation_count": (
            sum(
                len(item.get("relevant_ids", []))
                for item in diagnostics
                if isinstance(item, dict)
            )
            if supports_claim_verification
            else 0
        ),
        "retrieval_relevance_count": len(relevant_ids),
        "diagnostic_record_count": len([item for item in diagnostics if isinstance(item, dict)]),
        "retrieval_ledger_entry_count": len([item for item in retrieval_ledger if isinstance(item, dict)]),
    }


def _benchmark_source_record(profile: dict[str, Any]) -> dict[str, Any]:
    schema = _benchmark_query_document_evidence_schema(profile)
    dataset_id = profile.get("source_dataset_id")
    source_file_path = profile.get("source_file_path")
    source_locator = profile.get("source_url") or source_file_path
    revision = profile.get("source_revision")
    license_name = profile.get("source_license")
    fingerprint = profile.get("source_fingerprint")
    sample_count = int(profile.get("sample_count") or 0)
    split_count = int(profile.get("split_count") or 0)
    source_class = profile.get("source_class")
    eligibility = profile.get("publication_grade_eligibility", {})
    source_content_origin = str(
        profile.get("source_content_origin")
        or eligibility.get("source_content_origin")
        or ""
    ).strip()
    source_content_note = str(
        profile.get("source_content_note")
        or eligibility.get("source_content_note")
        or ""
    ).strip()
    source_parent_dataset_id = profile.get("source_parent_dataset_id") or eligibility.get(
        "source_parent_dataset_id"
    )
    source_parent_snapshot_fingerprint = profile.get(
        "source_parent_snapshot_fingerprint"
    ) or eligibility.get("source_parent_snapshot_fingerprint")
    supports_claim_verification = bool(profile.get("supports_claim_verification"))
    repository_local_snapshot_materialized = bool(
        source_file_path and Path(str(source_file_path)).is_file()
    )
    required_observation_roles = [
        "query_count",
        "document_count",
        *(
            ["evidence_annotation_count"]
            if supports_claim_verification
            else ["retrieval_relevance_count"]
        ),
    ]
    blockers = _dedupe(
        [
            *(["Missing benchmark dataset_id."] if not dataset_id else []),
            *(["Missing benchmark source locator."] if not source_locator else []),
            *(["Missing benchmark revision."] if not revision else []),
            *(["Missing benchmark license."] if not license_name else []),
            *(["Missing benchmark source fingerprint."] if not fingerprint else []),
            *(
                [
                    f"Benchmark has fewer than {PUBLICATION_MIN_DATASET_EXAMPLES} normalized examples."
                ]
                if sample_count < PUBLICATION_MIN_DATASET_EXAMPLES
                else []
            ),
            *(["Benchmark has fewer than two non-empty splits."] if split_count < 2 else []),
            *(["Benchmark query/document/evidence schema is incomplete."] if not schema["schema_complete"] else []),
            *(["Benchmark source class is missing."] if not source_class else []),
            *(
                ["Missing materialized repository-local frozen benchmark file."]
                if source_class == "frozen_snapshot" and not repository_local_snapshot_materialized
                else []
            ),
            *(
                [
                    "Benchmark content is schema-derived/template-generated and not imported from original benchmark records."
                ]
                if source_content_origin in SCHEMA_DERIVED_CONTENT_ORIGINS
                else []
            ),
            *[str(item) for item in profile.get("publication_grade_blockers", [])],
        ]
    )
    final_publish_candidate_blockers = _dedupe(
        [
            *blockers,
            *(
                [
                    f"Final-publish candidate benchmark has fewer than "
                    f"{FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES} normalized examples."
                ]
                if sample_count < FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES
                else []
            ),
            *(
                ["Final-publish candidate benchmark source is not publication-grade eligible."]
                if not bool(profile.get("publication_grade"))
                else []
            ),
            *(
                ["Final-publish candidate requires frozen/imported/remote real benchmark provenance."]
                if source_class not in {"frozen_snapshot", "imported_real", "remote_real"}
                else []
            ),
        ]
    )
    record = {
        "run_id": profile.get("run_id"),
        "benchmark_name": profile.get("benchmark_name"),
        "dataset_id": dataset_id,
        "revision": revision,
        "license": license_name,
        "source_locator": source_locator,
        "source_file_path": source_file_path,
        "repository_local_snapshot_materialized": repository_local_snapshot_materialized,
        "fingerprint": fingerprint,
        "source_content_origin": source_content_origin,
        "source_content_note": source_content_note,
        "source_parent_dataset_id": source_parent_dataset_id,
        "source_parent_snapshot_fingerprint": source_parent_snapshot_fingerprint,
        "sample_count": sample_count,
        "split_count": split_count,
        "split_distribution": dict(profile.get("split_distribution", {})),
        "label_distribution": dict(profile.get("label_distribution", {})),
        "query_count": int(profile.get("query_count") or 0),
        "document_count": int(profile.get("document_count") or 0),
        "evidence_annotation_count": int(profile.get("evidence_annotation_count") or 0),
        "retrieval_relevance_count": int(profile.get("retrieval_relevance_count") or 0),
        "ledger_status_distribution": dict(profile.get("ledger_status_distribution", {})),
        "diagnostic_record_count": int(profile.get("diagnostic_record_count") or 0),
        "retrieval_ledger_entry_count": int(profile.get("retrieval_ledger_entry_count") or 0),
        "label_space": list(profile.get("verification_label_space", []) or profile.get("label_space", [])),
        "query_document_evidence_schema": schema,
        "required_observation_roles": required_observation_roles,
        "source_class": source_class,
        "source_kind": profile.get("source_kind"),
        "supports_claim_verification": supports_claim_verification,
        "provenance_complete": bool(profile.get("provenance_complete")),
        "publication_grade": bool(profile.get("publication_grade")),
        "publication_grade_eligibility": eligibility,
        "publication_grade_blockers": list(profile.get("publication_grade_blockers", [])),
        "record_complete": not blockers,
        "publication_grade_eligible": bool(profile.get("publication_grade")) and not blockers,
        "final_publish_candidate_min_sample_count": FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES,
        "final_publish_candidate_eligible": not final_publish_candidate_blockers,
        "final_publish_candidate_blockers": final_publish_candidate_blockers,
        "record_blockers": blockers,
    }
    return {**record, "record_fingerprint": _fingerprint(record)}


def _build_project_benchmark_provenance_repair_index(
    *,
    project_id: str,
    evidence_profile: dict[str, Any],
) -> dict[str, Any]:
    run_profiles = list(evidence_profile.get("run_profiles", []))
    source_records = [_benchmark_source_record(item) for item in run_profiles]
    source_record_blockers = _dedupe(
        [
            f"{record.get('run_id', 'unknown_run')}: {blocker}"
            for record in source_records
            for blocker in record.get("record_blockers", [])
        ]
    )
    blockers = _dedupe(
        [
            *source_record_blockers,
            *[
                f"{item.get('run_id', 'unknown_run')}: {blocker}"
                for item in run_profiles
                for blocker in item.get("publication_grade_blockers", [])
            ],
            *(
                ["No selected run benchmark profiles are available for provenance repair."]
                if not run_profiles
                else []
            ),
            *(
                ["At least one selected run lacks complete benchmark provenance."]
                if run_profiles and not evidence_profile.get("benchmark_provenance_ready", False)
                else []
            ),
            *(
                ["At least one selected run benchmark is not publication-grade eligible."]
                if run_profiles and not evidence_profile.get("benchmark_publication_ready", False)
                else []
            ),
            *(
                [
                    f"At least one selected run must have >= {PUBLICATION_MIN_DATASET_EXAMPLES} normalized benchmark examples."
                ]
                if run_profiles and not evidence_profile.get("benchmark_scale_ready", False)
                else []
            ),
        ]
    )
    repaired_run_profiles = []
    for item, source_record in zip(run_profiles, source_records, strict=False):
        eligibility = item.get("publication_grade_eligibility", {})
        repaired_run_profiles.append(
            {
                "run_id": item.get("run_id"),
                "benchmark_name": item.get("benchmark_name"),
                "source_class": item.get("source_class"),
                "source_kind": item.get("source_kind"),
                "source_url": item.get("source_url"),
                "source_locator": source_record.get("source_locator"),
                "source_file_path": item.get("source_file_path"),
                "repository_local_snapshot_materialized": source_record.get(
                    "repository_local_snapshot_materialized"
                ),
                "source_dataset_id": item.get("source_dataset_id"),
                "source_revision": item.get("source_revision"),
                "source_license": item.get("source_license"),
                "source_fingerprint": item.get("source_fingerprint"),
                "source_content_origin": source_record.get("source_content_origin"),
                "source_content_note": source_record.get("source_content_note"),
                "sample_count": item.get("sample_count", 0),
                "split_count": item.get("split_count", 0),
                "supports_claim_verification": item.get("supports_claim_verification", False),
                "verification_label_space": item.get("verification_label_space", []),
                "provenance_complete": item.get("provenance_complete", False),
                "publication_grade": item.get("publication_grade", False),
                "publication_grade_eligibility": eligibility,
                "publication_grade_blockers": item.get("publication_grade_blockers", []),
                "query_document_evidence_schema": source_record["query_document_evidence_schema"],
                "source_record_complete": source_record["record_complete"],
                "source_record_blockers": source_record["record_blockers"],
                "repair_status": (
                    "eligible"
                    if item.get("provenance_complete")
                    and item.get("publication_grade")
                    and source_record["record_complete"]
                    else "blocked"
                ),
            }
        )
    payload = {
        "index_id": "project_benchmark_provenance_repair_index_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_count": len(run_profiles),
        "run_profiles": repaired_run_profiles,
        "source_records": source_records,
        "snapshot_metadata": evidence_profile.get("snapshot_metadata", {}),
        "benchmark_scale_ready": bool(evidence_profile.get("benchmark_scale_ready", False)),
        "benchmark_provenance_ready": bool(evidence_profile.get("benchmark_provenance_ready", False)),
        "benchmark_publication_ready": bool(evidence_profile.get("benchmark_publication_ready", False)),
        "complete": bool(run_profiles) and not blockers,
        "blockers": blockers,
        "policy": (
            "Benchmark provenance repair can only complete when selected runs already carry complete real, "
            "frozen, or imported benchmark provenance that passes publication eligibility. It never upgrades "
            "toy or fixture sources through metadata-only patches."
        ),
    }
    return {**payload, "repair_fingerprint": _fingerprint(payload)}


def _build_project_benchmark_source_independence_repair(
    *,
    project_id: str,
    evidence_profile: dict[str, Any],
) -> dict[str, Any]:
    run_profiles = list(evidence_profile.get("run_profiles", []))
    source_records = [_benchmark_source_record(item) for item in run_profiles]
    independence_audit = evidence_profile.get("benchmark_source_independence_audit", {})
    if not isinstance(independence_audit, dict):
        independence_audit = {}
    independent_source_keys = _dedupe(
        [
            str(
                record.get("source_parent_dataset_id")
                or record.get("dataset_id")
                or record.get("source_locator")
                or record.get("source_file_path")
                or record.get("run_id")
            )
            for record in source_records
            if record.get("run_id")
        ]
    )
    blockers = _dedupe(
        [
            *[str(item) for item in independence_audit.get("blockers", [])],
            *(
                ["No selected run benchmark profiles are available for source-independence repair."]
                if not run_profiles
                else []
            ),
            *(
                [
                    (
                        "Source-independence repair is blocked because the repository-local "
                        "evidence covers fewer than two independent external benchmark/source releases."
                    )
                ]
                if len(independent_source_keys) < 2
                else []
            ),
        ]
    )
    payload = {
        "repair_id": "project_benchmark_source_independence_repair_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "attempted_action_id": "project_benchmark_source_independence_repair",
        "selected_run_count": len(run_profiles),
        "independent_source_count": len(independent_source_keys),
        "independent_source_keys": independent_source_keys,
        "benchmark_source_independence_audit": independence_audit,
        "source_records": [
            {
                "run_id": record.get("run_id"),
                "dataset_id": record.get("dataset_id"),
                "source_parent_dataset_id": record.get("source_parent_dataset_id"),
                "source_class": record.get("source_class"),
                "source_locator": record.get("source_locator"),
                "source_file_path": record.get("source_file_path"),
                "fingerprint": record.get("fingerprint"),
                "sample_count": record.get("sample_count"),
                "publication_grade_eligible": record.get("publication_grade_eligible"),
                "final_publish_candidate_eligible": record.get(
                    "final_publish_candidate_eligible"
                ),
            }
            for record in source_records
        ],
        "candidate_import_plan": {
            "required_source_count": 2,
            "required_source_class": ["frozen_snapshot", "imported_real", "remote_real"],
            "required_provenance_fields": [
                "dataset_id",
                "revision",
                "license",
                "source_locator",
                "fingerprint",
                "sample_count",
                "split_count",
                "query_document_evidence_schema",
            ],
            "deterministic_offline_policy": (
                "This repair may only complete when an independent source release is already "
                "repository-local, cached, or imported with full provenance. It must not fetch "
                "live benchmarks or fabricate a second source."
            ),
        },
        "complete": bool(run_profiles) and not blockers,
        "blockers": blockers,
        "policy": (
            "Benchmark source-independence repair is evidence-producing only when it imports or "
            "selects an independent source release with complete provenance. Same-release views "
            "remain useful review-bundle evidence but keep final publish blocked for cross-source claims."
        ),
    }
    return {**payload, "repair_fingerprint": _fingerprint(payload)}


def _benchmark_source_independence_failure_classification(
    repair_payload: dict[str, Any],
) -> str | None:
    if repair_payload.get("complete"):
        return None
    blockers = " ".join(str(item) for item in repair_payload.get("blockers", [])).lower()
    if "fewer than two independent" in blockers or "source-independence" in blockers:
        return "benchmark_source_independence_gap"
    if "no selected run" in blockers:
        return "missing_benchmark_provenance"
    return "benchmark_source_independence_repair_blocked"


def _experiment_repair_failure_classification(
    repair_index: dict[str, Any],
    *,
    repair_kind: str,
) -> str | None:
    if repair_index.get("complete"):
        return None
    blockers = " ".join(repair_index.get("blockers", [])).lower()
    if "sample" in blockers or "scale" in blockers or "examples" in blockers:
        return "insufficient_benchmark_scale"
    if "runtime" in blockers or "materialized job" in blockers or "failed with classification" in blockers:
        return "runtime_failure"
    if "significance" in blockers or "statistics" in blockers:
        return "insufficient_statistics_outputs"
    if "artifact" in blockers or "result" in blockers:
        return "missing_result_artifact"
    return f"{repair_kind}_blocked"


def _run_experiment_execution_profile(
    run: AutoResearchRunRead,
    *,
    benchmark_profile: dict[str, Any] | None = None,
    statistics_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact = run.artifact
    environment = dict(artifact.environment) if artifact is not None else {}
    outputs = dict(artifact.outputs) if artifact is not None else {}
    materialized_jobs = list(getattr(run, "experiment_factory_materialized_jobs", []) or [])
    completed_jobs = [job for job in materialized_jobs if job.status == "done" and job.output_refs]
    failed_jobs = [job for job in materialized_jobs if job.status == "failed"]
    output_refs = _dedupe(
        [
            *(
                ["run_result_artifact_json"]
                if artifact is not None and artifact.status == "done"
                else []
            ),
            *(
                ["run_experiment_factory_materialized_jobs_json"]
                if materialized_jobs
                else []
            ),
            *(
                ["run_experiment_factory_environment_manifest_json"]
                if getattr(run, "experiment_factory_environment_manifest", None) is not None
                or environment.get("environment_manifest_id")
                else []
            ),
            *[
                str(value)
                for value in outputs.values()
                if isinstance(value, str)
                and (
                    "manifest" in value.lower()
                    or "ledger" in value.lower()
                    or "metric" in value.lower()
                    or "materialized" in value.lower()
                )
            ],
            *[
                ref
                for job in materialized_jobs
                for ref in job.output_refs
            ],
        ]
    )
    imported = bool(
        environment.get("external_imported")
        or environment.get("imported")
        or environment.get("imported_result_replay")
        or environment.get("bridge_result_imported")
        or str(environment.get("factory_executor_mode") or "").startswith("external")
    )
    has_multi_seed_or_split = bool(
        artifact is not None
        and (
            artifact.per_seed_results
            or artifact.sweep_results
            or artifact.aggregate_system_results
            or artifact.significance_tests
        )
    )
    if imported:
        execution_source = "imported_result_replay"
    elif completed_jobs:
        execution_source = "materialized_execution"
    elif has_multi_seed_or_split:
        execution_source = "persisted_multi_seed_result"
    elif artifact is not None and artifact.status == "done":
        execution_source = "persisted_result_artifact"
    else:
        execution_source = "missing_result_artifact"
    blockers = _dedupe(
        [
            *(
                ["No persisted result artifact is available for project-level experiment repair."]
                if artifact is None
                else []
            ),
            *(
                ["Persisted result artifact is not completed."]
                if artifact is not None and artifact.status != "done"
                else []
            ),
            *(
                ["No execution/import replay output refs are linked to this selected run."]
                if artifact is not None and not output_refs
                else []
            ),
            *[
                f"Materialized job {job.job_id} failed with classification {job.failure_classification}."
                for job in failed_jobs
            ],
        ]
    )
    command_or_import_paths = _dedupe(
        [
            *[
                job.command
                for job in materialized_jobs
                if job.command
            ],
            *[
                dependency
                for job in materialized_jobs
                for dependency in job.dependencies
            ],
            *[
                str(value)
                for value in outputs.values()
                if isinstance(value, str)
            ],
        ]
    )
    dependency_manifest = {
        "dependencies": _dedupe(
            [
                dependency
                for job in materialized_jobs
                for dependency in job.dependencies
            ]
        ),
        "job_dependency_count": sum(len(job.dependencies) for job in materialized_jobs),
    }
    runtime_contracts = [
        {
            "job_id": job.job_id,
            "job_kind": job.job_kind,
            "status": job.status,
            "runtime_contract": dict(job.runtime_contract),
            "expected_outputs": list(job.expected_outputs),
            "output_refs": list(job.output_refs),
        }
        for job in materialized_jobs
    ]
    metrics_artifact_refs = _dedupe(
        [
            *[
                str(value)
                for key, value in outputs.items()
                if isinstance(value, str)
                and ("metric" in key.lower() or "metric" in value.lower() or "stat" in key.lower())
            ],
            *(
                ["run_result_artifact_json"]
                if artifact is not None and artifact.status == "done"
                else []
            ),
        ]
    )
    evidence_ledger_artifact_refs = _dedupe(
        [
            *[
                str(value)
                for key, value in outputs.items()
                if isinstance(value, str)
                and ("ledger" in key.lower() or "evidence" in key.lower() or "ledger" in value.lower())
            ],
            *(
                ["run_evidence_ledger_json"]
                if getattr(run, "evidence_ledger", None) is not None
                else []
            ),
        ]
    )
    negative_evidence_artifact_refs = _dedupe(
        [
            *(
                ["run_result_artifact_json:negative_results"]
                if artifact is not None and artifact.negative_results
                else []
            ),
            *(
                ["run_result_artifact_json:failed_trials"]
                if artifact is not None and artifact.failed_trials
                else []
            ),
            *(
                ["run_result_artifact_json:objective_failure_cases"]
                if isinstance(outputs.get("objective_failure_cases"), list)
                and outputs.get("objective_failure_cases")
                else []
            ),
            *(
                ["run_result_artifact_json:objective_query_diagnostics"]
                if isinstance(outputs.get("objective_query_diagnostics"), list)
                and outputs.get("objective_query_diagnostics")
                else []
            ),
        ]
    )
    raw_method_outputs = outputs.get("method_outputs") if artifact is not None else None
    if isinstance(raw_method_outputs, dict):
        method_outputs = [
            value
            for value in raw_method_outputs.values()
            if isinstance(value, dict)
        ]
    else:
        method_outputs = (
            [
                {
                    "system": result.system,
                    "metrics": dict(result.metrics),
                    "notes": result.notes,
                }
                for result in artifact.system_results
            ]
            if artifact is not None
            else []
        )
    method_output_artifact_refs = _dedupe(
        [
            f"run_result_artifact_json:method_outputs:{item.get('system')}"
            for item in method_outputs
            if isinstance(item, dict) and item.get("system")
        ]
    )
    raw_method_configs = outputs.get("method_configs") if artifact is not None else None
    method_configs = raw_method_configs if isinstance(raw_method_configs, dict) else {}
    raw_method_ladder = outputs.get("method_ladder") if artifact is not None else None
    method_ladder = raw_method_ladder if isinstance(raw_method_ladder, list) else []
    aggregate_outputs = (
        [
            {
                "system": result.system,
                "mean_metrics": dict(result.mean_metrics),
                "sample_count": result.sample_count,
                "confidence_interval_metrics": sorted(result.confidence_intervals),
            }
            for result in artifact.aggregate_system_results
        ]
        if artifact is not None
        else []
    )
    benchmark_artifact = {
        "run_id": run.id,
        "benchmark_name": benchmark_profile.get("benchmark_name") if benchmark_profile else None,
        "dataset_id": benchmark_profile.get("source_dataset_id") if benchmark_profile else None,
        "revision": benchmark_profile.get("source_revision") if benchmark_profile else None,
        "license": benchmark_profile.get("source_license") if benchmark_profile else None,
        "source_locator": (
            benchmark_profile.get("source_url") or benchmark_profile.get("source_file_path")
            if benchmark_profile
            else None
        ),
        "fingerprint": benchmark_profile.get("source_fingerprint") if benchmark_profile else None,
        "source_content_origin": (
            benchmark_profile.get("source_content_origin") if benchmark_profile else None
        ),
        "source_content_note": (
            benchmark_profile.get("source_content_note") if benchmark_profile else None
        ),
        "sample_count": benchmark_profile.get("sample_count") if benchmark_profile else None,
        "split_count": benchmark_profile.get("split_count") if benchmark_profile else None,
        "source_class": benchmark_profile.get("source_class") if benchmark_profile else None,
        "label_space": benchmark_profile.get("verification_label_space") if benchmark_profile else [],
        "publication_grade": benchmark_profile.get("publication_grade") if benchmark_profile else False,
        "publication_grade_blockers": (
            benchmark_profile.get("publication_grade_blockers") if benchmark_profile else []
        ),
    }
    execution_evidence = {
        "evidence_id": f"{run.id}:execution_evidence_v1",
        "run_id": run.id,
        "execution_source": execution_source,
        "executor_mode": environment.get("factory_executor_mode") or environment.get("executor_mode"),
        "backend": environment.get("backend"),
        "command_or_import_paths": command_or_import_paths,
        "runtime_contracts": runtime_contracts,
        "environment_manifest": {
            "artifact_ref": (
                "run_experiment_factory_environment_manifest_json"
                if getattr(run, "experiment_factory_environment_manifest", None) is not None
                or environment.get("environment_manifest_id")
                else None
            ),
            "manifest_id": environment.get("environment_manifest_id"),
            "fingerprint": environment.get("environment_manifest_fingerprint"),
            "executor_mode": environment.get("factory_executor_mode") or environment.get("executor_mode"),
            "backend": environment.get("backend"),
        },
        "dependency_manifest": dependency_manifest,
        "input_benchmark_artifact": benchmark_artifact,
        "method_outputs": method_outputs,
        "method_output_artifact_refs": method_output_artifact_refs,
        "method_configs": method_configs,
        "method_ladder": method_ladder,
        "aggregate_outputs": aggregate_outputs,
        "metrics_artifact_refs": metrics_artifact_refs,
        "evidence_ledger_artifact_refs": evidence_ledger_artifact_refs,
        "negative_evidence_artifact_refs": negative_evidence_artifact_refs,
        "repair_action_linkage": [
            "project_benchmark_scale_repair",
            "project_insufficient_statistics_repair",
        ],
        "failure_classifications": _dedupe(
            [
                job.failure_classification
                for job in failed_jobs
                if job.failure_classification and job.failure_classification != "none"
            ]
        ),
        "statistics_profile": statistics_profile or {},
        "complete": bool(artifact is not None and artifact.status == "done" and output_refs and not failed_jobs),
        "blockers": blockers,
    }
    execution_evidence = {
        **execution_evidence,
        "deterministic_fingerprint": _fingerprint(execution_evidence),
    }
    return {
        "run_id": run.id,
        "execution_source": execution_source,
        "executor_mode": environment.get("factory_executor_mode") or environment.get("executor_mode"),
        "backend": environment.get("backend"),
        "imported_result_replay": imported,
        "materialized_job_count": len(materialized_jobs),
        "completed_materialized_job_count": len(completed_jobs),
        "failed_materialized_job_count": len(failed_jobs),
        "environment_manifest_id": environment.get("environment_manifest_id"),
        "environment_manifest_fingerprint": environment.get("environment_manifest_fingerprint"),
        "seed_count": (
            (environment.get("seed_count") or len(artifact.per_seed_results))
            if artifact is not None
            else 0
        ),
        "output_artifact_refs": output_refs,
        "failure_classifications": _dedupe(
            [
                job.failure_classification
                for job in failed_jobs
                if job.failure_classification and job.failure_classification != "none"
            ]
        ),
        "execution_evidence": execution_evidence,
        "complete": bool(artifact is not None and artifact.status == "done" and output_refs and not failed_jobs),
        "blockers": blockers,
    }


def _build_project_experiment_repair_index(
    *,
    project_id: str,
    evidence_profile: dict[str, Any],
    statistics_profiles: list[dict[str, Any]],
    selected_runs: list[AutoResearchRunRead] | None = None,
) -> dict[str, Any]:
    benchmark_profiles_by_run_id = {
        str(item.get("run_id")): item for item in evidence_profile.get("run_profiles", [])
    }
    statistics_profiles_by_run_id = {
        str(item.get("run_id")): item for item in statistics_profiles
    }
    execution_profiles = [
        _run_experiment_execution_profile(
            run,
            benchmark_profile=benchmark_profiles_by_run_id.get(run.id),
            statistics_profile=statistics_profiles_by_run_id.get(run.id),
        )
        for run in selected_runs or []
    ]
    runs_with_execution_outputs = [item for item in execution_profiles if item["complete"]]
    imported_replay_runs = [item for item in execution_profiles if item["imported_result_replay"]]
    materialized_runs = [
        item
        for item in execution_profiles
        if int(item.get("completed_materialized_job_count") or 0) > 0
    ]
    scaled_runs = [
        item
        for item in evidence_profile.get("run_profiles", [])
        if int(item.get("sample_count") or 0) >= PUBLICATION_MIN_DATASET_EXAMPLES
        and bool(item.get("publication_grade"))
    ]
    runs_with_statistics = [item for item in statistics_profiles if item.get("has_statistics")]
    runs_with_significance = [
        item for item in statistics_profiles if int(item.get("significance_test_count") or 0) > 0
    ]
    blockers = _dedupe(
        [
            *(
                [
                    f"No selected run uses a publication-eligible benchmark with at least {PUBLICATION_MIN_DATASET_EXAMPLES} normalized examples."
                ]
                if not scaled_runs
                else []
            ),
            *(
                ["No selected run result artifact includes deterministic aggregate/seed/split statistics."]
                if not runs_with_statistics
                else []
            ),
            *(
                ["No selected run result artifact includes a deterministic paired/significance comparison."]
                if not runs_with_significance
                else []
            ),
            *(
                ["No selected run links deterministic execution, materialized job, or imported replay outputs."]
                if selected_runs is not None and not runs_with_execution_outputs
                else []
            ),
            *[
                blocker
                for profile in execution_profiles
                for blocker in profile.get("blockers", [])
            ],
        ]
    )
    payload = {
        "index_id": "project_experiment_repair_index_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_count": len(evidence_profile.get("run_profiles", [])),
        "benchmark_scale_ready": bool(evidence_profile.get("benchmark_scale_ready", False)),
        "scaled_publication_run_ids": [item.get("run_id") for item in scaled_runs],
        "statistics_ready": bool(runs_with_statistics and runs_with_significance),
        "execution_coverage_ready": bool(
            runs_with_execution_outputs if selected_runs is not None else True
        ),
        "execution_profiles": execution_profiles,
        "execution_source_counts": {
            source: sum(1 for item in execution_profiles if item["execution_source"] == source)
            for source in sorted({item["execution_source"] for item in execution_profiles})
        },
        "imported_result_replay_run_ids": [item["run_id"] for item in imported_replay_runs],
        "materialized_execution_run_ids": [item["run_id"] for item in materialized_runs],
        "execution_evidence_ledger": {
            "ledger_id": "project_experiment_execution_evidence_ledger_v1",
            "project_id": project_id,
            "selected_run_ids": [run.id for run in selected_runs or []],
            "entry_count": len(execution_profiles),
            "complete_entry_count": sum(1 for item in execution_profiles if item.get("complete")),
            "entries": [item["execution_evidence"] for item in execution_profiles],
            "policy": (
                "Execution evidence is imported from selected run artifacts, materialized jobs, "
                "environment manifests, benchmark provenance, metrics outputs, evidence ledgers, "
                "and negative-evidence outputs. The project repair index does not fabricate "
                "execution results or upgrade missing outputs."
            ),
        },
        "execution_output_artifact_refs": _dedupe(
            [
                ref
                for profile in execution_profiles
                for ref in profile.get("output_artifact_refs", [])
            ]
        ),
        "run_statistics_profiles": statistics_profiles,
        "run_benchmark_profiles": evidence_profile.get("run_profiles", []),
        "repair_routes": {
            "project_benchmark_scale_repair": {
                "complete": bool(scaled_runs)
                and (selected_runs is None or bool(runs_with_execution_outputs)),
                "expected_outputs": [
                    "project_benchmark_provenance_manifest_json",
                    "project_statistics_report_json",
                    "run_result_artifact_json",
                    "run_experiment_factory_materialized_jobs_json",
                    "project_publication_readiness_report_json",
                ],
                "terminal_condition": (
                    "At least one selected run uses a publication-eligible benchmark with the required sample count and linked execution/import replay outputs."
                ),
            },
            "project_insufficient_statistics_repair": {
                "complete": bool(runs_with_statistics and runs_with_significance)
                and (selected_runs is None or bool(runs_with_execution_outputs)),
                "expected_outputs": [
                    "project_statistics_report_json",
                    "project_paper_compiler_evidence_json",
                    "run_result_artifact_json",
                    "run_experiment_factory_materialized_jobs_json",
                    "project_publication_readiness_report_json",
                ],
                "terminal_condition": (
                    "Project statistics report includes deterministic aggregate statistics, at least one paired/significance comparison, and linked execution/import replay outputs."
                ),
            },
        },
        "complete": not blockers,
        "blockers": blockers,
        "policy": (
            "Experiment/statistics repair completes only from persisted run artifacts, benchmark profiles, "
            "linked execution/import replay outputs, and deterministic statistics/significance outputs. It does not synthesize stronger experimental evidence."
        ),
    }
    return {**payload, "repair_fingerprint": _fingerprint(payload)}


def _project_execution_coverage(
    *,
    selected_runs: list[AutoResearchRunRead],
    evidence_profile: dict[str, Any],
    statistics_profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    benchmark_profiles_by_run_id = {
        str(item.get("run_id")): item for item in evidence_profile.get("run_profiles", [])
    }
    statistics_profiles_by_run_id = {
        str(item.get("run_id")): item for item in statistics_profiles
    }
    execution_profiles = [
        _run_experiment_execution_profile(
            run,
            benchmark_profile=benchmark_profiles_by_run_id.get(run.id),
            statistics_profile=statistics_profiles_by_run_id.get(run.id),
        )
        for run in selected_runs
    ]
    complete_profiles = [item for item in execution_profiles if item.get("complete")]
    source_counts = {
        source: sum(1 for item in execution_profiles if item["execution_source"] == source)
        for source in sorted({item["execution_source"] for item in execution_profiles})
    }
    output_refs = _dedupe(
        [
            ref
            for profile in execution_profiles
            for ref in profile.get("output_artifact_refs", [])
        ]
    )
    metrics_refs = _dedupe(
        [
            ref
            for profile in execution_profiles
            for ref in profile.get("execution_evidence", {}).get("metrics_artifact_refs", [])
        ]
    )
    evidence_refs = _dedupe(
        [
            ref
            for profile in execution_profiles
            for ref in profile.get("execution_evidence", {}).get("evidence_ledger_artifact_refs", [])
        ]
    )
    negative_refs = _dedupe(
        [
            ref
            for profile in execution_profiles
            for ref in profile.get("execution_evidence", {}).get("negative_evidence_artifact_refs", [])
        ]
    )
    blockers = _dedupe(
        [
            *(
                ["No selected run has linked deterministic execution/import replay outputs."]
                if selected_runs and not complete_profiles
                else []
            ),
            *[
                f"{profile.get('run_id', 'unknown_run')}: {blocker}"
                for profile in execution_profiles
                for blocker in profile.get("blockers", [])
            ],
        ]
    )
    payload = {
        "selected_run_count": len(selected_runs),
        "execution_profile_count": len(execution_profiles),
        "complete_execution_profile_count": len(complete_profiles),
        "execution_source_counts": source_counts,
        "imported_result_replay_run_ids": [
            item["run_id"] for item in execution_profiles if item.get("imported_result_replay")
        ],
        "materialized_execution_run_ids": [
            item["run_id"]
            for item in execution_profiles
            if int(item.get("completed_materialized_job_count") or 0) > 0
        ],
        "execution_output_artifact_refs": output_refs,
        "metrics_artifact_refs": metrics_refs,
        "evidence_ledger_artifact_refs": evidence_refs,
        "negative_evidence_artifact_refs": negative_refs,
        "execution_profiles": execution_profiles,
        "execution_evidence_ledger": {
            "ledger_id": "project_compiler_execution_evidence_coverage_v1",
            "entry_count": len(execution_profiles),
            "complete_entry_count": len(complete_profiles),
            "entries": [item["execution_evidence"] for item in execution_profiles],
        },
        "complete": bool(selected_runs) and len(complete_profiles) == len(selected_runs),
        "blockers": blockers,
    }
    return {**payload, "coverage_fingerprint": _fingerprint(payload)}


def _run_metric_line(run: AutoResearchRunRead) -> str:
    if run.artifact is None:
        return f"{run.id}: completed without a persisted result artifact."
    metric = run.artifact.primary_metric or "primary metric"
    score = run.artifact.objective_score
    score_text = f"{score:.4f}" if isinstance(score, (int, float)) else "n/a"
    system = run.artifact.objective_system or "candidate system"
    return f"{run.id}: {system} reached {score_text} on {metric}."


def _conclusion_lines(items: list[AutoResearchProjectConclusionEntryRead]) -> list[str]:
    lines: list[str] = []
    for item in items:
        refs = ", ".join(item.evidence_refs) if item.evidence_refs else "no attached evidence refs"
        caveats = f" Caveats: {'; '.join(item.caveats)}" if item.caveats else ""
        lines.append(f"{item.conclusion_id}: {item.text} Evidence: {refs}.{caveats}")
    return lines


def _render_project_paper_markdown(
    *,
    project_id: str,
    latest_brief: AutoResearchResearchBriefRead | None,
    selected_runs: list[AutoResearchRunRead],
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    paper_decision: AutoResearchProjectPaperDecision,
    source_strategy: AutoResearchProjectPaperSourceStrategy,
    should_write_paper: bool,
    project_level_paper_allowed: bool,
    blockers: list[str],
    warnings: list[str],
    next_actions: list[str],
    reviewer_count: int,
    reviewer_average_score: float,
) -> str:
    title = _brief_title(latest_brief)
    idea = _sentence(
        latest_brief.polished_idea if latest_brief is not None else None,
        fallback="No polished project idea is attached to this report.",
    )
    questions = latest_brief.research_questions if latest_brief is not None else []
    hypotheses = latest_brief.candidate_hypotheses if latest_brief is not None else []
    datasets = latest_brief.candidate_datasets if latest_brief is not None else []
    metrics = latest_brief.candidate_metrics if latest_brief is not None else []
    baselines = latest_brief.candidate_baselines if latest_brief is not None else []
    scout = latest_brief.literature_scout if latest_brief is not None else None
    scout_status = (
        "No literature scout is attached."
        if scout is None
        else (
            f"Literature scout indexed {len(scout.similar_papers)} paper(s), "
            f"{scout.cache_hit_count} cache hit(s), network_enabled={scout.network_enabled}."
        )
    )
    supported_traces = [trace for trace in traces if trace.support_status == "supported"]
    unsupported_traces = [trace for trace in traces if trace.support_status == "unsupported"]
    stable = _conclusion_lines(ledger.stable_conclusions)
    conditional = _conclusion_lines(ledger.conditional_conclusions)
    negative = _conclusion_lines(ledger.negative_findings)
    failed = _conclusion_lines(ledger.failed_hypotheses)
    limitations = _conclusion_lines(ledger.limitations)
    trace_lines = [
        (
            f"{trace.claim_id}: {trace.support_status}. {trace.claim} "
            f"Evidence refs: {', '.join(trace.evidence_refs) if trace.evidence_refs else 'none'}."
        )
        for trace in traces
    ]
    phase6_negative_entries = _project_negative_evidence_phase6_entries(
        selected_runs=selected_runs,
        ledger=ledger,
        traces=traces,
    )
    phase6_negative_summary = _phase6_category_summary(phase6_negative_entries)
    phase6_category_lines = [
        (
            f"{item['category']}: covered={item['covered']}; "
            f"entry_count={item['entry_count']}"
        )
        for item in phase6_negative_summary["coverage"]
    ]
    run_lines = [_run_metric_line(run) for run in selected_runs]
    all_limitations = limitations + blockers + warnings
    if phase6_negative_summary["missing_categories"]:
        all_limitations.append(
            "Phase 6 negative evidence categories still missing deterministic artifacts: "
            + ", ".join(phase6_negative_summary["missing_categories"])
            + "."
        )
    if not project_level_paper_allowed:
        all_limitations.append("Current evidence does not permit a project-level paper claim.")
    if not should_write_paper:
        all_limitations.append("The manuscript remains a blocked draft/report until blockers are resolved.")

    sections = [
        f"# {title}",
        "",
        "## Abstract",
        (
            f"This report describes project `{project_id}` under a {paper_decision} decision and "
            f"{source_strategy} source strategy. The system evaluates the idea `{idea}` through "
            f"{len(selected_runs)} selected run(s), a project conclusion ledger, and "
            f"{len(supported_traces)}/{len(traces)} supported core claim trace(s). "
            "Claims are constrained to attached run artifacts, claim matrices, and evidence ledgers."
        ),
        "",
        "## Introduction",
        f"The starting research idea is: {idea}",
        "",
        "## Research Question",
        "Research questions:",
        _markdown_list(questions, empty="No research questions were persisted in the latest brief."),
        "",
        "Candidate hypotheses:",
        _markdown_list(hypotheses, empty="No candidate hypotheses were persisted in the latest brief."),
        "",
        "Selected direction:",
        _markdown_list(
            [
                f"selected_hypothesis_id={latest_brief.selected_hypothesis_id}"
                if latest_brief is not None and latest_brief.selected_hypothesis_id
                else "No selected hypothesis id is persisted.",
                f"selection_reason={latest_brief.selection_reason}"
                if latest_brief is not None and latest_brief.selection_reason
                else "No selection reason is persisted.",
            ],
            empty="No selected direction was persisted.",
        ),
        "",
        "## Related Work",
        scout_status,
        "",
        _markdown_list(_literature_reference_lines(latest_brief), empty="No related-work entries available."),
        "",
        "## Method",
        (
            "ScholarFlow uses evidence-constrained automation: selected hypotheses become experiment runs; "
            "runs materialize artifacts, claim-evidence matrices, evidence ledgers, repair plans, reviewer "
            "signals, and project-level conclusion ledgers before manuscript claims are promoted."
        ),
        "",
        "Core claim traces:",
        _markdown_list(trace_lines, empty="No project claim traces were generated."),
        "",
        "## Benchmark And Data",
        f"Selected runs: {', '.join(run.id for run in selected_runs) if selected_runs else 'none'}",
        "",
        "Datasets:",
        _markdown_list(datasets, empty="No candidate datasets were persisted in the latest brief."),
        "",
        "Benchmark provenance summary:",
        _markdown_list(
            [
                (
                    f"{run.id}: benchmark={run.benchmark.name if run.benchmark is not None else 'none'}; "
                    f"dataset_id={run.benchmark.dataset_id if run.benchmark is not None else 'none'}; "
                    f"source={run.benchmark.url if run.benchmark is not None else 'none'}"
                )
                for run in selected_runs
            ],
            empty="No selected run benchmark provenance is available.",
        ),
        "",
        "## Experimental Setup",
        "Metrics:",
        _markdown_list(metrics, empty="No candidate metrics were persisted in the latest brief."),
        "",
        "Baselines:",
        _markdown_list(baselines, empty="No candidate baselines were persisted in the latest brief."),
        "",
        "Run outcomes:",
        _markdown_list(run_lines, empty="No completed selected run outcomes are available."),
        "",
        "## Results",
        "Stable conclusions:",
        _markdown_list(stable, empty="No stable project-level conclusions are available."),
        "",
        "Conditional conclusions:",
        _markdown_list(conditional, empty="No conditional project conclusions are available."),
        "",
        "## Analysis",
        (
            f"The current manuscript has {len(supported_traces)} supported, "
            f"{len([trace for trace in traces if trace.support_status == 'partial'])} partial, and "
            f"{len(unsupported_traces)} unsupported project claim trace(s). Reviewer simulation coverage is "
            f"{reviewer_count} run(s), with average score {reviewer_average_score:.2f}."
        ),
        "",
        "Project publish gate:",
        _markdown_list(
            [
                f"should_write_paper={should_write_paper}",
                f"project_level_paper_allowed={project_level_paper_allowed}",
                f"paper_decision={paper_decision}",
                f"source_strategy={source_strategy}",
            ],
            empty="No publish-gate status available.",
        ),
        "",
        "## Negative Evidence",
        "Negative findings, failed hypotheses, retrieval misses, and blocked repairs are kept in the manuscript so claims cannot silently outgrow the evidence.",
        "",
        "Negative and failed findings:",
        _markdown_list(negative + failed, empty="No negative findings or failed hypotheses are attached."),
        "",
        "Unsupported or partial claim traces:",
        _markdown_list(
            [
                (
                    f"{trace.claim_id}: {trace.support_status}. "
                    f"Reasons: {'; '.join(trace.unsupported_reasons) if trace.unsupported_reasons else 'no explicit reason'}."
                )
                for trace in traces
                if trace.support_status != "supported"
            ],
            empty="No unsupported or partial claim traces are attached.",
        ),
        "",
        "Phase 6 negative evidence categories:",
        _markdown_list(
            phase6_category_lines,
            empty="No Phase 6 negative-evidence categories were observed in deterministic artifacts.",
        ),
        "",
        "Phase 6 missing negative evidence categories:",
        _markdown_list(
            [
                (
                    f"{category}: "
                    f"{PROJECT_NEGATIVE_EVIDENCE_CATEGORY_LABELS.get(category, category)}"
                )
                for category in phase6_negative_summary["missing_categories"]
            ],
            empty="All currently required Phase 6 negative-evidence categories are covered.",
        ),
        "",
        "## Limitations",
        _markdown_list(all_limitations, empty="No blockers, warnings, or limitations were generated."),
        "",
        "Required next actions:",
        _markdown_list(next_actions, empty="No next actions were generated."),
        "",
        "## Reproducibility",
        "The project package records all available source and evidence artifacts for re-review and follow-up execution.",
        "",
        "Reproducibility assets:",
        _markdown_list(
            [
                "project manuscript markdown",
                "project paper sources and compile report",
                "claim-evidence index",
                "lineage archive",
                "benchmark card and provenance manifest",
                "statistics report",
                "repair execution log",
                "publication readiness report",
                "code package",
            ],
            empty="No reproducibility assets are declared.",
        ),
        "",
        "Artifact evidence map:",
        _markdown_list(
            [
                "literature support and gap evidence: submission_package/literature_support_index.json",
                "benchmark source, schema, and eligibility evidence: submission_package/benchmark_card.json; submission_package/benchmark_provenance_manifest.json; submission_package/benchmark_provenance_repair_index.json",
                "execution/import replay and statistics evidence: submission_package/experiment_repair_index.json; submission_package/statistics_report.json",
                "claim and retrieval evidence: submission_package/claim_evidence_index.md; submission_package/retrieval_evidence_ledger.json; paper_sources/paper_compiler_evidence.json",
                "negative evidence: submission_package/negative_evidence_report.json",
                "review, repair, and rereview evidence: submission_package/project_review_findings.json; submission_package/repair_execution_log.json; paper_sources/project_revision_action_index.json; paper_sources/project_rereview_report.json",
                "package lineage and readiness evidence: submission_package/lineage_archive.json; submission_package/publication_readiness_report.json; submission_package/publication_manifest.json",
            ],
            empty="No artifact evidence map is declared.",
        ),
        "",
        "## Conclusion",
        (
            "The project can be reported only at the strength allowed by the conclusion ledger and claim traces. "
            "Single-run or partial retrieval evidence is preserved as conditional evidence, while missing support "
            "remains a repair target before submission packaging."
        ),
        "",
        "## References",
        _markdown_list(_literature_reference_lines(latest_brief), empty="No references available."),
        "",
    ]
    return "\n".join(sections).strip() + "\n"


def _project_paper_section_status(markdown: str) -> tuple[list[str], list[str]]:
    present = []
    for section in PROJECT_PAPER_REQUIRED_SECTIONS:
        if f"## {section}" in markdown:
            present.append(section)
    missing = [section for section in PROJECT_PAPER_REQUIRED_SECTIONS if section not in present]
    return present, missing


def _project_revision_action(
    *,
    action_id: str,
    action_kind: str,
    repair_kind: str | None,
    execution_route: str,
    priority: str,
    title: str,
    detail: str,
    issue_ids: list[str],
    expected_outputs: list[str],
    terminal_condition: str,
) -> AutoResearchReviewLoopActionRead:
    return AutoResearchReviewLoopActionRead(
        action_id=action_id,
        action_kind=action_kind,  # type: ignore[arg-type]
        repair_kind=repair_kind,  # type: ignore[arg-type]
        execution_route=execution_route,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        title=title,
        detail=detail,
        status="pending",
        first_seen_round=1,
        last_seen_round=1,
        issue_ids=_dedupe(issue_ids),
        auto_applicable=True,
        expected_output_asset_ids=expected_outputs,
        terminal_condition=terminal_condition,
        requires_rereview=True,
        max_auto_rounds=3,
    )


def _build_project_revision_actions(
    *,
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    evidence_profile: dict[str, Any] | None = None,
    statistics_profiles: list[dict[str, Any]] | None = None,
) -> list[AutoResearchReviewLoopActionRead]:
    actions: dict[str, AutoResearchReviewLoopActionRead] = {}
    common_outputs = [
        "project_paper_markdown",
        "project_paper_revision_action_index_json",
        "project_paper_compile_report_json",
        "project_paper_sources_manifest_json",
    ]

    def add(action: AutoResearchReviewLoopActionRead) -> None:
        existing = actions.get(action.action_id)
        if existing is None:
            actions[action.action_id] = action
            return
        actions[action.action_id] = existing.model_copy(
            update={
                "issue_ids": _dedupe(existing.issue_ids + action.issue_ids),
                "expected_output_asset_ids": _dedupe(
                    existing.expected_output_asset_ids + action.expected_output_asset_ids
                ),
            }
        )

    for trace in traces:
        if trace.support_status == "supported":
            continue
        priority = "high" if trace.strong_claim or trace.support_status == "unsupported" else "medium"
        title = (
            "Downgrade unsupported project claim"
            if trace.support_status == "unsupported"
            else "Downgrade partially supported project claim"
        )
        add(
            _project_revision_action(
                action_id=f"project_claim_downgrade_{_slug(trace.claim_id)}",
                action_kind="claim_downgrade",
                repair_kind="repair_claim_evidence",
                execution_route="paper_rebuild",
                priority=priority,
                title=title,
                detail=(
                    f"Claim `{trace.claim_id}` is {trace.support_status}: {trace.claim} "
                    "Revise the manuscript so it is framed as a limitation, conditional finding, or required follow-up "
                    "unless stronger evidence is attached."
                ),
                issue_ids=[trace.source_conclusion_id],
                expected_outputs=common_outputs,
                terminal_condition=(
                    "The project manuscript no longer presents this unsupported or partial trace as a strong claim, "
                    "and a later project-paper review no longer reports the same support issue."
                ),
            )
        )

    for limitation in ledger.limitations:
        missing_refs = [
            ref for ref in limitation.evidence_refs if "evidence_retrieval_" in ref
        ]
        if not missing_refs:
            continue
        add(
            _project_revision_action(
                action_id=f"project_retrieval_repair_{_slug(limitation.conclusion_id)}",
                action_kind="claim_downgrade",
                repair_kind="repair_claim_evidence",
                execution_route="paper_rebuild",
                priority="high",
                title="Route missing retrieval evidence to claim repair",
                detail=(
                    f"{limitation.text} Repair by refreshing retrieval evidence, downgrading the affected claim, "
                    "or moving it to limitations until the retrieval ledger has support."
                ),
                issue_ids=[limitation.conclusion_id],
                expected_outputs=[
                    *common_outputs,
                    "project_retrieval_evidence_ledger",
                ],
                terminal_condition=(
                    "Missing retrieval-ledger refs are either supported by refreshed evidence or the affected claim is "
                    "downgraded in the manuscript and retained as a limitation."
                ),
            )
        )

    profile = evidence_profile or {}
    if profile and not profile.get("literature_ready", False):
        add(
            _project_revision_action(
                action_id="project_literature_refresh_multi_source",
                action_kind="literature_refresh",
                repair_kind="refresh_literature",
                execution_route="literature_refresh",
                priority="high",
                title="Refresh weak project literature support",
                detail=(
                    "Project-level readiness lacks multi-source real cached or network-sourced literature evidence. "
                    "Refresh arXiv, Semantic Scholar, and Crossref literature scout results, then update related work "
                    "and claim limitations without promoting unsupported claims."
                ),
                issue_ids=["project_literature_coverage"],
                expected_outputs=[
                    *common_outputs,
                    "project_literature_scout_json",
                    "project_related_work_section",
                    "project_publication_readiness_report_json",
                ],
                terminal_condition=(
                    "The latest project brief has real literature evidence from at least two non-fixture sources, "
                    "related-work citations are refreshed, and re-review no longer reports weak literature coverage."
                ),
            )
        )
    if profile and (
        not profile.get("benchmark_provenance_ready", False)
        or not profile.get("benchmark_publication_ready", False)
    ):
        add(
            _project_revision_action(
                action_id="project_benchmark_provenance_repair",
                action_kind="experiment_repair",
                repair_kind="update_benchmark_provenance",
                execution_route="research_replan",
                priority="high",
                title="Repair missing benchmark provenance",
                detail=(
                    "Selected project runs do not all have publication-grade benchmark provenance. "
                    "Attach dataset id, revision, license, source fingerprint, frozen snapshot metadata, "
                    "or keep final publish blocked."
                ),
                issue_ids=["project_benchmark_provenance"],
                expected_outputs=[
                    *common_outputs,
                    "project_benchmark_card_json",
                    "project_benchmark_provenance_manifest_json",
                    "project_publication_readiness_report_json",
                ],
                terminal_condition=(
                    "Every selected run has complete benchmark provenance and publication-grade eligibility, "
                    "or the project manuscript keeps benchmark provenance as an explicit blocker/follow-up."
                ),
            )
        )
    if profile and not profile.get("benchmark_source_independence_ready", False):
        add(
            _project_revision_action(
                action_id="project_benchmark_source_independence_repair",
                action_kind="experiment_repair",
                repair_kind="update_benchmark_provenance",
                execution_route="research_replan",
                priority="high",
                title="Attempt independent benchmark source repair",
                detail=(
                    "Selected project benchmark views do not cover at least two independent "
                    "external source releases. Attempt to import or select an independent "
                    "frozen/imported benchmark source; if no such repository-local evidence exists, "
                    "retain a blocked repair artifact and keep final publish blocked."
                ),
                issue_ids=["benchmark_source_independence"],
                expected_outputs=[
                    *common_outputs,
                    "project_benchmark_provenance_manifest_json",
                    "project_benchmark_source_independence_repair_json",
                    "project_publication_readiness_report_json",
                ],
                terminal_condition=(
                    "Selected benchmark evidence includes at least two independent source datasets "
                    "with complete frozen/imported/remote-real provenance, or the blocked repair "
                    "artifact preserves the source-independence limitation."
                ),
            )
        )
    if profile and not profile.get("benchmark_scale_ready", False):
        add(
            _project_revision_action(
                action_id="project_benchmark_scale_repair",
                action_kind="experiment_repair",
                repair_kind="rerun_experiments",
                execution_route="experiment_rerun",
                priority="high",
                title="Repair insufficient benchmark scale",
                detail=(
                    "Project benchmark evidence is below the publication-grade sample-count floor. "
                    "Import or execute a larger frozen/imported benchmark snapshot before final-publish claims."
                ),
                issue_ids=["project_benchmark_scale"],
                expected_outputs=[
                    *common_outputs,
                    "project_benchmark_provenance_manifest_json",
                    "project_statistics_report_json",
                    "project_publication_readiness_report_json",
                ],
                terminal_condition=(
                    "At least one selected run uses a publication-eligible benchmark with the required sample count, "
                    "or final publish remains blocked with a documented scale limitation."
                ),
            )
        )

    stats = statistics_profiles or []
    has_statistics = any(item.get("has_statistics") for item in stats)
    has_significance = any(item.get("significance_test_count", 0) > 0 for item in stats)
    if stats and (not has_statistics or not has_significance):
        add(
            _project_revision_action(
                action_id="project_insufficient_statistics_repair",
                action_kind="experiment_repair",
                repair_kind="rerun_experiments",
                execution_route="experiment_rerun",
                priority="high",
                title="Repair insufficient project statistics",
                detail=(
                    "Project paper compiler evidence lacks deterministic aggregate statistics or significance tests. "
                    "Run/import multi-seed, multi-split, bootstrap, or paired-comparison evidence before final publish."
                ),
                issue_ids=["project_statistics_coverage"],
                expected_outputs=[
                    *common_outputs,
                    "project_statistics_report_json",
                    "project_paper_compiler_evidence_json",
                    "project_publication_readiness_report_json",
                ],
                terminal_condition=(
                    "Project statistics report includes deterministic aggregate statistics and at least one "
                    "paired/significance comparison, or the manuscript marks insufficient statistics as a limitation."
                ),
            )
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        actions.values(),
        key=lambda item: (
            priority_order.get(item.priority, 3),
            item.action_kind,
            item.title.lower(),
            item.action_id,
        ),
    )


def _project_reviewer_role_for_action(action: AutoResearchReviewLoopActionRead) -> str:
    detail = f"{action.action_kind} {action.repair_kind or ''} {action.title} {action.detail}".lower()
    if "literature" in detail or "citation" in detail or "related work" in detail:
        return "novelty_reviewer"
    if "benchmark" in detail or "experiment" in detail or "statistics" in detail:
        return "methodology_reviewer"
    if "reproducibility" in detail or "package" in detail or "artifact" in detail:
        return "reproducibility_reviewer"
    if "unsupported" in detail or "downgrade" in detail or "claim" in detail:
        return "skeptical_reviewer"
    return "writing_reviewer"


def _project_review_findings_payload(
    *,
    project_id: str,
    actions: list[AutoResearchReviewLoopActionRead],
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    evidence_profile: dict[str, Any],
    statistics_profiles: list[dict[str, Any]],
    selected_runs: list[AutoResearchRunRead] | None = None,
) -> dict[str, Any]:
    phase6_negative_evidence_audit = _phase6_negative_evidence_audit_payload(
        selected_runs=selected_runs or [],
        ledger=ledger,
        traces=traces,
    )
    findings = []
    for index, action in enumerate(actions, start=1):
        finding_id = f"project_finding_{_slug(action.action_id)}"
        severity = "major" if action.priority == "high" else "minor" if action.priority == "low" else "moderate"
        findings.append(
            {
                "finding_id": finding_id,
                "reviewer_role": _project_reviewer_role_for_action(action),
                "severity": severity,
                "category": action.action_kind,
                "summary": action.title,
                "detail": action.detail,
                "mapped_revision_action_id": action.action_id,
                "mapped_issue_ids": list(action.issue_ids),
                "required_repair_kind": action.repair_kind,
                "required_execution_route": action.execution_route,
                "expected_output_asset_ids": list(action.expected_output_asset_ids),
                "terminal_condition": action.terminal_condition,
                "requires_rereview": action.requires_rereview,
                "finding_order": index,
            }
        )
    status_counts: dict[str, int] = {}
    for finding in findings:
        status_counts[finding["severity"]] = status_counts.get(finding["severity"], 0) + 1
    payload = {
        "review_id": "project_reviewer_simulation_findings_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "reviewer_simulator": "project_evidence_constrained_reviewer_v1",
        "review_round": 1,
        "finding_count": len(findings),
        "status_counts": status_counts,
        "findings": findings,
        "revision_action_ids": [action.action_id for action in actions],
        "claim_trace_count": len(traces),
        "unsupported_or_partial_trace_count": sum(
            1 for trace in traces if trace.support_status != "supported"
        ),
        "ledger_limitation_count": len(ledger.limitations),
        "ledger_negative_finding_count": len(ledger.negative_findings),
        "evidence_profile_blockers": list(evidence_profile.get("blockers", [])),
        "statistics_profiles": statistics_profiles,
        "phase6_negative_evidence_audit": phase6_negative_evidence_audit,
        "negative_evidence_category_summary": {
            "categories": phase6_negative_evidence_audit["categories"],
            "missing_categories": phase6_negative_evidence_audit["missing_categories"],
            "coverage_complete": phase6_negative_evidence_audit["coverage_complete"],
        },
        "policy": (
            "Project review findings are generated from claim traces, evidence profile blockers, "
            "statistics profiles, and revision actions. They route issues to bounded repairs or "
            "claim downgrades and cannot mark evidence-producing repairs complete without output artifacts."
        ),
    }
    return {**payload, "review_fingerprint": _fingerprint(payload)}


def _attach_project_review_finding_ids(
    actions: list[AutoResearchReviewLoopActionRead],
    review_findings: dict[str, Any],
) -> list[AutoResearchReviewLoopActionRead]:
    finding_by_action = {
        item.get("mapped_revision_action_id"): item.get("finding_id")
        for item in review_findings.get("findings", [])
        if item.get("mapped_revision_action_id") and item.get("finding_id")
    }
    return [
        action.model_copy(
            update={
                "finding_ids": _dedupe(
                    [
                        *action.finding_ids,
                        str(finding_by_action[action.action_id]),
                    ]
                )
            }
        )
        if action.action_id in finding_by_action
        else action
        for action in actions
    ]


def _revision_action_section(action: AutoResearchReviewLoopActionRead) -> str:
    if action.action_id.startswith("project_retrieval_repair_"):
        return "Results"
    if action.action_id.startswith("project_claim_downgrade_"):
        return "Limitations"
    detail = f"{action.title} {action.detail}".lower()
    if "literature" in detail or "citation" in detail:
        return "Related Work"
    if (
        "experiment" in detail
        or "baseline" in detail
        or "ablation" in detail
        or "benchmark" in detail
        or "provenance" in detail
        or "statistics" in detail
    ):
        return "Experimental Setup"
    if "limitation" in detail or "downgrade" in detail:
        return "Limitations"
    if "retrieval" in detail or "evidence" in detail:
        return "Results"
    return "Analysis"


def _build_project_revision_action_index(
    actions: list[AutoResearchReviewLoopActionRead],
    *,
    markdown: str,
) -> AutoResearchPaperRevisionActionIndexRead:
    entries: list[AutoResearchPaperRevisionActionEntryRead] = []
    for action in actions:
        section_title = _revision_action_section(action)
        entries.append(
            AutoResearchPaperRevisionActionEntryRead(
                action_id=action.action_id,
                title=action.title,
                detail=action.detail,
                priority=action.priority,
                status="completed" if action.status == "completed" else "pending",
                section_id=_slug(section_title, fallback="section"),
                section_title=section_title,
                first_seen_round=action.first_seen_round,
                last_seen_round=action.last_seen_round,
                completed_round=action.completed_round,
                issue_ids=action.issue_ids,
                claim_ids=[
                    item for item in action.issue_ids if item.startswith("project_claim_")
                ],
                evidence_focus=action.expected_output_asset_ids,
                packet_relative_path=PROJECT_PAPER_REVISED_FILENAME if action.status == "completed" else None,
                diff_status="updated" if action.status == "completed" else "unchanged",
                current_word_count=len(markdown.split()),
                resolved_issue_summaries=(
                    [action.terminal_condition] if action.status == "completed" else []
                ),
                open_issue_summaries=(
                    [] if action.status == "completed" else [action.terminal_condition]
                ),
                current_excerpt=action.terminal_condition,
            )
        )
    return AutoResearchPaperRevisionActionIndexRead(
        generated_at=_utcnow(),
        revision_round=1 if actions else 0,
        total_action_count=len(actions),
        pending_action_count=sum(1 for item in actions if item.status != "completed"),
        completed_action_count=sum(1 for item in actions if item.status == "completed"),
        materialized_action_count=sum(1 for item in actions if item.status == "completed"),
        summary=(
            f"Project paper revision plan has {len(actions)} bounded action(s) for weak, unsupported, "
            "or missing-evidence claims."
            if actions
            else "Project paper revision plan has no pending actions."
        ),
        actions=entries,
    )


def _project_claim_downgrade_status(action: AutoResearchReviewLoopActionRead) -> str:
    if action.action_kind != "claim_downgrade":
        return "not_applicable"
    if action.status == "completed":
        return "downgraded"
    if action.status == "blocked":
        return "blocked"
    if action.status == "failed":
        return "failed"
    return "pending"


def _project_compiler_has_audited_terminal_repair_attempt(
    action: AutoResearchReviewLoopActionRead,
) -> bool:
    if action.action_id not in PROJECT_COMPILER_AUDITED_TERMINAL_REPAIR_ACTION_IDS:
        return False
    if action.status != "blocked":
        return False
    if action.started_at_step is None or action.completed_at_step is None:
        return False
    if not action.failure_classification or not action.residual_blockers:
        return False
    rereview_result = action.rereview_result or {}
    if rereview_result.get("recommendation") != "block_final_publish":
        return False
    if bool(rereview_result.get("terminal_condition_met")):
        return False
    output_audits = _project_repair_output_audits(action)
    return bool(output_audits) and all(
        item["exists"] and item["loaded"] and not item["load_error"]
        for item in output_audits
    )


def _project_repair_output_audits(action: AutoResearchReviewLoopActionRead) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for ref in action.output_artifact_refs:
        if ":" not in ref:
            continue
        ref_kind, raw_path = ref.split(":", 1)
        path = Path(raw_path)
        exists = path.is_file()
        payload: dict[str, Any] = {}
        load_error: str | None = None
        if exists:
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = loaded
                else:
                    load_error = "artifact_json_root_not_object"
            except json.JSONDecodeError as exc:
                load_error = f"artifact_json_decode_error:{exc.msg}"
        complete_value = payload.get("complete")
        if complete_value is None:
            complete_value = payload.get("rereview_complete")
        fingerprint = next(
            (
                payload.get(key)
                for key in (
                    "fingerprint",
                    "support_index_fingerprint",
                    "repair_fingerprint",
                    "statistics_fingerprint",
                    "ledger_fingerprint",
                    "readiness_fingerprint",
                )
                if payload.get(key)
            ),
            None,
        )
        audits.append(
            {
                "ref": ref,
                "ref_kind": ref_kind,
                "path": raw_path,
                "exists": exists,
                "loaded": bool(payload),
                "load_error": load_error,
                "artifact_id": payload.get("index_id")
                or payload.get("repair_id")
                or payload.get("report_id")
                or payload.get("ledger_id")
                or payload.get("readiness_id")
                or payload.get("support_index_id")
                or payload.get("manifest_id"),
                "complete": bool(complete_value),
                "blockers": list(payload.get("blockers", [])) if isinstance(payload.get("blockers", []), list) else [],
                "fingerprint": fingerprint,
            }
        )
    return audits


def _project_action_rereview_details(
    actions: list[AutoResearchReviewLoopActionRead],
    *,
    phase6_negative_evidence_audit: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    negative_audit = phase6_negative_evidence_audit or {}
    for action in actions:
        output_audits = _project_repair_output_audits(action)
        evidence_repair = action.repair_kind in {
            "refresh_literature",
            "update_benchmark_provenance",
            "rerun_experiments",
        }
        repair_outputs_consumed = (
            bool(output_audits)
            and all(item["exists"] and item["loaded"] and not item["load_error"] for item in output_audits)
        )
        repair_outputs_complete = (
            bool(output_audits)
            and all(item["complete"] for item in output_audits)
        )
        rereview_result = action.rereview_result or {}
        terminal_condition_met = bool(
            rereview_result.get("terminal_condition_met", action.status == "completed")
        )
        if evidence_repair:
            terminal_condition_met = bool(
                terminal_condition_met
                and repair_outputs_consumed
                and (repair_outputs_complete if action.status == "completed" else True)
            )
        residual_blockers = list(action.residual_blockers)
        resolved_blockers = (
            [action.terminal_condition]
            if action.status == "completed" and terminal_condition_met
            else []
        )
        new_blockers = residual_blockers if action.status != "completed" else []
        reviewer_residual_concern = (
            "No residual concern; terminal condition was satisfied."
            if action.status == "completed" and not residual_blockers
            else "; ".join(residual_blockers)
            if residual_blockers
            else action.failure_classification
            if action.failure_classification
            else "Re-review is still pending."
        )
        recommendation = rereview_result.get("recommendation")
        if not recommendation:
            if action.status == "completed":
                recommendation = "accept_as_review_bundle"
            elif action.status == "blocked":
                recommendation = "block_final_publish"
            else:
                recommendation = "continue_repair"
        details.append(
            {
                "action_id": action.action_id,
                "original_finding": action.detail or action.title,
                "finding_ids": list(action.finding_ids),
                "issue_ids": list(action.issue_ids),
                "repair_kind": action.repair_kind,
                "repair_route": action.execution_route,
                "execution_route": action.execution_route,
                "status": action.status,
                "input_artifact_refs": list(action.input_artifact_refs),
                "output_artifact_refs": list(action.output_artifact_refs),
                "repair_output_audits": output_audits,
                "repair_output_audit_count": len(output_audits),
                "repair_outputs_consumed": repair_outputs_consumed,
                "repair_outputs_complete": repair_outputs_complete,
                "terminal_condition": action.terminal_condition,
                "terminal_condition_met": terminal_condition_met,
                "reviewer_residual_concern": reviewer_residual_concern,
                "resolved_blockers": resolved_blockers,
                "new_blockers": new_blockers,
                "claim_downgrade_status": _project_claim_downgrade_status(action),
                "phase6_negative_evidence_retained": bool(
                    negative_audit.get("entry_count", 0)
                    or negative_audit.get("categories")
                    or negative_audit.get("missing_categories")
                ),
                "phase6_negative_evidence_audit": negative_audit,
                "negative_evidence_report_ref": negative_audit.get(
                    "negative_evidence_report_ref",
                    "submission_package/negative_evidence_report.json",
                ),
                "negative_evidence_retention_policy": (
                    "Re-review must retain Phase 6 negative-evidence categories and missing-category "
                    "blockers; claim downgrades cannot convert missing support into positive evidence."
                ),
                "recommendation": recommendation,
                "failure_classification": action.failure_classification,
                "rereview_finding": rereview_result.get(
                    "finding",
                    "Claim downgraded or routed to repair without promoting unsupported evidence."
                    if action.status == "completed"
                    else "The original finding still requires repair or manual review.",
                ),
            }
        )
    return details


def _apply_project_revision_actions(
    *,
    project_id: str,
    markdown: str,
    actions: list[AutoResearchReviewLoopActionRead],
    selected_runs: list[AutoResearchRunRead] | None = None,
    latest_brief: AutoResearchResearchBriefRead | None = None,
    traces: list[AutoResearchProjectClaimTraceRead] | None = None,
    evidence_profile: dict[str, Any] | None = None,
    statistics_profiles: list[dict[str, Any]] | None = None,
) -> tuple[str, list[AutoResearchReviewLoopActionRead], dict[str, Any], dict[str, Any]]:
    completed: list[AutoResearchReviewLoopActionRead] = []
    pending: list[AutoResearchReviewLoopActionRead] = []
    blocked: list[AutoResearchReviewLoopActionRead] = []
    repair_execution_log: list[dict[str, Any]] = []
    revision_notes = [
        "## Revision Appendix",
        "The following bounded revisions were applied automatically. They downgrade unsupported or weak claims to limitations or repair targets; they do not promote missing evidence to supported evidence.",
    ]
    for action in actions:
        if (
            action.auto_applicable
            and action.action_id == "project_literature_refresh_multi_source"
            and action.repair_kind == "refresh_literature"
            and action.execution_route == "literature_refresh"
        ):
            support_index = _build_project_literature_support_index(
                project_id=project_id,
                latest_brief=latest_brief,
                traces=traces or [],
                evidence_profile=evidence_profile or {},
            )
            support_index_path = (
                _project_paper_dir(project_id) / PROJECT_LITERATURE_SUPPORT_INDEX_FILENAME
            )
            support_index_path.write_text(json.dumps(support_index, indent=2), encoding="utf-8")
            output_refs = [
                "project_literature_scout_json",
                f"project_literature_support_index:{support_index_path}",
            ]
            execution_record = {
                "action_id": action.action_id,
                "route": action.execution_route,
                "repair_kind": action.repair_kind,
                "status": "completed" if support_index["complete"] else "blocked",
                "started_at_step": action.started_at_step or 2,
                "completed_at_step": action.completed_at_step or 3,
                "output_artifact_refs": output_refs,
                "residual_blockers": support_index["blockers"],
            }
            repair_execution_log.append(execution_record)
            if support_index["complete"]:
                completed_action = action.model_copy(
                    update={
                        "status": "completed",
                        "completed_round": action.completed_round or 2,
                        "last_seen_round": max(action.last_seen_round, 2),
                        "started_at_step": action.started_at_step or 2,
                        "completed_at_step": action.completed_at_step or 3,
                        "input_artifact_refs": _dedupe(
                            [
                                *action.input_artifact_refs,
                                "latest_project_research_brief",
                                "project_claim_traces",
                            ]
                        ),
                        "output_artifact_refs": _dedupe(
                            [*action.output_artifact_refs, *output_refs]
                        ),
                        "rereview_result": {
                            "terminal_condition_met": True,
                            "recommendation": "accept_as_review_bundle",
                            "finding": "Multi-source real cached/network literature support was materialized.",
                        },
                        "residual_blockers": [],
                    }
                )
                completed.append(completed_action)
                revision_notes.extend(
                    [
                        "",
                        f"### {action.title}",
                        f"- Action id: `{action.action_id}`",
                        "- Applied repair: materialized a project literature support index from structured cached/network literature scout evidence.",
                        f"- Output artifact: `{support_index_path}`",
                        f"- Terminal condition: {action.terminal_condition}",
                    ]
                )
                continue
            blocked_action = action.model_copy(
                update={
                    "status": "blocked",
                    "last_seen_round": max(action.last_seen_round, 2),
                    "started_at_step": action.started_at_step or 2,
                    "completed_at_step": action.completed_at_step or 3,
                    "input_artifact_refs": _dedupe(
                        [
                            *action.input_artifact_refs,
                            "latest_project_research_brief",
                            "project_claim_traces",
                        ]
                    ),
                    "output_artifact_refs": _dedupe([*action.output_artifact_refs, *output_refs]),
                    "failure_classification": "insufficient_real_literature_sources",
                    "rereview_result": {
                        "terminal_condition_met": False,
                        "recommendation": "block_final_publish",
                        "finding": "Literature repair could not find at least two non-fixture cached/network sources.",
                    },
                    "residual_blockers": list(support_index["blockers"]),
                }
            )
            blocked.append(blocked_action)
            continue
        if (
            action.auto_applicable
            and action.action_id == "project_benchmark_provenance_repair"
            and action.repair_kind == "update_benchmark_provenance"
            and action.execution_route == "research_replan"
        ):
            repair_index = _build_project_benchmark_provenance_repair_index(
                project_id=project_id,
                evidence_profile=evidence_profile or {},
            )
            repair_index_path = (
                _project_paper_dir(project_id) / PROJECT_BENCHMARK_PROVENANCE_REPAIR_INDEX_FILENAME
            )
            repair_index_path.write_text(json.dumps(repair_index, indent=2), encoding="utf-8")
            output_refs = [
                "project_benchmark_card_json",
                "project_benchmark_provenance_manifest_json",
                f"project_benchmark_provenance_repair_index:{repair_index_path}",
            ]
            execution_record = {
                "action_id": action.action_id,
                "route": action.execution_route,
                "repair_kind": action.repair_kind,
                "status": "completed" if repair_index["complete"] else "blocked",
                "started_at_step": action.started_at_step or 2,
                "completed_at_step": action.completed_at_step or 3,
                "output_artifact_refs": output_refs,
                "residual_blockers": repair_index["blockers"],
            }
            repair_execution_log.append(execution_record)
            if repair_index["complete"]:
                completed_action = action.model_copy(
                    update={
                        "status": "completed",
                        "completed_round": action.completed_round or 2,
                        "last_seen_round": max(action.last_seen_round, 2),
                        "started_at_step": action.started_at_step or 2,
                        "completed_at_step": action.completed_at_step or 3,
                        "input_artifact_refs": _dedupe(
                            [
                                *action.input_artifact_refs,
                                "project_publication_evidence_profile",
                                "selected_run_experiment_specs",
                            ]
                        ),
                        "output_artifact_refs": _dedupe(
                            [*action.output_artifact_refs, *output_refs]
                        ),
                        "rereview_result": {
                            "terminal_condition_met": True,
                            "recommendation": "accept_as_review_bundle",
                            "finding": "Selected run benchmark provenance is publication-grade eligible and indexed.",
                        },
                        "residual_blockers": [],
                    }
                )
                completed.append(completed_action)
                revision_notes.extend(
                    [
                        "",
                        f"### {action.title}",
                        f"- Action id: `{action.action_id}`",
                        "- Applied repair: materialized a benchmark provenance repair index from selected run dataset provenance and eligibility checks.",
                        f"- Output artifact: `{repair_index_path}`",
                        f"- Terminal condition: {action.terminal_condition}",
                    ]
                )
                continue
            failure_classification = _benchmark_provenance_failure_classification(repair_index)
            blocked_action = action.model_copy(
                update={
                    "status": "blocked",
                    "last_seen_round": max(action.last_seen_round, 2),
                    "started_at_step": action.started_at_step or 2,
                    "completed_at_step": action.completed_at_step or 3,
                    "input_artifact_refs": _dedupe(
                        [
                            *action.input_artifact_refs,
                            "project_publication_evidence_profile",
                            "selected_run_experiment_specs",
                        ]
                    ),
                    "output_artifact_refs": _dedupe([*action.output_artifact_refs, *output_refs]),
                    "failure_classification": failure_classification,
                    "rereview_result": {
                        "terminal_condition_met": False,
                        "recommendation": "block_final_publish",
                        "finding": "Benchmark provenance repair could not satisfy publication-grade eligibility.",
                    },
                    "residual_blockers": list(repair_index["blockers"]),
                }
            )
            blocked.append(blocked_action)
            continue
        if (
            action.auto_applicable
            and action.action_id == "project_benchmark_source_independence_repair"
            and action.repair_kind == "update_benchmark_provenance"
            and action.execution_route == "research_replan"
        ):
            repair_payload = _build_project_benchmark_source_independence_repair(
                project_id=project_id,
                evidence_profile=evidence_profile or {},
            )
            repair_path = (
                _project_paper_sources_dir(project_id)
                / PROJECT_BENCHMARK_SOURCE_INDEPENDENCE_REPAIR_FILENAME
            )
            repair_path.write_text(json.dumps(repair_payload, indent=2), encoding="utf-8")
            output_refs = [
                "project_benchmark_provenance_manifest_json",
                f"project_benchmark_source_independence_repair:{repair_path}",
            ]
            execution_record = {
                "action_id": action.action_id,
                "route": action.execution_route,
                "repair_kind": action.repair_kind,
                "status": "completed" if repair_payload["complete"] else "blocked",
                "started_at_step": action.started_at_step or 2,
                "completed_at_step": action.completed_at_step or 3,
                "output_artifact_refs": output_refs,
                "residual_blockers": repair_payload["blockers"],
            }
            repair_execution_log.append(execution_record)
            if repair_payload["complete"]:
                completed_action = action.model_copy(
                    update={
                        "status": "completed",
                        "completed_round": action.completed_round or 2,
                        "last_seen_round": max(action.last_seen_round, 2),
                        "started_at_step": action.started_at_step or 2,
                        "completed_at_step": action.completed_at_step or 3,
                        "input_artifact_refs": _dedupe(
                            [
                                *action.input_artifact_refs,
                                "project_publication_evidence_profile",
                                "project_benchmark_provenance_manifest_json",
                            ]
                        ),
                        "output_artifact_refs": _dedupe(
                            [*action.output_artifact_refs, *output_refs]
                        ),
                        "rereview_result": {
                            "terminal_condition_met": True,
                            "recommendation": "accept_as_review_bundle",
                            "finding": "An independent benchmark source release is attached with complete provenance.",
                        },
                        "residual_blockers": [],
                    }
                )
                completed.append(completed_action)
                revision_notes.extend(
                    [
                        "",
                        f"### {action.title}",
                        f"- Action id: `{action.action_id}`",
                        "- Applied repair: materialized a benchmark source-independence repair artifact from selected source provenance.",
                        f"- Output artifact: `{repair_path}`",
                        f"- Terminal condition: {action.terminal_condition}",
                    ]
                )
                continue
            failure_classification = _benchmark_source_independence_failure_classification(
                repair_payload
            )
            blocked_action = action.model_copy(
                update={
                    "status": "blocked",
                    "last_seen_round": max(action.last_seen_round, 2),
                    "started_at_step": action.started_at_step or 2,
                    "completed_at_step": action.completed_at_step or 3,
                    "input_artifact_refs": _dedupe(
                        [
                            *action.input_artifact_refs,
                            "project_publication_evidence_profile",
                            "project_benchmark_provenance_manifest_json",
                        ]
                    ),
                    "output_artifact_refs": _dedupe([*action.output_artifact_refs, *output_refs]),
                    "failure_classification": failure_classification,
                    "rereview_result": {
                        "terminal_condition_met": False,
                        "recommendation": "block_final_publish",
                        "finding": "Source-independence repair could not attach a second independent benchmark/source release from repository-local or imported evidence.",
                    },
                    "residual_blockers": list(repair_payload["blockers"]),
                }
            )
            blocked.append(blocked_action)
            continue
        if (
            action.auto_applicable
            and action.action_id in {
                "project_benchmark_scale_repair",
                "project_insufficient_statistics_repair",
            }
            and action.repair_kind == "rerun_experiments"
            and action.execution_route == "experiment_rerun"
        ):
            repair_index = _build_project_experiment_repair_index(
                project_id=project_id,
                evidence_profile=evidence_profile or {},
                statistics_profiles=statistics_profiles or [],
                selected_runs=selected_runs,
            )
            route = repair_index["repair_routes"][action.action_id]
            repair_index_path = _project_paper_dir(project_id) / PROJECT_EXPERIMENT_REPAIR_INDEX_FILENAME
            repair_index_path.write_text(json.dumps(repair_index, indent=2), encoding="utf-8")
            output_refs = [
                "project_statistics_report_json",
                f"project_experiment_repair_index:{repair_index_path}",
            ]
            output_refs.extend(repair_index.get("execution_output_artifact_refs", []))
            if action.action_id == "project_benchmark_scale_repair":
                output_refs.append("project_benchmark_provenance_manifest_json")
            if action.action_id == "project_insufficient_statistics_repair":
                output_refs.append("project_paper_compiler_evidence_json")
            execution_record = {
                "action_id": action.action_id,
                "route": action.execution_route,
                "repair_kind": action.repair_kind,
                "status": "completed" if route["complete"] else "blocked",
                "started_at_step": action.started_at_step or 2,
                "completed_at_step": action.completed_at_step or 3,
                "output_artifact_refs": output_refs,
                "residual_blockers": repair_index["blockers"],
            }
            repair_execution_log.append(execution_record)
            if route["complete"]:
                completed_action = action.model_copy(
                    update={
                        "status": "completed",
                        "completed_round": action.completed_round or 2,
                        "last_seen_round": max(action.last_seen_round, 2),
                        "started_at_step": action.started_at_step or 2,
                        "completed_at_step": action.completed_at_step or 3,
                        "input_artifact_refs": _dedupe(
                            [
                                *action.input_artifact_refs,
                                "project_publication_evidence_profile",
                                "project_statistics_profiles",
                                "selected_run_result_artifacts",
                                "selected_run_execution_profiles",
                            ]
                        ),
                        "output_artifact_refs": _dedupe(
                            [*action.output_artifact_refs, *output_refs]
                        ),
                        "rereview_result": {
                            "terminal_condition_met": True,
                            "recommendation": "accept_as_review_bundle",
                            "finding": "Persisted benchmark scale, deterministic statistics, and selected-run execution/import replay outputs satisfy this repair route.",
                        },
                        "residual_blockers": [],
                    }
                )
                completed.append(completed_action)
                revision_notes.extend(
                    [
                        "",
                        f"### {action.title}",
                        f"- Action id: `{action.action_id}`",
                        "- Applied repair: materialized an experiment repair index from selected run benchmark and statistics artifacts.",
                        "- Execution coverage: linked selected-run execution/import replay outputs are recorded in the experiment repair index.",
                        f"- Output artifact: `{repair_index_path}`",
                        f"- Terminal condition: {action.terminal_condition}",
                    ]
                )
                continue
            failure_classification = _experiment_repair_failure_classification(
                repair_index,
                repair_kind=action.action_id,
            )
            blocked_action = action.model_copy(
                update={
                    "status": "blocked",
                    "last_seen_round": max(action.last_seen_round, 2),
                    "started_at_step": action.started_at_step or 2,
                    "completed_at_step": action.completed_at_step or 3,
                    "input_artifact_refs": _dedupe(
                        [
                            *action.input_artifact_refs,
                            "project_publication_evidence_profile",
                            "project_statistics_profiles",
                            "selected_run_result_artifacts",
                            "selected_run_execution_profiles",
                        ]
                    ),
                    "output_artifact_refs": _dedupe([*action.output_artifact_refs, *output_refs]),
                    "failure_classification": failure_classification,
                    "rereview_result": {
                        "terminal_condition_met": False,
                        "recommendation": "continue_repair",
                        "finding": "Experiment/statistics repair requires a larger benchmark run, imported replay, or deterministic significance artifact.",
                    },
                    "residual_blockers": list(repair_index["blockers"]),
                }
            )
            blocked.append(blocked_action)
            continue
        can_apply = (
            action.auto_applicable
            and action.action_kind == "claim_downgrade"
            and action.repair_kind == "repair_claim_evidence"
            and action.execution_route == "paper_rebuild"
        )
        if not can_apply:
            pending.append(action)
            continue
        completed_action = action.model_copy(
            update={
                "status": "completed",
                "completed_round": action.completed_round or 2,
                "last_seen_round": max(action.last_seen_round, 2),
                "output_artifact_refs": _dedupe(
                    [
                        *action.output_artifact_refs,
                        "project_paper_revised_markdown",
                        "project_claim_evidence_index_markdown",
                    ]
                ),
                "rereview_result": {
                    "terminal_condition_met": True,
                    "recommendation": "accept_as_review_bundle",
                    "finding": "Unsupported project-paper claim was downgraded to a limitation or required follow-up without promoting unsupported evidence.",
                },
                "residual_blockers": [],
            }
        )
        completed.append(completed_action)
        issue_text = ", ".join(action.issue_ids) if action.issue_ids else "unmapped issue"
        revision_notes.extend(
            [
                "",
                f"### {action.title}",
                f"- Action id: `{action.action_id}`",
                f"- Source issue(s): {issue_text}",
                f"- Applied revision: the affected claim is framed as a limitation, conditional finding, or required follow-up until stronger claim-evidence retrieval support is attached.",
                f"- Terminal condition: {action.terminal_condition}",
            ]
        )
        if "project_retrieval_evidence_ledger" in action.expected_output_asset_ids:
            revision_notes.append(
                "- Retrieval repair route: keep the claim downgraded and preserve a retrieval refresh requirement in the evidence ledger."
            )
    revised_markdown = markdown
    if completed:
        revised_markdown = markdown.rstrip() + "\n\n" + "\n".join(revision_notes).strip() + "\n"
    actions_after_revision = sorted(
        [*completed, *blocked, *pending],
        key=lambda item: (
            0 if item.status != "completed" else 1,
            item.priority,
            item.action_id,
        ),
    )
    unresolved = [*blocked, *pending]
    phase6_negative_evidence_audit = _phase6_negative_evidence_audit_payload(
        selected_runs=selected_runs or [],
        traces=traces or [],
        repair_execution_log={"entries": repair_execution_log},
    )
    application_report = {
        "application_id": "project_revision_application_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "revision_round": 2 if actions else 0,
        "input_action_count": len(actions),
        "completed_action_count": len(completed),
        "pending_action_count": len(unresolved),
        "blocked_action_count": len(blocked),
        "completed_actions": [action.model_dump(mode="json") for action in completed],
        "pending_actions": [action.model_dump(mode="json") for action in pending],
        "blocked_actions": [action.model_dump(mode="json") for action in blocked],
        "repair_execution_log": repair_execution_log,
        "phase6_negative_evidence_retained": bool(
            phase6_negative_evidence_audit.get("entry_count", 0)
            or phase6_negative_evidence_audit.get("categories")
            or phase6_negative_evidence_audit.get("missing_categories")
        ),
        "phase6_negative_evidence_audit": phase6_negative_evidence_audit,
        "negative_evidence_report_ref": "submission_package/negative_evidence_report.json",
        "negative_evidence_retention_policy": (
            "Revision may downgrade claims or route repairs, but it must preserve Phase 6 "
            "negative-evidence categories, missing-category blockers, and report references."
        ),
        "policy": "Auto-applicable claim downgrades and literature support-index repairs can be materialized; unsupported evidence is not promoted.",
    }
    action_reviews = _project_action_rereview_details(
        actions_after_revision,
        phase6_negative_evidence_audit=phase6_negative_evidence_audit,
    )
    resolved_blockers = _dedupe(
        blocker
        for review in action_reviews
        for blocker in review["resolved_blockers"]
    )
    new_blockers = _dedupe(
        blocker
        for review in action_reviews
        for blocker in review["new_blockers"]
    )
    rereview_report = {
        "rereview_id": "project_revision_rereview_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "revision_round": 2 if actions else 0,
        "rereview_complete": bool(actions) and not unresolved,
        "same_support_issue_recurs": bool(unresolved),
        "completed_action_ids": [action.action_id for action in completed],
        "pending_action_ids": [action.action_id for action in pending],
        "blocked_action_ids": [action.action_id for action in blocked],
        "repair_execution_log": repair_execution_log,
        "action_reviews": action_reviews,
        "phase6_negative_evidence_retained": bool(
            phase6_negative_evidence_audit.get("entry_count", 0)
            or phase6_negative_evidence_audit.get("categories")
            or phase6_negative_evidence_audit.get("missing_categories")
        ),
        "phase6_negative_evidence_audit": phase6_negative_evidence_audit,
        "negative_evidence_report_ref": "submission_package/negative_evidence_report.json",
        "negative_evidence_retention_policy": (
            "Rereview cannot erase negative evidence to pass final-publish readiness; uncovered Phase 6 "
            "categories remain blockers or required follow-ups until deterministic artifacts cover them."
        ),
        "resolved_blockers": resolved_blockers,
        "new_blockers": new_blockers,
        "claim_downgrade_statuses": {
            review["action_id"]: review["claim_downgrade_status"]
            for review in action_reviews
            if review["claim_downgrade_status"] != "not_applicable"
        },
        "recommendations": {
            review["action_id"]: review["recommendation"] for review in action_reviews
        },
        "finding": (
            "All auto-applicable weak or unsupported project-paper claims were downgraded or routed to retrieval repair."
            if actions and not unresolved
            else "No revision actions were present."
            if not actions
            else "Some revision actions still require manual review, more real literature, or experiment repair."
        ),
    }
    return revised_markdown, actions_after_revision, application_report, rereview_report


def _project_revision_actions_markdown(
    action_index: AutoResearchPaperRevisionActionIndexRead,
) -> str:
    lines = [
        "# Project Paper Revision Actions",
        "",
        f"- Revision round: {action_index.revision_round}",
        f"- Total actions: {action_index.total_action_count}",
        f"- Pending actions: {action_index.pending_action_count}",
        f"- Summary: {action_index.summary}",
    ]
    for action in action_index.actions:
        lines.extend(
            [
                "",
                f"## {action.section_title}",
                f"- Action: `{action.action_id}`",
                f"- Priority: `{action.priority}`",
                f"- Status: `{action.status}`",
                f"- Title: {action.title or action.detail}",
                f"- Detail: {action.detail}",
            ]
        )
        if action.completed_round is not None:
            lines.append(f"- Completed round: `{action.completed_round}`")
        if action.issue_ids:
            lines.append(f"- Issue ids: {', '.join(f'`{item}`' for item in action.issue_ids)}")
        if action.evidence_focus:
            lines.append(f"- Expected outputs: {', '.join(f'`{item}`' for item in action.evidence_focus)}")
    return "\n".join(lines).strip() + "\n"


def _build_project_paper_sources_manifest(*, has_bibliography: bool) -> AutoResearchPaperSourcesManifestRead:
    compile_commands = [f"./{PROJECT_PAPER_BUILD_SCRIPT_FILENAME}", "pdflatex main.tex"]
    if has_bibliography:
        compile_commands.append("bibtex main")
    compile_commands.extend(["pdflatex main.tex", "pdflatex main.tex"])
    expected_outputs = ["main.pdf"]
    if has_bibliography:
        expected_outputs.append("main.bbl")
    return AutoResearchPaperSourcesManifestRead(
        generated_at=_utcnow(),
        entrypoint=PROJECT_PAPER_LATEX_FILENAME,
        bibliography=PROJECT_PAPER_BIB_FILENAME,
        compiler_hint="pdflatex + bibtex" if has_bibliography else "pdflatex",
        compile_commands=compile_commands,
        expected_outputs=expected_outputs,
        files=[
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_FILENAME,
                kind="markdown",
                description="Project-level evidence-constrained Markdown manuscript.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_LATEX_FILENAME,
                kind="latex",
                description="Compile-oriented LaTeX source generated from the project manuscript.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_BIB_FILENAME,
                kind="bibtex",
                description="BibTeX references derived from the latest structured project literature scout.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_BUILD_SCRIPT_FILENAME,
                kind="shell",
                description="Portable shell entrypoint for compiling the project manuscript sources.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_COMPILE_REPORT_FILENAME,
                kind="json",
                description="Compile-readiness report for the project manuscript source package.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_COMPILER_EVIDENCE_FILENAME,
                kind="json",
                description="Project manuscript evidence compiler packet covering sections, claims, citations, results, statistics, provenance, revisions, and compile readiness.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_REVISION_ACTION_INDEX_FILENAME,
                kind="json",
                description="Bounded project-paper revision actions derived from project claim traces and evidence gaps.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_REVIEW_FINDINGS_FILENAME,
                kind="json",
                description="Project-level reviewer-simulator findings mapped to bounded revision actions.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_REVISION_ACTION_NOTE_FILENAME,
                kind="markdown",
                description="Human-readable project-paper revision and repair action plan.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_REVISED_FILENAME,
                kind="markdown",
                description="Project manuscript after bounded automatic claim downgrade or repair-route revisions.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_REVISION_APPLICATION_FILENAME,
                kind="json",
                description="Machine-readable record of project-paper revision actions that were automatically materialized.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_REREVIEW_REPORT_FILENAME,
                kind="json",
                description="Deterministic re-review record for materialized project-paper revision actions.",
            ),
            AutoResearchPaperSourceFileRead(
                relative_path=PROJECT_PAPER_MANIFEST_FILENAME,
                kind="json",
                description="Project paper source manifest with compile commands and file inventory.",
            ),
        ],
    )


def _build_project_compile_report(
    *,
    manifest: AutoResearchPaperSourcesManifestRead,
    markdown: str,
    literature_count: int,
) -> AutoResearchPaperCompileReportRead:
    report = PaperWriter().build_paper_compile_report(
        paper_sources_manifest=manifest,
        paper_markdown=markdown,
        literature_count=literature_count,
    )
    if shutil.which("pdflatex") is not None:
        return report
    return report.model_copy(
        update={
            "ready_for_compile": False,
            "evidence_blockers": _dedupe(
                [
                    *report.evidence_blockers,
                    "pdflatex is not available in the current environment; source package is materialized but PDF compilation is blocked.",
                ]
            ),
        }
    )


def _is_pdf_compile_environment_blocker(blocker: Any) -> bool:
    lowered = str(blocker).lower()
    return "pdflatex" in lowered or (
        "pdf compilation" in lowered and "source package is materialized" in lowered
    )


def _materialize_project_paper_sources(
    *,
    project_id: str,
    markdown: str,
    revised_markdown: str,
    latest_brief: AutoResearchResearchBriefRead | None,
    revision_action_index: AutoResearchPaperRevisionActionIndexRead,
    review_findings: dict[str, Any],
    revision_application_report: dict[str, Any],
    revision_rereview_report: dict[str, Any],
) -> tuple[Path, AutoResearchPaperSourcesManifestRead, AutoResearchPaperCompileReportRead, str, str]:
    sources_dir = _project_paper_sources_dir(project_id)
    literature = _literature_insights(latest_brief)
    writer = PaperWriter()
    latex_source = writer.build_paper_latex_source(markdown, literature=literature)
    bibliography = writer.build_paper_bibliography(literature)
    manifest = _build_project_paper_sources_manifest(has_bibliography=bool(literature))
    build_script = writer.build_paper_build_script(paper_sources_manifest=manifest)
    compile_report = _build_project_compile_report(
        manifest=manifest,
        markdown=markdown,
        literature_count=len(literature),
    )
    (sources_dir / PROJECT_PAPER_FILENAME).write_text(markdown, encoding="utf-8")
    (sources_dir / PROJECT_PAPER_LATEX_FILENAME).write_text(latex_source, encoding="utf-8")
    (sources_dir / PROJECT_PAPER_BIB_FILENAME).write_text(bibliography, encoding="utf-8")
    build_script_path = sources_dir / PROJECT_PAPER_BUILD_SCRIPT_FILENAME
    build_script_path.write_text(build_script, encoding="utf-8")
    build_script_path.chmod(0o755)
    (sources_dir / PROJECT_PAPER_COMPILE_REPORT_FILENAME).write_text(
        compile_report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (sources_dir / PROJECT_PAPER_REVISION_ACTION_INDEX_FILENAME).write_text(
        revision_action_index.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (sources_dir / PROJECT_REVIEW_FINDINGS_FILENAME).write_text(
        json.dumps(review_findings, indent=2),
        encoding="utf-8",
    )
    (sources_dir / PROJECT_PAPER_REVISION_ACTION_NOTE_FILENAME).write_text(
        _project_revision_actions_markdown(revision_action_index),
        encoding="utf-8",
    )
    (sources_dir / PROJECT_PAPER_REVISED_FILENAME).write_text(revised_markdown, encoding="utf-8")
    (sources_dir / PROJECT_PAPER_REVISION_APPLICATION_FILENAME).write_text(
        json.dumps(revision_application_report, indent=2),
        encoding="utf-8",
    )
    (sources_dir / PROJECT_PAPER_REREVIEW_REPORT_FILENAME).write_text(
        json.dumps(revision_rereview_report, indent=2),
        encoding="utf-8",
    )
    (sources_dir / PROJECT_PAPER_MANIFEST_FILENAME).write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return sources_dir, manifest, compile_report, latex_source, bibliography


def _project_reproducibility_checklist_markdown(
    *,
    selected_runs: list[AutoResearchRunRead],
    project_paper_sections: list[str],
    project_paper_missing_sections: list[str],
    project_paper_compile_report: AutoResearchPaperCompileReportRead,
    project_paper_revision_actions: list[AutoResearchReviewLoopActionRead],
    project_review_findings: dict[str, Any],
    project_publish_gate_passed: bool,
    project_submission_blockers: list[str],
) -> str:
    pending_revision_actions = [
        action for action in project_paper_revision_actions if action.status != "completed"
    ]
    checks = [
        ("Project manuscript has required sections", not project_paper_missing_sections),
        ("At least one selected run is attached", bool(selected_runs)),
        ("Project paper source package is complete", project_paper_compile_report.source_package_complete),
        ("Project paper compile report has no missing inputs", not project_paper_compile_report.missing_required_inputs),
        ("Project reviewer findings are persisted", bool(project_review_findings.get("review_fingerprint"))),
        ("No pending project-paper revision actions remain", not pending_revision_actions),
        ("Project publish gate passed", project_publish_gate_passed),
    ]
    lines = [
        "# Project Reproducibility Checklist",
        "",
        "## Checks",
        *[
            f"- [{'x' if passed else ' '}] {label}"
            for label, passed in checks
        ],
        "",
        "## Required Sections",
        _markdown_list(project_paper_sections, empty="No project-paper sections were detected."),
        "",
        "## Missing Sections",
        _markdown_list(project_paper_missing_sections, empty="No required project-paper sections are missing."),
        "",
        "## Selected Runs",
        _markdown_list([run.id for run in selected_runs], empty="No selected runs are attached."),
        "",
        "## Blockers",
        _markdown_list(project_submission_blockers, empty="No project submission blockers were generated."),
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def _project_repair_execution_log_payload(
    *,
    project_id: str,
    project_paper_revision_actions: list[AutoResearchReviewLoopActionRead],
) -> dict[str, Any]:
    repair_actions = [
        action
        for action in project_paper_revision_actions
        if action.repair_kind is not None or action.execution_route != "paper_rebuild"
    ]
    evidence_producing_actions = [
        action
        for action in repair_actions
        if action.action_id
        in {
            "project_literature_refresh_multi_source",
            "project_benchmark_provenance_repair",
            "project_benchmark_source_independence_repair",
            "project_benchmark_scale_repair",
            "project_insufficient_statistics_repair",
        }
    ]
    entries = []
    for action in repair_actions:
        output_audits = _project_repair_output_audits(action)
        entries.append(
            {
                "action_id": action.action_id,
                "action_kind": action.action_kind,
                "repair_kind": action.repair_kind,
                "execution_route": action.execution_route,
                "status": action.status,
                "priority": action.priority,
                "title": action.title,
                "terminal_condition": action.terminal_condition,
                "started_at_step": action.started_at_step,
                "completed_at_step": action.completed_at_step,
                "input_artifact_refs": list(action.input_artifact_refs),
                "output_artifact_refs": list(action.output_artifact_refs),
                "repair_output_audits": output_audits,
                "repair_outputs_consumed": bool(output_audits)
                and all(item["exists"] and item["loaded"] and not item["load_error"] for item in output_audits),
                "expected_output_asset_ids": list(action.expected_output_asset_ids),
                "failure_classification": action.failure_classification,
                "rereview_result": action.rereview_result,
                "residual_blockers": list(action.residual_blockers),
                "terminal_condition_met": bool(
                    action.status == "completed"
                    and action.output_artifact_refs
                    and not action.residual_blockers
                ),
            }
        )
    payload = {
        "log_id": "project_repair_execution_log_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "action_count": len(repair_actions),
        "evidence_producing_action_count": len(evidence_producing_actions),
        "completed_action_count": sum(1 for action in repair_actions if action.status == "completed"),
        "blocked_action_count": sum(1 for action in repair_actions if action.status == "blocked"),
        "pending_action_count": sum(1 for action in repair_actions if action.status == "pending"),
        "failed_action_count": sum(1 for action in repair_actions if action.status == "failed"),
        "materialized_output_count": sum(len(action.output_artifact_refs) for action in repair_actions),
        "entries": entries,
        "complete": bool(repair_actions) and all(action.status == "completed" for action in repair_actions),
        "policy": (
            "Repair execution entries are evidence-constrained: an evidence-producing repair is complete only "
            "when output artifact refs exist and residual blockers are empty. Blocked entries continue to block "
            "final publication."
        ),
    }
    return {**payload, "repair_execution_fingerprint": _fingerprint(payload)}


def _project_reviewer_response_markdown(
    *,
    project_paper_revision_actions: list[AutoResearchReviewLoopActionRead],
    warnings: list[str],
    blockers: list[str],
) -> tuple[str, bool]:
    pending_actions = [action for action in project_paper_revision_actions if action.status != "completed"]
    completed_actions = [action for action in project_paper_revision_actions if action.status == "completed"]
    lines = [
        "# Project Reviewer Response",
        "",
    ]
    if not pending_actions and not completed_actions:
        lines.append("No pending project-paper revision actions were generated.")
    else:
        if completed_actions:
            lines.extend(["Completed bounded revision actions:"])
            for action in completed_actions:
                action_review = _project_action_rereview_details([action])[0]
                lines.extend(
                    [
                        f"- `{action.action_id}` ({action.priority}, {action.action_kind}): {action.title}",
                        f"  - Detail: {action.detail}",
                        f"  - Completed round: {action.completed_round}",
                        f"  - Recommendation: `{action_review['recommendation']}`",
                        f"  - Claim downgrade status: `{action_review['claim_downgrade_status']}`",
                        "  - Re-review result: "
                        + str(action_review["rereview_finding"]),
                        "  - Reviewer residual concern: "
                        + str(action_review["reviewer_residual_concern"]),
                        "  - Resolved blockers: "
                        + (
                            "; ".join(action_review["resolved_blockers"])
                            if action_review["resolved_blockers"]
                            else "none"
                        ),
                        "  - New blockers: "
                        + (
                            "; ".join(action_review["new_blockers"])
                            if action_review["new_blockers"]
                            else "none"
                        ),
                    ]
                )
                if action.output_artifact_refs:
                    lines.append(
                        "  - Output artifacts: "
                        + ", ".join(f"`{item}`" for item in action.output_artifact_refs)
                    )
        if pending_actions:
            lines.extend(["", "Pending bounded revision actions:"])
            for action in pending_actions:
                action_review = _project_action_rereview_details([action])[0]
                lines.extend(
                    [
                        f"- `{action.action_id}` ({action.priority}, {action.action_kind}): {action.title}",
                        f"  - Detail: {action.detail}",
                        f"  - Status: `{action.status}`",
                        f"  - Recommendation: `{action_review['recommendation']}`",
                        f"  - Claim downgrade status: `{action_review['claim_downgrade_status']}`",
                        f"  - Terminal condition: {action.terminal_condition}",
                        "  - Reviewer residual concern: "
                        + str(action_review["reviewer_residual_concern"]),
                        "  - Resolved blockers: "
                        + (
                            "; ".join(action_review["resolved_blockers"])
                            if action_review["resolved_blockers"]
                            else "none"
                        ),
                        "  - New blockers: "
                        + (
                            "; ".join(action_review["new_blockers"])
                            if action_review["new_blockers"]
                            else "none"
                        ),
                    ]
                )
                if action.failure_classification:
                    lines.append(f"  - Failure classification: `{action.failure_classification}`")
                if action.output_artifact_refs:
                    lines.append(
                        "  - Output artifacts: "
                        + ", ".join(f"`{item}`" for item in action.output_artifact_refs)
                    )
                if action.residual_blockers:
                    lines.append(
                        "  - Residual blockers: " + "; ".join(action.residual_blockers)
                    )
    lines.extend(
        [
            "",
            "## Warnings",
            _markdown_list(warnings, empty="No warnings were generated."),
            "",
            "## Blockers",
            _markdown_list(blockers, empty="No blockers were generated."),
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n", not pending_actions


def _project_claim_evidence_index_markdown(
    *,
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
) -> tuple[str, bool]:
    lines = [
        "# Project Claim Evidence Index",
        "",
        "## Claim Traces",
    ]
    if not traces:
        lines.append("- No project claim traces were generated.")
    for trace in traces:
        lines.extend(
            [
                f"- `{trace.claim_id}`: `{trace.support_status}`",
                f"  - Claim: {trace.claim}",
                f"  - Source conclusion: `{trace.source_conclusion_id}`",
                f"  - Evidence refs: {', '.join(trace.evidence_refs) if trace.evidence_refs else 'none'}",
            ]
        )
        if trace.unsupported_reasons:
            lines.append(f"  - Unsupported reasons: {'; '.join(trace.unsupported_reasons)}")
    lines.extend(["", "## Conclusion Ledger"])
    for label, items in (
        ("Stable", ledger.stable_conclusions),
        ("Conditional", ledger.conditional_conclusions),
        ("Negative", ledger.negative_findings),
        ("Failed", ledger.failed_hypotheses),
        ("Limitations", ledger.limitations),
    ):
        lines.extend(["", f"### {label}"])
        if not items:
            lines.append("- None.")
            continue
        for item in items:
            lines.append(
                f"- `{item.conclusion_id}`: {item.text} Evidence: "
                f"{', '.join(item.evidence_refs) if item.evidence_refs else 'none'}"
            )
    complete = bool(traces) and all(trace.support_status == "supported" for trace in traces)
    return "\n".join(lines).strip() + "\n", complete


def _project_retrieval_evidence_ledger_payload(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for run in selected_runs:
        if run.evidence_ledger is not None:
            for entry in run.evidence_ledger.entries:
                if not entry.evidence_id.startswith("evidence_retrieval_"):
                    continue
                entries.append(
                    {
                        "run_id": run.id,
                        "source": "run_evidence_ledger",
                        "evidence_id": entry.evidence_id,
                        "claim": entry.claim,
                        "artifact_ref": entry.artifact_ref,
                        "support_status": entry.support_status,
                        "metric": entry.metric,
                        "value": entry.value,
                    }
                )
        if run.artifact is not None:
            retrieval_ledger = run.artifact.outputs.get("retrieval_evidence_ledger", [])
            if isinstance(retrieval_ledger, dict):
                retrieval_ledger = retrieval_ledger.get("entries", [])
            if isinstance(retrieval_ledger, list):
                for index, item in enumerate(retrieval_ledger, start=1):
                    if not isinstance(item, dict):
                        continue
                    entries.append(
                        {
                            "run_id": run.id,
                            "source": "run_artifact_outputs",
                            "evidence_id": item.get("evidence_id") or f"{run.id}:retrieval_output:{index}",
                            "claim": item.get("claim") or item.get("query") or "",
                            "artifact_ref": item.get("artifact_ref") or "run_artifact.outputs.retrieval_evidence_ledger",
                            "support_status": item.get("support_status") or item.get("status") or "unknown",
                            "metric": item.get("metric"),
                            "value": item.get("value"),
                            "raw_entry": item,
                        }
                    )
    status_counts: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("support_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    blockers = []
    missing_count = status_counts.get("missing", 0)
    if missing_count:
        blockers.append(f"{missing_count} retrieval evidence ledger entr{'y' if missing_count == 1 else 'ies'} have missing support.")
    payload = {
        "ledger_id": "project_retrieval_evidence_ledger_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_ids": [run.id for run in selected_runs],
        "entry_count": len(entries),
        "status_counts": status_counts,
        "entries": entries,
        "complete": bool(entries) and not blockers,
        "blockers": blockers,
        "policy": (
            "Project retrieval evidence ledger aggregates run-level retrieval evidence without "
            "promoting missing or partial support to supported project claims."
        ),
    }
    return {**payload, "ledger_fingerprint": _fingerprint(payload)}


def _project_benchmark_card_payload(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    project_publish_gate_passed: bool,
) -> dict[str, Any]:
    run_cards: list[dict[str, Any]] = []
    blockers: list[str] = []
    for run in selected_runs:
        spec = run.spec
        dataset = spec.dataset if spec is not None else None
        source_kind = (
            run.benchmark.kind
            if run.benchmark is not None
            else dataset.source_kind
            if dataset is not None
            else None
        )
        source_url = (
            dataset.source_url
            if dataset is not None and dataset.source_url
            else run.benchmark.url
            if run.benchmark is not None
            else None
        )
        source_file_path = run.benchmark.file_path if run.benchmark is not None else None
        source_dataset_id = (
            dataset.source_dataset_id
            if dataset is not None and dataset.source_dataset_id
            else run.benchmark.dataset_id
            if run.benchmark is not None
            else None
        )
        train_size = dataset.train_size if dataset is not None else 0
        test_size = dataset.test_size if dataset is not None else 0
        total_examples = train_size + test_size
        sample_count = dataset.sample_count if dataset is not None and dataset.sample_count else total_examples
        split_count = (
            dataset.split_count
            if dataset is not None and dataset.split_count
            else int(train_size > 0) + int(test_size > 0)
        )
        publication_grade = bool(dataset is not None and dataset.publication_grade)
        provenance_complete = bool(dataset is not None and dataset.provenance_complete)
        run_blockers = []
        if not publication_grade:
            run_blockers.append("Run benchmark is not marked publication-grade.")
        if not provenance_complete:
            run_blockers.append("Run benchmark provenance is incomplete.")
        run_blockers.extend(list(dataset.publication_grade_blockers) if dataset is not None else [])
        blockers.extend(f"{run.id}: {item}" for item in run_blockers)
        run_cards.append(
            {
                "run_id": run.id,
                "topic": run.topic,
                "task_family": run.task_family,
                "benchmark_name": spec.benchmark_name if spec is not None else None,
                "benchmark_description": spec.benchmark_description if spec is not None else None,
                "dataset_name": dataset.name if dataset is not None else None,
                "train_size": train_size,
                "test_size": test_size,
                "total_examples": total_examples,
                "sample_count": sample_count,
                "split_count": split_count,
                "supports_claim_verification": (
                    dataset.supports_claim_verification if dataset is not None else False
                ),
                "verification_label_space": (
                    dataset.verification_label_space if dataset is not None else []
                ),
                "label_space": dataset.label_space if dataset is not None else [],
                "source_kind": source_kind,
                "source_class": dataset.source_class if dataset is not None else None,
                "source_url": source_url,
                "source_file_path": source_file_path,
                "source_dataset_id": source_dataset_id,
                "source_revision": dataset.source_revision if dataset is not None else None,
                "source_license": dataset.source_license if dataset is not None else None,
                "source_fingerprint": dataset.source_fingerprint if dataset is not None else None,
                "source_content_origin": (
                    dataset.source_content_origin if dataset is not None else None
                ),
                "source_content_note": (
                    dataset.source_content_note if dataset is not None else None
                ),
                "source_parent_dataset_id": (
                    dataset.publication_grade_eligibility.get("source_parent_dataset_id")
                    if dataset is not None
                    else None
                ),
                "source_parent_snapshot_fingerprint": (
                    dataset.publication_grade_eligibility.get(
                        "source_parent_snapshot_fingerprint"
                    )
                    if dataset is not None
                    else None
                ),
                "publication_grade_eligibility": (
                    dataset.publication_grade_eligibility if dataset is not None else {}
                ),
                "publication_grade_blockers": (
                    list(dataset.publication_grade_blockers) if dataset is not None else []
                ),
                "publication_grade": publication_grade,
                "provenance_complete": provenance_complete,
                "blockers": run_blockers,
            }
        )
    payload = {
        "card_id": "project_benchmark_card_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_count": len(selected_runs),
        "selected_run_ids": [run.id for run in selected_runs],
        "publication_grade_run_count": sum(1 for item in run_cards if item["publication_grade"]),
        "provenance_complete_run_count": sum(1 for item in run_cards if item["provenance_complete"]),
        "project_publish_gate_passed": project_publish_gate_passed,
        "run_cards": run_cards,
        "blockers": _dedupe(blockers),
        "limitations": [
            "Project-level benchmark evidence is bounded to selected run benchmark cards and persisted splits.",
            "A review bundle may include non-final benchmark evidence, but final publication must preserve blocker status.",
        ],
    }
    return {**payload, "card_fingerprint": _fingerprint(payload)}


def _project_publication_evidence_profile(
    *,
    selected_runs: list[AutoResearchRunRead],
    latest_brief: AutoResearchResearchBriefRead | None,
) -> dict[str, Any]:
    run_profiles: list[dict[str, Any]] = []
    for run in selected_runs:
        spec = run.spec
        dataset = spec.dataset if spec is not None else None
        source_kind = (
            run.benchmark.kind
            if run.benchmark is not None
            else dataset.source_kind
            if dataset is not None
            else None
        )
        source_url = (
            dataset.source_url
            if dataset is not None and dataset.source_url
            else run.benchmark.url
            if run.benchmark is not None
            else None
        )
        source_file_path = run.benchmark.file_path if run.benchmark is not None else None
        source_dataset_id = (
            dataset.source_dataset_id
            if dataset is not None and dataset.source_dataset_id
            else run.benchmark.dataset_id
            if run.benchmark is not None
            else None
        )
        total_examples = (
            (dataset.train_size + dataset.test_size)
            if dataset is not None
            else 0
        )
        sample_count = dataset.sample_count if dataset is not None and dataset.sample_count else total_examples
        split_count = (
            dataset.split_count
            if dataset is not None and dataset.split_count
            else int((dataset.train_size if dataset is not None else 0) > 0)
            + int((dataset.test_size if dataset is not None else 0) > 0)
        )
        provenance_complete = bool(dataset is not None and dataset.provenance_complete)
        observation_profile = _benchmark_observation_profile(run)
        run_profiles.append(
            {
                "run_id": run.id,
                "benchmark_name": spec.benchmark_name if spec is not None else None,
                "train_size": dataset.train_size if dataset is not None else 0,
                "test_size": dataset.test_size if dataset is not None else 0,
                "total_examples": total_examples,
                "sample_count": sample_count,
                "split_count": split_count,
                **observation_profile,
                "supports_claim_verification": (
                    dataset.supports_claim_verification if dataset is not None else False
                ),
                "verification_label_space": (
                    dataset.verification_label_space if dataset is not None else []
                ),
                "label_space": dataset.label_space if dataset is not None else [],
                "input_fields": dataset.input_fields if dataset is not None else [],
                "publication_grade": bool(dataset is not None and dataset.publication_grade),
                "provenance_complete": provenance_complete,
                "source_kind": source_kind,
                "source_class": dataset.source_class if dataset is not None else None,
                "source_url": source_url,
                "source_file_path": source_file_path,
                "source_dataset_id": source_dataset_id,
                "source_revision": dataset.source_revision if dataset is not None else None,
                "source_license": dataset.source_license if dataset is not None else None,
                "source_fingerprint": dataset.source_fingerprint if dataset is not None else None,
                "source_content_origin": (
                    dataset.source_content_origin if dataset is not None else None
                ),
                "source_content_note": (
                    dataset.source_content_note if dataset is not None else None
                ),
                "source_parent_dataset_id": (
                    dataset.publication_grade_eligibility.get("source_parent_dataset_id")
                    if dataset is not None
                    else None
                ),
                "source_parent_snapshot_fingerprint": (
                    dataset.publication_grade_eligibility.get(
                        "source_parent_snapshot_fingerprint"
                    )
                    if dataset is not None
                    else None
                ),
                "publication_grade_blockers": (
                    list(dataset.publication_grade_blockers) if dataset is not None else []
                ),
                "publication_grade_eligibility": (
                    dataset.publication_grade_eligibility if dataset is not None else {}
                ),
            }
        )
    scout = latest_brief.literature_scout if latest_brief is not None else None
    literature_source_counts = dict(scout.source_counts) if scout is not None else {}
    real_literature_count = (
        sum(
            1
            for paper in scout.similar_papers
            if paper.source not in {"fixture", "offline_project_context"}
            and paper.cache_status in {"cache_hit", "network"}
        )
        if scout is not None
        else 0
    )
    real_literature_sources = (
        sorted(
            {
                paper.source
                for paper in scout.similar_papers
                if paper.source not in {"fixture", "offline_project_context"}
                and paper.cache_status in {"cache_hit", "network"}
            }
        )
        if scout is not None
        else []
    )
    benchmark_scale_ready = any(
        item["sample_count"] >= PUBLICATION_MIN_DATASET_EXAMPLES
        for item in run_profiles
    )
    benchmark_provenance_ready = bool(run_profiles) and all(
        item["provenance_complete"] for item in run_profiles
    )
    benchmark_publication_ready = bool(run_profiles) and all(
        item["publication_grade"] for item in run_profiles
    )
    benchmark_source_records = [_benchmark_source_record(item) for item in run_profiles]
    final_publish_candidate_eligible_run_ids = [
        str(record["run_id"])
        for record in benchmark_source_records
        if record.get("final_publish_candidate_eligible")
    ]
    final_publish_candidate_blockers = _dedupe(
        [
            f"{record.get('run_id', 'unknown_run')}: {blocker}"
            for record in benchmark_source_records
            for blocker in record.get("final_publish_candidate_blockers", [])
        ]
    )
    benchmark_final_publish_candidate_ready = bool(run_profiles) and len(
        final_publish_candidate_eligible_run_ids
    ) == len(run_profiles)
    replication_ready = len(selected_runs) >= 2
    independent_source_keys = sorted(
        {
            str(
                item.get("source_parent_dataset_id")
                or item.get("source_dataset_id")
                or item.get("source_url")
                or item.get("source_file_path")
                or item.get("run_id")
            )
            for item in run_profiles
        }
    )
    benchmark_source_independence_ready = len(independent_source_keys) >= 2
    benchmark_source_independence_audit = {
        "selected_run_count": len(run_profiles),
        "independent_source_count": len(independent_source_keys),
        "independent_source_keys": independent_source_keys,
        "complete": benchmark_source_independence_ready,
        "blockers": []
        if benchmark_source_independence_ready
        else [
            (
                "Selected benchmark runs do not cover at least two independent source datasets; "
                "multiple views of the same source release cannot support cross-source final-publish claims."
            )
        ],
        "policy": (
            "Final-publish-candidate source/provenance coverage is assessed per selected run. "
            "Source independence is a separate scientific evidence check: derived views of the same "
            "benchmark release can be useful final-candidate artifacts but do not prove cross-source generalization."
        ),
    }
    literature_ready = real_literature_count > 0 and len(real_literature_sources) >= 2
    blockers = _dedupe(
        [
            *(
                [
                    f"Project benchmark evidence has fewer than {PUBLICATION_MIN_DATASET_EXAMPLES} publication-grade examples in every selected run."
                ]
                if not benchmark_scale_ready
                else []
            ),
            *(
                ["Project benchmark provenance is incomplete for at least one selected run."]
                if not benchmark_provenance_ready
                else []
            ),
            *(
                ["At least one selected run is not marked publication-grade by its benchmark card."]
                if not benchmark_publication_ready
                else []
            ),
            *(
                final_publish_candidate_blockers
                if not benchmark_final_publish_candidate_ready
                else []
            ),
            *(
                ["Project has fewer than two selected runs; cross-run replication is insufficient for publication-grade claims."]
                if not replication_ready
                else []
            ),
            *(
                benchmark_source_independence_audit["blockers"]
                if not benchmark_source_independence_ready
                else []
            ),
            *(
                [
                    (
                        "Project literature scout lacks multi-source real cached or "
                        "network-sourced literature evidence."
                    )
                ]
                if not literature_ready
                else []
            ),
        ]
    )
    return {
        "run_profiles": run_profiles,
        "snapshot_metadata": {
            "selected_run_count": len(run_profiles),
            "total_sample_count": sum(int(item.get("sample_count") or 0) for item in run_profiles),
            "total_query_count": sum(int(item.get("query_count") or 0) for item in run_profiles),
            "total_document_count": sum(int(item.get("document_count") or 0) for item in run_profiles),
            "total_evidence_annotation_count": sum(
                int(item.get("evidence_annotation_count") or 0) for item in run_profiles
            ),
            "total_retrieval_relevance_count": sum(
                int(item.get("retrieval_relevance_count") or 0) for item in run_profiles
            ),
            "split_distribution": {
                split: sum(
                    int(item.get("split_distribution", {}).get(split) or 0)
                    for item in run_profiles
                )
                for split in sorted(
                    {
                        str(split)
                        for item in run_profiles
                        for split in item.get("split_distribution", {})
                    }
                )
            },
            "label_distribution": {
                label: sum(
                    int(item.get("label_distribution", {}).get(label) or 0)
                    for item in run_profiles
                )
                for label in sorted(
                    {
                        str(label)
                        for item in run_profiles
                        for label in item.get("label_distribution", {})
                    }
                )
            },
            "min_split_count": min(
                (int(item.get("split_count") or 0) for item in run_profiles),
                default=0,
            ),
            "frozen_snapshot_run_count": sum(
                1 for item in run_profiles if item.get("source_class") == "frozen_snapshot"
            ),
            "claim_verification_run_count": sum(
                1 for item in run_profiles if item.get("supports_claim_verification")
            ),
            "verification_label_spaces": sorted(
                {
                    str(label)
                    for item in run_profiles
                    for label in item.get("verification_label_space", [])
                }
            ),
        },
        "benchmark_scale_ready": benchmark_scale_ready,
        "benchmark_provenance_ready": benchmark_provenance_ready,
        "benchmark_publication_ready": benchmark_publication_ready,
        "benchmark_final_publish_candidate_ready": benchmark_final_publish_candidate_ready,
        "benchmark_final_publish_candidate_coverage": {
            "selected_run_count": len(benchmark_source_records),
            "minimum_sample_count": FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES,
            "eligible_run_count": len(final_publish_candidate_eligible_run_ids),
            "eligible_run_ids": final_publish_candidate_eligible_run_ids,
            "complete": benchmark_final_publish_candidate_ready,
            "blockers": final_publish_candidate_blockers,
            "policy": FINAL_PUBLISH_CANDIDATE_COVERAGE_POLICY,
        },
        "replication_ready": replication_ready,
        "benchmark_source_independence_ready": benchmark_source_independence_ready,
        "benchmark_source_independence_audit": benchmark_source_independence_audit,
        "literature_ready": literature_ready,
        "real_literature_count": real_literature_count,
        "real_literature_source_count": len(real_literature_sources),
        "real_literature_sources": real_literature_sources,
        "literature_source_counts": literature_source_counts,
        "blockers": blockers,
    }


def _run_statistics_profile(run: AutoResearchRunRead) -> dict[str, Any]:
    artifact = run.artifact
    if artifact is None:
        return {
            "run_id": run.id,
            "has_statistics": False,
            "system_count": 0,
            "aggregate_count": 0,
            "significance_test_count": 0,
            "negative_result_count": 0,
            "failure_case_count": 0,
        }
    aggregate_count = len(artifact.aggregate_system_results)
    significance_count = len(artifact.significance_tests)
    negative_count = len(artifact.negative_results)
    objective_failure_cases = artifact.outputs.get("objective_failure_cases", [])
    output_failure_count = len(objective_failure_cases) if isinstance(objective_failure_cases, list) else 0
    diagnostics = artifact.outputs.get("objective_query_diagnostics", [])
    diagnostic_negative_count = (
        sum(
            1
            for item in diagnostics
            if isinstance(item, dict)
            and (
                item.get("failure_modes")
                or item.get("claim_label") in {"refuted", "not_enough_info"}
                or item.get("retrieval_applicable") is False
            )
        )
        if isinstance(diagnostics, list)
        else 0
    )
    retrieval_ledger = artifact.outputs.get("retrieval_evidence_ledger", [])
    ledger_gap_count = (
        sum(
            1
            for item in retrieval_ledger
            if isinstance(item, dict)
            and (
                item.get("failure_modes")
                or item.get("support_status") in {"partial", "missing"}
            )
        )
        if isinstance(retrieval_ledger, list)
        else 0
    )
    failure_count = (
        len(artifact.failed_trials)
        + output_failure_count
        + diagnostic_negative_count
        + ledger_gap_count
    )
    return {
        "run_id": run.id,
        "primary_metric": artifact.primary_metric,
        "best_system": artifact.best_system,
        "objective_system": artifact.objective_system,
        "objective_score": artifact.objective_score,
        "has_statistics": bool(
            aggregate_count
            or significance_count
            or artifact.per_seed_results
            or artifact.sweep_results
        ),
        "system_count": len(artifact.system_results),
        "aggregate_count": aggregate_count,
        "aggregate_systems": [item.system for item in artifact.aggregate_system_results],
        "significance_test_count": significance_count,
        "significance_tests": [item.model_dump(mode="json") for item in artifact.significance_tests],
        "negative_result_count": negative_count,
        "failure_case_count": failure_count,
        "table_count": len(artifact.tables),
        "metric_names": sorted(
            {
                metric
                for result in artifact.system_results
                for metric in result.metrics
            }
        ),
    }


def _build_project_paper_compiler_evidence_packet(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    latest_brief: AutoResearchResearchBriefRead | None,
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    markdown: str,
    project_paper_sections: list[str],
    project_paper_missing_sections: list[str],
    project_paper_compile_report: AutoResearchPaperCompileReportRead,
    project_paper_revision_actions: list[AutoResearchReviewLoopActionRead],
    project_review_findings: dict[str, Any],
    evidence_profile: dict[str, Any],
) -> dict[str, Any]:
    literature = _literature_insights(latest_brief)
    supported_traces = [trace for trace in traces if trace.support_status == "supported"]
    partial_or_unsupported = [trace for trace in traces if trace.support_status != "supported"]
    statistics_profiles = [_run_statistics_profile(run) for run in selected_runs]
    explicit_result_table_count = sum(
        len(run.artifact.tables)
        for run in selected_runs
        if run.artifact is not None
    )
    derived_statistics_table_count = sum(
        1
        for run in selected_runs
        if run.artifact is not None and run.artifact.system_results
    ) + sum(
        1
        for run in selected_runs
        if run.artifact is not None and run.artifact.aggregate_system_results
    ) + sum(
        1
        for run in selected_runs
        if run.artifact is not None and run.artifact.significance_tests
    )
    artifact_tables_present = explicit_result_table_count > 0
    statistics_tables_present = derived_statistics_table_count > 0
    result_table_coverage = {
        "run_result_table_count": explicit_result_table_count,
        "derived_statistics_table_count": derived_statistics_table_count,
        "manuscript_results_section_present": "## Results" in markdown,
        "artifact_tables_present": artifact_tables_present,
        "statistics_tables_present": statistics_tables_present,
        "result_tables_present": artifact_tables_present or statistics_tables_present,
    }
    statistics_coverage = {
        "run_profiles": statistics_profiles,
        "run_with_statistics_count": sum(1 for item in statistics_profiles if item["has_statistics"]),
        "significance_test_count": sum(item["significance_test_count"] for item in statistics_profiles),
        "negative_result_count": sum(item["negative_result_count"] for item in statistics_profiles),
        "failure_case_count": sum(item["failure_case_count"] for item in statistics_profiles),
    }
    execution_coverage = _project_execution_coverage(
        selected_runs=selected_runs,
        evidence_profile=evidence_profile,
        statistics_profiles=statistics_profiles,
    )
    review_finding_records = [
        item
        for item in project_review_findings.get("findings", [])
        if isinstance(item, dict)
    ]
    review_finding_action_ids = {
        str(item.get("mapped_revision_action_id"))
        for item in review_finding_records
        if item.get("mapped_revision_action_id")
    }
    revision_action_ids = {action.action_id for action in project_paper_revision_actions}
    compiler_audited_terminal_repair_actions = [
        action
        for action in project_paper_revision_actions
        if _project_compiler_has_audited_terminal_repair_attempt(action)
    ]
    compiler_unresolved_revision_actions = [
        action
        for action in project_paper_revision_actions
        if action.status != "completed"
        and not _project_compiler_has_audited_terminal_repair_attempt(action)
    ]
    package_roles = list(PROJECT_SUBMISSION_PACKAGE_ROLES)
    reproducibility_coverage = {
        "source_package_complete": project_paper_compile_report.source_package_complete,
        "compile_report_materialized": True,
        "expected_compile_outputs": list(project_paper_compile_report.expected_outputs),
        "missing_required_inputs": list(project_paper_compile_report.missing_required_inputs),
        "selected_run_count": len(selected_runs),
        "selected_run_result_artifact_count": sum(
            1 for run in selected_runs if run.artifact is not None
        ),
        "selected_run_evidence_ledger_count": sum(
            1 for run in selected_runs if run.evidence_ledger is not None
        ),
        "planned_package_asset_roles": package_roles,
        "planned_package_asset_count": len(package_roles),
        "review_findings_persisted": bool(project_review_findings.get("review_fingerprint")),
        "complete": bool(
            project_paper_compile_report.source_package_complete
            and selected_runs
            and package_roles
            and project_review_findings.get("review_fingerprint")
        ),
    }
    section_coverage_complete = not project_paper_missing_sections
    claim_support_complete = bool(traces) and not partial_or_unsupported
    citation_reference_complete = bool(literature) and "## References" in markdown
    benchmark_provenance_complete = bool(evidence_profile.get("benchmark_provenance_ready"))
    statistics_complete = any(item["has_statistics"] for item in statistics_profiles)
    limitations_complete = "## Limitations" in markdown
    reviewer_revision_complete = not compiler_unresolved_revision_actions
    review_findings_complete = bool(review_finding_records) and (
        review_finding_action_ids == revision_action_ids
    )
    source_complete_with_project_evidence = bool(
        section_coverage_complete
        and traces
        and not partial_or_unsupported
        and reproducibility_coverage["complete"]
    )
    compile_environment_limitations = _dedupe(
        [
            str(blocker)
            for blocker in project_paper_compile_report.evidence_blockers
            if _is_pdf_compile_environment_blocker(blocker)
        ]
    )
    compile_evidence_blockers = [
        blocker
        for blocker in project_paper_compile_report.evidence_blockers
        if not _is_pdf_compile_environment_blocker(blocker)
        and not (
            source_complete_with_project_evidence
            and "paper evidence compiler requires paper markdown, paper plan, and claim ledger"
            in blocker.lower()
        )
    ]
    scientific_evidence_limitations = _dedupe(
        [str(blocker) for blocker in evidence_profile.get("blockers", [])]
    )
    compiler_blockers = _dedupe(
        [
            *project_paper_missing_sections,
            *compile_evidence_blockers,
            *(
                ["Project paper has partial or unsupported claim traces."]
                if not claim_support_complete
                else []
            ),
            *(
                ["Project paper compiler evidence lacks real citation/reference coverage."]
                if not citation_reference_complete
                else []
            ),
            *(
                ["Project paper compiler evidence lacks benchmark provenance coverage."]
                if not benchmark_provenance_complete
                else []
            ),
            *(
                ["Project paper compiler evidence lacks deterministic statistics across selected runs."]
                if not statistics_complete
                else []
            ),
            *(
                ["Project paper compiler evidence lacks linked execution/import replay coverage."]
                if not execution_coverage["complete"]
                else []
            ),
            *execution_coverage.get("blockers", []),
            *(
                ["Project paper compiler evidence lacks manuscript result tables."]
                if not result_table_coverage["result_tables_present"]
                else []
            ),
            *(
                ["Project paper compiler evidence lacks limitations section coverage."]
                if not limitations_complete
                else []
            ),
            *(
                ["Project paper compiler evidence has pending reviewer revision actions."]
                if not reviewer_revision_complete
                else []
            ),
            *(
                ["Project paper compiler evidence lacks persisted review findings."]
                if not review_findings_complete
                else []
            ),
            *(
                ["Project paper compiler evidence lacks reproducibility/source package coverage."]
                if not reproducibility_coverage["complete"]
                else []
            ),
        ]
    )
    payload = {
        "packet_id": "project_paper_compiler_evidence_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_ids": [run.id for run in selected_runs],
        "section_coverage": {
            "required_sections": PROJECT_PAPER_REQUIRED_SECTIONS,
            "present_sections": project_paper_sections,
            "missing_sections": project_paper_missing_sections,
            "complete": section_coverage_complete,
        },
        "claim_support_coverage": {
            "core_claim_count": len(traces),
            "supported_core_claim_count": len(supported_traces),
            "partial_or_unsupported_core_claim_count": len(partial_or_unsupported),
            "claim_traces": [trace.model_dump(mode="json") for trace in traces],
            "complete": claim_support_complete,
        },
        "citation_reference_coverage": {
            "literature_count": len(literature),
            "real_literature_sources": evidence_profile.get("real_literature_sources", []),
            "references_section_present": "## References" in markdown,
            "complete": citation_reference_complete,
        },
        "result_table_coverage": result_table_coverage,
        "benchmark_provenance_coverage": {
            "benchmark_scale_ready": evidence_profile.get("benchmark_scale_ready", False),
            "benchmark_provenance_ready": evidence_profile.get("benchmark_provenance_ready", False),
            "benchmark_publication_ready": evidence_profile.get("benchmark_publication_ready", False),
            "benchmark_final_publish_candidate_ready": evidence_profile.get(
                "benchmark_final_publish_candidate_ready", False
            ),
            "final_publish_candidate_coverage": evidence_profile.get(
                "benchmark_final_publish_candidate_coverage", {}
            ),
            "benchmark_source_independence_ready": evidence_profile.get(
                "benchmark_source_independence_ready", False
            ),
            "benchmark_source_independence_audit": evidence_profile.get(
                "benchmark_source_independence_audit", {}
            ),
            "snapshot_metadata": evidence_profile.get("snapshot_metadata", {}),
            "run_profiles": evidence_profile.get("run_profiles", []),
            "complete": benchmark_provenance_complete,
        },
        "statistics_coverage": {
            **statistics_coverage,
            "complete": statistics_complete,
        },
        "execution_coverage": execution_coverage,
        "limitations_coverage": {
            "limitation_count": len(ledger.limitations),
            "negative_finding_count": len(ledger.negative_findings),
            "limitations_section_present": "## Limitations" in markdown,
            "complete": limitations_complete,
        },
        "reviewer_revision_coverage": {
            "revision_action_count": len(project_paper_revision_actions),
            "completed_revision_action_count": sum(
                1 for action in project_paper_revision_actions if action.status == "completed"
            ),
            "pending_revision_action_count": sum(
                1 for action in project_paper_revision_actions if action.status != "completed"
            ),
            "compiler_unresolved_revision_action_count": len(compiler_unresolved_revision_actions),
            "compiler_unresolved_revision_action_ids": [
                action.action_id for action in compiler_unresolved_revision_actions
            ],
            "audited_terminal_repair_attempt_count": len(
                compiler_audited_terminal_repair_actions
            ),
            "audited_terminal_repair_action_ids": [
                action.action_id for action in compiler_audited_terminal_repair_actions
            ],
            "revision_actions": [action.model_dump(mode="json") for action in project_paper_revision_actions],
            "complete": reviewer_revision_complete,
        },
        "review_findings_coverage": {
            "review_id": project_review_findings.get("review_id"),
            "review_fingerprint": project_review_findings.get("review_fingerprint"),
            "finding_count": int(project_review_findings.get("finding_count") or len(review_finding_records)),
            "mapped_revision_action_count": len(review_finding_action_ids),
            "finding_ids": [
                str(item.get("finding_id"))
                for item in review_finding_records
                if item.get("finding_id")
            ],
            "mapped_revision_action_ids": sorted(review_finding_action_ids),
            "complete": review_findings_complete,
        },
        "reproducibility_coverage": reproducibility_coverage,
        "compile_readiness": {
            "source_package_complete": project_paper_compile_report.source_package_complete,
            "ready_for_compile": project_paper_compile_report.ready_for_compile,
            "all_expected_outputs_materialized": project_paper_compile_report.all_expected_outputs_materialized,
            "expected_outputs": project_paper_compile_report.expected_outputs,
            "materialized_outputs": project_paper_compile_report.materialized_outputs,
            "missing_required_inputs": project_paper_compile_report.missing_required_inputs,
            "missing_required_source_files": project_paper_compile_report.missing_required_source_files,
            "compiler_hint": project_paper_compile_report.compiler_hint,
            "pdf_blockers": compile_environment_limitations,
            "pdf_compile_environment_ready": not compile_environment_limitations,
            "source_package_auditable_without_pdf": bool(
                project_paper_compile_report.source_package_complete
                and compile_environment_limitations
            ),
        },
        "compile_environment_limitations": compile_environment_limitations,
        "scientific_evidence_limitations": scientific_evidence_limitations,
        "complete_policy": (
            "Compiler evidence completeness audits manuscript/source package and evidence coverage. "
            "Local PDF compiler availability and final-publish scientific limitations are reported "
            "separately so they do not masquerade as missing package plumbing."
        ),
        "blockers": compiler_blockers,
        "complete": not compiler_blockers,
    }
    return {**payload, "packet_fingerprint": _fingerprint(payload)}


def _project_publication_evidence_index_payload(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    paper_compiler_evidence_path: Path,
    benchmark_provenance_manifest_path: Path,
    benchmark_provenance_repair_index_path: Path,
    evidence_profile: dict[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    evidence_items = [
        {
            "claim_id": trace.claim_id,
            "claim": trace.claim,
            "support_status": trace.support_status,
            "supporting_run_ids": trace.supporting_run_ids,
            "evidence_refs": trace.evidence_refs,
        }
        for trace in traces
    ]
    benchmark_source_records = [
        _benchmark_source_record(item)
        for item in evidence_profile.get("run_profiles", [])
    ]
    benchmark_evidence_items = [
        {
            "evidence_id": f"benchmark_source:{record.get('run_id')}",
            "evidence_type": "benchmark_source_record",
            "run_id": record.get("run_id"),
            "dataset_id": record.get("dataset_id"),
            "source_class": record.get("source_class"),
            "source_locator": record.get("source_locator"),
            "fingerprint": record.get("fingerprint"),
            "source_content_origin": record.get("source_content_origin"),
            "source_content_note": record.get("source_content_note"),
            "sample_count": record.get("sample_count"),
            "split_count": record.get("split_count"),
            "schema_complete": record["query_document_evidence_schema"]["schema_complete"],
            "publication_grade_eligible": record.get("publication_grade_eligible"),
            "record_complete": record.get("record_complete"),
            "blockers": record.get("record_blockers", []),
            "artifact_refs": [
                str(benchmark_provenance_manifest_path),
                str(benchmark_provenance_repair_index_path),
            ],
        }
        for record in benchmark_source_records
    ]
    payload = {
        "index_id": "project_publication_evidence_index_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_ids": [run.id for run in selected_runs],
        "claim_count": len(evidence_items),
        "evidence_items": evidence_items,
        "benchmark_evidence_items": benchmark_evidence_items,
        "benchmark_evidence_count": len(benchmark_evidence_items),
        "package_evidence_refs": {
            "paper_compiler_evidence": str(paper_compiler_evidence_path),
            "benchmark_provenance_manifest": str(benchmark_provenance_manifest_path),
            "benchmark_provenance_repair_index": str(benchmark_provenance_repair_index_path),
        },
        "conclusion_ledger_fingerprint": ledger.ledger_fingerprint,
        "paper_compiler_evidence_path": str(paper_compiler_evidence_path),
        "blockers": _dedupe(
            [
                *blockers,
                *[
                    f"{item.get('run_id', 'unknown_run')}: {blocker}"
                    for item in benchmark_evidence_items
                    for blocker in item.get("blockers", [])
                ],
            ]
        ),
    }
    return {**payload, "evidence_index_fingerprint": _fingerprint(payload)}


def _project_benchmark_provenance_manifest_payload(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    evidence_profile: dict[str, Any],
) -> dict[str, Any]:
    run_profiles = list(evidence_profile.get("run_profiles", []))
    source_records = [_benchmark_source_record(item) for item in run_profiles]
    record_blockers = _dedupe(
        [
            f"{record.get('run_id', 'unknown_run')}: {blocker}"
            for record in source_records
            for blocker in record.get("record_blockers", [])
        ]
    )
    schema_complete_run_ids = [
        str(record["run_id"])
        for record in source_records
        if record["query_document_evidence_schema"]["schema_complete"]
    ]
    schema_blockers = _dedupe(
        [
            f"{record.get('run_id', 'unknown_run')}: benchmark schema missing {role}"
            for record in source_records
            for role in record["query_document_evidence_schema"]["missing_schema_roles"]
        ]
    )
    final_publish_candidate_eligible_run_ids = [
        str(record["run_id"])
        for record in source_records
        if record.get("final_publish_candidate_eligible")
    ]
    final_publish_candidate_blockers = _dedupe(
        [
            f"{record.get('run_id', 'unknown_run')}: {blocker}"
            for record in source_records
            for blocker in record.get("final_publish_candidate_blockers", [])
        ]
    )
    observation_blockers: list[str] = []
    for record in source_records:
        run_id = record.get("run_id", "unknown_run")
        if int(record.get("query_count") or 0) <= 0:
            observation_blockers.append(f"{run_id}: missing query_count")
        if int(record.get("document_count") or 0) <= 0:
            observation_blockers.append(f"{run_id}: missing document_count")
        if bool(record.get("supports_claim_verification")):
            if int(record.get("evidence_annotation_count") or 0) <= 0:
                observation_blockers.append(f"{run_id}: missing evidence_annotation_count")
        elif int(record.get("retrieval_relevance_count") or 0) <= 0:
            observation_blockers.append(
                f"{run_id}: missing retrieval relevance annotations"
            )
    observation_blockers = _dedupe(observation_blockers)
    benchmark_source_independence_audit = (
        evidence_profile.get("benchmark_source_independence_audit", {})
        if isinstance(evidence_profile.get("benchmark_source_independence_audit", {}), dict)
        else {}
    )
    blockers = _dedupe(
        [
            *record_blockers,
            *observation_blockers,
            *final_publish_candidate_blockers,
        ]
    )
    payload = {
        "manifest_id": "project_benchmark_provenance_manifest_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_ids": [run.id for run in selected_runs],
        "run_profiles": run_profiles,
        "benchmark_source_records": source_records,
        "schema_coverage": {
            "selected_run_count": len(source_records),
            "schema_complete_run_count": len(schema_complete_run_ids),
            "schema_complete_run_ids": schema_complete_run_ids,
            "schema_coverage_complete": bool(source_records)
            and len(schema_complete_run_ids) == len(source_records),
            "schema_blockers": schema_blockers,
            "policy": PROJECT_BENCHMARK_SCHEMA_COVERAGE_POLICY,
        },
        "source_observation_coverage": {
            "selected_run_count": len(source_records),
            "query_count_by_run": {
                str(record.get("run_id")): int(record.get("query_count") or 0)
                for record in source_records
            },
            "document_count_by_run": {
                str(record.get("run_id")): int(record.get("document_count") or 0)
                for record in source_records
            },
            "evidence_annotation_count_by_run": {
                str(record.get("run_id")): int(record.get("evidence_annotation_count") or 0)
                for record in source_records
            },
            "retrieval_relevance_count_by_run": {
                str(record.get("run_id")): int(record.get("retrieval_relevance_count") or 0)
                for record in source_records
            },
            "required_observation_roles_by_run": {
                str(record.get("run_id")): list(record.get("required_observation_roles", []))
                for record in source_records
            },
            "split_distribution": evidence_profile.get("snapshot_metadata", {}).get("split_distribution", {}),
            "label_distribution": evidence_profile.get("snapshot_metadata", {}).get("label_distribution", {}),
            "observation_coverage_complete": bool(source_records) and not observation_blockers,
            "observation_blockers": observation_blockers,
            "policy": PROJECT_BENCHMARK_OBSERVATION_COVERAGE_POLICY,
        },
        "final_publish_candidate_coverage": {
            "selected_run_count": len(source_records),
            "minimum_sample_count": FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES,
            "eligible_run_count": len(final_publish_candidate_eligible_run_ids),
            "eligible_run_ids": final_publish_candidate_eligible_run_ids,
            "complete": bool(source_records)
            and len(final_publish_candidate_eligible_run_ids) == len(source_records),
            "blockers": final_publish_candidate_blockers,
            "policy": FINAL_PUBLISH_CANDIDATE_COVERAGE_POLICY,
        },
        "benchmark_source_independence_audit": benchmark_source_independence_audit,
        "snapshot_metadata": evidence_profile.get("snapshot_metadata", {}),
        "benchmark_scale_ready": evidence_profile.get("benchmark_scale_ready", False),
        "benchmark_provenance_ready": evidence_profile.get("benchmark_provenance_ready", False),
        "benchmark_publication_ready": evidence_profile.get("benchmark_publication_ready", False),
        "complete": bool(source_records) and not blockers,
        "blockers": blockers,
        "policy": (
            "The manifest records benchmark provenance and claim-evidence schema from selected run artifacts. "
            "Missing schema, source locator, license, revision, fingerprint, scale, or publication eligibility "
            "remains a blocker and is not repaired through metadata-only upgrades."
        ),
    }
    return {**payload, "provenance_fingerprint": _fingerprint(payload)}


def _project_statistics_report_payload(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    paper_compiler_evidence: dict[str, Any],
    repair_execution_log: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def _metric_scope(metric: str) -> str:
        if metric in PROJECT_STATISTICS_RETRIEVAL_METRICS:
            return "retrieval"
        if metric in PROJECT_STATISTICS_VERIFICATION_METRICS:
            return "claim_verification"
        if metric in PROJECT_STATISTICS_REPAIR_METRICS:
            return "repair_router"
        return "general"

    def _metric_required_for_method(
        metric: str,
        *,
        method_config: dict[str, Any],
        supports_claim_verification: bool,
    ) -> bool:
        if metric in PROJECT_STATISTICS_RETRIEVAL_METRICS:
            return True
        if metric in PROJECT_STATISTICS_VERIFICATION_METRICS:
            return supports_claim_verification and bool(
                method_config.get("uses_verification", True)
            )
        if metric in PROJECT_STATISTICS_REPAIR_METRICS:
            return (
                supports_claim_verification
                and bool(method_config.get("uses_verification", True))
                and bool(method_config.get("repair_router_enabled", False))
            )
        return True

    def _diagnostic_row(
        *,
        run_id: str,
        system: str | None,
        index: int,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        metric_keys = [
            "reciprocal_rank",
            "recall_at_1",
            "recall_at_10",
            "ndcg_at_10",
            "evidence_coverage",
            "verification_correct",
            "unsupported_claim_precision",
            "unsupported_claim_recall",
            "abstention_correct",
            "repair_precision",
            "repair_recall",
        ]
        metric_values = {
            key: item.get(key)
            for key in metric_keys
            if key in item
        }
        failure_modes = list(item.get("failure_modes") or [])
        negative_evidence_categories = _negative_category_list(
            item.get("negative_evidence_categories")
        )
        claim_label = item.get("claim_label")
        return {
            "run_id": run_id,
            "system": system,
            "query_index": index,
            "claim_id": item.get("claim_id"),
            "query": item.get("query"),
            "claim_label": claim_label,
            "predicted_claim_label": item.get("predicted_claim_label"),
            "retrieval_applicable": bool(item.get("retrieval_applicable")),
            "relevant_id_count": len(item.get("relevant_ids", []) or []),
            "ranked_id_count_at_10": len(item.get("ranked_ids_at_10", []) or []),
            "metric_values": metric_values,
            "repair_needed": bool(item.get("repair_needed")),
            "repair_predicted": bool(item.get("repair_predicted")),
            "repair_true_positive": item.get("repair_true_positive"),
            "repair_false_positive": item.get("repair_false_positive"),
            "repair_false_negative": item.get("repair_false_negative"),
            "failure_modes": failure_modes,
            "negative_evidence_categories": negative_evidence_categories,
            "negative_or_ambiguous": bool(
                failure_modes
                or negative_evidence_categories
                or claim_label in {"refuted", "not_enough_info"}
                or item.get("retrieval_applicable") is False
            ),
        }

    statistics_coverage = paper_compiler_evidence.get("statistics_coverage", {})
    execution_coverage = paper_compiler_evidence.get("execution_coverage", {})
    per_method_metric_table = []
    aggregate_metric_table = []
    per_query_diagnostic_table = []
    metric_coverage_records = []
    replication_records = []
    split_metric_table = []
    split_evaluation_records = []
    paired_comparisons = []
    confidence_intervals = []
    effect_size_table = []
    negative_evidence_summary = []
    for run in selected_runs:
        artifact = run.artifact
        if artifact is None:
            negative_evidence_summary.append(
                {
                    "run_id": run.id,
                    "kind": "missing_result_artifact",
                    "detail": "No result artifact is available for statistics reporting.",
                }
            )
            continue
        outputs = artifact.outputs or {}
        method_configs = outputs.get("method_configs", {})
        if not isinstance(method_configs, dict):
            method_configs = {}
        supports_claim_verification = bool(
            artifact.environment.get("supports_claim_verification")
        )
        output_split_evaluations = outputs.get("split_evaluations", [])
        split_fingerprints_by_split = {
            str(item.get("split")): item.get("split_fingerprint")
            for item in output_split_evaluations
            if isinstance(item, dict) and item.get("split")
        } if isinstance(output_split_evaluations, list) else {}
        run_split_evaluation_records = []
        for sweep in artifact.sweep_results:
            split_kind = str(sweep.params.get("split_kind") or "")
            if split_kind != "benchmark_payload_split" and not sweep.label.startswith("benchmark_split_"):
                continue
            split_label = str(
                sweep.params.get("split") or sweep.label.removeprefix("benchmark_split_")
            )
            metric_names = sorted(
                {
                    metric
                    for aggregate in sweep.aggregate_system_results
                    for metric in aggregate.mean_metrics
                }
            )
            split_record = {
                "run_id": run.id,
                "label": sweep.label,
                "split": split_label,
                "status": sweep.status,
                "example_count": int(sweep.params.get("example_count") or 0),
                "seed_count": sweep.seed_count,
                "successful_seed_count": sweep.successful_seed_count,
                "aggregate_system_count": len(sweep.aggregate_system_results),
                "objective_system": sweep.objective_system,
                "objective_score_mean": sweep.objective_score_mean,
                "metric_names": metric_names,
                "split_fingerprint": split_fingerprints_by_split.get(split_label),
            }
            run_split_evaluation_records.append(split_record)
            for aggregate in sweep.aggregate_system_results:
                split_metric_table.append(
                    {
                        "run_id": run.id,
                        "split": split_label,
                        "system": aggregate.system,
                        "mean_metrics": dict(aggregate.mean_metrics),
                        "std_metrics": dict(aggregate.std_metrics),
                        "min_metrics": dict(aggregate.min_metrics),
                        "max_metrics": dict(aggregate.max_metrics),
                        "sample_count": aggregate.sample_count,
                        "confidence_intervals": {
                            metric: interval.model_dump(mode="json")
                            for metric, interval in aggregate.confidence_intervals.items()
                        },
                    }
                )
        split_evaluation_records.extend(run_split_evaluation_records)
        run_split_labels = sorted(
            {
                str(item.get("split"))
                for item in run_split_evaluation_records
                if item.get("split")
            }
        )
        run_multi_split_ready = (
            len(run_split_labels) >= 2
            and all(str(item.get("status")) == "done" for item in run_split_evaluation_records)
            and all(int(item.get("example_count") or 0) > 0 for item in run_split_evaluation_records)
        )
        replication_records.append(
            {
                "run_id": run.id,
                "per_seed_result_count": len(artifact.per_seed_results),
                "sweep_result_count": len(artifact.sweep_results),
                "split_evaluation_count": len(run_split_evaluation_records),
                "split_labels": run_split_labels,
                "split_example_count": sum(
                    int(item.get("example_count") or 0)
                    for item in run_split_evaluation_records
                ),
                "aggregate_system_count": len(artifact.aggregate_system_results),
                "significance_test_count": len(artifact.significance_tests),
                "objective_query_diagnostic_count": len(
                    outputs.get("objective_query_diagnostics", [])
                )
                if isinstance(outputs.get("objective_query_diagnostics"), list)
                else 0,
                "supports_claim_verification": supports_claim_verification,
                "deterministic_paired_query_comparison_ready": bool(
                    artifact.significance_tests
                ),
                "deterministic_multi_split_ready": run_multi_split_ready,
            }
        )
        for result in artifact.system_results:
            method_config = (
                method_configs.get(result.system, {})
                if isinstance(method_configs.get(result.system, {}), dict)
                else {}
            )
            per_method_metric_table.append(
                {
                    "run_id": run.id,
                    "system": result.system,
                    "metrics": dict(result.metrics),
                    "notes": result.notes,
                }
            )
            for metric in PROJECT_STATISTICS_REQUIRED_METRICS:
                required = _metric_required_for_method(
                    metric,
                    method_config=method_config,
                    supports_claim_verification=supports_claim_verification,
                )
                observed = metric in result.metrics
                metric_coverage_records.append(
                    {
                        "run_id": run.id,
                        "system": result.system,
                        "metric": metric,
                        "scope": _metric_scope(metric),
                        "required": required,
                        "observed": observed,
                        "method_ladder_role": method_config.get("ladder_role"),
                        "uses_verification": bool(
                            method_config.get("uses_verification", True)
                        ),
                        "repair_router_enabled": bool(
                            method_config.get("repair_router_enabled", False)
                        ),
                    }
                )
        for result in artifact.aggregate_system_results:
            aggregate_row = {
                "run_id": run.id,
                "system": result.system,
                "mean_metrics": dict(result.mean_metrics),
                "std_metrics": dict(result.std_metrics),
                "min_metrics": dict(result.min_metrics),
                "max_metrics": dict(result.max_metrics),
                "sample_count": result.sample_count,
                "confidence_intervals": {
                    metric: interval.model_dump(mode="json")
                    for metric, interval in result.confidence_intervals.items()
                },
            }
            aggregate_metric_table.append(aggregate_row)
            for metric, interval in result.confidence_intervals.items():
                confidence_intervals.append(
                    {
                        "run_id": run.id,
                        "system": result.system,
                        "metric": metric,
                        **interval.model_dump(mode="json"),
                    }
                )
        for test in artifact.significance_tests:
            comparison = {
                "run_id": run.id,
                **test.model_dump(mode="json"),
            }
            paired_comparisons.append(comparison)
            effect_size_table.append(
                {
                    "run_id": run.id,
                    "metric": comparison.get("metric"),
                    "candidate": comparison.get("candidate"),
                    "comparator": comparison.get("comparator"),
                    "effect_size": comparison.get("effect_size"),
                    "sample_count": comparison.get("sample_count"),
                    "method": comparison.get("method"),
                    "p_value": comparison.get("p_value"),
                    "adjusted_p_value": comparison.get("adjusted_p_value"),
                    "correction": comparison.get("correction"),
                    "significant": comparison.get("significant"),
                }
            )
        objective_failures = outputs.get("objective_failure_cases", [])
        if isinstance(objective_failures, list):
            for index, item in enumerate(objective_failures, start=1):
                negative_evidence_summary.append(
                    {
                        "run_id": run.id,
                        "kind": "objective_failure_case",
                        "case_id": f"{run.id}:objective_failure:{index}",
                        "detail": item,
                    }
                )
        diagnostics = outputs.get("objective_query_diagnostics", [])
        if isinstance(diagnostics, list):
            for index, item in enumerate(diagnostics, start=1):
                if not isinstance(item, dict):
                    continue
                per_query_diagnostic_table.append(
                    _diagnostic_row(
                        run_id=run.id,
                        system=artifact.objective_system,
                        index=index,
                        item=item,
                    )
                )
                if not (
                    item.get("failure_modes")
                    or item.get("claim_label") in {"refuted", "not_enough_info"}
                    or item.get("retrieval_applicable") is False
                ):
                    continue
                negative_evidence_summary.append(
                    {
                        "run_id": run.id,
                        "kind": "query_negative_or_ambiguous_evidence",
                        "case_id": str(item.get("claim_id") or f"{run.id}:query:{index}"),
                        "claim_label": item.get("claim_label"),
                        "predicted_claim_label": item.get("predicted_claim_label"),
                        "failure_modes": item.get("failure_modes", []),
                        "negative_evidence_categories": _negative_category_list(
                            item.get("negative_evidence_categories")
                        ),
                    }
                )
        for index, item in enumerate(artifact.negative_results, start=1):
            negative_evidence_summary.append(
                {
                    "run_id": run.id,
                    "kind": "negative_result",
                    "case_id": f"{run.id}:negative_result:{index}",
                    "detail": item.model_dump(mode="json"),
                }
            )
        for index, item in enumerate(artifact.failed_trials, start=1):
            negative_evidence_summary.append(
                {
                    "run_id": run.id,
                    "kind": "failed_trial",
                    "case_id": f"{run.id}:failed_trial:{index}",
                    "detail": item.model_dump(mode="json"),
                    "negative_evidence_categories": (
                        ["failed_or_blocked_repair_attempt", "runtime_failure"]
                        if _is_runtime_failure_record(item.model_dump(mode="json"))
                        else ["failed_or_blocked_repair_attempt"]
                    ),
                }
            )
    phase6_negative_entries = _project_negative_evidence_phase6_entries(
        selected_runs=selected_runs,
        repair_execution_log=repair_execution_log,
    )
    phase6_negative_summary = _phase6_category_summary(phase6_negative_entries)
    has_significance = bool(paired_comparisons)
    has_ci = bool(confidence_intervals)
    correction_required = [
        item for item in paired_comparisons if int(item.get("family_size") or 1) > 1
    ]
    correction_missing = [
        item for item in correction_required if not item.get("correction")
    ]
    multiple_comparison_correction = {
        "required": bool(correction_required),
        "comparison_count_requiring_correction": len(correction_required),
        "corrected_comparison_count": len(correction_required) - len(correction_missing),
        "missing_correction_count": len(correction_missing),
        "corrections": sorted(
            {
                str(item.get("correction"))
                for item in paired_comparisons
                if item.get("correction")
            }
        ),
        "complete": not correction_missing,
    }
    metric_coverage_table = []
    missing_metric_records = []
    for metric in PROJECT_STATISTICS_REQUIRED_METRICS:
        records = [item for item in metric_coverage_records if item["metric"] == metric]
        required_records = [item for item in records if item["required"]]
        observed_records = [item for item in required_records if item["observed"]]
        missing_records = [item for item in required_records if not item["observed"]]
        missing_metric_records.extend(missing_records)
        metric_coverage_table.append(
            {
                "metric": metric,
                "scope": _metric_scope(metric),
                "required": bool(required_records),
                "covered": not missing_records,
                "required_method_count": len(required_records),
                "observed_method_count": len(observed_records),
                "missing_method_count": len(missing_records),
                "observed_systems": sorted(
                    {
                        f"{item['run_id']}:{item['system']}"
                        for item in observed_records
                    }
                ),
                "missing_systems": sorted(
                    {
                        f"{item['run_id']}:{item['system']}"
                        for item in missing_records
                    }
                ),
            }
        )
    metric_coverage = {
        "required_metrics": PROJECT_STATISTICS_REQUIRED_METRICS,
        "metric_table": metric_coverage_table,
        "record_count": len(metric_coverage_records),
        "complete": not missing_metric_records,
        "missing_required_metrics": sorted(
            {str(item["metric"]) for item in missing_metric_records}
        ),
        "missing_required_metric_records": missing_metric_records,
        "policy": (
            "Retrieval metrics are required for every method. Claim-verification metrics are "
            "required only when the benchmark supports claim verification and the method config "
            "uses verification. Repair precision/recall are required only for active repair-router "
            "methods with verification enabled."
        ),
    }
    max_completed_seed_count = max(
        (int(item.get("per_seed_result_count") or 0) for item in replication_records),
        default=0,
    )
    max_completed_split_count = max(
        (int(item.get("split_evaluation_count") or 0) for item in replication_records),
        default=0,
    )
    multi_split_ready = bool(replication_records) and all(
        bool(item.get("deterministic_multi_split_ready"))
        for item in replication_records
    )
    replication_summary = {
        "selected_run_count": len(selected_runs),
        "run_records": replication_records,
        "max_completed_seed_count": max_completed_seed_count,
        "max_completed_split_count": max_completed_split_count,
        "multi_seed_ready": max_completed_seed_count >= 3,
        "multi_split_ready": multi_split_ready,
        "split_evaluation_count": len(split_evaluation_records),
        "split_labels": sorted(
            {
                str(item.get("split"))
                for item in split_evaluation_records
                if item.get("split")
            }
        ),
        "deterministic_paired_query_comparison_ready": has_significance,
        "confidence_interval_ready": has_ci,
        "final_publish_replication_ready": max_completed_seed_count >= 3
        or multi_split_ready,
        "policy": (
            "A deterministic paired query test can support scoped case-study claims. "
            "Deterministic train/test split-level evaluation can satisfy the statistics "
            "replication-evidence requirement, while source independence and negative evidence "
            "still bound the final claim ceiling."
        ),
    }
    deterministic_equivalents = (
        [
            {
                "kind": "deterministic_paired_comparison",
                "comparison_count": len(paired_comparisons),
                "detail": "Paired/significance comparisons are recorded as deterministic statistical evidence where confidence intervals are unavailable.",
            }
        ]
        if has_significance and not has_ci
        else []
    )
    has_negative_evidence = bool(negative_evidence_summary or phase6_negative_entries)
    benchmark_publication_ready = bool(
        paper_compiler_evidence.get("benchmark_provenance_coverage", {}).get(
            "benchmark_publication_ready"
        )
    )
    benchmark_final_candidate_ready = bool(
        paper_compiler_evidence.get("benchmark_provenance_coverage", {}).get(
            "benchmark_final_publish_candidate_ready"
        )
    )
    benchmark_source_independence_ready = bool(
        paper_compiler_evidence.get("benchmark_provenance_coverage", {}).get(
            "benchmark_source_independence_ready"
        )
    )
    claim_support_complete = bool(
        paper_compiler_evidence.get("claim_support_coverage", {}).get("complete")
    )
    claim_ceiling_recommendation = (
        "final_publish_claim"
        if (
            statistics_coverage.get("complete")
            and has_significance
            and has_ci
            and replication_summary["final_publish_replication_ready"]
            and not has_negative_evidence
            and benchmark_publication_ready
            and benchmark_final_candidate_ready
            and benchmark_source_independence_ready
            and claim_support_complete
        )
        else "workshop_case_study_claim"
        if statistics_coverage.get("complete") and has_significance
        else "technical_report_only"
    )
    final_publish_statistics_blockers = _dedupe(
        [
            *(
                ["Statistics report lacks a per-query diagnostic table from execution outputs."]
                if not per_query_diagnostic_table
                else []
            ),
            *(
                [
                    "Statistics metric coverage is incomplete for required retrieval, verification, or repair-router metrics."
                ]
                if not metric_coverage["complete"]
                else []
            ),
            *(
                ["No deterministic paired/significance comparison is available."]
                if not has_significance
                else []
            ),
            *(
                ["No confidence interval or deterministic equivalent is available."]
                if not has_ci and not deterministic_equivalents
                else []
            ),
            *(
                ["Paired comparisons do not expose effect sizes."]
                if not effect_size_table
                else []
            ),
            *(
                ["Multiple-comparison correction is missing for at least one comparison family."]
                if correction_missing
                else []
            ),
            *(
                [
                    "Current selected runs lack deterministic multi-seed or multi-split replication; paired-query evidence alone is scoped evidence only."
                ]
                if not replication_summary["final_publish_replication_ready"]
                else []
            ),
            *(
                ["Negative or ambiguous evidence is present; final-publish claims require stronger residual-failure analysis or additional evidence."]
                if has_negative_evidence
                else []
            ),
            *(
                [
                    "Selected benchmark evidence does not cover at least two independent source datasets, so statistics cannot support cross-source final-publish claims."
                ]
                if not benchmark_source_independence_ready
                else []
            ),
            *(
                [
                    "Benchmark publication-grade source/provenance coverage remains incomplete, so statistics cannot raise the claim ceiling to final publish."
                ]
                if not benchmark_publication_ready
                else []
            ),
            *(
                [
                    "Benchmark final-publish-candidate coverage remains incomplete, so statistics cannot raise the claim ceiling to final publish."
                ]
                if not benchmark_final_candidate_ready
                else []
            ),
            *(
                [
                    "Claim support remains incomplete, so statistics cannot raise the claim ceiling to final publish."
                ]
                if not claim_support_complete
                else []
            ),
        ]
    )
    statistics_limitations = _dedupe(
        [
            *(
                ["No per-method metric table is available from selected run artifacts."]
                if not per_method_metric_table
                else []
            ),
            *(
                ["No aggregate metric table is available from selected run artifacts."]
                if not aggregate_metric_table
                else []
            ),
            *(
                ["No deterministic paired/significance comparison is available."]
                if not has_significance
                else []
            ),
            *(
                ["No confidence interval or deterministic equivalent is available."]
                if not has_ci and not deterministic_equivalents
                else []
            ),
            *(
                ["Negative or ambiguous evidence is present; claim strength must remain scoped."]
                if has_negative_evidence
                else []
            ),
            *(
                [
                    "Claim ceiling is below final publish because selected benchmark sources are not independent."
                ]
                if not benchmark_source_independence_ready
                else []
            ),
            *(
                [
                    "Claim ceiling is below final publish because benchmark publication-grade source/provenance readiness is incomplete."
                ]
                if not benchmark_publication_ready
                else []
            ),
            *(
                [
                    "Claim ceiling is below final publish because benchmark final-candidate coverage is incomplete."
                ]
                if not benchmark_final_candidate_ready
                else []
            ),
            *(
                [
                    "Claim ceiling is below final publish because claim support is incomplete."
                ]
                if not claim_support_complete
                else []
            ),
            *final_publish_statistics_blockers,
            *(
                ["Statistics evidence is not fully linked to deterministic execution/import replay outputs."]
                if not execution_coverage.get("complete")
                else []
            ),
        ]
    )
    payload = {
        "report_id": "project_statistics_report_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_ids": [run.id for run in selected_runs],
        "statistics_coverage": statistics_coverage,
        "execution_coverage": {
            "complete": bool(execution_coverage.get("complete")),
            "complete_execution_profile_count": int(
                execution_coverage.get("complete_execution_profile_count") or 0
            ),
            "execution_source_counts": execution_coverage.get("execution_source_counts", {}),
            "imported_result_replay_run_ids": execution_coverage.get("imported_result_replay_run_ids", []),
            "materialized_execution_run_ids": execution_coverage.get("materialized_execution_run_ids", []),
            "execution_output_artifact_refs": execution_coverage.get("execution_output_artifact_refs", []),
            "metrics_artifact_refs": execution_coverage.get("metrics_artifact_refs", []),
            "evidence_ledger_artifact_refs": execution_coverage.get("evidence_ledger_artifact_refs", []),
            "negative_evidence_artifact_refs": execution_coverage.get("negative_evidence_artifact_refs", []),
            "blockers": execution_coverage.get("blockers", []),
        },
        "per_method_metric_table": per_method_metric_table,
        "aggregate_metric_table": aggregate_metric_table,
        "split_metric_table": split_metric_table,
        "split_evaluations": split_evaluation_records,
        "per_query_diagnostic_table": per_query_diagnostic_table,
        "metric_coverage": metric_coverage,
        "paired_comparisons": paired_comparisons,
        "confidence_intervals": confidence_intervals,
        "deterministic_equivalents": deterministic_equivalents,
        "effect_size_table": effect_size_table,
        "multiple_comparison_correction": multiple_comparison_correction,
        "replication_summary": replication_summary,
        "negative_evidence_summary": negative_evidence_summary,
        "negative_evidence_categories": sorted(
            phase6_negative_summary["category_counts"].keys()
        ),
        "phase6_negative_evidence_summary": phase6_negative_summary,
        "phase6_negative_evidence_entry_count": len(phase6_negative_entries),
        "claim_ceiling_recommendation": claim_ceiling_recommendation,
        "statistics_limitations": statistics_limitations,
        "final_publish_statistics_blockers": final_publish_statistics_blockers,
        "complete": bool(statistics_coverage.get("complete") and execution_coverage.get("complete")),
        "blockers": (
            []
            if statistics_coverage.get("complete") and execution_coverage.get("complete")
            else _dedupe(
                [
                    *(
                        ["Project statistics report lacks deterministic aggregate, split, seed, or significance evidence."]
                        if not statistics_coverage.get("complete")
                        else []
                    ),
                    *(
                        ["Project statistics report lacks linked execution/import replay evidence."]
                        if not execution_coverage.get("complete")
                        else []
                    ),
                    *execution_coverage.get("blockers", []),
                ]
            )
        ),
    }
    return {**payload, "statistics_fingerprint": _fingerprint(payload)}


def _project_negative_evidence_report_payload(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    statistics_report: dict[str, Any],
    experiment_repair_index: dict[str, Any],
    repair_execution_log: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    phase6_entries = _project_negative_evidence_phase6_entries(
        selected_runs=selected_runs,
        ledger=ledger,
        traces=traces,
        experiment_repair_index=experiment_repair_index,
        repair_execution_log=repair_execution_log,
    )
    for run in selected_runs:
        if run.artifact is not None:
            for index, item in enumerate(run.artifact.negative_results, start=1):
                entries.append(
                    {
                        "entry_id": f"{run.id}:negative_result:{index}",
                        "run_id": run.id,
                        "evidence_kind": "negative_result",
                        "category": item.scope,
                        "subject": item.subject,
                        "reference": item.reference,
                        "metric": item.metric,
                        "observed_score": item.observed_score,
                        "reference_score": item.reference_score,
                        "delta": item.delta,
                        "detail": item.detail,
                        "phase6_categories": [
                            entry["category"]
                            for entry in phase6_entries
                            if entry.get("entry_id") == f"{run.id}:phase6_negative_result:{index}"
                        ],
                        "artifact_ref": f"{run.id}:artifact:negative_results:{index}",
                        "blocks_publication": False,
                    }
                )
            for index, item in enumerate(run.artifact.failed_trials, start=1):
                entries.append(
                    {
                        "entry_id": f"{run.id}:failed_trial:{index}",
                        "run_id": run.id,
                        "evidence_kind": "failed_trial",
                        "category": item.category,
                        "subject": item.sweep_label,
                        "reference": item.scope,
                        "metric": "runtime_contract",
                        "detail": item.detail,
                        "diagnosis": item.diagnosis,
                        "likely_fix": item.likely_fix,
                        "returncode": item.returncode,
                        "phase6_categories": (
                            ["failed_repair_attempt", "failed_or_blocked_repair_attempt", "runtime_failure"]
                            if _is_runtime_failure_record(item.model_dump(mode="json"))
                            else ["failed_repair_attempt", "failed_or_blocked_repair_attempt"]
                        ),
                        "artifact_ref": f"{run.id}:artifact:failed_trials:{index}",
                        "blocks_publication": True,
                    }
                )
        if run.evidence_ledger is not None:
            for entry in run.evidence_ledger.entries:
                if entry.support_status == "missing":
                    entries.append(
                        {
                            "entry_id": f"{run.id}:retrieval_miss:{entry.evidence_id}",
                            "run_id": run.id,
                            "evidence_kind": "retrieval_miss",
                            "category": entry.evidence_kind,
                            "subject": entry.claim,
                            "reference": entry.artifact_ref,
                            "metric": "claim_evidence_support",
                            "detail": entry.claim,
                            "phase6_categories": ["retrieval_miss"],
                            "artifact_ref": f"{run.id}:evidence_ledger:{entry.evidence_id}",
                            "blocks_publication": True,
                        }
                    )
        if run.claim_evidence_matrix is not None:
            for claim in run.claim_evidence_matrix.entries:
                if claim.support_status == "unsupported":
                    entries.append(
                        {
                            "entry_id": f"{run.id}:unsupported_claim:{claim.claim_id}",
                            "run_id": run.id,
                            "evidence_kind": "unsupported_claim",
                            "category": claim.category,
                            "subject": claim.claim,
                            "reference": claim.section_hint,
                            "metric": "claim_support",
                            "detail": "; ".join(claim.gaps) if claim.gaps else "Claim lacks supporting evidence.",
                            "phase6_categories": ["claim_support_gap"],
                            "artifact_ref": f"{run.id}:claim_matrix:{claim.claim_id}",
                            "blocks_publication": True,
                        }
                    )
    for item in ledger.negative_findings:
        entries.append(
            {
                "entry_id": item.conclusion_id,
                "run_id": ",".join(item.supporting_run_ids),
                "evidence_kind": "project_negative_finding",
                "category": item.kind,
                "subject": item.text,
                "reference": ",".join(item.evidence_refs),
                "metric": "project_conclusion",
                "detail": "; ".join(item.caveats) if item.caveats else item.text,
                "phase6_categories": ["project_negative_finding"],
                "artifact_ref": f"project_conclusion_ledger:{item.conclusion_id}",
                "blocks_publication": False,
            }
        )
    for trace in traces:
        if trace.support_status != "supported":
            entries.append(
                {
                    "entry_id": f"{trace.claim_id}:claim_support_gap",
                    "run_id": ",".join(trace.supporting_run_ids),
                    "evidence_kind": "claim_support_gap",
                    "category": trace.support_status,
                    "subject": trace.claim,
                    "reference": trace.source_conclusion_id,
                    "metric": "project_claim_support",
                    "detail": "; ".join(trace.unsupported_reasons)
                    if trace.unsupported_reasons
                    else "Project claim is not fully supported.",
                    "phase6_categories": ["claim_support_gap"],
                    "artifact_ref": f"project_claim_trace:{trace.claim_id}",
                    "blocks_publication": trace.strong_claim or trace.support_status == "unsupported",
                }
            )
    repair_blockers = list(experiment_repair_index.get("blockers", []))
    for index, blocker in enumerate(repair_blockers, start=1):
        entries.append(
            {
                "entry_id": f"experiment_repair_blocker:{index}",
                "run_id": "",
                "evidence_kind": "blocked_repair",
                "category": "experiment_repair",
                "subject": blocker,
                "reference": "experiment_repair_index",
                "metric": "repair_completion",
                "detail": blocker,
                "phase6_categories": [
                    "blocked_repair_attempt",
                    "failed_or_blocked_repair_attempt",
                ],
                "artifact_ref": "project_experiment_repair_index_json",
                "blocks_publication": True,
            }
        )
    existing_entry_ids = {str(entry.get("entry_id")) for entry in entries}
    entries.extend(
        entry
        for entry in phase6_entries
        if str(entry.get("entry_id")) not in existing_entry_ids
    )
    categories = sorted({str(entry["evidence_kind"]) for entry in entries})
    phase6_summary = _phase6_category_summary(entries)
    blocking_entries = [entry for entry in entries if entry["blocks_publication"]]
    payload = {
        "report_id": "project_negative_evidence_report_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_ids": [run.id for run in selected_runs],
        "entry_count": len(entries),
        "blocking_entry_count": len(blocking_entries),
        "categories": categories,
        "phase6_required_categories": phase6_summary["required_categories"],
        "phase6_conditional_categories": phase6_summary["conditional_categories"],
        "phase6_categories": sorted(phase6_summary["category_counts"].keys()),
        "phase6_category_counts": phase6_summary["category_counts"],
        "phase6_entries_by_category": phase6_summary["entries_by_category"],
        "phase6_category_coverage": phase6_summary["coverage"],
        "phase6_missing_categories": phase6_summary["missing_categories"],
        "phase6_coverage_complete": phase6_summary["coverage_complete"],
        "phase6_runtime_failure_observed": phase6_summary["runtime_failure_observed"],
        "entries": entries,
        "statistics_negative_evidence_summary": statistics_report.get(
            "negative_evidence_summary", {}
        ),
        "statistics_phase6_negative_evidence_summary": statistics_report.get(
            "phase6_negative_evidence_summary", {}
        ),
        "claim_ceiling_recommendation": statistics_report.get("claim_ceiling_recommendation"),
        "negative_evidence_retained": bool(entries),
        "blocks_final_publish": bool(blocking_entries or phase6_summary["missing_categories"]),
        "blockers": _dedupe(
            [
                *[str(entry["detail"]) for entry in blocking_entries],
                *[
                    f"Phase 6 negative evidence category not covered by deterministic artifacts: {category}."
                    for category in phase6_summary["missing_categories"]
                ],
            ]
        ),
        "policy": (
            "Negative evidence is retained as first-class package evidence. It may support scoped "
            "case-study claims, but unresolved support gaps, failed trials, and blocked repairs continue "
            "to block final publication."
        ),
    }
    return {**payload, "negative_evidence_fingerprint": _fingerprint(payload)}


def _project_offline_publication_case_payload(
    *,
    project_id: str,
    latest_brief: AutoResearchResearchBriefRead | None,
    selected_runs: list[AutoResearchRunRead],
    evidence_profile: dict[str, Any],
    literature_support_index: dict[str, Any],
    benchmark_card: dict[str, Any],
    benchmark_provenance_manifest: dict[str, Any],
    statistics_report: dict[str, Any],
    negative_evidence_report: dict[str, Any],
    repair_execution_log: dict[str, Any],
    package_output_roles: list[str],
) -> dict[str, Any]:
    fixed_idea = (
        "Use claim-evidence ledgers to guide retrieval and verification in autonomous scientific "
        "writing, reducing unsupported claims without training a new large model."
    )
    research_question = (
        "Can evidence-ledger-guided retrieval and repair reduce unsupported claims in autonomous "
        "scientific writing without large-model training?"
    )
    method_ladder = [
        "random_ranker",
        "lexical_overlap",
        "bm25_tfidf_style",
        "phrase_or_bigram_aware_retrieval",
        "ledger_aware_retrieval",
        "abstention_repair_router",
        "no_ledger_ablation",
        "retrieval_only_no_verification_ablation",
        "repair_router_disabled_ablation",
    ]
    expected_metrics = [
        "MRR",
        "Recall@1",
        "Recall@10",
        "nDCG@10",
        "evidence_coverage",
        "verification_accuracy",
        "unsupported_claim_precision",
        "unsupported_claim_recall",
        "abstention_accuracy",
        "repair_precision",
        "repair_recall",
    ]
    run_evidence_classification = []
    benchmark_source_record_by_run = {
        str(record.get("run_id")): record
        for record in benchmark_provenance_manifest.get("benchmark_source_records", [])
        if isinstance(record, dict) and record.get("run_id")
    }
    for profile in evidence_profile.get("run_profiles", []):
        source_class = str(profile.get("source_class") or "unknown")
        source_record = benchmark_source_record_by_run.get(str(profile.get("run_id"))) or {}
        source_content_origin = str(
            source_record.get("source_content_origin")
            or profile.get("source_content_origin")
            or ""
        ).strip()
        if source_content_origin in SCHEMA_DERIVED_CONTENT_ORIGINS:
            evidence_class = "schema_derived_deterministic_execution_evidence"
        elif source_class in {"remote_real", "frozen_snapshot", "imported_real"}:
            evidence_class = "external_or_imported_evidence"
        elif source_class in {"cached_fixture", "toy_builtin"} or "fixture" in source_class:
            evidence_class = "internal_evaluation_fixture"
        else:
            evidence_class = "bounded_case_study_evidence"
        run_evidence_classification.append(
            {
                "run_id": profile.get("run_id"),
                "benchmark_name": profile.get("benchmark_name"),
                "source_kind": profile.get("source_kind"),
                "source_class": source_class,
                "source_content_origin": source_content_origin,
                "source_content_note": (
                    source_record.get("source_content_note")
                    or profile.get("source_content_note")
                ),
                "evidence_class": evidence_class,
                "publication_grade": bool(profile.get("publication_grade")),
                "publication_grade_eligible": bool(
                    source_record.get("publication_grade_eligible")
                ),
                "publication_grade_blockers": list(profile.get("publication_grade_blockers") or []),
                "repository_local_snapshot_materialized": bool(
                    source_record.get("repository_local_snapshot_materialized")
                ),
                "final_publish_candidate_eligible": bool(
                    source_record.get("final_publish_candidate_eligible")
                ),
                "final_publish_candidate_blockers": list(
                    source_record.get("final_publish_candidate_blockers", [])
                ),
                "final_publish_allowed": bool(
                    source_record.get("final_publish_candidate_eligible")
                ),
                "final_publish_policy": (
                    "final_publish_allowed mirrors benchmark_provenance_manifest "
                    "final_publish_candidate_eligible, not base publication_grade."
                ),
            }
        )
    literature_sources = literature_support_index.get("source_class_counts", {})
    literature_evidence_classification = {
        "complete": bool(literature_support_index.get("complete")),
        "real_literature_sources": list(literature_support_index.get("real_literature_sources", [])),
        "source_class_counts": literature_sources,
        "evidence_class": (
            "multi_source_cached_or_network_literature"
            if literature_support_index.get("complete")
            else "incomplete_or_fixture_literature"
        ),
    }
    payload = {
        "case_id": "offline_publication_case_claim_evidence_v3",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "fixed_idea": fixed_idea,
        "brief_original_idea": latest_brief.original_idea if latest_brief is not None else None,
        "brief_id": latest_brief.brief_id if latest_brief is not None else None,
        "research_question": research_question,
        "target_title": (
            "Evidence-Ledger-Guided Retrieval and Repair for Reducing Unsupported Claims "
            "in Autonomous Scientific Writing"
        ),
        "domain": "scientific writing agents / autonomous research systems",
        "research_chain": {
            "idea": fixed_idea,
            "research_brief": latest_brief.brief_id if latest_brief is not None else None,
            "literature_scout_inputs": {
                "queries": (
                    list(latest_brief.literature_scout.search_queries)
                    if latest_brief is not None and latest_brief.literature_scout is not None
                    else []
                ),
                "allow_live_network": bool(latest_brief.allow_web) if latest_brief is not None else False,
            },
            "gap_validation": (
                latest_brief.gap_miner.model_dump(mode="json")
                if latest_brief is not None and latest_brief.gap_miner is not None
                else None
            ),
            "hypothesis_bank": (
                [item.model_dump(mode="json") for item in latest_brief.hypothesis_bank]
                if latest_brief is not None
                else []
            ),
            "selected_direction_id": latest_brief.selected_direction_id if latest_brief is not None else None,
            "selected_hypothesis_id": latest_brief.selected_hypothesis_id if latest_brief is not None else None,
            "selected_run_ids": [run.id for run in selected_runs],
            "benchmark_snapshot": {
                "benchmark_card_id": benchmark_card.get("card_id"),
                "provenance_manifest_id": benchmark_provenance_manifest.get("manifest_id"),
                "snapshot_metadata": benchmark_provenance_manifest.get("snapshot_metadata", {}),
            },
            "experiment_protocol": {
                "task_family": "ir_reranking",
                "execution_paths": sorted(
                    {
                        str(profile.get("execution_source"))
                        for profile in evidence_profile.get("execution_profiles", [])
                        if profile.get("execution_source")
                    }
                ),
                "method_ladder": method_ladder,
                "expected_metrics": expected_metrics,
            },
            "method_ladder": method_ladder,
            "expected_metrics": expected_metrics,
            "repair_triggers": [
                "missing_or_fixture_literature_support",
                "missing_benchmark_provenance",
                "insufficient_benchmark_scale",
                "insufficient_statistics",
                "retrieval_miss_or_unsupported_claim",
                "runtime_failure_or_blocked_repair",
            ],
            "paper_package_outputs": package_output_roles,
        },
        "evidence_classification": {
            "literature": literature_evidence_classification,
            "benchmarks_and_runs": run_evidence_classification,
            "statistics": {
                "evidence_class": "deterministic_execution_or_import_replay_outputs",
                "complete": bool(statistics_report.get("complete")),
                "claim_ceiling_recommendation": statistics_report.get("claim_ceiling_recommendation"),
            },
            "negative_evidence": {
                "evidence_class": "retained_project_negative_evidence",
                "entry_count": negative_evidence_report.get("entry_count", 0),
                "blocking_entry_count": negative_evidence_report.get("blocking_entry_count", 0),
            },
            "internal_fixtures_policy": (
                "Internal fixtures and toy/cached fixture benchmarks may validate the regression pipeline "
                "and review-ready case study, but they cannot satisfy final publication evidence."
            ),
        },
        "repair_execution_summary": {
            "action_count": repair_execution_log.get("action_count", 0),
            "completed_action_count": repair_execution_log.get("completed_action_count", 0),
            "blocked_action_count": repair_execution_log.get("blocked_action_count", 0),
            "pending_action_count": repair_execution_log.get("pending_action_count", 0),
            "complete": bool(repair_execution_log.get("complete")),
        },
        "package_targets": {
            "minimum_target": "review_ready_workshop_or_technical_report_candidate",
            "final_publish_decision": "derived_from_readiness_report_and_publish_gates",
        },
        "policy": (
            "This case definition is deterministic and offline. It documents the research chain and "
            "evidence provenance classes without promoting fixtures, single-run results, or incomplete "
            "repairs to publication-grade claims."
        ),
    }
    return {**payload, "case_fingerprint": _fingerprint(payload)}


def _project_offline_publication_audit_payload(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    evidence_profile: dict[str, Any],
    literature_support_index: dict[str, Any],
    benchmark_provenance_manifest: dict[str, Any],
    experiment_repair_index: dict[str, Any],
    statistics_report: dict[str, Any],
    negative_evidence_report: dict[str, Any],
    rereview_report: dict[str, Any],
    submission_manifest: dict[str, Any],
    project_submission_blockers: list[str],
) -> dict[str, Any]:
    generated_roles = {
        item.get("role")
        for item in submission_manifest.get("generated_assets", [])
        if isinstance(item, dict)
    }
    auditable_package_ready = all(
        bool(item.get("exists"))
        for item in submission_manifest.get("generated_assets", [])
        if isinstance(item, dict)
        and item.get("role")
        not in {"project_offline_publication_audit", "project_publication_manifest"}
    )

    def classify_blocker(text: str) -> str:
        lowered = text.lower()
        if _is_pdf_compile_environment_blocker(text):
            return "compile_environment_limitation"
        compiler_evidence_scientific_signals = (
            "project paper compiler evidence lacks real citation/reference coverage",
            "project paper compiler evidence lacks benchmark provenance coverage",
            "project paper compiler evidence lacks deterministic statistics",
            "project paper compiler evidence lacks linked execution/import replay coverage",
            "project paper compiler evidence lacks manuscript result tables",
            "project paper compiler evidence has pending reviewer revision actions",
            "project paper compiler evidence lacks persisted review findings",
        )
        if any(signal in lowered for signal in compiler_evidence_scientific_signals):
            return "scientific_evidence_gap"
        scientific_override_signals = (
            "publication-grade",
            "publication grade",
            "not marked publication-grade",
            "not publication-grade",
            "cannot be publication-grade",
            "schema-derived",
            "template-generated",
            "not imported from original benchmark records",
            "fixture",
            "synthetic",
            "scholarflow internal benchmark",
            "scholarflow-fixtures",
            "project publish gate has not passed",
            "pending revision actions",
            "final submission must wait for re-review",
            "review-ready only",
            "missing final-candidate ladder element",
            "required baseline/ablation ladder",
            "method-superiority claims",
            "phase 6 negative evidence category",
            "phase 6 negative-evidence category",
            "negative evidence category not covered",
            "negative-evidence category not covered",
            "missing benchmark dataset_id",
            "missing benchmark source locator",
            "missing benchmark revision",
            "missing benchmark license",
            "missing benchmark source fingerprint",
            "benchmark query/document/evidence schema is incomplete",
            "benchmark source class is missing",
            "missing query_count",
            "missing document_count",
            "missing evidence_annotation_count",
            "missing evidence annotations",
            "missing retrieval relevance annotations",
            "missing materialized repository-local frozen benchmark file",
            "materialized repository-local frozen benchmark",
            "final-publish candidate benchmark",
            "independent source dataset",
            "same source release",
            "cross-source",
        )
        if any(signal in lowered for signal in scientific_override_signals):
            return "scientific_evidence_gap"
        source_provenance_terms = (
            "source locator",
            "dataset_id",
            "revision",
            "license",
            "fingerprint",
            "source fingerprint",
            "schema",
            "query_count",
            "document_count",
            "evidence_annotation_count",
            "retrieval relevance",
            "materialized repository-local",
            "schema-derived",
            "template-generated",
            "original benchmark records",
            "independent source",
            "same source release",
            "cross-source",
        )
        source_provenance_context = (
            "benchmark",
            "source",
            "dataset",
            "frozen",
            "imported",
            "publication-grade",
            "publication grade",
            "final-publish candidate",
            "claim-verification",
            "retrieval-only",
            "source independence",
        )
        if any(term in lowered for term in source_provenance_terms) and any(
            context in lowered for context in source_provenance_context
        ):
            return "scientific_evidence_gap"
        engineering_signals = (
            "missing",
            "not found",
            "not available",
            "compile",
            "pdflatex",
            "package",
            "manifest",
            "asset",
            "path",
            "file",
            "lineage",
            "output",
            "runtime_failure",
            "repair execution log",
            "reviewer response",
            "claim-evidence index",
        )
        scientific_signals = (
            "publication-grade",
            "publication grade",
            "scale",
            "sample",
            "example",
            "benchmark",
            "statistics",
            "significance",
            "replication",
            "seed",
            "split",
            "unsupported",
            "partial",
            "claim",
            "literature",
            "novelty",
            "negative",
            "evidence",
            "single-run",
            "final publish",
        )
        if any(signal in lowered for signal in engineering_signals):
            return "engineering_gap"
        if any(signal in lowered for signal in scientific_signals):
            return "scientific_evidence_gap"
        return "scientific_evidence_gap"

    def classify_blockers(blockers: list[Any]) -> list[dict[str, str]]:
        classified = []
        for blocker in blockers:
            text = str(blocker)
            classified.append(
                {
                    "blocker": text,
                    "classification": classify_blocker(text),
                    "resolution_policy": (
                        "fix package, lineage, execution-output, compile, or manifest plumbing in this goal"
                        if classify_blocker(text) == "engineering_gap"
                        else "install or provide the PDF compiler only if a compiled PDF artifact is required"
                        if classify_blocker(text) == "compile_environment_limitation"
                        else "retain as blocker, limitation, follow-up, or kill criterion until stronger evidence exists"
                    ),
                }
            )
        return classified

    benchmark_source_records = benchmark_provenance_manifest.get("benchmark_source_records", [])
    largest_sample_count = max(
        (
            int(record.get("sample_count") or 0)
            for record in benchmark_source_records
            if isinstance(record, dict)
        ),
        default=0,
    )
    imported_or_frozen_records = [
        record
        for record in benchmark_source_records
        if isinstance(record, dict)
        and record.get("source_class") in {"frozen_snapshot", "imported_real", "remote_real"}
    ]
    materialized_imported_or_frozen_records = [
        record
        for record in imported_or_frozen_records
        if record.get("source_class") != "frozen_snapshot"
        or bool(record.get("repository_local_snapshot_materialized"))
    ]
    unmaterialized_frozen_snapshot_records = [
        record
        for record in imported_or_frozen_records
        if record.get("source_class") == "frozen_snapshot"
        and not bool(record.get("repository_local_snapshot_materialized"))
    ]
    final_candidate_scale_ready = (
        bool(materialized_imported_or_frozen_records)
        and largest_sample_count >= FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES
    )
    benchmark_blockers = list(benchmark_provenance_manifest.get("blockers", []))
    if not final_candidate_scale_ready:
        benchmark_blockers.append(
            f"Final-publish candidate benchmark attempt requires a frozen/imported real snapshot with at least "
            f"{FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES} normalized examples; largest selected snapshot has "
            f"{largest_sample_count}."
        )
    if unmaterialized_frozen_snapshot_records:
        missing_run_ids = _dedupe(
            [
                str(record.get("run_id") or "unknown_run")
                for record in unmaterialized_frozen_snapshot_records
            ]
        )
        benchmark_blockers.append(
            "Missing materialized repository-local frozen benchmark file for selected "
            f"final-publish candidate source run(s): {', '.join(missing_run_ids)}."
        )
    final_publish_candidate_coverage = benchmark_provenance_manifest.get(
        "final_publish_candidate_coverage", {}
    )
    benchmark_schema_coverage = benchmark_provenance_manifest.get("schema_coverage", {})
    benchmark_observation_coverage = benchmark_provenance_manifest.get(
        "source_observation_coverage", {}
    )
    benchmark_source_independence_audit = benchmark_provenance_manifest.get(
        "benchmark_source_independence_audit", {}
    )
    if not isinstance(benchmark_source_independence_audit, dict):
        benchmark_source_independence_audit = {}
    if not benchmark_source_independence_audit:
        fallback_independence_audit = evidence_profile.get(
            "benchmark_source_independence_audit", {}
        )
        benchmark_source_independence_audit = (
            fallback_independence_audit
            if isinstance(fallback_independence_audit, dict)
            else {}
        )
    benchmark_source_independence_ready = bool(
        benchmark_source_independence_audit.get("complete")
    )
    benchmark_source_independence_blockers = list(
        benchmark_source_independence_audit.get("blockers", [])
    )
    statistics_systems = sorted(
        {
            str(item.get("system"))
            for item in statistics_report.get("per_method_metric_table", [])
            if isinstance(item, dict) and item.get("system")
        }
    )
    minimum_observed_ladder = {
        "random_ranker",
        "overlap_ranker",
        "bigram_ranker",
        "ledger_aware_ranker",
    }
    target_ladder_aliases = {
        "random_ranker": {"random_ranker"},
        "lexical_overlap": {"overlap_ranker", "lexical_overlap"},
        "tfidf_bm25_style_retrieval": {"bm25_ranker", "tfidf_ranker", "bm25_tfidf_style"},
        "phrase_or_bigram_aware_retrieval": {"bigram_ranker", "phrase_aware_ranker"},
        "ledger_aware_retrieval": {"ledger_aware_ranker", "ledger_aware_retrieval"},
        "abstention_or_repair_router": {"abstention_repair_router", "repair_router"},
        "no_ledger_ablation": {"no_ledger_ablation", "no_ledger_ranker"},
        "retrieval_only_no_verification_ablation": {
            "retrieval_only_no_verification_ablation",
            "retrieval_only_ranker",
        },
        "repair_router_disabled_ablation": {
            "repair_router_disabled_ablation",
            "repair_router_disabled",
        },
    }
    observed_ladder = {
        ladder_id
        for ladder_id, aliases in target_ladder_aliases.items()
        if aliases & set(statistics_systems)
    }
    missing_target_ladder = sorted(set(target_ladder_aliases) - observed_ladder)
    baseline_ladder_ready = bool(minimum_observed_ladder & set(statistics_systems))
    baseline_ladder_final_candidate_ready = not missing_target_ladder
    method_ladder_reproducibility_ready = bool(
        experiment_repair_index.get("execution_coverage_ready")
    )
    statistics_ready = bool(statistics_report.get("complete"))
    statistics_replication_summary = statistics_report.get("replication_summary", {})
    if not isinstance(statistics_replication_summary, dict):
        statistics_replication_summary = {}
    statistics_split_evaluations = statistics_report.get("split_evaluations", [])
    if not isinstance(statistics_split_evaluations, list):
        statistics_split_evaluations = []
    statistics_split_metric_table = statistics_report.get("split_metric_table", [])
    if not isinstance(statistics_split_metric_table, list):
        statistics_split_metric_table = []
    statistics_final_publish_blockers = list(
        statistics_report.get("final_publish_statistics_blockers", [])
    )
    statistics_limitations = list(statistics_report.get("statistics_limitations", []))
    statistics_final_publish_replication_ready = bool(
        statistics_replication_summary.get("final_publish_replication_ready")
    )
    statistics_split_labels = sorted(
        {
            str(item.get("split"))
            for item in statistics_split_evaluations
            if isinstance(item, dict) and item.get("split")
        }
    )
    negative_evidence_lowers_claim_ceiling = bool(
        negative_evidence_report.get("entry_count", 0)
    ) and statistics_report.get("claim_ceiling_recommendation") not in {
        "final_publish_claim",
        "conference_candidate_claim",
    }
    phase6_negative_evidence_audit = _phase6_negative_evidence_report_audit(
        negative_evidence_report
    )

    def _audit_followups(blockers: list[Any], *, default: str) -> list[str]:
        followups = [
            str(item.get("resolution_policy") or "")
            for item in classify_blockers(blockers)
            if str(item.get("classification")) == "scientific_evidence_gap"
        ]
        return _dedupe([*followups, default])

    def _phase1_requirement(
        *,
        requirement_id: str,
        question: str,
        ready: bool,
        evidence_refs: list[str],
        finding: str,
        blockers: list[Any] | None = None,
        followups: list[str] | None = None,
        kill_criteria: list[str] | None = None,
        scope_limitation: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_blockers = _dedupe([str(item) for item in blockers or []])
        return {
            "requirement_id": requirement_id,
            "question": question,
            "status": "satisfied" if ready else "blocked",
            "evidence_refs": evidence_refs,
            "finding": finding,
            "blockers": normalized_blockers,
            "blocker_classification": classify_blockers(normalized_blockers),
            "followups": _dedupe(followups or []),
            "kill_criteria": _dedupe(kill_criteria or []),
            "scope_limitation": scope_limitation,
            "details": details or {},
        }

    def _statistics_followups() -> list[str]:
        if statistics_report.get("claim_ceiling_recommendation") == "final_publish_claim":
            return []
        blockers = statistics_final_publish_blockers or statistics_limitations
        followups = _audit_followups(
            blockers,
            default=(
                "Resolve remaining final-publish statistics blockers before result claims exceed "
                "the scoped workshop/case-study ceiling."
            ),
        )
        if not statistics_final_publish_replication_ready:
            followups.append(
                "Add stronger deterministic multi-seed, multi-split, bootstrap, or paired "
                "randomization evidence before final-publish result claims."
            )
        return _dedupe(followups)

    checkpoints = [
        {
            "checkpoint_id": "literature_refresh",
            "question": "Can the offline case automatically materialize real cached/imported literature support?",
            "status": "satisfied" if literature_support_index.get("complete") else "blocked",
            "evidence_refs": ["literature_support_index.json"],
            "finding": (
                "Multi-source cached/network literature support is available."
                if literature_support_index.get("complete")
                else "Literature support is incomplete or fixture-only and must remain a blocker."
            ),
            "blockers": list(literature_support_index.get("blockers", [])),
        },
        {
            "checkpoint_id": "benchmark_snapshot_selection",
            "question": "Does the case select a frozen/imported benchmark snapshot with provenance?",
            "status": (
                "satisfied"
                if benchmark_provenance_manifest.get("complete")
                else "blocked"
            ),
            "evidence_refs": ["benchmark_card.json", "benchmark_provenance_manifest.json"],
            "finding": (
                "Benchmark provenance is audited from selected run profiles; final-publish-candidate "
                f"scale target is >= {FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES} normalized examples."
            ),
            "blockers": _dedupe(benchmark_blockers),
            "minimum_final_candidate_sample_count": FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES,
            "largest_selected_sample_count": largest_sample_count,
            "imported_or_frozen_source_count": len(imported_or_frozen_records),
            "materialized_imported_or_frozen_source_count": len(materialized_imported_or_frozen_records),
            "unmaterialized_frozen_snapshot_run_ids": [
                str(record.get("run_id") or "unknown_run")
                for record in unmaterialized_frozen_snapshot_records
            ],
            "all_required_frozen_snapshots_materialized": bool(imported_or_frozen_records)
            and not unmaterialized_frozen_snapshot_records,
            "final_candidate_scale_ready": final_candidate_scale_ready,
        },
        {
            "checkpoint_id": "experiment_execution_or_import_replay",
            "question": "Can experiment repair trace to deterministic execution or imported replay outputs?",
            "status": (
                "satisfied"
                if experiment_repair_index.get("execution_coverage_ready")
                else "blocked"
            ),
            "evidence_refs": ["experiment_repair_index.json"],
            "finding": "Execution/import replay coverage is read from selected run materialized jobs and outputs.",
            "blockers": list(experiment_repair_index.get("blockers", [])),
        },
        {
            "checkpoint_id": "statistics_strength",
            "question": "Does the statistics report cover deterministic aggregate/significance evidence?",
            "status": "satisfied" if statistics_report.get("complete") else "blocked",
            "evidence_refs": ["statistics_report.json"],
            "finding": (
                f"Claim ceiling is {statistics_report.get('claim_ceiling_recommendation')}."
            ),
            "blockers": list(statistics_report.get("blockers", [])),
        },
        {
            "checkpoint_id": "negative_evidence_retention",
            "question": "Is negative evidence retained in manuscript/package artifacts?",
            "status": (
                "satisfied"
                if negative_evidence_report.get("negative_evidence_retained")
                and "project_negative_evidence_report" in generated_roles
                else "blocked"
            ),
            "evidence_refs": ["negative_evidence_report.json", "paper.md"],
            "finding": (
                f"{negative_evidence_report.get('entry_count', 0)} negative/support-gap entries retained."
            ),
            "blockers": list(negative_evidence_report.get("blockers", [])),
        },
        {
            "checkpoint_id": "repair_aware_rereview",
            "question": "Does rereview read repair outputs at action level?",
            "status": "satisfied" if rereview_report.get("action_reviews") else "blocked",
            "evidence_refs": ["project_rereview_report.json", "reviewer_response.md"],
            "finding": "Action-level rereview records include outputs, blockers, and recommendations.",
            "blockers": list(rereview_report.get("new_blockers", [])),
        },
        {
            "checkpoint_id": "submission_package_v3",
            "question": "Can the package be handed to a human as a complete review bundle?",
            "status": (
                "satisfied"
                if submission_manifest.get("review_bundle_ready") or auditable_package_ready
                else "blocked"
            ),
            "evidence_refs": ["submission_manifest.json", "publication_manifest.json", "code_package.zip"],
            "finding": (
                f"Submission package has {len(generated_roles)} generated asset roles."
            ),
            "blockers": list(project_submission_blockers),
        },
    ]
    for checkpoint in checkpoints:
        checkpoint["blocker_classification"] = classify_blockers(list(checkpoint.get("blockers", [])))
    blocked = [item for item in checkpoints if item["status"] != "satisfied"]
    all_classified_blockers = [
        classified
        for checkpoint in checkpoints
        for classified in checkpoint.get("blocker_classification", [])
    ]
    engineering_gaps = [
        item for item in all_classified_blockers if item["classification"] == "engineering_gap"
    ]
    scientific_evidence_gaps = [
        item for item in all_classified_blockers if item["classification"] == "scientific_evidence_gap"
    ]
    phase1_requirements = [
        _phase1_requirement(
            requirement_id="literature_related_work_and_novelty",
            question="Is literature evidence sufficient for related work and novelty claims?",
            ready=bool(literature_support_index.get("complete")),
            evidence_refs=["literature_support_index.json"],
            finding=(
                "Cached/imported multi-source literature records support scoped related-work discussion."
                if literature_support_index.get("complete")
                else "Related-work and novelty claims remain blocked by incomplete real literature support."
            ),
            blockers=list(literature_support_index.get("blockers", [])),
            followups=_audit_followups(
                list(literature_support_index.get("blockers", [])),
                default=(
                    "Expand cached/imported arXiv, Semantic Scholar, and Crossref coverage before "
                    "making high-level novelty claims."
                ),
            ),
            scope_limitation=(
                "Literature evidence can support a scoped case-study framing only until broader "
                "real-paper coverage and related-system comparisons are imported."
            ),
            details={
                "real_literature_count": literature_support_index.get("real_literature_count", 0),
                "real_literature_sources": list(
                    literature_support_index.get("real_literature_sources", [])
                ),
                "related_system_coverage": literature_support_index.get(
                    "related_system_coverage", {}
                ),
            },
        ),
        _phase1_requirement(
            requirement_id="benchmark_scale",
            question="Is benchmark scale sufficient for a final-publish candidate?",
            ready=final_candidate_scale_ready,
            evidence_refs=["benchmark_provenance_manifest.json", "benchmark_card.json"],
            finding=(
                f"Largest selected frozen/imported benchmark snapshot has {largest_sample_count} "
                f"normalized examples; final-candidate target is "
                f"{FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES}."
            ),
            blockers=[] if final_candidate_scale_ready else _dedupe(benchmark_blockers),
            followups=(
                []
                if final_candidate_scale_ready
                else [
                    (
                        "Import or materialize a larger real frozen benchmark snapshot before "
                        "promoting benchmark-scale claims."
                    )
                ]
            ),
            kill_criteria=[
                (
                    "Do not submit as final publish unless selected benchmark evidence reaches "
                    f">= {FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES} normalized examples."
                )
            ],
            scope_limitation=(
                "Under-scale sources may validate adapter behavior or review-bundle cases, not "
                "final publication claims."
            ),
            details={
                "minimum_final_candidate_sample_count": FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES,
                "largest_selected_sample_count": largest_sample_count,
                "imported_or_frozen_source_count": len(imported_or_frozen_records),
                "materialized_imported_or_frozen_source_count": len(
                    materialized_imported_or_frozen_records
                ),
                "unmaterialized_frozen_snapshot_run_ids": [
                    str(record.get("run_id") or "unknown_run")
                    for record in unmaterialized_frozen_snapshot_records
                ],
                "all_required_frozen_snapshots_materialized": bool(
                    imported_or_frozen_records
                )
                and not unmaterialized_frozen_snapshot_records,
                "final_candidate_scale_ready": final_candidate_scale_ready,
            },
        ),
        _phase1_requirement(
            requirement_id="benchmark_source_publication_grade",
            question="Are selected benchmark sources publication-grade rather than toy/fixture evidence?",
            ready=bool(benchmark_provenance_manifest.get("benchmark_publication_ready")),
            evidence_refs=["benchmark_provenance_manifest.json"],
            finding="Selected benchmark sources are audited through per-run source records.",
            blockers=list(benchmark_provenance_manifest.get("blockers", [])),
            followups=(
                []
                if benchmark_provenance_manifest.get("benchmark_publication_ready")
                else _audit_followups(
                    list(benchmark_provenance_manifest.get("blockers", [])),
                    default=(
                        "Replace fixture, toy, or under-provenanced selected benchmark sources with "
                        "publication-grade frozen/imported/remote-real sources."
                    ),
                )
            ),
            kill_criteria=[
                "Do not convert fixture or toy benchmark evidence into final-publish evidence."
            ],
            scope_limitation=(
                "Publication-grade source/provenance eligibility is separate from cross-source "
                "independence; multiple same-release views still support only scoped case-study claims."
            ),
            details={
                "benchmark_publication_ready": benchmark_provenance_manifest.get(
                    "benchmark_publication_ready", False
                ),
                "final_publish_candidate_coverage": final_publish_candidate_coverage,
                "schema_coverage": benchmark_schema_coverage,
                "source_observation_coverage": benchmark_observation_coverage,
            },
        ),
        _phase1_requirement(
            requirement_id="benchmark_source_independence",
            question="Do selected benchmark sources cover independent source datasets?",
            ready=benchmark_source_independence_ready,
            evidence_refs=["benchmark_provenance_manifest.json", "publication_readiness_report.json"],
            finding=(
                "Selected benchmark evidence covers independent source datasets."
                if benchmark_source_independence_ready
                else (
                    "Selected benchmark views share the same parent source release; this supports "
                    "a scoped SciFact case study but not cross-source final-publish generalization."
                )
            ),
            blockers=benchmark_source_independence_blockers,
            followups=(
                []
                if benchmark_source_independence_ready
                else [
                    (
                        "Import or materialize an independent external benchmark/source release "
                        "beyond the repository-local SciFact verification and retrieval views."
                    )
                ]
            ),
            kill_criteria=[
                "Do not use same-release benchmark views to prove cross-source final-publish claims."
            ],
            scope_limitation=(
                "Repository-local SciFact verification and retrieval views are valid final-candidate "
                "artifacts for a scoped case study, but they do not constitute independent "
                "cross-source replication."
            ),
            details={
                "benchmark_source_independence_audit": benchmark_source_independence_audit,
                "benchmark_source_independence_ready": benchmark_source_independence_ready,
                "independent_source_keys": list(
                    benchmark_source_independence_audit.get("independent_source_keys", [])
                ),
                "independent_source_count": int(
                    benchmark_source_independence_audit.get("independent_source_count") or 0
                ),
            },
        ),
        _phase1_requirement(
            requirement_id="benchmark_schema_coverage",
            question="Do selected benchmark sources expose task-aware query/document/evidence schema?",
            ready=bool(benchmark_schema_coverage.get("schema_coverage_complete")),
            evidence_refs=["benchmark_provenance_manifest.json", "publication_readiness_report.json"],
            finding=(
                "Benchmark schema coverage is audited from per-run source records and repeated in readiness."
            ),
            blockers=list(benchmark_schema_coverage.get("schema_blockers", [])),
            followups=_audit_followups(
                list(benchmark_schema_coverage.get("schema_blockers", [])),
                default=(
                    "Repair benchmark source records so every selected run exposes query, document, "
                    "evidence, label, and split schema roles."
                ),
            ),
            kill_criteria=[
                "Do not submit as final publish while selected benchmark schema roles are missing."
            ],
            scope_limitation=(
                "Schema-incomplete sources may support regression checks only; final-publish evidence "
                "must expose explicit task-aware schema roles."
            ),
            details={
                "schema_coverage": benchmark_schema_coverage,
                "schema_coverage_complete": bool(
                    benchmark_schema_coverage.get("schema_coverage_complete")
                ),
                "schema_blockers": list(
                    benchmark_schema_coverage.get("schema_blockers", [])
                ),
            },
        ),
        _phase1_requirement(
            requirement_id="benchmark_source_observation_coverage",
            question="Do selected benchmark sources expose required query/document/evidence observations?",
            ready=bool(benchmark_observation_coverage.get("observation_coverage_complete")),
            evidence_refs=["benchmark_provenance_manifest.json", "publication_readiness_report.json"],
            finding=(
                "Benchmark observation coverage is audited from per-run query, document, "
                "evidence-annotation, and retrieval-relevance counts."
            ),
            blockers=list(benchmark_observation_coverage.get("observation_blockers", [])),
            followups=_audit_followups(
                list(benchmark_observation_coverage.get("observation_blockers", [])),
                default=(
                    "Repair benchmark source records so claim-verification sources include evidence "
                    "annotations and retrieval-only sources include relevance/qrels observations."
                ),
            ),
            kill_criteria=[
                "Do not submit as final publish while selected benchmark observation counts are missing."
            ],
            scope_limitation=(
                "Observation-incomplete sources may support adapter checks only; final-publish evidence "
                "must expose task-aware observation counts."
            ),
            details={
                "source_observation_coverage": benchmark_observation_coverage,
                "observation_coverage_complete": bool(
                    benchmark_observation_coverage.get("observation_coverage_complete")
                ),
                "observation_blockers": list(
                    benchmark_observation_coverage.get("observation_blockers", [])
                ),
            },
        ),
        _phase1_requirement(
            requirement_id="baseline_ladder",
            question="Is the baseline/method ladder sufficient for final-publish claims?",
            ready=baseline_ladder_final_candidate_ready,
            evidence_refs=["statistics_report.json", "offline_publication_case.json"],
            finding=(
                "Current deterministic ladder records random, lexical/overlap, bigram, and "
                "ledger-aware ranker outputs; stronger final-publish ablations remain separate "
                "scientific follow-up if missing."
            ),
            blockers=[
                f"Missing final-candidate ladder element: {item}."
                for item in missing_target_ladder
            ],
            followups=[
                (
                    "Implement or import deterministic outputs for the missing baseline and "
                    "ablation ladder elements before strong final-publish claims."
                )
            ]
            if missing_target_ladder
            else [],
            kill_criteria=[
                "Do not make broad method-superiority claims while required baseline/ablation ladder elements are missing."
            ],
            scope_limitation=(
                "The present ladder can support a scoped review-ready case study, not a full "
                "conference-style method claim when ablations are absent."
            ),
            details={
                "observed_systems": statistics_systems,
                "observed_target_ladder": sorted(observed_ladder),
                "missing_target_ladder": missing_target_ladder,
                "minimum_ladder_observed": baseline_ladder_ready,
            },
        ),
        _phase1_requirement(
            requirement_id="method_ladder_reproducibility",
            question="Can method outputs be reproduced from deterministic execution or imported replay?",
            ready=method_ladder_reproducibility_ready,
            evidence_refs=["experiment_repair_index.json", "statistics_report.json"],
            finding="Method reproducibility is audited from execution/import replay coverage.",
            blockers=list(experiment_repair_index.get("blockers", [])),
            followups=_audit_followups(
                list(experiment_repair_index.get("blockers", [])),
                default="Link every method output to deterministic execution or imported replay artifacts.",
            ),
            kill_criteria=[
                "Do not complete evidence-producing repair actions without materialized outputs."
            ],
            scope_limitation=(
                "Statistics cannot be treated as final-publish evidence unless every selected run "
                "has linked execution/import replay artifacts."
            ),
            details={
                "execution_coverage_ready": experiment_repair_index.get(
                    "execution_coverage_ready", False
                ),
                "execution_source_counts": experiment_repair_index.get(
                    "execution_source_counts", {}
                ),
                "materialized_execution_run_ids": experiment_repair_index.get(
                    "materialized_execution_run_ids", []
                ),
                "imported_result_replay_run_ids": experiment_repair_index.get(
                    "imported_result_replay_run_ids", []
                ),
            },
        ),
        _phase1_requirement(
            requirement_id="multi_seed_split_paired_statistics",
            question="Are multi-seed/multi-split/paired statistics strong enough for final-publish claims?",
            ready=statistics_ready
            and statistics_report.get("claim_ceiling_recommendation") == "final_publish_claim",
            evidence_refs=["statistics_report.json", "paper_compiler_evidence.json"],
            finding=(
                f"Statistics report is {'complete' if statistics_ready else 'incomplete'} and "
                f"claim ceiling is {statistics_report.get('claim_ceiling_recommendation')}."
            ),
            blockers=statistics_limitations
            if statistics_report.get("claim_ceiling_recommendation") != "final_publish_claim"
            else [],
            followups=_statistics_followups(),
            kill_criteria=[
                "Do not write state-of-the-art, broad, or final-publish improvement claims when the statistics claim ceiling is below final publish."
            ],
            scope_limitation=(
                "Current statistics may support a scoped workshop/case-study claim when the report "
                "is complete but the claim ceiling remains below final publish."
            ),
            details={
                "statistics_ready": statistics_ready,
                "paired_comparison_count": len(statistics_report.get("paired_comparisons", [])),
                "confidence_interval_count": len(statistics_report.get("confidence_intervals", [])),
                "deterministic_equivalent_count": len(
                    statistics_report.get("deterministic_equivalents", [])
                ),
                "replication_summary": statistics_replication_summary,
                "multi_seed_ready": bool(
                    statistics_replication_summary.get("multi_seed_ready")
                ),
                "multi_split_ready": bool(
                    statistics_replication_summary.get("multi_split_ready")
                ),
                "split_evaluation_count": len(statistics_split_evaluations),
                "split_metric_table_count": len(statistics_split_metric_table),
                "split_labels": statistics_split_labels,
                "final_publish_replication_ready": (
                    statistics_final_publish_replication_ready
                ),
                "claim_ceiling_recommendation": statistics_report.get(
                    "claim_ceiling_recommendation"
                ),
            },
        ),
        _phase1_requirement(
            requirement_id="negative_evidence_claim_ceiling",
            question="Does negative evidence lower the claim ceiling instead of being hidden?",
            ready=bool(negative_evidence_report.get("negative_evidence_retained"))
            and negative_evidence_lowers_claim_ceiling,
            evidence_refs=["negative_evidence_report.json", "statistics_report.json", "paper.md"],
            finding=(
                f"{negative_evidence_report.get('entry_count', 0)} negative/support-gap entries "
                "are retained and the claim ceiling remains scoped."
            ),
            blockers=[],
            followups=[
                "Resolve or explicitly retain negative evidence before any stronger final-publish claim."
            ],
            kill_criteria=[
                "Do not remove negative evidence during revision to make final-publish gates pass."
            ],
            scope_limitation=(
                "Negative evidence supports failure analysis and scoped conclusions, not unqualified "
                "method superiority."
            ),
            details={
                "entry_count": negative_evidence_report.get("entry_count", 0),
                "blocking_entry_count": negative_evidence_report.get(
                    "blocking_entry_count", 0
                ),
                "categories": list(negative_evidence_report.get("categories", [])),
                "phase6_negative_evidence_coverage": phase6_negative_evidence_audit,
                "phase6_categories": phase6_negative_evidence_audit["categories"],
                "phase6_missing_categories": phase6_negative_evidence_audit[
                    "missing_categories"
                ],
                "phase6_coverage_complete": phase6_negative_evidence_audit[
                    "coverage_complete"
                ],
                "claim_ceiling_recommendation": statistics_report.get(
                    "claim_ceiling_recommendation"
                ),
            },
        ),
        _phase1_requirement(
            requirement_id="package_artifact_completeness",
            question="Are required submission package artifacts present?",
            ready=auditable_package_ready,
            evidence_refs=["submission_manifest.json", "publication_manifest.json"],
            finding=(
                f"Auditable submission package contains {len(generated_roles)} generated asset roles."
            ),
            blockers=[] if auditable_package_ready else list(project_submission_blockers),
            followups=[
                "Materialize missing package artifacts before rerunning final-publish readiness."
            ]
            if not auditable_package_ready
            else [],
            kill_criteria=[
                "Do not call a package final-publish ready if required artifacts are missing."
            ],
            scope_limitation=(
                "A complete review bundle can still be final-publish blocked by scientific evidence gaps."
            ),
            details={
                "auditable_package_ready": auditable_package_ready,
                "generated_role_count": len(generated_roles),
                "generated_roles": sorted(str(role) for role in generated_roles if role),
            },
        ),
        _phase1_requirement(
            requirement_id="blocker_classification",
            question="Are final-publish blockers classified as engineering gaps or scientific evidence gaps?",
            ready=not engineering_gaps,
            evidence_refs=[
                "offline_publication_audit.json",
                "publication_readiness_report.json",
                "publication_manifest.json",
            ],
            finding=(
                "Remaining final-publish blockers are classified so package/plumbing defects can be "
                "separated from evidence limitations."
            ),
            blockers=[item["blocker"] for item in engineering_gaps],
            followups=[
                "Fix engineering-classified package, lineage, runtime-output, compile, or manifest gaps in this goal."
            ]
            if engineering_gaps
            else [
                "Keep scientific evidence gaps as limitations, required follow-ups, or kill criteria until stronger evidence exists."
            ],
            kill_criteria=[
                "Do not report final_publish_ready=true while either engineering gaps or scientific evidence blockers remain."
            ],
            scope_limitation=(
                "Scientific blockers are allowed to remain for a review-ready bundle only when they "
                "are concrete and reproducible."
            ),
            details={
                "engineering_gap_count": len(engineering_gaps),
                "scientific_evidence_gap_count": len(scientific_evidence_gaps),
            },
        ),
    ]
    phase1_requirements_by_id = {
        item["requirement_id"]: item for item in phase1_requirements
    }
    final_publish_blocker_classification = classify_blockers(project_submission_blockers)
    phase1_blocked_requirement_ids = [
        item["requirement_id"]
        for item in phase1_requirements
        if item["status"] != "satisfied"
    ]
    package_plumbing_complete = bool(auditable_package_ready and not engineering_gaps)
    final_publish_false_reason = (
        "final_publish_ready"
        if submission_manifest.get("final_publish_ready")
        else "engineering_gap"
        if engineering_gaps
        else "scientific_evidence_gap"
        if scientific_evidence_gaps or project_submission_blockers
        else "not_requested"
    )
    goal1_current_audit_summary = {
        "goal": "Goal 1: First Final-Publish Candidate For Claim-Evidence Retrieval",
        "phase_focus": ["phase1_final_publish_gap_audit", "phase2_larger_frozen_imported_benchmark_snapshot"],
        "review_bundle_ready": bool(
            submission_manifest.get("review_bundle_ready") or auditable_package_ready
        ),
        "final_publish_ready": bool(submission_manifest.get("final_publish_ready")),
        "final_publish_ready_false_reason": final_publish_false_reason,
        "package_plumbing_complete": package_plumbing_complete,
        "engineering_gap_count": len(engineering_gaps),
        "scientific_evidence_gap_count": len(scientific_evidence_gaps),
        "phase6_negative_evidence_coverage_complete": phase6_negative_evidence_audit[
            "coverage_complete"
        ],
        "phase6_missing_categories": phase6_negative_evidence_audit[
            "missing_categories"
        ],
        "benchmark_snapshot_artifact_materialized": bool(
            materialized_imported_or_frozen_records
        ),
        "benchmark_snapshot_artifact_record_count": len(imported_or_frozen_records),
        "benchmark_snapshot_artifact_materialized_count": len(
            materialized_imported_or_frozen_records
        ),
        "benchmark_final_publish_candidate_coverage_complete": bool(
            final_publish_candidate_coverage.get("complete")
        ),
        "benchmark_final_publish_candidate_blockers": list(
            final_publish_candidate_coverage.get("blockers", [])
        ),
        "benchmark_source_independence_ready": benchmark_source_independence_ready,
        "benchmark_source_independence_blockers": benchmark_source_independence_blockers,
        "benchmark_source_independence_audit": benchmark_source_independence_audit,
        "phase1_blocked_requirement_ids": phase1_blocked_requirement_ids,
        "remaining_scientific_blocker_requirement_ids": [
            item["requirement_id"]
            for item in phase1_requirements
            if item["status"] != "satisfied"
            and any(
                classified["classification"] == "scientific_evidence_gap"
                for classified in item.get("blocker_classification", [])
            )
        ],
        "policy": (
            "This summary separates package plumbing from scientific evidence limits. "
            "A review-ready package can have complete artifacts and explicit Phase 6 taxonomy "
            "coverage or missing-category audit fields while final publish remains blocked by "
            "benchmark-source independence, benchmark-scale, literature breadth, negative-evidence, "
            "or statistics/replication evidence gaps."
        ),
    }
    fixed_goal_audit = {
        "audit_id": "goal1_fixed_file_audit_v1",
        "goal": goal1_current_audit_summary["goal"],
        "source_goal_document": "docs/goal.md",
        "phase_focus": goal1_current_audit_summary["phase_focus"],
        "required_commands": [
            "git status --short --branch",
            "git log --oneline -n 8",
        ],
        "required_artifact_destinations": [
            "offline_publication_audit.json",
            "publication_readiness_report.json",
            "evaluation_cases.py trace",
            "docs",
            "tests",
        ],
        "artifact_destinations_used": [
            "offline_publication_audit.json",
            "publication_readiness_report.json",
            "evaluation_cases.py trace",
            "docs",
            "tests",
            "backend/tests/test_autoresearch_regressions.py",
            "docs/api-reference.md",
            "docs/claim-evidence-vertical-loop.md",
        ],
        "audited_file_count": len(GOAL1_FIXED_AUDIT_FILE_PATHS),
        "audited_files": [
            {
                "path": path,
                "audit_scope": GOAL1_FIXED_AUDIT_FILE_SCOPES[path],
                "phase1_phase2_relevance": (
                    "Phase 1/2 audit dependency for separating package plumbing from "
                    "scientific evidence limits and preserving repository-local frozen "
                    "benchmark provenance."
                ),
                "audit_conclusion": (
                    "Reviewed for Goal 1 Phase 1/2. Current package plumbing is complete "
                    "when this artifact is generated, and any remaining final-publish "
                    "blocker must stay classified by artifact evidence."
                ),
            }
            for path in GOAL1_FIXED_AUDIT_FILE_PATHS
        ],
        "artifact_conclusion": {
            "review_bundle_ready": bool(
                submission_manifest.get("review_bundle_ready") or auditable_package_ready
            ),
            "final_publish_ready": bool(submission_manifest.get("final_publish_ready")),
            "final_publish_ready_false_reason": final_publish_false_reason,
            "package_plumbing_complete": package_plumbing_complete,
            "engineering_gap_count": len(engineering_gaps),
            "scientific_evidence_gap_count": len(scientific_evidence_gaps),
            "benchmark_snapshot_artifact_materialized": bool(
                materialized_imported_or_frozen_records
            ),
            "benchmark_final_publish_candidate_coverage_complete": bool(
                final_publish_candidate_coverage.get("complete")
            ),
            "benchmark_source_independence_ready": benchmark_source_independence_ready,
            "benchmark_source_independence_blockers": benchmark_source_independence_blockers,
            "benchmark_source_independence_audit": benchmark_source_independence_audit,
        },
        "policy": (
            "This fixed audit records the mandatory docs/goal.md session audit in "
            "a generated artifact and regression tests. It does not weaken publish "
            "gates, promote fixture evidence, hide negative evidence, or convert "
            "review-ready evidence into final-publish evidence."
        ),
    }
    payload = {
        "audit_id": "offline_publication_capability_audit_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_ids": [run.id for run in selected_runs],
        "checkpoint_count": len(checkpoints),
        "satisfied_checkpoint_count": len(checkpoints) - len(blocked),
        "blocked_checkpoint_count": len(blocked),
        "checkpoints": checkpoints,
        "remaining_breakpoints": [
            {
                "checkpoint_id": item["checkpoint_id"],
                "finding": item["finding"],
                "blockers": item["blockers"],
                "blocker_classification": item.get("blocker_classification", []),
            }
            for item in blocked
        ],
        "fixed_goal_audit": fixed_goal_audit,
        "final_publish_gap_audit": {
            "goal1_current_audit_summary": goal1_current_audit_summary,
            "fixed_goal_audit": fixed_goal_audit,
            "literature_related_work_and_novelty_ready": bool(literature_support_index.get("complete")),
            "benchmark_scale_ready_for_final_candidate": final_candidate_scale_ready,
            "benchmark_final_publish_candidate_coverage_complete": bool(
                final_publish_candidate_coverage.get("complete")
            ),
            "benchmark_final_publish_candidate_blockers": list(
                final_publish_candidate_coverage.get("blockers", [])
            ),
            "benchmark_source_independence_ready": benchmark_source_independence_ready,
            "benchmark_source_independence_blockers": benchmark_source_independence_blockers,
            "benchmark_source_independence_audit": benchmark_source_independence_audit,
            "benchmark_schema_coverage_complete": bool(
                benchmark_schema_coverage.get("schema_coverage_complete")
            ),
            "benchmark_schema_coverage_blockers": list(
                benchmark_schema_coverage.get("schema_blockers", [])
            ),
            "benchmark_schema_coverage": benchmark_schema_coverage,
            "benchmark_source_observation_coverage_complete": bool(
                benchmark_observation_coverage.get("observation_coverage_complete")
            ),
            "benchmark_source_observation_blockers": list(
                benchmark_observation_coverage.get("observation_blockers", [])
            ),
            "benchmark_source_observation_coverage": benchmark_observation_coverage,
            "benchmark_source_publication_grade_ready": bool(
                benchmark_provenance_manifest.get("benchmark_publication_ready")
            ),
            "benchmark_snapshot_artifact_materialized": bool(materialized_imported_or_frozen_records),
            "benchmark_snapshot_artifact_record_count": len(imported_or_frozen_records),
            "benchmark_snapshot_artifact_materialized_count": len(
                materialized_imported_or_frozen_records
            ),
            "benchmark_snapshot_artifact_all_required_materialized": bool(
                imported_or_frozen_records
            )
            and not unmaterialized_frozen_snapshot_records,
            "benchmark_snapshot_artifact_unmaterialized_run_ids": [
                str(record.get("run_id") or "unknown_run")
                for record in unmaterialized_frozen_snapshot_records
            ],
            "benchmark_snapshot_artifact_materialization_policy": (
                "Frozen benchmark snapshots must be materialized as repository-local files. "
                "Imported and remote-real records must retain source locator, revision, "
                "license, fingerprints, and eligibility blockers in benchmark provenance."
            ),
            "benchmark_snapshot_artifact_records": [
                {
                    "run_id": record.get("run_id"),
                    "dataset_id": record.get("dataset_id"),
                    "revision": record.get("revision"),
                    "license": record.get("license"),
                    "source_class": record.get("source_class"),
                    "source_locator": record.get("source_locator"),
                    "source_file_path": record.get("source_file_path"),
                    "repository_local_snapshot_materialized": bool(
                        record.get("repository_local_snapshot_materialized")
                    ),
                    "fingerprint": record.get("fingerprint"),
                    "source_content_origin": record.get("source_content_origin"),
                    "source_content_note": record.get("source_content_note"),
                    "source_parent_dataset_id": record.get("source_parent_dataset_id"),
                    "source_parent_snapshot_fingerprint": record.get(
                        "source_parent_snapshot_fingerprint"
                    ),
                    "record_fingerprint": record.get("record_fingerprint"),
                    "sample_count": int(record.get("sample_count") or 0),
                    "split_count": int(record.get("split_count") or 0),
                    "split_distribution": dict(record.get("split_distribution", {})),
                    "label_distribution": dict(record.get("label_distribution", {})),
                    "query_count": int(record.get("query_count") or 0),
                    "document_count": int(record.get("document_count") or 0),
                    "evidence_annotation_count": int(
                        record.get("evidence_annotation_count") or 0
                    ),
                    "retrieval_relevance_count": int(
                        record.get("retrieval_relevance_count") or 0
                    ),
                    "publication_grade_eligible": bool(
                        record.get("publication_grade_eligible")
                    ),
                    "publication_grade_blockers": list(
                        record.get("publication_grade_blockers", [])
                    ),
                    "final_publish_candidate_eligible": bool(
                        record.get("final_publish_candidate_eligible")
                    ),
                    "final_publish_candidate_blockers": list(
                        record.get("final_publish_candidate_blockers", [])
                    ),
                }
                for record in imported_or_frozen_records
            ],
            "baseline_ladder_recorded": bool(statistics_report.get("per_method_metric_table")),
            "baseline_ladder_final_candidate_ready": baseline_ladder_final_candidate_ready,
            "baseline_ladder_missing_final_candidate_methods": missing_target_ladder,
            "method_ladder_reproducibility_ready": bool(experiment_repair_index.get("execution_coverage_ready")),
            "statistics_ready": bool(statistics_report.get("complete")),
            "negative_evidence_lowers_claim_ceiling": bool(
                negative_evidence_report.get("entry_count", 0)
            )
            and statistics_report.get("claim_ceiling_recommendation") not in {
                "final_publish_claim",
                "conference_candidate_claim",
            },
            "phase6_negative_evidence_coverage": phase6_negative_evidence_audit,
            "phase6_negative_evidence_categories": phase6_negative_evidence_audit[
                "categories"
            ],
            "phase6_negative_evidence_missing_categories": phase6_negative_evidence_audit[
                "missing_categories"
            ],
            "phase6_negative_evidence_coverage_complete": phase6_negative_evidence_audit[
                "coverage_complete"
            ],
            "package_artifacts_complete": auditable_package_ready,
            "engineering_gap_count": len(engineering_gaps),
            "scientific_evidence_gap_count": len(scientific_evidence_gaps),
            "engineering_gaps": engineering_gaps,
            "scientific_evidence_gaps": scientific_evidence_gaps,
            "phase1_requirement_count": len(phase1_requirements),
            "phase1_requirements": phase1_requirements,
            "phase1_requirements_by_id": phase1_requirements_by_id,
            "phase1_blocked_requirement_ids": phase1_blocked_requirement_ids,
            "final_publish_blocker_classification": final_publish_blocker_classification,
            "classification_policy": (
                "Engineering gaps are package, lineage, runtime-output, source-package compile, or "
                "manifest plumbing defects that should be fixed in this goal. Local PDF compiler "
                "availability is a compile-environment limitation when the source package is "
                "materialized. Benchmark source provenance, schema, observation-count, scale, "
                "literature, statistics, and negative-evidence gaps remain scientific blockers, "
                "limitations, required follow-ups, or kill criteria until stronger evidence is produced or imported."
            ),
        },
        "review_ready": bool(submission_manifest.get("review_bundle_ready") or auditable_package_ready),
        "final_publish_ready": bool(submission_manifest.get("final_publish_ready")),
        "final_publish_blockers": list(project_submission_blockers),
        "policy": (
            "This audit records current capabilities and remaining breakpoints from artifacts. It does "
            "not weaken publish gates or convert review-ready evidence into final-publish evidence."
        ),
    }
    return {**payload, "audit_fingerprint": _fingerprint(payload)}


def _materialize_project_code_package(
    *,
    project_id: str,
    paths: list[Path],
) -> Path:
    submission_dir = _project_submission_dir(project_id)
    archive_path = submission_dir / PROJECT_CODE_PACKAGE_FILENAME
    project_root = _project_paper_dir(project_id)
    added: set[str] = set()
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as handle:
        for path in paths:
            _add_path_to_project_zip(handle, project_root=project_root, path=path, added=added)
    return archive_path


def _project_publication_manifest_payload(
    *,
    project_id: str,
    project_publish_gate_passed: bool,
    project_review_bundle_ready: bool,
    project_final_publish_ready: bool,
    selected_runs: list[AutoResearchRunRead],
    project_paper_path: Path,
    project_paper_sources_dir: Path,
    project_paper_revised_path: Path,
    project_revision_application_path: Path,
    project_revision_rereview_path: Path,
    submission_manifest_path: Path,
    checklist_path: Path,
    reviewer_response_path: Path,
    review_findings_path: Path,
    repair_execution_log_path: Path,
    claim_index_path: Path,
    retrieval_evidence_ledger_path: Path,
    lineage_archive_path: Path,
    literature_support_index_path: Path,
    paper_compiler_evidence_path: Path,
    publication_evidence_index_path: Path,
    publication_readiness_report_path: Path,
    supplemental_artifacts_path: Path,
    code_package_path: Path,
    benchmark_card_path: Path,
    benchmark_provenance_manifest_path: Path,
    benchmark_provenance_repair_index_path: Path,
    statistics_report_path: Path,
    experiment_repair_index_path: Path,
    negative_evidence_report_path: Path,
    offline_publication_case_path: Path,
    offline_publication_audit_path: Path,
    blockers: list[str],
    generated_assets: list[dict[str, Any]] | None = None,
    readiness_report: dict[str, Any] | None = None,
    statistics_report: dict[str, Any] | None = None,
    negative_evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_assets: list[dict[str, Any]] = []
    for asset in generated_assets or []:
        manifest_asset = dict(asset)
        if manifest_asset.get("role") == "project_publication_manifest":
            manifest_asset["sha256"] = None
            manifest_asset["self_referential_hash"] = True
            manifest_asset["integrity_note"] = (
                "The publication manifest cannot embed its own final file sha256; "
                "verify the final manifest file hash from the filesystem or export envelope."
            )
        manifest_assets.append(manifest_asset)
    missing_assets = [asset for asset in manifest_assets if asset.get("missing_status") != "present"]
    final_publish_blocking_assets = [
        asset for asset in manifest_assets if asset.get("final_publish_blocking")
    ]
    readiness = readiness_report or {}
    statistics = statistics_report or {}
    phase6_negative_evidence_audit = _phase6_negative_evidence_report_audit(
        negative_evidence_report
    )
    readiness_checks = [
        item
        for item in readiness.get("checks", [])
        if isinstance(item, dict)
    ]
    failed_checks = [
        {
            "check_id": item.get("check_id"),
            "detail": item.get("detail"),
        }
        for item in readiness_checks
        if not item.get("passed")
    ]
    payload = {
        "publication_id": f"project_publication_{project_id}",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "bundle_kind": "final_publish_bundle" if project_final_publish_ready else "review_bundle",
        "review_bundle_ready": project_review_bundle_ready,
        "final_publish_ready": project_final_publish_ready,
        "project_publish_gate_passed": project_publish_gate_passed,
        "selected_run_ids": [run.id for run in selected_runs],
        "manuscript_path": str(project_paper_path),
        "manuscript_sha256": _file_sha256(project_paper_path),
        "revised_manuscript_path": str(project_paper_revised_path),
        "revised_manuscript_sha256": _file_sha256(project_paper_revised_path),
        "paper_sources_dir": str(project_paper_sources_dir),
        "revision_application_path": str(project_revision_application_path),
        "revision_application_sha256": _file_sha256(project_revision_application_path),
        "revision_rereview_path": str(project_revision_rereview_path),
        "revision_rereview_sha256": _file_sha256(project_revision_rereview_path),
        "submission_manifest_path": str(submission_manifest_path),
        "submission_manifest_sha256": _file_sha256(submission_manifest_path),
        "reproducibility_checklist_path": str(checklist_path),
        "reproducibility_checklist_sha256": _file_sha256(checklist_path),
        "reviewer_response_path": str(reviewer_response_path),
        "reviewer_response_sha256": _file_sha256(reviewer_response_path),
        "review_findings_path": str(review_findings_path),
        "review_findings_sha256": _file_sha256(review_findings_path),
        "repair_execution_log_path": str(repair_execution_log_path),
        "repair_execution_log_sha256": _file_sha256(repair_execution_log_path),
        "claim_evidence_index_path": str(claim_index_path),
        "claim_evidence_index_sha256": _file_sha256(claim_index_path),
        "retrieval_evidence_ledger_path": str(retrieval_evidence_ledger_path),
        "retrieval_evidence_ledger_sha256": _file_sha256(retrieval_evidence_ledger_path),
        "lineage_archive_path": str(lineage_archive_path),
        "lineage_archive_sha256": _file_sha256(lineage_archive_path),
        "literature_support_index_path": str(literature_support_index_path),
        "literature_support_index_sha256": _file_sha256(literature_support_index_path),
        "paper_compiler_evidence_path": str(paper_compiler_evidence_path),
        "paper_compiler_evidence_sha256": _file_sha256(paper_compiler_evidence_path),
        "publication_evidence_index_path": str(publication_evidence_index_path),
        "publication_evidence_index_sha256": _file_sha256(publication_evidence_index_path),
        "publication_readiness_report_path": str(publication_readiness_report_path),
        "publication_readiness_report_sha256": _file_sha256(publication_readiness_report_path),
        "supplemental_artifacts_path": str(supplemental_artifacts_path),
        "supplemental_artifacts_sha256": _file_sha256(supplemental_artifacts_path),
        "code_package_path": str(code_package_path),
        "code_package_sha256": _file_sha256(code_package_path),
        "benchmark_card_path": str(benchmark_card_path),
        "benchmark_card_sha256": _file_sha256(benchmark_card_path),
        "benchmark_provenance_manifest_path": str(benchmark_provenance_manifest_path),
        "benchmark_provenance_manifest_sha256": _file_sha256(benchmark_provenance_manifest_path),
        "benchmark_provenance_repair_index_path": str(benchmark_provenance_repair_index_path),
        "benchmark_provenance_repair_index_sha256": _file_sha256(benchmark_provenance_repair_index_path),
        "statistics_report_path": str(statistics_report_path),
        "statistics_report_sha256": _file_sha256(statistics_report_path),
        "experiment_repair_index_path": str(experiment_repair_index_path),
        "experiment_repair_index_sha256": _file_sha256(experiment_repair_index_path),
        "negative_evidence_report_path": str(negative_evidence_report_path),
        "negative_evidence_report_sha256": _file_sha256(negative_evidence_report_path),
        "negative_evidence_report_ref": "submission_package/negative_evidence_report.json",
        "phase6_negative_evidence_coverage": phase6_negative_evidence_audit,
        "negative_evidence_categories": phase6_negative_evidence_audit["categories"],
        "offline_publication_case_path": str(offline_publication_case_path),
        "offline_publication_case_sha256": _file_sha256(offline_publication_case_path),
        "offline_publication_audit_path": str(offline_publication_audit_path),
        "offline_publication_audit_sha256": _file_sha256(offline_publication_audit_path),
        "asset_count": len(manifest_assets),
        "missing_asset_count": len(missing_assets),
        "blocked_asset_count": len(final_publish_blocking_assets),
        "final_publish_blocking_asset_roles": [
            asset.get("role") for asset in final_publish_blocking_assets
        ],
        "asset_roles": [asset.get("role") for asset in manifest_assets],
        "generated_assets": manifest_assets,
        "readiness_decision": {
            "decision_source": "publication_readiness_report.json",
            "review_ready": bool(readiness.get("review_ready", project_review_bundle_ready)),
            "final_publish_ready": bool(readiness.get("final_publish_ready", project_final_publish_ready)),
            "bundle_kind": "final_publish_bundle" if project_final_publish_ready else "review_bundle",
            "project_publish_gate_passed": project_publish_gate_passed,
            "claim_ceiling_recommendation": statistics.get("claim_ceiling_recommendation"),
            "phase6_negative_evidence_coverage": phase6_negative_evidence_audit,
            "negative_evidence_categories": phase6_negative_evidence_audit["categories"],
            "negative_evidence_report_ref": "submission_package/negative_evidence_report.json",
            "failed_checks": failed_checks,
            "failed_check_count": len(failed_checks),
            "blockers": list(readiness.get("blockers", blockers)),
            "required_followups": list(readiness.get("required_followups", [])),
            "kill_criteria": list(readiness.get("kill_criteria", [])),
            "evidence_refs": [
                "publication_readiness_report.json",
                "paper_compiler_evidence.json",
                "repair_execution_log.json",
                "negative_evidence_report.json",
                "experiment_repair_index.json",
                "benchmark_provenance_manifest.json",
                "literature_support_index.json",
            ],
            "policy": (
                "Publication manifest mirrors readiness evidence for review packaging. "
                "It does not override publish gates or convert blockers into final-publish readiness."
            ),
        },
        "blocker_count": len(blockers),
        "blockers": blockers,
    }
    return {**payload, "publication_fingerprint": _fingerprint(payload)}


def _project_supplemental_artifacts_payload(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    project_paper_path: Path,
    project_paper_sources_dir: Path,
    project_paper_revised_path: Path,
    project_revision_application_path: Path,
    project_revision_rereview_path: Path,
    checklist_path: Path,
    reviewer_response_path: Path,
    review_findings_path: Path,
    repair_execution_log_path: Path,
    claim_index_path: Path,
    retrieval_evidence_ledger_path: Path,
    lineage_archive_path: Path,
    literature_support_index_path: Path,
    paper_compiler_evidence_path: Path,
    publication_evidence_index_path: Path,
    publication_readiness_report_path: Path,
    benchmark_card_path: Path,
    benchmark_provenance_manifest_path: Path,
    benchmark_provenance_repair_index_path: Path,
    statistics_report_path: Path,
    experiment_repair_index_path: Path,
    negative_evidence_report_path: Path,
    offline_publication_case_path: Path,
    offline_publication_audit_path: Path,
    blockers: list[str],
) -> dict[str, Any]:
    artifacts = [
        _submission_asset_ref("manuscript", project_paper_path),
        _submission_asset_ref("paper_sources", project_paper_sources_dir),
        _submission_asset_ref("revised_manuscript", project_paper_revised_path),
        _submission_asset_ref("revision_application", project_revision_application_path),
        _submission_asset_ref("revision_rereview_report", project_revision_rereview_path),
        _submission_asset_ref("reproducibility_checklist", checklist_path),
        _submission_asset_ref("reviewer_response", reviewer_response_path),
        _submission_asset_ref("review_findings", review_findings_path),
        _submission_asset_ref("repair_execution_log", repair_execution_log_path),
        _submission_asset_ref("claim_evidence_index", claim_index_path),
        _submission_asset_ref("retrieval_evidence_ledger", retrieval_evidence_ledger_path),
        _submission_asset_ref("lineage_archive", lineage_archive_path),
        _submission_asset_ref("literature_support_index", literature_support_index_path),
        _submission_asset_ref("paper_compiler_evidence", paper_compiler_evidence_path),
        _submission_asset_ref("publication_evidence_index", publication_evidence_index_path),
        _submission_asset_ref("publication_readiness_report", publication_readiness_report_path),
        _submission_asset_ref("benchmark_card", benchmark_card_path),
        _submission_asset_ref("benchmark_provenance_manifest", benchmark_provenance_manifest_path),
        _submission_asset_ref("benchmark_provenance_repair_index", benchmark_provenance_repair_index_path),
        _submission_asset_ref("statistics_report", statistics_report_path),
        _submission_asset_ref("experiment_repair_index", experiment_repair_index_path),
        _submission_asset_ref("negative_evidence_report", negative_evidence_report_path),
        _submission_asset_ref("offline_publication_case", offline_publication_case_path),
        _submission_asset_ref("offline_publication_audit", offline_publication_audit_path),
    ]
    payload = {
        "supplemental_id": "project_supplemental_artifacts_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_ids": [run.id for run in selected_runs],
        "artifact_count": len(artifacts),
        "present_artifact_count": sum(1 for item in artifacts if item["exists"]),
        "artifacts": artifacts,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "scope_note": (
            "Supplemental artifacts index project-level reproducibility materials; it does not override "
            "publish gates or promote unsupported claims."
        ),
    }
    return {**payload, "supplemental_fingerprint": _fingerprint(payload)}


def _project_publication_readiness_report_payload(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    latest_brief: AutoResearchResearchBriefRead | None,
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    project_publish_gate_passed: bool,
    project_final_publish_ready: bool,
    project_submission_blockers: list[str],
    evidence_profile: dict[str, Any],
    paper_compiler_evidence: dict[str, Any],
    repair_execution_log: dict[str, Any],
    warnings: list[str],
    pending_revision_actions: list[AutoResearchReviewLoopActionRead],
    reviewer_response_complete: bool,
    claim_index_complete: bool,
    negative_evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    execution_coverage = paper_compiler_evidence.get("execution_coverage", {})
    phase6_negative_evidence_audit = _phase6_negative_evidence_report_audit(
        negative_evidence_report
    )
    benchmark_source_records = [
        _benchmark_source_record(item)
        for item in evidence_profile.get("run_profiles", [])
        if isinstance(item, dict)
    ]
    benchmark_schema_complete_run_ids = [
        str(record["run_id"])
        for record in benchmark_source_records
        if record["query_document_evidence_schema"]["schema_complete"]
    ]
    benchmark_schema_blockers = _dedupe(
        [
            f"{record.get('run_id', 'unknown_run')}: benchmark schema missing {role}"
            for record in benchmark_source_records
            for role in record["query_document_evidence_schema"]["missing_schema_roles"]
        ]
    )
    benchmark_schema_coverage = {
        "selected_run_count": len(benchmark_source_records),
        "schema_complete_run_count": len(benchmark_schema_complete_run_ids),
        "schema_complete_run_ids": benchmark_schema_complete_run_ids,
        "schema_coverage_complete": bool(benchmark_source_records)
        and len(benchmark_schema_complete_run_ids) == len(benchmark_source_records),
        "schema_blockers": benchmark_schema_blockers,
        "policy": PROJECT_BENCHMARK_SCHEMA_COVERAGE_POLICY,
    }
    benchmark_observation_blockers: list[str] = []
    for record in benchmark_source_records:
        run_id = record.get("run_id", "unknown_run")
        if int(record.get("query_count") or 0) <= 0:
            benchmark_observation_blockers.append(f"{run_id}: missing query_count")
        if int(record.get("document_count") or 0) <= 0:
            benchmark_observation_blockers.append(f"{run_id}: missing document_count")
        if bool(record.get("supports_claim_verification")):
            if int(record.get("evidence_annotation_count") or 0) <= 0:
                benchmark_observation_blockers.append(
                    f"{run_id}: missing evidence_annotation_count"
                )
        elif int(record.get("retrieval_relevance_count") or 0) <= 0:
            benchmark_observation_blockers.append(
                f"{run_id}: missing retrieval relevance annotations"
            )
    benchmark_observation_blockers = _dedupe(benchmark_observation_blockers)
    benchmark_source_observation_coverage = {
        "selected_run_count": len(benchmark_source_records),
        "query_count_by_run": {
            str(record.get("run_id")): int(record.get("query_count") or 0)
            for record in benchmark_source_records
        },
        "document_count_by_run": {
            str(record.get("run_id")): int(record.get("document_count") or 0)
            for record in benchmark_source_records
        },
        "evidence_annotation_count_by_run": {
            str(record.get("run_id")): int(record.get("evidence_annotation_count") or 0)
            for record in benchmark_source_records
        },
        "retrieval_relevance_count_by_run": {
            str(record.get("run_id")): int(record.get("retrieval_relevance_count") or 0)
            for record in benchmark_source_records
        },
        "required_observation_roles_by_run": {
            str(record.get("run_id")): list(record.get("required_observation_roles", []))
            for record in benchmark_source_records
        },
        "split_distribution": evidence_profile.get("snapshot_metadata", {}).get(
            "split_distribution", {}
        ),
        "label_distribution": evidence_profile.get("snapshot_metadata", {}).get(
            "label_distribution", {}
        ),
        "observation_coverage_complete": bool(benchmark_source_records)
        and not benchmark_observation_blockers,
        "observation_blockers": benchmark_observation_blockers,
        "policy": PROJECT_BENCHMARK_OBSERVATION_COVERAGE_POLICY,
    }
    limitations = _dedupe(
        [
            *warnings,
            *[item.text for item in ledger.limitations],
            *[
                reason
                for trace in traces
                for reason in trace.unsupported_reasons
                if trace.support_status != "supported"
            ],
        ]
    )
    kill_criteria = _dedupe(
        [
            *(
                ["Do not claim publication-grade contribution until project publish gate passes."]
                if not project_publish_gate_passed
                else []
            ),
            *(
                ["Do not submit as final publish while project submission blockers remain."]
                if project_submission_blockers
                else []
            ),
            *(
                ["Do not promote single-run or partial retrieval evidence to project-level scientific claims."]
                if len(selected_runs) < 2 or any(trace.support_status != "supported" for trace in traces)
                else []
            ),
            *(
                ["Do not finalize while bounded revision actions remain pending."]
                if pending_revision_actions
                else []
            ),
            *(
                [
                    (
                        "Do not submit as final publish until every selected benchmark source "
                        f"satisfies the >= {FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES} "
                        "normalized-example final-candidate gate."
                    )
                ]
                if not evidence_profile.get("benchmark_final_publish_candidate_ready")
                else []
            ),
            *(
                [
                    (
                        "Do not submit as final publish until selected benchmark evidence covers "
                        "at least two independent source datasets; same-release benchmark views "
                        "cannot prove cross-source generalization."
                    )
                ]
                if not evidence_profile.get("benchmark_source_independence_ready")
                else []
            ),
            *(
                [
                    "Do not submit as final publish while required Phase 6 negative-evidence categories lack deterministic artifacts."
                ]
                if phase6_negative_evidence_audit["missing_categories"]
                else []
            ),
        ]
    )
    required_followups = _dedupe(
        [
            *project_submission_blockers,
            *evidence_profile.get("blockers", []),
            *(
                ["Run an additional independent selected hypothesis or replication before project-level claims."]
                if not evidence_profile.get("replication_ready")
                else []
            ),
            *(
                [
                    (
                        "Repair benchmark scale/provenance with repository-local frozen/imported/remote-real "
                        "source records before final-publish review."
                    )
                ]
                if not evidence_profile.get("benchmark_scale_ready")
                or not evidence_profile.get("benchmark_provenance_ready")
                or not evidence_profile.get("benchmark_publication_ready")
                else []
            ),
            *(
                [
                    (
                        "Replace under-scale, fixture, or non-materialized selected benchmark "
                        "sources with frozen/imported/remote-real final-candidate benchmark evidence."
                    )
                ]
                if not evidence_profile.get("benchmark_final_publish_candidate_ready")
                else []
            ),
            *(
                [
                    (
                        "Add an independent external benchmark/source release beyond the repository-local "
                        "SciFact verification and retrieval views before cross-source final-publish claims."
                    )
                ]
                if not evidence_profile.get("benchmark_source_independence_ready")
                else []
            ),
            *[
                f"Repair benchmark schema coverage before final publish: {blocker}."
                for blocker in benchmark_schema_blockers
            ],
            *[
                f"Repair benchmark source observation coverage before final publish: {blocker}."
                for blocker in benchmark_observation_blockers
            ],
            *(
                ["Refresh literature scout with real cached arXiv, Semantic Scholar, or Crossref records."]
                if not evidence_profile.get("literature_ready")
                else []
            ),
            *(
                ["Refresh literature and retrieval evidence for unsupported or partial claim traces."]
                if any(trace.support_status != "supported" for trace in traces)
                else []
            ),
            *(
                ["Complete pending project-paper revision actions and re-review the manuscript."]
                if pending_revision_actions
                else []
            ),
            *(
                ["Complete blocked or pending repair execution actions before final packaging."]
                if repair_execution_log.get("blocked_action_count", 0) > 0
                or repair_execution_log.get("pending_action_count", 0) > 0
                else []
            ),
            *(
                ["Complete reviewer response before final packaging."]
                if not reviewer_response_complete
                else []
            ),
            *(
                ["Complete claim-evidence index before final packaging."]
                if not claim_index_complete
                else []
            ),
            *(
                ["Complete paper compiler evidence coverage before final packaging."]
                if not paper_compiler_evidence.get("complete")
                else []
            ),
            *(
                ["Link selected-run statistics to deterministic execution/import replay artifacts before final packaging."]
                if not execution_coverage.get("complete")
                else []
            ),
            *[
                f"Produce or import deterministic negative-evidence artifact for Phase 6 category: {category}."
                for category in phase6_negative_evidence_audit["missing_categories"]
            ],
        ]
    )
    readiness_checks = [
        {
            "check_id": "project_publish_gate",
            "passed": project_publish_gate_passed,
            "detail": "Project-level publish gate passed.",
        },
        {
            "check_id": "submission_blockers",
            "passed": not project_submission_blockers,
            "detail": "No project submission blockers remain.",
        },
        {
            "check_id": "revision_actions",
            "passed": not pending_revision_actions,
            "detail": "No pending project-paper revision actions remain.",
        },
        {
            "check_id": "repair_execution_log",
            "passed": bool(repair_execution_log.get("complete")),
            "detail": "Repair execution log has no pending, blocked, or failed repair actions.",
        },
        {
            "check_id": "reviewer_response",
            "passed": reviewer_response_complete,
            "detail": "Reviewer response is complete.",
        },
        {
            "check_id": "claim_evidence_index",
            "passed": claim_index_complete,
            "detail": "Claim-evidence index is complete.",
        },
        {
            "check_id": "benchmark_scale",
            "passed": bool(evidence_profile.get("benchmark_scale_ready")),
            "detail": (
                f"At least one selected run has >= {PUBLICATION_MIN_DATASET_EXAMPLES} benchmark examples."
            ),
        },
        {
            "check_id": "benchmark_provenance",
            "passed": bool(evidence_profile.get("benchmark_provenance_ready")),
            "detail": "Selected run benchmark provenance is complete and non-builtin.",
        },
        {
            "check_id": "benchmark_schema_coverage",
            "passed": bool(benchmark_schema_coverage["schema_coverage_complete"]),
            "detail": (
                "Selected benchmark sources expose task-aware query/document/evidence/label/split "
                "schema for provenance and final-publish-candidate review."
            ),
            "coverage": benchmark_schema_coverage,
            "blockers": benchmark_schema_blockers,
        },
        {
            "check_id": "benchmark_source_observation_coverage",
            "passed": bool(
                benchmark_source_observation_coverage["observation_coverage_complete"]
            ),
            "detail": (
                "Selected benchmark sources expose required query/document/evidence "
                "observation counts for provenance and final-publish-candidate review."
            ),
            "coverage": benchmark_source_observation_coverage,
            "blockers": benchmark_observation_blockers,
        },
        {
            "check_id": "benchmark_publication_grade",
            "passed": bool(evidence_profile.get("benchmark_publication_ready")),
            "detail": "All selected run benchmarks are marked publication-grade.",
        },
        {
            "check_id": "benchmark_final_publish_candidate_coverage",
            "passed": bool(evidence_profile.get("benchmark_final_publish_candidate_ready")),
            "detail": (
                "Every selected benchmark source satisfies final-publish-candidate coverage: "
                f">= {FINAL_PUBLISH_CANDIDATE_MIN_DATASET_EXAMPLES} normalized examples, "
                "non-fixture provenance, and materialized frozen/imported/remote-real source evidence."
            ),
            "coverage": evidence_profile.get("benchmark_final_publish_candidate_coverage", {}),
            "blockers": evidence_profile.get("benchmark_final_publish_candidate_coverage", {}).get(
                "blockers", []
            ),
        },
        {
            "check_id": "benchmark_source_independence",
            "passed": bool(evidence_profile.get("benchmark_source_independence_ready")),
            "detail": (
                "Selected benchmark evidence covers at least two independent source datasets; "
                "derived views of the same release are tracked but do not prove cross-source generalization."
            ),
            "coverage": evidence_profile.get("benchmark_source_independence_audit", {}),
            "blockers": evidence_profile.get("benchmark_source_independence_audit", {}).get(
                "blockers", []
            ),
        },
        {
            "check_id": "cross_run_replication",
            "passed": bool(evidence_profile.get("replication_ready")),
            "detail": "At least two selected runs support project-level claims.",
        },
        {
            "check_id": "real_literature_coverage",
            "passed": bool(evidence_profile.get("literature_ready")),
            "detail": (
                "Latest project brief includes multi-source real cached or network-sourced literature evidence."
            ),
        },
        {
            "check_id": "execution_evidence",
            "passed": bool(execution_coverage.get("complete")),
            "detail": "Selected-run statistics are linked to deterministic execution/import replay artifact refs.",
            "execution_source_counts": execution_coverage.get("execution_source_counts", {}),
            "execution_output_artifact_refs": execution_coverage.get("execution_output_artifact_refs", []),
            "blockers": execution_coverage.get("blockers", []),
        },
        {
            "check_id": "paper_compiler_evidence",
            "passed": bool(paper_compiler_evidence.get("complete")),
            "detail": "Project paper compiler evidence packet covers sections, claims, citations, results, statistics, provenance, revisions, and compile readiness.",
        },
        {
            "check_id": "phase6_negative_evidence_coverage",
            "passed": bool(phase6_negative_evidence_audit["coverage_complete"]),
            "detail": (
                "Required Phase 6 negative-evidence categories are covered by deterministic "
                "execution artifacts or retained as explicit missing-category blockers."
            ),
            "coverage": phase6_negative_evidence_audit,
            "missing_categories": phase6_negative_evidence_audit["missing_categories"],
            "negative_evidence_report_ref": phase6_negative_evidence_audit[
                "negative_evidence_report_ref"
            ],
        },
    ]
    payload = {
        "readiness_id": "project_publication_readiness_report_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "publication_grade_ready": project_final_publish_ready,
        "review_ready": True,
        "final_publish_ready": project_final_publish_ready,
        "selected_run_ids": [run.id for run in selected_runs],
        "selected_run_count": len(selected_runs),
        "supported_claim_trace_count": sum(1 for trace in traces if trace.support_status == "supported"),
        "partial_or_unsupported_claim_trace_count": sum(
            1 for trace in traces if trace.support_status != "supported"
        ),
        "blockers": project_submission_blockers,
        "limitations": limitations,
        "kill_criteria": kill_criteria,
        "required_followups": required_followups,
        "evidence_profile": evidence_profile,
        "benchmark_schema_coverage": benchmark_schema_coverage,
        "benchmark_source_observation_coverage": benchmark_source_observation_coverage,
        "benchmark_source_independence_audit": evidence_profile.get(
            "benchmark_source_independence_audit", {}
        ),
        "paper_compiler_evidence": paper_compiler_evidence,
        "repair_execution_log": repair_execution_log,
        "phase6_negative_evidence_audit": phase6_negative_evidence_audit,
        "negative_evidence_report_ref": phase6_negative_evidence_audit[
            "negative_evidence_report_ref"
        ],
        "checks": readiness_checks,
        "scope_note": (
            "This readiness report is evidence-constrained. It preserves blockers and does not convert "
            "review-ready packages into final publish packages."
        ),
    }
    return {**payload, "readiness_fingerprint": _fingerprint(payload)}


def _materialize_project_submission_package(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    latest_brief: AutoResearchResearchBriefRead | None,
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    project_paper_path: Path,
    project_paper_sources_dir: Path,
    project_paper_revised_path: Path,
    project_revision_application_path: Path,
    project_revision_rereview_path: Path,
    project_paper_sections: list[str],
    project_paper_missing_sections: list[str],
    project_paper_compile_report: AutoResearchPaperCompileReportRead,
    project_paper_revision_actions: list[AutoResearchReviewLoopActionRead],
    project_review_findings: dict[str, Any],
    project_publish_gate_passed: bool,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    submission_dir = _project_submission_dir(project_id)
    manifest_path = submission_dir / PROJECT_SUBMISSION_MANIFEST_FILENAME
    checklist_path = submission_dir / PROJECT_REPRODUCIBILITY_CHECKLIST_FILENAME
    reviewer_response_path = submission_dir / PROJECT_REVIEWER_RESPONSE_FILENAME
    review_findings_path = submission_dir / PROJECT_REVIEW_FINDINGS_FILENAME
    repair_execution_log_path = submission_dir / PROJECT_REPAIR_EXECUTION_LOG_FILENAME
    claim_index_path = submission_dir / PROJECT_CLAIM_EVIDENCE_INDEX_FILENAME
    retrieval_evidence_ledger_path = submission_dir / PROJECT_RETRIEVAL_EVIDENCE_LEDGER_FILENAME
    lineage_archive_path = submission_dir / PROJECT_LINEAGE_ARCHIVE_FILENAME
    literature_support_index_path = submission_dir / PROJECT_LITERATURE_SUPPORT_INDEX_FILENAME
    paper_compiler_evidence_path = project_paper_sources_dir / PROJECT_PAPER_COMPILER_EVIDENCE_FILENAME
    publication_evidence_index_path = submission_dir / PROJECT_PUBLICATION_EVIDENCE_INDEX_FILENAME
    publication_readiness_report_path = submission_dir / PROJECT_PUBLICATION_READINESS_REPORT_FILENAME
    supplemental_artifacts_path = submission_dir / PROJECT_SUPPLEMENTAL_ARTIFACTS_FILENAME
    code_package_path = submission_dir / PROJECT_CODE_PACKAGE_FILENAME
    benchmark_card_path = submission_dir / PROJECT_BENCHMARK_CARD_FILENAME
    benchmark_provenance_manifest_path = submission_dir / PROJECT_BENCHMARK_PROVENANCE_MANIFEST_FILENAME
    benchmark_provenance_repair_index_path = (
        submission_dir / PROJECT_BENCHMARK_PROVENANCE_REPAIR_INDEX_FILENAME
    )
    statistics_report_path = submission_dir / PROJECT_STATISTICS_REPORT_FILENAME
    experiment_repair_index_path = submission_dir / PROJECT_EXPERIMENT_REPAIR_INDEX_FILENAME
    negative_evidence_report_path = submission_dir / PROJECT_NEGATIVE_EVIDENCE_REPORT_FILENAME
    offline_publication_case_path = submission_dir / PROJECT_OFFLINE_PUBLICATION_CASE_FILENAME
    offline_publication_audit_path = submission_dir / PROJECT_OFFLINE_PUBLICATION_AUDIT_FILENAME
    publication_manifest_path = submission_dir / PROJECT_PUBLICATION_MANIFEST_FILENAME
    pending_revision_actions = [
        action for action in project_paper_revision_actions if action.status != "completed"
    ]
    evidence_profile = _project_publication_evidence_profile(
        selected_runs=selected_runs,
        latest_brief=latest_brief,
    )
    paper_compiler_evidence = _build_project_paper_compiler_evidence_packet(
        project_id=project_id,
        selected_runs=selected_runs,
        latest_brief=latest_brief,
        ledger=ledger,
        traces=traces,
        markdown=project_paper_path.read_text(encoding="utf-8") if project_paper_path.is_file() else "",
        project_paper_sections=project_paper_sections,
        project_paper_missing_sections=project_paper_missing_sections,
        project_paper_compile_report=project_paper_compile_report,
        project_paper_revision_actions=project_paper_revision_actions,
        project_review_findings=project_review_findings,
        evidence_profile=evidence_profile,
    )
    paper_compiler_evidence_path.write_text(
        json.dumps(paper_compiler_evidence, indent=2),
        encoding="utf-8",
    )
    publication_evidence_index_payload = _project_publication_evidence_index_payload(
        project_id=project_id,
        selected_runs=selected_runs,
        ledger=ledger,
        traces=traces,
        paper_compiler_evidence_path=paper_compiler_evidence_path,
        benchmark_provenance_manifest_path=benchmark_provenance_manifest_path,
        benchmark_provenance_repair_index_path=benchmark_provenance_repair_index_path,
        evidence_profile=evidence_profile,
        blockers=list(paper_compiler_evidence.get("blockers", [])),
    )
    publication_evidence_index_path.write_text(
        json.dumps(publication_evidence_index_payload, indent=2),
        encoding="utf-8",
    )
    benchmark_provenance_manifest_payload = _project_benchmark_provenance_manifest_payload(
        project_id=project_id,
        selected_runs=selected_runs,
        evidence_profile=evidence_profile,
    )
    benchmark_provenance_manifest_path.write_text(
        json.dumps(benchmark_provenance_manifest_payload, indent=2),
        encoding="utf-8",
    )
    benchmark_provenance_repair_index_payload = _build_project_benchmark_provenance_repair_index(
        project_id=project_id,
        evidence_profile=evidence_profile,
    )
    benchmark_provenance_repair_index_path.write_text(
        json.dumps(benchmark_provenance_repair_index_payload, indent=2),
        encoding="utf-8",
    )
    repair_execution_log_payload = _project_repair_execution_log_payload(
        project_id=project_id,
        project_paper_revision_actions=project_paper_revision_actions,
    )
    repair_execution_log_path.write_text(
        json.dumps(repair_execution_log_payload, indent=2),
        encoding="utf-8",
    )
    statistics_report_payload = _project_statistics_report_payload(
        project_id=project_id,
        selected_runs=selected_runs,
        paper_compiler_evidence=paper_compiler_evidence,
        repair_execution_log=repair_execution_log_payload,
    )
    statistics_report_path.write_text(
        json.dumps(statistics_report_payload, indent=2),
        encoding="utf-8",
    )
    experiment_repair_index_payload = _build_project_experiment_repair_index(
        project_id=project_id,
        evidence_profile=evidence_profile,
        statistics_profiles=[_run_statistics_profile(run) for run in selected_runs],
        selected_runs=selected_runs,
    )
    experiment_repair_index_path.write_text(
        json.dumps(experiment_repair_index_payload, indent=2),
        encoding="utf-8",
    )
    negative_evidence_report_payload = _project_negative_evidence_report_payload(
        project_id=project_id,
        selected_runs=selected_runs,
        ledger=ledger,
        traces=traces,
        statistics_report=statistics_report_payload,
        experiment_repair_index=experiment_repair_index_payload,
        repair_execution_log=repair_execution_log_payload,
    )
    negative_evidence_report_path.write_text(
        json.dumps(negative_evidence_report_payload, indent=2),
        encoding="utf-8",
    )
    project_compile_blockers = _dedupe(
        [
            str(item)
            for item in project_paper_compile_report.evidence_blockers
            if str(item) in set(paper_compiler_evidence.get("blockers", []))
        ]
    )

    project_submission_blockers = _dedupe(
        [
            *blockers,
            *evidence_profile["blockers"],
            *paper_compiler_evidence.get("blockers", []),
            *negative_evidence_report_payload.get("blockers", []),
            *project_paper_missing_sections,
            *project_compile_blockers,
            *(
                ["Project paper has pending revision actions; final submission must wait for re-review."]
                if pending_revision_actions
                else []
            ),
            *(
                []
                if project_publish_gate_passed
                else ["Project publish gate has not passed; package is review-ready only."]
            ),
        ]
    )
    checklist_markdown = _project_reproducibility_checklist_markdown(
        selected_runs=selected_runs,
        project_paper_sections=project_paper_sections,
        project_paper_missing_sections=project_paper_missing_sections,
        project_paper_compile_report=project_paper_compile_report,
        project_paper_revision_actions=project_paper_revision_actions,
        project_review_findings=project_review_findings,
        project_publish_gate_passed=project_publish_gate_passed,
        project_submission_blockers=project_submission_blockers,
    )
    checklist_path.write_text(checklist_markdown, encoding="utf-8")
    reviewer_response_markdown, reviewer_response_complete = _project_reviewer_response_markdown(
        project_paper_revision_actions=project_paper_revision_actions,
        warnings=warnings,
        blockers=project_submission_blockers,
    )
    reviewer_response_path.write_text(reviewer_response_markdown, encoding="utf-8")
    review_findings_path.write_text(
        json.dumps(project_review_findings, indent=2),
        encoding="utf-8",
    )
    claim_index_markdown, claim_index_complete = _project_claim_evidence_index_markdown(
        ledger=ledger,
        traces=traces,
    )
    claim_index_path.write_text(claim_index_markdown, encoding="utf-8")
    retrieval_evidence_ledger_payload = _project_retrieval_evidence_ledger_payload(
        project_id=project_id,
        selected_runs=selected_runs,
    )
    retrieval_evidence_ledger_path.write_text(
        json.dumps(retrieval_evidence_ledger_payload, indent=2),
        encoding="utf-8",
    )
    benchmark_card_payload = _project_benchmark_card_payload(
        project_id=project_id,
        selected_runs=selected_runs,
        project_publish_gate_passed=project_publish_gate_passed,
    )
    benchmark_card_path.write_text(json.dumps(benchmark_card_payload, indent=2), encoding="utf-8")
    literature_support_index_payload = _build_project_literature_support_index(
        project_id=project_id,
        latest_brief=latest_brief,
        traces=traces,
        evidence_profile=evidence_profile,
    )
    literature_support_index_path.write_text(
        json.dumps(literature_support_index_payload, indent=2),
        encoding="utf-8",
    )
    package_output_roles = list(PROJECT_SUBMISSION_PACKAGE_ROLES)
    offline_publication_case_payload = _project_offline_publication_case_payload(
        project_id=project_id,
        latest_brief=latest_brief,
        selected_runs=selected_runs,
        evidence_profile=evidence_profile,
        literature_support_index=literature_support_index_payload,
        benchmark_card=benchmark_card_payload,
        benchmark_provenance_manifest=benchmark_provenance_manifest_payload,
        statistics_report=statistics_report_payload,
        negative_evidence_report=negative_evidence_report_payload,
        repair_execution_log=repair_execution_log_payload,
        package_output_roles=package_output_roles,
    )
    offline_publication_case_path.write_text(
        json.dumps(offline_publication_case_payload, indent=2),
        encoding="utf-8",
    )
    lineage_payload = {
        "archive_id": "project_submission_lineage_archive_v1",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "selected_run_ids": [run.id for run in selected_runs],
        "selected_run_count": len(selected_runs),
        "conclusion_ledger": ledger.model_dump(mode="json"),
        "claim_traces": [trace.model_dump(mode="json") for trace in traces],
        "revision_actions": [action.model_dump(mode="json") for action in project_paper_revision_actions],
        "project_review_findings_path": str(review_findings_path),
        "project_repair_execution_log_path": str(repair_execution_log_path),
        "project_retrieval_evidence_ledger_path": str(retrieval_evidence_ledger_path),
        "project_paper_path": str(project_paper_path),
        "project_paper_sources_dir": str(project_paper_sources_dir),
        "project_benchmark_card_path": str(benchmark_card_path),
        "project_paper_compiler_evidence_path": str(paper_compiler_evidence_path),
        "project_literature_support_index_path": str(literature_support_index_path),
        "project_publication_evidence_index_path": str(publication_evidence_index_path),
        "project_benchmark_provenance_manifest_path": str(benchmark_provenance_manifest_path),
        "project_benchmark_provenance_repair_index_path": str(benchmark_provenance_repair_index_path),
        "project_statistics_report_path": str(statistics_report_path),
        "project_experiment_repair_index_path": str(experiment_repair_index_path),
        "project_negative_evidence_report_path": str(negative_evidence_report_path),
        "project_offline_publication_case_path": str(offline_publication_case_path),
        "project_publish_gate_passed": project_publish_gate_passed,
        "project_submission_blockers": project_submission_blockers,
    }
    lineage_archive_path.write_text(json.dumps(lineage_payload, indent=2), encoding="utf-8")
    project_final_publish_ready_candidate = (
        project_publish_gate_passed
        and reviewer_response_complete
        and claim_index_complete
        and not project_submission_blockers
    )
    readiness_payload = _project_publication_readiness_report_payload(
        project_id=project_id,
        selected_runs=selected_runs,
        latest_brief=latest_brief,
        ledger=ledger,
        traces=traces,
        project_publish_gate_passed=project_publish_gate_passed,
        project_final_publish_ready=project_final_publish_ready_candidate,
        project_submission_blockers=project_submission_blockers,
        evidence_profile=evidence_profile,
        paper_compiler_evidence=paper_compiler_evidence,
        repair_execution_log=repair_execution_log_payload,
        warnings=warnings,
        pending_revision_actions=pending_revision_actions,
        reviewer_response_complete=reviewer_response_complete,
        claim_index_complete=claim_index_complete,
        negative_evidence_report=negative_evidence_report_payload,
    )
    publication_readiness_report_path.write_text(json.dumps(readiness_payload, indent=2), encoding="utf-8")
    supplemental_payload = _project_supplemental_artifacts_payload(
        project_id=project_id,
        selected_runs=selected_runs,
        project_paper_path=project_paper_path,
        project_paper_sources_dir=project_paper_sources_dir,
        project_paper_revised_path=project_paper_revised_path,
        project_revision_application_path=project_revision_application_path,
        project_revision_rereview_path=project_revision_rereview_path,
        checklist_path=checklist_path,
        reviewer_response_path=reviewer_response_path,
        review_findings_path=review_findings_path,
        repair_execution_log_path=repair_execution_log_path,
        claim_index_path=claim_index_path,
        retrieval_evidence_ledger_path=retrieval_evidence_ledger_path,
        lineage_archive_path=lineage_archive_path,
        literature_support_index_path=literature_support_index_path,
        paper_compiler_evidence_path=paper_compiler_evidence_path,
        publication_evidence_index_path=publication_evidence_index_path,
        publication_readiness_report_path=publication_readiness_report_path,
        benchmark_card_path=benchmark_card_path,
        benchmark_provenance_manifest_path=benchmark_provenance_manifest_path,
        benchmark_provenance_repair_index_path=benchmark_provenance_repair_index_path,
        statistics_report_path=statistics_report_path,
        experiment_repair_index_path=experiment_repair_index_path,
        negative_evidence_report_path=negative_evidence_report_path,
        offline_publication_case_path=offline_publication_case_path,
        offline_publication_audit_path=offline_publication_audit_path,
        blockers=project_submission_blockers,
    )
    supplemental_artifacts_path.write_text(json.dumps(supplemental_payload, indent=2), encoding="utf-8")
    code_package_path = _materialize_project_code_package(
        project_id=project_id,
        paths=[
            project_paper_path,
            project_paper_sources_dir,
            project_paper_revised_path,
            project_revision_application_path,
            project_revision_rereview_path,
            checklist_path,
            reviewer_response_path,
            review_findings_path,
            repair_execution_log_path,
            claim_index_path,
            retrieval_evidence_ledger_path,
            lineage_archive_path,
            literature_support_index_path,
            paper_compiler_evidence_path,
            publication_evidence_index_path,
            publication_readiness_report_path,
            supplemental_artifacts_path,
            benchmark_card_path,
            benchmark_provenance_manifest_path,
            benchmark_provenance_repair_index_path,
            statistics_report_path,
            experiment_repair_index_path,
            negative_evidence_report_path,
            offline_publication_case_path,
            offline_publication_audit_path,
        ],
    )
    selected_run_ids = [run.id for run in selected_runs]
    generated_assets = [
        _submission_asset_ref("project_submission_manifest", manifest_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_reproducibility_checklist", checklist_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_reviewer_response", reviewer_response_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_review_findings", review_findings_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_repair_execution_log", repair_execution_log_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_claim_evidence_index", claim_index_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_retrieval_evidence_ledger", retrieval_evidence_ledger_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_lineage_archive", lineage_archive_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_literature_support_index", literature_support_index_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_paper_compiler_evidence", paper_compiler_evidence_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_publication_evidence_index", publication_evidence_index_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_publication_readiness_report", publication_readiness_report_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_supplemental_artifacts", supplemental_artifacts_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_manuscript_markdown", project_paper_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_paper_sources", project_paper_sources_dir, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_revised_manuscript_markdown", project_paper_revised_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_revision_application", project_revision_application_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_revision_rereview_report", project_revision_rereview_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_code_package", code_package_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_benchmark_card", benchmark_card_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_benchmark_provenance_manifest", benchmark_provenance_manifest_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_benchmark_provenance_repair_index", benchmark_provenance_repair_index_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_statistics_report", statistics_report_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_experiment_repair_index", experiment_repair_index_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_negative_evidence_report", negative_evidence_report_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_offline_publication_case", offline_publication_case_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_offline_publication_audit", offline_publication_audit_path, selected_run_ids=selected_run_ids),
        _submission_asset_ref("project_publication_manifest", publication_manifest_path, selected_run_ids=selected_run_ids),
    ]
    project_review_bundle_ready = all(item["exists"] for item in generated_assets[1:])
    project_final_publish_ready = (
        project_review_bundle_ready
        and project_publish_gate_passed
        and reviewer_response_complete
        and claim_index_complete
        and not project_submission_blockers
    )
    generated_assets = _enrich_submission_asset_statuses(
        generated_assets,
        readiness_report=readiness_payload,
        final_publish_ready=project_final_publish_ready,
    )
    submission_manifest = {
        "submission_id": f"project_submission_{project_id}",
        "project_id": project_id,
        "generated_at": _utcnow().isoformat(),
        "bundle_kind": "final_publish_bundle" if project_final_publish_ready else "review_bundle",
        "review_bundle_ready": project_review_bundle_ready,
        "final_publish_ready": project_final_publish_ready,
        "project_publish_gate_passed": project_publish_gate_passed,
        "selected_run_ids": [run.id for run in selected_runs],
        "manuscript_path": str(project_paper_path),
        "paper_sources_dir": str(project_paper_sources_dir),
        "generated_assets": generated_assets[1:],
        "blocked_asset_count": sum(1 for item in generated_assets[1:] if item.get("final_publish_blocking")),
        "final_publish_blocking_asset_roles": [
            item.get("role") for item in generated_assets[1:] if item.get("final_publish_blocking")
        ],
        "blocker_count": len(project_submission_blockers),
        "blockers": project_submission_blockers,
        "revision_action_count": len(project_paper_revision_actions),
        "revision_pending_action_count": len(pending_revision_actions),
        "revision_completed_action_count": sum(
            1 for action in project_paper_revision_actions if action.status == "completed"
        ),
        "revision_actions": [action.title for action in project_paper_revision_actions],
        "phase6_negative_evidence_coverage": _phase6_negative_evidence_report_audit(
            negative_evidence_report_payload
        ),
        "negative_evidence_categories": _negative_category_list(
            negative_evidence_report_payload.get("phase6_categories")
        ),
        "negative_evidence_report_ref": "submission_package/negative_evidence_report.json",
    }
    manifest_path.write_text(json.dumps(submission_manifest, indent=2), encoding="utf-8")
    offline_publication_audit_payload = _project_offline_publication_audit_payload(
        project_id=project_id,
        selected_runs=selected_runs,
        evidence_profile=evidence_profile,
        literature_support_index=literature_support_index_payload,
        benchmark_provenance_manifest=benchmark_provenance_manifest_payload,
        experiment_repair_index=experiment_repair_index_payload,
        statistics_report=statistics_report_payload,
        negative_evidence_report=negative_evidence_report_payload,
        rereview_report=(
            json.loads(project_revision_rereview_path.read_text(encoding="utf-8"))
            if project_revision_rereview_path.is_file()
            else {}
        ),
        submission_manifest=submission_manifest,
        project_submission_blockers=project_submission_blockers,
    )
    offline_publication_audit_path.write_text(
        json.dumps(offline_publication_audit_payload, indent=2),
        encoding="utf-8",
    )
    supplemental_payload = _project_supplemental_artifacts_payload(
        project_id=project_id,
        selected_runs=selected_runs,
        project_paper_path=project_paper_path,
        project_paper_sources_dir=project_paper_sources_dir,
        project_paper_revised_path=project_paper_revised_path,
        project_revision_application_path=project_revision_application_path,
        project_revision_rereview_path=project_revision_rereview_path,
        checklist_path=checklist_path,
        reviewer_response_path=reviewer_response_path,
        review_findings_path=review_findings_path,
        repair_execution_log_path=repair_execution_log_path,
        claim_index_path=claim_index_path,
        retrieval_evidence_ledger_path=retrieval_evidence_ledger_path,
        lineage_archive_path=lineage_archive_path,
        literature_support_index_path=literature_support_index_path,
        paper_compiler_evidence_path=paper_compiler_evidence_path,
        publication_evidence_index_path=publication_evidence_index_path,
        publication_readiness_report_path=publication_readiness_report_path,
        benchmark_card_path=benchmark_card_path,
        benchmark_provenance_manifest_path=benchmark_provenance_manifest_path,
        benchmark_provenance_repair_index_path=benchmark_provenance_repair_index_path,
        statistics_report_path=statistics_report_path,
        experiment_repair_index_path=experiment_repair_index_path,
        negative_evidence_report_path=negative_evidence_report_path,
        offline_publication_case_path=offline_publication_case_path,
        offline_publication_audit_path=offline_publication_audit_path,
        blockers=project_submission_blockers,
    )
    supplemental_artifacts_path.write_text(json.dumps(supplemental_payload, indent=2), encoding="utf-8")
    code_package_path = _materialize_project_code_package(
        project_id=project_id,
        paths=[
            project_paper_path,
            project_paper_sources_dir,
            project_paper_revised_path,
            project_revision_application_path,
            project_revision_rereview_path,
            checklist_path,
            reviewer_response_path,
            review_findings_path,
            repair_execution_log_path,
            claim_index_path,
            retrieval_evidence_ledger_path,
            lineage_archive_path,
            literature_support_index_path,
            paper_compiler_evidence_path,
            publication_evidence_index_path,
            publication_readiness_report_path,
            supplemental_artifacts_path,
            benchmark_card_path,
            benchmark_provenance_manifest_path,
            benchmark_provenance_repair_index_path,
            statistics_report_path,
            experiment_repair_index_path,
            negative_evidence_report_path,
            offline_publication_case_path,
            offline_publication_audit_path,
        ],
    )
    for role, path in {
        "project_supplemental_artifacts": supplemental_artifacts_path,
        "project_code_package": code_package_path,
    }.items():
        for index, asset in enumerate(generated_assets):
            if asset["role"] == role:
                generated_assets[index] = _submission_asset_ref(
                    role,
                    path,
                    selected_run_ids=selected_run_ids,
                )
                break
    for index, asset in enumerate(generated_assets):
        if asset["role"] == "project_offline_publication_audit":
            generated_assets[index] = _submission_asset_ref(
                "project_offline_publication_audit",
                offline_publication_audit_path,
                selected_run_ids=selected_run_ids,
            )
            break
    generated_assets[0] = _submission_asset_ref(
        "project_submission_manifest",
        manifest_path,
        selected_run_ids=selected_run_ids,
    )
    project_review_bundle_ready = all(item["exists"] for item in generated_assets)
    project_final_publish_ready = (
        project_review_bundle_ready
        and project_publish_gate_passed
        and reviewer_response_complete
        and claim_index_complete
        and not project_submission_blockers
    )
    generated_assets = _enrich_submission_asset_statuses(
        generated_assets,
        readiness_report=readiness_payload,
        final_publish_ready=project_final_publish_ready,
    )
    publication_manifest_payload = _project_publication_manifest_payload(
        project_id=project_id,
        project_publish_gate_passed=project_publish_gate_passed,
        project_review_bundle_ready=project_review_bundle_ready,
        project_final_publish_ready=project_final_publish_ready,
        selected_runs=selected_runs,
        project_paper_path=project_paper_path,
        project_paper_sources_dir=project_paper_sources_dir,
        project_paper_revised_path=project_paper_revised_path,
        project_revision_application_path=project_revision_application_path,
        project_revision_rereview_path=project_revision_rereview_path,
        submission_manifest_path=manifest_path,
        checklist_path=checklist_path,
        reviewer_response_path=reviewer_response_path,
        review_findings_path=review_findings_path,
        repair_execution_log_path=repair_execution_log_path,
        claim_index_path=claim_index_path,
        retrieval_evidence_ledger_path=retrieval_evidence_ledger_path,
        lineage_archive_path=lineage_archive_path,
        literature_support_index_path=literature_support_index_path,
        paper_compiler_evidence_path=paper_compiler_evidence_path,
        publication_evidence_index_path=publication_evidence_index_path,
        publication_readiness_report_path=publication_readiness_report_path,
        supplemental_artifacts_path=supplemental_artifacts_path,
        code_package_path=code_package_path,
        benchmark_card_path=benchmark_card_path,
        benchmark_provenance_manifest_path=benchmark_provenance_manifest_path,
        benchmark_provenance_repair_index_path=benchmark_provenance_repair_index_path,
        statistics_report_path=statistics_report_path,
        experiment_repair_index_path=experiment_repair_index_path,
        negative_evidence_report_path=negative_evidence_report_path,
        offline_publication_case_path=offline_publication_case_path,
        offline_publication_audit_path=offline_publication_audit_path,
        blockers=project_submission_blockers,
        generated_assets=generated_assets[1:],
        readiness_report=readiness_payload,
        statistics_report=statistics_report_payload,
        negative_evidence_report=negative_evidence_report_payload,
    )
    publication_manifest_path.write_text(
        json.dumps(publication_manifest_payload, indent=2),
        encoding="utf-8",
    )
    generated_assets[-1] = _submission_asset_ref(
        "project_publication_manifest",
        publication_manifest_path,
        selected_run_ids=selected_run_ids,
    )
    project_review_bundle_ready = all(item["exists"] for item in generated_assets)
    project_final_publish_ready = (
        project_review_bundle_ready
        and project_publish_gate_passed
        and reviewer_response_complete
        and claim_index_complete
        and not project_submission_blockers
    )
    generated_assets = _enrich_submission_asset_statuses(
        generated_assets,
        readiness_report=readiness_payload,
        final_publish_ready=project_final_publish_ready,
    )
    submission_manifest = {
        **submission_manifest,
        "review_bundle_ready": project_review_bundle_ready,
        "final_publish_ready": project_final_publish_ready,
        "generated_assets": generated_assets[1:],
        "blocked_asset_count": sum(1 for item in generated_assets[1:] if item.get("final_publish_blocking")),
        "final_publish_blocking_asset_roles": [
            item.get("role") for item in generated_assets[1:] if item.get("final_publish_blocking")
        ],
        "supplemental_artifacts_path": str(supplemental_artifacts_path),
        "paper_compiler_evidence_path": str(paper_compiler_evidence_path),
        "review_findings_path": str(review_findings_path),
        "repair_execution_log_path": str(repair_execution_log_path),
        "retrieval_evidence_ledger_path": str(retrieval_evidence_ledger_path),
        "literature_support_index_path": str(literature_support_index_path),
        "publication_evidence_index_path": str(publication_evidence_index_path),
        "code_package_path": str(code_package_path),
        "benchmark_card_path": str(benchmark_card_path),
        "benchmark_provenance_manifest_path": str(benchmark_provenance_manifest_path),
        "benchmark_provenance_repair_index_path": str(benchmark_provenance_repair_index_path),
        "statistics_report_path": str(statistics_report_path),
        "experiment_repair_index_path": str(experiment_repair_index_path),
        "negative_evidence_report_path": str(negative_evidence_report_path),
        "offline_publication_case_path": str(offline_publication_case_path),
        "offline_publication_audit_path": str(offline_publication_audit_path),
        "publication_manifest_path": str(publication_manifest_path),
        "phase6_negative_evidence_coverage": _phase6_negative_evidence_report_audit(
            negative_evidence_report_payload
        ),
        "negative_evidence_categories": _negative_category_list(
            negative_evidence_report_payload.get("phase6_categories")
        ),
        "negative_evidence_report_ref": "submission_package/negative_evidence_report.json",
    }
    manifest_path.write_text(json.dumps(submission_manifest, indent=2), encoding="utf-8")
    publication_manifest_payload = {
        **publication_manifest_payload,
        "bundle_kind": "final_publish_bundle" if project_final_publish_ready else "review_bundle",
        "review_bundle_ready": project_review_bundle_ready,
        "final_publish_ready": project_final_publish_ready,
        "submission_manifest_sha256": _file_sha256(manifest_path),
        "readiness_decision": {
            **publication_manifest_payload.get("readiness_decision", {}),
            "review_ready": project_review_bundle_ready,
            "final_publish_ready": project_final_publish_ready,
            "bundle_kind": "final_publish_bundle" if project_final_publish_ready else "review_bundle",
            "phase6_negative_evidence_coverage": _phase6_negative_evidence_report_audit(
                negative_evidence_report_payload
            ),
            "negative_evidence_categories": _negative_category_list(
                negative_evidence_report_payload.get("phase6_categories")
            ),
            "negative_evidence_report_ref": "submission_package/negative_evidence_report.json",
        },
        "asset_count": len(generated_assets[1:]),
        "missing_asset_count": sum(1 for item in generated_assets[1:] if item.get("missing_status") != "present"),
        "blocked_asset_count": sum(1 for item in generated_assets[1:] if item.get("final_publish_blocking")),
        "final_publish_blocking_asset_roles": [
            item.get("role") for item in generated_assets[1:] if item.get("final_publish_blocking")
        ],
        "asset_roles": [item.get("role") for item in generated_assets[1:]],
        "generated_assets": [
            (
                {
                    **item,
                    "sha256": None,
                    "self_referential_hash": True,
                    "integrity_note": (
                        "The publication manifest cannot embed its own final file sha256; "
                        "verify the final manifest file hash from the filesystem or export envelope."
                    ),
                }
                if item.get("role") == "project_publication_manifest"
                else item
            )
            for item in generated_assets[1:]
        ],
    }
    publication_manifest_path.write_text(
        json.dumps(publication_manifest_payload, indent=2),
        encoding="utf-8",
    )
    generated_assets[0] = _submission_asset_ref(
        "project_submission_manifest",
        manifest_path,
        selected_run_ids=selected_run_ids,
    )
    generated_assets[-1] = _submission_asset_ref(
        "project_publication_manifest",
        publication_manifest_path,
        selected_run_ids=selected_run_ids,
    )
    return {
        "project_submission_dir": str(submission_dir),
        "project_submission_manifest": submission_manifest,
        "project_submission_manifest_path": str(manifest_path),
        "project_reproducibility_checklist_path": str(checklist_path),
        "project_reviewer_response_path": str(reviewer_response_path),
        "project_review_findings_path": str(review_findings_path),
        "project_repair_execution_log_path": str(repair_execution_log_path),
        "project_claim_evidence_index_path": str(claim_index_path),
        "project_retrieval_evidence_ledger_path": str(retrieval_evidence_ledger_path),
        "project_lineage_archive_path": str(lineage_archive_path),
        "project_literature_support_index_path": str(literature_support_index_path),
        "project_paper_compiler_evidence_path": str(paper_compiler_evidence_path),
        "project_publication_evidence_index_path": str(publication_evidence_index_path),
        "project_publication_readiness_report_path": str(publication_readiness_report_path),
        "project_supplemental_artifacts_path": str(supplemental_artifacts_path),
        "project_paper_revised_path": str(project_paper_revised_path),
        "project_revision_application_path": str(project_revision_application_path),
        "project_revision_rereview_path": str(project_revision_rereview_path),
        "project_code_package_path": str(code_package_path),
        "project_benchmark_card_path": str(benchmark_card_path),
        "project_benchmark_provenance_manifest_path": str(benchmark_provenance_manifest_path),
        "project_benchmark_provenance_repair_index_path": str(benchmark_provenance_repair_index_path),
        "project_statistics_report_path": str(statistics_report_path),
        "project_experiment_repair_index_path": str(experiment_repair_index_path),
        "project_negative_evidence_report_path": str(negative_evidence_report_path),
        "project_offline_publication_case_path": str(offline_publication_case_path),
        "project_offline_publication_audit_path": str(offline_publication_audit_path),
        "project_publication_manifest_path": str(publication_manifest_path),
        "project_review_bundle_ready": project_review_bundle_ready,
        "project_final_publish_ready": project_final_publish_ready,
        "project_submission_ready": project_final_publish_ready,
        "project_submission_asset_count": sum(1 for item in generated_assets if item["exists"]),
        "project_submission_blockers": project_submission_blockers,
        "project_reviewer_response_complete": reviewer_response_complete,
        "project_review_findings_complete": review_findings_path.is_file(),
        "project_repair_execution_log_complete": repair_execution_log_path.is_file(),
        "project_claim_evidence_index_complete": claim_index_complete,
        "project_retrieval_evidence_ledger_complete": retrieval_evidence_ledger_path.is_file(),
        "project_lineage_archive_complete": lineage_archive_path.is_file(),
        "project_literature_support_index_complete": literature_support_index_path.is_file(),
        "project_paper_compiler_evidence_complete": paper_compiler_evidence_path.is_file(),
        "project_publication_evidence_index_complete": publication_evidence_index_path.is_file(),
        "project_publication_readiness_report_complete": publication_readiness_report_path.is_file(),
        "project_supplemental_artifacts_complete": supplemental_artifacts_path.is_file(),
        "project_revision_application_complete": project_revision_application_path.is_file(),
        "project_revision_rereview_complete": project_revision_rereview_path.is_file(),
        "project_code_package_complete": code_package_path.is_file(),
        "project_benchmark_card_complete": benchmark_card_path.is_file(),
        "project_benchmark_provenance_manifest_complete": benchmark_provenance_manifest_path.is_file(),
        "project_benchmark_provenance_repair_index_complete": benchmark_provenance_repair_index_path.is_file(),
        "project_statistics_report_complete": statistics_report_path.is_file(),
        "project_experiment_repair_index_complete": experiment_repair_index_path.is_file(),
        "project_negative_evidence_report_complete": negative_evidence_report_path.is_file(),
        "project_offline_publication_case_complete": offline_publication_case_path.is_file(),
        "project_offline_publication_audit_complete": offline_publication_audit_path.is_file(),
        "project_publication_manifest_complete": publication_manifest_path.is_file(),
    }


def _selected_runs(
    *,
    runs: list[AutoResearchRunRead],
    meta_analysis: AutoResearchCrossRunMetaAnalysisRead,
) -> list[AutoResearchRunRead]:
    by_id = {run.id: run for run in runs}
    selected = [by_id[run_id] for run_id in meta_analysis.recommended_run_ids if run_id in by_id]
    if selected:
        return selected
    done_with_evidence = [run for run in runs if run.status == "done" and _run_has_evidence(run)]
    if done_with_evidence:
        return done_with_evidence
    return [run for run in runs if run.status == "done"]


def _conclusion(
    *,
    conclusion_id: str,
    kind: str,
    text: str,
    supporting_run_ids: list[str],
    evidence_refs: list[str],
    caveats: list[str] | None = None,
    paper_claim_allowed: bool = False,
) -> AutoResearchProjectConclusionEntryRead:
    return AutoResearchProjectConclusionEntryRead(
        conclusion_id=conclusion_id,
        kind=kind,  # type: ignore[arg-type]
        text=text,
        supporting_run_ids=_dedupe(supporting_run_ids),
        evidence_refs=_dedupe(evidence_refs),
        caveats=_dedupe(caveats or []),
        paper_claim_allowed=paper_claim_allowed,
    )


def _claim_entries(run: AutoResearchRunRead) -> list[AutoResearchClaimEvidenceEntryRead]:
    if run.claim_evidence_matrix is None:
        return []
    return run.claim_evidence_matrix.entries


def _retrieval_ledger_entries(run: AutoResearchRunRead) -> list[AutoResearchEvidenceLedgerEntryRead]:
    if run.evidence_ledger is None:
        return []
    return [
        entry
        for entry in run.evidence_ledger.entries
        if entry.evidence_id.startswith("evidence_retrieval_")
    ]


def _build_conclusion_ledger(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    meta_analysis: AutoResearchCrossRunMetaAnalysisRead,
) -> AutoResearchProjectConclusionLedgerRead:
    runs_by_id = {run.id: run for run in selected_runs}
    stable: list[AutoResearchProjectConclusionEntryRead] = []
    conditional: list[AutoResearchProjectConclusionEntryRead] = []
    negative: list[AutoResearchProjectConclusionEntryRead] = []
    failed: list[AutoResearchProjectConclusionEntryRead] = []
    limitations: list[AutoResearchProjectConclusionEntryRead] = []

    for item in meta_analysis.stable_conclusions:
        evidence_refs: list[str] = []
        for run_id in item.supporting_run_ids:
            run = runs_by_id.get(run_id)
            if run is None:
                continue
            evidence_refs.extend(_claim_evidence_refs(run))
        target = stable if item.stability == "stable" else conditional
        target.append(
            _conclusion(
                conclusion_id=item.conclusion_id,
                kind="stable" if item.stability == "stable" else "conditional",
                text=item.text,
                supporting_run_ids=item.supporting_run_ids,
                evidence_refs=evidence_refs,
                caveats=item.caveats,
                paper_claim_allowed=bool(evidence_refs),
            )
        )

    for run in selected_runs:
        if run.artifact is not None:
            for index, item in enumerate(run.artifact.negative_results, start=1):
                negative.append(
                    _conclusion(
                        conclusion_id=f"negative_{run.id}_{index}",
                        kind="negative",
                        text=(
                            f"{item.subject} did not exceed {item.reference} on {item.metric}: "
                            f"{item.detail}"
                        ),
                        supporting_run_ids=[run.id],
                        evidence_refs=_claim_evidence_refs(run),
                        caveats=["Negative findings are scoped to the executed comparator set."],
                        paper_claim_allowed=_run_has_evidence(run),
                    )
                )
            if run.artifact.failed_trials:
                failed.append(
                    _conclusion(
                        conclusion_id=f"failed_trials_{run.id}",
                        kind="failed_hypothesis",
                        text=f"Run {run.id} contains failed trials that should remain visible in the project paper.",
                        supporting_run_ids=[run.id],
                        evidence_refs=[f"{run.id}:artifact:failed_trials"],
                        caveats=["Failure evidence should be framed as a limitation or replanning signal."],
                        paper_claim_allowed=True,
                    )
                )
        if run.status == "failed":
            failed.append(
                _conclusion(
                    conclusion_id=f"failed_run_{run.id}",
                    kind="failed_hypothesis",
                    text=f"Run {run.id} failed and cannot support positive project-level claims.",
                    supporting_run_ids=[run.id],
                    evidence_refs=_claim_evidence_refs(run),
                    caveats=["Failed runs may support negative or methodological conclusions only."],
                    paper_claim_allowed=False,
                )
            )
        if run.experiment_factory_repair_plan is not None and run.experiment_factory_repair_plan.actions != ["none"]:
            limitations.append(
                _conclusion(
                    conclusion_id=f"factory_repair_{run.id}",
                    kind="limitation",
                    text=(
                        "Experiment factory repair actions remain for "
                        f"{run.id}: {', '.join(run.experiment_factory_repair_plan.actions)}."
                    ),
                    supporting_run_ids=[run.id],
                    evidence_refs=[f"{run.id}:experiment_factory_repair_plan"],
                    caveats=run.experiment_factory_repair_plan.action_reasons,
                    paper_claim_allowed=True,
                )
            )
        for claim in _claim_entries(run):
            if claim.support_status == "unsupported":
                limitations.append(
                    _conclusion(
                        conclusion_id=f"unsupported_claim_{run.id}_{claim.claim_id}",
                        kind="limitation",
                        text=f"Unsupported run-level claim remains unresolved: {claim.claim}",
                        supporting_run_ids=[run.id],
                        evidence_refs=[f"{run.id}:claim_matrix:{claim.claim_id}"],
                        caveats=claim.gaps,
                        paper_claim_allowed=True,
                    )
                )
        retrieval_entries = _retrieval_ledger_entries(run)
        supported_retrieval = [
            entry for entry in retrieval_entries if entry.support_status in {"supported", "partial"}
        ]
        missing_retrieval = [
            entry for entry in retrieval_entries if entry.support_status == "missing"
        ]
        if supported_retrieval:
            status_counts = {
                status: sum(1 for entry in supported_retrieval if entry.support_status == status)
                for status in ("supported", "partial")
            }
            conditional.append(
                _conclusion(
                    conclusion_id=f"claim_evidence_retrieval_{run.id}",
                    kind="conditional",
                    text=(
                        f"Run {run.id} produced claim-evidence retrieval ledger support for "
                        f"{len(supported_retrieval)} manuscript-relevant query claim(s): "
                        f"{status_counts['supported']} supported and {status_counts['partial']} partial."
                    ),
                    supporting_run_ids=[run.id],
                    evidence_refs=[
                        f"{run.id}:evidence_ledger:{entry.evidence_id}"
                        for entry in supported_retrieval[:8]
                    ],
                    caveats=[
                        "Retrieval-ledger conclusions remain run-level evidence unless replicated across independent runs.",
                        "Partial support entries must be framed as limitations or repair targets in the manuscript.",
                    ],
                    paper_claim_allowed=True,
                )
            )
        if missing_retrieval:
            limitations.append(
                _conclusion(
                    conclusion_id=f"missing_claim_evidence_retrieval_{run.id}",
                    kind="limitation",
                    text=(
                        f"Run {run.id} has {len(missing_retrieval)} claim-evidence retrieval ledger "
                        "entry or entries with missing support."
                    ),
                    supporting_run_ids=[run.id],
                    evidence_refs=[
                        f"{run.id}:evidence_ledger:{entry.evidence_id}"
                        for entry in missing_retrieval[:8]
                    ],
                    caveats=[
                        "Missing retrieval evidence must trigger claim downgrade, literature refresh, or experiment repair before promotion.",
                    ],
                    paper_claim_allowed=True,
                )
            )

    if selected_runs and not stable and not conditional:
        for run in selected_runs:
            refs = _claim_evidence_refs(run)
            if not refs:
                continue
            score = run.artifact.objective_score if run.artifact is not None else None
            metric = run.artifact.primary_metric if run.artifact is not None else "primary metric"
            conditional.append(
                _conclusion(
                    conclusion_id=f"conditional_{run.id}",
                    kind="conditional",
                    text=(
                        f"Run {run.id} provides run-level evidence on {metric}"
                        + (f" with objective score {score:.4f}." if isinstance(score, (int, float)) else ".")
                    ),
                    supporting_run_ids=[run.id],
                    evidence_refs=refs,
                    caveats=["Single-run evidence cannot be promoted to a stable project-level result."],
                    paper_claim_allowed=True,
                )
            )

    all_conclusions = stable + conditional + negative + failed + limitations
    payload = {
        "ledger_id": "project_conclusion_ledger_v1",
        "project_id": project_id,
        "stable_conclusions": [item.model_dump(mode="json") for item in stable],
        "conditional_conclusions": [item.model_dump(mode="json") for item in conditional],
        "negative_findings": [item.model_dump(mode="json") for item in negative],
        "failed_hypotheses": [item.model_dump(mode="json") for item in failed],
        "limitations": [item.model_dump(mode="json") for item in limitations],
        "conclusion_count": len(all_conclusions),
    }
    return AutoResearchProjectConclusionLedgerRead(
        ledger_fingerprint=_fingerprint(payload),
        **payload,
    )


def _trace_claims(
    ledger: AutoResearchProjectConclusionLedgerRead,
    *,
    selected_runs: list[AutoResearchRunRead],
) -> list[AutoResearchProjectClaimTraceRead]:
    runs_by_id = {run.id: run for run in selected_runs}
    entries = ledger.stable_conclusions + ledger.conditional_conclusions
    traces: list[AutoResearchProjectClaimTraceRead] = []
    for item in entries:
        strong = item.kind == "stable"
        missing = [
            run_id
            for run_id in item.supporting_run_ids
            if run_id not in runs_by_id or not _run_has_evidence(runs_by_id[run_id])
        ]
        if item.evidence_refs and not missing:
            status = "supported"
        elif item.evidence_refs:
            status = "partial"
        else:
            status = "unsupported"
        reasons = []
        if not item.evidence_refs:
            reasons.append("No run-level evidence refs are attached to the conclusion.")
        if missing:
            reasons.append("Some supporting runs lack artifact, evidence ledger, or claim-ledger evidence.")
        traces.append(
            AutoResearchProjectClaimTraceRead(
                claim_id=f"project_claim_{_slug(item.conclusion_id)}",
                claim=item.text,
                source_conclusion_id=item.conclusion_id,
                support_status=status,  # type: ignore[arg-type]
                supporting_run_ids=item.supporting_run_ids,
                evidence_refs=item.evidence_refs,
                unsupported_reasons=reasons,
                strong_claim=strong,
            )
        )
    return traces


def _reviewer_average(selected_runs: list[AutoResearchRunRead]) -> tuple[int, float]:
    simulations = [run.reviewer_simulation for run in selected_runs if run.reviewer_simulation is not None]
    if not simulations:
        return 0, 0.0
    return len(simulations), round(sum(item.average_score for item in simulations) / len(simulations), 2)


def _decision(
    *,
    selected_runs: list[AutoResearchRunRead],
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    reviewer_average_score: float,
) -> tuple[bool, bool, AutoResearchProjectPaperDecision, AutoResearchProjectPaperSourceStrategy, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not selected_runs:
        blockers.append("No completed run with project evidence is available.")
        return False, False, "do_not_write", "no_paper", blockers, warnings

    unsupported = [trace for trace in traces if trace.support_status == "unsupported"]
    strong_unsupported = [trace for trace in unsupported if trace.strong_claim]
    if strong_unsupported:
        blockers.append("Project-level paper has strong cross-run claims without run-level evidence.")
    if unsupported:
        warnings.append("Some project-level claims remain unsupported and must be downgraded or removed.")

    if len(selected_runs) == 1:
        warnings.append("Only one completed run is available; do not present it as a full project-level paper.")
        return True, False, "technical_report", "single_run_report", blockers, warnings

    stable_supported = [
        item
        for item in ledger.stable_conclusions
        if item.evidence_refs and item.paper_claim_allowed
    ]
    if stable_supported and not blockers:
        if reviewer_average_score >= 7.0:
            return True, True, "conference_candidate", "project_level_paper", blockers, warnings
        return True, True, "workshop_candidate", "project_level_paper", blockers, warnings
    if ledger.conditional_conclusions and not blockers:
        warnings.append("Evidence is cross-run but conditional; keep the manuscript at workshop or technical-report strength.")
        return True, False, "workshop_candidate", "project_level_paper", blockers, warnings

    blockers.append("Selected runs do not yet yield supported stable or conditional project conclusions.")
    return False, False, "do_not_write", "no_paper", blockers, warnings


def build_project_paper_orchestration(project_id: str) -> AutoResearchProjectPaperOrchestrationRead:
    briefs = list_research_briefs(project_id)
    latest_brief: AutoResearchResearchBriefRead | None = briefs[0] if briefs else None
    runs = list_runs(project_id)
    meta = build_cross_run_meta_analysis(project_id)
    selected_runs = _selected_runs(runs=runs, meta_analysis=meta)
    ledger = _build_conclusion_ledger(
        project_id=project_id,
        selected_runs=selected_runs,
        meta_analysis=meta,
    )
    traces = _trace_claims(ledger, selected_runs=selected_runs)
    reviewer_count, reviewer_average = _reviewer_average(selected_runs)
    (
        should_write,
        project_level_allowed,
        paper_decision,
        source_strategy,
        blockers,
        decision_warnings,
    ) = _decision(
        selected_runs=selected_runs,
        ledger=ledger,
        traces=traces,
        reviewer_average_score=reviewer_average,
    )
    warnings = _dedupe(meta.warnings + decision_warnings)
    if meta.blockers and len(selected_runs) < 2:
        warnings.extend(meta.blockers)
    supported = [trace for trace in traces if trace.support_status == "supported"]
    unsupported = [trace for trace in traces if trace.support_status == "unsupported"]
    next_actions = []
    if not project_level_allowed and len(selected_runs) < 2:
        next_actions.append("Run at least one additional selected hypothesis before claiming a project-level paper.")
    if unsupported:
        next_actions.append("Downgrade or remove unsupported project-level claims.")
    if not any(run.reviewer_simulation is not None for run in selected_runs):
        next_actions.append("Run reviewer simulation before project-level submission packaging.")
    if not blockers and should_write:
        next_actions.append("Draft project-level paper sections from the conclusion ledger.")
    effective_should_write = should_write and not blockers
    effective_project_level_allowed = project_level_allowed and not blockers
    effective_paper_decision: AutoResearchProjectPaperDecision = (
        "do_not_write" if blockers and not should_write else paper_decision
    )
    project_paper_markdown = _render_project_paper_markdown(
        project_id=project_id,
        latest_brief=latest_brief,
        selected_runs=selected_runs,
        ledger=ledger,
        traces=traces,
        paper_decision=effective_paper_decision,
        source_strategy=source_strategy,
        should_write_paper=effective_should_write,
        project_level_paper_allowed=effective_project_level_allowed,
        blockers=_dedupe(blockers),
        warnings=_dedupe(warnings),
        next_actions=_dedupe(next_actions),
        reviewer_count=reviewer_count,
        reviewer_average_score=reviewer_average,
    )
    evidence_profile_for_revision = _project_publication_evidence_profile(
        selected_runs=selected_runs,
        latest_brief=latest_brief,
    )
    statistics_profiles_for_revision = [_run_statistics_profile(run) for run in selected_runs]
    project_paper_revision_actions_initial_raw = _build_project_revision_actions(
        ledger=ledger,
        traces=traces,
        evidence_profile=evidence_profile_for_revision,
        statistics_profiles=statistics_profiles_for_revision,
    )
    project_review_findings = _project_review_findings_payload(
        project_id=project_id,
        actions=project_paper_revision_actions_initial_raw,
        ledger=ledger,
        traces=traces,
        evidence_profile=evidence_profile_for_revision,
        statistics_profiles=statistics_profiles_for_revision,
        selected_runs=selected_runs,
    )
    project_paper_revision_actions_initial = _attach_project_review_finding_ids(
        project_paper_revision_actions_initial_raw,
        project_review_findings,
    )
    (
        project_paper_markdown,
        project_paper_revision_actions,
        project_revision_application_report,
        project_revision_rereview_report,
    ) = _apply_project_revision_actions(
        project_id=project_id,
        markdown=project_paper_markdown,
        actions=project_paper_revision_actions_initial,
        selected_runs=selected_runs,
        latest_brief=latest_brief,
        traces=traces,
        evidence_profile=evidence_profile_for_revision,
        statistics_profiles=statistics_profiles_for_revision,
    )
    project_paper_path = _project_paper_path(project_id)
    project_paper_path.write_text(project_paper_markdown, encoding="utf-8")
    project_paper_sections, project_paper_missing_sections = _project_paper_section_status(project_paper_markdown)
    project_paper_revision_action_index = _build_project_revision_action_index(
        project_paper_revision_actions,
        markdown=project_paper_markdown,
    )
    (
        project_paper_sources_dir,
        project_paper_sources_manifest,
        project_paper_compile_report,
        project_paper_latex_source,
        project_paper_bibliography_bib,
    ) = _materialize_project_paper_sources(
        project_id=project_id,
        markdown=project_paper_markdown,
        revised_markdown=project_paper_markdown,
        latest_brief=latest_brief,
        revision_action_index=project_paper_revision_action_index,
        review_findings=project_review_findings,
        revision_application_report=project_revision_application_report,
        revision_rereview_report=project_revision_rereview_report,
    )
    effective_project_publish_gate_passed = effective_project_level_allowed and not unsupported
    project_submission_updates = _materialize_project_submission_package(
        project_id=project_id,
        selected_runs=selected_runs,
        latest_brief=latest_brief,
        ledger=ledger,
        traces=traces,
        project_paper_path=project_paper_path,
        project_paper_sources_dir=project_paper_sources_dir,
        project_paper_revised_path=project_paper_sources_dir / PROJECT_PAPER_REVISED_FILENAME,
        project_revision_application_path=project_paper_sources_dir / PROJECT_PAPER_REVISION_APPLICATION_FILENAME,
        project_revision_rereview_path=project_paper_sources_dir / PROJECT_PAPER_REREVIEW_REPORT_FILENAME,
        project_paper_sections=project_paper_sections,
        project_paper_missing_sections=project_paper_missing_sections,
        project_paper_compile_report=project_paper_compile_report,
        project_paper_revision_actions=project_paper_revision_actions,
        project_review_findings=project_review_findings,
        project_publish_gate_passed=effective_project_publish_gate_passed,
        blockers=_dedupe(blockers),
        warnings=_dedupe(warnings),
    )

    payload = {
        "orchestrator_id": "project_paper_orchestrator_v1",
        "project_id": project_id,
        "brief_count": len(briefs),
        "latest_brief_id": latest_brief.brief_id if latest_brief is not None else None,
        "latest_brief_selected_hypothesis_id": (
            latest_brief.selected_hypothesis_id if latest_brief is not None else None
        ),
        "candidate_run_count": len([run for run in runs if run.status == "done"]),
        "selected_run_ids": [run.id for run in selected_runs],
        "selected_run_count": len(selected_runs),
        "meta_analysis": meta.model_dump(mode="json"),
        "conclusion_ledger": ledger.model_dump(mode="json"),
        "claim_traces": [trace.model_dump(mode="json") for trace in traces],
        "core_claim_count": len(traces),
        "supported_core_claim_count": len(supported),
        "unsupported_core_claim_count": len(unsupported),
        "reviewer_simulation_count": reviewer_count,
        "reviewer_average_score": reviewer_average,
        "should_write_paper": effective_should_write,
        "project_level_paper_allowed": effective_project_level_allowed,
        "paper_decision": effective_paper_decision,
        "paper_tier": _paper_tier_from_decision(effective_paper_decision),
        "source_strategy": source_strategy,
        "project_publish_gate_passed": effective_project_publish_gate_passed,
        "project_paper_path": str(project_paper_path),
        "project_paper_markdown": project_paper_markdown,
        "project_paper_sections": project_paper_sections,
        "project_paper_missing_sections": project_paper_missing_sections,
        "project_paper_ready": effective_should_write and not project_paper_missing_sections,
        "project_paper_sources_dir": str(project_paper_sources_dir),
        "project_paper_sources_manifest": project_paper_sources_manifest.model_dump(mode="json"),
        "project_paper_sources_manifest_path": str(project_paper_sources_dir / PROJECT_PAPER_MANIFEST_FILENAME),
        "project_paper_compile_report": project_paper_compile_report.model_dump(mode="json"),
        "project_paper_compile_report_path": str(project_paper_sources_dir / PROJECT_PAPER_COMPILE_REPORT_FILENAME),
        "project_paper_latex_path": str(project_paper_sources_dir / PROJECT_PAPER_LATEX_FILENAME),
        "project_paper_bibliography_path": str(project_paper_sources_dir / PROJECT_PAPER_BIB_FILENAME),
        "project_paper_build_script_path": str(project_paper_sources_dir / PROJECT_PAPER_BUILD_SCRIPT_FILENAME),
        "project_paper_latex_source": project_paper_latex_source,
        "project_paper_bibliography_bib": project_paper_bibliography_bib,
        "project_paper_revision_actions": [
            item.model_dump(mode="json") for item in project_paper_revision_actions
        ],
        "project_review_findings": project_review_findings,
        "project_paper_revision_action_count": len(project_paper_revision_actions),
        "project_paper_revision_pending_action_count": sum(
            1 for item in project_paper_revision_actions if item.status != "completed"
        ),
        "project_paper_revision_completed_action_count": sum(
            1 for item in project_paper_revision_actions if item.status == "completed"
        ),
        "project_paper_claim_downgrade_action_count": sum(
            1 for item in project_paper_revision_actions if item.action_kind == "claim_downgrade"
        ),
        "project_paper_retrieval_repair_action_count": sum(
            1
            for item in project_paper_revision_actions
            if item.repair_kind == "repair_claim_evidence"
            and any("retrieval" in issue_id for issue_id in item.issue_ids)
        ),
        "project_paper_revision_action_index": project_paper_revision_action_index.model_dump(mode="json"),
        "project_paper_revision_action_index_path": str(
            project_paper_sources_dir / PROJECT_PAPER_REVISION_ACTION_INDEX_FILENAME
        ),
        "project_paper_revision_actions_markdown_path": str(
            project_paper_sources_dir / PROJECT_PAPER_REVISION_ACTION_NOTE_FILENAME
        ),
        "project_paper_revised_path": str(project_paper_sources_dir / PROJECT_PAPER_REVISED_FILENAME),
        "project_paper_revision_application_path": str(
            project_paper_sources_dir / PROJECT_PAPER_REVISION_APPLICATION_FILENAME
        ),
        "project_paper_rereview_report_path": str(
            project_paper_sources_dir / PROJECT_PAPER_REREVIEW_REPORT_FILENAME
        ),
        "project_paper_revision_application": project_revision_application_report,
        "project_paper_rereview_report": project_revision_rereview_report,
        "project_paper_rereview_complete": bool(
            project_revision_rereview_report.get("rereview_complete")
        ),
        **project_submission_updates,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "next_actions": _dedupe(next_actions),
    }
    return AutoResearchProjectPaperOrchestrationRead(
        generated_at=_utcnow(),
        orchestration_fingerprint=_fingerprint(payload),
        **payload,
    )
