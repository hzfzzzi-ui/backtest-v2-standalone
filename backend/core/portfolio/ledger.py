from __future__ import annotations

import json
from dataclasses import asdict

from backend.core.core.models import Order, Trade


class Ledger:
    def __init__(self) -> None:
        self.orders: list[Order] = []
        self.trades: list[Trade] = []

    def add_order(self, order: Order) -> None:
        self.orders.append(order)

    def add_trade(self, trade: Trade) -> None:
        self.trades.append(trade)

    def orders_rows(self) -> list[dict]:
        out = []
        for o in self.orders:
            r = asdict(o)
            r["signal_date"] = o.signal_date.isoformat()
            r["submit_date"] = o.submit_date.isoformat()
            r["side"] = o.side.value
            r["status"] = o.status.value
            r["reject_reason"] = o.reject_reason.value if o.reject_reason else ""
            r["skip_reason"] = o.skip_reason or ""
            r["reject_stage"] = o.reject_stage or ""
            r["limit_state"] = r["reject_reason"] if r["reject_reason"] in {"LIMIT_UP", "LIMIT_DOWN"} else ""
            r["slippage"] = ""
            r["slippage_cost"] = ""
            meta_json = json.dumps(o.meta, ensure_ascii=False, sort_keys=True) if o.meta else ""
            r["meta"] = meta_json
            r["meta_json"] = meta_json
            out.append(r)
        return out

    def trades_rows(self) -> list[dict]:
        out = []
        order_reason_code = {o.order_id: (o.reason_code or "") for o in self.orders}
        for t in self.trades:
            r = asdict(t)
            r["trade_date"] = t.trade_date.isoformat()
            r["side"] = t.side.value
            r["slippage_cost"] = r.get("slippage", 0.0)
            r["reject_reason"] = ""
            r["skip_reason"] = ""
            r["reject_stage"] = ""
            r["limit_state"] = ""
            r["reason_code"] = order_reason_code.get(t.order_id, "")
            out.append(r)
        return out
