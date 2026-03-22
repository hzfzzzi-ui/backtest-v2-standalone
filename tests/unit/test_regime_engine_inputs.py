from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from backend.core.config.models import ExitConfig
from backend.core.config.models import RegimeEngineConfig
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.regime_engine_evaluator import evaluate_formal_regime_engine
from backend.core.engine_vector.regime_engine_inputs import build_formal_regime_feature_bundle
from backend.core.engine_vector.regime_engine_inputs import resolve_required_regime_blocks
from backend.core.engine_vector.regime_router_signal_provider import RegimeRouterSignalProvider


def _make_days(periods: int = 260) -> list[pd.Timestamp]:
    return list(pd.bdate_range("2023-01-02", periods=periods))


def _make_benchmark(days: list[pd.Timestamp]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for idx, day in enumerate(days):
        close = 3000.0 + idx * 1.8 + ((idx % 9) - 4) * 3.5
        rows.append(
            {
                "date": day,
                "symbol": "000300.SH",
                "open": close - 8.0,
                "high": close + 12.0,
                "low": close - 14.0,
                "close": close,
                "amount": 8.0e10 + idx * 1.0e8,
            }
        )
    return pd.DataFrame(rows)


def _make_history(days: list[pd.Timestamp]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    symbols = ("sh600000", "sz000001", "sh600036")
    for sym_idx, symbol in enumerate(symbols):
        base = 10.0 + sym_idx * 3.0
        for idx, day in enumerate(days):
            close = base + idx * (0.015 + sym_idx * 0.002) + ((idx + sym_idx) % 5) * 0.03
            volume = 1.2e6 + sym_idx * 2.0e5 + idx * 1200.0
            amount = close * volume
            rows.append(
                {
                    "date": day,
                    "symbol": symbol,
                    "open": close - 0.08,
                    "high": close + 0.18,
                    "low": close - 0.16,
                    "close": close,
                    "volume": volume,
                    "amount": amount,
                    "turnover_rate": 0.8 + sym_idx * 0.15 + (idx % 10) * 0.01,
                    "turnover_rate_f": 0.9 + sym_idx * 0.12 + (idx % 8) * 0.01,
                    "is_suspended": False,
                }
            )
    return pd.DataFrame(rows)


def _make_strategy() -> SimpleNamespace:
    return SimpleNamespace(
        detector=SimpleNamespace(regime_ma=60),
        trend_strategy=SimpleNamespace(
            fast=5,
            slow=20,
            order_size=1000,
            ma_type="SMA",
            min_price=0.0,
        ),
        mr_strategy=SimpleNamespace(
            rsi_period=6,
            rsi_buy_threshold=20.0,
            rsi_sell_threshold=80.0,
            mr_max_hold_days=5,
            mr_stop_loss_pct=0.03,
            order_size=1000,
        ),
        state={"universe_filters": {}},
    )


def test_build_formal_regime_feature_bundle_supports_all_blocks_with_strategy_universe() -> None:
    days = _make_days()
    benchmark = _make_benchmark(days)
    history = _make_history(days)
    mx = build_ohlc_matrices_from_history(history, [day.date() for day in days])
    cfg = RegimeEngineConfig(engine="market_regime_framework")
    cfg.breadth_block.universe = "strategy_universe"

    bundle = build_formal_regime_feature_bundle(
        benchmark=benchmark,
        history=history,
        mx=mx,
        trading_days=[day.date() for day in days],
        regime_engine_cfg=cfg,
        membership_history=None,
    )

    assert len(bundle.dates) == len(days)
    assert np.isfinite(bundle.trend_long_ma[-1])
    assert np.isfinite(bundle.risk_realized_vol[-1])
    assert np.isfinite(bundle.breadth_above_ma_long_ratio[-1])
    assert np.isfinite(bundle.participation_amount_mean[-1])
    assert bool(bundle.feature_availability.trend_block[-1]) is True
    assert bool(bundle.feature_availability.risk_block[-1]) is True
    assert bool(bundle.feature_availability.breadth_block[-1]) is True
    assert bool(bundle.feature_availability.participation_block[-1]) is True
    required_mask = resolve_required_regime_blocks(
        bundle.feature_availability,
        cfg.fallback.required_blocks,
    )
    assert bool(required_mask[-1]) is True


def test_build_formal_regime_feature_bundle_marks_breadth_unavailable_without_membership_history() -> None:
    days = _make_days()
    benchmark = _make_benchmark(days)
    history = _make_history(days)
    mx = build_ohlc_matrices_from_history(history, [day.date() for day in days])
    cfg = RegimeEngineConfig(engine="market_regime_framework")
    cfg.breadth_block.universe = "benchmark_constituents"
    cfg.fallback.required_blocks = ["trend_block", "breadth_block"]

    bundle = build_formal_regime_feature_bundle(
        benchmark=benchmark,
        history=history,
        mx=mx,
        trading_days=[day.date() for day in days],
        regime_engine_cfg=cfg,
        membership_history=None,
    )

    assert not bool(bundle.feature_availability.breadth_block.any())
    assert np.isnan(bundle.breadth_above_ma_short_ratio).all()


def test_regime_router_precompute_attaches_formal_feature_bundle_without_changing_engine_default() -> None:
    days = _make_days()
    benchmark = _make_benchmark(days)
    history = _make_history(days)
    provider = RegimeRouterSignalProvider()
    cfg = RegimeEngineConfig(engine="market_regime_framework")
    cfg.breadth_block.universe = "strategy_universe"

    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=history,
        trading_days=[day.date() for day in days],
        strategy=_make_strategy(),
        exit_cfg=ExitConfig(),
        regime_engine_cfg=cfg,
    )

    assert provider._regime_engine_name == "market_regime_framework"
    assert provider._formal_regime_features is not None
    assert provider._required_feature_blocks_ready.size == len(days)
    assert bool(provider._required_feature_blocks_ready[-1]) is True
    assert provider._regime_confidence_arr.shape == (len(days),)
    assert provider._regime_duration_bars_arr.shape == (len(days),)
    assert provider._regime_transition_reason_arr.shape == (len(days),)
    assert provider._feature_availability_arr.shape == (len(days),)
    assert provider._fallback_active_arr.shape == (len(days),)
    assert isinstance(provider._feature_availability_arr[-1], dict)
    assert "required_blocks_ready" in provider._feature_availability_arr[-1]


def test_formal_regime_engine_uses_legacy_fallback_when_required_blocks_missing() -> None:
    days = _make_days()
    benchmark = _make_benchmark(days)
    history = _make_history(days)
    mx = build_ohlc_matrices_from_history(history, [day.date() for day in days])
    cfg = RegimeEngineConfig(engine="market_regime_framework")
    cfg.breadth_block.universe = "benchmark_constituents"
    cfg.fallback.required_blocks = ["trend_block", "breadth_block"]

    bundle = build_formal_regime_feature_bundle(
        benchmark=benchmark,
        history=history,
        mx=mx,
        trading_days=[day.date() for day in days],
        regime_engine_cfg=cfg,
        membership_history=None,
    )
    legacy_market_state = np.full(len(days), 3, dtype=np.int32)
    legacy_trade_mode = np.full(len(days), 2, dtype=np.int32)

    result = evaluate_formal_regime_engine(
        bundle=bundle,
        regime_engine_cfg=cfg,
        legacy_market_state=legacy_market_state,
        legacy_trade_mode=legacy_trade_mode,
    )

    assert result.market_state.shape == (len(days),)
    assert result.trade_mode.shape == (len(days),)
    assert bool(result.fallback_active[-1]) is True
    assert int(result.market_state[-1]) == 3
    assert int(result.trade_mode[-1]) == 2
    assert result.regime_transition_reason[-1] == "FALLBACK_FEATURE_UNAVAILABLE"
    assert isinstance(result.feature_availability[-1], dict)
    assert result.feature_availability[-1]["required_blocks_ready"] is False
