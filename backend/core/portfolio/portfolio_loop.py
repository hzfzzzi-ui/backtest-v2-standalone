"""Portfolio loop implementation.

This module hosts the preserved `run_portfolio_backtest` daily loop while
shared helpers live in `portfolio_runtime.py`.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd

from backend.core.config.models import (
    BenchmarkRegimeConfig,
    BreadthConfig,
    CostConfig,
    ExitConfig,
    MarketFilterConfig,
    RiskBudgetConfig,
    RiskConfig,
    SizingConfig,
)
from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from backend.core.portfolio.portfolio_runtime import (
    _compute_metrics,
    _estimate_buy_slots_after_sell,
    build_backtest_price_indices,
    build_rebalance_orders,
    compute_nav_snapshot,
    resolve_mf_gate_on_today,
)
from backend.core.portfolio.types import PortfolioBacktestResult, PortfolioOrder
from backend.core.strategies.base import Strategy


def run_portfolio_backtest(
    *,
    strategy: Strategy,
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
    engine_mode: str = "SLOW_AUDIT",
    fast_mode: bool = False,
    debug_first_divergence: bool = False,
    enable_multifactor_rank: bool = False,
    mf_topk: int = 10,
    mf_concentrate_topn: int = 3,
    mf_concentrate_scale: float = 1.5,
    mf_rank_gate_mode: str = "ALWAYS_ON",
    momentum_top_pct: float = 0.0,
    cost_cfg: CostConfig | None = None,
    exit_cfg: ExitConfig | None = None,
    risk_cfg: RiskConfig | None = None,
    sizing_cfg: SizingConfig | None = None,
    raw_history: pd.DataFrame | None = None,
    base_order_value: float = 0.0,
    st_history: pd.DataFrame | None = None,
    sector_data: dict[str, pd.DataFrame] | None = None,
    industry_map: dict[str, str] | None = None,
    industry_history: pd.DataFrame | None = None,
    risk_budget_cfg: RiskBudgetConfig | None = None,
    market_filter_cfg: MarketFilterConfig | None = None,
    benchmark_regime_cfg: BenchmarkRegimeConfig | None = None,
    breadth_cfg: BreadthConfig | None = None,
) -> PortfolioBacktestResult:
    if str(engine_mode).upper() == "VECTOR_FAST_STRICT":
        from backend.core.engine_vector.strict_runtime import run_vector_portfolio_backtest

        return run_vector_portfolio_backtest(
            strategy=strategy,
            history=history,
            benchmark=benchmark,
            trading_days=trading_days,
            benchmark_symbol=benchmark_symbol,
            initial_cash=initial_cash,
            max_positions=max_positions,
            lot_size=lot_size,
            enable_strength_rank=enable_strength_rank,
            strength_ma=strength_ma,
            strength_top_k_mode=strength_top_k_mode,
            history_lookback_days=history_lookback_days,
            fast_mode=bool(fast_mode),
            debug_first_divergence=bool(debug_first_divergence),
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_topk=int(mf_topk),
            mf_concentrate_topn=int(mf_concentrate_topn),
            mf_concentrate_scale=float(mf_concentrate_scale),
            mf_rank_gate_mode=str(mf_rank_gate_mode),
            momentum_top_pct=float(momentum_top_pct),
            cost_cfg=cost_cfg,
            exit_cfg=exit_cfg,
            risk_cfg=risk_cfg,
            sizing_cfg=sizing_cfg,
            raw_history=raw_history,
            base_order_value=float(base_order_value),
            st_history=st_history,
            sector_data=sector_data,
            industry_map=industry_map,
            industry_history=industry_history,
            risk_budget_cfg=risk_budget_cfg,
            market_filter_cfg=market_filter_cfg,
            benchmark_regime_cfg=benchmark_regime_cfg,
            breadth_cfg=breadth_cfg,
        )
    if history.empty:
        raise ValueError("history is empty")
    if not trading_days:
        raise ValueError("trading_days is empty")

    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    bench = benchmark.copy()
    if not bench.empty:
        bench["date"] = pd.to_datetime(bench["date"])
        bench["symbol"] = f"BENCH:{benchmark_symbol}"
        bench = bench.sort_values(["date"]).reset_index(drop=True)
    # Build one combined history table once, avoid per-day concat in main loop.
    if not bench.empty:
        combined = pd.concat([hist, bench], ignore_index=True)
        combined = combined.sort_values(["date", "symbol"]).reset_index(drop=True)
    else:
        combined = hist
    combined_date_series = combined["date"]

    open_idx, close_idx = build_backtest_price_indices(
        history=hist,
        trading_days=trading_days,
    )

    pending: dict[date, list[PortfolioOrder]] = {}
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
    _sc_cfg = sizing_cfg if isinstance(sizing_cfg, SizingConfig) else SizingConfig()
    _weight_mode_cfg = str(_sc_cfg.weight_mode or "equal")
    _min_positions_cfg = int(_sc_cfg.min_positions)
    _tilt_strength_cfg = float(_sc_cfg.tilt_strength)
    _tilt_top_n_cfg = int(_sc_cfg.tilt_top_n)
    _tilt_bottom_n_cfg = int(_sc_cfg.tilt_bottom_n)
    _score_weight_min_scale_cfg = float(_sc_cfg.score_weight_min_scale)
    _score_weight_max_scale_cfg = float(_sc_cfg.score_weight_max_scale)
    _candidate_plan_mode_cfg = str(_sc_cfg.candidate_plan_mode or "ranked")
    _cash_aware_search_top_n_cfg = int(_sc_cfg.cash_aware_search_top_n)
    _rotation_replace_enabled_cfg = bool(_sc_cfg.rotation_replace_enabled)
    _rotation_replace_only_strong_risk_on_cfg = bool(_sc_cfg.rotation_replace_only_strong_risk_on)
    _rotation_replace_max_swaps_per_day_cfg = int(_sc_cfg.rotation_replace_max_swaps_per_day)
    _rotation_replace_candidate_top_n_cfg = int(_sc_cfg.rotation_replace_candidate_top_n)
    _rotation_replace_min_score_gap_cfg = float(_sc_cfg.rotation_replace_min_score_gap)

    day_list = list(trading_days)
    # Precompute per-day slice end offsets to avoid repeated full DataFrame scans.
    day_slice_end_combined: dict[pd.Timestamp, int] = {}
    day_slice_start_combined: dict[pd.Timestamp, int] = {}
    use_lookback = isinstance(history_lookback_days, int) and int(history_lookback_days) > 0
    lookback_n = int(history_lookback_days) if use_lookback else 0
    for day in day_list:
        day_ts = pd.Timestamp(day)
        day_slice_end_combined[day_ts] = int(combined_date_series.searchsorted(day_ts, side="right"))
    if use_lookback:
        for i, day in enumerate(day_list):
            day_ts = pd.Timestamp(day)
            start_day = day_list[max(0, i - lookback_n)]
            start_ts = pd.Timestamp(start_day)
            day_slice_start_combined[day_ts] = int(combined_date_series.searchsorted(start_ts, side="left"))
    else:
        for day in day_list:
            day_slice_start_combined[pd.Timestamp(day)] = 0

    # Precompute strength(close/MA-1) lookup by (date, symbol) once.
    strength_lookup: dict[tuple[pd.Timestamp, str], float | None] = {}
    if enable_strength_rank:
        strength_src = hist[["date", "symbol", "close"]].copy()
        strength_src["close"] = pd.to_numeric(strength_src["close"], errors="coerce")
        strength_src["strength_ma"] = (
            strength_src.groupby("symbol", sort=False)["close"]
            .transform(lambda s: s.rolling(int(strength_ma)).mean())
        )
        strength_src["strength"] = (
            strength_src["close"] / strength_src["strength_ma"] - 1.0
        )
        for row in strength_src.itertuples(index=False):
            key = (pd.Timestamp(row.date), str(row.symbol))
            val = None
            try:
                if pd.notna(row.strength):
                    val = float(row.strength)
            except Exception:
                val = None
            strength_lookup[key] = val

    for i, day in enumerate(day_list):
        traded_value = 0.0
        for od in pending.pop(day, []):
            px = float(open_idx.get((day, od.symbol), 0.0) or 0.0)
            if px <= 0:
                continue
            if od.side == Side.SELL:
                held = int(positions.get(od.symbol, 0))
                qty = min(held, int(od.qty))
                if qty <= 0:
                    continue
                value = qty * px
                cash += value
                traded_value += value
                positions[od.symbol] = held - qty
                if positions[od.symbol] <= 0:
                    positions.pop(od.symbol, None)
                    position_avg_cost.pop(od.symbol, None)
                trade_rows.append(
                    {
                        "date": day.isoformat(),
                        "symbol": od.symbol,
                        "side": "SELL",
                        "price": px,
                        "qty": qty,
                        "value": value,
                        "reason_code": od.reason_code,
                        "triggered_rule": str((od.meta or {}).get("triggered_rule", "")),
                        "break_streak": int((od.meta or {}).get("break_streak", 0) or 0),
                        "meta_json": json.dumps(od.meta or {}, ensure_ascii=False),
                    }
                )
            else:
                qty = int(od.qty)
                value = qty * px
                if qty <= 0 or value > cash:
                    continue
                cash -= value
                traded_value += value
                prev_qty = int(positions.get(od.symbol, 0))
                prev_avg = float(position_avg_cost.get(od.symbol, 0.0))
                new_qty = prev_qty + qty
                new_avg = ((prev_qty * prev_avg) + (qty * px)) / float(new_qty) if new_qty > 0 else 0.0
                positions[od.symbol] = new_qty
                position_avg_cost[od.symbol] = float(new_avg)
                trade_rows.append(
                    {
                        "date": day.isoformat(),
                        "symbol": od.symbol,
                        "side": "BUY",
                        "price": px,
                        "qty": qty,
                        "value": value,
                        "reason_code": od.reason_code,
                        "triggered_rule": str((od.meta or {}).get("triggered_rule", "")),
                        "break_streak": int((od.meta or {}).get("break_streak", 0) or 0),
                        "meta_json": json.dumps(od.meta or {}, ensure_ascii=False),
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
        sigs = strategy.generate_signals(day, history_view, strategy_positions)
        sell_sigs: list[Signal] = []
        buy_sigs: list[Signal] = []
        day_gate_by_symbol: dict[str, dict[str, Any]] = {}
        raw_buy_candidates: list[str] = []
        for sig in sigs:
            sig_side = str(sig.side.value).upper()
            sig_action = str(sig.action or sig.side.value).upper()
            if sig_side == "BUY":
                sym_k = str(sig.symbol).lower()
                raw_buy_candidates.append(sym_k)
                meta_d = dict(sig.meta) if isinstance(sig.meta, dict) else {}
                day_gate_by_symbol[sym_k] = {
                    "cross_up": str(sig.reason_code or sig.reason or "").upper()
                    in {
                        "SMA_CROSS_UP",
                        "EMA_CROSS_UP",
                        "SMA_CROSS_UP_BLOCKED",
                        "EMA_CROSS_UP_BLOCKED",
                        "ENTRY_BUFFER_BLOCKED",
                        "BUY_BLOCKED_TREND_FILTER",
                    },
                    "entry_buffer_ok": bool(meta_d.get("buffer_ok")) if "buffer_ok" in meta_d else None,
                    "trend_ok": bool(meta_d.get("trend_ok")) if "trend_ok" in meta_d else None,
                    "regime_ok": bool(meta_d.get("regime_on")) if "regime_on" in meta_d else None,
                    "tradable": None,
                    "ma_is_valid": (meta_d.get("slow_ma") is not None and meta_d.get("fast_ma") is not None),
                    "close": meta_d.get("close"),
                    "fast_ma": meta_d.get("fast_ma"),
                    "slow_ma": meta_d.get("slow_ma"),
                    "fast_ma_prev": meta_d.get("fast_ma_prev"),
                    "slow_ma_prev": meta_d.get("slow_ma_prev"),
                    "ma120": meta_d.get("ma120", meta_d.get("trend_fast_value")),
                    "ma200": meta_d.get("ma200", meta_d.get("trend_slow_value")),
                    "trend_fast": meta_d.get("trend_fast_value"),
                    "trend_slow": meta_d.get("trend_slow_value"),
                    "reason_code": str(sig.reason_code or sig.reason or ""),
                }
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
        buy_slots_before_buy = _estimate_buy_slots_after_sell(
            positions=positions,
            sell_signals=sell_sigs,
            max_positions=max_positions,
        )

        next_open = {
            sym: float(open_idx.get((next_day, sym), 0.0) or 0.0)
            for sym in set([str(s.symbol).lower() for s in sell_sigs + buy_sigs] + list(positions.keys()))
        }
        for sym in raw_buy_candidates:
            g = day_gate_by_symbol.setdefault(sym, {})
            px = float(next_open.get(sym, 0.0) or 0.0)
            g["open_next"] = px
            g["tradable"] = bool(px > 0)
            rc = str((g.get("reason_code") or "")).upper()
            if not rc:
                # derive from signals list
                for s in sigs:
                    if str(s.symbol).lower() == sym and str(s.side.value).upper() == "BUY":
                        rc = str(s.reason_code or s.reason or "").upper()
                        break
            g["buy_raw_ok"] = rc in {"SMA_CROSS_UP", "EMA_CROSS_UP"}
        strength_map: dict[str, float | None] = {}
        if enable_strength_rank and buy_sigs:
            for sig in buy_sigs:
                sym_l = str(sig.symbol).lower()
                strength_map[sym_l] = strength_lookup.get((day_ts, sym_l))
        day_candidate_rows: list[dict[str, Any]] = []
        debug_plan: dict[str, Any] = {}
        regime_on_today = bool(strategy.state.get("regime_on", True))
        strong_risk_on_today = bool(strategy.state.get("strong_risk_on", regime_on_today))
        mf_gate_on_today = resolve_mf_gate_on_today(
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_rank_gate_mode=str(mf_rank_gate_mode or "ALWAYS_ON"),
            risk_on_today=bool(regime_on_today),
            strong_risk_on_today=bool(strong_risk_on_today),
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
            strength_map=strength_map,
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_topk=int(mf_topk),
            mf_concentrate_topn=int(mf_concentrate_topn),
            mf_concentrate_scale=float(mf_concentrate_scale),
            mf_gate_on_today=bool(mf_gate_on_today),
            mf_score_map={},
            decision_date=day,
            candidate_audit=day_candidate_rows,
            debug_plan=debug_plan,
            weight_mode=_weight_mode_cfg,
            min_positions=_min_positions_cfg,
            tilt_strength=_tilt_strength_cfg,
            tilt_top_n=_tilt_top_n_cfg,
            tilt_bottom_n=_tilt_bottom_n_cfg,
            min_trade_price=float(getattr(strategy, "min_price", 0.0) or 0.0),
            decision_close_map={
                str(sig.symbol).lower(): float(close_idx.get((day, str(sig.symbol).lower()), 0.0) or 0.0)
                for sig in buy_sigs
            },
            enable_entry_gap_guard=bool(getattr(strategy, "enable_entry_gap_guard", False)),
            entry_gap_guard_pct=float(getattr(strategy, "entry_gap_guard_pct", 0.0) or 0.0),
            score_weight_min_scale=_score_weight_min_scale_cfg,
            score_weight_max_scale=_score_weight_max_scale_cfg,
            candidate_plan_mode=_candidate_plan_mode_cfg,
            cash_aware_search_top_n=_cash_aware_search_top_n_cfg,
            holding_entry_dates=dict(getattr(strategy, "entry_day", {}) or {}),
            strong_risk_on_today=bool(strong_risk_on_map.get(day, False)),
            rotation_replace_enabled=_rotation_replace_enabled_cfg,
            rotation_replace_only_strong_risk_on=_rotation_replace_only_strong_risk_on_cfg,
            rotation_replace_max_swaps_per_day=_rotation_replace_max_swaps_per_day_cfg,
            rotation_replace_candidate_top_n=_rotation_replace_candidate_top_n_cfg,
            rotation_replace_min_score_gap=_rotation_replace_min_score_gap_cfg,
            rotation_min_hold_days=int(getattr(strategy, "min_hold_days", 0) or 0),
        )
        if debug_first_divergence:
            rank_pos_map: dict[str, int] = {}
            for idx_rank, row in enumerate([r for r in day_candidate_rows if bool(r.get("is_candidate"))], start=1):
                rank_pos_map[str(row.get("symbol", "")).lower()] = int(idx_rank)
                gate = day_gate_by_symbol.setdefault(str(row.get("symbol", "")).lower(), {})
                gate["rank_position"] = int(idx_rank)
                gate["strength_value"] = row.get("strength")
            sell_list: list[dict[str, Any]] = []
            held_before = {str(k): int(v) for k, v in positions.items() if int(v) > 0}
            for sig in sell_sigs:
                sym = str(sig.symbol).lower()
                qh = int(held_before.get(sym, 0))
                q = qh if int(sig.qty) <= 0 else min(qh, int(sig.qty))
                if q <= 0:
                    continue
                sell_list.append(
                    {
                        "symbol": sym,
                        "reason": str(sig.reason_code or sig.reason or "SELL"),
                        "next_open_price": float(next_open.get(sym, 0.0) or 0.0),
                        "qty": int(q),
                    }
                )
            debug_trace[day.isoformat()] = {
                "cash_before": float(cash),
                "held_symbols_before": held_before,
                "sell_list": sell_list,
                "buy_candidates_raw": sorted(list(set(raw_buy_candidates))),
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
        candidate_rows.extend(day_candidate_rows)
        if daily_rows:
            candidates_only = [r for r in day_candidate_rows if bool(r.get("is_candidate"))]
            selected = [r for r in candidates_only if bool(r.get("selected"))]
            rejected = [r for r in candidates_only if not bool(r.get("selected"))]
            selected_sorted = sorted(
                selected,
                key=lambda x: (x.get("strength") is not None, float(x.get("strength") or -1e18)),
                reverse=True,
            )[:5]
            rejected_sorted = sorted(
                rejected,
                key=lambda x: (x.get("strength") is not None, float(x.get("strength") or -1e18)),
                reverse=True,
            )[:5]
            daily_rows[-1]["candidates_count"] = int(len(candidates_only))
            daily_rows[-1]["selected_count"] = int(len(selected))
            daily_rows[-1]["top5_selected_strength_json"] = json.dumps(
                [{"symbol": r.get("symbol"), "strength": r.get("strength")} for r in selected_sorted],
                ensure_ascii=False,
            )
            daily_rows[-1]["top5_rejected_strength_json"] = json.dumps(
                [{"symbol": r.get("symbol"), "strength": r.get("strength"), "reason": r.get("reject_reason")} for r in rejected_sorted],
                ensure_ascii=False,
            )
            daily_rows[-1]["buy_slots_before_buy"] = int(buy_slots_before_buy)
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
        if orders:
            pending[next_day] = orders

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
    if debug_first_divergence:
        metrics["debug_trace"] = debug_trace
    return PortfolioBacktestResult(daily=daily_df, trades=trades_df, candidates=candidates_df, metrics=metrics)
