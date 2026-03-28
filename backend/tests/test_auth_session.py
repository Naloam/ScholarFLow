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


def test_open_workspace_lists_anonymous_projects_without_auth(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "auth_secret", "phase6-secret")
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "audit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    client, _session_local, engine = make_client(monkeypatch, tmp_path)

    try:
        anonymous_project = client.post(
            "/api/projects",
            json={"title": "Open Project", "topic": "Anonymous workspace", "status": "init"},
        )
        assert anonymous_project.status_code == 200
        anonymous_project_id = anonymous_project.json()["id"]

        alice_session = client.post(
            "/api/auth/session",
            json={"email": "alice@example.com", "name": "Alice"},
        )
        assert alice_session.status_code == 200
        alice_token = alice_session.json()["access_token"]

        owned_project = client.post(
            "/api/projects",
            json={"title": "Private Project", "topic": "Owned workspace", "status": "init"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert owned_project.status_code == 200

        listed = client.get("/api/projects")
        assert listed.status_code == 200
        assert listed.json() == [
            {
                "access_mode": "anonymous",
                "created_at": listed.json()[0]["created_at"],
                "id": anonymous_project_id,
                "status": "init",
                "template_id": None,
                "title": "Open Project",
                "topic": "Anonymous workspace",
                "updated_at": listed.json()[0]["updated_at"],
                "user_id": None,
            }
        ]
    finally:
        client.close()
        engine.dispose()


def test_auth_config_reports_api_token_protection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "api_token", "service-token")
    monkeypatch.setattr(settings, "auth_secret", None)
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "audit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    client, _session_local, engine = make_client(monkeypatch, tmp_path)

    try:
        response = client.get("/api/auth/config")
        assert response.status_code == 200
        assert response.json() == {
            "auth_required": False,
            "api_protected": True,
            "session_enabled": False,
        }
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


def test_invited_tutor_gets_read_only_project_access_and_can_submit_mentor_feedback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "auth_secret", "phase6-secret")
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "audit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    client, _session_local, engine = make_client(monkeypatch, tmp_path)

    try:
        student_session = client.post(
            "/api/auth/session",
            json={"email": "alice@example.com", "name": "Alice", "role": "student"},
        )
        assert student_session.status_code == 200
        assert student_session.json()["user"]["role"] == "student"
        student_token = student_session.json()["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}

        tutor_session = client.post(
            "/api/auth/session",
            json={"email": "mentor@example.com", "name": "Mentor", "role": "tutor"},
        )
        assert tutor_session.status_code == 200
        assert tutor_session.json()["user"]["role"] == "tutor"
        tutor_token = tutor_session.json()["access_token"]
        tutor_headers = {"Authorization": f"Bearer {tutor_token}"}

        create_project = client.post(
            "/api/projects",
            json={"title": "Mentor Project", "topic": "Phase 7", "status": "init"},
            headers=student_headers,
        )
        assert create_project.status_code == 200
        project_id = create_project.json()["id"]

        invite = client.post(
            f"/api/projects/{project_id}/mentor/access",
            json={"email": "mentor@example.com", "name": "Mentor"},
            headers=student_headers,
        )
        assert invite.status_code == 200
        assert invite.json()["mentor_email"] == "mentor@example.com"

        student_projects = client.get("/api/projects", headers=student_headers)
        assert student_projects.status_code == 200
        assert student_projects.json() == [
            {
                "access_mode": "owner",
                "created_at": student_projects.json()[0]["created_at"],
                "id": project_id,
                "status": "init",
                "template_id": None,
                "title": "Mentor Project",
                "topic": "Phase 7",
                "updated_at": student_projects.json()[0]["updated_at"],
                "user_id": student_session.json()["user"]["id"],
            }
        ]

        tutor_projects = client.get("/api/projects", headers=tutor_headers)
        assert tutor_projects.status_code == 200
        assert tutor_projects.json() == [
            {
                "access_mode": "mentor",
                "created_at": tutor_projects.json()[0]["created_at"],
                "id": project_id,
                "status": "init",
                "template_id": None,
                "title": "Mentor Project",
                "topic": "Phase 7",
                "updated_at": tutor_projects.json()[0]["updated_at"],
                "user_id": student_session.json()["user"]["id"],
            }
        ]

        generate = client.post(
            f"/api/projects/{project_id}/drafts/generate",
            json={"topic": "Phase 7", "language": "zh"},
            headers=student_headers,
        )
        assert generate.status_code == 200

        tutor_project = client.get(f"/api/projects/{project_id}", headers=tutor_headers)
        assert tutor_project.status_code == 200

        tutor_drafts = client.get(f"/api/projects/{project_id}/drafts", headers=tutor_headers)
        assert tutor_drafts.status_code == 200
        assert len(tutor_drafts.json()) == 1

        tutor_mentor_access = client.get(f"/api/projects/{project_id}/mentor/access", headers=tutor_headers)
        assert tutor_mentor_access.status_code == 200
        assert tutor_mentor_access.json()[0]["mentor_email"] == "mentor@example.com"

        with client.websocket_connect(f"/ws/projects/{project_id}/progress?token={tutor_token}") as websocket:
            snapshot = websocket.receive_json()
        assert snapshot["project_id"] == project_id

        forbidden_generate = client.post(
            f"/api/projects/{project_id}/drafts/generate",
            json={"topic": "Tutor should be read only", "language": "zh"},
            headers=tutor_headers,
        )
        assert forbidden_generate.status_code == 403

        mentor_feedback = client.post(
            f"/api/projects/{project_id}/mentor/feedback",
            json={
                "draft_version": 1,
                "summary": "The draft is on track but still needs stronger grounding.",
                "strengths": "The structure is clear and the topic framing is solid.",
                "concerns": "The main claims still need more direct evidence.",
                "next_steps": "Attach stronger citations and tighten the method explanation.",
            },
            headers=tutor_headers,
        )
        assert mentor_feedback.status_code == 200
        assert mentor_feedback.json()["mentor_email"] == "mentor@example.com"

        student_feedback = client.get(f"/api/projects/{project_id}/mentor/feedback", headers=student_headers)
        assert student_feedback.status_code == 200
        assert len(student_feedback.json()) == 1
        assert student_feedback.json()[0]["summary"].startswith("The draft is on track")
    finally:
        client.close()
        engine.dispose()
