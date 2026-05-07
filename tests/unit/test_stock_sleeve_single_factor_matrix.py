from __future__ import annotations

from backend.research.stock_sleeve_single_factor_matrix import build_stock_sleeve_single_factor_matrix


def test_build_stock_sleeve_single_factor_matrix_uses_current_active_sources() -> None:
    result = build_stock_sleeve_single_factor_matrix(write_outputs=False)
    meta = dict(result["meta"])
    window_matrix = result["window_matrix"]
    stability_matrix = result["stability_matrix"]

    assert meta["family_count"] == 10
    assert meta["window_keys"] == ["1217", "1222", "1226"]
    assert meta["family_factor_count"] == len(stability_matrix)
    assert meta["factor_window_row_count"] == len(window_matrix)

    moneyflow_rows = window_matrix.loc[window_matrix["family"] == "moneyflow"].copy()
    assert not moneyflow_rows.empty
    assert set(moneyflow_rows["study_id"]) == {"factors/moneyflow_factor_real_mainline_s2"}
    assert set(moneyflow_rows["variant_name"]) == {"A_H20_CONTROL"}
    assert set(moneyflow_rows["primary_metric_name"]) == {"mean_observation_ic_20d"}

    projection_rows = stability_matrix.loc[stability_matrix["family"] == "final_score_composition"].copy()
    assert not projection_rows.empty
    assert projection_rows["is_projection_family"].all()
