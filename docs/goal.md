ScholarFlow 目标路线图：AI 自动科研 + 写论文系统
================================================

文档状态
========

- 更新时间：2026-06-09。
- 默认下一阶段：Goal 7 - Submission Package And Final Publish Gate。
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

- 已经完成 Goal 1-6：从固定 claim-evidence publication case，推进到受控 domain idea routing、domain evidence package loop、typed experiment execution backend、cached literature/benchmark provenance、project-level manuscript compiler V2、autonomous revision loop。
- 当前系统已经能从一个受控 domain idea 生成 project-level manuscript/source package 和 evidence-constrained revision round，或者生成可审计 blocker；但还没有完整 final submission archive、系统级 end-to-end evaluation、production operator controls。
- 以 roadmap 粗略衡量，工程骨架已经过半：Goal 1-6 是“研究事实、论文草稿和审稿修订闭环”，Goal 7-9 是“最终提交、自我评估和生产化操作”。
- 以最终愿景衡量，距离“可靠 final-publish-ready autonomous scientist”仍然很远，因为 final publish 需要真实、多源、可复现、统计充分、负证据完整、审稿修订闭环完成的 evidence chain。当前大多数 deterministic fixture/local/import replay case 只能支持 review/workshop/case-study 级别，不能升级成 publication-grade claim。

更具体地说：

- Idea routing / controlled domains：第一版完成。
- Brief / hypothesis / selected direction：第一版完成。
- Per-domain evidence package loop：第一版完成。
- Literature/gap validation：已有策略、fixture blocker、readiness propagation、cached arXiv/Semantic Scholar/Crossref connector contract、dedupe、structured metadata、known methods/datasets/metrics/SOTA extraction、source sufficiency policy 和 extraction limitations；后续仍需更广的真实全文/现场 connector coverage。
- Benchmark resolver：已有 structured resolver 和 imported benchmark provenance path；source independence、scale/statistics support 仍继续约束 final publish。
- Experiment protocol：已有 per-domain protocol、typed execution job materialization、deterministic replay/local/import runtime、Docker/bridge structured blockers。
- Execution/repair：已有 typed runtime validation、environment manifest、failure classifier、repair recommendation 和 bounded blocker 分类；后续真实外部执行能力仍需由具体 bridge/Docker 环境接入。
- Evidence ledger/readiness：已有 typed execution result 到 run/project/package-level evidence、negative evidence、readiness/package manifest 的映射，并已接入 cached literature / imported benchmark provenance；Goal 5 已在 manuscript compiler/source package 中消费这些 evidence refs，Goal 6 已在 revision action/response/rereview 中保持可追溯，后续 Goal 7 要在 final submission package 中继续保持可追溯。
- Paper/compiler：已有 project orchestrator、versioned/fingerprinted manuscript context、evidence-constrained compiler/source package、claim-evidence index、figures/tables metadata、artifact index、readiness blockers。
- Reviewer/revision：已有第一版 finding-by-finding autonomous revision action planner、bounded execution、reviewer response dossier、revision round 和 re-review cycle；missing experiment/literature/benchmark evidence 仍保持 blocker/follow-up，不伪造 evidence。
- Submission/final publish：还没有完整 final submission archive、reproducibility checklist、lineage archive、final publish package gate；`final_publish_ready=true` 只能在后续真实 evidence 满足 publish policy 后出现。
- System evaluation/operator：P14 evaluation cases 还需要升级为真实 end-to-end regression/evaluation suite；Operator Console 还需要 production controls for long-running jobs、budgets、approvals、resumability、artifact lineage inspection。

剩余路线总览
============

默认顺序必须是 Goal 7 -> Goal 8 -> Goal 9，不要跳过 Goal 7 直接做 system paper/evaluation，也不要优先做 UI polish。

1. Goal 7: Submission Package And Final Publish Gate
   - 生成可重建 submission archive：manuscript、supplemental artifacts、claim-evidence index、reviewer response、lineage archive、benchmark/literature provenance、environment/command manifests、negative evidence appendix、publication readiness manifest。
   - 生成 reproducibility checklist：commands、environment、dependencies、datasets、benchmark versions、metrics、seeds/splits、artifact hashes、external requirements、known limitations。
   - 实现 final publish decision：只有 literature/source sufficiency、benchmark provenance/source independence、experiment evidence、statistics、negative evidence、claim coverage、revision status、reproducibility package 全部满足 policy，才允许 `final_publish_ready=true`。

2. Goal 8: Real End-To-End Evaluation And ScholarFlow System Paper Material
   - 将 P14 cases 升级为 deterministic executable evaluation suite。
   - 每个 case 输出完整 trace：idea/domain/literature/benchmark/execution/evidence/readiness/repair/revision/package/failure-analysis timeline。
   - 产出 ScholarFlow 自身 architecture、case studies、failure modes、limitations、reproducibility material；所有系统论文 claims 必须由 evaluation evidence 支撑。

3. Goal 9: Operator Console Productionization
   - 在 backend capability 已存在后补 production controls：long-running job inspection、resume/retry/cancel、approval/budget controls、bridge/import status、artifact lineage browser、repair queue、readiness/publish-gate/package status。
   - UI 必须反映 persisted state，不得把 review-ready 暗示为 final-publish-ready。
   - 这是最后做的 operational layer，不替代 Goal 6-8。

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
   - 完成提交：`a31322e Implement cached literature provenance expansion`
   - 已实现 cached arXiv / Semantic Scholar / Crossref connector contract；tests 使用 repository-local cache/fixtures，不依赖 live network。
   - Paper metadata 现在记录 source id、cache key、cache timestamp、fingerprint、extraction status，并保留 source/cache availability status。
   - Literature scout 保留 known methods/datasets/metrics/reported results/SOTA hints、source sufficiency policy、related-system coverage 和 extraction limitations。
   - Benchmark resolver 支持 brief-provided imported benchmark provenance，能提升 domain readiness，但仍保留 statistics、source independence、execution validation、negative evidence 和 publish-gate blockers。

7. Goal 5: Project-Level Manuscript Compiler V2
   - 完成提交：`91afa97 Complete project manuscript compiler package`
   - 已实现 versioned/fingerprinted manuscript context、evidence-constrained compiler/source package、source claim-evidence index、figures/tables metadata、artifact index、source fingerprints、missing reference/artifact readiness blockers。
   - Project-level manuscript/source package 现在能消费 brief、domain decision、literature support index、benchmark provenance、experiment execution evidence、evidence ledger、negative evidence、project conclusions、review state、domain readiness context 和 claim ceiling。
   - Unsupported claims 会被降级、阻断或限制在 engineering/review-only 表述；negative evidence 和 limitations 保持可见。
   - Review-ready、workshop/case-study、final-publish-ready 仍然明确区分。

8. Goal 6: Autonomous Revision Loop
   - 完成提交：本轮 scoped commit `Implement autonomous revision loop`。
   - 已实现 project-level typed revision action plan、bounded action execution、finding-by-finding reviewer response dossier、revision round、original/revised manuscript fingerprints、re-review resolution summary 和 explicit terminal blockers。
   - Claim downgrade / paper-only revisions 可以 deterministic 更新 manuscript/source package 与 source claim-evidence index；experiment/literature/benchmark/provenance/reproducibility evidence-producing actions 在没有 validated artifact refs 时保持 blocked/follow-up，不伪造 evidence。
   - API、frontend types、evaluation traces、docs 和 deterministic regression tests 已同步。

当前不要重做
============

- 不要重做 Goal 1，除非新改动破坏其 artifact 或测试。
- 不要重做 Goal 2A，除非 router/template/unsupported-domain blocker 回归。
- 不要重做 Goal 2B，除非 evidence chain、package readiness、claim ceiling 或 API/schema/docs 出现漂移。
- 不要重做 Goal 3，除非 typed execution runtime、validation、environment manifest、evidence mapping 或 repair classification 回归。
- 不要重做 Goal 4，除非 cached connector provenance、source sufficiency、extraction limitations、benchmark provenance 或 evaluation trace 回归。
- 不要重做 Goal 5，除非 manuscript context、source package、claim-evidence index、artifact manifest、readiness blockers 或 docs/schema/tests 出现漂移。
- 不要重做 Goal 6，除非 revision action plan、bounded execution、reviewer response dossier、revision round、re-review fingerprints/resolution summary、evaluation trace 或 tests 出现漂移。
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

- 状态：已完成。实现包括 versioned/fingerprinted manuscript context、evidence-constrained compiler/source package、source claim-evidence index、figures/tables metadata、artifact index、source fingerprints、missing reference/artifact readiness blockers，以及 deterministic tests。
- At least one controlled-domain idea produces a project-level manuscript package with complete claim-evidence index。
- Review-ready remains distinct from final-publish-ready。
- Source package is reconstructable from manifest。

Goal 6: Autonomous Revision Loop
================================

目标
----

把已有 reviewer simulator、review loop、publication repair plan、paper revision artifacts 升级成证据约束的 autonomous revision production path：

- reviewer findings -> typed revision actions；
- typed actions -> bounded manuscript/package revision、claim downgrade、experiment repair request、literature/benchmark follow-up blocker；
- revised manuscript/package -> item-by-item reviewer response；
- revised package -> deterministic re-review；
- unresolved issues -> next bounded round or terminal blocker。

Goal 6 不是重新实现 reviewer simulator，也不是为了让 paper 看起来更好而改写所有段落。它的核心是把“审稿意见”转换为可追溯、可停止、不会伪造证据的修订闭环。

当前基础
--------

Goal 6 实现复用并审计了这些现有能力：

- `backend/services/autoresearch/review_publish.py` 已提供 run review、review loop、publish/readiness 相关聚合。
- `backend/services/autoresearch/reviewer_simulator.py` 已提供 reviewer simulation / response-plan 基础。
- `backend/services/autoresearch/publication_repair_plan.py` 已能从 review / readiness / evidence blockers 汇总 repair actions。
- `backend/services/autoresearch/publication_repair_execution.py` 已有 repair execution 基础。
- `backend/services/autoresearch/orchestrator.py` 已有 review-loop apply / auto-apply / paper rebuild 入口。
- `backend/services/autoresearch/project_paper_orchestrator.py` 已有 manuscript context/source package/paper revision artifacts。
- `backend/services/autoresearch/repository.py` 已有 paper revision state/action index/diff 的 artifact paths。
- `backend/api/autoresearch.py` 已有 review-loop refresh/apply/auto-apply endpoint。

本轮在 `project_paper_orchestrator.py` 中补齐了 project-level typed schema、lineage、deterministic tests 和 artifact persistence，没有重写平行 reviewer/review-loop 系统。

非目标
------

- 不在 Goal 6 中实现 final submission archive；那是 Goal 7。
- 不在 Goal 6 中新增真实 live literature/network connector；缺文献时生成 follow-up/blocker。
- 不在 Goal 6 中执行未经 policy 允许的外部实验、Docker、GPU、paid LLM job。
- 不用 reviewer score 变高替代 evidence sufficiency。
- 不把 claim downgrade 包装成“证据已补足”。

Goal 6 Phase 0: Revision Capability Audit
-----------------------------------------

实现要求：

- 审计现有 review loop、reviewer simulator、publication repair plan、paper revision state、paper source package、claim-evidence index、experiment repair index。
- 明确哪些 review findings 已能映射为 existing repair actions，哪些还缺 typed mapping。
- 明确 current review-loop apply 是否只处理 paper rebuild，还是已经能处理 claim downgrade / evidence blocker / repair request。
- 明确 re-review 是否读取 revised package 和新 fingerprint，不能只复用旧 review object。
- 审计结论必须写入 docs、tests、artifact manifest 或 code comments 中的至少一种。

输出要求：

- 文档或测试中记录 Goal 6 是现有 review-loop 的 productionization，不是替换 `review_publish.py`。
- 至少一个 regression test 固定住：old review fingerprint 改变后 apply 必须拒绝 stale action。

Goal 6 Phase 1: Finding-To-Action Planner
-----------------------------------------

实现要求：

- 新增或扩展 typed planner schema，例如：
  - `AutoResearchRevisionActionRead`
  - `AutoResearchRevisionActionPlanRead`
  - `AutoResearchRevisionActionExecutionRead`
  - `AutoResearchReviewerResponseItemRead`
  - `AutoResearchRevisionRoundRead`
  - `AutoResearchReReviewFindingRead`
- 每个 action 至少记录：
  - `action_id`
  - `project_id`
  - `run_id`
  - `review_round`
  - `source_finding_ids`
  - `source_finding_fingerprint`
  - `action_kind`
  - `scope`: `manuscript` / `claim_evidence_index` / `experiment_repair` / `literature` / `benchmark` / `readiness`
  - `evidence_requirement`
  - `can_execute_now`
  - `approval_required`
  - `approval_state`
  - `expected_outputs`
  - `lineage_parent_refs`
  - `claim_ids`
  - `artifact_refs`
  - `terminal_condition`
  - `max_attempts`
  - `attempt_count`
  - `status`
  - `blockers`
  - `rationale`
- Map reviewer findings to action kinds：
  - `manuscript_text_revision`：clarity、organization、missing explanation、citation wording；不需要新 evidence。
  - `claim_downgrade`：unsupported / overstated / fixture-only / single-run / weak statistics claim。
  - `claim_removal`：claim 无 ledger entry 且无法被 downgrade 成 honest limitation。
  - `experiment_repair_request`：missing baseline、missing ablation、insufficient statistics、runtime failure、bad metric schema、missing output。
  - `literature_followup_request`：related-work coverage 不足、novelty unsupported、source sufficiency 不足。
  - `benchmark_provenance_followup_request`：benchmark license、source fingerprint、source independence、split/scale/schema provenance 不足。
  - `reproducibility_followup_request`：command/env/seed/artifact hash 缺失。
  - `no_action_with_rationale`：finding 已解决、与 scope 无关、需要人工判断或被 policy 明确拒绝。
- Planner 必须合并重复 findings，但保留所有 source ids。
- Planner 必须给 evidence-producing action 加上 blocker 或 approval requirement；不得标记为 completed。
- Planner 输出必须持久化，例如 `revision_action_plan.json` 或 existing paper revision action index 的版本化扩展。

测试要求：

- Reviewer finding -> manuscript_text_revision action。
- Unsupported claim finding -> claim_downgrade 或 claim_removal action。
- Missing baseline/ablation/statistics finding -> experiment_repair_request action。
- Literature novelty/source weakness -> literature_followup_request action。
- Benchmark source-independence weakness -> benchmark_provenance_followup_request action。
- Duplicate findings collapse into one action with multiple source ids。
- Evidence-producing action defaults to blocked/needs_approval/import_required，而不是 completed。

Goal 6 Phase 2: Bounded Revision Execution
------------------------------------------

实现要求：

- 根据 action kind 执行或阻断：
  - paper-only action 可以更新 manuscript source package、limitations、negative evidence section、claim wording、related-work wording、reproducibility wording。
  - `claim_downgrade` 必须更新 manuscript、claim-evidence index、readiness blockers/limitations、reviewer response。
  - `claim_removal` 必须从 core claims 中移除或转入 limitation/future-work，且保留 reviewer response 说明。
  - `experiment_repair_request` 只能调用 existing typed execution/repair path 或生成 repair queue item；没有真实 output/import 时不得 completed。
  - `literature_followup_request` 只能调用 cached/offline connector path 或生成 follow-up blocker；不能现场 live network。
  - `benchmark_provenance_followup_request` 只能消费已有/imported provenance 或生成 blocker；不能伪造 source independence。
  - `no_action_with_rationale` 必须写明不执行原因。
- 每轮执行必须保留：
  - original manuscript/source package ref and fingerprint；
  - original claim-evidence index ref；
  - original review/review-loop fingerprint；
  - selected action ids；
  - revised manuscript/source package ref and fingerprint；
  - revised claim-evidence index ref；
  - paper revision diff；
  - action execution result；
  - unresolved blockers；
  - terminal status。
- 对 paper-only rewrite 要保持 deterministic。若依赖 prompt/LLM，测试必须使用 deterministic fixture 或 local fallback。
- 对每个 action 记录 `executed` / `blocked` / `needs_approval` / `requires_import` / `requires_external_evidence` / `terminal_failed`。
- Bounded loop 必须检查 `max_attempts` 和 `auto_revision_rounds_remaining`。
- Stale review fingerprint、stale action plan、missing source package、missing claim-evidence index 必须失败或 blocker。

输出要求：

- `paper_revision_state.json` 或 equivalent persisted state。
- `paper_revision_action_index.json` with action execution statuses。
- `paper_revision_diff.json` with source and revised artifact refs。
- `reviewer_response_draft.json` or equivalent response items。
- Revised manuscript/source package manifest。

测试要求：

- Paper-only finding modifies revised package and records diff。
- Claim downgrade changes claim-evidence index/readiness and leaves limitation visible。
- Evidence-producing experiment action becomes repair request/blocker without fake output ref。
- Literature/benchmark follow-up without cached/imported evidence remains blocker。
- Stale review fingerprint blocks apply。
- Max attempts stops loop with terminal status and unresolved blocker。
- Original artifact refs remain reconstructable after revision。

Goal 6 Phase 3: Reviewer Response Dossier
-----------------------------------------

实现要求：

- 生成 finding-by-finding reviewer response。
- 每个 response item 至少包含：
  - source finding id；
  - original finding summary；
  - action id；
  - action taken；
  - revised artifact refs；
  - evidence refs used；
  - claim ids changed；
  - status：resolved / partially_resolved / unresolved / blocked / no_action；
  - limitation or blocker if unresolved；
  - final-publish impact。
- Reviewer response 不能声称已补实验或已补文献，除非对应 evidence/artifact ref 存在并通过 validation。
- Response dossier 必须进入 review package / manuscript package / future submission package。

测试要求：

- 每个 source finding 都有 response item 或 explicit no-action rationale。
- Claim downgrade response 指向 revised claim-evidence index。
- Blocked experiment/literature response 明确 required follow-up。
- Response dossier fingerprint 随 revised artifacts 改变。

Goal 6 Phase 4: Re-Review
-------------------------

实现要求：

- Re-review 必须读取 revised manuscript/source package、revised claim-evidence index、reviewer response dossier、unresolved blockers。
- Re-review 必须生成新的 review fingerprint；不得只复用旧 scores/findings。
- Re-review 必须对上一轮 findings 输出 resolution status：
  - `resolved`
  - `partially_resolved`
  - `unresolved`
  - `regressed`
  - `superseded_by_blocker`
- Re-review 必须保留新的 findings，不得隐藏因修订引入的新问题。
- Re-review 必须更新 review-loop summary：
  - current round；
  - previous/revised fingerprints；
  - resolved count；
  - partially resolved count；
  - unresolved count；
  - new finding count；
  - pending action count；
  - terminal status；
  - readiness impact。

测试要求：

- Re-review reads revised artifacts and produces new fingerprint。
- Resolved wording/claim downgrade reduces or closes matching finding。
- Blocked experiment repair remains unresolved or superseded_by_blocker。
- Re-review can introduce new finding if revised package breaks evidence coverage。
- Pending action count and terminal status are deterministic。

Goal 6 Phase 5: API, Frontend Types, Evaluation Trace, Docs
-----------------------------------------------------------

实现要求：

- 如 schema/API 变化，同步：
  - `backend/schemas/autoresearch.py`
  - `backend/api/autoresearch.py`
  - `frontend/src/api/types.ts`
  - `frontend/src/api/client.ts`
- API surface 至少能 inspect：
  - revision action plan；
  - action execution results；
  - reviewer response dossier；
  - revised artifact refs；
  - re-review status；
  - unresolved blockers。
- Evaluation traces 必须记录 Goal 6 关键信息：
  - review round；
  - selected actions；
  - paper-only revisions；
  - blocked evidence-producing actions；
  - reviewer response；
  - re-review resolution summary；
  - readiness impact。
- 更新 docs：
  - `docs/api-reference.md`
  - `docs/claim-evidence-vertical-loop.md`
  - `docs/goal.md`

测试要求：

- API read path exposes action plan and re-review status。
- Evaluation case trace includes revision/re-review timeline。
- Frontend build passes if types/client changed。
- Backend regression tests remain deterministic。

Goal 6 完成标准
---------------

状态：已完成。实现和测试覆盖以下条件：

- A review -> action plan -> bounded revision execution -> reviewer response -> re-review loop can run deterministically。
- Every reviewer finding maps to an action or explicit no-action rationale。
- Every revision action has evidence requirement、lineage parent refs、expected outputs、terminal condition、attempt count、status。
- Claim downgrade/removal updates manuscript/source package、claim-evidence index、readiness blockers/limitations。
- Experiment/literature/benchmark evidence-producing actions do not fake artifacts；missing evidence remains repair request/follow-up blocker。
- Original and revised artifacts are both preserved and reconstructable。
- Re-review reads revised artifacts and reports resolved / partially resolved / unresolved / regressed findings。
- Revision loop stops after max attempts with terminal status。
- Deterministic regression tests cover action planner、paper-only revision、claim downgrade、blocked evidence repair、stale fingerprint、re-review。
- API/schema/frontend/docs are synchronized when touched。
- `git diff --check` passes。

Goal 7: Submission Package And Final Publish Gate
=================================================

目标
----

把 existing review/publish package surface 升级成真正可审计、可重建、可下载的 final submission package，并只在 evidence 满足 domain-specific publish policy 时允许 `final_publish_ready=true`。

Goal 7 不是再加一个宽松 gate，也不是把 review-ready archive 改名成 final package。它的核心是 submission archive completeness + reproducibility + final publish policy enforcement。

当前基础
--------

下一轮 Goal 7 应先复用和审计：

- `backend/services/autoresearch/review_publish.py`
- `backend/services/autoresearch/project_paper_orchestrator.py`
- `backend/services/autoresearch/publication_evidence_index.py`
- `backend/services/autoresearch/artifact_integrity_audit.py`
- `backend/services/autoresearch/runtime_contract.py`
- `backend/services/autoresearch/experiment_execution.py`
- `backend/services/autoresearch/domain_evidence.py`
- `backend/services/autoresearch/meta_analysis.py`
- `backend/api/autoresearch.py` publish/export/download endpoints
- `frontend/src/api/types.ts`
- `frontend/src/api/client.ts`

非目标
------

- 不在 Goal 7 中新增 real experiment runtime；缺实验时 final gate blocked。
- 不在 Goal 7 中用手写 checklist 代替 artifact manifest validation。
- 不允许 review-ready/workshop/case-study package 自动升级 final package。
- 不删除 negative evidence、limitations、unresolved reviewer findings。

Goal 7 Phase 0: Publish Package Audit
-------------------------------------

实现要求：

- 审计 existing publish package、manifest、archive export、download gate、paper/source package、claim-evidence index、artifact integrity audit。
- 明确 current package 是否是 review package、submission candidate package、final publish package。
- 找出缺失 artifact、stale archive、manifest reconstructability、readiness blocker propagation 的缺口。
- 审计结论必须进入 docs/tests/artifact manifest。

测试要求：

- Stale archive must be detected。
- Review-ready package cannot be downloaded/exported as final publish package unless final policy passes。

Goal 7 Phase 1: Submission Archive
----------------------------------

实现要求：

- 新增或扩展 submission package schema，例如：
  - `AutoResearchSubmissionPackageRead`
  - `AutoResearchSubmissionArchiveManifestRead`
  - `AutoResearchSubmissionArchiveEntryRead`
  - `AutoResearchReproducibilityChecklistRead`
  - `AutoResearchFinalPublishDecisionRead`
- Final package 至少包含：
  - manuscript source；
  - rendered manuscript if available；
  - supplemental artifacts；
  - figures/tables metadata；
  - references；
  - claim-evidence index；
  - reviewer response dossier；
  - revision history；
  - benchmark/source provenance manifests；
  - literature support index；
  - execution plan/job/result manifests；
  - runtime contracts；
  - environment and command manifests；
  - artifact integrity audit；
  - negative evidence appendix；
  - limitations appendix；
  - reproducibility checklist；
  - publication readiness manifest；
  - final publish decision；
  - lineage archive。
- 每个 archive entry 至少记录：
  - logical id；
  - path in archive；
  - source artifact ref；
  - sha256；
  - size；
  - content type；
  - generated by；
  - required for final publish；
  - validation status；
  - blockers。
- Package manifest must reconstruct archive contents。
- Missing required artifact、hash mismatch、stale source fingerprint、unresolved integrity issue 必须 block archive readiness。
- Archive export 必须通过 repository helpers / existing artifact path helpers，不允许 API endpoint ad hoc writes。

测试要求：

- Complete submission archive manifest reconstructs contents。
- Missing required artifact blocks archive readiness。
- Hash mismatch blocks archive readiness。
- Archive current/stale status follows source package fingerprint。
- Negative evidence appendix is included when negative evidence exists。

Goal 7 Phase 2: Reproducibility Checklist
-----------------------------------------

实现要求：

- Checklist 必须由 artifact/runtime/evidence manifests 生成，不手写空壳。
- Checklist 至少包含：
  - code entry points；
  - commands；
  - cwd；
  - environment；
  - Python/Node/package dependencies if available；
  - external requirements；
  - datasets；
  - benchmark versions；
  - source fingerprints；
  - licenses；
  - metrics；
  - seeds；
  - splits；
  - sample counts；
  - statistical tests；
  - multi-run/multi-split status；
  - artifact hashes；
  - stdout/stderr refs where applicable；
  - runtime contract results；
  - known limitations；
  - expected blocker if reproducibility is partial。
- Checklist 必须标记哪些 item 是 complete / partial / missing / not_applicable。
- External Docker/bridge/GPU/network requirement 不可 silent skip。

测试要求：

- Checklist pulls command/environment from execution result manifests。
- Missing seeds/splits/sample counts create partial/missing status。
- External requirement is explicit blocker, not hidden note。
- Fixture/local smoke evidence keeps review-only claim ceiling in checklist。

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

实现要求：

- Final publish decision 至少包含：
  - `final_publish_ready`
  - `paper_tier`
  - `policy_version`
  - `checked_at`
  - `passed_checks`
  - `failed_checks`
  - `warnings`
  - `blockers`
  - `required_followups`
  - `claim_ceiling`
  - `evidence_refs`
  - `archive_manifest_ref`
  - `readiness_manifest_ref`
- Gate must fail when:
  - unsupported core claim remains；
  - any core claim lacks evidence ref；
  - literature source sufficiency is weak；
  - benchmark provenance/source independence is insufficient；
  - experiment output validation failed；
  - baseline/ablation/statistical sufficiency required but missing；
  - negative evidence is missing or hidden；
  - reviewer critical finding unresolved；
  - revision loop has pending required actions；
  - reproducibility checklist has missing required item；
  - archive manifest is incomplete/stale；
  - artifact integrity audit has unresolved issue。
- Gate may allow workshop/case-study package with `final_publish_ready=false` and explicit `paper_tier`。
- Any policy exception must record rationale、scope、evidence refs、claim ceiling。

Goal 7 Phase 4: API, Frontend, Docs
-----------------------------------

实现要求：

- API/schema expose:
  - submission package；
  - archive manifest；
  - reproducibility checklist；
  - final publish decision；
  - archive export status；
  - blockers and required follow-ups。
- Download endpoints must enforce final gate for final archive download。
- Frontend/client types sync if API changes。
- Docs update:
  - `docs/api-reference.md`
  - `docs/claim-evidence-vertical-loop.md`
  - `docs/goal.md`

测试要求：

- Review-ready package does not become final-publish-ready。
- Final-publish-ready case has no hidden unresolved blockers。
- Final gate fails when negative evidence is missing。
- Final gate fails when benchmark/source independence is insufficient unless policy explicitly accepts a substitute and records rationale。
- Submission archive can be reconstructed from manifest。
- Stale or incomplete archive cannot be downloaded as final。
- Reproducibility checklist blockers propagate to final decision。
- API/frontend types build if changed。

Goal 7 完成标准
---------------

- At least one case can produce a complete, reconstructable submission package。
- `final_publish_ready=true` only appears when all publish-policy evidence is present and no hidden blocker remains。
- Review/workshop/case-study packages remain explicitly non-final。
- Reproducibility checklist, archive manifest, final publish decision, reviewer response, negative evidence appendix, lineage archive are included。
- Failure cases remain honest and actionable with required follow-ups。
- Deterministic tests cover success, review-only failure, missing artifact, stale archive, missing negative evidence, insufficient benchmark independence。
- `git diff --check` passes。

Goal 8: Real End-To-End Evaluation And ScholarFlow System Paper Material
========================================================================

目标
----

让 P14 evaluation cases 成为真实 end-to-end regression/evaluation suite，并产出 ScholarFlow 自身 architecture / case-study / failure-analysis paper material。

Goal 8 不是宣传材料生成器。它的核心是用 deterministic cases 评估 ScholarFlow 自己的 evidence-constrained research loop，并只写评估证据支持的系统论文材料。

非目标
------

- 不使用 live network、paid LLM、GPU、Docker daemon 作为测试必需条件。
- 不把单个 happy-path case 写成系统能力证明。
- 不隐藏 unsupported-domain、failed runtime、weak literature、insufficient statistics、unresolved review blockers。

Goal 8 Phase 0: Evaluation Case Audit
-------------------------------------

实现要求：

- 审计 `backend/services/autoresearch/evaluation_cases.py`、`system_evaluation.py`、existing deterministic traces。
- 确认每个 case 当前覆盖哪些 loop stages，缺哪些 artifact。
- 至少保留这些 case classes：
  - claim-evidence generalized idea case；
  - RAG/citation faithfulness review case；
  - lightweight ML/NLP review case；
  - unsupported domain blocker case；
  - failed execution or missing-output case；
  - review/revision blocker case；
  - final package blocked case。
- 审计结论进入 evaluation suite output 或 docs。

Goal 8 Phase 1: Executable Evaluation Suite
-------------------------------------------

每个 case 必须可执行并输出：

- full trace；
- idea input；
- domain routing decision；
- research brief；
- hypothesis bank；
- selected direction；
- literature/gap validation；
- benchmark provenance；
- experiment protocol；
- typed execution jobs；
- execution timeline；
- output validation；
- evidence ledger summary；
- blocker/readiness timeline；
- repair/revision timeline；
- reviewer/re-review timeline；
- submission/package timeline where applicable；
- package manifest；
- final publish decision；
- failure analysis；
- artifact refs and fingerprints。

每个 trace 必须记录：

- stage status：succeeded / blocked / skipped_by_policy / failed。
- blocker source and severity。
- claim ceiling。
- evidence refs。
- negative evidence。
- deterministic fixture/import/local/replay labels。
- elapsed/budget estimates if available。
- reproducibility constraints。

测试要求：

- Evaluation suite output is deterministic。
- Unsupported domain never produces fake job/output。
- Fixture-only evidence never upgrades final publish readiness。
- Failed execution appears in negative evidence/readiness timeline。
- Re-review timeline appears for Goal 6 capable case。
- Submission/package timeline appears for Goal 7 capable case。

Goal 8 Phase 2: Evaluation Metrics And Scoring
----------------------------------------------

实现要求：

- Add system-level evaluation metrics such as:
  - stage completion coverage；
  - evidence coverage ratio；
  - unsupported claim detection；
  - blocker honesty；
  - artifact lineage completeness；
  - reproducibility package completeness；
  - reviewer finding resolution rate；
  - final gate false-positive count；
  - deterministic replay stability；
  - negative evidence retention。
- Metrics must be computed from artifacts/traces, not manually asserted。
- Any score must include limitations and excluded capabilities。

测试要求：

- Deterministic。
- No live network。
- No paid LLM。
- No GPU。
- No Docker daemon requirement。
- Metric values stable across repeated runs。

Goal 8 Phase 3: System Paper Material
-------------------------------------

产出材料：

- system architecture；
- evidence constraints；
- case studies；
- failure modes；
- limitations；
- reproducibility package；
- comparison to ARIS/FARS-style goals without overstating capability。

实现要求：

- System paper material must include:
  - abstract / intro draft；
  - architecture overview；
  - loop stage description；
  - evidence constraint design；
  - artifact lineage design；
  - case study summaries；
  - failure analysis；
  - limitations；
  - threats to validity；
  - reproducibility appendix；
  - comparison table to target ARIS/FARS-style capabilities；
  - future work。
- Every system claim must point to evaluation case metrics or artifact refs。
- Unsupported or future capabilities must be written as limitations/future work。
- The generated material must be clearly labeled as system paper material, not final submitted paper unless Goal 7 final gate passes for the system paper itself。

Goal 8 Phase 4: API, Docs, Regression
-------------------------------------

实现要求：

- API/schema expose evaluation suite and system paper material if not already sufficient。
- Evaluation artifacts should be persisted through repository helpers or deterministic build paths。
- Docs update:
  - `docs/api-reference.md`
  - `docs/claim-evidence-vertical-loop.md`
  - `docs/goal.md`

测试要求：

- System paper material only claims what evaluation evidence supports。
- Failure analysis includes blocked and negative cases。
- Unsupported-domain case remains blocked and auditable。
- Evaluation report can be reconstructed from trace artifacts。

Goal 8 完成标准
---------------

- ScholarFlow can evaluate itself through deterministic cases covering success, blocker, failed execution, revision, package readiness, unsupported domain。
- Evaluation suite outputs trace artifacts, metrics, readiness timeline, failure analysis, and package references。
- Generated system-paper material is evidence-constrained and reproducible。
- System claims are backed by evaluation evidence refs。
- No live network、paid LLM、GPU、Docker daemon requirement in regression tests。
- `git diff --check` passes。

Goal 9: Operator Console Productionization
==========================================

目标
----

只在 backend capability 已存在后补必要 operator controls，不做 UI-only polish。

Goal 9 是 operational safety layer：让 operator 能看见、审批、暂停、恢复、重试、取消 long-running research workflow，同时保持 persisted state、artifact lineage、evidence gates 一致。

非目标
------

- 不在 Goal 9 中新增核心 research capability。
- 不为了 UI 体验隐藏 blockers 或 readiness failure。
- 不实现只存在前端内存里的状态切换。
- 不让 retry/resume 覆盖旧 evidence、negative evidence 或 revision history。

Goal 9 Phase 0: Operator State Audit
------------------------------------

实现要求：

- 审计 backend persisted state：
  - auto-research run queue/worker execution；
  - typed experiment jobs；
  - approval/budget state；
  - repair queue；
  - revision loop；
  - submission package/archive；
  - readiness/final gate；
  - artifact lineage。
- 确认哪些 controls 已有 API，哪些只有 artifact state，哪些还缺 persistence。
- 审计结论进入 docs/tests。

Goal 9 Phase 1: Backend Control Surface
---------------------------------------

实现范围：

- Long-running job inspection：
  - run id；
  - stage；
  - status；
  - started/updated timestamps；
  - current blocker；
  - last artifact refs；
  - budget/approval state。
- Resume/retry/cancel policies：
  - policy-allowed transitions only；
  - stale fingerprint checks；
  - retry creates new attempt, does not overwrite old artifacts；
  - cancel records terminal status and reason。
- Approval and budget controls：
  - approve/reject execution job；
  - approve/reject repair/revision action；
  - budget class and estimated cost/time；
  - rejection creates visible blocker。
- Bridge/import status：
  - required external artifact；
  - import schema；
  - provenance required；
  - current validation status。
- Artifact lineage browser data：
  - artifact id/ref；
  - parent refs；
  - generated by；
  - sha256/fingerprint；
  - used by claims/packages；
  - missing/stale/integrity issue status。
- Repair queue inspection：
  - action id；
  - source blocker/finding；
  - status；
  - required evidence；
  - attempts；
  - terminal condition。
- Readiness and publish-gate status：
  - review-ready；
  - package-ready；
  - final-publish-ready；
  - blockers；
  - claim ceiling。
- Project-level package status：
  - manuscript/source package；
  - revision state；
  - submission archive；
  - export current/stale。

测试要求：

- API controls reflect persisted state。
- Invalid transition rejected。
- Retry/resume preserves prior artifacts。
- Approval rejection becomes blocker。
- Cancel records terminal status。

Goal 9 Phase 2: Frontend Operator Console
-----------------------------------------

实现要求：

- Update `frontend/src/api/types.ts` and `frontend/src/api/client.ts` with backend contract。
- Add only necessary controls/views:
  - run timeline；
  - job list and detail；
  - approval queue；
  - repair queue；
  - revision loop status；
  - artifact lineage viewer；
  - readiness/final gate panel；
  - package/export status。
- UI must distinguish:
  - planned；
  - needs approval；
  - running；
  - succeeded；
  - failed；
  - blocked；
  - cancelled；
  - stale。
- UI must show blockers and claim ceiling close to readiness/final status。
- Buttons must be disabled when policy disallows action。
- No marketing/landing-page UI work。

测试要求：

- Controls reflect persisted state。
- Resume/retry preserves lineage。
- Rejected/blocked actions stay visible。
- Frontend build passes。
- Browser E2E only if changed flows require it。

Goal 9 Phase 3: Resumability And Safety Regression
--------------------------------------------------

实现要求：

- Simulate restart by rebuilding console state from persisted artifacts/db only。
- Resume must detect stale fingerprints and missing artifacts。
- Retry must produce new attempt id and lineage parent refs。
- Cancel/reject must be terminal unless an explicit new attempt is created。
- UI/API must never imply final readiness when backend says false。

测试要求：

- Console state reconstructs after reload from persisted state。
- Stale package/export is visible。
- Final gate false stays false in UI/API。
- Artifact lineage remains intact after retry/resume。

Goal 9 完成标准
---------------

- Operator can safely inspect and control long-running research workflows。
- Controls are backed by persisted state and policy-checked transitions。
- Resume/retry/cancel/approve/reject preserve lineage and blockers。
- UI does not imply final readiness when backend evidence says otherwise。
- Frontend build passes, and E2E runs if operator flows changed materially。
- `git diff --check` passes。

AGENTS.md 和 skills 决策
========================

- `AGENTS.md` 应只保持高层 current state、active roadmap、safety constraints。
- 本文件负责详细 roadmap。
- 当前不新增 skill。
- 只有当“domain package verification / publication-case audit / execution backend repair loop / autonomous revision audit”成为跨多轮反复使用的稳定流程时，再考虑创建 repository-local skill。
- 由于 `AGENTS.md` 被 `.gitignore` 忽略，本轮如更新它也只是本地协作说明，不会进入普通 git commit。

下一轮执行建议
==============

- 默认执行 Goal 7。
- 不要一次性做 Goal 8-9。
- Goal 7 优先顺序：
  1. Phase 0：审计 existing publish package / manifest / archive export / download gate / artifact integrity，不把 review-ready bundle 改名成 final package。
  2. Phase 1：submission archive manifest，保证 archive contents 可重建、hash/source fingerprint/current-stale 状态可验证。
  3. Phase 2：reproducibility checklist，由 execution/runtime/evidence manifests 生成，不手写空壳。
  4. Phase 3：final publish decision，只有 literature、benchmark、experiment、statistics、negative evidence、claim coverage、revision status、reproducibility package 全部通过 policy 才能 `final_publish_ready=true`。
  5. Phase 4：必要 API/schema/frontend/evaluation/docs 同步。
- 如果 Goal 3/Goal 4/Goal 5/Goal 6 出现回归，先修复 typed runtime / validation / evidence mapping、cached connector / benchmark provenance、manuscript context/source package readiness，或 revision action/response/rereview lineage，再继续 Goal 7。
- 每完成一个实质子阶段，确认 submission archive entries、artifact integrity audit、reproducibility checklist、negative evidence appendix、reviewer response dossier、lineage archive、final publish decision 和 readiness blockers 进入 artifact 或 tests。

下一轮可直接使用的 /goal prompt
==============================

下面这段可以直接复制到新对话中：

```text
接下来请使用 /goal 功能执行 ScholarFlow 的下一阶段目标。

目标：实现 docs/goal.md 中的 Goal 7 - Submission Package And Final Publish Gate。

优先完成：
1. Goal 7 Phase 0: Publish Package Audit
2. Goal 7 Phase 1: Submission Archive
3. Goal 7 Phase 2: Reproducibility Checklist
4. Goal 7 Phase 3: Final Publish Decision
5. Goal 7 Phase 4: API, Frontend, Docs

开始前请先执行并审计：
- git status --short --branch
- git log --oneline -n 8
- 阅读 docs/goal.md
- 阅读 docs/goal.md 中 Goal 7 的 phases 和测试要求
- 阅读 Goal 7 涉及的关键文件：
  - backend/services/autoresearch/review_publish.py
  - backend/services/autoresearch/project_paper_orchestrator.py
  - backend/services/autoresearch/publication_evidence_index.py
  - backend/services/autoresearch/artifact_integrity_audit.py
  - backend/services/autoresearch/runtime_contract.py
  - backend/services/autoresearch/experiment_execution.py
  - backend/services/autoresearch/domain_evidence.py
  - backend/services/autoresearch/meta_analysis.py
  - backend/services/autoresearch/evaluation_cases.py
  - backend/api/autoresearch.py
  - backend/schemas/autoresearch.py
  - backend/tests/test_autoresearch_regressions.py
  - frontend/src/api/types.ts
  - frontend/src/api/client.ts
  - docs/api-reference.md
  - docs/claim-evidence-vertical-loop.md

当前基线：
- Goal 1 已通过 commit d53e5a6 完成，不要重做。
- Goal 2A 已通过 commit dda8dc6 完成，不要重做。
- Goal 2B 已通过 commit 7d48bbf 完成，不要重做。
- Goal 3 已通过 commit a0024a4 完成 typed experiment execution backend；除非测试回归，不要重做。
- Goal 4 已通过 commit a31322e 完成 cached literature scout and benchmark provenance expansion；除非测试回归，不要重做。
- Goal 5 已通过 commit 91afa97 完成 Project-Level Manuscript Compiler V2；除非测试回归，不要重做。
- Goal 6 已完成 Autonomous Revision Loop；除非 revision action plan、bounded execution、reviewer response dossier、revision round、re-review fingerprint/resolution、evaluation trace 或 tests 回归，不要重做。
- 默认分支是 master。

核心要求：
- 全程用中文回复。
- 不要削弱 publish gates、claim-evidence ledger、artifact lineage、repair safety、negative evidence、readiness blockers。
- Unsupported domain 必须产生可审计 blocker，不能伪造 toy experiment outputs。
- Fixture/toy/local smoke evidence 不能宣称为 publication-grade。
- Literature、benchmark、experiment、statistics、negative evidence 和 manuscript claims 必须能通过 artifact lineage 追溯。
- Review-ready/workshop/case-study package 不能自动升级成 final publish package。
- Submission archive、reproducibility checklist 和 final publish decision 必须由 persisted artifacts/manifests 驱动，不能手写通过。
- Tests 必须 deterministic，不能依赖 live network、paid LLM、GPU、Docker daemon、外部 benchmark 在线可用性。

Goal 7 验收标准：
- At least one case can produce a complete, reconstructable submission archive manifest。
- Archive entries include source artifact refs、sha256、size、content type、required/final status、validation status、blockers。
- Reproducibility checklist is generated from artifact/runtime/evidence manifests and exposes commands、environment、datasets、benchmark versions、metrics、seeds/splits、artifact hashes、external requirements、known limitations。
- `final_publish_ready=true` only appears when all publish-policy evidence is present and no hidden blocker remains。
- Review/workshop/case-study packages remain explicitly non-final when source sufficiency、benchmark independence、statistics、negative evidence、revision status、reproducibility package, or integrity checks are incomplete。
- Missing required artifact、hash mismatch、stale archive、missing negative evidence、insufficient benchmark/source independence、unresolved reviewer finding, or pending required revision action blocks final package/readiness。
- Final publish decision records policy version、passed/failed checks、blockers、required follow-ups、claim ceiling、evidence refs、archive/readiness refs。
- 新增或更新 deterministic regression tests。
- 如涉及 API/schema/types，更新 backend schema、frontend types/client、docs，并跑 frontend build。

测试节奏：
- 小步先跑 py_compile、窄 pytest、git diff --check。
- API/schema/types 变更后跑 cd frontend && npm run build。
- Goal 收口前按实际改动跑 cd backend && ../.venv/bin/pytest -q。

完成后：
- 更新 docs/api-reference.md 和 docs/claim-evidence-vertical-loop.md 中相关说明。
- 更新 docs/goal.md 的完成状态和下一阶段默认目标。
- 如 AGENTS.md 当前状态/路线图会误导下一轮，也做最小同步；如果它未被 git 跟踪，不要把无关本地协作说明混入 scoped commit。
- 提交 scoped commit；如果用户要求发布，再 push/PR。
```

最终验收提醒
============

- 只有当当前 evidence 能逐项证明目标完成，才可以标记 goal complete。
- 如果 evidence 不足，继续推进或输出具体 blocker。
- 永远不要把 review-ready package 说成 final-publish package。
- 永远不要通过降低 publish gate、删除 negative evidence、跳过 lineage 或伪造 provenance 来让测试通过。
