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
from services.autoresearch.benchmarks import ResolvedBenchmark, build_experiment_spec
from services.autoresearch.experiment_factory import (
    build_experiment_factory_plan,
    execute_cached_claim_evidence_experiment_factory,
    execute_toy_experiment_factory,
)
from services.autoresearch.idea_brief import build_research_brief, selected_hypothesis_from_brief
from services.autoresearch.literature_scout import (
    literature_insights_from_scout,
    scout_and_mine_gaps,
)
from services.autoresearch.project_paper_orchestrator import build_project_paper_orchestration
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

_OFFLINE_PUBLICATION_CASE_REQUIRED_PACKAGE_ROLES = {
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
    "project_benchmark_card",
    "project_benchmark_provenance_manifest",
    "project_benchmark_provenance_repair_index",
    "project_statistics_report",
    "project_experiment_repair_index",
    "project_negative_evidence_report",
    "project_offline_publication_case",
    "project_offline_publication_audit",
    "project_code_package",
    "project_publication_manifest",
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


def _seed_claim_evidence_cached_literature(brief) -> None:
    payloads = {
        "arxiv": _CACHED_REAL_ARXIV_PAYLOAD,
        "semantic_scholar": _CACHED_REAL_LITERATURE_PAYLOAD,
        "crossref": _CACHED_REAL_CROSSREF_PAYLOAD,
    }
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


def _build_case_trace(project_id: str, case: dict[str, Any]) -> AutoResearchEvaluationCaseTraceRead:
    brief = build_research_brief(
        project_id=project_id,
        payload=_payload_for_case(case),
    )
    if str(case["task_kind"]) == "claim_evidence_vertical_task":
        _seed_claim_evidence_cached_literature(brief)
    scouted = scout_and_mine_gaps(brief)
    save_research_brief(scouted)
    hypothesis = selected_hypothesis_from_brief(scouted)
    plan = build_experiment_factory_plan(
        project_id=project_id,
        brief=scouted,
        hypothesis=hypothesis,
    )
    if str(case["task_kind"]) == "claim_evidence_vertical_task":
        execution = execute_cached_claim_evidence_experiment_factory(
            plan,
            benchmark_payload=_CACHED_SCIFACT_VERTICAL_PAYLOAD,
            executor_mode="local",
        )
        execution_step = "cached_benchmark_execution"
    else:
        execution = execute_toy_experiment_factory(plan)
        execution_step = "toy_execution"

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
        benchmark = ResolvedBenchmark(
            source=_CACHED_SCIFACT_VERTICAL_SOURCE,
            task_family="ir_reranking",
            payload=_CACHED_SCIFACT_VERTICAL_PAYLOAD,
            benchmark_name=str(_CACHED_SCIFACT_VERTICAL_PAYLOAD["name"]),
            benchmark_description=str(_CACHED_SCIFACT_VERTICAL_PAYLOAD["description"]),
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
            benchmark=_CACHED_SCIFACT_VERTICAL_SOURCE,
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
        beir_execution = execute_cached_claim_evidence_experiment_factory(
            plan,
            benchmark_payload=_CACHED_BEIR_VERTICAL_PAYLOAD,
            executor_mode="local",
        )
        project_negative_evidence_count += _artifact_negative_evidence_count(beir_execution.result_artifact)
        beir_benchmark = ResolvedBenchmark(
            source=_CACHED_BEIR_VERTICAL_SOURCE,
            task_family="ir_reranking",
            payload=_CACHED_BEIR_VERTICAL_PAYLOAD,
            benchmark_name=str(_CACHED_BEIR_VERTICAL_PAYLOAD["name"]),
            benchmark_description=str(_CACHED_BEIR_VERTICAL_PAYLOAD["description"]),
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
                "Second cached benchmark-ladder run for BEIR-style retrieval-only validation; "
                "kept separate from SciFact-style verification evidence."
            ),
            task_family="ir_reranking",
            benchmark=_CACHED_BEIR_VERTICAL_SOURCE,
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
                f"{case['task_kind']}: benchmark ladder includes SciFact-style verification run "
                f"`{run.id}` and BEIR-style retrieval run `{beir_run.id}`."
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
        if project_submission_blockers:
            failure_analysis_materials.append(
                (
                    f"{case['task_kind']}: project submission blockers preserve publication honesty: "
                    + "; ".join(project_submission_blockers[:3])
                )
            )
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
        literature_cache_hit_count=(
            literature_scout.cache_hit_count if literature_scout is not None else 0
        ),
        real_literature_count=len(real_literature),
        literature_source_counts=(
            dict(literature_scout.source_counts) if literature_scout is not None else {}
        ),
        literature_network_enabled=(
            literature_scout.network_enabled if literature_scout is not None else False
        ),
        evidence_complete=execution.evidence_ledger.complete,
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
        project_review_bundle_ready=project_review_bundle_ready,
        project_final_publish_ready=project_final_publish_ready,
        project_revision_action_count=project_revision_action_count,
        project_review_finding_count=project_review_finding_count,
        project_review_findings_mapped_to_actions=project_review_findings_mapped_to_actions,
        project_submission_blockers=project_submission_blockers,
        project_submission_bundle_kind=project_submission_bundle_kind,
        project_submission_asset_roles=project_submission_asset_roles,
        project_submission_missing_asset_roles=project_submission_missing_asset_roles,
        project_submission_required_roles_present=project_submission_required_roles_present,
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
        _metric(
            metric_id="offline_end_to_end_submission_package",
            label="Offline End-to-End Submission Package",
            numerator=sum(1 for trace in claim_vertical_traces if trace.end_to_end_package_ready),
            denominator=max(len(claim_vertical_traces), 1),
            rationale="Counts traces that run idea-to-brief, cached benchmark execution, evidence ledger, project paper, revision actions, and project submission package without live services.",
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
