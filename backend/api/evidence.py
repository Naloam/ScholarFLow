from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agents.evidence_agent import EvidenceAgent
from config.deps import get_db
from schemas.evidence import EvidenceCoverage, EvidenceExtractRequest, EvidenceItem
from services.evidence.repository import list_evidence_items, save_evidence_items

router = APIRouter(prefix="/api/projects/{project_id}/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceItem])
def list_evidence(project_id: str, db: Session = Depends(get_db)) -> list[EvidenceItem]:
    return list_evidence_items(db, project_id)


@router.get("/coverage", response_model=EvidenceCoverage)
def evidence_coverage(project_id: str, db: Session = Depends(get_db)) -> EvidenceCoverage:
    items = list_evidence_items(db, project_id)
    claims = {i.claim_text for i in items if i.claim_text}
    total_claims = len(claims)
    covered_claims = len(claims)\n    coverage_rate = (covered_claims / total_claims) if total_claims else 0.0\n    return EvidenceCoverage(\n        total_claims=total_claims,\n        covered_claims=covered_claims,\n        coverage_rate=coverage_rate,\n    )


@router.post("/extract", response_model=list[EvidenceItem])
def extract_evidence(
    project_id: str, payload: EvidenceExtractRequest, db: Session = Depends(get_db)
) -> list[EvidenceItem]:
    agent = EvidenceAgent()
    result = agent.run(
        {\n            \"project_id\": project_id,\n            \"claims\": payload.claims,\n            \"chunks\": [c.model_dump() for c in payload.chunks],\n        }\n    )
    items = [EvidenceItem(**x) for x in result.get(\"items\", [])]\n    for item in items:\n        item.project_id = project_id\n    return save_evidence_items(db, items)
