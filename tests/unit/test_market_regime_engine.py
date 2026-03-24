from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from backend.core.config.models import RegimeEngineConfig
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.market_regime_engine import build_formal_market_regime_result
from backend.core.engine_vector.regime_engine_inputs import build_formal_regime_feature_bundle


def _make_regime_fixture() -> tuple[pd.DataFrame, pd.DataFrame, list[date]]:
    start = date(2026, 1, 1)
    trading_days = [start + timedelta(days=i) for i in range(90)]
    history_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []
    for i, day in enumerate(trading_days):
        close = 10.0 + float(i) * 0.1
        history_rows.append(
            {
                "date": day.isoformat(),
                "symbol": "sh600000",
                "open": close - 0.05,
                "high": close + 0.15,
                "low": close - 0.15,
                "close": close,
                "volume": 1_000_000.0,
                "amount": close * 1_000_000.0,
            }
        )
        benchmark_close = 100.0 + float(i) * 0.3
        benchmark_rows.append(
            {
                "date": day.isoformat(),
                "open": benchmark_close - 0.1,
                "high": benchmark_close + 0.6,
                "low": benchmark_close - 0.6,
                "close": benchmark_close,
                "volume": 1_000_000.0,
                "amount": benchmark_close * 1_000_000.0,
            }
        )
    return pd.DataFrame(history_rows), pd.DataFrame(benchmark_rows), trading_days


def test_build_formal_market_regime_result_emits_dual_track_payload_and_override() -> None:
    history, benchmark, trading_days = _make_regime_fixture()
    mx = build_ohlc_matrices_from_history(history.copy(), trading_days)
    bundle = build_formal_regime_feature_bundle(
        benchmark=benchmark.copy(),
        history=history.copy(),
        mx=mx,
        trading_days=trading_days,
        regime_engine_cfg=RegimeEngineConfig(engine="market_regime_framework"),
        membership_history=None,
    )

    result = build_formal_market_regime_result(
        bundle=bundle,
        regime_engine_cfg=RegimeEngineConfig(engine="market_regime_framework"),
        governed_contract={
            "regime": {
                "manual_override": {
                    "active": True,
                    "reason": "manual_review",
                    "scope": "cn_a_mainline",
                    "actor": "pm",
                    "target_state_5": "LIGHT",
                    "risk_budget_multiplier": 0.45,
                    "defense_bias": 0.4,
                }
            }
        },
    )

    assert len(result.base_state_5) == len(trading_days)
    assert len(result.effective_state_5) == len(trading_days)
    assert len(result.reason_codes) == len(trading_days)
    assert len(result.block_scores) == len(trading_days)
    assert len(result.subscores) == len(trading_days)
    assert len(result.manual_override) == len(trading_days)
    assert len(result.state_stability_metrics) == len(trading_days)
    assert set(result.base_state_5.tolist()).issubset({"BULL", "TRANS_UP", "LIGHT", "TRANS_DOWN", "RISK_OFF"})
    assert set(result.effective_state_5.tolist()) == {"LIGHT"}
    assert "MANUAL_OVERRIDE_ACTIVE" in set(result.reason_codes[-1])
    assert result.manual_override[-1]["active"] is True
    assert result.manual_override[-1]["target_state_5"] == "LIGHT"
    assert result.subscores[-1]["technical"] is not None
    assert result.subscores[-1]["macro_global"] is None
    assert result.block_scores[-1]["trend_block"]["net"] is not None
    assert result.state_stability_metrics[-1]["pending_transition"] in {True, False}
    assert float(result.risk_budget_multiplier[-1]) == 0.45
    assert float(result.defense_bias[-1]) == 0.4
