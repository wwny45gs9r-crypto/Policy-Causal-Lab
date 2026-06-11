from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import ChatRequest
from ..services.audit_logger import log_event
from ..services.deepseek_client import DeepSeekClient
from .helpers import require_project

router = APIRouter(prefix="/api/projects", tags=["chat"])


@router.post("/{project_id}/chat")
def chat(project_id: int, payload: ChatRequest, db: Session = Depends(get_db)):
    project = require_project(db, project_id)
    result = DeepSeekClient().complete_for_project(db, project_id, "research_design", payload.message, {"project_status": project.status})
    warning = [result["warning"]] if result.get("warning") else []
    refs = result.get("knowledge_refs", [])
    log_event(db, project_id, project.status, "chat", input_summary=payload.message[:500], output_summary=str(result.get("content", ""))[:1000], reasoning={"used_system_knowledge": bool(refs), "knowledge_refs": refs}, warnings=warning)
    return {"message": result.get("content", ""), "warning": warning}
