from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.data.snapshot import DataSnapshot


def build_report(
    config_hash: str,
    snapshot: DataSnapshot,
    benchmark_snapshot: DataSnapshot | None,
    equity: pd.DataFrame,
    trades: pd.DataFrame,
    orders: pd.DataFrame,
    warnings: list[str],
    audit_rules: dict[str, object] | None = None,
) -> dict[str, Any]:
    total_return_pct = 0.0
    max_dd_pct = 0.0
    if not equity.empty:
        start_eq = float(equity.iloc[0]["equity"])
        end_eq = float(equity.iloc[-1]["equity"])
        total_return_pct = (end_eq / start_eq - 1.0) * 100.0 if start_eq > 0 else 0.0
        max_dd_pct = float(equity["drawdown_pct"].min()) if "drawdown_pct" in equity.columns else 0.0

    commission_total = float(trades["commission"].sum()) if "commission" in trades.columns and not trades.empty else 0.0
    stamp_tax_total = float(trades["stamp_tax"].sum()) if "stamp_tax" in trades.columns and not trades.empty else 0.0
    slippage_cost_total = float(trades["slippage"].sum()) if "slippage" in trades.columns and not trades.empty else 0.0
    fees_total = commission_total + stamp_tax_total

    report = {
        "config_hash": config_hash,
        "data_snapshot": snapshot.to_dict(),
        "benchmark_snapshot": benchmark_snapshot.to_dict() if benchmark_snapshot else None,
        "summary": {
            "trading_days": int(len(equity)),
            "orders": int(len(orders)),
            "trades": int(len(trades)),
            "total_return_pct": round(total_return_pct, 4),
            "max_drawdown_pct": round(max_dd_pct, 4),
        },
        "cost_breakdown": {
            "commission_total": round(commission_total, 6),
            "stamp_tax_total": round(stamp_tax_total, 6),
            "slippage_cost_total": round(slippage_cost_total, 6),
            "fees_total": round(fees_total, 6),
        },
        "audit_rules": audit_rules or {},
        "warnings": warnings,
    }
    report["slippage_mode"] = "price_adjustment_only"
    report["slippage_definition"] = "abs(fill_price - reference_price) * qty"
    report["slippage_reference_price"] = "open"
    if audit_rules:
        for key in (
            "slippage_mode",
            "slippage_definition",
            "slippage_reference_price",
            "stamp_tax_by_instrument",
            "prev_close_extension",
            "prev_close_missing_policy",
            "limit_source",
            "limit_fallback_reason",
            "limit_price_epsilon_mode",
            "limit_price_epsilon",
            "strategy_name",
            "strategy_params",
            "no_lookahead_enforced",
            "execution_profile",
            "sizing",
            "raw_signals_total",
            "tradable_orders_total",
            "skipped_orders",
            "top_skip_reason",
        ):
            if key in audit_rules:
                report[key] = audit_rules[key]
    return report


def write_report(report: dict[str, Any], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
