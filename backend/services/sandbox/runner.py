from __future__ import annotations

import json
import subprocess
from pathlib import Path
from uuid import uuid4

from services.workspace import project_root


DEFAULT_IMAGE = "python:3.11-slim"


def run_python_in_docker(project_id: str, code: str, image: str | None = None) -> tuple[str, dict]:
    image = image or DEFAULT_IMAGE
    run_id = f"run_{uuid4().hex}"
    workdir = project_root(project_id) / "sandbox" / run_id
    workdir.mkdir(parents=True, exist_ok=True)
    code_path = workdir / "main.py"
    code_path.write_text(code, encoding="utf-8")

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{workdir}:/work",
        "-w",
        "/work",
        image,
        "python",
        "main.py",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        outputs = {"stdout": stdout, "stderr": stderr, "returncode": proc.returncode}
        try:
            if "__RESULT__" in stdout:
                payload = stdout.split("__RESULT__", 1)[1].strip()
                outputs["result"] = json.loads(payload)
        except Exception:
            pass
        return "\n".join([stdout, stderr]).strip(), outputs
    except Exception as exc:
        return str(exc), {"stdout": "", "stderr": str(exc), "returncode": -1}
