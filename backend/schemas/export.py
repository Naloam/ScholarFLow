from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class ExportRequest(BaseModel):
    format: Literal["markdown", "latex", "word", "docx"]

    @field_validator("format", mode="before")
    @classmethod
    def _normalize_format(cls, value: str) -> str:
        if isinstance(value, str):
            return value.lower()
        return value


class ExportResult(BaseModel):
    file_id: str
    format: str
    status: str
    file_name: str | None = None
    download_ready: bool = False
    created_at: datetime | None = None
