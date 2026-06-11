import math
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors


def _result(model, method: str, formula: str, main_term: str | None = None) -> dict:
    term = main_term or next(iter(model.params.index), "")
    ci = model.conf_int()
    return {
        "method": method, "model_formula": formula, "n_obs": int(model.nobs),
        "coefficients": {str(k): float(v) for k, v in model.params.items()},
        "standard_errors": {str(k): float(v) for k, v in model.bse.items()},
        "p_values": {str(k): float(v) for k, v in model.pvalues.items()},
        "confidence_intervals": {str(k): [float(v[0]), float(v[1])] for k, v in ci.iterrows()},
        "main_effect_interpretation": f"核心估计项 {term} 的系数为 {float(model.params.get(term, math.nan)):.4f}。",
    }


def _controls(spec: dict) -> str:
    return " + ".join(spec.get("covariates", []))


def run_ols(df: pd.DataFrame, spec: dict) -> dict:
    outcome = spec["outcome"]
    rhs = " + ".join([spec.get("treat", "")] + spec.get("covariates", [])).strip(" +")
    if not rhs:
        raise ValueError("OLS 至少需要一个解释变量")
    formula = f"{outcome} ~ {rhs}"
    return _result(smf.ols(formula, data=df).fit(cov_type="HC1"), "OLS", formula, spec.get("treat"))


def run_did(df: pd.DataFrame, spec: dict) -> dict:
    required = ["outcome", "treat", "post"]
    if any(not spec.get(k) for k in required):
        raise ValueError("DID 需要 outcome、treat 和 post")
    interaction = f"{spec['treat']}:{spec['post']}"
    has_fixed_effects = bool(spec.get("entity_fixed_effects") or spec.get("time_fixed_effects"))
    rhs = interaction if has_fixed_effects else f"{spec['treat']} * {spec['post']}"
    if _controls(spec):
        rhs += " + " + _controls(spec)
    if spec.get("entity_fixed_effects") and spec.get("entity_id"):
        rhs += f" + C({spec['entity_id']})"
    if spec.get("time_fixed_effects") and spec.get("time_id"):
        rhs += f" + C({spec['time_id']})"
    formula = f"{spec['outcome']} ~ {rhs}"
    model = smf.ols(formula, data=df)
    if spec.get("cluster_robust") and spec.get("entity_id"):
        fitted = model.fit(cov_type="cluster", cov_kwds={"groups": df.loc[model.data.row_labels, spec["entity_id"]]})
    else:
        fitted = model.fit(cov_type="HC1")
    return _result(fitted, "DID", formula, interaction)


def run_fixed_effects(df: pd.DataFrame, spec: dict) -> dict:
    if not all(spec.get(k) for k in ["outcome", "entity_id", "time_id"]):
        raise ValueError("Fixed Effects 需要 outcome、entity_id 和 time_id")
    variables = [spec.get("treat", "")] + spec.get("covariates", [])
    rhs = " + ".join(v for v in variables if v)
    if not rhs:
        raise ValueError("Fixed Effects 至少需要一个解释变量")
    formula = f"{spec['outcome']} ~ {rhs} + C({spec['entity_id']}) + C({spec['time_id']})"
    return _result(smf.ols(formula, data=df).fit(cov_type="HC1"), "Fixed Effects", formula, spec.get("treat"))


def run_psm(df: pd.DataFrame, spec: dict) -> dict:
    outcome, treat, covariates = spec.get("outcome"), spec.get("treat"), spec.get("covariates", [])
    if not outcome or not treat or len(covariates) < 1:
        raise ValueError("PSM 需要 outcome、treat 和至少一个 covariate")
    work = df[[outcome, treat] + covariates].dropna().copy()
    if work[treat].nunique() != 2:
        raise ValueError("PSM 的处理变量必须是二元变量")
    work["propensity_score"] = LogisticRegression(max_iter=1000).fit(work[covariates], work[treat]).predict_proba(work[covariates])[:, 1]
    treated, control = work[work[treat] == 1], work[work[treat] == 0]
    if treated.empty or control.empty:
        raise ValueError("PSM 需要同时存在处理组和对照组")
    idx = NearestNeighbors(n_neighbors=1).fit(control[["propensity_score"]]).kneighbors(treated[["propensity_score"]], return_distance=False).ravel()
    matched_control = control.iloc[idx]
    att = float(treated[outcome].mean() - matched_control[outcome].mean())
    return {"method": "PSM", "model_formula": f"{treat} ~ {' + '.join(covariates)}", "n_obs": int(len(treated) * 2), "coefficients": {"ATT": att}, "standard_errors": {}, "p_values": {}, "confidence_intervals": {}, "main_effect_interpretation": f"匹配后的 ATT 为 {att:.4f}。"}


def run_event_study(df: pd.DataFrame, spec: dict) -> dict:
    required = ["outcome", "treat", "time", "entity_id", "policy_time"]
    if any(spec.get(key) in (None, "") for key in required):
        raise ValueError("Event Study 需要 outcome、treat、time、entity_id 和 policy_time")
    work = df.copy()
    work["_relative_time"] = work[spec["time"]] - int(spec["policy_time"])
    before, after = int(spec.get("window_before", 3)), int(spec.get("window_after", 3))
    work = work[work["_relative_time"].between(-before, after)].copy()
    warnings = [] if (work["_relative_time"] < 0).sum() else ["缺少政策前样本，无法检验平行趋势"]
    terms, mapping = [], {}
    for relative_time in range(-before, after + 1):
        if relative_time == -1:
            continue
        name = f"_event_{'m' + str(abs(relative_time)) if relative_time < 0 else 'p' + str(relative_time)}"
        work[name] = ((work["_relative_time"] == relative_time) & (work[spec["treat"]] == 1)).astype(int)
        terms.append(name); mapping[name] = relative_time
    rhs = " + ".join(terms + spec.get("covariates", []) + [f"C({spec['entity_id']})", f"C({spec['time']})"])
    formula = f"{spec['outcome']} ~ {rhs}"
    model = smf.ols(formula, data=work).fit(cov_type="HC1")
    ci = model.conf_int()
    periods = [{"relative_time": value, "coef": float(model.params[name]), "std_err": float(model.bse[name]), "p_value": float(model.pvalues[name]), "ci_low": float(ci.loc[name, 0]), "ci_high": float(ci.loc[name, 1])} for name, value in mapping.items()]
    return {"method": "Event Study", "model_formula": formula, "n_obs": int(model.nobs), "relative_time_results": periods, "coefficients": {str(item["relative_time"]): item["coef"] for item in periods}, "standard_errors": {str(item["relative_time"]): item["std_err"] for item in periods}, "p_values": {str(item["relative_time"]): item["p_value"] for item in periods}, "confidence_intervals": {str(item["relative_time"]): [item["ci_low"], item["ci_high"]] for item in periods}, "warnings": warnings, "main_effect_interpretation": "事件研究系数展示相对政策时点的动态效应，基准期为政策前一期。"}


def run_analysis(df: pd.DataFrame, method_plan: dict) -> dict:
    method, spec = method_plan["selected_method"], method_plan["model_spec"]
    missing = [c for c in [spec.get("outcome"), spec.get("treat"), spec.get("post"), spec.get("entity_id"), spec.get("time_id")] + spec.get("covariates", []) if c and c not in df.columns]
    if missing:
        raise ValueError(f"数据中缺少变量: {', '.join(missing)}")
    runners = {"OLS": run_ols, "DID": run_did, "Fixed Effects": run_fixed_effects, "PSM": run_psm, "Event Study": run_event_study}
    if method not in runners:
        raise ValueError(f"MVP 尚未实现方法: {method}")
    return runners[method](df, spec)
