"""Build approximate CSI800/000906 PIT records from monthly snapshots.

Primary source:
- Tushare `index_weight` (requires token), then reconstruct monthly snapshots.

Fallback source:
- AkShare latest CSI800 constituents replicated across months. This is low-fidelity
  and must only be used explicitly.

This script is kept only as a low-fidelity monthly approximation path.
Formal CSI800 PIT ingest should use `fetch_csi800_pit_history.py`.

Outputs:
- data_cache/csi800_pit_snapshots.csv
- data_cache/csi800_pit_changes.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
from pathlib import Path
from typing import Iterable


INDEX_CODE = "000906.SH"
DEFAULT_START = "2007-01-15"
ROOT = Path(__file__).resolve().parents[2]
EXPECTED_COUNT = 800


def _load_env_file() -> dict[str, str]:
    env_path = ROOT / ".env"
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _month_ends(start: dt.date, end: dt.date) -> list[dt.date]:
    cur = dt.date(start.year, start.month, 1)
    out: list[dt.date] = []
    while cur <= end:
        if cur.month == 12:
            nxt = dt.date(cur.year + 1, 1, 1)
        else:
            nxt = dt.date(cur.year, cur.month + 1, 1)
        month_end = nxt - dt.timedelta(days=1)
        if month_end >= start and month_end <= end:
            out.append(month_end)
        cur = nxt
    return out


def _to_local_symbol(code: str) -> str:
    text = str(code).strip()
    if not text:
        return text
    if "." in text:
        left, right = text.split(".", 1)
        if right.upper() in {"SH", "SZ"}:
            return f"{left.zfill(6)}.{right.upper()}"
    text = text.zfill(6)
    if text.startswith(("6", "9")):
        return f"{text}.SH"
    return f"{text}.SZ"


def _reconstruct_changes(
    snapshots: list[tuple[str, list[str]]],
    *,
    index_code: str,
) -> list[dict[str, str]]:
    active: dict[str, str] = {}
    changes: list[dict[str, str]] = []
    for date_str, symbols in snapshots:
        current = set(symbols)
        prev = set(active.keys())
        added = current - prev
        removed = prev - current
        for symbol in added:
            active[symbol] = date_str
        for symbol in removed:
            changes.append(
                {
                    "index_code": index_code,
                    "symbol": symbol,
                    "in_date": active[symbol],
                    "out_date": date_str,
                }
            )
            del active[symbol]
    for symbol, in_date in active.items():
        changes.append(
            {
                "index_code": index_code,
                "symbol": symbol,
                "in_date": in_date,
                "out_date": "",
            }
        )
    changes.sort(key=lambda row: (row["symbol"], row["in_date"]))
    return changes


def _save_snapshots(path: Path, snapshots: Iterable[tuple[str, list[str]]]) -> int:
    total = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "symbol"])
        for date_str, symbols in snapshots:
            for symbol in symbols:
                writer.writerow([date_str, symbol])
                total += 1
    return total


def _save_changes(path: Path, changes: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["index_code", "symbol", "in_date", "out_date"])
        writer.writeheader()
        writer.writerows(changes)


def _build_with_tushare(month_ends: list[dt.date], token: str) -> list[tuple[str, list[str]]]:
    import pandas as pd
    import tushare as ts

    ts.set_token(token)
    pro = ts.pro_api(token)

    start_s = month_ends[0].strftime("%Y%m%d")
    end_s = month_ends[-1].strftime("%Y%m%d")
    frame = pro.index_weight(index_code=INDEX_CODE, start_date=start_s, end_date=end_s)
    if frame is None or frame.empty:
        raise RuntimeError(f"tushare index_weight returned empty for {INDEX_CODE}")

    frame = frame[["con_code", "trade_date"]].dropna()
    frame["con_code"] = frame["con_code"].astype(str).map(_to_local_symbol)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], format="%Y%m%d", errors="coerce")
    frame = frame.dropna(subset=["trade_date"]).sort_values("trade_date")
    if frame.empty:
        raise RuntimeError(f"tushare index_weight has no usable trade_date rows for {INDEX_CODE}")

    by_date: dict[dt.date, set[str]] = {}
    for trade_date, group in frame.groupby(frame["trade_date"].dt.date):
        symbols = set(group["con_code"].tolist())
        if len(symbols) != EXPECTED_COUNT:
            continue
        by_date[trade_date] = symbols
    snapshot_dates = sorted(by_date.keys())
    if not snapshot_dates:
        raise RuntimeError(f"no exact-{EXPECTED_COUNT} snapshot dates built from tushare index_weight for {INDEX_CODE}")

    snapshots: list[tuple[str, list[str]]] = []
    latest_set: set[str] | None = None
    cursor = 0
    for month_end in month_ends:
        while cursor < len(snapshot_dates) and snapshot_dates[cursor] <= month_end:
            latest_set = by_date[snapshot_dates[cursor]]
            cursor += 1
        if latest_set is None:
            continue
        snapshots.append((month_end.isoformat(), sorted(latest_set)))
    if not snapshots:
        raise RuntimeError(f"no monthly snapshots produced from tushare data for {INDEX_CODE}")
    return snapshots


def _build_with_akshare_static(month_ends: list[dt.date]) -> list[tuple[str, list[str]]]:
    import akshare as ak

    frame = ak.index_stock_cons(symbol="000906")
    if frame is None or frame.empty:
        raise RuntimeError("akshare index_stock_cons('000906') returned empty")
    code_col = "品种代码" if "品种代码" in frame.columns else frame.columns[0]
    symbols = sorted({_to_local_symbol(value) for value in frame[code_col].tolist() if str(value).strip()})
    if not symbols:
        raise RuntimeError("no symbols parsed from akshare CSI800 constituents")
    return [(month_end.isoformat(), symbols) for month_end in month_ends]


def main() -> None:
    file_env = _load_env_file()
    parser = argparse.ArgumentParser(description="Build CSI800 PIT by monthly snapshots")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=dt.date.today().isoformat())
    parser.add_argument("--provider", choices=["auto", "tushare", "akshare_static"], default="auto")
    parser.add_argument("--token", default=os.environ.get("TUSHARE_TOKEN") or file_env.get("TUSHARE_TOKEN") or "")
    parser.add_argument("--out-dir", default="data_cache")
    args = parser.parse_args()

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    if start > end:
        raise ValueError("start > end")

    month_ends = _month_ends(start, end)
    if not month_ends:
        raise RuntimeError("empty month range")

    provider = str(args.provider or "auto").strip().lower()
    token = str(args.token or "").strip()
    if provider == "auto":
        if not token:
            raise RuntimeError("provider=auto requires TUSHARE_TOKEN for true CSI800 history; use --provider akshare_static only for low-fidelity fallback")
        snapshots = _build_with_tushare(month_ends, token)
        used_provider = "tushare"
    elif provider == "tushare":
        if not token:
            raise RuntimeError("provider=tushare requires --token or env TUSHARE_TOKEN")
        snapshots = _build_with_tushare(month_ends, token)
        used_provider = "tushare"
    else:
        snapshots = _build_with_akshare_static(month_ends)
        used_provider = "akshare_static"

    first_dt = dt.date.fromisoformat(snapshots[0][0])

    changes = _reconstruct_changes(snapshots, index_code=INDEX_CODE)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshots_csv = out_dir / "csi800_pit_snapshots.csv"
    changes_csv = out_dir / "csi800_pit_changes.csv"
    snapshot_rows = _save_snapshots(snapshots_csv, snapshots)
    _save_changes(changes_csv, changes)

    active = sum(1 for row in changes if not row["out_date"])
    print(
        f"provider={used_provider} months={len(snapshots)} snapshot_rows={snapshot_rows} "
        f"changes={len(changes)} active={active}"
    )
    if first_dt > start:
        print(
            "warning=history_gap "
            f"(requested_start={start.isoformat()} earliest_snapshot={first_dt.isoformat()})"
        )
    print(f"snapshots_csv={snapshots_csv}")
    print(f"changes_csv={changes_csv}")
    if used_provider == "akshare_static":
        print("warning=static_fallback_no_true_history (set TUSHARE_TOKEN for true monthly history)")


if __name__ == "__main__":
    main()
