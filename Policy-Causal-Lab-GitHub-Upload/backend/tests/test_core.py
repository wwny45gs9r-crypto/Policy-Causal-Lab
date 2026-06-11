import pandas as pd
from app.routers.causal_workflow import _normalize_causal_structure, _select_panel_id
from app.services.causal_engine import run_did, run_event_study
from app.services.data_profiler import infer_variable_roles, profile_dataset
from app.services.system_knowledge_base import chunk_text


def panel():
    rows = []
    for firm in range(8):
        for year in range(2018, 2024):
            treat = int(firm >= 4)
            post = int(year >= 2021)
            rows.append({"firm_id": firm, "year": year, "treat": treat, "post": post, "outcome": firm + year - 2018 + 3 * treat * post, "size": firm + 1})
    return pd.DataFrame(rows)


def test_profile_detects_panel_roles():
    profile = profile_dataset(panel())
    assert profile["roles"]["id"] == ["firm_id"]
    assert profile["roles"]["time"] == ["year"]
    assert profile["method_feasibility"]["DID"]["status"] == "possible"


def test_did_estimates_effect():
    result = run_did(panel(), {"outcome": "outcome", "treat": "treat", "post": "post", "covariates": []})
    assert abs(result["coefficients"]["treat:post"] - 3) < 0.01


def test_event_study_returns_periods():
    result = run_event_study(panel(), {"outcome": "outcome", "treat": "treat", "time": "year", "entity_id": "firm_id", "policy_time": 2021, "window_before": 3, "window_after": 2})
    assert result["method"] == "Event Study"
    assert any(row["relative_time"] == 0 for row in result["relative_time_results"])


def test_chunk_text_overlap():
    chunks = chunk_text("x" * 1000, chunk_size=800, overlap=120)
    assert len(chunks) == 2


def test_panel_id_prefers_explicit_id_column():
    df = pd.DataFrame({"province_name": ["A"], "province_id": ["P01"], "year": [2020], "outcome": [1.0]})
    roles = infer_variable_roles(df)
    assert roles["id"][0] == "province_id"
    assert _select_panel_id(list(df.columns)) == "province_id"


def test_causal_structure_normalizes_directed_edges_and_post_treatment_variables():
    data = {
        "confounders": ["gdp_pc_log", "industrial_share", "not_in_data"],
        "mediators": ["企业数字化投资"],
        "bad_controls": ["政策后新增数字化设备数量"],
        "dag_edges": [["gdp_pc_log", "digital_subsidy"]],
    }
    normalized = _normalize_causal_structure(
        data,
        "digital_subsidy",
        "manufacturing_productivity",
        ["digital_subsidy", "manufacturing_productivity", "gdp_pc_log", "industrial_share"],
    )
    assert "digital_subsidy -> manufacturing_productivity" in normalized["dag_edges"]
    assert "gdp_pc_log -> digital_subsidy" in normalized["dag_edges"]
    assert "industrial_share -> manufacturing_productivity" in normalized["dag_edges"]
    assert "not_in_data" not in normalized["confounders"]
    assert "企业数字化投资" in normalized["post_treatment_variables"]
