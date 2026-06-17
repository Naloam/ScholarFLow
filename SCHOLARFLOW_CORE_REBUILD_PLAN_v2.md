# ScholarFlow Core Rebuild Plan (v2 — 病灶定位版)

更新时间：2026-06-15
关系：本文是对 `SCHOLARFLOW_STATUS_AND_PLAN.md`（v1，ChatGPT版）的修订，不是推翻。
v1 的终态架构（三层：Research Harness Core / Auditor Layer / 瘦后端+Cockpit）和 agent 角色
划分（Literature / Idea / ExperimentEngineer / Reviewer / Writer / Auditor）方向是对的，
保留。本文做两件 v1 没做的事：

1. 把"为什么现在不是 ARIS/FARS"这件事，定位到**具体文件和具体函数**，而不是停留在
   "kernel 不够强"这种可以被任意解读的描述。
2. 把 v1 的 Phase 0-7 顺序**倒过来**：先证明"AI 真的能对一个真实 idea 给出非模板化的
   方向、写出能跑的代码、产出诚实结论"，再回头补 schema / workspace / cockpit。
   v1 的顺序会让执行者（人或 agent）在证明核心能力存在之前先把脚手架做漂亮——
   这正是过去几轮发生的事。

---

## 0. 给执行 agent 的强制规则

**必须放在 system prompt / AGENTS.md 最前面，逐条执行，不得以"已经有类似逻辑"为由绕过。**

- **FROZEN 原则**：本文第 2 节列出的文件，在第 4 节 V0 验收标准达成之前，
  不允许做任何新增功能或"改造/适配"。如果某个新功能似乎需要修改它们，先停下来，
  在 `docs/research-harness-roadmap.md` 写明原因，等待人工确认。

- **LLM 主路径原则**：任何"给定一个 idea/topic，产出方向、假设、实验设计、候选方法"
  的逻辑，**必须**通过真实 LLM 调用（`services/llm/client.py` 的 `chat()`）完成，
  并且 prompt 必须把"用户原始 idea + LiteratureAgent 产出的文献笔记"作为真实输入。
  **不允许**新增任何"关键词 → 固定枚举 → 模板字符串"路径作为主路径。
  如果 LLM 调用失败，允许 fallback，但 fallback 输出必须显式标记
  `"source": "fallback_template"`，且不得进入"主结论/主论文/主报告"。

- **TaskFamily / DomainId 降级原则**：`TaskFamily`（4个值）和 `AutoResearchDomainId`
  （3个值）这两个 Literal 类型**不再作为 IdeaAgent 输出的约束**。它们可以继续存在，
  仅用于"统计层选择哪个评测脚本"这种内部路由，但不能再出现在"这是系统能想到的
  全部方向空间"的语义里。

- **新代码隔离原则**：新代码统一放在 `backend/services/research_harness/`，
  不散落进 `backend/services/autoresearch/`。

---

## 1. 病灶定位（取代 v1 第 6 章）

**一句话总结**：ScholarFlow 现在是一个"参数化玩具 ML benchmark 运行器"，外面套了一层
非常厚的审计/治理/打包系统；运行器和审计层都是真实代码，但运行器运行的是写死的东西，
不是 agent 想出来的东西。

### 1.1 具体证据（文件路径+行为均可验证）

**`services/autoresearch/idea_brief.py`（1027行，`build_research_brief` 所在）**

核心逻辑是关键词分类函数 `_preferred_task_families`（子串匹配 → 4 个 TaskFamily 之一）+
字符串模板函数 `_direction_from_family`（拼出 research_question / hypothesis /
method_sketch）+ 硬编码算术公式 `_score_direction`（base=0.72，按 family / budget /
序号加减固定常数算 feasibility）。**全文件 0 处 LLM 调用，0 处读取 literature_scout
的输出。** 所谓"多个候选方向"，不是 AI 提出的。

**`services/autoresearch/benchmarks.py`（2461行）**

`infer_task_family` 是子串匹配；`default_search_strategies` 给每个 family 提供 3-4
个写死的策略名（IR: overlap / idf / bigram / ledger-aware reranker；tabular:
threshold / perceptron；text: keyword / naive-bayes；llm_evaluation: zero-shot /
few-shot / rule-based）。**全文件 0 处 LLM 调用。**

**`services/autoresearch/experiment_factory.py`（2699行）**

把上述策略名变成 `ExperimentSpec`。**全文件 0 处 LLM 调用。**

**`services/autoresearch/codegen.py`（1664行）**

唯一有 LLM 调用的"方法生成"环节（`method_gen_v0.1.0.md`），但 prompt 显式要求：
"只用标准库、单个 `predict()` 函数、签名固定为 4 种之一、novel = 比 majority-class 好"。
LLM 失败时 fallback 到文件内写死的 `overlap_ranker` / `idf_ranker_factory` /
`ledger_aware_ranker_factory` / `naive_bayes` 实现。
结论：即使 LLM 生效，**系统结构性地无法构建任何涉及 embedding / 向量检索 / 预训练模型
的方法**——因为标准库里没有这些。这正好解释了为什么 v1 第 5 章那个"Citation-Faithful
RAG"题目，最后的 proposed method 是一个 IDF+bigram+ledger-weight 纯标准库重排器，
而不是任何跟 RAG / embedding 有关的东西。

**`schemas/autoresearch.py`**

`AutoResearchDomainId` 只有 `claim_evidence_retrieval` / `rag_citation_faithfulness` /
`lightweight_ml_nlp_benchmark` / `unsupported` 四个值。其中 `rag_citation_faithfulness`
几乎与 v1 第 5 章"上一轮真实测试题目"同名——说明每次换真实 idea 测试，就需要为它
添加一个硬编码 domain，而不是系统具备面对任意 idea 的能力。

**体量不对称**

`project_paper_orchestrator.py` 单文件 **13975 行 / 649KB**，比 idea_brief +
benchmarks + experiment_factory + codegen 四个"思考相关"文件加起来（约 7900 行）
还大 77%，占后端总代码量（103728 行）的约 13.5%。这个数字直接体现了"包装优先于思考"
的代码演化方向。

**文档已失效**

README / README_CN 引用的 `PROJECT_PLAN.md`、`AGENTS.md`、`SYSTEM_PROMPT.md`、
`docs/architecture.md`、`docs/fars-reference.md` 均不存在于仓库中；
"主测试文件"路径写成 `test_autoresearch.py`，实际应为
`test_autoresearch_regressions.py`。

### 1.2 真正值得保留的部分（不要误删）

- **`services/sandbox/backends.py`**：真实 `subprocess.run([sys.executable, "main.py"])`
  + Docker 后端 + `__RESULT__` JSON 解析，工作良好，新代码直接复用。
- **`services/autoresearch/runner.py` 中的统计函数**：`_confidence_interval`、
  `_paired_sign_flip_test`、`_power_style_analysis`、`_holm_bonferroni_adjustment`，
  实现质量高，直接抽出来用。
- **`services/autoresearch/literature_connectors.py`**：arXiv / Semantic Scholar /
  Crossref 真实调用，连带 cache freshness policy，直接复用。
- **evidence-ledger / claim-audit 思路**：方向对——2026 年 5 月的 ARIS 论文把
  "产出看似成功但证据不全/被误传的结论"称为"plausible unsupported success"，认为这是
  自动科研系统最主要的失败模式。ScholarFlow 的 claim 约束机制在解决真实问题，
  只是建在了一个空心的大脑上。等 V0 内核成立后，这套机制应作为 Auditor Layer 接入。

### 1.3 关于 ARIS/FARS 的事实校正

FARS 在 417 小时内消耗约 216 亿 token、花费 18.6 万美元生成 166 篇论文，平均每篇
约 1100 美元。"做一个能持续产出会议水平论文的 FARS 级系统"对个人开发者而言，
在预算上是不现实的，不应作为 V0 或 V1 的目标。

ARIS（Auto-Research-in-Sleep，2026 年 5 月开源）的实现方式与 ScholarFlow 完全不同：
它是一套面向 Claude Code / Codex 等 LLM agent 的纯 Markdown skill 文件集合，
不重新发明 agent 能力（代码执行 / 文件操作 / 规划这些 Claude Code 本身就有），
只提供"该怎么思考、怎么留痕、互相审"的 prompt + 约定 + 跨模型对抗审稿机制。

即：**ChatGPT 给 ScholarFlow 设计的"用 FastAPI 后端自己实现 orchestrator / queue /
sandbox 来充当 agent"，与真实 ARIS 的做法正好相反。** 真实 ARIS 把"能不能执行代码/
读文件/规划"这件事完全外包给已有 agent，自己只负责"怎么思考科研问题"。

ScholarFlow 作为独立 web 应用的定位没有问题，但它需要一个能真正"思考"的 LLM 内核，
而不是一套把 LLM 工具化但把思考写死在代码里的系统。

---

## 2. FROZEN 清单（V0 验收前不得新增工作）

以下文件原样保留在仓库中作为历史参考，V0 达成前不做任何功能性修改：

```
backend/services/autoresearch/project_paper_orchestrator.py  # 13975行，最大的偏差来源
backend/services/autoresearch/review_publish.py
backend/services/autoresearch/release_governance.py
backend/services/autoresearch/deployment.py
backend/services/autoresearch/console.py
backend/services/autoresearch/operator_control.py
backend/services/autoresearch/idea_brief.py           # 核心病灶之一：0 LLM 的 idea 生成
backend/services/autoresearch/experiment_factory.py   # 核心病灶之二：0 LLM 的实验设计
backend/services/autoresearch/benchmarks.py           # 核心病灶之三：写死的 catalog
backend/services/autoresearch/codegen.py              # 仅 fallback 模板部分冻结
```

"冻结"的含义：
- 这些文件不删除。
- 不在它们里面添加新功能。
- 不以"改造"的名义为 research_harness 新流程适配它们（改造 = 变相扩大它们的地位）。
- 它们的测试继续跑，regression 继续通过，但新核心的成功与否不依赖它们。

---

## 3. EXTRACT 清单（V0 第一步做的小范围抽取）

把以下**纯工具性、与 4-family/3-domain 封闭设计无关**的代码抽取到
`backend/services/research_harness/utils/`，不改逻辑，只换路径：

| 来源 | 抽取内容 | 目标文件 |
|------|----------|----------|
| `runner.py` | `_confidence_interval`、`_paired_sign_flip_test`、`_paired_differences`、`_power_style_analysis`、`_holm_bonferroni_adjustment` | `utils/stats.py`（去掉下划线前缀） |
| `services/sandbox/` | 整个目录 | 原路径保留，直接 import，不必移动 |
| `literature_connectors.py` | 各 source connector 的"调用并返回 paper 列表"函数 | `utils/literature_fetch.py`（薄封装，原始 connector 不动） |

---

## 4. V0：最小可信闭环（最高优先级，先于任何 schema/workspace/cockpit 工作）

V0 不追求 UI 完美，不追求 workspace 布局规范，不追求生产级别的 task queue。
只追求一件事：**对一个真实 CS idea，AI 自己读文献、自己提出假设、自己写代码、
自己跑实验、自己被审稿、自己报告结论（包括负面结论）。**

实现方式：V0 允许是一个 Python 脚本（`scripts/research_harness_v0.py`）或一组
`backend/services/research_harness/` 模块，**不要求接入 FastAPI endpoint，
不要求前端可见，不要求 task_queue**。能 `python scripts/v0_run.py --idea "..."` 
跑通就算达标。

### 4.1 输入

一个真实 idea 字符串。建议第一次用 v1 文档已测试过的主题：

> "Citation-Faithful RAG Answer Verification with Evidence-Aware Retrieval
>  and Abstention Calibration"

这样可以直接对比"模板系统产出"和"真实 agent 产出"在同一题目上的差距。

### 4.2 Sandbox 能力边界（必须在写第一行 ExperimentEngineer 代码前决定）

这是 V0 最重要的一个架构决策，v1 没有处理。**新 `method_gen` prompt
不再限定纯标准库**，允许以下包：

- 必选：`numpy`、`scikit-learn`、`pandas`
- 按需选择之一（影响能否真正实现 RAG 类 idea）：
  - **选项 A**（保守）：不引入 embedding，限定在 TF-IDF / sparse retrieval 实验，
    RAG 类 idea 只能实现"无 embedding 的近似"。成本低，开箱即运行。
  - **选项 B**（推荐）：加 `sentence-transformers`（用 `all-MiniLM-L6-v2` 这类小模型）
    或调用 embedding API（DeepSeek / OpenAI embeddings）。代码可以真实实现
    dense retrieval / RAG 类方法。需要确认 sandbox 里能装这个包。
  - **选项 C**（激进）：允许 HuggingFace `transformers`，但 GPU 不保证，
    大模型训练不在 V0 范围内。

**建议选 B**。V0 的测试题目（Citation-Faithful RAG）如果连 embedding 都用不了，
产出的"proposed method"和 v1 那个 IDF 重排器没有本质区别，V0 就失去了证明价值。

决策后把允许的包写进一个常量/配置，ExperimentEngineer 的 prompt 引用它。

### 4.3 六个 agent step 与输出约定

#### Step 1：LiteratureAgent

**目标**：用 LLM 驱动文献检索，产出结构化笔记，而不是把论文列表直接扔给下游。

```
输入：idea（字符串）
LLM 调用 1：用 idea 生成 3-5 个检索 query（不同角度：方法/数据集/评测/近期工作）
调用 literature_fetch.py：对每个 query 调 arXiv / Semantic Scholar / Crossref
LLM 调用 2：对返回的论文列表（标题+摘要），产出 structured literature notes
```

输出文件：
```
workspace/<project_id>/literature/search_queries.json   # LLM 生成的检索 query
workspace/<project_id>/literature/papers.jsonl          # 原始论文元信息
workspace/<project_id>/literature/notes.md              # LLM 产出的结构化阅读笔记
workspace/<project_id>/literature/gap_map.md            # LLM 总结的 research gap
workspace/<project_id>/literature/known_baselines.md    # LLM 识别的已知 baseline 方法
```

**LLM prompt 要求**（写进 `prompts/research_harness/literature_agent_v1.md`）：
- 让模型对每篇论文输出：方法核心/实验设置/声称的主要结论/局限性/与当前 idea 的关系。
- gap_map 必须列出：已知方法的共同局限、没有被充分研究的角度、本 idea 与已有工作
  的可能区分点（哪怕是"暂时不确定"也要写出来，而不是空着）。
- 如果检索结果为空或过少（<5 篇真实相关论文），必须在 notes.md 里显式记录
  `"literature_coverage": "insufficient"`，这会影响后续 IdeaAgent 的 novelty 评估。

#### Step 2：IdeaAgent

**目标**：基于 gap_map + notes 用 LLM 自由提出假设，不受 TaskFamily / DomainId 约束。

```
输入：idea（字符串）+ gap_map.md + notes.md
LLM 调用：生成 ≥5 个 hypothesis candidates
```

每个 candidate 必须包含以下字段（JSON）：
```json
{
  "hypothesis_id": "h1",
  "research_question": "...",                  // 具体可检验的问题
  "core_novelty": "...",                        // 引用 literature notes 说明不同在哪
  "proposed_method_sketch": "...",              // 自由描述，不限于 catalog
  "feasibility_in_sandbox": "high/medium/low", // LLM 自评：用 §4.2 的包能否实现
  "feasibility_reason": "...",                 // 说明原因
  "expected_result_if_valid": "...",
  "expected_result_if_invalid": "...",         // 必须有，体现"honest hypothesis"
  "kill_criteria": ["..."],                    // 在什么情况下放弃这个方向
  "estimated_runtime_minutes": 10              // LLM 估算，上限即 §4.2 sandbox 时间预算
}
```

输出文件：
```
workspace/<project_id>/ideas/candidates.json   # 全部候选
workspace/<project_id>/ideas/selected.md       # 选中的方向 + 选择原因
```

选择逻辑（简单版，V0 不需要复杂 selector）：
优先选 `feasibility_in_sandbox = high` 且 kill_criteria 最具体的那个。
如果没有 high feasibility 的，记录原因并选 medium，或者明确输出
`"no_feasible_hypothesis": true` 终止流程（这本身就是一种有价值的结论）。

#### Step 3：ExperimentEngineer

**目标**：把 selected idea 变成真实可运行的 Python 实验代码，基于"失败也保留"的原则。

```
输入：selected.md + known_baselines.md + sandbox 能力边界（§4.2）
LLM 调用 1：生成 experiment plan（数据集、baseline 列表、proposed method 描述、
             ablation 设计、metric、统计检验类型、失败判据）
LLM 调用 2：生成 experiment.py（完整可运行脚本）
执行：sandbox runner（subprocess）
如果失败：把 stderr + 当前代码喂回 LLM，最多 N 轮 repair（建议 N=3）
```

`experiment.py` 约定（写进 prompt）：
- 必须实现：≥1 个 baseline + 1 个 proposed method + ≥1 个 ablation。
- 每个 system 的结果必须输出到 `print("__RESULT__", json.dumps({...}))` 供 runner 解析。
- results dict 必须包含：`system_name`、`metric_name`、`metric_value`、
  `n_test_examples`、`dataset_name`。
- 代码允许使用 §4.2 批准的包，**不需要限定纯标准库**。
- 数据集：优先用 HuggingFace datasets（`from datasets import load_dataset`）的公开小数据集；
  如果 RAG 类 idea，可以用 BEIR 子集（NFCorpus / SciFact / 任何 <10k 文档的子集）。

输出文件：
```
workspace/<project_id>/code/experiment.py
workspace/<project_id>/code/requirements.txt      # pip 依赖
workspace/<project_id>/artifacts/logs/run_1.log   # subprocess stdout+stderr
workspace/<project_id>/artifacts/metrics.json     # 解析后的 __RESULT__ 输出
workspace/<project_id>/artifacts/tables/results.csv
workspace/<project_id>/experiments/repair_log.md  # 每轮 repair 的错误+修复描述
```

**失败处理原则**：
- 如果 3 轮 repair 后代码仍不可运行：输出 `"execution_status": "failed_after_repair"`，
  写进 repair_log.md，**不生成假数据**，直接进入 ReviewerAgent（ReviewerAgent 此时
  的输入是"代码失败"这个事实本身）。
- 如果运行成功但 proposed method 没有超过 baseline：保留结果，标记
  `"beats_baseline": false`，继续进入 ReviewerAgent（诚实报告负面结果）。

#### Step 4：统计层

直接调用从 `runner.py` 抽出的 `utils/stats.py`：

```python
from research_harness.utils.stats import confidence_interval, paired_sign_flip_test, holm_bonferroni

# 对 baseline vs proposed 做统计检验
# 如果有多个 ablation，对每个 comparison 做，然后 holm_bonferroni 修正
```

输出追加到 `artifacts/metrics.json`，新增字段：`confidence_intervals`、
`significance_tests`、`holm_corrected`、`power_note`。

#### Step 5：ReviewerAgent

**目标**：以严格审稿人身份给出可执行的批评，而不是泛泛的 limitations 列表。

```
输入：idea + gap_map + selected.md + metrics.json + results.csv + repair_log.md
LLM 调用：生成 reviewer critique
```

Reviewer prompt 必须要求输出以下结构（写进 `prompts/research_harness/reviewer_v1.md`）：
```json
{
  "overall_assessment": "accept/weak_accept/weak_reject/reject",
  "strengths": ["..."],
  "weaknesses": [
    {
      "issue": "...",             // 具体的问题，不允许"improvement could be made"式模糊表述
      "severity": "major/minor",
      "evidence": "..."           // 引用 metrics 或 literature 中的具体数字/事实
    }
  ],
  "required_experiments": [
    {
      "action": "add_baseline/run_ablation/test_on_second_dataset/report_failure_mode/rewrite_related_work",
      "description": "...",
      "priority": "must_have/nice_to_have"
    }
  ],
  "publish_gate": "no_evidence/insufficient_evidence/borderline/publishable"
}
```

输出文件：
```
workspace/<project_id>/reviews/reviewer_round_1.md
workspace/<project_id>/reviews/action_plan_1.json
```

#### Step 6：一轮 follow-up + 最终报告

```
输入：action_plan_1.json + 当前 workspace 全部内容
ResearchManager（一个简单函数/LLM 调用）：
  - 选取 action_plan 里 priority=must_have 的第一个 required_experiment
  - 如果可在 sandbox 时间预算内完成：执行（回到 Step 3，生成 follow-up experiment）
  - 如果不可（需要 GPU/大数据/多天）：在最终报告里明确记录为"未来工作"
```

最终报告 `workspace/<project_id>/research_report.md`：
```
# Research Report: <idea>
## TL;DR
## Literature Context (摘自 gap_map)
## Selected Hypothesis
## Methods
## Results
  - 含 metrics 表格（自动从 metrics.json 生成）
  - 含统计检验结论
## Reviewer Critique Summary
## Follow-up Experiment (if any)
## Conclusion
  - 如果结果不优于 baseline，必须明确写成 negative result
  - 如果代码执行失败，必须写成 execution failure
  - 禁止在无实验证据时写"our method shows promising results"一类表述
## Limitations & Future Work
```

### 4.4 V0 验收标准（与 v1 第 12 节一致，但措辞更精确）

V0 通过要求：
1. `literature/papers.jsonl` 包含 ≥10 篇真实检索到的相关论文（非内置 fixture）。
2. `ideas/candidates.json` 包含 ≥3 个 hypothesis，每个均有 core_novelty 字段，
   且内容**不能**是"将 idea 匹配到 text_classification / ir_reranking / tabular
   这些 family 的变体表述"——需要有真正针对 gap_map 的回应。
3. `code/experiment.py` 可以被 `python experiment.py` 在不需要 GPU 的条件下运行
   （或在 repo README 说明的环境下运行）。
4. `artifacts/metrics.json` 包含至少 1 个 baseline 和 1 个 proposed method 的
   真实 metric 数值（不是 fixture / mock 数据）。
5. `reviews/reviewer_round_1.md` 中包含至少 1 个 `severity=major` 的 weakness，
   且 evidence 字段引用 metrics.json 中的具体数字。
6. `research_report.md` 结论部分：如果 proposed method 没有显著超过 baseline，
   必须明确写出 negative result 而不是"promising"类措辞。
7. 人类打开 workspace 目录，看完 research_report.md，能判断：
   "这个系统真的读了文献、真的试图提出新方法、真的跑了实验、真的报告了失败。"

**反例（不通过）**：
- `proposed_method_sketch` 内容是"apply ledger-aware reranking on BM25"
  ——这和旧系统写死的策略没有区别。
- `research_report.md` 里写了"the proposed method achieves competitive results"
  但 metrics.json 里 proposed < baseline。
- `papers.jsonl` 里的论文全是"内置的 offline context"，没有真实网络检索。

---

## 5. V1：产品化（V0 验收后进行）

V0 产出的是一个可跑的脚本/模块集合，V1 把它接入 ScholarFlow 的 FastAPI + React。

### 5.1 API 层（最小化）

只需要以下端点，其余继续走旧的 autoresearch API：
```
POST /api/research-harness/projects/{project_id}/start
  body: { "idea": "..." }
  返回: { "run_id": "..." }

GET  /api/research-harness/projects/{project_id}/runs/{run_id}/status
GET  /api/research-harness/projects/{project_id}/runs/{run_id}/timeline
GET  /api/research-harness/projects/{project_id}/runs/{run_id}/files/{path}
```

timeline 是 `workspace/<project_id>/timeline.jsonl`，每个 agent step 完成后追加
一条记录：`{"step": "literature_agent", "status": "done", "ts": "...",
"output_files": ["literature/papers.jsonl", ...]}`

### 5.2 Workspace 布局（取代 v1 第 10 节，更简）

```
backend/data/research_workspace/<project_id>/
  project.yaml          # idea, created_at, run_id
  timeline.jsonl        # agent step 记录
  literature/
    search_queries.json
    papers.jsonl
    notes.md
    gap_map.md
    known_baselines.md
  ideas/
    candidates.json
    selected.md
  experiments/
    plan.md
  code/
    experiment.py
    requirements.txt
  artifacts/
    logs/
    metrics.json
    tables/
      results.csv
  reviews/
    reviewer_round_1.md
    action_plan_1.json
  paper/             # V2 才填充，V1 不做
  ledger/            # V2 才填充，V1 不做
```

**统一 DATA_DIR**：必须解决 v1 第 6.6 节指出的双 data root 问题。
统一为 `settings.DATA_DIR / "research_workspace" / project_id`，
旧的 `backend/backend/data` 路径用脚本做一次迁移或在代码里统一忽略。

### 5.3 Research Cockpit 前端（最小版）

按 v1 第 9.3 节三栏布局，但 V1 只实现：
- 左侧：项目列表 + run timeline（每个 step 的状态 icon + 耗时）。
- 中间：workspace 文件浏览器（点击可查看各个 .md / .json 文件原内容）。
- 右侧：ReviewerAgent 的批评 + action_plan。

**不做**：代码编辑器（工程师看，不是用户改的）、
Operator Console 深化、release package UI、venue adapter。

---

## 6. V2：Writer + Auditor Layer（V1 验收后进行）

这对应 v1 的 Phase 6 + Phase 1（workspace schema 精化）+ Auditor Layer 接入。

主要工作：
- **WriterAgent**：基于 `artifacts/` + `ideas/selected.md` + `reviews/action_plan_1.json`
  写论文草稿（contribution.md → outline.md → draft.md），使用
  `prompts/autoresearch/paper_writer/` 里已有的 section prompts（可复用）。
- **AuditorAgent**：把 v1 里 `claim_evidence_gate.py` / `citation_verifier.py` /
  `paper_evidence_compiler.py` 的逻辑，作为"写作后的门控"接入新流程：
  draft.md 里的每条 claim 必须在 `artifacts/metrics.json` 或 `literature/papers.jsonl`
  中找到支撑，否则标记为 `[UNVERIFIED]`，不通过 Auditor gate 就不能进入
  "final research_report"。
- **evidence ledger 接入**：把旧 `claim_evidence_gate.py` 的逻辑移植成
  `research_harness/auditor.py`，输出到 `ledger/claim_audit.json`。

**不做**：release governance 扩展、venue adapter、compliance checklist UI 深化、
publish archive 变体——这些对应 v1 第 8.1 节"停止继续堆"的方向，至少在 V2 前不碰。

---

## 7. 技术债优先级（从 v1 第 14 节提取，补充了具体方案）

| 优先级 | 问题 | 具体方案 |
|--------|------|----------|
| P0 | `idea_brief.py` 的 0-LLM 路径是主路径 | V0 的 IdeaAgent 绕过它，V1 后考虑归档 |
| P0 | `method_gen` prompt 限定纯标准库 | V0 起新 prompt，明确允许 §4.2 的包 |
| P0 | `build_research_brief` 不读 literature 输出 | V0 的 IdeaAgent 强制以 gap_map 为输入 |
| P1 | 双 data root | V1 时统一为 `settings.DATA_DIR / "research_workspace"` |
| P1 | README 引用的文件不存在 | V0 跑通后补写 AGENTS.md + docs/research-harness-roadmap.md |
| P1 | deterministic test 与 live research run 混在一起 | V0 起，research_harness 的端到端测试走独立 pytest mark `@pytest.mark.live_research`，不进 CI |
| P2 | `project_paper_orchestrator.py` 体量过大 | V2 以后逐步降级为读取新 workspace 文件的兼容层 |
| P3 | release archive / venue adapter / compliance UI | 不做，直到 V2 Writer 产出质量满足要求 |

---

## 8. 风险与约束（补充 v1 第 15 节）

### 8.1 Sandbox 能力决策（V0 前必须做，§4.2）

如果选 Option B（sentence-transformers），需要确认：
- 本地 sandbox 能否在合理时间（<10min）安装 + 运行 `all-MiniLM-L6-v2`？
- 如果 sandbox 是 Docker 容器，base image 需要包含这个包还是能 pip install？

这个决策不锁定，但必须在动手写 ExperimentEngineer 之前做，因为它决定
"RAG 类 idea 能否被真实实现"这件根本性的事。

### 8.2 LLM 成本预估（V0 一次完整 run）

粗估：
- LiteratureAgent：2 次 LLM 调用（query 生成 + 笔记压缩），输入包含论文摘要列表，
  约 3k-8k tokens/call → ~0.05-0.2 USD（DeepSeek Chat）
- IdeaAgent：1 次调用，约 2k-5k tokens → ~0.02-0.1 USD
- ExperimentEngineer：1-3 次（含 repair），约 2k-8k tokens/call → ~0.05-0.3 USD
- ReviewerAgent：1 次，约 3k-8k tokens → ~0.05-0.2 USD
- 合计：**单次完整 V0 run 约 0.2-0.8 USD（DeepSeek）或 2-8 USD（GPT-4o）**

建议用 DeepSeek Chat 跑 V0，成本可控；需要更强 reasoning 时用 GPT-4o 或 claude-sonnet-4-6。

### 8.3 伪贡献风险（继承 v1 第 15.3 节，强化措辞）

V0 必须继续保留以下硬 gate，**且这些 gate 必须在 research_report.md 生成之前运行**，
不允许因为"流程跑完了"就绕过：
- 未运行实验 → 不生成结论（`execution_status != "success"` 时 report 写 "no results"）
- proposed < baseline → 报告 negative result，不写 "competitive / promising"
- 统计检验不显著 → 不写 "significantly outperforms"
- 检索论文 <5 篇 → gap_map 显式标注 `"literature_coverage": "insufficient"`，
  report 中 novelty claim 必须附带这个标注

---

## 9. 完整 Prompt 清单（V0 需要新写的 prompt 文件）

```
backend/prompts/research_harness/
  literature_agent_v1.md      # Step 1：query 生成 + 论文笔记压缩
  idea_agent_v1.md            # Step 2：hypothesis bank 生成（自由格式，无 TaskFamily 约束）
  experiment_planner_v1.md    # Step 3a：experiment plan 生成
  experiment_codegen_v1.md    # Step 3b：experiment.py 生成（含 sandbox 能力说明）
  experiment_repair_v1.md     # Step 3c：repair（输入 stderr + 当前代码）
  reviewer_v1.md              # Step 5：reviewer critique（要求具体 + JSON 结构）
  research_manager_v1.md      # Step 6：follow-up 选择逻辑
```

这 7 个 prompt 是 V0 的全部 LLM prompt，不需要更多。V0 阶段不写 writer / auditor prompt。

---

## 10. 一句话判断

ScholarFlow 现在的价值放错了位置——它的 evidence/claim 机制解决的是真实问题
（防止自动科研系统产出"看似成功但无证据支撑的结论"），但"想什么、怎么想、如何实验"
这个核心完全没有 LLM 参与，是一套关键词→模板系统。

V0 的目标不是"做一个 ARIS/FARS"，而是**证明 ScholarFlow 里真的有一个会思考的大脑**：
能读文献、能提出和已有工作不同的假设、能写出并运行真实实验代码、能诚实报告失败。
大脑成立之后，现有的 evidence/audit/claim 层才有接入的意义。
