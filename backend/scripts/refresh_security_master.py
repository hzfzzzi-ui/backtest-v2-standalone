from __future__ import annotations

import argparse
import json
import os
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

DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "ops"
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"
DEFAULT_TABLE = "pit_security_master"
STOCK_BASIC_FIELDS = "ts_code,symbol,name,exchange,market,list_date,delist_date,industry"
LIST_STATUSES = ("L", "D", "P")
EXCHANGE_MAP = {
    "SSE": "SH",
    "SZSE": "SZ",
    "BSE": "BJ",
    "SH": "SH",
    "SZ": "SZ",
    "BJ": "BJ",
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
        exch_u = exch.upper()
        if exch_u == "SH":
            return f"sh{code}"
        if exch_u == "SZ":
            return f"sz{code}"
        if exch_u == "BJ":
            return f"bj{code}"
    lower = text.lower()
    if lower.startswith(("sh", "sz", "bj")):
        return lower
    if text.startswith(("4", "8")):
        return f"bj{text}"
    if text and text[0] in {"5", "6", "9"}:
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


def _resolve_token(explicit_token: str) -> str:
    explicit = str(explicit_token or "").strip()
    if explicit:
        return explicit
    env_token = str(os.environ.get("TUSHARE_TOKEN") or "").strip()
    if env_token:
        return env_token
    return str(_load_env_file().get("TUSHARE_TOKEN") or "").strip()


def _load_tushare_client(token: str):
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is required via --token, env, or .env")
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api(token)


def _normalize_exchange(value: Any, ts_code: str) -> str:
    raw = str(value or "").strip().upper()
    if raw in EXCHANGE_MAP:
        return EXCHANGE_MAP[raw]
    if "." in str(ts_code):
        _, exch = str(ts_code).split(".", 1)
        return exch.upper()
    if str(ts_code).startswith(("4", "8", "9")):
        return "BJ"
    return "SH" if str(ts_code).startswith(("5", "6")) else "SZ"


def _to_date_or_none(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _fetch_status_frame(pro: Any, list_status: str) -> pd.DataFrame:
    raw = pro.stock_basic(exchange="", list_status=list_status, fields=STOCK_BASIC_FIELDS)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["ts_code", "symbol", "name", "exchange", "market_type", "list_date", "delist_date", "industry"])
    df = raw.copy()
    for col in ["ts_code", "symbol", "name", "exchange", "market", "list_date", "delist_date", "industry"]:
        if col not in df.columns:
            df[col] = pd.NA
    df["ts_code"] = df["ts_code"].astype(str).str.upper().str.strip()
    df = df[df["ts_code"].str.contains(r"\.(?:SH|SZ|BJ)$", regex=True, na=False)].copy()
    df["symbol"] = df["ts_code"].map(_normalize_stock_symbol)
    df["exchange"] = [
        _normalize_exchange(exchange, ts_code)
        for exchange, ts_code in zip(df["exchange"], df["ts_code"], strict=False)
    ]
    df["market_type"] = "CN_A"
    df["list_date"] = df["list_date"].map(_to_date_or_none)
    df["delist_date"] = df["delist_date"].map(_to_date_or_none)
    df["name"] = df["name"].astype(str).str.strip()
    df["industry"] = df["industry"].astype(str).str.strip()
    df.loc[df["industry"] == "", "industry"] = pd.NA
    return (
        df[["ts_code", "symbol", "name", "exchange", "market_type", "list_date", "delist_date", "industry"]]
        .drop_duplicates(subset=["ts_code"], keep="last")
        .sort_values("ts_code")
        .reset_index(drop=True)
    )


def _fetch_security_master(pro: Any) -> tuple[pd.DataFrame, dict[str, int]]:
    frames: list[pd.DataFrame] = []
    fetched_counts: dict[str, int] = {}
    for status in LIST_STATUSES:
        frame = _fetch_status_frame(pro, status)
        frames.append(frame)
        fetched_counts[status] = int(len(frame))
    combined = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset=["ts_code"], keep="last")
        .sort_values("ts_code")
        .reset_index(drop=True)
    )
    return combined, fetched_counts


def _load_existing_subset(conn, ts_codes: list[str]) -> pd.DataFrame:
    if not ts_codes:
        return pd.DataFrame(columns=["ts_code", "symbol", "name", "exchange", "market_type", "list_date", "delist_date", "industry"])
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT ts_code, symbol, name, exchange, market_type, list_date, delist_date, industry
            FROM public.{DEFAULT_TABLE}
            WHERE ts_code = ANY(%s)
            ORDER BY ts_code
            """,
            (ts_codes,),
        )
        rows = cur.fetchall()
        cols = [d.name for d in cur.description]
    frame = pd.DataFrame(rows, columns=cols)
    if frame.empty:
        return pd.DataFrame(columns=["ts_code", "symbol", "name", "exchange", "market_type", "list_date", "delist_date", "industry"])
    for col in ["list_date", "delist_date"]:
        frame[col] = pd.to_datetime(frame[col], errors="coerce").dt.date
    return frame


def _compute_change_summary(existing: pd.DataFrame, incoming: pd.DataFrame) -> tuple[dict[str, int], pd.DataFrame]:
    merged = incoming.merge(existing, on="ts_code", how="left", suffixes=("_new", "_old"))
    merged["is_new"] = merged["symbol_old"].isna()
    merged["list_date_changed"] = (
        merged["list_date_new"].astype("string").fillna("")
        != merged["list_date_old"].astype("string").fillna("")
    )
    merged["delist_date_changed"] = (
        merged["delist_date_new"].astype("string").fillna("")
        != merged["delist_date_old"].astype("string").fillna("")
    )
    merged["name_changed"] = merged["name_new"].fillna("") != merged["name_old"].fillna("")
    merged["symbol_changed"] = merged["symbol_new"].fillna("") != merged["symbol_old"].fillna("")
    merged["exchange_changed"] = merged["exchange_new"].fillna("") != merged["exchange_old"].fillna("")
    summary = {
        "new_rows": int(merged["is_new"].sum()),
        "list_date_changed_rows": int((~merged["is_new"] & merged["list_date_changed"]).sum()),
        "delist_date_changed_rows": int((~merged["is_new"] & merged["delist_date_changed"]).sum()),
        "name_changed_rows": int((~merged["is_new"] & merged["name_changed"]).sum()),
        "symbol_changed_rows": int((~merged["is_new"] & merged["symbol_changed"]).sum()),
        "exchange_changed_rows": int((~merged["is_new"] & merged["exchange_changed"]).sum()),
    }
    change_view = merged[
        merged["is_new"]
        | merged["list_date_changed"]
        | merged["delist_date_changed"]
        | merged["name_changed"]
        | merged["symbol_changed"]
        | merged["exchange_changed"]
    ].copy()
    keep_cols = [
        "ts_code",
        "symbol_old",
        "symbol_new",
        "name_old",
        "name_new",
        "exchange_old",
        "exchange_new",
        "list_date_old",
        "list_date_new",
        "delist_date_old",
        "delist_date_new",
        "industry_old",
        "industry_new",
        "is_new",
    ]
    return summary, change_view[keep_cols].sort_values("ts_code").reset_index(drop=True)


def _init_temp_table(cur) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS tmp_pit_security_master_upsert (
            ts_code text NOT NULL,
            symbol text NOT NULL,
            name text,
            exchange text,
            market_type text,
            list_date date,
            delist_date date,
            industry text
        ) ON COMMIT DROP
        """
    )


def _load_batch_into_temp(cur, batch: pd.DataFrame) -> None:
    cur.execute("TRUNCATE TABLE tmp_pit_security_master_upsert")
    if batch.empty:
        return
    rows = [
        (
            str(row.ts_code),
            str(row.symbol),
            None if pd.isna(row.name) else str(row.name),
            None if pd.isna(row.exchange) else str(row.exchange),
            None if pd.isna(row.market_type) else str(row.market_type),
            row.list_date,
            row.delist_date,
            None if pd.isna(row.industry) else str(row.industry),
        )
        for row in batch.itertuples(index=False)
    ]
    cur.executemany(
        """
        INSERT INTO tmp_pit_security_master_upsert (
            ts_code,
            symbol,
            name,
            exchange,
            market_type,
            list_date,
            delist_date,
            industry
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )


def _count_batch_state(cur) -> tuple[int, int]:
    cur.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE target.ts_code IS NULL) AS insert_rows,
            COUNT(*) FILTER (WHERE target.ts_code IS NOT NULL) AS update_rows
        FROM tmp_pit_security_master_upsert AS src
        LEFT JOIN public.{DEFAULT_TABLE} AS target
          ON target.ts_code = src.ts_code
        """
    )
    row = cur.fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def _upsert_batch(cur) -> int:
    cur.execute(
        f"""
        INSERT INTO public.{DEFAULT_TABLE} (
            ts_code,
            symbol,
            name,
            exchange,
            list_date,
            delist_date,
            industry,
            market_type,
            created_at,
            updated_at
        )
        SELECT
            ts_code,
            symbol,
            name,
            exchange,
            list_date,
            delist_date,
            industry,
            market_type,
            NOW(),
            NOW()
        FROM tmp_pit_security_master_upsert
        ON CONFLICT (ts_code) DO UPDATE
        SET
            symbol = EXCLUDED.symbol,
            name = COALESCE(NULLIF(EXCLUDED.name, ''), {DEFAULT_TABLE}.name),
            exchange = COALESCE(NULLIF(EXCLUDED.exchange, ''), {DEFAULT_TABLE}.exchange),
            list_date = COALESCE(LEAST(EXCLUDED.list_date, {DEFAULT_TABLE}.list_date), EXCLUDED.list_date, {DEFAULT_TABLE}.list_date),
            delist_date = COALESCE(EXCLUDED.delist_date, {DEFAULT_TABLE}.delist_date),
            industry = COALESCE(NULLIF(EXCLUDED.industry, ''), {DEFAULT_TABLE}.industry),
            market_type = COALESCE(NULLIF(EXCLUDED.market_type, ''), {DEFAULT_TABLE}.market_type),
            updated_at = NOW()
        """
    )
    return int(cur.rowcount or 0)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_refresh(args: argparse.Namespace) -> dict[str, Any]:
    token = _resolve_token(str(args.token or ""))
    pro = _load_tushare_client(token)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"security_master_refresh_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    incoming, fetched_counts = _fetch_security_master(pro)
    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "table": DEFAULT_TABLE,
        "fetched_counts": fetched_counts,
        "rows_total": int(len(incoming)),
        "insert_rows": 0,
        "update_rows": 0,
        "upserted_rows": 0,
    }

    with _connect() as conn:
        existing = _load_existing_subset(conn, incoming["ts_code"].astype(str).tolist())
        change_summary, change_view = _compute_change_summary(existing, incoming)
        summary.update(change_summary)

        sample_csv = output_dir / "security_master_changes_sample.csv"
        change_view.head(500).to_csv(sample_csv, index=False)
        summary["sample_csv"] = str(sample_csv)

        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '600000ms'")
            _init_temp_table(cur)
            batch_size = max(int(args.batch_size), 1)
            for batch_start in range(0, len(incoming), batch_size):
                batch = incoming.iloc[batch_start : batch_start + batch_size].copy()
                _load_batch_into_temp(cur, batch)
                insert_rows, update_rows = _count_batch_state(cur)
                upserted_rows = _upsert_batch(cur)
                summary["insert_rows"] += insert_rows
                summary["update_rows"] += update_rows
                summary["upserted_rows"] += upserted_rows
            if args.apply:
                conn.commit()
            else:
                conn.rollback()
                summary["status"] = "dry_run"

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh pit_security_master from Tushare stock_basic")
    parser.add_argument("--token", default="", help="Tushare token; falls back to env/.env")
    parser.add_argument("--batch-size", type=int, default=2000, help="DB upsert batch size")
    parser.add_argument("--output-dir", default="", help="output directory for summary/sample artifacts")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_refresh(args)
    output_dir = Path(summary["sample_csv"]).parent
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
