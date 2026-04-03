from __future__ import annotations

import re

from sqlalchemy.orm import Session

from schemas.autoresearch import (
    AutoResearchProjectFlowContextRead,
    AutoResearchProjectFlowDraftRead,
    AutoResearchProjectFlowEvidenceRead,
    AutoResearchProjectFlowReviewRead,
)
from services.drafts.repository import get_latest_draft
from services.evidence.repository import list_evidence_items
from services.projects.repository import get_project
from services.review.repository import list_reviews
from services.templates.repository import get_template_content


_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", flags=re.M)
_HTTP_ENDPOINT_PATTERN = re.compile(
    r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_./{}-]+)"
)
_API_PATH_PATTERN = re.compile(r"(/api/[A-Za-z0-9_./{}-]+)")


def _excerpt(text: str | None, *, limit: int = 360) -> str | None:
    collapsed = " ".join((text or "").split())
    if not collapsed:
        return None
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 3)].rstrip() + "..."


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = " ".join(item.split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _template_sections(template: str | None) -> list[str]:
    if not template:
        return []
    return _dedupe(_HEADING_PATTERN.findall(template))[:8]


def _api_surface_hints(*texts: str | None) -> list[str]:
    hints: list[str] = []
    for text in texts:
        if not text:
            continue
        hints.extend(match.group(1) for match in _HTTP_ENDPOINT_PATTERN.finditer(text))
        hints.extend(match.group(1) for match in _API_PATH_PATTERN.finditer(text))
    return _dedupe(hints)[:8]


def gather_project_flow_context(
    db: Session,
    project_id: str,
) -> AutoResearchProjectFlowContextRead | None:
    project = get_project(db, project_id)
    if project is None:
        return None

    template = get_template_content(db, project.template_id)
    latest_draft = get_latest_draft(db, project_id)
    evidence_items = list_evidence_items(db, project_id)
    reviews = list_reviews(db, project_id)
    latest_review = reviews[0] if reviews else None

    draft_claims = [
        item.claim
        for item in (latest_draft.claims if latest_draft is not None else [])
        if item.claim
    ]
    evidence_claims = _dedupe(
        [item.claim_text for item in evidence_items if item.claim_text]
    )
    evidence_snippets = _dedupe(
        [item.snippet for item in evidence_items if item.snippet]
    )[:6]
    review_suggestions = _dedupe(
        latest_review.suggestions if latest_review is not None else []
    )[:6]
    template_sections = _template_sections(template)
    api_hints = _api_surface_hints(
        template,
        latest_draft.content if latest_draft is not None else None,
        "\n".join(evidence_snippets),
        "\n".join(review_suggestions),
    )

    flow_constraints: list[str] = []
    if template_sections:
        flow_constraints.append(
            f"Follow the persisted project template structure, especially sections: {', '.join(template_sections[:4])}."
        )
    if latest_draft is not None:
        flow_constraints.append(
            f"Stay aligned with project draft v{latest_draft.version}, which already frames the work as `{latest_draft.section or 'general'}`."
        )
    if draft_claims:
        flow_constraints.append(
            f"Carry forward the project's existing draft claims where they remain consistent with executed evidence: {'; '.join(draft_claims[:3])}."
        )
    if evidence_claims:
        flow_constraints.append(
            f"Use the project's saved evidence trail, including claims such as: {'; '.join(evidence_claims[:3])}."
        )
    if review_suggestions:
        flow_constraints.append(
            f"Address the latest project review guidance, especially: {'; '.join(review_suggestions[:3])}."
        )
    if api_hints:
        flow_constraints.append(
            f"Keep project API or workflow anchors visible in the manuscript, including: {', '.join(api_hints[:4])}."
        )
    if not flow_constraints:
        flow_constraints.append(
            "No prior project template, draft, evidence, or review state was available, so the run should document only executed benchmark evidence."
        )

    summary = " ".join(flow_constraints)
    return AutoResearchProjectFlowContextRead(
        generated_at=project.updated_at or project.created_at,
        project_title=project.title,
        project_topic=project.topic,
        project_status=project.status,
        template_id=project.template_id,
        template_excerpt=_excerpt(template),
        template_sections=template_sections,
        draft=(
            AutoResearchProjectFlowDraftRead(
                version=latest_draft.version,
                section=latest_draft.section,
                excerpt=_excerpt(latest_draft.content),
                claim_count=len(draft_claims),
                claims=draft_claims[:6],
            )
            if latest_draft is not None
            else None
        ),
        evidence=(
            AutoResearchProjectFlowEvidenceRead(
                claim_count=len(evidence_claims),
                claims=evidence_claims[:6],
                snippets=evidence_snippets,
            )
            if evidence_claims or evidence_snippets
            else None
        ),
        review=(
            AutoResearchProjectFlowReviewRead(
                latest_draft_version=latest_review.draft_version,
                suggestion_count=len(review_suggestions),
                suggestions=review_suggestions,
            )
            if latest_review is not None
            else None
        ),
        api_surface_hints=api_hints,
        flow_constraints=flow_constraints,
        summary=summary,
    )
