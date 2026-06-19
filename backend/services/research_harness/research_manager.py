"""
ResearchManager（纯逻辑版，本 session 不调 LLM）。

plan §4.3 Step6 允许纯逻辑实现。这样做的好处：结论完全可预测、不再多一次 LLM 往返、
且结论字符串严格走 §8.3 诚实 gate（不经过 LLM，无法被"润色"成 promising）。

三件事：
1. 选 follow-up：从 review.required_experiments 取第一个 must_have，按 sandbox 能力分类。
2. 生成结论字符串（纯逻辑 §8.3 gate）。
3. 落盘 action_plan_1.json（若 reviewer 未写）+ conclusion.md。

``research_manager_v1.md`` 本次不调用（保留备用）。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config.settings import settings
from services.research_harness import evidence
from services.research_harness.sandbox_capabilities import (
    MAX_EXPERIMENT_SECONDS,
    SANDBOX_BACKEND_KIND,
)

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path(settings.data_dir) / "research_workspace"

# 单次执行约耗时长阈值（秒）：首跑若显著短于此，test_on_second_dataset 可在 session3 自动跑。
SECOND_DATASET_BUDGET_THRESHOLD = 300


def _reviews_dir(project_id: str) -> Path:
    p = WORKSPACE_ROOT / project_id / "reviews"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _first_must_have(required_experiments: list) -> dict | None:
    for req in required_experiments or []:
        if isinstance(req, dict) and str(req.get("priority", "")).lower() == "must_have":
            return req
    return None


def _classify_follow_up(action: str, first_run_duration_seconds: float | None) -> str:
    """按 sandbox 能力给 follow-up 分类。

    返回值之一：
    - pending_session_3       —— sandbox 能做，但本轮不再循环（add_stronger_baseline / run_ablation）
    - feasible_in_budget      —— test_on_second_dataset 且首跑够快
    - pending_session_3       —— test_on_second_dataset 但首跑偏慢（仍留给 session3）
    - requires_manual_execution —— 需要 GPU / 大数据 / 人工，sandbox 做不了
    """
    a = (action or "").strip().lower()
    if a == "test_on_second_dataset":
        if first_run_duration_seconds is not None and first_run_duration_seconds < SECOND_DATASET_BUDGET_THRESHOLD:
            return "feasible_in_budget"
        return "pending_session_3"
    if a in {"add_stronger_baseline", "run_ablation", "improve_statistical_power"}:
        return "pending_session_3"
    return "requires_manual_execution"


def _build_conclusion(metrics: dict, hypothesis: dict | None = None) -> str:
    """结论字符串硬定（§8.3 gate），不经 LLM。

    With ``hypothesis`` the head reflects the hypothesis-anchored verdict
    (:func:`evidence.full_verdict`): a downgrade (primary metric lost / kill
    criterion tripped) is stated explicitly so the TL;DR can never claim success
    on a cherry-picked generic metric.
    """
    status = metrics.get("execution_status")
    bc = metrics.get("baseline_comparison", {}) or {}

    if status != "success":
        return "Experiment failed to execute after 3 repair attempts. No results."

    datasets = bc.get("datasets") or []
    overall = bc.get("overall_beats_baseline")
    stats = metrics.get("statistics") or {}
    any_sig = stats.get("any_significant")

    if not datasets:
        return "Result inconclusive: no baseline/proposed comparison available from the metrics."

    parts = []
    for d in datasets:
        parts.append(
            f"{d['dataset']}: proposed {d['proposed_metric']:.3f} vs baseline {d['baseline_metric']:.3f} "
            f"(Δ{d['delta']:+.3f}, beats_baseline={d['beats_baseline']})"
        )
    summary = "; ".join(parts)

    fv = evidence.full_verdict(metrics, hypothesis)
    if overall is False:
        head = "NEGATIVE RESULT"
    elif overall is True and any_sig:
        head = "POSITIVE RESULT (statistically significant, Holm-corrected)"
    elif overall is True:
        head = "Positive trend across datasets (descriptive; significance not established)"
    else:
        head = "Mixed result across datasets"
    sig_note = "" if any_sig else " No statistically significant improvement (paired sign-flip, Holm-corrected, p≥0.05)."
    base_conclusion = f"{head}: {summary}.{sig_note}"

    if hypothesis is not None and fv["downgraded"]:
        tripped = [k for k in fv["kill_criteria"] if k.get("tripped")]
        anchor = (
            f" HYPOTHESIS-ANCHORED DOWNGRADE to {fv['verdict'].upper()}: the primary metric "
            f"'{fv['primary_metric']}' (beats_baseline={fv['primary_beats_baseline']}) did not meet "
            f"its bar, so the '{head}' framing above (on a generic metric) does not hold."
        )
        if tripped:
            anchor += " Kill criterion tripped: " + "; ".join(f"“{k['criterion']}”" for k in tripped) + "."
        return base_conclusion + anchor
    return base_conclusion


def _select_follow_up(review: dict) -> dict | None:
    """First ``priority=must_have`` required_experiment, or None."""
    for req in review.get("required_experiments", []) or []:
        if isinstance(req, dict) and str(req.get("priority", "")).lower() == "must_have":
            return req
    return None


# V2.2 (goal_session8.md Step 6): resources that place a follow-up outside the sandbox budget.
_INFEASIBLE_KEYWORDS: tuple[str, ...] = (
    "gpu", "cuda", "large dataset", "large-scale", "multi-day", "multiday",
    "external api", "external-api", "pretrained language model", "billion",
    "cloud", "manual annotation", "manual evaluation",
)


def _follow_up_feasibility(req: dict) -> dict:
    """Is this required_experiment runnable inside the sandbox budget?"""
    blob = f"{str(req.get('action', '')).lower()} {str(req.get('description', '')).lower()}"
    for kw in _INFEASIBLE_KEYWORDS:
        if kw in blob:
            return {"feasible": False, "reason": f"requires resources outside the sandbox budget ({kw})"}
    return {"feasible": True, "reason": "action is runnable within the sandbox budget"}


def run_research_manager(
    project_id: str,
    idea: str,
    selected_hypothesis: dict,
    metrics: dict,
    review: dict,
) -> dict:
    """Follow-up decision + conclusion generation.

    V2.2 (goal_session8.md Step 6): the first FEASIBLE ``must_have`` required_experiment
    is run as a single bounded follow-up (results merged into metrics + persisted); every
    INFEASIBLE ``must_have`` is recorded as Future Work with its reason. At most one
    follow-up round — never an open loop. The merged metrics are returned so the report
    reflects the follow-up.
    """
    reviews = _reviews_dir(project_id)
    required_experiments = review.get("required_experiments", []) or []
    must_haves = [
        r for r in required_experiments
        if isinstance(r, dict) and str(r.get("priority", "")).lower() == "must_have"
    ]

    future_work: list[dict] = []
    run_target: dict | None = None
    for req in must_haves:
        feas = _follow_up_feasibility(req)
        if not feas["feasible"]:
            future_work.append({
                "action": req.get("action"),
                "description": req.get("description"),
                "reason": feas["reason"],
            })
        elif run_target is None:
            run_target = req  # the single follow-up we will actually run

    chosen = _select_follow_up(review)
    first_run_duration = _estimate_first_run_seconds(project_id)
    classification = (
        _classify_follow_up(chosen.get("action", ""), first_run_duration) if chosen else "none_must_have"
    )

    # ≤1 bounded follow-up run (feasible must_have only).
    follow_up_ran = False
    follow_up_log: dict | None = None
    merged_metrics = metrics
    if run_target is not None:
        try:
            from services.research_harness import experiment_engineer

            merged_metrics, follow_up_log = experiment_engineer.run_follow_up(
                project_id, idea, selected_hypothesis, run_target, metrics,
            )
            follow_up_ran = bool((follow_up_log or {}).get("ran"))
            if follow_up_ran:
                metrics_path = WORKSPACE_ROOT / project_id / "artifacts" / "metrics.json"
                metrics_path.parent.mkdir(parents=True, exist_ok=True)
                metrics_path.write_text(
                    json.dumps(merged_metrics, ensure_ascii=False, indent=2), encoding="utf-8",
                )
        except Exception as exc:  # noqa: BLE001 — follow-up is non-fatal; honest report never blocked
            logger.warning("[ResearchManager] follow-up run failed (non-fatal): %s", exc)
            follow_up_ran = False
            merged_metrics = metrics

    decision = {
        "selected_action": chosen,
        "follow_up_classification": classification,
        "follow_up_ran": follow_up_ran,
        "follow_up_target": run_target,
        "future_work": future_work,
        "sandbox_backend": SANDBOX_BACKEND_KIND,
        "sandbox_budget_seconds": MAX_EXPERIMENT_SECONDS,
    }
    conclusion = _build_conclusion(merged_metrics, selected_hypothesis)

    # action_plan_1.json（若 reviewer 未写则补）
    action_plan_path = reviews / "action_plan_1.json"
    if not action_plan_path.exists():
        action_plan_path.write_text(
            json.dumps({"required_experiments": required_experiments}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # conclusion.md
    conclusion_lines = [
        f"# Research Conclusion\n\n**Idea**: {idea}\n\n",
        f"**Selected hypothesis**: {selected_hypothesis.get('title', '')}\n\n",
        f"**Execution status**: {merged_metrics.get('execution_status', '')}\n\n",
        f"## Conclusion\n\n{conclusion}\n\n",
        "## Follow-up (ResearchManager decision)\n\n",
    ]
    if chosen:
        conclusion_lines.append(
            f"- Selected must_have action: **{chosen.get('action', '')}** — {chosen.get('description', '')}\n"
            f"- Classification: `{classification}`\n"
            f"- Follow-up ran: **{follow_up_ran}**\n"
        )
    else:
        conclusion_lines.append("- No must_have required_experiment found; nothing auto-scheduled.\n")
    if follow_up_log and follow_up_log.get("systems_added"):
        conclusion_lines.append(
            f"- Follow-up added systems: {', '.join(follow_up_log['systems_added'])}\n"
        )
    if future_work:
        conclusion_lines.append("\n### Future Work (infeasible in sandbox)\n\n")
        for fw in future_work:
            conclusion_lines.append(
                f"- **{fw.get('action', '')}** — {fw.get('description', '')} "
                f"(_reason: {fw.get('reason', '')}_)\n"
            )
    conclusion_lines.append(
        f"\n_Backend_: `{SANDBOX_BACKEND_KIND}` (budget {MAX_EXPERIMENT_SECONDS}s). "
        "Multi-seed / multi-dataset follow-ups are deferred to a later session.\n"
    )
    (reviews.parent / "conclusion.md").write_text("".join(conclusion_lines), encoding="utf-8")

    logger.info(
        "[ResearchManager] conclusion=%s follow_up_ran=%s future_work=%d",
        conclusion[:80], follow_up_ran, len(future_work),
    )
    return {"decision": decision, "conclusion": conclusion, "metrics": merged_metrics}


def _estimate_first_run_seconds(project_id: str) -> float | None:
    """从 artifacts/logs/run_1.log 末尾的 duration_ms 行估算首跑耗时（若有）。"""
    log_path = WORKSPACE_ROOT / project_id / "artifacts" / "logs" / "run_1.log"
    if not log_path.exists():
        return None
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    # sandbox 输出里没有标准 duration_ms 标记；保守返回 None，让分类走 pending_session_3。
    return None
