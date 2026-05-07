from __future__ import annotations

import pandas as pd

from backend.research.account_state_score_catalog import build_account_state_score_catalog
from backend.research.account_state_score_snapshots import (
    build_account_state_combo_score_snapshot,
    build_account_state_score_snapshots,
)


def _benchmark_history() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=180)
    rows: list[dict[str, object]] = []
    for idx, dt in enumerate(dates):
        close = 3400.0 + 0.8 * idx + 20.0 * ((idx % 15) / 15.0)
        rows.append(
            {
                "date": dt,
                "symbol": "sh000300",
                "close": close,
            }
        )
    return pd.DataFrame(rows)


def test_account_state_score_catalog_has_expected_ids() -> None:
    catalog = build_account_state_score_catalog()
    ids = [item["score_id"] for item in catalog]
    assert ids == ["risk_on_score", "recovery_score", "defense_score"]


def test_account_state_score_snapshot_has_required_columns() -> None:
    snapshot = build_account_state_score_snapshots(_benchmark_history(), benchmark_symbol="sh000300")
    required = {
        "date",
        "score_id",
        "scope",
        "raw_value",
        "normalized_value",
        "availability_flag",
        "asof_timestamp",
        "source_trace",
        "derived_state",
    }
    assert required.issubset(snapshot.columns)
    assert set(snapshot["score_id"]) == {"risk_on_score", "recovery_score", "defense_score"}


def test_account_state_combo_snapshot_has_required_columns() -> None:
    snapshot = build_account_state_score_snapshots(_benchmark_history(), benchmark_symbol="sh000300")
    combo = build_account_state_combo_score_snapshot(
        snapshot,
        score_ids=["risk_on_score", "recovery_score"],
        score_weights={"risk_on_score": 1.0, "recovery_score": 1.0},
    )
    required = {
        "date",
        "score_id",
        "scope",
        "raw_value",
        "normalized_value",
        "availability_flag",
        "asof_timestamp",
        "source_trace",
        "derived_state",
    }
    assert required.issubset(combo.columns)
    assert set(combo["score_id"]) == {"account_state_combo_score"}
