from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.sandbox_agent import SandboxAgent
from config.deps import get_db, get_identity, require_project_access
from config.db import SessionLocal
from schemas.common import IdResponse
from schemas.experiments import ExperimentResult, ExperimentRunRequest
from services.experiments.repository import (
    create_experiment,
    get_experiment as get_experiment_db,
    update_experiment,
)
from services.security.audit import write_task_audit_log
from services.security.auth import AuthIdentity

router = APIRouter(
    prefix="/api/projects/{project_id}/experiments",
    tags=["experiments"],
    dependencies=[Depends(require_project_access)],
)


@router.post("/run", response_model=IdResponse)
def run_experiment(
    project_id: str,
    payload: ExperimentRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> IdResponse:
    exp_id = create_experiment(db, project_id, payload.code, payload.docker_image, payload.seed)

    def _run() -> None:
        write_task_audit_log(
            SessionLocal,
            correlation_id=exp_id,
            task_name="experiments.run",
            project_id=project_id,
            action="running",
            status_code=102,
            user_id=identity.user_id if identity else None,
            detail=f"docker_image={payload.docker_image}",
        )
        local = SessionLocal()
        try:
            update_experiment(local, exp_id, "running")
            agent = SandboxAgent()
            result = agent.run(
                {
                    "project_id": project_id,
                    "code": payload.code,
                    "docker_image": payload.docker_image,
                }
            )
            update_experiment(local, exp_id, "done", result.get("logs"), result.get("outputs"))
            write_task_audit_log(
                SessionLocal,
                correlation_id=exp_id,
                task_name="experiments.run",
                project_id=project_id,
                action="done",
                status_code=200,
                user_id=identity.user_id if identity else None,
                detail=f"docker_image={payload.docker_image}",
            )
        except Exception as exc:
            update_experiment(local, exp_id, "failed", str(exc), {"error": str(exc)})
            write_task_audit_log(
                SessionLocal,
                correlation_id=exp_id,
                task_name="experiments.run",
                project_id=project_id,
                action="failed",
                status_code=500,
                user_id=identity.user_id if identity else None,
                detail=str(exc),
            )
        finally:
            local.close()

    write_task_audit_log(
        SessionLocal,
        correlation_id=exp_id,
        task_name="experiments.run",
        project_id=project_id,
        action="queued",
        status_code=202,
        user_id=identity.user_id if identity else None,
        detail=f"docker_image={payload.docker_image}",
    )
    background_tasks.add_task(_run)
    return IdResponse(id=exp_id)


@router.get("/{experiment_id}", response_model=ExperimentResult)
def get_experiment(project_id: str, experiment_id: str, db: Session = Depends(get_db)) -> ExperimentResult:
    result = get_experiment_db(db, experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result
