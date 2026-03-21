from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatusInfo:
    phase: str
    progress: float


STATUS_ORDER = [
    "init",
    "search",
    "fetch",
    "read",
    "evidence",
    "write",
    "edit",
    "review",
    "export",
    "done",
]

PHASE_BY_STATUS = {
    "init": "Phase 2",
    "search": "Phase 2",
    "fetch": "Phase 2",
    "read": "Phase 2",
    "evidence": "Phase 2",
    "write": "Phase 3",
    "edit": "Phase 3",
    "review": "Phase 5",
    "export": "Phase 5",
    "done": "Phase 6",
}


def normalize_status(status: str | None) -> str:
    if not status:
        return "init"
    return status.strip().lower()


def validate_status(status: str | None) -> str:
    normalized = normalize_status(status)
    if normalized not in STATUS_ORDER:
        raise ValueError(f"Invalid status: {status}")
    return normalized


def get_status_info(status: str | None) -> StatusInfo:
    normalized = normalize_status(status)
    if normalized not in STATUS_ORDER:
        normalized = "init"
    idx = STATUS_ORDER.index(normalized)
    progress = idx / (len(STATUS_ORDER) - 1)
    phase = PHASE_BY_STATUS.get(normalized, "Phase 2")
    return StatusInfo(phase=phase, progress=progress)
