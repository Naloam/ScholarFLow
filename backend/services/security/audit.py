from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from config.settings import settings
from models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    client_ip: str | None,
    user_id: str | None,
    duration_ms: int,
    event_type: str = "http",
    action: str = "request",
    resource_id: str | None = None,
    detail: str | None = None,
) -> None:
    row = AuditLog(
        id=f"audit_{uuid4().hex}",
        request_id=request_id,
        event_type=event_type,
        action=action,
        method=method,
        path=path,
        resource_id=resource_id,
        detail=detail,
        status_code=status_code,
        client_ip=client_ip,
        user_id=user_id,
        duration_ms=duration_ms,
    )
    db.add(row)
    db.commit()


def write_audit_log(
    session_factory: Callable[[], Session],
    **payload,
) -> None:
    if not settings.audit_enabled:
        return
    db = session_factory()
    try:
        create_audit_log(db, **payload)
    except Exception:
        pass
    finally:
        db.close()


def write_websocket_audit_log(
    session_factory: Callable[[], Session],
    *,
    connection_id: str,
    path: str,
    project_id: str,
    action: str,
    status_code: int,
    client_ip: str | None,
    user_id: str | None = None,
    detail: str | None = None,
) -> None:
    write_audit_log(
        session_factory,
        request_id=connection_id,
        event_type="websocket",
        action=action,
        method="WEBSOCKET",
        path=path,
        resource_id=project_id,
        detail=detail,
        status_code=status_code,
        client_ip=client_ip,
        user_id=user_id,
        duration_ms=0,
    )


def write_task_audit_log(
    session_factory: Callable[[], Session],
    *,
    correlation_id: str,
    task_name: str,
    project_id: str,
    action: str,
    status_code: int,
    user_id: str | None = None,
    detail: str | None = None,
) -> None:
    write_audit_log(
        session_factory,
        request_id=correlation_id,
        event_type="task",
        action=action,
        method="TASK",
        path=f"/internal/tasks/{task_name}",
        resource_id=project_id,
        detail=detail,
        status_code=status_code,
        client_ip=None,
        user_id=user_id,
        duration_ms=0,
    )
