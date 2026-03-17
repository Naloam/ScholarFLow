from __future__ import annotations

from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.usage_event import UsageEvent
from schemas.beta import BetaSummary, FeedbackRead, PerformanceSummary, UsageEventRead
from services.feedback.repository import list_feedback


def build_beta_summary(db: Session, project_id: str) -> BetaSummary:
    usage_rows = list(
        db.execute(
            select(UsageEvent)
            .where(UsageEvent.project_id == project_id)
            .order_by(UsageEvent.created_at.desc())
        ).scalars()
    )
    feedback = list_feedback(db, project_id)

    llm_calls = sum(1 for row in usage_rows if row.source == "chat")
    embedding_calls = sum(1 for row in usage_rows if row.source == "embedding")
    total_prompt_tokens = sum(row.prompt_tokens for row in usage_rows)
    total_completion_tokens = sum(row.completion_tokens for row in usage_rows)
    total_tokens = sum(row.total_tokens for row in usage_rows)
    estimated_cost_usd = round(sum(row.estimated_cost_usd for row in usage_rows), 6)
    average_latency_ms = (
        round(mean(row.duration_ms for row in usage_rows), 2) if usage_rows else 0.0
    )
    latest = usage_rows[0] if usage_rows else None

    performance = PerformanceSummary(
        total_events=len(usage_rows),
        llm_calls=llm_calls,
        embedding_calls=embedding_calls,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        average_latency_ms=average_latency_ms,
        latest_model=latest.model if latest else None,
        latest_operation=latest.operation if latest else None,
        recent_events=[
            UsageEventRead(
                source=row.source,
                operation=row.operation,
                model=row.model,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                total_tokens=row.total_tokens,
                estimated_cost_usd=row.estimated_cost_usd,
                duration_ms=row.duration_ms,
                created_at=row.created_at,
            )
            for row in usage_rows[:5]
        ],
    )

    average_rating = (
        round(mean(item.rating for item in feedback), 2) if feedback else None
    )

    return BetaSummary(
        project_id=project_id,
        performance=performance,
        feedback=feedback,
        feedback_count=len(feedback),
        average_rating=average_rating,
    )
