from __future__ import annotations

from pathlib import Path


def load_prompt(path: str) -> str:
    target = Path(path)
    if target.is_absolute() and target.exists():
        return target.read_text(encoding="utf-8")

    candidates = [
        target,
        Path(__file__).resolve().parents[3] / target,
        Path(__file__).resolve().parents[2] / target,
    ]
    for cand in candidates:
        if cand.exists():
            return cand.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt not found: {path}")
