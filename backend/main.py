from fastapi import FastAPI

from api.health import router as health_router
from api.projects import router as projects_router
from api.search import router as search_router
from api.papers import router as papers_router
from api.evidence import router as evidence_router
from api.drafts import router as drafts_router
from api.review import router as review_router
from api.experiments import router as experiments_router
from api.export import router as export_router
from api.templates import router as templates_router

app = FastAPI(title="ScholarFlow API", version="0.1.0")

app.include_router(health_router)
app.include_router(projects_router)
app.include_router(search_router)
app.include_router(papers_router)
app.include_router(evidence_router)
app.include_router(drafts_router)
app.include_router(review_router)
app.include_router(experiments_router)
app.include_router(export_router)
app.include_router(templates_router)
