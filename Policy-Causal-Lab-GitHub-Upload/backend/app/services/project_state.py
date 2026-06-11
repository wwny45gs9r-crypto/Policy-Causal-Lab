import json
from sqlalchemy.orm import Session
from .. import models


def _parse(value: str, default):
    try:
        return json.loads(value)
    except Exception:
        return default


def _latest(db: Session, model, project_id: int):
    return db.query(model).filter(model.project_id == project_id).order_by(model.id.desc()).first()


def build_project_state(db: Session, project_id: int) -> dict:
    project = db.get(models.Project, project_id)
    files = db.query(models.UploadedFile).filter(models.UploadedFile.project_id == project_id).order_by(models.UploadedFile.id.asc()).all()
    profile = _latest(db, models.DataProfile, project_id)
    cleaning = _latest(db, models.CleaningPlan, project_id)
    method = _latest(db, models.MethodPlan, project_id)
    causal_question = _latest(db, models.CausalQuestion, project_id)
    causal_structure = _latest(db, models.CausalStructure, project_id)
    counterfactual = _latest(db, models.CounterfactualPlan, project_id)
    assignment = _latest(db, models.AssignmentMechanism, project_id)
    strategy = _latest(db, models.IdentificationStrategy, project_id)
    identifiability = _latest(db, models.DataIdentifiabilityCheck, project_id)
    estimation_setup = _latest(db, models.EstimationSetup, project_id)
    estimation_result = _latest(db, models.EstimationResult, project_id)
    diagnostics = _latest(db, models.AssumptionDiagnostics, project_id)
    effect = _latest(db, models.CausalEffectInterpretation, project_id)
    robustness = _latest(db, models.RobustnessResult, project_id)
    analysis = _latest(db, models.AnalysisResult, project_id)
    logs = db.query(models.AuditLog).filter(models.AuditLog.project_id == project_id).order_by(models.AuditLog.id.desc()).limit(40).all()
    brief = db.query(models.ResearchBrief).filter(models.ResearchBrief.project_id == project_id).order_by(models.ResearchBrief.id.desc()).first()
    profile_extra = _parse(profile.method_feasibility_json, {}) if profile else {}
    return {
        "project": {"id": project.id, "name": project.name, "description": project.description, "status": project.status} if project else {},
        "files": [{"id": item.id, "filename": item.filename, "file_type": item.file_type} for item in files],
        "research_brief": {
            "policy_name": brief.policy_name,
            "research_question": brief.research_question,
            "research_objective": brief.research_objective,
            "treatment_definition": brief.treatment_definition,
            "control_definition": brief.control_definition,
            "time_window": brief.time_window,
            "outcome_variables": _parse(brief.outcome_variables, []),
            "covariates": _parse(brief.covariates, []),
            "hypotheses": _parse(brief.hypotheses, []),
            "identification_strategy_notes": brief.identification_strategy_notes,
        } if brief else {},
        "data_profile": {
            "n_rows": profile.n_rows,
            "n_cols": profile.n_cols,
            "columns": _parse(profile.columns_json, []),
            "variable_types": _parse(profile.variable_types_json, {}),
            "missing_summary": _parse(profile.missing_summary_json, {}),
            "descriptive_summary": profile_extra.get("_descriptive_summary", ""),
            "descriptive_statistics": profile_extra.get("_descriptive_statistics", {}),
            "method_feasibility": _parse(profile.method_feasibility_json, {}),
        } if profile else {},
        "causal_question": {
            "causal_question_text": causal_question.causal_question_text,
            "treatment": causal_question.treatment,
            "outcome": causal_question.outcome,
            "unit": causal_question.unit,
            "time_window": causal_question.time_window,
            "target_population": causal_question.target_population,
            "estimand": causal_question.estimand,
            "confirmed_by_user": causal_question.confirmed_by_user,
        } if causal_question else {},
        "causal_structure": {
            "treatment": causal_structure.treatment,
            "outcome": causal_structure.outcome,
            "confounders": _parse(causal_structure.confounders_json, []),
            "mediators": _parse(causal_structure.mediators_json, []),
            "colliders": _parse(causal_structure.colliders_json, []),
            "bad_controls": _parse(causal_structure.bad_controls_json, []),
            "dag_edges": _parse(causal_structure.dag_edges_json, []),
            "confirmed_by_user": causal_structure.confirmed_by_user,
        } if causal_structure else {},
        "counterfactual": {
            "counterfactual_question": counterfactual.counterfactual_question,
            "comparison_group": counterfactual.comparison_group,
            "counterfactual_source": counterfactual.counterfactual_source,
            "plausibility_assessment": counterfactual.plausibility_assessment,
            "risks": _parse(counterfactual.risks_json, []),
            "confirmed_by_user": counterfactual.confirmed_by_user,
        } if counterfactual else {},
        "assignment_mechanism": {
            "mechanism_type": assignment.mechanism_type,
            "description": assignment.description,
            "endogeneity_risks": _parse(assignment.endogeneity_risks_json, []),
            "possible_strategies": _parse(assignment.possible_strategies_json, []),
            "confirmed_by_user": assignment.confirmed_by_user,
        } if assignment else {},
        "identification_strategy": {
            "recommended_strategy": strategy.recommended_strategy,
            "alternative_strategies": _parse(strategy.alternative_strategies_json, []),
            "key_assumptions": _parse(strategy.key_assumptions_json, []),
            "required_data": _parse(strategy.required_data_json, []),
            "risk_level": strategy.risk_level,
            "credibility_prior": strategy.credibility_prior,
            "confirmed_by_user": strategy.confirmed_by_user,
        } if strategy else {},
        "data_identifiability": {
            "n_rows": identifiability.n_rows,
            "n_cols": identifiability.n_cols,
            "variable_roles": _parse(identifiability.variable_roles_json, {}),
            "identifiability_status": identifiability.identifiability_status,
            "warnings": _parse(identifiability.warnings_json, []),
            "confirmed_by_user": identifiability.confirmed_by_user,
        } if identifiability else {},
        "estimation_setup": {
            "strategy": estimation_setup.strategy,
            "outcome": estimation_setup.outcome,
            "treatment": estimation_setup.treatment,
            "model_formula": estimation_setup.model_formula,
            "covariates": _parse(estimation_setup.covariates_json, []),
            "confirmed_by_user": estimation_setup.confirmed_by_user,
        } if estimation_setup else {},
        "estimation_result": {
            "strategy": estimation_result.strategy,
            "model_formula": estimation_result.model_formula,
            "n_obs": estimation_result.n_obs,
            "result": _parse(estimation_result.result_json, {}),
            "warnings": _parse(estimation_result.warnings_json, []),
            "confirmed_by_user": estimation_result.confirmed_by_user,
        } if estimation_result else {},
        "assumption_diagnostics": {
            "strategy": diagnostics.strategy,
            "credibility_assessment": diagnostics.credibility_assessment,
            "failed_checks": _parse(diagnostics.failed_checks_json, []),
            "passed_checks": _parse(diagnostics.passed_checks_json, []),
            "warnings": _parse(diagnostics.warnings_json, []),
            "confirmed_by_user": diagnostics.confirmed_by_user,
        } if diagnostics else {},
        "causal_effect_interpretation": {
            "causal_claim": effect.causal_claim,
            "credibility_score": effect.credibility_score,
            "credibility_label": effect.credibility_label,
            "limitations": _parse(effect.limitations_json, []),
            "confirmed_by_user": effect.confirmed_by_user,
        } if effect else {},
        "robustness": {
            "results": _parse(robustness.results_json, {}),
            "interpretation": robustness.interpretation,
            "warnings": _parse(robustness.warnings_json, []),
            "confirmed_by_user": robustness.confirmed_by_user,
        } if robustness else {},
        "cleaning_plan": _parse(cleaning.plan_json, {}) if cleaning else {},
        "method_plan": {
            "selected_method": method.selected_method,
            "model_spec": _parse(method.model_spec_json, {}),
            "recommended_methods": _parse(method.recommended_methods_json, []),
        } if method else {},
        "analysis": {
            "method": analysis.method,
            "result": _parse(analysis.result_json, {}),
            "diagnostics": _parse(analysis.diagnostics_json, {}),
            "warnings": _parse(analysis.warnings_json, []),
            "confirmed_by_user": analysis.confirmed_by_user,
            "user_feedback": analysis.user_feedback,
        } if analysis else {},
        "research_timeline": [
            {
                "step": row.step,
                "action": row.action,
                "input_summary": row.input_summary,
                "output_summary": row.output_summary,
                "warnings": _parse(row.warnings_json, []),
                "user_action": row.user_action,
            }
            for row in reversed(logs)
        ],
    }
