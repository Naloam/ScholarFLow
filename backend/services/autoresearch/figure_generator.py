"""Generate comparison charts from experiment result artifacts."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

from schemas.autoresearch import (
    AggregateSystemMetricResult,
    ResultArtifact,
    SweepEvaluationResult,
)

logger = logging.getLogger(__name__)


@dataclass
class GeneratedFigure:
    figure_id: str
    title: str
    caption: str
    latex_label: str
    relative_path: str
    section_hint: str = "Results"


class FigureGenerator:
    """Produce matplotlib figures from a ResultArtifact."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir / "figures"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_figures(self, artifact: ResultArtifact) -> list[GeneratedFigure]:
        figures: list[GeneratedFigure] = []
        if not artifact.aggregate_system_results:
            logger.info("figure_generator: no aggregate results, skipping figures")
            return figures

        fig = self._main_comparison_chart(artifact)
        if fig is not None:
            figures.append(fig)

        fig = self._seed_distribution_chart(artifact)
        if fig is not None:
            figures.append(fig)

        if artifact.sweep_results:
            fig = self._sweep_parameter_chart(artifact)
            if fig is not None:
                figures.append(fig)

        logger.info("figure_generator: generated %d figures", len(figures))
        return figures

    def _main_comparison_chart(self, artifact: ResultArtifact) -> GeneratedFigure | None:
        systems = artifact.aggregate_system_results
        if len(systems) < 2:
            return None
        metric = artifact.primary_metric
        names: list[str] = []
        means: list[float] = []
        stds: list[float] = []
        for system in systems:
            mean = system.mean_metrics.get(metric)
            if mean is None:
                continue
            names.append(system.system)
            means.append(mean)
            stds.append(system.std_metrics.get(metric, 0.0))

        if len(names) < 2:
            return None

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(max(6, len(names) * 1.5), 4))
        x = list(range(len(names)))
        bars = ax.bar(x, means, yerr=stds, capsize=4, color="#4C72B0", edgecolor="black", linewidth=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right")
        ax.set_ylabel(metric)
        ax.set_title(f"System Comparison on {metric}")

        for bar, mean_val in zip(bars, means):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{mean_val:.4f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

        fig.tight_layout()
        path = self.output_dir / "figure_1_comparison.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)

        best = artifact.best_system or names[0]
        return GeneratedFigure(
            figure_id="fig_comparison",
            title=f"Comparison of {len(names)} systems on {metric}",
            caption=(
                f"Mean {metric} across systems with error bars showing standard deviation. "
                f"The best-performing system is {best}."
            ),
            latex_label="fig:comparison",
            relative_path=f"figures/figure_1_comparison.png",
        )

    def _seed_distribution_chart(self, artifact: ResultArtifact) -> GeneratedFigure | None:
        seeds = artifact.per_seed_results
        if len(seeds) < 3:
            return None
        metric = artifact.primary_metric

        system_names: set[str] = set()
        for seed in seeds:
            for sys_result in seed.system_results:
                system_names.add(sys_result.system)

        data_by_system: dict[str, list[float]] = {name: [] for name in system_names}
        for seed in seeds:
            seed_data = {sr.system: sr.metrics.get(metric, float("nan")) for sr in seed.system_results}
            for name in system_names:
                data_by_system[name].append(seed_data.get(name, float("nan")))

        valid_systems = {k: v for k, v in data_by_system.items() if any(not math.isnan(x) for x in v)}
        if len(valid_systems) < 1:
            return None

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(max(6, len(valid_systems) * 1.5), 4))
        labels = list(valid_systems.keys())
        data = [valid_systems[k] for k in labels]

        bp = ax.boxplot(data, patch_artist=True, labels=labels)
        colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]
        for patch, color in zip(bp["boxes"], colors[: len(labels)]):
            patch.set_facecolor(color)

        ax.set_ylabel(metric)
        ax.set_title(f"Per-Seed {metric} Distribution")
        fig.tight_layout()

        path = self.output_dir / "figure_2_seed_distribution.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)

        return GeneratedFigure(
            figure_id="fig_seed_distribution",
            title=f"Per-seed {metric} distribution",
            caption=(
                f"Box plot showing the distribution of {metric} across {len(seeds)} random seeds "
                f"for each system. Wider boxes indicate higher variance."
            ),
            latex_label="fig:seed_distribution",
            relative_path="figures/figure_2_seed_distribution.png",
        )

    def _sweep_parameter_chart(self, artifact: ResultArtifact) -> GeneratedFigure | None:
        sweeps = artifact.sweep_results
        if len(sweeps) < 2:
            return None
        metric = artifact.primary_metric

        labels: list[str] = []
        scores: list[float] = []
        stds: list[float] = []
        for sweep in sweeps:
            if sweep.objective_score_mean is None:
                continue
            labels.append(sweep.label)
            scores.append(sweep.objective_score_mean)
            stds.append(sweep.objective_score_std or 0.0)

        if len(labels) < 2:
            return None

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2), 4))
        x = list(range(len(labels)))
        ax.plot(x, scores, "o-", color="#4C72B0", linewidth=2, markersize=6)
        ax.fill_between(
            x,
            [s - sd for s, sd in zip(scores, stds)],
            [s + sd for s, sd in zip(scores, stds)],
            alpha=0.2,
            color="#4C72B0",
        )
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ax.set_ylabel(metric)
        ax.set_title(f"Sweep Configuration vs {metric}")
        fig.tight_layout()

        path = self.output_dir / "figure_3_sweep.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)

        best_idx = scores.index(max(scores))
        return GeneratedFigure(
            figure_id="fig_sweep",
            title=f"Sweep parameter search on {metric}",
            caption=(
                f"Mean {metric} for each sweep configuration. Shaded area shows standard deviation. "
                f"Best configuration: {labels[best_idx]} ({scores[best_idx]:.4f})."
            ),
            latex_label="fig:sweep",
            relative_path="figures/figure_3_sweep.png",
        )
