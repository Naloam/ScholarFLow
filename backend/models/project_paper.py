from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ProjectPaper(Base):
    __tablename__ = "project_papers"

    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), primary_key=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey("papers.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
