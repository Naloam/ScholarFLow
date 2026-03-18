from __future__ import annotations

import re

from schemas.autoresearch import LiteratureInsight
from schemas.papers import PaperMeta


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "into",
    "using",
    "based",
    "this",
    "these",
    "their",
    "when",
    "where",
    "have",
    "has",
    "over",
    "under",
    "between",
    "through",
    "toward",
    "study",
    "paper",
    "approach",
    "method",
    "results",
}


def _keywords(text: str, limit: int = 4) -> list[str]:
    counts: dict[str, int] = {}
    for token in re.findall(r"[a-z][a-z0-9_]+", (text or "").lower()):
        if token in STOPWORDS or len(token) < 4:
            continue
        counts[token] = counts.get(token, 0) + 1
    items = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [token for token, _ in items[:limit]]


def derive_literature_insights(papers: list[PaperMeta], max_items: int = 5) -> list[LiteratureInsight]:
    insights: list[LiteratureInsight] = []
    for paper in papers[:max_items]:
        title = paper.title or "Untitled paper"
        abstract = paper.abstract or ""
        key_terms = _keywords(f"{title} {abstract}")
        term_phrase = ", ".join(key_terms) if key_terms else "the reported method setting"
        insight = (
            f"{title} emphasizes {term_phrase}."
            if abstract
            else f"{title} provides domain context relevant to the current topic."
        )
        method_hint = (
            f"Borrow lightweight cues around {', '.join(key_terms[:2])}."
            if key_terms
            else None
        )
        gap_hint = (
            f"Test whether a smaller reproducible benchmark preserves signals around {key_terms[-1]}."
            if key_terms
            else None
        )
        insights.append(
            LiteratureInsight(
                paper_id=paper.id,
                title=title,
                year=paper.year,
                source=paper.source,
                insight=insight,
                method_hint=method_hint,
                gap_hint=gap_hint,
            )
        )
    return insights
