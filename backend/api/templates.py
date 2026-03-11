from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.deps import get_db
from schemas.templates import TemplateCreate, TemplateListResponse, TemplateMeta
from services.templates.repository import create_template, list_templates

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
def list_templates_endpoint(db: Session = Depends(get_db)) -> TemplateListResponse:
    return TemplateListResponse(items=list_templates(db))


@router.post("", response_model=TemplateMeta)
def create_template_endpoint(
    payload: TemplateCreate, db: Session = Depends(get_db)
) -> TemplateMeta:
    return create_template(db, payload)
