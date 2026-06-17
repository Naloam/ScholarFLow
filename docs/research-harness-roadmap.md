# Research Harness Roadmap

> Tracked canonical roadmap for the `research_harness` rebuild (V0 → V3).
> This is the single place that records **what is done**, **what is deliberately
> not done**, and the **explicit trigger conditions** for the deferred P2/P3 work.
> Companion to `SCHOLARFLOW_CORE_REBUILD_PLAN_v2.md` (the "why / diagnosis" doc);
> this file is the "where are we" doc.

## How the harness relates to the legacy `autoresearch` engine

`backend/services/autoresearch/` is **FROZEN** (see plan §2). It is a
keyword→template system with no LLM in its "thinking" path, wrapped in a very
thick audit/governance shell (incl. the 13975-line `project_paper_orchestrator.py`).
It stays in the tree as historical reference; its regression suite keeps running,
but the new core does **not** depend on it and must not be built by adapting it.

`backend/services/research_harness/` is the replacement core: a small,
LLM-driven pipeline (literature → idea → experiment → review → report → write →
audit) that proves "there is a brain that actually thinks." All new work lands here.

## Status by version

### V0 — Minimal credible loop ✅ done
`python scripts/v0_run.py --idea "…"` runs one real idea end-to-end: LLM-driven
literature search → hypothesis candidates → generated+executed experiment code
(sentence-transformers allowed) → stats layer → reviewer critique → honest report.
A genuine negative result is reported as a negative result.

### V1 — Productized UI ✅ done
The pipeline is exposed via a minimal FastAPI surface
(`POST /api/research-harness/projects/{id}/start`, `…/status`, `…/timeline`,
`…/files/{path}`) and a **fully rebuilt** React/Vite + TypeScript frontend
(5-item nav: Projects / Run / Workspace / Report / Settings; domain-split
Zustand stores; `<200`-line components; `react-router`). The old 1898-line store
and 14-panel OperatorConsole were retired.

### V2 — Writer + Auditor layer ✅ done
- **WriterAgent** (`writer.py`): `contribution.md → outline.md → draft.md`, fed
  the *real* evidence pack + honesty constraints derived from `metrics.json`.
- **AuditorAgent** (`auditor.py`): pure-deterministic post-writing gate. Overclaim
  rules (significance / scope / positive-spin-on-a-loss / bare-global-superiority)
  + metric/literature keyword-overlap evidence check. Unsupported claims get
  inline `[UNVERIFIED: reason]` markers; `ledger/claim_audit.json` records the
  verdict; `research_report.md` is annotated (FAILED is never silent).
- `write`/`audit` are **non-fatal** pipeline steps: a paper-layer failure never
  blocks the honest report.

### V2.1 — Verification completion + quality loop ✅ done (this session)
Closes the two gaps Session 6 left open (see plan §6 contract + §7 P1):
1. **Citation verification** (`citation.py`, new): every `[n]` / `[Author, Year]`
   / `**"Title"**` / reference-list entry in the draft is title-matched against
   `literature/papers.jsonl` (offline, ported `_titles_match`). An unmatched
   citation → `[UNVERIFIED: citation "…" not found in retrieved literature]`,
   counted as a `category: "citation"` claim, and **fails the gate**. DBLP/CrossRef
   is an optional second chance under `live_research` only; the offline path never
   imports `httpx`.
2. **Writer→Auditor quality loop** (bounded): `evidence.coverage_lint` flags draft
   numbers with no root in the evidence pack (tolerates honest rounding); the
   Writer gets **at most one** corrective pass (`revise_on_lint`) that may only fix
   flagged numbers (no new numbers, no softened honesty). `draft.raw.md` (pristine
   LLM output) and `draft.revise_pre.md` (pre-revision) are preserved for
   traceability; `paper/revise_log.json` records before/after flag counts.
3. **Test-to-CI decision landed** (plan §7 P1): the network/LLM-free pure-logic
   subset (`test_research_harness_prompts.py`, `test_research_harness_citation.py`)
   is force-tracked; fixture/live-LLM tests stay local (see "Testing" below).
4. **Frontend surfaces the citation gate**: `AuditLedger` shows a `metric` /
   `spin` / `citation` category chip per claim and a citation-unverified count;
   `PaperDraft` already renders `[UNVERIFIED: …]` (any reason) as a red `<mark>`.

**Verification baseline (fixture `v0_citrag_05`, MIXED result):**
- before V2.1 (metric/overclaim gate only): 3 claims, 1 unverified (scope overclaim), gate False.
- after V2.1 (citations + loop): honest drafts add no spurious flags; an injected
  unmatched citation is caught (gate False) while real citations verify. The loop
  does **not** loosen any gate — it only adds checks.

### V3 — Editable paper (not started)
TipTap rich-text editor so a human can edit `paper/draft.md` in-place (currently
read-only render). Out of scope until V2 quality is validated on live runs.

## Deferred work — explicit "not until X" triggers

### P2 — Orchestrator deprecation
Deprecate `project_paper_orchestrator.py` (13975 lines) into a thin
read-the-new-workspace compatibility layer.
**Trigger:** *after* V2, incrementally — not this session. Only once the
research_harness write/audit path is producing paper drafts of acceptable quality
on real runs (the P3 quality bar, below).

### P3 — Release / venue / compliance / publish-archive
Release governance, venue adapters, compliance checklists, publish-archive
variants (plan §6 "stop stacking"). **Trigger:** only when the V2 Writer's live-run
output quality meets the baseline defined below. Until then these are explicitly
**not built** — stacking publication plumbing on an unvalidated writer is the
failure mode this rebuild exists to avoid.

### V2 "quality bar" (the P3 trigger condition, quantified)
P3 becomes eligible when a **real live GLM run** (`SCHOLARFLOW_OFFLINE_LLM=0
pytest -m live_research backend/tests/test_live_research.py -s`, ~10–15 min, real
tokens) demonstrates, on a fresh idea:
- `paper/draft.md` is structurally complete (all outlined sections present, no
  empty/aborted sections from rate-limiting);
- the honesty gate is **not bypassed** (a genuine negative/mixed verdict is
  reported as such — no silent pass);
- `[UNVERIFIED]` hit rate is dominated by *real* unsupported claims/citations,
  not by Writer format drift or hallucinated numbers the loop should have caught;
- citation verification flags hallucinated references when present, and does not
  false-flag real retrieved papers.

Record each live run's `[UNVERIFIED]` hit count, draft completeness, and cost into
this file's baseline table as the "after" sample. **The live run is manual and is
the sole acceptance evidence for P3** — CI/fixtures cannot substitute.

## Non-negotiable baselines (never weakened)

- Portfolio-aware execution, multi-seed/sweep support, aggregate metrics,
  confidence intervals, significance reporting (Holm-corrected).
- Runtime contract enforcement + structured repair safety.
- Persisted run / candidate / artifact / review / publish state; registry/lineage
  compatibility.
- Backward compatibility for `run.json` and `artifact.json` consumers.
- The honesty gates: **negative / mixed / significance / retrieval-coverage /
  citation** verdicts are reported faithfully. New verification (citation, quality
  loop) **only adds gates, never loosens one**.
- LLM main path: idea/hypothesis/method generation must go through real `chat()`
  calls with the user's idea + literature notes as input — no keyword→template
  fallback as a main path (fallbacks must be marked `source: "fallback_template"`
  and excluded from main conclusions).
- Frontend: `files/{path}` path-traversal guard, background-async `start`,
  always-visible 5-item nav, domain-split stores, `<200`-line components, and
  faithful rendering (null/negative/mixed never reframed as positive).

## Testing

- **CI / default suite** (`-m "not live_research"`): the FROZEN `autoresearch`
  regression suite + the force-tracked research_harness pure-logic subset
  (`test_research_harness_prompts.py`, `test_research_harness_citation.py`).
  These are network-free and need no fixture.
- **Local-dev only** (gitignored): the fixture-backed research_harness tests
  (`test_research_harness_writer_auditor.py`, `_api.py`, `_session4.py`) and the
  `v0_citrag_05` fixture under `backend/data/`. They read `backend/data/`.
- **Manual only** (`@pytest.mark.live_research`): `test_live_research.py` — one
  real GLM run, real tokens, ~10–15 min. Never in CI.

## LLM / cost notes

`.env` targets Zhipu GLM-5.2 (`LLM_API_BASE=https://open.bigmodel.cn/...`, 1M
context, per-minute rate limits, no embeddings interface). The Writer issues
multiple section calls + at most one revise call, all through the rate-limit-aware
`chat()`; large prompts are batched. See memory `[[llm-testing-constraint]]`.
