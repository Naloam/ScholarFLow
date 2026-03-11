import os
from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/scholarflow"
    )
    semantic_scholar_api_key: str | None = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    arxiv_api_key: str | None = os.getenv("ARXIV_API_KEY")
    crossref_api_key: str | None = os.getenv("CROSSREF_API_KEY")
    llm_api_key: str | None = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")


settings = Settings()
