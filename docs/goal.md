ScholarFlow 目标路线图：AI 自动科研 + 写论文系统
================================================

文档状态
========

- 更新时间：2026-06-10。
- 默认下一阶段：Goal 8 - Real End-To-End Evaluation And ScholarFlow System Paper Material。
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

- 已经完成 Goal 1-7：从固定 claim-evidence publication case，推进到受控 domain idea routing、domain evidence package loop、typed experiment execution backend、cached literature/benchmark provenance、project-level manuscript compiler V2、autonomous revision loop、reconstructable submission package/final publish gate。
- 当前系统已经能从一个受控 domain idea 生成 project-level manuscript/source package、evidence-constrained revision round、Goal 7 submission archive/checklist/final decision，或者生成可审计 blocker；但还没有系统级 end-to-end evaluation、production operator controls。
- 以 roadmap 粗略衡量，工程骨架约完成 70%-75%：Goal 1-7 是“研究事实、论文草稿、审稿修订和最终提交 gate 闭环”，Goal 8-9 是“自我评估和生产化操作”，Goal 10+ 才是“真实外部科研能力、长期运行和多项目推广”。
- 以最终愿景衡量，距离“可靠 final-publish-ready autonomous scientist”仍然很远，因为 final publish 需要真实、多源、可复现、统计充分、负证据完整、审稿修订闭环完成的 evidence chain。当前大多数 deterministic fixture/local/import replay case 只能支持 review/workshop/case-study 级别，不能升级成 publication-grade claim。
- 近期最关键差距不是“再写论文文本”，而是把 deterministic evaluation cases 升级成系统级 evidence traces 和 ScholarFlow 系统论文材料，并证明 package/final gate 在 success、blocked、failed execution、revision、unsupported-domain 上都诚实可靠。
- 中期最关键差距是系统级可评估性：ScholarFlow 必须能用 deterministic cases 证明自己在 success、blocked、failed execution、revision、package readiness、unsupported domain 上都诚实可靠。
- 长期最关键差距是真实科研能力：live/full-text literature coverage、真实 benchmark/source independence、多环境执行、长期任务恢复、成本/审批、安全沙箱、多项目知识沉淀、最终可提交材料的人工审计接口。

当前距离最终目标的更细判断：

- Research-loop 工程骨架：约 70%-75%。idea -> brief -> hypothesis -> protocol -> execution/import -> evidence -> manuscript -> review/revision -> submission/final gate 的主链路已经打通，但很多 evidence 仍来自 deterministic fixture、cached/import replay 或 repository-local frozen snapshot。
- Deterministic self-evaluation：约 45%-55%。P14 cases 已存在，并且能覆盖多个 domain / blocker / package readiness 场景；但还缺完整 trace artifact、系统级 metric、readiness/failure timeline、以及可直接支撑 ScholarFlow 系统论文 claims 的 evidence refs。
- Operator/production control：约 35%-45%。已有 Operator Console research mode 和部分 queue/control 状态；但还缺 production-grade long-running job inspection、approval/budget controls、retry/resume/cancel safety、artifact lineage browser、repair queue 和 package/final gate inspection UI。
- Real external evidence/execution：约 25%-35%。已有 cached arXiv / Semantic Scholar / Crossref connector contract、imported benchmark provenance、typed execution routes 和 Docker/bridge blockers；但 live/full-text connector、real benchmark ingestion、Docker/bridge execution hardening、external artifact validation、sandbox/budget policy 仍未生产化。
- Long-running autonomous research reliability：约 25%-35%。已有 persisted artifacts、fingerprints、revision rounds、submission packages；但还缺 project timeline/runbook、branch/fork semantics、schema migration policy、attempt ledger、stale repair workflow 和 multi-day resume/retry audit。
- Multi-project memory：约 10%-20%。当前已有单项目 literature/benchmark/evidence artifacts；跨项目 paper/method/dataset/result/negative-finding memory、source-backed reuse policy、staleness/currentness 和 memory query API 还没开始系统化。
- Human review/compliance/release：约 10%-20%。已有 final publish decision 和 package integrity gate；但人工审查、policy exception workflow、license/privacy/compliance、venue adapter、release signing/export 还未实现。
- 距离“可靠 final-publish-ready autonomous scientist”：仍然很远，约 20%-30%。关键原因不是缺少论文文本，而是 publication-grade evidence chain 需要真实多源 literature/full-text evidence、独立 benchmark/source evidence、可复现实验、多 split/seed/statistics、负证据完整、人工/合规审查，以及长期任务可靠性。

更具体地说：

- Idea routing / controlled domains：第一版完成。
- Brief / hypothesis / selected direction：第一版完成。
- Per-domain evidence package loop：第一版完成。
- Literature/gap validation：已有策略、fixture blocker、readiness propagation、cached arXiv/Semantic Scholar/Crossref connector contract、dedupe、structured metadata、known methods/datasets/metrics/SOTA extraction、source sufficiency policy 和 extraction limitations；后续仍需更广的真实全文/现场 connector coverage。
- Benchmark resolver：已有 structured resolver 和 imported benchmark provenance path；source independence、scale/statistics support 仍继续约束 final publish。
- Experiment protocol：已有 per-domain protocol、typed execution job materialization、deterministic replay/local/import runtime、Docker/bridge structured blockers。
- Execution/repair：已有 typed runtime validation、environment manifest、failure classifier、repair recommendation 和 bounded blocker 分类；后续真实外部执行能力仍需由具体 bridge/Docker 环境接入。
- Evidence ledger/readiness：已有 typed execution result 到 run/project/package-level evidence、negative evidence、readiness/package manifest 的映射，并已接入 cached literature / imported benchmark provenance；Goal 5 已在 manuscript compiler/source package 中消费这些 evidence refs，Goal 6 已在 revision action/response/rereview 中保持可追溯，Goal 7 已在 final submission package/archive/checklist/final decision 中继续保持可追溯。
- Paper/compiler：已有 project orchestrator、versioned/fingerprinted manuscript context、evidence-constrained compiler/source package、claim-evidence index、figures/tables metadata、artifact index、readiness blockers。
- Reviewer/revision：已有第一版 finding-by-finding autonomous revision action planner、bounded execution、reviewer response dossier、revision round 和 re-review cycle；missing experiment/literature/benchmark evidence 仍保持 blocker/follow-up，不伪造 evidence。
- Submission/final publish：已有 reconstructable submission archive、archive manifest、reproducibility checklist JSON、limitations appendix、artifact-integrity audit、final publish decision、guarded final archive download；`final_publish_ready=true` 只能在真实 evidence 满足 publish policy 后出现。
- System evaluation/operator：P14 evaluation cases 还需要升级为真实 end-to-end regression/evaluation suite；Operator Console 还需要 production controls for long-running jobs、budgets、approvals、resumability、artifact lineage inspection。

剩余路线总览
============

默认顺序现在是 Goal 8 -> Goal 9 -> Goal 10 -> Goal 11 -> Goal 12 -> Goal 13。不要跳过 Goal 8 直接做 production UI，也不要优先做 UI polish；Goal 10+ 只有在 package/final gate/evaluation/operator 基础稳定后再做。

1. Goal 7: Submission Package And Final Publish Gate
   - 已完成：可重建 `submission_archive.zip` + `submission_archive_manifest.json`，覆盖 manuscript、supplemental artifacts、claim-evidence index、reviewer response、lineage archive、benchmark/literature provenance、negative evidence appendix、publication readiness manifest。
   - 已完成：manifest-driven `reproducibility_checklist.json`、`limitations_appendix.json`、`artifact_integrity_audit.json`。
   - 已完成：`final_publish_decision.json` 和 guarded final archive download；只有 literature/source sufficiency、benchmark provenance/source independence、experiment evidence、statistics、negative evidence、claim coverage、revision status、reproducibility package、archive integrity 全部满足 policy，才允许 `final_publish_ready=true`。

2. Goal 8: Real End-To-End Evaluation And ScholarFlow System Paper Material
   - 将 P14 cases 升级为 deterministic executable evaluation suite。
   - 每个 case 输出完整 trace：idea/domain/literature/benchmark/execution/evidence/readiness/repair/revision/package/failure-analysis timeline。
   - 产出 ScholarFlow 自身 architecture、case studies、failure modes、limitations、reproducibility material；所有系统论文 claims 必须由 evaluation evidence 支撑。

3. Goal 9: Operator Console Productionization
   - 在 backend capability 已存在后补 production controls：long-running job inspection、resume/retry/cancel、approval/budget controls、bridge/import status、artifact lineage browser、repair queue、readiness/publish-gate/package status。
   - UI 必须反映 persisted state，不得把 review-ready 暗示为 final-publish-ready。
   - 这是最后做的 operational layer，不替代 Goal 6-8。

4. Goal 10: Real External Evidence And Execution Hardening
   - 把 cached/offline connector、import replay、local deterministic execution 扩展为受控 real-world mode：live literature/full-text connector、real benchmark ingestion、Docker/bridge execution、artifact import validation、budget/approval/sandbox policy。
   - 真实外部能力必须默认受 policy 约束；不可用时仍输出 structured blocker，不得 silent fallback 成 toy evidence。

5. Goal 11: Long-Running Research Reliability
   - 让多日/多轮 research project 可以 checkpoint、resume、retry、fork direction、compare branch、preserve lineage、roll forward，而不是一次性脚本。
   - 引入 project-level runbook、budget ledger、attempt ledger、failure taxonomy、stale artifact repair、migration/versioning policy。

6. Goal 12: Multi-Project Knowledge And Literature Memory
   - 建立跨项目 paper/source/benchmark/method/result memory，支持去重、证据等级、citation graph、known baseline/SOTA registry、negative finding reuse。
   - Memory 只能作为 candidate evidence discovery；不能直接把历史结论升级为当前项目 claim，必须重新绑定到当前 artifact/evidence ledger。

7. Goal 13: Human Review, Compliance, And Release Packaging
   - 加入最终人工审查接口、policy exception workflow、license/privacy/compliance checklist、submission venue adapter、release artifact signing/export。
   - 这是最终交付层，不得绕过 final publish decision 或人工确认。

后续所有工作总清单
================

下面是 Goal 8-13 的完整剩余工作列表。后续每一轮都应从最靠前的未完成 goal 开始，不要跳级；如果前序 goal 的 artifact、schema、tests 或 docs 回归，先修复回归。

Goal 8 必须交付：

- Evaluation case audit artifact：列出每个 case 的输入、domain、expected path、covered stages、missing stages、artifact refs、claim ceiling、expected blockers。
- Per-case trace artifacts：每个 case 持久化 idea/domain/brief/hypothesis/literature/benchmark/protocol/execution/evidence/readiness/repair/revision/package/final-gate/failure timeline。
- Stage timeline model：每个 stage 至少记录 `stage_id`、status、started/completed timestamps 或 deterministic order、input refs、output refs、blockers、warnings、claim ceiling impact、evidence refs。
- Readiness/failure timeline：必须能解释 why review-ready、why not final-publish-ready、why blocked、why unsupported、why failed execution。
- System metrics：从 trace/artifact 计算，而不是手填；至少覆盖 stage coverage、evidence coverage、unsupported-domain honesty、blocker honesty、artifact lineage completeness、negative evidence retention、final gate false-positive count、revision resolution、package readiness。
- System paper material package：architecture、case studies、failure modes、limitations、threats to validity、reproducibility appendix、ARIS/FARS comparison、future work；每个 system claim 必须指向 evaluation evidence refs。
- API/schema/frontend/docs sync：如果新增 trace/material endpoints 或 schema，必须同步 backend schema、frontend types/client、docs。
- Regression tests：deterministic，不依赖 live network、paid LLM、GPU、Docker daemon、external benchmark online availability。

Goal 9 必须交付：

- Operator persisted-state audit：run queue、typed jobs、bridge/import、approval/budget、repair/revision、submission archive/final gate、artifact lineage。
- Backend control contracts：long-running job inspection、resume/retry/cancel、approval/rejection、budget state、bridge/import status、repair queue、artifact lineage refs、readiness/package/final-gate status。
- Policy-checked transitions：invalid transitions return structured errors；retry creates new attempt and preserves old artifacts；cancel/reject creates terminal blocker；resume checks stale fingerprints.
- Frontend Operator Console：only necessary operational UI，show timeline/job detail/approval queue/repair queue/revision/package/final gate/artifact lineage; buttons disabled when backend policy disallows action.
- Safety regression: restart/reload reconstructs console state from persisted artifacts/db only; UI never implies final readiness when backend says false.

Goal 10 必须交付：

- External capability manifest：network/literature/full-text/benchmark/Docker/bridge/import capabilities with unavailable/disabled/approval_required/ready status。
- Real literature hardening：live/cache modes、full-text/citation-context extraction path、source sufficiency and extraction limitations、source observation fingerprints。
- Real benchmark ingestion：manifest/checksum/schema/splits/license/source fingerprint/source independence/publication eligibility/final-candidate eligibility。
- External execution hardening：approved Docker/bridge/import routes with runtime contract、environment manifest、stdout/stderr refs、output validation、metric validation、failure classification、negative evidence。
- Final gate evidence-origin policy：fixture/local smoke/imported real/frozen snapshot/live source/Docker/bridge/imported execution all have distinct claim-ceiling and final-gate implications。
- Optional live smoke tests can exist, but required regression tests must stay offline/deterministic。

Goal 11 必须交付：

- Versioned project timeline：idea、brief、scout、hypothesis、protocol、execution、evidence、paper、review、revision、package、final decision、operator action events。
- Project runbook：next actions、required approvals、blocked actions、repair candidates、claim ceiling、package/final gate status、kill criteria。
- Attempt ledger：retry/resume/fork attempts with parent refs、old artifact preservation、failure evidence、stale detection。
- Branch/fork model：branch id、parent hypothesis/direction、inherited evidence scope、invalidated evidence、branch comparison、publish readiness。
- Schema/version/migration policy：artifact schema versions、fingerprints、supersedes/superseded_by、migration-needed blockers。

Goal 12 必须交付：

- Source-backed memory item schema：paper/method/dataset/metric/benchmark/result/implementation/negative finding/blocker/project conclusion/reviewer finding。
- Memory provenance：source project id、artifact ref、fingerprint、extraction timestamp、source date/version、evidence grade、limitations、currentness、reuse policy。
- Deterministic memory index：repository-local rebuild/export/import, no live vector DB requirement for tests。
- Memory query integration：idea/brief/scout can get related-system/baseline/benchmark/novelty-risk hints, but these remain discovery hints until current project revalidates them。
- Negative finding/blocker memory：prior blockers can warn, add follow-up or kill criterion, but cannot silently pre-block or support current claims without current evidence。

Goal 13 必须交付：

- Human review records：reviewer role/id、reviewed artifact refs、comments、requested changes、approval/rejection、policy exceptions、timestamp、final decision linkage。
- Compliance checklist：dataset/code/dependency/license/privacy/PII/model/API/benchmark terms/venue/artifact retention checks, all linked to source artifacts。
- Venue adapter：workshop/conference/arXiv/internal report profiles with required files, anonymity, metadata, supplemental policy, export naming。
- Release archive signing/export：release id/version, final decision, human review, compliance, venue metadata, artifact integrity audit, hashes/signature manifest, source package refs, lineage archive。
- Human approval and venue export cannot hide failed scientific final gate; non-final exports must be clearly labeled non-final。

跨 Goal 的永久约束：

- 不削弱 publish gates、claim-evidence ledger、artifact lineage、negative evidence、readiness blockers。
- 不把 review-ready/workshop/case-study package 自动升级 final package。
- 不把 fixture/toy/local smoke/import replay evidence 写成 publication-grade claim。
- 不生成 fake experiment outputs、fake provenance、fake source independence 或 fake statistics。
- 所有新增 artifacts 必须有 schema/version/fingerprint/parent refs 或明确说明为什么不需要。
- 所有 tests 必须 deterministic；live network / Docker / GPU / paid LLM 只能是 optional/manual path。

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
   - 完成提交：`6443138 Implement autonomous revision loop`。
   - 已实现 project-level typed revision action plan、bounded action execution、finding-by-finding reviewer response dossier、revision round、original/revised manuscript fingerprints、re-review resolution summary 和 explicit terminal blockers。
   - Claim downgrade / paper-only revisions 可以 deterministic 更新 manuscript/source package 与 source claim-evidence index；experiment/literature/benchmark/provenance/reproducibility evidence-producing actions 在没有 validated artifact refs 时保持 blocked/follow-up，不伪造 evidence。
   - API、frontend types、evaluation traces、docs 和 deterministic regression tests 已同步。

9. Goal 7: Submission Package And Final Publish Gate
   - 完成提交：`5d0c115 Implement submission package final gate`。
   - 已实现 typed project submission package、reconstructable `submission_archive.zip`、`submission_archive_manifest.json`、manifest-driven `reproducibility_checklist.json`、`limitations_appendix.json`、`artifact_integrity_audit.json`、`final_publish_decision.json`。
   - `load_project_submission_package()` 会重新校验 persisted archive/source hashes 和 source-package fingerprint；missing/hash mismatch/stale archive 会阻断 final decision 和 download。
   - 新增 project-paper submission API 和 guarded download endpoint；review-ready package 仍保持 `final_publish_ready=false`，只有 final policy 全部通过才允许 final archive download。
   - API、frontend types/client、Operator Console、evaluation traces、docs 和 deterministic regression tests 已同步。

当前不要重做
============

- 不要重做 Goal 1，除非新改动破坏其 artifact 或测试。
- 不要重做 Goal 2A，除非 router/template/unsupported-domain blocker 回归。
- 不要重做 Goal 2B，除非 evidence chain、package readiness、claim ceiling 或 API/schema/docs 出现漂移。
- 不要重做 Goal 3，除非 typed execution runtime、validation、environment manifest、evidence mapping 或 repair classification 回归。
- 不要重做 Goal 4，除非 cached connector provenance、source sufficiency、extraction limitations、benchmark provenance 或 evaluation trace 回归。
- 不要重做 Goal 5，除非 manuscript context、source package、claim-evidence index、artifact manifest、readiness blockers 或 docs/schema/tests 出现漂移。
- 不要重做 Goal 6，除非 revision action plan、bounded execution、reviewer response dossier、revision round、re-review fingerprints/resolution summary、evaluation trace 或 tests 出现漂移。
- 不要重做 Goal 7，除非 submission archive/checklist/final decision/download gate、archive integrity、evaluation trace 或 tests 出现漂移。
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

状态：已完成于 `5d0c115 Implement submission package final gate`。后续只在 submission archive、reproducibility checklist、artifact-integrity audit、final-publish decision、download gate 或相关 tests 回归时修复；默认下一阶段是 Goal 8。

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

Goal 10: Real External Evidence And Execution Hardening
=======================================================

目标
----

把现有 deterministic/offline/import-replay 能力扩展到受控 real-world mode：真实文献 connector、全文/引用抽取、真实 benchmark/source ingestion、Docker/bridge execution、external artifact import、budget/approval/sandbox policy。

Goal 10 不是把 network/Docker/GPU 打开就算完成。它的核心是让外部证据和外部执行进入同一套 evidence constraint、runtime contract、artifact lineage、approval、budget、failure classification 和 publish gate。

前置条件
--------

- Goal 7 final submission package 和 final publish decision 已稳定。
- Goal 8 evaluation suite 能覆盖 success/blocker/failure/package/revision cases。
- Goal 9 operator controls 能审批、拒绝、暂停、恢复、检查 long-running/external jobs。
- 如果 Goal 7-9 任一基础回归，先修复，不要直接开始 Goal 10。

非目标
------

- 不让 live network 成为 regression tests 的必需条件。
- 不把 abstract-only / metadata-only literature 当作 full evidence。
- 不把 Docker/bridge/local command failure silent fallback 成 deterministic success。
- 不把外部导入 artifact 自动信任为 valid evidence。
- 不为了生成 final-publish-ready case 绕过 benchmark/source independence、statistics、negative evidence 或 reviewer blockers。

Goal 10 Phase 0: External Capability Audit
------------------------------------------

实现要求：

- 审计已有 connector/runtime/import path：
  - cached arXiv / Semantic Scholar / Crossref connector；
  - literature cache schema and source status；
  - benchmark resolver imported/frozen/remote source classes；
  - typed experiment execution routes；
  - Docker/bridge blockers；
  - external import validation；
  - package/final gate evidence refs。
- 明确每类外部能力的 policy：
  - allowed by default；
  - requires operator approval；
  - requires budget approval；
  - requires sandbox；
  - disabled in tests；
  - final-publish eligible only after validation。
- 审计结论进入 docs、capability manifest、tests 或 readiness artifact。

测试要求：

- Network disabled path remains deterministic。
- Disabled Docker/bridge remains structured blocker。
- External import without required provenance fails validation。
- Capability manifest distinguishes unavailable, disabled, approval_required, and ready。

Goal 10 Phase 1: Real Literature Connector Hardening
----------------------------------------------------

实现要求：

- 扩展 literature connector contract：
  - source id；
  - query；
  - network/cache mode；
  - cache key；
  - request timestamp；
  - response fingerprint；
  - rate-limit/error status；
  - paper metadata；
  - abstract/full-text availability；
  - license/open-access status if known；
  - extraction status；
  - source sufficiency contribution；
  - final-publish eligibility contribution。
- 加入可选 full-text / citation-context extraction path：
  - PDF/HTML/text source ref；
  - parser version；
  - extraction fingerprint；
  - section coverage；
  - citation contexts；
  - method/dataset/metric/result extraction confidence；
  - limitations。
- Literature evidence must classify:
  - metadata_only；
  - abstract_only；
  - citation_context_only；
  - full_text_extracted；
  - imported_full_text；
  - unavailable。
- Related-work / novelty / SOTA claims must not exceed extraction level。
- Live connector tests must be optional/manual; regression tests use cached fixtures.

测试要求：

- Cached full-text fixture supports method/dataset/metric/result extraction。
- Metadata-only evidence creates source sufficiency limitation。
- Connector failure creates blocker/follow-up, not fake papers。
- Duplicate papers dedupe across source ids while preserving source observations。
- Live-network flag off prevents network calls。

Goal 10 Phase 2: Real Benchmark And Dataset Ingestion
-----------------------------------------------------

实现要求：

- Add benchmark ingestion contract for real/imported datasets:
  - dataset id；
  - source locator；
  - version/revision；
  - license；
  - source fingerprint；
  - retrieval/import timestamp；
  - split definitions；
  - sample counts；
  - schema roles；
  - label space；
  - task family；
  - provenance completeness；
  - source independence relation；
  - publication eligibility；
  - final-publish-candidate eligibility。
- Support imported real benchmark package validation:
  - manifest；
  - checksums；
  - schema；
  - train/dev/test splits；
  - examples；
  - qrels/evidence labels where needed；
  - license/source file refs。
- Reject or block:
  - missing license；
  - missing source fingerprint；
  - missing split；
  - insufficient sample count；
  - task-schema mismatch；
  - same-release-only independence when stronger claims require independent source。
- Preserve frozen/local fixtures as review/evaluation assets, not automatic final evidence。

测试要求：

- Valid imported benchmark fixture passes base publication eligibility。
- Missing license/fingerprint/split blocks eligibility。
- Same-source benchmark relation blocks cross-source final claim。
- Miniature fixture remains review-only by scale policy。
- Ingested benchmark provenance appears in package/final decision refs。

Goal 10 Phase 3: Docker / Bridge / External Execution Hardening
---------------------------------------------------------------

实现要求：

- Extend typed execution runtime for approved external execution:
  - Docker route with image/digest/command/env/mounts/timeouts/resource caps；
  - bridge route with handoff manifest, expected output schema, callback/import path；
  - external import route with provenance and artifact package validation。
- Every execution route must record:
  - approval state；
  - budget class；
  - environment manifest；
  - runtime contract；
  - command/import spec；
  - stdout/stderr refs；
  - exit code/status；
  - output validation；
  - metric schema validation；
  - artifact hashes；
  - failure classification；
  - repair recommendation；
  - negative evidence。
- If route is unavailable/unapproved, result must be blocked, not silently rerouted。
- Any imported result must be traceable to source package hash and manifest fingerprint。

测试要求：

- Docker unavailable produces structured blocker。
- Approval rejected produces terminal blocker。
- Bad imported output schema fails validation。
- Missing expected output produces missing-output failure and negative evidence。
- Valid external import fixture maps to evidence ledger and package manifest。

Goal 10 Phase 4: External Evidence Policy In Final Gate
-------------------------------------------------------

实现要求：

- Final publish decision must distinguish:
  - internal fixture；
  - deterministic replay；
  - local smoke；
  - imported real；
  - frozen real-source snapshot；
  - live retrieved source；
  - Docker/bridge execution；
  - externally imported execution。
- Claim ceiling must follow weakest required evidence type.
- Any external-source uncertainty must become:
  - limitation；
  - blocker；
  - required follow-up；
  - kill criterion；
  - policy exception with rationale and evidence refs。
- Package/archive must include connector/runtime/source manifests and validation reports.

测试要求：

- Fixture/local smoke evidence cannot pass final gate。
- Imported real evidence can raise readiness only when provenance and validation pass。
- Missing source independence still blocks final gate。
- Policy exceptions are explicit and scoped。

Goal 10 完成标准
----------------

- ScholarFlow can optionally use live/cached/imported external sources without making tests depend on live services。
- Literature full-text/citation extraction, benchmark ingestion, Docker/bridge/import runtime, and external evidence policy are all artifact-backed。
- External failures remain blockers or negative evidence, not hidden fallbacks。
- Final gate understands evidence origin and claim ceiling。
- Backend tests remain deterministic; optional live smoke tests are documented separately。
- `git diff --check` passes。

Goal 11: Long-Running Research Reliability
==========================================

目标
----

让 ScholarFlow 支持多日、多轮、多分支 research project：checkpoint、resume、retry、fork direction、compare branch、roll forward、preserve old artifacts，而不是一次性 pipeline。

Goal 11 是可靠性和状态演进层。它不新增 scientific claim 能力；它保证系统在长时间运行、失败、暂停、重启、外部导入和多轮修订中不丢失 evidence lineage。

非目标
------

- 不覆盖旧 artifacts。
- 不用最新状态重写历史 evidence。
- 不把 retry 结果和原始失败混在同一个 attempt。
- 不在没有迁移策略时改动 artifact schema。

Goal 11 Phase 0: Persistence And Version Audit
----------------------------------------------

实现要求：

- 审计 persisted objects：
  - project；
  - idea brief；
  - literature scout；
  - hypothesis bank；
  - experiment protocol；
  - execution jobs/results；
  - evidence ledger；
  - manuscript context；
  - revision round；
  - submission archive；
  - final decision；
  - operator controls。
- 为关键 artifact 定义：
  - schema version；
  - fingerprint；
  - parent refs；
  - created/updated timestamps；
  - supersedes/superseded_by；
  - stale detection policy；
  - migration policy。
- 审计结论进入 version manifest 或 docs/tests。

测试要求：

- Stale artifact detected after parent fingerprint changes。
- Schema version missing creates blocker/migration-needed status。
- Old artifacts remain readable after new attempt。

Goal 11 Phase 1: Research Project Timeline And Runbook
------------------------------------------------------

实现要求：

- Create project timeline artifact:
  - event id；
  - event type；
  - stage；
  - status；
  - actor/system；
  - input refs；
  - output refs；
  - parent event refs；
  - blockers；
  - decisions；
  - timestamps。
- Create project runbook:
  - next recommended actions；
  - required approvals；
  - blocked actions；
  - repair candidates；
  - current claim ceiling；
  - current package status；
  - final gate status；
  - kill criteria。
- Timeline/runbook must be reconstructable from persisted state where possible.

测试要求：

- Timeline contains idea->brief->experiment->evidence->paper->revision->package events。
- Blocked unsupported-domain project has clear terminal runbook.
- Retry creates new event with parent refs。

Goal 11 Phase 2: Branching And Direction Forks
----------------------------------------------

实现要求：

- Allow project directions to fork:
  - branch id；
  - parent brief/hypothesis/direction；
  - branch rationale；
  - changed assumptions；
  - evidence reused；
  - evidence invalidated；
  - comparison metrics；
  - branch status。
- Compare branches:
  - evidence strength；
  - feasibility；
  - novelty risk；
  - benchmark availability；
  - execution cost；
  - claim ceiling；
  - publish readiness。
- Branches must not share claims without explicit evidence refs.

测试要求：

- Forked branch preserves parent lineage。
- Invalidated evidence cannot support branch claim。
- Branch comparison is deterministic。

Goal 11 Phase 3: Retry/Resume/Fork Safety
-----------------------------------------

实现要求：

- Resume must check:
  - artifact existence；
  - parent fingerprints；
  - schema versions；
  - pending approvals；
  - stale package/archive；
  - unresolved blockers。
- Retry must:
  - create new attempt id；
  - preserve old failed output；
  - attach failure evidence；
  - update runbook and repair ledger。
- Fork must:
  - copy only allowed context；
  - record inherited evidence scope；
  - mark unsupported inherited claims as pending validation。

测试要求：

- Resume rejects stale parent fingerprint。
- Retry preserves old negative evidence。
- Fork cannot inherit final-publish readiness without revalidation。

Goal 11 完成标准
----------------

- Long-running projects have versioned timeline, runbook, stale detection, retry/resume/fork semantics。
- Old evidence and negative evidence remain reconstructable。
- Branch claims are evidence-scoped。
- Operator/API can inspect current state without reading raw files only。
- `git diff --check` passes。

Goal 12: Multi-Project Knowledge And Literature Memory
======================================================

目标
----

建立跨项目 memory：papers、methods、datasets、metrics、benchmarks、reported results、negative findings、known blockers、prior project outcomes。Memory 用于 discovery 和 planning，不直接替代当前项目 evidence。

Goal 12 的核心是“可复用知识索引”，不是“全局真理库”。任何跨项目信息进入当前项目 claim 前，都必须重新绑定当前项目 artifact/evidence ledger。

非目标
------

- 不让历史项目结论自动支持新项目核心 claim。
- 不把 memory 中的 SOTA/benchmark/result 当成实时事实。
- 不引入无法解释来源和时间戳的 embedding-only memory。
- 不依赖 live vector DB 作为 deterministic tests 前提。

Goal 12 Phase 0: Memory Scope And Provenance Audit
--------------------------------------------------

实现要求：

- 定义 memory item types:
  - paper；
  - method；
  - dataset；
  - metric；
  - benchmark source；
  - reported result；
  - implementation artifact；
  - negative finding；
  - blocker；
  - project conclusion；
  - reviewer finding。
- 每个 memory item 必须记录：
  - source project id；
  - source artifact ref；
  - source fingerprint；
  - extraction timestamp；
  - source date/version；
  - confidence/evidence grade；
  - limitations；
  - currentness status；
  - reuse policy。
- Memory audit must distinguish source observation from project conclusion.

测试要求：

- Memory item without source artifact ref is rejected or marked unusable。
- Project conclusion cannot be reused as current evidence without rebinding。
- Duplicate papers/methods merge while preserving source observations。

Goal 12 Phase 1: Literature And Benchmark Memory Index
------------------------------------------------------

实现要求：

- Build repository-local deterministic memory index:
  - paper metadata；
  - known methods；
  - known datasets；
  - known metrics；
  - reported results；
  - benchmark provenance；
  - SOTA hints；
  - extraction limitations。
- Support queries from idea/brief/scout:
  - related systems；
  - known baselines；
  - benchmark candidates；
  - novelty risks；
  - missing evidence warnings。
- Memory results must be labeled as discovery hints unless current project validates them.

测试要求：

- Memory returns deterministic related-system hints。
- Memory source limitations propagate into scout result。
- Stale memory does not satisfy final gate。

Goal 12 Phase 2: Negative Finding And Blocker Memory
----------------------------------------------------

实现要求：

- Index negative findings and blockers:
  - failed hypotheses；
  - non-improvements；
  - retrieval misses；
  - unsupported claims；
  - benchmark insufficiency；
  - runtime failures；
  - unresolved reviewer findings；
  - final gate blockers。
- Use memory to warn new projects:
  - repeated failure pattern；
  - known impossible source independence；
  - weak benchmark family；
  - high-cost execution path；
  - likely unsupported claim。
- Warnings must not pre-block a project without current evidence; they can recommend kill criteria or validation steps.

测试要求：

- Prior blocker appears as risk/follow-up, not current evidence。
- Negative finding memory can add kill criterion。
- Memory does not hide current positive evidence。

Goal 12 Phase 3: Memory Governance And API
------------------------------------------

实现要求：

- Add memory rebuild/export/import path:
  - deterministic local build；
  - manifest；
  - item count；
  - source artifacts；
  - fingerprints；
  - schema version。
- API/schema expose memory query results with source refs and limitations.
- If vector search is added, keep structured metadata path as source of truth.
- Memory update must be append-only or versioned.

测试要求：

- Memory rebuild is deterministic。
- Import validates schema/version/fingerprint。
- API returns source refs for every memory result。

Goal 12 完成标准
----------------

- ScholarFlow can reuse cross-project literature/benchmark/method/negative-finding knowledge as discovery hints。
- Memory items are source-backed, versioned, and limitation-aware。
- Current project final claims still require current project evidence refs。
- Deterministic tests do not require external vector DB or live network。
- `git diff --check` passes。

Goal 13: Human Review, Compliance, And Release Packaging
========================================================

目标
----

补齐最终交付前的人类审查、policy exception、license/privacy/compliance、venue adapter、release signing/export。Goal 13 是发布前治理层，不是绕过 final gate 的捷径。

非目标
------

- 不允许人工 override 隐藏 evidence blocker。
- 不把 compliance checklist 当作 scientific evidence。
- 不在未通过 final publish decision 时标记 ready for submission。
- 不生成无法追溯来源的 release archive。

Goal 13 Phase 0: Human Review Workflow
--------------------------------------

实现要求：

- Add human review records:
  - reviewer/operator id or role；
  - reviewed artifact refs；
  - checklist status；
  - comments；
  - requested changes；
  - approval/rejection；
  - timestamp；
  - policy exceptions；
  - final decision linkage。
- Human review can:
  - approve final package after gate passes；
  - reject or request revision；
  - approve scoped policy exception with rationale；
  - never erase blockers or negative evidence。

测试要求：

- Human approval cannot flip final ready when gate failed。
- Rejection creates revision/follow-up blocker。
- Policy exception is visible in final decision。

Goal 13 Phase 1: Compliance Checklist
-------------------------------------

实现要求：

- Checklist categories:
  - dataset license；
  - paper/source license；
  - code license；
  - third-party dependency licenses；
  - privacy/PII；
  - model/API usage restrictions；
  - paid service disclosure；
  - benchmark terms；
  - venue formatting requirements；
  - artifact retention policy。
- Checklist must link to source artifacts/manifests.
- Missing compliance evidence blocks release/submission, even if scientific final gate passed.

测试要求：

- Missing dataset license blocks release。
- PII flag blocks release until reviewed。
- Compliance blocker appears in release manifest。

Goal 13 Phase 2: Venue Adapter And Submission Metadata
------------------------------------------------------

实现要求：

- Support venue profiles:
  - workshop；
  - conference；
  - arXiv/preprint；
  - internal technical report。
- Each profile defines:
  - required files；
  - format constraints；
  - anonymity requirements；
  - supplemental policy；
  - checklist requirements；
  - metadata fields；
  - export naming。
- Venue adapter must not weaken evidence gate; it only shapes package format.

测试要求：

- Anonymous venue removes/flags identifying metadata when required。
- Missing venue-required file blocks venue package。
- Internal report can export with final_publish_ready=false but clearly labeled non-final。

Goal 13 Phase 3: Release Archive Signing And Export
---------------------------------------------------

实现要求：

- Release archive includes:
  - submission archive；
  - final decision；
  - human review record；
  - compliance checklist；
  - venue metadata；
  - artifact integrity audit；
  - hashes/signature manifest；
  - source package refs；
  - lineage archive。
- Export records:
  - release id；
  - version；
  - generated_at；
  - source package fingerprint；
  - archive hash；
  - signature/checksum；
  - final status；
  - blockers if non-final。
- Any rebuild must either reproduce same hash or create a new release version with reason.

测试要求：

- Release hash changes when source package changes。
- Stale release is detected。
- Non-final export is labeled non-final。
- Final release requires scientific gate, compliance, and human approval.

Goal 13 完成标准
----------------

- Final package can pass through human review, compliance, venue formatting, and signed release export without losing evidence lineage。
- Human approval cannot hide failed gates。
- Compliance and venue blockers are explicit。
- Release archive is reconstructable and hash-verifiable。
- `git diff --check` passes。

AGENTS.md 和 skills 决策
========================

- `AGENTS.md` 应只保持高层 current state、active roadmap、safety constraints。
- 本文件负责详细 roadmap。
- 当前不新增 skill。
- 只有当“final submission package audit / end-to-end evaluation audit / operator safety audit / external evidence hardening audit”成为跨多轮反复使用的稳定流程时，再考虑创建 repository-local skill。
- 由于 `AGENTS.md` 被 `.gitignore` 忽略，本轮如更新它也只是本地协作说明，不会进入普通 git commit。

下一轮执行建议
==============

- 默认执行 Goal 8。
- 不要一次性做 Goal 9-10。
- Goal 8 优先顺序：
  1. Phase 0：审计 current evaluation cases、trace artifacts、metrics、readiness/failure timeline 和 ScholarFlow system paper material 缺口。
  2. Phase 1：让 deterministic end-to-end cases 输出完整 trace artifacts，覆盖 success、blocked、failed execution、revision、package readiness、unsupported domain。
  3. Phase 2：汇总系统级 metrics 和 readiness/failure timelines，所有系统能力 claims 必须绑定 evaluation evidence refs。
  4. Phase 3：生成 ScholarFlow architecture / case-study / failure-analysis / limitations / reproducibility paper material，不把单个 happy path 写成系统能力证明。
  5. Phase 4：必要 API/schema/frontend/evaluation/docs 同步。
- 如果 Goal 3/Goal 4/Goal 5/Goal 6/Goal 7 出现回归，先修复 typed runtime、cached connector/provenance、manuscript source package、revision loop，或 submission archive/final gate，再继续 Goal 8。
- 每完成一个实质子阶段，确认 evaluation trace、metrics、readiness/failure timeline、package/final-gate evidence refs 和 system-paper material 进入 artifact 或 tests。

下一轮可直接使用的 /goal prompt
==============================

下面这段可以直接复制到新对话中：

```text
接下来请使用 /goal 功能执行 ScholarFlow 的下一阶段目标。

目标：实现 docs/goal.md 中的 Goal 8 - Real End-To-End Evaluation And ScholarFlow System Paper Material。

优先完成：
1. Goal 8 Phase 0: Evaluation Case Audit
2. Goal 8 Phase 1: Deterministic Trace Artifacts
3. Goal 8 Phase 2: System Metrics And Readiness/Failure Timelines
4. Goal 8 Phase 3: ScholarFlow System Paper Material
5. Goal 8 Phase 4: API, Frontend, Docs

开始前请先执行并审计：
- git status --short --branch
- git log --oneline -n 8
- 阅读 docs/goal.md
- 阅读 docs/goal.md 中 Goal 8 的 phases 和测试要求
- 阅读 Goal 8 涉及的关键文件：
  - backend/services/autoresearch/review_publish.py
  - backend/services/autoresearch/project_paper_orchestrator.py
  - backend/services/autoresearch/publication_evidence_index.py
  - backend/services/autoresearch/artifact_integrity_audit.py
  - backend/services/autoresearch/runtime_contract.py
  - backend/services/autoresearch/experiment_execution.py
  - backend/services/autoresearch/domain_evidence.py
  - backend/services/autoresearch/meta_analysis.py
  - backend/services/autoresearch/evaluation_cases.py
  - backend/services/autoresearch/system_evaluation.py
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
- Goal 7 已完成 Submission Package And Final Publish Gate；除非 submission archive、reproducibility checklist、artifact-integrity audit、final-publish decision、download gate、evaluation trace 或 tests 回归，不要重做。
- 默认分支是 master。

核心要求：
- 全程用中文回复。
- 不要削弱 publish gates、claim-evidence ledger、artifact lineage、repair safety、negative evidence、readiness blockers。
- Unsupported domain 必须产生可审计 blocker，不能伪造 toy experiment outputs。
- Fixture/toy/local smoke evidence 不能宣称为 publication-grade。
- Literature、benchmark、experiment、statistics、negative evidence 和 manuscript claims 必须能通过 artifact lineage 追溯。
- Review-ready/workshop/case-study package 不能自动升级成 final publish package。
- Submission archive、reproducibility checklist 和 final publish decision 必须由 persisted artifacts/manifests 驱动，不能手写通过。
- Goal 8 system-paper material 必须由 deterministic evaluation traces 和 evidence refs 支撑，不能把单个 case 或 unsupported evidence 写成系统能力证明。
- Tests 必须 deterministic，不能依赖 live network、paid LLM、GPU、Docker daemon、外部 benchmark 在线可用性。

Goal 8 验收标准：
- Evaluation case audit artifact 列出每个 case 的 input、domain、expected path、covered stages、missing stages、artifact refs、claim ceiling、expected blockers。
- 每个 evaluation case 输出持久化 trace artifact，覆盖 idea/domain/brief/hypothesis/literature/benchmark/protocol/execution/evidence/readiness/repair/revision/package/final-gate/failure timeline。
- Trace stage 至少记录 stage_id、status、deterministic order 或 started/completed timestamps、input refs、output refs、blockers、warnings、claim ceiling impact、evidence refs、negative evidence、deterministic fixture/import/local/replay labels。
- Readiness/failure timeline 能解释 why review-ready、why not final-publish-ready、why blocked、why unsupported、why failed execution。
- System metrics 从 trace/artifact 计算，覆盖 stage coverage、evidence coverage、unsupported-domain honesty、blocker honesty、artifact lineage completeness、negative evidence retention、final gate false-positive count、revision resolution、package readiness。
- ScholarFlow system-paper material includes architecture, case studies, failure modes, limitations, threats to validity, reproducibility appendix, ARIS/FARS comparison, and future work backed by trace evidence refs。
- Evaluation summaries distinguish review-ready, final-publish-ready, blocked, and unsupported cases without weakening Goal 7 final gate。
- No system-level claim is unsupported by evaluation evidence。
- Tests remain deterministic and do not require live network、paid LLM、GPU、Docker daemon、external benchmark availability。
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
