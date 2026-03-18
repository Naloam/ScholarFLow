from __future__ import annotations

from sqlalchemy.orm import Session

from schemas.autoresearch import AutoResearchRunRead, TaskFamily
from services.autoresearch.benchmarks import build_experiment_spec
from services.autoresearch.planner import ResearchPlanner
from services.autoresearch.repository import load_run, paper_file_path, save_run
from services.autoresearch.runner import AutoExperimentRunner
from services.autoresearch.writer import PaperWriter
from services.drafts.repository import create_draft
from services.projects.repository import set_project_status


class AutoResearchOrchestrator:
    def __init__(self) -> None:
        self.planner = ResearchPlanner()
        self.runner = AutoExperimentRunner()
        self.writer = PaperWriter()

    def execute(
        self,
        *,
        db: Session,
        project_id: str,
        run_id: str,
        topic: str,
        task_family_hint: TaskFamily | None = None,
        docker_image: str | None = None,
    ) -> AutoResearchRunRead:
        run = load_run(project_id, run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")

        set_project_status(db, project_id, "write")
        run = save_run(run.model_copy(update={"status": "running"}))
        try:
            plan = self.planner.plan(topic, task_family_hint)
            spec = build_experiment_spec(plan.task_family)
            run = save_run(
                run.model_copy(
                    update={
                        "task_family": plan.task_family,
                        "plan": plan,
                        "spec": spec,
                    }
                )
            )

            code_path, artifact = self.runner.run(
                project_id=project_id,
                run_id=run_id,
                plan=plan,
                spec=spec,
                docker_image=docker_image,
            )
            if artifact.status != "done":
                failed = save_run(
                    run.model_copy(
                        update={
                            "status": "failed",
                            "generated_code_path": code_path,
                            "artifact": artifact,
                            "error": artifact.summary,
                        }
                    )
                )
                return failed

            paper_markdown = self.writer.write(plan, spec, artifact)
            draft = create_draft(
                db,
                project_id,
                paper_markdown,
                claims=[],
                section="autorresearch_v0",
            )
            set_project_status(db, project_id, "edit")
            completed = save_run(
                run.model_copy(
                    update={
                        "status": "done",
                        "generated_code_path": code_path,
                        "artifact": artifact,
                        "paper_markdown": paper_markdown,
                        "paper_path": paper_file_path(project_id, run_id),
                        "paper_draft_version": draft.version,
                    }
                )
            )
            return completed
        except Exception as exc:
            failed = save_run(
                run.model_copy(
                    update={
                        "status": "failed",
                        "error": str(exc),
                    }
                )
            )
            return failed
