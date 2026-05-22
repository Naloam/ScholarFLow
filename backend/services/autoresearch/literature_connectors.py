from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import UTC, datetime
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

_ARXIV_API = "http://export.arxiv.org/api/query"
_SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
_CROSSREF_API = "https://api.crossref.org/works"
_ARXIV_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

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
    paper_id: str,
    title: str,
    query: str | None,
    brief: AutoResearchResearchBriefRead | None,
    cache_status: str,
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
) -> AutoResearchLiteratureScoutPaperRead:
    text = " ".join(part for part in [title, abstract or "", venue or ""] if part)
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
    return AutoResearchLiteratureScoutPaperRead(
        paper_id=paper_id,
        title=_norm(title) or "Untitled paper",
        source=source,
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
        relevance_score=relevance_score,
        novelty_risk_signal=_risk_signal(overlap_score, reported_results, known_sota),
        overlap_score=overlap_score,
        shared_terms=shared_terms[:12],
        source_query=query,
        cache_status=cache_status,  # type: ignore[arg-type]
        evidence="; ".join(part for part in evidence_parts if part) + ".",
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
                paper_id=f"arxiv:{arxiv_id}" if arxiv_id else _stable_id("arxiv", title),
                title=title,
                query=query,
                brief=brief,
                cache_status=cache_status,
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
                paper_id=_stable_id("semantic_scholar", str(raw_id)),
                title=title,
                query=query,
                brief=brief,
                cache_status=cache_status,
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
                paper_id=_stable_id("crossref", doi or title),
                title=title,
                query=query,
                brief=brief,
                cache_status=cache_status,
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
                paper_id=f"fixture_literature_{index}_{_slug(direction.direction_id)}",
                title=title,
                query=query,
                brief=brief,
                cache_status="fixture",
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
) -> list[AutoResearchLiteratureScoutPaperRead]:
    if source == ARXIV_SOURCE:
        return parse_arxiv_response(
            str(raw),
            query=query,
            brief=brief,
            cache_status=cache_status,
        )
    if source == SEMANTIC_SCHOLAR_SOURCE:
        return parse_semantic_scholar_response(
            raw,
            query=query,
            brief=brief,
            cache_status=cache_status,
        )
    if source == CROSSREF_SOURCE:
        return parse_crossref_response(
            raw,
            query=query,
            brief=brief,
            cache_status=cache_status,
        )
    return []


def _raw_from_cache(payload: dict[str, object]) -> object:
    if "raw" in payload:
        return payload["raw"]
    if "response" in payload:
        return payload["response"]
    return payload


def _arxiv_query(query: str) -> str:
    terms = [term for term in _terms(query)][:5]
    if not terms:
        return f'all:"{query}"'
    return " AND ".join(f'all:"{term}"' for term in terms[:4])


def _fetch_connector_response(source: str, query: str, *, limit: int) -> object:
    if source == ARXIV_SOURCE:
        params = {
            "search_query": _arxiv_query(query),
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        with httpx.Client(timeout=20.0) as client:
            response = client.get(_ARXIV_API, params=params)
            response.raise_for_status()
            return response.text
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
        with httpx.Client(timeout=20.0) as client:
            response = client.get(_SEMANTIC_SCHOLAR_API, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    if source == CROSSREF_SOURCE:
        headers: dict[str, str] = {}
        if settings.crossref_api_key:
            headers["Crossref-Plus-API-Token"] = f"Bearer {settings.crossref_api_key}"
        params = {
            "query": query,
            "rows": limit,
        }
        with httpx.Client(timeout=20.0) as client:
            response = client.get(_CROSSREF_API, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    return {}


def _merge_duplicate_papers(
    existing: AutoResearchLiteratureScoutPaperRead,
    incoming: AutoResearchLiteratureScoutPaperRead,
) -> AutoResearchLiteratureScoutPaperRead:
    methods = _dedupe([*existing.methods, existing.method, *incoming.methods, incoming.method])
    datasets = _dedupe([*existing.datasets, *incoming.datasets])
    metrics = _dedupe([*existing.metrics, *incoming.metrics])
    reported_results = _dedupe([*existing.reported_results, *incoming.reported_results])
    shared_terms = _dedupe([*existing.shared_terms, *incoming.shared_terms])
    return existing.model_copy(
        update={
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
            "known_sota": existing.known_sota or incoming.known_sota,
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
            "evidence": f"{existing.evidence} Duplicate metadata also found via {incoming.source}.",
        }
    )


def deduplicate_literature_papers(
    papers: Iterable[AutoResearchLiteratureScoutPaperRead],
) -> list[AutoResearchLiteratureScoutPaperRead]:
    deduped: list[AutoResearchLiteratureScoutPaperRead] = []
    index_by_key: dict[str, int] = {}
    for paper in papers:
        title_key = re.sub(r"[^a-z0-9]+", " ", paper.title.lower()).strip()
        key = (
            f"doi:{paper.doi.lower()}"
            if paper.doi
            else f"arxiv:{paper.arxiv_id.lower()}"
            if paper.arxiv_id
            else f"title:{title_key}"
        )
        if not title_key and not paper.doi and not paper.arxiv_id:
            continue
        if key in index_by_key:
            index = index_by_key[key]
            deduped[index] = _merge_duplicate_papers(deduped[index], paper)
            continue
        index_by_key[key] = len(deduped)
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
    selected_sources = list(sources or DEFAULT_CONNECTOR_SOURCES)
    queries = search_queries[: max(1, min(len(search_queries), 4))]
    for source in selected_sources:
        status = AutoResearchLiteratureScoutSourceStatusRead(source=source)
        if source == "fixture":
            status.query_count = 1
            fixture_papers = fixture_literature_papers(brief, query=queries[0] if queries else None)
            status.paper_count = len(fixture_papers)
            papers.extend(fixture_papers)
            statuses.append(status)
            continue

        for query in queries:
            status.query_count += 1
            raw: object | None = None
            cache_status = "cache_hit"
            if cache_enabled:
                cached = load_literature_scout_cache(
                    brief.project_id,
                    source=source,
                    query=query,
                    limit=limit_per_source,
                )
                if cached is not None:
                    status.cache_hit_count += 1
                    raw = _raw_from_cache(cached)
            if raw is None and network_enabled:
                try:
                    raw = _fetch_connector_response(source, query, limit=limit_per_source)
                    cache_status = "network"
                    status.network_request_count += 1
                    if cache_enabled:
                        save_literature_scout_cache(
                            brief.project_id,
                            source=source,
                            query=query,
                            limit=limit_per_source,
                            payload={
                                "fetched_at": _utcnow().isoformat(),
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
            )
            status.paper_count += len(parsed)
            papers.extend(parsed)
        statuses.append(status)

    return deduplicate_literature_papers(papers), statuses
