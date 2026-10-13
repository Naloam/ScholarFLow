#!/usr/bin/env python3
"""P4/M4 — tabular-domain seed slices for paper #3 (journal production line).

The tabular domain had only breast_cancer (424 rows, source-limited) — not
enough for a cross-dataset journal paper. This adds two UCI Wine Quality
slices (real data, stable archive URLs, deterministic):

  - wine_red_tabular   : red vinho verde, quality >= 7 = "good" (binary)
  - wine_white_tabular : white vinho verde, same binarization

11 numeric physicochemical features; label 0/1 balanced (min class capped at
1000/side → ≤2000 rows), sorted by id, committed as JSONL (zero runtime
network — same contract as the other slices).

Usage:
    ./.venv/bin/python scripts/build_tabular_slices.py --out-dir /tmp/tab_check  # verify
    ./.venv/bin/python scripts/build_tabular_slices.py --apply
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "backend" / "services" / "research_harness" / "seed_data"

WINE_URLS = {
    "wine_red_tabular": "https://archive.ics.uci.edu/static/public/186/wine+quality.zip",
}
PER_SIDE_CAP = 1000

FEATURES = [
    "fixed_acidity", "volatile_acidity", "citric_acid", "residual_sugar",
    "chlorides", "free_sulfur_dioxide", "total_sulfur_dioxide", "density",
    "ph", "sulphates", "alcohol",
]


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "scholarflow-seed-builder"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def build_wine(out_dir: Path) -> dict[str, list[dict]]:
    import zipfile

    data = _fetch(WINE_URLS["wine_red_tabular"])
    results: dict[str, list[dict]] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member, key in (
            ("winequality-red.csv", "wine_red_tabular"),
            ("winequality-white.csv", "wine_white_tabular"),
        ):
            rows = list(csv.DictReader(io.StringIO(zf.read(member).decode("utf-8")), delimiter=";"))
            by_label = {0: [], 1: []}
            for i, raw in enumerate(rows):
                r = {k.replace(" ", "_").lower(): v for k, v in raw.items()}  # headers quoted, spaced, mixed-case (pH)
                try:
                    feats = [float(r[f]) for f in FEATURES]
                    quality = int(r["quality"])
                except (KeyError, ValueError):
                    continue
                by_label[1 if quality >= 7 else 0].append({
                    "id": f"{key}-{i}",
                    "features": feats,
                    "label": 1 if quality >= 7 else 0,
                    "label_name": "good" if quality >= 7 else "not_good",
                    "quality_raw": quality,
                    "source": "UCI Wine Quality (Cortez et al. 2009, CC BY 4.0)",
                })
            per_side = min(len(by_label[0]), len(by_label[1]), PER_SIDE_CAP)
            balanced = by_label[1][:per_side] + by_label[0][:per_side]  # positives first like digits
            balanced.sort(key=lambda r: r["id"])
            out = out_dir / f"{key}.jsonl"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in balanced) + "\n",
                encoding="utf-8",
            )
            results[key] = balanced
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.apply and args.out_dir is None:
        ap.error("pass --out-dir <dir> to verify, or --apply")
    out_dir = args.out_dir if args.out_dir is not None else SEED_DIR
    results = build_wine(out_dir)
    for name, rows in results.items():
        dist = dict(Counter(r["label"] for r in rows))
        print(f"{name}: {len(rows)} rows, labels={dist}")
    print(f"written to: {out_dir}")


if __name__ == "__main__":
    main()
