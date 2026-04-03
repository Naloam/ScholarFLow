# ScholarFlow

ScholarFlow is an AI-powered auto-research platform that orchestrates the full academic research lifecycle — from topic formulation through experiment execution to paper drafting and review — inside a single workspace.

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Node.js 18+
- An LLM API key (DeepSeek, OpenAI, or any litellm-compatible provider)

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum one LLM provider:

```bash
# Option A — DeepSeek (recommended, cost-effective)
DEEPSEEK_API_KEY=sk-your-key-here
LLM_MODEL=deepseek/deepseek-chat
LLM_API_BASE=https://api.deepseek.com

# Option B — OpenAI
OPENAI_API_KEY=sk-your-key-here
LLM_MODEL=openai/gpt-4o-mini

# Database — SQLite works for local dev
DATABASE_URL=sqlite:///backend/dev.db
```

### 3. Install Dependencies

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### 4. Start Servers

```bash
# Terminal 1 — Backend (port 8000)
cd backend && PYTHONPATH=. python -m uvicorn main:app --reload

# Terminal 2 — Frontend (port 5173)
cd frontend && npm run dev
```

Open **http://localhost:5173** in your browser.

### 5. Use the Workspace

The ScholarFlow workspace guides you through a phased research workflow:

| Phase | Panel                               | What You Do                                                                                                     |
| ----- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 1     | **Project Launcher** (left sidebar) | Enter a title, topic, and template. Click **Create Project**.                                                   |
| 2     | **Research Roadmap** (left sidebar) | Review the auto-generated research plan and hypotheses.                                                         |
| 3     | **Editor Surface** (center)         | Click **Generate Draft** to produce a full paper outline via LLM. Edit with the rich-text editor (TipTap).      |
| 4     | **File Manager** (left sidebar)     | Save drafts, track versions. Click **Download Latest Export** for Markdown.                                     |
| 5     | **Review Panel** (right sidebar)    | Click **Run Review** to check evidence coverage, flag `[NEEDS_EVIDENCE]` markers, and get similarity screening. |
| 6     | **Operator Console** (center-right) | Click **Start Run** to launch a full auto-research pipeline: plan → codegen → execute → paper generation.       |
| 7     | **Deployments** (right sidebar)     | Export and download final publish bundles.                                                                      |

**Typical workflow:** Create Project → Generate Draft → Edit → Save → Run Review → Start Run → Download Final Publish.

### 6. Configuration Options

Key environment variables (see `.env.example` for the full list):

| Variable        | Default                    | Description                                              |
| --------------- | -------------------------- | -------------------------------------------------------- |
| `LLM_MODEL`     | `gpt-4o-mini`              | litellm model identifier (e.g. `deepseek/deepseek-chat`) |
| `LLM_API_BASE`  | —                          | API base URL for non-OpenAI providers                    |
| `DATABASE_URL`  | `sqlite:///backend/dev.db` | PostgreSQL or SQLite connection string                   |
| `AUTH_REQUIRED` | `false`                    | Enable session authentication                            |
| `DATA_DIR`      | `backend/data`             | Directory for project data storage                       |

## Document Map

- `PROJECT_PLAN.md`: authoritative roadmap and phase priorities
- `AGENTS.md`: contributor rules for humans and AI agents
- `SYSTEM_PROMPT.md`: long-lived default prompt for future AI development sessions
- `docs/fars-reference.md`: distilled public FARS signals and how ScholarFlow should emulate them
- `docs/architecture.md`: current and target architecture
- `docs/api-reference.md`: current auto-research and registry APIs

## Current State

- Portfolio-aware auto-research runs are implemented.
- The runner supports multi-seed execution, sweeps, aggregate metrics, confidence intervals, significance tests, and negative-result retention.
- Runtime contract enforcement and structured repair patching are in place.
- The execution plane supports queueing, checkpoint resume, retry, cancel, and worker state.
- Artifact registry / lineage is now in place with file hashes, lineage edges, bundle indexes, and candidate views.
- Registry-backed review reports and publish-package export are now in place.
- Review hardening now resolves paper citations against persisted literature state and checks for reference-section completeness.
- Review now also derives a novelty / related-work assessment from persisted literature and the selected candidate.
- The operator console now supports run filtering/search, candidate comparison, lineage summary, review-risk/novelty triage, and recovery/publish actions inside the workspace.
- Runs can now opt into budget-aware portfolio truncation through `candidate_execution_limit`, and the operator console surfaces constrained/default budget posture for triage.
- The execution plane now supports per-run queue priority, and the operator console can patch run controls for future scheduling/budget changes without editing raw run files.
- Execution recovery now tracks stale-lease recoveries explicitly and fences old lease updates so recovered jobs cannot be incorrectly closed out by stale workers.
- Publish hardening now distinguishes review-bundle readiness from final publish completeness, so missing reproducibility assets are exposed explicitly before final packaging.
- Export hardening now writes an explicit `archive_manifest.json` into publish bundles and labels each export as either a `review_bundle` or `final_publish_bundle`.
- Deployment hardening now exposes global deployment listing/detail APIs, persisted `publication_manifest.json`, and a stable `paper.md` / `publish_bundle.zip` / `code_package.zip` publication surface.
- Publication manifests and registry/bundle reads now also surface compiled paper outputs such as `paper_sources/main.pdf` when they exist, including a stable compiled-PDF download path.
- Research-quality hardening now adds role-aware candidate diversity, robustness-aware portfolio elimination, richer failed-config diagnostics, family-aware Holm metadata, and comparison-level power analysis notes.
- The numbered Phase 1-6 baseline plus Workstreams E/F are complete; the remaining gaps are deeper paper automation, compile-ready coverage, and higher-throughput scaling.

## Development Entry Points

- Backend: `cd backend && PYTHONPATH=. ../.venv/bin/uvicorn main:app --reload`
- Backend tests: `cd backend && ../.venv/bin/pytest -q`
- Frontend: `cd frontend && npm run dev`
- Frontend build: `cd frontend && npm run build`

## Key Paths

- Auto-research orchestration: `backend/services/autoresearch/orchestrator.py`
- Experiment execution: `backend/services/autoresearch/runner.py`
- Execution plane: `backend/services/autoresearch/execution.py`
- Persistence and manifests: `backend/services/autoresearch/repository.py`
- Schemas: `backend/schemas/autoresearch.py`
- Main regression suite: `backend/tests/test_autoresearch.py`

## Legacy Notes

The repository still contains student-writing, mentor, tutor, and low-code MVP artifacts. They are secondary to the current auto-research mainline unless `PROJECT_PLAN.md` explicitly says otherwise.
