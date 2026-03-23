from __future__ import annotations

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
)


REVIEW_FILENAME = "review.json"
PUBLISH_PACKAGE_FILENAME = "publish_package.json"
PUBLISH_ARCHIVE_FILENAME = "publish_bundle.zip"
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


def _publish_manifest_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / PUBLISH_PACKAGE_FILENAME


def _publish_archive_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / PUBLISH_ARCHIVE_FILENAME


def _selected_bundle(bundle_index: AutoResearchBundleIndexRead) -> AutoResearchBundleRead | None:
    return next((item for item in bundle_index.bundles if item.id == "selected_candidate_repro"), None)


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
    return review


def build_publish_package(project_id: str, run_id: str) -> AutoResearchPublishPackageRead | None:
    review = build_run_review(project_id, run_id)
    bundle_index = load_run_bundle_index(project_id, run_id)
    if review is None or bundle_index is None:
        return None

    bundle = _selected_bundle(bundle_index)
    if bundle is None:
        return None

    required_assets = [item for item in bundle.assets if item.required]
    optional_assets = [item for item in bundle.assets if not item.required]
    missing_required_assets = [item for item in required_assets if not item.ref.exists]
    blockers = [item.summary for item in review.findings if item.severity == "error"]
    status = (
        "blocked"
        if blockers
        else "publish_ready"
        if not missing_required_assets and review.overall_status == "ready"
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
        publish_ready=status == "publish_ready",
        review_path=review.persisted_path,
        manifest_path=str(_publish_manifest_path(project_id, run_id)),
        archive_path=str(_publish_archive_path(project_id, run_id)),
        asset_count=bundle.asset_count,
        existing_asset_count=bundle.existing_asset_count,
        missing_required_asset_count=len(missing_required_assets),
        blocker_count=len(blockers),
        revision_count=len(review.revision_plan),
        blockers=blockers,
        revision_actions=[item.title for item in review.revision_plan],
        required_assets=required_assets,
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
    added: set[str] = set()
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as handle:
        for generated_path in (
            _review_path(project_id, run_id),
            _publish_manifest_path(project_id, run_id),
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
        file_name=archive_path.name,
        archive_path=str(archive_path),
        download_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish/download",
        asset_count=package.asset_count,
        download_ready=archive_path.is_file(),
    )


def get_publish_archive_path(project_id: str, run_id: str) -> Path:
    return _publish_archive_path(project_id, run_id)
