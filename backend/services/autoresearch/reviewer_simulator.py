from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from schemas.autoresearch import (
    AutoResearchArtifactIntegrityAuditRead,
    AutoResearchContributionAssessmentRead,
    AutoResearchExperimentDesignRead,
    AutoResearchFailureAnalysisRead,
    AutoResearchLiteratureGraphRead,
    AutoResearchMethodologyAuditRead,
    AutoResearchNoveltyValidationRead,
    AutoResearchPublicationEvidenceIndexRead,
    AutoResearchPublicationReadinessRead,
    AutoResearchReviewerDecision,
    AutoResearchReviewerRole,
    AutoResearchReviewerResponseActionRead,
    AutoResearchReviewerSimulationRead,
    AutoResearchReviewerSimulationReviewRead,
    AutoResearchResearchProtocolRead,
    AutoResearchResearchReplanRead,
    AutoResearchRevisionPriority,
    AutoResearchPaperCompileReportRead,
    AutoResearchRunRead,
)


_ROLES: tuple[AutoResearchReviewerRole, ...] = (
    "novelty_reviewer",
    "methodology_reviewer",
    "reproducibility_reviewer",
    "writing_reviewer",
    "skeptical_reviewer",
)


def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decision_from_score(score: int) -> AutoResearchReviewerDecision:
    if score >= 85:
        return "accept"
    if score >= 75:
        return "weak_accept"
    if score >= 60:
        return "borderline"
    if score >= 45:
        return "weak_reject"
    return "reject"


def _clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(round(value))))


def _publication_blocker_count(review: AutoResearchReviewerSimulationReviewRead) -> int:
    return 1 if review.decision in {"weak_reject", "reject"} else 0


def _novelty_review(
    run: AutoResearchRunRead,
    *,
    literature_graph: AutoResearchLiteratureGraphRead | None = None,
    novelty_validation: AutoResearchNoveltyValidationRead | None = None,
    contribution_assessment: AutoResearchContributionAssessmentRead | None = None,
) -> AutoResearchReviewerSimulationReviewRead:
    novelty = novelty_validation or getattr(run, "novelty_validation", None)
    graph = literature_graph or getattr(run, "literature_graph", None)
    contribution = contribution_assessment or getattr(run, "contribution_assessment", None)
    risks = []
    if novelty is not None:
        risks.extend(novelty.blockers[:2])
        if novelty.duplicate_risk == "high":
            risks.append("Duplicate risk remains high.")
        if novelty.incremental_risk == "high":
            risks.append("Incremental risk remains high.")
    strengths = []
    if graph is not None and graph.known_sota:
        strengths.append("Literature graph enumerates known SOTA and related methods.")
    if contribution is not None and contribution.publishability_score >= 70:
        strengths.append("Contribution assessment identifies a concrete publishable direction.")
    weaknesses = []
    if novelty is None:
        weaknesses.append("Novelty validation is missing.")
    elif novelty.gap_validity in {"missing", "invalid"}:
        weaknesses.append("Validated literature gaps are weak or missing.")
    if contribution is not None and contribution.clear_contribution_count < 1:
        weaknesses.append("No explicit contribution survives novelty screening.")
    score = 86 if strengths and not weaknesses else 72 if strengths else 54
    if weaknesses:
        score -= min(18, len(weaknesses) * 6)
    decision = _decision_from_score(score)
    summary = (
        "Novelty is grounded in the literature graph and contribution assessment."
        if decision in {"accept", "weak_accept"}
        else "Novelty framing needs stronger gap validation."
    )
    return AutoResearchReviewerSimulationReviewRead(
        review_id="review_novelty_reviewer",
        role="novelty_reviewer",
        summary=summary,
        strengths=strengths,
        weaknesses=weaknesses,
        questions=[
            "What exact gap is validated by the literature graph?",
            "How is this contribution different from the nearest known SOTA?",
        ],
        score=_clamp(score),
        confidence=_clamp(80 - len(weaknesses) * 8 + len(strengths) * 4),
        decision=decision,
        reject_reason=weaknesses[0] if decision in {"weak_reject", "reject"} and weaknesses else None,
    )


def _methodology_review(
    run: AutoResearchRunRead,
    *,
    experiment_design: AutoResearchExperimentDesignRead | None = None,
    research_protocol: AutoResearchResearchProtocolRead | None = None,
    methodology_audit: AutoResearchMethodologyAuditRead | None = None,
) -> AutoResearchReviewerSimulationReviewRead:
    design = experiment_design or getattr(run, "experiment_design", None)
    protocol = research_protocol or getattr(run, "research_protocol", None)
    audit = methodology_audit or getattr(run, "methodology_audit", None)
    strengths = []
    weaknesses = []
    if design is not None and design.completeness == "complete":
        strengths.append("Experiment design includes baselines, ablations, seeds, and statistical tests.")
    if protocol is not None and protocol.complete:
        strengths.append("Research protocol is persisted and complete.")
    if audit is not None and audit.compliant:
        strengths.append("Methodology audit passes persisted checks.")
    if design is None:
        weaknesses.append("Experiment design is missing.")
    elif design.fair_baseline_count < 2:
        weaknesses.append("Baseline planning is not fair enough for final publish.")
    if design is not None and design.ablation_coverage < 1.0:
        weaknesses.append("Ablation coverage is incomplete.")
    if protocol is not None and protocol.literature_minimum > 0 and protocol.checks:
        pass
    if audit is not None and not audit.compliant:
        weaknesses.append("Methodology audit does not pass.")
    score = 88 if strengths and not weaknesses else 71 if strengths else 52
    score -= min(20, len(weaknesses) * 5)
    decision = _decision_from_score(score)
    summary = (
        "Methodology is well structured and publication-capable."
        if decision in {"accept", "weak_accept"}
        else "Methodology needs better baseline fairness or ablation support."
    )
    return AutoResearchReviewerSimulationReviewRead(
        review_id="review_methodology_reviewer",
        role="methodology_reviewer",
        summary=summary,
        strengths=strengths,
        weaknesses=weaknesses,
        questions=[
            "Are the baselines fair and sufficiently strong?",
            "Does every component have a corresponding ablation?",
        ],
        score=_clamp(score),
        confidence=_clamp(78 - len(weaknesses) * 7 + len(strengths) * 4),
        decision=decision,
        reject_reason=weaknesses[0] if decision in {"weak_reject", "reject"} and weaknesses else None,
    )


def _reproducibility_review(
    run: AutoResearchRunRead,
    *,
    publication_readiness: AutoResearchPublicationReadinessRead | None = None,
    publication_evidence_index: AutoResearchPublicationEvidenceIndexRead | None = None,
) -> AutoResearchReviewerSimulationReviewRead:
    artifact = run.artifact
    readiness = publication_readiness or getattr(run, "publication_readiness", None)
    evidence_index = publication_evidence_index or getattr(run, "publication_evidence_index", None)
    strengths = []
    weaknesses = []
    if artifact is not None and artifact.significance_tests:
        strengths.append("Artifact preserves significance tests.")
    if artifact is not None and len(artifact.per_seed_results) >= 2:
        strengths.append("Artifact preserves multi-seed results.")
    if evidence_index is not None and evidence_index.complete:
        strengths.append("Publication evidence index is complete.")
    if artifact is None:
        weaknesses.append("Artifact is missing.")
    elif not artifact.significance_tests:
        weaknesses.append("No significance tests are preserved.")
    if artifact is not None and len(artifact.per_seed_results) < 2:
        weaknesses.append("Seed coverage is too thin for stability claims.")
    if readiness is not None and not readiness.final_publish_ready:
        weaknesses.append("Publication readiness is not yet final.")
    score = 90 if strengths and not weaknesses else 68 if strengths else 50
    score -= min(24, len(weaknesses) * 6)
    decision = _decision_from_score(score)
    summary = (
        "Reproducibility package is strong enough for publication."
        if decision in {"accept", "weak_accept"}
        else "Reproducibility package still needs more preserved evidence."
    )
    return AutoResearchReviewerSimulationReviewRead(
        review_id="review_reproducibility_reviewer",
        role="reproducibility_reviewer",
        summary=summary,
        strengths=strengths,
        weaknesses=weaknesses,
        questions=[
            "Are the seeds, sweeps, and significance tests preserved?",
            "Can the result package be reproduced from persisted assets alone?",
        ],
        score=_clamp(score),
        confidence=_clamp(82 - len(weaknesses) * 8 + len(strengths) * 3),
        decision=decision,
        reject_reason=weaknesses[0] if decision in {"weak_reject", "reject"} and weaknesses else None,
    )


def _writing_review(
    run: AutoResearchRunRead,
    *,
    paper_compile_report: AutoResearchPaperCompileReportRead | None = None,
    publication_evidence_index: AutoResearchPublicationEvidenceIndexRead | None = None,
    contribution_assessment: AutoResearchContributionAssessmentRead | None = None,
) -> AutoResearchReviewerSimulationReviewRead:
    report = paper_compile_report or getattr(run, "paper_compile_report", None)
    review = publication_evidence_index or getattr(run, "publication_evidence_index", None)
    strengths = []
    weaknesses = []
    if run.paper_markdown:
        strengths.append("Paper markdown is materialized.")
    if report is not None and report.paper_tier != "technical_report":
        strengths.append(f"Paper tier is {report.paper_tier}.")
    if review is not None and review.complete:
        strengths.append("Evidence index is complete.")
    if report is None:
        weaknesses.append("Paper compile report is missing.")
    elif report.paper_tier == "technical_report":
        weaknesses.append("Paper tier remains technical_report.")
    if report is not None and report.unregistered_claim_count > 0:
        weaknesses.append("Paper contains unregistered claims.")
    if report is not None and report.contradiction_count > 0:
        weaknesses.append("Paper contains contradictions against evidence.")
    score = 84 if strengths and not weaknesses else 70 if strengths else 48
    score -= min(22, len(weaknesses) * 7)
    decision = _decision_from_score(score)
    summary = (
        "Writing is reasonably grounded but can be tightened further."
        if decision in {"accept", "weak_accept"}
        else "Writing overclaims or is not yet publication-ready."
    )
    return AutoResearchReviewerSimulationReviewRead(
        review_id="review_writing_reviewer",
        role="writing_reviewer",
        summary=summary,
        strengths=strengths,
        weaknesses=weaknesses,
        questions=[
            "Does every strong claim map to ledger evidence?",
            "Do abstract and conclusion stay bounded to the results?",
        ],
        score=_clamp(score),
        confidence=_clamp(76 - len(weaknesses) * 7 + len(strengths) * 4),
        decision=decision,
        reject_reason=weaknesses[0] if decision in {"weak_reject", "reject"} and weaknesses else None,
    )


def _skeptical_review(
    run: AutoResearchRunRead,
    *,
    publication_evidence_index: AutoResearchPublicationEvidenceIndexRead | None = None,
    failure_analysis: AutoResearchFailureAnalysisRead | None = None,
    research_replan: AutoResearchResearchReplanRead | None = None,
    contribution_assessment: AutoResearchContributionAssessmentRead | None = None,
    reviewer_simulation: AutoResearchReviewerSimulationRead | None = None,
) -> AutoResearchReviewerSimulationReviewRead:
    evidence_index = publication_evidence_index or getattr(run, "publication_evidence_index", None)
    failure = failure_analysis or getattr(run, "failure_analysis", None)
    replan = research_replan or getattr(run, "research_replan", None)
    contribution = contribution_assessment or getattr(run, "contribution_assessment", None)
    strengths = []
    weaknesses = []
    if failure is not None and failure.publication_blocker_count > 0:
        weaknesses.append("Failure analysis still records publication blockers.")
    if replan is not None and not replan.complete:
        weaknesses.append("Research replan is not complete.")
    if contribution is not None and contribution.blockers:
        weaknesses.append("Contribution assessment still has blockers.")
    evidence_blockers = list(evidence_index.blockers) if evidence_index is not None else []
    self_referential_blockers = [
        item
        for item in evidence_blockers
        if "reviewer_simulation" in item or "Reviewer simulation" in item
    ]
    actionable_evidence_blockers = [
        item for item in evidence_blockers if item not in self_referential_blockers
    ]
    if actionable_evidence_blockers:
        weaknesses.append("Evidence index still has blockers.")
    elif self_referential_blockers:
        strengths.append("Evidence index is otherwise complete aside from the reviewer simulation being generated.")
    if failure is not None and failure.blockers:
        strengths.append("Failure analysis names the concrete blocker paths.")
    if replan is not None and replan.actions:
        strengths.append("Replan produces concrete research actions.")
    score = 78 if strengths and not weaknesses else 58 if strengths else 41
    score -= min(30, len(weaknesses) * 8)
    decision = _decision_from_score(score)
    summary = (
        "The package withstands skeptical review with bounded reservations."
        if decision in {"accept", "weak_accept"}
        else "The package is still too weak for a skeptical publish recommendation."
    )
    reject_reason = None
    if decision in {"weak_reject", "reject"}:
        reject_reason = weaknesses[0] if weaknesses else "Core evidence remains insufficient."
    return AutoResearchReviewerSimulationReviewRead(
        review_id="review_skeptical_reviewer",
        role="skeptical_reviewer",
        summary=summary,
        strengths=strengths,
        weaknesses=weaknesses,
        questions=[
            "What would convince a skeptical reviewer to accept this paper?",
            "Which claims are still stronger than the evidence permits?",
        ],
        score=_clamp(score),
        confidence=_clamp(85 - len(weaknesses) * 6 + len(strengths) * 4),
        decision=decision,
        reject_reason=reject_reason,
    )


def build_reviewer_simulation(
    run: AutoResearchRunRead,
    *,
    experiment_design: AutoResearchExperimentDesignRead | None = None,
    research_protocol: AutoResearchResearchProtocolRead | None = None,
    methodology_audit: AutoResearchMethodologyAuditRead | None = None,
    publication_readiness: AutoResearchPublicationReadinessRead | None = None,
    contribution_assessment: AutoResearchContributionAssessmentRead | None = None,
    novelty_validation: AutoResearchNoveltyValidationRead | None = None,
    literature_graph: AutoResearchLiteratureGraphRead | None = None,
    failure_analysis: AutoResearchFailureAnalysisRead | None = None,
    research_replan: AutoResearchResearchReplanRead | None = None,
    publication_evidence_index: AutoResearchPublicationEvidenceIndexRead | None = None,
    artifact_integrity_audit: AutoResearchArtifactIntegrityAuditRead | None = None,
    paper_compile_report: AutoResearchPaperCompileReportRead | None = None,
) -> AutoResearchReviewerSimulationRead:
    reviews = [
        _novelty_review(
            run,
            literature_graph=literature_graph,
            novelty_validation=novelty_validation,
            contribution_assessment=contribution_assessment,
        ),
        _methodology_review(
            run,
            experiment_design=experiment_design,
            research_protocol=research_protocol,
            methodology_audit=methodology_audit,
        ),
        _reproducibility_review(
            run,
            publication_readiness=publication_readiness,
            publication_evidence_index=publication_evidence_index,
        ),
        _writing_review(
            run,
            paper_compile_report=paper_compile_report,
            publication_evidence_index=publication_evidence_index,
            contribution_assessment=contribution_assessment,
        ),
        _skeptical_review(
            run,
            publication_evidence_index=publication_evidence_index,
            failure_analysis=failure_analysis,
            research_replan=research_replan,
            contribution_assessment=contribution_assessment,
        ),
    ]
    scores = [item.score for item in reviews]
    confidence_scores = [item.confidence for item in reviews]
    response_plan: list[AutoResearchReviewerResponseActionRead] = []
    by_kind: dict[tuple[AutoResearchReviewerRole, AutoResearchReviewerResponseActionKind], AutoResearchReviewerResponseActionRead] = {}

    def add_action(
        *,
        reviewer_role: AutoResearchReviewerRole,
        action_kind: AutoResearchReviewerResponseActionKind,
        priority: AutoResearchRevisionPriority,
        title: str,
        detail: str,
        maps_to: str,
        source_review_ids: list[str],
    ) -> None:
        key = (reviewer_role, action_kind)
        if key in by_kind:
            by_kind[key].source_review_ids = sorted(set([*by_kind[key].source_review_ids, *source_review_ids]))
            return
        action = AutoResearchReviewerResponseActionRead(
            action_id=f"response_{reviewer_role}_{action_kind}_{len(response_plan) + 1}",
            reviewer_role=reviewer_role,
            action_kind=action_kind,
            priority=priority,
            title=title,
            detail=detail,
            maps_to=maps_to,
            source_review_ids=source_review_ids,
        )
        by_kind[key] = action
        response_plan.append(action)

    for review in reviews:
        if review.decision in {"weak_reject", "reject"}:
            add_action(
                reviewer_role=review.role,
                action_kind="evidence" if review.role in {"novelty_reviewer", "reproducibility_reviewer"} else "experiment",
                priority="high",
                title=f"Address {review.role.replace('_', ' ')} concerns",
                detail=review.reject_reason or "Strengthen the evidence package for this reviewer.",
                maps_to="review.revision_plan",
                source_review_ids=[review.review_id],
            )
        elif review.decision == "borderline":
            add_action(
                reviewer_role=review.role,
                action_kind="paper",
                priority="medium",
                title=f"Tighten wording for {review.role.replace('_', ' ')}",
                detail="Reduce claim strength or expose more explicit supporting evidence.",
                maps_to="paper.compile_report",
                source_review_ids=[review.review_id],
            )

    average_score = sum(scores) / len(scores) if scores else 0.0
    minimum_score = min(scores) if scores else 0
    minimum_decision = min((item.decision for item in reviews), key=lambda item: {"accept": 4, "weak_accept": 3, "borderline": 2, "weak_reject": 1, "reject": 0}[item])
    weak_reject_or_worse_count = sum(1 for item in reviews if item.decision in {"weak_reject", "reject"})
    blockers = []
    if weak_reject_or_worse_count > 0:
        blockers.append(
            f"{weak_reject_or_worse_count} reviewer(s) issued weak reject or reject decisions."
        )
    if any(review.reject_reason for review in reviews if review.decision in {"weak_reject", "reject"}):
        blockers.append("Reviewer simulation captured reject reasons that require a replan before publish.")
    if response_plan and weak_reject_or_worse_count == 0 and average_score < 80:
        blockers.append("Response plan is available but the average review score is still below strong publish grade.")
    if weak_reject_or_worse_count > 0 and not response_plan:
        blockers.append("Reviewer simulator identified weak reject decisions but no response plan could be generated.")
    payload = {
        "simulation_id": "reviewer_simulation_v1",
        "project_id": run.project_id,
        "run_id": run.id,
        "selected_candidate_id": run.portfolio.selected_candidate_id if run.portfolio is not None else None,
        "reviews": [item.model_dump(mode="json") for item in reviews],
        "average_score": average_score,
        "minimum_score": minimum_score,
        "minimum_decision": minimum_decision,
        "weak_reject_or_worse_count": weak_reject_or_worse_count,
        "confidence_mean": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0,
        "publication_blocker_count": sum(_publication_blocker_count(item) for item in reviews),
        "response_plan": [item.model_dump(mode="json") for item in response_plan],
        "response_plan_action_count": len(response_plan),
        "complete": not blockers,
        "blockers": blockers,
        "warnings": [] if blockers else ["No weak-reject reviewer decisions were produced."],
    }
    return AutoResearchReviewerSimulationRead(
        generated_at=_utcnow(),
        simulation_fingerprint=_fingerprint(payload),
        **payload,
    )
