import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..config import settings
from ..database import get_db
from ..schemas import CleaningPlanRequest, ConfirmCleaningRequest
from ..services.audit_logger import log_event
from ..services.ai_variable_analyzer import infer_roles_with_ai
from ..services.cleaning_engine import apply_cleaning, default_cleaning_plan
from ..services.data_profiler import infer_variable_roles, profile_dataset
from ..services.project_state import build_project_state
from .helpers import latest, load_data, parse, require_project

router = APIRouter(prefix="/api/projects", tags=["data"])


def profile_out(row):
    method_feasibility = parse(row.method_feasibility_json)
    roles = method_feasibility.get("_roles") or {"id": parse(row.id_candidates_json), "time": parse(row.time_candidates_json), "treatment": parse(row.treatment_candidates_json), "outcome": parse(row.outcome_candidates_json)}
    return {"n_rows": row.n_rows, "n_cols": row.n_cols, "columns": parse(row.columns_json), "missing_summary": parse(row.missing_summary_json), "variable_types": parse(row.variable_types_json), "descriptive_summary": method_feasibility.get("_descriptive_summary", ""), "descriptive_statistics": method_feasibility.get("_descriptive_statistics", {}), "roles": roles, "semantic_notes": method_feasibility.get("_semantic_notes", ""), "semantic_warning": method_feasibility.get("_semantic_warning", ""), "method_feasibility": {k: v for k, v in method_feasibility.items() if not k.startswith("_")}}


@router.get("/{project_id}/data-profile")
def get_profile(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    df = load_data(db, project_id)
    rule_roles = infer_variable_roles(df)
    semantic = infer_roles_with_ai(df, rule_roles, build_project_state(db, project_id))
    profile = profile_dataset(df, semantic["roles"], semantic.get("notes", ""), semantic.get("warning", ""))
    roles = profile["roles"]
    row = models.DataProfile(project_id=project_id, n_rows=profile["n_rows"], n_cols=profile["n_cols"], columns_json=json.dumps(profile["columns"], ensure_ascii=False), missing_summary_json=json.dumps(profile["missing_summary"], ensure_ascii=False), variable_types_json=json.dumps(profile["variable_types"], ensure_ascii=False), id_candidates_json=json.dumps(roles["id"], ensure_ascii=False), time_candidates_json=json.dumps(roles["time"], ensure_ascii=False), treatment_candidates_json=json.dumps(roles["treatment"], ensure_ascii=False), outcome_candidates_json=json.dumps(roles["outcome"], ensure_ascii=False), method_feasibility_json=json.dumps(profile["method_feasibility"], ensure_ascii=False))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "descriptive_statistics", "generate", output_summary=f"{row.n_rows} rows, {row.n_cols} columns; roles={json.dumps(roles, ensure_ascii=False)[:1000]}", warnings=[semantic["warning"]] if semantic.get("warning") else [])
    return profile_out(row)


@router.post("/{project_id}/cleaning-plan")
def cleaning_plan(project_id: int, payload: CleaningPlanRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    profile = latest(db, models.DataProfile, project_id)
    if not profile: raise HTTPException(400, "请先生成数据画像")
    plan = payload.plan or default_cleaning_plan(profile_out(profile))
    row = models.CleaningPlan(project_id=project_id, plan_json=json.dumps(plan, ensure_ascii=False))
    db.add(row); db.commit()
    log_event(db, project_id, "cleaning", "propose_plan", output_summary=json.dumps(plan, ensure_ascii=False))
    return {"plan": plan, "status": row.status}


@router.post("/{project_id}/confirm-cleaning")
def confirm_cleaning(project_id: int, payload: ConfirmCleaningRequest, db: Session = Depends(get_db)):
    require_project(db, project_id); df = load_data(db, project_id)
    clean, summary = apply_cleaning(df, payload.plan)
    path = settings.storage_path / str(project_id) / "clean_data_v1.csv"; path.parent.mkdir(parents=True, exist_ok=True); clean.to_csv(path, index=False)
    row = latest(db, models.CleaningPlan, project_id) or models.CleaningPlan(project_id=project_id, plan_json="{}")
    row.plan_json = json.dumps(payload.plan, ensure_ascii=False); row.user_feedback = payload.user_feedback; row.status = "confirmed"; db.add(row); db.commit()
    log_event(db, project_id, "cleaning", "confirm_and_execute", output_summary=json.dumps(summary), user_action="confirmed")
    return {"status": "confirmed", "clean_data_path": str(path), "summary": summary}
