from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from models.task_run import TaskRun


def create_task(db: Session) -> str:
    task_id = f"task_{uuid4().hex}"
    row = TaskRun(id=task_id, status="queued", detail=None)
    db.add(row)
    db.commit()
    return task_id


def set_task(db: Session, task_id: str, status: str, detail: str | None = None) -> None:
    row = db.get(TaskRun, task_id)
    if row is None:
        row = TaskRun(id=task_id, status=status, detail=detail)
        db.add(row)
    else:
        row.status = status
        row.detail = detail
        db.add(row)
    db.commit()


def get_task(db: Session, task_id: str) -> TaskRun | None:
    return db.get(TaskRun, task_id)
