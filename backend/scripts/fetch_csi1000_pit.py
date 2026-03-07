"""Fetch CSI1000 constituents and build a PIT CSV for import.

This script uses AkShare latest CSI1000 constituent list and emits a static PIT
snapshot CSV that can be imported into `pit_index_constituents`.

Note:
- This is a static fallback dataset (latest constituents only), not true
  historical monthly rebalance history.
- All symbols are assigned the same `in_date` and open-ended `out_date`.

Usage:
  python backend/scripts/fetch_csi1000_pit.py
  python backend/scripts/fetch_csi1000_pit.py --in-date 2014-10-17
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _to_local_symbol(code: str) -> str:
    c = str(code).strip()
    if not c:
        return c
    c = c.zfill(6)
    if c.startswith(("6", "9")):
        return f"{c}.SH"
    return f"{c}.SZ"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch CSI1000 constituents to PIT CSV")
    parser.add_argument(
        "--in-date",
        default="2014-10-17",
        help="static in_date for all constituents (default: 2014-10-17)",
    )
    parser.add_argument(
        "--out",
        default="data_cache/csi1000_pit_changes.csv",
        help="output csv path",
    )
    args = parser.parse_args()

    import akshare as ak  # local dependency for fetch only

    df = ak.index_stock_cons_csindex(symbol="000852")
    if df is None or df.empty:
        raise RuntimeError("empty CSI1000 constituents from ak.index_stock_cons_csindex('000852')")

    code_col = "成分券代码"
    if code_col not in df.columns:
        code_col = df.columns[4]

    symbols = sorted({_to_local_symbol(v) for v in df[code_col].tolist() if str(v).strip()})
    if not symbols:
        raise RuntimeError("no valid symbols parsed from CSI1000 constituents")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["index_code", "symbol", "in_date", "out_date"])
        writer.writeheader()
        for sym in symbols:
            writer.writerow(
                {
                    "index_code": "000852.SH",
                    "symbol": sym,
                    "in_date": args.in_date,
                    "out_date": "",
                }
            )

    print(f"written: {out_path} rows={len(symbols)} index_code=000852.SH in_date={args.in_date}")


if __name__ == "__main__":
    main()

