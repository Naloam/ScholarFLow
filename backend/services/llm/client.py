from __future__ import annotations

import logging
import multiprocessing as mp
import os
import queue
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
DEEPSEEK_V4_THINKING_IGNORED_PARAMS = (
    "temperature",
    "top_p",
    "presence_penalty",
    "frequency_penalty",
)
_FORK_CONTEXT_NAME = "fork"


def _apply_deepseek_v4_thinking_defaults(model: str, request_kwargs: dict[str, Any]) -> None:
    if "deepseek-v4" not in model.lower():
        return
    extra_body = dict(request_kwargs.get("extra_body") or {})
    extra_body.setdefault("thinking", {"type": "enabled"})
    request_kwargs["extra_body"] = extra_body

    effort = str(os.getenv("DEEPSEEK_REASONING_EFFORT") or "high").strip().lower()
    if effort not in {"high", "max"}:
        effort = "high"
    request_kwargs.setdefault("reasoning_effort", effort)

    allowed_params = list(request_kwargs.get("allowed_openai_params") or [])
    if "reasoning_effort" not in allowed_params:
        allowed_params.append("reasoning_effort")
    request_kwargs["allowed_openai_params"] = allowed_params

    removed_params = [
        name
        for name in DEEPSEEK_V4_THINKING_IGNORED_PARAMS
        if request_kwargs.pop(name, None) is not None
    ]
    if removed_params:
        logger.debug(
            "DeepSeek V4 thinking ignores sampling params; stripped %s",
            ", ".join(removed_params),
        )


def _apply_request_timeout(request_kwargs: dict[str, Any]) -> None:
    if "timeout" in request_kwargs:
        return
    raw_timeout = os.getenv("LLM_TIMEOUT_SECONDS")
    if not raw_timeout:
        return
    try:
        timeout = float(raw_timeout)
    except ValueError:
        logger.warning("Ignoring invalid LLM_TIMEOUT_SECONDS=%r", raw_timeout)
        return
    if timeout > 0:
        request_kwargs["timeout"] = timeout


def _positive_float(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _hard_timeout_seconds(model: str, request_kwargs: dict[str, Any]) -> float | None:
    raw_hard_timeout = os.getenv("LLM_HARD_TIMEOUT_SECONDS")
    if raw_hard_timeout:
        timeout = _positive_float(raw_hard_timeout)
        if timeout is None:
            logger.warning("Ignoring invalid LLM_HARD_TIMEOUT_SECONDS=%r", raw_hard_timeout)
        return timeout
    if "deepseek-v4" in model.lower():
        return _positive_float(request_kwargs.get("timeout"))
    return None


def _json_safe_response(response: Any) -> dict[str, Any]:
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    if isinstance(response, dict):
        return response
    usage = get_usage_fields(response)
    choices = getattr(response, "choices", None) or []
    normalized_choices: list[dict[str, Any]] = []
    for choice in choices:
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        role = getattr(message, "role", None)
        if role is None and isinstance(message, dict):
            role = message.get("role")
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content is None and isinstance(message, dict):
            reasoning_content = message.get("reasoning_content")
        normalized_message: dict[str, Any] = {
            "role": role or "assistant",
            "content": content if isinstance(content, str) else str(content or ""),
        }
        if reasoning_content:
            normalized_message["reasoning_content"] = reasoning_content
        normalized_choices.append({"message": normalized_message})
    return {"choices": normalized_choices, "usage": usage}


def _litellm_completion_worker(
    result_queue: mp.Queue,
    *,
    model: str,
    messages: list[dict[str, Any]],
    request_kwargs: dict[str, Any],
) -> None:
    try:
        response = litellm_completion(model=model, messages=messages, **request_kwargs)
        result_queue.put({"ok": True, "response": _json_safe_response(response)})
    except BaseException as exc:  # pragma: no cover - exercised through parent process
        result_queue.put(
            {
                "ok": False,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            }
        )


def _process_context() -> mp.context.BaseContext:
    if hasattr(os, "fork"):
        try:
            return mp.get_context(_FORK_CONTEXT_NAME)
        except ValueError:
            pass
    return mp.get_context()


class LLMHardTimeoutError(TimeoutError):
    pass


def _run_litellm_completion(
    *,
    model: str,
    messages: list[dict[str, Any]],
    request_kwargs: dict[str, Any],
    hard_timeout_seconds: float | None,
) -> Any:
    if hard_timeout_seconds is None:
        return litellm_completion(model=model, messages=messages, **request_kwargs)

    ctx = _process_context()
    result_queue: mp.Queue = ctx.Queue(maxsize=1)
    process = ctx.Process(
        target=_litellm_completion_worker,
        kwargs={
            "result_queue": result_queue,
            "model": model,
            "messages": messages,
            "request_kwargs": request_kwargs,
        },
        daemon=True,
    )
    try:
        process.start()
    except AssertionError as exc:
        logger.warning(
            "LLM hard timeout worker could not start (%s); falling back to SDK timeout only",
            exc,
        )
        return litellm_completion(model=model, messages=messages, **request_kwargs)

    process.join(hard_timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(2)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(2)
        raise LLMHardTimeoutError(f"LLM call exceeded hard timeout of {hard_timeout_seconds:g}s")

    try:
        payload = result_queue.get_nowait()
    except queue.Empty as exc:
        raise RuntimeError(f"LLM worker exited without returning a response (exitcode={process.exitcode})") from exc
    if not payload.get("ok"):
        error_type = payload.get("error_type") or "LLMError"
        error = payload.get("error") or "unknown error"
        raise RuntimeError(f"{error_type}: {error}")
    return payload.get("response") or FALLBACK_RESPONSE


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
    _apply_request_timeout(request_kwargs)
    _apply_deepseek_v4_thinking_defaults(model, request_kwargs)
    hard_timeout = _hard_timeout_seconds(model, request_kwargs)
    logger.info("LLM call: model=%s api_base=%s messages=%d", model, settings.llm_api_base, len(messages))
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = _run_litellm_completion(
                model=model,
                messages=messages,
                request_kwargs=request_kwargs,
                hard_timeout_seconds=hard_timeout,
            )
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
