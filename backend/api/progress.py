from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from config.db import SessionLocal
from config.settings import settings
from services.projects.repository import get_project_owner_id
from services.projects.progress import build_progress_snapshot
from services.security.audit import write_websocket_audit_log
from services.security.auth import authenticate_token, extract_api_token

router = APIRouter(tags=["progress"])


@router.websocket("/ws/projects/{project_id}/progress")
async def project_progress(websocket: WebSocket, project_id: str) -> None:
    connection_id = f"ws_{uuid4().hex}"
    path = websocket.url.path
    client_ip = websocket.client.host if websocket.client else None
    token = extract_api_token(
        websocket.headers.get("authorization"),
        websocket.query_params.get("token"),
    )
    identity = authenticate_token(token)
    if (settings.api_token or settings.auth_required) and identity is None:
        write_websocket_audit_log(
            SessionLocal,
            connection_id=connection_id,
            path=path,
            project_id=project_id,
            action="rejected",
            status_code=4401,
            client_ip=client_ip,
            detail="authentication_required",
        )
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        owner_id = get_project_owner_id(db, project_id)
    finally:
        db.close()
    if owner_id and (identity is None or identity.user_id is None):
        write_websocket_audit_log(
            SessionLocal,
            connection_id=connection_id,
            path=path,
            project_id=project_id,
            action="rejected",
            status_code=4401,
            client_ip=client_ip,
            detail="project_authentication_required",
        )
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.close(code=4401)
        return
    if identity is not None and identity.user_id is not None and owner_id and owner_id != identity.user_id:
        write_websocket_audit_log(
            SessionLocal,
            connection_id=connection_id,
            path=path,
            project_id=project_id,
            action="rejected",
            status_code=4403,
            client_ip=client_ip,
            user_id=identity.user_id,
            detail="forbidden_project_access",
        )
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.close(code=4403)
        return
    await websocket.accept()
    write_websocket_audit_log(
        SessionLocal,
        connection_id=connection_id,
        path=path,
        project_id=project_id,
        action="connected",
        status_code=101,
        client_ip=client_ip,
        user_id=identity.user_id if identity else None,
    )
    try:
        while True:
            db = SessionLocal()
            try:
                snapshot = build_progress_snapshot(db, project_id)
            finally:
                db.close()

            if snapshot is None:
                write_websocket_audit_log(
                    SessionLocal,
                    connection_id=connection_id,
                    path=path,
                    project_id=project_id,
                    action="closed",
                    status_code=4404,
                    client_ip=client_ip,
                    user_id=identity.user_id if identity else None,
                    detail="project_not_found",
                )
                await websocket.send_json({"error": "project_not_found", "project_id": project_id})
                await websocket.close(code=4404)
                return

            await websocket.send_json(snapshot)
            await asyncio.sleep(2)
    except WebSocketDisconnect as exc:
        write_websocket_audit_log(
            SessionLocal,
            connection_id=connection_id,
            path=path,
            project_id=project_id,
            action="disconnected",
            status_code=exc.code,
            client_ip=client_ip,
            user_id=identity.user_id if identity else None,
        )
        return
