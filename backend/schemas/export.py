from datetime import datetime
from pydantic import BaseModel


class ExportRequest(BaseModel):
    format: str


class ExportResult(BaseModel):
    file_id: str
    status: str
    created_at: datetime | None = None
