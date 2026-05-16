from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from schemas.autoresearch import (
    AutoResearchBundleAssetRole,
    AutoResearchEvidenceIndexCategory,
    AutoResearchEvidenceIndexItemRead,
    AutoResearchPublicationEvidenceIndexRead,
    AutoResearchReviewLoopRead,
    AutoResearchRunRead,
    AutoResearchRunReviewRead,
)
from services.autoresearch.repository import (
    ARTIFACT_FILENAME,
    ARTIFACT_INTEGRITY_AUDIT_FILENAME,
    BENCHMARK_FILENAME,
    CLAIM_EVIDENCE_MATRIX_FILENAME,
    CONTRIBUTION_ASSESSMENT_FILENAME,
    LITERATURE_GRAPH_FILENAME,
    NOVELTY_VALIDATION_FILENAME,
    PAPER_BIB_FILENAME,
    PAPER_BUILD_SCRIPT_FILENAME,
    PAPER_COMPILE_REPORT_FILENAME,
    PAPER_FILENAME,
    PAPER_LATEX_FILENAME,
    PAPER_SOURCES_DIRNAME,
    PAPER_SOURCES_MANIFEST_FILENAME,
    PLAN_FILENAME,
    PORTFOLIO_FILENAME,
    PROGRAM_FILENAME,
    RUN_FILENAME,
    SPEC_FILENAME,
    run_dir,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    return Path(value)


def _item(
    *,
    evidence_id: str,
    label: str,
    category: AutoResearchEvidenceIndexCategory,
    path: str | Path | None,
    role: AutoResearchBundleAssetRole | None = None,
    required_for_final_publish: bool = False,
    supports: list[str] | None = None,
) -> AutoResearchEvidenceIndexItemRead:
    candidate = _path(path)
    exists = bool(candidate is not None and candidate.exists())
    size_bytes = candidate.stat().st_size if candidate is not None and exists and candidate.is_file() else None
    return AutoResearchEvidenceIndexItemRead(
        evidence_id=evidence_id,
        label=label,
        category=category,
        role=role,
        path=str(candidate) if candidate is not None else None,
        exists=exists,
        size_bytes=size_bytes,
        sha256=_file_sha256(candidate) if candidate is not None else None,
        required_for_final_publish=required_for_final_publish,
        supports=supports or [],
        status="present" if exists else "missing",
    )


def build_publication_evidence_index(
    run: AutoResearchRunRead,
    *,
    review: AutoResearchRunReviewRead,
    review_loop: AutoResearchReviewLoopRead | None,
    review_path: str | Path | None,
    review_loop_path: str | Path | None,
) -> AutoResearchPublicationEvidenceIndexRead:
    base = run_dir(run.project_id, run.id)
    paper_sources_dir = Path(run.paper_sources_dir or (base / PAPER_SOURCES_DIRNAME))
    readiness = review.publication_readiness
    publication_tier = readiness.tier if readiness is not None else "exploratory"
    publication_readiness_score = readiness.score if readiness is not None else 0
    items = [
        _item(
            evidence_id="run_snapshot",
            label="Run snapshot",
            category="run",
            role="run_json",
            path=base / RUN_FILENAME,
            required_for_final_publish=True,
            supports=["run identity", "audit trail"],
        ),
        _item(
            evidence_id="program_snapshot",
            label="Program snapshot",
            category="run",
            role="program_json",
            path=base / PROGRAM_FILENAME,
            required_for_final_publish=True,
            supports=["research program", "candidate generation context"],
        ),
        _item(
            evidence_id="portfolio_snapshot",
            label="Portfolio snapshot",
            category="run",
            role="portfolio_json",
            path=base / PORTFOLIO_FILENAME,
            required_for_final_publish=True,
            supports=["candidate selection", "portfolio decision"],
        ),
        _item(
            evidence_id="benchmark_snapshot",
            label="Benchmark snapshot",
            category="benchmark",
            role="benchmark_json",
            path=base / BENCHMARK_FILENAME,
            required_for_final_publish=True,
            supports=["benchmark definition", "dataset split"],
        ),
        _item(
            evidence_id="benchmark_card",
            label="Benchmark card",
            category="benchmark",
            role="run_benchmark_card_json",
            path=review.benchmark_card_path,
            required_for_final_publish=True,
            supports=["benchmark provenance", "publication-grade dataset checks"],
        ),
        _item(
            evidence_id="plan",
            label="Selected research plan",
            category="run",
            role="run_plan_json",
            path=base / PLAN_FILENAME,
            required_for_final_publish=True,
            supports=["hypothesis", "evaluation plan"],
        ),
        _item(
            evidence_id="spec",
            label="Selected experiment spec",
            category="run",
            role="run_spec_json",
            path=base / SPEC_FILENAME,
            required_for_final_publish=True,
            supports=["task family", "metrics", "acceptance rules"],
        ),
        _item(
            evidence_id="artifact",
            label="Selected experiment artifact",
            category="run",
            role="run_artifact_json",
            path=base / ARTIFACT_FILENAME,
            required_for_final_publish=True,
            supports=["results", "statistics", "sweeps"],
        ),
        _item(
            evidence_id="generated_code",
            label="Generated experiment code",
            category="code",
            role="run_generated_code",
            path=run.generated_code_path,
            required_for_final_publish=True,
            supports=["reproducibility", "implementation"],
        ),
        _item(
            evidence_id="claim_evidence_matrix",
            label="Claim-evidence matrix",
            category="claims",
            role="run_claim_evidence_matrix_json",
            path=run.claim_evidence_matrix_path or (base / CLAIM_EVIDENCE_MATRIX_FILENAME),
            required_for_final_publish=True,
            supports=["claim support", "unsupported-claim review"],
        ),
        _item(
            evidence_id="research_protocol",
            label="Research protocol",
            category="protocol",
            role="run_research_protocol_json",
            path=review.research_protocol_path,
            required_for_final_publish=True,
            supports=["predefined methodology", "acceptance criteria"],
        ),
        _item(
            evidence_id="methodology_audit",
            label="Methodology audit",
            category="methodology",
            role="run_methodology_audit_json",
            path=review.methodology_audit_path,
            required_for_final_publish=True,
            supports=["protocol compliance", "statistical sufficiency"],
        ),
        _item(
            evidence_id="publication_readiness",
            label="Publication readiness report",
            category="readiness",
            role="run_publication_readiness_json",
            path=review.publication_readiness_path,
            required_for_final_publish=True,
            supports=["publish tier", "final gate decisions"],
        ),
        _item(
            evidence_id="contribution_assessment",
            label="Contribution assessment",
            category="contribution",
            role="run_contribution_assessment_json",
            path=review.contribution_assessment_path or (base / CONTRIBUTION_ASSESSMENT_FILENAME),
            required_for_final_publish=True,
            supports=["contribution claims", "claim strength", "novelty risks", "publishability"],
        ),
        _item(
            evidence_id="literature_graph",
            label="Literature graph",
            category="novelty",
            role="run_literature_graph_json",
            path=review.literature_graph_path or (base / LITERATURE_GRAPH_FILENAME),
            required_for_final_publish=True,
            supports=["paper nodes", "method nodes", "dataset nodes", "claim nodes"],
        ),
        _item(
            evidence_id="novelty_validation",
            label="Novelty validation",
            category="novelty",
            role="run_novelty_validation_json",
            path=review.novelty_validation_path or (base / NOVELTY_VALIDATION_FILENAME),
            required_for_final_publish=True,
            supports=["duplicate risk", "incremental risk", "gap validity"],
        ),
        _item(
            evidence_id="revision_dossier",
            label="Revision dossier",
            category="revision",
            role="run_revision_dossier_json",
            path=review.revision_dossier_path,
            required_for_final_publish=True,
            supports=["review response", "required action closure"],
        ),
        _item(
            evidence_id="artifact_integrity_audit",
            label="Artifact integrity audit",
            category="lineage",
            role="run_artifact_integrity_audit_json",
            path=review.artifact_integrity_audit_path or (base / ARTIFACT_INTEGRITY_AUDIT_FILENAME),
            required_for_final_publish=True,
            supports=["registry integrity", "lineage completeness", "bundle consistency"],
        ),
        _item(
            evidence_id="paper_markdown",
            label="Paper markdown",
            category="paper",
            role="run_paper_markdown",
            path=run.paper_path or (base / PAPER_FILENAME),
            required_for_final_publish=True,
            supports=["paper text", "citation grounding"],
        ),
        _item(
            evidence_id="paper_compile_report",
            label="Paper compile report",
            category="paper",
            role="run_paper_compile_report_json",
            path=run.paper_compile_report_path or (base / PAPER_COMPILE_REPORT_FILENAME),
            required_for_final_publish=True,
            supports=["compile readiness", "paper source package"],
        ),
        _item(
            evidence_id="paper_build_script",
            label="Paper build script",
            category="paper",
            role="run_paper_build_script",
            path=paper_sources_dir / PAPER_BUILD_SCRIPT_FILENAME,
            required_for_final_publish=True,
            supports=["paper reproducibility", "source package"],
        ),
        _item(
            evidence_id="paper_latex_source",
            label="Paper LaTeX source",
            category="paper",
            role="run_paper_latex_source",
            path=run.paper_latex_path or (paper_sources_dir / PAPER_LATEX_FILENAME),
            required_for_final_publish=True,
            supports=["camera-ready source", "paper reproducibility"],
        ),
        _item(
            evidence_id="paper_bibliography",
            label="Paper bibliography",
            category="paper",
            role="run_paper_bibliography_bib",
            path=run.paper_bibliography_path or (paper_sources_dir / PAPER_BIB_FILENAME),
            required_for_final_publish=True,
            supports=["citation reproducibility", "bibliography"],
        ),
        _item(
            evidence_id="paper_sources_manifest",
            label="Paper sources manifest",
            category="paper",
            role="run_paper_sources_manifest_json",
            path=run.paper_sources_manifest_path or (paper_sources_dir / PAPER_SOURCES_MANIFEST_FILENAME),
            required_for_final_publish=True,
            supports=["source package manifest", "paper artifacts"],
        ),
        _item(
            evidence_id="review_report",
            label="Review report",
            category="review",
            path=review_path,
            required_for_final_publish=True,
            supports=["review findings", "publish status"],
        ),
        _item(
            evidence_id="review_loop",
            label="Review loop state",
            category="review",
            path=review_loop_path,
            required_for_final_publish=True,
            supports=["round history", "revision tracking"],
        ),
    ]
    required_items = [item for item in items if item.required_for_final_publish]
    missing_required = [item for item in required_items if not item.exists]
    blockers = [
        f"Missing required publication evidence: {item.evidence_id} ({item.label})."
        for item in missing_required
    ]
    warnings: list[str] = []
    if review.overall_status != "ready":
        warnings.append(f"Review status is {review.overall_status}; evidence index is not a semantic approval.")
    if readiness is not None and not readiness.final_publish_ready:
        warnings.extend(readiness.blockers[:5])
    payload = {
        "index_id": "publication_evidence_index_v1",
        "project_id": run.project_id,
        "run_id": run.id,
        "selected_candidate_id": review.selected_candidate_id,
        "review_round": review_loop.current_round if review_loop is not None else 0,
        "review_fingerprint": review_loop.latest_review_fingerprint if review_loop is not None else None,
        "publication_tier": publication_tier,
        "publication_readiness_score": publication_readiness_score,
        "evidence_items": [item.model_dump(mode="json") for item in items],
        "missing_required_evidence_ids": [item.evidence_id for item in missing_required],
        "blockers": blockers,
        "warnings": warnings,
        "complete": not blockers,
    }
    return AutoResearchPublicationEvidenceIndexRead(
        generated_at=_utcnow(),
        evidence_item_count=len(items),
        required_evidence_count=len(required_items),
        present_required_evidence_count=len(required_items) - len(missing_required),
        missing_required_evidence_count=len(missing_required),
        evidence_index_fingerprint=_fingerprint(payload),
        **payload,
    )
