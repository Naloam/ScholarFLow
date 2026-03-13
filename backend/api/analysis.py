from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.deps import get_db
from schemas.analysis import AnalysisSummary
from services.analysis.summary import build_summary

router = APIRouter(prefix="/api/projects/{project_id}/analysis", tags=["analysis"])


@router.get("/summary", response_model=AnalysisSummary)
def get_summary(project_id: str, db: Session = Depends(get_db)) -> AnalysisSummary:
    return build_summary(db, project_id)
