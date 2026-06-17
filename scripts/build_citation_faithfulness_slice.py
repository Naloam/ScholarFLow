#!/usr/bin/env python3
"""Build a citation-faithfulness seed dataset (Session 4 Step 3).

The hypothesis under test is *citation parsing-error detection* — i.e. whether a
claim's cited evidence is the correct source or a mismatched (wrongly-parsed)
one. SciFact/VitaminC are general claim-verification sets; this third dataset
makes that hypothesis directly testable with **zero external dependencies** by
deriving it from the already-committed SciFact slice.

Construction (fully deterministic, no randomness → reproducible committed data):
  - 50 FAITHFUL examples: SciFact entries[0:50], each claim paired with its OWN
    gold evidence abstract (a correct citation).
  - 50 PARSING_ERROR examples: the SAME 50 claims, but each paired with the
    evidence of SciFact entry[i + 50] — a topically-different abstract, i.e. a
    citation that points to the wrong source (a realistic parsing error).

Same 50 claims in both classes ⇒ the *only* difference is the evidence, giving
the cleanest possible faithful-vs-mismatched signal. Label balance is exactly
50/50.

Output schema (same shape as the other slices, distinct label space):
  {"id","claim","evidence","evidence_title","label":"FAITHFUL|PARSING_ERROR","source"}

Run:
  cd backend && PYTHONPATH=. ../.venv/bin/python ../scripts/build_citation_faithfulness_slice.py
"""
from __future__ import annotations

import json
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "backend" / "services" / "research_harness" / "seed_data"
SOURCE = SEED_DIR / "scifact_slice.jsonl"
OUT = SEED_DIR / "citation_faithfulness_slice.jsonl"
N_CLAIMS = 50  # 50 claims × 2 classes = 100 examples


def main() -> None:
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= N_CLAIMS * 2, f"need >=100 source rows, got {len(rows)}"
    assert all((r.get("claim") or "").strip() and (r.get("evidence") or "").strip() for r in rows[: N_CLAIMS * 2])

    faithful = rows[:N_CLAIMS]
    donors = rows[N_CLAIMS : N_CLAIMS * 2]  # distinct entries whose evidence simulates mis-parsing

    out: list[dict] = []
    for i, entry in enumerate(faithful):
        out.append({
            "id": f"cit-faith-{i:03d}",
            "claim": entry["claim"],
            "evidence": entry["evidence"],
            "evidence_title": entry.get("evidence_title", ""),
            "label": "FAITHFUL",
            "source": "derived-from-allenai/scifact (correct citation)",
        })
    for i, entry in enumerate(faithful):
        donor = donors[i]
        out.append({
            "id": f"cit-err-{i:03d}",
            "claim": entry["claim"],
            "evidence": donor["evidence"],          # mismatched abstract → parsing error
            "evidence_title": donor.get("evidence_title", ""),
            "label": "PARSING_ERROR",
            "source": "derived-from-allenai/scifact (mismatched citation / parsing error)",
        })

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
    from collections import Counter
    counts = Counter(r["label"] for r in out)
    print(f"wrote {len(out)} rows to {OUT}")
    print("label balance:", dict(counts))
    # sanity: faithful and error share the same claim text for index i
    assert out[0]["claim"] == out[N_CLAIMS]["claim"], "faithful/error claims must align by index"
    assert out[0]["evidence"] != out[N_CLAIMS]["evidence"], "faithful/error evidence must differ"
    print("OK: faithful[i].claim == error[i].claim; evidence differs")


if __name__ == "__main__":
    main()
