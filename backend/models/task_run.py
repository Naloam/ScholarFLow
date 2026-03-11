from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
