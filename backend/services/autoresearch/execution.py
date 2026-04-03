from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Event, Lock, Thread
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

import config.db as db_module
from schemas.autoresearch import (
    AutoResearchExecutionJob,
    AutoResearchJobAction,
    AutoResearchQueuePriority,
    AutoResearchQueueTelemetryRead,
    AutoResearchRunConfig,
    AutoResearchRunControlPatch,
    AutoResearchRunExecutionRead,
    AutoResearchRunRead,
    AutoResearchWorkerState,
)
from services.autoresearch.orchestrator import (
    AutoResearchExecutionCancelled,
    AutoResearchOrchestrator,
)
from services.autoresearch.repository import load_run, save_run
from services.security.audit import write_task_audit_log
from services.workspace import autoresearch_execution_dir


QUEUE_FILENAME = "queue.json"
QUEUE_LOCK_FILENAME = "queue.lock"
LEASE_TIMEOUT = timedelta(minutes=15)
HEARTBEAT_INTERVAL = timedelta(seconds=5)
WORKER_RETENTION = timedelta(hours=12)
_UNSET = object()
_STATE_LOCK = Lock()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _default_worker_id() -> str:
    return f"autoresearch-worker-{os.getpid()}-{uuid4().hex[:12]}"


def _priority_rank(priority: AutoResearchQueuePriority) -> int:
    if priority == "high":
        return 2
    if priority == "normal":
        return 1
    return 0


def _latest_timestamp(*values: datetime | None) -> datetime | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _worker_is_stale(worker: AutoResearchWorkerState, *, now: datetime) -> bool:
    if worker.status == "idle":
        return False
    if worker.current_job_id is None or worker.current_lease_id is None:
        return False
    if worker.heartbeat_at is None:
        return False
    return now - worker.heartbeat_at > LEASE_TIMEOUT


def _worker_activity_rank(worker: AutoResearchWorkerState) -> tuple[int, float, str]:
    latest = _latest_timestamp(
        worker.heartbeat_at,
        worker.last_started_at,
        worker.last_completed_at,
        worker.last_recovered_at,
    )
    latest_timestamp = latest.timestamp() if latest is not None else 0.0
    status_rank = 0
    if worker.stale:
        status_rank = 3
    elif worker.current_job_id is not None:
        status_rank = 2
    elif worker.status != "idle":
        status_rank = 1
    return (status_rank, latest_timestamp, worker.worker_id or "")


def _should_prune_worker(worker: AutoResearchWorkerState, *, now: datetime) -> bool:
    if worker.current_job_id is not None or worker.current_lease_id is not None:
        return False
    if worker.status != "idle":
        return False
    latest = _latest_timestamp(
        worker.heartbeat_at,
        worker.last_started_at,
        worker.last_completed_at,
        worker.last_recovered_at,
    )
    if latest is None:
        return False
    return now - latest > WORKER_RETENTION


class _ExecutionQueueState(BaseModel):
    version: int = 2
    jobs: list[AutoResearchExecutionJob] = Field(default_factory=list)
    workers: list[AutoResearchWorkerState] = Field(default_factory=list)
    telemetry: AutoResearchQueueTelemetryRead = Field(default_factory=AutoResearchQueueTelemetryRead)


def _queue_path():
    return autoresearch_execution_dir() / QUEUE_FILENAME


def _queue_lock_path():
    return autoresearch_execution_dir() / QUEUE_LOCK_FILENAME


@contextmanager
def _locked_queue_state():
    lock_path = _queue_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _STATE_LOCK:
        with lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _refresh_state(state: _ExecutionQueueState) -> _ExecutionQueueState:
    now = _utcnow()
    queued_jobs = sum(1 for job in state.jobs if job.status == "queued")
    refreshed_workers: list[AutoResearchWorkerState] = []
    for worker in state.workers:
        refreshed_worker = worker.model_copy(
            update={
                "queue_depth": queued_jobs,
                "lease_expires_at": (
                    worker.heartbeat_at + LEASE_TIMEOUT
                    if worker.heartbeat_at is not None
                    else None
                ),
                "stale": _worker_is_stale(worker, now=now),
            }
        )
        if _should_prune_worker(refreshed_worker, now=now):
            continue
        refreshed_workers.append(refreshed_worker)
    refreshed_workers.sort(key=_worker_activity_rank, reverse=True)

    telemetry = AutoResearchQueueTelemetryRead(
        queue_depth=queued_jobs,
        total_jobs=len(state.jobs),
        queued_jobs=queued_jobs,
        leased_jobs=sum(1 for job in state.jobs if job.status == "leased"),
        running_jobs=sum(1 for job in state.jobs if job.status == "running"),
        succeeded_jobs=sum(1 for job in state.jobs if job.status == "succeeded"),
        failed_jobs=sum(1 for job in state.jobs if job.status == "failed"),
        canceled_jobs=sum(1 for job in state.jobs if job.status == "canceled"),
        worker_count=len(refreshed_workers),
        active_workers=sum(
            1
            for worker in refreshed_workers
            if worker.status != "idle" and not worker.stale
        ),
        idle_workers=sum(1 for worker in refreshed_workers if worker.status == "idle"),
        stale_workers=sum(1 for worker in refreshed_workers if worker.stale),
        total_processed_jobs=sum(worker.processed_jobs for worker in refreshed_workers),
        total_recovered_jobs=sum(job.recovery_count for job in state.jobs),
        last_recovered_at=_latest_timestamp(
            *[job.last_recovered_at for job in state.jobs],
            *[worker.last_recovered_at for worker in refreshed_workers],
        ),
        last_job_started_at=_latest_timestamp(
            *[job.started_at for job in state.jobs],
            *[worker.last_started_at for worker in refreshed_workers],
        ),
        last_job_finished_at=_latest_timestamp(
            *[job.finished_at for job in state.jobs],
            *[worker.last_completed_at for worker in refreshed_workers],
        ),
    )
    return state.model_copy(
        update={
            "version": 2,
            "workers": refreshed_workers,
            "telemetry": telemetry,
        }
    )


def _load_state_unlocked() -> _ExecutionQueueState:
    path = _queue_path()
    if not path.exists():
        return _refresh_state(_ExecutionQueueState())
    raw_text = path.read_text(encoding="utf-8")
    if not raw_text.strip():
        return _refresh_state(_ExecutionQueueState())
    raw_payload = json.loads(raw_text)
    if isinstance(raw_payload, dict) and "workers" not in raw_payload:
        legacy_worker = raw_payload.get("worker")
        raw_payload = {
            **raw_payload,
            "version": 2,
            "workers": [legacy_worker] if legacy_worker is not None else [],
        }
    state = _ExecutionQueueState.model_validate(raw_payload)
    return _refresh_state(state)


def _save_state_unlocked(state: _ExecutionQueueState) -> _ExecutionQueueState:
    state = _refresh_state(state)
    path = _queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(
            state.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    temp_path.replace(path)
    return state


class AutoResearchExecutionPlane:
    def __init__(self, *, worker_id: str | None = None) -> None:
        self.worker_id = worker_id or _default_worker_id()
        self._drain_lock = Lock()

    def _run_config(self, run: AutoResearchRunRead) -> AutoResearchRunConfig:
        if run.request is not None:
            return run.request
        return AutoResearchRunConfig(
            task_family_hint=run.task_family,
            language="en",
            max_rounds=3,
            queue_priority="normal",
            benchmark=run.benchmark,
            execution_backend=run.execution_backend,
            experiment_bridge=None,
            auto_search_literature=False,
            auto_fetch_literature=False,
            docker_image=run.docker_image,
        )

    def _find_worker(
        self,
        state: _ExecutionQueueState,
        worker_id: str | None = None,
    ) -> tuple[int | None, AutoResearchWorkerState | None]:
        target_id = worker_id or self.worker_id
        for index, worker in enumerate(state.workers):
            if worker.worker_id == target_id:
                return index, worker
        return None, None

    def _touch_worker_unlocked(
        self,
        state: _ExecutionQueueState,
        *,
        worker_id: str | None = None,
        status: str | object = _UNSET,
        job_id: str | None | object = _UNSET,
        run_id: str | None | object = _UNSET,
        lease_id: str | None | object = _UNSET,
        error: str | None | object = _UNSET,
        heartbeat_at: datetime | None | object = _UNSET,
        last_started_at: datetime | None | object = _UNSET,
        last_completed_at: datetime | None | object = _UNSET,
        last_recovered_at: datetime | None | object = _UNSET,
        increment_processed: int = 0,
        increment_recovered: int = 0,
    ) -> _ExecutionQueueState:
        target_id = worker_id or self.worker_id
        index, worker = self._find_worker(state, target_id)
        if worker is None:
            worker = AutoResearchWorkerState(worker_id=target_id)
        updates: dict[str, Any] = {
            "worker_id": target_id,
            "heartbeat_at": _utcnow() if heartbeat_at is _UNSET else heartbeat_at,
        }
        if status is not _UNSET:
            updates["status"] = status
        if job_id is not _UNSET:
            updates["current_job_id"] = job_id
        if run_id is not _UNSET:
            updates["current_run_id"] = run_id
        if lease_id is not _UNSET:
            updates["current_lease_id"] = lease_id
        if error is not _UNSET:
            updates["last_error"] = error
        if last_started_at is not _UNSET:
            updates["last_started_at"] = last_started_at
        if last_completed_at is not _UNSET:
            updates["last_completed_at"] = last_completed_at
        if last_recovered_at is not _UNSET:
            updates["last_recovered_at"] = last_recovered_at
        if increment_processed:
            updates["processed_jobs"] = worker.processed_jobs + increment_processed
        if increment_recovered:
            updates["recovered_job_count"] = worker.recovered_job_count + increment_recovered
        updated_worker = worker.model_copy(update=updates)
        workers = list(state.workers)
        if index is None:
            workers.append(updated_worker)
        else:
            workers[index] = updated_worker
        return state.model_copy(update={"workers": workers})

    def _select_run_worker(
        self,
        jobs: list[AutoResearchExecutionJob],
        workers: list[AutoResearchWorkerState],
    ) -> AutoResearchWorkerState | None:
        active_worker_ids = {
            job.worker_id
            for job in jobs
            if job.status in {"leased", "running"} and job.worker_id is not None
        }
        for worker in workers:
            if worker.worker_id in active_worker_ids:
                return worker
        known_worker_ids = [job.worker_id for job in reversed(jobs) if job.worker_id is not None]
        for worker_id in known_worker_ids:
            for worker in workers:
                if worker.worker_id == worker_id:
                    return worker
        if len(workers) == 1:
            return workers[0]
        return None

    def _update_run_for_enqueue(self, run: AutoResearchRunRead) -> AutoResearchRunRead:
        return save_run(
            run.model_copy(
                update={
                    "status": "queued",
                    "error": None,
                }
            )
        )

    def _update_run_status(
        self,
        project_id: str,
        run_id: str,
        *,
        status: str,
        detail: str,
    ) -> None:
        run = load_run(project_id, run_id)
        if run is None:
            return
        save_run(
            run.model_copy(
                update={
                    "status": status,
                    "error": detail,
                }
            )
        )

    def _update_run_for_cancel(self, project_id: str, run_id: str, detail: str) -> None:
        self._update_run_status(project_id, run_id, status="canceled", detail=detail)

    def _update_run_for_failure(self, project_id: str, run_id: str, detail: str) -> None:
        self._update_run_status(project_id, run_id, status="failed", detail=detail)

    def _recover_stale_workers_unlocked(
        self,
        state: _ExecutionQueueState,
    ) -> tuple[_ExecutionQueueState, list[tuple[str, str, str]]]:
        state = _refresh_state(state)
        now = _utcnow()
        stale_worker_ids = {
            worker.worker_id
            for worker in state.workers
            if worker.worker_id is not None and _worker_is_stale(worker, now=now)
        }
        if not stale_worker_ids:
            return state, []

        recovered_job_count = 0
        canceled_runs: list[tuple[str, str, str]] = []
        recovered_jobs: list[AutoResearchExecutionJob] = []
        for job in state.jobs:
            if job.status not in {"leased", "running"} or job.worker_id not in stale_worker_ids:
                recovered_jobs.append(job)
                continue
            recovered_job_count += 1
            if job.cancellation_requested_at is not None:
                detail = "Recovered canceled job after stale worker lease."
                recovered_jobs.append(
                    job.model_copy(
                        update={
                            "status": "canceled",
                            "detail": "lease_recovered_after_cancel",
                            "lease_id": None,
                            "finished_at": now,
                            "recovery_count": job.recovery_count + 1,
                            "last_recovered_at": now,
                            "error": job.error or detail,
                            "worker_id": self.worker_id,
                        }
                    )
                )
                canceled_runs.append((job.project_id, job.run_id, detail))
                continue
            recovered_jobs.append(
                job.model_copy(
                    update={
                        "status": "queued",
                        "detail": "lease_recovered",
                        "lease_id": None,
                        "started_at": None,
                        "recovery_count": job.recovery_count + 1,
                        "last_recovered_at": now,
                        "worker_id": None,
                    }
                )
            )

        recovered_workers: list[AutoResearchWorkerState] = []
        for worker in state.workers:
            if worker.worker_id in stale_worker_ids:
                recovered_workers.append(
                    worker.model_copy(
                        update={
                            "status": "idle",
                            "current_job_id": None,
                            "current_run_id": None,
                            "current_lease_id": None,
                            "heartbeat_at": now,
                            "last_recovered_at": now,
                            "last_error": "Recovered stale auto-research worker lease.",
                        }
                    )
                )
                continue
            recovered_workers.append(worker)

        recovered_state = state.model_copy(
            update={
                "jobs": recovered_jobs,
                "workers": recovered_workers,
            }
        )
        if recovered_job_count:
            recovered_state = self._touch_worker_unlocked(
                recovered_state,
                worker_id=self.worker_id,
                status="idle",
                job_id=None,
                run_id=None,
                lease_id=None,
                error="Recovered stale auto-research worker lease.",
                heartbeat_at=now,
                last_recovered_at=now,
                increment_recovered=recovered_job_count,
            )
        return recovered_state, canceled_runs

    def _sync_worker(
        self,
        *,
        status: str,
        job_id: str | None,
        run_id: str | None,
        lease_id: str | None = None,
        error: str | None | object = _UNSET,
        expected_lease_id: str | None = None,
    ) -> None:
        with _locked_queue_state():
            state = _load_state_unlocked()
            _, worker = self._find_worker(state)
            if worker is None and status == "idle" and job_id is None:
                return
            if expected_lease_id is not None:
                if worker is None or worker.current_lease_id != expected_lease_id:
                    return
            elif status == "idle" and job_id is None and worker is not None and worker.current_job_id is not None:
                return
            processed_jobs = 0
            last_completed_at: datetime | None | object = _UNSET
            if status == "idle" and worker is not None and worker.current_job_id is not None:
                processed_jobs = 1
                last_completed_at = _utcnow()
            state = self._touch_worker_unlocked(
                state,
                status=status,
                job_id=job_id,
                run_id=run_id,
                lease_id=lease_id,
                error=error,
                last_completed_at=last_completed_at,
                increment_processed=processed_jobs,
            )
            _save_state_unlocked(state)

    def _update_job(
        self,
        job_id: str,
        *,
        status: str,
        detail: str | None = None,
        error: str | None = None,
        cancellation_requested_at: datetime | None = None,
        expected_lease_id: str | None = None,
    ) -> AutoResearchExecutionJob | None:
        with _locked_queue_state():
            state = _load_state_unlocked()
            updated_job: AutoResearchExecutionJob | None = None
            now = _utcnow()
            jobs: list[AutoResearchExecutionJob] = []
            for job in state.jobs:
                if job.id != job_id:
                    jobs.append(job)
                    continue
                if expected_lease_id is not None and job.lease_id != expected_lease_id:
                    jobs.append(job)
                    continue
                payload: dict[str, object] = {
                    "status": status,
                    "detail": detail if detail is not None else job.detail,
                    "error": error,
                    "worker_id": self.worker_id,
                }
                if status in {"leased", "running"}:
                    payload["started_at"] = job.started_at or now
                if status in {"succeeded", "failed", "canceled"}:
                    payload["finished_at"] = now
                if status == "leased":
                    payload["attempt_count"] = job.attempt_count + 1
                    payload["lease_id"] = f"lease_{uuid4().hex}"
                if cancellation_requested_at is not None:
                    payload["cancellation_requested_at"] = cancellation_requested_at
                updated_job = job.model_copy(update=payload)
                jobs.append(updated_job)
            if updated_job is None:
                return None
            state = state.model_copy(update={"jobs": jobs})
            _save_state_unlocked(state)
            return updated_job

    def _lease_next_job(self) -> AutoResearchExecutionJob | None:
        canceled_runs: list[tuple[str, str, str]] = []
        with _locked_queue_state():
            state = _load_state_unlocked()
            state, canceled_runs = self._recover_stale_workers_unlocked(state)
            now = _utcnow()
            jobs: list[AutoResearchExecutionJob] = []
            leased_job: AutoResearchExecutionJob | None = None
            queued_indices = [
                index
                for index, job in enumerate(state.jobs)
                if job.status == "queued"
            ]
            selected_index = None
            if queued_indices:
                selected_index = max(
                    queued_indices,
                    key=lambda index: (
                        _priority_rank(state.jobs[index].priority),
                        -state.jobs[index].enqueued_at.timestamp(),
                    ),
                )
            for index, job in enumerate(state.jobs):
                if selected_index is not None and index == selected_index:
                    leased_job = job.model_copy(
                        update={
                            "status": "leased",
                            "lease_id": f"lease_{uuid4().hex}",
                            "worker_id": self.worker_id,
                            "started_at": now,
                            "attempt_count": job.attempt_count + 1,
                        }
                    )
                    jobs.append(leased_job)
                    continue
                jobs.append(job)
            state = state.model_copy(update={"jobs": jobs})
            if leased_job is None:
                _, worker = self._find_worker(state)
                if worker is not None:
                    state = self._touch_worker_unlocked(
                        state,
                        status="idle",
                        job_id=None,
                        run_id=None,
                        lease_id=None,
                        error=worker.last_error,
                    )
                _save_state_unlocked(state)
            else:
                state = self._touch_worker_unlocked(
                    state,
                    status="starting",
                    job_id=leased_job.id,
                    run_id=leased_job.run_id,
                    lease_id=leased_job.lease_id,
                    error=None,
                    heartbeat_at=now,
                    last_started_at=now,
                )
                _save_state_unlocked(state)
        for project_id, run_id, detail in canceled_runs:
            self._update_run_for_cancel(project_id, run_id, detail)
        return leased_job

    def _is_cancel_requested(self, job_id: str, lease_id: str | None) -> bool:
        with _locked_queue_state():
            state = _load_state_unlocked()
            _, worker = self._find_worker(state)
            if (
                worker is not None
                and worker.current_job_id == job_id
                and worker.current_lease_id == lease_id
            ):
                state = self._touch_worker_unlocked(state, worker_id=self.worker_id)
                _save_state_unlocked(state)
            for job in state.jobs:
                if job.id == job_id:
                    if lease_id is not None and job.lease_id != lease_id:
                        return False
                    return job.cancellation_requested_at is not None
        return False

    def _heartbeat_loop(self, *, job_id: str, lease_id: str | None) -> None:
        while not self._heartbeat_stop.wait(HEARTBEAT_INTERVAL.total_seconds()):
            with _locked_queue_state():
                state = _load_state_unlocked()
                _, worker = self._find_worker(state)
                if (
                    worker is None
                    or worker.current_job_id != job_id
                    or worker.current_lease_id != lease_id
                ):
                    return
                job = next((item for item in state.jobs if item.id == job_id), None)
                if job is None or job.lease_id != lease_id or job.status not in {"leased", "running"}:
                    return
                state = self._touch_worker_unlocked(
                    state,
                    worker_id=self.worker_id,
                    status=worker.status,
                    job_id=worker.current_job_id,
                    run_id=worker.current_run_id,
                    lease_id=worker.current_lease_id,
                    error=worker.last_error,
                )
                _save_state_unlocked(state)

    @contextmanager
    def _heartbeat(self, *, job_id: str, lease_id: str | None):
        self._heartbeat_stop = Event()
        thread = Thread(
            target=self._heartbeat_loop,
            kwargs={"job_id": job_id, "lease_id": lease_id},
            daemon=True,
            name=f"{self.worker_id}-heartbeat",
        )
        thread.start()
        try:
            yield
        finally:
            self._heartbeat_stop.set()
            thread.join(timeout=HEARTBEAT_INTERVAL.total_seconds() + 1)

    def enqueue(
        self,
        *,
        project_id: str,
        run_id: str,
        action: AutoResearchJobAction | str,
    ) -> tuple[AutoResearchExecutionJob, bool]:
        run = load_run(project_id, run_id)
        if run is None:
            raise ValueError(f"Auto research run not found: {run_id}")
        with _locked_queue_state():
            state = _load_state_unlocked()
            for job in reversed(state.jobs):
                if job.project_id == project_id and job.run_id == run_id and job.status in {
                    "queued",
                    "leased",
                    "running",
                }:
                    return job, False
            queued_job = AutoResearchExecutionJob(
                id=f"arjob_{uuid4().hex}",
                project_id=project_id,
                run_id=run_id,
                action=action,
                priority=self._run_config(run).queue_priority,
                status="queued",
                detail=f"{action}:{run_id}",
                enqueued_at=_utcnow(),
            )
            state.jobs.append(queued_job)
            _save_state_unlocked(state)
        self._update_run_for_enqueue(run)
        queued_job = self.get_run_execution(project_id, run_id).jobs[-1]
        return queued_job, True

    def get_queue_snapshot(self) -> tuple[AutoResearchQueueTelemetryRead, list[AutoResearchWorkerState]]:
        with _locked_queue_state():
            state = _load_state_unlocked()
            return state.telemetry, state.workers

    def get_run_execution(self, project_id: str, run_id: str) -> AutoResearchRunExecutionRead:
        with _locked_queue_state():
            state = _load_state_unlocked()
            jobs = [
                job for job in state.jobs if job.project_id == project_id and job.run_id == run_id
            ]
            active_job = next(
                (job for job in reversed(jobs) if job.status in {"leased", "running"}),
                None,
            )
            return AutoResearchRunExecutionRead(
                project_id=project_id,
                run_id=run_id,
                jobs=jobs,
                active_job_id=active_job.id if active_job is not None else None,
                cancel_requested=(
                    active_job is not None and active_job.cancellation_requested_at is not None
                ),
                queue=state.telemetry,
                worker=self._select_run_worker(jobs, state.workers),
                workers=state.workers,
            )

    def request_cancel(self, *, project_id: str, run_id: str) -> AutoResearchRunExecutionRead:
        canceled_now = False
        running_cancel = False
        now = _utcnow()
        detail = "Run canceled before execution started."
        leased_or_canceled_worker_ids: set[str] = set()
        running_worker_ids: set[str] = set()
        leased_job_ids: set[str] = set()
        running_job_ids: set[str] = set()

        with _locked_queue_state():
            state = _load_state_unlocked()
            jobs: list[AutoResearchExecutionJob] = []
            for job in state.jobs:
                if job.project_id != project_id or job.run_id != run_id:
                    jobs.append(job)
                    continue
                if job.status in {"queued", "leased"}:
                    canceled_now = True
                    if job.status == "leased" and job.worker_id is not None:
                        leased_or_canceled_worker_ids.add(job.worker_id)
                        leased_job_ids.add(job.id)
                    jobs.append(
                        job.model_copy(
                            update={
                                "status": "canceled",
                                "detail": "cancel_requested",
                                "error": detail,
                                "lease_id": None,
                                "finished_at": now,
                                "cancellation_requested_at": now,
                                "worker_id": job.worker_id or self.worker_id,
                            }
                        )
                    )
                    continue
                if job.status == "running":
                    running_cancel = True
                    if job.worker_id is not None:
                        running_worker_ids.add(job.worker_id)
                        running_job_ids.add(job.id)
                    jobs.append(
                        job.model_copy(
                            update={
                                "detail": "cancel_requested",
                                "cancellation_requested_at": job.cancellation_requested_at or now,
                            }
                        )
                    )
                    continue
                jobs.append(job)
            if not canceled_now and not running_cancel:
                raise ValueError("No queued or running auto-research job to cancel")

            workers: list[AutoResearchWorkerState] = []
            for worker in state.workers:
                if worker.worker_id in running_worker_ids and worker.current_job_id in running_job_ids:
                    workers.append(
                        worker.model_copy(
                            update={
                                "status": "stopping",
                                "heartbeat_at": now,
                            }
                        )
                    )
                    continue
                if (
                    worker.worker_id in leased_or_canceled_worker_ids
                    and worker.current_job_id in leased_job_ids
                ):
                    workers.append(
                        worker.model_copy(
                            update={
                                "status": "idle",
                                "current_job_id": None,
                                "current_run_id": None,
                                "current_lease_id": None,
                                "heartbeat_at": now,
                                "last_completed_at": now,
                                "last_error": detail,
                            }
                        )
                    )
                    continue
                workers.append(worker)

            state = state.model_copy(update={"jobs": jobs, "workers": workers})
            _save_state_unlocked(state)

        if canceled_now and not running_cancel:
            self._update_run_for_cancel(project_id, run_id, detail)
            write_task_audit_log(
                db_module.SessionLocal,
                correlation_id=run_id,
                task_name="autoresearch.run",
                project_id=project_id,
                action="canceled",
                status_code=499,
                detail=detail,
            )
        return self.get_run_execution(project_id, run_id)

    def update_run_controls(
        self,
        *,
        project_id: str,
        run_id: str,
        payload: AutoResearchRunControlPatch,
    ) -> AutoResearchRunRead:
        run = load_run(project_id, run_id)
        if run is None:
            raise ValueError(f"Auto research run not found: {run_id}")
        if not payload.model_fields_set:
            return run

        request = self._run_config(run)
        request_updates: dict[str, object] = {}
        if "max_rounds" in payload.model_fields_set:
            request_updates["max_rounds"] = (
                payload.max_rounds if payload.max_rounds is not None else request.max_rounds
            )
        if "candidate_execution_limit" in payload.model_fields_set:
            request_updates["candidate_execution_limit"] = payload.candidate_execution_limit
        if "queue_priority" in payload.model_fields_set:
            request_updates["queue_priority"] = (
                payload.queue_priority if payload.queue_priority is not None else "normal"
            )

        updated_run = save_run(
            run.model_copy(
                update={
                    "request": request.model_copy(update=request_updates),
                }
            )
        )

        if "queue_priority" not in payload.model_fields_set:
            return updated_run

        queue_priority = payload.queue_priority if payload.queue_priority is not None else "normal"
        with _locked_queue_state():
            state = _load_state_unlocked()
            jobs = [
                job.model_copy(update={"priority": queue_priority})
                if job.project_id == project_id and job.run_id == run_id and job.status == "queued"
                else job
                for job in state.jobs
            ]
            _save_state_unlocked(state.model_copy(update={"jobs": jobs}))
        return updated_run

    def _execute_job(self, job: AutoResearchExecutionJob) -> AutoResearchRunRead:
        run = load_run(job.project_id, job.run_id)
        if run is None:
            raise ValueError(f"Auto research run not found: {job.run_id}")
        request = self._run_config(run)
        write_task_audit_log(
            db_module.SessionLocal,
            correlation_id=run.id,
            task_name="autoresearch.run",
            project_id=job.project_id,
            action="running",
            status_code=102,
            detail=f"job_id={job.id} action={job.action} worker_id={self.worker_id}",
        )
        db = db_module.SessionLocal()
        try:
            return AutoResearchOrchestrator().execute(
                db=db,
                project_id=job.project_id,
                run_id=job.run_id,
                topic=run.topic,
                task_family_hint=request.task_family_hint,
                paper_ids=request.paper_ids,
                language=request.language,
                max_rounds=request.max_rounds,
                candidate_execution_limit=request.candidate_execution_limit,
                benchmark_source=request.benchmark,
                execution_backend=request.execution_backend,
                auto_search_literature=request.auto_search_literature,
                auto_fetch_literature=request.auto_fetch_literature,
                docker_image=request.docker_image,
                execution_action=job.action,
                should_cancel=lambda: self._is_cancel_requested(job.id, job.lease_id),
            )
        finally:
            db.close()

    def drain(self) -> None:
        if not self._drain_lock.acquire(blocking=False):
            return
        try:
            while True:
                job = self._lease_next_job()
                if job is None:
                    return
                self._sync_worker(
                    status="running",
                    job_id=job.id,
                    run_id=job.run_id,
                    lease_id=job.lease_id,
                    expected_lease_id=job.lease_id,
                )
                self._update_job(
                    job.id,
                    status="running",
                    detail=f"running:{job.action}",
                    expected_lease_id=job.lease_id,
                )
                with self._heartbeat(job_id=job.id, lease_id=job.lease_id):
                    try:
                        result = self._execute_job(job)
                    except AutoResearchExecutionCancelled as exc:
                        detail = str(exc)
                        self._update_job(
                            job.id,
                            status="canceled",
                            detail="canceled",
                            error=detail,
                            cancellation_requested_at=_utcnow(),
                            expected_lease_id=job.lease_id,
                        )
                        self._sync_worker(
                            status="idle",
                            job_id=None,
                            run_id=None,
                            lease_id=None,
                            error=detail,
                            expected_lease_id=job.lease_id,
                        )
                        write_task_audit_log(
                            db_module.SessionLocal,
                            correlation_id=job.run_id,
                            task_name="autoresearch.run",
                            project_id=job.project_id,
                            action="canceled",
                            status_code=499,
                            detail=f"{detail} worker_id={self.worker_id}",
                        )
                        continue
                    except Exception as exc:
                        detail = str(exc)
                        updated = self._update_job(
                            job.id,
                            status="failed",
                            detail="failed",
                            error=detail,
                            expected_lease_id=job.lease_id,
                        )
                        if updated is not None:
                            self._update_run_for_failure(job.project_id, job.run_id, detail)
                        self._sync_worker(
                            status="idle",
                            job_id=None,
                            run_id=None,
                            lease_id=None,
                            error=detail,
                            expected_lease_id=job.lease_id,
                        )
                        write_task_audit_log(
                            db_module.SessionLocal,
                            correlation_id=job.run_id,
                            task_name="autoresearch.run",
                            project_id=job.project_id,
                            action="failed",
                            status_code=500,
                            detail=f"{detail} worker_id={self.worker_id}",
                        )
                        continue

                if result.status == "done":
                    self._update_job(
                        job.id,
                        status="succeeded",
                        detail="done",
                        error=None,
                        expected_lease_id=job.lease_id,
                    )
                    self._sync_worker(
                        status="idle",
                        job_id=None,
                        run_id=None,
                        lease_id=None,
                        error=None,
                        expected_lease_id=job.lease_id,
                    )
                    write_task_audit_log(
                        db_module.SessionLocal,
                        correlation_id=job.run_id,
                        task_name="autoresearch.run",
                        project_id=job.project_id,
                        action="done",
                        status_code=200,
                        detail=f"job_id={job.id} action={job.action} worker_id={self.worker_id}",
                    )
                elif result.status == "canceled":
                    detail = result.error or "Auto-research run canceled"
                    self._update_job(
                        job.id,
                        status="canceled",
                        detail="canceled",
                        error=detail,
                        cancellation_requested_at=_utcnow(),
                        expected_lease_id=job.lease_id,
                    )
                    self._sync_worker(
                        status="idle",
                        job_id=None,
                        run_id=None,
                        lease_id=None,
                        error=detail,
                        expected_lease_id=job.lease_id,
                    )
                    write_task_audit_log(
                        db_module.SessionLocal,
                        correlation_id=job.run_id,
                        task_name="autoresearch.run",
                        project_id=job.project_id,
                        action="canceled",
                        status_code=499,
                        detail=f"{detail} worker_id={self.worker_id}",
                    )
                else:
                    detail = result.error or "Auto-research run failed"
                    self._update_job(
                        job.id,
                        status="failed",
                        detail="failed",
                        error=detail,
                        expected_lease_id=job.lease_id,
                    )
                    self._sync_worker(
                        status="idle",
                        job_id=None,
                        run_id=None,
                        lease_id=None,
                        error=detail,
                        expected_lease_id=job.lease_id,
                    )
                    write_task_audit_log(
                        db_module.SessionLocal,
                        correlation_id=job.run_id,
                        task_name="autoresearch.run",
                        project_id=job.project_id,
                        action="failed",
                        status_code=500,
                        detail=f"{detail} worker_id={self.worker_id}",
                    )
        finally:
            self._sync_worker(status="idle", job_id=None, run_id=None)
            self._drain_lock.release()
