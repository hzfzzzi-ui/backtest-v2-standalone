from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from backend.core.analytics.trade_concentration import compute_trade_concentration


def _empty_trade_pnl_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "trade_id",
            "symbol",
            "entry_date",
            "exit_date",
            "qty",
            "entry_price",
            "exit_price",
            "gross_pnl",
            "fees",
            "slippage_attr",
            "net_pnl",
            "hold_days",
        ]
    )


def _to_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def build_trade_pnl(
    results_dir: str | Path,
    trades_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    if trades_df.empty:
        empty = _empty_trade_pnl_df()
        empty.to_csv(out_dir / "trade_pnl.csv", index=False)
        return empty, _concentration_stats(empty), warnings

    trades = trades_df.copy()
    trades["trade_date"] = pd.to_datetime(trades["trade_date"]).dt.normalize()
    trades["trade_id"] = trades["trade_id"].astype(int)
    trades["qty"] = trades["qty"].astype(int)
    trades["price"] = trades["price"].astype(float)
    for col in ("commission", "stamp_tax", "slippage"):
        if col not in trades.columns:
            trades[col] = 0.0
        trades[col] = trades[col].map(_to_float)
    trades["side"] = trades["side"].astype(str).str.upper()
    trades["symbol"] = trades["symbol"].astype(str)
    trades = trades.sort_values(["trade_date", "trade_id"]).reset_index(drop=True)

    lots: dict[str, list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []

    for t in trades.itertuples(index=False):
        symbol = str(t.symbol)
        qty = int(t.qty)
        if qty <= 0:
            continue
        unit_commission = _to_float(t.commission) / qty
        unit_stamp_tax = _to_float(t.stamp_tax) / qty
        unit_slippage = _to_float(t.slippage) / qty

        if str(t.side) == "BUY":
            lots.setdefault(symbol, []).append(
                {
                    "entry_date": t.trade_date,
                    "entry_price": float(t.price),
                    "remain_qty": qty,
                    "unit_commission": unit_commission,
                    "unit_slippage": unit_slippage,
                }
            )
            continue

        if str(t.side) != "SELL":
            continue

        remain = qty
        queue = lots.setdefault(symbol, [])
        while remain > 0 and queue:
            lot = queue[0]
            matched = min(remain, int(lot["remain_qty"]))
            sell_commission = unit_commission * matched
            sell_stamp = unit_stamp_tax * matched
            buy_commission = float(lot["unit_commission"]) * matched
            fees = buy_commission + sell_commission + sell_stamp
            slippage_attr = (float(lot["unit_slippage"]) + unit_slippage) * matched
            gross = (float(t.price) - float(lot["entry_price"])) * matched
            net = gross - fees
            hold_days = int((t.trade_date - lot["entry_date"]).days)
            rows.append(
                {
                    "trade_id": int(t.trade_id),
                    "symbol": symbol,
                    "entry_date": lot["entry_date"].date().isoformat(),
                    "exit_date": t.trade_date.date().isoformat(),
                    "qty": matched,
                    "entry_price": float(lot["entry_price"]),
                    "exit_price": float(t.price),
                    "gross_pnl": gross,
                    "fees": fees,
                    "slippage_attr": slippage_attr,
                    "net_pnl": net,
                    "hold_days": hold_days,
                }
            )
            remain -= matched
            lot["remain_qty"] = int(lot["remain_qty"]) - matched
            if lot["remain_qty"] <= 0:
                queue.pop(0)

        if remain > 0:
            warnings.append(
                f"TRADE_PNL_SELL_EXCEEDS_POSITION: symbol={symbol} trade_id={int(t.trade_id)} excess_qty={remain}"
            )

    out = _empty_trade_pnl_df() if not rows else pd.DataFrame(rows)
    out.to_csv(out_dir / "trade_pnl.csv", index=False)
    return out, _concentration_stats(out), warnings


def _concentration_stats(trade_pnl: pd.DataFrame) -> dict[str, Any]:
    return compute_trade_concentration(trade_pnl)
