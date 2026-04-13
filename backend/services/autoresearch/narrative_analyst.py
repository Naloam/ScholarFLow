"""Analyze experiment results to discover the narrative story for paper writing."""

from __future__ import annotations

import json
import logging
import re

from schemas.autoresearch import (
    LiteratureSynthesis,
    NarrativeAnalysis,
    HypothesisResolution,
    ResearchPlan,
    ResultArtifact,
)
from services.llm.client import chat
from services.llm.prompting import load_prompt
from services.llm.response_utils import get_message_content

logger = logging.getLogger(__name__)

NARRATIVE_ANALYST_PROMPT_PATH = "backend/prompts/autoresearch/narrative_analyst/v0.1.0.md"


def _artifact_summary(artifact: ResultArtifact) -> str:
    """Build a concise text summary of experiment results for the LLM."""
    parts: list[str] = []

    if artifact.system_metrics:
        parts.append("## System Metrics")
        for sm in artifact.system_metrics:
            metrics_str = ", ".join(
                f"{m.metric}={m.mean:.4f}±{m.std:.4f}" for m in sm.metrics
            )
            parts.append(f"- {sm.system_name}: {metrics_str}")

    if artifact.significance_tests:
        parts.append("\n## Significance Tests")
        for test in artifact.significance_tests:
            parts.append(
                f"- {test.system_a} vs {test.system_b}: "
                f"p={test.p_value:.4f}, significant={test.is_significant}, "
                f"test={test.test_name}"
            )

    if artifact.acceptance_checks:
        parts.append("\n## Acceptance Checks")
        for check in artifact.acceptance_checks:
            parts.append(
                f"- [{check.status}] {check.rule_id}: {check.description}"
            )

    if artifact.sweep_evaluations:
        parts.append("\n## Sweep Evaluations")
        for sweep in artifact.sweep_evaluations:
            parts.append(f"- Sweep: {sweep.sweep_name}")
            if sweep.metric_results:
                for mr in sweep.metric_results:
                    parts.append(f"  - {mr.metric}: {mr.mean:.4f}±{mr.std:.4f}")

    return "\n".join(parts) if parts else "No structured results available."


def _parse_narrative(raw: str) -> NarrativeAnalysis | None:
    """Parse LLM JSON response into NarrativeAnalysis."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                return None
        else:
            return None

    resolutions = []
    for r in data.get("hypothesis_resolutions", []):
        try:
            resolutions.append(HypothesisResolution(**r))
        except Exception:
            continue

    return NarrativeAnalysis(
        story_arc=data.get("story_arc", ""),
        surprising_findings=data.get("surprising_findings", []),
        hypothesis_resolutions=resolutions,
        key_argument=data.get("key_argument", ""),
        evidence_chain=data.get("evidence_chain", []),
        recommended_emphasis=data.get("recommended_emphasis", []),
        alternative_explanations=data.get("alternative_explanations", []),
        connections_to_literature=data.get("connections_to_literature", []),
    )


def analyze(
    *,
    plan: ResearchPlan,
    artifact: ResultArtifact,
    literature_synthesis: LiteratureSynthesis | None = None,
) -> NarrativeAnalysis | None:
    """Produce a NarrativeAnalysis from experiment results via LLM."""
    prompt_text = load_prompt(NARRATIVE_ANALYST_PROMPT_PATH)
    if not prompt_text:
        logger.warning("Narrative analyst prompt not found")
        return None

    # Build research plan context
    plan_text = (
        f"## Research Plan\n"
        f"Topic: {plan.topic}\n"
        f"Title: {plan.title}\n"
        f"Problem: {plan.problem_statement}\n"
        f"Method: {plan.proposed_method}\n"
        f"Research questions: {plan.research_questions}\n"
        f"Hypotheses: {plan.hypotheses}\n"
    )
    if plan.conceptual_framework:
        cf = plan.conceptual_framework
        plan_text += (
            f"\n## Conceptual Framework\n"
            f"Theoretical basis: {cf.theoretical_basis}\n"
            f"Expected mechanism: {cf.expected_mechanism}\n"
            f"Assumptions: {cf.assumptions}\n"
        )

    # Build results context
    results_text = f"## Experiment Results\n{_artifact_summary(artifact)}"

    # Build literature context
    lit_text = ""
    if literature_synthesis:
        if literature_synthesis.themes:
            themes = "\n".join(
                f"  - {t.label}: {t.description}" for t in literature_synthesis.themes
            )
            lit_text = f"\n## Literature Themes\n{themes}\n"
        if literature_synthesis.gaps:
            gaps = "\n".join(
                f"  - [{g.gap_id}] {g.description}" for g in literature_synthesis.gaps
            )
            lit_text += f"\n## Literature Gaps\n{gaps}\n"

    user_message = f"{plan_text}\n{results_text}\n{lit_text}"

    try:
        response = chat(
            messages=[
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
        )
    except Exception as exc:
        logger.warning("Narrative analysis LLM call failed: %s", exc)
        return None

    content = get_message_content(response)
    if not content:
        return None

    return _parse_narrative(content)
