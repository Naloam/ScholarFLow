ScholarFlow Roadmap: Remaining Goals
====================================

Document Status
===============

- Updated: 2026-06-11.
- Completed and intentionally omitted from this file: Goal 1-12.
- Default next execution: finish Goal 13 without weakening gates or skipping tests.
- This file is the roadmap authority for the next `/goal` run.
- Keep this file focused on future work only. Do not re-add completed Goal 1-12 detail unless a regression in their artifacts, schemas, API/UI contracts, docs, or deterministic tests must be repaired.
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

- Goal 1-12 now provide the controlled research-loop skeleton, deterministic evaluation layer, operator control plane, external capability manifest, external evidence provenance, external import validation, runtime hardening, final-gate evidence-origin policy, long-running reliability state, and source-backed multi-project memory.
- ScholarFlow is roughly 88%-92% complete as an offline, deterministic, evidence-constrained research automation platform.
- ScholarFlow is roughly 45%-50% complete as a publication-grade autonomous scientist. The remaining gap is not paper text; it is human/compliance review, venue packaging, and release governance.

Current gap estimate:

- Controlled research-loop skeleton: 85%-90%.
  The main chain exists from idea to final publish decision, with evidence ledgers, lineage, reviewer/revision loop, package generation, deterministic evaluation, operator actions, external capability state, and evidence-origin gate policy.
- Operator, external capability, and long-running reliability control: 85%-90%.
  Goal 9, Goal 10, and Goal 11 added persisted operator controls, capability manifests, provenance, validation, blocker propagation, project state manifests, timelines, runbooks, attempt ledgers, branch/fork state, stale repair candidates, and migration blockers. Remaining work is release governance.
- Real external evidence/execution: 55%-65%.
  The system now has the hardening layer required to avoid fake external evidence: capability state, approval/budget policy, provenance/freshness, benchmark package validation, execution hash/runtime validation, and final-gate origin ceilings. Full live connector coverage, large real benchmarks, and production infrastructure remain outside the deterministic baseline.
- Long-running reliability: 75%-85%.
  Project state manifest, timeline, runbook, attempt ledger, branch/fork state, stale repair candidates, and migration policy are now typed, persisted, and visible through operator APIs/UI. Production-scale external queues/storage remain outside the deterministic baseline.
- Multi-project memory: 75%-85%.
  Goal 12 added typed source-backed discovery memory, currentness/reuse/privacy policy, deterministic store/index, query hints, and negative blocker memory. Production-scale vector/search services remain outside the deterministic baseline.
- Human review, compliance, venue, and release governance: 10%-20%.
  Final publish decision exists, but human approval, compliance checklist, venue adapters, signed/verifiable release packages, and final/non-final release controls remain future work.

Remaining Roadmap
=================

Default order:

1. Goal 13: Human Review, Compliance, Venue Adapter, And Release Packaging.

Goal 12 memory is complete in the deterministic baseline. Do not reimplement it unless a regression breaks its schemas, API/frontend contracts, docs, or tests.

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
- Goal 1-12 are complete. Do not reimplement completed goals unless a regression breaks their artifacts, schemas, API/UI contracts, docs, or deterministic tests.
- Default branch is master.
- docs/goal.md is the detailed roadmap authority.

Execution order:
1. Implement Goal 13 - Human Review, Compliance, Venue Adapter, And Release Packaging.

Goal 12 memory is already complete. Do not skip or weaken Goal 13 governance gates; if the goal cannot be completed safely in one run, update docs/goal.md with only the remaining future work and commit the completed scope.

Hard safety rules:
- Do not weaken publish gates, claim-evidence ledger behavior, artifact lineage, negative evidence, readiness blockers, operator policy checks, external capability policy, evidence-origin policy, or persisted artifact state.
- Do not treat fixture, toy, local smoke, deterministic replay, stale cache, memory hints, human approval, compliance approval, or venue export as publication-grade scientific evidence.
- Do not generate fake experiment outputs, fake provenance, fake source independence, fake literature support, fake compliance approval, fake human approval, or fake statistics.
- Memory may provide discovery hints only; current-project claims still require current-project validated artifacts and evidence ledgers.
- Human review, compliance, venue, and release actions must not convert a failed scientific final gate into a passed final gate.
- Required tests must be deterministic and must not require live network, paid LLM/API calls, GPUs, Docker daemon, external benchmark services, external vector DB, or external signing services.

Required implementation scope:
- Goal 13: human review workflow, compliance checklist, venue adapters, release archive hash/signature manifest, release API/operator UI, final/non-final export governance, docs/tests.

Testing rhythm:
- Run narrow deterministic pytest targets for each goal.
- After shared backend behavior changes, run cd backend && ../.venv/bin/pytest -q.
- After API/schema/frontend type changes, run cd frontend && npm run build.
- If operator/release browser flows change, run cd frontend && npm run e2e when feasible.
- Before finishing, run git diff --check.

Finish criteria:
- Update docs/api-reference.md and any relevant project docs for new API/schema/UI behavior.
- Update docs/goal.md so it contains only still-future work. If Goal 13 is complete, replace the roadmap with a concise completion/future-maintenance note and no stale goal backlog.
- Update AGENTS.md only if its current state or active roadmap would mislead the next session.
- Commit the completed scoped work. If all remaining goals are completed, use a message like Complete remaining research governance roadmap. Otherwise use a message for the completed earliest goal.
```
