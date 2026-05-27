from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import services.autoresearch.orchestrator as autoresearch_orchestrator
import services.autoresearch.console as autoresearch_console
import services.autoresearch.artifact_integrity_audit as artifact_integrity_audit
import services.autoresearch.evaluation_cases as autoresearch_evaluation_cases
import services.autoresearch.experiment_factory as autoresearch_experiment_factory
import services.autoresearch.idea_brief as autoresearch_idea_brief
import services.autoresearch.literature_connectors as autoresearch_literature_connectors
import services.autoresearch.literature_scout as autoresearch_literature_scout
import services.autoresearch.narrative_analyst as narrative_analyst
import services.autoresearch.planner as autoresearch_planner
import services.autoresearch.project_paper_orchestrator as autoresearch_project_paper_orchestrator
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
    AutoResearchClaimEvidenceEntryRead,
    AutoResearchClaimEvidenceMatrixRead,
    AutoResearchClaimEvidenceRefRead,
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
)
from schemas.papers import PaperMeta
from services.autoresearch.benchmarks import ResolvedBenchmark, build_experiment_spec, builtin_benchmark
from services.autoresearch.benchmark_card import build_benchmark_card
from services.autoresearch.contribution_assessment import build_contribution_assessment
from services.autoresearch.experiment_design import build_experiment_design
from services.autoresearch.failure_replanning import build_failure_analysis, build_research_replan
from services.autoresearch.literature_novelty import build_literature_graph, build_novelty_validation
from services.autoresearch.paper_evidence_compiler import compile_paper_evidence
from services.autoresearch.methodology_audit import build_methodology_audit
from services.autoresearch.publication_repair_execution import build_publication_repair_execution
from services.autoresearch.research_protocol import build_research_protocol
from services.autoresearch.research_readiness import (
    PUBLICATION_MIN_COMPLETED_SEEDS,
    build_publication_readiness,
    enforce_publication_protocol,
)
from services.autoresearch.writer import PaperWriter


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
    assert any("built-in toy benchmarks" in item for item in readiness.blockers)
    assert any("minimum completed seeds" in item for item in readiness.blockers)


def test_publication_readiness_accepts_external_profile_with_final_ablation_evidence() -> None:
    spec, benchmark = _external_publication_spec()
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


def test_evaluation_cases_include_required_internal_cases_and_metrics() -> None:
    suite = autoresearch_evaluation_cases.build_evaluation_case_suite("project-evaluation-cases")

    expected_kinds = {
        "toy_task",
        "medium_benchmark_task",
        "literature_heavy_task",
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
    }

    assert suite.case_count == 5
    assert {case.task_kind for case in suite.cases} == expected_kinds
    assert {metric.metric_id for metric in suite.metrics} == expected_metrics
    assert suite.toy_end_to_end_ready is True
    assert suite.completed_case_count == 1
    assert not suite.blockers
    assert all(case.idea for case in suite.cases)
    assert all(case.expected_brief_quality for case in suite.cases)
    assert all(case.expected_novelty_risks for case in suite.cases)
    assert all(case.expected_experiment_design_requirements for case in suite.cases)
    assert all(case.expected_failure_replan_behavior for case in suite.cases)
    assert any("Architecture" in item for item in suite.scholarflow_paper_materials)
    assert any("failure" in item.lower() for item in suite.scholarflow_paper_materials)


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
    assert trace.evidence_complete is True
    assert trace.paper_review_package_ready is True
    assert trace.blockers == []
    assert toy.score == 100
    assert toy.expected_paper_tier == "technical_report"


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
