ScholarFlow 下一阶段目标：Generalized Idea-To-Paper Runner And Productionized Execution
================================================================================

当前状态
========

ScholarFlow 已完成三个关键里程碑：

1. Offline Publication-Grade Paper Case And Submission Package V3
   - 完成提交：`0aec946 Complete offline publication case package`
   - 系统可以从固定 claim-evidence idea 生成 review-ready paper package，包含 manuscript、paper sources、compiler evidence、literature support index、benchmark provenance、experiment/statistics evidence、negative evidence、review/revision/rereview、submission/publication manifests。
   - 系统能诚实区分 review bundle 与 final publish bundle。

2. Goal 1: First Final-Publish Candidate For Claim-Evidence Retrieval
   - 完成提交：`d53e5a6 Complete final-publish candidate case`
   - 固定 claim-evidence retrieval / verification vertical 已推进到第一个 final-publish-candidate case runner。
   - 该 runner 使用 repository-local SciFact verification 与 retrieval frozen snapshots，各 120 normalized examples，train/test split，原始 benchmark records 来源，完整 provenance，final-candidate eligible。
   - Package 至少 `review_bundle_ready=true`。
   - `final_publish_ready=false` 仍然是正确状态，因为剩余 blocker 是科学/证据限制：
     - selected benchmark views share the same parent SciFact source release；
     - source-independence repair 被 deterministic offline policy 正确阻断；
     - negative/residual failure evidence 必须保留；
     - claim ceiling 保持 scoped workshop/case-study，而不是 broad final-publish claim。

3. Goal 2A: Controlled Domain Router, Template Registry, And Idea-To-Hypothesis Automation
   - 完成提交：`dda8dc6 Implement controlled domain idea routing`
   - 已支持 3 个受控 domain：
     - `claim_evidence_retrieval`
     - `rag_citation_faithfulness`
     - `lightweight_ml_nlp_benchmark`
   - 已实现：
     - structured domain router；
     - versioned domain template registry；
     - idea -> research brief -> hypothesis bank -> selected direction；
     - unsupported-domain auditable blocker；
     - service-level experiment factory safety gate，blocked brief 不生成 fake jobs；
     - API/schema/frontend type/docs/console/evaluation/project-readiness domain audit surface。
   - 已验证：
     - route check：3 个 supported ideas 均能进入 selected hypothesis / factory plan；unsupported idea 为 blocked、0 directions、0 hypotheses、factory 0 jobs。
     - `python -m py_compile ...` 通过。
     - tracked regression 窄测通过：`6 passed`。
     - `cd backend && ../.venv/bin/pytest -q` 通过：`247 passed, 2 warnings`。
     - `cd frontend && npm run build` 通过。
     - `git diff --check` 通过。

当前不要重做的事情
==================

- 不要重做 Goal 1。Goal 1 已通过 `d53e5a6` 完成，只能在测试回归或新改动破坏 Goal 1 artifact 时修复。
- 不要重做 Goal 2A。Domain router、domain template registry、idea-to-hypothesis automation 已通过 `dda8dc6` 完成。
- 不要为了让 demo 看起来完整而降低 publish gates、claim-evidence ledger、artifact lineage、repair safety、negative evidence 或 readiness blockers。
- 不要把 fixture/toy/local smoke evidence 宣称为 publication-grade。
- 不要把 unsupported domain 降级成无关 toy experiment。

离长期目标还差多远
==================

长期目标仍然是：

user idea -> research brief -> literature/gap validation -> hypothesis bank -> selected direction -> experiment protocol -> execution/repair -> evidence ledger -> project conclusions -> paper draft -> reviewer simulation -> revision loop -> submission package -> final publish decision

当前系统距离这个目标的状态：

- Idea classification/domain routing：已完成第一版。还需要让后续 literature、benchmark、experiment、paper package 真正消费 domain context，而不是只显示 domain fields。
- Research brief/hypothesis/direction：已完成第一版。supported domains 能生成 3 个候选 hypothesis 并选中方向；unsupported domain 可审计阻断。
- Literature/gap validation：仍是下一大缺口。已有 cached/imported connectors 和 scout/gap miner 基础，但还没有 per-domain literature strategy、source class requirements、domain-specific novelty/gap risk、final-publish literature blockers 的完整闭环。
- Benchmark resolver：仍是下一大缺口。claim-evidence 可复用 Goal 1 frozen SciFact path；RAG/citation 和 lightweight ML/NLP 还需要结构化 resolver result、provenance/eligibility/blockers 和 package/readiness 传播。
- Experiment protocol/execution：已有 experiment factory / toy execution / import replay 基础，但还没有 per-domain protocol id、metric schema validation、domain-specific execution adapter、domain-specific negative evidence taxonomy 和 repair routing 的完整闭环。
- Evidence ledger/readiness：claim-evidence 最强；新 domains 还需要把 benchmark/literature/execution evidence 系统性写入 ledgers、negative evidence、readiness report 和 package manifests。
- Project paper/reviewer/revision/submission：已有 project orchestrator 和 submission package 基础；还需要 generalized domain package context，让至少一个新 domain 生成 review-ready package 或清晰 blocker，而不是只有 fixed claim-evidence vertical 最完整。
- Final publish：仍然远。当前下一阶段目标不是强行 `final_publish_ready=true`，而是让受控 domain 的 evidence chain 可审计、可扩展、不会夸大证据。

实话总结：

- Goal 2A 已完成，约等于完成从 idea 到 selected executable direction 的受控入口。
- 距离“任意受控 idea 自动产出 review-ready package”还差 Goal 2B。
- 距离“真实执行后端生产化”还差 Goal 3。
- 距离“从用户 idea 到 submission-ready / final-publish-ready package”还差 Goal 4。

全局原则
========

- 不要削弱 publish gates、claim-evidence ledger、artifact lineage、repair safety、runtime contracts、multi-seed/sweep/statistics、negative-result retention 或 persisted artifact state。
- 不要把 toy、synthetic、cached fixture、单次 run、工程验证或内部评估伪装成 publication-grade science。
- 如果 evidence 不够 final publish，系统必须保持 `final_publish_ready=false`，并输出 blockers、limitations、kill criteria、required follow-up。
- Evidence-producing repair actions 只有在真实产生或导入对应 evidence artifact 后才能 `completed`。
- Literature、benchmark、experiment、statistics、negative evidence 和 manuscript claims 必须能通过 artifact lineage 追溯。
- Single-run evidence 不得膨胀成 project-level claim。多 run、多 split、多 seed、多 baseline 证据必须可审计。
- Tests 必须 deterministic，不能依赖 live network、paid LLM calls、GPU、Docker 可用性或外部 benchmark 在线可用性。
- 真实 evidence 可以通过 repository-local frozen snapshot、cached connector、imported artifact、adapter cache、deterministic local execution 或 deterministic replay 进入系统，但 provenance 必须完整。
- 不要为了让 demo 通过而隐藏 uncertainty。Literature 或 experiment uncertainty 必须作为 risk、limitation、kill criterion 或 required follow-up 表示。

测试节奏
========

- 小改动优先跑窄 pytest target、`python -m py_compile`、`git diff --check`。
- 大改动或累计 5 到 6 个工作块后，再跑完整后端测试：`cd backend && ../.venv/bin/pytest -q`。
- API/schema/types 变更后跑：`cd frontend && npm run build`。
- Operator Console 或浏览器工作流变更后，再考虑 E2E。
- 每轮最终收口前至少跑 `git diff --check`。
- 不要让 tests 依赖 live network、paid LLM、GPU、Docker daemon、外部 benchmark 在线可用性。

固定审计步骤
============

每一轮开始都必须先做：

1. `git status --short --branch`
2. `git log --oneline -n 8`
3. 阅读并审计当前目标涉及的关键文件。
4. 审计结论必须进入代码产物、evaluation artifact、readiness report、docs 或 tests，不能只写在聊天回复里。

下一轮 Goal 2B 的最小必读文件
=============================

- `backend/services/autoresearch/domain_router.py`
- `backend/services/autoresearch/evaluation_cases.py`
- `backend/services/autoresearch/idea_brief.py`
- `backend/services/autoresearch/experiment_factory.py`
- `backend/services/autoresearch/benchmarks.py`
- `backend/services/autoresearch/literature_scout.py`
- `backend/services/autoresearch/literature_connectors.py`
- `backend/services/autoresearch/project_paper_orchestrator.py`
- `backend/services/autoresearch/console.py`
- `backend/services/autoresearch/repository.py`
- `backend/api/autoresearch.py`
- `backend/schemas/autoresearch.py`
- `frontend/src/api/types.ts`
- `frontend/src/api/client.ts`
- `backend/tests/test_autoresearch_regressions.py`
- `docs/api-reference.md`
- `docs/claim-evidence-vertical-loop.md`
- `docs/goal.md`

注意：

- `backend/services/autoresearch/hypothesis_bank.py` 和 `backend/services/autoresearch/direction_selector.py` 目前不存在；相关逻辑仍内聚在 `idea_brief.py`。
- 如果下一轮需要拆模块，可以拆，但不是必须。优先让 evidence chain 和 package readiness 变强。

下一轮默认目标：Goal 2B - Domain Evidence And Review Package Loop
=================================================================

下一轮默认执行 Goal 2B。不要直接跳到 Goal 3 或 Goal 4，除非用户明确改目标。

Goal 2B 的核心目标
------------------

在 Goal 2A 的受控 domain routing 基础上，把 supported domains 推进到可审计的 domain evidence loop：

idea/domain -> literature strategy -> benchmark resolver -> experiment protocol -> deterministic execution/import replay -> evidence ledger -> project package/readiness -> evaluation trace

最低目标不是 final publish，而是：

- claim-evidence generalized idea 继续兼容 Goal 1 强证据路径；
- 至少一个新 domain（优先 `rag_citation_faithfulness`）可以从 user idea 生成 review-ready package，或者输出 concrete blockers；
- 另一个新 domain（`lightweight_ml_nlp_benchmark`）至少达到 deterministic execution/import replay + evidence ledger + package/readiness blockers；
- unsupported domain 仍然全链路 blocked 且可审计；
- 所有 fixture/toy/local smoke evidence 都被明确标成 non-final / review-only / engineering validation evidence。

Goal 2B Phase 4: Literature Strategy Per Domain
-----------------------------------------------

实现内容：

- 将 domain template 的 `literature_query_plan` 变成可执行的 per-domain literature strategy。
- 每个 supported domain 至少定义：
  - query strings；
  - required source classes；
  - minimum real-source count；
  - related-system coverage expectations；
  - novelty risk extraction；
  - known method extraction；
  - known dataset extraction；
  - known metric extraction；
  - known SOTA / reported-results extraction；
  - fixture-only limitation policy；
  - final-publish literature blockers。
- 复用 cached/imported arXiv、Semantic Scholar、Crossref connectors。
- Tests 必须使用 deterministic cache/fixtures，不能依赖 live network。
- Literature evidence 必须进入：
  - research brief / scouted brief；
  - literature support index；
  - related work section material；
  - novelty/gap risk report；
  - readiness blockers/followups；
  - evaluation trace；
  - Operator Console project status。
- Fixture-only literature 必须阻断 novelty/final-publish claims，不能支撑 broad novelty。
- Missing related work 必须变成 limitation/follow-up，不能伪造 novelty。

建议代码落点：

- `backend/services/autoresearch/literature_scout.py`
- `backend/services/autoresearch/literature_connectors.py`
- `backend/services/autoresearch/domain_router.py`
- `backend/services/autoresearch/project_paper_orchestrator.py`
- `backend/services/autoresearch/evaluation_cases.py`
- `backend/schemas/autoresearch.py`
- `frontend/src/api/types.ts`
- `docs/api-reference.md`

测试要求：

- Supported domain with cached connector data gets at least two source types when cache exists。
- Fixture-only literature produces explicit final-publish blocker。
- Literature support index records source type, cache/fingerprint identity, related-system coverage, known methods/datasets/metrics/SOTA。
- RAG/citation literature strategy searches citation faithfulness / attribution / RAG grounding。
- Lightweight ML/NLP literature strategy searches lightweight benchmark / deterministic local metrics / text classification baselines。
- Missing related-system coverage becomes limitation/follow-up。

Goal 2B Phase 5: Benchmark Resolver Per Domain
----------------------------------------------

实现内容：

- 为每个 supported domain 提供 structured benchmark resolver result。
- Resolver result 至少包含：
  - resolver id；
  - domain id；
  - benchmark name；
  - task family；
  - source class；
  - source locator；
  - dataset id；
  - revision；
  - license；
  - source fingerprint；
  - sample count；
  - train/test split counts；
  - label/query/document/evidence schema coverage；
  - source observation coverage；
  - benchmark provenance completeness；
  - publication-grade eligibility；
  - final-candidate eligibility；
  - source-independence audit；
  - blockers；
  - limitations；
  - required followups；
  - kill criteria。
- Resolver must return a structured blocked result for unsupported or incomplete benchmark requests instead of throwing an unauditable exception。
- Claim-evidence resolver must reuse Goal 1 repository-local SciFact verification/retrieval frozen snapshots where appropriate。
- RAG/citation resolver may start with repository-local deterministic review fixture or imported replay, but must carry explicit non-final blockers unless real multi-source citation-faithfulness provenance exists。
- Lightweight ML/NLP resolver may start with deterministic local text/tabular fixture or imported replay, but must carry explicit non-final blockers unless real/imported benchmark provenance and scale exist。
- Resolver result must propagate to:
  - experiment factory plan；
  - evidence ledger；
  - benchmark card / provenance manifest；
  - project readiness report；
  - offline publication case；
  - Operator Console；
  - evaluation trace；
  - API/schema/frontend types。

建议代码落点：

- Prefer adding a focused helper, for example `backend/services/autoresearch/domain_benchmarks.py`, if existing `benchmarks.py` becomes too broad.
- Keep adapter-specific parsing in `benchmarks.py` if that matches current patterns。
- Keep persistence through repository helpers。

测试要求：

- Claim-evidence resolver returns Goal 1 frozen snapshot metadata and stays compatible with existing final-candidate blockers。
- RAG/citation resolver returns deterministic fixture/imported source with explicit non-final blockers unless real provenance exists。
- Lightweight resolver returns deterministic local/imported source with explicit non-final blockers unless real provenance exists。
- Missing benchmark resolver returns structured blocker and does not generate experiment outputs。
- Benchmark blockers propagate to project package/readiness/console/evaluation trace。
- Resolver never marks fixture/toy/source-less benchmark as publication-grade。

Goal 2B Phase 6: Experiment Protocol And Execution Adapter
---------------------------------------------------------

实现内容：

- 每个 supported domain 定义 experiment protocol：
  - protocol id；
  - domain id；
  - method/baseline ladder；
  - metric schema；
  - expected outputs；
  - runtime contract；
  - deterministic execution route；
  - import replay route；
  - evidence ledger schema；
  - negative evidence categories；
  - repair routing policy；
  - readiness blockers；
  - final-publish limitations。
- Claim-evidence domain should keep reusing Goal 1 execution/import path。
- RAG/citation domain initial execution can be deterministic citation matching / citation support scoring / abstention metrics over a repository-local fixture/imported replay。
- Lightweight ML/NLP domain initial execution can be deterministic metric computation over local fixture/imported predictions。
- Each domain result artifact must include:
  - method outputs；
  - metrics；
  - evidence ledger；
  - negative evidence；
  - execution profile；
  - environment manifest；
  - benchmark resolver ref；
  - protocol id；
  - deterministic fingerprint。
- Missing expected output must be blocked。
- Runtime failure must be classified and routed to repair。
- Metric schema mismatch must be blocked。

建议代码落点：

- `backend/services/autoresearch/experiment_factory.py`
- `backend/services/autoresearch/benchmarks.py`
- optional new helper `backend/services/autoresearch/domain_protocols.py`
- `backend/services/autoresearch/project_paper_orchestrator.py`
- `backend/tests/test_autoresearch_regressions.py`

测试要求：

- Each supported domain can execute or import replay deterministically, or returns a concrete blocker for missing benchmark/protocol。
- RAG/citation execution records citation support / unsupported citation / abstention style evidence。
- Lightweight execution records accuracy / macro F1 / baseline comparison evidence。
- Missing expected output yields blocked repair action。
- Runtime failure yields runtime-failure classification。
- Metric schema mismatch yields blocked readiness。
- Evidence ledger enters package and readiness。

Goal 2B Phase 7: Generalized Project Paper Package
--------------------------------------------------

实现内容：

- Project paper orchestrator should consume domain package context, not only fixed claim-evidence assumptions。
- Domain package context should include:
  - domain decision；
  - domain template；
  - literature strategy/result；
  - benchmark resolver result；
  - experiment protocol；
  - execution/import replay status；
  - evidence ledger refs；
  - negative evidence refs；
  - readiness policy；
  - claim ceiling；
  - blockers/followups/kill criteria。
- Manuscript sections remain evidence-constrained:
  - Abstract；
  - Introduction；
  - Related Work；
  - Research Question；
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
- Domain-specific subsections may be added, but core evidence sections must not be removed。
- Review/revision/rereview must read domain-specific blockers and repair outputs。
- Package manifest must include domain metadata and domain readiness policy。
- Claim ceiling remains constrained by evidence quality。
- Unsupported domain must produce no fake manuscript claims。

测试要求：

- Claim-evidence generalized idea produces review-ready package compatible with Goal 1 expectations。
- At least one new domain produces a review-ready package or concrete package blockers。
- Unsupported domain produces no fake manuscript claims or package claims。
- Package manifest includes domain id, domain template version, benchmark resolver output, experiment protocol id。
- Readiness report includes domain-specific blockers/followups/kill criteria。
- Final publish remains false for fixture/toy/new-domain smoke evidence unless real evidence requirements are met。

Goal 2B Phase 8: API / Operator Console / Frontend Surface
---------------------------------------------------------

Goal 2A already exposes basic domain routing fields. Goal 2B should extend surfaces only where backend capability exists。

Implement or update API/schema/types/docs for:

- domain decision；
- domain template version；
- literature strategy/result；
- benchmark resolver result；
- experiment protocol id；
- unsupported-domain blockers；
- domain-specific readiness status；
- package paths；
- claim ceiling；
- review-ready vs final-publish-ready status；
- required followups；
- kill criteria。

Operator Console should show:

- routed domain；
- confidence and matched signals；
- unsupported reason；
- literature status；
- benchmark resolver status；
- experiment protocol/execution status；
- evidence ledger completeness；
- review bundle vs final publish bundle；
- blockers/followups/kill criteria。

测试要求：

- API read models include new fields。
- Frontend `npm run build` passes after type changes。
- Operator Console test covers:
  - supported ready/review path；
  - fixture-only blocker path；
  - unsupported blocked path。

Goal 2B Phase 9: Evaluation Cases And Regression Coverage
---------------------------------------------------------

Add or update deterministic evaluation cases:

- `claim_evidence_generalized_idea`
- `rag_citation_faithfulness_review_case`
- `lightweight_ml_nlp_review_case`
- `unsupported_domain_case`

Each case must record:

- input idea；
- domain decision；
- domain template id/version；
- literature strategy；
- literature source counts and fixture-only blockers；
- benchmark resolver result；
- experiment protocol id；
- execution/import replay status；
- evidence ledger status；
- negative evidence status；
- package readiness or blocker；
- final publish readiness；
- required followups；
- kill criteria。

Testing requirements:

- Cases are deterministic。
- No live network。
- No paid LLM。
- No GPU。
- No Docker requirement。
- Evaluation trace makes it obvious why a package is review-ready, final-publish-blocked, or fully blocked。

Goal 2B completion criteria
===========================

Goal 2B is complete only when all of the following are true:

- Claim-evidence generalized idea still routes through Goal 1-compatible evidence path。
- RAG/citation domain has per-domain literature strategy, benchmark resolver, experiment protocol, execution/import replay evidence, and package/readiness output or concrete blockers。
- Lightweight ML/NLP domain has per-domain literature strategy, benchmark resolver, experiment protocol, execution/import replay evidence, and package/readiness output or concrete blockers。
- At least one new domain can produce a review-ready package OR a fully auditable blocker package with no fake claims。
- Unsupported ideas are safely blocked and auditable through API, console, project readiness, evaluation trace, and repository persistence。
- Fixture/toy/local smoke evidence never becomes publication-grade evidence。
- Benchmark/literature/execution blockers propagate to package/readiness/console/evaluation trace。
- Deterministic regression tests cover supported domains and unsupported domains。
- If schema/API/types changed, docs and frontend types are updated and `cd frontend && npm run build` passes。
- `git diff --check` passes。
- Before marking Goal 2B complete, run `cd backend && ../.venv/bin/pytest -q` unless the user explicitly asks to stop earlier。

Goal 3: Real Experiment Backend And Repair Productionization
===========================================================

Do not start Goal 3 until Goal 2B is complete, unless the user explicitly redirects。

目标
----

把 experiment execution 从 deterministic replay / narrow local execution 推进到 production-grade local/Docker/bridge execution backend。

Required capabilities:

- Materialize execution plans into:
  - local command jobs；
  - Docker jobs when available；
  - external bridge/import jobs；
  - deterministic replay jobs。
- 每个 job 必须记录:
  - command；
  - environment；
  - dependency manifest；
  - runtime contract；
  - expected outputs；
  - actual outputs；
  - stdout/stderr refs if available；
  - failure classification；
  - repair recommendation；
  - lineage refs。
- Repair classifier 必须覆盖:
  - missing baseline；
  - missing ablation；
  - insufficient statistics；
  - runtime failure；
  - missing output；
  - bad metric schema；
  - benchmark mismatch；
  - environment mismatch。
- Operator Console 必须支持:
  - inspect jobs；
  - approve/reject expensive job；
  - resume；
  - view budgets；
  - view blockers；
  - view output artifact lineage。

Goal 3 Phase 1: Execution Plan Materialization
----------------------------------------------

实现内容：

- 将 experiment factory / domain protocol 输出 materialize 成 typed execution jobs。
- 每个 job 至少包含：
  - job id；
  - project/run id；
  - domain id；
  - protocol id；
  - benchmark resolver ref；
  - method/baseline ref；
  - command or replay/import spec；
  - expected input artifacts；
  - expected output artifacts；
  - metric schema；
  - runtime contract；
  - environment requirements；
  - budget class；
  - approval requirement；
  - lineage parent refs。
- Job planner 必须区分：
  - deterministic replay job；
  - repository-local command job；
  - Docker job；
  - external bridge/import job。
- Docker unavailable、external bridge unavailable、budget not approved 必须成为 structured blocker，而不是 silent skip。

测试要求：

- Factory plan 可以生成 typed replay/local/import job。
- Unsupported domain 或 missing protocol 不生成 fake job。
- Docker unavailable produces safe blocker。
- Budget/approval-gated job 不会未授权执行。
- Job carries benchmark/protocol/evidence lineage refs。

Goal 3 Phase 2: Local And Replay Execution Runtime
-------------------------------------------------

实现内容：

- 实现 deterministic local/replay runtime：
  - resolve inputs；
  - run command or replay/import adapter；
  - collect stdout/stderr refs when applicable；
  - validate output artifact existence；
  - validate metric schema；
  - compute deterministic fingerprint；
  - persist execution profile；
  - persist environment manifest。
- Runtime 不得把 missing outputs、bad JSON、bad metric schema 当作成功。
- Imported replay 必须记录 source package、hash、import timestamp、schema version 和 provenance。

测试要求：

- Local command success。
- Local runtime failure。
- Missing output。
- Bad metric schema。
- Imported replay success。
- Re-running deterministic replay produces stable fingerprint。
- Execution results persist through repository helpers。

Goal 3 Phase 3: Evidence Ledger Mapping
---------------------------------------

实现内容：

- 将 execution result 映射回：
  - run-level evidence ledger；
  - negative evidence；
  - benchmark card；
  - environment manifest；
  - project readiness report；
  - package manifest。
- Evidence mapping 必须保留：
  - metric values；
  - sample/split counts；
  - baseline comparisons；
  - ablation status；
  - statistical sufficiency；
  - failure classifications；
  - output artifact refs；
  - lineage parent refs。
- Single-run 或 fixture evidence 必须保留 claim ceiling，不得自动升级成 project-level claim。

测试要求：

- Successful job updates evidence ledger and readiness。
- Failed job updates negative evidence and readiness blocker。
- Missing baseline / missing ablation / insufficient statistics enter repair queue。
- Artifact refs remain reconstructable from package manifest。

Goal 3 Phase 4: Repair Classifier And Bounded Replanning
--------------------------------------------------------

实现内容：

- Repair classifier 覆盖：
  - missing baseline；
  - missing ablation；
  - insufficient statistics；
  - runtime failure；
  - missing output；
  - bad metric schema；
  - benchmark mismatch；
  - environment mismatch；
  - budget/approval blocker；
  - unsupported execution backend。
- Repair actions 必须分清：
  - can execute now；
  - requires approval；
  - requires imported artifact；
  - requires benchmark/protocol change；
  - blocked by deterministic offline policy；
  - should downgrade claim。
- Bounded replanning 必须避免无限循环。每个 repair loop 需要 max attempts、reason、terminal status。

测试要求：

- 每类 failure 有 deterministic repair classification。
- Evidence-producing repair 只有在真实 artifact 产生或导入后才能 completed。
- Offline policy 可以正确阻断需要外部 real-world evidence 的 repair。
- Repair loop 达到上限后保留 blocker 和 negative evidence。

Goal 3 Phase 5: Operator Controls And Resumability
--------------------------------------------------

实现内容：

- Operator Console/API 只暴露必要 controls：
  - list jobs；
  - inspect job status；
  - approve/reject expensive job；
  - resume paused/failed job when policy allows；
  - view budget and runtime contract；
  - view output artifacts and lineage；
  - view repair queue。
- Resumability 必须从 persisted state 恢复，不依赖内存状态。
- Resume 不能覆盖已有 evidence、negative evidence 或 lineage。

测试要求：

- Job list/read API includes status and blockers。
- Approval required job remains pending until approved。
- Resume preserves prior artifacts。
- Rejected job becomes explicit blocker。
- Console status distinguishes pending/running/succeeded/failed/blocked/needs approval。

Goal 3 tests:

- local execution success；
- local runtime failure；
- missing output；
- imported replay success；
- Docker unavailable safe fallback；
- repair action transitions；
- artifact lineage preserved；
- operator approval required for expensive job；
- resumed job preserves lineage and readiness blockers。

Goal 4: Toward Submission-Ready Research System
===============================================

Do not start Goal 4 until Goal 2B is complete and at least one Goal 3 execution path is stable, unless the user explicitly redirects。

目标
----

让 ScholarFlow 能把一个 user idea 自动推进到 submission-ready package，并且在 evidence 足够时让 `final_publish_ready=true`。

Requirements:

- 至少一个 case 达到 `final_publish_ready=true`，且该状态由真实 evidence 支撑。
- 至少一个 controlled-domain idea 从用户输入开始生成 submission-ready package。
- Manuscript source package 能通过 local compile path，或明确记录 compiler blocker 且 source package 完整。
- Reviewer response / rebuttal package 可生成。
- Reproducibility checklist 与 artifact package 完整。
- Publication manifest 可作为 submission archive index 使用。
- System evaluation 可以产出 ScholarFlow 自身 architecture / case-study / failure-analysis paper material。

Goal 4 Phase 1: Project-Level Manuscript Compiler V2
----------------------------------------------------

实现内容：

- 从 brief、literature strategy/result、hypothesis bank、selected direction、selected runs、meta-analysis、conclusions、reviewer results、claim evidence 和 domain readiness context 生成 project-level manuscript。
- 支持至少三类 candidate：
  - technical report；
  - workshop case-study paper；
  - conference-style candidate package。
- Compiler 必须 enforce：
  - every core claim has evidence refs；
  - unsupported claims are removed or downgraded；
  - fixture/toy evidence is labeled as engineering validation；
  - negative evidence remains visible；
  - limitations and kill criteria survive revisions。
- Manuscript source package 必须包含 references、figures/tables metadata、artifact index、compile manifest。

测试要求：

- Unsupported claim is downgraded or blocked。
- Negative evidence appears in generated manuscript package。
- Claim-evidence index covers all core claims。
- Compile blocker produces complete source package plus explicit blocker。

Goal 4 Phase 2: Autonomous Revision Loop
----------------------------------------

实现内容：

- 将 reviewer simulator findings 转换为 bounded revision plan：
  - manuscript text revision；
  - claim downgrade；
  - experiment repair；
  - literature follow-up；
  - benchmark/provenance follow-up；
  - no-action with rationale。
- Revision loop 必须记录：
  - finding id；
  - action type；
  - evidence requirement；
  - produced artifact refs；
  - unresolved blocker；
  - reviewer-response draft。
- Re-review 必须读取修订后的 manuscript/package，不得只复用旧评分。

测试要求：

- Reviewer finding creates bounded revision action。
- Unsupported claim finding causes claim downgrade or blocker。
- Missing experiment evidence finding creates repair action, not fake evidence。
- Re-review reflects revised artifacts。
- Revision loop stops with clear terminal status。

Goal 4 Phase 3: Submission Package And Reproducibility Archive
-------------------------------------------------------------

实现内容：

- 生成 final submission package：
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
- Package manifest 必须足够重建 archive 内容。
- 如果 package 不能 compile 或 archive 不完整，必须 blocked，而不是标记 ready。

测试要求：

- Submission archive can be reconstructed from manifest。
- Reproducibility checklist includes commands, environment, artifact hashes, datasets, metrics, seeds/splits when applicable。
- Reviewer response maps finding-by-finding。
- Missing supplemental artifact blocks submission。

Goal 4 Phase 4: Final Publish Decision And Publish Gate
------------------------------------------------------

实现内容：

- `final_publish_ready=true` 只能在 evidence 满足 domain-specific publish policy 时出现。
- Gate 必须检查：
  - literature/source sufficiency；
  - benchmark provenance and independence；
  - experiment evidence completeness；
  - statistics/multi-run/multi-split sufficiency where required；
  - negative evidence retention；
  - claim-evidence coverage；
  - reproducibility package completeness；
  - reviewer/revision status；
  - unresolved blockers。
- 如果只达到 review/workshop/case-study 级别，必须保持 final false，并给出 next required evidence。

测试要求：

- Review-ready package does not become final-publish-ready。
- Final-publish-ready case has no hidden unresolved blockers。
- Final gate fails when negative evidence is missing。
- Final gate fails when benchmark/source independence is insufficient unless domain policy explicitly accepts substitute and records rationale。

Goal 4 Phase 5: Real End-To-End Evaluation And System Paper Material
--------------------------------------------------------------------

实现内容：

- 让 P14 evaluation cases 成为可执行 end-to-end regression/evaluation suite。
- 每个 case 输出：
  - full trace；
  - evidence ledger summary；
  - blocker/readiness timeline；
  - repair/revision timeline；
  - package manifest；
  - failure analysis。
- 产出 ScholarFlow 自身 architecture / case-study / failure-analysis paper material：
  - system architecture；
  - evidence constraints；
  - case studies；
  - failure modes；
  - limitations；
  - reproducibility package。

测试要求：

- E2E evaluation is deterministic。
- Evaluation cases do not require live network、paid LLM、GPU、Docker daemon。
- System paper material only claims what evaluation evidence supports。
- Failure analysis includes blocked and negative cases, not only successful demos。

Goal 4 tests:

- final-publish-ready case has no hidden package plumbing gaps；
- final-publish-ready case has independent benchmark/source evidence or explicitly sufficient domain-specific substitute；
- reviewer response package includes finding-by-finding response；
- reproducibility package includes artifact hashes, commands, environment, and lineage；
- submission archive can be reconstructed from publication manifest；
- negative evidence remains visible even when final publish is ready。

AGENTS.md 和 skills
===================

AGENTS.md should stay aligned with this file at the high-level roadmap/current-state level。

Current decision:

- Update AGENTS.md when it would mislead the next run about completed phases or active priorities。
- Do not add a new skill yet。

Reason:

- Goal 2B is still project-specific engineering work; the repo-local instructions and this goal file are enough。
- Consider a repository-local skill only after domain package verification and publication-case audit become a repeated stable workflow across several turns。

下一轮执行建议
==============

- 默认执行 Goal 2B。
- 优先顺序:
  1. Literature Strategy Per Domain。
  2. Benchmark Resolver Per Domain。
  3. Experiment Protocol And Execution Adapter。
  4. Generalized Project Paper Package。
  5. API/Console/Evaluation surface only as needed by the backend capability。
- 不要一次性做 Goal 3 或 Goal 4。
- 不要把 RAG/citation 或 lightweight ML/NLP fixture evidence 宣称为 publication-grade。
- 每完成一个实质子阶段，提交前确认 blockers、limitations、followups、kill criteria 都进入 artifact 或 tests。
- 如果工作量过大，下一轮至少完成 Phase 4 和 Phase 5，并让 Phase 6 的 protocol result 能给出 structured blocker。

下一轮可直接使用的 /goal prompt
==============================

下面这段可以直接复制到新对话中：

```
接下来请使用 /goal 功能执行 ScholarFlow 的下一阶段目标。

目标：实现 docs/goal.md 中的 Goal 2B - Domain Evidence And Review Package Loop。

优先完成：
1. Goal 2B Phase 4: Literature Strategy Per Domain
2. Goal 2B Phase 5: Benchmark Resolver Per Domain
3. Goal 2B Phase 6: Experiment Protocol And Execution Adapter
4. 如果前 3 项稳定，再推进 Phase 7: Generalized Project Paper Package
5. 必要时同步 Phase 8/9 的 API、Operator Console、evaluation trace、frontend types、docs/tests

开始前请先执行并审计：
- git status --short --branch
- git log --oneline -n 8
- 阅读 docs/goal.md
- 阅读 docs/goal.md 中 “下一轮 Goal 2B 的最小必读文件”

当前基线：
- Goal 1 已通过 commit d53e5a6 完成，不要重做。
- Goal 2A 已通过 commit dda8dc6 完成，不要重做。
- 默认分支是 master。

核心要求：
- 全程用中文回复。
- 不要削弱 publish gates、claim-evidence ledger、artifact lineage、repair safety、negative evidence、readiness blockers。
- Unsupported domain 必须产生可审计 blocker，不能伪造 toy experiment outputs。
- Fixture/toy/local smoke evidence 不能宣称为 publication-grade。
- Literature、benchmark、experiment、statistics、negative evidence 和 manuscript claims 必须能通过 artifact lineage 追溯。
- Tests 必须 deterministic，不能依赖 live network、paid LLM、GPU、Docker daemon、外部 benchmark 在线可用性。

Goal 2B 验收标准：
- claim-evidence generalized idea 继续兼容 Goal 1 evidence path。
- RAG/citation domain 有 per-domain literature strategy、benchmark resolver、experiment protocol、execution/import replay evidence，并进入 package/readiness/evaluation trace，或者输出 concrete blockers。
- Lightweight ML/NLP domain 有 per-domain literature strategy、benchmark resolver、experiment protocol、execution/import replay evidence，并进入 package/readiness/evaluation trace，或者输出 concrete blockers。
- 至少一个新 domain 生成 review-ready package，或生成完整可审计 blocker package 且没有 fake claims。
- Unsupported domain 仍通过 API、console、project readiness、evaluation trace、repository persistence 全链路 blocked。
- Benchmark/literature/execution blockers propagate 到 package/readiness/console/evaluation trace。
- 新增或更新 deterministic regression tests。
- 如涉及 API/schema/types，更新 backend schema、frontend types/client、docs，并跑 frontend build。

测试节奏：
- 小步先跑 py_compile、窄 pytest、git diff --check。
- API/schema/types 变更后跑 cd frontend && npm run build。
- Goal 收口前按实际改动跑 cd backend && ../.venv/bin/pytest -q。

完成后：
- 更新 docs/api-reference.md 和 docs/claim-evidence-vertical-loop.md 中相关说明。
- 如 AGENTS.md 当前状态/路线图会误导下一轮，也做最小同步。
- 提交并 push scoped commit。
```

最终验收
========

- 只有当当前 evidence 能逐项证明目标完成，才可以标记 goal complete。
- 如果 evidence 不足，继续推进或输出具体 blocker。
- 永远不要把 review-ready package 说成 final-publish package。
- 永远不要通过降低 publish gate、删除 negative evidence、跳过 lineage 或伪造 provenance 来让测试通过。
