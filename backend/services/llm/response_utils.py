from __future__ import annotations

from typing import Any


def get_field(value: Any, key: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            result = getter(key)
        except TypeError:
            result = default
        if result is not None:
            return result
    return getattr(value, key, default)


def get_usage_fields(response: Any) -> dict[str, Any]:
    usage = get_field(response, "usage", {}) or {}
    if isinstance(usage, dict):
        return usage
    model_dump = getattr(usage, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {
        "prompt_tokens": get_field(usage, "prompt_tokens", 0),
        "completion_tokens": get_field(usage, "completion_tokens", 0),
        "total_tokens": get_field(usage, "total_tokens", 0),
        "prompt_cache_hit_tokens": get_field(usage, "prompt_cache_hit_tokens"),
        "prompt_cache_miss_tokens": get_field(usage, "prompt_cache_miss_tokens"),
    }


def get_message_content(response: Any) -> str:
    choices = get_field(response, "choices", []) or []
    if not choices:
        return ""
    message = get_field(choices[0], "message", {}) or {}
    content = get_field(message, "content", "")
    return content if isinstance(content, str) else str(content or "")
