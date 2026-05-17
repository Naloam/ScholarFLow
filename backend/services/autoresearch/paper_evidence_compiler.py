from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

from schemas.autoresearch import (
    AutoResearchClaimEvidenceEntryRead,
    AutoResearchClaimEvidenceMatrixRead,
    AutoResearchClaimEvidenceRefRead,
    AutoResearchClaimSupportStatus,
    AutoResearchPaperClaimLedgerEntryRead,
    AutoResearchPaperCompileReportRead,
    AutoResearchPaperContradictionRead,
    AutoResearchPaperParagraphEvidenceRead,
    AutoResearchPaperPlanRead,
    AutoResearchPaperTier,
    AutoResearchPaperUnregisteredClaimRead,
    AutoResearchRunRead,
    ResultArtifact,
)


_SECTION_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$")
_CLAIM_ID_PATTERN = re.compile(r"\bclaim_[a-z0-9_:-]+\b", re.IGNORECASE)
_STRONG_CLAIM_CUES = (
    "outperform",
    "outperforms",
    "outperformed",
    "improve",
    "improves",
    "improved",
    "improvement",
    "significant",
    "statistically significant",
    "robust",
    "strongest",
    "best-performing",
    "highest",
    "demonstrate",
    "demonstrates",
    "establish",
    "establishes",
    "contribution",
    "novel",
    "new ",
)
_UNREGISTERED_CLAIM_CUES = (
    "we show",
    "we demonstrate",
    "we prove",
    "we find",
    "our results show",
    "our experiments demonstrate",
    "this work presents",
    "this paper presents",
    "the results establish",
    "significantly outperforms",
    "outperforms",
    "improves",
    "achieves the highest",
    "achieves the strongest",
)
_OVERCLAIM_CUES = (
    "significantly outperform",
    "statistically significant",
    "robust",
    "generalizable",
    "generalise",
    "generalize",
    "state-of-the-art",
    "sota",
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "this",
    "to",
    "with",
    "we",
    "were",
    "will",
}
_NEGATIVE_SECTION_IDS = {"limitations", "discussion"}
_ARTIFACT_EVIDENCE_SOURCE_KINDS = {"artifact", "plan", "portfolio", "attempts"}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "section"


def _terms(value: str) -> set[str]:
    return {
        item
        for item in re.findall(r"[a-z0-9]+", value.lower())
        if len(item) >= 4 and item not in _STOPWORDS
    }


def _section_slug(title: str) -> str:
    normalized = re.sub(r"^\d+\.\s+", "", title.strip())
    return _slug(normalized)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _split_sections(paper_markdown: str) -> dict[str, tuple[str, str]]:
    sections: dict[str, tuple[str, str]] = {}
    current_id: str | None = None
    current_title: str | None = None
    current_lines: list[str] = []
    for raw_line in paper_markdown.splitlines():
        match = _SECTION_HEADING_PATTERN.match(raw_line.strip())
        if match:
            if current_id is not None and current_title is not None:
                sections[current_id] = (current_title, "\n".join(current_lines).strip())
            current_title = re.sub(r"^\d+\.\s+", "", match.group(1).strip())
            current_id = _section_slug(current_title)
            current_lines = []
            continue
        if current_id is not None:
            current_lines.append(raw_line)
    if current_id is not None and current_title is not None:
        sections[current_id] = (current_title, "\n".join(current_lines).strip())
    return sections


def _paragraphs(section_text: str) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        if line.startswith("|") or re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            paragraphs.append(line)
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current).strip())
    return [item for item in paragraphs if item]


def _evidence_kinds_for_refs(
    refs: list[AutoResearchClaimEvidenceRefRead],
    *,
    section_id: str,
) -> list[str]:
    kinds: list[str] = []
    if any(ref.source_kind in _ARTIFACT_EVIDENCE_SOURCE_KINDS for ref in refs):
        kinds.append("artifact")
    if any("significance" in f"{ref.label} {ref.detail}".lower() for ref in refs):
        kinds.append("statistic")
    if any(ref.source_kind == "literature" for ref in refs):
        kinds.append("literature")
    if section_id in _NEGATIVE_SECTION_IDS and any(
        term in f"{ref.label} {ref.detail}".lower()
        for ref in refs
        for term in ("negative", "failed", "limitation", "gap", "not ")
    ):
        kinds.append("negative")
    return sorted(set(kinds))


def _entry_evidence_kinds(
    entry: AutoResearchClaimEvidenceEntryRead,
    *,
    section_id: str,
) -> list[str]:
    return _evidence_kinds_for_refs(entry.evidence, section_id=section_id)


def _strong_claim(entry: AutoResearchClaimEvidenceEntryRead) -> bool:
    if entry.category not in {"method", "result", "context"}:
        return False
    lowered = entry.claim.lower()
    return entry.support_status != "unsupported" and any(cue in lowered for cue in _STRONG_CLAIM_CUES)


def _support_rank(status: AutoResearchClaimSupportStatus) -> int:
    return {"unsupported": 0, "partial": 1, "supported": 2}[status]


def _merge_support_status(statuses: list[AutoResearchClaimSupportStatus]) -> AutoResearchClaimSupportStatus:
    if not statuses:
        return "unsupported"
    return min(statuses, key=_support_rank)


def _section_plan_claim_ids(
    paper_plan: AutoResearchPaperPlanRead | None,
) -> dict[str, list[str]]:
    if paper_plan is None:
        return {}
    return {
        section.section_id or _section_slug(section.title): list(section.claim_ids)
        for section in paper_plan.sections
    }


def _section_title_map(
    paper_plan: AutoResearchPaperPlanRead | None,
) -> dict[str, str]:
    if paper_plan is None:
        return {}
    return {
        section.section_id or _section_slug(section.title): section.title
        for section in paper_plan.sections
    }


def _claim_ids_for_paragraph(
    paragraph: str,
    *,
    section_id: str,
    planned_claim_ids: dict[str, list[str]],
    claims_by_id: dict[str, AutoResearchClaimEvidenceEntryRead],
) -> list[str]:
    explicit = [item.lower() for item in _CLAIM_ID_PATTERN.findall(paragraph)]
    claim_ids = [item for item in explicit if item in claims_by_id]
    if claim_ids:
        return sorted(set(claim_ids))
    paragraph_terms = _terms(paragraph)
    if section_id == "references" or not paragraph_terms:
        return []
    matched: list[str] = []
    for entry in claims_by_id.values():
        claim_terms = _terms(entry.claim)
        if not claim_terms:
            continue
        overlap = paragraph_terms & claim_terms
        if len(overlap) >= 2 or len(overlap) / max(len(claim_terms), 1) >= 0.3:
            matched.append(entry.claim_id)
    if matched:
        return sorted(set(matched))
    planned = planned_claim_ids.get(section_id, [])
    return [item for item in planned if item in claims_by_id]


def _paragraph_has_unregistered_claim(paragraph: str) -> bool:
    lowered = paragraph.lower()
    return any(cue in lowered for cue in _UNREGISTERED_CLAIM_CUES)


def _registered_claim_mentioned(
    paragraph: str,
    *,
    claim_ids: list[str],
    claims_by_id: dict[str, AutoResearchClaimEvidenceEntryRead],
) -> bool:
    lowered = paragraph.lower()
    if any(claim_id.lower() in lowered for claim_id in claim_ids):
        return True
    for claim_id in claim_ids:
        claim = claims_by_id[claim_id].claim.lower()
        important_terms = [
            item
            for item in re.findall(r"[a-z][a-z0-9_]+", claim)
            if len(item) >= 6
        ]
        if important_terms and sum(1 for term in important_terms[:8] if term in lowered) >= 2:
            return True
    return False


def _artifact_has_positive_statistical_support(artifact: ResultArtifact | None) -> bool:
    if artifact is None:
        return False
    return any(item.significant for item in artifact.significance_tests)


def _artifact_has_negative_evidence(artifact: ResultArtifact | None) -> bool:
    if artifact is None:
        return False
    return bool(artifact.negative_results or artifact.failed_trials)


def _unsupported_claim_overreach(
    paragraph: str,
    *,
    section_id: str,
    claim_ids: list[str],
    claims_by_id: dict[str, AutoResearchClaimEvidenceEntryRead],
) -> AutoResearchPaperContradictionRead | None:
    lowered = paragraph.lower()
    if section_id not in {"abstract", "conclusion", "discussion", "results"}:
        return None
    unsupported = [
        claims_by_id[item]
        for item in claim_ids
        if item in claims_by_id and claims_by_id[item].support_status != "supported"
    ]
    if not unsupported:
        return None
    if not any(cue in lowered for cue in _OVERCLAIM_CUES):
        return None
    claim = unsupported[0]
    severity = "blocker" if section_id in {"abstract", "conclusion"} else "warning"
    return AutoResearchPaperContradictionRead(
        contradiction_id=f"contradiction_{section_id}_{claim.claim_id}",
        section_id=section_id,
        section_title=section_id.replace("_", " ").title(),
        severity=severity,
        claim_id=claim.claim_id,
        summary="Paper text states a stronger claim than the claim ledger supports.",
        detail=(
            f"Section `{section_id}` uses strong wording while `{claim.claim_id}` is "
            f"{claim.support_status}: {claim.claim}"
        ),
    )


def _global_overclaim(
    paragraph: str,
    *,
    section_id: str,
    artifact: ResultArtifact | None,
) -> AutoResearchPaperContradictionRead | None:
    if section_id not in {"abstract", "conclusion"}:
        return None
    lowered = paragraph.lower()
    has_statistical_phrase = "statistically significant" in lowered or "significantly outperform" in lowered
    if has_statistical_phrase and not _artifact_has_positive_statistical_support(artifact):
        return AutoResearchPaperContradictionRead(
            contradiction_id=f"contradiction_{section_id}_statistical_overclaim",
            section_id=section_id,
            section_title=section_id.replace("_", " ").title(),
            severity="blocker",
            summary="Abstract or conclusion claims statistical support that is not present.",
            detail="The paper uses significance language, but the artifact has no positive significance test.",
        )
    if "without limitation" in lowered or "generalizable" in lowered or "generalizes" in lowered:
        return AutoResearchPaperContradictionRead(
            contradiction_id=f"contradiction_{section_id}_scope_overclaim",
            section_id=section_id,
            section_title=section_id.replace("_", " ").title(),
            severity="warning",
            summary="Abstract or conclusion overstates scope beyond bounded results.",
            detail="The paper uses broad generalization language; final paper text must stay bounded to executed evidence.",
        )
    return None


def _paper_tier(
    *,
    evidence_bound_count: int,
    unbound_count: int,
    registered_strong_claim_count: int,
    contradiction_count: int,
    blocker_count: int,
    artifact: ResultArtifact | None,
    literature_count: int,
    negative_evidence_count: int,
) -> AutoResearchPaperTier:
    if blocker_count or contradiction_count or unbound_count:
        return "technical_report"
    if registered_strong_claim_count < 1 or evidence_bound_count < 3:
        return "technical_report"
    if (
        artifact is not None
        and len(artifact.significance_tests) > 0
        and literature_count > 0
        and negative_evidence_count > 0
        and registered_strong_claim_count >= 2
    ):
        return "strong_conference_candidate"
    if artifact is not None and len(artifact.significance_tests) > 0 and literature_count > 0:
        return "conference_candidate"
    return "workshop_candidate"


def compile_paper_evidence(
    report: AutoResearchPaperCompileReportRead,
    *,
    run: AutoResearchRunRead | None = None,
    paper_markdown: str | None = None,
    paper_plan: AutoResearchPaperPlanRead | None = None,
    claim_evidence_matrix: AutoResearchClaimEvidenceMatrixRead | None = None,
    artifact: ResultArtifact | None = None,
    literature_count: int | None = None,
) -> AutoResearchPaperCompileReportRead:
    """Attach P4 claim-evidence compiler output to the compile report."""
    if run is not None:
        paper_markdown = paper_markdown if paper_markdown is not None else run.paper_markdown
        paper_plan = paper_plan if paper_plan is not None else run.paper_plan
        claim_evidence_matrix = claim_evidence_matrix if claim_evidence_matrix is not None else run.claim_evidence_matrix
        artifact = artifact if artifact is not None else run.artifact
        literature_count = len(run.literature) if literature_count is None else literature_count

    matrix = claim_evidence_matrix
    markdown = paper_markdown or ""
    literature_count = int(literature_count or 0)
    if matrix is None or paper_plan is None or not markdown.strip():
        blockers = ["Paper evidence compiler requires paper markdown, paper plan, and claim ledger."]
        payload = {
            "paper_tier": "technical_report",
            "blockers": blockers,
            "paragraph_evidence": [],
            "claim_ledger": [],
            "unregistered_claims": [],
            "contradictions": [],
        }
        return report.model_copy(
            update={
                "paper_tier": "technical_report",
                "evidence_bound_paragraph_count": 0,
                "evidence_unbound_paragraph_count": 0,
                "strong_claim_count": 0,
                "registered_strong_claim_count": 0,
                "unregistered_claim_count": 0,
                "contradiction_count": 0,
                "blocker_count": len(blockers),
                "paragraph_evidence": [],
                "claim_ledger": [],
                "unregistered_claims": [],
                "contradictions": [],
                "evidence_blockers": blockers,
                "evidence_warnings": [],
                "evidence_compiler_fingerprint": _fingerprint(payload),
            }
        )

    claims_by_id = {entry.claim_id.lower(): entry for entry in matrix.entries}
    planned_claim_ids = _section_plan_claim_ids(paper_plan)
    planned_titles = _section_title_map(paper_plan)
    sections = _split_sections(markdown)
    paragraph_evidence: list[AutoResearchPaperParagraphEvidenceRead] = []
    unregistered_claims: list[AutoResearchPaperUnregisteredClaimRead] = []
    contradictions: list[AutoResearchPaperContradictionRead] = []
    ledger_sections: dict[str, set[str]] = defaultdict(set)
    ledger_paragraphs: dict[str, set[str]] = defaultdict(set)
    ledger_evidence_kinds: dict[str, set[str]] = defaultdict(set)

    for section_id, (section_title, body) in sections.items():
        if section_id == "references":
            continue
        for index, paragraph in enumerate(_paragraphs(body), start=1):
            paragraph_id = f"{section_id}_p{index}"
            claim_ids = _claim_ids_for_paragraph(
                paragraph,
                section_id=section_id,
                planned_claim_ids=planned_claim_ids,
                claims_by_id=claims_by_id,
            )
            entries = [claims_by_id[item] for item in claim_ids if item in claims_by_id]
            refs = [
                ref
                for entry in entries
                for ref in entry.evidence
            ]
            evidence_kinds = _evidence_kinds_for_refs(refs, section_id=section_id)
            if section_id in _NEGATIVE_SECTION_IDS and _artifact_has_negative_evidence(artifact):
                evidence_kinds = sorted(set([*evidence_kinds, "negative"]))
            missing: list[str] = []
            if entries and not any(kind in evidence_kinds for kind in ("artifact", "statistic", "literature", "negative")):
                missing.append("artifact")
            if any(entry.category == "context" for entry in entries) and "literature" not in evidence_kinds:
                missing.append("literature")
            if section_id in _NEGATIVE_SECTION_IDS and _artifact_has_negative_evidence(artifact) and "negative" not in evidence_kinds:
                missing.append("negative")
            support_status = _merge_support_status([entry.support_status for entry in entries])
            if not entries:
                support_status = "unsupported"
            for claim_id in claim_ids:
                ledger_sections[claim_id].add(section_id)
                ledger_paragraphs[claim_id].add(paragraph_id)
                ledger_evidence_kinds[claim_id].update(evidence_kinds)

            paragraph_evidence.append(
                AutoResearchPaperParagraphEvidenceRead(
                    paragraph_id=paragraph_id,
                    section_id=section_id,
                    section_title=section_title,
                    paragraph_index=index,
                    excerpt=paragraph[:300],
                    claim_ids=claim_ids,
                    evidence_kinds=evidence_kinds,  # type: ignore[arg-type]
                    evidence_refs=refs,
                    missing_evidence_kinds=sorted(set(missing)),  # type: ignore[arg-type]
                    support_status=support_status,
                )
            )
            if _paragraph_has_unregistered_claim(paragraph) and not _registered_claim_mentioned(
                paragraph,
                claim_ids=claim_ids,
                claims_by_id=claims_by_id,
            ):
                unregistered_claims.append(
                    AutoResearchPaperUnregisteredClaimRead(
                        claim_id=f"unregistered_{section_id}_{index}",
                        section_id=section_id,
                        section_title=section_title,
                        excerpt=paragraph[:300],
                        reason="Strong paper claim wording does not map to a registered claim id or ledger claim text.",
                    )
                )
            contradiction = _unsupported_claim_overreach(
                paragraph,
                section_id=section_id,
                claim_ids=claim_ids,
                claims_by_id=claims_by_id,
            )
            if contradiction is not None:
                contradictions.append(contradiction.model_copy(update={"section_title": section_title}))
            global_contradiction = _global_overclaim(
                paragraph,
                section_id=section_id,
                artifact=artifact,
            )
            if global_contradiction is not None:
                contradictions.append(global_contradiction.model_copy(update={"section_title": section_title}))

    claim_ledger: list[AutoResearchPaperClaimLedgerEntryRead] = []
    strong_claim_count = 0
    registered_strong_claim_count = 0
    for entry in matrix.entries:
        claim_id = entry.claim_id.lower()
        strong = _strong_claim(entry)
        if strong:
            strong_claim_count += 1
        if strong and ledger_paragraphs.get(claim_id):
            registered_strong_claim_count += 1
        claim_ledger.append(
            AutoResearchPaperClaimLedgerEntryRead(
                claim_id=entry.claim_id,
                claim=entry.claim,
                category=entry.category,
                section_ids=sorted(ledger_sections.get(claim_id, set())),
                paragraph_ids=sorted(ledger_paragraphs.get(claim_id, set())),
                support_status=entry.support_status,
                evidence_kinds=sorted(ledger_evidence_kinds.get(claim_id, set())),  # type: ignore[arg-type]
                evidence_count=len(entry.evidence),
                strong=strong,
            )
        )

    evidence_bound_count = sum(
        1
        for item in paragraph_evidence
        if item.claim_ids and item.evidence_refs and not item.missing_evidence_kinds
    )
    unbound_count = sum(
        1
        for item in paragraph_evidence
        if item.claim_ids and (not item.evidence_refs or item.missing_evidence_kinds)
    )
    blocker_messages: list[str] = []
    warning_messages: list[str] = []
    if unregistered_claims:
        blocker_messages.append(
            f"Paper contains {len(unregistered_claims)} strong claim paragraph(s) not present in the claim ledger."
        )
    blocker_contradictions = [item for item in contradictions if item.severity == "blocker"]
    if blocker_contradictions:
        blocker_messages.append(
            f"Paper contains {len(blocker_contradictions)} abstract/conclusion contradiction(s) or overclaims."
        )
    if unbound_count:
        blocker_messages.append(
            f"Paper has {unbound_count} claim-bearing paragraph(s) without complete evidence binding."
        )
    if registered_strong_claim_count < strong_claim_count:
        warning_messages.append(
            f"Registered strong claims used in paper={registered_strong_claim_count}/{strong_claim_count}."
        )
    if contradictions and not blocker_contradictions:
        warning_messages.append(
            f"Paper contains {len(contradictions)} claim-strength warning(s)."
        )

    negative_evidence_count = len(artifact.negative_results) + len(artifact.failed_trials) if artifact is not None else 0
    tier = _paper_tier(
        evidence_bound_count=evidence_bound_count,
        unbound_count=unbound_count,
        registered_strong_claim_count=registered_strong_claim_count,
        contradiction_count=len(contradictions),
        blocker_count=len(blocker_messages),
        artifact=artifact,
        literature_count=literature_count,
        negative_evidence_count=negative_evidence_count,
    )
    payload = {
        "paper_tier": tier,
        "evidence_bound_paragraph_count": evidence_bound_count,
        "evidence_unbound_paragraph_count": unbound_count,
        "strong_claim_count": strong_claim_count,
        "registered_strong_claim_count": registered_strong_claim_count,
        "unregistered_claims": [item.model_dump(mode="json") for item in unregistered_claims],
        "contradictions": [item.model_dump(mode="json") for item in contradictions],
        "claim_ledger": [item.model_dump(mode="json") for item in claim_ledger],
        "blockers": blocker_messages,
        "warnings": warning_messages,
    }
    return report.model_copy(
        update={
            "paper_tier": tier,
            "evidence_bound_paragraph_count": evidence_bound_count,
            "evidence_unbound_paragraph_count": unbound_count,
            "strong_claim_count": strong_claim_count,
            "registered_strong_claim_count": registered_strong_claim_count,
            "unregistered_claim_count": len(unregistered_claims),
            "contradiction_count": len(contradictions),
            "blocker_count": len(blocker_messages),
            "paragraph_evidence": paragraph_evidence,
            "claim_ledger": claim_ledger,
            "unregistered_claims": unregistered_claims,
            "contradictions": contradictions,
            "evidence_blockers": blocker_messages,
            "evidence_warnings": warning_messages,
            "evidence_compiler_fingerprint": _fingerprint(payload),
        }
    )
