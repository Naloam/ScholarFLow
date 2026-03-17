from datetime import datetime

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


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


class AuthConfigResponse(BaseModel):
    auth_required: bool
    session_enabled: bool
