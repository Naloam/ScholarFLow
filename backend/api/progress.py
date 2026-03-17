from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from config.db import SessionLocal
from config.settings import settings
from services.projects.repository import get_project_owner_id
from services.projects.progress import build_progress_snapshot
from services.security.auth import authenticate_token, extract_api_token

router = APIRouter(tags=["progress"])


@router.websocket("/ws/projects/{project_id}/progress")
async def project_progress(websocket: WebSocket, project_id: str) -> None:
    token = extract_api_token(
        websocket.headers.get("authorization"),
        websocket.query_params.get("token"),
    )
    identity = authenticate_token(token)
    if (settings.api_token or settings.auth_required) and identity is None:
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        owner_id = get_project_owner_id(db, project_id)
    finally:
        db.close()
    if owner_id and (identity is None or identity.user_id is None):
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.close(code=4401)
        return
    if identity is not None and identity.user_id is not None and owner_id and owner_id != identity.user_id:
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.close(code=4403)
        return
    await websocket.accept()
    try:
        while True:
            db = SessionLocal()
            try:
                snapshot = build_progress_snapshot(db, project_id)
            finally:
                db.close()

            if snapshot is None:
                await websocket.send_json({"error": "project_not_found", "project_id": project_id})
                await websocket.close(code=4404)
                return

            await websocket.send_json(snapshot)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
