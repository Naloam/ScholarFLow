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
8. Submission package includes manuscript, evidence index, reproducibility checklist, and lineage archive.

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
7. Submission package contains claim-evidence index and reproducibility assets.
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
- IR runner output now reports MRR, Recall@1, nDCG@10, Recall@10, evidence coverage, and per-query objective failure cases for paper analysis.
- The IR search ladder includes `ledger_aware_reranker_search`, which combines IDF, bigram overlap, and transparent claim/citation/artifact/experiment/review cue alignment.
- Retrieval failure cases are converted into deduplicated review-loop repair actions such as claim downgrades or literature refreshes.
- Claim-evidence IR runs now emit a workshop-style vertical package with manuscript section requirements, a per-query retrieval evidence ledger, claim-evidence index entries, reproducibility assets, limitations, and reviewer-response actions.

### V3: Runner Metrics

- Extend IR runner reporting with nDCG@10 and Recall@10.
- Preserve MRR and Recall@1 compatibility.
- Persist per-query failure cases for paper analysis.

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
