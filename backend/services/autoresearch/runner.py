from __future__ import annotations

import re
from typing import Any

from agents.sandbox_agent import SandboxAgent
from schemas.autoresearch import (
    ExecutionBackendSpec,
    ExperimentAttempt,
    ExperimentSpec,
    ResearchPlan,
    ResultArtifact,
)
from services.autoresearch.codegen import ExperimentCodeGenerator
from services.autoresearch.repository import save_generated_code


class AutoExperimentRunner:
    def __init__(self) -> None:
        self.codegen = ExperimentCodeGenerator()
        self.sandbox = SandboxAgent()

    def _build_failed_artifact(self, logs: str, outputs: dict[str, Any]) -> ResultArtifact:
        return ResultArtifact(
            status="failed",
            summary="The experiment failed before producing a structured result artifact.",
            primary_metric="macro_f1",
            logs=logs,
            environment={
                "executor_mode": outputs.get("executor_mode"),
                "docker_image": outputs.get("docker_image"),
                "workdir": outputs.get("workdir"),
                "duration_ms": outputs.get("duration_ms"),
                "host_platform": outputs.get("host_platform"),
                "host_python": outputs.get("host_python"),
            },
            outputs=outputs,
        )

    def _build_artifact(self, logs: str, outputs: dict[str, Any]) -> ResultArtifact:
        payload = outputs.get("result")
        if not isinstance(payload, dict):
            return self._build_failed_artifact(logs, outputs)

        payload_environment = payload.get("environment")
        environment = payload_environment if isinstance(payload_environment, dict) else {}
        environment.update(
            {
                "executor_mode": outputs.get("executor_mode"),
                "docker_image": outputs.get("docker_image"),
                "workdir": outputs.get("workdir"),
                "duration_ms": outputs.get("duration_ms"),
                "host_platform": outputs.get("host_platform"),
                "host_python": outputs.get("host_python"),
            }
        )
        return ResultArtifact(
            status="done" if outputs.get("returncode", 1) == 0 else "failed",
            summary=str(payload.get("summary") or "Experiment completed."),
            key_findings=[
                str(item)
                for item in (payload.get("key_findings") or [])
                if isinstance(item, str) and item.strip()
            ],
            primary_metric=str(payload.get("primary_metric") or "macro_f1"),
            best_system=(
                str(payload.get("best_system"))
                if payload.get("best_system") is not None
                else None
            ),
            system_results=payload.get("system_results") or [],
            tables=payload.get("tables") or [],
            logs=logs,
            environment=environment,
            outputs=outputs,
        )

    def run(
        self,
        *,
        project_id: str,
        run_id: str,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
        round_index: int,
        goal: str,
        prior_attempts: list[ExperimentAttempt],
        execution_backend: ExecutionBackendSpec | None = None,
        code_override: str | None = None,
        strategy_override: str | None = None,
    ) -> tuple[str, str, ResultArtifact]:
        if code_override is not None and strategy_override is not None:
            strategy, code = strategy_override, code_override
        else:
            strategy, code = self.codegen.generate(
                plan=plan,
                spec=spec,
                benchmark_payload=benchmark_payload,
                round_index=round_index,
                goal=goal,
                prior_attempts=prior_attempts,
            )
        safe_strategy = re.sub(r"[^a-zA-Z0-9_]+", "_", strategy).strip("_") or "attempt"
        code_path = save_generated_code(
            project_id,
            run_id,
            code,
            filename=f"experiment_round_{round_index}_{safe_strategy}.py",
        )
        result = self.sandbox.run(
            {
                "project_id": project_id,
                "code": code,
                "execution_backend": (
                    execution_backend.model_dump(mode="json") if execution_backend else None
                ),
            }
        )
        logs = str(result.get("logs") or "")
        outputs = result.get("outputs") if isinstance(result.get("outputs"), dict) else {}
        artifact = self._build_artifact(logs, outputs)
        artifact.environment.setdefault("generated_code_path", code_path)
        artifact.environment.setdefault("strategy", strategy)
        return strategy, code_path, artifact
