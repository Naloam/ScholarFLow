from __future__ import annotations

import os
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


def main() -> None:
    data_dir = Path(os.environ["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    db_url = os.environ["DATABASE_URL"]
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    elif db_url.startswith("sqlite+pysqlite:///"):
        db_path = Path(db_url.removeprefix("sqlite+pysqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(engine)
    uvicorn.run(
        app,
        host=os.getenv("SCHOLARFLOW_E2E_HOST", "127.0.0.1"),
        port=int(os.getenv("SCHOLARFLOW_E2E_BACKEND_PORT", "8000")),
        log_level=os.getenv("SCHOLARFLOW_E2E_LOG_LEVEL", "warning"),
    )


if __name__ == "__main__":
    main()
