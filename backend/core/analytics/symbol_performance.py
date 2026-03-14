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


def _normalize_daily_close_df(daily_close_df: pd.DataFrame | None) -> pd.DataFrame:
    columns = ["symbol", "trade_date", "close"]
    if daily_close_df is None or daily_close_df.empty:
        return pd.DataFrame(columns=columns)
    if "symbol" not in daily_close_df.columns or "close" not in daily_close_df.columns:
        return pd.DataFrame(columns=columns)
    date_col = "trade_date" if "trade_date" in daily_close_df.columns else ("date" if "date" in daily_close_df.columns else None)
    if date_col is None:
        return pd.DataFrame(columns=columns)

    out = daily_close_df.copy()
    out["symbol"] = out["symbol"].astype(str).str.lower()
    out["trade_date"] = pd.to_datetime(out[date_col], errors="coerce").dt.date
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["symbol", "trade_date", "close"])
    if out.empty:
        return pd.DataFrame(columns=columns)
    return out[columns].sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def _event_based_max_drawdown(
    *,
    pnl_events: list[tuple[date, float]],
    unrealized: float,
    buy_notional: float,
) -> float:
    ev = sorted(pnl_events, key=lambda x: x[0])
    cum = 0.0
    equity = [1.0]
    if buy_notional > 0:
        for _, pnl in ev:
            cum += float(pnl)
            equity.append(1.0 + cum / buy_notional)
        if unrealized != 0.0:
            equity.append(1.0 + (cum + unrealized) / buy_notional)
    return _max_drawdown_from_equity(equity)


def _marked_to_market_max_drawdown(
    *,
    sym_trades: pd.DataFrame,
    sym_close_df: pd.DataFrame,
    buy_notional: float,
) -> float | None:
    if buy_notional <= 0 or sym_trades.empty or sym_close_df.empty:
        return None

    trade_rows_by_date: dict[date, list[Any]] = defaultdict(list)
    for row in sym_trades.itertuples(index=False):
        trade_rows_by_date[row.trade_date].append(row)

    first_trade_date = sym_trades["trade_date"].min()
    close_rows = sym_close_df[sym_close_df["trade_date"] >= first_trade_date]
    if close_rows.empty:
        return None

    lots: list[dict[str, float | int]] = []
    realized = 0.0
    equity = [1.0]

    for bar in close_rows.itertuples(index=False):
        tdate = bar.trade_date
        for trade in trade_rows_by_date.get(tdate, []):
            side = str(trade.side)
            qty = max(0, _to_int(getattr(trade, "qty", 0)))
            if qty <= 0:
                continue
            value = _to_float(getattr(trade, "value", 0.0))
            comm = _to_float(getattr(trade, "commission", 0.0))
            stax = _to_float(getattr(trade, "stamp_tax", 0.0))
            slip = _to_float(getattr(trade, "slippage", 0.0))

            if side == "BUY":
                unit_cost = (value + comm + slip) / float(qty) if qty > 0 else 0.0
                lots.append({"qty": int(qty), "unit_cost": float(unit_cost)})
                continue

            if side != "SELL":
                continue

            unit_proceed = (value - comm - stax - slip) / float(qty) if qty > 0 else 0.0
            remain = int(qty)
            while remain > 0 and lots:
                lot = lots[0]
                matched = min(remain, int(lot["qty"]))
                realized += (unit_proceed - float(lot["unit_cost"])) * float(matched)
                lot["qty"] = int(lot["qty"]) - int(matched)
                remain -= int(matched)
                if int(lot["qty"]) <= 0:
                    lots.pop(0)

        close_px = _to_float(getattr(bar, "close", 0.0))
        unrealized = 0.0
        for lot in lots:
            q = int(lot["qty"])
            if q <= 0:
                continue
            unrealized += (close_px - float(lot["unit_cost"])) * float(q)
        equity.append(1.0 + (realized + unrealized) / buy_notional)

    return _max_drawdown_from_equity(equity)


def build_symbol_performance(
    *,
    trades_df: pd.DataFrame,
    last_close_map: dict[str, float],
    last_date: date | None,
    daily_close_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
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
    df["_trade_seq"] = range(len(df))
    df = df.sort_values(["trade_date", "_trade_seq"]).reset_index(drop=True)
    close_df = _normalize_daily_close_df(daily_close_df)

    lots: dict[str, list[dict[str, Any]]] = defaultdict(list)
    realized_by_symbol: dict[str, float] = defaultdict(float)
    buy_notional_by_symbol: dict[str, float] = defaultdict(float)
    trade_count_by_symbol: dict[str, int] = defaultdict(int)
    pnl_events: dict[str, list[tuple[date, float]]] = defaultdict(list)
    fallback_used: dict[str, bool] = defaultdict(bool)

    for trade in df.itertuples(index=False):
        sym = str(trade.symbol)
        side = str(trade.side)
        qty = max(0, _to_int(getattr(trade, "qty", 0)))
        if qty <= 0:
            continue
        value = _to_float(getattr(trade, "value", 0.0))
        comm = _to_float(getattr(trade, "commission", 0.0))
        stax = _to_float(getattr(trade, "stamp_tax", 0.0))
        slip = _to_float(getattr(trade, "slippage", 0.0))
        tdate = trade.trade_date

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
        sym_lots = lots.get(sym, [])
        has_open_position = any(int(lot["qty"]) > 0 for lot in sym_lots)

        valuation_px: float | None = None
        if has_open_position:
            valuation_px = last_close_map.get(sym)
            if valuation_px is None:
                fallback_used[sym] = True
                sym_df = df[df["symbol"] == sym]
                if "price" in sym_df.columns and not sym_df.empty:
                    price_series = pd.to_numeric(sym_df["price"], errors="coerce").dropna()
                    valuation_px = float(price_series.iloc[-1]) if not price_series.empty else 0.0
                else:
                    valuation_px = 0.0

        unrealized = 0.0
        for lot in sym_lots:
            q = int(lot["qty"])
            if q <= 0:
                continue
            unrealized += (float(valuation_px or 0.0) - float(lot["unit_cost"])) * float(q)

        realized = float(realized_by_symbol.get(sym, 0.0))
        net = realized + unrealized
        buy_notional = float(buy_notional_by_symbol.get(sym, 0.0))
        ret = (net / buy_notional) if buy_notional > 0 else 0.0

        sym_close_df = close_df[close_df["symbol"] == sym]
        sym_trades = df[df["symbol"] == sym]
        max_dd = _marked_to_market_max_drawdown(
            sym_trades=sym_trades,
            sym_close_df=sym_close_df,
            buy_notional=buy_notional,
        )
        if max_dd is None:
            max_dd = _event_based_max_drawdown(
                pnl_events=pnl_events.get(sym, []),
                unrealized=unrealized,
                buy_notional=buy_notional,
            )

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
                "valuation_fallback_used": bool(fallback_used.get(sym, False)) if has_open_position else False,
                "valuation_price": float(valuation_px) if has_open_position and valuation_px is not None else None,
                "last_valuation_date": valuation_date_s if has_open_position else "",
            }
        )

    out = pd.DataFrame(rows, columns=columns)
    if out.empty:
        return out
    out = out.sort_values(["return_pct", "net_pnl", "symbol"], ascending=[False, False, True]).reset_index(drop=True)
    return out
