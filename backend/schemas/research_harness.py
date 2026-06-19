"""Pydantic schemas for the research-harness API (plan §5.1)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    idea: str = Field(..., min_length=3, description="Research idea to investigate")
    steps: str = Field("all", description='Comma-separated steps or "all"')
    portfolio_k: int | None = Field(
        default=None,
        description=(
            "V2.3 portfolio size: how many ranked hypothesis candidates to execute "
            "(default 3, hard cap 5). K=1 reproduces the legacy single-hypothesis run."
        ),
    )


class StartResponse(BaseModel):
    run_id: str
    project_id: str


class SaveDraftRequest(BaseModel):
    """V3 (Session 11): human-edited paper draft from the TipTap editor."""
    content: str = Field(..., min_length=1, description="Edited paper/draft.md markdown")


class SaveDraftResponse(BaseModel):
    ok: bool
    chars: int
    path: str


class ReauditResponse(BaseModel):
    """V3 (Session 11): result of re-running the Auditor on the edited draft."""
    gate: bool
    verified_count: int | None = None
    unverified_count: int | None = None
    citation_unverified_count: int | None = None
    omission_unverified_count: int | None = None
    skipped: bool = False
    reason: str | None = None


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
