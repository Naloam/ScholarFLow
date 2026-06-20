"""Session 14 — publish-bundle export (P3 publication surface).

Deterministic, offline, network-free. Builds synthetic workspaces and asserts
``build_publish_bundle`` aggregates the honest verdict + audit gate + unverified
count + metric summary + provenance, writes ``publish_bundle/manifest.json`` +
``publish_bundle.zip``, and — the core honesty constraint — marks a bundle
``publishable: false`` with a reason whenever the audit gate failed or the
verdict is negative/all_negative. The publish surface must not let a gate-failed
artifact ship as "publishable".

CI-safe (tracked via the ``backend/tests/*`` negation in .gitignore).
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from services.research_harness import pipeline, publish


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed(root: Path, project_id: str, *, gate: bool, unverified: int,
          verdict: str = "positive_significant", portfolio_verdict: str | None = "mixed_portfolio",
          execution_status: str = "success") -> Path:
    proj = root / project_id
    _write_json(proj / "project.json", {
        "project_id": project_id, "idea": "test idea",
        "status": "done", "created_at": "2026-06-20T10:00:00", "updated_at": "2026-06-20T10:20:00",
    })
    _write_json(proj / "artifacts" / "metrics.json", {
        "execution_status": execution_status,
        "baseline_comparison": {"metric_name": "calibration_error", "direction": "lower_is_better",
                                "overall_beats_baseline": True,
                                "datasets": [{"dataset": "breast_cancer", "baseline_system": "baseline",
                                              "proposed_system": "proposed", "baseline_metric": 0.047,
                                              "proposed_metric": 0.026, "delta": -0.021, "beats_baseline": True,
                                              "n_seeds_baseline": 128, "n_seeds_proposed": 128}]},
        "statistics": {"seed_count": 128, "any_significant": True, "significance_tests": [
            {"candidate": "proposed", "comparator": "baseline", "significant": True,
             "adjusted_p_value": 0.001, "effect_size": 0.4, "method": "paired_sign_flip", "detail": "x"}]},
    })
    _write_json(proj / "ideas" / "candidates.json", [{"hypothesis_id": "h3", "title": "H3"}])
    _write_json(proj / "ledger" / "portfolio.json", {
        "best_candidate_id": "h3", "portfolio_verdict": portfolio_verdict or "single",
        "summary": [{"candidate_id": "h3", "title": "H3", "primary_metric": "calibration_error",
                     "beats_baseline": True, "verdict": verdict, "kill_tripped": False,
                     "downgraded": False, "execution_status": execution_status, "feasibility": "high", "is_best": True}],
        "best_candidate": {"hypothesis_id": "h3", "title": "H3"}, "note": "n",
    } if portfolio_verdict else {"best_candidate_id": "h3", "portfolio_verdict": "single",
                                  "summary": [], "best_candidate": {"hypothesis_id": "h3"}, "note": "n"})
    _write_json(proj / "ledger" / "anchored_verdict.json", {
        "verdict": verdict, "base_verdict": verdict, "primary_metric": "calibration_error",
        "primary_metric_source": "hypothesis_declared", "primary_beats_baseline": True,
        "kill_criteria": [{"criterion": "calibration_error >= 0.15", "tripped": False,
                           "needs_manual": False, "reason": "ok", "metric": "calibration_error",
                           "value": 0.026, "threshold": 0.15}],
        "downgraded": False, "downgrade_reasons": [],
    })
    _write_json(proj / "ledger" / "claim_audit.json", {
        "total_claims": 1, "verified_count": 0 if not gate else 1, "unverified_count": unverified,
        "citation_unverified_count": 0, "omission_unverified_count": unverified, "gate": gate,
        "claims": [], "verdict": verdict, "audited_at": "2026-06-20T10:19:00",
    })
    (proj / "paper").mkdir(parents=True, exist_ok=True)
    (proj / "paper" / "draft.md").write_text("# Draft\n\nbody\n", encoding="utf-8")
    (proj / "code").mkdir(parents=True, exist_ok=True)
    (proj / "code" / "experiment.py").write_text("print('hi')\n", encoding="utf-8")
    (proj / "code" / "requirements.txt").write_text("numpy\n", encoding="utf-8")
    with (proj / "timeline.jsonl").open("w", encoding="utf-8") as fh:
        for step in ["literature", "idea", "experiment", "review", "report"]:
            fh.write(json.dumps({"step": step, "status": "done", "ts": "t", "output_files": []}) + "\n")
    return proj


def test_bundle_gate_failed_marks_not_publishable(monkeypatch, tmp_path) -> None:
    _seed(tmp_path, "p1", gate=False, unverified=1)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    manifest = publish.build_publish_bundle("p1")

    assert manifest["publishable"] is False
    assert "audit gate failed" in manifest["publishable_reason"]
    assert manifest["audit_gate"]["gate"] is False
    assert manifest["audit_gate"]["unverified_count"] == 1
    # Honest verdict + metric summary still carried (transparency, not suppression).
    assert manifest["honest_verdict"]["verdict"] == "positive_significant"
    assert manifest["metric_summary"]["overall_beats_baseline"] is True


def test_bundle_gate_passed_positive_is_publishable(monkeypatch, tmp_path) -> None:
    _seed(tmp_path, "p2", gate=True, unverified=0)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    manifest = publish.build_publish_bundle("p2")
    assert manifest["publishable"] is True
    assert manifest["publishable_reason"] == "" or manifest["publishable_reason"] is None


def test_bundle_all_negative_portfolio_not_publishable(monkeypatch, tmp_path) -> None:
    _seed(tmp_path, "p3", gate=True, unverified=0, verdict="negative", portfolio_verdict="all_negative")
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    manifest = publish.build_publish_bundle("p3")
    assert manifest["publishable"] is False
    assert "negative" in manifest["publishable_reason"]


def test_bundle_writes_manifest_and_zip_with_required_files(monkeypatch, tmp_path) -> None:
    _seed(tmp_path, "p4", gate=True, unverified=0)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    manifest = publish.build_publish_bundle("p4")
    proj = tmp_path / "p4"
    # manifest.json written to disk.
    on_disk = json.loads((proj / "publish_bundle" / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["project_id"] == "p4"
    # zip exists and contains the required reproducibility files.
    zip_path = proj / "publish_bundle" / "publish_bundle.zip"
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "paper/draft.md" in names
        assert "code/experiment.py" in names
        assert "evidence/anchored_verdict.json" in names
        assert "evidence/claim_audit.json" in names
        # The manifest inside the zip matches the returned manifest.
        with zf.open("manifest.json") as fh:
            assert json.load(io.TextIOWrapper(fh))["project_id"] == "p4"


def test_bundle_provenance_carries_datasets_and_seeds(monkeypatch, tmp_path) -> None:
    _seed(tmp_path, "p5", gate=True, unverified=0)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    manifest = publish.build_publish_bundle("p5")
    prov = manifest["provenance"]
    assert "breast_cancer" in prov["datasets"]
    assert prov["seed_count"] == 128
    assert prov["candidate_count"] == 1


def test_bundle_missing_workspace_raises(monkeypatch, tmp_path) -> None:
    import pytest
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        publish.build_publish_bundle("nope")


# --------------------------------------------------------------------------- #
# API layer (TestClient) — publish-bundle + deployments
# --------------------------------------------------------------------------- #


def _client():
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


def test_api_publish_bundle_returns_manifest(monkeypatch, tmp_path) -> None:
    _seed(tmp_path, "ap1", gate=False, unverified=1)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    res = _client().get("/api/research-harness/projects/ap1/publish-bundle")
    assert res.status_code == 200
    body = res.json()
    assert body["publishable"] is False
    assert "audit gate failed" in body["publishable_reason"]
    assert body["audit_gate"]["unverified_count"] == 1


def test_api_publish_bundle_download_returns_zip(monkeypatch, tmp_path) -> None:
    _seed(tmp_path, "ap2", gate=True, unverified=0)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    res = _client().get("/api/research-harness/projects/ap2/publish-bundle?download=1")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "attachment" in res.headers.get("content-disposition", "")
    import zipfile
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert "manifest.json" in zf.namelist()
        assert "paper/draft.md" in zf.namelist()


def test_api_publish_bundle_404_for_missing_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)
    res = _client().get("/api/research-harness/projects/nope/publish-bundle")
    assert res.status_code == 404


def test_api_deployments_is_read_only_status(monkeypatch, tmp_path) -> None:
    _seed(tmp_path, "ap3", gate=False, unverified=2)
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)

    res = _client().get("/api/research-harness/projects/ap3/deployments")
    assert res.status_code == 200
    body = res.json()
    assert body["has_bundle"] is True
    assert body["publishable"] is False
    assert body["audit_gate"] is False
    assert body["unverified_count"] == 2
    assert body["manifest_path"] == "publish_bundle/manifest.json"
