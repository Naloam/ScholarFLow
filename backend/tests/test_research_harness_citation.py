"""Session 7 V2.1 layer: citation verification + coverage-lint quality loop.

Deterministic, offline, network-free. Split so the *pure-logic* cases
(titles_match / extract / verify / coverage_lint / offline-no-HTTP) build their
own synthetic inputs and do NOT read ``backend/data/`` — that subset is safe to
run in CI. The fixture-backed integration case (auditor + pipeline against the
real ``v0_citrag_05`` workspace) stays a local-dev test (see Step 4 decision).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from config.settings import BACKEND_ROOT
from services.research_harness import citation, evidence, writer, auditor, pipeline

FIXTURE = BACKEND_ROOT / "data" / "research_workspace" / "v0_citrag_05"


# --------------------------------------------------------------------------- #
# titles_match — port of citation_verifier._titles_match
# --------------------------------------------------------------------------- #


def test_titles_match_exact_contains_and_prefix() -> None:
    assert citation.titles_match("Attention Is All You Need", "Attention Is All You Need") is True
    # containment (one title truncated/subtitle-trimmed inside the other)
    assert citation.titles_match("Retrieval-Augmented Generation", "Retrieval-Augmented Generation for Knowledge-Intensive NLP") is True
    # long shared prefix
    long_a = "A Very Long Paper Title About Citation Faithfulness and Abstention Calibration"
    long_b = "A Very Long Paper Title About Citation Faithfulness and Abstention Calibration (Extended)"
    assert citation.titles_match(long_a, long_b) is True


def test_titles_match_rejects_unrelated() -> None:
    assert citation.titles_match("Totally Unrelated Paper XYZ", "Attention Is All You Need") is False
    assert citation.titles_match("", "Something") is False
    assert citation.titles_match("ab", "ab") is True  # exact short still matches


# --------------------------------------------------------------------------- #
# extract_citations + verify_citations (offline, synthetic papers)
# --------------------------------------------------------------------------- #


_PAPERS = [
    {"title": "SURE-RAG: Sufficiency and Uncertainty-Aware Evidence Verification for RAG"},
    {"title": "Model Internals-based Answer Attribution for Trustworthy Retrieval-Augmented Generation"},
]


def _draft_with_citations(real: str, fake: str) -> str:
    return (
        "# Draft\n\n"
        f"We extend prior work [1] and build on **\"{real}\"**.\n\n"
        "## References\n"
        f"[1] A. Author. *{real}*. Venue, 2023.\n"
        f"[2] B. Fabricated. {fake}. 2024.\n"
    )


def test_extract_citations_finds_reference_and_inline_titles() -> None:
    draft = _draft_with_citations(_PAPERS[0]["title"], "A Hallucinated Paper About Nothing Real At All")
    cits = citation.extract_citations(draft)
    titles = {c["raw_title"] for c in cits}
    assert _PAPERS[0]["title"] in titles  # from refs + inline (deduped to one)
    assert any("Hallucinated" in t for t in titles)


def test_verify_citations_offline_marks_unknown_as_unverified() -> None:
    draft = _draft_with_citations(_PAPERS[0]["title"], "A Hallucinated Paper About Nothing Real At All")
    results = citation.verify_citations(draft, _PAPERS, live=False)
    by_title = {r["raw_title"]: r for r in results}
    real = by_title[_PAPERS[0]["title"]]
    assert real["verdict"] == "verified"
    assert real["source"] == "literature"
    fake = next(r for r in results if "Hallucinated" in r["raw_title"])
    assert fake["verdict"] == "unverified"
    assert fake["source"] == "none"
    assert 'not found in retrieved literature' in fake["reason"]


def test_verify_citations_empty_when_no_citations() -> None:
    assert citation.verify_citations("# Draft\n\nNo citations here at all.", _PAPERS, live=False) == []


# --------------------------------------------------------------------------- #
# Offline purity: verify_citations never imports/touches httpx
# --------------------------------------------------------------------------- #


def test_offline_path_does_not_import_httpx(monkeypatch) -> None:
    """The default (offline) path must stay network-free — no httpx import, no
    DBLP/CrossRef call. CI relies on this."""
    monkeypatch.setenv("SCHOLARFLOW_OFFLINE_LLM", "1")
    # Save & restore httpx so this purity check does not leak into later tests
    # (starlette's TestClient accesses httpx._client — a popped httpx breaks it).
    original_httpx = sys.modules.get("httpx")
    sys.modules.pop("httpx", None)
    try:
        draft = _draft_with_citations(_PAPERS[0]["title"], "A Hallucinated Paper About Nothing Real At All")
        citation.verify_citations(draft, _PAPERS)  # live=None → auto → offline
        assert "httpx" not in sys.modules, "offline citation path imported httpx (network side-effect)"
    finally:
        if original_httpx is not None:
            sys.modules["httpx"] = original_httpx
        else:
            sys.modules.pop("httpx", None)


def test_live_path_only_runs_when_not_offline(monkeypatch) -> None:
    """When live IS requested, an unmatched citation gets a second chance via the
    external chain — but a network error must never break the audit (honest fallback)."""
    monkeypatch.setenv("SCHOLARFLOW_OFFLINE_LLM", "0")

    def _boom(titles):  # noqa: ANN001
        raise RuntimeError("network down")

    monkeypatch.setattr(citation, "verify_citations_live", _boom)
    draft = _draft_with_citations(_PAPERS[0]["title"], "A Hallucinated Paper About Nothing Real At All")
    # Must not raise — the audit falls back to the offline 'unverified' verdict.
    results = citation.verify_citations(draft, _PAPERS, live=True)
    fake = next(r for r in results if "Hallucinated" in r["raw_title"])
    assert fake["verdict"] == "unverified"


# --------------------------------------------------------------------------- #
# coverage_lint (deterministic numeric-coverage check)
# --------------------------------------------------------------------------- #


def _lint_metrics() -> dict:
    # proposed=0.966501, baseline=0.966501-ish, p=0.003
    return {
        "execution_status": "success",
        "baseline_comparison": {
            "overall_beats_baseline": True,
            "datasets": [
                {"dataset": "d1", "beats_baseline": True,
                 "baseline_metric": 0.9, "proposed_metric": 0.966501, "delta": 0.066501},
            ],
        },
        "statistics": {"seed_count": 5, "significance_tests": [
            {"significant": True, "detail": "dataset=d1: ...", "adjusted_p_value": 0.003},
        ]},
    }


def test_coverage_lint_flags_fabricated_numbers() -> None:
    m = _lint_metrics()
    flags = evidence.coverage_lint("Our method reached 0.999 accuracy (p=0.0001).", m)
    tokens = {f["token"] for f in flags}
    assert "0.999" in tokens
    assert any("0.0001" in t for t in tokens)


def test_coverage_lint_passes_honest_rounding_and_real_values() -> None:
    m = _lint_metrics()
    # 0.967 is honest rounding of 0.966501; 0.003 and 0.9 are exact.
    honest = "improved to 0.967 (adjusted p=0.003) from baseline 0.9."
    assert evidence.coverage_lint(honest, m) == []
    # 1.000 vs a pack value of 1.0 is just extra precision on the same value.
    assert evidence.coverage_lint("perfect macro_f1 of 1.0", m) == []


def test_coverage_lint_empty_when_no_numbers() -> None:
    assert evidence.coverage_lint("A draft with no decimal numbers.", _lint_metrics()) == []


def test_coverage_lint_ignores_markdown_heading_section_numbers() -> None:
    """Regression: the Session 7 live GLM run numbered its headings (``### 3.1 …``)
    and coverage_lint flagged ``3.1``/``6.2`` as unsupported metrics, so the bounded
    revise stripped the numbering. Section refs are structural, not experimental."""
    m = _lint_metrics()
    draft = (
        "## 5. Results\n\n"
        "### 3.1 Method Details\n"
        "### 6.2 Effect Size and Power\n"
        "Our method improved to 0.967 (p=0.003).\n"
    )
    flags = [f["token"] for f in evidence.coverage_lint(draft, m)]
    assert "3.1" not in flags
    assert "6.2" not in flags
    assert flags == []  # 0.967 rounds from the pack's 0.966501; p=0.003 is exact


# --------------------------------------------------------------------------- #
# Auditor integration: citation gate folds into the ledger + affects gate
# --------------------------------------------------------------------------- #


def test_auditor_adds_citation_claims_and_fails_gate_on_unmatched(monkeypatch) -> None:
    monkeypatch.setenv("SCHOLARFLOW_OFFLINE_LLM", "1")
    metrics = {
        "execution_status": "success",
        "baseline_comparison": {"overall_beats_baseline": True, "datasets": [
            {"dataset": "d1", "beats_baseline": True, "baseline_metric": 0.5, "proposed_metric": 0.8},
        ]},
        "statistics": {"seed_count": 5, "significance_tests": [
            {"significant": True, "detail": "dataset=d1: ...", "adjusted_p_value": 0.01},
        ]},
    }
    draft = _draft_with_citations(_PAPERS[0]["title"], "A Hallucinated Paper About Nothing Real At All")
    result = auditor.audit_draft(draft, metrics, _PAPERS, live=False)

    citation_claims = [c for c in result["claims"] if c.get("category") == "citation"]
    assert len(citation_claims) == 2
    unverified_cit = [c for c in citation_claims if c["verdict"] == "unverified"]
    assert len(unverified_cit) == 1
    assert "not found in retrieved literature" in unverified_cit[0]["reason"]
    assert result["citation_unverified_count"] == 1
    # An unmatched citation fails the overall gate (citation gate never loosened).
    assert result["gate"] is False

    annotated = auditor.annotate_draft(draft, result)
    assert "[UNVERIFIED: citation" in annotated


def test_auditor_passes_when_all_citations_resolve() -> None:
    metrics = {
        "execution_status": "success",
        "baseline_comparison": {"overall_beats_baseline": True, "datasets": [
            {"dataset": "d1", "beats_baseline": True, "baseline_metric": 0.5, "proposed_metric": 0.8},
        ]},
        "statistics": {"seed_count": 5, "significance_tests": [
            {"significant": True, "detail": "dataset=d1: ...", "adjusted_p_value": 0.01},
        ]},
    }
    draft = (
        "# Draft\n\nOur method improves over the baseline.\n\n"
        "## References\n[1] A. Author. *" + _PAPERS[0]["title"] + "*. Venue, 2023.\n"
    )
    result = auditor.audit_draft(draft, metrics, _PAPERS, live=False)
    assert all(c["verdict"] == "verified" for c in result["claims"] if c.get("category") == "citation")
    assert result["citation_unverified_count"] == 0


# --------------------------------------------------------------------------- #
# Writer quality loop: bounded (≤1) revision removes a fabricated number
# --------------------------------------------------------------------------- #


def test_revise_on_lint_is_bounded_and_fixes_flag(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(writer, "WORKSPACE_ROOT", tmp_path)
    paper = tmp_path / "p" / "paper"
    paper.mkdir(parents=True)
    bad = "# Draft\n\nOur method reached 0.999 on a hidden set.\n"
    (paper / "draft.md").write_text(bad, encoding="utf-8")
    (paper / "draft.raw.md").write_text(bad, encoding="utf-8")

    calls = {"n": 0}

    def fake_chat(msgs, model=None):  # noqa: ANN001
        calls["n"] += 1
        return {"choices": [{"message": {"content": "# Draft\n\nOur method reached 0.967 on d1."}}]}

    monkeypatch.setattr(writer, "chat", fake_chat)
    log = writer.run_quality_loop("p", _lint_metrics())

    assert calls["n"] == 1  # bounded — exactly one revise call
    assert log["revised"] is True
    assert log["flags_before"] == ["0.999"]
    assert log["flags_after"] == []  # the revision removed the unsupported number
    final = (paper / "draft.md").read_text(encoding="utf-8")
    assert "0.999" not in final
    # Pre-revision draft preserved for traceability; raw LLM output untouched.
    assert (paper / "draft.revise_pre.md").read_text(encoding="utf-8") == bad


def test_revise_keeps_original_when_no_flags(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(writer, "WORKSPACE_ROOT", tmp_path)
    paper = tmp_path / "p" / "paper"
    paper.mkdir(parents=True)
    honest = "# Draft\n\nOur method reached 0.967 (p=0.003).\n"
    (paper / "draft.md").write_text(honest, encoding="utf-8")
    (paper / "draft.raw.md").write_text(honest, encoding="utf-8")
    calls = {"n": 0}

    def boom(msgs, model=None):  # noqa: ANN001 — must never be called
        calls["n"] += 1
        raise AssertionError("revise must not be called when there are no flags")

    monkeypatch.setattr(writer, "chat", boom)
    log = writer.run_quality_loop("p", _lint_metrics())
    assert calls["n"] == 0  # no flags → no revise call
    assert log["revised"] is False
    assert (paper / "draft.md").read_text(encoding="utf-8") == honest


# --------------------------------------------------------------------------- #
# Fixture-backed integration (local only — reads backend/data/)
# --------------------------------------------------------------------------- #

FIXTURE_REQUIRED = pytest.mark.skipif(not FIXTURE.exists(), reason="v0_citrag_05 fixture not present (local-dev only)")


@FIXTURE_REQUIRED
def test_pipeline_audit_flags_injected_unmatched_citation(monkeypatch, tmp_path) -> None:
    """Integration E2E (backend): copy the real fixture, inject an unmatched citation
    into the draft, run the audit step, and assert the citation gate fires in the
    ledger + the inline marker lands in draft.md."""
    shutil.copytree(FIXTURE, tmp_path / "v0_citrag_05")
    for mod in (pipeline, writer, auditor):
        monkeypatch.setattr(mod, "WORKSPACE_ROOT", tmp_path)

    # Inject an unmatched citation into the pristine raw draft, then re-materialize draft.md.
    raw = (tmp_path / "v0_citrag_05" / "paper" / "draft.raw.md").read_text(encoding="utf-8")
    injected = raw + "\n\n## References\n[1] Z. Fabricated. A Hallucinated Paper About Nothing Real. 2024.\n"
    (tmp_path / "v0_citrag_05" / "paper" / "draft.md").write_text(injected, encoding="utf-8")

    summary = pipeline.run_pipeline("v0_citrag_05", "idea", steps=["audit"])
    assert summary["status"] == "done"

    ledger = json.loads((tmp_path / "v0_citrag_05" / "ledger" / "claim_audit.json").read_text(encoding="utf-8"))
    citation_unverified = [c for c in ledger["claims"] if c.get("category") == "citation" and c["verdict"] == "unverified"]
    assert len(citation_unverified) >= 1
    assert ledger["gate"] is False  # unmatched citation fails the gate
    draft = (tmp_path / "v0_citrag_05" / "paper" / "draft.md").read_text(encoding="utf-8")
    assert "[UNVERIFIED: citation" in draft
