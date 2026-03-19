from __future__ import annotations

import csv
import io
import json
from pathlib import PurePosixPath
from typing import Any, Protocol
from urllib.parse import urlencode

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
    if not query or not isinstance(candidates, list) or not relevant_ids:
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
    return {
        "query": query,
        "candidates": normalized_candidates,
        "relevant_ids": [str(item) for item in relevant_ids if str(item).strip()],
    }


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
    return _normalize_pre_split_rows(
        source,
        [row for row in train if isinstance(row, dict)],
        [row for row in test if isinstance(row, dict)],
        task_family,
        payload.get("name") or name,
        payload.get("description"),
    )


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
    return _normalize_ir_dataset(source, rows, name)


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
        source = source.model_copy(update={"url": self.build_url(source)})
        raw = _fetch_remote_text(source.url or "")
        name = _default_name(source)
        parsed = self.parser(raw)
        if self.kind == "beir_json":
            payload = _normalize_beir_payload(source, parsed, name)
        else:
            payload = _normalize_dataset_payload(source, task_family, parsed, name)

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


ADAPTERS: dict[str, BenchmarkAdapter] = {
    "builtin": BuiltinBenchmarkAdapter(),
    "remote_csv": RemoteCSVAdapter(),
    "remote_jsonl": RemoteJSONLAdapter(),
    "remote_json": RemoteJSONAdapter(),
    "huggingface_file": HuggingFaceFileAdapter(),
    "openml_file": OpenMLFileAdapter(),
    "beir_json": BeirJSONAdapter(),
}


def resolve_benchmark(
    *,
    topic: str,
    task_family_hint: TaskFamily | None = None,
    benchmark_source: BenchmarkSource | None = None,
) -> ResolvedBenchmark:
    source = benchmark_source or BenchmarkSource(kind="builtin")
    task_family = infer_task_family(topic, source.task_family_hint or task_family_hint)
    adapter = ADAPTERS.get(source.kind)
    if adapter is None:
        raise BenchmarkIngestionError(f"Unsupported benchmark adapter: {source.kind}")
    return adapter.load(source, task_family)
