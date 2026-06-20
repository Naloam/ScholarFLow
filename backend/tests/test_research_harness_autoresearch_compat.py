"""Session 13 — autoresearch_compat projection layer.

Deterministic, offline, network-free. Builds synthetic workspaces and asserts the
compat layer projects the NEW research_harness workspace (project.json +
artifacts/metrics.json + ledger/*) into the OLD ``run.json`` / ``artifact.json``
shapes (``AutoResearchRunRead`` / ``ResultArtifact``) that CLAUDE.md names as a
non-negotiable backward-compat baseline.

This file is CI-safe (tracked via the ``backend/tests/*`` negation in .gitignore).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.research_harness import pipeline
from services.research_harness.autoresearch_compat import projection as compat


# --------------------------------------------------------------------------- #
# Workspace seed helpers
# --------------------------------------------------------------------------- #


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_portfolio_workspace(root: Path, project_id: str = "proj_p") -> Path:
    """A portfolio + audited workspace modelled on live_session10_12_tabular."""
    proj = root / project_id
    _write_json(
        proj / "project.json",
        {
            "project_id": project_id,
            "idea": "Calibration-aware abstention for tabular classifiers",
            "status": "done",
            "created_at": "2026-06-19T10:00:00",
            "updated_at": "2026-06-19T10:20:00",
        },
    )
    _write_json(
        proj / "artifacts" / "metrics.json",
        {
            "execution_status": "success",
            "dataset": "breast_cancer",
            "results": [
                {"system_name": "baseline", "metric_name": "calibration_error",
                 "metric_value": 0.0474, "n_test_examples": 100, "dataset_name": "breast_cancer", "seed": 0},
                {"system_name": "proposed", "metric_name": "calibration_error",
                 "metric_value": 0.0260, "n_test_examples": 100, "dataset_name": "breast_cancer", "seed": 0},
            ],
            "baseline_comparison": {
                "metric_name": "calibration_error",
                "direction": "lower_is_better",
                "overall_beats_baseline": True,
                "datasets": [
                    {"dataset": "breast_cancer", "baseline_system": "baseline", "proposed_system": "proposed",
                     "baseline_metric": 0.0474, "proposed_metric": 0.0260, "delta": -0.0214,
                     "beats_baseline": True, "n_seeds_baseline": 128, "n_seeds_proposed": 128},
                ],
            },
            "statistics": {
                "seed_count": 128,
                "any_significant": True,
                "significance_tests": [
                    {"candidate": "proposed", "comparator": "baseline", "significant": True,
                     "adjusted_p_value": 0.001, "effect_size": 0.4, "method": "paired_sign_flip",
                     "detail": "128 seeds, holm-corrected"},
                ],
            },
        },
    )
    _write_json(
        proj / "ideas" / "candidates.json",
        [
            {"hypothesis_id": "h1", "research_question": "q1", "title": "H1",
             "proposed_method_sketch": "m1", "feasibility_in_sandbox": "high"},
            {"hypothesis_id": "h3", "research_question": "q3", "title": "H3",
             "proposed_method_sketch": "m3", "feasibility_in_sandbox": "high"},
        ],
    )
    _write_json(
        proj / "ideas" / "portfolio.json",
        {"k": 2, "ranked": [{"hypothesis_id": "h3", "rank": 0}, {"hypothesis_id": "h1", "rank": 1}]},
    )
    _write_json(
        proj / "ledger" / "portfolio.json",
        {
            "best_candidate_id": "h3",
            "portfolio_verdict": "mixed_portfolio",
            "summary": [
                {"candidate_id": "h3", "title": "H3", "primary_metric": "calibration_error",
                 "beats_baseline": True, "verdict": "positive_significant", "kill_tripped": False,
                 "downgraded": False, "execution_status": "success", "feasibility": "high", "is_best": True},
                {"candidate_id": "h1", "title": "H1", "primary_metric": "calibration_error",
                 "beats_baseline": False, "verdict": "negative", "kill_tripped": False,
                 "downgraded": False, "execution_status": "success", "feasibility": "high", "is_best": False},
            ],
            "best_candidate": {"hypothesis_id": "h3", "title": "H3"},
            "note": "mixed portfolio, best=h3",
        },
    )
    _write_json(
        proj / "ledger" / "claim_audit.json",
        {"total_claims": 1, "verified_count": 0, "unverified_count": 1,
         "citation_unverified_count": 0, "omission_unverified_count": 1,
         "gate": False, "claims": [], "verdict": "positive_significant",
         "audited_at": "2026-06-19T10:19:00"},
    )
    (proj / "paper").mkdir(parents=True, exist_ok=True)
    (proj / "paper" / "draft.md").write_text("# Draft\n\nA claim that is unsupported.\n", encoding="utf-8")
    (proj / "code").mkdir(parents=True, exist_ok=True)
    (proj / "code" / "experiment.py").write_text("print('hello')\n", encoding="utf-8")
    with (proj / "timeline.jsonl").open("w", encoding="utf-8") as fh:
        for step in ["literature", "idea", "experiment", "review", "report"]:
            fh.write(json.dumps({"step": step, "status": "done", "ts": "2026-06-19T10:0X:00",
                                 "output_files": []}) + "\n")
    return proj


# --------------------------------------------------------------------------- #
# legacy_artifact
# --------------------------------------------------------------------------- #


def test_legacy_artifact_projects_metrics_into_result_artifact_shape(monkeypatch, tmp_path) -> None:
    _seed_portfolio_workspace(tmp_path)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    art = compat.legacy_artifact("proj_p")

    # ResultArtifact required fields present + correctly typed.
    assert art["status"] == "done"  # execution_status == "success"
    assert art["primary_metric"] == "calibration_error"
    assert isinstance(art["key_findings"], list)
    assert isinstance(art["system_results"], list)
    assert isinstance(art["aggregate_system_results"], list)
    assert isinstance(art["significance_tests"], list)
    # Aggregate row carries the honest baseline→proposed delta.
    agg = art["aggregate_system_results"]
    assert any(row.get("system") == "proposed" for row in agg)
    # Significance tests projected through.
    assert art["significance_tests"][0]["significant"] is True


def test_legacy_artifact_marks_failed_when_execution_failed(monkeypatch, tmp_path) -> None:
    _seed_portfolio_workspace(tmp_path)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)
    # Flip execution_status to a failure.
    metrics_path = tmp_path / "proj_p" / "artifacts" / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["execution_status"] = "failed_after_3_repairs"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

    art = compat.legacy_artifact("proj_p")
    assert art["status"] == "failed"


# --------------------------------------------------------------------------- #
# legacy_run
# --------------------------------------------------------------------------- #


def test_legacy_run_projects_workspace_into_run_json_shape(monkeypatch, tmp_path) -> None:
    _seed_portfolio_workspace(tmp_path)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    run = compat.legacy_run("proj_p")

    # AutoResearchRunRead top-level identity + status mapping.
    assert run["id"] == "proj_p"
    assert run["project_id"] == "proj_p"
    assert run["topic"] == "Calibration-aware abstention for tabular classifiers"
    assert run["status"] == "done"  # new "done" → old "done"
    assert run["created_at"] == "2026-06-19T10:00:00"
    # Nested artifact is the projected ResultArtifact.
    assert run["artifact"]["primary_metric"] == "calibration_error"
    # Candidates + portfolio projected.
    assert isinstance(run["candidates"], list) and len(run["candidates"]) == 2
    assert run["portfolio"]["selected_candidate_id"] == "h3"
    # Code + paper paths surfaced for old consumers.
    assert run["generated_code_path"] == "code/experiment.py"
    assert run["paper_path"] == "paper/draft.md"
    assert run["hypothesis_id"] == "h3"


def test_legacy_run_returns_none_for_missing_workspace(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)
    assert compat.legacy_run("does_not_exist") is None


def test_legacy_run_status_maps_error_to_failed(monkeypatch, tmp_path) -> None:
    _seed_portfolio_workspace(tmp_path)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)
    meta_path = tmp_path / "proj_p" / "project.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status"] = "error"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    run = compat.legacy_run("proj_p")
    assert run["status"] == "failed"


# --------------------------------------------------------------------------- #
# legacy_candidates + legacy_portfolio
# --------------------------------------------------------------------------- #


def test_legacy_candidates_projects_ideas_bank(monkeypatch, tmp_path) -> None:
    _seed_portfolio_workspace(tmp_path)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    cands = compat.legacy_candidates("proj_p")
    assert len(cands) == 2
    # HypothesisCandidate required fields.
    first = cands[0]
    assert "id" in first and "title" in first and "hypothesis" in first
    assert first["program_id"] == "proj_p"


def test_legacy_portfolio_projects_ledger(monkeypatch, tmp_path) -> None:
    _seed_portfolio_workspace(tmp_path)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    port = compat.legacy_portfolio("proj_p")
    # PortfolioSummary shape.
    assert port["selected_candidate_id"] == "h3"
    assert port["total_candidates"] == 2
    assert "h3" in port["executed_candidate_ids"]
    assert isinstance(port["decision_summary"], str) and port["decision_summary"]


def test_legacy_portfolio_returns_none_when_no_ledger(monkeypatch, tmp_path) -> None:
    # A non-portfolio (single-candidate) workspace has no ledger/portfolio.json.
    _seed_portfolio_workspace(tmp_path)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)
    (tmp_path / "proj_p" / "ledger" / "portfolio.json").unlink()

    assert compat.legacy_portfolio("proj_p") is None
