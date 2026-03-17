from typing import Literal

from pydantic import BaseModel, Field


class ScoreSummary(BaseModel):
    originality: float
    importance: float
    evidence_support: float
    soundness: float
    clarity: float
    value: float
    contextualization: float


class SimilarityMatch(BaseModel):
    source_type: Literal["evidence_snippet", "paper_abstract"]
    source_label: str
    paper_id: str | None = None
    paper_title: str | None = None
    similarity: float
    overlap_units: int
    draft_excerpt: str
    source_excerpt: str


class SimilaritySummary(BaseModel):
    checked_paragraphs: int
    flagged_paragraphs: int
    max_similarity: float
    average_similarity: float
    status: Literal["clear", "warning", "high"]
    matches: list[SimilarityMatch] = Field(default_factory=list)


class AnalysisSummary(BaseModel):
    project_id: str
    draft_version: int | None = None
    evidence_coverage: float
    needs_evidence_count: int
    review_scores: ScoreSummary | None = None
    chart: dict | None = None
    similarity: SimilaritySummary | None = None
