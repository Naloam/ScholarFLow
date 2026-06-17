"""
IdeaAgent — 研究假设生成

输入：project_id, idea, literature notes (from LiteratureAgent output)
输出：写入 workspace/<project_id>/ideas/ 目录
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


def _workspace(project_id: str) -> Path:
    p = WORKSPACE_ROOT / project_id / "ideas"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_prompt(name: str) -> str:
    # Session 6: centralized on BACKEND_ROOT so resolution is CWD / DATA_DIR independent.
    from services.research_harness.prompts import load_prompt

    return load_prompt(name)


def _condense_gap_map(gap_map: dict, field_limit: int = 700) -> dict:
    """Lean the (possibly batch-merged) gap_map so the idea-gen prompt stays small enough for the
    LLM to finish within the gateway's ~110s window. Session 4: gap_map fields are merged across
    up-to-5 literature batches and can be long; truncate each, keep coverage + the merged essence.
    """
    def _trim(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            value = "; ".join(str(v) for v in value)
        elif isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = str(value)
        value = value.strip()
        return value if len(value) <= field_limit else value[:field_limit] + " …"

    return {
        "what_is_well_studied": _trim(gap_map.get("what_is_well_studied")),
        "what_is_missing": _trim(gap_map.get("what_is_missing")),
        "contradictions": _trim(gap_map.get("contradictions")),
        "literature_coverage": gap_map.get("literature_coverage", "unknown"),
    }


def generate_hypotheses(
    project_id: str,
    idea: str,
    gap_map: dict,
    known_baselines: list[dict],
) -> list[dict]:
    """用 LLM 基于 gap_map 生成候选 hypothesis 列表。

    Session 4：condense gap_map + cap baselines，保证 prompt 小到 LLM 能在网关 ~110s 窗口内
    生成完毕（mimo-v2.5-pro 在 saurlax 网关上生成较慢，原 prompt 易超时）。
    """
    prompt_template = _load_prompt("idea_agent_v1.md")
    condensed_gap = _condense_gap_map(gap_map or {})
    top_baselines = (known_baselines or [])[:10]
    prompt = (
        prompt_template
        .replace("{idea}", idea)
        .replace("{gap_map_json}", json.dumps(condensed_gap, ensure_ascii=False, indent=2))
        .replace("{known_baselines_json}", json.dumps(top_baselines, ensure_ascii=False, indent=2))
    )
    response = chat([{"role": "user", "content": prompt}])
    content = get_message_content(response)
    try:
        text = content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        candidates = json.loads(text.strip())
        if not isinstance(candidates, list):
            raise ValueError("Expected a JSON array")
        return candidates
    except Exception as e:
        logger.error("Failed to parse hypothesis response: %s\nContent: %s", e, content[:300])
        return []


def select_hypothesis(candidates: list[dict]) -> dict | None:
    """
    选择最优假设：优先 feasibility=high，其次 feasibility=medium。
    kill_criteria 最具体（字段最多）的优先。
    """
    if not candidates:
        return None
    priority = {"high": 0, "medium": 1, "low": 2}
    def score(h: dict) -> tuple:
        f = priority.get(h.get("feasibility", "low"), 2)
        specificity = len(h.get("kill_criteria", []))
        return (f, -specificity)
    return min(candidates, key=score)


def run_idea_agent(project_id: str, idea: str, literature_notes: dict) -> dict | None:
    """
    完整的 IdeaAgent 运行流程。
    返回 selected hypothesis dict，同时写入 workspace 文件。
    """
    ws = _workspace(project_id)
    gap_map = literature_notes.get("gap_map", {})
    known_baselines = literature_notes.get("known_baselines", [])

    # 检查文献覆盖率
    if gap_map.get("literature_coverage") == "insufficient":
        logger.warning("[IdeaAgent] literature_coverage=insufficient for project %s", project_id)

    logger.info("[IdeaAgent] Generating hypotheses for project=%s", project_id)
    candidates = generate_hypotheses(project_id, idea, gap_map, known_baselines)

    if not candidates:
        logger.error("[IdeaAgent] No hypotheses generated")
        (ws / "candidates.json").write_text(
            json.dumps({"error": "no_hypotheses_generated", "idea": idea}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return None

    (ws / "candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("[IdeaAgent] Generated %d candidates", len(candidates))

    selected = select_hypothesis(candidates)
    if selected is None:
        return None

    selected_md = f"# Selected Hypothesis\n\n"
    selected_md += f"**ID**: {selected.get('hypothesis_id', '')}\n\n"
    selected_md += f"**Title**: {selected.get('title', '')}\n\n"
    selected_md += f"**Research Question**: {selected.get('research_question', '')}\n\n"
    selected_md += f"**Gap Addressed**: {selected.get('gap_addressed', '')}\n\n"
    selected_md += f"**Core Novelty**: {selected.get('core_novelty', '')}\n\n"
    selected_md += f"**Proposed Method**: {selected.get('proposed_method_sketch', '')}\n\n"
    selected_md += f"**Implementation Hint**: {selected.get('implementation_hint', '')}\n\n"
    selected_md += f"**Feasibility**: {selected.get('feasibility', '')} — {selected.get('feasibility_reason', '')}\n\n"
    selected_md += f"**If valid**: {selected.get('expected_positive_outcome', '')}\n\n"
    selected_md += f"**If invalid**: {selected.get('expected_negative_outcome', '')}\n\n"
    selected_md += "**Kill Criteria**:\n"
    for k in selected.get("kill_criteria", []):
        selected_md += f"- {k}\n"

    (ws / "selected.md").write_text(selected_md, encoding="utf-8")
    logger.info("[IdeaAgent] Selected: %s (feasibility=%s)", selected.get("title"), selected.get("feasibility"))
    return selected
