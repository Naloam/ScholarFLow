from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Protocol

from config.settings import settings
from schemas.autoresearch import ExecutionBackendSpec


DEFAULT_IMAGE = "python:3.11-slim"


def extract_outputs(stdout: str, stderr: str, returncode: int) -> dict:
    outputs = {"stdout": stdout, "stderr": stderr, "returncode": returncode}
    try:
        if "__RESULT__" in stdout:
            payload = stdout.split("__RESULT__", 1)[1].strip()
            outputs["result"] = json.loads(payload)
    except Exception:
        pass
    return outputs


@dataclass(frozen=True)
class ExecutionContext:
    workdir: Path
    timeout_seconds: int
    docker_image: str
    env: dict[str, str] = field(default_factory=dict)


class SandboxBackend(Protocol):
    name: str

    def run(self, context: ExecutionContext) -> tuple[str, dict]:
        ...


def _finalize_outputs(
    *,
    backend_name: str,
    context: ExecutionContext,
    started: float,
    stdout: str,
    stderr: str,
    returncode: int,
    extra: dict | None = None,
) -> tuple[str, dict]:
    outputs = extract_outputs(stdout, stderr, returncode)
    outputs["executor_mode"] = backend_name
    outputs["docker_image"] = context.docker_image
    outputs["workdir"] = str(context.workdir)
    outputs["duration_ms"] = int((perf_counter() - started) * 1000)
    outputs["host_platform"] = platform.platform()
    outputs["host_python"] = sys.version.split()[0]
    if extra:
        outputs.update(extra)
    return "\n".join([stdout, stderr]).strip(), outputs


class LocalSandboxBackend:
    name = "local"

    def run(self, context: ExecutionContext) -> tuple[str, dict]:
        started = perf_counter()
        env = os.environ.copy()
        env.update(context.env)
        proc = subprocess.run(
            [sys.executable, "main.py"],
            cwd=str(context.workdir),
            capture_output=True,
            text=True,
            timeout=context.timeout_seconds,
            env=env,
        )
        return _finalize_outputs(
            backend_name=self.name,
            context=context,
            started=started,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            returncode=proc.returncode,
        )


class CommandSandboxBackend:
    name = "command"

    def __init__(self, prefix: list[str]) -> None:
        self.prefix = prefix

    def run(self, context: ExecutionContext) -> tuple[str, dict]:
        started = perf_counter()
        command = self.prefix + [str(context.workdir / "main.py")]
        env = os.environ.copy()
        env.update(context.env)
        proc = subprocess.run(
            command,
            cwd=str(context.workdir),
            capture_output=True,
            text=True,
            timeout=context.timeout_seconds,
            env=env,
        )
        return _finalize_outputs(
            backend_name=self.name,
            context=context,
            started=started,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            returncode=proc.returncode,
            extra={"command_prefix": self.prefix},
        )


class DockerSandboxBackend:
    name = "docker"

    def __init__(self, *, use_gpu: bool = False) -> None:
        self.use_gpu = use_gpu
        if use_gpu:
            self.name = "docker_gpu"

    def run(self, context: ExecutionContext) -> tuple[str, dict]:
        started = perf_counter()
        command = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{context.workdir}:/work",
            "-w",
            "/work",
        ]
        for key, value in context.env.items():
            command.extend(["-e", f"{key}={value}"])
        if self.use_gpu:
            command.extend(["--gpus", "all"])
        command.extend([context.docker_image, "python", "main.py"])
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=context.timeout_seconds,
        )
        return _finalize_outputs(
            backend_name=self.name,
            context=context,
            started=started,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            returncode=proc.returncode,
            extra={"gpu_requested": self.use_gpu},
        )


def _configured_command_prefix(spec: ExecutionBackendSpec | None) -> list[str]:
    if spec and spec.command_prefix:
        return spec.command_prefix
    return settings.sandbox_command_prefix


@lru_cache(maxsize=1)
def _docker_is_usable() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return proc.returncode == 0


def resolve_backend(spec: ExecutionBackendSpec | None = None) -> SandboxBackend:
    requested = (spec.kind if spec else settings.sandbox_backend).strip().lower()
    if requested == "local":
        return LocalSandboxBackend()
    if requested == "command":
        prefix = _configured_command_prefix(spec)
        return CommandSandboxBackend(prefix) if prefix else LocalSandboxBackend()
    if requested == "docker":
        return DockerSandboxBackend()
    if requested == "docker_gpu":
        return DockerSandboxBackend(use_gpu=True)

    if requested == "auto":
        if (spec.gpu_required if spec else False) and _docker_is_usable():
            return DockerSandboxBackend(use_gpu=True)
        if _docker_is_usable():
            return DockerSandboxBackend()
        prefix = _configured_command_prefix(spec)
        if prefix:
            return CommandSandboxBackend(prefix)
        return LocalSandboxBackend()

    return LocalSandboxBackend()
