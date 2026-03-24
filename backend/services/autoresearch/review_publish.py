from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from schemas.autoresearch import (
    AutoResearchBundleAssetRead,
    AutoResearchBundleIndexRead,
    AutoResearchBundleRead,
    AutoResearchCitationCoverageRead,
    AutoResearchNoveltyAssessmentRead,
    AutoResearchPublishExportRead,
    AutoResearchPublishPackageRead,
    AutoResearchRelatedWorkMatchRead,
    AutoResearchReviewEvidenceRead,
    AutoResearchReviewFindingRead,
    AutoResearchReviewLoopActionRead,
    AutoResearchReviewLoopIssueRead,
    AutoResearchReviewLoopRead,
    AutoResearchReviewLoopRoundRead,
    AutoResearchReviewScoresRead,
    AutoResearchRevisionActionRead,
    AutoResearchRunRead,
    AutoResearchRunReviewRead,
    HypothesisCandidate,
)
from services.autoresearch.repository import (
    load_run,
    load_run_bundle_index,
    load_run_registry,
    run_dir,
    save_run,
)
from services.autoresearch.writer import PaperWriter


REVIEW_FILENAME = "review.json"
REVIEW_LOOP_FILENAME = "review_loop.json"
PUBLISH_PACKAGE_FILENAME = "publish_package.json"
PUBLISH_ARCHIVE_FILENAME = "publish_bundle.zip"
PUBLISH_ARCHIVE_MANIFEST_FILENAME = "archive_manifest.json"
_FINAL_PUBLISH_REQUIRED_ROLES = {
    "run_json",
    "program_json",
    "portfolio_json",
    "benchmark_json",
    "run_plan_json",
    "run_spec_json",
    "run_artifact_json",
    "run_generated_code",
    "run_paper_markdown",
    "workspace",
    "candidate_json",
    "plan_json",
    "spec_json",
    "attempts_json",
    "artifact_json",
    "manifest_json",
    "generated_code",
}
_CITATION_PATTERN = re.compile(r"\[(\d+(?:,\s*\d+)*)\]")
_REFERENCE_SECTION_MARKERS = ("references", "bibliography")
_ALWAYS_CITED_SECTION_MARKERS = ("related work", "prior work", "background")
_CONTEXTUAL_SECTION_MARKERS = ("introduction", "discussion", "conclusion", "limitations")
_CONTEXTUAL_CITATION_CUES = (
    "prior work",
    "related work",
    "background",
    "literature",
    "previous",
    "existing",
    "retrieved work",
    "papers",
    "studies",
    "reported",
)
_NOVELTY_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "into",
    "over",
    "under",
    "through",
    "using",
    "based",
    "current",
    "selected",
    "candidate",
    "research",
    "paper",
    "papers",
    "study",
    "studies",
    "method",
    "methods",
    "system",
    "systems",
    "result",
    "results",
    "experimental",
    "experiment",
    "artifacts",
    "artifact",
    "evidence",
    "generated",
    "reports",
    "report",
    "only",
    "small",
    "minimal",
    "task",
    "tasks",
}
_INFRASTRUCTURE_CLAIM_CUES = (
    "seed",
    "sweep",
    "artifact",
    "artifacts",
    "acceptance",
    "persistence",
    "persisted",
    "repair",
    "runtime contract",
    "execution trace",
    "execution plane",
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _review_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / REVIEW_FILENAME


def _review_loop_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / REVIEW_LOOP_FILENAME


def _publish_manifest_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / PUBLISH_PACKAGE_FILENAME


def _publish_archive_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / PUBLISH_ARCHIVE_FILENAME


def _publish_archive_manifest_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / PUBLISH_ARCHIVE_MANIFEST_FILENAME


def _selected_bundle(bundle_index: AutoResearchBundleIndexRead) -> AutoResearchBundleRead | None:
    return next((item for item in bundle_index.bundles if item.id == "selected_candidate_repro"), None)


def _final_required_assets(bundle: AutoResearchBundleRead | None) -> list[AutoResearchBundleAssetRead]:
    if bundle is None:
        return []
    return [item for item in bundle.assets if item.role in _FINAL_PUBLISH_REQUIRED_ROLES]


def _paper_markdown(run: AutoResearchRunRead) -> str:
    if run.paper_markdown:
        return run.paper_markdown
    if run.paper_path:
        path = Path(run.paper_path)
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return ""


def _markdown_sections(markdown: str) -> list[tuple[str, str]]:
    if not markdown.strip():
        return []
    sections: list[tuple[str, str]] = []
    current_title = "Document"
    current_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("#"):
            content = "\n".join(current_lines).strip()
            if content or sections:
                sections.append((current_title, content))
            current_title = line.lstrip("#").strip() or "Untitled Section"
            current_lines = []
            continue
        current_lines.append(line)
    content = "\n".join(current_lines).strip()
    if content or not sections:
        sections.append((current_title, content))
    return sections


def _is_reference_section(title: str) -> bool:
    lowered = title.lower()
    return any(marker in lowered for marker in _REFERENCE_SECTION_MARKERS)


def _parse_citation_indices(markdown: str) -> list[int]:
    indices: list[int] = []
    for match in _CITATION_PATTERN.findall(markdown):
        for part in match.split(","):
            candidate = part.strip()
            if candidate.isdigit():
                indices.append(int(candidate))
    return indices


def _section_requires_citations(title: str, content: str) -> bool:
    lowered_title = title.lower()
    lowered_content = content.lower()
    if any(marker in lowered_title for marker in _ALWAYS_CITED_SECTION_MARKERS):
        return True
    if not any(marker in lowered_title for marker in _CONTEXTUAL_SECTION_MARKERS):
        return False
    return any(marker in lowered_content for marker in _CONTEXTUAL_CITATION_CUES)


def _sections_without_citations(markdown: str) -> tuple[list[str], bool, bool]:
    sections = _markdown_sections(markdown)
    uncited: list[str] = []
    has_related_work = False
    has_references = False
    for title, content in sections:
        lowered = title.lower()
        if "related work" in lowered or "prior work" in lowered or "background" in lowered:
            has_related_work = True
        if _is_reference_section(title):
            has_references = True
        if not _section_requires_citations(title, content):
            continue
        if len(content.strip()) < 40:
            continue
        if not _CITATION_PATTERN.search(content):
            uncited.append(title)
    if (
        not sections
        and markdown.strip()
        and not _CITATION_PATTERN.search(markdown)
        and any(marker in markdown.lower() for marker in _CONTEXTUAL_CITATION_CUES)
    ):
        uncited.append("Paper body")
    return uncited, has_related_work, has_references


def _clamp_score(value: int) -> int:
    return max(0, min(5, value))


def _normalize_term(token: str) -> str:
    normalized = token.lower()
    for suffix in ("ings", "ing", "ers", "ies", "ions", "ion", "ed", "er", "s"):
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 4:
            normalized = normalized[: -len(suffix)] + ("y" if suffix == "ies" else "")
            break
    return normalized


def _terms(*texts: str | None) -> set[str]:
    tokens: set[str] = set()
    for text in texts:
        for raw in re.findall(r"[a-z][a-z0-9_]+", (text or "").lower()):
            token = _normalize_term(raw)
            if len(token) < 4 or token in _NOVELTY_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _research_claims(run: AutoResearchRunRead, selected_candidate_id: str | None) -> list[str]:
    candidate = next((item for item in run.candidates if item.id == selected_candidate_id), None)
    if candidate is None:
        return []
    claims = []
    for claim in candidate.planned_contributions:
        lowered = claim.lower()
        if any(marker in lowered for marker in _INFRASTRUCTURE_CLAIM_CUES):
            continue
        if _terms(claim):
            claims.append(claim)
    return claims


def _selected_candidate(
    run: AutoResearchRunRead,
    selected_candidate_id: str | None,
) -> HypothesisCandidate | None:
    return next((item for item in run.candidates if item.id == selected_candidate_id), None)


def _build_novelty_assessment(
    *,
    run: AutoResearchRunRead,
    selected_candidate_id: str | None,
) -> AutoResearchNoveltyAssessmentRead:
    candidate = _selected_candidate(run, selected_candidate_id)
    if candidate is None:
        return AutoResearchNoveltyAssessmentRead(
            status="missing_context",
            summary="No selected candidate was available, so novelty and related-work analysis could not be computed.",
        )
    if not run.literature:
        return AutoResearchNoveltyAssessmentRead(
            status="missing_context",
            summary="No persisted literature was available, so novelty and related-work analysis remains weakly grounded.",
        )

    candidate_method_terms = _terms(candidate.title, candidate.hypothesis, candidate.proposed_method)
    candidate_claim_terms = _terms(*candidate.planned_contributions)
    matches: list[AutoResearchRelatedWorkMatchRead] = []
    strong_match_count = 0
    gap_aligned_paper_count = 0

    for item in run.literature:
        literature_terms = _terms(item.title, item.insight, item.method_hint)
        gap_terms = _terms(item.gap_hint)
        shared_terms = sorted(candidate_method_terms & literature_terms)
        gap_alignment_terms = sorted((candidate_method_terms | candidate_claim_terms) & gap_terms)
        overlap_score = len(shared_terms) * 2 + len(gap_alignment_terms)
        if overlap_score <= 0:
            continue
        if len(shared_terms) >= 2 or overlap_score >= 3:
            strong_match_count += 1
        if gap_alignment_terms:
            gap_aligned_paper_count += 1
        rationale = (
            "Shares method vocabulary and aligns with an explicit preserved gap."
            if shared_terms and gap_alignment_terms
            else "Aligns one or more selected-candidate claims with a preserved literature gap."
            if gap_alignment_terms
            else "Shares method vocabulary with the selected candidate."
        )
        matches.append(
            AutoResearchRelatedWorkMatchRead(
                paper_id=item.paper_id,
                title=item.title,
                year=item.year,
                source=item.source,
                overlap_score=overlap_score,
                shared_terms=shared_terms[:6],
                gap_alignment_terms=gap_alignment_terms[:6],
                rationale=rationale,
            )
        )

    matches.sort(
        key=lambda item: (
            -item.overlap_score,
            -len(item.gap_alignment_terms),
            -len(item.shared_terms),
            item.title.lower(),
        )
    )
    research_claims = _research_claims(run, selected_candidate_id)
    covered_claims = 0
    uncovered_claims: list[str] = []
    literature_claim_terms = [
        _terms(item.title, item.insight, item.method_hint, item.gap_hint)
        for item in run.literature
    ]
    for claim in research_claims:
        claim_terms = _terms(claim)
        if any(len(claim_terms & item_terms) >= 2 for item_terms in literature_claim_terms):
            covered_claims += 1
        else:
            uncovered_claims.append(claim)

    if strong_match_count == 0:
        status = "weak"
        summary = (
            f"The selected candidate does not show a strong lexical or gap-aligned match against {len(run.literature)} "
            "persisted literature items."
        )
    elif research_claims and covered_claims == 0:
        status = "weak"
        summary = (
            "Related work was preserved, but none of the selected candidate's research-facing contribution claims were "
            "well covered by the persisted literature state."
        )
    elif gap_aligned_paper_count == 0 or covered_claims < len(research_claims):
        status = "incremental"
        summary = (
            f"The selected candidate is grounded in related work with {strong_match_count} strong matches, but the "
            "novelty posture still looks incremental and should be framed carefully."
        )
    else:
        status = "grounded"
        summary = (
            f"The selected candidate is grounded against {strong_match_count} strong related-work matches and "
            f"{covered_claims}/{len(research_claims) if research_claims else 0} research-facing claims are tied back "
            "to the persisted literature state."
        )

    return AutoResearchNoveltyAssessmentRead(
        status=status,
        summary=summary,
        compared_paper_count=len(run.literature),
        strong_match_count=strong_match_count,
        gap_aligned_paper_count=gap_aligned_paper_count,
        covered_claim_count=covered_claims,
        total_claim_count=len(research_claims),
        uncovered_claims=uncovered_claims,
        top_related_work=matches[:3],
    )


def _review_findings(
    *,
    run: AutoResearchRunRead,
    bundle: AutoResearchBundleRead | None,
    selected_manifest_source: str | None,
    paper_markdown: str,
    novelty_assessment: AutoResearchNoveltyAssessmentRead,
) -> tuple[
    list[AutoResearchReviewFindingRead],
    AutoResearchReviewEvidenceRead,
    AutoResearchCitationCoverageRead,
]:
    findings: list[AutoResearchReviewFindingRead] = []

    def add_finding(
        *,
        severity: str,
        category: str,
        summary: str,
        detail: str,
        supporting_asset_ids: list[str] | None = None,
    ) -> None:
        findings.append(
            AutoResearchReviewFindingRead(
                id=f"finding_{len(findings) + 1}",
                severity=severity,
                category=category,
                summary=summary,
                detail=detail,
                supporting_asset_ids=supporting_asset_ids or [],
            )
        )

    artifact = run.artifact
    citation_marker_count = len(_CITATION_PATTERN.findall(paper_markdown))
    citation_indices = _parse_citation_indices(paper_markdown)
    unique_citation_indices = sorted(set(citation_indices))
    sections_without_citations, has_related_work, has_references = _sections_without_citations(paper_markdown)
    invalid_citation_indices = [
        item for item in unique_citation_indices if item < 1 or item > len(run.literature)
    ]
    cited_literature_count = sum(1 for item in unique_citation_indices if 1 <= item <= len(run.literature))
    required_assets = [item for item in bundle.assets if item.required] if bundle is not None else []
    optional_assets = [item for item in bundle.assets if not item.required] if bundle is not None else []
    missing_required_assets = [item for item in required_assets if not item.ref.exists]
    acceptance_total = len(artifact.acceptance_checks) if artifact is not None else 0
    acceptance_passed = sum(1 for item in artifact.acceptance_checks if item.passed) if artifact is not None else 0
    evidence = AutoResearchReviewEvidenceRead(
        selected_bundle_id=bundle.id if bundle is not None else None,
        literature_count=len(run.literature),
        candidate_count=len(run.candidates),
        executed_candidate_count=sum(1 for item in run.candidates if item.attempts),
        seed_count=len(run.spec.seeds) if run.spec is not None else 0,
        completed_seed_count=len(artifact.per_seed_results) if artifact is not None else 0,
        sweep_count=len(run.spec.sweeps) if run.spec is not None else 0,
        significance_test_count=len(artifact.significance_tests) if artifact is not None else 0,
        negative_result_count=len(artifact.negative_results) if artifact is not None else 0,
        failed_trial_count=len(artifact.failed_trials) if artifact is not None else 0,
        acceptance_passed=acceptance_passed,
        acceptance_total=acceptance_total,
        citation_marker_count=citation_marker_count,
        missing_required_asset_count=len(missing_required_assets),
    )
    citation_coverage = AutoResearchCitationCoverageRead(
        literature_item_count=len(run.literature),
        citation_marker_count=citation_marker_count,
        cited_literature_count=cited_literature_count,
        invalid_citation_indices=invalid_citation_indices,
        sections_without_citations=sections_without_citations,
        has_related_work_section=has_related_work,
        has_references_section=has_references,
    )

    if artifact is None or artifact.status != "done":
        add_finding(
            severity="error",
            category="artifact",
            summary="Selected run artifact is not publication-ready.",
            detail="The run does not currently expose a completed top-level result artifact for review and publish work.",
            supporting_asset_ids=["run_artifact_json"],
        )
    else:
        if acceptance_total == 0:
            add_finding(
                severity="warning",
                category="statistics",
                summary="No acceptance checks were recorded.",
                detail="The selected artifact should preserve explicit acceptance checks before publication review.",
                supporting_asset_ids=["run_artifact_json"],
            )
        elif acceptance_passed < acceptance_total:
            add_finding(
                severity="error",
                category="statistics",
                summary="Some acceptance checks failed on the selected artifact.",
                detail=(
                    f"The artifact passed {acceptance_passed}/{acceptance_total} acceptance checks. "
                    "Resolve failing checks before treating the paper as publish-ready."
                ),
                supporting_asset_ids=["run_artifact_json"],
            )

    if not paper_markdown.strip():
        add_finding(
            severity="error",
            category="artifact",
            summary="No grounded paper markdown was found for the run.",
            detail="Phase 5 review requires the persisted paper output produced from the selected artifact.",
            supporting_asset_ids=["run_paper_markdown"],
        )

    if missing_required_assets:
        add_finding(
            severity="error",
            category="publish",
            summary="Required publish assets are missing from the selected registry bundle.",
            detail=(
                "The selected publish bundle is missing required assets: "
                + ", ".join(item.role for item in missing_required_assets)
                + "."
            ),
            supporting_asset_ids=[item.asset_id for item in missing_required_assets],
        )

    if selected_manifest_source != "file":
        add_finding(
            severity="warning",
            category="provenance",
            summary="Selected candidate manifest is using generated fallback metadata.",
            detail=(
                "The selected candidate can still be inspected, but a missing on-disk manifest weakens the audit trail "
                "for publish and review workflows."
            ),
            supporting_asset_ids=["manifest_json"],
        )

    if citation_marker_count == 0:
        add_finding(
            severity="warning",
            category="citation",
            summary="Paper text does not include citation markers.",
            detail=(
                "The persisted paper should cite literature support and related work explicitly before publication review."
            ),
            supporting_asset_ids=["run_paper_markdown"],
        )
    elif invalid_citation_indices:
        add_finding(
            severity="error",
            category="provenance",
            summary="Paper citations do not resolve to persisted run literature.",
            detail=(
                "Citation indices outside the persisted literature range were found: "
                + ", ".join(str(item) for item in invalid_citation_indices)
                + f". The run retains {len(run.literature)} literature items."
            ),
            supporting_asset_ids=["run_json", "run_paper_markdown"],
        )
    elif sections_without_citations:
        add_finding(
            severity="warning",
            category="citation",
            summary="Some contextual sections lack citation support.",
            detail="Sections without citation markers: " + ", ".join(sections_without_citations) + ".",
            supporting_asset_ids=["run_paper_markdown"],
        )
    if len(run.literature) > 0 and citation_marker_count > 0 and not has_references:
        add_finding(
            severity="warning",
            category="citation",
            summary="Paper citations are missing a references section.",
            detail="Persisted literature is cited in the paper body, but no references or bibliography section was found.",
            supporting_asset_ids=["run_paper_markdown"],
        )

    if len(run.literature) == 0:
        add_finding(
            severity="warning",
            category="context",
            summary="No literature insights were persisted with the run.",
            detail="Related-work and novelty review will be weaker until the run retains literature context.",
        )
    elif not has_related_work and citation_marker_count > 0:
        add_finding(
            severity="warning",
            category="context",
            summary="Paper lacks an explicit related-work section.",
            detail=(
                "The run preserved literature context, but the paper structure should expose a dedicated related-work or "
                "background section before publish review."
            ),
            supporting_asset_ids=["run_paper_markdown"],
        )
    if novelty_assessment.status == "weak":
        add_finding(
            severity="warning",
            category="context",
            summary="Selected candidate novelty framing is weakly grounded in persisted literature.",
            detail=novelty_assessment.summary,
            supporting_asset_ids=["run_json", "run_paper_markdown"],
        )
    elif novelty_assessment.status == "incremental":
        add_finding(
            severity="info",
            category="context",
            summary="Selected candidate appears incremental relative to preserved related work.",
            detail=novelty_assessment.summary,
            supporting_asset_ids=["run_json", "run_paper_markdown"],
        )

    if artifact is not None and artifact.status == "done":
        if not artifact.significance_tests:
            add_finding(
                severity="warning",
                category="statistics",
                summary="The paper package does not preserve significance comparisons.",
                detail=(
                    "Selected artifacts should retain significance tests so later reviewers can distinguish stable gains "
                    "from one-off metric wins."
                ),
                supporting_asset_ids=["run_artifact_json"],
            )
        if artifact.negative_results or artifact.failed_trials:
            add_finding(
                severity="info",
                category="statistics",
                summary="The run preserves negative-result evidence.",
                detail=(
                    f"Negative results: {len(artifact.negative_results)}. "
                    f"Failed trials: {len(artifact.failed_trials)}."
                ),
                supporting_asset_ids=["run_artifact_json"],
            )
        if optional_assets and any(not item.ref.exists for item in optional_assets):
            add_finding(
                severity="info",
                category="publish",
                summary="Optional publish assets are not fully materialized.",
                detail="This is acceptable for review packaging, but a final publish package may still want those extras.",
                supporting_asset_ids=[item.asset_id for item in optional_assets if not item.ref.exists],
            )

    return findings, evidence, citation_coverage


def _review_scores(
    *,
    run: AutoResearchRunRead,
    bundle: AutoResearchBundleRead | None,
    findings: list[AutoResearchReviewFindingRead],
    evidence: AutoResearchReviewEvidenceRead,
    citation_coverage: AutoResearchCitationCoverageRead,
    selected_manifest_source: str | None,
) -> AutoResearchReviewScoresRead:
    errors = sum(1 for item in findings if item.severity == "error")
    warnings = sum(1 for item in findings if item.severity == "warning")
    required_assets = [item for item in bundle.assets if item.required] if bundle is not None else []
    existing_hashed_required_files = sum(
        1
        for item in required_assets
        if item.ref.exists and item.ref.kind == "file" and item.ref.sha256
    )

    evidence_support = 1
    if run.artifact is not None and run.artifact.status == "done":
        evidence_support += 2
    if evidence.acceptance_total and evidence.acceptance_passed == evidence.acceptance_total:
        evidence_support += 1
    if evidence.candidate_count > 1 and evidence.executed_candidate_count >= 1:
        evidence_support += 1
    if errors:
        evidence_support -= 2

    statistical_rigor = 0
    statistical_rigor += 1 if evidence.seed_count > 0 else 0
    statistical_rigor += 1 if evidence.completed_seed_count >= evidence.seed_count and evidence.seed_count > 0 else 0
    statistical_rigor += 1 if evidence.sweep_count > 0 else 0
    statistical_rigor += 1 if evidence.significance_test_count > 0 else 0
    statistical_rigor += 1 if evidence.negative_result_count or evidence.failed_trial_count else 0

    contextualization = 0
    contextualization += 1 if evidence.literature_count > 0 else 0
    contextualization += 1 if citation_coverage.citation_marker_count > 0 else 0
    contextualization += 1 if citation_coverage.cited_literature_count > 0 else 0
    contextualization += 1 if citation_coverage.has_related_work_section else 0
    contextualization += 1 if citation_coverage.has_references_section and citation_coverage.cited_literature_count > 0 else 0
    contextualization += 1 if not citation_coverage.sections_without_citations and evidence.literature_count > 0 else 0
    if citation_coverage.sections_without_citations:
        contextualization -= 1
    if citation_coverage.invalid_citation_indices:
        contextualization -= 1

    reproducibility = 0
    reproducibility += 1 if bundle is not None else 0
    reproducibility += 2 if evidence.missing_required_asset_count == 0 else 0
    reproducibility += 1 if existing_hashed_required_files else 0
    reproducibility += 1 if selected_manifest_source == "file" else 0

    publish_readiness = 5
    publish_readiness -= min(errors * 2, 4)
    publish_readiness -= min(warnings, 3)

    return AutoResearchReviewScoresRead(
        evidence_support=_clamp_score(evidence_support),
        statistical_rigor=_clamp_score(statistical_rigor),
        contextualization=_clamp_score(contextualization),
        reproducibility=_clamp_score(reproducibility),
        publish_readiness=_clamp_score(publish_readiness),
    )


def _revision_plan(findings: list[AutoResearchReviewFindingRead]) -> list[AutoResearchRevisionActionRead]:
    actions: list[AutoResearchRevisionActionRead] = []
    by_key: dict[str, int] = {}

    def add_action(*, key: str, priority: str, title: str, detail: str, finding_id: str) -> None:
        index = by_key.get(key)
        if index is None:
            by_key[key] = len(actions)
            actions.append(
                AutoResearchRevisionActionRead(
                    id=f"action_{len(actions) + 1}",
                    priority=priority,
                    title=title,
                    detail=detail,
                    finding_ids=[finding_id],
                )
            )
            return
        actions[index].finding_ids.append(finding_id)

    for finding in findings:
        if finding.category == "artifact":
            add_action(
                key="artifact",
                priority="high",
                title="Regenerate or restore the selected artifact and paper outputs",
                detail="Phase 5 publish work depends on a completed artifact and grounded paper markdown.",
                finding_id=finding.id,
            )
        elif finding.category == "publish":
            add_action(
                key="publish",
                priority="high" if finding.severity == "error" else "medium",
                title="Restore missing publish assets before final packaging",
                detail="The selected publish bundle should have all required run and candidate assets materialized.",
                finding_id=finding.id,
            )
        elif finding.category == "citation":
            add_action(
                key="citation",
                priority="medium",
                title="Add citation support to contextual and related-work claims",
                detail="Introduce explicit citations in background, related-work, and conclusion-facing discussion sections.",
                finding_id=finding.id,
            )
        elif finding.category == "statistics":
            add_action(
                key="statistics",
                priority="high" if finding.severity == "error" else "medium",
                title="Tighten statistical reporting in the paper summary",
                detail="Expose acceptance checks, seeds, sweep choice, and significance support directly in the publish-facing paper.",
                finding_id=finding.id,
            )
        elif finding.category == "context":
            add_action(
                key="context",
                priority="medium",
                title="Strengthen novelty and related-work framing",
                detail="Connect the selected run to preserved literature insights and expose that context in the paper.",
                finding_id=finding.id,
            )
        elif finding.category == "provenance":
            if "literature" in finding.summary.lower() or "citation" in finding.summary.lower():
                add_action(
                    key="citation_provenance",
                    priority="high" if finding.severity == "error" else "medium",
                    title="Repair citation provenance against persisted literature state",
                    detail="Ensure every citation marker resolves to run-local literature metadata and keep a references section in the paper.",
                    finding_id=finding.id,
                )
            else:
                add_action(
                    key="provenance",
                    priority="medium",
                    title="Restore direct provenance files for the selected candidate",
                    detail="Prefer an on-disk candidate manifest over generated fallback metadata before publication review.",
                    finding_id=finding.id,
                )
    return actions


def _review_fingerprint(review: AutoResearchRunReviewRead) -> str:
    payload = {
        "selected_candidate_id": review.selected_candidate_id,
        "overall_status": review.overall_status,
        "unsupported_claim_risk": review.unsupported_claim_risk,
        "findings": [item.model_dump(mode="json") for item in review.findings],
        "revision_plan": [item.model_dump(mode="json") for item in review.revision_plan],
        "scores": review.scores.model_dump(mode="json"),
        "citation_coverage": review.citation_coverage.model_dump(mode="json"),
        "novelty_assessment": (
            review.novelty_assessment.model_dump(mode="json")
            if review.novelty_assessment is not None
            else None
        ),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _loop_issue_id(category: str, summary: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", f"{category}_{summary}".lower()).strip("_")
    if not slug:
        slug = "issue"
    return f"review_issue_{slug[:80]}"


def _loop_action_id(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    if not slug:
        slug = "action"
    return f"review_action_{slug[:80]}"


def _load_review_loop(project_id: str, run_id: str) -> AutoResearchReviewLoopRead | None:
    path = _review_loop_path(project_id, run_id)
    if not path.is_file():
        return None
    try:
        return AutoResearchReviewLoopRead.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sync_paper_revision_state(
    *,
    run: AutoResearchRunRead,
    review: AutoResearchRunReviewRead,
    review_loop: AutoResearchReviewLoopRead,
) -> None:
    writer = PaperWriter()
    existing_state = run.paper_revision_state
    if existing_state is None and run.claim_evidence_matrix is not None:
        existing_state = writer.build_paper_revision_state(
            run.claim_evidence_matrix,
            paper_plan=run.paper_plan,
            figure_plan=run.figure_plan,
        )
    if existing_state is None:
        return
    synced_state = writer.sync_paper_revision_state(
        existing_state,
        review=review,
        review_loop=review_loop,
        paper_plan=run.paper_plan,
        figure_plan=run.figure_plan,
    )
    if existing_state.model_dump(mode="json") == synced_state.model_dump(mode="json"):
        return
    save_run(
        run.model_copy(update={"paper_revision_state": synced_state}),
        touch_updated_at=False,
    )


def _build_review_loop(
    *,
    project_id: str,
    run_id: str,
    review: AutoResearchRunReviewRead,
) -> AutoResearchReviewLoopRead:
    persisted_path = str(_review_loop_path(project_id, run_id))
    existing = _load_review_loop(project_id, run_id)
    fingerprint = _review_fingerprint(review)
    latest_path = review.persisted_path
    same_fingerprint = existing is not None and existing.latest_review_fingerprint == fingerprint
    current_round = (
        existing.current_round
        if same_fingerprint and existing is not None
        else (existing.current_round + 1) if existing is not None else 1
    )
    action_titles_by_finding: dict[str, list[str]] = {}
    for action in review.revision_plan:
        for finding_id in action.finding_ids:
            action_titles_by_finding.setdefault(finding_id, []).append(action.title)

    current_findings: dict[str, AutoResearchReviewFindingRead] = {
        _loop_issue_id(item.category, item.summary): item
        for item in review.findings
    }
    current_issue_ids = set(current_findings)
    current_issue_ids_by_finding_id = {
        finding.id: issue_id
        for issue_id, finding in current_findings.items()
    }
    issues_by_id = {
        item.issue_id: item.model_copy(deep=True)
        for item in (existing.issues if existing is not None else [])
    }

    for issue_id, finding in current_findings.items():
        action_titles = action_titles_by_finding.get(finding.id, [])
        existing_issue = issues_by_id.get(issue_id)
        if existing_issue is None:
            issues_by_id[issue_id] = AutoResearchReviewLoopIssueRead(
                issue_id=issue_id,
                category=finding.category,
                severity=finding.severity,
                summary=finding.summary,
                detail=finding.detail,
                status="open",
                first_seen_round=current_round,
                last_seen_round=current_round,
                finding_ids=[finding.id],
                action_titles=action_titles,
                supporting_asset_ids=list(finding.supporting_asset_ids),
            )
            continue
        issues_by_id[issue_id] = existing_issue.model_copy(
            update={
                "category": finding.category,
                "severity": finding.severity,
                "summary": finding.summary,
                "detail": finding.detail,
                "status": "open",
                "last_seen_round": current_round,
                "finding_ids": [finding.id],
                "action_titles": action_titles,
                "supporting_asset_ids": list(finding.supporting_asset_ids),
            }
        )

    for issue_id, issue in list(issues_by_id.items()):
        if issue_id in current_issue_ids:
            continue
        if same_fingerprint:
            continue
        issues_by_id[issue_id] = issue.model_copy(
            update={
                "status": "resolved",
                "last_seen_round": current_round,
            }
        )

    current_actions = {
        _loop_action_id(item.title): item
        for item in review.revision_plan
    }
    actions_by_id = {
        item.action_id: item.model_copy(deep=True)
        for item in (existing.actions if existing is not None else [])
    }
    for action_id, action in current_actions.items():
        issue_ids = sorted(
            {
                current_issue_ids_by_finding_id[finding_id]
                for finding_id in action.finding_ids
                if finding_id in current_issue_ids_by_finding_id
            }
        )
        existing_action = actions_by_id.get(action_id)
        actions_by_id[action_id] = AutoResearchReviewLoopActionRead(
            action_id=action_id,
            priority=action.priority,
            title=action.title,
            detail=action.detail,
            status="pending",
            first_seen_round=existing_action.first_seen_round if existing_action is not None else current_round,
            last_seen_round=current_round,
            completed_round=None,
            finding_ids=list(action.finding_ids),
            issue_ids=issue_ids,
        )

    for action_id, action in list(actions_by_id.items()):
        if action_id in current_actions:
            continue
        if same_fingerprint:
            continue
        actions_by_id[action_id] = action.model_copy(
            update={
                "status": "completed",
                "last_seen_round": current_round,
                "completed_round": action.completed_round or current_round,
            }
        )

    rounds = list(existing.rounds) if existing is not None else []
    if not same_fingerprint:
        rounds.append(
            AutoResearchReviewLoopRoundRead(
                round_index=current_round,
                generated_at=review.generated_at,
                fingerprint=fingerprint,
                overall_status=review.overall_status,
                unsupported_claim_risk=review.unsupported_claim_risk,
                summary=review.summary,
                review_path=review.persisted_path,
                finding_ids=[item.id for item in review.findings],
                revision_action_ids=list(current_actions),
                revision_action_titles=[item.title for item in review.revision_plan],
                blocker_count=sum(1 for item in review.findings if item.severity == "error"),
            )
        )
    elif not rounds:
        rounds.append(
            AutoResearchReviewLoopRoundRead(
                round_index=current_round,
                generated_at=review.generated_at,
                fingerprint=fingerprint,
                overall_status=review.overall_status,
                unsupported_claim_risk=review.unsupported_claim_risk,
                summary=review.summary,
                review_path=review.persisted_path,
                finding_ids=[item.id for item in review.findings],
                revision_action_ids=list(current_actions),
                revision_action_titles=[item.title for item in review.revision_plan],
                blocker_count=sum(1 for item in review.findings if item.severity == "error"),
            )
        )
    issues = sorted(
        issues_by_id.values(),
        key=lambda item: (
            item.status != "open",
            -item.last_seen_round,
            item.issue_id,
        ),
    )
    priority_order = {"high": 0, "medium": 1, "low": 2}
    actions = sorted(
        actions_by_id.values(),
        key=lambda item: (
            item.status != "pending",
            priority_order.get(item.priority, 3),
            item.title.lower(),
            item.action_id,
        ),
    )
    loop = AutoResearchReviewLoopRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=_utcnow(),
        persisted_path=persisted_path,
        current_round=current_round,
        overall_status=review.overall_status,
        unsupported_claim_risk=review.unsupported_claim_risk,
        latest_review_path=latest_path,
        latest_review_fingerprint=fingerprint,
        rounds=rounds,
        issues=issues,
        actions=actions,
        open_issue_count=sum(1 for item in issues if item.status == "open"),
        resolved_issue_count=sum(1 for item in issues if item.status == "resolved"),
        pending_action_count=sum(1 for item in actions if item.status == "pending"),
        completed_action_count=sum(1 for item in actions if item.status == "completed"),
        pending_revision_actions=[item.title for item in actions if item.status == "pending"],
    )
    _write_json(_review_loop_path(project_id, run_id), loop.model_dump(mode="json"))
    return loop


def build_run_review(project_id: str, run_id: str) -> AutoResearchRunReviewRead | None:
    run = load_run(project_id, run_id)
    registry = load_run_registry(project_id, run_id)
    bundle_index = load_run_bundle_index(project_id, run_id)
    if run is None or registry is None or bundle_index is None:
        return None

    bundle = _selected_bundle(bundle_index)
    selected_entry = next((item for item in registry.candidates if item.selected), None)
    paper_markdown = _paper_markdown(run)
    novelty_assessment = _build_novelty_assessment(
        run=run,
        selected_candidate_id=registry.selected_candidate_id,
    )
    findings, evidence, citation_coverage = _review_findings(
        run=run,
        bundle=bundle,
        selected_manifest_source=selected_entry.manifest_source if selected_entry is not None else None,
        paper_markdown=paper_markdown,
        novelty_assessment=novelty_assessment,
    )
    scores = _review_scores(
        run=run,
        bundle=bundle,
        findings=findings,
        evidence=evidence,
        citation_coverage=citation_coverage,
        selected_manifest_source=selected_entry.manifest_source if selected_entry is not None else None,
    )
    overall_status = (
        "blocked"
        if any(item.severity == "error" for item in findings)
        else "needs_revision"
        if any(item.severity == "warning" for item in findings)
        else "ready"
    )
    unsupported_claim_risk = (
        "high"
        if any(item.severity == "error" for item in findings)
        else "medium"
        if any(item.severity == "warning" for item in findings)
        else "low"
    )
    revision_plan = _revision_plan(findings)
    summary = (
        f"Review built from persisted run, artifact, paper, and registry bundle state. "
        f"Candidates={evidence.candidate_count}, seeds={evidence.seed_count}, sweeps={evidence.sweep_count}, "
        f"significance_tests={evidence.significance_test_count}, citations={citation_coverage.citation_marker_count}, "
        f"resolved_literature={citation_coverage.cited_literature_count}, novelty={novelty_assessment.status}."
    )
    review = AutoResearchRunReviewRead(
        project_id=project_id,
        run_id=run_id,
        generated_at=_utcnow(),
        selected_candidate_id=registry.selected_candidate_id,
        backed_by_bundle_id=bundle.id if bundle is not None else None,
        overall_status=overall_status,
        unsupported_claim_risk=unsupported_claim_risk,
        summary=summary,
        persisted_path=str(_review_path(project_id, run_id)),
        evidence=evidence,
        citation_coverage=citation_coverage,
        novelty_assessment=novelty_assessment,
        scores=scores,
        findings=findings,
        revision_plan=revision_plan,
    )
    _write_json(_review_path(project_id, run_id), review.model_dump(mode="json"))
    review_loop = _build_review_loop(project_id=project_id, run_id=run_id, review=review)
    _sync_paper_revision_state(
        run=run,
        review=review,
        review_loop=review_loop,
    )
    return review


def build_review_loop(project_id: str, run_id: str) -> AutoResearchReviewLoopRead | None:
    review = build_run_review(project_id, run_id)
    if review is None:
        return None
    return _build_review_loop(project_id=project_id, run_id=run_id, review=review)


def build_publish_package(project_id: str, run_id: str) -> AutoResearchPublishPackageRead | None:
    review = build_run_review(project_id, run_id)
    bundle_index = load_run_bundle_index(project_id, run_id)
    if review is None or bundle_index is None:
        return None

    bundle = _selected_bundle(bundle_index)
    if bundle is None:
        return None

    required_assets = [item for item in bundle.assets if item.required]
    final_required_assets = _final_required_assets(bundle)
    optional_assets = [item for item in bundle.assets if not item.required]
    missing_required_assets = [item for item in required_assets if not item.ref.exists]
    missing_final_assets = [item for item in final_required_assets if not item.ref.exists]
    blockers = [item.summary for item in review.findings if item.severity == "error"]
    final_blockers = [
        f"Missing final publish asset: {item.role}"
        for item in missing_final_assets
    ]
    review_bundle_ready = not missing_required_assets
    final_publish_ready = review.overall_status == "ready" and not missing_final_assets
    completeness_status = "complete" if not missing_final_assets else "incomplete"
    status = (
        "blocked"
        if blockers or not review_bundle_ready
        else "publish_ready"
        if final_publish_ready
        else "revision_required"
    )
    package = AutoResearchPublishPackageRead(
        project_id=project_id,
        run_id=run_id,
        package_id="publish_ready_bundle",
        generated_at=_utcnow(),
        selected_candidate_id=review.selected_candidate_id,
        source_bundle_id=bundle.id,
        status=status,
        publish_ready=final_publish_ready,
        review_bundle_ready=review_bundle_ready,
        final_publish_ready=final_publish_ready,
        completeness_status=completeness_status,
        review_path=review.persisted_path,
        manifest_path=str(_publish_manifest_path(project_id, run_id)),
        archive_path=str(_publish_archive_path(project_id, run_id)),
        asset_count=bundle.asset_count,
        existing_asset_count=bundle.existing_asset_count,
        missing_required_asset_count=len(missing_required_assets),
        missing_final_asset_count=len(missing_final_assets),
        blocker_count=len(blockers),
        final_blocker_count=len(final_blockers),
        revision_count=len(review.revision_plan),
        blockers=blockers,
        final_blockers=final_blockers,
        revision_actions=[item.title for item in review.revision_plan],
        required_assets=required_assets,
        final_required_assets=final_required_assets,
        optional_assets=optional_assets,
    )
    _write_json(_publish_manifest_path(project_id, run_id), package.model_dump(mode="json"))
    return package


def _arcname_for_path(run_root: Path, candidate: Path) -> str:
    resolved_root = run_root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        return resolved_candidate.relative_to(resolved_root).as_posix()
    except ValueError:
        return f"external/{candidate.name}"


def _add_path_to_zip(handle: ZipFile, *, run_root: Path, path: Path, added: set[str]) -> None:
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            arcname = _arcname_for_path(run_root, child)
            if arcname in added:
                continue
            handle.write(child, arcname=arcname)
            added.add(arcname)
        return
    if not path.is_file():
        return
    arcname = _arcname_for_path(run_root, path)
    if arcname in added:
        return
    handle.write(path, arcname=arcname)
    added.add(arcname)


def _archive_bundle_kind(package: AutoResearchPublishPackageRead) -> str:
    return "final_publish_bundle" if package.final_publish_ready else "review_bundle"


def _archive_manifest(
    *,
    project_id: str,
    run_id: str,
    package: AutoResearchPublishPackageRead,
) -> dict[str, object]:
    included_assets = [
        asset
        for asset in [*package.required_assets, *package.optional_assets]
        if asset.ref.exists
    ]
    omitted_assets = [
        asset
        for asset in [*package.required_assets, *package.optional_assets]
        if not asset.ref.exists
    ]
    omitted_required_assets = [asset.asset_id for asset in package.required_assets if not asset.ref.exists]
    omitted_final_assets = [asset.asset_id for asset in package.final_required_assets if not asset.ref.exists]
    omitted_optional_assets = [asset.asset_id for asset in package.optional_assets if not asset.ref.exists]
    return {
        "project_id": project_id,
        "run_id": run_id,
        "package_id": package.package_id,
        "generated_at": _utcnow().isoformat(),
        "bundle_kind": _archive_bundle_kind(package),
        "review_bundle_ready": package.review_bundle_ready,
        "final_publish_ready": package.final_publish_ready,
        "completeness_status": package.completeness_status,
        "selected_candidate_id": package.selected_candidate_id,
        "source_bundle_id": package.source_bundle_id,
        "archive_file_name": PUBLISH_ARCHIVE_FILENAME,
        "generated_files": [
            REVIEW_FILENAME,
            REVIEW_LOOP_FILENAME,
            PUBLISH_PACKAGE_FILENAME,
            PUBLISH_ARCHIVE_MANIFEST_FILENAME,
        ],
        "included_asset_count": len(included_assets),
        "omitted_asset_count": len(omitted_assets),
        "included_asset_ids": [asset.asset_id for asset in included_assets],
        "omitted_required_asset_ids": omitted_required_assets,
        "omitted_final_asset_ids": omitted_final_assets,
        "omitted_optional_asset_ids": omitted_optional_assets,
        "blockers": package.blockers,
        "final_blockers": package.final_blockers,
        "revision_actions": package.revision_actions,
    }


def export_publish_package(project_id: str, run_id: str) -> AutoResearchPublishExportRead | None:
    package = build_publish_package(project_id, run_id)
    bundle_index = load_run_bundle_index(project_id, run_id)
    if package is None or bundle_index is None:
        return None

    bundle = _selected_bundle(bundle_index)
    if bundle is None:
        return None

    run_root = run_dir(project_id, run_id)
    archive_path = _publish_archive_path(project_id, run_id)
    archive_manifest_path = _publish_archive_manifest_path(project_id, run_id)
    archive_manifest = _archive_manifest(
        project_id=project_id,
        run_id=run_id,
        package=package,
    )
    _write_json(archive_manifest_path, archive_manifest)
    added: set[str] = set()
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as handle:
        for generated_path in (
            _review_path(project_id, run_id),
            _review_loop_path(project_id, run_id),
            _publish_manifest_path(project_id, run_id),
            archive_manifest_path,
        ):
            if generated_path.is_file():
                handle.write(generated_path, arcname=generated_path.name)
                added.add(generated_path.name)
        for asset in bundle.assets:
            if not asset.ref.exists:
                continue
            _add_path_to_zip(handle, run_root=run_root, path=Path(asset.ref.path), added=added)

    package = package.model_copy(update={"archive_path": str(archive_path)})
    _write_json(_publish_manifest_path(project_id, run_id), package.model_dump(mode="json"))
    return AutoResearchPublishExportRead(
        project_id=project_id,
        run_id=run_id,
        package_id=package.package_id,
        generated_at=_utcnow(),
        bundle_kind=_archive_bundle_kind(package),
        review_bundle_ready=package.review_bundle_ready,
        final_publish_ready=package.final_publish_ready,
        file_name=archive_path.name,
        archive_path=str(archive_path),
        archive_manifest_path=str(archive_manifest_path),
        download_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish/download",
        asset_count=package.asset_count,
        included_asset_count=int(archive_manifest["included_asset_count"]),
        omitted_asset_count=int(archive_manifest["omitted_asset_count"]),
        download_ready=archive_path.is_file(),
    )


def get_publish_archive_path(project_id: str, run_id: str) -> Path:
    return _publish_archive_path(project_id, run_id)
