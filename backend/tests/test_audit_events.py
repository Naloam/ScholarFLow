from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

import api.chunks as chunks_api
import api.progress as progress_api
import main as main_module
import models  # noqa: F401
from config import db as db_module
from config import deps as deps_module
from config.settings import settings
from main import app
from models.audit_log import AuditLog
from models.base import Base
from services.security.rate_limit import clear_rate_limit_state


def make_client(monkeypatch, tmp_path: Path) -> tuple[TestClient, sessionmaker, object]:
    db_path = tmp_path / "audit-events.sqlite3"
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
    monkeypatch.setattr(chunks_api, "SessionLocal", session_local)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    clear_rate_limit_state()
    return TestClient(app), session_local, engine


def create_owned_project(client: TestClient) -> tuple[str, str]:
    session = client.post(
        "/api/auth/session",
        json={"email": "alice@example.com", "name": "Alice"},
    )
    assert session.status_code == 200
    token = session.json()["access_token"]

    project = client.post(
        "/api/projects",
        json={"title": "Audit Project", "topic": "Audit", "status": "init"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert project.status_code == 200
    return token, project.json()["id"]


def test_websocket_progress_events_are_audited(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "auth_secret", "phase6-secret")
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "audit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    client, session_local, engine = make_client(monkeypatch, tmp_path)

    try:
        token, project_id = create_owned_project(client)
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        user_id = me.json()["id"]

        with client.websocket_connect(f"/ws/projects/{project_id}/progress?token={token}") as websocket:
            snapshot = websocket.receive_json()
        assert snapshot["project_id"] == project_id

        try:
            with client.websocket_connect(f"/ws/projects/{project_id}/progress"):
                raise AssertionError("expected websocket auth rejection")
        except WebSocketDisconnect as exc:
            assert exc.code == 4401

        with session_local() as db:
            rows = list(
                db.execute(
                    select(AuditLog)
                    .where(AuditLog.event_type == "websocket")
                    .where(AuditLog.resource_id == project_id)
                ).scalars()
            )

        actions = {row.action for row in rows}
        assert "connected" in actions
        assert "rejected" in actions
        connected_row = next(row for row in rows if row.action == "connected")
        rejected_row = next(row for row in rows if row.action == "rejected")
        assert connected_row.user_id == user_id
        assert rejected_row.user_id is None
    finally:
        client.close()
        engine.dispose()


def test_background_task_lifecycle_is_audited(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "auth_secret", "phase6-secret")
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "audit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    client, session_local, engine = make_client(monkeypatch, tmp_path)

    try:
        token, project_id = create_owned_project(client)
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        user_id = me.json()["id"]

        response = client.post(
            f"/api/projects/{project_id}/chunks/rebuild",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        task_id = response.json()["task_id"]

        with session_local() as db:
            rows = list(
                db.execute(
                    select(AuditLog)
                    .where(AuditLog.event_type == "task")
                    .where(AuditLog.request_id == task_id)
                ).scalars()
            )

        actions = {row.action for row in rows}
        assert {"queued", "running", "done"} <= actions
        assert {row.path for row in rows} == {"/internal/tasks/chunks.rebuild"}
        assert {row.resource_id for row in rows} == {project_id}
        assert {row.user_id for row in rows} == {user_id}
    finally:
        client.close()
        engine.dispose()
