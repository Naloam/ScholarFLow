"""Session 9 V2.3 layer: portfolio-aware execution.

Deterministic, offline, network-free. Every case builds its own synthetic
candidates/metrics/hypotheses — none read ``backend/data/`` — so this file is
safe to run in CI (tracked via the ``backend/tests/*`` negation in ``.gitignore``).

This closes the gap CLAUDE.md's "Non-Negotiable Baselines" names but the new core
had not implemented: **portfolio-aware execution**. The harness used to pick ONE
hypothesis (``select_hypothesis``) and run just that. Now it ranks the idea_bank,
runs the top-K sequentially (per-minute GLM rate limit → no parallelism), applies
the full V2.2 honest gate to EACH candidate independently, and aggregates them into
one honest portfolio verdict — "who won / who lost / who tripped a kill criterion".

Only-add-never-loosen: portfolio never weakens a V2.2 gate. K=1 is byte-equivalent
to the old single-hypothesis path (top-level metrics + selected.json unchanged).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.research_harness import evidence, experiment_engineer, pipeline, portfolio, report_generator


# --------------------------------------------------------------------------- #
# Synthetic candidates / metrics
# --------------------------------------------------------------------------- #


def _candidate(cid: str, feasibility: str = "high", kill: int = 1, primary: str = "macro_f1") -> dict:
    return {
        "hypothesis_id": cid,
        "title": f"Hypothesis {cid}",
        "research_question": f"question for {cid}",
        "primary_metric": primary,
        "feasibility": feasibility,
        "kill_criteria": [f"kill {i}" for i in range(kill)],
        "expected_positive_outcome": f"{primary} improves",
        "expected_negative_outcome": f"{primary} does not improve",
    }


def _metrics_positive(cid: str = "h1") -> dict:
    """macro_f1 beats baseline everywhere + significant → verdict positive_significant."""
    return {
        "execution_status": "success",
        "baseline_comparison": {
            "metric_name": "macro_f1",
            "direction": "higher_is_better",
            "overall_beats_baseline": True,
            "datasets": [
                {"dataset": "d1", "baseline_system": "baseline", "proposed_system": "proposed",
                 "baseline_metric": 0.50, "proposed_metric": 0.60, "delta": 0.10,
                 "beats_baseline": True, "n_seeds_baseline": 5, "n_seeds_proposed": 5},
            ],
        },
        "results": [
            {"system_name": "proposed", "metric_name": "macro_f1", "metric_value": 0.60,
             "n_test": 100, "dataset_name": "d1", "seed": s} for s in range(1, 6)
        ] + [
            {"system_name": "baseline", "metric_name": "macro_f1", "metric_value": 0.50,
             "n_test": 100, "dataset_name": "d1", "seed": s} for s in range(1, 6)
        ],
        "statistics": {
            "seed_count": 5,
            "any_significant": True,
            "significance_tests": [
                {"significant": True, "detail": "dataset=d1: ...", "adjusted_p_value": 0.01,
                 "effect_size": 0.10, "method": "paired sign-flip", "candidate": "proposed",
                 "comparator": "baseline", "p_value": 0.01},
            ],
        },
    }


def _metrics_negative(seed_count: int = 3) -> dict:
    """proposed does NOT beat baseline, no significant win → verdict negative."""
    return {
        "execution_status": "success",
        "baseline_comparison": {
            "metric_name": "macro_f1",
            "direction": "higher_is_better",
            "overall_beats_baseline": False,
            "datasets": [
                {"dataset": "d1", "baseline_system": "baseline", "proposed_system": "proposed",
                 "baseline_metric": 0.60, "proposed_metric": 0.50, "delta": -0.10,
                 "beats_baseline": False, "n_seeds_baseline": seed_count, "n_seeds_proposed": seed_count},
            ],
        },
        "results": [
            {"system_name": "proposed", "metric_name": "macro_f1", "metric_value": 0.50,
             "n_test": 100, "dataset_name": "d1", "seed": s} for s in range(1, seed_count + 1)
        ] + [
            {"system_name": "baseline", "metric_name": "macro_f1", "metric_value": 0.60,
             "n_test": 100, "dataset_name": "d1", "seed": s} for s in range(1, seed_count + 1)
        ],
        "statistics": {"seed_count": seed_count, "any_significant": False, "significance_tests": []},
    }


def _per_candidate(cid: str, metrics: dict, hyp: dict) -> dict:
    return {
        "candidate_id": cid,
        "title": hyp.get("title", cid),
        "hypothesis": hyp,
        "metrics": metrics,
        "verdict": evidence.full_verdict(metrics, hyp),
    }


# --------------------------------------------------------------------------- #
# rank_candidates
# --------------------------------------------------------------------------- #


def test_rank_candidates_orders_by_feasibility_then_specificity() -> None:
    cands = [
        _candidate("low", feasibility="low", kill=0),
        _candidate("high2", feasibility="high", kill=1),
        _candidate("high1", feasibility="high", kill=3),  # more kill_criteria → more specific → first
        _candidate("med", feasibility="medium", kill=5),
    ]
    ranked = portfolio.rank_candidates(cands)
    ids = [c["hypothesis_id"] for c in ranked]
    assert ids[0] == "high1"  # high + most kill_criteria
    assert ids[1] == "high2"
    assert ids[2] == "med"
    assert ids[3] == "low"
    assert [c["rank"] for c in ranked] == [0, 1, 2, 3]


def test_rank_candidates_empty() -> None:
    assert portfolio.rank_candidates([]) == []


def test_rank_candidates_stable_on_full_ties() -> None:
    # Same feasibility + same kill_criteria count → stable, original order kept.
    cands = [_candidate("a"), _candidate("b"), _candidate("c")]
    ranked = portfolio.rank_candidates(cands)
    assert [c["hypothesis_id"] for c in ranked] == ["a", "b", "c"]


def test_rank_candidates_does_not_mutate_input() -> None:
    cands = [_candidate("low", feasibility="low"), _candidate("high", feasibility="high")]
    snapshot = [dict(c) for c in cands]
    portfolio.rank_candidates(cands)
    # Originals untouched (no 'rank' added in place).
    assert all("rank" not in c for c in cands)
    assert [c["hypothesis_id"] for c in cands] == [c["hypothesis_id"] for c in snapshot]


# --------------------------------------------------------------------------- #
# select_portfolio
# --------------------------------------------------------------------------- #


def test_select_portfolio_returns_top_k_full_hypotheses_with_rank() -> None:
    cands = [_candidate(f"h{i}", feasibility="high", kill=5 - i) for i in range(6)]
    sel = portfolio.select_portfolio(cands, k=3)
    assert sel["k"] == 3
    assert len(sel["ranked"]) == 3
    assert [c["hypothesis_id"] for c in sel["ranked"]] == ["h0", "h1", "h2"]
    assert [c["rank"] for c in sel["ranked"]] == [0, 1, 2]


def test_select_portfolio_caps_at_max_k() -> None:
    cands = [_candidate(f"h{i}", feasibility="high", kill=10 - i) for i in range(20)]
    sel = portfolio.select_portfolio(cands, k=99)
    assert sel["k"] == portfolio.MAX_K  # never exceeds the hard cap
    assert len(sel["ranked"]) == portfolio.MAX_K


def test_select_portfolio_k_capped_to_available_candidates() -> None:
    cands = [_candidate("only"), _candidate("two")]
    sel = portfolio.select_portfolio(cands, k=5)
    assert len(sel["ranked"]) == 2


def test_select_portfolio_writes_lean_portfolio_json_and_preserves_selected(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(portfolio, "WORKSPACE_ROOT", tmp_path)
    pid = "p"
    ideas = tmp_path / pid / "ideas"
    ideas.mkdir(parents=True)
    # selected.json is written by the idea step (rank-0); select_portfolio must not clobber it.
    rank0 = _candidate("h0", feasibility="high", kill=3)
    (ideas / "selected.json").write_text(json.dumps(rank0), encoding="utf-8")

    cands = [rank0, _candidate("h1", feasibility="high", kill=2), _candidate("h2", feasibility="medium")]
    portfolio.select_portfolio(cands, project_id=pid, k=2)

    on_disk = json.loads((ideas / "portfolio.json").read_text(encoding="utf-8"))
    assert on_disk["k"] == 2
    assert [r["hypothesis_id"] for r in on_disk["ranked"]] == ["h0", "h1"]
    # Lean projection shape — no free-text method sketches leaked into the index.
    assert set(on_disk["ranked"][0]) == {"hypothesis_id", "title", "rank", "primary_metric", "feasibility"}
    # Backward compat: selected.json untouched.
    assert json.loads((ideas / "selected.json").read_text(encoding="utf-8"))["hypothesis_id"] == "h0"


def test_select_portfolio_no_disk_write_without_project_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(portfolio, "WORKSPACE_ROOT", tmp_path)
    sel = portfolio.select_portfolio([_candidate("h1"), _candidate("h2")], k=2)
    assert not (tmp_path / "p" / "ideas" / "portfolio.json").exists()
    assert len(sel["ranked"]) == 2  # pure return, no side effect


# --------------------------------------------------------------------------- #
# aggregate_portfolio — honest best selection (never cherry-pick a metric)
# --------------------------------------------------------------------------- #


def test_aggregate_picks_most_favorable_anchored_verdict() -> None:
    h1 = _candidate("h1")
    h2 = _candidate("h2")
    per = [
        _per_candidate("h1", _metrics_positive("h1"), h1),     # positive_significant
        _per_candidate("h2", _metrics_negative(), h2),          # negative
    ]
    agg = portfolio.aggregate_portfolio(per)
    assert agg["best_candidate_id"] == "h1"
    assert agg["portfolio_verdict"] == "mixed_portfolio"
    assert agg["summary"][0]["is_best"] is True
    assert agg["summary"][0]["verdict"] == "positive_significant"
    assert agg["summary"][1]["verdict"] == "negative"


def test_aggregate_all_negative_portfolio_reports_all_negative_and_picks_highest_anchor() -> None:
    """Honesty: when every candidate is negative, the portfolio verdict is
    'all_negative' and best is STILL the highest anchored verdict — never upgraded,
    never shored up on a friendlier metric."""
    h1 = _candidate("h1", feasibility="high")
    h2 = _candidate("h2", feasibility="medium")
    per = [
        _per_candidate("h1", _metrics_negative(seed_count=5), h1),  # negative, 5 seeds
        _per_candidate("h2", _metrics_negative(seed_count=3), h2),  # negative, 3 seeds
    ]
    agg = portfolio.aggregate_portfolio(per)
    assert agg["portfolio_verdict"] == "all_negative"
    assert agg["best_candidate_id"] == "h1"  # tie on verdict → seed_count 5 > 3
    assert agg["best_candidate"]["hypothesis_id"] == "h1"
    # best verdict stays negative — not reframed.
    assert next(r for r in agg["summary"] if r["is_best"])["verdict"] == "negative"


def test_aggregate_tiebreak_feasibility_when_verdict_and_seeds_equal() -> None:
    h_high = _candidate("hA", feasibility="high")
    h_low = _candidate("hB", feasibility="low")
    per = [
        _per_candidate("hB", _metrics_negative(seed_count=4), h_low),
        _per_candidate("hA", _metrics_negative(seed_count=4), h_high),
    ]
    agg = portfolio.aggregate_portfolio(per)
    assert agg["best_candidate_id"] == "hA"  # same verdict+seeds → feasibility high wins


def test_aggregate_all_positive_labels_best_verdict() -> None:
    h1 = _candidate("h1")
    h2 = _candidate("h2")
    per = [_per_candidate("h1", _metrics_positive("h1"), h1), _per_candidate("h2", _metrics_positive("h2"), h2)]
    agg = portfolio.aggregate_portfolio(per)
    assert agg["portfolio_verdict"] == "best=positive_significant"


def test_aggregate_summary_row_fields() -> None:
    h = {
        "hypothesis_id": "h1", "title": "t", "primary_metric": "error_rate_at_20pct_abstain",
        "feasibility": "high",
        "kill_criteria": ["error_rate_at_20pct_abstain not lower than baseline"],
        "expected_positive_outcome": "error drops",
        "expected_negative_outcome": "error stays",
    }
    metrics = _metrics_positive("h1")
    # Force a tripped kill + downgrade so the summary surfaces kill_tripped/downgraded.
    metrics["results"] = [
        {"system_name": "proposed", "metric_name": "error_rate_at_20pct_abstain", "metric_value": 0.6,
         "n_test": 100, "dataset_name": "d1", "seed": 1},
    ] + metrics["results"]
    per = [_per_candidate("h1", metrics, h)]
    agg = portfolio.aggregate_portfolio(per)
    row = agg["summary"][0]
    for field in ("candidate_id", "title", "primary_metric", "beats_baseline", "verdict",
                  "kill_tripped", "downgraded", "execution_status", "feasibility", "is_best"):
        assert field in row


def test_aggregate_empty_portfolio() -> None:
    agg = portfolio.aggregate_portfolio([])
    assert agg["best_candidate_id"] is None
    assert agg["summary"] == []


# --------------------------------------------------------------------------- #
# Step 3 — per-candidate execution isolation (candidate_subdir)
# --------------------------------------------------------------------------- #


def _patch_codegen(monkeypatch) -> dict:
    """Mock plan/codegen chat + sandbox so run_experiment_engineer produces real metrics
    without network. Returns a counter dict for introspection."""
    calls: dict = {"n": 0}

    def fake_chat(msgs, model=None):
        calls["n"] += 1
        prompt = msgs[0]["content"]
        if "实验计划生成" in prompt or "输出格式（JSON" in prompt:
            return {"choices": [{"message": {"content": json.dumps({
                "dataset": {"name": "d1"}, "datasets": [{"name": "d1"}],
                "metrics": [{"name": "macro_f1", "primary": True}],
                "systems": [{"name": "proposed", "role": "proposed"},
                            {"name": "baseline", "role": "baseline"}],
                "success_criterion": "", "failure_criterion": "",
            })}}]}
        code = (
            "import json\n"
            "print('__RESULT__', json.dumps([\n"
            "  {'system_name':'proposed','metric_name':'macro_f1','metric_value':0.6,'n_test':100,'dataset_name':'d1','seed':1},\n"
            "  {'system_name':'baseline','metric_name':'macro_f1','metric_value':0.5,'n_test':100,'dataset_name':'d1','seed':1}\n"
            "]))\n"
        )
        return {"choices": [{"message": {"content": "```python\n" + code + "```"}}]}

    def fake_run(project_id, code=None, execution_backend=None):  # noqa: ANN001
        outputs = {
            "returncode": 0,
            "result": [
                {"system_name": "proposed", "metric_name": "macro_f1", "metric_value": 0.6,
                 "n_test": 100, "dataset_name": "d1", "seed": 1},
                {"system_name": "baseline", "metric_name": "macro_f1", "metric_value": 0.5,
                 "n_test": 100, "dataset_name": "d1", "seed": 1},
            ],
            "stderr": "",
        }
        return ("ok", outputs)

    monkeypatch.setattr(experiment_engineer, "chat", fake_chat)
    monkeypatch.setattr(experiment_engineer, "run_python_in_sandbox", fake_run)
    return calls


def test_run_experiment_engineer_candidate_subdir_isolates_artifacts(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(experiment_engineer, "WORKSPACE_ROOT", tmp_path)
    _patch_codegen(monkeypatch)
    notes = {"known_baselines": []}

    m1 = experiment_engineer.run_experiment_engineer(
        "p", "idea", notes, _candidate("h1"), candidate_subdir="h1")
    m2 = experiment_engineer.run_experiment_engineer(
        "p", "idea", notes, _candidate("h2"), candidate_subdir="h2")

    assert m1["execution_status"] == "success"
    assert (tmp_path / "p" / "candidates" / "h1" / "artifacts" / "metrics.json").is_file()
    assert (tmp_path / "p" / "candidates" / "h2" / "artifacts" / "metrics.json").is_file()
    # No cross-contamination: nothing promoted to the top-level artifacts dir.
    assert not (tmp_path / "p" / "artifacts" / "metrics.json").exists()


def test_run_experiment_engineer_default_subdir_is_top_level(monkeypatch, tmp_path) -> None:
    """candidate_subdir=None → existing behaviour: metrics at top-level (K=1 path)."""
    monkeypatch.setattr(experiment_engineer, "WORKSPACE_ROOT", tmp_path)
    _patch_codegen(monkeypatch)
    m = experiment_engineer.run_experiment_engineer("p", "idea", {"known_baselines": []}, _candidate("h1"))
    assert (tmp_path / "p" / "artifacts" / "metrics.json").is_file()
    assert not (tmp_path / "p" / "candidates").exists()
    assert m["execution_status"] == "success"


# --------------------------------------------------------------------------- #
# Step 3/4/5 — pipeline.run_portfolio_experiments (orchestration)
# --------------------------------------------------------------------------- #


def _seed_idea_workspace(monkeypatch, tmp_path, cands: list[dict]) -> str:
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(portfolio, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(report_generator, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(experiment_engineer, "WORKSPACE_ROOT", tmp_path)
    pid = "p"
    ideas = tmp_path / pid / "ideas"
    ideas.mkdir(parents=True)
    (ideas / "candidates.json").write_text(json.dumps(cands), encoding="utf-8")
    (ideas / "selected.json").write_text(json.dumps(cands[0]), encoding="utf-8")  # rank-0
    return pid


def _patch_run_experiment_engineer_per_candidate(monkeypatch, metrics_by_seed_delta: dict | None = None) -> None:
    """Return distinct metrics per candidate_subdir so aggregation is non-trivial.
    Default: h1 → positive (proposed 0.6 > baseline 0.5), h2 → negative (0.4 < 0.5)."""
    def fake_run(project_id, idea, notes, hyp, candidate_subdir=None):  # noqa: ANN001
        sub = candidate_subdir or "_top"
        if sub in ("h2", "h3"):
            proposed, baseline = 0.40, 0.50
        else:
            proposed, baseline = 0.60, 0.50
        return {
            "execution_status": "success",
            "dataset": "d1",
            "results": [
                {"system_name": "proposed", "metric_name": "macro_f1", "metric_value": proposed,
                 "n_test": 100, "dataset_name": "d1", "seed": s} for s in range(1, 4)
            ] + [
                {"system_name": "baseline", "metric_name": "macro_f1", "metric_value": baseline,
                 "n_test": 100, "dataset_name": "d1", "seed": s} for s in range(1, 4)
            ],
            "baseline_comparison": {
                "metric_name": "macro_f1", "direction": "higher_is_better",
                "overall_beats_baseline": proposed > baseline,
                "datasets": [{"dataset": "d1", "baseline_system": "baseline", "proposed_system": "proposed",
                              "baseline_metric": baseline, "proposed_metric": proposed,
                              "delta": round(proposed - baseline, 6), "beats_baseline": proposed > baseline,
                              "n_seeds_baseline": 3, "n_seeds_proposed": 3}],
            },
            "abstention_metrics": {},
            "missing_baselines": [], "underpowered": None,
            "attempts_used": 1, "repair_attempts": 0, "returncode": 0,
            "statistics": {"seed_count": 3, "any_significant": proposed > baseline,
                           "significance_tests": []},
        }
    monkeypatch.setattr(experiment_engineer, "run_experiment_engineer", fake_run)


def test_run_portfolio_experiments_k2_runs_each_candidate_separately(monkeypatch, tmp_path) -> None:
    cands = [_candidate("h1", feasibility="high", kill=2), _candidate("h2", feasibility="high", kill=1)]
    pid = _seed_idea_workspace(monkeypatch, tmp_path, cands)
    _patch_run_experiment_engineer_per_candidate(monkeypatch)

    best_metrics = pipeline.run_portfolio_experiments(pid, "idea", {"known_baselines": []}, cands, k=2)

    # Each candidate has its own subdir + metrics + verdict.
    for cid in ("h1", "h2"):
        assert (tmp_path / pid / "candidates" / cid / "artifacts" / "metrics.json").is_file()
        assert (tmp_path / pid / "candidates" / cid / "verdict.json").is_file()
    # Ledger written.
    ledger = json.loads((tmp_path / pid / "ledger" / "portfolio.json").read_text(encoding="utf-8"))
    assert ledger["best_candidate_id"] == "h1"  # h1 positive, h2 negative
    assert ledger["portfolio_verdict"] == "mixed_portfolio"
    assert len(ledger["summary"]) == 2
    # Best candidate promoted to top-level so review/report operate on it unchanged.
    assert (tmp_path / pid / "artifacts" / "metrics.json").is_file()
    top = json.loads((tmp_path / pid / "artifacts" / "metrics.json").read_text(encoding="utf-8"))
    assert top["baseline_comparison"]["overall_beats_baseline"] is True
    assert best_metrics["baseline_comparison"]["overall_beats_baseline"] is True
    # ideas/portfolio.json index written.
    idx = json.loads((tmp_path / pid / "ideas" / "portfolio.json").read_text(encoding="utf-8"))
    assert idx["k"] == 2


def test_run_portfolio_experiments_all_negative_is_honest(monkeypatch, tmp_path) -> None:
    cands = [_candidate("h1", feasibility="high"), _candidate("h2", feasibility="medium")]
    pid = _seed_idea_workspace(monkeypatch, tmp_path, cands)
    _patch_run_experiment_engineer_per_candidate(monkeypatch)  # both lose (h1 top-level... wait)

    # Force BOTH candidates to lose by patching so every subdir is negative.
    def all_negative(project_id, idea, notes, hyp, candidate_subdir=None):  # noqa: ANN001
        return fake_factory(0.40, 0.50)
    def fake_factory(proposed, baseline):
        return {
            "execution_status": "success", "dataset": "d1",
            "results": [{"system_name": "proposed", "metric_name": "macro_f1", "metric_value": proposed,
                         "n_test": 100, "dataset_name": "d1", "seed": s} for s in range(1, 4)]
                     + [{"system_name": "baseline", "metric_name": "macro_f1", "metric_value": baseline,
                         "n_test": 100, "dataset_name": "d1", "seed": s} for s in range(1, 4)],
            "baseline_comparison": {"metric_name": "macro_f1", "direction": "higher_is_better",
                "overall_beats_baseline": False,
                "datasets": [{"dataset": "d1", "beats_baseline": False, "baseline_metric": baseline,
                              "proposed_metric": proposed, "delta": round(proposed - baseline, 6),
                              "baseline_system": "baseline", "proposed_system": "proposed",
                              "n_seeds_baseline": 3, "n_seeds_proposed": 3}]},
            "abstention_metrics": {}, "missing_baselines": [], "underpowered": None,
            "attempts_used": 1, "repair_attempts": 0, "returncode": 0,
            "statistics": {"seed_count": 3, "any_significant": False, "significance_tests": []},
        }
    monkeypatch.setattr(experiment_engineer, "run_experiment_engineer", all_negative)

    pipeline.run_portfolio_experiments(pid, "idea", {"known_baselines": []}, cands, k=2)
    ledger = json.loads((tmp_path / pid / "ledger" / "portfolio.json").read_text(encoding="utf-8"))
    assert ledger["portfolio_verdict"] == "all_negative"
    # Best is still the highest-anchored negative (here a tie → feasibility high → h1), never upgraded.
    assert ledger["best_candidate_id"] == "h1"
    best_row = next(r for r in ledger["summary"] if r["is_best"])
    assert best_row["verdict"] == "negative"


def test_run_portfolio_experiments_k1_is_backward_compatible(monkeypatch, tmp_path) -> None:
    """K=1 ≡ old single-hypothesis path: top-level metrics.json, selected.json
    unchanged, NO candidates/ subtree, and the rank-0 candidate is what ran."""
    cands = [_candidate("h1", feasibility="high", kill=2), _candidate("h2", feasibility="medium")]
    pid = _seed_idea_workspace(monkeypatch, tmp_path, cands)
    _patch_run_experiment_engineer_per_candidate(monkeypatch)

    pipeline.run_portfolio_experiments(pid, "idea", {"known_baselines": []}, cands, k=1)

    assert (tmp_path / pid / "artifacts" / "metrics.json").is_file()  # top-level (the single run)
    assert not (tmp_path / pid / "candidates").exists()               # no per-candidate subtree
    # selected.json untouched (still rank-0).
    assert json.loads((tmp_path / pid / "ideas" / "selected.json").read_text(encoding="utf-8"))["hypothesis_id"] == "h1"


def test_load_selected_hypothesis_prefers_portfolio_best(monkeypatch, tmp_path) -> None:
    """only-add: with a portfolio ledger, review/report load the BEST candidate's
    hypothesis; without one they fall back to selected.json (rank-0)."""
    monkeypatch.setattr(pipeline, "WORKSPACE_ROOT", tmp_path)
    pid = "p"
    ideas = tmp_path / pid / "ideas"
    ideas.mkdir(parents=True)
    (ideas / "selected.json").write_text(json.dumps(_candidate("h0")), encoding="utf-8")
    best = _candidate("h2", feasibility="high")
    ledger = tmp_path / pid / "ledger"
    ledger.mkdir(parents=True)
    (ledger / "portfolio.json").write_text(json.dumps({
        "best_candidate_id": "h2", "portfolio_verdict": "best=positive_significant",
        "best_candidate": best, "summary": [],
    }), encoding="utf-8")
    assert pipeline.load_selected_hypothesis(pid)["hypothesis_id"] == "h2"

    # Remove ledger → falls back to selected.json (rank-0).
    (ledger / "portfolio.json").unlink()
    assert pipeline.load_selected_hypothesis(pid)["hypothesis_id"] == "h0"


# --------------------------------------------------------------------------- #
# Step 6 — report Portfolio Summary table
# --------------------------------------------------------------------------- #


def test_report_renders_portfolio_summary_table(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(report_generator, "WORKSPACE_ROOT", tmp_path)
    pid = "p"
    proj = tmp_path / pid
    for sub in ("literature", "experiments", "reviews", "ledger"):
        (proj / sub).mkdir(parents=True)
    (proj / "literature" / "papers.jsonl").write_text('{"title": "Real Paper"}\n', encoding="utf-8")
    (proj / "ledger" / "portfolio.json").write_text(json.dumps({
        "best_candidate_id": "h1",
        "portfolio_verdict": "mixed_portfolio",
        "summary": [
            {"candidate_id": "h1", "title": "Hyp A", "primary_metric": "macro_f1",
             "beats_baseline": True, "verdict": "positive_significant",
             "kill_tripped": False, "downgraded": False, "execution_status": "success",
             "feasibility": "high", "is_best": True},
            {"candidate_id": "h2", "title": "Hyp B", "primary_metric": "macro_f1",
             "beats_baseline": False, "verdict": "negative",
             "kill_tripped": False, "downgraded": False, "execution_status": "success",
             "feasibility": "high", "is_best": False},
        ],
        "note": "non-best candidates stop at metrics+verdict (cost control)",
    }), encoding="utf-8")

    report_generator.generate_research_report(
        pid, "idea", _candidate("h1"), _metrics_positive("h1"),
        {"publish_gate": "no_evidence", "required_experiments": []},
        {"decision": {}, "conclusion": "TL;DR"})
    report = (proj / "research_report.md").read_text(encoding="utf-8")
    assert "Portfolio Summary" in report
    assert "mixed_portfolio" in report
    assert "Hyp A" in report and "Hyp B" in report
    assert "positive_significant" in report and "negative" in report
