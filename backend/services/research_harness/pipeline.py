"""V0 research pipeline orchestration.

Single source of truth for the ordered agent steps (literature → idea → experiment
→ review → report). Both the CLI (``scripts/v0_run.py``) and the FastAPI layer
(``backend/api/research_harness.py``) call :func:`run_pipeline` so behaviour cannot
drift between the two entry points.

This module is intentionally free of CLI/argparse concerns and never blocks on
network by design at import time — the heavy LLM work happens inside the agent
functions invoked from the step wrappers.
"""
from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from config.settings import settings

logger = logging.getLogger("research_harness.pipeline")

# Unified workspace root (plan §5.2 P1 — single DATA_DIR, no double-backend).
WORKSPACE_ROOT: Path = Path(settings.data_dir) / "research_workspace"

ALL_STEPS: list[str] = ["literature", "idea", "experiment", "review", "report"]

STEP_OUTPUTS: dict[str, list[str]] = {
    "literature": [
        "literature/search_queries.json",
        "literature/papers.jsonl",
        "literature/notes.md",
        "literature/gap_map.md",
        "literature/known_baselines.md",
        "literature/notes.json",
    ],
    "idea": ["ideas/candidates.json", "ideas/selected.md", "ideas/selected.json"],
    "experiment": [
        "experiments/plan.json",
        "experiments/plan.md",
        "code/experiment.py",
        "code/requirements.txt",
        "artifacts/metrics.json",
        "artifacts/tables/results.csv",
    ],
    "review": [
        "reviews/reviewer_round_1.md",
        "reviews/action_plan_1.json",
        "reviews/review_round_1.json",
    ],
    "report": ["research_report.md", "conclusion.md"],
}


# --------------------------------------------------------------------------- #
# Paths & disk helpers
# --------------------------------------------------------------------------- #


def project_dir(project_id: str) -> Path:
    """Absolute path to a project workspace."""
    return WORKSPACE_ROOT / project_id


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return ""


def load_literature_notes(project_id: str) -> dict:
    """Prefer structured ``notes.json``; otherwise rebuild minimal notes from markdown."""
    proj = project_dir(project_id)
    notes = _read_json(proj / "literature" / "notes.json", None)
    if isinstance(notes, dict) and notes:
        return notes
    gap = _read_text(proj / "literature" / "gap_map.md")
    return {
        "gap_map": {"what_is_missing": gap, "literature_coverage": "unknown"},
        "known_baselines": [],
        "paper_notes": [],
        "source": "reconstructed_from_markdown",
    }


def load_selected_hypothesis(project_id: str) -> dict | None:
    """Prefer ``selected.json``; otherwise reuse :func:`select_hypothesis`."""
    from services.research_harness.idea_agent import select_hypothesis

    proj = project_dir(project_id)
    sel = _read_json(proj / "ideas" / "selected.json", None)
    if isinstance(sel, dict) and sel:
        return sel
    candidates = _read_json(proj / "ideas" / "candidates.json", None)
    if isinstance(candidates, list) and candidates:
        return select_hypothesis(candidates)
    return None


def load_metrics(project_id: str) -> dict:
    return _read_json(project_dir(project_id) / "artifacts" / "metrics.json", {})


def load_review(project_id: str) -> dict:
    return _read_json(project_dir(project_id) / "reviews" / "review_round_1.json", {})


def append_timeline(project_id: str, step: str, status: str, output_files: list[str]) -> None:
    proj = project_dir(project_id)
    proj.mkdir(parents=True, exist_ok=True)
    entry = {
        "step": step,
        "status": status,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "output_files": output_files,
    }
    with (proj / "timeline.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_timeline(project_id: str) -> list[dict]:
    """Parse ``timeline.jsonl`` into a list of entries (empty list if absent)."""
    path = project_dir(project_id) / "timeline.jsonl"
    if not path.exists():
        return []
    entries: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping unparseable timeline line in %s", path)
    return entries


# --------------------------------------------------------------------------- #
# Project metadata (project.json) — feeds the Projects list & status endpoint
# --------------------------------------------------------------------------- #


def write_project_meta(project_id: str, idea: str, status: str) -> None:
    """Persist/merge lightweight project metadata.

    Preserves ``created_at`` on update so the Projects list ordering is stable.
    """
    proj = project_dir(project_id)
    proj.mkdir(parents=True, exist_ok=True)
    meta_path = proj / "project.json"
    existing = _read_json(meta_path, {}) if isinstance(_read_json(meta_path, {}), dict) else {}
    created_at = existing.get("created_at") or datetime.now().isoformat(timespec="seconds")
    meta = {
        "project_id": project_id,
        "idea": idea,
        "status": status,
        "created_at": created_at,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _derive_idea(project_id: str) -> str:
    """Best-effort idea recovery for legacy workspaces without project.json."""
    report = _read_text(project_dir(project_id) / "research_report.md")
    for line in report.splitlines():
        if line.startswith("# Research Report:"):
            derived = line.replace("# Research Report:", "").strip()
            if derived:
                return derived
            break
    conclusion = _read_text(project_dir(project_id) / "conclusion.md")
    for line in conclusion.splitlines():
        if "**Idea**" in line:
            derived = line.split("**Idea**", 1)[-1].strip().strip(":").strip()
            if derived:
                return derived
    return project_id


def read_project_meta(project_id: str) -> dict | None:
    proj = project_dir(project_id)
    if not proj.exists():
        return None
    meta = _read_json(proj / "project.json", None)
    if isinstance(meta, dict) and meta:
        return meta
    timeline = read_timeline(project_id)
    status = _derive_status_from_timeline(timeline)
    return {
        "project_id": project_id,
        "idea": _derive_idea(project_id),
        "status": status,
        "created_at": (timeline[0]["ts"] if timeline else None),
        "updated_at": (timeline[-1]["ts"] if timeline else None),
        "source": "derived",
    }


def _derive_status_from_timeline(timeline: list[dict]) -> str:
    """Map a timeline to a coarse status used by the Projects list."""
    if not timeline:
        return "pending"
    if any(e.get("status") == "error" for e in timeline):
        return "error"
    done_steps = {e["step"] for e in timeline if e.get("status") == "done"}
    if set(ALL_STEPS).issubset(done_steps):
        return "done"
    return "partial"


def list_workspace_projects() -> list[dict]:
    """List all workspace projects, newest update first."""
    if not WORKSPACE_ROOT.exists():
        return []
    projects: list[dict] = []
    for child in sorted(WORKSPACE_ROOT.iterdir(), reverse=True):
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta = read_project_meta(child.name)
        if meta is None:
            continue
        timeline = read_timeline(child.name)
        # Dedupe steps — a step can appear multiple times after a rerun.
        seen: set[str] = set()
        steps_done: list[str] = []
        for entry in timeline:
            step = entry.get("step")
            if entry.get("status") == "done" and step and step not in seen:
                seen.add(step)
                steps_done.append(step)
        projects.append(
            {
                **meta,
                "steps_done": steps_done,
                "last_ts": (timeline[-1]["ts"] if timeline else meta.get("updated_at")),
            }
        )
    projects.sort(key=lambda p: p.get("last_ts") or "", reverse=True)
    return projects


# --------------------------------------------------------------------------- #
# Step wrappers (relocate of scripts/v0_run.py — behaviour preserved)
# --------------------------------------------------------------------------- #


def run_step_literature(project_id: str, idea: str) -> dict:
    from services.research_harness.literature_agent import run_literature_agent

    notes = run_literature_agent(project_id, idea)
    (project_dir(project_id) / "literature").mkdir(parents=True, exist_ok=True)
    (project_dir(project_id) / "literature" / "notes.json").write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    coverage = notes.get("gap_map", {}).get("literature_coverage", "unknown")
    logger.info("LiteratureAgent complete. Coverage: %s", coverage)
    return notes


def run_step_idea(project_id: str, idea: str) -> dict | None:
    from services.research_harness.idea_agent import run_idea_agent

    notes = load_literature_notes(project_id)
    selected = run_idea_agent(project_id, idea, notes)
    if selected:
        (project_dir(project_id) / "ideas").mkdir(parents=True, exist_ok=True)
        (project_dir(project_id) / "ideas" / "selected.json").write_text(
            json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("IdeaAgent selected: %s", selected.get("title"))
    else:
        logger.error("IdeaAgent failed to produce a hypothesis")
    return selected


def run_step_experiment(project_id: str, idea: str) -> dict:
    from services.research_harness.experiment_engineer import run_experiment_engineer

    notes = load_literature_notes(project_id)
    selected = load_selected_hypothesis(project_id)
    if not selected:
        raise RuntimeError("No selected hypothesis on disk. Run --steps idea first.")
    metrics = run_experiment_engineer(project_id, idea, notes, selected)
    logger.info(
        "ExperimentEngineer complete: status=%s beats_baseline=%s",
        metrics.get("execution_status"),
        metrics.get("baseline_comparison", {}).get("beats_baseline"),
    )
    return metrics


def run_step_review(project_id: str, idea: str) -> dict:
    from services.research_harness.reviewer_agent import run_reviewer_agent

    notes = load_literature_notes(project_id)
    selected = load_selected_hypothesis(project_id)
    metrics = load_metrics(project_id)
    if not metrics:
        raise RuntimeError("No metrics on disk. Run --steps experiment first.")
    review = run_reviewer_agent(project_id, idea, selected or {}, metrics, notes)
    (project_dir(project_id) / "reviews").mkdir(parents=True, exist_ok=True)
    (project_dir(project_id) / "reviews" / "review_round_1.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "ReviewerAgent complete: assessment=%s publish_gate=%s",
        review.get("overall_assessment"),
        review.get("publish_gate"),
    )
    return review


def run_step_report(project_id: str, idea: str) -> Path:
    from services.research_harness.report_generator import generate_research_report
    from services.research_harness.research_manager import run_research_manager

    notes = load_literature_notes(project_id)
    selected = load_selected_hypothesis(project_id) or {}
    metrics = load_metrics(project_id)
    review = load_review(project_id)
    if not metrics or not review:
        raise RuntimeError("No metrics/review on disk. Run --steps review first.")
    manager_decision = run_research_manager(project_id, idea, selected, metrics, review)
    report_path = generate_research_report(project_id, idea, selected, metrics, review, manager_decision)
    logger.info("Report written: %s", report_path)
    return report_path


STEP_FUNCS: dict[str, Callable[[str, str], Any]] = {
    "literature": run_step_literature,
    "idea": run_step_idea,
    "experiment": run_step_experiment,
    "review": run_step_review,
    "report": run_step_report,
}


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def run_pipeline(project_id: str, idea: str, steps: list[str] | None = None) -> dict:
    """Run the ordered agent steps for one project.

    Writes ``timeline.jsonl`` and ``project.json`` status as it goes. Raises only
    on unknown step names; per-step exceptions are recorded on the timeline and
    re-raised so the caller (CLI or background thread) can mark the run as failed.

    Returns a summary dict ``{project_id, idea, steps: [...], status}``.
    """
    resolved = list(steps) if steps else list(ALL_STEPS)
    unknown = [s for s in resolved if s not in ALL_STEPS]
    if unknown:
        raise ValueError(f"Unknown steps: {unknown}. Valid: {ALL_STEPS}")

    project_dir(project_id).mkdir(parents=True, exist_ok=True)
    write_project_meta(project_id, idea, "running")

    logger.info("=== research_harness run: %s ===", project_id)
    summary_steps: list[dict] = []
    failed = False
    for step in resolved:
        logger.info("--- Step: %s ---", step)
        try:
            STEP_FUNCS[step](project_id, idea)
            append_timeline(project_id, step, "done", STEP_OUTPUTS.get(step, []))
            summary_steps.append({"step": step, "status": "done"})
        except Exception:  # noqa: BLE001 — record + propagate
            logger.error("Step %s failed:\n%s", step, traceback.format_exc())
            append_timeline(project_id, step, "error", STEP_OUTPUTS.get(step, []))
            summary_steps.append({"step": step, "status": "error"})
            failed = True
            break

    final_status = "error" if failed else "done"
    write_project_meta(project_id, idea, final_status)
    return {"project_id": project_id, "idea": idea, "steps": summary_steps, "status": final_status}
