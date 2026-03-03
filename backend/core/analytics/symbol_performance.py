from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import pandas as pd


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def _max_drawdown_from_equity(equity: list[float]) -> float:
    if not equity:
        return 0.0
    peak = None
    max_dd = 0.0
    for v in equity:
        if peak is None or v > peak:
            peak = v
        if peak and peak > 0:
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return float(max_dd)


def build_symbol_performance(
    *,
    trades_df: pd.DataFrame,
    last_close_map: dict[str, float],
    last_date: date | None,
) -> pd.DataFrame:
    """
    快速口径：
    - 已平仓：按 FIFO 成交配对计算净收益（含佣金/印花税/滑点）。
    - 未平仓：按区间末日收盘价近似估值。
    """
    columns = [
        "symbol",
        "return_pct",
        "max_drawdown",
        "net_pnl",
        "realized_pnl",
        "unrealized_approx_pnl",
        "trades",
        "buy_notional",
        "valuation_fallback_used",
        "valuation_price",
        "last_valuation_date",
    ]
    if trades_df.empty:
        return pd.DataFrame(columns=columns)

    df = trades_df.copy()
    date_col = "date" if "date" in df.columns else ("trade_date" if "trade_date" in df.columns else None)
    if date_col is None:
        return pd.DataFrame(columns=columns)

    df["trade_date"] = pd.to_datetime(df[date_col], errors="coerce").dt.date
    df = df.dropna(subset=["trade_date"])
    if "symbol" not in df.columns or "side" not in df.columns:
        return pd.DataFrame(columns=columns)

    for col in ("qty", "value", "commission", "stamp_tax", "slippage"):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["side"] = df["side"].astype(str).str.upper()
    df["symbol"] = df["symbol"].astype(str).str.lower()
    df = df.sort_values(["trade_date"]).reset_index(drop=True)

    lots: dict[str, list[dict[str, Any]]] = defaultdict(list)
    realized_by_symbol: dict[str, float] = defaultdict(float)
    buy_notional_by_symbol: dict[str, float] = defaultdict(float)
    trade_count_by_symbol: dict[str, int] = defaultdict(int)
    pnl_events: dict[str, list[tuple[date, float]]] = defaultdict(list)
    fallback_used: dict[str, bool] = defaultdict(bool)

    for t in df.itertuples(index=False):
        sym = str(t.symbol)
        side = str(t.side)
        qty = max(0, _to_int(getattr(t, "qty", 0)))
        if qty <= 0:
            continue
        value = _to_float(getattr(t, "value", 0.0))
        comm = _to_float(getattr(t, "commission", 0.0))
        stax = _to_float(getattr(t, "stamp_tax", 0.0))
        slip = _to_float(getattr(t, "slippage", 0.0))
        tdate = t.trade_date

        trade_count_by_symbol[sym] += 1

        if side == "BUY":
            buy_notional_by_symbol[sym] += max(0.0, value)
            unit_cost = (value + comm + slip) / float(qty) if qty > 0 else 0.0
            lots[sym].append({"qty": int(qty), "unit_cost": float(unit_cost), "trade_date": tdate})
            continue

        if side != "SELL":
            continue

        unit_proceed = (value - comm - stax - slip) / float(qty) if qty > 0 else 0.0
        remain = int(qty)
        queue = lots[sym]
        while remain > 0 and queue:
            lot = queue[0]
            matched = min(remain, int(lot["qty"]))
            pnl = (unit_proceed - float(lot["unit_cost"])) * float(matched)
            realized_by_symbol[sym] += pnl
            pnl_events[sym].append((tdate, pnl))
            lot["qty"] = int(lot["qty"]) - int(matched)
            remain -= int(matched)
            if int(lot["qty"]) <= 0:
                queue.pop(0)

    rows: list[dict[str, Any]] = []
    symbols = sorted(set(df["symbol"].astype(str).str.lower().tolist()))
    valuation_date_s = last_date.isoformat() if isinstance(last_date, date) else ""
    for sym in symbols:
        valuation_px = last_close_map.get(sym)
        if valuation_px is None:
            # 无法拿到末日收盘时，回退到最后成交价近似，标记 fallback。
            fallback_used[sym] = True
            sdf = df[df["symbol"] == sym]
            valuation_px = float(pd.to_numeric(sdf.get("price"), errors="coerce").dropna().iloc[-1]) if "price" in sdf.columns and not sdf.empty else 0.0

        unrealized = 0.0
        for lot in lots.get(sym, []):
            q = int(lot["qty"])
            if q <= 0:
                continue
            unrealized += (float(valuation_px) - float(lot["unit_cost"])) * float(q)

        realized = float(realized_by_symbol.get(sym, 0.0))
        net = realized + unrealized
        buy_notional = float(buy_notional_by_symbol.get(sym, 0.0))
        ret = (net / buy_notional) if buy_notional > 0 else 0.0

        # 以事件累积净值近似回撤：1 + cumulative_pnl / buy_notional
        ev = sorted(pnl_events.get(sym, []), key=lambda x: x[0])
        cum = 0.0
        equity = [1.0]
        if buy_notional > 0:
            for _, p in ev:
                cum += float(p)
                equity.append(1.0 + cum / buy_notional)
            if unrealized != 0.0:
                equity.append(1.0 + (cum + unrealized) / buy_notional)
        max_dd = _max_drawdown_from_equity(equity)

        rows.append(
            {
                "symbol": sym,
                "return_pct": float(ret),
                "max_drawdown": float(max_dd),
                "net_pnl": float(net),
                "realized_pnl": float(realized),
                "unrealized_approx_pnl": float(unrealized),
                "trades": int(trade_count_by_symbol.get(sym, 0)),
                "buy_notional": float(buy_notional),
                "valuation_fallback_used": bool(fallback_used.get(sym, False)),
                "valuation_price": float(valuation_px or 0.0),
                "last_valuation_date": valuation_date_s,
            }
        )

    out = pd.DataFrame(rows, columns=columns)
    if out.empty:
        return out
    out = out.sort_values(["return_pct", "net_pnl", "symbol"], ascending=[False, False, True]).reset_index(drop=True)
    return out
