from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ProjectMentorAccess(Base):
    __tablename__ = "project_mentor_access"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), index=True)
    mentor_user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    mentor_email: Mapped[str] = mapped_column(String, index=True)
    invited_by_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
