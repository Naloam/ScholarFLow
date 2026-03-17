from __future__ import annotations

import hashlib
from time import perf_counter
from typing import List

try:
    from litellm import embedding as litellm_embedding  # type: ignore
except Exception:  # pragma: no cover
    litellm_embedding = None

from services.telemetry.usage import estimate_text_tokens, record_usage_event


DEFAULT_DIM = 384
DEFAULT_MODEL = "text-embedding-3-small"


def _hash_embed(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = [b / 255.0 for b in h]
    vec = (vals * ((dim // len(vals)) + 1))[:dim]
    return vec


def embed_texts(texts: List[str], model: str | None = None) -> list[list[float]]:
    model = model or DEFAULT_MODEL
    started = perf_counter()
    prompt_tokens = sum(estimate_text_tokens(text) for text in texts)
    if litellm_embedding is None:
        vectors = [_hash_embed(t) for t in texts]
        record_usage_event(
            source="embedding",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=0,
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return vectors

    resp = litellm_embedding(model=model, input=texts)
    data = resp.get("data", [])
    usage = resp.get("usage", {}) if isinstance(resp, dict) else {}
    record_usage_event(
        source="embedding",
        model=model,
        prompt_tokens=int(usage.get("prompt_tokens") or prompt_tokens),
        completion_tokens=0,
        duration_ms=int((perf_counter() - started) * 1000),
    )
    return [d.get("embedding", []) for d in data]
