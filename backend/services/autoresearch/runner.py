from __future__ import annotations

import json
import math
import re
from typing import Any

from agents.sandbox_agent import SandboxAgent
from schemas.autoresearch import (
    AcceptanceCheck,
    AggregateSystemMetricResult,
    ExecutionBackendSpec,
    ExperimentAttempt,
    ExperimentSpec,
    ResearchPlan,
    ResultArtifact,
    ResultTable,
    SeedArtifactResult,
    SweepConfig,
    SweepEvaluationResult,
    SystemMetricResult,
)
from services.autoresearch.codegen import ExperimentCodeGenerator
from services.autoresearch.runtime_contract import runtime_environment_violations
from services.autoresearch.repository import save_generated_code


def _round_metric(value: float) -> float:
    return round(value, 4)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    center = _mean(values)
    variance = sum((value - center) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _metric_label(name: str) -> str:
    labels = {
        "accuracy": "Accuracy",
        "macro_f1": "Macro F1",
        "mrr": "MRR",
        "recall_at_1": "Recall@1",
    }
    return labels.get(name, name.replace("_", " ").title())


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
            best_system=str(payload.get("best_system")) if payload.get("best_system") is not None else None,
            objective_system=(
                str(payload.get("objective_system"))
                if payload.get("objective_system") is not None
                else None
            ),
            objective_score=(
                float(payload.get("objective_score"))
                if payload.get("objective_score") is not None
                else None
            ),
            system_results=payload.get("system_results") or [],
            aggregate_system_results=payload.get("aggregate_system_results") or [],
            per_seed_results=payload.get("per_seed_results") or [],
            sweep_results=payload.get("sweep_results") or [],
            acceptance_checks=payload.get("acceptance_checks") or [],
            tables=payload.get("tables") or [],
            logs=logs,
            environment=environment,
            outputs=outputs,
        )

    def _runtime_contract_failure(
        self,
        artifact: ResultArtifact,
        *,
        seed: int,
        sweep: SweepConfig,
        code_path: str,
        strategy: str,
        violations: list[str],
    ) -> ResultArtifact:
        environment = dict(artifact.environment)
        environment.update(
            {
                "generated_code_path": code_path,
                "strategy": strategy,
                "expected_seed": seed,
                "expected_sweep": sweep.params,
                "runtime_contract_violations": violations,
            }
        )
        logs = (
            f"{artifact.logs or ''}\n"
            f"Runtime contract violation for seed={seed} sweep={sweep.label}: {', '.join(violations)}"
        ).strip()
        return ResultArtifact(
            status="failed",
            summary=(
                "The experiment completed but did not record the active seed/sweep configuration "
                "required by the runtime contract."
            ),
            key_findings=artifact.key_findings,
            primary_metric=artifact.primary_metric,
            best_system=artifact.best_system,
            objective_system=artifact.objective_system,
            objective_score=artifact.objective_score,
            system_results=artifact.system_results,
            tables=artifact.tables,
            logs=logs,
            environment=environment,
            outputs=artifact.outputs,
        )

    def _execution_env(self, seed: int, sweep: SweepConfig) -> dict[str, str]:
        return {
            "SCHOLARFLOW_SEED": str(seed),
            "SCHOLARFLOW_SWEEP_JSON": json.dumps(sweep.params, ensure_ascii=False, sort_keys=True),
        }

    def _run_once(
        self,
        *,
        project_id: str,
        code: str,
        execution_backend: ExecutionBackendSpec | None,
        seed: int,
        sweep: SweepConfig,
        code_path: str,
        strategy: str,
    ) -> ResultArtifact:
        result = self.sandbox.run(
            {
                "project_id": project_id,
                "code": code,
                "env": self._execution_env(seed, sweep),
                "execution_backend": (
                    execution_backend.model_dump(mode="json") if execution_backend else None
                ),
            }
        )
        logs = str(result.get("logs") or "")
        outputs = result.get("outputs") if isinstance(result.get("outputs"), dict) else {}
        artifact = self._build_artifact(logs, outputs)
        violations = runtime_environment_violations(
            artifact.environment,
            expected_seed=seed,
            expected_sweep=sweep.params,
        )
        if violations:
            return self._runtime_contract_failure(
                artifact,
                seed=seed,
                sweep=sweep,
                code_path=code_path,
                strategy=strategy,
                violations=violations,
            )
        artifact.environment.setdefault("generated_code_path", code_path)
        artifact.environment.setdefault("strategy", strategy)
        artifact.environment.setdefault("seed", seed)
        artifact.environment.setdefault("sweep", sweep.params)
        artifact.environment["sweep_label"] = sweep.label
        artifact.environment["sweep_params"] = sweep.params
        return artifact

    def _aggregate_system_results(
        self,
        artifacts: list[ResultArtifact],
    ) -> tuple[list[SystemMetricResult], list[AggregateSystemMetricResult]]:
        metrics_by_system: dict[str, dict[str, list[float]]] = {}
        for artifact in artifacts:
            for item in artifact.system_results:
                bucket = metrics_by_system.setdefault(item.system, {})
                for metric_name, value in item.metrics.items():
                    bucket.setdefault(metric_name, []).append(float(value))

        aggregate_results: list[AggregateSystemMetricResult] = []
        mean_results: list[SystemMetricResult] = []
        for system, metric_map in metrics_by_system.items():
            mean_metrics = {
                metric_name: _round_metric(_mean(values))
                for metric_name, values in metric_map.items()
                if values
            }
            std_metrics = {
                metric_name: _round_metric(_std(values))
                for metric_name, values in metric_map.items()
                if values
            }
            min_metrics = {
                metric_name: _round_metric(min(values))
                for metric_name, values in metric_map.items()
                if values
            }
            max_metrics = {
                metric_name: _round_metric(max(values))
                for metric_name, values in metric_map.items()
                if values
            }
            sample_count = max((len(values) for values in metric_map.values()), default=0) or 1
            aggregate_results.append(
                AggregateSystemMetricResult(
                    system=system,
                    mean_metrics=mean_metrics,
                    std_metrics=std_metrics,
                    min_metrics=min_metrics,
                    max_metrics=max_metrics,
                    sample_count=sample_count,
                )
            )
            mean_results.append(SystemMetricResult(system=system, metrics=mean_metrics))
        return mean_results, aggregate_results

    def _aggregate_tables(
        self,
        *,
        primary_metric: str,
        aggregate_results: list[AggregateSystemMetricResult],
        sweep_results: list[SweepEvaluationResult],
        per_seed_results: list[SeedArtifactResult],
    ) -> list[ResultTable]:
        if not aggregate_results:
            return []

        metric_order: list[str] = []
        for item in aggregate_results:
            for metric_name in item.mean_metrics:
                if metric_name not in metric_order:
                    metric_order.append(metric_name)
        if primary_metric and primary_metric not in metric_order:
            metric_order.append(primary_metric)

        ranked = sorted(
            aggregate_results,
            key=lambda item: item.mean_metrics.get(primary_metric, float("-inf")),
            reverse=True,
        )
        tables = [
            ResultTable(
                title="Main Results",
                columns=["System", *[_metric_label(metric) for metric in metric_order]],
                rows=[
                    [item.system, *[f"{item.mean_metrics.get(metric, 0.0):.4f}" for metric in metric_order]]
                    for item in ranked
                ],
            ),
            ResultTable(
                title="Aggregate Stability",
                columns=["System", *[f"{_metric_label(metric)} Std" for metric in metric_order]],
                rows=[
                    [item.system, *[f"{item.std_metrics.get(metric, 0.0):.4f}" for metric in metric_order]]
                    for item in ranked
                ],
            ),
        ]
        if len(sweep_results) > 1:
            tables.append(
                ResultTable(
                    title="Sweep Summary",
                    columns=[
                        "Sweep",
                        "Objective System",
                        f"{_metric_label(primary_metric)} Mean",
                        f"{_metric_label(primary_metric)} Std",
                        "Best System",
                        "Seeds",
                    ],
                    rows=[
                        [
                            item.label,
                            item.objective_system or "unknown",
                            f"{item.objective_score_mean:.4f}" if item.objective_score_mean is not None else "n/a",
                            f"{item.objective_score_std:.4f}" if item.objective_score_std is not None else "n/a",
                            item.best_system or "unknown",
                            str(item.seed_count),
                        ]
                        for item in sweep_results
                    ],
                )
            )
        tables.append(
            ResultTable(
                title="Seed Runs",
                columns=["Seed", "Sweep", "Objective System", _metric_label(primary_metric), "Best System"],
                rows=[
                    [
                        str(item.seed),
                        item.sweep_label,
                        item.objective_system or "unknown",
                        f"{item.objective_score:.4f}" if item.objective_score is not None else "n/a",
                        item.best_system or "unknown",
                    ]
                    for item in per_seed_results
                ],
            )
        )
        return tables

    def _acceptance_checks(
        self,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
    ) -> list[AcceptanceCheck]:
        mean_by_system = {
            item.system: item.mean_metrics for item in artifact.aggregate_system_results
        }
        selected_sweep = str(artifact.environment.get("selected_sweep") or "unknown")
        checks: list[AcceptanceCheck] = []
        for criterion in spec.acceptance_criteria:
            lowered = criterion.lower()
            if "every requested seed" in lowered:
                passed = len(artifact.per_seed_results) == max(1, len(spec.seeds))
                detail = (
                    f"Selected sweep `{selected_sweep}` completed {len(artifact.per_seed_results)}/"
                    f"{max(1, len(spec.seeds))} requested seeds."
                )
            elif "mean and standard deviation" in lowered:
                objective_metrics = mean_by_system.get(artifact.objective_system or "")
                objective_stats = next(
                    (
                        item.std_metrics.get(artifact.primary_metric)
                        for item in artifact.aggregate_system_results
                        if item.system == artifact.objective_system
                    ),
                    None,
                )
                passed = (
                    objective_metrics is not None
                    and artifact.primary_metric in objective_metrics
                    and objective_stats is not None
                )
                detail = (
                    f"Primary metric `{artifact.primary_metric}` mean/std were recorded for "
                    f"`{artifact.objective_system or artifact.best_system or 'unknown'}`."
                )
            elif "majority baseline" in lowered or "random baseline" in lowered:
                baseline = "random_ranker" if "random baseline" in lowered else "majority"
                baseline_score = mean_by_system.get(baseline, {}).get(artifact.primary_metric)
                objective_score = artifact.objective_score
                passed = (
                    objective_score is not None
                    and (baseline_score is None or objective_score > baseline_score)
                )
                detail = (
                    f"Objective mean {artifact.primary_metric}="
                    f"{artifact.objective_score if artifact.objective_score is not None else float('nan'):.4f} "
                    f"vs {baseline}="
                    f"{baseline_score if baseline_score is not None else float('nan'):.4f}"
                )
            else:
                passed = bool(artifact.aggregate_system_results)
                detail = "Aggregate experiment outputs were recorded."
            checks.append(AcceptanceCheck(criterion=criterion, passed=passed, detail=detail))
        return checks

    def _sweep_candidates(self, spec: ExperimentSpec) -> list[SweepConfig]:
        if spec.sweeps:
            return spec.sweeps
        return [SweepConfig(label="default", params={}, description="Single default configuration.")]

    def _seed_candidates(self, spec: ExperimentSpec) -> list[int]:
        return spec.seeds or [0]

    def _select_best_sweep(
        self,
        sweep_results: list[SweepEvaluationResult],
    ) -> SweepEvaluationResult | None:
        successful = [item for item in sweep_results if item.status == "done"]
        if not successful:
            return None
        return max(
            successful,
            key=lambda item: item.objective_score_mean if item.objective_score_mean is not None else float("-inf"),
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
        code_filename_prefix: str | None = None,
        code_subdir: str | None = None,
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
        safe_prefix = re.sub(r"[^a-zA-Z0-9_]+", "_", code_filename_prefix or "").strip("_")
        filename_prefix = f"{safe_prefix}_" if safe_prefix else ""
        code_path = save_generated_code(
            project_id,
            run_id,
            code,
            filename=f"{filename_prefix}experiment_round_{round_index}_{safe_strategy}.py",
            subdir=code_subdir,
        )

        sweep_results: list[SweepEvaluationResult] = []
        selected_artifacts_by_sweep: dict[str, list[ResultArtifact]] = {}
        selected_seed_results_by_sweep: dict[str, list[SeedArtifactResult]] = {}
        failed_artifacts: list[ResultArtifact] = []

        for sweep in self._sweep_candidates(spec):
            artifacts: list[ResultArtifact] = []
            per_seed_results: list[SeedArtifactResult] = []
            failed_seeds: list[int] = []
            for seed in self._seed_candidates(spec):
                artifact = self._run_once(
                    project_id=project_id,
                    code=code,
                    execution_backend=execution_backend,
                    seed=seed,
                    sweep=sweep,
                    code_path=code_path,
                    strategy=strategy,
                )
                if artifact.status != "done":
                    failed_artifacts.append(artifact)
                    failed_seeds.append(seed)
                    break
                artifacts.append(artifact)
                per_seed_results.append(
                    SeedArtifactResult(
                        seed=seed,
                        sweep_label=sweep.label,
                        best_system=artifact.best_system,
                        objective_system=artifact.objective_system,
                        objective_score=artifact.objective_score,
                        primary_metric=artifact.primary_metric,
                        system_results=artifact.system_results,
                    )
                )

            if artifacts:
                mean_results, aggregate_results = self._aggregate_system_results(artifacts)
                primary_metric = artifacts[0].primary_metric
                objective_system = artifacts[0].objective_system
                objective_scores = [
                    float(item.objective_score)
                    for item in artifacts
                    if item.objective_score is not None
                ]
                best_system = max(
                    mean_results,
                    key=lambda item: item.metrics.get(primary_metric, float("-inf")),
                ).system if mean_results else None
                sweep_results.append(
                    SweepEvaluationResult(
                        label=sweep.label,
                        params=sweep.params,
                        description=sweep.description,
                        status="done" if not failed_seeds else "failed",
                        best_system=best_system,
                        objective_system=objective_system,
                        objective_score_mean=(
                            _round_metric(_mean(objective_scores))
                            if objective_scores
                            else None
                        ),
                        objective_score_std=(
                            _round_metric(_std(objective_scores))
                            if objective_scores
                            else None
                        ),
                        aggregate_system_results=aggregate_results,
                        failed_seeds=failed_seeds,
                        seed_count=len(artifacts),
                    )
                )
                if not failed_seeds:
                    selected_artifacts_by_sweep[sweep.label] = artifacts
                    selected_seed_results_by_sweep[sweep.label] = per_seed_results
            else:
                sweep_results.append(
                    SweepEvaluationResult(
                        label=sweep.label,
                        params=sweep.params,
                        description=sweep.description,
                        status="failed",
                        failed_seeds=failed_seeds,
                        seed_count=0,
                    )
                )

        selected_sweep = self._select_best_sweep(sweep_results)
        if selected_sweep is None:
            failed = failed_artifacts[-1] if failed_artifacts else self._build_failed_artifact("", {})
            failed.environment.setdefault("generated_code_path", code_path)
            failed.environment.setdefault("strategy", strategy)
            failed.environment["seed_count"] = len(self._seed_candidates(spec))
            failed.environment["sweep_count"] = len(self._sweep_candidates(spec))
            failed.sweep_results = sweep_results
            return strategy, code_path, failed

        artifacts = selected_artifacts_by_sweep[selected_sweep.label]
        per_seed_results = selected_seed_results_by_sweep[selected_sweep.label]
        mean_results, aggregate_results = self._aggregate_system_results(artifacts)
        primary_metric = artifacts[0].primary_metric
        best_system = max(
            mean_results,
            key=lambda item: item.metrics.get(primary_metric, float("-inf")),
        ).system if mean_results else None
        objective_system = selected_sweep.objective_system
        acceptance_checks = self._acceptance_checks(
            spec,
            ResultArtifact(
                status="done",
                summary="",
                primary_metric=primary_metric,
                best_system=best_system,
                objective_system=objective_system,
                objective_score=selected_sweep.objective_score_mean,
                aggregate_system_results=aggregate_results,
                per_seed_results=per_seed_results,
                environment={"selected_sweep": selected_sweep.label},
            ),
        )
        logs = "\n\n".join(
            (
                f"=== sweep={selected_sweep.label} seed={seed_result.seed} ===\n"
                f"{artifact.logs or ''}"
            ).strip()
            for seed_result, artifact in zip(per_seed_results, artifacts, strict=False)
        )
        base_environment = dict(artifacts[0].environment)
        base_environment.update(
            {
                "selected_sweep": selected_sweep.label,
                "selected_sweep_params": selected_sweep.params,
                "seed_count": len(per_seed_results),
                "sweep_count": len(sweep_results),
                "sweeps_evaluated": [item.label for item in sweep_results],
                "aggregate_runtime_seconds": _round_metric(
                    sum(
                        float(item.environment.get("runtime_seconds") or 0.0)
                        for item in artifacts
                    )
                ),
            }
        )
        tables = self._aggregate_tables(
            primary_metric=primary_metric,
            aggregate_results=aggregate_results,
            sweep_results=sweep_results,
            per_seed_results=per_seed_results,
        )
        key_findings = list(artifacts[0].key_findings)
        if selected_sweep.objective_score_mean is not None:
            key_findings.append(
                f"Selected sweep `{selected_sweep.label}` reached mean {primary_metric}="
                f"{selected_sweep.objective_score_mean:.4f} with std="
                f"{selected_sweep.objective_score_std or 0.0:.4f} across {len(per_seed_results)} seeds."
            )
        key_findings.append(
            f"Selected sweep config: {selected_sweep.label} with params {json.dumps(selected_sweep.params, ensure_ascii=False, sort_keys=True)}."
        )
        failed_sweep_count = sum(1 for item in sweep_results if item.status != "done")
        if failed_sweep_count:
            key_findings.append(f"{failed_sweep_count} sweep configurations failed before full aggregation.")

        artifact = ResultArtifact(
            status="done",
            summary=(
                f"{plan.title} executed strategy {strategy} across {len(per_seed_results)} seeds and "
                f"{len(sweep_results)} sweep configs. Selected sweep: {selected_sweep.label}. "
                f"Best system: {best_system or 'unknown'} with mean {primary_metric}="
                f"{selected_sweep.objective_score_mean or 0.0:.4f}."
            ),
            key_findings=key_findings,
            primary_metric=primary_metric,
            best_system=best_system,
            objective_system=objective_system,
            objective_score=selected_sweep.objective_score_mean,
            system_results=mean_results,
            aggregate_system_results=aggregate_results,
            per_seed_results=per_seed_results,
            sweep_results=sweep_results,
            acceptance_checks=acceptance_checks,
            tables=tables,
            logs=logs,
            environment=base_environment,
            outputs={
                "selected_sweep": selected_sweep.label,
                "selected_sweep_params": selected_sweep.params,
                "seed_results": [item.model_dump(mode="json") for item in per_seed_results],
                "sweep_results": [item.model_dump(mode="json") for item in sweep_results],
            },
        )
        artifact.environment.setdefault("generated_code_path", code_path)
        artifact.environment.setdefault("strategy", strategy)
        return strategy, code_path, artifact
