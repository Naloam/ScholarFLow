#!/usr/bin/env python3
"""Session 12 Step 2 — build real, balanced, non-retrieval-domain seed slices.

Proves the harness brain is not claim-verification-overfit: two datasets from
**distinct non-retrieval domains**, committed as JSONL (zero runtime network),
loaded by stdlib json. Both are real scikit-learn toy datasets (already an
ALLOWED_PACKAGE), sliced deterministically and balanced.

  - breast_cancer_slice.jsonl  (domain="tabular")
      30 numeric diagnostic features → binary tumour class (malignant/benign).
      Real clinical features (sklearn.datasets.load_breast_cancer).
  - digits_slice.jsonl         (domain="structured")
      64 (8x8) pixel-intensity features → binary parity label (even/odd digit).
      Real handwritten-digit images (sklearn.datasets.load_digits); parity is a
      legitimate binary structuring of the 10-class task.

Schema (feature vectors, not text — distinct from the claim-verification slices):
  {"id","features":[float,...],"label":0|1,"label_name":"...","source":"..."}

Run from repo root:  ./.venv/bin/python scripts/build_cross_domain_slices.py
"""
from __future__ import annotations

import json
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "backend" / "services" / "research_harness" / "seed_data"
PER_DATASET_CAP = 500


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def _balance(rows: list[dict], per_side: int) -> list[dict]:
    by_label: dict[int, list[dict]] = {0: [], 1: []}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)
    by_label[0].sort(key=lambda r: r["id"])
    by_label[1].sort(key=lambda r: r["id"])
    n = min(len(by_label[0]), len(by_label[1]), per_side)
    return by_label[0][:n] + by_label[1][:n]


def build_breast_cancer() -> list[dict]:
    from sklearn.datasets import load_breast_cancer

    data = load_breast_cancer()
    rows = []
    for i, (feat, lab) in enumerate(zip(data.data, data.target)):
        rows.append({
            "id": f"breastcancer-{i}",
            "features": [round(float(x), 6) for x in feat],
            "label": int(lab),  # 0=malignant, 1=benign
            "label_name": str(data.target_names[int(lab)]),
            "source": "sklearn.datasets.load_breast_cancer",
        })
    balanced = _balance(rows, PER_DATASET_CAP // 2)
    balanced.sort(key=lambda r: r["id"])
    _write_jsonl(SEED_DIR / "breast_cancer_slice.jsonl", balanced)
    return balanced


def build_digits() -> list[dict]:
    from sklearn.datasets import load_digits

    data = load_digits()
    rows = []
    for i, (feat, tgt) in enumerate(zip(data.data, data.target)):
        parity = int(tgt) % 2  # 0=even digit, 1=odd digit — a real binary structuring
        rows.append({
            "id": f"digits-{i}",
            "features": [round(float(x) / 16.0, 6) for x in feat],  # normalize 0..16 -> 0..1
            "label": parity,
            "label_name": f"digit_{int(tgt)}",
            "source": "sklearn.datasets.load_digits",
        })
    balanced = _balance(rows, PER_DATASET_CAP // 2)
    balanced.sort(key=lambda r: r["id"])
    _write_jsonl(SEED_DIR / "digits_slice.jsonl", balanced)
    return balanced


def main() -> None:
    from collections import Counter

    bc = build_breast_cancer()
    dg = build_digits()
    for name, rows in (("breast_cancer", bc), ("digits", dg)):
        print(f"{name}: {len(rows)} rows, labels={dict(Counter(r['label'] for r in rows))}, "
              f"n_features={len(rows[0]['features'])}")


if __name__ == "__main__":
    main()
