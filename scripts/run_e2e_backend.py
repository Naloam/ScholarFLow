from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SCHOLARFLOW_OFFLINE_LLM", "1")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+pysqlite:///{(PROJECT_ROOT / '.tmp' / 'e2e' / 'backend.sqlite3').resolve()}",
)
os.environ.setdefault("DATA_DIR", str((PROJECT_ROOT / ".tmp" / "e2e" / "data").resolve()))

from config.db import engine  # noqa: E402
from main import app  # noqa: E402
import models  # noqa: F401, E402
from models.base import Base  # noqa: E402


def _sqlite_path(db_url: str) -> Path | None:
    if db_url.startswith("sqlite:///"):
        return Path(db_url.removeprefix("sqlite:///"))
    if db_url.startswith("sqlite+pysqlite:///"):
        return Path(db_url.removeprefix("sqlite+pysqlite:///"))
    return None


def _reset_e2e_state(*, data_dir: Path, db_url: str) -> None:
    if os.getenv("SCHOLARFLOW_E2E_RESET", "1") != "1":
        return
    if data_dir.exists():
        shutil.rmtree(data_dir)
    db_path = _sqlite_path(db_url)
    if db_path is None:
        return
    for candidate in (
        db_path,
        db_path.with_name(f"{db_path.name}-shm"),
        db_path.with_name(f"{db_path.name}-wal"),
    ):
        if candidate.exists():
            candidate.unlink()


def _seed_fixture_workspace(data_dir: Path) -> None:
    """Copy the real completed run (v0_citrag_05) into the E2E data dir.

    The UI flow (Projects → Run → Report) is validated against this genuine
    GLM-5.2 run rather than a synthetic mock — the E2E asserts the honest
    NEGATIVE result is rendered verbatim. A live 10-15 min run is gated behind
    ``@pytest.mark.live_research`` and never runs in CI/E2E.
    """
    source = BACKEND_ROOT / "data" / "research_workspace" / "v0_citrag_05"
    if not source.exists():
        return
    dest = data_dir / "research_workspace" / "v0_citrag_05"
    shutil.copytree(source, dest)


def main() -> None:
    data_dir = Path(os.environ["DATA_DIR"])
    db_url = os.environ["DATABASE_URL"]
    db_path = _sqlite_path(db_url)

    _reset_e2e_state(data_dir=data_dir, db_url=db_url)

    data_dir.mkdir(parents=True, exist_ok=True)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    _seed_fixture_workspace(data_dir)

    Base.metadata.create_all(engine)
    uvicorn.run(
        app,
        host=os.getenv("SCHOLARFLOW_E2E_HOST", "127.0.0.1"),
        port=int(os.getenv("SCHOLARFLOW_E2E_BACKEND_PORT", "8000")),
        log_level=os.getenv("SCHOLARFLOW_E2E_LOG_LEVEL", "warning"),
    )


if __name__ == "__main__":
    main()
