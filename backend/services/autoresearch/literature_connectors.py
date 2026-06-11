from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from config.settings import settings
from schemas.autoresearch import (
    AutoResearchLiteratureScoutPaperRead,
    AutoResearchLiteratureScoutSourceStatusRead,
    AutoResearchNoveltyRiskLevel,
    AutoResearchResearchBriefRead,
)
from services.autoresearch.repository import (
    literature_scout_cache_key,
    load_literature_scout_cache,
    save_literature_scout_cache,
)


ARXIV_SOURCE = "arxiv"
SEMANTIC_SCHOLAR_SOURCE = "semantic_scholar"
CROSSREF_SOURCE = "crossref"
FIXTURE_SOURCE = "fixture_offline"

DEFAULT_CONNECTOR_SOURCES = (
    "fixture",
    ARXIV_SOURCE,
    SEMANTIC_SCHOLAR_SOURCE,
    CROSSREF_SOURCE,
)
SUPPORTED_CONNECTOR_SOURCES = set(DEFAULT_CONNECTOR_SOURCES)
_SYNTHETIC_SOURCES = {FIXTURE_SOURCE, "fixture", "offline_project_context"}

_ARXIV_API = "http://export.arxiv.org/api/query"
_SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
_CROSSREF_API = "https://api.crossref.org/works"
_ARXIV_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}
_DEFAULT_CONNECTOR_TIMEOUT_SECONDS = 15.0
_DEFAULT_CONNECTOR_RETRIES = 2
_DEFAULT_CONNECTOR_RETRY_BACKOFF_SECONDS = 0.25
_DEFAULT_CACHE_FRESHNESS_DAYS = 30

_STOPWORDS = {
    "about",
    "against",
    "also",
    "and",
    "based",
    "because",
    "between",
    "candidate",
    "data",
    "dataset",
    "datasets",
    "from",
    "into",
    "method",
    "methods",
    "paper",
    "papers",
    "prior",
    "research",
    "result",
    "results",
    "study",
    "system",
    "systems",
    "that",
    "their",
    "this",
    "through",
    "using",
    "with",
    "work",
}
_METHOD_SIGNAL_TERMS = (
    "algorithm",
    "baseline",
    "classifier",
    "encoder",
    "framework",
    "method",
    "model",
    "pipeline",
    "policy",
    "ranker",
    "rerank",
    "retrieval",
    "transformer",
)
_RESULT_SIGNAL_TERMS = (
    "achieve",
    "achieves",
    "accuracy",
    "auc",
    "best",
    "bleu",
    "f1",
    "improve",
    "improves",
    "mrr",
    "ndcg",
    "outperform",
    "outperforms",
    "precision",
    "recall",
    "reported",
    "rmse",
    "score",
    "state of the art",
    "state-of-the-art",
    "sota",
)
_KNOWN_DATASET_PATTERNS = (
    "BEIR",
    "CIFAR",
    "GLUE",
    "ImageNet",
    "MS MARCO",
    "MIMIC",
    "SQuAD",
    "TREC",
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _norm(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _slug(value: str, *, fallback: str = "paper") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug[:96] or fallback


def _stable_id(prefix: str, value: str) -> str:
    cleaned = _slug(value)
    if cleaned != "paper":
        return f"{prefix}:{cleaned}"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if not isinstance(value, str) or not value.strip():
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _cache_freshness(cache_status: str, cache_timestamp: datetime | str | None) -> str:
    if cache_status in {"offline", "fixture"}:
        return "not_applicable"
    if cache_status == "network":
        return "fresh"
    parsed = _parse_datetime(cache_timestamp)
    if parsed is None:
        return "unknown"
    freshness_days = _env_positive_int(
        "LITERATURE_SCOUT_CACHE_FRESHNESS_DAYS",
        _DEFAULT_CACHE_FRESHNESS_DAYS,
    )
    if _utcnow() - parsed > timedelta(days=freshness_days):
        return "stale"
    return "fresh"


def _claim_ceiling_for_source(
    *,
    source: str,
    cache_status: str,
    cache_freshness: str,
    extraction_status: str,
) -> str:
    if source in _SYNTHETIC_SOURCES or cache_status in {"offline", "fixture"}:
        return "discovery_context_only"
    if cache_freshness == "stale":
        return "stale_cache_discovery_only"
    if cache_freshness == "unknown":
        return "unverified_cache_review_only"
    if extraction_status in {"limited_metadata", "metadata_only", "abstract_only"}:
        return "metadata_or_abstract_review_only"
    return "source_context_review_only"


def _terms(*texts: str | None) -> set[str]:
    terms: set[str] = set()
    for text in texts:
        for raw in re.findall(r"[a-z][a-z0-9_]+", (text or "").lower()):
            if len(raw) < 4 or raw in _STOPWORDS:
                continue
            terms.add(raw)
    return terms


def _dedupe(items: Iterable[str | None]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _norm(item)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _selected_sources(sources: Iterable[str] | None) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for source in sources or DEFAULT_CONNECTOR_SOURCES:
        cleaned = _norm(str(source))
        if cleaned == FIXTURE_SOURCE:
            cleaned = "fixture"
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        selected.append(cleaned)
    return selected


def _selected_queries(search_queries: list[str]) -> list[str]:
    queries = _dedupe(search_queries)
    return queries[:4]


def _brief_text(brief: AutoResearchResearchBriefRead | None) -> str:
    if brief is None:
        return ""
    return " ".join(
        [
            brief.original_idea,
            brief.polished_idea,
            " ".join(brief.research_questions),
            " ".join(brief.candidate_hypotheses),
            " ".join(brief.candidate_datasets),
            " ".join(brief.candidate_metrics),
            " ".join(brief.candidate_baselines),
        ]
    )


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", _norm(text))
    return [part.strip(" .") for part in parts if part.strip(" .")]


def _excerpt(text: str | None, *, limit: int = 720) -> str | None:
    cleaned = _norm(text)
    if not cleaned:
        return None
    return cleaned[:limit].rstrip()


def _metric_alias(metric: str) -> str:
    lowered = metric.lower().replace("-", "_").replace(" ", "_")
    lowered = lowered.replace("macro_f_1", "macro_f1")
    return lowered


def _extract_metrics(text: str, brief: AutoResearchResearchBriefRead | None) -> list[str]:
    lowered = text.lower()
    metrics: list[str] = []
    if brief is not None:
        for metric in brief.candidate_metrics:
            compact = metric.lower().replace("_", " ")
            if metric.lower() in lowered or compact in lowered:
                metrics.append(metric)
    patterns = {
        r"\bmacro[-_ ]?f1\b": "macro_f1",
        r"\bmicro[-_ ]?f1\b": "micro_f1",
        r"\bf1\b": "f1",
        r"\baccuracy\b": "accuracy",
        r"\bprecision\b": "precision",
        r"\brecall\b": "recall",
        r"\bauc\b": "auc",
        r"\brmse\b": "rmse",
        r"\bmrr\b": "mrr",
        r"\bndcg(?:@\d+)?\b": "ndcg",
    }
    for pattern, label in patterns.items():
        if re.search(pattern, lowered):
            metrics.append(label)
    return _dedupe(_metric_alias(item) for item in metrics)[:8]


def _extract_datasets(text: str, brief: AutoResearchResearchBriefRead | None) -> list[str]:
    lowered = text.lower()
    datasets: list[str] = []
    if brief is not None:
        for dataset in brief.candidate_datasets:
            if dataset.lower() in lowered:
                datasets.append(dataset)
    for dataset in _KNOWN_DATASET_PATTERNS:
        if dataset.lower() in lowered:
            datasets.append(dataset)
    for match in re.findall(
        r"\b([A-Z][A-Za-z0-9]+(?: [A-Z][A-Za-z0-9]+){0,4} (?:Benchmark|Dataset|Corpus|Testbed))\b",
        text,
    ):
        datasets.append(match)
    return _dedupe(datasets)[:8]


def _extract_methods(text: str, brief: AutoResearchResearchBriefRead | None) -> list[str]:
    method_candidates: list[str] = []
    if brief is not None:
        for baseline in brief.candidate_baselines:
            if baseline.lower() in text.lower():
                method_candidates.append(baseline)
        for direction in brief.research_directions[:3]:
            sketch_terms = _terms(direction.method_sketch)
            if sketch_terms and sketch_terms & _terms(text):
                method_candidates.append(direction.method_sketch)
    for sentence in _sentences(text):
        lowered = sentence.lower()
        if any(term in lowered for term in _METHOD_SIGNAL_TERMS):
            method_candidates.append(sentence[:180])
    return _dedupe(method_candidates)[:6]


def _extract_reported_results(text: str, metrics: list[str]) -> list[str]:
    result_sentences: list[str] = []
    metric_terms = {metric.lower().replace("_", " ") for metric in metrics}
    for sentence in _sentences(text):
        lowered = sentence.lower()
        if any(term in lowered for term in _RESULT_SIGNAL_TERMS) or any(
            term in lowered for term in metric_terms
        ):
            result_sentences.append(sentence[:220])
    return _dedupe(result_sentences)[:4]


def _extract_known_sota(results: list[str]) -> str | None:
    for sentence in results:
        lowered = sentence.lower()
        if "sota" in lowered or "state of the art" in lowered or "state-of-the-art" in lowered:
            return sentence
    return None


def _risk_signal(
    overlap_score: int,
    reported_results: list[str],
    known_sota: str | None,
) -> AutoResearchNoveltyRiskLevel:
    if known_sota or overlap_score >= 8:
        return "high"
    if reported_results or overlap_score >= 4:
        return "medium"
    return "low"


def _relevance_score(
    *,
    source: str,
    overlap_score: int,
    has_abstract: bool,
    has_identifier: bool,
) -> float:
    source_weight = {
        SEMANTIC_SCHOLAR_SOURCE: 0.24,
        ARXIV_SOURCE: 0.22,
        CROSSREF_SOURCE: 0.18,
        FIXTURE_SOURCE: 0.12,
        "offline_project_context": 0.10,
    }.get(source, 0.10)
    score = source_weight + min(0.52, overlap_score * 0.08)
    if has_abstract:
        score += 0.10
    if has_identifier:
        score += 0.08
    return round(min(1.0, score), 3)


def _make_paper(
    *,
    source: str,
    source_id: str | None = None,
    paper_id: str,
    title: str,
    query: str | None,
    brief: AutoResearchResearchBriefRead | None,
    cache_status: str,
    cache_key: str | None = None,
    cache_timestamp: datetime | str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    venue: str | None = None,
    abstract: str | None = None,
    url: str | None = None,
    doi: str | None = None,
    arxiv_id: str | None = None,
    provided_methods: list[str] | None = None,
    provided_datasets: list[str] | None = None,
    provided_metrics: list[str] | None = None,
    provided_results: list[str] | None = None,
    provided_known_sota: str | None = None,
    full_text: str | None = None,
) -> AutoResearchLiteratureScoutPaperRead:
    full_text_excerpt = _excerpt(full_text)
    extraction_level = "full_text" if full_text_excerpt else "abstract" if abstract else "metadata"
    extraction_status = (
        "full_text"
        if full_text_excerpt
        else "abstract_only"
        if abstract
        else "metadata_only"
        if authors or year or venue or url or doi or arxiv_id
        else "limited_metadata"
    )
    parsed_cache_timestamp = _parse_datetime(cache_timestamp)
    cache_freshness = _cache_freshness(cache_status, cache_timestamp)
    text = " ".join(part for part in [title, abstract or "", full_text_excerpt or "", venue or ""] if part)
    shared_terms = sorted(_terms(_brief_text(brief), query or "") & _terms(text))
    methods = _dedupe([*(provided_methods or []), *_extract_methods(text, brief)])
    datasets = _dedupe([*(provided_datasets or []), *_extract_datasets(text, brief)])
    metrics = _dedupe([*(provided_metrics or []), *_extract_metrics(text, brief)])
    reported_results = _dedupe(
        [*(provided_results or []), *_extract_reported_results(text, metrics)]
    )
    known_sota = provided_known_sota or _extract_known_sota(reported_results)
    overlap_score = len(shared_terms)
    relevance_score = _relevance_score(
        source=source,
        overlap_score=overlap_score,
        has_abstract=bool(abstract),
        has_identifier=bool(doi or arxiv_id),
    )
    evidence_parts = [
        f"Parsed {source} metadata",
        f"query={query}" if query else None,
        f"shared_terms={', '.join(shared_terms[:6])}" if shared_terms else None,
    ]
    cleaned_source_id = _norm(source_id) or _norm(arxiv_id) or _norm(doi) or paper_id
    extraction_limitations = _dedupe(
        [
            "Only limited metadata was available from the connector."
            if extraction_status == "limited_metadata"
            else None,
            "Only bibliographic metadata was available from the connector."
            if extraction_status == "metadata_only"
            else None,
            "Only abstract-level text was available; full-paper verification is required."
            if extraction_status == "abstract_only"
            else None,
            "Cached source observation is stale and cannot support fresh literature claims."
            if cache_freshness == "stale"
            else None,
            "Cached source observation has unknown freshness."
            if cache_freshness == "unknown"
            else None,
        ]
    )
    source_sufficiency_status = (
        "synthetic"
        if source in _SYNTHETIC_SOURCES or cache_status in {"offline", "fixture"}
        else "real_stale"
        if cache_freshness == "stale"
        else "real_unknown_freshness"
        if cache_freshness == "unknown"
        else "real_fresh"
    )
    source_observation_fingerprint = _fingerprint(
        {
            "source": source,
            "source_id": cleaned_source_id,
            "title": _norm(title),
            "url": _norm(url),
            "doi": _norm(doi).lower(),
            "arxiv_id": _norm(arxiv_id),
            "cache_status": cache_status,
            "cache_key": cache_key,
            "cache_timestamp": parsed_cache_timestamp.isoformat()
            if parsed_cache_timestamp is not None
            else None,
            "extraction_status": extraction_status,
        }
    )
    claim_ceiling = _claim_ceiling_for_source(
        source=source,
        cache_status=cache_status,
        cache_freshness=cache_freshness,
        extraction_status=extraction_status,
    )
    paper_fingerprint = _fingerprint(
        {
            "source": source,
            "source_id": cleaned_source_id,
            "title": _norm(title),
            "authors": _dedupe(authors or []),
            "year": year,
            "venue": _norm(venue),
            "abstract": _norm(abstract),
            "url": _norm(url),
            "doi": _norm(doi).lower(),
            "arxiv_id": _norm(arxiv_id),
            "methods": methods,
            "datasets": datasets,
            "metrics": metrics,
            "reported_results": reported_results,
            "known_sota": known_sota,
            "extraction_level": extraction_level,
            "full_text_excerpt": full_text_excerpt,
        }
    )
    return AutoResearchLiteratureScoutPaperRead(
        paper_id=paper_id,
        title=_norm(title) or "Untitled paper",
        source=source,
        source_id=cleaned_source_id,
        authors=_dedupe(authors or []),
        year=year,
        venue=_norm(venue) or None,
        abstract=_norm(abstract) or None,
        url=_norm(url) or None,
        doi=_norm(doi).lower() or None,
        arxiv_id=_norm(arxiv_id) or None,
        method=methods[0] if methods else None,
        methods=methods,
        datasets=datasets,
        metrics=metrics,
        reported_results=reported_results,
        known_sota=known_sota,
        extraction_level=extraction_level,  # type: ignore[arg-type]
        full_text_available=bool(full_text_excerpt),
        full_text_excerpt=full_text_excerpt,
        relevance_score=relevance_score,
        novelty_risk_signal=_risk_signal(overlap_score, reported_results, known_sota),
        overlap_score=overlap_score,
        shared_terms=shared_terms[:12],
        source_query=query,
        cache_status=cache_status,  # type: ignore[arg-type]
        cache_key=cache_key,
        cache_timestamp=parsed_cache_timestamp,
        cache_freshness=cache_freshness,  # type: ignore[arg-type]
        retrieved_at=parsed_cache_timestamp if cache_status in {"cache_hit", "network"} else None,
        connector_provider=source,
        source_observation_fingerprint=source_observation_fingerprint,
        fingerprint=paper_fingerprint,
        extraction_status=extraction_status,  # type: ignore[arg-type]
        extraction_limitations=extraction_limitations,
        source_sufficiency_status=source_sufficiency_status,
        related_system_coverage=[],
        contradiction_signals=[],
        claim_ceiling=claim_ceiling,
        evidence="; ".join(
            [
                *(part for part in evidence_parts if part),
                f"cache_freshness={cache_freshness}",
                f"claim_ceiling={claim_ceiling}",
            ]
        )
        + ".",
    )


def _int_year(raw: Any) -> int | None:
    try:
        if raw is None:
            return None
        value = int(str(raw)[:4])
        if 1500 <= value <= 2500:
            return value
    except (TypeError, ValueError):
        return None
    return None


def _arxiv_id_from_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.rstrip("/").split("/")[-1]
    return cleaned.replace(".pdf", "") or None


def parse_arxiv_response(
    raw: str,
    *,
    query: str | None = None,
    brief: AutoResearchResearchBriefRead | None = None,
    cache_status: str = "cache_hit",
    cache_key: str | None = None,
    cache_timestamp: datetime | str | None = None,
) -> list[AutoResearchLiteratureScoutPaperRead]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []

    papers: list[AutoResearchLiteratureScoutPaperRead] = []
    for entry in root.findall("a:entry", _ARXIV_NS):
        title = _norm(entry.findtext("a:title", default="", namespaces=_ARXIV_NS))
        abstract = _norm(entry.findtext("a:summary", default="", namespaces=_ARXIV_NS))
        url = _norm(entry.findtext("a:id", default="", namespaces=_ARXIV_NS))
        published = _norm(entry.findtext("a:published", default="", namespaces=_ARXIV_NS))
        arxiv_id = _arxiv_id_from_url(url)
        doi = _norm(entry.findtext("arxiv:doi", default="", namespaces=_ARXIV_NS)) or None
        authors = [
            _norm(author.findtext("a:name", default="", namespaces=_ARXIV_NS))
            for author in entry.findall("a:author", _ARXIV_NS)
        ]
        if not title:
            continue
        papers.append(
            _make_paper(
                source=ARXIV_SOURCE,
                source_id=arxiv_id or doi or title,
                paper_id=f"arxiv:{arxiv_id}" if arxiv_id else _stable_id("arxiv", title),
                title=title,
                query=query,
                brief=brief,
                cache_status=cache_status,
                cache_key=cache_key,
                cache_timestamp=cache_timestamp,
                authors=authors,
                year=_int_year(published),
                venue="arXiv",
                abstract=abstract,
                url=url,
                doi=doi,
                arxiv_id=arxiv_id,
            )
        )
    return papers


def _json_payload(raw: object) -> dict[str, Any]:
    if isinstance(raw, str):
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {}
    return raw if isinstance(raw, dict) else {}


def parse_semantic_scholar_response(
    raw: object,
    *,
    query: str | None = None,
    brief: AutoResearchResearchBriefRead | None = None,
    cache_status: str = "cache_hit",
    cache_key: str | None = None,
    cache_timestamp: datetime | str | None = None,
) -> list[AutoResearchLiteratureScoutPaperRead]:
    try:
        payload = _json_payload(raw)
    except json.JSONDecodeError:
        return []
    items = payload.get("data") or []
    papers: list[AutoResearchLiteratureScoutPaperRead] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        title = _norm(str(item.get("title") or ""))
        if not title:
            continue
        authors = [
            _norm(str(author.get("name") or ""))
            for author in item.get("authors", []) or []
            if isinstance(author, dict)
        ]
        external_ids = item.get("externalIds") or {}
        venue_payload = item.get("publicationVenue") or {}
        venue = item.get("venue") or (
            venue_payload.get("name") if isinstance(venue_payload, dict) else None
        )
        doi = item.get("doi") or (
            external_ids.get("DOI") if isinstance(external_ids, dict) else None
        )
        arxiv_id = external_ids.get("ArXiv") if isinstance(external_ids, dict) else None
        raw_id = item.get("paperId") or doi or arxiv_id or title
        papers.append(
            _make_paper(
                source=SEMANTIC_SCHOLAR_SOURCE,
                source_id=str(raw_id),
                paper_id=_stable_id("semantic_scholar", str(raw_id)),
                title=title,
                query=query,
                brief=brief,
                cache_status=cache_status,
                cache_key=cache_key,
                cache_timestamp=cache_timestamp,
                authors=authors,
                year=_int_year(item.get("year")),
                venue=str(venue) if venue else None,
                abstract=str(item.get("abstract") or ""),
                url=str(item.get("url") or ""),
                doi=str(doi) if doi else None,
                arxiv_id=str(arxiv_id) if arxiv_id else None,
            )
        )
    return papers


def _crossref_text(value: Any) -> str | None:
    if isinstance(value, list):
        return _norm(str(value[0])) if value else None
    if isinstance(value, str):
        return _norm(value)
    return None


def _crossref_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = item.get(key, {}).get("date-parts", []) if isinstance(item.get(key), dict) else []
        if parts and isinstance(parts, list) and parts[0]:
            return _int_year(parts[0][0])
    return None


def _clean_crossref_abstract(raw: object) -> str | None:
    text = _norm(str(raw or ""))
    if not text:
        return None
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return _norm(text)


def parse_crossref_response(
    raw: object,
    *,
    query: str | None = None,
    brief: AutoResearchResearchBriefRead | None = None,
    cache_status: str = "cache_hit",
    cache_key: str | None = None,
    cache_timestamp: datetime | str | None = None,
) -> list[AutoResearchLiteratureScoutPaperRead]:
    try:
        payload = _json_payload(raw)
    except json.JSONDecodeError:
        return []
    items = (
        payload.get("message", {}).get("items", [])
        if isinstance(payload.get("message"), dict)
        else []
    )
    papers: list[AutoResearchLiteratureScoutPaperRead] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        title = _crossref_text(item.get("title"))
        if not title:
            continue
        authors: list[str] = []
        for author in item.get("author", []) or []:
            if not isinstance(author, dict):
                continue
            name = _norm(f"{author.get('given', '')} {author.get('family', '')}")
            if name:
                authors.append(name)
        doi = str(item.get("DOI") or "")
        venue = _crossref_text(item.get("container-title"))
        papers.append(
            _make_paper(
                source=CROSSREF_SOURCE,
                source_id=doi or title,
                paper_id=_stable_id("crossref", doi or title),
                title=title,
                query=query,
                brief=brief,
                cache_status=cache_status,
                cache_key=cache_key,
                cache_timestamp=cache_timestamp,
                authors=authors,
                year=_crossref_year(item),
                venue=venue,
                abstract=_clean_crossref_abstract(item.get("abstract")),
                url=str(item.get("URL") or ""),
                doi=doi or None,
            )
        )
    return papers


def fixture_literature_papers(
    brief: AutoResearchResearchBriefRead,
    *,
    query: str | None = None,
) -> list[AutoResearchLiteratureScoutPaperRead]:
    papers: list[AutoResearchLiteratureScoutPaperRead] = []
    for index, direction in enumerate(brief.research_directions[:2], start=1):
        title = f"Fixture prior work for {direction.title}"
        abstract = (
            f"A deterministic offline fixture for {direction.target_task} on "
            f"{direction.candidate_dataset}. It compares "
            f"{', '.join(direction.required_baselines[:2])} "
            f"with candidate methods and reports {direction.primary_metric}."
        )
        papers.append(
            _make_paper(
                source=FIXTURE_SOURCE,
                source_id=f"fixture:{direction.direction_id}",
                paper_id=f"fixture_literature_{index}_{_slug(direction.direction_id)}",
                title=title,
                query=query,
                brief=brief,
                cache_status="fixture",
                cache_key=_fingerprint(
                    {
                        "source": FIXTURE_SOURCE,
                        "query": query,
                        "direction_id": direction.direction_id,
                    }
                ),
                authors=["ScholarFlow fixture"],
                year=2024,
                venue="Deterministic offline fixture",
                abstract=abstract,
                provided_methods=[direction.method_sketch],
                provided_datasets=[direction.candidate_dataset],
                provided_metrics=direction.candidate_metrics,
                provided_results=[
                    f"Fixture baselines report {direction.primary_metric} "
                    "but leave ablation evidence unresolved."
                ],
                provided_known_sota=(
                    f"Known baselines include {', '.join(direction.required_baselines[:2])} "
                    f"for {direction.primary_metric}."
                ),
            )
        )
    return papers


def _parse_response(
    source: str,
    raw: object,
    *,
    query: str,
    brief: AutoResearchResearchBriefRead,
    cache_status: str,
    cache_key: str | None,
    cache_timestamp: datetime | str | None,
) -> list[AutoResearchLiteratureScoutPaperRead]:
    if source == ARXIV_SOURCE:
        return parse_arxiv_response(
            str(raw),
            query=query,
            brief=brief,
            cache_status=cache_status,
            cache_key=cache_key,
            cache_timestamp=cache_timestamp,
        )
    if source == SEMANTIC_SCHOLAR_SOURCE:
        return parse_semantic_scholar_response(
            raw,
            query=query,
            brief=brief,
            cache_status=cache_status,
            cache_key=cache_key,
            cache_timestamp=cache_timestamp,
        )
    if source == CROSSREF_SOURCE:
        return parse_crossref_response(
            raw,
            query=query,
            brief=brief,
            cache_status=cache_status,
            cache_key=cache_key,
            cache_timestamp=cache_timestamp,
        )
    return []


def _raw_from_cache(payload: dict[str, object]) -> object:
    if "raw" in payload:
        return payload["raw"]
    if "response" in payload:
        return payload["response"]
    return payload


def _cache_timestamp(payload: dict[str, object] | None) -> datetime | str | None:
    if payload is None:
        return None
    value = payload.get("cache_timestamp") or payload.get("fetched_at")
    return value if isinstance(value, str) else None


def _cache_full_text(payload: dict[str, object] | None) -> object | None:
    if payload is None:
        return None
    return payload.get("full_text") or payload.get("full_text_by_paper") or payload.get("full_text_by_title")


def _full_text_for_paper(
    payload: object | None,
    paper: AutoResearchLiteratureScoutPaperRead,
) -> str | None:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return None
    keys = [
        paper.paper_id,
        paper.doi,
        paper.arxiv_id,
        paper.title,
        paper.title.lower(),
    ]
    for key in keys:
        if key and isinstance(payload.get(key), str):
            return str(payload[key])
    return None


def _enrich_with_full_text(
    papers: list[AutoResearchLiteratureScoutPaperRead],
    *,
    full_text_payload: object | None,
    query: str,
    brief: AutoResearchResearchBriefRead,
) -> list[AutoResearchLiteratureScoutPaperRead]:
    enriched: list[AutoResearchLiteratureScoutPaperRead] = []
    for paper in papers:
        full_text = _full_text_for_paper(full_text_payload, paper)
        if not full_text:
            enriched.append(paper)
            continue
        enriched.append(
            _make_paper(
                source=paper.source,
                source_id=paper.source_id,
                paper_id=paper.paper_id,
                title=paper.title,
                query=paper.source_query or query,
                brief=brief,
                cache_status=paper.cache_status,
                cache_key=paper.cache_key,
                cache_timestamp=paper.cache_timestamp,
                authors=paper.authors,
                year=paper.year,
                venue=paper.venue,
                abstract=paper.abstract,
                url=paper.url,
                doi=paper.doi,
                arxiv_id=paper.arxiv_id,
                provided_methods=paper.methods,
                provided_datasets=paper.datasets,
                provided_metrics=paper.metrics,
                provided_results=paper.reported_results,
                provided_known_sota=paper.known_sota,
                full_text=full_text,
            )
        )
    return enriched


def _arxiv_query(query: str) -> str:
    terms = [term for term in _terms(query)][:5]
    if not terms:
        return f'all:"{query}"'
    return " AND ".join(f'all:"{term}"' for term in terms[:4])


def _env_positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _connector_timeout() -> httpx.Timeout:
    total = _env_positive_float(
        "LITERATURE_SCOUT_TIMEOUT_SECONDS",
        _DEFAULT_CONNECTOR_TIMEOUT_SECONDS,
    )
    connect = min(total, _env_positive_float("LITERATURE_SCOUT_CONNECT_TIMEOUT_SECONDS", 5.0))
    return httpx.Timeout(total, connect=connect, read=total, write=total, pool=connect)


def _connector_retries() -> int:
    return _env_positive_int("LITERATURE_SCOUT_RETRIES", _DEFAULT_CONNECTOR_RETRIES)


def _retryable_http_error(exc: httpx.HTTPStatusError) -> bool:
    status_code = exc.response.status_code if exc.response is not None else 0
    return status_code == 429 or status_code >= 500


def _with_connector_retries(source: str, query: str, fetch: Any) -> object:
    retries = _connector_retries()
    backoff = _env_positive_float(
        "LITERATURE_SCOUT_RETRY_BACKOFF_SECONDS",
        _DEFAULT_CONNECTOR_RETRY_BACKOFF_SECONDS,
    )
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fetch()
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if not _retryable_http_error(exc) or attempt >= retries:
                break
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            if attempt >= retries:
                break
        if backoff > 0:
            time.sleep(backoff * (2 ** (attempt - 1)))
    detail = str(last_exc) if last_exc is not None else "unknown connector failure"
    raise RuntimeError(
        f"{source} query failed after {retries} attempt(s) for {query!r}: {detail}"
    ) from last_exc


def _fetch_connector_response(source: str, query: str, *, limit: int) -> object:
    if source == ARXIV_SOURCE:
        params = {
            "search_query": _arxiv_query(query),
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        def fetch() -> str:
            with httpx.Client(timeout=_connector_timeout()) as client:
                response = client.get(_ARXIV_API, params=params)
                response.raise_for_status()
                return response.text

        return _with_connector_retries(source, query, fetch)
    if source == SEMANTIC_SCHOLAR_SOURCE:
        headers: dict[str, str] = {}
        if settings.semantic_scholar_api_key:
            headers["x-api-key"] = settings.semantic_scholar_api_key
        params = {
            "query": query,
            "limit": limit,
            "fields": (
                "paperId,title,authors,year,venue,publicationVenue,"
                "abstract,doi,url,externalIds"
            ),
        }
        def fetch() -> object:
            with httpx.Client(timeout=_connector_timeout()) as client:
                response = client.get(_SEMANTIC_SCHOLAR_API, params=params, headers=headers)
                response.raise_for_status()
                return response.json()

        return _with_connector_retries(source, query, fetch)
    if source == CROSSREF_SOURCE:
        headers: dict[str, str] = {}
        if settings.crossref_api_key:
            headers["Crossref-Plus-API-Token"] = f"Bearer {settings.crossref_api_key}"
        params = {
            "query": query,
            "rows": limit,
        }
        def fetch() -> object:
            with httpx.Client(timeout=_connector_timeout()) as client:
                response = client.get(_CROSSREF_API, params=params, headers=headers)
                response.raise_for_status()
                return response.json()

        return _with_connector_retries(source, query, fetch)
    return {}


def _merge_duplicate_papers(
    existing: AutoResearchLiteratureScoutPaperRead,
    incoming: AutoResearchLiteratureScoutPaperRead,
) -> AutoResearchLiteratureScoutPaperRead:
    prefer_incoming_identity = (
        existing.source in _SYNTHETIC_SOURCES
        and incoming.source not in _SYNTHETIC_SOURCES
    )
    methods = _dedupe([*existing.methods, existing.method, *incoming.methods, incoming.method])
    datasets = _dedupe([*existing.datasets, *incoming.datasets])
    metrics = _dedupe([*existing.metrics, *incoming.metrics])
    reported_results = _dedupe([*existing.reported_results, *incoming.reported_results])
    shared_terms = _dedupe([*existing.shared_terms, *incoming.shared_terms])
    extraction_rank = {"metadata": 0, "abstract": 1, "full_text": 2}
    extraction_level = (
        incoming.extraction_level
        if extraction_rank.get(incoming.extraction_level, 0)
        > extraction_rank.get(existing.extraction_level, 0)
        else existing.extraction_level
    )
    freshness_rank = {"not_applicable": 0, "unknown": 1, "stale": 2, "fresh": 3}
    cache_freshness = (
        incoming.cache_freshness
        if freshness_rank.get(incoming.cache_freshness, 0)
        > freshness_rank.get(existing.cache_freshness, 0)
        else existing.cache_freshness
    )
    source_sufficiency_rank = {
        "synthetic": 0,
        "real_stale": 1,
        "real_unknown_freshness": 2,
        "real_fresh": 3,
    }
    source_sufficiency_status = (
        incoming.source_sufficiency_status
        if source_sufficiency_rank.get(incoming.source_sufficiency_status or "", 0)
        > source_sufficiency_rank.get(existing.source_sufficiency_status or "", 0)
        else existing.source_sufficiency_status or incoming.source_sufficiency_status
    )
    return existing.model_copy(
        update={
            "paper_id": incoming.paper_id if prefer_incoming_identity else existing.paper_id,
            "source": incoming.source if prefer_incoming_identity else existing.source,
            "source_id": incoming.source_id if prefer_incoming_identity else existing.source_id or incoming.source_id,
            "authors": _dedupe([*existing.authors, *incoming.authors]),
            "venue": existing.venue or incoming.venue,
            "abstract": existing.abstract or incoming.abstract,
            "url": existing.url or incoming.url,
            "doi": existing.doi or incoming.doi,
            "arxiv_id": existing.arxiv_id or incoming.arxiv_id,
            "method": methods[0] if methods else None,
            "methods": methods,
            "datasets": datasets,
            "metrics": metrics,
            "reported_results": reported_results,
            "known_sota": (
                incoming.known_sota
                if prefer_incoming_identity and incoming.known_sota
                else existing.known_sota or incoming.known_sota
            ),
            "extraction_level": extraction_level,
            "full_text_available": existing.full_text_available or incoming.full_text_available,
            "full_text_excerpt": existing.full_text_excerpt or incoming.full_text_excerpt,
            "relevance_score": max(existing.relevance_score, incoming.relevance_score),
            "novelty_risk_signal": (
                "high"
                if "high" in {existing.novelty_risk_signal, incoming.novelty_risk_signal}
                else "medium"
                if "medium" in {existing.novelty_risk_signal, incoming.novelty_risk_signal}
                else "low"
            ),
            "overlap_score": max(existing.overlap_score, incoming.overlap_score),
            "shared_terms": shared_terms[:12],
            "source_query": (
                incoming.source_query
                if prefer_incoming_identity and incoming.source_query
                else existing.source_query or incoming.source_query
            ),
            "cache_status": incoming.cache_status if prefer_incoming_identity else existing.cache_status,
            "cache_key": incoming.cache_key if prefer_incoming_identity else existing.cache_key or incoming.cache_key,
            "cache_timestamp": incoming.cache_timestamp if prefer_incoming_identity else existing.cache_timestamp or incoming.cache_timestamp,
            "cache_freshness": cache_freshness,
            "retrieved_at": incoming.retrieved_at if prefer_incoming_identity else existing.retrieved_at or incoming.retrieved_at,
            "connector_provider": incoming.connector_provider if prefer_incoming_identity else existing.connector_provider or incoming.connector_provider,
            "source_observation_fingerprint": _fingerprint(
                {
                    "existing": existing.source_observation_fingerprint,
                    "incoming": incoming.source_observation_fingerprint,
                    "cache_freshness": cache_freshness,
                }
            ),
            "fingerprint": _fingerprint(
                {
                    "existing": existing.fingerprint,
                    "incoming": incoming.fingerprint,
                    "methods": methods,
                    "datasets": datasets,
                    "metrics": metrics,
                    "reported_results": reported_results,
                    "extraction_level": extraction_level,
                }
            ),
            "extraction_status": (
                "full_text"
                if extraction_level == "full_text"
                else "abstract_only"
                if extraction_level == "abstract"
                else existing.extraction_status
                if existing.extraction_status != "limited_metadata"
                else incoming.extraction_status
            ),
            "extraction_limitations": _dedupe(
                [*existing.extraction_limitations, *incoming.extraction_limitations]
            ),
            "source_sufficiency_status": source_sufficiency_status,
            "related_system_coverage": _dedupe(
                [*existing.related_system_coverage, *incoming.related_system_coverage]
            ),
            "contradiction_signals": _dedupe(
                [*existing.contradiction_signals, *incoming.contradiction_signals]
            ),
            "claim_ceiling": incoming.claim_ceiling if prefer_incoming_identity else existing.claim_ceiling or incoming.claim_ceiling,
            "evidence": f"{existing.evidence} Duplicate metadata also found via {incoming.source}.",
        }
    )


def deduplicate_literature_papers(
    papers: Iterable[AutoResearchLiteratureScoutPaperRead],
) -> list[AutoResearchLiteratureScoutPaperRead]:
    deduped: list[AutoResearchLiteratureScoutPaperRead] = []
    index_by_key: dict[str, int] = {}
    index_by_title: dict[str, int] = {}
    for paper in papers:
        title_key = re.sub(r"[^a-z0-9]+", " ", paper.title.lower()).strip()
        keys: list[str] = []
        if paper.doi:
            keys.append(f"doi:{paper.doi.lower()}")
        if paper.arxiv_id:
            keys.append(f"arxiv:{paper.arxiv_id.lower()}")
        if title_key:
            keys.append(f"title:{title_key}")
        if not keys:
            continue

        index = next((index_by_key[key] for key in keys if key in index_by_key), None)
        if index is None and title_key:
            index = index_by_title.get(title_key)
        if index is not None:
            deduped[index] = _merge_duplicate_papers(deduped[index], paper)
            for key in keys:
                index_by_key[key] = index
            if title_key:
                index_by_title[title_key] = index
            continue
        index = len(deduped)
        for key in keys:
            index_by_key[key] = index
        if title_key:
            index_by_title[title_key] = index
        deduped.append(paper)
    deduped.sort(
        key=lambda item: (
            -item.relevance_score,
            -item.overlap_score,
            item.source,
            item.title.lower(),
        )
    )
    return deduped


def search_literature_connectors(
    brief: AutoResearchResearchBriefRead,
    *,
    search_queries: list[str],
    sources: Iterable[str] | None = None,
    limit_per_source: int = 3,
    network_enabled: bool = False,
    cache_enabled: bool = True,
) -> tuple[
    list[AutoResearchLiteratureScoutPaperRead],
    list[AutoResearchLiteratureScoutSourceStatusRead],
]:
    papers: list[AutoResearchLiteratureScoutPaperRead] = []
    statuses: list[AutoResearchLiteratureScoutSourceStatusRead] = []
    selected_sources = _selected_sources(sources)
    queries = _selected_queries(search_queries)
    for source in selected_sources:
        status = AutoResearchLiteratureScoutSourceStatusRead(source=source)
        if source not in SUPPORTED_CONNECTOR_SOURCES:
            status.error_count = 1
            status.availability_status = "unsupported"
            status.unavailable_reason = f"Unsupported literature connector source: {source}"
            status.errors.append(f"Unsupported literature connector source: {source}")
            statuses.append(status)
            continue
        if source == "fixture":
            status.query_count = 1
            fixture_papers = fixture_literature_papers(brief, query=queries[0] if queries else None)
            status.paper_count = len(fixture_papers)
            status.cache_freshness_counts = {"not_applicable": len(fixture_papers)}
            status.freshness_policy = "fixture/offline records are deterministic discovery context only."
            papers.extend(fixture_papers)
            statuses.append(status)
            continue

        for query in queries:
            status.query_count += 1
            raw: object | None = None
            cached_payload: dict[str, object] | None = None
            cache_status = "cache_hit"
            cache_key = literature_scout_cache_key(
                source=source,
                query=query,
                limit=limit_per_source,
            )
            cache_timestamp: datetime | str | None = None
            if cache_enabled:
                cached = load_literature_scout_cache(
                    brief.project_id,
                    source=source,
                    query=query,
                    limit=limit_per_source,
                )
                if cached is not None:
                    status.cache_hit_count += 1
                    cached_payload = cached
                    raw = _raw_from_cache(cached)
                    cache_timestamp = _cache_timestamp(cached)
                else:
                    status.cache_miss_count += 1
            if raw is None and network_enabled:
                try:
                    status.network_request_count += 1
                    cache_timestamp = _utcnow().isoformat()
                    raw = _fetch_connector_response(source, query, limit=limit_per_source)
                    cache_status = "network"
                    if cache_enabled:
                        save_literature_scout_cache(
                            brief.project_id,
                            source=source,
                            query=query,
                            limit=limit_per_source,
                            payload={
                                "fetched_at": str(cache_timestamp),
                                "raw": raw,
                            },
                        )
                except Exception as exc:
                    status.error_count += 1
                    status.errors.append(f"{source} query failed: {exc}")
                    continue
            if raw is None:
                continue
            parsed = _parse_response(
                source,
                raw,
                query=query,
                brief=brief,
                cache_status=cache_status,
                cache_key=cache_key,
                cache_timestamp=cache_timestamp,
            )
            parsed = _enrich_with_full_text(
                parsed,
                full_text_payload=_cache_full_text(cached_payload),
                query=query,
                brief=brief,
            )
            for paper in parsed:
                status.cache_freshness_counts[paper.cache_freshness] = (
                    status.cache_freshness_counts.get(paper.cache_freshness, 0) + 1
                )
                if paper.cache_freshness == "stale":
                    status.stale_cache_count += 1
            status.paper_count += len(parsed)
            papers.extend(parsed)
        if status.error_count:
            status.availability_status = "error"
            status.unavailable_reason = "; ".join(status.errors[:3])
        elif status.paper_count > 0:
            status.availability_status = "available"
            status.freshness_policy = (
                f"Cache entries older than {_env_positive_int('LITERATURE_SCOUT_CACHE_FRESHNESS_DAYS', _DEFAULT_CACHE_FRESHNESS_DAYS)} days are stale and cannot support fresh final-publish literature claims."
            )
            if status.stale_cache_count:
                status.availability_blockers.append(
                    f"{status.stale_cache_count} cached {source} record(s) are stale."
                )
        elif status.cache_miss_count and not network_enabled:
            status.availability_status = "cache_miss"
            status.unavailable_reason = (
                f"No cached {source} connector responses were available for this deterministic scout."
            )
            status.availability_blockers.append(status.unavailable_reason)
        else:
            status.availability_status = "unavailable"
            status.unavailable_reason = f"No {source} literature records were available."
            status.availability_blockers.append(status.unavailable_reason)
        statuses.append(status)

    return deduplicate_literature_papers(papers), statuses
