from pydantic import BaseModel


class ScoreSummary(BaseModel):
    originality: float
    importance: float
    evidence_support: float
    soundness: float
    clarity: float
    value: float
    contextualization: float


class AnalysisSummary(BaseModel):
    project_id: str
    draft_version: int | None = None
    evidence_coverage: float
    needs_evidence_count: int
    review_scores: ScoreSummary | None = None
    chart: dict | None = None
