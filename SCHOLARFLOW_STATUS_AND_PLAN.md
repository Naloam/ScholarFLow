# ScholarFlow Status And Rebuild Plan

更新时间：2026-06-12

本文是 ScholarFlow 当前状态、问题诊断和后续重构计划的完整交接文档。它的目标不是宣传项目，而是让后续开发者可以准确理解：项目现在有什么、为什么偏离了原始目标、哪些资产应该保留、哪些方向应该停止，以及怎样把系统重构成真正接近 ARIS/FARS 的自主科研产品。

## 1. 最终目标

ScholarFlow 的最终目标应当重新收敛为：

用户提出一个 research idea 后，系统能让 agent 像研究员一样完成完整科研闭环：

1. 理解用户 idea，形成研究问题和初始 brief。
2. 主动阅读论文、检索相关工作、识别 gap。
3. 生成多个候选 hypothesis / method idea，而不是只顺着一个方向写作。
4. 选择最有实验可行性和潜在贡献的方向。
5. 自动设计实验协议，包括数据集、baseline、metric、ablation、统计检验和失败判据。
6. 自动写实验代码，创建可运行的代码工作区。
7. 真正运行实验，保存日志、结果表、错误、环境信息和 artifacts。
8. 在失败时自动 debug、repair、retry、fork 或缩小问题。
9. 由另一个 reviewer agent 从审稿人角度攻击方法、实验和论证。
10. 根据审稿意见追加实验、修正方法或降级结论。
11. 在证据足够时写论文草稿；证据不足时输出 negative result 或 research memo。
12. 最终产出一个可争辩的研究贡献，而不是一个流程完整但没有科研价值的文件。

这个目标比“自动写论文”更严格。论文只是最后的表达形式，核心价值必须来自真实的实验、真实的对比、真实的失败和真实的证据。

## 2. 当前仓库状态

### 2.1 Git 状态

当前分支是 `master`，本地领先远端提交。最近一次已提交的变更是：

- `9161578 Harden autoresearch provenance gates`

该提交包含上一轮真实 API 测试中形成的修复：

- 修复 arXiv API 地址为 HTTPS。
- 修复 Semantic Scholar connector 字段请求，不再请求不支持的顶层 `doi`，改从 `externalIds.DOI` 解析。
- 让 connector 在部分 query 失败但已经拿到 papers 时仍标记 source available，同时保留错误作为审计信息。
- 优化 literature scout query 顺序，使短 domain query 优先，同时保留旧缓存查询兼容性。
- 增加 `benchmark_source_metadata.py`，为 file-backed frozen/imported benchmark 在缺少 run spec 时 materialize source metadata。
- 让 benchmark card 和 project paper orchestrator 使用 materialized benchmark source fallback。
- ingestion 保留更多 benchmark/source metadata。
- project paper selected runs 选择逻辑排除旧 smoke/fixture run，优先选择 final-candidate benchmark eligible runs。
- 增加相关回归测试。

当前已清理掉运行时生成的测试论文产物：

- `backend/backend/data/projects/**/autorresearch/project_paper`
- `backend/data/projects/**/autorresearch/project_paper`
- run/candidate 层的 `paper.md`
- `paper_sources/`
- `paper_revised.md`
- `main.tex`
- `references.bib`
- `submission_archive.zip`
- `final_publish_decision.json`
- `publication_manifest.json`
- `reviewer_response.md`
- `code_package.zip`

这些产物均为未被 git 跟踪的运行时输出。源码、测试和 schema 没有因为这次清理被删除。

### 2.2 已验证测试

上一轮变更完成后已经运行过：

- focused autoresearch regression：`18 passed, 146 deselected`
- full backend suite：`292 passed, 1 warning in 1256.08s`

这说明当前已提交代码在 deterministic regression 层面是稳定的。但这些测试只能证明现有 baseline 没坏，不能证明产品已经具备真正 ARIS/FARS 级科研能力。

### 2.3 当前配置能力

仓库支持：

- FastAPI backend。
- Vite / React frontend。
- litellm-compatible LLM 配置。
- `.env` 中可配置 `LLM_MODEL`、`LLM_WRITER_MODEL`、`LLM_API_BASE`、LLM key、Semantic Scholar key 等。
- Semantic Scholar key 在最近一次测试中已经可用。
- arXiv、Semantic Scholar、Crossref、offline project context 等 literature source。
- filesystem-backed project data。
- deterministic tests 不应依赖 live network、paid LLM、GPU 或外部 benchmark availability。

常用命令：

```bash
cd backend && PYTHONPATH=. ../.venv/bin/uvicorn main:app --reload
cd backend && ../.venv/bin/pytest -q
cd frontend && npm run dev
cd frontend && npm run build
cd frontend && npm run e2e
```

## 3. 当前系统架构

### 3.1 后端主结构

后端主要入口：

- `backend/main.py`
- `backend/api/autoresearch.py`
- `backend/api/autoresearch_deployments.py`
- `backend/schemas/autoresearch.py`
- `backend/services/autoresearch/`

`backend/services/autoresearch/` 当前包含大量科研流程模块，包括：

- `idea_brief.py`：idea 到 research brief。
- `literature_scout.py`、`literature_connectors.py`、`literature_pipeline.py`、`literature_synthesizer.py`：文献检索和综合。
- `planner.py`、`project_flow.py`、`orchestrator.py`：流程规划和编排。
- `research_protocol.py`、`experiment_design.py`、`experiment_factory.py`：实验协议和实验工厂。
- `codegen.py`、`runner.py`、`experiment_execution.py`、`execution.py`：代码生成、运行、队列、resume/retry/cancel。
- `repository.py`：filesystem persistence。
- `claim_evidence_gate.py`、`citation_verifier.py`、`paper_evidence_compiler.py`：claim/evidence/citation 检查。
- `reviewer_simulator.py`、`review_publish.py`、`project_paper_orchestrator.py`：审稿、发布和项目级论文包。
- `artifact_integrity_audit.py`、`benchmark_card.py`、`benchmark_source_metadata.py`、`publication_evidence_index.py`：artifact、benchmark provenance 和 publish evidence。
- `release_governance.py`、`operator_control.py`、`console.py`、`deployment.py`：发布治理、Operator Console 和 deployment surface。
- `memory.py`：多项目记忆，但根据约束只能作为 discovery hint，不能当作当前项目 claim evidence。

这些模块形成了一个很完整的“科研流程管理/审计平台”，但没有形成足够强的“研究执行内核”。

### 3.2 前端主结构

前端主要入口：

- `frontend/src/App.tsx`
- `frontend/src/pages/WorkspacePage.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`

主要组件：

- `ProjectLauncher`
- `WizardPanel`
- `EditorSurface`
- `FileManager`
- `ReviewPanel`
- `OperatorConsolePanel`
- `EvidencePanel`
- `DeploymentPanel`
- `StatusBar`

当前 UI 更像一个科研工作流/论文工作台，而不是 agent research cockpit。它有较多面板，但还没有把“agent 正在读什么、写什么代码、跑什么实验、为什么失败、下一步谁在决策”清晰呈现出来。

### 3.3 持久化布局

当前主要使用 filesystem-backed persistence：

```text
backend/data/projects/<project_id>/autorresearch/
backend/backend/data/projects/<project_id>/autorresearch/
```

历史上出现两个 data root，这是需要整理的问题。当前代码和测试中可能因运行路径不同产生不同根目录，后续应统一为单一 `DATA_DIR` 策略。

典型 run-level 文件包括：

- `run.json`
- `program.json`
- `plan.json`
- `spec.json`
- `portfolio.json`
- `artifact.json`
- attempts / manifests / metrics / reviews 等。

这套 persistence 是有价值的，因为 FARS/ARIS 类系统必须有持久 workspace、run identity、artifact lineage 和可恢复状态。但当前文件布局偏复杂，需要从“论文包导向”重构为“research workspace 导向”。

## 4. 当前实际运行流程

按照现有 baseline，AutoResearch 的理想流程是：

1. 用户创建 project。
2. 输入 idea。
3. 系统生成 research brief。
4. literature scout 搜索 arXiv / Semantic Scholar / Crossref / cache / offline context。
5. gap validation 给出可研究方向。
6. hypothesis bank 生成多个候选方向。
7. planner 选择方向。
8. experiment protocol 定义 dataset、metric、baseline、repair policy。
9. runner 或 experiment factory 执行实验。
10. artifact、metrics、attempt ledger、repair notes 写入 repository。
11. claim evidence ledger 约束结论。
12. reviewer simulator 检查论文或 project conclusion。
13. revision loop 执行 bounded claim downgrade / repair action。
14. project paper orchestrator 汇总 selected runs。
15. publish gate 判断 review bundle / final publish readiness。
16. deployment / release governance 暴露 archive、manifest、human approval、compliance checklist、venue adapter。

这条流程形式完整，且证据约束较强。但上一轮真实测试暴露出关键问题：系统能跑完流程，却不能保证产生强研究贡献。

## 5. 上一轮真实测试结论

上一轮测试主题是：

`Citation-Faithful RAG Answer Verification with Evidence-Aware Retrieval and Abstention Calibration`

实际执行后得到的事实：

- project 创建成功。
- literature source 可用，Semantic Scholar key 也可用。
- 系统成功创建 brief、hypothesis、protocol、runs、evidence ledger、review bundle。
- 新增了 BEIR NFCorpus frozen snapshot 作为独立 benchmark provenance。
- 最终 selected runs 为三个 publication-candidate benchmark run。
- old smoke/fixture run 已排除。
- project paper package 能生成 review-ready/workshop-candidate 输出。
- final publish gate 正确未通过。

未通过原因包括：

- 存在 negative / ambiguous evidence。
- `ledger_aware_ranker` 没有稳定超过 BM25。
- NFCorpus 上 59/60 query 未超过 BM25。
- SciFact retrieval view 上 48/48 query 未超过 BM25。
- statistical significance 不成立。
- 有 cached claim-evidence retrieval，不适合作为最终核心发表证据。
- evidence origin 包含 `deterministic_replay` 和 `local_smoke`，不满足 final evidence policy。
- meta-analysis 没有 stable project-level conclusion。

这次测试的真实结论是：系统的 gate 很诚实，但科研内核弱。它擅长说“不能发表”，不擅长把 idea 推进成“值得发表”。

## 6. 当前项目的核心问题

### 6.1 过早产品化

项目花了大量代码在：

- API surface
- schema
- publish package
- release governance
- operator console
- archive manifest
- compliance checklist
- project-level paper orchestration

这些东西不是错的，但它们应当建立在强 research harness 之后。现在的问题是底层研究能力还弱，上层治理和包装已经很复杂，造成“系统很庞大，但产出没有科研竞争力”。

### 6.2 研究执行内核不够强

真正的 ARIS/FARS 内核应该优先解决：

- agent 能否独立读论文并提炼 gap？
- agent 能否提出多个可执行 idea？
- agent 能否写出可运行实验代码？
- agent 能否 debug 自己的代码？
- agent 能否对照强 baseline / SOTA？
- agent 能否基于审稿意见补实验？
- agent 能否承认失败并改题？

当前 ScholarFlow 在这些方面有雏形，但被流程管理、paper package 和 gate 逻辑稀释了。

### 6.3 写作层把 ledger 拼成论文

当前 `writer.py` 和 `project_paper_orchestrator.py` 很容易把 artifacts、claim traces、limitations 拼成一篇“系统报告”。这类输出虽然证据可追溯，但不像高水平论文：

- 缺少清晰 contribution framing。
- 缺少 reviewer-facing argument。
- 缺少真正的方法动机。
- Related Work 容易 query drift。
- Results 像日志摘要。
- Limitations 很完整，但主线贡献很弱。

后续写作层必须从“拼接证据”转为“基于证据构造论文论证”。证据 ledger 是约束，不是论文正文模板。

### 6.4 实验选择太保守

当前系统倾向选择 repo-local frozen benchmark、toy/frozen snapshot、deterministic replay。这对测试很友好，但对真实科研不够。

需要引入两类运行：

- deterministic regression run：用于 CI 和系统稳定性。
- real research run：允许下载真实数据、运行真实 baseline、保存真实失败，不进入普通 deterministic tests。

二者必须分离。否则系统会为了测试稳定而牺牲科研真实性。

### 6.5 当前 Operator Console 不是研究驾驶舱

用户真正需要看到：

- agent 当前在哪个阶段？
- 它正在读哪些论文？
- 它提出了哪些 hypothesis？
- 它为什么选择这个 experiment？
- 它写了哪些代码？
- 实验日志是什么？
- 哪个错误导致 repair？
- reviewer agent 拒稿理由是什么？
- 下一步需要人类批准还是自动执行？

当前 UI 组件很多，但没有围绕这个 research cockpit 组织。

### 6.6 Data root 和产物管理混乱

当前同时存在：

- `backend/data/projects`
- `backend/backend/data/projects`

后续必须统一。否则同一个项目在不同 cwd 下可能产生不同运行产物，影响 reproducibility 和 operator inspection。

### 6.7 roadmap 已完成但方向需要重置

`docs/goal.md` 显示 Goal 1-13 已完成，且没有 active roadmap goal。这是 deterministic baseline 完成，不代表最终产品完成。

下一阶段不应继续沿旧 roadmap 堆 Goal 14、Goal 15。应该重置为 Research Harness roadmap。

## 7. 应保留的资产

虽然方向偏了，但仓库不是废掉。以下资产应该保留并改造：

### 7.1 Literature connector

保留：

- arXiv
- Semantic Scholar
- Crossref
- cache freshness policy
- source class tracking
- stale cache 不可作为 final publish evidence 的规则

改造：

- 从“给 brief 找几篇参考”升级为 `LiteratureAgent` 的工具。
- 支持 iterative search：query expansion、snowballing、citation graph、paper clustering。
- 输出 structured literature notes，而不只是 paper list。

### 7.2 Execution plane

保留：

- queue
- worker state
- resume
- retry
- cancel
- stale lease recovery

改造：

- 从 AutoResearch run queue 改造成 research task queue。
- task 粒度包括：literature_search、idea_generation、code_write、experiment_run、review、paper_write。
- 每个 task 必须有 input files、output files、logs、status 和 owner agent。

### 7.3 Repository / artifact lineage

保留：

- run identity
- artifact hashes
- manifests
- lineage edges
- attempt ledger

改造：

- 面向 workspace files，而不是 project paper package。
- 每个 artifact 都应该能回答：谁生成、基于什么输入、运行了什么命令、输出在哪里、是否被 reviewer 质疑。

### 7.4 Evidence gate

保留：

- claim-evidence ledger
- negative evidence retention
- publish gate 不允许弱化
- memory discovery-only 规则

改造：

- 作为最终 auditor layer，而不是主流程的中心。
- 在 paper writing 前检查 claim。
- 在 reviewer loop 后更新 claim ceiling。

### 7.5 Reviewer simulator

保留：

- reviewer findings
- revision action mapping
- bounded repair
- rereview

改造：

- 让 reviewer 主要攻击科研贡献，而不只是检查 missing retrieval evidence。
- Reviewer 输出必须能转成新实验任务，例如：
  - add stronger baseline
  - run ablation
  - test on second dataset
  - report failure mode
  - rewrite related work

## 8. 应停止或降级的方向

### 8.1 停止继续堆 publish/release 治理

Release governance 已经足够复杂。当前最缺的不是 release archive，而是强研究。

在 Research Harness MVP 完成前，不应继续新增：

- venue-specific release adapter
- compliance UI
- publish archive 变体
- package metadata 扩展

### 8.2 降级 project paper orchestrator

`project_paper_orchestrator.py` 当前很重。后续应该降级为兼容层，只负责读取新 workspace 的研究产物并生成 package。

新写作主线应该是：

```text
workspace evidence -> contribution brief -> paper outline -> paper draft -> reviewer rebuttal -> revision
```

而不是：

```text
run ledger -> project paper package -> publish bundle
```

### 8.3 停止把流程完整当作成功

未来任一 run 的成功标准必须是：

- 有真实代码。
- 有真实实验日志。
- 有 baseline。
- 有 comparison。
- 有 reviewer objections。
- 有 claim ceiling。

如果没有科研贡献，应输出 negative result，不生成“看起来完整”的 paper。

## 9. 新目标架构

建议重构为三层。

### 9.1 Research Harness Core

新核心建议路径：

```text
backend/services/research_harness/
  agents/
  workflows/
  tools/
  workspace.py
  task_queue.py
  state.py
  evaluator.py
```

它负责真正做科研。

核心对象：

- `ResearchProject`
- `ResearchWorkspace`
- `ResearchTask`
- `AgentStep`
- `LiteratureNote`
- `HypothesisCandidate`
- `ExperimentPlan`
- `CodeArtifact`
- `ExperimentRun`
- `ReviewFinding`
- `ContributionClaim`
- `PaperDraft`

### 9.2 Auditor Layer

可继续放在 `backend/services/autoresearch/` 或拆到：

```text
backend/services/research_auditor/
```

职责：

- evidence ledger
- artifact lineage
- claim audit
- benchmark provenance
- final gate
- release governance

这层不负责想 idea，不负责写代码，只负责约束和审计。

### 9.3 Thin Backend API + Research Cockpit Frontend

Backend 只暴露：

- 创建项目。
- 启动/暂停/恢复 research loop。
- 查看 agent timeline。
- 查看 workspace 文件。
- 查看实验日志和 artifacts。
- 查看 reviewer findings。
- 人工批准高成本动作。
- 导出 final package。

Frontend 改成 research cockpit：

```text
左侧：Project / Run / Agent Timeline
中间：Workspace 文件、代码、实验日志、论文草稿
右侧：Evidence、Reviewer Objections、Next Actions、Human Approval
底部：Queue / Worker / Cost / Errors
```

## 10. 新标准工作流

新的主流程应该是：

```text
User idea
-> Project bootstrap
-> Literature sweep
-> Gap map
-> Idea portfolio
-> Feasibility scoring
-> Experiment plan
-> Code workspace generation
-> Smoke execution
-> Candidate elimination
-> Full experiment execution
-> Repair/debug loop
-> Baseline/SOTA comparison
-> Reviewer simulation
-> Follow-up experiment planning
-> Claim audit
-> Paper drafting
-> Reviewer rebuttal/revision
-> Final publish gate or negative result
```

每一步都必须写入 workspace 文件，而不是只存在 API response 中。

建议 workspace 布局：

```text
research_workspace/<project_id>/
  project.yaml
  idea.md
  brief.md
  timeline.jsonl
  literature/
    search_queries.json
    papers.jsonl
    notes/
    gap_map.md
  ideas/
    candidates.json
    selected.md
  experiments/
    plan.md
    specs/
    runs/
  code/
    README.md
    requirements.txt
    experiment.py
    run.sh
    src/
  artifacts/
    metrics.json
    tables/
    figures/
    logs/
  reviews/
    reviewer_round_1.md
    action_plan_1.json
    reviewer_round_2.md
  ledger/
    artifact_lineage.jsonl
    evidence_ledger.json
    claim_audit.json
  paper/
    contribution.md
    outline.md
    draft.md
    revised.md
    references.bib
```

这个布局可以直接被 agent、后端 API、前端、人类开发者共同读写。

## 11. Agent 设计

### 11.1 Research Manager

职责：

- 管理整个 research loop。
- 决定下一步 task。
- 在失败时选择 retry、repair、fork、abandon。
- 控制成本和时间预算。
- 维护 project timeline。

### 11.2 Literature Agent

职责：

- 将 idea 拆成检索 query。
- 使用 arXiv / Semantic Scholar / Crossref / web/cached sources。
- 生成 paper notes。
- 做 related work clustering。
- 输出 gap map。

最低输出：

- `literature/papers.jsonl`
- `literature/notes/*.md`
- `literature/gap_map.md`
- `literature/known_baselines.md`

### 11.3 Idea Agent

职责：

- 基于 gap map 生成多个 hypothesis。
- 为每个 hypothesis 标注 novelty、feasibility、data availability、expected risk。
- 避免只生成一个顺滑但不可实验的 idea。

最低输出：

- `ideas/candidates.json`
- `ideas/selected.md`

### 11.4 Experiment Engineer

职责：

- 把 selected hypothesis 变成 experiment plan。
- 写代码。
- 写 `requirements.txt` / `run.sh`。
- 执行 smoke test。
- 修代码错误。
- 跑 baseline、proposed、ablation。

最低输出：

- `experiments/plan.md`
- `code/experiment.py`
- `artifacts/logs/*.log`
- `artifacts/metrics.json`
- `artifacts/tables/results.csv`

### 11.5 Reviewer Agent

职责：

- 像审稿人一样评估贡献。
- 明确拒稿理由。
- 要求更强 baseline、更多 dataset、ablation、error analysis。
- 不允许只给泛泛建议。

最低输出：

- `reviews/reviewer_round_1.md`
- `reviews/action_plan_1.json`

### 11.6 Writer Agent

职责：

- 在证据足够后写 paper。
- 不从空白 hallucinate。
- 所有核心 claim 必须引用 artifact / literature / experiment evidence。

最低输出：

- `paper/contribution.md`
- `paper/outline.md`
- `paper/draft.md`

### 11.7 Auditor Agent

职责：

- 检查 claim 是否有 evidence。
- 检查 result 是否来自当前项目 artifact。
- 检查 references 是否存在。
- 给出 final gate。

最低输出：

- `ledger/evidence_ledger.json`
- `ledger/claim_audit.json`

## 12. Research Harness MVP 验收标准

第一版 MVP 不追求 UI 完美，不追求完整 release package。只追求一件事：系统能真的做一个小研究项目。

输入：

- 一个 NLP/RAG/IR idea。

输出必须包含：

1. 至少 20 篇相关论文或真实文献记录。
2. 至少 5 个候选 hypothesis。
3. 至少 1 个被选中并转成 experiment plan 的方向。
4. 一个真实可运行代码工作区。
5. 至少一个 baseline。
6. 至少一个 proposed method 或 method variant。
7. 至少一个 ablation 或 failure comparison。
8. 实验日志和 metrics 文件。
9. reviewer agent 的具体拒稿意见。
10. 一轮基于 reviewer 的追加实验或明确终止。
11. 最终 `research_report.md`。
12. 如果证据不足，报告必须明确 negative result，不生成假阳性论文。

MVP 成功标准：

- 人类打开 workspace 能复现运行命令。
- 人类能看到 agent 为什么做每个决策。
- 人类能区分真实贡献、失败、猜测和待验证项。
- 系统不会把“流程跑完”误报为“高水平论文完成”。

## 13. 建议开发路线

### Phase 0：项目方向重置

目标：

- 更新 docs，明确 Research Harness 是唯一主线。
- 标记旧 project-paper-heavy 路线为 legacy/auditor layer。
- 统一术语：project、workspace、task、agent step、artifact、claim。

交付：

- 更新 `docs/goal.md`。
- 更新 `docs/architecture.md`。
- 新增 `docs/research-harness-roadmap.md`。
- 新增 root-level product brief。

### Phase 1：Workspace-first persistence

目标：

- 新增 `ResearchWorkspace` 服务。
- 统一 `DATA_DIR`。
- 所有新 research run 产物写到 workspace，而不是散落在 project_paper/run paper package。

交付：

- `backend/services/research_harness/workspace.py`
- workspace schema
- timeline jsonl
- artifact write/read helper
- tests

### Phase 2：Task/Agent loop

目标：

- 新增 task abstraction。
- ResearchManager 能按状态推进任务。
- 每个 agent step 都落盘。

交付：

- `ResearchTask`
- `AgentStep`
- `TaskStatus`
- local sequential executor
- basic resume

### Phase 3：Literature + Idea portfolio

目标：

- LiteratureAgent 使用现有 connectors。
- IdeaAgent 生成 candidate portfolio。
- 输出 gap map 和 selected idea。

交付：

- `literature/papers.jsonl`
- `literature/gap_map.md`
- `ideas/candidates.json`
- `ideas/selected.md`

### Phase 4：Experiment coding and execution

目标：

- ExperimentEngineer 生成代码并运行。
- 支持 Python experiment workspace。
- 保存 stdout/stderr、metrics、failures。
- 自动修复常见代码错误。

交付：

- `code/experiment.py`
- `code/run.sh`
- `artifacts/metrics.json`
- `artifacts/logs/`
- repair attempts

### Phase 5：Reviewer-driven follow-up

目标：

- ReviewerAgent 输出可执行批评。
- ResearchManager 把批评转为 follow-up experiment tasks。

交付：

- `reviews/reviewer_round_1.md`
- `reviews/action_plan_1.json`
- follow-up run

### Phase 6：Paper from contribution evidence

目标：

- WriterAgent 基于 contribution/evidence 写论文。
- AuditorAgent gate claim。
- 不再把 ledger 直接拼成正文。

交付：

- `paper/contribution.md`
- `paper/outline.md`
- `paper/draft.md`
- `ledger/claim_audit.json`

### Phase 7：Research cockpit frontend

目标：

- UI 从论文编辑器转为研究驾驶舱。

交付：

- agent timeline
- workspace file viewer
- experiment log viewer
- reviewer objections panel
- next-action approval controls

## 14. 技术债清单

优先级高：

- 统一 `backend/data` 与 `backend/backend/data`。
- 明确 deterministic test data 与 real research workspace 的边界。
- 降低 `project_paper_orchestrator.py` 的中心地位。
- 把 live LLM / live connector 运行从普通 pytest 中隔离。
- 把 experiment codegen 从 toy/frozen benchmark 推向真实可运行 workspace。
- 建立 agent timeline，而不是只存最终 JSON。

优先级中：

- 清理 legacy writing / mentor / MVP artifacts 的入口。
- 更新 README，避免继续宣传“Generate Draft”式论文工作流为主线。
- 前端 API types 跟随新 research harness schema。
- 增加 real-run smoke script，但不进入 deterministic CI。

优先级低：

- venue adapter 扩展。
- release archive 美化。
- compliance checklist UI 深化。
- deployment catalog 扩展。

## 15. 风险与约束

### 15.1 成本风险

真正 ARIS/FARS 式运行需要大量 LLM 调用和实验时间。需要预算控制：

- max papers
- max candidates
- max code repair attempts
- max experiment runtime
- max total cost

### 15.2 实验环境风险

自动生成代码可能需要依赖安装、数据下载、CPU/GPU 资源。MVP 应先限定在轻量 NLP/IR/RAG 任务，避免一开始支持大模型训练。

### 15.3 伪贡献风险

系统必须继续保留硬 gate：

- 未跑实验不能写论文。
- 未超过 baseline 不能声称 improvement。
- 单数据集结果不能声称 generalization。
- cached/stale literature 不能作为 final claim support。
- memory 只能 discovery，不能 claim evidence。

### 15.4 UI 复杂度风险

不要先重做漂亮 UI。先做能跑通的 research harness，再做 cockpit。否则会再次过早产品化。

## 16. 下一步建议

下一步不要继续修上一轮 RAG 测试论文，也不要继续堆 publish package。建议直接执行：

1. 更新 `docs/goal.md`，把旧 Goal 1-13 标记为 completed baseline / auditor assets。
2. 新增 `docs/research-harness-roadmap.md`。
3. 新建 `backend/services/research_harness/`。
4. 实现 `ResearchWorkspace` 和 workspace layout。
5. 实现最小 sequential ResearchManager。
6. 接入 LiteratureAgent，复用现有 connectors。
7. 生成 idea portfolio。
8. 做一个限定领域 MVP：RAG/IR 小实验，能自动写代码、跑 baseline、输出 metrics。
9. 再引入 reviewer-driven follow-up。
10. 最后才回到 paper generation 和前端 cockpit。

推荐第一条真实验收任务：

> 用户输入一个 RAG/IR idea，系统在本地创建 workspace，检索文献，生成 5 个候选 hypothesis，选择 1 个，写出可运行的 Python 实验，跑 baseline/proposed/ablation，保存 metrics 和 logs，生成 reviewer critique，并输出 research report。若结果不优于 baseline，必须写成 negative result。

## 17. 当前项目一句话判断

ScholarFlow 当前不是没价值，而是价值放错了位置。它已经有较强的 evidence/audit/governance 基础，但真正的 autonomous research harness 不够强。后续必须停止继续包装论文产物，把核心工程重心转到“agent 真实读论文、想 idea、写代码、跑实验、被审稿、补实验”上。只有这个内核成立，ScholarFlow 才会接近用户最初想要的 ARIS/FARS。
