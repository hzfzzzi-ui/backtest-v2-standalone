from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.data.pg_env import connect as pg_connect
from backend.core.data.pg_env import load_db_settings as load_shared_db_settings
from backend.core.data.pg_env import read_env_file as read_shared_env_file

DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "ops"
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"
DEFAULT_INDEX_CODE = "000906.SH"
RAW_FIELDS = "date,code,isST"
MAX_DATE = date(9999, 12, 31)


@dataclass(slots=True)
class DbSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _load_env_file() -> dict[str, str]:
    return read_shared_env_file(ROOT)


def _load_db_settings() -> DbSettings:
    settings = load_shared_db_settings(config_path=DEFAULT_CONFIG_PATH, root=ROOT)
    return DbSettings(settings.host, settings.port, settings.dbname, settings.user, settings.password)


def _connect():
    if psycopg is None:  # pragma: no cover
        raise RuntimeError("psycopg is required")
    return pg_connect(config_path=DEFAULT_CONFIG_PATH, root=ROOT, autocommit=False)


def _load_baostock():
    try:
        import baostock as bs
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("baostock is required") from exc
    return bs


def _ts_to_internal(symbol: str) -> str:
    text = str(symbol or "").strip()
    if "." in text:
        code, exch = text.split(".", 1)
        exch_u = exch.upper()
        if exch_u == "SH":
            return f"sh{code}"
        if exch_u == "SZ":
            return f"sz{code}"
        if exch_u == "BJ":
            return f"bj{code}"
    lower = text.lower()
    if lower.startswith(("sh", "sz", "bj")) and len(lower) == 8:
        return lower
    raise ValueError(f"unsupported symbol: {symbol}")


def _internal_to_ts(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    if text.startswith(("sh", "sz", "bj")) and len(text) == 8:
        return f"{text[2:]}.{text[:2].upper()}"
    if "." in text:
        code, exch = text.split(".", 1)
        return f"{code.upper()}.{exch.upper()}"
    raise ValueError(f"unsupported symbol: {symbol}")


def _internal_to_bs(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    if text.startswith(("sh", "sz", "bj")) and len(text) == 8:
        return f"{text[:2]}.{text[2:]}"
    if "." in text:
        code, exch = _internal_to_ts(text).split(".", 1)
        return f"{exch.lower()}.{code}"
    raise ValueError(f"unsupported symbol: {symbol}")


def _parse_symbol_list(raw: str) -> list[str]:
    tokens = [item.strip() for item in str(raw or "").replace(";", ",").split(",")]
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        if not token:
            continue
        normalized = _ts_to_internal(token)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _as_date_or_none(value: Any) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _load_target_symbols(index_code: str, start: date, end: date) -> list[str]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT symbol
                FROM public.pit_index_constituents
                WHERE index_code = %s
                  AND start_date <= %s
                  AND (end_date IS NULL OR end_date >= %s)
                ORDER BY symbol
                """,
                (index_code, end, start),
            )
            return [_ts_to_internal(str(row[0])) for row in cur.fetchall()]


def _fetch_st_intervals(bs: Any, symbol: str, start: date, end: date, created_at: datetime) -> pd.DataFrame:
    bs_code = _internal_to_bs(symbol)
    rs = bs.query_history_k_data_plus(
        bs_code,
        RAW_FIELDS,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        frequency="d",
        adjustflag="3",
    )
    raw = rs.get_data()
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type", "name_before", "name_after", "created_at"])

    raw["trade_date"] = pd.to_datetime(raw["date"], errors="coerce").dt.date
    raw["is_st"] = pd.to_numeric(raw.get("isST"), errors="coerce").fillna(0).astype(int).eq(1)
    raw = raw.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)

    rows: list[dict[str, Any]] = []
    active_start: date | None = None
    active_end: date | None = None
    ts_code = _internal_to_ts(symbol)
    for row in raw.itertuples(index=False):
        trade_day = row.trade_date
        if bool(row.is_st):
            if active_start is None:
                active_start = trade_day
            active_end = trade_day
            continue
        if active_start is not None and active_end is not None:
            rows.append(
                {
                    "ts_code": ts_code,
                    "start_date": active_start,
                    "end_date": active_end,
                    "st_type": "ST",
                    "name_before": None,
                    "name_after": None,
                    "created_at": created_at,
                }
            )
            active_start = None
            active_end = None
    if active_start is not None and active_end is not None:
        rows.append(
            {
                "ts_code": ts_code,
                "start_date": active_start,
                "end_date": active_end,
                "st_type": "ST",
                "name_before": None,
                "name_after": None,
                "created_at": created_at,
            }
        )
    return pd.DataFrame(rows, columns=["ts_code", "start_date", "end_date", "st_type", "name_before", "name_after", "created_at"])


def _load_existing_rows(ts_codes: list[str]) -> pd.DataFrame:
    if not ts_codes:
        return pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type", "name_before", "name_after", "created_at"])
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ts_code, start_date, end_date, st_type, name_before, name_after, created_at
                FROM public.pit_st_history
                WHERE ts_code = ANY(%s)
                ORDER BY ts_code, start_date, COALESCE(end_date, DATE '9999-12-31')
                """,
                (ts_codes,),
            )
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
    frame = pd.DataFrame(rows, columns=cols)
    if frame.empty:
        return pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type", "name_before", "name_after", "created_at"])
    for col in ["start_date", "end_date"]:
        frame[col] = frame[col].map(_as_date_or_none)
    return frame


def _trim_existing_rows(existing: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if existing.empty:
        return existing.copy()
    kept: list[dict[str, Any]] = []
    for row in existing.to_dict("records"):
        row_start = _as_date_or_none(row["start_date"])
        row_end = _as_date_or_none(row["end_date"])
        if row_start is None:
            continue
        row["start_date"] = row_start
        row["end_date"] = row_end
        row_end_cmp = row_end or MAX_DATE
        if row_end_cmp < start or row_start > end:
            kept.append(dict(row))
            continue
        if row_start < start:
            left = dict(row)
            left["end_date"] = start - timedelta(days=1)
            if left["end_date"] >= left["start_date"]:
                kept.append(left)
        if row_end is None or row_end > end:
            right = dict(row)
            right["start_date"] = end + timedelta(days=1)
            if row_end is None or right["start_date"] <= row_end:
                kept.append(right)
    return pd.DataFrame(kept, columns=existing.columns)


def _row_signature(row: dict[str, Any]) -> tuple[str, str | None, str | None]:
    return (
        str(row.get("st_type") or "ST"),
        None if pd.isna(row.get("name_before")) else str(row.get("name_before") or None),
        None if pd.isna(row.get("name_after")) else str(row.get("name_after") or None),
    )


def _normalize_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type", "name_before", "name_after", "created_at"])
    ordered = frame.copy()
    ordered["start_date"] = ordered["start_date"].map(_as_date_or_none)
    ordered["end_date"] = ordered["end_date"].map(_as_date_or_none)
    ordered["sort_end"] = ordered["end_date"].apply(lambda value: value if value is not None else MAX_DATE)
    ordered = ordered.sort_values(["ts_code", "start_date", "sort_end", "st_type"]).drop(columns=["sort_end"])

    out_rows: list[dict[str, Any]] = []
    for ts_code, group in ordered.groupby("ts_code", sort=False):
        merged: list[dict[str, Any]] = []
        for raw_row in group.to_dict("records"):
            row = dict(raw_row)
            row["st_type"] = str(row.get("st_type") or "ST")
            prev_handled = False
            while merged:
                prev = merged[-1]
                prev_end = prev["end_date"] or MAX_DATE
                row_end = row["end_date"] or MAX_DATE
                same_signature = _row_signature(prev) == _row_signature(row)
                if same_signature and row["start_date"] <= prev_end + timedelta(days=1):
                    prev["end_date"] = None if prev["end_date"] is None or row["end_date"] is None else max(prev["end_date"], row["end_date"])
                    prev_handled = True
                    break
                if row["start_date"] <= prev_end:
                    new_prev_end = row["start_date"] - timedelta(days=1)
                    if new_prev_end < prev["start_date"]:
                        merged.pop()
                        continue
                    prev["end_date"] = new_prev_end
                break
            if prev_handled:
                continue
            if row["end_date"] is not None and row["end_date"] < row["start_date"]:
                continue
            merged.append(row)
        out_rows.extend(merged)

    normalized = pd.DataFrame(out_rows, columns=["ts_code", "start_date", "end_date", "st_type", "name_before", "name_after", "created_at"])
    if normalized.empty:
        return normalized
    return normalized.sort_values(["ts_code", "start_date", "end_date"], na_position="last").reset_index(drop=True)


def _replace_rows(ts_codes: list[str], frame: pd.DataFrame, apply: bool) -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '1200000ms'")
            cur.execute("DELETE FROM public.pit_st_history WHERE ts_code = ANY(%s)", (ts_codes,))
            rows = [
                (
                    str(row.ts_code),
                    row.start_date,
                    row.end_date,
                    str(row.st_type or "ST"),
                    None if pd.isna(row.name_before) else row.name_before,
                    None if pd.isna(row.name_after) else row.name_after,
                    row.created_at,
                )
                for row in frame.itertuples(index=False)
            ]
            if rows:
                cur.executemany(
                    """
                    INSERT INTO public.pit_st_history (
                        ts_code,
                        start_date,
                        end_date,
                        st_type,
                        name_before,
                        name_after,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
            if apply:
                conn.commit()
            else:
                conn.rollback()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_backfill(args: argparse.Namespace) -> dict[str, Any]:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise ValueError("start must be <= end")

    explicit_symbols = _parse_symbol_list(args.symbols)
    target_symbols = explicit_symbols or _load_target_symbols(str(args.index_code), start, end)
    symbol_offset = max(int(args.symbol_offset), 0)
    if symbol_offset > 0:
        target_symbols = target_symbols[symbol_offset:]
    max_symbols = max(int(args.max_symbols), 0)
    if max_symbols > 0:
        target_symbols = target_symbols[:max_symbols]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"csi800_st_baostock_backfill_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now(timezone.utc)
    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "index_code": str(args.index_code),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "explicit_symbols": [_internal_to_ts(symbol) for symbol in explicit_symbols],
        "target_symbol_count": int(len(target_symbols)),
        "successful_symbol_count": 0,
        "failed_symbols": [],
        "rebuilt_interval_rows": 0,
        "existing_rows_loaded": 0,
        "final_rows": 0,
    }

    bs = _load_baostock()
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login.error_msg}")

    rebuilt_frames: list[pd.DataFrame] = []
    successful_symbols: list[str] = []
    try:
        for idx, symbol in enumerate(target_symbols, start=1):
            try:
                rebuilt = _fetch_st_intervals(bs, symbol, start, end, created_at)
                rebuilt_frames.append(rebuilt)
                successful_symbols.append(symbol)
            except Exception as exc:
                summary["failed_symbols"].append({"symbol": _internal_to_ts(symbol), "error": str(exc)})
            if idx % 50 == 0:
                print(f"[st] {idx}/{len(target_symbols)} symbols fetched")
            time.sleep(float(args.sleep_seconds))
    finally:
        bs.logout()

    successful_ts_codes = [_internal_to_ts(symbol) for symbol in successful_symbols]
    rebuilt = (
        pd.concat(rebuilt_frames, ignore_index=True)
        if rebuilt_frames
        else pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type", "name_before", "name_after", "created_at"])
    )
    rebuilt = rebuilt.sort_values(["ts_code", "start_date", "end_date"], na_position="last").reset_index(drop=True)
    summary["successful_symbol_count"] = int(len(successful_symbols))
    summary["rebuilt_interval_rows"] = int(len(rebuilt))

    existing = _load_existing_rows(successful_ts_codes)
    summary["existing_rows_loaded"] = int(len(existing))
    backup_path = output_dir / "existing_rows_backup.csv"
    existing.to_csv(backup_path, index=False)
    summary["existing_rows_backup_csv"] = str(backup_path)

    kept_existing = _trim_existing_rows(existing, start, end)
    final_frame = _normalize_rows(pd.concat([kept_existing, rebuilt], ignore_index=True))
    summary["final_rows"] = int(len(final_frame))

    sample_path = output_dir / "rebuilt_intervals_sample.csv"
    final_frame.head(1000).to_csv(sample_path, index=False)
    summary["sample_csv"] = str(sample_path)

    if successful_ts_codes:
        _replace_rows(successful_ts_codes, final_frame, bool(args.apply))
    else:
        summary["status"] = "no_successful_symbols"

    if not args.apply and summary["status"] == "ok":
        summary["status"] = "dry_run"
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild CSI800 pit_st_history intervals via baostock daily isST")
    parser.add_argument("--start", required=True, help="inclusive start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="inclusive end date YYYY-MM-DD")
    parser.add_argument("--index-code", default=DEFAULT_INDEX_CODE)
    parser.add_argument("--symbols", default="", help="optional comma-separated symbols in TS/internal format")
    parser.add_argument("--symbol-offset", type=int, default=0, help="skip this many symbols before rebuild")
    parser.add_argument("--max-symbols", type=int, default=0, help="optional symbol cap for smoke tests; 0 means all symbols")
    parser.add_argument("--sleep-seconds", type=float, default=0.01, help="sleep between baostock requests")
    parser.add_argument("--output-dir", default="", help="output directory for summary/sample artifacts")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_backfill(args)
    output_dir = Path(summary["sample_csv"]).parent if summary.get("sample_csv") else Path(args.output_dir or DEFAULT_OUTPUT_ROOT)
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
