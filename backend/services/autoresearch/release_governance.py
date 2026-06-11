from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from schemas.autoresearch import (
    AutoResearchComplianceChecklistItemRead,
    AutoResearchComplianceChecklistRead,
    AutoResearchComplianceChecklistRequest,
    AutoResearchHumanReviewRecordRead,
    AutoResearchHumanReviewRequest,
    AutoResearchReleaseExportRead,
    AutoResearchReleaseFileManifestEntryRead,
    AutoResearchReleaseFinality,
    AutoResearchReleaseHashManifestRead,
    AutoResearchReleasePackageRead,
    AutoResearchReleaseReadinessRead,
    AutoResearchReleaseRequest,
    AutoResearchReleaseType,
    AutoResearchVenueProfileRead,
    AutoResearchVenueProfileRequest,
)
from services.autoresearch.repository import (
    compliance_checklist_file_path,
    human_review_file_path,
    load_compliance_checklist,
    load_human_review_record,
    load_release_package,
    load_run,
    load_venue_profile,
    release_archive_file_path,
    release_archive_manifest_file_path,
    release_package_file_path,
    run_dir,
    save_compliance_checklist,
    save_human_review_record,
    save_release_package,
    save_venue_profile,
    venue_adapter_file_path,
)
from services.autoresearch.review_publish import (
    build_publish_package,
    get_publish_archive_path,
)


POLICY_VERSION = "release_governance_v1"
_NON_FINAL_LABEL = "NON_FINAL_REVIEW_EXPORT"
_FINAL_LABEL = "FINAL_PUBLISH_RELEASE"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _dedupe(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary_path.write_text(encoded, encoding="utf-8")
    temporary_path.replace(path)


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _path_if_file(value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    return str(path) if path.is_file() else None


def _publish_related_refs(project_id: str, run_id: str) -> list[str]:
    package = build_publish_package(project_id, run_id)
    if package is None:
        return []
    return _dedupe(
        [
            package.manifest_path,
            package.archive_manifest_path,
            package.publication_manifest_path,
            package.benchmark_card_path,
            package.research_protocol_path,
            package.methodology_audit_path,
            package.publication_readiness_path,
            package.experiment_design_path,
            package.failure_analysis_path,
            package.research_replan_path,
            package.contribution_assessment_path,
            package.literature_graph_path,
            package.novelty_validation_path,
            package.revision_dossier_path,
            package.publication_evidence_index_path,
            package.artifact_integrity_audit_path,
            package.reviewer_simulation_path,
            package.publication_repair_plan_path,
            package.publication_repair_execution_path,
            package.submission_manifest_path,
            package.reproducibility_checklist_path,
            package.reviewer_response_path,
            package.claim_evidence_index_path,
            package.lineage_archive_path,
            package.code_package_path,
        ]
    )


def _artifact_fingerprints(refs: list[str]) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for ref in refs:
        digest = _file_sha256(Path(ref))
        if digest is not None:
            fingerprints[ref] = digest
    return fingerprints


def record_human_review(
    project_id: str,
    run_id: str,
    request: AutoResearchHumanReviewRequest,
) -> AutoResearchHumanReviewRecordRead | None:
    run = load_run(project_id, run_id)
    package = build_publish_package(project_id, run_id)
    if run is None or package is None:
        return None
    reviewed_refs = _dedupe(request.reviewed_artifact_refs or _publish_related_refs(project_id, run_id))
    if package.manifest_path and package.manifest_path not in reviewed_refs:
        reviewed_refs.append(package.manifest_path)
    record = AutoResearchHumanReviewRecordRead(
        review_id=f"human_review:{project_id}:{run_id}",
        project_id=project_id,
        run_id=run_id,
        reviewer_id=request.reviewer_id,
        reviewer_role=request.reviewer_role,
        decision=request.decision,
        comments=request.comments,
        requested_changes=request.requested_changes,
        policy_exceptions=request.policy_exceptions,
        conflict_notes=request.conflict_notes,
        reviewed_artifact_refs=reviewed_refs,
        reviewed_artifact_fingerprints=_artifact_fingerprints(reviewed_refs),
        final_decision_linkage=(
            request.final_decision_linkage
            or f"publish_package:{package.package_fingerprint}:final_publish_ready={package.final_publish_ready}"
        ),
        timestamp=_utcnow(),
        review_path=human_review_file_path(project_id, run_id),
    )
    return save_human_review_record(record)


def get_human_review(project_id: str, run_id: str) -> AutoResearchHumanReviewRecordRead | None:
    return load_human_review_record(project_id, run_id)


_COMPLIANCE_ITEMS: tuple[tuple[str, str], ...] = (
    ("dataset_license", "Dataset license"),
    ("paper_source_license", "Paper/source license"),
    ("code_license", "Code license"),
    ("dependency_license", "Dependency license"),
    ("privacy_pii", "Privacy/PII"),
    ("model_api_terms", "Model/API terms"),
    ("paid_service_disclosure", "Paid service disclosure"),
    ("benchmark_terms", "Benchmark terms"),
    ("venue_policy", "Venue policy"),
    ("artifact_retention", "Artifact retention"),
    ("external_source_attribution", "External source attribution"),
    ("reproducibility_package_policy", "Reproducibility package policy"),
)


def _exception_for_item(
    item_id: str,
    exceptions: list[dict[str, object]],
) -> dict[str, object] | None:
    for exception in exceptions:
        exception_item_id = exception.get("item_id") or exception.get("check_id")
        if exception_item_id not in {item_id, "*"}:
            continue
        approved = exception.get("approved", True)
        scope = str(exception.get("scope") or exception.get("release_type") or "")
        if approved is False:
            continue
        if "internal" not in scope and scope not in {"internal_only", "non_final_internal"}:
            continue
        return exception
    return None


def _default_compliance_source(
    *,
    project_id: str,
    run_id: str,
    item_id: str,
    source_overrides: dict[str, str],
) -> tuple[str, list[str], list[str], dict[str, object]]:
    override = source_overrides.get(item_id)
    if override:
        normalized = override.strip().lower()
        if normalized in {"not_applicable", "not applicable", "n/a", "na"}:
            return "not_applicable", [], [], {"override": override}
        return "pass", [override], [], {"override": override}

    package = build_publish_package(project_id, run_id)
    refs = _publish_related_refs(project_id, run_id)
    ref_by_name = {Path(ref).name: ref for ref in refs}
    if item_id == "paid_service_disclosure":
        return "pass", [package.manifest_path] if package and package.manifest_path else [], [], {
            "policy": "deterministic offline baseline does not require paid service use"
        }
    if item_id == "artifact_retention":
        lineage_ref = package.lineage_archive_path if package else None
        if _path_if_file(lineage_ref):
            return "pass", [lineage_ref], [], {"retention": "lineage archive present"}
    if item_id == "external_source_attribution":
        source_refs = _dedupe(
            [
                package.literature_graph_path if package else None,
                package.benchmark_card_path if package else None,
                ref_by_name.get("external_capability_manifest.json"),
            ]
        )
        if source_refs:
            return "pass", source_refs, [], {"attribution": "source manifests linked"}
    if item_id == "reproducibility_package_policy":
        reproducibility_ref = package.reproducibility_checklist_path if package else None
        if _path_if_file(reproducibility_ref):
            return "pass", [reproducibility_ref], [], {"reproducibility": "checklist present"}

    return (
        "fail",
        [],
        [f"Compliance item '{item_id}' requires an explicit source, manifest, or approved exception."],
        {},
    )


def build_compliance_checklist(
    project_id: str,
    run_id: str,
    request: AutoResearchComplianceChecklistRequest | None = None,
    *,
    persist: bool = True,
) -> AutoResearchComplianceChecklistRead | None:
    if load_run(project_id, run_id) is None or build_publish_package(project_id, run_id) is None:
        return None
    request = request or AutoResearchComplianceChecklistRequest()
    items: list[AutoResearchComplianceChecklistItemRead] = []
    for item_id, label in _COMPLIANCE_ITEMS:
        status, source_refs, blockers, details = _default_compliance_source(
            project_id=project_id,
            run_id=run_id,
            item_id=item_id,
            source_overrides=request.source_overrides,
        )
        exception = _exception_for_item(item_id, request.policy_exceptions)
        exception_scope = None
        if status == "fail" and exception is not None:
            status = "exception"
            blockers = []
            source_refs = _dedupe([*source_refs, str(exception.get("source_ref") or "")])
            exception_scope = str(exception.get("scope") or exception.get("release_type") or "internal_only")
            details = {**details, "exception": exception}
        items.append(
            AutoResearchComplianceChecklistItemRead(
                item_id=item_id,
                label=label,
                status=status,
                source_refs=source_refs,
                blockers=blockers,
                exception_scope=exception_scope,
                details=details,
            )
        )
    failed_required_items = [
        item
        for item in items
        if item.status == "fail" and (item.required_for_public_release or item.required_for_final_release)
    ]
    exception_items = [item for item in items if item.status == "exception"]
    passed = not failed_required_items and not exception_items
    internal_only_exception_allowed = (
        not failed_required_items
        and bool(exception_items)
        and all(item.exception_scope and "internal" in item.exception_scope for item in exception_items)
    )
    status = "passed" if passed else "exception" if internal_only_exception_allowed else "failed"
    checklist = AutoResearchComplianceChecklistRead(
        checklist_id=f"compliance:{project_id}:{run_id}",
        project_id=project_id,
        run_id=run_id,
        generated_at=_utcnow(),
        status=status,
        passed=passed,
        item_count=len(items),
        failed_required_count=len(failed_required_items),
        exception_count=len(exception_items),
        internal_only_exception_allowed=internal_only_exception_allowed,
        public_release_allowed=passed,
        final_release_allowed=passed,
        items=items,
        blockers=[blocker for item in failed_required_items for blocker in item.blockers],
        policy_exceptions=request.policy_exceptions,
        checklist_path=compliance_checklist_file_path(project_id, run_id),
    )
    return save_compliance_checklist(checklist) if persist else checklist


def get_or_build_compliance_checklist(
    project_id: str,
    run_id: str,
) -> AutoResearchComplianceChecklistRead | None:
    existing = load_compliance_checklist(project_id, run_id)
    if existing is not None:
        return existing
    return build_compliance_checklist(project_id, run_id)


def _venue_defaults(profile_kind: str) -> tuple[str, list[str], str]:
    if profile_kind == "conference":
        return "Conference Submission", ["paper.md", "code_package.zip", "reproducibility_checklist.md"], _FINAL_LABEL
    if profile_kind == "arxiv_preprint":
        return "arXiv Preprint", ["paper.md"], "NON_FINAL_PREPRINT_EXPORT"
    if profile_kind == "internal_report":
        return "Internal Report", ["publish_package.json", "lineage_archive.json"], "INTERNAL_NON_FINAL_EXPORT"
    if profile_kind == "custom":
        return "Custom Venue", ["publish_package.json"], _NON_FINAL_LABEL
    return "Workshop", ["paper.md", "claim_evidence_index.md"], "NON_FINAL_WORKSHOP_EXPORT"


def _run_file_candidates(project_id: str, run_id: str) -> dict[str, Path]:
    root = run_dir(project_id, run_id)
    candidates: dict[str, Path] = {}
    for child in root.rglob("*"):
        if child.is_file():
            candidates.setdefault(child.name, child)
            candidates.setdefault(child.relative_to(root).as_posix(), child)
    return candidates


def build_venue_profile(
    project_id: str,
    run_id: str,
    request: AutoResearchVenueProfileRequest | None = None,
    *,
    persist: bool = True,
) -> AutoResearchVenueProfileRead | None:
    if load_run(project_id, run_id) is None or build_publish_package(project_id, run_id) is None:
        return None
    request = request or AutoResearchVenueProfileRequest()
    default_name, default_files, default_label = _venue_defaults(request.profile_kind)
    required_files = request.required_files or default_files
    candidates = _run_file_candidates(project_id, run_id)
    missing = [file_name for file_name in required_files if file_name not in candidates]
    blockers = [f"Venue package is missing required file: {file_name}" for file_name in missing]
    if request.release_finality == "final" and not build_publish_package(project_id, run_id).final_publish_ready:
        blockers.append("Venue final profile cannot bypass failed scientific final publish gate.")
    label = request.final_non_final_label or (
        _FINAL_LABEL if request.release_finality == "final" else default_label
    )
    profile = AutoResearchVenueProfileRead(
        profile_id=f"venue:{project_id}:{run_id}:{request.profile_kind}",
        project_id=project_id,
        run_id=run_id,
        profile_kind=request.profile_kind,
        venue_name=request.venue_name or default_name,
        release_finality=request.release_finality,
        release_type=request.release_type,
        required_files=required_files,
        anonymity=request.anonymity,
        metadata={
            **request.metadata,
            "policy_version": POLICY_VERSION,
            "required_file_count": len(required_files),
        },
        supplemental_policy=request.supplemental_policy,
        page_limit=request.page_limit,
        artifact_naming=request.artifact_naming,
        final_non_final_label=label,
        compliance_requirements=request.compliance_requirements,
        missing_required_files=missing,
        blockers=blockers,
        warnings=[] if request.release_finality == "final" else ["Export is explicitly non-final."],
        valid=not blockers,
        generated_at=_utcnow(),
        venue_path=venue_adapter_file_path(project_id, run_id),
    )
    return save_venue_profile(profile) if persist else profile


def get_or_build_venue_profile(project_id: str, run_id: str) -> AutoResearchVenueProfileRead | None:
    existing = load_venue_profile(project_id, run_id)
    if existing is not None:
        return existing
    return build_venue_profile(project_id, run_id)


def _release_label(
    *,
    release_finality: AutoResearchReleaseFinality,
    non_final_label: str | None,
    venue: AutoResearchVenueProfileRead | None,
) -> str:
    if release_finality == "final":
        return _FINAL_LABEL
    return non_final_label or (venue.final_non_final_label if venue is not None else None) or _NON_FINAL_LABEL


def build_release_readiness(
    project_id: str,
    run_id: str,
    request: AutoResearchReleaseRequest | None = None,
) -> AutoResearchReleaseReadinessRead | None:
    package = build_publish_package(project_id, run_id)
    if load_run(project_id, run_id) is None or package is None:
        return None
    request = request or AutoResearchReleaseRequest()
    human_review = load_human_review_record(project_id, run_id)
    compliance = load_compliance_checklist(project_id, run_id) or build_compliance_checklist(project_id, run_id)
    venue = (
        build_venue_profile(project_id, run_id, request.venue_profile)
        if request.venue_profile is not None
        else get_or_build_venue_profile(project_id, run_id)
    )
    release_type = request.release_type
    release_finality = request.release_finality
    if venue is not None:
        release_type = request.release_type or venue.release_type
        release_finality = request.release_finality or venue.release_finality
    label = _release_label(
        release_finality=release_finality,
        non_final_label=request.non_final_label,
        venue=venue,
    )
    blockers: list[str] = []
    warnings: list[str] = []
    required_actions: list[str] = []
    if release_finality == "final" and not package.final_publish_ready:
        blockers.append("Final release is blocked because scientific final_publish_ready is false.")
        required_actions.append("resolve_scientific_final_gate")
    if release_finality == "non_final" and "NON_FINAL" not in label.upper():
        blockers.append("Non-final release requires an explicit non-final label.")
        required_actions.append("set_non_final_release_label")
    if human_review is None:
        blockers.append("Human review approval is required before release export.")
        required_actions.append("record_human_review")
    elif human_review.decision != "approved":
        blockers.append(f"Human review blocks release: {human_review.decision}.")
        required_actions.append("resolve_human_review_changes")
    if human_review is not None and human_review.requested_changes:
        blockers.extend(f"Human requested change: {item}" for item in human_review.requested_changes)
        required_actions.append("resolve_human_review_changes")
    compliance_passed = bool(compliance is not None and compliance.passed)
    if compliance is None:
        blockers.append("Compliance checklist is required before release export.")
        required_actions.append("build_compliance_checklist")
    elif release_finality == "final" and not compliance.passed:
        blockers.append("Final release requires a passed compliance checklist.")
        blockers.extend(compliance.blockers)
        required_actions.append("resolve_compliance_checklist")
    elif release_type == "public" and not compliance.passed:
        blockers.append("Public release requires a passed compliance checklist.")
        blockers.extend(compliance.blockers)
        required_actions.append("resolve_compliance_checklist")
    elif release_type == "internal_only" and not compliance.passed:
        if compliance.internal_only_exception_allowed:
            warnings.append("Compliance is incomplete but covered by scoped internal-only exceptions.")
        else:
            blockers.append("Internal-only non-final release requires scoped policy exceptions for incomplete compliance.")
            blockers.extend(compliance.blockers)
            required_actions.append("record_scoped_compliance_exception")
    if venue is None:
        blockers.append("Venue adapter profile is required before release export.")
        required_actions.append("build_venue_profile")
    elif not venue.valid:
        blockers.extend(venue.blockers)
        required_actions.append("repair_venue_package")
    if package.archive_ready and not package.archive_current:
        blockers.append("Publish archive is stale; rebuild publish artifacts before final release.")
        required_actions.append("export_publish")

    related_refs = _dedupe(
        [
            package.manifest_path,
            human_review.review_path if human_review is not None else None,
            compliance.checklist_path if compliance is not None else None,
            venue.venue_path if venue is not None else None,
            package.artifact_integrity_audit_path,
            package.lineage_archive_path,
        ]
    )
    ready = not blockers
    return AutoResearchReleaseReadinessRead(
        project_id=project_id,
        run_id=run_id,
        release_type=release_type,
        release_finality=release_finality,
        ready=ready,
        status="ready" if ready else "blocked",
        final_publish_ready=package.final_publish_ready,
        human_review_approved=bool(human_review is not None and human_review.decision == "approved"),
        compliance_passed=compliance_passed,
        venue_valid=bool(venue is not None and venue.valid),
        non_final_label=label if release_finality == "non_final" else None,
        blockers=_dedupe(blockers),
        warnings=_dedupe(warnings),
        required_actions=_dedupe(required_actions),
        related_refs=related_refs,
    )


def build_release_package(
    project_id: str,
    run_id: str,
    request: AutoResearchReleaseRequest | None = None,
    *,
    persist: bool = True,
) -> AutoResearchReleasePackageRead | None:
    package = build_publish_package(project_id, run_id)
    if load_run(project_id, run_id) is None or package is None:
        return None
    request = request or AutoResearchReleaseRequest()
    readiness = build_release_readiness(project_id, run_id, request)
    if readiness is None:
        return None
    human_review = load_human_review_record(project_id, run_id)
    compliance = load_compliance_checklist(project_id, run_id)
    venue = load_venue_profile(project_id, run_id)
    previous = load_release_package(project_id, run_id)
    source_refs = _dedupe(
        [
            f"publish_package:{package.package_fingerprint}",
            package.manifest_path,
            package.submission_manifest_path,
            package.claim_evidence_index_path,
            package.lineage_archive_path,
            package.reproducibility_checklist_path,
        ]
    )
    version = 1
    warnings = list(readiness.warnings)
    if previous is not None:
        version = previous.version
        if previous.source_package_refs != source_refs:
            version += 1
            warnings.append(request.version_reason or "Release source package changed; version incremented.")
    label = _release_label(
        release_finality=readiness.release_finality,
        non_final_label=request.non_final_label,
        venue=venue,
    )
    release = AutoResearchReleasePackageRead(
        release_id=f"release:{project_id}:{run_id}:v{version}",
        project_id=project_id,
        run_id=run_id,
        version=version,
        generated_at=_utcnow(),
        release_type=readiness.release_type,
        release_finality=readiness.release_finality,
        status="ready" if readiness.ready else "blocked",
        ready=readiness.ready,
        final_publish_ready=package.final_publish_ready,
        final_decision_ref=package.publication_readiness_path,
        human_review_ref=human_review.review_path if human_review is not None else None,
        compliance_ref=compliance.checklist_path if compliance is not None else None,
        venue_ref=venue.venue_path if venue is not None else None,
        publish_package_ref=package.manifest_path,
        publish_archive_ref=str(get_publish_archive_path(project_id, run_id))
        if package.archive_ready
        else None,
        artifact_integrity_audit_ref=package.artifact_integrity_audit_path,
        source_package_refs=source_refs,
        lineage_refs=_dedupe([package.lineage_archive_path, package.claim_evidence_index_path]),
        limitations=[
            *([] if package.final_publish_ready else ["Scientific final publish gate is not passed."]),
            *([] if readiness.release_finality == "final" else ["This release is non-final and must not be cited as final publish-ready."]),
        ],
        scientific_blockers=package.final_blockers,
        blockers=readiness.blockers,
        warnings=warnings,
        reproducibility_checklist_ref=package.reproducibility_checklist_path,
        release_label=label,
        package_path=release_package_file_path(project_id, run_id),
        archive_path=release_archive_file_path(project_id, run_id),
        archive_manifest_path=release_archive_manifest_file_path(project_id, run_id),
    )
    return save_release_package(release) if persist else release


def get_release_package(project_id: str, run_id: str) -> AutoResearchReleasePackageRead | None:
    existing = load_release_package(project_id, run_id)
    if existing is not None:
        return existing
    return build_release_package(project_id, run_id)


def _release_archive_sources(
    package: AutoResearchReleasePackageRead,
    *,
    include_publish_archive: bool,
) -> list[tuple[str, Path]]:
    refs = _dedupe(
        [
            package.package_path,
            package.human_review_ref,
            package.compliance_ref,
            package.venue_ref,
            package.publish_package_ref,
            package.final_decision_ref,
            package.artifact_integrity_audit_ref,
            package.reproducibility_checklist_ref,
            *package.lineage_refs,
            package.publish_archive_ref if include_publish_archive else None,
        ]
    )
    sources: list[tuple[str, Path]] = []
    used_names: set[str] = set()
    for ref in refs:
        path = Path(ref)
        if not path.is_file():
            continue
        name = path.name
        if name in used_names:
            name = f"{path.parent.name}_{path.name}"
        used_names.add(name)
        sources.append((name, path))
    return sources


def _hash_manifest_for_sources(
    sources: list[tuple[str, Path]],
) -> AutoResearchReleaseHashManifestRead:
    entries = [
        AutoResearchReleaseFileManifestEntryRead(
            name=name,
            path=str(path),
            size_bytes=path.stat().st_size,
            sha256=_file_sha256(path) or "",
            required=True,
        )
        for name, path in sources
    ]
    signature = _payload_sha256([entry.model_dump(mode="json") for entry in entries])
    return AutoResearchReleaseHashManifestRead(
        manifest_id="release_hash_manifest",
        generated_at=_utcnow(),
        entries=entries,
        entry_count=len(entries),
        signature=signature,
    )


def export_release_package(
    project_id: str,
    run_id: str,
    request: AutoResearchReleaseRequest | None = None,
) -> AutoResearchReleaseExportRead | None:
    request = request or AutoResearchReleaseRequest()
    release = build_release_package(project_id, run_id, request)
    if release is None:
        return None
    if not release.ready:
        raise ValueError("; ".join(release.blockers) or "Release package is blocked by governance policy.")
    archive_path = Path(release_archive_file_path(project_id, run_id))
    archive_manifest_path = Path(release_archive_manifest_file_path(project_id, run_id))
    package_path = Path(release_package_file_path(project_id, run_id))
    release = save_release_package(
        release.model_copy(
            update={
                "status": "exported",
                "archive_path": str(archive_path),
                "archive_manifest_path": str(archive_manifest_path),
            }
        )
    )
    sources = _release_archive_sources(
        release,
        include_publish_archive=request.include_publish_archive,
    )
    hash_manifest = _hash_manifest_for_sources(sources)
    archive_manifest = {
        "schema_version": "release_archive_manifest_v1",
        "project_id": project_id,
        "run_id": run_id,
        "release_id": release.release_id,
        "release_type": release.release_type,
        "release_finality": release.release_finality,
        "release_label": release.release_label,
        "final_publish_ready": release.final_publish_ready,
        "generated_at": _utcnow().isoformat(),
        "package_fingerprint": release.release_fingerprint,
        "hash_manifest": hash_manifest.model_dump(mode="json"),
        "blockers": release.blockers,
        "warnings": release.warnings,
        "memory_export_policy_summary": release.memory_export_policy_summary,
    }
    _write_json(archive_manifest_path, archive_manifest)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as handle:
        for name, path in sources:
            handle.write(path, arcname=name)
        handle.write(archive_manifest_path, arcname=archive_manifest_path.name)
    return AutoResearchReleaseExportRead(
        project_id=project_id,
        run_id=run_id,
        release_id=release.release_id,
        generated_at=_utcnow(),
        release_type=release.release_type,
        release_finality=release.release_finality,
        file_name=archive_path.name,
        archive_path=str(archive_path),
        archive_manifest_path=str(archive_manifest_path),
        package_path=str(package_path),
        package_fingerprint=release.release_fingerprint,
        signature=hash_manifest.signature,
        entry_count=hash_manifest.entry_count,
        download_path=f"/api/projects/{project_id}/auto-research/{run_id}/release/download",
        ready=archive_path.is_file(),
    )


def get_release_archive_path(project_id: str, run_id: str) -> Path:
    return Path(release_archive_file_path(project_id, run_id))
