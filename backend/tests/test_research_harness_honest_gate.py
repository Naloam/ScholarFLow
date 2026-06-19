"""Session 8 V2.2 layer: hypothesis-anchored honest gate + kill criteria.

Deterministic, offline, network-free. Every case builds its own synthetic
metrics/hypothesis — none read ``backend/data/`` — so this file is safe to run
in CI (tracked via the ``backend/tests/*`` negation in ``.gitignore``).

The core hole this closes (goal_session8.md §"Session 7 暴露的核心漏洞"): the old
``verdict(metrics)`` judged success on a generic metric (``macro_f1``) while the
hypothesis actually cared about a *different* primary metric (an abstention /
calibration target) that quietly failed — "plausible unsupported success" via
cherry-picked metrics. The new layer anchors the verdict to the hypothesis's
declared primary metric and executes its deterministic kill criteria.
"""
from __future__ import annotations

import pytest

from services.research_harness import (
    auditor,
    evidence,
    experiment_engineer,
    report_generator,
    research_manager,
    writer,
)


# --------------------------------------------------------------------------- #
# Synthetic metrics helpers (macro_f1 in baseline_comparison + abstention metrics)
# --------------------------------------------------------------------------- #


def _macro_positive_metrics() -> dict:
    """macro_f1 beats baseline everywhere + significant → old verdict = positive_significant."""
    return {
        "execution_status": "success",
        "baseline_comparison": {
            "metric_name": "macro_f1",
            "direction": "higher_is_better",
            "overall_beats_baseline": True,
            "datasets": [
                {"dataset": "scifact", "baseline_system": "baseline", "proposed_system": "proposed",
                 "baseline_metric": 0.465, "proposed_metric": 0.496, "delta": 0.031,
                 "beats_baseline": True, "n_seeds_baseline": 10, "n_seeds_proposed": 10},
                {"dataset": "vitaminc", "baseline_system": "baseline", "proposed_system": "proposed",
                 "baseline_metric": 0.486, "proposed_metric": 0.515, "delta": 0.029,
                 "beats_baseline": True, "n_seeds_baseline": 10, "n_seeds_proposed": 10},
            ],
        },
        "abstention_metrics": {
            # Hypothesis's real target — proposed is WORSE (higher error) than baseline on both.
            "error_rate_at_20pct_abstain": {
                "scifact": {"baseline": 0.465, "proposed": 0.49625},
                "vitaminc": {"baseline": 0.48625, "proposed": 0.515},
            },
            "spearman_consistency_vs_label": {
                "scifact": {"baseline": 0.077, "proposed": 0.193},
                "vitaminc": {"baseline": 0.0047, "proposed": 0.006},
            },
        },
        "statistics": {
            "seed_count": 10,
            "any_significant": True,
            "significance_tests": [
                {"significant": True, "detail": "dataset=scifact: ...", "adjusted_p_value": 0.01},
            ],
        },
    }


def _abstention_hypothesis(primary: str = "error_rate_at_20pct_abstain") -> dict:
    """A hypothesis whose primary target is abstention calibration (mirrors v0_3c6558d0)."""
    return {
        "hypothesis_id": "h1",
        "title": "dispersion-based abstention",
        "expected_positive_outcome": "the abstention error rate drops below the baseline",
        "expected_negative_outcome": "error rate unchanged or worse, AUC near 0.5",
        "primary_metric": primary,
        "kill_criteria": [
            "error_rate_at_20pct_abstain not lower than baseline",
            "与 Sufficient Context Classifier 相比无显著性能提升",
        ],
    }


# --------------------------------------------------------------------------- #
# primary_metric_for
# --------------------------------------------------------------------------- #


def test_primary_metric_uses_hypothesis_declared_when_present_in_metrics() -> None:
    h = _abstention_hypothesis("error_rate_at_20pct_abstain")
    pm = evidence.primary_metric_for(h, _macro_positive_metrics())
    assert pm["name"] == "error_rate_at_20pct_abstain"
    assert pm["source"] == "hypothesis_declared"


def test_primary_metric_comparison_default_when_unspecified_and_no_heuristic_hit() -> None:
    # No primary_metric, expected outcome mentions no metric that exists in metrics.
    h = {"expected_positive_outcome": "the method simply works better"}
    pm = evidence.primary_metric_for(h, _macro_positive_metrics())
    assert pm["source"] == "comparison_default"
    assert pm["name"] == "macro_f1"


def test_primary_metric_none_hypothesis_is_comparison_default() -> None:
    pm = evidence.primary_metric_for(None, _macro_positive_metrics())
    assert pm["source"] == "comparison_default"


def test_primary_metric_heuristic_maps_expected_outcome_text_to_metric() -> None:
    # No declared primary, but expected outcome names "spearman" which is an abstention metric.
    h = {"expected_positive_outcome": "the spearman consistency improves over baseline"}
    pm = evidence.primary_metric_for(h, _macro_positive_metrics())
    assert pm["name"] == "spearman_consistency_vs_label"
    assert pm["source"] == "heuristic"


# --------------------------------------------------------------------------- #
# primary_metric_outcome (is the proposed method favorable on its PRIMARY metric?)
# --------------------------------------------------------------------------- #


def test_primary_outcome_macro_f1_uses_baseline_comparison() -> None:
    out = evidence.primary_metric_outcome(_macro_positive_metrics(), "macro_f1")
    assert out["beats_baseline"] is True
    assert out["source"] == "baseline_comparison"


def test_primary_outcome_abstention_proposed_losing_returns_false() -> None:
    # error_rate: lower is better; proposed is HIGHER (worse) on every dataset → loses.
    out = evidence.primary_metric_outcome(_macro_positive_metrics(), "error_rate_at_20pct_abstain")
    assert out["beats_baseline"] is False
    assert out["source"] == "abstention_metrics"


def test_primary_outcome_metric_not_found_returns_none() -> None:
    out = evidence.primary_metric_outcome(_macro_positive_metrics(), "auc")
    assert out["beats_baseline"] is None
    assert out["source"] == "not_found"


def test_primary_outcome_abstention_proposed_winning_returns_true() -> None:
    m = _macro_positive_metrics()
    m["abstention_metrics"]["error_rate_at_20pct_abstain"] = {
        "scifact": {"baseline": 0.5, "proposed": 0.3},
        "vitaminc": {"baseline": 0.5, "proposed": 0.3},
    }
    out = evidence.primary_metric_outcome(m, "error_rate_at_20pct_abstain")
    assert out["beats_baseline"] is True


# --------------------------------------------------------------------------- #
# evaluate_kill_criteria (deterministic threshold + comparison evaluation)
# --------------------------------------------------------------------------- #


def _auc_metrics(auc: float) -> dict:
    return {
        "execution_status": "success",
        "baseline_comparison": {"overall_beats_baseline": True, "datasets": []},
        "results": [
            {"system_name": "proposed", "metric_name": "auc", "metric_value": auc,
             "n_test": 100, "dataset_name": "val", "seed": 1},
        ],
    }


def test_kill_criterion_threshold_trips_when_metric_below() -> None:
    h = {"kill_criteria": ["AUC < 0.55"]}
    kcs = evidence.evaluate_kill_criteria(h, _auc_metrics(0.50))
    assert len(kcs) == 1
    assert kcs[0]["tripped"] is True
    assert kcs[0]["needs_manual"] is False
    assert kcs[0]["threshold"] == pytest.approx(0.55)


def test_kill_criterion_threshold_not_tripped_when_above() -> None:
    h = {"kill_criteria": ["AUC < 0.55"]}
    kcs = evidence.evaluate_kill_criteria(h, _auc_metrics(0.60))
    assert kcs[0]["tripped"] is False


def test_kill_criterion_chinese_threshold_below_trips() -> None:
    h = {"kill_criteria": ["分散度特征的AUC低于0.55"]}
    kcs = evidence.evaluate_kill_criteria(h, _auc_metrics(0.50))
    assert kcs[0]["tripped"] is True


def test_kill_criterion_threshold_needs_manual_when_metric_absent() -> None:
    h = {"kill_criteria": ["AUC < 0.55"]}
    # metrics has no auc → cannot evaluate deterministically.
    kcs = evidence.evaluate_kill_criteria(h, _macro_positive_metrics())
    assert kcs[0]["tripped"] is False
    assert kcs[0]["needs_manual"] is True


def test_kill_criterion_comparison_needs_manual_when_named_baseline_absent() -> None:
    h = {"kill_criteria": ["与 Sufficient Context Classifier 相比无显著性能提升"]}
    # Sufficient Context Classifier is not among the results → manual.
    kcs = evidence.evaluate_kill_criteria(h, _macro_positive_metrics())
    assert kcs[0]["tripped"] is False
    assert kcs[0]["needs_manual"] is True


def test_kill_criterion_comparison_trips_when_named_baseline_present_and_proposed_loses() -> None:
    metrics = {
        "execution_status": "success",
        "results": [
            {"system_name": "StrongBaseline", "metric_name": "macro_f1", "metric_value": 0.80,
             "n_test": 100, "dataset_name": "d1", "seed": 1},
            {"system_name": "proposed", "metric_name": "macro_f1", "metric_value": 0.70,
             "n_test": 100, "dataset_name": "d1", "seed": 1},
        ],
    }
    h = {"kill_criteria": ["no significant improvement over StrongBaseline"]}
    kcs = evidence.evaluate_kill_criteria(h, metrics)
    assert kcs[0]["tripped"] is True
    assert kcs[0]["needs_manual"] is False


def test_kill_criterion_unparseable_is_manual() -> None:
    h = {"kill_criteria": ["if the method feels wrong we should stop"]}
    kcs = evidence.evaluate_kill_criteria(h, _macro_positive_metrics())
    assert kcs[0]["tripped"] is False
    assert kcs[0]["needs_manual"] is True


def test_evaluate_kill_criteria_empty_when_no_hypothesis_or_criteria() -> None:
    assert evidence.evaluate_kill_criteria(None, _macro_positive_metrics()) == []
    assert evidence.evaluate_kill_criteria({}, _macro_positive_metrics()) == []
    assert evidence.evaluate_kill_criteria({"kill_criteria": []}, _macro_positive_metrics()) == []


# --------------------------------------------------------------------------- #
# verdict / full_verdict (anchoring + downgrade)
# --------------------------------------------------------------------------- #


def test_verdict_without_hypothesis_is_byte_identical_to_old_behavior() -> None:
    """only-add-never-loosen: no hypothesis → verdict unchanged."""
    m = _macro_positive_metrics()
    assert evidence.verdict(m) == "positive_significant"
    # negative case
    neg = {
        "execution_status": "success",
        "baseline_comparison": {"overall_beats_baseline": False, "datasets": [
            {"dataset": "d1", "beats_baseline": False, "baseline_metric": 0.9, "proposed_metric": 0.8},
        ]},
        "statistics": {"significance_tests": []},
    }
    assert evidence.verdict(neg) == "negative"


def test_verdict_anchored_downgrades_when_primary_metric_loses() -> None:
    """THE core fix: macro_f1 is positive_significant, but the hypothesis's declared
    primary metric (abstention error rate) shows the proposed method LOSING → verdict
    must downgrade instead of reporting success on a cherry-picked metric."""
    m = _macro_positive_metrics()
    h = _abstention_hypothesis("error_rate_at_20pct_abstain")
    fv = evidence.full_verdict(m, h)
    assert fv["base_verdict"] == "positive_significant"
    assert fv["verdict"] == "negative"  # downgraded — primary target failed
    assert fv["downgraded"] is True
    assert fv["primary_metric"] == "error_rate_at_20pct_abstain"
    assert fv["primary_beats_baseline"] is False


def test_verdict_no_downgrade_when_primary_metric_wins() -> None:
    # Hypothesis declares macro_f1 (which wins) → no downgrade.
    m = _macro_positive_metrics()
    h = {"primary_metric": "macro_f1", "expected_positive_outcome": "macro_f1 improves"}
    fv = evidence.full_verdict(m, h)
    assert fv["verdict"] == "positive_significant"
    assert fv["downgraded"] is False


def test_verdict_kill_criterion_trip_downgrades() -> None:
    m = _auc_metrics(0.50)
    m["baseline_comparison"] = {"overall_beats_baseline": True, "datasets": [
        {"dataset": "d1", "beats_baseline": True, "baseline_metric": 0.4, "proposed_metric": 0.5},
    ]}
    m["statistics"] = {"any_significant": True, "significance_tests": [
        {"significant": True, "detail": "dataset=d1: ...", "adjusted_p_value": 0.01}]}
    h = {"primary_metric": "auc", "kill_criteria": ["AUC < 0.55"]}
    fv = evidence.full_verdict(m, h)
    assert fv["base_verdict"] == "positive_significant"
    assert fv["verdict"] == "negative"
    assert fv["downgraded"] is True
    tripped = [kc for kc in fv["kill_criteria"] if kc["tripped"]]
    assert len(tripped) == 1


def test_verdict_downgrade_reports_reasons() -> None:
    m = _macro_positive_metrics()
    h = _abstention_hypothesis("error_rate_at_20pct_abstain")
    fv = evidence.full_verdict(m, h)
    assert any("primary" in r.lower() or "metric" in r.lower() for r in fv["downgrade_reasons"])


# --------------------------------------------------------------------------- #
# Step 3 — omitted material metric gate (Auditor)
# --------------------------------------------------------------------------- #


def _abstention_draft_macro_only() -> str:
    """A draft that reports macro_f1 success but says nothing about the abstention
    calibration metrics the hypothesis actually targets (the cherry-pick case)."""
    return (
        "# Draft\n\n"
        "## Results\n\n"
        "Our method improves macro_f1 over the baseline across datasets.\n\n"
        "## References\n[1] A. Author. *Real Retrieved Paper*. 2023.\n"
    )


def test_omitted_material_metrics_flags_abstention_when_draft_silent() -> None:
    m = _macro_positive_metrics()
    h = _abstention_hypothesis("error_rate_at_20pct_abstain")
    omitted = auditor._omitted_material_metrics(_abstention_draft_macro_only(), m, h)
    names = {o["metric"] for o in omitted}
    # The hypothesis's real target metrics are present in metrics but absent from the draft.
    assert "error_rate_at_20pct_abstain" in names
    assert "spearman_consistency_vs_label" in names
    for o in omitted:
        assert o["category"] == "omission"
        assert o["verdict"] == "unverified"
        assert "omitted material metric" in o["reason"]


def test_omitted_material_metrics_not_flagged_when_draft_discusses_them() -> None:
    m = _macro_positive_metrics()
    h = _abstention_hypothesis("error_rate_at_20pct_abstain")
    draft = (
        "# Draft\n\n"
        "Our error_rate_at_20pct_abstain dropped, and spearman consistency improved.\n"
    )
    omitted = auditor._omitted_material_metrics(draft, m, h)
    names = {o["metric"] for o in omitted}
    assert "error_rate_at_20pct_abstain" not in names
    assert "spearman_consistency_vs_label" not in names


def test_omitted_primary_metric_when_declared_and_absent_from_draft() -> None:
    m = _macro_positive_metrics()
    h = {"primary_metric": "spearman_consistency_vs_label",
         "expected_positive_outcome": "spearman improves"}
    omitted = auditor._omitted_material_metrics(_abstention_draft_macro_only(), m, h)
    names = {o["metric"] for o in omitted}
    assert "spearman_consistency_vs_label" in names


def test_audit_draft_omission_claims_fail_gate_and_inline_mark() -> None:
    m = _macro_positive_metrics()
    h = _abstention_hypothesis("error_rate_at_20pct_abstain")
    draft = _abstention_draft_macro_only()
    result = auditor.audit_draft(draft, m, hypothesis=h)
    omission_claims = [c for c in result["claims"] if c.get("category") == "omission"]
    assert len(omission_claims) >= 2  # error_rate + spearman
    # The omission gate fails the overall gate (only-add-never-loosen).
    assert result["gate"] is False
    assert result["unverified_count"] >= len(omission_claims)
    annotated = auditor.annotate_draft(draft, result)
    assert "[UNVERIFIED: omitted material metric" in annotated


def test_audit_draft_no_omission_gate_without_hypothesis() -> None:
    """only-add-never-loosen: with no hypothesis the auditor behaves as before —
    no omission claims are synthesized."""
    m = _macro_positive_metrics()
    draft = _abstention_draft_macro_only()
    result = auditor.audit_draft(draft, m)
    assert not any(c.get("category") == "omission" for c in result["claims"])


# --------------------------------------------------------------------------- #
# Step 4 — citation grounding loop (Writer, ≤1 round before the Auditor)
# --------------------------------------------------------------------------- #

import json as _json  # noqa: E402 — local to the Step 4 block
from pathlib import Path as _Path  # noqa: E402

_GROUND_PAPERS = [
    {"title": "Real Retrieved Paper About Abstention Calibration"},
]


def _draft_with_fake_citation() -> str:
    return (
        "# Draft\n\n"
        "Our method improves macro_f1 over the baseline.\n\n"
        "## References\n"
        "[1] A. Author. *A Hallucinated Paper About Nothing Real At All*. 2024.\n"
    )


def _seed_grounding_workspace(monkeypatch, tmp_path, draft_text: str) -> str:
    """Set up tmp workspace with paper/draft.md + literature/papers.jsonl; return pid."""
    monkeypatch.setattr(writer, "WORKSPACE_ROOT", tmp_path)
    pid = "p"
    (tmp_path / pid / "paper").mkdir(parents=True)
    (tmp_path / pid / "paper" / "draft.md").write_text(draft_text, encoding="utf-8")
    lit = tmp_path / pid / "literature"
    lit.mkdir(parents=True)
    (lit / "papers.jsonl").write_text(_json.dumps(_GROUND_PAPERS[0]) + "\n", encoding="utf-8")
    return pid


def test_ground_citations_deletes_unverified_citation(monkeypatch, tmp_path) -> None:
    pid = _seed_grounding_workspace(monkeypatch, tmp_path, _draft_with_fake_citation())
    fixed = "# Draft\n\nOur method improves macro_f1 over the baseline.\n"
    monkeypatch.setattr(writer, "chat", lambda msgs, model=None: {
        "choices": [{"message": {"content": fixed}}]
    })
    revised, log = writer.ground_citations(pid, _draft_with_fake_citation(), _macro_positive_metrics())
    assert log["revised"] is True
    assert any("Hallucinated" in u["title"] for u in log["unverified_before"])
    assert log["unverified_after"] == []  # the unsupported citation is gone
    assert "Hallucinated" not in revised


def test_ground_citations_noop_when_all_verified(monkeypatch, tmp_path) -> None:
    real_draft = (
        "# Draft\n\nOur method improves macro_f1 over the baseline.\n\n"
        "## References\n[1] A. Author. *" + _GROUND_PAPERS[0]["title"] + "*. 2023.\n"
    )
    pid = _seed_grounding_workspace(monkeypatch, tmp_path, real_draft)

    def boom(msgs, model=None):  # must never be called
        raise AssertionError("grounding must not call the LLM when there are no unverified citations")

    monkeypatch.setattr(writer, "chat", boom)
    revised, log = writer.ground_citations(pid, real_draft, _macro_positive_metrics())
    assert log["revised"] is False
    assert log["unverified_before"] == []
    assert revised == real_draft


def test_ground_citations_keeps_draft_on_llm_failure(monkeypatch, tmp_path) -> None:
    pid = _seed_grounding_workspace(monkeypatch, tmp_path, _draft_with_fake_citation())
    original = _draft_with_fake_citation()

    def boom(msgs, model=None):
        raise RuntimeError("writer LLM exploded")

    monkeypatch.setattr(writer, "chat", boom)
    revised, log = writer.ground_citations(pid, original, _macro_positive_metrics())
    assert log["revised"] is False
    assert "error" in log  # failure recorded, never blocks
    assert revised == original  # original draft kept; the Auditor backstops


def test_run_quality_loop_persists_citation_grounding_log(monkeypatch, tmp_path) -> None:
    pid = _seed_grounding_workspace(monkeypatch, tmp_path, _draft_with_fake_citation())
    # revise step: no flags (no fabricated numbers) → no revise call; grounding fires.
    fixed = "# Draft\n\nOur method improves macro_f1 over the baseline.\n"

    def fake_chat(msgs, model=None):
        return {"choices": [{"message": {"content": fixed}}]}

    monkeypatch.setattr(writer, "chat", fake_chat)
    writer.run_quality_loop(pid, _macro_positive_metrics())
    log_path = tmp_path / pid / "paper" / "citation_grounding_log.json"
    assert log_path.is_file()
    glog = _json.loads(log_path.read_text(encoding="utf-8"))
    assert glog["revised"] is True
    assert any("Hallucinated" in u["title"] for u in glog["unverified_before"])


# --------------------------------------------------------------------------- #
# Step 5 — experiment planner contract (missing baselines + underpowered)
# --------------------------------------------------------------------------- #


def test_detect_missing_baselines_finds_named_systems_not_run() -> None:
    h = {
        "expected_positive_outcome": "our method significantly outperforms Calibrated Softmax",
        "kill_criteria": ["no improvement over Sufficient Context Classifier"],
    }
    results = [
        {"system_name": "proposed_method", "metric_name": "macro_f1", "metric_value": 0.7,
         "dataset_name": "d1", "seed": 1},
        {"system_name": "baseline_lexical", "metric_name": "macro_f1", "metric_value": 0.6,
         "dataset_name": "d1", "seed": 1},
    ]
    plan = {"systems": [{"name": "proposed_method"}, {"name": "baseline_lexical"}]}
    missing = experiment_engineer._detect_missing_baselines(h, results, plan)
    assert "Calibrated Softmax" in missing
    assert "Sufficient Context Classifier" in missing


def test_detect_missing_baselines_empty_when_named_baseline_is_present() -> None:
    h = {"kill_criteria": ["no improvement over Strong Baseline"]}
    results = [
        {"system_name": "Strong Baseline", "metric_name": "macro_f1", "metric_value": 0.8,
         "dataset_name": "d1", "seed": 1},
    ]
    plan = {"systems": [{"name": "Strong Baseline"}]}
    assert experiment_engineer._detect_missing_baselines(h, results, plan) == []


def test_detect_missing_baselines_no_hypothesis() -> None:
    assert experiment_engineer._detect_missing_baselines(None, [], {"systems": []}) == []


def test_underpowered_note_when_ran_below_recommended() -> None:
    metrics = {"statistics": {"seed_count": 10, "significance_tests": [
        {"recommended_sample_count": 512}]}}
    note = experiment_engineer._underpowered_note(metrics)
    assert note is not None
    assert note["underpowered"] is True
    assert note["ran_seeds"] == 10
    assert note["recommended_seeds"] == 512


def test_underpowered_none_when_adequate() -> None:
    metrics = {"statistics": {"seed_count": 512, "significance_tests": [
        {"recommended_sample_count": 512}]}}
    assert experiment_engineer._underpowered_note(metrics) is None


def test_underpowered_none_without_recommended_count() -> None:
    metrics = {"statistics": {"seed_count": 3, "significance_tests": []}}
    assert experiment_engineer._underpowered_note(metrics) is None


def test_report_surfaces_missing_baselines_and_underpowered(monkeypatch, tmp_path) -> None:
    """The report must surface the hypothesis-contract signals (missing baselines +
    underpowered) so a reader sees them — never silent."""
    monkeypatch.setattr(report_generator, "WORKSPACE_ROOT", tmp_path)
    pid = "p"
    proj = tmp_path / pid
    (proj / "literature").mkdir(parents=True)
    (proj / "experiments").mkdir(parents=True)
    (proj / "reviews").mkdir(parents=True)
    (proj / "literature" / "papers.jsonl").write_text('{"title": "Some Real Paper"}\n', encoding="utf-8")

    metrics = _macro_positive_metrics()
    metrics["missing_baselines"] = ["Sufficient Context Classifier"]
    metrics["underpowered"] = {
        "underpowered": True, "ran_seeds": 10, "recommended_seeds": 512,
        "note": "underpowered: ran 10 of recommended 512 seeds",
    }
    h = _abstention_hypothesis("error_rate_at_20pct_abstain")  # primary loses → downgrade
    review = {"publish_gate": "no_evidence", "required_experiments": []}
    manager_decision = {"decision": {}, "conclusion": "TL;DR"}
    report_generator.generate_research_report(pid, "idea", h, metrics, review, manager_decision)

    report = (proj / "research_report.md").read_text(encoding="utf-8")
    assert "Sufficient Context Classifier" in report  # missing baseline surfaced
    assert "underpowered" in report.lower()
    assert "10" in report and "512" in report  # ran N of recommended M


# --------------------------------------------------------------------------- #
# Step 6 — reviewer → follow-up loop (research_manager, ≤1 round)
# --------------------------------------------------------------------------- #


def _review_feasible_must_have() -> dict:
    return {
        "required_experiments": [
            {"action": "add_stronger_baseline", "description": "add a stronger lexical baseline",
             "priority": "must_have"},
            {"action": "run_ablation", "description": "ablate the variance feature",
             "priority": "nice_to_have"},
        ],
        "publish_gate": "insufficient_evidence",
    }


def _review_infeasible_must_have() -> dict:
    return {
        "required_experiments": [
            {"action": "add_large_model", "description": "compare against a billion-parameter GPU model",
             "priority": "must_have"},
        ],
        "publish_gate": "no_evidence",
    }


def test_select_follow_up_picks_first_must_have() -> None:
    fu = research_manager._select_follow_up(_review_feasible_must_have())
    assert fu is not None
    assert fu["action"] == "add_stronger_baseline"


def test_select_follow_up_none_when_no_must_have() -> None:
    review = {"required_experiments": [{"action": "x", "priority": "nice_to_have"}]}
    assert research_manager._select_follow_up(review) is None


def test_follow_up_feasibility_feasible_for_sandbox_action() -> None:
    fu = {"action": "add_stronger_baseline", "description": "add a stronger lexical baseline"}
    feas = research_manager._follow_up_feasibility(fu)
    assert feas["feasible"] is True


def test_follow_up_feasibility_infeasible_for_gpu() -> None:
    fu = {"action": "add_large_model", "description": "compare against a billion-parameter GPU model"}
    feas = research_manager._follow_up_feasibility(fu)
    assert feas["feasible"] is False


def _seed_manager_workspace(monkeypatch, tmp_path, metrics, hypothesis, review) -> str:
    monkeypatch.setattr(research_manager, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(experiment_engineer, "WORKSPACE_ROOT", tmp_path)
    pid = "p"
    proj = tmp_path / pid
    for sub in ("artifacts", "ideas", "reviews", "experiments"):
        (proj / sub).mkdir(parents=True)
    (proj / "artifacts" / "metrics.json").write_text(_json.dumps(metrics), encoding="utf-8")
    (proj / "ideas" / "selected.json").write_text(_json.dumps(hypothesis), encoding="utf-8")
    (proj / "reviews" / "review_round_1.json").write_text(_json.dumps(review), encoding="utf-8")
    (proj / "experiments" / "plan.json").write_text(_json.dumps({
        "systems": [{"name": "proposed", "role": "proposed"}, {"name": "baseline", "role": "baseline"}],
        "metrics": [{"name": "macro_f1", "primary": True}],
        "dataset": {"name": "scifact"},
    }), encoding="utf-8")
    return pid


def _patch_follow_up_run(monkeypatch, with_stronger_baseline: bool = True) -> None:
    """Mock the LLM codegen + sandbox execution for a follow-up run."""
    monkeypatch.setattr(experiment_engineer, "chat", lambda msgs, model=None: {
        "choices": [{"message": {"content": "print('__RESULT__', [])"}}]
    })

    def fake_run(project_id, code=None, execution_backend=None):  # noqa: ANN001
        if not with_stronger_baseline:
            return ("traceback", {"returncode": 1, "result": None, "stderr": "boom"})
        outputs = {
            "returncode": 0,
            "result": [{"system_name": "stronger_baseline", "metric_name": "macro_f1",
                        "metric_value": 0.65, "n_test": 100, "dataset_name": "scifact", "seed": 1}],
            "stderr": "",
        }
        return ("ok", outputs)

    monkeypatch.setattr(experiment_engineer, "run_python_in_sandbox", fake_run)


def test_run_follow_up_merges_new_system(monkeypatch, tmp_path) -> None:
    pid = "fu_only"
    (tmp_path / pid / "experiments").mkdir(parents=True)
    (tmp_path / pid / "experiments" / "plan.json").write_text(_json.dumps({
        "systems": [{"name": "proposed", "role": "proposed"}, {"name": "baseline", "role": "baseline"}],
        "metrics": [{"name": "macro_f1", "primary": True}],
    }), encoding="utf-8")
    monkeypatch.setattr(experiment_engineer, "WORKSPACE_ROOT", tmp_path)
    _patch_follow_up_run(monkeypatch, with_stronger_baseline=True)
    merged, fu = experiment_engineer.run_follow_up(
        pid, "idea", {"title": "h"},
        {"action": "add_stronger_baseline", "description": "add a stronger baseline"},
        _macro_positive_metrics(),
    )
    assert fu["ran"] is True
    assert "stronger_baseline" in fu["systems_added"]
    assert any(r["system_name"] == "stronger_baseline" for r in merged["results"])


def test_run_follow_up_failure_keeps_base_metrics(monkeypatch, tmp_path) -> None:
    pid = "fu_fail"
    (tmp_path / pid / "experiments").mkdir(parents=True)
    (tmp_path / pid / "experiments" / "plan.json").write_text(_json.dumps({"systems": [], "metrics": []}), encoding="utf-8")
    monkeypatch.setattr(experiment_engineer, "WORKSPACE_ROOT", tmp_path)
    _patch_follow_up_run(monkeypatch, with_stronger_baseline=False)
    base = _macro_positive_metrics()
    merged, fu = experiment_engineer.run_follow_up(
        pid, "idea", {"title": "h"},
        {"action": "add_stronger_baseline", "description": "add a stronger baseline"}, base,
    )
    assert fu["ran"] is False  # honest: no fake data
    assert merged == base  # base metrics unchanged; no fabricated follow-up data


def test_research_manager_runs_feasible_follow_up(monkeypatch, tmp_path) -> None:
    pid = _seed_manager_workspace(
        monkeypatch, tmp_path, _macro_positive_metrics(),
        _abstention_hypothesis(), _review_feasible_must_have(),
    )
    _patch_follow_up_run(monkeypatch, with_stronger_baseline=True)
    out = research_manager.run_research_manager(
        pid, "idea", _abstention_hypothesis(), _macro_positive_metrics(), _review_feasible_must_have(),
    )
    assert out["decision"]["follow_up_ran"] is True
    assert any(r["system_name"] == "stronger_baseline" for r in out["metrics"]["results"])
    # The merged metrics are persisted to disk.
    on_disk = _json.loads((tmp_path / pid / "artifacts" / "metrics.json").read_text(encoding="utf-8"))
    assert any(r["system_name"] == "stronger_baseline" for r in on_disk["results"])


def test_research_manager_infeasible_goes_to_future_work(monkeypatch, tmp_path) -> None:
    pid = _seed_manager_workspace(
        monkeypatch, tmp_path, _macro_positive_metrics(),
        _abstention_hypothesis(), _review_infeasible_must_have(),
    )

    def boom(msgs, model=None):  # the follow-up must NOT run for an infeasible must_have
        raise AssertionError("follow-up must not run for an infeasible must_have")

    monkeypatch.setattr(experiment_engineer, "chat", boom)
    out = research_manager.run_research_manager(
        pid, "idea", _abstention_hypothesis(), _macro_positive_metrics(), _review_infeasible_must_have(),
    )
    assert out["decision"]["follow_up_ran"] is False
    future_work = out["decision"].get("future_work") or []
    assert future_work, "infeasible must_have should be recorded as Future Work"
    assert any("GPU" in fw["reason"] or "gpu" in fw["reason"] or "budget" in fw["reason"].lower()
               for fw in future_work)


def test_research_manager_at_most_one_follow_up(monkeypatch, tmp_path) -> None:
    """Even with several must_have items, only ONE follow-up round runs."""
    review = {"required_experiments": [
        {"action": "add_stronger_baseline", "description": "b1", "priority": "must_have"},
        {"action": "run_ablation", "description": "b2", "priority": "must_have"},
        {"action": "improve_statistical_power", "description": "b3", "priority": "must_have"},
    ], "publish_gate": "insufficient_evidence"}
    pid = _seed_manager_workspace(
        monkeypatch, tmp_path, _macro_positive_metrics(), _abstention_hypothesis(), review,
    )
    calls = {"n": 0}

    def counting_chat(msgs, model=None):
        calls["n"] += 1
        return {"choices": [{"message": {"content": "print('__RESULT__', [])"}}]}

    monkeypatch.setattr(experiment_engineer, "chat", counting_chat)
    monkeypatch.setattr(experiment_engineer, "run_python_in_sandbox", lambda *a, **k: (
        "ok", {"returncode": 0, "result": [
            {"system_name": "stronger_baseline", "metric_name": "macro_f1",
             "metric_value": 0.65, "n_test": 100, "dataset_name": "scifact", "seed": 1}], "stderr": ""}))
    research_manager.run_research_manager(
        pid, "idea", _abstention_hypothesis(), _macro_positive_metrics(), review)
    assert calls["n"] == 1  # bounded — exactly one follow-up codegen call
