from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config.db import SessionLocal
from services.projects.progress import build_progress_snapshot

router = APIRouter(tags=["progress"])


@router.websocket("/ws/projects/{project_id}/progress")
async def project_progress(websocket: WebSocket, project_id: str) -> None:
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
