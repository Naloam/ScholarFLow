from __future__ import annotations

import re

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


def _search_topic_literature(project_id: str, topic: str) -> SearchResult | None:
    try:
        agent = SearchAgent()
        result = agent.run({"query": topic, "limit": 6})
        return SearchResult(**result["result"])
    except Exception:
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
    scope_note = (
        f"This preserved benchmark-context memo frames {topic_label} as a bounded {family_label} study "
        f"on benchmark {benchmark_name}."
    )
    benchmark_note = (
        f"{benchmark_description.strip()} Dataset context: {dataset_description.strip() or benchmark_description.strip()}."
    )
    execution_note = (
        f"The executed study compares baseline and selected candidates under explicit train/test partitions for "
        f"{family_label} work on {dataset_label}."
    )
    return [
        LiteratureInsight(
            paper_id=f"{benchmark_slug}_scope_context",
            title=f"Scope note for {topic_label}",
            year=None,
            source="benchmark_context",
            insight=scope_note,
            method_hint=(
                f"Use benchmark-scoped comparisons, explicit citation markers, and cautious novelty framing for "
                f"{family_label} work."
            ),
            gap_hint=(
                f"Keep claims tied to benchmark {benchmark_name} and dataset {dataset_label} instead of extrapolating "
                "beyond the executed scope."
            ),
        ),
        LiteratureInsight(
            paper_id=f"{benchmark_slug}_benchmark_context",
            title=f"Benchmark note for {benchmark_name}",
            year=None,
            source="benchmark_context",
            insight=benchmark_note,
            method_hint=f"Preserve dataset-specific baselines and error analysis for {dataset_label}.",
            gap_hint=(
                f"Explain how the selected candidate differs from baseline methods while staying inside {benchmark_name}."
            ),
        ),
        LiteratureInsight(
            paper_id=f"{benchmark_slug}_execution_context",
            title=f"Execution note for {dataset_label}",
            year=None,
            source="benchmark_context",
            insight=execution_note,
            method_hint=(
                "Preserve aggregate metrics, seed coverage, and acceptance-check reporting in the paper summary."
            ),
            gap_hint=(
                f"Document why the selected candidate matters for {topic_label} without making claims beyond the "
                f"{family_label} benchmark slice."
            ),
        ),
    ]


def _fetch_chunk_context(db, project_id: str, papers: list[PaperMeta], max_papers: int = 2) -> dict[str, list[str]]:
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
