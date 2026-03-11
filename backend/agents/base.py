from typing import Any


class BaseAgent:
    """Base class placeholder. Implement in Phase 2."""

    name: str = "base"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
