from fastapi import APIRouter

from schemas.common import IdResponse
from schemas.experiments import ExperimentResult, ExperimentRunRequest

router = APIRouter(prefix="/api/projects/{project_id}/experiments", tags=["experiments"])


@router.post("/run", response_model=IdResponse)
def run_experiment(project_id: str, payload: ExperimentRunRequest) -> IdResponse:
    return IdResponse(id="exp_todo")


@router.get("/{experiment_id}", response_model=ExperimentResult)
def get_experiment(project_id: str, experiment_id: str) -> ExperimentResult:
    return ExperimentResult(id=experiment_id, project_id=project_id, status="todo")
