from __future__ import annotations

from dataclasses import dataclass
import re
from statistics import mean

from sqlalchemy.orm import Session

from schemas.analysis import SimilarityMatch, SimilaritySummary
from services.evidence.repository import list_evidence_items
from services.papers.repository import list_papers


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n+")
MIN_PARAGRAPH_TOKENS = 12
MAX_MATCHES = 5


@dataclass(frozen=True)
class SimilaritySource:
    source_type: str
    source_label: str
    paper_id: str | None
    paper_title: str | None
    text: str


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _excerpt(text: str, limit: int = 220) -> str:
    compact = _normalize_whitespace(text)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _is_cjk_token(token: str) -> bool:
    return len(token) == 1 and "\u4e00" <= token <= "\u9fff"


def _shingle_size(tokens: list[str]) -> int:
    if not tokens:
        return 5
    cjk_tokens = sum(1 for token in tokens if _is_cjk_token(token))
    if cjk_tokens >= max(8, len(tokens) // 2):
        return 8
    if len(tokens) >= 30:
        return 5
    return 4


def _shingles(tokens: list[str], size: int) -> set[str]:
    if len(tokens) <= size:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def _split_paragraphs(content: str) -> list[str]:
    paragraphs: list[str] = []
    for block in PARAGRAPH_SPLIT_PATTERN.split(content):
        paragraph = _normalize_whitespace(block)
        if not paragraph:
            continue
        if paragraph.startswith("#"):
            continue
        if len(_tokenize(paragraph)) < MIN_PARAGRAPH_TOKENS:
            continue
        paragraphs.append(paragraph)
    return paragraphs


def _collect_sources(db: Session, project_id: str) -> list[SimilaritySource]:
    papers = list_papers(db, project_id)
    paper_titles = {paper.id: paper.title for paper in papers if paper.id}

    sources: list[SimilaritySource] = []
    seen_texts: set[str] = set()

    for item in list_evidence_items(db, project_id):
        snippet = _normalize_whitespace(item.snippet or "")
        if len(_tokenize(snippet)) < MIN_PARAGRAPH_TOKENS:
            continue
        dedupe_key = f"evidence:{snippet.lower()}"
        if dedupe_key in seen_texts:
            continue
        seen_texts.add(dedupe_key)
        paper_title = paper_titles.get(item.paper_id)
        section = item.section or "snippet"
        label = paper_title or item.paper_id or "Evidence source"
        sources.append(
            SimilaritySource(
                source_type="evidence_snippet",
                source_label=f"{label} · {section}",
                paper_id=item.paper_id,
                paper_title=paper_title,
                text=snippet,
            )
        )

    for paper in papers:
        abstract = _normalize_whitespace(paper.abstract or "")
        if len(_tokenize(abstract)) < MIN_PARAGRAPH_TOKENS:
            continue
        dedupe_key = f"abstract:{abstract.lower()}"
        if dedupe_key in seen_texts:
            continue
        seen_texts.add(dedupe_key)
        label = paper.title or paper.id or "Paper abstract"
        sources.append(
            SimilaritySource(
                source_type="paper_abstract",
                source_label=f"{label} · abstract",
                paper_id=paper.id,
                paper_title=paper.title,
                text=abstract,
            )
        )

    return sources


def _best_match(paragraph: str, sources: list[SimilaritySource]) -> SimilarityMatch | None:
    paragraph_tokens = _tokenize(paragraph)
    if len(paragraph_tokens) < MIN_PARAGRAPH_TOKENS:
        return None
    paragraph_shingle_size = _shingle_size(paragraph_tokens)
    paragraph_shingles = _shingles(paragraph_tokens, paragraph_shingle_size)
    if not paragraph_shingles:
        return None

    best_match: SimilarityMatch | None = None
    best_score = 0.0
    for source in sources:
        source_tokens = _tokenize(source.text)
        if len(source_tokens) < paragraph_shingle_size:
            continue
        source_shingles = _shingles(source_tokens, paragraph_shingle_size)
        if not source_shingles:
            continue
        overlap = len(paragraph_shingles & source_shingles)
        if overlap == 0:
            continue
        score = overlap / len(paragraph_shingles)
        if score <= best_score:
            continue
        best_score = score
        best_match = SimilarityMatch(
            source_type=source.source_type,
            source_label=source.source_label,
            paper_id=source.paper_id,
            paper_title=source.paper_title,
            similarity=round(score, 4),
            overlap_units=max(1, round(score * len(paragraph_tokens))),
            draft_excerpt=_excerpt(paragraph),
            source_excerpt=_excerpt(source.text),
        )

    return best_match


def _is_flagged(match: SimilarityMatch) -> bool:
    return match.similarity >= 0.35 and match.overlap_units >= 8


def build_similarity_summary(db: Session, project_id: str, content: str) -> SimilaritySummary:
    paragraphs = _split_paragraphs(content)
    if not paragraphs:
        return SimilaritySummary(
            checked_paragraphs=0,
            flagged_paragraphs=0,
            max_similarity=0.0,
            average_similarity=0.0,
            status="clear",
            matches=[],
        )

    sources = _collect_sources(db, project_id)
    if not sources:
        return SimilaritySummary(
            checked_paragraphs=len(paragraphs),
            flagged_paragraphs=0,
            max_similarity=0.0,
            average_similarity=0.0,
            status="clear",
            matches=[],
        )

    best_matches = [match for paragraph in paragraphs if (match := _best_match(paragraph, sources)) is not None]
    if not best_matches:
        return SimilaritySummary(
            checked_paragraphs=len(paragraphs),
            flagged_paragraphs=0,
            max_similarity=0.0,
            average_similarity=0.0,
            status="clear",
            matches=[],
        )

    flagged_matches = [match for match in best_matches if _is_flagged(match)]
    max_similarity = max(match.similarity for match in best_matches)
    average_similarity = mean(match.similarity for match in best_matches)
    if max_similarity >= 0.75 or len(flagged_matches) >= 3:
        status = "high"
    elif flagged_matches:
        status = "warning"
    else:
        status = "clear"

    return SimilaritySummary(
        checked_paragraphs=len(paragraphs),
        flagged_paragraphs=len(flagged_matches),
        max_similarity=round(max_similarity, 4),
        average_similarity=round(average_similarity, 4),
        status=status,
        matches=sorted(flagged_matches, key=lambda match: match.similarity, reverse=True)[:MAX_MATCHES],
    )
