"""Session 12 (goal_session12) — cross-domain generalization.

CI-safe, network-free pure-logic tests: the dataset registry + capability note +
experiment routing are domain-agnostic, and the honesty gates (evidence/auditor)
do not assume claim-verification. Only-add — the claim-verification path stays
byte-equivalent (registry_note()/capability_note() default to it).
"""
from __future__ import annotations

from pathlib import Path

from services.research_harness import datasets, evidence
from services.research_harness.experiment_engineer import (
    _domain_from,
    _domain_preamble,
    _role_of,
)
from services.research_harness.sandbox_capabilities import (
    capability_note,
    domain_agnostic_note,
    domain_method_note,
)

SEED_DIR = Path(datasets.SEED_DIR)


# --------------------------------------------------------------------------- #
# Step 2: registry supports >=2 non-retrieval domains with loaders
# --------------------------------------------------------------------------- #


def test_registry_has_at_least_two_non_retrieval_domains() -> None:
    domains = {s.domain for s in datasets.DATASET_REGISTRY}
    non_claim = domains - {"claim_verification"}
    assert len(non_claim) >= 2, f"need >=2 non-retrieval domains, got {non_claim}"
    assert "tabular" in non_claim
    assert "structured" in non_claim


def test_non_retrieval_datasets_have_committed_loaders_and_feature_schema() -> None:
    for spec in datasets.DATASET_REGISTRY:
        if spec.domain == "claim_verification":
            continue
        assert spec.feature_schema, f"{spec.key} missing feature_schema"
        assert spec.file_path.exists(), f"{spec.key} missing slice file {spec.file_path}"
        snippet = datasets.loader_snippet(spec)
        assert "features" in snippet  # feature-vector loader, not text


def test_dataset_spec_domain_defaults_to_claim_verification() -> None:
    by_key = {s.key: s for s in datasets.DATASET_REGISTRY}
    assert by_key["scifact_claim_verification"].domain == "claim_verification"
    assert by_key["breast_cancer_tabular"].domain == "tabular"
    assert by_key["digits_structured"].domain == "structured"


# --------------------------------------------------------------------------- #
# Step 3: capability_note split (domain-agnostic + per-domain)
# --------------------------------------------------------------------------- #


def test_registry_note_default_is_claim_verification_only() -> None:
    """Backward compat: registry_note() (no arg) shows the 3 claim datasets and
    does NOT surface tabular/structured (those appear only when their domain is asked for)."""
    note = datasets.registry_note()
    assert "scifact_claim_verification" in note
    assert "citation_faithfulness" in note
    assert "统一任务" in note
    assert "breast_cancer_tabular" not in note
    assert "digits_structured" not in note


def test_registry_note_scoped_to_a_domain() -> None:
    note = datasets.registry_note("tabular")
    assert "本次实验 domain = `tabular`" in note
    assert "breast_cancer_tabular" in note
    assert "digits_structured" not in note
    assert "scifact_claim_verification" not in note  # other domains excluded


def test_capability_note_default_preserves_claim_path() -> None:
    note = capability_note()
    assert "SentenceTransformer('all-MiniLM-L6-v2')" in note
    assert "citation_faithfulness" in note
    assert "BM25" in note


def test_capability_note_tabular_does_not_force_sentence_transformers() -> None:
    note = capability_note("tabular")
    assert "breast_cancer_tabular" in note
    assert "sklearn" in note
    # The per-domain method note explicitly forbids dragging ST cosine into tabular.
    method = domain_method_note("tabular")
    assert "禁止用 SentenceTransformer" in method or "禁止" in method


def test_domain_agnostic_note_does_not_pin_a_specific_method() -> None:
    agnostic = domain_agnostic_note()
    assert "方法-假设一致性" in agnostic
    # The agnostic layer states the principle generically; the concrete method is per-domain.
    assert "SentenceTransformer('all-MiniLM-L6-v2')" not in agnostic


# --------------------------------------------------------------------------- #
# Step 4: idea->domain routing + gates are domain-agnostic
# --------------------------------------------------------------------------- #


def test_domain_from_extracts_from_hypothesis_or_plan() -> None:
    assert _domain_from({"domain": "tabular"}) == "tabular"
    assert _domain_from({"domain": "claim_verification"}) == "claim_verification"
    assert _domain_from({}, {"domain": "structured"}) == "structured"
    assert _domain_from({"nope": 1}) is None


def test_domain_preamble_only_for_non_claim_domains() -> None:
    assert _domain_preamble(None) == ""
    assert _domain_preamble("claim_verification") == ""
    assert "DOMAIN ROUTING" in _domain_preamble("tabular")


def test_role_of_stronger_baseline_guard_holds_cross_domain() -> None:
    assert _role_of("stronger_baseline_rf", {"stronger_baseline_rf": "stronger_baseline"}) == "stronger_baseline"


def test_evidence_gates_are_domain_agnostic_on_tabular_metrics() -> None:
    """The verdict / kill-criteria engine keys off metric NAMES in the metrics dict,
    never off a domain label — so a tabular-shaped run is gated identically."""
    metrics = {
        "execution_status": "success",
        "baseline_comparison": {
            "metric_name": "macro_f1",
            "overall_beats_baseline": True,
            "datasets": [
                {"dataset": "breast_cancer_tabular", "beats_baseline": True,
                 "baseline_metric": 0.90, "proposed_metric": 0.93, "delta": 0.03},
            ],
        },
        "statistics": {"any_significant": True, "seed_count": 128, "significance_tests": []},
        "results": [
            {"system_name": "baseline", "metric_name": "macro_f1", "metric_value": 0.90,
             "dataset_name": "breast_cancer_tabular", "seed": 0},
            {"system_name": "proposed", "metric_name": "macro_f1", "metric_value": 0.93,
             "dataset_name": "breast_cancer_tabular", "seed": 0},
        ],
    }
    # No crash, returns a known verdict string — domain label never consulted.
    v = evidence.verdict(metrics, None)
    assert isinstance(v, str) and v

    # A threshold kill criterion on macro_f1 evaluates regardless of domain.
    kill = evidence.evaluate_kill_criteria(
        {"kill_criteria": ["macro_f1 < 0.55"], "domain": "tabular"}, metrics,
    )
    assert kill and kill[0]["needs_manual"] is False
    assert kill[0]["tripped"] is False  # proposed macro_f1 ~0.93 is not < 0.55
