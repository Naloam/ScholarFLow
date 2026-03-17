from __future__ import annotations

import os
from typing import Any

try:
    from litellm import completion as litellm_completion  # type: ignore
except Exception:  # pragma: no cover
    litellm_completion = None

from config.settings import settings


DEFAULT_CHAT_MODEL = "gpt-4o-mini"
FALLBACK_RESPONSE = {"choices": [{"message": {"role": "assistant", "content": ""}}]}


def chat(messages: list[dict[str, Any]], model: str | None = None, **kwargs: Any) -> dict:
    model = model or DEFAULT_CHAT_MODEL
    if litellm_completion is None:
        return FALLBACK_RESPONSE
    if os.getenv("SCHOLARFLOW_OFFLINE_LLM") == "1" or not settings.llm_api_key:
        return FALLBACK_RESPONSE
    return litellm_completion(model=model, messages=messages, **kwargs)
