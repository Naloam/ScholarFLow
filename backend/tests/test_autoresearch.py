from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path
from zipfile import ZipFile

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
import services.autoresearch.execution as autoresearch_execution
from services.autoresearch.execution import AutoResearchExecutionPlane
import services.autoresearch.ingestion as autoresearch_ingestion
import services.autoresearch.literature_pipeline as literature_pipeline
import services.autoresearch.orchestrator as autoresearch_orchestrator
import services.autoresearch.repair as autoresearch_repair
import services.autoresearch.repository as autoresearch_repository
from services.autoresearch.benchmarks import build_experiment_spec, builtin_benchmark
from services.autoresearch.runner import AutoExperimentRunner
import services.llm.client as llm_client
from config import db as db_module
from config import deps as deps_module
from config.settings import settings
from main import app
from models.base import Base
from schemas.autoresearch import AutoResearchRunConfig, ExperimentAttempt, ExperimentSpec, LiteratureInsight, ResearchPlan, ResultArtifact, SweepConfig
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
        assert Path(run["narrative_report_path"]).is_file()
        assert Path(run["claim_evidence_matrix_path"]).is_file()
        assert Path(run["paper_plan_path"]).is_file()
        assert Path(run["figure_plan_path"]).is_file()
        assert Path(run["paper_revision_state_path"]).is_file()
        assert Path(run["paper_sources_dir"]).is_dir()
        assert Path(run["paper_latex_path"]).is_file()
        assert Path(run["paper_bibliography_path"]).is_file()
        assert Path(run["paper_sources_manifest_path"]).is_file()
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
        assert run["narrative_report_markdown"].startswith("# Narrative Report:")
        assert "## Claim-Evidence Commitments" in run["narrative_report_markdown"]
        assert run["claim_evidence_matrix"]["claim_count"] >= 5
        assert run["claim_evidence_matrix"]["supported_claim_count"] >= 4
        assert any(item["claim_id"] == "claim_result_summary" for item in run["claim_evidence_matrix"]["entries"])
        assert run["paper_plan"]["title"] == run["plan"]["title"]
        assert len(run["paper_plan"]["sections"]) >= 6
        assert run["figure_plan"]["items"]
        assert any(item["kind"] == "table" for item in run["figure_plan"]["items"])
        assert run["paper_revision_state"]["status"] == "needs_review"
        assert "Persisted narrative report" in run["paper_revision_state"]["completed_actions"]
        assert "Persisted compile-ready paper sources" in run["paper_revision_state"]["completed_actions"]
        assert run["paper_revision_state"]["focus_sections"]
        assert run["paper_revision_state"]["next_actions"]
        assert run["paper_revision_state"]["checkpoints"][0]["revision_round"] == 0
        assert "paper_sources/main.tex" in run["paper_revision_state"]["checkpoints"][0]["relative_assets"]
        assert run["paper_sources_manifest"]["entrypoint"] == "main.tex"
        assert "pdflatex main.tex" in run["paper_sources_manifest"]["compile_commands"]
        assert run["paper_sources_manifest"]["compiler_hint"] in {"pdflatex", "pdflatex + bibtex"}
        assert any(item["relative_path"] == "references.bib" for item in run["paper_sources_manifest"]["files"])
        assert "\\documentclass{article}" in run["paper_latex_source"]
        assert (
            "\\bibliography{references}" in run["paper_latex_source"]
            or "% No bibliography pass is required for this run." in run["paper_latex_source"]
        )
        assert run["paper_bibliography_bib"]
        assert "## 2. Related Work and Research Plan" in paper
        assert "Claim-evidence commitments carried into manuscript drafting were" in paper
        assert "Portfolio planning generated 3 ranked candidates" in paper
        assert "## 4. Experimental Setup" in paper
        assert "The figure plan promoted the following artifact-backed visuals" in paper
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


def test_autoresearch_registry_exposes_run_lineage_and_candidate_manifests(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Registry Project",
            "Automatic topic classification for compact CS abstracts",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        registry_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/registry")
        assert registry_response.status_code == 200
        registry = registry_response.json()
        assert registry["project_id"] == project_id
        assert registry["run_id"] == run_id
        assert registry["selected_candidate_id"] == registry["lineage"]["selected_candidate_id"]
        assert registry["lineage"]["top_level_artifact_candidate_id"] == registry["selected_candidate_id"]
        assert registry["lineage"]["top_level_paper_candidate_id"] == registry["selected_candidate_id"]
        assert registry["lineage"]["edges"]
        assert registry["files"]["root"]["kind"] == "directory"
        assert registry["files"]["run_json"]["exists"] is True
        assert len(registry["files"]["run_json"]["sha256"]) == 64
        assert registry["files"]["portfolio_json"]["exists"] is True
        assert registry["files"]["artifact_json"]["exists"] is True
        assert len(registry["files"]["artifact_json"]["sha256"]) == 64
        assert registry["files"]["paper_markdown"]["exists"] is True
        assert len(registry["files"]["paper_markdown"]["sha256"]) == 64
        assert registry["files"]["narrative_report_markdown"]["exists"] is True
        assert registry["files"]["claim_evidence_matrix_json"]["exists"] is True
        assert registry["files"]["paper_plan_json"]["exists"] is True
        assert registry["files"]["figure_plan_json"]["exists"] is True
        assert registry["files"]["paper_revision_state_json"]["exists"] is True
        assert registry["files"]["paper_sources_dir"]["exists"] is True
        assert registry["files"]["paper_sources_dir"]["kind"] == "directory"
        assert registry["files"]["paper_latex_source"]["exists"] is True
        assert registry["files"]["paper_bibliography_bib"]["exists"] is True
        assert registry["files"]["paper_sources_manifest_json"]["exists"] is True
        assert any(edge["relation"] == "selected_candidate" for edge in registry["lineage"]["edges"])
        assert any(
            edge["relation"] == "has_asset" and edge["target_kind"] == "artifact"
            for edge in registry["lineage"]["edges"]
        )
        assert any(
            edge["relation"] == "has_asset" and edge["target_kind"] == "narrative_report"
            for edge in registry["lineage"]["edges"]
        )
        assert any(
            edge["relation"] == "has_asset" and edge["target_kind"] == "paper_latex"
            for edge in registry["lineage"]["edges"]
        )
        assert len(registry["candidates"]) == 3

        selected_candidate = next(item for item in registry["candidates"] if item["selected"])
        assert selected_candidate["candidate_id"] == registry["selected_candidate_id"]
        assert selected_candidate["manifest_source"] == "file"
        assert selected_candidate["decision_outcome"] == "promoted"
        assert selected_candidate["files"]["workspace"]["kind"] == "directory"
        assert selected_candidate["files"]["manifest_json"]["exists"] is True
        assert len(selected_candidate["files"]["manifest_json"]["sha256"]) == 64
        assert selected_candidate["files"]["artifact_json"]["exists"] is True
        assert len(selected_candidate["files"]["artifact_json"]["sha256"]) == 64
        assert selected_candidate["files"]["paper_markdown"]["exists"] is True
        assert len(selected_candidate["files"]["paper_markdown"]["sha256"]) == 64

        candidate_response = client.get(
            f"/api/projects/{project_id}/auto-research/{run_id}/registry/candidates/{selected_candidate['candidate_id']}"
        )
        assert candidate_response.status_code == 200
        candidate_registry = candidate_response.json()
        assert candidate_registry["candidate_id"] == selected_candidate["candidate_id"]
        assert candidate_registry["selected"] is True
        assert candidate_registry["candidate"]["id"] == selected_candidate["candidate_id"]
        assert candidate_registry["manifest"]["manifest_source"] == "file"
        assert candidate_registry["manifest"]["decision"]["outcome"] == "promoted"
        assert candidate_registry["manifest"]["files"]["manifest_json"]["exists"] is True
        assert candidate_registry["manifest"]["files"]["paper_markdown"]["exists"] is True
        assert candidate_registry["lineage"]["selected"] is True
        assert candidate_registry["lineage"]["decision_outcome"] == "promoted"
        assert any(
            edge["relation"] == "has_asset" and edge["target_kind"] == "manifest"
            for edge in candidate_registry["lineage"]["edges"]
        )
        assert any(
            edge["relation"] == "materialized_to_run_asset" and edge["target_kind"] == "paper"
            for edge in candidate_registry["lineage"]["edges"]
        )
        assert any(
            edge["relation"] == "materialized_to_run_asset" and edge["target_kind"] == "paper_plan"
            for edge in candidate_registry["lineage"]["edges"]
        )
        assert any(
            edge["relation"] == "materialized_to_run_asset" and edge["target_kind"] == "paper_sources"
            for edge in candidate_registry["lineage"]["edges"]
        )
    finally:
        client.close()


def test_autoresearch_registry_falls_back_when_candidate_manifest_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Registry Fallback Project",
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
        selected_candidate = next(
            item for item in run["candidates"] if item["id"] == run["portfolio"]["selected_candidate_id"]
        )
        manifest_path = Path(selected_candidate["manifest_path"])
        assert manifest_path.is_file()
        manifest_path.unlink()

        candidate_response = client.get(
            f"/api/projects/{project_id}/auto-research/{run_id}/registry/candidates/{selected_candidate['id']}"
        )
        assert candidate_response.status_code == 200
        candidate_registry = candidate_response.json()
        assert candidate_registry["manifest"]["manifest_source"] == "generated_fallback"
        assert candidate_registry["manifest"]["decision"]["outcome"] == "promoted"
        assert candidate_registry["manifest"]["files"]["manifest_json"]["exists"] is False
        assert candidate_registry["manifest"]["files"]["manifest_json"]["sha256"] is None
        assert any(
            edge["relation"] == "has_asset" and edge["target_kind"] == "manifest" and edge["exists"] is False
            for edge in candidate_registry["lineage"]["edges"]
        )

        registry_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/registry")
        assert registry_response.status_code == 200
        registry = registry_response.json()
        selected_entry = next(item for item in registry["candidates"] if item["candidate_id"] == selected_candidate["id"])
        assert selected_entry["manifest_source"] == "generated_fallback"
        assert selected_entry["files"]["manifest_json"]["exists"] is False

        bundle_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/registry/bundles")
        assert bundle_response.status_code == 200
        bundle_index = bundle_response.json()
        selected_bundle = next(item for item in bundle_index["bundles"] if item["id"] == "selected_candidate_repro")
        missing_manifest_asset = next(
            item
            for item in selected_bundle["assets"]
            if item["role"] == "manifest_json" and item["candidate_id"] == selected_candidate["id"]
        )
        assert selected_bundle["missing_asset_count"] >= 1
        assert missing_manifest_asset["ref"]["exists"] is False
        assert missing_manifest_asset["ref"]["sha256"] is None
    finally:
        client.close()


def test_autoresearch_bundle_index_exposes_selected_and_portfolio_assets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Bundle Index Project",
            "Automatic topic classification for compact CS abstracts",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        bundle_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/registry/bundles")
        assert bundle_response.status_code == 200
        bundle_index = bundle_response.json()
        assert bundle_index["project_id"] == project_id
        assert bundle_index["run_id"] == run_id
        assert [item["id"] for item in bundle_index["bundles"]] == [
            "selected_candidate_repro",
            "portfolio_full",
        ]

        selected_bundle = bundle_index["bundles"][0]
        portfolio_bundle = bundle_index["bundles"][1]

        assert selected_bundle["selected_candidate_id"]
        assert selected_bundle["candidate_ids"] == [selected_bundle["selected_candidate_id"]]
        assert selected_bundle["asset_count"] >= 8
        assert selected_bundle["missing_asset_count"] == 0
        assert any(item["role"] == "run_json" for item in selected_bundle["assets"])
        assert any(item["role"] == "run_narrative_report_markdown" for item in selected_bundle["assets"])
        assert any(item["role"] == "run_claim_evidence_matrix_json" for item in selected_bundle["assets"])
        assert any(item["role"] == "run_paper_plan_json" for item in selected_bundle["assets"])
        assert any(item["role"] == "run_figure_plan_json" for item in selected_bundle["assets"])
        assert any(item["role"] == "run_paper_revision_state_json" for item in selected_bundle["assets"])
        assert any(item["role"] == "run_paper_sources_dir" for item in selected_bundle["assets"])
        assert any(item["role"] == "run_paper_latex_source" for item in selected_bundle["assets"])
        assert any(item["role"] == "run_paper_bibliography_bib" for item in selected_bundle["assets"])
        assert any(item["role"] == "run_paper_sources_manifest_json" for item in selected_bundle["assets"])
        assert any(item["role"] == "manifest_json" and item["selected"] for item in selected_bundle["assets"])
        assert any(item["role"] == "artifact_json" and item["selected"] for item in selected_bundle["assets"])
        assert any(item["role"] == "paper_markdown" and item["selected"] for item in selected_bundle["assets"])

        selected_manifest_asset = next(
            item for item in selected_bundle["assets"] if item["role"] == "manifest_json" and item["selected"]
        )
        assert selected_manifest_asset["ref"]["exists"] is True
        assert len(selected_manifest_asset["ref"]["sha256"]) == 64

        assert len(portfolio_bundle["candidate_ids"]) == 3
        assert portfolio_bundle["asset_count"] > selected_bundle["asset_count"]
        assert portfolio_bundle["missing_asset_count"] >= 1
        assert sum(1 for item in portfolio_bundle["assets"] if item["role"] == "manifest_json") == 3
        assert sum(1 for item in portfolio_bundle["assets"] if item["role"] == "candidate_json") == 3
        assert any(item["selected"] for item in portfolio_bundle["assets"])
        assert any(not item["selected"] and item["candidate_id"] for item in portfolio_bundle["assets"])
        assert any(
            item["role"] == "paper_markdown" and not item["selected"] and item["ref"]["exists"] is False
            for item in portfolio_bundle["assets"]
        )
    finally:
        client.close()


def test_autoresearch_registry_views_group_selected_and_eliminated_candidates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Registry Views Project",
            "Automatic topic classification for compact CS abstracts",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        views_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/registry/views")
        assert views_response.status_code == 200
        payload = views_response.json()
        assert payload["project_id"] == project_id
        assert payload["run_id"] == run_id
        assert payload["counts"]["total_candidates"] == 3
        assert payload["counts"]["selected"] == 1
        assert payload["counts"]["eliminated"] == 2
        assert payload["counts"]["failed"] == 0
        assert payload["counts"]["active"] == 0

        views = {item["id"]: item for item in payload["views"]}
        assert set(views) == {"selected", "eliminated", "failed", "active", "all"}
        assert views["selected"]["count"] == 1
        assert views["selected"]["entries"][0]["selected"] is True
        assert views["selected"]["candidate_ids"] == [payload["selected_candidate_id"]]
        assert views["eliminated"]["count"] == 2
        assert all(item["decision_outcome"] == "eliminated" for item in views["eliminated"]["entries"])
        assert views["failed"]["count"] == 0
        assert views["active"]["count"] == 0
        assert views["all"]["count"] == 3
    finally:
        client.close()


def test_autoresearch_registry_views_include_failed_candidates(
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
            status = "done"
        elif "robustness checks" in plan.proposed_method:
            candidate_label = "stability_probe"
            score = None
            status = "failed"
        else:
            candidate_label = "primary_method"
            score = 0.79
            status = "done"
        strategy = spec.search_strategies[min(round_index - 1, len(spec.search_strategies) - 1)]
        code_path = tmp_path / f"{candidate_label}_{round_index}.py"
        code_path.write_text(f"# {candidate_label} round {round_index}\n", encoding="utf-8")
        if status == "failed":
            artifact = ResultArtifact(
                status="failed",
                summary=f"{candidate_label} round {round_index} failed",
                key_findings=[candidate_label],
                primary_metric="macro_f1",
                logs="synthetic failure",
                environment={"executor_mode": "synthetic"},
                outputs={"returncode": 1},
            )
        else:
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
                environment={"executor_mode": "synthetic"},
            )
        return strategy, str(code_path), artifact

    monkeypatch.setattr(AutoExperimentRunner, "run", fake_run)
    try:
        project_id = _create_project(
            client,
            "Registry Failed View Project",
            "Automatic topic classification for compact CS abstracts",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert response.status_code == 200
        run_id = response.json()["id"]

        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "done"
        assert any(item["status"] == "failed" for item in run["candidates"])

        views_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/registry/views")
        assert views_response.status_code == 200
        payload = views_response.json()
        assert payload["counts"]["selected"] == 1
        assert payload["counts"]["eliminated"] == 1
        assert payload["counts"]["failed"] == 1
        assert payload["counts"]["active"] == 0

        views = {item["id"]: item for item in payload["views"]}
        assert views["failed"]["count"] == 1
        assert views["failed"]["entries"][0]["status"] == "failed"
        assert views["failed"]["entries"][0]["decision_outcome"] == "failed"
        assert views["eliminated"]["count"] == 1
        assert views["selected"]["count"] == 1
        assert views["all"]["count"] == 3
    finally:
        client.close()


def test_autoresearch_review_report_is_grounded_in_persisted_run_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 5 Review Project",
            "Automatic topic classification for compact CS abstracts",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        review_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review")
        assert review_response.status_code == 200
        review = review_response.json()
        assert review["project_id"] == project_id
        assert review["run_id"] == run_id
        assert review["backed_by_bundle_id"] == "selected_candidate_repro"
        assert review["overall_status"] == "needs_revision"
        assert review["unsupported_claim_risk"] == "medium"
        assert review["evidence"]["candidate_count"] == 3
        assert review["evidence"]["executed_candidate_count"] == 3
        assert review["citation_coverage"]["cited_literature_count"] == 0
        assert review["citation_coverage"]["invalid_citation_indices"] == []
        assert review["evidence"]["seed_count"] == len(
            client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()["spec"]["seeds"]
        )
        assert review["scores"]["reproducibility"] >= 3
        assert any(item["category"] == "citation" for item in review["findings"])
        assert any(item["category"] == "context" for item in review["findings"])
        assert any(item["title"] == "Add citation support to contextual and related-work claims" for item in review["revision_plan"])
        assert Path(review["persisted_path"]).is_file()

        loop_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review-loop")
        assert loop_response.status_code == 200
        loop = loop_response.json()
        assert loop["project_id"] == project_id
        assert loop["run_id"] == run_id
        assert loop["current_round"] == 1
        assert loop["overall_status"] == review["overall_status"]
        assert loop["unsupported_claim_risk"] == review["unsupported_claim_risk"]
        assert loop["open_issue_count"] >= 1
        assert loop["resolved_issue_count"] == 0
        assert len(loop["rounds"]) == 1
        assert loop["rounds"][0]["round_index"] == 1
        assert loop["rounds"][0]["finding_ids"]
        assert loop["rounds"][0]["revision_action_ids"]
        assert loop["issues"]
        assert loop["actions"]
        assert any(item["status"] == "open" for item in loop["issues"])
        assert loop["pending_action_count"] == len(loop["pending_revision_actions"])
        assert loop["completed_action_count"] == 0
        assert all(item["action_id"] for item in loop["actions"])
        assert all(item["issue_ids"] for item in loop["actions"])
        assert any(item["status"] == "pending" for item in loop["actions"])
        assert Path(loop["persisted_path"]).is_file()
    finally:
        client.close()


def test_autoresearch_review_loop_tracks_rounds_and_resolved_issues(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 5 Review Loop Project",
            "Automatic topic classification for compact CS abstracts",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        review = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review").json()
        loop = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review-loop").json()
        assert loop["current_round"] == 1
        assert len(loop["rounds"]) == 1
        first_fingerprint = loop["latest_review_fingerprint"]
        assert first_fingerprint
        assert loop["pending_revision_actions"] == [item["title"] for item in review["revision_plan"]]
        assert loop["pending_action_count"] == len(loop["actions"])
        assert loop["completed_action_count"] == 0
        assert all(item["status"] == "pending" for item in loop["actions"])

        repeat_loop = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review-loop").json()
        assert repeat_loop["current_round"] == 1
        assert len(repeat_loop["rounds"]) == 1
        assert repeat_loop["latest_review_fingerprint"] == first_fingerprint
        assert repeat_loop["pending_action_count"] == loop["pending_action_count"]
        assert repeat_loop["completed_action_count"] == 0

        run = autoresearch_repository.load_run(project_id, run_id)
        assert run is not None
        assert run.plan is not None
        updated_run = run.model_copy(
            update={
                "literature": [
                    LiteratureInsight(
                        paper_id="paper-loop-1",
                        title="Compact Classification Signals for CS Abstracts",
                        year=2024,
                        source="semantic_scholar",
                        insight="Provides grounded related-work context for compact abstract classification systems.",
                        method_hint="Use compact lexical and probabilistic signals for topic classification.",
                        gap_hint="Preserve explicit artifact-grounded reporting while adding citations.",
                    )
                ],
                "paper_markdown": f"""# {run.plan.title}

## Abstract
This grounded summary ties the selected artifact to preserved related work [1].

## 1. Introduction
Prior work informs the task framing and benchmark choice for this run [1].

## 2. Related Work and Research Plan
Retrieved work motivates the selected candidate and keeps the novelty framing explicit [1].

## 3. Method
The method remains grounded in the persisted run plan and artifact.

## 4. Experimental Setup
The experimental setup remains unchanged and artifact-backed.

## 5. Results
The results are still grounded in the persisted artifact table and acceptance checks.

## 6. Discussion
The discussion connects the run outcome back to prior work and preserved context [1].

## 7. Limitations
The limitations remain explicit and literature-aware [1].

## 8. Conclusion
The conclusion revisits the strongest supported claim in light of prior work [1].

## 9. References
[1] Compact Classification Signals for CS Abstracts. semantic scholar, 2024.
""",
            }
        )
        autoresearch_repository.save_run(updated_run)

        updated_review = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review").json()
        updated_loop = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review-loop").json()
        assert updated_loop["current_round"] == 2
        assert len(updated_loop["rounds"]) == 2
        assert updated_loop["latest_review_fingerprint"] != first_fingerprint
        assert updated_loop["overall_status"] == updated_review["overall_status"]
        assert updated_loop["resolved_issue_count"] >= 1
        assert updated_loop["completed_action_count"] >= 1
        assert any(item["status"] == "resolved" for item in updated_loop["issues"])
        assert any(item["status"] == "completed" for item in updated_loop["actions"])
        assert all(item["issue_ids"] for item in updated_loop["actions"] if item["status"] == "pending")
        assert any(item["completed_round"] == 2 for item in updated_loop["actions"] if item["status"] == "completed")
        assert all(item["issue_id"] for item in updated_loop["issues"])
    finally:
        client.close()


def test_autoresearch_publish_package_is_derived_from_selected_bundle(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 5 Publish Project",
            "Automatic topic classification for compact CS abstracts",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        package_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/publish")
        assert package_response.status_code == 200
        package = package_response.json()
        assert package["project_id"] == project_id
        assert package["run_id"] == run_id
        assert package["package_id"] == "publish_ready_bundle"
        assert package["source_bundle_id"] == "selected_candidate_repro"
        assert package["status"] == "revision_required"
        assert package["publish_ready"] is False
        assert package["review_bundle_ready"] is True
        assert package["final_publish_ready"] is False
        assert package["completeness_status"] == "complete"
        assert package["missing_required_asset_count"] == 0
        assert package["missing_final_asset_count"] == 0
        assert package["blocker_count"] == 0
        assert package["final_blocker_count"] == 0
        assert package["revision_count"] >= 1
        required_roles = {item["role"] for item in package["required_assets"]}
        final_required_roles = {item["role"] for item in package["final_required_assets"]}
        optional_roles = {item["role"] for item in package["optional_assets"]}
        assert "run_json" in required_roles
        assert "manifest_json" in required_roles
        assert "candidate_json" in required_roles
        assert "workspace" in required_roles
        assert "run_generated_code" in final_required_roles
        assert "attempts_json" in final_required_roles
        assert "artifact_json" in final_required_roles
        assert "run_artifact_json" in optional_roles
        assert "generated_code" in optional_roles
        assert Path(package["review_path"]).is_file()
        assert Path(package["manifest_path"]).is_file()
    finally:
        client.close()


def test_autoresearch_publish_package_marks_final_publish_ready_when_review_and_assets_align(
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
                    id="paper-publish-1",
                    title="Lightweight Reranking Signals for Compact Corpora",
                    abstract="This paper studies lexical reranking and hard negative retrieval signals.",
                    year=2024,
                    source="semantic_scholar",
                ),
                PaperMeta(
                    id="paper-publish-2",
                    title="Benchmarking Compact Retrieval Pipelines",
                    abstract="This paper evaluates compact retrieval pipelines under reproducible constraints.",
                    year=2023,
                    source="semantic_scholar",
                ),
            ],
        ),
    )
    try:
        project_id = _create_project(
            client,
            "Phase 5 Final Publish Project",
            "Compact reranking for cs retrieval",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Compact reranking for cs retrieval",
                "auto_search_literature": True,
            },
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        package = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/publish").json()
        assert package["status"] == "publish_ready"
        assert package["publish_ready"] is True
        assert package["review_bundle_ready"] is True
        assert package["final_publish_ready"] is True
        assert package["completeness_status"] == "complete"
        assert package["missing_required_asset_count"] == 0
        assert package["missing_final_asset_count"] == 0
        assert package["final_blockers"] == []
    finally:
        client.close()


def test_autoresearch_publish_package_flags_missing_final_semantic_assets(
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
                    id="paper-publish-1",
                    title="Lightweight Reranking Signals for Compact Corpora",
                    abstract="This paper studies lexical reranking and hard negative retrieval signals.",
                    year=2024,
                    source="semantic_scholar",
                ),
                PaperMeta(
                    id="paper-publish-2",
                    title="Benchmarking Compact Retrieval Pipelines",
                    abstract="This paper evaluates compact retrieval pipelines under reproducible constraints.",
                    year=2023,
                    source="semantic_scholar",
                ),
            ],
        ),
    )
    try:
        project_id = _create_project(
            client,
            "Phase 5 Missing Final Asset Project",
            "Compact reranking for cs retrieval",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Compact reranking for cs retrieval",
                "auto_search_literature": True,
            },
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]
        run = autoresearch_repository.load_run(project_id, run_id)
        assert run is not None
        assert run.portfolio is not None
        selected_candidate = next(
            item for item in run.candidates if item.id == run.portfolio.selected_candidate_id
        )
        assert selected_candidate.generated_code_path is not None
        generated_code_path = Path(selected_candidate.generated_code_path)
        generated_code_path.unlink()

        package = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/publish").json()
        assert package["status"] == "revision_required"
        assert package["publish_ready"] is False
        assert package["review_bundle_ready"] is True
        assert package["final_publish_ready"] is False
        assert package["completeness_status"] == "incomplete"
        assert package["missing_required_asset_count"] == 0
        assert package["missing_final_asset_count"] >= 1
        assert package["final_blocker_count"] >= 1
        assert any("generated_code" in item for item in package["final_blockers"])
    finally:
        client.close()


def test_autoresearch_publish_export_materializes_archive(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 5 Export Project",
            "Automatic topic classification for compact CS abstracts",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        export_response = client.post(f"/api/projects/{project_id}/auto-research/{run_id}/publish/export")
        assert export_response.status_code == 200
        export_body = export_response.json()
        assert export_body["project_id"] == project_id
        assert export_body["run_id"] == run_id
        assert export_body["bundle_kind"] == "review_bundle"
        assert export_body["review_bundle_ready"] is True
        assert export_body["final_publish_ready"] is False
        assert export_body["download_ready"] is True
        archive_path = Path(export_body["archive_path"])
        assert archive_path.is_file()
        assert export_body["file_name"] == archive_path.name
        assert Path(export_body["archive_manifest_path"]).is_file()
        assert export_body["included_asset_count"] >= 1
        assert export_body["omitted_asset_count"] >= 0

        with ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            archive_manifest = json.loads(archive.read("archive_manifest.json").decode("utf-8"))
        assert "review.json" in names
        assert "review_loop.json" in names
        assert "publish_package.json" in names
        assert "archive_manifest.json" in names
        assert "run.json" in names
        assert any(name.endswith("/manifest.json") for name in names)
        assert any(name.endswith("/artifact.json") for name in names)
        assert archive_manifest["bundle_kind"] == "review_bundle"
        assert archive_manifest["review_bundle_ready"] is True
        assert archive_manifest["final_publish_ready"] is False
        assert archive_manifest["included_asset_count"] == export_body["included_asset_count"]
        assert archive_manifest["omitted_asset_count"] == export_body["omitted_asset_count"]
        assert "archive_manifest.json" in archive_manifest["generated_files"]
        assert "review_loop.json" in archive_manifest["generated_files"]

        download_response = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/publish/download")
        assert download_response.status_code == 200
        assert download_response.headers["content-disposition"].endswith('publish_bundle.zip"')
    finally:
        client.close()


def test_autoresearch_publish_export_marks_final_bundle_kind_for_complete_package(
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
                    id="paper-export-1",
                    title="Lightweight Reranking Signals for Compact Corpora",
                    abstract="This paper studies lexical reranking and hard negative retrieval signals.",
                    year=2024,
                    source="semantic_scholar",
                ),
                PaperMeta(
                    id="paper-export-2",
                    title="Benchmarking Compact Retrieval Pipelines",
                    abstract="This paper evaluates compact retrieval pipelines under reproducible constraints.",
                    year=2023,
                    source="semantic_scholar",
                ),
            ],
        ),
    )
    try:
        project_id = _create_project(
            client,
            "Phase 5 Final Export Project",
            "Compact reranking for cs retrieval",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Compact reranking for cs retrieval",
                "auto_search_literature": True,
            },
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        export_body = client.post(
            f"/api/projects/{project_id}/auto-research/{run_id}/publish/export"
        ).json()
        assert export_body["bundle_kind"] == "final_publish_bundle"
        assert export_body["review_bundle_ready"] is True
        assert export_body["final_publish_ready"] is True
        with ZipFile(Path(export_body["archive_path"])) as archive:
            archive_manifest = json.loads(archive.read("archive_manifest.json").decode("utf-8"))
        assert archive_manifest["bundle_kind"] == "final_publish_bundle"
        assert archive_manifest["final_publish_ready"] is True
        assert archive_manifest["omitted_final_asset_ids"] == []
    finally:
        client.close()


def test_autoresearch_operator_console_aggregates_current_run_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 6 Console Project",
            "Automatic topic classification for compact CS abstracts",
        )
        run_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["id"]

        export_response = client.post(f"/api/projects/{project_id}/auto-research/{run_id}/publish/export")
        assert export_response.status_code == 200

        console_response = client.get(f"/api/projects/{project_id}/auto-research/console")
        assert console_response.status_code == 200
        console = console_response.json()
        assert console["project_id"] == project_id
        assert console["run_count"] == 1
        assert console["latest_run_id"] == run_id
        assert console["selected_run_id"] == run_id
        assert console["actions"]["start_run"] is True
        assert len(console["runs"]) == 1
        assert console["runs"][0]["run_id"] == run_id
        assert console["runs"][0]["status"] == "done"
        assert console["runs"][0]["selected_count"] == 1
        assert console["runs"][0]["failed_count"] == 0
        assert console["runs"][0]["publish_status"] == "revision_required"
        assert console["runs"][0]["review_risk"] == "medium"
        assert console["runs"][0]["novelty_status"] == "missing_context"
        assert console["runs"][0]["budget_status"] == "default"
        assert console["runs"][0]["queue_priority"] == "normal"
        assert console["runs"][0]["max_rounds"] == 3
        assert console["runs"][0]["candidate_execution_limit"] is None
        assert console["filtered_run_count"] == 1
        assert console["filters"]["search"] is None

        current = console["current_run"]
        assert current["run"]["id"] == run_id
        assert current["execution"]["active_job_id"] is None
        assert current["registry"]["run_id"] == run_id
        assert current["registry"]["lineage"]["edges"]
        assert current["registry_views"]["counts"]["selected"] == 1
        assert current["review"]["overall_status"] == "needs_revision"
        assert current["publish"]["status"] == "revision_required"
        assert current["actions"]["resume"] is False
        assert current["actions"]["retry"] is True
        assert current["actions"]["cancel"] is False
        assert current["actions"]["export_publish"] is True
        assert current["actions"]["download_publish"] is True
        assert current["actions"]["update_controls"] is True
    finally:
        client.close()


def test_autoresearch_operator_console_exposes_cancel_for_queued_run(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 6 Queued Console Project",
            "Queued auto research control path",
        )
        run = autoresearch_repository.create_run(project_id, "Queued auto research control path")
        AutoResearchExecutionPlane().enqueue(project_id=project_id, run_id=run.id, action="run")

        console_response = client.get(
            f"/api/projects/{project_id}/auto-research/console",
            params={"run_id": run.id},
        )
        assert console_response.status_code == 200
        console = console_response.json()
        assert console["run_count"] == 1
        assert console["filtered_run_count"] == 1
        assert console["selected_run_id"] == run.id
        assert console["runs"][0]["latest_job_status"] == "queued"
        assert console["runs"][0]["active_job_id"] is None
        assert console["runs"][0]["review_risk"] is None
        assert console["runs"][0]["novelty_status"] is None

        current = console["current_run"]
        assert current["run"]["status"] == "queued"
        assert current["review"] is None
        assert current["publish"] is None
        assert current["actions"]["resume"] is True
        assert current["actions"]["retry"] is False
        assert current["actions"]["cancel"] is True
        assert current["actions"]["export_publish"] is False
        assert current["actions"]["download_publish"] is False
    finally:
        client.close()


def test_autoresearch_respects_candidate_execution_limit_and_exposes_budget_status(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 6 Budget Console Project",
            "Budget-aware portfolio truncation for compact CS abstracts",
        )

        limited_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Budget-aware portfolio truncation for compact CS abstracts",
                "candidate_execution_limit": 1,
            },
        )
        assert limited_response.status_code == 200
        limited_run_id = limited_response.json()["id"]

        default_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert default_response.status_code == 200
        default_run_id = default_response.json()["id"]

        limited_run = client.get(f"/api/projects/{project_id}/auto-research/{limited_run_id}").json()
        assert limited_run["request"]["candidate_execution_limit"] == 1
        assert len(limited_run["portfolio"]["executed_candidate_ids"]) == 1
        executed_candidates = [item for item in limited_run["candidates"] if item["attempts"]]
        deferred_candidates = [item for item in limited_run["candidates"] if item["status"] == "deferred"]
        assert len(executed_candidates) == 1
        assert len(deferred_candidates) == 2
        assert all(item["attempts"] == [] for item in deferred_candidates)

        constrained_console = client.get(
            f"/api/projects/{project_id}/auto-research/console",
            params={"budget_status": "constrained"},
        )
        assert constrained_console.status_code == 200
        constrained_payload = constrained_console.json()
        assert constrained_payload["run_count"] == 2
        assert constrained_payload["filtered_run_count"] == 1
        assert constrained_payload["selected_run_id"] == limited_run_id
        assert constrained_payload["filters"]["budget_status"] == "constrained"
        assert constrained_payload["runs"][0]["run_id"] == limited_run_id
        assert constrained_payload["runs"][0]["budget_status"] == "constrained"
        assert constrained_payload["runs"][0]["candidate_execution_limit"] == 1
        assert constrained_payload["runs"][0]["executed_candidate_count"] == 1

        default_console = client.get(
            f"/api/projects/{project_id}/auto-research/console",
            params={"budget_status": "default"},
        )
        assert default_console.status_code == 200
        default_payload = default_console.json()
        assert default_payload["filtered_run_count"] == 1
        assert default_payload["selected_run_id"] == default_run_id
        assert default_payload["runs"][0]["run_id"] == default_run_id
        assert default_payload["runs"][0]["budget_status"] == "default"
        assert default_payload["runs"][0]["candidate_execution_limit"] is None
    finally:
        client.close()


def test_autoresearch_execution_plane_prefers_high_priority_jobs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 6 Priority Queue Project",
            "Priority queue ordering for auto research",
        )
        low_run = autoresearch_repository.create_run(
            project_id,
            "Low priority auto research",
            request=AutoResearchRunConfig(queue_priority="low"),
        )
        high_run = autoresearch_repository.create_run(
            project_id,
            "High priority auto research",
            request=AutoResearchRunConfig(queue_priority="high"),
        )
        plane = AutoResearchExecutionPlane()
        plane.enqueue(project_id=project_id, run_id=low_run.id, action="run")
        plane.enqueue(project_id=project_id, run_id=high_run.id, action="run")

        leased = plane._lease_next_job()
        assert leased is not None
        assert leased.run_id == high_run.id
        assert leased.priority == "high"
    finally:
        client.close()


def test_autoresearch_run_controls_patch_updates_queue_priority_and_console_filters(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 6 Control Patch Project",
            "Queue priority controls for auto research",
        )
        run = autoresearch_repository.create_run(
            project_id,
            "Queue priority controls for auto research",
        )
        AutoResearchExecutionPlane().enqueue(project_id=project_id, run_id=run.id, action="run")

        patch_response = client.patch(
            f"/api/projects/{project_id}/auto-research/{run.id}/controls",
            json={
                "queue_priority": "high",
                "max_rounds": 2,
                "candidate_execution_limit": 1,
            },
        )
        assert patch_response.status_code == 200
        payload = patch_response.json()
        assert payload["run"]["request"]["queue_priority"] == "high"
        assert payload["run"]["request"]["max_rounds"] == 2
        assert payload["run"]["request"]["candidate_execution_limit"] == 1
        assert payload["execution"]["jobs"][0]["priority"] == "high"

        console_response = client.get(
            f"/api/projects/{project_id}/auto-research/console",
            params={"queue_priority": "high", "budget_status": "constrained"},
        )
        assert console_response.status_code == 200
        console = console_response.json()
        assert console["filtered_run_count"] == 1
        assert console["selected_run_id"] == run.id
        assert console["filters"]["queue_priority"] == "high"
        assert console["runs"][0]["queue_priority"] == "high"
        assert console["runs"][0]["max_rounds"] == 2
        assert console["runs"][0]["candidate_execution_limit"] == 1
        assert console["current_run"]["actions"]["update_controls"] is True
    finally:
        client.close()


def test_autoresearch_stale_lease_recovery_increments_recovery_count_and_fences_old_updates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Phase 3 Recovery Hardening Project",
            "Stale lease recovery fencing for auto research",
        )
        run = autoresearch_repository.create_run(
            project_id,
            "Stale lease recovery fencing for auto research",
        )
        plane = AutoResearchExecutionPlane()
        plane.enqueue(project_id=project_id, run_id=run.id, action="run")

        leased = plane._lease_next_job()
        assert leased is not None
        assert leased.lease_id is not None

        with autoresearch_execution._STATE_LOCK:
            state = autoresearch_execution._load_state()
            stale_heartbeat = (
                autoresearch_execution._utcnow()
                - autoresearch_execution.LEASE_TIMEOUT
                - timedelta(seconds=1)
            )
            autoresearch_execution._save_state(
                state.model_copy(
                    update={
                        "worker": state.worker.model_copy(
                            update={
                                "status": "running",
                                "current_job_id": leased.id,
                                "current_run_id": run.id,
                                "current_lease_id": leased.lease_id,
                                "heartbeat_at": stale_heartbeat,
                            }
                        )
                    }
                )
            )

        recovered = plane._lease_next_job()
        assert recovered is not None
        assert recovered.run_id == run.id
        assert recovered.lease_id is not None
        assert recovered.lease_id != leased.lease_id
        assert recovered.recovery_count == 1

        stale_update = plane._update_job(
            leased.id,
            status="succeeded",
            detail="done",
            expected_lease_id=leased.lease_id,
        )
        assert stale_update is None

        execution = plane.get_run_execution(project_id, run.id)
        assert execution.jobs[-1].recovery_count == 1
        assert execution.jobs[-1].last_recovered_at is not None
        assert execution.worker is not None
        assert execution.worker.recovered_job_count == 1
        assert execution.worker.current_lease_id == recovered.lease_id
    finally:
        client.close()


def test_autoresearch_operator_console_supports_run_filtering_and_search(
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
                    id="paper-console-1",
                    title="Lightweight Reranking Signals for Compact Corpora",
                    abstract="This paper studies lexical reranking and hard negative retrieval signals.",
                    year=2024,
                    source="semantic_scholar",
                ),
                PaperMeta(
                    id="paper-console-2",
                    title="Benchmarking Compact Retrieval Pipelines",
                    abstract="This paper evaluates compact retrieval pipelines under reproducible constraints.",
                    year=2023,
                    source="semantic_scholar",
                ),
            ],
        ),
    )
    try:
        project_id = _create_project(
            client,
            "Phase 6 Filter Console Project",
            "Console triage filter project",
        )

        grounded_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={
                "topic": "Compact reranking for cs retrieval",
                "auto_search_literature": True,
            },
        )
        assert grounded_response.status_code == 200
        grounded_run_id = grounded_response.json()["id"]

        baseline_response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert baseline_response.status_code == 200
        baseline_run_id = baseline_response.json()["id"]
        baseline_run = autoresearch_repository.load_run(project_id, baseline_run_id)
        assert baseline_run is not None
        autoresearch_repository.save_run(
            baseline_run.model_copy(
                update={
                    "literature": [],
                    "paper_markdown": """# Controlled Baseline Paper

## 1. Introduction
This controlled baseline paper summarizes a completed experiment and artifact trail without explicit literature grounding.

## 2. Related Work and Research Plan
No project-specific literature was attached, so related-work grounding is limited.

## 3. Method
The selected candidate keeps the benchmark and execution path intact.

## 4. Experimental Setup
The run executed the benchmark with persisted seeds, sweeps, and artifacts.

## 5. Results
The artifact retained benchmark outputs for the selected candidate.

## 6. Discussion
The run is operationally complete but does not yet make a literature-grounded novelty argument.

## 7. Limitations
- Related-work grounding was intentionally removed for this controlled console test.

## 8. Conclusion
This paper remains artifact-grounded but should require revision before publication packaging.
""",
                }
            )
        )

        queued_run = autoresearch_repository.create_run(project_id, "Queued auto research control path")
        AutoResearchExecutionPlane().enqueue(project_id=project_id, run_id=queued_run.id, action="run")

        grounded_console = client.get(
            f"/api/projects/{project_id}/auto-research/console",
            params={"publish_status": "publish_ready", "novelty_status": "grounded"},
        )
        assert grounded_console.status_code == 200
        grounded_payload = grounded_console.json()
        assert grounded_payload["run_count"] == 3
        assert grounded_payload["filtered_run_count"] == 1
        assert grounded_payload["selected_run_id"] == grounded_run_id
        assert grounded_payload["filters"]["publish_status"] == "publish_ready"
        assert grounded_payload["filters"]["novelty_status"] == "grounded"
        assert grounded_payload["runs"][0]["run_id"] == grounded_run_id
        assert grounded_payload["runs"][0]["review_risk"] == "low"
        assert grounded_payload["runs"][0]["novelty_status"] == "grounded"

        medium_console = client.get(
            f"/api/projects/{project_id}/auto-research/console",
            params={"status": "done", "review_risk": "medium"},
        )
        assert medium_console.status_code == 200
        medium_payload = medium_console.json()
        assert medium_payload["filtered_run_count"] == 1
        assert medium_payload["selected_run_id"] == baseline_run_id
        assert medium_payload["runs"][0]["run_id"] == baseline_run_id
        assert medium_payload["runs"][0]["publish_status"] == "revision_required"
        assert medium_payload["runs"][0]["review_risk"] == "medium"
        assert medium_payload["runs"][0]["novelty_status"] == "missing_context"

        queued_console = client.get(
            f"/api/projects/{project_id}/auto-research/console",
            params={"search": "queued auto research"},
        )
        assert queued_console.status_code == 200
        queued_payload = queued_console.json()
        assert queued_payload["filtered_run_count"] == 1
        assert queued_payload["selected_run_id"] == queued_run.id
        assert queued_payload["filters"]["search"] == "queued auto research"
        assert queued_payload["runs"][0]["run_id"] == queued_run.id
        assert queued_payload["runs"][0]["status"] == "queued"

        empty_console = client.get(
            f"/api/projects/{project_id}/auto-research/console",
            params={"search": "does-not-match"},
        )
        assert empty_console.status_code == 200
        empty_payload = empty_console.json()
        assert empty_payload["run_count"] == 3
        assert empty_payload["filtered_run_count"] == 0
        assert empty_payload["selected_run_id"] is None
        assert empty_payload["current_run"] is None
        assert empty_payload["runs"] == []
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


def test_autoresearch_review_resolves_persisted_literature_citations(
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
                    id="paper-lit-1",
                    title="Lightweight Reranking Signals for Compact Corpora",
                    abstract="This paper studies lexical reranking and hard negative retrieval signals.",
                    year=2024,
                    source="semantic_scholar",
                ),
                PaperMeta(
                    id="paper-lit-2",
                    title="Benchmarking Compact Retrieval Pipelines",
                    abstract="This paper evaluates compact retrieval pipelines under reproducible constraints.",
                    year=2023,
                    source="semantic_scholar",
                ),
            ],
        ),
    )
    try:
        project_id = _create_project(
            client,
            "Citation Hardening Project",
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
        run_id = response.json()["id"]

        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "done"
        assert "## 9. References" in run["paper_markdown"]
        assert "[1]" in run["paper_markdown"]
        assert "[2]" in run["paper_markdown"]

        review = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review").json()
        assert review["overall_status"] == "ready"
        assert review["unsupported_claim_risk"] == "low"
        assert review["citation_coverage"]["literature_item_count"] >= 2
        assert review["citation_coverage"]["cited_literature_count"] >= 2
        assert review["citation_coverage"]["invalid_citation_indices"] == []
        assert review["citation_coverage"]["has_related_work_section"] is True
        assert review["citation_coverage"]["has_references_section"] is True
        assert review["novelty_assessment"]["status"] == "grounded"
        assert review["novelty_assessment"]["compared_paper_count"] >= 2
        assert review["novelty_assessment"]["strong_match_count"] >= 1
        assert review["novelty_assessment"]["covered_claim_count"] >= 1
        assert review["novelty_assessment"]["top_related_work"]
        assert not any(
            item["category"] in {"citation", "context", "provenance"} and item["severity"] != "info"
            for item in review["findings"]
        )
    finally:
        client.close()


def test_autoresearch_review_flags_weak_novelty_grounding_from_persisted_literature_state(
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
                    id="paper-lit-1",
                    title="Lightweight Reranking Signals for Compact Corpora",
                    abstract="This paper studies lexical reranking and hard negative retrieval signals.",
                    year=2024,
                    source="semantic_scholar",
                ),
                PaperMeta(
                    id="paper-lit-2",
                    title="Benchmarking Compact Retrieval Pipelines",
                    abstract="This paper evaluates compact retrieval pipelines under reproducible constraints.",
                    year=2023,
                    source="semantic_scholar",
                ),
            ],
        ),
    )
    try:
        project_id = _create_project(
            client,
            "Weak Novelty Project",
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
        run_id = response.json()["id"]

        run = autoresearch_repository.load_run(project_id, run_id)
        assert run is not None
        autoresearch_repository.save_run(
            run.model_copy(
                update={
                    "literature": [
                        LiteratureInsight(
                            paper_id="paper-unrelated-1",
                            title="Vision Transformers for Medical Imaging",
                            year=2024,
                            source="semantic_scholar",
                            insight="Focuses on radiology segmentation and pathology localization.",
                            method_hint="Use pathology-specific convolutional image encoders.",
                            gap_hint="Test whether mammography pretraining improves lesion localization.",
                        ),
                        LiteratureInsight(
                            paper_id="paper-unrelated-2",
                            title="Protein Folding Acceleration with Diffusion Priors",
                            year=2025,
                            source="semantic_scholar",
                            insight="Studies molecular structure prediction with diffusion-style priors.",
                            method_hint="Use structure-conditioned priors for folding trajectories.",
                            gap_hint="Measure folding stability under simulated biophysics constraints.",
                        ),
                    ]
                }
            )
        )

        review = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review").json()
        assert review["overall_status"] == "needs_revision"
        assert review["unsupported_claim_risk"] == "medium"
        assert review["novelty_assessment"]["status"] == "weak"
        assert review["novelty_assessment"]["strong_match_count"] == 0
        assert review["novelty_assessment"]["covered_claim_count"] == 0
        assert review["novelty_assessment"]["uncovered_claims"]
        assert any(
            item["category"] == "context"
            and "novelty framing is weakly grounded" in item["summary"].lower()
            for item in review["findings"]
        )
    finally:
        client.close()


def test_autoresearch_review_flags_invalid_citation_provenance(
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
                    id="paper-lit-1",
                    title="Compact Retrieval Signals",
                    abstract="This paper studies compact retrieval signals under reproducible settings.",
                    year=2024,
                    source="semantic_scholar",
                )
            ],
        ),
    )
    try:
        project_id = _create_project(
            client,
            "Citation Provenance Project",
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
        run_id = response.json()["id"]

        run = autoresearch_repository.load_run(project_id, run_id)
        assert run is not None
        assert run.paper_markdown is not None
        autoresearch_repository.save_run(
            run.model_copy(
                update={
                    "paper_markdown": run.paper_markdown
                    + "\n\nAdditional unsupported prior-work claim [99].\n"
                }
            )
        )

        review = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/review").json()
        assert review["overall_status"] == "blocked"
        assert review["unsupported_claim_risk"] == "high"
        assert review["citation_coverage"]["invalid_citation_indices"] == [99]
        assert any(
            item["category"] == "provenance"
            and "persisted run literature" in item["summary"].lower()
            for item in review["findings"]
        )
        assert any(
            item["title"] == "Repair citation provenance against persisted literature state"
            for item in review["revision_plan"]
        )
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


def test_autoresearch_exposes_execution_state_for_completed_run(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    try:
        project_id = _create_project(
            client,
            "Execution Plane Success",
            "Automatic topic classification for compact CS abstracts",
        )
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Automatic topic classification for compact CS abstracts"},
        )
        assert response.status_code == 200
        run_id = response.json()["id"]

        execution = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/execution")
        assert execution.status_code == 200
        payload = execution.json()
        assert payload["run_id"] == run_id
        assert len(payload["jobs"]) == 1
        assert payload["jobs"][0]["action"] == "run"
        assert payload["jobs"][0]["status"] == "succeeded"
        assert payload["active_job_id"] is None
        assert payload["cancel_requested"] is False
        assert payload["worker"]["status"] == "idle"
        assert payload["worker"]["queue_depth"] == 0
    finally:
        client.close()


def test_autoresearch_resume_enqueues_new_job_after_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    call_count = {"count": 0}

    def fake_execute(self, *, project_id: str, run_id: str, **kwargs):
        del self, kwargs
        call_count["count"] += 1
        run = autoresearch_repository.load_run(project_id, run_id)
        assert run is not None
        if call_count["count"] == 1:
            return autoresearch_repository.save_run(
                run.model_copy(update={"status": "failed", "error": "synthetic failure"})
            )
        return autoresearch_repository.save_run(
            run.model_copy(update={"status": "done", "error": None})
        )

    monkeypatch.setattr(autoresearch_orchestrator.AutoResearchOrchestrator, "execute", fake_execute)
    try:
        project_id = _create_project(client, "Resume Run", "Synthetic execution resume")
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Synthetic execution resume"},
        )
        assert response.status_code == 200
        run_id = response.json()["id"]
        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "failed"
        assert run["error"] == "synthetic failure"

        resume = client.post(f"/api/projects/{project_id}/auto-research/{run_id}/resume")
        assert resume.status_code == 200
        body = resume.json()
        assert body["run_id"] == run_id
        assert body["status"] == "accepted"
        assert body["execution"]["jobs"][-1]["action"] == "resume"

        execution = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/execution")
        assert execution.status_code == 200
        jobs = execution.json()["jobs"]
        assert [item["action"] for item in jobs] == ["run", "resume"]
        assert [item["status"] for item in jobs] == ["failed", "succeeded"]
        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "done"
    finally:
        client.close()


def test_autoresearch_retry_enqueues_new_job_after_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    call_count = {"count": 0}

    def fake_execute(self, *, project_id: str, run_id: str, **kwargs):
        del self, kwargs
        call_count["count"] += 1
        run = autoresearch_repository.load_run(project_id, run_id)
        assert run is not None
        if call_count["count"] == 1:
            return autoresearch_repository.save_run(
                run.model_copy(update={"status": "failed", "error": "retry me"})
            )
        return autoresearch_repository.save_run(
            run.model_copy(update={"status": "done", "error": None})
        )

    monkeypatch.setattr(autoresearch_orchestrator.AutoResearchOrchestrator, "execute", fake_execute)
    try:
        project_id = _create_project(client, "Retry Run", "Synthetic execution retry")
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Synthetic execution retry"},
        )
        assert response.status_code == 200
        run_id = response.json()["id"]
        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "failed"
        assert run["error"] == "retry me"

        retry = client.post(f"/api/projects/{project_id}/auto-research/{run_id}/retry")
        assert retry.status_code == 200
        body = retry.json()
        assert body["run_id"] == run_id
        assert body["status"] == "accepted"
        assert body["execution"]["jobs"][-1]["action"] == "retry"

        execution = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/execution")
        assert execution.status_code == 200
        jobs = execution.json()["jobs"]
        assert [item["action"] for item in jobs] == ["run", "retry"]
        assert [item["status"] for item in jobs] == ["failed", "succeeded"]
        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "done"
    finally:
        client.close()


def test_autoresearch_can_cancel_queued_job_before_worker_starts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    monkeypatch.setattr(autoresearch_api.AutoResearchExecutionPlane, "drain", lambda self: None)
    try:
        project_id = _create_project(client, "Cancel Run", "Synthetic execution cancel")
        response = client.post(
            f"/api/projects/{project_id}/auto-research/run",
            json={"topic": "Synthetic execution cancel"},
        )
        assert response.status_code == 200
        run_id = response.json()["id"]
        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "queued"

        cancel = client.post(f"/api/projects/{project_id}/auto-research/{run_id}/cancel")
        assert cancel.status_code == 200
        body = cancel.json()
        assert body["run_id"] == run_id
        assert body["status"] == "accepted"
        assert body["execution"]["jobs"][-1]["status"] == "canceled"
        assert body["execution"]["active_job_id"] is None

        execution = client.get(f"/api/projects/{project_id}/auto-research/{run_id}/execution")
        assert execution.status_code == 200
        jobs = execution.json()["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["status"] == "canceled"

        run = client.get(f"/api/projects/{project_id}/auto-research/{run_id}").json()
        assert run["status"] == "canceled"
        assert run["error"] == "Run canceled before execution started."
    finally:
        client.close()


def test_autoresearch_resume_reuses_checkpointed_rounds(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _configure_test_client(monkeypatch, tmp_path)
    call_log: list[tuple[str, int]] = []
    cancel_state = {"armed": False}

    def fake_run(
        self,
        *,
        code_filename_prefix: str,
        round_index: int,
        **kwargs,
    ):
        del self, kwargs
        call_log.append((code_filename_prefix, round_index))
        score = 0.60 + (0.01 * round_index)
        code_path = tmp_path / f"{code_filename_prefix}_{round_index}.py"
        code_path.write_text(f"# {code_filename_prefix} round {round_index}\n", encoding="utf-8")
        artifact = ResultArtifact(
            status="done",
            summary=f"{code_filename_prefix} round {round_index}",
            key_findings=[f"{code_filename_prefix}:{round_index}"],
            primary_metric="macro_f1",
            best_system="demo_system",
            objective_system="demo_system",
            objective_score=score,
            system_results=[
                {"system": "demo_system", "metrics": {"accuracy": score, "macro_f1": score}},
            ],
            aggregate_system_results=[
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
                    "detail": "ok",
                    "rule_id": "aggregate_metric_reporting",
                    "rule_kind": "aggregate_metric_reporting",
                }
            ],
            tables=[],
            environment={},
            outputs={},
        )
        cancel_state["armed"] = True
        return f"strategy_{round_index}", str(code_path), artifact

    monkeypatch.setattr(AutoExperimentRunner, "run", fake_run)
    monkeypatch.setattr(
        autoresearch_orchestrator.PaperWriter,
        "write",
        lambda self, *args, **kwargs: "# resumed checkpoint paper\n",
    )
    try:
        project_id = _create_project(client, "Checkpoint Resume", "Checkpoint resume topic")
        run = autoresearch_repository.create_run(project_id, "Checkpoint resume topic")

        db = db_module.SessionLocal()
        try:
            try:
                autoresearch_orchestrator.AutoResearchOrchestrator().execute(
                    db=db,
                    project_id=project_id,
                    run_id=run.id,
                    topic="Checkpoint resume topic",
                    should_cancel=lambda: cancel_state["armed"],
                )
                raise AssertionError("expected cancellation")
            except autoresearch_orchestrator.AutoResearchExecutionCancelled:
                pass
        finally:
            db.close()

        canceled = autoresearch_repository.load_run(project_id, run.id)
        assert canceled is not None
        assert canceled.status == "canceled"
        running_candidate = next(item for item in canceled.candidates if item.status == "running")
        assert len(running_candidate.attempts) == 1
        assert running_candidate.attempts[0].round_index == 1
        first_candidate_id = running_candidate.id

        cancel_state["armed"] = False
        db = db_module.SessionLocal()
        try:
            resumed = autoresearch_orchestrator.AutoResearchOrchestrator().execute(
                db=db,
                project_id=project_id,
                run_id=run.id,
                topic="Checkpoint resume topic",
                execution_action="resume",
                should_cancel=lambda: False,
            )
        finally:
            db.close()

        assert resumed.status == "done"
        resumed_candidate = next(item for item in resumed.candidates if item.id == first_candidate_id)
        assert [item.round_index for item in resumed_candidate.attempts] == [1, 2, 3]
        assert call_log.count((first_candidate_id, 1)) == 1
        assert (first_candidate_id, 2) in call_log
        assert (first_candidate_id, 3) in call_log
    finally:
        client.close()
