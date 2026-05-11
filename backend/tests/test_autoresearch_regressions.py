from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import services.autoresearch.orchestrator as autoresearch_orchestrator
import services.autoresearch.repository as autoresearch_repository
import services.papers.repository as papers_repository
from config.settings import settings
from models.base import Base
from models.project import Project
from schemas.autoresearch import (
    ExperimentAttempt,
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
