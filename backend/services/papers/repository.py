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
    if paper.source_weight is None and meta.get("source_weight") is not None:
        paper.source_weight = meta.get("source_weight")
    if paper.score is None and meta.get("score") is not None:
        paper.score = meta.get("score")


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
    if meta:
        _apply_metadata(paper, meta)
        db.add(paper)

    db.commit()
    return paper.id


def _find_by_title(db: Session, title: str) -> Paper | None:
    if not title:
        return None
    norm = title.strip().lower()
    if not norm:
        return None
    stmt = select(Paper).where(func.lower(Paper.title) == norm)
    return db.execute(stmt).scalar_one_or_none()


def upsert_papers_from_search(
    db: Session, project_id: str, items: list[PaperMeta]
) -> list[str]:
    paper_ids: list[str] = []
    for item in items:
        existing: Paper | None = None
        if item.doi:
            doi_norm = normalize_doi(item.doi)
            existing = db.execute(
                select(Paper).where(func.lower(Paper.doi) == doi_norm)
            ).scalar_one_or_none()
        if existing is None and item.url:
            existing = db.execute(select(Paper).where(Paper.url == item.url)).scalar_one_or_none()
        if existing is None and item.title:
            existing = _find_by_title(db, item.title)

        if existing is None:
            existing = Paper(
                id=str(uuid4()),
                doi=normalize_doi(item.doi) if item.doi else None,
                title=item.title,
                authors=item.authors or [],
                year=item.year,
                abstract=item.abstract,
                pdf_url=item.pdf_url,
                url=item.url,
                source=item.source,
                source_weight=item.source_weight,
                score=item.score,
            )
            db.add(existing)
            db.flush()
        else:
            _apply_metadata(
                existing,
                {
                    "title": item.title,
                    "authors": item.authors,
                    "year": item.year,
                    "abstract": item.abstract,
                    "doi": item.doi,
                    "url": item.url,
                    "pdf_url": item.pdf_url,
                    "source": item.source,
                    "source_weight": item.source_weight,
                    "score": item.score,
                },
            )
            db.add(existing)

        _ensure_project_link(db, project_id, existing.id)
        paper_ids.append(existing.id)

    db.commit()
    return paper_ids


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
            source_weight=row.source_weight,
            score=row.score,
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
