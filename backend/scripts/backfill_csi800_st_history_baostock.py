from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
DEFAULT_START = "2007-01-04"
DEFAULT_END = "2010-01-03"
ST_FIELDS = "date,code,tradestatus,isST"


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetchall(cur, sql: str, params: tuple[Any, ...] = ()) -> tuple[list[tuple[Any, ...]], list[str]]:
    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = [d.name for d in cur.description] if cur.description else []
    return rows, cols


def _fetchdf(cur, sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    rows, cols = _fetchall(cur, sql, params)
    return pd.DataFrame(rows, columns=cols)


def _normalize_ts_symbol(symbol: str) -> str:
    text = str(symbol or "").strip()
    if not text:
        raise ValueError("empty symbol")
    if "." in text:
        code, exch = text.split(".", 1)
        return f"{code.upper()}.{exch.upper()}"
    lower = text.lower()
    if lower.startswith(("sh", "sz", "bj")) and len(lower) == 8:
        return f"{lower[2:].upper()}.{lower[:2].upper()}"
    raise ValueError(f"unsupported symbol: {symbol}")


def _ts_to_bs(symbol: str) -> str:
    ts_symbol = _normalize_ts_symbol(symbol)
    code, exch = ts_symbol.split(".", 1)
    return f"{exch.lower()}.{code}"


def _parse_symbol_list(raw: str) -> list[str]:
    tokens = [item.strip() for item in str(raw or "").replace(";", ",").split(",")]
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        if not token:
            continue
        normalized = _normalize_ts_symbol(token)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _load_target_symbols(index_code: str, start: date, end: date, explicit_symbols: list[str]) -> list[str]:
    if explicit_symbols:
        return explicit_symbols
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT symbol
                FROM public.pit_index_constituents
                WHERE index_code = %s
                  AND start_date <= %s
                  AND (end_date IS NULL OR end_date > %s)
                ORDER BY symbol
                """,
                (index_code, end, start),
            )
            return [str(row[0]).strip().upper() for row in cur.fetchall()]


def _load_all_csi_symbols(index_code: str) -> list[str]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT symbol
                FROM public.pit_index_constituents
                WHERE index_code = %s
                ORDER BY symbol
                """,
                (index_code,),
            )
            return [str(row[0]).strip().upper() for row in cur.fetchall()]


def _load_baostock():
    try:
        import baostock as bs
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("baostock is required") from exc
    return bs


def _fetch_st_daily(bs: Any, ts_symbol: str, start: date, end: date) -> pd.DataFrame:
    rs = bs.query_history_k_data_plus(
        _ts_to_bs(ts_symbol),
        ST_FIELDS,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        frequency="d",
        adjustflag="3",
    )
    if rs.error_code != "0":
        raise RuntimeError(f"baostock query failed: {rs.error_code} {rs.error_msg}")
    frame = rs.get_data()
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["trade_date", "is_st"])
    frame["trade_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    frame["is_st"] = pd.to_numeric(frame.get("isST"), errors="coerce").fillna(0).astype(int).eq(1)
    frame = frame.dropna(subset=["trade_date"]).drop_duplicates(subset=["trade_date"], keep="last")
    return frame[["trade_date", "is_st"]].sort_values("trade_date").reset_index(drop=True)


def _is_login_error(exc: Exception) -> bool:
    text = str(exc)
    return "10001001" in text or "用户未登录" in text


def _build_intervals(ts_symbol: str, daily: pd.DataFrame) -> list[tuple[Any, ...]]:
    if daily.empty:
        return []
    rows: list[tuple[Any, ...]] = []
    active_start: date | None = None
    prev_is_st = False
    prev_trade_date: date | None = None
    for row in daily.itertuples(index=False):
        current_is_st = bool(row.is_st)
        current_date = row.trade_date
        if current_is_st and not prev_is_st:
            active_start = current_date
        if prev_is_st and not current_is_st and active_start is not None and prev_trade_date is not None:
            rows.append((ts_symbol, active_start, prev_trade_date, "ST", None, None))
            active_start = None
        prev_is_st = current_is_st
        prev_trade_date = current_date
    if prev_is_st and active_start is not None and prev_trade_date is not None:
        rows.append((ts_symbol, active_start, prev_trade_date, "ST", None, None))
    return rows


def _load_symbol_rows(cur, table: str, values: list[str]) -> None:
    cur.execute(f"TRUNCATE TABLE {table}")
    if not values:
        return
    cur.executemany(f"INSERT INTO {table} (ts_code) VALUES (%s)", [(item,) for item in values])


def _load_interval_rows(cur, table: str, rows: list[tuple[Any, ...]]) -> None:
    cur.execute(f"TRUNCATE TABLE {table}")
    if not rows:
        return
    cur.executemany(
        f"""
        INSERT INTO {table} (
            ts_code,
            start_date,
            end_date,
            st_type,
            name_before,
            name_after
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        rows,
    )


def _init_temp_tables(cur) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS tmp_csi800_st_symbols (
            ts_code text PRIMARY KEY
        ) ON COMMIT DROP
        """
    )
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS tmp_csi800_st_intervals (
            ts_code text NOT NULL,
            start_date date NOT NULL,
            end_date date,
            st_type text NOT NULL,
            name_before text,
            name_after text
        ) ON COMMIT DROP
        """
    )


def _preserve_boundary_rows(existing: pd.DataFrame, start: date, end: date) -> list[tuple[Any, ...]]:
    preserved: list[tuple[Any, ...]] = []
    start_cut = start - timedelta(days=1)
    end_cut = end + timedelta(days=1)
    for row in existing.itertuples(index=False):
        row_end = None if pd.isna(row.end_date) else row.end_date
        if row.start_date < start and (row_end is None or row_end >= start):
            if start_cut >= row.start_date:
                preserved.append((row.ts_code, row.start_date, start_cut, row.st_type, row.name_before, row.name_after))
        if row_end is None or row_end > end:
            if row_end is None or row_end >= end_cut:
                preserved.append((row.ts_code, end_cut, row_end, row.st_type, row.name_before, row.name_after))
    return preserved


def _query_overlap_rows(cur, symbols: list[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type", "prev_end"])
    cur.execute("TRUNCATE TABLE tmp_csi800_st_symbols")
    _load_symbol_rows(cur, "tmp_csi800_st_symbols", symbols)
    return _fetchdf(
        cur,
        """
        WITH ordered AS (
            SELECT
                ts_code,
                start_date,
                end_date,
                st_type,
                LAG(COALESCE(end_date, DATE '9999-12-31')) OVER (
                    PARTITION BY ts_code
                    ORDER BY start_date, COALESCE(end_date, DATE '9999-12-31')
                ) AS prev_end
            FROM public.pit_st_history
            WHERE ts_code IN (SELECT ts_code FROM tmp_csi800_st_symbols)
        )
        SELECT ts_code, start_date, end_date, st_type, prev_end
        FROM ordered
        WHERE prev_end IS NOT NULL
          AND start_date <= prev_end
        ORDER BY ts_code, start_date
        """,
    )


def run_backfill(args: argparse.Namespace) -> dict[str, Any]:
    start = date.fromisoformat(str(args.start))
    end = date.fromisoformat(str(args.end))
    if start > end:
        raise ValueError("start must be <= end")

    explicit_symbols = _parse_symbol_list(str(args.symbols or ""))
    target_symbols = _load_target_symbols(str(args.index_code), start, end, explicit_symbols)
    overlap_fix_symbols = _load_all_csi_symbols(str(args.index_code)) if args.fix_all_csi_overlaps else target_symbols

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"csi800_st_backfill_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "index_code": str(args.index_code),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "explicit_symbols": explicit_symbols,
        "target_symbol_count": int(len(target_symbols)),
        "target_symbols_sample": target_symbols[:50],
        "symbols_with_daily_rows": 0,
        "symbols_with_st_rows": 0,
        "daily_rows": 0,
        "generated_interval_rows": 0,
        "preserved_boundary_rows": 0,
        "deleted_intersecting_rows": 0,
        "inserted_rows": 0,
        "overlap_rows_before": 0,
        "overlap_rows_after": 0,
        "overlap_rows_fixed": 0,
        "failed_symbols": [],
    }

    bs = _load_baostock()
    def relogin() -> None:
        try:
            bs.logout()
        except Exception:
            pass
        login = bs.login()
        if login.error_code != "0":
            raise RuntimeError(f"baostock login failed: {login.error_msg}")

    relogin()

    interval_rows: list[tuple[Any, ...]] = []
    daily_samples: list[pd.DataFrame] = []
    try:
        for idx, ts_symbol in enumerate(target_symbols, start=1):
            try:
                daily = _fetch_st_daily(bs, ts_symbol, start, end)
            except Exception as exc:
                if not _is_login_error(exc):
                    raise
                relogin()
                daily = _fetch_st_daily(bs, ts_symbol, start, end)
            try:
                summary["daily_rows"] += int(len(daily))
                if not daily.empty:
                    summary["symbols_with_daily_rows"] += 1
                    sample = daily.assign(ts_code=ts_symbol).head(5)
                    daily_samples.append(sample)
                generated = _build_intervals(ts_symbol, daily)
                if generated:
                    summary["symbols_with_st_rows"] += 1
                    interval_rows.extend(generated)
            except Exception as exc:
                summary["failed_symbols"].append({"ts_code": ts_symbol, "error": str(exc)})
            if idx % 50 == 0:
                print(f"[st] {idx}/{len(target_symbols)} symbols fetched")
            time.sleep(float(args.sleep_seconds))
    finally:
        try:
            bs.logout()
        except Exception:
            pass

    summary["generated_interval_rows"] = int(len(interval_rows))

    interval_df = pd.DataFrame(
        interval_rows,
        columns=["ts_code", "start_date", "end_date", "st_type", "name_before", "name_after"],
    )
    interval_df = interval_df.drop_duplicates(subset=["ts_code", "start_date"], keep="last").sort_values(["ts_code", "start_date"])
    interval_rows = list(interval_df.itertuples(index=False, name=None))

    sample_daily_path = output_dir / "st_daily_sample.csv"
    if daily_samples:
        pd.concat(daily_samples, ignore_index=True).to_csv(sample_daily_path, index=False)
    else:
        pd.DataFrame(columns=["trade_date", "is_st", "ts_code"]).to_csv(sample_daily_path, index=False)
    summary["st_daily_sample_csv"] = str(sample_daily_path)

    interval_path = output_dir / "st_interval_rows.csv"
    interval_df.to_csv(interval_path, index=False)
    summary["st_interval_rows_csv"] = str(interval_path)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '1200000ms'")
            _init_temp_tables(cur)
            _load_symbol_rows(cur, "tmp_csi800_st_symbols", target_symbols)

            existing = _fetchdf(
                cur,
                """
                SELECT ts_code, start_date, end_date, st_type, name_before, name_after
                FROM public.pit_st_history
                WHERE ts_code IN (SELECT ts_code FROM tmp_csi800_st_symbols)
                  AND start_date <= %s
                  AND COALESCE(end_date, DATE '9999-12-31') >= %s
                ORDER BY ts_code, start_date
                """,
                (end, start),
            )
            existing_path = output_dir / "existing_intersecting_rows.csv"
            existing.to_csv(existing_path, index=False)
            summary["existing_intersecting_rows_csv"] = str(existing_path)

            preserved_rows = _preserve_boundary_rows(existing, start, end)
            summary["preserved_boundary_rows"] = int(len(preserved_rows))

            cur.execute(
                """
                DELETE FROM public.pit_st_history AS target
                USING tmp_csi800_st_symbols AS symbols
                WHERE target.ts_code = symbols.ts_code
                  AND target.start_date <= %s
                  AND COALESCE(target.end_date, DATE '9999-12-31') >= %s
                """,
                (end, start),
            )
            summary["deleted_intersecting_rows"] = int(cur.rowcount or 0)

            insert_rows = preserved_rows + interval_rows
            _load_interval_rows(cur, "tmp_csi800_st_intervals", insert_rows)
            cur.execute(
                """
                INSERT INTO public.pit_st_history (
                    ts_code,
                    start_date,
                    end_date,
                    st_type,
                    name_before,
                    name_after
                )
                SELECT ts_code, start_date, end_date, st_type, name_before, name_after
                FROM tmp_csi800_st_intervals
                ORDER BY ts_code, start_date
                """,
            )
            summary["inserted_rows"] = int(cur.rowcount or 0)

            overlap_before = _query_overlap_rows(cur, overlap_fix_symbols)
            summary["overlap_rows_before"] = int(len(overlap_before))
            overlap_before_path = output_dir / "overlap_rows_before.csv"
            overlap_before.to_csv(overlap_before_path, index=False)
            summary["overlap_rows_before_csv"] = str(overlap_before_path)

            _load_symbol_rows(cur, "tmp_csi800_st_symbols", overlap_fix_symbols)
            cur.execute(
                """
                WITH ordered AS (
                    SELECT
                        ts_code,
                        start_date,
                        LEAD(start_date) OVER (
                            PARTITION BY ts_code
                            ORDER BY start_date, COALESCE(end_date, DATE '9999-12-31')
                        ) AS next_start,
                        end_date
                    FROM public.pit_st_history
                    WHERE ts_code IN (SELECT ts_code FROM tmp_csi800_st_symbols)
                ),
                fixes AS (
                    SELECT
                        ts_code,
                        start_date,
                        (next_start - INTERVAL '1 day')::date AS new_end
                    FROM ordered
                    WHERE next_start IS NOT NULL
                      AND (end_date IS NULL OR end_date >= next_start)
                )
                UPDATE public.pit_st_history AS target
                SET end_date = fixes.new_end
                FROM fixes
                WHERE target.ts_code = fixes.ts_code
                  AND target.start_date = fixes.start_date
                """
            )
            summary["overlap_rows_fixed"] = int(cur.rowcount or 0)

            overlap_after = _query_overlap_rows(cur, overlap_fix_symbols)
            summary["overlap_rows_after"] = int(len(overlap_after))
            overlap_after_path = output_dir / "overlap_rows_after.csv"
            overlap_after.to_csv(overlap_after_path, index=False)
            summary["overlap_rows_after_csv"] = str(overlap_after_path)

            if args.apply:
                conn.commit()
            else:
                conn.rollback()
                summary["status"] = "dry_run"

    summary_path = output_dir / "summary.json"
    summary["summary_json"] = str(summary_path)
    _write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill CSI800 pit_st_history via baostock isST history")
    parser.add_argument("--start", default=DEFAULT_START, help="inclusive start date YYYY-MM-DD")
    parser.add_argument("--end", default=DEFAULT_END, help="inclusive end date YYYY-MM-DD")
    parser.add_argument("--index-code", default=DEFAULT_INDEX_CODE)
    parser.add_argument("--symbols", default="", help="optional comma-separated symbols in TS/internal format")
    parser.add_argument("--sleep-seconds", type=float, default=0.01, help="sleep between baostock requests")
    parser.add_argument("--fix-all-csi-overlaps", action="store_true", help="canonicalize overlapping existing ST rows across all CSI800 symbols")
    parser.add_argument("--output-dir", default="", help="output directory for artifacts")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_backfill(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary['summary_json']}")


if __name__ == "__main__":
    main()
