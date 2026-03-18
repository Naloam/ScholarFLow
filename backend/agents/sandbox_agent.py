from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from schemas.autoresearch import ExecutionBackendSpec
from services.sandbox.runner import run_python_in_sandbox


class SandboxAgent(BaseAgent):
    name = "sandbox"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = payload.get("project_id") or ""
        code = payload.get("code") or ""
        env = payload.get("env") if isinstance(payload.get("env"), dict) else None
        backend_payload = payload.get("execution_backend")
        backend = (
            ExecutionBackendSpec.model_validate(backend_payload)
            if isinstance(backend_payload, dict)
            else None
        )
        if backend is None and payload.get("docker_image"):
            backend = ExecutionBackendSpec(docker_image=payload.get("docker_image"))
        logs, outputs = run_python_in_sandbox(project_id, code, backend, env)
        return {"logs": logs, "outputs": outputs}
