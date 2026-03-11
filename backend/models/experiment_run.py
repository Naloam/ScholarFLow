from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"))
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    outputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    docker_image: Mapped[str | None] = mapped_column(String, nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
