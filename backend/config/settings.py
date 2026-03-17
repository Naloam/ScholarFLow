import os
from pathlib import Path

from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def _load_env_files() -> None:
    for path in (PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"):
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _split_csv(raw: str | None, defaults: list[str]) -> list[str]:
    if not raw:
        return defaults
    items = [item.strip() for item in raw.split(",")]
    return [item for item in items if item]


def _get_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


_load_env_files()


class Settings(BaseModel):
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://scholarflow:scholarflow@localhost:5432/scholarflow"
    )
    api_token: str | None = os.getenv("API_TOKEN")
    auth_secret: str | None = os.getenv("AUTH_SECRET")
    auth_required: bool = Field(
        default_factory=lambda: _get_bool(os.getenv("AUTH_REQUIRED"), False)
    )
    auth_token_ttl_seconds: int = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", str(7 * 24 * 60 * 60)))
    semantic_scholar_api_key: str | None = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    arxiv_api_key: str | None = os.getenv("ARXIV_API_KEY")
    crossref_api_key: str | None = os.getenv("CROSSREF_API_KEY")
    llm_api_key: str | None = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    grobid_url: str = os.getenv("GROBID_URL", "http://localhost:8070")
    rate_limit_requests_per_minute: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "0"))
    audit_enabled: bool = Field(
        default_factory=lambda: _get_bool(os.getenv("AUDIT_ENABLED"), True)
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: _split_csv(
            os.getenv("CORS_ORIGINS"),
            [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
        )
    )
    data_dir: Path = Field(
        default_factory=lambda: Path(
            os.getenv("DATA_DIR", str(BACKEND_ROOT / "data"))
        ).expanduser().resolve()
    )


settings = Settings()
