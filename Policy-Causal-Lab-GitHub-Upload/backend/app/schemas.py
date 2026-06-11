from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectOut(ORMModel):
    id: int
    name: str
    description: str
    status: str


class ChatRequest(BaseModel):
    message: str


class PolicyTextRequest(BaseModel):
    text: str


class CleaningPlanRequest(BaseModel):
    plan: dict[str, Any] | None = None


class ConfirmCleaningRequest(BaseModel):
    plan: dict[str, Any]
    user_feedback: str = ""


class ConfirmMethodRequest(BaseModel):
    selected_method: str
    model_spec: dict[str, Any] = Field(default_factory=dict)


class MethodComparisonRequest(BaseModel):
    candidate_methods: list[str] = Field(default_factory=list)
    research_question: str = ""
    notes: str = ""


class ReportRequest(BaseModel):
    confirmed: bool = True


class PromptSaveRequest(BaseModel):
    system_prompt: str
    output_format: str = "text"
    change_note: str = ""


class SystemKnowledgeSourceRequest(BaseModel):
    repo_url: str
    branch: str = "master"


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class ResearchBriefPayload(BaseModel):
    policy_name: str = ""
    policy_background: str = ""
    research_question: str = ""
    research_objective: str = ""
    treatment_definition: str = ""
    control_definition: str = ""
    time_window: str = ""
    outcome_variables: list[str] = Field(default_factory=list)
    mechanism_variables: list[str] = Field(default_factory=list)
    covariates: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    identification_strategy_notes: str = ""


class AnalysisConfirmRequest(BaseModel):
    confirmed: bool = True
    user_feedback: str = ""


class ReportUpdateRequest(BaseModel):
    markdown_content: str
    user_feedback: str = ""


class ModelConfigRequest(BaseModel):
    deepseek_model: str


class CausalModuleRequest(BaseModel):
    text: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    user_feedback: str = ""


class CausalModuleConfirmRequest(BaseModel):
    confirmed: bool = True
    user_feedback: str = ""
