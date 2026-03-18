from __future__ import annotations

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
import services.llm.client as llm_client
from config import db as db_module
from config import deps as deps_module
from config.settings import settings
from main import app
from models.base import Base


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
        assert run["artifact"]["status"] == "done"
        assert len(run["attempts"]) == 3
        assert run["attempts"][0]["goal"] == "initial_run"
        assert run["attempts"][-1]["strategy"] == "naive_bayes_search"
        assert run["selected_round_index"] is not None
        assert run["artifact"]["best_system"]
        assert len(run["artifact"]["tables"]) >= 1
        assert Path(run["generated_code_path"]).is_file()

        paper = run["paper_markdown"]
        assert "## 2. Related Work and Research Plan" in paper
        assert "## 4. Experimental Setup" in paper
        assert "## 5. Results" in paper
        assert "| System | Accuracy | Macro F1 |" in paper
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
    finally:
        client.close()
