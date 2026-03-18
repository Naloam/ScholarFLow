from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from schemas.autoresearch import ExecutionBackendSpec
from services.sandbox.backends import DEFAULT_IMAGE, ExecutionContext, resolve_backend
from services.workspace import project_root


def _prepare_workdir(project_id: str, code: str) -> Path:
    run_id = f"run_{uuid4().hex}"
    workdir = (project_root(project_id) / "sandbox" / run_id).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "main.py").write_text(code, encoding="utf-8")
    return workdir


def run_python_in_sandbox(
    project_id: str,
    code: str,
    execution_backend: ExecutionBackendSpec | None = None,
) -> tuple[str, dict]:
    spec = execution_backend or ExecutionBackendSpec()
    image = spec.docker_image or DEFAULT_IMAGE
    workdir = _prepare_workdir(project_id, code)
    context = ExecutionContext(
        workdir=workdir,
        timeout_seconds=spec.timeout_seconds,
        docker_image=image,
    )
    backend = resolve_backend(spec)
    try:
        return backend.run(context)
    except Exception as exc:
        return str(exc), {
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "executor_mode": "error",
            "docker_image": image,
            "workdir": str(workdir),
        }
