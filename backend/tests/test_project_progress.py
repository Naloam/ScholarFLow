from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import models  # noqa: F401
from models.base import Base
from models.project import Project
from schemas.review import ReviewScore
from services.export.repository import create_export, set_export_status
from services.projects.progress import build_progress_snapshot
from services.review.repository import create_review_placeholder, update_review


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return factory()


def test_progress_snapshot_changes_when_review_is_filled() -> None:
    db = make_session()
    try:
        db.add(Project(id="project-1", title="Demo", status="init"))
        db.commit()

        review_id = create_review_placeholder(db, "project-1", 1)
        pending_snapshot = build_progress_snapshot(db, "project-1")

        assert pending_snapshot is not None
        assert pending_snapshot["latest_review_status"] == "pending"

        update_review(
            db,
            review_id,
            ReviewScore(
                originality=4,
                importance=4,
                evidence_support=4,
                soundness=4,
                clarity=4,
                value=4,
                contextualization=4,
            ),
            ["Add stronger evidence."],
        )
        ready_snapshot = build_progress_snapshot(db, "project-1")

        assert ready_snapshot is not None
        assert ready_snapshot["latest_review_status"] == "ready"
        assert ready_snapshot["signature"] != pending_snapshot["signature"]
    finally:
        db.close()


def test_progress_snapshot_changes_when_export_status_changes() -> None:
    db = make_session()
    try:
        db.add(Project(id="project-1", title="Demo", status="export"))
        db.commit()

        export_id = create_export(db, "project-1", "markdown")
        running_snapshot = build_progress_snapshot(db, "project-1")

        assert running_snapshot is not None
        assert running_snapshot["latest_export_status"] == "running"

        set_export_status(db, export_id, "done", "/tmp/project-1.md")
        done_snapshot = build_progress_snapshot(db, "project-1")

        assert done_snapshot is not None
        assert done_snapshot["latest_export_status"] == "done"
        assert done_snapshot["signature"] != running_snapshot["signature"]
    finally:
        db.close()
