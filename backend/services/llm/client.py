from __future__ import annotations

import logging
import os
import time
from time import perf_counter
from typing import Any

try:
    from litellm import completion as litellm_completion  # type: ignore
except Exception:  # pragma: no cover
    litellm_completion = None

from config.settings import settings
from services.telemetry.usage import (
    estimate_message_tokens,
    estimate_text_tokens,
    record_usage_event,
)
from services.llm.response_utils import get_message_content, get_usage_fields

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
FALLBACK_RESPONSE = {"choices": [{"message": {"role": "assistant", "content": ""}}]}


def chat(messages: list[dict[str, Any]], model: str | None = None, **kwargs: Any) -> dict:
    model = model or settings.llm_model or DEFAULT_CHAT_MODEL
    started = perf_counter()
    if litellm_completion is None:
        logger.warning("LLM offline: litellm is not installed — returning empty fallback")
        response = FALLBACK_RESPONSE
        record_usage_event(
            source="chat",
            model=model,
            prompt_tokens=estimate_message_tokens(messages),
            completion_tokens=0,
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return response
    if os.getenv("SCHOLARFLOW_OFFLINE_LLM") == "1":
        logger.warning("LLM offline: SCHOLARFLOW_OFFLINE_LLM=1 — returning empty fallback")
        response = FALLBACK_RESPONSE
        record_usage_event(
            source="chat",
            model=model,
            prompt_tokens=estimate_message_tokens(messages),
            completion_tokens=0,
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return response
    if not settings.llm_api_key:
        logger.warning("LLM offline: no API key configured (set LITELLM_API_KEY / OPENAI_API_KEY) — returning empty fallback")
        response = FALLBACK_RESPONSE
        record_usage_event(
            source="chat",
            model=model,
            prompt_tokens=estimate_message_tokens(messages),
            completion_tokens=0,
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return response
    request_kwargs = dict(kwargs)
    if settings.llm_api_base and "api_base" not in request_kwargs:
        request_kwargs["api_base"] = settings.llm_api_base
    if settings.llm_api_key and "api_key" not in request_kwargs:
        request_kwargs["api_key"] = settings.llm_api_key
    logger.info("LLM call: model=%s api_base=%s messages=%d", model, settings.llm_api_base, len(messages))
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = litellm_completion(model=model, messages=messages, **request_kwargs)
            break
        except Exception as exc:
            error_str = str(exc)
            is_rate_limit = "rate" in error_str.lower() or "429" in error_str
            if is_rate_limit and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning("LLM rate limited, retrying in %ds (attempt %d/%d): %s", wait, attempt + 1, max_retries, exc)
                time.sleep(wait)
                continue
            logger.error("LLM call FAILED: model=%s error=%s", model, exc)
            response = FALLBACK_RESPONSE
            record_usage_event(
                source="chat",
                model=model,
                prompt_tokens=estimate_message_tokens(messages),
                completion_tokens=0,
                duration_ms=int((perf_counter() - started) * 1000),
            )
            return response
    usage = get_usage_fields(response)
    content = get_message_content(response)
    prompt_cache_hit_tokens = usage.get("prompt_cache_hit_tokens")
    prompt_cache_miss_tokens = usage.get("prompt_cache_miss_tokens")
    logger.info("LLM response: model=%s content_len=%d tokens=%s", model, len(content), usage.get("prompt_tokens"))
    record_usage_event(
        source="chat",
        model=model,
        prompt_tokens=int(usage.get("prompt_tokens") or estimate_message_tokens(messages)),
        completion_tokens=int(usage.get("completion_tokens") or estimate_text_tokens(content)),
        duration_ms=int((perf_counter() - started) * 1000),
        prompt_cache_hit_tokens=int(prompt_cache_hit_tokens or 0),
        prompt_cache_miss_tokens=(
            int(prompt_cache_miss_tokens)
            if prompt_cache_miss_tokens is not None
            else None
        ),
    )
    return response
