from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import api.export as export_api
import api.progress as progress_api
import api.review as review_api
import main as main_module
import models  # noqa: F401
import services.llm.client as llm_client
from config import db as db_module
from config import deps as deps_module
from config.settings import settings
from main import app
from models.base import Base
from models.evidence import Evidence
from models.paper import Paper
from models.project_paper import ProjectPaper


def test_topic_to_export_workflow(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "workflow.sqlite3"
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

    client = TestClient(app)

    try:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        templates = client.get("/api/templates")
        assert templates.status_code == 200
        assert len(templates.json()["items"]) >= 1

        create_project = client.post(
            "/api/projects",
            json={
                "title": "Phase 6 E2E Project",
                "topic": "Realtime academic writing workspace",
                "template_id": "builtin:general_paper",
                "status": "init",
            },
        )
        assert create_project.status_code == 200
        project_id = create_project.json()["id"]
        assert project_id

        project = client.get(f"/api/projects/{project_id}")
        assert project.status_code == 200
        assert project.json()["title"] == "Phase 6 E2E Project"

        with client.websocket_connect(f"/ws/projects/{project_id}/progress") as websocket:
            snapshot = websocket.receive_json()
        assert snapshot["status"] == "init"
        assert snapshot["phase"] == "Phase 2"
        assert snapshot["draft_count"] == 0

        generate_draft = client.post(
            f"/api/projects/{project_id}/drafts/generate",
            json={
                "topic": "Realtime academic writing workspace",
                "template_id": "builtin:general_paper",
                "language": "zh",
            },
        )
        assert generate_draft.status_code == 200

        drafts = client.get(f"/api/projects/{project_id}/drafts")
        assert drafts.status_code == 200
        draft_items = drafts.json()
        assert len(draft_items) == 1
        assert draft_items[0]["version"] == 1
        assert draft_items[0]["content"]

        draft_detail = client.get(f"/api/projects/{project_id}/drafts/1")
        assert draft_detail.status_code == 200
        assert draft_detail.json()["version"] == 1

        status_after_draft = client.get(f"/api/projects/{project_id}/status")
        assert status_after_draft.status_code == 200
        assert status_after_draft.json()["status"] == "edit"
        assert status_after_draft.json()["phase"] == "Phase 3"

        with client.websocket_connect(f"/ws/projects/{project_id}/progress") as websocket:
            snapshot = websocket.receive_json()
        assert snapshot["status"] == "edit"
        assert snapshot["draft_count"] == 1
        assert snapshot["latest_draft_version"] == 1

        run_review = client.post(f"/api/projects/{project_id}/review", json={"draft_version": 1})
        assert run_review.status_code == 200

        reviews = client.get(f"/api/projects/{project_id}/review")
        assert reviews.status_code == 200
        review_items = reviews.json()
        assert len(review_items) == 1
        assert review_items[0]["draft_version"] == 1
        assert len(review_items[0]["suggestions"]) >= 1

        with client.websocket_connect(f"/ws/projects/{project_id}/progress") as websocket:
            snapshot = websocket.receive_json()
        assert snapshot["status"] == "review"
        assert snapshot["review_count"] == 1
        assert snapshot["latest_review_status"] == "ready"

        run_export = client.post(f"/api/projects/{project_id}/export", json={"format": "markdown"})
        assert run_export.status_code == 200
        export_id = run_export.json()["id"]

        export_status = client.get(f"/api/projects/{project_id}/export/{export_id}")
        assert export_status.status_code == 200
        assert export_status.json()["status"] == "done"
        assert export_status.json()["download_ready"] is True

        export_download = client.get(f"/api/projects/{project_id}/export/{export_id}/download")
        assert export_download.status_code == 200
        assert export_download.headers["content-disposition"].endswith(f'{export_id}.md"')
        assert "Abstract" in export_download.text

        status_after_export = client.get(f"/api/projects/{project_id}/status")
        assert status_after_export.status_code == 200
        assert status_after_export.json()["status"] == "done"
        assert status_after_export.json()["phase"] == "Phase 6"

        analysis = client.get(f"/api/projects/{project_id}/analysis/summary")
        assert analysis.status_code == 200
        analysis_body = analysis.json()
        assert analysis_body["project_id"] == project_id
        assert analysis_body["draft_version"] == 1
        assert analysis_body["similarity"]["status"] == "clear"

        with client.websocket_connect(f"/ws/projects/{project_id}/progress") as websocket:
            snapshot = websocket.receive_json()
        assert snapshot["status"] == "done"
        assert snapshot["latest_export_status"] == "done"
        assert snapshot["export_count"] == 1

        exports_dir = data_dir / "projects" / project_id / "exports"
        assert exports_dir.exists()
        assert any(path.suffix == ".md" for path in exports_dir.iterdir())
    finally:
        client.close()
        engine.dispose()


def test_analysis_summary_flags_high_overlap_against_project_sources(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "similarity.sqlite3"
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

    client = TestClient(app)

    try:
        create_project = client.post(
            "/api/projects",
            json={
                "title": "Phase 7 Similarity Project",
                "topic": "Overlap screening",
                "template_id": "builtin:general_paper",
                "status": "init",
            },
        )
        assert create_project.status_code == 200
        project_id = create_project.json()["id"]

        generate_draft = client.post(
            f"/api/projects/{project_id}/drafts/generate",
            json={
                "topic": "Overlap screening",
                "template_id": "builtin:general_paper",
                "language": "zh",
            },
        )
        assert generate_draft.status_code == 200

        overlapping_paragraph = (
            "Graph neural recommenders learn user-item structure from interaction graphs and "
            "consistently improve ranking quality when high-order neighborhood information is "
            "preserved during message passing and representation refinement."
        )
        update_draft = client.put(
            f"/api/projects/{project_id}/drafts/1",
            json={
                "content": f"{overlapping_paragraph}\n\nThis paragraph adds enough surrounding context to stay realistic.",
                "section": "introduction",
            },
        )
        assert update_draft.status_code == 200

        with testing_session_local() as db:
            paper = Paper(
                id="paper_similarity",
                title="Graph Recommender Foundations",
                abstract=(
                    "Graph neural recommenders learn user-item structure from interaction graphs "
                    "and consistently improve ranking quality when high-order neighborhood "
                    "information is preserved during message passing and representation refinement."
                ),
                source="manual",
            )
            db.add(paper)
            db.add(ProjectPaper(project_id=project_id, paper_id=paper.id))
            db.add(
                Evidence(
                    id="evidence_similarity",
                    project_id=project_id,
                    claim_text="Graph recommenders preserve neighborhood information.",
                    paper_id=paper.id,
                    snippet=(
                        "Graph neural recommenders learn user-item structure from interaction "
                        "graphs and consistently improve ranking quality when high-order "
                        "neighborhood information is preserved during message passing and "
                        "representation refinement."
                    ),
                    type="quote",
                )
            )
            db.commit()

        analysis = client.get(f"/api/projects/{project_id}/analysis/summary")
        assert analysis.status_code == 200
        body = analysis.json()
        assert body["similarity"]["status"] in {"warning", "high"}
        assert body["similarity"]["flagged_paragraphs"] >= 1
        assert body["similarity"]["matches"][0]["source_label"].startswith("Graph Recommender Foundations")
        assert body["similarity"]["matches"][0]["similarity"] >= 0.35
    finally:
        client.close()
        engine.dispose()
