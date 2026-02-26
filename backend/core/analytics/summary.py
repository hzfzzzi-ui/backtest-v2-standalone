from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from backend.core.analytics.schema import normalize_order_status


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if pd.isna(x):
            return default
        return x
    except Exception:
        return default


def _kpis(equity: pd.DataFrame, orders: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    trading_days = int(len(equity))
    orders_total = int(len(orders))
    trades_count = int(len(trades))

    skipped_orders = 0
    rejected_orders = 0
    filled_orders = 0
    if orders_total > 0 and "status" in orders.columns:
        statuses = orders["status"].map(normalize_order_status)
        filled_orders = int(statuses.isin(["FILLED", "PARTIAL_FILLED"]).sum())
        rejected_orders = int(statuses.isin(["REJECTED", "CANCELLED"]).sum())
        skipped_orders = int(orders["status"].astype(str).str.upper().eq("SKIPPED").sum())
        filled_rate = filled_orders / orders_total
    else:
        filled_rate = 0.0

    total_return = 0.0
    max_drawdown = 0.0
    cagr = 0.0
    volatility = 0.0
    sharpe = 0.0
    if not equity.empty and "equity" in equity.columns:
        eq = equity["equity"].astype(float)
        if len(eq) >= 2 and _safe_float(eq.iloc[0]) > 0:
            total_return = _safe_float(eq.iloc[-1]) / _safe_float(eq.iloc[0]) - 1.0
            years = max(trading_days / 252.0, 1 / 252.0)
            cagr = (_safe_float(eq.iloc[-1]) / _safe_float(eq.iloc[0])) ** (1.0 / years) - 1.0
        if "drawdown_pct" in equity.columns:
            max_drawdown = abs(_safe_float(equity["drawdown_pct"].min()) / 100.0)
        ret = eq.pct_change().dropna()
        if len(ret) > 1:
            volatility = float(ret.std(ddof=0) * (252.0**0.5))
            mean_daily = float(ret.mean())
            sharpe = (mean_daily * 252.0 / volatility) if volatility > 0 else 0.0

    return {
        "trading_days": trading_days,
        "orders_total": orders_total,
        "trades_count": trades_count,
        "filled_orders": filled_orders,
        "rejected_orders": rejected_orders,
        "skipped_orders": skipped_orders,
        "filled_rate": round(filled_rate, 6),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "cagr": round(cagr, 6),
        "volatility": round(volatility, 6),
        "sharpe": round(sharpe, 6),
    }


def _reasons(orders: pd.DataFrame, trades: pd.DataFrame) -> list[dict[str, Any]]:
    if orders.empty or "reason_code" not in orders.columns:
        return []

    out: list[dict[str, Any]] = []
    trades_by_order = (
        trades.groupby("order_id").size().to_dict()
        if ("order_id" in trades.columns and not trades.empty)
        else {}
    )
    grouped = orders.groupby("reason_code", dropna=False)
    for reason, sub in grouped:
        code = str(reason or "").strip()
        if not code:
            continue
        order_ids = set(sub["order_id"].tolist()) if "order_id" in sub.columns else set()
        fills = int(sub["status"].map(normalize_order_status).isin(["FILLED", "PARTIAL_FILLED"]).sum()) if "status" in sub.columns else 0
        trades_count = int(sum(trades_by_order.get(int(oid), 0) for oid in order_ids))
        out.append(
            {
                "reason_code": code,
                "orders": int(len(sub)),
                "fills": fills,
                "trades": trades_count,
                "win_rate": None,
                "avg_hold_days": None,
            }
        )
    out.sort(key=lambda x: x["orders"], reverse=True)
    return out


def _recommendations(kpi: dict[str, Any], costs: dict[str, Any], warnings: list[str]) -> list[dict[str, str]]:
    recs: list[dict[str, str]] = []
    if kpi["trades_count"] > 20 and kpi["max_drawdown"] > 0.15:
        recs.append(
            {
                "code": "ADD_TREND_FILTER",
                "title": "建议加趋势过滤/风险开关",
                "detail": "交易频繁且回撤偏大，建议增加风险开关或趋势过滤。",
            }
        )
    if kpi["filled_rate"] < 0.6 or (
        kpi["trades_count"] > 0 and costs["fees_total"] > 0 and abs(kpi["total_return"]) < 0.03
    ):
        recs.append(
            {
                "code": "REDUCE_TURNOVER",
                "title": "换手偏高，建议降低交易频率",
                "detail": "当前成交效率或成本压力偏高，建议提高入场阈值或减少频繁换仓。",
            }
        )
    if warnings:
        recs.append(
            {
                "code": "DATA_QUALITY_WARNING",
                "title": "数据质量告警",
                "detail": "存在校验/运行告警，建议先处理数据质量问题再做参数优化。",
            }
        )

    pool = [
        {
            "code": "TUNE_ATR_STOP",
            "title": "止损参数可再校准",
            "detail": "建议回测不同 ATR 倍数与均线窗口，比较回撤与收益稳定性。",
        },
        {
            "code": "CHECK_LIMITS",
            "title": "检查涨跌停与流动性拒单",
            "detail": "若成交率偏低，优先排查涨跌停、停牌与容量限制带来的拒单。",
        },
        {
            "code": "BENCHMARK_COMPARE",
            "title": "增加基准对比",
            "detail": "建议对比同区间基准收益与回撤，评估超额收益稳定性。",
        },
    ]
    for p in pool:
        if len(recs) >= 3:
            break
        if p["code"] not in {r["code"] for r in recs}:
            recs.append(p)
    return recs[:3]


def _top_reasons(
    orders: pd.DataFrame,
    statuses: set[str],
    reason_col: str,
    use_raw_status: bool = False,
) -> dict[str, int]:
    if orders.empty or "status" not in orders.columns or reason_col not in orders.columns:
        return {}
    if use_raw_status:
        s = orders["status"].astype(str).str.upper()
    else:
        s = orders["status"].map(normalize_order_status)
    part = orders[s.isin(statuses)].copy()
    if part.empty:
        return {}
    return (
        part[reason_col]
        .astype(str)
        .str.strip()
        .replace({"": "UNKNOWN"})
        .value_counts()
        .head(3)
        .to_dict()
    )


def _exit_reason_breakdown(orders: pd.DataFrame) -> dict[str, int]:
    if orders.empty or "reason_code" not in orders.columns:
        return {}
    status = orders["status"].map(normalize_order_status) if "status" in orders.columns else pd.Series([""] * len(orders))
    side = orders["side"].astype(str).str.upper() if "side" in orders.columns else pd.Series([""] * len(orders))
    part = orders[status.isin(["FILLED", "PARTIAL_FILLED"]) & side.eq("SELL")]
    if part.empty:
        return {}
    return (
        part["reason_code"]
        .astype(str)
        .str.strip()
        .replace({"": "UNKNOWN"})
        .value_counts()
        .to_dict()
    )


def build_report_summary(
    run_id: str,
    start: date,
    end: date,
    symbols: list[str],
    benchmark_symbol: str,
    benchmark_snapshot: dict[str, Any] | None,
    strategy_name: str,
    strategy_params: dict[str, Any],
    equity: pd.DataFrame,
    orders: pd.DataFrame,
    trades: pd.DataFrame,
    report: dict[str, Any],
    warnings: list[str],
    chart: dict[str, Any] | None = None,
    trade_concentration: dict[str, Any] | None = None,
    conclusions_10: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kpi = _kpis(equity, orders, trades)
    costs = {
        "commission_total": _safe_float(report.get("cost_breakdown", {}).get("commission_total")),
        "stamp_tax_total": _safe_float(report.get("cost_breakdown", {}).get("stamp_tax_total")),
        "fees_total": _safe_float(report.get("cost_breakdown", {}).get("fees_total")),
        "slippage_attribution_total": _safe_float(report.get("cost_breakdown", {}).get("slippage_cost_total")),
    }

    bench_rows = int((benchmark_snapshot or {}).get("row_count", 0))
    bench_sources = (benchmark_snapshot or {}).get("sources", [])
    bench_source = bench_sources[0] if bench_sources else "unknown"

    audit_rules = report.get("audit_rules", {})
    validation = report.get("data_validation", {"request_id": None, "passed": None, "warnings": []})
    recs = _recommendations(kpi, costs, list(validation.get("warnings", [])) + list(warnings or []))
    execution_profile = str(audit_rules.get("execution_profile", "basic"))
    sizing_cfg = dict(audit_rules.get("sizing", {}) or {})
    raw_signals_total = int(audit_rules.get("raw_signals_total", 0) or 0)
    raw_buy_signals = int(audit_rules.get("raw_buy_signals", 0) or 0)
    raw_sell_signals = int(audit_rules.get("raw_sell_signals", 0) or 0)
    blocked_signals_total = int(audit_rules.get("blocked_signals_total", 0) or 0)
    blocked_buy_signals = int(audit_rules.get("blocked_buy_signals", 0) or 0)
    blocked_reasons_top3 = dict(audit_rules.get("blocked_reasons_top3", {}) or {})
    tradable_orders_total = int(audit_rules.get("tradable_orders_total", kpi.get("orders_total", 0)) or 0)
    skipped_orders = int(audit_rules.get("skipped_orders", kpi.get("skipped_orders", 0)) or 0)
    top_skip_reason = dict(audit_rules.get("top_skip_reason", {}) or {})
    skipped_reasons_top3 = _top_reasons(orders, {"SKIPPED"}, "skip_reason", use_raw_status=True)
    if not skipped_reasons_top3:
        skipped_reasons_top3 = top_skip_reason
    rejected_reasons_top3 = _top_reasons(orders, {"REJECTED", "CANCELLED"}, "reject_reason")
    exit_reason_breakdown = _exit_reason_breakdown(orders)

    return {
        "run_id": run_id,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "universe": {"symbols_count": len(symbols), "symbols_sample": symbols[:10]},
        "benchmark": {"symbol": benchmark_symbol, "rows": bench_rows, "source": bench_source},
        "strategy": {"name": strategy_name, "params": strategy_params},
        "kpis": kpi,
        "execution_profile": execution_profile,
        "sizing": sizing_cfg,
        "raw_signals_total": raw_signals_total,
        "raw_buy_signals": raw_buy_signals,
        "raw_sell_signals": raw_sell_signals,
        "blocked_signals_total": blocked_signals_total,
        "blocked_buy_signals": blocked_buy_signals,
        "blocked_reasons_top3": blocked_reasons_top3,
        "tradable_orders_total": tradable_orders_total,
        "skipped_orders": skipped_orders,
        "top_skip_reason": top_skip_reason,
        "signal_stats": {
            "raw_signals_total": raw_signals_total,
            "raw_buy_signals": raw_buy_signals,
            "raw_sell_signals": raw_sell_signals,
            "blocked_signals_total": blocked_signals_total,
            "blocked_buy_signals": blocked_buy_signals,
            "blocked_reasons_top3": blocked_reasons_top3,
        },
        "execution_stats": {
            "tradable_orders_total": tradable_orders_total,
            "skipped_orders_total": int(kpi.get("skipped_orders", 0)),
            "skipped_reasons_top3": skipped_reasons_top3,
            "rejected_orders_total": int(kpi.get("rejected_orders", 0)),
            "rejected_reasons_top3": rejected_reasons_top3,
        },
        "costs": costs,
        "reasons": _reasons(orders, trades),
        "exit_reason_breakdown": exit_reason_breakdown,
        "audit": {
            "no_lookahead_enforced": bool(audit_rules.get("no_lookahead_enforced", True)),
            "slippage_mode": report.get("slippage_mode", "price_adjustment_only"),
            "limit_source": audit_rules.get("limit_source"),
            "limit_price_epsilon": audit_rules.get("limit_price_epsilon"),
            "validation": {
                "request_id": validation.get("request_id"),
                "passed": validation.get("passed"),
                "warnings": validation.get("warnings", []),
            },
        },
        "recommendations": recs,
        "chart": chart or {},
        "trade_concentration": trade_concentration or {},
        "conclusions_10": conclusions_10 or {},
        "artifacts": {
            "report_json": "report.json",
            "report_summary_json": "report_summary.json",
            "equity_curve_csv": "equity_curve.csv",
            "benchmark_curve_csv": "benchmark_curve.csv",
            "orders_csv": "orders.csv",
            "trades_csv": "trades.csv",
            "trade_pnl_csv": "trade_pnl.csv",
            "signals_csv": "signals.csv",
            "conclusions_10_json": "conclusions_10.json",
            "conclusions_10_txt": "conclusions_10.txt",
            "warnings_json": "warnings.json",
        },
    }
