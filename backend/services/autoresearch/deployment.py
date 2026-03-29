from __future__ import annotations

from datetime import datetime

from schemas.autoresearch import (
    AutoResearchDeploymentListRead,
    AutoResearchDeploymentPublicationRead,
    AutoResearchDeploymentRead,
    AutoResearchDeploymentSummaryRead,
    AutoResearchPublicationManifestRead,
)
from schemas.projects import ProjectListItem
from services.autoresearch.repository import list_runs
from services.autoresearch.review_publish import build_publication_manifest


def _project_publications(project: ProjectListItem) -> list[AutoResearchPublicationManifestRead]:
    publications: list[AutoResearchPublicationManifestRead] = []
    for run in list_runs(project.id):
        publication = build_publication_manifest(project.id, run.id)
        if publication is None:
            continue
        publications.append(
            publication.model_copy(
                update={
                    "project_title": project.title,
                }
            )
        )
    return publications


def _deployment_publications(
    projects: list[ProjectListItem],
) -> dict[str, tuple[str, list[AutoResearchDeploymentPublicationRead]]]:
    grouped: dict[str, tuple[str, list[AutoResearchDeploymentPublicationRead]]] = {}
    for project in projects:
        for publication in _project_publications(project):
            for deployment in publication.deployments:
                entry = AutoResearchDeploymentPublicationRead(
                    deployment_id=deployment.deployment_id,
                    listed_at=deployment.listed_at,
                    publication=publication,
                )
                label, publications = grouped.get(
                    deployment.deployment_id,
                    (deployment.label, []),
                )
                publications.append(entry)
                grouped[deployment.deployment_id] = (deployment.label or label, publications)
    for deployment_id, (label, publications) in list(grouped.items()):
        grouped[deployment_id] = (
            label,
            sorted(
                publications,
                key=lambda item: (item.listed_at, item.publication.updated_at),
                reverse=True,
            ),
        )
    return grouped


def _deployment_summary(
    deployment_id: str,
    label: str,
    publications: list[AutoResearchDeploymentPublicationRead],
) -> AutoResearchDeploymentSummaryRead:
    created_at = min(item.listed_at for item in publications)
    updated_at = max(item.listed_at for item in publications)
    latest = publications[0].publication if publications else None
    return AutoResearchDeploymentSummaryRead(
        deployment_id=deployment_id,
        label=label,
        created_at=created_at,
        updated_at=updated_at,
        publication_count=len(publications),
        project_count=len({item.publication.project_id for item in publications}),
        final_publish_ready_count=sum(
            1 for item in publications if item.publication.final_publish_ready
        ),
        latest_publication_id=latest.publication_id if latest is not None else None,
        latest_run_id=latest.run_id if latest is not None else None,
    )


def build_deployment_list(projects: list[ProjectListItem]) -> AutoResearchDeploymentListRead:
    grouped = _deployment_publications(projects)
    summaries = [
        _deployment_summary(deployment_id, label, publications)
        for deployment_id, (label, publications) in grouped.items()
    ]
    summaries.sort(key=lambda item: (item.updated_at, item.deployment_id), reverse=True)
    return AutoResearchDeploymentListRead(
        deployment_count=len(summaries),
        publication_count=sum(item.publication_count for item in summaries),
        deployments=summaries,
    )


def build_deployment_detail(
    projects: list[ProjectListItem],
    deployment_id: str,
) -> AutoResearchDeploymentRead | None:
    grouped = _deployment_publications(projects)
    resolved = grouped.get(deployment_id)
    if resolved is None:
        return None
    label, publications = resolved
    summary = _deployment_summary(deployment_id, label, publications)
    return AutoResearchDeploymentRead(
        deployment_id=summary.deployment_id,
        label=summary.label,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        publication_count=summary.publication_count,
        project_count=summary.project_count,
        final_publish_ready_count=summary.final_publish_ready_count,
        latest_publication_id=summary.latest_publication_id,
        latest_run_id=summary.latest_run_id,
        publications=publications,
    )
