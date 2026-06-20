"""Session 16 Step 2 — Auditor re-audit marker hygiene (only-add regression test).

The Auditor's ``annotate_draft`` appends its OWN block to flag omitted material
metrics inline::

    <!-- auditor: omitted material metrics (V2.2 honesty gate) -->
    > [UNVERIFIED: omitted material metric "calibration_error"]

On the NEXT ``run_auditor_agent`` re-audit the Auditor read that marker back as
draft content, which (a) pseudo-cleared the very omission it flagged — the metric
name inside the marker satisfied ``_metric_mentioned`` — and (b) the quoted name
tripped a false citation. ``run_auditor_agent`` now strips its own write-back
before re-auditing (``_strip_self_injected_omission_block``).

These tests lock the **only-add / never-loosen** invariant: stripping the
Auditor's own marker never hides a *real* omission — a material metric that is
genuinely absent from the human text is still reported. Deterministic, offline,
network-free.
"""
from __future__ import annotations

import json
from pathlib import Path

from services.research_harness import auditor

# The exact block ``annotate_draft`` writes (mirrors auditor.py:428-431).
_AUDITOR_BLOCK = (
    "\n\n<!-- auditor: omitted material metrics (V2.2 honesty gate) -->\n"
    '> [UNVERIFIED: omitted material metric "calibration_error"]\n'
)


def _calibration_metrics() -> dict:
    """Minimal metrics whose primary metric is calibration_error (a material name:
    it carries the ``calibration`` keyword and is the hypothesis primary)."""
    return {
        "execution_status": "success",
        "baseline_comparison": {
            "metric_name": "calibration_error",
            "direction": "lower_is_better",
            "overall_beats_baseline": True,
            "datasets": [
                {
                    "dataset": "breast_cancer_tabular",
                    "baseline_system": "baseline_svm",
                    "baseline_metric": 0.047393,
                    "proposed_system": "proposed_svm",
                    "proposed_metric": 0.025962,
                    "delta": -0.021431,
                    "beats_baseline": True,
                }
            ],
        },
        "statistics": {
            "seed_count": 512,
            "any_significant": True,
            "significance_tests": [
                {"significant": True, "adjusted_p_value": 0.0, "detail": "paired sign-flip"},
            ],
        },
    }


def _calibration_hypothesis() -> dict:
    return {
        "hypothesis_id": "h1",
        "primary_metric": "calibration_error",
        "expected_positive_outcome": "calibration_error drops below the baseline",
        "expected_negative_outcome": "calibration_error unchanged or worse",
    }


# --------------------------------------------------------------------------- #
# pure helper: _strip_self_injected_omission_block
# --------------------------------------------------------------------------- #


def test_strip_removes_the_auditor_omission_block() -> None:
    draft = "# Draft\n\nHuman prose about the experiment.\n" + _AUDITOR_BLOCK
    stripped = auditor._strip_self_injected_omission_block(draft)
    assert "<!-- auditor: omitted material metrics" not in stripped
    assert "> [UNVERIFIED: omitted material" not in stripped
    # Human content survives verbatim.
    assert "Human prose about the experiment." in stripped


def test_strip_leaves_human_content_with_quoted_metric_names_untouched() -> None:
    # A human sentence that legitimately quotes a metric name is NOT the Auditor's
    # marker and must survive.
    draft = (
        "# Draft\n\n"
        'We report "calibration_error" (our primary metric) in the results.\n'
    )
    stripped = auditor._strip_self_injected_omission_block(draft)
    assert 'We report "calibration_error"' in stripped
    assert stripped.strip() == draft.strip()


def test_strip_is_idempotent() -> None:
    draft = "# Draft\n\nHuman prose.\n" + _AUDITOR_BLOCK
    once = auditor._strip_self_injected_omission_block(draft)
    twice = auditor._strip_self_injected_omission_block(once)
    assert once == twice


def test_strip_removes_orphan_marker_line_without_html_header() -> None:
    # Defense-in-depth: a stray marker line (no preceding HTML comment) is removed too.
    draft = (
        "# Draft\n\n"
        "Human prose.\n"
        '> [UNVERIFIED: omitted material metric "calibration_error"]\n'
    )
    stripped = auditor._strip_self_injected_omission_block(draft)
    assert "> [UNVERIFIED: omitted material" not in stripped
    assert "Human prose." in stripped


def test_strip_is_a_noop_on_a_clean_draft() -> None:
    draft = "# Draft\n\nClean human prose, no marker.\n"
    assert auditor._strip_self_injected_omission_block(draft) == draft
    assert auditor._strip_self_injected_omission_block("") == ""


# --------------------------------------------------------------------------- #
# only-add invariant: a REAL omission is still detected once the marker is gone
# --------------------------------------------------------------------------- #


def _human_draft_silent_on_calibration() -> str:
    """Human content that discusses the outcome WITHOUT naming the material metric
    or its distinctive tokens (``calibration`` / ``error``) → a genuine omission."""
    return (
        "# Draft\n\n"
        "Our pairwise-interaction features yield a favorable outcome on the "
        "clinical benchmark.\n"
    )


def test_real_omission_is_still_detected_after_stripping_the_marker() -> None:
    """THE core never-loosen test. The draft carries the Auditor's own omission
    block (which names calibration_error) AND is genuinely silent on the metric in
    its human text. After stripping the self-injected marker, the omitted-material
    gate MUST still flag calibration_error."""
    metrics = _calibration_metrics()
    hypothesis = _calibration_hypothesis()
    poisoned = _human_draft_silent_on_calibration() + _AUDITOR_BLOCK

    # Sanity: without stripping, the marker pseudo-clears the omission (the bug).
    unstripped = auditor.audit_draft(poisoned, metrics, hypothesis=hypothesis)
    assert unstripped["omission_unverified_count"] == 0, (
        "precondition: the marker must pseudo-clear the omission for this test to mean anything"
    )

    # Contract: after stripping, the REAL omission is detected — never loosened.
    stripped = auditor._strip_self_injected_omission_block(poisoned)
    result = auditor.audit_draft(stripped, metrics, hypothesis=hypothesis)
    assert result["omission_unverified_count"] == 1
    assert result["gate"] is False
    assert any(
        c.get("category") == "omission" and c.get("metric") == "calibration_error"
        for c in result["claims"]
    )


def test_metric_genuinely_mentioned_passes_with_no_citation_false_positive() -> None:
    """When the human text DOES name the metric, stripping the marker yields
    gate=true with zero citation false positives (the FIX-A rescue scenario)."""
    metrics = _calibration_metrics()
    hypothesis = _calibration_hypothesis()
    honest = (
        "# Draft\n\n"
        "Our method achieves calibration_error 0.025962 vs 0.047393 baseline.\n"
    )
    poisoned = honest + _AUDITOR_BLOCK  # a stale marker from a prior audit round

    stripped = auditor._strip_self_injected_omission_block(poisoned)
    result = auditor.audit_draft(stripped, metrics, hypothesis=hypothesis)
    assert result["omission_unverified_count"] == 0
    assert result["citation_unverified_count"] == 0
    assert result["gate"] is True


# --------------------------------------------------------------------------- #
# integration: run_auditor_agent actually strips before re-auditing
# --------------------------------------------------------------------------- #


def _seed_poisoned_workspace(proj: Path, draft_text: str, metrics: dict) -> None:
    (proj / "paper").mkdir(parents=True, exist_ok=True)
    (proj / "artifacts").mkdir(parents=True, exist_ok=True)
    (proj / "ideas").mkdir(parents=True, exist_ok=True)
    (proj / "paper" / "draft.md").write_text(draft_text, encoding="utf-8")
    (proj / "artifacts" / "metrics.json").write_text(
        json.dumps(metrics), encoding="utf-8"
    )
    (proj / "ideas" / "selected.json").write_text(
        json.dumps(_calibration_hypothesis()), encoding="utf-8"
    )
    (proj / "research_report.md").write_text(
        "# Research Report\n\n## Conclusion\n\nhonest conclusion.\n", encoding="utf-8"
    )


def test_run_auditor_agent_detects_real_omission_in_poisoned_draft(
    monkeypatch, tmp_path
) -> None:
    """A draft that already carries the Auditor's own omission block AND is genuinely
    silent on the metric: re-audit must still flag the omission (no pseudo-clear)."""
    monkeypatch.setattr(auditor, "WORKSPACE_ROOT", tmp_path)
    proj = tmp_path / "proj_p"
    metrics = _calibration_metrics()
    _seed_poisoned_workspace(
        proj, _human_draft_silent_on_calibration() + _AUDITOR_BLOCK, metrics
    )

    result = auditor.run_auditor_agent("proj_p", metrics)
    assert result["omission_unverified_count"] == 1
    assert result["citation_unverified_count"] == 0
    assert result["gate"] is False

    # The re-written draft carries exactly ONE fresh omission block (the real
    # omission), not the stale marker + a duplicate → no accumulation.
    rewritten = (proj / "paper" / "draft.md").read_text(encoding="utf-8")
    assert rewritten.count("<!-- auditor: omitted material metrics") == 1


def test_run_auditor_agent_rescues_metric_mentioned_draft_with_no_citation_fp(
    monkeypatch, tmp_path
) -> None:
    """FIX-A through the agent: human text names the metric, a stale marker sits at
    the tail. Re-audit → gate=true, no omission, no citation false positive."""
    monkeypatch.setattr(auditor, "WORKSPACE_ROOT", tmp_path)
    proj = tmp_path / "proj_r"
    metrics = _calibration_metrics()
    honest = (
        "# Draft\n\n"
        "Our method achieves calibration_error 0.025962 vs 0.047393 baseline.\n"
    )
    _seed_poisoned_workspace(proj, honest + _AUDITOR_BLOCK, metrics)

    result = auditor.run_auditor_agent("proj_r", metrics)
    assert result["gate"] is True
    assert result["omission_unverified_count"] == 0
    assert result["citation_unverified_count"] == 0

    # No omission block is re-appended to a clean draft.
    rewritten = (proj / "paper" / "draft.md").read_text(encoding="utf-8")
    assert "<!-- auditor: omitted material metrics" not in rewritten
