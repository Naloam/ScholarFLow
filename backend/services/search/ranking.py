from __future__ import annotations

from schemas.papers import PaperMeta


SOURCE_WEIGHT = {
    "semantic_scholar": 1.0,
    "arxiv": 0.9,
    "crossref": 0.8,
}


def score_item(item: PaperMeta) -> float:
    score = SOURCE_WEIGHT.get(item.source or "", 0.5)
    if item.doi:
        score += 0.2
    if item.abstract:
        score += 0.1
    if item.year:
        score += 0.01 * min(5, max(0, item.year - 2018))
    return score


def rank_items(items: list[PaperMeta]) -> list[PaperMeta]:
    for item in items:
        item.source_weight = SOURCE_WEIGHT.get(item.source or "", 0.5)
        item.score = score_item(item)
    return sorted(items, key=lambda x: x.score or 0.0, reverse=True)
