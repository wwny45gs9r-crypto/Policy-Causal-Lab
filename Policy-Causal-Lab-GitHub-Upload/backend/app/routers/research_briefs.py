import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ResearchBrief
from ..schemas import ResearchBriefPayload
from ..services.audit_logger import log_event
from .helpers import require_project

router = APIRouter(prefix="/api/projects", tags=["research-brief"])
JSON_FIELDS = ["outcome_variables", "mechanism_variables", "covariates", "hypotheses"]


def brief_out(row):
    return {field: (json.loads(getattr(row, field)) if field in JSON_FIELDS else getattr(row, field)) for field in ["id", "project_id", "policy_name", "policy_background", "research_question", "research_objective", "treatment_definition", "control_definition", "time_window", *JSON_FIELDS, "identification_strategy_notes", "confirmed_by_user", "version"]}


@router.get("/{project_id}/research-brief")
def get_brief(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); row = db.query(ResearchBrief).filter(ResearchBrief.project_id == project_id).first()
    if not row: raise HTTPException(404, "尚未创建 ResearchBrief")
    return brief_out(row)


def save_brief(project_id: int, payload: ResearchBriefPayload, db: Session):
    require_project(db, project_id); row = db.query(ResearchBrief).filter(ResearchBrief.project_id == project_id).first() or ResearchBrief(project_id=project_id)
    for field, value in payload.model_dump().items(): setattr(row, field, json.dumps(value, ensure_ascii=False) if field in JSON_FIELDS else value)
    row.version = (row.version or 0) + 1; row.confirmed_by_user = False; db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "research_design", "save_brief", output_summary=f"version {row.version}", user_action="saved")
    return brief_out(row)


@router.post("/{project_id}/research-brief")
def create_or_update(project_id: int, payload: ResearchBriefPayload, db: Session = Depends(get_db)): return save_brief(project_id, payload, db)


@router.patch("/{project_id}/research-brief")
def patch_brief(project_id: int, payload: ResearchBriefPayload, db: Session = Depends(get_db)): return save_brief(project_id, payload, db)


@router.post("/{project_id}/research-brief/confirm")
def confirm_brief(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); row = db.query(ResearchBrief).filter(ResearchBrief.project_id == project_id).first()
    if not row: raise HTTPException(404, "尚未创建 ResearchBrief")
    row.confirmed_by_user = True; db.commit(); log_event(db, project_id, "research_design", "confirm_brief", user_action="confirmed")
    return brief_out(row)
