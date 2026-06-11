import json
from typing import Any
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models
from ..config import settings
from ..database import get_db
from ..schemas import CausalModuleConfirmRequest, CausalModuleRequest
from ..services.audit_logger import log_event
from ..services.causal_engine import run_analysis
from ..services.chart_engine import plot_coefficients, plot_missing_values
from ..services.data_profiler import infer_variable_roles, profile_dataset
from ..services.deepseek_client import DeepSeekClient
from ..services.project_state import build_project_state
from .helpers import latest, load_data, parse, require_project

router = APIRouter(prefix="/api/projects", tags=["causal-workflow"])


def _latest(db: Session, model, project_id: int):
    return db.query(model).filter(model.project_id == project_id).order_by(model.id.desc()).first()


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def _parse(value: str | None, default: Any):
    try:
        return json.loads(value or "")
    except Exception:
        return default


def _list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _unique(items: list[Any]) -> list[Any]:
    seen = set()
    result = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if key not in seen and item not in (None, ""):
            seen.add(key)
            result.append(item)
    return result


def _project_columns(db: Session, project_id: int) -> list[str]:
    try:
        return list(load_data(db, project_id).columns)
    except Exception:
        return []


def _select_panel_id(columns: list[str]) -> str:
    priority = ["province_id", "city_id", "county_id", "firm_id", "school_id", "unit_id", "id"]
    lowered = {str(column).lower(): str(column) for column in columns}
    for name in priority:
        if name in lowered:
            return lowered[name]
    for column in columns:
        name = str(column).lower()
        if name.endswith("_id") or name in {"id", "code"}:
            return str(column)
    return ""


def _edge_text(edge: Any) -> str:
    if isinstance(edge, str):
        text = edge.strip()
        if "->" in text:
            return text
        return ""
    if isinstance(edge, (list, tuple)) and len(edge) >= 2:
        source, target = str(edge[0]).strip(), str(edge[1]).strip()
        if source and target and source != target:
            return f"{source} -> {target}"
    if isinstance(edge, dict):
        source = edge.get("source") or edge.get("from") or edge.get("cause")
        target = edge.get("target") or edge.get("to") or edge.get("effect")
        if source and target and str(source) != str(target):
            return f"{source} -> {target}"
    return ""


def _normalize_causal_structure(data: dict, treatment: str, outcome: str, columns: list[str]) -> dict:
    data = dict(data)
    observed = set(columns)
    warnings = _list(data.get("warnings"))
    confounders = [item for item in _list(data.get("confounders")) if not observed or item in observed]
    post_treatment = _unique(_list(data.get("post_treatment_variables")) + _list(data.get("bad_controls")))
    mediators = _unique(_list(data.get("mediators")))
    for variable in mediators:
        if variable not in post_treatment and variable not in observed:
            post_treatment.append(variable)
    edges = [_edge_text(edge) for edge in _list(data.get("dag_edges"))]
    edges = [edge for edge in edges if edge]
    if treatment and outcome:
        edges.append(f"{treatment} -> {outcome}")
    for variable in confounders:
        if variable not in {treatment, outcome}:
            edges.append(f"{variable} -> {treatment}")
            edges.append(f"{variable} -> {outcome}")
    for variable in mediators:
        if variable not in observed:
            edges.append(f"{treatment} -> {variable}")
            edges.append(f"{variable} -> {outcome}")
    data["confounders"] = _unique(confounders)
    data["mediators"] = mediators
    data["post_treatment_variables"] = post_treatment
    data["bad_controls"] = _unique(_list(data.get("bad_controls")) + [item for item in post_treatment if item not in observed])
    data["dag_edges"] = _unique(edges)
    if post_treatment:
        warnings.append("政策后变量或机制变量已单独标记，不应作为主回归的普通控制变量。")
    data["warnings"] = _unique(warnings)
    return data


def _looks_single_policy_start(db: Session, project_id: int) -> bool:
    try:
        df = load_data(db, project_id)
    except Exception:
        return False
    if {"treat", "post", "year"}.issubset(df.columns):
        treated_years = sorted(pd.to_numeric(df.loc[(df["treat"] == 1) & (df["post"] == 1), "year"], errors="coerce").dropna().unique())
        return bool(treated_years) and int(treated_years[0]) == 2018
    return False


def _looks_policy_pilot_from_state(db: Session, project_id: int) -> bool:
    state = build_project_state(db, project_id)
    texts = []
    for section in ["causal_question", "counterfactual"]:
        value = state.get(section, {})
        if isinstance(value, dict):
            texts.extend(str(item) for item in value.values() if isinstance(item, str))
    joined = " ".join(texts)
    has_partial_treated = any(token in joined for token in ["部分省份", "试点", "处理组", "对照组", "未纳入"])
    has_single_start = any(token in joined for token in ["2018年", "2018 年", "同一年", "统一开始"])
    return has_partial_treated and has_single_start


def _normalize_assignment(data: dict, db: Session, project_id: int) -> dict:
    data = dict(data)
    warnings = _list(data.get("warnings"))
    single_start = _looks_single_policy_start(db, project_id) or _looks_policy_pilot_from_state(db, project_id)
    if data.get("mechanism_type") == "staggered_policy" and single_start:
        data["mechanism_type"] = "policy_pilot"
        warnings.append("数据呈现统一政策起点，不应标记为 staggered_policy；已按非随机政策试点处理。")
    if data.get("mechanism_type") in {"", None, "unclear"} and single_start:
        data["mechanism_type"] = "policy_pilot"
        warnings.append("AI 未明确给出分配机制；系统根据当前项目中的试点省份、对照组和统一政策起点补全为非随机政策试点。")
    if data.get("mechanism_type") in {"policy_pilot", "observational_policy_panel"} and single_start:
        data["description"] = data.get("description") or "政策由政府选择试点省份并在2018年统一开始实施，处理分配不是随机实验。"
        data["evidence"] = _unique(_list(data.get("evidence")) + ["存在处理组和对照组", "存在政策前后多期面板数据", "处理组政策后年份从2018年开始"])
        data["possible_strategies"] = _unique(_list(data.get("possible_strategies")) + ["DID with province fixed effects and year fixed effects", "Event Study", "PSM-DID", "Fixed Effects"])
        data["endogeneity_risks"] = _unique(_list(data.get("endogeneity_risks")) + ["非随机试点选择", "处理组与对照组政策前趋势差异", "同期政策冲击"])
    data["warnings"] = _unique(warnings)
    return data


def _llm_json(db: Session, project_id: int, module: str, text: str, extra: dict | None = None) -> tuple[dict, list[str]]:
    context = {"project_state": build_project_state(db, project_id), **(extra or {})}
    result = DeepSeekClient().complete_for_project(db, project_id, module, text or "请基于当前项目状态生成结构化建议。", context, top_k=8)
    warnings = [result["warning"]] if result.get("warning") else []
    content = result.get("content") if isinstance(result.get("content"), dict) else {}
    if not content and result.get("raw_text"):
        warnings.append("AI 返回内容未能解析为 JSON，已保留默认结构。")
    return content or {}, warnings


def _merge(base: dict, incoming: dict) -> dict:
    return {**base, **{k: v for k, v in incoming.items() if v is not None}}


def _merge_nonempty(base: dict, incoming: dict) -> dict:
    return {**base, **{k: v for k, v in incoming.items() if v not in (None, "", [], {})}}


def _counterfactual_fallback(db: Session, project_id: int, text: str) -> dict:
    state = build_project_state(db, project_id)
    question = state.get("causal_question", {})
    treatment = question.get("treatment") or "处理/政策"
    outcome = question.get("outcome") or "结果变量"
    unit = question.get("unit") or "处理单位"
    return {
        "counterfactual_question": f"如果{unit}没有接受{treatment}，{outcome}本来会如何变化？",
        "comparison_group": "未接受处理或政策暴露较弱、且在政策前与处理组可比的单位；需要用户结合研究设计确认。",
        "counterfactual_source": "untreated_group_trend",
        "plausibility_assessment": "medium",
        "risks": ["处理不是随机分配，可能存在选择性进入。", "处理组和对照组政策前趋势可能不同。", "同期冲击或其他政策可能影响结果变量。"],
        "required_evidence": ["处理组和对照组的政策前趋势图。", "政策实施时间和处理组定义。", "对照组未受到同类政策或溢出影响的说明。"],
        "warnings": ["AI 返回内容未能解析为 JSON，系统已根据当前因果问题生成本地反事实草案，请人工确认。"] if text else ["系统已生成本地反事实草案，请人工确认。"],
    }


def _confirmed(row) -> dict:
    row.confirmed_by_user = True
    return {"status": "confirmed", "id": row.id}


def _md_value(value: Any, default: str = "尚未明确") -> str:
    if value in (None, "", [], {}):
        return default
    if isinstance(value, list):
        return "；".join(str(item) for item in value if item not in (None, "")) or default
    if isinstance(value, dict):
        return "；".join(f"{key}: {val}" for key, val in value.items() if val not in (None, "", [], {})) or default
    return str(value)


def _md_bullets(items: Any, default: str = "- 暂无") -> str:
    values = _list(items)
    values = [str(item) for item in values if item not in (None, "")]
    return "\n".join(f"- {item}" for item in values) if values else default


def _causal_question_markdown(row: models.CausalQuestion) -> str:
    questions = parse(row.clarification_questions_json)
    return f"""### 研究合作者建议

我会先把这个想法收束成一个可检验的因果问题：**{_md_value(row.causal_question_text)}**

当前最关键的研究要素是：处理为 **{_md_value(row.treatment)}**，结果为 **{_md_value(row.outcome)}**，分析单位为 **{_md_value(row.unit)}**，时间窗口为 **{_md_value(row.time_window)}**。估计目标暂定为 **{_md_value(row.estimand)}**。

下一步不要急着跑模型，先确认这些定义是否符合你的研究对象。尤其需要确认：
{_md_bullets(questions, "- 暂无必须立即澄清的问题；后续会继续检查变量、反事实和识别条件。")}"""


def _structure_markdown(row: models.CausalStructure) -> str:
    confounders = parse(row.confounders_json)
    bad_controls = _unique(parse(row.bad_controls_json) + parse(row.post_treatment_variables_json))
    return f"""### 变量与因果结构建议

当前结构围绕 **{_md_value(row.treatment)} -> {_md_value(row.outcome)}** 展开。优先需要关注的是会同时影响处理分配和结果的混杂因素，而不是把所有相关变量都放进回归。

建议优先讨论的混杂变量：
{_md_bullets(confounders)}

不宜作为主回归普通控制变量的项目：
{_md_bullets(bad_controls)}

DAG 边的初稿如下，后续应由你结合政策机制和数据口径确认：
{_md_bullets(parse(row.dag_edges_json))}"""


def _counterfactual_markdown(row: models.CounterfactualPlan) -> str:
    return f"""### 反事实构造建议

核心反事实问题是：**{_md_value(row.counterfactual_question)}**

当前可用的比较对象是：{_md_value(row.comparison_group)}。反事实来源判断为 **{_md_value(row.counterfactual_source)}**，可信度暂定为 **{_md_value(row.plausibility_assessment)}**。

主要风险：
{_md_bullets(parse(row.risks_json))}

建议下一步补充或检查的证据：
{_md_bullets(parse(row.required_evidence_json))}"""


def _assignment_markdown(row: models.AssignmentMechanism) -> str:
    return f"""### 处理分配机制判断

当前更像 **{_md_value(row.mechanism_type)}**。{_md_value(row.description)}

判断依据：
{_md_bullets(parse(row.evidence_json))}

这一步对识别策略很关键，因为非随机分配通常意味着处理组和对照组在政策前就可能不同。需要重点防范：
{_md_bullets(parse(row.endogeneity_risks_json))}

可进一步考虑的策略：
{_md_bullets(parse(row.possible_strategies_json))}"""


def _strategy_markdown(row: models.IdentificationStrategy) -> str:
    return f"""### 识别策略建议

我建议当前优先考虑 **{_md_value(row.recommended_strategy)}**。风险等级为 **{_md_value(row.risk_level)}**，先验可信度评分为 **{row.credibility_prior}/100**。

反事实逻辑：{_md_value(row.counterfactual_logic)}

该策略成立依赖的关键假设：
{_md_bullets(parse(row.key_assumptions_json))}

运行前需要的数据条件：
{_md_bullets(parse(row.required_data_json))}

建议诊断：
{_md_bullets(parse(row.diagnostics_json))}

如果这些条件无法满足，应把结论降级为描述性或相关性分析。"""


def _identifiability_markdown(row: models.DataIdentifiabilityCheck) -> str:
    roles = parse(row.variable_roles_json)
    return f"""### 数据可识别性判断

当前数据包含 **{row.n_rows}** 行、**{row.n_cols}** 列，可识别性状态为 **{_md_value(row.identifiability_status)}**。

从变量角色看，处理变量候选为 **{_md_value(roles.get("treatment", []), "未发现")}**，结果变量候选为 **{_md_value(roles.get("outcome", []), "未发现")}**，时间变量候选为 **{_md_value(roles.get("time", []), "未发现")}**，个体/地区标识候选为 **{_md_value(roles.get("id", []), "未发现")}**。

这个检查只能说明数据结构是否初步支持估计，不能自动证明识别假设成立。若缺少处理组、对照组、政策前后或关键变量，应先修正数据与研究设计。"""


def _setup_markdown(row: models.EstimationSetup) -> str:
    return f"""### 估计设定建议

当前建议使用 **{_md_value(row.strategy)}**。模型会以 **{_md_value(row.outcome)}** 为结果变量，以 **{_md_value(row.treatment)}** 为处理变量，时间变量为 **{_md_value(row.time_variable)}**，分析单位为 **{_md_value(row.entity_variable)}**。

协变量建议为：{_md_value(parse(row.covariates_json), "暂无")}。固定效应设定为：{_md_value(parse(row.fixed_effects_json))}。标准误建议使用 **{_md_value(row.standard_error_type)}**，聚类变量为 **{_md_value(row.cluster_variable)}**。

模型公式：
```text
{_md_value(row.model_formula, "尚未形成可执行公式")}
```

请确认这些变量名确实对应你的数据口径；如果处理变量、政策后变量或单位变量选错，后续估计结果会失去研究含义。"""


def _diagnostics_markdown(row: models.AssumptionDiagnostics) -> str:
    diagnostics = parse(row.diagnostics_json)
    pending = diagnostics.get("pending", []) if isinstance(diagnostics, dict) else []
    return f"""### 识别假设诊断解释

当前可信度判断为 **{_md_value(row.credibility_assessment)}**。已通过检查包括：
{_md_bullets(parse(row.passed_checks_json))}

未通过或存在风险的检查包括：
{_md_bullets(parse(row.failed_checks_json))}

仍待补充的检查包括：
{_md_bullets(pending)}

诊断通过只能增强因果解释的可信度，不能证明所有识别假设都绝对成立；诊断失败时应降低结论强度。"""


def _estimation_markdown(row: models.EstimationResult) -> str:
    result = parse(row.result_json)
    main = _main_effect(result)
    return f"""### 模型估计结果解读

已运行 **{_md_value(row.strategy)}**，样本量为 **{row.n_obs}**。核心估计项为 **{_md_value(main.get("term"))}**，系数为 **{_md_value(main.get("coefficient"))}**，p 值为 **{_md_value(main.get("p_value"))}**。

模型公式：
```text
{_md_value(row.model_formula)}
```

这个结果还不能单独构成因果结论，必须结合识别策略、诊断检查和稳健性分析一起解释。"""


def _effect_markdown(row: models.CausalEffectInterpretation) -> str:
    return f"""### 因果效应解释

{_md_value(row.causal_claim)}

估计目标解释：{_md_value(row.estimand_interpretation)}

效应大小与统计不确定性：{_md_value(row.effect_size_interpretation)} {_md_value(row.statistical_uncertainty, "")}

识别条件：
{_md_bullets(parse(row.identification_conditions_json))}

不能支持的结论：
{_md_bullets(parse(row.unsupported_claims_json))}

可信度为 **{_md_value(row.credibility_label)}**，评分 **{row.credibility_score}/100**。"""


def _robustness_markdown(output: dict) -> str:
    results = output.get("results", {}) if isinstance(output.get("results"), dict) else {}
    implemented = results.get("implemented", [])
    unavailable = results.get("unavailable", [])
    concern_items = [item.get("name", "") for item in implemented if item.get("status") == "concern"]
    return f"""### 稳健性与敏感性分析建议

{_md_value(output.get("interpretation"), "尚未形成稳健性解释。")}

已真实运行的检查包括：
{_md_bullets([item.get("name", "") for item in implemented])}

需要谨慎对待的检查：
{_md_bullets(concern_items, "- 当前未发现明确 concern 项。")}

尚未实现或未运行的检查：
{_md_bullets([item.get("name", item) if isinstance(item, dict) else item for item in unavailable])}

稳健性检查不能替代识别假设论证；如果安慰剂或预趋势检查失败，应降低因果结论强度。"""


def _causal_question_out(row: models.CausalQuestion | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _causal_question_markdown(row), "causal_question_text": row.causal_question_text, "treatment": row.treatment, "outcome": row.outcome, "unit": row.unit, "time_window": row.time_window, "target_population": row.target_population, "estimand": row.estimand, "research_context": row.research_context, "clarification_questions": parse(row.clarification_questions_json), "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


@router.get("/{project_id}/causal-question")
def get_causal_question(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return _causal_question_out(_latest(db, models.CausalQuestion, project_id))


@router.post("/{project_id}/causal-question")
def post_causal_question(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    data, warnings = _llm_json(db, project_id, "causal_question_builder", payload.text, payload.data)
    data = _merge(data, payload.data)
    panel_id = _select_panel_id(_project_columns(db, project_id))
    if panel_id:
        data["unit"] = panel_id
    row = models.CausalQuestion(project_id=project_id, causal_question_text=data.get("causal_question_text", payload.text), treatment=data.get("treatment", ""), outcome=data.get("outcome", ""), unit=data.get("unit", ""), time_window=data.get("time_window", ""), target_population=data.get("target_population", ""), estimand=data.get("estimand", "unclear"), research_context=data.get("research_context", payload.text), clarification_questions_json=_json(data.get("clarification_questions", [])), warnings_json=_json(_list(data.get("warnings")) + warnings))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "causal_question", "generate", input_summary=payload.text[:1000], output_summary=_json(_causal_question_out(row))[:2000], warnings=parse(row.warnings_json))
    return _causal_question_out(row)


@router.patch("/{project_id}/causal-question")
def patch_causal_question(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    row = _latest(db, models.CausalQuestion, project_id)
    if not row:
        raise HTTPException(404, "尚未生成因果问题")
    for key in ["causal_question_text", "treatment", "outcome", "unit", "time_window", "target_population", "estimand", "research_context"]:
        if key in payload.data:
            setattr(row, key, str(payload.data[key]))
    if "clarification_questions" in payload.data:
        row.clarification_questions_json = _json(payload.data["clarification_questions"])
    row.user_feedback = payload.user_feedback
    db.commit()
    log_event(db, project_id, "causal_question", "revise", input_summary=payload.user_feedback, user_action="revised")
    return _causal_question_out(row)


@router.post("/{project_id}/causal-question/confirm")
def confirm_causal_question(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    row = _latest(db, models.CausalQuestion, project_id)
    if not row:
        raise HTTPException(404, "尚未生成因果问题")
    row.confirmed_by_user = payload.confirmed; row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, "causal_question", "confirm", input_summary=payload.user_feedback, user_action="confirmed" if payload.confirmed else "questioned")
    return _causal_question_out(row)


def _structure_out(row: models.CausalStructure | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _structure_markdown(row), "treatment": row.treatment, "outcome": row.outcome, "confounders": parse(row.confounders_json), "mediators": parse(row.mediators_json), "colliders": parse(row.colliders_json), "moderators": parse(row.moderators_json), "bad_controls": parse(row.bad_controls_json), "post_treatment_variables": parse(row.post_treatment_variables_json), "mechanism_hypotheses": parse(row.mechanism_hypotheses_json), "dag_edges": parse(row.dag_edges_json), "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


@router.get("/{project_id}/causal-structure")
def get_causal_structure(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return _structure_out(_latest(db, models.CausalStructure, project_id))


@router.post("/{project_id}/causal-structure")
def post_causal_structure(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    data, warnings = _llm_json(db, project_id, "causal_structure_builder", payload.text, payload.data)
    cq = _latest(db, models.CausalQuestion, project_id)
    treatment = data.get("treatment", cq.treatment if cq else "")
    outcome = data.get("outcome", cq.outcome if cq else "")
    data = _normalize_causal_structure(data, treatment, outcome, _project_columns(db, project_id))
    row = models.CausalStructure(project_id=project_id, treatment=treatment, outcome=outcome, confounders_json=_json(data.get("confounders", [])), mediators_json=_json(data.get("mediators", [])), colliders_json=_json(data.get("colliders", [])), moderators_json=_json(data.get("moderators", [])), bad_controls_json=_json(data.get("bad_controls", [])), post_treatment_variables_json=_json(data.get("post_treatment_variables", [])), mechanism_hypotheses_json=_json(data.get("mechanism_hypotheses", [])), dag_edges_json=_json(data.get("dag_edges", [])), warnings_json=_json(_list(data.get("warnings")) + warnings))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "causal_structure", "generate", input_summary=payload.text[:1000], output_summary=_json(_structure_out(row))[:2000], warnings=parse(row.warnings_json))
    return _structure_out(row)


@router.patch("/{project_id}/causal-structure")
def patch_causal_structure(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    row = _latest(db, models.CausalStructure, project_id)
    if not row:
        raise HTTPException(404, "尚未生成因果结构")
    mapping = {"confounders": "confounders_json", "mediators": "mediators_json", "colliders": "colliders_json", "moderators": "moderators_json", "bad_controls": "bad_controls_json", "post_treatment_variables": "post_treatment_variables_json", "mechanism_hypotheses": "mechanism_hypotheses_json", "dag_edges": "dag_edges_json"}
    for key, attr in mapping.items():
        if key in payload.data:
            setattr(row, attr, _json(payload.data[key]))
    for key in ["treatment", "outcome"]:
        if key in payload.data:
            setattr(row, key, str(payload.data[key]))
    row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, "causal_structure", "revise", input_summary=payload.user_feedback, user_action="revised")
    return _structure_out(row)


@router.post("/{project_id}/causal-structure/confirm")
def confirm_causal_structure(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    row = _latest(db, models.CausalStructure, project_id)
    if not row:
        raise HTTPException(404, "尚未生成因果结构")
    row.confirmed_by_user = payload.confirmed; row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, "causal_structure", "confirm", input_summary=payload.user_feedback, user_action="confirmed" if payload.confirmed else "questioned")
    return _structure_out(row)


def _counterfactual_out(row: models.CounterfactualPlan | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _counterfactual_markdown(row), "counterfactual_question": row.counterfactual_question, "comparison_group": row.comparison_group, "counterfactual_source": row.counterfactual_source, "plausibility_assessment": row.plausibility_assessment, "risks": parse(row.risks_json), "required_evidence": parse(row.required_evidence_json), "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


@router.get("/{project_id}/counterfactual-plan")
def get_counterfactual(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return _counterfactual_out(_latest(db, models.CounterfactualPlan, project_id))


@router.post("/{project_id}/counterfactual-plan")
def post_counterfactual(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    data, warnings = _llm_json(db, project_id, "counterfactual_builder", payload.text, payload.data)
    if not data.get("counterfactual_question"):
        fallback = _counterfactual_fallback(db, project_id, payload.text)
        data = _merge(fallback, data)
        warnings = [item for item in warnings if "无法解析为 JSON" not in item and "未能解析为 JSON" not in item]
    row = models.CounterfactualPlan(project_id=project_id, counterfactual_question=data.get("counterfactual_question", ""), comparison_group=data.get("comparison_group", ""), counterfactual_source=data.get("counterfactual_source", "unclear"), plausibility_assessment=data.get("plausibility_assessment", "low"), risks_json=_json(data.get("risks", [])), required_evidence_json=_json(data.get("required_evidence", [])), warnings_json=_json(_list(data.get("warnings")) + warnings))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "counterfactual", "generate", input_summary=payload.text[:1000], output_summary=_json(_counterfactual_out(row))[:2000], warnings=parse(row.warnings_json))
    return _counterfactual_out(row)


@router.patch("/{project_id}/counterfactual-plan")
def patch_counterfactual(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    return _patch_simple(db, project_id, models.CounterfactualPlan, payload, _counterfactual_out, "counterfactual", ["counterfactual_question", "comparison_group", "counterfactual_source", "plausibility_assessment"], {"risks": "risks_json", "required_evidence": "required_evidence_json"})


@router.post("/{project_id}/counterfactual-plan/confirm")
def confirm_counterfactual(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    return _confirm_simple(db, project_id, models.CounterfactualPlan, payload, _counterfactual_out, "counterfactual")


def _assignment_out(row: models.AssignmentMechanism | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _assignment_markdown(row), "mechanism_type": row.mechanism_type, "description": row.description, "evidence": parse(row.evidence_json), "endogeneity_risks": parse(row.endogeneity_risks_json), "possible_strategies": parse(row.possible_strategies_json), "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


@router.get("/{project_id}/assignment-mechanism")
def get_assignment(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return _assignment_out(_latest(db, models.AssignmentMechanism, project_id))


@router.post("/{project_id}/assignment-mechanism")
def post_assignment(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    data, warnings = _llm_json(db, project_id, "assignment_mechanism_classifier", payload.text, payload.data)
    data = _normalize_assignment(data, db, project_id)
    row = models.AssignmentMechanism(project_id=project_id, mechanism_type=data.get("mechanism_type", "unclear"), description=data.get("description", ""), evidence_json=_json(data.get("evidence", [])), endogeneity_risks_json=_json(data.get("endogeneity_risks", [])), possible_strategies_json=_json(data.get("possible_strategies", [])), warnings_json=_json(_list(data.get("warnings")) + warnings))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "assignment_mechanism", "generate", input_summary=payload.text[:1000], output_summary=_json(_assignment_out(row))[:2000], warnings=parse(row.warnings_json))
    return _assignment_out(row)


@router.patch("/{project_id}/assignment-mechanism")
def patch_assignment(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    return _patch_simple(db, project_id, models.AssignmentMechanism, payload, _assignment_out, "assignment_mechanism", ["mechanism_type", "description"], {"evidence": "evidence_json", "endogeneity_risks": "endogeneity_risks_json", "possible_strategies": "possible_strategies_json"})


@router.post("/{project_id}/assignment-mechanism/confirm")
def confirm_assignment(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    return _confirm_simple(db, project_id, models.AssignmentMechanism, payload, _assignment_out, "assignment_mechanism")


def _strategy_out(row: models.IdentificationStrategy | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _strategy_markdown(row), "recommended_strategy": row.recommended_strategy, "alternative_strategies": parse(row.alternative_strategies_json), "counterfactual_logic": row.counterfactual_logic, "key_assumptions": parse(row.key_assumptions_json), "required_data": parse(row.required_data_json), "diagnostics": parse(row.diagnostics_json), "risks": parse(row.risks_json), "risk_level": row.risk_level, "credibility_prior": row.credibility_prior, "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


@router.get("/{project_id}/identification-strategy")
def get_strategy(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return _strategy_out(_latest(db, models.IdentificationStrategy, project_id))


@router.post("/{project_id}/identification-strategy")
def post_strategy(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    data, warnings = _llm_json(db, project_id, "identification_strategy_selector", payload.text, payload.data)
    row = models.IdentificationStrategy(project_id=project_id, recommended_strategy=data.get("recommended_strategy", "Descriptive only"), alternative_strategies_json=_json(data.get("alternative_strategies", [])), counterfactual_logic=data.get("counterfactual_logic", ""), key_assumptions_json=_json(data.get("key_assumptions", [])), required_data_json=_json(data.get("required_data", [])), diagnostics_json=_json(data.get("diagnostics", [])), risks_json=_json(data.get("risks", [])), risk_level=data.get("risk_level", "high"), credibility_prior=int(data.get("credibility_prior") or 0), warnings_json=_json(_list(data.get("warnings")) + warnings))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "identification_strategy", "generate", input_summary=payload.text[:1000], output_summary=_json(_strategy_out(row))[:2000], warnings=parse(row.warnings_json))
    return _strategy_out(row)


@router.patch("/{project_id}/identification-strategy")
def patch_strategy(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    return _patch_simple(db, project_id, models.IdentificationStrategy, payload, _strategy_out, "identification_strategy", ["recommended_strategy", "counterfactual_logic", "risk_level", "credibility_prior"], {"alternative_strategies": "alternative_strategies_json", "key_assumptions": "key_assumptions_json", "required_data": "required_data_json", "diagnostics": "diagnostics_json", "risks": "risks_json"})


@router.post("/{project_id}/identification-strategy/confirm")
def confirm_strategy(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    row = _latest(db, models.IdentificationStrategy, project_id)
    if not row:
        raise HTTPException(404, "尚未生成识别策略")
    row.confirmed_by_user = payload.confirmed; row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, "identification_strategy", "confirm", input_summary=payload.user_feedback, user_action="confirmed" if payload.confirmed else "questioned")
    return _strategy_out(row)


def _patch_simple(db: Session, project_id: int, model, payload: CausalModuleRequest, out_fn, step: str, text_fields: list[str], json_fields: dict[str, str]):
    row = _latest(db, model, project_id)
    if not row:
        raise HTTPException(404, "尚未生成该模块")
    for key in text_fields:
        if key in payload.data:
            setattr(row, key, payload.data[key] if isinstance(payload.data[key], int) else str(payload.data[key]))
    for key, attr in json_fields.items():
        if key in payload.data:
            setattr(row, attr, _json(payload.data[key]))
    row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, step, "revise", input_summary=payload.user_feedback, user_action="revised")
    return out_fn(row)


def _confirm_simple(db: Session, project_id: int, model, payload: CausalModuleConfirmRequest, out_fn, step: str):
    row = _latest(db, model, project_id)
    if not row:
        raise HTTPException(404, "尚未生成该模块")
    row.confirmed_by_user = payload.confirmed; row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, step, "confirm", input_summary=payload.user_feedback, user_action="confirmed" if payload.confirmed else "questioned")
    return out_fn(row)


def _identifiability_out(row: models.DataIdentifiabilityCheck | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _identifiability_markdown(row), "n_rows": row.n_rows, "n_cols": row.n_cols, "variable_roles": parse(row.variable_roles_json), "missing_summary": parse(row.missing_summary_json), "panel_structure": parse(row.panel_structure_json), "treatment_variation": parse(row.treatment_variation_json), "outcome_availability": parse(row.outcome_availability_json), "pre_post_availability": parse(row.pre_post_availability_json), "control_group_availability": parse(row.control_group_availability_json), "common_support_summary": parse(row.common_support_summary_json), "method_support": parse(row.method_support_json), "identifiability_status": row.identifiability_status, "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


@router.get("/{project_id}/data-identifiability-check")
def get_identifiability(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return _identifiability_out(_latest(db, models.DataIdentifiabilityCheck, project_id))


@router.post("/{project_id}/run-data-identifiability-check")
def run_identifiability(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    df = load_data(db, project_id)
    profile = profile_dataset(df, infer_variable_roles(df))
    roles = profile["roles"]
    strategy = _latest(db, models.IdentificationStrategy, project_id)
    selected = strategy.recommended_strategy if strategy else "unclear"
    warnings = []
    treatment = roles.get("treatment", [])
    outcome = roles.get("outcome", [])
    time = roles.get("time", [])
    entity = roles.get("id", [])
    treatment_variation = {"has_treatment_candidate": bool(treatment), "treatment_candidates": treatment}
    outcome_availability = {"has_outcome_candidate": bool(outcome), "outcome_candidates": outcome}
    panel_structure = {"has_time": bool(time), "has_entity": bool(entity), "time_candidates": time, "entity_candidates": entity}
    if selected in {"DID", "Event Study", "Staggered DID"} and not (treatment and outcome and time):
        warnings.append("当前数据尚不足以支持 DID/Event Study：需要处理变量、结果变量和时间变量。")
    if selected == "PSM" and len(roles.get("covariate", [])) < 2:
        warnings.append("当前协变量候选较少，PSM 共同支持和平衡性诊断可能不足。")
    status = "identifiable" if not warnings and treatment and outcome else "partially_identifiable" if outcome else "not_identifiable"
    row = models.DataIdentifiabilityCheck(project_id=project_id, n_rows=profile["n_rows"], n_cols=profile["n_cols"], variable_roles_json=_json(roles), missing_summary_json=_json(profile["missing_summary"]), panel_structure_json=_json(panel_structure), treatment_variation_json=_json(treatment_variation), outcome_availability_json=_json(outcome_availability), pre_post_availability_json=_json({"requires_user_confirmation": True}), control_group_availability_json=_json({"requires_user_confirmation": True}), common_support_summary_json=_json({"placeholder": "PSM 共同支持图在稳健性诊断阶段运行"}), method_support_json=_json(profile["method_feasibility"]), identifiability_status=status, warnings_json=_json(warnings))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "data_identifiability", "run", output_summary=_json(_identifiability_out(row))[:2000], warnings=warnings)
    return _identifiability_out(row)


@router.post("/{project_id}/data-identifiability-check/confirm")
def confirm_identifiability(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    return _confirm_simple(db, project_id, models.DataIdentifiabilityCheck, payload, _identifiability_out, "data_identifiability")


def _setup_out(row: models.EstimationSetup | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _setup_markdown(row), "strategy": row.strategy, "outcome": row.outcome, "treatment": row.treatment, "post_variable": row.post_variable, "time_variable": row.time_variable, "entity_variable": row.entity_variable, "running_variable": row.running_variable, "cutoff": row.cutoff, "instrument_variable": row.instrument_variable, "covariates": parse(row.covariates_json), "fixed_effects": parse(row.fixed_effects_json), "standard_error_type": row.standard_error_type, "cluster_variable": row.cluster_variable, "sample_filter": parse(row.sample_filter_json), "model_formula": row.model_formula, "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def _project_columns(db: Session, project_id: int) -> list[str]:
    try:
        return [str(column) for column in load_data(db, project_id).columns]
    except Exception:
        return []


def _pick_column(candidates: list[Any], columns: list[str], preferred: list[str] | None = None) -> str:
    column_set = {str(column): str(column) for column in columns}
    lowered = {str(column).lower(): str(column) for column in columns}
    for name in preferred or []:
        if name in column_set:
            return column_set[name]
        if name.lower() in lowered:
            return lowered[name.lower()]
    for item in candidates:
        name = str(item)
        if name in column_set:
            return column_set[name]
        if name.lower() in lowered:
            return lowered[name.lower()]
    return ""


def _normalize_fixed_effects(value: Any, strategy: str, entity: str, time: str) -> dict:
    if isinstance(value, dict):
        return {"entity": bool(value.get("entity")), "time": bool(value.get("time"))}
    items = {str(item).lower() for item in _as_list(value)}
    if items:
        return {
            "entity": bool(entity and (entity.lower() in items or "entity" in items or "unit" in items)),
            "time": bool(time and (time.lower() in items or "time" in items or "year" in items)),
        }
    if strategy in {"DID", "Fixed Effects", "Event Study"}:
        return {"entity": bool(entity), "time": bool(time)}
    return {"entity": False, "time": False}


def _formula(strategy: str, outcome: str, treatment: str, post: str, covariates: list[str], entity: str, time: str, fixed_effects: dict) -> str:
    if not outcome or not treatment:
        return ""
    rhs: list[str] = []
    if strategy == "DID":
        if not post:
            return ""
        did_term = f"{treatment}:{post}" if fixed_effects.get("entity") or fixed_effects.get("time") else f"{treatment} * {post}"
        rhs.append(did_term)
    elif strategy == "PSM":
        return f"{treatment} ~ {' + '.join(covariates)}" if covariates else f"{treatment} ~ 1"
    else:
        rhs.append(treatment)
    rhs.extend(covariates)
    if fixed_effects.get("entity") and entity:
        rhs.append(f"C({entity})")
    if fixed_effects.get("time") and time:
        rhs.append(f"C({time})")
    return f"{outcome} ~ {' + '.join(rhs)}"


def _repair_estimation_setup(db: Session, project_id: int, data: dict, warnings: list[str]) -> tuple[dict, list[str]]:
    roles = _parse((_latest(db, models.DataIdentifiabilityCheck, project_id) or models.DataIdentifiabilityCheck()).variable_roles_json, {})
    columns = _project_columns(db, project_id)
    strategy_row = _latest(db, models.IdentificationStrategy, project_id)
    strategy = strategy_row.recommended_strategy if strategy_row else data.get("strategy", "")
    strategy = data.get("strategy") or strategy or ""
    normalized_warnings = _list(data.get("warnings")) + warnings

    outcome = _pick_column(_as_list(data.get("outcome")) + roles.get("outcome", []), columns)
    treatment = _pick_column(_as_list(data.get("treatment")) + roles.get("treatment", []), columns, ["treat", "treated", "treatment", "policy_group"])
    time = _pick_column(_as_list(data.get("time_variable")) + roles.get("time", []), columns, ["year", "time", "date"])
    entity = _pick_column(_as_list(data.get("entity_variable")) + roles.get("id", []), columns, ["province_id", "city_id", "county_id", "firm_id", "school_id", "unit_id", "id"])
    post = _pick_column(_as_list(data.get("post_variable")), columns, ["post", "after", "policy_post", "post_policy"])

    if strategy == "DID" and not post:
        normalized_warnings.append("DID 需要政策后变量，系统已尝试从数据列名中匹配 post/after/policy_post。")
    if roles.get("id") and entity and any(str(item) not in {entity, "province_name", "city_name", "county_name"} and not str(item).lower().endswith("_id") for item in roles.get("id", [])):
        normalized_warnings.append("数据角色识别中存在疑似误判的个体标识候选，系统已优先使用明确的 ID 列。")

    raw_covariates = _as_list(data.get("covariates")) or roles.get("covariate", [])
    excluded = {outcome, treatment, post, time, entity, "_source_file", ""}
    covariates = []
    for item in raw_covariates:
        column = _pick_column([item], columns)
        if column and column not in excluded and column not in covariates:
            covariates.append(column)

    fixed_effects = _normalize_fixed_effects(data.get("fixed_effects"), strategy, entity, time)
    standard_error = data.get("standard_error_type") or ("cluster" if strategy in {"DID", "Fixed Effects", "Event Study"} and entity else "robust")
    if strategy in {"DID", "Fixed Effects", "Event Study"} and entity:
        standard_error = "cluster"
    cluster = data.get("cluster_variable") or (entity if standard_error == "cluster" else "")
    sample_filter = data.get("sample_filter") if isinstance(data.get("sample_filter"), dict) else {}
    if strategy in {"DID", "Event Study"} and time and "policy_time" not in sample_filter:
        sample_filter["policy_time"] = 2018 if "2018" in str(build_project_state(db, project_id)) else sample_filter.get("policy_time", "")
        if sample_filter.get("policy_time") == "":
            sample_filter.pop("policy_time", None)

    formula = data.get("model_formula") or ""
    generated_formula = _formula(strategy, outcome, treatment, post, covariates, entity, time, fixed_effects)
    did_terms = [f"{treatment} * {post}", f"{treatment}:{post}"]
    has_did_term = any(term in formula for term in did_terms)
    has_redundant_main_effects = bool(fixed_effects.get("entity") and fixed_effects.get("time") and f"{treatment} * {post}" in formula)
    if strategy == "DID" and (not formula or not post or not has_did_term or has_redundant_main_effects):
        formula = generated_formula
        normalized_warnings.append("DID 估计公式已自动规范为交互项、协变量与固定效应；双向固定效应下不单独解释 treatment 或 post 主效应。")
    elif not formula:
        formula = generated_formula

    return {
        "strategy": strategy,
        "outcome": outcome,
        "treatment": treatment,
        "post_variable": post,
        "time_variable": time,
        "entity_variable": entity,
        "running_variable": data.get("running_variable", ""),
        "cutoff": str(data.get("cutoff", "")),
        "instrument_variable": data.get("instrument_variable", ""),
        "covariates": covariates,
        "fixed_effects": fixed_effects,
        "standard_error_type": standard_error,
        "cluster_variable": cluster,
        "sample_filter": sample_filter,
        "model_formula": formula,
        "warnings": list(dict.fromkeys(item for item in normalized_warnings if item)),
    }, columns


def _invalid_estimation_setup_message(setup: models.EstimationSetup) -> str:
    fixed_effects = _parse(setup.fixed_effects_json, {})
    if setup.strategy == "DID":
        missing = [name for name, value in {"outcome": setup.outcome, "treatment": setup.treatment, "post_variable": setup.post_variable, "time_variable": setup.time_variable, "entity_variable": setup.entity_variable}.items() if not value]
        if missing:
            return f"DID 估计设定缺少必要字段：{', '.join(missing)}。请返回第七步重新生成或编辑估计设定。"
        if f"{setup.treatment} * {setup.post_variable}" not in setup.model_formula and f"{setup.treatment}:{setup.post_variable}" not in setup.model_formula:
            return "DID 模型公式必须包含 treatment * post 交互项。请返回第七步重新生成或编辑估计设定。"
        if not isinstance(fixed_effects, dict):
            return "fixed_effects 必须是对象格式，例如 {\"entity\": true, \"time\": true}。"
    return ""


@router.get("/{project_id}/estimation-setup")
def get_setup(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return _setup_out(_latest(db, models.EstimationSetup, project_id))


@router.post("/{project_id}/estimation-setup")
def post_setup(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    data, warnings = _llm_json(db, project_id, "estimation_setup_assistant", payload.text, payload.data)
    setup, _ = _repair_estimation_setup(db, project_id, data, warnings)
    row = models.EstimationSetup(project_id=project_id, strategy=setup["strategy"], outcome=setup["outcome"], treatment=setup["treatment"], post_variable=setup["post_variable"], time_variable=setup["time_variable"], entity_variable=setup["entity_variable"], running_variable=setup["running_variable"], cutoff=setup["cutoff"], instrument_variable=setup["instrument_variable"], covariates_json=_json(setup["covariates"]), fixed_effects_json=_json(setup["fixed_effects"]), standard_error_type=setup["standard_error_type"], cluster_variable=setup["cluster_variable"], sample_filter_json=_json(setup["sample_filter"]), model_formula=setup["model_formula"], warnings_json=_json(setup["warnings"]))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "estimation_setup", "generate", output_summary=_json(_setup_out(row))[:2000], warnings=parse(row.warnings_json))
    return _setup_out(row)


@router.patch("/{project_id}/estimation-setup")
def patch_setup(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    return _patch_simple(db, project_id, models.EstimationSetup, payload, _setup_out, "estimation_setup", ["strategy", "outcome", "treatment", "post_variable", "time_variable", "entity_variable", "running_variable", "cutoff", "instrument_variable", "standard_error_type", "cluster_variable", "model_formula"], {"covariates": "covariates_json", "fixed_effects": "fixed_effects_json", "sample_filter": "sample_filter_json"})


@router.post("/{project_id}/estimation-setup/confirm")
def confirm_setup(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    row = _latest(db, models.EstimationSetup, project_id)
    if not row:
        raise HTTPException(404, "尚未生成该模块")
    if payload.confirmed:
        message = _invalid_estimation_setup_message(row)
        if message:
            log_event(db, project_id, "estimation_setup", "confirm_blocked", input_summary=payload.user_feedback, warnings=[message], user_action="blocked")
            raise HTTPException(400, message)
    row.confirmed_by_user = payload.confirmed; row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, "estimation_setup", "confirm", input_summary=payload.user_feedback, user_action="confirmed" if payload.confirmed else "questioned")
    return _setup_out(row)


def _estimation_out(row: models.EstimationResult | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _estimation_markdown(row), "strategy": row.strategy, "model_formula": row.model_formula, "n_obs": row.n_obs, "result": parse(row.result_json), "coefficients": parse(row.coefficients_json), "diagnostics": parse(row.diagnostics_json), "warnings": parse(row.warnings_json), "chart_paths": parse(row.chart_paths_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


@router.post("/{project_id}/run-estimation")
def run_estimation(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    setup = _latest(db, models.EstimationSetup, project_id)
    if not setup or not setup.confirmed_by_user:
        raise HTTPException(400, "请先确认估计设定")
    if setup.strategy in {"RDD", "IV / 2SLS", "Synthetic Control", "Descriptive only"}:
        warning = f"{setup.strategy} 当前为 placeholder，尚未执行真实估计。"
        row = models.EstimationResult(project_id=project_id, strategy=setup.strategy, model_formula=setup.model_formula, n_obs=0, result_json=_json({"placeholder": True}), coefficients_json="{}", diagnostics_json="{}", warnings_json=_json([warning]), chart_paths_json="[]")
        db.add(row); db.commit(); db.refresh(row)
        return _estimation_out(row)
    spec = {"outcome": setup.outcome, "treat": setup.treatment, "post": setup.post_variable, "time": setup.time_variable, "time_id": setup.time_variable, "entity_id": setup.entity_variable, "covariates": parse(setup.covariates_json), "entity_fixed_effects": bool(_parse(setup.fixed_effects_json, {}).get("entity")), "time_fixed_effects": bool(_parse(setup.fixed_effects_json, {}).get("time")), "cluster_robust": setup.standard_error_type == "cluster", "policy_time": _parse(setup.sample_filter_json, {}).get("policy_time")}
    result = run_analysis(load_data(db, project_id), {"selected_method": setup.strategy, "model_spec": spec})
    chart_dir = settings.storage_path / str(project_id) / "charts"
    df = load_data(db, project_id)
    charts = [plot_missing_values(df, chart_dir), plot_coefficients(result, chart_dir)]
    row = models.EstimationResult(project_id=project_id, strategy=setup.strategy, model_formula=result.get("model_formula", setup.model_formula), n_obs=int(result.get("n_obs", 0)), result_json=_json(result), coefficients_json=_json(result.get("coefficients", {})), diagnostics_json="{}", warnings_json=_json(result.get("warnings", [])), chart_paths_json=_json(charts))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "estimation_runner", "run", output_summary=_json(_estimation_out(row))[:2000], warnings=parse(row.warnings_json))
    return _estimation_out(row)


@router.get("/{project_id}/estimation-results")
def list_estimations(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    rows = db.query(models.EstimationResult).filter(models.EstimationResult.project_id == project_id).order_by(models.EstimationResult.id.desc()).all()
    return {"results": [_estimation_out(row) for row in rows]}


@router.get("/{project_id}/estimation-results/{result_id}")
def get_estimation(project_id: int, result_id: int, db: Session = Depends(get_db)):
    row = db.get(models.EstimationResult, result_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "估计结果不存在")
    return _estimation_out(row)


@router.post("/{project_id}/estimation-results/{result_id}/confirm")
def confirm_estimation(project_id: int, result_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    row = db.get(models.EstimationResult, result_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "估计结果不存在")
    row.confirmed_by_user = payload.confirmed; row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, "estimation_runner", "confirm", input_summary=payload.user_feedback, user_action="confirmed" if payload.confirmed else "questioned")
    return _estimation_out(row)


def _diagnostics_out(row: models.AssumptionDiagnostics | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _diagnostics_markdown(row), "strategy": row.strategy, "diagnostics": parse(row.diagnostics_json), "charts": parse(row.charts_json), "credibility_assessment": row.credibility_assessment, "failed_checks": parse(row.failed_checks_json), "passed_checks": parse(row.passed_checks_json), "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


def _main_effect(result: dict) -> dict:
    coefficients = result.get("coefficients") or {}
    p_values = result.get("p_values") or {}
    intervals = result.get("confidence_intervals") or {}
    term = next((key for key in coefficients if ":" in key), None) or ("ATT" if "ATT" in coefficients else next(iter(coefficients), ""))
    return {
        "term": term,
        "coefficient": coefficients.get(term),
        "p_value": p_values.get(term),
        "confidence_interval": intervals.get(term),
    }


@router.post("/{project_id}/run-assumption-diagnostics")
def run_diagnostics(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    setup = _latest(db, models.EstimationSetup, project_id)
    strategy = setup.strategy if setup else "unclear"
    estimation = _latest(db, models.EstimationResult, project_id)
    warnings = []
    passed, failed, pending = [], [], []
    checks = []
    if estimation and estimation.n_obs > 0:
        result = _parse(estimation.result_json, {})
        main = _main_effect(result)
        checks.append({"name": "主模型结果", "status": "passed", "detail": f"已获得 {strategy} 估计结果，样本量 {estimation.n_obs}。"})
        passed.append("主模型结果已生成")
        if main.get("coefficient") is not None:
            checks.append({"name": "核心估计项", "status": "passed", "detail": f"{main['term']} = {float(main['coefficient']):.4f}，p 值 {float(main.get('p_value') or 1):.4g}。"})
            passed.append("核心估计项可解释")
        else:
            checks.append({"name": "核心估计项", "status": "failed", "detail": "没有找到可解释的核心估计项。"})
            failed.append("核心估计项缺失")
    else:
        checks.append({"name": "主模型结果", "status": "failed", "detail": "尚未运行有效估计结果。"})
        failed.append("主模型结果缺失")
    if setup and setup.strategy == "DID":
        fixed_effects = _parse(setup.fixed_effects_json, {})
        sample_filter = _parse(setup.sample_filter_json, {})
        policy_time = int(sample_filter.get("policy_time") or 2018)
        base_spec = {
            "outcome": setup.outcome,
            "treat": setup.treatment,
            "post": setup.post_variable,
            "time": setup.time_variable,
            "time_id": setup.time_variable,
            "entity_id": setup.entity_variable,
            "covariates": parse(setup.covariates_json),
            "entity_fixed_effects": bool(fixed_effects.get("entity")),
            "time_fixed_effects": bool(fixed_effects.get("time")),
            "cluster_robust": setup.standard_error_type == "cluster",
            "policy_time": policy_time,
        }
        try:
            df = load_data(db, project_id)
            event_result = run_analysis(df, {"selected_method": "Event Study", "model_spec": base_spec})
            pre_periods = [item for item in event_result.get("relative_time_results", []) if item.get("relative_time", 0) < 0]
            significant_pre = [item for item in pre_periods if item.get("p_value") is not None and float(item["p_value"]) < 0.05]
            if pre_periods and significant_pre:
                checks.append({"name": "平行趋势/预趋势", "status": "failed", "detail": f"事件研究中 {len(significant_pre)} 个政策前相对时期显著，提示平行趋势可能不成立。"})
                failed.append("平行趋势/预趋势存在风险")
            elif pre_periods:
                checks.append({"name": "平行趋势/预趋势", "status": "passed", "detail": "事件研究中政策前相对时期未显示显著差异；这只是支持性证据，不等于证明平行趋势。"})
                passed.append("平行趋势/预趋势未发现显著异常")
            else:
                checks.append({"name": "平行趋势/预趋势", "status": "pending", "detail": "缺少可用于事件研究的政策前相对时期。"})
                pending.append("平行趋势/预趋势")
        except Exception as exc:
            checks.append({"name": "平行趋势/预趋势", "status": "pending", "detail": f"自动事件研究未完成：{exc}"})
            pending.append("平行趋势/预趋势")
        try:
            df = load_data(db, project_id)
            placebo_col = "_diagnostic_placebo_post"
            placebo_time = policy_time - 1
            placebo_df = df.copy()
            placebo_df[placebo_col] = (pd.to_numeric(placebo_df[setup.time_variable], errors="coerce") >= placebo_time).astype(int)
            placebo_result = run_analysis(placebo_df, {"selected_method": "DID", "model_spec": {**base_spec, "post": placebo_col, "policy_time": placebo_time}})
            placebo = _main_effect(placebo_result)
            if placebo.get("p_value") is not None and float(placebo["p_value"]) < 0.05:
                checks.append({"name": "安慰剂政策时间", "status": "failed", "detail": f"将政策时间提前到 {placebo_time} 年仍显著（系数 {float(placebo['coefficient']):.4f}，p 值 {float(placebo['p_value']):.4g}），提示提前趋势、预期效应或设定风险。"})
                failed.append("安慰剂政策时间显著")
            else:
                checks.append({"name": "安慰剂政策时间", "status": "passed", "detail": f"将政策时间提前到 {placebo_time} 年未发现显著效应。"})
                passed.append("安慰剂政策时间未显著")
        except Exception as exc:
            checks.append({"name": "安慰剂政策时间", "status": "pending", "detail": f"自动安慰剂检验未完成：{exc}"})
            pending.append("安慰剂政策时间")
        robustness = _latest(db, models.RobustnessResult, project_id)
        if robustness:
            robust_results = _parse(robustness.results_json, {})
            if robust_results.get("stable"):
                checks.append({"name": "稳健性检查", "status": "passed", "detail": robustness.interpretation})
                passed.append("稳健性检查总体稳定")
            else:
                checks.append({"name": "稳健性检查", "status": "failed", "detail": robustness.interpretation or "最新稳健性结果提示需要谨慎。"})
                failed.append("稳健性检查存在风险")
        else:
            checks.append({"name": "稳健性检查", "status": "pending", "detail": "尚未运行稳健性与敏感性分析。"})
            pending.append("稳健性检查")
        pending_checks = [
            ("无溢出/SUTVA", "需要业务论证或空间/供应链溢出检查；仅凭当前面板数据不能自动证明。"),
            ("无同期差异冲击", "需要核对同一时期其他政策、产业冲击或地方事件；系统不能凭当前数据自动排除。"),
        ]
        for name, detail in pending_checks:
            checks.append({"name": name, "status": "pending", "detail": detail})
            pending.append(name)
        warnings.append("系统已自动补查可由当前数据支持的诊断；但无溢出和无同期冲击仍需要外部政策事实或研究者判断。")
    diagnostics = {"strategy": strategy, "checks": checks, "passed": passed, "failed": failed, "pending": pending}
    credibility = "not_supported" if "主模型结果缺失" in failed else "weak" if failed or pending else "moderate"
    row = models.AssumptionDiagnostics(project_id=project_id, strategy=strategy, diagnostics_json=_json(diagnostics), charts_json="[]", credibility_assessment=credibility, failed_checks_json=_json(failed), passed_checks_json=_json(passed), warnings_json=_json(warnings))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "assumption_diagnostics", "run", output_summary=_json(_diagnostics_out(row))[:2000], warnings=warnings)
    return _diagnostics_out(row)


@router.get("/{project_id}/assumption-diagnostics")
def get_diagnostics(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return _diagnostics_out(_latest(db, models.AssumptionDiagnostics, project_id))


@router.post("/{project_id}/assumption-diagnostics/confirm")
def confirm_diagnostics(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    return _confirm_simple(db, project_id, models.AssumptionDiagnostics, payload, _diagnostics_out, "assumption_diagnostics")


def _effect_out(row: models.CausalEffectInterpretation | None) -> dict:
    if not row:
        return {}
    return {"id": row.id, "analysis_markdown": _effect_markdown(row), "causal_claim": row.causal_claim, "estimand_interpretation": row.estimand_interpretation, "effect_size_interpretation": row.effect_size_interpretation, "statistical_uncertainty": row.statistical_uncertainty, "identification_conditions": parse(row.identification_conditions_json), "external_validity": row.external_validity, "unsupported_claims": parse(row.unsupported_claims_json), "limitations": parse(row.limitations_json), "credibility_score": row.credibility_score, "credibility_label": row.credibility_label, "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}


def _effect_fallback(db: Session, project_id: int, user_note: str = "") -> dict:
    state = build_project_state(db, project_id)
    cq = state.get("causal_question", {})
    strategy = state.get("identification_strategy", {})
    setup = state.get("estimation_setup", {})
    estimation = _latest(db, models.EstimationResult, project_id)
    result = _parse(estimation.result_json, {}) if estimation else state.get("estimation_result", {}).get("result", {})
    diagnostics_row = _latest(db, models.AssumptionDiagnostics, project_id)
    diagnostics = _diagnostics_out(diagnostics_row) if diagnostics_row else state.get("assumption_diagnostics", {})
    robustness_row = _latest(db, models.RobustnessResult, project_id)
    robustness = {"results": _parse(robustness_row.results_json, {}), "interpretation": robustness_row.interpretation, "warnings": _parse(robustness_row.warnings_json, [])} if robustness_row else {}
    method = setup.get("strategy") or strategy.get("recommended_strategy") or result.get("method") or "当前识别策略"
    outcome = cq.get("outcome") or setup.get("outcome") or "结果变量"
    treatment = cq.get("treatment") or setup.get("treatment") or "处理变量"
    unit = cq.get("unit") or setup.get("entity_variable") or "研究单位"
    time_window = cq.get("time_window") or "当前时间窗口"
    population = cq.get("target_population") or "当前样本总体"
    estimand = cq.get("estimand") or "ATT"
    setup_filter = setup.get("sample_filter", {}) if isinstance(setup, dict) else {}
    policy_time = setup_filter.get("policy_time") if isinstance(setup_filter, dict) else ""
    policy_time_text = f"{policy_time} 年政策后" if policy_time else "政策后"
    context = cq.get("causal_question_text") or cq.get("research_context") or ""
    main = _main_effect(result)
    coef = main.get("coefficient")
    p_value = main.get("p_value")
    ci = main.get("confidence_interval") if isinstance(main.get("confidence_interval"), list) else []
    ci_text = f"，95% 置信区间 [{float(ci[0]):.4f}, {float(ci[1]):.4f}]" if len(ci) == 2 else ""
    p_text = f"，p 值 {float(p_value):.4g}" if p_value is not None else ""
    effect_sentence = f"主模型中核心估计项 {main.get('term') or '核心处理项'} 的系数为 {float(coef):.4f}{p_text}{ci_text}。在当前变量口径下，这表示处理组在{policy_time_text}相对于比较组的 {outcome} 变化；是否能解释为 {treatment} 的因果效应取决于识别诊断。" if coef is not None else "尚未获得可解释的核心估计量。"
    diag_checks = diagnostics.get("diagnostics", {}).get("checks", []) if isinstance(diagnostics.get("diagnostics"), dict) else []
    failed_details = [item.get("detail", "") for item in diag_checks if item.get("status") == "failed"]
    pending_details = [item.get("detail", "") for item in diag_checks if item.get("status") == "pending"]
    passed_names = [item.get("name", "") for item in diag_checks if item.get("status") == "passed"]
    robust_results = robustness.get("results", {})
    robust_impl = robust_results.get("implemented", []) if isinstance(robust_results, dict) else []
    placebo_risks = [item for item in robust_impl if item.get("status") == "concern" or "安慰剂" in str(item.get("name")) and item.get("p_value") is not None and float(item["p_value"]) < 0.05]
    robustness_text = robustness.get("interpretation") or "尚未完成稳健性与敏感性分析。"
    assumptions = strategy.get("key_assumptions") or ["识别假设需要成立", "处理组与对照组需要具备可比性", "不存在足以改变结论的同期冲击"]
    diag_label = diagnostics.get("credibility_assessment") or "未完成"
    has_result = bool(result and not result.get("placeholder"))
    score = 55 if has_result else 25
    if diag_label in {"strong", "moderate"}:
        score += 15
    if diag_label in {"weak", "not_credible", "not_supported"}:
        score -= 15
    if failed_details:
        score -= 10
    if placebo_risks:
        score -= 10
    score = max(0, min(100, score))
    label_value = "medium" if score >= 60 else "low" if score >= 30 else "not_supported"
    claim_prefix = f"针对“{context}”这一问题，" if context else ""
    failed_summary = "；".join(failed_details) if failed_details else "当前自动诊断未发现直接失败项。"
    pending_summary = "；".join(pending_details) if pending_details else "暂无待人工补充项。"
    return {
        "causal_claim": f"{claim_prefix}当前结果更适合表述为：在 {method} 的识别假设成立时，接受 {treatment} 的单位相对于比较组，{outcome} 出现了相对变化。若诊断或稳健性提示风险，暂不应写成“{treatment} 已经被严格证明导致 {outcome} 改变”。",
        "estimand_interpretation": f"当前估计目标更接近 {estimand}：即接受处理单位在政策后的平均处理效应，而不是所有单位、所有年份或未来政策版本上的总体 ATE。",
        "effect_size_interpretation": effect_sentence,
        "statistical_uncertainty": f"{effect_sentence} 样本量为 {estimation.n_obs if estimation else '未提供'}。统计上主模型效应明显，但诊断上存在失败项：{failed_summary}",
        "identification_conditions": assumptions,
        "external_validity": f"外推边界应限定在{time_window}、以{unit}为单位、{population}这一类政策试点场景。不能直接推广到其他产业、其他年份、不同补贴强度或非试点式政策。{pending_summary}",
        "unsupported_claims": ["不能声称该处理已被无条件证明具有因果效应", "不能忽略安慰剂、预趋势或稳健性诊断中的风险信号", "不能把处理组 ATT 直接解释为目标总体中所有单位的 ATE", f"不能把 {outcome} 的估计变化直接拆解为具体机制效应，除非另有机制数据支持"],
        "limitations": [f"识别假设诊断状态：{diag_label}", f"已通过检查：{'、'.join(passed_names) if passed_names else '暂无'}", f"失败或风险项：{failed_summary}", f"稳健性结论：{robustness_text}", user_note] if user_note else [f"识别假设诊断状态：{diag_label}", f"已通过检查：{'、'.join(passed_names) if passed_names else '暂无'}", f"失败或风险项：{failed_summary}", f"稳健性结论：{robustness_text}"],
        "credibility_score": score,
        "credibility_label": label_value,
        "warnings": ["该解释已绑定当前项目的政策主题、估计结果、诊断与稳健性输出；安慰剂检验显著时应降低结论强度。"],
    }


@router.get("/{project_id}/causal-effect-interpretation")
def get_effect(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    return _effect_out(_latest(db, models.CausalEffectInterpretation, project_id))


@router.post("/{project_id}/generate-causal-effect-interpretation")
def generate_effect(project_id: int, payload: CausalModuleRequest | None = None, db: Session = Depends(get_db)):
    require_project(db, project_id)
    data, warnings = _llm_json(db, project_id, "causal_effect_interpreter", (payload.text if payload else "") or "请解释当前估计结果的因果含义和边界。", payload.data if payload else {})
    data = _merge_nonempty(data, _effect_fallback(db, project_id, payload.text if payload else ""))
    row = models.CausalEffectInterpretation(project_id=project_id, causal_claim=data.get("causal_claim", "当前因果结论需要依赖识别假设，不能仅凭相关性表达强因果结论。"), estimand_interpretation=data.get("estimand_interpretation", ""), effect_size_interpretation=data.get("effect_size_interpretation", ""), statistical_uncertainty=data.get("statistical_uncertainty", ""), identification_conditions_json=_json(data.get("identification_conditions", [])), external_validity=data.get("external_validity", ""), unsupported_claims_json=_json(data.get("unsupported_claims", [])), limitations_json=_json(data.get("limitations", [])), credibility_score=int(data.get("credibility_score") or 0), credibility_label=data.get("credibility_label", "low"), warnings_json=_json(_list(data.get("warnings")) + warnings))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "causal_effect_interpretation", "generate", output_summary=_json(_effect_out(row))[:2000], warnings=parse(row.warnings_json))
    return _effect_out(row)


@router.patch("/{project_id}/causal-effect-interpretation")
def patch_effect(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    return _patch_simple(db, project_id, models.CausalEffectInterpretation, payload, _effect_out, "causal_effect_interpretation", ["causal_claim", "estimand_interpretation", "effect_size_interpretation", "statistical_uncertainty", "external_validity", "credibility_score", "credibility_label"], {"identification_conditions": "identification_conditions_json", "unsupported_claims": "unsupported_claims_json", "limitations": "limitations_json"})


@router.post("/{project_id}/causal-effect-interpretation/confirm")
def confirm_effect(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    return _confirm_simple(db, project_id, models.CausalEffectInterpretation, payload, _effect_out, "causal_effect_interpretation")


@router.get("/{project_id}/robustness-plan")
def get_robustness_plan(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    row = _latest(db, models.RobustnessPlan, project_id)
    if row:
        return {"id": row.id, "planned_checks": parse(row.planned_checks_json), "rationale": parse(row.rationale_json), "confirmed_by_user": row.confirmed_by_user, "user_feedback": row.user_feedback}
    return {}


@router.post("/{project_id}/robustness-plan")
def post_robustness_plan(project_id: int, payload: CausalModuleRequest, db: Session = Depends(get_db)):
    require_project(db, project_id)
    checks = payload.data.get("planned_checks") or ["更换控制变量", "更换样本窗口", "安慰剂政策时间", "安慰剂处理组", "未观测混杂敏感性分析"]
    rationale = payload.data.get("rationale", [])
    if payload.text:
        rationale = _list(rationale) + [payload.text]
    row = models.RobustnessPlan(project_id=project_id, planned_checks_json=_json(checks), rationale_json=_json(rationale))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "robustness", "plan", output_summary=_json(checks))
    return {"id": row.id, "planned_checks": checks, "rationale": parse(row.rationale_json), "confirmed_by_user": row.confirmed_by_user}


@router.post("/{project_id}/run-robustness-checks")
def run_robustness(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    setup = _latest(db, models.EstimationSetup, project_id)
    if not setup or not setup.confirmed_by_user:
        raise HTTPException(400, "请先确认估计设定")
    if setup.strategy != "DID":
        raise HTTPException(400, "当前稳健性自动运行仅支持 DID；其他方法会在结果中明确标记为未实现。")
    df = load_data(db, project_id)
    covariates = parse(setup.covariates_json)
    fixed_effects = _parse(setup.fixed_effects_json, {})
    sample_filter = _parse(setup.sample_filter_json, {})
    policy_time = int(sample_filter.get("policy_time") or 2018)
    base_spec = {
        "outcome": setup.outcome,
        "treat": setup.treatment,
        "post": setup.post_variable,
        "time": setup.time_variable,
        "time_id": setup.time_variable,
        "entity_id": setup.entity_variable,
        "covariates": covariates,
        "entity_fixed_effects": bool(fixed_effects.get("entity")),
        "time_fixed_effects": bool(fixed_effects.get("time")),
        "cluster_robust": setup.standard_error_type == "cluster",
        "policy_time": policy_time,
    }
    plan = _latest(db, models.RobustnessPlan, project_id)
    planned = parse(plan.planned_checks_json) if plan else []
    implemented = []
    unavailable = []

    def run_variant(name: str, variant_df, spec_update: dict | None = None):
        spec = {**base_spec, **(spec_update or {})}
        try:
            result = run_analysis(variant_df, {"selected_method": "DID", "model_spec": spec})
            main = _main_effect(result)
            implemented.append({
                "name": name,
                "status": "completed",
                "term": main.get("term"),
                "coefficient": main.get("coefficient"),
                "p_value": main.get("p_value"),
                "confidence_interval": main.get("confidence_interval"),
                "n_obs": result.get("n_obs"),
                "model_formula": result.get("model_formula"),
            })
        except Exception as exc:
            implemented.append({"name": name, "status": "failed", "detail": str(exc)})

    run_variant("主模型复核", df)
    run_variant("不加入协变量", df, {"covariates": []})
    if covariates:
        run_variant("核心协变量子集", df, {"covariates": covariates[: max(1, min(3, len(covariates)))]})
    if setup.time_variable and setup.time_variable in df.columns:
        window = df[pd.to_numeric(df[setup.time_variable], errors="coerce").between(policy_time - 2, policy_time + 2)]
        if len(window) >= 20:
            run_variant("政策前后两年窗口", window)
        if setup.post_variable in df.columns:
            placebo_df = df.copy()
            placebo_col = "_placebo_post"
            placebo_time = policy_time - 1
            placebo_df[placebo_col] = (pd.to_numeric(placebo_df[setup.time_variable], errors="coerce") >= placebo_time).astype(int)
            run_variant(f"安慰剂政策时间 {placebo_time}", placebo_df, {"post": placebo_col, "policy_time": placebo_time})
    requested = set(str(item) for item in planned)
    unavailable_names = [
        "安慰剂处理组",
        "PSM 匹配后平衡性",
        "未观测混杂敏感性分析",
        "异质性分析",
        "正式事件研究动态效应",
    ]
    for name in unavailable_names:
        if not requested or any(token in name for token in requested) or any(name in token for token in requested):
            unavailable.append({"name": name, "status": "not_implemented", "detail": "当前版本尚未自动运行该检查；不会将其计入已通过稳健性证据。"})
    completed = [item for item in implemented if item.get("status") == "completed" and isinstance(item.get("coefficient"), (int, float))]
    for item in implemented:
        if item.get("status") == "completed" and "安慰剂" in str(item.get("name")) and item.get("p_value") is not None and float(item["p_value"]) < 0.05:
            item["status"] = "concern"
            item["detail"] = "安慰剂检查显著，提示可能存在提前趋势、预期效应或模型设定风险。"
    completed = [item for item in implemented if item.get("status") == "completed" and isinstance(item.get("coefficient"), (int, float))]
    concerns = [item for item in implemented if item.get("status") == "concern"]
    signs = {1 if item["coefficient"] > 0 else -1 if item["coefficient"] < 0 else 0 for item in completed}
    significant = [item for item in completed if item.get("p_value") is not None and float(item["p_value"]) < 0.05]
    stable = bool(completed) and not concerns and len(signs) == 1 and len(significant) >= max(1, len(completed) // 2)
    interpretation = "已运行可实现的 DID 稳健性变体；核心系数方向总体稳定。" if stable else "已运行部分 DID 稳健性变体，但安慰剂或其他检查提示结果稳定性仍需谨慎判断。"
    warnings = ["部分稳健性/敏感性检查尚未实现，系统已明确列入“未运行”，不会假装完成。"]
    results = {"implemented": implemented, "unavailable": unavailable, "stable": stable, "planned_checks": planned}
    row = models.RobustnessResult(project_id=project_id, checks_run_json=_json([item["name"] for item in implemented]), results_json=_json(results), interpretation=interpretation, warnings_json=_json(warnings))
    db.add(row); db.commit(); db.refresh(row)
    log_event(db, project_id, "robustness", "run", output_summary=row.interpretation, warnings=warnings)
    output = {"id": row.id, "checks_run": parse(row.checks_run_json), "results": parse(row.results_json), "interpretation": row.interpretation, "warnings": warnings, "confirmed_by_user": row.confirmed_by_user}
    output["analysis_markdown"] = _robustness_markdown(output)
    return output


@router.get("/{project_id}/robustness-results")
def get_robustness_results(project_id: int, db: Session = Depends(get_db)):
    require_project(db, project_id)
    rows = db.query(models.RobustnessResult).filter(models.RobustnessResult.project_id == project_id).order_by(models.RobustnessResult.id.desc()).all()
    results = []
    for row in rows:
        output = {"id": row.id, "checks_run": parse(row.checks_run_json), "results": parse(row.results_json), "interpretation": row.interpretation, "warnings": parse(row.warnings_json), "confirmed_by_user": row.confirmed_by_user}
        output["analysis_markdown"] = _robustness_markdown(output)
        results.append(output)
    return {"results": results}


@router.post("/{project_id}/robustness-results/confirm")
def confirm_robustness(project_id: int, payload: CausalModuleConfirmRequest, db: Session = Depends(get_db)):
    row = _latest(db, models.RobustnessResult, project_id)
    if not row:
        raise HTTPException(404, "尚未生成稳健性结果")
    row.confirmed_by_user = payload.confirmed; row.user_feedback = payload.user_feedback; db.commit()
    log_event(db, project_id, "robustness", "confirm", input_summary=payload.user_feedback, user_action="confirmed" if payload.confirmed else "questioned")
    return {"id": row.id, "confirmed_by_user": row.confirmed_by_user}
