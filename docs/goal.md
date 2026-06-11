ScholarFlow Roadmap: Remaining Goals
====================================

Document Status
===============

- Updated: 2026-06-11.
- Completed and intentionally omitted from this file: Goal 1-10.
- Default next execution: finish Goal 11, then Goal 12, then Goal 13 if the same `/goal` run can do so without weakening gates or skipping tests.
- This file is the roadmap authority for the next `/goal` run.
- Keep this file focused on future work only. Do not re-add completed Goal 1-10 detail unless a regression in their artifacts, schemas, API/UI contracts, docs, or deterministic tests must be repaired.
- `AGENTS.md` holds high-level collaboration and safety constraints. This file holds the detailed active roadmap and the next `/goal` prompt.

Long-Term Target
================

ScholarFlow is aiming at an evidence-constrained ARIS/FARS-style autonomous research system:

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

The differentiator remains evidence-constrained automation:

- claim-evidence ledgers;
- artifact lineage;
- benchmark/literature provenance;
- failure-driven replanning;
- negative evidence retention;
- reviewer simulation;
- bounded autonomous revision;
- operator-controlled long-running execution;
- publish gates that prevent unsupported claims.

If evidence is not strong enough, the system must preserve blockers, limitations, kill criteria, required follow-ups, and `final_publish_ready=false`.

How Far We Are From The Target
==============================

Short version:

- Goal 1-10 now provide the controlled research-loop skeleton, deterministic evaluation layer, operator control plane, external capability manifest, external evidence provenance, external import validation, runtime hardening, and final-gate evidence-origin policy.
- ScholarFlow is roughly 85%-90% complete as an offline, deterministic, evidence-constrained research automation platform.
- ScholarFlow is roughly 40%-45% complete as a publication-grade autonomous scientist. The remaining gap is not paper text; it is long-running reliability, cross-project memory with current-project revalidation, human/compliance review, venue packaging, and release governance.

Current gap estimate:

- Controlled research-loop skeleton: 85%-90%.
  The main chain exists from idea to final publish decision, with evidence ledgers, lineage, reviewer/revision loop, package generation, deterministic evaluation, operator actions, external capability state, and evidence-origin gate policy.
- Operator and external capability control: 75%-85%.
  Goal 9 and Goal 10 added persisted operator controls plus capability manifests, provenance, validation, and blocker propagation. Remaining work is long-running attempt history, branch/fork semantics, stale repair, and release governance.
- Real external evidence/execution: 55%-65%.
  The system now has the hardening layer required to avoid fake external evidence: capability state, approval/budget policy, provenance/freshness, benchmark package validation, execution hash/runtime validation, and final-gate origin ceilings. Full live connector coverage, large real benchmarks, and production infrastructure remain outside the deterministic baseline.
- Long-running reliability: 30%-40%.
  Persistence and fingerprints exist, but project timeline, runbook, attempt ledger, safe resume/retry/fork, stale repair, and migration policy remain future work.
- Multi-project memory: 10%-20%.
  Cross-project discovery memory, currentness policy, reuse restrictions, privacy/retention handling, and negative finding memory remain future work.
- Human review, compliance, venue, and release governance: 10%-20%.
  Final publish decision exists, but human approval, compliance checklist, venue adapters, signed/verifiable release packages, and final/non-final release controls remain future work.

Remaining Roadmap
=================

Default order:

1. Goal 11: Long-Running Research Reliability.
2. Goal 12: Multi-Project Knowledge And Literature Memory.
3. Goal 13: Human Review, Compliance, Venue Adapter, And Release Packaging.

The next `/goal` may attempt all remaining goals in one run, but must execute them in order. Do not implement Goal 12 before Goal 11 artifacts exist, and do not implement Goal 13 release governance before release inputs from Goal 11 and Goal 12 are represented clearly.

Fixed Start Audit For Every `/goal`
===================================

Every `/goal` session must begin with:

1. `git status --short --branch`
2. `git log --oneline -n 8`
3. Read `AGENTS.md`.
4. Read this file.
5. Read the active goal's key files.
6. Identify the boundary between completed Goal 1-10 artifacts and the remaining goal so completed work is not reimplemented.

Audit conclusions must be reflected in code artifacts, evaluation artifacts, readiness reports, docs, or deterministic tests. A chat-only audit is not enough.

Test Rhythm
===========

- For small backend changes, run `python -m py_compile` and a narrow pytest target first.
- After shared backend behavior changes, run `cd backend && ../.venv/bin/pytest -q`.
- After API/schema/frontend type changes, run `cd frontend && npm run build`.
- After Operator Console, workspace, release, or browser-flow changes, run `cd frontend && npm run e2e` when feasible.
- Before finishing a goal, run `git diff --check`.
- Required regression tests must be deterministic. They must not require live network, paid LLM calls, GPUs, Docker daemon availability, external signing services, or external benchmark services.

Global Safety Invariants
========================

- Do not weaken publish gates, claim-evidence ledger behavior, artifact lineage, negative evidence, readiness blockers, operator policy checks, external capability policy, evidence-origin policy, or persisted artifact state.
- Do not display review-ready, workshop, case-study, internal-report, or non-final packages as final-publish-ready.
- Do not treat fixture, toy, local smoke, deterministic replay, stale cache, or policy-blocked evidence as publication-grade evidence.
- Do not generate fake experiment outputs, fake provenance, fake source independence, fake literature support, fake compliance approval, fake human approval, or fake statistics.
- Do not downgrade unsupported domains into unrelated toy experiments.
- Evidence-producing repair actions can be marked completed only after the required artifact is actually produced or imported and validated.
- Single-run evidence must not be inflated into project-level claims.
- Every new durable artifact should have schema/version/fingerprint/parent refs, or explicitly document why it does not need them.
- A failed publication gate is a valid result. Do not bypass it for demo convenience.
- Operator, human-review, compliance, or venue actions may schedule, block, inspect, label, or record decisions; they must not manufacture evidence or final readiness.

Goal 11: Long-Running Research Reliability
==========================================

Objective
---------

Make multi-day, multi-attempt research projects first-class. Goal 11 does not add scientific claim power. It prevents evidence, lineage, blockers, approvals, capability state, and decisions from being lost during long runs, restarts, retries, resumes, imports, branches, forks, migrations, and revisions.

Non-Goals
---------

- Do not add new claim strength by relabeling old evidence.
- Do not silently repair stale or incompatible artifacts.
- Do not make resume/retry/cancel a frontend-only state change.
- Do not delete old failed attempts, negative evidence, or superseded artifacts.
- Do not require live network, Docker, paid APIs, external queues, or external storage for required tests.

Key Files To Read
-----------------

- `backend/services/autoresearch/repository.py`
- `backend/services/autoresearch/execution.py`
- `backend/services/autoresearch/operator_control.py`
- `backend/services/autoresearch/console.py`
- `backend/services/autoresearch/experiment_execution.py`
- `backend/services/autoresearch/project_paper_orchestrator.py`
- review/revision/submission/package/final-gate services under `backend/services/autoresearch/`
- Goal 10 external capability/evidence-origin services under `backend/services/autoresearch/`
- `backend/api/autoresearch.py`
- `backend/schemas/autoresearch.py`
- `backend/tests/test_autoresearch_regressions.py`
- Operator Console frontend files
- `frontend/src/api/types.ts`
- `frontend/src/api/client.ts`
- `docs/api-reference.md`

Phase 0: Persistence And Version Audit
--------------------------------------

Implementation requirements:

- Audit all project/run artifacts for:
  - schema version;
  - fingerprint/hash;
  - parent refs;
  - supersedes/superseded_by;
  - owning service;
  - reconstructability after restart;
  - migration status;
  - final-gate relevance;
  - evidence-origin classification where applicable.
- Identify artifacts missing version, fingerprint, or lineage.
- Define stale, migration-needed, fingerprint-mismatch, and unsafe-resume blockers.
- Add a project-level state manifest listing:
  - active artifacts;
  - stale artifacts;
  - superseded artifacts;
  - missing artifacts;
  - migration-needed artifacts;
  - unsafe-resume blockers;
  - current final-gate/package state;
  - rebuild timestamp and policy version.
- Persist the state manifest through repository helpers. API endpoints must not read/write ad hoc files.

Tests:

- Missing schema version blocks unsafe resume.
- Fingerprint mismatch blocks package/final gate.
- Superseded artifact no longer supports new claims but remains in lineage.
- State manifest rebuild is deterministic from repository artifacts.

Phase 1: Project Timeline And Runbook
-------------------------------------

Implementation requirements:

- Add versioned project timeline events for:
  - idea;
  - domain routing;
  - research brief;
  - literature scout;
  - benchmark/source validation;
  - hypothesis bank;
  - direction selection;
  - protocol;
  - execution/import;
  - evidence ledger;
  - manuscript/source package;
  - review;
  - revision;
  - submission package;
  - final decision;
  - external capability check;
  - operator action;
  - human/compliance placeholder event;
  - blocker/failure event.
- Each event must include:
  - event id;
  - event type;
  - timestamp;
  - actor/source;
  - artifact refs;
  - parent event refs;
  - policy version;
  - summary/status;
  - blockers/risks when relevant.
- Add a project runbook with:
  - next actions;
  - required approvals;
  - blocked actions;
  - repair candidates;
  - claim ceiling;
  - package/final-gate status;
  - kill criteria;
  - stale artifacts;
  - migration-needed artifacts;
  - owner/source refs.
- Operator Console should consume timeline/runbook instead of forcing users to infer next steps from raw artifacts.

Tests:

- Timeline deterministic order is stable.
- Runbook rebuilds from repository artifacts.
- Blocked project produces actionable next steps without fake evidence.
- Operator Console displays runbook/final-gate status from backend state.

Phase 2: Attempt Ledger And Retry/Resume Safety
-----------------------------------------------

Implementation requirements:

- Add an attempt ledger recording:
  - attempt id;
  - parent attempt id;
  - branch id when applicable;
  - action/job id;
  - trigger;
  - operator/user/system decision;
  - approval state;
  - budget state;
  - capability state snapshot;
  - inputs;
  - outputs;
  - failure classification;
  - repair action;
  - artifact refs;
  - negative evidence refs;
  - stale detection;
  - terminal status.
- Retry/resume must create a new attempt or explicitly update attempt state through a typed transition.
- Old failure evidence and negative evidence must remain immutable.
- Resume must validate artifact fingerprints, schema versions, capability state, approval state, budget state, selected branch, and final-gate blockers.
- Cancel/reject/timeout must become terminal attempt states with visible blockers.

Tests:

- Retry preserves old failed attempt.
- Resume is refused on stale artifacts or fingerprint mismatch.
- Cancel/reject appears in attempt ledger and runbook.
- Attempt ledger feeds operator console and API.
- Old negative evidence remains available after retry success.

Phase 3: Branching And Direction Forks
--------------------------------------

Implementation requirements:

- Add project branch/fork model:
  - branch id;
  - parent branch;
  - parent hypothesis/direction;
  - selected direction refs;
  - inherited evidence scope;
  - invalidated evidence;
  - branch-specific artifacts;
  - branch readiness;
  - branch claim ceiling;
  - branch final-gate blockers;
  - branch comparison summary.
- Forks must not reuse incompatible parent evidence for new claims.
- Branch comparison must distinguish:
  - performance;
  - evidence sufficiency;
  - literature/benchmark source sufficiency;
  - risk;
  - negative evidence;
  - claim ceiling;
  - final-gate blockers.
- Final gate must only consider selected branch artifacts unless cross-branch evidence has an explicit compatible scope.

Tests:

- Fork from selected direction creates branch lineage.
- Incompatible evidence is invalidated or downgraded.
- Branch comparison is deterministic.
- Final gate only considers selected branch artifacts.

Phase 4: Stale Repair And Migration Policy
------------------------------------------

Implementation requirements:

- Define stale artifact repair workflows:
  - revalidate;
  - migrate;
  - rerun;
  - reimport;
  - downgrade claim;
  - terminal blocker.
- Define schema migration policy:
  - supported migrations;
  - unsupported migrations;
  - migration artifact refs;
  - source/target schema version;
  - hash before/after;
  - policy version;
  - operator/reviewer visibility.
- Unsupported migration must block resume and final gate.
- Stale literature, benchmark, execution, package, release input, and paper-source artifacts must produce repair candidates rather than silent success.
- Migration records must be visible in timeline, runbook, attempt ledger, and package/release lineage.

Tests:

- Supported migration records before/after refs.
- Unsupported migration blocks resume/final gate.
- Stale literature/benchmark/execution artifacts produce repair candidates.
- Migration-needed state appears in operator console/runbook.

Goal 11 Completion Standard
---------------------------

- Project state manifest, timeline, runbook, attempt ledger, branch/fork state, stale repair, and migration policy are typed, persisted, and rebuildable.
- Retry/resume/fork do not lose old evidence, negative evidence, artifact lineage, blockers, operator decisions, or final-gate decisions.
- Stale/migration-needed artifacts cannot silently pass readiness or final gate.
- Operator Console consumes timeline/runbook/attempt ledger for long-running project inspection.
- Deterministic tests cover restart/reload, stale artifacts, migration blockers, retry/resume/fork safety, branch scoping, and final-gate preservation.

Goal 12: Multi-Project Knowledge And Literature Memory
======================================================

Objective
---------

Build source-backed cross-project memory as discovery infrastructure. Goal 12 is not a global truth database. Any memory item used to support a current project claim must be revalidated into current-project artifacts and evidence ledgers.

Non-Goals
---------

- Do not let memory directly satisfy current project claim evidence.
- Do not require a live vector database, paid embedding provider, or external search service for required tests.
- Do not reuse private, revoked, policy-blocked, or stale project material unless policy allows it and limitations are visible.
- Do not hide source limitations, negative findings, blockers, or currentness gaps when memory hints are reused.
- Do not allow memory to bypass Goal 10 evidence-origin or Goal 11 stale/migration policy.

Key Files To Read
-----------------

- `backend/services/autoresearch/repository.py`
- `backend/services/autoresearch/literature_scout.py`
- `backend/services/autoresearch/literature_connectors.py`
- `backend/services/autoresearch/domain_evidence.py`
- `backend/services/autoresearch/project_paper_orchestrator.py`
- `backend/services/autoresearch/evaluation_cases.py`
- Goal 10 external evidence/capability services
- Goal 11 timeline/runbook/attempt services
- `backend/api/autoresearch.py`
- `backend/schemas/autoresearch.py`
- `backend/tests/test_autoresearch_regressions.py`
- `frontend/src/api/types.ts`
- `frontend/src/api/client.ts`
- relevant workspace/operator UI files
- `docs/api-reference.md`

Phase 0: Memory Scope And Provenance
------------------------------------

Implementation requirements:

- Define memory item types:
  - paper;
  - method;
  - dataset;
  - metric;
  - benchmark;
  - reported result;
  - implementation;
  - negative finding;
  - blocker;
  - project conclusion;
  - reviewer finding;
  - compliance or release caveat.
- Each memory item must include:
  - memory id;
  - schema version;
  - source project id;
  - source run id or branch id when applicable;
  - source artifact ref;
  - source fingerprint;
  - extraction timestamp;
  - source date/version;
  - evidence grade;
  - source class;
  - extraction level;
  - currentness status;
  - limitations;
  - reuse policy;
  - privacy/retention policy;
  - negative/blocker status when relevant.
- Memory records must preserve source refs and cannot be edited into unsupported conclusions.

Tests:

- Memory item cannot be created without source artifact/fingerprint.
- Memory item records limitations and currentness.
- Private or revoked source material is excluded or blocked by policy.

Phase 1: Deterministic Memory Store And Index
---------------------------------------------

Implementation requirements:

- Add repository-local memory store/index that supports deterministic rebuild, export, and import.
- The required baseline can use structured JSON/index files or existing repository persistence. No external vector DB is required.
- Index dimensions should include:
  - domain;
  - method;
  - dataset;
  - metric;
  - benchmark;
  - paper/source ids;
  - claim/result type;
  - blocker/failure type;
  - evidence grade;
  - currentness;
  - reuse eligibility.
- Memory export/import must preserve hashes and policy fields.
- Dedupe should prefer stable source ids/fingerprints over text-only matching.

Tests:

- Rebuild produces stable memory index.
- Duplicate source fingerprints dedupe deterministically.
- Export/import preserves source refs and hashes.
- Memory store works without live network or vector DB.

Phase 2: Memory Query Integration
---------------------------------

Implementation requirements:

- Integrate memory query as discovery hints for:
  - idea/domain routing;
  - research brief;
  - literature scout;
  - related-system discovery;
  - baseline/benchmark suggestion;
  - novelty-risk detection;
  - method/dataset/metric selection;
  - reviewer concern prediction.
- Query results must be labeled as memory hints and include:
  - source refs;
  - currentness;
  - limitations;
  - reuse requirements;
  - required current-project validation actions.
- Current project claims can use memory only after revalidation into current-project literature/benchmark/execution/evidence artifacts.

Tests:

- Memory hint appears in brief/scout without becoming claim evidence.
- Current-project claim remains unsupported until revalidated evidence exists.
- Stale memory adds risk/follow-up, not direct support.
- Memory query output is deterministic.

Phase 3: Currentness, Privacy, And Reuse Policy
-----------------------------------------------

Implementation requirements:

- Define memory currentness states:
  - fresh;
  - aging;
  - stale;
  - revoked;
  - unknown.
- Define reuse policy states:
  - discovery_only;
  - revalidate_required;
  - internal_only;
  - blocked;
  - expired.
- Memory query must filter or label items by policy.
- Literature/source memory must track retrieval/extraction date and source observation fingerprint.
- Project-private, compliance-blocked, or user-restricted artifacts must not leak into unrelated projects.

Tests:

- Revoked memory is not returned as a usable hint.
- Stale memory creates revalidation action.
- Internal-only memory is not exported in public release materials.
- Policy filtering is deterministic and visible in API output.

Phase 4: Negative Finding And Blocker Memory
--------------------------------------------

Implementation requirements:

- Store prior negative findings and blockers as memory:
  - failed execution class;
  - invalid benchmark/source issue;
  - unsupported domain;
  - contradictory literature;
  - insufficient statistics;
  - final-gate blocker;
  - compliance/release blocker.
- Negative memory can warn, add a follow-up, add a kill criterion, or suggest repair.
- Negative memory cannot silently pre-block a current project without current-project validation.
- Runbook and reviewer simulation should surface relevant prior blockers as risks, not as current evidence.

Tests:

- Prior blocker becomes risk/follow-up in a related project.
- Prior blocker does not directly fail current final gate without current evidence.
- Negative memory is included in memory index and can be filtered by type.

Goal 12 Completion Standard
---------------------------

- Cross-project memory has typed schema, provenance, source refs, currentness, reuse policy, privacy/retention policy, deterministic store/index, API surface, and tests.
- Memory assists discovery and risk detection but never directly supports current-project claims.
- Revalidation requirements are explicit and visible in brief/scout/runbook outputs.
- Negative findings and blockers are preserved as reusable risk signals.

Goal 13: Human Review, Compliance, Venue Adapter, And Release Packaging
=======================================================================

Objective
---------

Add the final governance layer: human review, compliance checks, venue-specific package shaping, and verifiable release export. Goal 13 must not bypass scientific final gates; it records and enforces the human/compliance/release decisions around them.

Non-Goals
---------

- Do not let human approval turn a failed scientific final gate into a passed final gate.
- Do not hide non-final status in exported packages.
- Do not require an external signing service for required tests.
- Do not implement venue-specific formatting at the expense of evidence/final-gate correctness.
- Do not remove blockers, negative evidence, limitations, or claim ceilings from release packages.

Key Files To Read
-----------------

- `backend/services/autoresearch/repository.py`
- `backend/services/autoresearch/project_paper_orchestrator.py`
- submission/package/final-gate services under `backend/services/autoresearch/`
- Goal 10 evidence-origin/capability services
- Goal 11 timeline/runbook/attempt services
- Goal 12 memory policy services
- `backend/api/autoresearch.py`
- `backend/schemas/autoresearch.py`
- `backend/tests/test_autoresearch_regressions.py`
- `frontend/src/api/types.ts`
- `frontend/src/api/client.ts`
- Operator/release UI files
- `docs/api-reference.md`

Phase 0: Human Review Workflow
------------------------------

Implementation requirements:

- Add human review records with:
  - review id;
  - schema version;
  - reviewer role/id;
  - reviewed artifact refs;
  - reviewed artifact fingerprints;
  - comments;
  - requested changes;
  - approval/rejection;
  - policy exceptions;
  - timestamp;
  - final decision linkage;
  - conflict/notes when needed.
- Human review must be persisted and included in timeline, runbook, package lineage, and release lineage.
- Human approval can approve non-final export only when clearly labeled.
- Human approval cannot change failed final gate into passed final gate.
- Rejection or requested changes must create visible runbook actions and release blockers.

Tests:

- Human approval records artifact refs and fingerprints.
- Human rejection blocks release export.
- Human exception appears in release package and cannot hide scientific blocker.
- Non-final export requires explicit label and human approval.

Phase 1: Compliance Checklist
-----------------------------

Implementation requirements:

- Add compliance checklist covering:
  - dataset license;
  - paper/source license;
  - code license;
  - dependency license;
  - privacy/PII;
  - model/API terms;
  - paid service disclosure;
  - benchmark terms;
  - venue policy;
  - artifact retention;
  - external source attribution;
  - reproducibility package policy.
- Each checklist item must link source artifacts, source manifests, or explicit blockers.
- Compliance status must feed release gate.
- Compliance failure blocks final release and blocks non-final public release unless a policy-approved internal-only exception exists.
- Compliance state must appear in runbook and operator/release API.

Tests:

- Missing license blocks release.
- PII/privacy blocker is visible.
- Compliance checklist is included in release archive manifest.
- Compliance exception is auditable, scoped, and cannot erase scientific blockers.

Phase 2: Venue Adapter And Submission Metadata
----------------------------------------------

Implementation requirements:

- Support venue profiles:
  - internal report;
  - workshop;
  - conference;
  - arXiv/preprint;
  - custom venue profile.
- Each profile defines:
  - required files;
  - anonymity;
  - metadata;
  - supplemental policy;
  - page/format constraints;
  - artifact naming;
  - final/non-final export label;
  - compliance requirements.
- Venue adapter must validate required assets and metadata.
- Venue adapter cannot bypass final publish decision.
- Venue package manifest must include final/non-final status, blockers, limitations, and lineage refs.

Tests:

- Workshop profile can export non-final package with label.
- Final conference profile requires scientific final gate plus human/compliance approval.
- Missing required venue file blocks export.
- Venue metadata appears in release manifest.

Phase 3: Release Archive Signing And Export
-------------------------------------------

Implementation requirements:

- Add release package containing:
  - release id/version;
  - generated_at;
  - release type;
  - final/non-final status;
  - final decision ref;
  - human review refs;
  - compliance refs;
  - venue metadata;
  - artifact integrity audit;
  - hashes/signature manifest;
  - source package refs;
  - lineage archive;
  - reproducibility checklist;
  - limitations appendix;
  - memory export policy summary;
  - blockers if non-final.
- Archive signing may be deterministic hash manifest only; no external signing service is required.
- Release export must be guarded:
  - final release requires final gate pass;
  - non-final release requires explicit label and human approval;
  - public release requires compliance pass;
  - internal-only release requires scoped policy exception when compliance is incomplete.
- Any rebuild must either reproduce the same hash or create a new release version with reason.

Tests:

- Release archive is reconstructable.
- Hash/signature manifest verifies package contents.
- Non-final release is labeled and cannot be mistaken for final publish.
- Final release is blocked when final decision is false.
- Release hash changes or version increments when source package changes.

Phase 4: Release API And Operator UI
------------------------------------

Implementation requirements:

- Expose typed API for:
  - human review records;
  - compliance checklist;
  - venue profiles;
  - release readiness;
  - release export;
  - release manifest inspection.
- Operator/release UI must show:
  - scientific final gate status;
  - human review status;
  - compliance status;
  - venue profile status;
  - final/non-final export label;
  - blockers;
  - release manifest/hash.
- UI must disable final release actions when backend policy disallows them.

Tests:

- API returns release readiness with scientific/human/compliance/venue statuses.
- UI cannot imply final readiness when backend final gate is false.
- Non-final label appears in release view and export metadata.

Goal 13 Completion Standard
---------------------------

- Human review, compliance, venue adapter, release archive, release API, and release UI have typed schema, repository persistence, docs, and deterministic tests.
- Release archive is rebuildable, verifiable, and traceable.
- Final publish gate remains the scientific readiness hard gate.
- Non-final exports are clearly labeled and not shown as final-publish-ready.
- Compliance and human-review blockers are explicit and auditable.

Cross-Goal Completion Standard
==============================

The remaining roadmap is complete only when all of the following are true:

- Goal 11 long-running state can be reconstructed after restart from persisted artifacts.
- Goal 12 memory can provide source-backed discovery hints without becoming direct current-project claim evidence.
- Goal 13 release governance can export final and non-final packages with correct gates, labels, hashes, compliance, and human review.
- Backend schemas, frontend types/client, API docs, and operator/release UI are aligned.
- Deterministic backend tests pass.
- Frontend build passes after API/type/UI changes.
- E2E tests pass when operator or release browser flows changed, or a clear blocker is documented.
- `git diff --check` passes.
- A scoped commit records the completed work.

AGENTS.md And Skills Decision
=============================

- `AGENTS.md` should only keep high-level current state, active roadmap, build/test commands, and safety constraints.
- This file is the detailed roadmap authority.
- No repository-local skill is currently required.
- Consider adding a skill only if long-running research reliability audit, memory provenance audit, or release governance audit becomes a repeated workflow across multiple future projects.

Next `/goal` Prompt
===================

Copy this prompt into the next conversation:

```text
/goal

Goal: finish all remaining ScholarFlow roadmap work in docs/goal.md if feasible in one run.

Start by executing:
1. git status --short --branch
2. git log --oneline -n 8
3. Read AGENTS.md
4. Read docs/goal.md

Current baseline:
- Goal 1-10 are complete. Do not reimplement completed goals unless a regression breaks their artifacts, schemas, API/UI contracts, docs, or deterministic tests.
- Default branch is master.
- docs/goal.md is the detailed roadmap authority.

Execution order:
1. Implement Goal 11 - Long-Running Research Reliability.
2. If Goal 11 is complete and verified, implement Goal 12 - Multi-Project Knowledge And Literature Memory.
3. If Goal 12 is complete and verified, implement Goal 13 - Human Review, Compliance, Venue Adapter, And Release Packaging.

Do not skip ahead. If a later goal needs an artifact from an earlier goal, implement the earlier artifact first. If all three goals cannot be completed safely in one run, finish the earliest incomplete goal, update docs/goal.md with only the remaining future work, and commit the completed scope.

Hard safety rules:
- Do not weaken publish gates, claim-evidence ledger behavior, artifact lineage, negative evidence, readiness blockers, operator policy checks, external capability policy, evidence-origin policy, or persisted artifact state.
- Do not treat fixture, toy, local smoke, deterministic replay, stale cache, memory hints, human approval, compliance approval, or venue export as publication-grade scientific evidence.
- Do not generate fake experiment outputs, fake provenance, fake source independence, fake literature support, fake compliance approval, fake human approval, or fake statistics.
- Memory may provide discovery hints only; current-project claims still require current-project validated artifacts and evidence ledgers.
- Human review, compliance, venue, and release actions must not convert a failed scientific final gate into a passed final gate.
- Required tests must be deterministic and must not require live network, paid LLM/API calls, GPUs, Docker daemon, external benchmark services, external vector DB, or external signing services.

Required implementation scope:
- Goal 11: project state manifest, timeline, runbook, attempt ledger, retry/resume/fork safety, branch comparison, stale repair, migration policy, API/frontend/docs/tests.
- Goal 12: memory item schema, provenance/currentness/reuse/privacy policy, deterministic memory store/index, memory query integration as discovery hints, negative finding/blocker memory, API/frontend/docs/tests.
- Goal 13: human review workflow, compliance checklist, venue adapters, release archive hash/signature manifest, release API/operator UI, final/non-final export governance, docs/tests.

Testing rhythm:
- Run narrow deterministic pytest targets for each goal.
- After shared backend behavior changes, run cd backend && ../.venv/bin/pytest -q.
- After API/schema/frontend type changes, run cd frontend && npm run build.
- If operator/release browser flows change, run cd frontend && npm run e2e when feasible.
- Before finishing, run git diff --check.

Finish criteria:
- Update docs/api-reference.md and any relevant project docs for new API/schema/UI behavior.
- Update docs/goal.md so it contains only still-future work. If Goal 11-13 are all complete, replace the roadmap with a concise completion/future-maintenance note and no stale goal backlog.
- Update AGENTS.md only if its current state or active roadmap would mislead the next session.
- Commit the completed scoped work. If all remaining goals are completed, use a message like Complete remaining research governance roadmap. Otherwise use a message for the completed earliest goal.
```
