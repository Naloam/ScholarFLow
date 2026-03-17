from __future__ import annotations

import os
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


DEFAULT_CHAT_MODEL = "gpt-4o-mini"
FALLBACK_RESPONSE = {"choices": [{"message": {"role": "assistant", "content": ""}}]}


def chat(messages: list[dict[str, Any]], model: str | None = None, **kwargs: Any) -> dict:
    model = model or DEFAULT_CHAT_MODEL
    started = perf_counter()
    if litellm_completion is None:
        response = FALLBACK_RESPONSE
        record_usage_event(
            source="chat",
            model=model,
            prompt_tokens=estimate_message_tokens(messages),
            completion_tokens=0,
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return response
    if os.getenv("SCHOLARFLOW_OFFLINE_LLM") == "1" or not settings.llm_api_key:
        response = FALLBACK_RESPONSE
        record_usage_event(
            source="chat",
            model=model,
            prompt_tokens=estimate_message_tokens(messages),
            completion_tokens=0,
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return response
    response = litellm_completion(model=model, messages=messages, **kwargs)
    usage = response.get("usage", {}) if isinstance(response, dict) else {}
    content = (
        response.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(response, dict)
        else ""
    )
    record_usage_event(
        source="chat",
        model=model,
        prompt_tokens=int(usage.get("prompt_tokens") or estimate_message_tokens(messages)),
        completion_tokens=int(usage.get("completion_tokens") or estimate_text_tokens(content)),
        duration_ms=int((perf_counter() - started) * 1000),
    )
    return response
