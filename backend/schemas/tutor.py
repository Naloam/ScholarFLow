from pydantic import BaseModel


class TutorRequest(BaseModel):
    stage: str | None = None
    topic: str | None = None
    context: str | None = None


class TutorResponse(BaseModel):
    stage: str
    guidance: str
