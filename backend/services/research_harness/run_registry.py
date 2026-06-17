"""In-memory registry of background research runs.

A full V0 run takes 10-15 minutes and hits the live LLM + literature APIs, so the
``start`` endpoint must return immediately and execute the pipeline on a daemon
thread. This registry tracks the live thread + last-known status per run_id so
the ``status`` endpoint can report ``running`` while the thread is alive.

This is intentionally process-local (single uvicorn worker). It is *not* the source
of truth — ``timeline.jsonl`` and ``project.json`` on disk are. The registry only
augments disk-derived status with "is a thread currently executing this run?".
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable


@dataclass
class RunRecord:
    run_id: str
    project_id: str
    idea: str
    status: str = "running"  # running | done | error
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished_at: str | None = None
    error: str | None = None
    thread: threading.Thread | None = field(default=None, repr=False)


class RunRegistry:
    """Thread-safe map of run_id → RunRecord."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._lock = threading.Lock()

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def is_running(self, run_id: str) -> bool:
        record = self.get(run_id)
        if record is None or record.thread is None:
            return False
        return record.thread.is_alive() and record.status == "running"

    def register(self, run_id: str, project_id: str, idea: str) -> RunRecord:
        record = RunRecord(run_id=run_id, project_id=project_id, idea=idea)
        with self._lock:
            self._runs[run_id] = record
        return record

    def attach_thread(self, run_id: str, thread: threading.Thread) -> None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is not None:
                record.thread = thread

    def mark_finished(self, run_id: str, status: str, error: str | None = None) -> None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is not None:
                record.status = status
                record.finished_at = datetime.now().isoformat(timespec="seconds")
                record.error = error

    def spawn(self, run_id: str, project_id: str, idea: str, target: Callable[[], None]) -> RunRecord:
        """Register a run and start a daemon thread executing ``target``.

        The caller is responsible for invoking :func:`mark_finished` from inside
        ``target`` (or relying on the wrapper below).
        """
        record = self.register(run_id, project_id, idea)

        def _wrapped() -> None:
            try:
                target()
                self.mark_finished(run_id, "done")
            except Exception as exc:  # noqa: BLE001 — record + never kill the worker silently
                self.mark_finished(run_id, "error", error=str(exc))

        thread = threading.Thread(target=_wrapped, name=f"research-run-{run_id}", daemon=True)
        self.attach_thread(run_id, thread)
        thread.start()
        return record


# Module-level singleton — the API layer shares one registry across requests.
REGISTRY = RunRegistry()
