from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def now() -> datetime:
    return datetime.utcnow()


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="research_design")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(30))
    file_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ResearchBrief(Base):
    __tablename__ = "research_briefs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True, index=True)
    policy_name: Mapped[str] = mapped_column(String(255), default="")
    policy_background: Mapped[str] = mapped_column(Text, default="")
    research_question: Mapped[str] = mapped_column(Text, default="")
    research_objective: Mapped[str] = mapped_column(Text, default="")
    treatment_definition: Mapped[str] = mapped_column(Text, default="")
    control_definition: Mapped[str] = mapped_column(Text, default="")
    time_window: Mapped[str] = mapped_column(Text, default="")
    outcome_variables: Mapped[str] = mapped_column(Text, default="[]")
    mechanism_variables: Mapped[str] = mapped_column(Text, default="[]")
    covariates: Mapped[str] = mapped_column(Text, default="[]")
    hypotheses: Mapped[str] = mapped_column(Text, default="[]")
    identification_strategy_notes: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class DataProfile(Base):
    __tablename__ = "data_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    n_rows: Mapped[int] = mapped_column(Integer)
    n_cols: Mapped[int] = mapped_column(Integer)
    columns_json: Mapped[str] = mapped_column(Text)
    missing_summary_json: Mapped[str] = mapped_column(Text)
    variable_types_json: Mapped[str] = mapped_column(Text)
    id_candidates_json: Mapped[str] = mapped_column(Text)
    time_candidates_json: Mapped[str] = mapped_column(Text)
    treatment_candidates_json: Mapped[str] = mapped_column(Text)
    outcome_candidates_json: Mapped[str] = mapped_column(Text)
    method_feasibility_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class CleaningPlan(Base):
    __tablename__ = "cleaning_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class MethodPlan(Base):
    __tablename__ = "method_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    recommended_methods_json: Mapped[str] = mapped_column(Text, default="[]")
    selected_method: Mapped[str] = mapped_column(String(100))
    model_spec_json: Mapped[str] = mapped_column(Text, default="{}")
    assumptions_json: Mapped[str] = mapped_column(Text, default="[]")
    risks_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class CausalQuestion(Base):
    __tablename__ = "causal_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    causal_question_text: Mapped[str] = mapped_column(Text, default="")
    treatment: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(Text, default="")
    unit: Mapped[str] = mapped_column(Text, default="")
    time_window: Mapped[str] = mapped_column(Text, default="")
    target_population: Mapped[str] = mapped_column(Text, default="")
    estimand: Mapped[str] = mapped_column(String(50), default="unclear")
    research_context: Mapped[str] = mapped_column(Text, default="")
    clarification_questions_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class CausalStructure(Base):
    __tablename__ = "causal_structures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    treatment: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(Text, default="")
    confounders_json: Mapped[str] = mapped_column(Text, default="[]")
    mediators_json: Mapped[str] = mapped_column(Text, default="[]")
    colliders_json: Mapped[str] = mapped_column(Text, default="[]")
    moderators_json: Mapped[str] = mapped_column(Text, default="[]")
    bad_controls_json: Mapped[str] = mapped_column(Text, default="[]")
    post_treatment_variables_json: Mapped[str] = mapped_column(Text, default="[]")
    mechanism_hypotheses_json: Mapped[str] = mapped_column(Text, default="[]")
    dag_edges_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class CounterfactualPlan(Base):
    __tablename__ = "counterfactual_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    counterfactual_question: Mapped[str] = mapped_column(Text, default="")
    comparison_group: Mapped[str] = mapped_column(Text, default="")
    counterfactual_source: Mapped[str] = mapped_column(String(100), default="unclear")
    plausibility_assessment: Mapped[str] = mapped_column(String(50), default="low")
    risks_json: Mapped[str] = mapped_column(Text, default="[]")
    required_evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class AssignmentMechanism(Base):
    __tablename__ = "assignment_mechanisms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    mechanism_type: Mapped[str] = mapped_column(String(100), default="unclear")
    description: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    endogeneity_risks_json: Mapped[str] = mapped_column(Text, default="[]")
    possible_strategies_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class IdentificationStrategy(Base):
    __tablename__ = "identification_strategies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    recommended_strategy: Mapped[str] = mapped_column(String(100), default="Descriptive only")
    alternative_strategies_json: Mapped[str] = mapped_column(Text, default="[]")
    counterfactual_logic: Mapped[str] = mapped_column(Text, default="")
    key_assumptions_json: Mapped[str] = mapped_column(Text, default="[]")
    required_data_json: Mapped[str] = mapped_column(Text, default="[]")
    diagnostics_json: Mapped[str] = mapped_column(Text, default="[]")
    risks_json: Mapped[str] = mapped_column(Text, default="[]")
    risk_level: Mapped[str] = mapped_column(String(50), default="high")
    credibility_prior: Mapped[int] = mapped_column(Integer, default=0)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class DataIdentifiabilityCheck(Base):
    __tablename__ = "data_identifiability_checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    n_rows: Mapped[int] = mapped_column(Integer, default=0)
    n_cols: Mapped[int] = mapped_column(Integer, default=0)
    variable_roles_json: Mapped[str] = mapped_column(Text, default="{}")
    missing_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    panel_structure_json: Mapped[str] = mapped_column(Text, default="{}")
    treatment_variation_json: Mapped[str] = mapped_column(Text, default="{}")
    outcome_availability_json: Mapped[str] = mapped_column(Text, default="{}")
    pre_post_availability_json: Mapped[str] = mapped_column(Text, default="{}")
    control_group_availability_json: Mapped[str] = mapped_column(Text, default="{}")
    common_support_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    method_support_json: Mapped[str] = mapped_column(Text, default="{}")
    identifiability_status: Mapped[str] = mapped_column(String(50), default="high_risk")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class EstimationSetup(Base):
    __tablename__ = "estimation_setups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    strategy: Mapped[str] = mapped_column(String(100), default="")
    outcome: Mapped[str] = mapped_column(Text, default="")
    treatment: Mapped[str] = mapped_column(Text, default="")
    post_variable: Mapped[str] = mapped_column(Text, default="")
    time_variable: Mapped[str] = mapped_column(Text, default="")
    entity_variable: Mapped[str] = mapped_column(Text, default="")
    running_variable: Mapped[str] = mapped_column(Text, default="")
    cutoff: Mapped[str] = mapped_column(Text, default="")
    instrument_variable: Mapped[str] = mapped_column(Text, default="")
    covariates_json: Mapped[str] = mapped_column(Text, default="[]")
    fixed_effects_json: Mapped[str] = mapped_column(Text, default="{}")
    standard_error_type: Mapped[str] = mapped_column(String(100), default="robust")
    cluster_variable: Mapped[str] = mapped_column(Text, default="")
    sample_filter_json: Mapped[str] = mapped_column(Text, default="{}")
    model_formula: Mapped[str] = mapped_column(Text, default="")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class EstimationResult(Base):
    __tablename__ = "estimation_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    strategy: Mapped[str] = mapped_column(String(100), default="")
    model_formula: Mapped[str] = mapped_column(Text, default="")
    n_obs: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    coefficients_json: Mapped[str] = mapped_column(Text, default="{}")
    diagnostics_json: Mapped[str] = mapped_column(Text, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    chart_paths_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AssumptionDiagnostics(Base):
    __tablename__ = "assumption_diagnostics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    strategy: Mapped[str] = mapped_column(String(100), default="")
    diagnostics_json: Mapped[str] = mapped_column(Text, default="{}")
    charts_json: Mapped[str] = mapped_column(Text, default="[]")
    credibility_assessment: Mapped[str] = mapped_column(String(50), default="weak")
    failed_checks_json: Mapped[str] = mapped_column(Text, default="[]")
    passed_checks_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class CausalEffectInterpretation(Base):
    __tablename__ = "causal_effect_interpretations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    causal_claim: Mapped[str] = mapped_column(Text, default="")
    estimand_interpretation: Mapped[str] = mapped_column(Text, default="")
    effect_size_interpretation: Mapped[str] = mapped_column(Text, default="")
    statistical_uncertainty: Mapped[str] = mapped_column(Text, default="")
    identification_conditions_json: Mapped[str] = mapped_column(Text, default="[]")
    external_validity: Mapped[str] = mapped_column(Text, default="")
    unsupported_claims_json: Mapped[str] = mapped_column(Text, default="[]")
    limitations_json: Mapped[str] = mapped_column(Text, default="[]")
    credibility_score: Mapped[int] = mapped_column(Integer, default=0)
    credibility_label: Mapped[str] = mapped_column(String(50), default="low")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class RobustnessPlan(Base):
    __tablename__ = "robustness_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    planned_checks_json: Mapped[str] = mapped_column(Text, default="[]")
    rationale_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class RobustnessResult(Base):
    __tablename__ = "robustness_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    checks_run_json: Mapped[str] = mapped_column(Text, default="[]")
    results_json: Mapped[str] = mapped_column(Text, default="{}")
    interpretation: Mapped[str] = mapped_column(Text, default="")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    method: Mapped[str] = mapped_column(String(100))
    result_json: Mapped[str] = mapped_column(Text)
    diagnostics_json: Mapped[str] = mapped_column(Text, default="{}")
    chart_paths_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    markdown_content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    user_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    step: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")
    reasoning_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    user_action: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(30), default="system", index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    module_name: Mapped[str] = mapped_column(String(100), index=True)
    system_prompt: Mapped[str] = mapped_column(Text)
    output_format: Mapped[str] = mapped_column(String(30), default="text")
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class SystemKnowledgeSource(Base):
    __tablename__ = "system_knowledge_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), default="gitee")
    repo_url: Mapped[str] = mapped_column(Text)
    branch: Mapped[str] = mapped_column(String(100), default="master")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class SystemKnowledgeChunk(Base):
    __tablename__ = "system_knowledge_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("system_knowledge_sources.id"), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(String(30))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TaskRecord(Base):
    __tablename__ = "task_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30), default="user", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SystemAuditLog(Base):
    __tablename__ = "system_audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(100))
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
