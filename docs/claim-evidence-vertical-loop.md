# Claim-Evidence Vertical Loop

This is the first ScholarFlow vertical scenario to push from a system demo toward a real research result.

## Target

Build an evidence-constrained scientific writing loop:

1. A user proposes an idea for scientific writing agents.
2. ScholarFlow narrows it to claim-evidence retrieval and verification.
3. Literature scout identifies prior scientific claim verification and IR work.
4. Experiment factory runs claim-evidence retrieval baselines and ledger-aware variants.
5. Results populate the evidence ledger and claim-evidence matrix.
6. Paper writer drafts only evidence-supported claims.
7. Reviewer/revision loop demotes unsupported claims or queues bounded repair.
8. Submission package includes manuscript, paper sources, evidence index, reproducibility checklist, reviewer response, lineage archive, supplemental artifacts, benchmark card, code package, and publication manifest.

The central research question is:

> Can claim-evidence ledger-guided retrieval and repair reduce unsupported claims in autonomous scientific writing without requiring large-model training?

## Dataset Ladder

1. `frozen_claim_evidence_reranking`
   - Deterministic local fixture.
   - Used for CI and offline development.
   - Must never be treated as publication-grade evidence by itself.
   - General idea intake now reaches this path through the `claim_evidence_retrieval_v1` domain template when the idea matches claim-evidence retrieval / verification signals.
2. BEIR-style SciFact adapter
   - Local/cache-only fixture first, then optional downloaded/cache-backed corpus.
   - Metrics: MRR, Recall@1, nDCG@10, Recall@10.
3. SciFact / SciFact-Open style evidence verification
   - Adds support/refute/not-enough-evidence routing.
   - Metrics: evidence retrieval recall, support classification accuracy, unsupported-claim detection precision, abstention accuracy.

Primary references:

- SciFact: https://arxiv.org/abs/2004.14974
- BEIR: https://arxiv.org/abs/2104.08663
- SciFact-Open: https://arxiv.org/abs/2210.13777

## Method Ladder

1. Random ranker.
2. Lexical overlap / TF-IDF / BM25-style baseline.
3. Bigram or phrase-aware reranker.
4. Ledger-aware reranker that boosts evidence passages tied to claim type, artifact type, citation need, and support status.
5. Abstention and repair router:
   - supported: attach evidence and cite.
   - weak: downgrade claim strength.
   - missing: queue retrieval repair or mark limitation.
   - contradiction: flag reviewer issue and block publish.

## Acceptance Criteria

The vertical loop is complete only when all of the following are true:

1. A deterministic offline evaluation case exists and reaches a paper/review package.
2. Repository-local SciFact verification and retrieval frozen benchmark paths exist and can run without live network.
3. Runner outputs include MRR, Recall@1, nDCG@10 or Recall@10, and evidence coverage.
4. Claim-evidence ledger records retrieved evidence, missing evidence, and repair routing.
5. Paper draft cites persisted literature/evidence and does not promote unsupported claims.
6. Reviewer/revision loop can demote or repair at least one unsupported claim automatically.
7. Submission package contains claim-evidence index, reproducibility assets, supplemental artifacts, code package, benchmark card, and publication manifest.
8. Full backend tests and frontend build pass.

## Milestones

### V1: Evaluation Contract

- Add `claim_evidence_vertical_task` to internal evaluation cases.
- Route it through the existing frozen claim-evidence benchmark.
- Keep it deterministic and CI-safe.

### V2: Real Benchmark Adapter

- Add cache-backed SciFact and BEIR-style dataset loaders, including repository-local frozen snapshot paths for CI.
- Keep network disabled in tests.
- Add fixture tests for parsing corpus, queries, qrels, and metrics.

Current implementation:

- `beir_json` loads BEIR-style `queries` / `corpus` / `qrels` payloads.
- `scifact_json` loads SciFact-style `claims` / `corpus` / `evidence` payloads.
- Both paths can read from `BenchmarkSource.file_path`, allowing CI and local runs to use cached fixtures without live network.
- SciFact fixtures preserve supported/refuted/not-enough-info labels, including not-enough-info claims with no gold evidence document.
- IR runner output now reports MRR, Recall@1, nDCG@10, Recall@10, evidence coverage, claim-verification accuracy, unsupported-claim precision/recall, abstention accuracy, and per-query objective failure cases for paper analysis.
- The IR search ladder includes `ledger_aware_reranker_search`, which combines IDF, bigram overlap, and transparent claim/citation/artifact/experiment/review cue alignment.
- Retrieval failure cases are converted into deduplicated review-loop repair actions such as claim downgrades or literature refreshes.
- Claim-evidence IR runs now emit a workshop-style vertical package with manuscript section requirements, a per-query retrieval evidence ledger, claim-evidence index entries, reproducibility assets, limitations, and reviewer-response actions.
- The project-level paper orchestrator can now build a claim-evidence technical report / workshop candidate from the cached vertical run, preserve retrieval-ledger support and missing-evidence limitations, and prevent single-run evidence from being promoted to a full project-level claim.
- Project-level bounded revision actions now start from persisted `project_review_findings.json` reviewer-simulator findings, materialize automatic claim downgrades / retrieval-repair routes, write `project_revision_application.json`, produce action-level `project_rereview_report.json` records with original findings, repair outputs, residual/new blockers, claim-downgrade status, and recommendations, and keep unsupported evidence downgraded instead of promoting it.
- Project-level revision actions now also create bounded repair routes for weak literature coverage, missing benchmark provenance, insufficient benchmark scale, and insufficient deterministic statistics. Claim-evidence downgrade actions are auto-materialized as manuscript downgrades. Literature-refresh actions now execute a deterministic support-index repair from structured cached/network scout evidence when at least two non-fixture sources are present; fixture-only literature is marked `blocked` and remains a final-publish blocker. Benchmark-provenance actions now execute a deterministic provenance repair index and only complete for selected runs whose benchmark profiles already pass publication-grade provenance/eligibility checks; toy, fixture, under-scale, or missing-provenance benchmarks remain blocked. Benchmark-scale and statistics repair actions now execute a deterministic experiment repair index and only complete when persisted run artifacts carry publication-eligible scale, aggregate/significance evidence, and linked execution/import replay outputs.
- Project-level submission packages now include `submission_manifest.json`, `reproducibility_checklist.md`, `reviewer_response.md`, `project_review_findings.json`, `repair_execution_log.json`, `claim_evidence_index.md`, `retrieval_evidence_ledger.json`, `lineage_archive.json`, `literature_support_index.json`, `paper_compiler_evidence.json`, `publication_evidence_index.json`, `publication_readiness_report.json`, `supplemental_artifacts.json`, `benchmark_card.json`, `benchmark_provenance_manifest.json`, `benchmark_provenance_repair_index.json`, `statistics_report.json`, `experiment_repair_index.json`, `negative_evidence_report.json`, `offline_publication_case.json`, `offline_publication_audit.json`, `code_package.zip`, and `publication_manifest.json`.
- Project submission manifest assets now carry source action, source run ids, source evidence refs, readiness contribution, hashes, and missing status so package lineage can be audited from the manifest alone. `publication_manifest.json` mirrors that role-level asset ledger and marks its own self-referential file hash with an explicit integrity note.
- `publication_manifest.json` now also includes a readiness-decision trace with failed checks, blockers, required follow-ups, kill criteria, claim ceiling, and evidence refs so final-publish blocking can be audited from the final package manifest.
- `experiment_repair_index.json` records execution source classification, imported replay run ids, materialized execution run ids, output artifact refs, environment manifest ids/fingerprints, failed materialized job classifications, and residual blockers so project-level repair evidence can be traced back to run-level execution or imported-result replay artifacts. It now also carries an `execution_evidence_ledger` with per-run capsules for command/import paths, runtime contracts, dependency manifests, input benchmark provenance, method configs, method outputs, method-ladder artifact refs, metrics/evidence/negative-evidence refs, repair action linkage, and deterministic fingerprints. Project compiler evidence, statistics reports, and readiness reports repeat that execution coverage so statistics cannot be treated as complete without linked execution/import replay artifacts.
- `negative_evidence_report.json` retains negative results, failed trials, retrieval misses, unsupported claim gaps, project negative findings, and blocked repair evidence as package-level evidence; blocking entries keep final publish blocked instead of being hidden by the manuscript compiler. It also audits Goal 1 Phase 6 taxonomy coverage through required, conditional, covered, missing, per-category count, and per-category entry-ref fields. `runtime_failure` remains conditional on an actual runtime/process failure artifact, while missing required categories remain final-publish blockers or required follow-ups.
- `retrieval_evidence_ledger.json` aggregates selected-run retrieval ledger entries and retrieval-ledger artifact outputs into a project-level package asset so claim-evidence retrieval support can be audited without opening individual run folders.
- `literature_support_index.json` now records FARS/ARIS related-system coverage from cached/imported literature metadata and known-SOTA fields, and explicitly marks missing coverage as a limitation instead of inventing related-work support.
- `offline_publication_case.json` records the fixed claim-evidence publication-case idea, research question, brief/hypothesis/benchmark/experiment chain, full method ladder, expected metrics, repair triggers, output package roles, and evidence classification for real/imported/frozen sources versus internal fixtures. The ladder now includes random, lexical overlap, BM25/TF-IDF-style retrieval, phrase/bigram-aware retrieval, ledger-aware retrieval, abstention/repair routing, no-ledger ablation, retrieval-only/no-verification ablation, and repair-router-disabled ablation.
- The Goal 2 idea-to-paper path now records domain routing in the research brief, evaluation trace, offline publication case, readiness report, and Operator Console. Claim-evidence ideas route through `claim_evidence_retrieval_v1`; unsupported ideas are saved as blocked audit records with no generated hypothesis bank or experiment outputs. The route does not weaken Goal 1 readiness: review bundles and final-publish candidates still require provenance, statistics, source-independence, negative evidence, lineage, and publish-gate checks.
- The Goal 2B generalized domain package path now carries domain literature strategy/results, benchmark resolver output, experiment protocol, readiness status, and claim ceiling through the brief, scout, factory plan/execution, project package, Operator Console, and evaluation traces. Claim-evidence ideas continue to use the SciFact frozen-snapshot replay path, while RAG/citation-faithfulness and lightweight ML/NLP domains remain review-only or blocked unless real literature, benchmark provenance, execution/statistics, and negative-evidence requirements are satisfied.
- `offline_publication_audit.json` records the Phase 1 capability and remaining-breakpoint audit across literature refresh, benchmark snapshots, execution/import replay, statistics, negative evidence, rereview, and package completeness. Its top-level `fixed_goal_audit` records the mandatory Goal 1 audit commands, `docs/goal.md` source, audited key-file list/scopes, artifact destinations, and the artifact conclusion that package plumbing is complete while final publish remains evidence-blocked. Its `final_publish_gap_audit.phase1_requirements` now turns each Goal 1 Phase 1 question into a structured record with status, evidence refs, blockers, engineering/scientific classification, follow-ups, kill criteria, scope limitation, and details, including independent `benchmark_schema_coverage`, `benchmark_source_observation_coverage`, and `benchmark_source_independence` requirements rather than burying schema, observation-count, or same-release source limits inside source-grade prose. Missing cross-source benchmark evidence and scoped statistics remain scientific evidence gaps, while package artifact completeness is separately audited so review-ready bundles are not blocked by hidden manifest plumbing. Its final-publish gap audit mirrors Phase 6 negative-evidence coverage and frozen/imported benchmark source-lineage records, including source locator, revision/license, materialized local path, source and record fingerprints, parent source dataset metadata, sample/split counts, split/label distributions, query/document/evidence/relevance observation counts, publication/final-candidate eligibility and blockers, snapshot record counts, materialized counts, source-independence audit, and unmaterialized run ids, so missing negative categories or source-provenance limits can be traced without opening only `benchmark_provenance_manifest.json`.
- The Operator Console `publication_case` now mirrors the same benchmark schema coverage/blockers, benchmark source-observation coverage/blockers, benchmark final-candidate coverage/blockers, benchmark source-independence readiness/blockers, benchmark snapshot materialization status/counts/unmaterialized run ids, Phase 6 covered/missing/required category audit, final-publish package completeness, engineering/scientific gap counts, and blocker classifications. Under-provenanced, under-scale, schema-incomplete, unmaterialized, observation-incomplete, or same-release-only benchmark records stay visible as scientific evidence limitations rather than package plumbing defects, while real package/lineage/output/compile/manifest defects remain engineering gaps to fix before any final-publish promotion.
- Project-level paper compiler evidence now records section coverage, claim support coverage, citation/reference coverage, result table coverage, benchmark provenance, statistics coverage, limitations, review-findings coverage, revision coverage, reproducibility coverage, and compile readiness.
- Project-level rereview reports and repair execution logs now audit repair output artifacts by loading materialized support/repair indexes, recording artifact ids, completeness, blockers, and fingerprints before marking evidence-producing repairs as terminal-condition satisfied.
- Project-level manuscripts now include the full offline publication-case section set: Abstract, Introduction, Research Question, Related Work, Method, Benchmark And Data, Experimental Setup, Results, Analysis, Negative Evidence, Limitations, Reproducibility, Conclusion, and References. The Reproducibility section includes an artifact evidence map pointing to package evidence files for literature support, benchmark provenance, execution/statistics, claim/retrieval evidence, negative evidence, review/repair/rereview, lineage, readiness, and publication manifest.
- Benchmark provenance now records `source_class`, source revision/license/fingerprint, explicit eligibility checks, publication blockers, and per-run benchmark source records with query/document/evidence/label schema coverage plus split, label, query, document, evidence-annotation, and retrieval-relevance counts. Cached fixtures and toy benchmarks can support deterministic review-package evaluation, but final-publish eligibility requires complete real-source provenance, materialized repository-local files for frozen snapshots, and task-aware observations: claim-verification sources must expose evidence annotations, while retrieval-only sources must expose relevance/qrels observations.
- `publication_readiness_report.json` now exposes `benchmark_schema_coverage` and `benchmark_source_observation_coverage` as separate readiness checks, and benchmark provenance package assets include both check ids in `blocking_check_ids` when query/document/evidence/label/split roles or required query/document/evidence/relevance observations are missing. The Operator Console and deterministic evaluation trace mirror the same complete/blocker fields, so schema and observation-count defects remain visible without requiring operators to inspect only `benchmark_provenance_manifest.json`.
- Frozen local benchmark snapshots now preserve sample count, split count, claim-verification support, and verification label space. Complete `file_path` snapshots can be classified as `frozen_snapshot`, while miniature snapshots remain blocked from final-publish by scale eligibility instead of being promoted as paper-grade evidence.
- Project-level submission artifacts now propagate that snapshot metadata into the project benchmark card, paper compiler evidence packet, and benchmark provenance manifest, allowing final-publish blockers to be audited from package artifacts.
- The deterministic evaluation case seeds cached arXiv, Semantic Scholar, and Crossref connector responses, then materializes repository-local SciFact verification and retrieval frozen views. Both selected views can satisfy source/provenance and final-candidate gates, while the same parent SciFact release is retained as a source-independence blocker for cross-source final-publish claims.
- The claim-evidence evaluation trace now records submission-package V3 proof fields, including generated asset roles, missing required roles, publication/readiness/statistics/experiment-repair/negative-evidence/offline-case/offline-audit/review-findings paths, review finding count and action mapping, execution source counts, materialized execution run ids, paper section coverage, claim-support counts, claim ceiling, negative-evidence coverage, Phase 6 covered/missing/required category fields, runtime-failure observation status, final-publish package completeness, engineering/scientific gap counts and classifications, Phase 1 blocked requirement ids, benchmark schema coverage/blockers, benchmark source-observation coverage/blockers, benchmark final-publish-candidate blockers, benchmark source-independence blockers, kill criteria, required follow-ups, and negative-evidence counts.
- Project-level `statistics_report.json` now records per-method metrics, aggregate metrics, deterministic train/test split evaluations, split-level metric tables, per-query diagnostics, required metric coverage for retrieval / claim-verification / repair-router metrics, paired/significance comparisons with effect sizes, multiple-comparison correction status, confidence intervals or deterministic equivalents, execution/import replay coverage, negative-evidence summaries, final-publish statistics blockers, scoped statistics limitations, replication readiness, and a claim-ceiling recommendation instead of exposing only a coverage boolean.
- Review-bundle readiness and final-publish readiness are separate. Current deterministic packages may be review-ready while final publish stays blocked by benchmark independence, residual negative evidence, blocked repair attempts, statistics claim-ceiling constraints, or project publish-gate failures; local PDF compiler absence remains visible as a compile-environment limitation rather than a package-completeness failure.

### V3: Runner Metrics

- Extend IR runner reporting with nDCG@10 and Recall@10.
- Preserve MRR and Recall@1 compatibility.
- Persist per-query failure cases for paper analysis.
- Cached claim-evidence execution now records query-level aggregate dispersion, confidence intervals, paired query comparisons, repair precision/recall for active repair-router methods, and an exact sign-test summary instead of a fixed significance placeholder. Retrieval-only/no-verification ablations keep retrieval metrics but do not emit verification or repair-router metrics.
- Experiment-factory materialized jobs now carry deterministic execution surrogates, runtime contracts, output refs, environment manifest linkage, repair classifications, and explicit failure classifications so local/bridge/import execution can be audited without live infrastructure.

### V4: Ledger-Aware Retrieval

- Add a claim-type/evidence-status reranker.
- Compare against lexical baselines.
- Record evidence coverage and unsupported-claim detection behavior.

### V5: Repair Loop Integration

- Convert unsupported retrieval outcomes into review-loop actions.
- Auto-apply bounded claim downgrades or retrieval repairs.
- Re-review until claim support is clean or explicitly blocked.

### V6: Manuscript And Package

- Generate a workshop-style case-study paper from the vertical run.
- Include related work, method, benchmark, results, limitations, reviewer response, evidence index, and lineage archive.

### V7: Project-Level Submission Package

- Materialize project-level paper sources with Markdown, LaTeX, bibliography, compile report, build script, revision action index, revised manuscript, revision application report, and re-review report.
- Materialize a submission package with reproducibility checklist, reviewer response, claim-evidence index, lineage archive, supplemental artifacts manifest, benchmark card, code package, and publication manifest.
- Preserve blockers when the package is only review-ready.

### Remaining Publication-Grade Gaps

- The primary vertical now runs the materialized repository-local `backend/data/frozen_benchmarks/scifact_claim_verification_frozen_snapshot_v1.json` and `backend/data/frozen_benchmarks/scifact_claim_retrieval_frozen_snapshot_v1.json` SciFact frozen views with 120 normalized examples generated from original records in the official SciFact release tarball. `scripts/build_scifact_frozen_snapshot.py` records the release tarball URL, SHA-256, license split, normalization policy, split distribution, label distribution, source fingerprint, query/document/evidence schema, observation counts, parent source metadata, and publication/final-candidate eligibility fields directly in the frozen JSON. Both SciFact views can satisfy the source/provenance and final-candidate benchmark gate, and the package now materializes deterministic train/test split-level statistics for the selected runs. The project-level package also covers the Phase 6 `failed_or_blocked_repair_attempt` category with a deterministic blocked source-independence repair artifact instead of inferring success or fabricating a second benchmark source. Final publish still stays blocked by same-release source-independence limits, the blocked repair execution log, residual negative/failure evidence, and the scoped claim ceiling rather than by missing package plumbing.
- Literature coverage now exercises multi-source cached connectors, but must still be expanded to broader real-paper coverage before a high-level related-work or novelty claim is made.
- Independent-source replication, broader benchmark coverage, and residual-failure resolution are still required before promoting the vertical from technical report to strong conference claim.
- If `pdflatex` is absent, the system must keep the PDF compile-environment limitation visible in `paper_compiler_evidence.json` while still treating materialized paper sources, package manifests, and compiler-evidence coverage as auditable package artifacts.
