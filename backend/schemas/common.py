from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class IdResponse(BaseModel):
    id: str
