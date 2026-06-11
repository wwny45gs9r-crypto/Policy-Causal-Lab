import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db
from ..schemas import ConfirmMethodRequest, MethodComparisonRequest
from ..services.audit_logger import log_event
from ..services.deepseek_client import DeepSeekClient
from ..services.method_recommender import recommend_methods
from ..services.project_state import build_project_state
from .data import profile_out
from .helpers import latest, require_project

router = APIRouter(prefix="/api/projects", tags=["methods"])


@router.get("/{project_id}/method-recommendation")
def recommendation(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); profile = latest(db, models.DataProfile, project_id)
    if not profile: raise HTTPException(400, "请先生成数据画像")
    profile_data = profile_out(profile)
    methods = recommend_methods(profile_data)
    roles = profile_data.get("roles", {})
    summary = _recommendation_summary(profile_data, methods)
    log_event(db, project_id, "method_selection", "recommend", output_summary=json.dumps(methods, ensure_ascii=False))
    return {"summary": summary, "roles": roles, "recommended_methods": methods}


@router.get("/{project_id}/variable-validation")
def variable_validation(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id); profile = latest(db, models.DataProfile, project_id)
    if not profile: raise HTTPException(400, "请先上传数据并生成数据画像")
    profile_data = profile_out(profile)
    roles = profile_data["roles"]
    method = latest(db, models.MethodPlan, project_id)
    selected = method.selected_method if method else ""
    checks = []
    for item in recommend_methods(profile_data):
        status = item["feasibility_status"]
        checks.append({
            "method_name": item["method_name"],
            "support_level": item["support_level"],
            "status": status,
            "data_requirements": item["data_requirements"],
            "required_assumptions": item["required_assumptions"],
            "next_questions": _next_questions(item["method_name"], status),
            "selected": item["method_name"] == selected,
        })
    return {"detected_roles": roles, "columns": profile_data["columns"], "checks": checks}


@router.post("/{project_id}/compare-methods")
def compare_methods(project_id: int, payload: MethodComparisonRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    if len(payload.candidate_methods) < 2:
        raise HTTPException(400, "请至少选择两个候选方法进行比较")
    profile = latest(db, models.DataProfile, project_id)
    profile_summary = profile_out(profile) if profile else {"warning": "尚未生成数据画像"}
    project_state = build_project_state(db, project_id)
    prompt = (
        "请比较以下候选因果推断方法，输出 Markdown。"
        "先说明变量和识别条件是否满足，再比较优缺点、前置检验、稳健性检验、适用风险，"
        "最后给出建议排序。必须强调最终方法由研究者人工判断。\n\n"
        f"候选方法：{', '.join(payload.candidate_methods)}\n"
        f"研究问题：{payload.research_question or '未填写'}\n"
        f"研究者备注：{payload.notes or '无'}\n"
        f"连续研究状态：{json.dumps(project_state, ensure_ascii=False, default=str)[:9000]}\n"
        f"数据画像摘要：{json.dumps(profile_summary, ensure_ascii=False, default=str)[:6000]}"
    )
    result = DeepSeekClient().complete_for_project(db, project_id, "method_selection", prompt, {"candidate_methods": payload.candidate_methods, "project_state": project_state}, top_k=8)
    warning = [result["warning"]] if result.get("warning") else []
    log_event(db, project_id, "method_selection", "compare", input_summary=", ".join(payload.candidate_methods), output_summary=str(result.get("content", ""))[:1200], warnings=warning)
    return {"message": result.get("content", ""), "warning": warning, "candidate_methods": payload.candidate_methods}


@router.post("/{project_id}/confirm-method")
def confirm(project_id: int, payload: ConfirmMethodRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    methods = recommendation(project_id, db)["recommended_methods"]
    row = models.MethodPlan(project_id=project_id, recommended_methods_json=json.dumps(methods, ensure_ascii=False), selected_method=payload.selected_method, model_spec_json=json.dumps(payload.model_spec, ensure_ascii=False), confirmed_by_user=True)
    db.add(row); db.commit()
    log_event(db, project_id, "method_selection", "confirm", input_summary=payload.selected_method, output_summary=json.dumps(payload.model_spec, ensure_ascii=False), user_action="confirmed")
    return {"status": "confirmed", "selected_method": payload.selected_method, "model_spec": payload.model_spec}


def _next_questions(method_name: str, status: str) -> list[str]:
    common = ["结果变量是否清楚？", "处理变量或政策暴露如何定义？", "是否存在可比对照组？"]
    method_specific = {
        "DID": ["政策前趋势是否可检验？", "政策时点是否明确？", "处理组和对照组是否有共同趋势？"],
        "Staggered DID": ["是否存在分批实施时间？", "是否需要处理异质处理效应偏误？"],
        "Event Study": ["是否有足够政策前窗口？", "事件时间是否可定义？"],
        "Fixed Effects": ["是否有稳定的个体 ID 和时间变量？", "核心解释变量是否有组内变化？"],
        "IV / 2SLS": ["工具变量是什么？", "排除性限制如何论证？", "第一阶段是否足够强？"],
        "RDD": ["running variable 和 cutoff 是什么？", "阈值附近是否存在操纵？"],
        "Fuzzy RDD": ["阈值处处理概率是否跳跃？", "局部工具变量假设是否合理？"],
        "PSM": ["匹配协变量是否足够丰富？", "是否存在共同支撑？"],
        "Synthetic Control": ["是否有较长政策前时期？", "供体池是否未受政策影响？"],
        "Placebo Test": ["伪政策时间或伪处理组如何设定？"],
    }
    questions = method_specific.get(method_name, common)
    if status == "possible":
        return questions + ["建议进入模型设定或稳健性设计。"]
    return questions


def _recommendation_summary(profile_data: dict, methods: list[dict]) -> str:
    roles = profile_data.get("roles", {})
    executable = [item["method_name"] for item in methods if item.get("support_level") == "executable"]
    design = [item["method_name"] for item in methods if item.get("support_level") == "design"]
    outcome = "、".join(roles.get("outcome") or []) or "尚未稳定识别"
    treatment = "、".join(roles.get("treatment") or []) or "尚未稳定识别"
    time = "、".join(roles.get("time") or []) or "尚未稳定识别"
    entity = "、".join(roles.get("id") or []) or "未必需要，取决于最终方法是否使用面板或分组结构"
    return (
        f"当前数据共有 {profile_data.get('n_rows', '未知')} 行、{profile_data.get('n_cols', '未知')} 列。"
        f"系统暂时识别的结果变量候选为：{outcome}；处理/政策变量候选为：{treatment}；"
        f"时间变量候选为：{time}；个体或地区标识为：{entity}。"
        f"基于这些信息，可直接进入估计或初步诊断的方法包括：{('、'.join(executable) or '暂无')}。"
        f"仍需要进一步论证或补充变量设定的方法包括：{('、'.join(design[:6]) or '暂无')}。"
        "这些推荐只用于缩小候选范围，最终识别策略仍应由研究者结合制度背景、数据质量和识别假设判断。"
    )
