"""Session 6: the prompt-path CWD bug (docs/goal_session6.md item 3).

Prompt resolution must be CWD-independent: agents load prompts from
``backend/prompts/research_harness`` regardless of (a) the process CWD and
(b) a customized ``DATA_DIR`` (the E2E backend seeds a throwaway temp DATA_DIR,
which previously made ``data_dir.parent/prompts/...`` point at the temp dir).
"""
from __future__ import annotations

import os
from pathlib import Path

from services.research_harness import prompts as prompts_mod


def test_resolve_prompts_dir_is_absolute_and_under_backend_root() -> None:
    resolved = prompts_mod.resolve_prompts_dir()
    assert resolved.is_absolute()
    # Anchored to the source tree, not to a data dir or CWD.
    assert resolved == prompts_mod.BACKEND_ROOT / "prompts" / "research_harness"


def test_resolve_prompts_dir_is_cwd_independent(tmp_path, monkeypatch) -> None:
    """Changing CWD to a throwaway dir must NOT move the prompts directory."""
    monkeypatch.chdir(tmp_path)
    resolved = prompts_mod.resolve_prompts_dir()
    assert resolved == prompts_mod.BACKEND_ROOT / "prompts" / "research_harness"
    assert resolved.is_dir(), "resolved prompts dir must actually exist"


def test_resolve_prompts_dir_ignores_custom_data_dir(monkeypatch, tmp_path) -> None:
    """A temp DATA_DIR (as the E2E backend uses) must not redirect prompt resolution."""
    # The real settings.data_dir is read lazily by agents; the helper itself only uses
    # BACKEND_ROOT, so even a temp data dir cannot misdirect it.
    bogus_data = tmp_path / "throwaway-data"
    bogus_data.mkdir()
    monkeypatch.setenv("DATA_DIR", str(bogus_data))
    resolved = prompts_mod.resolve_prompts_dir()
    assert "throwaway-data" not in str(resolved)
    assert resolved == prompts_mod.BACKEND_ROOT / "prompts" / "research_harness"


def test_load_prompt_reads_existing_prompt() -> None:
    # reviewer_v1.md is a committed prompt — load_prompt must return its text.
    text = prompts_mod.load_prompt("reviewer_v1.md")
    assert isinstance(text, str) and text.strip()


def test_load_prompt_raises_on_missing(tmp_path, monkeypatch) -> None:
    # From an unrelated CWD, a missing prompt must still raise (not silently fall back).
    monkeypatch.chdir(tmp_path)
    try:
        prompts_mod.load_prompt("definitely-not-a-prompt-xyz.md")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError for a missing prompt")
