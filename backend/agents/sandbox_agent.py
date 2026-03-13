from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from services.sandbox.runner import run_python_in_docker


class SandboxAgent(BaseAgent):
    name = "sandbox"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = payload.get("project_id") or ""
        code = payload.get("code") or ""
        image = payload.get("docker_image")
        logs, outputs = run_python_in_docker(project_id, code, image)
        return {"logs": logs, "outputs": outputs}
