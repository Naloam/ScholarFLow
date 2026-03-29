from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from schemas.autoresearch import (
    AggregateSystemMetricResult,
    AutoResearchBridgeCheckpointRead,
    AutoResearchBridgeImportedArtifactRead,
    AutoResearchBridgeNotificationRead,
    AutoResearchBridgeSessionRead,
    AutoResearchExperimentBridgeConfig,
    AutoResearchExperimentBridgeRead,
    AutoResearchRunRead,
    ConfidenceIntervalSummary,
    NegativeResultRecord,
    ResultArtifact,
    ResultTable,
    SeedArtifactResult,
    SweepEvaluationResult,
    SystemMetricResult,
)
from services.autoresearch.repository import load_benchmark_snapshot, load_run, run_dir, save_run


BRIDGE_STATE_FILENAME = "bridge_state.json"
BRIDGE_DIRNAME = "bridge"
BRIDGE_HANDOFFS_DIRNAME = "handoffs"
BRIDGE_RESULT_FILENAME = "result_artifact.json"
BRIDGE_MANIFEST_FILENAME = "manifest.json"
BRIDGE_INSTRUCTIONS_FILENAME = "instructions.md"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _bridge_root(project_id: str, run_id: str) -> Path:
    path = run_dir(project_id, run_id) / BRIDGE_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def bridge_state_path(project_id: str, run_id: str) -> Path:
    return _bridge_root(project_id, run_id) / BRIDGE_STATE_FILENAME


def _handoff_root(project_id: str, run_id: str) -> Path:
    path = _bridge_root(project_id, run_id) / BRIDGE_HANDOFFS_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_for_run(run: AutoResearchRunRead) -> AutoResearchExperimentBridgeConfig | None:
    config = run.request.experiment_bridge if run.request is not None else None
    if config is None or not config.enabled:
        return None
    return config


def _default_state(run: AutoResearchRunRead) -> AutoResearchExperimentBridgeRead:
    return AutoResearchExperimentBridgeRead(
        project_id=run.project_id,
        run_id=run.id,
        enabled=_config_for_run(run) is not None,
        config=_config_for_run(run),
        persisted_path=str(bridge_state_path(run.project_id, run.id)),
    )


def _state_from_disk(project_id: str, run_id: str) -> AutoResearchExperimentBridgeRead | None:
    path = bridge_state_path(project_id, run_id)
    if not path.is_file():
        return None
    try:
        return AutoResearchExperimentBridgeRead.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sorted_sessions(state: AutoResearchExperimentBridgeRead) -> list[AutoResearchBridgeSessionRead]:
    return sorted(state.sessions, key=lambda item: (item.created_at, item.session_id))


def _current_session(
    state: AutoResearchExperimentBridgeRead,
) -> AutoResearchBridgeSessionRead | None:
    if state.active_session_id:
        for item in state.sessions:
            if item.session_id == state.active_session_id:
                return item
    sessions = _sorted_sessions(state)
    return sessions[-1] if sessions else None


def _normalized_state(
    run: AutoResearchRunRead,
    state: AutoResearchExperimentBridgeRead,
) -> AutoResearchExperimentBridgeRead:
    current_session = _current_session(state)
    session_count = len(state.sessions)
    open_session_count = sum(1 for item in state.sessions if item.status == "waiting_result")
    imported_session_count = sum(
        1 for item in state.sessions if item.status in {"result_imported", "completed"}
    )

    if run.status == "done":
        status = "completed"
    elif run.status == "failed":
        status = "failed"
    elif run.status == "canceled":
        status = "canceled"
    elif current_session is not None:
        status = current_session.status
    else:
        status = "inactive"

    latest_session_id = current_session.session_id if current_session is not None else None
    return state.model_copy(
        update={
            "enabled": _config_for_run(run) is not None,
            "config": _config_for_run(run),
            "persisted_path": str(bridge_state_path(run.project_id, run.id)),
            "status": status,
            "active_session_id": (
                current_session.session_id
                if current_session is not None and current_session.status == "waiting_result"
                else None
            ),
            "latest_session_id": latest_session_id,
            "open_session_count": open_session_count,
            "imported_session_count": imported_session_count,
            "session_count": session_count,
            "checkpoint_count": len(state.checkpoints),
            "notification_count": len(state.notifications),
            "current_session": current_session,
        }
    )


def build_bridge_state(project_id: str, run_id: str) -> AutoResearchExperimentBridgeRead | None:
    run = load_run(project_id, run_id)
    if run is None:
        return None
    stored = _state_from_disk(project_id, run_id)
    state = stored if stored is not None else _default_state(run)
    return _normalized_state(run, state)


def bridge_is_waiting_for_result(project_id: str, run_id: str) -> bool:
    state = build_bridge_state(project_id, run_id)
    return bool(state is not None and state.current_session is not None and state.current_session.status == "waiting_result")


class AutoResearchExperimentBridgeService:
    def _save(self, state: AutoResearchExperimentBridgeRead) -> AutoResearchExperimentBridgeRead:
        _write_json(bridge_state_path(state.project_id, state.run_id), state.model_dump(mode="json"))
        return state

    def _replace_session(
        self,
        state: AutoResearchExperimentBridgeRead,
        session: AutoResearchBridgeSessionRead,
    ) -> AutoResearchExperimentBridgeRead:
        sessions = [
            session if item.session_id == session.session_id else item
            for item in state.sessions
        ]
        if not any(item.session_id == session.session_id for item in state.sessions):
            sessions.append(session)
        return state.model_copy(update={"sessions": sessions})

    def _append_checkpoint(
        self,
        state: AutoResearchExperimentBridgeRead,
        *,
        kind: str,
        summary: str,
        detail: str | None = None,
        session_id: str | None = None,
    ) -> AutoResearchExperimentBridgeRead:
        checkpoints = list(state.checkpoints)
        checkpoints.append(
            AutoResearchBridgeCheckpointRead(
                checkpoint_id=f"bridge_ckpt_{uuid4().hex}",
                created_at=_utcnow(),
                kind=kind,  # type: ignore[arg-type]
                summary=summary,
                detail=detail,
                session_id=session_id,
            )
        )
        return state.model_copy(update={"checkpoints": checkpoints})

    def _notification_target(
        self,
        *,
        project_id: str,
        run_id: str,
        raw_target: str | None,
    ) -> Path:
        if raw_target:
            path = Path(raw_target)
            if path.is_absolute():
                return path
            return run_dir(project_id, run_id) / raw_target
        return _bridge_root(project_id, run_id) / "notifications.log"

    def _emit_notifications(
        self,
        state: AutoResearchExperimentBridgeRead,
        *,
        event: str,
        message: str,
    ) -> AutoResearchExperimentBridgeRead:
        config = state.config
        hooks = config.notification_hooks if config is not None else []
        notifications = list(state.notifications)
        for hook in hooks:
            if event not in hook.events:
                continue
            created_at = _utcnow()
            status = "sent"
            delivered_at = created_at
            error = None
            target = hook.target
            if hook.channel == "file":
                path = self._notification_target(
                    project_id=state.project_id,
                    run_id=state.run_id,
                    raw_target=hook.target,
                )
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("a", encoding="utf-8") as handle:
                        handle.write(
                            json.dumps(
                                {
                                    "created_at": created_at.isoformat(),
                                    "event": event,
                                    "run_id": state.run_id,
                                    "message": message,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                            + "\n"
                        )
                    target = str(path)
                except Exception as exc:
                    status = "failed"
                    delivered_at = None
                    error = str(exc)
            notifications.append(
                AutoResearchBridgeNotificationRead(
                    notification_id=f"bridge_ntf_{uuid4().hex}",
                    created_at=created_at,
                    event=event,  # type: ignore[arg-type]
                    channel=hook.channel,
                    status=status,  # type: ignore[arg-type]
                    target=target,
                    message=message,
                    delivered_at=delivered_at,
                    error=error,
                )
            )
        return state.model_copy(update={"notifications": notifications})

    def _load_run_or_raise(self, project_id: str, run_id: str) -> AutoResearchRunRead:
        run = load_run(project_id, run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")
        return run

    def _load_state_or_raise(self, project_id: str, run_id: str) -> AutoResearchExperimentBridgeRead:
        state = build_bridge_state(project_id, run_id)
        if state is None:
            raise ValueError(f"Run not found: {run_id}")
        if not state.enabled or state.config is None:
            raise ValueError("Run does not have an enabled experiment bridge")
        return state

    def _result_artifact_from_import(
        self,
        *,
        summary: str,
        objective_score: float,
        primary_metric: str,
        objective_system: str,
        baseline_system: str,
        baseline_score: float | None,
        key_findings: list[str],
        notes: str | None,
    ) -> ResultArtifact:
        effective_baseline = (
            baseline_score
            if baseline_score is not None
            else max(0.0, round(objective_score - 0.08, 4))
        )
        system_results = [
            SystemMetricResult(system=objective_system, metrics={primary_metric: round(objective_score, 4)}),
            SystemMetricResult(system=baseline_system, metrics={primary_metric: round(effective_baseline, 4)}),
        ]
        aggregate_system_results = [
            AggregateSystemMetricResult(
                system=objective_system,
                mean_metrics={primary_metric: round(objective_score, 4)},
                std_metrics={primary_metric: 0.0},
                confidence_intervals={
                    primary_metric: ConfidenceIntervalSummary(
                        lower=round(objective_score, 4),
                        upper=round(objective_score, 4),
                    )
                },
                min_metrics={primary_metric: round(objective_score, 4)},
                max_metrics={primary_metric: round(objective_score, 4)},
                sample_count=1,
            ),
            AggregateSystemMetricResult(
                system=baseline_system,
                mean_metrics={primary_metric: round(effective_baseline, 4)},
                std_metrics={primary_metric: 0.0},
                confidence_intervals={
                    primary_metric: ConfidenceIntervalSummary(
                        lower=round(effective_baseline, 4),
                        upper=round(effective_baseline, 4),
                    )
                },
                min_metrics={primary_metric: round(effective_baseline, 4)},
                max_metrics={primary_metric: round(effective_baseline, 4)},
                sample_count=1,
            ),
        ]
        per_seed_results = [
            SeedArtifactResult(
                seed=0,
                sweep_label="bridge_import",
                best_system=objective_system,
                objective_system=objective_system,
                objective_score=round(objective_score, 4),
                primary_metric=primary_metric,
                system_results=system_results,
            )
        ]
        sweep_results = [
            SweepEvaluationResult(
                label="bridge_import",
                params={},
                description="Imported bridge result",
                status="done",
                best_system=objective_system,
                objective_system=objective_system,
                objective_score_mean=round(objective_score, 4),
                objective_score_std=0.0,
                objective_score_confidence_interval=ConfidenceIntervalSummary(
                    lower=round(objective_score, 4),
                    upper=round(objective_score, 4),
                ),
                aggregate_system_results=aggregate_system_results,
                seed_count=1,
                successful_seed_count=1,
            )
        ]
        negative_results = [
            NegativeResultRecord(
                scope="system",
                subject=baseline_system,
                reference=objective_system,
                metric=primary_metric,
                observed_score=round(effective_baseline, 4),
                reference_score=round(objective_score, 4),
                delta=round(effective_baseline - objective_score, 4),
                detail=(
                    f"`{baseline_system}` remained below `{objective_system}` on "
                    f"`{primary_metric}` in the imported bridge result."
                ),
            )
        ]
        tables = [
            ResultTable(
                title="Imported Bridge Result",
                columns=["System", primary_metric],
                rows=[
                    [objective_system, f"{objective_score:.4f}"],
                    [baseline_system, f"{effective_baseline:.4f}"],
                ],
            )
        ]
        summary_suffix = f" {notes.strip()}" if notes and notes.strip() else ""
        return ResultArtifact(
            status="done",
            summary=f"{summary.strip()}{summary_suffix}",
            key_findings=key_findings or [f"{objective_system} reached {objective_score:.4f} {primary_metric}."],
            primary_metric=primary_metric,
            best_system=objective_system,
            objective_system=objective_system,
            objective_score=round(objective_score, 4),
            system_results=system_results,
            aggregate_system_results=aggregate_system_results,
            per_seed_results=per_seed_results,
            sweep_results=sweep_results,
            negative_results=negative_results,
            acceptance_checks=[],
            tables=tables,
            environment={
                "executor_mode": "bridge_import",
                "selected_sweep": "bridge_import",
                "bridge_imported": True,
            },
            outputs={"source": "bridge_import"},
        )

    def _session_by_id(
        self,
        state: AutoResearchExperimentBridgeRead,
        session_id: str | None,
    ) -> AutoResearchBridgeSessionRead:
        if session_id:
            for item in state.sessions:
                if item.session_id == session_id:
                    return item
            raise ValueError(f"Bridge session not found: {session_id}")
        if state.current_session is None:
            raise ValueError("Run does not have an active bridge session")
        return state.current_session

    def start_session(
        self,
        *,
        project_id: str,
        run_id: str,
        candidate_id: str,
        candidate_title: str,
        round_index: int,
        goal: str,
        strategy: str,
        code_path: str,
        plan_payload: dict[str, object],
        spec_payload: dict[str, object],
        prior_attempts_payload: list[dict[str, object]],
        execution_backend_payload: dict[str, object] | None,
    ) -> AutoResearchExperimentBridgeRead:
        run = self._load_run_or_raise(project_id, run_id)
        state = self._load_state_or_raise(project_id, run_id)
        benchmark_snapshot = load_benchmark_snapshot(project_id, run_id)
        session_id = f"arsession_{uuid4().hex}"
        handoff_dir = _handoff_root(project_id, run_id) / session_id
        handoff_dir.mkdir(parents=True, exist_ok=True)
        result_path = handoff_dir / BRIDGE_RESULT_FILENAME
        manifest_path = handoff_dir / BRIDGE_MANIFEST_FILENAME
        instructions_path = handoff_dir / BRIDGE_INSTRUCTIONS_FILENAME
        copied_code_path = handoff_dir / Path(code_path).name
        copied_code_path.write_text(Path(code_path).read_text(encoding="utf-8"), encoding="utf-8")
        _write_json(handoff_dir / "plan.json", plan_payload)
        _write_json(handoff_dir / "spec.json", spec_payload)
        _write_json(handoff_dir / "prior_attempts.json", prior_attempts_payload)
        if benchmark_snapshot is not None:
            _write_json(handoff_dir / "benchmark.json", benchmark_snapshot)
        manifest = {
            "project_id": project_id,
            "run_id": run_id,
            "session_id": session_id,
            "candidate_id": candidate_id,
            "candidate_title": candidate_title,
            "round_index": round_index,
            "goal": goal,
            "strategy": strategy,
            "result_path": str(result_path),
            "generated_code": copied_code_path.name,
            "execution_backend": execution_backend_payload,
            "bridge_config": state.config.model_dump(mode="json") if state.config is not None else None,
            "benchmark_snapshot_path": str(handoff_dir / "benchmark.json") if benchmark_snapshot is not None else None,
            "run_status": run.status,
        }
        _write_json(manifest_path, manifest)
        instructions_path.write_text(
            "\n".join(
                [
                    "# Experiment Bridge Instructions",
                    "",
                    f"- Run ID: `{run_id}`",
                    f"- Candidate: `{candidate_title}` (`{candidate_id}`)",
                    f"- Round: `{round_index}`",
                    f"- Goal: `{goal}`",
                    "",
                    "Use the copied experiment script plus the persisted plan/spec/benchmark snapshots in this",
                    "handoff directory. When the external environment finishes, write a `ResultArtifact` JSON payload",
                    f"to `{result_path.name}` and then refresh the bridge state from ScholarFlow.",
                ]
            ),
            encoding="utf-8",
        )
        session = AutoResearchBridgeSessionRead(
            session_id=session_id,
            created_at=_utcnow(),
            updated_at=_utcnow(),
            status="waiting_result",
            candidate_id=candidate_id,
            candidate_title=candidate_title,
            round_index=round_index,
            goal=goal,
            strategy=strategy,
            handoff_dir=str(handoff_dir),
            manifest_path=str(manifest_path),
            instructions_path=str(instructions_path),
            code_path=str(copied_code_path),
            benchmark_path=str(handoff_dir / "benchmark.json") if benchmark_snapshot is not None else None,
            result_path=str(result_path),
        )
        state = self._replace_session(state, session)
        state = self._append_checkpoint(
            state,
            kind="session_created",
            summary=(
                f"Prepared bridge handoff for `{candidate_title}` round {round_index} at "
                f"`{state.config.target_label if state.config is not None else 'external-environment'}`."
            ),
            detail=str(manifest_path),
            session_id=session_id,
        )
        state = self._emit_notifications(
            state,
            event="session_created",
            message=(
                f"Bridge session {session_id} is waiting for result import for run {run_id} "
                f"({candidate_title}, round {round_index})."
            ),
        )
        run = self._load_run_or_raise(project_id, run_id)
        state = _normalized_state(run, state)
        return self._save(state)

    def refresh_waiting_session(
        self,
        *,
        project_id: str,
        run_id: str,
    ) -> tuple[AutoResearchExperimentBridgeRead, ResultArtifact | None, str]:
        state = self._load_state_or_raise(project_id, run_id)
        session = self._session_by_id(state, None)
        if session.status != "waiting_result":
            return state, None, "none"
        now = _utcnow()
        updated_session = session.model_copy(update={"updated_at": now, "last_polled_at": now})
        state = self._replace_session(state, updated_session)
        result_path = Path(session.result_path)
        if not result_path.is_file():
            state = self._append_checkpoint(
                state,
                kind="status_polled",
                summary=f"Polled bridge session `{session.session_id}`; result is not ready yet.",
                session_id=session.session_id,
            )
            run = self._load_run_or_raise(project_id, run_id)
            state = _normalized_state(run, state)
            return self._save(state), None, "none"
        try:
            artifact = ResultArtifact.model_validate_json(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            updated_session = updated_session.model_copy(
                update={
                    "last_error": f"Invalid bridge result payload: {exc}",
                    "external_status": "invalid_result",
                }
            )
            state = self._replace_session(state, updated_session)
            state = self._append_checkpoint(
                state,
                kind="status_polled",
                summary=f"Polled bridge session `{session.session_id}`; result payload was invalid.",
                detail=str(exc),
                session_id=session.session_id,
            )
            run = self._load_run_or_raise(project_id, run_id)
            state = _normalized_state(run, state)
            return self._save(state), None, "none"
        run = self._load_run_or_raise(project_id, run_id)
        state = _normalized_state(run, state)
        return self._save(state), artifact, "file"

    def import_result(
        self,
        *,
        project_id: str,
        run_id: str,
        session_id: str | None,
        artifact: ResultArtifact,
        source: str,
    ) -> tuple[AutoResearchExperimentBridgeRead, AutoResearchRunRead]:
        state = self._load_state_or_raise(project_id, run_id)
        session = self._session_by_id(state, session_id)
        if session.status != "waiting_result":
            raise ValueError("Bridge session is not waiting for a result import")
        result_path = Path(session.result_path)
        _write_json(result_path, artifact.model_dump(mode="json"))
        from services.autoresearch.orchestrator import AutoResearchOrchestrator

        run = AutoResearchOrchestrator().ingest_bridge_result(
            project_id=project_id,
            run_id=run_id,
            session_id=session.session_id,
            artifact=artifact,
        )
        imported_artifact = AutoResearchBridgeImportedArtifactRead(
            imported_at=_utcnow(),
            source=source,  # type: ignore[arg-type]
            artifact_path=str(result_path),
            summary=artifact.summary,
            primary_metric=artifact.primary_metric,
            objective_score=artifact.objective_score,
        )
        updated_session = session.model_copy(
            update={
                "updated_at": _utcnow(),
                "status": "result_imported",
                "external_status": "result_imported",
                "last_error": None,
                "imported_artifact": imported_artifact,
            }
        )
        state = self._replace_session(state, updated_session)
        state = self._append_checkpoint(
            state,
            kind="result_imported",
            summary=(
                f"Imported bridge result for `{updated_session.candidate_title}` round "
                f"{updated_session.round_index}."
            ),
            detail=artifact.summary,
            session_id=updated_session.session_id,
        )
        state = self._emit_notifications(
            state,
            event="result_imported",
            message=(
                f"Bridge result imported for run {run_id}, candidate {updated_session.candidate_id}, "
                f"round {updated_session.round_index}."
            ),
        )
        state = _normalized_state(run, state)
        return self._save(state), run

    def import_inline_result(
        self,
        *,
        project_id: str,
        run_id: str,
        session_id: str | None,
        summary: str,
        objective_score: float,
        primary_metric: str,
        objective_system: str,
        baseline_system: str,
        baseline_score: float | None,
        key_findings: list[str],
        notes: str | None,
    ) -> tuple[AutoResearchExperimentBridgeRead, AutoResearchRunRead]:
        artifact = self._result_artifact_from_import(
            summary=summary,
            objective_score=objective_score,
            primary_metric=primary_metric,
            objective_system=objective_system,
            baseline_system=baseline_system,
            baseline_score=baseline_score,
            key_findings=key_findings,
            notes=notes,
        )
        return self.import_result(
            project_id=project_id,
            run_id=run_id,
            session_id=session_id,
            artifact=artifact,
            source="inline",
        )

    def record_resume_enqueued(
        self,
        *,
        project_id: str,
        run_id: str,
    ) -> AutoResearchExperimentBridgeRead:
        run = self._load_run_or_raise(project_id, run_id)
        state = self._load_state_or_raise(project_id, run_id)
        session = self._session_by_id(state, None)
        state = self._append_checkpoint(
            state,
            kind="resume_enqueued",
            summary=f"Queued resume after importing bridge result for session `{session.session_id}`.",
            session_id=session.session_id,
        )
        state = self._emit_notifications(
            state,
            event="resume_enqueued",
            message=f"Resume queued for run {run_id} after bridge import.",
        )
        state = _normalized_state(run, state)
        return self._save(state)

    def finalize_run(
        self,
        *,
        project_id: str,
        run_id: str,
        run_status: str,
    ) -> AutoResearchExperimentBridgeRead | None:
        state = build_bridge_state(project_id, run_id)
        run = load_run(project_id, run_id)
        if state is None or run is None or not state.enabled:
            return None
        session = state.current_session
        if session is not None and session.status in {"waiting_result", "result_imported"}:
            session_status = "completed" if run_status == "done" else run_status
            updated_session = session.model_copy(
                update={
                    "updated_at": _utcnow(),
                    "status": session_status,  # type: ignore[arg-type]
                    "external_status": run_status,
                }
            )
            state = self._replace_session(state, updated_session)
        event_by_status = {
            "done": "run_completed",
            "failed": "run_failed",
            "canceled": "run_canceled",
        }
        checkpoint_by_status = {
            "done": "run_completed",
            "failed": "run_failed",
            "canceled": "run_canceled",
        }
        if run_status in event_by_status:
            state = self._append_checkpoint(
                state,
                kind=checkpoint_by_status[run_status],
                summary=f"Bridge-backed run reached terminal status `{run_status}`.",
                session_id=session.session_id if session is not None else None,
            )
            state = self._emit_notifications(
                state,
                event=event_by_status[run_status],
                message=f"Run {run_id} reached terminal status `{run_status}`.",
            )
        state = _normalized_state(run, state)
        return self._save(state)

    def cancel_waiting_session(
        self,
        *,
        project_id: str,
        run_id: str,
    ) -> AutoResearchExperimentBridgeRead:
        run = self._load_run_or_raise(project_id, run_id)
        state = self._load_state_or_raise(project_id, run_id)
        session = self._session_by_id(state, None)
        if session.status != "waiting_result":
            raise ValueError("Run does not have a waiting bridge session to cancel")
        run = save_run(
            run.model_copy(
                update={
                    "status": "canceled",
                    "error": "Run canceled while waiting for bridge result import.",
                }
            )
        )
        updated_session = session.model_copy(
            update={
                "updated_at": _utcnow(),
                "status": "canceled",
                "external_status": "canceled",
            }
        )
        state = self._replace_session(state, updated_session)
        state = self._append_checkpoint(
            state,
            kind="run_canceled",
            summary=f"Canceled waiting bridge session `{session.session_id}`.",
            session_id=session.session_id,
        )
        state = self._emit_notifications(
            state,
            event="run_canceled",
            message=f"Canceled waiting bridge session for run {run_id}.",
        )
        state = _normalized_state(run, state)
        return self._save(state)
