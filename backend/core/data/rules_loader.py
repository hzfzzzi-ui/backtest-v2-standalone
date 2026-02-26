from __future__ import annotations

from pathlib import Path

import pandas as pd


def _default_type_by_symbol(symbol: str) -> str:
    s = str(symbol).strip().upper()
    code = s.split(".", 1)[0] if "." in s else s
    exch = s.split(".", 1)[1] if "." in s else ""
    if (exch == "SH" and code.startswith("5")) or (exch == "SZ" and code.startswith(("15", "16", "18"))):
        return "ETF"
    return "STOCK"


def _as_bool(value: object, default: bool) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "t", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "no", "n"}:
        return False
    return default


def load_rules_csv(path: str | Path, symbols: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"symbol": "string"})
    df["symbol"] = df["symbol"].str.strip().str.upper()
    if "type" not in df.columns:
        df["type"] = df["symbol"].map(_default_type_by_symbol)
    else:
        df["type"] = df["type"].astype("string").str.strip().str.upper()
        df["type"] = df.apply(
            lambda r: _default_type_by_symbol(r["symbol"]) if pd.isna(r["type"]) or str(r["type"]).strip() == "" else str(r["type"]).upper(),
            axis=1,
        )
    if "stamp_tax_sell" not in df.columns:
        df["stamp_tax_sell"] = df["type"].map(lambda x: str(x).upper() == "STOCK")
    else:
        df["stamp_tax_sell"] = df.apply(
            lambda r: _as_bool(r["stamp_tax_sell"], str(r["type"]).upper() == "STOCK"),
            axis=1,
        )

    need = {s.upper() for s in symbols}
    hit = df[df["symbol"].isin(need)].copy()
    if hit.empty:
        hit = pd.DataFrame(
            {
                "symbol": sorted(need),
                "board": "MAIN",
                "type": "STOCK",
                "lot_size": 100,
                "tick_size": 0.01,
                "limit_pct": 0.10,
                "stamp_tax_sell": True,
            }
        )
    else:
        missing = sorted(need - set(hit["symbol"].tolist()))
        if missing:
            hit = pd.concat(
                [
                    hit,
                    pd.DataFrame(
                        {
                            "symbol": missing,
                            "board": "MAIN",
                            "type": "STOCK",
                            "lot_size": 100,
                            "tick_size": 0.01,
                            "limit_pct": 0.10,
                            "stamp_tax_sell": True,
                        }
                    ),
                ],
                ignore_index=True,
            )
    hit["stamp_tax_sell"] = hit.apply(
        lambda r: _as_bool(r.get("stamp_tax_sell"), str(r.get("type", "STOCK")).upper() == "STOCK"),
        axis=1,
    )
    return hit.sort_values("symbol").reset_index(drop=True)
