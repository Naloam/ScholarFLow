"""Shared prompt resolution for the research harness (Session 6 fix).

Problem (docs/goal_session6.md item 3): every agent used to resolve its prompt
directory from ``Path(settings.data_dir).parent / "prompts" / "research_harness"``
with CWD-relative fallbacks. In environments where ``DATA_DIR`` is a throwaway
temp dir (e.g. the Playwright/E2E backend seeded under ``.tmp/...``), ``data_dir.parent``
is the temp dir — not the repo — so ``prompts/research_harness`` was not found and
``_load_prompt`` raised FileNotFoundError. The CWD-relative fallbacks only worked
when the process happened to be launched from the repo root or ``backend/``.

Fix: prompts are part of the SOURCE TREE (``backend/prompts/...``), so they must
resolve relative to ``BACKEND_ROOT`` — an absolute, CWD-independent constant — and
must NOT depend on where data lives.

This module is the single source of truth; the per-agent ``_resolve_prompts_dir`` /
``_load_prompt`` copies delegate here (DRY).
"""
from __future__ import annotations

from pathlib import Path

from config.settings import BACKEND_ROOT


def resolve_prompts_dir(subdir: str = "research_harness") -> Path:
    """Absolute path to ``backend/prompts/<subdir>``.

    Always anchored to ``BACKEND_ROOT`` (resolved at import time from this file's
    location), so it is correct regardless of CWD or a customized ``DATA_DIR``.
    """
    return BACKEND_ROOT / "prompts" / subdir


def load_prompt(name: str, subdir: str = "research_harness") -> str:
    """Read ``backend/prompts/<subdir>/<name>`` as UTF-8 text.

    Raises FileNotFoundError if the prompt is missing — callers rely on this to
    surface a clear error rather than silently degrading.
    """
    return (resolve_prompts_dir(subdir) / name).read_text(encoding="utf-8")
