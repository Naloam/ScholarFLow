from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

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
) -> None:
    row = AuditLog(
        id=f"audit_{uuid4().hex}",
        request_id=request_id,
        method=method,
        path=path,
        status_code=status_code,
        client_ip=client_ip,
        user_id=user_id,
        duration_ms=duration_ms,
    )
    db.add(row)
    db.commit()
