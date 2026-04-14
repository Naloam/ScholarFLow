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

    # System results (each has system name + metrics dict)
    if artifact.system_results:
        parts.append("## System Results")
        for sr in artifact.system_results:
            metrics_str = ", ".join(
                f"{k}={v:.4f}" if isinstance(v, (int, float)) else f"{k}={v}"
                for k, v in (sr.metrics or {}).items()
            )
            parts.append(f"- {sr.system}: {metrics_str}")

    # Aggregate results
    if artifact.aggregate_system_results:
        parts.append("\n## Aggregate Results")
        for ag in artifact.aggregate_system_results:
            metrics_str = ", ".join(
                f"{k}={v:.4f}" if isinstance(v, (int, float)) else f"{k}={v}"
                for k, v in (ag.metrics or {}).items()
            )
            parts.append(f"- {ag.system}: {metrics_str}")

    # Sweep results
    if artifact.sweep_results:
        parts.append("\n## Sweep Results")
        for sweep in artifact.sweep_results:
            sweep_name = getattr(sweep, 'sweep_name', '') or getattr(sweep, 'name', '') or 'sweep'
            parts.append(f"- Sweep: {sweep_name}")
            if hasattr(sweep, 'metric_results') and sweep.metric_results:
                for mr in sweep.metric_results:
                    mean_val = getattr(mr, 'mean', None)
                    std_val = getattr(mr, 'std', None)
                    metric = getattr(mr, 'metric', 'score')
                    if mean_val is not None:
                        val_str = f"{mean_val:.4f}"
                        if std_val is not None:
                            val_str += f"±{std_val:.4f}"
                        parts.append(f"  - {metric}: {val_str}")
            # Also check objective_score
            obj_score = getattr(sweep, 'objective_score', None)
            if obj_score is not None:
                parts.append(f"  - objective_score: {obj_score:.4f}")

    # Significance tests
    if artifact.significance_tests:
        parts.append("\n## Significance Tests")
        for test in artifact.significance_tests:
            system_a = getattr(test, 'system_a', '') or getattr(test, 'candidate', '')
            system_b = getattr(test, 'system_b', '') or getattr(test, 'comparator', '')
            p_value = getattr(test, 'p_value', None)
            is_sig = getattr(test, 'is_significant', None)
            method = getattr(test, 'method', '')
            p_str = f"{p_value:.4f}" if isinstance(p_value, (int, float)) else str(p_value)
            parts.append(
                f"- {system_a} vs {system_b}: "
                f"p={p_str}, significant={is_sig}, method={method}"
            )

    # Acceptance checks
    if artifact.acceptance_checks:
        parts.append("\n## Acceptance Checks")
        for check in artifact.acceptance_checks:
            status = getattr(check, 'status', '?')
            rule_id = getattr(check, 'rule_id', '')
            desc = getattr(check, 'description', '')
            parts.append(f"- [{status}] {rule_id}: {desc}")

    # Tables
    if artifact.tables:
        parts.append("\n## Tables")
        for table in artifact.tables[:3]:
            title = getattr(table, 'title', 'Untitled')
            ncols = len(getattr(table, 'columns', []))
            nrows = len(getattr(table, 'rows', []))
            parts.append(f"- '{title}': {ncols} cols x {nrows} rows")

    # Best system / objective score
    if artifact.best_system:
        score_str = f", {artifact.primary_metric}={artifact.objective_score:.4f}" if artifact.objective_score is not None else ""
        parts.append(f"\nBest system: {artifact.best_system}{score_str}")

    # Key findings
    if artifact.key_findings:
        parts.append("\n## Key Findings")
        for finding in artifact.key_findings[:5]:
            parts.append(f"- {finding}")

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
