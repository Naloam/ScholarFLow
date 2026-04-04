from __future__ import annotations

import itertools
import json
import math
import random
import re
from typing import Any

from agents.sandbox_agent import SandboxAgent
from schemas.autoresearch import (
    AcceptanceCheck,
    AggregateSystemMetricResult,
    AnomalousTrialRecord,
    ConfidenceIntervalSummary,
    ExecutionBackendSpec,
    ExperimentAttempt,
    ExperimentSpec,
    FailureCategory,
    FailureRecord,
    NegativeResultRecord,
    ResearchPlan,
    ResultArtifact,
    ResultTable,
    SeedArtifactResult,
    SignificanceTestResult,
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


def _sample_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    center = _mean(values)
    variance = sum((value - center) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


_T_CRITICAL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.16,
    14: 2.145,
    15: 2.131,
    16: 2.12,
    17: 2.11,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.08,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.06,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def _confidence_interval(values: list[float]) -> ConfidenceIntervalSummary | None:
    if not values:
        return None
    center = _mean(values)
    if len(values) == 1:
        return ConfidenceIntervalSummary(
            lower=_round_metric(center),
            upper=_round_metric(center),
        )
    degrees_of_freedom = len(values) - 1
    critical_value = _T_CRITICAL_95.get(degrees_of_freedom, 1.96)
    margin = critical_value * _sample_std(values) / math.sqrt(len(values))
    return ConfidenceIntervalSummary(
        lower=_round_metric(center - margin),
        upper=_round_metric(center + margin),
    )


def _metric_label(name: str) -> str:
    labels = {
        "accuracy": "Accuracy",
        "macro_f1": "Macro F1",
        "mrr": "MRR",
        "recall_at_1": "Recall@1",
    }
    return labels.get(name, name.replace("_", " ").title())


def _format_confidence_interval(interval: ConfidenceIntervalSummary | None) -> str:
    if interval is None:
        return "n/a"
    level_percent = int(round(interval.level * 100))
    return f"{level_percent}% CI [{interval.lower:.4f}, {interval.upper:.4f}]"


def _compare_values(left: float, right: float, comparison: str | None) -> bool:
    if comparison == "gte":
        return left >= right
    if comparison == "lt":
        return left < right
    if comparison == "lte":
        return left <= right
    if comparison == "eq":
        return left == right
    if comparison == "ne":
        return left != right
    return left > right


def _resolve_metric_name(metric: str | None, primary_metric: str) -> str:
    if not metric or metric == "primary_metric":
        return primary_metric
    return metric


def _detail_excerpt(text: str, *, limit: int = 220) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."


def _paired_sign_flip_test(
    values_a: list[float],
    values_b: list[float],
) -> tuple[float, str, float, int, str]:
    pairs = list(zip(values_a, values_b, strict=False))
    if not pairs:
        return 1.0, "two_sided", 0.0, 0, "paired_sign_flip_exact"
    differences = [left - right for left, right in pairs]
    effect_size = _round_metric(_mean(differences))
    non_zero = [value for value in differences if abs(value) > 1e-12]
    if not non_zero:
        return 1.0, "two_sided", effect_size, len(differences), "paired_sign_flip_exact"

    alternative = "greater" if effect_size >= 0 else "less"
    observed = _mean(non_zero)
    max_exact = 12
    if len(non_zero) <= max_exact:
        flipped_means = [
            _mean([sign * value for sign, value in zip(signs, non_zero, strict=False)])
            for signs in itertools.product((-1.0, 1.0), repeat=len(non_zero))
        ]
        if alternative == "greater":
            extreme = sum(1 for value in flipped_means if value >= observed - 1e-12)
        else:
            extreme = sum(1 for value in flipped_means if value <= observed + 1e-12)
        p_value = extreme / len(flipped_means)
        method = "paired_sign_flip_exact"
    else:
        rng = random.Random(0)
        draws = 4096
        extreme = 0
        for _ in range(draws):
            sampled = _mean([rng.choice((-1.0, 1.0)) * value for value in non_zero])
            if alternative == "greater" and sampled >= observed - 1e-12:
                extreme += 1
            elif alternative == "less" and sampled <= observed + 1e-12:
                extreme += 1
        p_value = extreme / draws
        method = "paired_sign_flip_monte_carlo"
    return _round_metric(p_value), alternative, effect_size, len(differences), method


def _paired_differences(values_a: list[float], values_b: list[float]) -> list[float]:
    return [left - right for left, right in zip(values_a, values_b, strict=False)]


def _power_style_analysis(differences: list[float]) -> dict[str, object]:
    sample_count = len(differences)
    absolute_effect = abs(_mean(differences)) if differences else 0.0
    if sample_count < 2:
        return {
            "minimum_detectable_effect": None,
            "recommended_sample_count": 4,
            "adequately_powered": False,
            "power_detail": (
                f"Only {sample_count} paired seed(s) were available, so power-style analysis is "
                "advisory only and more paired seeds are recommended."
            ),
        }

    difference_std = _sample_std(differences)
    if difference_std <= 1e-12:
        recommended = 2 if absolute_effect > 0 else 4
        adequately_powered = sample_count >= recommended and absolute_effect > 0
        return {
            "minimum_detectable_effect": 0.0,
            "recommended_sample_count": recommended,
            "adequately_powered": adequately_powered,
            "power_detail": (
                f"Observed paired differences were nearly deterministic across {sample_count} seeds; "
                f"an effect of {absolute_effect:.4f} is already stable under the current design."
                if adequately_powered
                else (
                    f"Observed paired differences were nearly deterministic, but the mean paired delta "
                    f"({absolute_effect:.4f}) is too small to treat the current design as adequately powered."
                )
            ),
        }

    z_alpha_plus_beta = 2.8
    minimum_detectable_effect = z_alpha_plus_beta * difference_std / math.sqrt(sample_count)
    if absolute_effect <= 1e-12:
        recommended_sample_count = 512
    else:
        recommended_sample_count = int(
            max(
                2,
                min(
                    512,
                    math.ceil((z_alpha_plus_beta * difference_std / absolute_effect) ** 2),
                ),
            )
        )
    adequately_powered = sample_count >= recommended_sample_count
    return {
        "minimum_detectable_effect": _round_metric(minimum_detectable_effect),
        "recommended_sample_count": recommended_sample_count,
        "adequately_powered": adequately_powered,
        "power_detail": (
            f"With {sample_count} paired seeds and paired-difference std={difference_std:.4f}, "
            f"the design can reliably detect deltas around {minimum_detectable_effect:.4f}; "
            f"the observed mean delta was {absolute_effect:.4f}."
            + (
                " Current seed coverage is likely adequate."
                if adequately_powered
                else f" Roughly {recommended_sample_count} paired seeds would be safer."
            )
        ),
    }


def _holm_bonferroni_adjustment(results: list[SignificanceTestResult]) -> list[SignificanceTestResult]:
    if not results:
        return results
    grouped: dict[str, list[tuple[int, SignificanceTestResult]]] = {}
    for index, item in enumerate(results):
        family = f"{item.scope}:{item.metric}"
        grouped.setdefault(family, []).append((index, item))

    updates: dict[int, dict[str, object]] = {}
    for family, family_results in grouped.items():
        indexed = sorted(family_results, key=lambda item: item[1].p_value)
        running_max = 0.0
        total = len(indexed)
        for position, (original_index, item) in enumerate(indexed, start=1):
            candidate = min(1.0, item.p_value * (total - position + 1))
            running_max = max(running_max, candidate)
            adjusted_alpha = 0.05 / (total - position + 1)
            updates[original_index] = {
                "comparison_family": family,
                "family_size": total,
                "adjusted_p_value": _round_metric(running_max),
                "adjusted_alpha": round(adjusted_alpha, 6),
                "correction": "holm_bonferroni",
                "significant": running_max < 0.05,
            }
    return [
        item.model_copy(update=updates[index])
        for index, item in enumerate(results)
    ]


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

    @staticmethod
    def _normalize_system_results(raw: Any) -> list[dict[str, Any]]:
        """Convert various LLM output formats into the expected list-of-dicts schema.

        The schema expects: [{"system": str, "metrics": {str: float}}]
        LLMs may return: {"system_name": {"metric": value}} or other variants.
        Nested dict values (e.g. per_class_f1) are flattened to key_subkey format.
        """
        def _flatten_metrics(metrics: dict[str, Any]) -> dict[str, float]:
            flat: dict[str, float] = {}
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    flat[key] = float(value)
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, (int, float)):
                            flat[f"{key}_{sub_key}"] = float(sub_value)
                elif value is not None:
                    try:
                        flat[key] = float(value)
                    except (TypeError, ValueError):
                        pass
            return flat

        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and "metrics" in item and isinstance(item["metrics"], dict):
                    item["metrics"] = _flatten_metrics(item["metrics"])
            return raw
        if isinstance(raw, dict):
            results: list[dict[str, Any]] = []
            for system_name, metrics in raw.items():
                if isinstance(metrics, dict):
                    results.append({"system": system_name, "metrics": _flatten_metrics(metrics)})
                elif isinstance(metrics, (int, float)):
                    results.append({"system": system_name, "metrics": {"score": float(metrics)}})
            return results
        return []

    @staticmethod
    def _normalize_tables(raw: Any) -> list[dict[str, Any]]:
        """Normalize raw tables into ResultTable-compatible dicts.

        Ensures each table has a 'title', 'columns', and 'rows' with all string values.
        """
        if not isinstance(raw, list):
            return []
        normalized: list[dict[str, Any]] = []
        for index, table in enumerate(raw):
            if not isinstance(table, dict):
                continue
            title = table.get("title") or table.get("name") or f"Table {index + 1}"
            headers = table.get("headers") or table.get("columns") or []
            raw_rows = table.get("rows") or table.get("data") or []
            columns = [str(h) for h in headers]
            rows: list[list[str]] = []
            for row in raw_rows:
                if isinstance(row, (list, tuple)):
                    rows.append([str(cell) for cell in row])
                elif isinstance(row, dict):
                    rows.append([str(row.get(h, "")) for h in headers])
            if columns and rows:
                normalized.append({"title": str(title), "columns": columns, "rows": rows})
        return normalized

    @staticmethod
    def _normalize_list_field(raw: Any) -> list[Any]:
        """Normalize an LLM output that should be a list but may be a dict or other type."""
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            converted: list[Any] = []
            for value in raw.values():
                if isinstance(value, list):
                    converted.extend(value)
                elif isinstance(value, dict):
                    converted.append(value)
                elif value is not None:
                    converted.append(value)
            return converted
        if raw is None:
            return []
        return [raw]

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
            system_results=self._normalize_system_results(payload.get("system_results")),
            aggregate_system_results=self._normalize_list_field(payload.get("aggregate_system_results")),
            per_seed_results=self._normalize_list_field(payload.get("per_seed_results")),
            sweep_results=self._normalize_list_field(payload.get("sweep_results")),
            significance_tests=self._normalize_list_field(payload.get("significance_tests")),
            negative_results=self._normalize_list_field(payload.get("negative_results")),
            failed_trials=self._normalize_list_field(payload.get("failed_trials")),
            anomalous_trials=self._normalize_list_field(payload.get("anomalous_trials")),
            acceptance_checks=self._normalize_list_field(payload.get("acceptance_checks")),
            tables=self._normalize_tables(payload.get("tables")),
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
        if artifact.status == "done":
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
            confidence_intervals = {
                metric_name: interval
                for metric_name, values in metric_map.items()
                if values and (interval := _confidence_interval(values)) is not None
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
                    confidence_intervals=confidence_intervals,
                    min_metrics=min_metrics,
                    max_metrics=max_metrics,
                    sample_count=sample_count,
                )
            )
            mean_results.append(SystemMetricResult(system=system, metrics=mean_metrics))
        return mean_results, aggregate_results

    def _failure_category(self, artifact: ResultArtifact) -> FailureCategory:
        if artifact.environment.get("runtime_contract_violations"):
            return "runtime_contract_failure"
        text = " ".join(
            str(item)
            for item in [
                artifact.summary,
                artifact.logs or "",
                json.dumps(artifact.outputs, ensure_ascii=False, sort_keys=True),
            ]
        ).lower()
        if any(
            marker in text
            for marker in [
                "traceback",
                "syntaxerror",
                "nameerror",
                "typeerror",
                "valueerror",
                "runtimeerror",
                "assertionerror",
                "importerror",
                "modulenotfounderror",
            ]
        ):
            return "code_failure"
        if any(
            marker in text
            for marker in [
                "dataset",
                "split",
                "column",
                "field",
                "filenotfounderror",
                "no such file",
                "jsondecodeerror",
                "csv",
            ]
        ):
            return "data_failure"
        if any(
            marker in text
            for marker in [
                "timeout",
                "timed out",
                "docker",
                "permission denied",
                "sandbox",
                "connection",
                "network",
                "image",
            ]
        ):
            return "environment_failure"
        if any(
            marker in text
            for marker in [
                "metric",
                "objective_score",
                "primary metric",
                "system_results",
                "structured result artifact",
            ]
        ):
            return "metric_failure"
        return "unknown_failure"

    def _config_signature(self, *, seed: int | None, sweep: SweepConfig) -> str:
        seed_fragment = f"seed={seed}" if seed is not None else "seed=n/a"
        return (
            f"{sweep.label}|{seed_fragment}|"
            f"{json.dumps(sweep.params, ensure_ascii=False, sort_keys=True)}"
        )

    def _failure_diagnosis(
        self,
        *,
        artifact: ResultArtifact,
        category: FailureCategory,
        sweep: SweepConfig,
        seed: int | None,
    ) -> tuple[str, str]:
        config_label = (
            f"sweep `{sweep.label}` seed {seed}" if seed is not None else f"sweep `{sweep.label}`"
        )
        if category == "runtime_contract_failure":
            return (
                f"{config_label} returned an artifact without the required seed/sweep runtime metadata.",
                "Regenerate the experiment so it records the active seed and sweep parameters in the result artifact.",
            )
        if category == "code_failure":
            return (
                f"{config_label} failed inside generated experiment code before producing a complete structured artifact.",
                "Inspect the generated code and traceback, then prefer a safer baseline or a repair-focused retry.",
            )
        if category == "environment_failure":
            return (
                f"{config_label} hit an execution-environment issue rather than a model-quality issue.",
                "Check sandbox, dependency, timeout, or backend configuration before retrying the same candidate.",
            )
        if category == "data_failure":
            return (
                f"{config_label} failed while reading or validating benchmark data.",
                "Re-check dataset fields, schema assumptions, and benchmark payload materialization.",
            )
        if category == "metric_failure":
            return (
                f"{config_label} ran but did not preserve enough metric structure for aggregation.",
                "Patch the result emitter so objective score, primary metric, and system-level metrics are always recorded.",
            )
        return (
            f"{config_label} failed for an uncategorized reason.",
            "Inspect the preserved logs and tighten failure categorization before rerunning at scale.",
        )

    def _failure_record(
        self,
        *,
        artifact: ResultArtifact,
        seed: int | None,
        sweep: SweepConfig,
    ) -> FailureRecord:
        category = self._failure_category(artifact)
        diagnosis, likely_fix = self._failure_diagnosis(
            artifact=artifact,
            category=category,
            sweep=sweep,
            seed=seed,
        )
        detail_parts = [artifact.summary]
        if artifact.logs:
            detail_parts.append(_detail_excerpt(artifact.logs))
        violations = artifact.environment.get("runtime_contract_violations")
        if isinstance(violations, list) and violations:
            detail_parts.append(f"runtime_contract={', '.join(str(item) for item in violations)}")
        detail_parts.append(diagnosis)
        returncode = artifact.outputs.get("returncode") if isinstance(artifact.outputs, dict) else None
        return FailureRecord(
            scope="seed" if seed is not None else "sweep",
            sweep_label=sweep.label,
            seed=seed,
            category=category,
            config_signature=self._config_signature(seed=seed, sweep=sweep),
            config_params=dict(sweep.params),
            runtime_context={
                "strategy": artifact.environment.get("strategy"),
                "generated_code_path": artifact.environment.get("generated_code_path"),
                "executor_mode": artifact.environment.get("executor_mode"),
            },
            summary=artifact.summary,
            detail=" | ".join(part for part in detail_parts if part),
            diagnosis=diagnosis,
            likely_fix=likely_fix,
            returncode=int(returncode) if isinstance(returncode, int) else None,
        )

    def _significance_tests(
        self,
        *,
        primary_metric: str,
        aggregate_results: list[AggregateSystemMetricResult],
        selected_sweep: SweepEvaluationResult,
        per_seed_results: list[SeedArtifactResult],
        seed_results_by_sweep: dict[str, list[SeedArtifactResult]],
    ) -> list[SignificanceTestResult]:
        selected_system = selected_sweep.objective_system
        if not selected_system:
            return []

        by_system_and_seed: dict[str, dict[int, float]] = {}
        for seed_result in per_seed_results:
            for system_result in seed_result.system_results:
                value = system_result.metrics.get(primary_metric)
                if value is None:
                    continue
                by_system_and_seed.setdefault(system_result.system, {})[seed_result.seed] = float(value)

        tests: list[SignificanceTestResult] = []
        for item in aggregate_results:
            if item.system == selected_system:
                continue
            selected_scores = by_system_and_seed.get(selected_system, {})
            comparator_scores = by_system_and_seed.get(item.system, {})
            common_seeds = sorted(set(selected_scores) & set(comparator_scores))
            if not common_seeds:
                continue
            values_a = [selected_scores[seed] for seed in common_seeds]
            values_b = [comparator_scores[seed] for seed in common_seeds]
            differences = _paired_differences(values_a, values_b)
            p_value, alternative, effect_size, sample_count, method = _paired_sign_flip_test(values_a, values_b)
            power_analysis = _power_style_analysis(differences)
            tests.append(
                SignificanceTestResult(
                    scope="system",
                    metric=primary_metric,
                    candidate=selected_system,
                    comparator=item.system,
                    alternative=alternative,
                    method=method,
                    p_value=p_value,
                    effect_size=effect_size,
                    minimum_detectable_effect=power_analysis["minimum_detectable_effect"],  # type: ignore[arg-type]
                    recommended_sample_count=power_analysis["recommended_sample_count"],  # type: ignore[arg-type]
                    adequately_powered=power_analysis["adequately_powered"],  # type: ignore[arg-type]
                    power_detail=power_analysis["power_detail"],  # type: ignore[arg-type]
                    sample_count=sample_count,
                    detail=(
                        f"`{selected_system}` vs `{item.system}` on `{primary_metric}` over {sample_count} paired seeds "
                        f"with mean delta {effect_size:.4f}."
                    ),
                )
            )

        selected_scores = {
            item.seed: float(item.objective_score)
            for item in per_seed_results
            if item.objective_score is not None
        }
        for sweep_label, sweep_seed_results in seed_results_by_sweep.items():
            if sweep_label == selected_sweep.label:
                continue
            comparator_scores = {
                item.seed: float(item.objective_score)
                for item in sweep_seed_results
                if item.objective_score is not None
            }
            common_seeds = sorted(set(selected_scores) & set(comparator_scores))
            if not common_seeds:
                continue
            values_a = [selected_scores[seed] for seed in common_seeds]
            values_b = [comparator_scores[seed] for seed in common_seeds]
            differences = _paired_differences(values_a, values_b)
            p_value, alternative, effect_size, sample_count, method = _paired_sign_flip_test(values_a, values_b)
            power_analysis = _power_style_analysis(differences)
            tests.append(
                SignificanceTestResult(
                    scope="sweep",
                    metric=primary_metric,
                    candidate=selected_sweep.label,
                    comparator=sweep_label,
                    alternative=alternative,
                    method=method,
                    p_value=p_value,
                    effect_size=effect_size,
                    minimum_detectable_effect=power_analysis["minimum_detectable_effect"],  # type: ignore[arg-type]
                    recommended_sample_count=power_analysis["recommended_sample_count"],  # type: ignore[arg-type]
                    adequately_powered=power_analysis["adequately_powered"],  # type: ignore[arg-type]
                    power_detail=power_analysis["power_detail"],  # type: ignore[arg-type]
                    sample_count=sample_count,
                    detail=(
                        f"Sweep `{selected_sweep.label}` vs `{sweep_label}` on `{primary_metric}` over "
                        f"{sample_count} paired seeds with mean delta {effect_size:.4f}."
                    ),
                )
            )
        return _holm_bonferroni_adjustment(tests)

    def _negative_results(
        self,
        *,
        primary_metric: str,
        aggregate_results: list[AggregateSystemMetricResult],
        selected_sweep: SweepEvaluationResult,
        significance_tests: list[SignificanceTestResult],
        sweep_results: list[SweepEvaluationResult],
    ) -> list[NegativeResultRecord]:
        negative_results: list[NegativeResultRecord] = []
        reference_system = selected_sweep.objective_system
        reference_score = selected_sweep.objective_score_mean
        if reference_system and reference_score is not None:
            for item in aggregate_results:
                observed_score = item.mean_metrics.get(primary_metric)
                if item.system == reference_system or observed_score is None:
                    continue
                delta = _round_metric(observed_score - reference_score)
                if delta <= 0:
                    negative_results.append(
                        NegativeResultRecord(
                            scope="system",
                            subject=item.system,
                            reference=reference_system,
                            metric=primary_metric,
                            observed_score=observed_score,
                            reference_score=reference_score,
                            delta=delta,
                            detail=(
                                f"`{item.system}` trailed `{reference_system}` by {abs(delta):.4f} "
                                f"on mean `{primary_metric}`."
                            ),
                        )
                    )

        for item in sweep_results:
            if item.label == selected_sweep.label or item.objective_score_mean is None:
                continue
            if reference_score is None:
                continue
            delta = _round_metric(item.objective_score_mean - reference_score)
            if delta <= 0:
                negative_results.append(
                    NegativeResultRecord(
                        scope="sweep",
                        subject=item.label,
                        reference=selected_sweep.label,
                        metric=primary_metric,
                        observed_score=item.objective_score_mean,
                        reference_score=reference_score,
                        delta=delta,
                        detail=(
                            f"Sweep `{item.label}` underperformed the selected sweep `{selected_sweep.label}` "
                            f"by {abs(delta):.4f} on `{primary_metric}`."
                        ),
                    )
                )

        for item in significance_tests:
            adjusted = item.adjusted_p_value if item.adjusted_p_value is not None else item.p_value
            if item.scope != "system" or adjusted < 0.05:
                continue
            negative_results.append(
                NegativeResultRecord(
                    scope="comparison",
                    subject=item.candidate,
                    reference=item.comparator,
                    metric=item.metric,
                    observed_score=None,
                    reference_score=None,
                    delta=item.effect_size,
                    detail=(
                        f"No statistically reliable separation was detected between `{item.candidate}` and "
                        f"`{item.comparator}` on `{item.metric}` (adjusted p={adjusted:.4f})."
                    ),
                )
            )
        return negative_results

    def _anomalous_trials(
        self,
        *,
        per_seed_results: list[SeedArtifactResult],
        primary_metric: str,
    ) -> list[AnomalousTrialRecord]:
        scores = [
            float(item.objective_score)
            for item in per_seed_results
            if item.objective_score is not None
        ]
        if len(scores) < 3:
            return []
        center = _mean(scores)
        deviation = _sample_std(scores)
        if deviation <= 0:
            return []
        records: list[AnomalousTrialRecord] = []
        for item in per_seed_results:
            if item.objective_score is None:
                continue
            z_score = (float(item.objective_score) - center) / deviation
            if abs(z_score) < 1.4:
                continue
            records.append(
                AnomalousTrialRecord(
                    sweep_label=item.sweep_label,
                    seed=item.seed,
                    metric=primary_metric,
                    observed_score=float(item.objective_score),
                    mean_score=_round_metric(center),
                    z_score=_round_metric(z_score),
                    detail=(
                        f"Seed {item.seed} in sweep `{item.sweep_label}` deviated from the selected-sweep mean "
                        f"by {z_score:.2f} standard deviations."
                    ),
                )
            )
        return records

    def _aggregate_tables(
        self,
        *,
        primary_metric: str,
        aggregate_results: list[AggregateSystemMetricResult],
        sweep_results: list[SweepEvaluationResult],
        per_seed_results: list[SeedArtifactResult],
        significance_tests: list[SignificanceTestResult],
        negative_results: list[NegativeResultRecord],
        failed_trials: list[FailureRecord],
        anomalous_trials: list[AnomalousTrialRecord],
    ) -> list[ResultTable]:
        tables: list[ResultTable] = []

        if aggregate_results:
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
            tables.extend(
                [
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
                    ResultTable(
                        title="Confidence Intervals",
                        columns=["System", *[f"{_metric_label(metric)} 95% CI" for metric in metric_order]],
                        rows=[
                            [
                                item.system,
                                *[
                                    _format_confidence_interval(item.confidence_intervals.get(metric))
                                    for metric in metric_order
                                ],
                            ]
                            for item in ranked
                        ],
                    ),
                ]
            )

        if significance_tests:
            tables.append(
                ResultTable(
                    title="Significance Tests",
                    columns=[
                        "Scope",
                        "Family",
                        "Candidate",
                        "Comparator",
                        "Metric",
                        "Effect",
                        "Adj P",
                        "Adj Alpha",
                        "Significant",
                        "Adequate Power",
                    ],
                    rows=[
                        [
                            item.scope,
                            item.comparison_family or "n/a",
                            item.candidate,
                            item.comparator,
                            _metric_label(item.metric),
                            f"{item.effect_size:.4f}",
                            f"{(item.adjusted_p_value if item.adjusted_p_value is not None else item.p_value):.4f}",
                            f"{item.adjusted_alpha:.4f}" if item.adjusted_alpha is not None else "n/a",
                            "yes" if item.significant else "no",
                            "yes" if item.adequately_powered else "no",
                        ]
                        for item in significance_tests
                    ],
                )
            )
            tables.append(
                ResultTable(
                    title="Comparison Power",
                    columns=[
                        "Scope",
                        "Candidate",
                        "Comparator",
                        "Paired Seeds",
                        "Min Detectable Effect",
                        "Recommended Seeds",
                        "Adequate",
                    ],
                    rows=[
                        [
                            item.scope,
                            item.candidate,
                            item.comparator,
                            str(item.sample_count),
                            (
                                f"{item.minimum_detectable_effect:.4f}"
                                if item.minimum_detectable_effect is not None
                                else "n/a"
                            ),
                            (
                                str(item.recommended_sample_count)
                                if item.recommended_sample_count is not None
                                else "n/a"
                            ),
                            "yes" if item.adequately_powered else "no",
                        ]
                        for item in significance_tests
                    ],
                )
            )

        if negative_results:
            tables.append(
                ResultTable(
                    title="Negative Results",
                    columns=["Scope", "Subject", "Reference", "Metric", "Delta", "Detail"],
                    rows=[
                        [
                            item.scope,
                            item.subject,
                            item.reference,
                            _metric_label(item.metric),
                            f"{item.delta:.4f}" if item.delta is not None else "n/a",
                            item.detail,
                        ]
                        for item in negative_results
                    ],
                )
            )

        if sweep_results:
            tables.append(
                ResultTable(
                    title="Sweep Summary",
                    columns=[
                        "Sweep",
                        "Status",
                        "Objective System",
                        f"{_metric_label(primary_metric)} Mean",
                        f"{_metric_label(primary_metric)} Std",
                        f"{_metric_label(primary_metric)} 95% CI",
                        "Best System",
                        "Successful Seeds",
                        "Failed Seeds",
                    ],
                    rows=[
                        [
                            item.label,
                            item.status,
                            item.objective_system or "unknown",
                            f"{item.objective_score_mean:.4f}" if item.objective_score_mean is not None else "n/a",
                            f"{item.objective_score_std:.4f}" if item.objective_score_std is not None else "n/a",
                            _format_confidence_interval(item.objective_score_confidence_interval),
                            item.best_system or "unknown",
                            str(item.successful_seed_count or item.seed_count),
                            str(len(item.failed_seeds)),
                        ]
                        for item in sweep_results
                    ],
                )
            )

        if per_seed_results:
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

        if failed_trials:
            tables.append(
                ResultTable(
                    title="Failed Configs",
                    columns=[
                        "Scope",
                        "Sweep",
                        "Seed",
                        "Category",
                        "Config",
                        "Diagnosis",
                        "Likely Fix",
                    ],
                    rows=[
                        [
                            item.scope,
                            item.sweep_label,
                            str(item.seed) if item.seed is not None else "n/a",
                            item.category,
                            item.config_signature or "n/a",
                            item.diagnosis or item.summary,
                            item.likely_fix or "n/a",
                        ]
                        for item in failed_trials
                    ],
                )
            )

        if anomalous_trials:
            tables.append(
                ResultTable(
                    title="Anomalous Trials",
                    columns=["Sweep", "Seed", "Metric", "Observed", "Mean", "Z"],
                    rows=[
                        [
                            item.sweep_label,
                            str(item.seed),
                            _metric_label(item.metric),
                            f"{item.observed_score:.4f}",
                            f"{item.mean_score:.4f}",
                            f"{item.z_score:.4f}" if item.z_score is not None else "n/a",
                        ]
                        for item in anomalous_trials
                    ],
                )
            )
        return tables

    def _acceptance_checks(
        self,
        spec: ExperimentSpec,
        artifact: ResultArtifact,
    ) -> list[AcceptanceCheck]:
        aggregate_by_system = {
            item.system: item for item in artifact.aggregate_system_results
        }
        selected_sweep = str(artifact.environment.get("selected_sweep") or "unknown")
        checks: list[AcceptanceCheck] = []
        for rule in spec.acceptance_criteria:
            metric_name = _resolve_metric_name(rule.metric, artifact.primary_metric)
            target_system = (
                artifact.best_system
                if rule.target == "best_system"
                else artifact.objective_system
            )
            if rule.kind == "seed_coverage":
                passed = len(artifact.per_seed_results) == max(1, len(spec.seeds))
                detail = (
                    f"Selected sweep `{selected_sweep}` completed {len(artifact.per_seed_results)}/"
                    f"{max(1, len(spec.seeds))} requested seeds."
                )
            elif rule.kind == "aggregate_metric_reporting":
                aggregate_item = aggregate_by_system.get(target_system or "")
                missing: list[str] = []
                if aggregate_item is None:
                    missing = list(rule.required_statistics or ["mean"])
                else:
                    for stat_name in rule.required_statistics or ["mean"]:
                        if stat_name == "mean" and metric_name not in aggregate_item.mean_metrics:
                            missing.append(stat_name)
                        elif stat_name == "std" and metric_name not in aggregate_item.std_metrics:
                            missing.append(stat_name)
                        elif (
                            stat_name == "confidence_interval"
                            and metric_name not in aggregate_item.confidence_intervals
                        ):
                            missing.append(stat_name)
                passed = not missing
                recorded_stats = []
                if aggregate_item is not None:
                    if metric_name in aggregate_item.mean_metrics:
                        recorded_stats.append("mean")
                    if metric_name in aggregate_item.std_metrics:
                        recorded_stats.append("std")
                    if metric_name in aggregate_item.confidence_intervals:
                        recorded_stats.append("confidence_interval")
                detail = (
                    f"Primary metric `{metric_name}` for `{target_system or 'unknown'}` recorded "
                    f"{', '.join(recorded_stats) or 'no aggregate statistics'}."
                    + (
                        f" Missing: {', '.join(missing)}."
                        if missing
                        else ""
                    )
                )
            elif rule.kind == "objective_metric_comparison":
                baseline_name = rule.baseline_system or "majority"
                target_score = None
                target_aggregate = aggregate_by_system.get(target_system or "")
                if target_aggregate is not None:
                    target_score = target_aggregate.mean_metrics.get(metric_name)
                elif target_system == artifact.objective_system:
                    target_score = artifact.objective_score
                baseline_score = None
                baseline_aggregate = aggregate_by_system.get(baseline_name)
                if baseline_aggregate is not None:
                    baseline_score = baseline_aggregate.mean_metrics.get(metric_name)
                passed = (
                    target_score is not None
                    and (baseline_score is None or _compare_values(target_score, baseline_score, rule.comparison))
                )
                detail = (
                    f"`{target_system or 'unknown'}` mean {metric_name}="
                    f"{target_score:.4f} " if target_score is not None else f"`{target_system or 'unknown'}` {metric_name}=n/a "
                    f"vs `{baseline_name}`="
                    f"{baseline_score:.4f}" if baseline_score is not None else f"vs `{baseline_name}`=n/a"
                )
            elif rule.kind == "significance_test_reporting":
                comparison_scope = rule.comparison_scope or "system"
                baseline_name = rule.baseline_system or "majority"
                matched = next(
                    (
                        item
                        for item in artifact.significance_tests
                        if item.scope == comparison_scope
                        and item.metric == metric_name
                        and item.candidate == (target_system or "")
                        and item.comparator == baseline_name
                    ),
                    None,
                )
                passed = matched is not None
                detail = (
                    matched.detail
                    if matched is not None
                    else (
                        f"No `{comparison_scope}` significance record for `{target_system or 'unknown'}` vs "
                        f"`{baseline_name}` on `{metric_name}`."
                    )
                )
            else:
                passed = bool(artifact.aggregate_system_results)
                detail = "Aggregate experiment outputs were recorded."
            checks.append(
                AcceptanceCheck(
                    criterion=rule.description,
                    passed=passed,
                    detail=detail,
                    rule_id=rule.id,
                    rule_kind=rule.kind,
                )
            )
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

    def prepare_attempt(
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
    ) -> tuple[str, str, str]:
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
        return strategy, code_path, code

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
        strategy, code_path, code = self.prepare_attempt(
            project_id=project_id,
            run_id=run_id,
            plan=plan,
            spec=spec,
            benchmark_payload=benchmark_payload,
            round_index=round_index,
            goal=goal,
            prior_attempts=prior_attempts,
            code_override=code_override,
            strategy_override=strategy_override,
            code_filename_prefix=code_filename_prefix,
            code_subdir=code_subdir,
        )

        sweep_results: list[SweepEvaluationResult] = []
        artifacts_by_sweep: dict[str, list[ResultArtifact]] = {}
        seed_results_by_sweep: dict[str, list[SeedArtifactResult]] = {}
        selected_artifacts_by_sweep: dict[str, list[ResultArtifact]] = {}
        selected_seed_results_by_sweep: dict[str, list[SeedArtifactResult]] = {}
        failed_trials: list[FailureRecord] = []
        failed_artifacts: list[ResultArtifact] = []
        all_successful_seed_results: list[SeedArtifactResult] = []
        requested_seeds = self._seed_candidates(spec)
        sweep_candidates = self._sweep_candidates(spec)

        for sweep in sweep_candidates:
            artifacts: list[ResultArtifact] = []
            per_seed_results: list[SeedArtifactResult] = []
            failed_seeds: list[int] = []
            sweep_failure_categories: list[FailureCategory] = []
            for seed in requested_seeds:
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
                    failure_record = self._failure_record(
                        artifact=artifact,
                        seed=seed,
                        sweep=sweep,
                    )
                    failed_trials.append(failure_record)
                    sweep_failure_categories.append(failure_record.category)
                    continue
                artifacts.append(artifact)
                seed_result = SeedArtifactResult(
                    seed=seed,
                    sweep_label=sweep.label,
                    best_system=artifact.best_system,
                    objective_system=artifact.objective_system,
                    objective_score=artifact.objective_score,
                    primary_metric=artifact.primary_metric,
                    system_results=artifact.system_results,
                )
                per_seed_results.append(seed_result)
                all_successful_seed_results.append(seed_result)

            if artifacts:
                artifacts_by_sweep[sweep.label] = artifacts
                seed_results_by_sweep[sweep.label] = per_seed_results
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
                        status="done" if not failed_seeds else "partial",
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
                        objective_score_confidence_interval=_confidence_interval(objective_scores),
                        aggregate_system_results=aggregate_results,
                        failed_seeds=failed_seeds,
                        seed_count=len(artifacts),
                        successful_seed_count=len(artifacts),
                        failure_categories=sorted(set(sweep_failure_categories)),
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
                        successful_seed_count=0,
                        failure_categories=sorted(set(sweep_failure_categories)),
                    )
                )

        selected_sweep = self._select_best_sweep(sweep_results)
        if selected_sweep is None:
            dominant_failure = max(
                (
                    (category, count)
                    for category, count in {
                        item.category: sum(1 for record in failed_trials if record.category == item.category)
                        for item in failed_trials
                    }.items()
                ),
                key=lambda item: item[1],
                default=(None, 0),
            )[0]
            reference_sweep = max(
                (item for item in sweep_results if item.objective_score_mean is not None),
                key=lambda item: item.objective_score_mean if item.objective_score_mean is not None else float("-inf"),
                default=None,
            )
            reference_seed_results = (
                list(seed_results_by_sweep.get(reference_sweep.label, []))
                if reference_sweep is not None
                else list(all_successful_seed_results)
            )
            primary_metric = (
                reference_seed_results[0].primary_metric
                if reference_seed_results and reference_seed_results[0].primary_metric
                else "macro_f1"
            )
            failure_summary: dict[str, int] = {}
            for item in failed_trials:
                failure_summary[item.category] = failure_summary.get(item.category, 0) + 1
            runtime_contract_violations = sorted(
                {
                    str(violation)
                    for artifact in failed_artifacts
                    for violation in (artifact.environment.get("runtime_contract_violations") or [])
                }
            )
            failure_reason = {
                "runtime_contract_failure": "runtime contract failures prevented aggregation",
                "code_failure": "code failures prevented aggregation",
                "environment_failure": "environment failures prevented aggregation",
                "data_failure": "data failures prevented aggregation",
                "metric_failure": "metric recording failures prevented aggregation",
            }.get(dominant_failure, "failures prevented aggregation")
            tables = self._aggregate_tables(
                primary_metric=primary_metric,
                aggregate_results=reference_sweep.aggregate_system_results if reference_sweep is not None else [],
                sweep_results=sweep_results,
                per_seed_results=reference_seed_results,
                significance_tests=[],
                negative_results=[],
                failed_trials=failed_trials,
                anomalous_trials=[],
            )
            failed = ResultArtifact(
                status="failed",
                summary=(
                    f"{plan.title} did not complete a sweep that covered all {len(requested_seeds)} requested seeds. "
                    f"{failure_reason.capitalize()}. Partial results and failure analysis were preserved for inspection."
                ),
                key_findings=[
                    f"Recorded {len(failed_trials)} failed seed configurations across {len(sweep_candidates)} sweep configs.",
                    (
                        f"Best partial sweep was `{reference_sweep.label}` with mean {primary_metric}="
                        f"{reference_sweep.objective_score_mean:.4f} over {reference_sweep.successful_seed_count} successful seeds."
                    )
                    if reference_sweep is not None and reference_sweep.objective_score_mean is not None
                    else "No sweep produced enough successful seeds to select a final configuration."
                ],
                primary_metric=primary_metric,
                best_system=reference_sweep.best_system if reference_sweep is not None else None,
                objective_system=reference_sweep.objective_system if reference_sweep is not None else None,
                objective_score=reference_sweep.objective_score_mean if reference_sweep is not None else None,
                system_results=[
                    SystemMetricResult(system=item.system, metrics=item.mean_metrics)
                    for item in (reference_sweep.aggregate_system_results if reference_sweep is not None else [])
                ],
                aggregate_system_results=(
                    reference_sweep.aggregate_system_results if reference_sweep is not None else []
                ),
                per_seed_results=reference_seed_results,
                sweep_results=sweep_results,
                failed_trials=failed_trials,
                tables=tables,
                logs="\n\n".join(
                    (
                        f"=== sweep={record.sweep_label} seed={record.seed if record.seed is not None else 'n/a'} ===\n"
                        f"{artifact.logs or artifact.summary}"
                    ).strip()
                    for record, artifact in zip(failed_trials[-5:], failed_artifacts[-5:], strict=False)
                ),
                environment={
                    "generated_code_path": code_path,
                    "strategy": strategy,
                    "seed_count": len(requested_seeds),
                    "sweep_count": len(sweep_candidates),
                    "failure_summary": failure_summary,
                    "failed_trial_count": len(failed_trials),
                    "runtime_contract_violations": runtime_contract_violations,
                },
                outputs={
                    "sweep_results": [item.model_dump(mode="json") for item in sweep_results],
                    "failed_trials": [item.model_dump(mode="json") for item in failed_trials],
                },
            )
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
        significance_tests = self._significance_tests(
            primary_metric=primary_metric,
            aggregate_results=aggregate_results,
            selected_sweep=selected_sweep,
            per_seed_results=per_seed_results,
            seed_results_by_sweep=seed_results_by_sweep,
        )
        negative_results = self._negative_results(
            primary_metric=primary_metric,
            aggregate_results=aggregate_results,
            selected_sweep=selected_sweep,
            significance_tests=significance_tests,
            sweep_results=sweep_results,
        )
        power_analysis_notes = [item.power_detail for item in significance_tests if item.power_detail]
        anomalous_trials = self._anomalous_trials(
            per_seed_results=per_seed_results,
            primary_metric=primary_metric,
        )
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
                significance_tests=significance_tests,
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
        failure_summary: dict[str, int] = {}
        for item in failed_trials:
            failure_summary[item.category] = failure_summary.get(item.category, 0) + 1
        base_environment = dict(artifacts[0].environment)
        base_environment.update(
            {
                "selected_sweep": selected_sweep.label,
                "selected_sweep_params": selected_sweep.params,
                "seed_count": len(per_seed_results),
                "sweep_count": len(sweep_results),
                "sweeps_evaluated": [item.label for item in sweep_results],
                "confidence_interval_level": 0.95,
                "confidence_interval_method": "student_t_95",
                "significance_test_count": len(significance_tests),
                "underpowered_test_count": sum(
                    1 for item in significance_tests if item.adequately_powered is False
                ),
                "negative_result_count": len(negative_results),
                "anomalous_trial_count": len(anomalous_trials),
                "failed_trial_count": len(failed_trials),
                "failure_summary": failure_summary,
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
            significance_tests=significance_tests,
            negative_results=negative_results,
            failed_trials=failed_trials,
            anomalous_trials=anomalous_trials,
        )
        key_findings = list(artifacts[0].key_findings)
        if selected_sweep.objective_score_mean is not None:
            ci_text = _format_confidence_interval(selected_sweep.objective_score_confidence_interval)
            key_findings.append(
                f"Selected sweep `{selected_sweep.label}` reached mean {primary_metric}="
                f"{selected_sweep.objective_score_mean:.4f} with std="
                f"{selected_sweep.objective_score_std or 0.0:.4f} and {ci_text} "
                f"across {len(per_seed_results)} seeds."
            )
        key_findings.append(
            f"Selected sweep config: {selected_sweep.label} with params {json.dumps(selected_sweep.params, ensure_ascii=False, sort_keys=True)}."
        )
        key_findings.append(
            f"Recorded {len(significance_tests)} paired significance comparisons with Holm correction."
        )
        underpowered_count = sum(
            1 for item in significance_tests if item.adequately_powered is False
        )
        if underpowered_count:
            key_findings.append(
                f"Flagged {underpowered_count} comparison(s) as underpowered for the observed effect sizes."
            )
        if negative_results:
            key_findings.append(
                f"Preserved {len(negative_results)} negative-result records for weaker systems, sweeps, or unsupported comparisons."
            )
        if anomalous_trials:
            key_findings.append(
                f"Flagged {len(anomalous_trials)} anomalous seed-level trials for manual inspection."
            )
        failed_sweep_count = sum(1 for item in sweep_results if item.status != "done")
        if failed_sweep_count:
            key_findings.append(
                f"Preserved {len(failed_trials)} failed seed configurations across {failed_sweep_count} non-complete sweeps."
            )

        artifact = ResultArtifact(
            status="done",
            summary=(
                f"{plan.title} executed strategy {strategy} across {len(per_seed_results)} seeds and "
                f"{len(sweep_results)} sweep configs. Selected sweep: {selected_sweep.label}. "
                f"Best system: {best_system or 'unknown'} with mean {primary_metric}="
                f"{selected_sweep.objective_score_mean or 0.0:.4f}"
                f" ({_format_confidence_interval(selected_sweep.objective_score_confidence_interval)}). "
                f"Recorded {len(significance_tests)} significance comparisons and {len(failed_trials)} failed configs."
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
            significance_tests=significance_tests,
            power_analysis_notes=power_analysis_notes,
            negative_results=negative_results,
            failed_trials=failed_trials,
            anomalous_trials=anomalous_trials,
            acceptance_checks=acceptance_checks,
            tables=tables,
            logs=logs,
            environment=base_environment,
            outputs={
                "selected_sweep": selected_sweep.label,
                "selected_sweep_params": selected_sweep.params,
                "seed_results": [item.model_dump(mode="json") for item in per_seed_results],
                "sweep_results": [item.model_dump(mode="json") for item in sweep_results],
                "significance_tests": [item.model_dump(mode="json") for item in significance_tests],
                "negative_results": [item.model_dump(mode="json") for item in negative_results],
                "failed_trials": [item.model_dump(mode="json") for item in failed_trials],
                "anomalous_trials": [item.model_dump(mode="json") for item in anomalous_trials],
            },
        )
        artifact.environment.setdefault("generated_code_path", code_path)
        artifact.environment.setdefault("strategy", strategy)
        return strategy, code_path, artifact
