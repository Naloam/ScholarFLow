ScholarFlow Roadmap Status
==========================

Document Status
===============

- Updated: 2026-06-11.
- Completed in the deterministic baseline: Goal 1-13.
- No active roadmap goal remains in this file.
- Do not re-add completed goal detail unless a regression breaks artifacts, schemas, API/UI contracts, docs, or deterministic tests.

Target Loop
===========

ScholarFlow is an evidence-constrained ARIS/FARS-style autonomous research system:

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
-> human/compliance/venue release governance

Completed Baseline
==================

The current offline deterministic baseline includes:

- controlled idea-to-run orchestration;
- domain routing, literature/gap validation, and conservative claim ceilings;
- experiment planning, deterministic execution/import contracts, and evidence ledgers;
- artifact registries, lineage, negative evidence retention, and repair/replan loops;
- paper drafting, reviewer simulation, bounded revisions, and final publish gates;
- operator controls, capability manifests, long-running reliability state, timelines, runbooks, attempt ledgers, and branch/fork safety;
- source-backed multi-project memory as discovery hints only;
- Goal 13 human review, compliance checklist, venue adapter, release readiness, verifiable release archive/hash manifest, release API, and Operator Console release governance.

Release Governance Invariants
=============================

- Human approval cannot turn `final_publish_ready=false` into a final release.
- Compliance approval or scoped exceptions cannot erase scientific blockers.
- Non-final exports must be explicitly labeled and must preserve scientific blockers/limitations.
- Public release requires compliance pass.
- Internal-only non-final release with incomplete compliance requires scoped, auditable policy exceptions.
- Final release requires scientific final gate pass, human approval, compliance pass, and a valid venue profile.
- Goal 12 memory remains discovery-only and cannot satisfy current-project claim evidence.

Future Maintenance
==================

Future work should focus on production hardening rather than redoing completed goals:

- live connector coverage and larger real benchmark integrations under the existing provenance policy;
- production queue/storage/signing infrastructure, while keeping deterministic hash-manifest export in tests;
- deeper venue-specific formatting adapters that do not weaken final-gate evidence constraints;
- additional browser E2E coverage for release-governance workflows;
- regression repairs when schemas, API/frontend contracts, docs, or deterministic tests drift.
