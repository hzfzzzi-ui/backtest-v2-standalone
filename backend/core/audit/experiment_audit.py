from __future__ import annotations

import math
from typing import Any

_ACCOUNTING_AUDIT_CONTRACT_VERSION = "accounting_integrity_audit@1"
_MAX_ACCOUNTING_SAMPLES = 5
_CASH_TOL = 0.015
_NAV_TOL = 0.01
_NET_AMOUNT_ROUNDING_TOL = 0.005


def _unique_warnings(raw_warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in list(raw_warnings or ()):
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return float(out)


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return None


def _normalize_positions(raw: Any) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[str, int] = {}
    for key, value in dict(raw).items():
        qty = _safe_int(value)
        if qty is None:
            return None
        if qty > 0:
            out[str(key).lower().strip()] = int(qty)
    return out


def _normalize_corporate_action_deltas(raw: Any) -> dict[str, int]:
    if not isinstance(raw, list):
        return {}
    out: dict[str, int] = {}
    for item in list(raw):
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").lower().strip()
        prev_qty = _safe_int(item.get("prev_qty"))
        adjusted_qty = _safe_int(item.get("adjusted_qty"))
        if not symbol or prev_qty is None or adjusted_qty is None:
            continue
        delta = int(adjusted_qty) - int(prev_qty)
        if delta == 0:
            continue
        out[symbol] = int(out.get(symbol, 0)) + int(delta)
    return out


def _append_sample(target: list[dict[str, Any]], sample: dict[str, Any]) -> None:
    if len(target) < _MAX_ACCOUNTING_SAMPLES:
        target.append(sample)


def _accounting_scale_tolerance(expected: float, actual: float, *, floor: float) -> float:
    scale = max(abs(float(expected)), abs(float(actual)), 1.0)
    return max(float(floor), scale * 1e-8)


def _cash_tolerance(expected: float, actual: float, *, trade_count: int) -> float:
    rounding_floor = float(max(0, int(trade_count))) * _NET_AMOUNT_ROUNDING_TOL
    return _accounting_scale_tolerance(expected, actual, floor=max(_CASH_TOL, rounding_floor))


def _unknown_accounting_integrity(reason: str) -> dict[str, Any]:
    return {
        "contract_version": _ACCOUNTING_AUDIT_CONTRACT_VERSION,
        "status": "UNKNOWN",
        "reason": reason,
        "summary": {
            "trading_days": 0,
            "days_with_evidence": 0,
            "missing_evidence_days": 0,
            "cash_check_pass": 0,
            "cash_check_fail": 0,
            "receivable_check_pass": 0,
            "receivable_check_fail": 0,
            "position_check_pass": 0,
            "position_check_fail": 0,
            "nav_check_pass": 0,
            "nav_check_fail": 0,
            "invalid_nav_days": 0,
            "negative_cash_days": 0,
            "max_positions_breach_days": 0,
        },
        "samples": {
            "missing_evidence": [],
            "cash_check_fail": [],
            "receivable_check_fail": [],
            "position_check_fail": [],
            "nav_check_fail": [],
            "invalid_nav": [],
            "negative_cash": [],
            "max_positions_breach": [],
        },
        "tolerances": {
            "cash_abs": _CASH_TOL,
            "nav_abs": _NAV_TOL,
        },
    }


def build_accounting_integrity_audit(
    *,
    initial_cash: Any,
    daily_snapshots: Any,
) -> dict[str, Any]:
    cash_before = _safe_float(initial_cash)
    rows = list(daily_snapshots or ())
    if cash_before is None or not rows:
        return _unknown_accounting_integrity("Insufficient canonical accounting snapshots.")

    prev_positions: dict[str, int] = {}
    receivable_before = 0.0
    prev_effective_max_positions: int | None = None
    samples = {
        "missing_evidence": [],
        "cash_check_fail": [],
        "receivable_check_fail": [],
        "position_check_fail": [],
        "nav_check_fail": [],
        "invalid_nav": [],
        "negative_cash": [],
        "max_positions_breach": [],
    }
    summary = {
        "trading_days": int(len(rows)),
        "days_with_evidence": 0,
        "missing_evidence_days": 0,
        "cash_check_pass": 0,
        "cash_check_fail": 0,
        "receivable_check_pass": 0,
        "receivable_check_fail": 0,
        "position_check_pass": 0,
        "position_check_fail": 0,
        "nav_check_pass": 0,
        "nav_check_fail": 0,
        "invalid_nav_days": 0,
        "negative_cash_days": 0,
        "max_positions_breach_days": 0,
    }

    for raw_row in rows:
        row = dict(raw_row or {})
        day = str(row.get("day") or "").strip()
        cash_after = _safe_float(row.get("cash_after"))
        dividend_receivable_after = _safe_float(row.get("dividend_receivable_after"))
        nav = _safe_float(row.get("nav"))
        market_value = _safe_float(row.get("market_value"))
        effective_max_positions = _safe_int(row.get("effective_max_positions"))
        max_positions = _safe_int(row.get("hard_max_positions"))
        if max_positions is None:
            max_positions = _safe_int(row.get("max_positions"))
        positions_after = _normalize_positions(row.get("positions_after"))
        trade_rows = row.get("trade_rows")
        if (
            not day
            or cash_after is None
            or market_value is None
            or max_positions is None
            or positions_after is None
            or not isinstance(trade_rows, list)
        ):
            summary["missing_evidence_days"] += 1
            _append_sample(
                samples["missing_evidence"],
                {
                    "day": day or None,
                    "cash_after_present": cash_after is not None,
                    "dividend_receivable_after_present": dividend_receivable_after is not None,
                    "nav_present": nav is not None,
                    "market_value_present": market_value is not None,
                    "positions_after_present": positions_after is not None,
                    "trade_rows_present": isinstance(trade_rows, list),
                    "max_positions_present": max_positions is not None,
                    "effective_max_positions_present": effective_max_positions is not None,
                },
            )
            continue

        buy_net = 0.0
        sell_net = 0.0
        dividend_cash_credit = _safe_float(row.get("dividend_cash_credit_today")) or 0.0
        dividend_receivable_create = _safe_float(row.get("dividend_receivable_create_today")) or 0.0
        dividend_receivable_settle = _safe_float(row.get("dividend_receivable_settle_today")) or 0.0
        trade_deltas: dict[str, int] = {}
        trade_rows_valid = True
        for raw_trade in trade_rows:
            trade = dict(raw_trade or {})
            symbol = str(trade.get("symbol") or "").lower().strip()
            side = str(trade.get("side") or "").upper().strip()
            qty = _safe_int(trade.get("qty"))
            net_amount = _safe_float(trade.get("net_amount"))
            if not symbol or side not in {"BUY", "SELL"} or qty is None or net_amount is None:
                trade_rows_valid = False
                break
            if side == "BUY":
                buy_net += float(net_amount)
                trade_deltas[symbol] = int(trade_deltas.get(symbol, 0)) + int(qty)
            else:
                sell_net += float(net_amount)
                trade_deltas[symbol] = int(trade_deltas.get(symbol, 0)) - int(qty)

        if not trade_rows_valid:
            summary["missing_evidence_days"] += 1
            _append_sample(
                samples["missing_evidence"],
                {
                    "day": day,
                    "reason": "invalid_trade_rows",
                },
            )
            continue

        summary["days_with_evidence"] += 1

        expected_cash_after = float(cash_before) + float(sell_net) + float(dividend_cash_credit) - float(buy_net)
        cash_tol = _cash_tolerance(expected_cash_after, cash_after, trade_count=len(trade_rows))
        cash_ok = abs(float(cash_after) - float(expected_cash_after)) <= cash_tol
        if cash_ok:
            summary["cash_check_pass"] += 1
        else:
            summary["cash_check_fail"] += 1
            _append_sample(
                samples["cash_check_fail"],
                {
                    "day": day,
                    "cash_before": round(float(cash_before), 4),
                    "cash_after": round(float(cash_after), 4),
                    "expected_cash_after": round(float(expected_cash_after), 4),
                    "sell_net": round(float(sell_net), 4),
                    "dividend_cash_credit": round(float(dividend_cash_credit), 4),
                    "buy_net": round(float(buy_net), 4),
                },
            )

        expected_receivable_after = float(receivable_before) + float(dividend_receivable_create) - float(dividend_receivable_settle)
        actual_receivable_after = float(dividend_receivable_after or 0.0)
        receivable_tol = _accounting_scale_tolerance(
            expected_receivable_after,
            actual_receivable_after,
            floor=_NAV_TOL,
        )
        receivable_ok = abs(actual_receivable_after - float(expected_receivable_after)) <= receivable_tol
        if receivable_ok:
            summary["receivable_check_pass"] += 1
        else:
            summary["receivable_check_fail"] += 1
            _append_sample(
                samples["receivable_check_fail"],
                {
                    "day": day,
                    "receivable_before": round(float(receivable_before), 4),
                    "receivable_after": round(float(actual_receivable_after), 4),
                    "expected_receivable_after": round(float(expected_receivable_after), 4),
                    "dividend_receivable_create": round(float(dividend_receivable_create), 4),
                    "dividend_receivable_settle": round(float(dividend_receivable_settle), 4),
                },
            )

        expected_positions = dict(prev_positions)
        corporate_action_deltas = _normalize_corporate_action_deltas(row.get("corporate_action_adjustments"))
        for symbol, delta in corporate_action_deltas.items():
            expected_positions[symbol] = int(expected_positions.get(symbol, 0)) + int(delta)
        for symbol, delta in trade_deltas.items():
            expected_positions[symbol] = int(expected_positions.get(symbol, 0)) + int(delta)
        expected_positions = {symbol: qty for symbol, qty in expected_positions.items() if int(qty) > 0}
        position_ok = expected_positions == positions_after
        if position_ok:
            summary["position_check_pass"] += 1
        else:
            summary["position_check_fail"] += 1
            mismatch_symbols = sorted(set(expected_positions) | set(positions_after))
            _append_sample(
                samples["position_check_fail"],
                {
                    "day": day,
                    "mismatched_symbols": [
                        {
                            "symbol": symbol,
                            "expected_qty": int(expected_positions.get(symbol, 0)),
                            "actual_qty": int(positions_after.get(symbol, 0)),
                        }
                        for symbol in mismatch_symbols
                        if int(expected_positions.get(symbol, 0)) != int(positions_after.get(symbol, 0))
                    ][:5],
                    "corporate_action_symbols": sorted(corporate_action_deltas),
                },
            )

        nav_valid = nav is not None and nav >= 0.0
        if not nav_valid:
            summary["invalid_nav_days"] += 1
            summary["nav_check_fail"] += 1
            _append_sample(
                samples["invalid_nav"],
                {
                    "day": day,
                    "nav": nav,
                },
            )
        else:
            expected_nav = float(cash_after) + float(actual_receivable_after) + float(market_value)
            nav_tol = _accounting_scale_tolerance(expected_nav, nav, floor=_NAV_TOL)
            nav_ok = abs(float(nav) - float(expected_nav)) <= nav_tol
            if nav_ok:
                summary["nav_check_pass"] += 1
            else:
                summary["nav_check_fail"] += 1
                _append_sample(
                    samples["nav_check_fail"],
                    {
                        "day": day,
                        "nav": round(float(nav), 4),
                        "expected_nav": round(float(expected_nav), 4),
                        "cash_after": round(float(cash_after), 4),
                        "dividend_receivable_after": round(float(actual_receivable_after), 4),
                        "market_value": round(float(market_value), 4),
                    },
                )

        if float(cash_after) < -_CASH_TOL:
            summary["negative_cash_days"] += 1
            _append_sample(
                samples["negative_cash"],
                {
                    "day": day,
                    "cash_after": round(float(cash_after), 4),
                },
            )

        schedule_cap = (
            int(prev_effective_max_positions)
            if prev_effective_max_positions is not None
            else (
                int(effective_max_positions)
                if effective_max_positions is not None
                else int(max_positions)
            )
        )
        portfolio_cap = int(schedule_cap)
        allowed_positions_cap = max(int(len(prev_positions)), int(portfolio_cap))
        if len(positions_after) > int(allowed_positions_cap):
            summary["max_positions_breach_days"] += 1
            _append_sample(
                samples["max_positions_breach"],
                {
                    "day": day,
                    "positions_count": int(len(positions_after)),
                    "max_positions": int(max_positions),
                    "scheduled_max_positions": int(schedule_cap),
                    "allowed_positions_cap": int(allowed_positions_cap),
                    "effective_max_positions": (
                        int(effective_max_positions)
                        if effective_max_positions is not None
                        else None
                    ),
                },
            )

        cash_before = float(cash_after)
        receivable_before = float(actual_receivable_after)
        prev_positions = dict(positions_after)
        prev_effective_max_positions = (
            int(effective_max_positions)
            if effective_max_positions is not None
            else int(max_positions)
        )

    hard_fail_count = (
        int(summary["cash_check_fail"])
        + int(summary["receivable_check_fail"])
        + int(summary["position_check_fail"])
        + int(summary["nav_check_fail"])
        + int(summary["negative_cash_days"])
        + int(summary["max_positions_breach_days"])
        + int(summary["invalid_nav_days"])
    )
    if hard_fail_count > 0:
        status = "FAIL"
        reason = "Detected cash, position, or NAV accounting invariant violations."
    elif int(summary["days_with_evidence"]) == 0 or int(summary["missing_evidence_days"]) > 0:
        status = "UNKNOWN"
        reason = "Canonical accounting evidence is incomplete."
    else:
        status = "PASS"
        reason = "Canonical accounting snapshots satisfy cash, position, and NAV invariants."

    return {
        "contract_version": _ACCOUNTING_AUDIT_CONTRACT_VERSION,
        "status": status,
        "reason": reason,
        "summary": summary,
        "samples": samples,
        "tolerances": {
            "cash_abs": _CASH_TOL,
            "nav_abs": _NAV_TOL,
        },
    }


def build_stage_summary(*, route_id: str, pipeline_result: Any) -> dict[str, Any]:
    summary = dict(getattr(pipeline_result, "summary", {}) or {})
    daily_results = tuple(getattr(pipeline_result, "daily_results", ()) or ())
    warnings: list[str] = []
    days_with_warnings = 0
    days_with_fills = 0
    days_with_scheduled_orders = 0

    for day_result in daily_results:
        warnings.extend(list(getattr(day_result, "warnings", ()) or ()))
        if getattr(day_result, "warnings", ()):
            days_with_warnings += 1
        if getattr(day_result, "filled_orders", ()):
            days_with_fills += 1
        if getattr(day_result, "scheduled_for_next_day", ()):
            days_with_scheduled_orders += 1

    return {
        "schema_version": str(summary.get("schema_version") or ""),
        "execution_shell": str(summary.get("execution_shell") or getattr(pipeline_result, "execution_shell", "")),
        "daily_loop_mode": str(summary.get("daily_loop_mode") or getattr(pipeline_result, "daily_loop_mode", "")),
        "route_id": str(route_id),
        "stage_order": list(summary.get("stage_order") or ()),
        "enabled_stages": list(summary.get("enabled_stages") or ()),
        "warnings": _unique_warnings(warnings or list(summary.get("warnings") or ())),
        "trading_days": int(summary.get("trading_days") or len(daily_results)),
        "days_with_warnings": int(days_with_warnings),
        "days_with_fills": int(days_with_fills),
        "days_with_scheduled_orders": int(days_with_scheduled_orders),
    }


def build_stage_pipeline_meta(stage_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(stage_summary.get("schema_version") or ""),
        "execution_shell": str(stage_summary.get("execution_shell") or ""),
        "daily_loop_mode": str(stage_summary.get("daily_loop_mode") or ""),
        "route_id": str(stage_summary.get("route_id") or ""),
        "stage_order": list(stage_summary.get("stage_order") or ()),
        "enabled_stages": list(stage_summary.get("enabled_stages") or ()),
        "warnings": list(stage_summary.get("warnings") or ()),
        "trading_days": int(stage_summary.get("trading_days") or 0),
    }


def build_stage_pipeline_audit(
    stage_pipeline: dict[str, Any] | None,
    stage_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(stage_pipeline, dict) and not isinstance(stage_summary, dict):
        return None
    audit_obj: dict[str, Any] = {}
    if isinstance(stage_pipeline, dict) and stage_pipeline:
        audit_obj["stage_pipeline"] = dict(stage_pipeline)
    if isinstance(stage_summary, dict) and stage_summary:
        audit_obj["warnings"] = list(stage_summary.get("warnings") or ())
        audit_obj["days_with_warnings"] = int(stage_summary.get("days_with_warnings") or 0)
        audit_obj["days_with_fills"] = int(stage_summary.get("days_with_fills") or 0)
        audit_obj["days_with_scheduled_orders"] = int(stage_summary.get("days_with_scheduled_orders") or 0)
    return audit_obj or None


def merge_experiment_audit(
    base_audit: dict[str, Any] | None,
    *,
    stage_pipeline: dict[str, Any] | None = None,
    stage_summary: dict[str, Any] | None = None,
    exp_id: str | None = None,
) -> dict[str, Any]:
    audit = dict(base_audit or {})
    stage_audit = build_stage_pipeline_audit(stage_pipeline, stage_summary)
    if isinstance(stage_audit, dict) and stage_audit:
        audit.update(stage_audit)
    if exp_id is not None:
        audit["exp_id"] = str(exp_id)
    return audit
