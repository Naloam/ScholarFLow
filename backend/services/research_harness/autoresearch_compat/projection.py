"""Projection: NEW research_harness workspace → OLD autoresearch JSON shapes.

Session 13 (plan §7 P2 — "逐步降级为读取新 workspace 文件的兼容层"). Every function
here is a pure reader over the new workspace; none reconstruct the old
keyword→template thinking. The dicts returned match the documented field names of
the legacy schemas (``ResultArtifact``, ``AutoResearchRunRead``,
``HypothesisCandidate``, ``PortfolioSummary``) so legacy JSON consumers keep
working. Where the new workspace carries no analogue, fields fall back to the
same defaults the old schema declares — never to fabricated signal.

All reads go through :mod:`services.research_harness.pipeline` so tests isolate
the workspace by monkeypatching ``pipeline.WORKSPACE_ROOT``.
"""
from __future__ import annotations

import json
from typing import Any

from services.research_harness import pipeline

# New-workspace status → old AutoResearchRunStatus mapping.
# (old Literal: "queued" | "running" | "done" | "failed" | "canceled")
_STATUS_MAP: dict[str, str] = {
    "done": "done",
    "running": "running",
    "error": "failed",
    "partial": "running",
    "pending": "queued",
}


def _read_json(path: Any, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def _read_text(path: Any) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return ""


# --------------------------------------------------------------------------- #
# ResultArtifact (artifact.json) projection
# --------------------------------------------------------------------------- #


def legacy_artifact(project_id: str) -> dict:
    """Project ``artifacts/metrics.json`` into the ``ResultArtifact`` shape.

    Carries the honest signal the new brain produced (execution status, baseline
    comparison deltas, significance tests, seed count) under the old field names.
    Never invents metrics that are absent.
    """
    metrics = pipeline.load_metrics(project_id)
    execution_status = metrics.get("execution_status") if isinstance(metrics, dict) else None
    if execution_status == "success":
        status = "done"
    elif execution_status:
        status = "failed"
    else:
        status = "queued"

    baseline_comparison = metrics.get("baseline_comparison") or {}
    primary_metric = (
        baseline_comparison.get("metric_name")
        or metrics.get("primary_metric")
        or ""
    )
    datasets = baseline_comparison.get("datasets") or []
    overall_beats = bool(baseline_comparison.get("overall_beats_baseline"))

    key_findings: list[str] = []
    for row in datasets:
        key_findings.append(
            f"{row.get('proposed_system', 'proposed')} vs "
            f"{row.get('baseline_system', 'baseline')} on {row.get('dataset')}: "
            f"delta={row.get('delta')} beats_baseline={row.get('beats_baseline')}"
        )

    # Per-system, per-seed rows → SystemMetricResult shape.
    system_results: list[dict] = []
    for res in metrics.get("results") or []:
        metric_name = res.get("metric_name", "")
        system_results.append(
            {
                "system": res.get("system_name", ""),
                "metrics": {metric_name: res.get("metric_value", 0.0)},
                "notes": (
                    f"dataset={res.get('dataset_name')} seed={res.get('seed')} "
                    f"n={res.get('n_test_examples')}"
                ),
            }
        )

    # baseline_comparison.datasets → AggregateSystemMetricResult rows for both systems.
    aggregate_system_results: list[dict] = []
    for row in datasets:
        for system, metric_value, sample_count in (
            (row.get("baseline_system", "baseline"),
             row.get("baseline_metric", 0.0), row.get("n_seeds_baseline", 1)),
            (row.get("proposed_system", "proposed"),
             row.get("proposed_metric", 0.0), row.get("n_seeds_proposed", 1)),
        ):
            aggregate_system_results.append(
                {
                    "system": system,
                    "mean_metrics": {primary_metric: metric_value},
                    "std_metrics": {},
                    "confidence_intervals": {},
                    "min_metrics": {},
                    "max_metrics": {},
                    "sample_count": sample_count,
                }
            )

    statistics = metrics.get("statistics") or {}
    significance_tests: list[dict] = []
    for sig in statistics.get("significance_tests") or []:
        significance_tests.append(
            {
                "scope": "aggregate",
                "metric": primary_metric,
                "candidate": sig.get("candidate", ""),
                "comparator": sig.get("comparator", ""),
                "method": sig.get("method", "paired_sign_flip"),
                "p_value": sig.get("adjusted_p_value", sig.get("p_value", 0.0)),
                "adjusted_p_value": sig.get("adjusted_p_value"),
                "effect_size": sig.get("effect_size", 0.0),
                "significant": bool(sig.get("significant", False)),
                "sample_count": statistics.get("seed_count", 0),
                "detail": sig.get("detail", ""),
            }
        )

    proposed_metric = datasets[0].get("proposed_metric") if datasets else None

    return {
        "status": status,
        "summary": (
            f"execution_status={execution_status or 'unknown'}; "
            f"overall_beats_baseline={overall_beats} "
            f"(projected from research_harness metrics.json)"
        ),
        "key_findings": key_findings,
        "primary_metric": primary_metric,
        "best_system": ("proposed" if overall_beats else "baseline") if datasets else None,
        "system_results": system_results,
        "aggregate_system_results": aggregate_system_results,
        "per_seed_results": [],
        "sweep_results": [],
        "significance_tests": significance_tests,
        "power_analysis_notes": [],
        "negative_results": [],
        "failed_trials": [],
        "anomalous_trials": [],
        "acceptance_checks": [],
        "tables": [],
        "logs": None,
        "environment": {},
        "outputs": {},
        "objective_system": "proposed" if overall_beats else None,
        "objective_score": proposed_metric,
    }


# --------------------------------------------------------------------------- #
# HypothesisCandidate list projection
# --------------------------------------------------------------------------- #


def legacy_candidates(project_id: str) -> list[dict]:
    """Project ``ideas/candidates.json`` into ``HypothesisCandidate``-shaped dicts."""
    proj = pipeline.project_dir(project_id)
    candidates = _read_json(proj / "ideas" / "candidates.json", [])
    if not isinstance(candidates, list):
        return []
    out: list[dict] = []
    for idx, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            continue
        out.append(
            {
                "id": cand.get("hypothesis_id", cand.get("id", f"h{idx}")),
                "program_id": project_id,
                "rank": cand.get("rank", idx),
                "portfolio_role": cand.get("portfolio_role"),
                "diversity_axis": cand.get("diversity_axis"),
                "title": cand.get("title", cand.get("hypothesis_id", "")),
                "hypothesis": cand.get("research_question", cand.get("hypothesis", "")),
                "proposed_method": cand.get("proposed_method_sketch", cand.get("proposed_method", "")),
                "rationale": cand.get("rationale", cand.get("core_novelty", "")),
                "planned_contributions": cand.get("planned_contributions", []),
                "differentiators": cand.get("differentiators", []),
                "search_strategies": cand.get("search_strategies", []),
                "status": cand.get("status", "planned"),
                "score": cand.get("score"),
                "selection_reason": cand.get("selection_reason"),
                "workspace_path": f"candidates/{cand.get('hypothesis_id', cand.get('id', ''))}" if cand.get("hypothesis_id") or cand.get("id") else None,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# PortfolioSummary projection
# --------------------------------------------------------------------------- #


def legacy_portfolio(project_id: str) -> dict | None:
    """Project ``ledger/portfolio.json`` into the ``PortfolioSummary`` shape.

    Returns ``None`` for single-candidate (non-portfolio) workspaces — the old
    field was nullable and a non-portfolio run legitimately has no portfolio.
    """
    proj = pipeline.project_dir(project_id)
    ledger = _read_json(proj / "ledger" / "portfolio.json", None)
    if not isinstance(ledger, dict):
        return None
    summary = ledger.get("summary") or []
    best = ledger.get("best_candidate_id")
    executed = [row.get("candidate_id") for row in summary if isinstance(row, dict)]
    return {
        "status": "executed",
        "total_candidates": len(summary),
        "candidate_rankings": executed,
        "executed_candidate_ids": executed,
        "selected_candidate_id": best,
        "selection_policy": "anchored_verdict_maximize",
        "decision_summary": (
            f"portfolio_verdict={ledger.get('portfolio_verdict', 'unknown')}; "
            f"best={best}. {ledger.get('note', '')}".strip()
        ),
        "winning_score": None,
        "decisions": [],
    }


# --------------------------------------------------------------------------- #
# AutoResearchRunRead (run.json) projection
# --------------------------------------------------------------------------- #


def legacy_run(project_id: str) -> dict | None:
    """Project the whole new workspace into the ``AutoResearchRunRead`` shape.

    Returns ``None`` if the workspace does not exist (the old ``load_run`` also
    signalled absence). ``run_id == project_id`` per the V0 one-run-per-workspace
    contract.
    """
    meta = pipeline.read_project_meta(project_id)
    if meta is None:
        return None

    new_status = meta.get("status", "pending")
    created_at = meta.get("created_at")
    updated_at = meta.get("updated_at")

    candidates = legacy_candidates(project_id)
    portfolio = legacy_portfolio(project_id)
    selected_id = None
    if portfolio and portfolio.get("selected_candidate_id"):
        selected_id = portfolio["selected_candidate_id"]
    elif candidates:
        selected_id = candidates[0]["id"]

    proj = pipeline.project_dir(project_id)
    paper_path = proj / "paper" / "draft.md"
    code_path = proj / "code" / "experiment.py"
    paper_markdown = _read_text(paper_path) or None

    return {
        "id": project_id,
        "project_id": project_id,
        "topic": meta.get("idea", project_id),
        "status": _STATUS_MAP.get(new_status, "queued"),
        "brief_id": None,
        "hypothesis_id": selected_id,
        "direction_selection_reason": None,
        "request": None,
        "task_family": None,
        "benchmark": None,
        "execution_backend": None,
        "program": None,
        "plan": None,
        "spec": None,
        "literature": [],
        "literature_synthesis": None,
        "narrative_analysis": None,
        "candidates": candidates,
        "portfolio": portfolio,
        "attempts": [],
        "artifact": legacy_artifact(project_id),
        "generated_code_path": "code/experiment.py" if code_path.exists() else None,
        "paper_path": "paper/draft.md" if paper_path.exists() else None,
        "paper_markdown": paper_markdown,
        "error": None,
        "created_at": created_at,
        "updated_at": updated_at,
    }
