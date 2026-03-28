from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class UserRead(BaseModel):
    id: str
    email: str
    name: str | None = None
    role: str
    created_at: datetime | None = None


class AuthSessionRequest(BaseModel):
    email: str
    name: str | None = None
    role: Literal["student", "tutor"] | None = None


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


class AuthConfigResponse(BaseModel):
    auth_required: bool
    api_protected: bool
    session_enabled: bool
