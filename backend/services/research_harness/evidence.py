"""Shared evidence model for the V2 Writer + Auditor layer (Session 6).

Both the WriterAgent (builds the paper draft) and the AuditorAgent (gates the
draft's claims) must agree on what the experiment *actually* showed. This module
is the single source of truth that turns ``metrics.json`` into:

  - structured evidence items (for the Auditor's keyword-overlap matching), and
  - a human-readable evidence pack + honesty constraints (for the Writer prompt).

Keeping it in one place means a claim the Writer can legitimately make and a
claim the Auditor will accept are derived from the same numbers — there is no
drift between "what we told the writer" and "what the auditor checks against".
"""
from __future__ import annotations

import re
from typing import Any

# Words stripped before keyword extraction (small, English-only stoplist — matches
# the frozen claim_evidence_gate behavior closely enough for portable matching).
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
        "her", "was", "one", "our", "out", "has", "have", "from", "this", "that",
        "with", "were", "they", "their", "than", "then", "these", "those", "into",
        "over", "such", "some", "what", "which", "when", "where", "who", "whom",
        "its", "itself", "him", "his", "she", "she's", "him", "how", "why",
        "will", "would", "there", "been", "being", "more", "most", "very", "also",
        "method", "paper", "approach", "results", "result", "study", "work",
        "system", "model", "methods", "propose", "proposed", "we", "our", "is",
        "are", "was", "were", "be", "been", "being", "a", "an", "of", "to", "in",
        "on", "at", "by", "as", "or", "it", "do", "does", "did", "done",
    }
)

_TOKEN_RE = re.compile(r"[a-z][a-z0-9_]{2,}")


def keywords(text: str) -> set[str]:
    """Content tokens (3+ chars, lowercase, stop-stripped) used for overlap matching."""
    return {tok for tok in _TOKEN_RE.findall((text or "").lower()) if tok not in _STOPWORDS}


# --------------------------------------------------------------------------- #
# Status / verdict (shared by writer honesty + auditor gate rules)
# --------------------------------------------------------------------------- #


def significant_favorable_datasets(metrics: dict[str, Any]) -> set[str]:
    """Datasets on which the proposed method has a statistically significant FAVORABLE win.

    Mirrors report_generator: ``significant=True`` already encodes a favorable
    direction (the stats layer sets significant=False for a significantly-worse
    result), so we only need the significance flag + the dataset parsed from the
    test's ``detail``.
    """
    tests = (metrics.get("statistics") or {}).get("significance_tests") or []
    wins: set[str] = set()
    for t in tests:
        if not isinstance(t, dict) or not t.get("significant"):
            continue
        detail = t.get("detail") or ""
        if "dataset=" in detail:
            wins.add(detail.split("dataset=")[-1].split(":")[0].split(" ")[0])
    return wins


def has_significant_favorable(metrics: dict[str, Any]) -> bool:
    return bool(significant_favorable_datasets(metrics))


def verdict(metrics: dict[str, Any]) -> str:
    """Coarse honest verdict used to drive Writer framing + Auditor overclaim rules.

    One of: ``execution_failed`` · ``no_comparison`` · ``negative`` · ``mixed``
    · ``positive_significant`` · ``positive_not_significant``.
    """
    if metrics.get("execution_status") != "success":
        return "execution_failed"
    bc = metrics.get("baseline_comparison") or {}
    datasets = bc.get("datasets") or []
    if not datasets:
        return "no_comparison"
    overall = bc.get("overall_beats_baseline")
    sig = has_significant_favorable(metrics)
    if overall is True and sig:
        return "positive_significant"
    if overall is True:
        return "positive_not_significant"
    if sig:  # overall loses but a dataset significantly wins
        return "mixed"
    return "negative"


# --------------------------------------------------------------------------- #
# Structured evidence items (for the Auditor)
# --------------------------------------------------------------------------- #


def build_evidence_items(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten metrics.json into a list of evidence items the auditor matches claims against.

    Each item: ``{id, kind, summary, keywords}``. Kinds: ``comparison`` (per-dataset
    baseline vs proposed), ``significance`` (a significance test), ``metric`` (a raw
    numeric result row). Keyword sets make claim/evidence matching portable.
    """
    items: list[dict[str, Any]] = []

    bc = metrics.get("baseline_comparison") or {}
    for i, d in enumerate(bc.get("datasets") or []):
        if not isinstance(d, dict):
            continue
        summary = (
            f"on {d.get('dataset')}: proposed {d.get('proposed_system')}="
            f"{d.get('proposed_metric')} vs baseline {d.get('baseline_system')}="
            f"{d.get('baseline_metric')}; beats_baseline={d.get('beats_baseline')}; "
            f"delta={d.get('delta')}"
        )
        items.append(
            {"id": f"cmp_{i}", "kind": "comparison", "summary": summary, "keywords": keywords(summary)}
        )

    for i, t in enumerate((metrics.get("statistics") or {}).get("significance_tests") or []):
        if not isinstance(t, dict):
            continue
        detail = t.get("detail") or ""
        dataset = detail.split("dataset=")[-1].split(":")[0].split(" ")[0] if "dataset=" in detail else ""
        summary = (
            f"significance {dataset}: {t.get('candidate')} vs {t.get('comparator')} "
            f"significant={t.get('significant')} adjusted_p={t.get('adjusted_p_value')} "
            f"method={t.get('method')}"
        )
        items.append(
            {"id": f"sig_{i}", "kind": "significance", "summary": summary, "keywords": keywords(summary)}
        )

    # Raw per-seed rows → one metric item per (system, metric, dataset) mean is overkill;
    # expose the raw rows so a claim citing an exact value can still match. Cap to keep
    # the keyword set tractable (the comparison/significance items already carry the
    # aggregated numbers; these rows are a fallback for literal numbers).
    seen: set[str] = set()
    for i, r in enumerate((metrics.get("results") or [])[:60]):
        if not isinstance(r, dict):
            continue
        key = (str(r.get("system_name")), str(r.get("metric_name")), str(r.get("dataset_name")))
        if key in seen:
            continue
        seen.add(key)
        summary = (
            f"{r.get('system_name')} {r.get('metric_name')}={r.get('metric_value')} "
            f"on {r.get('dataset_name')} n_test={r.get('n_test')}"
        )
        items.append(
            {"id": f"met_{i}", "kind": "metric", "summary": summary, "keywords": keywords(summary)}
        )

    return items


# --------------------------------------------------------------------------- #
# Human-readable pack + constraints (for the Writer prompt)
# --------------------------------------------------------------------------- #


def _datasets_summary(metrics: dict[str, Any]) -> str:
    bc = metrics.get("baseline_comparison") or {}
    lines = []
    for d in bc.get("datasets") or []:
        if isinstance(d, dict):
            lines.append(
                f"- {d.get('dataset')}: proposed {d.get('proposed_system')}="
                f"{d.get('proposed_metric')} vs baseline {d.get('baseline_system')}="
                f"{d.get('baseline_metric')} (Δ{d.get('delta'):+.4f}, "
                f"beats_baseline={d.get('beats_baseline')}, "
                f"seeds b={d.get('n_seeds_baseline')}/p={d.get('n_seeds_proposed')})"
            )
    return "\n".join(lines) or "_(no baseline/proposed comparison available)_"


def _significance_summary(metrics: dict[str, Any]) -> str:
    tests = (metrics.get("statistics") or {}).get("significance_tests") or []
    if not tests:
        return "_(no significance test performed — single-run/descriptive only)_"
    lines = []
    for t in tests:
        if isinstance(t, dict):
            lines.append(
                f"- {t.get('detail')}: significant={t.get('significant')}, "
                f"adjusted_p={t.get('adjusted_p_value')}, effect={t.get('effect_size')}"
            )
    return "\n".join(lines)


def build_evidence_pack(metrics: dict[str, Any]) -> str:
    """Markdown block of the REAL numbers the Writer may cite. Verbatim source of truth."""
    v = verdict(metrics)
    return (
        f"- execution_status: {metrics.get('execution_status')}\n"
        f"- verdict: {v}\n"
        f"- overall_beats_baseline: {(metrics.get('baseline_comparison') or {}).get('overall_beats_baseline')}\n"
        f"- any_significant_favorable: {has_significant_favorable(metrics)}\n"
        f"- significant_favorable_datasets: {sorted(significant_favorable_datasets(metrics)) or '[]'}\n"
        f"- seed_count: {(metrics.get('statistics') or {}).get('seed_count')}\n\n"
        f"Per-dataset comparison:\n{_datasets_summary(metrics)}\n\n"
        f"Significance tests:\n{_significance_summary(metrics)}\n"
    )


def build_honesty_constraints(metrics: dict[str, Any]) -> str:
    """Plain-English honesty directive derived from the real verdict (drives Writer framing)."""
    v = verdict(metrics)
    sig_datasets = sorted(significant_favorable_datasets(metrics))
    bc = metrics.get("baseline_comparison") or {}
    lost = [d["dataset"] for d in bc.get("datasets") or [] if isinstance(d, dict) and d.get("beats_baseline") is False]

    if v == "execution_failed":
        return (
            "execution_status is NOT success: the experiment FAILED to produce results. "
            "The Results section MUST report the execution failure; do NOT invent any metric."
        )
    if v == "no_comparison":
        return (
            "No baseline/proposed comparison is available. Do NOT claim the method beats anything; "
            "report that the comparison could not be computed."
        )
    if v == "negative":
        return (
            "NEGATIVE result: the proposed method did NOT beat the baseline on any dataset, and no "
            "dataset showed a statistically significant favorable improvement. Frame this as a "
            "negative result. Do NOT use 'competitive', 'promising', or 'state-of-the-art'. Do NOT "
            "write 'significantly outperforms'."
        )
    if v == "mixed":
        return (
            f"MIXED result: the proposed method significantly outperformed the baseline ONLY on "
            f"{sig_datasets}, but did NOT win on every dataset (lost on: {lost or 'some datasets'}). "
            "State the win narrowly (name the winning dataset) and explicitly acknowledge the losses. "
            "Do NOT write 'outperforms across all datasets'. Do NOT use 'competitive'/'promising'."
        )
    if v == "positive_not_significant":
        return (
            "Positive trend but NOT statistically significant. You may say the method improved on "
            "the baseline, but you MUST add that the improvement was not statistically significant. "
            "Do NOT write 'significantly outperforms'."
        )
    # positive_significant
    return (
        f"Positive and statistically significant on {sig_datasets}. You MAY write "
        "'significantly outperforms' for those datasets only; do not generalize the significance "
        "claim to datasets where the test was not significant."
    )


__all__ = [
    "keywords",
    "significant_favorable_datasets",
    "has_significant_favorable",
    "verdict",
    "build_evidence_items",
    "build_evidence_pack",
    "build_honesty_constraints",
]
