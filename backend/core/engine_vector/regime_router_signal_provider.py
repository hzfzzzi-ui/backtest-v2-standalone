"""RegimeRouter 策略向量化信号提供者。

将 RegimeRouter 的 O(N×D²) per-day 信号生成转化为
O(N×D) 矩阵预计算 + O(1) 逐日查表。
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
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today
from backend.core.engine_vector.regime_filter import RegimeFilter, RegimeFilterConfig
from backend.core.engine_vector.signal_provider import (
    DayContext,
    DaySignals,
    ExitCounts,
    evaluate_engine_exits,
)


class RegimeRouterSignalProvider:
    """RegimeRouter 的向量化信号提供者。"""

    def __init__(self) -> None:
        # fill hooks（统一循环传给 _process_pending_fills）
        self.extra_clear_dicts: list[dict] = []
        self.last_sell_day: dict[str, date] | None = None
        self.entry_day: dict[str, date] = {}
        self.entry_day_overwrite: bool = False
        self.peak_state_on_buy: dict[str, float] | None = None

        # 矩阵（precompute 后填充）
        self._mx: Any = None
        self._feats: Any = None
        self._sma_buy_ok: np.ndarray = np.array([])
        self._sma_sell_ok: np.ndarray = np.array([])
        self._rsi_buy: np.ndarray = np.array([])
        self._rsi_overbought: np.ndarray = np.array([])
        self._sma_cand_idx: list[np.ndarray] = []
        self._rsi_cand_idx: list[np.ndarray] = []
        self._bench_close: np.ndarray = np.array([])
        self._regime_on: np.ndarray = np.array([])     # 1D (T,) bool or 2D (T, N) bool
        self._use_regime_filter: bool = False            # True when RegimeFilter is active
        self._regime_filter: RegimeFilter | None = None
        self._risk_on_exits: np.ndarray = np.array([])
        self._strong_risk_on: np.ndarray = np.array([])
        self._sym_to_col: dict[str, int] = {}

        # MA200 市场过滤器
        self._use_market_filter: bool = False
        self._market_state: np.ndarray = np.array([])    # (T,) int8: 0=BULL,1=TRANS_DOWN,2=TRANS_UP,3=BEAR
        self._trade_mode: np.ndarray = np.array([])       # (T,) int8: 0=TREND_MAIN,1=TREND_LIGHT,2=NO_TRADE
        self._ema_light_buy_ok: np.ndarray = np.array([])
        self._ema_light_sell_ok: np.ndarray = np.array([])
        self._ema_light_cand_idx: list[np.ndarray] = []

        # ATR lookup（raw history 计算，用于 evaluate_engine_exits）
        self._atr_lookup: dict[str, dict[date, float]] = {}
        self._need_atr: bool = False

        # 退出配置
        self._ec: ExitConfig = ExitConfig()
        self._atr_stop_k: float = 2.0
        self._peak_close_state: dict[str, float] = {}

        # 策略参数
        self._fast: int = 5
        self._slow: int = 20
        self._trend_order_size: int = 1000
        self._mr_rsi_period: int = 6
        self._mr_rsi_buy_threshold: float = 20.0
        self._mr_rsi_sell_threshold: float = 80.0
        self._mr_max_hold_days: int = 5
        self._mr_stop_loss_pct: float = 0.03
        self._mr_order_size: int = 1000
        self._ma_type: str = "SMA"

        # MR 持仓状态
        self._mr_symbols: set[str] = set()
        self._mr_entry_day: dict[str, date] = {}
        self._mr_entry_price: dict[str, float] = {}

        # 多因子
        self._enable_multifactor_rank: bool = False
        self._mf_rank_gate_mode: str = "ALWAYS_ON"

        # 诊断计数器
        self.total_buy_signals: int = 0
        self.blocked_by_trend_count: int = 0
        self.regime_trend_days: int = 0
        self.regime_mr_days: int = 0
        self.mr_rsi_oversold_buy_count: int = 0
        self.mr_rsi_overbought_sell_count: int = 0
        self.mr_stop_loss_count: int = 0
        self.mr_time_exit_count: int = 0
        self.atr_stop_exit_count: int = 0
        self.atr_trail_exit_count: int = 0
        self.atr_trail_update_count: int = 0
        self.take_profit_exit_count: int = 0
        self.fixed_stop_loss_exit_count: int = 0
        self.precompute_seconds: float = 0.0
        self.diag_reason_counts: dict[str, int] = {}

        # 市场状态分布计数器
        self.market_state_bull_days: int = 0
        self.market_state_bear_days: int = 0
        self.market_state_trans_down_days: int = 0
        self.market_state_trans_up_days: int = 0
        self.trade_mode_main_days: int = 0
        self.trade_mode_light_days: int = 0
        self.trade_mode_notrade_days: int = 0

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

        pre_t0 = _time.perf_counter()
        exit_cfg = kwargs.get("exit_cfg") or ExitConfig()
        self._enable_multifactor_rank = bool(kwargs.get("enable_multifactor_rank", False))
        self._mf_rank_gate_mode = str(kwargs.get("mf_rank_gate_mode") or "ALWAYS_ON")
        st_history = kwargs.get("st_history")
        membership_history = kwargs.get("membership_history")
        self._ec = exit_cfg
        self._atr_stop_k = float(kwargs.get("atr_stop_k", 2.0))

        # ── 从 RegimeRouter 提取参数 ──
        detector = getattr(strategy, "detector", None)
        regime_ma = int(getattr(detector, "regime_ma", 60)) if detector else 60

        trend_strat = getattr(strategy, "trend_strategy", None)
        self._fast = int(getattr(trend_strat, "fast", 5))
        self._slow = int(getattr(trend_strat, "slow", 20))
        self._trend_order_size = int(getattr(trend_strat, "order_size", 1000))
        self._ma_type = str(getattr(trend_strat, "ma_type", "SMA")).upper()

        mr_strat = getattr(strategy, "mr_strategy", None)
        self._mr_rsi_period = int(getattr(mr_strat, "rsi_period", 6))
        self._mr_rsi_buy_threshold = float(getattr(mr_strat, "rsi_buy_threshold", 20.0))
        self._mr_rsi_sell_threshold = float(getattr(mr_strat, "rsi_sell_threshold", 80.0))
        self._mr_max_hold_days = int(getattr(mr_strat, "mr_max_hold_days", 5))
        self._mr_stop_loss_pct = float(getattr(mr_strat, "mr_stop_loss_pct", 0.03))
        self._mr_order_size = int(getattr(mr_strat, "order_size", 1000))

        # ── OHLC + feature 矩阵 ──
        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"])
        hist["symbol"] = hist["symbol"].astype(str).str.lower()
        hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

        _uf = dict(getattr(strategy, "state", {}).get("universe_filters") or {})
        _min_price = float(_uf.get("min_price", getattr(strategy, "min_price", 0.0) or getattr(trend_strat, "min_price", 0.0)) or 0.0)
        _min_list_days = int(_uf.get("min_list_days", 0) or 0)
        _min_avg_turnover_20d = float(_uf.get("min_avg_turnover_20d", 0.0) or 0.0)
        self._mx = build_ohlc_matrices_from_history(
            hist,
            trading_days,
            st_history=st_history,
            membership_history=membership_history,
            min_price=_min_price,
            min_list_days=_min_list_days,
            min_avg_turnover_20d=_min_avg_turnover_20d,
        )
        mx = self._mx
        t, n = mx.close.shape
        if n == 0:
            raise ValueError("history has no symbols")

        self._sym_to_col = {s: idx for idx, s in enumerate(mx.symbols)}

        self._feats = compute_feature_matrices(
            close=mx.close, high=mx.high, low=mx.low,
            fast=self._fast, slow=self._slow,
            trend_fast=120, trend_slow=200,
            atr_n=14, strength_ma=120, ma_type=self._ma_type,
            rsi_period=self._mr_rsi_period,
        )
        feats = self._feats

        # ── benchmark 数组 ──
        bench = benchmark.copy()
        bench["date"] = pd.to_datetime(bench["date"])
        bench = bench.sort_values("date")
        bench_close_s = pd.to_numeric(bench["close"], errors="coerce")

        # regime_on: 策略路由用 (MA=detector.regime_ma)
        bench_regime_ma_s = bench_close_s.rolling(regime_ma, min_periods=regime_ma).mean()
        bmap_close = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_close_s)}
        bmap_regime = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_regime_ma_s)}
        self._bench_close = np.array([bmap_close.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        bench_regime_arr = np.array([bmap_regime.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        self._regime_on = np.ones(t, dtype=bool)
        valid_regime = ~np.isnan(self._bench_close) & ~np.isnan(bench_regime_arr)
        self._regime_on[valid_regime] = self._bench_close[valid_regime] > bench_regime_arr[valid_regime]

        # ── RegimeFilter 覆盖（三层层级趋势过滤器） ──
        rf_cfg_raw = kwargs.get("regime_filter_cfg") or getattr(strategy, "regime_filter_cfg", None)
        sector_data_kw: dict[str, pd.DataFrame] = kwargs.get("sector_data") or {}
        industry_map_kw: dict[str, str] = kwargs.get("industry_map") or {}

        _rf_config: RegimeFilterConfig | None = None
        if isinstance(rf_cfg_raw, RegimeFilterConfig):
            _rf_config = rf_cfg_raw
        elif isinstance(rf_cfg_raw, dict) and rf_cfg_raw.get("enabled", True):
            _rf_fields = {k: v for k, v in rf_cfg_raw.items() if k in RegimeFilterConfig.__dataclass_fields__}
            _rf_config = RegimeFilterConfig(**_rf_fields)

        if _rf_config is not None and _rf_config.enabled:
            self._regime_filter = RegimeFilter(_rf_config)

            # 构建 benchmark high/low 数组
            bench_high_s = pd.to_numeric(bench["high"], errors="coerce")
            bench_low_s = pd.to_numeric(bench["low"], errors="coerce")
            bmap_high = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_high_s) if pd.notna(v)}
            bmap_low = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_low_s) if pd.notna(v)}
            bench_high_arr = np.array([bmap_high.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
            bench_low_arr = np.array([bmap_low.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)

            _stc = self._sym_to_col if self._sym_to_col else {s: idx for idx, s in enumerate(mx.symbols)}
            self._regime_filter.precompute(
                benchmark_close=self._bench_close,
                benchmark_high=bench_high_arr,
                benchmark_low=bench_low_arr,
                stock_close=mx.close,
                stock_high=mx.high,
                stock_low=mx.low,
                sector_data=sector_data_kw,
                industry_map=industry_map_kw,
                sym_to_col=_stc,
                trading_days=list(trading_days),
            )

            # 用 regime_signals >= threshold 生成逐股票 regime_on[T, N]
            rs = self._regime_filter.regime_signals
            self._regime_on = rs >= _rf_config.regime_threshold  # (T, N) bool
            self._use_regime_filter = True

        # risk_on_exits: evaluate_engine_exits 用 (MA=120，匹配 GenericSignalProvider 默认值)
        _exit_regime_ma = 120
        bench_exit_ma_s = bench_close_s.rolling(_exit_regime_ma, min_periods=_exit_regime_ma).mean()
        bmap_exit = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_exit_ma_s)}
        bench_exit_arr = np.array([bmap_exit.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        self._risk_on_exits = np.ones(t, dtype=bool)
        valid_exit = ~np.isnan(self._bench_close) & ~np.isnan(bench_exit_arr)
        self._risk_on_exits[valid_exit] = self._bench_close[valid_exit] > bench_exit_arr[valid_exit]

        # strong_risk_on（mf_gate 用）
        bench_ma120_s = bench_close_s.rolling(120, min_periods=120).mean()
        bench_ma200_s = bench_close_s.rolling(200, min_periods=200).mean()
        bmap_ma120 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma120_s)}
        bmap_ma200 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma200_s)}
        bench_ma120 = np.array([bmap_ma120.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        bench_ma200 = np.array([bmap_ma200.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        self._strong_risk_on = np.zeros(t, dtype=bool)
        valid_strong = ~np.isnan(bench_ma120) & ~np.isnan(bench_ma200)
        self._strong_risk_on[valid_strong] = bench_ma120[valid_strong] > bench_ma200[valid_strong]

        # ── MA200 市场过滤器（四态分类 + trade_mode） ──
        from backend.core.config.models import MarketFilterConfig
        _mf_cfg_raw = kwargs.get("market_filter_cfg")
        _mf_cfg: MarketFilterConfig | None = None
        if isinstance(_mf_cfg_raw, MarketFilterConfig):
            _mf_cfg = _mf_cfg_raw
        elif isinstance(_mf_cfg_raw, dict) and _mf_cfg_raw.get("enabled", False):
            _mf_fields = {k: v for k, v in _mf_cfg_raw.items() if k in MarketFilterConfig.__dataclass_fields__}
            _mf_cfg = MarketFilterConfig(**_mf_fields)

        if _mf_cfg is not None and _mf_cfg.enabled:
            self._use_market_filter = True
            _slope_w = _mf_cfg.slope_window
            _slope_period = getattr(_mf_cfg, "slope_ma_period", 50)

            _ma200_arr = bench_ma200

            # 动量指标: EMA(slope_ma_period) 的百分比斜率（替代 MA200 差分）
            _slope_ema_s = bench_close_s.ewm(span=_slope_period, adjust=False).mean()
            _bmap_slope_ema = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
                               for d, v in zip(bench["date"], _slope_ema_s)}
            _slope_ema_arr = np.array([_bmap_slope_ema.get(pd.Timestamp(d).normalize(), np.nan)
                                       for d in mx.dates], dtype=float)
            _momentum = np.full(t, np.nan, dtype=float)
            if _slope_w < t:
                _prev = _slope_ema_arr[:-_slope_w]
                _curr = _slope_ema_arr[_slope_w:]
                _safe_prev = np.where(np.abs(_prev) > 1e-8, _prev, np.nan)
                _momentum[_slope_w:] = (_curr - _prev) / _safe_prev

            # benchmark MA20, MA60（用于过渡态入场条件）
            _bench_ma20_s = bench_close_s.rolling(20, min_periods=20).mean()
            _bench_ma60_s = bench_close_s.rolling(60, min_periods=60).mean()
            _bmap_ma20 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
                          for d, v in zip(bench["date"], _bench_ma20_s)}
            _bmap_ma60 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
                          for d, v in zip(bench["date"], _bench_ma60_s)}
            _bench_ma20 = np.array([_bmap_ma20.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
            _bench_ma60 = np.array([_bmap_ma60.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)

            # 20日最高收盘价、60日最高价
            _bench_high_s = pd.to_numeric(bench["high"], errors="coerce")
            _bmap_high = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan)
                          for d, v in zip(bench["date"], _bench_high_s)}
            _bench_high_arr = np.array([_bmap_high.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
            # rolling max: 用 pandas 在 aligned 数组上算
            _bc_s = pd.Series(self._bench_close)
            _bh_s = pd.Series(_bench_high_arr)
            _close_max20 = _bc_s.rolling(20, min_periods=20).max().values
            _high_max60 = _bh_s.rolling(60, min_periods=60).max().values

            # 构建 _market_state[T]
            _ms = np.zeros(t, dtype=np.int8)  # 默认 0=BULL
            _bc = self._bench_close
            _above_ma200 = _bc > _ma200_arr
            _slope_pos = _momentum >= 0
            _valid_mf = ~np.isnan(_ma200_arr) & ~np.isnan(_momentum) & ~np.isnan(_bc)
            # BULL=0 (above + slope>=0), TRANS_DOWN=1 (above + slope<0),
            # TRANS_UP=2 (below + slope>=0), BEAR=3 (below + slope<0)
            _ms[_valid_mf & _above_ma200 & ~_slope_pos] = 1   # TRANS_DOWN
            _ms[_valid_mf & ~_above_ma200 & _slope_pos] = 2   # TRANS_UP
            _ms[_valid_mf & ~_above_ma200 & ~_slope_pos] = 3  # BEAR
            # 数据不足的保持 0=BULL（默认）
            self._market_state = _ms

            # 构建过渡态 entry_signal
            # 条件 A (TRANS_DOWN): MA20>MA60 & close>MA20 & close>max(close,20d)
            _cond_a = (_bench_ma20 > _bench_ma60) & (_bc > _bench_ma20) & (_bc > _close_max20)
            # 条件 B (TRANS_UP): close>HH60 & close>MA60 & MA20>MA60
            _cond_b = (_bc > _high_max60) & (_bc > _bench_ma60) & (_bench_ma20 > _bench_ma60)
            # NaN 安全
            _cond_a[np.isnan(_bench_ma20) | np.isnan(_bench_ma60) | np.isnan(_close_max20)] = False
            _cond_b[np.isnan(_bench_ma60) | np.isnan(_high_max60) | np.isnan(_bench_ma20)] = False

            # 构建 _trade_mode[T]
            _tm = np.full(t, 2, dtype=np.int8)  # 默认 NO_TRADE=2
            _tm[_ms == 0] = 0  # BULL → TREND_MAIN
            _tm[(_ms == 1) & _cond_a] = 1  # TRANS_DOWN + entry_signal → TREND_LIGHT
            _tm[(_ms == 2) & _cond_b] = 1  # TRANS_UP + entry_signal → TREND_LIGHT
            # BEAR 和无信号的 TRANSITION 保持 NO_TRADE=2
            self._trade_mode = _tm

            # EMA5/20 轻趋势信号矩阵
            _ema_fast = _mf_cfg.ema_light_fast
            _ema_slow = _mf_cfg.ema_light_slow
            _close_filled_ema = pd.DataFrame(mx.close).ffill().to_numpy(dtype=float)
            _ema_fast_ma = pd.DataFrame(_close_filled_ema).ewm(span=_ema_fast, adjust=False).mean().values
            _ema_slow_ma = pd.DataFrame(_close_filled_ema).ewm(span=_ema_slow, adjust=False).mean().values
            _valid_ema = ~np.isnan(_ema_fast_ma) & ~np.isnan(_ema_slow_ma)
            self._ema_light_buy_ok = _valid_ema & (_ema_fast_ma > _ema_slow_ma)
            self._ema_light_sell_ok = _valid_ema & (_ema_fast_ma < _ema_slow_ma)
            self._ema_light_cand_idx = build_daily_candidate_index(self._ema_light_buy_ok)
            del _close_filled_ema

        # ── SMA 信号矩阵（使用 level 检查匹配 SMACross.generate_signals 行为） ──
        # SMACross 使用 groupby+sort 后的连续 close 序列计算 SMA。
        # 矩阵中 suspended 日 close=NaN 会导致 rolling window 中断，
        # 必须先 ffill 以匹配旧路径行为（旧路径只含有效交易日行）。
        close_filled = pd.DataFrame(mx.close).ffill().to_numpy(dtype=float)
        if self._ma_type == "EMA":
            fast_ma_filled = pd.DataFrame(close_filled).ewm(span=self._fast, adjust=False).mean().values
            slow_ma_filled = pd.DataFrame(close_filled).ewm(span=self._slow, adjust=False).mean().values
        else:
            fast_ma_filled = pd.DataFrame(close_filled).rolling(self._fast, min_periods=self._fast).mean().values
            slow_ma_filled = pd.DataFrame(close_filled).rolling(self._slow, min_periods=self._slow).mean().values
        valid_sma = ~np.isnan(fast_ma_filled) & ~np.isnan(slow_ma_filled)
        self._sma_buy_ok = valid_sma & (fast_ma_filled > slow_ma_filled)
        self._sma_sell_ok = valid_sma & (fast_ma_filled < slow_ma_filled)
        self._sma_cand_idx = build_daily_candidate_index(self._sma_buy_ok)
        del close_filled

        # ── RSI 交叉信号矩阵 ──
        rsi = feats.rsi
        rsi_prev = np.full_like(rsi, np.nan)
        rsi_prev[1:, :] = rsi[:-1, :]

        with np.errstate(invalid="ignore"):
            self._rsi_buy = (rsi_prev <= self._mr_rsi_buy_threshold) & (rsi > self._mr_rsi_buy_threshold)
            self._rsi_overbought = (rsi_prev >= self._mr_rsi_sell_threshold) & (rsi < self._mr_rsi_sell_threshold)
        self._rsi_buy[np.isnan(rsi_prev) | np.isnan(rsi)] = False
        self._rsi_overbought[np.isnan(rsi_prev) | np.isnan(rsi)] = False
        self._rsi_cand_idx = build_daily_candidate_index(self._rsi_buy)

        # ── ATR lookup（from raw history，匹配 GenericSignalProvider） ──
        atr_n = 14
        ecfg = exit_cfg
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

        # ── fill hooks 初始化 ──
        self._peak_close_state = {}
        self._mr_symbols = set()
        self._mr_entry_day = {}
        self._mr_entry_price = {}
        self.entry_day = {}
        self.extra_clear_dicts = [self._peak_close_state]
        self.last_sell_day = None
        self.peak_state_on_buy = None

        self.extra_daily_init: dict[str, Any] = {"strong_risk_on": 0}
        self.precompute_seconds = float(_time.perf_counter() - pre_t0)

    # ------------------------------------------------------------------
    # day_signals
    # ------------------------------------------------------------------

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        i = day_idx
        mx = self._mx
        positions = ctx.positions
        position_avg_cost = ctx.position_avg_cost
        close_idx = ctx.close_idx

        # regime 判断: 全局 (1D) 或逐股票 (2D)
        # market_filter 模式下跳过此处计数，由下方 market_filter 分支统一计数
        if self._use_market_filter:
            if self._use_regime_filter:
                regime_row = self._regime_on[i]
                regime_on_global = bool(np.any(regime_row))
            else:
                regime_on_global = bool(self._regime_on[i])
        elif self._use_regime_filter:
            # 2D: 全局 regime 统计用 market gate 日均值
            regime_row = self._regime_on[i]  # (N,) bool
            regime_on_global = bool(np.any(regime_row))
            trend_count = int(np.sum(regime_row))
            mr_count = int(len(regime_row)) - trend_count
            if trend_count >= mr_count:
                self.regime_trend_days += 1
            else:
                self.regime_mr_days += 1
        else:
            regime_on_global = bool(self._regime_on[i])
            if regime_on_global:
                self.regime_trend_days += 1
            else:
                self.regime_mr_days += 1

        positions_before_sell = int(sum(1 for _q in positions.values() if int(_q) > 0))

        # ── Phase 1: 引擎级退出规则（匹配 GenericSignalProvider 行为） ──
        exit_rule_sells, exit_rule_syms, ecounts = evaluate_engine_exits(
            positions=positions,
            day=day,
            close_idx=close_idx,
            position_avg_cost=position_avg_cost,
            peak_state=self._peak_close_state,
            entry_day=self.entry_day,
            exit_cfg=self._ec,
            get_atr=lambda sym, d: (self._atr_lookup.get(sym) or {}).get(d) if self._need_atr else None,
            risk_on=bool(self._risk_on_exits[i]),
            max_hold_days=0,
            atr_stop_k=self._atr_stop_k,
        )
        self.atr_stop_exit_count += ecounts.atr_stop
        self.atr_trail_exit_count += ecounts.atr_trail
        self.take_profit_exit_count += ecounts.take_profit
        self.fixed_stop_loss_exit_count += ecounts.fixed_stop_loss

        sell_sigs: list[Signal] = list(exit_rule_sells)
        buy_sigs: list[Signal] = []

        # ── Phase 2: 策略信号 ──
        _MS_NAMES = ("BULL", "TRANS_DOWN", "TRANS_UP", "BEAR")
        _TM_NAMES = ("TREND_MAIN", "TREND_LIGHT", "NO_TRADE")
        _cur_market_state = ""
        _cur_trade_mode = ""

        if self._use_market_filter:
            # MA200 四态分发
            _ms_val = int(self._market_state[i])
            _tm_val = int(self._trade_mode[i])
            _cur_market_state = _MS_NAMES[_ms_val] if _ms_val < len(_MS_NAMES) else "BULL"
            _cur_trade_mode = _TM_NAMES[_tm_val] if _tm_val < len(_TM_NAMES) else "NO_TRADE"

            # 市场状态分布计数器
            if _ms_val == 0:
                self.market_state_bull_days += 1
            elif _ms_val == 1:
                self.market_state_trans_down_days += 1
            elif _ms_val == 2:
                self.market_state_trans_up_days += 1
            else:
                self.market_state_bear_days += 1

            if _tm_val == 0:
                self.trade_mode_main_days += 1
                self._day_signals_trend(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)
            elif _tm_val == 1:
                self.trade_mode_light_days += 1
                self._day_signals_light(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)
            else:
                self.trade_mode_notrade_days += 1
                self._day_signals_exits_only(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)

            # regime 统计仍然更新（兼容现有逻辑）
            if _tm_val == 2:
                self.regime_mr_days += 1
            else:
                self.regime_trend_days += 1
        elif self._use_regime_filter:
            # 逐股票 regime 路由: 同时运行趋势和 MR 分支
            self._day_signals_perstock(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)
        elif regime_on_global:
            self._day_signals_trend(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)
        else:
            self._day_signals_mr(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)

        # ── 清理已无持仓的 mr_symbols（排除当日新买入等待 fill 的 symbol） ──
        pending_buy_syms = {sig.symbol for sig in buy_sigs if sig.side == Side.BUY}
        to_remove = [
            s for s in self._mr_symbols
            if s not in pending_buy_syms and (s not in positions or int(positions.get(s, 0)) <= 0)
        ]
        for s in to_remove:
            self._mr_symbols.discard(s)
            self._mr_entry_day.pop(s, None)
            self._mr_entry_price.pop(s, None)

        # ── mf_gate / strong_risk_on ──
        strong_risk_on_today = bool(self._strong_risk_on[i])
        mf_gate_on_today = resolve_mf_gate_on_today(
            enable_multifactor_rank=self._enable_multifactor_rank,
            mf_rank_gate_mode=self._mf_rank_gate_mode,
            risk_on_today=True,
            strong_risk_on_today=strong_risk_on_today,
        )

        # 写入 market_state / trade_mode 到 Signal meta
        if self._use_market_filter and _cur_market_state:
            for sig in buy_sigs:
                sig.meta["market_state"] = _cur_market_state
                sig.meta["trade_mode"] = _cur_trade_mode
            for sig in sell_sigs:
                if "market_state" not in sig.meta:
                    sig.meta["market_state"] = _cur_market_state
                    sig.meta["trade_mode"] = _cur_trade_mode

        diagnostics: dict[str, Any] = {
            "positions_before_sell": positions_before_sell,
            "raw_buy_signal_count": len(buy_sigs),
            "buy_candidate_count": len(buy_sigs),
            "after_held_filter_count": len(buy_sigs),
            "market_state": _cur_market_state,
            "trade_mode": _cur_trade_mode,
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

    # ------------------------------------------------------------------
    # 趋势模式分支
    # ------------------------------------------------------------------

    def _day_signals_trend(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        mx = self._mx

        # ── MR 遗留持仓退出（仅 stop_loss + time_exit，不检查 overbought） ──
        for sym in list(self._mr_symbols):
            if sym in exit_rule_syms:
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)
                continue
            qty = int(positions.get(sym, 0))
            if qty <= 0:
                continue

            col = self._sym_to_col.get(sym)
            adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
            entry_px = self._mr_entry_price.get(sym, 0.0)
            sell_reason = ""

            if entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - self._mr_stop_loss_pct):
                sell_reason = "MR_STOP_LOSS"
                self.mr_stop_loss_count += 1
            elif self._mr_max_hold_days > 0 and sym in self._mr_entry_day:
                if (day - self._mr_entry_day[sym]).days >= self._mr_max_hold_days:
                    sell_reason = "MR_TIME_EXIT"
                    self.mr_time_exit_count += 1

            if sell_reason:
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason=sell_reason, reason_code=sell_reason,
                    meta={
                        "triggered_rule": sell_reason,
                        "entry_price": round(entry_px, 6),
                        "held_days": (day - self._mr_entry_day.get(sym, day)).days,
                        "regime_on": True, "signal_mode": "TREND",
                    },
                ))
                exit_rule_syms.add(sym)
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)

        # ── SMA cross_down 卖出（非 MR、非已退出的持仓） ──
        for sym, qty_v in list(positions.items()):
            qty = int(qty_v)
            if qty <= 0 or sym in exit_rule_syms or sym in self._mr_symbols:
                continue
            col = self._sym_to_col.get(sym)
            if col is None:
                continue
            if bool(self._sma_sell_ok[i, col]):
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason=f"{self._ma_type}_CROSS_DOWN",
                    reason_code=f"{self._ma_type}_CROSS_DOWN",
                    meta={"triggered_rule": f"{self._ma_type}_CROSS_DOWN", "regime_on": True, "signal_mode": "TREND"},
                ))

        # ── SMA cross_up 买入（排除 MR 遗留 + 已持仓） ──
        for c in self._sma_cand_idx[i]:
            sym = mx.symbols[int(c)]
            if sym in positions and int(positions[sym]) > 0:
                continue
            if sym in self._mr_symbols:
                continue
            self.total_buy_signals += 1
            buy_sigs.append(Signal(
                signal_date=day, symbol=sym, side=Side.BUY, qty=self._trend_order_size,
                reason=f"{self._ma_type}_CROSS_UP", reason_code=f"{self._ma_type}_CROSS_UP",
                meta={"regime_on": True, "signal_mode": "TREND"},
            ))

    # ------------------------------------------------------------------
    # 均值回归模式分支
    # ------------------------------------------------------------------

    def _day_signals_mr(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        mx = self._mx

        # ── MR 持仓退出（overbought + stop_loss + time_exit） ──
        for sym in list(self._mr_symbols):
            if sym in exit_rule_syms:
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)
                continue
            qty = int(positions.get(sym, 0))
            if qty <= 0:
                continue

            col = self._sym_to_col.get(sym)
            adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
            entry_px = self._mr_entry_price.get(sym, 0.0)
            sell_reason = ""

            if col is not None and bool(self._rsi_overbought[i, col]):
                sell_reason = "MR_RSI_OVERBOUGHT_SELL"
                self.mr_rsi_overbought_sell_count += 1
            elif entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - self._mr_stop_loss_pct):
                sell_reason = "MR_STOP_LOSS"
                self.mr_stop_loss_count += 1
            elif self._mr_max_hold_days > 0 and sym in self._mr_entry_day:
                if (day - self._mr_entry_day[sym]).days >= self._mr_max_hold_days:
                    sell_reason = "MR_TIME_EXIT"
                    self.mr_time_exit_count += 1

            if sell_reason:
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason=sell_reason, reason_code=sell_reason,
                    meta={
                        "triggered_rule": sell_reason,
                        "entry_price": round(entry_px, 6),
                        "held_days": (day - self._mr_entry_day.get(sym, day)).days,
                        "regime_on": False, "signal_mode": "MEAN_REVERT",
                    },
                ))
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)

        # ── RSI oversold 买入 ──
        for c in self._rsi_cand_idx[i]:
            sym = mx.symbols[int(c)]
            if sym in positions and int(positions[sym]) > 0:
                continue
            adj_close = float(mx.close[i, int(c)])
            if np.isnan(adj_close) or adj_close <= 0:
                continue

            self.total_buy_signals += 1
            self.mr_rsi_oversold_buy_count += 1
            self._mr_symbols.add(sym)
            self._mr_entry_day[sym] = day
            self._mr_entry_price[sym] = adj_close

            rsi_val = float(self._feats.rsi[i, int(c)]) if not np.isnan(self._feats.rsi[i, int(c)]) else None
            buy_sigs.append(Signal(
                signal_date=day, symbol=sym, side=Side.BUY, qty=self._mr_order_size,
                reason="MR_RSI_OVERSOLD_BUY", reason_code="MR_RSI_OVERSOLD_BUY",
                meta={
                    "triggered_rule": "MR_RSI_OVERSOLD_BUY",
                    "regime_on": False, "signal_mode": "MEAN_REVERT",
                    "rsi_value": rsi_val,
                    "close": round(adj_close, 6),
                },
            ))

    # ------------------------------------------------------------------
    # 轻趋势模式分支（EMA5/20，MA200 过渡态）
    # ------------------------------------------------------------------

    def _day_signals_light(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        mx = self._mx

        # ── MR 遗留持仓退出（仅 stop_loss + time_exit） ──
        for sym in list(self._mr_symbols):
            if sym in exit_rule_syms:
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)
                continue
            qty = int(positions.get(sym, 0))
            if qty <= 0:
                continue
            col = self._sym_to_col.get(sym)
            adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
            entry_px = self._mr_entry_price.get(sym, 0.0)
            sell_reason = ""
            if entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - self._mr_stop_loss_pct):
                sell_reason = "MR_STOP_LOSS"
                self.mr_stop_loss_count += 1
            elif self._mr_max_hold_days > 0 and sym in self._mr_entry_day:
                if (day - self._mr_entry_day[sym]).days >= self._mr_max_hold_days:
                    sell_reason = "MR_TIME_EXIT"
                    self.mr_time_exit_count += 1
            if sell_reason:
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason=sell_reason, reason_code=sell_reason,
                    meta={"triggered_rule": sell_reason, "entry_price": round(entry_px, 6),
                          "held_days": (day - self._mr_entry_day.get(sym, day)).days,
                          "regime_on": True, "signal_mode": "TREND_LIGHT"},
                ))
                exit_rule_syms.add(sym)
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)

        # ── EMA light cross_down 卖出（非 MR、非已退出的持仓） ──
        for sym, qty_v in list(positions.items()):
            qty = int(qty_v)
            if qty <= 0 or sym in exit_rule_syms or sym in self._mr_symbols:
                continue
            col = self._sym_to_col.get(sym)
            if col is None:
                continue
            if bool(self._ema_light_sell_ok[i, col]):
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason="EMA_LIGHT_CROSS_DOWN", reason_code="EMA_LIGHT_CROSS_DOWN",
                    meta={"triggered_rule": "EMA_LIGHT_CROSS_DOWN", "regime_on": True, "signal_mode": "TREND_LIGHT"},
                ))

        # ── EMA light cross_up 买入 ──
        for c in self._ema_light_cand_idx[i]:
            sym = mx.symbols[int(c)]
            if sym in positions and int(positions[sym]) > 0:
                continue
            if sym in self._mr_symbols:
                continue
            self.total_buy_signals += 1
            buy_sigs.append(Signal(
                signal_date=day, symbol=sym, side=Side.BUY, qty=self._trend_order_size,
                reason="EMA_LIGHT_CROSS_UP", reason_code="EMA_LIGHT_CROSS_UP",
                meta={"regime_on": True, "signal_mode": "TREND_LIGHT"},
            ))

    # ------------------------------------------------------------------
    # NO_TRADE 模式（仅退出规则）
    # ------------------------------------------------------------------

    def _day_signals_exits_only(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        """NO_TRADE 模式：不产生任何买入信号，只处理已有持仓的退出。"""
        mx = self._mx

        # ── MR 遗留持仓退出 ──
        for sym in list(self._mr_symbols):
            if sym in exit_rule_syms:
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)
                continue
            qty = int(positions.get(sym, 0))
            if qty <= 0:
                continue
            col = self._sym_to_col.get(sym)
            adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
            entry_px = self._mr_entry_price.get(sym, 0.0)
            sell_reason = ""
            if entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - self._mr_stop_loss_pct):
                sell_reason = "MR_STOP_LOSS"
                self.mr_stop_loss_count += 1
            elif self._mr_max_hold_days > 0 and sym in self._mr_entry_day:
                if (day - self._mr_entry_day[sym]).days >= self._mr_max_hold_days:
                    sell_reason = "MR_TIME_EXIT"
                    self.mr_time_exit_count += 1
            if sell_reason:
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason=sell_reason, reason_code=sell_reason,
                    meta={"triggered_rule": sell_reason, "entry_price": round(entry_px, 6),
                          "held_days": (day - self._mr_entry_day.get(sym, day)).days,
                          "regime_on": False, "signal_mode": "NO_TRADE"},
                ))
                exit_rule_syms.add(sym)
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)

        # ── SMA/EMA cross_down 卖出（趋势持仓退出） ──
        for sym, qty_v in list(positions.items()):
            qty = int(qty_v)
            if qty <= 0 or sym in exit_rule_syms or sym in self._mr_symbols:
                continue
            col = self._sym_to_col.get(sym)
            if col is None:
                continue
            if bool(self._sma_sell_ok[i, col]):
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason=f"{self._ma_type}_CROSS_DOWN",
                    reason_code=f"{self._ma_type}_CROSS_DOWN",
                    meta={"triggered_rule": f"{self._ma_type}_CROSS_DOWN", "signal_mode": "NO_TRADE"},
                ))

        # 不产生任何买入信号

    # ------------------------------------------------------------------
    # 逐股票 regime 路由分支（RegimeFilter 启用时）
    # ------------------------------------------------------------------

    def _day_signals_perstock(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        """当 RegimeFilter 启用时，逐股票路由趋势/MR 信号。

        退出逻辑不受 regime 状态影响（保持现有行为）。
        买入候选按逐股票 regime_on[i, col] 过滤：
        - regime_on[i, col] == True → SMA 趋势买入
        - regime_on[i, col] == False → RSI MR 买入
        """
        mx = self._mx
        regime_row = self._regime_on[i]  # (N,) bool

        # ── MR 遗留持仓退出（统一处理: overbought + stop_loss + time_exit） ──
        for sym in list(self._mr_symbols):
            if sym in exit_rule_syms:
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)
                continue
            qty = int(positions.get(sym, 0))
            if qty <= 0:
                continue

            col = self._sym_to_col.get(sym)
            adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
            entry_px = self._mr_entry_price.get(sym, 0.0)
            sell_reason = ""

            # overbought 检查（不论当前 regime）
            if col is not None and bool(self._rsi_overbought[i, col]):
                sell_reason = "MR_RSI_OVERBOUGHT_SELL"
                self.mr_rsi_overbought_sell_count += 1
            elif entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - self._mr_stop_loss_pct):
                sell_reason = "MR_STOP_LOSS"
                self.mr_stop_loss_count += 1
            elif self._mr_max_hold_days > 0 and sym in self._mr_entry_day:
                if (day - self._mr_entry_day[sym]).days >= self._mr_max_hold_days:
                    sell_reason = "MR_TIME_EXIT"
                    self.mr_time_exit_count += 1

            if sell_reason:
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason=sell_reason, reason_code=sell_reason,
                    meta={
                        "triggered_rule": sell_reason,
                        "entry_price": round(entry_px, 6),
                        "held_days": (day - self._mr_entry_day.get(sym, day)).days,
                        "regime_on": False, "signal_mode": "MEAN_REVERT",
                    },
                ))
                exit_rule_syms.add(sym)
                self._mr_symbols.discard(sym)
                self._mr_entry_day.pop(sym, None)
                self._mr_entry_price.pop(sym, None)

        # ── SMA cross_down 卖出（非 MR、非已退出的持仓, 不受 regime 影响） ──
        for sym, qty_v in list(positions.items()):
            qty = int(qty_v)
            if qty <= 0 or sym in exit_rule_syms or sym in self._mr_symbols:
                continue
            col = self._sym_to_col.get(sym)
            if col is None:
                continue
            if bool(self._sma_sell_ok[i, col]):
                sell_sigs.append(Signal(
                    signal_date=day, symbol=sym, side=Side.SELL, qty=qty,
                    reason=f"{self._ma_type}_CROSS_DOWN",
                    reason_code=f"{self._ma_type}_CROSS_DOWN",
                    meta={"triggered_rule": f"{self._ma_type}_CROSS_DOWN", "signal_mode": "TREND"},
                ))

        # ── SMA cross_up 买入（仅 regime_on == True 的股票） ──
        for c in self._sma_cand_idx[i]:
            col = int(c)
            sym = mx.symbols[col]
            if sym in positions and int(positions[sym]) > 0:
                continue
            if sym in self._mr_symbols:
                continue
            if not bool(regime_row[col]):
                continue  # 该股票不在趋势 regime
            self.total_buy_signals += 1
            buy_sigs.append(Signal(
                signal_date=day, symbol=sym, side=Side.BUY, qty=self._trend_order_size,
                reason=f"{self._ma_type}_CROSS_UP", reason_code=f"{self._ma_type}_CROSS_UP",
                meta={"regime_on": True, "signal_mode": "TREND"},
            ))

        # ── RSI oversold 买入（仅 regime_on == False 的股票） ──
        for c in self._rsi_cand_idx[i]:
            col = int(c)
            sym = mx.symbols[col]
            if sym in positions and int(positions[sym]) > 0:
                continue
            if bool(regime_row[col]):
                continue  # 该股票在趋势 regime，不走 MR
            adj_close = float(mx.close[i, col])
            if np.isnan(adj_close) or adj_close <= 0:
                continue

            self.total_buy_signals += 1
            self.mr_rsi_oversold_buy_count += 1
            self._mr_symbols.add(sym)
            self._mr_entry_day[sym] = day
            self._mr_entry_price[sym] = adj_close

            rsi_val = float(self._feats.rsi[i, col]) if not np.isnan(self._feats.rsi[i, col]) else None
            buy_sigs.append(Signal(
                signal_date=day, symbol=sym, side=Side.BUY, qty=self._mr_order_size,
                reason="MR_RSI_OVERSOLD_BUY", reason_code="MR_RSI_OVERSOLD_BUY",
                meta={
                    "triggered_rule": "MR_RSI_OVERSOLD_BUY",
                    "regime_on": False, "signal_mode": "MEAN_REVERT",
                    "rsi_value": rsi_val,
                    "close": round(adj_close, 6),
                },
            ))
