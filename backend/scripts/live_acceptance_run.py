"""Live acceptance runner (manual — never in CI).

Runs the FULL research_harness pipeline against the real GLM-5.2 backend on a
fresh idea, then prints the quality baseline the roadmap's "V2 quality bar"
needs (draft completeness, gate verdict, [UNVERIFIED]/citation hit rates, runtime).

    SCHOLARFLOW_OFFLINE_LLM=0 ../.venv/bin/python scripts/live_acceptance_run.py

Archive the produced workspace under backend/data/research_workspace/<live_id>/
after inspection — it is the "after" sample for the V2.1 quality measurement.
"""
from __future__ import annotations

import json
import logging
import time

from services.research_harness import pipeline

# A NEW real idea (distinct from the v0_citrag_05 fixture's "Citation-Faithful RAG").
LIVE_IDEA = (
    "Self-Consistency Calibration for Hallucination Detection in "
    "Retrieval-Augmented Generation: Aggregating Passage-Answer Agreement to "
    "Trigger Abstention"
)
PROJECT_ID = "live_session7"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    t0 = time.time()
    summary = pipeline.run_pipeline(PROJECT_ID, LIVE_IDEA)
    elapsed = time.time() - t0

    proj = pipeline.project_dir(PROJECT_ID)
    print("\n=== LIVE ACCEPTANCE — quality baseline ===")
    print(f"idea: {LIVE_IDEA}")
    print(f"project_id: {PROJECT_ID}")
    print(f"workspace: {proj}")
    print(f"status: {summary['status']}  steps: {summary['steps']}")
    print(f"elapsed: {elapsed/60:.1f} min")

    metrics = pipeline.load_metrics(PROJECT_ID)
    print(f"execution_status: {metrics.get('execution_status')}")
    print(f"verdict: {__import__('services.research_harness.evidence', fromlist=['verdict']).verdict(metrics)}")

    draft_path = proj / "paper" / "draft.md"
    if draft_path.exists():
        draft = draft_path.read_text(encoding="utf-8")
        print(f"draft.md: {len(draft)} chars, {len(draft.splitlines())} lines")
        print(f"  [UNVERIFIED] hits: {draft.count('[UNVERIFIED')}")
        headings = [l for l in draft.splitlines() if l.startswith('##')]
        print(f"  section headings ({len(headings)}): {[h.strip('# ').strip() for h in headings]}")
    else:
        print("draft.md: MISSING (write step failed)")

    ledger_path = proj / "ledger" / "claim_audit.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        print(f"ledger: gate={ledger.get('gate')} total={ledger.get('total_claims')} "
              f"verified={ledger.get('verified_count')} unverified={ledger.get('unverified_count')} "
              f"citation_unverified={ledger.get('citation_unverified_count')}")
    else:
        print("ledger: MISSING (audit step skipped/failed)")

    revise_log = proj / "paper" / "revise_log.json"
    if revise_log.exists():
        rl = json.loads(revise_log.read_text(encoding="utf-8"))
        print(f"quality loop: revised={rl.get('revised')} flags_before={rl.get('flags_before')} flags_after={rl.get('flags_after')}")


if __name__ == "__main__":
    main()
