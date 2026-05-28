from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchPublicationRepairExecutionActionRead,
    AutoResearchPublicationRepairExecutionRead,
    AutoResearchPublicationRepairPlanRead,
    AutoResearchReviewLoopRead,
)
from services.autoresearch.repository import load_run_bundle_index


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _selected_output_roles(project_id: str, run_id: str) -> set[str]:
    bundle_index = load_run_bundle_index(project_id, run_id)
    if bundle_index is None:
        return set()
    selected_bundle = next(
        (item for item in bundle_index.bundles if item.id == "selected_candidate_repro"),
        None,
    )
    if selected_bundle is None:
        return set()
    return {asset.role for asset in selected_bundle.assets if asset.ref.exists}


def build_publication_repair_execution(
    *,
    project_id: str,
    run_id: str,
    repair_plan: AutoResearchPublicationRepairPlanRead,
    review_loop_before: AutoResearchReviewLoopRead,
    review_loop_after: AutoResearchReviewLoopRead | None,
) -> AutoResearchPublicationRepairExecutionRead:
    materialized_roles = _selected_output_roles(project_id, run_id)
    next_action_ids = set(repair_plan.next_action_ids)
    pending_after_titles = (
        {
            action.title
            for action in review_loop_after.actions
            if action.status == "pending"
        }
        if review_loop_after is not None
        else set()
    )
    selected_actions = [
        action
        for action in repair_plan.actions
        if action.status == "pending"
        and (not next_action_ids or action.action_id in next_action_ids)
    ]
    action_results: list[AutoResearchPublicationRepairExecutionActionRead] = []
    for action in selected_actions:
        expected = list(action.expected_outputs)
        materialized = [role for role in expected if role in materialized_roles]
        missing = [role for role in expected if role not in materialized_roles]
        if not action.auto_applicable:
            status = "blocked"
            detail = "Repair action requires manual input and was not executed automatically."
        elif action.title in pending_after_titles:
            status = "partial"
            detail = "Repair action ran, but re-review still reports the action as pending."
        elif missing:
            status = "partial"
            detail = "Repair action ran but some expected output assets are still missing."
        else:
            status = "executed"
            detail = "Repair action ran and all expected output assets are materialized."
        action_results.append(
            AutoResearchPublicationRepairExecutionActionRead(
                action_id=action.action_id,
                kind=action.kind,
                title=action.title,
                status=status,
                auto_applicable=action.auto_applicable,
                expected_output_asset_ids=expected,
                materialized_output_asset_ids=materialized,
                missing_output_asset_ids=missing,
                detail=detail,
            )
        )
    materialized_output_asset_ids = sorted(
        {
            role
            for result in action_results
            for role in result.materialized_output_asset_ids
        }
    )
    missing_output_asset_ids = sorted(
        {
            role
            for result in action_results
            for role in result.missing_output_asset_ids
        }
    )
    payload = {
        "execution_id": "publication_repair_execution_v1",
        "project_id": project_id,
        "run_id": run_id,
        "selected_candidate_id": repair_plan.selected_candidate_id,
        "repair_plan_fingerprint": repair_plan.repair_plan_fingerprint,
        "review_round_before": review_loop_before.current_round,
        "review_fingerprint_before": review_loop_before.latest_review_fingerprint,
        "review_round_after": review_loop_after.current_round if review_loop_after is not None else 0,
        "review_fingerprint_after": (
            review_loop_after.latest_review_fingerprint if review_loop_after is not None else None
        ),
        "action_results": [item.model_dump(mode="json") for item in action_results],
        "materialized_output_asset_ids": materialized_output_asset_ids,
        "missing_output_asset_ids": missing_output_asset_ids,
    }
    executed_count = sum(1 for item in action_results if item.status == "executed")
    partial_count = sum(1 for item in action_results if item.status == "partial")
    blocked_count = sum(1 for item in action_results if item.status == "blocked")
    return AutoResearchPublicationRepairExecutionRead(
        generated_at=_utcnow(),
        attempted_action_count=len(action_results),
        executed_action_count=executed_count,
        partial_action_count=partial_count,
        blocked_action_count=blocked_count,
        success=bool(action_results) and partial_count == 0 and blocked_count == 0,
        execution_fingerprint=_fingerprint(payload),
        **payload,
    )
