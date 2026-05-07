from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from backend.research.mainline_breakout_runtime_context import MainlineBreakoutResearchContext
from backend.research.stock_lifecycle_fragility_snapshots import (
    build_stock_lifecycle_fragility_factor_score_snapshot,
    build_stock_lifecycle_fragility_snapshots,
)


def _context() -> MainlineBreakoutResearchContext:
    dates = pd.bdate_range('2024-01-01', periods=8)
    close = np.array([[10.0], [10.5], [10.3], [10.8], [10.7], [10.6], [10.9], [11.1]], dtype=float)
    high = np.array([[10.1], [10.7], [10.6], [10.9], [10.8], [10.7], [11.0], [11.2]], dtype=float)
    low = np.array([[9.9], [10.2], [10.1], [10.6], [10.5], [10.4], [10.8], [11.0]], dtype=float)
    tradable = np.ones_like(close, dtype=bool)
    provider = SimpleNamespace(
        _breakout_buy=np.array([[True], [False], [False], [False], [False], [False], [False], [False]], dtype=bool),
        _pullback_raw_selected=np.zeros_like(close, dtype=bool),
    )
    return MainlineBreakoutResearchContext(
        runtime_config={},
        cfg_obj=None,
        data_bundle=None,
        provider=provider,
        dates=dates,
        symbols=['sh600000'],
        close_matrix=close,
        high_matrix=high,
        low_matrix=low,
        tradable_matrix=tradable,
        risk_on_arr=np.ones(len(dates), dtype=bool),
        strong_risk_on_arr=np.ones(len(dates), dtype=bool),
        effective_state_5_arr=np.array(['BULL', 'BULL', 'TRANS_UP', 'BULL', 'TRANS_DOWN', 'TRANS_DOWN', 'RISK_OFF', 'RISK_OFF'], dtype=object),
        meta={},
    )


def test_stock_lifecycle_fragility_snapshots_emit_expected_columns() -> None:
    context = _context()
    snapshot = build_stock_lifecycle_fragility_snapshots(
        context,
        factor_ids=['early_fade_risk', 'weak_carry_risk', 'risk_off_exit_context_risk'],
    )
    assert set(snapshot.columns) == {'date', 'symbol', 'factor_id', 'raw_value', 'normalized_value', 'rank_value', 'available'}
    assert {'early_fade_risk', 'weak_carry_risk', 'risk_off_exit_context_risk'} == set(snapshot['factor_id'])


def test_stock_lifecycle_fragility_factor_score_snapshot_builds_score_id() -> None:
    context = _context()
    snapshot = build_stock_lifecycle_fragility_snapshots(
        context,
        factor_ids=['early_fade_risk', 'weak_carry_risk'],
    )
    scored = build_stock_lifecycle_fragility_factor_score_snapshot(
        snapshot,
        factor_ids=['early_fade_risk', 'weak_carry_risk'],
        factor_weights={'early_fade_risk': 1.0, 'weak_carry_risk': 1.0},
    )
    assert set(scored.columns) == {'date', 'symbol', 'score_id', 'raw_value', 'normalized_value', 'rank_value', 'available'}
    assert set(scored['score_id']) == {'stock_lifecycle_fragility_score'}
