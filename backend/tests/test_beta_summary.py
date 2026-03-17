from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import api.progress as progress_api
import api.review as review_api
import api.export as export_api
import main as main_module
import models  # noqa: F401
from config import db as db_module
from config import deps as deps_module
from config.settings import settings
from main import app
from models.base import Base
import services.llm.client as llm_client


def make_client(monkeypatch, tmp_path: Path) -> tuple[TestClient, object]:
    db_path = tmp_path / "beta-summary.sqlite3"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "SessionLocal", session_local)
    monkeypatch.setattr(main_module, "SessionLocal", session_local)
    monkeypatch.setattr(deps_module, "SessionLocal", session_local)
    monkeypatch.setattr(progress_api, "SessionLocal", session_local)
    monkeypatch.setattr(review_api, "SessionLocal", session_local)
    monkeypatch.setattr(export_api, "SessionLocal", session_local)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "audit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    monkeypatch.setattr(llm_client, "litellm_completion", None)
    return TestClient(app), engine


def test_beta_summary_reports_usage_and_feedback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "auth_secret", "phase6-secret")
    monkeypatch.setattr(settings, "auth_required", True)
    client, engine = make_client(monkeypatch, tmp_path)

    try:
        session = client.post(
            "/api/auth/session",
            json={"email": "alice@example.com", "name": "Alice"},
        )
        assert session.status_code == 200
        token = session.json()["access_token"]
        user_id = session.json()["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        project = client.post(
            "/api/projects",
            json={"title": "Beta Project", "topic": "Phase 6", "status": "init"},
            headers=headers,
        )
        assert project.status_code == 200
        project_id = project.json()["id"]

        generate = client.post(
            f"/api/projects/{project_id}/drafts/generate",
            json={"topic": "Phase 6", "language": "zh"},
            headers=headers,
        )
        assert generate.status_code == 200

        feedback = client.post(
            f"/api/projects/{project_id}/beta/feedback",
            json={
                "rating": 4,
                "category": "usability",
                "comment": "Integrated beta flow is coherent and fast enough.",
            },
            headers=headers,
        )
        assert feedback.status_code == 200
        assert feedback.json()["user_id"] == user_id

        summary = client.get(f"/api/projects/{project_id}/beta/summary", headers=headers)
        assert summary.status_code == 200
        payload = summary.json()

        assert payload["project_id"] == project_id
        assert payload["performance"]["llm_calls"] >= 1
        assert payload["performance"]["total_tokens"] > 0
        assert payload["performance"]["latest_operation"] == "draft.generate"
        assert payload["feedback_count"] == 1
        assert payload["average_rating"] == 4.0
        assert payload["feedback"][0]["comment"].startswith("Integrated beta flow")
    finally:
        client.close()
        engine.dispose()
