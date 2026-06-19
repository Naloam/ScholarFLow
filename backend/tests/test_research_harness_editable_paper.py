"""Session 11 (goal_session11) — V3 editable paper / re-audit closure.

CI-safe, network-free: the human-in-the-loop honesty closure. A human can edit
``paper/draft.md`` (TipTap), but on re-audit a newly-added unsupported claim (e.g.
a hallucinated citation) is marked ``[UNVERIFIED]`` and fails the gate — the human
collaborates with the gate, never bypasses it. Re-audit is non-fatal.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.research_harness import auditor, pipeline


def _patch_workspace(monkeypatch, tmp_path: Path) -> None:
    """Point both pipeline + auditor at the tmp workspace (they keep separate
    module-level WORKSPACE_ROOT constants that both resolve to settings.data_dir
    in production; tests must patch both for isolation)."""
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(auditor, "WORKSPACE_ROOT", tmp_path)


def _metrics() -> dict:
    return {
        "execution_status": "success",
        "baseline_comparison": {
            "metric_name": "macro_f1",
            "overall_beats_baseline": True,
            "datasets": [
                {"dataset": "d1", "beats_baseline": True,
                 "baseline_metric": 0.60, "proposed_metric": 0.65, "delta": 0.05},
            ],
        },
        "statistics": {"any_significant": True, "seed_count": 128, "significance_tests": []},
        "results": [],
    }


def _seed_workspace(tmp_path: Path, project_id: str, *, draft: str, metrics: dict | None = None) -> Path:
    proj = tmp_path / project_id
    (proj / "paper").mkdir(parents=True, exist_ok=True)
    (proj / "artifacts").mkdir(parents=True, exist_ok=True)
    (proj / "ideas").mkdir(parents=True, exist_ok=True)
    (proj / "literature").mkdir(parents=True, exist_ok=True)
    (proj / "ledger").mkdir(parents=True, exist_ok=True)
    (proj / "paper" / "draft.md").write_text(draft, encoding="utf-8")
    (proj / "artifacts" / "metrics.json").write_text(
        json.dumps(metrics if metrics is not None else _metrics()), encoding="utf-8",
    )
    (proj / "ideas" / "selected.json").write_text(json.dumps({}), encoding="utf-8")
    (proj / "literature" / "papers.jsonl").write_text("", encoding="utf-8")
    return proj


# --------------------------------------------------------------------------- #
# save_paper_draft (PUT draft)
# --------------------------------------------------------------------------- #


def test_save_paper_draft_writes_and_enforces_length_cap(tmp_path, monkeypatch) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    pipeline.write_project_meta("proj", "idea", "done")  # so read_project_meta finds it

    path = pipeline.save_paper_draft("proj", "# Edited\n\nHuman content.\n")
    assert path.read_text(encoding="utf-8").startswith("# Edited")

    with pytest.raises(ValueError):
        pipeline.save_paper_draft("proj", "x" * (pipeline.MAX_PAPER_DRAFT_CHARS + 1))


# --------------------------------------------------------------------------- #
# reaudit_paper (POST reaudit) — the honesty closure
# --------------------------------------------------------------------------- #


def test_reaudit_flags_human_added_unsupported_citation(tmp_path, monkeypatch) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    pipeline.write_project_meta("proj", "idea", "done")
    draft = (
        "# Draft\n\n"
        "Our method is honest. As shown by **\"Definitely Not A Real Paper\"** (2020), "
        "the approach is sound.\n"
    )
    proj = _seed_workspace(tmp_path, "proj", draft=draft)

    result = pipeline.reaudit_paper("proj")

    assert result["gate"] is False  # the hallucinated citation fails the gate
    assert result.get("citation_unverified_count", 0) >= 1
    # The human-added unsupported claim is marked inline — the gate is not bypassed.
    annotated = (proj / "paper" / "draft.md").read_text(encoding="utf-8")
    assert "[UNVERIFIED" in annotated
    # Ledger persisted.
    assert (proj / "ledger" / "claim_audit.json").exists()


def test_reaudit_is_non_fatal_without_metrics(tmp_path, monkeypatch) -> None:
    _patch_workspace(monkeypatch, tmp_path)
    pipeline.write_project_meta("proj", "idea", "done")
    proj = _seed_workspace(tmp_path, "proj", draft="# draft\n", metrics={})  # empty metrics

    result = pipeline.reaudit_paper("proj")  # must NOT raise
    assert result.get("skipped") is True
    # A completed run is never turned into an error by a re-audit failure.
    assert "error" not in (pipeline.read_project_meta("proj") or {}).get("status", "")
