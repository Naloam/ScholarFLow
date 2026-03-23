from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

import config.db as db_module
from schemas.autoresearch import (
    AutoResearchExecutionJob,
    AutoResearchJobAction,
    AutoResearchRunConfig,
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
LEASE_TIMEOUT = timedelta(minutes=15)
WORKER_ID = f"autoresearch-worker-{os.getpid()}"
_STATE_LOCK = Lock()
_DRAIN_LOCK = Lock()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class _ExecutionQueueState(BaseModel):
    version: int = 1
    jobs: list[AutoResearchExecutionJob] = Field(default_factory=list)
    worker: AutoResearchWorkerState = Field(default_factory=AutoResearchWorkerState)


def _queue_path():
    return autoresearch_execution_dir() / QUEUE_FILENAME


def _load_state() -> _ExecutionQueueState:
    path = _queue_path()
    if not path.exists():
        return _ExecutionQueueState()
    return _ExecutionQueueState.model_validate_json(path.read_text(encoding="utf-8"))


def _save_state(state: _ExecutionQueueState) -> _ExecutionQueueState:
    queued = sum(1 for job in state.jobs if job.status == "queued")
    state = state.model_copy(
        update={
            "worker": state.worker.model_copy(update={"queue_depth": queued}),
        }
    )
    path = _queue_path()
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(path)
    return state


class AutoResearchExecutionPlane:
    def _run_config(self, run: AutoResearchRunRead) -> AutoResearchRunConfig:
        if run.request is not None:
            return run.request
        return AutoResearchRunConfig(
            task_family_hint=run.task_family,
            max_rounds=3,
            benchmark=run.benchmark,
            execution_backend=run.execution_backend,
            auto_search_literature=False,
            auto_fetch_literature=False,
            docker_image=run.docker_image,
        )

    def _update_run_for_enqueue(self, run: AutoResearchRunRead) -> AutoResearchRunRead:
        return save_run(
            run.model_copy(
                update={
                    "status": "queued",
                    "error": None,
                }
            )
        )

    def _update_run_for_cancel(self, project_id: str, run_id: str, detail: str) -> None:
        run = load_run(project_id, run_id)
        if run is None:
            return
        save_run(
            run.model_copy(
                update={
                    "status": "canceled",
                    "error": detail,
                }
            )
        )

    def _recover_stale_jobs(self, state: _ExecutionQueueState) -> _ExecutionQueueState:
        worker = state.worker
        if worker.status not in {"starting", "running", "stopping"}:
            return state
        if worker.heartbeat_at is None:
            return state
        if _utcnow() - worker.heartbeat_at <= LEASE_TIMEOUT:
            return state
        now = _utcnow()
        recovered = False
        jobs: list[AutoResearchExecutionJob] = []
        for job in state.jobs:
            if job.status not in {"leased", "running"}:
                jobs.append(job)
                continue
            recovered = True
            if job.cancellation_requested_at is not None:
                jobs.append(
                    job.model_copy(
                        update={
                            "status": "canceled",
                            "detail": "lease_recovered_after_cancel",
                            "finished_at": now,
                            "error": job.error or "Recovered canceled job after stale worker lease.",
                            "worker_id": WORKER_ID,
                        }
                    )
                )
                continue
            jobs.append(
                job.model_copy(
                    update={
                        "status": "queued",
                        "detail": "lease_recovered",
                        "started_at": None,
                        "worker_id": None,
                    }
                )
            )
        if not recovered:
            return state
        return state.model_copy(
            update={
                "jobs": jobs,
                "worker": worker.model_copy(
                    update={
                        "worker_id": WORKER_ID,
                        "status": "idle",
                        "current_job_id": None,
                        "current_run_id": None,
                        "heartbeat_at": now,
                        "last_error": "Recovered stale auto-research worker lease.",
                    }
                ),
            }
        )

    def _sync_worker(self, *, status: str, job_id: str | None, run_id: str | None, error: str | None = None) -> None:
        with _STATE_LOCK:
            state = _load_state()
            processed_jobs = state.worker.processed_jobs
            if status in {"idle"} and state.worker.current_job_id:
                processed_jobs += 1
            state = state.model_copy(
                update={
                    "worker": state.worker.model_copy(
                        update={
                            "worker_id": WORKER_ID,
                            "status": status,
                            "current_job_id": job_id,
                            "current_run_id": run_id,
                            "heartbeat_at": _utcnow(),
                            "processed_jobs": processed_jobs,
                            "last_error": error,
                        }
                    )
                }
            )
            _save_state(state)

    def _update_job(
        self,
        job_id: str,
        *,
        status: str,
        detail: str | None = None,
        error: str | None = None,
        cancellation_requested_at: datetime | None = None,
    ) -> AutoResearchExecutionJob | None:
        with _STATE_LOCK:
            state = _load_state()
            updated_job: AutoResearchExecutionJob | None = None
            now = _utcnow()
            jobs: list[AutoResearchExecutionJob] = []
            for job in state.jobs:
                if job.id != job_id:
                    jobs.append(job)
                    continue
                payload: dict[str, object] = {
                    "status": status,
                    "detail": detail if detail is not None else job.detail,
                    "error": error,
                    "worker_id": WORKER_ID,
                }
                if status in {"leased", "running"}:
                    payload["started_at"] = job.started_at or now
                if status in {"succeeded", "failed", "canceled"}:
                    payload["finished_at"] = now
                if status == "leased":
                    payload["attempt_count"] = job.attempt_count + 1
                if cancellation_requested_at is not None:
                    payload["cancellation_requested_at"] = cancellation_requested_at
                updated_job = job.model_copy(update=payload)
                jobs.append(updated_job)
            if updated_job is None:
                return None
            state = state.model_copy(update={"jobs": jobs})
            _save_state(state)
            return updated_job

    def _lease_next_job(self) -> AutoResearchExecutionJob | None:
        with _STATE_LOCK:
            state = self._recover_stale_jobs(_load_state())
            now = _utcnow()
            jobs: list[AutoResearchExecutionJob] = []
            leased_job: AutoResearchExecutionJob | None = None
            for job in state.jobs:
                if leased_job is None and job.status == "queued":
                    leased_job = job.model_copy(
                        update={
                            "status": "leased",
                            "worker_id": WORKER_ID,
                            "started_at": now,
                            "attempt_count": job.attempt_count + 1,
                        }
                    )
                    jobs.append(leased_job)
                    continue
                jobs.append(job)
            if leased_job is None:
                state = state.model_copy(
                    update={
                        "worker": state.worker.model_copy(
                            update={
                                "worker_id": WORKER_ID,
                                "status": "idle",
                                "current_job_id": None,
                                "current_run_id": None,
                                "heartbeat_at": now,
                            }
                        )
                    }
                )
                _save_state(state)
                return None
            state = state.model_copy(
                update={
                    "jobs": jobs,
                    "worker": state.worker.model_copy(
                        update={
                            "worker_id": WORKER_ID,
                            "status": "starting",
                            "current_job_id": leased_job.id,
                            "current_run_id": leased_job.run_id,
                            "heartbeat_at": now,
                        }
                    ),
                }
            )
            _save_state(state)
            return leased_job

    def _is_cancel_requested(self, job_id: str) -> bool:
        with _STATE_LOCK:
            state = _load_state()
            if state.worker.current_job_id == job_id:
                state = state.model_copy(
                    update={
                        "worker": state.worker.model_copy(
                            update={
                                "worker_id": WORKER_ID,
                                "heartbeat_at": _utcnow(),
                            }
                        )
                    }
                )
                _save_state(state)
            for job in state.jobs:
                if job.id == job_id:
                    return job.cancellation_requested_at is not None
        return False

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
        with _STATE_LOCK:
            state = _load_state()
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
                status="queued",
                detail=f"{action}:{run_id}",
                enqueued_at=_utcnow(),
            )
            state.jobs.append(queued_job)
            _save_state(state)
        self._update_run_for_enqueue(run)
        queued_job = self.get_run_execution(project_id, run_id).jobs[-1]
        return queued_job, True

    def get_run_execution(self, project_id: str, run_id: str) -> AutoResearchRunExecutionRead:
        with _STATE_LOCK:
            state = _load_state()
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
                worker=state.worker,
            )

    def request_cancel(self, *, project_id: str, run_id: str) -> AutoResearchRunExecutionRead:
        canceled_now = False
        running_cancel = False
        now = _utcnow()
        with _STATE_LOCK:
            state = _load_state()
            jobs: list[AutoResearchExecutionJob] = []
            for job in state.jobs:
                if job.project_id != project_id or job.run_id != run_id:
                    jobs.append(job)
                    continue
                if job.status in {"queued", "leased"}:
                    canceled_now = True
                    jobs.append(
                        job.model_copy(
                            update={
                                "status": "canceled",
                                "detail": "cancel_requested",
                                "error": "Run canceled before execution started.",
                                "finished_at": now,
                                "cancellation_requested_at": now,
                                "worker_id": WORKER_ID,
                            }
                        )
                    )
                    continue
                if job.status == "running":
                    running_cancel = True
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
            worker = state.worker
            if running_cancel:
                worker = worker.model_copy(
                    update={
                        "status": "stopping",
                        "heartbeat_at": now,
                    }
                )
            state = state.model_copy(update={"jobs": jobs, "worker": worker})
            _save_state(state)
        if canceled_now and not running_cancel:
            detail = "Run canceled before execution started."
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
            detail=f"job_id={job.id} action={job.action}",
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
                max_rounds=request.max_rounds,
                candidate_execution_limit=request.candidate_execution_limit,
                benchmark_source=request.benchmark,
                execution_backend=request.execution_backend,
                auto_search_literature=request.auto_search_literature,
                auto_fetch_literature=request.auto_fetch_literature,
                docker_image=request.docker_image,
                execution_action=job.action,
                should_cancel=lambda: self._is_cancel_requested(job.id),
            )
        finally:
            db.close()

    def drain(self) -> None:
        if not _DRAIN_LOCK.acquire(blocking=False):
            return
        try:
            while True:
                job = self._lease_next_job()
                if job is None:
                    return
                self._sync_worker(status="running", job_id=job.id, run_id=job.run_id)
                self._update_job(job.id, status="running", detail=f"running:{job.action}")
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
                    )
                    self._sync_worker(status="idle", job_id=None, run_id=None, error=detail)
                    write_task_audit_log(
                        db_module.SessionLocal,
                        correlation_id=job.run_id,
                        task_name="autoresearch.run",
                        project_id=job.project_id,
                        action="canceled",
                        status_code=499,
                        detail=detail,
                    )
                    continue
                except Exception as exc:
                    detail = str(exc)
                    self._update_job(job.id, status="failed", detail="failed", error=detail)
                    self._update_run_for_cancel(job.project_id, job.run_id, detail)
                    self._sync_worker(status="idle", job_id=None, run_id=None, error=detail)
                    write_task_audit_log(
                        db_module.SessionLocal,
                        correlation_id=job.run_id,
                        task_name="autoresearch.run",
                        project_id=job.project_id,
                        action="failed",
                        status_code=500,
                        detail=detail,
                    )
                    continue

                if result.status == "done":
                    self._update_job(job.id, status="succeeded", detail="done", error=None)
                    self._sync_worker(status="idle", job_id=None, run_id=None, error=None)
                    write_task_audit_log(
                        db_module.SessionLocal,
                        correlation_id=job.run_id,
                        task_name="autoresearch.run",
                        project_id=job.project_id,
                        action="done",
                        status_code=200,
                        detail=f"job_id={job.id} action={job.action}",
                    )
                elif result.status == "canceled":
                    detail = result.error or "Auto-research run canceled"
                    self._update_job(
                        job.id,
                        status="canceled",
                        detail="canceled",
                        error=detail,
                        cancellation_requested_at=_utcnow(),
                    )
                    self._sync_worker(status="idle", job_id=None, run_id=None, error=detail)
                    write_task_audit_log(
                        db_module.SessionLocal,
                        correlation_id=job.run_id,
                        task_name="autoresearch.run",
                        project_id=job.project_id,
                        action="canceled",
                        status_code=499,
                        detail=detail,
                    )
                else:
                    detail = result.error or "Auto-research run failed"
                    self._update_job(job.id, status="failed", detail="failed", error=detail)
                    self._sync_worker(status="idle", job_id=None, run_id=None, error=detail)
                    write_task_audit_log(
                        db_module.SessionLocal,
                        correlation_id=job.run_id,
                        task_name="autoresearch.run",
                        project_id=job.project_id,
                        action="failed",
                        status_code=500,
                        detail=detail,
                    )
        finally:
            self._sync_worker(status="idle", job_id=None, run_id=None, error=None)
            _DRAIN_LOCK.release()
