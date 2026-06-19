"""Session 10 (goal_session10) — real-scale plane + gate precision.

CI-safe, network-free pure-logic tests for the four Session-10 changes:
  - ``evidence.validate_kill_criteria`` (idea-time gate precision, Step 6)
  - IdeaAgent kill-criteria parseability annotation + ranking demotion (Step 6)
  - ResearchManager analysis-only action exclusion (Step 7: ``report_failure_mode``
    must never be spawned as an experiment)
  - Scale + stronger-baseline invariants (Steps 3/4/5): committed slices grew past
    the toy 100-row size and stay balanced; the planner/capability note name a
    real stronger baseline and target ≥128 seeds.

Only-add: these assert NEW behaviour and do not relax any V2.2/V2.3 gate.
"""
from __future__ import annotations

import json
from pathlib import Path

import services.research_harness.research_manager as research_manager
from services.research_harness import datasets, evidence, idea_agent, portfolio
from services.research_harness.prompts import resolve_prompts_dir
from services.research_harness.sandbox_capabilities import capability_note

SEED_DIR = Path(datasets.SEED_DIR)
PLANNER_PROMPT = resolve_prompts_dir() / "experiment_planner_v1.md"


# --------------------------------------------------------------------------- #
# Step 6 — kill-criteria parseability validator (pure logic)
# --------------------------------------------------------------------------- #


def test_validate_kill_criteria_threshold_is_parseable() -> None:
    h = {"kill_criteria": ["auc < 0.55", "error_rate_at_20pct_abstain >= 0.20"]}
    out = evidence.validate_kill_criteria(h)
    assert [r["parseable"] for r in out] == [True, True]
    assert {r["kind"] for r in out} == {"threshold"}
    assert out[0]["metric"] == "auc"


def test_validate_kill_criteria_comparison_is_parseable() -> None:
    h = {"kill_criteria": ["macro_f1 相比 baseline 未提升"]}
    out = evidence.validate_kill_criteria(h)
    assert out[0]["parseable"] is True
    assert out[0]["kind"] == "comparison"
    assert out[0]["metric"] == "macro_f1"


def test_validate_kill_criteria_free_text_is_rejected_with_rewrite() -> None:
    h = {"kill_criteria": ["方法效果不好就放弃这个方向"]}
    out = evidence.validate_kill_criteria(h)
    assert out[0]["parseable"] is False
    assert "reason" in out[0]
    assert out[0]["suggested_rewrite"]


def test_validate_kill_criteria_empty_or_missing() -> None:
    assert evidence.validate_kill_criteria(None) == []
    assert evidence.validate_kill_criteria({"kill_criteria": []}) == []
    assert evidence.validate_kill_criteria({}) == []


def test_validate_kill_criteria_mixed() -> None:
    h = {"kill_criteria": ["auc < 0.55", "如果结果不理想就停止"]}
    out = evidence.validate_kill_criteria(h)
    assert out[0]["parseable"] is True
    assert out[1]["parseable"] is False


# --------------------------------------------------------------------------- #
# Step 6 — IdeaAgent annotation + ranking demotion
# --------------------------------------------------------------------------- #


def test_annotate_candidates_marks_unparseable() -> None:
    candidates = [
        {"hypothesis_id": "h1", "kill_criteria": ["auc < 0.55"]},
        {"hypothesis_id": "h2", "kill_criteria": ["结果不行就放弃"]},
    ]
    annotated = idea_agent.annotate_candidates_kill_criteria(candidates)
    assert annotated[0]["kill_criteria_parseable"] is True
    assert annotated[0]["kill_criteria_issues"] == []
    assert annotated[1]["kill_criteria_parseable"] is False
    assert annotated[1]["kill_criteria_issues"] and annotated[1]["kill_criteria_issues"][0]["criterion"]


def test_select_hypothesis_demotes_unparseable_within_feasibility_tier() -> None:
    parseable = {
        "hypothesis_id": "h1", "feasibility": "high",
        "kill_criteria": ["auc < 0.55"], "kill_criteria_parseable": True,
    }
    unparseable = {
        "hypothesis_id": "h2", "feasibility": "high",
        "kill_criteria": ["结果不行就放弃"], "kill_criteria_parseable": False,
    }
    selected = idea_agent.select_hypothesis([unparseable, parseable])
    assert selected["hypothesis_id"] == "h1"

    ranked = portfolio.rank_candidates([unparseable, parseable])
    assert ranked[0]["hypothesis_id"] == "h1"


def test_rank_candidates_unannotated_default_is_no_penalty() -> None:
    # Regression (only-add): candidates without the annotation flag keep the
    # original ranking (feasibility, then specificity) — no spurious penalty.
    a = {"hypothesis_id": "a", "feasibility": "high", "kill_criteria": ["x < 1"]}
    b = {"hypothesis_id": "b", "feasibility": "high", "kill_criteria": ["x < 1", "y < 1"]}
    ranked = portfolio.rank_candidates([a, b])
    assert ranked[0]["hypothesis_id"] == "b"  # more specific kill_criteria wins


# --------------------------------------------------------------------------- #
# Step 7 — analysis-only follow-up actions never spawn an experiment
# --------------------------------------------------------------------------- #


def _review_with(*actions: str) -> dict:
    return {
        "required_experiments": [
            {"action": a, "description": f"do {a}", "priority": "must_have"} for a in actions
        ],
    }


def test_report_failure_mode_is_not_spawned_as_experiment(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setattr(research_manager, "WORKSPACE_ROOT", tmp_path / "ws")
    calls: list = []
    monkeypatch.setattr(
        "services.research_harness.experiment_engineer.run_follow_up",
        lambda *a, **k: calls.append((a, k)) or ({"execution_status": "success"}, {"ran": True}),
    )
    metrics = {"execution_status": "success", "baseline_comparison": {"overall_beats_baseline": False, "datasets": []}}
    out = research_manager.run_research_manager(
        "proj", "idea", {"title": "t"}, metrics, _review_with("report_failure_mode"),
    )
    decision = out["decision"]
    assert decision["follow_up_target"] is None
    actions = {wt["action"] for wt in decision["writing_tasks"]}
    assert "report_failure_mode" in actions
    assert calls == []  # run_follow_up was NEVER called


def test_real_experiment_action_still_becomes_run_target(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(research_manager, "WORKSPACE_ROOT", tmp_path / "ws")
    monkeypatch.setattr(
        "services.research_harness.experiment_engineer.run_follow_up",
        lambda *a, **k: ({"execution_status": "success"}, {"ran": True, "systems_added": ["x"]}),
    )
    metrics = {"execution_status": "success", "baseline_comparison": {"overall_beats_baseline": False, "datasets": []}}
    out = research_manager.run_research_manager(
        "proj", "idea", {"title": "t"}, metrics, _review_with("add_stronger_baseline"),
    )
    assert out["decision"]["follow_up_target"] is not None
    assert out["decision"]["follow_up_target"]["action"] == "add_stronger_baseline"


# --------------------------------------------------------------------------- #
# Steps 3/4/5 — scale + stronger baseline invariants
# --------------------------------------------------------------------------- #


def test_committed_slices_grew_past_toy_scale_and_stay_balanced() -> None:
    from collections import Counter

    for name, pos, neg in (
        ("scifact_slice.jsonl", "SUPPORT", "REFUTE"),
        ("vitaminc_slice.jsonl", "SUPPORT", "REFUTE"),
        ("citation_faithfulness_slice.jsonl", "FAITHFUL", "PARSING_ERROR"),
    ):
        rows = [json.loads(line) for line in (SEED_DIR / name).read_text(encoding="utf-8").splitlines() if line.strip()]
        dist = Counter(r["label"] for r in rows)
        assert len(rows) > 100, f"{name} still at toy scale: {len(rows)}"
        assert dist[pos] == dist[neg], f"{name} not balanced: {dict(dist)}"


def test_registry_reports_new_sizes() -> None:
    by_key = {s.key: s for s in datasets.DATASET_REGISTRY}
    assert by_key["scifact_claim_verification"].n_examples > 100
    assert by_key["vitaminc_claim_verification"].n_examples > 100
    assert by_key["citation_faithfulness"].n_examples > 100


def test_planner_and_capability_note_name_a_stronger_baseline_and_more_seeds() -> None:
    note = capability_note()
    assert "stronger_baseline" in note
    assert "BM25" in note
    assert "≥128" in note or "贴近 512" in note or "512" in note

    planner = PLANNER_PROMPT.read_text(encoding="utf-8")
    assert "stronger_baseline_bm25" in planner
    assert '"seeds": 512' in planner


def test_role_of_does_not_classify_stronger_baseline_as_weak_baseline() -> None:
    """Session 10 correctness: ``stronger_baseline_bm25`` contains "baseline" but must
    NOT be folded into the weak-baseline pool (which would pollute the comparison)."""
    from services.research_harness.experiment_engineer import _role_of

    role_map = {"stronger_baseline_bm25": "stronger_baseline"}
    assert _role_of("stronger_baseline_bm25", role_map) == "stronger_baseline"
    # Even on naming drift (role_map miss), it must not become the weak baseline.
    assert _role_of("stronger_baseline_bm25", {}) == "stronger_baseline"
    # The weak baseline + proposed still classify correctly.
    assert _role_of("baseline_lexical_tfidf", {}) == "baseline"
    assert _role_of("proposed_sentence_transformer", {}) == "proposed"
