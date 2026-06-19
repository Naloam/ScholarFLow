#!/usr/bin/env python3
"""Session 10 Step 3 — rebuild the claim-verification seed slices at real scale.

The Session-9 live run was toy-scale: 100 examples/dataset × 10 seeds. The time
budget (Step 2 measurement, ``scripts/measure_scale_budget.py``) shows the
SentenceTransformer path costs <1s even at 1000×256, so the binding constraint is
**source-data availability**, not compute. This script maximises real held-out
data within the ``≤500`` cap, keeping the unified schema and license/attribution:

  - scifact_slice.jsonl      : 100 → 474 (237 SUPPORT / 237 REFUTE)
                               allenai/scifact dev+train labeled claims; gold
                               evidence abstract attached from corpus.jsonl.
  - vitaminc_slice.jsonl     : 100 → 500 (250 SUPPORTS / 250 REFUTES)
                               tals/vitaminc dev split.
  - citation_faithfulness    : 100 → 474 (237 FAITHFUL / 237 PARSING_ERROR)
                               deterministic derivation from the new scifact
                               slice (same construction as Session 4).

Deterministic (sorted by id) → reproducible committed data, zero runtime network.

Run from repo root:

    ./.venv/bin/python scripts/build_seed_slices_v2.py
"""
from __future__ import annotations

import io
import json
import tarfile
import urllib.request
from collections import Counter
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "backend" / "services" / "research_harness" / "seed_data"

SCIFACT_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
SCIFACT_SHA256 = "11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be"
VITAMINC_REPO = "tals/vitaminc"
VITAMINC_FILE = "dev.jsonl"

# ``capability_note`` caps each dataset at <= 500 held-out examples.
PER_DATASET_CAP = 500


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=180) as resp:
        return resp.read()


def _doc_text(doc: dict) -> tuple[str, str]:
    title = " ".join(str(doc.get("title") or "").split())
    abstract_raw = doc.get("abstract") or []
    if isinstance(abstract_raw, list):
        abstract = " ".join(" ".join(str(item).split()) for item in abstract_raw)
    else:
        abstract = " ".join(str(abstract_raw).split())
    return title, " ".join(part for part in (title, abstract) if part).strip()


def build_scifact_slice(out: Path) -> list[dict]:
    import hashlib

    data = _fetch(SCIFACT_URL)
    actual = hashlib.sha256(data).hexdigest()
    if actual != SCIFACT_SHA256:
        raise SystemExit(f"SciFact tarball sha256 mismatch: got {actual}")

    rows: list[dict] = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        corpus_raw = tf.extractfile("data/corpus.jsonl")
        corpus = {}
        for line in corpus_raw.read().decode("utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                corpus[str(d.get("doc_id"))] = d
        for split, member in (("dev", "data/claims_dev.jsonl"), ("train", "data/claims_train.jsonl")):
            extracted = tf.extractfile(member)
            for line in extracted.read().decode("utf-8").splitlines():
                if not line.strip():
                    continue
                claim = json.loads(line)
                evidence = claim.get("evidence") or {}
                if not isinstance(evidence, dict) or not evidence:
                    continue
                # decide label + pick the gold doc that determines it
                label = None
                gold_id = None
                for doc_id, entries in evidence.items():
                    labels = [str(e.get("label")).upper() for e in entries if isinstance(e, dict)]
                    if "CONTRADICT" in labels:
                        label, gold_id = "REFUTE", str(doc_id)
                        break
                    if "SUPPORT" in labels and label is None:
                        label, gold_id = "SUPPORT", str(doc_id)
                if label is None or gold_id is None or gold_id not in corpus:
                    continue
                title, text = _doc_text(corpus[gold_id])
                if not text:
                    continue
                rows.append({
                    "id": f"scifact-{split}-{int(claim.get('id') or 0)}",
                    "claim": " ".join(str(claim.get("claim") or "").split()),
                    "evidence": text,
                    "evidence_title": title,
                    "label": label,
                    "source": f"scifact_{split}",
                })

    # deterministic order, then balance to min(S,R) capped at PER_DATASET_CAP//2 each
    rows.sort(key=lambda r: (r["source"], r["id"]))
    by_label = {"SUPPORT": [], "REFUTE": []}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)
    per_side = min(len(by_label["SUPPORT"]), len(by_label["REFUTE"]), PER_DATASET_CAP // 2)
    balanced = by_label["SUPPORT"][:per_side] + by_label["REFUTE"][:per_side]
    balanced.sort(key=lambda r: r["id"])
    _write_jsonl(out, balanced)
    return balanced


def build_vitaminc_slice(out: Path) -> list[dict]:
    from huggingface_hub import hf_hub_download

    p = hf_hub_download(VITAMINC_REPO, VITAMINC_FILE, repo_type="dataset")
    by_label = {"SUPPORT": [], "REFUTE": []}
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            lab = str(r.get("label") or "").upper()
            if lab == "SUPPORTS":
                key = "SUPPORT"
            elif lab == "REFUTES":
                key = "REFUTE"
            else:
                continue
            claim = " ".join(str(r.get("claim") or "").split())
            evidence = " ".join(str(r.get("evidence") or "").split())
            if not claim or not evidence:
                continue
            by_label[key].append({
                "id": str(r.get("unique_id") or ""),
                "claim": claim,
                "evidence": evidence,
                "evidence_title": " ".join(str(r.get("page") or "").split()),
                "label": key,
                "source": "vitaminc",
            })
    for k in by_label:
        by_label[k].sort(key=lambda r: r["id"])
    per_side = min(len(by_label["SUPPORT"]), len(by_label["REFUTE"]), PER_DATASET_CAP // 2)
    balanced = by_label["SUPPORT"][:per_side] + by_label["REFUTE"][:per_side]
    balanced.sort(key=lambda r: r["id"])
    _write_jsonl(out, balanced)
    return balanced


def build_citation_faithfulness_slice(scifact_rows: list[dict], out: Path) -> list[dict]:
    """Deterministic derivation: N_CLAIMS claims × 2 classes.

    FAITHFUL[i]    = scifact[i]              (claim + its OWN gold evidence).
    PARSING_ERROR  = scifact[i] paired with the evidence of scifact[i + N_CLAIMS]
                     (a topically different abstract → a citation that resolves to
                     the wrong source). Same claims in both classes ⇒ the only
                     difference is the evidence.
    """
    n_claims = min(len(scifact_rows) // 2, PER_DATASET_CAP // 2)
    faithful = []
    errors = []
    for i in range(n_claims):
        base = scifact_rows[i]
        donor = scifact_rows[i + n_claims]
        faithful.append({
            "id": f"citation-faithful-{i}",
            "claim": base["claim"],
            "evidence": base["evidence"],
            "evidence_title": base.get("evidence_title", ""),
            "label": "FAITHFUL",
            "source": "citation_faithfulness",
        })
        errors.append({
            "id": f"citation-error-{i}",
            "claim": base["claim"],
            "evidence": donor["evidence"],
            "evidence_title": donor.get("evidence_title", ""),
            "label": "PARSING_ERROR",
            "source": "citation_faithfulness",
        })
    rows = faithful + errors
    _write_jsonl(out, rows)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    scifact = build_scifact_slice(SEED_DIR / "scifact_slice.jsonl")
    vitaminc = build_vitaminc_slice(SEED_DIR / "vitaminc_slice.jsonl")
    citation = build_citation_faithfulness_slice(scifact, SEED_DIR / "citation_faithfulness_slice.jsonl")
    for name, rows in (("scifact", scifact), ("vitaminc", vitaminc), ("citation_faithfulness", citation)):
        dist = dict(Counter(r["label"] for r in rows))
        print(f"{name}: {len(rows)} rows, labels={dist}")


if __name__ == "__main__":
    main()
