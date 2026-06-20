"""Session 17 (cont.) — Writer→Auditor structured-claims pipeline (offline integration).

The writer_draft prompt now instructs the Writer to emit ``<!-- audit-claim .. -->``
markers (Rule 7). This test proves the end-to-end pipeline offline with a MOCKED
compliant Writer: the marker written into ``paper/draft.md`` is extracted and verified
by ``run_auditor_agent``. A live GLM run confirms real Writer compliance separately
(deferred — live-LLM work).

Deterministic, offline, network-free (Writer's ``chat`` is mocked).
"""
from __future__ import annotations

import json

from services.research_harness import auditor, pipeline, writer
from services.research_harness.prompts import load_prompt


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
                    "baseline_system": "baseline_svm",
                    "baseline_metric": 0.047393,
                    "proposed_system": "proposed_svm",
                    "proposed_metric": 0.025962,
                    "delta": -0.021431,
                    "beats_baseline": True,
                    "n_seeds_baseline": 512,
                    "n_seeds_proposed": 512,
                }
            ],
        },
        "statistics": {
            "seed_count": 512,
            "any_significant": True,
            "significance_tests": [
                {"significant": True, "adjusted_p_value": 0.0, "detail": "paired sign-flip"}
            ],
        },
    }


def _selected() -> dict:
    return {
        "hypothesis_id": "h1",
        "primary_metric": "calibration_error",
        "expected_positive_outcome": "calibration_error drops below the baseline",
        "expected_negative_outcome": "calibration_error unchanged or worse",
    }


def test_writer_draft_prompt_instructs_audit_claim_markers() -> None:
    """Locks the prompt change: the draft prompt must tell the Writer to emit markers."""
    prompt = load_prompt("writer_draft_v1.md")
    assert "audit-claim" in prompt
    assert "metric=" in prompt and "proposed=" in prompt and "baseline=" in prompt


def test_compliant_writer_draft_flows_to_verified_structured_claim(
    monkeypatch, tmp_path
) -> None:
    """A Writer that emits an audit-claim marker (per the prompt) produces a draft whose
    structured claim the Auditor extracts AND verifies — in any language (Chinese here)."""
    for mod in (writer, auditor, pipeline):
        monkeypatch.setattr(mod, "WORKSPACE_ROOT", tmp_path)
    proj = tmp_path / "proj_w"
    (proj / "artifacts").mkdir(parents=True)
    (proj / "ideas").mkdir(parents=True)
    metrics = _calibration_metrics()
    (proj / "artifacts" / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    (proj / "ideas" / "selected.json").write_text(json.dumps(_selected()), encoding="utf-8")

    # Mocked compliant Writer: Chinese prose + the structured marker binding it to evidence.
    canned = (
        "# 草稿\n\n"
        "## 结果\n\n"
        "提出方法的期望校准误差为 0.025962，显著优于基线的 0.047393。\n"
        "<!-- audit-claim metric=calibration_error proposed=0.025962 baseline=0.047393 -->\n"
    )
    monkeypatch.setattr(
        writer,
        "chat",
        lambda msgs, model=None: {"choices": [{"message": {"content": canned}}]},
    )

    writer.write_draft("proj_w", "idea", _selected(), metrics, "contribution", "outline")
    result = auditor.run_auditor_agent("proj_w", metrics)

    structured = [c for c in result["claims"] if c.get("category") == "structured"]
    assert structured, "the audit-claim marker must be extracted from the draft"
    assert structured[0]["verdict"] == "verified"
    assert structured[0]["metric"] == "calibration_error"
    # No unverified claims → gate true; the Chinese result claim is now audited (via the marker).
    assert result["unverified_count"] == 0
    assert result["gate"] is True
