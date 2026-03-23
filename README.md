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
- Review hardening now resolves paper citations against persisted literature state and checks for reference-section completeness.
- Review now also derives a novelty / related-work assessment from persisted literature and the selected candidate.
- The operator console now supports run filtering/search, candidate comparison, lineage summary, review-risk/novelty triage, and recovery/publish actions inside the workspace.
- Publish hardening now distinguishes review-bundle readiness from final publish completeness, so missing reproducibility assets are exposed explicitly before final packaging.
- The numbered Phase 1-6 baseline is complete; the current focus is remaining operator controls plus deeper export/repro hardening.

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
