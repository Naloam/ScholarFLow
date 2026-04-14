"""Direct ArXiv API search — no extra dependencies needed, uses httpx.

Stolen from ARIS's ArXiv integration pattern: search real papers,
extract structured insights via LLM, and return LiteratureInsight objects.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import httpx

from schemas.autoresearch import LiteratureInsight

logger = logging.getLogger(__name__)

_ARXIV_API = "http://export.arxiv.org/api/query"
_ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}


def _build_query(topic: str, task_family: str) -> str:
    """Build an ArXiv search query from topic and task family."""
    # Extract key terms from topic
    tokens = re.findall(r"[a-z]{4,}", topic.lower())
    # Remove generic stopwords
    stopwords = {
        "using", "based", "study", "analysis", "approach", "method",
        "performance", "evaluation", "comparison", "novel", "improved",
        "efficient", "effective", "proposed", "this", "that", "with",
        "from", "through", "where", "when", "which", "their",
    }
    keywords = [t for t in tokens if t not in stopwords][:5]
    if not keywords:
        keywords = [topic.strip().split()[0].lower()]

    # Add task family domain hint
    domain_map = {
        "text_classification": "text classification",
        "tabular_classification": "tabular data classification",
        "ir_reranking": "information retrieval reranking",
        "llm_evaluation": "large language model evaluation",
    }
    domain = domain_map.get(task_family, "")

    parts = [f'all:"{kw}"' for kw in keywords[:3]]
    if domain:
        parts.append(f'all:"{domain}"')
    return " AND ".join(parts)


def search_arxiv(
    topic: str,
    task_family: str = "text_classification",
    max_results: int = 10,
) -> list[dict]:
    """Search ArXiv and return raw paper metadata."""
    query = _build_query(topic, task_family)
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    try:
        resp = httpx.get(_ARXIV_API, params=params, timeout=30.0)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("arxiv_search: API request failed: %s", exc)
        return []

    papers: list[dict] = []
    try:
        root = ET.fromstring(resp.text)
        for entry in root.findall("a:entry", _ARXIV_NS):
            title_el = entry.find("a:title", _ARXIV_NS)
            summary_el = entry.find("a:summary", _ARXIV_NS)
            published_el = entry.find("a:published", _ARXIV_NS)
            id_el = entry.find("a:id", _ARXIV_NS)

            if title_el is None or summary_el is None:
                continue

            title = " ".join(title_el.text.split()).strip()
            abstract = " ".join(summary_el.text.split()).strip()
            year = None
            if published_el is not None and published_el.text:
                year = int(published_el.text[:4])
            arxiv_id = (id_el.text or "").strip().split("/")[-1] if id_el is not None else ""

            # Get PDF link
            pdf_url = ""
            for link in entry.findall("a:link", _ARXIV_NS):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break

            # Get authors
            authors = []
            for author in entry.findall("a:author", _ARXIV_NS):
                name_el = author.find("a:name", _ARXIV_NS)
                if name_el is not None:
                    authors.append(name_el.text or "")

            papers.append({
                "title": title,
                "abstract": abstract,
                "year": year,
                "arxiv_id": arxiv_id,
                "pdf_url": pdf_url,
                "authors": authors[:5],
                "source": "arxiv",
            })
    except ET.ParseError as exc:
        logger.warning("arxiv_search: XML parse error: %s", exc)
        return []

    logger.info("arxiv_search: found %d papers for query=%r", len(papers), query)
    return papers


def extract_insights_from_arxiv(
    papers: list[dict],
    topic: str,
) -> list[LiteratureInsight]:
    """Use LLM to extract structured insights from ArXiv paper abstracts.

    This is the ARIS pattern: real papers → LLM extracts insight/method_hint/gap_hint.
    """
    if not papers:
        return []

    from services.llm.client import chat
    from services.llm.response_utils import get_message_content
    import json

    paper_texts = []
    for i, p in enumerate(papers[:8], 1):
        authors_str = ", ".join(p.get("authors", [])[:3]) or "Unknown"
        paper_texts.append(
            f"[{i}] {p['title']}\n"
            f"Authors: {authors_str} ({p.get('year', 'n.d.')})\n"
            f"Abstract: {p.get('abstract', 'No abstract available.')}"
        )

    prompt = (
        "You are extracting structured research insights from real academic papers. "
        "For each paper, identify:\n"
        "1. insight: One sentence summarizing the key finding or contribution\n"
        "2. method_hint: What method or technique the paper uses (one phrase)\n"
        "3. gap_hint: What limitation or open question remains (one sentence)\n\n"
        f"Research topic context: {topic}\n\n"
        "Papers:\n" + "\n\n".join(paper_texts) + "\n\n"
        "Return a JSON array with objects: {index, insight, method_hint, gap_hint}.\n"
        "Each insight must be grounded in the paper's actual abstract — do not fabricate."
    )

    try:
        response = chat(
            [
                {"role": "system", "content": "Extract structured insights from academic papers. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = get_message_content(response)
        if not content:
            return []

        m = re.search(r"\[.*\]", content, re.DOTALL)
        if not m:
            return []

        parsed = json.loads(m.group(0))
        insights: list[LiteratureInsight] = []
        for item in parsed:
            idx = item.get("index", 0)
            if idx < 1 or idx > len(papers):
                continue
            paper = papers[idx - 1]
            insights.append(
                LiteratureInsight(
                    paper_id=f"arxiv_{paper.get('arxiv_id', idx)}",
                    title=paper["title"],
                    year=paper.get("year"),
                    source="arxiv",
                    insight=item.get("insight", ""),
                    method_hint=item.get("method_hint"),
                    gap_hint=item.get("gap_hint"),
                )
            )
        return insights
    except Exception as exc:
        logger.warning("extract_insights_from_arxiv: LLM extraction failed: %s", exc)
        # Fallback: return basic insights without LLM extraction
        return [
            LiteratureInsight(
                paper_id=f"arxiv_{p.get('arxiv_id', i)}",
                title=p["title"],
                year=p.get("year"),
                source="arxiv",
                insight=p.get("abstract", "")[:200] + "...",
                method_hint=None,
                gap_hint=None,
            )
            for i, p in enumerate(papers[:5])
        ]
