from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchPublicationRepairActionRead,
    AutoResearchPublicationRepairPlanRead,
    AutoResearchRepairActionKind,
    AutoResearchRepairActionSource,
    AutoResearchRevisionPriority,
    AutoResearchReviewLoopRead,
    AutoResearchRunReviewRead,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:80] or "repair_action"


def _priority(text: str, *, required_for_final_publish: bool = False) -> AutoResearchRevisionPriority:
    lowered = text.lower()
    if required_for_final_publish or any(
        marker in lowered
        for marker in ("final publish", "missing required", "unsupported", "underpowered", "no real")
    ):
        return "high"
    if any(marker in lowered for marker in ("citation", "literature", "benchmark", "compile")):
        return "medium"
    return "low"


def _kind(text: str, supporting_asset_ids: list[str] | None = None) -> AutoResearchRepairActionKind:
    lowered = f"{text} {' '.join(supporting_asset_ids or [])}".lower()
    if any(marker in lowered for marker in ("claim", "unsupported", "evidence matrix")):
        return "repair_claim_evidence"
    if any(marker in lowered for marker in ("literature", "citation", "related work", "references")):
        return "refresh_literature"
    if any(marker in lowered for marker in ("benchmark", "dataset", "provenance", "license", "source_kind")):
        return "update_benchmark_provenance"
    if any(
        marker in lowered
        for marker in ("seed", "sweep", "ablation", "significance", "power", "statistic", "artifact")
    ):
        return "rerun_experiments"
    if any(
        marker in lowered
        for marker in (
            "paper",
            "latex",
            "bibliography",
            "compile",
            "build script",
            "source manifest",
            "paper_sources",
        )
    ):
        return "rebuild_paper_sources"
    if any(marker in lowered for marker in ("publish package", "archive", "code package")):
        return "rebuild_publish_package"
    return "manual_review"


def _auto_applicable(kind: AutoResearchRepairActionKind) -> bool:
    return kind in {
        "rebuild_paper_sources",
        "repair_claim_evidence",
        "refresh_literature",
        "rerun_experiments",
        "rebuild_publish_package",
    }


def _expected_outputs(kind: AutoResearchRepairActionKind) -> list[str]:
    return {
        "rebuild_paper_sources": [
            "run_paper_markdown",
            "run_paper_latex_source",
            "run_paper_bibliography_bib",
            "run_paper_sources_manifest_json",
            "run_paper_compile_report_json",
        ],
        "repair_claim_evidence": [
            "run_claim_evidence_matrix_json",
            "run_paper_markdown",
            "run_publication_readiness_json",
        ],
        "refresh_literature": [
            "run_paper_markdown",
            "run_claim_evidence_matrix_json",
            "run_publication_readiness_json",
        ],
        "rerun_experiments": [
            "run_artifact_json",
            "run_generated_code",
            "run_methodology_audit_json",
            "run_publication_readiness_json",
        ],
        "update_benchmark_provenance": [
            "benchmark_json",
            "run_benchmark_card_json",
            "run_research_protocol_json",
        ],
        "rebuild_publish_package": [
            "run_publication_evidence_index_json",
            "run_publication_repair_plan_json",
        ],
        "manual_review": ["run_revision_dossier_json"],
    }[kind]


def _status(kind: AutoResearchRepairActionKind) -> str:
    return "pending" if _auto_applicable(kind) else "blocked"


def _action(
    *,
    action_id: str,
    kind: AutoResearchRepairActionKind,
    source: AutoResearchRepairActionSource,
    title: str,
    detail: str,
    source_ids: list[str] | None = None,
    supporting_asset_ids: list[str] | None = None,
    priority: AutoResearchRevisionPriority | None = None,
    required_for_final_publish: bool = False,
) -> AutoResearchPublicationRepairActionRead:
    auto_applicable = _auto_applicable(kind)
    blockers = [] if auto_applicable else ["Requires operator-supplied provenance or manual research judgment."]
    return AutoResearchPublicationRepairActionRead(
        action_id=action_id,
        kind=kind,
        source=source,
        source_ids=source_ids or [],
        priority=priority or _priority(detail, required_for_final_publish=required_for_final_publish),
        title=title,
        detail=detail,
        status=_status(kind),
        auto_applicable=auto_applicable,
        expected_outputs=_expected_outputs(kind),
        supporting_asset_ids=supporting_asset_ids or [],
        blockers=blockers,
    )


def build_publication_repair_plan(
    *,
    review: AutoResearchRunReviewRead,
    review_loop: AutoResearchReviewLoopRead | None,
) -> AutoResearchPublicationRepairPlanRead:
    actions: dict[str, AutoResearchPublicationRepairActionRead] = {}

    def add(action: AutoResearchPublicationRepairActionRead) -> None:
        existing = actions.get(action.action_id)
        if existing is None:
            actions[action.action_id] = action
            return
        actions[action.action_id] = existing.model_copy(
            update={
                "source_ids": sorted(set(existing.source_ids + action.source_ids)),
                "supporting_asset_ids": sorted(
                    set(existing.supporting_asset_ids + action.supporting_asset_ids)
                ),
                "blockers": sorted(set(existing.blockers + action.blockers)),
            }
        )

    for finding in review.findings:
        if finding.severity == "info":
            continue
        text = f"{finding.summary} {finding.detail}"
        kind = _kind(text, finding.supporting_asset_ids)
        add(
            _action(
                action_id=f"finding_{finding.id}_{_slug(kind)}",
                kind=kind,
                source="review_finding",
                source_ids=[finding.id],
                title=f"Repair finding: {finding.summary}",
                detail=finding.detail,
                supporting_asset_ids=list(finding.supporting_asset_ids),
                required_for_final_publish=finding.severity == "error",
            )
        )

    for revision in review.revision_plan:
        text = f"{revision.title} {revision.detail}"
        kind = _kind(text)
        add(
            _action(
                action_id=f"revision_{revision.id}_{_slug(kind)}",
                kind=kind,
                source="revision_action",
                source_ids=[revision.id],
                title=revision.title,
                detail=revision.detail,
                priority=revision.priority,
            )
        )

    if review.revision_dossier is not None:
        for item in review.revision_dossier.items:
            if item.status == "resolved":
                continue
            text = f"{item.summary} {item.response} {' '.join(item.action_titles)}"
            kind = _kind(text, item.supporting_asset_ids)
            add(
                _action(
                    action_id=f"dossier_{item.item_id}_{_slug(kind)}",
                    kind=kind,
                    source="revision_dossier",
                    source_ids=[item.item_id],
                    title=item.summary,
                    detail=item.response,
                    supporting_asset_ids=list(item.supporting_asset_ids),
                    required_for_final_publish=item.required_for_final_publish,
                )
            )

    if review.publication_evidence_index is not None:
        for blocker in review.publication_evidence_index.blockers:
            kind = _kind(blocker)
            add(
                _action(
                    action_id=f"evidence_{_slug(blocker)}_{_slug(kind)}",
                    kind=kind,
                    source="evidence_index",
                    title="Restore missing publication evidence",
                    detail=blocker,
                    required_for_final_publish=True,
                )
            )

    if review.publication_readiness is not None:
        for blocker in review.publication_readiness.blockers:
            kind = _kind(blocker)
            add(
                _action(
                    action_id=f"readiness_{_slug(blocker)}_{_slug(kind)}",
                    kind=kind,
                    source="readiness",
                    title="Resolve publication readiness blocker",
                    detail=blocker,
                    required_for_final_publish=True,
                )
            )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    ordered_actions = sorted(
        actions.values(),
        key=lambda item: (
            item.status != "pending",
            priority_order.get(item.priority, 3),
            item.kind,
            item.action_id,
        ),
    )
    pending_actions = [item for item in ordered_actions if item.status == "pending"]
    blocked_actions = [item for item in ordered_actions if item.status == "blocked"]
    readiness = review.publication_readiness
    payload = {
        "plan_id": "publication_repair_plan_v1",
        "project_id": review.project_id,
        "run_id": review.run_id,
        "selected_candidate_id": review.selected_candidate_id,
        "review_round": review_loop.current_round if review_loop is not None else 0,
        "review_fingerprint": review_loop.latest_review_fingerprint if review_loop is not None else None,
        "publication_tier": readiness.tier if readiness is not None else "exploratory",
        "publication_readiness_score": readiness.score if readiness is not None else 0,
        "actions": [item.model_dump(mode="json") for item in ordered_actions],
        "next_action_ids": [item.action_id for item in pending_actions[:5]],
        "complete": not ordered_actions,
        "blockers": [
            f"Blocked repair action requires manual input: {item.title}"
            for item in blocked_actions
        ],
    }
    return AutoResearchPublicationRepairPlanRead(
        generated_at=_utcnow(),
        action_count=len(ordered_actions),
        pending_action_count=len(pending_actions),
        blocked_action_count=len(blocked_actions),
        auto_applicable_action_count=sum(1 for item in ordered_actions if item.auto_applicable),
        repair_plan_fingerprint=_fingerprint(payload),
        **payload,
    )
