"""SMA 策略信号提供者。

封装 SMA/EMA 路径的矩阵预计算和逐日信号生成逻辑。
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import ExitConfig
from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.candidate_index import build_daily_candidate_index
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.features import compute_feature_matrices
from backend.core.engine_vector.signal_matrix import build_signal_matrices
from backend.core.engine_vector.signal_provider import (
    DayContext,
    DaySignals,
    ExitCounts,
)
from backend.core.portfolio.portfolio_builder import (
    calc_buy_slots,
    resolve_mf_gate_on_today,
)


# ---------------------------------------------------------------------------
# 多因子排名辅助函数
# ---------------------------------------------------------------------------

def _cross_rank_pct(values: dict[str, float | None]) -> dict[str, float]:
    valid = [(k, float(v)) for k, v in values.items() if v is not None and not np.isnan(float(v))]
    out: dict[str, float] = {str(k): 0.0 for k in values.keys()}
    if len(valid) <= 1:
        for k, _ in valid:
            out[str(k)] = 0.5
        return out
    valid_sorted = sorted(valid, key=lambda kv: kv[1])
    denom = max(len(valid_sorted) - 1, 1)
    for idx, (k, _v) in enumerate(valid_sorted):
        out[str(k)] = float(idx) / float(denom)
    return out


def _build_daily_multifactor_scores(
    *,
    i: int,
    day_cands: np.ndarray,
    symbols: list[str],
    close: np.ndarray,
    amt_matrix: np.ndarray,
    bench_close: np.ndarray,
) -> dict[str, float]:
    if int(len(day_cands)) < 5:
        return {str(symbols[int(c)]): 0.5 for c in day_cands}
    vol_raw: dict[str, float | None] = {}
    roc20_raw: dict[str, float | None] = {}
    rs60_raw: dict[str, float | None] = {}
    bb_raw: dict[str, float | None] = {}
    bench_now = float(bench_close[i]) if i < len(bench_close) and not np.isnan(bench_close[i]) else np.nan
    bench_60 = float(bench_close[i - 60]) if i - 60 >= 0 and not np.isnan(bench_close[i - 60]) else np.nan
    bench_roc60 = None
    if not np.isnan(bench_now) and not np.isnan(bench_60) and bench_60 > 0:
        bench_roc60 = float(bench_now / bench_60 - 1.0)
    for c in day_cands:
        col = int(c)
        sym = str(symbols[col])
        amt = amt_matrix[:, col]
        if i >= 19:
            w = amt[i - 19 : i + 1]
            w = w[~np.isnan(w)]
            if len(w) >= 20:
                mu = float(np.mean(w))
                sd = float(np.std(w))
                v = float(amt[i]) if not np.isnan(amt[i]) else np.nan
                vol_raw[sym] = ((v - mu) / sd) if (sd > 0 and not np.isnan(v)) else None
            else:
                vol_raw[sym] = None
        else:
            vol_raw[sym] = None
        c_now = float(close[i, col]) if not np.isnan(close[i, col]) else np.nan
        c_20 = float(close[i - 20, col]) if i - 20 >= 0 and not np.isnan(close[i - 20, col]) else np.nan
        roc20_raw[sym] = (c_now / c_20 - 1.0) if (not np.isnan(c_now) and not np.isnan(c_20) and c_20 > 0) else None
        c_60 = float(close[i - 60, col]) if i - 60 >= 0 and not np.isnan(close[i - 60, col]) else np.nan
        if not np.isnan(c_now) and not np.isnan(c_60) and c_60 > 0 and bench_roc60 is not None:
            rs60_raw[sym] = float(c_now / c_60 - 1.0) - float(bench_roc60)
        else:
            rs60_raw[sym] = None
        if i >= 19:
            cw = close[i - 19 : i + 1, col]
            cw = cw[~np.isnan(cw)]
            if len(cw) >= 20:
                mid = float(np.mean(cw))
                sd = float(np.std(cw))
                up = mid + 2.0 * sd
                dn = mid - 2.0 * sd
                span = float(up - dn)
                bb_raw[sym] = float((c_now - mid) / span) if (span > 0 and not np.isnan(c_now)) else None
            else:
                bb_raw[sym] = None
        else:
            bb_raw[sym] = None
    r_vol = _cross_rank_pct(vol_raw)
    r_roc = _cross_rank_pct(roc20_raw)
    r_rs = _cross_rank_pct(rs60_raw)
    r_bb = _cross_rank_pct(bb_raw)
    scores: dict[str, float] = {}
    for c in day_cands:
        sym = str(symbols[int(c)])
        scores[sym] = float(0.25 * r_vol.get(sym, 0.0) + 0.25 * r_roc.get(sym, 0.0) + 0.25 * r_rs.get(sym, 0.0) + 0.25 * r_bb.get(sym, 0.0))
    return scores


# ---------------------------------------------------------------------------
# SMASignalProvider
# ---------------------------------------------------------------------------

class SMASignalProvider:
    """SMA/EMA 策略的信号提供者。"""

    def __init__(self) -> None:
        # fill hooks（统一循环传给 _process_pending_fills）
        self.extra_clear_dicts: list[dict] = []
        self.last_sell_day: dict[str, date] | None = None
        self.entry_day: dict[str, date] = {}
        self.entry_day_overwrite: bool = True
        self.peak_state_on_buy: dict[str, float] | None = None

        # 内部状态（precompute 后填充）
        self._mx: Any = None
        self._feats: Any = None
        self._sig_m: dict[str, np.ndarray] = {}
        self._cand_idx: Any = None
        self._strength: np.ndarray = np.array([])
        self._bench_close: np.ndarray = np.array([])
        self._risk_on: np.ndarray = np.array([])
        self._strong_risk_on: np.ndarray = np.array([])
        self._sym_to_col: dict[str, int] = {}
        self._ec: ExitConfig = ExitConfig()
        self._peak_close_state: dict[str, float] = {}
        self._raw_peak_state: dict[str, float] = {}
        self._break_streak_state: dict[str, int] = {}
        self._enable_multifactor_rank: bool = False
        self._mf_rank_gate_mode: str = "ALWAYS_ON"
        self._collect_debug: bool = False

        # strategy 参数（precompute 后填充）
        self._fast: int = 5
        self._slow: int = 20
        self._enable_trend_filter: bool = False
        self._enable_trend_tier: bool = True
        self._enable_trend_accel: bool = True
        self._enable_trend_break_exit: bool = True
        self._trend_break_confirm_days: int = 3
        self._trend_break_confirm_gap_pct: float = 0.0
        self._trend_break_use_benchmark_regime: bool = False
        self._weak_trend_order_scale: float = 0.5
        self._strong_trend_order_scale: float = 1.0
        self._enable_atr_stop: bool = False
        self._enable_atr_trail: bool = False
        self._atr_stop_k: float = 2.0
        self._atr_trail_k: float = 3.0
        self._order_size: int = 1000
        self._ma_type: str = "SMA"
        self._cross_up_code: str = "SMA_CROSS_UP"
        self._cross_down_code: str = "SMA_CROSS_DOWN"
        self._enable_entry_above_slow_ma: bool = False
        self._enable_entry_slow_ma_slope: bool = False
        self._max_hold_days: int = 0
        self._min_hold_days: int = 0
        self._cooldown_days: int = 0
        self._min_hold_exempt_set: set[str] = set()
        self._base_order_value: float = 0.0

        # 累計计数器
        self.blocked_by_trend_count: int = 0
        self.total_buy_signals: int = 0
        self.trend_slope_block_count: int = 0
        self.trend_continuity_block_count: int = 0
        self.entry_above_slow_ma_block_count: int = 0
        self.entry_slope_block_count: int = 0
        self.min_hold_block_count: int = 0
        self.cooldown_block_count: int = 0
        self.atr_trail_update_count: int = 0
        self.atr_stop_exit_count: int = 0
        self.atr_trail_exit_count: int = 0
        self.take_profit_exit_count: int = 0
        self.fixed_stop_loss_exit_count: int = 0
        self.scan_all_symbols_count: int = 0
        self.cand_index_access_count: int = 0
        self.diag_reason_counts: dict[str, int] = {}
        self.precompute_seconds: float = 0.0

    # ------------------------------------------------------------------
    # precompute
    # ------------------------------------------------------------------

    def precompute(
        self,
        *,
        history: pd.DataFrame,
        benchmark: pd.DataFrame,
        raw_history: pd.DataFrame | None,
        trading_days: list[date],
        strategy: Any,
        **kwargs: Any,
    ) -> None:
        import time as _time

        exit_cfg = kwargs.get("exit_cfg") or ExitConfig()
        self._enable_multifactor_rank = bool(kwargs.get("enable_multifactor_rank", False))
        self._mf_rank_gate_mode = str(kwargs.get("mf_rank_gate_mode") or "ALWAYS_ON")
        st_history = kwargs.get("st_history")
        strength_ma = int(kwargs.get("strength_ma", 120))
        self._base_order_value = float(kwargs.get("base_order_value", 0.0))

        self._ec = exit_cfg
        pre_t0 = _time.perf_counter()

        # -- strategy 参数提取 --
        self._fast = int(getattr(strategy, "fast", 5))
        self._slow = int(getattr(strategy, "slow", 20))
        trend_fast = int(getattr(strategy, "trend_fast_ma", 120))
        trend_slow = int(getattr(strategy, "trend_slow_ma", 200))
        enable_trend_slope_filter = bool(getattr(strategy, "enable_trend_slope_filter", False))
        slope_lookback = int(getattr(strategy, "slope_lookback", 5))
        enable_trend_continuity_filter = bool(getattr(strategy, "enable_trend_continuity_filter", False))
        continuity_n = int(getattr(strategy, "continuity_n", 10))
        atr_n = int(getattr(strategy, "atr_n", 14))
        entry_buffer = float(getattr(strategy, "entry_buffer", 0.0))
        self._enable_trend_filter = bool(getattr(strategy, "enable_trend_filter", False))
        self._enable_trend_tier = bool(getattr(strategy, "enable_trend_tier", True))
        self._enable_trend_accel = bool(getattr(strategy, "enable_trend_accel", True))
        self._enable_trend_break_exit = bool(getattr(strategy, "enable_trend_break_exit", True))
        self._trend_break_confirm_days = int(getattr(strategy, "trend_break_confirm_days", 3))
        self._trend_break_confirm_gap_pct = float(getattr(strategy, "trend_break_confirm_gap_pct", 0.0))
        self._trend_break_use_benchmark_regime = bool(getattr(strategy, "trend_break_use_benchmark_regime", False))
        self._weak_trend_order_scale = float(getattr(strategy, "weak_trend_order_scale", 0.5))
        self._strong_trend_order_scale = float(getattr(strategy, "strong_trend_order_scale", 1.0))
        self._enable_atr_stop = bool(getattr(strategy, "enable_atr_stop", False))
        self._enable_atr_trail = bool(getattr(strategy, "enable_atr_trail", False))
        self._atr_stop_k = float(kwargs.get("atr_stop_k", getattr(strategy, "atr_stop_k", 2.0)))
        self._atr_trail_k = float(getattr(strategy, "atr_trail_k", 3.0))
        self._order_size = int(getattr(strategy, "order_size", 1000))
        regime_ma = int(getattr(strategy, "regime_ma", 120))
        self._ma_type = str(getattr(strategy, "ma_type", "SMA")).upper()
        self._cross_up_code = f"{self._ma_type}_CROSS_UP"
        self._cross_down_code = f"{self._ma_type}_CROSS_DOWN"
        self._enable_entry_above_slow_ma = bool(getattr(strategy, "enable_entry_above_slow_ma", False))
        self._enable_entry_slow_ma_slope = bool(getattr(strategy, "enable_entry_slow_ma_slope", False))
        entry_slope_lookback = int(getattr(strategy, "entry_slope_lookback", 5))
        self._max_hold_days = int(getattr(strategy, "max_hold_days", 0))
        self._min_hold_days = int(getattr(strategy, "min_hold_days", 0))
        self._cooldown_days = int(getattr(strategy, "cooldown_days", 0))
        self._min_hold_exempt_set = set(getattr(strategy, "min_hold_exempt_reasons", []) or [])

        # -- OHLC + feature + signal 矩阵 --
        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"])
        hist["symbol"] = hist["symbol"].astype(str).str.lower()
        hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

        self._mx = build_ohlc_matrices_from_history(hist, trading_days, st_history=st_history)
        mx = self._mx
        t, n = mx.close.shape
        if n == 0:
            raise ValueError("history has no symbols")

        self._feats = compute_feature_matrices(
            close=mx.close, high=mx.high, low=mx.low,
            fast=self._fast, slow=self._slow,
            trend_fast=trend_fast, trend_slow=trend_slow,
            atr_n=atr_n, strength_ma=strength_ma, ma_type=self._ma_type,
        )
        feats = self._feats
        self._strength = mx.close / feats.strength_ma - 1.0
        self._strength[np.isnan(feats.strength_ma)] = np.nan

        # -- benchmark 数组 --
        bench = benchmark.copy()
        bench["date"] = pd.to_datetime(bench["date"])
        bench = bench.sort_values("date")
        bench_close_s = pd.to_numeric(bench["close"], errors="coerce")
        bench_ma_s = bench_close_s.rolling(regime_ma, min_periods=regime_ma).mean()
        bmap_close = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_close_s)}
        bmap_ma = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma_s)}
        self._bench_close = np.array([bmap_close.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        bench_ma = np.array([bmap_ma.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        self._risk_on = np.ones(t, dtype=bool)
        valid_bench = ~np.isnan(self._bench_close) & ~np.isnan(bench_ma)
        self._risk_on[valid_bench] = self._bench_close[valid_bench] > bench_ma[valid_bench]

        bench_ma120_s = bench_close_s.rolling(120, min_periods=120).mean()
        bench_ma200_s = bench_close_s.rolling(200, min_periods=200).mean()
        bmap_ma120 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma120_s)}
        bmap_ma200 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma200_s)}
        bench_ma120 = np.array([bmap_ma120.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        bench_ma200 = np.array([bmap_ma200.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        self._strong_risk_on = np.zeros(t, dtype=bool)
        valid_strong = ~np.isnan(bench_ma120) & ~np.isnan(bench_ma200)
        self._strong_risk_on[valid_strong] = bench_ma120[valid_strong] > bench_ma200[valid_strong]

        # -- 信号矩阵 + 候选索引 --
        self._sig_m = build_signal_matrices(
            close=mx.close, fast_ma=feats.fast_ma, slow_ma=feats.slow_ma,
            trend_fast_ma=feats.trend_fast_ma, trend_slow_ma=feats.trend_slow_ma,
            tradable=mx.tradable, entry_buffer=entry_buffer,
            enable_trend_filter=self._enable_trend_filter,
            enable_trend_tier=self._enable_trend_tier,
            enable_trend_slope_filter=enable_trend_slope_filter,
            slope_lookback=slope_lookback,
            enable_trend_continuity_filter=enable_trend_continuity_filter,
            continuity_n=continuity_n,
            risk_on=self._risk_on,
            enable_entry_above_slow_ma=self._enable_entry_above_slow_ma,
            enable_entry_slow_ma_slope=self._enable_entry_slow_ma_slope,
            entry_slope_lookback=entry_slope_lookback,
        )
        self._cand_idx = build_daily_candidate_index(self._sig_m["buy_base"])
        self._sym_to_col = {s: idx for idx, s in enumerate(mx.symbols)}
        self._amt_matrix = mx.close * mx.volume
        self.precompute_seconds = float(_time.perf_counter() - pre_t0)

        # -- fill hooks 初始化 --
        self._peak_close_state = {}
        self._raw_peak_state = {}
        self._break_streak_state = {}
        self.entry_day = {}
        self.last_sell_day = {}
        self.extra_clear_dicts = [self._peak_close_state, self._raw_peak_state, self._break_streak_state]
        self.peak_state_on_buy = self._peak_close_state

        # -- extra daily_row init（统一循环用于最后一天 DR 初始化） --
        self.extra_daily_init: dict[str, Any] = {
            "trend_slope_block_count": 0,
            "trend_continuity_block_count": 0,
            "base_trend_on_rate": 0.0,
            "quality_trend_on_rate": 0.0,
        }

    # ------------------------------------------------------------------
    # day_signals
    # ------------------------------------------------------------------

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        i = day_idx
        mx = self._mx
        feats = self._feats
        sig_m = self._sig_m
        positions = ctx.positions
        position_avg_cost = ctx.position_avg_cost
        close_idx = ctx.close_idx
        nav = ctx.nav
        max_positions = ctx.max_positions
        base_order_value = ctx.base_order_value
        n = mx.close.shape[1]

        # ── 行切片预提取（消除候选循环中重复 dict lookup + 2D 索引） ──
        _cross_up = sig_m["cross_up"][i, :]
        _cross_down = sig_m["cross_down"][i, :]
        _buffer_ok = sig_m["buffer_ok"][i, :]
        _trend_ok = sig_m["trend_ok"][i, :]
        _risk_on_m = sig_m["risk_on_matrix"][i, :]
        _ma_valid = sig_m["ma_is_valid"][i, :]
        _base_trend_on = sig_m["base_trend_on"][i, :]
        _slope_pass = sig_m["slope_pass"][i, :]
        _continuity_pass = sig_m["continuity_pass"][i, :]
        _quality_trend_on = sig_m["quality_trend_on"][i, :]
        _entry_above_slow = sig_m["entry_above_slow_ma"][i, :]
        _entry_slope_pos = sig_m["entry_slow_ma_slope_pos"][i, :]
        _close_row = mx.close[i, :]
        _tradable_row = mx.tradable[i, :]
        _tfast_row = feats.trend_fast_ma[i, :]
        _tslow_row = feats.trend_slow_ma[i, :]
        _slow_ma_row = feats.slow_ma[i, :]
        _fast_ma_row = feats.fast_ma[i, :]
        _atr_row = feats.atr14[i, :]
        _strength_row = self._strength[i, :]

        # ── 卖出信号 ──
        sell_sigs: list[Signal] = []
        exit_syms: set[str] = set()
        exit_counts = ExitCounts()
        positions_before_sell = int(sum(1 for _q in positions.values() if int(_q) > 0))
        held_syms = [s for s, q in positions.items() if int(q) > 0]
        held_cols = [self._sym_to_col[s] for s in held_syms if s in self._sym_to_col]

        for c in held_cols:
            sym = mx.symbols[c]
            qty = int(positions.get(sym, 0))
            if qty <= 0:
                continue
            cclose = float(_close_row[c]) if not np.isnan(_close_row[c]) else np.nan
            _raw_close_v = float(close_idx.get((day, sym), 0.0))
            old_peak = float(self._peak_close_state.get(sym, cclose))
            new_peak = max(old_peak, cclose)
            self._peak_close_state[sym] = new_peak
            _raw_old_peak = float(self._raw_peak_state.get(sym, _raw_close_v))
            _raw_new_peak = max(_raw_old_peak, _raw_close_v)
            self._raw_peak_state[sym] = _raw_new_peak
            if self._enable_atr_trail and new_peak > old_peak:
                self.atr_trail_update_count += 1
            atr_v = float(_atr_row[c]) if not np.isnan(_atr_row[c]) else None
            _raw_atr: float | None = None
            if atr_v is not None and cclose > 0 and _raw_close_v > 0:
                _raw_atr = atr_v * (_raw_close_v / cclose)
            trend_fast_v = float(_tfast_row[c]) if not np.isnan(_tfast_row[c]) else None
            trend_slow_v = float(_tslow_row[c]) if not np.isnan(_tslow_row[c]) else None
            strong_trend = bool(trend_fast_v is not None and trend_slow_v is not None and trend_fast_v > trend_slow_v)
            trend_tier = "STRONG" if strong_trend else "WEAK"
            break_t = not strong_trend
            if break_t:
                self._break_streak_state[sym] = int(self._break_streak_state.get(sym, 0)) + 1
            else:
                self._break_streak_state[sym] = 0
            break_streak = int(self._break_streak_state.get(sym, 0))
            gap_ok = True
            if float(self._trend_break_confirm_gap_pct) > 0:
                if trend_slow_v is None or trend_slow_v == 0 or trend_fast_v is None:
                    gap_ok = False
                else:
                    gap_ok = ((trend_slow_v - trend_fast_v) / trend_slow_v) >= float(self._trend_break_confirm_gap_pct)
            regime_gate_ok = True
            if bool(self._trend_break_use_benchmark_regime):
                regime_gate_ok = bool(self._risk_on[i])
            confirmed_break = (
                bool(self._enable_trend_break_exit)
                and break_t
                and break_streak >= int(max(1, self._trend_break_confirm_days))
                and gap_ok
                and regime_gate_ok
            )
            reason = ""
            _avg_cost = float(position_avg_cost.get(sym, 0.0))
            if not bool(self._risk_on[i]):
                reason = "RISK_OFF_EXIT"
            elif self._enable_atr_stop and _raw_atr is not None and _raw_close_v <= float(_avg_cost - self._atr_stop_k * _raw_atr):
                reason = "ATR_STOP_LOSS"
                self.atr_stop_exit_count += 1
                exit_counts.atr_stop += 1
            elif self._ec.enable_fixed_stop_loss and _avg_cost > 0 and _raw_close_v <= _avg_cost * (1.0 - self._ec.fixed_stop_loss_pct):
                reason = "FIXED_STOP_LOSS"
                self.fixed_stop_loss_exit_count += 1
                exit_counts.fixed_stop_loss += 1
            elif confirmed_break:
                reason = "TREND_BREAK_EXIT"
            elif self._ec.enable_take_profit and _avg_cost > 0 and (
                (self._ec.take_profit_mode == "pct" and _raw_close_v >= _avg_cost * (1.0 + self._ec.take_profit_pct))
                or (self._ec.take_profit_mode == "atr" and _raw_atr is not None and _raw_close_v >= _avg_cost + self._ec.take_profit_atr_k * _raw_atr)
            ):
                reason = "TAKE_PROFIT"
                self.take_profit_exit_count += 1
                exit_counts.take_profit += 1
            elif self._enable_atr_trail and _raw_atr is not None and _raw_close_v <= float(self._raw_peak_state.get(sym, _raw_close_v) - self._atr_trail_k * _raw_atr):
                reason = "ATR_TRAIL_EXIT"
                self.atr_trail_exit_count += 1
                exit_counts.atr_trail += 1
            elif self._max_hold_days > 0 and sym in self.entry_day and (day - self.entry_day[sym]).days >= self._max_hold_days:
                reason = "TIME_EXIT"
            elif bool(_cross_down[c]):
                reason = self._cross_down_code

            if reason:
                if self._min_hold_days > 0 and reason not in self._min_hold_exempt_set:
                    _held_days = (day - self.entry_day[sym]).days if sym in self.entry_day else 0
                    if _held_days < self._min_hold_days:
                        self.min_hold_block_count += 1
                        continue
                exit_syms.add(sym)
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason=reason, reason_code=reason,
                    meta={
                        "close": cclose,
                        "atr_last": atr_v,
                        "entry_price": _avg_cost,
                        "peak_close": float(self._peak_close_state.get(sym, cclose)),
                        "stop_price": None if atr_v is None else float(_avg_cost - self._atr_stop_k * atr_v),
                        "trail_price": None if atr_v is None else float(self._peak_close_state.get(sym, cclose) - self._atr_trail_k * atr_v),
                        "atr_stop_k": float(self._atr_stop_k),
                        "atr_trail_k": float(self._atr_trail_k),
                        "ma120": trend_fast_v,
                        "ma200": trend_slow_v,
                        "trend_tier_at_exit": trend_tier,
                        "strong_trend_at_exit": bool(strong_trend),
                        "break_streak": int(break_streak),
                        "trend_break_confirm_days": int(max(1, self._trend_break_confirm_days)),
                        "trend_break_confirm_gap_pct": float(self._trend_break_confirm_gap_pct),
                        "triggered_rule": ("CONFIRMED_TREND_BREAK_EXIT" if reason == "TREND_BREAK_EXIT" else reason),
                    },
                ))

        # ── 买入信号 ──
        self.cand_index_access_count += 1
        day_cands = self._cand_idx[i]
        buy_sigs: list[Signal] = []
        self.total_buy_signals += int(len(day_cands))
        raw_buy_mask = _cross_up & _buffer_ok & _trend_ok & _risk_on_m & _ma_valid
        if self._enable_entry_above_slow_ma:
            _above_blocked = int(np.sum(raw_buy_mask & ~_entry_above_slow))
            self.entry_above_slow_ma_block_count += _above_blocked
            raw_buy_mask = raw_buy_mask & _entry_above_slow
        else:
            _above_blocked = 0
        if self._enable_entry_slow_ma_slope:
            _slope_blocked = int(np.sum(raw_buy_mask & ~_entry_slope_pos))
            self.entry_slope_block_count += _slope_blocked
            raw_buy_mask = raw_buy_mask & _entry_slope_pos
        else:
            _slope_blocked = 0
        raw_buy_signal_count = int(np.sum(raw_buy_mask))
        buy_candidate_mask = raw_buy_mask & _tradable_row
        buy_candidate_count = int(np.sum(buy_candidate_mask))
        after_held_filter_count = 0
        day_gate_by_symbol: dict[str, dict[str, Any]] = {}

        _collect_debug = self._collect_debug
        for c in day_cands:
            sym = mx.symbols[int(c)]
            if sym in positions and int(positions[sym]) > 0:
                continue
            if self._cooldown_days > 0 and sym in self.last_sell_day:
                if (day - self.last_sell_day[sym]).days < self._cooldown_days:
                    self.cooldown_block_count += 1
                    continue
            if self._enable_entry_above_slow_ma and not bool(_entry_above_slow[c]):
                continue
            if self._enable_entry_slow_ma_slope and not bool(_entry_slope_pos[c]):
                continue
            after_held_filter_count += 1
            trend_fast_v = None if np.isnan(_tfast_row[c]) else float(_tfast_row[c])
            trend_slow_v = None if np.isnan(_tslow_row[c]) else float(_tslow_row[c])
            strong_trend = bool(trend_fast_v is not None and trend_slow_v is not None and trend_fast_v > trend_slow_v)
            if bool(self._enable_trend_accel):
                order_value_scale = float(self._strong_trend_order_scale if strong_trend else self._weak_trend_order_scale)
            else:
                order_value_scale = 1.0
            trend_tier = "STRONG" if strong_trend else "WEAK"
            if _collect_debug:
                day_gate_by_symbol[sym] = {
                    "cross_up": bool(_cross_up[c]),
                    "entry_buffer_ok": bool(_buffer_ok[c]),
                    "trend_ok": bool(_trend_ok[c]),
                    "base_trend_on": bool(_base_trend_on[c]),
                    "slope_pass": bool(_slope_pass[c]),
                    "continuity_pass": bool(_continuity_pass[c]),
                    "final_trend_on": bool(_quality_trend_on[c]),
                    "regime_ok": bool(_risk_on_m[c]),
                    "tradable": bool(_tradable_row[c]),
                    "ma_is_valid": bool(_ma_valid[c]),
                    "close": None if np.isnan(_close_row[c]) else float(_close_row[c]),
                    "open_next": None if np.isnan(mx.open[i + 1, c]) else float(mx.open[i + 1, c]),
                    "slow_ma": None if np.isnan(_slow_ma_row[c]) else float(_slow_ma_row[c]),
                    "fast_ma": None if np.isnan(_fast_ma_row[c]) else float(_fast_ma_row[c]),
                    "fast_ma_prev": None if (i <= 0 or np.isnan(feats.fast_ma[i - 1, c])) else float(feats.fast_ma[i - 1, c]),
                    "slow_ma_prev": None if (i <= 0 or np.isnan(feats.slow_ma[i - 1, c])) else float(feats.slow_ma[i - 1, c]),
                    "ma120": trend_fast_v,
                    "ma200": trend_slow_v,
                    "trend_fast": trend_fast_v,
                    "trend_slow": trend_slow_v,
                    "buy_raw_ok": True,
                    "entry_above_slow_ma": bool(_entry_above_slow[c]),
                    "slow_ma_slope_pos": bool(_entry_slope_pos[c]),
                    "strength_value": None if np.isnan(_strength_row[c]) else float(_strength_row[c]),
                    "strong_trend": bool(strong_trend),
                    "trend_tier": trend_tier,
                    "order_value_scale": float(order_value_scale),
                }
            eff_bov = float(base_order_value) if float(base_order_value) > 0 else (float(nav) / float(max_positions) if int(max_positions) > 0 else 0.0)
            _c_close = None if np.isnan(_close_row[c]) else float(_close_row[c])
            buy_sigs.append(Signal(
                signal_date=day, symbol=sym, side=Side.BUY, qty=self._order_size,
                reason=self._cross_up_code, reason_code=self._cross_up_code,
                meta={
                    "close": _c_close,
                    "slow_ma": None if np.isnan(_slow_ma_row[c]) else float(_slow_ma_row[c]),
                    "atr_last": None if np.isnan(_atr_row[c]) else float(_atr_row[c]),
                    "trend_ok": bool(_trend_ok[c]),
                    "base_trend_on": bool(_base_trend_on[c]),
                    "slope_pass": bool(_slope_pass[c]),
                    "continuity_pass": bool(_continuity_pass[c]),
                    "final_trend_on": bool(_quality_trend_on[c]),
                    "regime_on": bool(self._risk_on[i]),
                    "entry_above_slow_ma": bool(_entry_above_slow[c]),
                    "slow_ma_slope_pos": bool(_entry_slope_pos[c]),
                    "strong_trend": bool(strong_trend),
                    "trend_tier": trend_tier,
                    "order_value_scale": float(order_value_scale),
                    "order_value_raw": eff_bov,
                    "order_value_final": eff_bov * float(order_value_scale),
                },
            ))

        # ── blocked trend/risk/buffer counts ──
        if self._enable_trend_filter and (not self._enable_trend_tier):
            self.blocked_by_trend_count += int(np.sum(_cross_up & (~_trend_ok) & _risk_on_m))
        quality_base = _cross_up & _buffer_ok & _risk_on_m & _base_trend_on
        slope_block_today = int(np.sum(quality_base & (~_slope_pass)))
        continuity_block_today = int(np.sum(quality_base & _slope_pass & (~_continuity_pass)))
        self.trend_slope_block_count += int(slope_block_today)
        self.trend_continuity_block_count += int(continuity_block_today)
        self.diag_reason_counts["BLOCK_TRADABLE_FALSE"] = int(self.diag_reason_counts.get("BLOCK_TRADABLE_FALSE", 0)) + max(raw_buy_signal_count - buy_candidate_count, 0)
        self.diag_reason_counts["BLOCK_HELD_ALREADY"] = int(self.diag_reason_counts.get("BLOCK_HELD_ALREADY", 0)) + max(buy_candidate_count - after_held_filter_count, 0)
        self.diag_reason_counts["BLOCK_CROSS_NOT_MET"] = int(self.diag_reason_counts.get("BLOCK_CROSS_NOT_MET", 0)) + int(np.sum(_ma_valid & (~_cross_up)))
        self.diag_reason_counts["BLOCK_ENTRY_BUFFER"] = int(self.diag_reason_counts.get("BLOCK_ENTRY_BUFFER", 0)) + int(np.sum(_cross_up & (~_buffer_ok)))
        self.diag_reason_counts["BLOCK_TREND"] = int(self.diag_reason_counts.get("BLOCK_TREND", 0)) + int(np.sum(_cross_up & _buffer_ok & (~_trend_ok)))
        self.diag_reason_counts["BLOCK_REGIME_OFF"] = int(self.diag_reason_counts.get("BLOCK_REGIME_OFF", 0)) + int(np.sum(_cross_up & _buffer_ok & _trend_ok & (~_risk_on_m)))
        if self._enable_entry_above_slow_ma:
            self.diag_reason_counts["BLOCK_ENTRY_BELOW_SLOW_MA"] = int(self.diag_reason_counts.get("BLOCK_ENTRY_BELOW_SLOW_MA", 0)) + _above_blocked
        if self._enable_entry_slow_ma_slope:
            self.diag_reason_counts["BLOCK_ENTRY_SLOW_MA_SLOPE"] = int(self.diag_reason_counts.get("BLOCK_ENTRY_SLOW_MA_SLOPE", 0)) + _slope_blocked

        # ── strength / mf scores ──
        strength_map: dict[str, float] = {mx.symbols[c]: (None if np.isnan(_strength_row[c]) else float(_strength_row[c])) for c in day_cands}
        mf_score_map = _build_daily_multifactor_scores(
            i=i, day_cands=day_cands, symbols=mx.symbols,
            close=mx.close, amt_matrix=self._amt_matrix, bench_close=self._bench_close,
        ) if self._enable_multifactor_rank else {}

        # ── mf_gate / strong_risk_on ──
        mf_gate_on_today = resolve_mf_gate_on_today(
            enable_multifactor_rank=self._enable_multifactor_rank,
            mf_rank_gate_mode=self._mf_rank_gate_mode,
            risk_on_today=bool(self._risk_on[i]),
            strong_risk_on_today=bool(self._strong_risk_on[i]),
        )

        diagnostics: dict[str, Any] = {
            "positions_before_sell": positions_before_sell,
            "raw_buy_signal_count": raw_buy_signal_count,
            "buy_candidate_count": buy_candidate_count,
            "after_held_filter_count": after_held_filter_count,
            "slope_block_today": slope_block_today,
            "continuity_block_today": continuity_block_today,
            "base_trend_on_rate": float(np.mean(_base_trend_on)) if n > 0 else 0.0,
            "quality_trend_on_rate": float(np.mean(_quality_trend_on)) if n > 0 else 0.0,
            "day_gate_by_symbol": day_gate_by_symbol if _collect_debug else None,
            "day_cands": day_cands,
        }

        return DaySignals(
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            exit_syms=exit_syms,
            strength_map=strength_map,
            mf_score_map=mf_score_map,
            mf_gate_on_today=mf_gate_on_today,
            strong_risk_on=bool(self._strong_risk_on[i]),
            exit_counts=exit_counts,
            diagnostics=diagnostics,
        )
