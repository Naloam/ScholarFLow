"""autoresearch_compat — thin backward-compat layer (Session 13, plan §7 P2).

The research_harness core is the new brain, but CLAUDE.md names ``run.json`` /
``artifact.json`` shape compatibility as a non-negotiable baseline. This package
projects the NEW workspace (``project.json`` + ``artifacts/metrics.json`` +
``ledger/*`` + ``ideas/candidates.json``) into the OLD ``AutoResearchRunRead`` /
``ResultArtifact`` / ``HypothesisCandidate`` / ``PortfolioSummary`` shapes so any
legacy consumer of those JSON files keeps working after the orchestrator is
downgraded to a compat reader.

This is read-only projection — it never mutates the new workspace and never
re-introduces the old keyword→template thinking. See ``projection.py``.
"""

from services.research_harness.autoresearch_compat.projection import (
    legacy_artifact,
    legacy_candidates,
    legacy_portfolio,
    legacy_run,
)

__all__ = [
    "legacy_artifact",
    "legacy_candidates",
    "legacy_portfolio",
    "legacy_run",
]
