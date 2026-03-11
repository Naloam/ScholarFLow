from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config.deps import get_db
from schemas.common import TaskStatusResponse
from services.tasks import get_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str, db: Session = Depends(get_db)) -> TaskStatusResponse:
    row = get_task(db, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(status=row.status, detail=row.detail)
