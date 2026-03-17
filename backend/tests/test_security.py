from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

import models  # noqa: F401
import main as main_module
from config import deps as deps_module
from config.settings import settings
from main import app
from models.audit_log import AuditLog
from models.base import Base
from services.security.rate_limit import clear_rate_limit_state


def make_client(monkeypatch, tmp_path):
    db_path = tmp_path / "security.sqlite3"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main_module, "SessionLocal", session_local)
    monkeypatch.setattr(deps_module, "SessionLocal", session_local)
    clear_rate_limit_state()
    client = TestClient(app)
    return client, session_local, engine


def test_api_token_protects_api_routes(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "api_token", "test-token")
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    monkeypatch.setattr(settings, "audit_enabled", False)
    client, _session_local, engine = make_client(monkeypatch, tmp_path)
    try:
        unauthorized = client.get("/api/templates")
        assert unauthorized.status_code == 401

        authorized = client.get(
            "/api/templates",
            headers={"Authorization": "Bearer test-token"},
        )
        assert authorized.status_code == 200
    finally:
        client.close()
        engine.dispose()


def test_rate_limiting_blocks_second_request(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 1)
    monkeypatch.setattr(settings, "audit_enabled", False)
    client, _session_local, engine = make_client(monkeypatch, tmp_path)
    try:
        first = client.get("/api/templates")
        second = client.get("/api/templates")

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.headers.get("Retry-After") is not None
    finally:
        client.close()
        engine.dispose()


def test_audit_log_records_request_metadata(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    monkeypatch.setattr(settings, "audit_enabled", True)
    client, session_local, engine = make_client(monkeypatch, tmp_path)
    try:
        response = client.get("/api/templates")
        assert response.status_code == 200
        request_id = response.headers.get("X-Request-ID")
        assert request_id

        with session_local() as db:
            row = db.execute(select(AuditLog).where(AuditLog.request_id == request_id)).scalar_one()

        assert row.path == "/api/templates"
        assert row.method == "GET"
        assert row.status_code == 200
        assert row.duration_ms >= 0
    finally:
        client.close()
        engine.dispose()


def test_cors_preflight_bypasses_auth_guard(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 0)
    monkeypatch.setattr(settings, "audit_enabled", False)
    client, _session_local, engine = make_client(monkeypatch, tmp_path)
    try:
        response = client.options(
            "/api/projects",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        assert response.status_code in {200, 204}
        assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    finally:
        client.close()
        engine.dispose()
