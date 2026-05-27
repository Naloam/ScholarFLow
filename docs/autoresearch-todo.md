# ScholarFlow Auto-Research TODO

This TODO keeps the next implementation work tied to the project goal:
idea intake -> literature and gap validation -> hypothesis selection -> real experiments ->
claim-evidence ledger -> paper/reviewer/revision loop -> submission package.

## Priority 1: P16 Real Experiment Backend

Status: done.

Goal: materialize experiment factory plans into auditable execution jobs instead of only
describing toy jobs.

Acceptance:
- Create environment manifests for every factory execution.
- Materialize planned jobs with executor mode, backend, dependencies, expected outputs,
  output refs, status, and repair classification.
- Preserve deterministic toy execution for tests while making local/docker/bridge/import
  modes explicit and evidence-ledger aware.
- Persist materialized execution metadata through repository helpers.
- Do not weaken claim-evidence, artifact lineage, repair safety, or publish gates.

## Priority 2: P15+ Literature Depth

Status: done.

Goal: extend cached arXiv/Semantic Scholar/Crossref scouting beyond metadata-level signals.

Acceptance:
- Add optional full-text or PDF-derived ingestion behind cache/network controls.
- Canonicalize methods, datasets, metrics, and SOTA signals across sources.
- Keep pytest deterministic with fixtures and cached parser inputs only.
- Ensure novelty validation distinguishes real retrieved literature from fixtures/offline context.

## Priority 3: P18 Autonomous Revision Loop

Status: done.

Goal: convert reviewer findings into bounded, auditable actions.

Acceptance:
- Map reviewer findings to paper rewrites, experiment repairs, claim downgrades, or re-review.
- Keep every revision traceable to evidence, reviewer findings, and changed manuscript sections.
- Prevent unsupported claim promotion during revisions.

## Priority 4: P19 Submission Package

Status: done.

Goal: create a final package suitable for submission workflows.

Acceptance:
- Package manuscript, supplemental artifacts, reproducibility checklist, claim-evidence index,
  reviewer response, and lineage archive.
- Include publish blockers when the package is not strong enough for submission.

## Priority 5: P20 Real End-to-End Evaluation

Status: done.

Goal: run executable evaluation cases that produce ScholarFlow's own system evidence.

Acceptance:
- Execute idea-to-paper cases without live network, paid LLM calls, GPU, or external benchmark
  availability in tests.
- Produce architecture, case-study, and failure-analysis material from actual run artifacts.

## Priority 6: GitHub Sync

Status: next.

Goal: synchronize completed, tested work to the GitHub master branch.

Acceptance:
- Keep commits scoped and passing tests.
- Push only after the prioritized implementation goals above are complete and verified.
- Use `gh`/git to sync `master` with `origin/master`.
