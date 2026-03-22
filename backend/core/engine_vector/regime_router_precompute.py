"""Precompute stage for the regime router provider."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import MarketFilterConfig
from backend.core.config.models import RegimeEngineBreadthBlockConfig
from backend.core.config.models import RegimeEngineConfig
from backend.core.config.models import RegimeEngineFallbackConfig
from backend.core.config.models import RegimeEngineParticipationBlockConfig
from backend.core.config.models import RegimeEnginePersistenceConfig
from backend.core.config.models import RegimeEngineRiskBlockConfig
from backend.core.config.models import RegimeEngineTrendBlockConfig
from backend.core.engine_vector.candidate_index import build_daily_candidate_index
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.features import compute_feature_matrices
from backend.core.engine_vector.regime_engine_evaluator import evaluate_formal_regime_engine
from backend.core.engine_vector.regime_engine_inputs import build_formal_regime_feature_bundle
from backend.core.engine_vector.regime_engine_inputs import resolve_required_regime_blocks
from backend.core.engine_vector.regime_filter import RegimeFilter
from backend.core.engine_vector.regime_filter import RegimeFilterConfig
from backend.core.engine_vector.regime_router_models import apply_regime_router_config
from backend.core.engine_vector.regime_router_models import build_regime_router_config
from backend.core.engine_vector.regime_router_models import capture_regime_router_runtime_state


def _coerce_regime_engine_cfg(value: RegimeEngineConfig | dict[str, Any] | None) -> RegimeEngineConfig:
    if isinstance(value, RegimeEngineConfig):
        fields = {
            key: getattr(value, key)
            for key in RegimeEngineConfig.__dataclass_fields__
            if hasattr(value, key)
        }
    elif isinstance(value, dict):
        fields = {k: v for k, v in value.items() if k in RegimeEngineConfig.__dataclass_fields__}
    else:
        return RegimeEngineConfig()
    trend_block = fields.get("trend_block")
    if isinstance(trend_block, dict):
        fields["trend_block"] = RegimeEngineTrendBlockConfig(**trend_block)
    risk_block = fields.get("risk_block")
    if isinstance(risk_block, dict):
        fields["risk_block"] = RegimeEngineRiskBlockConfig(**risk_block)
    breadth_block = fields.get("breadth_block")
    if isinstance(breadth_block, dict):
        fields["breadth_block"] = RegimeEngineBreadthBlockConfig(**breadth_block)
    participation_block = fields.get("participation_block")
    if isinstance(participation_block, dict):
        fields["participation_block"] = RegimeEngineParticipationBlockConfig(**participation_block)
    persistence = fields.get("persistence")
    if isinstance(persistence, dict):
        fields["persistence"] = RegimeEnginePersistenceConfig(**persistence)
    fallback = fields.get("fallback")
    if isinstance(fallback, dict):
        fields["fallback"] = RegimeEngineFallbackConfig(**fallback)
    return RegimeEngineConfig(**fields)


def precompute_regime_router_provider(
    provider: Any,
    *,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    raw_history: pd.DataFrame | None,
    trading_days: list[date],
    strategy: Any,
    **kwargs: Any,
) -> None:
    import time as _time

    pre_t0 = _time.perf_counter()
    exit_cfg = kwargs.get("exit_cfg") or provider._ec
    config = build_regime_router_config(strategy, kwargs=kwargs)
    apply_regime_router_config(provider, config, exit_cfg=exit_cfg)
    st_history = kwargs.get("st_history")
    membership_history = kwargs.get("membership_history")
    regime_engine_cfg = _coerce_regime_engine_cfg(kwargs.get("regime_engine_cfg"))
    provider._regime_engine_name = str(regime_engine_cfg.engine or "ma200_legacy")
    provider._formal_regime_features = None
    provider._required_feature_blocks_ready = np.array([], dtype=bool)
    provider._regime_confidence_arr = np.array([], dtype=float)
    provider._regime_duration_bars_arr = np.array([], dtype=np.int32)
    provider._regime_transition_reason_arr = np.array([], dtype=object)
    provider._feature_availability_arr = np.array([], dtype=object)
    provider._fallback_active_arr = np.array([], dtype=bool)

    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    provider._mx = build_ohlc_matrices_from_history(
        hist,
        trading_days,
        st_history=st_history,
        membership_history=membership_history,
        min_price=float(config.min_price),
        min_list_days=int(config.min_list_days),
        min_avg_turnover_20d=float(config.min_avg_turnover_20d),
    )
    mx = provider._mx
    t, n = mx.close.shape
    if n == 0:
        raise ValueError("history has no symbols")

    provider._sym_to_col = {s: idx for idx, s in enumerate(mx.symbols)}

    provider._feats = compute_feature_matrices(
        close=mx.close,
        high=mx.high,
        low=mx.low,
        fast=int(config.fast),
        slow=int(config.slow),
        trend_fast=120,
        trend_slow=200,
        atr_n=14,
        strength_ma=120,
        ma_type=str(config.ma_type),
        rsi_period=int(config.mr_rsi_period),
    )
    feats = provider._feats

    if str(provider._regime_engine_name).strip().lower() == "market_regime_framework":
        formal_bundle = build_formal_regime_feature_bundle(
            benchmark=benchmark,
            history=hist,
            mx=mx,
            trading_days=trading_days,
            regime_engine_cfg=regime_engine_cfg,
            membership_history=membership_history,
        )
        provider._formal_regime_features = formal_bundle
        provider._required_feature_blocks_ready = resolve_required_regime_blocks(
            formal_bundle.feature_availability,
            regime_engine_cfg.fallback.required_blocks,
        )

    bench = benchmark.copy()
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.sort_values("date")
    bench_close_s = pd.to_numeric(bench["close"], errors="coerce")

    bench_regime_ma_s = bench_close_s.rolling(int(config.regime_ma), min_periods=int(config.regime_ma)).mean()
    bmap_close = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_close_s)}
    bmap_regime = {
        pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
        for d, v in zip(bench["date"], bench_regime_ma_s)
    }
    provider._bench_close = np.array(
        [bmap_close.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
        dtype=float,
    )
    bench_regime_arr = np.array(
        [bmap_regime.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
        dtype=float,
    )
    provider._regime_on = np.ones(t, dtype=bool)
    valid_regime = ~np.isnan(provider._bench_close) & ~np.isnan(bench_regime_arr)
    provider._regime_on[valid_regime] = provider._bench_close[valid_regime] > bench_regime_arr[valid_regime]

    rf_cfg_raw = kwargs.get("regime_filter_cfg") or getattr(strategy, "regime_filter_cfg", None)
    sector_data_kw: dict[str, pd.DataFrame] = kwargs.get("sector_data") or {}
    industry_map_kw: dict[str, str] = kwargs.get("industry_map") or {}

    rf_config: RegimeFilterConfig | None = None
    if isinstance(rf_cfg_raw, RegimeFilterConfig):
        rf_config = rf_cfg_raw
    elif isinstance(rf_cfg_raw, dict) and rf_cfg_raw.get("enabled", True):
        rf_fields = {
            k: v
            for k, v in rf_cfg_raw.items()
            if k in RegimeFilterConfig.__dataclass_fields__
        }
        rf_config = RegimeFilterConfig(**rf_fields)

    if rf_config is not None and rf_config.enabled:
        provider._regime_filter = RegimeFilter(rf_config)
        bench_high_s = pd.to_numeric(bench["high"], errors="coerce")
        bench_low_s = pd.to_numeric(bench["low"], errors="coerce")
        bmap_high = {
            pd.Timestamp(d).normalize(): float(v)
            for d, v in zip(bench["date"], bench_high_s)
            if pd.notna(v)
        }
        bmap_low = {
            pd.Timestamp(d).normalize(): float(v)
            for d, v in zip(bench["date"], bench_low_s)
            if pd.notna(v)
        }
        bench_high_arr = np.array(
            [bmap_high.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
            dtype=float,
        )
        bench_low_arr = np.array(
            [bmap_low.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
            dtype=float,
        )

        sym_to_col = provider._sym_to_col or {s: idx for idx, s in enumerate(mx.symbols)}
        provider._regime_filter.precompute(
            benchmark_close=provider._bench_close,
            benchmark_high=bench_high_arr,
            benchmark_low=bench_low_arr,
            stock_close=mx.close,
            stock_high=mx.high,
            stock_low=mx.low,
            sector_data=sector_data_kw,
            industry_map=industry_map_kw,
            sym_to_col=sym_to_col,
            trading_days=list(trading_days),
        )
        provider._regime_on = provider._regime_filter.regime_signals >= rf_config.regime_threshold
        provider._use_regime_filter = True

    exit_regime_ma = 120
    bench_exit_ma_s = bench_close_s.rolling(exit_regime_ma, min_periods=exit_regime_ma).mean()
    bmap_exit = {
        pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
        for d, v in zip(bench["date"], bench_exit_ma_s)
    }
    bench_exit_arr = np.array(
        [bmap_exit.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
        dtype=float,
    )
    provider._risk_on_exits = np.ones(t, dtype=bool)
    valid_exit = ~np.isnan(provider._bench_close) & ~np.isnan(bench_exit_arr)
    provider._risk_on_exits[valid_exit] = provider._bench_close[valid_exit] > bench_exit_arr[valid_exit]

    bench_ma120_s = bench_close_s.rolling(120, min_periods=120).mean()
    bench_ma200_s = bench_close_s.rolling(200, min_periods=200).mean()
    bmap_ma120 = {
        pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
        for d, v in zip(bench["date"], bench_ma120_s)
    }
    bmap_ma200 = {
        pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
        for d, v in zip(bench["date"], bench_ma200_s)
    }
    bench_ma120 = np.array(
        [bmap_ma120.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
        dtype=float,
    )
    bench_ma200 = np.array(
        [bmap_ma200.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
        dtype=float,
    )
    provider._strong_risk_on = np.zeros(t, dtype=bool)
    valid_strong = ~np.isnan(bench_ma120) & ~np.isnan(bench_ma200)
    provider._strong_risk_on[valid_strong] = bench_ma120[valid_strong] > bench_ma200[valid_strong]

    mf_cfg_raw = kwargs.get("market_filter_cfg")
    mf_config: MarketFilterConfig | None = None
    if isinstance(mf_cfg_raw, MarketFilterConfig):
        mf_config = mf_cfg_raw
    elif isinstance(mf_cfg_raw, dict) and mf_cfg_raw.get("enabled", False):
        mf_fields = {
            k: v
            for k, v in mf_cfg_raw.items()
            if k in MarketFilterConfig.__dataclass_fields__
        }
        mf_config = MarketFilterConfig(**mf_fields)

    if mf_config is not None and mf_config.enabled:
        provider._use_market_filter = True
        long_ma_window = max(2, int(getattr(mf_config, "long_ma_window", 200)))
        slope_window = mf_config.slope_window
        slope_period = getattr(mf_config, "slope_ma_period", 50)
        ma200_arr = pd.Series(provider._bench_close).rolling(long_ma_window, min_periods=long_ma_window).mean().to_numpy(dtype=float)

        slope_ema_s = bench_close_s.ewm(span=slope_period, adjust=False).mean()
        bmap_slope_ema = {
            pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
            for d, v in zip(bench["date"], slope_ema_s)
        }
        slope_ema_arr = np.array(
            [bmap_slope_ema.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
            dtype=float,
        )
        momentum = np.full(t, np.nan, dtype=float)
        if slope_window < t:
            prev = slope_ema_arr[:-slope_window]
            curr = slope_ema_arr[slope_window:]
            safe_prev = np.where(np.abs(prev) > 1e-8, prev, np.nan)
            momentum[slope_window:] = (curr - prev) / safe_prev

        bench_ma20_s = bench_close_s.rolling(20, min_periods=20).mean()
        bench_ma60_s = bench_close_s.rolling(60, min_periods=60).mean()
        bmap_ma20 = {
            pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
            for d, v in zip(bench["date"], bench_ma20_s)
        }
        bmap_ma60 = {
            pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
            for d, v in zip(bench["date"], bench_ma60_s)
        }
        bench_ma20 = np.array(
            [bmap_ma20.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
            dtype=float,
        )
        bench_ma60 = np.array(
            [bmap_ma60.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
            dtype=float,
        )

        bench_high_s = pd.to_numeric(bench["high"], errors="coerce")
        bmap_high = {
            pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
            for d, v in zip(bench["date"], bench_high_s)
        }
        bench_high_arr = np.array(
            [bmap_high.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates],
            dtype=float,
        )
        bench_close_series = pd.Series(provider._bench_close)
        bench_high_series = pd.Series(bench_high_arr)
        close_max20 = bench_close_series.rolling(20, min_periods=20).max().values
        high_max60 = bench_high_series.rolling(60, min_periods=60).max().values

        market_state = np.zeros(t, dtype=np.int8)
        above_ma200 = provider._bench_close > ma200_arr
        slope_pos = momentum >= 0
        valid_market_filter = ~np.isnan(ma200_arr) & ~np.isnan(momentum) & ~np.isnan(provider._bench_close)
        market_state[valid_market_filter & above_ma200 & ~slope_pos] = 1
        market_state[valid_market_filter & ~above_ma200 & slope_pos] = 2
        market_state[valid_market_filter & ~above_ma200 & ~slope_pos] = 3
        provider._market_state = market_state

        cond_a = (
            (bench_ma20 > bench_ma60)
            & (provider._bench_close > bench_ma20)
            & (provider._bench_close > close_max20)
        )
        cond_b = (
            (provider._bench_close > high_max60)
            & (provider._bench_close > bench_ma60)
            & (bench_ma20 > bench_ma60)
        )
        cond_a[np.isnan(bench_ma20) | np.isnan(bench_ma60) | np.isnan(close_max20)] = False
        cond_b[np.isnan(bench_ma60) | np.isnan(high_max60) | np.isnan(bench_ma20)] = False

        trade_mode = np.full(t, 2, dtype=np.int8)
        trade_mode[market_state == 0] = 0
        trade_mode[(market_state == 1) & cond_a] = 1
        trade_mode[(market_state == 2) & cond_b] = 1
        provider._trade_mode = trade_mode

        ema_fast = mf_config.ema_light_fast
        ema_slow = mf_config.ema_light_slow
        close_filled = pd.DataFrame(mx.close).ffill().to_numpy(dtype=float)
        ema_fast_ma = pd.DataFrame(close_filled).ewm(span=ema_fast, adjust=False).mean().values
        ema_slow_ma = pd.DataFrame(close_filled).ewm(span=ema_slow, adjust=False).mean().values
        valid_ema = ~np.isnan(ema_fast_ma) & ~np.isnan(ema_slow_ma)
        provider._ema_light_buy_ok = valid_ema & (ema_fast_ma > ema_slow_ma)
        provider._ema_light_sell_ok = valid_ema & (ema_fast_ma < ema_slow_ma)
        provider._ema_light_cand_idx = build_daily_candidate_index(provider._ema_light_buy_ok)

    legacy_market_state = np.array(getattr(provider, "_market_state", np.zeros(t, dtype=np.int8)), dtype=np.int32)
    legacy_trade_mode = np.array(getattr(provider, "_trade_mode", np.full(t, 2, dtype=np.int8)), dtype=np.int32)
    if str(provider._regime_engine_name).strip().lower() == "market_regime_framework" and provider._formal_regime_features is not None:
        formal_eval = evaluate_formal_regime_engine(
            bundle=provider._formal_regime_features,
            regime_engine_cfg=regime_engine_cfg,
            legacy_market_state=legacy_market_state,
            legacy_trade_mode=legacy_trade_mode,
        )
        provider._market_state = np.array(formal_eval.market_state, dtype=np.int8)
        provider._trade_mode = np.array(formal_eval.trade_mode, dtype=np.int8)
        provider._regime_confidence_arr = np.array(formal_eval.regime_confidence, dtype=float)
        provider._regime_duration_bars_arr = np.array(formal_eval.regime_duration_bars, dtype=np.int32)
        provider._regime_transition_reason_arr = np.array(formal_eval.regime_transition_reason, dtype=object)
        provider._feature_availability_arr = np.array(formal_eval.feature_availability, dtype=object)
        provider._fallback_active_arr = np.array(formal_eval.fallback_active, dtype=bool)
        provider._use_market_filter = True

    close_filled = pd.DataFrame(mx.close).ffill().to_numpy(dtype=float)
    if str(config.ma_type) == "EMA":
        fast_ma_filled = pd.DataFrame(close_filled).ewm(span=int(config.fast), adjust=False).mean().values
        slow_ma_filled = pd.DataFrame(close_filled).ewm(span=int(config.slow), adjust=False).mean().values
    else:
        fast_ma_filled = pd.DataFrame(close_filled).rolling(int(config.fast), min_periods=int(config.fast)).mean().values
        slow_ma_filled = pd.DataFrame(close_filled).rolling(int(config.slow), min_periods=int(config.slow)).mean().values
    valid_sma = ~np.isnan(fast_ma_filled) & ~np.isnan(slow_ma_filled)
    provider._sma_buy_ok = valid_sma & (fast_ma_filled > slow_ma_filled)
    provider._sma_sell_ok = valid_sma & (fast_ma_filled < slow_ma_filled)
    provider._sma_cand_idx = build_daily_candidate_index(provider._sma_buy_ok)

    rsi = feats.rsi
    rsi_prev = np.full_like(rsi, np.nan)
    rsi_prev[1:, :] = rsi[:-1, :]
    with np.errstate(invalid="ignore"):
        provider._rsi_buy = (rsi_prev <= float(config.mr_rsi_buy_threshold)) & (rsi > float(config.mr_rsi_buy_threshold))
        provider._rsi_overbought = (rsi_prev >= float(config.mr_rsi_sell_threshold)) & (rsi < float(config.mr_rsi_sell_threshold))
    provider._rsi_buy[np.isnan(rsi_prev) | np.isnan(rsi)] = False
    provider._rsi_overbought[np.isnan(rsi_prev) | np.isnan(rsi)] = False
    provider._rsi_cand_idx = build_daily_candidate_index(provider._rsi_buy)

    atr_n = 14
    ecfg = exit_cfg
    provider._need_atr = (
        ecfg.enable_atr_stop
        or ecfg.enable_atr_trail
        or (ecfg.enable_take_profit and ecfg.take_profit_mode == "atr")
    )
    if provider._need_atr:
        raw_for_atr = raw_history if raw_history is not None else history
        raw_atr_df = raw_for_atr.copy()
        raw_atr_df["date"] = pd.to_datetime(raw_atr_df["date"])
        raw_atr_df["symbol"] = raw_atr_df["symbol"].astype(str).str.lower()
        for sym_name, sym_df in raw_atr_df.groupby("symbol"):
            sym_str = str(sym_name).lower()
            sym_df = sym_df.sort_values("date")
            high_s = pd.to_numeric(sym_df["high"], errors="coerce")
            low_s = pd.to_numeric(sym_df["low"], errors="coerce")
            close_s = pd.to_numeric(sym_df["close"], errors="coerce")
            prev_close = close_s.shift(1)
            tr = pd.concat(
                [
                    (high_s - low_s).abs(),
                    (high_s - prev_close).abs(),
                    (low_s - prev_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            atr_series = tr.rolling(atr_n, min_periods=atr_n).mean()
            atr_map: dict[date, float] = {}
            for ts, atr_val in zip(sym_df["date"], atr_series):
                if pd.notna(atr_val):
                    atr_map[pd.Timestamp(ts).date()] = float(atr_val)
            provider._atr_lookup[sym_str] = atr_map

    provider._peak_close_state = {}
    provider._mr_symbols = set()
    provider._mr_entry_day = {}
    provider._mr_entry_price = {}
    provider.entry_day = {}
    provider.extra_clear_dicts = [provider._peak_close_state]
    provider.last_sell_day = None
    provider.peak_state_on_buy = None
    provider.extra_daily_init = {"strong_risk_on": 0}
    provider.precompute_seconds = float(_time.perf_counter() - pre_t0)
    capture_regime_router_runtime_state(provider)
