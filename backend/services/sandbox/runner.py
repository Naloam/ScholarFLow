from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from time import perf_counter
from pathlib import Path
from uuid import uuid4

from services.workspace import project_root


DEFAULT_IMAGE = "python:3.11-slim"


def _prepare_workdir(project_id: str, code: str) -> Path:
    run_id = f"run_{uuid4().hex}"
    workdir = (project_root(project_id) / "sandbox" / run_id).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "main.py").write_text(code, encoding="utf-8")
    return workdir


def _extract_outputs(stdout: str, stderr: str, returncode: int) -> dict:
    outputs = {"stdout": stdout, "stderr": stderr, "returncode": returncode}
    try:
        if "__RESULT__" in stdout:
            payload = stdout.split("__RESULT__", 1)[1].strip()
            outputs["result"] = json.loads(payload)
    except Exception:
        pass
    return outputs


def _run_python_local(workdir: Path, timeout: int) -> tuple[str, dict]:
    proc = subprocess.run(
        [sys.executable, "main.py"],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return "\n".join([stdout, stderr]).strip(), _extract_outputs(stdout, stderr, proc.returncode)


def run_python_in_docker(project_id: str, code: str, image: str | None = None) -> tuple[str, dict]:
    image = image or DEFAULT_IMAGE
    workdir = _prepare_workdir(project_id, code)
    started = perf_counter()
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
        if shutil.which("docker"):
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            outputs = _extract_outputs(stdout, stderr, proc.returncode)
            if proc.returncode == 0 or "__RESULT__" in stdout:
                outputs["executor_mode"] = "docker"
                outputs["docker_image"] = image
                outputs["workdir"] = str(workdir)
                outputs["duration_ms"] = int((perf_counter() - started) * 1000)
                outputs["host_platform"] = platform.platform()
                return "\n".join([stdout, stderr]).strip(), outputs
        logs, outputs = _run_python_local(workdir, timeout=300)
        outputs["executor_mode"] = "local_fallback"
        outputs["docker_image"] = image
        outputs["workdir"] = str(workdir)
        outputs["duration_ms"] = int((perf_counter() - started) * 1000)
        outputs["host_platform"] = platform.platform()
        outputs["host_python"] = sys.version.split()[0]
        return logs, outputs
    except Exception as exc:
        return str(exc), {
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "executor_mode": "error",
            "docker_image": image,
            "workdir": str(workdir),
            "duration_ms": int((perf_counter() - started) * 1000),
            "host_platform": platform.platform(),
            "host_python": sys.version.split()[0],
        }
