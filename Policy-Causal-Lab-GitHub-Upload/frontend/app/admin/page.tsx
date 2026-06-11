"use client";
import { useEffect, useState } from "react";
import { BookOpen, CheckCircle2, RefreshCw, Save, Settings2 } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const headers = { "Content-Type": "application/json", "X-User-Role": "admin" };
const modules = ["research_design","policy_understanding","data_profiling","cleaning_plan","method_selection","result_interpretation","report_generation","audit_summary"];

async function request(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { ...headers, ...(init?.headers || {}) } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "请求失败");
  return body;
}

export default function AdminPage() {
  const devAdminEnabled = process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN === "true";
  const [tab, setTab] = useState("knowledge");
  const [status, setStatus] = useState("");
  const [sources, setSources] = useState<any[]>([]);
  const [sourceId, setSourceId] = useState<number>();
  const [repo, setRepo] = useState("https://gitee.com/zhiyuanryanchen/causal-inference-machine-learning");
  const [query, setQuery] = useState("DID 平行趋势");
  const [results, setResults] = useState<any>();
  const [prompts, setPrompts] = useState<any[]>([]);
  const [module, setModule] = useState("research_design");
  const [promptText, setPromptText] = useState("");
  const loadSources = async () => { const value = await request("/api/admin/knowledge-sources"); setSources(value.sources); setRepo(value.default_repo_url); };
  const loadPrompts = async () => { const value = await request("/api/admin/prompts"); setPrompts(value); setPromptText(value.find((item:any) => item.module_name === module)?.system_prompt || ""); };
  useEffect(() => { if (devAdminEnabled) loadSources().catch(e => setStatus(e.message)); }, [devAdminEnabled]);
  useEffect(() => { const prompt = prompts.find(item => item.module_name === module); if (prompt) setPromptText(prompt.system_prompt); }, [module, prompts]);
  const run = async (fn: () => Promise<any>) => { try { const value = await fn(); setResults(value); setStatus("操作成功"); return value; } catch (e) { setStatus(e instanceof Error ? e.message : "请求失败"); } };
  if (!devAdminEnabled) return <main className="admin-shell"><section className="workspace"><div className="content"><div className="panel"><h2>无权限</h2><p>管理员后台未启用。</p></div></div></section></main>;
  return <main className="admin-shell"><aside><div className="brand"><div className="logo">P</div><div><b>Policy Causal Lab</b><small>管理员后台</small></div></div><nav><button className={tab==="knowledge"?"active":""} onClick={() => setTab("knowledge")}><BookOpen size={17}/>系统知识库</button><button className={tab==="prompts"?"active":""} onClick={() => { setTab("prompts"); loadPrompts(); }}><Settings2 size={17}/>Prompt 模板</button><button className={tab==="model"?"active":""} onClick={() => { setTab("model"); run(() => request("/api/admin/model-config")); }}><Settings2 size={17}/>模型配置</button></nav></aside><section className="workspace"><header><div><p>系统后台</p><h1>{tab === "knowledge" ? "系统知识库管理" : tab === "prompts" ? "Prompt 模板管理" : "模型配置"}</h1></div><span className="status ok">admin</span></header><div className="content"><div className="panel"><p>{status || "管理员功能不会出现在普通用户工作台中。"}</p><div className="form">
    {tab === "knowledge" && <><label>默认 Gitee 仓库</label><input value={repo} onChange={e=>setRepo(e.target.value)}/><button onClick={async()=>{const v=await run(()=>request("/api/admin/knowledge-sources",{method:"POST",body:JSON.stringify({repo_url:repo,branch:"master"})}));if(v?.id){setSourceId(v.id);loadSources();}}}><BookOpen size={16}/>添加知识源</button><select value={sourceId||""} onChange={e=>setSourceId(Number(e.target.value))}><option value="">选择知识源</option>{sources.map(s=><option key={s.id} value={s.id}>#{s.id} {s.status} {s.repo_url}</option>)}</select><button disabled={!sourceId} onClick={()=>run(()=>request(`/api/admin/knowledge-sources/${sourceId}/sync`,{method:"POST"}))}><RefreshCw size={16}/>同步仓库</button><label>管理员检索</label><input value={query} onChange={e=>setQuery(e.target.value)}/><button onClick={()=>run(()=>request("/api/admin/knowledge-search",{method:"POST",body:JSON.stringify({query,top_k:5})}))}><BookOpen size={16}/>搜索 chunk</button></>}
    {tab === "prompts" && <><select value={module} onChange={e=>setModule(e.target.value)}>{modules.map(item=><option key={item}>{item}</option>)}</select><textarea rows={14} value={promptText} onChange={e=>setPromptText(e.target.value)}/><button className="primary" onClick={()=>run(()=>request(`/api/admin/prompts/${module}`,{method:"POST",body:JSON.stringify({system_prompt:promptText,output_format:"text",change_note:"admin update"})}))}><Save size={16}/>保存系统模板</button></>}
    {tab === "model" && <><button onClick={()=>run(()=>request("/api/admin/model-config"))}><RefreshCw size={16}/>刷新配置</button><button onClick={()=>run(()=>request("/api/admin/model-config",{method:"POST",body:JSON.stringify({deepseek_model:"deepseek-v4-pro"})}))}><CheckCircle2 size={16}/>使用 v4-pro</button><button onClick={()=>run(()=>request("/api/admin/model-config",{method:"POST",body:JSON.stringify({deepseek_model:"deepseek-v4-flash"})}))}><CheckCircle2 size={16}/>使用 v4-flash</button></>}
    {results && <pre>{JSON.stringify(results,null,2)}</pre>}</div></div></div></section></main>
}
