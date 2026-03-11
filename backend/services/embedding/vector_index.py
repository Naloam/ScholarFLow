from __future__ import annotations

import json
from pathlib import Path
from typing import List

import math

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _index_paths(project_id: str) -> tuple[Path, Path]:
    base = Path("data/indices")
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{project_id}.faiss", base / f"{project_id}.json"


def reset_index(project_id: str) -> None:
    index_path, map_path = _index_paths(project_id)
    if index_path.exists():
        index_path.unlink()
    if map_path.exists():
        map_path.unlink()


def add_vectors(project_id: str, vectors: List[list[float]], chunk_ids: List[str]) -> None:
    if not vectors:
        return
    vecs = [_normalize(v) for v in vectors]
    dim = len(vecs[0])
    index_path, map_path = _index_paths(project_id)

    if faiss is not None:
        if index_path.exists():
            index = faiss.read_index(str(index_path))
        else:
            index = faiss.IndexFlatIP(dim)
        index.add(_to_faiss(vecs))
        faiss.write_index(index, str(index_path))
    _append_mapping(map_path, chunk_ids)


def search(project_id: str, query_vec: list[float], k: int = 5) -> list[tuple[str, float]]:
    index_path, map_path = _index_paths(project_id)
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

    return []


def _to_faiss(vecs: List[list[float]]):
    import numpy as np  # local import

    return np.array(vecs, dtype="float32")


def _append_mapping(map_path: Path, chunk_ids: List[str]) -> None:
    existing = []
    if map_path.exists():
        existing = _load_mapping(map_path)
    existing.extend(chunk_ids)
    map_path.write_text(json.dumps(existing))


def _load_mapping(map_path: Path) -> list[str]:
    return json.loads(map_path.read_text())
