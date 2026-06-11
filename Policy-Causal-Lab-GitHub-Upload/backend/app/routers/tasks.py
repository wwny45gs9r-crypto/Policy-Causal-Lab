import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..models import TaskRecord
from .helpers import require_project

router = APIRouter(prefix="/api/projects", tags=["tasks"])


def task_out(row):
    return {"id": row.id, "task_type": row.task_type, "status": row.status, "progress": row.progress, "message": row.message, "result": json.loads(row.result_json)}


def _latest(db: Session, model, project_id: int):
    return db.query(model).filter(model.project_id == project_id).order_by(model.id.desc()).first()


def _item(index: int, task_type: str, row, ready_message: str, pending_message: str):
    confirmed = bool(getattr(row, "confirmed_by_user", False)) if row else False
    exists = bool(row)
    status = "confirmed" if confirmed else "completed" if exists else "pending"
    progress = 100 if confirmed or exists else 0
    return {
        "id": -index,
        "task_type": task_type,
        "status": status,
        "progress": progress,
        "message": ready_message if exists else pending_message,
    }


def _project_status_items(db: Session, project_id: int) -> list[dict]:
    data_file_count = db.query(models.UploadedFile).filter(models.UploadedFile.project_id == project_id, models.UploadedFile.file_type == "data").count()
    report = _latest(db, models.Report, project_id)
    robustness = _latest(db, models.RobustnessResult, project_id)
    items = [
        _item(1, "1. 因果问题定义", _latest(db, models.CausalQuestion, project_id), "已完成。", "未完成。"),
        _item(2, "2. 变量与因果结构", _latest(db, models.CausalStructure, project_id), "已完成。", "未完成。"),
        _item(3, "3. 反事实构造", _latest(db, models.CounterfactualPlan, project_id), "已完成。", "未完成。"),
        _item(4, "4. 处理分配机制", _latest(db, models.AssignmentMechanism, project_id), "已完成。", "未完成。"),
        _item(5, "5. 识别策略选择", _latest(db, models.IdentificationStrategy, project_id), "已完成。", "未完成。"),
        {
            "id": -6,
            "task_type": "6. 数据上传与可识别性检查",
            "status": "completed" if data_file_count else "pending",
            "progress": 100 if data_file_count else 0,
            "message": f"已上传数据；可识别性检查状态见第 6 步输出。" if data_file_count else "未完成。",
        },
        _item(7, "7. 估计设定确认", _latest(db, models.EstimationSetup, project_id), "已完成。", "未完成。"),
        _item(8, "8. 模型估计", _latest(db, models.EstimationResult, project_id), "已完成。", "未完成。"),
        _item(9, "9. 识别假设诊断", _latest(db, models.AssumptionDiagnostics, project_id), "已完成。", "未完成。"),
        _item(10, "10. 因果效应解释", _latest(db, models.CausalEffectInterpretation, project_id), "已完成。", "未完成。"),
        _item(11, "11. 稳健性与敏感性分析", robustness, "已完成。", "未完成。"),
        _item(12, "12. 因果推断报告", report, f"已生成报告 version {report.version}。" if report else "已完成。", "未完成。"),
    ]
    completed = sum(1 for item in items if item["status"] in {"completed", "confirmed"})
    return [{
        "id": 0,
        "task_type": "项目总进度",
        "status": "completed" if completed == len(items) else "in_progress",
        "progress": round(completed / len(items) * 100),
        "message": f"已完成 {completed}/{len(items)} 个流程节点。",
    }, *items]


@router.get("/{project_id}/tasks")
def list_tasks(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    rows = db.query(TaskRecord).filter(TaskRecord.project_id == project_id).order_by(TaskRecord.id.desc()).all()
    if rows:
        return [task_out(row) for row in rows]
    return _project_status_items(db, project_id)


@router.get("/{project_id}/tasks/{task_id}")
def get_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); row = db.get(TaskRecord, task_id)
    if not row or row.project_id != project_id: raise HTTPException(404, "任务不存在")
    return task_out(row)
