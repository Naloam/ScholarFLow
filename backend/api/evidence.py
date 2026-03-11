from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agents.evidence_agent import EvidenceAgent
from config.deps import get_db
from schemas.evidence import EvidenceCoverage, EvidenceExtractRequest, EvidenceItem
from services.drafts.repository import get_claims_by_version, get_latest_claims
from services.evidence.repository import (
    list_evidence_claims,
    list_evidence_items,
    save_evidence_items,
)

router = APIRouter(prefix="/api/projects/{project_id}/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceItem])
def list_evidence(project_id: str, db: Session = Depends(get_db)) -> list[EvidenceItem]:
    return list_evidence_items(db, project_id)


@router.get("/coverage", response_model=EvidenceCoverage)
def evidence_coverage(
    project_id: str,
    version: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> EvidenceCoverage:
    draft_claims = (
        set(get_claims_by_version(db, project_id, version))
        if version is not None
        else set(get_latest_claims(db, project_id))
    )
    evidence_claims = list_evidence_claims(db, project_id)
    total_claims = len(draft_claims)
    covered_claims = len(draft_claims & evidence_claims)
    coverage_rate = (covered_claims / total_claims) if total_claims else 0.0
    return EvidenceCoverage(
        total_claims=total_claims,
        covered_claims=covered_claims,
        coverage_rate=coverage_rate,
    )


@router.post("/extract", response_model=list[EvidenceItem])
def extract_evidence(
    project_id: str, payload: EvidenceExtractRequest, db: Session = Depends(get_db)
) -> list[EvidenceItem]:
    agent = EvidenceAgent()
    result = agent.run(
        {
            "project_id": project_id,
            "claims": payload.claims,
            "chunks": [c.model_dump() for c in payload.chunks],
        }
    )
    items = [EvidenceItem(**x) for x in result.get("items", [])]
    for item in items:
        item.project_id = project_id
    return save_evidence_items(db, items)
