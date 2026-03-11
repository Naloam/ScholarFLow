from datetime import datetime
from pydantic import BaseModel


class ExperimentRunRequest(BaseModel):
    code: str
    docker_image: str | None = None
    seed: int | None = None


class ExperimentResult(BaseModel):
    id: str | None = None
    project_id: str | None = None
    status: str
    logs: str | None = None
    outputs: dict | None = None
    docker_image: str | None = None
    seed: int | None = None
    created_at: datetime | None = None
