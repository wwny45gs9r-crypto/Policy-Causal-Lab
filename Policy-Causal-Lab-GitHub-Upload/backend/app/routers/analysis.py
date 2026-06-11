import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..config import settings
from ..database import get_db
from ..schemas import AnalysisConfirmRequest
from ..services.audit_logger import log_event
from ..services.causal_engine import run_analysis
from ..services.chart_engine import plot_coefficients, plot_event_study_results, plot_missing_values, plot_parallel_trends
from .helpers import latest, load_data, parse, require_project

router = APIRouter(prefix="/api/projects", tags=["analysis"])


@router.post("/{project_id}/run-analysis")
def run(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); plan = latest(db, models.MethodPlan, project_id)
    if not plan or not plan.confirmed_by_user: raise HTTPException(400, "请先确认因果推断方法")
    df = load_data(db, project_id); method_plan = {"selected_method": plan.selected_method, "model_spec": parse(plan.model_spec_json)}
    try:
        result = run_analysis(df, method_plan)
        chart_dir = settings.storage_path / str(project_id) / "charts"
        charts = [plot_missing_values(df, chart_dir), plot_coefficients(result, chart_dir)]
        warnings = result.get("warnings", [])
        if plan.selected_method == "DID" and method_plan["model_spec"].get("time_id"):
            spec = method_plan["model_spec"]
            trend, trend_warnings = plot_parallel_trends(df, {**spec, "time": spec["time_id"], "policy_time": spec.get("policy_time", df[spec["time_id"]].median())}, chart_dir)
            charts.append(trend); warnings += trend_warnings
        if plan.selected_method == "Event Study":
            charts.append(plot_event_study_results(result, chart_dir))
        row = models.AnalysisResult(project_id=project_id, method=plan.selected_method, result_json=json.dumps(result, ensure_ascii=False), diagnostics_json="{}", chart_paths_json=json.dumps(charts), warnings_json="[]")
        row.warnings_json = json.dumps(warnings, ensure_ascii=False); db.add(row); db.commit(); db.refresh(row)
        log_event(db, project_id, "analysis", "run", output_summary=json.dumps(result, ensure_ascii=False)[:2000])
        return {"result": result, "diagnostics": {}, "warnings": warnings, "chart_paths": charts, "analysis_result_id": row.id}
    except Exception as exc:
        warning = f"模型未运行: {exc}"
        log_event(db, project_id, "analysis", "blocked", warnings=[warning])
        raise HTTPException(400, warning)


@router.post("/{project_id}/confirm-analysis")
def confirm_analysis(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); result = latest(db, models.AnalysisResult, project_id)
    if not result: raise HTTPException(400, "请先运行模型分析")
    result.confirmed_by_user = True; db.commit()
    log_event(db, project_id, "analysis", "confirm", user_action="confirmed")
    return {"status": "confirmed", "analysis_result_id": result.id}


@router.post("/{project_id}/analysis-results/{result_id}/confirm")
def confirm_result(project_id: int, result_id: int, payload: AnalysisConfirmRequest, db: Session = Depends(get_db)):
    require_project(db, project_id); result = db.get(models.AnalysisResult, result_id)
    if not result or result.project_id != project_id: raise HTTPException(404, "分析结果不存在")
    result.confirmed_by_user = payload.confirmed; result.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, "analysis", "confirm_result", input_summary=payload.user_feedback, user_action="confirmed" if payload.confirmed else "questioned")
    return {"status": "confirmed" if payload.confirmed else "questioned", "analysis_result_id": result.id}
