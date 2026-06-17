"""Pydantic schemas for the research-harness API (plan §5.1)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    idea: str = Field(..., min_length=3, description="Research idea to investigate")
    steps: str = Field("all", description='Comma-separated steps or "all"')


class StartResponse(BaseModel):
    run_id: str
    project_id: str


class TimelineEntry(BaseModel):
    step: str
    status: str
    ts: str | None = None
    output_files: list[str] = Field(default_factory=list)


class RunStatus(BaseModel):
    run_id: str
    project_id: str
    idea: str
    status: str  # running | done | error | partial | pending
    steps: list[TimelineEntry]
    current_step: str | None = None
    started_at: str | None = None
    updated_at: str | None = None
    execution_status: str | None = None  # from metrics.json (success / failed_after_repair / ...)


class ProjectSummary(BaseModel):
    project_id: str
    idea: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    steps_done: list[str] = Field(default_factory=list)
    last_ts: str | None = None


class FileContent(BaseModel):
    path: str
    content: str
    bytes: int
