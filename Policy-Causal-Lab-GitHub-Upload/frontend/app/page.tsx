"use client";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { AlertTriangle, BarChart3, CheckCircle2, Database, Download, FileText, GitBranch, ListChecks, RefreshCw, ScrollText, Send, Sparkles, Upload, WandSparkles } from "lucide-react";
import { api } from "../lib/api";

const steps = [
  ["因果问题定义", "Causal Question", "causal-question"],
  ["变量与因果结构", "Variable & Causal Structure", "causal-structure"],
  ["反事实构造", "Counterfactual", "counterfactual-plan"],
  ["处理分配机制", "Assignment Mechanism", "assignment-mechanism"],
  ["识别策略选择", "Identification Strategy", "identification-strategy"],
  ["数据上传与可识别性检查", "Data & Identifiability Check", "data-identifiability-check"],
  ["估计设定确认", "Estimation Setup", "estimation-setup"],
  ["模型估计", "Estimation Runner", "estimation-runner"],
  ["识别假设诊断", "Assumption Diagnostics", "assumption-diagnostics"],
  ["因果效应解释", "Causal Effect Interpretation", "causal-effect-interpretation"],
  ["稳健性与敏感性分析", "Robustness & Sensitivity", "robustness"],
  ["因果推断报告", "Causal Inference Report", "causal-report"],
  ["审计日志", "Audit Log", "audit-log"],
  ["任务状态", "Task Status", "task-status"],
] as const;
const robustnessOptions = ["更换政策前后时间窗口", "更换协变量集合", "加入/移除固定效应", "排除单个省份或异常样本", "安慰剂政策时间", "安慰剂处理组", "事件研究动态效应", "PSM 匹配后平衡性", "未观测混杂敏感性分析", "异质性分析"];

type ProjectItem = { id: number; name: string; description: string; status: string };
type ChatMessage = { role: "user" | "assistant"; content: string; warning?: string[] };

export default function Home() {
  const [projectId, setProjectId] = useState<number>();
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [projectListOpen, setProjectListOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("因果推断项目");
  const [input, setInput] = useState("");
  const [robustnessNotes, setRobustnessNotes] = useState("");
  const [selectedRobustness, setSelectedRobustness] = useState<string[]>(["更换政策前后时间窗口", "更换协变量集合", "安慰剂政策时间"]);
  const [output, setOutput] = useState<any>();
  const [done, setDone] = useState<number[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const current = steps[step];
  const confirmPath = ["causal-question", "causal-structure", "counterfactual-plan", "assignment-mechanism", "identification-strategy", "data-identifiability-check", "estimation-setup", "", "assumption-diagnostics", "causal-effect-interpretation", "", "", "", ""][step];
  const need = () => { if (!projectId) throw new Error("请先创建或打开项目"); return projectId; };
  const refreshProjects = async () => setProjects(await api.projects());
  const openProject = (project: ProjectItem) => { setProjectId(project.id); setName(project.name); setOutput(undefined); setProjectListOpen(false); setDone([]); };
  const act = async (fn: () => Promise<any>, completed = step) => {
    setBusy(true);
    try {
      const value = await fn();
      setOutput(value);
      setDone(items => Array.from(new Set([...items, completed])));
      return value;
    } catch (error) {
      setOutput({ error: error instanceof Error ? error.message : "请求失败" });
    } finally {
      setBusy(false);
    }
  };
  const sendCausalQuestion = async () => {
    const text = input.trim();
    if (!text) return;
    setChatHistory(items => [...items, { role: "user", content: text }]);
    const value = await act(() => api.causalPost(need(), "causal-question", text));
    if (value) setChatHistory(items => [...items, { role: "assistant", content: formatCausalQuestionMessage(value), warning: value.warnings || [] }]);
    setInput("");
  };

  return <main>
    <aside>
      <div className="brand"><div className="logo">C</div><div><b>Policy Causal Lab</b><small>因果推断工作台</small></div></div>
      <nav>{steps.map(([label], index) => <button className={step === index ? "active" : ""} onClick={() => { setStep(index); setOutput(undefined); }} key={label}><StepIcon index={index}/><span>{label}</span>{done.includes(index) && <CheckCircle2 size={15} className="done"/>}</button>)}</nav>
      <div className="aside-foot"><small>当前项目</small><span>{projectId ? `#${projectId} ${name}` : "尚未创建"}</span></div>
    </aside>
    <section className="workspace">
      <header><div><p>因果推断流程 / {current[1]}</p><h1>{current[0]}</h1></div><span className={projectId ? "status ok" : "status"}>{projectId ? "进行中" : "未开始"}</span></header>
      <div className="content">
        {step === 0 && <Panel title="因果问题定义" note="先把现实问题转写为可识别的因果问题，而不是直接进入模型。">
          <ProjectManager open={projectListOpen} setOpen={setProjectListOpen} projects={projects} refreshProjects={refreshProjects} openProject={openProject} abortCurrent={projectId ? () => act(async () => { const p = await api.abortProject(projectId); await refreshProjects(); return { message: `项目 #${p.id} 已中止。` }; }) : undefined}/>
          {!projectId && <><label>项目名称</label><input value={name} onChange={e => setName(e.target.value)}/><button className="primary" onClick={() => act(async () => { const p = await api.createProject(name); setProjectId(p.id); await refreshProjects(); return p; }, 0)}><Sparkles size={16}/> 创建项目</button></>}
          {projectId && <div className="chat">{chatHistory.length > 0 && <div className="thread">{chatHistory.map((item, index) => <div className={`bubble ${item.role}`} key={index}><div className="bubble-meta">{item.role === "user" ? "你" : "因果助手"}</div><ReactMarkdown>{item.content}</ReactMarkdown>{item.warning?.length ? <small>{item.warning.join("；")}</small> : null}</div>)}</div>}<label>现实研究问题</label><textarea rows={5} value={input} onChange={e => setInput(e.target.value)} placeholder="例如：西部大开发是否提高了西部地区的经济增长？处理、结果、单位、时间窗口还不清楚也可以先写自然语言。"/><button className="primary" disabled={busy || !input.trim()} onClick={sendCausalQuestion}><Send size={16}/> 生成因果问题卡片</button><button onClick={() => act(() => api.causalGet(need(), "causal-question"))}><ScrollText size={16}/> 查看当前卡片</button><ConfirmBlock path="causal-question" act={act} need={need}/></div>}
        </Panel>}

        {step === 1 && <CausalStep title="变量与因果结构" path="causal-structure" button="生成因果结构" placeholder="补充变量、机制、可能混杂因素。系统会区分混杂变量、中介变量、碰撞变量、坏控制和政策后变量。" icon={<GitBranch size={16}/>} act={act} need={need}/>}
        {step === 2 && <CausalStep title="反事实构造" path="counterfactual-plan" button="生成反事实构造卡片" placeholder="说明处理组如果没有接受政策，本来可能如何变化？对照组是谁？" icon={<GitBranch size={16}/>} act={act} need={need}/>}
        {step === 3 && <CausalStep title="处理分配机制" path="assignment-mechanism" button="判断处理分配机制" placeholder="说明政策如何实施：试点、分批、阈值、自选择、单一处理对象，还是观察性面板？" icon={<WandSparkles size={16}/>} act={act} need={need}/>}
        {step === 4 && <CausalStep title="识别策略选择" path="identification-strategy" button="推荐识别策略" placeholder="系统会基于因果问题、反事实、分配机制和已有数据推荐策略；如果不可识别，应推荐 Descriptive only。" icon={<WandSparkles size={16}/>} act={act} need={need}/>}

        {step === 5 && <Panel title="数据上传与可识别性检查" note="上传数据后，检查变量、样本结构、处理变化和当前识别策略是否被数据支持。"><UploadBox accept=".csv,.xlsx,.xls,.dta" multiple onFiles={files => act(async () => ({ uploaded: await Promise.all(files.map(file => api.upload(need(), "data", file))) }))}/><button onClick={() => act(() => api.profile(need()))}><Database size={16}/> 生成描述性统计</button><button className="primary" onClick={() => act(() => api.runDataIdentifiability(need()))}><CheckCircle2 size={16}/> 运行数据可识别性检查</button><ConfirmBlock path="data-identifiability-check" act={act} need={need}/></Panel>}

        {step === 6 && <CausalStep title="估计设定确认" path="estimation-setup" button="生成估计设定建议" placeholder="系统会根据识别策略和数据变量生成 outcome、treatment、time、unit、covariates、固定效应和标准误建议。" icon={<ListChecks size={16}/>} act={act} need={need}/>}
        {step === 7 && <Panel title="模型估计" note="运行已确认的估计设定并展示模型结果。"><button className="primary" onClick={() => act(() => api.runEstimation(need()))}><BarChart3 size={16}/> 运行估计</button>{output?.id && <button onClick={() => act(() => api.confirmEstimation(need(), output.id, true, ""))}><CheckCircle2 size={16}/> 确认估计结果</button>}</Panel>}
        {step === 8 && <Panel title="识别假设诊断" note="根据识别策略展示可运行的诊断检查和尚未实现的检查。"><button className="primary" onClick={() => act(() => api.runDiagnostics(need()))}><BarChart3 size={16}/> 运行诊断</button><ConfirmBlock path="assumption-diagnostics" act={act} need={need}/></Panel>}
        {step === 9 && <Panel title="因果效应解释" note="结合估计结果、诊断结果和识别假设，给出因果解释边界和可信度判断。"><textarea rows={4} value={input} onChange={e => setInput(e.target.value)} placeholder="可补充你希望重点解释的结果、担心的识别风险或外推边界。"/><button className="primary" onClick={() => act(() => api.generateEffect(need(), input))}><Sparkles size={16}/> 生成因果效应解释</button><ConfirmBlock path="causal-effect-interpretation" act={act} need={need}/></Panel>}
        {step === 10 && <Panel title="稳健性与敏感性分析" note="选择要检查的稳健性方案，并说明你希望重点比较的样本、变量或模型设定。当前版本会真实运行部分 DID 变体，未实现的检查会明确标记。"><div className="check-grid">{robustnessOptions.map(item => <label key={item}><input type="checkbox" checked={selectedRobustness.includes(item)} onChange={() => setSelectedRobustness(values => values.includes(item) ? values.filter(x => x !== item) : [...values, item])}/><span>{item}</span></label>)}</div><label>分析说明</label><textarea rows={4} value={robustnessNotes} onChange={e => setRobustnessNotes(e.target.value)} placeholder="例如：重点检查更换政策窗口、排除个别省份、加入省份和年份固定效应后结论是否稳定。"/><button onClick={() => act(() => api.robustnessPlan(need(), selectedRobustness, robustnessNotes ? [robustnessNotes] : [], robustnessNotes))}><WandSparkles size={16}/> 生成稳健性计划</button><button className="primary" onClick={() => act(() => api.runRobustness(need()))}><RefreshCw size={16}/> 运行可用检查</button><button onClick={() => act(() => api.robustnessResults(need()))}><ScrollText size={16}/> 查看最新结果</button></Panel>}
        {step === 11 && <Panel title="因果推断报告" note="汇总已确认的因果问题、识别策略、数据检查、估计结果、诊断和结论边界。"><button className="primary" onClick={() => act(() => api.report(need()))}><FileText size={16}/> 生成报告</button><button onClick={() => act(() => api.reports(need()))}><ScrollText size={16}/> 查看历史版本</button></Panel>}
        {step === 12 && <Panel title="审计日志" note="记录每一步的建议、确认、风险提示和系统知识库引用元数据。"><button className="primary" onClick={() => act(() => api.logs(need()))}><ScrollText size={16}/> 刷新审计日志</button></Panel>}
        {step === 13 && <Panel title="任务状态" note="查看后台任务和运行状态。"><button className="primary" onClick={() => act(() => api.tasks(need()))}><ListChecks size={16}/> 刷新任务状态</button></Panel>}

        {busy && <div className="loading">正在处理...</div>}
        {output && <OutputPanel output={output} confirmPath={confirmPath} act={act} need={need}/>}
      </div>
    </section>
  </main>;
}

function StepIcon({ index }: { index: number }) {
  const icons = [Sparkles, GitBranch, GitBranch, WandSparkles, WandSparkles, Database, ListChecks, BarChart3, BarChart3, Sparkles, RefreshCw, FileText, ScrollText, ListChecks];
  const Icon = icons[index] || Sparkles;
  return <Icon size={17}/>;
}

function formatCausalQuestionMessage(value: any) {
  const questions = Array.isArray(value.clarification_questions) && value.clarification_questions.length
    ? value.clarification_questions.map((item: string) => `- ${item}`).join("\n")
    : "- 暂无，后续步骤会继续检查变量、反事实和识别条件。";
  return [
    "已将你的研究想法转写为标准因果问题：",
    "",
    `**因果问题**：${value.causal_question_text || "未识别"}`,
    `**Treatment**：${value.treatment || "待明确"}`,
    `**Outcome**：${value.outcome || "待明确"}`,
    `**Unit**：${value.unit || "待明确"}`,
    `**Time Window**：${value.time_window || "待明确"}`,
    `**Target Population**：${value.target_population || "待明确"}`,
    `**Estimand**：${value.estimand || "unclear"}`,
    "",
    "**需要你进一步确认的问题**：",
    questions,
  ].join("\n");
}

function Panel({ title, note, children }: { title: string; note: string; children: React.ReactNode }) { return <div className="panel"><h2>{title}</h2><p>{note}</p><div className="form">{children}</div></div>; }

function ProjectManager({ open, setOpen, projects, refreshProjects, openProject, abortCurrent }: { open: boolean; setOpen: (value: boolean) => void; projects: ProjectItem[]; refreshProjects: () => void; openProject: (project: ProjectItem) => void; abortCurrent?: () => void }) {
  const toggle = async () => { if (!open) await refreshProjects(); setOpen(!open); };
  return <div className="project-tools"><button onClick={toggle}><ScrollText size={16}/> {open ? "收起已有项目" : "查看已有项目"}</button>{abortCurrent && <button onClick={abortCurrent}><AlertTriangle size={16}/> 中止当前项目</button>}{open && projects.length > 0 && <div className="project-list">{projects.map(project => <button key={project.id} onClick={() => openProject(project)}><span>#{project.id} {project.name}</span><small>{project.status}</small></button>)}</div>}</div>;
}

function CausalStep({ title, path, button, placeholder, icon, act, need }: { title: string; path: string; button: string; placeholder: string; icon: React.ReactNode; act: any; need: () => number }) {
  const [text, setText] = useState("");
  return <Panel title={title} note="系统给出结构化建议，用户可以编辑后确认。"><textarea rows={5} value={text} onChange={e => setText(e.target.value)} placeholder={placeholder}/><button className="primary" onClick={() => act(() => api.causalPost(need(), path, text))}>{icon} {button}</button><button onClick={() => act(() => api.causalGet(need(), path))}><ScrollText size={16}/> 查看当前卡片</button><ConfirmBlock path={path} act={act} need={need}/></Panel>;
}

function ConfirmBlock({ path, act, need }: { path: string; act: any; need: () => number }) {
  return <><button onClick={() => act(() => api.causalConfirm(need(), path, true, ""))}><CheckCircle2 size={16}/> 确认当前结果</button><button onClick={() => act(() => api.causalConfirm(need(), path, false, ""))}>标记为待修正</button></>;
}

function UploadBox({ accept, onFile, onFiles, multiple = false }: { accept: string; onFile?: (file: File) => void; onFiles?: (files: File[]) => void; multiple?: boolean }) {
  return <label className="drop"><Upload size={24}/><span>{multiple ? "选择一个或多个文件上传" : "选择文件上传"}</span><input type="file" multiple={multiple} accept={accept} onChange={e => { const files = Array.from(e.target.files || []); if (multiple) onFiles?.(files); else files[0] && onFile?.(files[0]); }}/></label>;
}

function OutputPanel({ output, confirmPath, act, need }: { output: any; confirmPath?: string; act: any; need: () => number }) {
  const canConfirm = Boolean(confirmPath && isConfirmableOutput(output, confirmPath));
  if (output.error) return <section className="result result-error"><div className="result-title"><AlertTriangle size={18}/><h2>请求未完成</h2></div><p>{output.error}</p></section>;
  if (isTaskStatusOutput(output)) return <TaskStatusResult output={output}/>;
  if (Array.isArray(output)) return <section className="result"><div className="result-title"><ScrollText size={18}/><h2>列表结果</h2></div>{output.map((item, index) => <DataCard item={item} key={index}/>)}</section>;
  if (output.markdown_content) return <ReportResult output={output}/>;
  if (Array.isArray(output.uploaded)) return <section className="result"><div className="result-title"><Upload size={18}/><h2>文件已上传</h2></div><div className="summary-grid">{output.uploaded.map((item: any) => <div key={item.file_id}><strong>{item.filename}</strong><span>项目内数据文件数：{item.data_file_count}</span></div>)}</div></section>;
  if (output.identifiability_status) return <IdentifiabilityResult output={output} confirmPath={canConfirm ? confirmPath : ""} act={act} need={need}/>;
  if (isDiagnosticsOutput(output)) return <DiagnosticsResult output={output} confirmPath={canConfirm ? confirmPath : ""} act={act} need={need}/>;
  if (isRobustnessOutput(output)) return <RobustnessResult output={output} act={act} need={need}/>;
  if (Array.isArray(output.results) && output.results.some(isRobustnessOutput)) return <RobustnessHistory output={output} act={act} need={need}/>;
  if (isEstimationOutput(output)) return <EstimationResult output={output} act={act} need={need}/>;
  if (Array.isArray(output.results) && output.results.some(isEstimationOutput)) return <EstimationHistory output={output} act={act} need={need}/>;
  return <section className="result"><div className="result-title"><Sparkles size={18}/><h2>{resultTitle(output)}</h2></div><StatusLine output={output}/><AnalysisMarkdown markdown={output.analysis_markdown}/><DataCard item={output}/><Warnings warnings={output.warnings || output.warning}/>{output.chart_paths?.length ? <div className="chart-grid">{output.chart_paths.map((path: string) => <img key={path} src={path.replace(/^storage\//, "/storage/").replace(/^.*\/storage\//, "/storage/")} alt="分析图表"/>)}</div> : null}{canConfirm && confirmPath ? <div className="result-actions"><EditableResultEditor output={output} path={confirmPath} act={act} need={need} feedback=""/><button className="primary" onClick={() => act(() => api.causalConfirm(need(), confirmPath, true, ""))}><CheckCircle2 size={16}/> {output.confirmed_by_user ? "重新确认当前结果" : "确认当前结果"}</button><button onClick={() => act(() => api.causalConfirm(need(), confirmPath, false, ""))}>标记为待修正</button></div> : null}</section>;
}

function isTaskStatusOutput(output: any) {
  return Array.isArray(output) && output.length > 0 && output.every(item => Object.prototype.hasOwnProperty.call(item, "task_type") && Object.prototype.hasOwnProperty.call(item, "progress") && Object.prototype.hasOwnProperty.call(item, "status"));
}

function TaskStatusResult({ output }: { output: any[] }) {
  const summary = output.find(item => item.task_type === "项目总进度");
  const steps = output.filter(item => item.task_type !== "项目总进度");
  return <section className="result task-status-result">
    <div className="result-title"><ListChecks size={18}/><h2>任务状态</h2></div>
    <div className="task-summary">
      <div><small>总进度</small><strong>{summary?.progress ?? 0}%</strong></div>
      <div><small>状态</small><strong>{taskStatusLabel(summary?.status)}</strong></div>
      <div><small>流程</small><strong>{summary?.message || `已完成 ${steps.filter(item => item.progress >= 100).length}/${steps.length} 个流程节点。`}</strong></div>
    </div>
    <div className="table-wrap task-table"><table><thead><tr><th>流程</th><th>进度</th><th>状态</th></tr></thead><tbody>{steps.map(item => <tr key={item.id} className={item.status === "pending" ? "risk-row" : "highlight-row"}><td>{item.task_type}</td><td><div className="progress-cell"><span><i style={{ width: `${Math.max(0, Math.min(100, Number(item.progress) || 0))}%` }}/></span><b>{item.progress}%</b></div></td><td>{taskStatusLabel(item.status)}</td></tr>)}</tbody></table></div>
  </section>;
}

function taskStatusLabel(status?: string) {
  const labels: Record<string, string> = { completed: "已完成", confirmed: "已确认", in_progress: "进行中", pending: "未完成", failed: "失败" };
  return labels[String(status || "")] || status || "未知";
}

function AnalysisMarkdown({ markdown }: { markdown?: string }) {
  if (!markdown) return null;
  return <article className="markdown analysis-markdown"><ReactMarkdown>{markdown}</ReactMarkdown></article>;
}

function ReportResult({ output }: { output: any }) {
  const download = () => {
    const blob = new Blob([output.markdown_content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `causal-report-v${output.version || "latest"}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return <section className="result report-result"><div className="result-title"><FileText size={18}/><h2>因果推断分析报告</h2></div><div className="report-actions"><button className="primary" onClick={download}><Download size={16}/> 下载 Markdown</button>{output.version && <span>版本 {output.version}</span>}</div><article className="markdown report-markdown">{renderReportMarkdown(output.markdown_content)}</article><Warnings warnings={output.warnings}/></section>;
}

function renderReportMarkdown(markdown: string) {
  const lines = markdown.split("\n");
  const nodes: React.ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1;
      nodes.push(<pre key={nodes.length}>{code.join("\n")}</pre>);
      continue;
    }
    if (line.startsWith("# ")) {
      nodes.push(<h1 key={nodes.length}>{line.slice(2)}</h1>);
      index += 1;
      continue;
    }
    if (line.startsWith("## ")) {
      nodes.push(<h2 key={nodes.length}>{line.slice(3)}</h2>);
      index += 1;
      continue;
    }
    if (line.startsWith("### ")) {
      nodes.push(<h3 key={nodes.length}>{line.slice(4)}</h3>);
      index += 1;
      continue;
    }
    if (line.trim().startsWith("|") && lines[index + 1]?.includes("---")) {
      const rows: string[][] = [];
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        const current = lines[index].trim();
        if (!/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(current)) {
          rows.push(current.replace(/^\||\|$/g, "").split("|").map(cell => cell.trim()));
        }
        index += 1;
      }
      const [head, ...body] = rows;
      nodes.push(<div className="table-wrap report-table" key={nodes.length}><table><thead><tr>{head.map((cell, cellIndex) => <th key={cellIndex}>{inlineMarkdown(cell)}</th>)}</tr></thead><tbody>{body.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}>{inlineMarkdown(cell)}</td>)}</tr>)}</tbody></table></div>);
      continue;
    }
    if (line.startsWith("- ")) {
      const items: string[] = [];
      while (index < lines.length && lines[index].startsWith("- ")) {
        items.push(lines[index].slice(2));
        index += 1;
      }
      nodes.push(<ul key={nodes.length}>{items.map((item, itemIndex) => <li key={itemIndex}>{inlineMarkdown(item)}</li>)}</ul>);
      continue;
    }
    const paragraph: string[] = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !lines[index].startsWith("#") && !lines[index].startsWith("- ") && !lines[index].trim().startsWith("|") && !lines[index].startsWith("```")) {
      paragraph.push(lines[index]);
      index += 1;
    }
    nodes.push(<p key={nodes.length}>{inlineMarkdown(paragraph.join(" "))}</p>);
  }
  return nodes;
}

function inlineMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    return <span key={index}>{part}</span>;
  });
}

function isEstimationOutput(output: any) {
  return Boolean(output && output.strategy && output.model_formula && output.n_obs !== undefined && (output.result || output.coefficients));
}

function EstimationHistory({ output, act, need }: { output: any; act: any; need: () => number }) {
  const results = (output.results || []).filter(isEstimationOutput);
  return <section className="result"><div className="result-title"><BarChart3 size={18}/><h2>历史估计结果</h2></div>{results.length ? <EstimationResult output={results[0]} act={act} need={need} embedded/> : <p className="empty">暂无估计结果。</p>}</section>;
}

function EstimationResult({ output, act, need, embedded = false }: { output: any; act: any; need: () => number; embedded?: boolean }) {
  const result = output.result || {};
  const coefficients = result.coefficients || output.coefficients || {};
  const standardErrors = result.standard_errors || {};
  const pValues = result.p_values || {};
  const intervals = result.confidence_intervals || {};
  const mainTerm = pickMainTerm(output, coefficients);
  const coef = numberOrUndefined(coefficients[mainTerm]);
  const se = numberOrUndefined(standardErrors[mainTerm]);
  const p = numberOrUndefined(pValues[mainTerm]);
  const ci = Array.isArray(intervals[mainTerm]) ? intervals[mainTerm].map(numberOrUndefined) : [];
  const significant = p !== undefined && p < 0.05;
  const direction = coef === undefined ? "尚无法判断方向" : coef > 0 ? "正向" : coef < 0 ? "负向" : "接近 0";
  const headline = coef === undefined
    ? "没有找到可解释的核心估计项。"
    : `${output.strategy} 的核心估计项 ${mainTerm} 为 ${formatNumber(coef)}，方向为${direction}${p === undefined ? "" : significant ? "，在 5% 水平上显著。" : "，在 5% 水平上不显著。"}`;
  const rows = [
    ["核心估计项", mainTerm],
    ["系数", formatNumber(coef)],
    ["标准误", formatNumber(se)],
    ["p 值", formatPValue(p)],
    ["95% 置信区间", ci.length === 2 ? `[${formatNumber(ci[0])}, ${formatNumber(ci[1])}]` : "未提供"],
    ["样本量", String(output.n_obs ?? result.n_obs ?? "未提供")],
  ];
  const modelRows = [
    ["估计方法", output.strategy || result.method || "未提供"],
    ["模型公式", output.model_formula || result.model_formula || "未提供"],
    ["结果解读", result.main_effect_interpretation || headline],
  ];
  const coefficientRows = Object.entries(coefficients).map(([term, value]) => ({
    term,
    coef: formatNumber(numberOrUndefined(value)),
    se: formatNumber(numberOrUndefined(standardErrors[term])),
    p: formatPValue(numberOrUndefined(pValues[term])),
  }));
  const body = <><AnalysisMarkdown markdown={output.analysis_markdown}/><div className={`effect-summary ${significant ? "positive" : "neutral"}`}>
    <small>核心结论</small>
    <strong>{headline}</strong>
    <span>注意：这里是统计估计结果，因果解释还需要结合平行趋势、溢出效应和同期冲击诊断。</span>
  </div><div className="metric-grid">{rows.map(([name, value]) => <div key={name}><small>{name}</small><strong>{value}</strong></div>)}</div><div className="table-wrap compact"><table><thead><tr><th>说明</th><th>内容</th></tr></thead><tbody>{modelRows.map(([name, value]) => <tr key={name}><td>{name}</td><td>{value}</td></tr>)}</tbody></table></div><details className="details"><summary>查看完整系数表</summary><div className="table-wrap"><table><thead><tr><th>变量</th><th>系数</th><th>标准误</th><th>p 值</th></tr></thead><tbody>{coefficientRows.map(row => <tr key={row.term} className={row.term === mainTerm ? "highlight-row" : ""}><td>{row.term}</td><td>{row.coef}</td><td>{row.se}</td><td>{row.p}</td></tr>)}</tbody></table></div></details><Warnings warnings={output.warnings || result.warnings}/>{output.chart_paths?.length ? <div className="chart-grid">{output.chart_paths.map((path: string) => <img key={path} src={path.replace(/^storage\//, "/storage/").replace(/^.*\/storage\//, "/storage/")} alt="分析图表"/>)}</div> : null}{!embedded && <div className="result-actions"><button className="primary" onClick={() => act(() => api.confirmEstimation(need(), output.id, true, ""))}><CheckCircle2 size={16}/> {output.confirmed_by_user ? "重新确认估计结果" : "确认估计结果"}</button><button onClick={() => act(() => api.confirmEstimation(need(), output.id, false, ""))}>标记为待修正</button></div>}</>;
  if (embedded) return <div className="estimation-embedded">{body}</div>;
  return <section className="result"><div className="result-title"><BarChart3 size={18}/><h2>模型估计结果</h2></div><StatusLine output={output}/>{body}</section>;
}

function pickMainTerm(output: any, coefficients: Record<string, any>) {
  const keys = Object.keys(coefficients);
  if (output.strategy === "DID") return keys.find(key => key.includes(":")) || "treat:post";
  if (keys.includes("ATT")) return "ATT";
  return keys.find(key => !key.startsWith("C(") && key !== "Intercept") || keys[0] || "";
}

function numberOrUndefined(value: any): number | undefined {
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function formatNumber(value: number | undefined) {
  if (value === undefined) return "未提供";
  if (Math.abs(value) >= 1000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)) return value.toExponential(3);
  return value.toFixed(4);
}

function formatPValue(value: number | undefined) {
  if (value === undefined) return "未提供";
  if (value < 0.001) return "< 0.001";
  return value.toFixed(4);
}

function IdentifiabilityResult({ output, confirmPath, act, need }: { output: any; confirmPath?: string; act: any; need: () => number }) {
  const roleRows = Object.entries(output.variable_roles || {}).map(([key, value]) => [label(key), renderValue(value)]);
  const checks = [
    ["样本量", `${output.n_rows} 行，${output.n_cols} 列`],
    ["可识别性状态", output.identifiability_status],
    ["面板结构", renderValue(output.panel_structure)],
    ["处理变量变化", renderValue(output.treatment_variation)],
    ["结果变量可用性", renderValue(output.outcome_availability)],
    ["政策前后信息", renderValue(output.pre_post_availability)],
    ["对照组信息", renderValue(output.control_group_availability)],
  ];
  return <section className="result"><div className="result-title"><Database size={18}/><h2>数据可识别性检查</h2></div><StatusLine output={output}/><AnalysisMarkdown markdown={output.analysis_markdown}/><div className="table-wrap"><table><thead><tr><th>检查项</th><th>结果</th></tr></thead><tbody>{checks.map(([name, value]) => <tr key={name}><td>{name}</td><td>{value}</td></tr>)}</tbody></table></div><details className="details" open><summary>变量角色识别</summary><div className="table-wrap"><table><thead><tr><th>角色</th><th>候选变量</th></tr></thead><tbody>{roleRows.map(([name, value]) => <tr key={name}><td>{name}</td><td>{value}</td></tr>)}</tbody></table></div></details><Warnings warnings={output.warnings}/>{confirmPath ? <div className="result-actions"><EditableResultEditor output={output} path={confirmPath} act={act} need={need} feedback=""/><button className="primary" onClick={() => act(() => api.causalConfirm(need(), confirmPath, true, ""))}><CheckCircle2 size={16}/> 确认当前结果</button><button onClick={() => act(() => api.causalConfirm(need(), confirmPath, false, ""))}>标记为待修正</button></div> : null}</section>;
}

function isDiagnosticsOutput(output: any) {
  return Boolean(output && output.credibility_assessment && output.diagnostics && (output.passed_checks || output.failed_checks));
}

function DiagnosticsResult({ output, confirmPath, act, need }: { output: any; confirmPath?: string; act: any; need: () => number }) {
  const checks = output.diagnostics?.checks || [];
  const statusLabel: Record<string, string> = { passed: "已通过", failed: "未通过", pending: "待检查" };
  return <section className="result"><div className="result-title"><BarChart3 size={18}/><h2>识别假设诊断</h2></div><StatusLine output={output}/><AnalysisMarkdown markdown={output.analysis_markdown}/><div className="effect-summary neutral"><small>诊断结论</small><strong>{diagnosticsSummary(output)}</strong><span>诊断不是“通过/不通过”的机械裁决；它告诉你哪些识别假设已有证据，哪些还需要额外检查。</span></div><div className="table-wrap compact"><table><thead><tr><th>检查项</th><th>状态</th><th>说明</th></tr></thead><tbody>{checks.map((item: any) => <tr key={item.name} className={item.status === "failed" ? "risk-row" : item.status === "passed" ? "highlight-row" : ""}><td>{item.name}</td><td>{statusLabel[item.status] || item.status}</td><td>{item.detail}</td></tr>)}</tbody></table></div><Warnings warnings={output.warnings}/>{confirmPath ? <div className="result-actions"><button className="primary" onClick={() => act(() => api.causalConfirm(need(), confirmPath, true, ""))}><CheckCircle2 size={16}/> 确认诊断结果</button><button onClick={() => act(() => api.causalConfirm(need(), confirmPath, false, ""))}>标记为待修正</button></div> : null}</section>;
}

function diagnosticsSummary(output: any) {
  const credibility = renderValue(output.credibility_assessment);
  const failed = output.failed_checks?.length || 0;
  const passed = output.passed_checks?.length || 0;
  const pending = output.diagnostics?.pending?.length || 0;
  if (failed) return `当前可信度为${credibility}：${failed} 项未通过，${passed} 项已通过，${pending} 项待检查。`;
  return `当前可信度为${credibility}：${passed} 项已有证据，${pending} 项仍需补充诊断。`;
}

function isRobustnessOutput(output: any) {
  return Boolean(output && output.results && (output.interpretation || output.checks_run));
}

function RobustnessHistory({ output, act, need }: { output: any; act: any; need: () => number }) {
  const results = (output.results || []).filter(isRobustnessOutput);
  return <section className="result"><div className="result-title"><RefreshCw size={18}/><h2>历史稳健性结果</h2></div>{results.length ? <RobustnessResult output={results[0]} act={act} need={need} embedded/> : <p className="empty">暂无稳健性结果。</p>}</section>;
}

function RobustnessResult({ output, act, need, embedded = false }: { output: any; act: any; need: () => number; embedded?: boolean }) {
  const implemented = output.results?.implemented || [];
  const unavailable = output.results?.unavailable || output.results?.placeholder || [];
  const stable = Boolean(output.results?.stable);
  const completed = implemented.filter((item: any) => item.status === "completed");
  const summary = stable ? "可运行检查中，核心系数方向总体稳定。" : "已运行部分检查，但稳健性证据仍需谨慎解读。";
  const body = <><AnalysisMarkdown markdown={output.analysis_markdown}/><div className={`effect-summary ${stable ? "positive" : "neutral"}`}><small>稳健性结论</small><strong>{summary}</strong><span>{output.interpretation || "暂无解释。"}</span></div><div className="metric-grid"><div><small>已运行检查</small><strong>{completed.length}</strong></div><div><small>未实现/未运行</small><strong>{unavailable.length}</strong></div><div><small>稳定性判断</small><strong>{stable ? "较稳定" : "需谨慎"}</strong></div></div><div className="table-wrap compact"><table><thead><tr><th>检查</th><th>状态</th><th>核心系数</th><th>p 值</th><th>样本量</th></tr></thead><tbody>{implemented.map((item: any) => <tr key={item.name} className={item.status === "completed" ? "highlight-row" : "risk-row"}><td>{item.name}</td><td>{robustnessStatus(item.status)}</td><td>{formatNumber(numberOrUndefined(item.coefficient))}</td><td>{formatPValue(numberOrUndefined(item.p_value))}</td><td>{item.n_obs || "未提供"}</td></tr>)}</tbody></table></div>{implemented.some((item: any) => item.detail) ? <Warnings warnings={implemented.map((item: any) => item.detail).filter(Boolean)}/> : null}{unavailable.length ? <details className="details" open><summary>未实现或未运行的检查</summary><div className="table-wrap compact"><table><thead><tr><th>检查</th><th>状态</th><th>说明</th></tr></thead><tbody>{unavailable.map((item: any) => typeof item === "string" ? <tr key={item}><td>{item}</td><td>未实现</td><td>当前版本没有真实运行该检查。</td></tr> : <tr key={item.name}><td>{item.name}</td><td>未实现</td><td>{item.detail}</td></tr>)}</tbody></table></div></details> : null}<Warnings warnings={output.warnings}/>{!embedded && <div className="result-actions"><button className="primary" onClick={() => act(() => api.confirmRobustness(need(), true, ""))}><CheckCircle2 size={16}/> 确认稳健性结果</button><button onClick={() => act(() => api.confirmRobustness(need(), false, ""))}>标记为待修正</button></div>}</>;
  if (embedded) return <div className="estimation-embedded">{body}</div>;
  return <section className="result"><div className="result-title"><RefreshCw size={18}/><h2>稳健性与敏感性分析</h2></div>{body}</section>;
}

function robustnessStatus(status: string) {
  if (status === "completed") return "已运行";
  if (status === "concern") return "需关注";
  if (status === "failed") return "失败";
  return status || "未知";
}

function EditableResultEditor({ output, path, act, need, feedback }: { output: any; path: string; act: any; need: () => number; feedback: string }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(JSON.stringify(editablePayload(output), null, 2));
  const [error, setError] = useState("");
  useEffect(() => {
    setDraft(JSON.stringify(editablePayload(output), null, 2));
    setError("");
  }, [output, path]);
  const save = () => {
    try {
      const data = JSON.parse(draft);
      setError("");
      return act(() => api.causalPatch(need(), path, data, feedback));
    } catch {
      setError("JSON 格式不正确，请检查逗号、引号和括号。");
    }
  };
  return <div className="edit-box">
    <button onClick={() => setOpen(!open)}>{open ? "收起编辑" : "编辑当前结果"}</button>
    {open && <><p>直接修改下面的字段，保存后再确认。只改需要修正的内容即可。</p><textarea rows={12} value={draft} onChange={event => setDraft(event.target.value)}/><button className="primary" onClick={save}><CheckCircle2 size={16}/> 保存修改</button>{error && <small>{error}</small>}</>}
  </div>;
}

function editablePayload(output: any) {
  const skip = new Set(["id", "analysis_markdown", "warnings", "warning", "confirmed_by_user", "user_feedback", "chart_paths", "result", "diagnostics"]);
  return Object.fromEntries(Object.entries(output || {}).filter(([key]) => !skip.has(key)));
}

function isConfirmableOutput(output: any, path: string) {
  if (!output || output.error || Array.isArray(output) || output.markdown_content || Array.isArray(output.uploaded)) return false;
  const markers: Record<string, string[]> = {
    "causal-question": ["causal_question_text", "treatment", "outcome", "estimand"],
    "causal-structure": ["confounders", "dag_edges", "mechanism_hypotheses"],
    "counterfactual-plan": ["counterfactual_question", "comparison_group", "counterfactual_source"],
    "assignment-mechanism": ["mechanism_type", "endogeneity_risks", "possible_strategies"],
    "identification-strategy": ["recommended_strategy", "alternative_strategies", "key_assumptions"],
    "data-identifiability-check": ["identifiability_status", "variable_roles"],
    "estimation-setup": ["strategy", "model_formula", "outcome", "treatment"],
    "assumption-diagnostics": ["diagnostic_results", "assumption_status", "credibility_assessment"],
    "causal-effect-interpretation": ["causal_claim", "estimand_interpretation", "credibility_score"],
  };
  return (markers[path] || []).some(key => Object.prototype.hasOwnProperty.call(output, key));
}

function resultTitle(output: any) {
  if (output.causal_question_text) return "因果问题卡片";
  if (output.confounders || output.dag_edges) return "因果结构卡片";
  if (output.counterfactual_question) return "反事实构造卡片";
  if (output.mechanism_type) return "处理分配机制";
  if (output.recommended_strategy) return "识别策略建议";
  if (output.identifiability_status) return "数据可识别性检查";
  if (output.n_obs || output.result || output.coefficients) return "估计与诊断结果";
  if (output.model_formula || output.strategy) return "估计设定";
  if (output.causal_claim) return "因果效应解释";
  return "系统输出";
}

function StatusLine({ output }: { output: any }) {
  const status = output.identifiability_status || output.credibility_label || output.credibility_assessment || output.risk_level || (output.confirmed_by_user ? "已确认" : "待确认");
  return <div className={`status-line ${String(status).includes("not") || String(status).includes("high") || String(status).includes("weak") ? "risk" : ""}`}><strong>状态</strong><span>{renderValue(status)}</span></div>;
}

function DataCard({ item }: { item: any }) {
  const hidden = ["id", "analysis_markdown", "warnings", "warning", "markdown_content", "confirmed_by_user", "user_feedback", "dag_edges"];
  return <><div className="kv-grid">{Object.entries(item || {}).filter(([key]) => !hidden.includes(key)).map(([key, value]) => <div key={key}><strong>{label(key)}</strong><span>{renderValue(value)}</span></div>)}</div><DagEdges edges={item?.dag_edges} treatment={item?.treatment} outcome={item?.outcome}/></>;
}

function DagEdges({ edges, treatment, outcome }: { edges?: any; treatment?: string; outcome?: string }) {
  const parsed = parseDagEdges(edges);
  if (!parsed.length) return null;
  const treat = treatment || "treat";
  const out = outcome || "manufacturing_productivity";
  const grouped = {
    treatmentDrivers: parsed.filter(edge => edge.to === treat),
    outcomeDrivers: parsed.filter(edge => edge.to === out && edge.from !== treat),
    treatmentEffects: parsed.filter(edge => edge.from === treat && edge.to !== out),
    mechanisms: parsed.filter(edge => edge.from !== treat && edge.to === out && /投资|效率|mechanism|digital|management/i.test(edge.from)),
  };
  const used = new Set([...grouped.treatmentDrivers, ...grouped.outcomeDrivers, ...grouped.treatmentEffects, ...grouped.mechanisms].map(edgeKey));
  const other = parsed.filter(edge => !used.has(edgeKey(edge))).slice(0, 12);
  const path = buildMainPath(treat, out, grouped.treatmentEffects, grouped.mechanisms);
  return <section className="dag-panel"><div className="dag-title"><GitBranch size={17}/><div><strong>因果图关系</strong><span>DAG 边已整理为可读路径，原始箭头仍可在下方展开查看。</span></div></div><div className="dag-flow">{path.map((node, index) => <div className="dag-node" key={`${node}-${index}`}><span>{node}</span>{index < path.length - 1 && <b>→</b>}</div>)}</div><div className="dag-groups">
    <DagGroup title="影响政策分配的因素" items={grouped.treatmentDrivers.map(edge => edge.from)} empty="暂未识别"/>
    <DagGroup title="政策可能影响的中介路径" items={grouped.treatmentEffects.map(edge => edge.to)} empty="暂未识别"/>
    <DagGroup title="直接影响结果的控制因素" items={grouped.outcomeDrivers.filter(edge => !grouped.mechanisms.some(item => item.from === edge.from)).map(edge => edge.from)} empty="暂未识别"/>
    <DagGroup title="其他关系" items={other.map(edge => `${edge.from} → ${edge.to}`)} empty="无"/>
  </div><details className="details"><summary>查看原始 DAG 边</summary><div className="dag-edge-list">{parsed.map(edge => <span key={edgeKey(edge)}>{edge.from} → {edge.to}</span>)}</div></details></section>;
}

function DagGroup({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  const unique = Array.from(new Set(items.filter(Boolean)));
  return <div><strong>{title}</strong>{unique.length ? <ul>{unique.map(item => <li key={item}>{item}</li>)}</ul> : <p>{empty}</p>}</div>;
}

function parseDagEdges(edges: any): { from: string; to: string }[] {
  const raw = Array.isArray(edges) ? edges : edges ? [edges] : [];
  return raw.flatMap(item => {
    if (Array.isArray(item) && item.length >= 2) return [{ from: String(item[0]).trim(), to: String(item[1]).trim() }];
    const text = String(item);
    return text.split(";").map(part => {
      const [from, to] = part.split("->").map(value => value?.trim()).filter(Boolean);
      return from && to ? { from, to } : null;
    }).filter(Boolean) as { from: string; to: string }[];
  });
}

function buildMainPath(treatment: string, outcome: string, treatmentEffects: { from: string; to: string }[], mechanisms: { from: string; to: string }[]) {
  const mechanism = treatmentEffects.find(edge => mechanisms.some(item => item.from === edge.to))?.to || treatmentEffects[0]?.to;
  return mechanism ? ["政策/处理", treatment, mechanism, outcome] : ["政策/处理", treatment, outcome];
}

function edgeKey(edge: { from: string; to: string }) {
  return `${edge.from}->${edge.to}`;
}

function Warnings({ warnings }: { warnings?: string[] | string }) {
  const items = Array.isArray(warnings) ? warnings.filter(Boolean) : warnings ? [warnings] : [];
  if (!items.length) return null;
  return <div className="warning"><AlertTriangle size={17}/><div><strong>风险提示</strong>{items.map(item => <p key={item}>{item}</p>)}</div></div>;
}

function renderValue(value: any): string {
  if (value === null || value === undefined || value === "") return "未填写";
  if (Array.isArray(value)) return value.length ? value.map(renderValue).join("；") : "无";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  if (typeof value === "boolean") return value ? "是" : "否";
  const text = String(value);
  const values: Record<string, string> = {
    unclear: "尚不明确",
    randomized: "随机分配",
    policy_pilot: "非随机政策试点",
    staggered_policy: "分批推进政策",
    threshold_based: "阈值分配",
    self_selection: "自选择进入",
    instrument_induced: "工具变量诱导",
    single_treated_unit: "单一处理单位",
    observational_panel: "观察性面板",
    untreated_group_trend: "未处理组趋势",
    low: "低",
    medium: "中",
    high: "高",
    weak: "弱",
    moderate: "中等",
    strong: "强",
    not_supported: "不支持",
    not_credible: "不可信",
  };
  return values[text] || text;
}

function label(key: string) {
  const map: Record<string, string> = { id: "个体/地区标识", time: "时间变量", covariate: "协变量", running: "阈值变量", causal_question_text: "因果问题", strategy: "估计方法", treatment: "处理变量", outcome: "结果变量", unit: "Unit", time_window: "Time Window", target_population: "Target Population", estimand: "Estimand", post_variable: "政策后变量", time_variable: "时间变量", entity_variable: "个体/地区标识", running_variable: "阈值变量", cutoff: "阈值", instrument_variable: "工具变量", covariates: "协变量", fixed_effects: "固定效应", standard_error_type: "标准误类型", cluster_variable: "聚类变量", sample_filter: "样本设定", clarification_questions: "澄清问题", confounders: "混杂变量", mediators: "中介变量", colliders: "碰撞变量", moderators: "调节变量", bad_controls: "坏控制", post_treatment_variables: "政策后变量", mechanism_hypotheses: "机制假设", dag_edges: "DAG 边", counterfactual_question: "反事实问题", comparison_group: "对照组", counterfactual_source: "反事实来源", plausibility_assessment: "可信度", required_evidence: "所需证据", mechanism_type: "分配机制", description: "机制说明", evidence: "判断依据", endogeneity_risks: "内生性风险", possible_strategies: "候选策略", recommended_strategy: "推荐策略", alternative_strategies: "替代策略", counterfactual_logic: "反事实逻辑", key_assumptions: "关键假设", required_data: "数据要求", diagnostics: "诊断要求", risks: "风险", risk_level: "风险等级", credibility_prior: "先验可信度", identifiability_status: "可识别性状态", variable_roles: "变量角色", model_formula: "模型公式", n_obs: "样本量", causal_claim: "因果表述", estimand_interpretation: "估计目标解释", effect_size_interpretation: "效应大小解释", statistical_uncertainty: "统计不确定性", identification_conditions: "识别条件", external_validity: "外推边界", unsupported_claims: "不能支持的结论", limitations: "局限性", credibility_score: "可信度评分", credibility_label: "可信度标签", confirmed_by_user: "用户确认", user_feedback: "用户反馈" };
  return map[key] || key;
}
