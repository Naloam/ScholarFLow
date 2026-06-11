from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from schemas.autoresearch import (
    AutoResearchBenchmarkPackageValidationIssueRead,
    AutoResearchBenchmarkPackageValidationRead,
    BenchmarkSource,
    TaskFamily,
)
from services.autoresearch.benchmarks import ResolvedBenchmark, builtin_benchmark, infer_task_family


class BenchmarkIngestionError(RuntimeError):
    pass


def _fetch_remote_text(url: str) -> str:
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _fetch_remote_bytes(url: str) -> bytes:
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def _fetch_remote_json(url: str) -> dict[str, Any]:
    payload = json.loads(_fetch_remote_text(url))
    if not isinstance(payload, dict):
        raise BenchmarkIngestionError(f"Expected a JSON object from {url}")
    return payload


def _default_name(source: BenchmarkSource) -> str:
    if source.name:
        return source.name
    if source.file_path:
        return PurePosixPath(source.file_path).name or "remote_benchmark"
    if source.url:
        return PurePosixPath(source.url.split("?", 1)[0]).name or "remote_benchmark"
    if source.dataset_id:
        return source.dataset_id
    return "builtin_benchmark"


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = " ".join(str(item).split()).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_text(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validation_issue(
    issue_id: str,
    detail: str,
    *,
    field: str | None = None,
    severity: str = "error",
    blocker: bool = True,
) -> AutoResearchBenchmarkPackageValidationIssueRead:
    return AutoResearchBenchmarkPackageValidationIssueRead(
        issue_id=issue_id,
        detail=detail,
        field=field,
        severity=severity,  # type: ignore[arg-type]
        blocker=blocker,
    )


def _package_manifest_payload(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    manifest = payload.get("benchmark_package_manifest") or payload.get("package_manifest")
    if not isinstance(manifest, dict) and payload.get("schema_version") == "benchmark_package_manifest_v1":
        manifest = payload
    benchmark_payload = payload.get("benchmark") or payload.get("payload") or payload.get("dataset")
    if not isinstance(benchmark_payload, dict):
        benchmark_payload = payload
    return manifest if isinstance(manifest, dict) else None, benchmark_payload


def _split_count_from_manifest(value: Any) -> int:
    if isinstance(value, dict):
        try:
            return int(value.get("count") or value.get("sample_count") or 0)
        except (TypeError, ValueError):
            return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def validate_benchmark_package_contract(
    payload: dict[str, Any],
    *,
    raw_text: str | None = None,
    source: BenchmarkSource | None = None,
    task_family: TaskFamily | None = None,
) -> AutoResearchBenchmarkPackageValidationRead:
    manifest, benchmark_payload = _package_manifest_payload(payload)
    if manifest is None:
        issue = _validation_issue(
            "missing_package_manifest",
            "Benchmark package validation requires benchmark_package_manifest or schema_version=benchmark_package_manifest_v1.",
            field="benchmark_package_manifest",
        )
        validation_payload = {
            "schema_version": "benchmark_package_manifest_v1",
            "issues": [issue.model_dump(mode="json")],
            "blockers": [issue.detail],
        }
        return AutoResearchBenchmarkPackageValidationRead(
            issues=[issue],
            blockers=[issue.detail],
            validation_fingerprint=_fingerprint(validation_payload),
        )

    issues: list[AutoResearchBenchmarkPackageValidationIssueRead] = []
    schema_version = str(manifest.get("schema_version") or payload.get("schema_version") or "")
    if schema_version != "benchmark_package_manifest_v1":
        issues.append(
            _validation_issue(
                "unsupported_schema_version",
                "Benchmark package manifest schema_version must be benchmark_package_manifest_v1.",
                field="schema_version",
            )
        )
    dataset_id = str(manifest.get("dataset_id") or payload.get("dataset_id") or (source.dataset_id if source else "") or "")
    source_locator = str(
        manifest.get("source_locator")
        or manifest.get("source_url")
        or payload.get("source_locator")
        or payload.get("source_url")
        or (source.file_path if source and source.file_path else "")
        or (source.url if source and source.url else "")
        or ""
    )
    source_revision = str(manifest.get("revision") or manifest.get("source_revision") or payload.get("revision") or (source.revision if source else "") or "")
    source_license = str(manifest.get("license") or manifest.get("source_license") or payload.get("license") or (source.license if source else "") or "")
    for field, value, detail in [
        ("dataset_id", dataset_id, "Benchmark package requires dataset_id."),
        ("source_locator", source_locator, "Benchmark package requires source locator or frozen local file path."),
        ("revision", source_revision, "Benchmark package requires source revision/version."),
        ("license", source_license, "Benchmark package requires license or terms."),
    ]:
        if not value:
            issues.append(_validation_issue(f"missing_{field}", detail, field=field))

    expected_sha = str(
        manifest.get("content_sha256")
        or manifest.get("benchmark_sha256")
        or manifest.get("expected_content_sha256")
        or ""
    )
    actual_content_sha = _fingerprint(benchmark_payload)
    if expected_sha and expected_sha != actual_content_sha:
        issues.append(
            _validation_issue(
                "checksum_mismatch",
                "Benchmark package content checksum does not match the declared manifest hash.",
                field="content_sha256",
            )
        )
    package_sha = str(manifest.get("package_sha256") or "")
    raw_sha = _sha256_text(raw_text) if raw_text is not None else None
    if package_sha and raw_sha is not None and package_sha != raw_sha:
        issues.append(
            _validation_issue(
                "package_checksum_mismatch",
                "Benchmark package file checksum does not match package_sha256.",
                field="package_sha256",
            )
        )

    declared_splits = manifest.get("splits") or manifest.get("split_definitions") or {}
    declared_split_counts = {
        str(key): _split_count_from_manifest(value)
        for key, value in declared_splits.items()
    } if isinstance(declared_splits, dict) else {}
    actual_split_counts = {
        split: len(benchmark_payload.get(split, []))
        for split in ("train", "test", "validation", "dev")
        if isinstance(benchmark_payload.get(split), list)
    }
    split_counts = declared_split_counts or actual_split_counts
    if not actual_split_counts.get("train") or not (
        actual_split_counts.get("test")
        or actual_split_counts.get("validation")
        or actual_split_counts.get("dev")
    ):
        issues.append(
            _validation_issue(
                "missing_train_test_splits",
                "Benchmark package must include non-empty train and test/validation/dev splits.",
                field="splits",
            )
        )
    for split, declared_count in declared_split_counts.items():
        if split in actual_split_counts and declared_count != actual_split_counts[split]:
            issues.append(
                _validation_issue(
                    f"{split}_split_count_mismatch",
                    f"Declared {split} split count does not match package records.",
                    field=f"splits.{split}.count",
                )
            )

    label_schema = manifest.get("label_schema") or payload.get("label_schema") or {}
    query_schema = (
        manifest.get("query_document_evidence_schema")
        or payload.get("query_document_evidence_schema")
        or {}
    )
    metric_compatibility = manifest.get("metric_compatibility") or {}
    source_independence = manifest.get("source_independence") or {}
    if not isinstance(label_schema, dict) or not label_schema:
        issues.append(
            _validation_issue(
                "missing_label_schema",
                "Benchmark package requires an explicit label/target schema.",
                field="label_schema",
            )
        )
    if task_family == "ir_reranking" and (not isinstance(query_schema, dict) or not query_schema):
        issues.append(
            _validation_issue(
                "missing_query_document_evidence_schema",
                "IR benchmark packages require query/document/evidence schema coverage.",
                field="query_document_evidence_schema",
            )
        )
    if not isinstance(metric_compatibility, dict) or not metric_compatibility:
        issues.append(
            _validation_issue(
                "missing_metric_compatibility",
                "Benchmark package requires metric compatibility metadata.",
                field="metric_compatibility",
            )
        )
    if not isinstance(source_independence, dict) or "ready" not in source_independence:
        issues.append(
            _validation_issue(
                "missing_source_independence",
                "Benchmark package requires source-independence metadata, even when not ready.",
                field="source_independence",
            )
        )

    blockers = [issue.detail for issue in issues if issue.blocker and issue.severity == "error"]
    warnings = [issue.detail for issue in issues if issue.severity == "warning"]
    sample_count = sum(actual_split_counts.values())
    validation_payload = {
        "schema_version": schema_version or "benchmark_package_manifest_v1",
        "dataset_id": dataset_id,
        "source_locator": source_locator,
        "source_revision": source_revision,
        "source_license": source_license,
        "package_sha256": raw_sha or package_sha or actual_content_sha,
        "expected_sha256": expected_sha or package_sha or None,
        "source_fingerprint": str(manifest.get("source_fingerprint") or actual_content_sha),
        "source_content_origin": str(manifest.get("source_content_origin") or payload.get("source_content_origin") or "imported_real"),
        "split_counts": split_counts,
        "sample_count": sample_count,
        "label_schema": label_schema if isinstance(label_schema, dict) else {},
        "query_document_evidence_schema": query_schema if isinstance(query_schema, dict) else {},
        "metric_compatibility": metric_compatibility if isinstance(metric_compatibility, dict) else {},
        "source_independence": source_independence if isinstance(source_independence, dict) else {},
        "publication_grade_eligible": not blockers and sample_count >= 20,
        "final_candidate_eligible": not blockers and sample_count >= 100 and bool(
            source_independence.get("ready") if isinstance(source_independence, dict) else False
        ),
        "valid": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "issues": [issue.model_dump(mode="json") for issue in issues],
    }
    return AutoResearchBenchmarkPackageValidationRead(
        **validation_payload,
        validation_fingerprint=_fingerprint(validation_payload),
    )


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


def _rows_from_arff(text: str) -> tuple[list[dict[str, Any]], list[dict[str, str]], str | None]:
    relation: str | None = None
    attributes: list[dict[str, str]] = []
    data_lines: list[str] = []
    in_data = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%"):
            continue
        lowered = line.lower()
        if lowered.startswith("@relation"):
            parts = line.split(None, 1)
            relation = parts[1].strip().strip("'\"") if len(parts) > 1 else None
            continue
        if lowered.startswith("@attribute"):
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            name = parts[1].strip().strip("'\"")
            attr_type = parts[2].strip()
            attributes.append({"name": name, "type": attr_type})
            continue
        if lowered.startswith("@data"):
            in_data = True
            continue
        if in_data:
            data_lines.append(raw_line)

    rows: list[dict[str, Any]] = []
    if not attributes:
        return rows, attributes, relation
    reader = csv.reader(io.StringIO("\n".join(data_lines)))
    for values in reader:
        if not values or (values[0].strip().startswith("%")):
            continue
        if len(values) < len(attributes):
            values = values + [""] * (len(attributes) - len(values))
        row = {
            attribute["name"]: value.strip()
            for attribute, value in zip(attributes, values, strict=False)
        }
        rows.append(row)
    return rows, attributes, relation


def _parser_for_path(path: str):
    lower = path.lower()
    if lower.endswith(".csv"):
        return _rows_from_csv
    if lower.endswith(".jsonl"):
        return _rows_from_jsonl
    return _rows_from_json


def _rows_from_parquet_bytes(payload: bytes) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - depends on optional runtime extra
        raise BenchmarkIngestionError(
            "Direct parquet reads require pyarrow; use datasets-server-backed discovery or install pyarrow"
        ) from exc

    try:
        table = pq.read_table(io.BytesIO(payload))
    except Exception as exc:  # pragma: no cover - exercised via adapter-level errors
        raise BenchmarkIngestionError(f"Unable to decode parquet benchmark payload: {exc}") from exc

    rows = table.to_pylist()
    if not isinstance(rows, list):
        raise BenchmarkIngestionError("Parquet benchmark did not decode into a row list")
    return [row for row in rows if isinstance(row, dict)]


def _load_remote_payload(path: str, url: str) -> Any:
    if path.lower().endswith(".parquet"):
        return _rows_from_parquet_bytes(_fetch_remote_bytes(url))
    return _parser_for_path(path)(_fetch_remote_text(url))


def _normalize_text_rows(
    source: BenchmarkSource,
    rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    text_field = source.text_field or "text"
    label_field = source.label_field or "label"
    return [
        {"text": str(row[text_field]), "label": str(row[label_field])}
        for row in rows
        if str(row.get(text_field, "")).strip() and str(row.get(label_field, "")).strip()
    ]


def _normalize_tabular_rows(
    source: BenchmarkSource,
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    label_field = source.label_field or "label"
    feature_fields = source.feature_fields or _infer_feature_fields(rows, label_field, source.split_field)
    if not feature_fields:
        raise BenchmarkIngestionError("Tabular benchmark needs numeric feature_fields")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        label = str(row.get(label_field, "")).strip()
        if not label:
            continue
        try:
            features = [float(row[field]) for field in feature_fields]
        except Exception:
            continue
        normalized.append({"features": features, "label": label})
    return normalized, feature_fields


def _source_url(source: BenchmarkSource) -> str | None:
    if source.url:
        return source.url
    if source.file_path:
        return f"file://{Path(source.file_path).resolve()}"
    if source.kind == "huggingface_file" and source.dataset_id:
        return f"https://huggingface.co/datasets/{source.dataset_id}"
    if source.kind == "openml_file" and source.dataset_id:
        return f"https://www.openml.org/search?type=data&id={source.dataset_id}"
    return None


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


def _normalize_scifact_verdict(value: Any) -> str | None:
    lowered = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if lowered in {"support", "supports", "supported", "entails", "entailment"}:
        return "supported"
    if lowered in {"refute", "refutes", "refuted", "contradict", "contradicts", "contradicted"}:
        return "refuted"
    if lowered in {"nei", "not_enough_info", "not_enough_evidence", "notenoughinfo", "unknown", "unverifiable"}:
        return "not_enough_info"
    return None


def _normalize_text_dataset(source: BenchmarkSource, rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    limited_rows = _limit_rows(rows, source)
    if source.split_field:
        train_raw, test_raw = _partition_rows(limited_rows, source)
        train = _normalize_text_rows(source, train_raw)
        test = _normalize_text_rows(source, test_raw)
    else:
        usable = _normalize_text_rows(source, limited_rows)
        train_rows, test_rows = _partition_rows(usable, source)
        train = [{"text": row["text"], "label": row["label"]} for row in train_rows]
        test = [{"text": row["text"], "label": row["label"]} for row in test_rows]
    labels = sorted({item["label"] for item in train + test})
    if len(labels) < 2:
        raise BenchmarkIngestionError("Text benchmark needs at least two labels")
    return {
        "name": name,
        "description": f"Remote text classification benchmark pulled from {_source_url(source)}",
        "train": train,
        "test": test,
        "label_space": labels,
        "source_url": _source_url(source),
    }


def _normalize_tabular_dataset(source: BenchmarkSource, rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    limited_rows = _limit_rows(rows, source)
    if source.split_field:
        train_raw, test_raw = _partition_rows(limited_rows, source)
        all_rows = train_raw + test_raw
        _, feature_fields = _normalize_tabular_rows(source, all_rows)
        feature_source = source.model_copy(update={"feature_fields": feature_fields})
        train, _ = _normalize_tabular_rows(feature_source, train_raw)
        test, _ = _normalize_tabular_rows(feature_source, test_raw)
    else:
        usable, feature_fields = _normalize_tabular_rows(source, limited_rows)
        train_rows, test_rows = _partition_rows(usable, source)
        train = [{"features": row["features"], "label": row["label"]} for row in train_rows]
        test = [{"features": row["features"], "label": row["label"]} for row in test_rows]
    labels = sorted({item["label"] for item in train + test})
    if len(labels) < 2:
        raise BenchmarkIngestionError("Tabular benchmark needs at least two labels")
    return {
        "name": name,
        "description": f"Remote tabular classification benchmark pulled from {_source_url(source)}",
        "train": train,
        "test": test,
        "feature_names": feature_fields,
        "label_space": labels,
        "source_url": _source_url(source),
    }


def _normalize_ir_row(source: BenchmarkSource, row: dict[str, Any]) -> dict[str, Any]:
    query_field = source.query_field or "query"
    candidates_field = source.candidates_field or "candidates"
    relevant_ids_field = source.relevant_ids_field or "relevant_ids"
    candidate_text_field = source.candidate_text_field or "text"
    candidate_id_field = source.candidate_id_field or "id"

    query = str(row.get(query_field, "")).strip()
    candidates = row.get(candidates_field) or []
    relevant_ids = row.get(relevant_ids_field) or []
    claim_label = _normalize_scifact_verdict(row.get("claim_label") or row.get("label") or row.get("verdict"))
    allow_empty_relevant = claim_label == "not_enough_info"
    if not query or not isinstance(candidates, list) or (not relevant_ids and not allow_empty_relevant):
        raise BenchmarkIngestionError("IR benchmark rows need query, candidates, and relevant_ids")

    normalized_candidates = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get(candidate_id_field, "")).strip()
        text = str(item.get(candidate_text_field, "")).strip()
        if candidate_id and text:
            normalized_candidates.append({"id": candidate_id, "text": text})
    if not normalized_candidates:
        raise BenchmarkIngestionError("IR benchmark candidates must include id/text")
    normalized = {
        "query": query,
        "candidates": normalized_candidates,
        "relevant_ids": [str(item) for item in relevant_ids if str(item).strip()],
    }
    for key in ("claim_id", "claim_label", "evidence_labels", "unsupported_claim"):
        if key in row:
            normalized[key] = row[key]
    if claim_label:
        normalized["claim_label"] = claim_label
        normalized["unsupported_claim"] = claim_label != "supported"
    return normalized


def _normalize_ir_dataset(source: BenchmarkSource, rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    limited_rows = _limit_rows(rows, source)
    if source.split_field:
        train_raw, test_raw = _partition_rows(limited_rows, source)
        train_rows = [_normalize_ir_row(source, row) for row in train_raw]
        test_rows = [_normalize_ir_row(source, row) for row in test_raw]
    else:
        usable = [_normalize_ir_row(source, row) for row in limited_rows]
        train_rows, test_rows = _partition_rows(usable, source)
    candidate_count = max((len(item["candidates"]) for item in train_rows + test_rows), default=0)
    return {
        "name": name,
        "description": f"Remote IR reranking benchmark pulled from {_source_url(source)}",
        "train": train_rows,
        "test": test_rows,
        "candidate_count": candidate_count,
        "source_url": _source_url(source),
    }


def _normalize_pre_split_rows(
    source: BenchmarkSource,
    train_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    task_family: TaskFamily,
    name: str,
    description: str | None = None,
) -> dict[str, Any]:
    if task_family == "tabular_classification":
        train, feature_names = _normalize_tabular_rows(source, train_rows)
        test, _ = _normalize_tabular_rows(source.model_copy(update={"feature_fields": feature_names}), test_rows)
        return {
            "name": name,
            "description": description or f"Remote tabular classification benchmark pulled from {_source_url(source)}",
            "train": train,
            "test": test,
            "feature_names": feature_names or source.feature_fields,
            "label_space": sorted({item["label"] for item in train + test}),
            "source_url": _source_url(source),
        }
    if task_family == "ir_reranking":
        normalized_train = [_normalize_ir_row(source, row) for row in train_rows if isinstance(row, dict)]
        normalized_test = [_normalize_ir_row(source, row) for row in test_rows if isinstance(row, dict)]
        return {
            "name": name,
            "description": description or f"Remote IR benchmark pulled from {_source_url(source)}",
            "train": normalized_train,
            "test": normalized_test,
            "candidate_count": max((len(item["candidates"]) for item in normalized_train + normalized_test), default=0),
            "source_url": _source_url(source),
        }
    train = _normalize_text_rows(source, train_rows)
    test = _normalize_text_rows(source, test_rows)
    return {
        "name": name,
        "description": description or f"Remote text classification benchmark pulled from {_source_url(source)}",
        "train": train,
        "test": test,
        "label_space": sorted({item["label"] for item in train + test}),
        "source_url": _source_url(source),
    }


def _normalize_pre_split_json(source: BenchmarkSource, payload: dict[str, Any], task_family: TaskFamily, name: str) -> dict[str, Any]:
    train = payload.get("train")
    test = payload.get("test")
    if not isinstance(train, list) or not isinstance(test, list):
        raise BenchmarkIngestionError("JSON benchmark must provide train/test arrays or raw rows")
    normalized = _normalize_pre_split_rows(
        source,
        [row for row in train if isinstance(row, dict)],
        [row for row in test if isinstance(row, dict)],
        task_family,
        payload.get("name") or name,
        payload.get("description"),
    )
    return _preserve_source_metadata(normalized, payload)


def _preserve_source_metadata(normalized: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "dataset_id",
        "revision",
        "license",
        "fingerprint",
        "source_dataset_id",
        "source_revision",
        "source_license",
        "source_fingerprint",
        "source_url",
        "source_locator",
        "source_splits",
        "source_class",
        "source_content_origin",
        "source_content_note",
        "source_archive_sha256",
        "supports_claim_verification",
        "verification_label_space",
        "query_document_evidence_schema",
        "publication_grade_eligibility",
        "publication_grade_blockers",
        "publication_grade",
        "final_publish_candidate_eligible",
        "final_publish_candidate_blockers",
    ):
        if key in payload:
            normalized[key] = payload[key]
    return normalized


def _normalize_dataset_payload(
    source: BenchmarkSource,
    task_family: TaskFamily,
    parsed: Any,
    name: str,
) -> dict[str, Any]:
    if isinstance(parsed, dict) and "train" in parsed and "test" in parsed:
        return _normalize_pre_split_json(source, parsed, task_family, name)
    if isinstance(parsed, list):
        if task_family == "tabular_classification":
            return _normalize_tabular_dataset(source, parsed, name)
        if task_family == "ir_reranking":
            return _normalize_ir_dataset(source, parsed, name)
        return _normalize_text_dataset(source, parsed, name)
    raise BenchmarkIngestionError("Unsupported remote benchmark payload format")


def _normalize_beir_payload(source: BenchmarkSource, payload: dict[str, Any], name: str) -> dict[str, Any]:
    if "train" in payload and "test" in payload:
        return _normalize_pre_split_json(source, payload, "ir_reranking", name)

    queries_raw = payload.get("queries") or {}
    corpus_raw = payload.get("corpus") or {}
    qrels_raw = payload.get("qrels") or {}

    queries = (
        queries_raw.items()
        if isinstance(queries_raw, dict)
        else [(str(item.get("id")), item.get("text")) for item in queries_raw if isinstance(item, dict)]
    )
    corpus = (
        corpus_raw.items()
        if isinstance(corpus_raw, dict)
        else [(str(item.get("id")), item.get("text")) for item in corpus_raw if isinstance(item, dict)]
    )
    qrels = (
        qrels_raw.items()
        if isinstance(qrels_raw, dict)
        else []
    )

    corpus_map = {doc_id: text for doc_id, text in corpus if doc_id and text}
    rows: list[dict[str, Any]] = []
    for query_id, query_text in queries:
        rels = qrels_raw.get(query_id, {}) if isinstance(qrels_raw, dict) else {}
        if not isinstance(rels, dict):
            continue
        relevant_ids = [doc_id for doc_id, score in rels.items() if float(score) > 0]
        candidate_ids = list(rels.keys())
        candidates = [{"id": doc_id, "text": corpus_map[doc_id]} for doc_id in candidate_ids if doc_id in corpus_map]
        if query_text and candidates and relevant_ids:
            rows.append({"query": query_text, "candidates": candidates, "relevant_ids": relevant_ids})
    return _preserve_source_metadata(_normalize_ir_dataset(source, rows, name), payload)


def _scifact_doc_id(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("doc_id", "id", "paper_id", "corpus_id"):
            value = item.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return str(item).strip()


def _scifact_doc_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    title = str(item.get("title") or "").strip()
    abstract = item.get("abstract") or item.get("text") or item.get("passage") or ""
    if isinstance(abstract, list):
        abstract_text = " ".join(str(part).strip() for part in abstract if str(part).strip())
    else:
        abstract_text = str(abstract).strip()
    return " ".join(part for part in (title, abstract_text) if part).strip()


def _scifact_corpus_map(payload: dict[str, Any]) -> dict[str, str]:
    corpus_raw = payload.get("corpus") or payload.get("abstracts") or payload.get("documents") or {}
    if isinstance(corpus_raw, dict):
        return {
            str(doc_id): _scifact_doc_text(item)
            for doc_id, item in corpus_raw.items()
            if str(doc_id).strip() and _scifact_doc_text(item)
        }
    if isinstance(corpus_raw, list):
        corpus: dict[str, str] = {}
        for item in corpus_raw:
            doc_id = _scifact_doc_id(item)
            text = _scifact_doc_text(item)
            if doc_id and text:
                corpus[doc_id] = text
        return corpus
    return {}


def _scifact_evidence_doc_ids(claim: dict[str, Any]) -> list[str]:
    evidence = claim.get("evidence") or claim.get("evidence_doc_ids") or {}
    doc_ids: list[str] = []
    if isinstance(evidence, dict):
        for doc_id, entries in evidence.items():
            if isinstance(entries, list):
                labels = [
                    str(entry.get("label") or entry.get("evidence_label") or "").lower()
                    for entry in entries
                    if isinstance(entry, dict)
                ]
                if labels and all(_normalize_scifact_verdict(label) == "not_enough_info" for label in labels):
                    continue
            doc_ids.append(str(doc_id))
    elif isinstance(evidence, list):
        for item in evidence:
            doc_id = _scifact_doc_id(item)
            label = _normalize_scifact_verdict(item.get("label") if isinstance(item, dict) else "")
            if doc_id and label != "not_enough_info":
                doc_ids.append(doc_id)
    return _dedupe(doc_ids)


def _scifact_claim_label(claim: dict[str, Any]) -> str | None:
    for key in ("label", "claim_label", "verdict", "classification", "gold_label"):
        label = _normalize_scifact_verdict(claim.get(key))
        if label:
            return label
    evidence = claim.get("evidence") or {}
    labels: list[str] = []
    if isinstance(evidence, dict):
        for entries in evidence.values():
            if isinstance(entries, list):
                labels.extend(
                    label
                    for entry in entries
                    if isinstance(entry, dict)
                    and (label := _normalize_scifact_verdict(entry.get("label") or entry.get("evidence_label")))
                )
    elif isinstance(evidence, list):
        labels.extend(
            label
            for entry in evidence
            if isinstance(entry, dict)
            and (label := _normalize_scifact_verdict(entry.get("label") or entry.get("evidence_label")))
        )
    if "refuted" in labels:
        return "refuted"
    if "supported" in labels:
        return "supported"
    if "not_enough_info" in labels:
        return "not_enough_info"
    return None


def _scifact_evidence_label_map(claim: dict[str, Any]) -> dict[str, str]:
    evidence = claim.get("evidence") or {}
    labels: dict[str, str] = {}
    if isinstance(evidence, dict):
        for doc_id, entries in evidence.items():
            label = None
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        label = _normalize_scifact_verdict(entry.get("label") or entry.get("evidence_label"))
                        if label:
                            break
            elif isinstance(entries, dict):
                label = _normalize_scifact_verdict(entries.get("label") or entries.get("evidence_label"))
            if label and label != "not_enough_info":
                labels[str(doc_id)] = label
    elif isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            doc_id = _scifact_doc_id(item)
            label = _normalize_scifact_verdict(item.get("label") or item.get("evidence_label"))
            if doc_id and label and label != "not_enough_info":
                labels[doc_id] = label
    return labels


def _scifact_candidate_doc_ids(claim: dict[str, Any], corpus_map: dict[str, str]) -> list[str]:
    candidates: list[str] = []
    for field in ("candidate_doc_ids", "doc_ids", "retrieved_doc_ids", "hard_negative_doc_ids"):
        raw = claim.get(field)
        if isinstance(raw, list):
            candidates.extend(str(item) for item in raw if str(item).strip())
    candidates.extend(_scifact_evidence_doc_ids(claim))
    if not candidates:
        candidates.extend(list(corpus_map)[:8])
    return _dedupe([doc_id for doc_id in candidates if doc_id in corpus_map])


def _normalize_scifact_payload(source: BenchmarkSource, payload: dict[str, Any], name: str) -> dict[str, Any]:
    if "train" in payload and "test" in payload:
        return _normalize_pre_split_json(source, payload, "ir_reranking", name)
    corpus_map = _scifact_corpus_map(payload)
    claims_raw = payload.get("claims") or payload.get("queries") or []
    if isinstance(claims_raw, dict):
        claims = [
            {"id": claim_id, **claim}
            if isinstance(claim, dict)
            else {"id": claim_id, "claim": str(claim)}
            for claim_id, claim in claims_raw.items()
        ]
    elif isinstance(claims_raw, list):
        claims = [claim for claim in claims_raw if isinstance(claim, dict)]
    else:
        claims = []
    if not corpus_map or not claims:
        raise BenchmarkIngestionError("SciFact benchmark needs corpus and claims")

    split_payload = payload.get("split") or payload.get("splits") or {}
    train_ids = {str(item) for item in split_payload.get("train", [])} if isinstance(split_payload, dict) else set()
    test_ids = {
        str(item)
        for item in (
            split_payload.get("test", []) or split_payload.get("dev", []) or split_payload.get("validation", [])
        )
    } if isinstance(split_payload, dict) else set()
    rows_by_split = {"train": [], "test": [], "unsplit": []}
    for claim in claims:
        claim_id = str(claim.get("id") or claim.get("claim_id") or "").strip()
        query = str(claim.get("claim") or claim.get("query") or "").strip()
        claim_label = _scifact_claim_label(claim)
        evidence_labels = _scifact_evidence_label_map(claim)
        relevant_ids = [doc_id for doc_id in _scifact_evidence_doc_ids(claim) if doc_id in corpus_map]
        candidate_ids = _scifact_candidate_doc_ids(claim, corpus_map)
        candidates = [{"id": doc_id, "text": corpus_map[doc_id]} for doc_id in candidate_ids]
        if not query or not candidates or (not relevant_ids and claim_label != "not_enough_info"):
            continue
        row = {
            "claim_id": claim_id,
            "query": query,
            "candidates": candidates,
            "relevant_ids": relevant_ids,
            "claim_label": claim_label,
            "evidence_labels": evidence_labels,
            "unsupported_claim": claim_label in {"refuted", "not_enough_info"},
        }
        claim_split = str(claim.get("split") or "").lower()
        if claim_id in train_ids or claim_split == "train":
            rows_by_split["train"].append(row)
        elif claim_id in test_ids or claim_split in {"test", "dev", "validation"}:
            rows_by_split["test"].append(row)
        else:
            rows_by_split["unsplit"].append(row)

    if rows_by_split["train"] and rows_by_split["test"]:
        normalized = _normalize_pre_split_rows(
            source,
            rows_by_split["train"],
            rows_by_split["test"],
            "ir_reranking",
            payload.get("name") or name,
            payload.get("description") or "SciFact-style claim-evidence retrieval benchmark.",
        )
    else:
        normalized = _normalize_ir_dataset(
            source,
            [*rows_by_split["train"], *rows_by_split["test"], *rows_by_split["unsplit"]],
            payload.get("name") or name,
        )
        normalized["description"] = payload.get("description") or "SciFact-style claim-evidence retrieval benchmark."
    normalized["source_url"] = _source_url(source)
    normalized["verification_label_space"] = sorted(
        {
            item["claim_label"]
            for item in [*normalized.get("train", []), *normalized.get("test", [])]
            if item.get("claim_label")
        }
    )
    normalized["supports_claim_verification"] = bool(normalized["verification_label_space"])
    return _preserve_source_metadata(normalized, payload)


class BenchmarkAdapter(Protocol):
    kind: str

    def load(self, source: BenchmarkSource, task_family: TaskFamily) -> ResolvedBenchmark:
        ...


class BuiltinBenchmarkAdapter:
    kind = "builtin"

    def load(self, source: BenchmarkSource, task_family: TaskFamily) -> ResolvedBenchmark:
        return builtin_benchmark(task_family, source)


class RemoteFileAdapter:
    kind = ""
    parser = staticmethod(_rows_from_json)

    def build_url(self, source: BenchmarkSource) -> str:
        if not source.url:
            raise BenchmarkIngestionError(f"{self.kind} benchmark requires a URL")
        return source.url

    def load(self, source: BenchmarkSource, task_family: TaskFamily) -> ResolvedBenchmark:
        if source.file_path:
            raw = Path(source.file_path).read_text(encoding="utf-8")
        else:
            source = source.model_copy(update={"url": self.build_url(source)})
            raw = _fetch_remote_text(source.url or "")
        name = _default_name(source)
        parsed = self.parser(raw)
        benchmark_package_validation: AutoResearchBenchmarkPackageValidationRead | None = None
        if isinstance(parsed, dict):
            manifest, benchmark_payload = _package_manifest_payload(parsed)
            if manifest is not None:
                benchmark_package_validation = validate_benchmark_package_contract(
                    parsed,
                    raw_text=raw,
                    source=source,
                    task_family=task_family,
                )
                if not benchmark_package_validation.valid:
                    raise BenchmarkIngestionError(
                        "Benchmark package validation failed: "
                        + "; ".join(benchmark_package_validation.blockers)
                    )
                parsed = {
                    **benchmark_payload,
                    "dataset_id": benchmark_package_validation.dataset_id,
                    "revision": benchmark_package_validation.source_revision,
                    "license": benchmark_package_validation.source_license,
                    "source_locator": benchmark_package_validation.source_locator,
                    "source_fingerprint": benchmark_package_validation.source_fingerprint,
                    "source_content_origin": benchmark_package_validation.source_content_origin
                    or "imported_real",
                    "source_class": "imported_real" if source.file_path else "remote_real",
                    "query_document_evidence_schema": benchmark_package_validation.query_document_evidence_schema,
                    "publication_grade": benchmark_package_validation.publication_grade_eligible,
                    "publication_grade_eligibility": benchmark_package_validation.model_dump(mode="json"),
                    "publication_grade_blockers": list(benchmark_package_validation.blockers),
                    "final_publish_candidate_eligible": benchmark_package_validation.final_candidate_eligible,
                    "final_publish_candidate_blockers": []
                    if benchmark_package_validation.final_candidate_eligible
                    else ["Benchmark package is not final-publish-candidate eligible."],
                }
        if self.kind == "beir_json":
            payload = _normalize_beir_payload(source, parsed, name)
        elif self.kind == "scifact_json":
            payload = _normalize_scifact_payload(source, parsed, name)
        else:
            payload = _normalize_dataset_payload(source, task_family, parsed, name)
        if benchmark_package_validation is not None:
            payload["benchmark_package_validation"] = benchmark_package_validation.model_dump(mode="json")

        return ResolvedBenchmark(
            source=source,
            task_family=task_family,
            payload=payload,
            benchmark_name=payload.get("name") or name,
            benchmark_description=payload.get("description") or f"Remote benchmark pulled from {source.url}",
        )


class RemoteCSVAdapter(RemoteFileAdapter):
    kind = "remote_csv"
    parser = staticmethod(_rows_from_csv)


class RemoteJSONLAdapter(RemoteFileAdapter):
    kind = "remote_jsonl"
    parser = staticmethod(_rows_from_jsonl)


class RemoteJSONAdapter(RemoteFileAdapter):
    kind = "remote_json"
    parser = staticmethod(_rows_from_json)


class HuggingFaceFileAdapter(RemoteFileAdapter):
    kind = "huggingface_file"
    datasets_server_base = "https://datasets-server.huggingface.co"
    datasets_server_page_size = 100
    datasets_server_max_rows = 200

    def _metadata_url(self, source: BenchmarkSource) -> str:
        if not source.dataset_id:
            raise BenchmarkIngestionError("huggingface_file requires dataset_id")
        return f"https://huggingface.co/api/datasets/{source.dataset_id}"

    def _resolve_path(self, source: BenchmarkSource, path: str) -> str:
        if not source.dataset_id:
            raise BenchmarkIngestionError("huggingface_file requires dataset_id")
        revision = source.revision or "main"
        return f"https://huggingface.co/datasets/{source.dataset_id}/resolve/{revision}/{path}"

    def _datasets_server_url(self, endpoint: str, source: BenchmarkSource, **params: Any) -> str:
        if not source.dataset_id:
            raise BenchmarkIngestionError("huggingface_file requires dataset_id")
        query: dict[str, Any] = {"dataset": source.dataset_id}
        query.update({key: value for key, value in params.items() if value is not None})
        return f"{self.datasets_server_base}/{endpoint}?{urlencode(query)}"

    def _choose_config(self, source: BenchmarkSource, splits: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in splits:
            config = str(entry.get("config", "")).strip() or "default"
            grouped.setdefault(config, []).append(entry)

        if source.subset:
            entries = grouped.get(source.subset)
            if entries:
                return source.subset, entries
            raise BenchmarkIngestionError(
                f"datasets-server does not expose config '{source.subset}' for dataset {source.dataset_id}"
            )

        if "default" in grouped:
            return "default", grouped["default"]

        train_markers = tuple(value.lower() for value in source.train_split_values)
        test_markers = tuple(value.lower() for value in source.test_split_values)
        for config, entries in grouped.items():
            names = [str(entry.get("split", "")).lower() for entry in entries]
            has_train = any(any(marker in name for marker in train_markers) for name in names)
            has_test = any(any(marker in name for marker in test_markers) for name in names)
            if has_train and has_test:
                return config, entries

        first_config = next(iter(grouped), None)
        if first_config is None:
            raise BenchmarkIngestionError(f"datasets-server returned no split configs for {source.dataset_id}")
        return first_config, grouped[first_config]

    def _match_split(
        self,
        entries: list[dict[str, Any]],
        markers: tuple[str, ...],
        *,
        exclude: str | None = None,
    ) -> str | None:
        for entry in entries:
            split = str(entry.get("split", "")).strip()
            if not split or split == exclude:
                continue
            split_lower = split.lower()
            if any(marker in split_lower for marker in markers):
                return split
        return None

    def _datasets_server_rows(
        self,
        source: BenchmarkSource,
        *,
        config: str,
        split: str,
        max_rows: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        target = max(1, max_rows)
        while len(rows) < target:
            page_size = min(self.datasets_server_page_size, target - len(rows))
            payload = _fetch_remote_json(
                self._datasets_server_url(
                    "rows",
                    source,
                    config=config,
                    split=split,
                    offset=offset,
                    length=page_size,
                )
            )
            page_rows_raw = payload.get("rows")
            if not isinstance(page_rows_raw, list):
                raise BenchmarkIngestionError(
                    f"datasets-server rows response for split '{split}' is missing row data"
                )
            page_rows = [
                item["row"]
                for item in page_rows_raw
                if isinstance(item, dict) and isinstance(item.get("row"), dict)
            ]
            if not page_rows:
                break
            rows.extend(page_rows)
            offset += len(page_rows)
            if len(page_rows) < page_size:
                break
            total = payload.get("num_rows_total")
            if isinstance(total, int) and offset >= total:
                break
        return rows

    def _load_via_datasets_server(
        self,
        source: BenchmarkSource,
        task_family: TaskFamily,
    ) -> ResolvedBenchmark:
        splits_payload = _fetch_remote_json(self._datasets_server_url("splits", source))
        split_entries_raw = splits_payload.get("splits")
        if not isinstance(split_entries_raw, list) or not split_entries_raw:
            raise BenchmarkIngestionError(
                f"datasets-server returned no splits for dataset {source.dataset_id}"
            )

        split_entries = [entry for entry in split_entries_raw if isinstance(entry, dict)]
        config, config_entries = self._choose_config(source, split_entries)
        train_split = self._match_split(
            config_entries,
            tuple(value.lower() for value in source.train_split_values),
        )
        test_split = self._match_split(
            config_entries,
            tuple(value.lower() for value in source.test_split_values),
            exclude=train_split,
        )
        if train_split is None:
            available = ", ".join(
                sorted({str(entry.get("split", "")).strip() for entry in config_entries if entry.get("split")})
            )
            raise BenchmarkIngestionError(
                f"datasets-server did not expose a train split for dataset {source.dataset_id} "
                f"(config={config}, available={available or 'none'})"
            )

        row_budget = source.limit_rows or self.datasets_server_max_rows
        dataset_url = f"https://huggingface.co/datasets/{source.dataset_id}"
        source = source.model_copy(update={"url": dataset_url})
        name = source.name or source.dataset_id or _default_name(source)

        if test_split:
            train_rows = self._datasets_server_rows(
                source,
                config=config,
                split=train_split,
                max_rows=row_budget,
            )
            test_rows = self._datasets_server_rows(
                source,
                config=config,
                split=test_split,
                max_rows=row_budget,
            )
            if not train_rows or not test_rows:
                raise BenchmarkIngestionError(
                    f"datasets-server returned empty rows for dataset {source.dataset_id} "
                    f"(config={config}, train={train_split}, test={test_split})"
                )
            payload = _normalize_pre_split_rows(
                source,
                train_rows,
                test_rows,
                task_family,
                name,
                f"Hugging Face dataset {source.dataset_id} loaded via datasets-server ({config}: {train_split}/{test_split}).",
            )
            payload["source_config"] = config
            payload["source_splits"] = [train_split, test_split]
        else:
            rows = self._datasets_server_rows(
                source,
                config=config,
                split=train_split,
                max_rows=max(row_budget, 8),
            )
            if not rows:
                raise BenchmarkIngestionError(
                    f"datasets-server returned no rows for dataset {source.dataset_id} "
                    f"(config={config}, split={train_split})"
                )
            payload = _normalize_dataset_payload(source, task_family, rows, name)
            payload["source_config"] = config
            payload["source_splits"] = [train_split]
        return ResolvedBenchmark(
            source=source,
            task_family=task_family,
            payload=payload,
            benchmark_name=payload.get("name") or name,
            benchmark_description=payload.get("description") or f"Remote benchmark pulled from {source.url}",
        )

    def _discover_paths(self, source: BenchmarkSource) -> tuple[str | None, str | None]:
        metadata = _fetch_remote_json(self._metadata_url(source))
        siblings = metadata.get("siblings") or []
        candidates = [
            str(item.get("rfilename", "")).strip()
            for item in siblings
            if isinstance(item, dict) and str(item.get("rfilename", "")).strip()
        ]
        if source.subset:
            subset = source.subset.strip("/")
            subset_candidates = [
                path
                for path in candidates
                if path.startswith(f"{subset}/") or f"/{subset}/" in path
            ]
            if subset_candidates:
                candidates = subset_candidates
        supported = [
            path
            for path in candidates
            if path.lower().endswith((".csv", ".jsonl", ".json", ".parquet"))
        ]
        if not supported:
            raise BenchmarkIngestionError(
                f"No supported CSV/JSON/JSONL/Parquet files were found for dataset {source.dataset_id}"
            )
        train_markers = tuple(value.lower() for value in source.train_split_values)
        test_markers = tuple(value.lower() for value in source.test_split_values)

        def _match_path(markers: tuple[str, ...]) -> str | None:
            for path in supported:
                lower = PurePosixPath(path).name.lower()
                if any(marker in lower for marker in markers):
                    return path
            return None

        train_path = _match_path(train_markers)
        test_path = _match_path(test_markers)
        if train_path and test_path and train_path != test_path:
            return train_path, test_path
        return supported[0], None

    def build_url(self, source: BenchmarkSource) -> str:
        if source.url:
            return source.url
        if source.file_path:
            return self._resolve_path(source, source.file_path)
        path, _ = self._discover_paths(source)
        if not path:
            raise BenchmarkIngestionError("Unable to resolve a file path for the Hugging Face dataset")
        return self._resolve_path(source, path)

    def load(self, source: BenchmarkSource, task_family: TaskFamily) -> ResolvedBenchmark:
        if source.file_path:
            path = source.file_path
            source = source.model_copy(update={"url": self._resolve_path(source, path)})
            parsed = _load_remote_payload(path, source.url or "")
            name = source.name or PurePosixPath(path).name or _default_name(source)
            payload = _normalize_dataset_payload(source, task_family, parsed, name)
        else:
            datasets_server_error: str | None = None
            try:
                return self._load_via_datasets_server(source, task_family)
            except BenchmarkIngestionError as exc:
                datasets_server_error = str(exc)

            try:
                train_path, test_path = self._discover_paths(source)
            except BenchmarkIngestionError as exc:
                raise BenchmarkIngestionError(
                    f"Unable to ingest Hugging Face dataset {source.dataset_id}: "
                    f"datasets-server failed ({datasets_server_error}); file discovery failed ({exc})"
                ) from exc

            if not train_path:
                raise BenchmarkIngestionError("Unable to discover supported files for the Hugging Face dataset")
            if test_path:
                train_rows = _load_remote_payload(train_path, self._resolve_path(source, train_path))
                test_rows = _load_remote_payload(test_path, self._resolve_path(source, test_path))
                if not isinstance(train_rows, list) or not isinstance(test_rows, list):
                    raise BenchmarkIngestionError("Discovered Hugging Face split files must decode into row lists")
                source = source.model_copy(update={"url": f"https://huggingface.co/datasets/{source.dataset_id}"})
                name = source.name or source.dataset_id or _default_name(source)
                payload = _normalize_pre_split_rows(
                    source,
                    [row for row in train_rows if isinstance(row, dict)],
                    [row for row in test_rows if isinstance(row, dict)],
                    task_family,
                    name,
                    f"Hugging Face dataset {source.dataset_id} using discovered split files.",
                )
                payload["source_files"] = [train_path, test_path]
            else:
                source = source.model_copy(update={"url": self._resolve_path(source, train_path)})
                parsed = _load_remote_payload(train_path, source.url or "")
                name = source.name or source.dataset_id or PurePosixPath(train_path).name or _default_name(source)
                payload = _normalize_dataset_payload(source, task_family, parsed, name)
        return ResolvedBenchmark(
            source=source,
            task_family=task_family,
            payload=payload,
            benchmark_name=payload.get("name") or name,
            benchmark_description=payload.get("description") or f"Remote benchmark pulled from {source.url}",
        )


class OpenMLFileAdapter(RemoteFileAdapter):
    kind = "openml_file"

    def _metadata_url(self, source: BenchmarkSource) -> str:
        if not source.dataset_id:
            raise BenchmarkIngestionError("openml_file requires dataset_id or url")
        return f"https://www.openml.org/api/v1/json/data/{source.dataset_id}"

    def _dataset_metadata(self, source: BenchmarkSource) -> dict[str, Any]:
        payload = _fetch_remote_json(self._metadata_url(source))
        description = payload.get("data_set_description")
        if isinstance(description, dict):
            return description
        raise BenchmarkIngestionError(f"Unexpected OpenML metadata response for dataset {source.dataset_id}")

    def build_url(self, source: BenchmarkSource) -> str:
        if source.url:
            return source.url
        metadata = self._dataset_metadata(source)
        file_id = metadata.get("file_id")
        if file_id:
            return f"https://www.openml.org/data/v1/download/{file_id}"
        if source.dataset_id:
            return f"https://www.openml.org/data/v1/download/{source.dataset_id}"
        raise BenchmarkIngestionError("Unable to resolve an OpenML download URL")

    def load(self, source: BenchmarkSource, task_family: TaskFamily) -> ResolvedBenchmark:
        metadata = self._dataset_metadata(source) if source.dataset_id and not source.url else {}
        source = source.model_copy(
            update={
                "url": self.build_url(source),
                "label_field": (
                    source.label_field
                    or str(metadata.get("default_target_attribute", "")).split(",", 1)[0].strip()
                    or source.label_field
                ),
                "name": source.name or metadata.get("name") or source.name,
            }
        )
        raw = _fetch_remote_text(source.url or "")
        name = source.name or _default_name(source)
        if (source.url or "").lower().endswith(".csv"):
            parsed = _rows_from_csv(raw)
        else:
            rows, attributes, relation = _rows_from_arff(raw)
            if not source.label_field:
                nominal = [
                    attribute["name"]
                    for attribute in attributes
                    if attribute["type"].startswith("{")
                ]
                if nominal:
                    source = source.model_copy(update={"label_field": nominal[-1]})
            parsed = rows
            if relation and not source.name:
                name = relation

        if task_family == "tabular_classification":
            payload = _normalize_tabular_dataset(source, parsed, name)
        elif task_family == "ir_reranking":
            payload = _normalize_ir_dataset(source, parsed, name)
        else:
            payload = _normalize_text_dataset(source, parsed, name)
        payload["source_dataset_id"] = source.dataset_id
        if metadata.get("version"):
            payload["source_dataset_version"] = metadata.get("version")
        return ResolvedBenchmark(
            source=source,
            task_family=task_family,
            payload=payload,
            benchmark_name=payload.get("name") or name,
            benchmark_description=payload.get("description") or f"Remote benchmark pulled from {source.url}",
        )


class BeirJSONAdapter(RemoteFileAdapter):
    kind = "beir_json"
    parser = staticmethod(_rows_from_json)


class SciFactJSONAdapter(RemoteFileAdapter):
    kind = "scifact_json"
    parser = staticmethod(_rows_from_json)


ADAPTERS: dict[str, BenchmarkAdapter] = {
    "builtin": BuiltinBenchmarkAdapter(),
    "remote_csv": RemoteCSVAdapter(),
    "remote_jsonl": RemoteJSONLAdapter(),
    "remote_json": RemoteJSONAdapter(),
    "huggingface_file": HuggingFaceFileAdapter(),
    "openml_file": OpenMLFileAdapter(),
    "beir_json": BeirJSONAdapter(),
    "scifact_json": SciFactJSONAdapter(),
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
        return builtin_benchmark(task_family, source, topic=topic)
    adapter = ADAPTERS.get(source.kind)
    if adapter is None:
        raise BenchmarkIngestionError(f"Unsupported benchmark adapter: {source.kind}")
    return adapter.load(source, task_family)
