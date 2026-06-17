#!/usr/bin/env python3
"""
ScholarFlow V0 — 端到端研究流程测试脚本

用法：
  cd backend
  PYTHONPATH=. python ../scripts/v0_run.py --idea "你的研究 idea"
  PYTHONPATH=. python ../scripts/v0_run.py --idea "..." --steps experiment   # 单步重跑

输出：backend/data/research_workspace/<project_id>/ 目录下的全部文件。

步骤（默认 all = literature,idea,experiment,review,report）：
  literature → idea → experiment → review → report

每步从磁盘 load 上一步产物（支持单步重跑）；每步完成追加 timeline.jsonl。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

# 确保能找到 backend 的模块
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("v0_run")

from config.settings import settings  # noqa: E402

WORKSPACE_ROOT = Path(settings.data_dir) / "research_workspace"

ALL_STEPS = ["literature", "idea", "experiment", "review", "report"]
STEP_OUTPUTS = {
    "literature": [
        "literature/search_queries.json", "literature/papers.jsonl",
        "literature/notes.md", "literature/gap_map.md",
        "literature/known_baselines.md", "literature/notes.json",
    ],
    "idea": ["ideas/candidates.json", "ideas/selected.md", "ideas/selected.json"],
    "experiment": [
        "experiments/plan.json", "experiments/plan.md",
        "code/experiment.py", "code/requirements.txt",
        "artifacts/metrics.json", "artifacts/tables/results.csv",
    ],
    "review": [
        "reviews/reviewer_round_1.md", "reviews/action_plan_1.json",
        "reviews/review_round_1.json",
    ],
    "report": ["research_report.md", "conclusion.md"],
}


# --------------------------------------------------------------------------- #
# 磁盘加载辅助（每步可独立重跑）
# --------------------------------------------------------------------------- #


def _project(project_id: str) -> Path:
    return WORKSPACE_ROOT / project_id


def _read_json(path: Path, default):
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
    """优先读 literature/notes.json（结构化）；否则从 markdown 重建最小 notes。"""
    proj = _project(project_id)
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


def load_selected_hypothesis(project_id: str):
    """优先读 ideas/selected.json；否则读 candidates.json 复用 select_hypothesis。"""
    from services.research_harness.idea_agent import select_hypothesis

    proj = _project(project_id)
    sel = _read_json(proj / "ideas" / "selected.json", None)
    if isinstance(sel, dict) and sel:
        return sel
    candidates = _read_json(proj / "ideas" / "candidates.json", None)
    if isinstance(candidates, list) and candidates:
        return select_hypothesis(candidates)
    return None


def load_metrics(project_id: str) -> dict:
    return _read_json(_project(project_id) / "artifacts" / "metrics.json", {})


def load_review(project_id: str) -> dict:
    return _read_json(_project(project_id) / "reviews" / "review_round_1.json", {})


def append_timeline(project_id: str, step: str, status: str, output_files: list[str]) -> None:
    proj = _project(project_id)
    proj.mkdir(parents=True, exist_ok=True)
    entry = {
        "step": step,
        "status": status,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "output_files": output_files,
    }
    with (proj / "timeline.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# 各 step
# --------------------------------------------------------------------------- #


def run_step_literature(project_id: str, idea: str) -> dict:
    from services.research_harness.literature_agent import run_literature_agent

    notes = run_literature_agent(project_id, idea)
    # 落盘结构化 notes.json，供后续步骤单步重跑时 load（Session 1 只写了 markdown）。
    (_project(project_id) / "literature").mkdir(parents=True, exist_ok=True)
    (_project(project_id) / "literature" / "notes.json").write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    coverage = notes.get("gap_map", {}).get("literature_coverage", "unknown")
    logger.info("LiteratureAgent complete. Coverage: %s", coverage)
    return notes


def run_step_idea(project_id: str, idea: str):
    from services.research_harness.idea_agent import run_idea_agent

    notes = load_literature_notes(project_id)
    selected = run_idea_agent(project_id, idea, notes)
    if selected:
        # 落盘结构化 selected.json，供后续步骤单步重跑时 load。
        (_project(project_id) / "ideas").mkdir(parents=True, exist_ok=True)
        (_project(project_id) / "ideas" / "selected.json").write_text(
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
        logger.error("No selected hypothesis on disk. Run --steps idea first.")
        sys.exit(1)
    metrics = run_experiment_engineer(project_id, idea, notes, selected)
    logger.info(
        "ExperimentEngineer complete: status=%s beats_baseline=%s",
        metrics.get("execution_status"), metrics.get("baseline_comparison", {}).get("beats_baseline"),
    )
    return metrics


def run_step_review(project_id: str, idea: str) -> dict:
    from services.research_harness.reviewer_agent import run_reviewer_agent

    notes = load_literature_notes(project_id)
    selected = load_selected_hypothesis(project_id)
    metrics = load_metrics(project_id)
    if not metrics:
        logger.error("No metrics on disk. Run --steps experiment first.")
        sys.exit(1)
    review = run_reviewer_agent(project_id, idea, selected or {}, metrics, notes)
    # 落盘结构化 review_round_1.json，供 report 单步重跑时 load。
    (_project(project_id) / "reviews").mkdir(parents=True, exist_ok=True)
    (_project(project_id) / "reviews" / "review_round_1.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "ReviewerAgent complete: assessment=%s publish_gate=%s",
        review.get("overall_assessment"), review.get("publish_gate"),
    )
    return review


def run_step_report(project_id: str, idea: str) -> Path:
    from services.research_harness.research_manager import run_research_manager
    from services.research_harness.report_generator import generate_research_report

    notes = load_literature_notes(project_id)
    selected = load_selected_hypothesis(project_id) or {}
    metrics = load_metrics(project_id)
    review = load_review(project_id)
    if not metrics or not review:
        logger.error("No metrics/review on disk. Run --steps review first.")
        sys.exit(1)
    manager_decision = run_research_manager(project_id, idea, selected, metrics, review)
    report_path = generate_research_report(project_id, idea, selected, metrics, review, manager_decision)
    logger.info("Report written: %s", report_path)
    return report_path


STEP_FUNCS = {
    "literature": run_step_literature,
    "idea": run_step_idea,
    "experiment": run_step_experiment,
    "review": run_step_review,
    "report": run_step_report,
}


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(description="ScholarFlow V0 Research Run")
    parser.add_argument("--idea", required=True, help="Research idea string")
    parser.add_argument("--project-id", default=None, help="Project ID (auto-generated if not set)")
    parser.add_argument(
        "--steps", default="all",
        help='Comma-separated steps (literature,idea,experiment,review,report) or "all"',
    )
    args = parser.parse_args()

    project_id = args.project_id or f"v0_{__import__('uuid').uuid4().hex[:8]}"
    raw_steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    steps = ALL_STEPS if raw_steps == ["all"] else raw_steps
    unknown = [s for s in steps if s not in ALL_STEPS]
    if unknown:
        parser.error(f"Unknown steps: {unknown}. Valid: {ALL_STEPS + ['all']}")

    _project(project_id).mkdir(parents=True, exist_ok=True)

    logger.info("=== ScholarFlow V0 Run ===")
    logger.info("Project ID: %s", project_id)
    logger.info("Idea: %s", args.idea)
    logger.info("Steps: %s", steps)

    for step in steps:
        logger.info("\n--- Step: %s ---", step)
        try:
            STEP_FUNCS[step](project_id, args.idea)
            append_timeline(project_id, step, "done", STEP_OUTPUTS.get(step, []))
        except SystemExit:
            raise
        except Exception:
            logger.error("Step %s failed:\n%s", step, traceback.format_exc())
            append_timeline(project_id, step, "error", STEP_OUTPUTS.get(step, []))
            raise

    workspace_path = _project(project_id)
    logger.info("\n=== V0 Run Complete ===")
    logger.info("Workspace: %s", workspace_path.resolve())
    if workspace_path.exists():
        for f in sorted(workspace_path.rglob("*")):
            if f.is_file():
                logger.info("  %s (%d bytes)", f.relative_to(workspace_path), f.stat().st_size)


if __name__ == "__main__":
    main()
