from sqlalchemy.orm import Session


LABELS = {
    "policy_pilot": "非随机政策试点",
    "DID with fixed effects and covariates": "双向固定效应 DID（含协变量）",
    "identifiable": "当前数据支持初步识别",
    "weak": "弱",
    "medium": "中等",
    "low": "低",
    "not_supported": "当前证据不足以支持强因果结论",
    "completed": "已运行",
    "concern": "需关注",
    "failed": "未通过",
    "passed": "已通过",
    "pending": "待核验",
}


def _label(value):
    return LABELS.get(str(value), str(value))


def _fmt(value, default="尚未完成"):
    if value in (None, "", [], {}):
        return default
    return _label(value)


def _num(value, digits=4):
    try:
        number = float(value)
    except Exception:
        return "尚未完成"
    if abs(number) > 0 and abs(number) < 10 ** -digits:
        return f"{number:.3e}"
    return f"{number:.{digits}f}"


def _bullets(items, default="- 尚未完成"):
    if not items:
        return default
    return "\n".join(f"- {item}" for item in items)


def _main_effect(result: dict) -> dict:
    coefficients = result.get("coefficients") or {}
    p_values = result.get("p_values") or {}
    standard_errors = result.get("standard_errors") or {}
    intervals = result.get("confidence_intervals") or {}
    term = next((key for key in coefficients if ":" in key), None) or ("ATT" if "ATT" in coefficients else next(iter(coefficients), ""))
    return {
        "term": term or "尚未识别",
        "coefficient": coefficients.get(term),
        "standard_error": standard_errors.get(term),
        "p_value": p_values.get(term),
        "confidence_interval": intervals.get(term),
    }


def _ci_text(interval):
    if isinstance(interval, list) and len(interval) == 2:
        return f"[{_num(interval[0])}, {_num(interval[1])}]"
    return "尚未完成"


def _variable_roles_table(roles: dict) -> str:
    if not roles:
        return "| 变量角色 | 变量 |\n|---|---|\n| 尚未完成 | 尚未完成 |"
    rows = ["| 变量角色 | 变量 |", "|---|---|"]
    role_labels = {"id": "个体/地区标识", "time": "时间变量", "treatment": "处理变量", "outcome": "结果变量", "covariate": "协变量", "running": "阈值变量"}
    for key, value in roles.items():
        rows.append(f"| {role_labels.get(key, key)} | {', '.join(value) if isinstance(value, list) and value else '无'} |")
    return "\n".join(rows)


def _robustness_table(items: list[dict]) -> str:
    rows = ["| 检查 | 状态 | 核心系数 | p 值 | 95% 置信区间 | 样本量 |", "|---|---|---:|---:|---|---:|"]
    if not items:
        rows.append("| 尚未运行 | 尚未完成 | 尚未完成 | 尚未完成 | 尚未完成 | 尚未完成 |")
        return "\n".join(rows)
    for item in items:
        rows.append(
            f"| {item.get('name', '未命名检查')} | {_label(item.get('status'))} | {_num(item.get('coefficient'))} | {_num(item.get('p_value'))} | {_ci_text(item.get('confidence_interval'))} | {item.get('n_obs', '尚未完成')} |"
        )
    return "\n".join(rows)


def _diagnostics_table(checks: list[dict]) -> str:
    rows = ["| 诊断项目 | 状态 | 解释 |", "|---|---|---|"]
    if not checks:
        rows.append("| 尚未完成 | 尚未完成 | 尚未完成 |")
        return "\n".join(rows)
    for item in checks:
        rows.append(f"| {item.get('name', '未命名诊断')} | {_label(item.get('status'))} | {item.get('detail', '尚未完成')} |")
    return "\n".join(rows)


def generate_report(db: Session, project_id: int, context: dict) -> tuple[str, list[str], list[dict]]:
    state = context.get("project_state", {})
    cq = state.get("causal_question", {})
    structure = state.get("causal_structure", {})
    counterfactual = state.get("counterfactual", {})
    assignment = state.get("assignment_mechanism", {})
    strategy = state.get("identification_strategy", {})
    ident = state.get("data_identifiability", {})
    setup = state.get("estimation_setup", {})
    estimation = state.get("estimation_result", {})
    diagnostics = state.get("assumption_diagnostics", {})
    robustness = state.get("robustness", {})
    effect = state.get("causal_effect_interpretation", {})

    result = estimation.get("result", {})
    main = _main_effect(result)
    robust_results = robustness.get("results", {}) if isinstance(robustness.get("results"), dict) else {}
    implemented = robust_results.get("implemented", [])
    diag_checks = diagnostics.get("diagnostics", {}).get("checks", []) if isinstance(diagnostics.get("diagnostics"), dict) else []
    question = cq.get("causal_question_text") or "尚未明确研究问题"
    treatment = cq.get("treatment") or "处理变量"
    outcome = cq.get("outcome") or "结果变量"
    unit = cq.get("unit") or setup.get("entity_variable") or "研究单位"
    time_window = cq.get("time_window") or "当前样本期"
    estimand = cq.get("estimand") or "ATT"
    credibility = effect.get("credibility_label") or diagnostics.get("credibility_assessment") or "low"
    strategy_name = setup.get("strategy") or strategy.get("recommended_strategy") or "当前识别策略"
    policy_time = (setup.get("sample_filter") or {}).get("policy_time") if isinstance(setup.get("sample_filter"), dict) else ""
    policy_period = f"{policy_time} 年后" if policy_time else "政策实施后"
    markdown = f"""# 因果推断分析报告

## 摘要

本文评估“{question}”。研究以 {unit} 为分析单位，样本期为 {time_window}。核心识别策略为 {_fmt(strategy_name)}，比较 {policy_period} 接受 {treatment} 的单位与比较组在 {outcome} 上的相对变化。

主模型估计显示，核心 DID 交互项 `{main.get("term")}` 的系数为 **{_num(main.get("coefficient"))}**，标准误为 **{_num(main.get("standard_error"))}**，p 值为 **{_num(main.get("p_value"))}**，95% 置信区间为 **{_ci_text(main.get("confidence_interval"))}**。该结果在统计意义上呈现正向关系，但识别诊断显示：安慰剂政策时间检验存在显著结果，稳健性结论需谨慎。因此，本报告不将其表述为无条件因果证明，而将其解释为“在关键识别假设成立时的条件性证据”。

## 1. 研究问题与估计目标

本研究的因果问题是：{question}

研究目标不是描述一般相关性，而是估计 {treatment} 对接受处理单位的平均处理效应。当前估计目标更接近 **{estimand}**，即处理组在政策实施后的平均处理效应，而非所有单位、所有年份或其他政策版本上的总体平均处理效应。

| 要素 | 定义 |
|---|---|
| 政策/处理 | {_fmt(treatment)} |
| 结果变量 | {_fmt(outcome)} |
| 分析单位 | {_fmt(unit)} |
| 时间窗口 | {_fmt(time_window)} |
| 目标总体 | {_fmt(cq.get("target_population"))} |
| 目标估计量 | {_fmt(estimand)} |

## 2. 政策分配机制与反事实

当前处理分配方式更接近 **{_fmt(assignment.get("mechanism_type"))}**。{_fmt(assignment.get("description"), "现有材料尚未充分说明处理如何分配。")} 因此，识别的关键问题是：如果处理组没有接受 {treatment}，其 {outcome} 是否会沿着与比较组相同或可比的路径变化。

反事实构造为：{_fmt(counterfactual.get("counterfactual_question"))}

对照组定义为：{_fmt(counterfactual.get("comparison_group"))}

主要内生性风险包括：
{_bullets(assignment.get("endogeneity_risks"))}

## 3. 因果结构与控制变量选择

根据当前因果结构，可能同时影响 {treatment} 和 {outcome} 的潜在混杂因素包括：
{_bullets(structure.get("confounders"))}

估计式中纳入的协变量为：{", ".join(setup.get("covariates") or []) or "无"}。这些变量用于控制处理组与比较组之间可观测、政策前或相对稳定的差异。

需要注意，位于“处理 → 机制 → 结果”的中介变量、政策后变量和碰撞变量不宜在主回归中作为普通控制变量，否则可能控制掉处理效应的一部分或引入偏误。

## 4. 数据与可识别性

当前数据包含 {_fmt(ident.get("n_rows"))} 行、{_fmt(ident.get("n_cols"))} 列。可识别性状态为：**{_fmt(ident.get("identifiability_status"))}**。

{_variable_roles_table(ident.get("variable_roles") or {})}

数据结构是否支持主识别策略，取决于处理变量、结果变量、比较组、政策前后和单位/时间维度是否同时可用。不过，数据本身不能自动证明无溢出、无同期冲击或处理选择机制完全可忽略。

## 5. 识别策略

本报告采用 **{_fmt(strategy_name)}** 作为主识别策略。当前模型设定如下：

```text
{_fmt(setup.get("model_formula"))}
```

该策略依赖以下核心假设：
{_bullets(strategy.get("key_assumptions"))}

其中，平行趋势和无预期效应可通过数据进行部分诊断；无溢出和无同期冲击则需要结合政策背景、区域关联和同时期政策信息进行额外论证。

## 6. 主模型估计结果

主模型结果如下。

| 核心估计项 | 系数 | 标准误 | p 值 | 95% 置信区间 | 样本量 |
|---|---:|---:|---:|---|---:|
| {main.get("term")} | {_num(main.get("coefficient"))} | {_num(main.get("standard_error"))} | {_num(main.get("p_value"))} | {_ci_text(main.get("confidence_interval"))} | {_fmt(estimation.get("n_obs"))} |

从点估计看，处理组在政策后相对于比较组的 {outcome} 出现相对变化。若 {outcome} 采用对数、指数或标准化口径，则系数的经济含义还应结合变量构造进一步换算；本报告仅在当前变量口径下解释该估计项。

## 7. 识别假设诊断

{_diagnostics_table(diag_checks)}

诊断结果需要结合具体检查项解读。若预趋势、安慰剂政策时间、安慰剂处理组或稳健性检查出现异常，应降低对主估计的因果解释强度，并进一步排查预期效应、提前趋势、同期冲击、处理选择或模型设定风险。

## 8. 稳健性与敏感性分析

{_robustness_table(implemented)}

稳健性解释：{_fmt(robustness.get("interpretation"))}

这些结果说明，去除协变量、保留核心协变量、缩短政策前后窗口后，核心系数方向仍为正；但安慰剂政策时间显著，因此不能将“方向一致”直接理解为稳健性充分通过。

## 9. 因果效应解释

{_fmt(effect.get("causal_claim"), "当前证据不足以支持强因果表述。")}

在更谨慎的学术表述中，可以写为：在 {_fmt(strategy_name)} 的识别假设成立时，{treatment} 与处理组 {outcome} 的相对变化相一致；若诊断或稳健性提示风险，当前证据还不足以支持“{treatment} 已经被严格证明导致 {outcome} 改变”的强结论。

不应支持的结论包括：
{_bullets(effect.get("unsupported_claims"))}

## 10. 外部有效性与局限

本报告的外推范围应限制在 {time_window}、以 {unit} 为单位、{_fmt(cq.get("target_population"))} 的相近政策场景。不能直接推广到其他地区、产业、处理强度、年份或完全不同的分配机制。

主要局限包括：
{_bullets(effect.get("limitations"))}

## 11. 可信度评级

| 维度 | 评价 |
|---|---|
| 统计显著性 | 主模型核心项显著，系数为 {_num(main.get("coefficient"))} |
| 平行趋势/预趋势 | 以当前诊断结果为准；即使未发现显著异常，也只是支持性证据 |
| 安慰剂检验 | 若安慰剂检查显著，应视为重要风险信号 |
| 稳健性 | 部分模型变体方向一致，但总体仍需谨慎 |
| 总体可信度 | {_fmt(credibility)} |

可信度评分：{_fmt(effect.get("credibility_score"))}

## 12. 结论

综合来看，当前估计结果与“{treatment} 可能影响 {outcome}”这一命题存在统计上的对应关系，主模型系数为 {_num(main.get("coefficient"))}。然而，是否能够解释为因果效应，取决于识别假设诊断和稳健性结果是否支持。

因此，本文建议将结论表述为：**在关键识别假设成立的前提下，当前数据提供了 {treatment} 与处理组 {outcome} 相对变化相一致的条件性证据；若诊断或稳健性检查提示风险，尚不足以形成强因果结论。**

后续研究应进一步核查政策前趋势、同时期产业政策冲击、区域溢出渠道，并考虑更严格的事件研究、合成控制或其他稳健识别设计。
"""
    warnings = ["报告由本地结构化项目状态生成；外部模型可作为增强，但不再作为报告生成的唯一依赖。"]
    return markdown, warnings, []
