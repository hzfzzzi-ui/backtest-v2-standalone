"""价格复权转换 — 支持 hfq（后复权）/ qfq（前复权）/ none（不复权）三种模式。

纯函数，不修改原始 DataFrame。
"""
from __future__ import annotations

import pandas as pd

_PRICE_COLS = ["open", "high", "low", "close"]


def apply_price_adjustment(history: pd.DataFrame, mode: str) -> pd.DataFrame:
    """根据 adj_factor 对 OHLCV 价格列做复权转换。

    参数:
        history: 包含 adj_factor 列的 OHLCV DataFrame（不复权价格）
        mode: "hfq"（后复权）/ "qfq"（前复权）/ "none"（不复权）

    返回:
        新 DataFrame，价格列已按指定模式转换。adj_factor 等其他列保持不变。
    """
    mode_lower = (mode or "none").strip().lower()

    if mode_lower == "none":
        return history.copy()

    if "adj_factor" not in history.columns:
        return history.copy()

    out = history.copy()
    af = out["adj_factor"].astype(float)

    if mode_lower == "hfq":
        # 后复权: adjusted_price = raw_price × adj_factor
        for col in _PRICE_COLS:
            if col in out.columns:
                out[col] = out[col].astype(float) * af
    elif mode_lower == "qfq":
        # 前复权: adjusted_price = raw_price × (adj_factor / latest_adj_factor_per_symbol)
        latest_af = out.groupby("symbol")["adj_factor"].transform("last")
        ratio = af / latest_af.astype(float)
        for col in _PRICE_COLS:
            if col in out.columns:
                out[col] = out[col].astype(float) * ratio
    else:
        raise ValueError(f"未知的复权模式: {mode!r}，支持 'hfq' / 'qfq' / 'none'")

    return out
