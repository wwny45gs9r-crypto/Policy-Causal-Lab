from pathlib import Path
import math
import pandas as pd


ROLE_KEYWORDS = {
    "id": ["id", "code", "city", "firm", "province", "county", "地区", "城市", "企业"],
    "time": ["year", "month", "date", "time", "年份", "月份", "日期"],
    "treatment": ["treat", "treated", "policy", "pilot", "group", "试点", "政策", "处理组"],
}


def read_dataset(file_path: str) -> pd.DataFrame:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_path)
    if suffix == ".dta":
        return pd.read_stata(file_path)
    raise ValueError(f"不支持的数据文件类型: {suffix}")


def infer_variable_roles(df: pd.DataFrame) -> dict:
    columns = list(df.columns)
    role = lambda name: [c for c in columns if any(k in str(c).lower() for k in ROLE_KEYWORDS[name])]
    raw_ids, times, treatments = role("id"), role("time"), role("treatment")
    id_priority = ["province_id", "city_id", "county_id", "firm_id", "school_id", "unit_id", "id"]
    lowered = {str(column).lower(): column for column in raw_ids}
    ids = [lowered[name] for name in id_priority if name in lowered]
    ids += [column for column in raw_ids if column not in ids and (str(column).lower().endswith("_id") or str(column).lower() in {"id", "code"})]
    ids += [column for column in raw_ids if column not in ids]
    post_like = [c for c in columns if any(k in str(c).lower() for k in ["post", "after", "政策后"])]
    excluded = set(ids + times + treatments + post_like)
    outcomes = [c for c in columns if pd.api.types.is_numeric_dtype(df[c]) and c not in excluded]
    covariates = outcomes[1:] if len(outcomes) > 1 else []
    running = [c for c in columns if any(k in str(c).lower() for k in ["score", "threshold", "cutoff", "分数", "阈值"])]
    return {"id": ids, "time": times, "treatment": treatments, "outcome": outcomes, "covariate": covariates, "running": running}


def check_method_feasibility(df: pd.DataFrame, roles: dict) -> dict:
    yes = lambda ok, reason: {"status": "possible" if ok else "not_recommended", "reason": reason}
    return {
        "DID": yes(bool(roles["treatment"] and roles["time"] and roles["outcome"]), "需要处理变量、时间变量和结果变量"),
        "Fixed Effects": yes(bool(roles["id"] and roles["time"] and roles["outcome"]), "需要个体、时间和结果变量"),
        "PSM": yes(bool(roles["treatment"] and len(roles["covariate"]) >= 2 and roles["outcome"]), "需要处理变量、结果变量和多个协变量"),
        "RDD": yes(bool(roles["running"]), "需要 running variable"),
        "IV": {"status": "risky", "reason": "需要用户明确指定工具变量并论证排除性限制"},
        "OLS": yes(bool(roles["outcome"]), "至少需要一个数值型结果变量"),
        "Event Study": yes(bool(roles["treatment"] and roles["time"] and roles["outcome"]), "需要处理变量、时间变量和结果变量"),
    }


def _clean_number(value):
    if pd.isna(value):
        return None
    number = float(value)
    if math.isinf(number) or math.isnan(number):
        return None
    return round(number, 4)


def descriptive_statistics(df: pd.DataFrame) -> dict:
    numeric = {}
    categorical = {}
    for column in df.columns:
        series = df[column]
        missing = int(series.isna().sum())
        missing_rate = round(missing / len(df), 4) if len(df) else 0
        if pd.api.types.is_numeric_dtype(series):
            desc = series.describe(percentiles=[0.25, 0.5, 0.75])
            numeric[str(column)] = {
                "count": int(desc.get("count", 0)),
                "missing": missing,
                "missing_rate": missing_rate,
                "mean": _clean_number(desc.get("mean")),
                "std": _clean_number(desc.get("std")),
                "min": _clean_number(desc.get("min")),
                "p25": _clean_number(desc.get("25%")),
                "median": _clean_number(desc.get("50%")),
                "p75": _clean_number(desc.get("75%")),
                "max": _clean_number(desc.get("max")),
            }
        else:
            values = series.dropna().astype(str)
            counts = values.value_counts().head(8)
            categorical[str(column)] = {
                "count": int(values.shape[0]),
                "missing": missing,
                "missing_rate": missing_rate,
                "unique": int(values.nunique()),
                "top_values": [{"value": str(k), "count": int(v)} for k, v in counts.items()],
            }
    return {"numeric": numeric, "categorical": categorical}


def descriptive_summary(stats: dict) -> str:
    numeric_count = len(stats.get("numeric", {}))
    categorical_count = len(stats.get("categorical", {}))
    high_missing = []
    for section in ("numeric", "categorical"):
        for name, item in stats.get(section, {}).items():
            if item.get("missing_rate", 0) >= 0.3:
                high_missing.append(name)
    return (
        f"已完成描述性统计分析：识别出 {numeric_count} 个数值变量、{categorical_count} 个非数值/分类变量。"
        f"{'缺失率较高的变量包括：' + '、'.join(high_missing[:8]) + '。' if high_missing else '未发现缺失率超过 30% 的变量。'}"
        "下方变量角色为 AI 结合研究上下文、列名和样例值的辅助判断，仍建议研究者人工确认。"
    )


def profile_dataset(df: pd.DataFrame, roles: dict | None = None, semantic_notes: str = "", semantic_warning: str = "") -> dict:
    roles = roles or infer_variable_roles(df)
    stats = descriptive_statistics(df)
    summary = descriptive_summary(stats)
    return {
        "n_rows": len(df), "n_cols": len(df.columns), "columns": list(df.columns),
        "missing_summary": {str(k): int(v) for k, v in df.isna().sum().items()},
        "variable_types": {str(k): str(v) for k, v in df.dtypes.items()},
        "descriptive_summary": summary,
        "descriptive_statistics": stats,
        "roles": roles,
        "semantic_notes": semantic_notes,
        "semantic_warning": semantic_warning,
        "method_feasibility": {**check_method_feasibility(df, roles), "_roles": roles, "_semantic_notes": semantic_notes, "_semantic_warning": semantic_warning, "_descriptive_summary": summary, "_descriptive_statistics": stats},
    }
