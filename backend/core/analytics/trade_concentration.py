from __future__ import annotations

import math
from typing import Any

import pandas as pd


def compute_trade_concentration(trade_pnl: pd.DataFrame) -> dict[str, Any]:
    if trade_pnl.empty or "net_pnl" not in trade_pnl.columns:
        return {
            "closed_trades": 0,
            "k5": 0,
            "k10": 0,
            "sum_all": 0.0,
            "sum_top5": 0.0,
            "sum_top10": 0.0,
            "top5_contribution_pct": None,
            "top10_contribution_pct": None,
            "top10_vs_total_net_pct": None,
            "top10_profit_concentration_pct": None,
            "top10_offset_loss_pct": None,
            "sample_hint": "no_closed_trades",
            "warning_notes": "no closed trades",
        }

    pnl = trade_pnl["net_pnl"].astype(float)
    n = int(len(pnl))
    k5 = int(math.ceil(n * 0.05)) if n > 0 else 0
    k10 = int(math.ceil(n * 0.10)) if n > 0 else 0
    sorted_pnl = pnl.sort_values(ascending=False)

    sum_all = float(pnl.sum())
    sum_top5 = float(sorted_pnl.head(k5).sum()) if k5 > 0 else 0.0
    sum_top10 = float(sorted_pnl.head(k10).sum()) if k10 > 0 else 0.0
    top5_vs_total = (sum_top5 / sum_all) if abs(sum_all) > 1e-12 else None
    top10_vs_total = (sum_top10 / sum_all) if abs(sum_all) > 1e-12 else None

    sum_pos = float(pnl.clip(lower=0.0).sum())
    top10_pos = float(sorted_pnl.head(k10).clip(lower=0.0).sum()) if k10 > 0 else 0.0
    top10_profit_concentration = (top10_pos / sum_pos) if sum_pos > 0 else None
    top10_offset_loss = (top10_pos / abs(sum_all)) if sum_all < 0 and abs(sum_all) > 1e-12 else None

    warning_notes = ""
    if n == 0:
        warning_notes = "no closed trades"
    elif sum_pos <= 0:
        warning_notes = "no positive pnl trades"

    return {
        "closed_trades": n,
        "k5": k5,
        "k10": k10,
        "sum_all": sum_all,
        "sum_top5": sum_top5,
        "sum_top10": sum_top10,
        "top5_contribution_pct": top5_vs_total,
        "top10_contribution_pct": top10_vs_total,
        "top10_vs_total_net_pct": top10_vs_total,
        "top10_profit_concentration_pct": top10_profit_concentration,
        "top10_offset_loss_pct": top10_offset_loss,
        "sample_hint": "small_sample" if n < 20 else "ok",
        "warning_notes": warning_notes,
    }

