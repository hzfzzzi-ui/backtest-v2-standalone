"""Breakout provider runtime implementation."""

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
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today
from backend.core.engine_vector.multifactor_rank import build_daily_multifactor_scores
from backend.core.engine_vector.signal_matrix import build_signal_matrices
from backend.core.portfolio.metrics import compute_backtest_metrics
from backend.core.portfolio.nav_snapshot import compute_nav_snapshot
from backend.core.portfolio.portfolio_runtime import build_rebalance_orders
from backend.core.portfolio.price_index import build_backtest_price_indices
from backend.core.portfolio.sizing import calc_buy_slots
from backend.core.portfolio.types import PortfolioBacktestResult
from backend.core.strategies.breakout_trend import BreakoutTrendStrategy
from backend.core.strategies.composite_strategy import CompositeStrategy
from backend.core.strategies.ema_cross import EMACrossStrategy
from backend.core.strategies.regime_router import RegimeRouter
from backend.core.strategies.sma_cross import SMACrossStrategy

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

    metrics = compute_backtest_metrics(
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

