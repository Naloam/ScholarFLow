from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.sandbox_agent import SandboxAgent
from config.deps import get_db, require_project_access
from config.db import SessionLocal
from schemas.common import IdResponse
from schemas.experiments import ExperimentResult, ExperimentRunRequest
from services.experiments.repository import (
    create_experiment,
    get_experiment as get_experiment_db,
    update_experiment,
)

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
) -> IdResponse:
    exp_id = create_experiment(db, project_id, payload.code, payload.docker_image, payload.seed)

    def _run() -> None:
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
        except Exception as exc:
            update_experiment(local, exp_id, "failed", str(exc), {"error": str(exc)})
        finally:
            local.close()

    background_tasks.add_task(_run)
    return IdResponse(id=exp_id)


@router.get("/{experiment_id}", response_model=ExperimentResult)
def get_experiment(project_id: str, experiment_id: str, db: Session = Depends(get_db)) -> ExperimentResult:
    result = get_experiment_db(db, experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result
