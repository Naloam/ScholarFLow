from __future__ import annotations

import re


STAGES = ["outline", "literature", "method", "results", "discussion", "final"]


def infer_stage(content: str) -> str:
    text = content.lower()
    has_related = "related work" in text or "literature" in text
    has_method = "method" in text
    has_results = "results" in text
    has_discussion = "discussion" in text
    has_conclusion = "conclusion" in text
    has_refs = "references" in text

    if has_conclusion and has_refs:
        return "final"
    if has_discussion:
        return "discussion"
    if has_results:
        return "results"
    if has_method:
        return "method"
    if has_related:
        return "literature"
    return "outline"


def needs_evidence_count(content: str) -> int:
    return len(re.findall(r"\[NEEDS_EVIDENCE\]", content))
