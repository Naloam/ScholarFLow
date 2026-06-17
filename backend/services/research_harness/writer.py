"""WriterAgent (V2, plan §6) — turns the honest experiment record into a paper draft.

Pipeline (3 LLM calls on the writer model): ``contribution.md → outline.md → draft.md``.
Reuses the per-section discipline of the frozen ``prompts/autoresearch/paper_writer/``
without copying the 13975-line orchestrator. The Writer is *advised* to be honest via
prompted constraints + a real evidence pack; the AuditorAgent is the hard gate that
catches anything that slips through.

Outputs land in ``workspace/<project_id>/paper/``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config.settings import settings
from services.llm.client import chat
from services.llm.response_utils import get_message_content
from services.research_harness.prompts import load_prompt
from services.research_harness import evidence

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path(settings.data_dir) / "research_workspace"


def _paper_dir(project_id: str) -> Path:
    p = WORKSPACE_ROOT / project_id / "paper"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _call_writer(prompt: str) -> str:
    """One writer-model call. The writer model (``LLM_WRITER_MODEL``) may differ from the
    main reasoning model; falls back to the default chat model when unset."""
    response = chat([{"role": "user", "content": prompt}], model=settings.llm_writer_model)
    return get_message_content(response)


def _baseline_summary(metrics: dict[str, Any]) -> str:
    """Compact per-dataset line for the outline prompt (so the outline plans honest framing)."""
    datasets = (metrics.get("baseline_comparison") or {}).get("datasets") or []
    if not datasets:
        return "_(no baseline/proposed comparison)_"
    return "; ".join(
        f"{d.get('dataset')}: proposed={d.get('proposed_metric')} vs baseline="
        f"{d.get('baseline_metric')} beats_baseline={d.get('beats_baseline')}"
        for d in datasets
        if isinstance(d, dict)
    )


def write_contribution(project_id: str, idea: str, selected: dict, notes: dict) -> str:
    prompt = (
        load_prompt("writer_contribution_v1.md")
        .replace("{idea}", idea)
        .replace("{hypothesis_json}", json.dumps(selected or {}, ensure_ascii=False, indent=2))
        .replace("{gap_map_json}", json.dumps(notes.get("gap_map", {}) or {}, ensure_ascii=False, indent=2))
    )
    text = _call_writer(prompt)
    (_paper_dir(project_id) / "contribution.md").write_text(text, encoding="utf-8")
    return text


def write_outline(
    project_id: str,
    idea: str,
    selected: dict,
    metrics: dict,
    review: dict,
    contribution: str,
) -> str:
    prompt = (
        load_prompt("writer_outline_v1.md")
        .replace("{contribution}", contribution)
        .replace("{hypothesis_json}", json.dumps(selected or {}, ensure_ascii=False, indent=2))
        .replace(
            "{action_plan_json}",
            json.dumps(review.get("required_experiments", []) or [], ensure_ascii=False, indent=2),
        )
        .replace("{execution_status}", str(metrics.get("execution_status")))
        .replace("{beats_baseline_summary}", _baseline_summary(metrics))
    )
    text = _call_writer(prompt)
    (_paper_dir(project_id) / "outline.md").write_text(text, encoding="utf-8")
    return text


def write_draft(
    project_id: str,
    idea: str,
    selected: dict,
    metrics: dict,
    contribution: str,
    outline: str,
) -> str:
    prompt = (
        load_prompt("writer_draft_v1.md")
        .replace("{outline}", outline)
        .replace("{contribution}", contribution)
        .replace("{hypothesis_json}", json.dumps(selected or {}, ensure_ascii=False, indent=2))
        .replace("{evidence_pack}", evidence.build_evidence_pack(metrics))
        .replace("{honesty_constraints}", evidence.build_honesty_constraints(metrics))
    )
    text = _call_writer(prompt)
    draft_path = _paper_dir(project_id) / "draft.md"
    draft_path.write_text(text, encoding="utf-8")
    # Keep the unaudited LLM output for traceability — the Auditor rewrites draft.md in place.
    (_paper_dir(project_id) / "draft.raw.md").write_text(text, encoding="utf-8")
    logger.info("[WriterAgent] draft written: %s (%d chars)", draft_path, len(text))
    return text


def run_writer_agent(
    project_id: str,
    idea: str,
    selected: dict,
    metrics: dict,
    review: dict,
    notes: dict,
) -> Path:
    """Full contribution → outline → draft pipeline. Returns the draft path."""
    contribution = write_contribution(project_id, idea, selected, notes)
    outline = write_outline(project_id, idea, selected, metrics, review, contribution)
    draft_path = _paper_dir(project_id) / "draft.md"
    write_draft(project_id, idea, selected, metrics, contribution, outline)
    return draft_path
