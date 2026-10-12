#!/usr/bin/env python3
"""P4.3 — expand the seed slices to journal-review scale (Session 18).

The June (Session 10) slices were capped at 500 examples/dataset. Journals expect
robustness at larger scale, and the measured budget (``measure_scale_budget.py``:
SentenceTransformer path <1s at 1000x256; sklearn paths far cheaper) leaves room.

Expansion (only where the SOURCE data allows — scifact/breast_cancer stay at
their full-labeled-set sizes, honestly attributed):

  - vitaminc_slice.jsonl            : 500 -> 2000 (1000 SUPPORT / 1000 REFUTE)
                                       tals/vitaminc dev split (needs network: HF).
  - citation_faithfulness_slice.jsonl: 474 -> 948 (474 FAITHFUL / 474 PARSING_ERROR)
                                       ALL committed scifact claims, circular
                                       half-shift donor pairing (no network).
  - digits_slice.jsonl              : 500 -> 1600 (800 even / 800 odd)
                                       sklearn.datasets.load_digits (local).

Deterministic (sorted by id) -> reproducible committed data, zero runtime
network for consumers. scifact_slice.jsonl is NOT rebuilt (stays byte-identical).

Usage:
    ./.venv/bin/python scripts/build_seed_slices_v3.py --out-dir /tmp/seed_v3   # verify
    ./.venv/bin/python scripts/build_seed_slices_v3.py --apply                  # write into seed_data/
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "backend" / "services" / "research_harness" / "seed_data"

VITAMINC_PER_SIDE = 1000
DIGITS_PER_SIDE = 800


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_vitaminc(out: Path) -> list[dict]:
    from huggingface_hub import hf_hub_download

    p = hf_hub_download("tals/vitaminc", "dev.jsonl", repo_type="dataset")
    by_label = {"SUPPORT": [], "REFUTE": []}
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            lab = str(r.get("label") or "").upper()
            key = {"SUPPORTS": "SUPPORT", "REFUTES": "REFUTE"}.get(lab)
            if key is None:
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
    per_side = min(len(by_label["SUPPORT"]), len(by_label["REFUTE"]), VITAMINC_PER_SIDE)
    balanced = by_label["SUPPORT"][:per_side] + by_label["REFUTE"][:per_side]
    balanced.sort(key=lambda r: r["id"])
    if per_side < VITAMINC_PER_SIDE:
        print(f"warning: vitaminc source only allowed {per_side}/side (wanted {VITAMINC_PER_SIDE})")
    _write_jsonl(out, balanced)
    return balanced


def build_citation_faithfulness(scifact_rows: list[dict], out: Path) -> list[dict]:
    """ALL claims x 2 classes. FAITHFUL[i] = claim[i] + own evidence;
    PARSING_ERROR[i] = claim[i] + evidence[(i + N//2) % N] — a deterministic
    circular half-shift donor (topically different abstract), wrapping so every
    claim yields both classes. Same claims in both classes => the only difference
    is the evidence (unchanged Session-4 construction property)."""
    rows_src = sorted(scifact_rows, key=lambda r: r["id"])
    n = len(rows_src)
    half = n // 2
    faithful, errors = [], []
    for i, base in enumerate(rows_src):
        donor = rows_src[(i + half) % n]
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


def build_digits(out: Path) -> list[dict]:
    from sklearn.datasets import load_digits

    data = load_digits()
    by_parity = {0: [], 1: []}
    for i, (img, tgt) in enumerate(zip(data.data, data.target)):
        by_parity[int(tgt) % 2].append({
            "id": f"digits-{i}",
            "features": [round(float(v) / 16.0, 6) for v in img],
            "label": int(tgt) % 2,
            "label_name": "even" if int(tgt) % 2 == 0 else "odd",
            "source": "sklearn.datasets.load_digits",
        })
    per_side = min(len(by_parity[0]), len(by_parity[1]), DIGITS_PER_SIDE)
    balanced = by_parity[0][:per_side] + by_parity[1][:per_side]
    balanced.sort(key=lambda r: r["id"])
    _write_jsonl(out, balanced)
    return balanced


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=None, help="verify mode: write to this dir instead of seed_data/")
    ap.add_argument("--apply", action="store_true", help="write into backend/services/research_harness/seed_data/")
    args = ap.parse_args()
    if not args.apply and args.out_dir is None:
        ap.error("pass --out-dir <dir> to verify, or --apply to write seed_data/")
    out_dir = args.out_dir if args.out_dir is not None else SEED_DIR

    scifact_rows = _read_jsonl(SEED_DIR / "scifact_slice.jsonl")  # committed, not rebuilt
    results = {
        "vitaminc_slice.jsonl": build_vitaminc(out_dir / "vitaminc_slice.jsonl"),
        "citation_faithfulness_slice.jsonl": build_citation_faithfulness(
            scifact_rows, out_dir / "citation_faithfulness_slice.jsonl"
        ),
        "digits_slice.jsonl": build_digits(out_dir / "digits_slice.jsonl"),
    }
    for name, rows in results.items():
        dist = dict(Counter(r.get("label", r.get("label_name", "?")) for r in rows))
        print(f"{name}: {len(rows)} rows, labels={dist}")
    print(f"written to: {out_dir}")


if __name__ == "__main__":
    main()
