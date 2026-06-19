"""
ExperimentEngineer — 实验计划 → 代码生成 → sandbox 执行 → repair → 统计。

所有"生成"环节（plan / codegen / repair）走真实 chat()；
结论 / 状态 / beats_baseline 由代码硬定，不走 LLM（诚实 gate，见 plan §4.3 / §8.3）。

主入口 ``run_experiment_engineer``：1 次初始生成 + 最多 3 次 repair = 最多 4 次执行。
失败即合法结果：3 次 repair 仍失败 → ``execution_status="failed_after_3_repairs"``，
不造任何假数据，带着"代码失败"进 Reviewer。
"""
from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path

from config.settings import settings
from schemas.autoresearch import ExecutionBackendSpec, SignificanceTestResult
from services.llm.client import chat
from services.llm.response_utils import get_message_content
from services.sandbox.runner import run_python_in_sandbox
from services.research_harness.sandbox_capabilities import (
    ALLOWED_PACKAGES,
    MAX_EXPERIMENT_SECONDS,
    SANDBOX_BACKEND_KIND,
    capability_note,
)
from services.research_harness.utils.stats import (
    confidence_interval,
    holm_bonferroni_adjustment,
    paired_sign_flip_test,
    power_style_analysis,
)

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path(settings.data_dir) / "research_workspace"

MAX_EXECUTIONS = 4  # 1 次初始 + 3 次 repair（对齐 plan §4.3 "N=3 repairs"）

# metric 名包含这些子串时为"越低越好"，影响 beats_baseline 方向。
LOWER_IS_BETTER_HINTS = ("error", "loss", "wer", "perplexity", "rmse", "mae", "cer", "mer")


# --------------------------------------------------------------------------- #
# workspace / prompt 解析（复用 Session 1 套路，见避坑清单 #1）
# --------------------------------------------------------------------------- #


def _project_dir(project_id: str) -> Path:
    return WORKSPACE_ROOT / project_id


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _candidate_base(project_id: str, candidate_subdir: str | None) -> Path:
    """Workspace root for one candidate's artifacts.

    ``candidate_subdir=None`` → the project root (the legacy single-hypothesis path:
    metrics/code/plan land at the top level, K=1 backward-compatible). When set
    (portfolio, K>1) the candidate's entire experiment subtree is isolated under
    ``candidates/<candidate_subdir>/`` so K candidates never contaminate each other.
    """
    base = _project_dir(project_id)
    if candidate_subdir:
        return _ensure_dir(base / "candidates" / candidate_subdir)
    return base


def _experiments_dir(project_id: str, candidate_subdir: str | None = None) -> Path:
    return _ensure_dir(_candidate_base(project_id, candidate_subdir) / "experiments")


def _code_dir(project_id: str, candidate_subdir: str | None = None) -> Path:
    return _ensure_dir(_candidate_base(project_id, candidate_subdir) / "code")


def _artifacts_dir(project_id: str, candidate_subdir: str | None = None) -> Path:
    return _ensure_dir(_candidate_base(project_id, candidate_subdir) / "artifacts")


def _artifacts_logs_dir(project_id: str, candidate_subdir: str | None = None) -> Path:
    return _ensure_dir(_artifacts_dir(project_id, candidate_subdir) / "logs")


def _load_prompt(name: str) -> str:
    # Session 6: centralized on BACKEND_ROOT so resolution is CWD / DATA_DIR independent.
    from services.research_harness.prompts import load_prompt

    return load_prompt(name)


# --------------------------------------------------------------------------- #
# Session 12: cross-domain routing
# --------------------------------------------------------------------------- #


def _domain_from(*sources: object) -> str | None:
    """First declared ``domain`` across hypothesis/plan dicts (else None).

    The hypothesis (tagged by the IdeaAgent) is the source of truth; the plan
    echoes it. Defaults to None → claim_verification path (backward compatible).
    """
    for s in sources:
        if isinstance(s, dict):
            d = str(s.get("domain") or "").strip().lower()
            if d:
                return d
    return None


def _domain_preamble(domain: str | None) -> str:
    """Override block prepended for non-claim domains so the static claim-specific
    prompt body (ST cosine / abstention / 'traverse 3 datasets') is neutralized."""
    d = (domain or "").strip().lower()
    if not d or d == "claim_verification":
        return ""
    return (
        f"\n\n## 🟢 DOMAIN ROUTING（domain={d}，覆盖下方 claim_verification 静态段）\n"
        f"本次实验属于 **{d}** 域。下方 prompt 模板里所有 claim-verification / 句向量 / "
        "abstention / 「遍历 3 个数据集」的静态描述**仅适用于 claim_verification 域，本次作废**。"
        "以本次追加的「本域方法提示」+「数据集注册表（本域）」为准：用本域数据集、本域方法、"
        "≥128 seed 配对 bootstrap，输出 `__RESULT__` 行"
        "（system_name/seed/metric_name/metric_value/n_test/dataset_name）。\n"
    )


def _read_plan_domain(project_id: str, candidate_subdir: str | None) -> str | None:
    """Domain recorded in experiments/plan.json (repair reads it for routing)."""
    try:
        plan_path = _experiments_dir(project_id, candidate_subdir) / "plan.json"
        if plan_path.exists():
            import json as _json

            return _domain_from(_json.loads(plan_path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return None


def _extract_json(content: str) -> object | None:
    """剥 ```json 包裹并 json.loads；失败返回 None（Session 1 套路）。"""
    if not content:
        return None
    text = content.strip()
    if "```" in text:
        # 取第一个代码块内容
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    text = text.strip()
    # 兜底：LLM 可能在 JSON 前后混入说明文字，截到首个 { / [ 到末尾
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start != -1 and text.rstrip().endswith(closer):
            text = text[start:]
            break
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_python_code(content: str) -> str:
    """从 LLM 回复里抽取 Python 代码（处理 ```python ``` 包裹）。"""
    text = content.strip()
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            block = parts[1]
            if block.startswith("python"):
                block = block[len("python"):]
            return block.strip()
    return text


def _detect_available_packages() -> list[str]:
    """Step 0 实测结果（见 sandbox_capabilities.ALLOWED_PACKAGES）。"""
    return list(ALLOWED_PACKAGES)


# --------------------------------------------------------------------------- #
# Step 3a：实验计划生成
# --------------------------------------------------------------------------- #


def generate_experiment_plan(
    project_id: str,
    idea: str,
    selected_hypothesis: dict,
    known_baselines: list[dict],
    available_packages: list[str],
    candidate_subdir: str | None = None,
) -> dict:
    """LLM 生成实验计划，写 experiments/plan.json + experiments/plan.md。"""
    ws = _experiments_dir(project_id, candidate_subdir)
    domain = _domain_from(selected_hypothesis)
    prompt_template = _load_prompt("experiment_planner_v1.md")
    prompt = _domain_preamble(domain) + (
        prompt_template
        .replace("{hypothesis_json}", json.dumps(selected_hypothesis, ensure_ascii=False, indent=2))
        .replace("{known_baselines_json}", json.dumps(known_baselines, ensure_ascii=False, indent=2))
    )
    # 追加实测能力说明 + 可用包清单（覆盖 prompt 模板里写死的"理想包"假设）。
    prompt += (
        "\n\n## 实测可用包（用于 sandbox_packages 字段）\n"
        f"available_packages = {available_packages or ['（仅 Python 标准库）']}\n"
    )
    prompt += capability_note(domain)

    logger.info("[ExperimentEngineer] generating plan for project=%s", project_id)
    content = get_message_content(chat([{"role": "user", "content": prompt}]))
    parsed = _extract_json(content)
    if not isinstance(parsed, dict):
        logger.error("[ExperimentEngineer] plan parse failed; raw=%s", (content or "")[:300])
        plan = {
            "dataset": {"name": "unknown", "source": "parse_failed", "load_code": "", "size_note": ""},
            "metrics": [],
            "systems": [],
            "statistical_tests": [],
            "success_criterion": "",
            "failure_criterion": "",
            "source": "fallback_after_parse_error",
        }
    else:
        plan = parsed

    # Session 12: persist the domain so repair + downstream steps route correctly.
    plan["domain"] = domain or "claim_verification"
    (ws / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (ws / "plan.md").write_text(_render_plan_md(plan, idea), encoding="utf-8")
    return plan


def _render_plan_md(plan: dict, idea: str) -> str:
    dataset = plan.get("dataset", {}) or {}
    metrics = plan.get("metrics", []) or []
    systems = plan.get("systems", []) or []
    lines = [f"# Experiment Plan\n\n**Idea**: {idea}\n"]
    lines.append(f"## Dataset\n- **name**: {dataset.get('name', '')}\n- **source**: {dataset.get('source', '')}\n")
    lines.append(f"- **size_note**: {dataset.get('size_note', '')}\n\n")
    lines.append("## Metrics\n")
    for m in metrics:
        tag = " (primary)" if m.get("primary") else ""
        lines.append(f"- {m.get('name', '')}{tag}\n")
    lines.append("\n## Systems\n")
    for s in systems:
        lines.append(f"- **{s.get('name', '')}** [{s.get('role', '')}]: {s.get('description', '')}\n")
    lines.append(f"\n## success_criterion\n{plan.get('success_criterion', '')}\n")
    lines.append(f"\n## failure_criterion\n{plan.get('failure_criterion', '')}\n")
    return "".join(lines)


# --------------------------------------------------------------------------- #
# Step 3b：实验代码生成
# --------------------------------------------------------------------------- #


def generate_experiment_code(
    project_id: str,
    plan: dict,
    selected_hypothesis: dict,
    available_packages: list[str],
    candidate_subdir: str | None = None,
) -> str:
    """LLM 生成 experiment.py 源码，写 code/experiment.py + code/requirements.txt。"""
    code_dir = _code_dir(project_id, candidate_subdir)
    domain = _domain_from(selected_hypothesis, plan)
    prompt_template = _load_prompt("experiment_codegen_v1.md")
    prompt = _domain_preamble(domain) + (
        prompt_template
        .replace("{plan_json}", json.dumps(plan, ensure_ascii=False, indent=2))
        .replace("{hypothesis_json}", json.dumps(selected_hypothesis, ensure_ascii=False, indent=2))
    )
    prompt += (
        "\n\n## 实测可用包（requirements）\n"
        f"available_packages = {available_packages or ['（仅 Python 标准库——不要写任何 import numpy/pandas/sklearn）']}\n"
    )
    prompt += capability_note(domain)

    logger.info("[ExperimentEngineer] generating code for project=%s", project_id)
    content = get_message_content(chat([{"role": "user", "content": prompt}]))
    code = _extract_python_code(content)
    if not code.strip():
        # 兜底：连代码都抽不到，写一个必然失败的最小骨架（让 repair 循环有机会救，或诚实失败）。
        code = (
            "# codegen returned empty — fallback skeleton\n"
            "def main():\n"
            "    raise RuntimeError('codegen produced empty experiment code')\n\n"
            "if __name__ == '__main__':\n    main()\n"
        )

    (code_dir / "experiment.py").write_text(code, encoding="utf-8")
    (code_dir / "requirements.txt").write_text(
        ("\n".join(available_packages) + "\n") if available_packages else "# no third-party packages (stdlib only)\n",
        encoding="utf-8",
    )
    return code


# --------------------------------------------------------------------------- #
# Step 3c：repair
# --------------------------------------------------------------------------- #


def repair_experiment_code(
    project_id: str, code: str, stderr: str, attempt: int, candidate_subdir: str | None = None
) -> str:
    """LLM 修复代码，返回修复后完整代码；追加记录到 experiments/repair_log.md。"""
    ws = _experiments_dir(project_id, candidate_subdir)
    domain = _read_plan_domain(project_id, candidate_subdir)
    prompt_template = _load_prompt("experiment_repair_v1.md")
    prompt = _domain_preamble(domain) + (
        prompt_template
        .replace("{stderr}", (stderr or "")[:6000])
        .replace("{code}", code)
        .replace("{attempt}", str(attempt))
    )
    prompt += capability_note(domain)

    logger.info("[ExperimentEngineer] repair attempt %d", attempt)
    content = get_message_content(chat([{"role": "user", "content": prompt}]))
    new_code = _extract_python_code(content)
    if not new_code.strip():
        logger.warning("[ExperimentEngineer] repair returned empty, keeping previous code")
        new_code = code  # 无法修复就保留原码，让下次执行暴露真实错误

    # 🔴 持久化最新代码到 code/experiment.py（可复现性 fix）：
    # 初始 codegen 若失败/超时只写了 fallback skeleton，后续 repair 在内存里改对了代码却没落盘，
    # 会导致磁盘上 experiment.py 与真正跑出结果的代码不一致（v0_citrag_04 GLM 限流时暴露）。
    # 每次 repair 都同步落盘，保证 on-disk == 即将运行的 code。
    try:
        (_code_dir(project_id, candidate_subdir) / "experiment.py").write_text(new_code, encoding="utf-8")
    except OSError as exc:
        logger.warning("[ExperimentEngineer] could not persist repaired experiment.py: %s", exc)

    log_entry = (
        f"\n## Repair attempt {attempt}\n\n"
        f"**Error output (truncated):**\n```\n{(stderr or '')[:2000]}\n```\n\n"
        f"**Root-cause note (from LLM):**\n{(content or '').split('```')[0].strip()[:1000]}\n\n"
    )
    # 追加（不覆盖）
    log_path = ws / "repair_log.md"
    if not log_path.exists():
        log_path.write_text("# Experiment Repair Log\n", encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(log_entry)
    return new_code


# --------------------------------------------------------------------------- #
# __RESULT__ 校验 / 归一化
# --------------------------------------------------------------------------- #


def _coerce_result_list(result: object) -> list[dict]:
    """list → 直接用；dict 带 'systems' → 取 systems；否则包成单元素。"""
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    if isinstance(result, dict):
        if isinstance(result.get("systems"), list):
            return [r for r in result["systems"] if isinstance(r, dict)]
        return [result]
    return []


def _is_nonempty_results(result: object) -> bool:
    rows = _coerce_result_list(result)
    if not rows:
        return False
    return all("metric_value" in row for row in rows)


def _normalize_results(result: object, dataset_name: str = "") -> list[dict]:
    """归一化 system 字段（兼容 n_test / n_test_examples 等变体）。"""
    rows = _coerce_result_list(result)
    normalized: list[dict] = []
    for row in rows:
        try:
            value = float(row.get("metric_value"))
        except (TypeError, ValueError):
            continue  # 缺数值的行丢弃（不造假）
        normalized.append(
            {
                "system_name": str(row.get("system_name", "unknown")),
                "metric_name": str(row.get("metric_name", "metric")),
                "metric_value": round(value, 6),
                "n_test": int(row.get("n_test") or row.get("n_test_examples") or 0),
                "dataset_name": str(row.get("dataset_name") or dataset_name or ""),
                "seed": int(row.get("seed") or 0),
            }
        )
    return normalized


# --------------------------------------------------------------------------- #
# 统计 / baseline 比较（诚实优先）
# --------------------------------------------------------------------------- #


def _role_by_name(plan: dict) -> dict[str, str]:
    """从 plan.systems 建 system_name → role 映射。"""
    mapping: dict[str, str] = {}
    for s in plan.get("systems", []) or []:
        name = str(s.get("name", "")).strip()
        if name:
            mapping[name] = str(s.get("role", "")).strip().lower()
    return mapping


def _find_by_role(results: list[dict], role_map: dict[str, str], role: str) -> dict | None:
    for row in results:
        name = row.get("system_name", "")
        if role_map.get(name) == role:
            return row
    return None


def _higher_is_better(metric_name: str) -> bool:
    name = (metric_name or "").lower()
    return not any(hint in name for hint in LOWER_IS_BETTER_HINTS)


def _role_of(system_name: str, role_map: dict[str, str]) -> str:
    """name → role：先查 plan 的 role_map，再用名称前缀启发式（容忍 LLM 命名漂移）。"""
    name = (system_name or "").lower()
    if system_name in role_map:
        return role_map[system_name]
    # Session 10: stronger_baseline is a DISTINCT system, not the comparison baseline —
    # its name contains "baseline", so guard it before the prefix heuristic to avoid
    # polluting the weak-baseline pool (only-add correctness fix).
    if "stronger" in name:
        return "stronger_baseline"
    for role in ("baseline", "proposed", "ablation"):
        if role in name:
            return role
    return ""


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# reviewer must_have（Session 4+）：弃权校准指标，与 macro_f1（主指标）并列上报。
ABSTENTION_METRICS: tuple[str, ...] = ("spearman_consistency_vs_label", "error_rate_at_20pct_abstain")


def _primary_metric(plan: dict, results: list[dict]) -> str:
    """主指标：plan 里标 primary 的那个；否则默认 macro_f1。comparison/significance 只对主指标做。"""
    for metric in plan.get("metrics", []) or []:
        if isinstance(metric, dict) and metric.get("primary"):
            name = str(metric.get("name") or "").strip()
            if name:
                return name
    return "macro_f1"


def _filter_primary_metric(results: list[dict], primary: str) -> list[dict]:
    return [row for row in results if row.get("metric_name") == primary]


def _compute_abstention_metrics(results: list[dict]) -> dict:
    """弃权校准指标（descriptive，不做显著性检验）：按 (dataset, system) 求 seed 均值。

    对应 reviewer must_have「报告一致性得分-正确性相关 + 不同弃权阈值下的错误率」。
    返回 {metric_name: {dataset: {system: mean_value}}}。
    """
    bucket: dict[str, dict[str, dict[str, list[float]]]] = {}
    for row in results:
        name = row.get("metric_name")
        if name not in ABSTENTION_METRICS:
            continue
        try:
            value = float(row["metric_value"])
        except (TypeError, ValueError, KeyError):
            continue
        bucket.setdefault(name, {}).setdefault(row.get("dataset_name") or "unknown", {}).setdefault(
            row.get("system_name") or "unknown", []
        ).append(value)
    return {
        metric: {
            ds: {sysn: round(sum(vals) / len(vals), 6) for sysn, vals in sys_map.items()}
            for ds, sys_map in ds_map.items()
        }
        for metric, ds_map in bucket.items()
    }


def _compute_baseline_comparison(
    results: list[dict],
    plan: dict,
    execution_status: str,
) -> dict:
    """多数据集 baseline 比较：每个数据集用 per-seed 均值；overall = 全部数据集都赢才算赢。

    只对**主指标**（默认 macro_f1）做；弃权指标走 _compute_abstention_metrics（descriptive）。
    """
    role_map = _role_by_name(plan)
    primary = _primary_metric(plan, results)
    results = _filter_primary_metric(results, primary)  # 只比主指标，避免与弃权指标混算
    metric_name = primary
    direction = "higher_is_better"

    # 按 (dataset, role) 收集 per-seed 值
    per_ds_role: dict[str, dict[str, list[float]]] = {}
    system_names: dict[str, dict[str, str]] = {}  # dataset -> role -> system_name
    for row in results:
        ds = row.get("dataset_name") or "unknown"
        role = _role_of(row.get("system_name", ""), role_map)
        if not role:
            continue
        per_ds_role.setdefault(ds, {}).setdefault(role, []).append(float(row["metric_value"]))
        system_names.setdefault(ds, {})[role] = row.get("system_name", "")
        if not metric_name:
            metric_name = row.get("metric_name", "metric")

    if metric_name:
        direction = "higher_is_better" if _higher_is_better(metric_name) else "lower_is_better"

    if execution_status != "success" or not per_ds_role:
        return {
            "metric_name": metric_name or "metric",
            "direction": direction,
            "overall_beats_baseline": None,
            "datasets": [],
            "note": "baseline comparison unavailable: execution failed or baseline/proposed result missing",
        }

    datasets_cmp: list[dict] = []
    beats_all: list[bool] = []
    for ds in sorted(per_ds_role):
        roles_here = per_ds_role[ds]
        b_vals = roles_here.get("baseline", [])
        p_vals = roles_here.get("proposed", [])
        if not b_vals or not p_vals:
            continue
        b_val = _mean(b_vals)
        p_val = _mean(p_vals)
        delta = p_val - b_val
        beats = (delta > 0) if direction == "higher_is_better" else (delta < 0)
        beats_all.append(beats)
        datasets_cmp.append({
            "dataset": ds,
            "baseline_system": system_names[ds].get("baseline"),
            "baseline_metric": round(b_val, 6),
            "proposed_system": system_names[ds].get("proposed"),
            "proposed_metric": round(p_val, 6),
            "delta": round(delta, 6),
            "beats_baseline": bool(beats),
            "n_seeds_baseline": len(b_vals),
            "n_seeds_proposed": len(p_vals),
        })

    overall = all(beats_all) if beats_all else None
    return {
        "metric_name": metric_name or "metric",
        "direction": direction,
        "overall_beats_baseline": overall,
        "datasets": datasets_cmp,
        "note": "per-seed means; significance in statistics.significance_tests" if datasets_cmp
        else "no baseline/proposed pair found in results",
    }


def _compute_stats(results: list[dict], plan: dict) -> dict | None:
    """multi-seed 真实统计：每个数据集 baseline vs proposed 配对符号检验 + CI + holm 修正。

    只对**主指标**（默认 macro_f1）做；弃权指标走 descriptive abstention_metrics。
    """
    role_map = _role_by_name(plan)
    primary = _primary_metric(plan, results)
    results = _filter_primary_metric(results, primary)
    metric_name = primary

    # (dataset, role) -> {seed: value}
    per_ds_role_seed: dict[str, dict[str, dict[int, float]]] = {}
    seed_counts: list[int] = []
    metric_name = "metric"
    for row in results:
        ds = row.get("dataset_name") or "unknown"
        role = _role_of(row.get("system_name", ""), role_map)
        if role not in ("baseline", "proposed", "ablation"):
            continue
        seed = int(row.get("seed", 0))
        per_ds_role_seed.setdefault(ds, {}).setdefault(role, {})[seed] = float(row["metric_value"])
        metric_name = row.get("metric_name", metric_name)

    direction = "higher_is_better" if _higher_is_better(metric_name) else "lower_is_better"

    sig_results: list[SignificanceTestResult] = []
    cis: dict[str, dict | None] = {}
    for ds in sorted(per_ds_role_seed):
        roles = per_ds_role_seed[ds]
        b_seeded = roles.get("baseline", {})
        p_seeded = roles.get("proposed", {})
        common = sorted(set(b_seeded) & set(p_seeded))
        seed_counts.append(len(common))
        # CI on proposed per-seed values
        p_vals = [p_seeded[s] for s in common] or list(p_seeded.values())
        ci = confidence_interval(p_vals)
        cis[f"{ds}:proposed"] = ({"lower": ci.lower, "upper": ci.upper} if ci else None)
        b_vals_all = [b_seeded[s] for s in common] or list(b_seeded.values())
        ci_b = confidence_interval(b_vals_all)
        cis[f"{ds}:baseline"] = ({"lower": ci_b.lower, "upper": ci_b.upper} if ci_b else None)
        if len(common) >= 2:
            b_series = [b_seeded[s] for s in common]
            p_series = [p_seeded[s] for s in common]
            # paired_sign_flip_test(a, b) → effect_size = mean(a - b)；传 (proposed, baseline)
            # 使 effect_size = proposed - baseline（proposed 更好时为正，higher_is_better 下 >0）。
            p_value, alternative, effect_size, n_pairs, method = paired_sign_flip_test(p_series, b_series)
            diffs = [p_series[i] - b_series[i] for i in range(len(common))]
            power = power_style_analysis(diffs)
            significant = bool(p_value < 0.05) and bool(
                (effect_size > 0) if direction == "higher_is_better" else (effect_size < 0)
            )
            sig_results.append(SignificanceTestResult(
                scope="system",
                metric=metric_name,
                candidate="proposed",
                comparator="baseline",
                alternative=alternative,
                method=method,
                p_value=p_value,
                effect_size=effect_size,
                significant=significant,
                sample_count=n_pairs,
                adequately_powered=power.get("adequately_powered"),
                minimum_detectable_effect=power.get("minimum_detectable_effect"),
                recommended_sample_count=power.get("recommended_sample_count"),
                power_detail=power.get("power_detail"),
                detail=f"dataset={ds}: paired sign-flip over {n_pairs} seeds, "
                       f"proposed-baseline mean delta={effect_size:.4f}",
            ))

    if not sig_results:
        # 多 seed 但 baseline/proposed 配对不足 → 仍记录 CI 与 seed 数，但不报 p
        return {
            "seed_count": max(seed_counts) if seed_counts else 0,
            "significance_tests": [],
            "confidence_intervals": cis,
            "holm_corrected": [],
            "power_note": "insufficient matched seeds (<2) for a paired test; only descriptive CIs reported",
        }

    corrected = holm_bonferroni_adjustment(sig_results)
    # 🔴 方向感知的 significant（honesty fix）：
    # holm_bonferroni_adjustment 只按 adjusted_p<0.05 判 significant，不看效应方向。这会把
    # 「proposed 显著更差」也标成 significant=True（v0_citrag_04 vitaminc 暴露：Δ-0.032 p=0.014），
    # 从而错误地抬高 any_significant。这里按方向复判：significant = (adj_p<0.05) AND (效应在更优方向)。
    final_rows: list[tuple[SignificanceTestResult, dict, bool]] = []
    for r in corrected:
        favorable = (r.effect_size > 0) if direction == "higher_is_better" else (r.effect_size < 0)
        adj_p = r.adjusted_p_value
        is_sig = bool((adj_p is not None and adj_p < 0.05) and favorable)
        rd = r.model_dump()
        rd["significant"] = is_sig
        final_rows.append((r, rd, is_sig))
    any_significant = any(is_sig for _, _, is_sig in final_rows)
    return {
        "seed_count": max(seed_counts) if seed_counts else 0,
        "significance_tests": [rd for _, rd, _ in final_rows],
        "confidence_intervals": cis,
        "holm_corrected": [
            {"dataset": r.detail.split("dataset=")[-1].split(":")[0] if "dataset=" in r.detail else "?",
             "adjusted_p_value": r.adjusted_p_value, "significant": is_sig}
            for r, _, is_sig in final_rows
        ],
        "any_significant": bool(any_significant),
        "power_note": "paired sign-flip test per dataset; Holm-Bonferroni corrected across datasets; "
                      "significant requires the effect to be in the favorable direction",
    }


# --------------------------------------------------------------------------- #
# 落盘
# --------------------------------------------------------------------------- #


# V2.2 hypothesis-contract signals (goal_session8.md Step 5):
#  - missing_baselines: comparison systems the hypothesis NAMES (in expected outcome /
#    kill criteria) but that were NOT generated/run → recorded honestly, never silent.
#  - underpowered: ran fewer seeds than the power analysis recommended.
_GENERIC_NAME_STARTS: frozenset[str] = frozenset(
    {"the", "our", "we", "this", "these", "those", "that", "a", "an", "if", "when",
     "for", "with", "without", "each", "some", "any", "all", "no", "not", "note"}
)
_NAMED_SYSTEM_RE = re.compile(r"[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,4}")


def _extract_named_systems(text: str) -> set[str]:
    """Capitalized multi-word phrases in ``text`` that look like named systems/
    baselines (e.g. 'Sufficient Context Classifier', 'Calibrated Softmax')."""
    candidates: set[str] = set()
    for m in _NAMED_SYSTEM_RE.finditer(text or ""):
        phrase = m.group(0).strip()
        words = phrase.split()
        if words[0].lower() in _GENERIC_NAME_STARTS:
            continue
        if not any(len(w) >= 4 for w in words):
            continue
        candidates.add(phrase)
    return candidates


def _existing_system_names(results: list[dict], plan: dict) -> set[str]:
    names: set[str] = set()
    for r in results or []:
        if isinstance(r, dict):
            names.add(str(r.get("system_name", "")))
    for s in (plan.get("systems") if isinstance(plan, dict) else None) or []:
        if isinstance(s, dict):
            names.add(str(s.get("name", "")))
    return names


def _phrase_matches_existing(phrase: str, names: set[str]) -> bool:
    """Does ``phrase`` correspond to a system that actually ran (token overlap)?"""
    cand = {w.lower() for w in re.split(r"[\s_\-]+", phrase) if len(w) >= 4}
    if not cand:
        return False
    for name in names:
        if not name:
            continue
        name_tokens = {w.lower() for w in re.split(r"[\s_\-]+", name) if len(w) >= 4}
        if cand & name_tokens:
            return True
    return False


def _detect_missing_baselines(
    hypothesis: dict | None, results: list[dict], plan: dict
) -> list[str]:
    """Comparison systems the hypothesis names but that did not run.

    Extracts Capitalized named systems from the hypothesis's expected-outcome /
    kill-criteria text and flags any with no matching system in the results/plan.
    Returns ``[]`` when there is no hypothesis.
    """
    if not hypothesis:
        return []
    text = " ".join(
        [
            str(hypothesis.get("expected_positive_outcome", "")),
            str(hypothesis.get("expected_negative_outcome", "")),
            " ".join(str(c) for c in (hypothesis.get("kill_criteria") or [])),
        ]
    )
    candidates = _extract_named_systems(text)
    names = _existing_system_names(results, plan)
    missing = [c for c in sorted(candidates) if not _phrase_matches_existing(c, names)]
    return missing


def _underpowered_note(metrics: dict) -> dict | None:
    """If the run used fewer seeds than the power analysis recommended, return a
    descriptive ``underpowered`` marker; else ``None``. Pure, deterministic."""
    stats = metrics.get("statistics") or {}
    ran = stats.get("seed_count")
    recommended = None
    for t in stats.get("significance_tests") or []:
        if isinstance(t, dict) and t.get("recommended_sample_count"):
            recommended = t["recommended_sample_count"]
            break
    if recommended and ran is not None and ran < recommended:
        return {
            "underpowered": True,
            "ran_seeds": int(ran),
            "recommended_seeds": int(recommended),
            "note": f"underpowered: ran {ran} of recommended {recommended} seeds",
        }
    return None


# --------------------------------------------------------------------------- #
# V2.2 reviewer → follow-up loop (goal_session8.md Step 6)
# --------------------------------------------------------------------------- #


def _load_plan_json(project_id: str) -> dict:
    path = _experiments_dir(project_id) / "plan.json"
    if path.exists():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _merge_followup_plan(base_plan: dict, action: str, new_rows: list[dict]) -> dict:
    """Add the follow-up systems to the plan's system list so role-aware stat /
    comparison recomputation treats them correctly. Roles are inferred from the
    reviewer action (stronger baseline → 'baseline', ablation → 'ablation')."""
    plan = dict(base_plan) if isinstance(base_plan, dict) else {}
    systems = [s for s in (plan.get("systems") or []) if isinstance(s, dict)]
    existing = {str(s.get("name", "")) for s in systems}
    a = (action or "").lower()
    inferred_role = "baseline" if "baseline" in a else ("ablation" if "ablation" in a else "")
    for r in new_rows:
        name = str(r.get("system_name", ""))
        if name and name not in existing:
            systems.append({"name": name, "role": inferred_role})
            existing.add(name)
    plan["systems"] = systems
    return plan


def _generate_followup_code(
    project_id: str,
    idea: str,
    selected: dict,
    follow_up_req: dict,
    base_metrics: dict,
    available_packages: list[str],
) -> str:
    """LLM-generate a self-contained follow-up experiment (the new system only)."""
    action = follow_up_req.get("action", "")
    description = follow_up_req.get("description", "")
    existing = {
        "dataset": base_metrics.get("dataset"),
        "systems_run": sorted({str(r.get("system_name", "")) for r in base_metrics.get("results", []) if isinstance(r, dict)}),
    }
    prompt = (
        "You are adding ONE follow-up experiment to an existing research project, requested by "
        "an automated reviewer. Do NOT re-run systems that already ran — run ONLY the new system.\n\n"
        f"Requested action: {action}\nDescription: {description}\n\n"
        f"Hypothesis: {json.dumps(selected, ensure_ascii=False)}\n"
        f"Already-run systems / dataset: {json.dumps(existing, ensure_ascii=False)}\n\n"
        f"Allowed packages: {available_packages or ['Python standard library only']}\n"
        "Write a SELF-CONTAINED Python script that runs the new follow-up system on the SAME small "
        "public dataset and prints exactly one line:\n"
        "  print('__RESULT__', json.dumps([{'system_name': ..., 'metric_name': ..., 'metric_value': ..., "
        "'n_test': ..., 'dataset_name': ..., 'seed': ...}]))\n"
        "Stay well within a small time budget (no GPU, no large downloads). "
        "Output ONLY the python code in a single ```python block.\n"
    )
    content = get_message_content(chat([{"role": "user", "content": prompt}]))
    code = _extract_python_code(content)
    if not code.strip():
        code = (
            "# follow-up codegen returned empty — honest failure skeleton\n"
            "def main():\n    raise RuntimeError('follow-up codegen produced empty code')\n\n"
            "if __name__ == '__main__':\n    main()\n"
        )
    return code


def run_follow_up(
    project_id: str,
    idea: str,
    selected: dict,
    follow_up_req: dict,
    base_metrics: dict,
) -> tuple[dict, dict]:
    """Run ONE bounded follow-up experiment and merge it into ``base_metrics``.

    Generates + executes a single follow-up system (no repair loop — bounded to one
    attempt), then recomputes the baseline comparison / abstention / statistics over
    the combined result rows. On any failure the base metrics are returned unchanged
    with ``ran=False`` (no fabricated data). Returns ``(merged_metrics, follow_up_log)``.
    """
    action = follow_up_req.get("action", "")
    available_packages = _detect_available_packages()
    code = _generate_followup_code(project_id, idea, selected, follow_up_req, base_metrics, available_packages)

    try:
        combined, outputs = run_python_in_sandbox(
            project_id,
            code=code,
            execution_backend=ExecutionBackendSpec(kind=SANDBOX_BACKEND_KIND, timeout_seconds=MAX_EXPERIMENT_SECONDS),
        )
    except Exception as exc:  # noqa: BLE001 — follow-up is best-effort, never fatal
        logger.warning("[ExperimentEngineer] follow-up execution failed: %s", exc)
        return base_metrics, {"ran": False, "action": action, "reason": f"execution error: {exc}"}

    result = outputs.get("result")
    if outputs.get("returncode") != 0 or not _is_nonempty_results(result):
        logger.info(
            "[ExperimentEngineer] follow-up produced no results: %s",
            (outputs.get("stderr") or combined or "")[:200],
        )
        return base_metrics, {"ran": False, "action": action, "reason": "follow-up experiment did not produce results"}

    new_rows = _normalize_results(result, base_metrics.get("dataset", ""))
    base_plan = _load_plan_json(project_id)
    merged_plan = _merge_followup_plan(base_plan, action, new_rows)
    merged_results = list(base_metrics.get("results") or []) + new_rows

    merged = dict(base_metrics)
    merged["results"] = merged_results
    merged["baseline_comparison"] = _compute_baseline_comparison(merged_results, merged_plan, "success")
    merged["abstention_metrics"] = _compute_abstention_metrics(merged_results)
    merged["statistics"] = _compute_stats(merged_results, merged_plan)
    systems_added = sorted({str(r.get("system_name", "")) for r in new_rows})
    merged["follow_up"] = {
        "ran": True,
        "action": action,
        "description": follow_up_req.get("description", ""),
        "systems_added": systems_added,
    }
    logger.info("[ExperimentEngineer] follow-up merged: %s", systems_added)
    return merged, merged["follow_up"]


def _write_metrics_json(project_id: str, metrics: dict, candidate_subdir: str | None = None) -> None:
    (_artifacts_dir(project_id, candidate_subdir) / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_results_csv(project_id: str, results: list[dict], candidate_subdir: str | None = None) -> None:
    tables = _ensure_dir(_artifacts_dir(project_id, candidate_subdir) / "tables")
    path = tables / "results.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["system_name", "metric_name", "metric_value", "n_test", "dataset_name", "seed"],
        )
        writer.writeheader()
        for row in results:
            writer.writerow(row)


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #


def run_experiment_engineer(
    project_id: str,
    idea: str,
    literature_notes: dict,
    selected_hypothesis: dict,
    candidate_subdir: str | None = None,
) -> dict:
    """完整执行循环：plan → codegen → run(+repair) → 统计 → metrics.json。

    ``candidate_subdir`` isolates this candidate's artifacts under
    ``candidates/<id>/`` (portfolio, K>1). ``None`` writes to the top-level workspace
    (the legacy single-hypothesis path, K=1 backward-compatible).
    """
    available_packages = _detect_available_packages()
    known_baselines = literature_notes.get("known_baselines", []) or []

    plan = generate_experiment_plan(
        project_id, idea, selected_hypothesis, known_baselines, available_packages, candidate_subdir
    )
    code = generate_experiment_code(
        project_id, plan, selected_hypothesis, available_packages, candidate_subdir
    )

    logs_dir = _artifacts_logs_dir(project_id, candidate_subdir)
    dataset_name = (plan.get("dataset") or {}).get("name", "")

    raw_results: list[dict] = []
    execution_status = "failed_after_3_repairs"
    last_outputs: dict = {}
    attempts_used = 0
    repair_attempts = 0

    for execution_index in range(1, MAX_EXECUTIONS + 1):
        attempts_used = execution_index
        logger.info("[ExperimentEngineer] execution %d/%d", execution_index, MAX_EXECUTIONS)
        combined, outputs = run_python_in_sandbox(
            project_id,
            code=code,
            execution_backend=ExecutionBackendSpec(
                kind=SANDBOX_BACKEND_KIND,
                timeout_seconds=MAX_EXPERIMENT_SECONDS,
            ),
        )
        last_outputs = outputs
        (logs_dir / f"run_{execution_index}.log").write_text(combined or "", encoding="utf-8")

        result = outputs.get("result")
        if outputs.get("returncode") == 0 and _is_nonempty_results(result):
            raw_results = _normalize_results(result, dataset_name)
            execution_status = "success"
            logger.info("[ExperimentEngineer] SUCCESS on execution %d (%d systems)", execution_index, len(raw_results))
            break

        # 失败：还能 repair 吗？
        if execution_index < MAX_EXECUTIONS:
            stderr_for_repair = outputs.get("stderr") or combined
            # 超时单独标注，提示 repair 缩小数据集
            if outputs.get("executor_mode") == "error" or "TimeoutExpired" in str(stderr_for_repair):
                stderr_for_repair = f"[TIMEOUT/EXEC-ERROR detected — shrink test set to <=500, lower complexity]\n{stderr_for_repair}"
            code = repair_experiment_code(project_id, code, stderr_for_repair, execution_index, candidate_subdir)
            repair_attempts += 1
        else:
            execution_status = "failed_after_3_repairs"
            logger.warning("[ExperimentEngineer] FAILED after %d executions", execution_index)
            break

    baseline_comparison = _compute_baseline_comparison(raw_results, plan, execution_status)
    statistics = _compute_stats(raw_results, plan) if raw_results else None
    abstention_metrics = _compute_abstention_metrics(raw_results) if raw_results else {}

    # V2.2 hypothesis-contract signals (goal_session8.md Step 5).
    missing_baselines = _detect_missing_baselines(selected_hypothesis, raw_results, plan)
    underpowered = _underpowered_note({"statistics": statistics} if statistics else {})

    metrics = {
        "execution_status": execution_status,
        "dataset": dataset_name,
        "results": raw_results,
        "baseline_comparison": baseline_comparison,
        "abstention_metrics": abstention_metrics,
        "missing_baselines": missing_baselines,
        "underpowered": underpowered,
        "attempts_used": attempts_used,
        "repair_attempts": repair_attempts,
        "returncode": last_outputs.get("returncode"),
        "statistics": statistics,
    }
    _write_metrics_json(project_id, metrics, candidate_subdir)
    _write_results_csv(project_id, raw_results, candidate_subdir)
    logger.info(
        "[ExperimentEngineer] done: status=%s beats_baseline=%s",
        execution_status, baseline_comparison.get("beats_baseline"),
    )
    return metrics
