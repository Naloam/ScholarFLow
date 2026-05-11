"""Test paper generation with GLM API.

Usage:
  LITELLM_API_KEY=xxx LLM_API_BASE=https://api.siliconflow.cn/v1 LLM_MODEL=openai/Pro/zai-org/GLM-5.1 python tests/glm_paper_smoke.py

The project settings loader reads .env files itself. Do not seed default
LLM_MODEL/OPENAI_API_KEY values here; doing that before importing settings would
mask the real local configuration.
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Smoke tests should finish with slow thinking models. The production defaults
# still run the full outline/section/review loop unless these variables are set.
os.environ.setdefault("AUTORESEARCH_PAPER_WRITER_SECTION_PASS", "0")
os.environ.setdefault("AUTORESEARCH_PAPER_WRITER_OUTLINE_PASS", "0")
os.environ.setdefault("AUTORESEARCH_PAPER_WRITER_REVIEW_ROUNDS", "0")

from config.settings import settings
print(f"API key configured: {bool(settings.llm_api_key)}")
print(f"API base: {settings.llm_api_base}")
print(f"Model: {settings.llm_model or os.getenv('LLM_MODEL')}")
print(
    "Paper writer smoke budget: "
    f"section_pass={os.getenv('AUTORESEARCH_PAPER_WRITER_SECTION_PASS')}, "
    f"outline_pass={os.getenv('AUTORESEARCH_PAPER_WRITER_OUTLINE_PASS')}, "
    f"review_rounds={os.getenv('AUTORESEARCH_PAPER_WRITER_REVIEW_ROUNDS')}"
)
print()

# Step 1: Test LLM connectivity
print("--- Step 1: LLM Connectivity ---")
from services.llm.client import chat
from services.llm.response_utils import get_message_content

resp = chat([
    {"role": "system", "content": "You are a research assistant. Be concise."},
    {"role": "user", "content": "What is Naive Bayes text classification? Answer in exactly 2 sentences."},
], temperature=0.3)
content = get_message_content(resp)
if content.strip():
    print(f"[OK] LLM response: {content[:120]}")
else:
    print("[FAIL] LLM returned empty response. Check API key and model name.")
    sys.exit(1)

# Step 2: Build research plan
print()
print("--- Step 2: Research Plan ---")
from services.autoresearch.planner import ResearchPlanner

planner = ResearchPlanner()
plan = planner._fallback_plan(
    topic="Sentiment Analysis on Short Texts",
    task_family="text_classification",
    literature=[],
    benchmark_name="sentiment140",
    benchmark_description="Twitter Sentiment Analysis",
)
print(f"[OK] Plan: {plan.title}")
print(f"  Method: {plan.proposed_method[:80]}")
print(f"  Hypotheses: {len(plan.hypotheses)}")
for h in plan.hypotheses:
    print(f"    - {h[:80]}")

# Step 3: Build experiment spec
print()
print("--- Step 3: Experiment Spec ---")
from schemas.autoresearch import ExperimentSpec, DatasetSpec, LiteratureInsight

spec = ExperimentSpec(
    task_family="text_classification",
    benchmark_name="sentiment140",
    benchmark_description="Twitter Sentiment Analysis",
    dataset=DatasetSpec(name="sentiment140", description="Twitter Sentiment", train_size=100, test_size=50),
    hypothesis=plan.hypotheses[0] if plan.hypotheses else "Test",
    search_strategies=["weighted_bayes", "naive_bayes"],
    seeds=[42],
)
print(f"[OK] Spec: {spec.task_family}, strategies={spec.search_strategies}")

literature = [
    LiteratureInsight(
        paper_id="pang-2002",
        title="Thumbs up? Sentiment Classification using Machine Learning Techniques",
        year=2002,
        source="local_smoke_fixture",
        insight="Early sentiment classification work established supervised lexical models as strong baselines for polarity detection.",
        method_hint="Compare lightweight probabilistic classifiers against simple baselines before claiming model improvements.",
        gap_hint="Small-resource settings still need transparent lexical baselines with explicit error and scope reporting.",
    ),
    LiteratureInsight(
        paper_id="go-2009",
        title="Twitter Sentiment Classification using Distant Supervision",
        year=2009,
        source="local_smoke_fixture",
        insight="Distantly supervised Twitter sentiment datasets make short-text polarity classification scalable but noisy.",
        method_hint="Treat tweet sentiment labels as useful benchmark signals while preserving caveats about label noise.",
        gap_hint="Benchmark-local results should be framed as bounded evidence rather than broad claims about all social media sentiment.",
    ),
]
print(f"  Literature fixtures: {len(literature)}")

# Step 4: Generate experiment code (fallback, no LLM needed)
print()
print("--- Step 4: Code Generation ---")
from services.autoresearch.codegen import ExperimentCodeGenerator

codegen = ExperimentCodeGenerator()
code = codegen._fallback_code(plan, spec, {
    "name": "sentiment140",
    "label_space": ["positive", "negative"],
    "texts": ["I love this", "Terrible", "Great movie", "Bad service"],
    "labels": ["positive", "negative", "positive", "negative"],
    "feature_names": ["good", "bad", "love", "hate"],
}, strategy="weighted_bayes")
print(f"[OK] Generated {len(code)} chars of Python code")

# Step 5: Build claim-evidence matrix + blueprint
print()
print("--- Step 5: Claims-Evidence Matrix + Blueprint ---")
from services.autoresearch.claim_evidence_gate import ClaimEvidenceMatrix
from services.autoresearch.paper_blueprint import PaperBlueprint
from schemas.autoresearch import ResultArtifact

artifact = ResultArtifact(
    status="done",
    summary="Experiment completed successfully",
    primary_metric="macro_f1",
    logs="Training complete. Evaluation complete.",
    environment={"executor_mode": "sandbox"},
    outputs={},
    system_results=[
        {"system": "weighted_bayes", "metrics": {"accuracy": 0.82, "macro_f1": 0.79}},
        {"system": "naive_bayes", "metrics": {"accuracy": 0.78, "macro_f1": 0.75}},
        {"system": "majority_baseline", "metrics": {"accuracy": 0.52, "macro_f1": 0.34}},
    ],
    key_findings=[
        "Weighted Bayes achieves 79% macro F1, outperforming plain Naive Bayes by 4 points",
        "Majority baseline achieves only 34% macro F1 on this balanced dataset",
    ],
    tables=[{
        "title": "Main Results",
        "columns": ["System", "Accuracy", "Macro F1"],
        "rows": [
            ["Weighted Bayes", "0.82", "0.79"],
            ["Naive Bayes", "0.78", "0.75"],
            ["Majority Baseline", "0.52", "0.34"],
        ],
    }],
)

matrix_builder = ClaimEvidenceMatrix()
matrix = matrix_builder.build_matrix(plan=plan, artifact=artifact, literature=literature)
print(f"[OK] Matrix: {matrix['supported_claims']}/{matrix['total_claims']} claims supported")

blueprint_builder = PaperBlueprint()
blueprint = blueprint_builder.build_blueprint(plan=plan, artifact=artifact)
print(f"[OK] Blueprint: {blueprint['total_outputs']} outputs, coverage={blueprint['data_coverage']['coverage']:.0%}")

# Step 6: Generate paper with LLM
print()
print("--- Step 6: Paper Generation (LLM) ---")
from services.autoresearch.writer import PaperWriter
from schemas.autoresearch import (
    AutoResearchClaimEvidenceMatrixRead, AutoResearchClaimEvidenceEntryRead,
)

writer = PaperWriter()

# Build a minimal claim evidence matrix in the expected format
claim_entries = []
for entry in matrix["claims"]:
    claim_entries.append(AutoResearchClaimEvidenceEntryRead(
        claim_id=entry["claim_id"],
        claim=entry["claim"],
        category="result",
        section_hint=entry.get("section_hint", "Results"),
        evidence_refs=entry["evidence_refs"],
        support_status=entry["support_status"],
        gaps=[],
    ))
from datetime import datetime
cem = AutoResearchClaimEvidenceMatrixRead(
    entries=claim_entries,
    generated_at=datetime.now().isoformat(),
)

try:
    paper = writer.write(
        plan, spec, artifact,
        literature=literature,
        attempts=[],
        benchmark_name="sentiment140",
        claim_evidence_matrix=cem,
        research_brief="The experiment tests lightweight classification methods on Twitter sentiment data. "
                       "Weighted Bayes with IDF-like term weighting outperforms both plain Naive Bayes and majority baseline. "
                       "The key finding is that term rarity weighting contributes a 4-point F1 improvement.",
        problem_anchor=plan.problem_anchor,
        paper_blueprint=blueprint,
    )
    print(f"[OK] Paper generated: {len(paper)} chars")
    print(f"  Sections: {paper.count('## ')}")

    # Save paper
    out_path = Path(__file__).parent.parent / "data" / "test_paper_output.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(paper)
    print(f"  Saved to: {out_path}")
except Exception as e:
    print(f"[ERROR] Paper generation failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("GLM Paper Generation Test Complete")
print("=" * 60)
