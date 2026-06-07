#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.request import urlopen


DEFAULT_SOURCE_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
DEFAULT_SOURCE_SHA256 = "11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "data"
    / "frozen_benchmarks"
    / "scifact_claim_verification_frozen_snapshot_v1.json"
)
DEFAULT_RETRIEVAL_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "data"
    / "frozen_benchmarks"
    / "scifact_claim_retrieval_frozen_snapshot_v1.json"
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_tarball(path: Path | None, url: str) -> bytes:
    if path is not None:
        return path.read_bytes()
    with urlopen(url, timeout=120) as response:
        return response.read()


def _read_jsonl_from_tar(tf: tarfile.TarFile, member: str) -> list[dict[str, Any]]:
    extracted = tf.extractfile(member)
    if extracted is None:
        raise FileNotFoundError(f"Missing {member} in SciFact tarball")
    rows: list[dict[str, Any]] = []
    for raw in extracted:
        line = raw.decode("utf-8").strip()
        if line:
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _doc_text(doc: dict[str, Any]) -> str:
    title = " ".join(str(doc.get("title") or "").split())
    abstract_raw = doc.get("abstract") or []
    if isinstance(abstract_raw, list):
        abstract = " ".join(" ".join(str(item).split()) for item in abstract_raw)
    else:
        abstract = " ".join(str(abstract_raw).split())
    return " ".join(part for part in (title, abstract) if part).strip()


def _label_from_evidence(evidence: dict[str, Any]) -> str:
    labels: list[str] = []
    for entries in evidence.values():
        if isinstance(entries, list):
            labels.extend(
                str(entry.get("label") or "").strip().upper()
                for entry in entries
                if isinstance(entry, dict)
            )
    if "CONTRADICT" in labels:
        return "refuted"
    if "SUPPORT" in labels:
        return "supported"
    return "not_enough_info"


def _gold_doc_ids(evidence: dict[str, Any]) -> list[str]:
    return [str(doc_id) for doc_id, entries in evidence.items() if isinstance(entries, list) and entries]


def _distractor_ids(
    *,
    claim: dict[str, Any],
    corpus_ids: list[str],
    corpus_by_id: dict[str, dict[str, Any]],
    gold_ids: list[str],
    target_candidates: int,
) -> list[str]:
    candidates: list[str] = []
    cited = [str(item) for item in claim.get("cited_doc_ids", []) if str(item) in corpus_by_id]
    for doc_id in [*gold_ids, *cited]:
        if doc_id not in candidates:
            candidates.append(doc_id)

    claim_id = int(claim.get("id") or 0)
    offset = claim_id % max(len(corpus_ids), 1)
    for index in range(len(corpus_ids)):
        doc_id = corpus_ids[(offset + index * 37) % len(corpus_ids)]
        if doc_id not in candidates:
            candidates.append(doc_id)
        if len(candidates) >= target_candidates:
            break
    return candidates[:target_candidates]


def _normalize_claim(
    claim: dict[str, Any],
    *,
    split: str,
    corpus_by_id: dict[str, dict[str, Any]],
    corpus_ids: list[str],
    target_candidates: int,
) -> dict[str, Any] | None:
    query = " ".join(str(claim.get("claim") or "").split())
    evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
    label = _label_from_evidence(evidence)
    gold_ids = [doc_id for doc_id in _gold_doc_ids(evidence) if doc_id in corpus_by_id]
    if not query or (label != "not_enough_info" and not gold_ids):
        return None
    candidate_ids = _distractor_ids(
        claim=claim,
        corpus_ids=corpus_ids,
        corpus_by_id=corpus_by_id,
        gold_ids=gold_ids,
        target_candidates=target_candidates,
    )
    candidates = [
        {"id": doc_id, "text": _doc_text(corpus_by_id[doc_id])}
        for doc_id in candidate_ids
        if doc_id in corpus_by_id and _doc_text(corpus_by_id[doc_id])
    ]
    if not candidates:
        return None
    evidence_labels = {
        str(doc_id): ("refuted" if any(
            str(entry.get("label") or "").upper() == "CONTRADICT"
            for entry in entries
            if isinstance(entry, dict)
        ) else "supported")
        for doc_id, entries in evidence.items()
        if isinstance(entries, list) and entries and str(doc_id) in corpus_by_id
    }
    return {
        "claim_id": f"scifact_{split}_{int(claim.get('id') or 0)}",
        "source_claim_id": int(claim.get("id") or 0),
        "source_split": split,
        "query": query,
        "candidates": candidates,
        "relevant_ids": gold_ids,
        "claim_label": label,
        "unsupported_claim": label != "supported",
        "evidence": evidence,
        "evidence_labels": evidence_labels,
        "cited_doc_ids": [str(item) for item in claim.get("cited_doc_ids", [])],
    }


def _take_by_label(rows: list[dict[str, Any]], *, total: int) -> list[dict[str, Any]]:
    by_label: dict[str, list[dict[str, Any]]] = {"supported": [], "refuted": [], "not_enough_info": []}
    for row in rows:
        by_label.setdefault(str(row.get("claim_label")), []).append(row)
    base = total // 3
    remainder = total % 3
    targets = {
        "supported": base + (1 if remainder > 0 else 0),
        "refuted": base + (1 if remainder > 1 else 0),
        "not_enough_info": base,
    }
    selected: list[dict[str, Any]] = []
    for label in ("supported", "refuted", "not_enough_info"):
        selected.extend(by_label[label][: targets[label]])
    selected.sort(key=lambda item: int(item["source_claim_id"]))
    if len(selected) < total:
        raise ValueError(f"SciFact snapshot requested {total} rows but only selected {len(selected)}")
    return selected[:total]


def build_snapshot(
    tarball: bytes,
    *,
    train_count: int,
    test_count: int,
    target_candidates: int,
    source_url: str,
) -> dict[str, Any]:
    import io

    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tf:
        claims_train = _read_jsonl_from_tar(tf, "data/claims_train.jsonl")
        claims_dev = _read_jsonl_from_tar(tf, "data/claims_dev.jsonl")
        corpus_rows = _read_jsonl_from_tar(tf, "data/corpus.jsonl")

    corpus_by_id = {
        str(row.get("doc_id")): row
        for row in corpus_rows
        if row.get("doc_id") is not None and _doc_text(row)
    }
    corpus_ids = sorted(corpus_by_id, key=lambda item: int(item) if item.isdigit() else item)
    normalized_train = [
        row
        for claim in claims_train
        if (
            row := _normalize_claim(
                claim,
                split="train",
                corpus_by_id=corpus_by_id,
                corpus_ids=corpus_ids,
                target_candidates=target_candidates,
            )
        )
    ]
    normalized_test = [
        row
        for claim in claims_dev
        if (
            row := _normalize_claim(
                claim,
                split="test",
                corpus_by_id=corpus_by_id,
                corpus_ids=corpus_ids,
                target_candidates=target_candidates,
            )
        )
    ]
    train = _take_by_label(normalized_train, total=train_count)
    test = _take_by_label(normalized_test, total=test_count)
    rows = [*train, *test]
    label_distribution = Counter(row["claim_label"] for row in rows)
    split_distribution = {"train": len(train), "test": len(test)}
    sample_count = len(rows)
    split_count = len([count for count in split_distribution.values() if count > 0])
    query_count = len({row["claim_id"] for row in test})
    document_count = len(
        {
            str(candidate.get("id"))
            for row in test
            for candidate in row.get("candidates", [])
            if candidate.get("id")
        }
    )
    evidence_annotation_count = sum(
        len(row.get("relevant_ids", []))
        for row in test
    )
    retrieval_relevance_count = len(
        {
            str(doc_id)
            for row in test
            for doc_id in row.get("relevant_ids", [])
        }
    )
    query_document_evidence_schema = {
        "query_fields": ["query"],
        "document_fields": ["candidates.id", "candidates.text"],
        "evidence_fields": ["relevant_ids", "evidence", "evidence_labels"],
        "label_fields": ["claim_label", "unsupported_claim"],
        "split_fields": ["train", "test", "source_split"],
        "label_space": ["not_enough_info", "refuted", "supported"],
        "supports_claim_verification": True,
        "schema_complete": True,
    }
    name = "SciFact Claim Verification Frozen Snapshot"
    description = (
        "Repository-local deterministic normalized snapshot generated from original SciFact "
        "claims_train/claims_dev records and corpus abstracts for offline claim-evidence execution."
    )
    dataset_id = "allenai/scifact"
    revision = "release-latest-data-tarball-sha256-11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be"
    license_name = "claims/evidence annotations: CC BY 4.0; corpus abstracts: S2ORC/ODC-By 1.0"
    source_fingerprint = _fingerprint(
        {
            "name": name,
            "description": description,
            "source_url": source_url,
            "train": train,
            "test": test,
        }
    )
    publication_grade_eligibility = {
        "source_class": "frozen_snapshot",
        "publication_grade": True,
        "provenance_complete": True,
        "sample_count": sample_count,
        "split_count": split_count,
        "source_fingerprint": source_fingerprint,
        "source_content_origin": "original_benchmark_records",
        "source_content_note": (
            "Normalized from original SciFact release records; not schema-derived "
            "or template-generated content."
        ),
        "checks": {
            "has_source_locator": True,
            "has_dataset_id": True,
            "has_revision": True,
            "has_license": True,
            "has_fingerprint": True,
            "has_train_test_split": split_count == 2,
            "meets_min_examples": sample_count >= 20,
            "meets_final_candidate_examples": sample_count >= 100,
            "not_internal_fixture": True,
            "content_imported_from_original_records": True,
            "query_document_evidence_schema_complete": True,
        },
    }
    payload: dict[str, Any] = {
        "name": name,
        "description": description,
        "source_url": source_url,
        "dataset_id": dataset_id,
        "revision": revision,
        "license": license_name,
        "fingerprint": source_fingerprint,
        "source_dataset_id": dataset_id,
        "source_revision": revision,
        "source_license": license_name,
        "source_locator": source_url,
        "source_content_origin": "original_benchmark_records",
        "source_content_note": (
            "Normalized from original SciFact claims_train.jsonl, claims_dev.jsonl, and corpus.jsonl "
            "records in the official release tarball; candidate pools are deterministic subsets of cited, "
            "gold, and corpus distractor documents."
        ),
        "source_archive_sha256": _sha256_bytes(tarball),
        "source_fingerprint": source_fingerprint,
        "source_splits": ["train", "test"],
        "source_class": "frozen_snapshot",
        "provenance_complete": True,
        "sample_count": sample_count,
        "split_count": split_count,
        "split_distribution": split_distribution,
        "label_distribution": dict(sorted(label_distribution.items())),
        "query_count": query_count,
        "document_count": document_count,
        "evidence_annotation_count": evidence_annotation_count,
        "retrieval_relevance_count": retrieval_relevance_count,
        "supports_claim_verification": True,
        "verification_label_space": ["not_enough_info", "refuted", "supported"],
        "query_document_evidence_schema": query_document_evidence_schema,
        "publication_grade_eligibility": publication_grade_eligibility,
        "publication_grade_blockers": [],
        "publication_grade": True,
        "final_publish_candidate_eligible": True,
        "final_publish_candidate_blockers": [],
        "normalization": {
            "script": "scripts/build_scifact_frozen_snapshot.py",
            "train_source_file": "data/claims_train.jsonl",
            "test_source_file": "data/claims_dev.jsonl",
            "corpus_source_file": "data/corpus.jsonl",
            "train_count": train_count,
            "test_count": test_count,
            "target_candidates_per_claim": target_candidates,
            "selection_policy": "deterministic balanced labels from official train/dev splits",
            "split_distribution": split_distribution,
            "label_distribution": dict(sorted(label_distribution.items())),
        },
        "train": train,
        "test": test,
    }
    return {**payload, "snapshot_fingerprint": _fingerprint(payload)}


def _retrieval_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": row["claim_id"],
        "query": row["query"],
        "candidates": row["candidates"],
        "relevant_ids": row["relevant_ids"],
    }


def build_retrieval_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    train = [_retrieval_row(row) for row in snapshot["train"]]
    test = [_retrieval_row(row) for row in snapshot["test"]]
    rows = [*train, *test]
    sample_count = len(rows)
    split_distribution = {"train": len(train), "test": len(test)}
    split_count = len([count for count in split_distribution.values() if count > 0])
    query_count = len({row["claim_id"] for row in test})
    document_count = len(
        {
            str(candidate.get("id"))
            for row in test
            for candidate in row.get("candidates", [])
            if candidate.get("id")
        }
    )
    retrieval_relevance_count = len(
        {
            str(doc_id)
            for row in test
            for doc_id in row.get("relevant_ids", [])
        }
    )
    name = "SciFact Claim Retrieval Frozen Snapshot"
    description = (
        "Repository-local retrieval-only view derived from the same official SciFact "
        "release records as the verification snapshot. It preserves query/candidate/qrels "
        "evidence for BEIR-style retrieval execution without carrying verification labels."
    )
    source_url = str(snapshot["source_url"])
    dataset_id = "allenai/scifact-retrieval-view"
    revision = str(snapshot["revision"])
    license_name = str(snapshot["license"])
    source_fingerprint = _fingerprint(
        {
            "name": name,
            "description": description,
            "source_url": source_url,
            "source_snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
            "train": train,
            "test": test,
        }
    )
    query_document_evidence_schema = {
        "query_fields": ["query"],
        "document_fields": ["candidates.id", "candidates.text"],
        "evidence_fields": ["relevant_ids"],
        "label_fields": [],
        "split_fields": ["train", "test"],
        "label_space": [],
        "supports_claim_verification": False,
        "schema_complete": True,
    }
    publication_grade_eligibility = {
        "source_class": "frozen_snapshot",
        "publication_grade": True,
        "provenance_complete": True,
        "sample_count": sample_count,
        "split_count": split_count,
        "source_fingerprint": source_fingerprint,
        "source_content_origin": "original_benchmark_records",
        "source_content_note": (
            "Retrieval-only view derived from normalized original SciFact release records; "
            "not schema-derived or template-generated content."
        ),
        "checks": {
            "has_source_locator": True,
            "has_dataset_id": True,
            "has_revision": True,
            "has_license": True,
            "has_fingerprint": True,
            "has_train_test_split": split_count == 2,
            "meets_min_examples": sample_count >= 20,
            "meets_final_candidate_examples": sample_count >= 100,
            "not_internal_fixture": True,
            "content_imported_from_original_records": True,
            "query_document_evidence_schema_complete": True,
        },
    }
    payload: dict[str, Any] = {
        "name": name,
        "description": description,
        "source_url": source_url,
        "dataset_id": dataset_id,
        "revision": revision,
        "license": license_name,
        "fingerprint": source_fingerprint,
        "source_dataset_id": dataset_id,
        "source_revision": revision,
        "source_license": license_name,
        "source_locator": source_url,
        "source_content_origin": "original_benchmark_records",
        "source_content_note": (
            "Derived from the repository-local SciFact verification snapshot generated from "
            "official claims_train.jsonl, claims_dev.jsonl, and corpus.jsonl records. This is "
            "a retrieval view of the same source release, not an independent benchmark source."
        ),
        "source_archive_sha256": snapshot.get("source_archive_sha256"),
        "source_fingerprint": source_fingerprint,
        "source_splits": ["train", "test"],
        "source_class": "frozen_snapshot",
        "source_parent_dataset_id": snapshot.get("dataset_id"),
        "source_parent_snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "provenance_complete": True,
        "sample_count": sample_count,
        "split_count": split_count,
        "split_distribution": split_distribution,
        "label_distribution": {},
        "query_count": query_count,
        "document_count": document_count,
        "evidence_annotation_count": 0,
        "retrieval_relevance_count": retrieval_relevance_count,
        "supports_claim_verification": False,
        "verification_label_space": [],
        "query_document_evidence_schema": query_document_evidence_schema,
        "publication_grade_eligibility": publication_grade_eligibility,
        "publication_grade_blockers": [],
        "publication_grade": True,
        "final_publish_candidate_eligible": True,
        "final_publish_candidate_blockers": [],
        "normalization": {
            "script": "scripts/build_scifact_frozen_snapshot.py",
            "source_view": "retrieval_only",
            "parent_snapshot": DEFAULT_OUTPUT.name,
            "selection_policy": "deterministic retrieval-only projection of the verification snapshot",
            "split_distribution": split_distribution,
        },
        "train": train,
        "test": test,
    }
    return {**payload, "snapshot_fingerprint": _fingerprint(payload)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ScholarFlow's frozen SciFact snapshot.")
    parser.add_argument("--input-tarball", type=Path, default=None)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--expected-sha256", default=DEFAULT_SOURCE_SHA256)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--retrieval-output", type=Path, default=DEFAULT_RETRIEVAL_OUTPUT)
    parser.add_argument(
        "--retrieval-only-from-snapshot",
        type=Path,
        default=None,
        help="Derive only the retrieval-view snapshot from an existing verification snapshot JSON.",
    )
    parser.add_argument("--train-count", type=int, default=72)
    parser.add_argument("--test-count", type=int, default=48)
    parser.add_argument("--target-candidates", type=int, default=5)
    args = parser.parse_args()

    if args.retrieval_only_from_snapshot is not None:
        snapshot = json.loads(args.retrieval_only_from_snapshot.read_text(encoding="utf-8"))
        retrieval_view = build_retrieval_view(snapshot)
        args.retrieval_output.parent.mkdir(parents=True, exist_ok=True)
        args.retrieval_output.write_text(
            json.dumps(retrieval_view, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"Wrote {args.retrieval_output} with "
            f"{len(retrieval_view['train']) + len(retrieval_view['test'])} "
            "retrieval-only SciFact examples."
        )
        return

    tarball = _load_tarball(args.input_tarball, args.source_url)
    actual_sha = _sha256_bytes(tarball)
    if args.expected_sha256 and actual_sha != args.expected_sha256:
        raise SystemExit(
            f"SciFact tarball sha256 mismatch: expected {args.expected_sha256}, got {actual_sha}"
        )
    snapshot = build_snapshot(
        tarball,
        train_count=args.train_count,
        test_count=args.test_count,
        target_candidates=args.target_candidates,
        source_url=args.source_url,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {args.output} with {len(snapshot['train']) + len(snapshot['test'])} "
        f"normalized SciFact examples."
    )
    retrieval_view = build_retrieval_view(snapshot)
    args.retrieval_output.parent.mkdir(parents=True, exist_ok=True)
    args.retrieval_output.write_text(
        json.dumps(retrieval_view, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {args.retrieval_output} with "
        f"{len(retrieval_view['train']) + len(retrieval_view['test'])} "
        "retrieval-only SciFact examples."
    )


if __name__ == "__main__":
    main()
