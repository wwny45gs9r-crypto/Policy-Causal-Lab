import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AuditLog
from .helpers import require_project

router = APIRouter(prefix="/api/projects", tags=["logs"])


@router.get("/{project_id}/audit-logs")
def logs(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    rows = db.query(AuditLog).filter(AuditLog.project_id == project_id).order_by(AuditLog.created_at.desc()).all()
    return [{"id": r.id, "step": r.step, "action": r.action, "input_summary": r.input_summary, "output_summary": r.output_summary, "reasoning_summary": json.loads(r.reasoning_summary_json), "warnings": json.loads(r.warnings_json), "user_action": r.user_action, "created_at": r.created_at} for r in rows]
