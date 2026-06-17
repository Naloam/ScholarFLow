# Seed Datasets (research_harness)

These are **real, attributed, balanced slices** of public claim-verification benchmarks, committed
to the repo so experiments have **zero runtime network dependency** (no 404 risk, fully reproducible).
Each file is JSONL with the unified schema:

```json
{"id": "...", "claim": "...", "evidence": "...", "evidence_title": "...", "label": "SUPPORT|REFUTE", "source": "..."}
```

## scifact_slice.jsonl — 100 examples (50 SUPPORT / 50 REFUTE)
- **Source**: [allenai/scifact](https://github.com/allenai/scifact) — *Fact or Fiction: Verifying
  Scientific Claims*, Wadden et al. 2020. License: **CC BY 4.0**.
- **Task**: scientific claim verification — given a claim and an evidence abstract, predict SUPPORT/REFUTE.
- **Construction**: 100-example balanced slice of the SciFact **dev** split. For each claim we attach
  the gold-cited corpus abstract as `evidence`; CONTRADICT → REFUTE. NEI claims excluded (clean binary task).
- Downloaded (session 3, 2026-06-15) from the official S3 tarball
  `https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz`.

## citation_faithfulness_slice.jsonl — 100 examples (50 FAITHFUL / 50 PARSING_ERROR)

**Session 4 (2026-06-16)** — the citation-specific dataset requested by the Session 3 reviewer
(`test_on_second_dataset` must_have: "create a dataset that contains simulated citation parsing
errors"). The general claim-verification slices (SciFact/VitaminC) don't directly exercise the
"Citation-Faithful RAG … detecting citation parsing errors" hypothesis; this one does.

- **Task**: citation faithfulness / parsing-error detection — given a claim and a cited evidence
  abstract, decide whether the citation is FAITHFUL (correct source) or a PARSING_ERROR (the
  citation points to the wrong/mismatched source).
- **Construction** (deterministic, zero external dependency): derived from `scifact_slice.jsonl`.
  The same 50 SciFact claims appear in both classes:
  - 50 FAITHFUL: `claim` + its OWN gold evidence abstract.
  - 50 PARSING_ERROR: `claim` + the evidence abstract of a *different* SciFact entry (a rotated
    donor), i.e. a citation that resolves to the wrong source.
  Because both classes share the same claims, the **only** difference is the evidence — the
  cleanest faithful-vs-mismatched signal a faithfulness detector can be asked to recover.
- **Regeneration**: `cd backend && PYTHONPATH=. ../.venv/bin/python ../scripts/build_citation_faithfulness_slice.py`.
- **License**: CC BY 4.0 (inherited from allenai/scifact).

## vitaminc_slice.jsonl — 100 examples (50 SUPPORT / 50 REFUTE)
- **Source**: [tals/vitaminc](https://huggingface.co/datasets/tals/vitaminc) — *VitaminC: A
  Systematic Benchmark for Visual Evidence, ...* / fact-verification via Wikipedia edits,
  Cobbe et al. License: **CC BY-SA 4.0**.
- **Task**: claim verification — given a claim and an evidence passage (Wikipedia sentence), predict
  SUPPORTS/REFUTES. Different domain (Wikipedia) from SciFact (scientific abstracts).
- **Construction**: 100-example balanced slice of the VitaminC **validation** split via the HuggingFace
  datasets-server REST API; SUPPORTS→SUPPORT, REFUTES→REFUTE; NOT ENOUGH INFO excluded.

## Why committed (not fetched at runtime)
Session 2's experiment failed on n=3 because the LLM-generated loader guessed a GitHub URL that 404'd.
Committing verified slices removes that entire failure class. The `DATASET_REGISTRY` in
`../datasets.py` exposes these with absolute-path loaders that experiment code copies verbatim.
