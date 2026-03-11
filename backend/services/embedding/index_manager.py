from __future__ import annotations

from typing import List

from services.embedding.embeddings import embed_texts
from services.embedding.vector_index import add_vectors, reset_index


def rebuild_index(project_id: str, chunk_ids: List[str], texts: List[str]) -> None:
    if not texts:
        return
    vectors = embed_texts(texts)
    reset_index(project_id)
    add_vectors(project_id, vectors, chunk_ids)
