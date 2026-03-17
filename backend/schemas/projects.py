from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    user_id: str | None = None
    title: str
    topic: str | None = None
    template_id: str | None = None
    status: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: str | None = None
    topic: str | None = None
    template_id: str | None = None
    status: str | None = None


class ProjectRead(ProjectBase):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectListItem(ProjectRead):
    access_mode: Literal["owner", "mentor"]


class ProjectStatus(BaseModel):
    status: str
    phase: str | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    message: str | None = None
