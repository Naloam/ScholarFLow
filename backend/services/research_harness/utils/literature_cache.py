"""Literature scout cache helpers.

Extracted byte-for-byte from ``services/autoresearch/repository.py`` (Session 15
orchestrator retirement) so that ``literature_connectors`` can keep caching
literature scout results without importing the soon-to-be-deleted old brain.

Behavior is identical to the original: cache files land at
``autoresearch_dir(project_id) / literature_scout_cache / <safe_source>_<sha[:20]>.json``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from services.workspace import autoresearch_dir

LITERATURE_SCOUT_CACHE_DIRNAME = "literature_scout_cache"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _literature_scout_cache_dir(project_id: str) -> Path:
    path = autoresearch_dir(project_id) / LITERATURE_SCOUT_CACHE_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _literature_scout_cache_key(*, source: str, query: str, limit: int) -> str:
    payload = json.dumps(
        {"source": source, "query": query, "limit": limit},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def literature_scout_cache_key(*, source: str, query: str, limit: int) -> str:
    return _literature_scout_cache_key(source=source, query=query, limit=limit)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary_path.write_text(encoded, encoding="utf-8")
    temporary_path.replace(path)


def _read_json(path: Path) -> object | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def literature_scout_cache_file_path(
    project_id: str,
    *,
    source: str,
    query: str,
    limit: int,
) -> str:
    key = _literature_scout_cache_key(source=source, query=query, limit=limit)
    safe_source = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in source
    )
    return str(_literature_scout_cache_dir(project_id) / f"{safe_source}_{key[:20]}.json")


def load_literature_scout_cache(
    project_id: str,
    *,
    source: str,
    query: str,
    limit: int,
) -> dict[str, object] | None:
    payload = _read_json(
        Path(literature_scout_cache_file_path(project_id, source=source, query=query, limit=limit))
    )
    return payload if isinstance(payload, dict) else None


def save_literature_scout_cache(
    project_id: str,
    *,
    source: str,
    query: str,
    limit: int,
    payload: dict[str, object],
) -> str:
    path = Path(
        literature_scout_cache_file_path(project_id, source=source, query=query, limit=limit)
    )
    _write_json(
        path,
        {
            **payload,
            "source": source,
            "query": query,
            "limit": limit,
            "cache_key": literature_scout_cache_key(source=source, query=query, limit=limit),
            "cache_timestamp": str(payload.get("cache_timestamp") or payload.get("fetched_at") or _utcnow().isoformat()),
        },
    )
    return str(path)
