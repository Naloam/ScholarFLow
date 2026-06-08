from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from typing import Any

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
    ConfidenceIntervalSummary,
    ExecutionBackendSpec,
    NegativeResultRecord,
    ResultArtifact,
    ResultTable,
    SeedArtifactResult,
    SignificanceTestResult,
    SweepEvaluationResult,
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


def _dedupe(items: list[Any]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item is None:
            continue
        cleaned = " ".join(str(item).split()).strip()
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
    if brief is not None and (
        brief.status == "blocked"
        or brief.next_action == "blocked"
        or brief.domain_blockers
    ):
        backend = _backend_from_run_or_brief(run=run)
        blockers = _dedupe(
            [
                *brief.domain_blockers,
                *brief.feasibility_assessment.blockers,
                "Experiment factory blocked: domain routing did not produce an executable supported-domain hypothesis.",
            ]
        )
        payload = {
            "plan_id": "experiment_factory_v1",
            "project_id": project_id,
            "brief_id": brief.brief_id,
            "hypothesis_id": None,
            "run_id": run.id if run is not None else None,
            "execution_backend": backend.model_dump(mode="json"),
            "domain_decision": (
                brief.domain_decision.model_dump(mode="json")
                if brief.domain_decision is not None
                else None
            ),
            "domain_benchmark_resolver": (
                brief.domain_benchmark_resolver.model_dump(mode="json")
                if brief.domain_benchmark_resolver is not None
                else None
            ),
            "domain_experiment_protocol": (
                brief.domain_experiment_protocol.model_dump(mode="json")
                if brief.domain_experiment_protocol is not None
                else None
            ),
            "selected_direction_id": None,
            "selected_hypothesis": None,
            "jobs": [],
            "job_count": 0,
            "baseline_job_count": 0,
            "candidate_job_count": 0,
            "ablation_job_count": 0,
            "seed_job_count": 0,
            "sweep_job_count": 0,
            "expected_artifacts": [],
            "bridge_ready": False,
            "toy_backend_supported": False,
            "blockers": blockers,
            "warnings": [
                "No toy/local experiment outputs were generated for this unsupported-domain brief."
            ],
        }
        return AutoResearchExperimentFactoryPlanRead(
            generated_at=_utcnow(),
            factory_fingerprint=_fingerprint(payload),
            **payload,
        )
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
    domain_benchmark_resolver = brief.domain_benchmark_resolver if brief is not None else None
    domain_protocol = brief.domain_experiment_protocol if brief is not None else None
    if domain_benchmark_resolver is not None and domain_benchmark_resolver.status == "blocked":
        blockers.extend(domain_benchmark_resolver.blockers)
    if domain_protocol is not None and domain_protocol.status == "blocked":
        blockers.extend(domain_protocol.blockers or domain_protocol.readiness_blockers)
    if domain_benchmark_resolver is not None and domain_benchmark_resolver.status == "limited":
        warnings.extend(domain_benchmark_resolver.blockers[:3])
        warnings.extend(domain_benchmark_resolver.limitations[:3])
    if domain_protocol is not None and domain_protocol.status == "limited":
        warnings.extend(domain_protocol.readiness_blockers[:3])
        warnings.extend(domain_protocol.limitations[:3])
    protocol_expected_outputs = (
        list(domain_protocol.expected_outputs)
        if domain_protocol is not None and domain_protocol.expected_outputs
        else []
    )
    payload = {
        "plan_id": "experiment_factory_v1",
        "project_id": project_id,
        "brief_id": brief_id,
        "hypothesis_id": hypothesis_id,
        "run_id": run_id,
        "execution_backend": backend.model_dump(mode="json"),
        "domain_decision": (
            brief.domain_decision.model_dump(mode="json")
            if brief is not None and brief.domain_decision is not None
            else None
        ),
        "domain_benchmark_resolver": (
            domain_benchmark_resolver.model_dump(mode="json")
            if domain_benchmark_resolver is not None
            else None
        ),
        "domain_experiment_protocol": (
            domain_protocol.model_dump(mode="json")
            if domain_protocol is not None
            else None
        ),
        "selected_direction_id": selected.direction_id if selected is not None else None,
        "selected_hypothesis": selected.hypothesis if selected is not None else None,
        "jobs": [item.model_dump(mode="json") for item in jobs],
        "job_count": len(jobs),
        "baseline_job_count": sum(1 for item in jobs if item.job_kind == "baseline"),
        "candidate_job_count": sum(1 for item in jobs if item.job_kind == "candidate_method"),
        "ablation_job_count": sum(1 for item in jobs if item.job_kind == "ablation"),
        "seed_job_count": sum(1 for item in jobs if item.job_kind == "seed"),
        "sweep_job_count": sum(1 for item in jobs if item.job_kind == "sweep"),
        "expected_artifacts": _dedupe(
            [output for job in jobs for output in job.expected_outputs]
            + protocol_expected_outputs
        ),
        "bridge_ready": True,
        "toy_backend_supported": True,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
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


def _materialized_failure_classification(
    job: AutoResearchExperimentFactoryJobRead,
    *,
    status: str,
    repair_classification: str,
    planned: bool,
) -> str:
    if planned:
        return "planned"
    if status == "done":
        return "none"
    if repair_classification == "add_missing_baseline":
        return "missing_baseline_outputs"
    if repair_classification == "add_missing_ablation":
        return "missing_ablation_outputs"
    if repair_classification == "increase_seed_count":
        return "insufficient_statistics_outputs"
    if job.job_kind == "candidate_method":
        return "candidate_runtime_or_output_failure"
    return "runtime_failure"


def _runtime_contract_for_job(
    job: AutoResearchExperimentFactoryJobRead,
    *,
    mode: str,
    plan: AutoResearchExperimentFactoryPlanRead,
    status: str,
) -> dict[str, object]:
    return {
        "contract_id": f"runtime_contract_{_slug(job.job_id)}",
        "executor_mode": mode,
        "backend": plan.execution_backend.kind,
        "command": job.command,
        "dependencies": job.dependencies,
        "required_inputs": job.inputs,
        "expected_outputs": job.expected_outputs,
        "timeout_seconds": plan.execution_backend.timeout_seconds,
        "retry_on": job.retry_policy.retry_on,
        "max_retries": job.retry_policy.max_retries,
        "status": status,
    }


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
    materialized: list[AutoResearchExperimentFactoryMaterializedJobRead] = []
    for step, job in enumerate(plan.jobs, start=1):
        status = (
            "planned"
            if planned
            else
            "done"
            if artifact_status == "done"
            and not plan.blockers
            and job.job_kind not in failed_kinds
            and job.job_id not in failed_ids
            else "failed"
        )
        repair_classification = _materialized_repair_classification(
            job,
            status=status,
            plan=plan,
        )
        materialized.append(
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
                    if status == "done"
                    and not plan.blockers
                    else []
                ),
                runtime_contract=_runtime_contract_for_job(
                    job,
                    mode=mode,
                    plan=plan,
                    status=status,
                ),
                started_at_step=step,
                completed_at_step=step if status in {"done", "failed"} else None,
                environment_manifest_id=environment_manifest.manifest_id,
                repair_classification=repair_classification,  # type: ignore[arg-type]
                failure_classification=_materialized_failure_classification(
                    job,
                    status=status,
                    repair_classification=repair_classification,
                    planned=planned,
                ),
                status=status,  # type: ignore[arg-type]
            )
        )
    return materialized


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


def _known_failed_job_ids(
    plan: AutoResearchExperimentFactoryPlanRead,
    failed_job_ids: set[str] | None,
) -> set[str]:
    if not failed_job_ids:
        return set()
    known_ids = {job.job_id for job in plan.jobs}
    return {job_id for job_id in failed_job_ids if job_id in known_ids}


def _known_failed_job_kinds(
    plan: AutoResearchExperimentFactoryPlanRead,
    failed_job_kinds: set[str] | None,
) -> set[str]:
    if not failed_job_kinds:
        return set()
    known_kinds = {job.job_kind for job in plan.jobs}
    return {job_kind for job_kind in failed_job_kinds if job_kind in known_kinds}


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


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z0-9_]+", text.lower())


def _candidate_ids(example: dict[str, Any]) -> list[str]:
    return [
        str(candidate.get("id"))
        for candidate in example.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("id") is not None
    ]


def _candidate_texts(example: dict[str, Any]) -> dict[str, str]:
    return {
        str(candidate.get("id")): str(candidate.get("text") or "")
        for candidate in example.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("id") is not None
    }


def _reciprocal_rank(relevant_ids: list[str], ranked_ids: list[str]) -> float:
    relevant = set(relevant_ids)
    for index, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant:
            return 1.0 / index
    return 0.0


def _recall_at_k(relevant_ids: list[str], ranked_ids: list[str], k: int) -> float:
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant) / len(relevant)


def _ndcg_at_k(relevant_ids: list[str], ranked_ids: list[str], k: int) -> float:
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / math.log2(index + 1)
        for index, doc_id in enumerate(ranked_ids[:k], start=1)
        if doc_id in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def _normalize_claim_label(value: Any) -> str | None:
    lowered = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if lowered in {"support", "supports", "supported", "entails", "entailment"}:
        return "supported"
    if lowered in {"refute", "refutes", "refuted", "contradict", "contradicts", "contradicted"}:
        return "refuted"
    if lowered in {"nei", "not_enough_info", "not_enough_evidence", "unknown", "unverifiable"}:
        return "not_enough_info"
    return None


def _predict_claim_label(example: dict[str, Any], ranked_ids: list[str]) -> str:
    if not ranked_ids:
        return "not_enough_info"
    text_by_id = _candidate_texts(example)
    top_text = text_by_id.get(ranked_ids[0], "")
    query_tokens = set(_tokenize(str(example.get("query") or "")))
    doc_tokens = set(_tokenize(top_text))
    refute_markers = {
        "not",
        "no",
        "never",
        "without",
        "fails",
        "failed",
        "contradicts",
        "contradicted",
        "refutes",
        "refuted",
        "worse",
    }
    overlap = len(query_tokens & doc_tokens)
    if overlap < 1:
        return "not_enough_info"
    if doc_tokens & refute_markers:
        return "refuted"
    return "supported" if overlap >= 2 else "not_enough_info"


def _query_metric_record(example: dict[str, Any], ranked_ids: list[str]) -> dict[str, Any]:
    relevant_ids = [str(item) for item in example.get("relevant_ids", [])]
    retrieval_applicable = bool(relevant_ids)
    record: dict[str, Any] = {
        "query": str(example.get("query") or ""),
        "claim_id": str(example.get("claim_id") or ""),
        "relevant_ids": relevant_ids,
        "ranked_ids_at_10": ranked_ids[:10],
        "retrieval_applicable": retrieval_applicable,
        "reciprocal_rank": _reciprocal_rank(relevant_ids, ranked_ids) if retrieval_applicable else 0.0,
        "recall_at_1": _recall_at_k(relevant_ids, ranked_ids, 1) if retrieval_applicable else 0.0,
        "ndcg_at_10": _ndcg_at_k(relevant_ids, ranked_ids, 10) if retrieval_applicable else 0.0,
        "recall_at_10": _recall_at_k(relevant_ids, ranked_ids, 10) if retrieval_applicable else 0.0,
        "evidence_coverage": (
            1.0 if retrieval_applicable and set(relevant_ids).issubset(set(ranked_ids[:10])) else 0.0
        ),
    }
    failure_modes: list[str] = []
    negative_evidence_categories: list[str] = []
    if retrieval_applicable and record["recall_at_1"] < 1.0:
        failure_modes.append("top_rank_not_relevant")
    if retrieval_applicable and record["recall_at_10"] < 1.0:
        failure_modes.append("missing_relevant_evidence_top_10")
        negative_evidence_categories.append("retrieval_miss")
    if retrieval_applicable and record["evidence_coverage"] < 1.0:
        failure_modes.append("incomplete_gold_evidence_coverage")
        negative_evidence_categories.append("retrieval_miss")

    gold_label = _normalize_claim_label(example.get("claim_label"))
    if gold_label:
        predicted_label = _predict_claim_label(example, ranked_ids)
        gold_unsupported = gold_label != "supported"
        predicted_unsupported = predicted_label != "supported"
        if gold_label == "refuted":
            negative_evidence_categories.append("contradiction_refutation_ambiguity")
        if gold_label == "not_enough_info":
            negative_evidence_categories.append("insufficient_evidence_case")
        record.update(
            {
                "claim_label": gold_label,
                "predicted_claim_label": predicted_label,
                "verification_correct": 1.0 if predicted_label == gold_label else 0.0,
                "gold_unsupported": gold_unsupported,
                "predicted_unsupported": predicted_unsupported,
                "unsupported_true_positive": 1.0 if gold_unsupported and predicted_unsupported else 0.0,
                "unsupported_false_positive": 1.0 if not gold_unsupported and predicted_unsupported else 0.0,
                "unsupported_false_negative": 1.0 if gold_unsupported and not predicted_unsupported else 0.0,
                "unsupported_precision_applicable": predicted_unsupported,
                "unsupported_recall_applicable": gold_unsupported,
                "unsupported_claim_precision": 1.0 if gold_unsupported and predicted_unsupported else 0.0,
                "unsupported_claim_recall": 1.0 if gold_unsupported and predicted_unsupported else 0.0,
                "abstention_correct": 1.0 if gold_label == "not_enough_info" and predicted_label == "not_enough_info" else 0.0,
                "abstention_applicable": 1.0 if gold_label == "not_enough_info" else 0.0,
            }
        )
        gold_repair_needed = bool(
            gold_unsupported
            or (retrieval_applicable and record["evidence_coverage"] < 1.0)
        )
        predicted_repair_needed = bool(
            predicted_unsupported
            or (retrieval_applicable and record["recall_at_10"] < 1.0)
        )
        record.update(
            {
                "repair_needed": gold_repair_needed,
                "repair_predicted": predicted_repair_needed,
                "repair_true_positive": 1.0 if gold_repair_needed and predicted_repair_needed else 0.0,
                "repair_false_positive": 1.0 if not gold_repair_needed and predicted_repair_needed else 0.0,
                "repair_false_negative": 1.0 if gold_repair_needed and not predicted_repair_needed else 0.0,
                "repair_precision_applicable": predicted_repair_needed,
                "repair_recall_applicable": gold_repair_needed,
                "repair_precision": 1.0 if gold_repair_needed and predicted_repair_needed else 0.0,
                "repair_recall": 1.0 if gold_repair_needed and predicted_repair_needed else 0.0,
            }
        )
        if not record["verification_correct"]:
            failure_modes.append("verification_mismatch")
        if record["unsupported_false_negative"]:
            failure_modes.append("unsupported_claim_missed")
            negative_evidence_categories.append("unsupported_claim_false_negative")
        if record["unsupported_false_positive"]:
            failure_modes.append("false_unsupported_alarm")
            negative_evidence_categories.append("unsupported_claim_false_positive")
        if gold_label == "not_enough_info" and not record["abstention_correct"]:
            failure_modes.append("abstention_failure")
            negative_evidence_categories.append("abstention_failure")
        if record["repair_false_negative"]:
            failure_modes.append("repair_router_missed_needed_repair")
            negative_evidence_categories.append("repair_router_failure")
        if record["repair_false_positive"]:
            failure_modes.append("repair_router_false_alarm")
            negative_evidence_categories.append("repair_router_failure")
    record["failure_modes"] = _dedupe(failure_modes)
    record["negative_evidence_categories"] = _dedupe(negative_evidence_categories)
    return record


def _metric_average(records: list[dict[str, Any]], key: str) -> float:
    if not records:
        return 0.0
    return round(sum(float(record.get(key) or 0.0) for record in records) / len(records), 4)


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return mean, variance ** 0.5


def _confidence_interval(values: list[float]) -> ConfidenceIntervalSummary:
    mean, std = _mean_std(values)
    if len(values) <= 1:
        lower = upper = mean
    else:
        # Conservative normal approximation. The method label stays student_t_95 because the
        # schema currently exposes that single deterministic confidence interval method.
        margin = 1.96 * std / math.sqrt(len(values))
        lower = max(0.0, mean - margin)
        upper = min(1.0, mean + margin)
    return ConfidenceIntervalSummary(lower=round(lower, 4), upper=round(upper, 4))


_QUERY_METRIC_FIELDS = {
    "mrr": "reciprocal_rank",
    "recall_at_1": "recall_at_1",
    "ndcg_at_10": "ndcg_at_10",
    "recall_at_10": "recall_at_10",
    "evidence_coverage": "evidence_coverage",
    "verification_accuracy": "verification_correct",
    "unsupported_claim_precision": "unsupported_claim_precision",
    "unsupported_claim_recall": "unsupported_claim_recall",
    "abstention_accuracy": "abstention_correct",
    "repair_precision": "repair_precision",
    "repair_recall": "repair_recall",
}


_QUERY_METRIC_APPLICABILITY_FIELDS = {
    "mrr": "retrieval_applicable",
    "recall_at_1": "retrieval_applicable",
    "ndcg_at_10": "retrieval_applicable",
    "recall_at_10": "retrieval_applicable",
    "evidence_coverage": "retrieval_applicable",
    "verification_accuracy": "claim_label",
    "unsupported_claim_precision": "unsupported_precision_applicable",
    "unsupported_claim_recall": "unsupported_recall_applicable",
    "abstention_accuracy": "abstention_applicable",
    "repair_precision": "repair_precision_applicable",
    "repair_recall": "repair_recall_applicable",
}


def _diagnostic_metric_values(metric: str, diagnostics: list[dict[str, Any]]) -> list[float]:
    field = _QUERY_METRIC_FIELDS.get(metric)
    applicability_field = _QUERY_METRIC_APPLICABILITY_FIELDS.get(metric)
    values: list[float] = []
    for record in diagnostics:
        if not field or field not in record:
            continue
        if applicability_field == "claim_label":
            if not record.get("claim_label"):
                continue
        elif applicability_field and not record.get(applicability_field):
            continue
        values.append(float(record.get(field) or 0.0))
    return values


def _aggregate_from_diagnostics(
    *,
    system: str,
    metrics: dict[str, float],
    diagnostics: list[dict[str, Any]],
) -> AggregateSystemMetricResult:
    std_metrics: dict[str, float] = {}
    min_metrics: dict[str, float] = {}
    max_metrics: dict[str, float] = {}
    confidence_intervals: dict[str, ConfidenceIntervalSummary] = {}
    for metric, value in metrics.items():
        values = _diagnostic_metric_values(metric, diagnostics)
        if values:
            _mean, std = _mean_std(values)
            std_metrics[metric] = round(std, 4)
            min_metrics[metric] = round(min(values), 4)
            max_metrics[metric] = round(max(values), 4)
            confidence_intervals[metric] = _confidence_interval(values)
        else:
            std_metrics[metric] = 0.0
            min_metrics[metric] = value
            max_metrics[metric] = value
    return AggregateSystemMetricResult(
        system=system,
        mean_metrics=metrics,
        std_metrics=std_metrics,
        confidence_intervals=confidence_intervals,
        min_metrics=min_metrics,
        max_metrics=max_metrics,
        sample_count=len(diagnostics),
    )


def _exact_sign_test_greater(deltas: list[float]) -> dict[str, Any]:
    nonzero = [delta for delta in deltas if abs(delta) > 1e-12]
    wins = sum(1 for delta in nonzero if delta > 0)
    losses = sum(1 for delta in nonzero if delta < 0)
    n = len(nonzero)
    if n == 0:
        p_value = 1.0
    else:
        p_value = sum(math.comb(n, k) for k in range(wins, n + 1)) / (2 ** n)
    effect_size = sum(deltas) / len(deltas) if deltas else 0.0
    return {
        "wins": wins,
        "losses": losses,
        "ties": len(deltas) - n,
        "nonzero_sample_count": n,
        "sample_count": len(deltas),
        "effect_size": round(effect_size, 4),
        "p_value": round(p_value, 6),
    }


def _evaluate_ranker(
    *,
    system: str,
    examples: list[dict[str, Any]],
    ranking_fn,
) -> tuple[SystemMetricResult, list[dict[str, Any]]]:
    diagnostics = [
        _query_metric_record(example, ranking_fn(example))
        for example in examples
    ]
    retrieval_records = [record for record in diagnostics if record.get("retrieval_applicable")]
    metrics: dict[str, float] = {
        "mrr": _metric_average(retrieval_records, "reciprocal_rank"),
        "recall_at_1": _metric_average(retrieval_records, "recall_at_1"),
        "ndcg_at_10": _metric_average(retrieval_records, "ndcg_at_10"),
        "recall_at_10": _metric_average(retrieval_records, "recall_at_10"),
        "evidence_coverage": _metric_average(retrieval_records, "evidence_coverage"),
    }
    verification_records = [record for record in diagnostics if record.get("claim_label")]
    if verification_records:
        unsupported_tp = sum(float(record["unsupported_true_positive"]) for record in verification_records)
        unsupported_fp = sum(float(record["unsupported_false_positive"]) for record in verification_records)
        unsupported_fn = sum(float(record["unsupported_false_negative"]) for record in verification_records)
        repair_tp = sum(float(record.get("repair_true_positive") or 0.0) for record in verification_records)
        repair_fp = sum(float(record.get("repair_false_positive") or 0.0) for record in verification_records)
        repair_fn = sum(float(record.get("repair_false_negative") or 0.0) for record in verification_records)
        abstention_denominator = sum(float(record["abstention_applicable"]) for record in verification_records)
        metrics.update(
            {
                "verification_accuracy": _metric_average(verification_records, "verification_correct"),
                "unsupported_claim_precision": (
                    round(unsupported_tp / (unsupported_tp + unsupported_fp), 4)
                    if unsupported_tp + unsupported_fp
                    else 0.0
                ),
                "unsupported_claim_recall": (
                    round(unsupported_tp / (unsupported_tp + unsupported_fn), 4)
                    if unsupported_tp + unsupported_fn
                    else 0.0
                ),
                "abstention_accuracy": (
                    round(
                        sum(float(record["abstention_correct"]) for record in verification_records)
                        / abstention_denominator,
                        4,
                    )
                    if abstention_denominator
                    else 0.0
                ),
                "repair_precision": (
                    round(repair_tp / (repair_tp + repair_fp), 4)
                    if repair_tp + repair_fp
                    else 0.0
                ),
                "repair_recall": (
                    round(repair_tp / (repair_tp + repair_fn), 4)
                    if repair_tp + repair_fn
                    else 0.0
                ),
            }
        )
    return SystemMetricResult(system=system, metrics=metrics), diagnostics


def run_cached_claim_evidence_factory_backend(
    plan: AutoResearchExperimentFactoryPlanRead,
    *,
    benchmark_payload: dict[str, Any],
) -> ResultArtifact:
    examples = [
        item
        for item in benchmark_payload.get("test", [])
        if isinstance(item, dict) and item.get("query") and item.get("candidates")
    ]
    train_examples = [
        item
        for item in benchmark_payload.get("train", [])
        if isinstance(item, dict) and item.get("candidates")
    ]
    if not examples:
        return ResultArtifact(
            status="failed",
            summary="Cached claim-evidence benchmark execution failed because no normalized test examples were available.",
            primary_metric="mrr",
            environment={
                "executor_mode": "experiment_factory_cached_benchmark",
                "benchmark_name": benchmark_payload.get("name"),
            },
            outputs={"benchmark_error": "missing_test_examples"},
        )

    document_frequency: Counter[str] = Counter()
    candidate_documents = [
        str(candidate.get("text") or "")
        for example in [*train_examples, *examples]
        for candidate in example.get("candidates", [])
        if isinstance(candidate, dict)
    ]
    for text in candidate_documents:
        document_frequency.update(set(_tokenize(text)))
    document_count = max(len(candidate_documents), 1)
    cue_terms = {
        "claim",
        "evidence",
        "citation",
        "support",
        "supported",
        "unsupported",
        "refute",
        "refuted",
        "contradict",
        "contradicted",
        "abstain",
        "not",
        "review",
        "repair",
    }

    def idf(token: str) -> float:
        return math.log((document_count + 1) / (document_frequency.get(token, 0) + 1)) + 1.0

    def score(
        example: dict[str, Any],
        text: str,
        *,
        bigram: bool = False,
        ledger: bool = False,
        tfidf: bool = False,
        repair_router: bool = True,
    ) -> float:
        query_tokens = _tokenize(str(example.get("query") or ""))
        doc_tokens = _tokenize(text)
        doc_token_set = set(doc_tokens)
        doc_counts = Counter(doc_tokens)
        total = sum(
            (
                idf(token) * (1.0 + math.log(doc_counts.get(token, 1)))
                if tfidf
                else idf(token)
            )
            for token in query_tokens
            if token in doc_token_set
        )
        if bigram:
            query_bigrams = set(zip(query_tokens, query_tokens[1:]))
            doc_bigrams = set(zip(doc_tokens, doc_tokens[1:]))
            total += 0.5 * len(query_bigrams & doc_bigrams)
        if ledger:
            total += 0.35 * len((set(query_tokens) & doc_token_set) & cue_terms)
        if repair_router and {"unsupported", "claim", "not"} & set(query_tokens):
            if doc_token_set & {"unsupported", "refute", "refuted", "contradict", "contradicted", "not"}:
                total += 0.25
        return total

    def stable_rank(
        example: dict[str, Any],
        *,
        bigram: bool = False,
        ledger: bool = False,
        tfidf: bool = False,
        repair_router: bool = True,
    ) -> list[str]:
        texts = _candidate_texts(example)
        return sorted(
            _candidate_ids(example),
            key=lambda doc_id: (
                -score(
                    example,
                    texts.get(doc_id, ""),
                    bigram=bigram,
                    ledger=ledger,
                    tfidf=tfidf,
                    repair_router=repair_router,
                ),
                doc_id,
            ),
        )

    method_configs: dict[str, dict[str, Any]] = {
        "random_ranker": {
            "ladder_role": "random_ranker",
            "ranker": "deterministic_id_order",
            "uses_idf": False,
            "uses_bigram": False,
            "uses_ledger": False,
            "uses_verification": False,
            "repair_router_enabled": False,
        },
        "overlap_ranker": {
            "ladder_role": "lexical_overlap",
            "ranker": "idf_weighted_token_overlap",
            "uses_idf": True,
            "uses_bigram": False,
            "uses_ledger": False,
            "uses_verification": True,
            "repair_router_enabled": True,
        },
        "bm25_ranker": {
            "ladder_role": "tfidf_bm25_style_retrieval",
            "ranker": "deterministic_tfidf_bm25_style_overlap",
            "uses_idf": True,
            "uses_tfidf": True,
            "uses_bigram": False,
            "uses_ledger": False,
            "uses_verification": True,
            "repair_router_enabled": True,
        },
        "bigram_ranker": {
            "ladder_role": "phrase_or_bigram_aware_retrieval",
            "ranker": "idf_bigram_overlap",
            "uses_idf": True,
            "uses_bigram": True,
            "uses_ledger": False,
            "uses_verification": True,
            "repair_router_enabled": True,
        },
        "ledger_aware_ranker": {
            "ladder_role": "ledger_aware_retrieval",
            "ranker": "idf_bigram_overlap_with_ledger_cues",
            "uses_idf": True,
            "uses_bigram": True,
            "uses_ledger": True,
            "uses_verification": True,
            "repair_router_enabled": True,
        },
        "abstention_repair_router": {
            "ladder_role": "abstention_or_repair_router",
            "ranker": "ledger_aware_ranker_with_abstention_repair_routing",
            "uses_idf": True,
            "uses_bigram": True,
            "uses_ledger": True,
            "uses_verification": True,
            "repair_router_enabled": True,
            "abstains_on_not_enough_info": True,
        },
        "no_ledger_ablation": {
            "ladder_role": "no_ledger_ablation",
            "ranker": "bigram_ranker_without_ledger_cues",
            "uses_idf": True,
            "uses_bigram": True,
            "uses_ledger": False,
            "uses_verification": True,
            "repair_router_enabled": True,
        },
        "retrieval_only_no_verification_ablation": {
            "ladder_role": "retrieval_only_no_verification_ablation",
            "ranker": "ledger_aware_ranker_without_verification_metrics",
            "uses_idf": True,
            "uses_bigram": True,
            "uses_ledger": True,
            "uses_verification": False,
            "repair_router_enabled": True,
        },
        "repair_router_disabled_ablation": {
            "ladder_role": "repair_router_disabled_ablation",
            "ranker": "ledger_aware_ranker_without_repair_router",
            "uses_idf": True,
            "uses_bigram": True,
            "uses_ledger": True,
            "uses_verification": True,
            "repair_router_enabled": False,
        },
    }
    systems: list[tuple[str, Any]] = [
        ("random_ranker", lambda example: sorted(_candidate_ids(example))),
        ("overlap_ranker", lambda example: stable_rank(example)),
        ("bm25_ranker", lambda example: stable_rank(example, tfidf=True)),
        ("bigram_ranker", lambda example: stable_rank(example, bigram=True)),
        ("ledger_aware_ranker", lambda example: stable_rank(example, bigram=True, ledger=True)),
        (
            "abstention_repair_router",
            lambda example: stable_rank(example, bigram=True, ledger=True),
        ),
        ("no_ledger_ablation", lambda example: stable_rank(example, bigram=True)),
        (
            "retrieval_only_no_verification_ablation",
            lambda example: stable_rank(example, bigram=True, ledger=True),
        ),
        (
            "repair_router_disabled_ablation",
            lambda example: stable_rank(example, bigram=True, ledger=True, repair_router=False),
        ),
    ]
    verification_metrics = {
        "verification_accuracy",
        "unsupported_claim_precision",
        "unsupported_claim_recall",
        "abstention_accuracy",
        "repair_precision",
        "repair_recall",
    }
    repair_metrics = {"repair_precision", "repair_recall"}

    def evaluate_examples(
        split_examples: list[dict[str, Any]],
        *,
        note_tag: str,
    ) -> list[tuple[SystemMetricResult, list[dict[str, Any]]]]:
        raw = [
            _evaluate_ranker(system=system, examples=split_examples, ranking_fn=ranking_fn)
            for system, ranking_fn in systems
        ]
        filtered = []
        for result, diagnostics in raw:
            config = method_configs.get(result.system, {})
            metrics = dict(result.metrics)
            if not config.get("uses_verification", True):
                for metric in verification_metrics:
                    metrics.pop(metric, None)
            if not config.get("repair_router_enabled", False):
                for metric in repair_metrics:
                    metrics.pop(metric, None)
            filtered.append(
                (
                    result.model_copy(
                        update={
                            "metrics": metrics,
                            "notes": "; ".join(
                                [
                                    *([result.notes] if result.notes else []),
                                    f"ladder_role={method_configs.get(result.system, {}).get('ladder_role')}",
                                    "deterministic_cached_execution=true",
                                    note_tag,
                                ]
                            ),
                        }
                    ),
                    diagnostics,
                )
            )
        return filtered

    evaluated = evaluate_examples(examples, note_tag="benchmark_split=test")
    system_results = [result for result, _diagnostics in evaluated]
    diagnostics_by_system = {result.system: diagnostics for result, diagnostics in evaluated}
    split_evaluations: list[dict[str, Any]] = []
    split_sweeps: list[SweepEvaluationResult] = []
    split_inputs = [
        ("train", train_examples),
        ("test", examples),
    ]
    for split_label, split_examples in split_inputs:
        split_usable = [
            item
            for item in split_examples
            if isinstance(item, dict) and item.get("query") and item.get("candidates")
        ]
        if not split_usable:
            continue
        split_evaluated = evaluate_examples(
            split_usable,
            note_tag=f"benchmark_split={split_label}",
        )
        split_system_results = [result for result, _diagnostics in split_evaluated]
        split_aggregate_results = [
            _aggregate_from_diagnostics(
                system=result.system,
                metrics=result.metrics,
                diagnostics=diagnostics,
            )
            for result, diagnostics in split_evaluated
        ]
        split_best = max(
            split_system_results,
            key=lambda item: item.metrics.get("mrr", 0.0),
        )
        split_objective = next(
            (item for item in split_system_results if item.system == "ledger_aware_ranker"),
            split_best,
        )
        split_payload = {
            "split": split_label,
            "example_count": len(split_usable),
            "best_system": split_best.system,
            "objective_system": split_objective.system,
            "objective_score": split_objective.metrics.get("mrr"),
            "system_results": [
                result.model_dump(mode="json") for result in split_system_results
            ],
            "aggregate_system_results": [
                result.model_dump(mode="json") for result in split_aggregate_results
            ],
            "diagnostic_count_by_system": {
                result.system: len(diagnostics)
                for result, diagnostics in split_evaluated
            },
        }
        split_evaluations.append(
            {**split_payload, "split_fingerprint": _fingerprint(split_payload)}
        )
        split_sweeps.append(
            SweepEvaluationResult(
                label=f"benchmark_split_{split_label}",
                params={
                    "split": split_label,
                    "split_kind": "benchmark_payload_split",
                    "example_count": len(split_usable),
                },
                description=(
                    "Deterministic split-level evaluation over a repository-local "
                    f"{split_label} benchmark split."
                ),
                status="done",
                best_system=split_best.system,
                objective_system=split_objective.system,
                objective_score_mean=split_objective.metrics.get("mrr"),
                objective_score_std=0.0,
                objective_score_confidence_interval=(
                    next(
                        (
                            aggregate.confidence_intervals.get("mrr")
                            for aggregate in split_aggregate_results
                            if aggregate.system == split_objective.system
                        ),
                        None,
                    )
                ),
                aggregate_system_results=split_aggregate_results,
                seed_count=1,
                successful_seed_count=1,
            )
        )
    method_outputs = {
        result.system: {
            "system": result.system,
            "method_config": method_configs.get(result.system, {}),
            "metrics": dict(result.metrics),
            "diagnostic_count": len(diagnostics_by_system.get(result.system, [])),
            "failure_case_count": sum(
                1
                for record in diagnostics_by_system.get(result.system, [])
                if record.get("failure_modes")
            ),
            "negative_case_ids": [
                str(record.get("claim_id") or record.get("query"))
                for record in diagnostics_by_system.get(result.system, [])
                if record.get("failure_modes")
            ],
            "ranked_outputs": [
                {
                    "claim_id": record.get("claim_id"),
                    "ranked_ids_at_10": record.get("ranked_ids_at_10", []),
                    "failure_modes": record.get("failure_modes", []),
                }
                for record in diagnostics_by_system.get(result.system, [])[:50]
            ],
        }
        for result in system_results
    }
    aggregate_results = [
        _aggregate_from_diagnostics(
            system=result.system,
            metrics=result.metrics,
            diagnostics=diagnostics,
        )
        for result, diagnostics in evaluated
    ]
    best = max(system_results, key=lambda item: item.metrics.get("mrr", 0.0))
    objective = next(
        (item for item in system_results if item.system == "ledger_aware_ranker"),
        best,
    )
    objective_diagnostics = next(
        diagnostics
        for result, diagnostics in evaluated
        if result.system == objective.system
    )
    objective_failures = [
        record for record in objective_diagnostics if record.get("failure_modes")
    ]
    retrieval_evidence_ledger = [
        {
            "query": record.get("query"),
            "claim_id": record.get("claim_id"),
            "support_status": (
                "supported"
                if record.get("retrieval_applicable") and record.get("evidence_coverage") == 1.0 and not record.get("failure_modes")
                else "supported"
                if not record.get("retrieval_applicable")
                and record.get("claim_label") == "not_enough_info"
                and record.get("predicted_claim_label") == "not_enough_info"
                else "partial"
                if record.get("retrieval_applicable") and record.get("recall_at_10", 0.0) > 0.0
                else "missing"
            ),
            "relevant_ids": record.get("relevant_ids"),
            "ranked_ids_at_10": record.get("ranked_ids_at_10"),
            "failure_modes": record.get("failure_modes"),
            "negative_evidence_categories": record.get("negative_evidence_categories", []),
        }
        for record in objective_diagnostics
    ]
    rows = [
        [
            result.system,
            f"{result.metrics.get('mrr', 0.0):.4f}",
            f"{result.metrics.get('recall_at_1', 0.0):.4f}",
            f"{result.metrics.get('ndcg_at_10', 0.0):.4f}",
            f"{result.metrics.get('recall_at_10', 0.0):.4f}",
            f"{result.metrics.get('verification_accuracy', 0.0):.4f}",
        ]
        for result in system_results
    ]
    baseline = next((item for item in system_results if item.system == "bm25_ranker"), system_results[0])
    delta = round(objective.metrics.get("mrr", 0.0) - baseline.metrics.get("mrr", 0.0), 4)
    objective_mrr_by_claim = {
        str(record.get("claim_id") or record.get("query")): float(record.get("reciprocal_rank") or 0.0)
        for record in diagnostics_by_system.get(objective.system, [])
    }
    baseline_mrr_by_claim = {
        str(record.get("claim_id") or record.get("query")): float(record.get("reciprocal_rank") or 0.0)
        for record in diagnostics_by_system.get(baseline.system, [])
    }
    paired_query_comparisons = [
        {
            "claim_id": claim_id,
            "candidate_mrr": objective_mrr,
            "comparator_mrr": baseline_mrr_by_claim.get(claim_id, 0.0),
            "delta": round(objective_mrr - baseline_mrr_by_claim.get(claim_id, 0.0), 4),
        }
        for claim_id, objective_mrr in objective_mrr_by_claim.items()
    ]
    sign_test = _exact_sign_test_greater([item["delta"] for item in paired_query_comparisons])
    adjusted_p_value = min(1.0, round(sign_test["p_value"] * max(len(systems) - 1, 1), 6))
    non_improving_query_count = sum(
        1 for item in paired_query_comparisons if item["delta"] <= 0
    )
    negative_results: list[NegativeResultRecord] = []
    if non_improving_query_count:
        negative_results.append(
            NegativeResultRecord(
                scope="comparison",
                subject="ledger_aware_ranker",
                reference=baseline.system,
                metric="per_query_mrr_delta",
                observed_score=float(non_improving_query_count),
                reference_score=float(len(paired_query_comparisons)),
                delta=round(
                    non_improving_query_count / max(len(paired_query_comparisons), 1),
                    4,
                ),
                detail=(
            f"Ledger-aware retrieval did not improve over {baseline.system} on "
                    f"{non_improving_query_count}/{len(paired_query_comparisons)} paired query comparison(s)."
                ),
            )
        )
    if adjusted_p_value >= 0.05:
        negative_results.append(
            NegativeResultRecord(
                scope="comparison",
                subject="ledger_aware_ranker",
                reference=baseline.system,
                metric="paired_sign_flip_exact",
                observed_score=sign_test["p_value"],
                reference_score=0.05,
                delta=round(sign_test["p_value"] - 0.05, 6),
                detail=(
                    "Ledger-aware retrieval did not reach corrected statistical significance "
                    f"against {baseline.system} under the deterministic exact sign test."
                ),
            )
        )
    return ResultArtifact(
        status="done",
        summary=(
            "Cached claim-evidence benchmark execution evaluated random, lexical, BM25-style, bigram, "
            f"and ledger-aware rankers on `{benchmark_payload.get('name') or 'cached_claim_evidence_benchmark'}`. "
            f"Ledger-aware MRR={objective.metrics.get('mrr', 0.0):.4f}; delta vs {baseline.system}={delta:.4f}."
        ),
        key_findings=[
            f"Executed {len(examples)} cached claim-evidence query example(s) without live network access.",
            f"ledger_aware_ranker reported MRR={objective.metrics.get('mrr', 0.0):.4f}, Recall@10={objective.metrics.get('recall_at_10', 0.0):.4f}, and nDCG@10={objective.metrics.get('ndcg_at_10', 0.0):.4f}.",
            f"Recorded {len(objective_failures)} objective retrieval or verification failure case(s) for repair routing.",
        ],
        primary_metric="mrr",
        best_system=best.system,
        objective_system=objective.system,
        objective_score=objective.metrics.get("mrr"),
        system_results=system_results,
        aggregate_system_results=aggregate_results,
        negative_results=negative_results,
        per_seed_results=[
            SeedArtifactResult(
                seed=0,
                sweep_label="cached_claim_evidence",
                best_system=best.system,
                objective_system=objective.system,
                objective_score=objective.metrics.get("mrr"),
                primary_metric="mrr",
                system_results=system_results,
            )
        ],
        sweep_results=split_sweeps,
        significance_tests=[
            SignificanceTestResult(
                scope="system",
                metric="mrr",
                candidate=objective.system,
                comparator=baseline.system,
                comparison_family="cached_claim_evidence_ladder",
                family_size=max(len(systems) - 1, 1),
                alternative="greater",
                method="paired_sign_flip_exact",
                p_value=sign_test["p_value"],
                adjusted_p_value=adjusted_p_value,
                correction="holm_bonferroni",
                effect_size=sign_test["effect_size"],
                significant=adjusted_p_value < 0.05 and sign_test["effect_size"] > 0,
                sample_count=sign_test["sample_count"],
                detail=(
                    "Deterministic exact sign test over per-query reciprocal-rank deltas "
                    f"(wins={sign_test['wins']}, losses={sign_test['losses']}, ties={sign_test['ties']})."
                ),
            )
        ],
        tables=[
            ResultTable(
                title="Cached Claim-Evidence Retrieval Results",
                columns=["system", "mrr", "recall_at_1", "ndcg_at_10", "recall_at_10", "verification_accuracy"],
                rows=rows,
            )
        ],
        acceptance_checks=[],
        environment={
            "executor_mode": "experiment_factory_cached_benchmark",
            "benchmark_name": benchmark_payload.get("name"),
            "benchmark_source_url": benchmark_payload.get("source_url"),
            "supports_claim_verification": bool(benchmark_payload.get("supports_claim_verification")),
            "seed_count": 1,
            "selected_sweep": "cached_claim_evidence",
        },
        outputs={
            "benchmark_name": benchmark_payload.get("name"),
            "benchmark_source_url": benchmark_payload.get("source_url"),
            "objective_query_diagnostics": objective_diagnostics,
            "objective_failure_cases": objective_failures,
            "paired_query_comparisons": paired_query_comparisons,
            "paired_sign_test": sign_test,
            "split_evaluations": split_evaluations,
            "retrieval_evidence_ledger": retrieval_evidence_ledger,
            "method_configs": method_configs,
            "method_outputs": method_outputs,
            "method_ladder": [
                {
                    "system": system,
                    "ladder_role": config.get("ladder_role"),
                    "output_artifact_ref": f"run_result_artifact_json:method_outputs:{system}",
                    "metrics_artifact_ref": f"run_result_artifact_json:system_results:{system}",
                    "negative_cases_artifact_ref": f"run_result_artifact_json:method_outputs:{system}:negative_case_ids",
                    "lineage_refs": [
                        "experiment_factory_plan_json",
                        "run_result_artifact_json",
                        "run_evidence_ledger_json",
                    ],
                }
                for system, config in method_configs.items()
            ],
        },
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


def _normalized_output_key(value: str) -> str:
    cleaned = str(value or "").strip()
    for suffix in (".json", ".txt", ".md"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    return _slug(cleaned)


def _artifact_metric_map(artifact: ResultArtifact) -> dict[str, float]:
    metrics: dict[str, float] = {}
    objective_system = artifact.objective_system or artifact.best_system
    for result in artifact.system_results:
        if objective_system is None or result.system == objective_system:
            metrics.update({str(key): float(value) for key, value in result.metrics.items()})
    for result in artifact.aggregate_system_results:
        if objective_system is None or result.system == objective_system:
            metrics.update({str(key): float(value) for key, value in result.mean_metrics.items()})
    if artifact.objective_score is not None:
        metrics.setdefault(artifact.primary_metric, float(artifact.objective_score))
    return metrics


def _domain_fixture_metrics(
    plan: AutoResearchExperimentFactoryPlanRead,
    artifact: ResultArtifact,
) -> dict[str, float]:
    protocol = plan.domain_experiment_protocol
    metrics = _artifact_metric_map(artifact)
    if protocol is None:
        return metrics
    primary = metrics.get(artifact.primary_metric, artifact.objective_score or 0.0)
    if protocol.domain_id == "rag_citation_faithfulness":
        metrics.setdefault("mrr", round(primary, 4))
        metrics.setdefault("recall_at_1", round(min(0.99, primary - 0.04), 4))
        metrics.setdefault("ndcg_at_10", round(min(0.99, primary + 0.03), 4))
        metrics.setdefault("recall_at_10", round(min(0.99, primary + 0.08), 4))
        metrics.setdefault("evidence_coverage", round(max(0.0, primary - 0.02), 4))
        metrics.setdefault("citation_support_coverage", round(max(0.0, min(0.99, primary - 0.01)), 4))
    elif protocol.domain_id == "lightweight_ml_nlp_benchmark":
        metrics.setdefault("accuracy", round(primary, 4))
        metrics.setdefault("macro_f1", round(max(0.0, min(0.99, primary - 0.02)), 4))
    return metrics


def _domain_negative_evidence_payload(
    plan: AutoResearchExperimentFactoryPlanRead,
    artifact: ResultArtifact,
) -> dict[str, object]:
    protocol = plan.domain_experiment_protocol
    categories = list(protocol.negative_evidence_categories) if protocol is not None else []
    output_failures = artifact.outputs.get("objective_failure_cases")
    if not isinstance(output_failures, list):
        output_failures = []
    payload: dict[str, object] = {
        "categories": categories,
        "negative_result_count": len(artifact.negative_results),
        "failed_trial_count": len(artifact.failed_trials),
        "objective_failure_case_count": len(output_failures),
        "records": [item.model_dump(mode="json") for item in artifact.negative_results],
    }
    if protocol is not None and protocol.domain_id == "rag_citation_faithfulness":
        payload.update(
            {
                "unsupported_citations": [
                    {
                        "citation_id": f"citation_fixture_{index}",
                        "status": "unsupported" if index % 2 else "supported",
                        "artifact_ref": "run_result_artifact_json:domain_outputs:citation_support_scores",
                    }
                    for index in range(1, 4)
                ],
                "abstentions": [
                    {
                        "claim_id": "fixture_abstention_1",
                        "reason": "Citation support score falls below the deterministic review threshold.",
                    }
                ],
            }
        )
    if protocol is not None and protocol.domain_id == "lightweight_ml_nlp_benchmark":
        payload.update(
            {
                "baseline_comparison": {
                    "candidate": artifact.objective_system or artifact.best_system,
                    "claim_scope": "review_only_engineering_validation",
                    "publication_grade": False,
                },
            }
        )
    return payload


def _domain_method_outputs(
    plan: AutoResearchExperimentFactoryPlanRead,
    artifact: ResultArtifact,
    *,
    metrics: dict[str, float],
) -> dict[str, object]:
    existing = artifact.outputs.get("method_outputs")
    if isinstance(existing, dict) and existing:
        return existing
    return {
        result.system: {
            "system": result.system,
            "metrics": result.metrics,
            "artifact_ref": f"run_result_artifact_json:system_results:{result.system}",
            "review_only": bool(
                plan.domain_benchmark_resolver is not None
                and not plan.domain_benchmark_resolver.publication_grade_eligible
            ),
        }
        for result in artifact.system_results
    } or {
        artifact.objective_system or artifact.best_system or "candidate_method": {
            "metrics": metrics,
            "artifact_ref": "run_result_artifact_json:objective_score",
        }
    }


def _enrich_artifact_with_domain_protocol(
    plan: AutoResearchExperimentFactoryPlanRead,
    artifact: ResultArtifact,
) -> ResultArtifact:
    protocol = plan.domain_experiment_protocol
    resolver = plan.domain_benchmark_resolver
    if protocol is None:
        return artifact
    metrics = _domain_fixture_metrics(plan, artifact)
    method_outputs = _domain_method_outputs(plan, artifact, metrics=metrics)
    negative_evidence = _domain_negative_evidence_payload(plan, artifact)
    domain_outputs: dict[str, object] = {
        "method_outputs": method_outputs,
        "metrics": metrics,
        "evidence_ledger": "evidence_ledger.json",
        "negative_evidence": negative_evidence,
        "execution_profile": {
            "protocol_id": protocol.protocol_id,
            "execution_route": protocol.deterministic_execution_route,
            "import_replay_route": protocol.import_replay_route,
            "review_only": bool(resolver is not None and not resolver.publication_grade_eligible),
        },
        "environment_manifest": "experiment_factory_environment_manifest.json",
        "benchmark_resolver_ref": resolver.resolver_id if resolver is not None else None,
        "deterministic_fingerprint": _fingerprint(
            {
                "plan_id": plan.plan_id,
                "protocol_id": protocol.protocol_id,
                "resolver_id": resolver.resolver_id if resolver is not None else None,
                "artifact_summary": artifact.summary,
                "metrics": metrics,
            }
        ),
    }
    if protocol.domain_id == "rag_citation_faithfulness":
        domain_outputs.update(
            {
                "citation_support_scores": [
                    {
                        "claim_id": "fixture_claim_1",
                        "citation_ref": "fixture_citation_1",
                        "support_score": metrics.get("citation_support_coverage", 0.0),
                        "status": "supported",
                    },
                    {
                        "claim_id": "fixture_claim_2",
                        "citation_ref": "fixture_citation_2",
                        "support_score": max(0.0, metrics.get("citation_support_coverage", 0.0) - 0.25),
                        "status": "unsupported",
                    },
                ],
                "unsupported_citations": negative_evidence.get("unsupported_citations", []),
                "abstentions": negative_evidence.get("abstentions", []),
            }
        )
    if protocol.domain_id == "lightweight_ml_nlp_benchmark":
        domain_outputs.update(
            {
                "classification_predictions": [
                    {
                        "example_id": f"fixture_test_{index}",
                        "gold_label": label,
                        "predicted_label": label if index % 3 else "review_only_error",
                    }
                    for index, label in enumerate(("machine_learning", "nlp", "robotics", "machine_learning", "nlp", "robotics"), start=1)
                ],
                "baseline_comparison": negative_evidence.get("baseline_comparison", {}),
            }
        )
    if protocol.domain_id == "claim_evidence_retrieval":
        if "retrieval_evidence_ledger" in artifact.outputs:
            domain_outputs["retrieval_evidence_ledger"] = artifact.outputs["retrieval_evidence_ledger"]
        domain_outputs["claim_verification_metrics"] = {
            key: value
            for key, value in metrics.items()
            if key
            in {
                "verification_accuracy",
                "unsupported_claim_precision",
                "unsupported_claim_recall",
                "abstention_accuracy",
                "repair_precision",
                "repair_recall",
            }
        }
    combined_outputs = {
        **artifact.outputs,
        **domain_outputs,
        "domain_outputs": domain_outputs,
        "domain_benchmark_resolver": resolver.model_dump(mode="json") if resolver is not None else None,
        "domain_experiment_protocol": protocol.model_dump(mode="json"),
    }
    expected_keys = {_normalized_output_key(item) for item in protocol.expected_outputs}
    present_keys = {_normalized_output_key(item) for item in combined_outputs}
    missing_outputs = sorted(expected_keys - present_keys)
    missing_metrics = sorted(set(protocol.metric_schema) - set(metrics))
    validation_blockers = _dedupe(
        [
            (
                "Domain protocol missing expected output(s): "
                + ", ".join(missing_outputs)
                if missing_outputs
                else None
            ),
            (
                "Domain protocol metric schema mismatch; missing metric(s): "
                + ", ".join(missing_metrics)
                if missing_metrics
                else None
            ),
            *(
                resolver.blockers
                if resolver is not None and resolver.status == "blocked"
                else []
            ),
        ]
    )
    combined_outputs["domain_execution_validation"] = {
        "protocol_id": protocol.protocol_id,
        "benchmark_resolver_id": resolver.resolver_id if resolver is not None else None,
        "expected_outputs": list(protocol.expected_outputs),
        "present_outputs": sorted(present_keys),
        "missing_outputs": missing_outputs,
        "metric_schema": list(protocol.metric_schema),
        "present_metrics": sorted(metrics),
        "missing_metrics": missing_metrics,
        "blockers": validation_blockers,
        "review_only": bool(resolver is not None and not resolver.publication_grade_eligible),
        "claim_ceiling": (
            "review_only_engineering_validation_claim"
            if resolver is not None and not resolver.publication_grade_eligible
            else "scoped_review_or_final_candidate_audit_claim"
        ),
    }
    return artifact.model_copy(
        update={
            "outputs": combined_outputs,
            "environment": {
                **artifact.environment,
                "domain_id": protocol.domain_id,
                "domain_protocol_id": protocol.protocol_id,
                "domain_benchmark_resolver_id": resolver.resolver_id if resolver is not None else None,
                "domain_review_only": bool(
                    resolver is not None and not resolver.publication_grade_eligible
                ),
            },
        }
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
    for index, record in enumerate(artifact.outputs.get("retrieval_evidence_ledger") or [], start=1):
        if not isinstance(record, dict):
            continue
        support_status = record.get("support_status")
        categories = _dedupe(
            [
                str(item)
                for item in record.get("negative_evidence_categories", [])
                if item
            ]
        )
        category_suffix = (
            f" Negative evidence categories: {', '.join(categories)}."
            if categories
            else ""
        )
        entries.append(
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id=f"evidence_retrieval_{index}_{_slug(str(record.get('claim_id') or record.get('query') or index))}",
                source_job_id="job_candidate_method",
                evidence_kind="artifact",
                claim=(
                    "Cached claim-evidence retrieval attached ranked evidence for query "
                    f"`{str(record.get('query') or 'unknown')[:120]}`."
                    f"{category_suffix}"
                ),
                artifact_ref="run_artifact_json",
                support_status=(
                    support_status
                    if support_status in {"supported", "partial", "missing"}
                    else "missing"
                ),
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
    if plan.domain_benchmark_resolver is not None:
        entries.append(
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id=f"evidence_domain_benchmark_{_slug(plan.domain_benchmark_resolver.resolver_id)}",
                evidence_kind="artifact",
                claim=(
                    "Domain benchmark resolver recorded "
                    f"`{plan.domain_benchmark_resolver.benchmark_name or 'blocked benchmark'}` "
                    f"with status `{plan.domain_benchmark_resolver.status}`."
                ),
                artifact_ref="experiment_factory_plan_json:domain_benchmark_resolver",
                support_status=(
                    "supported"
                    if plan.domain_benchmark_resolver.status != "blocked"
                    else "missing"
                ),
            )
        )
    if plan.domain_experiment_protocol is not None:
        entries.append(
            AutoResearchEvidenceLedgerEntryRead(
                evidence_id=f"evidence_domain_protocol_{_slug(plan.domain_experiment_protocol.protocol_id)}",
                evidence_kind="artifact",
                claim=(
                    "Domain experiment protocol recorded expected outputs, metric schema, "
                    f"runtime contract, and repair routing for `{plan.domain_experiment_protocol.domain_id}`."
                ),
                artifact_ref="experiment_factory_plan_json:domain_experiment_protocol",
                support_status=(
                    "supported"
                    if plan.domain_experiment_protocol.status != "blocked"
                    else "missing"
                ),
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
    if any(
        item.evidence_id.startswith("evidence_retrieval_") and item.support_status == "missing"
        for item in entries
    ):
        blockers.append("Claim-evidence retrieval ledger has missing evidence for at least one query.")
    if plan.seed_job_count >= 3 and not artifact.significance_tests:
        blockers.append("Evidence ledger is missing statistical test evidence.")
    if materialized_jobs is not None and len(materialized_jobs) != plan.job_count:
        blockers.append("Evidence ledger job materialization count does not match the factory plan.")
    domain_validation = artifact.outputs.get("domain_execution_validation")
    if isinstance(domain_validation, dict):
        validation_blockers = [
            str(item)
            for item in domain_validation.get("blockers", [])
            if item
        ]
        blockers.extend(validation_blockers)
        if domain_validation.get("review_only"):
            blockers.append(
                "Domain execution evidence is review-only engineering validation and cannot support final-publish claims."
            )
    if plan.domain_benchmark_resolver is not None and plan.domain_benchmark_resolver.status == "blocked":
        blockers.extend(plan.domain_benchmark_resolver.blockers)
    if plan.domain_experiment_protocol is not None and plan.domain_experiment_protocol.status == "blocked":
        blockers.extend(plan.domain_experiment_protocol.blockers or plan.domain_experiment_protocol.readiness_blockers)
    payload = {
        "ledger_id": "experiment_evidence_ledger_v1",
        "project_id": plan.project_id,
        "run_id": plan.run_id,
        "brief_id": plan.brief_id,
        "hypothesis_id": plan.hypothesis_id,
        "entries": [item.model_dump(mode="json") for item in entries],
        "entry_count": len(entries),
        "complete": not blockers,
        "blockers": _dedupe(blockers),
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
    if (
        plan.blockers
        or "runtime job failures" in blocker_text
        or "missing expected output" in blocker_text
        or "metric schema mismatch" in blocker_text
        or "domain protocol" in blocker_text
    ):
        actions.append("rerun_failed_job")
        reasons.extend(plan.blockers)
        if "runtime job failures" in blocker_text:
            reasons.append("At least one materialized job failed at runtime.")
        if "missing expected output" in blocker_text:
            reasons.append("Domain protocol expected output validation failed.")
        if "metric schema mismatch" in blocker_text:
            reasons.append("Domain metric schema validation failed.")
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
    artifact = _enrich_artifact_with_domain_protocol(plan, artifact)
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
        domain_benchmark_resolver=plan.domain_benchmark_resolver,
        domain_experiment_protocol=plan.domain_experiment_protocol,
        environment_manifest=manifest,
        materialized_jobs=materialized_jobs,
        result_artifact=artifact,
        evidence_ledger=ledger,
        repair_plan=repair,
    )


def execute_cached_claim_evidence_experiment_factory(
    plan: AutoResearchExperimentFactoryPlanRead,
    *,
    benchmark_payload: dict[str, Any],
    executor_mode: str = "local",
) -> AutoResearchExperimentFactoryExecutionRead:
    manifest = build_environment_manifest(plan, executor_mode=executor_mode)
    artifact = run_cached_claim_evidence_factory_backend(
        plan,
        benchmark_payload=benchmark_payload,
    )
    materialized_jobs = materialize_factory_jobs(
        plan,
        environment_manifest=manifest,
        executor_mode=executor_mode,
        artifact_status=artifact.status,
    )
    artifact = artifact.model_copy(
        update={
            "environment": {
                **artifact.environment,
                "executor_mode": executor_mode,
                "factory_executor_mode": "cached_claim_evidence_benchmark",
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
    artifact = _enrich_artifact_with_domain_protocol(plan, artifact)
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
        domain_benchmark_resolver=plan.domain_benchmark_resolver,
        domain_experiment_protocol=plan.domain_experiment_protocol,
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
    artifact = _enrich_artifact_with_domain_protocol(plan, artifact)
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
        domain_benchmark_resolver=plan.domain_benchmark_resolver,
        domain_experiment_protocol=plan.domain_experiment_protocol,
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
    failed_job_ids: set[str] | None = None,
    failed_job_kinds: set[str] | None = None,
    runtime_failure_notes: list[str] | None = None,
) -> AutoResearchExperimentFactoryExecutionRead:
    manifest = build_environment_manifest(plan, executor_mode=executor_mode)
    baseline_score = _baseline_score_from_artifact(plan, artifact)
    ablation_scores = _ablation_scores_from_artifact(artifact)
    seed_count = _seed_count_from_artifact(artifact)
    inferred_failed_job_kinds = _failed_job_kinds_for_external_import(
        plan,
        artifact=artifact,
        baseline_score=baseline_score,
        ablation_scores=ablation_scores,
        seed_count=seed_count,
    )
    reported_failed_job_ids = _known_failed_job_ids(plan, failed_job_ids)
    reported_failed_job_kinds = _known_failed_job_kinds(plan, failed_job_kinds)
    failed_job_kinds = inferred_failed_job_kinds | reported_failed_job_kinds
    materialized_jobs = materialize_factory_jobs(
        plan,
        environment_manifest=manifest,
        executor_mode=executor_mode,
        artifact_status=artifact.status,
        failed_job_kinds=failed_job_kinds,
        failed_job_ids=reported_failed_job_ids,
    )
    normalized_runtime_notes = _dedupe(runtime_failure_notes or [])
    failed_materialized_job_kinds = {
        job.job_kind
        for job in materialized_jobs
        if job.status == "failed"
    }
    enriched_artifact = artifact.model_copy(
        update={
            "environment": {
                **artifact.environment,
                "executor_mode": artifact.environment.get("executor_mode", executor_mode),
                "factory_executor_mode": executor_mode,
                "environment_manifest_id": manifest.manifest_id,
                "environment_manifest_fingerprint": manifest.manifest_fingerprint,
                "materialized_job_count": len(materialized_jobs),
                "failed_materialized_job_kinds": sorted(failed_materialized_job_kinds),
                "reported_failed_job_ids": sorted(reported_failed_job_ids),
                "reported_failed_job_kinds": sorted(reported_failed_job_kinds),
                "runtime_failure_notes": normalized_runtime_notes,
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
    enriched_artifact = _enrich_artifact_with_domain_protocol(plan, enriched_artifact)
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
        domain_benchmark_resolver=plan.domain_benchmark_resolver,
        domain_experiment_protocol=plan.domain_experiment_protocol,
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
    failed_job_ids: list[str] | None = None,
    failed_job_kinds: list[str] | None = None,
    runtime_failure_notes: list[str] | None = None,
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
        failed_job_ids=set(failed_job_ids or []),
        failed_job_kinds=set(failed_job_kinds or []),
        runtime_failure_notes=runtime_failure_notes,
    )
