from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.common import IdResponse
from schemas.export import ExportRequest, ExportResult
from config.deps import get_db
from config.db import SessionLocal
from services.drafts.repository import list_drafts
from services.export.engine import export_latex, export_markdown, export_word
from services.export.repository import create_export, get_export, set_export_status
from services.projects.repository import set_project_status

router = APIRouter(prefix="/api/projects/{project_id}/export", tags=["export"])


def _run_export_task(project_id: str, export_id: str, fmt: str) -> None:
    db = SessionLocal()
    try:
        set_project_status(db, project_id, "export")
        drafts = list_drafts(db, project_id)
        if not drafts:
            set_export_status(db, export_id, "failed", None)
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
    except Exception:
        set_export_status(db, export_id, "failed", None)
    finally:
        db.close()


@router.post("", response_model=IdResponse)
def run_export(
    project_id: str,
    payload: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> IdResponse:
    drafts = list_drafts(db, project_id)
    if not drafts:
        raise HTTPException(status_code=400, detail="No draft available")
    fmt = payload.format.lower()
    if fmt not in {"markdown", "latex", "word", "docx"}:
        raise HTTPException(status_code=400, detail="Unsupported format")

    set_project_status(db, project_id, "export")
    export_id = create_export(db, project_id, fmt)

    background_tasks.add_task(_run_export_task, project_id, export_id, fmt)

    return IdResponse(id=export_id)


@router.get("/{file_id}", response_model=ExportResult)
def get_export_status(
    project_id: str, file_id: str, db: Session = Depends(get_db)
) -> ExportResult:
    result = get_export(db, file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return result
