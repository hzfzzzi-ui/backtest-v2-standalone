from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
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
DEFAULT_SOURCE_TABLE = "pams_ohlcv_daily"
DEFAULT_TARGET_TABLE = "pit_index_daily"
TMP_TABLE = "tmp_pit_index_daily_upsert"
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(slots=True)
class DbSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _safe_ident(name: str) -> str:
    if not IDENT_RE.match(str(name or "")):
        raise ValueError(f"invalid SQL identifier: {name}")
    return str(name)


def _internal_to_ts_index_code(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    if text.startswith(("sh", "sz")) and len(text) == 8:
        return f"{text[2:]}.{text[:2].upper()}"
    if "." in text:
        code, exch = text.split(".", 1)
        return f"{code.upper()}.{exch.upper()}"
    raise ValueError(f"unsupported CN_INDEX symbol: {symbol}")


def _load_env_file() -> dict[str, str]:
    return read_shared_env_file(ROOT)


def _load_db_settings() -> DbSettings:
    settings = load_shared_db_settings(config_path=DEFAULT_CONFIG_PATH, root=ROOT)
    return DbSettings(settings.host, settings.port, settings.dbname, settings.user, settings.password)


def _connect():
    if psycopg is None:  # pragma: no cover
        raise RuntimeError("psycopg is required")
    return pg_connect(config_path=DEFAULT_CONFIG_PATH, root=ROOT, autocommit=False)


def _load_before_state(cur, target_table: str) -> dict[str, date | None]:
    table = _safe_ident(target_table)
    cur.execute(
        f"""
        SELECT index_code, MAX(trade_date) AS max_trade_date
        FROM public.{table}
        GROUP BY index_code
        ORDER BY index_code
        """
    )
    return {
        str(index_code): (pd.Timestamp(max_trade_date).date() if max_trade_date is not None else None)
        for index_code, max_trade_date in cur.fetchall()
    }


def _load_source_symbols(cur, source_table: str, end: date) -> list[str]:
    table = _safe_ident(source_table)
    cur.execute(
        f"""
        SELECT DISTINCT symbol
        FROM public.{table}
        WHERE market = 'CN_INDEX'
          AND trade_date <= %s
        ORDER BY symbol
        """,
        (end,),
    )
    return [str(row[0]).strip().lower() for row in cur.fetchall() if str(row[0]).strip()]


def _load_source_rows(cur, source_table: str, end: date, symbols: list[str]) -> pd.DataFrame:
    table = _safe_ident(source_table)
    cur.execute(
        f"""
        SELECT symbol, trade_date, open, high, low, close, volume, turnover
        FROM public.{table}
        WHERE market = 'CN_INDEX'
          AND trade_date <= %s
          AND symbol = ANY(%s)
        ORDER BY trade_date, symbol
        """,
        (end, symbols),
    )
    rows = cur.fetchall()
    cols = [d.name for d in cur.description]
    frame = pd.DataFrame(rows, columns=cols)
    if frame.empty:
        return pd.DataFrame(columns=["index_code", "trade_date", "open", "high", "low", "close", "volume", "turnover"])
    frame["index_code"] = frame["symbol"].astype(str).map(_internal_to_ts_index_code)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
    for col in ("open", "high", "low", "close", "volume", "turnover"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame[["index_code", "trade_date", "open", "high", "low", "close", "volume", "turnover"]].copy()


def _filter_incremental_rows(frame: pd.DataFrame, before_max: dict[str, date | None], start: date | None) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    if start is not None:
        out = out[out["trade_date"] >= start].copy()
    keep_mask = []
    for row in out.itertuples(index=False):
        max_td = before_max.get(str(row.index_code))
        keep_mask.append(max_td is None or row.trade_date > max_td)
    out = out[pd.Series(keep_mask, index=out.index)].copy()
    return out.drop_duplicates(subset=["index_code", "trade_date"], keep="last").sort_values(["trade_date", "index_code"]).reset_index(drop=True)


def _init_temp_table(cur) -> None:
    cur.execute(
        f"""
        CREATE TEMP TABLE IF NOT EXISTS {TMP_TABLE} (
            index_code text NOT NULL,
            trade_date date NOT NULL,
            open numeric,
            high numeric,
            low numeric,
            close numeric,
            volume bigint,
            turnover numeric,
            created_at timestamptz NOT NULL
        ) ON COMMIT DROP
        """
    )


def _load_batch_into_temp(cur, batch: pd.DataFrame, created_at: datetime) -> None:
    cur.execute(f"TRUNCATE TABLE {TMP_TABLE}")
    if batch.empty:
        return
    rows = [
        (
            str(row.index_code),
            row.trade_date,
            None if pd.isna(row.open) else float(row.open),
            None if pd.isna(row.high) else float(row.high),
            None if pd.isna(row.low) else float(row.low),
            None if pd.isna(row.close) else float(row.close),
            None if pd.isna(row.volume) else int(round(float(row.volume))),
            None if pd.isna(row.turnover) else float(row.turnover),
            created_at,
        )
        for row in batch.itertuples(index=False)
    ]
    cur.executemany(
        f"""
        INSERT INTO {TMP_TABLE} (
            index_code, trade_date, open, high, low, close, volume, turnover, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )


def _count_batch_state(cur, target_table: str) -> tuple[int, int]:
    table = _safe_ident(target_table)
    cur.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE t.index_code IS NULL) AS insert_rows,
            COUNT(*) FILTER (WHERE t.index_code IS NOT NULL) AS update_rows
        FROM {TMP_TABLE} AS s
        LEFT JOIN public.{table} AS t
          ON t.index_code = s.index_code
         AND t.trade_date = s.trade_date
        """
    )
    row = cur.fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def _upsert_batch(cur, target_table: str) -> int:
    table = _safe_ident(target_table)
    cur.execute(
        f"""
        INSERT INTO public.{table} (
            index_code, trade_date, open, high, low, close, volume, turnover, created_at
        )
        SELECT
            index_code, trade_date, open, high, low, close, volume, turnover, created_at
        FROM {TMP_TABLE}
        ON CONFLICT (index_code, trade_date) DO UPDATE
        SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            turnover = EXCLUDED.turnover
        """
    )
    return int(cur.rowcount or 0)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_update(args: argparse.Namespace) -> dict[str, Any]:
    end = date.fromisoformat(args.end)
    start = date.fromisoformat(args.start) if str(args.start or "").strip() else None
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"pit_index_daily_update_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '600000ms'")
            before_max = _load_before_state(cur, str(args.target_table))
            source_symbols = _load_source_symbols(cur, str(args.source_table), end)
            source_frame = _load_source_rows(cur, str(args.source_table), end, source_symbols)

    incremental = _filter_incremental_rows(source_frame, before_max, start)
    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "source_table": str(args.source_table),
        "target_table": str(args.target_table),
        "start": start.isoformat() if start is not None else None,
        "end": end.isoformat(),
        "source_symbol_count": int(len(source_symbols)),
        "source_symbols": [_internal_to_ts_index_code(symbol) for symbol in source_symbols],
        "source_rows": int(len(source_frame)),
        "rows_to_upsert": int(len(incremental)),
        "before_max": {k: v.isoformat() if v is not None else None for k, v in before_max.items()},
        "insert_rows": 0,
        "update_rows": 0,
        "upserted_rows": 0,
    }

    sample_path = output_dir / "pit_index_daily_update_sample.csv"
    incremental.head(200).to_csv(sample_path, index=False)
    summary["sample_csv"] = str(sample_path)

    if incremental.empty:
        summary["status"] = "noop"
        _write_json(output_dir / "summary.json", summary)
        return summary

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '600000ms'")
            _init_temp_table(cur)
            created_at = datetime.utcnow()
            batch_size = max(int(args.batch_size), 1)
            for batch_start in range(0, len(incremental), batch_size):
                batch = incremental.iloc[batch_start : batch_start + batch_size].copy()
                _load_batch_into_temp(cur, batch, created_at)
                insert_rows, update_rows = _count_batch_state(cur, str(args.target_table))
                upserted_rows = _upsert_batch(cur, str(args.target_table))
                summary["insert_rows"] += insert_rows
                summary["update_rows"] += update_rows
                summary["upserted_rows"] += upserted_rows
            if args.apply:
                conn.commit()
            else:
                conn.rollback()
                summary["status"] = "dry_run"

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '600000ms'")
            after_max = _load_before_state(cur, str(args.target_table))
    summary["after_max"] = {k: v.isoformat() if v is not None else None for k, v in after_max.items()}
    _write_json(output_dir / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync pit_index_daily from audited CN_INDEX rows in pams_ohlcv_daily")
    parser.add_argument("--end", required=True, help="inclusive end date YYYY-MM-DD")
    parser.add_argument("--start", default="", help="optional inclusive start date YYYY-MM-DD")
    parser.add_argument("--source-table", default=DEFAULT_SOURCE_TABLE)
    parser.add_argument("--target-table", default=DEFAULT_TARGET_TABLE)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_update(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
