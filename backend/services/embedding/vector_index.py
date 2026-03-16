from __future__ import annotations

import json
from pathlib import Path
from typing import List

import math

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None

from config.settings import settings


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _index_paths(project_id: str) -> tuple[Path, Path, Path]:
    base = settings.data_dir / "indices"
    base.mkdir(parents=True, exist_ok=True)
    return (
        base / f"{project_id}.faiss",
        base / f"{project_id}.json",
        base / f"{project_id}.vectors.json",
    )


def reset_index(project_id: str) -> None:
    for path in _index_paths(project_id):
        if path.exists():
            path.unlink()


def add_vectors(project_id: str, vectors: List[list[float]], chunk_ids: List[str]) -> None:
    if not vectors:
        return
    vecs = [_normalize(v) for v in vectors]
    dim = len(vecs[0])
    index_path, map_path, vector_path = _index_paths(project_id)

    if faiss is not None:
        if index_path.exists():
            index = faiss.read_index(str(index_path))
        else:
            index = faiss.IndexFlatIP(dim)
        index.add(_to_faiss(vecs))
        faiss.write_index(index, str(index_path))
    _append_mapping(map_path, chunk_ids)
    _append_vectors(vector_path, vecs)


def search(project_id: str, query_vec: list[float], k: int = 5) -> list[tuple[str, float]]:
    index_path, map_path, vector_path = _index_paths(project_id)
    if not map_path.exists():
        return []
    mapping = _load_mapping(map_path)

    q = _normalize(query_vec)
    if faiss is not None and index_path.exists():
        index = faiss.read_index(str(index_path))
        scores, idxs = index.search(_to_faiss([q]), k)
        results: list[tuple[str, float]] = []
        for i, score in zip(idxs[0], scores[0]):
            if i < 0 or i >= len(mapping):
                continue
            results.append((mapping[i], float(score)))
        return results

    vectors = _load_vectors(vector_path)
    if not vectors:
        return []
    offset = max(0, len(mapping) - len(vectors))
    scored = [
        (chunk_id, _dot(q, vec))
        for chunk_id, vec in zip(mapping[offset:], vectors)
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:k]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _to_faiss(vecs: List[list[float]]):
    import numpy as np  # local import

    return np.array(vecs, dtype="float32")


def _append_mapping(map_path: Path, chunk_ids: List[str]) -> None:
    existing = []
    if map_path.exists():
        existing = _load_mapping(map_path)
    existing.extend(chunk_ids)
    map_path.write_text(json.dumps(existing), encoding="utf-8")


def _load_mapping(map_path: Path) -> list[str]:
    return json.loads(map_path.read_text(encoding="utf-8"))


def _append_vectors(vector_path: Path, vectors: List[list[float]]) -> None:
    existing: list[list[float]] = []
    if vector_path.exists():
        existing = _load_vectors(vector_path)
    existing.extend(vectors)
    vector_path.write_text(json.dumps(existing), encoding="utf-8")


def _load_vectors(vector_path: Path) -> list[list[float]]:
    if not vector_path.exists():
        return []
    return json.loads(vector_path.read_text(encoding="utf-8"))
