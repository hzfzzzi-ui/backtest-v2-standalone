from __future__ import annotations

import math
from datetime import date

import numpy as np

from backend.core.config.etf_beta_contract import (
    CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO,
    build_etf_beta_formal_view,
    build_etf_beta_research_view,
    _is_formal_stabilizer_role,
    _is_standalone_mainline_role,
)
from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.signal_provider import DayContext, DaySignals, ExitCounts

from .candidate_pool import *
from .diagnostics import *
from .provider_config import *


_RISK_ON_TRANSITION_STATES = {"BULL", "TRANS_UP"}
_DEFENSIVE_TRANSITION_STATES = {"TRANS_DOWN", "RISK_OFF"}


def _build_shared_risk_on_to_defensive_release_plan(
    *,
    ctx: DayContext,
    day: date,
    day_idx: int,
    held_qty_by_symbol: dict[str, int],
    sym_to_col: dict[str, int],
    close_matrix: Any,
    current_cash: float,
    release_target_cash: float,
    release_ratio_cap: float,
    defense_symbol: str,
    core_beta_symbol: str,
) -> tuple[dict[str, int], float, list[str]]:
    remaining_cash = max(float(release_target_cash or 0.0) - float(current_cash or 0.0), 0.0)
    if remaining_cash <= 1e-12:
        return {}, 0.0, []
    candidates: list[tuple[int, float, str, int, float]] = []
    for symbol, raw_qty in dict(held_qty_by_symbol or {}).items():
        normalized_symbol = _normalize_etf_symbol_key(symbol)
        qty = int(raw_qty or 0)
        if qty <= 0 or normalized_symbol == defense_symbol:
            continue
        fallback_price = None
        col_idx = sym_to_col.get(normalized_symbol)
        if col_idx is not None:
            try:
                raw_close = float(close_matrix[day_idx, col_idx])
            except Exception:
                raw_close = float("nan")
            if np.isfinite(raw_close) and raw_close > 0.0:
                fallback_price = float(raw_close)
        price = _resolve_ctx_symbol_price(
            ctx=ctx,
            day=day,
            normalized_symbol=normalized_symbol,
            fallback_price=fallback_price,
        )
        if price is None or price <= 0.0:
            continue
        bounded_qty = int(math.floor(float(qty) * float(release_ratio_cap) / 100.0) * 100)
        if bounded_qty <= 0:
            continue
        priority = 0 if normalized_symbol == core_beta_symbol else 1
        candidates.append((priority, -float(price) * float(bounded_qty), normalized_symbol, bounded_qty, float(price)))
    candidates.sort()
    plan: dict[str, int] = {}
    released_cash = 0.0
    released_symbols: list[str] = []
    for _priority, _sort_value, normalized_symbol, max_qty, price in candidates:
        remaining_cash = max(float(release_target_cash or 0.0) - float(current_cash or 0.0) - float(released_cash), 0.0)
        if remaining_cash <= 1e-12:
            break
        needed_qty = int(math.ceil(float(remaining_cash) / float(price) / 100.0) * 100)
        sell_qty = min(int(max_qty), max(int(needed_qty), 100))
        sell_qty = int(math.floor(float(sell_qty) / 100.0) * 100)
        if sell_qty <= 0:
            continue
        plan[normalized_symbol] = int(sell_qty)
        released_cash += float(sell_qty) * float(price)
        released_symbols.append(normalized_symbol)
    return plan, float(released_cash), released_symbols


def _resolve_standalone_deploy_delta_target_weights(
    *,
    ctx: DayContext,
    day: date,
    day_idx: int,
    held_qty_by_symbol: dict[str, int],
    deploy_symbols: list[str],
    target_exposure_by_symbol: dict[str, float],
    standalone_deploy_gap: float,
    sym_to_col: dict[str, int],
    close_matrix: Any,
) -> dict[str, float]:
    normalized_symbols = [str(symbol).strip().upper() for symbol in list(deploy_symbols or []) if str(symbol).strip()]
    deploy_gap = max(float(standalone_deploy_gap or 0.0), 0.0)
    if not normalized_symbols or deploy_gap <= 1e-12:
        return {}

    raw_delta_gap_by_symbol: dict[str, float] = {}
    for symbol in normalized_symbols:
        current_symbol_exposure = _group_exposure_from_holdings(
            ctx=ctx,
            day=day,
            day_idx=day_idx,
            held_qty_by_symbol=held_qty_by_symbol,
            group_symbols=[symbol],
            sym_to_col=sym_to_col,
            close_matrix=close_matrix,
        )
        desired_final_target_weight = max(float(dict(target_exposure_by_symbol or {}).get(symbol, 0.0)), 0.0)
        raw_delta_gap_by_symbol[symbol] = max(float(desired_final_target_weight) - float(current_symbol_exposure), 0.0)

    total_raw_delta_gap = float(sum(raw_delta_gap_by_symbol.values()) or 0.0)
    if total_raw_delta_gap > 1e-12:
        scale = min(1.0, float(deploy_gap) / float(total_raw_delta_gap))
        return {
            symbol: float(raw_delta_gap_by_symbol[symbol]) * float(scale)
            for symbol in normalized_symbols
            if float(raw_delta_gap_by_symbol[symbol]) > 1e-12
        }

    equal_delta = float(deploy_gap) / float(len(normalized_symbols))
    return {
        symbol: float(equal_delta)
        for symbol in normalized_symbols
    }


def _resolve_riskoff_cash_drip_target_weights(
    *,
    ctx: DayContext,
    day: date,
    day_idx: int,
    held_qty_by_symbol: dict[str, int],
    deploy_symbols: list[str],
    target_exposure_by_symbol: dict[str, float],
    sym_to_col: dict[str, int],
    close_matrix: Any,
    lot_size: int = 100,
    cash_available_override: float | None = None,
) -> tuple[dict[str, float], str]:
    normalized_symbols = [str(symbol).strip().upper() for symbol in list(deploy_symbols or []) if str(symbol).strip()]
    nav = max(float(getattr(ctx, "nav", 0.0) or 0.0), 0.0)
    remaining_cash = max(
        float(cash_available_override if cash_available_override is not None else getattr(ctx, "cash", 0.0) or 0.0),
        0.0,
    )
    if not normalized_symbols:
        return {}, "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_NO_SELECTION"
    if nav <= 0.0 or remaining_cash <= 0.0:
        return {}, "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_CASH_TOO_SMALL"

    normalized_target_exposure_by_symbol = {
        str(symbol).strip().upper(): max(float(value or 0.0), 0.0)
        for symbol, value in dict(target_exposure_by_symbol or {}).items()
        if str(symbol).strip()
    }
    effective_lot_size = max(int(lot_size or 0), 1)
    has_gap_symbol = False
    has_priced_gap_symbol = False
    has_affordable_gap_symbol = False
    drip_target_weight_by_symbol: dict[str, float] = {}
    next_day = getattr(ctx, "next_day", None)
    open_idx = dict(getattr(ctx, "open_idx", {}) or {})

    for symbol in normalized_symbols:
        normalized_symbol = str(symbol).strip().upper()
        current_symbol_exposure = _group_exposure_from_holdings(
            ctx=ctx,
            day=day,
            day_idx=day_idx,
            held_qty_by_symbol=held_qty_by_symbol,
            group_symbols=[normalized_symbol],
            sym_to_col=sym_to_col,
            close_matrix=close_matrix,
        )
        desired_final_target_weight = max(
            float(normalized_target_exposure_by_symbol.get(normalized_symbol, 0.0)),
            0.0,
        )
        target_gap = max(float(desired_final_target_weight) - float(current_symbol_exposure), 0.0)
        if target_gap <= 1e-12:
            continue
        has_gap_symbol = True

        normalized_symbol_key = _normalize_etf_symbol_key(normalized_symbol)
        next_open_price = (
            float(open_idx.get((next_day, normalized_symbol_key.lower()), 0.0) or 0.0)
            if next_day is not None
            else 0.0
        )
        col_idx = sym_to_col.get(normalized_symbol_key)
        close_price = (
            float(close_matrix[day_idx, col_idx])
            if col_idx is not None and day_idx < int(close_matrix.shape[0])
            else 0.0
        )
        reference_price = float(next_open_price or close_price or 0.0)
        if not np.isfinite(reference_price) or reference_price <= 0.0:
            continue
        has_priced_gap_symbol = True

        one_lot_cost = float(effective_lot_size) * float(reference_price)
        if one_lot_cost <= 0.0 or one_lot_cost > float(remaining_cash) + 1e-12:
            continue
        has_affordable_gap_symbol = True
        drip_target_weight_by_symbol[normalized_symbol] = float(one_lot_cost) / float(nav)
        remaining_cash = max(float(remaining_cash) - float(one_lot_cost), 0.0)

    if drip_target_weight_by_symbol:
        return drip_target_weight_by_symbol, ""
    if not has_gap_symbol:
        return {}, "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_TARGET_SATISFIED"
    if not has_priced_gap_symbol:
        return {}, "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_EXECUTION_CONSTRAINT"
    if not has_affordable_gap_symbol:
        return {}, "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_CASH_TOO_SMALL"
    return {}, "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_EXECUTION_CONSTRAINT"


def _resolve_riskoff_account_budget_materialization_plan(
    *,
    ctx: DayContext,
    day: date,
    day_idx: int,
    held_qty_by_symbol: dict[str, int],
    weak_state_target_symbols: list[str],
    selected_core_symbols: list[str],
    weak_state_defense_candidate_symbols: set[str],
    target_exposure_by_symbol: dict[str, float],
    sym_to_col: dict[str, int],
    close_matrix: Any,
    open_matrix: Any,
    current_total_exposure: float,
    current_core_exposure: float,
    desired_live_exposure: float,
    bounded_partial_release_ratio_cap: float = 0.02,
    lot_size: int = 100,
) -> dict[str, Any]:
    normalized_targets = {
        str(symbol).strip().upper(): max(
            float(dict(target_exposure_by_symbol or {}).get(str(symbol).strip().upper(), 0.0) or 0.0),
            0.0,
        )
        for symbol in list(weak_state_target_symbols or ())
        if str(symbol).strip()
    }
    if not normalized_targets:
        return {
            "active": False,
            "reason_code": "",
            "reject_reason": "ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_REJECT_NO_SELECTION",
            "release_plan": {},
            "release_target_cash": 0.0,
            "release_cash": 0.0,
            "release_destination": "",
            "target_symbols": [],
            "release_symbols": [],
        }
    defense_targets = [
        str(symbol).strip().upper()
        for symbol in list(weak_state_target_symbols or ())
        if str(symbol).strip().upper() in weak_state_defense_candidate_symbols
    ]
    core_targets = [
        str(symbol).strip().upper()
        for symbol in list(weak_state_target_symbols or ())
        if str(symbol).strip().upper() in set(selected_core_symbols)
    ]
    current_defense_exposure = _group_exposure_from_holdings(
        ctx=ctx,
        day=day,
        day_idx=day_idx,
        held_qty_by_symbol=held_qty_by_symbol,
        group_symbols=defense_targets,
        sym_to_col=sym_to_col,
        close_matrix=close_matrix,
    )
    target_defense_exposure = float(sum(normalized_targets.get(symbol, 0.0) for symbol in defense_targets))
    target_core_exposure = float(sum(normalized_targets.get(symbol, 0.0) for symbol in core_targets))
    defense_gap = max(float(target_defense_exposure) - float(current_defense_exposure or 0.0), 0.0)
    core_gap = max(float(target_core_exposure) - float(current_core_exposure or 0.0), 0.0)
    release_destination = ""
    target_symbols: list[str] = []
    if defense_gap > 1e-12 and defense_targets:
        release_destination = "defense"
        target_symbols = list(defense_targets)
    elif core_gap > 1e-12 and core_targets:
        release_destination = "core_beta"
        target_symbols = list(core_targets)
    else:
        return {
            "active": False,
            "reason_code": "",
            "reject_reason": "ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_REJECT_TARGET_ALREADY_MATERIALIZED",
            "release_plan": {},
            "release_target_cash": 0.0,
            "release_cash": 0.0,
            "release_destination": "",
            "target_symbols": [],
            "release_symbols": [],
        }
    candidate_release_symbols = sorted(
        [str(symbol).strip().upper() for symbol in list(held_qty_by_symbol.keys()) if str(symbol).strip()],
        key=lambda symbol: (
            0 if symbol not in normalized_targets else 1,
            0 if symbol not in set(target_symbols) else 1,
            0 if symbol in set(selected_core_symbols) else 1,
            symbol,
        ),
    )
    if not candidate_release_symbols:
        return {
            "active": False,
            "reason_code": "",
            "reject_reason": "ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_REJECT_NO_RELEASE_SOURCE",
            "release_plan": {},
            "release_target_cash": 0.0,
            "release_cash": 0.0,
            "release_destination": release_destination,
            "target_symbols": list(target_symbols),
            "release_symbols": [],
        }
    first_target_symbol = str(target_symbols[0]).strip().upper()
    normalized_target_symbol = _normalize_etf_symbol_key(first_target_symbol)
    display_target_symbol = _display_etf_symbol(normalized_target_symbol)
    first_target_col = None
    for key in (
        normalized_target_symbol,
        normalized_target_symbol.lower(),
        normalized_target_symbol.upper(),
        display_target_symbol,
        display_target_symbol.lower(),
        display_target_symbol.upper(),
    ):
        candidate_col = sym_to_col.get(key)
        if candidate_col is not None:
            first_target_col = candidate_col
            break
    fallback_close_price = (
        float(close_matrix[day_idx, first_target_col])
        if first_target_col is not None and day_idx < int(close_matrix.shape[0])
        else 0.0
    )
    reference_price = _resolve_ctx_symbol_price(
        ctx=ctx,
        day=day,
        normalized_symbol=normalized_target_symbol,
        fallback_price=float(fallback_close_price or 0.0),
    )
    if reference_price is None or float(reference_price) <= 0.0:
        return {
            "active": False,
            "reason_code": "",
            "reject_reason": "ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_REJECT_EXECUTION_CONSTRAINT",
            "release_plan": {},
            "release_target_cash": 0.0,
            "release_cash": 0.0,
            "release_destination": release_destination,
            "target_symbols": list(target_symbols),
            "release_symbols": [],
        }
    current_cash = max(float(getattr(ctx, "cash", 0.0) or 0.0), 0.0)
    effective_lot_size = max(int(lot_size or 0), 1)
    minimum_lot_cash = float(reference_price) * float(effective_lot_size)
    if current_cash + 1e-12 >= minimum_lot_cash:
        return {
            "active": False,
            "reason_code": "",
            "reject_reason": "ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_REJECT_EXECUTION_CONSTRAINT",
            "release_plan": {},
            "release_target_cash": 0.0,
            "release_cash": 0.0,
            "release_destination": release_destination,
            "target_symbols": list(target_symbols),
            "release_symbols": [],
        }
    gap_exposure = defense_gap if release_destination == "defense" else core_gap
    nav_value = max(float(getattr(ctx, "nav", 0.0) or 0.0), 0.0)
    release_target_cash = min(
        max(float(gap_exposure) * nav_value, max(minimum_lot_cash - current_cash, 0.0)),
        nav_value * float(max(bounded_partial_release_ratio_cap, 0.0)),
        max(float(current_total_exposure or 0.0) - float(desired_live_exposure or 0.0), 0.0) * nav_value
        + float(max(minimum_lot_cash - current_cash, 0.0)),
    )
    release_plan, release_cash, reject_reason = _resolve_state_edge_cash_release_plan(
        ctx=ctx,
        day=day,
        day_idx=day_idx,
        held_qty_by_symbol=held_qty_by_symbol,
        candidate_symbols=candidate_release_symbols,
        release_target_cash=float(release_target_cash),
        sym_to_col=sym_to_col,
        close_matrix=close_matrix,
        lot_size=lot_size,
    )
    if not release_plan:
        return {
            "active": False,
            "reason_code": "",
            "reject_reason": reject_reason
            or "ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_REJECT_NO_RELEASE_SOURCE",
            "release_plan": {},
            "release_target_cash": float(release_target_cash),
            "release_cash": float(release_cash or 0.0),
            "release_destination": release_destination,
            "target_symbols": list(target_symbols),
            "release_symbols": [],
        }
    return {
        "active": True,
        "reason_code": "ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_ACTIVE",
        "reject_reason": "",
        "release_plan": dict(release_plan),
        "release_target_cash": float(release_target_cash),
        "release_cash": float(release_cash or 0.0),
        "release_destination": release_destination,
        "target_symbols": list(target_symbols),
        "release_symbols": list(release_plan.keys()),
    }


def _resolve_state_edge_cash_release_plan(
    *,
    ctx: DayContext,
    day: date,
    day_idx: int,
    held_qty_by_symbol: dict[str, int],
    candidate_symbols: list[str],
    release_target_cash: float,
    sym_to_col: dict[str, int],
    close_matrix: Any,
    lot_size: int = 100,
    per_symbol_release_cap_ratio: float = 0.25,
) -> tuple[dict[str, int], float, str]:
    normalized_symbols = [str(symbol).strip().upper() for symbol in list(candidate_symbols or []) if str(symbol).strip()]
    if not normalized_symbols:
        return {}, 0.0, "ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_LIQUID_RELEASE"
    nav = max(float(getattr(ctx, "nav", 0.0) or 0.0), 0.0)
    if nav <= 0.0:
        return {}, 0.0, "ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_LIQUID_RELEASE"
    target_cash = max(0.0, float(release_target_cash or 0.0))
    if target_cash <= 1e-12:
        return {}, 0.0, "ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_RELEASE_REQUIRED"
    effective_lot_size = max(int(lot_size or 0), 1)
    release_plan: dict[str, int] = {}
    released_cash = 0.0

    next_day = getattr(ctx, "next_day", None)
    open_idx = dict(getattr(ctx, "open_idx", {}) or {})
    scored_symbols = []
    for symbol in normalized_symbols:
        held_qty = max(0, int(held_qty_by_symbol.get(symbol, 0) or 0))
        if held_qty < effective_lot_size:
            continue
        normalized_symbol_key = _normalize_etf_symbol_key(symbol)
        display_symbol_key = _display_etf_symbol(normalized_symbol_key)
        symbol_key_candidates = (
            normalized_symbol_key,
            normalized_symbol_key.lower(),
            normalized_symbol_key.upper(),
            display_symbol_key,
            display_symbol_key.lower(),
            display_symbol_key.upper(),
        )
        col_idx = None
        for key in symbol_key_candidates:
            candidate_col_idx = sym_to_col.get(key)
            if candidate_col_idx is not None:
                col_idx = candidate_col_idx
                break
        fallback_close_price = (
            float(close_matrix[day_idx, col_idx])
            if col_idx is not None and day_idx < int(close_matrix.shape[0])
            else 0.0
        )
        reference_price = _resolve_ctx_symbol_price(
            ctx=ctx,
            day=day,
            normalized_symbol=normalized_symbol_key,
            fallback_price=float(fallback_close_price or 0.0),
        )
        reference_price = float(reference_price or 0.0)
        if not np.isfinite(reference_price) or reference_price <= 0.0:
            continue
        current_symbol_exposure = float(held_qty) * float(reference_price) / float(nav)
        if current_symbol_exposure <= 1e-12:
            continue
        scored_symbols.append((float(current_symbol_exposure), symbol))
    scored_symbols.sort(reverse=True)

    for current_symbol_exposure, symbol in scored_symbols:
        if released_cash >= target_cash - 1e-12:
            break
        held_qty = max(0, int(held_qty_by_symbol.get(symbol, 0) or 0))
        if held_qty < effective_lot_size:
            continue
        normalized_symbol_key = _normalize_etf_symbol_key(symbol)
        display_symbol_key = _display_etf_symbol(normalized_symbol_key)
        symbol_key_candidates = (
            normalized_symbol_key,
            normalized_symbol_key.lower(),
            normalized_symbol_key.upper(),
            display_symbol_key,
            display_symbol_key.lower(),
            display_symbol_key.upper(),
        )
        next_open_price = 0.0
        if next_day is not None:
            for key in symbol_key_candidates:
                try:
                    price = float(open_idx.get((next_day, key), 0.0) or 0.0)
                except Exception:
                    price = 0.0
                if np.isfinite(price) and price > 0.0:
                    next_open_price = float(price)
                    break
        col_idx = None
        for key in symbol_key_candidates:
            candidate_col_idx = sym_to_col.get(key)
            if candidate_col_idx is not None:
                col_idx = candidate_col_idx
                break
        close_price = (
            float(close_matrix[day_idx, col_idx])
            if col_idx is not None and day_idx < int(close_matrix.shape[0])
            else 0.0
        )
        reference_price = float(next_open_price or close_price or 0.0)
        if not np.isfinite(reference_price) or reference_price <= 0.0:
            continue
        max_sell_qty = (held_qty // effective_lot_size) * effective_lot_size
        if max_sell_qty <= 0:
            continue
        remaining_cash = max(target_cash - released_cash, 0.0)
        per_symbol_cap_cash = min(
            remaining_cash,
            float(nav) * float(current_symbol_exposure) * float(per_symbol_release_cap_ratio or 0.0),
        )
        if per_symbol_cap_cash <= 1e-12:
            per_symbol_cap_cash = remaining_cash
        requested_qty = int(math.floor(per_symbol_cap_cash / float(reference_price)))
        if requested_qty <= 0:
            requested_qty = effective_lot_size
        requested_qty = (requested_qty // effective_lot_size) * effective_lot_size
        if requested_qty <= 0:
            requested_qty = effective_lot_size
        qty = min(max_sell_qty, requested_qty)
        qty = (qty // effective_lot_size) * effective_lot_size
        if qty <= 0:
            continue
        release_plan[symbol] = int(qty)
        released_cash += float(qty) * float(reference_price)

    if not release_plan:
        return {}, 0.0, "ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_LIQUID_RELEASE"
    return release_plan, float(released_cash), ""


def _normalize_account_transition_reject_reason(code: str) -> str:
    normalized = str(code or "").strip()
    if not normalized:
        return ""
    legacy_prefix = "ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_"
    if normalized.startswith(legacy_prefix):
        return "ETF_BETA_ACCOUNT_TRANSITION_HANDOFF_REJECT_" + normalized[len(legacy_prefix):]
    return normalized


def build_etf_day_signals(provider, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
    self = provider
    held_qty_by_symbol = {
        _normalize_etf_symbol_key(symbol): int(qty)
        for symbol, qty in dict(ctx.positions or {}).items()
        if _normalize_etf_symbol_key(symbol) and int(qty) > 0
    }
    held_symbols = set(held_qty_by_symbol.keys())
    state_5 = str(
        self._effective_state_5_arr[day_idx]
        if day_idx < len(self._effective_state_5_arr)
        else self._market_state_name_map.get(day, "")
    ).strip().upper()
    trade_mode = str(
        self._trade_mode_name_arr[day_idx]
        if day_idx < len(self._trade_mode_name_arr)
        else self._trade_mode_name_map.get(day, "")
    ).strip().upper()
    slot_cap = int(self._etf_beta_slot_cap_arr[day_idx]) if day_idx < len(self._etf_beta_slot_cap_arr) else 0
    rebalance_day = bool(self._etf_beta_rebalance_flag_arr[day_idx]) if day_idx < len(self._etf_beta_rebalance_flag_arr) else False
    eligible_symbols = (
        [str(symbol).strip().upper() for symbol in _sequence_payload(self._etf_beta_eligible_symbols_arr[day_idx])]
        if day_idx < len(self._etf_beta_eligible_symbols_arr)
        else []
    )
    selected_symbols = (
        [str(symbol).strip().upper() for symbol in _sequence_payload(self._etf_beta_selected_symbols_arr[day_idx])]
        if day_idx < len(self._etf_beta_selected_symbols_arr)
        else []
    )
    selection_reason_codes = (
        dict(self._etf_beta_selection_reason_codes_arr[day_idx] or {})
        if day_idx < len(self._etf_beta_selection_reason_codes_arr)
        else {}
    )
    runtime_reason_codes = (
        [str(code).strip() for code in _sequence_payload(self._etf_beta_runtime_reason_codes_arr[day_idx])]
        if day_idx < len(self._etf_beta_runtime_reason_codes_arr)
        else []
    )
    vol_target_info = (
        dict(self._etf_beta_vol_target_info_arr[day_idx] or {})
        if day_idx < len(self._etf_beta_vol_target_info_arr)
        else {}
    )
    vol_target_scale_by_symbol = {
        str(symbol).strip().upper(): float(scale)
        for symbol, scale in dict(vol_target_info.get("scale_by_symbol") or {}).items()
        if str(symbol).strip()
    }
    vol_target_realized_vol_by_symbol = {
        str(symbol).strip().upper(): float(vol)
        for symbol, vol in dict(vol_target_info.get("realized_vol_by_symbol") or {}).items()
        if str(symbol).strip()
    }
    target_exposure = (
        float(self._etf_beta_target_exposure_arr[day_idx])
        if day_idx < len(self._etf_beta_target_exposure_arr)
        and np.isfinite(self._etf_beta_target_exposure_arr[day_idx])
        else None
    )
    target_exposure_source = (
        str(self._etf_beta_target_exposure_source_arr[day_idx] or "").strip()
        if day_idx < len(self._etf_beta_target_exposure_source_arr)
        else ""
    )
    min_deployable_exposure = (
        float(self._etf_beta_min_deployable_exposure_arr[day_idx])
        if day_idx < len(self._etf_beta_min_deployable_exposure_arr)
        and np.isfinite(self._etf_beta_min_deployable_exposure_arr[day_idx])
        else None
    )
    min_deployable_exposure_source = (
        str(self._etf_beta_min_deployable_exposure_source_arr[day_idx] or "").strip()
        if day_idx < len(self._etf_beta_min_deployable_exposure_source_arr)
        else ""
    )
    target_selected_count = (
        int(self._etf_beta_target_selected_count_arr[day_idx])
        if day_idx < len(self._etf_beta_target_selected_count_arr)
        else 0
    )
    target_exposure_per_symbol = (
        float(self._etf_beta_target_exposure_per_symbol_arr[day_idx])
        if day_idx < len(self._etf_beta_target_exposure_per_symbol_arr)
        and np.isfinite(self._etf_beta_target_exposure_per_symbol_arr[day_idx])
        else None
    )
    target_actual_exposure = (
        float(self._etf_beta_target_actual_exposure_arr[day_idx])
        if day_idx < len(self._etf_beta_target_actual_exposure_arr)
        and np.isfinite(self._etf_beta_target_actual_exposure_arr[day_idx])
        else None
    )
    target_deployability_gap = (
        float(self._etf_beta_target_deployability_gap_arr[day_idx])
        if day_idx < len(self._etf_beta_target_deployability_gap_arr)
        and np.isfinite(self._etf_beta_target_deployability_gap_arr[day_idx])
        else None
    )
    fallback_allowed = (
        bool(self._etf_beta_fallback_allowed_arr[day_idx])
        if day_idx < len(self._etf_beta_fallback_allowed_arr)
        else False
    )
    exposure_policy_family = (
        str(self._etf_beta_exposure_policy_family_arr[day_idx] or "").strip()
        if day_idx < len(self._etf_beta_exposure_policy_family_arr)
        else self._etf_beta_exposure_policy_family
    )
    policy_scope = (
        str(self._etf_beta_policy_scope_arr[day_idx] or "").strip()
        if day_idx < len(self._etf_beta_policy_scope_arr)
        else self._etf_beta_policy_scope
    )
    broad_based_only = (
        bool(self._etf_beta_broad_based_only_arr[day_idx])
        if day_idx < len(self._etf_beta_broad_based_only_arr)
        else bool(self._etf_beta_broad_based_only)
    )
    strategy_role = str(self._etf_beta_strategy_role or "").strip()
    governor_boundary_mode = str(self._etf_beta_governor_boundary_mode or "").strip()
    local_policy_mode = str(self._etf_beta_local_policy_mode or "").strip()
    layering_policy = (
        str(self._etf_beta_layering_policy_arr[day_idx] or "").strip()
        if day_idx < len(self._etf_beta_layering_policy_arr)
        else self._etf_beta_layering_policy
    )
    controlled_accumulation_mode = str(self._etf_beta_controlled_accumulation_mode or "").strip()
    layering_band = (
        str(self._etf_beta_layering_band_arr[day_idx] or "").strip()
        if day_idx < len(self._etf_beta_layering_band_arr)
        else ""
    )
    layering_active = (
        bool(self._etf_beta_layering_active_arr[day_idx])
        if day_idx < len(self._etf_beta_layering_active_arr)
        else False
    )
    layering_reason_codes = (
        [str(code).strip() for code in _sequence_payload(self._etf_beta_layering_reason_codes_arr[day_idx]) if str(code).strip()]
        if day_idx < len(self._etf_beta_layering_reason_codes_arr)
        else []
    )
    target_selected_count_source = (
        str(self._etf_beta_target_selected_count_source_arr[day_idx] or "").strip()
        if day_idx < len(self._etf_beta_target_selected_count_source_arr)
        else ""
    )
    fallback_allowed_source = (
        str(self._etf_beta_fallback_allowed_source_arr[day_idx] or "").strip()
        if day_idx < len(self._etf_beta_fallback_allowed_source_arr)
        else ""
    )
    core_slot_selected_symbol = (
        str(self._etf_beta_core_slot_selected_symbol_arr[day_idx] or "").strip().upper()
        if day_idx < len(self._etf_beta_core_slot_selected_symbol_arr)
        else ""
    )
    growth_slot_selected_symbol = (
        str(self._etf_beta_growth_slot_selected_symbol_arr[day_idx] or "").strip().upper()
        if day_idx < len(self._etf_beta_growth_slot_selected_symbol_arr)
        else ""
    )
    slot_selection_reason_codes = (
        dict(self._etf_beta_slot_selection_reason_codes_arr[day_idx] or {})
        if day_idx < len(self._etf_beta_slot_selection_reason_codes_arr)
        else {}
    )
    slot_under_deploy_reason_codes = (
        dict(self._etf_beta_slot_under_deploy_reason_codes_arr[day_idx] or {})
        if day_idx < len(self._etf_beta_slot_under_deploy_reason_codes_arr)
        else {}
    )
    core_slot_target_exposure = (
        float(self._etf_beta_core_slot_target_exposure_arr[day_idx])
        if day_idx < len(self._etf_beta_core_slot_target_exposure_arr)
        and np.isfinite(self._etf_beta_core_slot_target_exposure_arr[day_idx])
        else None
    )
    growth_slot_target_exposure = (
        float(self._etf_beta_growth_slot_target_exposure_arr[day_idx])
        if day_idx < len(self._etf_beta_growth_slot_target_exposure_arr)
        and np.isfinite(self._etf_beta_growth_slot_target_exposure_arr[day_idx])
        else None
    )
    core_slot_target_actual_exposure = (
        float(self._etf_beta_core_slot_target_actual_exposure_arr[day_idx])
        if day_idx < len(self._etf_beta_core_slot_target_actual_exposure_arr)
        and np.isfinite(self._etf_beta_core_slot_target_actual_exposure_arr[day_idx])
        else None
    )
    growth_slot_target_actual_exposure = (
        float(self._etf_beta_growth_slot_target_actual_exposure_arr[day_idx])
        if day_idx < len(self._etf_beta_growth_slot_target_actual_exposure_arr)
        and np.isfinite(self._etf_beta_growth_slot_target_actual_exposure_arr[day_idx])
        else None
    )
    requested_budget = (
        float(self._etf_beta_requested_budget_arr[day_idx])
        if day_idx < len(self._etf_beta_requested_budget_arr)
        and np.isfinite(self._etf_beta_requested_budget_arr[day_idx])
        else None
    )
    applied_budget = (
        float(self._etf_beta_applied_budget_arr[day_idx])
        if day_idx < len(self._etf_beta_applied_budget_arr)
        and np.isfinite(self._etf_beta_applied_budget_arr[day_idx])
        else None
    )
    cash_weight = (
        float(self._etf_beta_cash_weight_arr[day_idx])
        if day_idx < len(self._etf_beta_cash_weight_arr)
        and np.isfinite(self._etf_beta_cash_weight_arr[day_idx])
        else None
    )
    defense_weight = (
        float(self._etf_beta_defense_weight_arr[day_idx])
        if day_idx < len(self._etf_beta_defense_weight_arr)
        and np.isfinite(self._etf_beta_defense_weight_arr[day_idx])
        else None
    )
    equity_core_bucket = (
        float(self._etf_beta_equity_core_bucket_arr[day_idx])
        if day_idx < len(self._etf_beta_equity_core_bucket_arr)
        and np.isfinite(self._etf_beta_equity_core_bucket_arr[day_idx])
        else None
    )
    defense_tilt_bucket = (
        float(self._etf_beta_defense_tilt_bucket_arr[day_idx])
        if day_idx < len(self._etf_beta_defense_tilt_bucket_arr)
        and np.isfinite(self._etf_beta_defense_tilt_bucket_arr[day_idx])
        else None
    )
    cash_buffer_bucket = (
        float(self._etf_beta_cash_buffer_bucket_arr[day_idx])
        if day_idx < len(self._etf_beta_cash_buffer_bucket_arr)
        and np.isfinite(self._etf_beta_cash_buffer_bucket_arr[day_idx])
        else None
    )
    strategic_floor_cap_arr = getattr(self, "_etf_beta_strategic_floor_cap_arr", np.array([], dtype=float))
    tactical_overlay_cap_arr = getattr(self, "_etf_beta_tactical_overlay_cap_arr", np.array([], dtype=float))
    limited_defense_cap_arr = getattr(self, "_etf_beta_limited_defense_cap_arr", np.array([], dtype=float))
    deployment_pace_arr = getattr(self, "_etf_beta_deployment_pace_arr", np.array([], dtype=float))
    pace_policy_gap_arr = getattr(self, "_etf_beta_pace_policy_gap_arr", np.array([], dtype=float))
    pace_policy_reason_code_arr = getattr(self, "_etf_beta_pace_policy_reason_code_arr", np.array([], dtype=object))
    pace_policy_mode_arr = getattr(self, "_etf_beta_pace_policy_mode_arr", np.array([], dtype=object))
    bull_partial_overlay_pace_ratio_arr = getattr(
        self,
        "_etf_beta_bull_partial_overlay_pace_ratio_arr",
        np.array([], dtype=float),
    )
    bull_pace_mode_arr = getattr(self, "_etf_beta_bull_pace_mode_arr", np.array([], dtype=object))
    hard_block_flags_arr = getattr(self, "_etf_beta_hard_block_flags_arr", np.array([], dtype=object))
    core_accumulator_symbols_arr = getattr(self, "_etf_beta_core_accumulator_symbols_arr", np.array([], dtype=object))
    tactical_satellite_symbols_arr = getattr(self, "_etf_beta_tactical_satellite_symbols_arr", np.array([], dtype=object))
    limited_defense_symbols_arr = getattr(self, "_etf_beta_limited_defense_symbols_arr", np.array([], dtype=object))
    symbol_role_map_arr = getattr(self, "_etf_beta_symbol_role_map_arr", np.array([], dtype=object))
    strategic_floor_cap = (
        float(strategic_floor_cap_arr[day_idx])
        if day_idx < len(strategic_floor_cap_arr) and np.isfinite(strategic_floor_cap_arr[day_idx])
        else None
    )
    tactical_overlay_cap = (
        float(tactical_overlay_cap_arr[day_idx])
        if day_idx < len(tactical_overlay_cap_arr) and np.isfinite(tactical_overlay_cap_arr[day_idx])
        else None
    )
    limited_defense_cap = (
        float(limited_defense_cap_arr[day_idx])
        if day_idx < len(limited_defense_cap_arr) and np.isfinite(limited_defense_cap_arr[day_idx])
        else None
    )
    deployment_pace = (
        float(deployment_pace_arr[day_idx])
        if day_idx < len(deployment_pace_arr) and np.isfinite(deployment_pace_arr[day_idx])
        else None
    )
    pace_policy_gap = (
        float(pace_policy_gap_arr[day_idx])
        if day_idx < len(pace_policy_gap_arr) and np.isfinite(pace_policy_gap_arr[day_idx])
        else (
            max(float(target_exposure or 0.0) - float(deployment_pace or 0.0), 0.0)
            if target_exposure is not None and deployment_pace is not None
            else None
        )
    )
    pace_policy_reason_code = (
        str(pace_policy_reason_code_arr[day_idx]).strip()
        if day_idx < len(pace_policy_reason_code_arr) and str(pace_policy_reason_code_arr[day_idx]).strip()
        else (
            "ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY"
            if state_5 in {"BULL", "TRANS_UP"} and pace_policy_gap is not None and float(pace_policy_gap) > 1e-12
            else None
        )
    )
    pace_policy_mode = (
        str(pace_policy_mode_arr[day_idx]).strip()
        if day_idx < len(pace_policy_mode_arr) and str(pace_policy_mode_arr[day_idx]).strip()
        else ("floor_only_between_rebalances" if pace_policy_reason_code is not None else None)
    )
    bull_partial_overlay_pace_ratio = (
        float(bull_partial_overlay_pace_ratio_arr[day_idx])
        if day_idx < len(bull_partial_overlay_pace_ratio_arr) and np.isfinite(bull_partial_overlay_pace_ratio_arr[day_idx])
        else (
            float(getattr(self, "_etf_beta_bull_partial_overlay_pace_ratio", CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO))
            if state_5 == "BULL"
            else None
        )
    )
    bull_pace_mode = (
        str(bull_pace_mode_arr[day_idx]).strip()
        if day_idx < len(bull_pace_mode_arr) and str(bull_pace_mode_arr[day_idx]).strip()
        else None
    )
    hard_block_flags = (
        [str(code).strip() for code in _sequence_payload(hard_block_flags_arr[day_idx]) if str(code).strip()]
        if day_idx < len(hard_block_flags_arr)
        else []
    )
    core_accumulator_symbols = (
        [str(symbol).strip().upper() for symbol in _sequence_payload(core_accumulator_symbols_arr[day_idx]) if str(symbol).strip()]
        if day_idx < len(core_accumulator_symbols_arr)
        else []
    )
    tactical_satellite_symbols = (
        [str(symbol).strip().upper() for symbol in _sequence_payload(tactical_satellite_symbols_arr[day_idx]) if str(symbol).strip()]
        if day_idx < len(tactical_satellite_symbols_arr)
        else []
    )
    limited_defense_symbols = (
        [str(symbol).strip().upper() for symbol in _sequence_payload(limited_defense_symbols_arr[day_idx]) if str(symbol).strip()]
        if day_idx < len(limited_defense_symbols_arr)
        else []
    )
    symbol_role_map = (
        {
            str(symbol).strip().upper(): str(role).strip()
            for symbol, role in dict(symbol_role_map_arr[day_idx] or {}).items()
            if str(symbol).strip() and str(role).strip()
        }
        if day_idx < len(symbol_role_map_arr)
        else {}
    )
    target_exposure_by_symbol = (
        {
            str(symbol).strip().upper(): float(value)
            for symbol, value in dict(self._etf_beta_targets_arr[day_idx] or {}).items()
            if str(symbol).strip()
        }
        if day_idx < len(self._etf_beta_targets_arr)
        else {}
    )
    allocation_reason_codes = (
        [str(code).strip() for code in _sequence_payload(self._etf_beta_allocation_reason_codes_arr[day_idx]) if str(code).strip()]
        if day_idx < len(self._etf_beta_allocation_reason_codes_arr)
        else []
    )
    weak_state_defense_policy_id = str(getattr(self, "_etf_beta_weak_state_defense_policy_id", "") or "").strip() or None
    weak_state_defense_policy_active = "ETF_BETA_WEAK_STATE_DEFENSE_POLICY_ACTIVE" in runtime_reason_codes
    weak_state_defense_allow_core_beta = "ETF_BETA_WEAK_STATE_ALLOW_CORE_BETA" in runtime_reason_codes
    weak_state_defense_deployability_floor_applied = (
        "ETF_BETA_WEAK_STATE_DEFENSE_SEAT_FLOOR_ACTIVE" in runtime_reason_codes
    )
    weak_state_defense_candidate_symbols = list(limited_defense_symbols) if weak_state_defense_policy_active else []
    weak_state_defense_unavailable_reason_codes = [
        str(code).strip()
        for code in list(runtime_reason_codes)
        if str(code).strip()
        in {
            "ETF_BETA_WEAK_STATE_NO_DEFENSE_CANDIDATES",
            "ETF_BETA_WEAK_STATE_NO_DEPLOYABLE_DEFENSE_CANDIDATES",
        }
    ]
    boundary_policy_mode = str(getattr(self, "_etf_beta_boundary_policy_mode", "") or "").strip()
    governor_hard_blocked = "ETF_BETA_PHASE1_GOVERNOR_HARD_BLOCK" in runtime_reason_codes
    governor_hard_block_reason_codes: list[str] = []
    local_boundary_state = next(
        (
            str(code).split("ETF_BETA_LOCAL_BOUNDARY_STATE::", 1)[1].strip()
            for code in runtime_reason_codes
            if str(code).startswith("ETF_BETA_LOCAL_BOUNDARY_STATE::")
        ),
        "",
    )
    local_boundary_reason_codes = [
        str(code).strip()
        for code in runtime_reason_codes
        if str(code).strip().startswith("BOUNDARY_POLICY::")
        or str(code).strip().startswith("LOCAL_BOUNDARY_STATE::")
        or str(code).strip() == "PHASE1_DOCUMENT_REDUCED_ALLOCATION"
    ]
    absolute_filter_reject_count = (
        int(self._etf_beta_absolute_filter_reject_count_arr[day_idx])
        if day_idx < len(self._etf_beta_absolute_filter_reject_count_arr)
        else 0
    )
    absolute_filter_reject_reason_counts = (
        dict(self._etf_beta_absolute_filter_reject_reason_counts_arr[day_idx] or {})
        if day_idx < len(self._etf_beta_absolute_filter_reject_reason_counts_arr)
        else {}
    )
    is_phase1_allocation_engine = _is_formal_stabilizer_role(strategy_role, local_policy_mode)
    standalone_mainline_active = _is_standalone_mainline_role(
        strategy_role,
        local_policy_mode=local_policy_mode,
        exposure_policy_family=exposure_policy_family,
    )
    trans_up_contract_mode = (
        "single_seat_core_recovery"
        if bool(is_phase1_allocation_engine) and str(state_5 or "").upper() == "TRANS_UP"
        else ""
    )
    trans_up_single_seat_core_recovery = bool(trans_up_contract_mode == "single_seat_core_recovery")
    selection_chain_winner_counts = (
        dict(self._etf_beta_selection_chain_winner_counts_arr[day_idx] or {})
        if day_idx < len(self._etf_beta_selection_chain_winner_counts_arr)
        else {}
    )
    selection_chain_reject_reason_counts = (
        dict(self._etf_beta_selection_chain_reject_reason_counts_arr[day_idx] or {})
        if day_idx < len(self._etf_beta_selection_chain_reject_reason_counts_arr)
        else {}
    )
    configured_max_selected = (
        int(self._etf_beta_max_selected_symbols)
        if self._etf_beta_max_selected_symbols is not None and int(self._etf_beta_max_selected_symbols) > 0
        else None
    )
    selected_cap = int(slot_cap)
    if configured_max_selected is not None:
        selected_cap = min(int(slot_cap), int(configured_max_selected))
    fallback_active = any(
        "ETF_BETA_FALLBACK_SINGLE_SYMBOL" in [str(code).strip() for code in list(codes or [])]
        for codes in selection_reason_codes.values()
    )
    entry_reason_code = _entry_reason_code(self._etf_beta_rebalance_frequency)
    governor_boundary_reason_codes = [
        f"GOVERNOR_STATE::{state_5}",
        f"GOVERNOR_BOUNDARY_MODE::{governor_boundary_mode.upper()}" if governor_boundary_mode else "",
        f"GOVERNOR_TARGET_EXPOSURE_SOURCE::{target_exposure_source.upper()}" if target_exposure_source else "",
        f"GOVERNOR_TARGET_SELECTED_COUNT_SOURCE::{target_selected_count_source.upper()}" if target_selected_count_source else "",
        f"GOVERNOR_FALLBACK_ALLOWED_SOURCE::{fallback_allowed_source.upper()}" if fallback_allowed_source else "",
        f"GOVERNOR_LAYERING_BAND::{layering_band}" if layering_band else "",
    ]
    governor_boundary_reason_codes = [code for code in governor_boundary_reason_codes if code]
    previous_state_5 = (
        str(self._effective_state_5_arr[day_idx - 1] or "").strip().upper()
        if day_idx > 0 and (day_idx - 1) < len(self._effective_state_5_arr)
        else ""
    )
    normalized_core_accumulator_symbols = {
        _normalize_etf_symbol_key(symbol)
        for symbol in list(core_accumulator_symbols or [])
        if _normalize_etf_symbol_key(symbol)
    }
    selected_core_symbols = [
        str(symbol).strip().upper()
        for symbol in selected_symbols
        if _normalize_etf_symbol_key(symbol) in normalized_core_accumulator_symbols
    ]
    if not selected_core_symbols:
        selected_core_symbols = [
            str(symbol).strip().upper()
            for symbol, target_value in dict(target_exposure_by_symbol or {}).items()
            if _normalize_etf_symbol_key(symbol) in normalized_core_accumulator_symbols and float(target_value) > 0.0
        ]
    current_core_exposure = _group_exposure_from_holdings(
        ctx=ctx,
        day=day,
        day_idx=day_idx,
        held_qty_by_symbol=held_qty_by_symbol,
        group_symbols=list(core_accumulator_symbols),
        sym_to_col=self._sym_to_col,
        close_matrix=self._mx.close,
    )
    current_selected_exposure = _group_exposure_from_holdings(
        ctx=ctx,
        day=day,
        day_idx=day_idx,
        held_qty_by_symbol=held_qty_by_symbol,
        group_symbols=list(selected_symbols),
        sym_to_col=self._sym_to_col,
        close_matrix=self._mx.close,
    )
    current_total_exposure = _group_exposure_from_holdings(
        ctx=ctx,
        day=day,
        day_idx=day_idx,
        held_qty_by_symbol=held_qty_by_symbol,
        group_symbols=list(held_qty_by_symbol.keys()),
        sym_to_col=self._sym_to_col,
        close_matrix=self._mx.close,
    )
    current_defense_exposure = _group_exposure_from_holdings(
        ctx=ctx,
        day=day,
        day_idx=day_idx,
        held_qty_by_symbol=held_qty_by_symbol,
        group_symbols=list(limited_defense_symbols),
        sym_to_col=self._sym_to_col,
        close_matrix=self._mx.close,
    )
    trans_up_redeploy_floor_gap = max(float(strategic_floor_cap or 0.0) - float(current_core_exposure or 0.0), 0.0)
    trans_up_redeploy_active = False
    trans_up_redeploy_reason_code = ""
    trans_up_redeploy_reject_reason = ""
    trans_up_redeploy_target_per_symbol = None
    trans_up_redeploy_core_symbols: list[str] = []
    trans_up_state_change_edge = (
        bool(is_phase1_allocation_engine)
        and str(state_5 or "").upper() == "TRANS_UP"
        and previous_state_5 in _TRANS_UP_REDEPLOY_EDGE_FROM_STATES
    )
    if bool(is_phase1_allocation_engine) and str(state_5 or "").upper() == "TRANS_UP" and not bool(rebalance_day):
        if not trans_up_state_change_edge:
            trans_up_redeploy_reject_reason = "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_NOT_STATE_CHANGE_EDGE"
        elif governor_hard_blocked:
            trans_up_redeploy_reject_reason = "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_HARD_BLOCK"
        elif trans_up_redeploy_floor_gap <= 1e-12:
            trans_up_redeploy_reject_reason = "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_FLOOR_ALREADY_SATISFIED"
        elif not selected_core_symbols:
            trans_up_redeploy_reject_reason = "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_NO_CORE_SELECTION"
        else:
            trans_up_redeploy_active = True
            trans_up_redeploy_reason_code = "ETF_BETA_TRANS_UP_REDEPLOY_ACTIVE"
            trans_up_redeploy_core_symbols = list(selected_core_symbols)
            trans_up_redeploy_target_per_symbol = float(trans_up_redeploy_floor_gap) / float(len(trans_up_redeploy_core_symbols))
    standalone_deploy_active = False
    standalone_deploy_reason_code = ""
    standalone_deploy_reject_reason = ""
    standalone_deploy_target_weight_by_symbol: dict[str, float] = {}
    standalone_deploy_symbols: list[str] = []
    standalone_deploy_path = ""
    standalone_deploy_gap = 0.0
    weak_state_inter_redeploy_active = False
    weak_state_inter_redeploy_reason_code = ""
    weak_state_inter_redeploy_reject_reason = ""
    weak_state_inter_redeploy_symbols: list[str] = []
    weak_state_inter_redeploy_current_symbols: list[str] = []
    weak_state_inter_redeploy_posture_satisfied = False
    state_edge_cash_release_active = False
    state_edge_cash_release_reason_code = ""
    state_edge_cash_release_reject_reason = ""
    state_edge_cash_release_symbols: list[str] = []
    state_edge_cash_release_edge_from_state = previous_state_5
    state_edge_cash_release_edge_to_state = ""
    state_edge_cash_release_release_cash = 0.0
    state_edge_cash_release_release_destination = ""
    state_edge_cash_release_release_target_cash = 0.0
    state_edge_cash_release_bounded_partial_release_ratio_cap = 0.02
    state_edge_cash_release_plan: dict[str, int] = {}
    riskoff_account_budget_materialization_active = False
    riskoff_account_budget_materialization_reason_code = ""
    riskoff_account_budget_materialization_reject_reason = ""
    riskoff_account_budget_materialization_release_destination = ""
    riskoff_account_budget_materialization_release_target_cash = 0.0
    riskoff_account_budget_materialization_release_cash = 0.0
    riskoff_account_budget_materialization_symbols: list[str] = []
    riskoff_account_budget_materialization_target_symbols: list[str] = []
    riskoff_account_budget_materialization_bounded_partial_release_ratio_cap = 0.02
    riskoff_account_budget_materialization_plan: dict[str, int] = {}
    if standalone_mainline_active and not bool(rebalance_day):
        state_text = str(state_5 or "").upper()
        desired_live_exposure = max(float(target_exposure or 0.0), 0.0)
        standalone_active_symbols: list[str] = []
        weak_state_target_symbols: list[str] = []
        if state_text in {"TRANS_DOWN", "RISK_OFF"} and weak_state_defense_policy_active:
            weak_state_target_symbols = list(
                dict.fromkeys(
                    [
                        str(symbol).strip().upper()
                        for symbol, target_value in dict(target_exposure_by_symbol or {}).items()
                        if float(target_value) > 0.0
                        and (
                            str(symbol).strip().upper() in weak_state_defense_candidate_symbols
                            or (
                                bool(weak_state_defense_allow_core_beta)
                                and str(symbol).strip().upper() in selected_core_symbols
                            )
                        )
                    ]
                )
            )
            weak_state_inter_redeploy_current_symbols = [
                display_symbol
                for display_symbol in (
                    str(_display_etf_symbol(symbol) or "").strip().upper()
                    for symbol in held_symbols
                )
                if display_symbol
            ]
            weak_state_inter_redeploy_posture_satisfied = (
                bool(weak_state_target_symbols)
                and bool(weak_state_inter_redeploy_current_symbols)
                and set(weak_state_inter_redeploy_current_symbols).issubset(set(weak_state_target_symbols))
                and float(current_total_exposure or 0.0) >= float(desired_live_exposure or 0.0) - 1e-12
                and float(current_defense_exposure or 0.0) >= float(limited_defense_cap or 0.0) - 1e-12
            )
        state_edge_cash_release_edge_triggered = (
            state_text in {"TRANS_DOWN", "RISK_OFF"}
            and previous_state_5 in {"BULL", "TRANS_UP"}
            and weak_state_defense_policy_active
        )
        if state_edge_cash_release_edge_triggered:
            state_edge_cash_release_edge_from_state = previous_state_5
            state_edge_cash_release_edge_to_state = state_text
            state_edge_cash_release_release_destination = (
                "defense" if state_text == "TRANS_DOWN" else "accumulation"
            )
            if float(current_total_exposure or 0.0) <= float(desired_live_exposure or 0.0) + 1e-12:
                state_edge_cash_release_reject_reason = "ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_RELEASE_REQUIRED"
            else:
                state_edge_cash_release_release_target_cash = min(
                    float(getattr(ctx, "nav", 0.0) or 0.0) * float(state_edge_cash_release_bounded_partial_release_ratio_cap),
                    max(float(current_total_exposure or 0.0) - float(desired_live_exposure or 0.0), 0.0)
                    * float(getattr(ctx, "nav", 0.0) or 0.0),
                )
                state_edge_cash_release_plan, state_edge_cash_release_release_cash, state_edge_cash_release_reject_reason = (
                    _resolve_state_edge_cash_release_plan(
                        ctx=ctx,
                        day=day,
                        day_idx=day_idx,
                        held_qty_by_symbol=held_qty_by_symbol,
                        candidate_symbols=sorted(held_symbols),
                        release_target_cash=float(state_edge_cash_release_release_target_cash),
                        sym_to_col=self._sym_to_col,
                        close_matrix=self._mx.close,
                        lot_size=getattr(ctx, "lot_size", 100) or 100,
                    )
                )
                if state_edge_cash_release_plan:
                    state_edge_cash_release_active = True
                    state_edge_cash_release_reason_code = "ETF_BETA_STATE_EDGE_CASH_RELEASE_ACTIVE"
                    state_edge_cash_release_symbols = list(state_edge_cash_release_plan.keys())
                elif not state_edge_cash_release_reject_reason:
                    state_edge_cash_release_reject_reason = "ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_LIQUID_RELEASE"
        if (
            state_edge_cash_release_reject_reason
            and not state_edge_cash_release_active
            and not state_edge_cash_release_edge_triggered
        ):
            runtime_reason_codes.append(state_edge_cash_release_reject_reason)
        if state_text == "RISK_OFF" and weak_state_target_symbols and not governor_hard_blocked:
            materialization_plan = _resolve_riskoff_account_budget_materialization_plan(
                ctx=ctx,
                day=day,
                day_idx=day_idx,
                held_qty_by_symbol=held_qty_by_symbol,
                weak_state_target_symbols=weak_state_target_symbols,
                selected_core_symbols=selected_core_symbols,
                weak_state_defense_candidate_symbols=set(weak_state_defense_candidate_symbols),
                target_exposure_by_symbol=target_exposure_by_symbol,
                sym_to_col=self._sym_to_col,
                close_matrix=self._mx.close,
                open_matrix=self._mx.open,
                current_total_exposure=float(current_total_exposure or 0.0),
                current_core_exposure=float(current_core_exposure or 0.0),
                desired_live_exposure=float(desired_live_exposure or 0.0),
                bounded_partial_release_ratio_cap=riskoff_account_budget_materialization_bounded_partial_release_ratio_cap,
                lot_size=getattr(ctx, "lot_size", 100) or 100,
            )
            riskoff_account_budget_materialization_active = bool(materialization_plan.get("active"))
            riskoff_account_budget_materialization_reason_code = str(
                materialization_plan.get("reason_code") or ""
            ).strip()
            riskoff_account_budget_materialization_reject_reason = str(
                materialization_plan.get("reject_reason") or ""
            ).strip()
            riskoff_account_budget_materialization_release_destination = str(
                materialization_plan.get("release_destination") or ""
            ).strip()
            riskoff_account_budget_materialization_release_target_cash = float(
                materialization_plan.get("release_target_cash") or 0.0
            )
            riskoff_account_budget_materialization_release_cash = float(
                materialization_plan.get("release_cash") or 0.0
            )
            riskoff_account_budget_materialization_symbols = list(
                materialization_plan.get("release_symbols") or []
            )
            riskoff_account_budget_materialization_target_symbols = list(
                materialization_plan.get("target_symbols") or []
            )
            riskoff_account_budget_materialization_plan = dict(
                materialization_plan.get("release_plan") or {}
            )
            if (
                riskoff_account_budget_materialization_reject_reason
                and not riskoff_account_budget_materialization_active
            ):
                runtime_reason_codes.append(riskoff_account_budget_materialization_reject_reason)
        if (
            state_text in {"BULL", "TRANS_UP"}
            and selected_cap > 0
            and not selected_symbols
            and fallback_allowed
            and self._etf_beta_fallback_mode == "single_symbol"
            and self._etf_beta_fallback_symbol
            and self._etf_beta_fallback_symbol in self._sym_to_col
        ):
            fallback_display_symbol = _display_etf_symbol(self._etf_beta_fallback_symbol).upper()
            if fallback_display_symbol:
                selected_symbols.append(fallback_display_symbol)
                selection_reason_codes[fallback_display_symbol] = [
                    "ETF_BETA_FALLBACK_SINGLE_SYMBOL",
                    f"FALLBACK_SYMBOL::{fallback_display_symbol}",
                    f"STATE::{state_text}",
                    f"RULE_FAMILY::{self._etf_beta_rule_family.upper()}",
                    "UNDERFILLED_DEPLOYMENT_FILL",
                    "INTER_REBALANCE_DEPLOY_FILL",
                ]
                fallback_active = True
                runtime_reason_codes.append("ETF_BETA_FALLBACK_ACTIVE")
                runtime_reason_codes.append("ETF_BETA_FALLBACK_FULL_REPLACEMENT_ACTIVE")
                runtime_reason_codes.append("ETF_BETA_INTER_REBALANCE_FALLBACK_FILL_ACTIVE")
        if state_text == "BULL":
            standalone_active_symbols = list(selected_symbols)
            standalone_deploy_gap = max(float(desired_live_exposure) - float(current_total_exposure or 0.0), 0.0)
            if governor_hard_blocked:
                standalone_deploy_reject_reason = "ETF_BETA_BULL_INTER_REBALANCE_DEPLOY_REJECT_HARD_BLOCK"
            elif standalone_deploy_gap <= 1e-12:
                standalone_deploy_reject_reason = "ETF_BETA_BULL_INTER_REBALANCE_DEPLOY_REJECT_FULLY_DEPLOYED"
            elif not standalone_active_symbols:
                standalone_deploy_reject_reason = "ETF_BETA_BULL_INTER_REBALANCE_DEPLOY_REJECT_NO_SELECTION"
            else:
                standalone_deploy_active = True
                standalone_deploy_reason_code = "ETF_BETA_BULL_INTER_REBALANCE_DEPLOY_ACTIVE"
                standalone_deploy_symbols = list(standalone_active_symbols)
                standalone_deploy_path = "bull_inter_rebalance_deploy"
        elif state_text == "TRANS_UP":
            standalone_active_symbols = list(selected_symbols)
            standalone_deploy_gap = max(float(desired_live_exposure) - float(current_total_exposure or 0.0), 0.0)
            if governor_hard_blocked:
                standalone_deploy_reject_reason = "ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_REJECT_HARD_BLOCK"
            elif standalone_deploy_gap <= 1e-12:
                standalone_deploy_reject_reason = "ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_REJECT_FULLY_DEPLOYED"
            elif not standalone_active_symbols:
                standalone_deploy_reject_reason = "ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_REJECT_NO_SELECTION"
            else:
                standalone_deploy_active = True
                standalone_deploy_reason_code = "ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_ACTIVE"
                standalone_deploy_symbols = list(standalone_active_symbols)
                standalone_deploy_path = "trans_up_inter_rebalance_deploy"
        elif state_text in {"TRANS_DOWN", "RISK_OFF"} and weak_state_defense_policy_active:
            defense_floor_gap = max(float(limited_defense_cap or 0.0) - float(current_defense_exposure or 0.0), 0.0)
            defense_only_symbols = [
                str(symbol).strip().upper()
                for symbol in list(weak_state_target_symbols or [])
                if str(symbol).strip().upper() in weak_state_defense_candidate_symbols
            ]
            standalone_active_symbols = list(defense_only_symbols or weak_state_target_symbols)
            standalone_deploy_gap = max(
                max(float(desired_live_exposure) - float(current_total_exposure or 0.0), 0.0),
                float(defense_floor_gap),
            )
            if governor_hard_blocked:
                weak_state_inter_redeploy_reject_reason = (
                    "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_HARD_BLOCK"
                    if state_text == "RISK_OFF"
                    else "ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_HARD_BLOCK"
                )
                standalone_deploy_reject_reason = weak_state_inter_redeploy_reject_reason
            elif weak_state_inter_redeploy_posture_satisfied:
                weak_state_inter_redeploy_reject_reason = (
                    "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_TARGET_SATISFIED"
                    if state_text == "RISK_OFF"
                    else "ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_ALREADY_DEFENSIVE"
                )
                standalone_deploy_reject_reason = weak_state_inter_redeploy_reject_reason
            elif not standalone_active_symbols:
                weak_state_inter_redeploy_reject_reason = (
                    "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_NO_SELECTION"
                    if state_text == "RISK_OFF"
                    else "ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_NO_DEFENSE_SELECTION"
                )
                standalone_deploy_reject_reason = weak_state_inter_redeploy_reject_reason
            else:
                weak_state_inter_redeploy_active = True
                weak_state_inter_redeploy_reason_code = (
                    "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_ACTIVE"
                    if state_text == "RISK_OFF"
                    else "ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_ACTIVE"
                )
                weak_state_inter_redeploy_symbols = list(standalone_active_symbols)
                standalone_deploy_active = True
                standalone_deploy_reason_code = weak_state_inter_redeploy_reason_code
                standalone_deploy_symbols = list(standalone_active_symbols)
                standalone_deploy_path = (
                    "riskoff_cash_drip_topup"
                    if state_text == "RISK_OFF"
                    else "weak_state_inter_rebalance_defense_redeploy"
                )
        elif state_text == "RISK_OFF":
            standalone_active_symbols = list(selected_core_symbols)
            standalone_deploy_gap = max(float(desired_live_exposure) - float(current_total_exposure or 0.0), 0.0)
            if governor_hard_blocked:
                standalone_deploy_reject_reason = "ETF_BETA_RISK_OFF_CORE_ACCUMULATION_REJECT_HARD_BLOCK"
            elif standalone_deploy_gap <= 1e-12:
                standalone_deploy_reject_reason = "ETF_BETA_RISK_OFF_CORE_ACCUMULATION_REJECT_FULLY_DEPLOYED"
            elif not standalone_active_symbols:
                standalone_deploy_reject_reason = "ETF_BETA_RISK_OFF_CORE_ACCUMULATION_REJECT_NO_CORE_SELECTION"
            else:
                standalone_deploy_active = True
                standalone_deploy_reason_code = "ETF_BETA_RISK_OFF_CORE_ACCUMULATION_ACTIVE"
                standalone_deploy_symbols = list(standalone_active_symbols)
                standalone_deploy_path = "risk_off_core_accumulation_deploy"
        if standalone_deploy_active and standalone_deploy_symbols:
            if weak_state_inter_redeploy_active and state_text == "RISK_OFF":
                ordered_riskoff_symbols = sorted(
                    list(standalone_deploy_symbols),
                    key=lambda symbol: (
                        1 if str(symbol).strip().upper() in selected_core_symbols else 0,
                        -float(dict(target_exposure_by_symbol or {}).get(str(symbol).strip().upper(), 0.0) or 0.0),
                        str(symbol).strip().upper(),
                    ),
                )
                standalone_deploy_target_weight_by_symbol, riskoff_cash_drip_reject_reason = (
                    _resolve_riskoff_cash_drip_target_weights(
                        ctx=ctx,
                        day=day,
                        day_idx=day_idx,
                        held_qty_by_symbol=held_qty_by_symbol,
                        deploy_symbols=list(ordered_riskoff_symbols),
                        target_exposure_by_symbol=target_exposure_by_symbol,
                        sym_to_col=self._sym_to_col,
                        close_matrix=self._mx.close,
                        cash_available_override=float(getattr(ctx, "cash", 0.0) or 0.0)
                        + float(state_edge_cash_release_release_cash or 0.0)
                        + float(riskoff_account_budget_materialization_release_cash or 0.0),
                    )
                )
                if standalone_deploy_target_weight_by_symbol:
                    standalone_deploy_symbols = list(standalone_deploy_target_weight_by_symbol.keys())
                    weak_state_inter_redeploy_symbols = list(standalone_deploy_symbols)
                    weak_state_inter_redeploy_reason_code = (
                        "ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_ACTIVE"
                        if riskoff_account_budget_materialization_active
                        else "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_ACTIVE"
                    )
                    standalone_deploy_reason_code = weak_state_inter_redeploy_reason_code
                    standalone_deploy_path = (
                        "riskoff_account_budget_materialization"
                        if riskoff_account_budget_materialization_active
                        else "riskoff_cash_drip_topup"
                    )
                else:
                    weak_state_inter_redeploy_active = False
                    weak_state_inter_redeploy_reject_reason = (
                        riskoff_cash_drip_reject_reason
                        or "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_EXECUTION_CONSTRAINT"
                    )
                    standalone_deploy_active = False
                    standalone_deploy_reason_code = ""
                    standalone_deploy_reject_reason = weak_state_inter_redeploy_reject_reason
                    standalone_deploy_symbols = []
                    standalone_deploy_path = ""
                    weak_state_inter_redeploy_symbols = []
            else:
                standalone_deploy_target_weight_by_symbol = _resolve_standalone_deploy_delta_target_weights(
                    ctx=ctx,
                    day=day,
                    day_idx=day_idx,
                    held_qty_by_symbol=held_qty_by_symbol,
                    deploy_symbols=list(standalone_deploy_symbols),
                    target_exposure_by_symbol=target_exposure_by_symbol,
                    standalone_deploy_gap=float(standalone_deploy_gap),
                    sym_to_col=self._sym_to_col,
                    close_matrix=self._mx.close,
                )
                if weak_state_inter_redeploy_active and not standalone_deploy_target_weight_by_symbol:
                    weak_state_inter_redeploy_active = False
                    weak_state_inter_redeploy_reject_reason = (
                        "ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_EXECUTION_CONSTRAINT"
                    )
                    standalone_deploy_active = False
                    standalone_deploy_reason_code = ""
                    standalone_deploy_reject_reason = weak_state_inter_redeploy_reject_reason
                    standalone_deploy_symbols = []
                    standalone_deploy_path = ""
                    weak_state_inter_redeploy_symbols = []

    selected_lower = {_normalize_etf_symbol_key(symbol) for symbol in selected_symbols}
    strength_map: dict[str, float] = {}
    mf_score_map: dict[str, float] = {}
    for symbol in set(selected_lower) | held_symbols:
        col_idx = self._sym_to_col.get(symbol)
        if col_idx is None:
            continue
        close_now = float(self._mx.close[day_idx, col_idx])
        ma120_now = float(self._feats.trend_fast_ma[day_idx, col_idx])
        if close_now != close_now or ma120_now != ma120_now:
            continue
        score = 0.0
        if symbol.upper() in selected_symbols:
            rank_map = selection_reason_codes.get(symbol.upper()) or []
            if rank_map:
                score = 1.0
        strength_map[symbol] = float(score)
        mf_score_map[symbol] = float(score)
    if trans_up_redeploy_active:
        runtime_reason_codes = [
            code
            for code in list(runtime_reason_codes)
            if str(code).strip() != _await_rebalance_reason_code(self._etf_beta_rebalance_frequency)
        ]
        runtime_reason_codes.append(trans_up_redeploy_reason_code)
        runtime_reason_codes.append(f"ETF_BETA_TRANS_UP_REDEPLOY_EDGE::{previous_state_5}_TO_TRANS_UP")
    elif standalone_deploy_active:
        runtime_reason_codes = [
            code
            for code in list(runtime_reason_codes)
            if str(code).strip() != _await_rebalance_reason_code(self._etf_beta_rebalance_frequency)
        ]
        runtime_reason_codes.append(standalone_deploy_reason_code)
    elif weak_state_inter_redeploy_reject_reason:
        runtime_reason_codes = [
            code
            for code in list(runtime_reason_codes)
            if str(code).strip() != _await_rebalance_reason_code(self._etf_beta_rebalance_frequency)
        ]
        runtime_reason_codes.append(weak_state_inter_redeploy_reject_reason)
    elif trans_up_redeploy_reject_reason:
        runtime_reason_codes.append(trans_up_redeploy_reject_reason)
    elif standalone_deploy_reject_reason:
        runtime_reason_codes.append(standalone_deploy_reject_reason)
    out_of_scope_symbols = list(getattr(self, "_etf_beta_out_of_scope_symbols", []) or [])
    out_of_scope_reason_codes = dict(getattr(self, "_etf_beta_out_of_scope_reason_codes", {}) or {})

    formal_view_payload = build_etf_beta_formal_view(
        {
            "effective_state_5": state_5,
            "strategy_role": strategy_role,
            "governor_boundary_mode": governor_boundary_mode,
            "local_policy_mode": local_policy_mode,
            "boundary_policy_mode": boundary_policy_mode,
            "exposure_policy_family": exposure_policy_family,
            "policy_scope": policy_scope,
            "broad_based_only": bool(broad_based_only),
            "reason_codes": list(allocation_reason_codes),
            "target_exposure": target_exposure,
            "target_exposure_source": target_exposure_source,
            "min_deployable_exposure": min_deployable_exposure,
            "min_deployable_exposure_source": min_deployable_exposure_source,
            "target_selected_count": int(target_selected_count),
            "target_selected_count_source": target_selected_count_source,
            "fallback_allowed": bool(fallback_allowed),
            "fallback_allowed_source": fallback_allowed_source,
            "targets": dict(target_exposure_by_symbol),
            "selected_symbols": list(selected_symbols),
            "eligible_etfs": list(eligible_symbols),
            "selected_etfs": list(selected_symbols),
            "selection_reason_codes": dict(selection_reason_codes),
            "out_of_scope_etfs": list(out_of_scope_symbols),
            "out_of_scope_reason_codes": dict(out_of_scope_reason_codes),
            "formal_core_beta_symbols": list(
                getattr(self, "_etf_beta_formal_core_beta_symbols", self._etf_beta_formal_scope_symbols) or []
            ),
            "limited_defense_candidates": list(getattr(self, "_etf_beta_limited_defense_candidates", []) or []),
            "weak_state_defense_policy_id": weak_state_defense_policy_id,
            "weak_state_defense_policy_active": bool(weak_state_defense_policy_active),
            "weak_state_defense_candidate_symbols": list(weak_state_defense_candidate_symbols),
            "weak_state_defense_allow_core_beta": bool(weak_state_defense_allow_core_beta),
            "weak_state_defense_deployability_floor_applied": bool(weak_state_defense_deployability_floor_applied),
            "weak_state_defense_unavailable_reason_codes": list(weak_state_defense_unavailable_reason_codes),
            "weak_state_inter_rebalance_defense_redeploy_active": bool(weak_state_inter_redeploy_active),
            "weak_state_inter_rebalance_defense_redeploy_reason_code": weak_state_inter_redeploy_reason_code or None,
            "weak_state_inter_rebalance_defense_redeploy_reject_reason": (
                weak_state_inter_redeploy_reject_reason or None
            ),
            "weak_state_inter_rebalance_defense_redeploy_symbols": list(weak_state_inter_redeploy_symbols),
            "weak_state_inter_rebalance_defense_current_symbols": list(weak_state_inter_redeploy_current_symbols),
            "weak_state_inter_rebalance_defense_posture_satisfied": bool(
                weak_state_inter_redeploy_posture_satisfied
            ),
            "state_edge_cash_release_active": bool(state_edge_cash_release_active),
            "state_edge_cash_release_reason_code": state_edge_cash_release_reason_code or None,
            "state_edge_cash_release_reject_reason": state_edge_cash_release_reject_reason or None,
            "state_edge_cash_release_edge_from_state": state_edge_cash_release_edge_from_state or None,
            "state_edge_cash_release_edge_to_state": state_edge_cash_release_edge_to_state or None,
            "state_edge_cash_release_release_destination": state_edge_cash_release_release_destination or None,
            "state_edge_cash_release_release_target_cash": float(state_edge_cash_release_release_target_cash or 0.0),
            "state_edge_cash_release_release_cash": float(state_edge_cash_release_release_cash or 0.0),
            "state_edge_cash_release_bounded_partial_release_ratio_cap": float(
                state_edge_cash_release_bounded_partial_release_ratio_cap or 0.0
            ),
            "state_edge_cash_release_symbols": list(state_edge_cash_release_symbols),
            "governor_hard_blocked": bool(governor_hard_blocked),
            "governor_hard_block_reason_codes": list(governor_hard_block_reason_codes),
            "governor_budget_reason_codes": list(governor_boundary_reason_codes),
            "local_boundary_state": local_boundary_state or None,
            "local_boundary_reason_codes": list(local_boundary_reason_codes),
            "governor_boundary": {
                "hard_blocked": bool(governor_hard_blocked),
                "reason_codes": list(governor_boundary_reason_codes),
            },
            "local_policy_decision": {
                "boundary_state": local_boundary_state or None,
                "reason_codes": list(local_boundary_reason_codes),
            },
            "coverage_summary": dict(getattr(self, "_etf_beta_candidate_pool_coverage_summary", {}) or {}),
        }
    )
    research_view_payload = build_etf_beta_research_view(
        {
            "requested_budget": requested_budget,
            "applied_budget": applied_budget,
            "equity_core_bucket": equity_core_bucket,
            "defense_tilt_bucket": defense_tilt_bucket,
            "cash_buffer_bucket": cash_buffer_bucket,
            "cash_weight": cash_weight,
            "defense_weight": defense_weight,
            "strategic_floor_cap": strategic_floor_cap,
            "tactical_overlay_cap": tactical_overlay_cap,
            "limited_defense_cap": limited_defense_cap,
            "deployment_pace": deployment_pace,
            "bull_partial_overlay_pace_ratio": bull_partial_overlay_pace_ratio,
            "bull_pace_mode": bull_pace_mode,
            "pace_policy_gap": pace_policy_gap,
            "pace_policy_reason_code": pace_policy_reason_code,
            "pace_policy_mode": pace_policy_mode,
            "execution_path": (
                "trans_up_state_change_redeploy"
                if trans_up_redeploy_active
                else standalone_deploy_path
                if standalone_deploy_active
                else "monthly_rebalance"
                if rebalance_day
                else "hold_until_rebalance"
            ),
            "trans_up_contract_mode": trans_up_contract_mode or None,
            "trans_up_single_seat_core_recovery": bool(trans_up_single_seat_core_recovery),
            "trans_up_redeploy_active": bool(trans_up_redeploy_active),
            "trans_up_redeploy_reason_code": trans_up_redeploy_reason_code or None,
            "trans_up_redeploy_reject_reason": trans_up_redeploy_reject_reason or None,
            "trans_up_redeploy_floor_gap": float(trans_up_redeploy_floor_gap or 0.0),
            "trans_up_redeploy_edge_from_state": previous_state_5 or None,
            "hard_block_flags": list(hard_block_flags),
            "core_accumulator_symbols": list(core_accumulator_symbols),
            "tactical_satellite_symbols": list(tactical_satellite_symbols),
            "limited_defense_symbols": list(limited_defense_symbols),
            "weak_state_defense_policy_id": weak_state_defense_policy_id,
            "weak_state_defense_policy_active": bool(weak_state_defense_policy_active),
            "weak_state_defense_candidate_symbols": list(weak_state_defense_candidate_symbols),
            "weak_state_defense_allow_core_beta": bool(weak_state_defense_allow_core_beta),
            "weak_state_defense_deployability_floor_applied": bool(weak_state_defense_deployability_floor_applied),
            "weak_state_defense_unavailable_reason_codes": list(weak_state_defense_unavailable_reason_codes),
            "weak_state_inter_rebalance_defense_redeploy_active": bool(weak_state_inter_redeploy_active),
            "weak_state_inter_rebalance_defense_redeploy_reason_code": weak_state_inter_redeploy_reason_code or None,
            "weak_state_inter_rebalance_defense_redeploy_reject_reason": (
                weak_state_inter_redeploy_reject_reason or None
            ),
            "weak_state_inter_rebalance_defense_redeploy_symbols": list(weak_state_inter_redeploy_symbols),
            "weak_state_inter_rebalance_defense_current_symbols": list(weak_state_inter_redeploy_current_symbols),
            "weak_state_inter_rebalance_defense_posture_satisfied": bool(
                weak_state_inter_redeploy_posture_satisfied
            ),
            "state_edge_cash_release_active": bool(state_edge_cash_release_active),
            "state_edge_cash_release_reason_code": state_edge_cash_release_reason_code or None,
            "state_edge_cash_release_reject_reason": state_edge_cash_release_reject_reason or None,
            "state_edge_cash_release_edge_from_state": state_edge_cash_release_edge_from_state or None,
            "state_edge_cash_release_edge_to_state": state_edge_cash_release_edge_to_state or None,
            "state_edge_cash_release_release_destination": state_edge_cash_release_release_destination or None,
            "state_edge_cash_release_release_target_cash": float(state_edge_cash_release_release_target_cash or 0.0),
            "state_edge_cash_release_release_cash": float(state_edge_cash_release_release_cash or 0.0),
            "state_edge_cash_release_bounded_partial_release_ratio_cap": float(
                state_edge_cash_release_bounded_partial_release_ratio_cap or 0.0
            ),
            "state_edge_cash_release_symbols": list(state_edge_cash_release_symbols),
            "symbol_role_map": dict(symbol_role_map),
            "layering_policy": layering_policy or None,
            "controlled_accumulation_mode": controlled_accumulation_mode or None,
            "layering_band": layering_band or None,
            "layering_active": bool(layering_active),
            "layering_reason_codes": list(layering_reason_codes),
            "under_deploy_reason_codes": [
                code
                for code in list(runtime_reason_codes)
                if str(code).strip()
                in {
                    "ETF_BETA_SLOT_CAP_ZERO",
                    "ETF_BETA_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER",
                    "ETF_BETA_NO_ELIGIBLE_AFTER_SELECTION_CHAIN",
                    "ETF_BETA_UNDERFILLED_DEPLOYMENT",
                    "ETF_BETA_MIN_DEPLOYABLE_EXPOSURE_UNMET",
                    "ETF_BETA_FALLBACK_PARTIAL_FILL_ACTIVE",
                    "ETF_BETA_FALLBACK_FULL_REPLACEMENT_ACTIVE",
                    "ETF_BETA_CORE_SLOT_SUPPRESSED_BY_SLOT_CAP",
                    "ETF_BETA_GROWTH_SLOT_SUPPRESSED_BY_SLOT_CAP",
                    "ETF_BETA_CORE_SLOT_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER",
                    "ETF_BETA_GROWTH_SLOT_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER",
                    "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_HARD_BLOCK",
                    "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_FLOOR_ALREADY_SATISFIED",
                    "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_NOT_STATE_CHANGE_EDGE",
                    "ETF_BETA_TRANS_UP_REDEPLOY_REJECT_NO_CORE_SELECTION",
                    "ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_REJECT_HARD_BLOCK",
                    "ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_REJECT_FULLY_DEPLOYED",
                    "ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_REJECT_NO_SELECTION",
                    "ETF_BETA_RISK_OFF_CORE_ACCUMULATION_REJECT_HARD_BLOCK",
                    "ETF_BETA_RISK_OFF_CORE_ACCUMULATION_REJECT_FULLY_DEPLOYED",
                    "ETF_BETA_RISK_OFF_CORE_ACCUMULATION_REJECT_NO_CORE_SELECTION",
                    "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_HARD_BLOCK",
                    "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_TARGET_SATISFIED",
                    "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_NO_SELECTION",
                    "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_CASH_TOO_SMALL",
                    "ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_EXECUTION_CONSTRAINT",
                    "ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_HARD_BLOCK",
                    "ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_ALREADY_DEFENSIVE",
                    "ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_NO_DEFENSE_SELECTION",
                    "ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_EXECUTION_CONSTRAINT",
                    "ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_LIQUID_RELEASE",
                    "ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_RELEASE_REQUIRED",
                }
            ],
            "runtime_reason_codes": list(runtime_reason_codes),
            "absolute_filter_reject_count": absolute_filter_reject_count,
            "absolute_filter_reject_reason_counts": dict(absolute_filter_reject_reason_counts),
            "candidate_pool_symbols": list(self._etf_beta_candidate_pool_symbols),
            "candidate_pool_coverage_summary": dict(self._etf_beta_candidate_pool_coverage_summary),
            "candidate_pool_reject_reason_counts": dict(self._etf_beta_candidate_pool_reject_reason_counts),
            "selection_chain_winner_counts": dict(selection_chain_winner_counts),
            "selection_chain_reject_reason_counts": dict(selection_chain_reject_reason_counts),
            "slot_selection_reason_codes": dict(slot_selection_reason_codes),
            "slot_under_deploy_reason_codes": dict(slot_under_deploy_reason_codes),
            "core_slot_target_exposure": core_slot_target_exposure,
            "growth_slot_target_exposure": growth_slot_target_exposure,
            "core_slot_target_actual_exposure": core_slot_target_actual_exposure,
            "growth_slot_target_actual_exposure": growth_slot_target_actual_exposure,
            "deployability_gap": target_deployability_gap,
            "runtime_vol_target": {
                "active": bool(vol_target_info.get("active", False)),
                "window": vol_target_info.get("window"),
                "annualized_target": vol_target_info.get("annualized_target"),
                "min_scale": vol_target_info.get("min_scale"),
                "max_scale": vol_target_info.get("max_scale"),
                "scale_by_symbol": dict(vol_target_scale_by_symbol),
                "realized_vol_by_symbol": dict(vol_target_realized_vol_by_symbol),
            },
            "runtime_selection": {
                "proxy_replacement_mode": self._etf_beta_proxy_replacement_mode,
                "formal_replacement_pairs": dict(self._etf_beta_formal_replacement_pairs),
                "core_slot_symbols": list(self._etf_beta_core_slot_symbols),
                "growth_slot_symbols": list(self._etf_beta_growth_slot_symbols),
                "core_slot_selected_symbol": core_slot_selected_symbol or None,
                "growth_slot_selected_symbol": growth_slot_selected_symbol or None,
                "selected_cap": int(selected_cap),
                "max_selected_symbols": configured_max_selected,
                "absolute_filter_profile": self._etf_beta_absolute_filter_profile,
                "candidate_pool_profile": self._etf_beta_candidate_pool_profile,
                "selection_chain_profile": self._etf_beta_selection_chain_profile,
            },
        }
    )

    def _append_phase1_buy_signal(
        symbol: str,
        *,
        reason: str,
        reason_code: str,
        execution_path: str,
        target_exposure_per_symbol_override: float | None = None,
        extra_selection_reason_codes: list[str] | None = None,
        allow_held_topup: bool = False,
    ) -> None:
        normalized = _normalize_etf_symbol_key(symbol)
        if not normalized:
            return
        if normalized in held_symbols and not is_phase1_allocation_engine and not allow_held_topup:
            return
        col_idx = self._sym_to_col.get(normalized)
        if col_idx is None:
            return
        close_now = float(self._mx.close[day_idx, col_idx])
        ma120_now = float(self._feats.trend_fast_ma[day_idx, col_idx])
        if close_now != close_now or (not is_phase1_allocation_engine and ma120_now != ma120_now):
            return
        raw_score = (
            float(len(selected_symbols) - selected_symbols.index(symbol))
            if symbol in selected_symbols
            else 1.0
        )
        order_value_scale = float(vol_target_scale_by_symbol.get(symbol.upper(), 1.0))
        selection_codes = list(selection_reason_codes.get(symbol) or [])
        if extra_selection_reason_codes:
            selection_codes.extend([str(code).strip() for code in list(extra_selection_reason_codes) if str(code).strip()])
        signal_meta = {
            "alpha_id": "cn_etf_beta",
            "alpha_source": "cn_etf_beta_selector",
            "sleeve_id": "cn_etf_beta",
            "raw_score": raw_score,
            "compose_score": raw_score,
            "close": close_now,
            "ma120": ma120_now,
            "symbol_role": symbol_role_map.get(_display_etf_symbol(symbol).upper()),
            "strategy_role": strategy_role or None,
            "governor_boundary_mode": governor_boundary_mode or None,
            "local_policy_mode": local_policy_mode or None,
            "boundary_policy_mode": boundary_policy_mode or None,
            "target_exposure": target_exposure,
            "target_exposure_source": target_exposure_source or None,
            "min_deployable_exposure": min_deployable_exposure,
            "min_deployable_exposure_source": min_deployable_exposure_source or None,
            "target_selected_count": int(target_selected_count),
            "target_selected_count_source": target_selected_count_source or None,
            "selection_reason_codes": selection_codes,
            "rebalance_day": rebalance_day,
            "state_5": state_5,
            "execution_path": execution_path,
        }
        is_fallback_buy = (
            reason_code != "ETF_BETA_TRANS_UP_REDEPLOY"
            and "ETF_BETA_FALLBACK_SINGLE_SYMBOL" in signal_meta["selection_reason_codes"]
        )
        effective_reason = "ETF_BETA_FALLBACK_BUY" if is_fallback_buy else reason
        effective_reason_code = "ETF_BETA_FALLBACK_BUY" if is_fallback_buy else reason_code
        signal_meta["owner_system"] = "cn_etf_beta"
        original_symbol_target_weight = _safe_float(target_exposure_by_symbol.get(symbol.upper()))
        fallback_full_replacement_active = bool(
            is_fallback_buy
            and original_symbol_target_weight in (None, 0.0)
            and "ETF_BETA_FALLBACK_FULL_REPLACEMENT_ACTIVE" in runtime_reason_codes
        )
        desired_final_target_weight = (
            float(max(float(target_exposure or 0.0), 0.0))
            if fallback_full_replacement_active
            else float(target_exposure_by_symbol.get(symbol.upper(), target_exposure_per_symbol) or 0.0)
        )
        requested_target_weight = (
            float(max(float(target_exposure or 0.0), 0.0))
            if fallback_full_replacement_active and target_exposure_per_symbol_override is None
            else float(
                (
                    target_exposure_by_symbol.get(symbol.upper(), target_exposure_per_symbol)
                    if target_exposure_per_symbol_override is None
                    else float(target_exposure_per_symbol_override)
                )
                or 0.0
            )
        )
        final_target_weight = (
            float(desired_final_target_weight)
            * float(order_value_scale or 1.0)
        )
        target_weight = (
            float(requested_target_weight)
            * float(order_value_scale or 1.0)
        )
        signal_meta["final_target_weight"] = float(max(final_target_weight, 0.0))
        signal_meta["target_weight"] = float(max(target_weight, 0.0))
        signal_meta["target_weight_basis"] = (
            "delta_deploy_gap"
            if target_exposure_per_symbol_override is not None
            else "final_target"
        )
        signal_meta["formal_reason_codes"] = [
            code
            for code in [
                str(effective_reason_code or "").strip(),
                f"STATE_{state_5}" if str(state_5 or "").strip() else "",
                str(signal_meta.get("symbol_role") or "").strip().upper(),
            ]
            if code
        ]
        buy_signals.append(
            Signal(
                signal_date=day,
                symbol=normalized,
                side=Side.BUY,
                qty=1,
                reason=effective_reason,
                reason_code=effective_reason_code,
                meta=signal_meta,
            )
        )
        strength_map[normalized] = raw_score
        mf_score_map[normalized] = raw_score
        self.diag_reason_counts[effective_reason_code] = int(self.diag_reason_counts.get(effective_reason_code, 0)) + 1

    sell_signals: list[Signal] = []
    buy_signals: list[Signal] = []
    exit_counts = ExitCounts()
    account_transition_handoff_active = False
    account_transition_handoff_consumed = False
    account_transition_handoff_reason_code = ""
    account_transition_handoff_reject_reason = ""
    account_transition_handoff_reference_paths = [
        "state_edge_cash_release",
        "riskoff_cash_drip_topup",
        "riskoff_account_budget_materialization",
        "weak_state_inter_rebalance_defense_redeploy",
    ]
    account_transition_execution_owner = "shared_account_execution_runtime"
    account_transition_execution_status = "reference_only"
    account_transition_execution_reason_code = (
        "ETF_BETA_ACCOUNT_LAYER_TRANSITION_EXECUTION_DIAGNOSTICS_ONLY"
    )
    account_transition_execution_reject_reason = ""
    shared_transition_execution_enabled = bool(
        getattr(self, "_etf_beta_shared_transition_execution_enabled", False)
    )
    shared_transition_execution_owner = str(
        getattr(self, "_etf_beta_shared_transition_execution_owner", "") or "shared_account_execution_runtime"
    ).strip() or "shared_account_execution_runtime"
    shared_transition_reference_paths = [
        str(item).strip()
        for item in list(getattr(self, "_etf_beta_shared_transition_reference_paths", []) or [])
        if str(item).strip()
    ]
    if shared_transition_reference_paths:
        account_transition_handoff_reference_paths = list(shared_transition_reference_paths)
    shared_risk_on_to_defensive_enabled = bool(
        getattr(self, "_etf_beta_shared_transition_risk_on_to_defensive_enabled", False)
    )
    shared_transition_release_ratio_cap = max(
        min(float(getattr(self, "_etf_beta_shared_transition_release_ratio_cap", 0.2) or 0.2), 1.0),
        0.0,
    )
    shared_transition_min_defense_lots = max(
        int(getattr(self, "_etf_beta_shared_transition_min_defense_lots", 1) or 1),
        1,
    )
    shared_transition_defense_symbol = _normalize_etf_symbol_key(
        getattr(self, "_etf_beta_shared_transition_defense_symbol", "") or "511010.SH"
    )
    shared_transition_core_beta_symbol = _normalize_etf_symbol_key(
        getattr(self, "_etf_beta_shared_transition_core_beta_symbol", "") or "510300.SH"
    )
    shared_transition_defense_establish_enabled = bool(
        getattr(self, "_etf_beta_shared_transition_defense_establish_enabled", False)
    )
    shared_transition_defense_establish_mode = str(
        getattr(self, "_etf_beta_shared_transition_defense_establish_mode", "")
        or "buy_after_sell_same_edge"
    ).strip() or "buy_after_sell_same_edge"
    shared_transition_defense_establish_variant_id = str(
        getattr(self, "_etf_beta_shared_transition_defense_establish_variant_id", "")
        or "all_defensive"
    ).strip() or "all_defensive"
    shared_transition_defense_establish_edge_to_states = {
        canonical_state_5(str(item).strip())
        for item in list(
            getattr(self, "_etf_beta_shared_transition_defense_establish_edge_to_states", set()) or set()
        )
        if canonical_state_5(str(item).strip())
    }
    shared_transition_defense_establish_top_up_existing_defense = bool(
        getattr(self, "_etf_beta_shared_transition_defense_establish_top_up_existing_defense", True)
    )
    shared_transition_edge_from_state = canonical_state_5(str(state_edge_cash_release_edge_from_state or "").strip())
    shared_transition_edge_to_state = canonical_state_5(str(state_edge_cash_release_edge_to_state or state_5).strip())
    shared_transition_active = False
    shared_transition_reason_code = ""
    shared_transition_reject_reason = ""
    shared_transition_release_destination = "defense_first"
    shared_transition_release_target_cash = 0.0
    shared_transition_release_cash = 0.0
    shared_transition_release_plan: dict[str, int] = {}
    shared_transition_release_symbols: list[str] = []
    shared_transition_defense_establish_active = False
    shared_transition_defense_establish_reason_code = ""
    shared_transition_defense_establish_symbol = shared_transition_defense_symbol
    shared_transition_defense_establish_target_weight = 0.0
    shared_transition_defense_establish_cash = 0.0
    shared_transition_defense_establish_skipped_by_variant = False
    shared_transition_defense_establish_skipped_existing_hold = False
    if (
        shared_transition_execution_enabled
        and shared_risk_on_to_defensive_enabled
        and shared_transition_edge_from_state in _RISK_ON_TRANSITION_STATES
        and shared_transition_edge_to_state in _DEFENSIVE_TRANSITION_STATES
    ):
        account_transition_handoff_active = True
        current_cash = float(getattr(ctx, "cash", 0.0) or 0.0)
        defense_price = _resolve_ctx_symbol_price(
            ctx=ctx,
            day=day,
            normalized_symbol=shared_transition_defense_symbol,
        )
        if defense_price is None or defense_price <= 0.0:
            shared_transition_reject_reason = (
                "ETF_BETA_SHARED_ACCOUNT_TRANSITION_RISK_ON_TO_DEFENSIVE_REJECT_NO_DEFENSE_PRICE"
            )
        else:
            nav_value = max(float(getattr(ctx, "nav", 0.0) or 0.0), 0.0)
            minimum_defense_cash = float(defense_price) * 100.0 * float(shared_transition_min_defense_lots)
            desired_defense_floor = max(
                float(limited_defense_cap or 0.0),
                float(dict(target_exposure_by_symbol or {}).get(shared_transition_defense_symbol.upper(), 0.0) or 0.0),
            )
            defense_floor_gap = max(float(desired_defense_floor) - float(current_defense_exposure or 0.0), 0.0)
            shared_transition_release_target_cash = max(float(defense_floor_gap) * float(nav_value), minimum_defense_cash)
            (
                shared_transition_release_plan,
                shared_transition_release_cash,
                shared_transition_release_symbols,
            ) = _build_shared_risk_on_to_defensive_release_plan(
                ctx=ctx,
                day=day,
                day_idx=day_idx,
                held_qty_by_symbol=held_qty_by_symbol,
                sym_to_col=self._sym_to_col,
                close_matrix=self._mx.close,
                current_cash=current_cash,
                release_target_cash=shared_transition_release_target_cash,
                release_ratio_cap=shared_transition_release_ratio_cap,
                defense_symbol=shared_transition_defense_symbol,
                core_beta_symbol=shared_transition_core_beta_symbol,
            )
            if current_cash + shared_transition_release_cash >= shared_transition_release_target_cash:
                shared_transition_active = True
                shared_transition_reason_code = (
                    "ETF_BETA_SHARED_ACCOUNT_TRANSITION_RISK_ON_TO_DEFENSIVE_ACTIVE"
                )
                account_transition_handoff_consumed = True
                account_transition_handoff_reason_code = shared_transition_reason_code
                account_transition_execution_owner = shared_transition_execution_owner
                account_transition_execution_status = "active"
                account_transition_execution_reason_code = shared_transition_reason_code
                state_edge_cash_release_active = False
                riskoff_account_budget_materialization_active = False
                weak_state_inter_redeploy_active = False
                standalone_deploy_active = False
                standalone_deploy_reason_code = ""
                standalone_deploy_reject_reason = ""
                standalone_deploy_symbols = []
                standalone_deploy_path = ""
                available_defense_cash = max(float(current_cash) + float(shared_transition_release_cash or 0.0), 0.0)
                shared_transition_defense_establish_cash = min(
                    available_defense_cash,
                    max(float(shared_transition_release_target_cash or 0.0), minimum_defense_cash),
                )
                edge_allowed = (
                    not shared_transition_defense_establish_edge_to_states
                    or shared_transition_edge_to_state in shared_transition_defense_establish_edge_to_states
                )
                top_up_allowed = (
                    shared_transition_defense_establish_top_up_existing_defense
                    or shared_transition_defense_symbol not in held_symbols
                )
                if nav_value > 0.0 and shared_transition_defense_establish_cash > 0.0 and edge_allowed and top_up_allowed:
                    shared_transition_defense_establish_active = True
                    shared_transition_defense_establish_reason_code = (
                        "ETF_BETA_SHARED_ACCOUNT_TRANSITION_RISK_ON_TO_DEFENSIVE_DEFENSE_ESTABLISH_ACTIVE"
                    )
                    shared_transition_defense_establish_target_weight = (
                        float(shared_transition_defense_establish_cash) / float(nav_value)
                    )
                elif not edge_allowed:
                    shared_transition_defense_establish_skipped_by_variant = True
                elif not top_up_allowed:
                    shared_transition_defense_establish_skipped_existing_hold = True
            else:
                shared_transition_reject_reason = (
                    "ETF_BETA_SHARED_ACCOUNT_TRANSITION_RISK_ON_TO_DEFENSIVE_REJECT_NO_LIQUID_RELEASE"
                )
        if shared_transition_reject_reason:
            account_transition_handoff_consumed = False
            account_transition_handoff_reject_reason = shared_transition_reject_reason
            account_transition_execution_owner = shared_transition_execution_owner
            account_transition_execution_status = "rejected"
            account_transition_execution_reason_code = ""
            account_transition_execution_reject_reason = shared_transition_reject_reason
            state_edge_cash_release_active = False
            riskoff_account_budget_materialization_active = False
            weak_state_inter_redeploy_active = False
            standalone_deploy_active = False
            standalone_deploy_reason_code = ""
            standalone_deploy_symbols = []
            standalone_deploy_path = ""

    if shared_transition_active and shared_transition_release_plan:
        for symbol, qty in sorted(shared_transition_release_plan.items()):
            sell_signals.append(
                Signal(
                    signal_date=day,
                    symbol=str(symbol).strip().upper(),
                    side=Side.SELL,
                    qty=int(qty),
                    reason="ETF_BETA_SHARED_ACCOUNT_TRANSITION_EXECUTION",
                    reason_code=shared_transition_reason_code,
                    meta={
                        "alpha_id": "cn_etf_beta",
                        "alpha_source": "cn_etf_beta_selector",
                        "sleeve_id": "cn_etf_beta",
                        "state_5": state_5,
                        "previous_state_5": shared_transition_edge_from_state or None,
                        "strategy_role": strategy_role,
                        "execution_path": "shared_risk_on_to_defensive_transition",
                        "target_weight_basis": "delta_deploy_gap",
                        "release_destination": shared_transition_release_destination,
                        "release_cash_target": float(shared_transition_release_target_cash or 0.0),
                        "release_cash_proceeds": float(shared_transition_release_cash or 0.0),
                        "release_symbols": list(shared_transition_release_symbols),
                    },
                )
            )
    if shared_transition_defense_establish_active and shared_transition_defense_establish_target_weight > 1e-12:
        runtime_reason_codes.append(shared_transition_defense_establish_reason_code)
        buy_signal_meta = {
            "alpha_id": "cn_etf_beta",
            "alpha_source": "cn_etf_beta_selector",
            "sleeve_id": "cn_etf_beta",
            "raw_score": 1.0,
            "compose_score": 1.0,
            "close": float(defense_price or 0.0),
            "ma120": float(defense_price or 0.0),
            "symbol_role": "defense",
            "strategy_role": strategy_role or None,
            "governor_boundary_mode": governor_boundary_mode or None,
            "local_policy_mode": local_policy_mode or None,
            "boundary_policy_mode": boundary_policy_mode or None,
            "target_exposure": target_exposure,
            "target_exposure_source": target_exposure_source or None,
            "min_deployable_exposure": min_deployable_exposure,
            "min_deployable_exposure_source": min_deployable_exposure_source or None,
            "target_selected_count": int(target_selected_count),
            "target_selected_count_source": target_selected_count_source or None,
            "selection_reason_codes": [
                shared_transition_reason_code,
                shared_transition_defense_establish_reason_code,
                f"EDGE_FROM::{shared_transition_edge_from_state}",
                f"EDGE_TO::{shared_transition_edge_to_state}",
                f"VARIANT::{shared_transition_defense_establish_variant_id.upper()}",
                "DEFENSE_ESTABLISH",
            ],
            "rebalance_day": rebalance_day,
            "state_5": state_5,
            "execution_path": "shared_risk_on_to_defensive_transition_defense_establish",
            "owner_system": "cn_etf_beta",
            "final_target_weight": float(max(shared_transition_defense_establish_target_weight, 0.0)),
            "target_weight": float(max(shared_transition_defense_establish_target_weight, 0.0)),
            "target_weight_basis": "delta_deploy_gap",
            "formal_reason_codes": [
                shared_transition_reason_code,
                shared_transition_defense_establish_reason_code,
                f"STATE_{state_5}" if str(state_5 or "").strip() else "",
                f"EDGE_FROM::{shared_transition_edge_from_state}",
                f"EDGE_TO::{shared_transition_edge_to_state}",
                f"VARIANT::{shared_transition_defense_establish_variant_id.upper()}",
                "DEFENSE_ESTABLISH",
            ],
            "release_destination": shared_transition_release_destination,
            "release_cash_target": float(shared_transition_release_target_cash or 0.0),
            "release_cash_proceeds": float(shared_transition_release_cash or 0.0),
            "release_symbols": list(shared_transition_release_symbols),
            "defense_establish_cash": float(shared_transition_defense_establish_cash or 0.0),
            "allow_held_topup": bool(shared_transition_defense_establish_top_up_existing_defense),
            "defense_establish_variant_id": shared_transition_defense_establish_variant_id,
        }
        buy_signals.append(
            Signal(
                signal_date=day,
                symbol=shared_transition_defense_establish_symbol,
                side=Side.BUY,
                qty=1,
                reason="ETF_BETA_SHARED_ACCOUNT_TRANSITION_DEFENSE_ESTABLISH",
                reason_code=shared_transition_defense_establish_reason_code,
                meta=buy_signal_meta,
            )
        )
    elif shared_transition_defense_establish_skipped_by_variant:
        runtime_reason_codes.append(
            "ETF_BETA_SHARED_ACCOUNT_TRANSITION_RISK_ON_TO_DEFENSIVE_DEFENSE_ESTABLISH_SKIPPED_BY_VARIANT"
        )
    elif shared_transition_defense_establish_skipped_existing_hold:
        runtime_reason_codes.append(
            "ETF_BETA_SHARED_ACCOUNT_TRANSITION_RISK_ON_TO_DEFENSIVE_DEFENSE_ESTABLISH_SKIPPED_EXISTING_HOLD"
        )
    elif riskoff_account_budget_materialization_active and riskoff_account_budget_materialization_plan:
        for symbol, qty in sorted(riskoff_account_budget_materialization_plan.items()):
            sell_signals.append(
                Signal(
                    signal_date=day,
                    symbol=str(symbol).strip().upper(),
                    side=Side.SELL,
                    qty=int(qty),
                    reason="ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION",
                    reason_code="ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_ACTIVE",
                    meta={
                        "alpha_id": "cn_etf_beta",
                        "alpha_source": "cn_etf_beta_selector",
                        "sleeve_id": "cn_etf_beta",
                        "state_5": state_5,
                        "release_destination": riskoff_account_budget_materialization_release_destination or None,
                        "release_cash_target": float(riskoff_account_budget_materialization_release_target_cash or 0.0),
                        "release_cash_proceeds": float(riskoff_account_budget_materialization_release_cash or 0.0),
                        "release_symbols": list(riskoff_account_budget_materialization_symbols),
                        "target_symbols": list(riskoff_account_budget_materialization_target_symbols),
                        "runtime_reason_codes": list(runtime_reason_codes),
                    },
                )
            )
        runtime_reason_codes.append("ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_ACTIVE")
        if riskoff_account_budget_materialization_release_destination:
            runtime_reason_codes.append(
                f"ETF_BETA_RISK_OFF_ACCOUNT_BUDGET_MATERIALIZATION_DESTINATION::{riskoff_account_budget_materialization_release_destination}"
            )
    elif state_edge_cash_release_active and state_edge_cash_release_plan:
        active_signal_reason = (
            "ETF_BETA_ACCOUNT_LAYER_TRANSITION_EXECUTION"
            if account_transition_handoff_active
            else "ETF_BETA_STATE_EDGE_CASH_RELEASE"
        )
        active_signal_reason_code = (
            account_transition_execution_reason_code
            if account_transition_handoff_active
            else "ETF_BETA_STATE_EDGE_CASH_RELEASE_ACTIVE"
        )
        for symbol, qty in sorted(state_edge_cash_release_plan.items()):
            sell_signals.append(
                Signal(
                    signal_date=day,
                    symbol=str(symbol).strip().upper(),
                    side=Side.SELL,
                    qty=int(qty),
                    reason=active_signal_reason,
                    reason_code=active_signal_reason_code,
                    meta={
                        "alpha_id": "cn_etf_beta",
                        "alpha_source": "cn_etf_beta_selector",
                        "sleeve_id": "cn_etf_beta",
                        "state_5": state_5,
                        "previous_state_5": state_edge_cash_release_edge_from_state,
                        "release_destination": state_edge_cash_release_release_destination or None,
                        "release_cash_target": float(state_edge_cash_release_release_target_cash or 0.0),
                        "release_cash_proceeds": float(state_edge_cash_release_release_cash or 0.0),
                        "release_symbols": list(state_edge_cash_release_plan.keys()),
                        "runtime_reason_codes": list(runtime_reason_codes),
                    },
                )
            )
        runtime_reason_codes.append(active_signal_reason_code)
        if account_transition_handoff_active:
            runtime_reason_codes.append("ETF_BETA_ACCOUNT_LAYER_TRANSITION_EXECUTION_OWNER::account_layer_transition_contract")
            if state_edge_cash_release_edge_from_state:
                runtime_reason_codes.append(
                    f"ETF_BETA_ACCOUNT_LAYER_TRANSITION_EXECUTION_EDGE_FROM::{state_edge_cash_release_edge_from_state}"
                )
            if state_edge_cash_release_edge_to_state:
                runtime_reason_codes.append(
                    f"ETF_BETA_ACCOUNT_LAYER_TRANSITION_EXECUTION_EDGE_TO::{state_edge_cash_release_edge_to_state}"
                )
            if state_edge_cash_release_release_destination:
                runtime_reason_codes.append(
                    f"ETF_BETA_ACCOUNT_LAYER_TRANSITION_EXECUTION_DESTINATION::{state_edge_cash_release_release_destination}"
                )
            if state_edge_cash_release_release_cash > 0:
                runtime_reason_codes.append("ETF_BETA_ACCOUNT_LAYER_TRANSITION_EXECUTION_PARTIAL_RELEASE_ACTIVE")
        else:
            if state_edge_cash_release_edge_from_state:
                runtime_reason_codes.append(f"ETF_BETA_STATE_EDGE_CASH_RELEASE_EDGE_FROM::{state_edge_cash_release_edge_from_state}")
            if state_edge_cash_release_edge_to_state:
                runtime_reason_codes.append(f"ETF_BETA_STATE_EDGE_CASH_RELEASE_EDGE_TO::{state_edge_cash_release_edge_to_state}")
            if state_edge_cash_release_release_destination:
                runtime_reason_codes.append(
                    f"ETF_BETA_STATE_EDGE_CASH_RELEASE_DESTINATION::{state_edge_cash_release_release_destination}"
                )
            if state_edge_cash_release_release_cash > 0:
                runtime_reason_codes.append("ETF_BETA_STATE_EDGE_CASH_RELEASE_PARTIAL_RELEASE_ACTIVE")

    if slot_cap <= 0:
        for symbol in sorted(held_symbols):
            sell_signals.append(
                Signal(
                    signal_date=day,
                    symbol=symbol,
                    side=Side.SELL,
                    qty=0,
                    reason="ETF_BETA_STATE_EXIT",
                    reason_code="ETF_BETA_STATE_EXIT",
                    meta={
                        "alpha_id": "cn_etf_beta",
                        "alpha_source": "cn_etf_beta_selector",
                        "sleeve_id": "cn_etf_beta",
                        "state_5": state_5,
                        "selection_reason_codes": [],
                        "runtime_reason_codes": list(runtime_reason_codes),
                    },
                )
            )
            self.diag_reason_counts["ETF_BETA_STATE_EXIT"] = int(self.diag_reason_counts.get("ETF_BETA_STATE_EXIT", 0)) + 1
    elif rebalance_day:
        symbols_to_exit = sorted(held_symbols) if is_phase1_allocation_engine else sorted(held_symbols - selected_lower)
        for symbol in symbols_to_exit:
            sell_signals.append(
                Signal(
                    signal_date=day,
                    symbol=symbol,
                    side=Side.SELL,
                    qty=0,
                    reason="ETF_BETA_PHASE1_REBALANCE_RESET" if is_phase1_allocation_engine else "ETF_BETA_REBALANCE_EXIT",
                    reason_code="ETF_BETA_PHASE1_REBALANCE_RESET" if is_phase1_allocation_engine else "ETF_BETA_REBALANCE_EXIT",
                    meta={
                        "alpha_id": "cn_etf_beta",
                        "alpha_source": "cn_etf_beta_selector",
                        "sleeve_id": "cn_etf_beta",
                        "state_5": state_5,
                        "selection_reason_codes": [],
                        "runtime_reason_codes": list(runtime_reason_codes),
                    },
                )
            )
            reason_counter_key = "ETF_BETA_PHASE1_REBALANCE_RESET" if is_phase1_allocation_engine else "ETF_BETA_REBALANCE_EXIT"
            self.diag_reason_counts[reason_counter_key] = int(self.diag_reason_counts.get(reason_counter_key, 0)) + 1
        for symbol in selected_symbols:
            _append_phase1_buy_signal(
                symbol,
                reason=entry_reason_code,
                reason_code=entry_reason_code,
                execution_path="monthly_rebalance",
            )
    elif trans_up_redeploy_active:
        for symbol in trans_up_redeploy_core_symbols:
            _append_phase1_buy_signal(
                symbol,
                reason="ETF_BETA_TRANS_UP_REDEPLOY",
                reason_code="ETF_BETA_TRANS_UP_REDEPLOY",
                execution_path="trans_up_state_change_redeploy",
                target_exposure_per_symbol_override=trans_up_redeploy_target_per_symbol,
                extra_selection_reason_codes=[
                    trans_up_redeploy_reason_code,
                    f"EDGE_FROM::{previous_state_5}",
                    "CORE_ONLY_REDEPLOY",
                ],
            )
    elif standalone_deploy_active:
        for symbol in standalone_deploy_symbols:
            _append_phase1_buy_signal(
                symbol,
                reason=standalone_deploy_reason_code,
                reason_code=standalone_deploy_reason_code,
                execution_path=standalone_deploy_path,
                target_exposure_per_symbol_override=standalone_deploy_target_weight_by_symbol.get(symbol, 0.0),
                extra_selection_reason_codes=[
                    standalone_deploy_reason_code,
                    f"INTER_REBALANCE_STATE::{str(state_5 or '').upper()}",
                ],
                allow_held_topup=True,
            )
    local_policy_reason_codes = list(runtime_reason_codes)
    if controlled_accumulation_mode != "none":
        local_policy_reason_codes.append(f"ETF_BETA_CONTROLLED_ACCUMULATION_MODE::{controlled_accumulation_mode.upper()}")

    diagnostics = {
        "composition_enabled": False,
        "market_state": state_5,
        "trade_mode": trade_mode,
        "raw_alpha_signal_count": int(len(buy_signals)),
        "buy_candidate_count": int(len(eligible_symbols)),
        "after_held_filter_count": int(len([symbol for symbol in selected_symbols if symbol.lower() not in held_symbols])),
        "etf_beta_rebalance_day": bool(rebalance_day),
        "etf_beta_deployable_slot_cap": int(slot_cap),
        "etf_beta_formal_scope_symbols": list(self._etf_beta_formal_scope_symbols),
        "etf_beta_eligible_symbols": list(eligible_symbols),
        "etf_beta_selected_symbols": list(selected_symbols),
        "etf_beta_selection_reason_codes": selection_reason_codes,
        "etf_beta_runtime_reason_codes": list(runtime_reason_codes),
        "etf_beta_execution_path": (
            "trans_up_state_change_redeploy"
            if trans_up_redeploy_active
            else standalone_deploy_path
            if standalone_deploy_active
            else "monthly_rebalance"
            if rebalance_day
            else "hold_until_rebalance"
        ),
        "etf_beta_trans_up_redeploy_active": bool(trans_up_redeploy_active),
        "etf_beta_trans_up_redeploy_reason_code": trans_up_redeploy_reason_code or None,
        "etf_beta_trans_up_redeploy_reject_reason": trans_up_redeploy_reject_reason or None,
        "etf_beta_trans_up_redeploy_floor_gap": float(trans_up_redeploy_floor_gap or 0.0),
        "etf_beta_trans_up_redeploy_edge_from_state": previous_state_5 or None,
        "etf_beta_trans_up_redeploy_core_exposure_before": float(current_core_exposure or 0.0),
        "etf_beta_trans_up_redeploy_core_symbols": list(trans_up_redeploy_core_symbols),
        "etf_beta_weak_state_inter_rebalance_defense_redeploy_active": bool(weak_state_inter_redeploy_active),
        "etf_beta_weak_state_inter_rebalance_defense_redeploy_reason_code": (
            weak_state_inter_redeploy_reason_code or None
        ),
        "etf_beta_weak_state_inter_rebalance_defense_redeploy_reject_reason": (
            weak_state_inter_redeploy_reject_reason or None
        ),
        "etf_beta_weak_state_inter_rebalance_defense_redeploy_symbols": list(weak_state_inter_redeploy_symbols),
        "etf_beta_weak_state_inter_rebalance_defense_current_symbols": list(
            weak_state_inter_redeploy_current_symbols
        ),
        "etf_beta_weak_state_inter_rebalance_defense_posture_satisfied": bool(
            weak_state_inter_redeploy_posture_satisfied
        ),
        "etf_beta_state_edge_cash_release_active": bool(state_edge_cash_release_active),
        "etf_beta_state_edge_cash_release_reason_code": state_edge_cash_release_reason_code or None,
        "etf_beta_state_edge_cash_release_reject_reason": state_edge_cash_release_reject_reason or None,
        "etf_beta_state_edge_cash_release_edge_from_state": state_edge_cash_release_edge_from_state or None,
        "etf_beta_state_edge_cash_release_edge_to_state": state_edge_cash_release_edge_to_state or None,
        "etf_beta_state_edge_cash_release_release_destination": state_edge_cash_release_release_destination or None,
        "etf_beta_riskoff_account_budget_materialization_active": bool(
            riskoff_account_budget_materialization_active
        ),
        "etf_beta_riskoff_account_budget_materialization_reason_code": (
            riskoff_account_budget_materialization_reason_code or None
        ),
        "etf_beta_riskoff_account_budget_materialization_reject_reason": (
            riskoff_account_budget_materialization_reject_reason or None
        ),
        "etf_beta_riskoff_account_budget_materialization_release_destination": (
            riskoff_account_budget_materialization_release_destination or None
        ),
        "etf_beta_riskoff_account_budget_materialization_release_target_cash": float(
            riskoff_account_budget_materialization_release_target_cash or 0.0
        ),
        "etf_beta_riskoff_account_budget_materialization_release_cash": float(
            riskoff_account_budget_materialization_release_cash or 0.0
        ),
        "etf_beta_riskoff_account_budget_materialization_symbols": list(
            riskoff_account_budget_materialization_symbols
        ),
        "etf_beta_riskoff_account_budget_materialization_target_symbols": list(
            riskoff_account_budget_materialization_target_symbols
        ),
        "etf_beta_riskoff_account_budget_materialization_bounded_partial_release_ratio_cap": float(
            riskoff_account_budget_materialization_bounded_partial_release_ratio_cap or 0.0
        ),
        "etf_beta_state_edge_cash_release_release_target_cash": float(state_edge_cash_release_release_target_cash or 0.0),
        "etf_beta_state_edge_cash_release_release_cash": float(state_edge_cash_release_release_cash or 0.0),
        "etf_beta_state_edge_cash_release_bounded_partial_release_ratio_cap": float(
            state_edge_cash_release_bounded_partial_release_ratio_cap or 0.0
        ),
        "etf_beta_state_edge_cash_release_symbols": list(state_edge_cash_release_symbols),
        "etf_beta_account_transition_handoff_active": bool(account_transition_handoff_active),
        "etf_beta_account_transition_handoff_transition_kind": (
            "risk_on_to_defensive" if account_transition_handoff_active else ""
        ),
        "etf_beta_account_transition_handoff_consumed": bool(account_transition_handoff_consumed),
        "etf_beta_account_transition_handoff_reason_code": (
            account_transition_handoff_reason_code or None
        ),
        "etf_beta_account_transition_handoff_reject_reason": (
            account_transition_handoff_reject_reason or None
        ),
        "etf_beta_account_transition_handoff_edge_from_state": (
            state_edge_cash_release_edge_from_state or None
        ),
        "etf_beta_account_transition_handoff_edge_to_state": (
            state_edge_cash_release_edge_to_state or None
        ),
        "etf_beta_account_transition_handoff_release_destination": (
            state_edge_cash_release_release_destination or None
        ),
        "etf_beta_account_transition_handoff_reference_paths": list(
            account_transition_handoff_reference_paths
        ),
        "etf_beta_account_transition_execution_owner": account_transition_execution_owner,
        "etf_beta_account_transition_execution_status": account_transition_execution_status,
        "etf_beta_account_transition_execution_reason_code": (
            account_transition_execution_reason_code or None
        ),
        "etf_beta_account_transition_execution_reject_reason": (
            account_transition_execution_reject_reason or None
        ),
        "etf_beta_shared_transition_defense_establish_active": bool(
            shared_transition_defense_establish_active
        ),
        "etf_beta_shared_transition_defense_establish_reason_code": (
            shared_transition_defense_establish_reason_code or None
        ),
        "etf_beta_shared_transition_defense_establish_variant_id": (
            shared_transition_defense_establish_variant_id or None
        ),
        "etf_beta_shared_transition_defense_establish_edge_to_states": sorted(
            shared_transition_defense_establish_edge_to_states
        ),
        "etf_beta_shared_transition_defense_establish_top_up_existing_defense": bool(
            shared_transition_defense_establish_top_up_existing_defense
        ),
        "etf_beta_shared_transition_defense_establish_symbol": (
            shared_transition_defense_establish_symbol or None
        ),
        "etf_beta_shared_transition_defense_establish_cash": float(
            shared_transition_defense_establish_cash or 0.0
        ),
        "etf_beta_shared_transition_defense_establish_target_weight": float(
            shared_transition_defense_establish_target_weight or 0.0
        ),
        "etf_beta_shared_transition_defense_establish_skipped_by_variant": bool(
            shared_transition_defense_establish_skipped_by_variant
        ),
        "etf_beta_shared_transition_defense_establish_skipped_existing_hold": bool(
            shared_transition_defense_establish_skipped_existing_hold
        ),
        "etf_beta_account_transition_execution_reference_paths": list(
            account_transition_handoff_reference_paths
        ),
        "etf_beta_rule_family": self._etf_beta_rule_family,
        "etf_beta_strategy_role": strategy_role or None,
        "etf_beta_governor_boundary_mode": governor_boundary_mode or None,
        "etf_beta_local_policy_mode": local_policy_mode or None,
        "etf_beta_template_id": self._etf_beta_template_id or None,
        "etf_beta_template_asset_pool_version": self._etf_beta_template_asset_pool_version or None,
        "etf_beta_template_role_map": dict(self._etf_beta_template_role_map),
        "etf_beta_template_proxy_map": dict(self._etf_beta_template_proxy_map),
        "etf_beta_template_target_formal_symbols": list(self._etf_beta_template_target_formal_symbols),
        "etf_beta_proxy_replacement_mode": self._etf_beta_proxy_replacement_mode,
        "etf_beta_formal_replacement_pairs": dict(self._etf_beta_formal_replacement_pairs),
        "etf_beta_core_slot_symbols": list(self._etf_beta_core_slot_symbols),
        "etf_beta_growth_slot_symbols": list(self._etf_beta_growth_slot_symbols),
        "etf_beta_growth_seat_symbol": self._etf_beta_growth_seat_symbol or None,
        "etf_beta_core_slot_selected_symbol": core_slot_selected_symbol or None,
        "etf_beta_growth_slot_selected_symbol": growth_slot_selected_symbol or None,
        "etf_beta_slot_selection_reason_codes": slot_selection_reason_codes,
        "etf_beta_slot_under_deploy_reason_codes": slot_under_deploy_reason_codes,
        "etf_beta_core_slot_target_exposure": core_slot_target_exposure,
        "etf_beta_growth_slot_target_exposure": growth_slot_target_exposure,
        "etf_beta_core_slot_target_actual_exposure": core_slot_target_actual_exposure,
        "etf_beta_growth_slot_target_actual_exposure": growth_slot_target_actual_exposure,
        "etf_beta_absolute_filter_profile": self._etf_beta_absolute_filter_profile,
        "etf_beta_candidate_pool_profile": self._etf_beta_candidate_pool_profile,
        "etf_beta_selection_chain_profile": self._etf_beta_selection_chain_profile,
        "etf_beta_absolute_filter_mode": self._etf_beta_absolute_filter_mode,
        "etf_beta_absolute_filter_reject_count": absolute_filter_reject_count,
        "etf_beta_absolute_filter_reject_reason_counts": dict(absolute_filter_reject_reason_counts),
        "etf_beta_candidate_pool_symbols": list(self._etf_beta_candidate_pool_symbols),
        "etf_beta_candidate_pool_coverage_summary": dict(self._etf_beta_candidate_pool_coverage_summary),
        "etf_beta_candidate_pool_reject_reason_counts": dict(self._etf_beta_candidate_pool_reject_reason_counts),
        "etf_beta_rebalance_frequency": self._etf_beta_rebalance_frequency,
        "etf_beta_relative_strength_fast_window": self._etf_beta_rs_fast_window,
        "etf_beta_relative_strength_mid_window": self._etf_beta_rs_mid_window,
        "etf_beta_relative_strength_slow_window": self._etf_beta_rs_slow_window,
        "etf_beta_relative_strength_fast_weight": self._etf_beta_rs_fast_weight,
        "etf_beta_relative_strength_mid_weight": self._etf_beta_rs_mid_weight,
        "etf_beta_relative_strength_slow_weight": self._etf_beta_rs_slow_weight,
        "etf_beta_selection_chain_winner_counts": dict(selection_chain_winner_counts),
        "etf_beta_selection_chain_reject_reason_counts": dict(selection_chain_reject_reason_counts),
        "etf_beta_max_selected_symbols": self._etf_beta_max_selected_symbols,
        "etf_beta_selected_cap": int(selected_cap),
        "etf_beta_target_exposure": target_exposure,
        "etf_beta_target_exposure_source": target_exposure_source or None,
        "etf_beta_allocation_engine_mode": self._etf_beta_allocation_engine_mode,
        "etf_beta_bucket_policy_profile": self._etf_beta_bucket_policy_profile,
        "etf_beta_min_deployable_exposure": min_deployable_exposure,
        "etf_beta_min_deployable_exposure_source": min_deployable_exposure_source or None,
        "etf_beta_target_selected_count": int(target_selected_count),
        "etf_beta_target_selected_count_source": target_selected_count_source or None,
        "etf_beta_exposure_policy_family": exposure_policy_family or None,
        "etf_beta_policy_scope": policy_scope or None,
        "etf_beta_broad_based_only": bool(broad_based_only),
        "etf_beta_boundary_policy_mode": boundary_policy_mode or None,
        "etf_beta_governor_hard_blocked": bool(governor_hard_blocked),
        "etf_beta_governor_hard_block_reason_codes": list(governor_hard_block_reason_codes),
        "etf_beta_local_boundary_state": local_boundary_state or None,
        "etf_beta_local_boundary_reason_codes": list(local_boundary_reason_codes),
        "etf_beta_governor_boundary_reason_codes": list(governor_boundary_reason_codes),
        "etf_beta_local_policy_reason_codes": list(local_policy_reason_codes),
        "etf_beta_fallback_mode": self._etf_beta_fallback_mode,
        "etf_beta_fallback_symbol": _display_etf_symbol(self._etf_beta_fallback_symbol) if self._etf_beta_fallback_symbol else None,
        "etf_beta_fallback_allowed": bool(fallback_allowed),
        "etf_beta_fallback_allowed_source": fallback_allowed_source or None,
        "etf_beta_fallback_active": bool(fallback_active),
        "etf_beta_formal_view": dict(formal_view_payload),
        "etf_beta_research_view": dict(research_view_payload),
    }
    return DaySignals(
        sell_signals=sell_signals,
        buy_signals=buy_signals,
        raw_alpha_signals=list(buy_signals),
        composed_sell_signals=list(sell_signals),
        composed_buy_signals=list(buy_signals),
        exit_syms={str(signal.symbol).lower() for signal in sell_signals},
        strength_map=strength_map,
        mf_score_map=mf_score_map,
        mf_gate_on_today=False,
        strong_risk_on=state_5 in {"BULL", "TRANS_UP"},
        exit_counts=exit_counts,
        diagnostics=diagnostics,
    )

