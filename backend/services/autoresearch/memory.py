from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from schemas.autoresearch import (
    AutoResearchGapMinerRead,
    AutoResearchMemoryExportRead,
    AutoResearchMemoryHintRead,
    AutoResearchMemoryImportRead,
    AutoResearchMemoryImportRequest,
    AutoResearchMemoryIndexRead,
    AutoResearchMemoryItemRead,
    AutoResearchMemoryItemType,
    AutoResearchMemoryQueryRequest,
    AutoResearchMemoryQueryResultRead,
    AutoResearchMemoryRebuildRead,
    AutoResearchMemorySourceRefRead,
    AutoResearchMemoryStoreRead,
    AutoResearchProjectRunbookRead,
    AutoResearchResearchBriefRead,
    AutoResearchRunRead,
)
from services.autoresearch.repository import (
    list_autoresearch_project_ids,
    list_research_briefs,
    list_runs,
    load_long_running_attempt_ledger,
    load_memory_store,
    load_project_runbook,
    memory_index_file_path,
    memory_store_file_path,
    save_memory_index,
    save_memory_store,
)


MEMORY_SCHEMA_VERSION = "autoresearch_memory_item_v1"
MEMORY_POLICY_VERSION = "goal12_multi_project_memory_v1"
_STOPWORDS = {
    "about",
    "against",
    "and",
    "artifact",
    "baseline",
    "benchmark",
    "candidate",
    "claim",
    "claims",
    "data",
    "dataset",
    "evidence",
    "experiment",
    "from",
    "literature",
    "memory",
    "method",
    "metric",
    "paper",
    "project",
    "research",
    "result",
    "source",
    "study",
    "system",
    "that",
    "this",
    "using",
    "with",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str, *, fallback: str = "memory") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:96] or fallback


def _norm(value: object | None) -> str:
    return " ".join(str(value or "").split()).strip()


def _dedupe(items: Iterable[object | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _norm(item)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _terms(*texts: object | None) -> set[str]:
    terms: set[str] = set()
    for text in texts:
        for raw in re.findall(r"[a-z][a-z0-9_]+", _norm(text).lower()):
            if len(raw) < 4 or raw in _STOPWORDS:
                continue
            terms.add(raw)
    return terms


def _source_fingerprint(payload: object) -> str:
    return _fingerprint(payload)


def _text_fingerprint(*parts: object | None) -> str:
    return _fingerprint({"text": " ".join(_norm(part).lower() for part in parts if _norm(part))})


def _source_ref(
    *,
    project_id: str,
    artifact_ref: str,
    payload: object,
    source_run_id: str | None = None,
    source_branch_id: str | None = None,
    source_date_version: str | None = None,
) -> AutoResearchMemorySourceRefRead:
    return AutoResearchMemorySourceRefRead(
        source_project_id=project_id,
        source_run_id=source_run_id,
        source_branch_id=source_branch_id,
        source_artifact_ref=artifact_ref,
        source_fingerprint=_source_fingerprint(payload),
        source_date_version=source_date_version,
    )


def _memory_id(
    *,
    project_id: str,
    item_type: AutoResearchMemoryItemType,
    source_ref: AutoResearchMemorySourceRefRead,
    text_fingerprint: str,
) -> str:
    payload = {
        "project_id": project_id,
        "source_run_id": source_ref.source_run_id,
        "source_branch_id": source_ref.source_branch_id,
        "source_artifact_ref": source_ref.source_artifact_ref,
        "source_fingerprint": source_ref.source_fingerprint,
        "text_fingerprint": text_fingerprint,
        "item_type": item_type,
    }
    return f"mem_{item_type}_{_fingerprint(payload)[:20]}"


def _item(
    *,
    item_type: AutoResearchMemoryItemType,
    title: str,
    summary: str,
    source: AutoResearchMemorySourceRefRead,
    evidence_grade: str,
    source_class: str,
    extraction_level: str,
    currentness: str = "fresh",
    limitations: list[str] | None = None,
    reuse_policy: str = "requires_current_project_revalidation",
    privacy_policy: str = "internal",
    retention_policy: str = "retain",
    negative_status: str = "none",
    domains: list[str] | None = None,
    methods: list[str] | None = None,
    datasets: list[str] | None = None,
    metrics: list[str] | None = None,
    benchmarks: list[str] | None = None,
    paper_source_ids: list[str] | None = None,
    claim_result_types: list[str] | None = None,
    blocker_failure_types: list[str] | None = None,
    tags: list[str] | None = None,
) -> AutoResearchMemoryItemRead:
    text_fingerprint = _text_fingerprint(
        item_type,
        title,
        summary,
        domains,
        methods,
        datasets,
        metrics,
        benchmarks,
        paper_source_ids,
        claim_result_types,
        blocker_failure_types,
    )
    return AutoResearchMemoryItemRead(
        memory_id=_memory_id(
            project_id=source.source_project_id,
            item_type=item_type,
            source_ref=source,
            text_fingerprint=text_fingerprint,
        ),
        schema_version=MEMORY_SCHEMA_VERSION,
        item_type=item_type,
        title=title,
        summary=summary,
        source=source,
        extraction_timestamp=_utcnow(),
        evidence_grade=evidence_grade,  # type: ignore[arg-type]
        source_class=source_class,  # type: ignore[arg-type]
        extraction_level=extraction_level,  # type: ignore[arg-type]
        currentness=currentness,  # type: ignore[arg-type]
        limitations=_dedupe(limitations or []),
        reuse_policy=reuse_policy,  # type: ignore[arg-type]
        privacy_policy=privacy_policy,  # type: ignore[arg-type]
        retention_policy=retention_policy,  # type: ignore[arg-type]
        negative_status=negative_status,  # type: ignore[arg-type]
        domains=_dedupe(domains or []),
        methods=_dedupe(methods or []),
        datasets=_dedupe(datasets or []),
        metrics=_dedupe(metrics or []),
        benchmarks=_dedupe(benchmarks or []),
        paper_source_ids=_dedupe(paper_source_ids or []),
        claim_result_types=_dedupe(claim_result_types or []),
        blocker_failure_types=_dedupe(blocker_failure_types or []),
        tags=_dedupe(tags or []),
        text_fingerprint=text_fingerprint,
    )


def _brief_artifact_ref(brief: AutoResearchResearchBriefRead) -> str:
    return brief.brief_path or f"brief:{brief.brief_id}"


def _run_artifact_ref(run: AutoResearchRunRead, fallback: str) -> str:
    return run.evidence_ledger_path or run.experiment_execution_result_path or run.paper_path or fallback


def _items_from_brief(brief: AutoResearchResearchBriefRead) -> list[AutoResearchMemoryItemRead]:
    artifact_ref = _brief_artifact_ref(brief)
    payload = brief.model_dump(mode="json")
    source = _source_ref(
        project_id=brief.project_id,
        artifact_ref=artifact_ref,
        payload=payload,
        source_date_version=brief.updated_at.isoformat(),
    )
    items: list[AutoResearchMemoryItemRead] = []
    if brief.domain_decision is not None:
        items.append(
            _item(
                item_type="method",
                title=f"Domain route: {brief.domain_decision.domain_label}",
                summary=(
                    f"Brief {brief.brief_id} routed `{brief.original_idea}` to "
                    f"{brief.domain_decision.domain_id}; supported={brief.domain_decision.is_supported}."
                ),
                source=source,
                evidence_grade="review_only",
                source_class="project",
                extraction_level="project_summary",
                limitations=[
                    "This is prior-project routing memory only; current project must rerun domain routing.",
                    *brief.domain_blockers,
                ],
                domains=[brief.domain_decision.domain_id, brief.domain_decision.domain_label, brief.domain or ""],
                methods=brief.candidate_baselines,
                datasets=brief.candidate_datasets,
                metrics=brief.candidate_metrics,
                benchmarks=[brief.benchmark_source.name if brief.benchmark_source is not None else ""],
                claim_result_types=["domain_route", "research_brief"],
                negative_status="blocker" if brief.status == "blocked" or brief.domain_blockers else "none",
                blocker_failure_types=brief.domain_blockers,
            )
        )
    for direction in brief.research_directions[:8]:
        items.append(
            _item(
                item_type="method",
                title=direction.title,
                summary=direction.method_sketch,
                source=source,
                evidence_grade="review_only",
                source_class="project",
                extraction_level="project_summary",
                limitations=[
                    "Prior brief direction is a discovery hint, not current-project evidence.",
                    *direction.kill_criteria[:2],
                ],
                domains=[brief.domain or "", brief.domain_decision.domain_id if brief.domain_decision else ""],
                methods=[direction.method_sketch, *direction.required_baselines],
                datasets=[direction.candidate_dataset],
                metrics=direction.candidate_metrics,
                benchmarks=[direction.target_task],
                claim_result_types=["method_direction", direction.expected_contribution_type],
                tags=[direction.task_family, direction.novelty_risk],
            )
        )
        if direction.novelty_risk == "high":
            items.append(
                _item(
                    item_type="negative_finding",
                    title=f"Novelty risk: {direction.title}",
                    summary=(
                        f"Prior direction `{direction.direction_id}` was marked high novelty risk and "
                        "requires a narrower gap before publication positioning."
                    ),
                    source=source,
                    evidence_grade="review_only",
                    source_class="project",
                    extraction_level="project_summary",
                    limitations=["High-risk prior memory can only create risk/follow-up actions."],
                    domains=[brief.domain or ""],
                    methods=[direction.method_sketch],
                    datasets=[direction.candidate_dataset],
                    metrics=direction.candidate_metrics,
                    benchmarks=[direction.target_task],
                    claim_result_types=["novelty_risk"],
                    blocker_failure_types=["novelty_insufficient"],
                    negative_status="negative_finding",
                )
            )
    if brief.literature_scout is not None:
        items.extend(_items_from_literature_scout(brief))
    if brief.gap_miner is not None:
        items.extend(_items_from_gap_miner(brief, brief.gap_miner))
    return items


def _items_from_literature_scout(brief: AutoResearchResearchBriefRead) -> list[AutoResearchMemoryItemRead]:
    scout = brief.literature_scout
    if scout is None:
        return []
    artifact_ref = f"brief:{brief.brief_id}:literature_scout"
    payload = scout.model_dump(mode="json")
    source = _source_ref(
        project_id=brief.project_id,
        artifact_ref=artifact_ref,
        payload=payload,
        source_date_version=scout.generated_at.isoformat(),
    )
    items: list[AutoResearchMemoryItemRead] = []
    for paper in scout.similar_papers[:24]:
        stale = paper.cache_freshness == "stale"
        revoked = paper.claim_ceiling == "revoked"
        currentness = "revoked" if revoked else "stale" if stale else "fresh" if paper.cache_freshness in {"fresh", "not_applicable"} else "unknown"
        privacy_policy = "revoked" if revoked else "internal"
        reuse_policy = "blocked" if revoked else "requires_current_project_revalidation"
        item_type: AutoResearchMemoryItemType = "paper"
        limitations = [
            *paper.extraction_limitations,
            "Literature memory is a discovery hint; cite only after current-project revalidation.",
        ]
        items.append(
            _item(
                item_type=item_type,
                title=paper.title,
                summary=paper.evidence or paper.abstract or paper.title,
                source=source,
                evidence_grade="review_only" if paper.source not in {"offline_project_context", "fixture", "fixture_offline"} else "weak",
                source_class="literature",
                extraction_level=paper.extraction_level,
                currentness=currentness,
                limitations=limitations,
                reuse_policy=reuse_policy,
                privacy_policy=privacy_policy,
                retention_policy="expire_on_source_revocation",
                domains=[brief.domain or "", brief.domain_decision.domain_id if brief.domain_decision else ""],
                methods=paper.methods or ([paper.method] if paper.method else []),
                datasets=paper.datasets,
                metrics=paper.metrics,
                benchmarks=paper.related_system_coverage,
                paper_source_ids=[paper.source_id or paper.doi or paper.arxiv_id or paper.paper_id],
                claim_result_types=["literature_observation", *paper.reported_results[:3]],
                tags=[paper.source, paper.cache_freshness, paper.extraction_status],
            )
        )
        for result in paper.reported_results[:3]:
            items.append(
                _item(
                    item_type="reported_result",
                    title=f"Reported result from {paper.title}",
                    summary=result,
                    source=source,
                    evidence_grade="review_only",
                    source_class="literature",
                    extraction_level=paper.extraction_level,
                    currentness=currentness,
                    limitations=[
                        "Reported-result memory must be rechecked against the current project literature artifact.",
                        *paper.extraction_limitations,
                    ],
                    reuse_policy=reuse_policy,
                    privacy_policy=privacy_policy,
                    retention_policy="expire_on_source_revocation",
                    domains=[brief.domain or ""],
                    methods=paper.methods or ([paper.method] if paper.method else []),
                    datasets=paper.datasets,
                    metrics=paper.metrics,
                    paper_source_ids=[paper.source_id or paper.doi or paper.arxiv_id or paper.paper_id],
                    claim_result_types=["reported_result"],
                )
            )
    return items


def _items_from_gap_miner(
    brief: AutoResearchResearchBriefRead,
    miner: AutoResearchGapMinerRead,
) -> list[AutoResearchMemoryItemRead]:
    artifact_ref = f"brief:{brief.brief_id}:gap_miner"
    payload = miner.model_dump(mode="json")
    source = _source_ref(
        project_id=brief.project_id,
        artifact_ref=artifact_ref,
        payload=payload,
        source_date_version=miner.generated_at.isoformat(),
    )
    items: list[AutoResearchMemoryItemRead] = []
    for gap in miner.gap_candidates[:8]:
        direction = next(
            (item for item in brief.research_directions if item.direction_id == gap.recommended_direction_id),
            None,
        )
        items.append(
            _item(
                item_type="project_conclusion",
                title=f"Gap hint: {gap.gap_id}",
                summary=gap.description,
                source=source,
                evidence_grade="review_only",
                source_class="project",
                extraction_level="project_summary",
                limitations=[
                    "Prior gap-mining output is not claim evidence for the current project.",
                    "Current project must run its own literature scout and gap validation.",
                ],
                domains=[brief.domain or "", brief.domain_decision.domain_id if brief.domain_decision else ""],
                methods=[direction.method_sketch if direction is not None else ""],
                datasets=[direction.candidate_dataset if direction is not None else ""],
                metrics=direction.candidate_metrics if direction is not None else [],
                benchmarks=[gap.validation_target or ""],
                paper_source_ids=gap.literature_evidence,
                claim_result_types=["gap_candidate", gap.recommendation],
                negative_status="negative_finding" if gap.recommendation != "proceed" else "none",
                blocker_failure_types=[gap.recommendation] if gap.recommendation != "proceed" else [],
            )
        )
    for warning in miner.warnings:
        items.append(
            _item(
                item_type="negative_finding",
                title=f"Gap-miner warning: {warning[:80]}",
                summary=warning,
                source=source,
                evidence_grade="review_only",
                source_class="project",
                extraction_level="project_summary",
                limitations=["Warning memory can only create current-project risks or follow-up actions."],
                domains=[brief.domain or ""],
                claim_result_types=["gap_warning"],
                blocker_failure_types=["novelty_or_gap_warning"],
                negative_status="negative_finding",
            )
        )
    for blocker in miner.blockers:
        items.append(
            _item(
                item_type="blocker",
                title=f"Gap-miner blocker: {blocker[:80]}",
                summary=blocker,
                source=source,
                evidence_grade="review_only",
                source_class="project",
                extraction_level="project_summary",
                limitations=["Blocker memory cannot fail a new final gate without current-project evidence."],
                domains=[brief.domain or ""],
                claim_result_types=["gap_blocker"],
                blocker_failure_types=["gap_blocker"],
                negative_status="blocker",
            )
        )
    return items


def _items_from_run(run: AutoResearchRunRead) -> list[AutoResearchMemoryItemRead]:
    artifact_ref = _run_artifact_ref(run, f"run:{run.id}")
    payload = run.model_dump(mode="json")
    source = _source_ref(
        project_id=run.project_id,
        source_run_id=run.id,
        source_branch_id=(
            f"branch:{run.portfolio.selected_candidate_id}"
            if run.portfolio is not None and run.portfolio.selected_candidate_id
            else f"branch:{run.id}:default"
        ),
        artifact_ref=artifact_ref,
        payload=payload,
        source_date_version=run.updated_at.isoformat(),
    )
    items: list[AutoResearchMemoryItemRead] = []
    if run.spec is not None:
        items.append(
            _item(
                item_type="benchmark",
                title=run.spec.benchmark_name,
                summary=run.spec.benchmark_description,
                source=source,
                evidence_grade="artifact_supported" if run.status == "done" else "review_only",
                source_class="benchmark",
                extraction_level="artifact",
                limitations=["Benchmark memory is a discovery hint until the current project resolves/imports its own benchmark artifact."],
                methods=[baseline.name for baseline in run.spec.baselines],
                datasets=[run.spec.dataset.name],
                metrics=[metric.name for metric in run.spec.metrics],
                benchmarks=[run.spec.benchmark_name],
                claim_result_types=["benchmark_protocol"],
                tags=[run.task_family or ""],
            )
        )
    if run.artifact is not None:
        metric_names = [
            metric
            for result in run.artifact.system_results
            for metric in result.metrics
        ]
        metric_names.extend(
            metric
            for result in run.artifact.aggregate_system_results
            for metric in result.mean_metrics
        )
        result_systems = [
            result.system
            for result in [
                *run.artifact.system_results,
                *run.artifact.aggregate_system_results,
            ]
        ]
        summary = run.artifact.summary or f"Run {run.id} produced {len(result_systems)} result rows."
        items.append(
            _item(
                item_type="reported_result",
                title=f"Run result: {run.topic}",
                summary=summary,
                source=source,
                evidence_grade="artifact_supported" if run.status == "done" else "weak",
                source_class="experiment",
                extraction_level="artifact",
                limitations=[
                    "Prior run result cannot support current-project claims without rerun/import validation.",
                    *(run.error.splitlines()[:2] if run.error else []),
                ],
                methods=result_systems,
                datasets=[run.spec.dataset.name if run.spec is not None else ""],
                metrics=metric_names,
                benchmarks=[run.spec.benchmark_name if run.spec is not None else ""],
                claim_result_types=["experiment_result", run.status],
                negative_status="negative_finding" if run.status in {"failed", "canceled"} else "none",
                blocker_failure_types=[run.error or run.status] if run.status in {"failed", "canceled"} else [],
            )
        )
    if run.evidence_ledger is not None:
        for entry in run.evidence_ledger.entries[:16]:
            items.append(
                _item(
                    item_type="project_conclusion"
                    if entry.support_status == "supported"
                    else "negative_finding",
                    title=f"Ledger claim: {entry.evidence_id}",
                    summary=entry.claim,
                    source=source,
                    evidence_grade="artifact_supported" if entry.support_status == "supported" else "weak",
                    source_class="experiment",
                    extraction_level="ledger",
                    currentness="fresh"
                    if entry.evidence_origin not in {"stale_cache"}
                    else "stale",
                    limitations=[
                        "Run-level ledger memory is not current-project claim evidence.",
                        *entry.limitations,
                    ],
                    methods=[entry.source_job_id or ""],
                    datasets=[run.spec.dataset.name if run.spec is not None else ""],
                    metrics=[entry.metric or ""],
                    benchmarks=[run.spec.benchmark_name if run.spec is not None else ""],
                    claim_result_types=[entry.evidence_kind, entry.evidence_type or "", entry.support_status],
                    negative_status="negative_finding" if entry.support_status != "supported" else "none",
                    blocker_failure_types=entry.failure_classifications,
                )
            )
    if run.reviewer_simulation is not None:
        for review in run.reviewer_simulation.reviews[:12]:
            items.append(
                _item(
                    item_type="reviewer_finding",
                    title=f"{review.role}: {review.decision}",
                    summary=review.reject_reason or "; ".join(review.weaknesses[:2]) or review.summary,
                    source=source,
                    evidence_grade="review_only",
                    source_class="review",
                    extraction_level="project_summary",
                    limitations=["Reviewer finding memory predicts risks only; it cannot support or fail current claims directly."],
                    claim_result_types=["reviewer_finding", review.decision],
                    blocker_failure_types=review.weaknesses,
                    negative_status="negative_finding" if review.decision in {"weak_reject", "reject"} else "none",
                )
            )
    return items


def _items_from_runbook(project_id: str, run: AutoResearchRunRead) -> list[AutoResearchMemoryItemRead]:
    runbook = load_project_runbook(project_id, run.id)
    if runbook is None:
        return []
    source = _source_ref(
        project_id=project_id,
        source_run_id=run.id,
        artifact_ref=runbook.runbook_path or f"runbook:{run.id}",
        payload=runbook.model_dump(mode="json"),
        source_date_version=runbook.rebuilt_at.isoformat(),
    )
    items: list[AutoResearchMemoryItemRead] = []
    for blocker in [*runbook.blockers, *runbook.blocked_actions]:
        items.append(
            _item(
                item_type="blocker",
                title=f"Runbook blocker: {blocker[:80]}",
                summary=blocker,
                source=source,
                evidence_grade="review_only",
                source_class="runbook",
                extraction_level="project_summary",
                limitations=["Prior runbook blocker is a risk signal only for a new project."],
                claim_result_types=["runbook_blocker"],
                blocker_failure_types=[blocker],
                negative_status="blocker",
            )
        )
    for repair in runbook.repair_candidates[:12]:
        items.append(
            _item(
                item_type="blocker" if repair.blockers else "implementation",
                title=f"Repair workflow: {repair.workflow}",
                summary=f"{repair.reason} Required action: {repair.required_action}.",
                source=source,
                evidence_grade="review_only",
                source_class="runbook",
                extraction_level="project_summary",
                limitations=["Repair workflow memory suggests follow-up only; it is not evidence of current failure."],
                claim_result_types=["repair_workflow", repair.workflow],
                blocker_failure_types=repair.blockers or [repair.workflow],
                negative_status="blocker" if repair.blockers else "none",
            )
        )
    ledger = load_long_running_attempt_ledger(project_id, run.id)
    if ledger is not None:
        ledger_source = _source_ref(
            project_id=project_id,
            source_run_id=run.id,
            artifact_ref=ledger.ledger_path or f"attempt_ledger:{run.id}",
            payload=ledger.model_dump(mode="json"),
            source_date_version=ledger.rebuilt_at.isoformat(),
        )
        for attempt in ledger.attempts[:16]:
            if attempt.status not in {"failed", "blocked", "canceled", "rejected", "timeout"} and not attempt.blockers:
                continue
            items.append(
                _item(
                    item_type="blocker",
                    title=f"Attempt {attempt.status}: {attempt.attempt_id}",
                    summary=attempt.failure_classification or "; ".join(attempt.blockers) or attempt.status,
                    source=ledger_source,
                    evidence_grade="review_only",
                    source_class="runbook",
                    extraction_level="ledger",
                    limitations=["Attempt-failure memory can suggest retry/repair planning only."],
                    claim_result_types=["attempt_failure", attempt.status],
                    blocker_failure_types=[attempt.failure_classification or "", *attempt.blockers],
                    negative_status="blocker",
                )
            )
    return items


def extract_memory_items(project_id: str) -> list[AutoResearchMemoryItemRead]:
    items: list[AutoResearchMemoryItemRead] = []
    for brief in list_research_briefs(project_id):
        items.extend(_items_from_brief(brief))
    for run in list_runs(project_id):
        items.extend(_items_from_run(run))
        items.extend(_items_from_runbook(project_id, run))
    return items


def _dedupe_memory_items(items: Iterable[AutoResearchMemoryItemRead]) -> list[AutoResearchMemoryItemRead]:
    by_key: dict[tuple[str, str, str, str], AutoResearchMemoryItemRead] = {}
    for item in items:
        key = (
            item.item_type,
            item.source.source_project_id,
            item.source.source_fingerprint,
            item.text_fingerprint,
        )
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = item
            continue
        winner = sorted(
            [existing, item],
            key=lambda candidate: (
                candidate.evidence_grade,
                candidate.extraction_timestamp,
                candidate.memory_id,
            ),
            reverse=True,
        )[0]
        by_key[key] = winner
    return sorted(by_key.values(), key=lambda item: item.memory_id)


def _eligible_for_store(item: AutoResearchMemoryItemRead) -> bool:
    return item.privacy_policy not in {"private", "revoked"} and item.currentness != "revoked"


def _index_dimension(items: Iterable[AutoResearchMemoryItemRead], getter) -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    for item in items:
        values = getter(item)
        if isinstance(values, str):
            values = [values]
        for value in _dedupe(values):
            index[value.lower()].append(item.memory_id)
    return {key: sorted(set(value)) for key, value in sorted(index.items())}


def build_memory_index(
    *,
    project_id: str,
    items: list[AutoResearchMemoryItemRead],
) -> AutoResearchMemoryIndexRead:
    item_ids = [item.memory_id for item in sorted(items, key=lambda value: value.memory_id)]
    return AutoResearchMemoryIndexRead(
        project_id=project_id,
        rebuilt_at=_utcnow(),
        item_count=len(item_ids),
        item_ids=item_ids,
        domains=_index_dimension(items, lambda item: item.domains),
        methods=_index_dimension(items, lambda item: item.methods),
        datasets=_index_dimension(items, lambda item: item.datasets),
        metrics=_index_dimension(items, lambda item: item.metrics),
        benchmarks=_index_dimension(items, lambda item: item.benchmarks),
        paper_source_ids=_index_dimension(items, lambda item: item.paper_source_ids),
        claim_result_types=_index_dimension(items, lambda item: item.claim_result_types),
        blocker_failure_types=_index_dimension(items, lambda item: item.blocker_failure_types),
        evidence_grades=_index_dimension(items, lambda item: item.evidence_grade),
        currentness=_index_dimension(items, lambda item: item.currentness),
        reuse_eligibility=_index_dimension(items, lambda item: item.reuse_policy),
        source_projects=_index_dimension(items, lambda item: item.source.source_project_id),
        store_path=memory_store_file_path(project_id),
        index_path=memory_index_file_path(project_id),
    )


def rebuild_project_memory(project_id: str) -> AutoResearchMemoryRebuildRead:
    extracted = extract_memory_items(project_id)
    deduped = _dedupe_memory_items(extracted)
    stored = [item for item in deduped if _eligible_for_store(item)]
    blocked_count = len(deduped) - len(stored)
    store = save_memory_store(
        AutoResearchMemoryStoreRead(
            project_id=project_id,
            rebuilt_at=_utcnow(),
            items=stored,
        )
    )
    index = save_memory_index(
        build_memory_index(project_id=project_id, items=store.items)
    )
    return AutoResearchMemoryRebuildRead(
        project_id=project_id,
        rebuilt_at=_utcnow(),
        store=store,
        index=index,
        extracted_count=len(extracted),
        deduped_count=len(stored),
        blocked_count=blocked_count,
        policy_notes=[
            "Memory items are discovery hints only and cannot satisfy current-project claim evidence.",
            "Private/revoked memory is excluded from the persisted store.",
        ],
    )


def get_or_rebuild_project_memory(project_id: str) -> AutoResearchMemoryStoreRead:
    store = load_memory_store(project_id)
    if store is not None:
        return store
    return rebuild_project_memory(project_id).store


def _load_all_stores() -> list[AutoResearchMemoryStoreRead]:
    stores: list[AutoResearchMemoryStoreRead] = []
    for project_id in list_autoresearch_project_ids():
        store = load_memory_store(project_id)
        if store is not None:
            stores.append(store)
    return stores


def _item_search_terms(item: AutoResearchMemoryItemRead) -> set[str]:
    return _terms(
        item.title,
        item.summary,
        item.domains,
        item.methods,
        item.datasets,
        item.metrics,
        item.benchmarks,
        item.paper_source_ids,
        item.claim_result_types,
        item.blocker_failure_types,
        item.tags,
    )


def _query_terms(request: AutoResearchMemoryQueryRequest) -> set[str]:
    return _terms(
        request.query,
        request.domain,
        request.methods,
        request.datasets,
        request.metrics,
        request.benchmarks,
    )


def _passes_policy(
    item: AutoResearchMemoryItemRead,
    request: AutoResearchMemoryQueryRequest,
) -> tuple[bool, str | None]:
    if request.source_project_ids is not None and item.source.source_project_id not in set(request.source_project_ids):
        return False, None
    if item.source.source_project_id in set(request.exclude_project_ids):
        return False, None
    if request.item_types is not None and item.item_type not in set(request.item_types):
        return False, None
    if item.privacy_policy == "private" and not request.include_private:
        return False, item.memory_id
    if item.privacy_policy == "revoked" or item.currentness == "revoked":
        return (request.include_revoked, item.memory_id if not request.include_revoked else None)
    if item.reuse_policy in {"blocked", "expired"}:
        return False, item.memory_id
    if item.reuse_policy == "internal_only" and not request.include_internal:
        return False, item.memory_id
    if item.currentness == "stale" and not request.include_stale:
        return False, item.memory_id
    return True, None


def _score_item(
    item: AutoResearchMemoryItemRead,
    request: AutoResearchMemoryQueryRequest,
) -> tuple[float, list[str]]:
    query_terms = _query_terms(request)
    item_terms = _item_search_terms(item)
    matches = sorted(query_terms & item_terms)
    score = len(matches) * 0.12
    dimensions = [
        (request.domain, item.domains, 0.18),
        (request.methods, item.methods, 0.12),
        (request.datasets, item.datasets, 0.12),
        (request.metrics, item.metrics, 0.12),
        (request.benchmarks, item.benchmarks, 0.12),
    ]
    for raw_query, values, weight in dimensions:
        raw_values = raw_query if isinstance(raw_query, list) else [raw_query] if raw_query else []
        value_terms = _terms(raw_values)
        if value_terms and value_terms & _terms(values):
            score += weight
    grade_bonus = {
        "publication_candidate": 0.16,
        "artifact_supported": 0.14,
        "review_only": 0.08,
        "weak": 0.04,
        "unsupported": 0.0,
    }.get(item.evidence_grade, 0.0)
    currentness_penalty = {"fresh": 0.0, "unknown": -0.04, "stale": -0.08, "revoked": -1.0}.get(item.currentness, 0.0)
    negative_bonus = 0.04 if item.negative_status in {"negative_finding", "blocker"} else 0.0
    score = max(0.0, min(1.0, score + grade_bonus + currentness_penalty + negative_bonus))
    return round(score, 3), matches[:12]


def _validation_actions(item: AutoResearchMemoryItemRead) -> list[str]:
    actions = [
        "Revalidate this memory through current-project literature, benchmark, execution, or evidence-ledger artifacts before using it in a claim.",
        f"Record a current-project source artifact and fingerprint separate from memory item `{item.memory_id}`.",
    ]
    if item.currentness in {"aging", "stale", "unknown"}:
        actions.append("Refresh or replace stale/unknown source material before publish-facing use.")
    if item.item_type in {"paper", "reported_result"}:
        actions.append("Run current-project literature scout/import and cite the current-project paper observation, not memory.")
    if item.item_type in {"benchmark", "dataset", "metric"}:
        actions.append("Resolve/import the benchmark or metric schema in the current project before protocol claims.")
    if item.negative_status in {"negative_finding", "blocker", "policy_blocked"}:
        actions.append("Convert this prior negative memory into a risk, kill criterion, repair suggestion, or follow-up only.")
    return _dedupe(actions)


def _hint_from_item(
    item: AutoResearchMemoryItemRead,
    *,
    score: float,
    matched_terms: list[str],
) -> AutoResearchMemoryHintRead:
    return AutoResearchMemoryHintRead(
        hint_id=f"hint_{item.memory_id}",
        memory_id=item.memory_id,
        item_type=item.item_type,
        source_project_id=item.source.source_project_id,
        source_run_id=item.source.source_run_id,
        source_branch_id=item.source.source_branch_id,
        source_artifact_ref=item.source.source_artifact_ref,
        source_fingerprint=item.source.source_fingerprint,
        title=item.title,
        summary=item.summary,
        source_refs=[
            item.source.source_artifact_ref,
            item.source.source_fingerprint,
            *(item.paper_source_ids[:4] if item.paper_source_ids else []),
        ],
        currentness=item.currentness,
        limitations=item.limitations,
        reuse_policy=item.reuse_policy,
        reuse_requirements=[
            "Memory is a discovery hint and must not be copied into current-project claim evidence.",
            "Current-project validation must produce its own artifact refs, fingerprints, and evidence ledger entries.",
        ],
        required_current_project_validation_actions=_validation_actions(item),
        evidence_grade=item.evidence_grade,
        source_class=item.source_class,
        extraction_level=item.extraction_level,
        negative_status=item.negative_status,
        relevance_score=score,
        matched_terms=matched_terms,
        memory_hint_only=True,
    )


def query_memory(
    project_id: str,
    request: AutoResearchMemoryQueryRequest | None = None,
) -> AutoResearchMemoryQueryResultRead:
    request = request or AutoResearchMemoryQueryRequest(exclude_project_ids=[project_id])
    if project_id not in request.exclude_project_ids:
        request = request.model_copy(update={"exclude_project_ids": [*request.exclude_project_ids, project_id]})
    scored: list[tuple[float, str, AutoResearchMemoryItemRead, list[str]]] = []
    blocked: list[str] = []
    for store in _load_all_stores():
        for item in store.items:
            allowed, blocked_id = _passes_policy(item, request)
            if blocked_id:
                blocked.append(blocked_id)
            if not allowed:
                continue
            score, matches = _score_item(item, request)
            if _query_terms(request) and score <= 0.0:
                continue
            scored.append((score, item.memory_id, item, matches))
    scored.sort(key=lambda row: (-row[0], row[1]))
    hints = [
        _hint_from_item(item, score=score, matched_terms=matches)
        for score, _memory_id, item, matches in scored[: request.limit]
    ]
    payload = {
        "project_id": project_id,
        "query": request.model_dump(mode="json"),
        "hints": [hint.model_dump(mode="json") for hint in hints],
        "blocked_memory_ids": sorted(set(blocked)),
    }
    return AutoResearchMemoryQueryResultRead(
        query_id=f"memory_query:{_fingerprint(payload)[:16]}",
        project_id=project_id,
        generated_at=_utcnow(),
        query=request,
        hints=hints,
        hint_count=len(hints),
        policy_notes=[
            "Returned rows are memory hints only.",
            "They cannot satisfy current-project claim evidence until revalidated into current-project artifacts.",
            "Stale or negative memory is converted to risk/follow-up guidance only.",
        ],
        blocked_memory_ids=sorted(set(blocked)),
        result_fingerprint=_fingerprint(payload),
    )


def query_memory_for_brief(
    brief: AutoResearchResearchBriefRead,
    *,
    limit: int = 6,
) -> AutoResearchMemoryQueryResultRead:
    return query_memory(
        brief.project_id,
        AutoResearchMemoryQueryRequest(
            query=" ".join(
                [
                    brief.original_idea,
                    brief.polished_idea,
                    " ".join(brief.research_questions),
                ]
            ),
            domain=brief.domain_decision.domain_id if brief.domain_decision is not None else brief.domain,
            methods=brief.candidate_baselines,
            datasets=brief.candidate_datasets,
            metrics=brief.candidate_metrics,
            benchmarks=[brief.benchmark_source.name if brief.benchmark_source is not None else ""],
            exclude_project_ids=[brief.project_id],
            include_stale=True,
            include_internal=True,
            include_private=False,
            include_revoked=False,
            limit=limit,
        ),
    )


def attach_memory_hints_to_brief(
    brief: AutoResearchResearchBriefRead,
    *,
    limit: int = 6,
) -> AutoResearchResearchBriefRead:
    result = query_memory_for_brief(brief, limit=limit)
    followups = _dedupe(
        [
            *brief.memory_required_followups,
            *[
                action
                for hint in result.hints
                for action in hint.required_current_project_validation_actions
                if hint.currentness in {"stale", "unknown"} or hint.negative_status != "none"
            ],
        ]
    )
    validation_actions = _dedupe(
        [
            *brief.memory_validation_actions,
            *[
                action
                for hint in result.hints
                for action in hint.required_current_project_validation_actions[:2]
            ],
        ]
    )
    return brief.model_copy(
        update={
            "memory_hints": result.hints,
            "memory_policy_notes": result.policy_notes,
            "memory_required_followups": followups,
            "memory_validation_actions": validation_actions,
            "domain_required_followups": _dedupe([*brief.domain_required_followups, *followups]),
            "kill_criteria": _dedupe(
                [
                    *brief.kill_criteria,
                    *[
                        f"Reframe or stop if current-project validation confirms prior blocker memory `{hint.memory_id}`."
                        for hint in result.hints
                        if hint.negative_status in {"negative_finding", "blocker"}
                    ],
                ]
            ),
        }
    )


def memory_risks_from_hints(hints: Iterable[AutoResearchMemoryHintRead]) -> list[str]:
    risks: list[str] = []
    for hint in hints:
        if hint.currentness in {"aging", "stale", "unknown"}:
            risks.append(f"Memory `{hint.memory_id}` is {hint.currentness}; refresh before relying on it.")
        if hint.negative_status in {"negative_finding", "blocker", "policy_blocked"}:
            risks.append(f"Prior negative memory `{hint.memory_id}` suggests risk: {hint.summary}")
        if hint.reuse_policy in {"internal_only", "blocked", "expired"}:
            risks.append(f"Memory `{hint.memory_id}` reuse policy is {hint.reuse_policy}.")
    return _dedupe(risks)


def memory_followups_from_hints(hints: Iterable[AutoResearchMemoryHintRead]) -> list[str]:
    return _dedupe(
        action
        for hint in hints
        for action in hint.required_current_project_validation_actions
    )


def export_project_memory(project_id: str) -> AutoResearchMemoryExportRead:
    store = get_or_rebuild_project_memory(project_id)
    export_items = [
        item
        for item in store.items
        if item.privacy_policy == "public" or item.reuse_policy != "internal_only"
    ]
    payload = {
        "project_id": project_id,
        "items": [item.model_dump(mode="json") for item in export_items],
        "store_fingerprint": store.store_fingerprint,
    }
    return AutoResearchMemoryExportRead(
        project_id=project_id,
        exported_at=_utcnow(),
        items=export_items,
        item_count=len(export_items),
        store_fingerprint=store.store_fingerprint,
        export_fingerprint=_fingerprint(payload),
    )


def import_project_memory(
    project_id: str,
    request: AutoResearchMemoryImportRequest,
) -> AutoResearchMemoryImportRead:
    existing = [] if request.replace else list((load_memory_store(project_id) or AutoResearchMemoryStoreRead(project_id=project_id, rebuilt_at=_utcnow())).items)
    incoming = [
        item.model_copy(
            update={
                "source": item.source.model_copy(update={"source_project_id": item.source.source_project_id})
            }
        )
        for item in request.items
        if _eligible_for_store(item)
    ]
    merged = _dedupe_memory_items([*existing, *incoming])
    store = save_memory_store(
        AutoResearchMemoryStoreRead(
            project_id=project_id,
            rebuilt_at=_utcnow(),
            items=merged,
        )
    )
    index = save_memory_index(build_memory_index(project_id=project_id, items=store.items))
    skipped = len(request.items) - len(incoming)
    return AutoResearchMemoryImportRead(
        project_id=project_id,
        imported_at=_utcnow(),
        imported_count=len(incoming),
        skipped_count=skipped,
        store=store,
        index=index,
        policy_notes=[
            "Imported memory remains discovery-only.",
            "Private/revoked/blocked memory is skipped during import.",
        ],
    )
