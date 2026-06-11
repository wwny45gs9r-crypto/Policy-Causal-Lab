import pandas as pd


def default_cleaning_plan(profile: dict) -> dict:
    missing = profile.get("missing_summary", {})
    empty_columns = [name for name, count in missing.items() if count == profile.get("n_rows")]
    partial_missing = [name for name, count in missing.items() if 0 < count < profile.get("n_rows")]
    return {
        "drop_duplicates": True,
        "drop_all_missing_columns": True,
        "missing_strategy": "keep",
        "empty_columns": empty_columns,
        "columns_with_missing": partial_missing,
        "notes": "保留部分缺失值，建模时按所选变量处理；删除完全为空的列和重复行。",
    }


def apply_cleaning(df: pd.DataFrame, plan: dict) -> tuple[pd.DataFrame, dict]:
    before = df.shape
    if plan.get("drop_duplicates", True):
        df = df.drop_duplicates()
    if plan.get("drop_all_missing_columns", True):
        df = df.dropna(axis=1, how="all")
    if plan.get("missing_strategy") == "drop_rows":
        df = df.dropna()
    return df, {"before": list(before), "after": list(df.shape)}
