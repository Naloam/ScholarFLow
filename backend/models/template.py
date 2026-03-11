from datetime import datetime

from sqlalchemy import DateTime, Text, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
