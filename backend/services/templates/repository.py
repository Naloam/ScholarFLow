from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.template import Template
from schemas.templates import TemplateCreate, TemplateMeta


BUILTIN_DIR = Path("backend/templates")


def _load_builtin_templates() -> list[TemplateMeta]:
    items: list[TemplateMeta] = []
    if not BUILTIN_DIR.exists():
        return items
    for path in sorted(BUILTIN_DIR.glob("*.md")):
        slug = path.stem
        title = slug.replace("_", " ").title()
        items.append(TemplateMeta(id=f"builtin:{slug}", name=title, description="Built-in"))
    return items


def list_templates(db: Session) -> list[TemplateMeta]:
    rows = db.execute(select(Template)).scalars().all()
    custom = [
        TemplateMeta(id=row.id, name=row.name, description=row.description) for row in rows
    ]
    return _load_builtin_templates() + custom


def get_template_content(db: Session, template_id: str | None) -> str | None:
    if not template_id:
        return None
    if template_id.startswith("builtin:"):
        slug = template_id.split("builtin:", 1)[1]
        path = BUILTIN_DIR / f"{slug}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
    row = db.execute(select(Template).where(Template.id == template_id)).scalar_one_or_none()
    if row is None:
        return None
    return row.content


def create_template(db: Session, payload: TemplateCreate) -> TemplateMeta:
    row = Template(
        id=f"tpl_{uuid4().hex}",
        name=payload.name,
        description=payload.description,
        content=payload.content,
    )
    db.add(row)
    db.commit()
    return TemplateMeta(id=row.id, name=row.name, description=row.description)
