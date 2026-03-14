from __future__ import annotations

import math

import pandas as pd

from backend.core.tools.experiment_runner import (
    _compute_effective_warmup_analysis,
    _recompute_perf_from_daily,
)


def test_compute_effective_warmup_analysis_respects_min_list_and_benchmark_regime() -> None:
    trading_days = [d.date() for d in pd.bdate_range("2016-03-01", periods=140)]
    daily_df = pd.DataFrame(
        {
            "date": [d.isoformat() for d in trading_days],
            "raw_buy_signal_count": [0] * 119 + [1] * 21,
            "benchmark_regime_on": [False] * 124 + [True] * 16,
            "positions_count_end_of_day": [0] * 125 + [1] * 15,
            "nav": [1.0] * 140,
            "daily_return": [0.0] * 140,
            "drawdown": [0.0] * 140,
        }
    )
    cfg = {
        "strategy_pack": "BREAKOUT_TREND",
        "signal_generation": {
            "strategy": "BREAKOUT_TREND",
            "breakout": {"breakout_window": 45},
            "ranking": {"score_source_mode": "residual_only"},
        },
        "universe": {"filters": {"min_list_days": 120}},
        "benchmark_regime": {"enabled": True, "slow_period": 120, "slope_window": 5},
        "position_risk": {"cost_model": {"matching": "next_open"}},
    }

    warmup = _compute_effective_warmup_analysis(cfg, trading_days, daily_df)

    assert warmup["candidate_warmup_trading_days"] == 119
    assert warmup["signal_warmup_trading_days"] == 124
    assert warmup["execution_warmup_trading_days"] == 125
    assert warmup["observed_first_raw_signal_date"] == str(trading_days[119])
    assert warmup["observed_first_regime_ready_date"] == str(trading_days[124])
    assert warmup["observed_first_position_date"] == str(trading_days[125])


def test_recompute_perf_from_daily_trims_to_effective_execution_start() -> None:
    dates = pd.bdate_range("2020-01-01", periods=6)
    daily_df = pd.DataFrame(
        {
            "date": dates,
            "nav": [1.0, 1.0, 1.0, 1.10, 1.15, 1.20],
            "daily_return": [0.0, 0.0, 0.0, 0.10, 0.0454545455, 0.0434782609],
            "drawdown": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )

    perf = _recompute_perf_from_daily(daily_df, str(dates[3].date()))

    assert perf["metrics_from_effective_start"] is True
    assert perf["effective_observation_days"] == 3
    assert math.isclose(perf["total_return"], (1.20 / 1.10) - 1.0, rel_tol=1e-9)
    assert perf["cagr"] > 0
