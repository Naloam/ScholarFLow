from __future__ import annotations

from statistics import mean

from sqlalchemy.orm import Session

from schemas.analysis import AnalysisSummary, ScoreSummary
from services.drafts.analysis import needs_evidence_count
from services.drafts.repository import get_latest_draft
from services.evidence.repository import list_evidence_claims
from services.review.repository import list_reviews


def build_summary(db: Session, project_id: str) -> AnalysisSummary:
    draft = get_latest_draft(db, project_id)
    draft_version = draft.version if draft else None
    content = draft.content if draft else ""

    draft_claims = set()
    if draft and draft.claims:
        for c in draft.claims:
            if isinstance(c, dict) and c.get("claim"):
                draft_claims.add(c.get("claim"))
    evidence_claims = list_evidence_claims(db, project_id)
    total_claims = len(draft_claims)
    covered = len(draft_claims & evidence_claims) if total_claims else 0
    coverage_rate = (covered / total_claims) if total_claims else 0.0

    reviews = list_reviews(db, project_id)
    score_summary = None
    if reviews:
        vals = {
            "originality": mean([r.scores.originality for r in reviews]),
            "importance": mean([r.scores.importance for r in reviews]),
            "evidence_support": mean([r.scores.evidence_support for r in reviews]),
            "soundness": mean([r.scores.soundness for r in reviews]),
            "clarity": mean([r.scores.clarity for r in reviews]),
            "value": mean([r.scores.value for r in reviews]),
            "contextualization": mean([r.scores.contextualization for r in reviews]),
        }
        score_summary = ScoreSummary(**vals)

    chart = None
    if score_summary:
        chart = {
            "labels": [
                "originality",
                "importance",
                "evidence_support",
                "soundness",
                "clarity",
                "value",
                "contextualization",
            ],
            "values": [
                score_summary.originality,
                score_summary.importance,
                score_summary.evidence_support,
                score_summary.soundness,
                score_summary.clarity,
                score_summary.value,
                score_summary.contextualization,
            ],
        }

    return AnalysisSummary(
        project_id=project_id,
        draft_version=draft_version,
        evidence_coverage=coverage_rate,
        needs_evidence_count=needs_evidence_count(content),
        review_scores=score_summary,
        chart=chart,
    )
