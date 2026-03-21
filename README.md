# ScholarFlow

ScholarFlow is being developed as a FARS-style auto-research system for computer-science research. The goal is a repeatable loop from topic -> portfolio of hypotheses -> executable experiments -> grounded artifacts -> paper draft -> review and publish surfaces.

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
- The operator console now surfaces run lists, candidate comparison, lineage summary, failure triage, and recovery/publish actions inside the workspace.
- The numbered Phase 1-6 baseline is complete; the current focus is hardening review/publish and console depth.

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
