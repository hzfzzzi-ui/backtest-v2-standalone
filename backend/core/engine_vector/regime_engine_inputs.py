from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import RegimeEngineConfig
from backend.core.engine_vector.data_matrix import OhlcMatrices


def _empty_float_array() -> np.ndarray:
    return np.array([], dtype=float)


def _empty_bool_array() -> np.ndarray:
    return np.array([], dtype=bool)


def _safe_float_series(values: pd.Series, *, index: pd.Index | None = None) -> pd.Series:
    out = pd.to_numeric(values, errors="coerce")
    if index is not None:
        out = pd.Series(out.to_numpy(dtype=float), index=index)
    return out.astype(float)


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    safe_std = std.replace(0.0, np.nan)
    return (series - mean) / safe_std


def _row_ratio(mask: np.ndarray, available: np.ndarray) -> np.ndarray:
    counts = np.sum(available, axis=1)
    hits = np.sum(mask & available, axis=1)
    out = np.full(mask.shape[0], np.nan, dtype=float)
    valid = counts > 0
    out[valid] = hits[valid] / counts[valid]
    return out


@dataclass(slots=True)
class RegimeFeatureAvailability:
    trend_block: np.ndarray = field(default_factory=_empty_bool_array)
    risk_block: np.ndarray = field(default_factory=_empty_bool_array)
    breadth_block: np.ndarray = field(default_factory=_empty_bool_array)
    participation_block: np.ndarray = field(default_factory=_empty_bool_array)

    def block_mask(self, name: str) -> np.ndarray:
        key = str(name or "").strip().lower()
        if key == "trend_block":
            return self.trend_block
        if key == "risk_block":
            return self.risk_block
        if key == "breadth_block":
            return self.breadth_block
        if key == "participation_block":
            return self.participation_block
        return np.zeros(0, dtype=bool)


@dataclass(slots=True)
class FormalRegimeFeatureBundle:
    dates: np.ndarray
    benchmark_close: np.ndarray
    trend_long_ma: np.ndarray = field(default_factory=_empty_float_array)
    trend_long_ma_slope: np.ndarray = field(default_factory=_empty_float_array)
    trend_breakout_ratio: np.ndarray = field(default_factory=_empty_float_array)
    risk_realized_vol: np.ndarray = field(default_factory=_empty_float_array)
    risk_atr_ratio: np.ndarray = field(default_factory=_empty_float_array)
    risk_drawdown: np.ndarray = field(default_factory=_empty_float_array)
    breadth_above_ma_short_ratio: np.ndarray = field(default_factory=_empty_float_array)
    breadth_above_ma_long_ratio: np.ndarray = field(default_factory=_empty_float_array)
    breadth_new_high_ratio: np.ndarray = field(default_factory=_empty_float_array)
    breadth_new_low_ratio: np.ndarray = field(default_factory=_empty_float_array)
    participation_turnover_mean: np.ndarray = field(default_factory=_empty_float_array)
    participation_amount_mean: np.ndarray = field(default_factory=_empty_float_array)
    participation_amount_zscore: np.ndarray = field(default_factory=_empty_float_array)
    feature_availability: RegimeFeatureAvailability = field(default_factory=RegimeFeatureAvailability)


def resolve_required_regime_blocks(
    availability: RegimeFeatureAvailability,
    required_blocks: list[str] | tuple[str, ...] | None,
) -> np.ndarray:
    required = [str(name or "").strip().lower() for name in list(required_blocks or ()) if str(name or "").strip()]
    if not required:
        return np.ones(0, dtype=bool)
    masks = [availability.block_mask(name) for name in required]
    masks = [mask for mask in masks if mask.size > 0]
    if not masks:
        return np.zeros(0, dtype=bool)
    out = masks[0].copy()
    for mask in masks[1:]:
        out &= mask
    return out


def build_formal_regime_feature_bundle(
    *,
    benchmark: pd.DataFrame,
    history: pd.DataFrame,
    mx: OhlcMatrices,
    trading_days: list[Any],
    regime_engine_cfg: RegimeEngineConfig,
    membership_history: pd.DataFrame | None = None,
) -> FormalRegimeFeatureBundle:
    dates = pd.DatetimeIndex(pd.to_datetime([pd.Timestamp(d).normalize() for d in trading_days]))
    day_count = len(dates)

    bench = benchmark.copy()
    bench["date"] = pd.to_datetime(bench["date"]).dt.normalize()
    bench = bench.sort_values("date")
    bench_close = _safe_float_series(bench["close"], index=bench["date"]).reindex(dates)
    bench_high = _safe_float_series(bench.get("high", bench["close"]), index=bench["date"]).reindex(dates)
    bench_low = _safe_float_series(bench.get("low", bench["close"]), index=bench["date"]).reindex(dates)

    bundle = FormalRegimeFeatureBundle(
        dates=dates.to_numpy(),
        benchmark_close=bench_close.to_numpy(dtype=float),
    )

    trend_cfg = regime_engine_cfg.trend_block
    if trend_cfg.enabled:
        long_ma = bench_close.rolling(int(trend_cfg.long_ma_window), min_periods=int(trend_cfg.long_ma_window)).mean()
        prev_long_ma = long_ma.shift(int(trend_cfg.slope_window))
        safe_prev = prev_long_ma.where(prev_long_ma.abs() > 1e-12, np.nan)
        slope = (long_ma - prev_long_ma) / safe_prev
        breakout_base = bench_close.rolling(
            int(trend_cfg.breakout_lookback),
            min_periods=int(trend_cfg.breakout_lookback),
        ).max()
        breakout_ratio = bench_close / breakout_base.where(breakout_base.abs() > 1e-12, np.nan)
        bundle.trend_long_ma = long_ma.to_numpy(dtype=float)
        bundle.trend_long_ma_slope = slope.to_numpy(dtype=float)
        bundle.trend_breakout_ratio = breakout_ratio.to_numpy(dtype=float)
    else:
        bundle.trend_long_ma = np.full(day_count, np.nan, dtype=float)
        bundle.trend_long_ma_slope = np.full(day_count, np.nan, dtype=float)
        bundle.trend_breakout_ratio = np.full(day_count, np.nan, dtype=float)

    risk_cfg = regime_engine_cfg.risk_block
    if risk_cfg.enabled:
        ret = bench_close.pct_change()
        realized_vol = ret.rolling(
            int(risk_cfg.realized_vol_window),
            min_periods=int(risk_cfg.realized_vol_window),
        ).std(ddof=0)
        prev_close = bench_close.shift(1)
        tr = pd.concat(
            [
                (bench_high - bench_low).abs(),
                (bench_high - prev_close).abs(),
                (bench_low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(int(risk_cfg.atr_window), min_periods=int(risk_cfg.atr_window)).mean()
        atr_ratio = atr / bench_close.where(bench_close.abs() > 1e-12, np.nan)
        rolling_peak = bench_close.rolling(
            int(risk_cfg.drawdown_window),
            min_periods=int(risk_cfg.drawdown_window),
        ).max()
        drawdown = bench_close / rolling_peak.where(rolling_peak.abs() > 1e-12, np.nan) - 1.0
        bundle.risk_realized_vol = realized_vol.to_numpy(dtype=float)
        bundle.risk_atr_ratio = atr_ratio.to_numpy(dtype=float)
        bundle.risk_drawdown = drawdown.to_numpy(dtype=float)
    else:
        bundle.risk_realized_vol = np.full(day_count, np.nan, dtype=float)
        bundle.risk_atr_ratio = np.full(day_count, np.nan, dtype=float)
        bundle.risk_drawdown = np.full(day_count, np.nan, dtype=float)

    breadth_cfg = regime_engine_cfg.breadth_block
    breadth_available = False
    if breadth_cfg.enabled:
        can_use_strategy_universe = str(breadth_cfg.universe or "benchmark_constituents").strip().lower() == "strategy_universe"
        can_use_membership = membership_history is not None and not membership_history.empty
        if can_use_strategy_universe or can_use_membership:
            close_df = pd.DataFrame(mx.close, index=dates)
            valid_close = ~close_df.isna()
            ma_short = close_df.rolling(
                int(breadth_cfg.above_ma_short_window),
                min_periods=int(breadth_cfg.above_ma_short_window),
            ).mean()
            ma_long = close_df.rolling(
                int(breadth_cfg.above_ma_long_window),
                min_periods=int(breadth_cfg.above_ma_long_window),
            ).mean()
            rolling_high = close_df.rolling(
                int(breadth_cfg.new_high_low_window),
                min_periods=int(breadth_cfg.new_high_low_window),
            ).max()
            rolling_low = close_df.rolling(
                int(breadth_cfg.new_high_low_window),
                min_periods=int(breadth_cfg.new_high_low_window),
            ).min()
            above_short = _row_ratio((close_df.to_numpy(dtype=float) > ma_short.to_numpy(dtype=float)), valid_close.to_numpy(dtype=bool))
            above_long = _row_ratio((close_df.to_numpy(dtype=float) > ma_long.to_numpy(dtype=float)), valid_close.to_numpy(dtype=bool))
            new_high = _row_ratio((close_df.to_numpy(dtype=float) >= rolling_high.to_numpy(dtype=float)), valid_close.to_numpy(dtype=bool))
            new_low = _row_ratio((close_df.to_numpy(dtype=float) <= rolling_low.to_numpy(dtype=float)), valid_close.to_numpy(dtype=bool))
            bundle.breadth_above_ma_short_ratio = above_short
            bundle.breadth_above_ma_long_ratio = above_long
            bundle.breadth_new_high_ratio = new_high
            bundle.breadth_new_low_ratio = new_low
            breadth_available = True
        else:
            bundle.breadth_above_ma_short_ratio = np.full(day_count, np.nan, dtype=float)
            bundle.breadth_above_ma_long_ratio = np.full(day_count, np.nan, dtype=float)
            bundle.breadth_new_high_ratio = np.full(day_count, np.nan, dtype=float)
            bundle.breadth_new_low_ratio = np.full(day_count, np.nan, dtype=float)
    else:
        bundle.breadth_above_ma_short_ratio = np.full(day_count, np.nan, dtype=float)
        bundle.breadth_above_ma_long_ratio = np.full(day_count, np.nan, dtype=float)
        bundle.breadth_new_high_ratio = np.full(day_count, np.nan, dtype=float)
        bundle.breadth_new_low_ratio = np.full(day_count, np.nan, dtype=float)

    participation_cfg = regime_engine_cfg.participation_block
    if participation_cfg.enabled:
        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"]).dt.normalize()
        amount_values = None
        if "amount" in hist.columns:
            amount_values = pd.to_numeric(hist["amount"], errors="coerce")
        elif "turnover" in hist.columns:
            amount_values = pd.to_numeric(hist["turnover"], errors="coerce")
        elif {"close", "volume"}.issubset(hist.columns):
            amount_values = pd.to_numeric(hist["close"], errors="coerce") * pd.to_numeric(hist["volume"], errors="coerce")
        turnover_values = None
        if bool(participation_cfg.use_turnover_rate):
            if "turnover_rate_f" in hist.columns:
                turnover_values = pd.to_numeric(hist["turnover_rate_f"], errors="coerce")
            elif "turnover_rate" in hist.columns:
                turnover_values = pd.to_numeric(hist["turnover_rate"], errors="coerce")
        hist["_amount_value"] = amount_values if amount_values is not None else np.nan
        hist["_turnover_value"] = turnover_values if turnover_values is not None else np.nan
        daily_amount = hist.groupby("date", sort=True)["_amount_value"].sum(min_count=1).reindex(dates)
        daily_turnover = hist.groupby("date", sort=True)["_turnover_value"].mean().reindex(dates)
        amount_mean = daily_amount.rolling(
            int(participation_cfg.amount_window),
            min_periods=int(participation_cfg.amount_window),
        ).mean()
        turnover_mean = daily_turnover.rolling(
            int(participation_cfg.turnover_window),
            min_periods=int(participation_cfg.turnover_window),
        ).mean()
        bundle.participation_amount_mean = amount_mean.to_numpy(dtype=float)
        bundle.participation_turnover_mean = turnover_mean.to_numpy(dtype=float)
        bundle.participation_amount_zscore = _rolling_zscore(
            daily_amount,
            int(participation_cfg.amount_window),
        ).to_numpy(dtype=float)
    else:
        bundle.participation_amount_mean = np.full(day_count, np.nan, dtype=float)
        bundle.participation_turnover_mean = np.full(day_count, np.nan, dtype=float)
        bundle.participation_amount_zscore = np.full(day_count, np.nan, dtype=float)

    trend_available = np.zeros(day_count, dtype=bool)
    if trend_cfg.enabled:
        trend_available = (
            ~np.isnan(bundle.trend_long_ma)
            & ~np.isnan(bundle.trend_long_ma_slope)
            & ~np.isnan(bundle.trend_breakout_ratio)
        )
    risk_available = np.zeros(day_count, dtype=bool)
    if risk_cfg.enabled:
        risk_available = (
            ~np.isnan(bundle.risk_realized_vol)
            & ~np.isnan(bundle.risk_atr_ratio)
            & ~np.isnan(bundle.risk_drawdown)
        )
    breadth_available_mask = np.zeros(day_count, dtype=bool)
    if breadth_cfg.enabled and breadth_available:
        breadth_available_mask = (
            ~np.isnan(bundle.breadth_above_ma_short_ratio)
            & ~np.isnan(bundle.breadth_above_ma_long_ratio)
            & ~np.isnan(bundle.breadth_new_high_ratio)
            & ~np.isnan(bundle.breadth_new_low_ratio)
        )
    participation_available = np.zeros(day_count, dtype=bool)
    if participation_cfg.enabled:
        participation_available = (
            ~np.isnan(bundle.participation_turnover_mean)
            | ~np.isnan(bundle.participation_amount_mean)
        )

    bundle.feature_availability = RegimeFeatureAvailability(
        trend_block=trend_available.astype(bool),
        risk_block=risk_available.astype(bool),
        breadth_block=breadth_available_mask.astype(bool),
        participation_block=participation_available.astype(bool),
    )
    return bundle
