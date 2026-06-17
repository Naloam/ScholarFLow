"""
ReviewerAgent — 以严格审稿人身份给出具体、可执行的批评。

诚实注入（plan §8.3 gate）：
- 执行失败 → 在 prompt 里明确告知"无 metric 结果，审稿必须针对执行失败本身"。
- proposed 没超过 baseline → 明确告知，weaknesses 必须如实反映。
即使执行失败也必须产出 review（publish_gate 应为 no_evidence）。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config.settings import settings
from services.llm.client import chat
from services.llm.response_utils import get_message_content

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path(settings.data_dir) / "research_workspace"

EXEC_FAILURE_INJECTION = (
    "\n\n## ⚠️ 诚实约束（必须遵守）\n"
    "Note: the experiment FAILED to execute (execution_status != success). "
    "There are NO metric results. Your review MUST address the execution failure itself; "
    "do not invent results. Set publish_gate to no_evidence. "
    "At least one weakness (severity=major) must cite the execution failure / empty metrics."
)

NEGATIVE_RESULT_INJECTION = (
    "\n\n## ⚠️ 诚实约束（必须遵守）\n"
    "Note: the proposed method did NOT beat the baseline on the evaluated datasets:\n"
    "{comparison_summary}\n"
    "Your weaknesses MUST reflect this honestly; do NOT write \"competitive\" or \"promising\". "
    "At least one weakness (severity=major) must cite the specific per-dataset numbers showing "
    "proposed <= baseline."
)


def _reviews_dir(project_id: str) -> Path:
    p = WORKSPACE_ROOT / project_id / "reviews"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_prompt(name: str) -> str:
    # Session 6: centralized on BACKEND_ROOT so resolution is CWD / DATA_DIR independent.
    from services.research_harness.prompts import load_prompt

    return load_prompt(name)


def _extract_json(content: str) -> object | None:
    if not content:
        return None
    text = content.strip()
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    text = text.strip()
    start = text.find("{")
    if start != -1 and text.rstrip().endswith("}"):
        text = text[start:]
    try:
        return json.loads(text)
    except Exception:
        return None


def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    return text if len(text) <= limit else text[:limit] + " …(truncated)"


def _coerce_text(value, limit: int) -> str:
    """把 gap_map 字段（可能是 list / dict / str）安全转成截断后的字符串。"""
    if value is None:
        return ""
    if isinstance(value, list):
        value = "; ".join(str(item) for item in value)
    elif isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False)
    else:
        value = str(value)
    return _truncate(value, limit)


def run_reviewer_agent(
    project_id: str,
    idea: str,
    selected_hypothesis: dict,
    metrics: dict,
    literature_notes: dict,
) -> dict:
    """生成审稿意见，写 reviews/reviewer_round_1.md + reviews/action_plan_1.json。"""
    reviews = _reviews_dir(project_id)
    gap_map = literature_notes.get("gap_map", {}) or {}
    notes_summary = _coerce_text(gap_map.get("what_is_missing", ""), 500)
    baseline_comparison = metrics.get("baseline_comparison", {}) or {}

    prompt = (
        _load_prompt("reviewer_v1.md")
        .replace("{idea}", idea)
        .replace("{hypothesis_json}", json.dumps(selected_hypothesis, ensure_ascii=False, indent=2))
        .replace("{results_json}", json.dumps(metrics, ensure_ascii=False, indent=2))
        .replace("{stats_json}", json.dumps(baseline_comparison, ensure_ascii=False, indent=2))
        .replace("{notes_summary}", notes_summary)
    )

    # 诚实注入
    if metrics.get("execution_status") != "success":
        prompt += EXEC_FAILURE_INJECTION
    elif baseline_comparison.get("overall_beats_baseline") is False:
        cmp_summary = "; ".join(
            f"{d['dataset']}: proposed {d['proposed_metric']:.3f} vs baseline {d['baseline_metric']:.3f}"
            for d in baseline_comparison.get("datasets", [])
        ) or "see metrics.results"
        prompt += NEGATIVE_RESULT_INJECTION.format(comparison_summary=cmp_summary)

    logger.info("[ReviewerAgent] generating review for project=%s", project_id)
    content = get_message_content(chat([{"role": "user", "content": prompt}]))
    parsed = _extract_json(content)
    if not isinstance(parsed, dict):
        logger.error("[ReviewerAgent] parse failed; raw=%s", (content or "")[:300])
        review = _fallback_review(metrics)
    else:
        review = parsed

    # 规范化关键字段，保证下游（ResearchManager / ReportGenerator）可用
    review.setdefault("overall_assessment", "reject")
    review.setdefault("summary", "")
    review.setdefault("strengths", [])
    review.setdefault("weaknesses", [])
    review.setdefault("required_experiments", [])
    review.setdefault("publish_gate", "no_evidence")

    (reviews / "reviewer_round_1.md").write_text(_render_review_md(review, idea), encoding="utf-8")
    (reviews / "action_plan_1.json").write_text(
        json.dumps(
            {"required_experiments": review.get("required_experiments", [])},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info(
        "[ReviewerAgent] done: assessment=%s publish_gate=%s weaknesses=%d",
        review.get("overall_assessment"), review.get("publish_gate"), len(review.get("weaknesses", [])),
    )
    return review


def _fallback_review(metrics: dict) -> dict:
    """LLM 解析失败时的诚实兜底：不伪造优点，只记录无法评审。"""
    if metrics.get("execution_status") != "success":
        return {
            "overall_assessment": "reject",
            "summary": "Reviewer generation failed AND experiment did not execute; no evidence available.",
            "strengths": [],
            "weaknesses": [
                {
                    "issue": "Experiment failed to execute after repair attempts; no metric results exist.",
                    "severity": "major",
                    "evidence": f"execution_status={metrics.get('execution_status')}, results={metrics.get('results')}",
                }
            ],
            "required_experiments": [
                {
                    "action": "report_failure_mode",
                    "description": "Fix the experiment code so it executes and emits __RESULT__; no review is meaningful until results exist.",
                    "priority": "must_have",
                }
            ],
            "publish_gate": "no_evidence",
            "source": "fallback_after_parse_error",
        }
    return {
        "overall_assessment": "weak_reject",
        "summary": "Reviewer generation failed; review is a minimal honest placeholder based on raw metrics.",
        "strengths": [],
        "weaknesses": [
            {
                "issue": "Automated reviewer critique could not be generated; only raw metrics are available.",
                "severity": "major",
                "evidence": f"results={metrics.get('results')}",
            }
        ],
        "required_experiments": [
            {
                "action": "run_ablation",
                "description": "Re-run review with a valid LLM response once available.",
                "priority": "nice_to_have",
            }
        ],
        "publish_gate": "no_evidence",
        "source": "fallback_after_parse_error",
    }


def _render_review_md(review: dict, idea: str) -> str:
    lines = [f"# Reviewer Round 1\n\n**Idea**: {idea}\n"]
    lines.append(f"**Overall assessment**: {review.get('overall_assessment', '')}\n")
    lines.append(f"**Publish gate**: {review.get('publish_gate', '')}\n\n")
    lines.append(f"## Summary\n{review.get('summary', '')}\n\n")
    lines.append("## Strengths\n")
    for s in review.get("strengths", []) or []:
        lines.append(f"- {s}\n")
    lines.append("\n## Weaknesses\n")
    for w in review.get("weaknesses", []) or []:
        if isinstance(w, dict):
            lines.append(
                f"- **[{w.get('severity', '?')}]** {w.get('issue', '')}\n"
                f"  - evidence: {w.get('evidence', '')}\n"
            )
        else:
            lines.append(f"- {w}\n")
    lines.append("\n## Required Experiments\n")
    for req in review.get("required_experiments", []) or []:
        if isinstance(req, dict):
            lines.append(
                f"- **[{req.get('priority', '?')}]** {req.get('action', '')}: {req.get('description', '')}\n"
            )
        else:
            lines.append(f"- {req}\n")
    return "".join(lines)
