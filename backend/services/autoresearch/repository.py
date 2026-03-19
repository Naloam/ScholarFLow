from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from schemas.autoresearch import (
    AutoResearchRunRead,
    BenchmarkSource,
    ExecutionBackendSpec,
    ExperimentSpec,
    HypothesisCandidate,
    PortfolioDecisionRecord,
    ResearchPlan,
)
from services.workspace import autoresearch_dir


RUN_FILENAME = "run.json"
PROGRAM_FILENAME = "program.json"
PLAN_FILENAME = "plan.json"
SPEC_FILENAME = "spec.json"
PORTFOLIO_FILENAME = "portfolio.json"
ARTIFACT_FILENAME = "artifact.json"
CODE_FILENAME = "experiment.py"
PAPER_FILENAME = "paper.md"
BENCHMARK_FILENAME = "benchmark.json"
CANDIDATES_DIRNAME = "candidates"
CANDIDATE_FILENAME = "candidate.json"
ATTEMPTS_FILENAME = "attempts.json"
MANIFEST_FILENAME = "manifest.json"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _runs_dir(project_id: str) -> Path:
    path = autoresearch_dir(project_id) / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_path(project_id: str, run_id: str) -> Path:
    return _runs_dir(project_id) / run_id


def run_dir(project_id: str, run_id: str) -> Path:
    path = _run_path(project_id, run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def candidate_dir(project_id: str, run_id: str, candidate_id: str) -> Path:
    path = run_dir(project_id, run_id) / CANDIDATES_DIRNAME / candidate_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def create_run(
    project_id: str,
    topic: str,
    docker_image: str | None = None,
    benchmark: BenchmarkSource | None = None,
    execution_backend: ExecutionBackendSpec | None = None,
) -> AutoResearchRunRead:
    now = _utcnow()
    run = AutoResearchRunRead(
        id=f"arun_{uuid4().hex}",
        project_id=project_id,
        topic=topic,
        status="queued",
        benchmark=benchmark,
        execution_backend=execution_backend,
        docker_image=docker_image,
        created_at=now,
        updated_at=now,
    )
    save_run(run)
    return run


def save_run(run: AutoResearchRunRead) -> AutoResearchRunRead:
    payload = run.model_copy(update={"updated_at": _utcnow()})
    base = run_dir(payload.project_id, payload.id)
    _write_json(base / RUN_FILENAME, payload.model_dump(mode="json"))
    if payload.program is not None:
        _write_json(base / PROGRAM_FILENAME, payload.program.model_dump(mode="json"))
    if payload.plan is not None:
        _write_json(base / PLAN_FILENAME, payload.plan.model_dump(mode="json"))
    if payload.spec is not None:
        _write_json(base / SPEC_FILENAME, payload.spec.model_dump(mode="json"))
    if payload.portfolio is not None:
        _write_json(base / PORTFOLIO_FILENAME, payload.portfolio.model_dump(mode="json"))
    if payload.candidates:
        candidate_dir = base / CANDIDATES_DIRNAME
        candidate_dir.mkdir(parents=True, exist_ok=True)
        for candidate in payload.candidates:
            _write_json(candidate_dir / f"{candidate.id}.json", candidate.model_dump(mode="json"))
    if payload.artifact is not None:
        _write_json(base / ARTIFACT_FILENAME, payload.artifact.model_dump(mode="json"))
    if payload.paper_markdown:
        (base / PAPER_FILENAME).write_text(payload.paper_markdown, encoding="utf-8")
    return payload


def load_run(project_id: str, run_id: str) -> AutoResearchRunRead | None:
    path = _run_path(project_id, run_id) / RUN_FILENAME
    if not path.exists():
        return None
    return AutoResearchRunRead.model_validate_json(path.read_text(encoding="utf-8"))


def list_runs(project_id: str) -> list[AutoResearchRunRead]:
    items: list[AutoResearchRunRead] = []
    root = _runs_dir(project_id)
    for path in sorted(root.glob("*/run.json"), reverse=True):
        try:
            items.append(AutoResearchRunRead.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    items.sort(key=lambda item: item.updated_at, reverse=True)
    return items


def save_generated_code(
    project_id: str,
    run_id: str,
    code: str,
    filename: str | None = None,
    subdir: str | None = None,
) -> str:
    base = run_dir(project_id, run_id)
    if subdir:
        base = base / subdir
        base.mkdir(parents=True, exist_ok=True)
    path = base / (filename or CODE_FILENAME)
    path.write_text(code, encoding="utf-8")
    return str(path)


def paper_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_FILENAME)


def candidate_paper_file_path(project_id: str, run_id: str, candidate_id: str) -> str:
    return str(candidate_dir(project_id, run_id, candidate_id) / PAPER_FILENAME)


def save_benchmark_snapshot(project_id: str, run_id: str, payload: dict) -> str:
    path = run_dir(project_id, run_id) / BENCHMARK_FILENAME
    _write_json(path, payload)
    return str(path)


def save_candidate_snapshot(
    project_id: str,
    run_id: str,
    candidate: HypothesisCandidate,
    *,
    plan: ResearchPlan,
    spec: ExperimentSpec,
) -> HypothesisCandidate:
    base = candidate_dir(project_id, run_id, candidate.id)
    payload = candidate.model_copy(
        update={
            "workspace_path": str(base),
            "plan_path": str(base / PLAN_FILENAME),
            "spec_path": str(base / SPEC_FILENAME),
            "attempts_path": str(base / ATTEMPTS_FILENAME) if candidate.attempts else None,
            "artifact_path": str(base / ARTIFACT_FILENAME) if candidate.artifact is not None else None,
            "paper_path": (
                candidate.paper_path
                or (str(base / PAPER_FILENAME) if candidate.paper_markdown else None)
            ),
        }
    )
    _write_json(base / CANDIDATE_FILENAME, payload.model_dump(mode="json"))
    _write_json(base / PLAN_FILENAME, plan.model_dump(mode="json"))
    _write_json(base / SPEC_FILENAME, spec.model_dump(mode="json"))
    if payload.attempts:
        _write_json(
            base / ATTEMPTS_FILENAME,
            [item.model_dump(mode="json") for item in payload.attempts],
        )
    if payload.artifact is not None:
        _write_json(base / ARTIFACT_FILENAME, payload.artifact.model_dump(mode="json"))
    if payload.paper_markdown:
        (base / PAPER_FILENAME).write_text(payload.paper_markdown, encoding="utf-8")
    return payload


def save_candidate_manifest(
    project_id: str,
    run_id: str,
    candidate: HypothesisCandidate,
    *,
    decision: PortfolioDecisionRecord | None = None,
) -> HypothesisCandidate:
    base = candidate_dir(project_id, run_id, candidate.id)
    manifest_path = base / MANIFEST_FILENAME
    manifest_payload = {
        "candidate": {
            "id": candidate.id,
            "program_id": candidate.program_id,
            "rank": candidate.rank,
            "title": candidate.title,
            "status": candidate.status,
            "objective_score": candidate.score,
            "selection_reason": candidate.selection_reason,
        },
        "decision": decision.model_dump(mode="json") if decision is not None else None,
        "files": {
            "workspace_path": str(base),
            "candidate_path": str(base / CANDIDATE_FILENAME),
            "plan_path": candidate.plan_path,
            "spec_path": candidate.spec_path,
            "attempts_path": candidate.attempts_path,
            "artifact_path": candidate.artifact_path,
            "generated_code_path": candidate.generated_code_path,
            "paper_path": candidate.paper_path,
        },
    }
    _write_json(manifest_path, manifest_payload)
    return candidate.model_copy(update={"manifest_path": str(manifest_path)})
