from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.common import IdResponse
from schemas.export import ExportRequest, ExportResult
from config.deps import get_db
from services.drafts.repository import list_drafts
from services.export.engine import export_latex, export_markdown, export_word
from services.export.repository import create_export, get_export, set_export_status

router = APIRouter(prefix="/api/projects/{project_id}/export", tags=["export"])


@router.post("", response_model=IdResponse)
def run_export(
    project_id: str, payload: ExportRequest, db: Session = Depends(get_db)
) -> IdResponse:
    drafts = list_drafts(db, project_id)
    if not drafts:
        raise HTTPException(status_code=400, detail="No draft available")
    latest = sorted(drafts, key=lambda d: d.version, reverse=True)[0]
    fmt = payload.format.lower()
    if fmt not in {"markdown", "latex", "word", "docx"}:
        raise HTTPException(status_code=400, detail="Unsupported format")

    export_id = create_export(db, project_id, fmt)

    try:
        if fmt == "markdown":
            path = export_markdown(project_id, latest.content, export_id)
        elif fmt == "latex":
            path = export_latex(project_id, latest.content, export_id)
        else:
            path = export_word(project_id, latest.content, export_id)
        set_export_status(db, export_id, "done", path)
    except Exception as exc:
        set_export_status(db, export_id, "failed", None)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return IdResponse(id=export_id)


@router.get("/{file_id}", response_model=ExportResult)
def get_export_status(
    project_id: str, file_id: str, db: Session = Depends(get_db)
) -> ExportResult:
    result = get_export(db, file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return result
