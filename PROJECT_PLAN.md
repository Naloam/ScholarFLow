# ScholarFlow — 大学生全流程学术论文写作 Agent 系统

## 项目规划文档 v1.0

> **文档目的**：作为整个项目从设计到开发的唯一权威参考。所有后续开发工作均以本文档为基准。
>
> **最后更新**：2026-03-11

---

## 目录

1. [项目定位与愿景](#1-项目定位与愿景)
2. [核心决策：构建路线](#2-核心决策构建路线)
3. [参考项目深度分析与借鉴](#3-参考项目深度分析与借鉴)
4. [系统架构总览](#4-系统架构总览)
5. [Agent 体系设计](#5-agent-体系设计)
6. [Agent 间通信与协作机制](#6-agent-间通信与协作机制)
7. [技术栈选型](#7-技术栈选型)
8. [产品功能设计（面向大学生）](#8-产品功能设计面向大学生)
9. [质量标准与评估体系](#9-质量标准与评估体系)
10. [开发阶段与里程碑](#10-开发阶段与里程碑)
11. [风险与应对策略](#11-风险与应对策略)
12. [附录：数据结构与接口规范](#12-附录数据结构与接口规范)

---

## 1. 项目定位与愿景

### 1.1 一句话定义

面向大学生（本科 / 硕士）的全流程学术论文写作 Agent 系统——从零开始，引导学生完成一篇可提交的学术论文。

### 1.2 目标用户

| 用户角色 | 描述 | 核心诉求 |
|----------|------|----------|
| **大学生（主要）** | 本科毕业论文、课程论文、竞赛论文（如数模） | 没写过论文，需要全流程引导；降低门槛 |
| **硕士研究生** | 小规模研究论文、文献综述 | 加速写作效率，保证引用质量 |
| **导师 / 助教** | 指导学生论文 | 查看进度、逐段批注、自动审稿反馈 |

### 1.3 产出形式

- 结构完整的论文草稿（引言、背景/文献综述、方法、实验/结果、讨论、结论、参考文献）
- 支持导出 **LaTeX / Word / Markdown / PDF**
- 附带引用溯源报告（每条断言对应来源论文 + 页码 + 原文片段）
- 可选：代码实验复现包（Notebook + 依赖清单 + 运行日志）

### 1.4 核心原则

1. **可验证性优先**：AI 生成的每个重要断言都必须能追溯到具体文献证据，杜绝幻觉
2. **教学引导（Scaffold）**：不是"直接写完"，而是分步骤引导学生理解每个写作环节
3. **人类始终在环（HITL）**：AI 辅助，人来确认；学生保持对论文的理解和控制
4. **科研级严谨**：引用正确、证据充分、格式合规、可检测抄袭

---

## 2. 核心决策：构建路线

### 2.1 最终决策：混合路线（并行双轨）

> **结论**：不是"二选一"，而是两条线**并行推进**。

```
┌─────────────────────────────────────────────────────────────────┐
│                        混合路线（推荐）                          │
├─────────────────────────┬───────────────────────────────────────┤
│   短期（快速出效果）     │   长期（科研级自研）                    │
│   低代码 Workflow MVP    │   自研核心后端模块                      │
│   ↓                     │   ↓                                    │
│   验证产品流程 & UX      │   证据追溯 / PDF 解析 / 向量索引        │
│   收集用户反馈           │   实验沙箱 / 自动审稿 / 引用系统        │
│   3-8 周可演示           │   3-12 月逐步替换                      │
│                         │   ↓                                    │
│   ←─── 自研模块作为插件接入低代码平台 / 自建前端 ───→            │
└─────────────────────────┴───────────────────────────────────────┘
```

### 2.2 为什么不完全从零开始

- 大学生项目需要**快速看到效果**来验证想法是否成立
- 低代码 Workflow（Coze / n8n / Dify）可以在几周内串联出可演示的 MVP
- 避免前期花大量时间建基础设施而看不到产品形态

### 2.3 为什么不完全依赖低代码

- **证据可追溯性**（provenance）是科研级核心能力，低代码平台无法精细控制
- **PDF 全文解析 + 学术向量索引**需要自研，这是系统质量的命脉
- **实验沙箱（Docker 化代码执行）**需要自建
- 长期来看，可控性和可扩展性决定产品天花板

### 2.4 并行策略时间线

| 时间 | 短期线（低代码 MVP） | 长期线（自研核心） |
|------|--------------------|--------------------|
| 第 1-2 周 | 搭建 Coze/Dify Workflow 原型 | 技术选型 + 环境搭建 |
| 第 3-6 周 | MVP 可演示（检索→摘要→草稿→Review） | PDF 解析 + 向量索引 + 证据 DB |
| 第 7-12 周 | 用户测试 + 反馈迭代 | SearchAgent + ReaderAgent 开发 |
| 第 13-24 周 | 将自研模块接入替换低代码节点 | WritingAgent + ReviewAgent + 沙箱 |
| 第 25+ 周 | 完全迁移到自研平台 | 完善 UX + 导师模式 + 部署 |

---

## 3. 参考项目深度分析与借鉴

### 3.1 FARS（Fully Automated Research System）— Analemma

| 维度 | 内容 |
|------|------|
| **是什么** | 端到端自动化研究系统，包含 Ideation → Planning → Experiment → Writing 四个 Agent |
| **核心架构** | 多 Agent 通过**共享文件系统**协作，无需 Agent 间直接通信；每个 Agent 读写结构化项目目录 |
| **关键能力** | 160 GPU 集群作为实验工具；自动假设生成 + 实验验证 + 论文写作；负面结果也会报告 |
| **可借鉴** | ① 四阶段 Agent 流水线架构<br>② 共享文件系统作为协作媒介（简洁高效）<br>③ "假设 + 验证"的科研范式 |
| **需裁剪** | FARS 面向无人干预的完全自动化，我们需要保留 HITL（人审）以适配学生教学场景 |
| **参考** | https://analemma.ai/blog/introducing-fars/ |

**架构启示**：FARS 的四 Agent 模型（Ideation / Planning / Experiment / Writing）是我们系统的骨架。我们在此基础上增加 Search、Reader、Evidence、Review、Tutor 等专业 Agent。

### 3.2 PaSa（Bytedance）— 学术论文检索 Agent

| 维度 | 内容 |
|------|------|
| **是什么** | ACL 2025 Main，面向复杂学术查询的自动论文检索 Agent |
| **核心架构** | 双 Agent：**Crawler**（搜索 + 引用扩展 + 论文阅读）+ **Selector**（相关性评分筛选） |
| **关键能力** | Recall@50 超过 Google Scholar + GPT-4o 基线 39.9%；支持关键词搜索 + 引用网络爬取 |
| **训练方式** | SFT + PPO 强化学习，基于 Qwen2.5-7B |
| **可借鉴** | ① Crawler + Selector 双 Agent 分工模式（搜集 vs 筛选）<br>② 引用网络扩展策略<br>③ 多轮搜索 + 阅读 + 决策的循环 |
| **参考** | https://github.com/bytedance/pasa |

**架构启示**：我们的 SearchAgent 应采用 PaSa 的 Crawler-Selector 双层模式——先广泛搜集，再精准筛选排序。

### 3.3 Agent Laboratory — LLM Agent 作为研究助手

| 维度 | 内容 |
|------|------|
| **是什么** | 输入研究 idea → 输出研究报告 + 代码仓库的框架 |
| **核心架构** | 三阶段：Literature Review → Experimentation → Report Writing；mle-solver 做实验，paper-solver 做写作 |
| **关键能力** | Co-Pilot 模式（人引导）评分高于全自动模式；支持 arXiv + HuggingFace + Python + LaTeX |
| **可借鉴** | ① **Co-Pilot（人引导）模式显著优于全自动**——验证了 HITL 的价值<br>② 三阶段流程（文献→实验→写作）的简洁设计<br>③ mle-solver 的迭代代码改进思路 |
| **参考** | https://agentlaboratory.github.io/ |

**架构启示**：Co-Pilot 模式是我们面向学生的核心交互模式。全自动写作质量不够（NeurIPS 评分仅 4/10），人引导后提升至 4.38/10——证明 HITL 不可或缺。

### 3.4 Stanford Agentic Reviewer — 自动审稿

| 维度 | 内容 |
|------|------|
| **是什么** | 斯坦福 ML 组的论文自动审稿系统，Spearman 相关性达到人类审稿人水平（0.42 vs 人与人 0.41） |
| **核心 Workflow** | PDF → Markdown → 生成搜索查询 → Tavily 搜索 arXiv → 下载相关论文元数据 → 评估相关性 → 摘要/全文总结 → 综合审稿 |
| **评分维度** | 7 维：原创性、研究问题重要性、证据支持度、实验可靠性、写作清晰度、社区价值、先前工作上下文化 |
| **可借鉴** | ① 7 维评分体系直接用于我们的 ReviewAgent<br>② "搜索相关论文→评估相关性→选择性深读"的流程<br>③ 用线性回归组合多维评分为综合分数 |
| **参考** | https://paperreview.ai/tech-overview |

**架构启示**：ReviewAgent 完全可以复用这套 7 维评分 + 审稿 Workflow。对学生来说，这就是一个"虚拟导师"。

### 3.5 其他参考工具

| 工具 | 用途 | 集成方式 |
|------|------|----------|
| **Google NotebookLM** | 文献阅读与笔记 | 参考其交互设计；不直接集成 |
| **Napkin AI** | 科研绘图/可视化 | 可作为外挂工具；或自研简单图表生成 |
| **Semantic Scholar API** | 学术检索 + 元数据 + 学术 Embeddings | 核心检索后端之一 |
| **arXiv API** | 开放获取论文源 | 核心检索后端之一 |
| **CrossRef API** | DOI 核查 + BibTeX 元数据 | 引用管理的元数据来源 |

### 3.6 学术写作 Skills 资源（可直接复用）

开发过程中，**鼓励 AI 主动搜索 GitHub 上的学术写作相关 Skills 仓库**，借鉴或直接使用其中的技能定义、Prompt 模板和写作规范。以下是已知的高质量资源：

| 仓库 | Stars | 内容概述 | 建议用法 |
|------|-------|----------|----------|
| **[claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills)** | 14.3k | 170+ 科学/研究 Skills，覆盖文献检索、科学写作、Peer Review、文档处理、引用管理、可视化等 | ① 直接安装 `scientific-skills/` 下的 Skills（如 `Literature Review`、`Scientific Writing`、`Peer Review`、`Citation Management`）到 `.cursor/skills/` 或 `.claude/skills/`<br>② 参考其 Prompt 结构和最佳实践设计我们的 Agent Prompt |
| **[claude-scholar](https://github.com/Galaxy-Dawn/claude-scholar)** | 1.2k | 面向学术研究全生命周期的配置系统：32 Skills + 50+ Commands + 14 Agents，覆盖选题→文献→实验→写作→审稿→投稿→Rebuttal 全流程 | ① 参考其 7 阶段 Workflow 设计（Research Ideation → ML Project → Experiment Analysis → Paper Writing → Self-Review → Rebuttal → Post-Acceptance）<br>② 借鉴 `ml-paper-writing`、`citation-verification`、`writing-anti-ai`、`paper-self-review` 等 Skills<br>③ 参考其 `paper-miner` Agent 的知识抽取模式 |

**使用原则**：
- 遇到特定写作/检索/审稿子任务时，优先搜索是否有现成 Skill 可直接使用
- AI 开发者可以主动在 GitHub 搜索更多 `academic writing skill`、`scientific agent`、`paper writing prompt` 等关键词发现新资源
- 使用第三方 Skill 时注意检查其 License（上述两个仓库均为 MIT）

---

## 4. 系统架构总览

### 4.1 高层架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              前端层 (Frontend)                          │
│   React/Vue + TipTap 编辑器 + 证据侧栏 + 分步向导 + 实时预览           │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │ WebSocket / REST API
┌─────────────────────────▼───────────────────────────────────────────────┐
│                          API 网关层 (Gateway)                           │
│   认证 (JWT) │ 限流 │ 路由 │ 审计日志                                    │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────────────┐
│                      编排层 (Orchestration)                              │
│                                                                         │
│   ┌─────────────┐                                                       │
│   │ MainAgent   │  任务分解 → Agent 调度 → 上下文管理 → 进度追踪        │
│   │ (编排核心)  │  失败重试 → 成本控制 → 降级策略                        │
│   └──────┬──────┘                                                       │
│          │ 事件驱动 (消息队列)                                            │
│   ┌──────▼──────────────────────────────────────────────────────────┐   │
│   │                    专业 Agent 集群                               │   │
│   │                                                                  │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │   │
│   │  │ Tutor    │ │ Search   │ │ Fetcher  │ │ Reader   │           │   │
│   │  │ Agent    │ │ Agent    │ │ Agent    │ │ Agent    │           │   │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │   │
│   │  │ Evidence │ │ Writing  │ │ Editor   │ │ Review   │           │   │
│   │  │ Agent    │ │ Agent    │ │ Agent    │ │ Agent    │           │   │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │   │
│   │  ┌──────────┐ ┌──────────┐                                      │   │
│   │  │ Sandbox  │ │ Analysis │                                      │   │
│   │  │ Agent    │ │ Agent    │                                      │   │
│   │  └──────────┘ └──────────┘                                      │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────────────┐
│                        基础设施层 (Infrastructure)                       │
│                                                                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │ 向量 DB    │ │ 关系 DB    │ │ 文件存储   │ │ 消息队列           │   │
│  │ FAISS/     │ │ PostgreSQL │ │ S3/MinIO   │ │ Redis Streams/     │   │
│  │ Milvus     │ │            │ │            │ │ RabbitMQ           │   │
│  └────────────┘ └────────────┘ └────────────┘ └────────────────────┘   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                          │
│  │ LLM 适配层 │ │ 实验沙箱   │ │ 缓存层     │                          │
│  │ (多模型)   │ │ Docker     │ │ Redis      │                          │
│  └────────────┘ └────────────┘ └────────────┘                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 数据流全景（用户视角）

```
用户输入研究主题/关键词
        │
        ▼
  ┌─ TutorAgent ─────── 拆解为分步任务，引导用户明确研究方向
  │     │
  │     ▼
  ├─ SearchAgent ─────── 检索 Semantic Scholar / arXiv / CrossRef
  │     │                 (Crawler + Selector 双层模式，借鉴 PaSa)
  │     ▼
  ├─ FetcherAgent ────── 下载 PDF → GROBID 结构化解析
  │     │
  │     ▼
  ├─ ReaderAgent ─────── chunking → embedding → 多粒度摘要 → 证据片段抽取
  │     │
  │     ▼
  ├─ EvidenceAgent ───── 维护 claim→evidence 映射，生成 BibTeX
  │     │
  │     ▼
  ├─ WritingAgent ────── 按模板生成各章节草稿（Claim + Evidence 模式）
  │     │
  │     ▼
  ├─ [SandboxAgent] ──── 运行实验代码 → 生成图表 → 插入稿件（可选）
  │     │
  │     ▼
  ├─ EditorAgent ─────── 学术语言润色 + 格式化（LaTeX/Word）
  │     │
  │     ▼
  ├─ ReviewAgent ─────── 7 维自动审稿（借鉴 Stanford Agentic Reviewer）
  │     │                 输出改进建议 → 触发回环修改
  │     ▼
  └─ 用户确认 ────────── 逐段 review → 编辑 → 版本保存 → 导出
```

---

## 5. Agent 体系设计

### 5.1 Agent 职责清单

#### 5.1.1 MainAgent（编排核心）

- **职责**：全局任务分解、Agent 调度、上下文管理、进度追踪、失败重试、成本控制
- **输入**：用户请求 + 系统状态
- **输出**：分派给具体 Agent 的子任务
- **借鉴**：FARS 的编排思路 + PaperAgent 的 MainAgent 概念
- **关键策略**：
  - 降级策略：先用本地小模型生成草稿，再用大模型润色
  - Token 成本预估：在调用高费用模型前评估并征求用户确认
  - 重试逻辑：Agent 失败后尝试替代路径，而非简单重试

#### 5.1.2 TutorAgent（教学引导）

- **职责**：将"写一篇论文"拆解为可完成的小步骤，像虚拟导师一样引导学生
- **输入**：用户当前阶段 + 研究主题
- **输出**：学习提示、当前步骤指引、示例参考、常见问题提醒
- **关键设计**：
  - 分阶段向导：选题确认 → 背景调研 → 研究问题定义 → 方法设计 → 实验计划 → 撰写各章节 → 修改润色
  - 每个阶段输出清单（checklist），学生完成后才进入下一阶段
  - 可配置"教学深度"：简洁模式（有经验的学生）vs 详细模式（新手）

#### 5.1.3 SearchAgent（学术检索）

- **职责**：根据研究主题检索相关论文，返回排序后的结果
- **输入**：搜索查询（关键词 / 自然语言描述）
- **输出**：论文列表（标题、作者、摘要、年份、引用数、DOI、PDF 链接、相关性评分）
- **借鉴 PaSa 双层模式**：
  - **Crawler 子模块**：生成多轮搜索查询 → 调用 Semantic Scholar / arXiv API → 引用网络扩展
  - **Selector 子模块**：对候选论文进行相关性评分和筛选排序
- **检索源**：
  - Semantic Scholar API（元数据 + 学术 embeddings）
  - arXiv API（开放获取 PDF）
  - CrossRef API（DOI 核查 + BibTeX）
- **排序策略**：可按 recency / citation count / relevance / venue 权重调节

#### 5.1.4 FetcherAgent（获取与预处理）

- **职责**：下载论文 PDF，执行结构化解析
- **输入**：论文 URL / DOI 列表
- **输出**：结构化文档（标题、摘要、各章节文本、表格、图像描述、参考文献列表）
- **技术实现**：
  - PDF 下载 + 存储（S3/MinIO）
  - **GROBID**：提取结构化书目信息和段落
  - **pdfplumber**：纯文本和表格抽取
  - **Tesseract OCR**：处理扫描版 PDF（兜底）
  - 处理付费墙情况：提示用户手动上传或通过校内代理

#### 5.1.5 ReaderAgent（深度阅读与理解）

- **职责**：对解析后的论文进行深度理解，生成多粒度摘要和证据片段
- **输入**：结构化论文文档
- **输出**：
  - 多粒度摘要（句子级、段落级、章节级、全文级）
  - 结构化证据片段：`{type: "method"|"result"|"conclusion", text, page, section}`
  - 向量 embeddings（用于后续 RAG 检索）
- **技术实现**：
  - 语义分块（semantic chunking），而非固定长度切割
  - 每个 chunk 生成 embedding（SPECTER2 或 OpenAI embeddings）
  - 存入向量数据库，支持后续基于语义的检索
  - 抽取"Method / Data / Result / Conclusion"结构化片段

#### 5.1.6 EvidenceAgent（证据管理与引用）

- **职责**：维护断言→证据的映射关系，确保每条生成内容可追溯
- **输入**：WritingAgent 输出的断言 + ReaderAgent 的证据库
- **输出**：
  - `{claim, evidence_refs: [{paper_id, title, page, snippet, confidence}]}`
  - BibTeX / DOI 格式的参考文献列表
  - 引用覆盖率报告
- **关键规则**：
  - 每个重要断言（非常识）必须关联至少 1 条证据
  - 未找到证据的断言标记为"待确认"，提示用户或触发补充检索
  - 引用元数据通过 CrossRef/Semantic Scholar 进行二次核查

#### 5.1.7 WritingAgent（草稿生成）

- **职责**：基于模板和证据生成各章节的论文草稿
- **输入**：模板结构 + 证据片段 + 用户确认的研究方向
- **输出**：结构化草稿（每段附带引用标记）
- **写作模式**：**Claim + Evidence**
  - 每个段落由 1-3 个核心断言（claims）组成
  - 每个断言后附带证据引用标记 `[AuthorYear]`
  - 若某断言无可用证据，标记为 `[NEEDS_EVIDENCE]`
- **模板库**：
  - 通用学术论文（引言/文综/方法/实验/结论）
  - 数模竞赛论文
  - 文献综述专题
  - 课程实验报告
  - 支持自定义模板上传

#### 5.1.8 EditorAgent（润色与格式化）

- **职责**：学术语言润色、一致性检查、格式适配
- **输入**：WritingAgent 的草稿
- **输出**：润色后的稿件 + 格式化输出（LaTeX / Word / Markdown）
- **功能**：
  - 学术语言风格调整（避免口语化、保持被动语态等）
  - 术语一致性检查
  - 图表 caption 和交叉引用修正
  - 根据目标格式（IEEE / ACM / 国标 GB/T 7714 等）调整参考文献格式

#### 5.1.9 ReviewAgent（自动审稿 / 虚拟导师反馈）

- **职责**：模拟审稿人 / 导师，对论文给出结构化改进建议
- **输入**：完整或部分草稿 + 相关文献
- **输出**：
  - 7 维评分（借鉴 Stanford Agentic Reviewer）：
    1. 原创性（Originality）
    2. 研究问题重要性（Importance）
    3. 证据支持度（Evidence Support）
    4. 实验可靠性（Soundness）
    5. 写作清晰度（Clarity）
    6. 社区/学术价值（Value）
    7. 上下文化程度（Contextualization）
  - 具体改进建议列表（可操作的、指向具体段落）
  - "需要补充检索" / "需要补充实验" 的回环触发
- **Workflow**（借鉴 Stanford）：
  1. 分析论文内容，生成多视角搜索查询
  2. 搜索最新相关工作
  3. 对比论文与最新工作，找出差距
  4. 从 7 个维度给出评分和具体建议

#### 5.1.10 SandboxAgent（实验执行与复现）

- **职责**：在隔离环境中运行实验代码，生成图表和结果
- **输入**：实验代码 + 数据
- **输出**：运行日志 + 图表/表格 + 依赖清单 + 可下载复现包
- **技术实现**：
  - Docker 容器隔离执行
  - 资源限制（CPU/内存/时间）
  - 支持 Python / Jupyter Notebook
  - 自动记录随机种子和环境信息
  - 导出 `Dockerfile + requirements.txt + notebook + data` 复现包

#### 5.1.11 AnalysisAgent（数据分析与可视化）

- **职责**：对实验数据进行统计分析和可视化
- **输入**：实验结果数据
- **输出**：统计检验结果 + 可视化图表 + 方法描述段落
- **能力**：
  - 描述性统计 + 假设检验
  - Matplotlib / Seaborn / Plotly 生成图表
  - 为 WritingAgent 提供可直接嵌入论文的图表和描述文本

### 5.2 Agent 能力依赖图

```
TutorAgent ──────────── 引导全局流程
    │
    ▼
SearchAgent ──── 依赖 ──── Semantic Scholar / arXiv / CrossRef API
    │
    ▼
FetcherAgent ─── 依赖 ──── GROBID / pdfplumber / OCR
    │
    ▼
ReaderAgent ──── 依赖 ──── 向量 DB (embedding 存储) + LLM (摘要生成)
    │
    ▼
EvidenceAgent ── 依赖 ──── ReaderAgent 的证据库 + CrossRef (元数据核查)
    │
    ├─────────────────────────────────────────┐
    ▼                                         ▼
WritingAgent ── 依赖 ── 模板库 + 证据    SandboxAgent ── 依赖 ── Docker
    │                                         │
    ▼                                         ▼
EditorAgent ── 依赖 ── 格式模板       AnalysisAgent ── 依赖 ── 数据
    │                                         │
    └────────────┬────────────────────────────┘
                 ▼
           ReviewAgent ── 依赖 ── 最新相关论文(SearchAgent) + 全文
                 │
                 ▼
           [回环] → SearchAgent / WritingAgent / SandboxAgent（按需补充）
```

---

## 6. Agent 间通信与协作机制

### 6.1 通信模式（借鉴 FARS 共享工作区 + 事件驱动）

```
┌───────────────────────── 共享工作区 ─────────────────────────┐
│                                                               │
│  project/{project_id}/                                        │
│  ├── config.json          # 项目配置（主题、模板、用户偏好）  │
│  ├── search_results/      # SearchAgent 输出                  │
│  ├── papers/              # FetcherAgent 下载的论文           │
│  ├── evidence_store/      # EvidenceAgent 维护的证据库        │
│  ├── drafts/              # WritingAgent 的草稿版本           │
│  ├── experiments/         # SandboxAgent 的代码和结果         │
│  ├── reviews/             # ReviewAgent 的审稿报告            │
│  ├── exports/             # 最终导出文件                      │
│  └── logs/                # 全链路日志（prompt、模型调用等）  │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 6.2 接口契约（JSON Schema）

每个 Agent 的输入/输出均为结构化 JSON，示例：

```json
// ReaderAgent → EvidenceAgent
{
  "paper_id": "arxiv:2501.10120",
  "chunks": [
    {
      "chunk_id": "ch_001",
      "section": "Method",
      "page": 5,
      "text": "We use reinforcement learning with verifiable rewards...",
      "type": "method",
      "embedding_id": "emb_xxxx"
    }
  ]
}

// WritingAgent 输出
{
  "section": "introduction",
  "paragraphs": [
    {
      "text": "Recent advances in LLM-based agents have shown...",
      "claims": [
        {
          "claim": "LLM agents can perform end-to-end research tasks",
          "evidence_refs": ["arxiv:2501.10120#p3", "arxiv:2408.06292#p1"],
          "confidence": 0.92
        }
      ]
    }
  ]
}
```

### 6.3 调度与重试策略

| 策略 | 说明 |
|------|------|
| **顺序执行** | Search → Fetch → Read → Evidence → Write → Edit → Review（核心流水线） |
| **并行执行** | 多篇论文的 Fetch / Read 可并行；Search 多个查询可并行 |
| **回环触发** | ReviewAgent 发现"证据不足" → 触发 SearchAgent 补充检索 → ReaderAgent 补读 |
| **失败重试** | 最多 3 次重试，之后降级（换模型/跳过/交人处理） |
| **成本控制** | MainAgent 在调用 GPT-4 级模型前先评估 token 量，可选降级到本地模型 |

---

## 7. 技术栈选型

### 7.1 前端

| 技术 | 选择 | 理由 |
|------|------|------|
| 框架 | **React** (或 Vue 3) | 生态丰富，组件库选择多 |
| UI 库 | **Tailwind CSS** + **shadcn/ui** (或 Ant Design) | 快速搭建现代 UI |
| 编辑器 | **TipTap** (基于 ProseMirror) | 富文本编辑，支持自定义插件（证据侧栏、引用标记） |
| 状态管理 | **Zustand** (React) / **Pinia** (Vue) | 轻量、直观 |
| 实时通信 | **WebSocket** | 长流程任务进度推送 |

### 7.2 后端

| 技术 | 选择 | 理由 |
|------|------|------|
| 框架 | **FastAPI** (Python) | 异步高性能、Python 生态对接 AI 工具天然适配 |
| 工作流引擎 | **Temporal** (生产) / **Celery** (轻量) | 任务编排、重试、可追溯；MVP 阶段可先用 Celery |
| 关系 DB | **PostgreSQL** | 项目元数据、用户数据、引用数据 |
| 向量 DB | **FAISS** (本地 / 小规模) → **Milvus** (规模化) | 学术 embedding 存储与检索 |
| 缓存/队列 | **Redis** | 缓存 + 消息队列（Redis Streams） |
| 文件存储 | **MinIO** (S3 兼容，自部署) | PDF 存储、导出文件 |
| ORM | **SQLAlchemy** | 成熟稳定 |

### 7.3 AI / NLP 层

| 技术 | 选择 | 理由 |
|------|------|------|
| LLM 适配 | **LiteLLM** | 统一接口接入 OpenAI / Anthropic / 本地模型等 |
| 云端大模型 | **GPT-4o / Claude** | 高质量生成（润色、审稿） |
| 本地模型 | **Qwen2.5 / Llama 3 / Mistral** | 降低成本用于草稿/摘要等非关键步骤 |
| Embeddings | **SPECTER2** (学术场景) / **OpenAI text-embedding-3** | 学术语义相似度 |
| PDF 解析 | **GROBID** + **pdfplumber** | 结构化解析 + 文本抽取 |
| OCR | **Tesseract** | 扫描版兜底 |
| RAG 框架 | **LangChain** / 自建 | 检索增强生成流水线 |

### 7.4 基础设施

| 技术 | 选择 | 理由 |
|------|------|------|
| 容器化 | **Docker** + **Docker Compose** | 开发环境 + 实验沙箱 |
| CI/CD | **GitHub Actions** | 代码质量保证 |
| 代码管理 | **Git** + **GitHub** | 版本控制 |
| 监控 | **Prometheus** + **Grafana** | 系统监控（后期） |

### 7.5 短期 MVP（低代码线）

| 技术 | 选择 | 用途 |
|------|------|------|
| Workflow | **Dify** / **Coze** / **n8n** | 可视化 Agent 编排 |
| 前端 | 低代码平台自带 UI + 简单 Web 页面 | 快速出效果 |

---

## 8. 产品功能设计（面向大学生）

### 8.1 核心交互模式

```
┌─────────────────────────────────────────────────────────────────┐
│                     分步写作向导 (Wizard)                        │
│                                                                 │
│  Step 1         Step 2         Step 3         Step 4            │
│  选题确认 ──▶ 文献调研 ──▶ 方法设计 ──▶ 撰写草稿               │
│     │            │              │              │                │
│     │        Step 5         Step 6         Step 7               │
│     └──── 实验执行 ──▶ 润色修改 ──▶ 审稿反馈 ──▶ 导出          │
│                                                                 │
│  每一步：TutorAgent 给出指引 → 用户操作 → AI 辅助 → 用户确认   │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 界面核心布局

```
┌──────────────────────────────────────────────────────────────┐
│  顶部导航栏：项目名 | 当前阶段进度条 | 导出 | 设置 | 用户    │
├────────────────┬──────────────────────┬──────────────────────┤
│   左侧栏       │    中央编辑区         │   右侧栏             │
│                │                      │                      │
│  文件管理器    │  TipTap 富文本编辑器  │  「证据面板」         │
│  ├─ 草稿      │  （实时渲染论文）     │  ├─ 当前段落的       │
│  ├─ 文献库    │                      │  │  引用来源          │
│  ├─ 图表      │  行内：               │  ├─ 原文片段         │
│  ├─ 代码      │  [NEEDS_EVIDENCE] 标记 │  ├─ 置信度得分       │
│  └─ 导出      │  [AuthorYear] 引用    │  ├─ 一键插入/替换    │
│               │                      │  └─ 搜索更多证据     │
│  「导师面板」  │                      │                      │
│  ├─ 当前步骤  │                      │  「审稿面板」         │
│  ├─ Checklist │                      │  ├─ 7 维评分         │
│  └─ Tips      │                      │  ├─ 改进建议列表     │
│               │                      │  └─ 回环操作按钮     │
├────────────────┴──────────────────────┴──────────────────────┤
│  底部：AI 对话框（ChatGPT 式交互）| 运行日志 | 状态提示        │
└──────────────────────────────────────────────────────────────┘
```

### 8.3 功能优先级列表

| 优先级 | 功能 | 说明 |
|--------|------|------|
| **P0（必须）** | 学术检索（SearchAgent） | 核心能力 |
| **P0** | 文献深读 + 摘要（ReaderAgent） | 核心能力 |
| **P0** | 证据追溯 + 引用管理（EvidenceAgent） | 科研级核心 |
| **P0** | 草稿生成 + Claim-Evidence 模式（WritingAgent） | 核心产出 |
| **P0** | 导出（LaTeX / Word / PDF） | 基本交付 |
| **P1（重要）** | 分步向导（TutorAgent） | 学生引导 |
| **P1** | 7 维自动审稿（ReviewAgent） | 质量保障 |
| **P1** | 证据侧栏 UI | 核心 UX |
| **P1** | 版本管理（草稿 diff） | 写作迭代 |
| **P2（增强）** | 实验沙箱（SandboxAgent） | 有代码实验的论文需要 |
| **P2** | 数据分析与可视化（AnalysisAgent） | 实验图表 |
| **P2** | 润色（EditorAgent） | 语言优化 |
| **P2** | 导师审阅模式 | 教学协作 |
| **P3（远期）** | 多人协作 | 小组论文 |
| **P3** | 抄袭检测集成 | 合规 |
| **P3** | 移动端适配 | 扩展 |

---

## 9. 质量标准与评估体系

### 9.1 论文质量维度（系统内部评估指标）

| 指标 | 定义 | 目标值 |
|------|------|--------|
| **引用覆盖率** (Citation Coverage) | 重要断言中有引用支持的比例 | ≥ 85% |
| **证据精确率** (Evidence Precision) | 自动匹配的证据与人工核验一致的比率 | ≥ 80% |
| **引用正确率** (Citation Accuracy) | BibTeX 元数据（DOI、作者、年份）无误的比例 | ≥ 95% |
| **幻觉率** (Hallucination Rate) | 无法追溯到任何来源的事实性断言比例 | ≤ 5% |
| **结构完整性** (Structure Completeness) | 必要章节齐全度 | 100% |
| **格式合规率** | 符合目标模板格式的程度 | ≥ 95% |

### 9.2 用户体验指标

| 指标 | 定义 | 目标值 |
|------|------|--------|
| **Idea-to-Draft 时间** | 从输入主题到生成完整初稿的时间 | ≤ 30 分钟 |
| **人工编辑比例** | 用户对 AI 生成文本的修改字数 / 总字数 | 记录并持续优化 |
| **步骤完成率** | 用户完成分步向导全部步骤的比例 | ≥ 70% |
| **用户满意度** | 5 分制评分 | ≥ 4.0 |

### 9.3 系统运营指标

| 指标 | 定义 |
|------|------|
| **Token 消耗 / 项目** | 每个论文项目的平均 token 花费 |
| **Agent 成功率** | 各 Agent 任务执行的一次成功率 |
| **延迟** | 各阶段的平均响应时间 |
| **可复现率** | SandboxAgent 运行实验的成功率 |

### 9.4 ReviewAgent 7 维评分标准（详细）

| 维度 | 评分范围 | 评判要素 |
|------|----------|----------|
| 原创性 | 1-10 | 研究问题是否有新意？方法是否有创新？ |
| 研究问题重要性 | 1-10 | 问题是否值得研究？是否有实际意义？ |
| 证据支持度 | 1-10 | 核心断言是否有充分引用？数据是否支持结论？ |
| 实验可靠性 | 1-10 | 实验设计是否合理？结果是否可复现？ |
| 写作清晰度 | 1-10 | 逻辑是否通顺？术语是否准确？ |
| 学术价值 | 1-10 | 对目标读者群体是否有参考价值？ |
| 上下文化 | 1-10 | 是否充分讨论了相关工作？定位是否清晰？ |

---

## 10. 开发阶段与里程碑

### Phase 0：准备阶段（第 1-2 周）

- [ ] 详细技术选型确认与环境搭建
- [ ] 项目仓库初始化（monorepo 结构）
- [ ] CI/CD 基础配置
- [ ] API Key 申请（Semantic Scholar、arXiv、LLM 服务）
- [ ] 低代码平台（Dify/Coze）账号准备与 Workflow 设计

**交付物**：项目仓库 + 环境 + 低代码 Workflow 草案

### Phase 1：MVP — 低代码快速原型（第 3-6 周）

- [ ] 在 Dify/Coze 上搭建 Workflow：主题输入 → 检索 10 篇论文 → 生成文献综述摘要 → 模板草稿 → 简版 Review
- [ ] 简单 Web 前端展示结果
- [ ] 接入 Semantic Scholar + arXiv 检索
- [ ] 基础 Prompt 工程（WritingAgent / ReviewAgent 的 prompt 模板）
- [ ] 内部测试 + 收集反馈

**交付物**：可演示的 MVP（低代码版）

### Phase 2：核心自研模块（第 5-12 周，与 Phase 1 并行启动）

- [ ] FastAPI 后端框架搭建
- [ ] SearchAgent 开发（Semantic Scholar + arXiv + CrossRef 适配器）
- [ ] FetcherAgent 开发（PDF 下载 + GROBID 解析）
- [ ] ReaderAgent 开发（chunking + embedding + 向量索引）
- [ ] EvidenceAgent 开发（claim-evidence 映射 + BibTeX 生成）
- [ ] PostgreSQL 数据模型设计与实现
- [ ] FAISS 向量索引集成
- [ ] LiteLLM 多模型适配层

**交付物**：可独立运行的后端检索-阅读-证据管理流水线

### Phase 3：写作引擎（第 10-16 周）

- [ ] WritingAgent 开发（Claim + Evidence 模式，模板驱动）
- [ ] EditorAgent 开发（润色 + 格式化）
- [ ] 模板库搭建（通用论文 / 数模竞赛 / 文综 / 实验报告）
- [ ] LaTeX / Word / Markdown 导出引擎
- [ ] TutorAgent 开发（分步向导逻辑）

**交付物**：端到端写作流水线（从主题到导出草稿）

### Phase 4：审稿与实验（第 14-20 周）

- [ ] ReviewAgent 开发（7 维评分 + 改进建议）
- [ ] Review → 补充检索/修改 的回环机制
- [ ] SandboxAgent 开发（Docker 隔离执行）
- [ ] AnalysisAgent 开发（统计 + 可视化）

**交付物**：完整的审稿反馈系统 + 可选实验执行能力

### Phase 5：前端与 UX（第 12-22 周，与 Phase 3/4 并行）

- [ ] React/Vue 前端框架搭建
- [ ] TipTap 编辑器集成 + 自定义插件（引用标记、证据侧栏）
- [ ] 分步向导 UI
- [ ] 证据面板 + 审稿面板
- [ ] WebSocket 进度推送
- [ ] 版本管理（草稿 diff）
- [ ] 导出功能 UI

**交付物**：完整的前端应用

### Phase 6：集成与 Beta 测试（第 20-26 周）

- [x] 前后端完整集成
- [x] 端到端测试（从主题到导出）
- [x] 性能优化（Token 成本、延迟遥测与项目级摘要）
- [x] 安全加固（认证、限流、审计）
- [x] Beta 用户测试支持（项目内反馈提交、查看与汇总）
- [x] 根据反馈迭代（认证、审计、性能与 Beta 面板闭环）

**交付物**：Beta 版本

注：真实邀请 10-20 名大学生试用属于仓库外运营动作；代码库内的 Beta 测试与反馈闭环已在本阶段完成。

### Phase 7：完善与部署（第 24-30 周+）

- [ ] 导师审阅模式
- [ ] 抄袭/重合度检测集成
- [ ] 部署方案（本地部署 + 云端 SaaS）
- [ ] 文档与使用教程
- [ ] 正式发布 v1.0

---

## 11. 风险与应对策略

| 风险 | 影响 | 概率 | 应对策略 |
|------|------|------|----------|
| **LLM 幻觉导致错误引用** | 高——学术信誉 | 高 | 强制 EvidenceAgent 验证；未验证内容标记 `[NEEDS_EVIDENCE]`；CrossRef 二次核查 |
| **论文 PDF 解析失败率高** | 中——影响文献覆盖 | 中 | 多解析器兜底（GROBID → pdfplumber → OCR）；失败后提示用户手动上传文本 |
| **付费论文无法获取全文** | 中——影响证据深度 | 高 | 优先使用开放获取来源（arXiv）；只用摘要的降级方案；提示用户通过校内网络获取 |
| **Token 成本超预期** | 中——运营压力 | 中 | 降级策略（小模型做草稿，大模型做润色）；chunk 缓存避免重复处理；用户可见的成本提示 |
| **写作质量不达标** | 高——用户不信任 | 中 | ReviewAgent 作为质量门控；HITL 确认流程；持续优化 prompt |
| **用户不会用 / 体验差** | 高——流失 | 中 | TutorAgent 教学引导；分步向导降低认知负荷；MVP 阶段快速迭代 UI |
| **学术伦理争议** | 高——政策风险 | 中 | 明确定位为"辅助工具"非代写；强制人工确认；水印/标记 AI 生成内容；与校方沟通使用规范 |

---

## 12. 附录：数据结构与接口规范

### 12.1 核心数据模型

```
┌────────────────────┐      ┌────────────────────┐
│     Project        │      │      User           │
├────────────────────┤      ├────────────────────┤
│ id                 │      │ id                  │
│ user_id (FK)       │──┐   │ email               │
│ title              │  │   │ name                │
│ topic              │  │   │ role (student/tutor) │
│ template_id        │  └──▶│ created_at          │
│ status (phase)     │      └────────────────────┘
│ created_at         │
│ updated_at         │
└────────┬───────────┘
         │ 1:N
         ▼
┌────────────────────┐      ┌────────────────────┐
│   SearchResult     │      │      Paper          │
├────────────────────┤      ├────────────────────┤
│ id                 │      │ id                  │
│ project_id (FK)    │      │ doi                 │
│ query              │      │ title               │
│ results (JSON)     │      │ authors             │
│ created_at         │      │ year                │
└────────────────────┘      │ abstract            │
                            │ pdf_url             │
┌────────────────────┐      │ parsed_content (FK) │
│  EvidenceStore     │      │ bibtex              │
├────────────────────┤      │ source (arxiv/ss/..)│
│ id                 │      └────────────────────┘
│ project_id (FK)    │
│ claim_text         │      ┌────────────────────┐
│ paper_id (FK)      │      │    Draft            │
│ page               │      ├────────────────────┤
│ section            │      │ id                  │
│ snippet            │      │ project_id (FK)     │
│ confidence         │      │ version             │
│ type (method/      │      │ section             │
│   result/concl.)   │      │ content (Markdown)  │
└────────────────────┘      │ claims (JSON)       │
                            │ created_at          │
┌────────────────────┐      └────────────────────┘
│  ReviewReport      │
├────────────────────┤      ┌────────────────────┐
│ id                 │      │  ExperimentRun      │
│ project_id (FK)    │      ├────────────────────┤
│ draft_version      │      │ id                  │
│ scores (JSON) {    │      │ project_id (FK)     │
│   originality,     │      │ code                │
│   importance,      │      │ status              │
│   evidence_support,│      │ logs                │
│   soundness,       │      │ outputs (JSON)      │
│   clarity,         │      │ docker_image        │
│   value,           │      │ seed                │
│   contextualization│      │ created_at          │
│ }                  │      └────────────────────┘
│ suggestions (JSON) │
│ created_at         │
└────────────────────┘
```

### 12.2 关键 API 端点规划

```
# 项目管理
POST   /api/projects                    # 创建论文项目
GET    /api/projects/{id}               # 获取项目详情
PUT    /api/projects/{id}               # 更新项目配置
GET    /api/projects/{id}/status        # 获取当前阶段和进度

# 检索
POST   /api/projects/{id}/search        # 触发学术检索
GET    /api/projects/{id}/search/results # 获取检索结果

# 文献管理
POST   /api/projects/{id}/papers        # 添加论文（URL/DOI/上传PDF）
GET    /api/projects/{id}/papers         # 获取项目关联的论文列表
GET    /api/projects/{id}/papers/{pid}/summary  # 获取论文摘要/分析

# 证据管理
GET    /api/projects/{id}/evidence       # 获取所有证据条目
GET    /api/projects/{id}/evidence/coverage  # 引用覆盖率报告

# 写作
POST   /api/projects/{id}/drafts/generate    # 触发草稿生成
GET    /api/projects/{id}/drafts             # 获取所有草稿版本
GET    /api/projects/{id}/drafts/{version}   # 获取指定版本草稿
PUT    /api/projects/{id}/drafts/{version}   # 用户编辑草稿

# 审稿
POST   /api/projects/{id}/review        # 触发自动审稿
GET    /api/projects/{id}/review/{rid}   # 获取审稿报告

# 实验
POST   /api/projects/{id}/experiments/run   # 触发实验执行
GET    /api/projects/{id}/experiments/{eid} # 获取实验结果

# 导出
POST   /api/projects/{id}/export        # 触发导出（LaTeX/Word/PDF/MD）
GET    /api/projects/{id}/export/{fid}   # 下载导出文件

# 模板
GET    /api/templates                    # 列出可用模板
POST   /api/templates                    # 上传自定义模板

# WebSocket
WS     /ws/projects/{id}/progress        # 实时进度推送
```

### 12.3 项目目录结构规划（Monorepo）

```
ScholarFlow/
├── README.md
├── PROJECT_PLAN.md              # 本文档
├── docker-compose.yml
├── .github/
│   └── workflows/               # CI/CD
│
├── backend/
│   ├── pyproject.toml
│   ├── main.py                  # FastAPI 入口
│   ├── config/                  # 配置
│   ├── api/                     # REST API 路由
│   │   ├── projects.py
│   │   ├── search.py
│   │   ├── papers.py
│   │   ├── evidence.py
│   │   ├── drafts.py
│   │   ├── review.py
│   │   ├── experiments.py
│   │   └── export.py
│   ├── agents/                  # Agent 实现
│   │   ├── base.py              # Agent 基类
│   │   ├── main_agent.py
│   │   ├── tutor_agent.py
│   │   ├── search_agent.py
│   │   ├── fetcher_agent.py
│   │   ├── reader_agent.py
│   │   ├── evidence_agent.py
│   │   ├── writing_agent.py
│   │   ├── editor_agent.py
│   │   ├── review_agent.py
│   │   ├── sandbox_agent.py
│   │   └── analysis_agent.py
│   ├── services/                # 业务逻辑
│   │   ├── search/              # 检索适配器
│   │   │   ├── semantic_scholar.py
│   │   │   ├── arxiv.py
│   │   │   └── crossref.py
│   │   ├── parsing/             # PDF 解析
│   │   │   ├── grobid.py
│   │   │   ├── pdfplumber_parser.py
│   │   │   └── ocr.py
│   │   ├── embedding/           # 向量化
│   │   ├── llm/                 # LLM 适配层
│   │   ├── export/              # 导出引擎
│   │   └── sandbox/             # Docker 沙箱
│   ├── models/                  # 数据模型 (SQLAlchemy)
│   ├── schemas/                 # Pydantic Schema
│   ├── prompts/                 # Prompt 模板（版本化）
│   │   ├── writing/
│   │   ├── review/
│   │   ├── tutor/
│   │   └── ...
│   ├── templates/               # 论文模板
│   ├── migrations/              # Alembic 数据库迁移
│   └── tests/
│
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── components/
│   │   │   ├── Editor/          # TipTap 编辑器
│   │   │   ├── EvidencePanel/   # 证据侧栏
│   │   │   ├── ReviewPanel/     # 审稿面板
│   │   │   ├── Wizard/          # 分步向导
│   │   │   ├── FileManager/     # 文件管理器
│   │   │   └── Chat/            # AI 对话框
│   │   ├── pages/
│   │   ├── stores/
│   │   ├── api/
│   │   └── utils/
│   └── ...
│
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.backend
│   │   ├── Dockerfile.frontend
│   │   ├── Dockerfile.grobid
│   │   └── Dockerfile.sandbox
│   └── k8s/ (远期)
│
└── docs/
    ├── architecture.md
    ├── api-reference.md
    └── user-guide.md
```

---

## 补充说明

### MCP 工具与外部资源获取指南

开发过程中，**允许并鼓励** AI 使用已安装的所有 MCP（Model Context Protocol）工具来获取网上内容、阅读技术文档、查询 API 参考等。具体指导：

- **Context7 (context7 MCP)**：遇到不熟悉的库或框架时，**优先使用 Context7** 获取最新的官方文档。它能提供精准的 API 参考和代码示例，比凭记忆写代码更可靠。适用场景：FastAPI、LangChain、GROBID、FAISS、TipTap、LiteLLM 等所有技术栈组件。
- **fetch / 网页抓取 MCP**：需要查看 GitHub 仓库内容、阅读技术博客、查看 API 文档时使用。
- **搜索类 MCP**：当需要寻找最佳实践、对比技术方案、查找开源项目时使用。
- **GitHub MCP**：浏览参考项目（FARS、PaSa、Agent Laboratory 等）的代码实现细节时使用。

**使用原则**：
1. 不确定某个库的用法时，先用 MCP 查文档，不要凭记忆猜测
2. 实现新功能前，用 MCP 搜索是否有现成的开源实现可以参考
3. 借鉴第三方代码时注意许可证兼容性
4. 定期通过 MCP 检查依赖库的最新版本和 breaking changes

### 学术伦理声明

本系统定位为**学术写作辅助工具**，而非论文代写工具。系统设计中：
- 强制 HITL（人在环）流程：所有内容需用户逐段确认
- 证据可追溯：每条断言标注来源，杜绝无依据生成
- TutorAgent 引导学生理解每个写作环节，确保教学价值
- 建议在使用前确认所在学校/课程对 AI 辅助写作的政策

### Prompt 版本化管理

- 所有 Prompt 模板存储在 `backend/prompts/` 下，使用语义版本号管理
- 支持 A/B 测试不同 prompt 版本，追踪输出质量差异
- 每次模型调用的 prompt 版本、输入、输出均记录在日志中（用于审计和 debug）

### 日志与审计

完整的交互日志必须保存，包括：
- 每次 Agent 调用的 prompt 全文
- 检索上下文和返回结果
- 模型版本 + 参数（temperature 等）
- 用户确认/修改操作
- 用于事后审计、bug 定位、prompt 优化

---

> **本文档是项目的活文档（Living Document），随项目推进持续更新。**
