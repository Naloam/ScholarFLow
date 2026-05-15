from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from config import db as db_module
from schemas.autoresearch import (
    AutoResearchArtifactIntegrityAuditRead,
    AutoResearchBundleAssetRead,
    AutoResearchBundleIndexRead,
    AutoResearchBundleRead,
    AutoResearchBenchmarkCardRead,
    AutoResearchCitationCoverageRead,
    AutoResearchDeploymentRefRead,
    AutoResearchMethodologyAuditRead,
    AutoResearchNoveltyAssessmentRead,
    AutoResearchPaperRevisionStateRead,
    AutoResearchPublicationReadinessRead,
    AutoResearchPublicationRepairExecutionRead,
    AutoResearchResearchProtocolRead,
    AutoResearchPublishExportRead,
    AutoResearchPublishExportRequest,
    AutoResearchPublishPackageRead,
    AutoResearchPublicationManifestRead,
    AutoResearchRelatedWorkMatchRead,
    AutoResearchReviewEvidenceRead,
    AutoResearchReviewFindingRead,
    AutoResearchReviewLoopActionRead,
    AutoResearchReviewLoopIssueRead,
    AutoResearchReviewLoopRead,
    AutoResearchReviewLoopRoundRead,
    AutoResearchReviewScoresRead,
    AutoResearchRevisionDossierItemRead,
    AutoResearchRevisionDossierRead,
    AutoResearchRevisionActionRead,
    AutoResearchRunRead,
    AutoResearchRunReviewRead,
    HypothesisCandidate,
)
from services.autoresearch.repository import (
    METHODOLOGY_AUDIT_FILENAME,
    BENCHMARK_CARD_FILENAME,
    PAPER_BIBLIOGRAPHY_OUTPUT_FILENAME,
    PAPER_COMPILED_PDF_FILENAME,
    RESEARCH_PROTOCOL_FILENAME,
    PUBLICATION_READINESS_FILENAME,
    PUBLICATION_EVIDENCE_INDEX_FILENAME,
    ARTIFACT_INTEGRITY_AUDIT_FILENAME,
    PUBLICATION_REPAIR_PLAN_FILENAME,
    PUBLICATION_REPAIR_EXECUTION_FILENAME,
    REVISION_DOSSIER_FILENAME,
    load_run,
    load_run_bundle_index,
    load_run_registry,
    benchmark_card_file_path,
    methodology_audit_file_path,
    publication_readiness_file_path,
    publication_evidence_index_file_path,
    artifact_integrity_audit_file_path,
    publication_repair_plan_file_path,
    publication_repair_execution_file_path,
    research_protocol_file_path,
    revision_dossier_file_path,
    run_dir,
    save_run,
)
from services.autoresearch.benchmark_card import build_benchmark_card
from services.autoresearch.artifact_integrity_audit import build_artifact_integrity_audit
from services.autoresearch.methodology_audit import build_methodology_audit
from services.autoresearch.publication_evidence_index import build_publication_evidence_index
from services.autoresearch.publication_repair_plan import build_publication_repair_plan
from services.autoresearch.research_protocol import build_research_protocol
from services.autoresearch.research_readiness import build_publication_readiness
from services.projects.repository import get_project
from services.autoresearch.writer import PaperWriter


REVIEW_FILENAME = "review.json"
REVIEW_LOOP_FILENAME = "review_loop.json"
PUBLISH_PACKAGE_FILENAME = "publish_package.json"
PUBLISH_ARCHIVE_FILENAME = "publish_bundle.zip"
PUBLISH_ARCHIVE_MANIFEST_FILENAME = "archive_manifest.json"
PUBLICATION_MANIFEST_FILENAME = "publication_manifest.json"
CODE_PACKAGE_FILENAME = "code_package.zip"
_DEFAULT_DEPLOYMENT_ID = "local_default"
_DEFAULT_DEPLOYMENT_LABEL = "Local Deployment"
_FINAL_PUBLISH_REQUIRED_ROLES = {
    "run_json",
    "program_json",
    "portfolio_json",
    "benchmark_json",
    "run_benchmark_card_json",
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
    "run_research_protocol_json",
    "run_methodology_audit_json",
    "run_publication_readiness_json",
    "run_revision_dossier_json",
    "run_publication_evidence_index_json",
    "run_artifact_integrity_audit_json",
    "run_publication_repair_plan_json",
    "run_paper_compile_report_json",
    "run_paper_build_script",
    "run_paper_latex_source",
    "run_paper_bibliography_bib",
    "run_paper_sources_manifest_json",
    "generated_code",
}
_CODE_PACKAGE_INCLUDED_ROLES = {
    "run_json",
    "program_json",
    "portfolio_json",
    "benchmark_json",
    "run_benchmark_card_json",
    "run_plan_json",
    "run_spec_json",
    "run_artifact_json",
    "run_generated_code",
    "workspace",
    "candidate_json",
    "plan_json",
    "spec_json",
    "attempts_json",
    "artifact_json",
    "manifest_json",
    "run_research_protocol_json",
    "run_methodology_audit_json",
    "run_publication_readiness_json",
    "run_revision_dossier_json",
    "run_publication_evidence_index_json",
    "run_artifact_integrity_audit_json",
    "run_publication_repair_plan_json",
    "run_publication_repair_execution_json",
    "generated_code",
}
_VOLATILE_GENERATED_DIGEST_ROLES = {
    "run_json",
    "run_benchmark_card_json",
    "run_research_protocol_json",
    "run_methodology_audit_json",
    "run_publication_readiness_json",
    "run_revision_dossier_json",
    "run_publication_evidence_index_json",
    "run_artifact_integrity_audit_json",
    "run_publication_repair_plan_json",
    "run_publication_repair_execution_json",
    "run_paper_compile_report_json",
    "run_paper_sources_manifest_json",
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
_SYNTHETIC_LITERATURE_SOURCES = {
    "ai_generated_context",
    "benchmark_context",
}


def _normalize_text(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _system_aliases(system_name: str) -> set[str]:
    normalized = _normalize_text(system_name)
    aliases = {normalized}
    if "_" in system_name:
        aliases.add(_normalize_text(system_name.replace("_", " ")))
    return {item for item in aliases if item}


def _text_mentions_system(text: str | None, system_name: str) -> bool:
    normalized_text = f" {_normalize_text(text)} "
    return any(f" {alias} " in normalized_text for alias in _system_aliases(system_name))


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary_path.write_text(encoded, encoding="utf-8")
    temporary_path.replace(path)


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


def _publication_manifest_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / PUBLICATION_MANIFEST_FILENAME


def _code_package_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / CODE_PACKAGE_FILENAME


def _normalize_deployment_id(value: str | None) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "_"
        for character in (value or _DEFAULT_DEPLOYMENT_ID).strip()
    ).strip("_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized or _DEFAULT_DEPLOYMENT_ID


def _deployment_ref(
    *,
    deployment_id: str | None,
    deployment_label: str | None,
) -> AutoResearchDeploymentRefRead:
    normalized_id = _normalize_deployment_id(deployment_id)
    label = (deployment_label or "").strip() or (
        _DEFAULT_DEPLOYMENT_LABEL
        if normalized_id == _DEFAULT_DEPLOYMENT_ID
        else normalized_id.replace("_", " ").title()
    )
    return AutoResearchDeploymentRefRead(
        deployment_id=normalized_id,
        label=label,
        listed_at=_utcnow(),
    )


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


def _is_synthetic_literature(item) -> bool:
    source = (getattr(item, "source", None) or "").strip().lower()
    paper_id = (getattr(item, "paper_id", None) or "").strip().lower()
    title = (getattr(item, "title", None) or "").strip().lower()
    return (
        source in _SYNTHETIC_LITERATURE_SOURCES
        or paper_id.startswith("context_ref_")
        or title.startswith("[context summary]")
    )


def _real_literature_items(run: AutoResearchRunRead) -> list:
    return [item for item in run.literature if not _is_synthetic_literature(item)]


def _selected_candidate(
    run: AutoResearchRunRead,
    selected_candidate_id: str | None,
) -> HypothesisCandidate | None:
    return next((item for item in run.candidates if item.id == selected_candidate_id), None)


def _topic_proxy_alignment_finding(
    run: AutoResearchRunRead,
) -> tuple[str, str, str] | None:
    plan = run.plan
    spec = run.spec
    if plan is None or spec is None:
        return None
    topic_terms = _terms(plan.topic)
    proxy_terms = _terms(
        spec.benchmark_name,
        spec.benchmark_description,
        spec.dataset.name,
        spec.dataset.description,
        " ".join(spec.dataset.input_fields),
        " ".join(spec.dataset.query_fields),
        " ".join(spec.dataset.label_space),
    )
    if not topic_terms or not proxy_terms:
        return None

    shared_terms = sorted(topic_terms & proxy_terms)
    if len(shared_terms) >= 2 or (shared_terms and len(topic_terms) <= 2):
        return None
    if shared_terms:
        return (
            "warning",
            "Requested topic only weakly overlaps the executed proxy benchmark.",
            (
                f"The requested topic `{plan.topic}` was executed through benchmark `{spec.benchmark_name}` "
                f"(`{spec.dataset.name}`), but the lexical overlap is limited to {', '.join(shared_terms)}. "
                "Tighten the paper framing so claims are scoped to the proxy benchmark rather than the full topic."
            ),
        )
    severity = "error" if len(topic_terms) >= 2 else "warning"
    return (
        severity,
        "Requested topic and executed proxy benchmark are not semantically aligned.",
        (
            f"The requested topic `{plan.topic}` was executed through benchmark `{spec.benchmark_name}` "
            f"(`{spec.dataset.name}`), but the persisted plan and benchmark share no meaningful topic terms. "
            "Final publish should either narrow the paper to the actual benchmark task or rerun on a benchmark that "
            "directly matches the requested topic."
        ),
    )


def _hypothesis_resolution_finding(
    run: AutoResearchRunRead,
    paper_markdown: str,
) -> tuple[str, str, str] | None:
    artifact = run.artifact
    spec = run.spec
    if artifact is None or artifact.status != "done" or spec is None:
        return None
    best_system_name = artifact.best_system or artifact.objective_system
    if not best_system_name:
        return None
    candidate_names = sorted(
        {item.name for item in [*spec.baselines, *spec.ablations]},
        key=len,
        reverse=True,
    )
    mentioned_systems = [
        item
        for item in candidate_names
        if _text_mentions_system(spec.hypothesis, item)
    ]
    if not mentioned_systems:
        return None
    if best_system_name in mentioned_systems:
        return None
    publication_profile = run.request is not None and run.request.execution_profile == "publication"
    if publication_profile:
        objective_system_name = artifact.objective_system
        objective_score = artifact.objective_score
        best_score = None
        for item in [*artifact.system_results, *artifact.aggregate_system_results]:
            metric_value = item.metrics.get(artifact.primary_metric) if hasattr(item, "metrics") else None
            if metric_value is None and hasattr(item, "mean_metrics"):
                metric_value = item.mean_metrics.get(artifact.primary_metric)
            if item.system == best_system_name and metric_value is not None:
                best_score = float(metric_value)
            if item.system == objective_system_name and metric_value is not None:
                objective_score = float(metric_value)
        if (
            objective_system_name in mentioned_systems
            and objective_score is not None
            and best_score is not None
            and abs(float(objective_score) - float(best_score)) <= 1e-12
        ):
            return None
    lowered_paper = paper_markdown.lower()
    if (
        publication_profile
        and best_system_name
        and best_system_name.lower() in lowered_paper
        and (
            "original hypothesis is not supported" in lowered_paper
            or "hypothesis is not supported" in lowered_paper
            or "contradicts the planned hypothesis" in lowered_paper
            or "initial hypothesis was contradicted" in lowered_paper
            or "original hypothesis was contradicted" in lowered_paper
        )
    ):
        return None
    mentioned_attempts = sorted(
        {
            attempt.strategy.removesuffix("_search")
            for attempt in run.attempts
            if any(
                _text_mentions_system(attempt.strategy, system_name)
                or _text_mentions_system(attempt.summary, system_name)
                or (
                    attempt.artifact is not None
                    and (
                        attempt.artifact.best_system == system_name
                        or attempt.artifact.objective_system == system_name
                        or any(item.system == system_name for item in attempt.artifact.system_results)
                        or any(item.system == system_name for item in attempt.artifact.aggregate_system_results)
                    )
                )
                for system_name in mentioned_systems
            )
        }
    )
    mentioned_label = ", ".join(f"`{item}`" for item in mentioned_systems)
    attempt_clause = (
        f" Related execution rounds still tested {', '.join(f'`{item}`' for item in mentioned_attempts)}."
        if mentioned_attempts
        else ""
    )
    return (
        "warning",
        "Paper should state clearly that the original hypothesis was not supported.",
        (
            f"The study hypothesis names {mentioned_label}, but the selected artifact ranks `{best_system_name}` "
            f"highest on `{artifact.primary_metric}`.{attempt_clause} The publish-facing paper should explicitly say "
            "that the initial hypothesis was contradicted or only partially supported."
        ),
    )


def _system_names_from_artifact(artifact) -> set[str]:
    if artifact is None:
        return set()
    names: set[str] = set()
    if artifact.best_system:
        names.add(artifact.best_system)
    if artifact.objective_system:
        names.add(artifact.objective_system)
    for collection_name in ("system_results", "aggregate_system_results"):
        for item in getattr(artifact, collection_name, []) or []:
            system = getattr(item, "system", None)
            if system:
                names.add(system)
    for sweep in getattr(artifact, "sweep_results", []) or []:
        if sweep.best_system:
            names.add(sweep.best_system)
        if sweep.objective_system:
            names.add(sweep.objective_system)
        for item in sweep.aggregate_system_results:
            if item.system:
                names.add(item.system)
    return names


def _planned_ablation_gaps(run: AutoResearchRunRead) -> list[str]:
    spec = run.spec
    artifact = run.artifact
    if spec is None:
        return []
    observed_systems = _system_names_from_artifact(artifact)
    gaps = []
    for ablation in spec.ablations:
        if ablation.name not in observed_systems:
            gaps.append(ablation.name)
    return gaps


def _unsupported_claim_gap_finding(
    run: AutoResearchRunRead,
) -> tuple[str, str, str] | None:
    matrix = run.claim_evidence_matrix
    if matrix is None:
        return None
    unsupported = [item for item in matrix.entries if item.support_status == "unsupported"]
    if not unsupported:
        return None
    example_claims = "; ".join(item.claim for item in unsupported[:3])
    return (
        "warning",
        "Claim-evidence matrix contains unsupported publish-facing claims.",
        (
            f"{len(unsupported)}/{matrix.claim_count} claim commitments are unsupported by "
            "the selected artifact and literature state. Demote unsupported claims to limitations or run the "
            f"missing experiments before final publish. Examples: {example_claims}"
        ),
    )


def _semantic_final_publish_blockers(review: AutoResearchRunReviewRead) -> list[str]:
    blockers: list[str] = []
    if review.publication_readiness is not None:
        for item in review.publication_readiness.blockers:
            blockers.append(f"Final publish readiness gate: {item}")
    if review.artifact_integrity_audit is not None:
        for item in review.artifact_integrity_audit.blockers:
            blockers.append(f"Final publish artifact integrity gate: {item}")
    else:
        blockers.append("Final publish requires an artifact registry and lineage integrity audit.")
    for finding in review.findings:
        lowered_summary = finding.summary.lower()
        if finding.category == "citation":
            blockers.append(f"Final publish requires citation-grounded paper text: {finding.summary}")
            continue
        if finding.category == "benchmark":
            blockers.append(f"Final publish requires a publication-grade benchmark: {finding.summary}")
            continue
        if finding.category == "provenance" and "research protocol" in lowered_summary:
            blockers.append(f"Final publish requires a complete research protocol: {finding.summary}")
            continue
        if "methodology audit" in lowered_summary:
            blockers.append(f"Final publish requires protocol-compliant methodology: {finding.summary}")
            continue
        if finding.category == "context":
            if (
                "no literature insights were persisted" in lowered_summary
                or "no real literature sources" in lowered_summary
                or "novelty framing is weakly grounded" in lowered_summary
                or "lacks an explicit related-work section" in lowered_summary
                or "requested topic" in lowered_summary
                or "original hypothesis" in lowered_summary
            ):
                blockers.append(f"Final publish requires tighter research framing: {finding.summary}")
            if "claim-evidence matrix contains unsupported" in lowered_summary:
                blockers.append(f"Final publish requires supported claim-evidence commitments: {finding.summary}")
            continue
        if finding.category == "statistics" and (
            "does not preserve significance" in lowered_summary
            or "seed coverage is insufficient" in lowered_summary
            or "seed coverage is below final-publish grade" in lowered_summary
            or "publication-profile seed coverage is incomplete" in lowered_summary
            or "planned ablations were not executed" in lowered_summary
        ):
            blockers.append(f"Final publish requires stronger experimental evidence: {finding.summary}")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in blockers:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _repair_state_final_blockers(review: AutoResearchRunReviewRead) -> list[str]:
    blockers: list[str] = []
    repair_plan = review.publication_repair_plan
    repair_execution = review.publication_repair_execution
    if repair_plan is not None:
        if repair_plan.pending_action_count:
            blockers.append(
                "Final publish requires applying or explicitly resolving "
                f"{repair_plan.pending_action_count} pending publication repair action(s)."
            )
        if repair_plan.blocked_action_count:
            blockers.append(
                "Final publish requires manual closure for "
                f"{repair_plan.blocked_action_count} blocked publication repair action(s)."
            )
        for item in repair_plan.blockers[:5]:
            blockers.append(f"Final publish repair plan blocker: {item}")
        if (
            not repair_plan.complete
            and not repair_plan.pending_action_count
            and not repair_plan.blocked_action_count
            and not repair_plan.blockers
        ):
            blockers.append("Final publish requires closing the publication repair plan.")
    if repair_execution is not None:
        if (
            repair_plan is not None
            and repair_execution.repair_plan_fingerprint
            and repair_plan.repair_plan_fingerprint
            and repair_execution.repair_plan_fingerprint != repair_plan.repair_plan_fingerprint
            and not repair_plan.complete
        ):
            blockers.append("Final publish repair execution is stale relative to the current repair plan.")
        if repair_execution.partial_action_count or repair_execution.blocked_action_count:
            blockers.append(
                "Final publish repair execution has incomplete action results: "
                f"{repair_execution.partial_action_count} partial, "
                f"{repair_execution.blocked_action_count} blocked."
            )
        if repair_execution.missing_output_asset_ids:
            missing = ", ".join(repair_execution.missing_output_asset_ids[:6])
            if len(repair_execution.missing_output_asset_ids) > 6:
                missing = f"{missing}, ..."
            blockers.append(f"Final publish repair execution is missing expected outputs: {missing}.")
        if repair_execution.attempted_action_count and not repair_execution.success:
            blockers.append("Final publish repair execution did not complete successfully.")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in blockers:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


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
    real_literature = _real_literature_items(run)
    if not real_literature:
        return AutoResearchNoveltyAssessmentRead(
            status="missing_context",
            summary=(
                f"The run retained {len(run.literature)} fallback context item(s), but no real literature records. "
                "Novelty cannot be publication-grounded until retrieved papers are persisted."
            ),
            compared_paper_count=0,
        )

    candidate_method_terms = _terms(candidate.title, candidate.hypothesis, candidate.proposed_method)
    candidate_claim_terms = _terms(*candidate.planned_contributions)
    matches: list[AutoResearchRelatedWorkMatchRead] = []
    strong_match_count = 0
    gap_aligned_paper_count = 0

    for item in real_literature:
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
        for item in real_literature
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
            f"The selected candidate does not show a strong lexical or gap-aligned match against {len(real_literature)} "
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
        compared_paper_count=len(real_literature),
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
    benchmark_card: AutoResearchBenchmarkCardRead,
    research_protocol: AutoResearchResearchProtocolRead,
    methodology_audit: AutoResearchMethodologyAuditRead,
    publication_readiness: AutoResearchPublicationReadinessRead,
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
    real_literature_count = len(_real_literature_items(run))
    synthetic_literature_count = len(run.literature) - real_literature_count
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
        real_literature_count=real_literature_count,
        synthetic_literature_count=synthetic_literature_count,
        publication_grade_benchmark=publication_readiness.publication_grade_benchmark,
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
    topic_proxy_alignment = _topic_proxy_alignment_finding(run)
    if topic_proxy_alignment is not None:
        severity, summary, detail = topic_proxy_alignment
        add_finding(
            severity=severity,
            category="context",
            summary=summary,
            detail=detail,
            supporting_asset_ids=["run_plan_json", "run_spec_json", "run_paper_markdown"],
        )
    hypothesis_resolution = _hypothesis_resolution_finding(run, paper_markdown)
    if hypothesis_resolution is not None:
        severity, summary, detail = hypothesis_resolution
        add_finding(
            severity=severity,
            category="context",
            summary=summary,
            detail=detail,
            supporting_asset_ids=["run_spec_json", "run_artifact_json", "run_paper_markdown"],
        )
    unsupported_claim_gap = _unsupported_claim_gap_finding(run)
    if unsupported_claim_gap is not None:
        severity, summary, detail = unsupported_claim_gap
        add_finding(
            severity=severity,
            category="context",
            summary=summary,
            detail=detail,
            supporting_asset_ids=["run_claim_evidence_matrix_json", "run_paper_markdown"],
        )
    if benchmark_card.blockers:
        add_finding(
            severity="error",
            category="benchmark",
            summary="Benchmark card is incomplete for publication review.",
            detail="; ".join(benchmark_card.blockers),
            supporting_asset_ids=["run_benchmark_card_json", "benchmark_json", "run_spec_json"],
        )
    if research_protocol.blockers:
        add_finding(
            severity="error" if research_protocol.execution_profile == "publication" else "warning",
            category="provenance",
            summary="Research protocol is incomplete.",
            detail="; ".join(research_protocol.blockers),
            supporting_asset_ids=["run_research_protocol_json", "run_spec_json"],
        )
    if methodology_audit.blockers:
        add_finding(
            severity="error" if methodology_audit.execution_profile == "publication" else "warning",
            category="statistics",
            summary="Methodology audit found protocol adherence gaps.",
            detail="; ".join(methodology_audit.blockers),
            supporting_asset_ids=[
                "run_methodology_audit_json",
                "run_research_protocol_json",
                "run_artifact_json",
            ],
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
    elif real_literature_count == 0:
        add_finding(
            severity="warning",
            category="context",
            summary="No real literature sources were persisted with the run.",
            detail=(
                f"The run retained {synthetic_literature_count} fallback context item(s), but all persisted "
                "literature is synthetic benchmark or AI-generated context. Final publish needs at least one "
                "retrieved paper record from a real literature source."
            ),
            supporting_asset_ids=["run_json", "run_paper_markdown"],
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
        if not publication_readiness.publication_grade_benchmark:
            add_finding(
                severity="warning",
                category="benchmark",
                summary="Selected benchmark is not publication-grade.",
                detail=next(
                    (
                        item.detail
                        for item in publication_readiness.checks
                        if item.check_id == "publication_grade_benchmark"
                    ),
                    "Final publish requires an external benchmark with persisted provenance.",
                ),
                supporting_asset_ids=["run_benchmark_json", "run_spec_json"],
            )
        if evidence.completed_seed_count < 2:
            add_finding(
                severity="warning",
                category="statistics",
                summary="Seed coverage is insufficient for publication-level claims.",
                detail=(
                    f"The selected artifact preserves {evidence.completed_seed_count} completed seed result(s) "
                    f"for {evidence.seed_count} requested seed(s). Final publish should run at least two completed "
                    "seeds, and preferably the requested seed set, before making stability or robustness claims."
                ),
                supporting_asset_ids=["run_spec_json", "run_artifact_json"],
            )
        elif evidence.completed_seed_count < publication_readiness.requested_seed_count and (
            run.request is not None and run.request.execution_profile == "publication"
        ):
            add_finding(
                severity="warning",
                category="statistics",
                summary="Publication-profile seed coverage is incomplete.",
                detail=(
                    f"The selected artifact preserves {evidence.completed_seed_count}/"
                    f"{publication_readiness.requested_seed_count} publication-profile seed results. "
                    "Complete the requested publication seed set or rerun in exploratory profile."
                ),
                supporting_asset_ids=["run_spec_json", "run_artifact_json"],
            )
        elif evidence.completed_seed_count < 3:
            add_finding(
                severity="warning",
                category="statistics",
                summary="Seed coverage is below final-publish grade.",
                detail=(
                    f"The selected artifact preserves {evidence.completed_seed_count} completed seed result(s). "
                    "Final publish requires at least three completed seeds; use publication profile for paper-candidate runs."
                ),
                supporting_asset_ids=["run_spec_json", "run_artifact_json"],
            )
        elif evidence.seed_count and evidence.completed_seed_count < evidence.seed_count:
            add_finding(
                severity="warning",
                category="statistics",
                summary="Seed coverage is incomplete relative to the experiment specification.",
                detail=(
                    f"The selected artifact preserves {evidence.completed_seed_count}/{evidence.seed_count} requested seed "
                    "results. Complete the planned seed set or narrow claims to the executed subset."
                ),
                supporting_asset_ids=["run_spec_json", "run_artifact_json"],
            )
        missing_ablations = _planned_ablation_gaps(run)
        if missing_ablations:
            add_finding(
                severity="warning",
                category="statistics",
                summary="Planned ablations were not executed in the selected artifact.",
                detail=(
                    "The experiment specification lists ablations that do not appear in the final result tables or "
                    "aggregate system results: "
                    + ", ".join(f"`{item}`" for item in missing_ablations)
                    + ". Run these ablations or demote the related hypotheses to limitations."
                ),
                supporting_asset_ids=["run_spec_json", "run_artifact_json"],
            )
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
        if finding.severity == "info":
            continue
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
        elif finding.category == "benchmark":
            add_action(
                key="publication_grade_benchmark",
                priority="high",
                title="Rerun on a publication-grade external benchmark",
                detail="Replace built-in toy benchmarks with a persisted external benchmark source, dataset card, and reproducible split before final publish.",
                finding_id=finding.id,
            )
        elif finding.category == "statistics":
            lowered_summary = finding.summary.lower()
            if (
                "seed coverage is insufficient" in lowered_summary
                or "seed coverage is incomplete" in lowered_summary
                or "seed coverage is below final-publish grade" in lowered_summary
                or "publication-profile seed coverage is incomplete" in lowered_summary
            ):
                add_action(
                    key="seed_coverage",
                    priority="high",
                    title="Run additional seeds before final publication",
                    detail="Complete the planned seed set, preserve per-seed artifacts, and regenerate aggregate metrics before making stability claims.",
                    finding_id=finding.id,
                )
            elif "planned ablations were not executed" in lowered_summary:
                add_action(
                    key="planned_ablations",
                    priority="high",
                    title="Run planned ablations or demote ablation claims",
                    detail="Execute every ablation named in the experiment specification, or revise the paper to state that those hypotheses remain untested.",
                    finding_id=finding.id,
                )
            elif "significance comparisons" in lowered_summary:
                add_action(
                    key="significance",
                    priority="high",
                    title="Run paired significance comparisons",
                    detail="Preserve paired significance tests for the primary metric so score gaps can be interpreted as more than one-off wins.",
                    finding_id=finding.id,
                )
            else:
                add_action(
                    key="statistics",
                    priority="high" if finding.severity == "error" else "medium",
                    title="Tighten statistical reporting in the paper summary",
                    detail="Expose acceptance checks, seeds, sweep choice, and significance support directly in the publish-facing paper.",
                    finding_id=finding.id,
                )
        elif finding.category == "context":
            lowered_summary = finding.summary.lower()
            if "proxy benchmark" in lowered_summary or "requested topic" in lowered_summary:
                add_action(
                    key="topic_alignment",
                    priority="high" if finding.severity == "error" else "medium",
                    title="Align the paper framing with the executed proxy benchmark",
                    detail="Either narrow the manuscript to the actual benchmark task or rerun on a benchmark that directly matches the requested topic.",
                    finding_id=finding.id,
                )
            elif "original hypothesis" in lowered_summary:
                add_action(
                    key="hypothesis_resolution",
                    priority="medium",
                    title="State clearly whether the original hypothesis was supported",
                    detail="Make the publish-facing paper say whether the planned hypothesis held under the selected artifact and what system actually won.",
                    finding_id=finding.id,
                )
            elif "claim-evidence matrix contains unsupported" in lowered_summary:
                add_action(
                    key="claim_evidence",
                    priority="high",
                    title="Rerun experiments or demote unsupported claims",
                    detail="Every publish-facing claim should map to persisted evidence; unsupported claims must become limitations or trigger additional experiments.",
                    finding_id=finding.id,
                )
            else:
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


def _review_fingerprint(
    review: AutoResearchRunReviewRead,
    *,
    run: AutoResearchRunRead | None = None,
    paper_markdown: str | None = None,
) -> str:
    payload = {
        "selected_candidate_id": review.selected_candidate_id,
        "paper_draft_version": run.paper_draft_version if run is not None else None,
        "paper_markdown_sha256": (
            hashlib.sha256(paper_markdown.encode("utf-8")).hexdigest()
            if paper_markdown is not None
            else None
        ),
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


def _load_publication_repair_execution(
    project_id: str,
    run_id: str,
) -> AutoResearchPublicationRepairExecutionRead | None:
    path = Path(publication_repair_execution_file_path(project_id, run_id))
    if not path.is_file():
        return None
    try:
        return AutoResearchPublicationRepairExecutionRead.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return None


def _paper_revision_state_semantic_payload(
    state: AutoResearchPaperRevisionStateRead,
) -> dict[str, object]:
    payload = state.model_dump(mode="json")
    payload.pop("generated_at", None)
    return payload


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
    existing_payload = _paper_revision_state_semantic_payload(existing_state)
    synced_payload = _paper_revision_state_semantic_payload(synced_state)
    if existing_payload == synced_payload:
        return
    save_run(
        run.model_copy(update={"paper_revision_state": synced_state}),
        touch_updated_at=False,
        materialize_paper_workspace=False,
    )


def _build_review_loop(
    *,
    project_id: str,
    run_id: str,
    review: AutoResearchRunReviewRead,
    run: AutoResearchRunRead | None = None,
    paper_markdown: str | None = None,
    advance_round: bool = False,
) -> AutoResearchReviewLoopRead:
    persisted_path = str(_review_loop_path(project_id, run_id))
    existing = _load_review_loop(project_id, run_id)
    fingerprint = _review_fingerprint(review, run=run, paper_markdown=paper_markdown)
    latest_path = review.persisted_path
    same_fingerprint = existing is not None and existing.latest_review_fingerprint == fingerprint
    if existing is None:
        current_round = 1
    elif same_fingerprint and not advance_round:
        current_round = existing.current_round
    else:
        current_round = existing.current_round + 1
    action_titles_by_finding: dict[str, list[str]] = {}
    for action in review.revision_plan:
        for finding_id in action.finding_ids:
            action_titles_by_finding.setdefault(finding_id, []).append(action.title)

    actionable_findings = [
        item for item in review.findings if item.severity != "info"
    ]
    current_findings: dict[str, AutoResearchReviewFindingRead] = {
        _loop_issue_id(item.category, item.summary): item
        for item in actionable_findings
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
    if not same_fingerprint or advance_round:
        rounds.append(
            AutoResearchReviewLoopRoundRead(
                round_index=current_round,
                generated_at=review.generated_at,
                fingerprint=fingerprint,
                overall_status=review.overall_status,
                unsupported_claim_risk=review.unsupported_claim_risk,
                summary=review.summary,
                review_path=review.persisted_path,
                finding_ids=[item.id for item in actionable_findings],
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
                finding_ids=[item.id for item in actionable_findings],
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


def _revision_dossier_response(
    *,
    finding: AutoResearchReviewFindingRead,
    action_titles: list[str],
    resolved: bool,
) -> str:
    if resolved:
        return "Resolved in the current review loop; preserve the repaired evidence and manuscript state."
    if action_titles:
        return "Required revision: " + "; ".join(action_titles) + "."
    return f"Address this {finding.category} finding before treating the run as publication-ready."


def _build_revision_dossier(
    *,
    review: AutoResearchRunReviewRead,
    review_loop: AutoResearchReviewLoopRead,
) -> AutoResearchRevisionDossierRead:
    issues_by_finding_id: dict[str, AutoResearchReviewLoopIssueRead] = {}
    for issue in review_loop.issues:
        for finding_id in issue.finding_ids:
            issues_by_finding_id[finding_id] = issue
    actions_by_finding_id: dict[str, list[AutoResearchReviewLoopActionRead]] = {}
    for action in review_loop.actions:
        for finding_id in action.finding_ids:
            actions_by_finding_id.setdefault(finding_id, []).append(action)

    items: list[AutoResearchRevisionDossierItemRead] = []
    for finding in review.findings:
        if finding.severity == "info":
            continue
        issue = issues_by_finding_id.get(finding.id)
        actions = actions_by_finding_id.get(finding.id, [])
        action_titles = [item.title for item in actions]
        resolved = issue is not None and issue.status == "resolved"
        required_for_final_publish = finding.severity == "error" or any(
            item.priority == "high" for item in actions
        )
        status = (
            "resolved"
            if resolved
            else "blocked"
            if required_for_final_publish
            else "action_required"
        )
        items.append(
            AutoResearchRevisionDossierItemRead(
                item_id=f"revision_item_{len(items) + 1}",
                finding_id=finding.id,
                issue_id=issue.issue_id if issue is not None else None,
                severity=finding.severity,
                category=finding.category,
                summary=finding.summary,
                response=_revision_dossier_response(
                    finding=finding,
                    action_titles=action_titles,
                    resolved=resolved,
                ),
                status=status,
                required_for_final_publish=required_for_final_publish,
                action_ids=[item.action_id for item in actions],
                action_titles=action_titles,
                supporting_asset_ids=list(finding.supporting_asset_ids),
            )
        )

    publication_readiness = review.publication_readiness
    methodology_audit = review.methodology_audit
    required_open_items = [
        item for item in items if item.required_for_final_publish and item.status != "resolved"
    ]
    payload = {
        "dossier_id": "revision_dossier_v1",
        "review_round": review_loop.current_round,
        "review_fingerprint": review_loop.latest_review_fingerprint,
        "review_path": review.persisted_path,
        "overall_status": review.overall_status,
        "publication_tier": publication_readiness.tier if publication_readiness is not None else "exploratory",
        "publication_readiness_score": publication_readiness.score if publication_readiness is not None else 0,
        "methodology_audit_score": methodology_audit.score if methodology_audit is not None else 0,
        "methodology_audit_compliant": methodology_audit.compliant if methodology_audit is not None else False,
        "open_issue_count": review_loop.open_issue_count,
        "resolved_issue_count": review_loop.resolved_issue_count,
        "pending_action_count": review_loop.pending_action_count,
        "completed_action_count": review_loop.completed_action_count,
        "blocker_count": sum(1 for item in review.findings if item.severity == "error"),
        "final_blocker_count": len(required_open_items),
        "required_action_titles": list(review_loop.pending_revision_actions),
        "items": [item.model_dump(mode="json") for item in items],
        "complete": not required_open_items,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return AutoResearchRevisionDossierRead(
        generated_at=_utcnow(),
        dossier_fingerprint=hashlib.sha256(encoded).hexdigest(),
        **payload,
    )


def _build_and_persist_artifact_integrity_audit(
    project_id: str,
    run_id: str,
) -> tuple[AutoResearchArtifactIntegrityAuditRead, str] | None:
    registry = load_run_registry(project_id, run_id)
    bundle_index = load_run_bundle_index(project_id, run_id)
    if registry is None or bundle_index is None:
        return None
    audit = build_artifact_integrity_audit(
        registry=registry,
        bundle_index=bundle_index,
    )
    audit_path = Path(artifact_integrity_audit_file_path(project_id, run_id))
    _write_json(audit_path, audit.model_dump(mode="json"))
    return audit, str(audit_path)


def build_run_review(
    project_id: str,
    run_id: str,
    *,
    advance_review_loop_round: bool = False,
) -> AutoResearchRunReviewRead | None:
    run = load_run(project_id, run_id)
    if run is None:
        return None

    paper_markdown = _paper_markdown(run)
    benchmark_card = build_benchmark_card(run)
    benchmark_card_path = Path(benchmark_card_file_path(project_id, run_id))
    _write_json(benchmark_card_path, benchmark_card.model_dump(mode="json"))
    research_protocol = build_research_protocol(run)
    research_protocol_path = Path(research_protocol_file_path(project_id, run_id))
    _write_json(research_protocol_path, research_protocol.model_dump(mode="json"))
    methodology_audit = build_methodology_audit(run, protocol=research_protocol)
    methodology_audit_path = Path(methodology_audit_file_path(project_id, run_id))
    _write_json(methodology_audit_path, methodology_audit.model_dump(mode="json"))
    publication_readiness = build_publication_readiness(
        run,
        paper_markdown=paper_markdown,
    )
    publication_readiness_path = Path(publication_readiness_file_path(project_id, run_id))
    _write_json(publication_readiness_path, publication_readiness.model_dump(mode="json"))
    artifact_integrity_result = _build_and_persist_artifact_integrity_audit(
        project_id,
        run_id,
    )
    if artifact_integrity_result is None:
        return None
    artifact_integrity_audit, artifact_integrity_audit_path = artifact_integrity_result
    registry = load_run_registry(project_id, run_id)
    bundle_index = load_run_bundle_index(project_id, run_id)
    if registry is None or bundle_index is None:
        return None

    bundle = _selected_bundle(bundle_index)
    selected_entry = next((item for item in registry.candidates if item.selected), None)
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
        benchmark_card=benchmark_card,
        research_protocol=research_protocol,
        methodology_audit=methodology_audit,
        publication_readiness=publication_readiness,
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
        f"resolved_literature={citation_coverage.cited_literature_count}, novelty={novelty_assessment.status}, "
        f"publication_tier={publication_readiness.tier}, readiness_score={publication_readiness.score}."
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
        benchmark_card=benchmark_card,
        benchmark_card_path=str(benchmark_card_path),
        research_protocol=research_protocol,
        research_protocol_path=str(research_protocol_path),
        methodology_audit=methodology_audit,
        methodology_audit_path=str(methodology_audit_path),
        publication_readiness=publication_readiness,
        publication_readiness_path=str(publication_readiness_path),
        scores=scores,
        findings=findings,
        revision_plan=revision_plan,
        artifact_integrity_audit=artifact_integrity_audit,
        artifact_integrity_audit_path=artifact_integrity_audit_path,
    )
    _write_json(_review_path(project_id, run_id), review.model_dump(mode="json"))
    review_loop = _build_review_loop(
        project_id=project_id,
        run_id=run_id,
        review=review,
        run=run,
        paper_markdown=paper_markdown,
        advance_round=advance_review_loop_round,
    )
    revision_dossier = _build_revision_dossier(
        review=review,
        review_loop=review_loop,
    )
    revision_dossier_path = Path(revision_dossier_file_path(project_id, run_id))
    _write_json(revision_dossier_path, revision_dossier.model_dump(mode="json"))
    review = review.model_copy(
        update={
            "revision_dossier": revision_dossier,
            "revision_dossier_path": str(revision_dossier_path),
        }
    )
    publication_evidence_index = build_publication_evidence_index(
        run,
        review=review,
        review_loop=review_loop,
        review_path=_review_path(project_id, run_id),
        review_loop_path=_review_loop_path(project_id, run_id),
    )
    publication_evidence_index_path = Path(
        publication_evidence_index_file_path(project_id, run_id)
    )
    _write_json(
        publication_evidence_index_path,
        publication_evidence_index.model_dump(mode="json"),
    )
    review = review.model_copy(
        update={
            "publication_evidence_index": publication_evidence_index,
            "publication_evidence_index_path": str(publication_evidence_index_path),
        }
    )
    publication_repair_plan = build_publication_repair_plan(
        review=review,
        review_loop=review_loop,
    )
    publication_repair_plan_path = Path(publication_repair_plan_file_path(project_id, run_id))
    _write_json(
        publication_repair_plan_path,
        publication_repair_plan.model_dump(mode="json"),
    )
    review = review.model_copy(
        update={
            "publication_repair_plan": publication_repair_plan,
            "publication_repair_plan_path": str(publication_repair_plan_path),
        }
    )
    publication_repair_execution = _load_publication_repair_execution(project_id, run_id)
    if publication_repair_execution is not None:
        review = review.model_copy(
            update={
                "publication_repair_execution": publication_repair_execution,
                "publication_repair_execution_path": publication_repair_execution_file_path(
                    project_id,
                    run_id,
                ),
            }
        )
    final_artifact_integrity_result = _build_and_persist_artifact_integrity_audit(
        project_id,
        run_id,
    )
    if final_artifact_integrity_result is not None:
        artifact_integrity_audit, artifact_integrity_audit_path = final_artifact_integrity_result
        review = review.model_copy(
            update={
                "artifact_integrity_audit": artifact_integrity_audit,
                "artifact_integrity_audit_path": artifact_integrity_audit_path,
            }
        )
        publication_evidence_index = build_publication_evidence_index(
            run,
            review=review,
            review_loop=review_loop,
            review_path=_review_path(project_id, run_id),
            review_loop_path=_review_loop_path(project_id, run_id),
        )
        _write_json(
            publication_evidence_index_path,
            publication_evidence_index.model_dump(mode="json"),
        )
        review = review.model_copy(
            update={
                "publication_evidence_index": publication_evidence_index,
                "publication_evidence_index_path": str(publication_evidence_index_path),
            }
        )
        publication_repair_plan = build_publication_repair_plan(
            review=review,
            review_loop=review_loop,
        )
        _write_json(
            publication_repair_plan_path,
            publication_repair_plan.model_dump(mode="json"),
        )
        review = review.model_copy(
            update={
                "publication_repair_plan": publication_repair_plan,
                "publication_repair_plan_path": str(publication_repair_plan_path),
            }
        )
    _write_json(_review_path(project_id, run_id), review.model_dump(mode="json"))
    _sync_paper_revision_state(
        run=run,
        review=review,
        review_loop=review_loop,
    )
    return review


def build_review_loop(
    project_id: str,
    run_id: str,
    *,
    advance_round: bool = False,
) -> AutoResearchReviewLoopRead | None:
    review = build_run_review(
        project_id,
        run_id,
        advance_review_loop_round=advance_round,
    )
    if review is None:
        return None
    return _load_review_loop(project_id, run_id)


def _review_loop_revision_requirements(review_loop: AutoResearchReviewLoopRead | None) -> list[str]:
    if review_loop is None:
        return []
    messages: list[str] = []
    if review_loop.open_issue_count > 0:
        messages.append(
            f"Review loop still has {review_loop.open_issue_count} open issue(s) in round {review_loop.current_round}."
        )
    if review_loop.pending_action_count > 0:
        messages.append(
            f"Review loop still has {review_loop.pending_action_count} pending revision action(s)."
        )
    return messages


def _compile_ready_final_blockers(run: AutoResearchRunRead | None) -> list[str]:
    if run is None:
        return ["Paper source package could not be loaded for compile-readiness checks."]
    report = run.paper_compile_report
    if report is None:
        return ["Paper compile report is missing, so compile-ready publication coverage cannot be verified."]
    messages: list[str] = []
    if report.missing_required_source_files:
        missing = ", ".join(report.missing_required_source_files[:6])
        if len(report.missing_required_source_files) > 6:
            missing = f"{missing}, ..."
        messages.append(f"Paper source package is incomplete: missing {missing}.")
    extra_missing_inputs = [
        item
        for item in report.missing_required_inputs
        if item not in report.missing_required_source_files
    ]
    if extra_missing_inputs:
        messages.append(
            "Paper compile path is missing required inputs: "
            + ", ".join(extra_missing_inputs[:6])
            + (", ..." if len(extra_missing_inputs) > 6 else "")
            + "."
        )
    if not report.ready_for_compile and not messages:
        messages.append("Paper source package is not currently marked ready for compile.")
    return messages


def _publish_asset_fingerprint_payload(
    assets: list[AutoResearchBundleAssetRead],
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for asset in assets:
        payload: dict[str, object] = {
            "asset_id": asset.asset_id,
            "role": asset.role,
            "required": asset.required,
            "path": asset.ref.path,
            "kind": asset.ref.kind,
            "exists": asset.ref.exists,
        }
        if asset.role not in _VOLATILE_GENERATED_DIGEST_ROLES:
            payload["size_bytes"] = asset.ref.size_bytes
            payload["sha256"] = asset.ref.sha256
        payloads.append(payload)
    return payloads


def _publish_package_fingerprint(
    *,
    review: AutoResearchRunReviewRead,
    review_loop: AutoResearchReviewLoopRead | None,
    bundle: AutoResearchBundleRead,
    required_assets: list[AutoResearchBundleAssetRead],
    final_required_assets: list[AutoResearchBundleAssetRead],
    optional_assets: list[AutoResearchBundleAssetRead],
    blockers: list[str],
    final_blockers: list[str],
    revision_actions: list[str],
    review_bundle_ready: bool,
    final_publish_ready: bool,
    completeness_status: str,
    status: str,
) -> str:
    payload = {
        "selected_candidate_id": review.selected_candidate_id,
        "review_status": review.overall_status,
        "review_path": review.persisted_path,
        "benchmark_card_path": review.benchmark_card_path,
        "research_protocol_path": review.research_protocol_path,
        "methodology_audit_path": review.methodology_audit_path,
        "publication_readiness_path": review.publication_readiness_path,
        "revision_dossier_path": review.revision_dossier_path,
        "publication_evidence_index_path": review.publication_evidence_index_path,
        "artifact_integrity_audit_path": review.artifact_integrity_audit_path,
        "publication_repair_plan_path": review.publication_repair_plan_path,
        "publication_repair_execution_path": review.publication_repair_execution_path,
        "review_round": review_loop.current_round if review_loop is not None else 0,
        "review_fingerprint": (
            review_loop.latest_review_fingerprint
            if review_loop is not None
            else None
        ),
        "source_bundle_id": bundle.id,
        "status": status,
        "review_bundle_ready": review_bundle_ready,
        "final_publish_ready": final_publish_ready,
        "publication_tier": (
            review.publication_readiness.tier
            if review.publication_readiness is not None
            else "exploratory"
        ),
        "publication_readiness_score": (
            review.publication_readiness.score
            if review.publication_readiness is not None
            else 0
        ),
        "completeness_status": completeness_status,
        "blockers": blockers,
        "final_blockers": final_blockers,
        "revision_actions": revision_actions,
        "required_assets": _publish_asset_fingerprint_payload(required_assets),
        "final_required_asset_ids": [asset.asset_id for asset in final_required_assets],
        "optional_assets": _publish_asset_fingerprint_payload(optional_assets),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_publish_archive_manifest(project_id: str, run_id: str) -> dict[str, object] | None:
    path = _publish_archive_manifest_path(project_id, run_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _archive_manifest_generated_at(archive_manifest: dict[str, object] | None) -> datetime | None:
    if archive_manifest is None:
        return None
    value = archive_manifest.get("generated_at")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _load_publication_manifest(project_id: str, run_id: str) -> AutoResearchPublicationManifestRead | None:
    path = _publication_manifest_path(project_id, run_id)
    if not path.is_file():
        return None
    try:
        return AutoResearchPublicationManifestRead.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _file_sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _paper_title(run: AutoResearchRunRead) -> str:
    markdown = _paper_markdown(run)
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or run.topic
        return stripped[:160]
    if run.artifact is not None and run.artifact.best_system:
        return f"{run.topic}: {run.artifact.best_system}"
    return run.topic


def _paper_summary(run: AutoResearchRunRead) -> str | None:
    markdown = _paper_markdown(run)
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    body_lines = [line for line in lines if not line.startswith("#")]
    summary = " ".join(body_lines[:2]).strip()
    return summary[:280] if summary else None


def _project_title(project_id: str) -> str | None:
    db = db_module.SessionLocal()
    try:
        project = get_project(db, project_id)
        return project.title if project is not None else None
    finally:
        db.close()


def _bundle_assets_for_code_package(
    package: AutoResearchPublishPackageRead,
) -> list[AutoResearchBundleAssetRead]:
    code_assets: list[AutoResearchBundleAssetRead] = []
    seen_asset_ids: set[str] = set()
    for asset in [*package.required_assets, *package.optional_assets]:
        if asset.role not in _CODE_PACKAGE_INCLUDED_ROLES or not asset.ref.exists:
            continue
        if asset.asset_id in seen_asset_ids:
            continue
        seen_asset_ids.add(asset.asset_id)
        code_assets.append(asset)
    return code_assets


def _export_code_package(
    *,
    project_id: str,
    run_id: str,
    package: AutoResearchPublishPackageRead,
) -> Path:
    archive_path = _code_package_path(project_id, run_id)
    run_root = run_dir(project_id, run_id)
    added: set[str] = set()
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as handle:
        for asset in _bundle_assets_for_code_package(package):
            _add_path_to_zip(handle, run_root=run_root, path=Path(asset.ref.path), added=added)
    return archive_path


def _publish_generated_paths(project_id: str, run_id: str) -> list[Path]:
    return [
        _review_path(project_id, run_id),
        _review_loop_path(project_id, run_id),
        Path(publication_evidence_index_file_path(project_id, run_id)),
        Path(artifact_integrity_audit_file_path(project_id, run_id)),
        Path(publication_repair_plan_file_path(project_id, run_id)),
        Path(publication_repair_execution_file_path(project_id, run_id)),
        _publish_manifest_path(project_id, run_id),
        _publish_archive_manifest_path(project_id, run_id),
        _publication_manifest_path(project_id, run_id),
        _code_package_path(project_id, run_id),
    ]


def _updated_deployments(
    existing: list[AutoResearchDeploymentRefRead],
    new_ref: AutoResearchDeploymentRefRead,
) -> list[AutoResearchDeploymentRefRead]:
    preserved = [item for item in existing if item.deployment_id != new_ref.deployment_id]
    preserved.append(new_ref)
    preserved.sort(key=lambda item: item.listed_at, reverse=True)
    return preserved


def _paper_compile_output_paths(run: AutoResearchRunRead) -> list[str]:
    report = run.paper_compile_report
    paper_sources_dir = Path(run.paper_sources_dir or (run_dir(run.project_id, run.id) / "paper_sources"))
    candidates = []
    if report is not None:
        candidates.extend(report.materialized_outputs)
    candidates.extend([PAPER_COMPILED_PDF_FILENAME, PAPER_BIBLIOGRAPHY_OUTPUT_FILENAME])
    outputs: list[str] = []
    seen: set[str] = set()
    for relative_path in candidates:
        if relative_path in seen:
            continue
        seen.add(relative_path)
        path = paper_sources_dir / relative_path
        if path.is_file():
            outputs.append(str(path))
    return outputs


def _compiled_paper_path(run: AutoResearchRunRead) -> str | None:
    paper_sources_dir = Path(run.paper_sources_dir or (run_dir(run.project_id, run.id) / "paper_sources"))
    compiled_pdf = paper_sources_dir / PAPER_COMPILED_PDF_FILENAME
    if compiled_pdf.is_file():
        return str(compiled_pdf)
    return None


def build_publication_manifest(
    project_id: str,
    run_id: str,
    *,
    deployment_id: str | None = None,
    deployment_label: str | None = None,
) -> AutoResearchPublicationManifestRead | None:
    run = load_run(project_id, run_id)
    package = build_publish_package(project_id, run_id)
    if (
        run is None
        or package is None
        or not package.final_publish_ready
        or not package.archive_ready
        or not package.archive_current
    ):
        return None
    manifest_path = _publication_manifest_path(project_id, run_id)
    existing = _load_publication_manifest(project_id, run_id)
    if deployment_id is None and deployment_label is None:
        deployments = (
            list(existing.deployments)
            if existing is not None
            else [_deployment_ref(deployment_id=None, deployment_label=None)]
        )
    else:
        deployments = _updated_deployments(
            existing.deployments if existing is not None else [],
            _deployment_ref(
                deployment_id=deployment_id,
                deployment_label=deployment_label,
            ),
        )
    code_package_path = _export_code_package(
        project_id=project_id,
        run_id=run_id,
        package=package,
    )
    compiled_paper_path = _compiled_paper_path(run)
    paper_compile_output_paths = _paper_compile_output_paths(run)
    benchmark_card_path = (
        Path(package.benchmark_card_path)
        if package.benchmark_card_path
        else Path(benchmark_card_file_path(project_id, run_id))
    )
    benchmark_card_path_value = (
        str(benchmark_card_path) if benchmark_card_path.is_file() else package.benchmark_card_path
    )
    protocol_path = (
        Path(package.research_protocol_path)
        if package.research_protocol_path
        else Path(research_protocol_file_path(project_id, run_id))
    )
    protocol_path_value = str(protocol_path) if protocol_path.is_file() else package.research_protocol_path
    audit_path = (
        Path(package.methodology_audit_path)
        if package.methodology_audit_path
        else Path(methodology_audit_file_path(project_id, run_id))
    )
    audit_path_value = str(audit_path) if audit_path.is_file() else package.methodology_audit_path
    readiness_path = (
        Path(package.publication_readiness_path)
        if package.publication_readiness_path
        else Path(publication_readiness_file_path(project_id, run_id))
    )
    readiness_path_value = str(readiness_path) if readiness_path.is_file() else package.publication_readiness_path
    dossier_path = (
        Path(package.revision_dossier_path)
        if package.revision_dossier_path
        else Path(revision_dossier_file_path(project_id, run_id))
    )
    dossier_path_value = str(dossier_path) if dossier_path.is_file() else package.revision_dossier_path
    evidence_index_path = (
        Path(package.publication_evidence_index_path)
        if package.publication_evidence_index_path
        else Path(publication_evidence_index_file_path(project_id, run_id))
    )
    evidence_index_path_value = (
        str(evidence_index_path)
        if evidence_index_path.is_file()
        else package.publication_evidence_index_path
    )
    artifact_integrity_audit_path = (
        Path(package.artifact_integrity_audit_path)
        if package.artifact_integrity_audit_path
        else Path(artifact_integrity_audit_file_path(project_id, run_id))
    )
    artifact_integrity_audit_path_value = (
        str(artifact_integrity_audit_path)
        if artifact_integrity_audit_path.is_file()
        else package.artifact_integrity_audit_path
    )
    repair_plan_path = (
        Path(package.publication_repair_plan_path)
        if package.publication_repair_plan_path
        else Path(publication_repair_plan_file_path(project_id, run_id))
    )
    repair_plan_path_value = (
        str(repair_plan_path) if repair_plan_path.is_file() else package.publication_repair_plan_path
    )
    repair_execution_path = (
        Path(package.publication_repair_execution_path)
        if package.publication_repair_execution_path
        else Path(publication_repair_execution_file_path(project_id, run_id))
    )
    repair_execution_path_value = (
        str(repair_execution_path)
        if repair_execution_path.is_file()
        else package.publication_repair_execution_path
    )

    publication = AutoResearchPublicationManifestRead(
        publication_id=f"publication_{run_id}",
        project_id=project_id,
        project_title=_project_title(project_id),
        run_id=run_id,
        topic=run.topic,
        paper_title=_paper_title(run),
        paper_summary=_paper_summary(run),
        generated_at=existing.generated_at if existing is not None else _utcnow(),
        updated_at=_utcnow(),
        selected_candidate_id=package.selected_candidate_id,
        benchmark_name=run.spec.benchmark_name if run.spec is not None else run.program.benchmark_name if run.program is not None else None,
        task_family=run.task_family,
        package_id=package.package_id,
        package_fingerprint=package.package_fingerprint,
        bundle_kind=_archive_bundle_kind(package),
        review_bundle_ready=package.review_bundle_ready,
        final_publish_ready=package.final_publish_ready,
        publication_tier=package.publication_tier,
        publication_readiness_score=package.publication_readiness_score,
        benchmark_card_path=benchmark_card_path_value,
        benchmark_card_sha256=_file_sha256(benchmark_card_path),
        research_protocol_path=protocol_path_value,
        research_protocol_sha256=_file_sha256(protocol_path),
        methodology_audit_path=audit_path_value,
        methodology_audit_sha256=_file_sha256(audit_path),
        publication_readiness_path=readiness_path_value,
        publication_readiness_sha256=_file_sha256(readiness_path),
        revision_dossier_path=dossier_path_value,
        revision_dossier_sha256=_file_sha256(dossier_path),
        publication_evidence_index_path=evidence_index_path_value,
        publication_evidence_index_sha256=_file_sha256(evidence_index_path),
        artifact_integrity_audit_path=artifact_integrity_audit_path_value,
        artifact_integrity_audit_sha256=_file_sha256(artifact_integrity_audit_path),
        publication_repair_plan_path=repair_plan_path_value,
        publication_repair_plan_sha256=_file_sha256(repair_plan_path),
        publication_repair_execution_path=repair_execution_path_value,
        publication_repair_execution_sha256=_file_sha256(repair_execution_path),
        archive_ready=package.archive_ready,
        archive_current=package.archive_current,
        review_round=package.review_round,
        review_fingerprint=package.review_fingerprint,
        publication_manifest_path=str(manifest_path),
        publish_manifest_path=package.manifest_path or str(_publish_manifest_path(project_id, run_id)),
        publish_archive_path=package.archive_path or str(_publish_archive_path(project_id, run_id)),
        paper_path=run.paper_path or str(run_dir(project_id, run_id) / "paper.md"),
        compiled_paper_path=compiled_paper_path,
        compiled_paper_sha256=_file_sha256(Path(compiled_paper_path)) if compiled_paper_path is not None else None,
        paper_compile_output_paths=paper_compile_output_paths,
        code_package_path=str(code_package_path),
        code_package_sha256=_file_sha256(code_package_path),
        run_api_path=f"/api/projects/{project_id}/auto-research/{run_id}",
        registry_api_path=f"/api/projects/{project_id}/auto-research/{run_id}/registry",
        publish_api_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish",
        publish_download_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish/download",
        paper_download_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish/paper/download",
        compiled_paper_download_path=(
            f"/api/projects/{project_id}/auto-research/{run_id}/publish/paper/compiled/download"
            if compiled_paper_path is not None
            else None
        ),
        code_package_download_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish/code/download",
        deployments=deployments,
    )
    _write_json(manifest_path, publication.model_dump(mode="json"))
    return publication


def build_publish_package(project_id: str, run_id: str) -> AutoResearchPublishPackageRead | None:
    review = build_run_review(project_id, run_id)
    bundle_index = load_run_bundle_index(project_id, run_id)
    run = load_run(project_id, run_id)
    if review is None or bundle_index is None or run is None:
        return None
    review_loop = _load_review_loop(project_id, run_id)
    if review_loop is None:
        review_loop = _build_review_loop(
            project_id=project_id,
            run_id=run_id,
            review=review,
            run=run,
            paper_markdown=_paper_markdown(run),
        )

    bundle = _selected_bundle(bundle_index)
    if bundle is None:
        return None

    required_assets = [item for item in bundle.assets if item.required]
    final_required_assets = _final_required_assets(bundle)
    optional_assets = [item for item in bundle.assets if not item.required]
    missing_required_assets = [item for item in required_assets if not item.ref.exists]
    missing_final_assets = [item for item in final_required_assets if not item.ref.exists]
    blockers = [item.summary for item in review.findings if item.severity == "error"]
    repair_state_final_blockers = _repair_state_final_blockers(review)
    semantic_final_blockers = [
        *_semantic_final_publish_blockers(review),
        *repair_state_final_blockers,
    ]
    compile_final_blockers = _compile_ready_final_blockers(run)
    evidence_index_final_blockers = (
        review.publication_evidence_index.blockers
        if review.publication_evidence_index is not None
        else ["Final publish requires a publication evidence index."]
    )
    status_semantic_blockers = [
        item
        for item in semantic_final_blockers
        if item.startswith("Final publish requires citation-grounded")
        or item.startswith("Final publish requires tighter research framing")
        or item.startswith("Final publish requires supported claim-evidence")
    ]
    if semantic_final_blockers and not missing_final_assets and not compile_final_blockers:
        status_semantic_blockers = semantic_final_blockers
    review_loop_requirements = (
        _review_loop_revision_requirements(review_loop)
        if review.overall_status != "ready"
        else []
    )
    final_blockers = [
        *semantic_final_blockers,
        *compile_final_blockers,
        *evidence_index_final_blockers,
        *review_loop_requirements,
        *(f"Missing final publish asset: {item.role}" for item in missing_final_assets),
    ]
    review_bundle_ready = not missing_required_assets
    final_publish_ready = (
        review.overall_status == "ready"
        and not missing_final_assets
        and not semantic_final_blockers
        and not compile_final_blockers
        and not evidence_index_final_blockers
        and not review_loop_requirements
    )
    completeness_status = "complete" if not missing_final_assets else "incomplete"
    status = (
        "blocked"
        if blockers or status_semantic_blockers or not review_bundle_ready
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
        publication_tier=(
            review.publication_readiness.tier
            if review.publication_readiness is not None
            else "exploratory"
        ),
        publication_readiness_score=(
            review.publication_readiness.score
            if review.publication_readiness is not None
            else 0
        ),
        benchmark_card_path=review.benchmark_card_path,
        research_protocol_path=review.research_protocol_path,
        methodology_audit_path=review.methodology_audit_path,
        revision_dossier_path=review.revision_dossier_path,
        publication_evidence_index_path=review.publication_evidence_index_path,
        artifact_integrity_audit_path=review.artifact_integrity_audit_path,
        publication_repair_plan_path=review.publication_repair_plan_path,
        publication_repair_execution_path=(
            str(Path(publication_repair_execution_file_path(project_id, run_id)))
            if Path(publication_repair_execution_file_path(project_id, run_id)).is_file()
            else review.publication_repair_execution_path
        ),
        publication_readiness_path=review.publication_readiness_path,
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
        revision_count=review_loop.pending_action_count if review_loop is not None else len(review.revision_plan),
        blockers=blockers,
        final_blockers=final_blockers,
        revision_actions=[],
        required_assets=required_assets,
        final_required_assets=final_required_assets,
        optional_assets=optional_assets,
    )
    revision_actions = (
        list(review_loop.pending_revision_actions)
        if review_loop is not None
        else [item.title for item in review.revision_plan]
    )
    package_fingerprint = _publish_package_fingerprint(
        review=review,
        review_loop=review_loop,
        bundle=bundle,
        required_assets=required_assets,
        final_required_assets=final_required_assets,
        optional_assets=optional_assets,
        blockers=blockers,
        final_blockers=final_blockers,
        revision_actions=revision_actions,
        review_bundle_ready=review_bundle_ready,
        final_publish_ready=final_publish_ready,
        completeness_status=completeness_status,
        status=status,
    )
    archive_manifest = _load_publish_archive_manifest(project_id, run_id)
    publication_manifest = _load_publication_manifest(project_id, run_id)
    archive_path = _publish_archive_path(project_id, run_id)
    archive_ready = archive_manifest is not None and archive_path.is_file()
    archive_current = (
        archive_ready
        and archive_manifest.get("package_fingerprint") == package_fingerprint
    )
    archive_status = "current" if archive_current else "stale" if archive_ready else "missing"
    package = package.model_copy(
        update={
            "archive_manifest_path": str(_publish_archive_manifest_path(project_id, run_id)),
            "package_fingerprint": package_fingerprint,
            "review_round": review_loop.current_round if review_loop is not None else 0,
            "review_fingerprint": (
                review_loop.latest_review_fingerprint
                if review_loop is not None
                else None
            ),
            "archive_status": archive_status,
            "archive_ready": archive_ready,
            "archive_current": archive_current,
            "archive_generated_at": _archive_manifest_generated_at(archive_manifest),
            "archive_bundle_kind": archive_manifest.get("bundle_kind") if archive_manifest is not None else None,
            "archive_review_round": archive_manifest.get("review_round") if archive_manifest is not None else None,
            "archive_review_fingerprint": (
                archive_manifest.get("review_fingerprint")
                if archive_manifest is not None
                else None
            ),
            "publication_id": publication_manifest.publication_id if publication_manifest is not None else None,
            "publication_manifest_path": (
                publication_manifest.publication_manifest_path
                if publication_manifest is not None
                else str(_publication_manifest_path(project_id, run_id))
            ),
            "code_package_path": (
                publication_manifest.code_package_path if publication_manifest is not None else str(_code_package_path(project_id, run_id))
            ),
            "deployment_ids": (
                [item.deployment_id for item in publication_manifest.deployments]
                if publication_manifest is not None
                else []
            ),
            "revision_actions": revision_actions,
        }
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


def _write_publish_archive(
    *,
    project_id: str,
    run_id: str,
    archive_path: Path,
    bundle: AutoResearchBundleRead,
) -> None:
    run_root = run_dir(project_id, run_id)
    added: set[str] = set()
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as handle:
        for generated_path in _publish_generated_paths(project_id, run_id):
            if generated_path.is_file():
                handle.write(generated_path, arcname=generated_path.name)
                added.add(generated_path.name)
        for asset in bundle.assets:
            if not asset.ref.exists:
                continue
            _add_path_to_zip(handle, run_root=run_root, path=Path(asset.ref.path), added=added)


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
        "package_fingerprint": package.package_fingerprint,
        "review_round": package.review_round,
        "review_fingerprint": package.review_fingerprint,
        "review_bundle_ready": package.review_bundle_ready,
        "final_publish_ready": package.final_publish_ready,
        "publication_tier": package.publication_tier,
        "publication_readiness_score": package.publication_readiness_score,
        "completeness_status": package.completeness_status,
        "selected_candidate_id": package.selected_candidate_id,
        "source_bundle_id": package.source_bundle_id,
        "archive_file_name": PUBLISH_ARCHIVE_FILENAME,
        "generated_files": [
            REVIEW_FILENAME,
            REVIEW_LOOP_FILENAME,
            BENCHMARK_CARD_FILENAME,
            RESEARCH_PROTOCOL_FILENAME,
            METHODOLOGY_AUDIT_FILENAME,
            PUBLICATION_READINESS_FILENAME,
            REVISION_DOSSIER_FILENAME,
            PUBLICATION_EVIDENCE_INDEX_FILENAME,
            ARTIFACT_INTEGRITY_AUDIT_FILENAME,
            PUBLICATION_REPAIR_PLAN_FILENAME,
            PUBLICATION_REPAIR_EXECUTION_FILENAME,
            PUBLISH_PACKAGE_FILENAME,
            PUBLISH_ARCHIVE_MANIFEST_FILENAME,
            PUBLICATION_MANIFEST_FILENAME,
            CODE_PACKAGE_FILENAME,
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


def export_publish_package(
    project_id: str,
    run_id: str,
    *,
    deployment_id: str | None = None,
    deployment_label: str | None = None,
) -> AutoResearchPublishExportRead | None:
    package = build_publish_package(project_id, run_id)
    bundle_index = load_run_bundle_index(project_id, run_id)
    if package is None or bundle_index is None:
        return None
    if not package.final_publish_ready:
        raise ValueError(
            "Auto research run is not final publish ready; resolve review and citation blockers before export"
        )

    bundle = _selected_bundle(bundle_index)
    if bundle is None:
        return None

    archive_path = _publish_archive_path(project_id, run_id)
    archive_manifest_path = _publish_archive_manifest_path(project_id, run_id)
    archive_manifest = _archive_manifest(
        project_id=project_id,
        run_id=run_id,
        package=package,
    )
    _write_json(archive_manifest_path, archive_manifest)
    _write_publish_archive(
        project_id=project_id,
        run_id=run_id,
        archive_path=archive_path,
        bundle=bundle,
    )

    code_package_path = _export_code_package(project_id=project_id, run_id=run_id, package=package)
    publication_manifest = build_publication_manifest(
        project_id,
        run_id,
        deployment_id=deployment_id,
        deployment_label=deployment_label,
    )
    package = package.model_copy(update={"archive_path": str(archive_path)})
    package = package.model_copy(
        update={
            "archive_manifest_path": str(archive_manifest_path),
            "archive_status": "current",
            "archive_ready": archive_path.is_file() and archive_manifest_path.is_file(),
            "archive_current": archive_path.is_file() and archive_manifest_path.is_file(),
            "archive_generated_at": _archive_manifest_generated_at(archive_manifest),
            "archive_bundle_kind": archive_manifest["bundle_kind"],
            "archive_review_round": archive_manifest["review_round"],
            "archive_review_fingerprint": archive_manifest["review_fingerprint"],
            "publication_id": (
                publication_manifest.publication_id if publication_manifest is not None else None
            ),
            "publication_manifest_path": (
                publication_manifest.publication_manifest_path
                if publication_manifest is not None
                else str(_publication_manifest_path(project_id, run_id))
            ),
            "code_package_path": str(code_package_path),
            "deployment_ids": (
                [item.deployment_id for item in publication_manifest.deployments]
                if publication_manifest is not None
                else []
            ),
        }
    )
    _write_json(_publish_manifest_path(project_id, run_id), package.model_dump(mode="json"))
    _write_publish_archive(
        project_id=project_id,
        run_id=run_id,
        archive_path=archive_path,
        bundle=bundle,
    )
    deployment = publication_manifest.deployments[0] if publication_manifest is not None and publication_manifest.deployments else None
    return AutoResearchPublishExportRead(
        project_id=project_id,
        run_id=run_id,
        package_id=package.package_id,
        generated_at=_utcnow(),
        publication_id=publication_manifest.publication_id if publication_manifest is not None else None,
        publication_manifest_path=(
            publication_manifest.publication_manifest_path
            if publication_manifest is not None
            else str(_publication_manifest_path(project_id, run_id))
        ),
        deployment_id=deployment.deployment_id if deployment is not None else None,
        deployment_label=deployment.label if deployment is not None else None,
        bundle_kind=_archive_bundle_kind(package),
        review_bundle_ready=package.review_bundle_ready,
        final_publish_ready=package.final_publish_ready,
        file_name=archive_path.name,
        archive_path=str(archive_path),
        archive_manifest_path=str(archive_manifest_path),
        code_package_path=str(code_package_path),
        code_package_download_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish/code/download",
        package_fingerprint=package.package_fingerprint,
        review_round=package.review_round,
        review_fingerprint=package.review_fingerprint,
        download_path=f"/api/projects/{project_id}/auto-research/{run_id}/publish/download",
        asset_count=package.asset_count,
        included_asset_count=int(archive_manifest["included_asset_count"]),
        omitted_asset_count=int(archive_manifest["omitted_asset_count"]),
        download_ready=archive_path.is_file(),
    )


def get_publish_archive_path(project_id: str, run_id: str) -> Path:
    return _publish_archive_path(project_id, run_id)
