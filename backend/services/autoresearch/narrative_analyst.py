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


def _format_value(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return str(value)


def _format_metric_summary(
    mean_metrics: dict[str, float],
    *,
    std_metrics: dict[str, float] | None = None,
    confidence_intervals: dict[str, object] | None = None,
) -> str:
    if not mean_metrics:
        return "no metrics recorded"
    std_metrics = std_metrics or {}
    confidence_intervals = confidence_intervals or {}
    rendered: list[str] = []
    for metric, mean_value in mean_metrics.items():
        item = f"{metric}={_format_value(mean_value)}"
        std_value = std_metrics.get(metric)
        if std_value is not None:
            item += f" (std={_format_value(std_value)})"
        interval = confidence_intervals.get(metric)
        if interval is not None:
            lower = getattr(interval, "lower", None)
            upper = getattr(interval, "upper", None)
            level = getattr(interval, "level", None)
            if lower is not None and upper is not None:
                if isinstance(level, (int, float)):
                    item += f", {round(level * 100):d}% CI [{_format_value(lower)}, {_format_value(upper)}]"
                else:
                    item += f", CI [{_format_value(lower)}, {_format_value(upper)}]"
        rendered.append(item)
    return ", ".join(rendered)


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
            metrics_str = _format_metric_summary(
                ag.mean_metrics or {},
                std_metrics=ag.std_metrics,
                confidence_intervals=ag.confidence_intervals,
            )
            sample_suffix = f"; n={ag.sample_count}" if ag.sample_count else ""
            parts.append(f"- {ag.system}: {metrics_str}{sample_suffix}")

    # Sweep results
    if artifact.sweep_results:
        parts.append("\n## Sweep Results")
        for sweep in artifact.sweep_results:
            params = f", params={sweep.params}" if sweep.params else ""
            parts.append(
                f"- Sweep: {sweep.label} ({sweep.status}; "
                f"{sweep.successful_seed_count}/{sweep.seed_count} seeds{params})"
            )
            if sweep.best_system:
                parts.append(f"  - best_system: {sweep.best_system}")
            obj_score = sweep.objective_score_mean
            if obj_score is not None:
                obj_text = f"  - objective_score_mean: {_format_value(obj_score)}"
                if sweep.objective_score_std is not None:
                    obj_text += f" (std={_format_value(sweep.objective_score_std)})"
                interval = sweep.objective_score_confidence_interval
                if interval is not None:
                    obj_text += (
                        f", {round(interval.level * 100):d}% CI "
                        f"[{_format_value(interval.lower)}, {_format_value(interval.upper)}]"
                    )
                parts.append(obj_text)

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
            status = "pass" if check.passed else "fail"
            rule_id = f"{check.rule_id}: " if check.rule_id else ""
            detail = f" -- {check.detail}" if check.detail else ""
            parts.append(f"- [{status}] {rule_id}{check.criterion}{detail}")

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
