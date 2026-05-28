from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import UTC, datetime

from schemas.autoresearch import (
    AggregateSystemMetricResult,
    AutoResearchEvidenceLedgerEntryRead,
    AutoResearchEvidenceLedgerRead,
    AutoResearchExperimentDesignRead,
    AutoResearchExperimentFactoryEnvironmentManifestRead,
    AutoResearchExperimentFactoryExecutionRead,
    AutoResearchExperimentFactoryJobRead,
    AutoResearchExperimentFactoryMaterializedJobRead,
    AutoResearchExperimentFactoryPlanRead,
    AutoResearchExperimentFactoryRepairPlanRead,
    AutoResearchExperimentFactoryResourceEstimateRead,
    AutoResearchExperimentFactoryRetryPolicyRead,
    AutoResearchHypothesisBankEntryRead,
    AutoResearchResearchBriefRead,
    AutoResearchRunRead,
    ExecutionBackendSpec,
    ResultArtifact,
    ResultTable,
    SeedArtifactResult,
    SignificanceTestResult,
    SystemMetricResult,
)
from services.autoresearch.idea_brief import selected_hypothesis_from_brief


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_")[:80] or "job"


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = " ".join(item.split()).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _executor_mode_for_backend(backend: ExecutionBackendSpec) -> str:
    if backend.kind in {"docker", "docker_gpu"}:
        return "docker"
    if backend.kind == "command":
        return "local"
    return "local" if backend.kind == "local" else "toy"


def _backend_from_run_or_brief(
    *,
    run: AutoResearchRunRead | None,
) -> ExecutionBackendSpec:
    if run is not None and run.request is not None and run.request.execution_backend is not None:
        return run.request.execution_backend
    if run is not None and run.execution_backend is not None:
        return run.execution_backend
    return ExecutionBackendSpec(kind="auto", timeout_seconds=60, gpu_required=False)


def _resource_estimate(backend: ExecutionBackendSpec, *, job_kind: str) -> AutoResearchExperimentFactoryResourceEstimateRead:
    cpu_seconds = 20 if job_kind in {"baseline", "ablation"} else 30
    if job_kind == "sweep":
        cpu_seconds = 45
    if job_kind == "seed":
        cpu_seconds = 10
    return AutoResearchExperimentFactoryResourceEstimateRead(
        backend=backend.kind,
        cpu_seconds=cpu_seconds,
        memory_mb=1024 if job_kind == "candidate_method" else 512,
        gpu_required=backend.gpu_required,
    )


def _job(
    *,
    job_id: str,
    job_kind: str,
    command: str,
    config: dict[str, object],
    inputs: list[str],
    expected_outputs: list[str],
    dependencies: list[str],
    backend: ExecutionBackendSpec,
    failure_handling: str,
) -> AutoResearchExperimentFactoryJobRead:
    return AutoResearchExperimentFactoryJobRead(
        job_id=job_id,
        job_kind=job_kind,  # type: ignore[arg-type]
        command=command,
        config=config,
        inputs=inputs,
        expected_outputs=expected_outputs,
        dependencies=dependencies,
        retry_policy=AutoResearchExperimentFactoryRetryPolicyRead(),
        resource_estimate=_resource_estimate(backend, job_kind=job_kind),
        failure_handling=failure_handling,
    )


def build_experiment_factory_plan(
    *,
    project_id: str,
    brief: AutoResearchResearchBriefRead | None = None,
    hypothesis: AutoResearchHypothesisBankEntryRead | None = None,
    run: AutoResearchRunRead | None = None,
    experiment_design: AutoResearchExperimentDesignRead | None = None,
) -> AutoResearchExperimentFactoryPlanRead:
    selected = hypothesis
    if selected is None and brief is not None:
        selected = selected_hypothesis_from_brief(brief)
    backend = _backend_from_run_or_brief(run=run)
    run_id = run.id if run is not None else None
    brief_id = brief.brief_id if brief is not None else run.brief_id if run is not None else None
    hypothesis_id = selected.hypothesis_id if selected is not None else run.hypothesis_id if run is not None else None
    primary_metric = (
        selected.required_metrics[0]
        if selected is not None and selected.required_metrics
        else run.spec.metrics[0].name
        if run is not None and run.spec is not None and run.spec.metrics
        else "primary_metric"
    )
    dataset = (
        selected.required_datasets[0]
        if selected is not None and selected.required_datasets
        else run.spec.dataset.name
        if run is not None and run.spec is not None
        else "dataset"
    )
    baselines = (
        selected.required_baselines
        if selected is not None and selected.required_baselines
        else [item.name for item in run.spec.baselines]
        if run is not None and run.spec is not None
        else []
    )
    ablations = (
        selected.required_ablations
        if selected is not None and selected.required_ablations
        else [item.name for item in run.spec.ablations]
        if run is not None and run.spec is not None
        else []
    )
    seeds = (
        run.spec.seeds
        if run is not None and run.spec is not None and run.spec.seeds
        else [0, 1, 2]
    )
    sweeps = (
        [item.label for item in run.spec.sweeps]
        if run is not None and run.spec is not None and run.spec.sweeps
        else ["default"]
    )

    jobs: list[AutoResearchExperimentFactoryJobRead] = []
    for index, baseline in enumerate(baselines, start=1):
        jobs.append(
            _job(
                job_id=f"job_baseline_{index}_{_slug(baseline)}",
                job_kind="baseline",
                command="scholarflow toy-run --kind baseline",
                config={"system": baseline, "dataset": dataset, "metric": primary_metric},
                inputs=["brief.json" if brief is not None else "run.json", "spec.json"],
                expected_outputs=["baseline_metrics.json"],
                dependencies=[],
                backend=backend,
                failure_handling="If missing, add_missing_baseline repair must create a baseline job before claims are promoted.",
            )
        )
    candidate_job_id = "job_candidate_method"
    jobs.append(
        _job(
            job_id=candidate_job_id,
            job_kind="candidate_method",
            command="scholarflow toy-run --kind candidate",
            config={"hypothesis_id": hypothesis_id, "dataset": dataset, "metric": primary_metric},
            inputs=["brief.json" if brief is not None else "run.json", "spec.json"],
            expected_outputs=["candidate_metrics.json", "result_artifact.json"],
            dependencies=[job.job_id for job in jobs if job.job_kind == "baseline"],
            backend=backend,
            failure_handling="If candidate output is missing, rerun_failed_job regenerates deterministic toy evidence.",
        )
    )
    for index, ablation in enumerate(ablations, start=1):
        jobs.append(
            _job(
                job_id=f"job_ablation_{index}_{_slug(ablation)}",
                job_kind="ablation",
                command="scholarflow toy-run --kind ablation",
                config={"ablation": ablation, "dataset": dataset, "metric": primary_metric},
                inputs=["candidate_metrics.json"],
                expected_outputs=["ablation_metrics.json"],
                dependencies=[candidate_job_id],
                backend=backend,
                failure_handling="If missing, add_missing_ablation repair adds an ablation job and downgrades mechanism claims until rerun.",
            )
        )
    for seed in seeds:
        jobs.append(
            _job(
                job_id=f"job_seed_{seed}",
                job_kind="seed",
                command="scholarflow toy-run --kind seed",
                config={"seed": seed, "metric": primary_metric},
                inputs=["candidate_metrics.json", "baseline_metrics.json"],
                expected_outputs=[f"seed_{seed}_metrics.json"],
                dependencies=[candidate_job_id],
                backend=backend,
                failure_handling="If statistical evidence is insufficient, increase_seed_count adds more seed jobs.",
            )
        )
    for sweep in sweeps:
        jobs.append(
            _job(
                job_id=f"job_sweep_{_slug(sweep)}",
                job_kind="sweep",
                command="scholarflow toy-run --kind sweep",
                config={"sweep": sweep, "metric": primary_metric},
                inputs=["seed_metrics.json"],
                expected_outputs=[f"sweep_{_slug(sweep)}_summary.json"],
                dependencies=[job.job_id for job in jobs if job.job_kind == "seed"],
                backend=backend,
                failure_handling="If sweep evidence is incomplete, rerun_failed_job regenerates the sweep summary.",
            )
        )

    blockers: list[str] = []
    warnings: list[str] = []
    if not baselines:
        blockers.append("Factory cannot create baseline jobs because no required baselines are registered.")
    if not ablations:
        warnings.append("Factory has no ablation jobs; mechanism claims must remain limited.")
    if len(seeds) < 2:
        warnings.append("Factory has fewer than two seed jobs; statistical evidence is weak.")
    if experiment_design is not None and experiment_design.blockers:
        blockers.extend(experiment_design.blockers)
    payload = {
        "plan_id": "experiment_factory_v1",
        "project_id": project_id,
        "brief_id": brief_id,
        "hypothesis_id": hypothesis_id,
        "run_id": run_id,
        "execution_backend": backend.model_dump(mode="json"),
        "selected_direction_id": selected.direction_id if selected is not None else None,
        "selected_hypothesis": selected.hypothesis if selected is not None else None,
        "jobs": [item.model_dump(mode="json") for item in jobs],
        "job_count": len(jobs),
        "baseline_job_count": sum(1 for item in jobs if item.job_kind == "baseline"),
        "candidate_job_count": sum(1 for item in jobs if item.job_kind == "candidate_method"),
        "ablation_job_count": sum(1 for item in jobs if item.job_kind == "ablation"),
        "seed_job_count": sum(1 for item in jobs if item.job_kind == "seed"),
        "sweep_job_count": sum(1 for item in jobs if item.job_kind == "sweep"),
        "expected_artifacts": _dedupe([output for job in jobs for output in job.expected_outputs]),
        "bridge_ready": True,
        "toy_backend_supported": True,
        "blockers": blockers,
        "warnings": warnings,
    }
    return AutoResearchExperimentFactoryPlanRead(
        generated_at=_utcnow(),
        factory_fingerprint=_fingerprint(payload),
        **payload,
    )


def build_environment_manifest(
    plan: AutoResearchExperimentFactoryPlanRead,
    *,
    executor_mode: str | None = None,
) -> AutoResearchExperimentFactoryEnvironmentManifestRead:
    mode = executor_mode or _executor_mode_for_backend(plan.execution_backend)
    payload = {
        "manifest_id": "experiment_factory_environment_v1",
        "executor_mode": mode,
        "backend": plan.execution_backend.kind,
        "docker_image": plan.execution_backend.docker_image,
        "gpu_required": plan.execution_backend.gpu_required,
        "runtime": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "timeout_seconds": plan.execution_backend.timeout_seconds,
            "job_count": plan.job_count,
            "expected_artifacts": plan.expected_artifacts,
        },
    }
    return AutoResearchExperimentFactoryEnvironmentManifestRead(
        generated_at=_utcnow(),
        manifest_fingerprint=_fingerprint(payload),
        **payload,
    )


def _materialized_output_refs(job: AutoResearchExperimentFactoryJobRead) -> list[str]:
    return [
        f"experiment_factory_outputs/{job.job_id}/{_slug(output)}"
        for output in job.expected_outputs
    ]


def _materialized_repair_classification(
    job: AutoResearchExperimentFactoryJobRead,
    *,
    status: str,
    plan: AutoResearchExperimentFactoryPlanRead,
) -> str:
    if status == "failed":
        if job.job_kind == "baseline":
            return "add_missing_baseline"
        if job.job_kind == "ablation":
            return "add_missing_ablation"
        if job.job_kind == "seed":
            return "increase_seed_count"
        return "rerun_failed_job"
    if job.job_kind == "seed" and plan.seed_job_count < 3:
        return "increase_seed_count"
    return "none"


def materialize_factory_jobs(
    plan: AutoResearchExperimentFactoryPlanRead,
    *,
    environment_manifest: AutoResearchExperimentFactoryEnvironmentManifestRead,
    executor_mode: str | None = None,
    artifact_status: str = "done",
    failed_job_kinds: set[str] | None = None,
    failed_job_ids: set[str] | None = None,
) -> list[AutoResearchExperimentFactoryMaterializedJobRead]:
    mode = executor_mode or environment_manifest.executor_mode
    failed_kinds = failed_job_kinds or set()
    failed_ids = failed_job_ids or set()
    planned = artifact_status in {"queued", "running", "planned"}
    return [
        AutoResearchExperimentFactoryMaterializedJobRead(
            job_id=job.job_id,
            job_kind=job.job_kind,
            executor_mode=mode,  # type: ignore[arg-type]
            backend=plan.execution_backend.kind,
            command=job.command,
            dependencies=job.dependencies,
            expected_outputs=job.expected_outputs,
            output_refs=(
                _materialized_output_refs(job)
                if artifact_status == "done"
                and not plan.blockers
                and job.job_kind not in failed_kinds
                and job.job_id not in failed_ids
                else []
            ),
            environment_manifest_id=environment_manifest.manifest_id,
            repair_classification=_materialized_repair_classification(
                job,
                status=(
                    "planned"
                    if planned
                    else
                    "done"
                    if artifact_status == "done"
                    and not plan.blockers
                    and job.job_kind not in failed_kinds
                    and job.job_id not in failed_ids
                    else "failed"
                ),
                plan=plan,
            ),  # type: ignore[arg-type]
            status=(
                "planned"
                if planned
                else
                "done"
                if artifact_status == "done"
                and not plan.blockers
                and job.job_kind not in failed_kinds
                and job.job_id not in failed_ids
                else "failed"
            ),  # type: ignore[arg-type]
        )
        for job in plan.jobs
    ]


def result_artifact_from_external_import(
    *,
    summary: str,
    primary_metric: str,
    objective_system: str,
    objective_score: float | None,
    baseline_system: str | None = None,
    baseline_score: float | None = None,
    key_findings: list[str] | None = None,
    ablation_scores: dict[str, float] | None = None,
    seed_count: int = 1,
    significance_p_value: float | None = None,
    notes: str | None = None,
) -> ResultArtifact:
    system_results = []
    aggregate_results = []
    if objective_score is not None:
        system_results.append(
            SystemMetricResult(system=objective_system, metrics={primary_metric: objective_score})
        )
        aggregate_results.append(
            AggregateSystemMetricResult(
                system=objective_system,
                mean_metrics={primary_metric: objective_score},
                std_metrics={primary_metric: 0.0},
                min_metrics={primary_metric: objective_score},
                max_metrics={primary_metric: objective_score},
                sample_count=seed_count,
            )
        )
    if baseline_system and baseline_score is not None:
        system_results.append(
            SystemMetricResult(system=baseline_system, metrics={primary_metric: baseline_score})
        )
        aggregate_results.append(
            AggregateSystemMetricResult(
                system=baseline_system,
                mean_metrics={primary_metric: baseline_score},
                std_metrics={primary_metric: 0.0},
                min_metrics={primary_metric: baseline_score},
                max_metrics={primary_metric: baseline_score},
                sample_count=seed_count,
            )
        )
    significance_tests = []
    if (
        significance_p_value is not None
        and baseline_system
        and objective_score is not None
        and baseline_score is not None
    ):
        delta = objective_score - baseline_score
        significance_tests.append(
            SignificanceTestResult(
                scope="system",
                metric=primary_metric,
                candidate=objective_system,
                comparator=baseline_system,
                comparison_family="external_import",
                family_size=1,
                alternative="greater",
                method="paired_sign_flip_exact",
                p_value=significance_p_value,
                adjusted_p_value=significance_p_value,
                correction="holm_bonferroni",
                effect_size=round(delta, 4),
                significant=significance_p_value < 0.05 and delta > 0,
                sample_count=seed_count,
                detail="Imported external experiment significance summary.",
            )
        )
    rows = [[item.system, f"{item.metrics.get(primary_metric, 0):.4f}"] for item in system_results]
    return ResultArtifact(
        status="done" if objective_score is not None else "failed",
        summary=summary,
        key_findings=key_findings or ([summary] if summary else []),
        primary_metric=primary_metric,
        best_system=objective_system if objective_score is not None else None,
        system_results=system_results,
        aggregate_system_results=aggregate_results,
        per_seed_results=[],
        sweep_results=[],
        significance_tests=significance_tests,
        acceptance_checks=[],
        tables=[
            ResultTable(
                title="External Factory Import Results",
                columns=["system", primary_metric],
                rows=rows,
            )
        ],
        logs=notes,
        environment={
            "executor_mode": "external_import",
            "seed_count": seed_count,
            "external_imported": True,
            "ablation_scores": ablation_scores or {},
        },
        outputs={"source": "experiment_factory_external_import"},
        objective_system=objective_system if objective_score is not None else None,
        objective_score=objective_score,
    )


def _failed_job_kinds_for_external_import(
    plan: AutoResearchExperimentFactoryPlanRead,
    *,
    artifact: ResultArtifact,
    baseline_score: float | None,
    ablation_scores: dict[str, float] | None,
    seed_count: int,
) -> set[str]:
    failed: set[str] = set()
    if artifact.status != "done":
        return {job.job_kind for job in plan.jobs}
    if plan.baseline_job_count and baseline_score is None:
        failed.add("baseline")
    if plan.ablation_job_count and not ablation_scores:
        failed.add("ablation")
    if plan.seed_job_count >= 3 and seed_count < 3:
        failed.add("seed")
    return failed


def _artifact_metric_value(
    artifact: ResultArtifact,
    *,
    system: str,
    metric: str,
) -> float | None:
    for result in artifact.aggregate_system_results:
        if result.system == system and metric in result.mean_metrics:
            return result.mean_metrics[metric]
    for result in artifact.system_results:
        if result.system == system and metric in result.metrics:
            return result.metrics[metric]
    return None


def _baseline_score_from_artifact(
    plan: AutoResearchExperimentFactoryPlanRead,
    artifact: ResultArtifact,
) -> float | None:
    metric = artifact.primary_metric
    objective_system = artifact.objective_system or artifact.best_system
    planned_baselines = {
        str(job.config.get("system")).lower()
        for job in plan.jobs
        if job.job_kind == "baseline" and job.config.get("system")
    }
    candidates: list[float] = []
    system_names = [
        result.system
        for result in artifact.aggregate_system_results
    ] or [result.system for result in artifact.system_results]
    for system in system_names:
        if system == objective_system:
            continue
        lowered = system.lower()
        if planned_baselines and lowered not in planned_baselines and "baseline" not in lowered:
            continue
        value = _artifact_metric_value(artifact, system=system, metric=metric)
        if value is not None:
            candidates.append(value)
    return max(candidates) if candidates else None


def _ablation_scores_from_artifact(
    artifact: ResultArtifact,
) -> dict[str, float]:
    raw_scores = artifact.environment.get("ablation_scores")
    scores: dict[str, float] = {}
    if isinstance(raw_scores, dict):
        for key, value in raw_scores.items():
            try:
                scores[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
    metric = artifact.primary_metric
    for result in artifact.aggregate_system_results:
        lowered = result.system.lower()
        if "ablation" not in lowered and "without_" not in lowered:
            continue
        value = result.mean_metrics.get(metric)
        if value is not None:
            scores[result.system] = value
    return scores


def _seed_count_from_artifact(artifact: ResultArtifact) -> int:
    raw_seed_count = artifact.environment.get("seed_count")
    if isinstance(raw_seed_count, int) and raw_seed_count > 0:
        return raw_seed_count
    if artifact.per_seed_results:
        return len({item.seed for item in artifact.per_seed_results})
    sample_counts = [
        item.sample_count
        for item in artifact.aggregate_system_results
        if item.sample_count > 0
    ]
    return max(sample_counts) if sample_counts else 1


def _metric_value_for_system(system: str, *, baseline_index: int = 0, seed: int = 0) -> float:
    lowered = system.lower()
    base = 0.58 + (baseline_index * 0.035)
    if "majority" in lowered or "random" in lowered:
        base = 0.5
    elif "bm25" in lowered or "keyword" in lowered or "tfidf" in lowered:
        base = 0.63
    elif "candidate" in lowered or "method" in lowered:
        base = 0.72
    jitter = ((seed % 7) - 3) * 0.003
    return round(max(0.0, min(0.99, base + jitter)), 4)


def _aggregate(system: str, values: list[float], metric: str) -> AggregateSystemMetricResult:
    mean = sum(values) / max(len(values), 1)
    variance = sum((value - mean) ** 2 for value in values) / max(len(values), 1)
    std = variance ** 0.5
    return AggregateSystemMetricResult(
        system=system,
        mean_metrics={metric: round(mean, 4)},
        std_metrics={metric: round(std, 4)},
        min_metrics={metric: round(min(values), 4) if values else 0.0},
        max_metrics={metric: round(max(values), 4) if values else 0.0},
        sample_count=len(values),
    )


def run_toy_factory_backend(
    plan: AutoResearchExperimentFactoryPlanRead,
) -> ResultArtifact:
    metric = "primary_metric"
    for job in plan.jobs:
        configured_metric = job.config.get("metric")
        if isinstance(configured_metric, str) and configured_metric:
            metric = configured_metric
            break
    baseline_names = [
        str(job.config.get("system"))
        for job in plan.jobs
        if job.job_kind == "baseline" and job.config.get("system")
    ]
    if not baseline_names:
        baseline_names = ["keyword_baseline"]
    seed_values = [
        int(job.config.get("seed"))
        for job in plan.jobs
        if job.job_kind == "seed" and isinstance(job.config.get("seed"), int)
    ] or [0, 1, 2]
    candidate_name = "candidate_method"
    values_by_system: dict[str, list[float]] = {candidate_name: []}
    for baseline in baseline_names:
        values_by_system[baseline] = []
    per_seed_results: list[SeedArtifactResult] = []
    for seed in seed_values:
        system_results: list[SystemMetricResult] = []
        for index, baseline in enumerate(baseline_names):
            value = _metric_value_for_system(baseline, baseline_index=index, seed=seed)
            values_by_system[baseline].append(value)
            system_results.append(SystemMetricResult(system=baseline, metrics={metric: value}))
        candidate_value = _metric_value_for_system(candidate_name, seed=seed)
        values_by_system[candidate_name].append(candidate_value)
        system_results.append(SystemMetricResult(system=candidate_name, metrics={metric: candidate_value}))
        per_seed_results.append(
            SeedArtifactResult(
                seed=seed,
                sweep_label="factory_default",
                best_system=candidate_name,
                objective_system=candidate_name,
                objective_score=candidate_value,
                primary_metric=metric,
                system_results=system_results,
            )
        )
    aggregate_results = [
        _aggregate(system, values, metric)
        for system, values in values_by_system.items()
    ]
    candidate_mean = values_by_system[candidate_name]
    best_baseline_name = max(
        baseline_names,
        key=lambda name: sum(values_by_system[name]) / max(len(values_by_system[name]), 1),
    )
    baseline_mean = values_by_system[best_baseline_name]
    delta = round(
        (sum(candidate_mean) / len(candidate_mean)) - (sum(baseline_mean) / len(baseline_mean)),
        4,
    )
    significance_tests = [
        SignificanceTestResult(
            scope="system",
            metric=metric,
            candidate=candidate_name,
            comparator=best_baseline_name,
            comparison_family="factory_baselines",
            family_size=len(baseline_names),
            alternative="greater",
            method="paired_sign_flip_exact",
            p_value=0.0312 if delta > 0 else 1.0,
            adjusted_p_value=0.0312 if delta > 0 else 1.0,
            correction="holm_bonferroni",
            effect_size=delta,
            significant=delta > 0,
            sample_count=len(seed_values),
            detail="Deterministic toy factory paired comparison over seed jobs.",
        )
    ]
    system_results = [
        SystemMetricResult(system=item.system, metrics=item.mean_metrics)
        for item in aggregate_results
    ]
    return ResultArtifact(
        status="done",
        summary=(
            f"Experiment factory toy backend executed {plan.job_count} planned job(s); "
            f"candidate_method beat {best_baseline_name} by {delta:.4f} on {metric}."
        ),
        key_findings=[
            f"candidate_method mean {metric} exceeded {best_baseline_name} by {delta:.4f}.",
            f"{len(seed_values)} deterministic seed job(s) were materialized.",
            f"{plan.ablation_job_count} ablation job(s) were represented in the execution plan.",
        ],
        primary_metric=metric,
        best_system=candidate_name,
        system_results=system_results,
        aggregate_system_results=aggregate_results,
        per_seed_results=per_seed_results,
        significance_tests=significance_tests,
        tables=[
            ResultTable(
                title="Experiment Factory Toy Results",
                columns=["system", metric],
                rows=[
                    [item.system, f"{item.mean_metrics.get(metric, 0):.4f}"]
                    for item in aggregate_results
                ],
            )
        ],
        acceptance_checks=[],
        environment={
            "executor_mode": "experiment_factory_toy",
            "job_count": plan.job_count,
            "seed_count": len(seed_values),
            "selected_sweep": "factory_default",
        },
        outputs={"execution_plan": "experiment_factory_plan.json", "evidence_ledger": "evidence_ledger.json"},
        objective_system=candidate_name,
        objective_score=round(sum(candidate_mean) / len(candidate_mean), 4),
    )


def build_evidence_ledger(
    *,
    plan: AutoResearchExperimentFactoryPlanRead,
    artifact: ResultArtifact,
    environment_manifest: AutoResearchExperimentFactoryEnvironmentManifestRead | None = None,
    materialized_jobs: list[AutoResearchExperimentFactoryMaterializedJobRead] | None = None,
) -> AutoResearchEvidenceLedgerRead:
    entries: list[AutoResearchEvidenceLedgerEntryRead] = []
    for result in artifact.aggregate_system_results:
        metric_value = result.mean_metrics.get(artifact.primary_metric)
        entries.append(
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id=f"evidence_metric_{_slug(result.system)}",
                source_job_id="job_candidate_method" if result.system == artifact.objective_system else None,
                evidence_kind="metric",
                claim=f"{result.system} achieved mean {artifact.primary_metric}.",
                artifact_ref="run_artifact_json",
                metric=artifact.primary_metric,
                value=metric_value,
                support_status="supported" if metric_value is not None else "missing",
            )
        )
    for job in plan.jobs:
        kind = "baseline" if job.job_kind == "baseline" else "ablation" if job.job_kind == "ablation" else None
        if kind is None:
            continue
        entries.append(
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id=f"evidence_{job.job_id}",
                source_job_id=job.job_id,
                evidence_kind=kind,
                claim=f"Factory planned {job.job_kind} evidence for {job.config}.",
                artifact_ref="experiment_factory_plan_json",
                support_status="supported",
            )
        )
    if environment_manifest is not None:
        entries.append(
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id="evidence_experiment_environment_manifest",
                evidence_kind="artifact",
                claim=(
                    "Experiment execution recorded an environment manifest for "
                    f"{environment_manifest.executor_mode} execution."
                ),
                artifact_ref="experiment_factory_environment_manifest_json",
                support_status="supported",
            )
        )
    for job in materialized_jobs or []:
        entries.append(
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id=f"evidence_materialized_{_slug(job.job_id)}",
                source_job_id=job.job_id,
                evidence_kind=job.job_kind if job.job_kind in {"baseline", "ablation", "seed", "sweep"} else "artifact",  # type: ignore[arg-type]
                claim=f"Factory job {job.job_id} materialized with status {job.status}.",
                artifact_ref="experiment_factory_materialized_jobs_json",
                support_status="supported" if job.status == "done" else "missing",
            )
        )
    blockers: list[str] = []
    if not any(item.evidence_kind == "baseline" for item in entries):
        blockers.append("Evidence ledger is missing baseline evidence.")
    if plan.ablation_job_count and not any(item.evidence_kind == "ablation" for item in entries):
        blockers.append("Evidence ledger is missing ablation evidence.")
    failed_jobs = [job for job in materialized_jobs or [] if job.status == "failed"]
    if any(job.job_kind == "baseline" for job in failed_jobs):
        blockers.append("Materialized execution is missing required baseline outputs.")
    if any(job.job_kind == "ablation" for job in failed_jobs):
        blockers.append("Materialized execution is missing required ablation outputs.")
    if any(job.job_kind == "seed" for job in failed_jobs):
        blockers.append("Materialized execution has insufficient seed/statistical outputs.")
    if any(job.repair_classification == "rerun_failed_job" for job in failed_jobs):
        blockers.append("Materialized execution has runtime job failures.")
    if artifact.status != "done":
        blockers.append("Materialized execution has no completed result artifact.")
    if plan.seed_job_count >= 3 and not artifact.significance_tests:
        blockers.append("Evidence ledger is missing statistical test evidence.")
    if materialized_jobs is not None and len(materialized_jobs) != plan.job_count:
        blockers.append("Evidence ledger job materialization count does not match the factory plan.")
    payload = {
        "ledger_id": "experiment_evidence_ledger_v1",
        "project_id": plan.project_id,
        "run_id": plan.run_id,
        "brief_id": plan.brief_id,
        "hypothesis_id": plan.hypothesis_id,
        "entries": [item.model_dump(mode="json") for item in entries],
        "entry_count": len(entries),
        "complete": not blockers,
        "blockers": blockers,
    }
    return AutoResearchEvidenceLedgerRead(
        generated_at=_utcnow(),
        ledger_fingerprint=_fingerprint(payload),
        **payload,
    )


def build_factory_repair_plan(
    *,
    plan: AutoResearchExperimentFactoryPlanRead,
    evidence_ledger: AutoResearchEvidenceLedgerRead,
) -> AutoResearchExperimentFactoryRepairPlanRead:
    actions = []
    reasons = []
    blocker_text = " ".join(evidence_ledger.blockers).lower()
    if plan.baseline_job_count == 0 or "baseline" in blocker_text:
        actions.append("add_missing_baseline")
        reasons.append("Baseline evidence is missing.")
    if plan.ablation_job_count == 0 or "ablation" in blocker_text:
        actions.append("add_missing_ablation")
        reasons.append("Ablation evidence is missing; mechanism claims must be repaired.")
    if plan.seed_job_count < 3 or "statistical" in blocker_text or "seed" in blocker_text:
        actions.append("increase_seed_count")
        reasons.append("Statistical evidence has fewer than three seed jobs.")
    if plan.blockers or "runtime job failures" in blocker_text:
        actions.append("rerun_failed_job")
        reasons.extend(plan.blockers)
        if "runtime job failures" in blocker_text:
            reasons.append("At least one materialized job failed at runtime.")
    if not actions:
        actions.append("none")
        reasons.append("Factory evidence is complete enough for the selected profile.")
    payload = {
        "repair_id": "experiment_factory_repair_v1",
        "project_id": plan.project_id,
        "run_id": plan.run_id,
        "brief_id": plan.brief_id,
        "actions": actions,
        "action_reasons": reasons,
        "complete": actions == ["none"],
    }
    return AutoResearchExperimentFactoryRepairPlanRead(
        generated_at=_utcnow(),
        repair_fingerprint=_fingerprint(payload),
        **payload,
    )


def execute_toy_experiment_factory(
    plan: AutoResearchExperimentFactoryPlanRead,
) -> AutoResearchExperimentFactoryExecutionRead:
    manifest = build_environment_manifest(plan, executor_mode="toy")
    artifact = run_toy_factory_backend(plan)
    materialized_jobs = materialize_factory_jobs(
        plan,
        environment_manifest=manifest,
        executor_mode="toy",
        artifact_status=artifact.status,
    )
    artifact = artifact.model_copy(
        update={
            "environment": {
                **artifact.environment,
                "environment_manifest_id": manifest.manifest_id,
                "environment_manifest_fingerprint": manifest.manifest_fingerprint,
                "materialized_job_count": len(materialized_jobs),
            },
            "outputs": {
                **artifact.outputs,
                "environment_manifest": "experiment_factory_environment_manifest.json",
                "materialized_jobs": "experiment_factory_materialized_jobs.json",
            },
        }
    )
    ledger = build_evidence_ledger(
        plan=plan,
        artifact=artifact,
        environment_manifest=manifest,
        materialized_jobs=materialized_jobs,
    )
    repair = build_factory_repair_plan(plan=plan, evidence_ledger=ledger)
    return AutoResearchExperimentFactoryExecutionRead(
        project_id=plan.project_id,
        run_id=plan.run_id,
        brief_id=plan.brief_id,
        hypothesis_id=plan.hypothesis_id,
        generated_at=_utcnow(),
        execution_plan=plan,
        environment_manifest=manifest,
        materialized_jobs=materialized_jobs,
        result_artifact=artifact,
        evidence_ledger=ledger,
        repair_plan=repair,
    )


def materialize_factory_execution(
    plan: AutoResearchExperimentFactoryPlanRead,
    *,
    executor_mode: str = "local",
) -> AutoResearchExperimentFactoryExecutionRead:
    manifest = build_environment_manifest(plan, executor_mode=executor_mode)
    materialized_jobs = materialize_factory_jobs(
        plan,
        environment_manifest=manifest,
        executor_mode=executor_mode,
        artifact_status="queued",
    )
    artifact = ResultArtifact(
        status="queued",
        summary=(
            f"Experiment factory materialized {len(materialized_jobs)} "
            f"{executor_mode} job handoff(s); results have not been imported yet."
        ),
        key_findings=[
            "Materialized jobs are planned and cannot support claims until outputs are imported."
        ],
        primary_metric="primary_metric",
        environment={
            "executor_mode": executor_mode,
            "environment_manifest_id": manifest.manifest_id,
            "environment_manifest_fingerprint": manifest.manifest_fingerprint,
            "materialized_job_count": len(materialized_jobs),
        },
        outputs={
            "environment_manifest": "experiment_factory_environment_manifest.json",
            "materialized_jobs": "experiment_factory_materialized_jobs.json",
        },
    )
    ledger = build_evidence_ledger(
        plan=plan,
        artifact=artifact,
        environment_manifest=manifest,
        materialized_jobs=materialized_jobs,
    )
    return AutoResearchExperimentFactoryExecutionRead(
        project_id=plan.project_id,
        run_id=plan.run_id,
        brief_id=plan.brief_id,
        hypothesis_id=plan.hypothesis_id,
        generated_at=_utcnow(),
        execution_plan=plan,
        environment_manifest=manifest,
        materialized_jobs=materialized_jobs,
        result_artifact=artifact,
        evidence_ledger=ledger,
        repair_plan=None,
    )


def execute_imported_artifact_experiment_factory(
    plan: AutoResearchExperimentFactoryPlanRead,
    *,
    artifact: ResultArtifact,
    executor_mode: str = "external_import",
) -> AutoResearchExperimentFactoryExecutionRead:
    manifest = build_environment_manifest(plan, executor_mode=executor_mode)
    baseline_score = _baseline_score_from_artifact(plan, artifact)
    ablation_scores = _ablation_scores_from_artifact(artifact)
    seed_count = _seed_count_from_artifact(artifact)
    failed_job_kinds = _failed_job_kinds_for_external_import(
        plan,
        artifact=artifact,
        baseline_score=baseline_score,
        ablation_scores=ablation_scores,
        seed_count=seed_count,
    )
    materialized_jobs = materialize_factory_jobs(
        plan,
        environment_manifest=manifest,
        executor_mode=executor_mode,
        artifact_status=artifact.status,
        failed_job_kinds=failed_job_kinds,
    )
    enriched_artifact = artifact.model_copy(
        update={
            "environment": {
                **artifact.environment,
                "executor_mode": artifact.environment.get("executor_mode", executor_mode),
                "factory_executor_mode": executor_mode,
                "environment_manifest_id": manifest.manifest_id,
                "environment_manifest_fingerprint": manifest.manifest_fingerprint,
                "materialized_job_count": len(materialized_jobs),
                "failed_materialized_job_kinds": sorted(failed_job_kinds),
                "external_imported": True,
                "seed_count": seed_count,
            },
            "outputs": {
                **artifact.outputs,
                "environment_manifest": "experiment_factory_environment_manifest.json",
                "materialized_jobs": "experiment_factory_materialized_jobs.json",
            },
        }
    )
    ledger = build_evidence_ledger(
        plan=plan,
        artifact=enriched_artifact,
        environment_manifest=manifest,
        materialized_jobs=materialized_jobs,
    )
    repair = build_factory_repair_plan(plan=plan, evidence_ledger=ledger)
    return AutoResearchExperimentFactoryExecutionRead(
        project_id=plan.project_id,
        run_id=plan.run_id,
        brief_id=plan.brief_id,
        hypothesis_id=plan.hypothesis_id,
        generated_at=_utcnow(),
        execution_plan=plan,
        environment_manifest=manifest,
        materialized_jobs=materialized_jobs,
        result_artifact=enriched_artifact,
        evidence_ledger=ledger,
        repair_plan=repair,
    )


def execute_imported_experiment_factory(
    plan: AutoResearchExperimentFactoryPlanRead,
    *,
    summary: str,
    primary_metric: str,
    objective_system: str,
    objective_score: float | None,
    baseline_system: str | None = None,
    baseline_score: float | None = None,
    key_findings: list[str] | None = None,
    ablation_scores: dict[str, float] | None = None,
    seed_count: int = 1,
    significance_p_value: float | None = None,
    notes: str | None = None,
) -> AutoResearchExperimentFactoryExecutionRead:
    artifact = result_artifact_from_external_import(
        summary=summary,
        primary_metric=primary_metric,
        objective_system=objective_system,
        objective_score=objective_score,
        baseline_system=baseline_system,
        baseline_score=baseline_score,
        key_findings=key_findings,
        ablation_scores=ablation_scores,
        seed_count=seed_count,
        significance_p_value=significance_p_value,
        notes=notes,
    )
    return execute_imported_artifact_experiment_factory(
        plan,
        artifact=artifact,
        executor_mode="external_import",
    )
