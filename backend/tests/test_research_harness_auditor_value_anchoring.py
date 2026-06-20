"""Session 17 — value-anchored omission gate (only-add regression test).

Closes the root-cause hole that Session 16's rescue worked around. The Writer
produces drafts (often Chinese) that report a material metric's REAL measured
value (e.g. ``0.025962``) without using the canonical English metric name. The
V2.2 omitted-material gate matched only the English name / English distinctive
tokens (``_metric_mentioned``), so such a draft was misjudged as "omitted" even
though it honestly reported the number.

Value-anchoring (S17 candidate #1, cheapest): a material metric is treated as
"discussed" when the draft contains one of its real measured values from
``metrics.json`` — in addition to (not instead of) the English-name match.

**Only-add / never-loosen**: a metric genuinely absent from the draft (neither
its name nor any of its real values) is still flagged. Anchors are restricted to
DISTINCTIVE values (≥4 significant digits) so a generic number like ``0.9`` or
``1.0`` can't coincidentally clear a real omission.

Deterministic, offline, network-free.
"""
from __future__ import annotations

from services.research_harness import auditor


def _calibration_metrics() -> dict:
    """baseline_comparison carries the summary values the Writer copies into prose
    (proposed 0.025962 vs baseline 0.047393). results[] carries per-seed values."""
    return {
        "execution_status": "success",
        "baseline_comparison": {
            "metric_name": "calibration_error",
            "direction": "lower_is_better",
            "overall_beats_baseline": True,
            "datasets": [
                {
                    "dataset": "breast_cancer_tabular",
                    "baseline_metric": 0.047393,
                    "proposed_metric": 0.025962,
                    "delta": -0.021431,
                    "beats_baseline": True,
                }
            ],
        },
        "results": [
            {"system_name": "baseline_svm", "metric_name": "calibration_error",
             "metric_value": 0.047393, "seed": 0},
            {"system_name": "proposed_svm", "metric_name": "calibration_error",
             "metric_value": 0.043983, "seed": 0},
        ],
        "statistics": {"seed_count": 512, "any_significant": True, "significance_tests": []},
    }


def _calibration_hypothesis() -> dict:
    return {
        "hypothesis_id": "h1",
        "primary_metric": "calibration_error",
        "expected_positive_outcome": "calibration_error drops below the baseline",
        "expected_negative_outcome": "calibration_error unchanged or worse",
    }


# --------------------------------------------------------------------------- #
# pure helper: distinctive value forms
# --------------------------------------------------------------------------- #


def test_distinctive_value_yields_its_exact_string_form() -> None:
    assert "0.025962" in auditor._value_anchor_forms(0.025962)
    assert "0.047393" in auditor._value_anchor_forms(0.047393)


def test_generic_values_are_not_anchors() -> None:
    # Too likely to match by coincidence — must not be used to clear an omission.
    assert auditor._value_anchor_forms(0.9) == []
    assert auditor._value_anchor_forms(1.0) == []
    assert auditor._value_anchor_forms(0.5) == []
    assert auditor._value_anchor_forms(0) == []


def test_non_numeric_is_not_an_anchor() -> None:
    assert auditor._value_anchor_forms(None) == []
    assert auditor._value_anchor_forms("0.025962") == []  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# pure helper: _metric_value_mentioned
# --------------------------------------------------------------------------- #


def test_metric_value_mentioned_true_when_draft_carries_real_value() -> None:
    metrics = _calibration_metrics()
    draft = "the proposed method reaches 0.025962 on the clinical set.\n"
    assert auditor._metric_value_mentioned("calibration_error", metrics, draft.lower()) is True


def test_metric_value_mentioned_false_when_draft_omits_the_value() -> None:
    metrics = _calibration_metrics()
    draft = "the proposed method is favorable on the clinical set.\n"
    assert auditor._metric_value_mentioned("calibration_error", metrics, draft.lower()) is False


def test_metric_value_mentioned_only_for_the_right_metric() -> None:
    # A value belonging to calibration_error must not clear an unrelated metric.
    metrics = _calibration_metrics()
    draft = "calibration_error reached 0.025962.\n"
    assert auditor._metric_value_mentioned("macro_f1", metrics, draft.lower()) is False


# --------------------------------------------------------------------------- #
# only-add invariant via the omission gate
# --------------------------------------------------------------------------- #


def test_chinese_draft_with_value_but_no_english_name_is_not_omitted() -> None:
    """THE root-cause fix (Session 16's rescue is no longer needed once this lands).
    A Chinese draft reports the metric's real value but never uses the English name
    `calibration_error`. Before S17 this was a false omission; now it is anchored."""
    metrics = _calibration_metrics()
    hypothesis = _calibration_hypothesis()
    draft = (
        "# 草稿\n\n"
        "我们在乳腺癌数据集上取得了积极结果。提出方法的期望校准误差为 0.025962，"
        "相比基线的 0.047393 有所改善。\n"
    )
    # Sanity: the English-name matcher does NOT see the metric here.
    assert auditor._metric_mentioned("calibration_error", draft.lower()) is False

    result = auditor.audit_draft(draft, metrics, hypothesis=hypothesis)
    assert result["omission_unverified_count"] == 0
    assert not any(
        c.get("category") == "omission" and c.get("metric") == "calibration_error"
        for c in result["claims"]
    )


def test_metric_genuinely_absent_is_still_omitted() -> None:
    """Never-loosen: a draft that neither names the metric nor quotes any of its
    real values is still flagged."""
    metrics = _calibration_metrics()
    hypothesis = _calibration_hypothesis()
    draft = (
        "# Draft\n\n"
        "Our pairwise-interaction features yield a favorable outcome on the "
        "clinical benchmark.\n"
    )
    result = auditor.audit_draft(draft, metrics, hypothesis=hypothesis)
    assert result["omission_unverified_count"] == 1
    assert result["gate"] is False
    assert any(
        c.get("category") == "omission" and c.get("metric") == "calibration_error"
        for c in result["claims"]
    )


def test_generic_value_in_draft_does_not_false_clear_an_omission() -> None:
    """A draft that quotes only a generic number (0.9) must not clear a metric whose
    real value is distinctive — the anchor filter prevents accidental matches."""
    metrics = _calibration_metrics()
    hypothesis = _calibration_hypothesis()
    draft = "# Draft\n\nOur method reached accuracy 0.9 on the benchmark.\n"
    result = auditor.audit_draft(draft, metrics, hypothesis=hypothesis)
    assert result["omission_unverified_count"] == 1
