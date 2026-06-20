"""FastAPI router exposing the V0 research harness (plan §5.1).

Endpoints (only these 5 are new; the rest of the API is unchanged):
  POST /api/research-harness/projects/{project_id}/start
  GET  /api/research-harness/projects/{project_id}/runs/{run_id}/status
  GET  /api/research-harness/projects/{project_id}/runs/{run_id}/timeline
  GET  /api/research-harness/projects/{project_id}/runs/{run_id}/files/{path:path}
  GET  /api/research-harness/projects

Design notes:
- ``start`` runs the full pipeline (10-15 min, live LLM) on a daemon thread and
  returns immediately — never blocks the HTTP request.
- ``files/{path}`` resolves the requested path and rejects anything that escapes
  the project workspace (path-traversal guard).
- Disk (timeline.jsonl, project.json, metrics.json) is the source of truth; the
  in-memory RunRegistry only adds the "is a thread alive right now?" signal.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from config.settings import settings
from schemas.research_harness import (
    FileContent,
    ProjectSummary,
    ReauditResponse,
    RunStatus,
    SaveDraftRequest,
    SaveDraftResponse,
    StartRequest,
    StartResponse,
    TimelineEntry,
)
from services.research_harness import pipeline, publish
from services.research_harness.run_registry import REGISTRY

logger = logging.getLogger("api.research_harness")

router = APIRouter(prefix="/api/research-harness", tags=["research-harness"])

_VALID_STEPS = set(pipeline.ALL_STEPS)


@router.get("/config")
def get_harness_config() -> dict:
    """Read-only LLM/sandbox config for the Settings page.

    Never exposes API keys — only model id + api base + sandbox backend, so the
    user can see *which* model a run will use without leaking credentials.
    """
    return {
        "llm_model": settings.llm_model or "(default)",
        "llm_writer_model": settings.llm_writer_model or settings.llm_model or "(default)",
        "llm_api_base": settings.llm_api_base or "(default)",
        "sandbox_backend": settings.sandbox_backend,
    }


def _resolve_status(project_id: str, run_id: str) -> RunStatus:
    """Combine registry liveness + disk timeline + metrics into one status view."""
    if project_id != run_id:
        # V0: run_id == project_id (one run per workspace). Keep the contract explicit.
        run_id = project_id

    meta = pipeline.read_project_meta(project_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Project not found")

    timeline = pipeline.read_timeline(project_id)
    entries = [
        TimelineEntry(
            step=e.get("step", ""),
            status=e.get("status", ""),
            ts=e.get("ts"),
            output_files=e.get("output_files", []),
        )
        for e in timeline
    ]

    done_steps = {e.step for e in entries if e.status == "done"}
    has_error = any(e.status == "error" for e in entries)

    if REGISTRY.is_running(run_id):
        status = "running"
    elif has_error:
        status = "error"
    elif set(pipeline.CORE_STEPS).issubset(done_steps):
        # Core research done. write/audit (paper layer) are best-effort and do not
        # gate "done" — a draft/audit failure must not make a finished run look partial.
        status = "done"
    elif done_steps:
        status = "partial"
    else:
        status = "pending"

    current_step = None
    if status == "running":
        executed = [e.step for e in entries]
        current_step = next((s for s in pipeline.ALL_STEPS if s not in executed), None)

    metrics = pipeline.load_metrics(project_id)
    execution_status = metrics.get("execution_status") if isinstance(metrics, dict) else None

    started_at = entries[0].ts if entries else meta.get("created_at")
    updated_at = entries[-1].ts if entries else meta.get("updated_at")

    return RunStatus(
        run_id=run_id,
        project_id=project_id,
        idea=meta.get("idea", ""),
        status=status,
        steps=entries,
        current_step=current_step,
        started_at=started_at,
        updated_at=updated_at,
        execution_status=execution_status,
    )


@router.post("/projects/{project_id}/start", response_model=StartResponse)
def start_run(project_id: str, payload: StartRequest) -> StartResponse:
    idea = payload.idea.strip()
    if not idea:
        raise HTTPException(status_code=400, detail="idea must not be empty")

    raw_steps = [s.strip() for s in payload.steps.split(",") if s.strip()]
    steps = None if raw_steps == ["all"] else raw_steps
    if steps is not None:
        unknown = [s for s in steps if s not in _VALID_STEPS]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown steps: {unknown}. Valid: {sorted(_VALID_STEPS)}",
            )

    # V0 contract: run_id == project_id (one run per workspace).
    run_id = project_id
    if REGISTRY.is_running(run_id):
        raise HTTPException(status_code=409, detail="A run is already in progress for this project")

    def _target() -> None:
        pipeline.run_pipeline(run_id, idea, steps=steps, portfolio_k=payload.portfolio_k)

    REGISTRY.spawn(run_id, project_id, idea, _target)
    logger.info(
        "Started background run %s for idea (len=%d) portfolio_k=%s",
        run_id, len(idea), payload.portfolio_k,
    )
    return StartResponse(run_id=run_id, project_id=project_id)


@router.put(
    "/projects/{project_id}/paper/draft",
    response_model=SaveDraftResponse,
)
def save_paper_draft(project_id: str, payload: SaveDraftRequest) -> SaveDraftResponse:
    """V3 (Session 11): save a human-edited ``paper/draft.md`` (TipTap editor).

    The path is fixed (no traversal surface); length is validated at the boundary.
    """
    if pipeline.read_project_meta(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        path = pipeline.save_paper_draft(project_id, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SaveDraftResponse(ok=True, chars=len(payload.content), path=str(path.name))


@router.post(
    "/projects/{project_id}/paper/reaudit",
    response_model=ReauditResponse,
)
def reaudit_paper(project_id: str) -> ReauditResponse:
    """V3 (Session 11): re-run the Auditor on the (human-edited) draft.

    The audit is pure-logic (no LLM), so it runs synchronously and returns the new
    gate + counts immediately — a human-added unsupported claim is marked
    ``[UNVERIFIED]`` without bypassing the gate. Non-fatal: never breaks a run.
    """
    if pipeline.read_project_meta(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    result = pipeline.reaudit_paper(project_id)
    return ReauditResponse(
        gate=bool(result.get("gate", False)),
        verified_count=result.get("verified_count"),
        unverified_count=result.get("unverified_count"),
        citation_unverified_count=result.get("citation_unverified_count"),
        omission_unverified_count=result.get("omission_unverified_count"),
        skipped=bool(result.get("skipped", False)),
        reason=result.get("reason"),
    )


@router.get("/projects/{project_id}/runs/{run_id}/status", response_model=RunStatus)
def get_status(project_id: str, run_id: str) -> RunStatus:
    return _resolve_status(project_id, run_id)


@router.get("/projects/{project_id}/runs/{run_id}/timeline", response_model=list[TimelineEntry])
def get_timeline(project_id: str, run_id: str) -> list[TimelineEntry]:
    _ = run_id  # V0: run_id == project_id; accepted for route symmetry.
    if pipeline.read_project_meta(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return [
        TimelineEntry(
            step=e.get("step", ""),
            status=e.get("status", ""),
            ts=e.get("ts"),
            output_files=e.get("output_files", []),
        )
        for e in pipeline.read_timeline(project_id)
    ]


@router.get("/projects/{project_id}/runs/{run_id}/files/{file_path:path}")
def get_file(project_id: str, run_id: str, file_path: str) -> PlainTextResponse:
    """Return raw workspace file content.

    Path-traversal guard: the resolved absolute path must remain inside the
    project workspace directory. ``..`` segments and absolute paths are rejected
    with 400; missing files return 404.
    """
    _ = run_id  # V0: run_id == project_id.
    base = pipeline.project_dir(project_id).resolve()
    if not base.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    # Reject obvious escape attempts early; the resolve() containment check below
    # is the authoritative guard.
    if not file_path or file_path != file_path.lstrip("/"):
        raise HTTPException(status_code=400, detail="Invalid file path")
    candidate = (base / file_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path escapes project workspace") from exc

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = candidate.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Binary file — return size only as text is not meaningful; surface as 415.
        raise HTTPException(status_code=415, detail="Binary file not supported") from None
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects() -> list[ProjectSummary]:
    return [
        ProjectSummary(
            project_id=p["project_id"],
            idea=p.get("idea", ""),
            status=p.get("status", "pending"),
            created_at=p.get("created_at"),
            updated_at=p.get("updated_at"),
            steps_done=p.get("steps_done", []),
            last_ts=p.get("last_ts"),
        )
        for p in pipeline.list_workspace_projects()
    ]


# --------------------------------------------------------------------------- #
# Session 14 — P3 publication surface (publish-bundle + deployment listing)
# --------------------------------------------------------------------------- #


@router.get("/projects/{project_id}/publish-bundle")
def get_publish_bundle(project_id: str, download: int = 0):
    """Return the publish-bundle manifest, or the .zip when ``?download=1``.

    Re-builds the bundle from the workspace (idempotent / deterministic) so the
    manifest always reflects current on-disk state. The honesty contract is
    enforced inside ``build_publish_bundle``: a gate-failed / negative artifact
    is returned with ``publishable: false`` + reason — the endpoint never
    overrides that. No user-controlled path (fixed bundle path → no traversal).
    """
    if pipeline.read_project_meta(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    manifest = publish.build_publish_bundle(project_id)

    if download:
        zip_path = pipeline.project_dir(project_id) / "publish_bundle" / "publish_bundle.zip"
        if not zip_path.is_file():
            raise HTTPException(status_code=404, detail="Bundle archive not available")
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"{project_id}_publish_bundle.zip",
        )
    return manifest


@router.get("/projects/{project_id}/deployments")
def list_deployments(project_id: str) -> dict:
    """Read-only deployment status for a project's publish-bundle.

    Lists the bundle + its publishable state. Does NOT auto-deploy, does NOT do
    venue adaptation — pure read-only status (plan §6 YAGNI).
    """
    if pipeline.read_project_meta(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    manifest_path = pipeline.project_dir(project_id) / "publish_bundle" / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = publish.build_publish_bundle(project_id)
    else:
        manifest = publish.build_publish_bundle(project_id)

    audit = manifest.get("audit_gate", {}) or {}
    verdict = manifest.get("honest_verdict", {}) or {}
    return {
        "project_id": project_id,
        "has_bundle": True,
        "publishable": manifest.get("publishable"),
        "publishable_reason": manifest.get("publishable_reason"),
        "honest_verdict": verdict.get("verdict"),
        "portfolio_verdict": manifest.get("portfolio_verdict"),
        "audit_gate": audit.get("gate"),
        "unverified_count": audit.get("unverified_count"),
        "bundle_files": manifest.get("bundle_files"),
        "manifest_path": "publish_bundle/manifest.json",
    }
