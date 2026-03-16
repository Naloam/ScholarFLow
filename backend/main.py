from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from api.tasks import router as tasks_router
from api.chunks import router as chunks_router
from api.tutor import router as tutor_router
from api.editor import router as editor_router
from api.analysis import router as analysis_router
from api.progress import router as progress_router
from config.settings import settings

app = FastAPI(title="ScholarFlow API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(tasks_router)
app.include_router(chunks_router)
app.include_router(tutor_router)
app.include_router(editor_router)
app.include_router(analysis_router)
app.include_router(progress_router)
