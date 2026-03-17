from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class MentorFeedback(Base):
    __tablename__ = "mentor_feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), index=True)
    mentor_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    draft_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    strengths: Mapped[str] = mapped_column(Text)
    concerns: Mapped[str] = mapped_column(Text)
    next_steps: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
