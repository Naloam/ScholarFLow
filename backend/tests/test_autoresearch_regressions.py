from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import services.autoresearch.orchestrator as autoresearch_orchestrator
import services.autoresearch.console as autoresearch_console
import services.autoresearch.narrative_analyst as narrative_analyst
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
    AutoResearchNoveltyAssessmentRead,
    AutoResearchPaperCompileReportRead,
    AutoResearchPaperPlanRead,
    AutoResearchPaperPlanSectionRead,
    AutoResearchPublishPackageRead,
    AutoResearchRegistryAssetRef,
    AutoResearchRunConfig,
    AutoResearchRunExecutionRead,
    AutoResearchRunRead,
    AutoResearchRunRegistryFiles,
    BenchmarkSource,
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
)
from schemas.papers import PaperMeta
from services.autoresearch.benchmarks import ResolvedBenchmark, build_experiment_spec, builtin_benchmark
from services.autoresearch.research_readiness import build_publication_readiness, enforce_publication_protocol
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


def _publication_literature() -> list[LiteratureInsight]:
    return [
        LiteratureInsight(
            paper_id="paper_pub_1",
            title="Benchmarking Compact Retrieval Pipelines",
            year=2024,
            source="semantic_scholar",
            insight="Provides real related-work context for compact retrieval benchmarks.",
        ),
        LiteratureInsight(
            paper_id="paper_pub_2",
            title="Lightweight Lexical Signals for Reranking",
            year=2023,
            source="semantic_scholar",
            insight="Motivates lexical baselines and controlled reranking comparisons.",
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
            "min_metrics": {"accuracy": 0.5, "macro_f1": 0.5},
            "max_metrics": {"accuracy": 0.5, "macro_f1": 0.5},
            "sample_count": seed_count,
        },
        {
            "system": "candidate_system",
            "mean_metrics": {"accuracy": 0.8, "macro_f1": 0.8},
            "std_metrics": {"accuracy": 0.01, "macro_f1": 0.01},
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
            }
        ],
        tables=[],
        environment={},
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


def test_autoresearch_attempt_preference_keeps_richer_tied_artifact() -> None:
    orchestrator = autoresearch_orchestrator.AutoResearchOrchestrator()
    narrow = _publication_artifact(include_ablation=False, seed_count=5)
    richer = _publication_artifact(include_ablation=True, seed_count=5)

    assert orchestrator._attempt_preference_key(richer) > orchestrator._attempt_preference_key(narrow)


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

    findings, evidence, citation_coverage = review_publish._review_findings(
        run=run,
        bundle=None,
        selected_manifest_source="file",
        paper_markdown=run.paper_markdown or "",
        novelty_assessment=novelty,
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
    findings, evidence, citation_coverage = review_publish._review_findings(
        run=run,
        bundle=None,
        selected_manifest_source="file",
        paper_markdown=run.paper_markdown or "",
        novelty_assessment=novelty,
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
