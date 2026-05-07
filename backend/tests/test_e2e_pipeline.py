"""End-to-end pipeline test — tests core pipeline without database/Docker.

Tests: planner → codegen → new modules → writer
"""
import os
import sys
import json
import tempfile
from pathlib import Path

import pytest

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _build_plan():
    """Test that planner creates a valid plan with problem anchor."""
    from services.autoresearch.planner import ResearchPlanner
    planner = ResearchPlanner()
    return planner._fallback_plan(
        topic="Sentiment Analysis on Short Texts",
        task_family="text_classification",
        literature=[],
        benchmark_name="sentiment140",
        benchmark_description="Twitter Sentiment Analysis",
    )


@pytest.fixture
def plan():
    return _build_plan()


def test_planner(plan):
    """Test that planner creates a valid plan with problem anchor."""
    assert plan.topic == "Sentiment Analysis on Short Texts"
    assert plan.task_family == "text_classification"
    assert plan.hypotheses
    assert plan.planned_contributions
    print(f"[PASS] planner: {len(plan.hypotheses)} hypotheses, {len(plan.planned_contributions)} contributions")


def test_problem_anchor(plan):
    """Test #9 Problem Anchor."""
    from services.autoresearch.orchestrator import AutoResearchOrchestrator
    orch = AutoResearchOrchestrator()
    anchored = orch._freeze_problem_anchor(plan)
    assert hasattr(anchored, "problem_anchor")
    assert anchored.problem_anchor is not None
    assert "PROBLEM_ANCHOR" in anchored.problem_anchor
    print(f"[PASS] problem_anchor: {anchored.problem_anchor[:60]}...")


def test_5block_experiment_design(plan):
    """Test #6 5-Block Experiment Design."""
    from services.autoresearch.orchestrator import AutoResearchOrchestrator
    from schemas.autoresearch import ExperimentSpec, DatasetSpec
    orch = AutoResearchOrchestrator()
    spec = ExperimentSpec(
        task_family="text_classification",
        benchmark_name="sentiment140",
        benchmark_description="Twitter Sentiment Analysis",
        dataset=DatasetSpec(name="sentiment140", description="test", train_size=100, test_size=50),
        hypothesis="Test hypothesis",
    )
    class MockBenchmark:
        benchmark_name = "sentiment140"
        benchmark_description = "Twitter Sentiment Analysis"
        task_family = "text_classification"
        source = type("S", (), {"kind": "builtin"})()
        payload = {"name": "sentiment140"}
    enhanced = orch._apply_5block_experiment_design(plan, spec, MockBenchmark())
    outline = enhanced.experiment_outline
    assert any("Block 1" in step for step in outline), f"Missing Block 1 in: {outline[:3]}"
    assert any("Block 5" in step for step in outline), f"Missing Block 5 in: {outline[-3:]}"
    print(f"[PASS] 5block_experiment: {len(outline)} steps including 5 blocks")


def _make_spec():
    """Helper to create a valid ExperimentSpec."""
    from schemas.autoresearch import ExperimentSpec, DatasetSpec
    return ExperimentSpec(
        task_family="text_classification",
        benchmark_name="sentiment140",
        benchmark_description="Twitter Sentiment Analysis",
        dataset=DatasetSpec(name="sentiment140", description="test", train_size=100, test_size=50),
        hypothesis="Test hypothesis",
        search_strategies=["naive_bayes", "weighted_bayes"],
        seeds=[0, 42],
    )


def test_ablation_planner(plan):
    """Test #7 Ablation Planner."""
    from services.autoresearch.ablation_planner import AblationPlanner
    planner = AblationPlanner()
    spec = _make_spec()
    result = planner.plan_ablations(plan=plan, spec=spec)
    assert result["component_ablations"]
    assert result["suggested_order"]
    print(f"[PASS] ablation_planner: {result['total_planned']} ablations, "
          f"{len(result['unnecessary_ablations'])} unnecessary")


def test_claim_evidence_matrix():
    """Test #1 Claims-Evidence Matrix."""
    from services.autoresearch.claim_evidence_gate import ClaimEvidenceMatrix
    from schemas.autoresearch import ResearchPlan, ResultArtifact
    matrix_builder = ClaimEvidenceMatrix()

    plan = ResearchPlan(
        topic="Test", title="Test", task_family="text_classification",
        problem_statement="Test", motivation="Test", proposed_method="Test",
        hypotheses=["Naive Bayes will outperform majority baseline"],
        planned_contributions=["A comparison of methods"],
    )
    artifact = ResultArtifact(
        status="done", summary="done", primary_metric="macro_f1",
        logs="", environment={}, outputs={},
        system_results=[{"system": "naive_bayes", "metrics": {"accuracy": 0.82, "macro_f1": 0.79}}],
        key_findings=["Naive Bayes achieved 79% macro F1"],
        tables=[{"title": "Main Results", "columns": ["system", "accuracy"], "rows": [["nb", "0.82"]]}],
    )
    matrix = matrix_builder.build_matrix(plan=plan, artifact=artifact)
    assert matrix["total_claims"] > 0
    print(f"[PASS] claim_evidence_matrix: {matrix['supported_claims']}/{matrix['total_claims']} supported, "
          f"coverage={matrix['coverage_score']:.0%}")


def test_paper_blueprint():
    """Test #4 Paper Blueprint."""
    from services.autoresearch.paper_blueprint import PaperBlueprint
    from schemas.autoresearch import ResearchPlan, ResultArtifact
    builder = PaperBlueprint()
    plan = ResearchPlan(
        topic="Test", title="Test", task_family="text_classification",
        problem_statement="Test", motivation="Test", proposed_method="Test",
    )
    artifact = ResultArtifact(
        status="done", summary="done", primary_metric="macro_f1",
        logs="", environment={}, outputs={},
        system_results=[
            {"system": "baseline", "metrics": {"accuracy": 0.6}},
            {"system": "method", "metrics": {"accuracy": 0.82}},
        ],
        tables=[{"title": "Main Results", "columns": ["system", "acc"], "rows": [["base", "0.6"], ["method", "0.82"]]}],
    )
    blueprint = builder.build_blueprint(plan=plan, artifact=artifact)
    assert blueprint["total_outputs"] > 0
    assert blueprint["data_coverage"]["coverage"] > 0
    print(f"[PASS] paper_blueprint: {blueprint['total_outputs']} outputs, "
          f"coverage={blueprint['data_coverage']['coverage']:.0%}")


def test_writing_audit():
    """Test #2 5-Pass Writing Quality Audit."""
    from services.autoresearch.writing_audit import run_writing_audit, audit_report_to_markdown
    sample_paper = """# Test Paper

## Abstract
This paper presents a method for text classification. In order to demonstrate the effectiveness, we make a comparison between methods. It is important to note that the results are significant. Due to the fact that the data is limited, we use a small model. The method achieves an accuracy of 0.82 and a macro_f1 of 0.82 on the benchmark.

## Introduction
Text classification is an important task in natural language processing. We propose a novel approach that leverages lexical features for the purpose of achieving competitive performance without external dependencies.

## Related Work
Prior work on text classification has explored various approaches. Smith et al. demonstrated that simple features can achieve strong results. Jones (2023) showed that in spite of the fact that deep learning dominates, lightweight methods remain competitive on small datasets with accuracy of 0.75.

## Method
Our method utilizes a Naive Bayes classifier with TF-IDF inspired term weighting. We carry out an investigation into the impact of different weighting schemes.

## Results
The results demonstrate that our method achieves an accuracy of 0.82 on the test set. The macro_f1 score is 0.79 which is a different number from the accuracy mentioned earlier. We also note that the method achieves 0.65 on sentiment140 but we report 0.82 accuracy here.
"""
    report = run_writing_audit(sample_paper)
    assert report["total_issues"] > 0, "Expected to find issues in deliberately bad text"
    print(f"[PASS] writing_audit: {report['total_issues']} issues found "
          f"(clutter={report['pass1_clutter']['count']}, "
          f"voice={report['pass2_active_voice']['count']}, "
          f"sentences={report['pass3_sentences']['count']}, "
          f"keywords={report['pass4_keywords']['count']}, "
          f"numbers={report['pass5_numbers']['count']})")


def test_reverse_outline():
    """Test #5 Reverse Outline Test."""
    from services.autoresearch.reverse_outline import generate_reverse_outline
    paper = """# Test Paper

## Abstract
This paper introduces a lightweight method for sentiment classification. We evaluate on Twitter data and show improvements over baselines.

## Introduction
Sentiment analysis is a key NLP task with many applications. Our method uses lexical features for robust classification.

## Method
We propose a Naive Bayes variant with IDF weighting. The classifier is trained on bag-of-words features with term frequency normalization.

## Results
Experimental results show our method outperforms baselines by 5 percentage points. The confusion matrix reveals that negative sentiment is harder to classify correctly.

## Conclusion
We presented a simple yet effective approach for sentiment analysis. Future work will explore transfer learning approaches.
"""
    result = generate_reverse_outline(paper)
    assert result["total_paragraphs"] > 0
    print(f"[PASS] reverse_outline: {result['total_paragraphs']} paragraphs, "
          f"coherence={result['coherence_score']:.2f}, "
          f"issues={result['total_issues']}")


def test_self_optimization():
    """Test #8 Self-Optimization Trace."""
    from services.autoresearch.self_optimization import SelfOptimizationTrace
    from schemas.autoresearch import ResultArtifact
    optimizer = SelfOptimizationTrace()
    artifact = ResultArtifact(
        status="done", summary="done", primary_metric="macro_f1",
        logs="", environment={}, outputs={},
        system_results=[{"system": "method", "metrics": {"accuracy": 0.55}}],
        sweep_results=[],
    )
    trace = optimizer.analyze_and_suggest(artifact=artifact, round_index=1, max_rounds=3)
    assert trace["severity"] in ("good", "needs_improvement", "critical")
    print(f"[PASS] self_optimization: severity={trace['severity']}, "
          f"issues={len(trace['issues_found'])}, "
          f"suggestions={len(trace['suggestions'])}")


def test_citation_verifier():
    """Test #3 Citation Verification Chain."""
    from services.autoresearch.citation_verifier import CitationVerifier
    verifier = CitationVerifier()
    # Test extraction from markdown
    paper = """# Paper

## References
- Vaswani et al. "Attention Is All You Need", NeurIPS 2017.
- Smith, J. "Deep Learning for NLP", ACL 2023.
- Unknown Author. "Fake Paper That Does Not Exist", arXiv 2025.
"""
    citations = verifier.extract_citations_from_markdown(paper)
    print(f"[PASS] citation_verifier: extracted {len(citations)} citations from markdown")


def test_integrity_labels():
    """Test #11 Experiment Integrity Labels."""
    from services.autoresearch.orchestrator import AutoResearchOrchestrator
    from schemas.autoresearch import ResultArtifact
    orch = AutoResearchOrchestrator()
    artifact = ResultArtifact(
        status="done", summary="done", primary_metric="macro_f1",
        logs="", environment={"executor_mode": "sandbox"}, outputs={},
    )
    labeled = orch._label_experiment_integrity(artifact)
    integrity = labeled.environment.get("evaluation_integrity", {})
    assert integrity.get("evaluation_type") == "real_gt"
    assert integrity.get("claim_ceiling") == "full_performance_claims"
    print(f"[PASS] integrity_labels: type={integrity['evaluation_type']}, ceiling={integrity['claim_ceiling']}")


def test_simplicity_criterion():
    """Test #13 Simplicity Criterion."""
    from services.autoresearch.orchestrator import AutoResearchOrchestrator
    from schemas.autoresearch import ResultArtifact
    orch = AutoResearchOrchestrator()
    artifact = ResultArtifact(
        status="done", summary="done", primary_metric="macro_f1",
        logs="", environment={}, outputs={},
    )
    simple = orch._apply_simplicity_score(artifact, "naive_bayes_tfidf")
    assert simple.environment["simplicity_flag"] == "simple"

    complex_artifact = orch._apply_simplicity_score(artifact, "ensemble_stacking_multi_head")
    assert complex_artifact.environment["simplicity_flag"] == "complex"
    print("[PASS] simplicity_criterion: simple=naive_bayes, complex=ensemble_stacking")


def test_codegen():
    """Test code generation produces valid Python (fallback template)."""
    from services.autoresearch.codegen import ExperimentCodeGenerator
    from schemas.autoresearch import ResearchPlan
    gen = ExperimentCodeGenerator()
    plan = ResearchPlan(
        topic="Sentiment Analysis", title="Test", task_family="text_classification",
        problem_statement="Test", motivation="Test", proposed_method="Weighted Naive Bayes",
    )
    spec = _make_spec()
    # Test fallback code generation (doesn't require LLM)
    code = gen._fallback_code(plan, spec,
        benchmark_payload={
            "name": "sentiment140",
            "label_space": ["positive", "negative"],
            "texts": ["good", "bad"],
            "labels": ["positive", "negative"],
            "feature_names": ["good", "bad"],
        },
        strategy="weighted_bayes",
    )
    assert len(code) > 100
    compile(code, "<test>", "exec")
    print(f"[PASS] codegen: generated {len(code)} chars of valid Python")


if __name__ == "__main__":
    print("=" * 60)
    print("ScholarFlow End-to-End Pipeline Test")
    print("=" * 60)
    print()

    results = []

    # Phase 1: Planning
    print("--- Phase 1: Planning ---")
    plan = _build_plan()
    test_planner(plan)
    test_problem_anchor(plan)
    test_5block_experiment_design(plan)

    # Phase 2: Experiment Design
    print()
    print("--- Phase 2: Experiment Design ---")
    test_ablation_planner(plan)
    test_codegen()

    # Phase 3: Result Analysis
    print()
    print("--- Phase 3: Result Analysis ---")
    test_claim_evidence_matrix()
    test_self_optimization()
    test_integrity_labels()
    test_simplicity_criterion()

    # Phase 4: Paper Writing
    print()
    print("--- Phase 4: Paper Writing ---")
    test_paper_blueprint()
    test_writing_audit()
    test_reverse_outline()
    test_citation_verifier()

    print()
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
