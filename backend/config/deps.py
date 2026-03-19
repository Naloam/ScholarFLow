from collections.abc import Generator

from fastapi import Depends, HTTPException, Request

from config.db import SessionLocal
from models.project import Project
from services.mentor.repository import has_mentor_access
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


def require_project_access(
    project_id: str,
    request: Request,
    db=Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.user_id:
        return
    if identity is None or identity.user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if project.user_id and project.user_id != identity.user_id:
        if request.method.upper() in {"GET", "HEAD"} and has_mentor_access(
            db,
            project_id=project_id,
            user_id=identity.user_id,
            email=identity.email,
        ):
            return
        raise HTTPException(status_code=403, detail="Forbidden")


def require_project_owner(
    project_id: str,
    db=Depends(get_db),
    identity: AuthIdentity = Depends(require_identity),
) -> AuthIdentity:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id and project.user_id != identity.user_id:
        raise HTTPException(status_code=403, detail="Project owner required")
    return identity


def require_project_mentor(
    project_id: str,
    db=Depends(get_db),
    identity: AuthIdentity = Depends(require_identity),
) -> AuthIdentity:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id and project.user_id == identity.user_id:
        raise HTTPException(status_code=403, detail="Project owner cannot submit mentor feedback")
    if has_mentor_access(
        db,
        project_id=project_id,
        user_id=identity.user_id,
        email=identity.email,
    ):
        return identity
    raise HTTPException(status_code=403, detail="Mentor access required")
