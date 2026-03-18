from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from schemas.autoresearch import AutoResearchRunRead
from services.workspace import autoresearch_dir


RUN_FILENAME = "run.json"
PLAN_FILENAME = "plan.json"
SPEC_FILENAME = "spec.json"
ARTIFACT_FILENAME = "artifact.json"
CODE_FILENAME = "experiment.py"
PAPER_FILENAME = "paper.md"
BENCHMARK_FILENAME = "benchmark.json"


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


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def create_run(project_id: str, topic: str, docker_image: str | None = None) -> AutoResearchRunRead:
    now = _utcnow()
    run = AutoResearchRunRead(
        id=f"arun_{uuid4().hex}",
        project_id=project_id,
        topic=topic,
        status="queued",
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
    if payload.plan is not None:
        _write_json(base / PLAN_FILENAME, payload.plan.model_dump(mode="json"))
    if payload.spec is not None:
        _write_json(base / SPEC_FILENAME, payload.spec.model_dump(mode="json"))
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


def save_generated_code(project_id: str, run_id: str, code: str) -> str:
    path = run_dir(project_id, run_id) / CODE_FILENAME
    path.write_text(code, encoding="utf-8")
    return str(path)


def paper_file_path(project_id: str, run_id: str) -> str:
    return str(_run_path(project_id, run_id) / PAPER_FILENAME)


def save_benchmark_snapshot(project_id: str, run_id: str, payload: dict) -> str:
    path = run_dir(project_id, run_id) / BENCHMARK_FILENAME
    _write_json(path, payload)
    return str(path)
