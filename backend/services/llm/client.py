from __future__ import annotations

from typing import Any

try:
    from litellm import completion as litellm_completion  # type: ignore
except Exception:  # pragma: no cover
    litellm_completion = None

from config.settings import settings


DEFAULT_CHAT_MODEL = "gpt-4o-mini"


def chat(messages: list[dict[str, Any]], model: str | None = None, **kwargs: Any) -> dict:
    model = model or DEFAULT_CHAT_MODEL
    if litellm_completion is None:
        return {"choices": [{"message": {"role": "assistant", "content": ""}}]}
    return litellm_completion(model=model, messages=messages, **kwargs)
