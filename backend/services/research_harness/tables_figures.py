"""P4.5/A3 — deterministic tables & figures for the paper layer (plan Phase A).

Why: live manuscripts proved LLM-hand-written tables drop systems/columns and
the papers ship with zero figures. Everything here is DERIVED from metrics.json
by plain code — the Writer copies these artifacts verbatim and never invents
numbers or plots.

Contract:
- ``aggregate_results(metrics)`` → per (system, metric, dataset): mean/std/n
- ``render_main_table(metrics)``  → markdown table with ALL systems × datasets
  for the anchored primary metric (mean ± std over seeds), proposed-vs-lexical
  Δ and significance marks when the tests exist
- ``render_figures(project_dir, metrics)`` → PNG files under artifacts/figures/:
  1. main comparison grouped bars (mean + 95% CI whiskers from per-seed values)
  2. per-seed paired delta distribution (the honest significance picture)
  3. cross-dataset robustness heatmap (system × dataset, column-normalized)
Labels are Chinese when a CJK font is available, English otherwise.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


def aggregate_results(metrics: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, float]]:
    """Per (system, metric, dataset) mean/std/count over the per-seed rows."""
    buckets: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for r in metrics.get("results") or []:
        if not isinstance(r, dict):
            continue
        v = r.get("metric_value")
        if not isinstance(v, (int, float)):
            continue
        buckets[(r.get("system_name", ""), r.get("metric_name", ""), r.get("dataset_name", ""))].append(float(v))
    out: dict[tuple[str, str, str], dict[str, float]] = {}
    for key, vals in buckets.items():
        n = len(vals)
        mean = sum(vals) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / n) if n > 1 else 0.0
        out[key] = {"mean": mean, "std": std, "n": n}
    return out


def _primary_metric(metrics: dict[str, Any]) -> str:
    return (metrics.get("baseline_comparison") or {}).get("metric_name") or "macro_f1"


def _resolve_systems(systems: list[str]) -> tuple[str | None, str | None]:
    """(proposed, baseline) resolution robust to system naming: proposed = the
    one containing 'proposed'; baseline = 'lexical' → 'baseline*' → first
    system that is neither proposed nor an ablation."""
    proposed = next((s for s in systems if "proposed" in s.lower()), None)
    baseline = next(
        (s for s in systems if "baseline" in s.lower() and "lexical" in s.lower()),
        None,
    )
    if baseline is None:
        baseline = next((s for s in systems if s.lower().startswith("baseline")), None)
    if baseline is None:
        baseline = next(
            (s for s in systems if "lexical" in s.lower() and "ablation" not in s.lower()),
            None,
        )
    if baseline is None:
        baseline = next(
            (s for s in systems if s is not proposed and "ablation" not in s.lower()),
            None,
        )
    return proposed, baseline


def _significance_by_dataset(metrics: dict[str, Any]) -> dict[str, bool]:
    """dataset → significant (favorable) from the paired tests."""
    out: dict[str, bool] = {}
    for t in (metrics.get("statistics") or {}).get("significance_tests") or []:
        detail = t.get("detail") or ""
        if "dataset=" in detail:
            ds = detail.split("dataset=")[-1].split(":")[0].split(" ")[0].strip()
            out[ds] = bool(t.get("significant"))
    return out


# --------------------------------------------------------------------------- #
# Main table (markdown, ALL systems)
# --------------------------------------------------------------------------- #


def render_main_table(metrics: dict[str, Any], table_id: int = 1) -> str:
    agg = aggregate_results(metrics)
    primary = _primary_metric(metrics)
    bc = metrics.get("baseline_comparison") or {}
    datasets = [d.get("dataset") for d in (bc.get("datasets") or []) if isinstance(d, dict)]
    if not datasets:
        seen: list[str] = []
        for _s, _m, ds in agg:
            if ds not in seen:
                seen.append(ds)
        datasets = seen
    systems = sorted({s for (s, m, _d) in agg if m == primary and _d in datasets})
    if not systems:
        return ""
    sig = _significance_by_dataset(metrics)
    direction = (bc.get("direction") or "higher_is_better") == "higher_is_better"

    # Δ reference: the resolved baseline system (NOT systems[0] — that once
    # picked an ablation and mislabeled the whole delta row)
    _p, lexical = _resolve_systems(systems)
    proposed = _p

    lines = [
        f"表 {table_id} 各系统在 {len(datasets)} 个数据集上的 {primary}（512 种子均值 ± 标准差；"
        + ("越高越好" if direction else "越低越好")
        + "）",
        "",
        "| 系统 | " + " | ".join(datasets) + " |",
        "|---|" + "---|" * len(datasets),
    ]
    for s in systems:
        cells = []
        for d in datasets:
            e = agg.get((s, primary, d))
            cells.append(f"{e['mean']:.4f} ± {e['std']:.4f}" if e else "—")
        lines.append(f"| {s} | " + " | ".join(cells) + " |")
    if proposed and proposed != lexical:
        deltas = []
        for d in datasets:
            p = agg.get((proposed, primary, d))
            b = agg.get((lexical, primary, d))
            if not p or not b:
                deltas.append("—")
                continue
            delta = p["mean"] - b["mean"]
            mark = ""
            if sig.get(d):
                mark = "*" if (delta > 0) == direction else "†"  # * 显著有利 / † 显著不利
            deltas.append(f"{delta:+.4f}{mark}")
        lines.append(f"| Δ（{proposed} − {lexical}） | " + " | ".join(deltas) + " |")
    lines.append("")
    lines.append("注：* 表示配对符号翻转检验显著且方向有利；† 表示显著但方向不利；无标记为不显著。")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #

_CJK_FONT_CANDIDATES = ("PingFang SC", "Hiragino Sans GB", "Arial Unicode MS", "SimHei", "Noto Sans CJK SC")


def _setup_cjk_font():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, rcParams
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _CJK_FONT_CANDIDATES:
        if name in available:
            rcParams["font.family"] = [name, "DejaVu Sans"]
            rcParams["axes.unicode_minus"] = False
            return name
    rcParams["font.family"] = ["DejaVu Sans"]
    return None


def _per_seed_pairs(metrics: dict[str, Any], primary: str) -> dict[str, dict[int, tuple[float, float]]]:
    """dataset → seed → (proposed, baseline) per-seed values."""
    systems = {r.get("system_name", "") for r in metrics.get("results") or []}
    proposed, lexical = _resolve_systems(sorted(systems))
    if not proposed or not lexical:
        return {}
    out: dict[str, dict[int, tuple[float, float]]] = defaultdict(dict)
    for r in metrics.get("results") or []:
        if r.get("metric_name") != primary:
            continue
        s = r.get("system_name", "")
        seed = r.get("seed")
        ds = r.get("dataset_name", "")
        if seed is None:
            continue
        if s == proposed:
            out[ds].setdefault(int(seed), [None, None])[0] = float(r["metric_value"])
        elif s == lexical:
            out[ds].setdefault(int(seed), [None, None])[1] = float(r["metric_value"])
    return {d: {k: tuple(v) for k, v in pairs.items() if v[0] is not None and v[1] is not None}
            for d, pairs in out.items()}


def render_figures(project_dir: Path, metrics: dict[str, Any]) -> list[Path]:
    """Generate the standard figure set; returns the written PNG paths."""
    font = _setup_cjk_font()
    lang = "zh" if font else "en"
    out_dir = Path(project_dir) / "artifacts" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    primary = _primary_metric(metrics)
    agg = aggregate_results(metrics)
    bc = metrics.get("baseline_comparison") or {}
    datasets = [d.get("dataset") for d in (bc.get("datasets") or []) if isinstance(d, dict)]
    systems = sorted({s for (s, m, d) in agg if m == primary and d in datasets})
    direction = (bc.get("direction") or "higher_is_better") == "higher_is_better"

    import matplotlib.pyplot as plt

    # ---- Fig 1: main comparison, grouped bars with 95% CI ----
    if systems and datasets:
        fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
        width = 0.8 / max(len(systems), 1)
        for i, s in enumerate(systems):
            xs, means, cis = [], [], []
            for j, d in enumerate(datasets):
                e = agg.get((s, primary, d))
                if e:
                    xs.append(j + i * width - 0.4 + width / 2)
                    means.append(e["mean"])
                    cis.append(1.96 * e["std"] / math.sqrt(e["n"]) if e["n"] > 1 else 0.0)
            ax.bar(xs, means, width=width * 0.92, yerr=cis, capsize=2, label=s)
        ax.set_xticks(range(len(datasets)))
        ax.set_xticklabels(datasets, rotation=12, fontsize=8)
        metric_label = f"{primary}（" + ("越高越好" if direction else "越低越好") + "）" if lang == "zh" else primary
        ax.set_ylabel(metric_label)
        ax.set_title(f"各系统 {primary} 对比（误差线为 95% 置信区间）" if lang == "zh" else f"{primary} by system (95% CI)")
        ax.legend(fontsize=7, loc="best")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        p = out_dir / "fig1_main_comparison.png"
        fig.savefig(p)
        plt.close(fig)
        written.append(p)

    # ---- Fig 2: per-seed paired delta distribution ----
    pairs = _per_seed_pairs(metrics, primary)
    if pairs:
        fig, axes = plt.subplots(1, len(pairs), figsize=(3.4 * len(pairs), 3.4), dpi=200, squeeze=False)
        for ax, (d, seeds) in zip(axes[0], pairs.items()):
            deltas = [p - b for p, b in seeds.values()]
            ax.hist(deltas, bins=40, alpha=0.75, edgecolor="none")
            mean_d = sum(deltas) / len(deltas)
            ax.axvline(0, color="gray", lw=1, ls="--")
            ax.axvline(mean_d, color="crimson", lw=1.5,
                       label=f"均值 {mean_d:+.4f}" if lang == "zh" else f"mean {mean_d:+.4f}")
            ax.set_title(d, fontsize=9)
            ax.set_xlabel(f"逐种子 Δ({primary})" if lang == "zh" else f"per-seed Δ({primary})", fontsize=8)
            ax.legend(fontsize=7)
        fig.suptitle("所提方法 − 词法基线的逐种子配对差值分布" if lang == "zh" else "Per-seed paired deltas (proposed − lexical)", fontsize=10)
        fig.tight_layout()
        p = out_dir / "fig2_delta_distribution.png"
        fig.savefig(p)
        plt.close(fig)
        written.append(p)

    # ---- Fig 3: robustness heatmap ----
    if len(systems) > 1 and len(datasets) > 1:
        fig, ax = plt.subplots(figsize=(6.4, 0.5 * len(systems) + 2.2), dpi=200)
        # column-normalize (min-max per dataset) so different scales are comparable
        norm = {}
        for d in datasets:
            vals = [agg[(s, primary, d)]["mean"] for s in systems if (s, primary, d) in agg]
            if not vals:
                continue
            lo, hi = min(vals), max(vals)
            for s in systems:
                if (s, primary, d) in agg:
                    norm[(s, d)] = (agg[(s, primary, d)]["mean"] - lo) / (hi - lo) if hi > lo else 0.5
        if norm:
            import numpy as np
            mat = np.array([[norm.get((s, d), float("nan")) for d in datasets] for s in systems])
            im = ax.imshow(mat, cmap="RdYlGn" if direction else "RdYlGn_r", vmin=0, vmax=1, aspect="auto")
            ax.set_xticks(range(len(datasets)))
            ax.set_xticklabels(datasets, rotation=12, fontsize=8)
            ax.set_yticks(range(len(systems)))
            ax.set_yticklabels(systems, fontsize=8)
            for i in range(len(systems)):
                for j in range(len(datasets)):
                    e = agg.get((systems[i], primary, datasets[j]))
                    if e:
                        ax.text(j, i, f"{e['mean']:.3f}", ha="center", va="center", fontsize=7)
            fig.colorbar(im, ax=ax, shrink=0.8,
                         label="数据集内相对位置（绿=优）" if lang == "zh" else "within-dataset rank (green=better)")
            ax.set_title(f"跨数据集稳健性（{primary}）" if lang == "zh" else f"Cross-dataset robustness ({primary})")
            fig.tight_layout()
            p = out_dir / "fig3_robustness.png"
            fig.savefig(p)
            plt.close(fig)
            written.append(p)

    (out_dir / "figures_manifest.json").write_text(
        json.dumps({"font": font, "figures": [p.name for p in written]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return written
