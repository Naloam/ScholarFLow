# API Reference

This document focuses on the current auto-research API surface.

## Current Auto-Research Endpoints

### `POST /api/projects/{project_id}/auto-research/ideas`

- converts a user idea into a persisted research brief instead of creating a run
- accepts `idea`, optional `domain`, optional `resource_budget`, optional `target_tier`, and flags for `allow_web` / `allow_experiments`
- routes the idea through controlled domain templates for `claim_evidence_retrieval`, `rag_citation_faithfulness`, and `lightweight_ml_nlp_benchmark`
- returns `domain_decision`, `domain_template`, and `domain_blockers` alongside multiple research directions, selection reasoning, feasibility assessment, and kill criteria
- supported-domain briefs also return domain evidence context: `domain_literature_strategy`, `domain_literature_result`, `domain_benchmark_resolver`, `domain_experiment_protocol`, `domain_readiness_status`, `domain_claim_ceiling`, `domain_required_followups`, and `domain_kill_criteria`
- Goal 12 memory is exposed only as discovery context: briefs may include `memory_hints`, `memory_policy_notes`, `memory_required_followups`, and `memory_validation_actions`; memory hints carry source refs/fingerprints/currentness/limitations/reuse requirements, but they never satisfy current-project claim evidence
- `domain_readiness_status` is intentionally conservative: fixture-only literature, review-only benchmarks, toy execution, unsupported routes, or incomplete protocol coverage keep the status at `limited` or `blocked` and constrain the claim ceiling instead of promoting the idea to final-publish evidence
- unsupported domains are persisted as auditable blocked briefs with `status=blocked`, `next_action=blocked`, `allow_experiments=false`, zero generated hypotheses/directions, and explicit blockers; unsupported ideas are not downgraded into unrelated toy outputs

### `GET /api/projects/{project_id}/auto-research/ideas`

- lists persisted idea briefs for the project

### `GET /api/projects/{project_id}/auto-research/ideas/{brief_id}`

- returns a single persisted idea brief
- includes the generated hypothesis bank, selected hypothesis, direction-selection rationale, and rejected directions

### `GET /api/projects/{project_id}/auto-research/ideas/{brief_id}/hypotheses`

- returns the persisted hypothesis bank and selector output for the idea brief
- exposes selector weights across novelty, feasibility, evidence availability, resource cost, and publish potential

### `POST /api/projects/{project_id}/auto-research/ideas/{brief_id}/literature-scout`

- runs cached literature scouting and gap mining for the idea brief
- accepts optional `sources` (`fixture`, `arxiv`, `semantic_scholar`, `crossref`), `limit_per_source`, `cache_enabled`, and `allow_network`
- never enables network access unless the brief was created with `allow_web=true`; `allow_network=false` forces cache/offline-only behavior
- persists `literature_scout` and `gap_miner` back into the brief snapshot
- returns `domain_literature_strategy` and `domain_literature_result` when the brief has a routed domain; the result records source-class counts, source sufficiency policy/readiness, fixture-only status, related-system coverage, known methods/datasets/metrics/SOTA, novelty risks, extraction limitations, final-publish blockers, required follow-ups, kill criteria, and evidence refs
- preserves `next_action=blocked` for domain-blocked briefs instead of unlocking run creation
- returns search queries, structured paper metadata, source/cache statuses, extraction level (`metadata`, `abstract`, or cached `full_text`), extraction status (`limited_metadata`, `metadata_only`, `abstract_only`, or `full_text`), similar-paper risk signals, known baseline/SOTA notes, experimentally testable gap candidates, and whether the idea needs a changed research question or experiment design
- paper metadata includes `source_id`, title/authors/venue/year, abstract/url/doi/arXiv id, `cache_key`, `cache_timestamp`, deterministic `fingerprint`, source query, extraction fields, known methods/datasets/metrics/reported results/SOTA hints, and evidence text
- paper metadata also includes Goal 10 provenance fields: `cache_freshness` (`fresh`, `stale`, `unknown`, or `not_applicable`), `retrieved_at`, `connector_provider`, `source_observation_fingerprint`, `extraction_limitations`, `source_sufficiency_status`, `related_system_coverage`, `contradiction_signals`, and `claim_ceiling`
- connector statuses include cache hit/miss counts, network request counts, paper/error counts, `availability_status`, `unavailable_reason`, `cache_freshness_counts`, `stale_cache_count`, `freshness_policy`, and `availability_blockers`; deterministic cache misses are reported as unavailable source evidence rather than replaced with fake papers
- cached connector payloads may include `full_text`, `full_text_by_paper`, or `full_text_by_title` to enrich method/dataset/metric/result extraction without enabling live network access
- stale cached real connector observations are discovery context only: they do not count toward final-publish source sufficiency, related-system coverage, or fresh novelty/related-work claims until refreshed
- fixture-only literature is review/evaluation support only; it is preserved as a limitation and final-publish blocker instead of supporting broad novelty claims
- Goal 12 memory hints are also returned on `literature_scout` and reflected in `gap_miner.memory_risks` / `gap_miner.memory_required_followups`; stale or negative memory becomes risk/follow-up/kill-criterion guidance, not literature evidence

### `POST /api/projects/{project_id}/auto-research/ideas/{brief_id}/experiment-factory`

- builds a deterministic experiment-factory plan from the selected hypothesis, or from an explicit `hypothesis_id` query param
- returns baseline, candidate-method, ablation, seed, and sweep jobs with commands/configs, inputs, outputs, dependencies, retry policy, resource estimates, and failure-handling guidance
- returns `domain_benchmark_resolver` and `domain_experiment_protocol` for routed domains; these record benchmark provenance/eligibility, schema coverage, deterministic execution or import replay routes, expected outputs, negative-evidence taxonomy, repair routing policy, blockers, limitations, required follow-ups, kill criteria, and evidence refs
- does not execute jobs or require GPU/network access
- returns HTTP 409 for blocked/domain-blocked briefs; service-level factory planning for such briefs produces zero jobs, `toy_backend_supported=false`, and blockers rather than fake experiment outputs

### `POST /api/projects/{project_id}/auto-research/ideas/{brief_id}/run`

- creates and enqueues an auto-research run from the selected hypothesis, or from an explicit `hypothesis_id`
- preserves `brief_id`, `hypothesis_id`, and `direction_selection_reason` on the run snapshot
- accepts optional run budget overrides for `max_rounds`, `candidate_execution_limit`, `queue_priority`, and `execution_profile`
- returns `{ "id": "<run_id>" }`
- returns HTTP 409 for blocked/domain-blocked briefs with the domain decision and blockers in the error detail

### `POST /api/projects/{project_id}/auto-research/run`

- creates a new run
- snapshots the request into run persistence
- enqueues an initial `run` job in the execution plane
- accepts optional `candidate_execution_limit` to cap how many ranked portfolio candidates may actually execute
- accepts optional `queue_priority` (`low`, `normal`, `high`) to influence queue dispatch order
- accepts optional `experiment_bridge` config to hand off attempt execution through the persisted bridge layer instead of executing inline
- when `experiment_bridge.enabled=true`, the initial `run` request now prepares the first bridge handoff synchronously so the response can be followed immediately by bridge inspection
- returns `{ "id": "<run_id>" }`

### `GET /api/projects/{project_id}/auto-research`

- lists persisted auto-research runs for the project

### `POST /api/projects/{project_id}/auto-research/memory/rebuild`

- rebuilds the project-local Goal 12 memory store/index from persisted briefs, literature scouts, runs, evidence ledgers, reviewer findings, runbooks, and attempt ledgers
- writes `memory/memory_store.json` and `memory/memory_index.json` through repository helpers
- memory item types include paper, method, dataset, metric, benchmark, reported result, implementation, negative finding, blocker, project conclusion, reviewer finding, and compliance/release caveat
- every stored item has `memory_id`, schema version, source project/run/branch refs, source artifact ref/fingerprint, extraction timestamp, source date/version, evidence grade, source class, extraction level, currentness, limitations, reuse policy, privacy/retention policy, negative/blocker status, and deterministic text fingerprint
- private/revoked memory is blocked from the persisted usable store; stale/aging/unknown memory is retained only with visible revalidation requirements
- returns extracted/deduped/blocked counts plus deterministic store/index fingerprints; no vector DB, live network, paid embedding, or external service is required

### `POST /api/projects/{project_id}/auto-research/memory/query`

- queries local memory stores across projects as discovery hints, excluding the current project by default
- accepts optional query text plus domain/method/dataset/metric/benchmark/source-project/item-type filters and policy flags for stale/internal/private/revoked material
- returns `hints` labeled with `memory_hint_only=true`, source refs, currentness, limitations, reuse policy, reuse requirements, required current-project validation actions, evidence grade, source class, negative status, matched terms, and relevance score
- blocked/private/revoked/expired memory ids are surfaced in `blocked_memory_ids` instead of being silently treated as reusable support
- query results cannot satisfy claim-evidence matrices, final gates, literature sufficiency, benchmark provenance, or evidence-origin policy; current projects must revalidate into their own artifacts/evidence ledgers

### `GET /api/projects/{project_id}/auto-research/memory/export`

- returns an auditable memory export with source refs/hashes/policy fields preserved
- excludes internal-only/private/revoked material from public-style export behavior

### `POST /api/projects/{project_id}/auto-research/memory/import`

- imports memory items into the project-local store with deterministic dedupe by item type, source project, source fingerprint, and text fingerprint
- skips private/revoked/blocked material and rebuilds the local index after import
- imported memory remains discovery-only and still requires current-project validation before any claim use

### `GET /api/projects/{project_id}/auto-research/{run_id}`

- returns the run snapshot
- includes current top-level program/plan/spec/artifact state when present
- now also includes persisted narrative / paper-pipeline artifacts:
  - `narrative_report_markdown`
  - `claim_evidence_matrix`
  - `paper_plan`
  - `figure_plan`
  - `paper_revision_state`
  - `paper_compile_report`
  - `paper_revision_action_index`
  - `paper_revision_diff`
  - `paper_section_rewrite_index`
  - `paper_latex_source`
  - `paper_bibliography_bib`
  - `paper_sources_manifest`
- `paper_revision_state` now carries focus sections, next revision actions, and checkpoint history for resume-oriented paper improvement
- `paper_revision_action_index` now persists an action-to-section ledger that ties pending and completed revision actions to rewrite packets, section deltas, and current manuscript excerpts
- `paper_revision_diff` now persists section-by-section deltas against the previous revision checkpoint, including resolved action IDs and closed section-local issues
- `paper_section_rewrite_index` now materializes section-level rewrite packets so revision work can resume from per-section drafting inputs instead of only global issue lists
- `paper_sources_manifest` now also declares `expected_outputs` so downstream compile/export steps can consume an explicit output contract instead of inferring it from commands alone
- `paper_compile_report` now snapshots compile readiness, compile-critical source-file coverage, expected outputs, and currently materialized outputs for the persisted paper workspace
- Goal 3 typed experiment-runtime artifacts are returned when present as `experiment_execution_plan`, `experiment_execution_plan_path`, `experiment_execution_result`, and `experiment_execution_result_path`
- today this is still the main read surface for completed runs

### `POST /api/projects/{project_id}/auto-research/{run_id}/experiment-factory`

- builds an executable experiment-factory plan for an existing run
- reuses the run's linked `brief_id` / `hypothesis_id` when available, and falls back to run spec metadata otherwise
- returns the same job contract as the idea-level factory endpoint

### `POST /api/projects/{project_id}/auto-research/{run_id}/experiment-factory/toy-execute`

- executes the deterministic toy factory backend for the run's factory plan
- persists `experiment_factory_plan.json`, `experiment_factory_environment_manifest.json`, `experiment_factory_materialized_jobs.json`, `artifact.json`, `evidence_ledger.json`, and `experiment_factory_repair_plan.json`
- each materialized job records a deterministic execution surrogate (`started_at_step`, `completed_at_step`), a `runtime_contract` with command/dependencies/expected outputs/retry and timeout requirements, output refs, and explicit `failure_classification`
- marks the run `done` and returns the execution plan, environment manifest, materialized jobs, result artifact, evidence ledger, and repair plan
- repair actions distinguish missing baseline evidence, missing ablation evidence, insufficient seed count, and failed rerun needs

### `POST /api/projects/{project_id}/auto-research/{run_id}/experiment-factory/materialize`

- materializes local, Docker, or bridge job handoffs without claiming that experiments have completed
- accepts `executor_mode` (`local`, `docker`, or `bridge`)
- persists the execution plan, environment manifest, materialized planned jobs with runtime contracts and deterministic pending status, and an incomplete evidence ledger
- leaves result claims blocked until outputs are imported or toy execution produces a completed result artifact

### `POST /api/projects/{project_id}/auto-research/{run_id}/experiment-factory/import`

- imports an externally produced factory result without live benchmark, GPU, or Docker access
- persists the same environment manifest, materialized jobs, result artifact, evidence ledger, and repair plan as toy execution
- classifies missing imported baselines as `add_missing_baseline` / `missing_baseline_outputs`, missing ablations as `add_missing_ablation` / `missing_ablation_outputs`, insufficient seed/statistical evidence as `increase_seed_count` / `insufficient_statistics_outputs`, and candidate/runtime failures as rerun-required failures
- keeps the run `failed` when no objective score is provided; otherwise marks the run `done` while preserving repair blockers for incomplete evidence

### `POST /api/projects/{project_id}/auto-research/{run_id}/experiment-execution/plan`

- builds the Goal 3 typed experiment-job execution plan from the run's domain experiment protocol and experiment-factory plan
- this is the experiment-job runtime contract, not the auto-research queue/worker execution plane
- accepts optional `execution_route` (`deterministic_replay`, `local_command`, `docker`, `external_import`, or `bridge_import`), `budget_class`, `approval_state`, `docker_available`, and `bridge_available`
- returns `AutoResearchExperimentExecutionPlanRead` with typed jobs, route-specific `command` / `replay_spec` / `import_spec`, expected inputs/outputs, metric schema, runtime contract, `capability_refs`, environment requirements, approval state, lineage refs, claim ceiling, blockers, and warnings
- unsupported domains, missing protocol, missing benchmark, Docker unavailable, bridge unavailable, and unapproved budget routes produce structured blockers; blocked plans do not generate fake output refs

### `POST /api/projects/{project_id}/auto-research/{run_id}/experiment-execution/execute`

- executes the typed experiment plan through deterministic replay or repository-approved local-command runtime
- local command runtime is restricted to the internal approved command spec and records command, cwd, environment, timeout, stdout/stderr refs, exit code, runtime contracts, environment manifest, output validation, deterministic fingerprint, failure classification, repair recommendation, lineage refs, result artifact, and evidence ledger mapping
- replay runtime records replay source package refs/hashes and produces a stable deterministic fingerprint
- Docker and bridge routes are blocked unless their availability/approval is explicitly represented; there is no silent fallback to local success
- validation failures such as missing output, bad JSON, bad metric schema, benchmark mismatch, environment mismatch, runtime failure, and approval-required state are returned as failed/blocked results with negative evidence and repair recommendations
- results, output validation rows, package manifest fragments, and evidence ledger entries carry `evidence_origin` so fixture, toy, local-smoke, deterministic replay, stale-cache, imported-real, frozen-snapshot, live-source, Docker, and bridge evidence cannot be confused at the final gate
- environment manifests and results carry `output_hashes`; imported packages with declared `expected_artifact_sha256`, `artifact_sha256`, `source_package_sha256`, or `content_sha256` fail with `environment_mismatch` when the package hash does not match
- persists `experiment_execution_plan.json`, `experiment_execution_result.json`, `artifact.json`, and an appended/merged `evidence_ledger.json` through repository helpers
- fixture/local smoke evidence preserves claim ceilings such as `review_only_engineering_validation_claim` and never upgrades final-publish readiness

### `POST /api/projects/{project_id}/auto-research/{run_id}/experiment-execution/import`

- imports an externally produced typed experiment artifact package through the Goal 3 runtime contract
- validates the imported package's schema version, provenance, declared package hash, metric schema, benchmark resolver ref, environment requirements, expected outputs, output hashes, sample/split counts, baseline refs, ablation refs, and output validation blockers
- incomplete or schema-mismatched imports fail validation; imported packages are not auto-filled with synthetic output refs
- persists the same typed plan/result/evidence artifacts as local/replay execution while retaining source package, hash, import timestamp, provenance, evidence origin, and validation blockers in the result payload

### `PATCH /api/projects/{project_id}/auto-research/{run_id}/controls`

- patches the persisted run request snapshot for future scheduling/budget changes
- currently supports `max_rounds`, `candidate_execution_limit`, and `queue_priority`
- updates queued job priority in the execution plane when the run still has queued work

### `GET /api/projects/{project_id}/auto-research/{run_id}/execution`

- returns execution-plane state for the run
- this endpoint is the auto-research queue/worker plane for scheduling whole research runs; it is not the Goal 3 experiment-job runtime
- includes job history, active job information, cancel flag, queue telemetry, a primary worker snapshot, and the current worker fleet
- job entries now expose `priority`, `lease_id`, `recovery_count`, and `last_recovered_at`
- worker state now also exposes `lease_expires_at`, recent lifecycle timestamps, and a `stale` flag
- queue telemetry exposes queue depth, per-status job counts, worker counts, processed-job totals, and recovery timestamps

### `GET /api/projects/{project_id}/auto-research/console`

- returns the project-level operator console view
- aggregates run list, top-level queue telemetry, worker fleet state, current run detail, execution state, bridge state, registry/lineage, grouped candidate views, review state, publish state, and currently available actions
- accepts optional `run_id` query param to focus the console on a specific run
- also accepts optional `search`, `status`, `publish_status`, `review_risk`, `novelty_status`, `budget_status`, and `queue_priority` query params for run triage
- returns both total run count and filtered run count, and each run summary now includes bridge posture, publish status, review risk, novelty posture, budget posture, and queue priority
- surfaces latest idea-brief domain routing fields: `latest_brief_domain_id`, `latest_brief_domain_label`, `latest_brief_domain_confidence`, `latest_brief_domain_supported`, and `latest_brief_domain_blockers`
- surfaces latest idea-brief domain evidence status fields: `latest_brief_domain_literature_status`, `latest_brief_domain_benchmark_status`, `latest_brief_domain_protocol_status`, `latest_brief_domain_claim_ceiling`, `latest_brief_domain_required_followups`, and `latest_brief_domain_kill_criteria`
- exposes `actions.create_run_from_brief=false` when the latest brief is blocked, lacks a selected hypothesis, or cannot create experiments under its routed domain policy
- includes `publication_case`, a project-level offline publication-case summary with domain decision/template/literature/resolver/protocol/readiness context, review/final readiness, package asset statuses, blocked asset counts/roles, per-asset final-publish blocking checks/reasons, submission archive current/complete/download-gate status, reproducibility checklist completeness, artifact-integrity audit status, final-publish policy version and failed check ids, review finding count/path, repair action status counts, execution/import replay outputs, literature source coverage, benchmark provenance status, benchmark schema coverage/blockers, benchmark source-observation coverage/blockers, benchmark final-publish-candidate coverage/blockers, benchmark source-independence readiness/blockers, benchmark snapshot materialization status/counts/unmaterialized run ids, statistics claim ceiling, negative evidence counts, Goal 1 Phase 6 covered/missing/required negative-evidence categories, blocked source-independence repair-attempt evidence, final-publish package completeness, engineering-vs-scientific gap counts/classification, rereview recommendations, publish blockers, required follow-ups, kill criteria, and paths to `offline_publication_case.json` / `offline_publication_audit.json`
- includes `operator_audit`, the persisted operator-state audit for the project, when runs exist
- includes `external_capability_manifest`, a deterministic project-level manifest of external network, literature, full-text/citation-context extraction, benchmark ingestion, local/Docker/bridge/import execution, budget, approval, and sandbox capabilities
- includes `current_run.operator_status`, the policy-backed run control surface with persisted job inspection, approval/budget status, repair queue, artifact lineage, package status, final-gate status, external capability manifest, action log, stale/missing refs, blockers, and per-action allow/deny reasons
- includes Goal 11 long-running reliability state on the current run: `state_manifest`, `runbook`, `timeline_state`, `attempt_ledger`, and `branch_state`
- the long-running state is rebuilt from repository artifacts and persisted through repository helpers as `project_state_manifest.json`, `project_runbook.json`, `project_timeline.json`, `attempt_ledger.json`, and `branch_state.json`
- `current_run.actions.resume`, `retry`, and `cancel` mirror the backend operator policy instead of being UI-only affordances
- operators can inspect queue bottlenecks, stale-worker posture, and recent recoveries without reading `queue.json`

### `GET /api/projects/{project_id}/auto-research/operator/audit`

- returns the persisted Goal 9 operator-state audit for the project
- accepts optional `rebuild=true` to reconstruct and rewrite the audit from persisted run, queue, bridge, review, package, evaluation, and project-paper state
- persists `operator_state_audit.json` through repository helpers and returns `audit_artifact_path`, `audit_artifact_sha256`, `state_items`, `case_coverage`, blockers, and a conservative conclusion
- state items cover run queue state, typed experiment jobs, bridge imports, approval/budget controls, repair/revision queues, package/final-gate state, artifact lineage, and evaluation artifacts
- review-ready, workshop, and case-study package states are represented as blocked or review-ready unless the final-publish gate itself is satisfied

### `GET /api/projects/{project_id}/auto-research/external-capabilities`

- returns the persisted Goal 10 external capability manifest for the project
- accepts optional `rebuild=true` to reconstruct and rewrite `external_capability_manifest.json`
- manifest records use `schema_version=external_capability_manifest_v1` and `policy_version=goal10_external_capability_policy_v1`
- each record includes `capability_id`, provider/source/config source, checked timestamp, state (`disabled`, `not_configured`, `unavailable`, `approval_required`, `ready`, `blocked_by_policy`, or `failed_validation`), approval requirement, budget class, sandbox constraints, blockers, related artifact refs, and optional operator action policy
- manifest-level fields include deterministic fingerprint/path, record count, ready/unavailable/approval-required counts, and blockers; optional or unavailable capabilities remain visible but do not fabricate readiness
- the manifest is declarative and deterministic: it reads repository state, run/brief requests, settings, and explicit environment flags such as `SCHOLARFLOW_EXTERNAL_NETWORK_APPROVED`, `SCHOLARFLOW_DOCKER_AVAILABLE`, and `SCHOLARFLOW_BRIDGE_AVAILABLE`; it does not probe Docker or make live network calls

### `GET /api/projects/{project_id}/auto-research/{run_id}/operator/status`

- returns the persisted operator-control status for one run
- reconstructs state from `run.json`, registry/lineage artifacts, queue state, bridge state, typed experiment execution results, review/publish artifacts, and `operator_action_log.json`
- response fields include `control_state`, `action_policy`, `jobs`, `approvals`, `budget`, `repair_queue`, `artifact_lineage`, `package_status`, `final_gate_status`, `external_capability_manifest`, `action_log`, `stale_refs`, `missing_refs`, and a deterministic timeline
- response also includes Goal 11/12 state: `state_manifest` audits active/stale/superseded/missing/migration-needed artifacts plus unsafe-resume blockers; `runbook` lists next actions, approvals, repair candidates, claim ceiling, final-gate status, kill criteria, stale/migration inputs, and relevant prior memory risks/follow-ups; `timeline_state` records versioned project events; `attempt_ledger` records retry/resume/cancel/reject/import attempts without deleting old negative evidence; `branch_state` scopes final-gate evidence to the selected branch
- runbook memory hints surface prior blockers/negative findings as risks or repair suggestions only; they do not directly fail the current run's final gate without current-project evidence
- `action_policy` provides policy-checked `approve`, `reject`, `retry`, `resume`, and `cancel` decisions with blocker codes, recoverability, required next action, and related refs
- approval state is derived from persisted operator action records after reload; approval does not fabricate experiment output or bypass runtime contracts
- stale package/archive refs, missing registry refs, schema-version gaps, fingerprint mismatches, migration-needed artifacts, pending bridge imports, rejected approvals, and active leased/running queue work block unsafe resume/retry transitions; resume on an already queued run is treated as an idempotent noop

### `POST /api/projects/{project_id}/auto-research/{run_id}/operator/actions`

- applies a policy-checked operator action: `approve`, `reject`, `retry`, `resume`, or `cancel`
- accepts `action`, optional `target_id`, `approval_id`, `operator_id`, `reason`, and optional `expected_artifact_fingerprints` for freshness preconditions
- returns `AutoResearchOperatorActionResult` with `accepted`, `status`, optional `job_id`, persisted `action_record`, updated `run_status`, and execution state when relevant
- every accepted, noop, or blocked action appends to `operator_action_log.json` with preserved artifact refs, failure refs, negative-evidence refs, parent attempt/job refs, decision evidence, and terminal blocker evidence where applicable
- Goal 11 actions also update `attempt_ledger.json`; retry/resume create new attempt records or typed transitions, while cancel/reject become terminal attempt states visible in runbook/operator console
- invalid transitions return `409` with structured `AutoResearchOperatorPolicyError` detail instead of silently queuing work
- `reject` and `cancel` create terminal decision evidence and preserve the prior artifacts/failures; `retry` and `resume` enqueue through the existing execution plane without deleting prior attempt evidence

### `GET /api/projects/{project_id}/auto-research/project-paper`

- builds a deterministic project-level paper orchestration snapshot
- reads idea briefs, selected runs, cross-run meta-analysis, run-level evidence ledgers, claim ledgers, and reviewer simulations when present
- returns latest-brief domain routing and evidence fields (`latest_brief_domain_decision`, `latest_brief_domain_template`, `latest_brief_domain_blockers`, `latest_brief_domain_literature_strategy`, `latest_brief_domain_literature_result`, `latest_brief_domain_benchmark_resolver`, `latest_brief_domain_experiment_protocol`, `latest_brief_domain_readiness_status`, `latest_brief_domain_claim_ceiling`, `latest_brief_domain_required_followups`, and `latest_brief_domain_kill_criteria`)
- writes domain routing and evidence information into `offline_publication_case.json`, `publication_readiness_report.json`, and readiness `checks` entries for `domain_routing`, `domain_literature_strategy`, `domain_benchmark_resolver`, and `domain_experiment_protocol`
- keeps domain blockers in project blockers, limitations, required follow-ups, and kill criteria so unsupported ideas cannot progress into paper claims
- returns a project conclusion ledger split into stable conclusions, conditional conclusions, negative findings, failed hypotheses, and limitations
- returns claim traces for every core project-level claim, with run IDs and evidence refs
- decides whether the project should write no paper, a single-run technical report, a workshop candidate, or a conference candidate
- prevents single-run evidence from being presented as a full project-level paper and blocks project-level publish readiness when strong claims lack run-level evidence
- materializes an evidence-constrained project manuscript with required sections: abstract, introduction, research question, related work, method, benchmark and data, experiment setup, results, analysis, negative evidence, limitations, reproducibility, conclusion, and references; the reproducibility section includes an artifact evidence map for literature, benchmark provenance, execution/statistics, claim/retrieval evidence, negative evidence, review/repair/rereview, lineage, readiness, and publication-manifest files
- materializes compile-oriented project paper sources:
  - `paper_original.md`
  - `paper.md`
  - `paper_revised.md`
  - `main.tex`
  - `references.bib`
  - `build.sh`
  - `paper_compile_report.json`
  - `paper_compiler_evidence.json`
  - `manuscript_context.json`
  - `artifact_index.json`
  - `claim_evidence_index.json`
  - `figures_tables_metadata.json`
  - `source_fingerprints.json`
  - `project_revision_action_index.json`
  - `project_review_findings.json`
  - `revision_action_plan.json`
  - `reviewer_response_dossier.json`
  - `revision_round.json`
  - `revision_actions.md`
  - `project_revision_application.json`
  - `project_rereview_report.json`
  - `manifest.json`
- `manuscript_context.json` is a versioned/fingerprinted Goal 5 compiler context linking the brief, domain decision/template, literature support, benchmark provenance, experiment execution evidence, claim evidence, negative evidence, project conclusions, reviewer/revision state, readiness policy, and claim ceiling
- source `manifest.json` records required files, SHA-256/size metadata, source fingerprints, reconstructability, external evidence-artifact completeness, and missing source/external artifact blockers; self-referential `manifest.json` and `source_fingerprints.json` hashes are handled by explicit policy instead of embedded impossible self-hashes
- `artifact_index.json`, source `claim_evidence_index.json`, and `figures_tables_metadata.json` make the source package auditable without a local PDF compiler; missing references or evidence artifacts mark source-package readiness false rather than being hidden by submission readiness
- converts weak or unsupported project-paper claims into bounded revision actions; auto-applicable claim-evidence actions are materialized as claim downgrades or retrieval-repair routes and then re-reviewed without upgrading missing evidence to supported evidence
- project-paper revision actions also route final-publish blockers into bounded repairs for weak/missing literature support, missing benchmark provenance, insufficient benchmark scale, and insufficient statistics; literature-refresh actions now materialize `literature_support_index.json` from structured cached/network scout evidence when at least two non-fixture sources are available, otherwise the action is marked `blocked` with residual blockers
- benchmark-provenance repair actions now materialize `benchmark_provenance_repair_index.json`; they complete only when selected run benchmark profiles already carry complete publication-grade frozen/imported/real provenance, and they remain `blocked` for toy/fixture sources, missing provenance, insufficient scale, or failed eligibility checks
- benchmark-scale and insufficient-statistics repair actions now materialize `experiment_repair_index.json`; they record selected-run execution coverage, imported-result replay runs, materialized-job output refs, environment manifest linkage, and deterministic statistics/significance evidence. The routes complete only when publication-eligible benchmark scale, deterministic aggregate/significance evidence, and linked execution/import replay outputs are available; otherwise they remain `blocked` with the required rerun/import follow-up
- `revision_action_plan.json` records the Goal 6 autonomous revision plan with finding-to-action mapping, evidence requirement, action kind/scope, expected outputs, lineage parent refs, attempt limits, execution eligibility, blockers, status, and a capability audit proving the project-level loop productionizes the existing review/repair path instead of replacing it
- `reviewer_response_dossier.json` records a finding-by-finding reviewer response with action taken, revised artifact refs, evidence refs used, changed claim IDs, response status, unresolved blocker or limitation, and final-publish impact; blocked evidence-producing actions remain unresolved unless validated artifact refs already exist
- `revision_round.json` records the bounded revision round, preserving original and revised manuscript refs/fingerprints, original and revised claim-evidence index refs, selected action executions, reviewer response dossier, re-review findings, resolved/partial/unresolved/regressed counts, pending action count, terminal status, readiness impact, and unresolved blockers
- `project_rereview_report.json` now includes action-level re-review records with the original finding, repair route, input/output artifacts, repair-output artifact audits, terminal-condition status, reviewer residual concern, resolved blockers, new blockers, claim-downgrade status, and recommendation for each revision action
- `project_rereview_report.json` also records previous review, revised artifact, and re-review fingerprints so clients can verify re-review consumed revised artifacts rather than reusing the prior review object
- `statistics_report.json` now carries publication-case statistics evidence directly: per-method metric rows, aggregate metric rows, deterministic train/test `split_evaluations`, split-level `split_metric_table` rows, per-query diagnostic rows, required-metric coverage for retrieval / verification / repair-router metrics, paired/significance comparisons, effect sizes, multiple-comparison correction status, confidence intervals or deterministic equivalents, execution/import replay coverage, negative-evidence summaries, replication readiness fields such as `multi_split_ready` and `final_publish_replication_ready`, final-publish statistics blockers, statistics limitations, and a claim-ceiling recommendation constrained by benchmark readiness and claim support
- project submission packages now include a standalone `repair_execution_log.json` that records every repair action's status, input/output artifact refs, repair-output artifact audits, failure classification, residual blockers, and re-review result
- materializes a project submission package:
  - `submission_manifest.json`
  - `reproducibility_checklist.md`
  - `reviewer_response.md`
  - `repair_execution_log.json`
  - `claim_evidence_index.md`
  - `retrieval_evidence_ledger.json`
  - `lineage_archive.json`
  - `literature_support_index.json`
  - `paper_compiler_evidence.json`
  - `publication_evidence_index.json`
  - `publication_readiness_report.json`
  - `supplemental_artifacts.json`
  - `project_review_findings.json`
  - `benchmark_card.json`
  - `benchmark_provenance_manifest.json`
  - `benchmark_provenance_repair_index.json`
  - `statistics_report.json`
  - `experiment_repair_index.json`
  - `negative_evidence_report.json`
  - `limitations_appendix.json`
  - `submission_archive.zip`
  - `submission_archive_manifest.json`
  - `reproducibility_checklist.json`
  - `artifact_integrity_audit.json`
  - `final_publish_decision.json`
  - `offline_publication_case.json`
  - `offline_publication_audit.json`
  - `code_package.zip`
  - `publication_manifest.json`
- every project submission `generated_assets` entry includes role, path, hash, source action, source run ids, source evidence refs, readiness contribution, explicit `missing_status`, `blocked_status`, `final_publish_blocking`, `blocking_check_ids`, and `blocking_reasons`; `publication_manifest.json` mirrors the same auditable asset list, with the manifest's own self-referential hash marked by an integrity note instead of embedding an impossible final self-hash
- `submission_archive_manifest.json` is the reconstructability ledger for `submission_archive.zip`; each entry records logical id, archive path, source artifact ref/path, sha256, size, content type, generator, final-publish requirement flag, validation status, and blockers. The archive intentionally excludes self-referential siblings such as `submission_archive.zip`, `submission_archive_manifest.json`, `reproducibility_checklist.json`, `artifact_integrity_audit.json`, `final_publish_decision.json`, and `publication_manifest.json`; those files are tracked beside the archive and verified by the manifest/final decision instead.
- `reproducibility_checklist.json` is generated from source, execution, benchmark, statistics, negative-evidence, and archive manifests. Required checklist items with `missing` or `partial` status propagate into `final_publish_decision.json` instead of being hidden behind review readiness.
- `artifact_integrity_audit.json` replays archive/source-package validation and blocks final readiness on missing required artifacts, hash mismatch, stale source fingerprints, or unresolved archive-current failures.
- `final_publish_decision.json` records the Goal 7/10 final-publish policy decision with `policy_version`, `paper_tier`, passed/failed checks, blockers, required follow-ups, claim ceiling, evidence refs, archive manifest ref, readiness manifest ref, and the `evidence_origin_policy` check. `project_final_publish_ready` mirrors this decision, not loose package existence.
- `evidence_origin_policy` rejects fixture, toy, local-smoke, deterministic-replay, and stale-cache evidence as final-publish support, requires at least one publication-grade real origin (`fresh_cache`, `imported_real_artifact`, `frozen_snapshot`, `live_source`, `docker_execution`, or `bridge_execution`), and carries origin counts from literature, benchmark provenance, and execution profiles
- `publication_manifest.json` also mirrors the readiness decision trace from `publication_readiness_report.json`, including review/final readiness, failed checks, blockers, required follow-ups, kill criteria, claim ceiling, Phase 6 negative-evidence coverage, and evidence artifact refs explaining why a review bundle is not a final-publish bundle; benchmark schema failures surface as the `benchmark_schema_coverage` readiness check, benchmark source-observation failures surface as the `benchmark_source_observation_coverage` readiness check, benchmark final-publish-candidate failures surface as the `benchmark_final_publish_candidate_coverage` readiness check, same-release benchmark-view limits surface as the `benchmark_source_independence` readiness check, and missing Phase 6 categories surface as the `phase6_negative_evidence_coverage` readiness check
- returns Goal 6 revision fields including `project_revision_action_plan`, `project_revision_action_plan_path`, `project_revision_response_dossier`, `project_revision_response_dossier_path`, `project_revision_round`, and `project_revision_round_path`, so clients can inspect the action plan, action execution results, reviewer response dossier, revised artifact refs, re-review status, terminal status, and unresolved blockers from the project-paper response
- returns project package readiness fields including `project_review_bundle_ready`, `project_final_publish_ready`, `project_submission_blockers`, `project_submission_package`, `project_submission_archive_manifest`, `project_submission_archive_manifest_path`, `project_submission_archive_path`, `project_reproducibility_checklist`, `project_reproducibility_checklist_json_path`, `project_artifact_integrity_audit`, `project_artifact_integrity_audit_path`, `project_final_publish_decision`, `project_final_publish_decision_path`, `project_paper_sources_manifest_path`, `project_manuscript_context_path`, `project_manuscript_context_complete`, `project_manuscript_context_fingerprint`, `project_review_findings_path`, `project_repair_execution_log_path`, `project_retrieval_evidence_ledger_path`, `project_literature_support_index_path`, `project_paper_compiler_evidence_path`, `project_publication_evidence_index_path`, `project_code_package_path`, `project_benchmark_card_path`, `project_benchmark_provenance_manifest_path`, `project_benchmark_provenance_repair_index_path`, `project_statistics_report_path`, `project_experiment_repair_index_path`, `project_negative_evidence_report_path`, `project_limitations_appendix_path`, `project_offline_publication_case_path`, `project_offline_publication_audit_path`, `project_publication_manifest_path`, and `project_supplemental_artifacts_path`
- `project_review_findings.json` records project-level reviewer-simulator findings mapped one-to-one to bounded revision actions, preserving finding ids, reviewer role, severity, required repair kind, execution route, expected outputs, terminal condition, and rereview requirement
- `paper_compiler_evidence.json` now records review-findings coverage, execution/import replay coverage, benchmark final-publish-candidate coverage, audited terminal blocked repair attempts, and reproducibility coverage, including persisted finding/action mapping, source package readiness, selected-run artifact coverage, execution source counts, execution evidence ledger entries, and planned package asset roles; local PDF compiler availability is reported through `compile_readiness.pdf_blockers` and `compile_environment_limitations`, and deterministic terminal blocked repairs are reported as evidence limitations rather than missing package plumbing, but neither condition makes an otherwise materialized source package or compiler-evidence packet incomplete
- `publication_evidence_index.json` records both claim-level evidence traces and benchmark-level evidence items that point to `benchmark_provenance_manifest.json` and `benchmark_provenance_repair_index.json`, so benchmark repair/provenance outputs are part of the publication evidence graph
- `project_final_publish_ready=false` is expected whenever evidence, revision, source-package/evidence-compiler, or publish-gate blockers remain; local PDF compiler absence only blocks compiled-PDF output when sources are materialized, so clients must not treat a review bundle as a final publish bundle
- `negative_evidence_report.json` retains run-level negative results, failed trials, retrieval misses, unsupported claim gaps, project negative findings, and blocked repair evidence as first-class package evidence; unresolved blocking entries continue to block final publish
- `negative_evidence_report.json` exposes the Goal 1 Phase 6 taxonomy through `phase6_required_categories`, `phase6_conditional_categories`, `phase6_categories`, `phase6_category_counts`, `phase6_entries_by_category`, `phase6_category_coverage`, `phase6_missing_categories`, `phase6_coverage_complete`, and `phase6_runtime_failure_observed`. Required categories include ledger-aware non-improvement, unsupported-claim false negatives/positives, retrieval misses, contradiction/refutation ambiguity, insufficient-evidence cases, abstention failure, repair-router failure, and failed or blocked repair attempts. The claim-evidence vertical covers the repair-attempt category through `phase6_repair_execution:project_benchmark_source_independence_repair`, a deterministic blocked repair entry that records why no second independent benchmark/source release can be attached offline. `runtime_failure` is conditional and is required only when a failed trial records runtime/process failure evidence. Missing required categories are preserved as final-publish blockers/follow-ups rather than being inferred as covered.
- `retrieval_evidence_ledger.json` aggregates selected-run retrieval evidence entries and artifact-output retrieval ledgers into a project-level ledger while preserving partial/missing support as blockers or limitations
- `experiment_repair_index.json` includes a project `execution_evidence_ledger` with per-run execution/import capsules for executor mode, backend, command or import path, runtime contracts, environment manifest identity, dependency manifest, input benchmark provenance, method configs, method outputs, method-ladder artifact refs, metrics refs, evidence-ledger refs, negative-evidence refs, repair action linkage, failure classifications, and deterministic fingerprints; compiler evidence and readiness reports repeat execution coverage checks so statistics cannot be marked complete without linked execution/import replay artifacts
- `literature_support_index.json` records domain literature strategy/result details, source-class counts, fixture-only status, related-system coverage, known methods/datasets/metrics/SOTA, and coverage for FARS and ARIS from cached/imported literature metadata and known-SOTA fields; missing coverage is preserved as a limitation/follow-up rather than inferred
- `offline_publication_case.json` records the deterministic fixed idea, research question, brief/hypothesis/benchmark/experiment chain, full claim-evidence method ladder, expected metrics including repair precision/recall for active repair-router methods, repair triggers, paper package outputs, and explicit evidence classification for real/imported/frozen sources, schema-derived deterministic execution evidence when present, and internal fixtures; the method ladder covers random, lexical overlap, BM25/TF-IDF-style retrieval, phrase/bigram-aware retrieval, ledger-aware retrieval, abstention/repair routing, no-ledger ablation, retrieval-only/no-verification ablation, and repair-router-disabled ablation
- `offline_publication_audit.json` records the Phase 1 capability/breakpoint audit for literature refresh, benchmark snapshot selection, execution/import replay, statistics strength, negative-evidence retention, repair-aware rereview, and submission-package completeness; it includes structured `phase1_requirements` for literature/novelty, benchmark scale/source grade, benchmark source independence, schema coverage, source-observation coverage, baseline ladder, method reproducibility, multi-seed/split/paired statistics, negative-evidence claim ceiling, package completeness, and blocker classification. The statistics requirement details mirror the statistics report's replication summary, split labels, split evaluation count, split metric row count, and final-publish replication readiness, while still preserving non-statistical final-publish blockers such as same-release source independence and negative evidence. Each requirement records status, evidence refs, blockers, engineering-vs-scientific classification, follow-ups, kill criteria, scope limitation, and detail fields, so `final_publish_ready=false` can be traced to concrete evidence limitations rather than missing package plumbing. Its top-level `fixed_goal_audit` records the mandatory Goal 1 audit commands, `docs/goal.md` source, audited key-file list/scopes, artifact destinations, and the artifact conclusion that package plumbing is complete while final publish remains evidence-blocked. Its `final_publish_gap_audit.goal1_current_audit_summary` gives the compact Goal 1 state: review readiness, final-publish false reason, package-plumbing completeness, engineering/scientific gap counts, Phase 6 coverage, frozen/imported snapshot materialization, benchmark final-candidate coverage, benchmark source-independence status, and blocked Phase 1 requirement ids. Its `final_publish_gap_audit.benchmark_snapshot_artifact_records` mirrors frozen/imported source lineage from `benchmark_provenance_manifest.json`, including dataset id, source locator, revision/license, materialized local path, source and record fingerprints, source content origin/note, parent source dataset metadata, sample/split counts, split and label distributions, query/document/evidence/relevance observation counts, publication-grade eligibility/blockers, and final-candidate eligibility/blockers; the same audit also reports snapshot record count, materialized count, all-required-materialized status, unmaterialized run ids, source-independence audit, and the materialization policy.
- the Operator Console mirrors that audit through `publication_case`: benchmark schema coverage/blockers, benchmark source-observation coverage/blockers, benchmark final-candidate coverage/blockers, benchmark source-independence readiness/blockers, benchmark snapshot materialization status/counts/unmaterialized run ids, Phase 6 missing categories, `final_publish_engineering_gap_count`, and remaining `final_publish_scientific_evidence_gaps` stay visible so operators can distinguish package/lineage/output/compile/manifest defects from benchmark-source evidence limitations without opening package internals
- benchmark provenance assets expose source class, content-origin, and eligibility fields such as `source_class`, `source_content_origin`, `source_content_note`, `provenance_complete`, `publication_grade_eligibility`, `publication_grade_blockers`, `publication_grade_eligible`, `final_publish_candidate_eligible`, and `final_publish_candidate_blockers`; `publication_grade_eligible` is the base source/provenance gate, while `final_publish_candidate_eligible` is the stricter project-candidate gate that also requires at least 100 normalized examples, frozen/imported/remote-real provenance, and original/imported benchmark content rather than schema-derived/template-generated content
- imported JSON benchmark packages may declare `benchmark_package_manifest` or `schema_version=benchmark_package_manifest_v1`; declared packages are validated for manifest schema, dataset id, source locator, revision/license, content/package checksums, non-empty train and test/validation/dev splits, split-count consistency, label schema, task-aware query/document/evidence schema, metric compatibility, and source-independence metadata before resolver output can become benchmark provenance
- failed package validation raises a benchmark ingestion error for the resolver path and records validation blockers for direct validation callers; legacy JSON inputs without a declared package manifest continue through the existing adapter path without being silently promoted to publication-grade provenance
- idea briefs can carry an explicit `benchmark_source`; supported-domain benchmark resolvers use that imported/local provenance before falling back to template fixtures. Complete imported provenance can make the resolver `ready` and `publication_grade_eligible`, but source-independence, statistics, execution validation, negative evidence, and publish-gate checks still prevent final-publish promotion.
- `benchmark_provenance_manifest.json` now includes per-run `benchmark_source_records` with dataset id, revision, license, source locator, fingerprint, source content origin/note, parent source dataset metadata, sample/split counts, split distribution, label distribution, query/document/evidence-annotation/relevance counts, label space, source class, publication eligibility/blockers, final-publish-candidate eligibility/blockers, and `query_document_evidence_schema`; its `schema_coverage`, `source_observation_coverage`, `final_publish_candidate_coverage`, and `benchmark_source_independence_audit` sections preserve missing query/document/evidence/label/count roles, stricter final-candidate blockers, and same-release benchmark-view limits, with claim-verification sources requiring evidence annotations and retrieval-only sources requiring relevance/qrels observations. `publication_readiness_report.json` repeats `benchmark_schema_coverage`, `benchmark_source_observation_coverage`, and `benchmark_source_independence_audit`, and benchmark provenance package assets list those readiness checks in `blocking_check_ids` whenever schema roles, required source observations, or independent-source evidence are missing.
- repository-local frozen benchmark snapshots can carry the same Phase 2 source metadata directly in the JSON. The current SciFact snapshot includes canonical `dataset_id`, `revision`, `license`, `fingerprint`, `source_class`, `provenance_complete`, `sample_count`, `split_count`, split/label distributions, query/document/evidence/relevance observation counts, `query_document_evidence_schema`, `publication_grade_eligibility`, and final-publish-candidate eligibility/blockers, so package manifests are not fabricating provenance that is absent from the materialized source artifact. For file-path-only frozen snapshots, project-level benchmark provenance treats the materialized `source_file_path` as the source locator instead of requiring a synthetic URL.
- benchmark adapters preserve payload-owned canonical source metadata (`dataset_id`, `revision`, `license`, `fingerprint`, source/content fields, and eligibility records) into `DatasetSpec`, benchmark cards, provenance manifests, readiness reports, and offline audits; `BenchmarkSource` metadata is only a fallback when the materialized JSON does not carry those fields.
- `benchmark_card.blockers` describes benchmark-card completeness blockers for the current run profile, while `publication_grade_blockers` separately describes why the source cannot be used as final-publish evidence
- benchmark cards and dataset specs expose frozen snapshot metadata including `sample_count`, `split_count`, `supports_claim_verification`, `verification_label_space`, `source_content_origin`, and `source_content_note`; the current SciFact snapshot records `source_content_origin=original_benchmark_records`, while schema-derived/template-generated content, if used by another source, remains deterministic execution evidence only and blocks publication/final-candidate eligibility until original/imported benchmark records are materialized
- project-level `benchmark_card.json`, `paper_compiler_evidence.json`, `publication_readiness_report.json`, and `benchmark_provenance_manifest.json` carry the same snapshot metadata and final-candidate benchmark coverage so submission-package readiness can be audited from project artifacts rather than only from run snapshots
- base benchmark publication eligibility requires a real or imported source class (`remote_real`, `frozen_snapshot`, or `imported_real`), non-empty train/test splits, at least 20 normalized examples, complete provenance fields (source locator, `dataset_id`, `revision`, `license`, and `source_fingerprint`), original/imported benchmark content rather than schema-derived/template-generated content, and a complete task-aware query/document/evidence schema; final-publish-candidate eligibility is stricter and is reported separately, with a 100-normalized-example target and materialized frozen/imported provenance requirements
- repository-local frozen snapshots loaded through `file_path` may satisfy `frozen_snapshot` eligibility when provenance and scale checks pass; miniature frozen snapshots remain useful adapter tests but must stay blocked by the sample-count gate
- internal fixtures remain review/evaluation assets only: `toy_builtin`, `cached_fixture`, `scholarflow:` dataset ids, `file://scholarflow-fixtures` snapshots, and fixture/synthetic/toy provenance signals must remain blocked from final-publish eligibility
- RAG/citation-faithfulness and lightweight ML/NLP domain evidence currently uses deterministic review-only fixtures or import-replay-compatible protocols unless real benchmark/literature provenance is present; these domains can produce auditable review packages or concrete blockers, but their `domain_claim_ceiling` must remain scoped to review-only engineering validation or technical-report-only claims until real multi-source literature, publication-grade benchmark scale/provenance, source independence, execution/statistics, and negative-evidence requirements are satisfied

### `GET /api/projects/{project_id}/auto-research/project-paper/submission`

- returns the typed Goal 7 project submission package: archive manifest, archive path, reproducibility checklist, artifact-integrity audit, final-publish decision, blockers, required follow-ups, and package fingerprint
- first reads persisted submission artifacts and revalidates the archive manifest against current source hashes/source-package fingerprint; if no persisted package exists, it builds the project-paper orchestration once and returns the materialized package
- stale source fingerprints, missing source artifacts, hash mismatches, or archive zip mismatches are returned as archive/integrity/final-decision blockers rather than repaired silently
- review-ready packages can return `review_bundle_ready=true` while `final_publish_ready=false`; clients must inspect `final_publish_decision.failed_checks` before offering any final-publish action

### `GET /api/projects/{project_id}/auto-research/project-paper/submission/download`

- downloads the persisted `submission_archive.zip` only when `final_publish_decision.final_publish_ready=true`
- also requires the persisted archive manifest to be `complete=true` and `current=true`; stale/missing/hash-mismatched archives return `409`
- does not rebuild or refresh artifacts during download, so a stale package cannot become downloadable as a side effect of a GET
- returns `404` when no submission package has been materialized, and `409` when the package is review-ready but not final-publish-ready

### `GET /api/projects/{project_id}/auto-research/evaluation-cases`

- returns the internal evaluation-case suite for idea-to-paper validation
- includes ten deterministic cases: toy, medium benchmark, literature-heavy, claim-evidence vertical, ablation-heavy, failed-hypothesis, generalized claim-evidence idea, RAG citation-faithfulness review, lightweight ML/NLP review, and unsupported-domain audit
- persists Goal 8 evaluation artifacts under the project autoresearch `evaluation/` directory: `evaluation_case_suite.json`, `evaluation_case_audit.json`, `system_metrics.json`, `scholarflow_system_paper_material.json`, and one trace JSON per case under `evaluation/traces/`
- every case trace includes a Goal 8 stage timeline for `idea`, `domain`, `brief`, `hypothesis`, `literature`, `benchmark`, `protocol`, `execution`, `evidence`, `readiness`, `repair`, `revision`, `package`, `final_gate`, and `failure`; each stage records status, input/output refs, artifact refs, evidence refs, negative evidence, blockers, claim ceiling impact, deterministic labels, and reproducibility constraints
- the toy case runs end-to-end through brief, scout, hypothesis selection, experiment factory, evidence ledger, and paper/review package materialization
- the claim-evidence vertical case seeds offline cached arXiv / Semantic Scholar / Crossref literature connector responses, runs repository-local SciFact frozen snapshots for support/refute/not-enough-info verification and retrieval-only evidence (`scifact_claim_verification_frozen_snapshot_v1.json` plus `scifact_claim_retrieval_frozen_snapshot_v1.json`), records retrieval and verification metrics, persists retrieval evidence ledgers, builds a project paper, applies bounded project revision actions, and emits a review-ready project submission package
- generalized claim-evidence ideas reuse the SciFact frozen-snapshot replay path rather than falling back to toy execution
- RAG citation-faithfulness and lightweight ML/NLP review cases exercise domain literature strategy, benchmark resolver, experiment protocol, deterministic review-only execution/replay outputs, evidence ledgers, package readiness, claim ceilings, and blockers without claiming final-publish evidence
- unsupported-domain evaluation keeps the case score successful only when the unsupported route is auditable: the trace remains blocked with no hypothesis, no experiment jobs, no evidence entries, no paper review package, and explicit domain blockers
- the failed-hypothesis case includes a deterministic typed execution missing-output failure; the failure is retained in negative evidence and failure timeline instead of becoming paper support
- evaluation traces include `domain_decision`, `domain_template`, `domain_blockers`, `domain_literature_strategy`, `domain_literature_result`, `domain_benchmark_resolver`, `domain_experiment_protocol`, `domain_readiness_status`, and `domain_claim_ceiling` so route and evidence decisions are auditable from the evaluation artifact
- evaluation traces also expose `literature_source_sufficiency_ready`, `literature_connector_availability`, and `literature_extraction_limitations` so deterministic cases can prove whether cached connectors, source-class requirements, and abstract/metadata-only evidence limitations reached the artifact
- claim-evidence vertical traces expose V3 package and Goal 6 revision proof fields: publication/readiness/statistics/experiment-repair/negative-evidence/offline-case/offline-audit/repair-log/review-findings paths, revision action plan / reviewer response dossier / revision round paths, selected action ids, paper-only action ids, blocked evidence-action ids, reviewer response item count, re-review resolved / partially resolved / unresolved / regressed counts, revision terminal status, revision readiness impact, review finding count and action mapping, submission bundle kind, generated asset roles, missing required asset roles, execution source counts, imported replay run ids, materialized execution run ids, paper section coverage, claim-support counts, claim ceiling, negative-evidence coverage, Phase 6 covered/missing/required category fields, blocked repair-attempt evidence, final-publish package completeness, engineering-vs-scientific gap counts/classification, Phase 1 blocked requirement ids, benchmark schema coverage/blockers, benchmark source-observation coverage/blockers, benchmark final-publish-candidate coverage/blockers, benchmark source-independence readiness/blockers, kill criteria, required follow-ups, and negative-evidence counts
- exposes trace-derived metrics used to judge idea-to-brief completeness, hypothesis selection, novelty risk detection, experiment executability, evidence consistency, reviewer readiness, final publish correctness, offline end-to-end submission-package coverage, stage coverage, evidence coverage, unsupported-domain honesty, blocker honesty, artifact lineage completeness, negative evidence retention, final gate false-positive count, revision resolution, and package readiness
- returns `system_paper_material` labeled `system_paper_material_not_final_submission`; its architecture, case-study, failure-mode, limitations, threats-to-validity, reproducibility appendix, ARIS/FARS comparison, future-work, and system-claim records must point back to evaluation metrics, trace artifacts, or audit refs
- evaluation cases remain deterministic and do not require live network, paid LLM calls, GPUs, or external benchmark availability

### `GET /api/projects/{project_id}/auto-research/system-evaluation`

- returns system-level evaluation tasks and metrics
- after `/evaluation-cases` has materialized Goal 8 artifacts, this endpoint reuses persisted `system_metrics.json`, `evaluation_case_audit.json`, and `scholarflow_system_paper_material.json` instead of hand-filled system claims
- if Goal 8 artifacts are missing, the response includes a blocker telling clients to run `/evaluation-cases`; it does not silently claim system-paper evidence

### `GET /api/projects/{project_id}/auto-research/{run_id}/bridge`

- returns the persisted experiment-bridge state for the run
- exposes the effective bridge config, current session, handoff/result paths, checkpoint history, and delivered notification records
- returns a disabled/inactive state for runs that do not use the bridge layer

### `POST /api/projects/{project_id}/auto-research/{run_id}/bridge/refresh`

- polls the current bridge session for a materialized `result_artifact.json`
- records a status-poll checkpoint even when no result is ready yet
- if a valid result artifact file is present, imports it into run/candidate state and, when `auto_resume_on_result=true`, resumes orchestration immediately
- response includes `imported`, `resumed`, and `source` (`none` or `file`) so clients can distinguish a pure poll from a successful ingest

### `POST /api/projects/{project_id}/auto-research/{run_id}/bridge/import`

- imports a compact inline bridge result payload for the active session
- synthesizes a structured `ResultArtifact`, persists it at the current handoff's expected result path, updates the candidate/run checkpoint state, and optionally resumes orchestration immediately
- intended for operator-driven bridge testing or manual external result entry when the result is not being dropped to disk automatically

### `GET /api/projects/{project_id}/auto-research/{run_id}/registry`

- returns the run-level registry / lineage view
- exposes persisted run files, selected candidate lineage, candidate registry entries, and explicit lineage edges
- run-level file refs now also cover the narrative / paper-pipeline assets that sit between `artifact.json` and `paper.md`
- paper-source refs now include the `paper_sources/` directory, the grounded `paper.md` snapshot, `revision_brief.md`, `revision_history.md`, `revision_actions.md`, `revision_diff.md`, `rewrite_packets/`, `build.sh`, `checkpoints/index.json`, `main.tex`, `references.bib`, the compile report, the structured revision action/diff ledgers, and the paper-source manifest
- file-bearing asset refs now include `size_bytes` and `sha256` when the target file exists
- is intended to be the stable read surface for Phase 4 artifact registry work

### `GET /api/projects/{project_id}/auto-research/{run_id}/registry/candidates/{candidate_id}`

- returns candidate-level registry state
- exposes the candidate snapshot, decision record, manifest source, resolved file references, and candidate lineage edges
- falls back to a generated manifest view when an on-disk manifest is missing or malformed

### `GET /api/projects/{project_id}/auto-research/{run_id}/registry/bundles`

- returns a reproducibility/export bundle index for the run
- current bundles include:
  - `selected_candidate_repro`
  - `portfolio_full`
- each bundle lists the asset refs, missing/existing counts, and candidate coverage needed to assemble a repro or export package later
- selected-candidate bundles now also carry the run-level narrative report, claim-evidence matrix, paper plan, figure plan, and paper revision state
- selected-candidate bundles now also carry the compile-oriented paper source package for later LaTeX-oriented export or refinement
- bundle asset lists now explicitly include paper revision history/brief assets, the structured revision action/diff ledgers, the section rewrite index/packet directory, plus the compile helper `build.sh` and checkpoint index, instead of relying only on the `paper_sources/` directory ref
- `portfolio_full` may intentionally report missing optional assets for non-selected candidates, for example candidate-local paper files that were never materialized

### `GET /api/projects/{project_id}/auto-research/{run_id}/registry/views`

- returns grouped registry views for the run
- current views include:
  - `selected`
  - `eliminated`
  - `failed`
  - `active`
  - `all`
- intended to give clients a stable way to inspect portfolio outcomes without rebuilding view logic from the raw candidate list

### `GET /api/projects/{project_id}/auto-research/{run_id}/review`

- returns a run-level Phase 5 review report grounded in persisted run, artifact, paper, and registry-bundle state
- persists `review.json` alongside the run so later publish/export steps can consume the same audit result
- highlights citation gaps, statistical/reporting gaps, provenance gaps, and revision actions
- citation coverage now resolves numeric citation markers against persisted `run.literature` entries and reports invalid indices, cited literature count, and whether a references section was found
- review output now also includes a structured `novelty_assessment` derived from the selected candidate and persisted literature state, including top related-work matches and uncovered research-facing claims

### `GET /api/projects/{project_id}/auto-research/{run_id}/review-loop`

- returns the persisted review-loop state for the run
- persists `review_loop.json` with round history, fingerprinted latest review state, open/resolved issues, and pending/completed revision actions
- each persisted revision action now carries stable `action_id`, linked finding/issue IDs, round visibility, and completion state
- avoids incrementing the round counter when the underlying review state is unchanged
- also keeps `paper_revision_state.json` synchronized with the latest review-loop round so later paper work can resume from persisted state rather than hidden context

### `POST /api/projects/{project_id}/auto-research/{run_id}/review-loop/apply`

- applies the currently pending review-loop actions against a completed run's persisted paper package
- requires `expected_round` plus `expected_review_fingerprint` so operators cannot accidentally rebuild against stale review state
- returns `409` when the review loop advanced, the fingerprint changed, or there are no pending actions left to apply
- leaves `POST /paper/rebuild` available as a compatibility path, but this explicit route is now the intended operator-facing review-action command

### `POST /api/projects/{project_id}/auto-research/{run_id}/paper/rebuild`

- rebuilds the narrative and paper pipeline for a completed run without rerunning experiments
- re-materializes `narrative_report.md`, `claim_evidence_matrix.json`, `paper_plan.json`, `figure_plan.json`, `paper_compile_report.json`, `paper_revision_action_index.json`, `paper_revision_diff.json`, `paper_section_rewrite_index.json`, `paper.md`, and the `paper_sources/` workspace package from persisted run state
- the rebuilt `paper_sources/` package now also carries `revision_brief.md`, a human-readable drafting brief derived from the persisted paper revision state
- the rebuilt `paper_sources/` package now also carries `revision_actions.md`, a human-readable action ledger derived from persisted review actions, rewrite packets, and section deltas
- the rebuilt `paper_sources/` package now also carries `revision_diff.md`, a human-readable change summary derived from the persisted structured revision diff
- the paper workspace now also materializes `rewrite_packets/index.json` plus per-section rewrite packets so revision work can jump straight into section-local objectives, claim commitments, and open actions
- the paper workspace also keeps `checkpoints/index.json` plus per-round `checkpoints/round_XXXX/` snapshots so revision rounds can resume from materialized paper assets rather than JSON metadata alone
- each checkpoint directory now also carries `checkpoint_note.md`, while the root workspace keeps `revision_history.md`, so the paper-improvement trail stays readable without parsing raw checkpoint payloads
- the paper workspace now also includes `build.sh`, a compile entrypoint that replays the persisted LaTeX/BibTeX command sequence
- refreshes the downstream draft snapshot and then rebuilds review / review-loop state against the rebuilt paper package
- returns `409` when the run is not yet complete or is missing the persisted planning/artifact state required for paper regeneration

### `GET /api/projects/{project_id}/auto-research/{run_id}/publish`

- returns the current publish-package manifest derived from the selected registry bundle and review output
- exposes required and optional assets, publish readiness, blockers, and revision actions
- persists `publish_package.json` alongside the run
- now distinguishes review-bundle readiness from final publish completeness
- reports `final_required_assets`, `missing_final_asset_count`, `final_blockers`, and `final_publish_ready` so clients can tell whether the package is merely reviewable or actually final-export complete
- final publish readiness now also requires the compile-oriented paper source package to remain intact and auditable from the V2 manifest (`paper.md`, `main.tex`, `references.bib`, `build.sh`, compiler evidence, manuscript context, source claim-evidence index, figures/tables metadata, artifact index, source fingerprints, revision artifacts, and external evidence refs)
- now also exposes `package_fingerprint`, current `review_round` / `review_fingerprint`, and archive freshness fields so clients can tell whether an existing `publish_bundle.zip` still matches the latest review-loop state and asset digests
- `archive_status` is `missing`, `stale`, or `current`; only `current` archives are downloadable without re-export

### `POST /api/projects/{project_id}/auto-research/{run_id}/publish/export`

- materializes a zip archive for the selected publish package
- includes the generated `review.json`, `review_loop.json`, `publish_package.json`, and the selected bundle's existing assets
- now also includes `archive_manifest.json`, which records whether the export is a `review_bundle` or `final_publish_bundle`, along with included and omitted asset IDs
- export response now exposes `bundle_kind`, `review_bundle_ready`, `final_publish_ready`, `included_asset_count`, `omitted_asset_count`, `package_fingerprint`, and the bound review-loop round / fingerprint used for that archive
- export can optionally register the run into a deployment via `deployment_id` and `deployment_label`
- exporting now also materializes:
  - `publication_manifest.json`
  - `code_package.zip`

### `GET /api/projects/{project_id}/auto-research/{run_id}/publish/download`

- downloads the latest materialized publish zip
- returns `409` until a publish export has been generated
- also returns `409` when the last exported archive is stale relative to the current review-loop or publish-package state

### `GET /api/projects/{project_id}/auto-research/{run_id}/publish/manifest`

- returns the persisted publication-facing manifest for a run once a current publish export exists
- includes stable run/project identity, paper metadata, publish/code download paths, and the deployment refs that currently list the publication
- now also exposes `compiled_paper_path`, `compiled_paper_sha256`, `paper_compile_output_paths`, and `compiled_paper_download_path` when the paper workspace already contains materialized compile outputs such as `main.pdf`
- returns `404` when the run has not been exported or when the existing export is stale and must be regenerated

### `GET /api/projects/{project_id}/auto-research/{run_id}/publish/code/download`

- downloads the persisted `code_package.zip` for the published run
- intended to keep code-package access stable even when clients do not unpack the larger publish bundle

### `GET /api/projects/{project_id}/auto-research/{run_id}/publish/paper/download`

- downloads the published `paper.md` artifact for the run
- keeps paper download stable and separate from the larger publish bundle

### `GET /api/projects/{project_id}/auto-research/{run_id}/publish/paper/compiled/download`

- downloads the compiled paper PDF when the persisted paper workspace already contains `paper_sources/main.pdf`
- returns `404` when no compiled PDF has been materialized for that run yet

### `GET /api/auto-research/deployments`

- returns deployment summaries across all projects visible to the current caller
- each summary includes publication count, project count, latest publication/run IDs, and final-ready counts

### `GET /api/auto-research/deployments/{deployment_id}`

- returns a deployment detail view with all publications currently registered into that deployment
- accepts optional query filters:
  - `search`
  - `final_publish_ready`
  - `bundle_kind`
  - `task_family`
- response now includes both `publication_count` and `filtered_publication_count`, plus an echoed `filters` object so clients can preserve applied triage state
- each deployment publication entry includes the persisted publication manifest, so clients can jump from deployment listing to run/paper/code assets directly

### `POST /api/projects/{project_id}/auto-research/{run_id}/resume`

- enqueues a `resume` job
- current behavior resumes from persisted checkpoint rather than silently repeating completed candidate/round work
- routes through the Goal 9 operator policy/action log; if a resume is already queued the command returns a noop instead of adding duplicate work
- returns the existing string `409` detail while a bridge-backed run is waiting for external result import, and structured policy error detail for other policy blocks such as stale artifacts, missing refs, approval state, or active leased/running work

### `POST /api/projects/{project_id}/auto-research/{run_id}/retry`

- enqueues a `retry` job for the existing run
- routes through the Goal 9 operator policy/action log, preserving previous artifacts, failure evidence, negative evidence, and parent attempt refs before a new queued attempt is created
- returns `409` with structured policy error detail when retry is not currently allowed

### `POST /api/projects/{project_id}/auto-research/{run_id}/cancel`

- requests cancellation for the current queued or running job
- also cancels runs that are currently parked on a waiting bridge session
- canceled runs fall to `canceled` and store a cancellation reason in `error`
- routes through the Goal 9 operator policy/action log and records terminal operator decision evidence instead of deleting prior queue or bridge state

## Current Downstream Surfaces

These are still available, but they are downstream of auto-research output rather than the mainline control plane:

- drafts
- review
- export
- evidence
- tutor / mentor related routes

## Current Contract Notes

- `run.json` remains the top-level compatibility snapshot
- idea briefs now persist separately under `autorresearch/briefs/<brief_id>/brief.json`
- idea briefs now carry hypothesis-bank and direction-selector state before any run is created
- idea briefs may also carry offline literature-scout and gap-miner state before run creation
- runs created from idea briefs preserve `brief_id`, `hypothesis_id`, and `direction_selection_reason`
- candidate-level manifests and artifacts are already persisted on disk
- successful publish export now also persists `publication_manifest.json` and `code_package.zip`
- publication manifests now also surface any materialized paper compile outputs so downstream deployment or browser sessions can consume compiled PDFs without unpacking the publish archive first
- the writing layer now also persists `narrative_report.md`, `claim_evidence_matrix.json`, `paper_plan.json`, `figure_plan.json`, `paper_revision_state.json`, `paper_compile_report.json`, `paper_revision_action_index.json`, and `paper_section_rewrite_index.json` before final paper generation
- completed runs now also persist `paper_sources/paper.md`, `paper_sources/revision_brief.md`, `paper_sources/revision_history.md`, `paper_sources/revision_actions.md`, `paper_sources/paper_compile_report.json`, `paper_sources/paper_revision_action_index.json`, `paper_sources/rewrite_packets/`, `paper_sources/build.sh`, `paper_sources/main.tex`, `paper_sources/references.bib`, `paper_sources/manifest.json`, and `paper_sources/checkpoints/` snapshots
- dedicated registry reads now exist for run, candidate, bundle-index, and grouped-view inspection
- bridge-backed runs now also persist `bridge/bridge_state.json` plus per-session `bridge/handoffs/<session_id>/` manifests, copied code, instructions, and expected/imported result payloads
- Phase 5 review/publish outputs are now persisted as run-local `review.json`, `review_loop.json`, and `publish_package.json`
- experiment artifacts now also preserve candidate-diversity metadata, robustness-aware portfolio decisions, family-aware significance metadata, power notes, and richer failed-config diagnostics
- Phase 6 operator-console reads now aggregate execution, bridge, registry, review, and publish state without requiring clients to rebuild that graph themselves
- operator console reads now also surface the latest persisted idea brief summary for project-level intake triage

## Next After Workstreams E/F

The following are the natural hardening steps after the numbered Phase 1-6 baseline:

- extend the paper pipeline with more automated rewrite execution beyond the current persisted revision ledgers, packets, and compile-oriented source package
- stronger recovery and multi-worker execution hardening at higher throughput

## Related Docs

- `docs/autoresearch-execution-plane.md`
- `docs/autoresearch-experiment-bridge.md`
- `docs/architecture.md`
- `PROJECT_PLAN.md`
