from __future__ import annotations

import json
import time
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import BenchmarkRegimeConfig
from backend.core.config.models import CostConfig
from backend.core.config.models import MarketFilterConfig
from backend.core.core.models import Position
from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.candidate_index import build_daily_candidate_index
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.features import compute_feature_matrices
from backend.core.engine_vector.signal_matrix import build_signal_matrices
from backend.core.portfolio.portfolio_builder import (
    PortfolioBacktestResult,
    _compute_metrics,
    build_backtest_price_indices,
    build_rebalance_orders,
    calc_buy_slots,
    compute_nav_snapshot,
    resolve_mf_gate_on_today,
)
from backend.core.strategies.breakout_trend import BreakoutTrendStrategy
from backend.core.strategies.composite_strategy import CompositeStrategy
from backend.core.strategies.ema_cross import EMACrossStrategy
from backend.core.strategies.regime_router import RegimeRouter
from backend.core.strategies.sma_cross import SMACrossStrategy


def _resolve_runtime_route_id(strategy: Any) -> str:
    if isinstance(strategy, BreakoutTrendStrategy):
        return "provider_breakout_runtime"
    if isinstance(strategy, CompositeStrategy):
        return "generic_inline_runtime"
    if isinstance(strategy, (SMACrossStrategy, EMACrossStrategy, RegimeRouter)):
        return "strict_inline_runtime"
    return "strict_inline_runtime"

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
    volume: np.ndarray,
    bench_close: np.ndarray,
) -> dict[str, float]:
    """3-factor momentum scoring: mean(roc20, roc60, roc120).

    Uses adjusted close (后复权) for return computation.
    If any factor has insufficient data, uses available factors via nanmean.
    """
    if int(len(day_cands)) < 5:
        return {str(symbols[int(c)]): 0.5 for c in day_cands}
    scores: dict[str, float] = {}
    for c in day_cands:
        col = int(c)
        sym = str(symbols[col])
        c_now = float(close[i, col]) if not np.isnan(close[i, col]) else np.nan
        # roc20
        c_20 = float(close[i - 20, col]) if i - 20 >= 0 and not np.isnan(close[i - 20, col]) else np.nan
        roc20 = (c_now / c_20 - 1.0) if (not np.isnan(c_now) and not np.isnan(c_20) and c_20 > 0) else np.nan
        # roc60
        c_60 = float(close[i - 60, col]) if i - 60 >= 0 and not np.isnan(close[i - 60, col]) else np.nan
        roc60 = (c_now / c_60 - 1.0) if (not np.isnan(c_now) and not np.isnan(c_60) and c_60 > 0) else np.nan
        # roc120
        c_120 = float(close[i - 120, col]) if i - 120 >= 0 and not np.isnan(close[i - 120, col]) else np.nan
        roc120 = (c_now / c_120 - 1.0) if (not np.isnan(c_now) and not np.isnan(c_120) and c_120 > 0) else np.nan
        # composite score: nanmean of available factors
        factors = [roc20, roc60, roc120]
        score = float(np.nanmean(factors))
        scores[sym] = score if not np.isnan(score) else 0.0
    return scores


def run_vector_portfolio_backtest_strict(
    *,
    strategy: Any,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    trading_days: list[date],
    benchmark_symbol: str,
    initial_cash: float,
    max_positions: int,
    lot_size: int,
    enable_strength_rank: bool = False,
    strength_ma: int = 120,
    strength_top_k_mode: str = "FILL_TO_MAX",
    history_lookback_days: int | None = None,
    fast_mode: bool = False,
    collect_decision_diff: bool = False,
    debug_first_divergence: bool = False,
    enable_multifactor_rank: bool = False,
    mf_topk: int = 10,
    mf_concentrate_topn: int = 3,
    mf_concentrate_scale: float = 1.5,
    mf_rank_gate_mode: str = "ALWAYS_ON",
    momentum_top_pct: float = 0.0,
    cost_cfg: CostConfig | None = None,
    raw_history: pd.DataFrame | None = None,
    # 以下参数由 portfolio_builder 透传，当前引擎从 strategy 对象读取对应值
    exit_cfg: Any = None,
    risk_cfg: Any = None,
    sizing_cfg: Any = None,
    base_order_value: float = 0.0,
    st_history: Any = None,
    sector_data: Any = None,
    industry_map: Any = None,
    industry_history: Any = None,
    risk_budget_cfg: Any = None,
    market_filter_cfg: Any = None,
    benchmark_regime_cfg: Any = None,
    breadth_cfg: Any = None,
) -> PortfolioBacktestResult:
    route_id = _resolve_runtime_route_id(strategy)

    if route_id == "provider_breakout_runtime":
        return _run_vector_portfolio_backtest_breakout(
            strategy=strategy,
            history=history,
            benchmark=benchmark,
            trading_days=trading_days,
            initial_cash=initial_cash,
            max_positions=max_positions,
            lot_size=lot_size,
            enable_strength_rank=enable_strength_rank,
            strength_ma=strength_ma,
            strength_top_k_mode=strength_top_k_mode,
            fast_mode=fast_mode,
            enable_multifactor_rank=enable_multifactor_rank,
            mf_topk=mf_topk,
            mf_concentrate_topn=mf_concentrate_topn,
            mf_concentrate_scale=mf_concentrate_scale,
            mf_rank_gate_mode=mf_rank_gate_mode,
            momentum_top_pct=momentum_top_pct,
            cost_cfg=cost_cfg,
            raw_history=raw_history,
            exit_cfg=exit_cfg,
            st_history=st_history,
            sector_data=sector_data,
            industry_map=industry_map,
            industry_history=industry_history,
            risk_budget_cfg=risk_budget_cfg,
            sizing_cfg=sizing_cfg,
            market_filter_cfg=market_filter_cfg,
            benchmark_regime_cfg=benchmark_regime_cfg,
        )

    if route_id == "generic_inline_runtime":
        return _run_vector_portfolio_backtest_generic_signals(
            strategy=strategy,
            history=history,
            benchmark=benchmark,
            trading_days=trading_days,
            initial_cash=initial_cash,
            max_positions=max_positions,
            lot_size=lot_size,
            enable_strength_rank=enable_strength_rank,
            strength_ma=strength_ma,
            strength_top_k_mode=strength_top_k_mode,
            history_lookback_days=history_lookback_days,
            fast_mode=fast_mode,
            debug_first_divergence=debug_first_divergence,
            enable_multifactor_rank=enable_multifactor_rank,
            mf_topk=mf_topk,
            mf_concentrate_topn=mf_concentrate_topn,
            mf_concentrate_scale=mf_concentrate_scale,
            mf_rank_gate_mode=mf_rank_gate_mode,
            momentum_top_pct=momentum_top_pct,
            cost_cfg=cost_cfg,
            raw_history=raw_history,
            sector_data=sector_data,
            industry_map=industry_map,
            industry_history=industry_history,
        )

    if history.empty:
        raise ValueError("history is empty")
    if not trading_days:
        raise ValueError("trading_days is empty")

    pre_t0 = time.perf_counter()
    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    _uf = dict(getattr(strategy, "state", {}).get("universe_filters") or {})
    _min_price = float(_uf.get("min_price", getattr(strategy, "min_price", 0.0)) or 0.0)
    _min_trade_price = float(_min_price)
    _min_list_days = int(_uf.get("min_list_days", 0) or 0)
    _min_avg_turnover_20d = float(_uf.get("min_avg_turnover_20d", 0.0) or 0.0)
    _membership_history = getattr(strategy, "state", {}).get("membership_history")
    mx = build_ohlc_matrices_from_history(
        hist,
        trading_days,
        st_history=st_history,
        membership_history=_membership_history,
        min_price=_min_price,
        min_list_days=_min_list_days,
        min_avg_turnover_20d=_min_avg_turnover_20d,
    )
    t, n = mx.close.shape
    if n == 0:
        raise ValueError("history has no symbols")

    fast = int(getattr(strategy, "fast", 5))
    slow = int(getattr(strategy, "slow", 20))
    trend_fast = int(getattr(strategy, "trend_fast_ma", 120))
    trend_slow = int(getattr(strategy, "trend_slow_ma", 200))
    enable_trend_slope_filter = bool(getattr(strategy, "enable_trend_slope_filter", False))
    slope_lookback = int(getattr(strategy, "slope_lookback", 5))
    enable_trend_continuity_filter = bool(getattr(strategy, "enable_trend_continuity_filter", False))
    continuity_n = int(getattr(strategy, "continuity_n", 10))
    atr_n = int(getattr(strategy, "atr_n", 14))
    entry_buffer = float(getattr(strategy, "entry_buffer", 0.0))
    enable_trend_filter = bool(getattr(strategy, "enable_trend_filter", False))
    enable_trend_tier = bool(getattr(strategy, "enable_trend_tier", True))
    enable_trend_accel = bool(getattr(strategy, "enable_trend_accel", True))
    enable_trend_break_exit = bool(getattr(strategy, "enable_trend_break_exit", True))
    trend_break_confirm_days = int(getattr(strategy, "trend_break_confirm_days", 3))
    trend_break_confirm_gap_pct = float(getattr(strategy, "trend_break_confirm_gap_pct", 0.0))
    trend_break_use_benchmark_regime = bool(getattr(strategy, "trend_break_use_benchmark_regime", False))
    weak_trend_order_scale = float(getattr(strategy, "weak_trend_order_scale", 0.5))
    strong_trend_order_scale = float(getattr(strategy, "strong_trend_order_scale", 1.0))
    enable_atr_stop = bool(getattr(strategy, "enable_atr_stop", False))
    enable_atr_trail = bool(getattr(strategy, "enable_atr_trail", False))
    atr_stop_k = float(getattr(strategy, "atr_stop_k", 2.0))
    atr_trail_k = float(getattr(strategy, "atr_trail_k", 3.0))
    trailing_activate_profit_pct = float(getattr(strategy, "trailing_activate_profit_pct", 0.0) or 0.0)
    enable_take_profit = bool(getattr(strategy, "enable_take_profit", False))
    take_profit_mode = str(getattr(strategy, "take_profit_mode", "pct"))
    take_profit_pct = float(getattr(strategy, "take_profit_pct", 0.10))
    take_profit_atr_k = float(getattr(strategy, "take_profit_atr_k", 3.0))
    enable_fixed_stop_loss = bool(getattr(strategy, "enable_fixed_stop_loss", False))
    fixed_stop_loss_pct = float(getattr(strategy, "fixed_stop_loss_pct", 0.05))
    max_hold_days = int(getattr(strategy, "max_hold_days", 0))
    enable_ma20_exit = bool(getattr(strategy, "enable_ma20_exit", False))
    enable_low10_exit = bool(getattr(strategy, "enable_low10_exit", False))
    order_size = int(getattr(strategy, "order_size", 1000))
    regime_ma = int(getattr(strategy, "regime_ma", 60))
    enable_v2_trend_filter = bool(getattr(strategy, "enable_v2_trend_filter", False))
    v2_trend_short_ma = int(getattr(strategy, "v2_trend_short_ma", 20))
    v2_trend_long_ma = int(getattr(strategy, "v2_trend_long_ma", 60))
    # DD circuit breaker
    from backend.core.config.models import RiskBudgetConfig
    _rbc = risk_budget_cfg if isinstance(risk_budget_cfg, RiskBudgetConfig) else RiskBudgetConfig()
    enable_dd_breaker = bool(_rbc.enabled)
    dd_reduce_pct = float(_rbc.dd_reduce_pct)
    dd_reduce_scale = float(_rbc.dd_reduce_scale)
    # Portfolio sizing
    from backend.core.config.models import SizingConfig
    _sc = sizing_cfg if isinstance(sizing_cfg, SizingConfig) else SizingConfig()
    weight_mode = str(_sc.weight_mode or "equal")
    min_positions = int(_sc.min_positions)
    tilt_strength = float(_sc.tilt_strength)
    tilt_top_n = int(_sc.tilt_top_n)
    tilt_bottom_n = int(_sc.tilt_bottom_n)
    score_weight_min_scale = float(_sc.score_weight_min_scale)
    score_weight_max_scale = float(_sc.score_weight_max_scale)
    candidate_plan_mode = str(_sc.candidate_plan_mode or "ranked")
    cash_aware_search_top_n = int(_sc.cash_aware_search_top_n)
    rotation_replace_enabled = bool(_sc.rotation_replace_enabled)
    rotation_replace_only_strong_risk_on = bool(_sc.rotation_replace_only_strong_risk_on)
    rotation_replace_max_swaps_per_day = int(_sc.rotation_replace_max_swaps_per_day)
    rotation_replace_candidate_top_n = int(_sc.rotation_replace_candidate_top_n)
    rotation_replace_min_score_gap = float(_sc.rotation_replace_min_score_gap)

    feats = compute_feature_matrices(
        close=mx.close,
        high=mx.high,
        low=mx.low,
        fast=fast,
        slow=slow,
        trend_fast=trend_fast,
        trend_slow=trend_slow,
        atr_n=atr_n,
        strength_ma=int(strength_ma),
        v2_trend_short_ma=v2_trend_short_ma,
        v2_trend_long_ma=v2_trend_long_ma,
    )
    strength = mx.close / feats.strength_ma - 1.0
    strength[np.isnan(feats.strength_ma)] = np.nan

    bench = benchmark.copy()
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.sort_values("date")
    bench_close_s = pd.to_numeric(bench["close"], errors="coerce")
    bench_ma_s = bench_close_s.rolling(regime_ma, min_periods=regime_ma).mean()
    bmap_close = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_close_s)}
    bmap_ma = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma_s)}
    bench_close = np.array([bmap_close.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
    bench_ma = np.array([bmap_ma.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
    risk_on = np.ones(t, dtype=bool)
    valid_bench = ~np.isnan(bench_close) & ~np.isnan(bench_ma)
    risk_on[valid_bench] = bench_close[valid_bench] > bench_ma[valid_bench]
    bench_ma120_s = bench_close_s.rolling(120, min_periods=120).mean()
    bench_ma200_s = bench_close_s.rolling(200, min_periods=200).mean()
    bmap_ma120 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma120_s)}
    bmap_ma200 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma200_s)}
    bench_ma120 = np.array([bmap_ma120.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
    bench_ma200 = np.array([bmap_ma200.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
    strong_risk_on = np.zeros(t, dtype=bool)
    valid_strong = ~np.isnan(bench_ma120) & ~np.isnan(bench_ma200)
    strong_risk_on[valid_strong] = bench_ma120[valid_strong] > bench_ma200[valid_strong]

    sig_m = build_signal_matrices(
        close=mx.close,
        fast_ma=feats.fast_ma,
        slow_ma=feats.slow_ma,
        trend_fast_ma=feats.trend_fast_ma,
        trend_slow_ma=feats.trend_slow_ma,
        tradable=mx.tradable,
        entry_buffer=entry_buffer,
        enable_trend_filter=enable_trend_filter,
        enable_trend_tier=enable_trend_tier,
        enable_trend_slope_filter=enable_trend_slope_filter,
        slope_lookback=slope_lookback,
        enable_trend_continuity_filter=enable_trend_continuity_filter,
        continuity_n=continuity_n,
        risk_on=risk_on,
        sma20=feats.sma20 if enable_v2_trend_filter else None,
        sma60=feats.sma60 if enable_v2_trend_filter else None,
    )
    # ── Sector gate: top N% industries by 60d return ──
    _enable_sector_gate = bool(getattr(strategy, "enable_sector_gate", False))
    if _enable_sector_gate and sector_data and industry_map:
        from backend.core.engine_vector.features import compute_sector_eligible
        _sector_eligible = compute_sector_eligible(
            sector_data=sector_data,
            industry_map=industry_map,
            symbols=mx.symbols,
            dates=mx.dates,
            window=int(getattr(strategy, "sector_rank_window", 60)),
            top_pct=float(getattr(strategy, "sector_top_pct", 0.30)),
        )
        sig_m["buy_base"] = sig_m["buy_base"] & _sector_eligible

    cand_idx = build_daily_candidate_index(sig_m["buy_base"])
    precompute_seconds = float(time.perf_counter() - pre_t0)

    # lookup for close/nav snapshots — 成交执行使用不复权价格
    _raw = raw_history if raw_history is not None else history
    _raw_hist = _raw.copy()
    _raw_hist["date"] = pd.to_datetime(_raw_hist["date"])
    _raw_hist["symbol"] = _raw_hist["symbol"].astype(str).str.lower()
    day_list = list(trading_days)
    open_idx, close_idx = build_backtest_price_indices(
        history=_raw_hist,
        trading_days=day_list,
    )
    del _raw_hist
    sym_to_col = {s: i for i, s in enumerate(mx.symbols)}

    sim_t0 = time.perf_counter()
    pending: dict[date, list[dict[str, Any]]] = {}
    positions: dict[str, int] = {}
    position_avg_cost: dict[str, float] = {}
    position_avg_cost_adj: dict[str, float] = {}  # 后复权 entry price for exit checks
    peak_close_state: dict[str, float] = {}
    break_streak_state: dict[str, int] = {}
    position_entry_day: dict[str, int] = {}
    cash = float(initial_cash)
    peak_nav = float(initial_cash)
    prev_nav = float(initial_cash)
    blocked_by_trend_count = 0
    total_buy_signals = 0
    trend_slope_block_count = 0
    trend_continuity_block_count = 0
    scan_all_symbols_count = 0
    cand_index_access_count = 0
    diag_reason_counts: dict[str, int] = {}
    exit_take_profit_count = 0
    exit_fixed_stop_count = 0
    exit_atr_stop_count = 0
    exit_atr_trail_count = 0
    exit_time_exit_count = 0
    exit_signal_count = 0
    exit_ma20_count = 0
    exit_low10_count = 0

    _cc = cost_cfg if cost_cfg is not None else CostConfig()
    _slip_bps = _cc.slippage_bps / 10000.0
    _comm_rate = _cc.commission_rate
    _comm_min = _cc.commission_min
    _stamp_rate = _cc.stamp_tax_rate

    trade_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    debug_trace: dict[str, Any] = {}
    day_list = list(trading_days)

    for i, day in enumerate(day_list):
        traded_value = 0.0
        # t open fills
        for od in pending.pop(day, []):
            px = float(open_idx.get((day, od["symbol"]), 0.0) or 0.0)
            if px <= 0:
                continue
            if od["side"] == Side.SELL:
                held = int(positions.get(od["symbol"], 0))
                qty = min(held, int(od["qty"]))
                if qty <= 0:
                    continue
                risk_off_partial_state = getattr(provider, "_risk_off_partial_state", None)
                fill_px = px * (1.0 - _slip_bps)
                gross = qty * fill_px
                comm = max(_comm_min, gross * _comm_rate)
                stax = gross * _stamp_rate
                net = gross - comm - stax
                cash += net
                traded_value += gross
                positions[od["symbol"]] = held - qty
                if positions[od["symbol"]] <= 0:
                    positions.pop(od["symbol"], None)
                    position_avg_cost.pop(od["symbol"], None)
                    position_avg_cost_adj.pop(od["symbol"], None)
                    peak_close_state.pop(od["symbol"], None)
                    break_streak_state.pop(od["symbol"], None)
                    position_entry_day.pop(od["symbol"], None)
                trade_rows.append(
                    {
                        "date": day.isoformat(),
                        "symbol": od["symbol"],
                        "side": "SELL",
                        "price": px,
                        "fill_price": round(fill_px, 4),
                        "qty": qty,
                        "value": round(gross, 2),
                        "commission": round(comm, 2),
                        "stamp_tax": round(stax, 2),
                        "slippage": round(abs(fill_px - px) * qty, 2),
                        "net_amount": round(net, 2),
                        "reason_code": od["reason_code"],
                        "triggered_rule": str((od.get("meta") or {}).get("triggered_rule", "")),
                        "break_streak": int((od.get("meta") or {}).get("break_streak", 0) or 0),
                        "meta_json": json.dumps(od.get("meta") or {}, ensure_ascii=False),
                    }
                )
            else:
                if _min_trade_price > 0 and px < _min_trade_price:
                    continue
                qty = int(od["qty"])
                fill_px = px * (1.0 + _slip_bps)
                gross = qty * fill_px
                comm = max(_comm_min, gross * _comm_rate)
                net = gross + comm
                if qty <= 0 or net > cash:
                    continue
                cash -= net
                traded_value += gross
                prev_qty = int(positions.get(od["symbol"], 0))
                prev_avg = float(position_avg_cost.get(od["symbol"], 0.0))
                new_qty = prev_qty + qty
                new_avg = ((prev_qty * prev_avg) + (qty * fill_px)) / float(new_qty) if new_qty > 0 else 0.0
                positions[od["symbol"]] = new_qty
                position_avg_cost[od["symbol"]] = float(new_avg)
                # 计算后复权成本价：raw_fill * (adj_close / raw_close) 得到同比例尺
                _col_idx = sym_to_col.get(od["symbol"], -1)
                _raw_close_fill = float(close_idx.get((day, od["symbol"]), 0.0) or 0.0)
                if _col_idx >= 0 and _raw_close_fill > 0 and i < t and not np.isnan(mx.close[i, _col_idx]):
                    _adj_factor = float(mx.close[i, _col_idx]) / _raw_close_fill
                else:
                    _adj_factor = 1.0
                _adj_fill_px = fill_px * _adj_factor
                _prev_adj_avg = float(position_avg_cost_adj.get(od["symbol"], 0.0))
                position_avg_cost_adj[od["symbol"]] = float(
                    ((prev_qty * _prev_adj_avg) + (qty * _adj_fill_px)) / float(new_qty)
                ) if new_qty > 0 else 0.0
                # peak 使用后复权价（与 cclose/atr_v 同尺度）
                _adj_close_init = float(mx.close[i, _col_idx]) if (_col_idx >= 0 and i < t and not np.isnan(mx.close[i, _col_idx])) else float(close_idx.get((day, od["symbol"]), px))
                peak_close_state.setdefault(od["symbol"], _adj_close_init)
                if prev_qty == 0:
                    position_entry_day[od["symbol"]] = i
                trade_rows.append(
                    {
                        "date": day.isoformat(),
                        "symbol": od["symbol"],
                        "side": "BUY",
                        "price": px,
                        "fill_price": round(fill_px, 4),
                        "qty": qty,
                        "value": round(gross, 2),
                        "commission": round(comm, 2),
                        "stamp_tax": 0.0,
                        "slippage": round(abs(fill_px - px) * qty, 2),
                        "net_amount": round(net, 2),
                        "reason_code": od["reason_code"],
                        "triggered_rule": str((od.get("meta") or {}).get("triggered_rule", "")),
                        "break_streak": int((od.get("meta") or {}).get("break_streak", 0) or 0),
                        "meta_json": json.dumps(od.get("meta") or {}, ensure_ascii=False),
                    }
                )

        nav, market_value, pos_values = compute_nav_snapshot(cash=cash, positions=positions, close_idx=close_idx, day=day)
        peak_nav = max(peak_nav, nav)
        daily_ret = (nav / prev_nav - 1.0) if prev_nav > 0 else 0.0
        drawdown = (nav / peak_nav - 1.0) if peak_nav > 0 else 0.0
        # DD risk control: DD > threshold → reduce positions
        dd_abs = abs(drawdown)
        if enable_dd_breaker and dd_abs >= dd_reduce_pct:
            effective_max_positions = max(1, int(max_positions * dd_reduce_scale))
            dd_state = "REDUCED"
        else:
            effective_max_positions = int(max_positions)
            dd_state = "NORMAL"
        gross_exposure = (market_value / nav) if nav > 0 else 0.0
        turnover_pct = (traded_value / prev_nav) if prev_nav > 0 else 0.0
        top5 = [{"symbol": s, "value": round(v, 2)} for s, v in sorted(pos_values, key=lambda x: x[1], reverse=True)[:5]]
        daily_rows.append(
            {
                "date": day.isoformat(),
                "nav": nav,
                "cash": cash,
                "positions_count": len(positions),
                "positions_count_end_of_day": len(positions),
                "daily_return": daily_ret,
                "drawdown": drawdown,
                "gross_exposure": gross_exposure,
                "turnover_pct": turnover_pct,
                "top5_positions_json": json.dumps(top5, ensure_ascii=False),
                "candidates_count": 0,
                "selected_count": 0,
                "top5_selected_strength_json": "[]",
                "top5_rejected_strength_json": "[]",
                "buy_slots_before_buy": 0,
                "buy_slots_after_sell": 0,
                "raw_buy_signal_count": 0,
                "buy_candidate_count": 0,
                "after_held_filter_count": 0,
                "after_slot_filter_count": 0,
                "after_cash_lot_count": 0,
                "positions_before_sell": 0,
                "sells_executed_count": 0,
                "positions_after_sell": 0,
                "buy_slots_calculated": 0,
                "candidates_after_held_filter_count": 0,
                "sorting_triggered": False,
                "mean_order_value_scale": 0.0,
                "weak_trend_buy_rate": 0.0,
                "strong_trend_buy_rate": 0.0,
                "mf_rank_applied": 0,
                "mf_gate_on": 0,
                "trend_slope_block_count": 0,
                "trend_continuity_block_count": 0,
                "base_trend_on_rate": 0.0,
                "quality_trend_on_rate": 0.0,
                "effective_max_positions": int(effective_max_positions),
                "dd_state": dd_state,
            }
        )
        prev_nav = nav
        if i >= t - 1:
            # No t+1 open available on the last bar, but slot diagnostics should still
            # follow the same identity to avoid false zero-slot anomalies.
            pos_cnt_eod = int(sum(1 for _s, _q in positions.items() if int(_q) > 0))
            buy_slots_eod = int(calc_buy_slots(int(effective_max_positions), int(pos_cnt_eod)))
            daily_rows[-1]["positions_before_sell"] = int(pos_cnt_eod)
            daily_rows[-1]["positions_after_sell"] = int(pos_cnt_eod)
            daily_rows[-1]["buy_slots_before_buy"] = int(buy_slots_eod)
            daily_rows[-1]["buy_slots_after_sell"] = int(buy_slots_eod)
            daily_rows[-1]["buy_slots_calculated"] = int(buy_slots_eod)
            continue

        # held-only SELL (risk_off > confirmed_trend_break > atr_stop > atr_trail > cross_down)
        sell_sigs: list[Signal] = []
        positions_before_sell = int(sum(1 for _s, _q in positions.items() if int(_q) > 0))
        held_syms = [s for s, q in positions.items() if int(q) > 0]
        held_cols = [sym_to_col[s] for s in held_syms if s in sym_to_col]
        for c in held_cols:
            sym = mx.symbols[c]
            qty = int(positions.get(sym, 0))
            if qty <= 0:
                continue
            cclose = float(mx.close[i, c]) if not np.isnan(mx.close[i, c]) else np.nan
            # peak update at decision close
            peak_close_state[sym] = max(float(peak_close_state.get(sym, cclose)), cclose)
            atr_v = float(feats.atr14[i, c]) if not np.isnan(feats.atr14[i, c]) else None
            trend_fast_v = float(feats.trend_fast_ma[i, c]) if not np.isnan(feats.trend_fast_ma[i, c]) else None
            trend_slow_v = float(feats.trend_slow_ma[i, c]) if not np.isnan(feats.trend_slow_ma[i, c]) else None
            strong_trend = bool(
                trend_fast_v is not None
                and trend_slow_v is not None
                and trend_fast_v > trend_slow_v
            )
            trend_tier = "STRONG" if strong_trend else "WEAK"
            break_t = not strong_trend
            if break_t:
                break_streak_state[sym] = int(break_streak_state.get(sym, 0)) + 1
            else:
                break_streak_state[sym] = 0
            break_streak = int(break_streak_state.get(sym, 0))
            gap_ok = True
            if float(trend_break_confirm_gap_pct) > 0:
                if trend_slow_v is None or trend_slow_v == 0 or trend_fast_v is None:
                    gap_ok = False
                else:
                    gap_ok = ((trend_slow_v - trend_fast_v) / trend_slow_v) >= float(trend_break_confirm_gap_pct)
            regime_gate_ok = True
            if bool(trend_break_use_benchmark_regime):
                regime_gate_ok = bool(risk_on[i])
            confirmed_break = (
                bool(enable_trend_break_exit)
                and break_t
                and break_streak >= int(max(1, trend_break_confirm_days))
                and gap_ok
                and regime_gate_ok
            )
            # exit priority: risk_off > trend_break > atr_stop > fixed_stop > atr_trail > take_profit > time_exit > signal
            # 价格尺度：position_avg_cost = 不复权, position_avg_cost_adj = 后复权(与 cclose/atr_v 同尺度)
            _entry_px = float(position_avg_cost.get(sym, 0.0))
            _entry_adj = float(position_avg_cost_adj.get(sym, 0.0))
            _hold_days = i - position_entry_day.get(sym, i)
            # 不复权收益率（用于百分比止盈/止损）
            _raw_close_v = float(close_idx.get((day, sym), 0.0) or 0.0)
            _pnl_pct = (_raw_close_v / _entry_px - 1.0) if (_entry_px > 0 and _raw_close_v > 0) else 0.0
            reason = ""
            if not bool(risk_on[i]):
                reason = "RISK_OFF_EXIT"
            elif confirmed_break:
                reason = "TREND_BREAK_EXIT"
            elif enable_atr_stop and atr_v is not None and _entry_adj > 0 and cclose <= _entry_adj - atr_stop_k * atr_v:
                reason = "ATR_STOP_LOSS"
            elif enable_fixed_stop_loss and _entry_px > 0 and _pnl_pct <= -fixed_stop_loss_pct:
                reason = "FIXED_STOP_LOSS"
            elif (
                enable_atr_trail
                and atr_v is not None
                and (trailing_activate_profit_pct <= 0.0 or _pnl_pct >= trailing_activate_profit_pct)
                and cclose <= float(peak_close_state.get(sym, cclose) - atr_trail_k * atr_v)
            ):
                reason = "ATR_TRAIL_EXIT"
            elif enable_take_profit and _entry_px > 0 and (
                (take_profit_mode == "atr" and atr_v is not None and _entry_adj > 0 and cclose >= _entry_adj + take_profit_atr_k * atr_v)
                or (take_profit_mode != "atr" and _pnl_pct >= take_profit_pct)
            ):
                reason = "TAKE_PROFIT"
            elif enable_ma20_exit and not np.isnan(feats.sma20[i, c]) and cclose < feats.sma20[i, c]:
                reason = "TREND_EXIT_MA20"
            elif enable_low10_exit and not np.isnan(feats.low_min10[i, c]) and cclose < feats.low_min10[i, c]:
                reason = "TREND_EXIT_LOW10"
            elif max_hold_days > 0 and _hold_days >= max_hold_days:
                reason = "TIME_EXIT"
            elif bool(sig_m["cross_down"][i, c]):
                reason = "SMA_CROSS_DOWN"
            if reason:
                if reason == "TAKE_PROFIT":
                    exit_take_profit_count += 1
                elif reason == "FIXED_STOP_LOSS":
                    exit_fixed_stop_count += 1
                elif reason == "ATR_STOP_LOSS":
                    exit_atr_stop_count += 1
                elif reason == "ATR_TRAIL_EXIT":
                    exit_atr_trail_count += 1
                elif reason == "TREND_EXIT_MA20":
                    exit_ma20_count += 1
                elif reason == "TREND_EXIT_LOW10":
                    exit_low10_count += 1
                elif reason == "TIME_EXIT":
                    exit_time_exit_count += 1
                elif reason == "SMA_CROSS_DOWN":
                    exit_signal_count += 1
                sell_sigs.append(
                    Signal(
                        signal_date=day,
                        symbol=sym,
                        side=Side.SELL,
                        qty=qty,
                        reason=reason,
                        reason_code=reason,
                        meta={
                            "close": cclose,
                            "raw_close": _raw_close_v,
                            "atr_last": atr_v,
                            "entry_price": _entry_px,
                            "entry_price_adj": _entry_adj,
                            "pnl_pct": round(_pnl_pct, 6),
                            "peak_close": float(peak_close_state.get(sym, cclose)),
                            "stop_price": None if (atr_v is None or _entry_adj <= 0) else float(_entry_adj - atr_stop_k * atr_v),
                            "trail_price": None if atr_v is None else float(peak_close_state.get(sym, cclose) - atr_trail_k * atr_v),
                            "atr_stop_k": float(atr_stop_k),
                            "atr_trail_k": float(atr_trail_k),
                            "trailing_activate_profit_pct": float(trailing_activate_profit_pct),
                            "ma120": trend_fast_v,
                            "ma200": trend_slow_v,
                            "trend_tier_at_exit": trend_tier,
                            "strong_trend_at_exit": bool(strong_trend),
                            "break_streak": int(break_streak),
                            "trend_break_confirm_days": int(max(1, trend_break_confirm_days)),
                            "trend_break_confirm_gap_pct": float(trend_break_confirm_gap_pct),
                            "triggered_rule": ("CONFIRMED_TREND_BREAK_EXIT" if reason == "TREND_BREAK_EXIT" else reason),
                        },
                    )
                )

        # candidates-only BUY via preindex (raw BUY candidates; tradable-at-order-stage with next_open like slow)
        cand_index_access_count += 1
        day_cands = cand_idx[i]
        buy_sigs: list[Signal] = []
        total_buy_signals += int(len(day_cands))
        raw_buy_mask = (
            sig_m["cross_up"][i, :]
            & sig_m["buffer_ok"][i, :]
            & sig_m["trend_ok"][i, :]
            & sig_m["risk_on_matrix"][i, :]
            & sig_m["ma_is_valid"][i, :]
            & sig_m["v2_trend_ok"][i, :]
        )
        raw_buy_signal_count = int(np.sum(raw_buy_mask))
        buy_candidate_mask = raw_buy_mask & mx.tradable[i, :]
        buy_candidate_count = int(np.sum(buy_candidate_mask))
        after_held_filter_count = 0
        day_gate_by_symbol: dict[str, dict[str, Any]] = {}
        for c in day_cands:
            sym = mx.symbols[int(c)]
            if sym in positions and int(positions[sym]) > 0:
                continue
            after_held_filter_count += 1
            trend_fast_v = None if np.isnan(feats.trend_fast_ma[i, c]) else float(feats.trend_fast_ma[i, c])
            trend_slow_v = None if np.isnan(feats.trend_slow_ma[i, c]) else float(feats.trend_slow_ma[i, c])
            strong_trend = bool(
                trend_fast_v is not None
                and trend_slow_v is not None
                and trend_fast_v > trend_slow_v
            )
            if bool(enable_trend_accel):
                order_value_scale = float(strong_trend_order_scale if strong_trend else weak_trend_order_scale)
            else:
                order_value_scale = 1.0
            trend_tier = "STRONG" if strong_trend else "WEAK"
            day_gate_by_symbol[sym] = {
                "cross_up": bool(sig_m["cross_up"][i, c]),
                "entry_buffer_ok": bool(sig_m["buffer_ok"][i, c]),
                "trend_ok": bool(sig_m["trend_ok"][i, c]),
                "base_trend_on": bool(sig_m["base_trend_on"][i, c]),
                "slope_pass": bool(sig_m["slope_pass"][i, c]),
                "continuity_pass": bool(sig_m["continuity_pass"][i, c]),
                "final_trend_on": bool(sig_m["quality_trend_on"][i, c]),
                "regime_ok": bool(sig_m["risk_on_matrix"][i, c]),
                "tradable": bool(mx.tradable[i, c]),
                "ma_is_valid": bool(sig_m["ma_is_valid"][i, c]),
                "close": None if np.isnan(mx.close[i, c]) else float(mx.close[i, c]),
                "open_next": None if np.isnan(mx.open[i + 1, c]) else float(mx.open[i + 1, c]),
                "slow_ma": None if np.isnan(feats.slow_ma[i, c]) else float(feats.slow_ma[i, c]),
                "fast_ma": None if np.isnan(feats.fast_ma[i, c]) else float(feats.fast_ma[i, c]),
                "fast_ma_prev": None if (i <= 0 or np.isnan(feats.fast_ma[i - 1, c])) else float(feats.fast_ma[i - 1, c]),
                "slow_ma_prev": None if (i <= 0 or np.isnan(feats.slow_ma[i - 1, c])) else float(feats.slow_ma[i - 1, c]),
                "ma120": None if np.isnan(feats.trend_fast_ma[i, c]) else float(feats.trend_fast_ma[i, c]),
                "ma200": None if np.isnan(feats.trend_slow_ma[i, c]) else float(feats.trend_slow_ma[i, c]),
                "trend_fast": trend_fast_v,
                "trend_slow": trend_slow_v,
                "v2_trend_ok": bool(sig_m["v2_trend_ok"][i, c]),
                "buy_raw_ok": True,
                "strength_value": None if np.isnan(strength[i, c]) else float(strength[i, c]),
                "strong_trend": bool(strong_trend),
                "trend_tier": trend_tier,
                "order_value_scale": float(order_value_scale),
            }
            buy_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.BUY,
                    qty=order_size,
                    reason="SMA_CROSS_UP",
                    reason_code="SMA_CROSS_UP",
                    meta={
                        "close": float(mx.close[i, c]) if not np.isnan(mx.close[i, c]) else None,
                        "slow_ma": float(feats.slow_ma[i, c]) if not np.isnan(feats.slow_ma[i, c]) else None,
                        "trend_ok": bool(sig_m["trend_ok"][i, c]),
                        "base_trend_on": bool(sig_m["base_trend_on"][i, c]),
                        "slope_pass": bool(sig_m["slope_pass"][i, c]),
                        "continuity_pass": bool(sig_m["continuity_pass"][i, c]),
                        "final_trend_on": bool(sig_m["quality_trend_on"][i, c]),
                        "regime_on": bool(risk_on[i]),
                        "strong_trend": bool(strong_trend),
                        "trend_tier": trend_tier,
                        "order_value_scale": float(order_value_scale),
                        "order_value_raw": (float(nav) / float(max_positions)) if int(max_positions) > 0 else 0.0,
                        "order_value_final": ((float(nav) / float(max_positions)) if int(max_positions) > 0 else 0.0) * float(order_value_scale),
                    },
                )
            )

        # blocked trend/risk/buffer counts (for metrics consistency)
        if enable_trend_filter and (not enable_trend_tier):
            blocked_by_trend_count += int(np.sum(sig_m["cross_up"][i, :] & (~sig_m["trend_ok"][i, :]) & sig_m["risk_on_matrix"][i, :]))
        quality_base = sig_m["cross_up"][i, :] & sig_m["buffer_ok"][i, :] & sig_m["risk_on_matrix"][i, :] & sig_m["base_trend_on"][i, :]
        slope_block_today = int(np.sum(quality_base & (~sig_m["slope_pass"][i, :])))
        continuity_block_today = int(np.sum(quality_base & sig_m["slope_pass"][i, :] & (~sig_m["continuity_pass"][i, :])))
        trend_slope_block_count += int(slope_block_today)
        trend_continuity_block_count += int(continuity_block_today)
        diag_reason_counts["BLOCK_TRADABLE_FALSE"] = int(diag_reason_counts.get("BLOCK_TRADABLE_FALSE", 0)) + max(raw_buy_signal_count - buy_candidate_count, 0)
        diag_reason_counts["BLOCK_HELD_ALREADY"] = int(diag_reason_counts.get("BLOCK_HELD_ALREADY", 0)) + max(buy_candidate_count - after_held_filter_count, 0)
        diag_reason_counts["BLOCK_CROSS_NOT_MET"] = int(diag_reason_counts.get("BLOCK_CROSS_NOT_MET", 0)) + int(np.sum(sig_m["ma_is_valid"][i, :] & (~sig_m["cross_up"][i, :])))
        diag_reason_counts["BLOCK_ENTRY_BUFFER"] = int(diag_reason_counts.get("BLOCK_ENTRY_BUFFER", 0)) + int(np.sum(sig_m["cross_up"][i, :] & (~sig_m["buffer_ok"][i, :])))
        diag_reason_counts["BLOCK_TREND"] = int(diag_reason_counts.get("BLOCK_TREND", 0)) + int(np.sum(sig_m["cross_up"][i, :] & sig_m["buffer_ok"][i, :] & (~sig_m["trend_ok"][i, :])))
        diag_reason_counts["BLOCK_REGIME_OFF"] = int(diag_reason_counts.get("BLOCK_REGIME_OFF", 0)) + int(np.sum(sig_m["cross_up"][i, :] & sig_m["buffer_ok"][i, :] & sig_m["trend_ok"][i, :] & (~sig_m["risk_on_matrix"][i, :])))
        diag_reason_counts["BLOCK_V2_TREND"] = int(diag_reason_counts.get("BLOCK_V2_TREND", 0)) + int(np.sum(sig_m["cross_up"][i, :] & sig_m["buffer_ok"][i, :] & sig_m["trend_ok"][i, :] & sig_m["risk_on_matrix"][i, :] & sig_m["ma_is_valid"][i, :] & (~sig_m["v2_trend_ok"][i, :])))

        next_day = day_list[i + 1]
        next_open = {
            s: float(open_idx.get((next_day, s), 0.0) or 0.0)
            for s in set([str(x.symbol).lower() for x in sell_sigs + buy_sigs] + list(positions.keys()))
        }
        strength_map = {mx.symbols[c]: (None if np.isnan(strength[i, c]) else float(strength[i, c])) for c in day_cands}
        mf_score_map = _build_daily_multifactor_scores(
            i=i,
            day_cands=day_cands,
            symbols=mx.symbols,
            close=mx.close,
            volume=mx.volume,
            bench_close=bench_close,
        ) if bool(enable_multifactor_rank) else {}
        debug_plan: dict[str, Any] = {}
        day_candidate_rows: list[dict[str, Any]] = []
        mf_gate_on_today = resolve_mf_gate_on_today(
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_rank_gate_mode=str(mf_rank_gate_mode or "ALWAYS_ON"),
            risk_on_today=bool(risk_on[i]),
            strong_risk_on_today=bool(strong_risk_on[i]),
            market_state_today="",
        )
        # Build ATR/close map for inverse-vol sizing
        _acm: dict[str, tuple[float, float]] = {}
        if weight_mode == "inverse_vol":
            for _sym, _c in sym_to_col.items():
                _a14 = float(feats.atr14[i, _c])
                _cv = float(mx.close[i, _c])
                if not (np.isnan(_a14) or np.isnan(_cv)):
                    _acm[_sym] = (_a14, _cv)
        orders = build_rebalance_orders(
            positions=positions,
            cash_available=cash,
            nav_close=nav,
            max_positions=effective_max_positions,
            lot_size=lot_size,
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            next_open=next_open,
            enable_strength_rank=bool(enable_strength_rank),
            strength_ma=int(strength_ma),
            strength_top_k_mode=str(strength_top_k_mode),
            strength_map=strength_map,
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_topk=int(mf_topk),
            mf_concentrate_topn=int(mf_concentrate_topn),
            mf_concentrate_scale=float(mf_concentrate_scale),
            mf_gate_on_today=bool(mf_gate_on_today),
            mf_score_map=mf_score_map,
            momentum_top_pct=float(momentum_top_pct),
            decision_date=day,
            candidate_audit=(None if bool(fast_mode) else day_candidate_rows),
            debug_plan=debug_plan,
            weight_mode=weight_mode,
            min_positions=min_positions,
            tilt_strength=tilt_strength,
            tilt_top_n=tilt_top_n,
            tilt_bottom_n=tilt_bottom_n,
            atr_close_map=_acm,
            min_trade_price=float(_min_trade_price),
            decision_close_map={sym: float(close_idx.get((day, sym), 0.0) or 0.0) for sym in next_open},
            enable_entry_gap_guard=bool(getattr(strategy, "enable_entry_gap_guard", False)),
            entry_gap_guard_pct=float(getattr(strategy, "entry_gap_guard_pct", 0.0) or 0.0),
            score_weight_min_scale=score_weight_min_scale,
            score_weight_max_scale=score_weight_max_scale,
            candidate_plan_mode=candidate_plan_mode,
            cash_aware_search_top_n=cash_aware_search_top_n,
            holding_entry_dates=dict(getattr(strategy, "entry_day", {}) or {}),
            strong_risk_on_today=bool(strong_risk_on[i]),
            rotation_replace_enabled=rotation_replace_enabled,
            rotation_replace_only_strong_risk_on=rotation_replace_only_strong_risk_on,
            rotation_replace_max_swaps_per_day=rotation_replace_max_swaps_per_day,
            rotation_replace_candidate_top_n=rotation_replace_candidate_top_n,
            rotation_replace_min_score_gap=rotation_replace_min_score_gap,
            rotation_min_hold_days=int(getattr(strategy, "min_hold_days", 0) or 0),
        )
        if not bool(fast_mode):
            candidate_rows.extend(day_candidate_rows)

        if daily_rows:
            cands_count = int((debug_plan or {}).get("buy_candidates_count", 0)) if bool(fast_mode) else int(len([r for r in day_candidate_rows if bool(r.get("is_candidate"))]))
            sel_count = int(len((debug_plan or {}).get("selected_symbols", []))) if bool(fast_mode) else int(len([r for r in day_candidate_rows if bool(r.get("is_candidate")) and bool(r.get("selected"))]))
            buy_slots_from_plan = int((debug_plan or {}).get("buy_slots", 0))
            sell_symbols = {str(s.symbol).lower() for s in sell_sigs}
            positions_after_sell = int(
                sum(
                    1
                    for sym, q in positions.items()
                    if int(q) > 0 and str(sym).lower() not in sell_symbols
                )
            )
            buy_slots = int(calc_buy_slots(int(effective_max_positions), int(positions_after_sell)))
            # In debug mode, enforce the slot identity to catch silent zeroing regressions.
            if bool(debug_first_divergence) and positions_after_sell < int(effective_max_positions):
                assert buy_slots > 0, (
                    f"buy_slots invalid: positions_after_sell={positions_after_sell}, "
                    f"max_positions={int(max_positions)}"
                )
            if buy_slots_from_plan != buy_slots:
                # Keep simulation semantics from order planner for orders, but diagnostics must
                # always reflect the explicit slot formula.
                debug_plan["buy_slots"] = int(buy_slots)
            after_slot_filter_count = int(min(after_held_filter_count, max(buy_slots, 0)))
            reject_reason_counts = dict((debug_plan or {}).get("reject_reason_counts", {}) or {})
            diag_reason_counts["BLOCK_NO_SLOTS"] = int(diag_reason_counts.get("BLOCK_NO_SLOTS", 0)) + max(after_held_filter_count - after_slot_filter_count, 0)
            skip_qty_zero = int(reject_reason_counts.get("SKIP_QTY_ZERO", 0) or 0)
            skip_no_cash = int(reject_reason_counts.get("SKIP_NO_CASH", 0) or 0)
            weak_blocked = int(reject_reason_counts.get("BLOCK_WEAK_TIER_DISABLED", 0) or 0)
            diag_reason_counts["SKIP_LOT_TOO_SMALL"] = int(diag_reason_counts.get("SKIP_LOT_TOO_SMALL", 0)) + skip_qty_zero
            diag_reason_counts["SKIP_CASH_INSUFFICIENT"] = int(diag_reason_counts.get("SKIP_CASH_INSUFFICIENT", 0)) + skip_no_cash
            diag_reason_counts["BLOCK_WEAK_TIER_DISABLED"] = int(diag_reason_counts.get("BLOCK_WEAK_TIER_DISABLED", 0)) + weak_blocked
            daily_rows[-1]["candidates_count"] = cands_count
            daily_rows[-1]["selected_count"] = sel_count
            daily_rows[-1]["buy_slots_before_buy"] = buy_slots
            daily_rows[-1]["buy_slots_after_sell"] = buy_slots
            daily_rows[-1]["raw_buy_signal_count"] = int(raw_buy_signal_count)
            daily_rows[-1]["buy_candidate_count"] = int(buy_candidate_count)
            daily_rows[-1]["after_held_filter_count"] = int(after_held_filter_count)
            daily_rows[-1]["after_slot_filter_count"] = int(after_slot_filter_count)
            daily_rows[-1]["after_cash_lot_count"] = int(sel_count)
            daily_rows[-1]["positions_before_sell"] = int(positions_before_sell)
            daily_rows[-1]["sells_executed_count"] = int(len(sell_sigs))
            daily_rows[-1]["positions_after_sell"] = int(positions_after_sell)
            daily_rows[-1]["buy_slots_calculated"] = int(buy_slots)
            daily_rows[-1]["candidates_after_held_filter_count"] = int(after_held_filter_count)
            daily_rows[-1]["sorting_triggered"] = bool(cands_count > buy_slots)
            selected_scales = list((debug_plan or {}).get("selected_order_value_scales", []) or [])
            weak_selected_count = int((debug_plan or {}).get("weak_trend_selected_count", 0) or 0)
            strong_selected_count = int((debug_plan or {}).get("strong_trend_selected_count", 0) or 0)
            selected_n_dbg = int(len((debug_plan or {}).get("selected_symbols", []) or []))
            daily_rows[-1]["mean_order_value_scale"] = (
                float(sum(float(x) for x in selected_scales) / len(selected_scales))
                if len(selected_scales) > 0
                else 0.0
            )
            daily_rows[-1]["weak_trend_buy_rate"] = (
                float(weak_selected_count) / float(selected_n_dbg)
                if selected_n_dbg > 0
                else 0.0
            )
            daily_rows[-1]["strong_trend_buy_rate"] = (
                float(strong_selected_count) / float(selected_n_dbg)
                if selected_n_dbg > 0
                else 0.0
            )
            daily_rows[-1]["mf_rank_triggered"] = 1 if bool((debug_plan or {}).get("mf_rank_triggered", False)) else 0
            daily_rows[-1]["mf_rank_applied"] = 1 if bool((debug_plan or {}).get("mf_rank_applied", False)) else 0
            daily_rows[-1]["mf_candidates_when_triggered"] = int((debug_plan or {}).get("mf_candidates_when_triggered", 0) or 0)
            daily_rows[-1]["mf_topk_reject_count"] = int((debug_plan or {}).get("mf_topk_reject_count", 0) or 0)
            daily_rows[-1]["mf_concentrated_selected_count"] = int((debug_plan or {}).get("mf_concentrated_selected_count", 0) or 0)
            daily_rows[-1]["mf_gate_on"] = 1 if bool((debug_plan or {}).get("mf_gate_on", False)) else 0
            daily_rows[-1]["trend_slope_block_count"] = int(slope_block_today)
            daily_rows[-1]["trend_continuity_block_count"] = int(continuity_block_today)
            daily_rows[-1]["base_trend_on_rate"] = float(np.mean(sig_m["base_trend_on"][i, :])) if n > 0 else 0.0
            daily_rows[-1]["quality_trend_on_rate"] = float(np.mean(sig_m["quality_trend_on"][i, :])) if n > 0 else 0.0
            daily_rows[-1]["strong_risk_on"] = 1 if bool(strong_risk_on[i]) else 0
            cands_now = int((debug_plan or {}).get("buy_candidates_count", 0) or 0)
            slots_now = int((debug_plan or {}).get("buy_slots", 0) or 0)
            daily_rows[-1]["mf_rank_suppressed_by_strong_gate"] = (
                1
                if bool(enable_multifactor_rank) and (not bool(mf_gate_on_today)) and (cands_now > slots_now)
                else 0
            )
            if bool(fast_mode):
                daily_rows[-1]["top5_selected_strength_json"] = "[]"
                daily_rows[-1]["top5_rejected_strength_json"] = "[]"
            else:
                cands = [r for r in day_candidate_rows if bool(r.get("is_candidate"))]
                sel = [r for r in cands if bool(r.get("selected"))]
                rej = [r for r in cands if not bool(r.get("selected"))]
                daily_rows[-1]["top5_selected_strength_json"] = json.dumps(
                    [{"symbol": r.get("symbol"), "strength": r.get("strength")} for r in sel[:5]],
                    ensure_ascii=False,
                )
                daily_rows[-1]["top5_rejected_strength_json"] = json.dumps(
                    [{"symbol": r.get("symbol"), "strength": r.get("strength"), "reason": r.get("reject_reason")} for r in rej[:5]],
                    ensure_ascii=False,
                )
        if debug_first_divergence:
            rank_pos_map: dict[str, int] = {}
            ranked_rows = [r for r in day_candidate_rows if bool(r.get("is_candidate"))]
            if not ranked_rows:
                raw_syms = [str(s.symbol).lower() for s in buy_sigs]
                if bool(enable_strength_rank):
                    raw_syms = sorted(
                        raw_syms,
                        key=lambda s: (
                            -1e18
                            if day_gate_by_symbol.get(s, {}).get("strength_value") is None
                            else -float(day_gate_by_symbol.get(s, {}).get("strength_value")),
                            s,
                        ),
                    )
                else:
                    raw_syms = sorted(raw_syms)
                for idx_rank, sym_r in enumerate(raw_syms, start=1):
                    rank_pos_map[sym_r] = int(idx_rank)
                    gate = day_gate_by_symbol.setdefault(sym_r, {})
                    gate["rank_position"] = int(idx_rank)
            else:
                for idx_rank, row in enumerate(ranked_rows, start=1):
                    sym_r = str(row.get("symbol", "")).lower()
                    rank_pos_map[sym_r] = int(idx_rank)
                    gate = day_gate_by_symbol.setdefault(sym_r, {})
                    gate["rank_position"] = int(idx_rank)
                    if gate.get("strength_value") is None:
                        gate["strength_value"] = row.get("strength")
            sig_details = []
            for s in sell_sigs + buy_sigs:
                sig_details.append(
                    {
                        "symbol": str(s.symbol),
                        "side": str(s.side.value),
                        "action": str(s.action or ""),
                        "reason_code": str(s.reason_code or s.reason or ""),
                        "meta": dict(s.meta) if isinstance(s.meta, dict) else {},
                    }
                )
            debug_trace[day.isoformat()] = {
                "cash_before": float(cash),
                "held_symbols_before": {str(k): int(v) for k, v in positions.items() if int(v) > 0},
                "signal_details": sig_details,
                "buy_candidates_raw": sorted([str(s.symbol).lower() for s in buy_sigs]),
                "buy_gate_by_symbol": day_gate_by_symbol,
                "buy_candidates_count": int((debug_plan or {}).get("buy_candidates_count", 0)),
                "buy_slots": int((debug_plan or {}).get("buy_slots", 0)),
                "sorting_triggered": bool(int((debug_plan or {}).get("buy_candidates_count", 0)) > int((debug_plan or {}).get("buy_slots", 0))),
                "sorted_selected_symbols": list((debug_plan or {}).get("selected_symbols", [])),
                "selected_symbols": list((debug_plan or {}).get("selected_symbols", [])),
                "buys_executed": list((debug_plan or {}).get("buys_executed", [])),
                "positions_after": {str(k): int(v) for k, v in positions.items() if int(v) > 0},
                "nav_end_of_day": float(nav),
            }

        if orders:
            pending[next_day] = [
                {
                    "side": o.side,
                    "symbol": str(o.symbol).lower(),
                    "qty": int(o.qty),
                    "reason_code": str(o.reason_code),
                    "meta": dict(o.meta or {}),
                }
                for o in orders
            ]

    simulation_seconds = float(time.perf_counter() - sim_t0)
    io_t0 = time.perf_counter()
    daily_df = pd.DataFrame(daily_rows)
    trades_df = pd.DataFrame(trade_rows)
    candidates_df = pd.DataFrame(candidate_rows)
    io_write_seconds = float(time.perf_counter() - io_t0)

    metrics = _compute_metrics(
        daily_df,
        trades_df,
        max_positions=max_positions,
        blocked_by_trend_count=blocked_by_trend_count,
        total_buy_signals=total_buy_signals,
        candidates_df=candidates_df,
        enable_strength_rank=bool(enable_strength_rank),
        strength_ma=int(strength_ma),
    )
    metrics["trend_slope_block_count"] = int(trend_slope_block_count)
    metrics["trend_continuity_block_count"] = int(trend_continuity_block_count)
    metrics["precompute_seconds"] = precompute_seconds
    metrics["simulation_seconds"] = simulation_seconds
    metrics["io_write_seconds"] = io_write_seconds
    metrics["scan_all_symbols_count"] = int(scan_all_symbols_count)
    metrics["cand_index_access_count"] = int(cand_index_access_count)
    metrics["notes"] = "preindex=true; held_only_sell=true; one_shot_write=true"
    metrics["candidate_diag_reason_counts"] = dict(diag_reason_counts)
    metrics["BLOCK_WEAK_TIER_DISABLED"] = int(diag_reason_counts.get("BLOCK_WEAK_TIER_DISABLED", 0) or 0)
    metrics["exit_take_profit_count"] = exit_take_profit_count
    metrics["exit_fixed_stop_count"] = exit_fixed_stop_count
    metrics["exit_atr_stop_count"] = exit_atr_stop_count
    metrics["exit_atr_trail_count"] = exit_atr_trail_count
    metrics["exit_time_exit_count"] = exit_time_exit_count
    metrics["exit_signal_count"] = exit_signal_count
    metrics["exit_ma20_count"] = exit_ma20_count
    metrics["exit_low10_count"] = exit_low10_count
    if collect_decision_diff:
        metrics["decision_diff_preview"] = []
    if debug_first_divergence:
        metrics["debug_trace"] = debug_trace
    return PortfolioBacktestResult(daily=daily_df, trades=trades_df, candidates=candidates_df, metrics=metrics)


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


def _run_vector_portfolio_backtest_breakout(
    *,
    strategy: Any,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    trading_days: list[date],
    initial_cash: float,
    max_positions: int,
    lot_size: int,
    enable_strength_rank: bool,
    strength_ma: int,
    strength_top_k_mode: str,
    fast_mode: bool,
    enable_multifactor_rank: bool,
    mf_topk: int,
    mf_concentrate_topn: int,
    mf_concentrate_scale: float,
    mf_rank_gate_mode: str,
    momentum_top_pct: float = 0.0,
    cost_cfg: CostConfig | None = None,
    raw_history: pd.DataFrame | None = None,
    exit_cfg: Any = None,
    st_history: Any = None,
    sector_data: Any = None,
    industry_map: Any = None,
    risk_budget_cfg: Any = None,
    sizing_cfg: Any = None,
    market_filter_cfg: Any = None,
    benchmark_regime_cfg: Any = None,
    **_kwargs: Any,
) -> PortfolioBacktestResult:
    """Breakout Trend 策略的 provider-based 执行路径。"""
    from backend.core.config.models import ExitConfig, RiskBudgetConfig
    from backend.core.engine_vector.breakout_signal_provider import BreakoutTrendProvider
    from backend.core.engine_vector.signal_provider import DayContext

    if history.empty:
        raise ValueError("history is empty")
    if not trading_days:
        raise ValueError("trading_days is empty")
    _uf_b = dict(getattr(strategy, "state", {}).get("universe_filters") or {})
    _min_trade_price = float(_uf_b.get("min_price", getattr(strategy, "min_price", 0.0)) or 0.0)

    # DD circuit breaker config
    _rbc = risk_budget_cfg if isinstance(risk_budget_cfg, RiskBudgetConfig) else RiskBudgetConfig()
    enable_dd_breaker = bool(_rbc.enabled)
    dd_reduce_pct = float(_rbc.dd_reduce_pct)
    dd_reduce_scale = float(_rbc.dd_reduce_scale)
    # Portfolio sizing
    from backend.core.config.models import SizingConfig as _SizingConfig_b
    _sc_b = sizing_cfg if isinstance(sizing_cfg, _SizingConfig_b) else _SizingConfig_b()
    weight_mode = str(_sc_b.weight_mode or "equal")
    min_positions_cfg = int(_sc_b.min_positions)
    tilt_strength_cfg = float(_sc_b.tilt_strength)
    tilt_top_n_cfg = int(_sc_b.tilt_top_n)
    tilt_bottom_n_cfg = int(_sc_b.tilt_bottom_n)
    score_weight_min_scale_cfg = float(_sc_b.score_weight_min_scale)
    score_weight_max_scale_cfg = float(_sc_b.score_weight_max_scale)
    candidate_plan_mode_cfg = str(_sc_b.candidate_plan_mode or "ranked")
    cash_aware_search_top_n_cfg = int(_sc_b.cash_aware_search_top_n)
    rotation_replace_enabled_cfg = bool(_sc_b.rotation_replace_enabled)
    rotation_replace_only_strong_risk_on_cfg = bool(_sc_b.rotation_replace_only_strong_risk_on)
    rotation_replace_max_swaps_per_day_cfg = int(_sc_b.rotation_replace_max_swaps_per_day)
    rotation_replace_candidate_top_n_cfg = int(_sc_b.rotation_replace_candidate_top_n)
    rotation_replace_min_score_gap_cfg = float(_sc_b.rotation_replace_min_score_gap)

    provider = BreakoutTrendProvider()
    _ec = exit_cfg if isinstance(exit_cfg, ExitConfig) else ExitConfig()
    provider.precompute(
        history=history,
        benchmark=benchmark,
        raw_history=raw_history,
        trading_days=trading_days,
        strategy=strategy,
        exit_cfg=_ec,
        st_history=st_history,
        membership_history=getattr(strategy, "state", {}).get("membership_history"),
        strength_ma=strength_ma,
        base_order_value=float(initial_cash) / float(max(max_positions, 1)),
        sector_data=sector_data,
        industry_map=industry_map,
        industry_history=_kwargs.get("industry_history"),
    )

    day_list = list(trading_days)
    day_ts_list = [pd.Timestamp(d).normalize() for d in day_list]
    day_count = len(day_list)

    # ── MA market filter gate ──
    _mf_cfg: MarketFilterConfig | None = None
    if isinstance(market_filter_cfg, MarketFilterConfig):
        _mf_cfg = market_filter_cfg
    elif isinstance(market_filter_cfg, dict):
        _mf_fields = {k: v for k, v in market_filter_cfg.items() if k in MarketFilterConfig.__dataclass_fields__}
        _mf_cfg = MarketFilterConfig(**_mf_fields)

    _mf_enabled = bool(_mf_cfg is not None and _mf_cfg.enabled)
    _mf_state_arr = np.zeros(day_count, dtype=np.int8)  # 0=BULL,1=TRANS_DOWN,2=TRANS_UP,3=BEAR
    _mf_mult_arr = np.ones(day_count, dtype=float)      # max_positions multiplier
    if _mf_enabled and not benchmark.empty:
        _bench_df = benchmark.copy()
        _bench_df["date"] = pd.to_datetime(_bench_df["date"]).dt.normalize()
        _bench_df = _bench_df.sort_values("date")
        _bench_close_s = pd.to_numeric(_bench_df["close"], errors="coerce")
        _bench_close = pd.Series(_bench_close_s.to_numpy(dtype=float), index=_bench_df["date"])
        _bench_close = _bench_close.reindex(day_ts_list)

        _slope_window = max(1, int(_mf_cfg.slope_window))
        _slope_ma_period = max(2, int(getattr(_mf_cfg, "slope_ma_period", 50)))
        _ema_s = _bench_close.ewm(span=_slope_ma_period, adjust=False).mean()
        _prev = _ema_s.shift(_slope_window)
        _momentum = (_ema_s - _prev) / _prev
        _ma200 = _bench_close.rolling(200, min_periods=200).mean()

        _bc = _bench_close.to_numpy(dtype=float)
        _mom = _momentum.to_numpy(dtype=float)
        _ma2 = _ma200.to_numpy(dtype=float)
        _valid = ~np.isnan(_bc) & ~np.isnan(_mom) & ~np.isnan(_ma2)
        _above = _bc > _ma2
        _slope_pos = _mom >= 0.0

        _mf_state_arr[_valid & _above & ~_slope_pos] = 1
        _mf_state_arr[_valid & ~_above & _slope_pos] = 2
        _mf_state_arr[_valid & ~_above & ~_slope_pos] = 3

        _mf_mult_arr[_mf_state_arr == 0] = float(_mf_cfg.bull_multiplier)
        _td_mult = getattr(_mf_cfg, "trans_down_multiplier", None)
        _tu_mult = getattr(_mf_cfg, "trans_up_multiplier", None)
        _bear_mult = getattr(_mf_cfg, "bear_multiplier", None)
        _mf_mult_arr[_mf_state_arr == 1] = float(_td_mult if _td_mult is not None else _mf_cfg.light_multiplier)
        _mf_mult_arr[_mf_state_arr == 2] = float(_tu_mult if _tu_mult is not None else _mf_cfg.light_multiplier)
        _mf_mult_arr[_mf_state_arr == 3] = float(_bear_mult if _bear_mult is not None else 0.0)

    # ── Benchmark regime gate ──
    _br_cfg: BenchmarkRegimeConfig | None = None
    if isinstance(benchmark_regime_cfg, BenchmarkRegimeConfig):
        _br_cfg = benchmark_regime_cfg
    elif isinstance(benchmark_regime_cfg, dict):
        _br_fields = {k: v for k, v in benchmark_regime_cfg.items() if k in BenchmarkRegimeConfig.__dataclass_fields__}
        _br_cfg = BenchmarkRegimeConfig(**_br_fields)

    _br_enabled = bool(_br_cfg is not None and _br_cfg.enabled)
    _br_gate_arr = np.ones(day_count, dtype=bool)
    if _br_enabled and not benchmark.empty:
        _bench_df = benchmark.copy()
        _bench_df["date"] = pd.to_datetime(_bench_df["date"]).dt.normalize()
        _bench_df = _bench_df.sort_values("date")
        _bench_close_s = pd.to_numeric(_bench_df["close"], errors="coerce")
        _bench_close = pd.Series(_bench_close_s.to_numpy(dtype=float), index=_bench_df["date"])
        _bench_close = _bench_close.reindex(day_ts_list)
        _fast = max(2, int(_br_cfg.fast_period))
        _slow = max(_fast + 1, int(_br_cfg.slow_period))
        _slope_w = max(1, int(_br_cfg.slope_window))
        _ma_fast = _bench_close.rolling(_fast, min_periods=_fast).mean()
        _ma_slow = _bench_close.rolling(_slow, min_periods=_slow).mean()
        _slow_slope = _ma_slow - _ma_slow.shift(_slope_w)
        _allow = (_ma_fast > _ma_slow) & (_slow_slope >= 0.0)
        _br_gate_arr = _allow.fillna(False).to_numpy(dtype=bool)

    # ── Sector gate for breakout path ──
    _enable_sector_gate = bool(getattr(strategy, "enable_sector_gate", False))
    _sector_elig_mat: np.ndarray | None = None
    _sector_elig_col: dict[str, int] = {}
    if _enable_sector_gate and sector_data and industry_map:
        from backend.core.engine_vector.features import compute_sector_eligible
        _p_syms = provider._mx.symbols if hasattr(provider, "_mx") else list(sorted(set(history["symbol"].astype(str).str.lower())))
        _p_dates = provider._mx.dates if hasattr(provider, "_mx") else np.array([pd.Timestamp(d) for d in trading_days])
        _sector_elig_mat = compute_sector_eligible(
            sector_data=sector_data,
            industry_map=industry_map,
            symbols=_p_syms,
            dates=_p_dates,
            window=int(getattr(strategy, "sector_rank_window", 60)),
            top_pct=float(getattr(strategy, "sector_top_pct", 0.30)),
        )
        _sector_elig_col = {s: j for j, s in enumerate(_p_syms)}

    # 成交执行使用不复权价格
    _raw = raw_history if raw_history is not None else history
    _raw_hist = _raw.copy()
    _raw_hist["date"] = pd.to_datetime(_raw_hist["date"])
    _raw_hist["symbol"] = _raw_hist["symbol"].astype(str).str.lower()
    day_list = list(trading_days)
    open_idx, close_idx = build_backtest_price_indices(
        history=_raw_hist,
        trading_days=day_list,
    )
    del _raw_hist

    _cc = cost_cfg if cost_cfg is not None else CostConfig()
    _slip_bps = _cc.slippage_bps / 10000.0
    _comm_rate = _cc.commission_rate
    _comm_min = _cc.commission_min
    _stamp_rate = _cc.stamp_tax_rate

    pending: dict[date, list[dict[str, Any]]] = {}
    positions: dict[str, int] = {}
    position_avg_cost: dict[str, float] = {}
    holding_sources: dict[str, dict[str, Any]] = {}
    cash = float(initial_cash)
    peak_nav = float(initial_cash)
    prev_nav = float(initial_cash)

    trade_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    sim_t0 = time.perf_counter()
    market_filter_bull_days = 0
    market_filter_bear_days = 0
    market_state_trans_down_days = 0
    market_state_trans_up_days = 0
    trade_mode_main_days = 0
    trade_mode_light_days = 0
    trade_mode_notrade_days = 0
    _portfolio_mode = str(getattr(strategy, "portfolio_mode", "equal_10") or "equal_10").strip().lower()

    for i, day in enumerate(day_list):
        traded_value = 0.0

        # ── T+1 open fills ──
        for od in pending.pop(day, []):
            px = float(open_idx.get((day, od["symbol"]), 0.0) or 0.0)
            if px <= 0:
                continue
            if od["side"] == Side.SELL:
                held = int(positions.get(od["symbol"], 0))
                qty = min(held, int(od["qty"]))
                if qty <= 0:
                    continue
                fill_px = px * (1.0 - _slip_bps)
                gross = qty * fill_px
                comm = max(_comm_min, gross * _comm_rate)
                stax = gross * _stamp_rate
                net = gross - comm - stax
                cash += net
                traded_value += gross
                positions[od["symbol"]] = held - qty
                if positions[od["symbol"]] <= 0:
                    positions.pop(od["symbol"], None)
                    position_avg_cost.pop(od["symbol"], None)
                    # fill hook: last_sell_day
                    if provider.last_sell_day is not None:
                        provider.last_sell_day[od["symbol"]] = day
                    # fill hook: clear extra dicts
                    for d in provider.extra_clear_dicts:
                        d.pop(od["symbol"], None)
                    provider.entry_day.pop(od["symbol"], None)
                elif bool((od.get("meta") or {}).get("risk_off_partial_mark_on_fill", False)) and isinstance(risk_off_partial_state, dict):
                    risk_off_partial_state[od["symbol"]] = True
                trade_rows.append({
                    "date": day.isoformat(), "symbol": od["symbol"], "side": "SELL",
                    "price": px, "fill_price": round(fill_px, 4), "qty": qty,
                    "value": round(gross, 2), "commission": round(comm, 2),
                    "stamp_tax": round(stax, 2),
                    "slippage": round(abs(fill_px - px) * qty, 2),
                    "net_amount": round(net, 2),
                    "reason_code": od["reason_code"],
                    "triggered_rule": str((od.get("meta") or {}).get("triggered_rule", "")),
                    "break_streak": 0,
                    "meta_json": json.dumps(od.get("meta") or {}, ensure_ascii=False),
                })
            else:
                if _min_trade_price > 0 and px < _min_trade_price:
                    continue
                qty = int(od["qty"])
                fill_px = px * (1.0 + _slip_bps)
                gross = qty * fill_px
                comm = max(_comm_min, gross * _comm_rate)
                net = gross + comm
                if qty <= 0 or net > cash:
                    continue
                cash -= net
                traded_value += gross
                prev_qty = int(positions.get(od["symbol"], 0))
                prev_avg = float(position_avg_cost.get(od["symbol"], 0.0))
                new_qty = prev_qty + qty
                new_avg = ((prev_qty * prev_avg) + (qty * fill_px)) / float(new_qty) if new_qty > 0 else 0.0
                positions[od["symbol"]] = new_qty
                position_avg_cost[od["symbol"]] = float(new_avg)
                risk_off_partial_state = getattr(provider, "_risk_off_partial_state", None)
                if prev_qty <= 0 and isinstance(risk_off_partial_state, dict):
                    risk_off_partial_state.pop(od["symbol"], None)
                # fill hook: entry_day
                if prev_qty == 0 or provider.entry_day_overwrite:
                    provider.entry_day[od["symbol"]] = day
                # fill hook: entry bar index / breakout floor
                if prev_qty == 0:
                    if isinstance(getattr(provider, "entry_bar_index", None), dict):
                        provider.entry_bar_index[od["symbol"]] = int(i)
                    if isinstance(getattr(provider, "entry_breakout_floor_raw", None), dict):
                        try:
                            breakout_floor_raw = float((od.get("meta") or {}).get("entry_breakout_floor_raw", 0.0) or 0.0)
                        except Exception:
                            breakout_floor_raw = 0.0
                        if breakout_floor_raw > 0.0:
                            provider.entry_breakout_floor_raw[od["symbol"]] = float(breakout_floor_raw)
                # fill hook: peak_state_on_buy
                if provider.peak_state_on_buy is not None:
                    raw_c = float(close_idx.get((day, od["symbol"]), px))
                    provider.peak_state_on_buy.setdefault(od["symbol"], raw_c)
                trade_rows.append({
                    "date": day.isoformat(), "symbol": od["symbol"], "side": "BUY",
                    "price": px, "fill_price": round(fill_px, 4), "qty": qty,
                    "value": round(gross, 2), "commission": round(comm, 2),
                    "stamp_tax": 0.0,
                    "slippage": round(abs(fill_px - px) * qty, 2),
                    "net_amount": round(net, 2),
                    "reason_code": od["reason_code"],
                    "triggered_rule": "",
                    "break_streak": 0,
                    "meta_json": json.dumps(od.get("meta") or {}, ensure_ascii=False),
                })

        # ── NAV snapshot ──
        nav, market_value, pos_values = compute_nav_snapshot(cash=cash, positions=positions, close_idx=close_idx, day=day)
        peak_nav = max(peak_nav, nav)
        daily_ret = (nav / prev_nav - 1.0) if prev_nav > 0 else 0.0
        drawdown = (nav / peak_nav - 1.0) if peak_nav > 0 else 0.0
        # DD risk control: DD > threshold → reduce positions
        dynamic_base_positions = int(max_positions)
        if _portfolio_mode == "equal_8":
            dynamic_base_positions = min(int(max_positions), 8)
        elif _portfolio_mode == "equal_6":
            dynamic_base_positions = min(int(max_positions), 6)
        elif _portfolio_mode == "profit_release":
            dynamic_base_positions = int(max_positions)
            for _sym, _qty in positions.items():
                if int(_qty) <= 0:
                    continue
                _sym_s = str(_sym).lower()
                _c = float(close_idx.get((day, _sym_s), 0.0) or 0.0)
                _avg = float(position_avg_cost.get(_sym_s, 0.0) or 0.0)
                if _c > 0 and _avg > 0 and ((_c / _avg) - 1.0) > 0.20:
                    dynamic_base_positions = int(max_positions) + 1
                    break

        dd_abs = abs(drawdown)
        if enable_dd_breaker and dd_abs >= dd_reduce_pct:
            effective_max_positions = max(1, int(dynamic_base_positions * dd_reduce_scale))
            dd_state = "REDUCED"
        else:
            effective_max_positions = int(dynamic_base_positions)
            dd_state = "NORMAL"
        market_state_name = "BULL"
        trade_mode_name = "TREND_MAIN"
        if _mf_enabled:
            _state = int(_mf_state_arr[i])
            _mult = float(_mf_mult_arr[i])
            _scaled = int(round(float(effective_max_positions) * max(0.0, _mult)))
            effective_max_positions = max(0, _scaled)
            if _state == 0:
                market_filter_bull_days += 1
                trade_mode_main_days += 1
                market_state_name = "BULL"
                trade_mode_name = "TREND_MAIN"
            elif _state == 1:
                market_state_trans_down_days += 1
                trade_mode_light_days += 1
                market_state_name = "TRANS_DOWN"
                trade_mode_name = "TREND_LIGHT"
            elif _state == 2:
                market_state_trans_up_days += 1
                trade_mode_light_days += 1
                market_state_name = "TRANS_UP"
                trade_mode_name = "TREND_LIGHT"
            else:
                market_filter_bear_days += 1
                trade_mode_notrade_days += 1
                market_state_name = "BEAR"
                trade_mode_name = "NO_TRADE"
        gross_exposure = (market_value / nav) if nav > 0 else 0.0
        turnover_pct = (traded_value / prev_nav) if prev_nav > 0 else 0.0
        top5 = [{"symbol": s, "value": round(v, 2)} for s, v in sorted(pos_values, key=lambda x: x[1], reverse=True)[:5]]
        daily_rows.append({
            "date": day.isoformat(), "nav": nav, "cash": cash,
            "positions_count": len(positions),
            "positions_count_end_of_day": len(positions),
            "daily_return": daily_ret, "drawdown": drawdown,
            "gross_exposure": gross_exposure, "turnover_pct": turnover_pct,
            "top5_positions_json": json.dumps(top5, ensure_ascii=False),
            "candidates_count": 0, "selected_count": 0,
            "top5_selected_strength_json": "[]",
            "top5_rejected_strength_json": "[]",
            "buy_slots_before_buy": 0, "buy_slots_after_sell": 0,
            "raw_buy_signal_count": 0, "buy_candidate_count": 0,
            "after_held_filter_count": 0, "after_slot_filter_count": 0,
            "after_cash_lot_count": 0,
            "positions_before_sell": 0, "sells_executed_count": 0,
            "positions_after_sell": 0, "buy_slots_calculated": 0,
            "candidates_after_held_filter_count": 0,
            "sorting_triggered": False,
            "mean_order_value_scale": 0.0,
            "weak_trend_buy_rate": 0.0, "strong_trend_buy_rate": 0.0,
            "mf_rank_applied": 0, "mf_gate_on": 0,
            "trend_slope_block_count": 0, "trend_continuity_block_count": 0,
            "base_trend_on_rate": 0.0, "quality_trend_on_rate": 0.0,
            "effective_max_positions": int(effective_max_positions),
            "dd_state": dd_state,
            "market_state": market_state_name,
            "trade_mode": trade_mode_name,
            "benchmark_regime_on": bool(_br_gate_arr[i]) if _br_enabled else True,
        })
        prev_nav = nav

        if i >= len(day_list) - 1:
            pos_cnt_eod = int(sum(1 for _q in positions.values() if int(_q) > 0))
            buy_slots_eod = int(calc_buy_slots(int(effective_max_positions), int(pos_cnt_eod)))
            daily_rows[-1]["positions_before_sell"] = int(pos_cnt_eod)
            daily_rows[-1]["positions_after_sell"] = int(pos_cnt_eod)
            daily_rows[-1]["buy_slots_before_buy"] = int(buy_slots_eod)
            daily_rows[-1]["buy_slots_after_sell"] = int(buy_slots_eod)
            daily_rows[-1]["buy_slots_calculated"] = int(buy_slots_eod)
            continue

        next_day = day_list[i + 1]
        base_order_value = float(nav) / float(max(effective_max_positions, 1))

        # ── provider day_signals ──
        ctx = DayContext(
            positions=positions,
            position_avg_cost=position_avg_cost,
            cash=cash,
            nav=nav,
            base_order_value=base_order_value,
            max_positions=max_positions,
            close_idx=close_idx,
            open_idx=open_idx,
            next_day=next_day,
            holding_sources=holding_sources,
            risk_on=bool(provider._risk_on[i]),
            market_state=market_state_name,
        )
        ds = provider.day_signals(day, i, ctx)

        sell_sigs = ds.sell_signals
        buy_sigs = ds.buy_signals

        # ── Sector gate filter (breakout path) ──
        if _sector_elig_mat is not None:
            buy_sigs = [
                s for s in buy_sigs
                if (_sc := _sector_elig_col.get(str(s.symbol).lower())) is not None
                and bool(_sector_elig_mat[i, _sc])
            ]
        # ── Benchmark regime gate / market no-trade ──
        if _br_enabled and not bool(_br_gate_arr[i]):
            buy_sigs = []
        if _mf_enabled and int(_mf_state_arr[i]) == 3:
            buy_sigs = []

        # ── order planning ──
        next_open = {
            s: float(open_idx.get((next_day, s), 0.0) or 0.0)
            for s in set([str(x.symbol).lower() for x in sell_sigs + buy_sigs] + list(positions.keys()))
        }
        debug_plan: dict[str, Any] = {}
        day_candidate_rows: list[dict[str, Any]] = []
        mf_gate_on_today = resolve_mf_gate_on_today(
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_rank_gate_mode=str(mf_rank_gate_mode or "ALWAYS_ON"),
            risk_on_today=bool(provider._risk_on[i]),
            strong_risk_on_today=ds.strong_risk_on,
            market_state_today=market_state_name,
        )
        # Build ATR/close map for inverse-vol sizing (breakout path)
        _acm_b: dict[str, tuple[float, float]] = {}
        if weight_mode == "inverse_vol" and hasattr(provider, "_feats"):
            _p_feats = provider._feats
            _p_mx = provider._mx
            _p_stc = provider._sym_to_col if hasattr(provider, "_sym_to_col") else {}
            for _sym_b, _col_b in _p_stc.items():
                _a14_b = float(_p_feats.atr14[i, _col_b])
                _cv_b = float(_p_mx.close[i, _col_b])
                if not (np.isnan(_a14_b) or np.isnan(_cv_b)):
                    _acm_b[_sym_b] = (_a14_b, _cv_b)
        orders = build_rebalance_orders(
            positions=positions,
            cash_available=cash,
            nav_close=nav,
            max_positions=effective_max_positions,
            lot_size=lot_size,
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            next_open=next_open,
            enable_strength_rank=bool(enable_strength_rank),
            strength_ma=int(strength_ma),
            strength_top_k_mode=str(strength_top_k_mode),
            strength_map=ds.strength_map,
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_topk=int(mf_topk),
            mf_concentrate_topn=int(mf_concentrate_topn),
            mf_concentrate_scale=float(mf_concentrate_scale),
            mf_gate_on_today=bool(mf_gate_on_today),
            mf_score_map=ds.mf_score_map,
            momentum_top_pct=float(momentum_top_pct),
            decision_date=day,
            candidate_audit=(None if bool(fast_mode) else day_candidate_rows),
            debug_plan=debug_plan,
            weight_mode=weight_mode,
            min_positions=min_positions_cfg,
            tilt_strength=tilt_strength_cfg,
            tilt_top_n=tilt_top_n_cfg,
            tilt_bottom_n=tilt_bottom_n_cfg,
            atr_close_map=_acm_b,
            min_trade_price=float(_min_trade_price),
            decision_close_map={sym: float(close_idx.get((day, sym), 0.0) or 0.0) for sym in next_open},
            enable_entry_gap_guard=bool(getattr(strategy, "enable_entry_gap_guard", False)),
            entry_gap_guard_pct=float(getattr(strategy, "entry_gap_guard_pct", 0.0) or 0.0),
            score_weight_min_scale=score_weight_min_scale_cfg,
            score_weight_max_scale=score_weight_max_scale_cfg,
            candidate_plan_mode=candidate_plan_mode_cfg,
            cash_aware_search_top_n=cash_aware_search_top_n_cfg,
            holding_entry_dates=dict(getattr(provider, "entry_day", {}) or {}),
            strong_risk_on_today=bool(ds.strong_risk_on),
            rotation_replace_enabled=rotation_replace_enabled_cfg,
            rotation_replace_only_strong_risk_on=rotation_replace_only_strong_risk_on_cfg,
            rotation_replace_max_swaps_per_day=rotation_replace_max_swaps_per_day_cfg,
            rotation_replace_candidate_top_n=rotation_replace_candidate_top_n_cfg,
            rotation_replace_min_score_gap=rotation_replace_min_score_gap_cfg,
            rotation_min_hold_days=int(getattr(strategy, "min_hold_days", 0) or 0),
        )
        if not bool(fast_mode):
            candidate_rows.extend(day_candidate_rows)

        # ── daily diagnostics ──
        positions_before_sell = int(sum(1 for _q in positions.values() if int(_q) > 0))
        sell_symbols = {str(s.symbol).lower() for s in sell_sigs}
        positions_after_sell = int(sum(1 for sym, q in positions.items() if int(q) > 0 and str(sym).lower() not in sell_symbols))
        buy_slots = int(calc_buy_slots(int(effective_max_positions), int(positions_after_sell)))
        cands_count = int((debug_plan or {}).get("buy_candidates_count", 0))
        sel_count = int(len((debug_plan or {}).get("selected_symbols", [])))
        daily_rows[-1]["candidates_count"] = cands_count
        daily_rows[-1]["selected_count"] = sel_count
        daily_rows[-1]["buy_slots_before_buy"] = buy_slots
        daily_rows[-1]["buy_slots_after_sell"] = buy_slots
        daily_rows[-1]["buy_candidate_count"] = int(len(buy_sigs))
        daily_rows[-1]["after_held_filter_count"] = int(len(buy_sigs))
        daily_rows[-1]["positions_before_sell"] = int(positions_before_sell)
        daily_rows[-1]["sells_executed_count"] = int(len(sell_sigs))
        daily_rows[-1]["positions_after_sell"] = int(positions_after_sell)
        daily_rows[-1]["buy_slots_calculated"] = int(buy_slots)
        daily_rows[-1]["raw_buy_signal_count"] = int(ds.diagnostics.get("raw_buy_signal_count", ds.diagnostics.get("breakout_candidates", 0)))
        daily_rows[-1]["mf_rank_triggered"] = 1 if bool((debug_plan or {}).get("mf_rank_triggered", False)) else 0
        daily_rows[-1]["mf_rank_applied"] = 1 if bool((debug_plan or {}).get("mf_rank_applied", False)) else 0
        daily_rows[-1]["mf_candidates_when_triggered"] = int((debug_plan or {}).get("mf_candidates_when_triggered", 0) or 0)
        daily_rows[-1]["mf_topk_reject_count"] = int((debug_plan or {}).get("mf_topk_reject_count", 0) or 0)
        daily_rows[-1]["mf_concentrated_selected_count"] = int((debug_plan or {}).get("mf_concentrated_selected_count", 0) or 0)
        daily_rows[-1]["mf_gate_on"] = 1 if bool((debug_plan or {}).get("mf_gate_on", False)) else 0
        daily_rows[-1]["strong_risk_on"] = 1 if bool(ds.strong_risk_on) else 0
        cands_now = int((debug_plan or {}).get("buy_candidates_count", 0) or 0)
        slots_now = int((debug_plan or {}).get("buy_slots", 0) or 0)
        daily_rows[-1]["mf_rank_suppressed_by_strong_gate"] = (
            1
            if bool(enable_multifactor_rank) and (not bool(mf_gate_on_today)) and (cands_now > slots_now)
            else 0
        )

        if orders:
            pending[next_day] = [
                {
                    "side": o.side,
                    "symbol": str(o.symbol).lower(),
                    "qty": int(o.qty),
                    "reason_code": str(o.reason_code),
                    "meta": dict(o.meta or {}),
                }
                for o in orders
            ]

    simulation_seconds = float(time.perf_counter() - sim_t0)
    daily_df = pd.DataFrame(daily_rows)
    trades_df = pd.DataFrame(trade_rows)
    candidates_df = pd.DataFrame(candidate_rows)

    metrics = _compute_metrics(
        daily_df,
        trades_df,
        max_positions=max_positions,
        blocked_by_trend_count=0,
        total_buy_signals=provider.total_buy_signals,
        candidates_df=candidates_df,
        enable_strength_rank=bool(enable_strength_rank),
        strength_ma=int(strength_ma),
    )
    ec = provider.diag_reason_counts
    metrics["precompute_seconds"] = provider.precompute_seconds
    metrics["simulation_seconds"] = simulation_seconds
    metrics["notes"] = "breakout_provider=true; provider_based=true"
    metrics["candidate_diag_reason_counts"] = dict(ec)
    metrics["exit_atr_stop_count"] = int(ec.get("ATR_STOP_LOSS", 0))
    metrics["exit_atr_trail_count"] = int(ec.get("ATR_TRAIL_EXIT", 0))
    metrics["exit_take_profit_count"] = int(ec.get("TAKE_PROFIT", 0))
    metrics["exit_fixed_stop_count"] = int(ec.get("FIXED_STOP_LOSS", 0))
    metrics["exit_time_exit_count"] = int(ec.get("TIME_EXIT", 0))
    metrics["exit_signal_count"] = 0
    metrics["exit_ma20_count"] = int(ec.get("TREND_EXIT_MA20", 0))
    metrics["exit_low10_count"] = int(ec.get("TREND_EXIT_LOW10", 0))
    metrics["min_hold_block_count"] = provider.min_hold_block_count
    metrics["cooldown_block_count"] = provider.cooldown_block_count
    metrics["market_filter_bull_days"] = int(market_filter_bull_days)
    metrics["market_filter_bear_days"] = int(market_filter_bear_days)
    metrics["market_state_trans_down_days"] = int(market_state_trans_down_days)
    metrics["market_state_trans_up_days"] = int(market_state_trans_up_days)
    metrics["trade_mode_main_days"] = int(trade_mode_main_days)
    metrics["trade_mode_light_days"] = int(trade_mode_light_days)
    metrics["trade_mode_notrade_days"] = int(trade_mode_notrade_days)
    return PortfolioBacktestResult(daily=daily_df, trades=trades_df, candidates=candidates_df, metrics=metrics)


def _run_vector_portfolio_backtest_generic_signals(
    *,
    strategy: Any,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    trading_days: list[date],
    initial_cash: float,
    max_positions: int,
    lot_size: int,
    enable_strength_rank: bool,
    strength_ma: int,
    strength_top_k_mode: str,
    history_lookback_days: int | None,
    fast_mode: bool,
    debug_first_divergence: bool,
    enable_multifactor_rank: bool,
    mf_topk: int,
    mf_concentrate_topn: int,
    mf_concentrate_scale: float,
    mf_rank_gate_mode: str,
    momentum_top_pct: float = 0.0,
    cost_cfg: CostConfig | None = None,
    raw_history: pd.DataFrame | None = None,
    sector_data: Any = None,
    industry_map: Any = None,
    **_kwargs: Any,
) -> PortfolioBacktestResult:
    if history.empty:
        raise ValueError("history is empty")
    if not trading_days:
        raise ValueError("trading_days is empty")
    _uf_g = dict(getattr(strategy, "state", {}).get("universe_filters") or {})
    _min_trade_price = float(_uf_g.get("min_price", getattr(strategy, "min_price", 0.0)) or 0.0)

    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    # ── Sector gate for generic path ──
    _enable_sector_gate = bool(getattr(strategy, "enable_sector_gate", False))
    _sector_elig_mat_g: np.ndarray | None = None
    _sector_elig_col_g: dict[str, int] = {}
    if _enable_sector_gate and sector_data and industry_map:
        from backend.core.engine_vector.features import compute_sector_eligible
        _g_syms = sorted(set(hist["symbol"].astype(str)))
        _g_dates = np.array([pd.Timestamp(d) for d in trading_days])
        _sector_elig_mat_g = compute_sector_eligible(
            sector_data=sector_data,
            industry_map=industry_map,
            symbols=_g_syms,
            dates=_g_dates,
            window=int(getattr(strategy, "sector_rank_window", 60)),
            top_pct=float(getattr(strategy, "sector_top_pct", 0.30)),
        )
        _sector_elig_col_g = {s: j for j, s in enumerate(_g_syms)}

    bench = benchmark.copy()
    strong_risk_on_map: dict[date, bool] = {}
    if not bench.empty:
        bench["date"] = pd.to_datetime(bench["date"])
        bclose = pd.to_numeric(bench["close"], errors="coerce")
        bma120 = bclose.rolling(120, min_periods=120).mean()
        bma200 = bclose.rolling(200, min_periods=200).mean()
        for d, m120, m200 in zip(bench["date"], bma120, bma200):
            dt = pd.Timestamp(d).date()
            if pd.isna(m120) or pd.isna(m200):
                strong_risk_on_map[dt] = False
            else:
                strong_risk_on_map[dt] = bool(float(m120) > float(m200))
        bench["symbol"] = "bench:composite"
        bench = bench.sort_values(["date"]).reset_index(drop=True)
        combined = pd.concat([hist, bench], ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
    else:
        combined = hist

    # 成交执行使用不复权价格
    _raw_gs = raw_history if raw_history is not None else history
    _raw_gs_hist = _raw_gs.copy()
    _raw_gs_hist["date"] = pd.to_datetime(_raw_gs_hist["date"])
    _raw_gs_hist["symbol"] = _raw_gs_hist["symbol"].astype(str).str.lower()
    day_list = list(trading_days)
    open_idx, close_idx = build_backtest_price_indices(
        history=_raw_gs_hist,
        trading_days=day_list,
    )
    del _raw_gs_hist

    pending: dict[date, list[dict[str, Any]]] = {}
    positions: dict[str, int] = {}
    position_avg_cost: dict[str, float] = {}
    cash = float(initial_cash)
    peak_nav = float(initial_cash)
    prev_nav = float(initial_cash)
    blocked_by_trend_count = 0
    total_buy_signals = 0

    trade_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    debug_trace: dict[str, Any] = {}

    day_list = list(trading_days)
    combined_date_series = combined["date"]
    use_lookback = isinstance(history_lookback_days, int) and int(history_lookback_days) > 0
    lookback_n = int(history_lookback_days) if use_lookback else 0
    day_slice_end_combined: dict[pd.Timestamp, int] = {}
    day_slice_start_combined: dict[pd.Timestamp, int] = {}
    for day in day_list:
        ts = pd.Timestamp(day)
        day_slice_end_combined[ts] = int(combined_date_series.searchsorted(ts, side="right"))
    if use_lookback:
        for i, day in enumerate(day_list):
            ts = pd.Timestamp(day)
            start_day = day_list[max(0, i - lookback_n)]
            start_ts = pd.Timestamp(start_day)
            day_slice_start_combined[ts] = int(combined_date_series.searchsorted(start_ts, side="left"))
    else:
        for day in day_list:
            day_slice_start_combined[pd.Timestamp(day)] = 0

    mf_fast = _build_multifactor_and_fast_gate(strategy, hist, day_list)
    mf_fast_hits = 0

    _cc2 = cost_cfg if cost_cfg is not None else CostConfig()
    _slip_bps2 = _cc2.slippage_bps / 10000.0
    _comm_rate2 = _cc2.commission_rate
    _comm_min2 = _cc2.commission_min
    _stamp_rate2 = _cc2.stamp_tax_rate

    for i, day in enumerate(day_list):
        traded_value = 0.0
        for od in pending.pop(day, []):
            px = float(open_idx.get((day, od["symbol"]), 0.0) or 0.0)
            if px <= 0:
                continue
            if od["side"] == Side.SELL:
                held = int(positions.get(od["symbol"], 0))
                qty = min(held, int(od["qty"]))
                if qty <= 0:
                    continue
                fill_px = px * (1.0 - _slip_bps2)
                gross = qty * fill_px
                comm = max(_comm_min2, gross * _comm_rate2)
                stax = gross * _stamp_rate2
                net = gross - comm - stax
                cash += net
                traded_value += gross
                positions[od["symbol"]] = held - qty
                if positions[od["symbol"]] <= 0:
                    positions.pop(od["symbol"], None)
                    position_avg_cost.pop(od["symbol"], None)
                trade_rows.append(
                    {
                        "date": day.isoformat(),
                        "symbol": od["symbol"],
                        "side": "SELL",
                        "price": px,
                        "fill_price": round(fill_px, 4),
                        "qty": qty,
                        "value": round(gross, 2),
                        "commission": round(comm, 2),
                        "stamp_tax": round(stax, 2),
                        "slippage": round(abs(fill_px - px) * qty, 2),
                        "net_amount": round(net, 2),
                        "reason_code": od["reason_code"],
                        "triggered_rule": str((od.get("meta") or {}).get("triggered_rule", "")),
                        "break_streak": int((od.get("meta") or {}).get("break_streak", 0) or 0),
                        "meta_json": json.dumps(od.get("meta") or {}, ensure_ascii=False),
                    }
                )
            else:
                if _min_trade_price > 0 and px < _min_trade_price:
                    continue
                qty = int(od["qty"])
                fill_px = px * (1.0 + _slip_bps2)
                gross = qty * fill_px
                comm = max(_comm_min2, gross * _comm_rate2)
                net = gross + comm
                if qty <= 0 or net > cash:
                    continue
                cash -= net
                traded_value += gross
                prev_qty = int(positions.get(od["symbol"], 0))
                prev_avg = float(position_avg_cost.get(od["symbol"], 0.0))
                new_qty = prev_qty + qty
                new_avg = ((prev_qty * prev_avg) + (qty * fill_px)) / float(new_qty) if new_qty > 0 else 0.0
                positions[od["symbol"]] = new_qty
                position_avg_cost[od["symbol"]] = float(new_avg)
                trade_rows.append(
                    {
                        "date": day.isoformat(),
                        "symbol": od["symbol"],
                        "side": "BUY",
                        "price": px,
                        "fill_price": round(fill_px, 4),
                        "qty": qty,
                        "value": round(gross, 2),
                        "commission": round(comm, 2),
                        "stamp_tax": 0.0,
                        "slippage": round(abs(fill_px - px) * qty, 2),
                        "net_amount": round(net, 2),
                        "reason_code": od["reason_code"],
                        "triggered_rule": str((od.get("meta") or {}).get("triggered_rule", "")),
                        "break_streak": int((od.get("meta") or {}).get("break_streak", 0) or 0),
                        "meta_json": json.dumps(od.get("meta") or {}, ensure_ascii=False),
                    }
                )

        nav, market_value, pos_values = compute_nav_snapshot(cash=cash, positions=positions, close_idx=close_idx, day=day)
        peak_nav = max(peak_nav, nav)
        daily_ret = (nav / prev_nav - 1.0) if prev_nav > 0 else 0.0
        drawdown = (nav / peak_nav - 1.0) if peak_nav > 0 else 0.0
        gross_exposure = (market_value / nav) if nav > 0 else 0.0
        turnover_pct = (traded_value / prev_nav) if prev_nav > 0 else 0.0
        top5 = [{"symbol": s, "value": round(v, 2)} for s, v in sorted(pos_values, key=lambda x: x[1], reverse=True)[:5]]
        daily_rows.append(
            {
                "date": day.isoformat(),
                "nav": nav,
                "cash": cash,
                "positions_count": len(positions),
                "daily_return": daily_ret,
                "drawdown": drawdown,
                "gross_exposure": gross_exposure,
                "turnover_pct": turnover_pct,
                "top5_positions_json": json.dumps(top5, ensure_ascii=False),
                "candidates_count": 0,
                "selected_count": 0,
                "top5_selected_strength_json": "[]",
                "top5_rejected_strength_json": "[]",
                "buy_slots_before_buy": 0,
                "mean_order_value_scale": 0.0,
                "weak_trend_buy_rate": 0.0,
                "strong_trend_buy_rate": 0.0,
                "mf_rank_applied": 0,
                "mf_gate_on": 0,
            }
        )
        prev_nav = nav

        if i >= len(day_list) - 1:
            continue
        next_day = day_list[i + 1]

        day_ts = pd.Timestamp(day)
        history_view = combined.iloc[day_slice_start_combined[day_ts] : day_slice_end_combined[day_ts]]
        strategy_positions = {
            sym: Position(symbol=sym, total_qty=int(q), sellable_qty=int(q), avg_cost=float(position_avg_cost.get(sym, 0.0)))
            for sym, q in positions.items()
            if int(q) > 0
        }
        strategy.state["base_order_value"] = float(nav) / float(max_positions) if int(max_positions) > 0 else 0.0
        sell_sigs: list[Signal] = []
        buy_sigs: list[Signal] = []
        if mf_fast is not None:
            base_strategy = mf_fast["base"]
            base_strategy.state["base_order_value"] = float(nav) / float(max_positions) if int(max_positions) > 0 else 0.0
            base_sigs = base_strategy.generate_signals(day, history_view, strategy_positions)
            dts = pd.Timestamp(day).normalize()
            pass_set: set[str] | None = None
            for fs in mf_fast["factor_sets"]:
                s = fs.get(dts, set())
                pass_set = set(s) if pass_set is None else (pass_set & set(s))
            pass_set = pass_set or set()
            for sig in base_sigs:
                sig_action = str(sig.action or sig.side.value).upper()
                if sig.side == Side.BUY:
                    total_buy_signals += 1
                    if str(sig.action or "").upper() == "BLOCKED" and str(sig.reason_code or "") == "BUY_BLOCKED_TREND_FILTER":
                        blocked_by_trend_count += 1
                if sig_action == "BLOCKED":
                    continue
                if sig.side == Side.SELL:
                    sell_sigs.append(sig)
                elif sig.side == Side.BUY and str(sig.symbol).lower() in pass_set:
                    buy_sigs.append(sig)
            mf_fast_hits += 1
        else:
            sigs = strategy.generate_signals(day, history_view, strategy_positions)
            for sig in sigs:
                sig_action = str(sig.action or sig.side.value).upper()
                if sig.side == Side.BUY:
                    total_buy_signals += 1
                    if str(sig.action or "").upper() == "BLOCKED" and str(sig.reason_code or "") == "BUY_BLOCKED_TREND_FILTER":
                        blocked_by_trend_count += 1
                if sig_action == "BLOCKED":
                    continue
                if sig.side == Side.SELL:
                    sell_sigs.append(sig)
                elif sig.side == Side.BUY:
                    buy_sigs.append(sig)

        # ── Sector gate filter (generic path) ──
        if _sector_elig_mat_g is not None:
            buy_sigs = [
                s for s in buy_sigs
                if (_sc := _sector_elig_col_g.get(str(s.symbol).lower())) is not None
                and bool(_sector_elig_mat_g[i, _sc])
            ]

        next_open = {
            s: float(open_idx.get((next_day, s), 0.0) or 0.0)
            for s in set([str(x.symbol).lower() for x in sell_sigs + buy_sigs] + list(positions.keys()))
        }
        day_candidate_rows: list[dict[str, Any]] = []
        # Keep debug_plan always-on for fast_mode metrics parity:
        # candidates/slots/selected stats depend on planner outputs even when
        # candidate_audit rows are disabled.
        debug_plan: dict[str, Any] = {}
        regime_on_today = bool(strategy.state.get("regime_on", True))
        strong_risk_on_today = bool(strong_risk_on_map.get(day, False))
        strategy.state["strong_risk_on"] = bool(strong_risk_on_today)
        mf_gate_on_today = resolve_mf_gate_on_today(
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_rank_gate_mode=str(mf_rank_gate_mode or "ALWAYS_ON"),
            risk_on_today=bool(regime_on_today),
            strong_risk_on_today=bool(strong_risk_on_today),
            market_state_today=str(strategy.state.get("market_state", "") or ""),
        )
        orders = build_rebalance_orders(
            positions=positions,
            cash_available=cash,
            nav_close=nav,
            max_positions=max_positions,
            lot_size=lot_size,
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            next_open=next_open,
            enable_strength_rank=bool(enable_strength_rank),
            strength_ma=int(strength_ma),
            strength_top_k_mode=str(strength_top_k_mode),
            strength_map={},
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_topk=int(mf_topk),
            mf_concentrate_topn=int(mf_concentrate_topn),
            mf_concentrate_scale=float(mf_concentrate_scale),
            mf_gate_on_today=bool(mf_gate_on_today),
            mf_score_map={},
            momentum_top_pct=float(momentum_top_pct),
            decision_date=day,
            candidate_audit=(None if bool(fast_mode) else day_candidate_rows),
            debug_plan=debug_plan,
            weight_mode="equal",
            min_positions=10,
            min_trade_price=float(_min_trade_price),
            decision_close_map={sym: float(close_idx.get((day, sym), 0.0) or 0.0) for sym in next_open},
            enable_entry_gap_guard=bool(getattr(strategy, "enable_entry_gap_guard", False)),
            entry_gap_guard_pct=float(getattr(strategy, "entry_gap_guard_pct", 0.0) or 0.0),
            candidate_plan_mode=candidate_plan_mode,
            cash_aware_search_top_n=cash_aware_search_top_n,
            holding_entry_dates=dict(getattr(strategy, "entry_day", {}) or {}),
            strong_risk_on_today=bool(strong_risk_on_today),
            rotation_replace_enabled=rotation_replace_enabled,
            rotation_replace_only_strong_risk_on=rotation_replace_only_strong_risk_on,
            rotation_replace_max_swaps_per_day=rotation_replace_max_swaps_per_day,
            rotation_replace_candidate_top_n=rotation_replace_candidate_top_n,
            rotation_replace_min_score_gap=rotation_replace_min_score_gap,
            rotation_min_hold_days=int(getattr(strategy, "min_hold_days", 0) or 0),
        )
        if not bool(fast_mode):
            candidate_rows.extend(day_candidate_rows)
            cands = [r for r in day_candidate_rows if bool(r.get("is_candidate"))]
            sel = [r for r in cands if bool(r.get("selected"))]
            rej = [r for r in cands if not bool(r.get("selected"))]
            daily_rows[-1]["candidates_count"] = int(len(cands))
            daily_rows[-1]["selected_count"] = int(len(sel))
            daily_rows[-1]["top5_selected_strength_json"] = json.dumps(
                [{"symbol": r.get("symbol"), "strength": r.get("strength")} for r in sel[:5]],
                ensure_ascii=False,
            )
            daily_rows[-1]["top5_rejected_strength_json"] = json.dumps(
                [{"symbol": r.get("symbol"), "strength": r.get("strength"), "reason": r.get("reject_reason")} for r in rej[:5]],
                ensure_ascii=False,
            )
        else:
            daily_rows[-1]["candidates_count"] = int((debug_plan or {}).get("buy_candidates_count", 0))
            daily_rows[-1]["selected_count"] = int(len((debug_plan or {}).get("selected_symbols", [])))
        daily_rows[-1]["buy_slots_before_buy"] = int((debug_plan or {}).get("buy_slots", 0))

        selected_scales = list((debug_plan or {}).get("selected_order_value_scales", []) or [])
        weak_selected_count = int((debug_plan or {}).get("weak_trend_selected_count", 0) or 0)
        strong_selected_count = int((debug_plan or {}).get("strong_trend_selected_count", 0) or 0)
        selected_n_dbg = int(len((debug_plan or {}).get("selected_symbols", []) or []))
        daily_rows[-1]["mean_order_value_scale"] = (
            float(sum(float(x) for x in selected_scales) / len(selected_scales))
            if len(selected_scales) > 0
            else 0.0
        )
        daily_rows[-1]["weak_trend_buy_rate"] = (
            float(weak_selected_count) / float(selected_n_dbg)
            if selected_n_dbg > 0
            else 0.0
        )
        daily_rows[-1]["strong_trend_buy_rate"] = (
            float(strong_selected_count) / float(selected_n_dbg)
            if selected_n_dbg > 0
            else 0.0
        )
        daily_rows[-1]["mf_rank_triggered"] = 1 if bool((debug_plan or {}).get("mf_rank_triggered", False)) else 0
        daily_rows[-1]["mf_rank_applied"] = 1 if bool((debug_plan or {}).get("mf_rank_applied", False)) else 0
        daily_rows[-1]["mf_candidates_when_triggered"] = int((debug_plan or {}).get("mf_candidates_when_triggered", 0) or 0)
        daily_rows[-1]["mf_topk_reject_count"] = int((debug_plan or {}).get("mf_topk_reject_count", 0) or 0)
        daily_rows[-1]["mf_concentrated_selected_count"] = int((debug_plan or {}).get("mf_concentrated_selected_count", 0) or 0)
        daily_rows[-1]["mf_gate_on"] = 1 if bool((debug_plan or {}).get("mf_gate_on", False)) else 0
        daily_rows[-1]["strong_risk_on"] = 1 if bool(strong_risk_on_today) else 0
        cands_now = int((debug_plan or {}).get("buy_candidates_count", 0) or 0)
        slots_now = int((debug_plan or {}).get("buy_slots", 0) or 0)
        daily_rows[-1]["mf_rank_suppressed_by_strong_gate"] = (
            1
            if bool(enable_multifactor_rank) and (not bool(mf_gate_on_today)) and (cands_now > slots_now)
            else 0
        )

        if debug_first_divergence:
            debug_trace[day.isoformat()] = {
                "cash_before": float(cash),
                "held_symbols_before": {str(k): int(v) for k, v in positions.items() if int(v) > 0},
                "buy_candidates_count": int((debug_plan or {}).get("buy_candidates_count", 0)),
                "buy_slots": int((debug_plan or {}).get("buy_slots", 0)),
                "sorted_selected_symbols": list((debug_plan or {}).get("selected_symbols", [])),
                "buys_executed": list((debug_plan or {}).get("buys_executed", [])),
                "positions_after": {str(k): int(v) for k, v in positions.items() if int(v) > 0},
                "nav_end_of_day": float(nav),
            }

        if orders:
            pending[next_day] = [
                {
                    "side": o.side,
                    "symbol": str(o.symbol).lower(),
                    "qty": int(o.qty),
                    "reason_code": str(o.reason_code),
                    "meta": dict(o.meta or {}),
                }
                for o in orders
            ]

    daily_df = pd.DataFrame(daily_rows)
    trades_df = pd.DataFrame(trade_rows)
    candidates_df = pd.DataFrame(candidate_rows)
    metrics = _compute_metrics(
        daily_df,
        trades_df,
        max_positions=max_positions,
        blocked_by_trend_count=blocked_by_trend_count,
        total_buy_signals=total_buy_signals,
        candidates_df=candidates_df,
        enable_strength_rank=bool(enable_strength_rank),
        strength_ma=int(strength_ma),
    )
    metrics["notes"] = "preindex=false; held_only_sell=false; one_shot_write=true; generic_signals=true"
    if debug_first_divergence:
        metrics["debug_trace"] = debug_trace
    metrics["multifactor_fast_gate_days"] = int(mf_fast_hits)
    return PortfolioBacktestResult(daily=daily_df, trades=trades_df, candidates=candidates_df, metrics=metrics)
