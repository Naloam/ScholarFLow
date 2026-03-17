from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.deps import get_db, get_identity, require_identity, require_project_access
from fastapi import HTTPException

from schemas.common import IdResponse
from schemas.projects import ProjectCreate, ProjectListItem, ProjectRead, ProjectStatus, ProjectUpdate
from services.security.auth import AuthIdentity
from services.projects.repository import (
    create_project as create_project_db,
    get_project as get_project_db,
    list_projects_for_user,
    update_project as update_project_db,
)
from services.projects.status import get_status_info, validate_status

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=IdResponse)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> IdResponse:
    effective_payload = payload
    if identity is not None and identity.user_id is not None:
        if payload.user_id and payload.user_id != identity.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        effective_payload = payload.model_copy(update={"user_id": identity.user_id})
    try:
        project = create_project_db(db, effective_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IdResponse(id=project.id)


@router.get("", response_model=list[ProjectListItem])
def list_projects(
    db: Session = Depends(get_db),
    identity: AuthIdentity = Depends(require_identity),
) -> list[ProjectListItem]:
    return list_projects_for_user(
        db,
        user_id=identity.user_id or "",
        email=identity.email,
    )


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    _access: None = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> ProjectRead:
    project = get_project_db(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    _access: None = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> ProjectRead:
    try:
        project = update_project_db(db, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/status", response_model=ProjectStatus)
def get_project_status(
    project_id: str,
    _access: None = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> ProjectStatus:
    project = get_project_db(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    status = validate_status(project.status)
    info = get_status_info(status)
    return ProjectStatus(status=status, phase=info.phase, progress=info.progress)
