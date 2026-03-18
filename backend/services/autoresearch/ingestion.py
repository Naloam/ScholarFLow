from __future__ import annotations

import csv
import io
import json
from pathlib import PurePosixPath
from typing import Any

import httpx

from schemas.autoresearch import BenchmarkSource, TaskFamily
from services.autoresearch.benchmarks import ResolvedBenchmark, builtin_benchmark, infer_task_family


class BenchmarkIngestionError(RuntimeError):
    pass


def _fetch_remote_text(url: str) -> str:
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _default_name(source: BenchmarkSource) -> str:
    if source.name:
        return source.name
    if source.url:
        return PurePosixPath(source.url.split("?", 1)[0]).name or "remote_benchmark"
    return "builtin_benchmark"


def _rows_from_csv(text: str) -> list[dict[str, Any]]:
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _rows_from_jsonl(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _rows_from_json(text: str) -> Any:
    return json.loads(text)


def _partition_rows(rows: list[dict[str, Any]], source: BenchmarkSource) -> tuple[list[dict], list[dict]]:
    if not rows:
        raise BenchmarkIngestionError("Remote benchmark returned zero rows")
    if source.split_field:
        train_values = {value.lower() for value in source.train_split_values}
        test_values = {value.lower() for value in source.test_split_values}
        train_rows = [
            row for row in rows if str(row.get(source.split_field, "")).lower() in train_values
        ]
        test_rows = [
            row for row in rows if str(row.get(source.split_field, "")).lower() in test_values
        ]
        if train_rows and test_rows:
            return train_rows, test_rows

    test_ratio = min(max(source.test_ratio, 0.1), 0.5)
    test_size = max(1, int(len(rows) * test_ratio))
    if len(rows) - test_size < 2:
        raise BenchmarkIngestionError("Remote benchmark needs at least two training rows after split")
    return rows[:-test_size], rows[-test_size:]


def _limit_rows(rows: list[dict[str, Any]], source: BenchmarkSource) -> list[dict[str, Any]]:
    if source.limit_rows is None or source.limit_rows <= 0:
        return rows
    return rows[: source.limit_rows]


def _normalize_text_dataset(
    source: BenchmarkSource,
    rows: list[dict[str, Any]],
    name: str,
) -> dict[str, Any]:
    text_field = source.text_field or "text"
    label_field = source.label_field or "label"
    usable = [
        row
        for row in _limit_rows(rows, source)
        if str(row.get(text_field, "")).strip() and str(row.get(label_field, "")).strip()
    ]
    train_rows, test_rows = _partition_rows(usable, source)
    train = [{"text": str(row[text_field]), "label": str(row[label_field])} for row in train_rows]
    test = [{"text": str(row[text_field]), "label": str(row[label_field])} for row in test_rows]
    labels = sorted({item["label"] for item in train + test})
    if len(labels) < 2:
        raise BenchmarkIngestionError("Text benchmark needs at least two labels")
    return {
        "name": name,
        "description": f"Remote text classification benchmark pulled from {source.url}",
        "train": train,
        "test": test,
        "label_space": labels,
        "source_url": source.url,
    }


def _infer_feature_fields(rows: list[dict[str, Any]], label_field: str, split_field: str | None) -> list[str]:
    if not rows:
        return []
    sample = rows[0]
    fields = []
    for key, value in sample.items():
        if key in {label_field, split_field}:
            continue
        try:
            float(value)
        except Exception:
            continue
        fields.append(key)
    return fields


def _normalize_tabular_dataset(
    source: BenchmarkSource,
    rows: list[dict[str, Any]],
    name: str,
) -> dict[str, Any]:
    label_field = source.label_field or "label"
    feature_fields = source.feature_fields or _infer_feature_fields(rows, label_field, source.split_field)
    if not feature_fields:
        raise BenchmarkIngestionError("Tabular benchmark needs numeric feature_fields")
    usable: list[dict[str, Any]] = []
    for row in _limit_rows(rows, source):
        label = str(row.get(label_field, "")).strip()
        if not label:
            continue
        try:
            features = [float(row[field]) for field in feature_fields]
        except Exception:
            continue
        usable.append({"features": features, "label": label, **row})
    train_rows, test_rows = _partition_rows(usable, source)
    train = [{"features": row["features"], "label": row["label"]} for row in train_rows]
    test = [{"features": row["features"], "label": row["label"]} for row in test_rows]
    labels = sorted({item["label"] for item in train + test})
    if len(labels) < 2:
        raise BenchmarkIngestionError("Tabular benchmark needs at least two labels")
    return {
        "name": name,
        "description": f"Remote tabular classification benchmark pulled from {source.url}",
        "train": train,
        "test": test,
        "feature_names": feature_fields,
        "label_space": labels,
        "source_url": source.url,
    }


def _normalize_pre_split_json(
    source: BenchmarkSource,
    payload: dict[str, Any],
    task_family: TaskFamily,
    name: str,
) -> dict[str, Any]:
    train = payload.get("train")
    test = payload.get("test")
    if not isinstance(train, list) or not isinstance(test, list):
        raise BenchmarkIngestionError("JSON benchmark must provide train/test arrays or raw rows")
    if task_family == "tabular_classification":
        feature_names = payload.get("feature_names") or source.feature_fields
        return {
            "name": payload.get("name") or name,
            "description": payload.get("description")
            or f"Remote tabular classification benchmark pulled from {source.url}",
            "train": train,
            "test": test,
            "feature_names": feature_names,
            "label_space": sorted({item["label"] for item in train + test if isinstance(item, dict)}),
            "source_url": source.url,
        }
    return {
        "name": payload.get("name") or name,
        "description": payload.get("description")
        or f"Remote text classification benchmark pulled from {source.url}",
        "train": train,
        "test": test,
        "label_space": sorted({item["label"] for item in train + test if isinstance(item, dict)}),
        "source_url": source.url,
    }


def resolve_benchmark(
    *,
    topic: str,
    task_family_hint: TaskFamily | None = None,
    benchmark_source: BenchmarkSource | None = None,
) -> ResolvedBenchmark:
    source = benchmark_source or BenchmarkSource(kind="builtin")
    task_family = infer_task_family(topic, source.task_family_hint or task_family_hint)
    if source.kind == "builtin":
        return builtin_benchmark(task_family, source)

    if not source.url:
        raise BenchmarkIngestionError("Remote benchmark requires a URL")

    raw = _fetch_remote_text(source.url)
    name = _default_name(source)
    parsed: Any
    if source.kind == "remote_csv":
        parsed = _rows_from_csv(raw)
    elif source.kind == "remote_jsonl":
        parsed = _rows_from_jsonl(raw)
    else:
        parsed = _rows_from_json(raw)

    if isinstance(parsed, dict) and "train" in parsed and "test" in parsed:
        payload = _normalize_pre_split_json(source, parsed, task_family, name)
    elif isinstance(parsed, list):
        if task_family == "tabular_classification":
            payload = _normalize_tabular_dataset(source, parsed, name)
        else:
            payload = _normalize_text_dataset(source, parsed, name)
    else:
        raise BenchmarkIngestionError("Unsupported remote benchmark payload format")

    return ResolvedBenchmark(
        source=source,
        task_family=task_family,
        payload=payload,
        benchmark_name=payload.get("name") or name,
        benchmark_description=payload.get("description")
        or f"Remote benchmark pulled from {source.url}",
    )
