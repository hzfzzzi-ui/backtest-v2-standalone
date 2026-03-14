from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "ops"
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"
DEFAULT_TABLE = "pams_ohlcv_daily"
DAILY_BASIC_FIELDS = [
    "turnover_rate",
    "turnover_rate_f",
    "volume_ratio",
    "float_share",
    "free_share",
    "circ_mv",
]
FIELD_SQL_TYPES = {
    "turnover_rate": "double precision",
    "turnover_rate_f": "double precision",
    "volume_ratio": "double precision",
    "float_share": "double precision",
    "free_share": "double precision",
    "circ_mv": "double precision",
}


@dataclass(slots=True)
class DbSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _normalize_stock_symbol(symbol: str) -> str:
    text = str(symbol or "").strip()
    if "." in text:
        code, exch = text.split(".", 1)
        return ("sh" if exch.upper() == "SH" else "sz") + code
    lower = text.lower()
    if lower.startswith(("sh", "sz", "bj")):
        return lower
    if text and text[0] in {"6", "5", "9"}:
        return f"sh{text}"
    return f"sz{text}"


def _load_env_file() -> dict[str, str]:
    env_path = ROOT / ".env"
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _load_db_settings() -> DbSettings:
    file_env = _load_env_file()
    cfg = {}
    if DEFAULT_CONFIG_PATH.exists():
        cfg = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    db_cfg = dict(cfg.get("db") or {})
    return DbSettings(
        host=str(os.environ.get("PGHOST") or os.environ.get("PAMS_PG_HOST") or db_cfg.get("host") or "pams-postgres"),
        port=int(os.environ.get("PGPORT") or os.environ.get("PAMS_PG_PORT") or db_cfg.get("port") or 5432),
        dbname=str(os.environ.get("PGDATABASE") or os.environ.get("PAMS_PG_DBNAME") or db_cfg.get("dbname") or "pams"),
        user=str(os.environ.get("PGUSER") or os.environ.get("PAMS_PG_USER") or db_cfg.get("user") or "pams"),
        password=str(
            os.environ.get("PGPASSWORD")
            or os.environ.get("PAMS_PG_PASSWORD")
            or file_env.get("POSTGRES_PASSWORD")
            or db_cfg.get("password")
            or ""
        ),
    )


def _connect():
    if psycopg is None:  # pragma: no cover
        raise RuntimeError("psycopg is required")
    db = _load_db_settings()
    return psycopg.connect(
        host=db.host,
        port=db.port,
        dbname=db.dbname,
        user=db.user,
        password=db.password,
        autocommit=False,
    )


def _iter_date_chunks(start: date, end: date, chunk_days: int) -> Iterable[tuple[date, date]]:
    cur = start
    step = max(int(chunk_days), 1)
    while cur <= end:
        chunk_end = min(cur + timedelta(days=step - 1), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def _load_tushare_client(token: str):
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is required via --token or env TUSHARE_TOKEN")
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api(token)


def _normalize_daily_basic_frame(raw: pd.DataFrame, symbol_filter: set[str]) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["symbol", "trade_date", *DAILY_BASIC_FIELDS])
    df = raw.copy()
    keep_cols = [c for c in ["ts_code", "trade_date", *DAILY_BASIC_FIELDS] if c in df.columns]
    df = df.loc[:, keep_cols].copy()
    if "ts_code" not in df.columns or "trade_date" not in df.columns:
        raise RuntimeError("tushare daily_basic missing ts_code/trade_date")
    df["symbol"] = df["ts_code"].astype(str).map(_normalize_stock_symbol).astype(str).str.lower()
    df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce").dt.date
    df = df.dropna(subset=["symbol", "trade_date"]).reset_index(drop=True)
    if symbol_filter:
        df = df[df["symbol"].isin(symbol_filter)].copy()
    for col in DAILY_BASIC_FIELDS:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["symbol", "trade_date", *DAILY_BASIC_FIELDS]].drop_duplicates(subset=["symbol", "trade_date"], keep="last")
    return df.sort_values(["trade_date", "symbol"]).reset_index(drop=True)


def _fetch_daily_basic_chunk(
    pro: Any,
    start: date,
    end: date,
    symbol_filter: set[str],
) -> pd.DataFrame:
    raw = pro.daily_basic(
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        fields="ts_code,trade_date," + ",".join(DAILY_BASIC_FIELDS),
    )
    return _normalize_daily_basic_frame(raw, symbol_filter)


def _ensure_liquidity_columns(cur, table: str) -> list[str]:
    statements = [
        f"ALTER TABLE public.{table} ADD COLUMN IF NOT EXISTS {column} {sql_type}"
        for column, sql_type in FIELD_SQL_TYPES.items()
    ]
    for statement in statements:
        cur.execute(statement)
    return statements


def _init_temp_table(cur) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS tmp_cn_daily_basic_liquidity (
            symbol text NOT NULL,
            trade_date date NOT NULL,
            turnover_rate double precision,
            turnover_rate_f double precision,
            volume_ratio double precision,
            float_share double precision,
            free_share double precision,
            circ_mv double precision
        ) ON COMMIT DROP
        """
    )


def _load_batch_into_temp(cur, batch: pd.DataFrame) -> None:
    cur.execute("TRUNCATE TABLE tmp_cn_daily_basic_liquidity")
    if batch.empty:
        return
    insert_sql = """
        INSERT INTO tmp_cn_daily_basic_liquidity (
            symbol,
            trade_date,
            turnover_rate,
            turnover_rate_f,
            volume_ratio,
            float_share,
            free_share,
            circ_mv
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    rows = [
        (
            str(row.symbol),
            row.trade_date,
            None if pd.isna(row.turnover_rate) else float(row.turnover_rate),
            None if pd.isna(row.turnover_rate_f) else float(row.turnover_rate_f),
            None if pd.isna(row.volume_ratio) else float(row.volume_ratio),
            None if pd.isna(row.float_share) else float(row.float_share),
            None if pd.isna(row.free_share) else float(row.free_share),
            None if pd.isna(row.circ_mv) else float(row.circ_mv),
        )
        for row in batch.itertuples(index=False)
    ]
    cur.executemany(insert_sql, rows)


def _update_target_from_temp(cur, table: str) -> tuple[int, int]:
    cur.execute(
        f"""
        SELECT COUNT(*)
        FROM tmp_cn_daily_basic_liquidity AS t
        LEFT JOIN public.{table} AS p
          ON p.market = 'CN_A'
         AND p.symbol = t.symbol
         AND p.trade_date = t.trade_date
        WHERE p.symbol IS NULL
        """
    )
    unmatched_rows = int(cur.fetchone()[0] or 0)
    cur.execute(
        f"""
        UPDATE public.{table} AS p
        SET
            turnover_rate = t.turnover_rate,
            turnover_rate_f = t.turnover_rate_f,
            volume_ratio = t.volume_ratio,
            float_share = t.float_share,
            free_share = t.free_share,
            circ_mv = t.circ_mv
        FROM tmp_cn_daily_basic_liquidity AS t
        WHERE p.market = 'CN_A'
          AND p.symbol = t.symbol
          AND p.trade_date = t.trade_date
        """
    )
    return int(cur.rowcount or 0), unmatched_rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_import(args: argparse.Namespace) -> dict[str, Any]:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise ValueError("start must be <= end")

    token = str(args.token or os.environ.get("TUSHARE_TOKEN") or "").strip()
    symbol_filter = {
        _normalize_stock_symbol(symbol).lower()
        for symbol in [item.strip() for item in str(args.symbols_csv or "").split(",")]
        if symbol.strip()
    }
    pro = _load_tushare_client(token)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"daily_basic_liquidity_{ts}")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "table": str(args.table),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "chunk_days": int(args.chunk_days),
        "symbol_filter_count": int(len(symbol_filter)),
        "fetched_rows": 0,
        "normalized_rows": 0,
        "updated_rows": 0,
        "unmatched_rows": 0,
        "chunks": [],
        "schema_sql": [
            f"ALTER TABLE public.{args.table} ADD COLUMN IF NOT EXISTS {column} {sql_type}"
            for column, sql_type in FIELD_SQL_TYPES.items()
        ],
    }

    all_rows: list[pd.DataFrame] = []
    for chunk_start, chunk_end in _iter_date_chunks(start, end, int(args.chunk_days)):
        chunk_df = _fetch_daily_basic_chunk(pro, chunk_start, chunk_end, symbol_filter)
        summary["normalized_rows"] += int(len(chunk_df))
        summary["chunks"].append(
            {
                "start": chunk_start.isoformat(),
                "end": chunk_end.isoformat(),
                "rows": int(len(chunk_df)),
            }
        )
        if not chunk_df.empty:
            all_rows.append(chunk_df)

    combined = (
        pd.concat(all_rows, ignore_index=True)
        if all_rows
        else pd.DataFrame(columns=["symbol", "trade_date", *DAILY_BASIC_FIELDS])
    )
    combined = combined.drop_duplicates(subset=["symbol", "trade_date"], keep="last").reset_index(drop=True)
    summary["fetched_rows"] = int(sum(int(item["rows"]) for item in summary["chunks"]))
    summary["normalized_rows"] = int(len(combined))

    sample_path = output_dir / "daily_basic_liquidity_sample.csv"
    combined.head(200).to_csv(sample_path, index=False)
    summary["sample_csv"] = str(sample_path)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '600000ms'")
            _init_temp_table(cur)
            if args.apply:
                _ensure_liquidity_columns(cur, str(args.table))
            for batch_start in range(0, len(combined), int(args.batch_size)):
                batch = combined.iloc[batch_start : batch_start + int(args.batch_size)].copy()
                if batch.empty:
                    continue
                _load_batch_into_temp(cur, batch)
                updated_rows, unmatched_rows = _update_target_from_temp(cur, str(args.table))
                summary["updated_rows"] += int(updated_rows)
                summary["unmatched_rows"] += int(unmatched_rows)
            if args.apply:
                conn.commit()
            else:
                conn.rollback()
                summary["status"] = "dry_run"

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill Tushare daily_basic liquidity fields into pams_ohlcv_daily"
    )
    parser.add_argument("--start", required=True, help="inclusive start date, format YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="inclusive end date, format YYYY-MM-DD")
    parser.add_argument("--token", default=os.environ.get("TUSHARE_TOKEN", ""))
    parser.add_argument("--symbols-csv", default="", help="optional comma-separated symbols, e.g. 600000.SH,000001.SZ")
    parser.add_argument("--table", default=DEFAULT_TABLE, help="target PostgreSQL table")
    parser.add_argument("--chunk-days", type=int, default=31, help="Tushare fetch range per request")
    parser.add_argument("--batch-size", type=int, default=5000, help="DB update batch size")
    parser.add_argument("--output-dir", default="", help="output directory for summary/sample artifacts")
    parser.add_argument("--apply", action="store_true", help="commit schema + data updates; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_import(args)
    output_dir = Path(summary["sample_csv"]).parent
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
