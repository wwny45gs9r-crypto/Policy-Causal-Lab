import json
import pandas as pd
from .deepseek_client import DeepSeekClient


ROLE_KEYS = ["id", "time", "treatment", "post", "outcome", "covariate", "running", "instrument"]


def sample_columns(df: pd.DataFrame, max_columns: int = 80, max_values: int = 6) -> list[dict]:
    rows = []
    for column in list(df.columns)[:max_columns]:
        values = [str(value) for value in df[column].dropna().head(max_values).tolist()]
        rows.append({
            "name": str(column),
            "dtype": str(df[column].dtype),
            "missing": int(df[column].isna().sum()),
            "sample_values": values,
        })
    return rows


def infer_roles_with_ai(df: pd.DataFrame, rule_roles: dict, project_state: dict) -> dict:
    prompt = {
        "task": "根据研究上下文、列名、数据类型和样例值推断变量角色。只返回 JSON，不要解释。",
        "role_schema": {key: "array of column names" for key in ROLE_KEYS},
        "rules": [
            "outcome 是政策可能影响的结果变量",
            "treatment 是政策暴露、试点、处理组或强度变量",
            "post 是政策后、实施后或时间断点指示变量",
            "id 是地区、企业、个人等面板个体标识",
            "time 是年份、月份、日期等时间变量",
            "covariate 是前置控制变量或混杂因素",
            "running 是 RDD 的阈值排序变量",
            "instrument 是 IV/2SLS 的工具变量候选",
        ],
        "project_state": project_state,
        "rule_roles": rule_roles,
        "columns": sample_columns(df),
    }
    result = DeepSeekClient().complete(
        "你是因果推断数据语义识别助手。必须输出 JSON 对象，包含 roles 和 notes。",
        json.dumps(prompt, ensure_ascii=False, default=str)[:16000],
        json_mode=True,
    )
    content = result.get("content") if isinstance(result.get("content"), dict) else {}
    roles = content.get("roles", {}) if isinstance(content, dict) else {}
    merged = {key: list(dict.fromkeys([*(rule_roles.get(key, []) or []), *(roles.get(key, []) or [])])) for key in ROLE_KEYS}
    return {
        "roles": merged,
        "notes": content.get("notes", "") if isinstance(content, dict) else "",
        "warning": result.get("warning", ""),
    }
