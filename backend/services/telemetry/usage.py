from __future__ import annotations

import math
from uuid import uuid4

from config import db as db_module
from models.usage_event import UsageEvent
from services.telemetry.context import get_telemetry_context


CHAT_COST_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
}
EMBEDDING_COST_PER_1K: dict[str, float] = {
    "text-embedding-3-small": 0.00002,
}


def estimate_text_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, math.ceil(len(stripped) / 4))


def estimate_message_tokens(messages: list[dict]) -> int:
    total = 0
    for message in messages:
        total += 4
        total += estimate_text_tokens(str(message.get("content") or ""))
    return total


def estimate_cost_usd(
    source: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    if source == "chat":
        prompt_rate, completion_rate = CHAT_COST_PER_1K.get(model, (0.0, 0.0))
        return round(((prompt_tokens / 1000) * prompt_rate) + ((completion_tokens / 1000) * completion_rate), 6)
    prompt_rate = EMBEDDING_COST_PER_1K.get(model, 0.0)
    return round((prompt_tokens / 1000) * prompt_rate, 6)


def record_usage_event(
    *,
    source: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: int,
    operation: str | None = None,
) -> None:
    context = get_telemetry_context()
    total_tokens = prompt_tokens + completion_tokens
    estimated_cost_usd = estimate_cost_usd(source, model, prompt_tokens, completion_tokens)
    db = db_module.SessionLocal()
    try:
        db.add(
            UsageEvent(
                id=f"usage_{uuid4().hex}",
                project_id=context.project_id,
                user_id=context.user_id,
                source=source,
                operation=operation or context.operation,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost_usd,
                duration_ms=duration_ms,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
