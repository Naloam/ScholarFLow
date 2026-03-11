from __future__ import annotations

from pathlib import Path


def project_root(project_id: str) -> Path:
    base = Path("data/projects") / project_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def papers_dir(project_id: str) -> Path:
    path = project_root(project_id) / "papers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def parsed_dir(project_id: str) -> Path:
    path = project_root(project_id) / "parsed"
    path.mkdir(parents=True, exist_ok=True)
    return path
