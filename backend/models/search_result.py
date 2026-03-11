from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (
        Index("ix_search_results_project_created", "project_id", "created_at"),
        Index("ix_search_results_project_query_norm", "project_id", "query_normalized"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"))
    query: Mapped[str] = mapped_column(Text)
    query_normalized: Mapped[str] = mapped_column(Text)
    results: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
