METHOD_LIBRARY = {
    "OLS": ("executable", "作为基准回归估计", ["线性设定合理", "控制混杂变量充分"], "至少需要结果变量和解释变量"),
    "Logit / Probit": ("design", "二元结果变量的响应模型", ["正确指定链接函数", "样本量足够"], "需要二元结果变量"),
    "DID": ("executable", "政策前后处理组与对照组比较", ["平行趋势", "无同期差异化冲击"], "需要处理变量、时间变量和结果变量"),
    "Staggered DID": ("design", "处理分批实施政策下的动态和异质效应", ["分批实施时点清楚", "处理效应异质性处理得当"], "需要分批政策时点和面板数据"),
    "DDD": ("design", "在双重差分基础上加入第三维差异", ["第三维对照合理", "无三重差异同期冲击"], "需要三组可比较维度"),
    "Event Study": ("executable", "观察动态效应并辅助检查趋势", ["政策时点可识别", "平行趋势"], "需要处理变量、时间变量和结果变量"),
    "Fixed Effects": ("executable", "控制不随时间变化的个体异质性", ["面板结构有效", "解释变量存在组内变化"], "需要个体、时间和结果变量"),
    "IV / 2SLS": ("design", "处理潜在内生性", ["相关性", "排除性限制", "单调性"], "需要用户明确工具变量"),
    "RDD": ("design", "阈值附近局部比较", ["阈值不可操纵", "阈值附近连续性"], "需要 running variable 和 cutoff"),
    "Fuzzy RDD": ("design", "阈值改变处理概率但不完全决定处理状态", ["阈值处处理概率跳跃", "局部排除性限制"], "需要 running variable、cutoff 和处理变量"),
    "PSM": ("executable", "在可观测协变量上构造可比对照组", ["条件独立性", "共同支撑"], "需要处理变量、结果变量和多个协变量"),
    "Entropy Balancing": ("design", "用权重精确平衡协变量矩", ["协变量可观测且足够丰富", "权重不过度集中"], "需要处理变量和协变量"),
    "PSM-DID": ("design", "先匹配再进行双重差分", ["条件独立性", "共同支撑", "平行趋势"], "需要协变量、处理变量、时间变量和结果变量"),
    "Synthetic Control": ("design", "为单一处理单元构造合成对照", ["较长政策前时期", "供体池未受政策影响"], "需要单一或少量处理单元和长面板"),
    "Synthetic DID": ("design", "结合合成控制和 DID 权重", ["政策前拟合充分", "供体池可比"], "需要面板数据和较长政策前窗口"),
    "Interrupted Time Series": ("design", "分析单一时间序列在政策节点前后的变化", ["无同期结构断点", "趋势形式合理"], "需要长时间序列"),
    "Placebo Test": ("diagnostic", "用伪政策时点、伪处理组或伪结果检查稳健性", ["安慰剂设定不应产生真实效应"], "需要已确定的主识别策略"),
    "Sensitivity Analysis": ("diagnostic", "评估未观测混杂或模型设定变化的影响", ["敏感性参数有解释意义"], "需要主模型结果"),
    "Heterogeneous Treatment Effects": ("design", "检验不同地区、行业或群体的政策效应差异", ["分组事前确定", "避免过度挖掘"], "需要分组变量或交互项"),
    "Causal Forest / DML": ("design", "用机器学习辅助估计异质效应或控制高维混杂", ["交叉拟合", "可解释性与外推限制"], "需要较大样本和丰富协变量"),
}


def recommend_methods(profile: dict) -> list[dict]:
    items = []
    feasibility_map = profile.get("method_feasibility", {})
    for name, (support_level, why, assumptions, requirement) in METHOD_LIBRARY.items():
        feasibility = feasibility_map.get(name)
        if not feasibility and name == "IV / 2SLS":
            feasibility = feasibility_map.get("IV")
        if not feasibility:
            status = "risky" if support_level in {"design", "diagnostic"} else "not_recommended"
            feasibility = {"status": status, "reason": requirement}
        items.append({
            "method_name": name,
            "support_level": support_level,
            "why_recommended": why,
            "required_assumptions": assumptions,
            "data_requirements": feasibility["reason"],
            "risks": [] if feasibility["status"] == "possible" else [feasibility["reason"]],
            "suggested_diagnostics": ["检查样本量", "检查变量缺失", "核验模型假设"],
            "feasibility_status": feasibility["status"],
        })
    return items
