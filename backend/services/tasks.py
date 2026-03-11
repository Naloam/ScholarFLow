from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from uuid import uuid4


@dataclass
class TaskStatus:
    status: str
    detail: str | None = None


class TaskStore:
    def __init__(self) -> None:
        self._tasks: Dict[str, TaskStatus] = {}

    def create(self) -> str:
        task_id = f"task_{uuid4().hex}"
        self._tasks[task_id] = TaskStatus(status="queued")
        return task_id

    def set(self, task_id: str, status: str, detail: str | None = None) -> None:
        self._tasks[task_id] = TaskStatus(status=status, detail=detail)

    def get(self, task_id: str) -> TaskStatus | None:
        return self._tasks.get(task_id)


task_store = TaskStore()
