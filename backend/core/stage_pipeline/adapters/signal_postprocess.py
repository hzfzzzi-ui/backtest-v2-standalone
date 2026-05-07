from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date
from typing import Any, Mapping

from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.signal_provider import DaySignals


def _normalize_symbol(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_etf_trans_up_redeploy_signal(signal: Any) -> bool:
    reason_code = str(getattr(signal, "reason_code", "") or "").strip().upper()
    meta = getattr(signal, "meta", None)
    meta = meta if isinstance(meta, Mapping) else {}
    execution_path = str(meta.get("execution_path", "") or "").strip().lower()
    sleeve_id = str(meta.get("sleeve_id", "") or "").strip().lower()
    alpha_id = str(meta.get("alpha_id", "") or "").strip().lower()
    return (
        reason_code == "ETF_BETA_TRANS_UP_REDEPLOY"
        and execution_path == "trans_up_state_change_redeploy"
        and (sleeve_id == "cn_etf_beta" or alpha_id == "cn_etf_beta")
    )


def _is_shared_risk_on_to_defensive_defense_establish_signal(signal: Any) -> bool:
    reason_code = str(getattr(signal, "reason_code", "") or "").strip().upper()
    meta = getattr(signal, "meta", None)
    meta = meta if isinstance(meta, Mapping) else {}
    execution_path = str(meta.get("execution_path", "") or "").strip().lower()
    sleeve_id = str(meta.get("sleeve_id", "") or "").strip().lower()
    alpha_id = str(meta.get("alpha_id", "") or "").strip().lower()
    return (
        reason_code == "ETF_BETA_SHARED_ACCOUNT_TRANSITION_RISK_ON_TO_DEFENSIVE_DEFENSE_ESTABLISH_ACTIVE"
        and execution_path == "shared_risk_on_to_defensive_transition_defense_establish"
        and (sleeve_id == "cn_etf_beta" or alpha_id == "cn_etf_beta")
    )


def _split_preserved_transition_signals(buy_signals: list[Any]) -> tuple[list[Any], list[Any]]:
    preserved: list[Any] = []
    ordinary: list[Any] = []
    for signal in list(buy_signals or ()):
        if _is_etf_trans_up_redeploy_signal(signal) or _is_shared_risk_on_to_defensive_defense_establish_signal(signal):
            preserved.append(signal)
        else:
            ordinary.append(signal)
    return preserved, ordinary


def _apply_trans_up_recovery_entry_scale(signal: Any, *, scale: float) -> Any:
    meta_raw = getattr(signal, "meta", None)
    meta = dict(meta_raw) if isinstance(meta_raw, Mapping) else {}
    base_scale = float(meta.get("order_value_scale", 1.0) or 1.0)
    meta["order_value_scale"] = float(base_scale) * float(scale)
    meta["trans_up_recovery_staged_deploy_active"] = True
    meta["trans_up_recovery_entry_scale_when_benchmark_off"] = float(scale)
    meta["entry_reason_code"] = "TRANS_UP_RECOVERY_STAGED_ENTRY"
    try:
        return replace(signal, meta=meta)
    except Exception:
        cloned = copy.copy(signal)
        setattr(cloned, "meta", meta)
        return cloned


def _is_trans_up_recovery_staged_holding(runtime: Any, signal: Any) -> bool:
    symbol = _normalize_symbol(getattr(signal, "symbol", ""))
    if not symbol:
        return False
    held_qty = int(dict(getattr(runtime, "positions", {}) or {}).get(symbol, 0) or 0)
    if held_qty <= 0:
        return False
    holding_source = dict(getattr(runtime, "holding_sources", {}).get(symbol) or {})
    return str(holding_source.get("entry_reason_code", "") or "").strip().upper() == "TRANS_UP_RECOVERY_STAGED_ENTRY"


def _apply_trans_up_recovery_confirmed_top_up(signal: Any, *, scale: float) -> Any:
    meta_raw = getattr(signal, "meta", None)
    meta = dict(meta_raw) if isinstance(meta_raw, Mapping) else {}
    base_scale = float(meta.get("order_value_scale", 1.0) or 1.0)
    meta["order_value_scale"] = float(base_scale) * float(scale)
    meta["allow_existing_holding_top_up"] = True
    meta["trans_up_recovery_confirmed_scale_up_active"] = True
    meta["trans_up_recovery_confirmed_top_up_scale_when_benchmark_on"] = float(scale)
    meta["entry_reason_code"] = "TRANS_UP_RECOVERY_CONFIRMED_TOP_UP"
    try:
        return replace(signal, meta=meta)
    except Exception:
        cloned = copy.copy(signal)
        setattr(cloned, "meta", meta)
        return cloned


def _future_positions_after_sell(runtime: Any, *, day: date, sell_signals: list[Any]) -> dict[str, int]:
    future_positions = {
        _normalize_symbol(symbol): int(qty)
        for symbol, qty in dict(getattr(runtime, "positions", {}) or {}).items()
        if int(qty) > 0
    }
    for signal in list(sell_signals or ()):
        symbol = _normalize_symbol(getattr(signal, "symbol", ""))
        held = int(future_positions.get(symbol, 0))
        if held <= 0:
            continue
        qty = int(getattr(signal, "qty", 0) or 0)
        sell_qty = held if qty <= 0 else min(held, qty)
        remain = held - sell_qty
        if remain > 0:
            future_positions[symbol] = remain
        else:
            future_positions.pop(symbol, None)
    return future_positions


def _held_position_quality_rows(runtime: Any, *, day: date, day_index: int, future_positions: Mapping[str, int]) -> list[tuple[str, int, float, float, float, float | None]]:
    provider = getattr(runtime, "provider", None)
    close_idx = dict(getattr(runtime, "close_idx", {}) or {})
    avg_cost_map = dict(getattr(runtime, "position_avg_cost", {}) or {})
    residual_strength = getattr(provider, "_residual_strength_score", None)
    sym_to_col = dict(getattr(provider, "_sym_to_col", {}) or {})

    held_rows: list[tuple[str, int, float, float, float, float | None]] = []
    for symbol, qty in future_positions.items():
        close_v = float(close_idx.get((day, symbol), 0.0) or 0.0)
        avg_cost = float(avg_cost_map.get(symbol, 0.0) or 0.0)
        pnl_pct = (close_v / avg_cost - 1.0) if close_v > 0 and avg_cost > 0 else float("-inf")
        residual_score: float | None = None
        try:
            col_idx = sym_to_col.get(symbol)
            if residual_strength is not None and col_idx is not None:
                value = float(residual_strength[int(day_index), int(col_idx)])
                if value == value:
                    residual_score = value
        except Exception:
            residual_score = None
        ranking_score = float(residual_score) if residual_score is not None else float(pnl_pct)
        held_rows.append((symbol, int(qty), float(ranking_score), close_v, avg_cost, residual_score))
    return held_rows


def _build_trans_down_topk_trim_signals(
    runtime: Any,
    *,
    day_index: int,
    sell_signals: list[Any],
    controls: Mapping[str, Any],
) -> list[Signal]:
    provider = getattr(runtime, "provider", None)
    risk_off_mode = str(getattr(provider, "_risk_off_exit_mode", "") or "").strip().lower()
    market_state = str(controls.get("market_state", "") or "").strip().upper()
    target_max_positions = int(getattr(provider, "_risk_off_exit_trans_down_max_positions", 0) or 0)
    if risk_off_mode != "trans_down_topk_bear_exit" or market_state != "TRANS_DOWN" or target_max_positions <= 0:
        return []

    data_bundle = getattr(getattr(runtime, "request", None), "data_bundle", None)
    trading_days = list(getattr(data_bundle, "trading_days", []) or [])
    if not (0 <= int(day_index) < len(trading_days)):
        return []
    day = trading_days[int(day_index)]
    future_positions = _future_positions_after_sell(runtime, day=day, sell_signals=sell_signals)
    if len(future_positions) <= target_max_positions:
        return []

    held_rows = _held_position_quality_rows(runtime, day=day, day_index=int(day_index), future_positions=future_positions)
    held_rows.sort(key=lambda item: (-item[2], item[0]))
    keep_symbols = {symbol for symbol, *_rest in held_rows[:target_max_positions]}

    trim_signals: list[Signal] = []
    for rank, (symbol, qty, ranking_score, close_v, avg_cost, residual_score) in enumerate(held_rows, start=1):
        if symbol in keep_symbols:
            continue
        pnl_pct = (close_v / avg_cost - 1.0) if close_v > 0 and avg_cost > 0 else None
        trim_metric = "residual_strength_score" if residual_score is not None else "floating_pnl_pct"
        trim_signals.append(
            Signal(
                signal_date=day,
                symbol=symbol,
                side=Side.SELL,
                qty=int(qty),
                reason="TRANS_DOWN_TOPK_TRIM",
                reason_code="TRANS_DOWN_TOPK_TRIM",
                meta={
                    "market_state": market_state,
                    "risk_off_exit_mode": risk_off_mode,
                    "trans_down_max_positions": int(target_max_positions),
                    "trim_rank": int(rank),
                    "trim_metric": trim_metric,
                    "trim_score": float(ranking_score),
                    "residual_strength_score": None if residual_score is None else float(residual_score),
                    "floating_pnl_pct": pnl_pct,
                    "close": float(close_v),
                    "avg_cost": float(avg_cost),
                },
            )
        )
    return trim_signals


def _build_trans_down_residual_trim_signals(
    runtime: Any,
    *,
    day_index: int,
    sell_signals: list[Any],
    controls: Mapping[str, Any],
) -> list[Signal]:
    provider = getattr(runtime, "provider", None)
    risk_off_mode = str(getattr(provider, "_risk_off_exit_mode", "") or "").strip().lower()
    market_state = str(controls.get("market_state", "") or "").strip().upper()
    min_residual_score = float(getattr(provider, "_risk_off_exit_trans_down_min_residual_score", 0.0) or 0.0)
    if risk_off_mode != "trans_down_residual_floor_bear_exit" or market_state != "TRANS_DOWN" or min_residual_score <= 0.0:
        return []

    data_bundle = getattr(getattr(runtime, "request", None), "data_bundle", None)
    trading_days = list(getattr(data_bundle, "trading_days", []) or [])
    if not (0 <= int(day_index) < len(trading_days)):
        return []
    day = trading_days[int(day_index)]
    future_positions = _future_positions_after_sell(runtime, day=day, sell_signals=sell_signals)
    if not future_positions:
        return []

    held_rows = _held_position_quality_rows(runtime, day=day, day_index=int(day_index), future_positions=future_positions)
    trim_signals: list[Signal] = []
    for symbol, qty, ranking_score, close_v, avg_cost, residual_score in held_rows:
        if residual_score is not None and float(residual_score) >= min_residual_score:
            continue
        pnl_pct = (close_v / avg_cost - 1.0) if close_v > 0 and avg_cost > 0 else None
        trim_signals.append(
            Signal(
                signal_date=day,
                symbol=symbol,
                side=Side.SELL,
                qty=int(qty),
                reason="TRANS_DOWN_RESIDUAL_TRIM",
                reason_code="TRANS_DOWN_RESIDUAL_TRIM",
                meta={
                    "market_state": market_state,
                    "risk_off_exit_mode": risk_off_mode,
                    "trans_down_min_residual_score": float(min_residual_score),
                    "residual_strength_score": None if residual_score is None else float(residual_score),
                    "floating_pnl_pct": pnl_pct,
                    "close": float(close_v),
                    "avg_cost": float(avg_cost),
                    "quality_passed": False,
                },
            )
        )
    return trim_signals


def _build_trans_down_residual_profit_trim_signals(
    runtime: Any,
    *,
    day_index: int,
    sell_signals: list[Any],
    controls: Mapping[str, Any],
) -> list[Signal]:
    provider = getattr(runtime, "provider", None)
    risk_off_mode = str(getattr(provider, "_risk_off_exit_mode", "") or "").strip().lower()
    market_state = str(controls.get("market_state", "") or "").strip().upper()
    min_residual_score = float(getattr(provider, "_risk_off_exit_trans_down_min_residual_score", 0.0) or 0.0)
    if risk_off_mode != "trans_down_residual_profit_floor_bear_exit" or market_state != "TRANS_DOWN" or min_residual_score <= 0.0:
        return []

    data_bundle = getattr(getattr(runtime, "request", None), "data_bundle", None)
    trading_days = list(getattr(data_bundle, "trading_days", []) or [])
    if not (0 <= int(day_index) < len(trading_days)):
        return []
    day = trading_days[int(day_index)]
    future_positions = _future_positions_after_sell(runtime, day=day, sell_signals=sell_signals)
    if not future_positions:
        return []

    held_rows = _held_position_quality_rows(runtime, day=day, day_index=int(day_index), future_positions=future_positions)
    trim_signals: list[Signal] = []
    for symbol, qty, ranking_score, close_v, avg_cost, residual_score in held_rows:
        pnl_pct = (close_v / avg_cost - 1.0) if close_v > 0 and avg_cost > 0 else None
        keep_by_quality = residual_score is not None and float(residual_score) >= min_residual_score
        keep_by_profit = pnl_pct is not None and float(pnl_pct) > 0.0
        if keep_by_quality and keep_by_profit:
            continue
        trim_signals.append(
            Signal(
                signal_date=day,
                symbol=symbol,
                side=Side.SELL,
                qty=int(qty),
                reason="TRANS_DOWN_RESIDUAL_PROFIT_TRIM",
                reason_code="TRANS_DOWN_RESIDUAL_PROFIT_TRIM",
                meta={
                    "market_state": market_state,
                    "risk_off_exit_mode": risk_off_mode,
                    "trans_down_min_residual_score": float(min_residual_score),
                    "residual_strength_score": None if residual_score is None else float(residual_score),
                    "floating_pnl_pct": pnl_pct,
                    "close": float(close_v),
                    "avg_cost": float(avg_cost),
                    "quality_passed": bool(keep_by_quality),
                    "profit_passed": bool(keep_by_profit),
                },
            )
        )
    return trim_signals


def _build_trans_down_residual_ma20_trim_signals(
    runtime: Any,
    *,
    day_index: int,
    sell_signals: list[Any],
    controls: Mapping[str, Any],
) -> list[Signal]:
    provider = getattr(runtime, "provider", None)
    risk_off_mode = str(getattr(provider, "_risk_off_exit_mode", "") or "").strip().lower()
    market_state = str(controls.get("market_state", "") or "").strip().upper()
    min_residual_score = float(getattr(provider, "_risk_off_exit_trans_down_min_residual_score", 0.0) or 0.0)
    if risk_off_mode != "trans_down_residual_ma20_floor_bear_exit" or market_state != "TRANS_DOWN" or min_residual_score <= 0.0:
        return []

    data_bundle = getattr(getattr(runtime, "request", None), "data_bundle", None)
    trading_days = list(getattr(data_bundle, "trading_days", []) or [])
    if not (0 <= int(day_index) < len(trading_days)):
        return []
    day = trading_days[int(day_index)]
    future_positions = _future_positions_after_sell(runtime, day=day, sell_signals=sell_signals)
    if not future_positions:
        return []

    held_rows = _held_position_quality_rows(runtime, day=day, day_index=int(day_index), future_positions=future_positions)
    feats = getattr(provider, "_feats", None)
    mx = getattr(provider, "_mx", None)
    sym_to_col = dict(getattr(provider, "_sym_to_col", {}) or {})

    trim_signals: list[Signal] = []
    for symbol, qty, ranking_score, close_v, avg_cost, residual_score in held_rows:
        col = sym_to_col.get(symbol)
        sma20_v: float | None = None
        close_cur: float | None = None
        try:
            if col is not None and feats is not None and mx is not None:
                close_cur = float(mx.close[int(day_index), int(col)])
                sma20_raw = float(feats.sma20[int(day_index), int(col)])
                if sma20_raw == sma20_raw:
                    sma20_v = sma20_raw
        except Exception:
            sma20_v = None
            close_cur = None

        keep_by_quality = residual_score is not None and float(residual_score) >= min_residual_score
        keep_by_ma20 = close_cur is not None and sma20_v is not None and float(close_cur) >= float(sma20_v)
        pnl_pct = (close_v / avg_cost - 1.0) if close_v > 0 and avg_cost > 0 else None
        if keep_by_quality and keep_by_ma20:
            continue
        trim_signals.append(
            Signal(
                signal_date=day,
                symbol=symbol,
                side=Side.SELL,
                qty=int(qty),
                reason="TRANS_DOWN_RESIDUAL_MA20_TRIM",
                reason_code="TRANS_DOWN_RESIDUAL_MA20_TRIM",
                meta={
                    "market_state": market_state,
                    "risk_off_exit_mode": risk_off_mode,
                    "trans_down_min_residual_score": float(min_residual_score),
                    "residual_strength_score": None if residual_score is None else float(residual_score),
                    "close": None if close_cur is None else float(close_cur),
                    "sma20": None if sma20_v is None else float(sma20_v),
                    "avg_cost": float(avg_cost),
                    "floating_pnl_pct": pnl_pct,
                    "quality_passed": bool(keep_by_quality),
                    "ma20_passed": bool(keep_by_ma20),
                },
            )
        )
    return trim_signals


def postprocess_day_signals(
    runtime: Any,
    *,
    day_index: int,
    day_signals: DaySignals,
    controls: Mapping[str, Any],
) -> DaySignals:
    if runtime.route_id != "provider_breakout_runtime":
        return day_signals
    buy_signals = list(day_signals.buy_signals)
    sell_signals = list(day_signals.sell_signals)
    exit_syms = set(day_signals.exit_syms)
    diagnostics = dict(day_signals.diagnostics or {})
    provider = getattr(runtime, "provider", None)
    risk_off_mode = str(getattr(provider, "_risk_off_exit_mode", "") or "").strip().lower()
    market_state = str(controls.get("market_state", "") or "").strip().upper()
    trade_mode = str(controls.get("trade_mode", "") or "").strip().upper()
    global_risk_override_count = int(diagnostics.get("global_risk_override_count", 0) or 0)
    allow_trans_up_recovery_entries = bool(
        getattr(
            getattr(runtime, "_market_filter_cfg", None),
            "allow_trans_up_recovery_entries_when_benchmark_off",
            False,
        )
    )
    trans_up_recovery_entry_scale = float(
        getattr(
            getattr(runtime, "_market_filter_cfg", None),
            "trans_up_recovery_entry_scale_when_benchmark_off",
            1.0,
        )
        or 1.0
    )
    trans_up_recovery_confirmed_top_up_scale = float(
        getattr(
            getattr(runtime, "_market_filter_cfg", None),
            "trans_up_recovery_confirmed_top_up_scale_when_benchmark_on",
            0.0,
        )
        or 0.0
    )
    trans_up_recovery_gate_relaxed = False
    trans_up_recovery_scaled_entry_count = 0
    trans_up_recovery_confirmed_top_up_count = 0
    if runtime._br_enabled and not bool(controls["benchmark_regime_on"]):
        allow_recovery_bypass = (
            allow_trans_up_recovery_entries
            and getattr(runtime, "route_id", "") == "provider_breakout_runtime"
            and market_state == "TRANS_UP"
            and trade_mode == "TREND_LIGHT"
        )
        if allow_recovery_bypass:
            trans_up_recovery_gate_relaxed = True
            if (trans_up_recovery_entry_scale < 1.0 or trans_up_recovery_confirmed_top_up_scale > 0.0) and buy_signals:
                buy_signals = [
                    _apply_trans_up_recovery_entry_scale(signal, scale=trans_up_recovery_entry_scale)
                    for signal in buy_signals
                ]
                trans_up_recovery_scaled_entry_count = int(len(buy_signals))
        else:
            preserved_redeploy, ordinary_buy_signals = _split_preserved_transition_signals(buy_signals)
            global_risk_override_count += int(len(ordinary_buy_signals))
            buy_signals = preserved_redeploy
    elif (
        runtime._br_enabled
        and bool(controls["benchmark_regime_on"])
        and trans_up_recovery_confirmed_top_up_scale > 0.0
        and market_state == "TRANS_UP"
        and trade_mode == "TREND_LIGHT"
        and buy_signals
    ):
        confirmed_buy_signals: list[Any] = []
        for signal in buy_signals:
            if _is_trans_up_recovery_staged_holding(runtime, signal):
                confirmed_buy_signals.append(
                    _apply_trans_up_recovery_confirmed_top_up(
                        signal,
                        scale=trans_up_recovery_confirmed_top_up_scale,
                    )
                )
            else:
                confirmed_buy_signals.append(signal)
        buy_signals = confirmed_buy_signals
        trans_up_recovery_confirmed_top_up_count = int(
            sum(
                1
                for signal in buy_signals
                if bool(
                    dict(getattr(signal, "meta", {}) or {}).get(
                        "trans_up_recovery_confirmed_scale_up_active",
                        False,
                    )
                )
            )
        )
    state_blocks_entries = False
    if runtime._mf_enabled:
        if trade_mode:
            state_blocks_entries = trade_mode == "NO_TRADE"
        else:
            state_blocks_entries = int(runtime._mf_state_arr[day_index]) == 3
    if state_blocks_entries:
        preserved_redeploy, ordinary_buy_signals = _split_preserved_transition_signals(buy_signals)
        global_risk_override_count += int(len(ordinary_buy_signals))
        buy_signals = preserved_redeploy
    freeze_trans_up_entries = bool(getattr(getattr(runtime, "_market_filter_cfg", None), "freeze_trans_up_entries", False))
    if freeze_trans_up_entries and market_state == "TRANS_UP":
        preserved_redeploy, ordinary_buy_signals = _split_preserved_transition_signals(buy_signals)
        global_risk_override_count += int(len(ordinary_buy_signals))
        buy_signals = preserved_redeploy
    if risk_off_mode == "trans_down_freeze_bear_exit" and market_state == "TRANS_DOWN":
        global_risk_override_count += int(len(buy_signals))
        buy_signals = []
    if risk_off_mode == "trans_down_topk_bear_exit" and market_state == "TRANS_DOWN":
        global_risk_override_count += int(len(buy_signals))
        buy_signals = []
        trim_signals = _build_trans_down_topk_trim_signals(
            runtime,
            day_index=day_index,
            sell_signals=sell_signals,
            controls=controls,
        )
        if trim_signals:
            sell_signals.extend(trim_signals)
            exit_syms.update(_normalize_symbol(signal.symbol) for signal in trim_signals)
            global_risk_override_count += int(len(trim_signals))
    if risk_off_mode == "trans_down_residual_floor_bear_exit" and market_state == "TRANS_DOWN":
        global_risk_override_count += int(len(buy_signals))
        buy_signals = []
        trim_signals = _build_trans_down_residual_trim_signals(
            runtime,
            day_index=day_index,
            sell_signals=sell_signals,
            controls=controls,
        )
        if trim_signals:
            sell_signals.extend(trim_signals)
            exit_syms.update(_normalize_symbol(signal.symbol) for signal in trim_signals)
            global_risk_override_count += int(len(trim_signals))
    if risk_off_mode == "trans_down_residual_profit_floor_bear_exit" and market_state == "TRANS_DOWN":
        global_risk_override_count += int(len(buy_signals))
        buy_signals = []
        trim_signals = _build_trans_down_residual_profit_trim_signals(
            runtime,
            day_index=day_index,
            sell_signals=sell_signals,
            controls=controls,
        )
        if trim_signals:
            sell_signals.extend(trim_signals)
            exit_syms.update(_normalize_symbol(signal.symbol) for signal in trim_signals)
            global_risk_override_count += int(len(trim_signals))
    if risk_off_mode == "trans_down_residual_ma20_floor_bear_exit" and market_state == "TRANS_DOWN":
        global_risk_override_count += int(len(buy_signals))
        buy_signals = []
        trim_signals = _build_trans_down_residual_ma20_trim_signals(
            runtime,
            day_index=day_index,
            sell_signals=sell_signals,
            controls=controls,
        )
        if trim_signals:
            sell_signals.extend(trim_signals)
            exit_syms.update(_normalize_symbol(signal.symbol) for signal in trim_signals)
            global_risk_override_count += int(len(trim_signals))
    diagnostics["global_risk_override_count"] = int(global_risk_override_count)
    diagnostics["trans_up_recovery_gate_relaxed"] = bool(trans_up_recovery_gate_relaxed)
    diagnostics["trans_up_recovery_entry_scale_applied"] = float(
        trans_up_recovery_entry_scale if trans_up_recovery_gate_relaxed else 1.0
    )
    diagnostics["trans_up_recovery_scaled_entry_count"] = int(trans_up_recovery_scaled_entry_count)
    diagnostics["trans_up_recovery_confirmed_top_up_scale_when_benchmark_on"] = float(
        trans_up_recovery_confirmed_top_up_scale
    )
    diagnostics["trans_up_recovery_confirmed_top_up_count"] = int(trans_up_recovery_confirmed_top_up_count)
    return replace(
        day_signals,
        sell_signals=sell_signals,
        buy_signals=buy_signals,
        exit_syms=exit_syms,
        diagnostics=diagnostics,
    )
