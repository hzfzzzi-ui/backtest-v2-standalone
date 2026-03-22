from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from backend.core.config.models import WeeklyFiveStateRegimeConfig
from backend.core.engine_vector import weekly_five_state_engine as weekly_engine


def _make_benchmark_df(closes: list[float], *, start: str = "2026-01-05") -> tuple[pd.DataFrame, np.ndarray]:
    dates = pd.bdate_range(start=start, periods=len(closes))
    frame = pd.DataFrame(
        {
            "date": dates,
            "close": closes,
            "high": [value + 0.5 for value in closes],
            "low": [value - 0.5 for value in closes],
        }
    )
    return frame, dates.date.astype(object)


def test_weekly_five_state_engine_maps_bull_main_and_budget(monkeypatch) -> None:
    closes = [100.0 + float(i) for i in range(180)]
    benchmark, dates = _make_benchmark_df(closes)
    monkeypatch.setattr(weekly_engine, "adx_matrix", lambda high, low, close, period: np.full(len(close), 30.0, dtype=float))

    evaluation = weekly_engine.evaluate_weekly_five_state_regime(
        benchmark=benchmark,
        dates=dates,
        cfg=WeeklyFiveStateRegimeConfig(),
        legacy_market_state=np.zeros(len(dates), dtype=np.int8),
    )

    assert evaluation.market_state_names[-1] == "BULL_MAIN"
    assert evaluation.market_state_smoothed_names[-1] == "BULL_MAIN"
    assert evaluation.trade_mode_names[-1] == "TREND_MAIN"
    assert evaluation.risk_budget_multipliers[-1] == 1.0
    assert bool(np.any(evaluation.weekly_observation_flags))


def test_weekly_five_state_engine_requires_two_weekly_observations_for_upgrade(monkeypatch) -> None:
    closes = [
        10, 9, 8, 7, 6,
        6, 7, 8, 9, 10,
        11, 12, 13, 14, 15,
    ]
    benchmark, dates = _make_benchmark_df([float(v) for v in closes], start="2026-01-05")
    monkeypatch.setattr(weekly_engine, "adx_matrix", lambda high, low, close, period: np.full(len(close), 30.0, dtype=float))
    cfg = WeeklyFiveStateRegimeConfig(
        ma_window=3,
        ma_slope_lookback=1,
        ret_short_window=1,
        ret_long_window=2,
        adx_window=2,
        weekly_rule="W-FRI",
        upgrade_confirm_weeks=2,
        downgrade_confirm_weeks=1,
    )

    evaluation = weekly_engine.evaluate_weekly_five_state_regime(
        benchmark=benchmark,
        dates=dates,
        cfg=cfg,
        legacy_market_state=np.zeros(len(dates), dtype=np.int8),
    )

    observation_idx = np.flatnonzero(evaluation.weekly_observation_flags)
    assert len(observation_idx) == 3
    first_obs, second_obs, third_obs = observation_idx.tolist()

    assert evaluation.market_state_raw_names[first_obs] == "TURN_WEAK"
    assert evaluation.market_state_smoothed_names[first_obs] == "TURN_WEAK"
    assert evaluation.market_state_raw_names[second_obs] == "BULL_MAIN"
    assert evaluation.market_state_smoothed_names[second_obs] == "TURN_WEAK"
    assert evaluation.regime_transition_reason[second_obs] == "UPGRADE_PENDING"
    assert evaluation.market_state_smoothed_names[third_obs] == "BULL_MAIN"
    assert evaluation.regime_transition_reason[third_obs] == "UPGRADE_CONFIRMED"


def test_weekly_five_state_engine_three_state_budget_collapses_turn_weak_to_no_trade(monkeypatch) -> None:
    closes = [
        10, 9, 8, 7, 6,
        6, 7, 8, 9, 10,
        11, 12, 13, 14, 15,
    ]
    benchmark, dates = _make_benchmark_df([float(v) for v in closes], start="2026-01-05")
    monkeypatch.setattr(weekly_engine, "adx_matrix", lambda high, low, close, period: np.full(len(close), 30.0, dtype=float))
    cfg = WeeklyFiveStateRegimeConfig(
        ma_window=3,
        ma_slope_lookback=1,
        ret_short_window=1,
        ret_long_window=2,
        adx_window=2,
        weekly_rule="W-FRI",
        upgrade_confirm_weeks=2,
        downgrade_confirm_weeks=1,
        risk_budget_mode="three_state",
    )

    evaluation = weekly_engine.evaluate_weekly_five_state_regime(
        benchmark=benchmark,
        dates=dates,
        cfg=cfg,
        legacy_market_state=np.zeros(len(dates), dtype=np.int8),
    )

    observation_idx = np.flatnonzero(evaluation.weekly_observation_flags)
    first_obs = int(observation_idx[0])

    assert evaluation.market_state_smoothed_names[first_obs] == "TURN_WEAK"
    assert evaluation.trade_mode_names[first_obs] == "NO_TRADE"
    assert evaluation.risk_budget_multipliers[first_obs] == 0.0


def test_weekly_five_state_engine_asymmetric_budget_keeps_turn_strong_at_point7(monkeypatch) -> None:
    closes = [100.0 + float(i) for i in range(180)]
    benchmark, dates = _make_benchmark_df(closes)
    monkeypatch.setattr(weekly_engine, "adx_matrix", lambda high, low, close, period: np.full(len(close), 22.0, dtype=float))
    cfg = WeeklyFiveStateRegimeConfig(risk_budget_mode="asymmetric_budget")

    evaluation = weekly_engine.evaluate_weekly_five_state_regime(
        benchmark=benchmark,
        dates=dates,
        cfg=cfg,
        legacy_market_state=np.zeros(len(dates), dtype=np.int8),
    )

    turn_strong_idx = int(np.flatnonzero(evaluation.market_state_names == "TURN_STRONG")[0])
    assert evaluation.trade_mode_names[turn_strong_idx] == "TREND_MAIN"
    assert evaluation.risk_budget_multipliers[turn_strong_idx] == 0.70
