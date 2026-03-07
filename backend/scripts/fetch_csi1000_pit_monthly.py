"""Build CSI1000 PIT records from monthly snapshots.

Primary source:
- Tushare `index_weight` (requires token), then reconstruct monthly snapshots.

Fallback source:
- AkShare latest CSI1000 constituents replicated across months.

Outputs:
- data_cache/csi1000_pit_monthly_snapshots.csv
- data_cache/csi1000_pit_monthly_changes.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
from pathlib import Path
from typing import Iterable


def _month_ends(start: dt.date, end: dt.date) -> list[dt.date]:
    cur = dt.date(start.year, start.month, 1)
    out: list[dt.date] = []
    while cur <= end:
        if cur.month == 12:
            nxt = dt.date(cur.year + 1, 1, 1)
        else:
            nxt = dt.date(cur.year, cur.month + 1, 1)
        m_end = nxt - dt.timedelta(days=1)
        if m_end >= start and m_end <= end:
            out.append(m_end)
        cur = nxt
    return out


def _to_local_symbol(code: str) -> str:
    c = str(code).strip()
    if not c:
        return c
    if "." in c:
        left, right = c.split(".", 1)
        if right.upper() in {"SH", "SZ"}:
            return f"{left.zfill(6)}.{right.upper()}"
    c = c.zfill(6)
    if c.startswith(("6", "9")):
        return f"{c}.SH"
    return f"{c}.SZ"


def _reconstruct_changes(
    snapshots: list[tuple[str, list[str]]],
    index_code: str,
) -> list[dict[str, str]]:
    active: dict[str, str] = {}
    changes: list[dict[str, str]] = []
    for date_str, symbols in snapshots:
        current = set(symbols)
        prev = set(active.keys())
        added = current - prev
        removed = prev - current
        for sym in added:
            active[sym] = date_str
        for sym in removed:
            changes.append(
                {
                    "index_code": index_code,
                    "symbol": sym,
                    "in_date": active[sym],
                    "out_date": date_str,
                }
            )
            del active[sym]
    for sym, in_date in active.items():
        changes.append(
            {
                "index_code": index_code,
                "symbol": sym,
                "in_date": in_date,
                "out_date": "",
            }
        )
    changes.sort(key=lambda r: (r["symbol"], r["in_date"]))
    return changes


def _save_snapshots(path: Path, snapshots: Iterable[tuple[str, list[str]]]) -> int:
    total = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "symbol"])
        for d, syms in snapshots:
            for s in syms:
                w.writerow([d, s])
                total += 1
    return total


def _save_changes(path: Path, changes: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["index_code", "symbol", "in_date", "out_date"])
        w.writeheader()
        w.writerows(changes)


def _build_with_tushare(month_ends: list[dt.date], token: str) -> list[tuple[str, list[str]]]:
    import pandas as pd
    import tushare as ts

    ts.set_token(token)
    pro = ts.pro_api(token)

    start_s = month_ends[0].strftime("%Y%m%d")
    end_s = month_ends[-1].strftime("%Y%m%d")
    df = pro.index_weight(index_code="000852.SH", start_date=start_s, end_date=end_s)
    if df is None or df.empty:
        raise RuntimeError("tushare index_weight returned empty for 000852.SH")

    df = df[["con_code", "trade_date"]].dropna()
    df["con_code"] = df["con_code"].astype(str).map(_to_local_symbol)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["trade_date"]).sort_values("trade_date")
    if df.empty:
        raise RuntimeError("tushare index_weight has no usable trade_date rows")

    by_date: dict[dt.date, set[str]] = {}
    for tdate, g in df.groupby(df["trade_date"].dt.date):
        by_date[tdate] = set(g["con_code"].tolist())
    snap_dates = sorted(by_date.keys())
    if not snap_dates:
        raise RuntimeError("no snapshot dates built from tushare index_weight")

    snapshots: list[tuple[str, list[str]]] = []
    latest_set: set[str] | None = None
    i = 0
    for mend in month_ends:
        while i < len(snap_dates) and snap_dates[i] <= mend:
            latest_set = by_date[snap_dates[i]]
            i += 1
        if latest_set is None:
            continue
        snapshots.append((mend.isoformat(), sorted(latest_set)))
    if not snapshots:
        raise RuntimeError("no monthly snapshots produced from tushare data")
    return snapshots


def _build_with_akshare_static(month_ends: list[dt.date]) -> list[tuple[str, list[str]]]:
    import akshare as ak

    df = ak.index_stock_cons_csindex(symbol="000852")
    if df is None or df.empty:
        raise RuntimeError("akshare index_stock_cons_csindex('000852') returned empty")
    code_col = "成分券代码" if "成分券代码" in df.columns else df.columns[4]
    syms = sorted({_to_local_symbol(v) for v in df[code_col].tolist() if str(v).strip()})
    if not syms:
        raise RuntimeError("no symbols parsed from akshare CSI1000 constituents")
    return [(d.isoformat(), syms) for d in month_ends]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CSI1000 PIT by monthly snapshots")
    parser.add_argument("--start", default="2016-03-01")
    parser.add_argument("--end", default=dt.date.today().isoformat())
    parser.add_argument("--provider", choices=["auto", "tushare", "akshare_static"], default="auto")
    parser.add_argument("--token", default=os.environ.get("TUSHARE_TOKEN", ""))
    parser.add_argument("--out-dir", default="data_cache")
    args = parser.parse_args()

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    if start > end:
        raise ValueError("start > end")
    month_ends = _month_ends(start, end)
    if not month_ends:
        raise RuntimeError("empty month range")

    provider = args.provider
    snapshots: list[tuple[str, list[str]]]
    used: str
    if provider == "tushare":
        if not args.token:
            raise RuntimeError("provider=tushare requires --token or env TUSHARE_TOKEN")
        snapshots = _build_with_tushare(month_ends, args.token)
        used = "tushare"
    elif provider == "akshare_static":
        snapshots = _build_with_akshare_static(month_ends)
        used = "akshare_static"
    else:
        if args.token:
            snapshots = _build_with_tushare(month_ends, args.token)
            used = "tushare"
        else:
            snapshots = _build_with_akshare_static(month_ends)
            used = "akshare_static"

    first_dt = dt.date.fromisoformat(snapshots[0][0])
    if first_dt > start:
        snapshots.insert(0, (start.isoformat(), list(snapshots[0][1])))
    changes = _reconstruct_changes(snapshots, index_code="000852.SH")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshots_csv = out_dir / "csi1000_pit_monthly_snapshots.csv"
    changes_csv = out_dir / "csi1000_pit_monthly_changes.csv"
    snap_rows = _save_snapshots(snapshots_csv, snapshots)
    _save_changes(changes_csv, changes)

    active = sum(1 for r in changes if not r["out_date"])
    print(
        f"provider={used} months={len(snapshots)} snapshot_rows={snap_rows} "
        f"changes={len(changes)} active={active}"
    )
    print(f"snapshots_csv={snapshots_csv}")
    print(f"changes_csv={changes_csv}")
    if used == "akshare_static":
        print("warning=static_fallback_no_true_history (set TUSHARE_TOKEN for true monthly history)")


if __name__ == "__main__":
    main()
