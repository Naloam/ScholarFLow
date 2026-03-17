from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config.deps import get_db, get_identity, require_project_access
from config.db import SessionLocal
from schemas.common import IdResponse
from schemas.export import ExportRequest, ExportResult
from services.drafts.repository import list_drafts
from services.export.engine import export_latex, export_markdown, export_word
from services.export.repository import create_export, get_export, get_export_row, set_export_status
from services.projects.repository import set_project_status
from services.security.audit import write_task_audit_log
from services.security.auth import AuthIdentity
from services.workspace import project_root

router = APIRouter(
    prefix="/api/projects/{project_id}/export",
    tags=["export"],
    dependencies=[Depends(require_project_access)],
)


def _run_export_task(project_id: str, export_id: str, fmt: str, user_id: str | None) -> None:
    write_task_audit_log(
        SessionLocal,
        correlation_id=export_id,
        task_name="export.generate",
        project_id=project_id,
        action="running",
        status_code=102,
        user_id=user_id,
        detail=f"format={fmt}",
    )
    db = SessionLocal()
    try:
        set_project_status(db, project_id, "export")
        drafts = list_drafts(db, project_id)
        if not drafts:
            set_export_status(db, export_id, "failed", None)
            write_task_audit_log(
                SessionLocal,
                correlation_id=export_id,
                task_name="export.generate",
                project_id=project_id,
                action="failed",
                status_code=400,
                user_id=user_id,
                detail="no_draft_available",
            )
            return
        latest = sorted(drafts, key=lambda d: d.version, reverse=True)[0]
        if fmt == "markdown":
            path = export_markdown(project_id, latest.content, export_id)
        elif fmt == "latex":
            path = export_latex(project_id, latest.content, export_id)
        else:
            path = export_word(project_id, latest.content, export_id)
        set_export_status(db, export_id, "done", path)
        set_project_status(db, project_id, "done")
        write_task_audit_log(
            SessionLocal,
            correlation_id=export_id,
            task_name="export.generate",
            project_id=project_id,
            action="done",
            status_code=200,
            user_id=user_id,
            detail=f"format={fmt}",
        )
    except Exception as exc:
        set_export_status(db, export_id, "failed", None)
        write_task_audit_log(
            SessionLocal,
            correlation_id=export_id,
            task_name="export.generate",
            project_id=project_id,
            action="failed",
            status_code=500,
            user_id=user_id,
            detail=str(exc),
        )
    finally:
        db.close()


@router.post("", response_model=IdResponse)
def run_export(
    project_id: str,
    payload: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> IdResponse:
    drafts = list_drafts(db, project_id)
    if not drafts:
        raise HTTPException(status_code=400, detail="No draft available")
    fmt = payload.format.lower()
    if fmt not in {"markdown", "latex", "word", "docx"}:
        raise HTTPException(status_code=400, detail="Unsupported format")

    set_project_status(db, project_id, "export")
    export_id = create_export(db, project_id, fmt)

    write_task_audit_log(
        SessionLocal,
        correlation_id=export_id,
        task_name="export.generate",
        project_id=project_id,
        action="queued",
        status_code=202,
        user_id=identity.user_id if identity else None,
        detail=f"format={fmt}",
    )
    background_tasks.add_task(_run_export_task, project_id, export_id, fmt, identity.user_id if identity else None)

    return IdResponse(id=export_id)


@router.get("/{file_id}", response_model=ExportResult)
def get_export_status(
    project_id: str, file_id: str, db: Session = Depends(get_db)
) -> ExportResult:
    result = get_export(db, project_id, file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return result


@router.get("/{file_id}/download")
def download_export_file(
    project_id: str,
    file_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    row = get_export_row(db, project_id, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Export not found")
    if row.status != "done" or not row.file_path:
        raise HTTPException(status_code=409, detail="Export is not ready for download")

    file_path = Path(row.file_path).resolve()
    export_root = (project_root(project_id) / "exports").resolve()
    if export_root not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Export file missing")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )
