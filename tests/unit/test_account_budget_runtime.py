from __future__ import annotations

import pytest

from backend.core.services import account_budget_runtime as budget_runtime


def test_actual_budget_snapshot_prefers_explicit_etf_role_exposures() -> None:
    actual = budget_runtime._actual_budget_snapshot(
        {
            "sleeve_budgets": {
                "cn_stock_trend_alpha_core": {"actual_exposure": 0.4},
                "cn_etf_beta": {
                    "actual_exposure": 0.2,
                    "actual_risk_exposure": 0.2,
                    "actual_defense_exposure": 0.14,
                },
            }
        }
    )

    assert actual["alpha"] == 0.4
    assert actual["defense"] == 0.14
    assert actual["core_beta"] == 0.06
    assert actual["derivation"] == "stock_actual_exposure + etf_actual_role_exposures"


def test_actual_budget_snapshot_falls_back_to_proxy_split_without_role_exposures() -> None:
    actual = budget_runtime._actual_budget_snapshot(
        {
            "sleeve_budgets": {
                "cn_stock_trend_alpha_core": {"actual_exposure": 0.4},
                "cn_etf_beta": {
                    "actual_exposure": 0.2,
                    "actual_risk_exposure": 0.12,
                },
            }
        }
    )

    assert actual["alpha"] == 0.4
    assert actual["defense"] == pytest.approx(0.08)
    assert actual["core_beta"] == pytest.approx(0.12)
    assert actual["derivation"] == "stock_actual_exposure + etf_actual_risk_split_proxy"
