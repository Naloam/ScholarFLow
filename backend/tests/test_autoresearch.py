from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import api.autoresearch as autoresearch_api
import api.export as export_api
import api.progress as progress_api
import api.review as review_api
import main as main_module
import models  # noqa: F401
import services.autoresearch.codegen as autoresearch_codegen
import services.autoresearch.ingestion as autoresearch_ingestion
import services.autoresearch.literature_pipeline as literature_pipeline
import services.autoresearch.repair as autoresearch_repair
from services.autoresearch.benchmarks import build_experiment_spec, builtin_benchmark
from services.autoresearch.runner import AutoExperimentRunner
import services.llm.client as llm_client
from config import db as db_module
from config import deps as deps_module
from config.settings import settings
from main import app
from models.base import Base
from schemas.autoresearch import ExperimentAttempt, ExperimentSpec, ResearchPlan, ResultArtifact, SweepConfig
from schemas.papers import PaperMeta
from schemas.search import SearchResult


def _configure_test_client(monkeypatch, tmp_path: Path) -> TestClient:
    db_path = tmp_path / "autorresearch.sqlite3"
    data_dir = tmp_path / "data"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    monkeypatch.setattr(settings, "data_dir", data_dir)
    monkeypatch.setattr(llm_client, "litellm_completion", None)
    monkeypatch.setattr(db_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(main_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(deps_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(progress_api, "SessionLocal", testing_session_local)
    monkeypatch.setattr(review_api, "SessionLocal", testing_session_local)
    monkeypatch.setattr(export_api, "SessionLocal", testing_session_local)
    monkeypatch.setattr(autoresearch_api, "SessionLocal", testing_session_local)
    return TestClient(app)


def _create_project(client: TestClient, title: str, topic: str) -> str:
    response = client.post(
        "/api/projects",
        json={
            "title": title,
            "topic": topic,
            "template_id": "builtin:general_paper",
            "status": "init",
        },
    )
    assert response.status_code == 200
    project_id = response.json()["id"]
    assert project_id
    return project_id


def test_autoresearch_text_run_generates_grounded_paper(monkeypatch, tmp_path: Path) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "CS AutoResearch Text",
            "Automatic topic classification for compact CS abstracts",
        )

        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        run_detail = client.get(f"/api/projects/{project_id}/auto-research/{run_id}")
        assert run_detail.status_code == 200
        run = run_detail.json()
        assert run["status"] == "done"
        assert run["task_family"] == "text_classification"
        assert run["spec"]["benchmark_name"] == "toy_cs_abstract_topic"
        assert run["program"]["id"].endswith("_program")
        assert run["program"]["benchmark_name"] == "toy_cs_abstract_topic"
        assert run["artifact"]["status"] == "done"
        assert len(run["attempts"]) == 3
        assert len(run["candidates"]) == 3
        assert run["portfolio"]["status"] == "done"
        assert run["portfolio"]["total_candidates"] == 3
        assert len(run["portfolio"]["candidate_rankings"]) == 3
        assert len(run["portfolio"]["executed_candidate_ids"]) == 3
        assert len(run["portfolio"]["decisions"]) == 3
        assert run["attempts"][0]["goal"] == "initial_run"
        assert run["attempts"][-1]["strategy"] == "naive_bayes_search"
        assert run["selected_round_index"] is not None
        assert run["artifact"]["best_system"]
        assert len(run["artifact"]["tables"]) >= 1
        assert len(run["artifact"]["aggregate_system_results"]) >= 1
        assert any(
            "macro_f1" in item["confidence_intervals"]
            for item in run["artifact"]["aggregate_system_results"]
        )
        assert len(run["artifact"]["significance_tests"]) >= 1
        assert len(run["artifact"]["negative_results"]) >= 1
        assert len(run["artifact"]["per_seed_results"]) == len(run["spec"]["seeds"])
        assert len(run["artifact"]["sweep_results"]) == len(run["spec"]["sweeps"])
        assert run["artifact"]["sweep_results"][0]["objective_score_confidence_interval"] is not None
        assert run["artifact"]["environment"]["selected_sweep"]
        assert any(table["title"] == "Confidence Intervals" for table in run["artifact"]["tables"])
        assert any(table["title"] == "Significance Tests" for table in run["artifact"]["tables"])
        assert any(table["title"] == "Negative Results" for table in run["artifact"]["tables"])
        assert Path(run["generated_code_path"]).is_file()
        run_dir = Path(run["paper_path"]).parent
        assert (run_dir / "program.json").is_file()
        assert (run_dir / "portfolio.json").is_file()
        assert len(list((run_dir / "candidates").glob("*.json"))) == 3
        assert run["spec"]["seeds"] == [7, 13]
        assert len(run["spec"]["sweeps"]) == 2
        assert all(isinstance(item, dict) for item in run["spec"]["acceptance_criteria"])
        assert any(item["kind"] == "aggregate_metric_reporting" for item in run["spec"]["acceptance_criteria"])
        aggregate_rule = next(
            item for item in run["spec"]["acceptance_criteria"] if item["kind"] == "aggregate_metric_reporting"
        )
        assert "confidence_interval" in aggregate_rule["required_statistics"]
        assert any(item["kind"] == "significance_test_reporting" for item in run["spec"]["acceptance_criteria"])
        selected_candidate = next(
            item for item in run["candidates"] if item["id"] == run["portfolio"]["selected_candidate_id"]
        )
        candidate_scores = [
            item["score"]
            for item in run["candidates"]
            if item["score"] is not None
        ]
        assert candidate_scores
        assert selected_candidate["rank"] == 1
        assert selected_candidate["status"] == "done"
        assert selected_candidate["artifact"]["status"] == "done"
        assert selected_candidate["selected_round_index"] == run["selected_round_index"]
        assert selected_candidate["score"] == max(candidate_scores)
        assert Path(selected_candidate["workspace_path"]).is_dir()
        assert Path(selected_candidate["plan_path"]).is_file()
        assert Path(selected_candidate["spec_path"]).is_file()
        assert Path(selected_candidate["attempts_path"]).is_file()
        assert Path(selected_candidate["artifact_path"]).is_file()
        assert Path(selected_candidate["manifest_path"]).is_file()
        assert Path(selected_candidate["paper_path"]).is_file()
        assert all(item["status"] == "done" for item in run["candidates"])
        assert all(item["attempts"] for item in run["candidates"])
        assert all(Path(item["workspace_path"]).is_dir() for item in run["candidates"])
        assert all(Path(item["plan_path"]).is_file() for item in run["candidates"])
        assert all(Path(item["spec_path"]).is_file() for item in run["candidates"])
        assert all(Path(item["attempts_path"]).is_file() for item in run["candidates"])
        assert all(Path(item["artifact_path"]).is_file() for item in run["candidates"])
        assert all(Path(item["manifest_path"]).is_file() for item in run["candidates"])
        assert any(record["selected"] for record in run["portfolio"]["decisions"])
        assert any("Won the executed portfolio" in record["reason"] for record in run["portfolio"]["decisions"])
        assert any(record["outcome"] == "promoted" for record in run["portfolio"]["decisions"])
        assert all(record["criteria"] for record in run["portfolio"]["decisions"])
        selected_record = next(
            item for item in run["portfolio"]["decisions"] if item["candidate_id"] == selected_candidate["id"]
        )
        assert selected_record["outcome"] == "promoted"
        manifest = json.loads(Path(selected_candidate["manifest_path"]).read_text(encoding="utf-8"))
        assert manifest["decision"]["outcome"] == "promoted"
        assert manifest["files"]["paper_path"] == selected_candidate["paper_path"]

        paper = run["paper_markdown"]
        assert "## 2. Related Work and Research Plan" in paper
        assert "Portfolio planning generated 3 ranked candidates" in paper
        assert "## 4. Experimental Setup" in paper
        assert "## 5. Results" in paper
        assert "| System | Accuracy | Macro F1 |" in paper
        assert "Aggregate Stability" in paper
        assert "Confidence Intervals" in paper
        assert "Significance Tests" in paper
        assert "Negative results retained in the artifact" in paper
        assert "95% CI" in paper
        assert "Acceptance checks for the selected configuration" in paper
        assert "## 7. Limitations" in paper
        assert "recorded experiment outputs" in paper

        drafts = client.get(f"/api/projects/{project_id}/drafts")
        assert drafts.status_code == 200
        draft_items = drafts.json()
        assert len(draft_items) == 1
        assert draft_items[0]["section"] == "autorresearch_v0"
        assert "## 5. Results" in draft_items[0]["content"]

        export_response = client.post(
            f"/api/projects/{project_id}/export",
            json={"format": "markdown"},
        )
        assert export_response.status_code == 200
        export_id = export_response.json()["id"]

        download_response = client.get(f"/api/projects/{project_id}/export/{export_id}/download")
        assert download_response.status_code == 200
        assert "| System | Accuracy | Macro F1 |" in download_response.text
    finally:
        client.close()


def test_autoresearch_tabular_run_supports_second_task_family(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "CS AutoResearch Tabular",
            "Training run stability prediction from tabular features",
        )

        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Training run stability prediction from tabular features",
                "task_family_hint": "tabular_classification",
            },
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        run_detail = client.get(f"/api/projects/{project_id}/auto-research/{run_id}")
        assert run_detail.status_code == 200
        run = run_detail.json()
        assert run["status"] == "done"
        assert run["task_family"] == "tabular_classification"
        assert run["spec"]["benchmark_name"] == "toy_training_run_stability"
        assert len(run["attempts"]) == 3

        all_systems = {
            item["system"]
            for attempt in run["attempts"]
            for item in (attempt.get("artifact") or {}).get("system_results", [])
        }
        systems = {item["system"] for item in run["artifact"]["system_results"]}
        assert "threshold_rule" in systems
        assert "perceptron_scaled" in all_systems
        assert "perceptron_unscaled" in all_systems
        assert "## 3. Method" in run["paper_markdown"]
        assert "Toy Training Run Stability" in run["paper_markdown"]
    finally:
        client.close()


def test_autoresearch_selects_best_executed_candidate_from_portfolio(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)

    def fake_run(
        self,
        *,
        plan,
        spec,
        round_index,
        **kwargs,
    ):
        del self, kwargs
        if "narrower modeling delta" in plan.proposed_method:
            candidate_label = "baseline_anchor"
            score = 0.84
        elif "robustness checks" in plan.proposed_method:
            candidate_label = "stability_probe"
            score = 0.72
        else:
            candidate_label = "primary_method"
            score = 0.79
        strategy = spec.search_strategies[min(round_index - 1, len(spec.search_strategies) - 1)]
        code_path = tmp_path / f"{candidate_label}_{round_index}.py"
        code_path.write_text(f"# {candidate_label} round {round_index}\n", encoding="utf-8")
        artifact = ResultArtifact(
            status="done",
            summary=f"{candidate_label} round {round_index}",
            key_findings=[candidate_label],
            primary_metric="macro_f1",
            best_system="demo_system",
            objective_system="demo_system",
            objective_score=score,
            system_results=[
                {"system": "majority", "metrics": {"accuracy": 0.40, "macro_f1": 0.40}},
                {"system": "demo_system", "metrics": {"accuracy": score, "macro_f1": score}},
            ],
            aggregate_system_results=[
                {
                    "system": "majority",
                    "mean_metrics": {"accuracy": 0.40, "macro_f1": 0.40},
                    "std_metrics": {"accuracy": 0.0, "macro_f1": 0.0},
                    "min_metrics": {"accuracy": 0.40, "macro_f1": 0.40},
                    "max_metrics": {"accuracy": 0.40, "macro_f1": 0.40},
                    "sample_count": 1,
                },
                {
                    "system": "demo_system",
                    "mean_metrics": {"accuracy": score, "macro_f1": score},
                    "std_metrics": {"accuracy": 0.0, "macro_f1": 0.0},
                    "min_metrics": {"accuracy": score, "macro_f1": score},
                    "max_metrics": {"accuracy": score, "macro_f1": score},
                    "sample_count": 1,
                },
            ],
            acceptance_checks=[
                {
                    "criterion": "Record mean and standard deviation for the primary metric.",
                    "passed": True,
                    "detail": "Synthetic candidate passed.",
                }
            ],
            tables=[
                {
                    "title": "Main Results",
                    "columns": ["System", "Macro F1"],
                    "rows": [["majority", "0.4000"], ["demo_system", f"{score:.4f}"]],
                }
            ],
            environment={
                "executor_mode": "synthetic",
                "python_version": "3.11.0",
                "platform": "test-platform",
                "runtime_seconds": 0.01,
                "selected_sweep": "default",
                "seed_count": 1,
            },
        )
        return strategy, str(code_path), artifact

    monkeypatch.setattr(AutoExperimentRunner, "run", fake_run)
    try:
        project_id = _create_project(
            client,
            "Portfolio Winner Project",
            "Automatic topic classification for compact CS abstracts",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "done"
        assert run["portfolio"]["selected_candidate_id"].endswith("cand_02")
        assert run["candidates"][0]["id"] == run["portfolio"]["selected_candidate_id"]
        assert run["artifact"]["summary"].startswith("baseline_anchor")
        assert Path(run["generated_code_path"]).name.startswith("baseline_anchor_")
        assert len(run["attempts"]) == 2
        assert run["spec"]["search_strategies"] == [
            "keyword_rule_search",
            "naive_bayes_limited_vocab_search",
        ]
        winner = run["candidates"][0]
        assert "Won the executed portfolio" in winner["selection_reason"]
        assert Path(winner["workspace_path"]).is_dir()
        assert Path(winner["manifest_path"]).is_file()
        assert len(run["portfolio"]["decisions"]) == 3
        assert run["portfolio"]["decisions"][0]["candidate_id"] == winner["id"]
        assert run["portfolio"]["decisions"][0]["outcome"] == "promoted"
        assert run["portfolio"]["decisions"][1]["outcome"] == "eliminated"
    finally:
        client.close()


def test_autoresearch_can_pull_remote_csv_benchmark(monkeypatch, tmp_path: Path) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    csv_payload = """text,label,split
retrieval models rank documents,retrieval,train
query expansion improves recall,retrieval,train
gpu cache compression helps serving,systems,train
kernel fusion lowers latency,systems,train
static analysis tracks taint,analysis,train
symbolic execution explores paths,analysis,train
reranking helps search quality,retrieval,test
cluster scheduling improves throughput,systems,test
abstract interpretation proves safety,analysis,test
"""
    monkeypatch.setattr(autoresearch_ingestion, "_fetch_remote_text", lambda url: csv_payload)
    try:
        project_id = _create_project(
            client,
            "Remote Benchmark Project",
            "External benchmark ingestion for text classification",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "External benchmark ingestion for text classification",
                "benchmark": {
                    "kind": "remote_csv",
                    "url": "https://example.com/benchmark.csv",
                    "text_field": "text",
                    "label_field": "label",
                    "split_field": "split",
                },
            },
        )
        assert response.status_code == 200
        run_id = response.json()["id"]

        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "done"
        assert run["benchmark"]["kind"] == "remote_csv"
        assert run["spec"]["dataset"]["train_size"] == 6
        assert run["spec"]["dataset"]["test_size"] == 3
        assert run["artifact"]["environment"]["source_url"] == "https://example.com/benchmark.csv"
    finally:
        client.close()


def test_autoresearch_repairs_after_failed_first_attempt(monkeypatch, tmp_path: Path) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    original_generate = autoresearch_codegen.ExperimentCodeGenerator.generate
    calls = {"count": 0}

    def flaky_generate(self, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return "forced_failure", 'raise RuntimeError("synthetic failure")'
        return original_generate(self, **kwargs)

    monkeypatch.setattr(autoresearch_codegen.ExperimentCodeGenerator, "generate", flaky_generate)
    try:
        project_id = _create_project(
            client,
            "Repair Loop Project",
            "Automatic topic classification with repair loop",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification with repair loop"},
        )
        assert response.status_code == 200
        run_id = response.json()["id"]

        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "done"
        assert run["attempts"][0]["status"] == "failed"
        assert run["attempts"][1]["goal"] == "repair_previous_failure"
        assert run["selected_round_index"] >= 2
        assert run["attempts"][1]["repair_summary"]["strategy"] == "repair_regenerate"
        assert "fallback_to_regenerate" in run["attempts"][1]["repair_summary"]["sanity_checks"]
    finally:
        client.close()


def test_autoresearch_traceback_patch_repairs_inline_failure(monkeypatch, tmp_path: Path) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    original_generate = autoresearch_codegen.ExperimentCodeGenerator.generate
    calls = {"count": 0}

    def flaky_generate(self, **kwargs):
        strategy, code = original_generate(self, **kwargs)
        calls["count"] += 1
        if calls["count"] == 1:
            broken = code.replace(
                '    started = time.perf_counter()\n',
                '    started = time.perf_counter()\n    raise RuntimeError("traceback patch trigger")\n',
                1,
            )
            return "inline_runtime_failure", broken
        return strategy, code

    monkeypatch.setattr(autoresearch_codegen.ExperimentCodeGenerator, "generate", flaky_generate)
    try:
        project_id = _create_project(
            client,
            "Traceback Patch Project",
            "Automatic topic classification with traceback patch repair",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification with traceback patch repair"},
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "done"
        assert run["attempts"][0]["status"] == "failed"
        assert run["attempts"][1]["strategy"] == "repair_local_patch"
        assert run["attempts"][1]["status"] == "done"
        assert run["attempts"][1]["repair_summary"]["patch_line_count"] >= 1
        assert "patch_is_local" in run["attempts"][1]["repair_summary"]["sanity_checks"]
    finally:
        client.close()


def test_runner_aggregates_across_seeds_and_sweeps(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    runner = AutoExperimentRunner()
    plan = ResearchPlan(
        topic="Automatic topic classification for compact CS abstracts",
        title="Seeded Sweep Runner Test",
        task_family="text_classification",
        problem_statement="Test aggregate selection.",
        motivation="Verify runner aggregation.",
        proposed_method="Evaluate a compact lexical model across seeds and sweeps.",
        research_questions=["Does the runner pick the strongest sweep?"],
        hypotheses=["The stronger sweep should win on mean macro F1."],
        planned_contributions=["Aggregate metrics across seeds and sweeps."],
        experiment_outline=["Run the generated code over every seed/sweep pair."],
        scope_limits=["This is a unit-level runner test."],
    )
    spec = build_experiment_spec("text_classification", builtin_benchmark("text_classification")).model_copy(
        update={
            "seeds": [7, 13],
            "sweeps": [
                SweepConfig(label="base", params={"variant": "base"}),
                SweepConfig(label="better", params={"variant": "better"}),
            ],
        }
    )
    observed_envs: list[dict[str, str]] = []

    def fake_generate(self, **kwargs):
        del kwargs
        return "naive_bayes_search", 'print("__RESULT__" + "{}")'

    def fake_run(payload: dict[str, object]) -> dict[str, object]:
        env = payload.get("env")
        assert isinstance(env, dict)
        observed_envs.append({str(key): str(value) for key, value in env.items()})
        seed = int(env["SCHOLARFLOW_SEED"])
        sweep = json.loads(env["SCHOLARFLOW_SWEEP_JSON"])
        variant = sweep.get("variant")
        bonus = 0.20 if variant == "better" else 0.05
        score = round(0.55 + bonus + (0.01 if seed == 13 else 0.0), 4)
        return {
            "logs": f"seed={seed} sweep={variant}",
            "outputs": {
                "returncode": 0,
                "executor_mode": "local",
                "docker_image": None,
                "workdir": str(tmp_path),
                "duration_ms": 12,
                "host_platform": "test-platform",
                "host_python": "3.11.0",
                "result": {
                    "summary": f"sweep={variant} seed={seed}",
                    "primary_metric": "macro_f1",
                    "best_system": "naive_bayes",
                    "objective_system": "naive_bayes",
                    "objective_score": score,
                    "key_findings": [f"variant={variant}", f"seed={seed}"],
                    "system_results": [
                        {"system": "majority", "metrics": {"accuracy": 0.40, "macro_f1": 0.40}},
                        {"system": "naive_bayes", "metrics": {"accuracy": score, "macro_f1": score}},
                    ],
                    "tables": [],
                    "environment": {
                        "python_version": "3.11.0",
                        "platform": "test-platform",
                        "runtime_seconds": 0.012,
                        "seed": seed,
                        "sweep": sweep,
                    },
                },
            },
        }

    monkeypatch.setattr(autoresearch_codegen.ExperimentCodeGenerator, "generate", fake_generate)
    monkeypatch.setattr(runner.sandbox, "run", fake_run)

    strategy, code_path, artifact = runner.run(
        project_id="project-test",
        run_id="run-test",
        plan=plan,
        spec=spec,
        benchmark_payload=builtin_benchmark("text_classification").payload,
        round_index=3,
        goal="search_for_better_candidate",
        prior_attempts=[],
    )

    assert strategy == "naive_bayes_search"
    assert Path(code_path).is_file()
    assert len(observed_envs) == 4
    assert {env["SCHOLARFLOW_SEED"] for env in observed_envs} == {"7", "13"}
    assert {json.loads(env["SCHOLARFLOW_SWEEP_JSON"])["variant"] for env in observed_envs} == {"base", "better"}
    assert artifact.status == "done"
    assert artifact.environment["selected_sweep"] == "better"
    assert len(artifact.per_seed_results) == 2
    assert len(artifact.sweep_results) == 2
    assert artifact.objective_score is not None and artifact.objective_score > 0.75
    assert artifact.best_system == "naive_bayes"
    assert any(check.passed for check in artifact.acceptance_checks)
    assert any(table.title == "Sweep Summary" for table in artifact.tables)
    assert any(table.title == "Confidence Intervals" for table in artifact.tables)
    assert any(table.title == "Significance Tests" for table in artifact.tables)
    assert any(table.title == "Negative Results" for table in artifact.tables)
    assert any(item.system == "naive_bayes" for item in artifact.aggregate_system_results)
    naive_bayes_result = next(item for item in artifact.aggregate_system_results if item.system == "naive_bayes")
    assert "macro_f1" in naive_bayes_result.confidence_intervals
    assert naive_bayes_result.confidence_intervals["macro_f1"].lower < naive_bayes_result.mean_metrics["macro_f1"]
    assert naive_bayes_result.confidence_intervals["macro_f1"].upper > naive_bayes_result.mean_metrics["macro_f1"]
    assert artifact.sweep_results[1].objective_score_confidence_interval is not None
    assert any(item.scope == "system" for item in artifact.significance_tests)
    assert any(item.scope == "sweep" for item in artifact.significance_tests)
    assert artifact.negative_results
    aggregate_rule_check = next(
        check for check in artifact.acceptance_checks if check.rule_kind == "aggregate_metric_reporting"
    )
    assert aggregate_rule_check.passed
    assert "confidence_interval" in aggregate_rule_check.detail
    significance_rule_check = next(
        check for check in artifact.acceptance_checks if check.rule_kind == "significance_test_reporting"
    )
    assert significance_rule_check.passed


def test_experiment_spec_acceptance_criteria_upgrades_legacy_strings() -> None:
    base_spec = build_experiment_spec("text_classification", builtin_benchmark("text_classification"))
    spec = ExperimentSpec.model_validate(
        {
            **base_spec.model_dump(mode="json"),
            "acceptance_criteria": [
                "Objective system should outperform the majority baseline on mean primary metric.",
                "Selected sweep should execute successfully for every requested seed.",
                "Aggregate reporting should include mean and standard deviation for the primary metric.",
            ],
        }
    )

    assert [rule.kind for rule in spec.acceptance_criteria] == [
        "objective_metric_comparison",
        "seed_coverage",
        "aggregate_metric_reporting",
    ]
    assert spec.acceptance_criteria[0].baseline_system == "majority"
    assert spec.acceptance_criteria[2].required_statistics == ["mean", "std"]


def test_runner_records_partial_sweeps_negative_results_and_anomalies(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    runner = AutoExperimentRunner()
    plan = ResearchPlan(
        topic="Automatic topic classification for compact CS abstracts",
        title="Phase 2 Evidence Test",
        task_family="text_classification",
        problem_statement="Test partial sweeps and negative-result preservation.",
        motivation="Phase 2 should preserve richer evidence.",
        proposed_method="Compare stable and risky sweep configurations.",
        research_questions=["Are failed configs, negative results, and anomalies preserved?"],
        hypotheses=["The stable sweep should win while preserving risk evidence."],
        planned_contributions=["Failure analysis and significance reporting."],
        experiment_outline=["Run four seeds across a stable and a risky sweep."],
        scope_limits=["Unit-level runner validation only."],
    )
    spec = build_experiment_spec("text_classification", builtin_benchmark("text_classification")).model_copy(
        update={
            "seeds": [1, 2, 3, 4],
            "sweeps": [
                SweepConfig(label="stable", params={"variant": "stable"}),
                SweepConfig(label="risky", params={"variant": "risky"}),
            ],
        }
    )

    def fake_generate(self, **kwargs):
        del kwargs
        return "naive_bayes_search", 'print("__RESULT__" + "{}")'

    def fake_run(payload: dict[str, object]) -> dict[str, object]:
        env = payload.get("env")
        assert isinstance(env, dict)
        seed = int(env["SCHOLARFLOW_SEED"])
        sweep = json.loads(env["SCHOLARFLOW_SWEEP_JSON"])
        variant = str(sweep["variant"])
        if variant == "risky" and seed == 4:
            return {
                "logs": 'Traceback (most recent call last): RuntimeError: risky sweep blew up',
                "outputs": {
                    "returncode": 1,
                    "executor_mode": "local",
                    "docker_image": None,
                    "workdir": str(tmp_path),
                    "duration_ms": 13,
                    "host_platform": "test-platform",
                    "host_python": "3.11.0",
                },
            }

        stable_scores = {1: 0.9, 2: 0.9, 3: 0.9, 4: 0.2}
        risky_scores = {1: 0.61, 2: 0.62, 3: 0.63}
        score = stable_scores[seed] if variant == "stable" else risky_scores[seed]
        return {
            "logs": f"seed={seed} sweep={variant}",
            "outputs": {
                "returncode": 0,
                "executor_mode": "local",
                "docker_image": None,
                "workdir": str(tmp_path),
                "duration_ms": 12,
                "host_platform": "test-platform",
                "host_python": "3.11.0",
                "result": {
                    "summary": f"{variant} seed={seed}",
                    "primary_metric": "macro_f1",
                    "best_system": "naive_bayes",
                    "objective_system": "naive_bayes",
                    "objective_score": score,
                    "key_findings": [variant, str(seed)],
                    "system_results": [
                        {"system": "majority", "metrics": {"accuracy": 0.4, "macro_f1": 0.4}},
                        {"system": "naive_bayes", "metrics": {"accuracy": score, "macro_f1": score}},
                    ],
                    "tables": [],
                    "environment": {
                        "python_version": "3.11.0",
                        "platform": "test-platform",
                        "runtime_seconds": 0.012,
                        "seed": seed,
                        "sweep": sweep,
                    },
                },
            },
        }

    monkeypatch.setattr(autoresearch_codegen.ExperimentCodeGenerator, "generate", fake_generate)
    monkeypatch.setattr(runner.sandbox, "run", fake_run)

    _, _, artifact = runner.run(
        project_id="project-test",
        run_id="run-phase2",
        plan=plan,
        spec=spec,
        benchmark_payload=builtin_benchmark("text_classification").payload,
        round_index=2,
        goal="search_for_better_candidate",
        prior_attempts=[],
    )

    assert artifact.status == "done"
    assert any(item.status == "partial" for item in artifact.sweep_results)
    assert len(artifact.failed_trials) == 1
    assert artifact.failed_trials[0].category == "code_failure"
    assert artifact.failed_trials[0].sweep_label == "risky"
    assert any(item.scope == "sweep" for item in artifact.negative_results)
    assert artifact.anomalous_trials
    assert any(table.title == "Failed Configs" for table in artifact.tables)
    assert any(table.title == "Anomalous Trials" for table in artifact.tables)
    assert any(table.title == "Negative Results" for table in artifact.tables)
    assert any(table.title == "Significance Tests" for table in artifact.tables)


def test_runner_preserves_failure_analysis_when_no_sweep_completes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    runner = AutoExperimentRunner()
    plan = ResearchPlan(
        topic="Automatic topic classification for compact CS abstracts",
        title="Failure Preservation Test",
        task_family="text_classification",
        problem_statement="Test failed-sweep preservation.",
        motivation="Even fully failed runs should keep failure analysis.",
        proposed_method="Force every seed to fail.",
        research_questions=["Does the runner keep failed configs when no sweep completes?"],
        hypotheses=["A failed artifact should still contain sweep and failure tables."],
        planned_contributions=["Failure-preserving artifact behavior."],
        experiment_outline=["Run one failing sweep across two seeds."],
        scope_limits=["Unit-level runner validation only."],
    )
    spec = build_experiment_spec("text_classification", builtin_benchmark("text_classification")).model_copy(
        update={
            "seeds": [7, 13],
            "sweeps": [SweepConfig(label="broken", params={"variant": "broken"})],
        }
    )

    def fake_generate(self, **kwargs):
        del kwargs
        return "keyword_rule_search", 'print("__RESULT__" + "{}")'

    def fake_run(payload: dict[str, object]) -> dict[str, object]:
        del payload
        return {
            "logs": 'Traceback (most recent call last): RuntimeError: broken config',
            "outputs": {
                "returncode": 1,
                "executor_mode": "local",
                "docker_image": None,
                "workdir": str(tmp_path),
                "duration_ms": 9,
                "host_platform": "test-platform",
                "host_python": "3.11.0",
            },
        }

    monkeypatch.setattr(autoresearch_codegen.ExperimentCodeGenerator, "generate", fake_generate)
    monkeypatch.setattr(runner.sandbox, "run", fake_run)

    _, _, artifact = runner.run(
        project_id="project-test",
        run_id="run-all-fail",
        plan=plan,
        spec=spec,
        benchmark_payload=builtin_benchmark("text_classification").payload,
        round_index=1,
        goal="initial_run",
        prior_attempts=[],
    )

    assert artifact.status == "failed"
    assert len(artifact.failed_trials) == 2
    assert artifact.sweep_results[0].status == "failed"
    assert any(table.title == "Sweep Summary" for table in artifact.tables)
    assert any(table.title == "Failed Configs" for table in artifact.tables)
    assert artifact.environment["failed_trial_count"] == 2
    assert "failure analysis" in artifact.summary.lower()


def test_runner_rejects_artifact_with_runtime_environment_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    runner = AutoExperimentRunner()
    plan = ResearchPlan(
        topic="Automatic topic classification for compact CS abstracts",
        title="Runner Runtime Validation Test",
        task_family="text_classification",
        problem_statement="Test runtime mismatch rejection.",
        motivation="Runner must reject mismatched runtime metadata.",
        proposed_method="Validate artifact seed/sweep against injected runtime config.",
        research_questions=["Does runner reject mismatched artifact environment?"],
        hypotheses=["Artifacts with mismatched runtime metadata should fail."],
        planned_contributions=["Post-run runtime contract validation."],
        experiment_outline=["Run a single fake execution and inspect artifact validation."],
        scope_limits=["Unit-level runner validation only."],
    )
    spec = build_experiment_spec("text_classification", builtin_benchmark("text_classification")).model_copy(
        update={"seeds": [7], "sweeps": [SweepConfig(label="base", params={"variant": "base"})]}
    )

    def fake_generate(self, **kwargs):
        del kwargs
        return "keyword_rule_search", 'print("__RESULT__" + "{}")'

    def fake_run(payload: dict[str, object]) -> dict[str, object]:
        del payload
        return {
            "logs": "mismatched runtime metadata",
            "outputs": {
                "returncode": 0,
                "executor_mode": "local",
                "docker_image": None,
                "workdir": str(tmp_path),
                "duration_ms": 11,
                "host_platform": "test-platform",
                "host_python": "3.11.0",
                "result": {
                    "summary": "done",
                    "primary_metric": "macro_f1",
                    "best_system": "keyword_rule",
                    "objective_system": "keyword_rule",
                    "objective_score": 0.6,
                    "key_findings": [],
                    "system_results": [
                        {"system": "majority", "metrics": {"accuracy": 0.4, "macro_f1": 0.4}},
                        {"system": "keyword_rule", "metrics": {"accuracy": 0.6, "macro_f1": 0.6}},
                    ],
                    "tables": [],
                    "environment": {
                        "python_version": "3.11.0",
                        "platform": "test-platform",
                        "runtime_seconds": 0.011,
                        "seed": 999,
                        "sweep": {"variant": "wrong"},
                    },
                },
            },
        }

    monkeypatch.setattr(autoresearch_codegen.ExperimentCodeGenerator, "generate", fake_generate)
    monkeypatch.setattr(runner.sandbox, "run", fake_run)

    _, _, artifact = runner.run(
        project_id="project-test",
        run_id="run-runtime-mismatch",
        plan=plan,
        spec=spec,
        benchmark_payload=builtin_benchmark("text_classification").payload,
        round_index=1,
        goal="initial_run",
        prior_attempts=[],
    )

    assert artifact.status == "failed"
    assert "runtime contract" in artifact.summary.lower()
    assert "seed_mismatch" in artifact.environment["runtime_contract_violations"]
    assert "sweep_mismatch" in artifact.environment["runtime_contract_violations"]


def test_codegen_rejects_llm_code_without_runtime_controls(monkeypatch) -> None:
    generator = autoresearch_codegen.ExperimentCodeGenerator()
    observed_payload: dict[str, object] = {}

    def fake_chat(messages):
        observed_payload.update(json.loads(messages[1]["content"]))
        return {
            "choices": [
                {
                    "message": {
                        "content": """```python
import json

def run():
    print("__RESULT__" + json.dumps({"summary": "ok", "primary_metric": "macro_f1", "best_system": "x", "objective_system": "x", "objective_score": 1.0, "key_findings": [], "system_results": [], "tables": [], "environment": {}}))

if __name__ == "__main__":
    run()
```"""
                    }
                }
            ]
        }

    monkeypatch.setattr(autoresearch_codegen, "chat", fake_chat)
    plan = ResearchPlan(
        topic="Automatic topic classification for compact CS abstracts",
        title="Codegen Runtime Contract Test",
        task_family="text_classification",
        problem_statement="Test runtime contract enforcement.",
        motivation="LLM output must honor seed/sweep controls.",
        proposed_method="Generate a compliant script.",
        research_questions=["Does codegen reject incomplete LLM code?"],
        hypotheses=["Fallback code should be used when runtime controls are missing."],
        planned_contributions=["Enforce runtime contract during validation."],
        experiment_outline=["Generate code and validate runtime controls."],
        scope_limits=["Unit-level validation only."],
    )
    spec = build_experiment_spec("text_classification", builtin_benchmark("text_classification"))

    strategy, code = generator.generate(
        plan=plan,
        spec=spec,
        benchmark_payload=builtin_benchmark("text_classification").payload,
        round_index=1,
        goal="initial_run",
        prior_attempts=[],
    )

    assert strategy == "keyword_rule_search"
    assert observed_payload["runtime_contract"]["seed_env_var"] == "SCHOLARFLOW_SEED"
    assert observed_payload["runtime_contract"]["sweep_env_var"] == "SCHOLARFLOW_SWEEP_JSON"
    assert "SCHOLARFLOW_SEED" in code
    assert "SCHOLARFLOW_SWEEP_JSON" in code
    assert 'json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON")' in code


def test_codegen_rejects_llm_code_that_only_reads_runtime_controls(monkeypatch) -> None:
    generator = autoresearch_codegen.ExperimentCodeGenerator()

    def fake_chat(messages):
        del messages
        return {
            "choices": [
                {
                    "message": {
                        "content": """```python
import json
import os

SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{}")

def run():
    artifact = {
        "summary": "ok",
        "primary_metric": "macro_f1",
        "best_system": "x",
        "objective_system": "x",
        "objective_score": 1.0,
        "key_findings": [],
        "system_results": [],
        "tables": [],
        "environment": {},
    }
    print("__RESULT__" + json.dumps(artifact))

if __name__ == "__main__":
    run()
```"""
                    }
                }
            ]
        }

    monkeypatch.setattr(autoresearch_codegen, "chat", fake_chat)
    plan = ResearchPlan(
        topic="Automatic topic classification for compact CS abstracts",
        title="Codegen Runtime Usage Test",
        task_family="text_classification",
        problem_statement="Test runtime usage enforcement.",
        motivation="LLM output must use runtime controls, not just read them.",
        proposed_method="Generate a compliant script.",
        research_questions=["Does codegen reject read-only runtime controls?"],
        hypotheses=["Fallback code should replace incomplete read-only code."],
        planned_contributions=["Enforce runtime usage during validation."],
        experiment_outline=["Generate code and validate runtime usage."],
        scope_limits=["Unit-level validation only."],
    )
    spec = build_experiment_spec("text_classification", builtin_benchmark("text_classification"))

    _, code = generator.generate(
        plan=plan,
        spec=spec,
        benchmark_payload=builtin_benchmark("text_classification").payload,
        round_index=1,
        goal="initial_run",
        prior_attempts=[],
    )

    assert '"seed": SEED' in code
    assert '"sweep": SWEEP' in code


def test_repair_flow_requires_runtime_controls_in_candidate(monkeypatch, tmp_path: Path) -> None:
    engine = autoresearch_repair.ExperimentRepairEngine()
    observed_payload: dict[str, object] = {}
    previous_code = """import json
import os

SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{}")

def run():
    artifact = {
        "summary": "ok",
        "primary_metric": "macro_f1",
        "best_system": "demo",
        "objective_system": "demo",
        "objective_score": 1.0,
        "key_findings": [],
        "system_results": [],
        "tables": [],
        "environment": {"seed": SEED, "sweep": SWEEP},
    }
    print("__RESULT__" + json.dumps(artifact))

if __name__ == "__main__":
    run()
"""
    code_path = tmp_path / "repair_runtime_contract.py"
    code_path.write_text(previous_code, encoding="utf-8")

    def fake_chat(messages):
        observed_payload.update(json.loads(messages[1]["content"]))
        return {
            "choices": [
                {
                    "message": {
                        "content": """```python
import json

def run():
    artifact = {
        "summary": "patched",
        "primary_metric": "macro_f1",
        "best_system": "demo",
        "objective_system": "demo",
        "objective_score": 1.0,
        "key_findings": [],
        "system_results": [],
        "tables": [],
        "environment": {},
    }
    print("__RESULT__" + json.dumps(artifact))

if __name__ == "__main__":
    run()
```"""
                    }
                }
            ]
        }

    monkeypatch.setattr(autoresearch_repair, "chat", fake_chat)
    candidate = engine.repair(
        previous_attempt=ExperimentAttempt(
            round_index=1,
            strategy="forced_failure",
            goal="initial_run",
            status="failed",
            summary="failed",
            code_path=str(code_path),
            artifact=ResultArtifact(
                status="failed",
                summary="failed",
                primary_metric="macro_f1",
                logs='Traceback (most recent call last):\n  File "main.py", line 8, in run\nValueError: boom',
            ),
        ),
        plan=ResearchPlan(
            topic="Automatic topic classification for compact CS abstracts",
            title="Repair Runtime Contract Test",
            task_family="text_classification",
            problem_statement="Test repair runtime contract enforcement.",
            motivation="Repair must preserve seed/sweep controls.",
            proposed_method="Patch the failed script.",
            research_questions=["Does repair reject incomplete runtime control patches?"],
            hypotheses=["Invalid LLM patches should be discarded."],
            planned_contributions=["Carry runtime contract into repair."],
            experiment_outline=["Attempt LLM repair and validate the candidate."],
            scope_limits=["Unit-level repair validation only."],
        ),
        spec=build_experiment_spec("text_classification", builtin_benchmark("text_classification")),
        benchmark_payload=builtin_benchmark("text_classification").payload,
    )

    assert observed_payload["runtime_contract"]["seed_env_var"] == "SCHOLARFLOW_SEED"
    assert observed_payload["runtime_contract"]["sweep_env_var"] == "SCHOLARFLOW_SWEEP_JSON"
    assert candidate.strategy == "repair_heuristic_patch"
    assert "reads_seed_env" in candidate.sanity_checks
    assert "reads_sweep_env" in candidate.sanity_checks
    assert "parses_sweep_json" in candidate.sanity_checks
    assert "SCHOLARFLOW_SEED" in candidate.code
    assert "SCHOLARFLOW_SWEEP_JSON" in candidate.code


def test_repair_llm_patch_applies_structured_minimal_diff(monkeypatch, tmp_path: Path) -> None:
    engine = autoresearch_repair.ExperimentRepairEngine()
    previous_code = """import json
import os

SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{}")

def run():
    raise ValueError("boom")
    artifact = {
        "summary": "ok",
        "primary_metric": "macro_f1",
        "best_system": "demo",
        "objective_system": "demo",
        "objective_score": 1.0,
        "key_findings": [],
        "system_results": [],
        "tables": [],
        "environment": {"seed": SEED, "sweep": SWEEP},
    }
    print("__RESULT__" + json.dumps(artifact))

if __name__ == "__main__":
    run()
"""
    raise_line = previous_code.splitlines().index('    raise ValueError("boom")') + 1
    code_path = tmp_path / "repair_llm_patch.py"
    code_path.write_text(previous_code, encoding="utf-8")
    observed_payload: dict[str, object] = {}

    def fake_chat(messages):
        observed_payload.update(json.loads(messages[1]["content"]))
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "patch_ops": [
                                    {
                                        "op": "replace",
                                        "line_number": raise_line,
                                        "content": "    pass  # ScholarFlow llm patch",
                                    }
                                ]
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(autoresearch_repair, "chat", fake_chat)
    candidate = engine.repair(
        previous_attempt=ExperimentAttempt(
            round_index=1,
            strategy="forced_failure",
            goal="initial_run",
            status="failed",
            summary="failed",
            code_path=str(code_path),
            artifact=ResultArtifact(
                status="failed",
                summary="failed",
                primary_metric="macro_f1",
                logs=f'Traceback (most recent call last):\n  File "main.py", line {raise_line}, in run\nValueError: boom',
            ),
        ),
        plan=ResearchPlan(
            topic="Automatic topic classification for compact CS abstracts",
            title="Repair Structured Patch Test",
            task_family="text_classification",
            problem_statement="Test structured llm patch application.",
            motivation="LLM repair should return a minimal patch, not a rewrite.",
            proposed_method="Apply a one-line patch to restore execution.",
            research_questions=["Does repair accept a small structured patch?"],
            hypotheses=["A one-line replace patch should be accepted."],
            planned_contributions=["Structured llm patch support."],
            experiment_outline=["Parse patch ops and validate the candidate."],
            scope_limits=["Unit-level repair validation only."],
        ),
        spec=build_experiment_spec("text_classification", builtin_benchmark("text_classification")),
        benchmark_payload=builtin_benchmark("text_classification").payload,
    )

    assert observed_payload["patch_budget"] == 12
    assert "failed_code_with_line_numbers" in observed_payload
    assert candidate.strategy == "repair_llm_patch"
    assert candidate.patch_ops[0].line_number == raise_line
    assert candidate.patch_ops[0].op == "replace"
    assert "patch_within_budget" in candidate.sanity_checks
    assert "pass  # ScholarFlow llm patch" in candidate.code


def test_repair_llm_patch_rejects_large_structured_rewrite(tmp_path: Path) -> None:
    engine = autoresearch_repair.ExperimentRepairEngine()
    previous_code = """import json
import os

SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{}")

def run():
    artifact = {
        "summary": "ok",
        "primary_metric": "macro_f1",
        "best_system": "demo",
        "objective_system": "demo",
        "objective_score": 1.0,
        "key_findings": [],
        "system_results": [],
        "tables": [],
        "environment": {"seed": SEED, "sweep": SWEEP},
    }
    print("__RESULT__" + json.dumps(artifact))

if __name__ == "__main__":
    run()
"""
    patch_ops = [
        autoresearch_repair.PatchOp("insert", line_number=1, content=f"# rewrite {index}")
        for index in range(1, 14)
    ]
    candidate_code = engine._apply_patch_ops(previous_code, patch_ops)
    candidate = engine._build_candidate(
        previous_code,
        candidate_code,
        strategy="repair_llm_patch",
        patch_ops=patch_ops,
        patch_budget=12,
    )
    assert candidate is None


def test_local_patch_skips_runtime_contract_lines() -> None:
    engine = autoresearch_repair.ExperimentRepairEngine()
    code = """import json

SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{}")

def run():
    artifact = {"summary": "ok", "primary_metric": "macro_f1", "system_results": [], "tables": [], "environment": {"seed": SEED, "sweep": SWEEP}}
    print("__RESULT__" + json.dumps(artifact))

if __name__ == "__main__":
    run()
"""
    logs = 'Traceback (most recent call last):\n  File "main.py", line 3, in <module>\nNameError: name \'os\' is not defined'

    candidate = engine._local_patch_candidate(code, logs)
    assert candidate is None


def test_heuristic_repair_restores_os_import_for_runtime_contract(monkeypatch, tmp_path: Path) -> None:
    engine = autoresearch_repair.ExperimentRepairEngine()
    previous_code = """import json

SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{}")

def run():
    artifact = {
        "summary": "ok",
        "primary_metric": "macro_f1",
        "best_system": "demo",
        "objective_system": "demo",
        "objective_score": 1.0,
        "key_findings": [],
        "system_results": [],
        "tables": [],
        "environment": {"seed": SEED, "sweep": SWEEP},
    }
    print("__RESULT__" + json.dumps(artifact))

if __name__ == "__main__":
    run()
"""
    code_path = tmp_path / "repair_missing_os.py"
    code_path.write_text(previous_code, encoding="utf-8")

    def fail_chat(messages):
        del messages
        raise RuntimeError("skip llm")

    monkeypatch.setattr(autoresearch_repair, "chat", fail_chat)
    candidate = engine.repair(
        previous_attempt=ExperimentAttempt(
            round_index=1,
            strategy="forced_failure",
            goal="initial_run",
            status="failed",
            summary="failed",
            code_path=str(code_path),
            artifact=ResultArtifact(
                status="failed",
                summary="failed",
                primary_metric="macro_f1",
                logs='Traceback (most recent call last):\n  File "main.py", line 3, in <module>\nNameError: name \'os\' is not defined',
            ),
        ),
        plan=ResearchPlan(
            topic="Automatic topic classification for compact CS abstracts",
            title="Repair Missing Import Test",
            task_family="text_classification",
            problem_statement="Test heuristic import restoration.",
            motivation="Repair should preserve runtime contract support.",
            proposed_method="Restore missing imports instead of clobbering runtime controls.",
            research_questions=["Does heuristic repair import os when required by runtime controls?"],
            hypotheses=["Missing os import should be repaired with a real import."],
            planned_contributions=["Protect runtime contract during heuristic repair."],
            experiment_outline=["Reject local patch and apply heuristic repair."],
            scope_limits=["Unit-level repair validation only."],
        ),
        spec=build_experiment_spec("text_classification", builtin_benchmark("text_classification")),
        benchmark_payload=builtin_benchmark("text_classification").payload,
    )

    assert candidate.strategy == "repair_heuristic_patch"
    assert candidate.code.startswith("import os\n")
    assert "os = None" not in candidate.code
    assert "reads_seed_env" in candidate.sanity_checks
    assert "preserves_runtime_contract_lines" in candidate.sanity_checks


def test_repair_sanity_rejects_patch_without_result_marker(tmp_path: Path) -> None:
    engine = autoresearch_repair.ExperimentRepairEngine()
    previous_code = """import json

def run():
    artifact = {"summary": "ok", "primary_metric": "macro_f1", "system_results": [], "tables": [], "environment": {}}
    print("__RESULT__" + json.dumps(artifact))

if __name__ == "__main__":
    run()
"""
    broken_candidate = """def run():
    return None

if __name__ == "__main__":
    run()
"""
    path = tmp_path / "broken_repair.py"
    path.write_text(previous_code, encoding="utf-8")
    attempt = ExperimentAttempt(
        round_index=1,
        strategy="forced_failure",
        goal="initial_run",
        status="failed",
        summary="failed",
        code_path=str(path),
        artifact=ResultArtifact(
            status="failed",
            summary="failed",
            primary_metric="macro_f1",
            logs='Traceback (most recent call last):\n  File "main.py", line 4, in <module>\nRuntimeError: boom',
        ),
    )
    candidate = engine._build_candidate(
        previous_code,
        broken_candidate,
        strategy="repair_local_patch",
        local_patch=True,
    )
    assert candidate is None


def test_autoresearch_auto_searches_literature_when_project_has_no_papers(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    monkeypatch.setattr(
        literature_pipeline,
        "_search_topic_literature",
        lambda project_id, topic: SearchResult(
            query=topic,
            items=[
                PaperMeta(
                    id="paper-auto-1",
                    title="Lightweight Reranking Signals for Compact Corpora",
                    abstract="This paper studies lexical reranking and hard negative retrieval signals.",
                    year=2024,
                    source="semantic_scholar",
                )
            ],
        ),
    )
    try:
        project_id = _create_project(
            client,
            "Auto Literature Project",
            "Compact reranking for cs retrieval",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Compact reranking for cs retrieval",
                "auto_search_literature": True,
            },
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "done"
        assert len(run["literature"]) >= 1
        assert "Lightweight Reranking Signals" in run["literature"][0]["title"]
        papers = client.get(f"/api/projects/{project_id}/papers")
        assert papers.status_code == 200
        assert len(papers.json()) >= 1
    finally:
        client.close()


def test_autoresearch_supports_command_execution_backend(monkeypatch, tmp_path: Path) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Command Backend Project",
            "Automatic topic classification for compact CS abstracts",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Automatic topic classification for compact CS abstracts",
                "execution_backend": {
                    "kind": "command",
                    "command_prefix": [sys.executable],
                },
            },
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "done"
        assert run["execution_backend"]["kind"] == "command"
        assert run["artifact"]["environment"]["executor_mode"] == "command"
    finally:
        client.close()


def test_autoresearch_supports_ir_reranking_with_beir_like_adapter(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    beir_payload = {
        "name": "Toy BEIR Export",
        "queries": {
            "q1": "dense retrieval ranking",
            "q2": "gpu serving cache",
            "q3": "static taint analysis",
        },
        "corpus": {
            "d1": "Dense retrieval encoders improve passage ranking with hard negatives.",
            "d2": "KV cache quantization reduces memory overhead for model serving.",
            "d3": "Static taint analysis tracks untrusted data across dependence graphs.",
            "d4": "Query expansion improves lexical recall.",
        },
        "qrels": {
            "q1": {"d1": 1, "d4": 0},
            "q2": {"d2": 1, "d4": 0},
            "q3": {"d3": 1, "d1": 0},
        },
    }
    monkeypatch.setattr(
        autoresearch_ingestion,
        "_fetch_remote_text",
        lambda url: __import__("json").dumps(beir_payload),
    )
    try:
        project_id = _create_project(
            client,
            "IR Reranking Project",
            "Compact information retrieval reranking benchmark",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Compact information retrieval reranking benchmark",
                "task_family_hint": "ir_reranking",
                "benchmark": {
                    "kind": "beir_json",
                    "url": "https://example.com/beir.json",
                },
            },
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "done"
        assert run["task_family"] == "ir_reranking"
        assert run["spec"]["dataset"]["candidate_count"] is not None
        all_systems = {
            item["system"]
            for attempt in run["attempts"]
            for item in (attempt.get("artifact") or {}).get("system_results", [])
        }
        assert "idf_ranker" in all_systems
        assert "bigram_ranker" in all_systems
        assert "| System | MRR | Recall@1 |" in run["paper_markdown"]
    finally:
        client.close()


def test_autoresearch_can_discover_huggingface_split_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    train_csv = """text,label
dense retrieval learns passage ranking,retrieval
bm25 remains strong for lexical first stage,retrieval
gpu kernel fusion lowers serving latency,systems
cache quantization improves memory efficiency,systems
static taint analysis tracks data flow,analysis
abstract interpretation proves safety,analysis
"""
    test_csv = """text,label
query expansion boosts retrieval recall,retrieval
cluster schedulers stabilize training,systems
symbolic execution explores program paths,analysis
"""

    def fetch_text(url: str) -> str:
        if url == "https://datasets-server.huggingface.co/splits?dataset=demo%2Fcs-mini":
            return json.dumps({"splits": []})
        if url == "https://huggingface.co/api/datasets/demo/cs-mini":
            return json.dumps(
                {
                    "siblings": [
                        {"rfilename": "data/train.csv"},
                        {"rfilename": "data/test.csv"},
                    ]
                }
            )
        if url.endswith("/data/train.csv"):
            return train_csv
        if url.endswith("/data/test.csv"):
            return test_csv
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(autoresearch_ingestion, "_fetch_remote_text", fetch_text)
    try:
        project_id = _create_project(
            client,
            "HuggingFace Adapter Project",
            "Compact CS abstract classification from Hugging Face",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Compact CS abstract classification from Hugging Face",
                "benchmark": {
                    "kind": "huggingface_file",
                    "dataset_id": "demo/cs-mini",
                    "text_field": "text",
                    "label_field": "label",
                },
            },
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "done"
        assert run["benchmark"]["kind"] == "huggingface_file"
        assert run["spec"]["dataset"]["train_size"] == 6
        assert run["spec"]["dataset"]["test_size"] == 3
        assert run["artifact"]["environment"]["source_url"] == "https://huggingface.co/datasets/demo/cs-mini"
    finally:
        client.close()


def test_autoresearch_prefers_huggingface_datasets_server_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    train_rows = [
        {"text": "dense retrieval learns passage ranking", "label": "retrieval"},
        {"text": "bm25 remains strong for lexical first stage", "label": "retrieval"},
        {"text": "gpu kernel fusion lowers serving latency", "label": "systems"},
        {"text": "cache quantization improves memory efficiency", "label": "systems"},
        {"text": "static taint analysis tracks data flow", "label": "analysis"},
        {"text": "abstract interpretation proves safety", "label": "analysis"},
    ]
    test_rows = [
        {"text": "query expansion boosts retrieval recall", "label": "retrieval"},
        {"text": "cluster schedulers stabilize training", "label": "systems"},
        {"text": "symbolic execution explores program paths", "label": "analysis"},
    ]

    def fetch_text(url: str) -> str:
        if url == "https://datasets-server.huggingface.co/splits?dataset=demo%2Fcs-dsv":
            return json.dumps(
                {
                    "splits": [
                        {"config": "default", "split": "train", "num_rows": len(train_rows)},
                        {"config": "default", "split": "test", "num_rows": len(test_rows)},
                    ]
                }
            )
        if (
            url
            == "https://datasets-server.huggingface.co/rows?"
            "dataset=demo%2Fcs-dsv&config=default&split=train&offset=0&length=100"
        ):
            return json.dumps(
                {"rows": [{"row": row} for row in train_rows], "num_rows_total": len(train_rows)}
            )
        if (
            url
            == "https://datasets-server.huggingface.co/rows?"
            "dataset=demo%2Fcs-dsv&config=default&split=test&offset=0&length=100"
        ):
            return json.dumps(
                {"rows": [{"row": row} for row in test_rows], "num_rows_total": len(test_rows)}
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(autoresearch_ingestion, "_fetch_remote_text", fetch_text)
    try:
        project_id = _create_project(
            client,
            "HuggingFace Datasets Server Project",
            "Compact CS abstract classification via datasets-server",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Compact CS abstract classification via datasets-server",
                "benchmark": {
                    "kind": "huggingface_file",
                    "dataset_id": "demo/cs-dsv",
                    "text_field": "text",
                    "label_field": "label",
                },
            },
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "done"
        assert run["benchmark"]["kind"] == "huggingface_file"
        assert run["spec"]["dataset"]["train_size"] == 6
        assert run["spec"]["dataset"]["test_size"] == 3
        assert run["artifact"]["environment"]["source_url"] == "https://huggingface.co/datasets/demo/cs-dsv"
    finally:
        client.close()


def test_autoresearch_can_ingest_huggingface_parquet_split_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    train_rows = [
        {"text": "dense retrieval learns passage ranking", "label": "retrieval"},
        {"text": "bm25 remains strong for lexical first stage", "label": "retrieval"},
        {"text": "gpu kernel fusion lowers serving latency", "label": "systems"},
        {"text": "cache quantization improves memory efficiency", "label": "systems"},
        {"text": "static taint analysis tracks data flow", "label": "analysis"},
        {"text": "abstract interpretation proves safety", "label": "analysis"},
    ]
    test_rows = [
        {"text": "query expansion boosts retrieval recall", "label": "retrieval"},
        {"text": "cluster schedulers stabilize training", "label": "systems"},
        {"text": "symbolic execution explores program paths", "label": "analysis"},
    ]

    def fetch_text(url: str) -> str:
        if url == "https://datasets-server.huggingface.co/splits?dataset=demo%2Fcs-parquet":
            return json.dumps({"splits": []})
        if url == "https://huggingface.co/api/datasets/demo/cs-parquet":
            return json.dumps(
                {
                    "siblings": [
                        {"rfilename": "data/train-00000-of-00001.parquet"},
                        {"rfilename": "data/test-00000-of-00001.parquet"},
                    ]
                }
            )
        raise AssertionError(f"unexpected text url: {url}")

    def fetch_bytes(url: str) -> bytes:
        if url.endswith("/data/train-00000-of-00001.parquet"):
            return b"train"
        if url.endswith("/data/test-00000-of-00001.parquet"):
            return b"test"
        raise AssertionError(f"unexpected bytes url: {url}")

    def rows_from_parquet(payload: bytes) -> list[dict[str, str]]:
        if payload == b"train":
            return train_rows
        if payload == b"test":
            return test_rows
        raise AssertionError(f"unexpected parquet payload: {payload!r}")

    monkeypatch.setattr(autoresearch_ingestion, "_fetch_remote_text", fetch_text)
    monkeypatch.setattr(autoresearch_ingestion, "_fetch_remote_bytes", fetch_bytes)
    monkeypatch.setattr(autoresearch_ingestion, "_rows_from_parquet_bytes", rows_from_parquet)
    try:
        project_id = _create_project(
            client,
            "HuggingFace Parquet Project",
            "Compact CS abstract classification from parquet-only metadata",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Compact CS abstract classification from parquet-only metadata",
                "benchmark": {
                    "kind": "huggingface_file",
                    "dataset_id": "demo/cs-parquet",
                    "text_field": "text",
                    "label_field": "label",
                },
            },
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "done"
        assert run["benchmark"]["kind"] == "huggingface_file"
        assert run["spec"]["dataset"]["train_size"] == 6
        assert run["spec"]["dataset"]["test_size"] == 3
        assert run["artifact"]["environment"]["source_url"] == "https://huggingface.co/datasets/demo/cs-parquet"
    finally:
        client.close()


def test_autoresearch_surfaces_huggingface_fallback_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)

    def fetch_text(url: str) -> str:
        if url == "https://datasets-server.huggingface.co/splits?dataset=demo%2Fbroken":
            return json.dumps({"splits": []})
        if url == "https://huggingface.co/api/datasets/demo/broken":
            return json.dumps({"siblings": [{"rfilename": "README.md"}]})
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(autoresearch_ingestion, "_fetch_remote_text", fetch_text)
    try:
        project_id = _create_project(
            client,
            "HuggingFace Error Project",
            "Broken Hugging Face benchmark ingestion",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Broken Hugging Face benchmark ingestion",
                "benchmark": {
                    "kind": "huggingface_file",
                    "dataset_id": "demo/broken",
                    "text_field": "text",
                    "label_field": "label",
                },
            },
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "failed"
        assert "datasets-server failed" in run["error"]
        assert "file discovery failed" in run["error"]
        assert "No supported CSV/JSON/JSONL/Parquet files were found" in run["error"]
    finally:
        client.close()


def test_autoresearch_can_ingest_openml_arff_benchmark(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    arff_payload = """@relation training_run_stability
@attribute learning_rate numeric
@attribute batch_size numeric
@attribute dropout numeric
@attribute depth numeric
@attribute residual numeric
@attribute split {train,test}
@attribute label {stable,unstable}
@data
0.001,64,0.10,8,1,train,stable
0.002,128,0.20,12,1,train,stable
0.020,16,0.00,18,0,train,unstable
0.030,16,0.05,20,0,train,unstable
0.004,32,0.25,6,1,train,stable
0.018,16,0.35,14,0,train,unstable
0.0015,64,0.10,8,1,test,stable
0.022,24,0.35,19,0,test,unstable
0.0035,128,0.05,7,1,test,stable
"""

    def fetch_text(url: str) -> str:
        if url == "https://www.openml.org/api/v1/json/data/61":
            return json.dumps(
                {
                    "data_set_description": {
                        "name": "ToyOpenMLStability",
                        "file_id": "99991",
                        "default_target_attribute": "label",
                        "version": "1",
                    }
                }
            )
        if url == "https://www.openml.org/data/v1/download/99991":
            return arff_payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(autoresearch_ingestion, "_fetch_remote_text", fetch_text)
    try:
        project_id = _create_project(
            client,
            "OpenML Adapter Project",
            "Training run stability prediction from OpenML",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Training run stability prediction from OpenML",
                "task_family_hint": "tabular_classification",
                "benchmark": {
                    "kind": "openml_file",
                    "dataset_id": "61",
                    "split_field": "split",
                },
            },
        )
        assert response.status_code == 200
        run = client.get(f"/api/projects/{project_id}/auto-research/{response.json()['id']}").json()
        assert run["status"] == "done"
        assert run["benchmark"]["kind"] == "openml_file"
        assert run["spec"]["dataset"]["train_size"] == 6
        assert run["spec"]["dataset"]["test_size"] == 3
        assert run["spec"]["dataset"]["name"] == "ToyOpenMLStability"
    finally:
        client.close()
