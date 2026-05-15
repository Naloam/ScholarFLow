from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from schemas.autoresearch import (
    AutoResearchArtifactIntegrityAuditRead,
    AutoResearchArtifactIntegrityIssueRead,
    AutoResearchBundleAssetRead,
    AutoResearchBundleIndexRead,
    AutoResearchRegistryAssetRef,
    AutoResearchRunRegistryRead,
)


_SELF_AUDIT_ROLE = "run_artifact_integrity_audit_json"
_LINEAGE_REQUIRED_ROLE_KINDS = {
    "program_json": "program",
    "portfolio_json": "portfolio",
    "benchmark_json": "benchmark",
    "run_plan_json": "plan",
    "run_spec_json": "spec",
    "run_artifact_json": "artifact",
    "run_generated_code": "generated_code",
    "run_paper_markdown": "paper",
    "run_benchmark_card_json": "benchmark_card",
    "run_claim_evidence_matrix_json": "claim_evidence_matrix",
    "run_research_protocol_json": "research_protocol",
    "run_methodology_audit_json": "methodology_audit",
    "run_publication_readiness_json": "publication_readiness",
    "run_revision_dossier_json": "revision_dossier",
    "run_publication_evidence_index_json": "publication_evidence_index",
    "run_publication_repair_plan_json": "publication_repair_plan",
    "run_publication_repair_execution_json": "publication_repair_execution",
    "run_paper_compile_report_json": "paper_compile_report",
    "run_paper_build_script": "paper_build_script",
    "run_paper_latex_source": "paper_latex",
    "run_paper_bibliography_bib": "paper_bibliography",
    "run_paper_sources_manifest_json": "paper_sources_manifest",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:96] or "issue"


def _norm_path(value: str | None) -> str | None:
    if not value:
        return None
    return str(Path(value))


def _actual_exists(ref: AutoResearchRegistryAssetRef) -> bool:
    return Path(ref.path).exists()


def _iter_file_refs(
    registry: AutoResearchRunRegistryRead,
) -> Iterable[tuple[str, str, AutoResearchRegistryAssetRef]]:
    for field_name in registry.files.__class__.model_fields:
        ref = getattr(registry.files, field_name)
        if isinstance(ref, AutoResearchRegistryAssetRef):
            yield ("run", field_name, ref)
    for entry in registry.candidates:
        for field_name in entry.files.__class__.model_fields:
            ref = getattr(entry.files, field_name)
            if isinstance(ref, AutoResearchRegistryAssetRef):
                yield (entry.candidate_id, field_name, ref)


def _issue(
    *,
    severity: str,
    category: str,
    summary: str,
    detail: str,
    asset_id: str | None = None,
    role: str | None = None,
    path: str | None = None,
) -> AutoResearchArtifactIntegrityIssueRead:
    seed = "|".join([severity, category, summary, asset_id or "", role or "", path or ""])
    return AutoResearchArtifactIntegrityIssueRead(
        issue_id=f"{category}_{_slug(seed)}",
        severity=severity,
        category=category,
        summary=summary,
        detail=detail,
        asset_id=asset_id,
        role=role,
        path=path,
    )


def _selected_bundle(bundle_index: AutoResearchBundleIndexRead) -> object | None:
    return next((item for item in bundle_index.bundles if item.id == "selected_candidate_repro"), None)


def _duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _bundle_issues(
    *,
    registry: AutoResearchRunRegistryRead,
    bundle_index: AutoResearchBundleIndexRead,
    selected_assets: list[AutoResearchBundleAssetRead],
) -> list[AutoResearchArtifactIntegrityIssueRead]:
    issues: list[AutoResearchArtifactIntegrityIssueRead] = []
    selected_entries = [item for item in registry.candidates if item.selected]
    if registry.selected_candidate_id and len(selected_entries) != 1:
        issues.append(
            _issue(
                severity="error",
                category="identity",
                summary="Registry must identify exactly one selected candidate.",
                detail=(
                    f"selected_candidate_id={registry.selected_candidate_id}; "
                    f"selected entries={len(selected_entries)}."
                ),
            )
        )
    if selected_entries and selected_entries[0].candidate_id != registry.selected_candidate_id:
        issues.append(
            _issue(
                severity="error",
                category="identity",
                summary="Selected candidate entry does not match registry selection.",
                detail=(
                    f"entry={selected_entries[0].candidate_id}; "
                    f"registry={registry.selected_candidate_id}."
                ),
            )
        )
    selected_bundle = _selected_bundle(bundle_index)
    if selected_bundle is None:
        issues.append(
            _issue(
                severity="error",
                category="bundle",
                summary="Selected candidate reproducibility bundle is missing.",
                detail="The registry could not construct the selected_candidate_repro bundle.",
            )
        )
        return issues
    if selected_bundle.selected_candidate_id != registry.selected_candidate_id:
        issues.append(
            _issue(
                severity="error",
                category="bundle",
                summary="Selected bundle candidate identity does not match the registry.",
                detail=(
                    f"bundle={selected_bundle.selected_candidate_id}; "
                    f"registry={registry.selected_candidate_id}."
                ),
            )
        )
    for duplicate_id in _duplicate_values([asset.asset_id for asset in selected_assets]):
        issues.append(
            _issue(
                severity="error",
                category="bundle",
                summary="Selected bundle contains duplicate asset ids.",
                detail=f"Duplicate asset id: {duplicate_id}.",
                asset_id=duplicate_id,
            )
        )
    for asset in selected_assets:
        if asset.role == _SELF_AUDIT_ROLE:
            continue
        if asset.required and not asset.ref.exists:
            issues.append(
                _issue(
                    severity="error",
                    category="bundle",
                    summary="Selected bundle required asset is missing.",
                    detail=f"Required asset {asset.asset_id} ({asset.role}) is not materialized.",
                    asset_id=asset.asset_id,
                    role=asset.role,
                    path=asset.ref.path,
                )
            )
    return issues


def _registry_ref_issues(
    refs: list[tuple[str, str, AutoResearchRegistryAssetRef]],
) -> list[AutoResearchArtifactIntegrityIssueRead]:
    issues: list[AutoResearchArtifactIntegrityIssueRead] = []
    for owner_id, field_name, ref in refs:
        if field_name == "artifact_integrity_audit_json":
            continue
        actual_exists = _actual_exists(ref)
        if actual_exists != ref.exists:
            issues.append(
                _issue(
                    severity="error",
                    category="registry",
                    summary="Registry asset existence flag is stale.",
                    detail=(
                        f"{owner_id}.{field_name} records exists={ref.exists}, "
                        f"but the filesystem reports exists={actual_exists}."
                    ),
                    path=ref.path,
                )
            )
        candidate = Path(ref.path)
        if actual_exists and ref.kind == "file" and not candidate.is_file():
            issues.append(
                _issue(
                    severity="error",
                    category="registry",
                    summary="Registry asset kind does not match a file.",
                    detail=f"{owner_id}.{field_name} is registered as a file but is not a file.",
                    path=ref.path,
                )
            )
        if actual_exists and ref.kind == "directory" and not candidate.is_dir():
            issues.append(
                _issue(
                    severity="error",
                    category="registry",
                    summary="Registry asset kind does not match a directory.",
                    detail=f"{owner_id}.{field_name} is registered as a directory but is not a directory.",
                    path=ref.path,
                )
            )
        if actual_exists and ref.kind == "file" and not ref.sha256:
            issues.append(
                _issue(
                    severity="warning",
                    category="registry",
                    summary="Registry file asset is missing a checksum.",
                    detail=f"{owner_id}.{field_name} exists but has no sha256 recorded.",
                    path=ref.path,
                )
            )
    return issues


def _lineage_issues(
    *,
    registry: AutoResearchRunRegistryRead,
    selected_assets: list[AutoResearchBundleAssetRead],
) -> tuple[list[AutoResearchArtifactIntegrityIssueRead], int, int]:
    issues: list[AutoResearchArtifactIntegrityIssueRead] = []
    lineage_targets = {
        (_norm_path(edge.target_path), edge.target_kind)
        for edge in registry.lineage.edges
        if edge.target_path
    }
    missing_lineage_targets = 0
    for edge in registry.lineage.edges:
        if not edge.target_path:
            continue
        actual_exists = Path(edge.target_path).exists()
        if not actual_exists:
            missing_lineage_targets += 1
        if edge.exists is not None and edge.exists != actual_exists:
            issues.append(
                _issue(
                    severity="error",
                    category="lineage",
                    summary="Lineage edge existence flag is stale.",
                    detail=(
                        f"{edge.source_kind}:{edge.source_id} -> {edge.target_kind}:{edge.target_id} "
                        f"records exists={edge.exists}, but filesystem reports exists={actual_exists}."
                    ),
                    path=edge.target_path,
                )
            )
    untraced_existing = 0
    run_asset_prefix = f"{registry.run_id}:"
    for asset in selected_assets:
        if not asset.asset_id.startswith(run_asset_prefix):
            continue
        expected_kind = _LINEAGE_REQUIRED_ROLE_KINDS.get(asset.role)
        if expected_kind is None or not asset.ref.exists:
            continue
        if (_norm_path(asset.ref.path), expected_kind) in lineage_targets:
            continue
        untraced_existing += 1
        issues.append(
            _issue(
                severity="error",
                category="lineage",
                summary="Existing selected run asset is missing lineage.",
                detail=(
                    f"Asset {asset.asset_id} ({asset.role}) exists but no lineage edge "
                    f"targets its path as {expected_kind}."
                ),
                asset_id=asset.asset_id,
                role=asset.role,
                path=asset.ref.path,
            )
        )
    return issues, missing_lineage_targets, untraced_existing


def build_artifact_integrity_audit(
    *,
    registry: AutoResearchRunRegistryRead,
    bundle_index: AutoResearchBundleIndexRead,
) -> AutoResearchArtifactIntegrityAuditRead:
    refs = list(_iter_file_refs(registry))
    selected_bundle = _selected_bundle(bundle_index)
    selected_assets = list(selected_bundle.assets) if selected_bundle is not None else []
    issues = [
        *_bundle_issues(
            registry=registry,
            bundle_index=bundle_index,
            selected_assets=selected_assets,
        ),
        *_registry_ref_issues(refs),
    ]
    lineage_issues, missing_lineage_target_count, untraced_existing_asset_count = _lineage_issues(
        registry=registry,
        selected_assets=selected_assets,
    )
    issues.extend(lineage_issues)
    blocker_issues = [item for item in issues if item.severity == "error"]
    warning_issues = [item for item in issues if item.severity == "warning"]
    refs_without_self = [
        (owner_id, field_name, ref)
        for owner_id, field_name, ref in refs
        if field_name != "artifact_integrity_audit_json"
    ]
    selected_assets_without_self = [
        asset for asset in selected_assets if asset.role != _SELF_AUDIT_ROLE
    ]
    selected_missing_required = [
        asset
        for asset in selected_assets_without_self
        if asset.required and not asset.ref.exists
    ]
    payload = {
        "audit_id": "artifact_integrity_audit_v1",
        "project_id": registry.project_id,
        "run_id": registry.run_id,
        "selected_candidate_id": registry.selected_candidate_id,
        "registry_asset_count": len(refs_without_self),
        "existing_registry_asset_count": sum(1 for _owner, _field, ref in refs_without_self if ref.exists),
        "missing_registry_asset_count": sum(1 for _owner, _field, ref in refs_without_self if not ref.exists),
        "bundle_count": len(bundle_index.bundles),
        "selected_bundle_asset_count": len(selected_assets_without_self),
        "selected_bundle_missing_required_count": len(selected_missing_required),
        "lineage_edge_count": len(registry.lineage.edges),
        "missing_lineage_target_count": missing_lineage_target_count,
        "untraced_existing_asset_count": untraced_existing_asset_count,
        "issues": [item.model_dump(mode="json") for item in issues],
        "blockers": [item.summary for item in blocker_issues],
        "warnings": [item.summary for item in warning_issues],
        "complete": not blocker_issues,
    }
    return AutoResearchArtifactIntegrityAuditRead(
        generated_at=_utcnow(),
        issue_count=len(issues),
        blocker_count=len(blocker_issues),
        warning_count=len(warning_issues),
        audit_fingerprint=_fingerprint(payload),
        **payload,
    )
