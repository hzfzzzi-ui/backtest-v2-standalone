"""Build formal CSI800/000906 PIT history from Tushare trade_date snapshots.

This script is the formal CSI800 ingest path. It rebuilds constituent history
from actual `index_weight` trade dates instead of month-end approximation.

Outputs:
- data_cache/csi800_pit_history_snapshots.csv
- data_cache/csi800_pit_history_changes.csv
- data_cache/csi800_pit_history_fetch_summary.json
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Iterable


INDEX_CODE = "000906.SH"
DEFAULT_START = "2007-01-15"
ROOT = Path(__file__).resolve().parents[2]
EXPECTED_COUNT = 800
FORMAL_SOURCE = "tushare_csi800_history"


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


def _resolve_tushare_token(explicit: str | None = None) -> str:
    file_env = _load_env_file()
    return str(explicit or os.environ.get("TUSHARE_TOKEN") or file_env.get("TUSHARE_TOKEN") or "").strip()


def _to_local_symbol(code: str) -> str:
    text = str(code or "").strip().upper()
    if not text or text in {"NAN", "NONE"}:
        return ""
    if "." in text:
        left, right = text.split(".", 1)
        if right in {"SH", "SZ"}:
            return f"{left.zfill(6)}.{right}"
        if left in {"SH", "SZ"}:
            return f"{right.zfill(6)}.{left}"
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) != 6:
        return ""
    if digits.startswith(("6", "9")):
        return f"{digits}.SH"
    return f"{digits}.SZ"


def _load_tushare_history(
    *,
    start: dt.date,
    end: dt.date,
    token: str,
):
    import pandas as pd
    import tushare as ts

    ts.set_token(token)
    pro = ts.pro_api(token)
    frame = pro.index_weight(
        index_code=INDEX_CODE,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    if frame is None or frame.empty:
        raise RuntimeError(f"tushare index_weight returned empty for {INDEX_CODE}")

    usable = frame[["con_code", "trade_date"]].dropna().copy()
    usable["trade_date"] = pd.to_datetime(usable["trade_date"], format="%Y%m%d", errors="coerce")
    usable["symbol"] = usable["con_code"].astype(str).map(_to_local_symbol)
    usable = usable.dropna(subset=["trade_date"])
    usable = usable[usable["symbol"].astype(str) != ""]
    usable = usable.sort_values("trade_date").reset_index(drop=True)
    if usable.empty:
        raise RuntimeError(f"tushare index_weight has no usable trade_date rows for {INDEX_CODE}")
    return usable


def build_trade_date_snapshots(
    frame,
    *,
    expected_count: int = EXPECTED_COUNT,
) -> tuple[list[tuple[str, list[str]]], list[str], list[dict[str, Any]]]:
    usable_by_date: dict[dt.date, list[str]] = {}
    skipped_dates: list[dict[str, Any]] = []
    for trade_date, group in frame.groupby(frame["trade_date"].dt.date):
        symbols = sorted(set(group["symbol"].astype(str).tolist()))
        if len(symbols) != int(expected_count):
            skipped_dates.append({"trade_date": trade_date.isoformat(), "count": len(symbols)})
            continue
        usable_by_date[trade_date] = symbols

    usable_dates = sorted(usable_by_date.keys())
    if not usable_dates:
        raise RuntimeError(f"no exact-{int(expected_count)} trade_date snapshots built from tushare for {INDEX_CODE}")

    snapshots: list[tuple[str, list[str]]] = []
    previous: tuple[str, ...] | None = None
    for trade_date in usable_dates:
        symbols = tuple(usable_by_date[trade_date])
        if previous is None or symbols != previous:
            snapshots.append((trade_date.isoformat(), list(symbols)))
        previous = symbols

    return snapshots, [value.isoformat() for value in usable_dates], skipped_dates


def reconstruct_changes(
    snapshots: list[tuple[str, list[str]]],
    *,
    index_code: str = INDEX_CODE,
    source_label: str = FORMAL_SOURCE,
) -> list[dict[str, str]]:
    active: dict[str, dict[str, str]] = {}
    changes: list[dict[str, str]] = []
    for date_str, symbols in snapshots:
        current = set(symbols)
        previous = set(active.keys())
        added = current - previous
        removed = previous - current
        for symbol in added:
            active[symbol] = {"in_date": date_str, "source": source_label}
        for symbol in removed:
            entry = active[symbol]
            changes.append(
                {
                    "index_code": index_code,
                    "symbol": symbol,
                    "in_date": entry["in_date"],
                    "out_date": date_str,
                    "source": entry["source"],
                }
            )
            del active[symbol]
    for symbol, entry in active.items():
        changes.append(
            {
                "index_code": index_code,
                "symbol": symbol,
                "in_date": entry["in_date"],
                "out_date": "",
                "source": entry["source"],
            }
        )
    changes.sort(key=lambda row: (row["symbol"], row["in_date"]))
    return changes


def _save_snapshots(
    path: Path,
    snapshots: Iterable[tuple[str, list[str]]],
    *,
    source_label: str,
) -> int:
    rows = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["trade_date", "symbol", "source"])
        for trade_date, symbols in snapshots:
            for symbol in symbols:
                writer.writerow([trade_date, symbol, source_label])
                rows += 1
    return rows


def _save_changes(path: Path, changes: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["index_code", "symbol", "in_date", "out_date", "source"])
        writer.writeheader()
        writer.writerows(changes)


def _build_summary(
    *,
    start: dt.date,
    end: dt.date,
    source_label: str,
    usable_trade_dates: list[str],
    skipped_trade_dates: list[dict[str, Any]],
    snapshots: list[tuple[str, list[str]]],
    snapshot_rows: int,
    changes: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "status": "ok",
        "index_code": INDEX_CODE,
        "source_label": source_label,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "usable_trade_dates": int(len(usable_trade_dates)),
        "snapshot_dates": int(len(snapshots)),
        "snapshot_rows": int(snapshot_rows),
        "changes_rows": int(len(changes)),
        "open_rows": int(sum(1 for row in changes if not row["out_date"])),
        "closed_rows": int(sum(1 for row in changes if row["out_date"])),
        "first_usable_trade_date": usable_trade_dates[0] if usable_trade_dates else None,
        "last_usable_trade_date": usable_trade_dates[-1] if usable_trade_dates else None,
        "first_change_date": snapshots[0][0] if snapshots else None,
        "last_change_date": snapshots[-1][0] if snapshots else None,
        "skipped_trade_dates": int(len(skipped_trade_dates)),
        "skipped_trade_date_samples": skipped_trade_dates[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build formal CSI800 PIT history from Tushare trade_date snapshots")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=dt.date.today().isoformat())
    parser.add_argument("--token", default="")
    parser.add_argument("--out-dir", default="data_cache")
    parser.add_argument("--summary-out", default="")
    parser.add_argument("--expected-count", type=int, default=EXPECTED_COUNT)
    args = parser.parse_args()

    start = dt.date.fromisoformat(str(args.start))
    end = dt.date.fromisoformat(str(args.end))
    if start > end:
        raise ValueError("start > end")

    token = _resolve_tushare_token(str(args.token or ""))
    if not token:
        raise RuntimeError("formal CSI800 Tushare history requires TUSHARE_TOKEN")

    frame = _load_tushare_history(start=start, end=end, token=token)
    snapshots, usable_trade_dates, skipped_trade_dates = build_trade_date_snapshots(
        frame,
        expected_count=int(args.expected_count),
    )
    changes = reconstruct_changes(snapshots)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshots_csv = out_dir / "csi800_pit_history_snapshots.csv"
    changes_csv = out_dir / "csi800_pit_history_changes.csv"
    summary_out = Path(args.summary_out).resolve() if str(args.summary_out or "").strip() else (
        out_dir / "csi800_pit_history_fetch_summary.json"
    )

    snapshot_rows = _save_snapshots(snapshots_csv, snapshots, source_label=FORMAL_SOURCE)
    _save_changes(changes_csv, changes)
    summary = _build_summary(
        start=start,
        end=end,
        source_label=FORMAL_SOURCE,
        usable_trade_dates=usable_trade_dates,
        skipped_trade_dates=skipped_trade_dates,
        snapshots=snapshots,
        snapshot_rows=snapshot_rows,
        changes=changes,
    )
    summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({**summary, "snapshots_csv": str(snapshots_csv), "changes_csv": str(changes_csv)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
