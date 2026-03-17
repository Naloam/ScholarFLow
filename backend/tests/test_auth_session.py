from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
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
from services.security.rate_limit import clear_rate_limit_state


def make_client(monkeypatch, tmp_path: Path) -> tuple[TestClient, sessionmaker, object]:
    db_path = tmp_path / "auth.sqlite3"
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
    monkeypatch.setattr(llm_client, "litellm_completion", None)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    clear_rate_limit_state()
    return TestClient(app), session_local, engine


def test_auth_session_creates_owned_project_and_blocks_other_user(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "auth_secret", "phase6-secret")
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "audit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    client, _session_local, engine = make_client(monkeypatch, tmp_path)

    try:
        anonymous = client.get("/api/templates")
        assert anonymous.status_code == 401

        alice_session = client.post(
            "/api/auth/session",
            json={"email": "alice@example.com", "name": "Alice"},
        )
        assert alice_session.status_code == 200
        alice_token = alice_session.json()["access_token"]

        create_project = client.post(
            "/api/projects",
            json={"title": "Alice Project", "topic": "Auth", "status": "init"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert create_project.status_code == 200
        project_id = create_project.json()["id"]

        owned_project = client.get(
            f"/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert owned_project.status_code == 200
        assert owned_project.json()["user_id"] == alice_session.json()["user"]["id"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {alice_token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "alice@example.com"

        bob_session = client.post(
            "/api/auth/session",
            json={"email": "bob@example.com", "name": "Bob"},
        )
        assert bob_session.status_code == 200
        bob_token = bob_session.json()["access_token"]

        forbidden = client.get(
            f"/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert forbidden.status_code == 403

        with client.websocket_connect(f"/ws/projects/{project_id}/progress?token={alice_token}") as websocket:
            snapshot = websocket.receive_json()
        assert snapshot["project_id"] == project_id

        try:
            with client.websocket_connect(f"/ws/projects/{project_id}/progress?token={bob_token}"):
                raise AssertionError("expected websocket to be rejected")
        except WebSocketDisconnect as exc:
            assert exc.code == 4403
    finally:
        client.close()
        engine.dispose()


def test_owned_project_requires_matching_session_even_when_auth_is_optional(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "auth_secret", "phase6-secret")
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "audit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    client, _session_local, engine = make_client(monkeypatch, tmp_path)

    try:
        alice_session = client.post(
            "/api/auth/session",
            json={"email": "alice@example.com", "name": "Alice"},
        )
        assert alice_session.status_code == 200
        alice_token = alice_session.json()["access_token"]

        create_project = client.post(
            "/api/projects",
            json={"title": "Private Project", "topic": "Auth", "status": "init"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert create_project.status_code == 200
        project_id = create_project.json()["id"]

        anonymous = client.get(f"/api/projects/{project_id}")
        assert anonymous.status_code == 401

        try:
            with client.websocket_connect(f"/ws/projects/{project_id}/progress"):
                raise AssertionError("expected websocket to require auth")
        except WebSocketDisconnect as exc:
            assert exc.code == 4401

        owned = client.get(
            f"/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert owned.status_code == 200
    finally:
        client.close()
        engine.dispose()


def test_project_scoped_review_and_export_resources_do_not_leak(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "auth_secret", "phase6-secret")
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "audit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    client, _session_local, engine = make_client(monkeypatch, tmp_path)

    try:
        alice_session = client.post(
            "/api/auth/session",
            json={"email": "alice@example.com", "name": "Alice"},
        )
        assert alice_session.status_code == 200
        alice_token = alice_session.json()["access_token"]
        headers = {"Authorization": f"Bearer {alice_token}"}

        first_project = client.post(
            "/api/projects",
            json={"title": "Scoped A", "topic": "Auth", "status": "init"},
            headers=headers,
        )
        assert first_project.status_code == 200
        first_project_id = first_project.json()["id"]

        second_project = client.post(
            "/api/projects",
            json={"title": "Scoped B", "topic": "Auth", "status": "init"},
            headers=headers,
        )
        assert second_project.status_code == 200
        second_project_id = second_project.json()["id"]

        generate = client.post(
            f"/api/projects/{first_project_id}/drafts/generate",
            json={"topic": "Scoped Auth", "language": "zh"},
            headers=headers,
        )
        assert generate.status_code == 200

        review = client.post(
            f"/api/projects/{first_project_id}/review",
            json={"draft_version": 1},
            headers=headers,
        )
        assert review.status_code == 200
        review_id = review.json()["id"]

        export = client.post(
            f"/api/projects/{first_project_id}/export",
            json={"format": "markdown"},
            headers=headers,
        )
        assert export.status_code == 200
        export_id = export.json()["id"]

        wrong_review = client.get(
            f"/api/projects/{second_project_id}/review/{review_id}",
            headers=headers,
        )
        assert wrong_review.status_code == 404

        wrong_followups = client.get(
            f"/api/projects/{second_project_id}/review/{review_id}/followups",
            headers=headers,
        )
        assert wrong_followups.status_code == 404

        wrong_export = client.get(
            f"/api/projects/{second_project_id}/export/{export_id}",
            headers=headers,
        )
        assert wrong_export.status_code == 404

        wrong_download = client.get(
            f"/api/projects/{second_project_id}/export/{export_id}/download",
            headers=headers,
        )
        assert wrong_download.status_code == 404
    finally:
        client.close()
        engine.dispose()
