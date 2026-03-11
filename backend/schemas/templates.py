from pydantic import BaseModel


class TemplateMeta(BaseModel):
    id: str | None = None
    name: str
    description: str | None = None


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    content: str


class TemplateListResponse(BaseModel):
    items: list[TemplateMeta]
