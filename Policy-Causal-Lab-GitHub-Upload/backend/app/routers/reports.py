import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db
from ..schemas import ReportRequest, ReportUpdateRequest
from ..services.audit_logger import log_event
from ..services.project_state import build_project_state
from ..services.report_generator import generate_report
from .helpers import latest, parse, require_project

router = APIRouter(prefix="/api/projects", tags=["reports"])


@router.post("/{project_id}/generate-report")
def generate(project_id: int, payload: ReportRequest, db: Session = Depends(get_db)):
    require_project(db, project_id); analysis = latest(db, models.AnalysisResult, project_id)
    brief = db.query(models.ResearchBrief).filter(models.ResearchBrief.project_id == project_id, models.ResearchBrief.confirmed_by_user.is_(True)).first()
    cleaning, method = latest(db, models.CleaningPlan, project_id), latest(db, models.MethodPlan, project_id)
    logs = db.query(models.AuditLog).filter(models.AuditLog.project_id == project_id).order_by(models.AuditLog.id.desc()).limit(30).all()
    context = {
        "project_state": build_project_state(db, project_id),
        "research_brief": {"policy_name": brief.policy_name, "research_question": brief.research_question, "research_objective": brief.research_objective, "treatment_definition": brief.treatment_definition, "control_definition": brief.control_definition, "outcome_variables": parse(brief.outcome_variables)} if brief else {},
        "cleaning_plan": parse(cleaning.plan_json) if cleaning else {},
        "method_plan": {"selected_method": method.selected_method, "model_spec": parse(method.model_spec_json)} if method else {},
        "analysis": parse(analysis.result_json) if analysis else {}, "diagnostics": parse(analysis.diagnostics_json) if analysis else {}, "charts": parse(analysis.chart_paths_json) if analysis else [], "warnings": parse(analysis.warnings_json) if analysis else [],
        "audit_summary": [{"step": row.step, "action": row.action, "warnings": parse(row.warnings_json)} for row in logs],
    }
    markdown, warnings, refs = generate_report(db, project_id, context)
    version = db.query(models.Report).filter(models.Report.project_id == project_id).count() + 1
    row = models.Report(project_id=project_id, markdown_content=markdown, version=version); db.add(row); db.commit()
    log_event(db, project_id, "causal_report", "generate", output_summary=f"version {version}", reasoning={"used_system_knowledge": bool(refs), "knowledge_refs": refs}, warnings=warnings, user_action="confirmed" if payload.confirmed else "")
    return {"markdown_content": markdown, "version": version, "warnings": warnings}


@router.get("/{project_id}/report")
def get_report(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); report = latest(db, models.Report, project_id)
    if not report: raise HTTPException(404, "尚未生成报告")
    return {"markdown_content": report.markdown_content, "version": report.version}


def report_out(report):
    return {"id": report.id, "project_id": report.project_id, "markdown_content": report.markdown_content, "version": report.version, "status": report.status, "user_feedback": report.user_feedback, "created_at": report.created_at, "updated_at": report.updated_at}


@router.get("/{project_id}/reports")
def list_reports(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return [report_out(row) for row in db.query(models.Report).filter(models.Report.project_id == project_id).order_by(models.Report.version.desc()).all()]


@router.get("/{project_id}/reports/{report_id}")
def get_report_version(project_id: int, report_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); row = db.get(models.Report, report_id)
    if not row or row.project_id != project_id: raise HTTPException(404, "报告版本不存在")
    return report_out(row)


@router.patch("/{project_id}/reports/{report_id}")
def update_report(project_id: int, report_id: int, payload: ReportUpdateRequest, db: Session = Depends(get_db)):
    require_project(db, project_id); row = db.get(models.Report, report_id)
    if not row or row.project_id != project_id: raise HTTPException(404, "报告版本不存在")
    row.markdown_content = payload.markdown_content; row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, "report", "edit", output_summary=f"version {row.version}", user_action="saved")
    return report_out(row)


@router.post("/{project_id}/reports/{report_id}/confirm")
def confirm_report(project_id: int, report_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); row = db.get(models.Report, report_id)
    if not row or row.project_id != project_id: raise HTTPException(404, "报告版本不存在")
    row.status = "confirmed"; db.commit()
    log_event(db, project_id, "report", "confirm", output_summary=f"version {row.version}", user_action="confirmed")
    return report_out(row)
