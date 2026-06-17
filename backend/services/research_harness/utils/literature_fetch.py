"""
literature_fetch.py — 对 literature_connectors 的薄封装。
让 research_harness agents 可以直接用 (project_id, queries) 调用，
不依赖旧的 AutoResearchResearchBriefRead 结构。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from schemas.autoresearch import (
    AutoResearchIdeaFeasibilityAssessmentRead,
    AutoResearchResearchBriefRead,
)
from services.autoresearch.literature_connectors import search_literature_connectors


def fetch_papers(
    project_id: str,
    queries: list[str],
    *,
    sources: list[str] | None = None,
    limit_per_source: int = 5,
    network_enabled: bool = True,
    cache_enabled: bool = True,
) -> list[dict[str, Any]]:
    """
    给定 project_id 和检索 query 列表，返回论文列表（dict 格式）。
    sources 默认为 ["arxiv", "semantic_scholar", "crossref"]（不含 fixture）。

    内部构造一个最小化的 AutoResearchResearchBriefRead，仅用于 connector 的
    cache key 和内部路由；research_harness 不依赖 brief 的其余字段。
    """
    primary_idea = queries[0] if queries else ""
    timestamp = datetime.now()
    minimal_brief = AutoResearchResearchBriefRead(
        brief_id=f"harness_{project_id}",
        project_id=project_id,
        generated_at=timestamp,
        updated_at=timestamp,
        original_idea=primary_idea,
        polished_idea=primary_idea,
        scope_narrowing_recommendation="",
        feasibility_assessment=AutoResearchIdeaFeasibilityAssessmentRead(
            score=0.0,
            summary="research_harness minimal brief — feasibility deferred to IdeaAgent",
        ),
    )
    used_sources = sources or ["arxiv", "semantic_scholar", "crossref"]
    papers, _statuses = search_literature_connectors(
        minimal_brief,
        search_queries=queries,
        sources=used_sources,
        limit_per_source=limit_per_source,
        network_enabled=network_enabled,
        cache_enabled=cache_enabled,
    )
    return [p.model_dump() for p in papers]
