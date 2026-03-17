from datetime import datetime

from pydantic import BaseModel, Field


class UsageEventRead(BaseModel):
    source: str
    operation: str | None = None
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    duration_ms: int
    created_at: datetime | None = None


class PerformanceSummary(BaseModel):
    total_events: int = 0
    llm_calls: int = 0
    embedding_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    average_latency_ms: float = 0.0
    latest_model: str | None = None
    latest_operation: str | None = None
    recent_events: list[UsageEventRead] = Field(default_factory=list)


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    category: str = Field(min_length=2, max_length=50)
    comment: str = Field(min_length=4, max_length=4000)


class FeedbackRead(BaseModel):
    id: str
    project_id: str
    user_id: str | None = None
    rating: int
    category: str
    comment: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BetaSummary(BaseModel):
    project_id: str
    performance: PerformanceSummary
    feedback: list[FeedbackRead] = Field(default_factory=list)
    feedback_count: int = 0
    average_rating: float | None = None
