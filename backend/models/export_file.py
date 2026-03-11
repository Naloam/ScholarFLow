from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ExportFile(Base):
    __tablename__ = "export_files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"))
    format: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
