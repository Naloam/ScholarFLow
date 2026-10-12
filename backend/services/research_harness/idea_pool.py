"""P4.4 — Idea pool manager (journal production line intake).

The paper production line needs batch topic management: ideas come in faster
than runs execute, duplicates must be caught before burning LLM budget, and each
queued idea should get an offline novelty pre-check against the literature the
system has ALREADY retrieved (prior runs' ``papers.jsonl``) — a cheap crowded-
topic warning, not a substitute for the live literature step.

Design rules (harness conventions):
- Deterministic, offline, no LLM: this is bookkeeping; the literature/idea steps
  do the real semantic work at run time.
- Plain JSON at ``<workspace_root>/idea_pool.json`` — human-readable, gitignored
  with the rest of the workspace data.
- Overlap via ``evidence.keywords`` (the same tokenizer the claim-evidence gate
  uses), so "novelty" here means the same thing everywhere in the harness.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.research_harness import evidence
from services.research_harness.pipeline import WORKSPACE_ROOT

logger = logging.getLogger(__name__)

POOL_FILENAME = "idea_pool.json"
STATUSES = ("queued", "running", "done", "retired")

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _pool_tokens(text: str) -> set[str]:
    """ASCII words (3+ chars, stop-stripped — same as evidence.keywords) plus CJK
    character bigrams. Bigrams are the standard cheap CJK token: they let a
    Chinese idea overlap-match Chinese paper titles from S2/Crossref (evidence.
    keywords is ASCII-only, which pre-checked every Chinese idea at 0.0)."""
    tokens = set(evidence.keywords(text))
    cjk = "".join(_CJK_RE.findall(text or ""))
    if len(cjk) == 1:
        tokens.add(cjk)
    for i in range(len(cjk) - 1):
        tokens.add(cjk[i:i + 2])
    return tokens


def _pool_path(pool_root: Path | None = None) -> Path:
    root = Path(pool_root) if pool_root is not None else WORKSPACE_ROOT
    return root / POOL_FILENAME


def _load(pool_root: Path | None = None) -> list[dict[str, Any]]:
    p = _pool_path(pool_root)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        logger.warning("idea pool corrupted; starting empty (file preserved as-is)")
        return []


def _save(entries: list[dict[str, Any]], pool_root: Path | None = None) -> None:
    p = _pool_path(pool_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Novelty pre-check vs literature the system has already retrieved
# --------------------------------------------------------------------------- #


def _prior_paper_titles(pool_root: Path | None = None) -> list[str]:
    root = Path(pool_root) if pool_root is not None else WORKSPACE_ROOT
    titles: list[str] = []
    for papers in sorted(root.glob("*/literature/papers.jsonl")):
        for line in papers.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            title = row.get("title")
            if isinstance(title, str) and title.strip():
                titles.append(title.strip())
    return titles


def novelty_precheck(
    idea: str,
    pool_root: Path | None = None,
    max_reported: int = 5,
) -> dict[str, Any]:
    """Offline crowded-topic warning against prior runs' retrieved papers.

    ``overlap_score`` ∈ [0, 1] = share of the idea's keywords that appear in some
    prior paper title; ``top_overlaps`` lists the highest-overlap titles. High
    score means the topic neighbourhood is already heavily covered by what the
    system has SEEN (not necessarily by the literature at large) — flag, don't
    block: the live literature step makes the real novelty call at run time.
    """
    idea_kw = _pool_tokens(idea)
    if not idea_kw:
        return {"overlap_score": 0.0, "top_overlaps": []}
    scored: list[tuple[float, str]] = []
    for title in _prior_paper_titles(pool_root):
        title_kw = _pool_tokens(title)
        if not title_kw:
            continue
        overlap = len(idea_kw & title_kw) / len(idea_kw)
        if overlap > 0:
            scored.append((round(overlap, 4), title))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return {
        "overlap_score": scored[0][0] if scored else 0.0,
        "top_overlaps": [{"title": t, "overlap": s} for s, t in scored[:max_reported]],
    }


# --------------------------------------------------------------------------- #
# Pool operations
# --------------------------------------------------------------------------- #


def add_idea(
    idea: str,
    domain: str | None = None,
    pool_root: Path | None = None,
) -> dict[str, Any]:
    """Add an idea (dedup: exact-normalized match against queued/running entries).

    The novelty pre-check runs automatically and is stored on the entry. Returns
    the stored entry; raises ValueError on empty or duplicate ideas.
    """
    text = (idea or "").strip()
    if len(text) < 10:
        raise ValueError("idea too short to pool (min 10 chars)")
    entries = _load(pool_root)
    normalized = " ".join(text.lower().split())
    for e in entries:
        if e.get("status") in ("queued", "running") and " ".join(
            (e.get("idea") or "").lower().split()
        ) == normalized:
            raise ValueError(f"duplicate idea already in pool as {e['id']} (status={e['status']})")

    precheck = novelty_precheck(text, pool_root)
    entry = {
        "id": f"idea_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{len(entries) + 1:03d}",
        "idea": text,
        "domain": domain,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "novelty_precheck": precheck,
    }
    entries.append(entry)
    _save(entries, pool_root)
    logger.info("[IdeaPool] added %s (overlap=%.2f)", entry["id"], precheck["overlap_score"])
    return entry


def list_ideas(status: str | None = None, pool_root: Path | None = None) -> list[dict[str, Any]]:
    if status is not None and status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {STATUSES}")
    entries = _load(pool_root)
    return [e for e in entries if status is None or e.get("status") == status]


def next_idea(pool_root: Path | None = None) -> dict[str, Any] | None:
    """Oldest queued idea (FIFO), or None when the queue is empty."""
    queued = [e for e in _load(pool_root) if e.get("status") == "queued"]
    return min(queued, key=lambda e: e.get("created_at", "")) if queued else None


def set_status(idea_id: str, status: str, pool_root: Path | None = None) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {STATUSES}")
    entries = _load(pool_root)
    for e in entries:
        if e.get("id") == idea_id:
            e["status"] = status
            _save(entries, pool_root)
            return e
    raise KeyError(f"no pool idea with id {idea_id!r}")
