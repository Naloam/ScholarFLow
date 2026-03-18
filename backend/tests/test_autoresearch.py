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
import services.llm.client as llm_client
from config import db as db_module
from config import deps as deps_module
from config.settings import settings
from main import app
from models.base import Base
from schemas.autoresearch import ExperimentAttempt, ResultArtifact
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
