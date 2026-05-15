from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from schemas.autoresearch import (
    AutoResearchClaimEvidenceEntryRead,
    AutoResearchClaimStrength,
    AutoResearchContributionAssessmentRead,
    AutoResearchContributionClaimRead,
    AutoResearchContributionType,
    AutoResearchNoveltyAssessmentRead,
    AutoResearchNoveltyRiskRead,
    AutoResearchPublicationReadinessRead,
    AutoResearchRunRead,
    HypothesisCandidate,
)


_CLAIM_STRENGTH_ORDER: dict[AutoResearchClaimStrength, int] = {
    "unsupported": 0,
    "weakly_supported": 1,
    "artifact_supported": 2,
    "statistically_supported": 3,
    "literature_positioned": 4,
}
_SYNTHETIC_LITERATURE_SOURCES = {
    "ai_generated",
    "ai_generated_context",
    "benchmark_context",
    "fallback",
    "generated",
    "mock",
    "synthetic",
}
_GENERIC_EXPERIMENT_TERMS = {
    "experiment",
    "experiments",
    "run",
    "runs",
    "ran",
    "execute",
    "executed",
    "execution",
    "test",
    "tests",
    "testing",
    "evaluate",
    "evaluates",
    "evaluated",
    "evaluation",
    "result",
    "results",
    "metric",
    "metrics",
    "benchmark",
    "benchmarks",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _norm_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:80] or "claim"


def _terms(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _real_literature_count(run: AutoResearchRunRead) -> int:
    return sum(
        1
        for item in run.literature
        if (item.source or "").strip().lower() not in _SYNTHETIC_LITERATURE_SOURCES
        and not (item.paper_id or "").strip().lower().startswith("context_ref_")
        and not item.title.strip().lower().startswith("[context summary]")
    )


def _selected_candidate(run: AutoResearchRunRead) -> HypothesisCandidate | None:
    selected_id = run.portfolio.selected_candidate_id if run.portfolio is not None else None
    if selected_id:
        found = next((item for item in run.candidates if item.id == selected_id), None)
        if found is not None:
            return found
    return next((item for item in run.candidates if item.selected_round_index is not None), None)


def _classify_contribution(
    text: str,
    *,
    entry: AutoResearchClaimEvidenceEntryRead | None = None,
) -> AutoResearchContributionType:
    lowered = text.lower()
    if any(term in lowered for term in ("benchmark", "dataset", "corpus", "task suite", "testbed")):
        return "new_benchmark"
    if any(term in lowered for term in ("system", "pipeline", "platform", "framework", "tool", "workflow")):
        return "new_system"
    if entry is not None and entry.category == "method":
        return "new_method"
    if any(term in lowered for term in ("method", "algorithm", "model", "rerank", "ranker", "classifier", "policy")):
        return "new_method"
    if any(term in lowered for term in ("analysis", "ablation", "taxonomy", "diagnostic", "failure mode")):
        return "analysis_framework"
    return "experimental_finding"


def _strongest_strength(*strengths: AutoResearchClaimStrength) -> AutoResearchClaimStrength:
    return max(strengths, key=lambda item: _CLAIM_STRENGTH_ORDER[item])


def _entry_strength(
    entry: AutoResearchClaimEvidenceEntryRead,
    *,
    has_done_artifact: bool,
    significance_test_count: int,
    real_literature_count: int,
) -> AutoResearchClaimStrength:
    if entry.support_status == "unsupported":
        return "unsupported"
    evidence_kinds = {item.source_kind for item in entry.evidence}
    if real_literature_count > 0 and "literature" in evidence_kinds:
        return "literature_positioned"
    if entry.support_status == "partial":
        return "weakly_supported"
    if significance_test_count > 0 and "artifact" in evidence_kinds and entry.category in {"method", "result"}:
        return "statistically_supported"
    if has_done_artifact and "artifact" in evidence_kinds:
        return "artifact_supported"
    if evidence_kinds:
        return "weakly_supported"
    return "unsupported"


def _planned_claim_strength(
    *,
    has_done_artifact: bool,
    significance_test_count: int,
    real_literature_count: int,
) -> AutoResearchClaimStrength:
    if real_literature_count > 0 and significance_test_count > 0:
        return "literature_positioned"
    if significance_test_count > 0:
        return "statistically_supported"
    if has_done_artifact:
        return "artifact_supported"
    return "weakly_supported"


def _substantive_contribution(text: str) -> bool:
    terms = _terms(text)
    if len(terms) < 4:
        return False
    return bool(terms - _GENERIC_EXPERIMENT_TERMS)


def _claim_rationale(
    *,
    strength: AutoResearchClaimStrength,
    contribution_type: AutoResearchContributionType,
    evidence_sources: list[str],
) -> str:
    source_text = ", ".join(evidence_sources) if evidence_sources else "no explicit evidence source"
    if strength == "literature_positioned":
        return (
            f"Classified as {contribution_type}; the claim is tied to experiment evidence and persisted real literature "
            f"({source_text})."
        )
    if strength == "statistically_supported":
        return (
            f"Classified as {contribution_type}; the claim has artifact evidence plus preserved statistical tests "
            f"({source_text})."
        )
    if strength == "artifact_supported":
        return f"Classified as {contribution_type}; the claim is supported by a completed artifact ({source_text})."
    if strength == "weakly_supported":
        return f"Classified as {contribution_type}; the claim is stated but lacks strong statistical or literature grounding."
    return f"Classified as {contribution_type}; the claim is unsupported by the persisted run state."


def _add_or_merge_claim(
    claims_by_text: dict[str, AutoResearchContributionClaimRead],
    claim: AutoResearchContributionClaimRead,
) -> None:
    key = _norm_text(claim.text).lower()
    existing = claims_by_text.get(key)
    if existing is None:
        claims_by_text[key] = claim
        return
    strength = _strongest_strength(existing.claim_strength, claim.claim_strength)
    evidence_sources = sorted(set(existing.evidence_sources + claim.evidence_sources))
    claims_by_text[key] = existing.model_copy(
        update={
            "claim_strength": strength,
            "core": existing.core or claim.core,
            "evidence_sources": evidence_sources,
            "rationale": _claim_rationale(
                strength=strength,
                contribution_type=existing.contribution_type,
                evidence_sources=evidence_sources,
            ),
        }
    )


def _planned_contribution_claims(
    run: AutoResearchRunRead,
    *,
    strength: AutoResearchClaimStrength,
) -> list[AutoResearchContributionClaimRead]:
    selected = _selected_candidate(run)
    candidates: list[tuple[str, list[str]]] = []
    if run.plan is not None:
        candidates.extend(("plan", item) for item in run.plan.planned_contributions)
    if selected is not None:
        candidates.extend(("portfolio", item) for item in selected.planned_contributions)

    claims: list[AutoResearchContributionClaimRead] = []
    seen: set[str] = set()
    for index, (source, text) in enumerate(candidates, start=1):
        normalized = _norm_text(text)
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        contribution_type = _classify_contribution(normalized)
        evidence_sources = [source]
        if strength in {"artifact_supported", "statistically_supported", "literature_positioned"}:
            evidence_sources.append("artifact")
        if strength == "literature_positioned":
            evidence_sources.append("literature")
        claims.append(
            AutoResearchContributionClaimRead(
                claim_id=f"contribution_plan_{index}_{_slug(normalized)}",
                text=normalized,
                contribution_type=contribution_type,
                claim_strength=strength,
                core=True,
                evidence_sources=sorted(set(evidence_sources)),
                rationale=_claim_rationale(
                    strength=strength,
                    contribution_type=contribution_type,
                    evidence_sources=sorted(set(evidence_sources)),
                ),
            )
        )
    return claims


def _matrix_contribution_claims(
    run: AutoResearchRunRead,
    *,
    has_done_artifact: bool,
    significance_test_count: int,
    real_literature_count: int,
) -> list[AutoResearchContributionClaimRead]:
    matrix = run.claim_evidence_matrix
    if matrix is None:
        return []
    claims: list[AutoResearchContributionClaimRead] = []
    for index, entry in enumerate(matrix.entries, start=1):
        if entry.category == "limitation":
            continue
        contribution_type = _classify_contribution(entry.claim, entry=entry)
        strength = _entry_strength(
            entry,
            has_done_artifact=has_done_artifact,
            significance_test_count=significance_test_count,
            real_literature_count=real_literature_count,
        )
        evidence_sources = sorted({item.source_kind for item in entry.evidence})
        core = entry.category in {"method", "result"} and index <= 8
        claims.append(
            AutoResearchContributionClaimRead(
                claim_id=entry.claim_id,
                text=_norm_text(entry.claim),
                contribution_type=contribution_type,
                claim_strength=strength,
                core=core,
                evidence_sources=evidence_sources,
                rationale=_claim_rationale(
                    strength=strength,
                    contribution_type=contribution_type,
                    evidence_sources=evidence_sources,
                ),
            )
        )
    return claims


def _novelty_risks(
    *,
    claims: list[AutoResearchContributionClaimRead],
    run: AutoResearchRunRead,
    real_literature_count: int,
    novelty_assessment: AutoResearchNoveltyAssessmentRead | None,
) -> list[AutoResearchNoveltyRiskRead]:
    risks: list[AutoResearchNoveltyRiskRead] = []
    if real_literature_count < 1:
        risks.append(
            AutoResearchNoveltyRiskRead(
                risk_id="risk_no_real_literature",
                risk_type="literature_gap",
                severity="high",
                summary="No real literature evidence is available for contribution positioning.",
                detail=(
                    "The run may have results, but duplicate and incremental novelty risk cannot be audited without "
                    "persisted real paper records."
                ),
                evidence_refs=["run_json"],
            )
        )
    if claims and not any(item.claim_strength == "literature_positioned" for item in claims):
        risks.append(
            AutoResearchNoveltyRiskRead(
                risk_id="risk_unpositioned_contributions",
                risk_type="incremental_risk",
                severity="medium",
                summary="Contribution claims are not positioned against literature.",
                detail=(
                    "At least one core contribution should be explicitly connected to prior work before final publish."
                ),
                evidence_refs=["run_contribution_assessment_json", "run_claim_evidence_matrix_json"],
            )
        )
    unsupported = [item for item in claims if item.claim_strength == "unsupported"]
    if unsupported:
        risks.append(
            AutoResearchNoveltyRiskRead(
                risk_id="risk_unsupported_contribution_claims",
                risk_type="claim_overreach",
                severity="high",
                summary="Some contribution claims are unsupported.",
                detail=f"{len(unsupported)} contribution claim(s) lack artifact, statistical, or literature support.",
                evidence_refs=["run_claim_evidence_matrix_json"],
            )
        )
    if novelty_assessment is not None and novelty_assessment.status in {"weak", "incremental"}:
        risks.append(
            AutoResearchNoveltyRiskRead(
                risk_id=f"risk_novelty_assessment_{novelty_assessment.status}",
                risk_type="duplicate_risk" if novelty_assessment.status == "weak" else "incremental_risk",
                severity="high" if novelty_assessment.status == "weak" else "medium",
                summary="Novelty assessment raises a publish-facing risk.",
                detail=novelty_assessment.summary,
                evidence_refs=["run_json", "run_paper_markdown"],
            )
        )
    if run.claim_evidence_matrix is None:
        risks.append(
            AutoResearchNoveltyRiskRead(
                risk_id="risk_missing_claim_evidence_matrix",
                risk_type="evidence_gap",
                severity="high",
                summary="No claim-evidence matrix is available for contribution auditing.",
                detail="Contribution claims cannot be safely compared with artifact and literature evidence.",
                evidence_refs=["run_claim_evidence_matrix_json"],
            )
        )
    return risks


def _publishability_score(
    *,
    readiness: AutoResearchPublicationReadinessRead | None,
    clear_contribution_count: int,
    strong_core_claim_count: int,
    artifact_supported_claim_count: int,
    statistically_supported_claim_count: int,
    literature_positioned_claim_count: int,
    novelty_risks: list[AutoResearchNoveltyRiskRead],
) -> int:
    score = 0
    if readiness is not None:
        score += round(readiness.score * 0.25)
    score += min(clear_contribution_count, 2) * 15
    score += min(strong_core_claim_count, 2) * 20
    score += min(artifact_supported_claim_count, 2) * 5
    score += min(statistically_supported_claim_count, 2) * 10
    score += min(literature_positioned_claim_count, 2) * 12
    for risk in novelty_risks:
        score -= 15 if risk.severity == "high" else 8 if risk.severity == "medium" else 3
    return max(0, min(100, score))


def build_contribution_assessment(
    run: AutoResearchRunRead,
    *,
    publication_readiness: AutoResearchPublicationReadinessRead | None = None,
    novelty_assessment: AutoResearchNoveltyAssessmentRead | None = None,
) -> AutoResearchContributionAssessmentRead:
    artifact = run.artifact
    has_done_artifact = artifact is not None and artifact.status == "done"
    significance_test_count = len(artifact.significance_tests) if artifact is not None else 0
    real_lit_count = _real_literature_count(run)
    planned_strength = _planned_claim_strength(
        has_done_artifact=has_done_artifact,
        significance_test_count=significance_test_count,
        real_literature_count=real_lit_count,
    )
    claims_by_text: dict[str, AutoResearchContributionClaimRead] = {}
    for claim in _planned_contribution_claims(run, strength=planned_strength):
        _add_or_merge_claim(claims_by_text, claim)
    for claim in _matrix_contribution_claims(
        run,
        has_done_artifact=has_done_artifact,
        significance_test_count=significance_test_count,
        real_literature_count=real_lit_count,
    ):
        _add_or_merge_claim(claims_by_text, claim)

    claims = sorted(
        claims_by_text.values(),
        key=lambda item: (
            not item.core,
            -_CLAIM_STRENGTH_ORDER[item.claim_strength],
            item.claim_id,
        ),
    )
    clear_claims = [
        item
        for item in claims
        if item.core
        and item.claim_strength != "unsupported"
        and _substantive_contribution(item.text)
    ]
    strong_core_claims = [
        item
        for item in clear_claims
        if item.claim_strength in {"statistically_supported", "literature_positioned"}
    ]
    artifact_supported_claim_count = sum(
        1
        for item in claims
        if item.claim_strength
        in {"artifact_supported", "statistically_supported", "literature_positioned"}
    )
    statistically_supported_claim_count = sum(
        1 for item in claims if item.claim_strength == "statistically_supported"
    )
    literature_positioned_claim_count = sum(
        1 for item in claims if item.claim_strength == "literature_positioned"
    )
    risks = _novelty_risks(
        claims=claims,
        run=run,
        real_literature_count=real_lit_count,
        novelty_assessment=novelty_assessment,
    )

    blockers: list[str] = []
    if not claims:
        blockers.append(
            "Final publish requires explicit contribution claims; completed experiments alone are not a contribution."
        )
    if not clear_claims:
        blockers.append(
            "Final publish cannot rely on completed experiments alone; it requires at least one clear, substantive contribution claim tied to the run evidence."
        )
    if not strong_core_claims:
        blockers.append(
            "Final publish requires at least one core contribution claim with statistically_supported or literature_positioned strength."
        )

    warnings = [risk.summary for risk in risks if risk.severity != "high"]
    payload = {
        "assessment_id": "contribution_assessment_v1",
        "contribution_claims": [item.model_dump(mode="json") for item in claims],
        "novelty_risks": [item.model_dump(mode="json") for item in risks],
        "clear_contribution_count": len(clear_claims),
        "strong_core_claim_count": len(strong_core_claims),
        "artifact_supported_claim_count": artifact_supported_claim_count,
        "statistically_supported_claim_count": statistically_supported_claim_count,
        "literature_positioned_claim_count": literature_positioned_claim_count,
        "blockers": blockers,
        "warnings": warnings,
        "complete": not blockers,
    }
    score = _publishability_score(
        readiness=publication_readiness,
        clear_contribution_count=len(clear_claims),
        strong_core_claim_count=len(strong_core_claims),
        artifact_supported_claim_count=artifact_supported_claim_count,
        statistically_supported_claim_count=statistically_supported_claim_count,
        literature_positioned_claim_count=literature_positioned_claim_count,
        novelty_risks=risks,
    )
    payload["publishability_score"] = score
    return AutoResearchContributionAssessmentRead(
        generated_at=_utcnow(),
        assessment_fingerprint=_fingerprint(payload),
        **payload,
    )
