from __future__ import annotations

import logging
import re
from datetime import datetime

from agents.fetcher_agent import FetcherAgent
from agents.reader_agent import ReaderAgent
from agents.search_agent import SearchAgent
from schemas.autoresearch import LiteratureInsight, LiteratureSynthesis
from schemas.agents import FetchItem, FetchResult, ReadResult
from schemas.papers import PaperMeta
from schemas.search import SearchResult
from services.autoresearch.literature import derive_literature_insights
from services.autoresearch.literature_synthesizer import synthesize as synthesize_literature
from services.embedding.embeddings import embed_texts
from services.embedding.vector_index import add_vectors
from services.papers.repository import list_papers, upsert_papers_from_search
from services.reader.repository import save_chunks, update_embeddings
from services.search.repository import get_latest_search_result, save_search_result

logger = logging.getLogger(__name__)


def _search_topic_literature(project_id: str, topic: str) -> SearchResult | None:
    """Search for literature with retry and multi-source fallback."""
    import time as _time

    agent = SearchAgent()
    last_exc: Exception | None = None

    # Try with all sources first, then fallback source by source
    source_configs = [
        (["semantic_scholar", "arxiv", "crossref"], 25),
        (["arxiv", "crossref"], 25),
        (["arxiv"], 25),
        (["crossref"], 25),
    ]

    for attempt, (sources, limit) in enumerate(source_configs):
        try:
            result = agent.run({"query": topic, "limit": limit, "sources": sources})
            sr = SearchResult(**result["result"])
            if sr.items:
                return sr
            logger.info("literature search returned 0 items with sources=%s (attempt %d)", sources, attempt + 1)
        except Exception as exc:
            last_exc = exc
            logger.warning("literature search failed for topic=%r sources=%s: %s", topic, sources, exc)
            if attempt < len(source_configs) - 1:
                _time.sleep(2 ** attempt)
            continue

    if last_exc is not None:
        logger.warning("all literature search attempts failed for topic=%r", topic)
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
    """Generate context literature when search yields no real papers.

    Attempts LLM-generated domain references first; falls back to static context.
    """
    # Try LLM-generated domain-specific references
    try:
        from services.llm.client import chat
        from services.llm.response_utils import get_message_content
        import json as _json

        prompt = (
            "Generate 3 plausible academic references for a research study. "
            "Each reference must be a real-sounding but clearly labeled as AI-generated context. "
            "The study is about:\n"
            f"Topic: {topic}\n"
            f"Task family: {task_family}\n"
            f"Benchmark: {benchmark_name}\n\n"
            "Return JSON array with objects having: title, year (2019-2025), insight (one sentence summary), "
            "method_hint (what method the paper used), gap_hint (what gap remains).\n"
            "Rules: Do NOT fabricate specific author names. Use realistic but clearly synthetic titles. "
            "Focus on the actual research area, not the benchmark itself."
        )
        response = chat(
            [
                {"role": "system", "content": "You are generating academic context references. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        content = get_message_content(response)
        if content:
            import re as _re
            m = _re.search(r"\[.*\]", content, _re.DOTALL)
            if m:
                refs = _json.loads(m.group(0))
                return [
                    LiteratureInsight(
                        paper_id=f"context_ref_{i}",
                        title=r.get("title", f"Domain Reference {i}"),
                        year=r.get("year"),
                        source="ai_generated_context",
                        insight=r.get("insight", ""),
                        method_hint=r.get("method_hint"),
                        gap_hint=r.get("gap_hint"),
                    )
                    for i, r in enumerate(refs[:3])
                ]
    except Exception as exc:
        logger.warning("LLM fallback literature generation failed: %s", exc)

    # Static fallback (last resort)
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


def _fetch_chunk_context(db, project_id: str, papers: list[PaperMeta], max_papers: int = 10) -> dict[str, list[str]]:
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
    task_family: str = "text_classification",
) -> tuple[list, list[LiteratureInsight], dict[str, list[str]], LiteratureSynthesis | None]:
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

    synthesis: LiteratureSynthesis | None = None
    try:
        synthesis = synthesize_literature(
            papers=papers,
            chunk_context=chunk_context,
            existing_insights=insights,
            topic=topic,
            task_family=task_family,
        )
    except Exception as exc:
        logger.warning("Literature synthesis failed, continuing without it: %s", exc)

    return papers, insights, chunk_context, synthesis
