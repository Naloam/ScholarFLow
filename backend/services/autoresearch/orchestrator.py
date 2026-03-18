from __future__ import annotations

from sqlalchemy.orm import Session

from schemas.autoresearch import (
    AutoResearchRunRead,
    BenchmarkSource,
    ExecutionBackendSpec,
    ExperimentAttempt,
    ResultArtifact,
    TaskFamily,
)
from services.autoresearch.benchmarks import build_experiment_spec
from services.autoresearch.ingestion import resolve_benchmark
from services.autoresearch.literature_pipeline import gather_literature_context
from services.autoresearch.planner import ResearchPlanner
from services.autoresearch.repair import ExperimentRepairEngine
from services.autoresearch.repository import (
    load_run,
    paper_file_path,
    save_benchmark_snapshot,
    save_run,
)
from services.autoresearch.runner import AutoExperimentRunner
from services.autoresearch.writer import PaperWriter
from services.drafts.repository import create_draft
from services.projects.repository import set_project_status


class AutoResearchOrchestrator:
    def __init__(self) -> None:
        self.planner = ResearchPlanner()
        self.repair = ExperimentRepairEngine()
        self.runner = AutoExperimentRunner()
        self.writer = PaperWriter()

    def _attempt_goal(self, attempts: list[ExperimentAttempt], round_index: int) -> str:
        if round_index == 1:
            return "initial_run"
        if attempts and attempts[-1].status == "failed":
            return "repair_previous_failure"
        return "search_for_better_candidate"

    def _artifact_score(self, artifact: ResultArtifact) -> float:
        if artifact.objective_score is not None:
            return float(artifact.objective_score)
        if artifact.best_system:
            for item in artifact.system_results:
                if item.system == artifact.best_system:
                    value = item.metrics.get(artifact.primary_metric)
                    if value is not None:
                        return float(value)
        return float("-inf")

    def _attempt_critique(
        self,
        artifact: ResultArtifact,
        attempts: list[ExperimentAttempt],
    ) -> str:
        if artifact.status != "done":
            return "Attempt failed, so the next round should repair execution and preserve a result artifact."
        if not attempts:
            return "First successful attempt establishes the initial objective score."
        previous = attempts[-1].artifact
        if previous is None:
            return "Previous attempt had no artifact, so this round restores executable results."
        prev_score = self._artifact_score(previous)
        current_score = self._artifact_score(artifact)
        if current_score > prev_score:
            return (
                f"Objective score improved from {prev_score:.4f} to {current_score:.4f}; "
                "keep the stronger candidate as the current best."
            )
        return (
            f"Objective score did not improve over the previous round ({prev_score:.4f} -> "
            f"{current_score:.4f}); retain the earlier best candidate."
        )

    def execute(
        self,
        *,
        db: Session,
        project_id: str,
        run_id: str,
        topic: str,
        task_family_hint: TaskFamily | None = None,
        paper_ids: list[str] | None = None,
        max_rounds: int = 3,
        benchmark_source: BenchmarkSource | None = None,
        execution_backend: ExecutionBackendSpec | None = None,
        auto_search_literature: bool = True,
        auto_fetch_literature: bool = False,
        docker_image: str | None = None,
    ) -> AutoResearchRunRead:
        run = load_run(project_id, run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")

        set_project_status(db, project_id, "write")
        run = save_run(run.model_copy(update={"status": "running"}))
        try:
            effective_backend = execution_backend or run.execution_backend
            if effective_backend is None and docker_image:
                effective_backend = ExecutionBackendSpec(docker_image=docker_image)
            papers, literature, chunk_context = gather_literature_context(
                db=db,
                project_id=project_id,
                topic=topic,
                paper_ids=paper_ids,
                auto_search=auto_search_literature,
                auto_fetch=auto_fetch_literature,
            )
            benchmark = resolve_benchmark(
                topic=topic,
                task_family_hint=task_family_hint,
                benchmark_source=benchmark_source,
            )
            benchmark_snapshot_path = save_benchmark_snapshot(
                project_id,
                run_id,
                {
                    "source": benchmark.source.model_dump(mode="json"),
                    "task_family": benchmark.task_family,
                    "benchmark_name": benchmark.benchmark_name,
                    "benchmark_description": benchmark.benchmark_description,
                    "payload": benchmark.payload,
                },
            )

            plan = self.planner.plan(topic, benchmark.task_family, literature)
            if not plan.experiment_outline:
                plan.experiment_outline = [
                    "Pull or instantiate a benchmark snapshot and freeze train/test partitions.",
                    "Run baseline and candidate systems.",
                    "Summarize metrics and environment metadata.",
                ]
            plan.experiment_outline[0] = (
                "Pull a benchmark snapshot, validate its schema, and freeze train/test partitions."
                if benchmark.source.kind != "builtin"
                else "Instantiate the selected benchmark and freeze train/test partitions."
            )
            spec = build_experiment_spec(plan.task_family, benchmark)
            run = save_run(
                run.model_copy(
                    update={
                        "task_family": plan.task_family,
                        "benchmark": benchmark.source,
                        "execution_backend": effective_backend,
                        "plan": plan,
                        "spec": spec,
                        "literature": literature,
                    }
                )
            )

            attempts: list[ExperimentAttempt] = []
            best_attempt: ExperimentAttempt | None = None
            total_rounds = max(1, min(max_rounds, max(1, len(spec.search_strategies))))

            for round_index in range(1, total_rounds + 1):
                goal = self._attempt_goal(attempts, round_index)
                if goal == "repair_previous_failure" and attempts:
                    repair_strategy, repaired_code = self.repair.repair(
                        previous_attempt=attempts[-1],
                        plan=plan,
                        spec=spec,
                        benchmark_payload=benchmark.payload,
                    )
                    if repair_strategy != "repair_regenerate":
                        strategy, code_path, artifact = self.runner.run(
                            project_id=project_id,
                            run_id=run_id,
                            plan=plan,
                            spec=spec,
                            benchmark_payload=benchmark.payload,
                            round_index=round_index,
                            goal=goal,
                            prior_attempts=attempts,
                            execution_backend=effective_backend,
                            code_override=repaired_code,
                            strategy_override=repair_strategy,
                        )
                    else:
                        strategy, code_path, artifact = self.runner.run(
                            project_id=project_id,
                            run_id=run_id,
                            plan=plan,
                            spec=spec,
                            benchmark_payload=benchmark.payload,
                            round_index=round_index,
                            goal=goal,
                            prior_attempts=attempts,
                            execution_backend=effective_backend,
                        )
                else:
                    strategy, code_path, artifact = self.runner.run(
                        project_id=project_id,
                        run_id=run_id,
                        plan=plan,
                        spec=spec,
                        benchmark_payload=benchmark.payload,
                        round_index=round_index,
                        goal=goal,
                        prior_attempts=attempts,
                        execution_backend=effective_backend,
                    )
                artifact.environment.setdefault("benchmark_snapshot_path", benchmark_snapshot_path)
                if chunk_context:
                    artifact.environment.setdefault("literature_chunk_context", chunk_context)
                critique = self._attempt_critique(artifact, attempts)
                attempt = ExperimentAttempt(
                    round_index=round_index,
                    strategy=strategy,
                    goal=goal,
                    status="done" if artifact.status == "done" else "failed",
                    summary=artifact.summary,
                    critique=critique,
                    code_path=code_path,
                    artifact=artifact,
                )
                attempts.append(attempt)

                if artifact.status == "done" and (
                    best_attempt is None
                    or self._artifact_score(artifact) > self._artifact_score(best_attempt.artifact)  # type: ignore[arg-type]
                ):
                    best_attempt = attempt

                run = save_run(
                    run.model_copy(
                        update={
                            "attempts": attempts,
                            "generated_code_path": code_path,
                            "artifact": best_attempt.artifact if best_attempt else artifact,
                            "selected_round_index": best_attempt.round_index if best_attempt else None,
                        }
                    )
                )

            if best_attempt is None or best_attempt.artifact is None:
                failed = save_run(
                    run.model_copy(
                        update={
                            "status": "failed",
                            "attempts": attempts,
                            "error": attempts[-1].summary if attempts else "No attempt produced a result artifact",
                        }
                    )
                )
                return failed

            artifact = best_attempt.artifact
            paper_markdown = self.writer.write(
                plan,
                spec,
                artifact,
                literature=literature,
                attempts=attempts,
                benchmark_name=benchmark.benchmark_name,
            )
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
                            "generated_code_path": best_attempt.code_path,
                            "artifact": artifact,
                            "paper_markdown": paper_markdown,
                            "paper_path": paper_file_path(project_id, run_id),
                            "paper_draft_version": draft.version,
                        "attempts": attempts,
                        "selected_round_index": best_attempt.round_index,
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
