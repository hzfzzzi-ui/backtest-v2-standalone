"""Breakout Trend 信号提供者。

V2 Stage 6: close > max(high[-20:]) 突破入场信号。
使用 SignalProvider 协议，可被引擎统一循环调用。
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
from backend.core.engine_vector.signal_provider import (
    DayContext,
    DaySignals,
    ExitCounts,
    evaluate_engine_exits,
)


class BreakoutTrendProvider:
    """20-Day High Breakout 信号提供者。

    买入信号: close[t] > high_max20[t-1]  (昨日 20 日最高价突破)
    卖出信号: 由 evaluate_engine_exits 统一评估
    """

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
        self._breakout_up: np.ndarray = np.array([])
        self._breakout_up_short: np.ndarray = np.array([])
        self._breakout_up_long: np.ndarray = np.array([])
        self._high_max_short: np.ndarray = np.array([])
        self._high_max_long: np.ndarray = np.array([])
        self._high_max_main: np.ndarray = np.array([])
        self._v2_trend_ok: np.ndarray = np.array([])
        self._entry_confirm_ok: np.ndarray = np.array([])
        self._entry_delay_ok: np.ndarray = np.array([])
        self._cand_idx: Any = None
        self._bench_close: np.ndarray = np.array([])
        self._risk_on: np.ndarray = np.array([])
        self._sym_to_col: dict[str, int] = {}
        self._ec: ExitConfig = ExitConfig()
        self._peak_close_state: dict[str, float] = {}

        # strategy 参数
        self._breakout_window: int = 20
        self._enable_dual_breakout: bool = False
        self._breakout_window_short: int = 20
        self._breakout_window_long: int = 55
        self._breakout_entry_buffer_pct: float = 0.0
        self._entry_confirm_mode: str = "none"
        self._entry_delay_mode: str = "none"
        self._enable_atr_stop: bool = False
        self._enable_atr_trail: bool = False
        self._atr_stop_k: float = 2.0
        self._atr_trail_k: float = 3.0
        self._order_size: int = 1000
        self._max_hold_days: int = 0
        self._min_hold_days: int = 0
        self._cooldown_days: int = 0
        self._enable_risk_off_exit: bool = False
        self._min_hold_exempt_set: set[str] = set()
        self._base_order_value: float = 0.0

        # 累计计数器
        self.total_buy_signals: int = 0
        self.min_hold_block_count: int = 0
        self.cooldown_block_count: int = 0
        self.precompute_seconds: float = 0.0
        self.diag_reason_counts: dict[str, int] = {}

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
        st_history = kwargs.get("st_history")
        strength_ma = int(kwargs.get("strength_ma", 120))
        self._base_order_value = float(kwargs.get("base_order_value", 0.0))

        self._ec = exit_cfg
        pre_t0 = _time.perf_counter()

        # -- strategy 参数提取 --
        self._breakout_window = int(getattr(strategy, "breakout_window", 20))
        self._enable_dual_breakout = bool(getattr(strategy, "enable_dual_breakout", False))
        self._breakout_window_short = int(getattr(strategy, "breakout_window_short", 20))
        self._breakout_window_long = int(getattr(strategy, "breakout_window_long", max(self._breakout_window, 55)))
        self._breakout_entry_buffer_pct = float(getattr(strategy, "breakout_entry_buffer_pct", 0.0))
        self._entry_confirm_mode = str(getattr(strategy, "entry_confirm_mode", "none") or "none").strip().lower()
        self._entry_delay_mode = str(getattr(strategy, "entry_delay_mode", "none") or "none").strip().lower()
        self._enable_atr_stop = bool(getattr(strategy, "enable_atr_stop", False))
        self._enable_atr_trail = bool(getattr(strategy, "enable_atr_trail", False))
        self._atr_stop_k = float(kwargs.get("atr_stop_k", getattr(strategy, "atr_stop_k", 2.0)))
        self._atr_trail_k = float(getattr(strategy, "atr_trail_k", 3.0))
        self._order_size = int(getattr(strategy, "order_size", 1000))
        regime_ma = int(getattr(strategy, "regime_ma", 60))
        self._max_hold_days = int(getattr(strategy, "max_hold_days", 0))
        self._min_hold_days = int(getattr(strategy, "min_hold_days", 0))
        self._cooldown_days = int(getattr(strategy, "cooldown_days", 0))
        self._min_hold_exempt_set = set(getattr(strategy, "min_hold_exempt_reasons", []) or [])
        self._enable_risk_off_exit = bool(getattr(strategy, "enable_risk_off_exit", False))

        enable_v2_trend_filter = bool(getattr(strategy, "enable_v2_trend_filter", True))
        v2_trend_short_ma = int(getattr(strategy, "v2_trend_short_ma", 20))
        v2_trend_long_ma = int(getattr(strategy, "v2_trend_long_ma", 60))

        # -- OHLC + feature 矩阵 --
        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"])
        hist["symbol"] = hist["symbol"].astype(str).str.lower()
        hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

        _uf = dict(getattr(strategy, "state", {}).get("universe_filters") or {})
        _min_price = float(_uf.get("min_price", getattr(strategy, "min_price", 0.0)) or 0.0)
        _min_list_days = int(_uf.get("min_list_days", 0) or 0)
        _min_avg_turnover_20d = float(_uf.get("min_avg_turnover_20d", 0.0) or 0.0)
        self._mx = build_ohlc_matrices_from_history(
            hist,
            trading_days,
            st_history=st_history,
            min_price=_min_price,
            min_list_days=_min_list_days,
            min_avg_turnover_20d=_min_avg_turnover_20d,
        )
        mx = self._mx
        t, n = mx.close.shape
        if n == 0:
            raise ValueError("history has no symbols")

        self._feats = compute_feature_matrices(
            close=mx.close, high=mx.high, low=mx.low,
            fast=5, slow=20,
            trend_fast=120, trend_slow=200,
            atr_n=14, strength_ma=strength_ma,
            v2_trend_short_ma=v2_trend_short_ma,
            v2_trend_long_ma=v2_trend_long_ma,
            breakout_window=max(self._breakout_window, self._breakout_window_short, self._breakout_window_long),
        )
        feats = self._feats

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

        # -- breakout signal matrix: close[t] > high_max(window)[t-1] * (1+buffer) --
        def _rolling_high_max(arr: np.ndarray, window: int) -> np.ndarray:
            w = max(2, int(window))
            return pd.DataFrame(arr).rolling(w, min_periods=w).max().to_numpy(dtype=float)

        self._high_max_short = _rolling_high_max(mx.high, self._breakout_window_short)
        self._high_max_long = _rolling_high_max(mx.high, self._breakout_window_long)
        self._high_max_main = _rolling_high_max(mx.high, self._breakout_window)
        self._breakout_up_short = np.zeros((t, n), dtype=bool)
        self._breakout_up_long = np.zeros((t, n), dtype=bool)
        self._breakout_up = np.zeros((t, n), dtype=bool)
        if t > 1:
            curr_close = mx.close[1:, :]
            _buf = max(0.0, float(self._breakout_entry_buffer_pct))

            prev_hmax_short = self._high_max_short[:-1, :]
            prev_hmax_long = self._high_max_long[:-1, :]
            valid_short = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_short)
            valid_long = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_long)
            self._breakout_up_short[1:, :] = (curr_close > (prev_hmax_short * (1.0 + _buf))) & valid_short
            self._breakout_up_long[1:, :] = (curr_close > (prev_hmax_long * (1.0 + _buf))) & valid_long

            if self._enable_dual_breakout:
                self._breakout_up = self._breakout_up_short | self._breakout_up_long
            else:
                if int(self._breakout_window) == int(self._breakout_window_short):
                    self._breakout_up = self._breakout_up_short.copy()
                elif int(self._breakout_window) == int(self._breakout_window_long):
                    self._breakout_up = self._breakout_up_long.copy()
                else:
                    prev_hmax_main = self._high_max_main[:-1, :]
                    valid_main = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_main)
                    self._breakout_up[1:, :] = (curr_close > (prev_hmax_main * (1.0 + _buf))) & valid_main

        # -- entry confirmation matrix --
        self._entry_confirm_ok = np.ones((t, n), dtype=bool)
        _eps = 1e-8
        if self._entry_confirm_mode == "close_strength":
            spread = mx.high - mx.low
            close_pos = np.where(spread > _eps, (mx.close - mx.low) / spread, np.nan)
            self._entry_confirm_ok = (~np.isnan(close_pos)) & (close_pos > 0.6)
        elif self._entry_confirm_mode == "volume_confirm":
            vol_ma20 = pd.DataFrame(mx.volume).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
            self._entry_confirm_ok = (~np.isnan(mx.volume)) & (~np.isnan(vol_ma20)) & (mx.volume > vol_ma20)
        elif self._entry_confirm_mode == "volatility_confirm":
            prev_close = np.empty_like(mx.close)
            prev_close[:] = np.nan
            if t > 1:
                prev_close[1:, :] = mx.close[:-1, :]
            tr1 = mx.high - mx.low
            tr2 = np.abs(mx.high - prev_close)
            tr3 = np.abs(mx.low - prev_close)
            tr = np.fmax(tr1, np.fmax(tr2, tr3))
            atr20 = pd.DataFrame(tr).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
            self._entry_confirm_ok = (~np.isnan(tr)) & (~np.isnan(atr20)) & (tr > (atr20 * 0.8))
        elif self._entry_confirm_mode not in {"none", ""}:
            self._entry_confirm_mode = "none"

        # -- entry delay confirmation matrix --
        self._entry_delay_ok = self._breakout_up.copy()
        if self._entry_delay_mode == "t1_confirm":
            _prev = np.zeros_like(self._breakout_up, dtype=bool)
            if t > 1:
                _prev[1:, :] = self._breakout_up[:-1, :]
            self._entry_delay_ok = self._breakout_up & _prev
        elif self._entry_delay_mode == "t2_confirm":
            _prev2 = np.zeros_like(self._breakout_up, dtype=bool)
            if t > 2:
                _prev2[2:, :] = self._breakout_up[:-2, :]
            self._entry_delay_ok = self._breakout_up & _prev2
        elif self._entry_delay_mode == "pullback_confirm":
            self._entry_delay_ok = np.zeros((t, n), dtype=bool)
            if t > 1:
                prev_breakout = self._breakout_up[:-1, :]
                level = self._high_max_main[:-1, :]
                low_touch = (~np.isnan(mx.low[1:, :])) & (~np.isnan(level)) & (mx.low[1:, :] <= level)
                close_reclaim = (~np.isnan(mx.close[1:, :])) & (~np.isnan(level)) & (mx.close[1:, :] > level)
                self._entry_delay_ok[1:, :] = prev_breakout & low_touch & close_reclaim
        elif self._entry_delay_mode not in {"none", ""}:
            self._entry_delay_mode = "none"

        # -- V2 个股趋势过滤 --
        self._v2_trend_ok = np.ones((t, n), dtype=bool)
        if enable_v2_trend_filter:
            self._v2_trend_ok = (
                ~np.isnan(mx.close)
                & ~np.isnan(feats.sma20)
                & ~np.isnan(feats.sma60)
                & (mx.close > feats.sma60)
                & (feats.sma20 > feats.sma60)
            )

        # -- Momentum 前置过滤: 60日动量 top N% --
        momentum_top_pct = float(getattr(strategy, "momentum_top_pct", 0.0))
        momentum_window = 60
        self._momentum_ok = np.ones((t, n), dtype=bool)
        if momentum_top_pct > 0:
            # 60日收益率 = close[t] / close[t-60] - 1
            mom = np.full((t, n), np.nan, dtype=float)
            if t > momentum_window:
                prev_close = mx.close[:-momentum_window, :]
                curr_close = mx.close[momentum_window:, :]
                safe_prev = np.where(prev_close > 1e-8, prev_close, np.nan)
                mom[momentum_window:, :] = curr_close / safe_prev - 1.0
            # 每日排名, 只取 top N%
            self._momentum_ok = np.zeros((t, n), dtype=bool)
            for _di in range(t):
                row = mom[_di, :]
                valid_mask = ~np.isnan(row) & mx.tradable[_di, :]
                valid_count = int(np.sum(valid_mask))
                if valid_count == 0:
                    continue
                topk = max(1, int(valid_count * momentum_top_pct))
                # 找 top-K 的阈值
                valid_vals = row[valid_mask]
                threshold = np.partition(valid_vals, -topk)[-topk]
                self._momentum_ok[_di, :] = valid_mask & (row >= threshold)

        # -- 综合买入候选矩阵 --
        risk_on_m = np.repeat(self._risk_on.reshape(-1, 1), n, axis=1)
        buy_base = self._entry_delay_ok & self._entry_confirm_ok & self._v2_trend_ok & risk_on_m & mx.tradable & self._momentum_ok
        self._cand_idx = build_daily_candidate_index(buy_base)
        self._sym_to_col = {s: idx for idx, s in enumerate(mx.symbols)}

        # -- fill hooks 初始化 --
        self._peak_close_state = {}
        self.entry_day = {}
        self.last_sell_day = {}
        self.extra_clear_dicts = [self._peak_close_state]
        self.peak_state_on_buy = self._peak_close_state

        self.precompute_seconds = float(_time.perf_counter() - pre_t0)

    # ------------------------------------------------------------------
    # day_signals
    # ------------------------------------------------------------------

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        i = day_idx
        mx = self._mx
        feats = self._feats
        positions = ctx.positions
        position_avg_cost = ctx.position_avg_cost
        close_idx = ctx.close_idx
        nav = ctx.nav
        max_positions = ctx.max_positions
        base_order_value = ctx.base_order_value
        n = mx.close.shape[1]

        # ── 卖出信号: engine 级退出规则 ──
        def _get_atr(sym: str, d: date) -> float | None:
            col = self._sym_to_col.get(sym)
            if col is None:
                return None
            v = float(feats.atr14[i, col])
            return v if not np.isnan(v) else None

        def _check_ma20(sym: str) -> bool:
            col = self._sym_to_col.get(sym)
            if col is None:
                return False
            adj_c = float(mx.close[i, col])
            sma20_v = float(feats.sma20[i, col])
            if np.isnan(adj_c) or np.isnan(sma20_v):
                return False
            return adj_c < sma20_v

        def _check_low10(sym: str) -> bool:
            col = self._sym_to_col.get(sym)
            if col is None:
                return False
            adj_c = float(mx.close[i, col])
            low10_v = float(feats.low_min10[i, col])
            if np.isnan(adj_c) or np.isnan(low10_v):
                return False
            return adj_c < low10_v

        sell_sigs, exit_syms, exit_counts = evaluate_engine_exits(
            positions=positions,
            day=day,
            close_idx=close_idx,
            position_avg_cost=position_avg_cost,
            peak_state=self._peak_close_state,
            entry_day=self.entry_day,
            exit_cfg=self._ec,
            get_atr=_get_atr,
            risk_on=bool(self._risk_on[i]),
            enable_risk_off_exit=self._enable_risk_off_exit,
            max_hold_days=self._max_hold_days,
            atr_stop_k=self._atr_stop_k,
            check_ma20_exit=_check_ma20,
            check_low10_exit=_check_low10,
        )
        for _ss in sell_sigs:
            _rc = str(_ss.reason_code)
            self.diag_reason_counts[_rc] = int(self.diag_reason_counts.get(_rc, 0)) + 1

        # ── 买入信号 ──
        day_cands = self._cand_idx[i]
        buy_sigs: list[Signal] = []
        self.total_buy_signals += int(len(day_cands))

        for c in day_cands:
            sym = mx.symbols[int(c)]
            # 已持有跳过
            if sym in positions and int(positions[sym]) > 0:
                continue
            # min_hold 约束
            if self._min_hold_days > 0 and sym in self.entry_day:
                held = (day - self.entry_day[sym]).days
                if held < self._min_hold_days:
                    self.min_hold_block_count += 1
                    continue
            # cooldown 约束
            if self._cooldown_days > 0 and self.last_sell_day and sym in self.last_sell_day:
                since_sell = (day - self.last_sell_day[sym]).days
                if since_sell < self._cooldown_days:
                    self.cooldown_block_count += 1
                    continue

            close_val = float(mx.close[i, c]) if not np.isnan(mx.close[i, c]) else None
            hmax_prev_short = float(self._high_max_short[i - 1, c]) if (i > 0 and not np.isnan(self._high_max_short[i - 1, c])) else None
            hmax_prev_long = float(self._high_max_long[i - 1, c]) if (i > 0 and not np.isnan(self._high_max_long[i - 1, c])) else None
            hit_short = bool(self._breakout_up_short[i, c]) if self._breakout_up_short.size else False
            hit_long = bool(self._breakout_up_long[i, c]) if self._breakout_up_long.size else False

            buy_sigs.append(Signal(
                signal_date=day,
                symbol=sym,
                side=Side.BUY,
                qty=self._order_size,
                reason="BREAKOUT_DUAL_OR" if self._enable_dual_breakout else "BREAKOUT_HIGH",
                reason_code="BREAKOUT_DUAL_OR" if self._enable_dual_breakout else "BREAKOUT_HIGH",
                meta={
                    "close": close_val,
                    "breakout_window_main": int(self._breakout_window),
                    "breakout_window_short": int(self._breakout_window_short),
                    "breakout_window_long": int(self._breakout_window_long),
                    "breakout_entry_buffer_pct": float(self._breakout_entry_buffer_pct),
                    "entry_confirm_mode": str(self._entry_confirm_mode),
                    "entry_delay_mode": str(self._entry_delay_mode),
                    "high_max_short_prev": hmax_prev_short,
                    "high_max_long_prev": hmax_prev_long,
                    "breakout_hit_short": hit_short,
                    "breakout_hit_long": hit_long,
                    "v2_trend_ok": bool(self._v2_trend_ok[i, c]),
                    "regime_on": bool(self._risk_on[i]),
                },
            ))

        return DaySignals(
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            exit_syms=exit_syms,
            strength_map={},
            mf_score_map={},
            mf_gate_on_today=False,
            strong_risk_on=False,
            exit_counts=exit_counts,
            diagnostics={
                "breakout_candidates": int(len(day_cands)),
                "buy_signals_generated": int(len(buy_sigs)),
            },
        )
