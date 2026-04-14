"""Structured experiment history tracking in TSV format.

Inspired by karpathy/autoresearch's results.tsv pattern:
each experiment attempt appends a row with modification, metric, delta, verdict.
This history is fed to the paper writer for iterative improvement narrative.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

HEADERS = ["round", "modification", "metric_name", "metric_value", "delta", "verdict", "description"]

# Verdict values
KEEP = "keep"
DISCARD = "discard"
BASELINE = "baseline"
FAILED = "failed"


def results_tsv_path(run_dir: Path) -> Path:
    return run_dir / "results.tsv"


def append_result(
    run_dir: Path,
    *,
    round_index: int,
    modification: str,
    metric_name: str,
    metric_value: float | None,
    delta: float | None,
    verdict: str,
    description: str = "",
) -> None:
    """Append one row to the experiment history TSV."""
    tsv_path = results_tsv_path(run_dir)
    write_header = not tsv_path.exists()

    row = {
        "round": str(round_index),
        "modification": modification,
        "metric_name": metric_name,
        "metric_value": f"{metric_value:.4f}" if metric_value is not None else "",
        "delta": f"{delta:+.4f}" if delta is not None else "",
        "verdict": verdict,
        "description": description,
    }

    with open(tsv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS, delimiter="\t")
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    logger.info(
        "results_tsv: round=%d modification=%s metric=%s verdict=%s",
        round_index, modification, metric_value, verdict,
    )


def load_history(run_dir: Path) -> list[dict]:
    """Load all rows from the experiment history TSV."""
    tsv_path = results_tsv_path(run_dir)
    if not tsv_path.exists():
        return []

    rows: list[dict] = []
    with open(tsv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row.get("metric_value"):
                try:
                    row["metric_value"] = float(row["metric_value"])
                except ValueError:
                    pass
            if row.get("delta"):
                try:
                    row["delta"] = float(row["delta"])
                except ValueError:
                    pass
            if row.get("round"):
                try:
                    row["round"] = int(row["round"])
                except ValueError:
                    pass
            rows.append(row)
    return rows


def history_to_narrative(run_dir: Path) -> str:
    """Convert experiment history to a human-readable narrative for paper writing.

    This is consumed by the paper writer to describe the iterative improvement process.
    """
    rows = load_history(run_dir)
    if not rows:
        return "No structured experiment history was recorded."

    lines = ["# Experiment History", ""]
    baseline_value = None
    kept_count = 0

    for row in rows:
        verdict = row.get("verdict", "")
        modification = row.get("modification", "unknown")
        metric_val = row.get("metric_value", "")
        delta = row.get("delta", "")
        round_idx = row.get("round", "?")

        if verdict == BASELINE:
            baseline_value = metric_val
            lines.append(f"- **Baseline** (round {round_idx}): {modification} — {metric_val}")

        elif verdict == KEEP:
            kept_count += 1
            delta_str = f" (Δ={delta})" if delta else ""
            lines.append(
                f"- **Kept** (round {round_idx}): {modification} — {metric_val}{delta_str}"
            )

        elif verdict == DISCARD:
            delta_str = f" (Δ={delta})" if delta else ""
            lines.append(
                f"- Discarded (round {round_idx}): {modification} — {metric_val}{delta_str}"
            )

        elif verdict == FAILED:
            lines.append(f"- **Failed** (round {round_idx}): {modification} — {row.get('description', 'execution error')}")

    # Summary
    if baseline_value is not None and kept_count > 0:
        kept_rows = [r for r in rows if r.get("verdict") == KEEP]
        best = kept_rows[-1] if kept_rows else None
        if best:
            best_val = best.get("metric_value")
            best_mod = best.get("modification", "final method")
            total_delta = ""
            if isinstance(best_val, (int, float)) and isinstance(baseline_value, (int, float)):
                total_delta = f" (+{best_val - baseline_value:.4f} over baseline)"
            lines.append(
                f"\n**Summary**: {kept_count} improvements kept across {len(rows)} rounds. "
                f"Best: {best_mod} at {best_val}{total_delta}."
            )

    return "\n".join(lines)
