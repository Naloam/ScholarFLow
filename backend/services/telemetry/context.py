from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryContext:
    project_id: str | None = None
    user_id: str | None = None
    operation: str | None = None


_telemetry_context: ContextVar[TelemetryContext] = ContextVar(
    "scholarflow_telemetry_context",
    default=TelemetryContext(),
)


@contextmanager
def telemetry_context(
    *,
    project_id: str | None = None,
    user_id: str | None = None,
    operation: str | None = None,
):
    current = _telemetry_context.get()
    token = _telemetry_context.set(
        TelemetryContext(
            project_id=project_id if project_id is not None else current.project_id,
            user_id=user_id if user_id is not None else current.user_id,
            operation=operation if operation is not None else current.operation,
        )
    )
    try:
        yield _telemetry_context.get()
    finally:
        _telemetry_context.reset(token)


def get_telemetry_context() -> TelemetryContext:
    return _telemetry_context.get()
