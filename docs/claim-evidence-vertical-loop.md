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
2. A cached BEIR/SciFact-style benchmark path exists and can run without live network.
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

- Add a cache-backed SciFact/BEIR-style dataset loader.
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
- `experiment_repair_index.json` records execution source classification, imported replay run ids, materialized execution run ids, output artifact refs, environment manifest ids/fingerprints, failed materialized job classifications, and residual blockers so project-level repair evidence can be traced back to run-level execution or imported-result replay artifacts. It now also carries an `execution_evidence_ledger` with per-run capsules for command/import paths, runtime contracts, dependency manifests, input benchmark provenance, method outputs, metrics/evidence/negative-evidence refs, repair action linkage, and deterministic fingerprints. Project compiler evidence, statistics reports, and readiness reports repeat that execution coverage so statistics cannot be treated as complete without linked execution/import replay artifacts.
- `negative_evidence_report.json` retains negative results, failed trials, retrieval misses, unsupported claim gaps, project negative findings, and blocked repair evidence as package-level evidence; blocking entries keep final publish blocked instead of being hidden by the manuscript compiler.
- `retrieval_evidence_ledger.json` aggregates selected-run retrieval ledger entries and retrieval-ledger artifact outputs into a project-level package asset so claim-evidence retrieval support can be audited without opening individual run folders.
- `literature_support_index.json` now records FARS/ARIS related-system coverage from cached/imported literature metadata and known-SOTA fields, and explicitly marks missing coverage as a limitation instead of inventing related-work support.
- `offline_publication_case.json` records the fixed claim-evidence publication-case idea, research question, brief/hypothesis/benchmark/experiment chain, method ladder, expected metrics, repair triggers, output package roles, and evidence classification for real/imported/frozen sources versus internal fixtures.
- `offline_publication_audit.json` records the Phase 1 capability and remaining-breakpoint audit across literature refresh, benchmark snapshots, execution/import replay, statistics, negative evidence, rereview, and package completeness.
- Project-level paper compiler evidence now records section coverage, claim support coverage, citation/reference coverage, result table coverage, benchmark provenance, statistics coverage, limitations, review-findings coverage, revision coverage, reproducibility coverage, and compile readiness.
- Project-level rereview reports and repair execution logs now audit repair output artifacts by loading materialized support/repair indexes, recording artifact ids, completeness, blockers, and fingerprints before marking evidence-producing repairs as terminal-condition satisfied.
- Project-level manuscripts now include the full offline publication-case section set: Abstract, Introduction, Research Question, Related Work, Method, Benchmark And Data, Experimental Setup, Results, Analysis, Negative Evidence, Limitations, Reproducibility, Conclusion, and References. The Reproducibility section includes an artifact evidence map pointing to package evidence files for literature support, benchmark provenance, execution/statistics, claim/retrieval evidence, negative evidence, review/repair/rereview, lineage, readiness, and publication manifest.
- Benchmark provenance now records `source_class`, source revision/license/fingerprint, explicit eligibility checks, publication blockers, and per-run benchmark source records with query/document/evidence/label schema coverage. Cached fixtures and toy benchmarks can support deterministic review-package evaluation, but final-publish eligibility requires complete real-source provenance and must block missing `dataset_id`, `revision`, `license`, source locator, fingerprint, or claim-evidence schema roles.
- Frozen local benchmark snapshots now preserve sample count, split count, claim-verification support, and verification label space. Complete `file_path` snapshots can be classified as `frozen_snapshot`, while miniature snapshots remain blocked from final-publish by scale eligibility instead of being promoted as paper-grade evidence.
- Project-level submission artifacts now propagate that snapshot metadata into the project benchmark card, paper compiler evidence packet, and benchmark provenance manifest, allowing final-publish blockers to be audited from package artifacts.
- The deterministic evaluation case seeds cached arXiv, Semantic Scholar, and Crossref connector responses, then materializes both a cached SciFact-style verification run and a cached BEIR-style retrieval run so benchmark readiness can distinguish a review-ready ladder from final publication evidence.
- The claim-evidence evaluation trace now records submission-package V3 proof fields, including generated asset roles, missing required roles, publication/readiness/statistics/experiment-repair/negative-evidence/offline-case/offline-audit/review-findings paths, review finding count and action mapping, execution source counts, materialized execution run ids, paper section coverage, claim-support counts, claim ceiling, negative-evidence coverage, kill criteria, required follow-ups, and negative-evidence counts.
- Project-level `statistics_report.json` now records per-method metrics, aggregate metrics, paired/significance comparisons, confidence intervals or deterministic equivalents, execution/import replay coverage, negative-evidence summaries, scoped statistics limitations, and a claim-ceiling recommendation instead of exposing only a coverage boolean.
- Review-bundle readiness and final-publish readiness are separate. Current deterministic packages may be review-ready while final publish stays blocked by compile availability, benchmark scale, replication, or project publish-gate failures.

### V3: Runner Metrics

- Extend IR runner reporting with nDCG@10 and Recall@10.
- Preserve MRR and Recall@1 compatibility.
- Persist per-query failure cases for paper analysis.
- Cached claim-evidence execution now records query-level aggregate dispersion, confidence intervals, paired query comparisons, and an exact sign-test summary instead of a fixed significance placeholder.
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

- The cached SciFact/BEIR-style benchmark ladder is deterministic and useful for regression / case-study validation, but fixture provenance keeps it below broad publication-grade evidence.
- Literature coverage now exercises multi-source cached connectors, but must still be expanded to broader real-paper coverage before a high-level related-work or novelty claim is made.
- Cross-run replication, stronger statistics, and broader benchmark coverage are still required before promoting the vertical from technical report to strong conference claim.
- If `pdflatex` is absent, the system must keep the compile blocker visible even though paper sources and package manifests are materialized.
