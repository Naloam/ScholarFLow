from __future__ import annotations

import math
from uuid import uuid4

from config import db as db_module
from models.usage_event import UsageEvent
from services.telemetry.context import get_telemetry_context


CHAT_COST_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
}
DEEPSEEK_CHAT_COST_PER_1M: dict[str, tuple[float, float, float]] = {
    "deepseek/deepseek-chat": (0.028, 0.28, 0.42),
    "deepseek-chat": (0.028, 0.28, 0.42),
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
    prompt_cache_hit_tokens: int = 0,
    prompt_cache_miss_tokens: int | None = None,
) -> float:
    normalized_model = (model or "").strip().lower()
    if source == "chat":
        deepseek_rates = DEEPSEEK_CHAT_COST_PER_1M.get(normalized_model)
        if deepseek_rates is not None:
            hit_rate, miss_rate, completion_rate = deepseek_rates
            cache_hit_tokens = max(0, prompt_cache_hit_tokens)
            cache_miss_tokens = (
                max(0, prompt_cache_miss_tokens)
                if prompt_cache_miss_tokens is not None
                else max(0, prompt_tokens - cache_hit_tokens)
            )
            return round(
                ((cache_hit_tokens / 1_000_000) * hit_rate)
                + ((cache_miss_tokens / 1_000_000) * miss_rate)
                + ((completion_tokens / 1_000_000) * completion_rate),
                6,
            )
        prompt_rate, completion_rate = CHAT_COST_PER_1K.get(normalized_model, (0.0, 0.0))
        return round(((prompt_tokens / 1000) * prompt_rate) + ((completion_tokens / 1000) * completion_rate), 6)
    prompt_rate = EMBEDDING_COST_PER_1K.get(normalized_model, 0.0)
    return round((prompt_tokens / 1000) * prompt_rate, 6)


def record_usage_event(
    *,
    source: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: int,
    operation: str | None = None,
    prompt_cache_hit_tokens: int = 0,
    prompt_cache_miss_tokens: int | None = None,
) -> None:
    context = get_telemetry_context()
    total_tokens = prompt_tokens + completion_tokens
    estimated_cost_usd = estimate_cost_usd(
        source,
        model,
        prompt_tokens,
        completion_tokens,
        prompt_cache_hit_tokens=prompt_cache_hit_tokens,
        prompt_cache_miss_tokens=prompt_cache_miss_tokens,
    )
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
