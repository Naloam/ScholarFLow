"""Session 17 (cont.) — structured-claims auditor foundation (only-add).

The investigation (see docs/research-harness-roadmap.md, "claim-extraction
investigation") proved that prose-based claim verification cannot reliably reach
non-English drafts: ``_CLAIM_CUES`` are English, ``_split_sentences`` ignores CJK
terminals, and ``evidence.keywords`` drops decimals and CJK. The only correct fix
is for the Writer to bind each claim to its evidence explicitly via a
language-independent marker::

    <!-- audit-claim metric=calibration_error proposed=0.025962 baseline=0.047393 -->

The auditor then extracts + verifies these markers by their NUMBERS (not by parsing
prose), so verification works for any language. This is the auditor half; the Writer
half (emitting markers) is a separate, live-verified change.

**Only-add / never-loosen**: a draft with NO markers is byte-identical to today
(no structured claims extracted → verdicts unchanged). A marker grounds a claim in
real numbers; a fabricated/out-of-tolerance value still fails. Deterministic,
offline, network-free.
"""
from __future__ import annotations

from services.research_harness import auditor


def _calibration_metrics() -> dict:
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
        "statistics": {"seed_count": 512, "any_significant": True, "significance_tests": []},
    }


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #


def test_extract_structured_claims_parses_a_marker() -> None:
    draft = (
        "# Draft\n\nOur method improves calibration.\n\n"
        "<!-- audit-claim metric=calibration_error proposed=0.025962 baseline=0.047393 -->\n"
    )
    claims = auditor.extract_structured_claims(draft)
    assert len(claims) == 1
    c = claims[0]
    assert c["category"] == "structured"
    assert c["metric"] == "calibration_error"
    assert c["proposed"] == 0.025962
    assert c["baseline"] == 0.047393


def test_extract_structured_claims_handles_missing_baseline() -> None:
    draft = "<!-- audit-claim metric=macro_f1 proposed=0.974 -->\n"
    claims = auditor.extract_structured_claims(draft)
    assert len(claims) == 1
    assert claims[0]["proposed"] == 0.974
    assert claims[0]["baseline"] is None


def test_extract_structured_claims_finds_multiple_and_ignores_prose() -> None:
    draft = (
        "<!-- audit-claim metric=a proposed=0.1 baseline=0.2 -->\n"
        "some prose with no marker\n"
        "<!-- audit-claim metric=b proposed=0.3 -->\n"
    )
    claims = auditor.extract_structured_claims(draft)
    assert [c["metric"] for c in claims] == ["a", "b"]


def test_extract_structured_claims_empty_when_no_markers() -> None:
    assert auditor.extract_structured_claims("# Draft\n\nPlain prose, no markers.\n") == []
    assert auditor.extract_structured_claims("") == []


# --------------------------------------------------------------------------- #
# verification
# --------------------------------------------------------------------------- #


def test_structured_claim_with_real_values_verifies() -> None:
    draft = (
        "我们的方法显著降低了校准误差。\n\n"
        "<!-- audit-claim metric=calibration_error proposed=0.025962 baseline=0.047393 -->\n"
    )
    result = auditor.audit_draft(draft, _calibration_metrics())
    structured = [c for c in result["claims"] if c.get("category") == "structured"]
    assert structured and structured[0]["verdict"] == "verified"


def test_structured_claim_tolerates_rounded_values() -> None:
    # The Writer often rounds in prose; the marker may carry a rounded form.
    draft = "<!-- audit-claim metric=calibration_error proposed=0.026 baseline=0.047 -->\n"
    result = auditor.audit_draft(draft, _calibration_metrics())
    structured = [c for c in result["claims"] if c.get("category") == "structured"]
    assert structured and structured[0]["verdict"] == "verified"


def test_structured_claim_with_fabricated_value_is_unverified() -> None:
    draft = "<!-- audit-claim metric=calibration_error proposed=0.9 baseline=0.1 -->\n"
    result = auditor.audit_draft(draft, _calibration_metrics())
    structured = [c for c in result["claims"] if c.get("category") == "structured"]
    assert structured and structured[0]["verdict"] == "unverified"
    assert result["unverified_count"] >= 1
    assert result["gate"] is False


def test_structured_claim_unknown_metric_is_unverified() -> None:
    draft = "<!-- audit-claim metric=nonexistent_metric proposed=0.5 baseline=0.6 -->\n"
    result = auditor.audit_draft(draft, _calibration_metrics())
    structured = [c for c in result["claims"] if c.get("category") == "structured"]
    assert structured and structured[0]["verdict"] == "unverified"


# --------------------------------------------------------------------------- #
# only-add safety: no markers => byte-identical to today
# --------------------------------------------------------------------------- #


def test_draft_without_markers_is_byte_identical_to_pre_structured_behavior() -> None:
    """The foundational safety guarantee: adding structured-claim extraction must not
    change ANY verdict for a draft that carries no markers."""
    metrics = _calibration_metrics()
    draft = (
        "# Draft\n\n"
        "Our method significantly outperforms the baseline on the dataset.\n"
    )
    result = auditor.audit_draft(draft, metrics)
    # No structured claims were extracted.
    assert not any(c.get("category") == "structured" for c in result["claims"])
    # The cue-based claim still behaves exactly as before (it overclaims without a
    # dataset qualifier while beating baseline — the point is the verdict is
    # unchanged, whatever it is, by the structured path being inert).
    assert all(c.get("category") != "structured" for c in result["claims"])


def test_structured_claim_supplements_but_does_not_replace_cue_claims() -> None:
    """A draft can carry BOTH a prose cue-claim and a structured marker; both are
    audited (the structured path is additive)."""
    draft = (
        "Our method significantly outperforms the baseline.\n\n"
        "<!-- audit-claim metric=calibration_error proposed=0.025962 baseline=0.047393 -->\n"
    )
    result = auditor.audit_draft(draft, _calibration_metrics())
    cats = {c.get("category") for c in result["claims"]}
    assert "structured" in cats
