from importlib import import_module
from sqlalchemy.orm import Session
from ..models import PromptTemplate

MODULES = [
    "research_design", "policy_understanding", "data_profiling", "cleaning_plan",
    "method_selection", "result_interpretation", "report_generation", "audit_summary",
    "causal_question_builder", "causal_structure_builder", "counterfactual_builder",
    "assignment_mechanism_classifier", "identification_strategy_selector",
    "data_identifiability_interpreter", "estimation_setup_assistant",
    "assumption_diagnostics_interpreter", "causal_effect_interpreter",
    "robustness_interpreter", "causal_report_generation",
]
FORMATS = {"research_design": "text", "policy_understanding": "json", "data_profiling": "json", "cleaning_plan": "json", "method_selection": "json", "result_interpretation": "text", "report_generation": "markdown", "audit_summary": "json", "causal_question_builder": "json", "causal_structure_builder": "json", "counterfactual_builder": "json", "assignment_mechanism_classifier": "json", "identification_strategy_selector": "json", "data_identifiability_interpreter": "json", "estimation_setup_assistant": "json", "assumption_diagnostics_interpreter": "json", "causal_effect_interpreter": "json", "robustness_interpreter": "json", "causal_report_generation": "markdown"}


def default_prompt(module_name: str) -> dict:
    if module_name not in MODULES:
        raise ValueError(f"未知 Prompt 模块: {module_name}")
    module = import_module(f"app.prompts.{module_name}_prompt")
    return {"module_name": module_name, "system_prompt": module.SYSTEM_PROMPT, "output_format": FORMATS[module_name], "version": 0, "is_default": True}


def get_prompt(db: Session, module_name: str) -> dict:
    row = db.query(PromptTemplate).filter(PromptTemplate.scope == "system", PromptTemplate.project_id.is_(None), PromptTemplate.module_name == module_name).order_by(PromptTemplate.version.desc()).first()
    if not row:
        return default_prompt(module_name)
    return {"id": row.id, "module_name": row.module_name, "system_prompt": row.system_prompt, "output_format": row.output_format, "version": row.version, "is_default": row.is_default, "updated_at": row.updated_at}


def list_prompts(db: Session) -> list[dict]:
    return [get_prompt(db, name) for name in MODULES]
