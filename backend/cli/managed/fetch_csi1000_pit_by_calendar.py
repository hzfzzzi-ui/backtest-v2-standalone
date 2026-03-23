from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from backend.cli.managed.csi1000_rebalance_calendar import (
    DEFAULT_CALENDAR_PATH,
    RebalanceCalendarEntry,
    load_rebalance_calendar,
    validate_rebalance_calendar,
)
from backend.scripts.build_csi1000_pit_from_manual_snapshots import (
    SnapshotSpec,
    reconstruct_changes,
    save_changes,
    save_flat_snapshots,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
INDEX_CODE = "000852.SH"
DEFAULT_TUSHARE_SOURCE = "tushare_csi1000_calendar"
DEFAULT_STATIC_FALLBACK_SOURCE = "akshare_csi1000_static_fallback"
DEFAULT_LOOKAHEAD_DAYS = 10
CSI1000_CODE_COLUMNS = (
    "\u6210\u5206\u5238\u4ee3\u7801",
    "\u6210\u5206\u80a1\u4ee3\u7801",
    "\u6210\u5206\u4ee3\u7801",
    "code",
    "symbol",
)

_STATIC_CACHE: list[str] | None = None


def _load_env_file() -> dict[str, str]:
    env_path = REPO_ROOT / ".env"
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
    if not text:
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


def _fetch_tushare_snapshot(
    effective_date: str,
    *,
    token: str,
    lookahead_days: int = DEFAULT_LOOKAHEAD_DAYS,
) -> tuple[list[str], str]:
    import pandas as pd
    import tushare as ts

    start = dt.date.fromisoformat(effective_date)
    end = start + dt.timedelta(days=int(lookahead_days))
    ts.set_token(token)
    pro = ts.pro_api(token)
    df = pro.index_weight(
        index_code=INDEX_CODE,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    if df is None or df.empty:
        raise RuntimeError(f"tushare index_weight returned empty for effective_date={effective_date}")

    if "con_code" not in df.columns or "trade_date" not in df.columns:
        raise RuntimeError(f"tushare index_weight missing expected columns for effective_date={effective_date}")

    usable = df[["con_code", "trade_date"]].dropna().copy()
    usable["trade_date"] = pd.to_datetime(usable["trade_date"], format="%Y%m%d", errors="coerce")
    usable["symbol"] = usable["con_code"].astype(str).map(_to_local_symbol)
    usable = usable.dropna(subset=["trade_date"])
    usable = usable[usable["symbol"].astype(str) != ""]
    if usable.empty:
        raise RuntimeError(f"tushare index_weight had no usable rows for effective_date={effective_date}")

    usable["trade_date_key"] = usable["trade_date"].dt.date
    eligible_dates = sorted({trade_date for trade_date in usable["trade_date_key"].tolist() if trade_date >= start})
    if not eligible_dates:
        raise RuntimeError(f"no tushare trade_date on or after effective_date={effective_date}")
    snapshot_date = eligible_dates[0]
    snapshot = usable.loc[usable["trade_date_key"] == snapshot_date, "symbol"].dropna().astype(str)
    symbols = sorted(set(snapshot.tolist()))
    if not symbols:
        raise RuntimeError(f"no symbols parsed from tushare index_weight for effective_date={effective_date}")
    return symbols, snapshot_date.isoformat()


def _fetch_akshare_static_snapshot() -> list[str]:
    global _STATIC_CACHE
    if _STATIC_CACHE is not None:
        return list(_STATIC_CACHE)

    import akshare as ak

    df = ak.index_stock_cons_csindex(symbol="000852")
    if df is None or df.empty:
        raise RuntimeError("akshare index_stock_cons_csindex('000852') returned empty")

    code_col = None
    for name in CSI1000_CODE_COLUMNS:
        for col in df.columns:
            text = str(col).strip()
            if text == name or text.lower() == name.lower():
                code_col = col
                break
        if code_col is not None:
            break
    if code_col is None:
        candidate_cols = [
            col
            for col in df.columns
            if "\u6210\u5206" in str(col) and "\u4ee3\u7801" in str(col)
        ]
        code_col = candidate_cols[0] if candidate_cols else str(df.columns[4])

    symbols = sorted({_to_local_symbol(value) for value in df[code_col].tolist() if _to_local_symbol(value)})
    if not symbols:
        raise RuntimeError("no symbols parsed from akshare CSI1000 constituents")
    _STATIC_CACHE = list(symbols)
    return symbols


def _assert_constituent_count(
    symbols: list[str],
    *,
    effective_date: str,
    expected_count: int,
    strict_count: bool,
) -> None:
    if len(symbols) == int(expected_count):
        return
    message = (
        f"snapshot count mismatch at effective_date={effective_date}: "
        f"expected={int(expected_count)} actual={len(symbols)}"
    )
    if strict_count:
        raise RuntimeError(message)


def build_calendar_snapshots(
    entries: list[RebalanceCalendarEntry],
    *,
    provider: str,
    token: str,
    allow_static_fallback: bool,
    expected_count: int = 1000,
    strict_count: bool = True,
    lookahead_days: int = DEFAULT_LOOKAHEAD_DAYS,
) -> tuple[list[tuple[SnapshotSpec, list[str]]], dict[str, Any]]:
    snapshots: list[tuple[SnapshotSpec, list[str]]] = []
    provider_counts: dict[str, int] = {}
    fallback_dates: list[str] = []
    snapshot_trade_dates: dict[str, str] = {}

    for entry in entries:
        used_source = DEFAULT_TUSHARE_SOURCE
        source_note = entry.source_note
        symbols: list[str]
        if provider == "akshare_static":
            symbols = _fetch_akshare_static_snapshot()
            used_source = DEFAULT_STATIC_FALLBACK_SOURCE
        else:
            try:
                symbols, snapshot_trade_date = _fetch_tushare_snapshot(
                    entry.effective_date,
                    token=token,
                    lookahead_days=lookahead_days,
                )
                snapshot_trade_dates[entry.effective_date] = snapshot_trade_date
                if source_note:
                    source_note = f"{source_note}; snapshot_trade_date={snapshot_trade_date}"
                else:
                    source_note = f"snapshot_trade_date={snapshot_trade_date}"
            except Exception as exc:
                if not allow_static_fallback:
                    raise RuntimeError(
                        f"failed to fetch CSI1000 snapshot for effective_date={entry.effective_date}: {exc}"
                    ) from exc
                symbols = _fetch_akshare_static_snapshot()
                used_source = DEFAULT_STATIC_FALLBACK_SOURCE
                fallback_dates.append(entry.effective_date)
                fallback_note = f"static_fallback_reason={type(exc).__name__}: {exc}"
                if source_note:
                    source_note = f"{source_note}; {fallback_note}"
                else:
                    source_note = fallback_note

        symbols = sorted(set(symbols))
        _assert_constituent_count(
            symbols,
            effective_date=entry.effective_date,
            expected_count=expected_count,
            strict_count=strict_count,
        )
        provider_counts[used_source] = int(provider_counts.get(used_source, 0)) + 1
        snapshots.append(
            (
                SnapshotSpec(
                    effective_date=entry.effective_date,
                    snapshot_path=Path(f"{entry.effective_date}.generated.csv"),
                    source=used_source,
                    event_type=entry.event_type,
                    version=entry.version,
                    snapshot_trade_date=snapshot_trade_dates.get(entry.effective_date, ""),
                    rebalance_calendar_source=entry.source,
                    rebalance_calendar_generated_at=entry.generated_at,
                    source_url=entry.source_url,
                    source_note=source_note,
                ),
                symbols,
            )
        )

    return snapshots, {
        "event_count": len(entries),
        "snapshot_count": len(snapshots),
        "provider_counts": provider_counts,
        "fallback_event_count": len(fallback_dates),
        "fallback_effective_dates": fallback_dates,
        "snapshot_trade_dates": snapshot_trade_dates,
        "provider_floor_date": (
            min(snapshot_trade_dates.values())
            if snapshot_trade_dates
            else None
        ),
        "calendar_version": (
            entries[0].version if entries and len({entry.version for entry in entries}) == 1 else "mixed"
        ),
        "calendar_source": (
            entries[0].source if entries and len({entry.source for entry in entries}) == 1 else "mixed"
        ),
        "calendar_generated_at": (
            entries[0].generated_at if entries and len({entry.generated_at for entry in entries}) == 1 else "mixed"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CSI1000 PIT snapshots and changes from rebalance calendar")
    parser.add_argument("--calendar", default=str(DEFAULT_CALENDAR_PATH), help="rebalance calendar csv path")
    parser.add_argument("--provider", choices=["auto", "tushare", "akshare_static"], default="auto")
    parser.add_argument("--token", default="", help="tushare token; defaults to env TUSHARE_TOKEN or repo .env")
    parser.add_argument("--out-dir", default="data_cache", help="output directory")
    parser.add_argument("--summary-out", default="", help="optional summary json path")
    parser.add_argument("--expected-count", type=int, default=1000, help="expected constituent count per snapshot")
    parser.add_argument(
        "--allow-count-mismatch",
        action="store_true",
        help="allow snapshots with constituent count != expected-count",
    )
    parser.add_argument(
        "--allow-static-fallback",
        action="store_true",
        help="allow akshare static fallback when tushare snapshot fetch fails",
    )
    parser.add_argument(
        "--lookahead-days",
        type=int,
        default=DEFAULT_LOOKAHEAD_DAYS,
        help="days to look ahead when matching effective_date to tushare trade_date",
    )
    args = parser.parse_args()

    calendar_path = Path(args.calendar).resolve()
    entries = load_rebalance_calendar(calendar_path)
    validation = validate_rebalance_calendar(entries)

    token = _resolve_tushare_token(args.token)
    provider = args.provider
    if provider == "auto":
        provider = "tushare" if token else "akshare_static"
    if provider == "tushare" and not token:
        raise RuntimeError("provider=tushare requires --token, env TUSHARE_TOKEN, or repo .env TUSHARE_TOKEN")
    if provider == "akshare_static" and not args.allow_static_fallback:
        raise RuntimeError(
            "provider=akshare_static is low fidelity; pass --allow-static-fallback only for explicit fallback rebuilds"
        )

    snapshots, build_summary = build_calendar_snapshots(
        entries,
        provider=provider,
        token=token,
        allow_static_fallback=bool(args.allow_static_fallback),
        expected_count=int(args.expected_count),
        strict_count=not bool(args.allow_count_mismatch),
        lookahead_days=int(args.lookahead_days),
    )
    changes = reconstruct_changes(snapshots, index_code=INDEX_CODE)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshots_csv = out_dir / "csi1000_pit_calendar_snapshots.csv"
    changes_csv = out_dir / "csi1000_pit_calendar_changes.csv"
    summary_path = Path(args.summary_out).resolve() if args.summary_out else out_dir / "csi1000_pit_calendar_summary.json"

    snapshot_rows = save_flat_snapshots(snapshots_csv, snapshots)
    save_changes(changes_csv, changes)
    summary_payload = {
        "index_code": INDEX_CODE,
        "calendar_path": str(calendar_path),
        "provider": provider,
        "allow_static_fallback": bool(args.allow_static_fallback),
        "expected_count": int(args.expected_count),
        "strict_count": not bool(args.allow_count_mismatch),
        "snapshot_rows": int(snapshot_rows),
        "change_rows": int(len(changes)),
        "open_rows": int(sum(1 for row in changes if not row["out_date"])),
        "closed_rows": int(sum(1 for row in changes if row["out_date"])),
        "validation": validation,
        "build": build_summary,
        "outputs": {
            "snapshots_csv": str(snapshots_csv),
            "changes_csv": str(changes_csv),
        },
    }
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"provider={provider} events={len(entries)} snapshot_rows={snapshot_rows} "
        f"change_rows={len(changes)} fallback_events={build_summary['fallback_event_count']}"
    )
    print(f"snapshots_csv={snapshots_csv}")
    print(f"changes_csv={changes_csv}")
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
