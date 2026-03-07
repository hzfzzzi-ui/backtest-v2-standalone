from __future__ import annotations

import re

import pandas as pd

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def safe_ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"invalid SQL identifier: {name}")
    return name


def normalize_stock_symbol(symbol: str) -> str:
    s = symbol.strip()
    if "." in s:
        code, exch = s.split(".", 1)
        return ("sh" if exch.upper() == "SH" else "sz") + code
    if s.lower().startswith(("sh", "sz", "bj")):
        return s.lower()
    if s and s[0] in {"6", "5", "9"}:
        return f"sh{s}"
    return f"sz{s}"


def normalize_index_symbol(symbol: str) -> str:
    s = symbol.strip()
    if "." in s:
        return s.upper()
    if s.lower().startswith(("sh", "sz")) and len(s) == 8:
        return f"{s[2:]}.{s[:2].upper()}"
    raise ValueError(f"unsupported benchmark symbol format: {symbol}")


def ts_to_cn_index_symbol(symbol: str) -> str:
    """Convert TS-style index symbol to internal CN_INDEX symbol.

    Examples:
    - 000300.SH -> sh000300
    - 399001.SZ -> sz399001
    """
    s = symbol.strip()
    if "." not in s:
        if s.lower().startswith(("sh", "sz")) and len(s) == 8:
            return s.lower()
        raise ValueError(f"unsupported CN_INDEX symbol format: {symbol}")
    code, exch = s.split(".", 1)
    exch_u = exch.upper()
    if exch_u not in {"SH", "SZ"}:
        raise ValueError(f"unsupported CN_INDEX exchange suffix: {symbol}")
    if not code.isdigit():
        raise ValueError(f"unsupported CN_INDEX code format: {symbol}")
    return ("sh" if exch_u == "SH" else "sz") + code


def to_canonical(
    df: pd.DataFrame,
    mapping: dict[str, str],
    amount_optional: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    required = ["date", "symbol", "open", "high", "low", "close"]
    for key in required:
        if key not in mapping or not mapping[key]:
            raise ValueError(f"missing mapping key: {key}")

    rename_map = {mapping[k]: k for k in required if mapping[k] in df.columns}

    volume_col = mapping.get("volume", "")
    amount_col = mapping.get("amount", "")

    if volume_col and volume_col in df.columns:
        rename_map[volume_col] = "volume"
    else:
        warnings.append("volume column missing; liquidity checks may be degraded")

    if amount_col and amount_col in df.columns:
        rename_map[amount_col] = "amount"
    elif amount_optional:
        warnings.append("amount column missing; amount filled with NaN")

    out = df.rename(columns=rename_map).copy()

    if "volume" not in out.columns:
        out["volume"] = pd.NA
    if "amount" not in out.columns:
        out["amount"] = pd.NA

    optional_cols = {
        "limit_up": mapping.get("limit_up", ""),
        "limit_down": mapping.get("limit_down", ""),
        "is_suspended": mapping.get("is_suspended", ""),
        "is_st": mapping.get("is_st", ""),
        "adj_factor": mapping.get("adj_factor", ""),
    }
    for key, src_col in optional_cols.items():
        if src_col and src_col in df.columns:
            out[key] = df[src_col]

    base_cols = ["date", "symbol", "open", "high", "low", "close", "volume", "amount"]
    keep_cols = base_cols + [c for c in ("limit_up", "limit_down", "is_suspended", "is_st", "adj_factor") if c in out.columns]
    out = out[keep_cols]
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()

    # Convert numeric columns from Decimal to float (fixes PostgreSQL Decimal issues)
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)

    # Convert optional limit/suspension columns to float
    for col in ["limit_up", "limit_down"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # adj_factor: Decimal→float, 按股票前向填充（覆盖数据滞后场景），兜底 1.0
    if "adj_factor" in out.columns:
        out["adj_factor"] = pd.to_numeric(out["adj_factor"], errors="coerce")
        out["adj_factor"] = out.groupby("symbol")["adj_factor"].ffill().fillna(1.0).astype(float)

    out = out.sort_values(["date", "symbol"]).reset_index(drop=True)
    return out, warnings
