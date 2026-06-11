export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "请求失败");
  return body;
}

export const api = {
  projects: () => request("/api/projects"),
  createProject: (name: string) => request("/api/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }),
  abortProject: (id: number) => request(`/api/projects/${id}/abort`, { method: "POST" }),
  chat: (id: number, message: string) => request(`/api/projects/${id}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) }),
  policyText: (id: number, text: string) => request(`/api/projects/${id}/policy-text`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) }),
  upload: (id: number, kind: "policy" | "data", file: File) => { const body = new FormData(); body.append("file", file); return request(`/api/projects/${id}/upload-${kind}`, { method: "POST", body }); },
  profile: (id: number) => request(`/api/projects/${id}/data-profile`),
  cleaningPlan: (id: number) => request(`/api/projects/${id}/cleaning-plan`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }),
  confirmCleaning: (id: number, plan: object) => request(`/api/projects/${id}/confirm-cleaning`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan }) }),
  variableValidation: (id: number) => request(`/api/projects/${id}/variable-validation`),
  methods: (id: number) => request(`/api/projects/${id}/method-recommendation`),
  compareMethods: (id: number, candidate_methods: string[], research_question: string, notes: string) => request(`/api/projects/${id}/compare-methods`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ candidate_methods, research_question, notes }) }),
  confirmMethod: (id: number, selected_method: string, model_spec: object) => request(`/api/projects/${id}/confirm-method`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ selected_method, model_spec }) }),
  analysis: (id: number) => request(`/api/projects/${id}/run-analysis`, { method: "POST" }),
  confirmAnalysis: (id: number) => request(`/api/projects/${id}/confirm-analysis`, { method: "POST" }),
  report: (id: number) => request(`/api/projects/${id}/generate-report`, { method: "POST", headers: { "Content-Type": "application/json" }, body: '{"confirmed":true}' }),
  logs: (id: number) => request(`/api/projects/${id}/audit-logs`),
  confirmResult: (id: number, resultId: number, confirmed: boolean, user_feedback: string) => request(`/api/projects/${id}/analysis-results/${resultId}/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmed, user_feedback }) }),
  reports: (id: number) => request(`/api/projects/${id}/reports`),
  tasks: (id: number) => request(`/api/projects/${id}/tasks`),
  causalGet: (id: number, path: string) => request(`/api/projects/${id}/${path}`),
  causalPost: (id: number, path: string, text = "", data: object = {}) => request(`/api/projects/${id}/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, data }) }),
  causalPatch: (id: number, path: string, data: object, user_feedback = "") => request(`/api/projects/${id}/${path}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data, user_feedback }) }),
  causalConfirm: (id: number, path: string, confirmed = true, user_feedback = "") => request(`/api/projects/${id}/${path}/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmed, user_feedback }) }),
  runDataIdentifiability: (id: number) => request(`/api/projects/${id}/run-data-identifiability-check`, { method: "POST" }),
  runEstimation: (id: number) => request(`/api/projects/${id}/run-estimation`, { method: "POST" }),
  confirmEstimation: (id: number, resultId: number, confirmed = true, user_feedback = "") => request(`/api/projects/${id}/estimation-results/${resultId}/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmed, user_feedback }) }),
  runDiagnostics: (id: number) => request(`/api/projects/${id}/run-assumption-diagnostics`, { method: "POST" }),
  generateEffect: (id: number, text = "") => request(`/api/projects/${id}/generate-causal-effect-interpretation`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, data: {} }) }),
  robustnessPlan: (id: number, planned_checks: string[] = [], rationale: string[] = [], text = "") => request(`/api/projects/${id}/robustness-plan`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, data: { planned_checks, rationale } }) }),
  runRobustness: (id: number) => request(`/api/projects/${id}/run-robustness-checks`, { method: "POST" }),
  robustnessResults: (id: number) => request(`/api/projects/${id}/robustness-results`),
  confirmRobustness: (id: number, confirmed = true, user_feedback = "") => request(`/api/projects/${id}/robustness-results/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmed, user_feedback }) }),
};
