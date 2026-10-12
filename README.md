# ScholarFlow

ScholarFlow is an autonomous research harness: given a research idea, it runs the full lifecycle — literature review (real arXiv / Semantic Scholar / Crossref), hypothesis generation, experiment code generation and execution (real subprocess, CPU sandbox), statistical evaluation, honest research reporting, paper drafting, and an audit gate that refuses unsupported claims. Current goal (P4): turn audited runs into core-journal paper manuscripts (first/solo author), with a human edit + re-audit loop before anything ships.

## What it actually does

One command per run:

```bash
cd backend && ../.venv/bin/python ../scripts/v0_run.py --idea "..." --project-id my_run
```

produces a workspace under `backend/data/research_workspace/<project_id>/`:

| Stage | Output | Guarantee |
|---|---|---|
| literature | `papers.jsonl`, `notes.md`, `gap_map.md` | real retrieved papers (no fabricated citations) |
| idea | `candidates.json`, `selected.json` | hypotheses with literature-grounded `core_novelty` |
| experiment | `candidates/*/artifacts/metrics.json` | real numbers from real datasets (SciFact, VitaminC, tabular slices), multi-seed + significance tests |
| review | `reviewer_round_1.md` | concrete criticisms citing the run's own numbers |
| report | `research_report.md`, `conclusion.md` | negative result stays negative (hard-coded conclusion gate) |
| write | `paper/draft.md` | draft with inline `[UNVERIFIED]` markers where claims lack evidence |
| audit | `ledger/claim_audit.json` | deterministic gate (no LLM-judging-LLM); structured `audit-claim` markers verified by value |
| publish | `publish_bundle.zip` | `publishable=false` unless every honesty gate passes |

Portfolio execution runs the top-K hypothesis candidates independently and aggregates honestly (`mixed_portfolio` when they disagree). The TipTap editor lets a human edit the draft; saving re-enters the audit gate, so human-added unsupported claims get flagged too.

## Architecture

- **Backend** (FastAPI, `backend/`): the entire research brain is `services/research_harness/` (~7k lines) — pipeline, experiment engineer, evidence/auditor honesty gates, writer, publish. LLM calls go through one client (`services/llm/client.py`, litellm-based). The pre-rebuild `autoresearch` system (~72k lines) was physically retired in June 2026; only `literature_connectors.py` survives by design.
- **Frontend** (React 19 + Vite + TipTap, `frontend/`): five pages — Projects, Run, Workspace, Report (paper editor + publish card), Settings.
- **Tests**: 213 offline tests (`cd backend && SCHOLARFLOW_OFFLINE_LLM=1 ../.venv/bin/python -m pytest tests/ -m "not live_research" -q`); live end-to-end runs are opt-in (`-m live_research`, real LLM + budget).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "backend[dev]" -r backend/requirements-experiment.txt
cp .env.example .env   # then set LITELLM_API_KEY / LLM_MODEL / LLM_API_BASE
```

Backend dev server: `cd backend && PYTHONPATH=. ../.venv/bin/uvicorn main:app --reload`
Frontend dev server: `cd frontend && npm install && npm run dev`

## Honest limits

- Dataset slices are ≤500 examples, experiments capped at 10 min CPU (no GPU) — workshop-grade evidence, not SOTA competition. Scaling is P4 work.
- The "sandbox" executes generated code with the host Python (no isolation) — trusted single-user context only.
- The audit gate's prose heuristics are English-centered; Chinese drafts rely on structured `audit-claim` markers (S17).
- `publishable=true` means the honesty gates passed — it does not mean ready-to-submit.

## Docs

- `AGENTS.md` — contributor rules and current goal
- `docs/research-harness-roadmap.md` — full session-by-session history, live-run baseline table, P2–P4 plans
- `SCHOLARFLOW_CORE_REBUILD_PLAN_v2.md` — the June 2026 failure diagnosis that led to the rebuild
