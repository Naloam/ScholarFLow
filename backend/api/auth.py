from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config.deps import get_db, require_identity
from config.settings import settings
from schemas.auth import AuthConfigResponse, AuthSessionRequest, AuthSessionResponse, UserRead
from services.security.auth import AuthIdentity, create_user_token
from services.users.repository import get_or_create_user_by_email, get_user_by_id

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigResponse)
def get_auth_config() -> AuthConfigResponse:
    return AuthConfigResponse(
        auth_required=settings.auth_required,
        session_enabled=bool(settings.auth_secret),
    )


@router.post("/session", response_model=AuthSessionResponse)
def create_session(payload: AuthSessionRequest, db: Session = Depends(get_db)) -> AuthSessionResponse:
    if not settings.auth_secret:
        raise HTTPException(status_code=503, detail="AUTH_SECRET is not configured")
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email")
    user = get_or_create_user_by_email(db, payload.email, payload.name, payload.role)
    token, expires_at = create_user_token(user.id, user.email)
    return AuthSessionResponse(access_token=token, expires_at=expires_at, user=user)


@router.get("/me", response_model=UserRead)
def get_current_user(
    identity: AuthIdentity = Depends(require_identity),
    db: Session = Depends(get_db),
) -> UserRead:
    user = get_user_by_id(db, identity.user_id or "")
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid session")
    return user
