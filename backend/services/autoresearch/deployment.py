from __future__ import annotations

from datetime import datetime
import re

from schemas.autoresearch import (
    AutoResearchDeploymentFiltersRead,
    AutoResearchDeploymentListRead,
    AutoResearchDeploymentPublicationRead,
    AutoResearchDeploymentRead,
    AutoResearchPublishBundleKind,
    AutoResearchDeploymentSummaryRead,
    AutoResearchPublicationManifestRead,
    TaskFamily,
)
from schemas.projects import ProjectListItem
from services.autoresearch.repository import list_runs
from services.autoresearch.review_publish import build_publication_manifest


def _normalize_search(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


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


def _publication_matches_filters(
    item: AutoResearchDeploymentPublicationRead,
    *,
    search: str | None = None,
    final_publish_ready: bool | None = None,
    bundle_kind: AutoResearchPublishBundleKind | None = None,
    task_family: TaskFamily | None = None,
) -> bool:
    publication = item.publication
    if final_publish_ready is not None and publication.final_publish_ready != final_publish_ready:
        return False
    if bundle_kind is not None and publication.bundle_kind != bundle_kind:
        return False
    if task_family is not None and publication.task_family != task_family:
        return False
    normalized_search = _normalize_search(search)
    if normalized_search:
        haystack = _normalize_search(
            " ".join(
                filter(
                    None,
                    [
                        publication.publication_id,
                        publication.project_id,
                        publication.project_title,
                        publication.run_id,
                        publication.topic,
                        publication.paper_title,
                        publication.benchmark_name,
                        publication.task_family,
                    ],
                )
            )
        )
        if normalized_search not in haystack:
            return False
    return True


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
    *,
    search: str | None = None,
    final_publish_ready: bool | None = None,
    bundle_kind: AutoResearchPublishBundleKind | None = None,
    task_family: TaskFamily | None = None,
) -> AutoResearchDeploymentRead | None:
    grouped = _deployment_publications(projects)
    resolved = grouped.get(deployment_id)
    if resolved is None:
        return None
    label, publications = resolved
    filtered_publications = [
        item
        for item in publications
        if _publication_matches_filters(
            item,
            search=search,
            final_publish_ready=final_publish_ready,
            bundle_kind=bundle_kind,
            task_family=task_family,
        )
    ]
    summary = _deployment_summary(deployment_id, label, publications)
    return AutoResearchDeploymentRead(
        deployment_id=summary.deployment_id,
        label=summary.label,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        publication_count=summary.publication_count,
        filtered_publication_count=len(filtered_publications),
        project_count=summary.project_count,
        final_publish_ready_count=summary.final_publish_ready_count,
        latest_publication_id=summary.latest_publication_id,
        latest_run_id=summary.latest_run_id,
        filters=AutoResearchDeploymentFiltersRead(
            search=search.strip() if search and search.strip() else None,
            final_publish_ready=final_publish_ready,
            bundle_kind=bundle_kind,
            task_family=task_family,
        ),
        publications=filtered_publications,
    )
