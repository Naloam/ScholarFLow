from pydantic import BaseModel


class TutorRequest(BaseModel):
    project_id: str | None = None
    draft_version: int | None = None
    stage: str | None = None
    topic: str | None = None
    context: str | None = None


class TutorResponse(BaseModel):
    stage: str
    guidance: str
