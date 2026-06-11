from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Any

from config.settings import settings
from schemas.autoresearch import (
    AutoResearchExternalCapabilityId,
    AutoResearchExternalCapabilityManifestRead,
    AutoResearchExternalCapabilityRecordRead,
    AutoResearchExternalCapabilityState,
    AutoResearchOperatorActionPolicyRead,
)
from services.autoresearch.repository import (
    external_capability_manifest_file_path,
    list_research_briefs,
    list_runs,
    load_external_capability_manifest,
    save_external_capability_manifest,
)


GOAL10_EXTERNAL_CAPABILITY_POLICY_VERSION = "goal10_external_capability_policy_v1"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _dedupe(items: list[Any]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item is None:
            continue
        cleaned = " ".join(str(item).split()).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _approval_policy(reason: str, *, allowed: bool = False) -> AutoResearchOperatorActionPolicyRead:
    return AutoResearchOperatorActionPolicyRead(
        action="approve",
        allowed=allowed,
        reason=reason,
        blocker_code=None if allowed else "external_capability_approval_required",
        recoverable=True,
        required_next_action="approve",
        related_refs=["external_capability_manifest"],
    )


def _record(
    capability_id: AutoResearchExternalCapabilityId,
    *,
    checked_at: datetime,
    state: AutoResearchExternalCapabilityState,
    provider: str | None = None,
    source: str | None = None,
    config_source: str = "default_policy",
    approval_required: bool = False,
    budget_class: str = "free",
    sandbox_constraints: list[str] | None = None,
    known_blockers: list[str] | None = None,
    related_artifact_refs: list[str] | None = None,
    operator_action_policy: AutoResearchOperatorActionPolicyRead | None = None,
) -> AutoResearchExternalCapabilityRecordRead:
    return AutoResearchExternalCapabilityRecordRead(
        capability_id=capability_id,
        provider=provider,
        source=source,
        config_source=config_source,
        checked_at=checked_at,
        policy_version=GOAL10_EXTERNAL_CAPABILITY_POLICY_VERSION,
        approval_required=approval_required,
        budget_class=budget_class,  # type: ignore[arg-type]
        sandbox_constraints=sandbox_constraints or [],
        known_blockers=known_blockers or [],
        related_artifact_refs=related_artifact_refs or [],
        operator_action_policy=operator_action_policy,
        state=state,
    )


def _records_for_project(project_id: str, *, checked_at: datetime) -> list[AutoResearchExternalCapabilityRecordRead]:
    briefs = list_research_briefs(project_id)
    runs = list_runs(project_id)
    web_requested = any(getattr(brief, "allow_web", False) for brief in briefs)
    bridge_requested = any(
        run.request is not None and run.request.experiment_bridge is not None
        for run in runs
    )
    bounded_budget = any(
        run.request is not None
        and (run.request.candidate_execution_limit is not None or run.request.max_rounds != 3)
        for run in runs
    )
    network_allowed = _env_flag("SCHOLARFLOW_EXTERNAL_NETWORK_APPROVED")
    docker_declared = _env_flag("SCHOLARFLOW_DOCKER_AVAILABLE")
    bridge_declared = _env_flag("SCHOLARFLOW_BRIDGE_AVAILABLE") or bridge_requested
    live_literature_configured = bool(
        settings.semantic_scholar_api_key
        or settings.crossref_api_key
        or settings.arxiv_api_key
        or network_allowed
    )
    sandbox_prefixes = list(settings.sandbox_command_prefix)

    network_state: AutoResearchExternalCapabilityState
    network_blockers: list[str] = []
    if network_allowed:
        network_state = "ready"
    elif web_requested:
        network_state = "approval_required"
        network_blockers.append(
            "Live network literature or artifact access was requested, but external network approval is not recorded."
        )
    else:
        network_state = "disabled"
        network_blockers.append(
            "Live network access is disabled by default; cached and fixture paths remain deterministic."
        )

    literature_state: AutoResearchExternalCapabilityState = (
        "ready" if live_literature_configured or not web_requested else "approval_required"
    )
    literature_blockers = []
    if web_requested and not network_allowed:
        literature_blockers.append(
            "Live literature connectors require network approval; cached connector responses remain usable."
        )
    if not live_literature_configured:
        literature_blockers.append(
            "No live literature API key or network approval is configured; final claims must rely on cached/imported provenance only."
        )

    docker_state: AutoResearchExternalCapabilityState = "ready" if docker_declared else "unavailable"
    docker_blockers = [] if docker_declared else [
        "Docker execution is not declared available; no daemon probing is attempted in deterministic policy mode."
    ]

    bridge_state: AutoResearchExternalCapabilityState
    if bridge_declared:
        bridge_state = "approval_required" if bridge_requested else "ready"
    else:
        bridge_state = "not_configured"

    return [
        _record(
            "network",
            checked_at=checked_at,
            state=network_state,
            provider="external_network",
            source="operator_policy",
            config_source="SCHOLARFLOW_EXTERNAL_NETWORK_APPROVED",
            approval_required=network_state == "approval_required",
            budget_class="approval_required" if network_state == "approval_required" else "free",
            sandbox_constraints=["no live network calls in deterministic tests"],
            known_blockers=network_blockers,
            operator_action_policy=(
                _approval_policy("External network access requires explicit operator approval.")
                if network_state == "approval_required"
                else None
            ),
        ),
        _record(
            "literature_connectors",
            checked_at=checked_at,
            state=literature_state,
            provider="arxiv, semantic_scholar, crossref",
            source="cache_or_live_connector",
            config_source="SEMANTIC_SCHOLAR_API_KEY,CROSSREF_API_KEY,ARXIV_API_KEY,SCHOLARFLOW_EXTERNAL_NETWORK_APPROVED",
            approval_required=literature_state == "approval_required",
            budget_class="approval_required" if literature_state == "approval_required" else "bounded",
            sandbox_constraints=["cached responses are allowed", "live requests require approval"],
            known_blockers=literature_blockers,
            related_artifact_refs=["literature_scout_cache"],
        ),
        _record(
            "full_text_extraction",
            checked_at=checked_at,
            state="ready" if _env_flag("SCHOLARFLOW_FULL_TEXT_EXTRACTION_ENABLED") else "not_configured",
            provider="grobid_or_cached_full_text",
            source="cached_full_text",
            config_source="SCHOLARFLOW_FULL_TEXT_EXTRACTION_ENABLED,GROBID_URL",
            budget_class="bounded",
            sandbox_constraints=["cached full text may be parsed without live fetch"],
            known_blockers=[] if _env_flag("SCHOLARFLOW_FULL_TEXT_EXTRACTION_ENABLED") else [
                "Full-text extraction is not configured; metadata or cached excerpts keep novelty claims limited."
            ],
        ),
        _record(
            "citation_context_extraction",
            checked_at=checked_at,
            state="ready" if _env_flag("SCHOLARFLOW_CITATION_CONTEXT_ENABLED") else "not_configured",
            provider="cached_citation_context",
            source="cached_full_text",
            config_source="SCHOLARFLOW_CITATION_CONTEXT_ENABLED",
            budget_class="bounded",
            known_blockers=[] if _env_flag("SCHOLARFLOW_CITATION_CONTEXT_ENABLED") else [
                "Citation-context extraction is not configured; citation-context claims remain follow-up work."
            ],
        ),
        _record(
            "benchmark_dataset_ingestion",
            checked_at=checked_at,
            state="ready",
            provider="local_import_validator",
            source="benchmark_package_manifest_v1",
            config_source="repository_validation_contract",
            budget_class="free",
            sandbox_constraints=["local JSON package validation", "checksum and split/schema validation required"],
            related_artifact_refs=["benchmark.json", "benchmark_card.json"],
        ),
        _record(
            "local_command_execution",
            checked_at=checked_at,
            state="ready",
            provider="scholarflow_local_fixture",
            source="approved_command_allowlist",
            config_source="APPROVED_LOCAL_COMMAND,SANDBOX_COMMAND_PREFIX",
            budget_class="free",
            sandbox_constraints=_dedupe(
                [
                    "scholarflow experiment-execution local-fixture",
                    *sandbox_prefixes,
                    "no paid LLM, GPU, or live network in deterministic tests",
                ]
            ),
            related_artifact_refs=["experiment_execution_plan.json", "experiment_execution_result.json"],
        ),
        _record(
            "docker_execution",
            checked_at=checked_at,
            state=docker_state,
            provider="docker",
            source="declared_operator_capability",
            config_source="SCHOLARFLOW_DOCKER_AVAILABLE",
            budget_class="approval_required" if docker_declared else "blocked",
            sandbox_constraints=["Docker daemon availability is declarative; execution still needs typed runtime contract"],
            known_blockers=docker_blockers,
        ),
        _record(
            "bridge_execution",
            checked_at=checked_at,
            state=bridge_state,
            provider="manual_async_bridge",
            source="experiment_bridge_config",
            config_source="run.request.experiment_bridge,SCHOLARFLOW_BRIDGE_AVAILABLE",
            approval_required=bridge_state == "approval_required",
            budget_class="approval_required" if bridge_state == "approval_required" else "bounded",
            sandbox_constraints=["bridge imports must carry schema and provenance hashes"],
            known_blockers=[] if bridge_declared else [
                "No external bridge configuration is recorded."
            ],
            related_artifact_refs=["experiment_bridge", "experiment_execution_result.json"],
        ),
        _record(
            "external_artifact_import",
            checked_at=checked_at,
            state="approval_required",
            provider="operator_import",
            source="artifact_package",
            config_source="import_request.provenance.expected_artifact_sha256",
            approval_required=True,
            budget_class="approval_required",
            sandbox_constraints=["imported artifacts must validate schema, resolver ref, metrics, and sha256 when declared"],
            known_blockers=[
                "Imported artifacts cannot become publication evidence unless schema, hash, source independence, and statistics checks pass."
            ],
            related_artifact_refs=["experiment_execution_result.json:import_provenance"],
            operator_action_policy=_approval_policy(
                "External artifact imports require operator approval plus schema/hash validation."
            ),
        ),
        _record(
            "budget_policy",
            checked_at=checked_at,
            state="ready",
            provider="operator_budget",
            source="run_request",
            config_source="max_rounds,candidate_execution_limit,execution_profile",
            budget_class="bounded" if bounded_budget else "free",
            sandbox_constraints=["bounded runs do not bypass final publish evidence gates"],
            known_blockers=[],
        ),
        _record(
            "approval_policy",
            checked_at=checked_at,
            state="ready",
            provider="operator_controls",
            source="operator_action_log",
            config_source="operator_control.apply_operator_action",
            budget_class="free",
            sandbox_constraints=["approval, rejection, retry, resume, and cancel decisions are persisted"],
            related_artifact_refs=["operator_action_log.json"],
        ),
        _record(
            "sandbox_policy",
            checked_at=checked_at,
            state="ready",
            provider="repository_policy",
            source="runtime_contract",
            config_source="SANDBOX_BACKEND,SANDBOX_COMMAND_PREFIX",
            budget_class="free",
            sandbox_constraints=_dedupe(
                [
                    f"sandbox_backend={settings.sandbox_backend}",
                    *sandbox_prefixes,
                    "runtime contracts block undeclared network/GPU/paid-LLM requirements",
                ]
            ),
        ),
    ]


def build_external_capability_manifest(project_id: str) -> AutoResearchExternalCapabilityManifestRead:
    generated_at = _utcnow()
    records = _records_for_project(project_id, checked_at=generated_at)
    blockers = _dedupe(
        [
            f"{record.capability_id}: {blocker}"
            for record in records
            if record.state in {"blocked_by_policy", "failed_validation"}
            for blocker in record.known_blockers
        ]
    )
    fingerprint_payload = {
        "schema_version": "external_capability_manifest_v1",
        "project_id": project_id,
        "policy_version": GOAL10_EXTERNAL_CAPABILITY_POLICY_VERSION,
        "records": [
            {
                key: value
                for key, value in record.model_dump(mode="json").items()
                if key not in {"checked_at", "operator_action_policy"}
            }
            for record in records
        ],
        "blockers": blockers,
    }
    manifest = AutoResearchExternalCapabilityManifestRead(
        project_id=project_id,
        generated_at=generated_at,
        policy_version=GOAL10_EXTERNAL_CAPABILITY_POLICY_VERSION,
        records=records,
        record_count=len(records),
        blockers=blockers,
        deterministic=True,
        manifest_fingerprint=_fingerprint(fingerprint_payload),
        manifest_path=external_capability_manifest_file_path(project_id),
        unavailable_count=sum(1 for record in records if record.state == "unavailable"),
        approval_required_count=sum(1 for record in records if record.approval_required),
        ready_count=sum(1 for record in records if record.state == "ready"),
    )
    save_external_capability_manifest(manifest)
    return manifest


def get_or_build_external_capability_manifest(
    project_id: str,
    *,
    rebuild: bool = False,
) -> AutoResearchExternalCapabilityManifestRead:
    if not rebuild:
        loaded = load_external_capability_manifest(project_id)
        if loaded is not None:
            return loaded
    return build_external_capability_manifest(project_id)
