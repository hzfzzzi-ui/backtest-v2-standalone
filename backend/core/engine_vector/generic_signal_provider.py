"""Generic 策略信号提供者。

封装非 SMA 路径的信号生成逻辑：调用 strategy.generate_signals() + 引擎退出规则 + 多因子快速门控。
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import ExitConfig
from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today
from backend.core.engine_vector.signal_provider import (
    DayContext,
    DaySignals,
    ExitCounts,
    evaluate_engine_exits,
)


# ---------------------------------------------------------------------------
# 多因子快速门控
# ---------------------------------------------------------------------------

def _build_multifactor_and_fast_gate(
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
    for s in extra:
        if isinstance(s, MomentumROCStrategy) and bool(getattr(s, "enable_roc_exit", False)):
            return None
        if isinstance(s, BollingerBreakoutStrategy) and bool(getattr(s, "enable_bb_mid_exit", False)):
            return None
        if not isinstance(s, (VolumeBreakoutStrategy, MomentumROCStrategy, RelativeStrengthStrategy, BollingerBreakoutStrategy)):
            return None

    data = hist[["date", "symbol", "close", "volume"]].copy()
    data["date"] = pd.to_datetime(data["date"])
    data["symbol"] = data["symbol"].astype(str).str.lower()
    data = data.sort_values(["symbol", "date"]).reset_index(drop=True)
    data["n"] = data.groupby("symbol").cumcount() + 1
    day_set = {pd.Timestamp(d).normalize() for d in trading_days}

    factor_sets: list[dict[pd.Timestamp, set[str]]] = []
    for s in extra:
        fdf = data.copy()
        cond = pd.Series(False, index=fdf.index)
        if isinstance(s, VolumeBreakoutStrategy):
            p = int(getattr(s, "vol_ma_period", 20))
            m = float(getattr(s, "vol_mult", 1.5))
            md = int(getattr(s, "min_data_days", 30))
            fdf["vol_ma"] = fdf.groupby("symbol")["volume"].transform(lambda x: x.rolling(p, min_periods=p).mean())
            cond = (fdf["n"] >= md) & (fdf["volume"] > (fdf["vol_ma"] * m))
        elif isinstance(s, MomentumROCStrategy):
            p = int(getattr(s, "roc_period", 20))
            th = float(getattr(s, "roc_threshold", 0.0))
            md = int(getattr(s, "min_data_days", 30))
            prev = fdf.groupby("symbol")["close"].shift(p)
            roc = (fdf["close"] - prev) / prev
            cond = (fdf["n"] >= md) & roc.notna() & (roc >= th)
        elif isinstance(s, RelativeStrengthStrategy):
            p = int(getattr(s, "rs_period", 60))
            th = float(getattr(s, "rs_threshold", 0.7))
            md = int(getattr(s, "min_data_days", 70))
            prev = fdf.groupby("symbol")["close"].shift(p)
            ret = (fdf["close"] - prev) / prev
            fdf["ret"] = ret
            valid = (fdf["n"] >= md) & fdf["ret"].notna()
            rank = fdf[valid].groupby("date")["ret"].rank(method="average", pct=True)
            cond = pd.Series(False, index=fdf.index)
            cond.loc[valid[valid].index] = (rank >= th).values
        elif isinstance(s, BollingerBreakoutStrategy):
            p = int(getattr(s, "bb_period", 20))
            k = float(getattr(s, "bb_std_mult", 2.0))
            md = int(getattr(s, "min_data_days", 30))
            mid = fdf.groupby("symbol")["close"].transform(lambda x: x.rolling(p, min_periods=p).mean())
            std = fdf.groupby("symbol")["close"].transform(lambda x: x.rolling(p, min_periods=p).std())
            upper = mid + k * std
            cond = (fdf["n"] >= md) & upper.notna() & (fdf["close"] > upper)

        pass_df = fdf.loc[cond, ["date", "symbol"]].copy()
        pass_df["date"] = pd.to_datetime(pass_df["date"]).dt.normalize()
        pass_df = pass_df[pass_df["date"].isin(day_set)]
        by_day: dict[pd.Timestamp, set[str]] = {}
        if not pass_df.empty:
            for d, g in pass_df.groupby("date", sort=False):
                by_day[pd.Timestamp(d)] = set(g["symbol"].astype(str).tolist())
        factor_sets.append(by_day)

    return {"base": base, "factor_sets": factor_sets}


# ---------------------------------------------------------------------------
# GenericSignalProvider
# ---------------------------------------------------------------------------

class GenericSignalProvider:
    """Generic 策略（CompositeStrategy 等）的信号提供者。"""

    def __init__(self) -> None:
        # fill hooks（统一循环传给 _process_pending_fills）
        self.extra_clear_dicts: list[dict] = []
        self.last_sell_day: dict[str, date] | None = None
        self.entry_day: dict[str, date] = {}
        self.entry_day_overwrite: bool = False
        self.peak_state_on_buy: dict[str, float] | None = None

        # 内部状态
        self._strategy: Any = None
        self._combined: pd.DataFrame = pd.DataFrame()
        self._day_slice_start: dict[pd.Timestamp, int] = {}
        self._day_slice_end: dict[pd.Timestamp, int] = {}
        self._mf_fast: dict[str, Any] | None = None
        self._merged_exit_cfg: ExitConfig = ExitConfig()
        self._risk_on_map: dict[date, bool] = {}
        self._atr_lookup: dict[str, dict[date, float]] = {}
        self._need_atr: bool = False
        self._max_hold_days: int = 0
        self._peak_close_state: dict[str, float] = {}
        self._strong_risk_on_map: dict[date, bool] = {}
        self._enable_multifactor_rank: bool = False
        self._mf_rank_gate_mode: str = "ALWAYS_ON"

        # 累计计数器
        self.mf_fast_hits: int = 0
        self.blocked_by_trend_count: int = 0
        self.total_buy_signals: int = 0

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
        exit_cfg = kwargs.get("exit_cfg") or ExitConfig()
        history_lookback_days = kwargs.get("history_lookback_days")
        self._enable_multifactor_rank = bool(kwargs.get("enable_multifactor_rank", False))
        self._mf_rank_gate_mode = str(kwargs.get("mf_rank_gate_mode") or "ALWAYS_ON")

        self._strategy = strategy
        day_list = list(trading_days)

        # -- hist 准备（与 benchmark 合并） --
        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"])
        hist["symbol"] = hist["symbol"].astype(str).str.lower()
        hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

        bench = benchmark.copy()
        if not bench.empty:
            bench["date"] = pd.to_datetime(bench["date"])
            bclose = pd.to_numeric(bench["close"], errors="coerce")
            bma120 = bclose.rolling(120, min_periods=120).mean()
            bma200 = bclose.rolling(200, min_periods=200).mean()
            for d, m120, m200 in zip(bench["date"], bma120, bma200):
                dt = pd.Timestamp(d).date()
                if pd.isna(m120) or pd.isna(m200):
                    self._strong_risk_on_map[dt] = False
                else:
                    self._strong_risk_on_map[dt] = bool(float(m120) > float(m200))
            bench["symbol"] = "bench:composite"
            bench = bench.sort_values(["date"]).reset_index(drop=True)
            self._combined = pd.concat([hist, bench], ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
        else:
            self._combined = hist

        # -- day slice 查找表 --
        combined_date_series = self._combined["date"]
        use_lookback = isinstance(history_lookback_days, int) and int(history_lookback_days) > 0
        lookback_n = int(history_lookback_days) if use_lookback else 0
        for day in day_list:
            ts = pd.Timestamp(day)
            self._day_slice_end[ts] = int(combined_date_series.searchsorted(ts, side="right"))
        if use_lookback:
            for idx, day in enumerate(day_list):
                ts = pd.Timestamp(day)
                start_day = day_list[max(0, idx - lookback_n)]
                start_ts = pd.Timestamp(start_day)
                self._day_slice_start[ts] = int(combined_date_series.searchsorted(start_ts, side="left"))
        else:
            for day in day_list:
                self._day_slice_start[pd.Timestamp(day)] = 0

        # -- 多因子快速门控 --
        self._mf_fast = _build_multifactor_and_fast_gate(strategy, hist, day_list)

        # -- 退出规则参数合并 --
        _ec = exit_cfg
        self._atr_stop_k = float(kwargs.get("atr_stop_k", 2.0))
        self._merged_exit_cfg = ExitConfig(
            enable_atr_stop=bool(getattr(strategy, "enable_atr_stop", False)) or bool(_ec.enable_atr_stop),
            enable_atr_trail=bool(getattr(strategy, "enable_atr_trail", False)) or bool(_ec.enable_atr_trail),
            atr_trail_k=float(_ec.atr_trail_k) if _ec.enable_atr_trail else float(getattr(strategy, "atr_trail_k", 3.0)),
            enable_take_profit=_ec.enable_take_profit,
            take_profit_mode=_ec.take_profit_mode,
            take_profit_pct=_ec.take_profit_pct,
            take_profit_atr_k=_ec.take_profit_atr_k,
            enable_fixed_stop_loss=_ec.enable_fixed_stop_loss,
            fixed_stop_loss_pct=_ec.fixed_stop_loss_pct,
        )
        self._max_hold_days = int(getattr(strategy, "max_hold_days", 0))

        # -- benchmark regime（RISK_OFF_EXIT 用） --
        regime_ma = int(getattr(strategy, "regime_ma", 120))
        _bench2 = benchmark.copy()
        _bench2["date"] = pd.to_datetime(_bench2["date"])
        _bench2 = _bench2.sort_values("date")
        _bench_close = pd.to_numeric(_bench2["close"], errors="coerce")
        _bench_ma = _bench_close.rolling(regime_ma, min_periods=regime_ma).mean()
        for _d, _bc, _bm in zip(_bench2["date"], _bench_close, _bench_ma):
            _dd = pd.Timestamp(_d).date()
            if pd.notna(_bc) and pd.notna(_bm):
                self._risk_on_map[_dd] = bool(float(_bc) > float(_bm))
            else:
                self._risk_on_map[_dd] = True

        # -- ATR lookup --
        atr_n = int(getattr(strategy, "atr_n", 14))
        ecfg = self._merged_exit_cfg
        self._need_atr = ecfg.enable_atr_stop or ecfg.enable_atr_trail or (ecfg.enable_take_profit and ecfg.take_profit_mode == "atr")
        if self._need_atr:
            _raw_for_atr = raw_history if raw_history is not None else history
            _raw_atr_df = _raw_for_atr.copy()
            _raw_atr_df["date"] = pd.to_datetime(_raw_atr_df["date"])
            _raw_atr_df["symbol"] = _raw_atr_df["symbol"].astype(str).str.lower()
            for sym_name, sym_df in _raw_atr_df.groupby("symbol"):
                sym_str = str(sym_name).lower()
                sym_df = sym_df.sort_values("date")
                h_s = pd.to_numeric(sym_df["high"], errors="coerce")
                l_s = pd.to_numeric(sym_df["low"], errors="coerce")
                c_s = pd.to_numeric(sym_df["close"], errors="coerce")
                prev_c = c_s.shift(1)
                tr = pd.concat([
                    (h_s - l_s).abs(),
                    (h_s - prev_c).abs(),
                    (l_s - prev_c).abs(),
                ], axis=1).max(axis=1)
                atr_series = tr.rolling(atr_n, min_periods=atr_n).mean()
                atr_map: dict[date, float] = {}
                for d_ts, atr_val in zip(sym_df["date"], atr_series):
                    if pd.notna(atr_val):
                        atr_map[pd.Timestamp(d_ts).date()] = float(atr_val)
                self._atr_lookup[sym_str] = atr_map
            del _raw_atr_df

        # -- fill hooks 初始化 --
        self._peak_close_state = {}
        self.entry_day = {}
        self.extra_clear_dicts = [self._peak_close_state]
        self.last_sell_day = None
        self.entry_day_overwrite = False
        self.peak_state_on_buy = None

        # -- extra daily_row init（统一循环用于最后一天 DR 初始化） --
        self.extra_daily_init: dict[str, Any] = {
            "strong_risk_on": 0,
        }

    # ------------------------------------------------------------------
    # day_signals
    # ------------------------------------------------------------------

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        positions = ctx.positions
        position_avg_cost = ctx.position_avg_cost
        nav = ctx.nav
        max_positions = ctx.max_positions
        base_order_value = ctx.base_order_value
        close_idx = ctx.close_idx
        next_day = ctx.next_day

        # strategy state 更新
        eff_bov = float(base_order_value) if float(base_order_value) > 0 else (float(nav) / float(max_positions) if int(max_positions) > 0 else 0.0)
        self._strategy.state["base_order_value"] = eff_bov

        # 持仓前卖出漏斗
        positions_before_sell = int(sum(1 for _q in positions.values() if int(_q) > 0))

        # ── 退出规则 ──
        exit_rule_sells, exit_rule_syms, ecounts = evaluate_engine_exits(
            positions=positions,
            day=day,
            close_idx=close_idx,
            position_avg_cost=position_avg_cost,
            peak_state=self._peak_close_state,
            entry_day=self.entry_day,
            exit_cfg=self._merged_exit_cfg,
            get_atr=lambda sym, d: (self._atr_lookup.get(sym) or {}).get(d) if self._need_atr else None,
            risk_on=self._risk_on_map.get(day, True),
            max_hold_days=self._max_hold_days,
            atr_stop_k=self._atr_stop_k,
        )

        # ── history view + strategy positions ──
        day_ts = pd.Timestamp(day)
        history_view = self._combined.iloc[self._day_slice_start[day_ts]:self._day_slice_end[day_ts]]
        strategy_positions = {
            sym: Position(symbol=sym, total_qty=int(q), sellable_qty=int(q), avg_cost=float(position_avg_cost.get(sym, 0.0)))
            for sym, q in positions.items()
            if int(q) > 0
        }

        # ── 信号生成 ──
        sell_sigs: list[Signal] = list(exit_rule_sells)
        buy_sigs: list[Signal] = []
        day_raw_buy_signal_count = 0

        if self._mf_fast is not None:
            base_strategy = self._mf_fast["base"]
            base_strategy.state["base_order_value"] = eff_bov
            base_sigs = base_strategy.generate_signals(day, history_view, strategy_positions)
            dts = pd.Timestamp(day).normalize()
            pass_set: set[str] | None = None
            for fs in self._mf_fast["factor_sets"]:
                s = fs.get(dts, set())
                pass_set = set(s) if pass_set is None else (pass_set & set(s))
            pass_set = pass_set or set()
            for sig in base_sigs:
                sig_action = str(sig.action or sig.side.value).upper()
                if sig.side == Side.BUY:
                    self.total_buy_signals += 1
                    day_raw_buy_signal_count += 1
                    if str(sig.action or "").upper() == "BLOCKED" and str(sig.reason_code or "") == "BUY_BLOCKED_TREND_FILTER":
                        self.blocked_by_trend_count += 1
                if sig_action == "BLOCKED":
                    continue
                if sig.side == Side.SELL:
                    if str(sig.symbol).lower() not in exit_rule_syms:
                        sell_sigs.append(sig)
                elif sig.side == Side.BUY and str(sig.symbol).lower() in pass_set:
                    buy_sigs.append(sig)
            self.mf_fast_hits += 1
        else:
            sigs = self._strategy.generate_signals(day, history_view, strategy_positions)
            for sig in sigs:
                sig_action = str(sig.action or sig.side.value).upper()
                if sig.side == Side.BUY:
                    self.total_buy_signals += 1
                    day_raw_buy_signal_count += 1
                    if str(sig.action or "").upper() == "BLOCKED" and str(sig.reason_code or "") == "BUY_BLOCKED_TREND_FILTER":
                        self.blocked_by_trend_count += 1
                if sig_action == "BLOCKED":
                    continue
                if sig.side == Side.SELL:
                    if str(sig.symbol).lower() not in exit_rule_syms:
                        sell_sigs.append(sig)
                elif sig.side == Side.BUY:
                    buy_sigs.append(sig)

        # ── mf_gate / strong_risk_on ──
        regime_on_today = bool(self._strategy.state.get("regime_on", True))
        strong_risk_on_today = bool(self._strong_risk_on_map.get(day, False))
        self._strategy.state["strong_risk_on"] = bool(strong_risk_on_today)
        mf_gate_on_today = resolve_mf_gate_on_today(
            enable_multifactor_rank=self._enable_multifactor_rank,
            mf_rank_gate_mode=self._mf_rank_gate_mode,
            risk_on_today=bool(regime_on_today),
            strong_risk_on_today=bool(strong_risk_on_today),
        )

        diagnostics: dict[str, Any] = {
            "positions_before_sell": positions_before_sell,
            "raw_buy_signal_count": day_raw_buy_signal_count,
            "buy_candidate_count": len(buy_sigs),
            "after_held_filter_count": len(buy_sigs),
        }

        return DaySignals(
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            exit_syms=exit_rule_syms,
            strength_map={},
            mf_score_map={},
            mf_gate_on_today=mf_gate_on_today,
            strong_risk_on=strong_risk_on_today,
            exit_counts=ecounts,
            diagnostics=diagnostics,
        )
