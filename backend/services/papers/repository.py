from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.paper import Paper
from models.project_paper import ProjectPaper
from schemas.papers import PaperCreate, PaperMeta, PaperSummary
from services.papers.metadata import fetch_metadata, normalize_doi


def _find_existing_paper(db: Session, payload: PaperCreate) -> Paper | None:
    if payload.doi:
        doi_norm = normalize_doi(payload.doi)
        stmt = select(Paper).where(func.lower(Paper.doi) == doi_norm)
        row = db.execute(stmt).scalar_one_or_none()
        if row is not None:
            return row
    if payload.url:
        stmt = select(Paper).where(Paper.url == payload.url)
        row = db.execute(stmt).scalar_one_or_none()
        if row is not None:
            return row
    if payload.pdf_url:
        stmt = select(Paper).where(Paper.pdf_url == payload.pdf_url)
        row = db.execute(stmt).scalar_one_or_none()
        if row is not None:
            return row
    return None


def _ensure_project_link(db: Session, project_id: str, paper_id: str) -> None:
    stmt = select(ProjectPaper).where(
        ProjectPaper.project_id == project_id, ProjectPaper.paper_id == paper_id
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is None:
        db.add(ProjectPaper(project_id=project_id, paper_id=paper_id))


def _apply_metadata(paper: Paper, meta: dict) -> None:
    if not paper.title and meta.get("title"):
        paper.title = meta.get("title")
    if (not paper.authors) and meta.get("authors") is not None:
        paper.authors = meta.get("authors")
    if paper.year is None and meta.get("year") is not None:
        paper.year = meta.get("year")
    if not paper.abstract and meta.get("abstract"):
        paper.abstract = meta.get("abstract")
    if not paper.url and meta.get("url"):
        paper.url = meta.get("url")
    if not paper.pdf_url and meta.get("pdf_url"):
        paper.pdf_url = meta.get("pdf_url")
    if not paper.source and meta.get("source"):
        paper.source = meta.get("source")


def add_paper(db: Session, project_id: str, payload: PaperCreate) -> str:
    paper = _find_existing_paper(db, payload)
    if paper is None:
        paper = Paper(
            id=str(uuid4()),
            doi=normalize_doi(payload.doi) if payload.doi else None,
            pdf_url=payload.pdf_url,
            url=payload.url,
            title=None,
        )
        db.add(paper)
        db.flush()

    _ensure_project_link(db, project_id, paper.id)

    meta = fetch_metadata(payload.doi, payload.url)
    if meta:\n        _apply_metadata(paper, meta)
        db.add(paper)

    db.commit()
    return paper.id


def list_papers(db: Session, project_id: str) -> list[PaperMeta]:
    stmt = (
        select(Paper)
        .join(ProjectPaper, ProjectPaper.paper_id == Paper.id)
        .where(ProjectPaper.project_id == project_id)
    )
    rows = db.execute(stmt).scalars().all()
    return [
        PaperMeta(
            id=row.id,
            doi=row.doi,
            title=row.title,
            authors=row.authors or [],
            year=row.year,
            abstract=row.abstract,
            pdf_url=row.pdf_url,
            url=row.url,
            bibtex=row.bibtex,
            source=row.source,
        )
        for row in rows
    ]


def get_paper_summary(db: Session, project_id: str, paper_id: str) -> PaperSummary | None:
    stmt = (
        select(Paper)
        .join(ProjectPaper, ProjectPaper.paper_id == Paper.id)
        .where(ProjectPaper.project_id == project_id, Paper.id == paper_id)
    )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        return None
    return PaperSummary(id=row.id, title=row.title or "", abstract=row.abstract, summary=None)


def update_paper_paths(db: Session, paper_id: str, pdf_url: str | None, xml_path: str | None) -> None:
    row = db.get(Paper, paper_id)
    if row is None:
        return
    if pdf_url and not row.pdf_url:
        row.pdf_url = pdf_url
    if xml_path:
        row.parsed_content_id = xml_path
    db.add(row)
    db.commit()
