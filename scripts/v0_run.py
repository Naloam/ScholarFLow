#!/usr/bin/env python3
"""
ScholarFlow V0 — end-to-end research run CLI.

Usage:
  cd backend
  PYTHONPATH=. python ../scripts/v0_run.py --idea "your research idea"
  PYTHONPATH=. python ../scripts/v0_run.py --idea "..." --steps experiment   # rerun one step

Output: everything under ``backend/data/research_workspace/<project_id>/``.

The pipeline logic now lives in ``services.research_harness.pipeline`` so the
FastAPI layer and this CLI share one implementation.
"""
from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

# Ensure backend modules are importable when run as a script.
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("v0_run")

from services.research_harness.pipeline import (  # noqa: E402
    ALL_STEPS,
    project_dir,
    run_pipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="ScholarFlow V0 Research Run")
    parser.add_argument("--idea", required=True, help="Research idea string")
    parser.add_argument("--project-id", default=None, help="Project ID (auto-generated if not set)")
    parser.add_argument(
        "--steps",
        default="all",
        help='Comma-separated steps (literature,idea,experiment,review,report) or "all"',
    )
    args = parser.parse_args()

    project_id = args.project_id or f"v0_{uuid.uuid4().hex[:8]}"
    raw_steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    steps = None if raw_steps == ["all"] else raw_steps

    logger.info("=== ScholarFlow V0 Run ===")
    logger.info("Project ID: %s", project_id)
    logger.info("Idea: %s", args.idea)
    logger.info("Steps: %s", steps or ALL_STEPS)

    result = run_pipeline(project_id, args.idea, steps=steps)
    logger.info("Run status: %s", result["status"])

    workspace_path = project_dir(project_id)
    logger.info("\n=== V0 Run Complete ===")
    logger.info("Workspace: %s", workspace_path.resolve())
    if workspace_path.exists():
        for f in sorted(workspace_path.rglob("*")):
            if f.is_file():
                logger.info("  %s (%d bytes)", f.relative_to(workspace_path), f.stat().st_size)


if __name__ == "__main__":
    main()
