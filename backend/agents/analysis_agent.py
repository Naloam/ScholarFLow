from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from services.analysis.summary import build_summary
from config.db import SessionLocal


class AnalysisAgent(BaseAgent):
    name = "analysis"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = payload.get("project_id") or ""
        db = SessionLocal()
        try:
            summary = build_summary(db, project_id)
            return summary.model_dump()
        finally:
            db.close()
