from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import services.autoresearch.orchestrator as autoresearch_orchestrator
import services.autoresearch.console as autoresearch_console
import services.autoresearch.artifact_integrity_audit as artifact_integrity_audit
import services.autoresearch.bridge as autoresearch_bridge
import services.autoresearch.evaluation_cases as autoresearch_evaluation_cases
import services.autoresearch.experiment_factory as autoresearch_experiment_factory
import services.autoresearch.idea_brief as autoresearch_idea_brief
import services.autoresearch.ingestion as autoresearch_ingestion
import services.autoresearch.literature_connectors as autoresearch_literature_connectors
import services.autoresearch.literature_scout as autoresearch_literature_scout
import services.autoresearch.narrative_analyst as narrative_analyst
import services.autoresearch.planner as autoresearch_planner
import services.autoresearch.project_paper_orchestrator as autoresearch_project_paper_orchestrator
import services.autoresearch.publication_repair_execution as publication_repair_execution
import services.autoresearch.repository as autoresearch_repository
import services.autoresearch.review_publish as review_publish
import services.autoresearch.writer as autoresearch_writer
import services.papers.repository as papers_repository
import services.llm.client as llm_client
from config.settings import settings
from models.base import Base
from models.project import Project
from schemas.autoresearch import (
    AblationSpec,
    AggregateSystemMetricResult,
    AutoResearchClaimEvidenceEntryRead,
    AutoResearchClaimEvidenceMatrixRead,
    AutoResearchClaimEvidenceRefRead,
    AutoResearchEvidenceLedgerEntryRead,
    AutoResearchEvidenceLedgerRead,
    AutoResearchExperimentBridgeConfig,
    AutoResearchExperimentFactoryMaterializedJobRead,
    AutoResearchLineageEdgeRead,
    AutoResearchNoveltyAssessmentRead,
    AutoResearchOperatorConsoleFiltersRead,
    AutoResearchPaperCompileReportRead,
    AutoResearchPaperPlanRead,
    AutoResearchPaperPlanSectionRead,
    AutoResearchArtifactIntegrityAuditRead,
    AutoResearchArtifactIntegrityIssueRead,
    AutoResearchIdeaRequest,
    AutoResearchLiteratureScoutPaperRead,
    AutoResearchPublicationEvidenceIndexRead,
    AutoResearchPublicationRepairExecutionActionRead,
    AutoResearchPublicationRepairExecutionRead,
    AutoResearchPublicationRepairActionRead,
    AutoResearchPublicationRepairPlanRead,
    AutoResearchProjectClaimTraceRead,
    AutoResearchProjectConclusionEntryRead,
    AutoResearchProjectConclusionLedgerRead,
    AutoResearchPublishPackageRead,
    AutoResearchRegistryAssetRef,
    AutoResearchRunConfig,
    AutoResearchRunExecutionRead,
    AutoResearchRunLineageRead,
    AutoResearchRunRead,
    AutoResearchRunRegistryFiles,
    AutoResearchRunRegistryRead,
    BaselineSpec,
    BenchmarkSource,
    ExecutionBackendSpec,
    ExperimentAttempt,
    ExperimentSpec,
    HypothesisCandidate,
    LiteratureInsight,
    LiteratureSynthesis,
    LiteratureTheme,
    PortfolioSummary,
    ResearchPlan,
    ResearchProgram,
    ResultArtifact,
    ResultTable,
    SignificanceTestResult,
    SystemMetricResult,
)
from schemas.papers import PaperMeta
from services.autoresearch.benchmarks import ResolvedBenchmark, build_experiment_spec, builtin_benchmark
from services.autoresearch.benchmark_card import build_benchmark_card
from services.autoresearch.codegen import ExperimentCodeGenerator
from services.autoresearch.contribution_assessment import build_contribution_assessment
from services.autoresearch.experiment_design import build_experiment_design
from services.autoresearch.failure_replanning import build_failure_analysis, build_research_replan
from services.autoresearch.literature_novelty import build_literature_graph, build_novelty_validation
from services.autoresearch.paper_evidence_compiler import compile_paper_evidence
from services.autoresearch.methodology_audit import build_methodology_audit
from services.autoresearch.publication_repair_execution import build_publication_repair_execution
from services.autoresearch.research_protocol import build_research_protocol
from services.autoresearch.runner import AutoExperimentRunner
from services.autoresearch.research_readiness import (
    PUBLICATION_MIN_COMPLETED_SEEDS,
    build_publication_readiness,
    enforce_publication_protocol,
)
from services.autoresearch.writer import PaperWriter


def test_llm_chat_hard_timeout_returns_fallback(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    monkeypatch.delenv("SCHOLARFLOW_OFFLINE_LLM", raising=False)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("LLM_HARD_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_api_base", "https://example.invalid")
    monkeypatch.setattr(llm_client, "record_usage_event", lambda **kwargs: recorded.update(kwargs))

    def slow_completion(**kwargs):
        time.sleep(5)
        return {"choices": [{"message": {"role": "assistant", "content": "late"}}]}

    monkeypatch.setattr(llm_client, "litellm_completion", slow_completion)

    started = time.perf_counter()
    response = llm_client.chat([{"role": "user", "content": "hello"}], model="test-model")
    elapsed = time.perf_counter() - started

    assert response == llm_client.FALLBACK_RESPONSE
    assert elapsed < 2
    assert recorded["model"] == "test-model"
    assert recorded["completion_tokens"] == 0


def test_planner_repairs_structured_string_lists(monkeypatch) -> None:
    payload = {
        "title": "Evidence-Constrained Retrieval Planning",
        "problem_statement": {"summary": "Autonomous review agents need grounded retrieval decisions."},
        "motivation": "Reduce unsupported literature claims.",
        "proposed_method": {"method": "claim-evidence reranking", "rationale": "prefer cited support"},
        "research_questions": [
            {"question": "Does evidence-aware scoring improve retrieval quality?"},
        ],
        "hypotheses": [
            {
                "hypothesis": "Evidence-aware reranking improves MRR over overlap baselines.",
                "rationale": "claim support filters distractors",
            }
        ],
        "planned_contributions": [
            {"contribution": "A deterministic evidence-constrained reranking benchmark."}
        ],
        "experiment_outline": [{"description": "Compare overlap, IDF, and evidence-aware variants."}],
        "scope_limits": [{"description": "Use local benchmark fixtures only."}],
        "literature_gaps_addressed": [{"gap": "limited evidence-ledger evaluation"}],
        "novelty_statement": {"claim": "The novelty is bounded to evidence-aware orchestration."},
        "contribution_statements": [{"statement": "All claims remain tied to executable artifacts."}],
    }

    monkeypatch.setattr(
        autoresearch_planner,
        "chat",
        lambda *args, **kwargs: {"choices": [{"message": {"content": json.dumps(payload)}}]},
    )

    plan = autoresearch_planner.ResearchPlanner().plan(
        "evidence aware retrieval",
        task_family_hint="ir_reranking",
    )

    assert plan.title == "Evidence-Constrained Retrieval Planning"
    assert plan.problem_statement == "Autonomous review agents need grounded retrieval decisions."
    assert plan.proposed_method == "claim-evidence reranking; prefer cited support"
    assert plan.hypotheses == [
        "Evidence-aware reranking improves MRR over overlap baselines.; claim support filters distractors"
    ]
    assert all(isinstance(item, str) for item in plan.planned_contributions)


def _session_local(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "regressions.sqlite3"
    data_dir = tmp_path / "data"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings, "data_dir", data_dir)
    return testing_session_local


def _seed_project(db, project_id: str, *, title: str = "Regression Project") -> None:
    db.add(
        Project(
            id=project_id,
            title=title,
            topic="Regression topic",
            template_id="builtin:general_paper",
            status="init",
        )
    )
    db.commit()


def _idea_request_payload() -> dict[str, object]:
    return {
        "idea": "Improve evidence-aware reranking for autonomous literature review",
        "domain": "scientific document retrieval",
        "resource_budget": {
            "budget_label": "standard",
            "max_rounds": 2,
            "candidate_execution_limit": 2,
            "max_literature_queries": 3,
        },
        "target_tier": "workshop_candidate",
        "allow_web": False,
        "allow_experiments": True,
        "task_family_hint": "ir_reranking",
        "execution_profile": "exploratory",
    }


def _claim_evidence_runner_plan(spec: ExperimentSpec) -> ResearchPlan:
    return ResearchPlan(
        topic="claim evidence retrieval",
        title="Frozen Claim Evidence Retrieval",
        task_family="ir_reranking",
        problem_statement="Evaluate claim-evidence retrieval under structured near-miss distractors.",
        motivation="Autonomous paper writers need retrieval evidence that does not overfit lexical overlap.",
        proposed_method="Use rarity-aware and bigram lexical reranking as a deterministic candidate method.",
        research_questions=["Does bigram reranking improve MRR on claim-evidence retrieval?"],
        hypotheses=[spec.hypothesis],
        planned_contributions=["A deterministic claim-evidence reranking execution trace."],
        experiment_outline=["Run the frozen claim-evidence benchmark with lexical baselines."],
    )


def test_claim_evidence_ir_routes_to_frozen_non_publication_fixture() -> None:
    benchmark = builtin_benchmark(
        "ir_reranking",
        topic="claim evidence retrieval unsupported claims citation grounded scientific writing agents",
    )
    spec = build_experiment_spec("ir_reranking", benchmark)

    assert benchmark.benchmark_name == "frozen_claim_evidence_reranking"
    assert benchmark.source.kind == "builtin"
    assert benchmark.source.url == "local://scholarflow/fixtures/frozen_claim_evidence_reranking/v1"
    assert benchmark.source.dataset_id == "scholarflow:frozen_claim_evidence_reranking"
    assert benchmark.source.revision == "v1.0.0"
    assert benchmark.source.license == "synthetic-fixture"
    assert spec.dataset.name == "Frozen Claim Evidence Reranking"
    assert spec.dataset.train_size == 12
    assert spec.dataset.test_size == 12
    assert spec.dataset.candidate_count == 5
    assert spec.dataset.source_kind == "builtin"
    assert spec.dataset.publication_grade is False
    assert [metric.name for metric in spec.metrics] == [
        "mrr",
        "recall_at_1",
        "ndcg_at_10",
        "recall_at_10",
        "evidence_coverage",
        "verification_accuracy",
        "unsupported_claim_precision",
        "unsupported_claim_recall",
        "abstention_accuracy",
    ]
    assert spec.search_strategies[-1] == "ledger_aware_reranker_search"
    assert spec.sweeps[0].params["ledger_weight"] == 1.0


def test_frozen_claim_evidence_ir_runner_executes_non_degenerate_fixture(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    benchmark = builtin_benchmark(
        "ir_reranking",
        topic="claim evidence retrieval unsupported claims citation grounded scientific writing agents",
    )
    spec = build_experiment_spec("ir_reranking", benchmark)
    plan = _claim_evidence_runner_plan(spec)
    code = ExperimentCodeGenerator()._ir_template(
        plan,
        spec,
        benchmark.payload,
        "bigram_reranker_search",
    )

    _, _, artifact = AutoExperimentRunner().run(
        project_id="project-frozen-claim-evidence",
        run_id="run-frozen-claim-evidence",
        plan=plan,
        spec=spec,
        benchmark_payload=benchmark.payload,
        round_index=3,
        goal="evaluate frozen claim-evidence fixture",
        prior_attempts=[],
        execution_backend=ExecutionBackendSpec(kind="local", timeout_seconds=30),
        code_override=code,
        strategy_override="bigram_reranker_search",
    )

    scores = {
        item.system: item.mean_metrics[artifact.primary_metric]
        for item in artifact.aggregate_system_results
    }
    assert artifact.status == "done"
    assert artifact.primary_metric == "mrr"
    assert artifact.objective_system == "bigram_ranker"
    assert artifact.best_system == "bigram_ranker"
    assert scores["random_ranker"] < scores["overlap_ranker"] < scores["bigram_ranker"]
    assert scores["bigram_ranker"] < 1.0
    assert artifact.objective_score == scores["bigram_ranker"]
    bigram_metrics = next(
        item.mean_metrics
        for item in artifact.aggregate_system_results
        if item.system == "bigram_ranker"
    )
    assert set(bigram_metrics) >= {
        "mrr",
        "recall_at_1",
        "ndcg_at_10",
        "recall_at_10",
        "evidence_coverage",
    }
    assert 0.0 < bigram_metrics["ndcg_at_10"] <= 1.0
    assert bigram_metrics["recall_at_10"] == 1.0
    assert bigram_metrics["evidence_coverage"] == 1.0
    main_table = next(table for table in artifact.tables if table.title == "Main Results")
    assert main_table.columns == [
        "System",
        "MRR",
        "Recall@1",
        "nDCG@10",
        "Recall@10",
        "Evidence Coverage",
    ]
    assert artifact.outputs["objective_query_diagnostics"]
    assert artifact.outputs["objective_failure_cases"]
    assert {"query", "ranked_ids_at_10", "failure_modes", "ndcg_at_10"} <= set(
        artifact.outputs["objective_query_diagnostics"][0]
    )
    assert len(artifact.per_seed_results) == len(spec.seeds)
    assert artifact.significance_tests
    assert all(check.passed for check in artifact.acceptance_checks)
    assert artifact.environment["benchmark_name"] == "Frozen Claim Evidence Reranking"


def test_ledger_aware_claim_evidence_ranker_beats_bigram_fixture(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    benchmark = builtin_benchmark(
        "ir_reranking",
        topic="claim evidence retrieval unsupported claims citation grounded scientific writing agents",
    )
    spec = build_experiment_spec("ir_reranking", benchmark)
    plan = _claim_evidence_runner_plan(spec)
    code = ExperimentCodeGenerator()._ir_template(
        plan,
        spec,
        benchmark.payload,
        "ledger_aware_reranker_search",
    )

    _, _, artifact = AutoExperimentRunner().run(
        project_id="project-ledger-aware-claim-evidence",
        run_id="run-ledger-aware-claim-evidence",
        plan=plan,
        spec=spec,
        benchmark_payload=benchmark.payload,
        round_index=4,
        goal="evaluate ledger-aware claim-evidence retrieval",
        prior_attempts=[],
        execution_backend=ExecutionBackendSpec(kind="local", timeout_seconds=30),
        code_override=code,
        strategy_override="ledger_aware_reranker_search",
    )

    scores = {
        item.system: item.mean_metrics[artifact.primary_metric]
        for item in artifact.aggregate_system_results
    }
    ndcg = {
        item.system: item.mean_metrics["ndcg_at_10"]
        for item in artifact.aggregate_system_results
    }
    assert artifact.status == "done"
    assert artifact.best_system == "ledger_aware_ranker"
    assert artifact.objective_system == "ledger_aware_ranker"
    assert scores["ledger_aware_ranker"] > scores["bigram_ranker"] > scores["overlap_ranker"]
    assert ndcg["ledger_aware_ranker"] > ndcg["bigram_ranker"]
    assert artifact.outputs["objective_failure_cases"]
    assert all("top_rank_not_relevant" in item["failure_modes"] for item in artifact.outputs["objective_failure_cases"])
    repair_actions = artifact.outputs["review_loop_repair_actions"]
    assert len(repair_actions) == 1
    assert repair_actions[0]["action_kind"] == "claim_downgrade"
    assert repair_actions[0]["repair_kind"] == "repair_claim_evidence"
    assert repair_actions[0]["execution_route"] == "paper_rebuild"
    assert repair_actions[0]["requires_rereview"] is True
    assert "run_claim_evidence_matrix_json" in repair_actions[0]["expected_output_asset_ids"]
    assert artifact.outputs["review_loop_repair_summary"] == {"claim_downgrade": 1}
    assert any("bounded review-loop repair actions" in item for item in artifact.key_findings)
    vertical_package = artifact.outputs["claim_evidence_vertical_package"]
    assert vertical_package["paper_tier"] == "workshop_case_study"
    assert vertical_package["benchmark_scope"] == "synthetic_fixture"
    assert vertical_package["objective_system"] == "ledger_aware_ranker"
    assert vertical_package["open_repair_case_count"] == len(artifact.outputs["objective_failure_cases"])
    assert any(item["claim_id"] == "claim_repair_routing" for item in vertical_package["claim_evidence_index"])
    retrieval_ledger = vertical_package["retrieval_evidence_ledger"]
    assert retrieval_ledger["ledger_id"] == "claim_evidence_retrieval_ledger_v1"
    assert retrieval_ledger["entry_count"] == 12
    assert retrieval_ledger["partial_entry_count"] >= 1
    assert retrieval_ledger["repair_action_count"] == 1
    assert retrieval_ledger["complete"] is False
    repaired_entries = [
        item for item in retrieval_ledger["entries"] if item["repair_action_ids"]
    ]
    assert repaired_entries[0]["repair_action_ids"] == [repair_actions[0]["action_id"]]
    assert repaired_entries[0]["support_status"] == "partial"
    assert any(section["section"] == "limitations" for section in vertical_package["sections"])
    assert "review-loop repair actions" in vertical_package["reproducibility_assets"]
    assert vertical_package["reviewer_response_plan"][0]["action_kind"] == "claim_downgrade"
    assert any("workshop-style claim-evidence vertical package" in item for item in artifact.key_findings)


def test_scifact_json_adapter_normalizes_claim_evidence_fixture(
    monkeypatch,
    tmp_path: Path,
) -> None:
    payload = {
        "name": "SciFact Claim Evidence Fixture",
        "description": "Cache-backed SciFact-style claim-evidence retrieval fixture.",
        "corpus": [
            {
                "doc_id": "doc_support_train",
                "title": "Vitamin D and Respiratory Infection",
                "abstract": ["Vitamin D supplementation reduces respiratory infection risk in adults."],
            },
            {
                "doc_id": "doc_neutral_train",
                "title": "Respiratory Survey Design",
                "abstract": ["A survey describes respiratory symptoms without intervention evidence."],
            },
            {
                "doc_id": "doc_support_test",
                "title": "Masks and Aerosol Transmission",
                "abstract": ["Mask wearing reduces aerosol transmission in controlled environments."],
            },
            {
                "doc_id": "doc_distractor_test",
                "title": "Aerosol Measurement Devices",
                "abstract": ["Measurement devices characterize aerosols but do not test mask wearing."],
            },
        ],
        "claims": [
            {
                "id": "claim_train",
                "claim": "Vitamin D supplementation reduces respiratory infection risk.",
                "candidate_doc_ids": ["doc_support_train", "doc_neutral_train"],
                "evidence": {"doc_support_train": [{"label": "SUPPORT"}]},
            },
            {
                "id": "claim_test",
                "claim": "Masks reduce aerosol transmission.",
                "candidate_doc_ids": ["doc_support_test", "doc_distractor_test"],
                "evidence": {"doc_support_test": [{"label": "SUPPORT"}]},
            },
        ],
        "split": {"train": ["claim_train"], "test": ["claim_test"]},
    }
    cache_path = tmp_path / "scifact_fixture.json"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        autoresearch_ingestion,
        "_fetch_remote_text",
        lambda url: pytest.fail(f"SciFact fixture should load from cache, not network: {url}"),
    )

    source = BenchmarkSource(
        kind="scifact_json",
        name="SciFact fixture",
        file_path=str(cache_path),
        dataset_id="allenai/scifact",
        revision="fixture-v1",
        license="cc-by-nc",
    )
    benchmark = autoresearch_ingestion.resolve_benchmark(
        topic="claim evidence retrieval for scientific writing agents",
        task_family_hint="ir_reranking",
        benchmark_source=source,
    )
    spec = build_experiment_spec("ir_reranking", benchmark)

    assert benchmark.benchmark_name == "SciFact Claim Evidence Fixture"
    assert benchmark.source.kind == "scifact_json"
    assert benchmark.payload["train"][0]["query"] == "Vitamin D supplementation reduces respiratory infection risk."
    assert benchmark.payload["test"][0]["relevant_ids"] == ["doc_support_test"]
    assert benchmark.payload["test"][0]["claim_label"] == "supported"
    assert benchmark.payload["test"][0]["evidence_labels"] == {"doc_support_test": "supported"}
    assert benchmark.payload["verification_label_space"] == ["supported"]
    assert benchmark.payload["test"][0]["candidates"][0]["text"].startswith("Masks and Aerosol Transmission")
    assert spec.dataset.source_kind == "scifact_json"
    assert spec.dataset.source_url == f"file://{cache_path.resolve()}"
    assert spec.dataset.source_dataset_id == "allenai/scifact"
    assert spec.dataset.source_revision == "fixture-v1"
    assert spec.dataset.source_license == "cc-by-nc"
    assert spec.dataset.candidate_count == 2
    assert spec.dataset.source_class == "cached_fixture"
    assert spec.dataset.provenance_complete is True
    assert any("fixture" in item.lower() for item in spec.dataset.publication_grade_blockers)
    assert spec.dataset.publication_grade is False


def test_scifact_json_adapter_records_frozen_snapshot_metadata_without_promoting_miniature(
    monkeypatch,
    tmp_path: Path,
) -> None:
    payload = {
        "name": "SciFact Frozen Mini Snapshot",
        "description": "Repository-local SciFact-style snapshot with complete provenance but miniature scale.",
        "corpus": [
            {
                "doc_id": "doc_support_train",
                "title": "Training Support Evidence",
                "abstract": ["Training intervention improves measured outcomes in randomized studies."],
            },
            {
                "doc_id": "doc_nei_train",
                "title": "Training Background Evidence",
                "abstract": ["Background observations do not establish the intervention claim."],
            },
            {
                "doc_id": "doc_refute_test",
                "title": "Test Refutation Evidence",
                "abstract": ["Independent trials found no reduction in the target outcome."],
            },
            {
                "doc_id": "doc_distractor_test",
                "title": "Test Distractor Evidence",
                "abstract": ["A measurement paper describes the target outcome without intervention evidence."],
            },
        ],
        "claims": [
            {
                "id": "claim_train",
                "claim": "The training intervention improves measured outcomes.",
                "candidate_doc_ids": ["doc_support_train", "doc_nei_train"],
                "evidence": {"doc_support_train": [{"label": "SUPPORT"}]},
            },
            {
                "id": "claim_test",
                "claim": "The intervention reduces the target outcome.",
                "candidate_doc_ids": ["doc_refute_test", "doc_distractor_test"],
                "evidence": {"doc_refute_test": [{"label": "REFUTE"}]},
            },
        ],
        "split": {"train": ["claim_train"], "test": ["claim_test"]},
    }
    snapshot_path = tmp_path / "scifact_frozen_mini_snapshot.json"
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        autoresearch_ingestion,
        "_fetch_remote_text",
        lambda url: pytest.fail(f"Frozen SciFact snapshot should load from file, not network: {url}"),
    )

    source = BenchmarkSource(
        kind="scifact_json",
        name="SciFact frozen mini snapshot",
        file_path=str(snapshot_path),
        dataset_id="allenai/scifact-frozen-mini",
        revision="2026-06-01",
        license="cc-by-4.0",
    )
    benchmark = autoresearch_ingestion.resolve_benchmark(
        topic="claim evidence verification for scientific writing agents",
        task_family_hint="ir_reranking",
        benchmark_source=source,
    )
    spec = build_experiment_spec("ir_reranking", benchmark)

    assert spec.dataset.source_class == "frozen_snapshot"
    assert spec.dataset.provenance_complete is True
    assert spec.dataset.sample_count == 2
    assert spec.dataset.split_count == 2
    assert spec.dataset.supports_claim_verification is True
    assert spec.dataset.verification_label_space == ["refuted", "supported"]
    assert spec.dataset.publication_grade is False
    assert "Benchmark has fewer than 20 normalized examples." in spec.dataset.publication_grade_blockers
    assert spec.dataset.publication_grade_eligibility["checks"]["not_internal_fixture"] is True
    assert spec.dataset.publication_grade_eligibility["checks"]["meets_min_examples"] is False


def test_beir_json_adapter_accepts_publication_eligible_frozen_snapshot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    queries = {
        f"q{index}": f"claim evidence retrieval query {index}"
        for index in range(20)
    }
    corpus = {}
    qrels = {}
    for index in range(20):
        relevant_id = f"d{index}_rel"
        distractor_id = f"d{index}_neg"
        corpus[relevant_id] = {
            "title": f"Relevant Evidence {index}",
            "text": f"Relevant evidence document {index} supports claim-evidence retrieval query {index}.",
        }
        corpus[distractor_id] = {
            "title": f"Distractor Evidence {index}",
            "text": f"Distractor document {index} discusses adjacent scientific writing topics.",
        }
        qrels[f"q{index}"] = {relevant_id: 1, distractor_id: 0}
    payload = {
        "name": "BEIR Claim Evidence Frozen Snapshot",
        "description": "Repository-local BEIR-style frozen snapshot with complete provenance and candidate pools.",
        "queries": queries,
        "corpus": corpus,
        "qrels": qrels,
    }
    snapshot_path = tmp_path / "beir_claim_evidence_frozen_snapshot.json"
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        autoresearch_ingestion,
        "_fetch_remote_text",
        lambda url: pytest.fail(f"Frozen BEIR snapshot should load from file, not network: {url}"),
    )

    source = BenchmarkSource(
        kind="beir_json",
        name="BEIR claim evidence frozen snapshot",
        file_path=str(snapshot_path),
        dataset_id="beir/claim-evidence-frozen-snapshot",
        revision="2026-06-01",
        license="cc-by-4.0",
    )
    benchmark = autoresearch_ingestion.resolve_benchmark(
        topic="claim evidence retrieval for scientific writing agents",
        task_family_hint="ir_reranking",
        benchmark_source=source,
    )
    spec = build_experiment_spec("ir_reranking", benchmark)

    assert benchmark.payload["test"]
    assert benchmark.payload["test"][0]["relevant_ids"]
    assert len(benchmark.payload["test"][0]["candidates"]) == 2
    assert spec.dataset.source_class == "frozen_snapshot"
    assert spec.dataset.provenance_complete is True
    assert spec.dataset.sample_count == 20
    assert spec.dataset.split_count == 2
    assert spec.dataset.supports_claim_verification is False
    assert spec.dataset.publication_grade_blockers == []
    assert spec.dataset.publication_grade is True
    assert spec.dataset.publication_grade_eligibility["sample_count"] == 20
    assert spec.dataset.publication_grade_eligibility["checks"]["has_fingerprint"] is True


def test_scifact_verification_fixture_reports_unsupported_claim_metrics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    payload = {
        "name": "SciFact Verification Fixture",
        "description": "Cached support/refute/not-enough-info claim verification fixture.",
        "corpus": [
            {
                "doc_id": "support_train",
                "title": "Training Support Evidence",
                "abstract": ["Training intervention improves measured outcomes in a randomized trial."],
            },
            {
                "doc_id": "refute_train",
                "title": "Training Refutation Evidence",
                "abstract": ["The candidate intervention does not improve measured outcomes."],
            },
            {
                "doc_id": "nei_train",
                "title": "Training Background Evidence",
                "abstract": ["Background notes discuss study design without testing the intervention."],
            },
            {
                "doc_id": "support_test",
                "title": "Omega Inflammation Trial",
                "abstract": ["Omega treatment reduces inflammation in controlled clinical trials."],
            },
            {
                "doc_id": "support_distractor",
                "title": "Inflammation Survey",
                "abstract": ["Surveys describe inflammation symptoms without testing omega treatment."],
            },
            {
                "doc_id": "refute_test",
                "title": "Coffee Sleep Trial",
                "abstract": ["Coffee does not reduce sleep latency and increases wakefulness."],
            },
            {
                "doc_id": "refute_distractor",
                "title": "Sleep Questionnaire",
                "abstract": ["Questionnaires measure sleep latency in observational cohorts."],
            },
            {
                "doc_id": "nei_test",
                "title": "Reading Comfort Study",
                "abstract": ["Cognitive training improves memory and reading comfort in adults."],
            },
            {
                "doc_id": "nei_distractor",
                "title": "Screen Brightness Study",
                "abstract": ["Screen brightness changes user comfort during evening reading."],
            },
        ],
        "claims": [
            {
                "id": "train_support",
                "claim": "Training intervention improves measured outcomes.",
                "candidate_doc_ids": ["support_train", "nei_train"],
                "evidence": {"support_train": [{"label": "SUPPORT"}]},
            },
            {
                "id": "train_refute",
                "claim": "Candidate intervention improves measured outcomes.",
                "candidate_doc_ids": ["refute_train", "support_train"],
                "evidence": {"refute_train": [{"label": "REFUTE"}]},
            },
            {
                "id": "train_nei",
                "claim": "Training intervention cures seasonal allergies.",
                "candidate_doc_ids": ["nei_train", "support_train"],
                "label": "NEI",
                "evidence": {},
            },
            {
                "id": "test_support",
                "claim": "Omega treatment reduces inflammation.",
                "candidate_doc_ids": ["support_test", "support_distractor", "nei_test"],
                "evidence": {"support_test": [{"label": "SUPPORT"}]},
            },
            {
                "id": "test_refute",
                "claim": "Coffee reduces sleep latency.",
                "candidate_doc_ids": ["refute_test", "refute_distractor", "nei_test"],
                "evidence": {"refute_test": [{"label": "REFUTE"}]},
            },
            {
                "id": "test_nei",
                "claim": "Blue light cures migraine.",
                "candidate_doc_ids": ["nei_test", "nei_distractor", "support_distractor"],
                "label": "NEI",
                "evidence": {},
            },
        ],
        "split": {
            "train": ["train_support", "train_refute", "train_nei"],
            "test": ["test_support", "test_refute", "test_nei"],
        },
    }
    cache_path = tmp_path / "scifact_verification_fixture.json"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        autoresearch_ingestion,
        "_fetch_remote_text",
        lambda url: pytest.fail(f"SciFact verification fixture should load from cache, not network: {url}"),
    )

    source = BenchmarkSource(
        kind="scifact_json",
        name="SciFact verification fixture",
        file_path=str(cache_path),
        dataset_id="allenai/scifact",
        revision="verification-fixture-v1",
        license="cc-by-nc",
    )
    benchmark = autoresearch_ingestion.resolve_benchmark(
        topic="claim evidence verification unsupported scientific claims",
        task_family_hint="ir_reranking",
        benchmark_source=source,
    )
    spec = build_experiment_spec("ir_reranking", benchmark)
    plan = _claim_evidence_runner_plan(spec)
    code = ExperimentCodeGenerator()._ir_template(
        plan,
        spec,
        benchmark.payload,
        "ledger_aware_reranker_search",
    )

    _, _, artifact = AutoExperimentRunner().run(
        project_id="project-scifact-verification",
        run_id="run-scifact-verification",
        plan=plan,
        spec=spec,
        benchmark_payload=benchmark.payload,
        round_index=4,
        goal="evaluate cached SciFact verification fixture",
        prior_attempts=[],
        execution_backend=ExecutionBackendSpec(kind="local", timeout_seconds=30),
        code_override=code,
        strategy_override="ledger_aware_reranker_search",
    )

    assert benchmark.payload["verification_label_space"] == ["not_enough_info", "refuted", "supported"]
    assert benchmark.payload["test"][2]["claim_label"] == "not_enough_info"
    assert benchmark.payload["test"][2]["relevant_ids"] == []
    objective_metrics = next(
        item.mean_metrics
        for item in artifact.aggregate_system_results
        if item.system == "ledger_aware_ranker"
    )
    assert artifact.status == "done"
    assert objective_metrics["verification_accuracy"] == 1.0
    assert objective_metrics["unsupported_claim_precision"] == 1.0
    assert objective_metrics["unsupported_claim_recall"] == 1.0
    assert objective_metrics["abstention_accuracy"] == 1.0
    main_table = next(table for table in artifact.tables if table.title == "Main Results")
    assert "Verification Accuracy" in main_table.columns
    assert "Unsupported Recall" in main_table.columns
    vertical_package = artifact.outputs["claim_evidence_vertical_package"]
    assert any(item["claim_id"] == "claim_verification_behavior" for item in vertical_package["claim_evidence_index"])
    verification_entries = vertical_package["retrieval_evidence_ledger"]["entries"]
    assert {item["claim_label"] for item in verification_entries} == {
        "supported",
        "refuted",
        "not_enough_info",
    }
    assert all(item["metrics"]["verification_correct"] == 1.0 for item in verification_entries)


def _result_artifact() -> ResultArtifact:
    return ResultArtifact(
        status="done",
        summary="Checkpointed execution completed with a stable macro F1 result.",
        key_findings=["candidate improved macro F1 over the keyword baseline"],
        primary_metric="macro_f1",
        best_system="candidate_system",
        objective_system="candidate_system",
        objective_score=0.72,
        system_results=[
            {"system": "candidate_system", "metrics": {"accuracy": 0.72, "macro_f1": 0.72}},
            {"system": "keyword_baseline", "metrics": {"accuracy": 0.61, "macro_f1": 0.61}},
        ],
        aggregate_system_results=[
            {
                "system": "candidate_system",
                "mean_metrics": {"accuracy": 0.72, "macro_f1": 0.72},
                "std_metrics": {"accuracy": 0.0, "macro_f1": 0.0},
                "min_metrics": {"accuracy": 0.72, "macro_f1": 0.72},
                "max_metrics": {"accuracy": 0.72, "macro_f1": 0.72},
                "sample_count": 1,
            }
        ],
        acceptance_checks=[
            {
                "criterion": "Record mean and standard deviation for the primary metric.",
                "passed": True,
                "detail": "aggregate statistics are present",
                "rule_id": "aggregate_metric_reporting",
                "rule_kind": "aggregate_metric_reporting",
            }
        ],
        tables=[],
        environment={},
        outputs={},
    )


def _publication_compile_report() -> AutoResearchPaperCompileReportRead:
    return AutoResearchPaperCompileReportRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        entrypoint="main.tex",
        bibliography="references.bib",
        compiler_hint="pdflatex",
        compile_commands=["pdflatex main.tex"],
        required_inputs=["main.tex", "references.bib"],
        missing_required_inputs=[],
        required_source_files=["main.tex", "references.bib"],
        missing_required_source_files=[],
        expected_outputs=["main.pdf"],
        materialized_outputs=[],
        source_package_complete=True,
        all_expected_outputs_materialized=False,
        ready_for_compile=True,
        paper_tier="technical_report",
    )


def _publication_claim_matrix(*, partial: bool = False) -> AutoResearchClaimEvidenceMatrixRead:
    evidence = [
        AutoResearchClaimEvidenceRefRead(
            source_kind="artifact",
            label="Result artifact",
            detail="The selected artifact preserves aggregate metrics and significance tests.",
            locator="artifact.json",
        )
    ]
    entries = [
        AutoResearchClaimEvidenceEntryRead(
            claim_id="claim_supported_result",
            category="result",
            section_hint="Results",
            claim="The candidate outperforms the majority baseline on macro F1.",
            support_status="supported",
            evidence=evidence,
            gaps=[],
        )
    ]
    if partial:
        entries.append(
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_partial_negative",
                category="limitation",
                section_hint="Limitations",
                claim="Negative evidence remains bounded to the executed comparator set.",
                support_status="partial",
                evidence=evidence,
                gaps=["Comparator coverage is intentionally limited."],
            )
        )
    return AutoResearchClaimEvidenceMatrixRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        claim_count=len(entries),
        supported_claim_count=sum(1 for item in entries if item.support_status == "supported"),
        unsupported_claim_count=sum(1 for item in entries if item.support_status != "supported"),
        entries=entries,
    )


def _paper_plan_with_claims() -> AutoResearchPaperPlanRead:
    return AutoResearchPaperPlanRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        title="Publication Readiness Paper",
        narrative_summary="A paper plan with registered claim ids.",
        sections=[
            AutoResearchPaperPlanSectionRead(
                section_id="abstract",
                title="Abstract",
                objective="Summarize the study.",
                claim_ids=["claim_supported_result"],
                evidence_focus=["artifact.summary"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="results",
                title="Results",
                objective="Report the main results.",
                claim_ids=["claim_supported_result"],
                evidence_focus=["artifact.tables", "artifact.significance_tests"],
            ),
            AutoResearchPaperPlanSectionRead(
                section_id="conclusion",
                title="Conclusion",
                objective="Close the paper.",
                claim_ids=["claim_supported_result"],
                evidence_focus=["claim_evidence_matrix"],
            ),
        ],
    )


def _publication_literature() -> list[LiteratureInsight]:
    return [
        LiteratureInsight(
            paper_id="paper_pub_1",
            title="Benchmarking Compact Retrieval Pipelines",
            year=2024,
            source="semantic_scholar",
            insight="Provides real related-work context for compact retrieval benchmarks.",
            method_hint="Compare compact retrieval pipelines with reproducible reranking baselines.",
            gap_hint="Test whether compact reranking benchmarks preserve macro F1 gains across seeds.",
            relevance="Matches the external compact reranking benchmark and macro F1 evaluation.",
        ),
        LiteratureInsight(
            paper_id="paper_pub_2",
            title="Lightweight Lexical Signals for Reranking",
            year=2023,
            source="semantic_scholar",
            insight="Motivates lexical baselines and controlled reranking comparisons.",
            method_hint="Use lightweight lexical reranking signals against conventional baselines.",
            gap_hint="Ablate lexical feature groups to identify which reranking component drives macro F1.",
            relevance="Supports the candidate ablation and seed-stable macro F1 experiment.",
        ),
    ]


def _publication_artifact(*, include_ablation: bool = True, seed_count: int = 5) -> ResultArtifact:
    systems = [
        {"system": "majority", "metrics": {"accuracy": 0.5, "macro_f1": 0.5}},
        {"system": "candidate_system", "metrics": {"accuracy": 0.8, "macro_f1": 0.8}},
    ]
    aggregate = [
        {
            "system": "majority",
            "mean_metrics": {"accuracy": 0.5, "macro_f1": 0.5},
            "std_metrics": {"accuracy": 0.0, "macro_f1": 0.0},
            "confidence_intervals": {
                "macro_f1": {"lower": 0.5, "upper": 0.5, "level": 0.95}
            },
            "min_metrics": {"accuracy": 0.5, "macro_f1": 0.5},
            "max_metrics": {"accuracy": 0.5, "macro_f1": 0.5},
            "sample_count": seed_count,
        },
        {
            "system": "candidate_system",
            "mean_metrics": {"accuracy": 0.8, "macro_f1": 0.8},
            "std_metrics": {"accuracy": 0.01, "macro_f1": 0.01},
            "confidence_intervals": {
                "macro_f1": {"lower": 0.79, "upper": 0.81, "level": 0.95}
            },
            "min_metrics": {"accuracy": 0.79, "macro_f1": 0.79},
            "max_metrics": {"accuracy": 0.81, "macro_f1": 0.81},
            "sample_count": seed_count,
        },
    ]
    if include_ablation:
        systems.append({"system": "candidate_ablation", "metrics": {"accuracy": 0.7, "macro_f1": 0.7}})
        aggregate.append(
            {
                "system": "candidate_ablation",
                "mean_metrics": {"accuracy": 0.7, "macro_f1": 0.7},
                "std_metrics": {"accuracy": 0.01, "macro_f1": 0.01},
                "confidence_intervals": {
                    "macro_f1": {"lower": 0.69, "upper": 0.71, "level": 0.95}
                },
                "min_metrics": {"accuracy": 0.69, "macro_f1": 0.69},
                "max_metrics": {"accuracy": 0.71, "macro_f1": 0.71},
                "sample_count": seed_count,
            }
        )
    return ResultArtifact(
        status="done",
        summary="Publication artifact with multi-seed aggregate metrics.",
        key_findings=["candidate_system improves over majority"],
        primary_metric="macro_f1",
        best_system="candidate_system",
        objective_system="candidate_system",
        objective_score=0.8,
        system_results=systems,
        aggregate_system_results=aggregate,
        per_seed_results=[
            {
                "seed": seed,
                "sweep_label": "default",
                "best_system": "candidate_system",
                "objective_system": "candidate_system",
                "objective_score": 0.8,
                "primary_metric": "macro_f1",
                "system_results": systems,
            }
            for seed in [7, 13, 23, 31, 47][:seed_count]
        ],
        sweep_results=[
            {
                "label": "default",
                "status": "done",
                "best_system": "candidate_system",
                "objective_system": "candidate_system",
                "objective_score_mean": 0.8,
                "objective_score_std": 0.01,
                "aggregate_system_results": aggregate,
                "seed_count": seed_count,
                "successful_seed_count": seed_count,
            },
            {
                "label": "higher_order_lexical",
                "status": "done",
                "best_system": "candidate_system",
                "objective_system": "candidate_system",
                "objective_score_mean": 0.79,
                "objective_score_std": 0.01,
                "aggregate_system_results": aggregate,
                "seed_count": seed_count,
                "successful_seed_count": seed_count,
            },
        ],
        significance_tests=[
            {
                "scope": "system",
                "metric": "macro_f1",
                "candidate": "candidate_system",
                "comparator": "majority",
                "comparison_family": "system:macro_f1",
                "family_size": 1,
                "p_value": 0.0312,
                "adjusted_p_value": 0.0312,
                "adjusted_alpha": 0.05,
                "correction": "holm_bonferroni",
                "effect_size": 0.3,
                "recommended_sample_count": 3,
                "adequately_powered": True,
                "sample_count": seed_count,
                "significant": True,
                "detail": "candidate_system beats majority across paired seeds.",
            }
        ],
        acceptance_checks=[
            {
                "criterion": "Objective system should outperform the majority baseline.",
                "passed": True,
                "detail": "candidate_system mean macro_f1=0.8",
                "rule_id": "objective_primary_metric_beats_baseline",
                "rule_kind": "objective_metric_comparison",
            },
            {
                "criterion": "Selected sweep should complete every requested seed.",
                "passed": seed_count == 5,
                "detail": f"Selected sweep completed {seed_count}/5 requested seeds.",
                "rule_id": "selected_sweep_completes_all_requested_seeds",
                "rule_kind": "seed_coverage",
            },
            {
                "criterion": "Record mean, standard deviation, and confidence intervals for the primary metric.",
                "passed": True,
                "detail": "macro_f1 mean, std, and 95% confidence interval are recorded.",
                "rule_id": "primary_metric_reports_mean_std_and_ci",
                "rule_kind": "aggregate_metric_reporting",
            },
            {
                "criterion": "Report significance for the objective system against the baseline.",
                "passed": True,
                "detail": "candidate_system beats majority across paired seeds.",
                "rule_id": "objective_vs_baseline_significance_reported",
                "rule_kind": "significance_test_reporting",
            }
        ],
        tables=[],
        environment={
            "selected_sweep": "default",
            "sweeps_evaluated": ["default", "higher_order_lexical"],
        },
        outputs={},
    )


def _external_publication_spec() -> tuple[ExperimentSpec, BenchmarkSource]:
    source = BenchmarkSource(
        kind="remote_csv",
        name="Publication Regression Benchmark",
        url="https://example.com/publication-regression.csv",
        dataset_id="example/publication-regression",
        revision="2026-06-01",
        license="cc-by-4.0",
        task_family_hint="text_classification",
    )
    rows = [
        {"text": f"retrieval example {index}", "label": "retrieval"}
        for index in range(12)
    ] + [
        {"text": f"systems example {index}", "label": "systems"}
        for index in range(12)
    ]
    payload = {
        "name": "Publication Regression Benchmark",
        "description": "External benchmark fixture with persisted source provenance.",
        "train": rows[:18],
        "test": rows[18:],
        "label_space": ["retrieval", "systems"],
        "source_url": source.url,
    }
    spec = build_experiment_spec(
        "text_classification",
        ResolvedBenchmark(
            source=source,
            task_family="text_classification",
            payload=payload,
            benchmark_name="Publication Regression Benchmark",
            benchmark_description="External benchmark fixture with persisted source provenance.",
        ),
    )
    spec = spec.model_copy(
        update={
            "ablations": [
                AblationSpec(
                    name="candidate_ablation",
                    description="Remove the strongest lexical feature group.",
                )
            ]
        }
    )
    return enforce_publication_protocol(spec), source


def _readiness_run(
    *,
    spec: ExperimentSpec,
    benchmark: BenchmarkSource,
    artifact: ResultArtifact,
    profile: str = "publication",
    claim_matrix: AutoResearchClaimEvidenceMatrixRead | None = None,
) -> AutoResearchRunRead:
    timestamp = datetime.now(UTC).replace(tzinfo=None)
    return AutoResearchRunRead(
        id="run_publication_readiness",
        project_id="project_publication_readiness",
        topic="Publication readiness regression",
        status="done",
        request=AutoResearchRunConfig(execution_profile=profile),
        task_family="text_classification",
        benchmark=benchmark,
        spec=spec,
        literature=_publication_literature(),
        claim_evidence_matrix=claim_matrix or _publication_claim_matrix(),
        paper_compile_report=_publication_compile_report(),
        artifact=artifact,
        paper_markdown="# Publication Readiness\n\nThis paper cites related work [1, 2].",
        created_at=timestamp,
        updated_at=timestamp,
    )


def _paper_compile_run(*, paper_markdown: str, claim_matrix: AutoResearchClaimEvidenceMatrixRead) -> AutoResearchRunRead:
    spec, benchmark = _external_publication_spec()
    artifact = _publication_artifact(include_ablation=True, seed_count=5)
    timestamp = datetime.now(UTC).replace(tzinfo=None)
    return AutoResearchRunRead(
        id="run_paper_compile",
        project_id="project_paper_compile",
        topic="Paper compile regression",
        status="done",
        request=AutoResearchRunConfig(execution_profile="publication"),
        task_family="text_classification",
        benchmark=benchmark,
        spec=spec,
        literature=_publication_literature(),
        claim_evidence_matrix=claim_matrix,
        paper_compile_report=_publication_compile_report(),
        artifact=artifact,
        paper_markdown=paper_markdown,
        paper_plan=_paper_plan_with_claims(),
        created_at=timestamp,
        updated_at=timestamp,
    )


def _writer_plan_and_spec() -> tuple[ResearchPlan, ExperimentSpec]:
    topic = "Writer regression topic"
    benchmark = builtin_benchmark("text_classification", topic=topic)
    spec = build_experiment_spec("text_classification", benchmark)
    plan = ResearchPlan(
        topic=topic,
        title="Writer Regression Topic",
        task_family="text_classification",
        problem_statement="Evaluate a compact text classification method.",
        motivation="The writer should preserve concrete experimental context.",
        proposed_method="Use a lightweight lexical classifier.",
        research_questions=["Does the candidate improve macro F1?"],
        hypotheses=["The candidate improves macro F1 over the baseline."],
        planned_contributions=["A grounded writer regression case."],
        experiment_outline=["Build the candidate and report grounded metrics."],
    )
    return plan, spec


def test_publication_readiness_blocks_builtin_toy_benchmark_even_with_grounded_assets() -> None:
    benchmark = builtin_benchmark("text_classification", topic="Compact CS classification")
    spec = build_experiment_spec("text_classification", benchmark)
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark.source,
        artifact=_publication_artifact(include_ablation=False, seed_count=2),
        profile="exploratory",
    )

    readiness = build_publication_readiness(run, paper_markdown=run.paper_markdown)

    assert readiness.tier == "review_ready"
    assert readiness.final_publish_ready is False
    assert readiness.publication_grade_benchmark is False
    assert readiness.completed_seed_count == 2
    assert any(
        item.check_id == "publication_grade_benchmark" and not item.passed
        for item in readiness.checks
    )
    assert any("Built-in toy benchmarks" in item for item in readiness.blockers)
    assert any("minimum completed seeds" in item for item in readiness.blockers)


def test_publication_readiness_accepts_external_profile_with_final_ablation_evidence() -> None:
    spec, benchmark = _external_publication_spec()
    assert spec.dataset.source_class == "remote_real"
    assert spec.dataset.provenance_complete is True
    assert spec.dataset.publication_grade_blockers == []
    assert spec.dataset.publication_grade_eligibility["checks"]["has_dataset_id"] is True
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
        claim_matrix=_publication_claim_matrix(partial=True),
    )

    readiness = build_publication_readiness(run, paper_markdown=run.paper_markdown)

    assert readiness.tier == "publish_ready"
    assert readiness.score == 100
    assert readiness.final_publish_ready is True
    assert readiness.publication_grade_benchmark is True
    assert readiness.completed_seed_count == 5
    assert readiness.requested_seed_count == 5
    assert readiness.significance_test_count == 1
    assert readiness.observed_ablation_count == readiness.planned_ablation_count == 1
    assert readiness.unsupported_claim_count == 0
    assert readiness.blockers == []


def test_publication_readiness_blocks_external_benchmark_with_incomplete_provenance() -> None:
    source = BenchmarkSource(
        kind="remote_csv",
        name="Incomplete Provenance Benchmark",
        url="https://example.com/incomplete.csv",
        task_family_hint="text_classification",
    )
    rows = [
        {"text": f"retrieval example {index}", "label": "retrieval"}
        for index in range(12)
    ] + [
        {"text": f"systems example {index}", "label": "systems"}
        for index in range(12)
    ]
    spec = build_experiment_spec(
        "text_classification",
        ResolvedBenchmark(
            source=source,
            task_family="text_classification",
            payload={
                "name": "Incomplete Provenance Benchmark",
                "description": "External-sized benchmark missing dataset id, revision, and license.",
                "train": rows[:18],
                "test": rows[18:],
                "label_space": ["retrieval", "systems"],
                "source_url": source.url,
            },
            benchmark_name="Incomplete Provenance Benchmark",
            benchmark_description="External-sized benchmark missing dataset id, revision, and license.",
        ),
    )
    run = _readiness_run(
        spec=spec,
        benchmark=source,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
        claim_matrix=_publication_claim_matrix(partial=True),
    )

    readiness = build_publication_readiness(run, paper_markdown=run.paper_markdown)

    assert spec.dataset.source_class == "remote_real"
    assert spec.dataset.provenance_complete is False
    assert spec.dataset.publication_grade is False
    assert "Benchmark provenance requires dataset_id." in spec.dataset.publication_grade_blockers
    assert "Benchmark provenance requires revision." in spec.dataset.publication_grade_blockers
    assert "Benchmark provenance requires license." in spec.dataset.publication_grade_blockers
    assert readiness.final_publish_ready is False
    assert readiness.publication_grade_benchmark is False
    assert any("dataset_id" in item for item in readiness.blockers)


def test_contribution_assessment_requires_more_than_experiment_completion() -> None:
    spec, benchmark = _external_publication_spec()
    artifact = _publication_artifact(include_ablation=True, seed_count=5)
    evidence = [
        AutoResearchClaimEvidenceRefRead(
            source_kind="artifact",
            label="Result artifact",
            detail="The artifact exists, but the claim only states that results were produced.",
        )
    ]
    generic_claim_matrix = AutoResearchClaimEvidenceMatrixRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        claim_count=1,
        supported_claim_count=1,
        unsupported_claim_count=0,
        entries=[
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_experiment_completed",
                category="result",
                section_hint="Results",
                claim="Experiment results benchmark metrics.",
                support_status="supported",
                evidence=evidence,
            )
        ],
    )
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=artifact,
        claim_matrix=generic_claim_matrix,
    )
    readiness = build_publication_readiness(run, paper_markdown=run.paper_markdown)

    assessment = build_contribution_assessment(run, publication_readiness=readiness)

    assert assessment.complete is False
    assert assessment.clear_contribution_count == 0
    assert assessment.strong_core_claim_count == 0
    assert any("completed experiments alone" in item for item in assessment.blockers)
    assert any("clear, substantive contribution" in item for item in assessment.blockers)


def test_contribution_assessment_accepts_statistically_supported_core_claim() -> None:
    spec, benchmark = _external_publication_spec()
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
    )
    readiness = build_publication_readiness(run, paper_markdown=run.paper_markdown)

    assessment = build_contribution_assessment(run, publication_readiness=readiness)

    assert assessment.complete is True
    assert assessment.clear_contribution_count >= 1
    assert assessment.strong_core_claim_count >= 1
    assert any(
        item.claim_strength == "statistically_supported"
        for item in assessment.contribution_claims
        if item.core
    )
    assert not any("completed experiments alone" in item for item in assessment.blockers)


def test_experiment_design_accepts_publication_protocol_with_fair_baselines() -> None:
    spec, benchmark = _external_publication_spec()
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
    )

    design = build_experiment_design(run)

    assert design.completeness == "complete"
    assert design.blockers == []
    assert design.naive_baseline_present is True
    assert design.strong_baseline_present is True
    assert design.candidate_method_present is True
    assert design.fair_baseline_count >= 2
    assert design.ablation_coverage == 1.0
    assert design.seed_plan.sufficient_for_profile is True
    assert design.statistical_test_plan.recommended_test == "paired_t_test"
    assert design.statistical_test_plan.complete is True
    assert {item.category for item in design.failure_mode_analysis} >= {
        "performance_failure",
        "baseline_fairness_failure",
        "ablation_coverage_failure",
        "statistical_power_failure",
    }


def test_experiment_design_blocks_publication_without_strong_baseline_or_statistics() -> None:
    spec, benchmark = _external_publication_spec()
    weak_spec = spec.model_copy(
        update={
            "baselines": [BaselineSpec(name="majority", description="Naive majority baseline.")],
            "seeds": [7],
            "acceptance_criteria": [],
        }
    )
    run = _readiness_run(
        spec=weak_spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=1),
    )

    design = build_experiment_design(run)

    assert design.completeness == "blocked"
    assert design.naive_baseline_present is True
    assert design.strong_baseline_present is False
    assert any("strong conventional baseline" in item for item in design.blockers)
    assert any("enough seeds" in item for item in design.blockers)
    assert any("statistical test plan" in item for item in design.blockers)


def test_failure_analysis_maps_statistical_and_ablation_failures_to_replan() -> None:
    spec, benchmark = _external_publication_spec()
    artifact = _publication_artifact(include_ablation=False, seed_count=5)
    failed_test = artifact.significance_tests[0].model_copy(
        update={
            "p_value": 0.42,
            "adjusted_p_value": 0.42,
            "effect_size": 0.02,
            "adequately_powered": False,
            "significant": False,
            "detail": "candidate_system does not significantly beat majority across paired seeds.",
        }
    )
    failed_acceptance_checks = [
        item.model_copy(
            update={
                "passed": False,
                "detail": "candidate_system does not significantly beat majority across paired seeds.",
            }
        )
        if item.rule_kind == "significance_test_reporting"
        else item
        for item in artifact.acceptance_checks
    ]
    artifact = artifact.model_copy(
        update={
            "significance_tests": [failed_test],
            "acceptance_checks": failed_acceptance_checks,
        }
    )
    run = _readiness_run(spec=spec, benchmark=benchmark, artifact=artifact)
    design = build_experiment_design(run)
    readiness = build_publication_readiness(run, paper_markdown=run.paper_markdown)
    graph = build_literature_graph(run)
    novelty = build_novelty_validation(run, literature_graph=graph)
    contribution = build_contribution_assessment(run, publication_readiness=readiness)

    failure_analysis = build_failure_analysis(
        run,
        experiment_design=design,
        contribution_assessment=contribution,
        novelty_validation=novelty,
        publication_readiness=readiness,
    )

    assert failure_analysis.complete is False
    assert failure_analysis.statistical_failure_count == 1
    assert failure_analysis.ablation_failure_count >= 1
    assert failure_analysis.publication_blocker_count >= 2
    assert {
        "statistical_not_significant",
        "ablation_unsupported_claim",
    }.issubset({item.failure_type for item in failure_analysis.findings})

    replan = build_research_replan(
        run,
        failure_analysis=failure_analysis,
        experiment_design=design,
        contribution_assessment=contribution,
        novelty_validation=novelty,
    )

    action_kinds = {item.action_kind for item in replan.actions}
    assert {"add_ablation", "rerun_plan", "downgrade_contribution_claim"}.issubset(action_kinds)
    assert replan.rerun_required is True
    assert replan.claim_downgrade_required is True
    assert replan.experiment_design_repair_required is True
    assert any("Final publish is blocked" in item for item in replan.blockers)


def test_literature_graph_and_novelty_validation_accept_literature_backed_gap() -> None:
    spec, benchmark = _external_publication_spec()
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
    )

    graph = build_literature_graph(run)
    validation = build_novelty_validation(run, literature_graph=graph)

    assert graph.real_paper_count == 2
    assert graph.paper_nodes
    assert graph.method_nodes
    assert graph.claim_nodes
    assert graph.similar_methods
    assert validation.complete is True
    assert validation.gap_validity == "valid"
    assert validation.recommendation in {"proceed", "reframe_positioning"}
    assert validation.blockers == []


def test_novelty_validation_blocks_when_gap_is_not_literature_backed_or_testable() -> None:
    spec, benchmark = _external_publication_spec()
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
    ).model_copy(
        update={
            "literature": [
                LiteratureInsight(
                    paper_id="paper_no_gap",
                    title="Generic Compact Retrieval Survey",
                    year=2024,
                    source="semantic_scholar",
                    insight="Surveys compact retrieval systems without identifying a testable gap.",
                    method_hint="Compare compact retrieval methods.",
                )
            ],
            "literature_synthesis": None,
        }
    )

    graph = build_literature_graph(run)
    validation = build_novelty_validation(run, literature_graph=graph)

    assert graph.real_paper_count == 1
    assert validation.complete is False
    assert validation.gap_validity == "missing"
    assert any("literature-backed research gap" in item for item in validation.blockers)


def test_publication_readiness_requires_ablation_in_final_selected_artifact() -> None:
    spec, benchmark = _external_publication_spec()
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=False, seed_count=5),
    )

    readiness = build_publication_readiness(run, paper_markdown=run.paper_markdown)

    assert readiness.tier == "publish_candidate"
    assert readiness.final_publish_ready is False
    assert readiness.observed_ablation_count == 0
    assert any(
        item.check_id == "planned_ablations_observed" and not item.passed
        for item in readiness.checks
    )


def test_paper_evidence_compiler_blocks_unregistered_claims_and_overclaiming() -> None:
    claim_matrix = _publication_claim_matrix()
    run = _paper_compile_run(
        claim_matrix=claim_matrix,
        paper_markdown=(
            "# Publication Readiness Paper\n\n"
            "## Abstract\n"
            "We demonstrate a novel method that significantly outperforms all prior work.\n\n"
            "## 1. Results\n"
            "The candidate outperforms the majority baseline on macro F1.\n\n"
            "## 2. Conclusion\n"
            "This work establishes a broad, generalizable system-level improvement."
        ),
    )

    report = compile_paper_evidence(
        run.paper_compile_report,
        run=run,
        paper_markdown=run.paper_markdown,
        paper_plan=run.paper_plan,
        claim_evidence_matrix=run.claim_evidence_matrix,
        artifact=run.artifact,
        literature_count=len(run.literature),
    )

    assert report.paper_tier == "technical_report"
    assert report.unregistered_claim_count >= 1
    assert report.contradiction_count >= 1
    assert report.blocker_count >= 1
    assert report.evidence_blockers
    assert any(item.claim_id == "claim_supported_result" for item in report.claim_ledger)
    assert any(item.strong for item in report.claim_ledger)


def test_paper_evidence_compiler_promotes_claim_ledgers_when_paper_is_bounded() -> None:
    claim_matrix = _publication_claim_matrix(partial=True)
    run = _paper_compile_run(
        claim_matrix=claim_matrix,
        paper_markdown=(
            "# Publication Readiness Paper\n\n"
            "## Abstract\n"
            "We report the candidate result on the benchmark.\n\n"
            "## 1. Results\n"
            "The candidate outperforms the majority baseline on macro F1.\n\n"
            "## 2. Conclusion\n"
            "This paper stays bounded to the executed artifact and evidence ledger."
        ),
    )

    report = compile_paper_evidence(
        run.paper_compile_report,
        run=run,
        paper_markdown=run.paper_markdown,
        paper_plan=run.paper_plan,
        claim_evidence_matrix=run.claim_evidence_matrix,
        artifact=run.artifact,
        literature_count=len(run.literature),
    )

    assert report.paper_tier in {
        "workshop_candidate",
        "conference_candidate",
        "strong_conference_candidate",
    }
    assert report.unregistered_claim_count == 0
    assert report.contradiction_count == 0
    assert report.evidence_bound_paragraph_count >= 1


def test_autoresearch_attempt_preference_keeps_richer_tied_artifact() -> None:
    orchestrator = autoresearch_orchestrator.AutoResearchOrchestrator()
    narrow = _publication_artifact(include_ablation=False, seed_count=5)
    richer = _publication_artifact(include_ablation=True, seed_count=5)

    assert orchestrator._attempt_preference_key(richer) > orchestrator._attempt_preference_key(narrow)


def test_operator_console_summary_surfaces_publication_readiness() -> None:
    spec, benchmark = _external_publication_spec()
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
    )
    protocol = build_research_protocol(run)
    benchmark_card = build_benchmark_card(run)
    audit = build_methodology_audit(run, protocol=protocol)
    readiness = build_publication_readiness(run, paper_markdown=run.paper_markdown)
    dossier = review_publish.AutoResearchRevisionDossierRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        review_round=1,
        review_fingerprint="review-fingerprint",
        overall_status="ready",
        publication_tier=readiness.tier,
        publication_readiness_score=readiness.score,
        methodology_audit_score=audit.score,
        methodology_audit_compliant=audit.compliant,
        complete=True,
        dossier_fingerprint="dossier-fingerprint",
    )
    evidence_index = AutoResearchPublicationEvidenceIndexRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        project_id=run.project_id,
        run_id=run.id,
        review_round=1,
        review_fingerprint="review-fingerprint",
        publication_tier=readiness.tier,
        publication_readiness_score=readiness.score,
        evidence_item_count=18,
        required_evidence_count=18,
        present_required_evidence_count=18,
        missing_required_evidence_count=0,
        complete=True,
        evidence_index_fingerprint="evidence-index-fingerprint",
    )
    artifact_integrity_audit = AutoResearchArtifactIntegrityAuditRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        project_id=run.project_id,
        run_id=run.id,
        selected_candidate_id=run.portfolio.selected_candidate_id if run.portfolio is not None else None,
        registry_asset_count=32,
        existing_registry_asset_count=32,
        missing_registry_asset_count=0,
        bundle_count=2,
        selected_bundle_asset_count=24,
        selected_bundle_missing_required_count=0,
        lineage_edge_count=48,
        missing_lineage_target_count=0,
        untraced_existing_asset_count=0,
        complete=True,
        audit_fingerprint="artifact-integrity-fingerprint",
    )
    repair_plan = AutoResearchPublicationRepairPlanRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        project_id=run.project_id,
        run_id=run.id,
        review_round=1,
        review_fingerprint="review-fingerprint",
        publication_tier=readiness.tier,
        publication_readiness_score=readiness.score,
        action_count=1,
        pending_action_count=1,
        auto_applicable_action_count=1,
        next_action_ids=["repair_claims"],
        actions=[
            AutoResearchPublicationRepairActionRead(
                action_id="repair_claims",
                kind="repair_claim_evidence",
                source="readiness",
                priority="high",
                title="Repair claim evidence",
                detail="Refresh claim-evidence support.",
                auto_applicable=True,
                expected_outputs=["run_claim_evidence_matrix_json"],
            )
        ],
        repair_plan_fingerprint="repair-plan-fingerprint",
    )
    repair_execution = AutoResearchPublicationRepairExecutionRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        project_id=run.project_id,
        run_id=run.id,
        repair_plan_fingerprint=repair_plan.repair_plan_fingerprint,
        review_round_before=1,
        review_fingerprint_before="review-fingerprint",
        review_round_after=2,
        review_fingerprint_after="review-fingerprint-after",
        attempted_action_count=1,
        executed_action_count=1,
        materialized_output_asset_ids=["run_claim_evidence_matrix_json"],
        action_results=[
            AutoResearchPublicationRepairExecutionActionRead(
                action_id="repair_claims",
                kind="repair_claim_evidence",
                title="Repair claim evidence",
                status="executed",
                auto_applicable=True,
                expected_output_asset_ids=["run_claim_evidence_matrix_json"],
                materialized_output_asset_ids=["run_claim_evidence_matrix_json"],
                detail="Repair action ran and all expected output assets are materialized.",
            )
        ],
        success=True,
        execution_fingerprint="repair-execution-fingerprint",
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=run.project_id,
        run_id=run.id,
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Publication-ready console regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        novelty_assessment=AutoResearchNoveltyAssessmentRead(
            status="grounded",
            summary="Grounded literature context.",
            compared_paper_count=2,
            strong_match_count=1,
        ),
        research_protocol=protocol,
        benchmark_card=benchmark_card,
        methodology_audit=audit,
        publication_readiness=readiness,
        revision_dossier=dossier,
        publication_evidence_index=evidence_index,
        artifact_integrity_audit=artifact_integrity_audit,
        publication_repair_plan=repair_plan,
        publication_repair_execution=repair_execution,
        scores=review_publish.AutoResearchReviewScoresRead(),
    )
    publish = AutoResearchPublishPackageRead(
        project_id=run.project_id,
        run_id=run.id,
        package_id="publish_ready_bundle",
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        status="publish_ready",
        publish_ready=True,
        review_bundle_ready=True,
        final_publish_ready=True,
        publication_tier=readiness.tier,
        publication_readiness_score=readiness.score,
    )

    summary = autoresearch_console._run_summary(
        run=run,
        execution=AutoResearchRunExecutionRead(project_id=run.project_id, run_id=run.id),
        bridge=None,
        review=review,
        review_loop=None,
        publish=publish,
    )

    assert summary.execution_profile == "publication"
    assert summary.publication_tier == "publish_ready"
    assert summary.publication_readiness_score == 100
    assert summary.research_protocol_complete is True
    assert summary.research_protocol_blocker_count == 0
    assert summary.methodology_audit_compliant is True
    assert summary.methodology_audit_score == 100
    assert summary.methodology_audit_checks_passed == summary.methodology_audit_checks_total
    assert summary.revision_dossier_complete is True
    assert summary.revision_dossier_blocker_count == 0
    assert summary.benchmark_card_publication_grade is True
    assert summary.benchmark_card_provenance_complete is True
    assert summary.benchmark_card_total_examples == 24
    assert summary.benchmark_card_blocker_count == 0
    assert summary.publication_evidence_index_complete is True
    assert summary.publication_evidence_index_missing_count == 0
    assert summary.publication_evidence_index_blockers == []
    assert summary.artifact_integrity_audit_complete is True
    assert summary.artifact_integrity_audit_blocker_count == 0
    assert summary.artifact_integrity_audit_warning_count == 0
    assert summary.artifact_integrity_audit_untraced_asset_count == 0
    assert summary.artifact_integrity_audit_missing_lineage_target_count == 0
    assert summary.artifact_integrity_audit_blockers == []
    assert summary.publication_repair_plan_complete is False
    assert summary.publication_repair_plan_pending_count == 1
    assert summary.publication_repair_plan_blocked_count == 0
    assert summary.publication_repair_plan_auto_applicable_count == 1
    assert summary.publication_repair_plan_next_actions == ["Repair claim evidence"]
    assert summary.publication_repair_execution_success is True
    assert summary.publication_repair_execution_attempted_count == 1
    assert summary.publication_repair_execution_executed_count == 1
    assert summary.publication_repair_execution_partial_count == 0
    assert summary.publication_repair_execution_missing_outputs == []
    assert summary.publication_grade_benchmark is True
    assert summary.readiness_checks_passed == summary.readiness_checks_total
    assert summary.publication_blocker_count == 0
    assert autoresearch_console._matches_filters(
        run=run,
        review=review,
        publish=publish,
        filters=AutoResearchOperatorConsoleFiltersRead(publication_tier="publish_ready"),
    )
    assert not autoresearch_console._matches_filters(
        run=run,
        review=review,
        publish=publish,
        filters=AutoResearchOperatorConsoleFiltersRead(publication_tier="review_ready"),
    )


def test_operator_console_summary_prefers_publish_final_blockers() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    project_id = "project_console_publish_blockers"
    run_id = "run_console_publish_blockers"
    run = AutoResearchRunRead(
        id=run_id,
        project_id=project_id,
        topic="Console publish blocker visibility",
        status="done",
        created_at=now,
        updated_at=now,
    )
    readiness = review_publish.AutoResearchPublicationReadinessRead(
        generated_at=now,
        tier="publish_ready",
        score=100,
        summary="Readiness checks have no blockers.",
        final_publish_ready=True,
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Ready review with downstream publish blockers.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        publication_readiness=readiness,
        scores=review_publish.AutoResearchReviewScoresRead(),
    )
    publish = AutoResearchPublishPackageRead(
        project_id=project_id,
        run_id=run_id,
        package_id="publish_ready_bundle",
        generated_at=now,
        status="revision_required",
        publish_ready=False,
        review_bundle_ready=True,
        final_publish_ready=False,
        publication_tier="publish_ready",
        publication_readiness_score=100,
        final_blocker_count=1,
        final_blockers=["Final publish requires artifact integrity audit."],
    )

    summary = autoresearch_console._run_summary(
        run=run,
        execution=AutoResearchRunExecutionRead(project_id=project_id, run_id=run_id),
        bridge=None,
        review=review,
        review_loop=None,
        publish=publish,
    )

    assert summary.publication_blocker_count == 1
    assert summary.publication_blockers == [
        "Final publish requires artifact integrity audit."
    ]


def test_apply_review_actions_respects_repair_plan_action_kind() -> None:
    paper_plan = AutoResearchPublicationRepairPlanRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        project_id="project_repair_gate",
        run_id="run_repair_gate",
        action_count=1,
        pending_action_count=1,
        auto_applicable_action_count=1,
        next_action_ids=["paper_repair"],
        actions=[
            AutoResearchPublicationRepairActionRead(
                action_id="paper_repair",
                kind="rebuild_paper_sources",
                source="revision_action",
                title="Rebuild paper sources",
                detail="Materialize missing paper source package.",
                auto_applicable=True,
                expected_outputs=["run_paper_sources_manifest_json"],
            )
        ],
        repair_plan_fingerprint="paper-repair",
    )
    autoresearch_orchestrator._ensure_repair_plan_allows_paper_rebuild(paper_plan)

    experiment_plan = paper_plan.model_copy(
        update={
            "next_action_ids": ["rerun_experiment"],
            "actions": [
                AutoResearchPublicationRepairActionRead(
                    action_id="rerun_experiment",
                    kind="rerun_experiments",
                    source="readiness",
                    title="Rerun experiments",
                    detail="Add missing seed and ablation evidence.",
                    auto_applicable=True,
                    expected_outputs=["run_artifact_json"],
                )
            ],
            "repair_plan_fingerprint": "experiment-repair",
        }
    )
    with pytest.raises(ValueError, match="non-paper repair actions"):
        autoresearch_orchestrator._ensure_repair_plan_allows_paper_rebuild(experiment_plan)

    blocked_plan = paper_plan.model_copy(
        update={
            "pending_action_count": 0,
            "blocked_action_count": 1,
            "auto_applicable_action_count": 0,
            "next_action_ids": [],
            "actions": [
                AutoResearchPublicationRepairActionRead(
                    action_id="manual_review",
                    kind="manual_review",
                    source="evidence_index",
                    title="Close manual provenance",
                    detail="Attach operator-reviewed provenance.",
                    status="blocked",
                    blockers=["Requires operator-supplied provenance."],
                )
            ],
            "repair_plan_fingerprint": "manual-repair",
        }
    )
    with pytest.raises(ValueError, match="manual repair"):
        autoresearch_orchestrator._ensure_repair_plan_allows_paper_rebuild(blocked_plan)


def test_publication_repair_execution_requires_review_loop_closure(monkeypatch) -> None:
    project_id = "project-repair-loop-closure"
    run_id = "run-repair-loop-closure"
    action_title = "Tighten statistical reporting"
    repair_plan = AutoResearchPublicationRepairPlanRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        project_id=project_id,
        run_id=run_id,
        action_count=1,
        pending_action_count=1,
        auto_applicable_action_count=1,
        next_action_ids=["repair_stats"],
        actions=[
            AutoResearchPublicationRepairActionRead(
                action_id="repair_stats",
                kind="rerun_experiments",
                source="revision_action",
                title=action_title,
                detail="Add missing statistical report.",
                auto_applicable=True,
                expected_outputs=["run_artifact_json"],
            )
        ],
        repair_plan_fingerprint="repair-stats-fingerprint",
    )

    def loop_with(status: str) -> review_publish.AutoResearchReviewLoopRead:
        return review_publish.AutoResearchReviewLoopRead(
            project_id=project_id,
            run_id=run_id,
            generated_at=datetime.now(UTC).replace(tzinfo=None),
            current_round=1,
            latest_review_fingerprint=f"fingerprint-{status}",
            actions=[
                review_publish.AutoResearchReviewLoopActionRead(
                    action_id="loop_repair_stats",
                    action_kind="experiment_repair",
                    repair_kind="rerun_experiments",
                    execution_route="experiment_rerun",
                    title=action_title,
                    detail="Add missing statistical report.",
                    status=status,
                    auto_applicable=True,
                    expected_output_asset_ids=["run_artifact_json"],
                )
            ],
            pending_action_count=1 if status == "pending" else 0,
            completed_action_count=1 if status == "completed" else 0,
            pending_revision_actions=[action_title] if status == "pending" else [],
        )

    monkeypatch.setattr(
        publication_repair_execution,
        "_selected_output_roles",
        lambda *_args: {"run_artifact_json"},
    )

    unresolved = publication_repair_execution.build_publication_repair_execution(
        project_id=project_id,
        run_id=run_id,
        repair_plan=repair_plan,
        review_loop_before=loop_with("pending"),
        review_loop_after=loop_with("pending"),
    )
    assert unresolved.success is False
    assert unresolved.partial_action_count == 1
    assert unresolved.action_results[0].status == "partial"
    assert "still reports the action as pending" in unresolved.action_results[0].detail

    resolved = publication_repair_execution.build_publication_repair_execution(
        project_id=project_id,
        run_id=run_id,
        repair_plan=repair_plan,
        review_loop_before=loop_with("pending"),
        review_loop_after=loop_with("completed"),
    )
    assert resolved.success is True
    assert resolved.executed_action_count == 1
    assert resolved.action_results[0].status == "executed"


def test_review_loop_materializes_bounded_action_routes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    now = datetime.now(UTC).replace(tzinfo=None)
    findings = [
        review_publish.AutoResearchReviewFindingRead(
            id="finding_seed",
            severity="warning",
            category="statistics",
            summary="Seed coverage is insufficient for publication-level claims.",
            detail="Run more seeds before making stability claims.",
            supporting_asset_ids=["run_artifact_json"],
        ),
        review_publish.AutoResearchReviewFindingRead(
            id="finding_claim",
            severity="warning",
            category="context",
            summary="Claim-evidence matrix contains unsupported claims.",
            detail="Unsupported claims must be demoted or backed by additional experiments.",
            supporting_asset_ids=["run_claim_evidence_matrix_json"],
        ),
        review_publish.AutoResearchReviewFindingRead(
            id="finding_paper",
            severity="warning",
            category="context",
            summary="Original hypothesis is not clearly resolved.",
            detail="The manuscript should state whether the planned hypothesis was supported.",
            supporting_asset_ids=["run_paper_markdown"],
        ),
        review_publish.AutoResearchReviewFindingRead(
            id="finding_citation",
            severity="warning",
            category="citation",
            summary="Paper text does not include citation markers.",
            detail="Add citation support to related work.",
            supporting_asset_ids=["run_paper_markdown"],
        ),
    ]
    review = review_publish.AutoResearchRunReviewRead(
        project_id="project_review_loop_routes",
        run_id="run_review_loop_routes",
        generated_at=now,
        overall_status="needs_revision",
        summary="Review loop action route regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        findings=findings,
        revision_plan=[
            review_publish.AutoResearchRevisionActionRead(
                id="action_seed",
                priority="high",
                title="Run additional seeds before final publication",
                detail="Complete the planned seed set and preserve per-seed artifacts.",
                finding_ids=["finding_seed"],
            ),
            review_publish.AutoResearchRevisionActionRead(
                id="action_claim",
                priority="high",
                title="Rerun experiments or demote unsupported claims",
                detail="Unsupported claims must become limitations unless new evidence is imported.",
                finding_ids=["finding_claim"],
            ),
            review_publish.AutoResearchRevisionActionRead(
                id="action_paper",
                priority="medium",
                title="State clearly whether the original hypothesis was supported",
                detail="Make the publish-facing paper state what the artifact supports.",
                finding_ids=["finding_paper"],
            ),
            review_publish.AutoResearchRevisionActionRead(
                id="action_citation",
                priority="medium",
                title="Add citation support to contextual and related-work claims",
                detail="Introduce explicit citations in background and related-work sections.",
                finding_ids=["finding_citation"],
            ),
        ],
    )

    loop = review_publish._build_review_loop(
        project_id=review.project_id,
        run_id=review.run_id,
        review=review,
    )

    actions = {item.title: item for item in loop.actions}
    seed_action = actions["Run additional seeds before final publication"]
    claim_action = actions["Rerun experiments or demote unsupported claims"]
    paper_action = actions["State clearly whether the original hypothesis was supported"]
    citation_action = actions["Add citation support to contextual and related-work claims"]
    assert seed_action.action_kind == "experiment_repair"
    assert seed_action.repair_kind == "rerun_experiments"
    assert seed_action.execution_route == "experiment_rerun"
    assert "run_artifact_json" in seed_action.expected_output_asset_ids
    assert claim_action.action_kind == "claim_downgrade"
    assert claim_action.repair_kind == "repair_claim_evidence"
    assert claim_action.execution_route == "paper_rebuild"
    assert "claim-evidence ledger" in claim_action.terminal_condition
    assert paper_action.action_kind == "paper_revision"
    assert paper_action.execution_route == "paper_rebuild"
    assert citation_action.action_kind == "literature_refresh"
    assert citation_action.execution_route == "literature_refresh"
    assert loop.experiment_repair_action_count == 1
    assert loop.claim_downgrade_action_count == 1
    assert loop.paper_revision_action_count == 1
    assert loop.literature_refresh_action_count == 1
    assert loop.re_review_action_count == 4
    assert loop.next_review_required is True
    assert loop.auto_revision_rounds_remaining == 2


def _minimal_review_loop(
    *,
    project_id: str,
    run_id: str,
    round_index: int,
    fingerprint: str,
    pending_actions: int,
    open_issues: int,
    rounds_remaining: int = 2,
) -> review_publish.AutoResearchReviewLoopRead:
    now = datetime.now(UTC).replace(tzinfo=None)
    return review_publish.AutoResearchReviewLoopRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        current_round=round_index,
        latest_review_fingerprint=fingerprint,
        pending_action_count=pending_actions,
        open_issue_count=open_issues,
        auto_revision_rounds_remaining=rounds_remaining,
        next_review_required=pending_actions > 0,
    )


def _minimal_run_review(project_id: str, run_id: str) -> review_publish.AutoResearchRunReviewRead:
    return review_publish.AutoResearchRunReviewRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Auto apply review-loop regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
    )


def _minimal_repair_execution(
    *,
    project_id: str,
    run_id: str,
    success: bool,
    partial_count: int = 0,
) -> AutoResearchPublicationRepairExecutionRead:
    return AutoResearchPublicationRepairExecutionRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        project_id=project_id,
        run_id=run_id,
        attempted_action_count=1,
        executed_action_count=0 if partial_count else 1,
        partial_action_count=partial_count,
        success=success,
        execution_fingerprint="auto-apply-repair-execution",
    )


def test_auto_apply_review_loop_rechecks_until_clean(monkeypatch) -> None:
    project_id = "project_auto_apply_clean"
    run_id = "run_auto_apply_clean"
    run = AutoResearchRunRead(
        id=run_id,
        project_id=project_id,
        topic="Auto apply clean",
        status="done",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    state = {"applied": False}

    def fake_build_review_loop(*_args, **_kwargs):
        if state["applied"]:
            return _minimal_review_loop(
                project_id=project_id,
                run_id=run_id,
                round_index=2,
                fingerprint="fp-clean",
                pending_actions=0,
                open_issues=0,
            )
        return _minimal_review_loop(
            project_id=project_id,
            run_id=run_id,
            round_index=1,
            fingerprint="fp-pending",
            pending_actions=1,
            open_issues=1,
        )

    def fake_apply(self, **kwargs):
        del self
        assert kwargs["expected_round"] == 1
        assert kwargs["expected_review_fingerprint"] == "fp-pending"
        state["applied"] = True
        return (
            run,
            _minimal_repair_execution(project_id=project_id, run_id=run_id, success=True),
            ["repair_claims"],
            False,
        )

    monkeypatch.setattr(autoresearch_orchestrator, "load_run", lambda *_args, **_kwargs: run)
    monkeypatch.setattr(review_publish, "build_review_loop", fake_build_review_loop)
    monkeypatch.setattr(review_publish, "build_run_review", lambda *_args, **_kwargs: _minimal_run_review(project_id, run_id))
    monkeypatch.setattr(autoresearch_orchestrator.AutoResearchOrchestrator, "apply_review_actions", fake_apply)

    result = autoresearch_orchestrator.AutoResearchOrchestrator().auto_apply_review_loop(
        db=None,  # type: ignore[arg-type]
        project_id=project_id,
        run_id=run_id,
        max_rounds=3,
        expected_review_fingerprint="fp-pending",
    )

    assert result.completed is True
    assert result.blocked is False
    assert result.stop_reason == "completed"
    assert result.applied_action_ids == ["repair_claims"]
    assert [step.status for step in result.steps] == ["applied", "no_pending_actions"]
    assert result.review_loop.pending_action_count == 0
    assert result.review_loop.open_issue_count == 0


def test_auto_apply_review_loop_stops_on_incomplete_repair(monkeypatch) -> None:
    project_id = "project_auto_apply_partial"
    run_id = "run_auto_apply_partial"
    run = AutoResearchRunRead(
        id=run_id,
        project_id=project_id,
        topic="Auto apply partial",
        status="done",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    def fake_build_review_loop(*_args, **_kwargs):
        return _minimal_review_loop(
            project_id=project_id,
            run_id=run_id,
            round_index=1,
            fingerprint="fp-partial",
            pending_actions=1,
            open_issues=1,
        )

    def fake_apply(self, **_kwargs):
        del self
        return (
            run,
            _minimal_repair_execution(
                project_id=project_id,
                run_id=run_id,
                success=False,
                partial_count=1,
            ),
            ["repair_claims"],
            False,
        )

    monkeypatch.setattr(autoresearch_orchestrator, "load_run", lambda *_args, **_kwargs: run)
    monkeypatch.setattr(review_publish, "build_review_loop", fake_build_review_loop)
    monkeypatch.setattr(review_publish, "build_run_review", lambda *_args, **_kwargs: _minimal_run_review(project_id, run_id))
    monkeypatch.setattr(autoresearch_orchestrator.AutoResearchOrchestrator, "apply_review_actions", fake_apply)

    result = autoresearch_orchestrator.AutoResearchOrchestrator().auto_apply_review_loop(
        db=None,  # type: ignore[arg-type]
        project_id=project_id,
        run_id=run_id,
        max_rounds=3,
        expected_review_fingerprint="fp-partial",
    )

    assert result.completed is False
    assert result.blocked is True
    assert result.stop_reason == "repair_incomplete"
    assert result.step_count == 1
    assert result.steps[0].status == "repair_incomplete"
    assert result.steps[0].repair_execution is not None
    assert result.steps[0].repair_execution.partial_action_count == 1


def test_operator_console_disables_apply_review_actions_for_non_paper_repair_plan() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    run = AutoResearchRunRead(
        id="run_console_repair_action_gate",
        project_id="project_console_repair_action_gate",
        topic="Console repair action gate",
        status="done",
        task_family="text_classification",
        created_at=now,
        updated_at=now,
    )
    review_loop = review_publish.AutoResearchReviewLoopRead(
        project_id=run.project_id,
        run_id=run.id,
        generated_at=now,
        current_round=1,
        pending_action_count=1,
        pending_revision_actions=["Rerun experiments"],
    )
    experiment_plan = AutoResearchPublicationRepairPlanRead(
        generated_at=now,
        project_id=run.project_id,
        run_id=run.id,
        action_count=1,
        pending_action_count=1,
        auto_applicable_action_count=1,
        next_action_ids=["rerun_experiment"],
        actions=[
            AutoResearchPublicationRepairActionRead(
                action_id="rerun_experiment",
                kind="rerun_experiments",
                source="readiness",
                title="Rerun experiments",
                detail="Add missing seed and ablation evidence.",
                auto_applicable=True,
                expected_outputs=["run_artifact_json"],
            )
        ],
        repair_plan_fingerprint="experiment-repair",
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=run.project_id,
        run_id=run.id,
        generated_at=now,
        overall_status="needs_revision",
        summary="Console repair action gate regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        publication_repair_plan=experiment_plan,
    )

    actions = autoresearch_console._run_actions(
        run=run,
        execution=AutoResearchRunExecutionRead(project_id=run.project_id, run_id=run.id),
        bridge=None,
        review=review,
        review_loop=review_loop,
        publish=None,
    )

    assert actions.apply_review_actions is False
    assert actions.rebuild_paper is False

    paper_plan = experiment_plan.model_copy(
        update={
            "next_action_ids": ["repair_claims"],
            "actions": [
                AutoResearchPublicationRepairActionRead(
                    action_id="repair_claims",
                    kind="repair_claim_evidence",
                    source="readiness",
                    title="Repair claim evidence",
                    detail="Refresh claim-evidence support.",
                    auto_applicable=True,
                    expected_outputs=["run_claim_evidence_matrix_json"],
                )
            ],
            "repair_plan_fingerprint": "paper-repair",
        }
    )
    paper_actions = autoresearch_console._run_actions(
        run=run,
        execution=AutoResearchRunExecutionRead(project_id=run.project_id, run_id=run.id),
        bridge=None,
        review=review.model_copy(update={"publication_repair_plan": paper_plan}),
        review_loop=review_loop,
        publish=None,
    )

    assert paper_actions.apply_review_actions is True
    assert paper_actions.rebuild_paper is True


def test_final_publish_blocks_unresolved_repair_state() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    repair_plan = AutoResearchPublicationRepairPlanRead(
        generated_at=now,
        project_id="project_repair_state_gate",
        run_id="run_repair_state_gate",
        action_count=2,
        pending_action_count=1,
        blocked_action_count=1,
        auto_applicable_action_count=1,
        next_action_ids=["repair_claims"],
        actions=[
            AutoResearchPublicationRepairActionRead(
                action_id="repair_claims",
                kind="repair_claim_evidence",
                source="readiness",
                priority="high",
                title="Repair claim evidence",
                detail="Refresh claim-evidence support.",
                auto_applicable=True,
                expected_outputs=["run_claim_evidence_matrix_json"],
            ),
            AutoResearchPublicationRepairActionRead(
                action_id="manual_provenance",
                kind="manual_review",
                source="evidence_index",
                priority="high",
                title="Close manual provenance",
                detail="Attach operator-reviewed provenance.",
                status="blocked",
                blockers=["Requires operator-supplied provenance."],
            ),
        ],
        blockers=["Blocked repair action requires manual input: Close manual provenance"],
        repair_plan_fingerprint="current-repair-plan",
    )
    repair_execution = AutoResearchPublicationRepairExecutionRead(
        generated_at=now,
        project_id=repair_plan.project_id,
        run_id=repair_plan.run_id,
        repair_plan_fingerprint="stale-repair-plan",
        attempted_action_count=1,
        partial_action_count=1,
        missing_output_asset_ids=["run_claim_evidence_matrix_json"],
        action_results=[
            AutoResearchPublicationRepairExecutionActionRead(
                action_id="repair_claims",
                kind="repair_claim_evidence",
                title="Repair claim evidence",
                status="partial",
                auto_applicable=True,
                expected_output_asset_ids=["run_claim_evidence_matrix_json"],
                missing_output_asset_ids=["run_claim_evidence_matrix_json"],
                detail="Repair action ran but expected outputs are still missing.",
            )
        ],
        success=False,
        execution_fingerprint="repair-execution",
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=repair_plan.project_id,
        run_id=repair_plan.run_id,
        generated_at=now,
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Repair state gate regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        publication_repair_plan=repair_plan,
        publication_repair_execution=repair_execution,
    )

    blockers = review_publish._repair_state_final_blockers(review)

    assert any("pending publication repair action" in item for item in blockers)
    assert any("blocked publication repair action" in item for item in blockers)
    assert any("repair plan blocker" in item for item in blockers)
    assert any("stale relative to the current repair plan" in item for item in blockers)
    assert any("incomplete action results" in item for item in blockers)
    assert any("missing expected outputs" in item for item in blockers)
    assert any("did not complete successfully" in item for item in blockers)


def test_repair_plan_classifies_final_asset_gaps_as_auto_repairable() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    evidence_index = AutoResearchPublicationEvidenceIndexRead(
        generated_at=now,
        project_id="project_repair_asset_kind",
        run_id="run_repair_asset_kind",
        evidence_item_count=2,
        required_evidence_count=2,
        present_required_evidence_count=0,
        missing_required_evidence_count=2,
        blockers=[
            "Missing final publish asset: run_generated_code.",
            "Missing final publish asset: run_paper_build_script.",
        ],
        complete=False,
        evidence_index_fingerprint="asset-kind-evidence",
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=evidence_index.project_id,
        run_id=evidence_index.run_id,
        generated_at=now,
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Repair asset kind regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        publication_evidence_index=evidence_index,
    )

    repair_plan = review_publish.build_publication_repair_plan(
        review=review,
        review_loop=None,
    )

    assert repair_plan.pending_action_count == 2
    assert repair_plan.blocked_action_count == 0
    assert any(action.kind == "rerun_experiments" for action in repair_plan.actions)
    assert any(action.kind == "rebuild_paper_sources" for action in repair_plan.actions)


def test_repair_plan_includes_artifact_integrity_blockers() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    issue = AutoResearchArtifactIntegrityIssueRead(
        issue_id="lineage_missing_program",
        severity="error",
        category="lineage",
        summary="Existing selected run asset is missing lineage.",
        detail="Asset run_repair_integrity:program_json exists but no lineage edge targets it.",
        asset_id="run_repair_integrity:program_json",
        role="program_json",
        path="/tmp/program.json",
    )
    artifact_integrity_audit = AutoResearchArtifactIntegrityAuditRead(
        generated_at=now,
        project_id="project_repair_integrity",
        run_id="run_repair_integrity",
        registry_asset_count=4,
        existing_registry_asset_count=4,
        bundle_count=1,
        selected_bundle_asset_count=4,
        lineage_edge_count=1,
        missing_lineage_target_count=0,
        untraced_existing_asset_count=1,
        issue_count=1,
        blocker_count=1,
        issues=[issue],
        blockers=[issue.summary],
        complete=False,
        audit_fingerprint="artifact-integrity-blocker",
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=artifact_integrity_audit.project_id,
        run_id=artifact_integrity_audit.run_id,
        generated_at=now,
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Artifact integrity repair plan regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        artifact_integrity_audit=artifact_integrity_audit,
    )

    repair_plan = review_publish.build_publication_repair_plan(
        review=review,
        review_loop=None,
    )

    action = next(
        item for item in repair_plan.actions if item.source == "artifact_integrity_audit"
    )
    assert action.source_ids == [issue.issue_id]
    assert action.supporting_asset_ids == [issue.asset_id]
    assert action.priority == "high"
    assert action.status == "blocked"
    assert action.kind == "manual_review"


def test_artifact_integrity_requires_matching_lineage_target_kind(tmp_path: Path) -> None:
    run_id = "run_lineage_kind_audit"
    root = tmp_path / "run"
    root.mkdir()
    run_path = root / "run.json"
    program_path = root / "program.json"
    run_path.write_text("{}", encoding="utf-8")
    program_path.write_text("{}", encoding="utf-8")
    program_ref = AutoResearchRegistryAssetRef(
        path=str(program_path),
        exists=True,
        sha256=hashlib.sha256(program_path.read_bytes()).hexdigest(),
    )
    registry = AutoResearchRunRegistryRead(
        project_id="project_lineage_kind_audit",
        run_id=run_id,
        topic="Lineage target kind audit",
        status="done",
        root_path=str(root),
        files=AutoResearchRunRegistryFiles(
            root=AutoResearchRegistryAssetRef(
                path=str(root),
                kind="directory",
                exists=True,
            ),
            run_json=AutoResearchRegistryAssetRef(
                path=str(run_path),
                exists=True,
                sha256=hashlib.sha256(run_path.read_bytes()).hexdigest(),
            ),
            program_json=program_ref,
        ),
        lineage=AutoResearchRunLineageRead(
            edges=[
                AutoResearchLineageEdgeRead(
                    source_kind="run",
                    source_id=run_id,
                    relation="has_asset",
                    target_kind="artifact",
                    target_id=f"{run_id}:program_json",
                    target_path=str(program_path),
                    exists=True,
                )
            ]
        ),
    )
    bundle_index = review_publish.AutoResearchBundleIndexRead(
        project_id=registry.project_id,
        run_id=registry.run_id,
        bundles=[
            review_publish.AutoResearchBundleRead(
                id="selected_candidate_repro",
                name="Selected Candidate Repro Bundle",
                description="Regression bundle.",
                asset_count=1,
                existing_asset_count=1,
                assets=[
                    review_publish.AutoResearchBundleAssetRead(
                        asset_id=f"{run_id}:program_json",
                        label="Program snapshot",
                        role="program_json",
                        ref=program_ref,
                    )
                ],
            )
        ],
    )

    audit = artifact_integrity_audit.build_artifact_integrity_audit(
        registry=registry,
        bundle_index=bundle_index,
    )

    assert any(
        issue.category == "lineage"
        and issue.asset_id == f"{run_id}:program_json"
        and issue.severity == "error"
        for issue in audit.issues
    )


def test_artifact_integrity_detects_stale_registry_checksum(tmp_path: Path) -> None:
    run_id = "run_registry_checksum_audit"
    root = tmp_path / "run"
    root.mkdir()
    run_path = root / "run.json"
    program_path = root / "program.json"
    run_path.write_text("{}", encoding="utf-8")
    program_path.write_text('{"version": 2}', encoding="utf-8")
    stale_program_ref = AutoResearchRegistryAssetRef(
        path=str(program_path),
        exists=True,
        sha256="0" * 64,
    )
    registry = AutoResearchRunRegistryRead(
        project_id="project_registry_checksum_audit",
        run_id=run_id,
        topic="Registry checksum audit",
        status="done",
        root_path=str(root),
        files=AutoResearchRunRegistryFiles(
            root=AutoResearchRegistryAssetRef(
                path=str(root),
                kind="directory",
                exists=True,
            ),
            run_json=AutoResearchRegistryAssetRef(
                path=str(run_path),
                exists=True,
                sha256=hashlib.sha256(run_path.read_bytes()).hexdigest(),
            ),
            program_json=stale_program_ref,
        ),
        lineage=AutoResearchRunLineageRead(
            edges=[
                AutoResearchLineageEdgeRead(
                    source_kind="run",
                    source_id=run_id,
                    relation="has_asset",
                    target_kind="program",
                    target_id=f"{run_id}:program",
                    target_path=str(program_path),
                    exists=True,
                )
            ]
        ),
    )
    bundle_index = review_publish.AutoResearchBundleIndexRead(
        project_id=registry.project_id,
        run_id=registry.run_id,
        bundles=[
            review_publish.AutoResearchBundleRead(
                id="selected_candidate_repro",
                name="Selected Candidate Repro Bundle",
                description="Regression bundle.",
                asset_count=1,
                existing_asset_count=1,
                assets=[
                    review_publish.AutoResearchBundleAssetRead(
                        asset_id=f"{run_id}:program_json",
                        label="Program snapshot",
                        role="program_json",
                        ref=stale_program_ref,
                    )
                ],
            )
        ],
    )

    audit = artifact_integrity_audit.build_artifact_integrity_audit(
        registry=registry,
        bundle_index=bundle_index,
    )

    assert audit.complete is False
    assert any(
        issue.category == "registry"
        and issue.summary == "Registry file checksum is stale."
        and issue.severity == "error"
        and issue.path == str(program_path)
        for issue in audit.issues
    )


def test_artifact_integrity_detects_unregistered_selected_bundle_asset(
    tmp_path: Path,
) -> None:
    run_id = "run_unregistered_bundle_asset"
    root = tmp_path / "run"
    root.mkdir()
    run_path = root / "run.json"
    external_path = tmp_path / "external_candidate.py"
    run_path.write_text("{}", encoding="utf-8")
    external_path.write_text("print('unregistered')\n", encoding="utf-8")
    unregistered_ref = AutoResearchRegistryAssetRef(
        path=str(external_path),
        exists=True,
        size_bytes=external_path.stat().st_size,
        sha256=hashlib.sha256(external_path.read_bytes()).hexdigest(),
    )
    registry = AutoResearchRunRegistryRead(
        project_id="project_unregistered_bundle_asset",
        run_id=run_id,
        topic="Unregistered bundle asset audit",
        status="done",
        root_path=str(root),
        files=AutoResearchRunRegistryFiles(
            root=AutoResearchRegistryAssetRef(
                path=str(root),
                kind="directory",
                exists=True,
            ),
            run_json=AutoResearchRegistryAssetRef(
                path=str(run_path),
                exists=True,
                sha256=hashlib.sha256(run_path.read_bytes()).hexdigest(),
            ),
        ),
        lineage=AutoResearchRunLineageRead(),
    )
    bundle_index = review_publish.AutoResearchBundleIndexRead(
        project_id=registry.project_id,
        run_id=registry.run_id,
        bundles=[
            review_publish.AutoResearchBundleRead(
                id="selected_candidate_repro",
                name="Selected Candidate Repro Bundle",
                description="Regression bundle.",
                asset_count=1,
                existing_asset_count=1,
                assets=[
                    review_publish.AutoResearchBundleAssetRead(
                        asset_id=f"{run_id}:run_generated_code",
                        label="Generated code",
                        role="run_generated_code",
                        ref=unregistered_ref,
                    )
                ],
            )
        ],
    )

    audit = artifact_integrity_audit.build_artifact_integrity_audit(
        registry=registry,
        bundle_index=bundle_index,
    )

    assert audit.complete is False
    assert any(
        issue.category == "bundle"
        and issue.summary == "Selected bundle asset is not backed by the registry."
        and issue.severity == "error"
        and issue.asset_id == f"{run_id}:run_generated_code"
        for issue in audit.issues
    )


def test_publish_package_blocks_unresolved_repair_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    now = datetime.now(UTC).replace(tzinfo=None)
    project_id = "project_package_repair_state_gate"
    run_id = "run_package_repair_state_gate"
    repair_plan = AutoResearchPublicationRepairPlanRead(
        generated_at=now,
        project_id=project_id,
        run_id=run_id,
        action_count=1,
        pending_action_count=1,
        auto_applicable_action_count=1,
        next_action_ids=["repair_claims"],
        actions=[
            AutoResearchPublicationRepairActionRead(
                action_id="repair_claims",
                kind="repair_claim_evidence",
                source="readiness",
                priority="high",
                title="Repair claim evidence",
                detail="Refresh claim-evidence support.",
                auto_applicable=True,
                expected_outputs=["run_claim_evidence_matrix_json"],
            )
        ],
        repair_plan_fingerprint="package-repair-plan",
    )
    evidence_index = AutoResearchPublicationEvidenceIndexRead(
        generated_at=now,
        project_id=project_id,
        run_id=run_id,
        evidence_item_count=0,
        required_evidence_count=0,
        present_required_evidence_count=0,
        missing_required_evidence_count=0,
        complete=True,
        evidence_index_fingerprint="package-evidence-index",
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Package repair state gate regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        publication_evidence_index=evidence_index,
        publication_repair_plan=repair_plan,
    )
    bundle = review_publish.AutoResearchBundleRead(
        id="selected_candidate_repro",
        name="Selected candidate",
        description="Regression bundle.",
        asset_count=1,
        existing_asset_count=1,
        assets=[
            review_publish.AutoResearchBundleAssetRead(
                asset_id="run_json",
                label="Run",
                role="run_json",
                required=True,
                ref=AutoResearchRegistryAssetRef(
                    path=str(tmp_path / "run.json"),
                    exists=True,
                    sha256="run-json",
                ),
            )
        ],
    )
    review_loop = review_publish.AutoResearchReviewLoopRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        current_round=1,
        overall_status="ready",
        unsupported_claim_risk="low",
        latest_review_fingerprint="review-fingerprint",
    )
    run = AutoResearchRunRead(
        id=run_id,
        project_id=project_id,
        topic="Package repair state gate",
        status="done",
        task_family="text_classification",
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(review_publish, "build_run_review", lambda *_args: review)
    monkeypatch.setattr(
        review_publish,
        "load_run_bundle_index",
        lambda *_args: review_publish.AutoResearchBundleIndexRead(
            project_id=project_id,
            run_id=run_id,
            bundles=[bundle],
        ),
    )
    monkeypatch.setattr(review_publish, "load_run", lambda *_args: run)
    monkeypatch.setattr(review_publish, "_load_review_loop", lambda *_args: review_loop)
    monkeypatch.setattr(review_publish, "_compile_ready_final_blockers", lambda *_args: [])

    package = review_publish.build_publish_package(project_id, run_id)

    assert package is not None
    assert package.status == "blocked"
    assert package.final_publish_ready is False
    assert any(
        "pending publication repair action" in item
        for item in package.final_blockers
    )


def test_publish_package_materializes_submission_assets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    now = datetime.now(UTC).replace(tzinfo=None)
    project_id = "project_submission_assets"
    run_id = "run_submission_assets"
    run_root = autoresearch_repository.run_dir(project_id, run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    paper_path = run_root / "paper.md"
    paper_path.write_text("# Submission Asset Paper\n\nGrounded result.\n", encoding="utf-8")
    run_json_path = run_root / "run.json"
    run_json_path.write_text("{}", encoding="utf-8")
    claim_matrix_path = run_root / "claim_evidence_matrix.json"
    claim_matrix = AutoResearchClaimEvidenceMatrixRead(
        generated_at=now,
        claim_count=1,
        supported_claim_count=1,
        entries=[
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_result_summary",
                category="result",
                section_hint="Results",
                claim="The candidate improves the primary metric on the retained artifact.",
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Selected artifact",
                        detail="Objective score is preserved in the run artifact.",
                    )
                ],
            )
        ],
    )
    claim_matrix_path.write_text(claim_matrix.model_dump_json(indent=2), encoding="utf-8")
    evidence_ledger_path = run_root / "evidence_ledger.json"
    evidence_ledger = AutoResearchEvidenceLedgerRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        entries=[
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id="evidence_retrieval_claim_result_summary",
                source_job_id="job_candidate_method",
                evidence_kind="artifact",
                claim="Cached claim-evidence retrieval attached ranked evidence for the result claim.",
                artifact_ref="run_artifact_json",
                support_status="supported",
            )
        ],
        entry_count=1,
        complete=True,
        ledger_fingerprint="submission-assets-ledger",
    )
    evidence_ledger_path.write_text(evidence_ledger.model_dump_json(indent=2), encoding="utf-8")
    run = AutoResearchRunRead(
        id=run_id,
        project_id=project_id,
        topic="Submission package assets",
        status="done",
        task_family="text_classification",
        created_at=now,
        updated_at=now,
        paper_path=str(paper_path),
        paper_markdown=paper_path.read_text(encoding="utf-8"),
        claim_evidence_matrix=claim_matrix,
        claim_evidence_matrix_path=str(claim_matrix_path),
        evidence_ledger=evidence_ledger,
        evidence_ledger_path=str(evidence_ledger_path),
    )
    evidence_index_path = run_root / "publication_evidence_index.json"
    evidence_index = AutoResearchPublicationEvidenceIndexRead(
        generated_at=now,
        project_id=project_id,
        run_id=run_id,
        evidence_item_count=1,
        required_evidence_count=1,
        present_required_evidence_count=1,
        complete=True,
        evidence_index_fingerprint="submission-assets-evidence",
    )
    evidence_index_path.write_text(evidence_index.model_dump_json(indent=2), encoding="utf-8")
    review = review_publish.AutoResearchRunReviewRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        overall_status="needs_revision",
        unsupported_claim_risk="medium",
        summary="Submission asset regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        findings=[
            review_publish.AutoResearchReviewFindingRead(
                id="finding_1",
                severity="warning",
                category="citation",
                summary="Paper text does not include citation markers.",
                detail="Add citation support before final publication.",
            )
        ],
        publication_evidence_index=evidence_index,
        publication_evidence_index_path=str(evidence_index_path),
    )
    review_loop = review_publish.AutoResearchReviewLoopRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        current_round=1,
        latest_review_fingerprint="submission-assets-review",
        pending_action_count=1,
        pending_revision_actions=["Add citation support"],
    )
    asset = review_publish.AutoResearchBundleAssetRead(
        asset_id=f"{run_id}:run_paper_markdown",
        label="Paper",
        role="run_paper_markdown",
        required=True,
        ref=AutoResearchRegistryAssetRef(
            path=str(paper_path),
            exists=True,
            size_bytes=paper_path.stat().st_size,
            sha256=hashlib.sha256(paper_path.read_bytes()).hexdigest(),
        ),
    )
    bundle = review_publish.AutoResearchBundleRead(
        id="selected_candidate_repro",
        name="Selected Candidate Repro Bundle",
        description="Submission asset bundle.",
        asset_count=1,
        existing_asset_count=1,
        assets=[asset],
    )
    registry = AutoResearchRunRegistryRead(
        project_id=project_id,
        run_id=run_id,
        topic=run.topic,
        status=run.status,
        root_path=str(run_root),
        files=AutoResearchRunRegistryFiles(
            root=AutoResearchRegistryAssetRef(path=str(run_root), kind="directory", exists=True),
            run_json=AutoResearchRegistryAssetRef(path=str(run_json_path), exists=True),
        ),
        lineage=AutoResearchRunLineageRead(
            selected_candidate_id="candidate_1",
            edges=[
                AutoResearchLineageEdgeRead(
                    source_kind="artifact",
                    source_id=f"{run_id}:artifact",
                    relation="derived_from",
                    target_kind="paper",
                    target_id=f"{run_id}:paper",
                    target_path=str(paper_path),
                    exists=True,
                )
            ],
        ),
    )
    monkeypatch.setattr(review_publish, "build_run_review", lambda *_args, **_kwargs: review)
    monkeypatch.setattr(review_publish, "load_run", lambda *_args: run)
    monkeypatch.setattr(review_publish, "_load_review_loop", lambda *_args: review_loop)
    monkeypatch.setattr(review_publish, "load_run_registry", lambda *_args: registry)
    monkeypatch.setattr(
        review_publish,
        "load_run_bundle_index",
        lambda *_args: review_publish.AutoResearchBundleIndexRead(
            project_id=project_id,
            run_id=run_id,
            bundles=[bundle],
        ),
    )

    package = review_publish.build_publish_package(project_id, run_id)

    assert package is not None
    assert package.submission_asset_count == 5
    assert package.submission_ready is False
    assert package.claim_evidence_index_complete is True
    assert package.reviewer_response_complete is True
    assert package.lineage_archive_complete is True
    checklist_path = Path(package.reproducibility_checklist_path)
    response_path = Path(package.reviewer_response_path)
    claim_index_path = Path(package.claim_evidence_index_path)
    lineage_archive_path = Path(package.lineage_archive_path)
    submission_manifest_path = Path(package.submission_manifest_path)
    assert checklist_path.is_file()
    assert response_path.is_file()
    assert claim_index_path.is_file()
    assert lineage_archive_path.is_file()
    assert submission_manifest_path.is_file()
    assert "Reproducibility Checklist" in checklist_path.read_text(encoding="utf-8")
    assert "Reviewer Response" in response_path.read_text(encoding="utf-8")
    claim_index_text = claim_index_path.read_text(encoding="utf-8")
    assert "claim_result_summary" in claim_index_text
    assert "Experiment Evidence Ledger" in claim_index_text
    assert "evidence_retrieval_claim_result_summary" in claim_index_text
    lineage_payload = json.loads(lineage_archive_path.read_text(encoding="utf-8"))
    assert lineage_payload["lineage_edge_count"] == 1
    submission_payload = json.loads(submission_manifest_path.read_text(encoding="utf-8"))
    assert submission_payload["final_blocker_count"] == package.final_blocker_count
    assert {item["role"] for item in submission_payload["generated_assets"]} == {
        "reproducibility_checklist",
        "reviewer_response",
        "claim_evidence_index",
        "lineage_archive",
    }
    generated_names = {
        path.name
        for path in review_publish._publish_generated_paths(project_id, run_id)
    }
    assert {
        review_publish.SUBMISSION_MANIFEST_FILENAME,
        review_publish.REPRODUCIBILITY_CHECKLIST_FILENAME,
        review_publish.REVIEWER_RESPONSE_FILENAME,
        review_publish.CLAIM_EVIDENCE_INDEX_FILENAME,
        review_publish.LINEAGE_ARCHIVE_FILENAME,
    }.issubset(generated_names)


def test_claim_evidence_index_accepts_retrieval_evidence_ledger_without_matrix() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    run = AutoResearchRunRead(
        id="run_ledger_only_claim_index",
        project_id="project_ledger_only_claim_index",
        topic="Ledger-only claim evidence index",
        status="done",
        task_family="ir_reranking",
        created_at=now,
        updated_at=now,
        evidence_ledger=AutoResearchEvidenceLedgerRead(
            project_id="project_ledger_only_claim_index",
            run_id="run_ledger_only_claim_index",
            generated_at=now,
            entries=[
                AutoResearchEvidenceLedgerEntryRead(
                    evidence_id="evidence_retrieval_claim_support",
                    source_job_id="job_candidate_method",
                    evidence_kind="artifact",
                    claim="Cached retrieval supports the selected scientific writing claim.",
                    artifact_ref="run_artifact_json",
                    support_status="supported",
                )
            ],
            entry_count=1,
            complete=True,
            ledger_fingerprint="ledger-only-claim-index",
        ),
        evidence_ledger_path="/tmp/evidence_ledger.json",
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=run.project_id,
        run_id=run.id,
        generated_at=now,
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Ledger-only claim evidence index regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        publication_evidence_index=AutoResearchPublicationEvidenceIndexRead(
            generated_at=now,
            project_id=run.project_id,
            run_id=run.id,
            complete=True,
            evidence_index_fingerprint="ledger-only-publication-index",
        ),
        publication_evidence_index_path="/tmp/publication_evidence_index.json",
    )
    package = AutoResearchPublishPackageRead(
        project_id=run.project_id,
        run_id=run.id,
        package_id="ledger_only_package",
        generated_at=now,
    )

    markdown, complete = review_publish._build_claim_evidence_index_markdown(
        run=run,
        review=review,
        package=package,
    )

    assert complete is True
    assert "No claim-evidence matrix entries were available" in markdown
    assert "Experiment Evidence Ledger" in markdown
    assert "evidence_retrieval_claim_support" in markdown


def test_publish_package_marks_archive_stale_when_asset_digest_changes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    now = datetime.now(UTC).replace(tzinfo=None)
    project_id = "project_archive_digest_stale"
    run_id = "run_archive_digest_stale"
    run = AutoResearchRunRead(
        id=run_id,
        project_id=project_id,
        topic="Archive digest stale regression",
        status="done",
        created_at=now,
        updated_at=now,
    )
    evidence_index = AutoResearchPublicationEvidenceIndexRead(
        generated_at=now,
        project_id=project_id,
        run_id=run_id,
        evidence_item_count=0,
        required_evidence_count=0,
        present_required_evidence_count=0,
        missing_required_evidence_count=0,
        complete=True,
        evidence_index_fingerprint="archive-digest-evidence",
    )
    artifact_audit = AutoResearchArtifactIntegrityAuditRead(
        generated_at=now,
        project_id=project_id,
        run_id=run_id,
        registry_asset_count=1,
        existing_registry_asset_count=1,
        bundle_count=1,
        selected_bundle_asset_count=1,
        complete=True,
        audit_fingerprint="archive-digest-integrity",
    )
    repair_plan = AutoResearchPublicationRepairPlanRead(
        generated_at=now,
        project_id=project_id,
        run_id=run_id,
        complete=True,
        repair_plan_fingerprint="archive-digest-repair-plan",
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Archive digest stale regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        publication_evidence_index=evidence_index,
        artifact_integrity_audit=artifact_audit,
        publication_repair_plan=repair_plan,
    )
    review_loop = review_publish.AutoResearchReviewLoopRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        current_round=1,
        latest_review_fingerprint="archive-digest-review",
    )
    current_sha = "old-digest"

    def bundle_index_for_current_sha() -> review_publish.AutoResearchBundleIndexRead:
        asset = review_publish.AutoResearchBundleAssetRead(
            asset_id=f"{run_id}:run_generated_code",
            label="Generated code",
            role="run_generated_code",
            required=True,
            ref=AutoResearchRegistryAssetRef(
                path=str(tmp_path / "generated_code.py"),
                exists=True,
                size_bytes=12,
                sha256=current_sha,
            ),
        )
        bundle = review_publish.AutoResearchBundleRead(
            id="selected_candidate_repro",
            name="Selected candidate",
            description="Regression bundle.",
            asset_count=1,
            existing_asset_count=1,
            assets=[asset],
        )
        return review_publish.AutoResearchBundleIndexRead(
            project_id=project_id,
            run_id=run_id,
            bundles=[bundle],
        )

    monkeypatch.setattr(review_publish, "build_run_review", lambda *_args, **_kwargs: review)
    monkeypatch.setattr(review_publish, "load_run", lambda *_args: run)
    monkeypatch.setattr(review_publish, "_load_review_loop", lambda *_args: review_loop)
    monkeypatch.setattr(review_publish, "_compile_ready_final_blockers", lambda *_args: [])
    monkeypatch.setattr(
        review_publish,
        "load_run_bundle_index",
        lambda *_args: bundle_index_for_current_sha(),
    )

    initial_package = review_publish.build_publish_package(project_id, run_id)
    assert initial_package is not None
    archive_manifest_path = review_publish._publish_archive_manifest_path(project_id, run_id)
    archive_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    archive_manifest_path.write_text(
        json.dumps(
            {
                "generated_at": now.isoformat(),
                "bundle_kind": "final_publish_bundle",
                "package_fingerprint": initial_package.package_fingerprint,
                "review_round": initial_package.review_round,
                "review_fingerprint": initial_package.review_fingerprint,
            }
        ),
        encoding="utf-8",
    )
    review_publish._publish_archive_path(project_id, run_id).write_bytes(b"old archive")
    stale_publication_manifest = review_publish.AutoResearchPublicationManifestRead(
        publication_id=f"publication_{run_id}",
        project_id=project_id,
        run_id=run_id,
        topic="Archive digest stale regression.",
        paper_title="Archive digest stale regression.",
        generated_at=now,
        updated_at=now,
        package_id=initial_package.package_id,
        package_fingerprint=initial_package.package_fingerprint,
        bundle_kind="final_publish_bundle",
        review_bundle_ready=True,
        final_publish_ready=True,
        publication_manifest_path=str(review_publish._publication_manifest_path(project_id, run_id)),
        publish_manifest_path=str(review_publish._publish_manifest_path(project_id, run_id)),
        publish_archive_path=str(review_publish._publish_archive_path(project_id, run_id)),
        run_api_path=f"/api/projects/{project_id}/auto-research/{run_id}",
        registry_api_path=f"/api/projects/{project_id}/auto-research/{run_id}/registry",
        publish_api_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish",
        publish_download_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish/download",
        deployments=[
            review_publish.AutoResearchDeploymentRefRead(
                deployment_id="stale_live",
                label="Stale Live",
                listed_at=now,
            )
        ],
    )
    review_publish._publication_manifest_path(project_id, run_id).write_text(
        stale_publication_manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    current_sha = "new-digest"

    package = review_publish.build_publish_package(project_id, run_id)

    assert package is not None
    assert package.archive_ready is True
    assert package.archive_current is False
    assert package.archive_status == "stale"
    assert package.publication_id is None
    assert package.deployment_ids == []


def test_publish_package_marks_archive_stale_when_zip_generated_file_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    now = datetime.now(UTC).replace(tzinfo=None)
    project_id = "project_archive_zip_contents"
    run_id = "run_archive_zip_contents"
    run = AutoResearchRunRead(
        id=run_id,
        project_id=project_id,
        topic="Archive zip content integrity",
        status="done",
        created_at=now,
        updated_at=now,
    )
    evidence_index = AutoResearchPublicationEvidenceIndexRead(
        generated_at=now,
        project_id=project_id,
        run_id=run_id,
        complete=True,
        evidence_index_fingerprint="archive-zip-evidence",
    )
    artifact_audit = AutoResearchArtifactIntegrityAuditRead(
        generated_at=now,
        project_id=project_id,
        run_id=run_id,
        registry_asset_count=1,
        existing_registry_asset_count=1,
        bundle_count=1,
        selected_bundle_asset_count=1,
        complete=True,
        audit_fingerprint="archive-zip-integrity",
    )
    repair_plan = AutoResearchPublicationRepairPlanRead(
        generated_at=now,
        project_id=project_id,
        run_id=run_id,
        complete=True,
        repair_plan_fingerprint="archive-zip-repair-plan",
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        overall_status="ready",
        unsupported_claim_risk="low",
        summary="Archive zip content regression.",
        evidence=review_publish.AutoResearchReviewEvidenceRead(),
        citation_coverage=review_publish.AutoResearchCitationCoverageRead(),
        scores=review_publish.AutoResearchReviewScoresRead(),
        publication_evidence_index=evidence_index,
        artifact_integrity_audit=artifact_audit,
        publication_repair_plan=repair_plan,
    )
    review_loop = review_publish.AutoResearchReviewLoopRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=now,
        current_round=1,
        latest_review_fingerprint="archive-zip-review",
    )
    code_path = tmp_path / "generated_code.py"
    code_path.write_text("print('stable')\n", encoding="utf-8")
    code_sha = hashlib.sha256(code_path.read_bytes()).hexdigest()
    asset = review_publish.AutoResearchBundleAssetRead(
        asset_id=f"{run_id}:run_generated_code",
        label="Generated code",
        role="run_generated_code",
        required=True,
        ref=AutoResearchRegistryAssetRef(
            path=str(code_path),
            exists=True,
            size_bytes=code_path.stat().st_size,
            sha256=code_sha,
        ),
    )
    bundle = review_publish.AutoResearchBundleRead(
        id="selected_candidate_repro",
        name="Selected Candidate Repro Bundle",
        description="Regression bundle.",
        asset_count=1,
        existing_asset_count=1,
        assets=[asset],
    )
    bundle_index = review_publish.AutoResearchBundleIndexRead(
        project_id=project_id,
        run_id=run_id,
        bundles=[bundle],
    )
    monkeypatch.setattr(review_publish, "build_run_review", lambda *_args, **_kwargs: review)
    monkeypatch.setattr(review_publish, "load_run", lambda *_args: run)
    monkeypatch.setattr(review_publish, "_load_review_loop", lambda *_args: review_loop)
    monkeypatch.setattr(review_publish, "_compile_ready_final_blockers", lambda *_args: [])
    monkeypatch.setattr(review_publish, "load_run_bundle_index", lambda *_args: bundle_index)

    initial_package = review_publish.build_publish_package(project_id, run_id)
    assert initial_package is not None
    publication_manifest_path = review_publish._publication_manifest_path(project_id, run_id)
    publication_manifest_path.write_text('{"publication_id":"stale"}', encoding="utf-8")
    code_package_path = review_publish._code_package_path(project_id, run_id)
    code_package_path.write_bytes(b"code package")
    archive_manifest = {
        "generated_at": now.isoformat(),
        "bundle_kind": "final_publish_bundle",
        "package_fingerprint": initial_package.package_fingerprint,
        "review_round": initial_package.review_round,
        "review_fingerprint": initial_package.review_fingerprint,
        "generated_file_refs": [
            {
                "file_name": review_publish.PUBLICATION_MANIFEST_FILENAME,
                "path": str(publication_manifest_path),
                "exists": True,
                "digest_tracked": True,
                "size_bytes": publication_manifest_path.stat().st_size,
                "sha256": hashlib.sha256(
                    publication_manifest_path.read_bytes()
                ).hexdigest(),
            },
            {
                "file_name": review_publish.CODE_PACKAGE_FILENAME,
                "path": str(code_package_path),
                "exists": True,
                "digest_tracked": True,
                "size_bytes": code_package_path.stat().st_size,
                "sha256": hashlib.sha256(
                    code_package_path.read_bytes()
                ).hexdigest(),
            },
        ],
    }
    archive_manifest_path = review_publish._publish_archive_manifest_path(project_id, run_id)
    archive_manifest_path.write_text(json.dumps(archive_manifest), encoding="utf-8")
    with ZipFile(review_publish._publish_archive_path(project_id, run_id), "w") as archive:
        archive.write(
            publication_manifest_path,
            arcname=review_publish.PUBLICATION_MANIFEST_FILENAME,
        )

    package = review_publish.build_publish_package(project_id, run_id)

    assert package is not None
    assert package.archive_ready is True
    assert package.archive_current is False
    assert package.archive_status == "stale"


def test_publication_manifest_requires_current_archive(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    now = datetime.now(UTC).replace(tzinfo=None)
    project_id = "project_manifest_current_archive"
    run_id = "run_manifest_current_archive"
    run = AutoResearchRunRead(
        id=run_id,
        project_id=project_id,
        topic="Manifest current archive gate",
        status="done",
        created_at=now,
        updated_at=now,
    )
    autoresearch_repository.save_run(run)
    package = AutoResearchPublishPackageRead(
        project_id=project_id,
        run_id=run_id,
        package_id="publish_ready_bundle",
        generated_at=now,
        status="publish_ready",
        publish_ready=True,
        review_bundle_ready=True,
        final_publish_ready=True,
        archive_ready=True,
        archive_current=False,
        archive_status="stale",
        package_fingerprint="stale-package-fingerprint",
    )
    monkeypatch.setattr(
        review_publish,
        "build_publish_package",
        lambda current_project_id, current_run_id: package,
    )

    manifest = review_publish.build_publication_manifest(project_id, run_id)

    assert manifest is None


def test_publication_readiness_is_persisted_registered_and_packaged(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    spec, benchmark = _external_publication_spec()
    project_id = "project_publication_readiness_registry"
    run_id = "run_publication_readiness_registry"
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
    ).model_copy(
        update={
            "id": run_id,
            "project_id": project_id,
            "paper_latex_source": "\\documentclass{article}\\begin{document}Ready\\end{document}",
            "paper_bibliography_bib": "@article{ready2026,title={Ready},author={A},year={2026}}",
        }
    )
    autoresearch_repository.save_run(run)

    readiness_path = Path(
        autoresearch_repository.publication_readiness_file_path(project_id, run_id)
    )
    contribution_assessment_path = Path(
        autoresearch_repository.contribution_assessment_file_path(project_id, run_id)
    )
    experiment_design_path = Path(
        autoresearch_repository.experiment_design_file_path(project_id, run_id)
    )
    failure_analysis_path = Path(
        autoresearch_repository.failure_analysis_file_path(project_id, run_id)
    )
    research_replan_path = Path(
        autoresearch_repository.research_replan_file_path(project_id, run_id)
    )
    literature_graph_path = Path(
        autoresearch_repository.literature_graph_file_path(project_id, run_id)
    )
    novelty_validation_path = Path(
        autoresearch_repository.novelty_validation_file_path(project_id, run_id)
    )
    benchmark_card_path = Path(
        autoresearch_repository.benchmark_card_file_path(project_id, run_id)
    )
    protocol_path = Path(
        autoresearch_repository.research_protocol_file_path(project_id, run_id)
    )
    audit_path = Path(
        autoresearch_repository.methodology_audit_file_path(project_id, run_id)
    )
    dossier_path = Path(
        autoresearch_repository.revision_dossier_file_path(project_id, run_id)
    )
    evidence_index_path = Path(
        autoresearch_repository.publication_evidence_index_file_path(project_id, run_id)
    )
    artifact_integrity_audit_path = Path(
        autoresearch_repository.artifact_integrity_audit_file_path(project_id, run_id)
    )
    repair_plan_path = Path(
        autoresearch_repository.publication_repair_plan_file_path(project_id, run_id)
    )
    repair_execution_path = Path(
        autoresearch_repository.publication_repair_execution_file_path(project_id, run_id)
    )
    assert not readiness_path.is_file()
    assert not contribution_assessment_path.is_file()
    assert not experiment_design_path.is_file()
    assert not failure_analysis_path.is_file()
    assert not research_replan_path.is_file()
    assert not literature_graph_path.is_file()
    assert not novelty_validation_path.is_file()
    assert not benchmark_card_path.is_file()
    assert not protocol_path.is_file()
    assert not audit_path.is_file()
    assert not dossier_path.is_file()
    assert not evidence_index_path.is_file()
    assert not artifact_integrity_audit_path.is_file()
    assert not repair_plan_path.is_file()
    assert not repair_execution_path.is_file()

    review = review_publish.build_run_review(project_id, run_id)

    assert review is not None
    assert review.benchmark_card is not None
    assert review.benchmark_card_path == str(benchmark_card_path)
    assert benchmark_card_path.is_file()
    benchmark_card_payload = json.loads(benchmark_card_path.read_text(encoding="utf-8"))
    assert benchmark_card_payload["publication_grade"] is True
    assert benchmark_card_payload["provenance_complete"] is True
    assert benchmark_card_payload["card_fingerprint"] == review.benchmark_card.card_fingerprint
    assert review.research_protocol is not None
    assert review.research_protocol_path == str(protocol_path)
    assert protocol_path.is_file()
    protocol_payload = json.loads(protocol_path.read_text(encoding="utf-8"))
    assert protocol_payload["complete"] is True
    assert protocol_payload["execution_profile"] == "publication"
    assert protocol_payload["planned_seed_count"] == 5
    assert protocol_payload["minimum_completed_seed_count"] == PUBLICATION_MIN_COMPLETED_SEEDS
    assert protocol_payload["ablation_systems"] == ["candidate_ablation"]
    assert protocol_payload["protocol_fingerprint"] == review.research_protocol.protocol_fingerprint
    assert review.methodology_audit is not None
    assert review.methodology_audit_path == str(audit_path)
    assert audit_path.is_file()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit_payload["compliant"] is True
    assert audit_payload["protocol_fingerprint"] == review.research_protocol.protocol_fingerprint
    assert audit_payload["audit_fingerprint"] == review.methodology_audit.audit_fingerprint
    assert audit_payload["completed_seed_count"] == 5
    assert audit_payload["observed_ablation_systems"] == ["candidate_ablation"]
    assert set(audit_payload["required_statistics"]) == {"mean", "std", "confidence_interval"}
    assert review.revision_dossier is not None
    assert review.revision_dossier_path == str(dossier_path)
    assert dossier_path.is_file()
    dossier_payload = json.loads(dossier_path.read_text(encoding="utf-8"))
    assert dossier_payload["dossier_fingerprint"] == review.revision_dossier.dossier_fingerprint
    assert dossier_payload["review_fingerprint"] is not None
    assert dossier_payload["items"]
    assert review.publication_evidence_index is not None
    assert review.publication_evidence_index_path == str(evidence_index_path)
    assert evidence_index_path.is_file()
    evidence_index_payload = json.loads(evidence_index_path.read_text(encoding="utf-8"))
    assert evidence_index_payload["complete"] is False
    assert evidence_index_payload["missing_required_evidence_count"] > 0
    assert evidence_index_payload["evidence_index_fingerprint"] == (
        review.publication_evidence_index.evidence_index_fingerprint
    )
    assert "paper_build_script" in evidence_index_payload["missing_required_evidence_ids"]
    assert "paper_sources_manifest" in evidence_index_payload["missing_required_evidence_ids"]
    contribution_evidence = next(
        item
        for item in evidence_index_payload["evidence_items"]
        if item["evidence_id"] == "contribution_assessment"
    )
    assert contribution_evidence["exists"] is True
    assert contribution_evidence["role"] == "run_contribution_assessment_json"
    experiment_design_evidence = next(
        item
        for item in evidence_index_payload["evidence_items"]
        if item["evidence_id"] == "experiment_design"
    )
    assert experiment_design_evidence["exists"] is True
    assert experiment_design_evidence["role"] == "run_experiment_design_json"
    failure_analysis_evidence = next(
        item
        for item in evidence_index_payload["evidence_items"]
        if item["evidence_id"] == "failure_analysis"
    )
    assert failure_analysis_evidence["exists"] is True
    assert failure_analysis_evidence["role"] == "run_failure_analysis_json"
    research_replan_evidence = next(
        item
        for item in evidence_index_payload["evidence_items"]
        if item["evidence_id"] == "research_replan"
    )
    assert research_replan_evidence["exists"] is True
    assert research_replan_evidence["role"] == "run_research_replan_json"
    literature_graph_evidence = next(
        item
        for item in evidence_index_payload["evidence_items"]
        if item["evidence_id"] == "literature_graph"
    )
    assert literature_graph_evidence["exists"] is True
    assert literature_graph_evidence["role"] == "run_literature_graph_json"
    novelty_validation_evidence = next(
        item
        for item in evidence_index_payload["evidence_items"]
        if item["evidence_id"] == "novelty_validation"
    )
    assert novelty_validation_evidence["exists"] is True
    assert novelty_validation_evidence["role"] == "run_novelty_validation_json"
    assert review.artifact_integrity_audit is not None
    assert review.artifact_integrity_audit_path == str(artifact_integrity_audit_path)
    assert artifact_integrity_audit_path.is_file()
    artifact_integrity_audit_payload = json.loads(
        artifact_integrity_audit_path.read_text(encoding="utf-8")
    )
    assert artifact_integrity_audit_payload["audit_fingerprint"] == (
        review.artifact_integrity_audit.audit_fingerprint
    )
    assert artifact_integrity_audit_payload["complete"] is False
    assert artifact_integrity_audit_payload["blocker_count"] >= 2
    assert any(
        issue["asset_id"] == f"{run_id}:program_json"
        for issue in artifact_integrity_audit_payload["issues"]
    )
    assert any(
        issue["asset_id"] == f"{run_id}:portfolio_json"
        for issue in artifact_integrity_audit_payload["issues"]
    )
    artifact_integrity_evidence = next(
        item
        for item in evidence_index_payload["evidence_items"]
        if item["evidence_id"] == "artifact_integrity_audit"
    )
    assert artifact_integrity_evidence["exists"] is True
    assert artifact_integrity_evidence["sha256"] == hashlib.sha256(
        artifact_integrity_audit_path.read_bytes()
    ).hexdigest()
    assert review.publication_repair_plan is not None
    assert review.publication_repair_plan_path == str(repair_plan_path)
    assert repair_plan_path.is_file()
    repair_plan_payload = json.loads(repair_plan_path.read_text(encoding="utf-8"))
    assert repair_plan_payload["repair_plan_fingerprint"] == (
        review.publication_repair_plan.repair_plan_fingerprint
    )
    assert repair_plan_payload["action_count"] > 0
    assert repair_plan_payload["pending_action_count"] > 0
    assert any(
        action["source"] == "artifact_integrity_audit"
        for action in repair_plan_payload["actions"]
    )
    assert any(action["source"] == "evidence_index" for action in repair_plan_payload["actions"])
    review_loop = review_publish.build_review_loop(project_id, run_id)
    assert review_loop is not None
    repair_execution = build_publication_repair_execution(
        project_id=project_id,
        run_id=run_id,
        repair_plan=review.publication_repair_plan,
        review_loop_before=review_loop,
        review_loop_after=review_loop,
    )
    repair_execution_path.write_text(
        repair_execution.model_dump_json(indent=2),
        encoding="utf-8",
    )
    review = review_publish.build_run_review(project_id, run_id)
    assert review is not None
    assert review.publication_repair_execution is not None
    assert review.publication_repair_execution_path == str(repair_execution_path)
    assert review.publication_repair_execution.execution_fingerprint == (
        repair_execution.execution_fingerprint
    )
    evidence_ids = {item["evidence_id"] for item in evidence_index_payload["evidence_items"]}
    assert {
        "benchmark_card",
        "research_protocol",
        "methodology_audit",
        "publication_readiness",
        "contribution_assessment",
        "experiment_design",
        "failure_analysis",
        "research_replan",
        "literature_graph",
        "novelty_validation",
        "revision_dossier",
        "artifact_integrity_audit",
        "claim_evidence_matrix",
        "paper_latex_source",
    }.issubset(evidence_ids)
    assert review.publication_readiness is not None
    assert review.publication_readiness_path == str(readiness_path)
    assert readiness_path.is_file()
    readiness_payload = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert readiness_payload["tier"] == review.publication_readiness.tier
    assert readiness_payload["score"] == review.publication_readiness.score
    assert review.contribution_assessment is not None
    assert review.contribution_assessment_path == str(contribution_assessment_path)
    assert contribution_assessment_path.is_file()
    contribution_payload = json.loads(contribution_assessment_path.read_text(encoding="utf-8"))
    assert contribution_payload["complete"] is True
    assert contribution_payload["strong_core_claim_count"] >= 1
    assert contribution_payload["assessment_fingerprint"] == (
        review.contribution_assessment.assessment_fingerprint
    )
    assert review.experiment_design is not None
    assert review.experiment_design_path == str(experiment_design_path)
    assert experiment_design_path.is_file()
    experiment_design_payload = json.loads(experiment_design_path.read_text(encoding="utf-8"))
    assert experiment_design_payload["completeness"] == "complete"
    assert experiment_design_payload["naive_baseline_present"] is True
    assert experiment_design_payload["strong_baseline_present"] is True
    assert experiment_design_payload["design_fingerprint"] == review.experiment_design.design_fingerprint
    assert review.failure_analysis is not None
    assert review.failure_analysis_path == str(failure_analysis_path)
    assert failure_analysis_path.is_file()
    failure_analysis_payload = json.loads(failure_analysis_path.read_text(encoding="utf-8"))
    assert failure_analysis_payload["complete"] is True
    assert failure_analysis_payload["finding_count"] == 0
    assert failure_analysis_payload["analysis_fingerprint"] == review.failure_analysis.analysis_fingerprint
    assert review.research_replan is not None
    assert review.research_replan_path == str(research_replan_path)
    assert research_replan_path.is_file()
    research_replan_payload = json.loads(research_replan_path.read_text(encoding="utf-8"))
    assert research_replan_payload["complete"] is True
    assert research_replan_payload["action_count"] == 0
    assert research_replan_payload["replan_fingerprint"] == review.research_replan.replan_fingerprint
    assert review.literature_graph is not None
    assert review.literature_graph_path == str(literature_graph_path)
    assert literature_graph_path.is_file()
    literature_graph_payload = json.loads(literature_graph_path.read_text(encoding="utf-8"))
    assert literature_graph_payload["real_paper_count"] >= 2
    assert literature_graph_payload["graph_fingerprint"] == review.literature_graph.graph_fingerprint
    assert review.novelty_validation is not None
    assert review.novelty_validation_path == str(novelty_validation_path)
    assert novelty_validation_path.is_file()
    novelty_validation_payload = json.loads(novelty_validation_path.read_text(encoding="utf-8"))
    assert novelty_validation_payload["complete"] is True
    assert novelty_validation_payload["gap_validity"] == "valid"
    assert novelty_validation_payload["validation_fingerprint"] == (
        review.novelty_validation.validation_fingerprint
    )

    registry = autoresearch_repository.load_run_registry(project_id, run_id)
    assert registry is not None
    assert registry.files.benchmark_card_json is not None
    assert registry.files.benchmark_card_json.exists is True
    assert registry.files.research_protocol_json is not None
    assert registry.files.research_protocol_json.exists is True
    assert registry.files.methodology_audit_json is not None
    assert registry.files.methodology_audit_json.exists is True
    assert registry.files.publication_readiness_json is not None
    assert registry.files.publication_readiness_json.exists is True
    assert registry.files.contribution_assessment_json is not None
    assert registry.files.contribution_assessment_json.exists is True
    assert registry.files.experiment_design_json is not None
    assert registry.files.experiment_design_json.exists is True
    assert registry.files.failure_analysis_json is not None
    assert registry.files.failure_analysis_json.exists is True
    assert registry.files.research_replan_json is not None
    assert registry.files.research_replan_json.exists is True
    assert registry.files.literature_graph_json is not None
    assert registry.files.literature_graph_json.exists is True
    assert registry.files.novelty_validation_json is not None
    assert registry.files.novelty_validation_json.exists is True
    assert registry.files.revision_dossier_json is not None
    assert registry.files.revision_dossier_json.exists is True
    assert registry.files.publication_evidence_index_json is not None
    assert registry.files.publication_evidence_index_json.exists is True
    assert registry.files.artifact_integrity_audit_json is not None
    assert registry.files.artifact_integrity_audit_json.exists is True
    assert registry.files.publication_repair_plan_json is not None
    assert registry.files.publication_repair_plan_json.exists is True
    assert registry.files.publication_repair_execution_json is not None
    assert registry.files.publication_repair_execution_json.exists is True
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "research_protocol"
        and edge.target_path == str(protocol_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "research_protocol"
        and edge.source_kind in {"spec", "plan"}
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "benchmark_card"
        and edge.target_path == str(benchmark_card_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "benchmark_card"
        and edge.source_kind in {"spec", "benchmark", "artifact"}
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "methodology_audit"
        and edge.target_path == str(audit_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "methodology_audit"
        and edge.source_kind in {"research_protocol", "artifact", "claim_evidence_matrix"}
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "revision_dossier"
        and edge.target_path == str(dossier_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "revision_dossier"
        and edge.source_kind in {"methodology_audit", "publication_readiness", "claim_evidence_matrix"}
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "publication_evidence_index"
        and edge.target_path == str(evidence_index_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "publication_evidence_index"
        and edge.source_kind in {
            "benchmark_card",
            "research_protocol",
            "methodology_audit",
            "publication_readiness",
            "revision_dossier",
            "claim_evidence_matrix",
        }
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "artifact_integrity_audit"
        and edge.target_path == str(artifact_integrity_audit_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "artifact_integrity_audit"
        and edge.source_kind == "run"
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "publication_repair_plan"
        and edge.target_path == str(repair_plan_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "publication_repair_plan"
        and edge.source_kind in {
            "revision_dossier",
            "publication_evidence_index",
            "publication_readiness",
        }
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "publication_repair_execution"
        and edge.target_path == str(repair_execution_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "publication_repair_execution"
        and edge.source_kind in {"publication_repair_plan", "paper_revision_action_index"}
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "publication_readiness"
        and edge.target_path == str(readiness_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "contribution_assessment"
        and edge.target_path == str(contribution_assessment_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "experiment_design"
        and edge.target_path == str(experiment_design_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "failure_analysis"
        and edge.target_path == str(failure_analysis_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "research_replan"
        and edge.target_path == str(research_replan_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "literature_graph"
        and edge.target_path == str(literature_graph_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "has_asset"
        and edge.target_kind == "novelty_validation"
        and edge.target_path == str(novelty_validation_path)
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "publication_readiness"
        and edge.source_kind in {"artifact", "paper", "claim_evidence_matrix", "paper_compile_report"}
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "contribution_assessment"
        and edge.source_kind in {"artifact", "paper", "claim_evidence_matrix", "publication_readiness"}
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "experiment_design"
        and edge.source_kind in {"spec", "plan", "artifact", "claim_evidence_matrix"}
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "failure_analysis"
        and edge.source_kind in {
            "artifact",
            "experiment_design",
            "publication_readiness",
            "contribution_assessment",
            "novelty_validation",
        }
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "research_replan"
        and edge.source_kind == "failure_analysis"
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "literature_graph"
        and edge.source_kind in {"paper", "claim_evidence_matrix"}
        for edge in registry.lineage.edges
    )
    assert any(
        edge.relation == "derived_from"
        and edge.target_kind == "novelty_validation"
        and edge.source_kind in {"artifact", "literature_graph"}
        for edge in registry.lineage.edges
    )

    bundle_index = autoresearch_repository.load_run_bundle_index(project_id, run_id)
    assert bundle_index is not None
    selected_bundle = next(item for item in bundle_index.bundles if item.id == "selected_candidate_repro")
    benchmark_card_asset = next(
        item for item in selected_bundle.assets if item.role == "run_benchmark_card_json"
    )
    assert benchmark_card_asset.ref.exists is True
    protocol_asset = next(
        item for item in selected_bundle.assets if item.role == "run_research_protocol_json"
    )
    assert protocol_asset.ref.exists is True
    audit_asset = next(
        item for item in selected_bundle.assets if item.role == "run_methodology_audit_json"
    )
    assert audit_asset.ref.exists is True
    readiness_asset = next(
        item for item in selected_bundle.assets if item.role == "run_publication_readiness_json"
    )
    assert readiness_asset.ref.exists is True
    contribution_asset = next(
        item for item in selected_bundle.assets if item.role == "run_contribution_assessment_json"
    )
    assert contribution_asset.ref.exists is True
    experiment_design_asset = next(
        item for item in selected_bundle.assets if item.role == "run_experiment_design_json"
    )
    assert experiment_design_asset.ref.exists is True
    failure_analysis_asset = next(
        item for item in selected_bundle.assets if item.role == "run_failure_analysis_json"
    )
    assert failure_analysis_asset.ref.exists is True
    research_replan_asset = next(
        item for item in selected_bundle.assets if item.role == "run_research_replan_json"
    )
    assert research_replan_asset.ref.exists is True
    literature_graph_asset = next(
        item for item in selected_bundle.assets if item.role == "run_literature_graph_json"
    )
    assert literature_graph_asset.ref.exists is True
    novelty_validation_asset = next(
        item for item in selected_bundle.assets if item.role == "run_novelty_validation_json"
    )
    assert novelty_validation_asset.ref.exists is True
    dossier_asset = next(
        item for item in selected_bundle.assets if item.role == "run_revision_dossier_json"
    )
    assert dossier_asset.ref.exists is True
    evidence_index_asset = next(
        item for item in selected_bundle.assets if item.role == "run_publication_evidence_index_json"
    )
    assert evidence_index_asset.ref.exists is True
    artifact_integrity_audit_asset = next(
        item for item in selected_bundle.assets if item.role == "run_artifact_integrity_audit_json"
    )
    assert artifact_integrity_audit_asset.ref.exists is True
    repair_plan_asset = next(
        item for item in selected_bundle.assets if item.role == "run_publication_repair_plan_json"
    )
    assert repair_plan_asset.ref.exists is True
    repair_execution_asset = next(
        item for item in selected_bundle.assets if item.role == "run_publication_repair_execution_json"
    )
    assert repair_execution_asset.ref.exists is True

    package = review_publish.build_publish_package(project_id, run_id)
    assert package is not None
    assert package.benchmark_card_path == str(benchmark_card_path)
    assert package.research_protocol_path == str(protocol_path)
    assert package.methodology_audit_path == str(audit_path)
    assert package.revision_dossier_path == str(dossier_path)
    assert package.publication_evidence_index_path == str(evidence_index_path)
    assert package.artifact_integrity_audit_path == str(artifact_integrity_audit_path)
    assert package.publication_repair_plan_path == str(repair_plan_path)
    assert package.publication_repair_execution_path == str(repair_execution_path)
    assert package.publication_readiness_path == str(readiness_path)
    assert package.contribution_assessment_path == str(contribution_assessment_path)
    assert package.experiment_design_path == str(experiment_design_path)
    assert package.failure_analysis_path == str(failure_analysis_path)
    assert package.research_replan_path == str(research_replan_path)
    assert package.literature_graph_path == str(literature_graph_path)
    assert package.novelty_validation_path == str(novelty_validation_path)
    assert any(
        item.role == "run_benchmark_card_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_research_protocol_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_methodology_audit_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_publication_readiness_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_contribution_assessment_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_experiment_design_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_failure_analysis_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_research_replan_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_literature_graph_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_novelty_validation_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_revision_dossier_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_publication_evidence_index_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_artifact_integrity_audit_json"
        for item in package.final_required_assets
    )
    assert any(
        item.role == "run_publication_repair_plan_json"
        for item in package.final_required_assets
    )


def test_publication_manifest_records_readiness_artifact_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(
        review_publish,
        "_project_title",
        lambda project_id: "Publication Manifest Readiness Project",
    )
    spec, benchmark = _external_publication_spec()
    project_id = "project_publication_manifest_readiness"
    run_id = "run_publication_manifest_readiness"
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
    ).model_copy(
        update={
            "id": run_id,
            "project_id": project_id,
            "paper_latex_source": "\\documentclass{article}\\begin{document}Ready\\end{document}",
            "paper_bibliography_bib": "@article{ready2026,title={Ready},author={A},year={2026}}",
        }
    )
    autoresearch_repository.save_run(run)
    review = review_publish.build_run_review(project_id, run_id)
    assert review is not None
    assert review.benchmark_card is not None
    assert review.benchmark_card_path is not None
    assert review.research_protocol is not None
    assert review.research_protocol_path is not None
    assert review.methodology_audit is not None
    assert review.methodology_audit_path is not None
    assert review.revision_dossier is not None
    assert review.revision_dossier_path is not None
    assert review.publication_evidence_index is not None
    assert review.publication_evidence_index_path is not None
    assert review.publication_repair_plan is not None
    assert review.publication_repair_plan_path is not None
    assert review.publication_readiness is not None
    assert review.publication_readiness_path is not None
    assert review.contribution_assessment is not None
    assert review.contribution_assessment_path is not None
    assert review.experiment_design is not None
    assert review.experiment_design_path is not None
    assert review.failure_analysis is not None
    assert review.failure_analysis_path is not None
    assert review.research_replan is not None
    assert review.research_replan_path is not None
    assert review.literature_graph is not None
    assert review.literature_graph_path is not None
    assert review.novelty_validation is not None
    assert review.novelty_validation_path is not None
    benchmark_card_path = Path(review.benchmark_card_path)
    protocol_path = Path(review.research_protocol_path)
    audit_path = Path(review.methodology_audit_path)
    dossier_path = Path(review.revision_dossier_path)
    evidence_index_path = Path(review.publication_evidence_index_path)
    repair_plan_path = Path(review.publication_repair_plan_path)
    repair_execution_path = Path(
        autoresearch_repository.publication_repair_execution_file_path(project_id, run_id)
    )
    readiness_path = Path(review.publication_readiness_path)
    contribution_assessment_path = Path(review.contribution_assessment_path)
    experiment_design_path = Path(review.experiment_design_path)
    failure_analysis_path = Path(review.failure_analysis_path)
    research_replan_path = Path(review.research_replan_path)
    literature_graph_path = Path(review.literature_graph_path)
    novelty_validation_path = Path(review.novelty_validation_path)
    review_loop = review_publish.build_review_loop(project_id, run_id)
    assert review_loop is not None
    repair_execution = build_publication_repair_execution(
        project_id=project_id,
        run_id=run_id,
        repair_plan=review.publication_repair_plan,
        review_loop_before=review_loop,
        review_loop_after=review_loop,
    )
    repair_execution_path.write_text(
        repair_execution.model_dump_json(indent=2),
        encoding="utf-8",
    )
    assert benchmark_card_path.is_file()
    assert protocol_path.is_file()
    assert audit_path.is_file()
    assert dossier_path.is_file()
    assert evidence_index_path.is_file()
    assert repair_plan_path.is_file()
    assert repair_execution_path.is_file()
    assert readiness_path.is_file()
    assert contribution_assessment_path.is_file()
    assert experiment_design_path.is_file()
    assert failure_analysis_path.is_file()
    assert research_replan_path.is_file()
    assert literature_graph_path.is_file()
    assert novelty_validation_path.is_file()
    expected_benchmark_card_sha256 = hashlib.sha256(benchmark_card_path.read_bytes()).hexdigest()
    expected_protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    expected_audit_sha256 = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    expected_dossier_sha256 = hashlib.sha256(dossier_path.read_bytes()).hexdigest()
    expected_evidence_index_sha256 = hashlib.sha256(evidence_index_path.read_bytes()).hexdigest()
    expected_repair_plan_sha256 = hashlib.sha256(repair_plan_path.read_bytes()).hexdigest()
    expected_repair_execution_sha256 = hashlib.sha256(repair_execution_path.read_bytes()).hexdigest()
    expected_readiness_sha256 = hashlib.sha256(readiness_path.read_bytes()).hexdigest()
    expected_contribution_sha256 = hashlib.sha256(contribution_assessment_path.read_bytes()).hexdigest()
    expected_experiment_design_sha256 = hashlib.sha256(experiment_design_path.read_bytes()).hexdigest()
    expected_failure_analysis_sha256 = hashlib.sha256(failure_analysis_path.read_bytes()).hexdigest()
    expected_research_replan_sha256 = hashlib.sha256(research_replan_path.read_bytes()).hexdigest()
    expected_literature_graph_sha256 = hashlib.sha256(literature_graph_path.read_bytes()).hexdigest()
    expected_novelty_validation_sha256 = hashlib.sha256(novelty_validation_path.read_bytes()).hexdigest()

    code_package_path = review_publish._code_package_path(project_id, run_id)
    code_package_path.parent.mkdir(parents=True, exist_ok=True)
    code_package_path.write_bytes(b"fake code package")
    package = AutoResearchPublishPackageRead(
        project_id=project_id,
        run_id=run_id,
        package_id="publish_ready_bundle",
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        status="publish_ready",
        publish_ready=True,
        review_bundle_ready=True,
        final_publish_ready=True,
        publication_tier=review.publication_readiness.tier,
        publication_readiness_score=review.publication_readiness.score,
        benchmark_card_path=str(benchmark_card_path),
        research_protocol_path=str(protocol_path),
        methodology_audit_path=str(audit_path),
        revision_dossier_path=str(dossier_path),
        publication_evidence_index_path=str(evidence_index_path),
        publication_repair_plan_path=str(repair_plan_path),
        publication_repair_execution_path=str(repair_execution_path),
        publication_readiness_path=str(readiness_path),
        contribution_assessment_path=str(contribution_assessment_path),
        experiment_design_path=str(experiment_design_path),
        failure_analysis_path=str(failure_analysis_path),
        research_replan_path=str(research_replan_path),
        literature_graph_path=str(literature_graph_path),
        novelty_validation_path=str(novelty_validation_path),
        manifest_path=str(review_publish._publish_manifest_path(project_id, run_id)),
        archive_path=str(review_publish._publish_archive_path(project_id, run_id)),
        archive_ready=True,
        archive_current=True,
        package_fingerprint="package-fingerprint",
    )
    monkeypatch.setattr(
        review_publish,
        "build_publish_package",
        lambda current_project_id, current_run_id: package,
    )

    manifest = review_publish.build_publication_manifest(project_id, run_id)

    assert manifest is not None
    assert manifest.benchmark_card_path == str(benchmark_card_path)
    assert manifest.benchmark_card_sha256 == expected_benchmark_card_sha256
    assert manifest.research_protocol_path == str(protocol_path)
    assert manifest.research_protocol_sha256 == expected_protocol_sha256
    assert manifest.methodology_audit_path == str(audit_path)
    assert manifest.methodology_audit_sha256 == expected_audit_sha256
    assert manifest.revision_dossier_path == str(dossier_path)
    assert manifest.revision_dossier_sha256 == expected_dossier_sha256
    assert manifest.publication_evidence_index_path == str(evidence_index_path)
    assert manifest.publication_evidence_index_sha256 == expected_evidence_index_sha256
    assert manifest.publication_repair_plan_path == str(repair_plan_path)
    assert manifest.publication_repair_plan_sha256 == expected_repair_plan_sha256
    assert manifest.publication_repair_execution_path == str(repair_execution_path)
    assert manifest.publication_repair_execution_sha256 == expected_repair_execution_sha256
    assert manifest.publication_readiness_path == str(readiness_path)
    assert manifest.publication_readiness_sha256 == expected_readiness_sha256
    assert manifest.contribution_assessment_path == str(contribution_assessment_path)
    assert manifest.contribution_assessment_sha256 == expected_contribution_sha256
    assert manifest.experiment_design_path == str(experiment_design_path)
    assert manifest.experiment_design_sha256 == expected_experiment_design_sha256
    assert manifest.failure_analysis_path == str(failure_analysis_path)
    assert manifest.failure_analysis_sha256 == expected_failure_analysis_sha256
    assert manifest.research_replan_path == str(research_replan_path)
    assert manifest.research_replan_sha256 == expected_research_replan_sha256
    assert manifest.literature_graph_path == str(literature_graph_path)
    assert manifest.literature_graph_sha256 == expected_literature_graph_sha256
    assert manifest.novelty_validation_path == str(novelty_validation_path)
    assert manifest.novelty_validation_sha256 == expected_novelty_validation_sha256
    persisted = json.loads(Path(manifest.publication_manifest_path).read_text(encoding="utf-8"))
    assert persisted["benchmark_card_path"] == str(benchmark_card_path)
    assert persisted["benchmark_card_sha256"] == expected_benchmark_card_sha256
    assert persisted["research_protocol_path"] == str(protocol_path)
    assert persisted["research_protocol_sha256"] == expected_protocol_sha256
    assert persisted["methodology_audit_path"] == str(audit_path)
    assert persisted["methodology_audit_sha256"] == expected_audit_sha256
    assert persisted["revision_dossier_path"] == str(dossier_path)
    assert persisted["revision_dossier_sha256"] == expected_dossier_sha256
    assert persisted["publication_evidence_index_path"] == str(evidence_index_path)
    assert persisted["publication_evidence_index_sha256"] == expected_evidence_index_sha256
    assert persisted["publication_repair_plan_path"] == str(repair_plan_path)
    assert persisted["publication_repair_plan_sha256"] == expected_repair_plan_sha256
    assert persisted["publication_repair_execution_path"] == str(repair_execution_path)
    assert persisted["publication_repair_execution_sha256"] == expected_repair_execution_sha256
    assert persisted["publication_readiness_path"] == str(readiness_path)
    assert persisted["publication_readiness_sha256"] == expected_readiness_sha256
    assert persisted["contribution_assessment_path"] == str(contribution_assessment_path)
    assert persisted["contribution_assessment_sha256"] == expected_contribution_sha256
    assert persisted["experiment_design_path"] == str(experiment_design_path)
    assert persisted["experiment_design_sha256"] == expected_experiment_design_sha256
    assert persisted["failure_analysis_path"] == str(failure_analysis_path)
    assert persisted["failure_analysis_sha256"] == expected_failure_analysis_sha256
    assert persisted["research_replan_path"] == str(research_replan_path)
    assert persisted["research_replan_sha256"] == expected_research_replan_sha256
    assert persisted["literature_graph_path"] == str(literature_graph_path)
    assert persisted["literature_graph_sha256"] == expected_literature_graph_sha256
    assert persisted["novelty_validation_path"] == str(novelty_validation_path)
    assert persisted["novelty_validation_sha256"] == expected_novelty_validation_sha256


def test_export_publish_package_rewrites_archive_with_final_manifests(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project_export_archive_final_manifest"
    run_id = "run_export_archive_final_manifest"
    now = datetime.now(UTC).replace(tzinfo=None)
    run_root = autoresearch_repository.run_dir(project_id, run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    code_path = run_root / "candidate.py"
    code_path.write_text("print('ready')\n", encoding="utf-8")
    asset = review_publish.AutoResearchBundleAssetRead(
        asset_id=f"{run_id}:run_generated_code",
        label="Generated code",
        role="run_generated_code",
        required=True,
        ref=AutoResearchRegistryAssetRef(
            path=str(code_path),
            exists=True,
            sha256=hashlib.sha256(code_path.read_bytes()).hexdigest(),
        ),
    )
    bundle = review_publish.AutoResearchBundleRead(
        id="selected_candidate_repro",
        name="Selected Candidate Repro Bundle",
        description="Regression bundle.",
        asset_count=1,
        existing_asset_count=1,
        assets=[asset],
    )
    bundle_index = review_publish.AutoResearchBundleIndexRead(
        project_id=project_id,
        run_id=run_id,
        bundles=[bundle],
    )
    package = AutoResearchPublishPackageRead(
        project_id=project_id,
        run_id=run_id,
        package_id="publish_ready_bundle",
        generated_at=now,
        source_bundle_id=bundle.id,
        status="publish_ready",
        publish_ready=True,
        review_bundle_ready=True,
        final_publish_ready=True,
        manifest_path=str(review_publish._publish_manifest_path(project_id, run_id)),
        archive_path=str(review_publish._publish_archive_path(project_id, run_id)),
        asset_count=1,
        existing_asset_count=1,
        required_assets=[asset],
        final_required_assets=[asset],
        package_fingerprint="export-package-fingerprint",
        review_round=3,
        review_fingerprint="review-fingerprint",
    )

    monkeypatch.setattr(
        review_publish,
        "build_publish_package",
        lambda current_project_id, current_run_id: package,
    )
    monkeypatch.setattr(
        review_publish,
        "load_run_bundle_index",
        lambda current_project_id, current_run_id: bundle_index,
    )

    def fake_publication_manifest(
        current_project_id: str,
        current_run_id: str,
        *,
        deployment_id: str | None = None,
        deployment_label: str | None = None,
    ) -> review_publish.AutoResearchPublicationManifestRead:
        manifest_path = review_publish._publication_manifest_path(
            current_project_id,
            current_run_id,
        )
        deployment = review_publish.AutoResearchDeploymentRefRead(
            deployment_id=deployment_id or "local_default",
            label=deployment_label or "Local Deployment",
            listed_at=now,
        )
        manifest = review_publish.AutoResearchPublicationManifestRead(
            publication_id=f"publication_{current_run_id}",
            project_id=current_project_id,
            run_id=current_run_id,
            topic="Final archive manifest regression",
            paper_title="Final archive manifest regression",
            generated_at=now,
            updated_at=now,
            package_id=package.package_id,
            package_fingerprint=package.package_fingerprint,
            bundle_kind="final_publish_bundle",
            review_bundle_ready=True,
            final_publish_ready=True,
            publication_manifest_path=str(manifest_path),
            publish_manifest_path=str(
                review_publish._publish_manifest_path(current_project_id, current_run_id)
            ),
            publish_archive_path=str(
                review_publish._publish_archive_path(current_project_id, current_run_id)
            ),
            code_package_path=str(
                review_publish._code_package_path(current_project_id, current_run_id)
            ),
            run_api_path=f"/api/projects/{current_project_id}/auto-research/{current_run_id}",
            registry_api_path=(
                f"/api/projects/{current_project_id}/auto-research/{current_run_id}/registry"
            ),
            publish_api_path=(
                f"/api/projects/{current_project_id}/auto-research/{current_run_id}/publish"
            ),
            publish_download_path=(
                f"/api/projects/{current_project_id}/auto-research/{current_run_id}/publish/download"
            ),
            code_package_download_path=(
                f"/api/projects/{current_project_id}/auto-research/{current_run_id}/publish/code/download"
            ),
            deployments=[deployment],
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return manifest

    monkeypatch.setattr(
        review_publish,
        "build_publication_manifest",
        fake_publication_manifest,
    )

    export = review_publish.export_publish_package(project_id, run_id)

    assert export is not None
    with ZipFile(export.archive_path) as archive:
        names = set(archive.namelist())
        assert review_publish.PUBLISH_PACKAGE_FILENAME in names
        assert review_publish.PUBLISH_ARCHIVE_MANIFEST_FILENAME in names
        assert review_publish.PUBLICATION_MANIFEST_FILENAME in names
        assert review_publish.CODE_PACKAGE_FILENAME in names
        archived_package = json.loads(
            archive.read(review_publish.PUBLISH_PACKAGE_FILENAME).decode("utf-8")
        )
        archived_manifest = json.loads(
            archive.read(review_publish.PUBLISH_ARCHIVE_MANIFEST_FILENAME).decode("utf-8")
        )

    assert archived_package["archive_current"] is True
    assert archived_package["publication_id"] == f"publication_{run_id}"
    assert archived_package["code_package_path"] == str(
        review_publish._code_package_path(project_id, run_id)
    )
    assert review_publish.PUBLICATION_MANIFEST_FILENAME in archived_manifest["generated_files"]
    assert review_publish.CODE_PACKAGE_FILENAME in archived_manifest["generated_files"]
    generated_refs = {
        item["file_name"]: item
        for item in archived_manifest["generated_file_refs"]
    }
    publication_manifest_ref = generated_refs[review_publish.PUBLICATION_MANIFEST_FILENAME]
    code_package_ref = generated_refs[review_publish.CODE_PACKAGE_FILENAME]
    assert publication_manifest_ref["exists"] is True
    assert publication_manifest_ref["sha256"] == hashlib.sha256(
        Path(export.publication_manifest_path).read_bytes()
    ).hexdigest()
    assert code_package_ref["exists"] is True
    assert code_package_ref["sha256"] == hashlib.sha256(
        Path(export.code_package_path).read_bytes()
    ).hexdigest()


def test_export_publish_package_rejects_incomplete_archive(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project_export_archive_integrity"
    run_id = "run_export_archive_integrity"
    now = datetime.now(UTC).replace(tzinfo=None)
    run_root = autoresearch_repository.run_dir(project_id, run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    code_path = run_root / "candidate.py"
    code_path.write_text("print('ready')\n", encoding="utf-8")
    asset = review_publish.AutoResearchBundleAssetRead(
        asset_id=f"{run_id}:run_generated_code",
        label="Generated code",
        role="run_generated_code",
        required=True,
        ref=AutoResearchRegistryAssetRef(
            path=str(code_path),
            exists=True,
            size_bytes=code_path.stat().st_size,
            sha256=hashlib.sha256(code_path.read_bytes()).hexdigest(),
        ),
    )
    bundle = review_publish.AutoResearchBundleRead(
        id="selected_candidate_repro",
        name="Selected Candidate Repro Bundle",
        description="Regression bundle.",
        asset_count=1,
        existing_asset_count=1,
        assets=[asset],
    )
    bundle_index = review_publish.AutoResearchBundleIndexRead(
        project_id=project_id,
        run_id=run_id,
        bundles=[bundle],
    )
    package = AutoResearchPublishPackageRead(
        project_id=project_id,
        run_id=run_id,
        package_id="publish_ready_bundle",
        generated_at=now,
        source_bundle_id=bundle.id,
        status="publish_ready",
        publish_ready=True,
        review_bundle_ready=True,
        final_publish_ready=True,
        manifest_path=str(review_publish._publish_manifest_path(project_id, run_id)),
        archive_path=str(review_publish._publish_archive_path(project_id, run_id)),
        asset_count=1,
        existing_asset_count=1,
        required_assets=[asset],
        final_required_assets=[asset],
        package_fingerprint="integrity-package-fingerprint",
        review_round=3,
        review_fingerprint="review-fingerprint",
    )
    monkeypatch.setattr(
        review_publish,
        "build_publish_package",
        lambda current_project_id, current_run_id: package,
    )
    monkeypatch.setattr(
        review_publish,
        "load_run_bundle_index",
        lambda current_project_id, current_run_id: bundle_index,
    )

    def fake_publication_manifest(
        current_project_id: str,
        current_run_id: str,
        *,
        deployment_id: str | None = None,
        deployment_label: str | None = None,
    ) -> review_publish.AutoResearchPublicationManifestRead:
        manifest_path = review_publish._publication_manifest_path(
            current_project_id,
            current_run_id,
        )
        deployment = review_publish.AutoResearchDeploymentRefRead(
            deployment_id=deployment_id or "local_default",
            label=deployment_label or "Local Deployment",
            listed_at=now,
        )
        manifest = review_publish.AutoResearchPublicationManifestRead(
            publication_id=f"publication_{current_run_id}",
            project_id=current_project_id,
            run_id=current_run_id,
            topic="Archive integrity regression",
            paper_title="Archive integrity regression",
            generated_at=now,
            updated_at=now,
            package_id=package.package_id,
            package_fingerprint=package.package_fingerprint,
            bundle_kind="final_publish_bundle",
            review_bundle_ready=True,
            final_publish_ready=True,
            publication_manifest_path=str(manifest_path),
            publish_manifest_path=str(
                review_publish._publish_manifest_path(current_project_id, current_run_id)
            ),
            publish_archive_path=str(
                review_publish._publish_archive_path(current_project_id, current_run_id)
            ),
            code_package_path=str(
                review_publish._code_package_path(current_project_id, current_run_id)
            ),
            run_api_path=f"/api/projects/{current_project_id}/auto-research/{current_run_id}",
            registry_api_path=f"/api/projects/{current_project_id}/auto-research/{current_run_id}/registry",
            publish_api_path=f"/api/projects/{current_project_id}/auto-research/{current_run_id}/publish",
            publish_download_path=f"/api/projects/{current_project_id}/auto-research/{current_run_id}/publish/download",
            code_package_download_path=f"/api/projects/{current_project_id}/auto-research/{current_run_id}/publish/code/download",
            deployments=[deployment],
        )
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return manifest

    def write_incomplete_archive(**kwargs: object) -> None:
        archive_path = kwargs["archive_path"]
        assert isinstance(archive_path, Path)
        with ZipFile(archive_path, "w"):
            pass

    monkeypatch.setattr(
        review_publish,
        "build_publication_manifest",
        fake_publication_manifest,
    )
    monkeypatch.setattr(review_publish, "_write_publish_archive", write_incomplete_archive)

    with pytest.raises(ValueError, match="integrity verification failed"):
        review_publish.export_publish_package(project_id, run_id)

    persisted_package = json.loads(
        review_publish._publish_manifest_path(project_id, run_id).read_text(
            encoding="utf-8"
        )
    )
    assert persisted_package["archive_status"] == "stale"
    assert persisted_package["archive_current"] is False


def test_autoresearch_resume_preserves_checkpointed_literature_synthesis(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session_local = _session_local(monkeypatch, tmp_path)
    project_id = "project_resume_regression"
    topic = "Checkpoint resume literature synthesis"
    code_path = tmp_path / "candidate.py"
    code_path.write_text("# checkpointed candidate\n", encoding="utf-8")
    benchmark = builtin_benchmark("text_classification", topic=topic)
    spec = build_experiment_spec("text_classification", benchmark)
    plan = ResearchPlan(
        topic=topic,
        title="Checkpoint Resume Literature Synthesis",
        task_family="text_classification",
        problem_statement="Resume a checkpointed text classification experiment.",
        motivation="Recovered runs should keep literature positioning for the paper.",
        proposed_method="Use a lightweight lexical classifier.",
        research_questions=["Does the checkpointed candidate beat the baseline?"],
        hypotheses=["The candidate improves macro F1 over the keyword baseline."],
        planned_contributions=["A reproducible checkpoint resume path."],
        experiment_outline=["Reuse the checkpointed artifact and rebuild the paper."],
    )
    program = ResearchProgram(
        id="program_resume_regression",
        topic=topic,
        title=plan.title,
        task_family="text_classification",
        objective="Recover the run without dropping paper context.",
        benchmark_name=benchmark.benchmark_name,
        portfolio_policy="single checkpointed candidate",
    )
    artifact = _result_artifact()
    attempt = ExperimentAttempt(
        round_index=1,
        strategy="checkpointed_strategy",
        goal="recover_checkpoint",
        status="done",
        summary=artifact.summary,
        code_path=str(code_path),
        artifact=artifact,
    )
    candidate = HypothesisCandidate(
        id="candidate_resume_regression",
        program_id=program.id,
        rank=1,
        title="Checkpointed Candidate",
        hypothesis=plan.hypotheses[0],
        proposed_method=plan.proposed_method,
        rationale="The checkpoint already contains a successful artifact.",
        status="running",
        score=0.72,
        attempts=[attempt],
        artifact=artifact,
        generated_code_path=str(code_path),
        selected_round_index=1,
    )
    portfolio = PortfolioSummary(
        status="running",
        total_candidates=1,
        candidate_rankings=[candidate.id],
        executed_candidate_ids=[candidate.id],
        selected_candidate_id=candidate.id,
        selection_policy="highest checkpointed score",
        decision_summary="Candidate is running from a checkpoint.",
        winning_score=0.72,
    )
    synthesis = LiteratureSynthesis(
        themes=[
            LiteratureTheme(
                theme_id="theme_checkpoint",
                label="Checkpointed context",
                description="Prior work motivates preserving paper positioning across resume.",
            )
        ],
        positioning="The resumed paper should keep this positioning.",
        novelty_claim="Checkpoint resume preserves literature synthesis for writing.",
    )

    db = session_local()
    try:
        _seed_project(db, project_id)
        run = autoresearch_repository.create_run(project_id, topic)
        autoresearch_repository.save_run(
            run.model_copy(
                update={
                    "status": "canceled",
                    "task_family": "text_classification",
                    "benchmark": benchmark.source,
                    "program": program,
                    "plan": plan,
                    "spec": spec,
                    "literature": [],
                    "literature_synthesis": synthesis,
                    "candidates": [candidate],
                    "portfolio": portfolio,
                    "attempts": [attempt],
                    "artifact": artifact,
                    "generated_code_path": str(code_path),
                    "selected_round_index": 1,
                }
            )
        )
    finally:
        db.close()

    narrative_synthesis: list[LiteratureSynthesis | None] = []
    writer_synthesis: list[LiteratureSynthesis | None] = []
    original_build_pipeline = autoresearch_orchestrator.PaperWriter.build_pipeline

    def fake_analyze_narrative(*, plan, artifact, literature_synthesis=None):
        del plan, artifact
        narrative_synthesis.append(literature_synthesis)
        return None

    def wrapped_build_pipeline(self, *args, **kwargs):
        writer_synthesis.append(kwargs.get("literature_synthesis"))
        return original_build_pipeline(self, *args, **kwargs)

    monkeypatch.setattr(autoresearch_orchestrator, "analyze_narrative", fake_analyze_narrative)
    monkeypatch.setattr(autoresearch_orchestrator.PaperWriter, "build_pipeline", wrapped_build_pipeline)
    monkeypatch.setattr(
        autoresearch_orchestrator.PaperWriter,
        "write",
        lambda self, *args, **kwargs: "# resumed checkpoint paper\n\nThe checkpointed paper is grounded.",
    )

    db = session_local()
    try:
        resumed = autoresearch_orchestrator.AutoResearchOrchestrator().execute(
            db=db,
            project_id=project_id,
            run_id=run.id,
            topic=topic,
            execution_action="resume",
            max_rounds=1,
            auto_search_literature=False,
        )
    finally:
        db.close()

    assert resumed.status == "done"
    assert narrative_synthesis
    assert writer_synthesis
    assert narrative_synthesis[0] is not None
    assert writer_synthesis[0] is not None
    assert narrative_synthesis[0].novelty_claim == synthesis.novelty_claim
    assert writer_synthesis[0].novelty_claim == synthesis.novelty_claim


def test_paper_search_upsert_reuses_project_link_for_duplicate_results(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session_local = _session_local(monkeypatch, tmp_path)
    project_id = "project_duplicate_links"
    db = session_local()
    try:
        _seed_project(db, project_id, title="Duplicate Literature Links")
        ids = papers_repository.upsert_papers_from_search(
            db,
            project_id,
            [
                PaperMeta(
                    title="Deduplicated Search Paper",
                    authors=["A. Author"],
                    year=2024,
                    abstract="First search result.",
                    source="semantic_scholar",
                ),
                PaperMeta(
                    title="Deduplicated Search Paper",
                    authors=["A. Author"],
                    year=2024,
                    abstract="Duplicate search result mapped to the same paper.",
                    source="semantic_scholar",
                ),
            ],
        )
        papers = papers_repository.list_papers(db, project_id)
    finally:
        db.close()

    assert len(ids) == 2
    assert ids[0] == ids[1]
    assert len(papers) == 1
    assert papers[0].title == "Deduplicated Search Paper"


def test_research_brief_uses_objective_score_when_best_system_is_missing(
    monkeypatch,
) -> None:
    plan, spec = _writer_plan_and_spec()
    artifact = ResultArtifact(
        status="done",
        summary="The candidate produced an objective score without a best-system alias.",
        key_findings=["objective system improved macro F1"],
        primary_metric="macro_f1",
        objective_system="candidate_system",
        objective_score=0.83,
        system_results=[],
        aggregate_system_results=[],
        acceptance_checks=[],
        tables=[],
        environment={},
        outputs={},
    )

    def fail_chat(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("offline")

    monkeypatch.setattr(autoresearch_writer, "chat", fail_chat)

    brief = PaperWriter()._build_research_brief(
        plan=plan,
        spec=spec,
        artifact=artifact,
        literature=[],
        attempts=[],
    )

    assert "candidate_system" in brief
    assert "macro_f1=0.8300" in brief


def test_llm_section_generation_uses_paper_plan_section_objective(
    monkeypatch,
) -> None:
    plan, spec = _writer_plan_and_spec()
    artifact = _result_artifact()
    writer = PaperWriter()
    claim_matrix = writer.build_claim_evidence_matrix(
        plan,
        spec,
        artifact,
        literature=[],
        attempts=[],
        portfolio=None,
        candidates=[],
    )
    paper_plan = AutoResearchPaperPlanRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        title=plan.title,
        narrative_summary="Use the exact section objective during LLM section drafting.",
        sections=[
            AutoResearchPaperPlanSectionRead(
                section_id="intro",
                title="Introduction",
                objective="Explain the exact benchmark framing and paper contribution.",
            )
        ],
    )
    seen_objectives: list[str] = []

    def fail_chat(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("offline")

    def fake_write_section(self, section_title, section_objective, **kwargs):
        del self, section_title, kwargs
        seen_objectives.append(section_objective)
        return "Generated section grounded in the exact paper-plan objective."

    monkeypatch.setattr(autoresearch_writer, "chat", fail_chat)
    monkeypatch.setattr(PaperWriter, "_write_section_with_llm", fake_write_section)

    sections = writer._write_full_paper_with_llm(
        plan,
        spec,
        artifact,
        paper_plan,
        claim_matrix,
        [],
    )

    assert seen_objectives == ["Explain the exact benchmark framing and paper contribution."]
    assert sections["introduction"].startswith("Generated section grounded")


def test_dedicated_section_prompt_receives_assignment_context(monkeypatch) -> None:
    writer = PaperWriter()
    captured_messages: list[dict] = []

    def fake_load_prompt(path):
        del path
        return "Dedicated section prompt."

    def fake_chat(messages, **kwargs):
        del kwargs
        captured_messages.extend(messages)
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Generated section content grounded in the provided assignment context.",
                    }
                }
            ]
        }

    monkeypatch.setattr(autoresearch_writer, "load_prompt", fake_load_prompt)
    monkeypatch.setattr(autoresearch_writer, "chat", fake_chat)

    content = writer._write_section_with_llm(
        section_title="Introduction",
        section_objective="Explain the exact benchmark framing and contribution.",
        evidence_context="- supported claim with metric evidence",
        topic="Writer regression topic",
        section_slug="introduction",
    )

    assert content is not None
    user_context = captured_messages[1]["content"]
    assert "## Section Assignment" in user_context
    assert "- Title: Introduction" in user_context
    assert "- Objective: Explain the exact benchmark framing and contribution." in user_context
    assert "- Topic: Writer regression topic" in user_context


def test_section_evidence_context_includes_table_values() -> None:
    plan, _spec = _writer_plan_and_spec()
    writer = PaperWriter()
    artifact = _result_artifact().model_copy(
        update={
            "tables": [
                ResultTable(
                    title="Main Results",
                    columns=["System", "Macro F1"],
                    rows=[
                        ["candidate_system", "0.72"],
                        ["keyword_baseline", "0.61"],
                    ],
                )
            ]
        }
    )
    claim_matrix = writer.build_claim_evidence_matrix(
        plan,
        _spec,
        artifact,
        literature=[],
        attempts=[],
        portfolio=None,
        candidates=[],
    )
    section = AutoResearchPaperPlanSectionRead(
        section_id="results",
        title="Results",
        objective="Present grounded metrics.",
        claim_ids=["claim_result_summary"],
    )

    evidence_context = writer._build_evidence_context_for_section(
        section,
        artifact,
        claim_matrix,
    )

    assert "| System | Macro F1 |" in evidence_context
    assert "| candidate_system | 0.72 |" in evidence_context
    assert "| keyword_baseline | 0.61 |" in evidence_context


def test_split_sections_normalizes_numbered_headings() -> None:
    sections = PaperWriter()._split_sections(
        "# Title\n\n"
        "## Abstract\nBrief.\n\n"
        "## 1. Introduction\nIntro body.\n\n"
        "## 2. Related Work\nRelated body.\n"
    )

    assert sections["abstract"] == "Brief."
    assert sections["introduction"] == "Intro body."
    assert sections["related_work"] == "Related body."


def test_writer_section_pass_can_be_disabled(monkeypatch) -> None:
    plan, spec = _writer_plan_and_spec()
    artifact = _result_artifact()
    writer = PaperWriter()
    claim_matrix = writer.build_claim_evidence_matrix(
        plan,
        spec,
        artifact,
        literature=[],
        attempts=[],
        portfolio=None,
        candidates=[],
    )
    paper_plan = writer.build_paper_plan(plan, claim_matrix)

    def fail_chat(*args, **kwargs):
        del args, kwargs
        raise AssertionError("section-pass disabled should not call the LLM")

    monkeypatch.setenv("AUTORESEARCH_PAPER_WRITER_SECTION_PASS", "0")
    monkeypatch.setattr(autoresearch_writer, "chat", fail_chat)

    sections = writer._write_full_paper_with_llm(
        plan,
        spec,
        artifact,
        paper_plan,
        claim_matrix,
        [],
    )

    assert sections == {}


def test_writer_review_loop_can_be_disabled(monkeypatch) -> None:
    plan, spec = _writer_plan_and_spec()
    artifact = _result_artifact()
    writer = PaperWriter()
    claim_matrix = writer.build_claim_evidence_matrix(
        plan,
        spec,
        artifact,
        literature=[],
        attempts=[],
        portfolio=None,
        candidates=[],
    )
    paper_plan = AutoResearchPaperPlanRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        title=plan.title,
        narrative_summary="Minimal plan for review-budget regression.",
        sections=[
            AutoResearchPaperPlanSectionRead(
                section_id="abstract",
                title="Abstract",
                objective="Summarize the grounded result.",
            )
        ],
    )
    revision_state = writer.build_paper_revision_state(
        claim_matrix,
        paper_plan=paper_plan,
        figure_plan=None,
    )
    seed_markdown = "# Writer Regression Topic\n\n## Abstract\nGrounded abstract.\n"

    def fake_chat(*args, **kwargs):
        del args, kwargs
        return {"choices": [{"message": {"role": "assistant", "content": seed_markdown}}]}

    def fail_review(*args, **kwargs):
        del args, kwargs
        raise AssertionError("review loop should be skipped")

    monkeypatch.setenv("AUTORESEARCH_PAPER_WRITER_REVIEW_ROUNDS", "0")
    monkeypatch.setattr(autoresearch_writer, "chat", fake_chat)
    monkeypatch.setattr(PaperWriter, "_multi_perspective_review", fail_review)

    result = writer._maybe_refine_with_llm(
        seed_markdown=seed_markdown,
        language="en",
        plan=plan,
        spec=spec,
        artifact=artifact,
        literature=[],
        attempts=[],
        project_context=None,
        narrative_report_markdown="Narrative report.",
        claim_evidence_matrix=claim_matrix,
        paper_plan=paper_plan,
        paper_revision_state=revision_state,
    )

    assert result == seed_markdown.strip()


def test_writer_and_planner_tolerate_missing_prompt_files(monkeypatch) -> None:
    plan, spec = _writer_plan_and_spec()
    artifact = _result_artifact()
    writer = PaperWriter()
    claim_matrix = writer.build_claim_evidence_matrix(
        plan,
        spec,
        artifact,
        literature=[],
        attempts=[],
        portfolio=None,
        candidates=[],
    )
    paper_plan = AutoResearchPaperPlanRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        title=plan.title,
        narrative_summary="Prompt-missing fallback regression.",
        sections=[
            AutoResearchPaperPlanSectionRead(
                section_id="abstract",
                title="Abstract",
                objective="Summarize the fallback result.",
            )
        ],
    )
    revision_state = writer.build_paper_revision_state(
        claim_matrix,
        paper_plan=paper_plan,
        figure_plan=None,
    )
    seed_markdown = "# Prompt Missing Topic\n\n## Abstract\nFallback abstract.\n"

    def missing_prompt(path: str) -> str:
        raise FileNotFoundError(f"Prompt not found: {path}")

    monkeypatch.setenv("AUTORESEARCH_PAPER_WRITER_REVIEW_ROUNDS", "0")
    monkeypatch.setattr(autoresearch_writer, "load_prompt", missing_prompt)
    monkeypatch.setattr(autoresearch_planner, "load_prompt", missing_prompt)

    result = writer._maybe_refine_with_llm(
        seed_markdown=seed_markdown,
        language="en",
        plan=plan,
        spec=spec,
        artifact=artifact,
        literature=[],
        attempts=[],
        project_context=None,
        narrative_report_markdown="Narrative report.",
        claim_evidence_matrix=claim_matrix,
        paper_plan=paper_plan,
        paper_revision_state=revision_state,
    )
    framework = autoresearch_planner.ResearchPlanner()._build_conceptual_framework(
        topic=plan.topic,
        task_family=plan.task_family,
        proposed_method=plan.proposed_method,
        hypotheses=plan.hypotheses,
        literature_synthesis=None,
    )

    assert result == seed_markdown.strip()
    assert framework is None


def test_writer_marks_unexecuted_ablation_hypothesis_as_untested() -> None:
    plan, spec = _writer_plan_and_spec()
    plan = plan.model_copy(
        update={
            "hypotheses": [
                "The candidate improves macro F1 over the baseline.",
                "Reducing vocabulary coverage hurts macro F1.",
            ]
        }
    )
    spec = spec.model_copy(
        update={
            "ablations": [
                AblationSpec(
                    name="vocab_ablation",
                    description="Remove rare lexical features.",
                )
            ]
        }
    )
    artifact = _result_artifact()

    block = PaperWriter()._hypothesis_validation_block(
        plan,
        spec,
        artifact,
        best_metric=0.72,
        baseline_metric=0.61,
        attempts=[],
    )

    assert "H1" in block
    assert "SUPPORTED" in block
    assert "H2" in block
    assert "UNTESTED" in block
    assert "no completed ablation result was preserved" in block


def test_writer_seed_paper_demotes_missing_ablation_and_significance(monkeypatch) -> None:
    plan, spec = _writer_plan_and_spec()
    plan = plan.model_copy(
        update={
            "hypotheses": [
                "The candidate improves macro F1 over the baseline.",
                "Reducing vocabulary coverage hurts macro F1.",
            ]
        }
    )
    spec = spec.model_copy(
        update={
            "ablations": [
                AblationSpec(
                    name="vocab_ablation",
                    description="Remove rare lexical features.",
                )
            ],
            "seeds": [1, 2],
        }
    )
    artifact = _result_artifact().model_copy(update={"per_seed_results": [], "significance_tests": []})
    writer = PaperWriter()
    claim_matrix = writer.build_claim_evidence_matrix(
        plan,
        spec,
        artifact,
        literature=[],
        attempts=[],
        portfolio=None,
        candidates=[],
    )
    statistical_claim = next(
        item for item in claim_matrix.entries if item.claim_id == "claim_statistical_grounding"
    )
    assert statistical_claim.support_status == "partial"
    assert "does not preserve completed per-seed artifacts" in statistical_claim.claim
    assert "multi-seed aggregate reporting across 2 seeds" not in statistical_claim.claim

    def empty_chat(*args, **kwargs):
        del args, kwargs
        return {"choices": [{"message": {"role": "assistant", "content": ""}}]}

    monkeypatch.setenv("AUTORESEARCH_PAPER_WRITER_SECTION_PASS", "0")
    monkeypatch.setenv("AUTORESEARCH_PAPER_WRITER_REVIEW_ROUNDS", "0")
    monkeypatch.setattr(autoresearch_writer, "chat", empty_chat)

    paper = writer.write(
        plan,
        spec,
        artifact,
        literature=[],
        attempts=[],
        claim_evidence_matrix=claim_matrix,
    )

    assert "No completed ablation result was preserved" in paper
    assert "ablation-specific hypotheses remain untested" in paper
    assert "No paired significance comparisons were preserved" in paper
    assert "UNTESTED" in paper
    assert "An ablation study was included" not in paper


def test_writer_strips_whole_markdown_fences_from_llm_outputs() -> None:
    writer = PaperWriter()

    cleaned = writer._strip_markdown_fence(
        """```markdown
# Paper Title

## Abstract
Grounded paper content.
```"""
    )

    assert cleaned.startswith("# Paper Title")
    assert "## Abstract" in cleaned
    assert not cleaned.startswith("```")
    assert not cleaned.endswith("```")


def test_llm_paper_candidate_must_preserve_top_level_title() -> None:
    writer = PaperWriter()

    valid = writer._llm_paper_candidate_valid(
        "## Abstract\nGrounded abstract.\n",
        seed_markdown="# Paper Title\n\n## Abstract\nGrounded abstract.\n",
        literature=[],
        project_context=None,
    )

    assert valid is False


def test_writer_restores_dropped_top_level_title() -> None:
    writer = PaperWriter()

    repaired = writer._ensure_top_level_title(
        "## Abstract\nGrounded abstract.\n",
        seed_markdown="# Paper Title\n\n## Abstract\nSeed abstract.\n",
    )

    assert repaired.startswith("# Paper Title\n\n## Abstract")


def test_review_flags_hypothesis_mismatch_from_objective_system() -> None:
    _plan, spec = _writer_plan_and_spec()
    spec = spec.model_copy(
        update={"hypothesis": "The majority baseline should produce the best macro F1."}
    )
    artifact = ResultArtifact(
        status="done",
        summary="The candidate system won even though the hypothesis named the baseline.",
        key_findings=["candidate system beat the named baseline"],
        primary_metric="macro_f1",
        objective_system="candidate_system",
        objective_score=0.83,
        system_results=[],
        aggregate_system_results=[],
        acceptance_checks=[],
        tables=[],
        environment={},
        outputs={},
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    run = AutoResearchRunRead(
        id="run_hypothesis_objective_system",
        project_id="project_hypothesis_objective_system",
        topic="Writer regression topic",
        status="done",
        task_family="text_classification",
        spec=spec,
        artifact=artifact,
        created_at=now,
        updated_at=now,
    )

    finding = review_publish._hypothesis_resolution_finding(run, "")

    assert finding is not None
    assert finding[0] == "warning"
    assert "`candidate_system`" in finding[2]


def test_review_blocks_final_publish_for_underpowered_or_unsupported_research() -> None:
    plan, spec = _writer_plan_and_spec()
    spec = spec.model_copy(
        update={
            "ablations": [
                AblationSpec(
                    name="vocab_ablation",
                    description="Remove rare lexical features to test vocabulary coverage.",
                )
            ],
            "seeds": [1, 2, 3],
        }
    )
    artifact = _result_artifact().model_copy(
        update={
            "per_seed_results": [],
            "significance_tests": [],
            "sweep_results": [],
        }
    )
    claim_matrix = AutoResearchClaimEvidenceMatrixRead(
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        claim_count=2,
        supported_claim_count=1,
        unsupported_claim_count=1,
        entries=[
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_result_summary",
                category="result",
                section_hint="Results",
                claim="Candidate system improved macro F1.",
                evidence=[
                    AutoResearchClaimEvidenceRefRead(
                        source_kind="artifact",
                        label="Result table",
                        detail="Candidate system scored 0.72 macro F1.",
                    )
                ],
            ),
            AutoResearchClaimEvidenceEntryRead(
                claim_id="claim_ablation",
                category="result",
                section_hint="Results",
                claim="Vocabulary ablation confirms lexical coverage is necessary.",
                support_status="unsupported",
                evidence=[],
                gaps=["Run the planned vocabulary ablation."],
            ),
        ],
    )
    literature = [
        LiteratureInsight(
            paper_id="paper-1",
            title="Lexical Sentiment Baselines",
            year=2024,
            source="semantic_scholar",
            insight="Lexical baselines need multi-seed evaluation.",
        )
    ]
    now = datetime.now(UTC).replace(tzinfo=None)
    run = AutoResearchRunRead(
        id="run_underpowered_publish_gate",
        project_id="project_underpowered_publish_gate",
        topic=plan.topic,
        status="done",
        task_family="text_classification",
        plan=plan,
        spec=spec,
        artifact=artifact,
        literature=literature,
        claim_evidence_matrix=claim_matrix,
        paper_markdown=(
            "# Writer Regression Topic\n\n"
            "## Abstract\nGrounded result summary.\n\n"
            "## Related Work\nPrior lexical baselines motivate this benchmark [1].\n\n"
            "## Results\nCandidate system scored 0.72 macro F1.\n\n"
            "## References\n[1] Lexical Sentiment Baselines. Semantic Scholar, 2024.\n"
        ),
        created_at=now,
        updated_at=now,
    )
    novelty = AutoResearchNoveltyAssessmentRead(
        status="grounded",
        summary="Literature context is present for the selected claim.",
        compared_paper_count=1,
        strong_match_count=1,
        covered_claim_count=1,
        total_claim_count=1,
    )

    protocol = build_research_protocol(run)
    audit = build_methodology_audit(run, protocol=protocol)
    findings, evidence, citation_coverage = review_publish._review_findings(
        run=run,
        bundle=None,
        selected_manifest_source="file",
        paper_markdown=run.paper_markdown or "",
        novelty_assessment=novelty,
        benchmark_card=build_benchmark_card(run),
        research_protocol=protocol,
        methodology_audit=audit,
        publication_readiness=build_publication_readiness(
            run,
            paper_markdown=run.paper_markdown or "",
        ),
    )

    summaries = {item.summary for item in findings}
    assert "Seed coverage is insufficient for publication-level claims." in summaries
    assert "The paper package does not preserve significance comparisons." in summaries
    assert "Planned ablations were not executed in the selected artifact." in summaries
    assert "Claim-evidence matrix contains unsupported publish-facing claims." in summaries

    actions = review_publish._revision_plan(findings)
    action_titles = {item.title for item in actions}
    assert "Run additional seeds before final publication" in action_titles
    assert "Run paired significance comparisons" in action_titles
    assert "Run planned ablations or demote ablation claims" in action_titles
    assert "Rerun experiments or demote unsupported claims" in action_titles

    review = review_publish.AutoResearchRunReviewRead(
        project_id=run.project_id,
        run_id=run.id,
        generated_at=now,
        overall_status="needs_revision",
        unsupported_claim_risk="medium",
        summary="Regression review.",
        evidence=evidence,
        citation_coverage=citation_coverage,
        novelty_assessment=novelty,
        research_protocol=protocol,
        methodology_audit=audit,
        publication_readiness=build_publication_readiness(
            run,
            paper_markdown=run.paper_markdown or "",
        ),
        scores=review_publish._review_scores(
            run=run,
            bundle=None,
            findings=findings,
            evidence=evidence,
            citation_coverage=citation_coverage,
            selected_manifest_source="file",
        ),
        findings=findings,
        revision_plan=actions,
    )
    final_blockers = review_publish._semantic_final_publish_blockers(review)

    assert any("stronger experimental evidence" in item for item in final_blockers)
    assert any("supported claim-evidence commitments" in item for item in final_blockers)


def test_review_blocks_final_publish_when_only_synthetic_literature_is_cited() -> None:
    plan, spec = _writer_plan_and_spec()
    artifact = _result_artifact()
    claim_matrix = PaperWriter().build_claim_evidence_matrix(
        plan,
        spec,
        artifact,
        literature=[
            LiteratureInsight(
                paper_id="context_ref_1",
                title="[Context Summary] Benchmark fallback",
                source="benchmark_context",
                insight="Synthetic benchmark context cannot establish publication novelty.",
            )
        ],
        attempts=[],
        portfolio=None,
        candidates=[],
    )
    candidate = HypothesisCandidate(
        id="candidate_synthetic_literature",
        program_id="program_synthetic_literature",
        rank=1,
        title="Synthetic Literature Candidate",
        hypothesis=plan.hypotheses[0],
        proposed_method=plan.proposed_method,
        rationale="Exercise literature provenance gating.",
        planned_contributions=plan.planned_contributions,
        status="done",
        artifact=artifact,
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    run = AutoResearchRunRead(
        id="run_synthetic_literature_gate",
        project_id="project_synthetic_literature_gate",
        topic=plan.topic,
        status="done",
        task_family="text_classification",
        plan=plan,
        spec=spec,
        candidates=[candidate],
        artifact=artifact,
        literature=[
            LiteratureInsight(
                paper_id="context_ref_1",
                title="[Context Summary] Benchmark fallback",
                source="benchmark_context",
                insight="Synthetic benchmark context cannot establish publication novelty.",
            )
        ],
        claim_evidence_matrix=claim_matrix,
        paper_markdown=(
            "# Synthetic Literature Gate\n\n"
            "## Abstract\nCandidate system scored 0.72 macro F1.\n\n"
            "## Related Work\nSynthetic benchmark context motivates the proxy task [1].\n\n"
            "## Results\nCandidate system scored 0.72 macro F1.\n\n"
            "## References\n[1] [Context Summary] Benchmark fallback.\n"
        ),
        created_at=now,
        updated_at=now,
    )

    novelty = review_publish._build_novelty_assessment(
        run=run,
        selected_candidate_id=candidate.id,
    )
    protocol = build_research_protocol(run)
    audit = build_methodology_audit(run, protocol=protocol)
    findings, evidence, citation_coverage = review_publish._review_findings(
        run=run,
        bundle=None,
        selected_manifest_source="file",
        paper_markdown=run.paper_markdown or "",
        novelty_assessment=novelty,
        benchmark_card=build_benchmark_card(run),
        research_protocol=protocol,
        methodology_audit=audit,
        publication_readiness=build_publication_readiness(
            run,
            paper_markdown=run.paper_markdown or "",
        ),
    )
    review = review_publish.AutoResearchRunReviewRead(
        project_id=run.project_id,
        run_id=run.id,
        generated_at=now,
        overall_status="needs_revision",
        unsupported_claim_risk="medium",
        summary="Synthetic literature regression review.",
        evidence=evidence,
        citation_coverage=citation_coverage,
        novelty_assessment=novelty,
        research_protocol=protocol,
        methodology_audit=audit,
        publication_readiness=build_publication_readiness(
            run,
            paper_markdown=run.paper_markdown or "",
        ),
        scores=review_publish._review_scores(
            run=run,
            bundle=None,
            findings=findings,
            evidence=evidence,
            citation_coverage=citation_coverage,
            selected_manifest_source="file",
        ),
        findings=findings,
        revision_plan=review_publish._revision_plan(findings),
    )

    assert novelty.status == "missing_context"
    assert novelty.compared_paper_count == 0
    assert "No real literature sources were persisted with the run." in {
        item.summary for item in findings
    }
    assert any(
        "real literature sources" in item
        for item in review_publish._semantic_final_publish_blockers(review)
    )


def test_paper_writer_dedupes_literature_context_in_paper_assets() -> None:
    plan, spec = _writer_plan_and_spec()
    artifact = _result_artifact()
    literature = [
        LiteratureInsight(
            paper_id="paper-claim",
            title="Claim Evidence Retrieval",
            year=2025,
            source="semantic_scholar",
            insight="Claim-evidence retrieval needs citation support.",
            method_hint="Claim-evidence retrieval needs citation support.",
            gap_hint="Benchmark reports still duplicate related-work snippets.",
        ),
        LiteratureInsight(
            paper_id="paper-claim",
            title="Claim Evidence Retrieval",
            year=2025,
            source="arxiv",
            insight="Claim-evidence retrieval needs citation support.",
            method_hint="Ledger-aware reranking compares claim support passages.",
            gap_hint="Benchmark reports still duplicate related-work snippets.",
        ),
        LiteratureInsight(
            paper_id="paper-ledger",
            title="Ledger Grounded Writing",
            year=2024,
            source="crossref",
            insight="Ledger grounded writing tracks supported manuscript claims.",
        ),
    ]

    writer = PaperWriter()

    related_block = writer._literature_block(literature)
    assert related_block.count("Claim Evidence Retrieval") == 1
    assert related_block.count("Ledger Grounded Writing") == 1
    assert "[1] Claim Evidence Retrieval" in related_block
    assert "[2] Ledger Grounded Writing" in related_block
    assert related_block.count("Claim-evidence retrieval needs citation support.") == 1
    assert related_block.count("Benchmark reports still duplicate related-work snippets.") == 1
    assert "Ledger-aware reranking compares claim support passages." in related_block

    references = writer._references_block(literature)
    assert references.count("Claim Evidence Retrieval") == 1
    assert references.count("[2] Ledger Grounded Writing") == 1

    bibliography = writer.build_paper_bibliography(literature)
    assert bibliography.count("@misc{ref") == 2
    assert bibliography.count("Claim Evidence Retrieval") == 1
    assert bibliography.count("Claim-evidence retrieval needs citation support.") == 1
    assert bibliography.count("Benchmark reports still duplicate related-work snippets.") == 1

    claim_matrix = writer.build_claim_evidence_matrix(
        plan,
        spec,
        artifact,
        literature=literature,
        attempts=[],
        portfolio=None,
        candidates=[],
    )
    context_entry = next(
        item for item in claim_matrix.entries if item.claim_id == "claim_context_grounding"
    )
    assert [item.label for item in context_entry.evidence] == [
        "Claim Evidence Retrieval",
        "Ledger Grounded Writing",
    ]


def test_paper_writer_sanitizes_repeated_title_and_ir_language(monkeypatch) -> None:
    monkeypatch.setattr(PaperWriter, "_write_full_paper_with_llm", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        PaperWriter,
        "_maybe_refine_with_llm",
        lambda self, *, seed_markdown, **kwargs: seed_markdown,
    )
    benchmark = builtin_benchmark("ir_reranking", topic="claim evidence retrieval")
    spec = build_experiment_spec("ir_reranking", benchmark)
    plan = ResearchPlan(
        topic="claim evidence retrieval",
        title=(
            "Claim Evidence Retrieval: Claim Evidence Retrieval: "
            "Lightweight Reranking With Ledger Grounding"
        ),
        task_family="ir_reranking",
        problem_statement="Autonomous literature agents need retrieval results tied to evidence ledgers.",
        motivation="Unsupported retrieval claims can mislead downstream paper writing.",
        proposed_method="Use lexical overlap, IDF weighting, and ledger-aware reranking signals.",
        research_questions=["Does ledger-aware reranking improve retrieval quality?"],
        hypotheses=["Ledger-aware reranking improves MRR over overlap-only ranking."],
        planned_contributions=["A bounded reranking evaluation tied to evidence ledgers."],
        experiment_outline=["Compare overlap, IDF, and ledger-aware reranking variants."],
    )
    artifact = ResultArtifact(
        status="done",
        summary="Ledger-aware reranking completed on the fixture benchmark.",
        key_findings=["ledger_ranker improved MRR over overlap_ranker"],
        primary_metric="mrr",
        best_system="ledger_ranker",
        objective_system="ledger_ranker",
        objective_score=0.82,
        system_results=[
            SystemMetricResult(system="ledger_ranker", metrics={"mrr": 0.82}),
            SystemMetricResult(system="overlap_ranker", metrics={"mrr": 0.71}),
        ],
        aggregate_system_results=[
            AggregateSystemMetricResult(
                system="ledger_ranker",
                mean_metrics={"mrr": 0.82},
                std_metrics={"mrr": 0.01},
                min_metrics={"mrr": 0.81},
                max_metrics={"mrr": 0.83},
                sample_count=3,
            ),
            AggregateSystemMetricResult(
                system="overlap_ranker",
                mean_metrics={"mrr": 0.71},
                std_metrics={"mrr": 0.01},
                min_metrics={"mrr": 0.70},
                max_metrics={"mrr": 0.72},
                sample_count=3,
            ),
        ],
        tables=[
            ResultTable(
                title="Reranking Results",
                columns=["System", "MRR"],
                rows=[["ledger_ranker", "0.82"], ["overlap_ranker", "0.71"]],
            )
        ],
        environment={"seed_count": 3},
    )

    paper = PaperWriter().write(plan, spec, artifact, literature=[], attempts=[])

    title_line = paper.splitlines()[0]
    assert title_line == "# Claim Evidence Retrieval: Lightweight Reranking With Ledger Grounding"
    assert "classification approaches" not in paper
    assert "classification methods" not in paper
    assert "retrieval and reranking approaches" in paper
    assert "training queries" in paper
    assert "test queries" in paper


def test_operator_console_summary_exposes_final_publish_blockers() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    run = AutoResearchRunRead(
        id="run_console_final_blockers",
        project_id="project_console_final_blockers",
        topic="Console final blocker visibility",
        status="done",
        task_family="text_classification",
        created_at=now,
        updated_at=now,
    )
    publish = AutoResearchPublishPackageRead(
        project_id=run.project_id,
        run_id=run.id,
        package_id="publish_ready_bundle",
        generated_at=now,
        status="blocked",
        publish_ready=False,
        review_bundle_ready=True,
        final_publish_ready=False,
        archive_ready=False,
        blocker_count=0,
        final_blocker_count=2,
        revision_count=1,
        revision_actions=["Attach real retrieved literature before final publish."],
    )

    summary = autoresearch_console._run_summary(
        run=run,
        execution=AutoResearchRunExecutionRead(project_id=run.project_id, run_id=run.id),
        bridge=None,
        review=None,
        review_loop=None,
        publish=publish,
    )

    assert summary.publish_status == "blocked"
    assert summary.review_bundle_ready is True
    assert summary.final_publish_ready is False
    assert summary.archive_ready is False
    assert summary.blocker_count == 0
    assert summary.final_blocker_count == 2
    assert summary.revision_actions == ["Attach real retrieved literature before final publish."]


def test_run_lineage_records_paper_derivation_chain(tmp_path: Path) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    run = AutoResearchRunRead(
        id="run_lineage_derivation",
        project_id="project_lineage_derivation",
        topic="Lineage derivation chain",
        status="done",
        task_family="text_classification",
        created_at=now,
        updated_at=now,
    )

    def asset(name: str) -> AutoResearchRegistryAssetRef:
        return AutoResearchRegistryAssetRef(
            path=str(tmp_path / name),
            exists=True,
            sha256=f"sha-{name}",
        )

    files = AutoResearchRunRegistryFiles(
        root=AutoResearchRegistryAssetRef(path=str(tmp_path), kind="directory", exists=True),
        run_json=asset("run.json"),
        plan_json=asset("plan.json"),
        spec_json=asset("spec.json"),
        artifact_json=asset("artifact.json"),
        generated_code=asset("experiment.py"),
        paper_markdown=asset("paper.md"),
        claim_evidence_matrix_json=asset("claim_evidence_matrix.json"),
        narrative_report_markdown=asset("narrative_report.md"),
        paper_plan_json=asset("paper_plan.json"),
        figure_plan_json=asset("figure_plan.json"),
        benchmark_json=asset("benchmark.json"),
    )

    edges = autoresearch_repository._run_lineage_edges(run=run, run_assets=files)
    derivations = {
        (edge.source_kind, edge.source_id, edge.target_kind, edge.target_id)
        for edge in edges
        if edge.relation == "derived_from"
    }

    assert ("paper", f"{run.id}:paper", "artifact", f"{run.id}:artifact") in derivations
    assert (
        "paper",
        f"{run.id}:paper",
        "claim_evidence_matrix",
        f"{run.id}:claim_evidence_matrix",
    ) in derivations
    assert ("paper", f"{run.id}:paper", "plan", f"{run.id}:plan") in derivations
    assert ("artifact", f"{run.id}:artifact", "generated_code", f"{run.id}:generated_code") in derivations


def test_autoresearch_execute_persists_literature_synthesis(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session_local = _session_local(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "llm_api_key", None)
    project_id = "project_persist_literature_synthesis"
    topic = "Persist literature synthesis"
    synthesis = LiteratureSynthesis(
        themes=[
            LiteratureTheme(
                theme_id="theme_persist",
                label="Persisted synthesis",
                description="The run should retain synthesized literature context.",
            )
        ],
        positioning="Persisted positioning for rebuild and review.",
        novelty_claim="The persisted synthesis keeps novelty framing available after execution.",
    )

    def fake_gather_literature_context(**kwargs):
        del kwargs
        return (
            [],
            [
                LiteratureInsight(
                    title="Persisting Literature Synthesis for Research Agents",
                    year=2025,
                    source="test",
                    insight="Research agents need persisted related-work context.",
                    method_hint="Persist structured synthesis alongside literature insights.",
                    gap_hint="Checkpoint recovery often loses narrative context.",
                )
            ],
            None,
            synthesis,
        )

    def fake_run(
        self,
        *,
        code_filename_prefix: str,
        round_index: int,
        **kwargs,
    ):
        del self, kwargs
        code_path = tmp_path / f"{code_filename_prefix}_{round_index}.py"
        code_path.write_text("# persisted synthesis candidate\n", encoding="utf-8")
        return "persisted_synthesis_strategy", str(code_path), _result_artifact()

    monkeypatch.setattr(
        autoresearch_orchestrator,
        "gather_literature_context",
        fake_gather_literature_context,
    )
    monkeypatch.setattr(autoresearch_orchestrator.AutoExperimentRunner, "run", fake_run)
    monkeypatch.setattr(
        autoresearch_orchestrator.PaperWriter,
        "write",
        lambda self, *args, **kwargs: "# persisted synthesis paper\n\nThe paper cites preserved context [1].\n\n## References\n[1] Test reference.",
    )

    db = session_local()
    try:
        _seed_project(db, project_id, title="Persist Literature Synthesis")
        run = autoresearch_repository.create_run(project_id, topic)
        result = autoresearch_orchestrator.AutoResearchOrchestrator().execute(
            db=db,
            project_id=project_id,
            run_id=run.id,
            topic=topic,
            max_rounds=1,
            candidate_execution_limit=1,
            auto_search_literature=False,
        )
    finally:
        db.close()

    reloaded = autoresearch_repository.load_run(project_id, run.id)

    assert result.status == "done"
    assert result.literature_synthesis is not None
    assert result.literature_synthesis.novelty_claim == synthesis.novelty_claim
    assert reloaded is not None
    assert reloaded.literature_synthesis is not None
    assert reloaded.literature_synthesis.positioning == synthesis.positioning


def test_research_brief_builder_produces_multiple_executable_directions() -> None:
    payload = AutoResearchIdeaRequest.model_validate(_idea_request_payload())

    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-brief",
        payload=payload,
    )

    assert 2 <= brief.direction_count <= 5
    assert len(brief.research_directions) == brief.direction_count
    assert brief.selected_direction_id is not None
    assert brief.selected_hypothesis_id is not None
    assert brief.selection_reason is not None
    assert brief.direction_selection is not None
    assert brief.idea_too_generic is False
    narrowing = brief.scope_narrowing_recommendation.lower()
    assert "task" in narrowing
    assert "dataset" in narrowing
    assert "metric" in narrowing
    assert len(brief.research_questions) == brief.direction_count
    assert len(brief.candidate_hypotheses) == brief.direction_count
    assert brief.hypothesis_count == brief.direction_count
    assert len(brief.hypothesis_bank) == brief.direction_count
    assert brief.hypothesis_bank[0].hypothesis_id == brief.selected_hypothesis_id
    assert brief.direction_selection.rejected_directions
    assert all(item.reasons for item in brief.direction_selection.rejected_directions)
    assert [item.selection_score for item in brief.hypothesis_bank] == sorted(
        [item.selection_score for item in brief.hypothesis_bank],
        reverse=True,
    )
    assert any(
        direction.candidate_dataset in query
        for direction in brief.research_directions
        for query in brief.novelty_search_plan
    )
    assert any("Abandon" in item for item in brief.kill_criteria)

    selected = next(
        item for item in brief.research_directions if item.direction_id == brief.selected_direction_id
    )
    assert selected.required_baselines
    assert selected.candidate_metrics
    assert selected.expected_evidence

    run_request = autoresearch_idea_brief.run_request_from_selected_direction(
        brief,
        payload=payload,
    )
    assert run_request.topic == selected.run_topic
    assert run_request.task_family_hint == selected.task_family
    assert run_request.max_rounds == payload.resource_budget.max_rounds
    assert run_request.candidate_execution_limit == payload.resource_budget.candidate_execution_limit


def test_research_brief_selected_hypothesis_creates_metadata_run(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-hypothesis-run"
    payload = AutoResearchIdeaRequest.model_validate(_idea_request_payload())
    brief = autoresearch_repository.save_research_brief(
        autoresearch_idea_brief.build_research_brief(
            project_id=project_id,
            payload=payload,
        )
    )
    run_request, hypothesis = autoresearch_idea_brief.run_request_from_selected_hypothesis(brief)

    run = autoresearch_repository.create_run(
        project_id,
        run_request.topic,
        request=AutoResearchRunConfig.from_request(run_request),
        brief_id=brief.brief_id,
        hypothesis_id=hypothesis.hypothesis_id,
        direction_selection_reason=brief.selection_reason,
    )
    loaded = autoresearch_repository.load_run(project_id, run.id)

    assert loaded is not None
    assert loaded.brief_id == brief.brief_id
    assert loaded.hypothesis_id == hypothesis.hypothesis_id
    assert loaded.direction_selection_reason == brief.selection_reason
    assert loaded.request is not None
    assert loaded.request.max_rounds == payload.resource_budget.max_rounds
    assert loaded.request.candidate_execution_limit == payload.resource_budget.candidate_execution_limit


def _cached_literature_query(brief) -> str:
    return f'"{brief.original_idea}"'


def test_literature_connectors_reject_unsupported_sources_without_io(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-unsupported-literature-source",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )

    def fail_io(*_args, **_kwargs):
        raise AssertionError("unsupported source must not touch cache or network IO")

    monkeypatch.setattr(autoresearch_literature_connectors, "load_literature_scout_cache", fail_io)
    monkeypatch.setattr(autoresearch_literature_connectors, "save_literature_scout_cache", fail_io)
    monkeypatch.setattr(autoresearch_literature_connectors, "_fetch_connector_response", fail_io)

    papers, statuses = autoresearch_literature_connectors.search_literature_connectors(
        brief,
        search_queries=[_cached_literature_query(brief)],
        sources=["unknown_connector"],
        network_enabled=True,
        cache_enabled=True,
    )

    assert papers == []
    assert len(statuses) == 1
    assert statuses[0].source == "unknown_connector"
    assert statuses[0].query_count == 0
    assert statuses[0].network_request_count == 0
    assert statuses[0].cache_hit_count == 0
    assert statuses[0].error_count == 1
    assert statuses[0].errors == [
        "Unsupported literature connector source: unknown_connector"
    ]


def test_literature_dedup_merges_identifier_and_prefers_real_source() -> None:
    synthetic = AutoResearchLiteratureScoutPaperRead(
        paper_id="fixture:duplicate",
        title="Deduplicated Search Paper",
        source="fixture_offline",
        authors=["Fixture Author"],
        year=2024,
        venue="Fixture Venue",
        abstract="Fixture abstract with macro F1.",
        method="fixture method",
        methods=["fixture method"],
        datasets=["Fixture Dataset"],
        metrics=["macro_f1"],
        reported_results=["Fixture result reports macro F1."],
        known_sota="Fixture baseline note.",
        relevance_score=0.55,
        novelty_risk_signal="medium",
        overlap_score=3,
        shared_terms=["search"],
        source_query="fixture query",
        cache_status="fixture",
        evidence="Fixture evidence.",
    )
    real = AutoResearchLiteratureScoutPaperRead(
        paper_id="arxiv:2401.00001",
        title="Deduplicated Search Paper",
        source="arxiv",
        authors=["Real Author"],
        year=2025,
        venue="arXiv",
        abstract="Real abstract reports state-of-the-art nDCG on a benchmark.",
        url="https://arxiv.org/abs/2401.00001",
        doi="10.0000/dedup-real",
        arxiv_id="2401.00001",
        method="real method",
        methods=["real method"],
        datasets=["Real Benchmark"],
        metrics=["ndcg"],
        reported_results=["Real result reaches state-of-the-art nDCG."],
        known_sota="Real result reaches state-of-the-art nDCG.",
        relevance_score=0.85,
        novelty_risk_signal="high",
        overlap_score=7,
        shared_terms=["search", "benchmark"],
        source_query="real query",
        cache_status="cache_hit",
        evidence="Real evidence.",
    )

    papers = autoresearch_literature_connectors.deduplicate_literature_papers(
        [synthetic, real]
    )

    assert len(papers) == 1
    merged = papers[0]
    assert merged.paper_id == "arxiv:2401.00001"
    assert merged.source == "arxiv"
    assert merged.cache_status == "cache_hit"
    assert merged.doi == "10.0000/dedup-real"
    assert merged.arxiv_id == "2401.00001"
    assert merged.known_sota == "Real result reaches state-of-the-art nDCG."
    assert merged.novelty_risk_signal == "high"
    assert merged.relevance_score == 0.85
    assert set(merged.methods) == {"fixture method", "real method"}
    assert set(merged.datasets) == {"Fixture Dataset", "Real Benchmark"}
    assert set(merged.metrics) == {"macro_f1", "ndcg"}


def _arxiv_cache_fixture() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <title>Evidence-Aware Reranking on Publication Regression Benchmark</title>
    <summary>
      We propose an evidence-aware reranking pipeline for the Publication Regression Benchmark.
      The method compares lexical baselines and reports macro F1 improvements, but leaves
      ablation evidence unresolved. Results approach state-of-the-art macro F1.
    </summary>
    <published>2024-01-03T00:00:00Z</published>
    <author><name>Ada Reviewer</name></author>
    <author><name>Ben Auditor</name></author>
    <arxiv:doi>10.0000/arxiv-fixture</arxiv:doi>
  </entry>
</feed>
"""


def _semantic_scholar_cache_fixture() -> dict[str, object]:
    return {
        "data": [
            {
                "paperId": "S2-P15",
                "title": "Cached Evidence Ledgers for Reranking Experiments",
                "authors": [{"name": "Casey Scholar"}],
                "year": 2025,
                "venue": "ACL Findings",
                "publicationVenue": {"name": "ACL Findings"},
                "abstract": (
                    "The framework uses claim evidence ledgers for reranking experiments on "
                    "Publication Regression Benchmark and reports macro F1 and nDCG."
                ),
                "doi": "10.0000/semantic-fixture",
                "url": "https://example.test/semantic-fixture",
                "externalIds": {"DOI": "10.0000/semantic-fixture", "ArXiv": "2501.09999"},
            }
        ]
    }


def _crossref_cache_fixture() -> dict[str, object]:
    return {
        "message": {
            "items": [
                {
                    "title": ["Crossref Metadata for Evidence-Constrained Reranking"],
                    "author": [{"given": "Dana", "family": "Indexer"}],
                    "published-print": {"date-parts": [[2023, 7, 1]]},
                    "container-title": ["SIGIR Workshop"],
                    "abstract": (
                        "<jats:p>Reports a reranking model on retrieval benchmarks with "
                        "macro F1, nDCG, and baseline comparisons.</jats:p>"
                    ),
                    "DOI": "10.0000/crossref-fixture",
                    "URL": "https://example.test/crossref-fixture",
                }
            ]
        }
    }


def test_literature_connectors_parse_cached_sources_without_network(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-cached-connectors",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    query = _cached_literature_query(brief)
    for source, raw in [
        ("arxiv", _arxiv_cache_fixture()),
        ("semantic_scholar", _semantic_scholar_cache_fixture()),
        ("crossref", _crossref_cache_fixture()),
    ]:
        autoresearch_repository.save_literature_scout_cache(
            brief.project_id,
            source=source,
            query=query,
            limit=2,
            payload={"raw": raw},
        )

    def fail_fetch(*_args, **_kwargs):
        raise AssertionError("network fetch should not run for cached connector tests")

    monkeypatch.setattr(autoresearch_literature_connectors, "_fetch_connector_response", fail_fetch)

    papers, statuses = autoresearch_literature_connectors.search_literature_connectors(
        brief,
        search_queries=[query],
        sources=["arxiv", "semantic_scholar", "crossref"],
        limit_per_source=2,
        network_enabled=False,
    )

    assert {item.source for item in papers} == {"arxiv", "semantic_scholar", "crossref"}
    assert all(status.network_request_count == 0 for status in statuses)
    assert all(status.cache_hit_count == 1 for status in statuses)
    assert all(item.cache_status == "cache_hit" for item in papers)
    assert any(item.arxiv_id == "2401.01234v1" for item in papers)
    assert any(item.doi == "10.0000/semantic-fixture" for item in papers)
    assert any(item.venue == "SIGIR Workshop" for item in papers)
    assert any("macro_f1" in item.metrics for item in papers)
    assert all(item.methods for item in papers)
    assert all(item.relevance_score > 0 for item in papers)


def test_literature_connector_retries_transient_network_errors(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    timeouts: list[object] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return _semantic_scholar_cache_fixture()

    class FakeClient:
        def __init__(self, *, timeout: object) -> None:
            timeouts.append(timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def get(self, url: str, **kwargs):
            calls.append((url, kwargs))
            if len(calls) == 1:
                raise autoresearch_literature_connectors.httpx.TimeoutException(
                    "transient timeout"
                )
            return FakeResponse()

    monkeypatch.setenv("LITERATURE_SCOUT_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("LITERATURE_SCOUT_RETRIES", "2")
    monkeypatch.setenv("LITERATURE_SCOUT_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setattr(autoresearch_literature_connectors.httpx, "Client", FakeClient)

    raw = autoresearch_literature_connectors._fetch_connector_response(
        "semantic_scholar",
        "evidence constrained reranking",
        limit=1,
    )

    assert raw == _semantic_scholar_cache_fixture()
    assert len(calls) == 2
    assert len(timeouts) == 2


def test_literature_connectors_use_cached_full_text_for_structured_extraction(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-cached-full-text",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    query = _cached_literature_query(brief)
    full_text = (
        "The contrastive calibration reranker method evaluates MIMIC Dataset and "
        "Publication Regression Benchmark. It reports nDCG and accuracy. "
        "It achieves state-of-the-art nDCG after evidence ledger filtering."
    )
    autoresearch_repository.save_literature_scout_cache(
        brief.project_id,
        source="arxiv",
        query=query,
        limit=3,
        payload={
            "raw": _arxiv_cache_fixture(),
            "full_text_by_paper": {"arxiv:2401.01234v1": full_text},
        },
    )

    def fail_fetch(*_args, **_kwargs):
        raise AssertionError("full-text cache test must not use network")

    monkeypatch.setattr(autoresearch_literature_connectors, "_fetch_connector_response", fail_fetch)

    papers, statuses = autoresearch_literature_connectors.search_literature_connectors(
        brief,
        search_queries=[query],
        sources=["arxiv"],
        network_enabled=False,
    )

    assert statuses[0].cache_hit_count == 1
    paper = next(item for item in papers if item.paper_id == "arxiv:2401.01234v1")
    assert paper.extraction_level == "full_text"
    assert paper.full_text_available is True
    assert paper.full_text_excerpt is not None
    assert "contrastive calibration reranker" in paper.full_text_excerpt
    assert "MIMIC" in paper.datasets
    assert "ndcg" in paper.metrics
    assert "accuracy" in paper.metrics
    assert any("contrastive calibration" in method for method in paper.methods)
    assert any("state-of-the-art nDCG" in result for result in paper.reported_results)


def test_literature_scout_network_override_respects_brief_web_consent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    payload = _idea_request_payload()
    payload["allow_web"] = False
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-scout-network-consent",
        payload=AutoResearchIdeaRequest.model_validate(payload),
    )

    def fail_fetch(*_args, **_kwargs):
        raise AssertionError("network fetch must not run when brief.allow_web is false")

    monkeypatch.setattr(autoresearch_literature_connectors, "_fetch_connector_response", fail_fetch)

    scouted = autoresearch_literature_scout.scout_and_mine_gaps(
        brief,
        sources=["arxiv"],
        network_enabled=True,
    )

    assert scouted.literature_scout is not None
    assert scouted.literature_scout.network_enabled is False
    assert scouted.literature_scout.source_statuses[0].network_request_count == 0
    assert "arxiv" not in scouted.literature_scout.source_counts


def test_literature_scout_network_results_are_cached(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    payload = _idea_request_payload()
    payload["allow_web"] = True
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-scout-network-cache",
        payload=AutoResearchIdeaRequest.model_validate(payload),
    )
    calls: list[tuple[str, str, int]] = []

    def fake_fetch(source: str, query: str, *, limit: int):
        calls.append((source, query, limit))
        return _semantic_scholar_cache_fixture()

    monkeypatch.setattr(autoresearch_literature_connectors, "_fetch_connector_response", fake_fetch)

    first = autoresearch_literature_scout.scout_and_mine_gaps(
        brief,
        sources=["semantic_scholar"],
        limit_per_source=4,
        network_enabled=True,
    )

    assert first.literature_scout is not None
    assert first.literature_scout.network_enabled is True
    assert first.literature_scout.source_statuses[0].network_request_count == len(calls)
    assert first.literature_scout.source_counts["semantic_scholar"] == 1
    assert any(
        paper.cache_status == "network"
        for paper in first.literature_scout.similar_papers
        if paper.source == "semantic_scholar"
    )

    def fail_fetch(*_args, **_kwargs):
        raise AssertionError("second scout should reuse cached connector responses")

    monkeypatch.setattr(autoresearch_literature_connectors, "_fetch_connector_response", fail_fetch)

    second = autoresearch_literature_scout.scout_and_mine_gaps(
        brief,
        sources=["semantic_scholar"],
        limit_per_source=4,
        network_enabled=False,
    )

    assert second.literature_scout is not None
    assert second.literature_scout.network_enabled is False
    assert second.literature_scout.cache_hit_count == len(calls)
    assert second.literature_scout.source_statuses[0].network_request_count == 0
    assert any(
        paper.cache_status == "cache_hit"
        for paper in second.literature_scout.similar_papers
        if paper.source == "semantic_scholar"
    )


def test_literature_scout_mines_testable_gap_for_brief() -> None:
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-scout",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )

    scouted = autoresearch_literature_scout.scout_and_mine_gaps(brief)

    assert scouted.literature_scout is not None
    assert scouted.gap_miner is not None
    assert scouted.literature_scout.search_queries
    assert scouted.literature_scout.similar_papers
    assert scouted.literature_scout.datasets
    assert scouted.literature_scout.metrics
    assert scouted.gap_miner.gap_candidates
    assert scouted.gap_miner.recommended_narrower_gap is not None
    assert any(item.experimentally_testable for item in scouted.gap_miner.gap_candidates)
    assert all(item.literature_evidence for item in scouted.gap_miner.gap_candidates)


def test_literature_scout_uses_cached_real_sources_for_novelty_graph(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-scout-graph",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    autoresearch_repository.save_literature_scout_cache(
        brief.project_id,
        source="arxiv",
        query=_cached_literature_query(brief),
        limit=3,
        payload={"raw": _arxiv_cache_fixture()},
    )

    scouted = autoresearch_literature_scout.scout_and_mine_gaps(brief)

    assert scouted.literature_scout is not None
    assert scouted.literature_scout.network_enabled is False
    assert scouted.literature_scout.cache_hit_count == 1
    assert scouted.literature_scout.source_counts["arxiv"] == 1
    real_insights = autoresearch_literature_scout.literature_insights_from_scout(
        scouted.literature_scout
    )
    assert real_insights
    assert all(item.source != "fixture_offline" for item in real_insights)

    spec, benchmark = _external_publication_spec()
    run = _readiness_run(
        spec=spec,
        benchmark=benchmark,
        artifact=_publication_artifact(include_ablation=True, seed_count=5),
    ).model_copy(
        update={
            "literature": real_insights,
            "literature_synthesis": None,
        }
    )

    graph = build_literature_graph(run)
    validation = build_novelty_validation(run, literature_graph=graph)

    assert graph.real_paper_count == len(real_insights)
    assert graph.known_sota
    assert validation.gap_validity == "valid"
    assert validation.complete is True


def test_autoresearch_execute_reuses_cached_brief_scout_before_legacy_search(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session_local = _session_local(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "llm_api_key", None)
    project_id = "project-brief-scout-execute"
    payload = _idea_request_payload()
    payload["allow_web"] = True
    brief = autoresearch_idea_brief.build_research_brief(
        project_id=project_id,
        payload=AutoResearchIdeaRequest.model_validate(payload),
    )
    autoresearch_repository.save_literature_scout_cache(
        brief.project_id,
        source="arxiv",
        query=_cached_literature_query(brief),
        limit=3,
        payload={"raw": _arxiv_cache_fixture()},
    )
    brief = autoresearch_repository.save_research_brief(
        autoresearch_literature_scout.scout_and_mine_gaps(
            brief,
            sources=["arxiv"],
            network_enabled=False,
        )
    )
    observed: dict[str, object] = {}

    def fake_gather_literature_context(**kwargs):
        observed["auto_search"] = kwargs["auto_search"]
        return [], [], {}, None

    def fake_run(
        self,
        *,
        code_filename_prefix: str,
        round_index: int,
        **kwargs,
    ):
        del self, kwargs
        code_path = tmp_path / f"{code_filename_prefix}_{round_index}.py"
        code_path.write_text("# cached brief scout candidate\n", encoding="utf-8")
        return "cached_brief_scout_strategy", str(code_path), _result_artifact()

    monkeypatch.setattr(
        autoresearch_orchestrator,
        "gather_literature_context",
        fake_gather_literature_context,
    )
    monkeypatch.setattr(autoresearch_orchestrator.AutoExperimentRunner, "run", fake_run)
    monkeypatch.setattr(
        autoresearch_orchestrator.PaperWriter,
        "write",
        lambda self, *args, **kwargs: "# cached scout paper\n\nThe paper cites preserved context [1].",
    )

    db = session_local()
    try:
        _seed_project(db, project_id, title="Cached Brief Scout Execute")
        run_request, hypothesis = autoresearch_idea_brief.run_request_from_selected_hypothesis(brief)
        run = autoresearch_repository.create_run(
            project_id,
            run_request.topic,
            request=AutoResearchRunConfig(
                task_family_hint=run_request.task_family_hint,
                auto_search_literature=True,
                max_rounds=1,
                candidate_execution_limit=1,
            ),
            brief_id=brief.brief_id,
            hypothesis_id=hypothesis.hypothesis_id,
            direction_selection_reason=brief.selection_reason,
        )
        result = autoresearch_orchestrator.AutoResearchOrchestrator().execute(
            db=db,
            project_id=project_id,
            run_id=run.id,
            topic=run.topic,
            task_family_hint=run_request.task_family_hint,
            max_rounds=1,
            candidate_execution_limit=1,
            auto_search_literature=True,
        )
    finally:
        db.close()

    assert observed["auto_search"] is False
    assert result.literature
    assert {item.source for item in result.literature} == {"arxiv"}


def test_research_brief_repository_persists_and_console_summarizes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-idea-console"
    brief = autoresearch_repository.save_research_brief(
        autoresearch_idea_brief.build_research_brief(
            project_id=project_id,
            payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
        )
    )
    brief = autoresearch_repository.save_research_brief(
        autoresearch_literature_scout.scout_and_mine_gaps(brief)
    )

    assert brief.brief_path is not None
    assert Path(brief.brief_path).is_file()

    loaded = autoresearch_repository.load_research_brief(project_id, brief.brief_id)
    listed = autoresearch_repository.list_research_briefs(project_id)

    assert loaded is not None
    assert loaded.brief_id == brief.brief_id
    assert listed
    assert listed[0].brief_id == brief.brief_id

    console = autoresearch_console.build_operator_console(project_id)

    assert console.brief_count == 1
    assert console.latest_brief_id == brief.brief_id
    assert console.latest_brief_original_idea == brief.original_idea
    assert console.latest_brief_hypothesis_count == brief.direction_count
    assert console.latest_brief_selected_direction_id == brief.selected_direction_id
    assert console.latest_brief_selected_hypothesis_id == brief.selected_hypothesis_id
    assert console.latest_brief_next_action == "create_run"
    assert console.latest_brief_literature_scout_ready is True
    assert console.latest_brief_gap_count > 0
    assert console.latest_brief_recommended_gap == brief.gap_miner.recommended_narrower_gap
    assert console.actions.create_idea_brief is True
    assert console.actions.create_run_from_brief is True


def test_experiment_factory_builds_executable_plan_from_selected_hypothesis() -> None:
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-factory-plan",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    hypothesis = autoresearch_idea_brief.selected_hypothesis_from_brief(brief)

    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id=brief.project_id,
        brief=brief,
        hypothesis=hypothesis,
    )

    assert plan.brief_id == brief.brief_id
    assert plan.hypothesis_id == hypothesis.hypothesis_id
    assert plan.baseline_job_count >= 1
    assert plan.candidate_job_count == 1
    assert plan.ablation_job_count >= 1
    assert plan.seed_job_count >= 3
    assert plan.sweep_job_count >= 1
    assert plan.bridge_ready is True
    assert plan.toy_backend_supported is True
    assert "result_artifact.json" in plan.expected_artifacts
    assert all(job.command.startswith("scholarflow toy-run") for job in plan.jobs)
    candidate = next(job for job in plan.jobs if job.job_kind == "candidate_method")
    assert candidate.dependencies
    assert all(dep.startswith("job_baseline_") for dep in candidate.dependencies)
    assert all(job.retry_policy.max_retries >= 1 for job in plan.jobs)


def test_experiment_factory_toy_execution_builds_evidence_ledger() -> None:
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-factory-execute",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id=brief.project_id,
        brief=brief,
    )

    execution = autoresearch_experiment_factory.execute_toy_experiment_factory(plan)

    assert execution.result_artifact.status == "done"
    assert execution.result_artifact.objective_system == "candidate_method"
    assert execution.result_artifact.significance_tests
    assert execution.environment_manifest is not None
    assert execution.environment_manifest.executor_mode == "toy"
    assert execution.environment_manifest.backend == "auto"
    assert len(execution.materialized_jobs) == plan.job_count
    assert all(job.status == "done" for job in execution.materialized_jobs)
    assert all(job.output_refs for job in execution.materialized_jobs)
    assert all(job.repair_classification == "none" for job in execution.materialized_jobs)
    assert all(job.failure_classification == "none" for job in execution.materialized_jobs)
    assert all(job.started_at_step >= 1 for job in execution.materialized_jobs)
    assert all(job.completed_at_step == job.started_at_step for job in execution.materialized_jobs)
    assert all(job.runtime_contract["status"] == "done" for job in execution.materialized_jobs)
    assert all(job.runtime_contract["expected_outputs"] == job.expected_outputs for job in execution.materialized_jobs)
    assert all(job.runtime_contract["timeout_seconds"] == plan.execution_backend.timeout_seconds for job in execution.materialized_jobs)
    assert (
        execution.result_artifact.environment["environment_manifest_id"]
        == execution.environment_manifest.manifest_id
    )
    assert execution.result_artifact.environment["materialized_job_count"] == plan.job_count
    assert execution.evidence_ledger.complete is True
    assert execution.evidence_ledger.entry_count >= plan.baseline_job_count + plan.ablation_job_count
    assert any(item.evidence_kind == "baseline" for item in execution.evidence_ledger.entries)
    assert any(item.evidence_kind == "ablation" for item in execution.evidence_ledger.entries)
    assert any(
        item.artifact_ref == "experiment_factory_environment_manifest_json"
        for item in execution.evidence_ledger.entries
    )
    assert any(
        item.artifact_ref == "experiment_factory_materialized_jobs_json"
        for item in execution.evidence_ledger.entries
    )
    assert execution.repair_plan is not None
    assert execution.repair_plan.actions == ["none"]


def test_experiment_factory_executes_cached_scifact_claim_evidence_benchmark(
    monkeypatch,
    tmp_path: Path,
) -> None:
    payload = {
        "name": "Cached SciFact Claim Evidence Benchmark",
        "description": "Offline cached SciFact-style claim-evidence benchmark for factory execution.",
        "corpus": [
            {
                "doc_id": "support_train",
                "title": "Training Evidence",
                "abstract": ["Training improves retrieval quality for supported claims."],
            },
            {
                "doc_id": "support_test",
                "title": "Ledger Evidence Support",
                "abstract": ["Claim evidence ledgers improve support retrieval for scientific writing agents."],
            },
            {
                "doc_id": "support_distractor",
                "title": "Writing Fluency",
                "abstract": ["Writing fluency improves readability without evidence retrieval support."],
            },
            {
                "doc_id": "refute_test",
                "title": "Unsupported Claim Refutation",
                "abstract": ["Unsupported claim generation does not improve evidence verification accuracy."],
            },
            {
                "doc_id": "refute_distractor",
                "title": "Verification Survey",
                "abstract": ["A survey describes verification tasks without testing unsupported claim generation."],
            },
            {
                "doc_id": "nei_test",
                "title": "Background Evidence",
                "abstract": ["Background work studies citation graphs but not autonomous claim repair."],
            },
        ],
        "claims": [
            {
                "id": "train_support",
                "claim": "Training improves retrieval quality.",
                "candidate_doc_ids": ["support_train", "support_distractor"],
                "evidence": {"support_train": [{"label": "SUPPORT"}]},
            },
            {
                "id": "test_support",
                "claim": "Claim evidence ledgers improve support retrieval.",
                "candidate_doc_ids": ["support_test", "support_distractor", "nei_test"],
                "evidence": {"support_test": [{"label": "SUPPORT"}]},
            },
            {
                "id": "test_refute",
                "claim": "Unsupported claim generation improves evidence verification accuracy.",
                "candidate_doc_ids": ["refute_test", "refute_distractor", "support_distractor"],
                "evidence": {"refute_test": [{"label": "REFUTE"}]},
            },
            {
                "id": "test_nei",
                "claim": "Blue light cures migraine.",
                "candidate_doc_ids": ["nei_test", "support_distractor", "refute_distractor"],
                "label": "NEI",
                "evidence": {},
            },
        ],
        "split": {"train": ["train_support"], "test": ["test_support", "test_refute", "test_nei"]},
    }
    cache_path = tmp_path / "cached_scifact_factory.json"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        autoresearch_ingestion,
        "_fetch_remote_text",
        lambda url: pytest.fail(f"factory benchmark must load from cache, not network: {url}"),
    )
    benchmark = autoresearch_ingestion.resolve_benchmark(
        topic="claim evidence retrieval and verification for scientific writing agents",
        task_family_hint="ir_reranking",
        benchmark_source=BenchmarkSource(
            kind="scifact_json",
            name="Cached SciFact Factory",
            file_path=str(cache_path),
            dataset_id="allenai/scifact",
            revision="factory-fixture-v1",
            license="cc-by-nc",
        ),
    )
    spec = build_experiment_spec("ir_reranking", benchmark).model_copy(update={"seeds": [0, 1, 2]})
    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id="project-factory-cached-scifact",
        run=AutoResearchRunRead(
            id="run-factory-cached-scifact",
            project_id="project-factory-cached-scifact",
            topic="Cached SciFact factory execution",
            status="running",
            task_family="ir_reranking",
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            spec=spec,
            benchmark=benchmark.source,
            execution_backend=ExecutionBackendSpec(kind="local", timeout_seconds=30),
        ),
    )

    execution = autoresearch_experiment_factory.execute_cached_claim_evidence_experiment_factory(
        plan,
        benchmark_payload=benchmark.payload,
        executor_mode="local",
    )

    assert execution.result_artifact.status == "done"
    assert execution.environment_manifest.executor_mode == "local"
    assert execution.result_artifact.environment["factory_executor_mode"] == "cached_claim_evidence_benchmark"
    assert execution.result_artifact.objective_system == "ledger_aware_ranker"
    objective_metrics = next(
        item.mean_metrics
        for item in execution.result_artifact.aggregate_system_results
        if item.system == "ledger_aware_ranker"
    )
    assert {"mrr", "recall_at_1", "ndcg_at_10", "recall_at_10", "evidence_coverage"}.issubset(
        objective_metrics
    )
    assert {"verification_accuracy", "unsupported_claim_precision", "unsupported_claim_recall", "abstention_accuracy"}.issubset(
        objective_metrics
    )
    objective_aggregate = next(
        item
        for item in execution.result_artifact.aggregate_system_results
        if item.system == "ledger_aware_ranker"
    )
    assert objective_aggregate.sample_count == 3
    assert "mrr" in objective_aggregate.confidence_intervals
    assert objective_aggregate.std_metrics["mrr"] >= 0.0
    assert execution.result_artifact.significance_tests
    significance = execution.result_artifact.significance_tests[0]
    assert significance.method == "paired_sign_flip_exact"
    assert significance.sample_count == 3
    assert "wins=" in significance.detail
    assert execution.result_artifact.outputs["paired_query_comparisons"]
    assert execution.result_artifact.outputs["paired_sign_test"]["sample_count"] == 3
    assert execution.result_artifact.outputs["retrieval_evidence_ledger"]
    assert execution.result_artifact.outputs["objective_query_diagnostics"]
    assert len(execution.materialized_jobs) == plan.job_count
    assert all(job.status == "done" for job in execution.materialized_jobs)
    assert any(
        item.evidence_id.startswith("evidence_retrieval_")
        for item in execution.evidence_ledger.entries
    )
    assert execution.evidence_ledger.complete is True
    assert execution.repair_plan is not None
    assert execution.repair_plan.actions == ["none"]


def test_experiment_factory_external_import_can_complete_ledger() -> None:
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-factory-import-complete",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id=brief.project_id,
        brief=brief,
    )

    execution = autoresearch_experiment_factory.execute_imported_experiment_factory(
        plan,
        summary="External backend completed candidate, baseline, ablation, and seed evidence.",
        primary_metric="macro_f1",
        objective_system="candidate_method",
        objective_score=0.76,
        baseline_system="keyword_baseline",
        baseline_score=0.63,
        key_findings=["External candidate beat the imported baseline."],
        ablation_scores={"without_evidence_features": 0.71},
        seed_count=3,
        significance_p_value=0.031,
        notes="Imported from deterministic regression fixture.",
    )

    assert execution.environment_manifest is not None
    assert execution.environment_manifest.executor_mode == "external_import"
    assert execution.result_artifact.status == "done"
    assert execution.result_artifact.environment["external_imported"] is True
    assert execution.result_artifact.significance_tests
    assert len(execution.materialized_jobs) == plan.job_count
    assert all(job.status == "done" for job in execution.materialized_jobs)
    assert all(job.repair_classification == "none" for job in execution.materialized_jobs)
    assert execution.evidence_ledger.complete is True
    assert execution.repair_plan is not None
    assert execution.repair_plan.actions == ["none"]


def test_experiment_factory_maps_imported_artifact_to_ledger() -> None:
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-factory-import-artifact",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id=brief.project_id,
        brief=brief,
    )
    artifact = autoresearch_experiment_factory.result_artifact_from_external_import(
        summary="Bridge backend returned candidate, baseline, ablation, and seed evidence.",
        primary_metric="macro_f1",
        objective_system="candidate_method",
        objective_score=0.78,
        baseline_system="keyword_baseline",
        baseline_score=0.64,
        key_findings=["Bridge candidate beat the imported baseline."],
        ablation_scores={"without_evidence_features": 0.72},
        seed_count=3,
        significance_p_value=0.027,
        notes="Imported from bridge fixture.",
    )

    execution = autoresearch_experiment_factory.execute_imported_artifact_experiment_factory(
        plan,
        artifact=artifact,
        executor_mode="bridge",
    )

    assert execution.environment_manifest is not None
    assert execution.environment_manifest.executor_mode == "bridge"
    assert execution.result_artifact.environment["executor_mode"] == "external_import"
    assert execution.result_artifact.environment["factory_executor_mode"] == "bridge"
    assert execution.result_artifact.environment["external_imported"] is True
    assert len(execution.materialized_jobs) == plan.job_count
    assert all(job.status == "done" for job in execution.materialized_jobs)
    assert execution.evidence_ledger.complete is True
    assert execution.repair_plan is not None
    assert execution.repair_plan.actions == ["none"]


def test_bridge_ingest_persists_factory_evidence_ledger(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    plan, spec = _writer_plan_and_spec()
    spec = enforce_publication_protocol(spec)
    artifact = _result_artifact()
    candidate = HypothesisCandidate(
        id="candidate_bridge_factory",
        program_id="program_bridge_factory",
        rank=1,
        title="Bridge Factory Candidate",
        hypothesis=plan.hypotheses[0],
        proposed_method=plan.proposed_method,
        rationale="Exercise bridge-to-factory evidence mapping.",
        status="running",
    )
    portfolio = PortfolioSummary(
        status="running",
        total_candidates=1,
        candidate_rankings=[candidate.id],
        selected_candidate_id=candidate.id,
        selection_policy="bridge import fixture",
        decision_summary="Waiting for bridge import fixture.",
    )
    project_id = "project-bridge-factory"
    run_id = "run-bridge-factory"
    bridge_config = AutoResearchExperimentBridgeConfig(
        enabled=True,
        notification_hooks=[],
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    run = autoresearch_repository.save_run(
        AutoResearchRunRead(
            id=run_id,
            project_id=project_id,
            topic=plan.topic,
            status="running",
            request=AutoResearchRunConfig(experiment_bridge=bridge_config),
            task_family="text_classification",
            plan=plan,
            spec=spec,
            candidates=[candidate],
            portfolio=portfolio,
            artifact=artifact,
            created_at=now,
            updated_at=now,
        )
    )
    handoff_dir = Path(autoresearch_bridge._handoff_root(project_id, run_id)) / "session_bridge_factory"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    code_path = handoff_dir / "candidate.py"
    manifest_path = handoff_dir / "manifest.json"
    instructions_path = handoff_dir / "instructions.md"
    result_path = handoff_dir / "result_artifact.json"
    code_path.write_text("print('bridge fixture')\n", encoding="utf-8")
    manifest_path.write_text("{}", encoding="utf-8")
    instructions_path.write_text("bridge fixture", encoding="utf-8")
    session = autoresearch_bridge.AutoResearchBridgeSessionRead(
        session_id="session_bridge_factory",
        created_at=now,
        updated_at=now,
        status="waiting_result",
        candidate_id=candidate.id,
        candidate_title=candidate.title,
        round_index=1,
        goal="external_bridge_result",
        strategy="bridge_import",
        handoff_dir=str(handoff_dir),
        manifest_path=str(manifest_path),
        instructions_path=str(instructions_path),
        code_path=str(code_path),
        result_path=str(result_path),
    )
    state = autoresearch_bridge.AutoResearchExperimentBridgeRead(
        project_id=project_id,
        run_id=run_id,
        enabled=True,
        config=bridge_config,
        persisted_path=str(autoresearch_bridge.bridge_state_path(project_id, run_id)),
        active_session_id=session.session_id,
        sessions=[session],
    )
    autoresearch_bridge.bridge_state_path(project_id, run_id).write_text(
        state.model_dump_json(indent=2),
        encoding="utf-8",
    )
    bridge_artifact = autoresearch_experiment_factory.result_artifact_from_external_import(
        summary="Bridge backend returned complete factory evidence.",
        primary_metric=artifact.primary_metric,
        objective_system="candidate_method",
        objective_score=0.79,
        baseline_system="keyword_baseline",
        baseline_score=0.62,
        key_findings=["Bridge candidate beat the imported baseline."],
        ablation_scores={"without_evidence_features": 0.73},
        seed_count=3,
        significance_p_value=0.024,
    )

    updated = autoresearch_orchestrator.AutoResearchOrchestrator().ingest_bridge_result(
        project_id=run.project_id,
        run_id=run.id,
        session_id=session.session_id,
        artifact=bridge_artifact,
    )

    assert updated.experiment_factory_plan is not None
    assert updated.experiment_factory_environment_manifest is not None
    assert updated.experiment_factory_environment_manifest.executor_mode == "bridge"
    assert updated.experiment_factory_materialized_jobs
    assert updated.evidence_ledger is not None
    assert updated.evidence_ledger.complete is True
    assert updated.experiment_factory_repair_plan is not None
    assert updated.experiment_factory_repair_plan.actions == ["none"]
    loaded = autoresearch_repository.load_run(project_id, run_id)
    assert loaded is not None
    assert loaded.evidence_ledger is not None
    assert Path(loaded.evidence_ledger_path or "").is_file()


def test_experiment_factory_external_import_classifies_missing_evidence() -> None:
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-factory-import-repair",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id=brief.project_id,
        brief=brief,
    )

    execution = autoresearch_experiment_factory.execute_imported_experiment_factory(
        plan,
        summary="External backend only returned candidate metrics.",
        primary_metric="macro_f1",
        objective_system="candidate_method",
        objective_score=0.72,
        seed_count=1,
    )

    assert execution.environment_manifest is not None
    assert execution.environment_manifest.executor_mode == "external_import"
    failed_by_kind = {
        job.job_kind: job.repair_classification
        for job in execution.materialized_jobs
        if job.status == "failed"
    }
    assert failed_by_kind["baseline"] == "add_missing_baseline"
    assert failed_by_kind["ablation"] == "add_missing_ablation"
    assert failed_by_kind["seed"] == "increase_seed_count"
    failed_classes = {
        job.job_kind: job.failure_classification
        for job in execution.materialized_jobs
        if job.status == "failed"
    }
    assert failed_classes["baseline"] == "missing_baseline_outputs"
    assert failed_classes["ablation"] == "missing_ablation_outputs"
    assert failed_classes["seed"] == "insufficient_statistics_outputs"
    assert all(
        job.runtime_contract["status"] == job.status
        for job in execution.materialized_jobs
    )
    assert all(
        job.completed_at_step == job.started_at_step
        for job in execution.materialized_jobs
    )
    assert execution.evidence_ledger.complete is False
    assert execution.repair_plan is not None
    assert {
        "add_missing_baseline",
        "add_missing_ablation",
        "increase_seed_count",
    }.issubset(set(execution.repair_plan.actions))


def test_experiment_factory_materializes_docker_handoff_without_claim_support() -> None:
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-factory-materialize-docker",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id=brief.project_id,
        brief=brief,
    ).model_copy(
        update={
            "execution_backend": ExecutionBackendSpec(
                kind="docker",
                docker_image="scholarflow/factory-fixture:latest",
                timeout_seconds=120,
            )
        }
    )

    execution = autoresearch_experiment_factory.materialize_factory_execution(
        plan,
        executor_mode="docker",
    )

    assert execution.environment_manifest is not None
    assert execution.environment_manifest.executor_mode == "docker"
    assert execution.environment_manifest.backend == "docker"
    assert execution.environment_manifest.docker_image == "scholarflow/factory-fixture:latest"
    assert execution.result_artifact.status == "queued"
    assert len(execution.materialized_jobs) == plan.job_count
    assert all(job.status == "planned" for job in execution.materialized_jobs)
    assert all(job.executor_mode == "docker" for job in execution.materialized_jobs)
    assert all(job.output_refs == [] for job in execution.materialized_jobs)
    assert all(job.failure_classification == "planned" for job in execution.materialized_jobs)
    assert all(job.completed_at_step is None for job in execution.materialized_jobs)
    assert all(job.runtime_contract["executor_mode"] == "docker" for job in execution.materialized_jobs)
    assert all(job.runtime_contract["status"] == "planned" for job in execution.materialized_jobs)
    assert execution.evidence_ledger.complete is False
    assert "Materialized execution has no completed result artifact." in execution.evidence_ledger.blockers
    assert execution.repair_plan is None


def test_experiment_factory_external_import_classifies_runtime_failure() -> None:
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-factory-import-runtime-failure",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id=brief.project_id,
        brief=brief,
    )

    execution = autoresearch_experiment_factory.execute_imported_experiment_factory(
        plan,
        summary="External backend failed before producing an objective score.",
        primary_metric="macro_f1",
        objective_system="candidate_method",
        objective_score=None,
    )

    assert execution.result_artifact.status == "failed"
    assert any(
        job.repair_classification == "rerun_failed_job"
        for job in execution.materialized_jobs
        if job.job_kind == "candidate_method"
    )
    assert execution.evidence_ledger.complete is False
    assert "Materialized execution has runtime job failures." in execution.evidence_ledger.blockers
    assert execution.repair_plan is not None
    assert "rerun_failed_job" in execution.repair_plan.actions


def test_experiment_factory_external_import_records_reported_partial_runtime_failure() -> None:
    brief = autoresearch_idea_brief.build_research_brief(
        project_id="project-factory-import-partial-runtime-failure",
        payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
    )
    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id=brief.project_id,
        brief=brief,
    )
    failed_sweep_job = next(job for job in plan.jobs if job.job_kind == "sweep")

    execution = autoresearch_experiment_factory.execute_imported_experiment_factory(
        plan,
        summary="External backend imported candidate, baseline, and ablation metrics, but one sweep job failed.",
        primary_metric="macro_f1",
        objective_system="candidate_method",
        objective_score=0.77,
        baseline_system="keyword_baseline",
        baseline_score=0.62,
        key_findings=["External candidate beat the imported baseline."],
        ablation_scores={"without_evidence_features": 0.71},
        seed_count=3,
        significance_p_value=0.029,
        failed_job_ids=[failed_sweep_job.job_id],
        runtime_failure_notes=[
            "Sweep summary crashed after primary candidate evidence was imported.",
            "Sweep summary crashed after primary candidate evidence was imported.",
        ],
    )

    jobs_by_id = {job.job_id: job for job in execution.materialized_jobs}
    failed_job = jobs_by_id[failed_sweep_job.job_id]

    assert execution.result_artifact.status == "done"
    assert failed_job.status == "failed"
    assert failed_job.repair_classification == "rerun_failed_job"
    assert failed_job.output_refs == []
    assert all(
        job.status == "done"
        for job_id, job in jobs_by_id.items()
        if job_id != failed_sweep_job.job_id
    )
    assert execution.result_artifact.environment["reported_failed_job_ids"] == [
        failed_sweep_job.job_id
    ]
    assert execution.result_artifact.environment["failed_materialized_job_kinds"] == ["sweep"]
    assert execution.result_artifact.environment["runtime_failure_notes"] == [
        "Sweep summary crashed after primary candidate evidence was imported."
    ]
    assert execution.evidence_ledger.complete is False
    assert "Materialized execution has runtime job failures." in execution.evidence_ledger.blockers
    assert execution.repair_plan is not None
    assert execution.repair_plan.actions == ["rerun_failed_job"]


def test_experiment_factory_artifacts_persist_on_run(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-factory-persist"
    brief = autoresearch_repository.save_research_brief(
        autoresearch_idea_brief.build_research_brief(
            project_id=project_id,
            payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
        )
    )
    run_request, hypothesis = autoresearch_idea_brief.run_request_from_selected_hypothesis(brief)
    run = autoresearch_repository.create_run(
        project_id,
        run_request.topic,
        request=AutoResearchRunConfig.from_request(run_request),
        brief_id=brief.brief_id,
        hypothesis_id=hypothesis.hypothesis_id,
        direction_selection_reason=brief.selection_reason,
    )
    plan = autoresearch_experiment_factory.build_experiment_factory_plan(
        project_id=project_id,
        brief=brief,
        hypothesis=hypothesis,
        run=run,
    )
    execution = autoresearch_experiment_factory.execute_toy_experiment_factory(plan)
    saved = autoresearch_repository.save_run(
        run.model_copy(
            update={
                "status": "done",
                "experiment_factory_plan": execution.execution_plan,
                "experiment_factory_environment_manifest": execution.environment_manifest,
                "experiment_factory_materialized_jobs": execution.materialized_jobs,
                "artifact": execution.result_artifact,
                "evidence_ledger": execution.evidence_ledger,
                "experiment_factory_repair_plan": execution.repair_plan,
            }
        )
    )
    loaded = autoresearch_repository.load_run(project_id, run.id)
    registry = autoresearch_repository.load_run_registry(project_id, run.id)
    bundles = autoresearch_repository.load_run_bundle_index(project_id, run.id)

    assert loaded is not None
    assert loaded.experiment_factory_plan is not None
    assert loaded.experiment_factory_environment_manifest is not None
    assert loaded.experiment_factory_materialized_jobs
    assert loaded.evidence_ledger is not None
    assert loaded.experiment_factory_repair_plan is not None
    assert loaded.experiment_factory_plan_path is not None
    assert loaded.experiment_factory_environment_manifest_path is not None
    assert loaded.experiment_factory_materialized_jobs_path is not None
    assert loaded.evidence_ledger_path is not None
    assert loaded.experiment_factory_repair_plan_path is not None
    assert Path(loaded.experiment_factory_plan_path).is_file()
    assert Path(loaded.experiment_factory_environment_manifest_path).is_file()
    assert Path(loaded.experiment_factory_materialized_jobs_path).is_file()
    assert Path(loaded.evidence_ledger_path).is_file()
    assert Path(loaded.experiment_factory_repair_plan_path).is_file()
    assert saved.artifact is not None
    assert registry is not None
    assert registry.files.experiment_factory_plan_json is not None
    assert registry.files.experiment_factory_environment_manifest_json is not None
    assert registry.files.experiment_factory_materialized_jobs_json is not None
    assert registry.files.evidence_ledger_json is not None
    assert registry.files.experiment_factory_repair_plan_json is not None
    assert bundles is not None
    roles = {asset.role for bundle in bundles.bundles for asset in bundle.assets}
    assert "run_experiment_factory_plan_json" in roles
    assert "run_experiment_factory_environment_manifest_json" in roles
    assert "run_experiment_factory_materialized_jobs_json" in roles
    assert "run_evidence_ledger_json" in roles
    assert "run_experiment_factory_repair_plan_json" in roles


def _stable_project_artifact(score: float) -> ResultArtifact:
    return _result_artifact().model_copy(
        update={
            "objective_score": score,
            "significance_tests": [
                SignificanceTestResult(
                    scope="system",
                    metric="macro_f1",
                    candidate="candidate_system",
                    comparator="keyword_baseline",
                    comparison_family="project_factory",
                    family_size=1,
                    alternative="greater",
                    method="paired_sign_flip_exact",
                    p_value=0.0312,
                    adjusted_p_value=0.0312,
                    correction="holm_bonferroni",
                    effect_size=0.11,
                    significant=True,
                    sample_count=3,
                    detail="Stable deterministic comparison for project-level paper orchestration.",
                )
            ],
        }
    )


def test_project_paper_orchestrator_keeps_single_run_to_technical_report(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-paper-single"
    brief = autoresearch_repository.save_research_brief(
        autoresearch_idea_brief.build_research_brief(
            project_id=project_id,
            payload=AutoResearchIdeaRequest.model_validate(_idea_request_payload()),
        )
    )
    run = autoresearch_repository.create_run(
        project_id,
        "Shared evidence-aware reranking benchmark",
        request=AutoResearchRunConfig(task_family_hint="ir_reranking"),
        brief_id=brief.brief_id,
        hypothesis_id=brief.selected_hypothesis_id,
        direction_selection_reason=brief.selection_reason,
    )
    autoresearch_repository.save_run(
        run.model_copy(
            update={
                "status": "done",
                "artifact": _stable_project_artifact(0.72),
            }
        )
    )

    orchestration = autoresearch_project_paper_orchestrator.build_project_paper_orchestration(project_id)

    assert orchestration.latest_brief_id == brief.brief_id
    assert orchestration.selected_run_count == 1
    assert orchestration.should_write_paper is True
    assert orchestration.project_level_paper_allowed is False
    assert orchestration.paper_decision == "technical_report"
    assert orchestration.source_strategy == "single_run_report"
    assert orchestration.conclusion_ledger.conditional_conclusions
    assert orchestration.supported_core_claim_count == orchestration.core_claim_count
    assert any("Only one completed run" in item for item in orchestration.warnings)
    assert orchestration.project_paper_ready is True
    assert orchestration.project_paper_path is not None
    assert Path(orchestration.project_paper_path).is_file()
    assert orchestration.project_paper_missing_sections == []
    assert set(orchestration.project_paper_sections) == set(
        autoresearch_project_paper_orchestrator.PROJECT_PAPER_REQUIRED_SECTIONS
    )
    paper_markdown = Path(orchestration.project_paper_path).read_text(encoding="utf-8")
    assert "## Abstract" in paper_markdown
    assert "## Research Question" in paper_markdown
    assert "## Benchmark And Data" in paper_markdown
    assert "## Experimental Setup" in paper_markdown
    assert "## Negative Evidence" in paper_markdown
    assert "## Reproducibility" in paper_markdown
    assert "Artifact evidence map:" in paper_markdown
    assert "submission_package/experiment_repair_index.json" in paper_markdown
    assert "submission_package/statistics_report.json" in paper_markdown
    assert "submission_package/negative_evidence_report.json" in paper_markdown
    assert "submission_package/benchmark_provenance_manifest.json" in paper_markdown
    assert "paper_sources/paper_compiler_evidence.json" in paper_markdown
    assert "## References" in paper_markdown
    assert run.id in paper_markdown
    assert orchestration.project_paper_sources_dir is not None
    sources_dir = Path(orchestration.project_paper_sources_dir)
    assert sources_dir.is_dir()
    assert Path(orchestration.project_paper_sources_manifest_path).is_file()
    assert Path(orchestration.project_paper_compile_report_path).is_file()
    assert Path(orchestration.project_paper_latex_path).is_file()
    assert Path(orchestration.project_paper_bibliography_path).is_file()
    assert Path(orchestration.project_paper_build_script_path).is_file()
    assert Path(orchestration.project_paper_build_script_path).stat().st_mode & 0o111
    assert orchestration.project_paper_sources_manifest is not None
    source_files = {item.relative_path for item in orchestration.project_paper_sources_manifest.files}
    assert {
        "paper.md",
        "main.tex",
        "references.bib",
        "build.sh",
            "paper_compile_report.json",
            "paper_compiler_evidence.json",
            "project_revision_action_index.json",
            "project_review_findings.json",
            "revision_actions.md",
        "paper_revised.md",
        "project_revision_application.json",
        "project_rereview_report.json",
        "manifest.json",
    } == source_files
    assert all((sources_dir / item).exists() for item in source_files)
    assert orchestration.project_paper_compile_report is not None
    assert orchestration.project_paper_compile_report.source_package_complete is True
    assert orchestration.project_paper_compile_report.missing_required_inputs == []
    assert orchestration.project_paper_revision_action_count >= 3
    assert orchestration.project_paper_revision_pending_action_count >= 3
    assert orchestration.project_paper_revision_completed_action_count == 0
    assert orchestration.project_paper_revision_action_index is not None
    assert orchestration.project_paper_revision_action_index.pending_action_count >= 3
    assert orchestration.project_paper_revision_action_index.completed_action_count == 0
    assert {
        "project_literature_refresh_multi_source",
        "project_benchmark_provenance_repair",
        "project_benchmark_scale_repair",
    }.issubset({action.action_id for action in orchestration.project_paper_revision_actions})
    assert Path(orchestration.project_paper_revision_action_index_path).is_file()
    assert Path(orchestration.project_paper_revision_actions_markdown_path).is_file()
    assert Path(orchestration.project_paper_revised_path).is_file()
    assert Path(orchestration.project_paper_revision_application_path).is_file()
    assert Path(orchestration.project_paper_rereview_report_path).is_file()
    assert orchestration.project_paper_latex_source is not None
    assert "\\section{Abstract}" in orchestration.project_paper_latex_source
    assert orchestration.project_paper_bibliography_bib is not None
    assert orchestration.project_review_bundle_ready is True
    assert orchestration.project_final_publish_ready is False
    assert orchestration.project_submission_ready is False
    assert orchestration.project_submission_asset_count == 28
    assert orchestration.project_submission_manifest_path is not None
    assert Path(orchestration.project_submission_manifest_path).is_file()
    assert Path(orchestration.project_reproducibility_checklist_path).is_file()
    assert Path(orchestration.project_reviewer_response_path).is_file()
    assert Path(orchestration.project_review_findings_path).is_file()
    assert Path(orchestration.project_repair_execution_log_path).is_file()
    assert Path(orchestration.project_claim_evidence_index_path).is_file()
    assert Path(orchestration.project_retrieval_evidence_ledger_path).is_file()
    assert Path(orchestration.project_lineage_archive_path).is_file()
    assert Path(orchestration.project_paper_compiler_evidence_path).is_file()
    assert Path(orchestration.project_publication_evidence_index_path).is_file()
    assert Path(orchestration.project_publication_readiness_report_path).is_file()
    assert Path(orchestration.project_supplemental_artifacts_path).is_file()
    assert Path(orchestration.project_revision_application_path).is_file()
    assert Path(orchestration.project_revision_rereview_path).is_file()
    assert orchestration.project_code_package_path is not None
    assert orchestration.project_benchmark_card_path is not None
    assert orchestration.project_benchmark_provenance_manifest_path is not None
    assert orchestration.project_benchmark_provenance_repair_index_path is not None
    assert orchestration.project_statistics_report_path is not None
    assert orchestration.project_experiment_repair_index_path is not None
    assert orchestration.project_offline_publication_case_path is not None
    assert orchestration.project_offline_publication_audit_path is not None
    assert orchestration.project_publication_manifest_path is not None
    assert Path(orchestration.project_code_package_path).is_file()
    assert Path(orchestration.project_benchmark_card_path).is_file()
    assert Path(orchestration.project_benchmark_provenance_manifest_path).is_file()
    assert Path(orchestration.project_benchmark_provenance_repair_index_path).is_file()
    assert Path(orchestration.project_statistics_report_path).is_file()
    assert Path(orchestration.project_experiment_repair_index_path).is_file()
    assert Path(orchestration.project_negative_evidence_report_path).is_file()
    assert Path(orchestration.project_offline_publication_case_path).is_file()
    assert Path(orchestration.project_offline_publication_audit_path).is_file()
    assert Path(orchestration.project_publication_manifest_path).is_file()
    assert orchestration.project_code_package_complete is True
    assert orchestration.project_benchmark_card_complete is True
    assert orchestration.project_benchmark_provenance_manifest_complete is True
    assert orchestration.project_benchmark_provenance_repair_index_complete is True
    assert orchestration.project_statistics_report_complete is True
    assert orchestration.project_experiment_repair_index_complete is True
    assert orchestration.project_negative_evidence_report_complete is True
    assert orchestration.project_offline_publication_case_complete is True
    assert orchestration.project_offline_publication_audit_complete is True
    assert orchestration.project_repair_execution_log_complete is True
    assert orchestration.project_review_findings_complete is True
    assert orchestration.project_publication_manifest_complete is True
    assert orchestration.project_retrieval_evidence_ledger_complete is True
    assert orchestration.project_publication_readiness_report_complete is True
    assert orchestration.project_paper_compiler_evidence_complete is True
    assert orchestration.project_publication_evidence_index_complete is True
    assert orchestration.project_supplemental_artifacts_complete is True
    assert orchestration.project_revision_application_complete is True
    assert orchestration.project_revision_rereview_complete is True
    submission_manifest = json.loads(Path(orchestration.project_submission_manifest_path).read_text(encoding="utf-8"))
    assert submission_manifest["bundle_kind"] == "review_bundle"
    assert submission_manifest["review_bundle_ready"] is True
    assert submission_manifest["final_publish_ready"] is False
    assert all(item["source_action"] for item in submission_manifest["generated_assets"])
    assert all(item["readiness_contribution"] for item in submission_manifest["generated_assets"])
    assert all("source_evidence_refs" in item for item in submission_manifest["generated_assets"])
    assert all(item["missing_status"] == "present" for item in submission_manifest["generated_assets"])
    assert all("blocked_status" in item for item in submission_manifest["generated_assets"])
    assert all("final_publish_blocking" in item for item in submission_manifest["generated_assets"])
    assert all("blocking_check_ids" in item for item in submission_manifest["generated_assets"])
    assert submission_manifest["blocked_asset_count"] > 0
    assert "project_publication_readiness_report" in submission_manifest["final_publish_blocking_asset_roles"]
    assert all(item["source_run_ids"] == [run.id] for item in submission_manifest["generated_assets"])
    assets_by_role = {item["role"]: item for item in submission_manifest["generated_assets"]}
    assert assets_by_role["project_review_findings"]["source_action"] == "run_project_reviewer_simulator"
    assert assets_by_role["project_review_findings"]["readiness_contribution"] == "review_findings"
    assert assets_by_role["project_statistics_report"]["source_action"] == "build_project_statistics_report"
    assert assets_by_role["project_experiment_repair_index"]["readiness_contribution"] == "experiment_repair"
    assert assets_by_role["project_negative_evidence_report"]["readiness_contribution"] == "negative_evidence"
    assert assets_by_role["project_retrieval_evidence_ledger"]["readiness_contribution"] == "retrieval_evidence"
    assert assets_by_role["project_offline_publication_case"]["readiness_contribution"] == "offline_publication_case"
    assert assets_by_role["project_offline_publication_audit"]["readiness_contribution"] == "capability_audit"
    assert "selected_run_result_artifacts" in assets_by_role["project_statistics_report"]["source_evidence_refs"]
    assert "project_evidence_ledgers" in assets_by_role["project_negative_evidence_report"]["source_evidence_refs"]
    assert submission_manifest["code_package_path"] == orchestration.project_code_package_path
    assert submission_manifest["supplemental_artifacts_path"] == orchestration.project_supplemental_artifacts_path
    assert submission_manifest["review_findings_path"] == orchestration.project_review_findings_path
    assert submission_manifest["repair_execution_log_path"] == orchestration.project_repair_execution_log_path
    assert submission_manifest["retrieval_evidence_ledger_path"] == orchestration.project_retrieval_evidence_ledger_path
    assert submission_manifest["paper_compiler_evidence_path"] == orchestration.project_paper_compiler_evidence_path
    assert submission_manifest["publication_evidence_index_path"] == orchestration.project_publication_evidence_index_path
    assert submission_manifest["benchmark_card_path"] == orchestration.project_benchmark_card_path
    assert submission_manifest["benchmark_provenance_manifest_path"] == orchestration.project_benchmark_provenance_manifest_path
    assert submission_manifest["statistics_report_path"] == orchestration.project_statistics_report_path
    assert submission_manifest["negative_evidence_report_path"] == orchestration.project_negative_evidence_report_path
    assert submission_manifest["offline_publication_case_path"] == orchestration.project_offline_publication_case_path
    assert submission_manifest["offline_publication_audit_path"] == orchestration.project_offline_publication_audit_path
    assert submission_manifest["publication_manifest_path"] == orchestration.project_publication_manifest_path
    assert "Project publish gate has not passed" in "\n".join(orchestration.project_submission_blockers)
    assert "Project Reproducibility Checklist" in Path(
        orchestration.project_reproducibility_checklist_path
    ).read_text(encoding="utf-8")
    benchmark_card = json.loads(Path(orchestration.project_benchmark_card_path).read_text(encoding="utf-8"))
    assert benchmark_card["card_id"] == "project_benchmark_card_v1"
    assert benchmark_card["selected_run_ids"] == [run.id]
    run_card = benchmark_card["run_cards"][0]
    assert run_card["sample_count"] == run_card["total_examples"]
    assert "split_count" in run_card
    assert "supports_claim_verification" in run_card
    assert "verification_label_space" in run_card
    assert "source_class" in run_card
    assert "publication_grade_eligibility" in run_card
    assert "publication_grade_blockers" in run_card
    publication_manifest = json.loads(Path(orchestration.project_publication_manifest_path).read_text(encoding="utf-8"))
    assert publication_manifest["publication_id"] == f"project_publication_{project_id}"
    assert publication_manifest["review_bundle_ready"] is True
    assert publication_manifest["final_publish_ready"] is False
    readiness_decision = publication_manifest["readiness_decision"]
    assert readiness_decision["decision_source"] == "publication_readiness_report.json"
    assert readiness_decision["review_ready"] is True
    assert readiness_decision["final_publish_ready"] is False
    assert readiness_decision["bundle_kind"] == "review_bundle"
    assert readiness_decision["failed_check_count"] > 0
    assert {item["check_id"] for item in readiness_decision["failed_checks"]} >= {
        "project_publish_gate",
        "benchmark_scale",
        "benchmark_provenance",
    }
    assert readiness_decision["blockers"]
    assert readiness_decision["required_followups"]
    assert readiness_decision["kill_criteria"]
    assert "negative_evidence_report.json" in readiness_decision["evidence_refs"]
    assert readiness_decision["claim_ceiling_recommendation"] in {
        "workshop_case_study_claim",
        "technical_report_only",
    }
    assert publication_manifest["paper_compiler_evidence_sha256"] is not None
    assert publication_manifest["publication_evidence_index_sha256"] is not None
    assert publication_manifest["publication_readiness_report_sha256"] is not None
    assert publication_manifest["repair_execution_log_sha256"] is not None
    assert publication_manifest["review_findings_sha256"] is not None
    assert publication_manifest["retrieval_evidence_ledger_sha256"] is not None
    assert publication_manifest["supplemental_artifacts_sha256"] is not None
    assert publication_manifest["code_package_sha256"] is not None
    assert publication_manifest["benchmark_provenance_manifest_sha256"] is not None
    assert publication_manifest["statistics_report_sha256"] is not None
    assert publication_manifest["negative_evidence_report_sha256"] is not None
    assert publication_manifest["offline_publication_case_sha256"] is not None
    assert publication_manifest["offline_publication_audit_sha256"] is not None
    assert publication_manifest["asset_count"] == len(submission_manifest["generated_assets"])
    assert publication_manifest["missing_asset_count"] == 0
    publication_assets_by_role = {item["role"]: item for item in publication_manifest["generated_assets"]}
    assert set(publication_assets_by_role) == set(assets_by_role)
    assert all(item["source_action"] for item in publication_manifest["generated_assets"])
    assert all(item["readiness_contribution"] for item in publication_manifest["generated_assets"])
    assert all("source_evidence_refs" in item for item in publication_manifest["generated_assets"])
    assert all(item["missing_status"] == "present" for item in publication_manifest["generated_assets"])
    assert all("blocked_status" in item for item in publication_manifest["generated_assets"])
    assert all("final_publish_blocking" in item for item in publication_manifest["generated_assets"])
    assert publication_manifest["blocked_asset_count"] == len(
        publication_manifest["final_publish_blocking_asset_roles"]
    )
    assert publication_manifest["blocked_asset_count"] > 0
    assert publication_assets_by_role["project_publication_readiness_report"]["blocked_status"] == (
        "blocked_for_final_publish"
    )
    assert "project_publish_gate" in (
        publication_assets_by_role["project_publication_readiness_report"]["blocking_check_ids"]
    )
    assert publication_assets_by_role["project_benchmark_provenance_manifest"]["blocked_status"] == (
        "blocked_for_final_publish"
    )
    assert all(item["source_run_ids"] == [run.id] for item in publication_manifest["generated_assets"])
    assert all(
        item["sha256"] is not None
        for item in publication_manifest["generated_assets"]
        if item["kind"] == "file" and item["role"] != "project_publication_manifest"
    )
    assert publication_assets_by_role["project_publication_manifest"]["self_referential_hash"] is True
    assert publication_assets_by_role["project_publication_manifest"]["sha256"] is None
    assert publication_assets_by_role["project_statistics_report"]["source_action"] == "build_project_statistics_report"
    assert (
        publication_assets_by_role["project_offline_publication_audit"]["readiness_contribution"]
        == "capability_audit"
    )
    review_findings = json.loads(Path(orchestration.project_review_findings_path).read_text(encoding="utf-8"))
    assert review_findings["review_id"] == "project_reviewer_simulation_findings_v1"
    assert review_findings["finding_count"] == orchestration.project_paper_revision_action_count
    assert {
        item["mapped_revision_action_id"] for item in review_findings["findings"]
    } == {action.action_id for action in orchestration.project_paper_revision_actions}
    assert all(action.finding_ids for action in orchestration.project_paper_revision_actions)
    compiler_evidence = json.loads(Path(orchestration.project_paper_compiler_evidence_path).read_text(encoding="utf-8"))
    assert compiler_evidence["packet_id"] == "project_paper_compiler_evidence_v1"
    assert compiler_evidence["section_coverage"]["complete"] is True
    assert set(compiler_evidence["section_coverage"]["required_sections"]) == set(
        autoresearch_project_paper_orchestrator.PROJECT_PAPER_REQUIRED_SECTIONS
    )
    assert {
        "Research Question",
        "Benchmark And Data",
        "Negative Evidence",
        "Reproducibility",
    }.issubset(set(compiler_evidence["section_coverage"]["present_sections"]))
    assert compiler_evidence["claim_support_coverage"]["core_claim_count"] == orchestration.core_claim_count
    assert compiler_evidence["compile_readiness"]["source_package_complete"] is True
    assert compiler_evidence["statistics_coverage"]["run_with_statistics_count"] >= 1
    execution_coverage = compiler_evidence["execution_coverage"]
    assert execution_coverage["complete"] is True
    assert execution_coverage["complete_execution_profile_count"] == 1
    assert execution_coverage["execution_source_counts"]
    assert "run_result_artifact_json" in execution_coverage["execution_output_artifact_refs"]
    assert execution_coverage["execution_evidence_ledger"]["entry_count"] == 1
    assert execution_coverage["execution_evidence_ledger"]["entries"][0]["run_id"] == run.id
    assert execution_coverage["metrics_artifact_refs"]
    assert compiler_evidence["review_findings_coverage"]["finding_count"] == (
        orchestration.project_paper_revision_action_count
    )
    assert compiler_evidence["review_findings_coverage"]["complete"] is True
    assert compiler_evidence["reproducibility_coverage"]["review_findings_persisted"] is True
    assert "project_review_findings" in compiler_evidence["reproducibility_coverage"]["planned_package_asset_roles"]
    assert compiler_evidence["reproducibility_coverage"]["planned_package_asset_count"] == len(
        autoresearch_project_paper_orchestrator.PROJECT_SUBMISSION_PACKAGE_ROLES
    )
    benchmark_coverage = compiler_evidence["benchmark_provenance_coverage"]
    assert benchmark_coverage["snapshot_metadata"]["selected_run_count"] == 1
    assert benchmark_coverage["snapshot_metadata"]["total_sample_count"] == run_card["sample_count"]
    assert benchmark_coverage["run_profiles"][0]["sample_count"] == run_card["sample_count"]
    benchmark_provenance_manifest = json.loads(
        Path(orchestration.project_benchmark_provenance_manifest_path).read_text(encoding="utf-8")
    )
    assert benchmark_provenance_manifest["manifest_id"] == "project_benchmark_provenance_manifest_v1"
    assert benchmark_provenance_manifest["snapshot_metadata"]["selected_run_count"] == 1
    assert benchmark_provenance_manifest["run_profiles"][0]["split_count"] == run_card["split_count"]
    source_record = benchmark_provenance_manifest["benchmark_source_records"][0]
    assert source_record["run_id"] == run.id
    assert source_record["dataset_id"] == run_card["source_dataset_id"]
    assert source_record["revision"] == run_card["source_revision"]
    assert source_record["license"] == run_card["source_license"]
    assert source_record["source_locator"] == run_card["source_url"]
    assert source_record["fingerprint"] == run_card["source_fingerprint"]
    assert source_record["sample_count"] == run_card["sample_count"]
    assert source_record["split_count"] == run_card["split_count"]
    assert "query_document_evidence_schema" in source_record
    assert "label_space" in source_record
    assert "source_class" in source_record
    assert "publication_grade_eligibility" in source_record
    assert "publication_grade_blockers" in source_record
    schema_coverage = benchmark_provenance_manifest["schema_coverage"]
    assert schema_coverage["selected_run_count"] == 1
    assert "schema_coverage_complete" in schema_coverage
    assert "schema_blockers" in schema_coverage
    publication_evidence_index = json.loads(
        Path(orchestration.project_publication_evidence_index_path).read_text(encoding="utf-8")
    )
    assert publication_evidence_index["index_id"] == "project_publication_evidence_index_v1"
    assert publication_evidence_index["benchmark_evidence_count"] == 1
    benchmark_evidence_item = publication_evidence_index["benchmark_evidence_items"][0]
    assert benchmark_evidence_item["run_id"] == run.id
    assert benchmark_evidence_item["dataset_id"] == run_card["source_dataset_id"]
    assert benchmark_evidence_item["artifact_refs"] == [
        orchestration.project_benchmark_provenance_manifest_path,
        orchestration.project_benchmark_provenance_repair_index_path,
    ]
    assert publication_evidence_index["package_evidence_refs"]["benchmark_provenance_manifest"] == (
        orchestration.project_benchmark_provenance_manifest_path
    )
    assert publication_evidence_index["package_evidence_refs"]["benchmark_provenance_repair_index"] == (
        orchestration.project_benchmark_provenance_repair_index_path
    )
    statistics_report = json.loads(Path(orchestration.project_statistics_report_path).read_text(encoding="utf-8"))
    assert statistics_report["report_id"] == "project_statistics_report_v1"
    assert statistics_report["per_method_metric_table"]
    assert statistics_report["aggregate_metric_table"]
    assert statistics_report["paired_comparisons"]
    assert statistics_report["confidence_intervals"] or statistics_report["deterministic_equivalents"]
    assert statistics_report["execution_coverage"]["complete"] is True
    assert statistics_report["execution_coverage"]["complete_execution_profile_count"] == 1
    assert "run_result_artifact_json" in statistics_report["execution_coverage"]["execution_output_artifact_refs"]
    assert statistics_report["claim_ceiling_recommendation"] in {
        "workshop_case_study_claim",
        "technical_report_only",
    }
    assert statistics_report["statistics_limitations"]
    experiment_repair_index = json.loads(Path(orchestration.project_experiment_repair_index_path).read_text(encoding="utf-8"))
    execution_ledger = experiment_repair_index["execution_evidence_ledger"]
    assert execution_ledger["ledger_id"] == "project_experiment_execution_evidence_ledger_v1"
    assert execution_ledger["entry_count"] == 1
    assert execution_ledger["entries"][0]["run_id"] == run.id
    assert execution_ledger["entries"][0]["repair_action_linkage"] == [
        "project_benchmark_scale_repair",
        "project_insufficient_statistics_repair",
    ]
    assert execution_ledger["entries"][0]["metrics_artifact_refs"]
    assert execution_ledger["entries"][0]["deterministic_fingerprint"]
    negative_evidence_report = json.loads(Path(orchestration.project_negative_evidence_report_path).read_text(encoding="utf-8"))
    assert negative_evidence_report["report_id"] == "project_negative_evidence_report_v1"
    assert negative_evidence_report["entry_count"] > 0
    assert negative_evidence_report["negative_evidence_retained"] is True
    assert "claim_ceiling_recommendation" in negative_evidence_report
    retrieval_ledger = json.loads(Path(orchestration.project_retrieval_evidence_ledger_path).read_text(encoding="utf-8"))
    assert retrieval_ledger["ledger_id"] == "project_retrieval_evidence_ledger_v1"
    assert "entries" in retrieval_ledger
    assert "status_counts" in retrieval_ledger
    offline_case = json.loads(Path(orchestration.project_offline_publication_case_path).read_text(encoding="utf-8"))
    assert offline_case["case_id"] == "offline_publication_case_claim_evidence_v3"
    assert offline_case["research_question"].startswith("Can evidence-ledger-guided retrieval")
    assert offline_case["research_chain"]["method_ladder"] == [
        "random_ranker",
        "lexical_overlap",
        "bm25_tfidf_style",
        "phrase_or_bigram_aware_retrieval",
        "ledger_aware_retrieval",
        "abstention_repair_router",
    ]
    assert "project_negative_evidence_report" in offline_case["research_chain"]["paper_package_outputs"]
    assert offline_case["evidence_classification"]["internal_fixtures_policy"]
    offline_audit = json.loads(Path(orchestration.project_offline_publication_audit_path).read_text(encoding="utf-8"))
    assert offline_audit["audit_id"] == "offline_publication_capability_audit_v1"
    assert offline_audit["checkpoint_count"] == 7
    assert offline_audit["review_ready"] is True
    assert offline_audit["final_publish_ready"] is False
    assert {item["checkpoint_id"] for item in offline_audit["checkpoints"]} == {
        "literature_refresh",
        "benchmark_snapshot_selection",
        "experiment_execution_or_import_replay",
        "statistics_strength",
        "negative_evidence_retention",
        "repair_aware_rereview",
        "submission_package_v3",
    }
    assert offline_audit["remaining_breakpoints"]
    repair_execution_log = json.loads(Path(orchestration.project_repair_execution_log_path).read_text(encoding="utf-8"))
    assert repair_execution_log["log_id"] == "project_repair_execution_log_v1"
    assert all("input_artifact_refs" in item for item in repair_execution_log["entries"])
    assert all("output_artifact_refs" in item for item in repair_execution_log["entries"])
    assert all("repair_output_audits" in item for item in repair_execution_log["entries"])
    assert all("repair_outputs_consumed" in item for item in repair_execution_log["entries"])
    publication_evidence_index = json.loads(Path(orchestration.project_publication_evidence_index_path).read_text(encoding="utf-8"))
    assert publication_evidence_index["index_id"] == "project_publication_evidence_index_v1"
    assert publication_evidence_index["paper_compiler_evidence_path"] == orchestration.project_paper_compiler_evidence_path
    readiness_report = json.loads(Path(orchestration.project_publication_readiness_report_path).read_text(encoding="utf-8"))
    assert readiness_report["readiness_id"] == "project_publication_readiness_report_v1"
    assert readiness_report["publication_grade_ready"] is False
    assert readiness_report["final_publish_ready"] is False
    assert readiness_report["blockers"]
    assert any("Do not submit as final publish" in item for item in readiness_report["kill_criteria"])
    assert readiness_report["required_followups"]
    checks_by_id = {item["check_id"]: item for item in readiness_report["checks"]}
    assert checks_by_id["benchmark_scale"]["passed"] is False
    assert checks_by_id["benchmark_provenance"]["passed"] is False
    assert checks_by_id["cross_run_replication"]["passed"] is False
    assert checks_by_id["real_literature_coverage"]["passed"] is False
    assert checks_by_id["execution_evidence"]["passed"] is True
    assert "run_result_artifact_json" in checks_by_id["execution_evidence"]["execution_output_artifact_refs"]
    assert checks_by_id["paper_compiler_evidence"]["passed"] is False
    assert readiness_report["paper_compiler_evidence"]["packet_id"] == "project_paper_compiler_evidence_v1"
    assert readiness_report["repair_execution_log"]["log_id"] == "project_repair_execution_log_v1"
    assert checks_by_id["repair_execution_log"]["passed"] is False
    assert readiness_report["evidence_profile"]["real_literature_count"] == 0
    assert any("benchmark" in item.lower() for item in readiness_report["required_followups"])
    supplemental_manifest = json.loads(Path(orchestration.project_supplemental_artifacts_path).read_text(encoding="utf-8"))
    assert supplemental_manifest["supplemental_id"] == "project_supplemental_artifacts_v1"
    assert supplemental_manifest["present_artifact_count"] == supplemental_manifest["artifact_count"]
    with ZipFile(orchestration.project_code_package_path) as archive:
        names = set(archive.namelist())
    assert "paper.md" in names
    assert "paper_sources/main.tex" in names
    assert "paper_sources/project_revision_application.json" in names
    assert "paper_sources/project_rereview_report.json" in names
    assert "paper_sources/paper_compiler_evidence.json" in names
    assert "submission_package/claim_evidence_index.md" in names
    assert "submission_package/retrieval_evidence_ledger.json" in names
    assert "submission_package/project_review_findings.json" in names
    assert "submission_package/repair_execution_log.json" in names
    assert "submission_package/publication_evidence_index.json" in names
    assert "submission_package/publication_readiness_report.json" in names
    assert "submission_package/supplemental_artifacts.json" in names
    assert "submission_package/benchmark_card.json" in names
    assert "submission_package/benchmark_provenance_manifest.json" in names
    assert "submission_package/statistics_report.json" in names
    assert "submission_package/negative_evidence_report.json" in names
    assert "submission_package/offline_publication_case.json" in names
    assert "submission_package/offline_publication_audit.json" in names


def test_project_paper_orchestrator_traces_retrieval_evidence_ledger(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-paper-retrieval-ledger"
    run = autoresearch_repository.create_run(
        project_id,
        "Claim-evidence retrieval ledger trace",
        request=AutoResearchRunConfig(task_family_hint="ir_reranking"),
    )
    evidence_ledger = AutoResearchEvidenceLedgerRead(
        project_id=project_id,
        run_id=run.id,
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        entries=[
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id="evidence_retrieval_supported_claim",
                source_job_id="job_candidate_method",
                evidence_kind="artifact",
                claim="Cached SciFact-style retrieval attached ranked evidence for a supported claim.",
                artifact_ref="run_artifact_json",
                support_status="supported",
            ),
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id="evidence_retrieval_partial_claim",
                source_job_id="job_candidate_method",
                evidence_kind="artifact",
                claim="Cached SciFact-style retrieval found partial evidence for a weak claim.",
                artifact_ref="run_artifact_json",
                support_status="partial",
            ),
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id="evidence_retrieval_missing_claim",
                source_job_id="job_candidate_method",
                evidence_kind="artifact",
                claim="Cached SciFact-style retrieval failed to find support for an over-broad claim.",
                artifact_ref="run_artifact_json",
                support_status="missing",
            ),
        ],
        entry_count=3,
        complete=False,
        blockers=["Claim-evidence retrieval ledger has missing evidence for at least one query."],
        ledger_fingerprint="project-paper-retrieval-ledger",
    )
    autoresearch_repository.save_run(
        run.model_copy(
            update={
                "status": "done",
                "evidence_ledger": evidence_ledger,
            }
        )
    )

    orchestration = autoresearch_project_paper_orchestrator.build_project_paper_orchestration(project_id)

    retrieval_conclusion = next(
        item
        for item in orchestration.conclusion_ledger.conditional_conclusions
        if item.conclusion_id.startswith("claim_evidence_retrieval_")
    )
    missing_limitation = next(
        item
        for item in orchestration.conclusion_ledger.limitations
        if item.conclusion_id.startswith("missing_claim_evidence_retrieval_")
    )
    retrieval_trace = next(
        trace
        for trace in orchestration.claim_traces
        if trace.source_conclusion_id == retrieval_conclusion.conclusion_id
    )

    assert orchestration.should_write_paper is True
    assert orchestration.paper_decision == "technical_report"
    assert orchestration.project_level_paper_allowed is False
    assert retrieval_conclusion.paper_claim_allowed is True
    assert "1 supported and 1 partial" in retrieval_conclusion.text
    assert all("evidence_ledger:evidence_retrieval_" in ref for ref in retrieval_conclusion.evidence_refs)
    assert "missing support" in missing_limitation.text
    assert retrieval_trace.support_status == "supported"
    assert retrieval_trace.evidence_refs == retrieval_conclusion.evidence_refs
    assert orchestration.project_paper_path is not None
    project_paper_path = Path(orchestration.project_paper_path)
    assert project_paper_path.is_file()
    paper_markdown = project_paper_path.read_text(encoding="utf-8")
    assert orchestration.project_paper_markdown == paper_markdown
    assert orchestration.project_paper_ready is True
    assert orchestration.project_paper_missing_sections == []
    assert "## Abstract" in paper_markdown
    assert "## Introduction" in paper_markdown
    assert "## Related Work" in paper_markdown
    assert "## Method" in paper_markdown
    assert "## Experimental Setup" in paper_markdown
    assert "## Results" in paper_markdown
    assert "## Analysis" in paper_markdown
    assert "## Limitations" in paper_markdown
    assert "## Conclusion" in paper_markdown
    assert "## References" in paper_markdown
    assert "evidence_retrieval_supported_claim" in paper_markdown
    assert "evidence_retrieval_partial_claim" in paper_markdown
    assert "missing_claim_evidence_retrieval_" in paper_markdown
    assert "Current evidence does not permit a project-level paper claim." in paper_markdown
    assert orchestration.project_paper_sources_manifest is not None
    assert orchestration.project_paper_compile_report is not None
    assert orchestration.project_paper_compile_report.source_package_complete is True
    assert orchestration.project_paper_compile_report.entrypoint == "main.tex"
    assert orchestration.project_paper_compile_report.bibliography == "references.bib"
    assert orchestration.project_paper_latex_source is not None
    assert "evidence\\_retrieval\\_supported\\_claim" in orchestration.project_paper_latex_source
    assert orchestration.project_paper_revision_action_count >= 5
    assert orchestration.project_paper_revision_pending_action_count >= 4
    assert orchestration.project_paper_revision_completed_action_count == 1
    assert orchestration.project_paper_claim_downgrade_action_count == 1
    assert orchestration.project_paper_retrieval_repair_action_count == 1
    action_ids = {action.action_id for action in orchestration.project_paper_revision_actions}
    assert {
        "project_literature_refresh_multi_source",
        "project_benchmark_provenance_repair",
        "project_benchmark_scale_repair",
        "project_insufficient_statistics_repair",
    }.issubset(action_ids)
    repair_action = next(
        action
        for action in orchestration.project_paper_revision_actions
        if action.action_id.startswith("project_retrieval_repair_")
    )
    assert repair_action.action_kind == "claim_downgrade"
    assert repair_action.repair_kind == "repair_claim_evidence"
    assert repair_action.status == "completed"
    assert repair_action.completed_round == 2
    assert repair_action.auto_applicable is True
    assert "project_retrieval_evidence_ledger" in repair_action.expected_output_asset_ids
    assert orchestration.project_paper_revision_action_index is not None
    assert orchestration.project_paper_revision_action_index.pending_action_count >= 4
    assert orchestration.project_paper_revision_action_index.completed_action_count == 1
    assert orchestration.project_paper_revision_action_index.materialized_action_count == 1
    assert Path(orchestration.project_paper_revision_action_index_path).is_file()
    assert "Route missing retrieval evidence" in Path(
        orchestration.project_paper_revision_actions_markdown_path
    ).read_text(encoding="utf-8")
    assert Path(orchestration.project_paper_revised_path).is_file()
    revised_markdown = Path(orchestration.project_paper_revised_path).read_text(encoding="utf-8")
    assert "## Revision Appendix" in revised_markdown
    assert "do not promote missing evidence to supported evidence" in revised_markdown
    assert Path(orchestration.project_paper_revision_application_path).is_file()
    revision_application = json.loads(Path(orchestration.project_paper_revision_application_path).read_text(encoding="utf-8"))
    assert revision_application["completed_action_count"] == 1
    assert revision_application["pending_action_count"] >= 4
    assert Path(orchestration.project_paper_rereview_report_path).is_file()
    rereview_report = json.loads(Path(orchestration.project_paper_rereview_report_path).read_text(encoding="utf-8"))
    assert rereview_report["rereview_complete"] is False
    assert rereview_report["same_support_issue_recurs"] is True
    assert rereview_report["action_reviews"]
    completed_review = next(
        item
        for item in rereview_report["action_reviews"]
        if item["action_id"] == repair_action.action_id
    )
    assert completed_review["claim_downgrade_status"] == "downgraded"
    assert completed_review["recommendation"] == "accept_as_review_bundle"
    assert completed_review["resolved_blockers"]
    assert any(item["new_blockers"] for item in rereview_report["action_reviews"])
    assert orchestration.project_paper_rereview_complete is False
    assert orchestration.project_review_bundle_ready is True
    assert orchestration.project_final_publish_ready is False
    assert orchestration.project_submission_ready is False
    assert orchestration.project_reviewer_response_complete is False
    assert orchestration.project_claim_evidence_index_complete is True
    assert any("Project publish gate has not passed" in item for item in orchestration.project_submission_blockers)
    reviewer_response = Path(orchestration.project_reviewer_response_path).read_text(encoding="utf-8")
    assert "Completed bounded revision actions" in reviewer_response
    assert "Route missing retrieval evidence" in reviewer_response
    assert "Recommendation" in reviewer_response
    assert "Claim downgrade status" in reviewer_response
    assert "Resolved blockers" in reviewer_response
    assert "New blockers" in reviewer_response
    lineage_payload = json.loads(Path(orchestration.project_lineage_archive_path).read_text(encoding="utf-8"))
    assert repair_action.action_id in {
        item["action_id"] for item in lineage_payload["revision_actions"]
    }
    assert lineage_payload["project_publish_gate_passed"] is False


def test_operator_console_surfaces_offline_publication_case_status(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-console-offline-publication-case"
    run = autoresearch_repository.create_run(
        project_id,
        "Console offline publication case",
        request=AutoResearchRunConfig(task_family_hint="ir_reranking"),
    )
    autoresearch_repository.save_run(
        run.model_copy(
            update={
                "status": "done",
                "artifact": _stable_project_artifact(0.73),
            }
        )
    )

    console = autoresearch_console.build_operator_console(project_id)

    assert console.publication_case is not None
    publication_case = console.publication_case
    assert publication_case.status == "review_ready"
    assert publication_case.review_bundle_ready is True
    assert publication_case.final_publish_ready is False
    assert publication_case.submission_bundle_kind == "review_bundle"
    assert publication_case.submission_asset_count >= 20
    assert publication_case.missing_asset_roles == []
    assert publication_case.blocked_asset_count > 0
    assert publication_case.blocked_asset_roles
    assert publication_case.final_publish_blocking_asset_roles == publication_case.blocked_asset_roles
    roles = {item["role"] for item in publication_case.package_asset_statuses}
    assert {
        "project_offline_publication_case",
        "project_offline_publication_audit",
        "project_negative_evidence_report",
        "project_retrieval_evidence_ledger",
        "project_statistics_report",
        "project_experiment_repair_index",
    }.issubset(roles)
    statuses_by_role = {item["role"]: item for item in publication_case.package_asset_statuses}
    assert statuses_by_role["project_publication_readiness_report"]["blocked_status"] == (
        "blocked_for_final_publish"
    )
    assert statuses_by_role["project_publication_readiness_report"]["final_publish_blocking"] is True
    assert statuses_by_role["project_publication_readiness_report"]["blocking_check_ids"]
    assert statuses_by_role["project_publication_readiness_report"]["blocking_reasons"]
    assert publication_case.repair_action_status_counts
    assert "blocked" in publication_case.repair_action_status_counts
    assert publication_case.review_finding_count > 0
    assert publication_case.review_findings_path is not None
    assert Path(publication_case.review_findings_path).is_file()
    assert publication_case.literature_source_counts == {}
    assert publication_case.real_literature_count == 0
    assert publication_case.benchmark_provenance_ready is False
    assert publication_case.benchmark_publication_ready is False
    assert publication_case.statistics_claim_ceiling in {
        "workshop_case_study_claim",
        "technical_report_only",
    }
    assert publication_case.negative_evidence_count > 0
    assert publication_case.negative_evidence_blocking_count > 0
    assert publication_case.rereview_complete is False
    assert publication_case.publish_blockers
    assert publication_case.required_followups
    assert publication_case.kill_criteria
    assert publication_case.offline_publication_case_path is not None
    assert Path(publication_case.offline_publication_case_path).is_file()
    assert publication_case.offline_publication_audit_path is not None
    assert Path(publication_case.offline_publication_audit_path).is_file()


def test_project_paper_revision_actions_route_unsupported_claim_and_retrieval_repair() -> None:
    ledger = AutoResearchProjectConclusionLedgerRead(
        project_id="project-paper-revision-actions",
        stable_conclusions=[],
        conditional_conclusions=[],
        negative_findings=[],
        failed_hypotheses=[],
        limitations=[
            AutoResearchProjectConclusionEntryRead(
                conclusion_id="missing_claim_evidence_retrieval_run_1",
                kind="limitation",
                text="Run 1 has a missing retrieval evidence entry.",
                supporting_run_ids=["run_1"],
                evidence_refs=["run_1:evidence_ledger:evidence_retrieval_missing_claim"],
                caveats=["Downgrade or repair before promotion."],
                paper_claim_allowed=True,
            )
        ],
        conclusion_count=1,
        ledger_fingerprint="revision-action-ledger",
    )
    traces = [
        AutoResearchProjectClaimTraceRead(
            claim_id="project_claim_overbroad_result",
            claim="The method eliminates unsupported claims across autonomous writing systems.",
            source_conclusion_id="conditional_overbroad_result",
            support_status="unsupported",
            supporting_run_ids=["run_1"],
            evidence_refs=[],
            unsupported_reasons=["No run-level evidence refs are attached to the conclusion."],
            strong_claim=True,
        )
    ]

    actions = autoresearch_project_paper_orchestrator._build_project_revision_actions(
        ledger=ledger,
        traces=traces,
    )
    action_index = autoresearch_project_paper_orchestrator._build_project_revision_action_index(
        actions,
        markdown="# Draft\n\n## Results\n\nUnsupported strong claim.\n",
    )

    assert len(actions) == 2
    downgrade = next(action for action in actions if action.action_id.startswith("project_claim_downgrade_"))
    repair = next(action for action in actions if action.action_id.startswith("project_retrieval_repair_"))
    assert downgrade.action_kind == "claim_downgrade"
    assert downgrade.repair_kind == "repair_claim_evidence"
    assert downgrade.priority == "high"
    assert downgrade.auto_applicable is True
    assert "no longer presents this unsupported or partial trace as a strong claim" in downgrade.terminal_condition
    assert repair.action_kind == "claim_downgrade"
    assert repair.repair_kind == "repair_claim_evidence"
    assert "project_retrieval_evidence_ledger" in repair.expected_output_asset_ids
    assert action_index.total_action_count == 2
    assert action_index.pending_action_count == 2
    assert {item.section_title for item in action_index.actions} == {"Results", "Limitations"}


def test_project_paper_revision_actions_cover_literature_statistics_and_provenance_repairs() -> None:
    ledger = AutoResearchProjectConclusionLedgerRead(
        project_id="project-paper-revision-expanded-actions",
        stable_conclusions=[],
        conditional_conclusions=[],
        negative_findings=[],
        failed_hypotheses=[],
        limitations=[],
        conclusion_count=0,
        ledger_fingerprint="expanded-revision-action-ledger",
    )
    evidence_profile = {
        "literature_ready": False,
        "benchmark_provenance_ready": False,
        "benchmark_publication_ready": False,
        "benchmark_scale_ready": False,
    }
    statistics_profiles = [
        {
            "run_id": "run_1",
            "has_statistics": False,
            "significance_test_count": 0,
        }
    ]

    actions = autoresearch_project_paper_orchestrator._build_project_revision_actions(
        ledger=ledger,
        traces=[],
        evidence_profile=evidence_profile,
        statistics_profiles=statistics_profiles,
    )
    action_index = autoresearch_project_paper_orchestrator._build_project_revision_action_index(
        actions,
        markdown="# Draft\n\n## Related Work\n\n## Experimental Setup\n\n## Results\n",
    )
    actions_by_id = {action.action_id: action for action in actions}

    assert {
        "project_literature_refresh_multi_source",
        "project_benchmark_provenance_repair",
        "project_benchmark_scale_repair",
        "project_insufficient_statistics_repair",
    }.issubset(actions_by_id)
    literature = actions_by_id["project_literature_refresh_multi_source"]
    assert literature.action_kind == "literature_refresh"
    assert literature.repair_kind == "refresh_literature"
    assert literature.execution_route == "literature_refresh"
    assert "project_literature_scout_json" in literature.expected_output_asset_ids
    assert "at least two non-fixture sources" in literature.terminal_condition
    provenance = actions_by_id["project_benchmark_provenance_repair"]
    assert provenance.action_kind == "experiment_repair"
    assert provenance.repair_kind == "update_benchmark_provenance"
    assert "project_benchmark_provenance_manifest_json" in provenance.expected_output_asset_ids
    scale = actions_by_id["project_benchmark_scale_repair"]
    assert scale.repair_kind == "rerun_experiments"
    assert scale.execution_route == "experiment_rerun"
    statistics = actions_by_id["project_insufficient_statistics_repair"]
    assert statistics.repair_kind == "rerun_experiments"
    assert "project_statistics_report_json" in statistics.expected_output_asset_ids
    assert "deterministic aggregate statistics" in statistics.terminal_condition
    sections = {item.action_id: item.section_title for item in action_index.actions}
    assert sections["project_literature_refresh_multi_source"] == "Related Work"
    assert sections["project_benchmark_provenance_repair"] == "Experimental Setup"
    assert sections["project_insufficient_statistics_repair"] == "Experimental Setup"


def test_project_literature_refresh_repair_materializes_real_support_index(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-literature-repair-complete"
    literature_action = next(
        action
        for action in autoresearch_project_paper_orchestrator._build_project_revision_actions(
            ledger=AutoResearchProjectConclusionLedgerRead(
                project_id=project_id,
                stable_conclusions=[],
                conditional_conclusions=[],
                negative_findings=[],
                failed_hypotheses=[],
                limitations=[],
                conclusion_count=0,
                ledger_fingerprint="literature-repair-ledger",
            ),
            traces=[],
            evidence_profile={"literature_ready": False},
            statistics_profiles=[],
        )
        if action.action_id == "project_literature_refresh_multi_source"
    )
    scout = SimpleNamespace(
        search_queries=["claim evidence retrieval autonomous research"],
        source_counts={"arxiv": 1, "semantic_scholar": 1},
        source_statuses=[],
        methods=["claim-evidence ledger"],
        datasets=["SciFact"],
        metrics=["unsupported claim recall"],
        known_sota=[
            "FARS-style autonomous research systems require executable artifact lineage.",
            "ARIS-style reviewer loops motivate bounded claim repair and rebuttal checks.",
        ],
        similar_papers=[
            AutoResearchLiteratureScoutPaperRead(
                paper_id="arxiv_real_claim_evidence",
                title="Evidence-Grounded Scientific Writing With FARS-Style Lineage",
                source="arxiv",
                authors=["Ada Researcher"],
                year=2024,
                arxiv_id="2401.00001",
                methods=["claim-evidence ledger"],
                datasets=["SciFact"],
                metrics=["unsupported claim recall"],
                cache_status="cache_hit",
                evidence="Cached arXiv metadata supports related-work coverage for claim-evidence retrieval.",
                relevance_score=0.91,
            ),
            AutoResearchLiteratureScoutPaperRead(
                paper_id="semanticscholar_real_repair",
                title="Repairing Unsupported Claims in ARIS-Style Research Agents",
                source="semantic_scholar",
                authors=["Ben Scientist"],
                year=2025,
                doi="10.0000/repair",
                methods=["retrieval repair"],
                datasets=["BEIR"],
                metrics=["Recall@10"],
                cache_status="cache_hit",
                evidence="Cached Semantic Scholar metadata supports novelty and repair framing.",
                relevance_score=0.88,
            ),
        ],
    )
    brief = SimpleNamespace(brief_id="brief_literature_repair", literature_scout=scout)

    _, actions, application_report, rereview_report = (
        autoresearch_project_paper_orchestrator._apply_project_revision_actions(
            project_id=project_id,
            markdown="# Draft\n\n## Related Work\n\n## References\n",
            actions=[literature_action],
            latest_brief=brief,
            traces=[],
            evidence_profile={"literature_ready": False},
        )
    )

    repaired = actions[0]
    assert repaired.status == "completed"
    assert repaired.completed_round == 2
    assert repaired.completed_at_step == 3
    assert repaired.failure_classification is None
    assert "project_literature_scout_json" in repaired.output_artifact_refs
    support_ref = next(ref for ref in repaired.output_artifact_refs if ref.startswith("project_literature_support_index:"))
    support_path = Path(support_ref.split(":", 1)[1])
    support_index = json.loads(support_path.read_text(encoding="utf-8"))
    assert support_index["complete"] is True
    assert support_index["real_literature_sources"] == ["arxiv", "semantic_scholar"]
    assert support_index["source_class_counts"]["cached_real_connector"] == 2
    assert support_index["related_system_coverage"]["covered_systems"] == ["FARS", "ARIS"]
    assert support_index["related_system_coverage"]["complete"] is True
    assert support_index["unsupported_or_weak_literature_claims"] == []
    assert application_report["repair_execution_log"][0]["status"] == "completed"
    assert rereview_report["rereview_complete"] is True
    assert rereview_report["completed_action_ids"] == ["project_literature_refresh_multi_source"]
    assert rereview_report["action_reviews"][0]["original_finding"] == repaired.detail
    assert rereview_report["action_reviews"][0]["output_artifact_refs"]
    assert rereview_report["action_reviews"][0]["repair_outputs_consumed"] is True
    assert rereview_report["action_reviews"][0]["repair_outputs_complete"] is True
    assert rereview_report["action_reviews"][0]["repair_output_audits"][0]["artifact_id"] == (
        "project_literature_support_index_v1"
    )
    assert rereview_report["action_reviews"][0]["repair_output_audits"][0]["fingerprint"]
    assert rereview_report["action_reviews"][0]["terminal_condition_met"] is True
    assert rereview_report["action_reviews"][0]["resolved_blockers"]
    assert rereview_report["action_reviews"][0]["new_blockers"] == []
    assert rereview_report["action_reviews"][0]["recommendation"] == "accept_as_review_bundle"


def test_project_literature_refresh_repair_blocks_fixture_only_support(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-literature-repair-blocked"
    literature_action = next(
        action
        for action in autoresearch_project_paper_orchestrator._build_project_revision_actions(
            ledger=AutoResearchProjectConclusionLedgerRead(
                project_id=project_id,
                stable_conclusions=[],
                conditional_conclusions=[],
                negative_findings=[],
                failed_hypotheses=[],
                limitations=[],
                conclusion_count=0,
                ledger_fingerprint="literature-repair-blocked-ledger",
            ),
            traces=[],
            evidence_profile={"literature_ready": False},
            statistics_profiles=[],
        )
        if action.action_id == "project_literature_refresh_multi_source"
    )
    scout = SimpleNamespace(
        search_queries=["claim evidence retrieval autonomous research"],
        source_counts={"fixture": 1},
        source_statuses=[],
        methods=[],
        datasets=[],
        metrics=[],
        known_sota=[],
        similar_papers=[
            AutoResearchLiteratureScoutPaperRead(
                paper_id="fixture_literature_only",
                title="Fixture Context for Claim Evidence",
                source="fixture",
                cache_status="fixture",
                evidence="Synthetic fixture context must not satisfy publication-grade literature repair.",
            )
        ],
    )
    brief = SimpleNamespace(brief_id="brief_literature_fixture_only", literature_scout=scout)

    _, actions, application_report, rereview_report = (
        autoresearch_project_paper_orchestrator._apply_project_revision_actions(
            project_id=project_id,
            markdown="# Draft\n\n## Related Work\n\n",
            actions=[literature_action],
            latest_brief=brief,
            traces=[],
            evidence_profile={"literature_ready": False},
        )
    )

    blocked = actions[0]
    assert blocked.status == "blocked"
    assert blocked.failure_classification == "insufficient_real_literature_sources"
    assert blocked.residual_blockers
    support_ref = next(ref for ref in blocked.output_artifact_refs if ref.startswith("project_literature_support_index:"))
    support_index = json.loads(Path(support_ref.split(":", 1)[1]).read_text(encoding="utf-8"))
    assert support_index["complete"] is False
    assert support_index["source_class_counts"]["fixture_or_offline_context"] == 1
    assert support_index["related_system_coverage"]["missing_systems"] == ["FARS", "ARIS"]
    assert support_index["related_system_coverage"]["complete"] is False
    assert "at least two non-fixture sources" in " ".join(blocked.residual_blockers)
    assert application_report["blocked_action_count"] == 1
    assert application_report["repair_execution_log"][0]["status"] == "blocked"
    assert rereview_report["rereview_complete"] is False
    assert rereview_report["blocked_action_ids"] == ["project_literature_refresh_multi_source"]
    assert rereview_report["action_reviews"][0]["terminal_condition_met"] is False
    assert rereview_report["action_reviews"][0]["new_blockers"]
    assert rereview_report["action_reviews"][0]["recommendation"] == "block_final_publish"


def test_project_benchmark_provenance_repair_materializes_valid_snapshot_index(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-benchmark-provenance-repair-complete"
    stale_actions = autoresearch_project_paper_orchestrator._build_project_revision_actions(
        ledger=AutoResearchProjectConclusionLedgerRead(
            project_id=project_id,
            stable_conclusions=[],
            conditional_conclusions=[],
            negative_findings=[],
            failed_hypotheses=[],
            limitations=[],
            conclusion_count=0,
            ledger_fingerprint="benchmark-provenance-stale-ledger",
        ),
        traces=[],
        evidence_profile={
            "literature_ready": True,
            "benchmark_provenance_ready": False,
            "benchmark_publication_ready": False,
            "benchmark_scale_ready": True,
        },
        statistics_profiles=[],
    )
    provenance_action = next(
        action for action in stale_actions if action.action_id == "project_benchmark_provenance_repair"
    )
    repaired_profile = {
        "run_profiles": [
            {
                "run_id": "run_valid_frozen",
                "benchmark_name": "frozen_scifact_20",
                "sample_count": 20,
                "split_count": 2,
                "supports_claim_verification": True,
                "verification_label_space": ["supported", "refuted", "not_enough_info"],
                "publication_grade": True,
                "provenance_complete": True,
                "source_kind": "local_json",
                "source_class": "frozen_snapshot",
                "source_url": "file:///repo/fixtures/scifact_20.json",
                "source_dataset_id": "scifact",
                "source_revision": "frozen-2026-06-03",
                "source_license": "CC-BY-4.0",
                "source_fingerprint": "sha256:valid-frozen-scifact",
                "publication_grade_blockers": [],
                "publication_grade_eligibility": {
                    "publication_grade": True,
                    "sample_count": 20,
                    "split_count": 2,
                    "checks": {
                        "has_dataset_id": True,
                        "has_revision": True,
                        "has_license": True,
                        "has_fingerprint": True,
                        "meets_min_examples": True,
                        "not_internal_fixture": True,
                    },
                },
            }
        ],
        "snapshot_metadata": {
            "selected_run_count": 1,
            "total_sample_count": 20,
            "min_split_count": 2,
            "frozen_snapshot_run_count": 1,
            "claim_verification_run_count": 1,
            "verification_label_spaces": ["not_enough_info", "refuted", "supported"],
        },
        "benchmark_scale_ready": True,
        "benchmark_provenance_ready": True,
        "benchmark_publication_ready": True,
        "blockers": [],
    }

    _, actions, application_report, rereview_report = (
        autoresearch_project_paper_orchestrator._apply_project_revision_actions(
            project_id=project_id,
            markdown="# Draft\n\n## Experimental Setup\n\n",
            actions=[provenance_action],
            evidence_profile=repaired_profile,
        )
    )

    repaired = actions[0]
    assert repaired.status == "completed"
    assert repaired.repair_kind == "update_benchmark_provenance"
    assert repaired.completed_round == 2
    assert "project_benchmark_provenance_manifest_json" in repaired.output_artifact_refs
    support_ref = next(
        ref
        for ref in repaired.output_artifact_refs
        if ref.startswith("project_benchmark_provenance_repair_index:")
    )
    repair_index = json.loads(Path(support_ref.split(":", 1)[1]).read_text(encoding="utf-8"))
    assert repair_index["complete"] is True
    assert repair_index["run_profiles"][0]["source_class"] == "frozen_snapshot"
    assert repair_index["run_profiles"][0]["query_document_evidence_schema"]["schema_complete"] is True
    assert repair_index["run_profiles"][0]["source_record_complete"] is True
    assert repair_index["run_profiles"][0]["repair_status"] == "eligible"
    assert repair_index["snapshot_metadata"]["frozen_snapshot_run_count"] == 1
    assert application_report["repair_execution_log"][0]["status"] == "completed"
    assert rereview_report["rereview_complete"] is True
    assert rereview_report["completed_action_ids"] == ["project_benchmark_provenance_repair"]
    assert rereview_report["action_reviews"][0]["repair_kind"] == "update_benchmark_provenance"
    assert rereview_report["action_reviews"][0]["repair_outputs_consumed"] is True
    assert rereview_report["action_reviews"][0]["repair_outputs_complete"] is True
    assert rereview_report["action_reviews"][0]["repair_output_audits"][0]["artifact_id"] == (
        "project_benchmark_provenance_repair_index_v1"
    )
    assert rereview_report["action_reviews"][0]["repair_output_audits"][0]["fingerprint"]
    assert rereview_report["action_reviews"][0]["terminal_condition_met"] is True
    assert rereview_report["action_reviews"][0]["recommendation"] == "accept_as_review_bundle"


def test_project_benchmark_provenance_repair_blocks_fixture_source(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-benchmark-provenance-repair-blocked"
    stale_actions = autoresearch_project_paper_orchestrator._build_project_revision_actions(
        ledger=AutoResearchProjectConclusionLedgerRead(
            project_id=project_id,
            stable_conclusions=[],
            conditional_conclusions=[],
            negative_findings=[],
            failed_hypotheses=[],
            limitations=[],
            conclusion_count=0,
            ledger_fingerprint="benchmark-provenance-blocked-ledger",
        ),
        traces=[],
        evidence_profile={
            "literature_ready": True,
            "benchmark_provenance_ready": False,
            "benchmark_publication_ready": False,
            "benchmark_scale_ready": False,
        },
        statistics_profiles=[],
    )
    provenance_action = next(
        action for action in stale_actions if action.action_id == "project_benchmark_provenance_repair"
    )
    fixture_profile = {
        "run_profiles": [
            {
                "run_id": "run_fixture",
                "benchmark_name": "scholarflow_fixture",
                "sample_count": 8,
                "split_count": 1,
                "supports_claim_verification": False,
                "verification_label_space": [],
                "publication_grade": False,
                "provenance_complete": True,
                "source_kind": "builtin",
                "source_class": "cached_fixture",
                "source_url": "file://scholarflow-fixtures/claim-evidence.json",
                "source_dataset_id": "scholarflow:fixture",
                "source_revision": "fixture-v1",
                "source_license": "cached-fixture",
                "source_fingerprint": "sha256:fixture",
                "publication_grade_blockers": [
                    "Internal ScholarFlow fixtures cannot be used as final-publish evidence.",
                    "Benchmark has fewer than 20 normalized examples.",
                ],
                "publication_grade_eligibility": {
                    "publication_grade": False,
                    "sample_count": 8,
                    "split_count": 1,
                    "checks": {
                        "not_internal_fixture": False,
                        "meets_min_examples": False,
                    },
                },
            }
        ],
        "snapshot_metadata": {
            "selected_run_count": 1,
            "total_sample_count": 8,
            "min_split_count": 1,
            "frozen_snapshot_run_count": 0,
            "claim_verification_run_count": 0,
            "verification_label_spaces": [],
        },
        "benchmark_scale_ready": False,
        "benchmark_provenance_ready": True,
        "benchmark_publication_ready": False,
        "blockers": [
            "Project benchmark evidence has fewer than 20 publication-grade examples in every selected run.",
            "At least one selected run is not marked publication-grade by its benchmark card.",
        ],
    }

    _, actions, application_report, rereview_report = (
        autoresearch_project_paper_orchestrator._apply_project_revision_actions(
            project_id=project_id,
            markdown="# Draft\n\n## Experimental Setup\n\n",
            actions=[provenance_action],
            evidence_profile=fixture_profile,
        )
    )

    blocked = actions[0]
    assert blocked.status == "blocked"
    assert blocked.failure_classification == "non_publication_benchmark_source"
    assert blocked.residual_blockers
    support_ref = next(
        ref
        for ref in blocked.output_artifact_refs
        if ref.startswith("project_benchmark_provenance_repair_index:")
    )
    repair_index = json.loads(Path(support_ref.split(":", 1)[1]).read_text(encoding="utf-8"))
    assert repair_index["complete"] is False
    assert repair_index["run_profiles"][0]["repair_status"] == "blocked"
    assert repair_index["run_profiles"][0]["source_class"] == "cached_fixture"
    assert repair_index["run_profiles"][0]["query_document_evidence_schema"]["schema_complete"] is False
    assert "claim_verification_support" in (
        repair_index["run_profiles"][0]["query_document_evidence_schema"]["missing_schema_roles"]
    )
    assert repair_index["run_profiles"][0]["source_record_complete"] is False
    assert any(
        "query/document/evidence schema" in item
        for item in repair_index["run_profiles"][0]["source_record_blockers"]
    )
    assert any("fixture" in item.lower() for item in repair_index["blockers"])
    assert application_report["blocked_action_count"] == 1
    assert application_report["repair_execution_log"][0]["status"] == "blocked"
    assert rereview_report["rereview_complete"] is False
    assert rereview_report["blocked_action_ids"] == ["project_benchmark_provenance_repair"]
    assert rereview_report["action_reviews"][0]["new_blockers"]
    assert rereview_report["action_reviews"][0]["recommendation"] == "block_final_publish"


def test_project_experiment_repairs_materialize_scale_and_statistics_index(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-experiment-repair-complete"
    repair_actions = [
        action
        for action in autoresearch_project_paper_orchestrator._build_project_revision_actions(
            ledger=AutoResearchProjectConclusionLedgerRead(
                project_id=project_id,
                stable_conclusions=[],
                conditional_conclusions=[],
                negative_findings=[],
                failed_hypotheses=[],
                limitations=[],
                conclusion_count=0,
                ledger_fingerprint="experiment-repair-complete-ledger",
            ),
            traces=[],
            evidence_profile={
                "literature_ready": True,
                "benchmark_provenance_ready": True,
                "benchmark_publication_ready": True,
                "benchmark_scale_ready": False,
            },
            statistics_profiles=[{"run_id": "run_scaled", "has_statistics": False, "significance_test_count": 0}],
        )
        if action.action_id in {"project_benchmark_scale_repair", "project_insufficient_statistics_repair"}
    ]
    evidence_profile = {
        "run_profiles": [
            {
                "run_id": "run_scaled",
                "benchmark_name": "frozen_beir_20",
                "sample_count": 24,
                "split_count": 2,
                "publication_grade": True,
                "provenance_complete": True,
                "source_class": "frozen_snapshot",
                "source_dataset_id": "real_claim_evidence_snapshot",
                "source_revision": "2026-06-frozen",
                "source_license": "CC-BY-4.0",
                "source_url": "file://fixtures/claim-evidence-snapshot.jsonl",
                "source_fingerprint": "claim-evidence-snapshot-fingerprint",
                "verification_label_space": ["supports", "refutes", "not_enough_info"],
            }
        ],
        "benchmark_scale_ready": True,
        "benchmark_provenance_ready": True,
        "benchmark_publication_ready": True,
        "blockers": [],
    }
    statistics_profiles = [
        {
            "run_id": "run_scaled",
            "has_statistics": True,
            "aggregate_count": 6,
            "significance_test_count": 1,
            "negative_result_count": 2,
            "failure_case_count": 1,
            "metric_names": ["MRR", "Recall@10", "unsupported_claim_recall"],
        }
    ]
    imported_artifact = _publication_artifact(include_ablation=True, seed_count=5).model_copy(
        update={
            "environment": {
                "external_imported": True,
                "factory_executor_mode": "external_import",
                "executor_mode": "external_import",
                "environment_manifest_id": "experiment_factory_environment_v1",
                "environment_manifest_fingerprint": "env-imported-scaled",
                "seed_count": 5,
            },
            "outputs": {
                "metrics": "imported_metrics.json",
                "evidence_ledger": "imported_evidence_ledger.json",
                "environment_manifest": "experiment_factory_environment_manifest.json",
                "materialized_jobs": "experiment_factory_materialized_jobs.json",
            },
        }
    )
    imported_run = autoresearch_repository.create_run(
        project_id,
        "Imported replay run for project experiment repair",
        request=AutoResearchRunConfig(task_family_hint="ir_reranking", execution_profile="publication"),
    ).model_copy(
        update={
            "id": "run_scaled",
            "status": "done",
            "artifact": imported_artifact,
            "experiment_factory_materialized_jobs": [
                AutoResearchExperimentFactoryMaterializedJobRead(
                    job_id="job_imported_metrics",
                    job_kind="candidate_method",
                    executor_mode="external_import",
                    backend="local",
                    command="import imported_metrics.json",
                    dependencies=["imported_metrics.json"],
                    expected_outputs=["imported_metrics.json", "imported_evidence_ledger.json"],
                    output_refs=["imported_metrics.json", "imported_evidence_ledger.json"],
                    runtime_contract={
                        "executor_mode": "external_import",
                        "status": "done",
                        "expected_outputs": ["imported_metrics.json", "imported_evidence_ledger.json"],
                    },
                    started_at_step=1,
                    completed_at_step=1,
                    environment_manifest_id="experiment_factory_environment_v1",
                    status="done",
                )
            ],
        }
    )

    _, actions, application_report, rereview_report = (
        autoresearch_project_paper_orchestrator._apply_project_revision_actions(
            project_id=project_id,
            markdown="# Draft\n\n## Experimental Setup\n\n",
            actions=repair_actions,
            selected_runs=[imported_run],
            evidence_profile=evidence_profile,
            statistics_profiles=statistics_profiles,
        )
    )

    assert {action.action_id: action.status for action in actions} == {
        "project_benchmark_scale_repair": "completed",
        "project_insufficient_statistics_repair": "completed",
    }
    assert all(action.completed_round == 2 for action in actions)
    assert all("project_statistics_report_json" in action.output_artifact_refs for action in actions)
    support_ref = next(
        ref
        for action in actions
        for ref in action.output_artifact_refs
        if ref.startswith("project_experiment_repair_index:")
    )
    repair_index = json.loads(Path(support_ref.split(":", 1)[1]).read_text(encoding="utf-8"))
    assert repair_index["complete"] is True
    assert repair_index["repair_routes"]["project_benchmark_scale_repair"]["complete"] is True
    assert repair_index["repair_routes"]["project_insufficient_statistics_repair"]["complete"] is True
    assert repair_index["scaled_publication_run_ids"] == ["run_scaled"]
    assert repair_index["run_statistics_profiles"][0]["significance_test_count"] == 1
    assert repair_index["execution_coverage_ready"] is True
    assert repair_index["imported_result_replay_run_ids"] == ["run_scaled"]
    assert repair_index["materialized_execution_run_ids"] == ["run_scaled"]
    assert repair_index["execution_profiles"][0]["execution_source"] == "imported_result_replay"
    assert repair_index["execution_profiles"][0]["completed_materialized_job_count"] == 1
    assert "run_result_artifact_json" in repair_index["execution_output_artifact_refs"]
    assert "imported_metrics.json" in repair_index["execution_output_artifact_refs"]
    execution_ledger = repair_index["execution_evidence_ledger"]
    assert execution_ledger["entry_count"] == 1
    assert execution_ledger["complete_entry_count"] == 1
    execution_evidence = execution_ledger["entries"][0]
    assert execution_evidence["execution_source"] == "imported_result_replay"
    assert execution_evidence["command_or_import_paths"] == [
        "import imported_metrics.json",
        "imported_metrics.json",
        "imported_evidence_ledger.json",
        "experiment_factory_environment_manifest.json",
        "experiment_factory_materialized_jobs.json",
    ]
    assert execution_evidence["dependency_manifest"]["dependencies"] == ["imported_metrics.json"]
    assert execution_evidence["runtime_contracts"][0]["runtime_contract"]["executor_mode"] == "external_import"
    assert execution_evidence["environment_manifest"]["fingerprint"] == "env-imported-scaled"
    assert execution_evidence["input_benchmark_artifact"]["dataset_id"] == "real_claim_evidence_snapshot"
    assert execution_evidence["metrics_artifact_refs"] == ["imported_metrics.json", "run_result_artifact_json"]
    assert execution_evidence["evidence_ledger_artifact_refs"] == ["imported_evidence_ledger.json"]
    assert execution_evidence["repair_action_linkage"] == [
        "project_benchmark_scale_repair",
        "project_insufficient_statistics_repair",
    ]
    assert execution_evidence["deterministic_fingerprint"]
    assert any("imported_metrics.json" in action.output_artifact_refs for action in actions)
    assert application_report["completed_action_count"] == 2
    assert rereview_report["rereview_complete"] is True
    assert set(rereview_report["completed_action_ids"]) == {
        "project_benchmark_scale_repair",
        "project_insufficient_statistics_repair",
    }
    assert {item["action_id"] for item in rereview_report["action_reviews"]} == {
        "project_benchmark_scale_repair",
        "project_insufficient_statistics_repair",
    }
    assert all(item["terminal_condition_met"] is True for item in rereview_report["action_reviews"])
    assert all(item["resolved_blockers"] for item in rereview_report["action_reviews"])
    assert all(item["repair_outputs_consumed"] is True for item in rereview_report["action_reviews"])
    assert all(item["repair_outputs_complete"] is True for item in rereview_report["action_reviews"])
    assert all(
        item["repair_output_audits"][0]["artifact_id"] == "project_experiment_repair_index_v1"
        for item in rereview_report["action_reviews"]
    )


def test_project_experiment_repairs_block_missing_statistics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-experiment-repair-blocked"
    repair_action = next(
        action
        for action in autoresearch_project_paper_orchestrator._build_project_revision_actions(
            ledger=AutoResearchProjectConclusionLedgerRead(
                project_id=project_id,
                stable_conclusions=[],
                conditional_conclusions=[],
                negative_findings=[],
                failed_hypotheses=[],
                limitations=[],
                conclusion_count=0,
                ledger_fingerprint="experiment-repair-blocked-ledger",
            ),
            traces=[],
            evidence_profile={
                "literature_ready": True,
                "benchmark_provenance_ready": True,
                "benchmark_publication_ready": True,
                "benchmark_scale_ready": True,
            },
            statistics_profiles=[{"run_id": "run_no_stats", "has_statistics": False, "significance_test_count": 0}],
        )
        if action.action_id == "project_insufficient_statistics_repair"
    )
    evidence_profile = {
        "run_profiles": [
            {
                "run_id": "run_no_stats",
                "benchmark_name": "frozen_beir_20",
                "sample_count": 24,
                "split_count": 2,
                "publication_grade": True,
                "provenance_complete": True,
                "source_class": "frozen_snapshot",
            }
        ],
        "benchmark_scale_ready": True,
        "benchmark_provenance_ready": True,
        "benchmark_publication_ready": True,
        "blockers": [],
    }

    _, actions, application_report, rereview_report = (
        autoresearch_project_paper_orchestrator._apply_project_revision_actions(
            project_id=project_id,
            markdown="# Draft\n\n## Experimental Setup\n\n",
            actions=[repair_action],
            evidence_profile=evidence_profile,
            statistics_profiles=[
                {
                    "run_id": "run_no_stats",
                    "has_statistics": False,
                    "aggregate_count": 0,
                    "significance_test_count": 0,
                }
            ],
        )
    )

    blocked = actions[0]
    assert blocked.status == "blocked"
    assert blocked.failure_classification == "insufficient_statistics_outputs"
    assert blocked.residual_blockers
    support_ref = next(
        ref
        for ref in blocked.output_artifact_refs
        if ref.startswith("project_experiment_repair_index:")
    )
    repair_index = json.loads(Path(support_ref.split(":", 1)[1]).read_text(encoding="utf-8"))
    assert repair_index["complete"] is False
    assert repair_index["repair_routes"]["project_insufficient_statistics_repair"]["complete"] is False
    assert "significance" in " ".join(repair_index["blockers"]).lower()
    assert application_report["blocked_action_count"] == 1
    assert rereview_report["rereview_complete"] is False
    assert rereview_report["blocked_action_ids"] == ["project_insufficient_statistics_repair"]
    assert rereview_report["action_reviews"][0]["terminal_condition_met"] is False
    assert rereview_report["action_reviews"][0]["new_blockers"]
    assert rereview_report["action_reviews"][0]["recommendation"] == "continue_repair"


def test_project_experiment_repairs_block_runtime_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-experiment-repair-runtime-failure"
    run = autoresearch_repository.create_run(
        project_id,
        "Runtime failure should block project experiment repair",
        request=AutoResearchRunConfig(task_family_hint="ir_reranking"),
    )
    repair_action = next(
        action
        for action in autoresearch_project_paper_orchestrator._build_project_revision_actions(
            ledger=AutoResearchProjectConclusionLedgerRead(
                project_id=project_id,
                stable_conclusions=[],
                conditional_conclusions=[],
                negative_findings=[],
                failed_hypotheses=[],
                limitations=[],
                conclusion_count=0,
                ledger_fingerprint="experiment-repair-runtime-failure-ledger",
            ),
            traces=[],
            evidence_profile={
                "literature_ready": True,
                "benchmark_provenance_ready": True,
                "benchmark_publication_ready": True,
                "benchmark_scale_ready": False,
            },
            statistics_profiles=[{"run_id": run.id, "has_statistics": True, "significance_test_count": 1}],
        )
        if action.action_id == "project_benchmark_scale_repair"
    )
    failed_run = run.model_copy(
        update={
            "status": "done",
            "artifact": _publication_artifact(include_ablation=True, seed_count=5),
            "experiment_factory_materialized_jobs": [
                AutoResearchExperimentFactoryMaterializedJobRead(
                    job_id="job_runtime_failed",
                    job_kind="candidate_method",
                    executor_mode="local",
                    backend="local",
                    command="python run_failed_candidate.py",
                    expected_outputs=["failed_metrics.json"],
                    output_refs=[],
                    runtime_contract={
                        "executor_mode": "local",
                        "status": "failed",
                        "expected_outputs": ["failed_metrics.json"],
                    },
                    started_at_step=1,
                    completed_at_step=2,
                    failure_classification="runtime_failure",
                    status="failed",
                )
            ],
        }
    )
    evidence_profile = {
        "run_profiles": [
            {
                "run_id": run.id,
                "benchmark_name": "real_claim_evidence_snapshot",
                "sample_count": 24,
                "split_count": 2,
                "publication_grade": True,
                "provenance_complete": True,
                "source_class": "frozen_snapshot",
                "source_dataset_id": "real_claim_evidence_snapshot",
                "source_revision": "2026-06-frozen",
                "source_license": "CC-BY-4.0",
                "source_fingerprint": "runtime-failure-snapshot-fingerprint",
                "verification_label_space": ["supports", "refutes", "not_enough_info"],
            }
        ],
        "benchmark_scale_ready": True,
        "benchmark_provenance_ready": True,
        "benchmark_publication_ready": True,
        "blockers": [],
    }
    statistics_profiles = [
        {
            "run_id": run.id,
            "has_statistics": True,
            "aggregate_count": 1,
            "significance_test_count": 1,
        }
    ]

    _, actions, application_report, rereview_report = (
        autoresearch_project_paper_orchestrator._apply_project_revision_actions(
            project_id=project_id,
            markdown="# Draft\n\n## Experimental Setup\n\n",
            actions=[repair_action],
            selected_runs=[failed_run],
            evidence_profile=evidence_profile,
            statistics_profiles=statistics_profiles,
        )
    )

    blocked = actions[0]
    assert blocked.status == "blocked"
    assert blocked.failure_classification == "runtime_failure"
    support_ref = next(
        ref
        for ref in blocked.output_artifact_refs
        if ref.startswith("project_experiment_repair_index:")
    )
    repair_index = json.loads(Path(support_ref.split(":", 1)[1]).read_text(encoding="utf-8"))
    assert repair_index["complete"] is False
    assert repair_index["execution_coverage_ready"] is False
    assert repair_index["execution_profiles"][0]["failed_materialized_job_count"] == 1
    assert repair_index["execution_profiles"][0]["failure_classifications"] == ["runtime_failure"]
    execution_entry = repair_index["execution_evidence_ledger"]["entries"][0]
    assert execution_entry["failure_classifications"] == ["runtime_failure"]
    assert any("runtime_failure" in item for item in repair_index["blockers"])
    assert application_report["blocked_action_count"] == 1
    assert rereview_report["rereview_complete"] is False
    assert rereview_report["blocked_action_ids"] == ["project_benchmark_scale_repair"]
    assert rereview_report["action_reviews"][0]["terminal_condition_met"] is False
    assert rereview_report["action_reviews"][0]["recommendation"] == "continue_repair"


def test_project_paper_orchestrator_allows_project_paper_for_stable_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    project_id = "project-paper-stable"
    runs = []
    for index, score in enumerate((0.72, 0.74), start=1):
        run = autoresearch_repository.create_run(
            project_id,
            "Shared evidence-aware reranking benchmark",
            request=AutoResearchRunConfig(task_family_hint="ir_reranking"),
        )
        runs.append(
            autoresearch_repository.save_run(
                run.model_copy(
                    update={
                        "status": "done",
                        "artifact": _stable_project_artifact(score),
                    }
                )
            )
        )

    orchestration = autoresearch_project_paper_orchestrator.build_project_paper_orchestration(project_id)

    assert orchestration.candidate_run_count == 2
    assert set(orchestration.selected_run_ids) == {run.id for run in runs}
    assert orchestration.conclusion_ledger.stable_conclusions
    assert orchestration.should_write_paper is True
    assert orchestration.project_level_paper_allowed is True
    assert orchestration.source_strategy == "project_level_paper"
    assert orchestration.paper_decision == "workshop_candidate"
    assert orchestration.project_publish_gate_passed is True
    assert orchestration.core_claim_count >= 1
    assert orchestration.unsupported_core_claim_count == 0
    assert all(trace.evidence_refs for trace in orchestration.claim_traces)
    assert orchestration.project_paper_ready is True
    assert orchestration.project_paper_path is not None
    assert Path(orchestration.project_paper_path).is_file()
    assert orchestration.project_paper_missing_sections == []
    assert "paper_decision=workshop_candidate" in orchestration.project_paper_markdown
    assert orchestration.project_paper_sources_dir is not None
    assert Path(orchestration.project_paper_sources_dir, "paper.md").is_file()
    assert Path(orchestration.project_paper_sources_dir, "main.tex").is_file()
    assert Path(orchestration.project_paper_sources_dir, "references.bib").is_file()
    assert Path(orchestration.project_paper_sources_dir, "manifest.json").is_file()
    assert Path(orchestration.project_paper_sources_dir, "project_revision_action_index.json").is_file()
    assert orchestration.project_paper_compile_report is not None
    assert orchestration.project_paper_compile_report.source_package_complete is True
    assert orchestration.project_paper_revision_action_count >= 3
    assert orchestration.project_paper_revision_pending_action_count >= 3
    assert orchestration.project_paper_revision_completed_action_count == 0
    assert {
        "project_literature_refresh_multi_source",
        "project_benchmark_provenance_repair",
        "project_benchmark_scale_repair",
    }.issubset({action.action_id for action in orchestration.project_paper_revision_actions})
    assert orchestration.project_review_bundle_ready is True
    assert orchestration.project_final_publish_ready is False
    assert orchestration.project_submission_ready is False
    assert orchestration.project_reviewer_response_complete is False
    assert orchestration.project_claim_evidence_index_complete is True
    assert orchestration.project_lineage_archive_complete is True
    assert any("pending revision actions" in item.lower() for item in orchestration.project_submission_blockers)
    assert any("pdflatex is not available" in item for item in orchestration.project_submission_blockers)
    submission_manifest = json.loads(Path(orchestration.project_submission_manifest_path).read_text(encoding="utf-8"))
    assert submission_manifest["bundle_kind"] == "review_bundle"
    assert submission_manifest["review_bundle_ready"] is True
    assert submission_manifest["final_publish_ready"] is False
    assert {item["role"] for item in submission_manifest["generated_assets"]} == {
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
    }
    assert Path(orchestration.project_code_package_path).is_file()
    assert Path(orchestration.project_benchmark_card_path).is_file()
    assert Path(orchestration.project_paper_compiler_evidence_path).is_file()
    assert Path(orchestration.project_publication_evidence_index_path).is_file()
    assert Path(orchestration.project_benchmark_provenance_manifest_path).is_file()
    assert Path(orchestration.project_statistics_report_path).is_file()
    assert Path(orchestration.project_publication_manifest_path).is_file()


def test_evaluation_cases_include_required_internal_cases_and_metrics() -> None:
    suite = autoresearch_evaluation_cases.build_evaluation_case_suite("project-evaluation-cases")

    expected_kinds = {
        "toy_task",
        "medium_benchmark_task",
        "literature_heavy_task",
        "claim_evidence_vertical_task",
        "ablation_heavy_task",
        "failed_hypothesis_task",
    }
    expected_metrics = {
        "idea_to_brief_completeness",
        "hypothesis_selection_quality",
        "novelty_risk_detection",
        "experiment_plan_executability",
        "evidence_consistency",
        "reviewer_score_improvement",
        "final_publish_correctness",
        "offline_end_to_end_submission_package",
    }

    assert suite.case_count == 6
    assert suite.executed_case_count == 6
    assert {case.task_kind for case in suite.cases} == expected_kinds
    assert {metric.metric_id for metric in suite.metrics} == expected_metrics
    assert suite.toy_end_to_end_ready is True
    assert suite.completed_case_count == 6
    assert suite.evaluation_artifact_count > 0
    assert not suite.blockers
    assert not suite.warnings
    assert all(case.idea for case in suite.cases)
    assert all(case.trace is not None for case in suite.cases)
    assert all(case.score == 100 for case in suite.cases)
    assert all(case.expected_brief_quality for case in suite.cases)
    assert all(case.expected_novelty_risks for case in suite.cases)
    assert all(case.expected_experiment_design_requirements for case in suite.cases)
    assert all(case.expected_failure_replan_behavior for case in suite.cases)
    assert any("Architecture" in item for item in suite.scholarflow_paper_materials)
    assert any("Claim-evidence vertical package" in item for item in suite.scholarflow_paper_materials)
    assert any("failure" in item.lower() for item in suite.scholarflow_paper_materials)
    assert len(suite.architecture_materials) >= 5
    assert len(suite.case_study_materials) >= 6
    assert len(suite.failure_analysis_materials) >= 5
    assert all(metric.score == 100 for metric in suite.metrics)
    literature_heavy = next(case for case in suite.cases if case.task_kind == "literature_heavy_task")
    assert literature_heavy.trace is not None
    assert any(
        "Frozen Claim Evidence Reranking" in material
        for material in literature_heavy.trace.architecture_materials
    )
    claim_evidence_vertical = next(
        case for case in suite.cases if case.task_kind == "claim_evidence_vertical_task"
    )
    assert claim_evidence_vertical.trace is not None
    assert claim_evidence_vertical.expected_paper_tier == "workshop_candidate"
    assert "cached_benchmark_execution" in claim_evidence_vertical.trace.steps_completed
    assert "project_paper_orchestration" in claim_evidence_vertical.trace.steps_completed
    assert "project_revision_actions" in claim_evidence_vertical.trace.steps_completed
    assert "project_submission_package" in claim_evidence_vertical.trace.steps_completed
    assert "submission_package_v3_asset_manifest" in claim_evidence_vertical.trace.steps_completed
    assert claim_evidence_vertical.trace.project_paper_path is not None
    assert Path(claim_evidence_vertical.trace.project_paper_path).is_file()
    assert claim_evidence_vertical.trace.project_submission_manifest_path is not None
    assert Path(claim_evidence_vertical.trace.project_submission_manifest_path).is_file()
    assert claim_evidence_vertical.trace.project_publication_manifest_path is not None
    assert Path(claim_evidence_vertical.trace.project_publication_manifest_path).is_file()
    assert claim_evidence_vertical.trace.project_publication_readiness_report_path is not None
    assert Path(claim_evidence_vertical.trace.project_publication_readiness_report_path).is_file()
    assert claim_evidence_vertical.trace.project_experiment_repair_index_path is not None
    assert Path(claim_evidence_vertical.trace.project_experiment_repair_index_path).is_file()
    assert claim_evidence_vertical.trace.project_statistics_report_path is not None
    assert Path(claim_evidence_vertical.trace.project_statistics_report_path).is_file()
    assert claim_evidence_vertical.trace.project_repair_execution_log_path is not None
    assert Path(claim_evidence_vertical.trace.project_repair_execution_log_path).is_file()
    assert claim_evidence_vertical.trace.project_review_findings_path is not None
    assert Path(claim_evidence_vertical.trace.project_review_findings_path).is_file()
    assert claim_evidence_vertical.trace.project_retrieval_evidence_ledger_path is not None
    assert Path(claim_evidence_vertical.trace.project_retrieval_evidence_ledger_path).is_file()
    assert claim_evidence_vertical.trace.project_negative_evidence_report_path is not None
    assert Path(claim_evidence_vertical.trace.project_negative_evidence_report_path).is_file()
    assert claim_evidence_vertical.trace.project_offline_publication_case_path is not None
    assert Path(claim_evidence_vertical.trace.project_offline_publication_case_path).is_file()
    assert claim_evidence_vertical.trace.project_offline_publication_audit_path is not None
    assert Path(claim_evidence_vertical.trace.project_offline_publication_audit_path).is_file()
    assert claim_evidence_vertical.trace.project_review_bundle_ready is True
    assert claim_evidence_vertical.trace.project_final_publish_ready is False
    assert claim_evidence_vertical.trace.project_review_finding_count == (
        claim_evidence_vertical.trace.project_revision_action_count
    )
    assert claim_evidence_vertical.trace.project_review_findings_mapped_to_actions is True
    assert claim_evidence_vertical.trace.project_submission_bundle_kind == "review_bundle"
    assert claim_evidence_vertical.trace.project_submission_required_roles_present is True
    assert claim_evidence_vertical.trace.project_submission_missing_asset_roles == []
    assert {
        "project_paper_compiler_evidence",
        "project_publication_evidence_index",
        "project_review_findings",
        "project_repair_execution_log",
        "project_retrieval_evidence_ledger",
        "project_experiment_repair_index",
        "project_negative_evidence_report",
        "project_offline_publication_case",
        "project_offline_publication_audit",
        "project_publication_manifest",
    }.issubset(set(claim_evidence_vertical.trace.project_submission_asset_roles))
    assert claim_evidence_vertical.trace.project_experiment_execution_source_counts
    assert claim_evidence_vertical.trace.project_materialized_execution_run_ids
    assert claim_evidence_vertical.trace.project_paper_section_coverage_complete is True
    assert claim_evidence_vertical.trace.project_paper_missing_sections == []
    assert "Research Question" in claim_evidence_vertical.trace.project_paper_present_sections
    assert "Benchmark And Data" in claim_evidence_vertical.trace.project_paper_present_sections
    assert "Experimental Setup" in claim_evidence_vertical.trace.project_paper_present_sections
    assert "Results" in claim_evidence_vertical.trace.project_paper_present_sections
    assert "Negative Evidence" in claim_evidence_vertical.trace.project_paper_present_sections
    assert "Limitations" in claim_evidence_vertical.trace.project_paper_present_sections
    assert "Reproducibility" in claim_evidence_vertical.trace.project_paper_present_sections
    assert claim_evidence_vertical.trace.project_supported_core_claim_count >= 1
    assert claim_evidence_vertical.trace.project_claim_ceiling == "workshop_case_study_claim"
    assert claim_evidence_vertical.trace.project_negative_evidence_coverage_complete is True
    assert claim_evidence_vertical.trace.project_negative_evidence_count > 0
    assert any("Do not submit as final publish" in item for item in claim_evidence_vertical.trace.project_kill_criteria)
    assert claim_evidence_vertical.trace.project_required_followups
    assert claim_evidence_vertical.trace.end_to_end_package_ready is True
    assert claim_evidence_vertical.trace.literature_cache_hit_count >= 1
    assert claim_evidence_vertical.trace.real_literature_count >= 3
    assert claim_evidence_vertical.trace.literature_network_enabled is False
    assert claim_evidence_vertical.trace.literature_source_counts["arxiv"] >= 1
    assert claim_evidence_vertical.trace.literature_source_counts["semantic_scholar"] >= 1
    assert claim_evidence_vertical.trace.literature_source_counts["crossref"] >= 1
    assert any(
        "Project publish gate has not passed" in item
        for item in claim_evidence_vertical.trace.project_submission_blockers
    )
    assert "Evidence Ledger Guided Claim Verification" in Path(
        claim_evidence_vertical.trace.project_paper_path
    ).read_text(encoding="utf-8")
    submission_payload = json.loads(
        Path(claim_evidence_vertical.trace.project_submission_manifest_path).read_text(encoding="utf-8")
    )
    assert submission_payload["review_bundle_ready"] is True
    assert submission_payload["final_publish_ready"] is False
    assert submission_payload["bundle_kind"] == claim_evidence_vertical.trace.project_submission_bundle_kind
    submission_run_ids = submission_payload["selected_run_ids"]
    assert {
        item["role"]
        for item in submission_payload["generated_assets"]
    } >= set(claim_evidence_vertical.trace.project_submission_asset_roles)
    assert all(item["source_action"] for item in submission_payload["generated_assets"])
    assert all(item["readiness_contribution"] for item in submission_payload["generated_assets"])
    assert all("source_evidence_refs" in item for item in submission_payload["generated_assets"])
    assert all(item["missing_status"] == "present" for item in submission_payload["generated_assets"])
    assert all(
        set(item["source_run_ids"]) == set(submission_run_ids)
        for item in submission_payload["generated_assets"]
    )
    readiness_report_path = (
        Path(claim_evidence_vertical.trace.project_submission_manifest_path).parent
        / "publication_readiness_report.json"
    )
    readiness_report = json.loads(readiness_report_path.read_text(encoding="utf-8"))
    assert readiness_report["final_publish_ready"] is False
    assert readiness_report["kill_criteria"] == claim_evidence_vertical.trace.project_kill_criteria
    assert readiness_report["required_followups"] == claim_evidence_vertical.trace.project_required_followups
    assert readiness_report["selected_run_count"] == 2
    assert {
        item["source_kind"]
        for item in readiness_report["evidence_profile"]["run_profiles"]
    } == {"scifact_json", "beir_json"}
    assert readiness_report["evidence_profile"]["replication_ready"] is True
    assert readiness_report["evidence_profile"]["benchmark_publication_ready"] is False
    assert all(
        item["publication_grade"] is False
        for item in readiness_report["evidence_profile"]["run_profiles"]
    )
    assert readiness_report["evidence_profile"]["literature_ready"] is True
    assert readiness_report["evidence_profile"]["real_literature_count"] >= 3
    readiness_checks_by_id = {item["check_id"]: item for item in readiness_report["checks"]}
    assert readiness_checks_by_id["execution_evidence"]["passed"] is True
    assert readiness_checks_by_id["execution_evidence"]["execution_source_counts"] == (
        claim_evidence_vertical.trace.project_experiment_execution_source_counts
    )
    assert set(readiness_report["evidence_profile"]["real_literature_sources"]) >= {
        "arxiv",
        "semantic_scholar",
        "crossref",
    }
    experiment_repair_index = json.loads(
        Path(claim_evidence_vertical.trace.project_experiment_repair_index_path).read_text(encoding="utf-8")
    )
    assert experiment_repair_index["execution_coverage_ready"] is True
    assert experiment_repair_index["execution_source_counts"] == (
        claim_evidence_vertical.trace.project_experiment_execution_source_counts
    )
    assert experiment_repair_index["materialized_execution_run_ids"] == (
        claim_evidence_vertical.trace.project_materialized_execution_run_ids
    )
    statistics_report = json.loads(
        Path(claim_evidence_vertical.trace.project_statistics_report_path).read_text(encoding="utf-8")
    )
    assert statistics_report["per_method_metric_table"]
    assert statistics_report["aggregate_metric_table"]
    assert statistics_report["paired_comparisons"]
    assert statistics_report["confidence_intervals"]
    assert statistics_report["execution_coverage"]["complete"] is True
    assert statistics_report["execution_coverage"]["execution_source_counts"] == (
        claim_evidence_vertical.trace.project_experiment_execution_source_counts
    )
    assert statistics_report["negative_evidence_summary"]
    assert statistics_report["claim_ceiling_recommendation"] == (
        claim_evidence_vertical.trace.project_claim_ceiling
    )
    assert any("scoped" in item.lower() for item in statistics_report["statistics_limitations"])
    compiler_evidence = json.loads(
        Path(claim_evidence_vertical.trace.project_submission_manifest_path).parent.joinpath(
            "../paper_sources/paper_compiler_evidence.json"
        ).resolve().read_text(encoding="utf-8")
    )
    assert compiler_evidence["section_coverage"]["complete"] is True
    assert {
        "Research Question",
        "Benchmark And Data",
        "Negative Evidence",
        "Reproducibility",
    }.issubset(set(compiler_evidence["section_coverage"]["present_sections"]))
    assert compiler_evidence["claim_support_coverage"]["supported_core_claim_count"] == (
        claim_evidence_vertical.trace.project_supported_core_claim_count
    )
    assert compiler_evidence["statistics_coverage"]["failure_case_count"] > 0
    assert compiler_evidence["execution_coverage"]["complete"] is True
    assert compiler_evidence["execution_coverage"]["execution_evidence_ledger"]["complete_entry_count"] == 2
    assert any(
        "Cached SciFact-style Claim Evidence Evaluation" in material
        for material in claim_evidence_vertical.trace.case_study_materials
    )
    assert any(
        "BEIR-style retrieval run" in material
        for material in claim_evidence_vertical.trace.case_study_materials
    )
    assert any(
        "project-level manuscript" in material
        for material in claim_evidence_vertical.trace.case_study_materials
    )
    assert any(
        "unsupported-claim detection" in requirement.lower()
        for requirement in claim_evidence_vertical.expected_experiment_design_requirements
    )


def test_toy_evaluation_case_runs_idea_to_evidence_package() -> None:
    suite = autoresearch_evaluation_cases.build_evaluation_case_suite("project-evaluation-toy")
    toy = next(case for case in suite.cases if case.task_kind == "toy_task")

    assert toy.trace is not None
    trace = toy.trace
    assert trace.idea == toy.idea
    assert trace.brief_id is not None
    assert trace.selected_hypothesis_id is not None
    assert trace.experiment_plan_id == "experiment_factory_v1"
    assert trace.evidence_ledger_id == "experiment_evidence_ledger_v1"
    assert trace.result_artifact_status == "done"
    assert trace.primary_metric is not None
    assert trace.objective_score is not None
    assert trace.paper_decision == "technical_report"
    assert {
        "idea",
        "research_brief",
        "literature_scout",
        "gap_mining",
        "hypothesis_selection",
        "experiment_plan",
        "toy_execution",
        "evidence_ledger",
        "paper_draft",
        "review_package",
    }.issubset(set(trace.steps_completed))
    assert 2 <= trace.direction_count <= 5
    assert trace.hypothesis_count == trace.direction_count
    assert trace.experiment_job_count > 0
    assert trace.evidence_entry_count > 0
    assert trace.repair_action_count == 0
    assert trace.evidence_complete is True
    assert trace.paper_review_package_ready is True
    assert trace.architecture_materials
    assert trace.case_study_materials
    assert trace.failure_analysis_materials
    assert trace.blockers == []
    assert toy.score == 100
    assert toy.expected_paper_tier == "technical_report"


def test_all_evaluation_cases_execute_offline_to_paper_packages() -> None:
    suite = autoresearch_evaluation_cases.build_evaluation_case_suite("project-evaluation-all")

    for case in suite.cases:
        assert case.trace is not None
        assert case.trace.paper_review_package_ready is True
        assert case.trace.evidence_complete is True
        assert case.trace.experiment_job_count > 0
        assert case.trace.evidence_entry_count > 0
        assert case.trace.blockers == []
        assert "paper_draft" in case.trace.steps_completed
        assert "review_package" in case.trace.steps_completed
        assert case.trace.case_study_materials


def test_narrative_artifact_summary_uses_objective_system_when_best_missing() -> None:
    artifact = ResultArtifact(
        status="done",
        summary="The objective system is present even without a best-system alias.",
        key_findings=["objective system is the selected outcome"],
        primary_metric="macro_f1",
        objective_system="candidate_system",
        objective_score=0.83,
        system_results=[],
        aggregate_system_results=[],
        acceptance_checks=[],
        tables=[],
        environment={},
        outputs={},
    )

    summary = narrative_analyst._artifact_summary(artifact)

    assert "Best system: candidate_system, macro_f1=0.8300" in summary


def test_llm_client_enables_deepseek_v4_thinking_defaults(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"role": "assistant", "content": "OK"}}]}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_api_base", "https://api.deepseek.com")
    monkeypatch.setattr(llm_client, "litellm_completion", fake_completion)

    response = llm_client.chat(
        [{"role": "user", "content": "Return OK"}],
        model="openai/deepseek-v4-pro",
        temperature=0.2,
        top_p=0.9,
    )

    assert response["choices"][0]["message"]["content"] == "OK"
    assert captured["model"] == "openai/deepseek-v4-pro"
    assert captured["extra_body"] == {"thinking": {"type": "enabled"}}
    assert captured["reasoning_effort"] == "high"
    assert "reasoning_effort" in captured["allowed_openai_params"]
    assert "temperature" not in captured
    assert "top_p" not in captured
