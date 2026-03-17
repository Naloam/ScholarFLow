from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.evidence_agent import EvidenceAgent
from agents.writing_agent import WritingAgent
from config.deps import get_db, get_identity, require_project_access
from schemas.common import IdResponse
from schemas.drafts import DraftCreate, DraftGenerateRequest, DraftRead
from schemas.evidence import EvidenceItem
from services.drafts.repository import (
    create_draft,
    get_draft,
    list_drafts,
    update_draft,
    update_draft_claims,
)
from services.evidence.repository import save_evidence_items
from services.papers.repository import list_papers
from services.projects.repository import set_project_status
from services.reader.repository import list_all_chunks
from services.security.auth import AuthIdentity
from services.telemetry.context import telemetry_context
from services.templates.repository import get_template_content

router = APIRouter(
    prefix="/api/projects/{project_id}/drafts",
    tags=["drafts"],
    dependencies=[Depends(require_project_access)],
)


@router.post("/generate", response_model=IdResponse)
def generate_draft(
    project_id: str,
    payload: DraftGenerateRequest,
    db: Session = Depends(get_db),
    identity: AuthIdentity | None = Depends(get_identity),
) -> IdResponse:
    set_project_status(db, project_id, "write")
    papers = list_papers(db, project_id)
    if payload.paper_ids:
        papers = [p for p in papers if p.id in payload.paper_ids]
    template = get_template_content(db, payload.template_id)
    agent = WritingAgent()
    with telemetry_context(
        project_id=project_id,
        user_id=identity.user_id if identity else None,
        operation="draft.generate",
    ):
        result = agent.run(
            {
                "topic": payload.topic or "Untitled Topic",
                "scope": payload.scope or "",
                "papers": [p.model_dump() for p in papers],
                "template": template or "",
            }
        )
    draft = create_draft(db, project_id, result.get("content", ""), result.get("claims"))

    claims_payload = result.get("claims") or []
    claims = [
        c.get("claim") for c in claims_payload if isinstance(c, dict) and c.get("claim")
    ]
    if claims:
        set_project_status(db, project_id, "evidence")
        chunks = list_all_chunks(db, project_id)
        evidence_agent = EvidenceAgent()
        ev_result = evidence_agent.run(
            {"project_id": project_id, "claims": claims, "chunks": [c.model_dump() for c in chunks]}
        )
        items = []
        for raw in ev_result.get("items", []):
            item = EvidenceItem(**raw)
            item.draft_version = draft.version
            items.append(item)
        saved = save_evidence_items(db, items) if items else []
        ref_map: dict[str, list[str]] = {}
        for s in saved:
            ref_map.setdefault(s.claim_text, []).append(s.id or "")
        updated_claims = []
        for c in claims_payload:
            if not isinstance(c, dict):
                continue
            claim_text = c.get("claim")
            if not claim_text:
                continue
            updated_claims.append(
                {
                    "claim": claim_text,
                    "evidence_refs": ref_map.get(claim_text, []),
                    "confidence": c.get("confidence"),
                }
            )
        update_draft_claims(db, project_id, draft.version, updated_claims)

    set_project_status(db, project_id, "edit")
    return IdResponse(id=draft.id or "")


@router.get("", response_model=list[DraftRead])
def list_drafts_endpoint(project_id: str, db: Session = Depends(get_db)) -> list[DraftRead]:
    return list_drafts(db, project_id)


@router.get("/{version}", response_model=DraftRead)
def get_draft_endpoint(
    project_id: str, version: int, db: Session = Depends(get_db)
) -> DraftRead:
    draft = get_draft(db, project_id, version)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.put("/{version}", response_model=DraftRead)
def update_draft_endpoint(
    project_id: str, version: int, payload: DraftCreate, db: Session = Depends(get_db)
) -> DraftRead:
    set_project_status(db, project_id, "edit")
    draft = update_draft(db, project_id, version, payload)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft
