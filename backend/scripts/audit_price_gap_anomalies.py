from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from typing import Any

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


def _read_symbols_from_trades(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        symbols = sorted({str(row.get("symbol") or "").strip().lower() for row in reader if str(row.get("symbol") or "").strip()})
    return symbols


def _symbol_args(args: argparse.Namespace) -> list[str]:
    symbols: list[str] = []
    if args.symbols_csv:
        symbols.extend([s.strip().lower() for s in str(args.symbols_csv).split(",") if s.strip()])
    if args.symbols_from_trades:
        symbols.extend(_read_symbols_from_trades(Path(args.symbols_from_trades)))
    return sorted({s for s in symbols if s})


def _base_where_clause(start: str | None, end: str | None, symbols: list[str]) -> tuple[str, list[Any]]:
    clauses = ["coalesce(market,'') <> 'CN_INDEX'"]
    params: list[Any] = []
    if start:
        clauses.append("trade_date >= %s")
        params.append(start)
    if end:
        clauses.append("trade_date <= %s")
        params.append(end)
    if symbols:
        clauses.append("symbol = any(%s)")
        params.append(symbols)
    return " and ".join(clauses), params


def _query_one(cur, sql: str, params: list[Any]) -> dict[str, Any]:
    cur.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return {}
    cols = [d.name for d in cur.description]
    return {cols[i]: row[i] for i in range(len(cols))}


def _query_all(cur, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = [d.name for d in cur.description]
    return [{cols[i]: row[i] for i in range(len(cols))} for row in rows]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, tuple):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    if isinstance(obj, Decimal):
        if obj == obj.to_integral_value():
            return int(obj)
        return float(obj)
    return obj


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit stock price date gaps that can break NAV marking")
    parser.add_argument("--start", default=None, help="inclusive start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="inclusive end date YYYY-MM-DD")
    parser.add_argument("--symbols-csv", default="", help="comma-separated symbols")
    parser.add_argument("--symbols-from-trades", default="", help="portfolio_trades.csv path to infer symbols")
    parser.add_argument("--top", type=int, default=50, help="top gap segments to export")
    parser.add_argument("--output-dir", default="", help="output directory")
    args = parser.parse_args()

    symbols = _symbol_args(args)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"price_gap_audit_{ts}")
    out_dir.mkdir(parents=True, exist_ok=True)

    where_sql, where_params = _base_where_clause(args.start, args.end, symbols)
    rows_where_sql, rows_where_params = _base_where_clause(args.start, args.end, symbols)

    summary_sql = f"""
with rows_base as (
    select * from pams_ohlcv_daily where {rows_where_sql}
),
cal as (
    select trade_date, row_number() over(order by trade_date) as cal_rn
    from (select distinct trade_date from rows_base) d
),
ranked as (
    select
        p.symbol,
        p.trade_date,
        c.cal_rn,
        lag(c.cal_rn) over(partition by p.symbol order by p.trade_date) as prev_rn
    from rows_base p
    join cal c on c.trade_date = p.trade_date
),
gaps as (
    select symbol, greatest(cal_rn - prev_rn - 1, 0) as gap_days
    from ranked
    where prev_rn is not null and cal_rn - prev_rn > 1
)
select
    (select count(*) from rows_base) as rows_total,
    (select count(distinct symbol) from rows_base) as symbols,
    (select min(trade_date) from rows_base) as min_date,
    (select max(trade_date) from rows_base) as max_date,
    (select count(*) from rows_base where coalesce(is_suspended, false)) as suspended_rows,
    (select count(*) from gaps) as gap_segments,
    (select coalesce(sum(gap_days), 0) from gaps) as gap_days_total,
    (select count(distinct symbol) from gaps) as symbols_with_gaps
"""

    top_sql = f"""
with rows_base as (
    select * from pams_ohlcv_daily where {rows_where_sql}
),
cal as (
    select trade_date, row_number() over(order by trade_date) as cal_rn
    from (select distinct trade_date from rows_base) d
),
ranked as (
    select
        p.symbol,
        p.trade_date,
        c.cal_rn,
        lag(c.cal_rn) over(partition by p.symbol order by p.trade_date) as prev_rn,
        lag(p.trade_date) over(partition by p.symbol order by p.trade_date) as prev_date
    from rows_base p
    join cal c on c.trade_date = p.trade_date
)
select
    symbol,
    prev_date,
    trade_date as next_date,
    (cal_rn - prev_rn - 1) as gap_days
from ranked
where prev_rn is not null and cal_rn - prev_rn > 1
order by gap_days desc, symbol
limit %s
"""

    dist_sql = f"""
with rows_base as (
    select * from pams_ohlcv_daily where {rows_where_sql}
),
cal as (
    select trade_date, row_number() over(order by trade_date) as cal_rn
    from (select distinct trade_date from rows_base) d
),
ranked as (
    select
        p.symbol,
        p.trade_date,
        c.cal_rn,
        lag(c.cal_rn) over(partition by p.symbol order by p.trade_date) as prev_rn
    from rows_base p
    join cal c on c.trade_date = p.trade_date
),
gaps as (
    select greatest(cal_rn - prev_rn - 1, 0) as gap_days
    from ranked
    where prev_rn is not null and cal_rn - prev_rn > 1
)
select
    case
        when gap_days = 1 then '1'
        when gap_days = 2 then '2'
        when gap_days = 3 then '3'
        when gap_days between 4 and 5 then '4-5'
        when gap_days between 6 and 10 then '6-10'
        when gap_days between 11 and 20 then '11-20'
        when gap_days between 21 and 60 then '21-60'
        else '61+'
    end as bucket,
    count(*) as segments,
    min(gap_days) as min_gap,
    max(gap_days) as max_gap
from gaps
group by 1
order by min(gap_days)
"""

    with _connect() as conn:
        with conn.cursor() as cur:
            summary = _query_one(cur, summary_sql, rows_where_params)
            top_rows = _query_all(cur, top_sql, rows_where_params + [int(args.top)])
            dist_rows = _query_all(cur, dist_sql, rows_where_params)
        conn.rollback()

    payload = {
        "scope": {
            "start": args.start,
            "end": args.end,
            "symbols_count": len(symbols),
            "symbols": symbols[:200],
        },
        "summary": summary,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    (out_dir / "summary.json").write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(out_dir / "gap_segments_top.csv", top_rows)
    _write_csv(out_dir / "gap_distribution.csv", dist_rows)

    print(json.dumps(_jsonable({"output_dir": str(out_dir), **payload}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
