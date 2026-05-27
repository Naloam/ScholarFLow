# API Reference

This document focuses on the current auto-research API surface.

## Current Auto-Research Endpoints

### `POST /api/projects/{project_id}/auto-research/ideas`

- converts a user idea into a persisted research brief instead of creating a run
- accepts `idea`, optional `domain`, optional `resource_budget`, optional `target_tier`, and flags for `allow_web` / `allow_experiments`
- returns a structured brief with multiple research directions, selection reasoning, feasibility assessment, and kill criteria

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
- returns search queries, structured paper metadata, source/cache statuses, similar-paper risk signals, known baseline/SOTA notes, experimentally testable gap candidates, and whether the idea needs a changed research question or experiment design

### `POST /api/projects/{project_id}/auto-research/ideas/{brief_id}/experiment-factory`

- builds a deterministic experiment-factory plan from the selected hypothesis, or from an explicit `hypothesis_id` query param
- returns baseline, candidate-method, ablation, seed, and sweep jobs with commands/configs, inputs, outputs, dependencies, retry policy, resource estimates, and failure-handling guidance
- does not execute jobs or require GPU/network access

### `POST /api/projects/{project_id}/auto-research/ideas/{brief_id}/run`

- creates and enqueues an auto-research run from the selected hypothesis, or from an explicit `hypothesis_id`
- preserves `brief_id`, `hypothesis_id`, and `direction_selection_reason` on the run snapshot
- accepts optional run budget overrides for `max_rounds`, `candidate_execution_limit`, `queue_priority`, and `execution_profile`
- returns `{ "id": "<run_id>" }`

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
- today this is still the main read surface for completed runs

### `POST /api/projects/{project_id}/auto-research/{run_id}/experiment-factory`

- builds an executable experiment-factory plan for an existing run
- reuses the run's linked `brief_id` / `hypothesis_id` when available, and falls back to run spec metadata otherwise
- returns the same job contract as the idea-level factory endpoint

### `POST /api/projects/{project_id}/auto-research/{run_id}/experiment-factory/toy-execute`

- executes the deterministic toy factory backend for the run's factory plan
- persists `experiment_factory_plan.json`, `experiment_factory_environment_manifest.json`, `experiment_factory_materialized_jobs.json`, `artifact.json`, `evidence_ledger.json`, and `experiment_factory_repair_plan.json`
- marks the run `done` and returns the execution plan, environment manifest, materialized jobs, result artifact, evidence ledger, and repair plan
- repair actions distinguish missing baseline evidence, missing ablation evidence, insufficient seed count, and failed rerun needs

### `PATCH /api/projects/{project_id}/auto-research/{run_id}/controls`

- patches the persisted run request snapshot for future scheduling/budget changes
- currently supports `max_rounds`, `candidate_execution_limit`, and `queue_priority`
- updates queued job priority in the execution plane when the run still has queued work

### `GET /api/projects/{project_id}/auto-research/{run_id}/execution`

- returns execution-plane state for the run
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
- operators can inspect queue bottlenecks, stale-worker posture, and recent recoveries without reading `queue.json`

### `GET /api/projects/{project_id}/auto-research/project-paper`

- builds a deterministic project-level paper orchestration snapshot
- reads idea briefs, selected runs, cross-run meta-analysis, run-level evidence ledgers, claim ledgers, and reviewer simulations when present
- returns a project conclusion ledger split into stable conclusions, conditional conclusions, negative findings, failed hypotheses, and limitations
- returns claim traces for every core project-level claim, with run IDs and evidence refs
- decides whether the project should write no paper, a single-run technical report, a workshop candidate, or a conference candidate
- prevents single-run evidence from being presented as a full project-level paper and blocks project-level publish readiness when strong claims lack run-level evidence

### `GET /api/projects/{project_id}/auto-research/evaluation-cases`

- returns the internal evaluation-case suite for idea-to-paper validation
- includes five deterministic cases: toy, medium benchmark, literature-heavy, ablation-heavy, and failed-hypothesis
- the toy case runs end-to-end through brief, scout, hypothesis selection, experiment factory, evidence ledger, and paper/review package materialization
- exposes the evaluation metrics used to judge idea-to-brief completeness, hypothesis selection, novelty risk detection, experiment executability, evidence consistency, reviewer readiness, and final publish correctness

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
- final publish readiness now also requires the compile-oriented paper source package to remain intact (`build.sh`, `main.tex`, `references.bib`, `manifest.json`, and the compile report itself)
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
- now returns `409` while a bridge-backed run is still waiting for external result import

### `POST /api/projects/{project_id}/auto-research/{run_id}/retry`

- enqueues a `retry` job for the existing run

### `POST /api/projects/{project_id}/auto-research/{run_id}/cancel`

- requests cancellation for the current queued or running job
- also cancels runs that are currently parked on a waiting bridge session
- canceled runs fall to `canceled` and store a cancellation reason in `error`

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
