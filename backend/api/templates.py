from fastapi import APIRouter

from schemas.templates import TemplateCreate, TemplateListResponse, TemplateMeta

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
def list_templates() -> TemplateListResponse:
    return TemplateListResponse(items=[])


@router.post("", response_model=TemplateMeta)
def create_template(payload: TemplateCreate) -> TemplateMeta:
    return TemplateMeta(id="tpl_todo", name=payload.name, description=payload.description)
