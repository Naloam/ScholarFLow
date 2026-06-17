"""
LiteratureAgent — 文献检索与分析

输入：project_id, idea (str)
输出：写入 workspace/<project_id>/literature/ 目录下的文件
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config.settings import settings
from services.llm.client import chat
from services.llm.response_utils import get_message_content
from services.research_harness.utils.literature_fetch import fetch_papers

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path(settings.data_dir) / "research_workspace"


def _workspace(project_id: str) -> Path:
    p = WORKSPACE_ROOT / project_id / "literature"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _resolve_prompts_dir() -> Path:
    # settings.data_dir 默认是 <backend_root>/data，其 parent 即 backend root。
    # 额外提供 CWD 相关的 fallback，兼容从仓库根或 backend 目录启动。
    anchored = Path(settings.data_dir).parent / "prompts" / "research_harness"
    candidates = (
        anchored,
        Path("backend/prompts/research_harness"),
        Path("prompts/research_harness"),
    )
    for cand in candidates:
        if cand.is_dir():
            return cand
    return anchored


def _load_prompt(name: str) -> str:
    path = _resolve_prompts_dir() / name
    return path.read_text(encoding="utf-8")


def generate_search_queries(project_id: str, idea: str) -> list[str]:
    """Step 1: 用 LLM 从 idea 生成检索 query 列表"""
    prompt_template = _load_prompt("literature_agent_v1.md")
    prompt = prompt_template.replace("{idea}", idea)
    response = chat([{"role": "user", "content": prompt}])
    content = get_message_content(response)
    try:
        # 提取 JSON（处理 LLM 可能加了 ```json ``` 的情况）
        text = content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        queries = data.get("queries", [])
        if not queries:
            raise ValueError("No queries in response")
        logger.info("Generated %d search queries for idea: %s", len(queries), idea[:60])
        return queries
    except Exception as e:
        logger.error("Failed to parse query generation response: %s\nContent: %s", e, content[:200])
        # fallback: 用 idea 本身作为唯一 query
        return [idea]


def _parse_notes_json(content: str) -> dict | None:
    """从 LLM 回复解析 literature notes JSON；失败返回 None。

    容错：剥 ```json``` 围栏；若 LLM 在 JSON 前后混入说明文字，截取首个 ``{`` 到末尾 ``}```
    再 parse（Session 4 实测：mimo-v2.5-pro 偶尔会这么做，导致整批 parse 失败被丢弃）。
    """
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
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    if start != -1 and text.rstrip().endswith("}"):
        try:
            return json.loads(text[start:])
        except Exception:
            return None
    return None


def _coerce_gap_str(value: object) -> str:
    """gap_map 字段可能是 str / list / dict / None —— 统一转成可拼接的字符串。"""
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _empty_notes(reason: str) -> dict:
    return {
        "paper_notes": [],
        "gap_map": {
            "what_is_well_studied": "",
            "what_is_missing": reason,
            "contradictions": "",
            "literature_coverage": "insufficient",
        },
        "known_baselines": [],
    }


# 每批最多分析的论文数。Session 4 实测：mimo-v2.5-pro 处理 8 篇/批 ≈ 100-108s，逼近 110s
# 软超时与 120s 网关上限。降到 6 篇/批后每批 ~70-85s，留出安全余量；即便某批被软超时兜底
# 返回空（chat() fallback），其余批次仍能产出足够笔记（coverage 保持 sufficient）。
NOTES_BATCH_SIZE = 6
# 为结构化笔记最多总结的论文数（取前 N 篇）。papers.jsonl 仍记录全部检索结果（溯源），
# 但对 >N 篇只对前 N 篇生成笔记——兼顾覆盖率（N=30 远超 Session 3 的 10、且 ≥5 阈值）与
# 运行时（30 篇 / 6 = 5 批 ≈ 6-8 分钟，而不是 80+ 篇的 ~25 分钟）。
NOTES_MAX_PAPERS = 30


def _summarize_paper_batch(idea: str, batch: list[dict]) -> dict:
    """对一个小批次调一次 LLM，返回解析后的 notes dict（失败/超时返回空 notes）。"""
    papers_json = json.dumps(
        [
            {
                "title": p.get("title", ""),
                "abstract": (p.get("abstract", "") or "")[:500],
                "year": p.get("year"),
                "source": p.get("source", ""),
            }
            for p in batch
        ],
        ensure_ascii=False,
        indent=2,
    )
    prompt_template = _load_prompt("literature_notes_v1.md")
    prompt = prompt_template.replace("{idea}", idea).replace("{papers_json}", papers_json)
    response = chat([{"role": "user", "content": prompt}])
    content = get_message_content(response)
    parsed = _parse_notes_json(content)
    if isinstance(parsed, dict):
        return parsed
    logger.warning("Failed to parse a literature-notes batch; skipping batch")
    return _empty_notes("a batch could not be parsed")


def _chunked_notes(idea: str, papers: list[dict]) -> dict:
    """把 N 篇论文分批（每批 ≤NOTES_BATCH_SIZE 篇）调 LLM，再合并 gap_map / paper_notes / known_baselines。

    Session 4 Step 4：取代 Session 3 的「只取前 10 篇 + 截短摘要」临时 hack——分批让每批
    LLM 调用都小到能在 110s 软超时内完成；gap_map 字段可能是 str/list/dict，统一 coerce。
    为兼顾覆盖率与运行时，只对前 NOTES_MAX_PAPERS 篇生成笔记（papers.jsonl 仍保留全部）。
    """
    summarised = papers[:NOTES_MAX_PAPERS]
    batches = [summarised[i : i + NOTES_BATCH_SIZE] for i in range(0, len(summarised), NOTES_BATCH_SIZE)]
    logger.info(
        "[LiteratureAgent] summarizing %d/%d papers in %d batch(es) of <=%d",
        len(summarised), len(papers), len(batches), NOTES_BATCH_SIZE,
    )

    merged_paper_notes: list[dict] = []
    merged_baselines: list[dict] = []
    seen_baseline_names: set[str] = set()
    gap_missing: list[str] = []
    gap_studied: list[str] = []
    gap_contradictions: list[str] = []
    batches_ok = 0

    for batch in batches:
        notes = _summarize_paper_batch(idea, batch)
        if notes.get("paper_notes"):
            batches_ok += 1
        merged_paper_notes.extend(notes.get("paper_notes", []) or [])
        for b in notes.get("known_baselines", []) or []:
            name = (b.get("name") or "").strip()
            if name and name not in seen_baseline_names:
                seen_baseline_names.add(name)
                merged_baselines.append(b)
        gm = notes.get("gap_map", {}) or {}
        for key, bucket in (("what_is_missing", gap_missing), ("what_is_well_studied", gap_studied), ("contradictions", gap_contradictions)):
            val = _coerce_gap_str(gm.get(key))
            if val:
                bucket.append(val)

    # 覆盖率：成功批次产出的真实笔记数 >= 5 才算 sufficient。
    coverage = "sufficient" if len(merged_paper_notes) >= 5 else "insufficient"

    return {
        "paper_notes": merged_paper_notes,
        "known_baselines": merged_baselines,
        "gap_map": {
            "what_is_well_studied": "\n---\n".join(gap_studied) if gap_studied else "",
            "what_is_missing": "\n---\n".join(gap_missing) if gap_missing else "No usable gap analysis produced.",
            "contradictions": "\n---\n".join(gap_contradictions) if gap_contradictions else "",
            "literature_coverage": coverage,
        },
        "_meta": {"papers_input": len(papers), "batches": len(batches), "batches_ok": batches_ok},
    }


def generate_literature_notes(
    project_id: str,
    idea: str,
    papers: list[dict],
) -> dict:
    """Step 2: 用 LLM 把论文列表压缩成结构化笔记和 gap_map（分批，Session 4 Step 4）。"""
    if not papers:
        logger.warning("No papers to analyze for project %s", project_id)
        return _empty_notes("No papers found — gap analysis unavailable.")
    return _chunked_notes(idea, papers)


def run_literature_agent(project_id: str, idea: str) -> dict:
    """
    完整的 LiteratureAgent 运行流程。
    返回 notes dict，同时写入 workspace 文件。
    """
    ws = _workspace(project_id)
    logger.info("[LiteratureAgent] Starting for project=%s idea=%s", project_id, idea[:60])

    # 1. 生成检索 query
    queries = generate_search_queries(project_id, idea)
    (ws / "search_queries.json").write_text(
        json.dumps({"idea": idea, "queries": queries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("[LiteratureAgent] Queries: %s", queries)

    # 2. 检索论文
    papers = fetch_papers(project_id, queries, limit_per_source=8, network_enabled=True)
    (ws / "papers.jsonl").write_text(
        "\n".join(json.dumps(p, ensure_ascii=False, default=str) for p in papers),
        encoding="utf-8",
    )
    logger.info("[LiteratureAgent] Retrieved %d papers", len(papers))

    # 3. 生成结构化笔记
    notes = generate_literature_notes(project_id, idea, papers)

    # 写入各文件
    paper_notes = notes.get("paper_notes", [])
    gap_map = notes.get("gap_map", {})
    known_baselines = notes.get("known_baselines", [])

    notes_md_lines = [f"# Literature Notes\n\n**Idea**: {idea}\n\n**Papers analyzed**: {len(paper_notes)}\n\n"]
    for note in paper_notes:
        notes_md_lines.append(f"## {note.get('title', 'Unknown')} ({note.get('year', '?')})\n")
        notes_md_lines.append(f"- **Method**: {note.get('core_method', '')}\n")
        notes_md_lines.append(f"- **Finding**: {note.get('main_finding', '')}\n")
        notes_md_lines.append(f"- **Limitation**: {note.get('limitation', '')}\n")
        notes_md_lines.append(f"- **Relevance**: {note.get('relevance_to_idea', '')}\n\n")

    (ws / "notes.md").write_text("".join(notes_md_lines), encoding="utf-8")

    gap_md = f"# Research Gap Map\n\n**Idea**: {idea}\n\n"
    gap_md += f"## Well-studied\n{gap_map.get('what_is_well_studied', '')}\n\n"
    gap_md += f"## Missing / Under-explored\n{gap_map.get('what_is_missing', '')}\n\n"
    gap_md += f"## Contradictions\n{gap_map.get('contradictions', '')}\n\n"
    gap_md += f"**Coverage**: {gap_map.get('literature_coverage', 'unknown')}\n"
    (ws / "gap_map.md").write_text(gap_md, encoding="utf-8")

    baselines_md = "# Known Baselines\n\n"
    for b in known_baselines:
        baselines_md += f"- **{b.get('name', '')}**: {b.get('description', '')} (metric: {b.get('reported_metric', 'N/A')}, source: {b.get('source_paper', '')})\n"
    (ws / "known_baselines.md").write_text(baselines_md, encoding="utf-8")

    logger.info("[LiteratureAgent] Done. Coverage: %s", gap_map.get("literature_coverage"))
    return notes
