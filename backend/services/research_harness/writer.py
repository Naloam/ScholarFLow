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
from services.research_harness import citation
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
        .replace("{evidence_pack}", evidence.build_evidence_pack(metrics, selected))
        .replace("{honesty_constraints}", evidence.build_honesty_constraints(metrics, selected))
    )
    text = _call_writer(prompt)
    draft_path = _paper_dir(project_id) / "draft.md"
    draft_path.write_text(text, encoding="utf-8")
    # Keep the unaudited LLM output for traceability — the Auditor rewrites draft.md in place.
    (_paper_dir(project_id) / "draft.raw.md").write_text(text, encoding="utf-8")
    logger.info("[WriterAgent] draft written: %s (%d chars)", draft_path, len(text))
    return text


# --------------------------------------------------------------------------- #
# V2.1 quality loop: deterministic coverage lint → at most ONE bounded revision
# --------------------------------------------------------------------------- #


def _format_lint_flags(flags: list[dict]) -> str:
    if not flags:
        return "_(none — the lint found no unsupported numbers)_"
    return "\n".join(f"- `{f['token']}` — {f['reason']}" for f in flags)


def revise_on_lint(
    project_id: str,
    draft: str,
    flags: list[dict],
    metrics: dict,
    hypothesis: dict | None = None,
) -> tuple[str, dict]:
    """One bounded Writer revision pass over the lint flags.

    Feeds the flags + evidence pack + honesty constraints back to the writer model
    with instructions to fix ONLY the flagged numbers (no new numbers, no softened
    honesty). At most one call; on empty/failed revision the original draft is kept
    (the flags still reach the Auditor as a backstop). Returns ``(revised_draft, log)``.
    """
    log = {"flags_before": [f["token"] for f in flags], "revised": False, "flags_after": []}
    if not flags:
        return draft, log

    prompt = (
        load_prompt("writer_revise_v1.md")
        .replace("{draft}", draft)
        .replace("{lint_flags}", _format_lint_flags(flags))
        .replace("{evidence_pack}", evidence.build_evidence_pack(metrics, hypothesis))
        .replace("{honesty_constraints}", evidence.build_honesty_constraints(metrics, hypothesis))
    )
    try:
        revised = _call_writer(prompt)
    except Exception as exc:  # noqa: BLE001 — revision is best-effort; never block the draft
        logger.warning("[WriterAgent] revise call failed, keeping original draft: %s", exc)
        log["error"] = str(exc)
        return draft, log

    revised = (revised or "").strip()
    if not revised or revised == draft:
        # No usable change → keep the original; the Auditor still gates the flags.
        return draft, log

    # Re-lint the revision so the ledger records whether the loop actually helped.
    log["revised"] = True
    log["flags_after"] = [f["token"] for f in evidence.coverage_lint(revised, metrics)]
    return revised, log


# --------------------------------------------------------------------------- #
# V2.2 citation grounding (goal_session8.md Step 4) — mirror of coverage_lint,
# but for unverified citations: ≤1 bounded pass to delete or re-anchor them.
# --------------------------------------------------------------------------- #


def _load_papers(project_id: str) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    papers_path = WORKSPACE_ROOT / project_id / "literature" / "papers.jsonl"
    if papers_path.exists():
        for line in papers_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                papers.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return papers


def _build_grounding_prompt(
    draft: str,
    unverified: list[dict[str, Any]],
    available_titles: list[str],
    metrics: dict[str, Any],
    hypothesis: dict[str, Any] | None,
) -> str:
    unverified_list = "\n".join(f'- "{r.get("raw_title", "")}"' for r in unverified)
    if available_titles:
        titles_block = "\n".join(f"- {t}" for t in available_titles)
    else:
        titles_block = "_(no retrieved papers available — DELETE the unsupported citations instead)_"
    return (
        "You are fixing a research paper draft so that EVERY citation resolves to a paper "
        "that was ACTUALLY retrieved. The following citations were NOT found in the retrieved "
        "literature and are likely hallucinated:\n\n"
        f"{unverified_list}\n\n"
        "For each unsupported citation do EXACTLY ONE of:\n"
        "  1. DELETE the sentence/claim that relies on it (preferred when the claim is not "
        "supported by the experiment's own numbers); OR\n"
        "  2. REPLACE the citation with one of the REAL retrieved paper titles listed below — "
        "only if that paper genuinely supports the claim (pick the closest topical neighbor).\n\n"
        f"Retrieved paper titles you MAY cite:\n{titles_block}\n\n"
        "HARD RULES:\n"
        "- NEVER cite a paper that is not in the list above. NEVER invent a title, author, or year.\n"
        "- Do NOT change any experimental number, verdict, or honest conclusion.\n"
        "- Do NOT add new claims. Only remove or re-anchor unsupported citations.\n"
        "- Output the FULL revised draft (markdown), nothing else.\n\n"
        f"## Evidence pack (do not contradict)\n{evidence.build_evidence_pack(metrics, hypothesis)}\n\n"
        f"## Draft to fix\n{draft}\n"
    )


def ground_citations(
    project_id: str,
    draft: str,
    metrics: dict[str, Any],
    hypothesis: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """One bounded pass to ground unverified citations (≤1 LLM call).

    For every citation :func:`citation.verify_citations` marks unverified (offline),
    ask the writer to DELETE the unsupported sentence OR REPLACE it with a real
    retrieved paper title — never invent or retain an unretrieved cite. At most one
    call; on empty/failure the original draft is kept (the Auditor backstops).
    Returns ``(revised_draft, log)``; ``log`` carries ``unverified_before`` /
    ``unverified_after`` and is what gets persisted to
    ``paper/citation_grounding_log.json``.
    """
    papers = _load_papers(project_id)
    unverified = [r for r in citation.verify_citations(draft, papers) if r.get("verdict") == "unverified"]
    log: dict[str, Any] = {
        "unverified_before": [{"title": r.get("raw_title"), "marker": r.get("marker")} for r in unverified],
        "revised": False,
        "unverified_after": [],
    }
    if not unverified:
        return draft, log

    available_titles = [
        str(p.get("title")) for p in papers[:30]
        if isinstance(p, dict) and isinstance(p.get("title"), str) and p["title"].strip()
    ]
    prompt = _build_grounding_prompt(draft, unverified, available_titles, metrics, hypothesis)
    try:
        revised = _call_writer(prompt)
    except Exception as exc:  # noqa: BLE001 — grounding is best-effort; never block the draft
        logger.warning("[WriterAgent] citation grounding call failed, keeping original draft: %s", exc)
        log["error"] = str(exc)
        return draft, log

    revised = (revised or "").strip()
    if not revised or revised == draft:
        return draft, log

    log["revised"] = True
    log["unverified_after"] = [
        {"title": r.get("raw_title"), "marker": r.get("marker")}
        for r in citation.verify_citations(revised, papers)
        if r.get("verdict") == "unverified"
    ]
    return revised, log


def run_quality_loop(project_id: str, metrics: dict, hypothesis: dict | None = None) -> dict:
    """``draft → lint → revise(≤1) → ground citations(≤1) → persist``.

    Mutates ``paper/draft.md`` only when a real revision/grounding lands; always
    writes ``paper/revise_log.json`` + ``paper/citation_grounding_log.json`` for
    measurement. The pre-revision draft is preserved at ``paper/draft.revise_pre.md``
    (numbers) and ``paper/draft.ground_pre.md`` (citations); ``paper/draft.raw.md``
    (the pristine first LLM output) is never touched. Returns the revise log.
    """
    paper = _paper_dir(project_id)
    draft_path = paper / "draft.md"
    draft = draft_path.read_text(encoding="utf-8") if draft_path.exists() else ""
    flags = evidence.coverage_lint(draft, metrics)

    revised, log = revise_on_lint(project_id, draft, flags, metrics, hypothesis)
    if log.get("revised"):
        (paper / "draft.revise_pre.md").write_text(draft, encoding="utf-8")
        draft_path.write_text(revised, encoding="utf-8")
        logger.info(
            "[WriterAgent] revised draft: flags %d → %d", len(flags), len(log["flags_after"])
        )
    (paper / "revise_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # V2.2 citation grounding (≤1 round); the Auditor backstops anything that slips.
    current = draft_path.read_text(encoding="utf-8") if draft_path.exists() else ""
    grounded, glog = ground_citations(project_id, current, metrics, hypothesis)
    if glog.get("revised"):
        (paper / "draft.ground_pre.md").write_text(current, encoding="utf-8")
        draft_path.write_text(grounded, encoding="utf-8")
        logger.info(
            "[WriterAgent] grounded citations: unverified %d → %d",
            len(glog["unverified_before"]), len(glog["unverified_after"]),
        )
    (paper / "citation_grounding_log.json").write_text(
        json.dumps(glog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return log


def run_writer_agent(
    project_id: str,
    idea: str,
    selected: dict,
    metrics: dict,
    review: dict,
    notes: dict,
) -> Path:
    """Full contribution → outline → draft → (lint → revise ≤1) pipeline.

    The quality loop (V2.1) runs INSIDE the write step — it is not a new pipeline
    step, so the 7-step timeline and 5-item nav stay unchanged. Returns the draft path.
    """
    contribution = write_contribution(project_id, idea, selected, notes)
    outline = write_outline(project_id, idea, selected, metrics, review, contribution)
    draft_path = _paper_dir(project_id) / "draft.md"
    write_draft(project_id, idea, selected, metrics, contribution, outline)
    run_quality_loop(project_id, metrics, selected)
    return draft_path
