"""Portfolio-aware execution (V2.3, goal_session9.md).

The new core used to pick ONE hypothesis (``idea_agent.select_hypothesis``) and
run just that. CLAUDE.md's "Non-Negotiable Baselines" names **portfolio-aware
execution** as a baseline the new core had not yet implemented. This module is the
pure-logic core of that layer: rank the idea bank, pick the top-K, and — after each
candidate has been run + gated independently — aggregate them into ONE honest
portfolio verdict.

Honesty contract (only-add-never-loosen):
  - ``aggregate_portfolio`` picks the best candidate by its **anchored** verdict
    (the same ``evidence.full_verdict`` V2.2 uses). It never upgrades a verdict and
    never shores a portfolio up on a friendlier metric. An all-negative portfolio is
    reported as ``all_negative``; its "best" is still the highest-anchored candidate.
  - K=1 is byte-equivalent to the old single-hypothesis path (handled in the
    pipeline layer, which only builds a ``candidates/`` subtree when K>1).

This module is pure logic + an optional additive disk index (``ideas/portfolio.json``);
the per-candidate execution + ledger writing lives in ``pipeline.run_portfolio_experiments``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config.settings import settings
from services.research_harness import evidence

logger = logging.getLogger(__name__)

WORKSPACE_ROOT: Path = Path(settings.data_dir) / "research_workspace"

# K = how many of the ranked candidates actually get executed. Default 3 (breadth
# without runaway LLM cost), hard cap 5 (GLM per-minute rate limit — portfolio runs
# sequentially, never in parallel).
DEFAULT_K: int = 3
MAX_K: int = 5

# Feasibility favourability for tie-breaking (higher = more favourable).
_FEASIBILITY_RANK: dict[str, int] = {"high": 2, "medium": 1, "low": 0}
# Priority for ascending sort (lower = better-first); mirrors select_hypothesis.
_FEASIBILITY_PRIORITY: dict[str, int] = {"high": 0, "medium": 1, "low": 2}

# Verdict favourability rank — mirrors evidence._VERDICT_SEVERITY. Duplicated (not
# imported) so this module stays stable if the severity table is re-tuned; the
# aggregate must agree with full_verdict's ordering, which it does by construction.
_VERDICT_FAVOURABILITY: dict[str, int] = {
    "execution_failed": 0,
    "no_comparison": 1,
    "negative": 2,
    "mixed": 3,
    "positive_not_significant": 4,
    "positive_significant": 5,
}
_FAVOURABLE: frozenset[str] = frozenset({"positive_significant", "positive_not_significant", "mixed"})
_UNFAVOURABLE: frozenset[str] = frozenset({"negative", "no_comparison", "execution_failed"})


# --------------------------------------------------------------------------- #
# Ranking + top-K selection
# --------------------------------------------------------------------------- #


def _feasibility_rank(h: dict[str, Any]) -> int:
    return _FEASIBILITY_RANK.get(str(h.get("feasibility", "")).strip().lower(), 0)


def _rank_key(h: dict[str, Any]) -> tuple[int, int]:
    """Sort key reusing select_hypothesis's logic: feasibility first (high<medium<low
    as 0/1/2), then MORE kill_criteria = MORE specific = EARLIER (hence negative)."""
    feasibility = _FEASIBILITY_PRIORITY.get(
        str(h.get("feasibility", "")).strip().lower(),
        _FEASIBILITY_PRIORITY["low"],
    )
    specificity = len(h.get("kill_criteria") or [])
    return (feasibility, -specificity)


def rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return candidates sorted best-first, each with a 0-based ``rank`` added.

    Reuses ``select_hypothesis``'s scoring (feasibility high>medium>low; more
    kill_criteria = more specific = earlier). Stable on ties (original order kept).
    Does NOT mutate the input — works on shallow copies.
    """
    ordered = sorted((dict(c) for c in candidates), key=_rank_key)
    for i, c in enumerate(ordered):
        c["rank"] = i
    return ordered


def _lean_row(h: dict[str, Any]) -> dict[str, Any]:
    """The projection written to ``ideas/portfolio.json`` — identifiers only, no
    free-text method sketches leaked into the index."""
    return {
        "hypothesis_id": h.get("hypothesis_id", ""),
        "title": h.get("title", ""),
        "rank": h.get("rank", 0),
        "primary_metric": h.get("primary_metric"),
        "feasibility": h.get("feasibility"),
    }


def select_portfolio(
    candidates: list[dict[str, Any]],
    *,
    k: int = DEFAULT_K,
    project_id: str | None = None,
    budget_hint: int | None = None,
) -> dict[str, Any]:
    """Rank candidates and take the top-K (capped to ``MAX_K`` and to the candidate
    count). Returns ``{"k": effective_k, "ranked": [top-K hypotheses with rank]}``.

    When ``project_id`` is given, also writes the lean index ``ideas/portfolio.json``
    (additive — never touches ``selected.json``, which stays rank-0 for old consumers).
    ``budget_hint`` caps K further when supplied (reserved for a future budget knob).
    """
    ranked = rank_candidates(candidates)
    cap = MAX_K
    if budget_hint is not None and budget_hint > 0:
        cap = min(cap, budget_hint)
    effective_k = max(0, min(k, cap, len(ranked)))
    top_k = ranked[:effective_k]

    if project_id is not None and top_k:
        ideas_dir = WORKSPACE_ROOT / project_id / "ideas"
        ideas_dir.mkdir(parents=True, exist_ok=True)
        payload = {"k": effective_k, "ranked": [_lean_row(h) for h in top_k]}
        (ideas_dir / "portfolio.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("[Portfolio] selected top-%d of %d candidates for %s", effective_k, len(ranked), project_id)

    return {"k": effective_k, "ranked": top_k}


# --------------------------------------------------------------------------- #
# Honest aggregation
# --------------------------------------------------------------------------- #


def _any_significant(metrics: dict[str, Any]) -> bool:
    stats = metrics.get("statistics") or {}
    return bool(stats.get("any_significant"))


def _seed_count(metrics: dict[str, Any]) -> int:
    stats = metrics.get("statistics") or {}
    try:
        return int(stats.get("seed_count") or 0)
    except (TypeError, ValueError):
        return 0


def _kill_tripped(verdict: dict[str, Any]) -> bool:
    return any(bool(k.get("tripped")) for k in (verdict.get("kill_criteria") or []))


def _best_key(entry: dict[str, Any]) -> tuple[int, int, int, int]:
    """max-key: (verdict favourability, any_significant, seed_count, feasibility)."""
    v = entry["verdict"]
    metrics = entry.get("metrics") or {}
    hyp = entry.get("hypothesis") or {}
    return (
        _VERDICT_FAVOURABILITY.get(v.get("verdict"), 0),
        1 if _any_significant(metrics) else 0,
        _seed_count(metrics),
        _feasibility_rank(hyp),
    )


def aggregate_portfolio(per_candidate: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-candidate verdicts into one honest portfolio verdict.

    ``per_candidate``: list of ``{candidate_id, title, hypothesis, metrics, verdict}``
    where ``verdict`` is an ``evidence.full_verdict`` result (already anchored to that
    candidate's own primary metric + kill criteria — every V2.2 gate applied
    independently).

    Returns ``{best_candidate_id, portfolio_verdict, summary, best_candidate, note}``.
    Best = the candidate with the most favourable **anchored** verdict (tie-break:
    any_significant → seed_count → feasibility). Never upgraded; an all-negative
    portfolio reports ``all_negative`` and still names a best (the highest anchor).
    """
    if not per_candidate:
        return {
            "best_candidate_id": None,
            "portfolio_verdict": "empty",
            "summary": [],
            "best_candidate": None,
            "note": _COST_NOTE,
        }

    best = max(per_candidate, key=_best_key)
    best_id = best.get("candidate_id")

    summary = [_summary_row(entry, entry is best) for entry in per_candidate]

    verdicts = {(entry.get("verdict") or {}).get("verdict") for entry in per_candidate}
    has_favourable = bool(verdicts & _FAVOURABLE)
    has_unfavourable = bool(verdicts & _UNFAVOURABLE)
    best_verdict = (best.get("verdict") or {}).get("verdict", "")
    if not has_favourable:
        portfolio_verdict = "all_negative"
    elif has_favourable and has_unfavourable:
        portfolio_verdict = "mixed_portfolio"
    else:
        portfolio_verdict = f"best={best_verdict}"

    return {
        "best_candidate_id": best_id,
        "portfolio_verdict": portfolio_verdict,
        "summary": summary,
        "best_candidate": best.get("hypothesis"),
        "note": _COST_NOTE,
    }


_COST_NOTE = (
    "Per V2.3 cost control, only the best candidate runs the Writer+Auditor; "
    "non-best candidates stop at metrics + anchored verdict."
)


def _summary_row(entry: dict[str, Any], is_best: bool) -> dict[str, Any]:
    v = entry.get("verdict") or {}
    metrics = entry.get("metrics") or {}
    hyp = entry.get("hypothesis") or {}
    return {
        "candidate_id": entry.get("candidate_id"),
        "title": entry.get("title") or hyp.get("title") or entry.get("candidate_id"),
        "primary_metric": v.get("primary_metric"),
        "beats_baseline": v.get("primary_beats_baseline"),
        "verdict": v.get("verdict"),
        "kill_tripped": _kill_tripped(v),
        "downgraded": bool(v.get("downgraded")),
        "execution_status": metrics.get("execution_status"),
        "feasibility": hyp.get("feasibility"),
        "is_best": is_best,
    }


__all__ = [
    "DEFAULT_K",
    "MAX_K",
    "rank_candidates",
    "select_portfolio",
    "aggregate_portfolio",
]
