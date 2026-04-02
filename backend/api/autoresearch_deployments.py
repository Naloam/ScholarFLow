from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from config.deps import get_db, get_identity
from config.settings import settings
from schemas.autoresearch import (
    AutoResearchPublishBundleKind,
    AutoResearchDeploymentListRead,
    AutoResearchDeploymentRead,
    TaskFamily,
)
from services.autoresearch.deployment import (
    build_deployment_detail,
    build_deployment_list,
)
from services.projects.repository import list_open_projects, list_projects_for_user
from services.security.auth import AuthIdentity


router = APIRouter(prefix="/api/auto-research/deployments", tags=["auto-research-deployments"])


def _accessible_projects(
    *,
    db: Session,
    identity: AuthIdentity | None,
):
    if identity is None or identity.user_id is None:
        if settings.auth_required or settings.api_token:
            raise HTTPException(status_code=401, detail="Authentication required")
        return list_open_projects(db)
    return list_projects_for_user(
        db,
        user_id=identity.user_id,
        email=identity.email,
    )


@router.get("", response_model=AutoResearchDeploymentListRead)
def list_auto_research_deployments(
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> AutoResearchDeploymentListRead:
    return build_deployment_list(_accessible_projects(db=db, identity=identity))


@router.get("/{deployment_id}", response_model=AutoResearchDeploymentRead)
def get_auto_research_deployment(
    deployment_id: str,
    search: str | None = Query(default=None),
    final_publish_ready: bool | None = Query(default=None),
    bundle_kind: AutoResearchPublishBundleKind | None = Query(default=None),
    task_family: TaskFamily | None = Query(default=None),
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> AutoResearchDeploymentRead:
    deployment = build_deployment_detail(
        _accessible_projects(db=db, identity=identity),
        deployment_id,
        search=search,
        final_publish_ready=final_publish_ready,
        bundle_kind=bundle_kind,
        task_family=task_family,
    )
    if deployment is None:
        raise HTTPException(status_code=404, detail="Auto research deployment not found")
    return deployment
