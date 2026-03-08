from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from backend.core.engine_vector.signal_provider import DaySignals
from backend.core.portfolio.portfolio_builder import calc_buy_slots, compute_nav_snapshot


@dataclass(frozen=True, slots=True)
class DailySnapshot:
    nav: float
    market_value: float
    controls: dict[str, Any]


def build_daily_row(
    runtime: Any,
    *,
    day: date,
    nav: float,
    daily_ret: float,
    drawdown: float,
    gross_exposure: float,
    turnover_pct: float,
    top5: list[dict[str, Any]],
    controls: Mapping[str, Any],
) -> dict[str, Any]:
    row = {
        "date": day.isoformat(),
        "nav": nav,
        "cash": runtime.cash,
        "positions_count": len(runtime.positions),
        "positions_count_end_of_day": len(runtime.positions),
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
        "effective_max_positions": int(controls["effective_max_positions"]),
        "dd_state": str(controls["dd_state"]),
    }
    if runtime.route_id == "provider_breakout_runtime":
        row["market_state"] = str(controls["market_state"])
        row["trade_mode"] = str(controls["trade_mode"])
        row["benchmark_regime_on"] = bool(controls["benchmark_regime_on"])
    return row


def prepare_daily_snapshot(runtime: Any, *, day_index: int, day: date) -> DailySnapshot:
    nav, market_value, pos_values = compute_nav_snapshot(
        cash=runtime.cash,
        positions=runtime.positions,
        close_idx=runtime.close_idx,
        day=day,
    )
    runtime.peak_nav = max(runtime.peak_nav, nav)
    daily_ret = (nav / runtime.prev_nav - 1.0) if runtime.prev_nav > 0 else 0.0
    drawdown = (nav / runtime.peak_nav - 1.0) if runtime.peak_nav > 0 else 0.0
    controls = runtime._compute_day_controls(day_index, day, drawdown)
    gross_exposure = (market_value / nav) if nav > 0 else 0.0
    turnover_pct = (runtime._traded_value_today / runtime.prev_nav) if runtime.prev_nav > 0 else 0.0
    top5 = [
        {"symbol": symbol, "value": round(value, 2)}
        for symbol, value in sorted(pos_values, key=lambda item: item[1], reverse=True)[:5]
    ]
    runtime.daily_rows.append(
        build_daily_row(
            runtime,
            day=day,
            nav=nav,
            daily_ret=daily_ret,
            drawdown=drawdown,
            gross_exposure=gross_exposure,
            turnover_pct=turnover_pct,
            top5=top5,
            controls=controls,
        )
    )
    runtime.prev_nav = nav
    return DailySnapshot(
        nav=float(nav),
        market_value=float(market_value),
        controls=dict(controls),
    )


def apply_daily_decision_diagnostics(runtime: Any, *, day_signals: DaySignals, debug_plan: Mapping[str, Any]) -> None:
    if not runtime.daily_rows or runtime._current_day is None:
        return
    daily_row = runtime.daily_rows[-1]
    sell_symbols = {str(sig.symbol).lower() for sig in day_signals.sell_signals}
    positions_after_sell = int(
        sum(1 for symbol, qty in runtime.positions.items() if int(qty) > 0 and str(symbol).lower() not in sell_symbols)
    )
    buy_slots = int(calc_buy_slots(int(runtime._current_day["controls"]["effective_max_positions"]), int(positions_after_sell)))
    daily_row["positions_before_sell"] = int(sum(1 for qty in runtime.positions.values() if int(qty) > 0))
    daily_row["positions_after_sell"] = int(positions_after_sell)
    daily_row["buy_slots_before_buy"] = int(buy_slots)
    daily_row["buy_slots_after_sell"] = int(buy_slots)
    daily_row["buy_slots_calculated"] = int(buy_slots)
    daily_row["sells_executed_count"] = int(len(day_signals.sell_signals))
    daily_row["candidates_count"] = int((debug_plan or {}).get("buy_candidates_count", 0) or 0)
    daily_row["selected_count"] = int(len((debug_plan or {}).get("selected_symbols", []) or []))
    daily_row["buy_candidate_count"] = int(len(day_signals.buy_signals))
    daily_row["after_held_filter_count"] = int(len(day_signals.buy_signals))
    daily_row["raw_buy_signal_count"] = int(day_signals.diagnostics.get("raw_buy_signal_count", len(day_signals.buy_signals)) or 0)
