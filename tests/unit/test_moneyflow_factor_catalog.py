from __future__ import annotations

import pandas as pd

from backend.research.moneyflow_factor_catalog import build_moneyflow_factor_catalog
from backend.research.moneyflow_factor_snapshots import (
    build_moneyflow_factor_score_snapshot,
    build_moneyflow_factor_snapshots,
)


def _monthly_panel() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"month": "2025-01-31", "symbol": "sh600000", "monthly_divergence_rate": 0.10, "monthly_factor_valid": True},
            {"month": "2025-01-31", "symbol": "sz000001", "monthly_divergence_rate": 0.30, "monthly_factor_valid": True},
            {"month": "2025-01-31", "symbol": "sh601318", "monthly_divergence_rate": 0.20, "monthly_factor_valid": True},
            {"month": "2025-02-28", "symbol": "sh600000", "monthly_divergence_rate": 0.15, "monthly_factor_valid": True},
            {"month": "2025-02-28", "symbol": "sz000001", "monthly_divergence_rate": 0.35, "monthly_factor_valid": True},
            {"month": "2025-02-28", "symbol": "sh601318", "monthly_divergence_rate": 0.25, "monthly_factor_valid": False},
        ]
    )


def test_build_moneyflow_factor_catalog_has_expected_first_factor() -> None:
    catalog = build_moneyflow_factor_catalog()
    assert [item["factor_id"] for item in catalog] == ["monthly_divergence_rate"]
    assert catalog[0]["frequency"] == "monthly_observation"


def test_build_moneyflow_factor_snapshots_emits_required_columns() -> None:
    snapshots = build_moneyflow_factor_snapshots(_monthly_panel())
    assert list(snapshots.columns) == [
        "date",
        "symbol",
        "factor_id",
        "raw_value",
        "normalized_value",
        "rank_value",
        "availability_flag",
        "asof_timestamp",
    ]
    assert snapshots["availability_flag"].sum() == 5
    assert snapshots["factor_id"].nunique() == 1


def test_build_moneyflow_factor_score_snapshot_combines_normalized_values() -> None:
    snapshots = build_moneyflow_factor_snapshots(_monthly_panel())
    score = build_moneyflow_factor_score_snapshot(
        snapshots,
        factor_ids=["monthly_divergence_rate"],
        factor_weights={"monthly_divergence_rate": 1.0},
    )
    assert list(score.columns) == [
        "date",
        "symbol",
        "score_id",
        "score_value",
        "availability_flag",
        "asof_timestamp",
    ]
    assert set(score["score_id"]) == {"moneyflow_factor_score"}
