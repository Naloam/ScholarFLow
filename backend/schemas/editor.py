from pydantic import BaseModel


class EditRequest(BaseModel):
    content: str
    style: str | None = None


class EditResponse(BaseModel):
    content: str
