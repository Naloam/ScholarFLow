"""Synthesize literature into thematic groups, research gaps, and positioning."""

from __future__ import annotations

import json
import logging

from schemas.autoresearch import LiteratureInsight, LiteratureSynthesis
from schemas.papers import PaperMeta
from services.llm.client import chat
from services.llm.prompting import load_prompt
from services.llm.response_utils import get_message_content

logger = logging.getLogger(__name__)

LITERATURE_SYNTHESIS_PROMPT_PATH = "backend/prompts/autoresearch/literature_synthesis/v0.1.0.md"


def _build_paper_brief(paper: PaperMeta, chunk_texts: list[str] | None = None) -> str:
    parts = [f"Title: {paper.title or 'Untitled'}"]
    if paper.year:
        parts.append(f"Year: {paper.year}")
    if paper.source:
        parts.append(f"Source: {paper.source}")
    if paper.abstract:
        parts.append(f"Abstract: {paper.abstract}")
    if chunk_texts:
        combined = " ".join(chunk_texts)[:800]
        parts.append(f"Full-text excerpt: {combined}")
    return "\n".join(parts)


def _parse_synthesis(raw: str, fallback_insights: list[LiteratureInsight]) -> LiteratureSynthesis:
    """Parse LLM JSON response into LiteratureSynthesis, with graceful fallback."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re
        m = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                logger.warning("Failed to parse literature synthesis JSON, using empty fallback")
                return LiteratureSynthesis(insights=fallback_insights)
        else:
            logger.warning("No JSON found in literature synthesis response")
            return LiteratureSynthesis(insights=fallback_insights)

    from schemas.autoresearch import LiteratureTheme, ResearchGap

    themes = [LiteratureTheme(**t) for t in data.get("themes", [])]
    gaps = [ResearchGap(**g) for g in data.get("gaps", [])]

    raw_insights = data.get("insights", [])
    insights: list[LiteratureInsight] = []
    for ri in raw_insights:
        try:
            insights.append(LiteratureInsight(**ri))
        except Exception:
            continue
    if not insights:
        insights = fallback_insights

    return LiteratureSynthesis(
        themes=themes,
        gaps=gaps,
        positioning=data.get("positioning"),
        novelty_claim=data.get("novelty_claim"),
        insights=insights,
    )


def synthesize(
    *,
    papers: list[PaperMeta],
    chunk_context: dict[str, list[str]],
    existing_insights: list[LiteratureInsight],
    topic: str,
    task_family: str,
) -> LiteratureSynthesis | None:
    """Produce a LiteratureSynthesis from gathered papers via LLM analysis."""
    if not papers:
        return None

    prompt_text = load_prompt(LITERATURE_SYNTHESIS_PROMPT_PATH)
    if not prompt_text:
        logger.warning("Literature synthesis prompt not found at %s", LITERATURE_SYNTHESIS_PROMPT_PATH)
        return None

    paper_briefs = []
    for paper in papers:
        chunks = chunk_context.get(paper.id or "", [])
        paper_briefs.append(_build_paper_brief(paper, chunk_texts=chunks if chunks else None))

    papers_text = "\n\n---\n\n".join(paper_briefs)

    user_message = (
        f"## Topic\n{topic}\n\n"
        f"## Task Family\n{task_family}\n\n"
        f"## Papers ({len(papers)} total)\n\n{papers_text}"
    )

    try:
        response = chat(
            messages=[
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
        )
    except Exception as exc:
        logger.warning("Literature synthesis LLM call failed: %s", exc)
        return None

    content = get_message_content(response)
    if not content:
        return None

    return _parse_synthesis(content, existing_insights)
