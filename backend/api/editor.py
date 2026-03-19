from fastapi import APIRouter

from agents.editor_agent import EditorAgent
from schemas.editor import EditRequest, EditResponse
from services.telemetry.context import telemetry_context

router = APIRouter(prefix="/api/editor", tags=["editor"])


@router.post("", response_model=EditResponse)
def edit_text(payload: EditRequest) -> EditResponse:
    agent = EditorAgent()
    with telemetry_context(operation="editor.rewrite"):
        result = agent.run(payload.model_dump())
    return EditResponse(content=result.get("content", payload.content))
