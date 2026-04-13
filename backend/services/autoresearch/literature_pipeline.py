from __future__ import annotations

import logging
import re
from datetime import datetime

from agents.fetcher_agent import FetcherAgent
from agents.reader_agent import ReaderAgent
from agents.search_agent import SearchAgent
from schemas.autoresearch import LiteratureInsight
from schemas.agents import FetchItem, FetchResult, ReadResult
from schemas.papers import PaperMeta
from schemas.search import SearchResult
from services.autoresearch.literature import derive_literature_insights
from services.embedding.embeddings import embed_texts
from services.embedding.vector_index import add_vectors
from services.papers.repository import list_papers, upsert_papers_from_search
from services.reader.repository import save_chunks, update_embeddings
from services.search.repository import get_latest_search_result, save_search_result

logger = logging.getLogger(__name__)


def _search_topic_literature(project_id: str, topic: str) -> SearchResult | None:
    try:
        agent = SearchAgent()
        result = agent.run({"query": topic, "limit": 15})
        return SearchResult(**result["result"])
    except Exception as exc:
        logger.warning("literature search failed for topic=%r: %s", topic, exc)
        return None


def _context_slug(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return slug or fallback


def build_fallback_literature_context(
    *,
    topic: str,
    benchmark_name: str,
    benchmark_description: str,
    dataset_name: str,
    dataset_description: str,
    task_family: str,
) -> list[LiteratureInsight]:
    family_label = task_family.replace("_", " ")
    topic_label = topic.strip() or benchmark_name
    benchmark_slug = _context_slug(benchmark_name, "benchmark")
    dataset_label = dataset_name or benchmark_name
    scope_insight = (
        f"Automated classification and analysis of {topic_label} is an active area of research in {family_label}. "
        f"Benchmark {benchmark_name} provides a standardized evaluation framework for comparing approaches on this task."
    )
    benchmark_insight = (
        f"{benchmark_description.strip()} "
        f"The dataset {dataset_label} provides structured examples for supervised evaluation."
    )
    dataset_insight = (
        f"Prior work in {family_label} has established the value of comparing lightweight baseline methods "
        f"against learned models under controlled conditions, particularly for small-scale benchmark evaluation."
    )
    return [
        LiteratureInsight(
            paper_id=f"{benchmark_slug}_scope_context",
            title=f"[Context Summary] {family_label.title()} Task Scope for {topic_label}",
            year=None,
            source="benchmark_context",
            insight=scope_insight,
            method_hint=(
                f"Compare multiple approaches with proper statistical grounding for "
                f"{family_label} tasks."
            ),
            gap_hint=(
                f"Identify which method characteristics contribute most to performance on {dataset_label}."
            ),
        ),
        LiteratureInsight(
            paper_id=f"{benchmark_slug}_benchmark_context",
            title=f"[Context Summary] {benchmark_name} Benchmark Description",
            year=None,
            source="benchmark_context",
            insight=benchmark_insight,
            method_hint="Include both simple baselines and learned models for meaningful comparison.",
            gap_hint=(
                f"Determine the performance ceiling of simple methods on {dataset_label} before applying complex models."
            ),
        ),
        LiteratureInsight(
            paper_id=f"{benchmark_slug}_execution_context",
            title=f"[Context Summary] Baseline Comparison Strategy for {dataset_label}",
            year=None,
            source="benchmark_context",
            insight=dataset_insight,
            method_hint=(
                "Report multi-seed aggregate statistics with confidence intervals for reproducibility."
            ),
            gap_hint=(
                f"Characterize the conditions under which lightweight methods suffice for {topic_label}."
            ),
        ),
    ]


def _fetch_chunk_context(db, project_id: str, papers: list[PaperMeta], max_papers: int = 5) -> dict[str, list[str]]:
    fetcher = FetcherAgent()
    reader = ReaderAgent()
    chunk_context: dict[str, list[str]] = {}
    for paper in [paper for paper in papers if paper.pdf_url][:max_papers]:
        try:
            fetch_result = fetcher.run(
                {
                    "project_id": project_id,
                    "items": [FetchItem(paper_id=paper.id or "", pdf_url=paper.pdf_url).model_dump()],
                }
            )
            item = FetchResult(**(fetch_result.get("items") or [{}])[0])
            if item.status != "ok" or not item.grobid_xml_path:
                continue
            read_result = ReadResult(
                **reader.run({"paper_id": paper.id or "", "grobid_xml_path": item.grobid_xml_path})
            )
            saved = save_chunks(db, project_id, paper.id or "", read_result.chunks)
            if saved:
                vectors = embed_texts([chunk.text for chunk in saved])
                add_vectors(project_id, vectors, [chunk.chunk_id for chunk in saved])
                update_embeddings(db, [chunk.chunk_id for chunk in saved], [chunk.chunk_id for chunk in saved])
                chunk_context[paper.id or ""] = [chunk.text for chunk in saved[:3]]
        except Exception:
            continue
    return chunk_context


def gather_literature_context(
    *,
    db,
    project_id: str,
    topic: str,
    paper_ids: list[str] | None,
    auto_search: bool,
    auto_fetch: bool,
):
    papers = list_papers(db, project_id)
    if paper_ids:
        paper_id_set = set(paper_ids)
        papers = [paper for paper in papers if paper.id in paper_id_set]

    if not papers:
        latest = get_latest_search_result(db, project_id, query=topic)
        if latest is None and auto_search:
            searched = _search_topic_literature(project_id, topic)
            if searched is not None:
                save_search_result(db, project_id, searched)
                upsert_papers_from_search(db, project_id, searched.items)
                papers = list_papers(db, project_id)
        if latest is not None and not papers:
            papers = latest.items

    chunk_context = _fetch_chunk_context(db, project_id, papers) if auto_fetch and papers else {}
    insights = derive_literature_insights(papers, chunk_context=chunk_context)
    return papers, insights, chunk_context
