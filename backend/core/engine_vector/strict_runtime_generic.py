"""Generic inline runtime implementation and fast multifactor gate."""

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
from backend.core.engine_vector.multifactor_fast_gate import (
    build_multifactor_fast_gate as _build_multifactor_and_fast_gate,
)
from backend.core.engine_vector.multifactor_rank import build_daily_multifactor_scores
from backend.core.engine_vector.signal_matrix import build_signal_matrices
from backend.core.portfolio.metrics import compute_backtest_metrics
from backend.core.portfolio.nav_snapshot import compute_nav_snapshot
from backend.core.portfolio.portfolio_runtime import build_rebalance_orders
from backend.core.portfolio.price_index import build_backtest_hfq_indices, build_backtest_price_indices
from backend.core.portfolio.sizing import calc_buy_slots
from backend.core.portfolio.types import PortfolioBacktestResult
from backend.core.strategies.breakout_trend import BreakoutTrendStrategy
from backend.core.strategies.composite_strategy import CompositeStrategy
from backend.core.strategies.ema_cross import EMACrossStrategy
from backend.core.strategies.regime_router import RegimeRouter
from backend.core.strategies.sma_cross import SMACrossStrategy


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
    hfq_close_idx, adj_factor_idx = build_backtest_hfq_indices(
        history=_raw_gs_hist,
        trading_days=day_list,
    )
    del _raw_gs_hist

    pending: dict[date, list[dict[str, Any]]] = {}
    positions: dict[str, int] = {}
    position_avg_cost: dict[str, float] = {}
    position_entry_adj: dict[str, float] = {}
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
                    position_entry_adj.pop(od["symbol"], None)
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
                prev_entry_adj = float(position_entry_adj.get(od["symbol"], 1.0) or 1.0)
                new_qty = prev_qty + qty
                new_avg = ((prev_qty * prev_avg) + (qty * fill_px)) / float(new_qty) if new_qty > 0 else 0.0
                positions[od["symbol"]] = new_qty
                position_avg_cost[od["symbol"]] = float(new_avg)
                buy_entry_adj = float(adj_factor_idx.get((day, od["symbol"]), 1.0) or 1.0)
                denom = (float(prev_qty) / max(prev_entry_adj, 1e-8)) + (float(qty) / max(buy_entry_adj, 1e-8))
                position_entry_adj[od["symbol"]] = (float(new_qty) / denom) if denom > 1e-8 else 1.0
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

        nav, market_value, pos_values = compute_nav_snapshot(
            cash=cash,
            positions=positions,
            close_idx=close_idx,
            day=day,
            hfq_close_idx=hfq_close_idx,
            position_entry_adj=position_entry_adj,
        )
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
            overlay_mode=str(getattr(ds, "overlay_mode", "off") or "off"),
            overlay_gate_on_today=bool(getattr(ds, "overlay_gate_on_today", False)),
            overlay_score_map=dict(getattr(ds, "overlay_score_map", {}) or {}),
            overlay_band_limit=int(getattr(ds, "overlay_band_limit", 0) or 0),
            overlay_observation_date=getattr(ds, "overlay_observation_date", None),
            overlay_score_source=str(getattr(ds, "overlay_score_source", "") or ""),
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
        daily_rows[-1]["moneyflow_overlay_enabled"] = 1 if bool((debug_plan or {}).get("moneyflow_overlay_enabled", False)) else 0
        daily_rows[-1]["moneyflow_overlay_mode"] = str((debug_plan or {}).get("moneyflow_overlay_mode", "off") or "off")
        daily_rows[-1]["moneyflow_overlay_gate_on"] = 1 if bool((debug_plan or {}).get("moneyflow_overlay_gate_on", False)) else 0
        daily_rows[-1]["moneyflow_overlay_observation_date"] = str((debug_plan or {}).get("moneyflow_overlay_observation_date", "") or "")
        daily_rows[-1]["moneyflow_overlay_score_source"] = str((debug_plan or {}).get("moneyflow_overlay_score_source", "") or "")
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
    metrics = compute_backtest_metrics(
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


