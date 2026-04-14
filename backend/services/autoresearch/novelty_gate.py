"""Novelty check gate — verify research plan novelty before committing resources.

Stolen from ARIS's deepxiv/novelty verification stage:
before running experiments, have the LLM evaluate if the proposed method
is genuinely different from existing work.
"""
from __future__ import annotations

import json
import logging
import re

from schemas.autoresearch import LiteratureInsight, LiteratureSynthesis, ResearchPlan

logger = logging.getLogger(__name__)


class NoveltyCheck:
    """Evaluate whether a research plan's hypothesis is novel relative to known literature."""

    def check(
        self,
        plan: ResearchPlan,
        literature: list[LiteratureInsight],
        literature_synthesis: LiteratureSynthesis | None = None,
    ) -> dict:
        """Run novelty check. Returns {"score": int 1-5, "verdict": str, "reasoning": str}."""
        if not literature:
            return {
                "score": 3,
                "verdict": "no_literature",
                "reasoning": "No literature available to check novelty against. Proceed with caution.",
            }

        try:
            from services.llm.client import chat
            from services.llm.response_utils import get_message_content

            # Build literature summary
            lit_texts = []
            for i, item in enumerate(literature[:8], 1):
                parts = [f"[{i}] {item.title}"]
                if item.year:
                    parts.append(f"({item.year})")
                if item.insight:
                    parts.append(f"— {item.insight}")
                if item.method_hint:
                    parts.append(f"Method: {item.method_hint}")
                lit_texts.append(" ".join(parts))

            lit_block = "\n".join(lit_texts)

            # Build gap info
            gaps = []
            if literature_synthesis and literature_synthesis.gaps:
                gaps = [g.description for g in literature_synthesis.gaps[:5]]
            gap_block = "\n".join(f"- {g}" for g in gaps) if gaps else "No explicit gaps identified."

            prompt = (
                "You are a research novelty evaluator. Given a research plan and existing literature, "
                "assess whether the proposed method and hypotheses are genuinely novel.\n\n"
                f"## Proposed Research\n"
                f"Topic: {plan.topic}\n"
                f"Proposed method: {plan.proposed_method}\n"
                f"Hypotheses: {'; '.join(plan.hypotheses)}\n"
                f"Novelty claim: {getattr(plan, 'novelty_statement', 'Not stated')}\n"
                f"Planned contributions: {'; '.join(plan.planned_contributions)}\n\n"
                f"## Existing Literature\n{lit_block}\n\n"
                f"## Known Gaps\n{gap_block}\n\n"
                "Score novelty from 1-5:\n"
                "1 = Already done — this exact approach exists in the literature\n"
                "2 = Mostly incremental — small variation on existing methods\n"
                "3 = Moderate novelty — combines known ideas in a new way or applies to new domain\n"
                "4 = Notably novel — introduces genuinely new technique or insight\n"
                "5 = Highly novel — represents a significant departure from existing approaches\n\n"
                "Return JSON: {\"score\": <1-5>, \"verdict\": \"<already_done|incremental|moderate|novel|highly_novel>\", "
                "\"reasoning\": \"<2-3 sentences explaining the score>\", "
                "\"closest_prior_work\": \"<which paper is closest, if any>\"}"
            )

            response = chat(
                [
                    {"role": "system", "content": "Evaluate research novelty. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            content = get_message_content(response)
            if not content:
                return self._fallback_check(plan, literature)

            m = re.search(r"\{.*\}", content, re.DOTALL)
            if not m:
                return self._fallback_check(plan, literature)

            result = json.loads(m.group(0))
            score = max(1, min(5, int(result.get("score", 3))))
            return {
                "score": score,
                "verdict": result.get("verdict", "moderate"),
                "reasoning": result.get("reasoning", ""),
                "closest_prior_work": result.get("closest_prior_work"),
            }
        except Exception as exc:
            logger.warning("novelty_check: LLM evaluation failed: %s", exc)
            return self._fallback_check(plan, literature)

    def _fallback_check(
        self,
        plan: ResearchPlan,
        literature: list[LiteratureInsight],
    ) -> dict:
        """Heuristic novelty check when LLM is unavailable."""
        # Simple lexical overlap check
        plan_terms = set(re.findall(r"[a-z]{4,}", f"{plan.proposed_method} {plan.topic}".lower()))
        lit_terms = set()
        for item in literature[:5]:
            lit_terms.update(re.findall(r"[a-z]{4,}", f"{item.title} {item.insight or ''}".lower()))

        overlap = plan_terms & lit_terms
        if not plan_terms:
            score = 2
        elif len(overlap) / len(plan_terms) > 0.7:
            score = 2
        elif len(overlap) / len(plan_terms) > 0.4:
            score = 3
        else:
            score = 4

        return {
            "score": score,
            "verdict": "moderate",
            "reasoning": f"Heuristic check: {len(overlap)}/{len(plan_terms)} plan terms overlap with literature.",
            "closest_prior_work": None,
        }

    def should_skip(self, result: dict, threshold: int = 2) -> bool:
        """Return True if the plan should be skipped due to low novelty."""
        return result.get("score", 3) < threshold
