from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchClaimEvidenceEntryRead,
    AutoResearchCrossRunMetaAnalysisRead,
    AutoResearchPaperTier,
    AutoResearchProjectClaimTraceRead,
    AutoResearchProjectConclusionEntryRead,
    AutoResearchProjectConclusionLedgerRead,
    AutoResearchProjectPaperDecision,
    AutoResearchProjectPaperOrchestrationRead,
    AutoResearchProjectPaperSourceStrategy,
    AutoResearchResearchBriefRead,
    AutoResearchRunRead,
)
from services.autoresearch.meta_analysis import build_cross_run_meta_analysis
from services.autoresearch.repository import list_research_briefs, list_runs


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str, *, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug[:72] or fallback


def _paper_tier_from_decision(decision: AutoResearchProjectPaperDecision) -> AutoResearchPaperTier:
    if decision == "conference_candidate":
        return "conference_candidate"
    if decision == "workshop_candidate":
        return "workshop_candidate"
    return "technical_report"


def _claim_evidence_refs(run: AutoResearchRunRead) -> list[str]:
    refs: list[str] = []
    if run.artifact is not None and run.artifact.status == "done":
        refs.append(f"{run.id}:artifact:{run.artifact.primary_metric}")
    if run.evidence_ledger is not None and run.evidence_ledger.entries:
        refs.extend(f"{run.id}:evidence_ledger:{item.evidence_id}" for item in run.evidence_ledger.entries[:6])
    if run.claim_evidence_matrix is not None:
        supported = [
            item
            for item in run.claim_evidence_matrix.entries
            if item.support_status in {"supported", "partial"} and item.evidence
        ]
        refs.extend(f"{run.id}:claim_matrix:{item.claim_id}" for item in supported[:6])
    if run.paper_compile_report is not None:
        strong = [
            item
            for item in run.paper_compile_report.claim_ledger
            if item.support_status in {"supported", "partial"} and item.evidence_count > 0
        ]
        refs.extend(f"{run.id}:paper_claim_ledger:{item.claim_id}" for item in strong[:6])
    return _dedupe(refs)


def _run_has_evidence(run: AutoResearchRunRead) -> bool:
    return bool(_claim_evidence_refs(run))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = " ".join(str(item).split()).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _selected_runs(
    *,
    runs: list[AutoResearchRunRead],
    meta_analysis: AutoResearchCrossRunMetaAnalysisRead,
) -> list[AutoResearchRunRead]:
    by_id = {run.id: run for run in runs}
    selected = [by_id[run_id] for run_id in meta_analysis.recommended_run_ids if run_id in by_id]
    if selected:
        return selected
    done_with_evidence = [run for run in runs if run.status == "done" and _run_has_evidence(run)]
    if done_with_evidence:
        return done_with_evidence
    return [run for run in runs if run.status == "done"]


def _conclusion(
    *,
    conclusion_id: str,
    kind: str,
    text: str,
    supporting_run_ids: list[str],
    evidence_refs: list[str],
    caveats: list[str] | None = None,
    paper_claim_allowed: bool = False,
) -> AutoResearchProjectConclusionEntryRead:
    return AutoResearchProjectConclusionEntryRead(
        conclusion_id=conclusion_id,
        kind=kind,  # type: ignore[arg-type]
        text=text,
        supporting_run_ids=_dedupe(supporting_run_ids),
        evidence_refs=_dedupe(evidence_refs),
        caveats=_dedupe(caveats or []),
        paper_claim_allowed=paper_claim_allowed,
    )


def _claim_entries(run: AutoResearchRunRead) -> list[AutoResearchClaimEvidenceEntryRead]:
    if run.claim_evidence_matrix is None:
        return []
    return run.claim_evidence_matrix.entries


def _build_conclusion_ledger(
    *,
    project_id: str,
    selected_runs: list[AutoResearchRunRead],
    meta_analysis: AutoResearchCrossRunMetaAnalysisRead,
) -> AutoResearchProjectConclusionLedgerRead:
    runs_by_id = {run.id: run for run in selected_runs}
    stable: list[AutoResearchProjectConclusionEntryRead] = []
    conditional: list[AutoResearchProjectConclusionEntryRead] = []
    negative: list[AutoResearchProjectConclusionEntryRead] = []
    failed: list[AutoResearchProjectConclusionEntryRead] = []
    limitations: list[AutoResearchProjectConclusionEntryRead] = []

    for item in meta_analysis.stable_conclusions:
        evidence_refs: list[str] = []
        for run_id in item.supporting_run_ids:
            run = runs_by_id.get(run_id)
            if run is None:
                continue
            evidence_refs.extend(_claim_evidence_refs(run))
        target = stable if item.stability == "stable" else conditional
        target.append(
            _conclusion(
                conclusion_id=item.conclusion_id,
                kind="stable" if item.stability == "stable" else "conditional",
                text=item.text,
                supporting_run_ids=item.supporting_run_ids,
                evidence_refs=evidence_refs,
                caveats=item.caveats,
                paper_claim_allowed=bool(evidence_refs),
            )
        )

    for run in selected_runs:
        if run.artifact is not None:
            for index, item in enumerate(run.artifact.negative_results, start=1):
                negative.append(
                    _conclusion(
                        conclusion_id=f"negative_{run.id}_{index}",
                        kind="negative",
                        text=(
                            f"{item.subject} did not exceed {item.reference} on {item.metric}: "
                            f"{item.detail}"
                        ),
                        supporting_run_ids=[run.id],
                        evidence_refs=_claim_evidence_refs(run),
                        caveats=["Negative findings are scoped to the executed comparator set."],
                        paper_claim_allowed=_run_has_evidence(run),
                    )
                )
            if run.artifact.failed_trials:
                failed.append(
                    _conclusion(
                        conclusion_id=f"failed_trials_{run.id}",
                        kind="failed_hypothesis",
                        text=f"Run {run.id} contains failed trials that should remain visible in the project paper.",
                        supporting_run_ids=[run.id],
                        evidence_refs=[f"{run.id}:artifact:failed_trials"],
                        caveats=["Failure evidence should be framed as a limitation or replanning signal."],
                        paper_claim_allowed=True,
                    )
                )
        if run.status == "failed":
            failed.append(
                _conclusion(
                    conclusion_id=f"failed_run_{run.id}",
                    kind="failed_hypothesis",
                    text=f"Run {run.id} failed and cannot support positive project-level claims.",
                    supporting_run_ids=[run.id],
                    evidence_refs=_claim_evidence_refs(run),
                    caveats=["Failed runs may support negative or methodological conclusions only."],
                    paper_claim_allowed=False,
                )
            )
        if run.experiment_factory_repair_plan is not None and run.experiment_factory_repair_plan.actions != ["none"]:
            limitations.append(
                _conclusion(
                    conclusion_id=f"factory_repair_{run.id}",
                    kind="limitation",
                    text=(
                        "Experiment factory repair actions remain for "
                        f"{run.id}: {', '.join(run.experiment_factory_repair_plan.actions)}."
                    ),
                    supporting_run_ids=[run.id],
                    evidence_refs=[f"{run.id}:experiment_factory_repair_plan"],
                    caveats=run.experiment_factory_repair_plan.action_reasons,
                    paper_claim_allowed=True,
                )
            )
        for claim in _claim_entries(run):
            if claim.support_status == "unsupported":
                limitations.append(
                    _conclusion(
                        conclusion_id=f"unsupported_claim_{run.id}_{claim.claim_id}",
                        kind="limitation",
                        text=f"Unsupported run-level claim remains unresolved: {claim.claim}",
                        supporting_run_ids=[run.id],
                        evidence_refs=[f"{run.id}:claim_matrix:{claim.claim_id}"],
                        caveats=claim.gaps,
                        paper_claim_allowed=True,
                    )
                )

    if selected_runs and not stable and not conditional:
        for run in selected_runs:
            refs = _claim_evidence_refs(run)
            if not refs:
                continue
            score = run.artifact.objective_score if run.artifact is not None else None
            metric = run.artifact.primary_metric if run.artifact is not None else "primary metric"
            conditional.append(
                _conclusion(
                    conclusion_id=f"conditional_{run.id}",
                    kind="conditional",
                    text=(
                        f"Run {run.id} provides run-level evidence on {metric}"
                        + (f" with objective score {score:.4f}." if isinstance(score, (int, float)) else ".")
                    ),
                    supporting_run_ids=[run.id],
                    evidence_refs=refs,
                    caveats=["Single-run evidence cannot be promoted to a stable project-level result."],
                    paper_claim_allowed=True,
                )
            )

    all_conclusions = stable + conditional + negative + failed + limitations
    payload = {
        "ledger_id": "project_conclusion_ledger_v1",
        "project_id": project_id,
        "stable_conclusions": [item.model_dump(mode="json") for item in stable],
        "conditional_conclusions": [item.model_dump(mode="json") for item in conditional],
        "negative_findings": [item.model_dump(mode="json") for item in negative],
        "failed_hypotheses": [item.model_dump(mode="json") for item in failed],
        "limitations": [item.model_dump(mode="json") for item in limitations],
        "conclusion_count": len(all_conclusions),
    }
    return AutoResearchProjectConclusionLedgerRead(
        ledger_fingerprint=_fingerprint(payload),
        **payload,
    )


def _trace_claims(
    ledger: AutoResearchProjectConclusionLedgerRead,
    *,
    selected_runs: list[AutoResearchRunRead],
) -> list[AutoResearchProjectClaimTraceRead]:
    runs_by_id = {run.id: run for run in selected_runs}
    entries = ledger.stable_conclusions + ledger.conditional_conclusions
    traces: list[AutoResearchProjectClaimTraceRead] = []
    for item in entries:
        strong = item.kind == "stable"
        missing = [
            run_id
            for run_id in item.supporting_run_ids
            if run_id not in runs_by_id or not _run_has_evidence(runs_by_id[run_id])
        ]
        if item.evidence_refs and not missing:
            status = "supported"
        elif item.evidence_refs:
            status = "partial"
        else:
            status = "unsupported"
        reasons = []
        if not item.evidence_refs:
            reasons.append("No run-level evidence refs are attached to the conclusion.")
        if missing:
            reasons.append("Some supporting runs lack artifact, evidence ledger, or claim-ledger evidence.")
        traces.append(
            AutoResearchProjectClaimTraceRead(
                claim_id=f"project_claim_{_slug(item.conclusion_id)}",
                claim=item.text,
                source_conclusion_id=item.conclusion_id,
                support_status=status,  # type: ignore[arg-type]
                supporting_run_ids=item.supporting_run_ids,
                evidence_refs=item.evidence_refs,
                unsupported_reasons=reasons,
                strong_claim=strong,
            )
        )
    return traces


def _reviewer_average(selected_runs: list[AutoResearchRunRead]) -> tuple[int, float]:
    simulations = [run.reviewer_simulation for run in selected_runs if run.reviewer_simulation is not None]
    if not simulations:
        return 0, 0.0
    return len(simulations), round(sum(item.average_score for item in simulations) / len(simulations), 2)


def _decision(
    *,
    selected_runs: list[AutoResearchRunRead],
    ledger: AutoResearchProjectConclusionLedgerRead,
    traces: list[AutoResearchProjectClaimTraceRead],
    reviewer_average_score: float,
) -> tuple[bool, bool, AutoResearchProjectPaperDecision, AutoResearchProjectPaperSourceStrategy, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not selected_runs:
        blockers.append("No completed run with project evidence is available.")
        return False, False, "do_not_write", "no_paper", blockers, warnings

    unsupported = [trace for trace in traces if trace.support_status == "unsupported"]
    strong_unsupported = [trace for trace in unsupported if trace.strong_claim]
    if strong_unsupported:
        blockers.append("Project-level paper has strong cross-run claims without run-level evidence.")
    if unsupported:
        warnings.append("Some project-level claims remain unsupported and must be downgraded or removed.")

    if len(selected_runs) == 1:
        warnings.append("Only one completed run is available; do not present it as a full project-level paper.")
        return True, False, "technical_report", "single_run_report", blockers, warnings

    stable_supported = [
        item
        for item in ledger.stable_conclusions
        if item.evidence_refs and item.paper_claim_allowed
    ]
    if stable_supported and not blockers:
        if reviewer_average_score >= 7.0:
            return True, True, "conference_candidate", "project_level_paper", blockers, warnings
        return True, True, "workshop_candidate", "project_level_paper", blockers, warnings
    if ledger.conditional_conclusions and not blockers:
        warnings.append("Evidence is cross-run but conditional; keep the manuscript at workshop or technical-report strength.")
        return True, False, "workshop_candidate", "project_level_paper", blockers, warnings

    blockers.append("Selected runs do not yet yield supported stable or conditional project conclusions.")
    return False, False, "do_not_write", "no_paper", blockers, warnings


def build_project_paper_orchestration(project_id: str) -> AutoResearchProjectPaperOrchestrationRead:
    briefs = list_research_briefs(project_id)
    latest_brief: AutoResearchResearchBriefRead | None = briefs[0] if briefs else None
    runs = list_runs(project_id)
    meta = build_cross_run_meta_analysis(project_id)
    selected_runs = _selected_runs(runs=runs, meta_analysis=meta)
    ledger = _build_conclusion_ledger(
        project_id=project_id,
        selected_runs=selected_runs,
        meta_analysis=meta,
    )
    traces = _trace_claims(ledger, selected_runs=selected_runs)
    reviewer_count, reviewer_average = _reviewer_average(selected_runs)
    (
        should_write,
        project_level_allowed,
        paper_decision,
        source_strategy,
        blockers,
        decision_warnings,
    ) = _decision(
        selected_runs=selected_runs,
        ledger=ledger,
        traces=traces,
        reviewer_average_score=reviewer_average,
    )
    warnings = _dedupe(meta.warnings + decision_warnings)
    if meta.blockers and len(selected_runs) < 2:
        warnings.extend(meta.blockers)
    supported = [trace for trace in traces if trace.support_status == "supported"]
    unsupported = [trace for trace in traces if trace.support_status == "unsupported"]
    next_actions = []
    if not project_level_allowed and len(selected_runs) < 2:
        next_actions.append("Run at least one additional selected hypothesis before claiming a project-level paper.")
    if unsupported:
        next_actions.append("Downgrade or remove unsupported project-level claims.")
    if not any(run.reviewer_simulation is not None for run in selected_runs):
        next_actions.append("Run reviewer simulation before project-level submission packaging.")
    if not blockers and should_write:
        next_actions.append("Draft project-level paper sections from the conclusion ledger.")

    payload = {
        "orchestrator_id": "project_paper_orchestrator_v1",
        "project_id": project_id,
        "brief_count": len(briefs),
        "latest_brief_id": latest_brief.brief_id if latest_brief is not None else None,
        "latest_brief_selected_hypothesis_id": (
            latest_brief.selected_hypothesis_id if latest_brief is not None else None
        ),
        "candidate_run_count": len([run for run in runs if run.status == "done"]),
        "selected_run_ids": [run.id for run in selected_runs],
        "selected_run_count": len(selected_runs),
        "meta_analysis": meta.model_dump(mode="json"),
        "conclusion_ledger": ledger.model_dump(mode="json"),
        "claim_traces": [trace.model_dump(mode="json") for trace in traces],
        "core_claim_count": len(traces),
        "supported_core_claim_count": len(supported),
        "unsupported_core_claim_count": len(unsupported),
        "reviewer_simulation_count": reviewer_count,
        "reviewer_average_score": reviewer_average,
        "should_write_paper": should_write and not blockers,
        "project_level_paper_allowed": project_level_allowed and not blockers,
        "paper_decision": "do_not_write" if blockers and not should_write else paper_decision,
        "paper_tier": _paper_tier_from_decision(paper_decision),
        "source_strategy": source_strategy,
        "project_publish_gate_passed": project_level_allowed and not blockers and not unsupported,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "next_actions": _dedupe(next_actions),
    }
    return AutoResearchProjectPaperOrchestrationRead(
        generated_at=_utcnow(),
        orchestration_fingerprint=_fingerprint(payload),
        **payload,
    )
