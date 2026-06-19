#!/usr/bin/env python3
"""Session 10 Step 2 — empirical time-budget measurement for the experiment plane.

Measures the real wall-clock of the SentenceTransformer + paired-bootstrap path
that ``experiment_engineer`` asks the LLM to generate, so the scale decision
(held-out size × seed count) is grounded in a measurement, not a guess. Prints a
slice × seed × wall-clock table. Run from repo root:

    ./.venv/bin/python scripts/measure_scale_budget.py
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

import numpy as np

SEED_DIR = Path("backend/services/research_harness/seed_data")
SLICES = ["scifact_slice.jsonl", "vitaminc_slice.jsonl", "citation_faithfulness_slice.jsonl"]


def _load(name: str) -> list[dict]:
    rows = [json.loads(line) for line in (SEED_DIR / name).read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def _labels(rows: list[dict]) -> list[int]:
    out = []
    for r in rows:
        lab = str(r.get("label", "")).upper()
        # faithful/support -> 1, else 0
        out.append(0 if lab in {"REFUTE", "PARSING_ERROR"} else 1)
    return out


def macro_f1_from_scores(scores: np.ndarray, y: np.ndarray, threshold: float) -> float:
    pred = (scores >= threshold).astype(int)
    classes = sorted(set(y.tolist()))
    f1s = []
    for c in classes:
        tp = int(((pred == c) & (y == c)).sum())
        fp = int(((pred == c) & (y != c)).sum())
        fn = int(((pred != c) & (y == c)).sum())
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        f1s.append(f1)
    return float(np.mean(f1s))


def main() -> None:
    from sentence_transformers import SentenceTransformer

    t0 = time.time()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"# ST model load: {time.time() - t0:.2f}s")

    datasets = {}
    for name in SLICES:
        rows = _load(name)
        claims = [r.get("claim", "") for r in rows]
        evid = [r.get("evidence", "") for r in rows]
        y = np.array(_labels(rows), dtype=int)
        datasets[name] = {"claims": claims, "evid": evid, "y": y, "n": len(rows)}

    # Pre-encode each full slice once (the codegen is told to do exactly this).
    for name, d in datasets.items():
        te = time.time()
        d["claim_emb"] = model.encode(d["claims"], normalize_embeddings=True, show_progress_bar=False)
        d["evid_emb"] = model.encode(d["evid"], normalize_embeddings=True, show_progress_bar=False)
        d["encode_s"] = time.time() - te

    print(f"\n# Per-dataset encode (full 100-row slice):")
    for name, d in datasets.items():
        print(f"#   {name}: encode={d['encode_s']:.2f}s  (n={d['n']})")

    # Simulate the bootstrap at varying (n_examples, n_seeds). For n_examples > 100 we
    # tile the slice deterministically so the measurement reflects real compute shape.
    print("\n## slice_size × seeds × wall_clock(s)  [3 datasets, proposed-system only]")
    print("## (encode amortized once outside the seed loop, as the codegen is told)")
    for n_examples in (100, 300, 500, 1000):
        for n_seeds in (10, 64, 128, 256):
            # build a deterministic n_examples pool per dataset
            pools = {}
            for name, d in datasets.items():
                c = d["claim_emb"]; e = d["evid_emb"]; y = d["y"]
                reps = (n_examples + len(y) - 1) // len(y)
                pools[name] = {
                    "c": np.tile(c, (reps, 1))[:n_examples],
                    "e": np.tile(e, (reps, 1))[:n_examples],
                    "y": np.tile(y, reps)[:n_examples],
                }
            t = time.time()
            for name, p in pools.items():
                yb = p["y"]
                full_scores = (p["c"] * p["e"]).sum(axis=1)
                # calibrate threshold on a tiny split (mean), then bootstrap
                base_thr = float(full_scores.mean())
                for seed in range(n_seeds):
                    rng = random.Random(seed)
                    idx = [rng.randrange(n_examples) for _ in range(n_examples)]
                    idx_arr = np.array(idx)
                    sc = full_scores[idx_arr]
                    yy = yb[idx_arr]
                    macro_f1_from_scores(sc, yy, base_thr)
            wall = time.time() - t
            print(f"#   n={n_examples:>4} seeds={n_seeds:>3} -> {wall:6.2f}s")


if __name__ == "__main__":
    main()
