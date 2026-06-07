ScholarFlow 下一阶段目标：Generalized Idea-To-Paper Runner And Productionized Execution

当前状态
========

ScholarFlow 已完成两个关键里程碑：

1. Offline Publication-Grade Paper Case And Submission Package V3
   - 最新已知基线提交：`0aec946 Complete offline publication case package`
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
   - 已验证：
     - `cd backend && ../.venv/bin/pytest -q` 通过：`243 passed, 2 warnings`
     - `cd frontend && npm run build` 通过
     - `git diff --check` 通过

下一轮对话默认不要重做 Goal 1。除非测试回归或新改动打破 Goal 1 artifact，否则只把 Goal 1 当作已完成的 evidence-constrained foundation。

长期目标
========

用户给出一个 idea，ScholarFlow 自动完成科研和论文发表链路：

idea -> research brief -> literature/gap validation -> hypothesis bank -> selected direction -> experiment protocol -> execution/repair -> evidence ledger -> project conclusions -> paper draft -> reviewer simulation -> revision loop -> submission package -> final publish decision

下一阶段的目标不是继续加 publish gate，也不是美化 demo。目标是让系统从固定 claim-evidence vertical 扩展到受控开放域 idea-to-paper runner，并逐步接入更真实的 experiment backend。

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

固定审计步骤
============

每一轮开始都必须先做：

1. `git status --short --branch`
2. `git log --oneline -n 8`
3. 阅读并审计当前目标涉及的关键文件。
4. 审计结论必须进入代码产物、evaluation artifact、readiness report、docs 或 tests，不能只写在聊天回复里。

Goal 2 的最小必读文件：

- `backend/services/autoresearch/evaluation_cases.py`
- `backend/services/autoresearch/idea_brief.py`
- `backend/services/autoresearch/hypothesis_bank.py`
- `backend/services/autoresearch/direction_selector.py`
- `backend/services/autoresearch/experiment_factory.py`
- `backend/services/autoresearch/benchmarks.py`
- `backend/services/autoresearch/literature_scout.py`
- `backend/services/autoresearch/literature_connectors.py`
- `backend/services/autoresearch/project_paper_orchestrator.py`
- `backend/services/autoresearch/console.py`
- `backend/schemas/autoresearch.py`
- `frontend/src/api/types.ts`
- `backend/tests/test_autoresearch_regressions.py`
- `docs/api-reference.md`
- `docs/claim-evidence-vertical-loop.md`
- `docs/goal.md`

Goal 2: Generalized Idea-To-Paper Runner For Controlled Domains
===============================================================

下一轮默认执行 Goal 2。不要尝试一次性完成 Goal 2、Goal 3、Goal 4。Goal 2 的核心目标是把固定 claim-evidence publication case 泛化成受控开放域 idea-to-paper runner。

目标
----

用户输入一个 idea，系统自动完成：

idea classification -> domain routing -> research brief -> literature strategy -> benchmark resolver -> experiment protocol -> deterministic execution/import replay -> evidence ledger -> project paper package -> reviewer/revision/rereview -> readiness decision

先支持 2 到 3 个 controlled domains，不追求所有科研领域。

Goal 2 支持域
-------------

必须支持：

1. `claim_evidence_retrieval`
   - 主题：claim-evidence retrieval / verification for scientific writing agents
   - 复用 Goal 1 的强 evidence-constrained package path。
   - 目标：任意接近该领域的用户 idea 能路由到已完成 vertical，而不是只能运行硬编码 case。

2. `rag_citation_faithfulness`
   - 主题：RAG evaluation / citation faithfulness for knowledge-intensive QA
   - 初始证据可以使用 repository-local frozen/imported toy-sized review benchmark，但不能 final publish。
   - 必须明确 blocker：缺少 real multi-source benchmark 或 citation-faithfulness benchmark provenance 时只能 review-ready 或 blocked。

3. `lightweight_ml_nlp_benchmark`
   - 主题：lightweight ML/NLP benchmark comparison with deterministic local metrics
   - 初始可使用 deterministic local tabular/text classification fixture 或 imported replay。
   - 必须避免把 fixture/local smoke test 宣称为 publication-grade。

必须安全阻断：

- Unsupported domain；
- 需要 live network、paid LLM、GPU、Docker-only benchmark、外部 benchmark 在线可用性才可运行的 idea；
- 无法匹配 benchmark resolver 或 metric schema 的 idea；
- 要求 broad final-publish claim 但 evidence 只有 fixture/toy/local smoke test 的 idea。

Goal 2 Phase 1: Domain Router And Audit Surface
-----------------------------------------------

实现内容：

- 新增 domain routing service 或扩展现有 idea-to-brief path。
- 输入：user idea、可选 domain hint、budget/policy hints。
- 输出 structured domain decision：
  - `domain_id`
  - `domain_label`
  - `confidence`
  - `matched_signals`
  - `unsupported_reason`
  - `required_capabilities`
  - `evidence_policy`
  - `publish_readiness_policy`
  - `default_blockers`
- Domain router 不能只靠宽泛关键词胡乱匹配。必须能解释为什么匹配。
- Unsupported idea 必须产生 explicit blocker，不得自动降级成 unrelated toy case。
- 将 domain decision 写入：
  - evaluation trace；
  - project package / offline case artifact；
  - readiness report；
  - Operator Console publication/project status；
  - API response schema；
  - tests。

测试要求：

- claim-evidence idea routes to `claim_evidence_retrieval`。
- citation/RAG/citation-faithfulness idea routes to `rag_citation_faithfulness`。
- lightweight benchmark idea routes to `lightweight_ml_nlp_benchmark`。
- unrelated domain idea returns unsupported domain blocker。
- Route decision includes matched signals and evidence policy。
- Unsupported domain does not create fake experiment outputs。

Goal 2 Phase 2: Domain Template Registry
----------------------------------------

实现内容：

- 为每个 supported domain 定义 deterministic template：
  - research brief template；
  - literature query plan；
  - benchmark resolver policy；
  - method/baseline ladder；
  - metric schema；
  - experiment factory protocol；
  - evidence ledger schema；
  - paper section requirements；
  - publish readiness constraints；
  - negative evidence taxonomy；
  - required package artifacts。
- Template 应该是 structured Python/Pydantic data 或 local service helper，不要散落在字符串拼接里。
- Domain template 需要版本号，例如 `claim_evidence_retrieval_v1`。
- Template 变更必须在 API/types/docs/tests 中可追踪。

测试要求：

- 每个 supported domain 有完整 template。
- Template 缺少 benchmark resolver、metric schema、paper section requirements 时 blocked。
- Claim-evidence domain template 和 Goal 1 artifact path 保持兼容。
- Domain template registry 不允许 duplicate domain id。

Goal 2 Phase 3: Idea To Brief To Hypothesis Automation
------------------------------------------------------

实现内容：

- 用户 idea 进入 domain router 后，自动生成或约束：
  - research brief；
  - literature/gap validation plan；
  - hypothesis bank；
  - direction selector output；
  - selected direction rationale；
  - experiment protocol draft。
- 对 unsupported domain：
  - still create an auditable unsupported-domain record；
  - do not create a fake hypothesis bank；
  - do not create experiment outputs。
- 对 supported domains：
  - hypothesis bank 至少给出 2 到 3 个候选 hypothesis；
  - selected direction 必须说明 evidence prerequisites 和 kill criteria；
  - direction selector 不得把没有 benchmark 的 hypothesis 选成 executable。

测试要求：

- Claim-evidence idea 自动走到 selected direction。
- RAG/citation idea 自动走到 selected direction 或 concrete benchmark blocker。
- Lightweight ML/NLP idea 自动走到 selected direction。
- Unsupported idea 被 blocked，且 blocker 进入 trace/readiness/console。

Goal 2 Phase 4: Literature Strategy Per Domain
----------------------------------------------

实现内容：

- 复用 cached/imported arXiv、Semantic Scholar、Crossref connectors。
- 每个 domain 有 deterministic literature query plan：
  - query strings；
  - required source classes；
  - minimum real-source count；
  - related-system coverage expectations；
  - novelty risk extraction；
  - known method/dataset/metric extraction。
- 不允许 live network 成为测试必要条件。
- Fixture-only literature 只能支持 smoke/review path，不能 support final publish claims。
- Literature evidence 进入：
  - literature support index；
  - related work section；
  - novelty/gap risk report；
  - readiness blockers/followups；
  - evaluation trace。

测试要求：

- At least two connector source types present for supported review-ready domain when cached data exists。
- Fixture-only literature blocks novelty/final-publish claim。
- Literature support index records source type, fingerprint/cache id, related-system coverage, known metrics/datasets/methods。
- Missing related work becomes limitation/follow-up, not fabricated novelty。

Goal 2 Phase 5: Benchmark Resolver Per Domain
---------------------------------------------

实现内容：

- 为每个 supported domain 提供 benchmark resolver：
  - claim-evidence: reuse SciFact verification/retrieval frozen snapshots from Goal 1。
  - RAG/citation faithfulness: add a repository-local deterministic benchmark fixture or imported replay format for citation-faithfulness cases。
  - lightweight ML/NLP: add deterministic local fixture or imported replay benchmark spec。
- Resolver 输出：
  - source class；
  - provenance fields；
  - sample/split counts；
  - schema coverage；
  - source observation coverage；
  - publication-grade eligibility；
  - final-candidate eligibility；
  - source-independence audit；
  - blockers/followups。
- Resolver 不得把 fixture/toy benchmark 标记为 publication-grade。
- Resolver 必须能返回 blocked result，而不是抛出不可审计异常。

测试要求：

- Claim-evidence resolver returns Goal 1 frozen snapshots。
- RAG/citation resolver returns deterministic fixture/imported source with explicit non-final blockers unless real provenance exists。
- Lightweight ML/NLP resolver returns deterministic fixture/imported source with explicit non-final blockers unless real provenance exists。
- Unsupported or missing benchmark returns structured blocker。
- Benchmark blockers propagate to package/readiness/console。

Goal 2 Phase 6: Experiment Protocol And Execution Adapter
--------------------------------------------------------

实现内容：

- 每个 supported domain 定义 experiment protocol：
  - method/baseline ladder；
  - metric schema；
  - expected outputs；
  - runtime contract；
  - deterministic execution/import replay route；
  - negative evidence categories；
  - repair routing policy。
- Claim-evidence domain 复用 Goal 1 execution path。
- RAG/citation domain 初始可实现 deterministic citation matching / citation support scoring / abstention metrics。
- Lightweight ML/NLP domain 初始可实现 deterministic metric computation over local fixture/imported predictions。
- 每个 domain 的 result artifact 必须包含：
  - method outputs；
  - metrics；
  - evidence ledger；
  - negative evidence；
  - execution profile；
  - environment manifest；
  - deterministic fingerprint。

测试要求：

- Each supported domain can execute or import replay deterministically。
- Missing expected output is blocked。
- Runtime failure is classified and routed to repair。
- Metric schema mismatch is blocked。
- Evidence ledger enters package and readiness。

Goal 2 Phase 7: Generalized Project Paper Package
-------------------------------------------------

实现内容：

- Project paper orchestrator 接收 domain package context，而不是只理解 fixed claim-evidence case。
- Manuscript sections remain evidence-constrained：
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
- Domain-specific paper sections can add subsections but cannot remove core evidence sections。
- Review/revision/rereview 必须读取 domain-specific repair outputs。
- Package manifest must include domain metadata and domain readiness policy。
- Claim ceiling remains constrained by evidence quality。

测试要求：

- Claim-evidence generalized idea produces review-ready package compatible with Goal 1 expectations。
- At least one new domain produces a review-ready package or concrete blockers。
- Unsupported domain produces no fake manuscript claims。
- Package manifest includes domain id, domain template version, benchmark resolver output, experiment protocol id。

Goal 2 Phase 8: Operator Console And API Surface
------------------------------------------------

实现内容：

- API/schema/types expose：
  - domain decision；
  - domain template version；
  - benchmark resolver result；
  - experiment protocol id；
  - unsupported-domain blockers；
  - domain-specific readiness status；
  - package paths。
- Operator Console shows：
  - routed domain；
  - confidence and matched signals；
  - unsupported reason；
  - benchmark/literature/execution status；
  - review bundle vs final publish bundle；
  - blockers/followups/kill criteria。
- Frontend types and docs must stay aligned with backend schemas。

测试要求：

- API read models include new fields。
- Frontend `npm run build` passes after types changes。
- Operator Console test covers supported and unsupported domain cases。

Goal 2 Phase 9: Evaluation Cases And Regression Coverage
--------------------------------------------------------

Add or update deterministic evaluation cases:

- `claim_evidence_generalized_idea`
- `rag_citation_faithfulness_review_case`
- `lightweight_ml_nlp_review_case`
- `unsupported_domain_case`

Each case must record:

- input idea；
- domain decision；
- literature strategy；
- benchmark resolver result；
- experiment protocol；
- execution/import replay status；
- evidence ledger status；
- package readiness or blocker；
- final publish readiness；
- required followups；
- kill criteria。

Goal 2 completion criteria:

- At least two controlled domains can run idea-to-package deterministically.
- Unsupported ideas are safely blocked and auditable.
- Claim-evidence generalized idea remains compatible with Goal 1 package guarantees.
- Operator Console/API can show domain routing and package status.
- Tests deterministic, no live network, paid LLM, GPU, or external benchmark online dependency.
- If API/types changed, frontend build passes.
- Full backend pytest passes before marking complete.

Goal 3: Real Experiment Backend And Repair Productionization
===========================================================

Do not start Goal 3 until Goal 2 is complete, unless the user explicitly redirects.

目标
----

把 experiment execution 从 deterministic replay / narrow local execution 推进到 production-grade local/Docker/bridge execution backend。

Required capabilities:

- Materialize execution plans into：
  - local command jobs；
  - Docker jobs when available；
  - external bridge/import jobs；
  - deterministic replay jobs。
- 每个 job 必须记录：
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
- Repair classifier 必须覆盖：
  - missing baseline；
  - missing ablation；
  - insufficient statistics；
  - runtime failure；
  - missing output；
  - bad metric schema；
  - benchmark mismatch；
  - environment mismatch。
- Operator Console 必须支持：
  - inspect jobs；
  - approve/reject expensive job；
  - resume；
  - view budgets；
  - view blockers；
  - view output artifact lineage。

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

Do not start Goal 4 until Goal 2 is complete and at least one Goal 3 execution path is stable, unless the user explicitly redirects.

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

Goal 4 tests:

- final-publish-ready case has no hidden package plumbing gaps；
- final-publish-ready case has independent benchmark/source evidence or explicitly sufficient domain-specific substitute；
- reviewer response package includes finding-by-finding response；
- reproducibility package includes artifact hashes, commands, environment, and lineage；
- submission archive can be reconstructed from publication manifest；
- negative evidence remains visible even when final publish is ready。

AGENTS.md 和 skills
===================

当前不需要更新 AGENTS.md。

原因：

- 现有 AGENTS.md 已经正确约束 repository mission、active roadmap、testing、git workflow 和 safety constraints。
- 下一阶段主要是项目代码实现和 docs/goal.md 驱动，不需要新的全局协作规则。

当前不需要新增 skill。

原因：

- Goal 2 需要先稳定 domain routing / package generation workflow。
- 只有当 publication-case audit、domain routing audit、package verification 在多轮中反复稳定后，才考虑新增 repository-local skill。

下一轮执行建议
==============

- 默认执行 Goal 2。
- 第一轮优先做 Goal 2 Phase 1 到 Phase 3：
  - domain router；
  - domain template registry；
  - idea -> brief -> hypothesis -> selected direction 自动化；
  - unsupported-domain blocker。
- 不要一次性做 Goal 2 到 Goal 4。
- 不要把 RAG/citation 或 lightweight ML/NLP fixture evidence 宣称为 publication-grade。
- 每完成一个实质子阶段，提交前确认 blockers、limitations、followups、kill criteria 都进入 artifact 或 tests。

最终验收
========

- 只有当当前 evidence 能逐项证明目标完成，才可以标记 goal complete。
- 如果 evidence 不足，继续推进或输出具体 blocker。
- 永远不要把 review-ready package 说成 final-publish package。
- 永远不要通过降低 publish gate、删除 negative evidence、跳过 lineage 或伪造 provenance 来让测试通过。
