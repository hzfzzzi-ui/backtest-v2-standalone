"""Shared multifactor fast-gate helpers for generic runtime paths."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd


def build_multifactor_fast_gate(
    strategy: Any,
    hist: pd.DataFrame,
    trading_days: list[date],
) -> dict[str, Any] | None:
    try:
        enabled = bool((getattr(strategy, "state", {}) or {}).get("enable_multifactor_fast_gate", False))
    except Exception:
        enabled = False
    if not enabled:
        return None
    try:
        from backend.core.strategies.composite_strategy import CompositeStrategy
        from backend.core.strategies.sma_cross_regime_atr import SMACrossRegimeATRStrategy
        from backend.core.strategies.volume_breakout import VolumeBreakoutStrategy
        from backend.core.strategies.momentum_roc import MomentumROCStrategy
        from backend.core.strategies.relative_strength import RelativeStrengthStrategy
        from backend.core.strategies.bollinger_breakout import BollingerBreakoutStrategy
    except Exception:
        return None

    if not isinstance(strategy, CompositeStrategy):
        return None
    if str(getattr(strategy, "combine_mode", "")).upper() != "AND":
        return None
    sub = list(getattr(strategy, "strategies", []) or [])
    if len(sub) < 2:
        return None
    base = sub[0]
    if not isinstance(base, SMACrossRegimeATRStrategy):
        return None
    extra = sub[1:]
    for sub_strategy in extra:
        if isinstance(sub_strategy, MomentumROCStrategy) and bool(getattr(sub_strategy, "enable_roc_exit", False)):
            return None
        if isinstance(sub_strategy, BollingerBreakoutStrategy) and bool(getattr(sub_strategy, "enable_bb_mid_exit", False)):
            return None
        if not isinstance(
            sub_strategy,
            (VolumeBreakoutStrategy, MomentumROCStrategy, RelativeStrengthStrategy, BollingerBreakoutStrategy),
        ):
            return None

    data = hist[["date", "symbol", "close", "volume"]].copy()
    data["date"] = pd.to_datetime(data["date"])
    data["symbol"] = data["symbol"].astype(str).str.lower()
    data = data.sort_values(["symbol", "date"]).reset_index(drop=True)
    data["n"] = data.groupby("symbol").cumcount() + 1
    day_set = {pd.Timestamp(day).normalize() for day in trading_days}

    factor_sets: list[dict[pd.Timestamp, set[str]]] = []
    for sub_strategy in extra:
        factor_frame = data.copy()
        cond = pd.Series(False, index=factor_frame.index)
        if isinstance(sub_strategy, VolumeBreakoutStrategy):
            period = int(getattr(sub_strategy, "vol_ma_period", 20))
            mult = float(getattr(sub_strategy, "vol_mult", 1.5))
            min_days = int(getattr(sub_strategy, "min_data_days", 30))
            factor_frame["vol_ma"] = factor_frame.groupby("symbol")["volume"].transform(
                lambda values: values.rolling(period, min_periods=period).mean()
            )
            cond = (factor_frame["n"] >= min_days) & (factor_frame["volume"] > (factor_frame["vol_ma"] * mult))
        elif isinstance(sub_strategy, MomentumROCStrategy):
            period = int(getattr(sub_strategy, "roc_period", 20))
            threshold = float(getattr(sub_strategy, "roc_threshold", 0.0))
            min_days = int(getattr(sub_strategy, "min_data_days", 30))
            prev = factor_frame.groupby("symbol")["close"].shift(period)
            roc = (factor_frame["close"] - prev) / prev
            cond = (factor_frame["n"] >= min_days) & roc.notna() & (roc >= threshold)
        elif isinstance(sub_strategy, RelativeStrengthStrategy):
            period = int(getattr(sub_strategy, "rs_period", 60))
            threshold = float(getattr(sub_strategy, "rs_threshold", 0.7))
            min_days = int(getattr(sub_strategy, "min_data_days", 70))
            prev = factor_frame.groupby("symbol")["close"].shift(period)
            ret = (factor_frame["close"] - prev) / prev
            factor_frame["ret"] = ret
            valid = (factor_frame["n"] >= min_days) & factor_frame["ret"].notna()
            rank = factor_frame[valid].groupby("date")["ret"].rank(method="average", pct=True)
            cond = pd.Series(False, index=factor_frame.index)
            cond.loc[valid[valid].index] = (rank >= threshold).values
        elif isinstance(sub_strategy, BollingerBreakoutStrategy):
            period = int(getattr(sub_strategy, "bb_period", 20))
            std_mult = float(getattr(sub_strategy, "bb_std_mult", 2.0))
            min_days = int(getattr(sub_strategy, "min_data_days", 30))
            mid = factor_frame.groupby("symbol")["close"].transform(
                lambda values: values.rolling(period, min_periods=period).mean()
            )
            std = factor_frame.groupby("symbol")["close"].transform(
                lambda values: values.rolling(period, min_periods=period).std()
            )
            upper = mid + std_mult * std
            cond = (factor_frame["n"] >= min_days) & upper.notna() & (factor_frame["close"] > upper)

        pass_frame = factor_frame.loc[cond, ["date", "symbol"]].copy()
        pass_frame["date"] = pd.to_datetime(pass_frame["date"]).dt.normalize()
        pass_frame = pass_frame[pass_frame["date"].isin(day_set)]
        by_day: dict[pd.Timestamp, set[str]] = {}
        if not pass_frame.empty:
            for day, group in pass_frame.groupby("date", sort=False):
                by_day[pd.Timestamp(day)] = set(group["symbol"].astype(str).tolist())
        factor_sets.append(by_day)

    return {"base": base, "factor_sets": factor_sets}
