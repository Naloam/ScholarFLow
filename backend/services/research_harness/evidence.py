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


def _base_verdict(metrics: dict[str, Any]) -> str:
    """Coarse honest verdict on the comparison metric (Session 6 behaviour, unchanged).

    One of: ``execution_failed`` · ``no_comparison`` · ``negative`` · ``mixed``
    · ``positive_significant`` · ``positive_not_significant``. This is the
    *generic-metric* verdict; :func:`full_verdict` may downgrade it once the
    hypothesis's own primary metric / kill criteria are taken into account.
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


def verdict(metrics: dict[str, Any], hypothesis: dict[str, Any] | None = None) -> str:
    """Honest verdict string. With no hypothesis this is byte-identical to the
    Session 6 behaviour (only-add-never-loosen). Passing the selected hypothesis
    anchors the verdict to the hypothesis's declared primary metric + executes
    its deterministic kill criteria, which may DOWNGRADE the verdict — never upgrade.
    """
    return full_verdict(metrics, hypothesis)["verdict"]


# --------------------------------------------------------------------------- #
# V2.2 hypothesis-anchored verdict + kill criteria (goal_session8.md Step 2)
# --------------------------------------------------------------------------- #
#
# The Session 7 hole: ``verdict(metrics)`` judged success on a generic metric
# (``macro_f1``) while the hypothesis actually cared about a *different* primary
# metric (an abstention / calibration target) that quietly failed — "plausible
# unsupported success" via a cherry-picked metric. The layer below anchors the
# verdict to the hypothesis's own primary metric and executes its kill criteria.
# All of it is pure logic, offline, deterministic. Anchoring / kill can only
# DOWNGRADE the verdict — never upgrade — so every prior honest gate is preserved.

# Verdict favourability rank (higher = more favourable). Used to clamp a downgrade.
_VERDICT_SEVERITY: dict[str, int] = {
    "execution_failed": 0,
    "no_comparison": 1,
    "negative": 2,
    "mixed": 3,
    "positive_not_significant": 4,
    "positive_significant": 5,
}

# Metric names whose value is better when LOWER (mirrors experiment_engineer).
_LOWER_IS_BETTER_HINTS: tuple[str, ...] = (
    "error", "loss", "wer", "perplexity", "rmse", "mae", "cer", "mer",
)


def _less_favourable(a: str, b: str) -> str:
    """Return whichever verdict is less favourable (lower severity rank)."""
    return a if _VERDICT_SEVERITY.get(a, 2) <= _VERDICT_SEVERITY.get(b, 2) else b


def _metric_lower_is_better(name: str) -> bool:
    n = (name or "").lower()
    return any(hint in n for hint in _LOWER_IS_BETTER_HINTS)


def _metric_names_in_metrics(metrics: dict[str, Any]) -> set[str]:
    """Every metric name the experiment actually produced a value for."""
    names: set[str] = set()
    bc = metrics.get("baseline_comparison") or {}
    if isinstance(bc.get("metric_name"), str) and bc["metric_name"].strip():
        names.add(bc["metric_name"])
    for key in (metrics.get("abstention_metrics") or {}):
        if isinstance(key, str):
            names.add(key)
    for r in metrics.get("results") or []:
        if isinstance(r, dict) and isinstance(r.get("metric_name"), str):
            names.add(r["metric_name"])
    return names


def _heuristic_metric(text: str, available: set[str]) -> str | None:
    """Map free-text (expected outcome / kill criteria) to a metric name that
    actually exists in ``available``, by head-word containment."""
    low = (text or "").lower()
    for name in sorted(available):
        if name.lower() in low:
            return name
        head = name.split("_")[0].lower()
        if len(head) >= 4 and head in low:
            return name
    return None


def primary_metric_for(hypothesis: dict[str, Any] | None, metrics: dict[str, Any]) -> dict[str, str]:
    """Resolve the hypothesis's primary metric to a name that exists in ``metrics``.

    Returns ``{"name", "source"}`` where ``source`` ∈
    ``{"hypothesis_declared", "heuristic", "comparison_default"}``. The default is
    the baseline-comparison metric (``macro_f1``) — i.e. when no primary can be
    resolved the verdict keeps its old behaviour.
    """
    bc_metric = (metrics.get("baseline_comparison") or {}).get("metric_name") or "macro_f1"
    available = _metric_names_in_metrics(metrics)
    if available:
        # Keep macro_f1 in the candidate set even if the comparison dict omitted it.
        available.add(bc_metric)
    else:
        available = {bc_metric}
    fallback = {"name": bc_metric, "source": "comparison_default"}
    if not hypothesis:
        return fallback

    declared = hypothesis.get("primary_metric")
    if isinstance(declared, str) and declared.strip():
        name = declared.strip()
        if name in available:
            return {"name": name, "source": "hypothesis_declared"}

    # Heuristic: scan the outcome + kill text for a metric name that exists.
    text = " ".join(
        [
            str(hypothesis.get("expected_positive_outcome", "")),
            str(hypothesis.get("expected_negative_outcome", "")),
            " ".join(str(c) for c in (hypothesis.get("kill_criteria") or [])),
            str(hypothesis.get("title", "")),
        ]
    )
    hit = _heuristic_metric(text, available)
    if hit:
        return {"name": hit, "source": "heuristic"}
    return fallback


def _mean_role(sys_map: dict[str, Any], role: str) -> float | None:
    """Mean value across systems whose name contains ``role`` (e.g. 'proposed')."""
    vals: list[float] = []
    for sysn, v in (sys_map or {}).items():
        if role in str(sysn).lower():
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue
    return sum(vals) / len(vals) if vals else None


def primary_metric_outcome(metrics: dict[str, Any], primary_metric: str) -> dict[str, Any]:
    """Did the proposed method beat the baseline on ``primary_metric``?

    Returns ``{"beats_baseline": bool|None, "any_significant": bool|None, "source"}``
    where ``source`` ∈ ``{"baseline_comparison", "abstention_metrics", "results",
    "not_found"}``. ``beats_baseline is None`` means it could not be determined
    (no baseline value, or metric absent) — which is NOT a downgrade trigger.
    """
    bc = metrics.get("baseline_comparison") or {}
    bc_metric = bc.get("metric_name")

    # macro_f1 / comparison path.
    if primary_metric == bc_metric or (primary_metric == "macro_f1" and bc_metric in (None, "macro_f1")):
        return {
            "beats_baseline": bc.get("overall_beats_baseline"),
            "any_significant": has_significant_favorable(metrics),
            "source": "baseline_comparison",
        }

    abstention = metrics.get("abstention_metrics") or {}
    if primary_metric in abstention and isinstance(abstention[primary_metric], dict):
        ds_map = abstention[primary_metric]
        lower_is_better = _metric_lower_is_better(primary_metric)
        per_dataset: list[dict[str, Any]] = []
        beats_all = True
        any_data = False
        for ds, sys_map in ds_map.items():
            if not isinstance(sys_map, dict):
                continue
            b = _mean_role(sys_map, "baseline")
            p = _mean_role(sys_map, "proposed")
            if b is None or p is None:
                continue
            any_data = True
            favorable = (p < b) if lower_is_better else (p > b)
            per_dataset.append({"dataset": ds, "baseline": b, "proposed": p, "beats": favorable})
            if not favorable:
                beats_all = False
        return {
            "beats_baseline": beats_all if any_data else None,
            "any_significant": None,  # abstention metrics are descriptive only
            "source": "abstention_metrics",
            "datasets": per_dataset,
        }

    # Raw results rows (proposed vs baseline on this metric).
    rows = [
        r for r in (metrics.get("results") or [])
        if isinstance(r, dict) and (r.get("metric_name") or "") == primary_metric
    ]
    if rows:
        proposed = [
            float(r["metric_value"]) for r in rows
            if "proposed" in (r.get("system_name") or "").lower() and "metric_value" in r
        ]
        baseline = [
            float(r["metric_value"]) for r in rows
            if "baseline" in (r.get("system_name") or "").lower() and "metric_value" in r
        ]
        if not proposed or not baseline:
            return {"beats_baseline": None, "any_significant": None, "source": "results"}
        p = sum(proposed) / len(proposed)
        b = sum(baseline) / len(baseline)
        beats = (p < b) if _metric_lower_is_better(primary_metric) else (p > b)
        return {"beats_baseline": beats, "any_significant": None, "source": "results"}

    return {"beats_baseline": None, "any_significant": None, "source": "not_found"}


# Threshold criterion: ``AUC<0.55`` / ``AUC 低于 0.55`` / ``spearman below 0.1``.
_KILL_THRESHOLD_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9_]*)\s*"
    r"(<=|>=|<|>|低于|小于|below|less than|高于|大于|above|greater than)\s*"
    r"([0-9]*\.?[0-9]+)"
)
_LOWER_OPS = ("<", "<=", "低于", "小于", "below", "less than")
_COMPARISON_CUES = (
    "相比", "相比无", "compared to", "compared with", " vs ", "versus",
    "over", "than", "outperform", "no improvement", "no significant improvement",
    "无显著", "无显著提升", "不超过", "未超过", "低于", "劣于",
)


def _proposed_metric_value(metrics: dict[str, Any], keyword: str) -> float | None:
    """The proposed method's value for ``keyword`` (mean across datasets/seeds)."""
    kw = (keyword or "").lower()
    proposed: list[float] = []
    for r in metrics.get("results") or []:
        if not isinstance(r, dict):
            continue
        if (r.get("metric_name") or "").lower() == kw and "proposed" in (r.get("system_name") or "").lower():
            try:
                proposed.append(float(r["metric_value"]))
            except (TypeError, ValueError, KeyError):
                continue
    if proposed:
        return sum(proposed) / len(proposed)

    abstention = metrics.get("abstention_metrics") or {}
    for key, ds_map in abstention.items():
        if key.lower() != kw or not isinstance(ds_map, dict):
            continue
        vals = [
            float(v) for sysn, v in _flatten_role_values(ds_map).items() if "proposed" in sysn.lower()
        ]
        if vals:
            return sum(vals) / len(vals)

    bc = metrics.get("baseline_comparison") or {}
    if (bc.get("metric_name") or "").lower() == kw:
        p_vals = [
            float(d["proposed_metric"]) for d in bc.get("datasets") or []
            if isinstance(d, dict) and "proposed_metric" in d
        ]
        if p_vals:
            return sum(p_vals) / len(p_vals)
    return None


def _flatten_role_values(ds_map: dict[str, Any]) -> dict[str, float]:
    """Flatten ``{dataset: {system: value}}`` → ``{system: [values]}``-ish mean per system."""
    out: dict[str, list[float]] = {}
    for sys_map in ds_map.values():
        if not isinstance(sys_map, dict):
            continue
        for sysn, v in sys_map.items():
            try:
                out.setdefault(str(sysn), []).append(float(v))
            except (TypeError, ValueError):
                continue
    return {sysn: sum(vs) / len(vs) for sysn, vs in out.items()}


def _eval_threshold_criterion(criterion: str, metrics: dict[str, Any]) -> dict[str, Any] | None:
    m = _KILL_THRESHOLD_RE.search(criterion)
    if not m:
        return None
    metric_kw, op, threshold_str = m.group(1), m.group(2), m.group(3)
    threshold = float(threshold_str)
    value = _proposed_metric_value(metrics, metric_kw)
    if value is None:
        return _manual(criterion, f"threshold metric '{metric_kw}' not present in metrics; cannot evaluate")
    tripped = (value < threshold) if op in _LOWER_OPS else (value > threshold)
    reason = (
        f"{metric_kw}={value:.4f} {'<' if op in _LOWER_OPS else '>'} {threshold} → "
        f"{'kill criterion tripped' if tripped else 'not tripped'}"
    )
    return {
        "criterion": criterion,
        "tripped": bool(tripped),
        "needs_manual": False,
        "reason": reason,
        "metric": metric_kw,
        "value": value,
        "threshold": threshold,
    }


def _eval_comparison_criterion(criterion: str, metrics: dict[str, Any]) -> dict[str, Any]:
    """Comparison-style kill ('no improvement over X'). Trips only when the named
    system X is present in results AND the proposed method did not beat it; if X is
    absent the criterion is ``needs_manual`` (we never trip on an unevaluable claim)."""
    results = [r for r in (metrics.get("results") or []) if isinstance(r, dict)]
    system_names = {(r.get("system_name") or "") for r in results}
    lowered = criterion.lower()
    # Find a named comparison system mentioned in the criterion that exists in results.
    matched_system: str | None = None
    for sysn in system_names:
        if not sysn:
            continue
        if sysn.lower() in lowered or _token_in(sysn, lowered):
            if "proposed" not in sysn.lower():  # the comparator, not the proposed method itself
                matched_system = sysn
                break
    if matched_system is None:
        return _manual(criterion, "named comparison baseline not present in results; cannot evaluate")
    # Did proposed beat matched_system on their shared metric(s)?
    proposed_better = _proposed_beats_system(results, "proposed", matched_system)
    if proposed_better is None:
        return _manual(criterion, f"could not compare proposed vs '{matched_system}' on a shared metric")
    tripped = not proposed_better
    return {
        "criterion": criterion,
        "tripped": tripped,
        "needs_manual": False,
        "reason": (
            f"proposed did beat '{matched_system}'" if not tripped
            else f"proposed did NOT beat '{matched_system}' → kill criterion tripped"
        ),
        "metric": None,
        "value": None,
        "threshold": None,
    }


def _token_in(system_name: str, lowered_text: str) -> bool:
    """True if any distinctive token of ``system_name`` appears in the criterion text."""
    for tok in re.split(r"[\s_\-]+", system_name):
        if len(tok) >= 4 and tok.lower() in lowered_text:
            return True
    return False


def _proposed_beats_system(results: list[dict[str, Any]], proposed_name: str, other_name: str) -> bool | None:
    """Per-metric: does the proposed system beat ``other_name`` (respecting direction)?"""
    wins_any = False
    decided = False
    by_system: dict[str, dict[str, list[float]]] = {}
    for r in results:
        sysn = (r.get("system_name") or "").lower()
        metric = r.get("metric_name") or ""
        try:
            val = float(r["metric_value"])
        except (TypeError, ValueError, KeyError):
            continue
        bucket = by_system.setdefault(sysn, {}).setdefault(metric, [])
        bucket.append(val)
    p = by_system.get(proposed_name.lower(), {})
    o = by_system.get(other_name.lower(), {})
    for metric, p_vals in p.items():
        o_vals = o.get(metric)
        if not o_vals:
            continue
        lower_is_better = _metric_lower_is_better(metric)
        p_mean = sum(p_vals) / len(p_vals)
        o_mean = sum(o_vals) / len(o_vals)
        favorable = (p_mean < o_mean) if lower_is_better else (p_mean > o_mean)
        decided = True
        if favorable:
            wins_any = True
    return wins_any if decided else None


def _manual(criterion: str, reason: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "tripped": False,
        "needs_manual": True,
        "reason": reason,
        "metric": None,
        "value": None,
        "threshold": None,
    }


def evaluate_kill_criteria(hypothesis: dict[str, Any] | None, metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministically evaluate each ``hypothesis.kill_criteria`` string.

    Each result: ``{criterion, tripped, needs_manual, reason, metric, value, threshold}``.
    Threshold-type criteria (``AUC<0.55``) trip when the metric is present and the
    threshold holds. Comparison-type criteria (``no improvement over X``) trip only
    when ``X`` is in the results and the proposed method lost; otherwise they are
    ``needs_manual`` (never silently tripped). Returns ``[]`` when there is no
    hypothesis or no kill criteria.
    """
    if not hypothesis:
        return []
    criteria = hypothesis.get("kill_criteria")
    if not isinstance(criteria, list):
        return []
    out: list[dict[str, Any]] = []
    for c in criteria:
        if not isinstance(c, str) or not c.strip():
            continue
        evaluated = _eval_threshold_criterion(c, metrics)
        if evaluated is not None:
            out.append(evaluated)
            continue
        if any(cue in c.lower() for cue in _COMPARISON_CUES):
            out.append(_eval_comparison_criterion(c, metrics))
        else:
            out.append(_manual(c, "criterion is not a parseable threshold or comparison; cannot evaluate"))
    return out


# --------------------------------------------------------------------------- #
# Idea-time kill-criterion validation (goal_session10 Step 6)
# --------------------------------------------------------------------------- #

# Metric names the claim-verification experiments actually produce (V2.2/V2.3).
_STANDARD_METRICS: tuple[str, ...] = (
    "macro_f1", "accuracy", "auc",
    "error_rate_at_20pct_abstain", "spearman_consistency_vs_label",
)

_STOPWORD_TOKENS: frozenset[str] = frozenset({
    "the", "and", "for", "not", "with", "that", "this", "when", "if", "than",
    "method", "baseline", "criterion", "kill", "drop", "abandon", "stop",
    "result", "metric", "proposed", "ablation",
})


def _looks_like_metric(token: str, avail: set[str]) -> bool:
    """A plausible metric identifier: a known metric, or a snake_case name."""
    low = token.lower()
    if low in avail:
        return True
    return "_" in low and len(low) >= 4 and low not in _STOPWORD_TOKENS


def _suggest_kill_rewrite(criterion: str, available_metrics: list[str]) -> str:
    """Deterministic rewrite hint for an unparseable kill criterion."""
    avail = {m.lower() for m in available_metrics}
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]*", criterion or "")
    picked = next((t.lower() for t in tokens if _looks_like_metric(t, avail)), None)
    if picked is None:
        picked = next((t.lower() for t in tokens if t.lower() not in _STOPWORD_TOKENS), None)
    if picked is None:
        return "rewrite as: '<metric_name> < 0.5' (threshold) or '<metric_name> 相比 baseline 未提升' (comparison)"
    return f"{picked} 相比 baseline 未提升"


def _validate_one_kill_criterion(criterion: str, available_metrics: list[str]) -> dict[str, Any]:
    m = _KILL_THRESHOLD_RE.search(criterion)
    if m:
        return {
            "criterion": criterion,
            "parseable": True,
            "kind": "threshold",
            "metric": m.group(1).lower(),
        }
    avail = {x.lower() for x in available_metrics}
    has_baseline = "baseline" in criterion.lower()
    metric = next(
        (t.lower() for t in re.findall(r"[A-Za-z][A-Za-z0-9_]*", criterion)
         if _looks_like_metric(t, avail)),
        None,
    )
    if has_baseline and metric:
        return {
            "criterion": criterion,
            "parseable": True,
            "kind": "comparison",
            "metric": metric,
        }
    return {
        "criterion": criterion,
        "parseable": False,
        "kind": None,
        "metric": None,
        "reason": (
            "not a parseable threshold (`<metric> <op> <number>`) "
            "or comparison (`<metric> 相比 baseline <op>`)"
        ),
        "suggested_rewrite": _suggest_kill_rewrite(criterion, available_metrics),
    }


def validate_kill_criteria(
    hypothesis: dict[str, Any] | None,
    available_metrics: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Idea-time check: is each ``hypothesis.kill_criteria`` mechanically parseable?

    Pure, deterministic, network-free — the gate that refuses to *silently* let a
    free-text kill criterion through (goal_session10 Step 6). For each criterion
    returns ``{criterion, parseable, kind, metric}`` and, when not parseable, a
    ``reason`` + ``suggested_rewrite``. The IdeaAgent marks candidates with
    unparseable criteria and demotes them, so live-run kill criteria are no longer
    all ``needs_manual`` at evaluation time. ``available_metrics`` defaults to the
    standard claim-verification metric set.
    """
    if not hypothesis:
        return []
    criteria = hypothesis.get("kill_criteria")
    if not isinstance(criteria, list):
        return []
    avail = list(available_metrics) if available_metrics else list(_STANDARD_METRICS)
    return [
        _validate_one_kill_criterion(c, avail)
        for c in criteria
        if isinstance(c, str) and c.strip()
    ]


def full_verdict(metrics: dict[str, Any], hypothesis: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verdict anchored to the hypothesis's primary metric + kill criteria.

    Returns ``{verdict, base_verdict, primary_metric, primary_metric_source,
    primary_beats_baseline, kill_criteria, downgraded, downgrade_reasons}``.
    ``base_verdict`` is the Session 6 generic-metric verdict; ``verdict`` is
    ``base_verdict`` possibly DOWNGRADED (never upgraded) when the hypothesis's
    own primary metric demonstrably lost or a deterministic kill criterion tripped.
    With ``hypothesis=None`` the result is the old behaviour exactly.
    """
    base = _base_verdict(metrics)
    bc_metric = (metrics.get("baseline_comparison") or {}).get("metric_name") or "macro_f1"
    if hypothesis is None:
        return {
            "verdict": base,
            "base_verdict": base,
            "primary_metric": bc_metric,
            "primary_metric_source": "comparison_default",
            "primary_beats_baseline": (metrics.get("baseline_comparison") or {}).get("overall_beats_baseline"),
            "kill_criteria": [],
            "downgraded": False,
            "downgrade_reasons": [],
        }

    pm = primary_metric_for(hypothesis, metrics)
    outcome = primary_metric_outcome(metrics, pm["name"])
    kill = evaluate_kill_criteria(hypothesis, metrics)
    tripped = [k for k in kill if k["tripped"]]

    verdict = base
    reasons: list[str] = []

    # Primary-metric anchoring: success cannot be claimed on a different metric.
    if outcome["beats_baseline"] is False:
        verdict = _less_favourable(verdict, "negative")
        reasons.append(
            f"primary metric '{pm['name']}' did not beat the baseline "
            f"(source={outcome['source']}); success cannot be claimed on another metric"
        )

    # Deterministic kill-criterion trip → downgrade (never loosen).
    if tripped:
        verdict = _less_favourable(verdict, "negative")
        reasons.append("kill criterion tripped: " + "; ".join(t["criterion"] for t in tripped))

    downgraded = _VERDICT_SEVERITY[verdict] < _VERDICT_SEVERITY[base]
    return {
        "verdict": verdict,
        "base_verdict": base,
        "primary_metric": pm["name"],
        "primary_metric_source": pm["source"],
        "primary_beats_baseline": outcome["beats_baseline"],
        "kill_criteria": kill,
        "downgraded": downgraded,
        "downgrade_reasons": reasons,
    }


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


def build_evidence_pack(metrics: dict[str, Any], hypothesis: dict[str, Any] | None = None) -> str:
    """Markdown block of the REAL numbers the Writer may cite. Verbatim source of truth.

    When ``hypothesis`` is supplied the pack also carries the hypothesis-anchored
    verdict (primary metric + any tripped kill criteria), so the Writer frames the
    result on the metric the hypothesis actually cared about — not a generic one.
    """
    fv = full_verdict(metrics, hypothesis)
    lines = [
        f"- execution_status: {metrics.get('execution_status')}",
        f"- verdict: {fv['verdict']} (base_verdict: {fv['base_verdict']})",
        f"- primary_metric: {fv['primary_metric']} (source: {fv['primary_metric_source']}; "
        f"beats_baseline: {fv['primary_beats_baseline']})",
        f"- overall_beats_baseline: {(metrics.get('baseline_comparison') or {}).get('overall_beats_baseline')}",
        f"- any_significant_favorable: {has_significant_favorable(metrics)}",
        f"- significant_favorable_datasets: {sorted(significant_favorable_datasets(metrics)) or '[]'}",
        f"- seed_count: {(metrics.get('statistics') or {}).get('seed_count')}",
    ]
    if fv["downgraded"]:
        lines.append(f"- ⚠ DOWNGRADED from {fv['base_verdict']} to {fv['verdict']}:")
        lines.extend(f"  - {r}" for r in fv["downgrade_reasons"])
    tripped = [k for k in fv["kill_criteria"] if k["tripped"]]
    if tripped:
        lines.append("- kill criteria tripped:")
        lines.extend(f"  - {k['criterion']} ({k['reason']})" for k in tripped)
    abstention = metrics.get("abstention_metrics") or {}
    if abstention:
        lines.append(f"- abstention_metrics present: {sorted(abstention.keys())}")
    head = "\n".join(lines)
    return (
        f"{head}\n\n"
        f"Per-dataset comparison:\n{_datasets_summary(metrics)}\n\n"
        f"Significance tests:\n{_significance_summary(metrics)}\n"
    )


# --------------------------------------------------------------------------- #
# Coverage lint (V2.1 quality loop — deterministic, no LLM, no network)
# --------------------------------------------------------------------------- #

# Numbers worth checking: decimals (0.003, 0.966501), p-values (p=0.03, p<0.05),
# deltas (Δ+0.0335). We capture the optional p=/Δ prefix for display but match
# on the decimal body. Integers alone (seed counts, n) are too noisy to lint, so
# only floating-point quantities are checked — the things the Writer is most
# tempted to invent or drift.
_LINT_NUMBER_RE = re.compile(r"(?:p\s*[=<≤]?\s*|Δ\s*[+\-]?|delta\s*[+\-]?)?\d+\.\d+")
_DECIMAL_BODY_RE = re.compile(r"\d+\.\d+")


def _decimal_places(token: str) -> int:
    """Decimal places in a numeric token (``1.000``→3, ``0.003``→3, ``0.966501``→6)."""
    m = _DECIMAL_BODY_RE.search(token)
    if not m:
        return 0
    return len(m.group(0).split(".", 1)[1])


def _pack_numbers(metrics: dict[str, Any]) -> list[float]:
    """Every decimal the experiment actually produced — from the readable evidence
    pack AND the raw metrics JSON, so a draft citing an exact stored value still
    matches even when the human-readable pack rounded it."""
    import json

    sources = [build_evidence_pack(metrics)]
    try:
        sources.append(json.dumps(metrics, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        pass
    nums: list[float] = []
    for text in sources:
        for m in _DECIMAL_BODY_RE.finditer(text or ""):
            try:
                nums.append(float(m.group(0)))
            except ValueError:
                continue
    return nums


def coverage_lint(draft_text: str, metrics: dict[str, Any]) -> list[dict[str, str]]:
    """Flag draft numbers that have no root in the real evidence pack.

    Pure logic, offline, no LLM. A draft decimal is *covered* when some pack
    number rounds (to the draft's own precision) to the same value — so honest
    rounding (``0.967`` ← ``0.966501``, ``1.000`` ← ``1.0``) passes, while a
    fabricated number (``0.999``, ``p=0.0001``) that no experiment produced is
    flagged. The bounded ``revise_on_lint`` step feeds these flags back to the
    Writer for a single corrective pass. Returns ``[{token, reason}, ...]``.
    """
    pack = _pack_numbers(metrics)
    # Strip LEADING section numbers from markdown headings (``### 3.1 Title`` → ``### Title``).
    # Those ``\d+\.\d+`` tokens are structural section refs, not experimental metrics —
    # flagging them (surfaced by the Session 7 live run on GLM-5.2, which numbers its
    # headings) produced false positives that the bounded revise then stripped. A real
    # metric appearing mid-heading is unaffected; only the leading ``N.N`` after ``#`` is.
    body = re.sub(r"^(#{1,6}\s+)\d+(?:\.\d+)*\s+", r"\1", draft_text or "", flags=re.MULTILINE)
    flags: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in _LINT_NUMBER_RE.finditer(body):
        token = m.group(0).strip()
        dec = _DECIMAL_BODY_RE.search(token)
        if not dec:
            continue
        try:
            value = float(dec.group(0))
        except ValueError:
            continue
        if token in seen:
            continue
        places = _decimal_places(token)
        covered = any(round(p, places) == value for p in pack)
        if covered:
            continue
        seen.add(token)
        flags.append({"token": token, "reason": f"number {token!r} not found in experimental evidence"})
    return flags


def json_dumps_compact(metrics: dict[str, Any]) -> str:
    """Compact JSON of the metrics — re-exported so callers/tests can build the
    same string the coverage pool uses. Kept here for a single source of truth."""
    import json

    try:
        return json.dumps(metrics, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return ""


def build_honesty_constraints(metrics: dict[str, Any], hypothesis: dict[str, Any] | None = None) -> str:
    """Plain-English honesty directive derived from the real verdict (drives Writer framing).

    With ``hypothesis`` the directive is built on the hypothesis-anchored verdict,
    so a downgrade (primary metric lost / kill criterion tripped) forces honest
    framing even when a generic metric looked favourable.
    """
    fv = full_verdict(metrics, hypothesis)
    v = fv["verdict"]
    sig_datasets = sorted(significant_favorable_datasets(metrics))
    bc = metrics.get("baseline_comparison") or {}
    lost = [d["dataset"] for d in bc.get("datasets") or [] if isinstance(d, dict) and d.get("beats_baseline") is False]

    anchor_note = ""
    if hypothesis and fv["downgraded"]:
        anchor_note = (
            f"\n\n⚠ Hypothesis-anchored honesty: the verdict was DOWNGRADED from "
            f"{fv['base_verdict']} to {v} because the hypothesis's primary metric "
            f"'{fv['primary_metric']}' did not meet its bar "
            f"(beats_baseline={fv['primary_beats_baseline']}). You MUST frame the paper around "
            f"this anchored verdict and report the primary metric's outcome honestly. "
            "Do NOT claim success by citing a different, favourable metric."
        )
    if v == "execution_failed":
        directive = (
            "execution_status is NOT success: the experiment FAILED to produce results. "
            "The Results section MUST report the execution failure; do NOT invent any metric."
        )
    elif v == "no_comparison":
        directive = (
            "No baseline/proposed comparison is available. Do NOT claim the method beats anything; "
            "report that the comparison could not be computed."
        )
    elif v == "negative":
        directive = (
            "NEGATIVE result: the proposed method did NOT beat the baseline on any dataset, and no "
            "dataset showed a statistically significant favorable improvement. Frame this as a "
            "negative result. Do NOT use 'competitive', 'promising', or 'state-of-the-art'. Do NOT "
            "write 'significantly outperforms'."
        )
    elif v == "mixed":
        directive = (
            f"MIXED result: the proposed method significantly outperformed the baseline ONLY on "
            f"{sig_datasets}, but did NOT win on every dataset (lost on: {lost or 'some datasets'}). "
            "State the win narrowly (name the winning dataset) and explicitly acknowledge the losses. "
            "Do NOT write 'outperforms across all datasets'. Do NOT use 'competitive'/'promising'."
        )
    elif v == "positive_not_significant":
        directive = (
            "Positive trend but NOT statistically significant. You may say the method improved on "
            "the baseline, but you MUST add that the improvement was not statistically significant. "
            "Do NOT write 'significantly outperforms'."
        )
    else:  # positive_significant
        directive = (
            f"Positive and statistically significant on {sig_datasets}. You MAY write "
            "'significantly outperforms' for those datasets only; do not generalize the significance "
            "claim to datasets where the test was not significant."
        )
    return directive + anchor_note


__all__ = [
    "keywords",
    "significant_favorable_datasets",
    "has_significant_favorable",
    "verdict",
    "primary_metric_for",
    "primary_metric_outcome",
    "evaluate_kill_criteria",
    "validate_kill_criteria",
    "full_verdict",
    "build_evidence_items",
    "build_evidence_pack",
    "build_honesty_constraints",
    "coverage_lint",
    "json_dumps_compact",
]
