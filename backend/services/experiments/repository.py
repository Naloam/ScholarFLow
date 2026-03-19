from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.experiment_run import ExperimentRun
from schemas.experiments import ExperimentResult


def create_experiment(
    db: Session, project_id: str, code: str, docker_image: str | None, seed: int | None
) -> str:
    row = ExperimentRun(
        id=f"exp_{uuid4().hex}",
        project_id=project_id,
        code=code,
        status="queued",
        docker_image=docker_image,
        seed=seed,
    )
    db.add(row)
    db.commit()
    return row.id


def update_experiment(
    db: Session,
    experiment_id: str,
    status: str,
    logs: str | None = None,
    outputs: dict | None = None,
) -> None:
    row = db.execute(select(ExperimentRun).where(ExperimentRun.id == experiment_id)).scalar_one_or_none()
    if row is None:
        return
    row.status = status
    row.logs = logs
    row.outputs = outputs
    db.commit()


def get_experiment(db: Session, experiment_id: str) -> ExperimentResult | None:
    row = db.execute(select(ExperimentRun).where(ExperimentRun.id == experiment_id)).scalar_one_or_none()
    if row is None:
        return None
    return ExperimentResult(
        id=row.id,
        project_id=row.project_id,
        status=row.status,
        logs=row.logs,
        outputs=row.outputs,
        docker_image=row.docker_image,
        seed=row.seed,
        created_at=row.created_at,
    )
