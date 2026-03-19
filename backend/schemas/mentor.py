from datetime import datetime

from pydantic import BaseModel, Field


class MentorAccessCreate(BaseModel):
    email: str
    name: str | None = None


class MentorAccessRead(BaseModel):
    id: str
    project_id: str
    mentor_user_id: str | None = None
    mentor_email: str
    mentor_name: str | None = None
    invited_by_user_id: str
    status: str
    created_at: datetime | None = None


class MentorFeedbackCreate(BaseModel):
    draft_version: int | None = None
    summary: str = Field(min_length=4, max_length=2000)
    strengths: str = Field(min_length=4, max_length=4000)
    concerns: str = Field(min_length=4, max_length=4000)
    next_steps: str = Field(min_length=4, max_length=4000)


class MentorFeedbackRead(BaseModel):
    id: str
    project_id: str
    mentor_user_id: str
    mentor_email: str
    mentor_name: str | None = None
    draft_version: int | None = None
    summary: str
    strengths: str
    concerns: str
    next_steps: str
    created_at: datetime | None = None
