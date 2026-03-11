from fastapi import APIRouter

from schemas.evidence import EvidenceCoverage, EvidenceItem

router = APIRouter(prefix="/api/projects/{project_id}/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceItem])
def list_evidence(project_id: str) -> list[EvidenceItem]:
    return []


@router.get("/coverage", response_model=EvidenceCoverage)
def evidence_coverage(project_id: str) -> EvidenceCoverage:
    return EvidenceCoverage(total_claims=0, covered_claims=0, coverage_rate=0.0)
