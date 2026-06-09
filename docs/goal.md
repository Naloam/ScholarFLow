ScholarFlow 目标路线图：AI 自动科研 + 写论文系统
================================================

文档状态
========

- 更新时间：2026-06-09。
- 默认下一阶段：Goal 5 - Project-Level Manuscript Compiler V2。
- 本文件是下一轮 `/goal` 的主要执行依据。
- `AGENTS.md` 只保留高层协作约束；具体阶段、验收标准、下一轮 prompt 以本文件为准。

最终目标
========

ScholarFlow 的长期目标是一个受证据约束的 ARIS/FARS-style 自动科研系统：

user idea
-> research brief
-> literature/gap validation
-> hypothesis bank
-> selected direction
-> experiment protocol
-> execution/repair
-> evidence ledger
-> project conclusions
-> paper draft
-> reviewer simulation
-> revision loop
-> submission package
-> final publish decision

这个系统的核心差异化不是“自动写一篇看起来像论文的文本”，而是：

- claim-evidence ledgers；
- artifact lineage；
- benchmark/literature provenance；
- failure-driven replanning；
- negative evidence retention；
- reviewer simulation；
- autonomous but bounded revision；
- publish gates that prevent unsupported claims。

如果证据不够，系统必须诚实地输出 blocker、limitation、kill criterion、required follow-up，并保持 `final_publish_ready=false`。

我们离目标还差多远
==================

简短结论：

- 已经完成从固定 claim-evidence case 到受控 domain idea-to-review-package loop 的工程骨架，并完成第一版真实缓存文献/benchmark provenance 扩展。
- 现在处在“能生成 review-ready package 或可审计 blocker”的阶段。
- 离“真实自动科研 + 写论文 + submission package”还差 3 个大能力层：
  1. project-level manuscript compiler V2；
  2. autonomous revision and submission packaging；
  3. real end-to-end evaluation and operator productionization。
- 离“可靠 final-publish-ready autonomous scientist”还远，因为 final publish 需要真实、多源、可复现、统计充分、负证据完整的 evidence chain。

更具体地说：

- Idea routing / controlled domains：第一版完成。
- Brief / hypothesis / selected direction：第一版完成。
- Per-domain evidence package loop：第一版完成。
- Literature/gap validation：已有策略、fixture blocker、readiness propagation、cached arXiv/Semantic Scholar/Crossref connector contract、dedupe、structured metadata、known methods/datasets/metrics/SOTA extraction、source sufficiency policy 和 extraction limitations；后续仍需更广的真实全文/现场 connector coverage。
- Benchmark resolver：已有 structured resolver 和 imported benchmark provenance path；source independence、scale/statistics support 仍继续约束 final publish。
- Experiment protocol：已有 per-domain protocol、typed execution job materialization、deterministic replay/local/import runtime、Docker/bridge structured blockers。
- Execution/repair：已有 typed runtime validation、environment manifest、failure classifier、repair recommendation 和 bounded blocker 分类；后续真实外部执行能力仍需由具体 bridge/Docker 环境接入。
- Evidence ledger/readiness：已有 typed execution result 到 run/project/package-level evidence、negative evidence、readiness/package manifest 的映射，并已接入 cached literature / imported benchmark provenance；后续要在 manuscript compiler/package 中消费这些 evidence refs。
- Paper/reviewer/revision：已有 project orchestrator 和 reviewer/publish gate 基础；还缺 submission-ready compiler V2、autonomous revision loop、finding-by-finding reviewer response。
- Submission/final publish：还没有完整 final submission archive；`final_publish_ready=true` 只能在后续真实 evidence 满足 publish policy 后出现。

已完成基线
==========

1. Offline Publication-Grade Paper Case And Submission Package V3
   - 完成提交：`0aec946 Complete offline publication case package`
   - 固定 claim-evidence idea 能生成 review bundle、paper sources、compiler evidence、literature support index、benchmark provenance、experiment/statistics evidence、negative evidence、review/revision/rereview、submission/publication manifests。
   - 系统能区分 review bundle 与 final publish bundle。

2. Goal 1: First Final-Publish Candidate For Claim-Evidence Retrieval
   - 完成提交：`d53e5a6 Complete final-publish candidate case`
   - 固定 claim-evidence retrieval / verification vertical 已推进到第一个 final-publish-candidate case runner。
   - 使用 repository-local SciFact verification 与 retrieval frozen snapshots，各 120 normalized examples，train/test split，原始 benchmark records provenance。
   - 当前 `final_publish_ready=false` 是正确状态，主要 blocker 是 source independence、negative/residual evidence、claim ceiling。

3. Goal 2A: Controlled Domain Router, Template Registry, And Idea-To-Hypothesis Automation
   - 完成提交：`dda8dc6 Implement controlled domain idea routing`
   - 已支持：
     - `claim_evidence_retrieval`
     - `rag_citation_faithfulness`
     - `lightweight_ml_nlp_benchmark`
   - 已实现 controlled domain router、versioned template registry、idea -> brief -> hypothesis bank -> selected direction、unsupported-domain audit blockers。
   - Unsupported domain 不生成 fake jobs。

4. Goal 2B: Domain Evidence And Review Package Loop
   - 完成提交：`7d48bbf Implement domain evidence package loop`
   - 已实现 per-domain literature strategy/result、structured benchmark resolver、experiment protocol、deterministic execution/import replay validation、evidence ledger/readiness/package propagation。
   - API、Operator Console、frontend types、docs、evaluation traces 已有 generalized domain package/readiness surface。
   - RAG/citation 和 lightweight ML/NLP domains 可以形成 review-ready package 或 concrete blocker，但 fixture/local smoke evidence 保持 review-only / engineering-validation。
   - Unsupported domain 全链路 blocked/auditable，不生成 fake experiment outputs。

5. Goal 3: Real Experiment Backend And Repair Productionization
   - 完成提交：`a0024a4 Implement typed experiment execution backend`
   - 已实现 typed experiment execution plan/job/result/blocker/runtime-contract/output-validation/environment-manifest schema。
   - 已新增 `backend/services/autoresearch/experiment_execution.py`，将 domain protocol/factory plan materialize 为 deterministic replay、repository-local command、Docker-blocked、external/bridge import jobs。
   - 已明确 `AutoResearchExecutionPlane` 是整条 auto-research run 的 queue/worker plane；Goal 3 runtime 是 experiment-job runtime，不替代 queue。
   - Replay/local/import runtime 记录 command/replay/import spec、environment manifest、runtime contract、output validation、fingerprint、failure classification、repair recommendation、lineage refs，并通过 repository helpers 持久化 `experiment_execution_plan.json` / `experiment_execution_result.json`。
   - Unsupported domain、missing protocol、missing benchmark、Docker unavailable、bridge unavailable、budget approval required/rejected 都产生 structured blockers，不生成 fake output refs。
   - Project `experiment_repair_index.json` 现在可记录 typed execution capsules、typed execution run ids、output validation、manifest fragment、failure/repair state，并保留 claim ceiling。
   - API、frontend types/client、deterministic evaluation traces、docs 和 regression tests 已同步；fixture/local smoke evidence 仍不会升级 final publish。

6. Goal 4: Real Literature Scout And Benchmark Provenance Expansion
   - 完成状态：已完成；提交哈希以 `git log` 为准。
   - 已实现 cached arXiv / Semantic Scholar / Crossref connector contract；tests 使用 repository-local cache/fixtures，不依赖 live network。
   - Paper metadata 现在记录 source id、cache key、cache timestamp、fingerprint、extraction status，并保留 source/cache availability status。
   - Literature scout 保留 known methods/datasets/metrics/reported results/SOTA hints、source sufficiency policy、related-system coverage 和 extraction limitations。
   - Benchmark resolver 支持 brief-provided imported benchmark provenance，能提升 domain readiness，但仍保留 statistics、source independence、execution validation、negative evidence 和 publish-gate blockers。

当前不要重做
============

- 不要重做 Goal 1，除非新改动破坏其 artifact 或测试。
- 不要重做 Goal 2A，除非 router/template/unsupported-domain blocker 回归。
- 不要重做 Goal 2B，除非 evidence chain、package readiness、claim ceiling 或 API/schema/docs 出现漂移。
- 不要重做 Goal 3，除非 typed execution runtime、validation、environment manifest、evidence mapping 或 repair classification 回归。
- 不要重做 Goal 4，除非 cached connector provenance、source sufficiency、extraction limitations、benchmark provenance 或 evaluation trace 回归。
- 不要为了 demo 降低 publish gates、claim-evidence ledger、artifact lineage、repair safety、negative evidence、readiness blockers。
- 不要把 fixture/toy/local smoke evidence 宣称为 publication-grade。
- 不要把 unsupported domain 降级成无关 toy experiment。

全局不可破坏原则
================

- Claim 必须能追溯到 evidence ledger entry 或明确降级。
- Literature、benchmark、execution、statistics、negative evidence、manuscript claims 必须能通过 artifact lineage 追溯。
- Evidence-producing repair action 只有在真实产生或导入对应 artifact 后才能 `completed`。
- Single-run evidence 不得膨胀成 project-level claim。
- Fixture/toy/local smoke/import replay evidence 必须带 claim ceiling。
- Unsupported domain 必须有 structured blocker，不得生成 fake protocol/job/output。
- Docker、network、paid LLM、GPU、external benchmark unavailable 必须成为 structured blocker 或 deterministic fallback，不得 silent skip。
- Tests 必须 deterministic，不依赖 live network、paid LLM、GPU、Docker daemon、外部 benchmark 在线可用性。
- Publication gate 失败是有效结果，不是要绕过的问题。

固定开局审计
============

每一轮开始必须先执行：

1. `git status --short --branch`
2. `git log --oneline -n 8`
3. 阅读 `docs/goal.md`
4. 阅读目标阶段列出的关键文件

审计结论必须进入代码产物、evaluation artifact、readiness report、docs 或 tests，不能只写在聊天回复里。

测试节奏
========

- 小改动先跑 `python -m py_compile`、窄 pytest、`git diff --check`。
- 共享后端行为变更后跑 `cd backend && ../.venv/bin/pytest -q`。
- API/schema/frontend types 变更后跑 `cd frontend && npm run build`。
- Operator Console 或浏览器流程变更后再考虑 E2E。
- 每轮收口前至少跑 `git diff --check`。

Goal 3: Real Experiment Backend And Repair Productionization
============================================================

Goal 3 已完成稳定的 typed experiment execution backend；除非测试回归，下一轮不要重复实现 execution backend。

目标
----

把 Goal 2B 的 deterministic replay / narrow local execution 推进成 production-grade experiment execution backend：

- materialize domain experiment protocols into typed jobs；
- support replay/local/import/Docker-blocked/bridge jobs；
- validate outputs and metric schemas；
- record environment manifests and runtime contracts；
- persist execution profiles and artifact refs；
- map execution results back into evidence ledger/readiness/package manifests；
- classify repair actions；
- expose only necessary operator controls；
- keep evidence gates intact。

Goal 3 不是再写一个 publish gate，也不是 UI polishing。它的核心是让实验从“计划/玩具 materialization”变成“可审计执行事实”。

最小可接受范围
--------------

如果下一轮工作量过大，至少完成：

- Phase 1 typed execution job materialization；
- Phase 2 local/replay/import runtime skeleton；
- Phase 3 output/schema/fingerprint validation；
- unsupported domain、missing protocol、Docker unavailable、budget/approval blocker 的 structured blocker；
- deterministic regression tests。

Goal 3 关键必读文件
-------------------

- `backend/services/autoresearch/experiment_factory.py`
- `backend/services/autoresearch/domain_evidence.py`
- `backend/services/autoresearch/execution.py`
- `backend/services/autoresearch/repository.py`
- `backend/services/autoresearch/console.py`
- `backend/services/autoresearch/project_paper_orchestrator.py`
- `backend/services/autoresearch/evaluation_cases.py`
- `backend/api/autoresearch.py`
- `backend/schemas/autoresearch.py`
- `backend/tests/test_autoresearch_regressions.py`
- `frontend/src/api/types.ts`
- `frontend/src/api/client.ts`
- `docs/api-reference.md`
- `docs/claim-evidence-vertical-loop.md`

Goal 3 Phase 0: Execution Capability Audit
------------------------------------------

实现要求：

- 审计当前 experiment factory jobs、materialized jobs、evidence ledger、repair plan、queue/worker execution plane 的边界。
- 明确区分两类 execution：
  - auto-research queue/worker execution：调度整条 research run；
  - experiment execution backend：执行 domain protocol/job 并产生实验 evidence。
- 在 docs 或 tests 中记录该边界，避免下一轮把已有 queue 当成 real experiment runtime。
- 找到已有 toy/materialized path 的 claim ceiling，不能直接把它改名为 production runtime。

输出要求：

- 代码或 docs 中出现明确说明：Goal 3 runtime 是 experiment-job runtime，不替代 queue/worker plane。
- Regression test 覆盖至少一个旧 materialized toy path 不被误标为 publication-grade execution。

Goal 3 Phase 1: Typed Execution Job Materialization
---------------------------------------------------

实现要求：

- 将 experiment factory / domain protocol 输出 materialize 成 typed execution jobs。
- 建议新增或扩展 schema，例如：
  - `AutoResearchExperimentExecutionJobRead`
  - `AutoResearchExperimentExecutionPlanRead`
  - `AutoResearchExperimentExecutionResultRead`
  - `AutoResearchExperimentExecutionBlockerRead`
  - `AutoResearchExperimentRuntimeContractRead`
  - `AutoResearchExperimentOutputValidationRead`
- 每个 job 至少包含：
  - `job_id`
  - `project_id`
  - `run_id`
  - `brief_id`
  - `domain_id`
  - `protocol_id`
  - `benchmark_resolver_ref`
  - `method_ref`
  - `baseline_ref`
  - `job_kind`
  - `execution_route`: `deterministic_replay` / `local_command` / `docker` / `external_import` / `bridge_import`
  - `command` or `import_spec` or `replay_spec`
  - `expected_input_artifacts`
  - `expected_output_artifacts`
  - `metric_schema`
  - `runtime_contract`
  - `environment_requirements`
  - `budget_class`
  - `approval_required`
  - `approval_state`
  - `lineage_parent_refs`
  - `claim_ceiling`
  - `blockers`
  - `warnings`
- Job planner 必须区分：
  - deterministic replay job；
  - repository-local command job；
  - Docker job；
  - external bridge/import job。
- Docker unavailable、external bridge unavailable、budget not approved、unsupported domain、missing protocol、missing benchmark 必须返回 structured blocker。
- Blocked state 不得生成 fake output refs。

建议代码落点：

- `backend/services/autoresearch/experiment_execution.py` 或同等新 helper。
- `backend/services/autoresearch/experiment_factory.py`
- `backend/services/autoresearch/domain_evidence.py`
- `backend/schemas/autoresearch.py`
- `backend/api/autoresearch.py`
- `backend/tests/test_autoresearch_regressions.py`

测试要求：

- Supported claim-evidence idea can materialize deterministic replay/import job with lineage refs。
- RAG/citation domain can materialize review-only replay/local job with claim ceiling。
- Lightweight ML/NLP domain can materialize review-only local/replay job with claim ceiling。
- Unsupported domain materializes no fake job and returns blocker。
- Missing protocol returns blocker。
- Docker job without Docker availability returns blocker, not success。
- Approval-gated job remains `needs_approval` and does not execute。
- Every job carries benchmark/protocol/evidence lineage refs。

Goal 3 Phase 2: Local, Replay, And Import Runtime
-------------------------------------------------

实现要求：

- 实现 deterministic local/replay/import runtime。
- Runtime 输入是 typed execution job，不直接从 API ad hoc 拼路径。
- Replay runtime：
  - 读取 repository-local deterministic replay spec；
  - 验证 replay source package；
  - 记录 replay source hash；
  - 生成 stable fingerprint。
- Import runtime：
  - 验证 imported artifact package；
  - 记录 source package、hash、schema version、import timestamp、provenance；
  - 不得把 schema mismatch 当成功。
- Local command runtime：
  - 只执行 repository-approved safe command/spec；
  - 记录 command、cwd、environment、timeout；
  - 收集 stdout/stderr refs；
  - 记录 exit code；
  - 验证 expected outputs；
  - 验证 metric schema；
  - 记录 deterministic fingerprint。
- Docker runtime：
  - 下一轮可以先不真正执行 Docker；
  - 如果 Docker daemon unavailable 或 policy 不允许，返回 structured blocker；
  - 不得 silent fallback 成 local success。
- Runtime 必须生成：
  - execution profile；
  - environment manifest；
  - runtime contract result；
  - output validation result；
  - failure classification；
  - repair recommendation；
  - lineage refs。

测试要求：

- Deterministic replay success。
- Imported replay success。
- Local command success with expected output。
- Local runtime non-zero exit failure。
- Missing output failure。
- Bad JSON failure。
- Bad metric schema failure。
- Re-running deterministic replay produces stable fingerprint。
- Docker unavailable produces blocker。
- Results persist through repository helpers。

Goal 3 Phase 3: Output Validation And Runtime Contracts
-------------------------------------------------------

实现要求：

- 对每个 expected output 建立 validation record：
  - expected path/ref；
  - exists；
  - content type；
  - sha256；
  - schema version；
  - metric names；
  - metric value types；
  - sample/split counts；
  - baseline references；
  - ablation references；
  - validation status；
  - blockers。
- Runtime contract 至少检查：
  - required inputs exist；
  - expected outputs exist；
  - metric schema matches protocol；
  - benchmark/domain id matches job；
  - environment requirements are recorded；
  - timeout/exit status classified；
  - no unauthorized external dependency is used in deterministic tests。
- Missing outputs、bad JSON、bad metric schema、benchmark mismatch、environment mismatch 不得标记成功。

测试要求：

- Expected output present and schema-valid -> success。
- Missing output -> failure classification `missing_output`。
- Metric not in schema -> `bad_metric_schema`。
- Benchmark mismatch -> `benchmark_mismatch`。
- Environment mismatch -> `environment_mismatch` or blocker。
- Validation blockers propagate to repair plan/readiness。

Goal 3 Phase 4: Evidence Ledger Mapping
---------------------------------------

实现要求：

- 将 execution result 映射回：
  - run-level evidence ledger；
  - negative evidence；
  - benchmark card/provenance context；
  - environment manifest；
  - project readiness report；
  - package manifest；
  - evaluation trace。
- Evidence ledger entry 至少包含：
  - claim；
  - evidence_type；
  - source_job_id；
  - artifact_ref；
  - metric values；
  - sample/split counts；
  - baseline comparisons；
  - ablation status；
  - statistical sufficiency；
  - failure classifications；
  - limitations；
  - claim_ceiling；
  - lineage parent refs。
- Failed job 必须进入 negative evidence 或 readiness blocker。
- Single-run、fixture、local smoke、review-only evidence 必须保留 claim ceiling。
- Evidence mapping 不能覆盖旧 evidence，必须追加或版本化。

测试要求：

- Successful job updates evidence ledger and readiness。
- Failed job updates negative evidence and blocker。
- Missing baseline creates repair requirement and claim ceiling。
- Missing ablation creates mechanism-claim blocker。
- Insufficient statistics creates statistics blocker。
- Artifact refs can be reconstructed from package manifest。
- Fixture/local evidence does not upgrade final publish readiness。

Goal 3 Phase 5: Repair Classifier And Bounded Replanning
--------------------------------------------------------

实现要求：

- Repair classifier 覆盖：
  - `missing_baseline`
  - `missing_ablation`
  - `insufficient_statistics`
  - `runtime_failure`
  - `missing_output`
  - `bad_json`
  - `bad_metric_schema`
  - `benchmark_mismatch`
  - `environment_mismatch`
  - `budget_approval_required`
  - `unsupported_execution_backend`
  - `external_import_required`
- Repair actions 必须分清：
  - can execute now；
  - requires approval；
  - requires imported artifact；
  - requires benchmark/protocol change；
  - blocked by deterministic offline policy；
  - should downgrade claim；
  - terminal blocker。
- Bounded replanning 必须包含：
  - max attempts；
  - attempt count；
  - reason；
  - produced artifacts；
  - unresolved blockers；
  - terminal status。
- Evidence-producing repair 只有在 artifact 真实产生或导入后才能 `completed`。

测试要求：

- 每类 failure 有 deterministic repair classification。
- Approval-required repair 不会自动执行。
- Offline policy 正确阻断需要 live real-world evidence 的 repair。
- Repair loop 达上限后保留 blocker 和 negative evidence。
- Claim downgrade action 不伪造 evidence。

Goal 3 Phase 6: Persistence, API, Console, Frontend Surface
-----------------------------------------------------------

实现要求：

- Persistence 必须通过 repository helpers，不允许 API endpoint ad hoc file writes。
- API/schema 应暴露：
  - execution plan；
  - typed jobs；
  - job status；
  - blockers；
  - runtime contracts；
  - environment manifests；
  - output validation；
  - evidence ledger mapping；
  - repair recommendations；
  - approval state。
- Operator Console 只加必要 controls：
  - list experiment jobs；
  - inspect job；
  - approve/reject approval-gated job；
  - resume/retry when policy allows；
  - view budget/runtime contract；
  - view output artifact lineage；
  - view repair queue。
- Resumability 必须从 persisted state 恢复，不依赖内存。
- Resume/retry 不能覆盖已有 evidence、negative evidence 或 lineage。
- Frontend types/client 如 API 变更必须同步。

测试要求：

- Job list/read API includes status/blockers/lineage。
- Approval-required job remains pending until approved。
- Rejected job becomes blocker。
- Resume preserves prior artifacts。
- Console distinguishes planned/needs_approval/running/succeeded/failed/blocked。
- `cd frontend && npm run build` passes when frontend types change。

Goal 3 Phase 7: Evaluation Cases And Documentation
--------------------------------------------------

实现要求：

- 更新 deterministic evaluation cases：
  - `claim_evidence_generalized_idea`
  - `rag_citation_faithfulness_review_case`
  - `lightweight_ml_nlp_review_case`
  - `unsupported_domain_case`
- 每个 trace 记录：
  - typed execution jobs；
  - runtime route；
  - approval/budget status；
  - output validation；
  - evidence ledger mapping；
  - repair recommendation；
  - package/readiness impact；
  - final publish readiness。
- 更新 docs：
  - `docs/api-reference.md`
  - `docs/claim-evidence-vertical-loop.md`
  - 本文件的完成状态。

测试要求：

- No live network。
- No paid LLM。
- No GPU。
- No Docker daemon requirement。
- Evaluation trace makes blockers obvious。

Goal 3 完成标准
---------------

Goal 3 只有在以下条件都满足时才能标记完成：

- Factory/domain protocol outputs materialize into typed replay/local/import/Docker-blocked execution jobs。
- Unsupported domain、missing protocol、missing benchmark、Docker unavailable、budget/approval blocker 都输出 structured blocker，不生成 fake job/output。
- Local/replay/import runtime 记录 command/import/replay spec、environment manifest、runtime contract、expected/actual outputs、stdout/stderr refs where applicable、fingerprint、failure classification、repair recommendation、lineage refs。
- Missing outputs、bad JSON、bad metric schema、runtime failure、benchmark/environment mismatch 不得标记为成功。
- Execution result maps back into evidence ledger、negative evidence、benchmark card/readiness/package manifest，且保留 claim ceiling。
- Repair classifier 覆盖 Goal 3 Phase 5 列出的 failure classes。
- Deterministic regression tests 覆盖 supported domains、unsupported domains、success/failure paths。
- API/schema/types 变更后 docs/frontend types/client 同步，`npm run build` 通过。
- `git diff --check` 通过。
- 完整后端测试按实际改动运行并记录结果。

Goal 4: Real Literature Scout And Benchmark Provenance Expansion
================================================================

Goal 4 已完成第一版。Goal 3 已有 stable deterministic replay/local/import path；除非 Goal 3/Goal 4 回归，下一轮不要重复实现 execution backend 或 cached connector provenance。

目标
----

把 Goal 2B 的 literature strategy/result 和 benchmark resolver 从 deterministic/fixture-first 推进到 real cached provenance-first：

- cached arXiv / Semantic Scholar / Crossref connectors；
- deduplication；
- structured paper metadata；
- known methods/datasets/metrics/SOTA extraction；
- source-class sufficiency policy；
- benchmark provenance expansion；
- final-publish literature/benchmark blockers。

Goal 4 Phase 1: Cached Connector Contract
-----------------------------------------

实现要求：

- 为 arXiv、Semantic Scholar、Crossref 建立统一 cached connector contract。
- Tests 必须使用 repository-local cache/fixtures，不允许 live network。
- 每条 paper metadata 至少包含：
  - source；
  - source id；
  - title；
  - authors；
  - venue/year；
  - abstract；
  - url/doi/arxiv id；
  - cache key；
  - cache timestamp；
  - fingerprint；
  - extraction status。

测试要求：

- Cache hit deterministic。
- Cache miss in tests becomes structured unavailable status。
- Duplicate paper across sources dedupes by DOI/arXiv/title fingerprint。

Goal 4 Phase 2: Metadata And Evidence Extraction
------------------------------------------------

实现要求：

- Extract known methods/datasets/metrics/reported results/SOTA hints。
- Preserve uncertainty and extraction limitations。
- Do not infer novelty from abstract-only weak evidence。
- Missing related work becomes limitation/follow-up。

测试要求：

- Fixture papers produce deterministic extraction。
- Missing metadata creates limitation。
- Related-system coverage affects readiness。

Goal 4 Phase 3: Benchmark Provenance Expansion
----------------------------------------------

实现要求：

- Expand benchmark resolver beyond current frozen/fixture paths。
- Resolver output must record:
  - source class；
  - source locator；
  - dataset id；
  - revision；
  - license；
  - source fingerprint；
  - sample count；
  - split counts；
  - schema coverage；
  - provenance completeness；
  - publication-grade eligibility；
  - source-independence audit；
  - blockers/limitations/followups。
- RAG/citation and lightweight ML/NLP must not become final-publish-ready until real/imported benchmark provenance and scale exist。

测试要求：

- Real/imported fixture with complete provenance can raise readiness but not bypass statistics/source independence。
- Fixture-only benchmark remains final-publish-blocked。
- Missing license/source fingerprint blocks final publish。

Goal 4 完成标准
---------------

- Literature and benchmark provenance are richer than Goal 2B fixture strategy。
- All connectors are deterministic under tests。
- Readiness/publish gates receive source sufficiency, related-system coverage, extraction limitations, and benchmark provenance blockers。
- No novelty/final-publish claim is supported by fixture-only literature。

Goal 4 当前完成状态
------------------

- Cached arXiv / Semantic Scholar / Crossref connectors share a deterministic cache contract and cache-miss availability status。
- Paper records carry source id、cache key/timestamp、fingerprint、extraction status、structured extraction hints。
- Domain literature results expose source sufficiency policy, related-system coverage, extraction limitations, blockers, follow-ups, and kill criteria。
- Imported benchmark provenance can make a supported domain resolver ready only when provenance passes base eligibility; final publish remains blocked by source independence/statistics/execution/negative-evidence gates。

Goal 5: Project-Level Manuscript Compiler V2
============================================

目标
----

从 brief、literature、hypotheses、selected direction、execution evidence、meta-analysis、review results、claim evidence、domain readiness context 生成 project-level manuscript source package。

Goal 5 Phase 1: Manuscript Context Assembly
-------------------------------------------

实现要求：

- Build a project-level manuscript context containing:
  - research brief；
  - domain decision/template；
  - literature support index；
  - benchmark provenance；
  - experiment execution evidence；
  - evidence ledger；
  - negative evidence；
  - project conclusions；
  - reviewer/revision state；
  - readiness policy；
  - claim ceiling。
- Context must be versioned/fingerprinted。

Goal 5 Phase 2: Evidence-Constrained Compiler
---------------------------------------------

实现要求：

- Generate technical report / workshop case-study / conference-style candidates。
- Required sections:
  - Abstract；
  - Introduction；
  - Related Work；
  - Research Questions；
  - Method；
  - Benchmark And Data；
  - Experimental Setup；
  - Results；
  - Analysis；
  - Negative Evidence；
  - Limitations；
  - Reproducibility；
  - Conclusion；
  - References。
- Every core claim must have evidence refs。
- Unsupported claims must be removed, downgraded, or blocked。
- Fixture/toy evidence must be labeled as engineering validation。
- Negative evidence and limitations must remain visible。

Goal 5 Phase 3: Source Package And Compile Manifest
---------------------------------------------------

实现要求：

- Manuscript source package includes:
  - manuscript source；
  - references；
  - figures/tables metadata；
  - artifact index；
  - compile manifest；
  - claim-evidence index；
  - source fingerprints。
- If compile is unavailable, output a complete source package plus explicit compiler blocker。

测试要求：

- Unsupported claim is downgraded or blocked。
- Negative evidence appears in manuscript package。
- Claim-evidence index covers all core claims。
- Missing reference/artifact blocks source package readiness。

Goal 5 完成标准
---------------

- At least one controlled-domain idea produces a project-level manuscript package with complete claim-evidence index。
- Review-ready remains distinct from final-publish-ready。
- Source package is reconstructable from manifest。

Goal 6: Autonomous Revision Loop
================================

目标
----

把 reviewer simulator findings 转换为 bounded paper revisions、experiment repairs、claim downgrades、literature/benchmark follow-ups、and re-review cycles。

Goal 6 Phase 1: Finding-To-Action Planner
-----------------------------------------

实现要求：

- Map reviewer findings to action types:
  - manuscript text revision；
  - claim downgrade；
  - experiment repair；
  - literature follow-up；
  - benchmark/provenance follow-up；
  - no-action with rationale。
- Each action records:
  - finding id；
  - action kind；
  - evidence requirement；
  - expected outputs；
  - approval requirement；
  - terminal condition。

Goal 6 Phase 2: Bounded Revision Execution
------------------------------------------

实现要求：

- Execute or block actions according to policy。
- Do not fake evidence for experiment/literature actions。
- Preserve original and revised artifacts。
- Record reviewer-response draft item by item。
- Stop after max attempts with clear terminal status。

Goal 6 Phase 3: Re-Review
-------------------------

实现要求：

- Re-review must read revised manuscript/package。
- It must not reuse old scores without checking revised artifacts。
- It must report resolved, partially resolved, unresolved findings。

测试要求：

- Reviewer finding creates bounded revision action。
- Unsupported claim finding causes claim downgrade/blocker。
- Missing experiment evidence finding creates repair action, not fake evidence。
- Re-review reflects revised artifacts。
- Revision loop stops with terminal status。

Goal 6 完成标准
---------------

- A review -> revision -> re-review loop can run deterministically。
- Every revision action has lineage and evidence requirement。
- Claim downgrades and unresolved blockers remain visible in package/readiness。

Goal 7: Submission Package And Final Publish Gate
=================================================

目标
----

生成真正可审计的 submission package，并只在 evidence 满足 domain-specific publish policy 时允许 `final_publish_ready=true`。

Goal 7 Phase 1: Submission Archive
----------------------------------

实现要求：

- Final package includes:
  - manuscript；
  - supplemental artifacts；
  - reproducibility checklist；
  - claim-evidence index；
  - reviewer response；
  - lineage archive；
  - benchmark/source provenance manifests；
  - environment and command manifests；
  - negative evidence appendix；
  - publication readiness manifest。
- Package manifest must reconstruct archive contents。
- Missing artifact blocks archive readiness。

Goal 7 Phase 2: Reproducibility Checklist
-----------------------------------------

实现要求：

- Checklist includes:
  - commands；
  - environment；
  - dependencies；
  - datasets；
  - benchmark versions；
  - metrics；
  - seeds/splits；
  - artifact hashes；
  - known limitations；
  - external requirements。

Goal 7 Phase 3: Final Publish Decision
--------------------------------------

Gate 必须检查：

- literature/source sufficiency；
- benchmark provenance and independence；
- experiment evidence completeness；
- statistics/multi-run/multi-split sufficiency where required；
- negative evidence retention；
- claim-evidence coverage；
- reproducibility package completeness；
- reviewer/revision status；
- unresolved blockers。

如果只达到 review/workshop/case-study 级别，必须保持 final false，并给出 next required evidence。

测试要求：

- Review-ready package does not become final-publish-ready。
- Final-publish-ready case has no hidden unresolved blockers。
- Final gate fails when negative evidence is missing。
- Final gate fails when benchmark/source independence is insufficient unless policy explicitly accepts a substitute and records rationale。
- Submission archive can be reconstructed from manifest。

Goal 7 完成标准
---------------

- At least one case can produce a complete submission package。
- `final_publish_ready=true` only appears when all publish-policy evidence is present。
- Failure cases remain honest and actionable。

Goal 8: Real End-To-End Evaluation And ScholarFlow System Paper Material
========================================================================

目标
----

让 P14 evaluation cases 成为真实 end-to-end regression/evaluation suite，并产出 ScholarFlow 自身 architecture / case-study / failure-analysis paper material。

Goal 8 Phase 1: Executable Evaluation Suite
-------------------------------------------

每个 case 输出：

- full trace；
- literature/gap validation；
- domain decision；
- benchmark provenance；
- execution timeline；
- evidence ledger summary；
- blocker/readiness timeline；
- repair/revision timeline；
- package manifest；
- failure analysis。

测试要求：

- Deterministic。
- No live network。
- No paid LLM。
- No GPU。
- No Docker daemon requirement。

Goal 8 Phase 2: System Paper Material
-------------------------------------

产出材料：

- system architecture；
- evidence constraints；
- case studies；
- failure modes；
- limitations；
- reproducibility package；
- comparison to ARIS/FARS-style goals without overstating capability。

测试要求：

- System paper material only claims what evaluation evidence supports。
- Failure analysis includes blocked and negative cases。

Goal 8 完成标准
---------------

- ScholarFlow can evaluate itself through deterministic cases。
- The generated system-paper material is evidence-constrained and reproducible。

Goal 9: Operator Console Productionization
==========================================

目标
----

只在 backend capability 已存在后补必要 operator controls，不做 UI-only polish。

实现范围
--------

- Long-running job inspection。
- Resume/retry/cancel policies。
- Approval and budget controls。
- Bridge/import status。
- Artifact lineage browser。
- Repair queue inspection。
- Readiness and publish-gate status。
- Project-level package status。

测试要求：

- Controls reflect persisted state。
- Resume/retry preserves lineage。
- Rejected/blocked actions stay visible。
- Frontend build passes。

Goal 9 完成标准
---------------

- Operator can safely inspect and control long-running research workflows。
- UI does not imply final readiness when backend evidence says otherwise。

AGENTS.md 和 skills 决策
========================

- `AGENTS.md` 应只保持高层 current state、active roadmap、safety constraints。
- 本文件负责详细 roadmap。
- 当前不新增 skill。
- 只有当“domain package verification / publication-case audit / execution backend repair loop”成为跨多轮反复使用的稳定流程时，再考虑创建 repository-local skill。
- 由于 `AGENTS.md` 被 `.gitignore` 忽略，本轮如更新它也只是本地协作说明，不会进入普通 git commit。

下一轮执行建议
==============

- 默认执行 Goal 5。
- 不要一次性做 Goal 6-9。
- Goal 5 优先顺序：
  1. Phase 1: Manuscript Context Assembly。
  2. Phase 2: Evidence-Constrained Compiler。
  3. Phase 3: Source Package And Compile Manifest。
- 如果 Goal 3/Goal 4 出现回归，先修复 typed runtime / validation / evidence mapping 或 cached connector / benchmark provenance，再继续 Goal 5。
- 每完成一个实质子阶段，确认 manuscript context、claim evidence index、unsupported-claim downgrade、negative evidence、compile blockers、source fingerprints 和 package readiness 进入 artifact 或 tests。

下一轮可直接使用的 /goal prompt
==============================

下面这段可以直接复制到新对话中：

```text
接下来请使用 /goal 功能执行 ScholarFlow 的下一阶段目标。

目标：实现 docs/goal.md 中的 Goal 5 - Project-Level Manuscript Compiler V2。

优先完成：
1. Goal 5 Phase 1: Manuscript Context Assembly
2. Goal 5 Phase 2: Evidence-Constrained Compiler
3. Goal 5 Phase 3: Source Package And Compile Manifest
4. 必要时同步 API/schema/frontend types、evaluation trace、docs/tests

开始前请先执行并审计：
- git status --short --branch
- git log --oneline -n 8
- 阅读 docs/goal.md
- 阅读 docs/goal.md 中 Goal 5 的 phases 和测试要求
- 阅读 Goal 5 涉及的 project paper compiler / package orchestrator / claim-evidence index / readiness 关键文件

当前基线：
- Goal 1 已通过 commit d53e5a6 完成，不要重做。
- Goal 2A 已通过 commit dda8dc6 完成，不要重做。
- Goal 2B 已通过 commit 7d48bbf 完成，不要重做。
- Goal 3 已完成 typed experiment execution backend；除非测试回归，不要重做。
- Goal 4 已完成 cached literature scout and benchmark provenance expansion；除非测试回归，不要重做。
- 默认分支是 master。

核心要求：
- 全程用中文回复。
- 不要削弱 publish gates、claim-evidence ledger、artifact lineage、repair safety、negative evidence、readiness blockers。
- Unsupported domain 必须产生可审计 blocker，不能伪造 toy experiment outputs。
- Fixture/toy/local smoke evidence 不能宣称为 publication-grade。
- Literature、benchmark、experiment、statistics、negative evidence 和 manuscript claims 必须能通过 artifact lineage 追溯。
- Tests 必须 deterministic，不能依赖 live network、paid LLM、GPU、Docker daemon、外部 benchmark 在线可用性。

Goal 5 验收标准：
- 至少一个 controlled-domain idea 能生成 project-level manuscript package。
- Manuscript context versioned/fingerprinted，并包含 brief、literature、hypotheses、selected direction、execution evidence、claim evidence、negative evidence、review/revision state、domain readiness 和 claim ceiling。
- Every core claim has evidence refs；unsupported claims are removed, downgraded, or blocked。
- Negative evidence and limitations remain visible。
- Source package 包含 manuscript source、references、figures/tables metadata、artifact index、compile manifest、claim-evidence index、source fingerprints。
- 如果 compiler 不可用，仍输出完整 source package 和 explicit compiler blocker。
- 新增或更新 deterministic regression tests。
- 如涉及 API/schema/types，更新 backend schema、frontend types/client、docs，并跑 frontend build。

测试节奏：
- 小步先跑 py_compile、窄 pytest、git diff --check。
- API/schema/types 变更后跑 cd frontend && npm run build。
- Goal 收口前按实际改动跑 cd backend && ../.venv/bin/pytest -q。

完成后：
- 更新 docs/api-reference.md 和 docs/claim-evidence-vertical-loop.md 中相关说明。
- 更新 docs/goal.md 的完成状态和下一阶段默认目标。
- 如 AGENTS.md 当前状态/路线图会误导下一轮，也做最小同步。
- 提交 scoped commit；如果用户要求发布，再 push/PR。
```

最终验收提醒
============

- 只有当当前 evidence 能逐项证明目标完成，才可以标记 goal complete。
- 如果 evidence 不足，继续推进或输出具体 blocker。
- 永远不要把 review-ready package 说成 final-publish package。
- 永远不要通过降低 publish gate、删除 negative evidence、跳过 lineage 或伪造 provenance 来让测试通过。
