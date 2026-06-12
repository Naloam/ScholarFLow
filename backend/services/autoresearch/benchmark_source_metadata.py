from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schemas.autoresearch import AutoResearchRunRead, ExperimentSpec
from services.autoresearch.benchmarks import build_experiment_spec
from services.autoresearch.ingestion import BenchmarkIngestionError, resolve_benchmark


@dataclass(frozen=True)
class MaterializedBenchmarkSource:
    spec: ExperimentSpec
    payload: dict[str, Any]


def materialize_file_backed_benchmark_source(
    run: AutoResearchRunRead,
) -> MaterializedBenchmarkSource | None:
    source = run.benchmark
    if run.spec is not None or source is None or source.kind == "builtin" or not source.file_path:
        return None
    if not Path(source.file_path).is_file():
        return None
    try:
        benchmark = resolve_benchmark(
            topic=run.topic,
            task_family_hint=run.task_family or source.task_family_hint,
            benchmark_source=source,
        )
        spec = build_experiment_spec(benchmark.task_family, benchmark)
    except (BenchmarkIngestionError, OSError, ValueError, TypeError, KeyError):
        return None
    return MaterializedBenchmarkSource(spec=spec, payload=dict(benchmark.payload))
