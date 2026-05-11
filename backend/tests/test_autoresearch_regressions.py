from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import services.autoresearch.orchestrator as autoresearch_orchestrator
import services.autoresearch.repository as autoresearch_repository
import services.autoresearch.review_publish as review_publish
import services.autoresearch.writer as autoresearch_writer
import services.papers.repository as papers_repository
from config.settings import settings
from models.base import Base
from models.project import Project
from schemas.autoresearch import (
    AutoResearchPaperPlanRead,
    AutoResearchPaperPlanSectionRead,
    AutoResearchRunRead,
    ExperimentAttempt,
    ExperimentSpec,
    HypothesisCandidate,
    LiteratureSynthesis,
    LiteratureTheme,
    PortfolioSummary,
    ResearchPlan,
    ResearchProgram,
    ResultArtifact,
)
from schemas.papers import PaperMeta
from services.autoresearch.benchmarks import build_experiment_spec, builtin_benchmark
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

    finding = review_publish._hypothesis_resolution_finding(run)

    assert finding is not None
    assert finding[0] == "warning"
    assert "`candidate_system`" in finding[2]
