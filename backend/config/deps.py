from collections.abc import Generator

from fastapi import Depends, HTTPException, Request

from config.db import SessionLocal
from services.security.auth import AuthIdentity


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_identity(request: Request) -> AuthIdentity | None:
    return getattr(request.state, "identity", None)


def require_identity(identity: AuthIdentity | None = Depends(get_identity)) -> AuthIdentity:
    if identity is None or identity.user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return identity
