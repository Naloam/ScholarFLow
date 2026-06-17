# ScholarFlow V0 Session 1 — 完整任务

## 首先必须读这些文件（按顺序，不要跳过）

```
Read AGENTS.md                                                          # 项目规则
Read SCHOLARFLOW_CORE_REBUILD_PLAN_v2.md                               # 完整计划
Read backend/services/llm/client.py                                    # 理解 chat() 接口
Read backend/services/autoresearch/literature_connectors.py            # 重点：1-100行 + search_literature_connectors 函数
Read backend/services/autoresearch/runner.py lines 100-145, 495-640    # 要抽取的统计函数
Read backend/services/sandbox/backends.py                              # 理解 LocalSandboxBackend
Read backend/services/sandbox/runner.py                                # 理解 run_python_in_sandbox
Read backend/prompts/autoresearch/codegen/method_gen_v0.1.0.md        # 理解旧 prompt 的问题（纯标准库限制）
```

读完后开始按以下步骤执行，**每个步骤完成后告诉我完成了什么再继续**。

---

## Step 1：EXTRACT — 创建工具层（不改原文件，只复制逻辑）

### 1a. 创建目录结构

```
backend/services/research_harness/__init__.py          （空文件）
backend/services/research_harness/utils/__init__.py    （空文件）
```

### 1b. 创建 `backend/services/research_harness/utils/stats.py`

从 `runner.py` 里把以下 5 个函数**复制**（不是 import）进来，去掉下划线前缀，
改为公共函数。需要的 type import 从 `schemas/autoresearch.py` 里带过来（
`ConfidenceIntervalSummary`、`SignificanceTestResult`），或在文件里 inline 定义简单版：

- `_confidence_interval` → `confidence_interval`
- `_paired_sign_flip_test` → `paired_sign_flip_test`
- `_paired_differences` → `paired_differences`
- `_power_style_analysis` → `power_style_analysis`
- `_holm_bonferroni_adjustment` → `holm_bonferroni_adjustment`

文件顶部加注释：

```python
"""
统计工具函数。
从 services/autoresearch/runner.py 抽取，逻辑不变，仅改为公共接口。
"""
```

### 1c. 创建 `backend/services/research_harness/utils/literature_fetch.py`

这个文件是 `literature_connectors.search_literature_connectors()` 的薄封装，
目的是让 research_harness 的 agent 不需要构造 `AutoResearchResearchBriefRead` 对象。

```python
"""
literature_fetch.py — 对 literature_connectors 的薄封装。
让 research_harness agents 可以直接用 (project_id, queries) 调用，
不依赖旧的 AutoResearchResearchBriefRead 结构。
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from schemas.autoresearch import AutoResearchResearchBriefRead
from services.autoresearch.literature_connectors import search_literature_connectors


def fetch_papers(
    project_id: str,
    queries: list[str],
    *,
    sources: list[str] | None = None,
    limit_per_source: int = 5,
    network_enabled: bool = True,
    cache_enabled: bool = True,
) -> list[dict[str, Any]]:
    """
    给定 project_id 和检索 query 列表，返回论文列表（dict 格式）。
    sources 默认为 ["arxiv", "semantic_scholar", "crossref"]（不含 fixture）。
    """
    # 构造一个最小化的 brief 对象，仅用于 connector 的 cache key 和内部路由
    minimal_brief = AutoResearchResearchBriefRead(
        project_id=project_id,
        brief_id=f"harness_{project_id}",
        idea=queries[0] if queries else "",
        domain="",
        status="active",
    )
    used_sources = sources or ["arxiv", "semantic_scholar", "crossref"]
    papers, statuses = search_literature_connectors(
        minimal_brief,
        search_queries=queries,
        sources=used_sources,
        limit_per_source=limit_per_source,
        network_enabled=network_enabled,
        cache_enabled=cache_enabled,
    )
    return [p.model_dump() for p in papers]
```

**注意**：`AutoResearchResearchBriefRead` 的必填字段可能比上面多，读完 schemas/autoresearch.py
里的定义再补齐，保持"只填必填字段，其余用默认值或空字符串"的原则。

---

## Step 2：创建 7 个 Prompt 文件

路径：`backend/prompts/research_harness/`

每个文件的内容按下面的规格严格写，**不要缩水成"TODO"或"placeholder"**。
这 7 个 prompt 是 V0 的大脑，内容质量直接决定产出是否有科研价值。

### `literature_agent_v1.md`

```markdown
# LiteratureAgent — 检索 Query 生成

你是一个学术文献检索专家。给定一个研究 idea，你的任务是生成 4 个不同角度的检索 query，
覆盖：(1) 核心方法领域，(2) 相关评测数据集/benchmark，(3) 已知 baseline 方法，
(4) 最近两年的新进展。

## 输入

- idea: {idea}

## 输出格式（JSON，只输出 JSON，不要其他文字）

{
"queries": [
"query 1 covering core method domain",
"query 2 covering benchmark/dataset",
"query 3 covering known baselines",
"query 4 covering recent advances"
]
}

## 规则

- query 用英文，适合在 arXiv / Semantic Scholar 搜索
- 每个 query 独立，不要互相重复
- 控制在 5-10 个词，不要过长的句子
- 不要加引号或 site: 这类搜索语法
```

### `literature_notes_v1.md`

```markdown
# LiteratureAgent — 论文笔记与 Gap Map 生成

你是一个自动科研系统的文献分析模块。给定一批论文（标题+摘要），你的任务是：

1. 为每篇论文写一条结构化笔记
2. 综合所有笔记，生成 gap_map 和 known_baselines

## 输入

- idea: {idea}
- papers: {papers_json}
  （格式：[{"title": "...", "abstract": "...", "year": ..., "source": "..."}, ...]）

## 输出格式（JSON，只输出 JSON，不要其他文字）

{
"paper_notes": [
{
"title": "论文标题",
"year": 2024,
"core_method": "这篇论文用了什么方法（1-2句）",
"main_finding": "核心结论是什么（1-2句）",
"limitation": "主要局限是什么（1句）",
"relevance_to_idea": "和当前 idea 的关系（1-2句，明确说相关/不相关/有哪方面相关）"
}
],
"gap_map": {
"what_is_well_studied": "已经被充分研究的方向（列举2-4点）",
"what_is_missing": "明显缺失或研究不足的方向（列举2-4点，这是 IdeaAgent 的主要输入）",
"contradictions": "不同论文之间有哪些矛盾或未解决的争议（如果有）",
"literature_coverage": "sufficient | insufficient（少于5篇真实相关论文时填 insufficient）"
},
"known_baselines": [
{
"name": "方法/系统名称",
"description": "一句话描述",
"reported_metric": "论文里报告的指标名和数值（如有）",
"source_paper": "来自哪篇论文的标题"
}
]
}

## 规则

- paper_notes 必须覆盖所有输入论文，不得遗漏
- gap_map.what_is_missing 必须至少有2条，且要具体（不能只写"更多研究需要"）
- 如果输入论文少于5篇，literature_coverage 填 "insufficient"
- 所有文字用中文或英文均可，保持一致
```

### `idea_agent_v1.md`

```markdown
# IdeaAgent — 研究假设生成

你是一个自动科研系统的创意生成模块。基于文献综述的 gap_map，提出多个可实验验证的研究假设。

## 输入

- idea: {idea}
- gap_map: {gap_map_json}
- known_baselines: {known_baselines_json}
- sandbox_packages: ["numpy", "pandas", "scikit-learn", "sentence-transformers (all-MiniLM-L6-v2)"]
- max_experiment_minutes: 10

## 你的任务

生成 5 个候选假设（hypothesis），每个必须：

1. 直接回应 gap_map.what_is_missing 中的某一条（在 gap_addressed 字段里引用原文）
2. 提出一个与 known_baselines 中的方法明确不同的核心思路
3. 在 sandbox_packages 范围内可以实现（不需要 GPU，10分钟内能跑完）
4. 包含诚实的失败预期（如果方法不 work，预期是什么）

## 输出格式（JSON array，只输出 JSON）

[
{
"hypothesis_id": "h1",
"title": "简短标题（一句话）",
"research_question": "这个假设要回答的具体问题（可检验的问题）",
"gap_addressed": "引用 gap_map.what_is_missing 中的原文",
"core_novelty": "与 known_baselines 的本质区别（具体说，不能只说'更好'）",
"proposed_method_sketch": "方法描述（2-5句，足够让工程师写代码）",
"implementation_hint": "用 sandbox_packages 里的哪些包，大致怎么实现",
"feasibility": "high | medium | low",
"feasibility_reason": "为什么这个可行性评级（1-2句）",
"expected_positive_outcome": "如果假设成立，实验会看到什么",
"expected_negative_outcome": "如果假设不成立，实验会看到什么（必填）",
"kill_criteria": ["在什么情况下应该放弃这个方向（1-3条具体判据）"],
"estimated_runtime_minutes": 5
}
]

## 禁止的输出

- 不允许 proposed_method_sketch 只是"apply X to Y"而不解释 X 和 Y 的具体含义
- 不允许 core_novelty 是"我们的方法更高效/准确"这类空话
- 不允许 feasibility=high 的假设需要下载超过 200MB 的模型
- 不允许所有 5 个假设都是 TF-IDF / 关键词匹配的变体（即使它们 feasibility 高）
- 不允许 expected_negative_outcome 是空的或"没有负面结果"
```

### `experiment_planner_v1.md`

```markdown
# ExperimentEngineer — 实验计划生成

你是一个自动科研系统的实验设计模块。给定一个选定的研究假设，生成详细的实验计划。

## 输入

- selected_hypothesis: {hypothesis_json}
- known_baselines: {known_baselines_json}
- sandbox_packages: ["numpy", "pandas", "scikit-learn", "sentence-transformers (all-MiniLM-L6-v2)"]
- max_experiment_minutes: 10

## 输出格式（JSON，只输出 JSON）

{
"dataset": {
"name": "数据集名称",
"source": "从哪里获取（huggingface datasets / URL / 内置生成）",
"load_code": "Python 代码片段，展示如何加载这个数据集",
"size_note": "大概有多少样本，为什么这个大小合适"
},
"metrics": [
{"name": "主要指标名（如 ndcg@10, f1, accuracy）", "primary": true},
{"name": "次要指标名", "primary": false}
],
"systems": [
{
"name": "baseline_1",
"role": "baseline",
"description": "描述（对应 known_baselines 中的某个方法）"
},
{
"name": "proposed",
"role": "proposed",
"description": "对应 hypothesis 中的 proposed_method_sketch"
},
{
"name": "ablation_no_X",
"role": "ablation",
"description": "去掉 proposed 中某个关键组件的变体"
}
],
"statistical_tests": ["paired_sign_flip_test", "confidence_interval"],
"success_criterion": "什么条件下认为假设得到支持（具体数值或统计显著性要求）",
"failure_criterion": "什么条件下认为假设不成立，应该报告 negative result"
}

## 规则

- dataset 必须是真实存在的数据集，不能是"随机生成的玩具数据"（除非假设本身是证明方法论）
- 优先用 HuggingFace datasets 里能直接 load_dataset() 的数据集
- 必须包含至少 1 个 baseline + 1 个 proposed + 1 个 ablation
- 实验必须能在 max_experiment_minutes 内完成（适当截取数据集大小）
```

### `experiment_codegen_v1.md`

````markdown
# ExperimentEngineer — 实验代码生成

你是一个自动科研系统的代码生成模块。根据实验计划，生成完整可运行的 Python 实验脚本。

## 输入

- experiment_plan: {plan_json}
- selected_hypothesis: {hypothesis_json}

## 允许的 Python 包

Python 标准库 + numpy + pandas + scikit-learn + sentence-transformers

加载 sentence-transformers 时必须用小模型：

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')  # ~80MB，可离线使用
```
````

## 你必须生成一个完整的 `experiment.py`

脚本结构要求：

1. 所有 import 在文件顶部
2. 数据加载函数：`def load_data() -> tuple[list, list]:`（返回 train, test）
3. 每个 system 一个函数：`def run_baseline_1(train, test) -> dict:` 等
4. 每个 system 函数必须返回：
   ```python
   {
     "system_name": "...",
     "metric_name": "...",  # 与 plan 中 primary metric 名称一致
     "metric_value": 0.xxx,
     "n_test": 100,
     "dataset_name": "..."
   }
   ```
5. main 函数里依次运行所有 system，把结果收集后：
   ```python
   import json
   print("__RESULT__", json.dumps(results))  # 这行必须在最后
   ```
6. 脚本末尾：`if __name__ == "__main__": main()`

## 绝对禁止

- 不允许 mock/fake 数据作为实验数据（只允许在 load_data 失败时打印错误并退出）
- 不允许在 **RESULT** 里输出假数值
- 不允许 proposed method 和 baseline 共用完全相同的实现
- 不允许使用 GPU（no .cuda()，no device="cuda"）

## 输出

只输出 Python 代码，用 `python ` 包裹，不要额外说明。

````

### `experiment_repair_v1.md`

```markdown
# ExperimentEngineer — 代码修复

你是一个自动科研系统的代码调试模块。给定实验代码和运行错误，修复代码使其可以正确运行。

## 输入
- error_output: {stderr}
- current_code: {code}
- attempt_number: {attempt}  （最多修复 3 次）

## 你的任务
分析错误原因，输出修复后的完整代码。

## 修复优先级（按此顺序检查）
1. ImportError / ModuleNotFoundError：检查是否用了不在允许列表里的包
   - 允许：标准库 + numpy + pandas + scikit-learn + sentence-transformers
   - 不允许：torch（除非 sentence-transformers 内部依赖）、transformers（直接使用）
2. 数据集加载错误：换一个更小/更简单的数据集，或用内置生成的简单数据集
3. 形状/类型错误：检查 numpy/pandas 的维度和类型转换
4. __RESULT__ 缺失：确保 main() 最后有 print("__RESULT__", json.dumps(results))
5. 超时：减少数据集大小（如 test[:200]），降低模型复杂度

## 输出格式
首先用 2-3 句话说明根本原因，然后输出修复后的完整代码（用 ```python ``` 包裹）。
不要只输出 diff，要输出完整文件。
````

### `reviewer_v1.md`

```markdown
# ReviewerAgent — 研究审稿

你是一个自动科研系统的严格审稿人。像 NeurIPS/AAAI/ACL 的审稿人一样，评估一个小型实验研究的质量。

## 输入

- idea: {idea}
- selected_hypothesis: {hypothesis_json}
- experiment_results: {results_json}
- statistics: {stats_json}
- literature_notes: {notes_summary}

## 你的任务

给出严格、具体、可执行的审稿意见。

## 输出格式（JSON，只输出 JSON）

{
"overall_assessment": "accept | weak_accept | weak_reject | reject",
"summary": "一句话总结你的判断和核心原因",
"strengths": [
"优点1（具体，引用实验结果里的数字）",
"优点2"
],
"weaknesses": [
{
"issue": "具体问题描述（不允许模糊表述，必须指出是哪个方面、哪个数字有问题）",
"severity": "major | minor",
"evidence": "引用 experiment_results 或 statistics 中的具体数值作为证据"
}
],
"required_experiments": [
{
"action": "add_stronger_baseline | run_ablation | test_on_second_dataset | report_failure_mode | improve_statistical_power",
"description": "具体要做什么（一句话，足够让工程师执行）",
"priority": "must_have | nice_to_have"
}
],
"publish_gate": "no_evidence | insufficient_evidence | borderline | publishable"
}

## 审稿规则

- weaknesses 至少要有 1 条 major（即使结果好，也总有方法论局限）
- 如果 proposed method 没有显著超过 baseline（p > 0.05），必须在 weaknesses 里明确指出
- 如果只测了 1 个数据集，必须要求 test_on_second_dataset（priority=must_have）
- evidence 字段不允许是空字符串，必须引用具体数字
- 不允许给 publish_gate=publishable（一轮小实验不够，这是诚实的科研评估）
```

### `research_manager_v1.md`

```markdown
# ResearchManager — Follow-up 决策

你是一个自动科研系统的项目管理模块。根据审稿意见，决定下一步行动。

## 输入

- action_plan: {action_plan_json} （reviewer 输出的 required_experiments）
- current_workspace_summary: {workspace_summary}
- remaining_budget_minutes: {budget}

## 你的任务

从 required_experiments 里选择 1 个 priority=must_have 的 action 执行，或者明确说明无法执行的原因。

## 输出格式（JSON，只输出 JSON）

{
"decision": "execute | skip_all | partial",
"selected_action": {
"action": "...",
"description": "...",
"rationale": "为什么选这个（而不是其他 must_have 的 action）"
},
"skipped_actions": [
{
"action": "...",
"reason": "为什么跳过（预算不足/需要 GPU/超出 sandbox 能力）"
}
],
"final_conclusion": "根据当前所有证据，这个研究 idea 的状态是什么（1-3句）",
"negative_result_note": "如果 proposed 没有超过 baseline，在这里明确写出 negative result 的表述"
}
```

---

## Step 3：实现 LiteratureAgent

创建 `backend/services/research_harness/literature_agent.py`：

````python
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


def _load_prompt(name: str) -> str:
    path = Path("backend/prompts/research_harness") / name
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


def generate_literature_notes(
    project_id: str,
    idea: str,
    papers: list[dict],
) -> dict:
    """Step 2: 用 LLM 把论文列表压缩成结构化笔记和 gap_map"""
    if not papers:
        logger.warning("No papers to analyze for project %s", project_id)
        return {
            "paper_notes": [],
            "gap_map": {
                "what_is_well_studied": "",
                "what_is_missing": "No papers found — gap analysis unavailable.",
                "contradictions": "",
                "literature_coverage": "insufficient",
            },
            "known_baselines": [],
        }

    # 只取前 20 篇，避免 prompt 过长
    papers_for_prompt = papers[:20]
    papers_json = json.dumps(
        [{"title": p.get("title", ""), "abstract": p.get("abstract", "")[:800], "year": p.get("year"), "source": p.get("source", "")} for p in papers_for_prompt],
        ensure_ascii=False,
        indent=2,
    )

    prompt_template = _load_prompt("literature_notes_v1.md")
    prompt = prompt_template.replace("{idea}", idea).replace("{papers_json}", papers_json)
    response = chat([{"role": "user", "content": prompt}])
    content = get_message_content(response)

    try:
        text = content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        logger.error("Failed to parse literature notes response: %s", e)
        return {
            "paper_notes": [],
            "gap_map": {
                "what_is_well_studied": "",
                "what_is_missing": f"Parse error: {e}",
                "contradictions": "",
                "literature_coverage": "insufficient",
            },
            "known_baselines": [],
        }


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
        "\n".join(json.dumps(p, ensure_ascii=False) for p in papers),
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
````

---

## Step 4：实现 IdeaAgent

创建 `backend/services/research_harness/idea_agent.py`：

````python
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
    path = Path("backend/prompts/research_harness") / name
    return path.read_text(encoding="utf-8")


def generate_hypotheses(
    project_id: str,
    idea: str,
    gap_map: dict,
    known_baselines: list[dict],
) -> list[dict]:
    """用 LLM 基于 gap_map 生成候选 hypothesis 列表"""
    prompt_template = _load_prompt("idea_agent_v1.md")
    prompt = (
        prompt_template
        .replace("{idea}", idea)
        .replace("{gap_map_json}", json.dumps(gap_map, ensure_ascii=False, indent=2))
        .replace("{known_baselines_json}", json.dumps(known_baselines, ensure_ascii=False, indent=2))
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
````

---

## Step 5：创建 CLI 测试脚本

创建 `scripts/v0_run.py`：

```python
#!/usr/bin/env python3
"""
ScholarFlow V0 — 端到端研究流程测试脚本

用法：
  cd backend
  PYTHONPATH=. python ../scripts/v0_run.py --idea "你的研究 idea"

输出：backend/data/research_workspace/<project_id>/ 目录下的全部文件
"""
from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

# 确保能找到 backend 的模块
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("v0_run")


def main() -> None:
    parser = argparse.ArgumentParser(description="ScholarFlow V0 Research Run")
    parser.add_argument("--idea", required=True, help="Research idea string")
    parser.add_argument("--project-id", default=None, help="Project ID (auto-generated if not set)")
    parser.add_argument("--steps", default="literature,idea", help="Comma-separated steps to run (literature,idea)")
    args = parser.parse_args()

    project_id = args.project_id or f"v0_{uuid.uuid4().hex[:8]}"
    steps = [s.strip() for s in args.steps.split(",")]

    logger.info("=== ScholarFlow V0 Run ===")
    logger.info("Project ID: %s", project_id)
    logger.info("Idea: %s", args.idea)
    logger.info("Steps: %s", steps)

    literature_notes = None

    if "literature" in steps:
        logger.info("\n--- Step 1: LiteratureAgent ---")
        from services.research_harness.literature_agent import run_literature_agent
        literature_notes = run_literature_agent(project_id, args.idea)
        logger.info("LiteratureAgent complete. Coverage: %s",
                    literature_notes.get("gap_map", {}).get("literature_coverage", "unknown"))

    if "idea" in steps:
        logger.info("\n--- Step 2: IdeaAgent ---")
        if literature_notes is None:
            # 尝试从磁盘读取已有的文献笔记
            import json
            ws_root = Path("data/research_workspace") / project_id
            gap_file = ws_root / "literature" / "gap_map.md"
            if not gap_file.exists():
                logger.error("No literature notes found. Run with --steps literature,idea")
                sys.exit(1)
            # 简化：从 candidates.json 检查有没有已有结果
            notes_file = ws_root / "literature" / "papers.jsonl"
            papers = [json.loads(l) for l in notes_file.read_text().splitlines() if l.strip()] if notes_file.exists() else []
            literature_notes = {
                "gap_map": {"what_is_missing": gap_file.read_text(), "literature_coverage": "unknown"},
                "known_baselines": [],
                "paper_notes": [],
            }

        from services.research_harness.idea_agent import run_idea_agent
        selected = run_idea_agent(project_id, args.idea, literature_notes)
        if selected:
            logger.info("IdeaAgent selected: %s", selected.get("title"))
        else:
            logger.error("IdeaAgent failed to produce a hypothesis")

    workspace_path = Path("data/research_workspace") / project_id
    logger.info("\n=== V0 Run Complete ===")
    logger.info("Workspace: %s", workspace_path.resolve())
    if workspace_path.exists():
        for f in sorted(workspace_path.rglob("*")):
            if f.is_file():
                logger.info("  %s (%d bytes)", f.relative_to(workspace_path), f.stat().st_size)


if __name__ == "__main__":
    main()
```

---

## Step 6：验证

运行以下命令确认 Session 1 产出正确：

```bash
# 在仓库根目录
cd backend
PYTHONPATH=. python -c "from services.research_harness.utils.stats import confidence_interval; print('stats OK')"
PYTHONPATH=. python -c "from services.research_harness.utils.literature_fetch import fetch_papers; print('fetch OK')"
PYTHONPATH=. python -c "from services.research_harness.literature_agent import run_literature_agent; print('literature_agent OK')"
PYTHONPATH=. python -c "from services.research_harness.idea_agent import run_idea_agent; print('idea_agent OK')"
```

如果所有 import 都通过，Session 1 完成。

---

## Session 1 完成后的状态检查

告诉我：

1. 4 个 import 是否全部 OK
2. `backend/prompts/research_harness/` 下有哪几个文件
3. `backend/services/research_harness/` 下有哪几个文件

然后我们进入 Session 2（ExperimentEngineer + ReviewerAgent + 真实端到端测试）。
