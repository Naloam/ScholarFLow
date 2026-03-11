from __future__ import annotations

import hashlib
from typing import List

try:
    from litellm import embedding as litellm_embedding  # type: ignore
except Exception:  # pragma: no cover
    litellm_embedding = None


DEFAULT_DIM = 384
DEFAULT_MODEL = "text-embedding-3-small"


def _hash_embed(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = [b / 255.0 for b in h]
    vec = (vals * ((dim // len(vals)) + 1))[:dim]
    return vec


def embed_texts(texts: List[str], model: str | None = None) -> list[list[float]]:
    model = model or DEFAULT_MODEL
    if litellm_embedding is None:
        return [_hash_embed(t) for t in texts]

    resp = litellm_embedding(model=model, input=texts)
    data = resp.get("data", [])
    return [d.get("embedding", []) for d in data]
