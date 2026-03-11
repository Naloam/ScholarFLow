from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class IdResponse(BaseModel):
    id: str


class TaskStatusResponse(BaseModel):
    status: str
    detail: str | None = None
