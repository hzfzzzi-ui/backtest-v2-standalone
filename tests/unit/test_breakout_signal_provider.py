from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.core.config.models import ExitConfig
from backend.core.config.models import LegacyTurnWeakOverlayConfig
from backend.core.config.models import MarketFilterConfig
from backend.core.config.models import RegimeEngineConfig
from backend.core.config.models import StrategyConfig
from backend.core.config.models import WeeklyFiveStateRegimeConfig
from backend.core.engine_vector.breakout_signal_provider import (
    BreakoutTrendProvider,
    _build_legacy_market_filter_state,
    _build_industry_assignment_matrices,
    _compute_residual_ranking_matrices,
)
from backend.core.engine_vector.weekly_five_state_engine import WeeklyFiveStateEvaluation
from backend.core.engine_vector.signal_provider import DayContext
from backend.core.strategies.registry import build_strategy
from backend.core.strategies.breakout_trend import BreakoutTrendStrategy
from backend.core.universe.ingest_universe import SW_L1_INDEX_MAP


def _make_price_fixture(closes: list[float]) -> tuple[pd.DataFrame, pd.DataFrame, list[date]]:
    start = date(2026, 1, 1)
    trading_days = [start + timedelta(days=i) for i in range(len(closes))]
    history_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []

    for i, (day, close) in enumerate(zip(trading_days, closes)):
        high = close + 0.05
        low = close - 0.05
        open_ = close - 0.02
        volume = 1_000_000.0
        history_rows.append(
            {
                "date": day.isoformat(),
                "symbol": "sh600000",
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": close * volume,
            }
        )
        benchmark_rows.append(
            {
                "date": day.isoformat(),
                "close": 100.0 + float(i),
            }
        )

    return pd.DataFrame(history_rows), pd.DataFrame(benchmark_rows), trading_days


def _make_breakout_fixture() -> tuple[pd.DataFrame, pd.DataFrame, list[date]]:
    start = date(2026, 1, 1)
    trading_days = [start + timedelta(days=i) for i in range(70)]
    history_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []

    for i, day in enumerate(trading_days):
        if i <= 47:
            close = 20.0
            high = 20.5
            low = 19.5
            open_ = 20.0
        elif i <= 68:
            close = 9.6
            high = 9.9
            low = 9.3
            open_ = 9.5
        else:
            close = 10.2
            high = 10.3
            low = 10.0
            open_ = 10.1
        volume = 1_000_000.0
        history_rows.append(
            {
                "date": day.isoformat(),
                "symbol": "sh600000",
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": close * volume,
            }
        )
        benchmark_rows.append(
            {
                "date": day.isoformat(),
                "close": 100.0 + float(i),
            }
        )

    return pd.DataFrame(history_rows), pd.DataFrame(benchmark_rows), trading_days


def _make_breakout_volume_fixture(*, last_volume: float) -> tuple[pd.DataFrame, pd.DataFrame, list[date]]:
    start = date(2026, 1, 1)
    trading_days = [start + timedelta(days=i) for i in range(70)]
    history_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []

    for i, day in enumerate(trading_days):
        if i <= 47:
            close = 20.0
            high = 20.5
            low = 19.5
            open_ = 20.0
        elif i <= 68:
            close = 9.6
            high = 9.9
            low = 9.3
            open_ = 9.5
        else:
            close = 10.2
            high = 10.3
            low = 10.0
            open_ = 10.1
        volume = float(last_volume if i == 69 else 1_000_000.0)
        history_rows.append(
            {
                "date": day.isoformat(),
                "symbol": "sh600000",
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": close * volume,
            }
        )
        benchmark_rows.append(
            {
                "date": day.isoformat(),
                "close": 100.0 + float(i),
            }
        )

    return pd.DataFrame(history_rows), pd.DataFrame(benchmark_rows), trading_days


def _make_low_quality_breakout_fixture() -> tuple[pd.DataFrame, pd.DataFrame, list[date]]:
    start = date(2026, 1, 1)
    trading_days = [start + timedelta(days=i) for i in range(70)]
    history_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []

    for i, day in enumerate(trading_days):
        if i <= 47:
            close = 20.0
            high = 20.5
            low = 19.5
            open_ = 20.0
        elif i <= 68:
            close = 9.6
            high = 9.9
            low = 9.3
            open_ = 9.5
        else:
            close = 10.2
            high = 10.8
            low = 10.0
            open_ = 10.7
        volume = 1_000_000.0
        history_rows.append(
            {
                "date": day.isoformat(),
                "symbol": "sh600000",
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": close * volume,
            }
        )
        benchmark_rows.append(
            {
                "date": day.isoformat(),
                "close": 100.0 + float(i),
            }
        )

    return pd.DataFrame(history_rows), pd.DataFrame(benchmark_rows), trading_days


def _make_pullback_reclaim_fixture() -> tuple[pd.DataFrame, pd.DataFrame, list[date]]:
    closes: list[float] = []
    start = 10.0
    peak = 18.0
    trough = 15.0
    end = 17.5
    closes.extend(start + (peak - start) * i / 59 for i in range(60))
    closes.extend(peak + (trough - peak) * i / 8 for i in range(1, 9))
    closes.extend(trough + (end - trough) * i / 12 for i in range(1, 13))
    return _make_price_fixture([float(v) for v in closes])


def _make_long_benchmark_breakout_fixture() -> tuple[pd.DataFrame, pd.DataFrame, list[date]]:
    closes = [20.0] * 229 + [21.0]
    return _make_price_fixture([float(v) for v in closes])


def _make_conditional_tiebreak_fixture() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[date]]:
    start = date(2026, 1, 1)
    trading_days = [start + timedelta(days=i) for i in range(70)]
    history_rows: list[dict[str, object]] = []
    raw_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []

    for i, day in enumerate(trading_days):
        if i <= 47:
            close = 20.0
            high = 20.5
            low = 19.5
            open_ = 20.0
        elif i <= 67:
            close = 9.6
            high = 9.9
            low = 9.3
            open_ = 9.5
        elif i == 68:
            close = 9.0
            high = 9.9
            low = 8.9
            open_ = 8.95
        else:
            close = 10.2
            high = 11.22
            low = 10.0
            open_ = 10.1
        volume = 1_200_000.0
        amount = close * volume
        limit_up = round(close * 1.1, 4)
        row = {
            "date": day.isoformat(),
            "symbol": "sh600000",
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": amount,
            "circ_mv": 5_000_000_000.0,
            "turnover_rate_f": 2.5,
            "limit_up": limit_up,
        }
        history_rows.append(dict(row))
        raw_rows.append(dict(row))
        benchmark_rows.append(
            {
                "date": day.isoformat(),
                "close": 100.0 + float(i),
            }
        )

    return pd.DataFrame(history_rows), pd.DataFrame(benchmark_rows), pd.DataFrame(raw_rows), trading_days


def _run_provider(
    strategy: BreakoutTrendStrategy,
    fixture_builder=_make_breakout_fixture,
):
    fixture = fixture_builder()
    if len(fixture) == 4:
        history, benchmark, raw_history, trading_days = fixture
    else:
        history, benchmark, trading_days = fixture
        raw_history = None
    provider = BreakoutTrendProvider()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=raw_history,
        trading_days=trading_days,
        strategy=strategy,
        exit_cfg=ExitConfig(),
    )
    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        DayContext(
            positions={},
            position_avg_cost={},
            cash=1_000_000.0,
            nav=1_000_000.0,
            base_order_value=100_000.0,
            max_positions=10,
            close_idx={},
            open_idx={},
            next_day=None,
        ),
    )
    return provider, signals


def _build_day_context(*, market_state: str = "", risk_on: bool = True) -> DayContext:
    return DayContext(
        positions={},
        position_avg_cost={},
        cash=1_000_000.0,
        nav=1_000_000.0,
        base_order_value=100_000.0,
        max_positions=10,
        close_idx={},
        open_idx={},
        next_day=None,
        market_state=market_state,
        risk_on=risk_on,
    )


def test_breakout_provider_allows_buy_without_entry_filters() -> None:
    provider, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
        )
    )

    assert len(signals.buy_signals) == 1
    assert provider.entry_above_slow_ma_block_count == 0
    assert provider.entry_slope_block_count == 0


def test_breakout_provider_preserves_bull_breakout_quality_veto_params() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "bull_breakout_quality_veto_enabled": True,
                "bull_breakout_quality_veto_min_residual_strength_score": 0.94,
                "bull_breakout_quality_veto_min_breakout_margin_score": 0.55,
            },
        )
    )

    assert isinstance(strategy, BreakoutTrendStrategy)
    assert strategy.bull_breakout_quality_veto_enabled is True
    assert strategy.bull_breakout_quality_veto_min_residual_strength_score == 0.94
    assert strategy.bull_breakout_quality_veto_min_breakout_margin_score == 0.55


def test_breakout_provider_bull_quality_veto_default_disabled_keeps_signal() -> None:
    provider = BreakoutTrendProvider()
    history, benchmark, trading_days = _make_breakout_fixture()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_window=40,
        ),
        exit_cfg=ExitConfig(),
    )
    provider._residual_strength_score[-1, 0] = 0.2
    provider._breakout_margin_score[-1, 0] = 0.2

    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        _build_day_context(market_state="BULL", risk_on=True),
    )

    assert len(signals.buy_signals) == 1
    assert signals.diagnostics["bull_breakout_quality_veto_applied"] is False
    assert provider.bull_breakout_quality_veto_block_count == 0


def test_breakout_provider_bull_quality_veto_blocks_low_residual_strength() -> None:
    provider = BreakoutTrendProvider()
    history, benchmark, trading_days = _make_breakout_fixture()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_window=40,
            bull_breakout_quality_veto_enabled=True,
            bull_breakout_quality_veto_min_residual_strength_score=0.94,
            bull_breakout_quality_veto_min_breakout_margin_score=0.55,
        ),
        exit_cfg=ExitConfig(),
    )
    provider._residual_strength_score[-1, 0] = 0.50
    provider._breakout_margin_score[-1, 0] = 0.80

    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        _build_day_context(market_state="BULL", risk_on=True),
    )

    assert signals.buy_signals == []
    assert signals.diagnostics["bull_breakout_quality_veto_applied"] is True
    assert signals.diagnostics["bull_breakout_quality_veto_block_count"] == 1
    assert signals.diagnostics["bull_breakout_quality_veto_residual_block_count"] == 1
    assert signals.diagnostics["bull_breakout_quality_veto_margin_block_count"] == 0
    assert provider.bull_breakout_quality_veto_block_count == 1
    assert provider.diag_reason_counts["BLOCK_BULL_QUALITY_VETO"] == 1


def test_breakout_provider_bull_quality_veto_blocks_low_breakout_margin() -> None:
    provider = BreakoutTrendProvider()
    history, benchmark, trading_days = _make_breakout_fixture()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_window=40,
            bull_breakout_quality_veto_enabled=True,
            bull_breakout_quality_veto_min_residual_strength_score=0.94,
            bull_breakout_quality_veto_min_breakout_margin_score=0.55,
        ),
        exit_cfg=ExitConfig(),
    )
    provider._residual_strength_score[-1, 0] = 0.99
    provider._breakout_margin_score[-1, 0] = 0.20

    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        _build_day_context(market_state="BULL", risk_on=True),
    )

    assert signals.buy_signals == []
    assert signals.diagnostics["bull_breakout_quality_veto_block_count"] == 1
    assert signals.diagnostics["bull_breakout_quality_veto_residual_block_count"] == 0
    assert signals.diagnostics["bull_breakout_quality_veto_margin_block_count"] == 1


def test_breakout_provider_bull_quality_veto_does_not_apply_outside_bull() -> None:
    provider = BreakoutTrendProvider()
    history, benchmark, trading_days = _make_breakout_fixture()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_window=40,
            bull_breakout_quality_veto_enabled=True,
            bull_breakout_quality_veto_min_residual_strength_score=0.94,
            bull_breakout_quality_veto_min_breakout_margin_score=0.55,
        ),
        exit_cfg=ExitConfig(),
    )
    provider._residual_strength_score[-1, 0] = 0.20
    provider._breakout_margin_score[-1, 0] = 0.20

    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        _build_day_context(market_state="TRANS_UP", risk_on=True),
    )

    assert len(signals.buy_signals) == 1
    assert signals.diagnostics["bull_breakout_quality_veto_applied"] is False
    assert provider.bull_breakout_quality_veto_block_count == 0


def test_breakout_provider_bull_quality_veto_skips_pullback_only_candidates() -> None:
    provider = BreakoutTrendProvider()
    history, benchmark, trading_days = _make_pullback_reclaim_fixture()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_pullback_candidates=True,
            bull_breakout_quality_veto_enabled=True,
            bull_breakout_quality_veto_min_residual_strength_score=0.94,
            bull_breakout_quality_veto_min_breakout_margin_score=0.55,
        ),
        exit_cfg=ExitConfig(),
    )
    provider._residual_strength_score[-1, 0] = 0.20
    provider._breakout_margin_score[-1, 0] = 0.20

    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        _build_day_context(market_state="BULL", risk_on=True),
    )

    assert len(signals.buy_signals) == 1
    assert signals.buy_signals[0].meta["alpha_source"] == "pullback_only"
    assert signals.buy_signals[0].meta["bull_breakout_quality_veto_applied"] is False
    assert provider.bull_breakout_quality_veto_block_count == 0


def test_breakout_provider_blocks_entry_above_slow_ma() -> None:
    provider, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_entry_above_slow_ma=True,
        )
    )

    assert signals.buy_signals == []
    assert provider.entry_above_slow_ma_block_count == 1


def test_breakout_provider_blocks_entry_on_negative_slow_ma_slope() -> None:
    provider, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_entry_slow_ma_slope=True,
            entry_slope_lookback=5,
        )
    )

    assert signals.buy_signals == []
    assert provider.entry_slope_block_count == 1


def test_breakout_provider_supports_slow_gate_fast_trigger_mode() -> None:
    provider, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_dual_breakout=True,
            breakout_window_short=3,
            breakout_window_long=55,
            dual_breakout_mode="slow_gate_fast_trigger",
            dual_breakout_gate_ma_window=5,
            dual_breakout_gate_slope_lookback=2,
            enable_v2_trend_filter=False,
        ),
        fixture_builder=lambda: _make_price_fixture([10.0, 10.0, 10.0, 10.0, 10.1, 10.3, 10.6, 10.9]),
    )

    assert len(signals.buy_signals) == 1
    assert signals.buy_signals[0].reason_code == "BREAKOUT_SLOW_GATE_FAST_TRIGGER"
    assert signals.buy_signals[0].meta["slow_gate_ok"] is True


def test_breakout_provider_slow_gate_fast_trigger_blocks_negative_slow_trend() -> None:
    provider, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_dual_breakout=True,
            breakout_window_short=3,
            breakout_window_long=55,
            dual_breakout_mode="slow_gate_fast_trigger",
            dual_breakout_gate_ma_window=5,
            dual_breakout_gate_slope_lookback=2,
            enable_v2_trend_filter=False,
        ),
        fixture_builder=lambda: _make_price_fixture([11.0, 10.9, 10.8, 10.7, 10.6, 10.65, 10.7, 10.8]),
    )

    assert signals.buy_signals == []
    assert bool(provider._dual_breakout_slow_gate_ok[-1, 0]) is False


def test_breakout_provider_volume_ratio_confirm_uses_prior_20d_average() -> None:
    provider, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            entry_confirm_mode="volume_ratio_confirm",
        ),
        fixture_builder=lambda: _make_breakout_volume_fixture(last_volume=1_520_000.0),
    )

    assert len(signals.buy_signals) == 1
    assert bool(provider._entry_confirm_ok[-1, 0]) is True


def test_breakout_provider_volume_ratio_confirm_blocks_when_ratio_below_threshold() -> None:
    provider, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            entry_confirm_mode="volume_ratio_confirm",
        ),
        fixture_builder=lambda: _make_breakout_volume_fixture(last_volume=1_480_000.0),
    )

    assert signals.buy_signals == []
    assert bool(provider._entry_confirm_ok[-1, 0]) is False


def test_build_legacy_market_filter_state_respects_long_ma_window() -> None:
    benchmark = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=220, freq="D"),
            "close": np.concatenate(
                [
                    np.full(100, 220.0),
                    np.full(40, 80.0),
                    np.linspace(80.0, 140.0, 80),
                ]
            ),
            "high": np.concatenate(
                [
                    np.full(100, 220.5),
                    np.full(40, 80.5),
                    np.linspace(80.5, 140.5, 80),
                ]
            ),
        }
    )
    dates = benchmark["date"].dt.date.to_numpy()

    market_state_160, trade_mode_160 = _build_legacy_market_filter_state(
        benchmark=benchmark,
        dates=dates,
        market_filter_cfg=MarketFilterConfig(enabled=True, long_ma_window=160, slope_window=10, slope_ma_period=50),
    )
    market_state_200, trade_mode_200 = _build_legacy_market_filter_state(
        benchmark=benchmark,
        dates=dates,
            market_filter_cfg=MarketFilterConfig(enabled=True, long_ma_window=200, slope_window=10, slope_ma_period=50),
        )

    assert int(market_state_160[-1]) == 0
    assert int(trade_mode_160[-1]) == 0
    assert int(market_state_200[-1]) == 2
    assert int(trade_mode_200[-1]) == 2


def test_breakout_provider_emits_pullback_only_when_pullback_candidates_enabled() -> None:
    provider, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=45,
            enable_v2_trend_filter=False,
            enable_pullback_candidates=True,
            pullback_variant_mode="pb_reclaim_ma20",
        ),
        fixture_builder=_make_pullback_reclaim_fixture,
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signal.reason_code == "PULLBACK_TREND"
    assert signal.meta["alpha_source"] == "pullback_only"
    assert signal.meta["pullback_variant"] == "pb_reclaim_ma20"
    assert bool(provider._pullback_buy[-1, 0]) is True
    assert bool(provider._breakout_buy[-1, 0]) is False


def test_breakout_provider_emits_entry_breakout_floor_raw_meta() -> None:
    history, benchmark, trading_days = _make_breakout_fixture()
    provider = BreakoutTrendProvider()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
        ),
        exit_cfg=ExitConfig(),
    )
    close_idx = {
        (pd.to_datetime(row["date"]).date(), str(row["symbol"]).lower()): float(row["close"])
        for row in history.to_dict("records")
    }
    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        DayContext(
            positions={},
            position_avg_cost={},
            cash=1_000_000.0,
            nav=1_000_000.0,
            base_order_value=100_000.0,
            max_positions=10,
            close_idx=close_idx,
            open_idx={},
            next_day=None,
        ),
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signal.meta["high_max_main_prev"] is not None
    assert signal.meta["entry_breakout_floor_raw"] is not None


def test_breakout_provider_switches_residual_window_in_strong_risk_on_regime() -> None:
    _, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_window=40,
            residual_window_regime_mode="strong_risk_on",
            residual_window_fallback=60,
        ),
        fixture_builder=_make_long_benchmark_breakout_fixture,
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signals.strong_risk_on is True
    assert signal.meta["strong_risk_on"] is True
    assert signal.meta["residual_window_effective"] == 40
    assert signal.meta["residual_window_conditional_active"] is True


def test_breakout_provider_supports_custom_regime_ma_definition_for_conditional_residual_window() -> None:
    _, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_window=40,
            residual_window_regime_mode="strong_risk_on",
            residual_window_fallback=60,
            residual_window_regime_fast_ma=20,
            residual_window_regime_slow_ma=60,
        )
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signals.strong_risk_on is True
    assert signal.meta["residual_window_regime_fast_ma"] == 20
    assert signal.meta["residual_window_regime_slow_ma"] == 60
    assert signal.meta["residual_window_effective"] == 40
    assert signal.meta["residual_window_conditional_active"] is True


def test_compute_residual_ranking_matrices_respects_split_weights() -> None:
    sector_name, sector_code = next(iter(SW_L1_INDEX_MAP.items()))
    close = pd.DataFrame(
        [
            [10.0, 10.0],
            [12.0, 11.0],
            [14.4, 11.55],
        ]
    ).to_numpy(dtype=float)
    bench_close = pd.Series([100.0, 110.0, 121.0], dtype=float).to_numpy()
    tradable = pd.DataFrame([[True, True], [True, True], [True, True]]).to_numpy(dtype=bool)
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]).to_numpy()
    sector_df = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "close": [100.0, 100.0, 100.0],
        }
    )
    industry_map = {"sh600000": sector_name, "sh600001": sector_name}
    symbols = ["sh600000", "sh600001"]

    bench_only = _compute_residual_ranking_matrices(
        close=close,
        bench_close=bench_close,
        tradable=tradable,
        residual_window=2,
        residual_benchmark_weight=1.0,
        residual_industry_weight=0.0,
        sector_data={sector_code: sector_df},
        industry_map=industry_map,
        industry_history=None,
        symbols=symbols,
        dates=dates,
        sector_strength_window_short=2,
        sector_strength_window_long=2,
    )
    industry_only = _compute_residual_ranking_matrices(
        close=close,
        bench_close=bench_close,
        tradable=tradable,
        residual_window=2,
        residual_benchmark_weight=0.0,
        residual_industry_weight=1.0,
        sector_data={sector_code: sector_df},
        industry_map=industry_map,
        industry_history=None,
        symbols=symbols,
        dates=dates,
        sector_strength_window_short=2,
        sector_strength_window_long=2,
    )

    bench_raw, _, bench_branch, _, _, _, _, _, _, _ = bench_only
    industry_raw, _, _, sector_branch, _, _, _, _, _, _ = industry_only
    assert bench_raw[-1, 0] == bench_branch[-1, 0]
    assert bench_raw[-1, 1] == bench_branch[-1, 1]
    assert industry_raw[-1, 0] == sector_branch[-1, 0]
    assert industry_raw[-1, 1] == sector_branch[-1, 1]


def test_compute_residual_ranking_matrices_industry_history_overrides_static_mapping() -> None:
    historical_name, historical_code = "农林牧渔", "801010.SI"
    latest_name = next(name for name, code in SW_L1_INDEX_MAP.items() if code == "801780.SI")
    close = pd.DataFrame(
        [
            [10.0],
            [11.0],
            [12.1],
        ]
    ).to_numpy(dtype=float)
    bench_close = pd.Series([100.0, 101.0, 102.0], dtype=float).to_numpy()
    tradable = pd.DataFrame([[True], [True], [True]]).to_numpy(dtype=bool)
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]).to_numpy()
    sector_df = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "close": [100.0, 102.0, 104.0],
        }
    )
    industry_map = {"sh600000": latest_name}
    industry_history = pd.DataFrame(
        [
            {
                "ts_code": "sh600000",
                "start_date": "2026-01-01",
                "end_date": None,
                "standard": "SW2021",
                "industry_l1": historical_name,
                "industry_l2": "110101",
            },
        ]
    )

    without_history = _compute_residual_ranking_matrices(
        close=close,
        bench_close=bench_close,
        tradable=tradable,
        residual_window=2,
        residual_benchmark_weight=0.0,
        residual_industry_weight=1.0,
        sector_data={historical_code: sector_df},
        industry_map=industry_map,
        industry_history=None,
        symbols=["sh600000"],
        dates=dates,
        sector_strength_window_short=2,
        sector_strength_window_long=2,
    )
    with_history = _compute_residual_ranking_matrices(
        close=close,
        bench_close=bench_close,
        tradable=tradable,
        residual_window=2,
        residual_benchmark_weight=0.0,
        residual_industry_weight=1.0,
        sector_data={historical_code: sector_df},
        industry_map=industry_map,
        industry_history=industry_history,
        symbols=["sh600000"],
        dates=dates,
        sector_strength_window_short=2,
        sector_strength_window_long=2,
    )

    assert np.isnan(without_history[3][-1, 0])
    assert not np.isnan(with_history[3][-1, 0])
    assert not np.isnan(with_history[7][-1, 0])


def test_build_industry_assignment_matrices_does_not_fallback_to_latest_mapping_on_pit_gaps() -> None:
    sector_name, sector_code = "农林牧渔", "801010.SI"
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]).to_numpy()
    sector_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2026-01-02", "2026-01-03"]),
            "close": [100.0, 101.0],
        }
    )
    industry_history = pd.DataFrame(
        [
            {
                "ts_code": "sh600000",
                "start_date": "2026-01-02",
                "end_date": None,
                "standard": "SW2021",
                "industry_l1": sector_name,
                "industry_l2": "110101",
            }
        ]
    )

    name_matrix, code_matrix = _build_industry_assignment_matrices(
        industry_map={"sh600000": "银行"},
        industry_history=industry_history,
        sector_data={sector_code: sector_df},
        symbols=["sh600000"],
        dates=dates,
    )

    assert name_matrix is not None
    assert code_matrix is not None
    assert name_matrix[0, 0] is None
    assert code_matrix[0, 0] is None
    assert name_matrix[1, 0] == sector_name
    assert code_matrix[1, 0] == sector_code


def test_build_industry_assignment_matrices_bridges_to_previous_index_code_before_new_code_starts() -> None:
    dates = pd.to_datetime(
        ["2021-12-10", "2021-12-11", "2021-12-12", "2021-12-13", "2021-12-14"]
    ).to_numpy()
    sector_data = {
        "801020.SI": pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2021-12-10", "2021-12-11", "2021-12-12", "2021-12-13", "2021-12-14"]),
                "close": [100.0, 101.0, 102.0, 103.0, 104.0],
            }
        ),
        "801950.SI": pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2021-12-13", "2021-12-14"]),
                "close": [200.0, 201.0],
            }
        ),
    }
    industry_history = pd.DataFrame(
        [
            {
                "ts_code": "sh600000",
                "start_date": "2021-12-10",
                "end_date": "2021-12-11",
                "standard": "SW_LEGACY",
                "industry_l1": "采掘",
                "industry_l2": "210101",
            },
            {
                "ts_code": "sh600000",
                "start_date": "2021-12-11",
                "end_date": None,
                "standard": "SW2021",
                "industry_l1": "煤炭",
                "industry_l2": "740101",
            },
        ]
    )

    _, code_matrix = _build_industry_assignment_matrices(
        industry_map={"sh600000": "煤炭"},
        industry_history=industry_history,
        sector_data=sector_data,
        symbols=["sh600000"],
        dates=dates,
    )

    assert code_matrix is not None
    assert code_matrix[0, 0] == "801020.SI"
    assert code_matrix[1, 0] == "801020.SI"
    assert code_matrix[2, 0] == "801020.SI"
    assert code_matrix[3, 0] == "801950.SI"
    assert code_matrix[4, 0] == "801950.SI"


def test_compute_residual_ranking_matrices_supports_strict_industry_rank_pct_mode() -> None:
    close = pd.DataFrame(
        [
            [10.0, 10.0, 10.0, 10.0],
            [11.0, 10.5, 11.5, 10.8],
            [13.0, 11.0, 14.0, 12.0],
        ]
    ).to_numpy(dtype=float)
    bench_close = pd.Series([100.0, 101.0, 102.0], dtype=float).to_numpy()
    tradable = pd.DataFrame([[True, True, True, True]] * 3).to_numpy(dtype=bool)
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]).to_numpy()
    symbols = ["sh600000", "sh600001", "sh600002", "sh600003"]
    industry_map = {
        "sh600000": "行业A",
        "sh600001": "行业A",
        "sh600002": "行业B",
        "sh600003": "行业B",
    }

    strict_industry_only = _compute_residual_ranking_matrices(
        close=close,
        bench_close=bench_close,
        tradable=tradable,
        residual_window=2,
        residual_benchmark_weight=0.0,
        residual_industry_weight=1.0,
        sector_data=None,
        industry_map=industry_map,
        industry_history=None,
        symbols=symbols,
        dates=dates,
        sector_strength_window_short=2,
        sector_strength_window_long=2,
        industry_relative_mode="industry_rank_pct",
    )

    strict_raw, strict_score, _, strict_sector_branch, _, _, _, strict_sector_proxy_raw, strict_industry_median_excess, strict_sector_beta_tailwind = strict_industry_only
    assert strict_score[-1, 0] == 1.0
    assert strict_score[-1, 1] == 0.0
    assert strict_score[-1, 2] == 1.0
    assert strict_score[-1, 3] == 0.0
    assert strict_raw[-1, 0] == 0.5
    assert strict_raw[-1, 1] == -0.5
    assert strict_raw[-1, 2] == 0.5
    assert strict_raw[-1, 3] == -0.5
    assert strict_sector_branch[-1, 0] == 0.5
    assert strict_sector_branch[-1, 1] == -0.5
    assert np.isnan(strict_sector_proxy_raw[-1, 0])
    assert strict_industry_median_excess[-1, 0] == pytest.approx(0.1)
    assert strict_industry_median_excess[-1, 1] == pytest.approx(-0.1)
    assert np.isnan(strict_sector_beta_tailwind[-1, 0])


def test_compute_residual_ranking_matrices_supports_industry_excess_median_mode() -> None:
    close = pd.DataFrame(
        [
            [10.0, 10.0, 10.0, 10.0],
            [11.0, 10.5, 11.5, 10.8],
            [13.0, 11.0, 14.0, 12.0],
        ]
    ).to_numpy(dtype=float)
    bench_close = pd.Series([100.0, 101.0, 102.0], dtype=float).to_numpy()
    tradable = pd.DataFrame([[True, True, True, True]] * 3).to_numpy(dtype=bool)
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]).to_numpy()
    symbols = ["sh600000", "sh600001", "sh600002", "sh600003"]
    industry_map = {
        "sh600000": "琛屼笟A",
        "sh600001": "琛屼笟A",
        "sh600002": "琛屼笟B",
        "sh600003": "琛屼笟B",
    }

    result = _compute_residual_ranking_matrices(
        close=close,
        bench_close=bench_close,
        tradable=tradable,
        residual_window=2,
        residual_benchmark_weight=0.0,
        residual_industry_weight=1.0,
        sector_data=None,
        industry_map=industry_map,
        industry_history=None,
        symbols=symbols,
        dates=dates,
        sector_strength_window_short=2,
        sector_strength_window_long=2,
        industry_relative_mode="industry_excess_median",
    )

    median_raw, median_score, _, median_sector_branch, _, _, _, median_sector_proxy_raw, median_industry_excess, median_sector_beta_tailwind = result
    assert median_raw[-1, 0] == pytest.approx(0.1)
    assert median_raw[-1, 1] == pytest.approx(-0.1)
    assert median_raw[-1, 2] == pytest.approx(0.1)
    assert median_raw[-1, 3] == pytest.approx(-0.1)
    assert median_sector_branch[-1, 0] == pytest.approx(0.1)
    assert median_sector_branch[-1, 1] == pytest.approx(-0.1)
    assert median_score[-1, 0] > median_score[-1, 1]
    assert median_score[-1, 2] > median_score[-1, 3]
    assert np.isnan(median_sector_proxy_raw[-1, 0])
    assert median_industry_excess[-1, 0] == pytest.approx(0.1)
    assert np.isnan(median_sector_beta_tailwind[-1, 0])


def test_breakout_provider_emits_residual_split_meta_fields() -> None:
    _, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_window=40,
            residual_benchmark_weight=1.0,
            residual_industry_weight=0.0,
        ),
        fixture_builder=_make_long_benchmark_breakout_fixture,
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signal.meta["residual_benchmark_weight"] == 1.0
    assert signal.meta["residual_industry_weight"] == 0.0
    assert "residual_vs_bench_raw" in signal.meta
    assert "residual_vs_sector_raw" in signal.meta
    assert "sector_proxy_residual_raw" in signal.meta
    assert "industry_median_excess_raw" in signal.meta
    assert "sector_beta_tailwind_raw" in signal.meta


def test_breakout_provider_switches_residual_weights_outside_strong_risk_on_regime() -> None:
    _, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_window=40,
            residual_benchmark_weight=0.0,
            residual_industry_weight=1.0,
            residual_weight_regime_mode="strong_risk_on",
            residual_benchmark_weight_fallback=0.5,
            residual_industry_weight_fallback=0.5,
        ),
        fixture_builder=_make_breakout_fixture,
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signals.strong_risk_on is False
    assert signal.meta["residual_weight_regime_mode"] == "strong_risk_on"
    assert signal.meta["residual_weight_conditional_active"] is False
    assert signal.meta["residual_benchmark_weight"] == 0.0
    assert signal.meta["residual_industry_weight"] == 1.0
    assert signal.meta["residual_benchmark_weight_fallback"] == 0.5
    assert signal.meta["residual_industry_weight_fallback"] == 0.5
    assert signal.meta["residual_benchmark_weight_effective"] == 0.5
    assert signal.meta["residual_industry_weight_effective"] == 0.5


def test_breakout_provider_emits_strict_industry_relative_meta_fields() -> None:
    _, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_window=40,
            residual_benchmark_weight=0.5,
            residual_industry_weight=0.5,
            industry_relative_mode="industry_rank_pct",
            industry_relative_regime_mode="strong_risk_on",
        ),
        fixture_builder=_make_breakout_fixture,
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signal.meta["industry_relative_mode"] == "industry_rank_pct"
    assert signal.meta["industry_relative_regime_mode"] == "strong_risk_on"
    assert signal.meta["industry_relative_mode_effective"] == "sector_proxy"
    assert signal.meta["industry_relative_conditional_active"] is False


def test_build_strategy_preserves_residual_split_weights() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_residual_ranking": True,
                "residual_window": 40,
                "residual_benchmark_weight": 0.7,
                "residual_industry_weight": 0.3,
            },
        )
    )

    assert isinstance(strategy, BreakoutTrendStrategy)
    assert strategy.residual_benchmark_weight == 0.7
    assert strategy.residual_industry_weight == 0.3


def test_build_strategy_preserves_industry_relative_mode_params() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_residual_ranking": True,
                "industry_relative_mode": "industry_rank_pct",
                "industry_relative_regime_mode": "strong_risk_on",
            },
        )
    )

    assert isinstance(strategy, BreakoutTrendStrategy)
    assert strategy.industry_relative_mode == "industry_rank_pct"
    assert strategy.industry_relative_regime_mode == "strong_risk_on"


def test_build_strategy_preserves_conditional_residual_weight_params() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_residual_ranking": True,
                "residual_benchmark_weight": 0.0,
                "residual_industry_weight": 1.0,
                "residual_weight_regime_mode": "strong_risk_on",
                "residual_benchmark_weight_fallback": 0.5,
                "residual_industry_weight_fallback": 0.5,
            },
        )
    )

    assert isinstance(strategy, BreakoutTrendStrategy)
    assert strategy.residual_weight_regime_mode == "strong_risk_on"
    assert strategy.residual_benchmark_weight_fallback == 0.5
    assert strategy.residual_industry_weight_fallback == 0.5


def test_build_strategy_preserves_quality_then_residual_params() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_residual_ranking": True,
                "ranking_mode": "quality_then_residual",
                "breakout_quality_gate_min_score": 0.6,
                "breakout_quality_margin_cap_pct": 0.07,
                "breakout_quality_fade_cap_pct": 0.03,
                "breakout_quality_open_gap_cap_pct": 0.035,
            },
        )
    )

    assert isinstance(strategy, BreakoutTrendStrategy)
    assert strategy.ranking_mode == "quality_then_residual"
    assert strategy.breakout_quality_gate_min_score == 0.6
    assert strategy.breakout_quality_margin_cap_pct == 0.07
    assert strategy.breakout_quality_fade_cap_pct == 0.03
    assert strategy.breakout_quality_open_gap_cap_pct == 0.035


def test_build_strategy_preserves_leadership_then_residual_params() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="breakout_trend",
            params={
                "enable_residual_ranking": True,
                "ranking_mode": "leadership_then_residual",
                "leadership_route_bucket_count": 3,
            },
        )
    )

    assert isinstance(strategy, BreakoutTrendStrategy)
    assert strategy.ranking_mode == "leadership_then_residual"
    assert strategy.leadership_route_bucket_count == 3


def test_breakout_provider_emits_quality_then_residual_meta_fields() -> None:
    _, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            ranking_mode="quality_then_residual",
            breakout_quality_gate_min_score=0.10,
        ),
        fixture_builder=_make_breakout_fixture,
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signal.meta["ranking_mode"] == "quality_then_residual"
    assert "breakout_quality_score" in signal.meta
    assert "breakout_open_gap_raw" in signal.meta
    assert "breakout_fade_raw" in signal.meta
    assert signal.meta["breakout_quality_pass"] is True


def test_breakout_provider_emits_conditional_tiebreak_meta_fields() -> None:
    _, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_refine_mode="conditional_tiebreak",
            residual_refine_weight=0.2,
        ),
        fixture_builder=_make_conditional_tiebreak_fixture,
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signal.meta["residual_refine_mode"] == "conditional_tiebreak"
    assert signal.meta["conditional_tiebreak_score"] is not None
    assert signal.meta["conditional_factor_leader_score"] is not None
    assert signal.meta["conditional_institution_proxy_score"] is not None
    assert signal.meta["conditional_crowding_score"] is not None
    assert signal.meta["conditional_recent_limit_hit_3d"] is True
    assert signal.meta["conditional_near_limit_up"] is True


def test_breakout_provider_emits_industry_second_stage_meta_fields() -> None:
    history, benchmark, raw_history, trading_days = _make_conditional_tiebreak_fixture()
    industry_name = "银行"
    sector_code = SW_L1_INDEX_MAP[industry_name]
    sector_rows = [
        {
            "trade_date": day.isoformat(),
            "close": 100.0 + float(i) * 0.8,
        }
        for i, day in enumerate(trading_days)
    ]
    industry_history = pd.DataFrame(
        [
            {
                "ts_code": "sh600000",
                "industry_l1": industry_name,
                "standard": "SW2021",
                "start_date": trading_days[0].isoformat(),
                "end_date": None,
            }
        ]
    )
    provider = BreakoutTrendProvider()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=raw_history,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_benchmark_weight=0.0,
            residual_industry_weight=1.0,
            residual_refine_mode="industry_second_stage",
            residual_refine_weight=0.15,
            industry_second_stage_min_industry_score=0.0,
        ),
        exit_cfg=ExitConfig(),
        sector_data={sector_code: pd.DataFrame(sector_rows)},
        industry_history=industry_history,
    )
    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        DayContext(
            positions={},
            position_avg_cost={},
            cash=1_000_000.0,
            nav=1_000_000.0,
            base_order_value=100_000.0,
            max_positions=10,
            close_idx={},
            open_idx={},
            next_day=None,
        ),
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signal.meta["residual_refine_mode"] == "industry_second_stage"
    assert signal.meta["industry_second_stage_score"] is not None
    assert signal.meta["industry_second_stage_not_hot_score"] is not None
    assert signal.meta["industry_second_stage_uncrowded_score"] is not None
    assert signal.meta["industry_second_stage_breadth_timing_score"] is not None
    assert signal.meta["industry_second_stage_persistence_10d"] is not None
    assert isinstance(signal.meta["industry_second_stage_active"], bool)
    assert signal.meta["industry_second_stage_min_industry_score"] == 0.0


def test_breakout_provider_emits_industry_second_stage_tiebreak_meta_fields() -> None:
    history, benchmark, raw_history, trading_days = _make_conditional_tiebreak_fixture()
    industry_name = "银行"
    sector_code = SW_L1_INDEX_MAP[industry_name]
    sector_rows = [
        {
            "trade_date": day.isoformat(),
            "close": 100.0 + float(i) * 0.8,
        }
        for i, day in enumerate(trading_days)
    ]
    industry_history = pd.DataFrame(
        [
            {
                "ts_code": "sh600000",
                "industry_l1": industry_name,
                "standard": "SW2021",
                "start_date": trading_days[0].isoformat(),
                "end_date": None,
            }
        ]
    )
    provider = BreakoutTrendProvider()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=raw_history,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            residual_benchmark_weight=0.0,
            residual_industry_weight=1.0,
            residual_refine_mode="industry_second_stage_tiebreak",
            industry_second_stage_min_industry_score=0.0,
        ),
        exit_cfg=ExitConfig(),
        sector_data={sector_code: pd.DataFrame(sector_rows)},
        industry_history=industry_history,
    )
    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        DayContext(
            positions={},
            position_avg_cost={},
            cash=1_000_000.0,
            nav=1_000_000.0,
            base_order_value=100_000.0,
            max_positions=10,
            close_idx={},
            open_idx={},
            next_day=None,
        ),
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signal.meta["residual_refine_mode"] == "industry_second_stage_tiebreak"
    assert signal.meta["industry_second_stage_score"] is not None
    assert isinstance(signal.meta["industry_second_stage_active"], bool)
    assert signal.meta["industry_second_stage_min_industry_score"] == 0.0


def test_breakout_provider_emits_leadership_route_meta_fields() -> None:
    _, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            ranking_mode="leadership_then_residual",
            leadership_route_bucket_count=3,
        ),
        fixture_builder=_make_conditional_tiebreak_fixture,
    )

    assert len(signals.buy_signals) == 1
    signal = signals.buy_signals[0]
    assert signal.meta["ranking_mode"] == "leadership_then_residual"
    assert signal.meta["leadership_route_score"] is not None
    assert signal.meta["leadership_route_rank"] is not None
    assert signal.meta["leadership_route_bucket"] is not None
    assert signal.meta["leadership_route_bucket_count"] == 3


def test_breakout_provider_filters_low_quality_breakout_in_quality_then_residual_mode() -> None:
    _, signals = _run_provider(
        BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_residual_ranking=True,
            ranking_mode="quality_then_residual",
            breakout_quality_gate_min_score=0.55,
        ),
        fixture_builder=_make_low_quality_breakout_fixture,
    )

    assert signals.buy_signals == []


def test_breakout_provider_emits_profit_decay_exit_for_profitable_weak_holding() -> None:
    history, benchmark, trading_days = _make_price_fixture([10.0] * 39 + [11.0])
    provider = BreakoutTrendProvider()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_profit_decay_exit=True,
            profit_decay_exit_profit_pct=0.12,
            profit_decay_exit_min_hold_bars=8,
            profit_decay_exit_residual_score_threshold=0.35,
        ),
        exit_cfg=ExitConfig(enable_profit_decay_exit=True),
    )
    provider.entry_day["sh600000"] = trading_days[20]
    provider.entry_bar_index["sh600000"] = 20
    provider._residual_strength_score[-1, 0] = 0.2
    provider._mx.close[-1, 0] = 11.0
    provider._feats.sma20 = provider._feats.sma20.copy()
    provider._feats.sma20[-1, 0] = 11.5

    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        DayContext(
            positions={"sh600000": 100},
            position_avg_cost={"sh600000": 9.5},
            cash=1_000_000.0,
            nav=1_000_000.0,
            base_order_value=100_000.0,
            max_positions=10,
            close_idx={(trading_days[-1], "sh600000"): 11.0},
            open_idx={},
            next_day=None,
        ),
    )

    assert len(signals.sell_signals) == 1
    signal = signals.sell_signals[0]
    assert signal.reason_code == "PROFIT_DECAY_EXIT"
    assert signal.meta["residual_strength_score"] == 0.2
    assert signal.meta["profit_decay_exit_min_hold_bars"] == 8
    assert signals.exit_counts.profit_decay_exit == 1


def test_breakout_provider_skips_profit_decay_exit_when_residual_strength_still_high() -> None:
    history, benchmark, trading_days = _make_price_fixture([10.0] * 39 + [11.0])
    provider = BreakoutTrendProvider()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
            enable_profit_decay_exit=True,
            profit_decay_exit_profit_pct=0.12,
            profit_decay_exit_min_hold_bars=8,
            profit_decay_exit_residual_score_threshold=0.35,
        ),
        exit_cfg=ExitConfig(enable_profit_decay_exit=True),
    )
    provider.entry_day["sh600000"] = trading_days[20]
    provider.entry_bar_index["sh600000"] = 20
    provider._residual_strength_score[-1, 0] = 0.6
    provider._mx.close[-1, 0] = 11.0
    provider._feats.sma20 = provider._feats.sma20.copy()
    provider._feats.sma20[-1, 0] = 11.5

    signals = provider.day_signals(
        trading_days[-1],
        len(trading_days) - 1,
        DayContext(
            positions={"sh600000": 100},
            position_avg_cost={"sh600000": 9.5},
            cash=1_000_000.0,
            nav=1_000_000.0,
            base_order_value=100_000.0,
            max_positions=10,
            close_idx={(trading_days[-1], "sh600000"): 11.0},
            open_idx={},
            next_day=None,
        ),
    )

    assert signals.sell_signals == []
    assert signals.exit_counts.profit_decay_exit == 0


def test_breakout_provider_emits_formal_regime_arrays() -> None:
    history, benchmark, trading_days = _make_breakout_fixture()
    benchmark = benchmark.copy()
    benchmark["high"] = pd.to_numeric(benchmark["close"], errors="coerce") + 1.0
    benchmark["low"] = pd.to_numeric(benchmark["close"], errors="coerce") - 1.0

    provider = BreakoutTrendProvider()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
        ),
        exit_cfg=ExitConfig(),
        market_filter_cfg=MarketFilterConfig(enabled=True),
        regime_engine_cfg=RegimeEngineConfig(engine="market_regime_framework"),
        governed_a_share={
            "regime": {
                "manual_override": {
                    "active": True,
                    "reason": "manual_risk_cut",
                    "scope": "cn_a_mainline",
                    "actor": "pm",
                    "target_state_5": "LIGHT",
                }
            }
        },
    )

    assert provider._regime_engine_name == "market_regime_framework"
    assert len(provider._market_state) == len(trading_days)
    assert len(provider._trade_mode) == len(trading_days)
    assert len(provider._regime_confidence_arr) == len(trading_days)
    assert len(provider._regime_duration_bars_arr) == len(trading_days)
    assert len(provider._regime_transition_reason_arr) == len(trading_days)
    assert len(provider._feature_availability_arr) == len(trading_days)
    assert len(provider._base_state_5_arr) == len(trading_days)
    assert len(provider._effective_state_5_arr) == len(trading_days)
    assert len(provider._coarse_state_arr) == len(trading_days)
    assert len(provider._effective_coarse_state_arr) == len(trading_days)
    assert len(provider._reason_codes_arr) == len(trading_days)
    assert len(provider._block_scores_arr) == len(trading_days)
    assert len(provider._subscores_arr) == len(trading_days)
    assert len(provider._manual_override_arr) == len(trading_days)
    assert len(provider._state_stability_metrics_arr) == len(trading_days)
    assert len(provider._regime_risk_budget_multiplier_arr) == len(trading_days)
    assert len(provider._defense_bias_arr) == len(trading_days)
    assert set(provider._base_state_5_arr.tolist()).issubset({"BULL", "TRANS_UP", "TRANS_DOWN", "RISK_OFF"})
    assert set(provider._effective_state_5_arr.tolist()) == {"TRANS_UP"}
    assert "MANUAL_OVERRIDE_ACTIVE" in set(provider._reason_codes_arr[-1])
    assert provider._runtime_state.base_state_5.shape[0] == len(trading_days)
    assert provider._runtime_state.manual_override.shape[0] == len(trading_days)
    assert provider._runtime_state.regime_engine == "market_regime_framework"


def test_breakout_provider_emits_weekly_five_state_arrays() -> None:
    closes = [100.0 + float(i) for i in range(180)]
    history, benchmark, trading_days = _make_price_fixture(closes)
    benchmark = benchmark.copy()
    benchmark["high"] = pd.to_numeric(benchmark["close"], errors="coerce") + 1.0
    benchmark["low"] = pd.to_numeric(benchmark["close"], errors="coerce") - 1.0

    provider = BreakoutTrendProvider()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
        ),
        exit_cfg=ExitConfig(),
        market_filter_cfg=MarketFilterConfig(enabled=True),
        regime_engine_cfg=RegimeEngineConfig(engine="weekly_five_state"),
    )

    assert provider._regime_engine_name == "weekly_five_state"
    assert len(provider._market_state) == len(trading_days)
    assert len(provider._trade_mode) == len(trading_days)
    assert len(provider._market_state_name_arr) == len(trading_days)
    assert len(provider._market_state_raw_name_arr) == len(trading_days)
    assert len(provider._market_state_smoothed_name_arr) == len(trading_days)
    assert len(provider._risk_budget_multiplier_arr) == len(trading_days)
    assert len(provider._weekly_observation_flag_arr) == len(trading_days)
    assert provider._runtime_state.regime_engine == "weekly_five_state"
    assert "BULL_MAIN" in set(provider._market_state_name_arr.tolist())


def test_breakout_provider_legacy_overlay_only_vetoes_turn_weak(monkeypatch) -> None:
    closes = [100.0 + float(i) for i in range(180)]
    history, benchmark, trading_days = _make_price_fixture(closes)
    benchmark = benchmark.copy()
    benchmark["high"] = pd.to_numeric(benchmark["close"], errors="coerce") + 1.0
    benchmark["low"] = pd.to_numeric(benchmark["close"], errors="coerce") - 1.0

    def _fake_eval(**_: object) -> WeeklyFiveStateEvaluation:
        day_count = len(trading_days)
        smoothed_names = np.array(["BULL_MAIN"] * day_count, dtype=object)
        smoothed_names[-1] = "TURN_WEAK"
        return WeeklyFiveStateEvaluation(
            market_state_codes=np.full(day_count, 4, dtype=np.int8),
            market_state_names=np.array(["BULL_MAIN"] * day_count, dtype=object),
            market_state_raw_names=np.array(smoothed_names, dtype=object),
            market_state_smoothed_names=np.array(smoothed_names, dtype=object),
            trade_mode_codes=np.zeros(day_count, dtype=np.int8),
            trade_mode_names=np.array(["TREND_MAIN"] * day_count, dtype=object),
            risk_budget_multipliers=np.ones(day_count, dtype=float),
            state_scores=np.full(day_count, 5.0, dtype=float),
            weekly_observation_flags=np.zeros(day_count, dtype=bool),
            regime_confidence=np.full(day_count, 0.8, dtype=float),
            regime_duration_bars=np.ones(day_count, dtype=np.int32),
            regime_transition_reason=np.array(["UNCHANGED"] * day_count, dtype=object),
            feature_availability=np.array([{"all_ready": True}] * day_count, dtype=object),
            fallback_active=np.zeros(day_count, dtype=bool),
        )

    monkeypatch.setattr(
        "backend.core.engine_vector.breakout_signal_provider.evaluate_weekly_five_state_regime",
        _fake_eval,
    )

    provider = BreakoutTrendProvider()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=None,
        trading_days=trading_days,
        strategy=BreakoutTrendStrategy(
            breakout_window=20,
            enable_v2_trend_filter=False,
        ),
        exit_cfg=ExitConfig(),
        market_filter_cfg=MarketFilterConfig(enabled=True),
        regime_engine_cfg=RegimeEngineConfig(
            engine="ma200_legacy",
            legacy_turn_weak_overlay=LegacyTurnWeakOverlayConfig(
                enabled=True,
                weekly_cfg=WeeklyFiveStateRegimeConfig(benchmark="000001.SH"),
            ),
        ),
    )

    assert provider._regime_engine_name == "ma200_legacy"
    assert provider._legacy_turn_weak_overlay_active is True
    assert provider._market_state_name_arr[-1] == "BULL"
    assert provider._market_state_smoothed_name_arr[-1] == "TURN_WEAK"
    assert provider._trade_mode_name_arr[-1] == "NO_TRADE"
    assert float(provider._risk_budget_multiplier_arr[-1]) == 0.0
