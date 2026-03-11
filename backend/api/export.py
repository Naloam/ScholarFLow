from fastapi import APIRouter

from schemas.common import IdResponse
from schemas.export import ExportRequest, ExportResult

router = APIRouter(prefix="/api/projects/{project_id}/export", tags=["export"])


@router.post("", response_model=IdResponse)
def run_export(project_id: str, payload: ExportRequest) -> IdResponse:
    return IdResponse(id="export_todo")


@router.get("/{file_id}", response_model=ExportResult)
def get_export(project_id: str, file_id: str) -> ExportResult:
    return ExportResult(file_id=file_id, status="todo")
