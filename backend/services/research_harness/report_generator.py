"""
ReportGenerator — 组装 research_report.md。

🔴 Conclusion 段硬编码（不经 LLM，最强诚实 gate，plan §8.3）：
- 执行失败 → 写失败，不造 metric。
- proposed < baseline → 写 negative result（合法发现）。
- 改进但证据不足 → 写"insufficient evidence"。
- 单 seed / 单数据集 → 禁止 "significantly outperforms"。
- papers < 5 → novelty claim 附 literature_coverage: insufficient。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config.settings import settings
from services.research_harness.sandbox_capabilities import (
    ALLOWED_PACKAGES,
    SENTENCE_TRANSFORMERS_AVAILABLE,
    SANDBOX_BACKEND_KIND,
)

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path(settings.data_dir) / "research_workspace"

FORBIDDEN_OVERCLAIM = ("significantly outperforms", "competitive", "promising", "state-of-the-art")


def _project_dir(project_id: str) -> Path:
    return WORKSPACE_ROOT / project_id


def _read(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else default
    except OSError:
        return default


def _count_papers(project_id: str) -> int:
    papers_path = _project_dir(project_id) / "literature" / "papers.jsonl"
    if not papers_path.exists():
        return 0
    try:
        return sum(1 for line in papers_path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _results_table(metrics: dict) -> str:
    results = metrics.get("results", []) or []
    if not results:
        return "_(no results — execution did not produce metric values)_\n"
    header = "| system | metric | value | n_test | dataset |\n|---|---|---|---|---|\n"
    rows = "".join(
        f"| {r.get('system_name', '')} | {r.get('metric_name', '')} | {r.get('metric_value', '')} "
        f"| {r.get('n_test', '')} | {r.get('dataset_name', '')} |\n"
        for r in results
    )
    return header + rows


def _baseline_block(metrics: dict) -> str:
    bc = metrics.get("baseline_comparison", {}) or {}
    datasets = bc.get("datasets") or []
    overall = bc.get("overall_beats_baseline")
    if not datasets:
        return f"Baseline comparison unavailable ({bc.get('note', 'no baseline/proposed pair')}).\n"
    lines = [
        f"- overall_beats_baseline: **{overall}** (direction: {bc.get('direction', 'higher_is_better')})\n"
    ]
    for d in datasets:
        lines.append(
            f"- {d['dataset']}: baseline **{d.get('baseline_system')}**={d['baseline_metric']} "
            f"vs proposed **{d.get('proposed_system')}**={d['proposed_metric']} "
            f"(Δ{d['delta']:+.3f}, beats={d['beats_baseline']}, "
            f"seeds b={d.get('n_seeds_baseline')}/p={d.get('n_seeds_proposed')})\n"
        )
    lines.append(f"- note: {bc.get('note', '')}\n")
    return "".join(lines)


def _stats_block(metrics: dict) -> str:
    stats = metrics.get("statistics")
    if not stats or not stats.get("significance_tests"):
        seed_count = (stats or {}).get("seed_count", 0)
        if seed_count:
            return (
                f"{seed_count} seed(s) per system, but fewer than 2 matched seeds for a paired test — "
                "no significance test reported; numbers are descriptive only.\n"
            )
        return (
            "Single-run aggregate metrics. **No significance test was performed** "
            "(paired tests require per-seed paired values). Numbers are descriptive only.\n"
        )
    sigs = stats.get("significance_tests", [])
    rows = "; ".join(
        f"{s.get('detail','')}: p={s.get('p_value')}, adj_p={s.get('adjusted_p_value')}, "
        f"significant={s.get('significant')}"
        for s in sigs
    )
    cis = stats.get("confidence_intervals", {})
    return (
        f"Paired sign-flip test (Holm-Bonferroni corrected across datasets), "
        f"{stats.get('seed_count')} matched seeds: {rows}\n"
        f"Confidence intervals: `{json.dumps(cis, ensure_ascii=False)}`\n"
        f"any_significant={stats.get('any_significant')}. {stats.get('power_note', '')}\n"
    )


def _abstention_block(metrics: dict) -> str:
    """弃权校准指标（descriptive；对应 reviewer must_have「报告一致性得分-正确性相关 + 弃权错误率」）。

    不做显著性检验（主指标 macro_f1 已做 paired test）；这里只把 spearman / error-at-abstain
    的 per-(dataset, system) seed 均值列出来，作为对假设「一致性得分能否校准弃权」的直接证据。
    """
    abstention = metrics.get("abstention_metrics") or {}
    if not abstention:
        return ""
    lines = [
        "Reviewer must_have: does the consistency score correlate with correctness, and does "
        "abstaining on the least-confident examples reduce the answered-set error rate? "
        "(descriptive — no significance test; the paired test above is on macro_f1.)\n"
    ]
    for metric, ds_map in abstention.items():
        direction = "higher is better" if "spearman" in metric else "lower is better"
        lines.append(f"\n**{metric}** ({direction}):")
        for ds in sorted(ds_map):
            sys_map = ds_map[ds]
            parts = [f"{sysn}={v}" for sysn, v in sorted(sys_map.items())]
            lines.append(f"- {ds}: " + ", ".join(parts))
    return "\n".join(lines) + "\n"


def _hardcoded_conclusion(metrics: dict, review: dict, paper_count: int) -> str:
    """🔴 硬定 Conclusion 段（plan §8.3），绝不走 LLM，绝不出现 overclaim 措辞。"""
    status = metrics.get("execution_status")
    bc = metrics.get("baseline_comparison", {}) or {}
    publish_gate = review.get("publish_gate", "no_evidence")

    lines: list[str] = []

    if status != "success":
        lines.append(
            "**Experiments failed to produce results.** No conclusions can be drawn. "
            "The generated code did not execute successfully after the repair budget was exhausted; "
            "this is reported honestly rather than fabricated."
        )
    else:
        overall = bc.get("overall_beats_baseline")
        stats = metrics.get("statistics") or {}
        any_sig = stats.get("any_significant")
        datasets = bc.get("datasets") or []
        ds_names = ", ".join(d["dataset"] for d in datasets) or "the evaluated datasets"

        # 哪些数据集有「显著且方向有利」的赢，哪些是输——用于 Mixed vs Negative 的区分。
        sig_tests = stats.get("significance_tests", []) or []
        def _ds_of(s: dict) -> str:
            detail = s.get("detail") or ""
            return detail.split("dataset=")[-1].split(":")[0] if "dataset=" in detail else ""
        sig_win_datasets = sorted({d for d in (_ds_of(s) for s in sig_tests if s.get("significant")) if d})
        lost_datasets = [d["dataset"] for d in datasets if d.get("beats_baseline") is False]

        if overall is True and any_sig:
            lines.append(
                f"The proposed method outperformed the baseline across {ds_names} with statistical "
                "support (paired sign-flip, Holm-corrected). This is a positive but preliminary result; "
                "broader replication is still warranted."
            )
        elif overall is True:
            lines.append(
                f"Results show improvement over the baseline across {ds_names}, but the improvement was "
                "**not statistically significant** (paired sign-flip, Holm-corrected, p≥0.05). The evidence "
                "is insufficient for any submission claim; more seeds and datasets are needed."
            )
        elif overall is False and sig_win_datasets:
            # 关键诚实修正：overall=False 不一定是「全负」——若某些数据集有显著有利提升，应报 Mixed，
            # 而不是笼统写「Negative Result / did not outperform」（那会掩盖单数据集的显著胜利）。
            lines.append(
                f"**Mixed Result**: the proposed method **significantly outperformed** the baseline on "
                f"{', '.join(sig_win_datasets)} (paired sign-flip, Holm-corrected), but did not win "
                f"uniformly — it failed to beat the baseline on {', '.join(lost_datasets) or 'the others'}. "
                "The hypothesis is supported on its target task(s) but does not generalize across all "
                "datasets. This is a valid, nuanced finding."
            )
        elif overall is False:
            lines.append(
                f"**Negative Result**: across {ds_names}, the proposed method did not outperform the "
                "baseline, and no dataset showed a statistically significant favorable improvement. This "
                "is a valid scientific finding — the hypothesis, as operationalized here, is not supported."
            )
        else:
            lines.append(
                f"Mixed result across {ds_names}: the proposed method beat the baseline on some datasets "
                "but not others. No uniform conclusion is supported."
            )

    # 单/多 seed + 显著性诚实说明
    stats = metrics.get("statistics") or {}
    seed_count = stats.get("seed_count")
    any_sig = stats.get("any_significant")
    if seed_count and any_sig:
        lines.append(
            f"\nBased on {seed_count} paired seeds per dataset with Holm-Bonferroni correction. "
            "The word \"significantly\" is used only where the corrected test supports it."
        )
    else:
        lines.append(
            "\nThe word \"significantly\" is deliberately avoided — no significance test supports any "
            "such claim at the corrected threshold."
        )

    # 文献覆盖不足标注
    if paper_count < 5:
        lines.append(
            "\n`literature_coverage: insufficient` — fewer than 5 papers were retrieved, so any novelty "
            "claim must be treated as preliminary."
        )
    return "\n".join(lines)


def _assert_no_overclaim(text: str) -> list[str]:
    """扫描报告里是否混入禁用 overclaim 措辞（LLM 片段可能带入），返回告警。"""
    lowered = text.lower()
    return [word for word in FORBIDDEN_OVERCLAIM if word in lowered]


def generate_research_report(
    project_id: str,
    idea: str,
    selected_hypothesis: dict,
    metrics: dict,
    review: dict,
    manager_decision: dict,
) -> Path:
    """读 workspace 文件组装 research_report.md，返回其路径。"""
    proj = _project_dir(project_id)
    paper_count = _count_papers(project_id)

    gap_map_md = _read(proj / "literature" / "gap_map.md")
    plan_md = _read(proj / "experiments" / "plan.md")
    reviewer_md = _read(proj / "reviews" / "reviewer_round_1.md")
    notes_md = _read(proj / "literature" / "notes.md")

    conclusion = _hardcoded_conclusion(metrics, review, paper_count)
    decision = manager_decision.get("decision", {}) or {}

    sections: list[str] = []
    sections.append(f"# Research Report: {idea}\n")
    sections.append(f"## TL;DR\n\n{manager_decision.get('conclusion', '')}\n")
    sections.append(f"- execution_status: **{metrics.get('execution_status')}**\n")
    bc = metrics.get("baseline_comparison", {}) or {}
    sections.append(
        f"- overall_beats_baseline: **{bc.get('overall_beats_baseline')}** "
        f"(direction: {bc.get('direction', 'higher_is_better')}; "
        f"{len(bc.get('datasets') or [])} dataset(s) compared)\n"
    )
    sections.append(f"- publish_gate: **{review.get('publish_gate', 'no_evidence')}**\n")
    sections.append(f"- papers retrieved: **{paper_count}**\n\n")

    sections.append("## Literature Context\n\n")
    sections.append(gap_map_md or "_(gap_map.md unavailable)_\n")
    sections.append("\n## Selected Hypothesis\n\n")
    sections.append(
        f"**{selected_hypothesis.get('title', '')}**\n\n"
        f"- research_question: {selected_hypothesis.get('research_question', '')}\n"
        f"- core_novelty: {selected_hypothesis.get('core_novelty', '')}\n"
        f"- proposed_method_sketch: {selected_hypothesis.get('proposed_method_sketch', '')}\n"
        f"- feasibility: {selected_hypothesis.get('feasibility', '')}\n\n"
    )

    sections.append("## Methods\n\n")
    sections.append(plan_md or "_(plan.md unavailable)_\n")
    sections.append(
        f"\n_Sandbox_: backend `{SANDBOX_BACKEND_KIND}`, allowed packages "
        f"`{ALLOWED_PACKAGES or 'stdlib-only'}`, "
        f"sentence-transformers available: `{SENTENCE_TRANSFORMERS_AVAILABLE}`.\n\n"
    )

    sections.append("## Results\n\n")
    sections.append(_results_table(metrics))
    sections.append("\n**Baseline comparison**\n\n")
    sections.append(_baseline_block(metrics))
    sections.append(f"\n_attempts_used: {metrics.get('attempts_used')}, "
                    f"repair_attempts: {metrics.get('repair_attempts')}, "
                    f"returncode: {metrics.get('returncode')}_\n\n")

    sections.append("## Statistical Analysis\n\n")
    sections.append(_stats_block(metrics))

    abstention = _abstention_block(metrics)
    if abstention:
        sections.append("\n## Abstention Calibration\n\n")
        sections.append(abstention)

    sections.append("## Reviewer Critique Summary\n\n")
    sections.append(reviewer_md or "_(reviewer_round_1.md unavailable)_\n")

    sections.append("\n## Follow-up\n\n")
    chosen = decision.get("selected_action")
    if chosen:
        sections.append(
            f"- selected must_have action: **{chosen.get('action', '')}** — {chosen.get('description', '')}\n"
            f"- classification: `{decision.get('follow_up_classification', '')}`\n"
        )
    else:
        sections.append("- No must_have follow-up was selected by the ResearchManager.\n")
    sections.append(
        f"- sandbox budget: {decision.get('sandbox_budget_seconds')}s on backend "
        f"`{decision.get('sandbox_backend')}`.\n"
    )

    sections.append("\n## Conclusion\n\n")
    sections.append(conclusion + "\n")

    sections.append("\n## Limitations & Future Work\n\n")
    stats = metrics.get("statistics") or {}
    seed_count = stats.get("seed_count")
    n_datasets = len(bc.get("datasets") or [])
    if seed_count:
        sections.append(
            f"- **Statistical power**: paired sign-flip test over {seed_count} bootstrap seeds per dataset, "
            f"Holm-Bonferroni corrected across {n_datasets} dataset(s). Bootstrap resampling of a fixed "
            "100-example slice bounds the detectable effect; larger held-out test sets would strengthen claims.\n"
        )
    else:
        sections.append("- **Single-run / under-seeded**: results are descriptive; no significance test was performed.\n")
    sections.append(
        f"- **Sandbox capability**: backend `{SANDBOX_BACKEND_KIND}`, allowed packages "
        f"`{ALLOWED_PACKAGES or 'stdlib-only'}`, sentence-transformers available: "
        f"`{SENTENCE_TRANSFORMERS_AVAILABLE}`.\n"
    )
    sections.append(
        f"- **Literature coverage**: {paper_count} papers retrieved"
        + (" (insufficient — novelty claims are preliminary)." if paper_count < 5 else ".") + "\n"
    )
    for req in review.get("required_experiments", []) or []:
        if isinstance(req, dict):
            sections.append(
                f"- Future work ({req.get('priority', '?')}): {req.get('action', '')} — "
                f"{req.get('description', '')}\n"
            )
    if notes_md:
        sections.append("\n<details><summary>Literature notes (raw)</summary>\n\n" + notes_md + "\n</details>\n")

    report_text = "".join(sections)
    overclaim_warnings = _assert_no_overclaim(report_text)
    if overclaim_warnings:
        # 仅 Conclusion 段是我们写的（已保证无 overclaim）；这里只记录 LLM 片段是否带入。
        logger.info("[ReportGenerator] overclaim words found in LLM-sourced sections: %s", overclaim_warnings)

    report_path = proj / "research_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    logger.info("[ReportGenerator] report written: %s", report_path)
    return report_path
