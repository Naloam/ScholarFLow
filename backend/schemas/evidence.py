from datetime import datetime
from pydantic import BaseModel


class EvidenceItem(BaseModel):
    id: str | None = None
    project_id: str | None = None
    claim_text: str
    paper_id: str
    page: int | None = None
    section: str | None = None
    snippet: str | None = None
    confidence: float | None = None
    type: str | None = None
    created_at: datetime | None = None


class EvidenceCoverage(BaseModel):
    total_claims: int
    covered_claims: int
    coverage_rate: float
