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
        password=str(os.environ.get("PGPASSWORD") or os.environ.get("PAMS_PG_PASSWORD") or file_env.get("POSTGRES_PASSWORD") or db_cfg.get("password") or ""),
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


def _where_clause(start: str | None, end: str | None, symbols: list[str], exclude_bj: bool) -> tuple[str, list[Any]]:
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
    if exclude_bj:
        clauses.append("symbol not like %s")
        params.append("bj%")
    return " and ".join(clauses), params


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
    parser = argparse.ArgumentParser(
        description="Backfill missing stock-date rows as explicit suspended rows using previous close carry-forward"
    )
    parser.add_argument("--start", default=None, help="inclusive start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="inclusive end date YYYY-MM-DD")
    parser.add_argument("--symbols-csv", default="", help="comma-separated symbols")
    parser.add_argument("--symbols-from-trades", default="", help="portfolio_trades.csv path to infer symbols")
    parser.add_argument("--max-gap-days", type=int, default=60, help="only repair gap segments up to this length")
    parser.add_argument("--exclude-bj", action="store_true", help="exclude BJ symbols from repair candidates")
    parser.add_argument("--apply", action="store_true", help="write repaired rows into pams_ohlcv_daily")
    parser.add_argument("--output-dir", default="", help="output directory")
    args = parser.parse_args()

    symbols = _symbol_args(args)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"price_gap_repair_{ts}")
    out_dir.mkdir(parents=True, exist_ok=True)

    where_sql, where_params = _where_clause(args.start, args.end, symbols, bool(args.exclude_bj))

    segments_sql = f"""
with rows_base as (
    select * from pams_ohlcv_daily where {where_sql}
),
cal as (
    select trade_date, row_number() over(order by trade_date) as cal_rn
    from (select distinct trade_date from rows_base) d
),
ranked as (
    select
        p.symbol,
        p.market,
        p.trade_date,
        p.close,
        p.adj_factor,
        c.cal_rn,
        lag(c.cal_rn) over(partition by p.symbol, p.market order by p.trade_date) as prev_rn,
        lag(p.trade_date) over(partition by p.symbol, p.market order by p.trade_date) as prev_date,
        lag(p.close) over(partition by p.symbol, p.market order by p.trade_date) as prev_close,
        lag(p.adj_factor) over(partition by p.symbol, p.market order by p.trade_date) as prev_adj_factor
    from rows_base p
    join cal c on c.trade_date = p.trade_date
)
select
    symbol,
    market,
    prev_date,
    trade_date as next_date,
    (cal_rn - prev_rn - 1) as gap_days,
    prev_close,
    prev_adj_factor,
    prev_rn,
    cal_rn as next_rn
from ranked
where prev_rn is not null
  and cal_rn - prev_rn > 1
  and (cal_rn - prev_rn - 1) <= %s
  and prev_close is not null
order by gap_days desc, symbol
"""

    repair_plan_sql = f"""
with rows_base as (
    select * from pams_ohlcv_daily where {where_sql}
),
cal as (
    select trade_date, row_number() over(order by trade_date) as cal_rn
    from (select distinct trade_date from rows_base) d
),
ranked as (
    select
        p.symbol,
        p.market,
        p.trade_date,
        p.close,
        p.adj_factor,
        c.cal_rn,
        lag(c.cal_rn) over(partition by p.symbol, p.market order by p.trade_date) as prev_rn,
        lag(p.trade_date) over(partition by p.symbol, p.market order by p.trade_date) as prev_date,
        lag(p.close) over(partition by p.symbol, p.market order by p.trade_date) as prev_close,
        lag(p.adj_factor) over(partition by p.symbol, p.market order by p.trade_date) as prev_adj_factor
    from rows_base p
    join cal c on c.trade_date = p.trade_date
),
gaps as (
    select
        symbol,
        market,
        prev_date,
        trade_date as next_date,
        prev_close,
        prev_adj_factor,
        prev_rn,
        cal_rn as next_rn,
        (cal_rn - prev_rn - 1) as gap_days
    from ranked
    where prev_rn is not null
      and cal_rn - prev_rn > 1
      and (cal_rn - prev_rn - 1) <= %s
      and prev_close is not null
),
missing as (
    select
        g.symbol,
        g.market,
        c.trade_date,
        g.prev_date,
        g.next_date,
        g.gap_days,
        g.prev_close,
        g.prev_adj_factor
    from gaps g
    join cal c on c.cal_rn > g.prev_rn and c.cal_rn < g.next_rn
)
select
    symbol,
    market,
    trade_date,
    prev_date,
    next_date,
    gap_days,
    prev_close as fill_price,
    prev_adj_factor as fill_adj_factor
from missing
order by symbol, trade_date
"""

    insert_sql = f"""
with rows_base as (
    select * from pams_ohlcv_daily where {where_sql}
),
cal as (
    select trade_date, row_number() over(order by trade_date) as cal_rn
    from (select distinct trade_date from rows_base) d
),
ranked as (
    select
        p.symbol,
        p.market,
        p.trade_date,
        p.close,
        p.adj_factor,
        c.cal_rn,
        lag(c.cal_rn) over(partition by p.symbol, p.market order by p.trade_date) as prev_rn,
        lag(p.close) over(partition by p.symbol, p.market order by p.trade_date) as prev_close,
        lag(p.adj_factor) over(partition by p.symbol, p.market order by p.trade_date) as prev_adj_factor
    from rows_base p
    join cal c on c.trade_date = p.trade_date
),
gaps as (
    select
        symbol,
        market,
        prev_close,
        prev_adj_factor,
        prev_rn,
        cal_rn as next_rn,
        (cal_rn - prev_rn - 1) as gap_days
    from ranked
    where prev_rn is not null
      and cal_rn - prev_rn > 1
      and (cal_rn - prev_rn - 1) <= %s
      and prev_close is not null
),
missing as (
    select
        g.symbol,
        g.market,
        c.trade_date,
        g.prev_close,
        g.prev_adj_factor
    from gaps g
    join cal c on c.cal_rn > g.prev_rn and c.cal_rn < g.next_rn
)
insert into pams_ohlcv_daily (
    symbol, market, trade_date, open, high, low, close, volume, turnover, adj_factor, limit_up, limit_down, is_suspended
)
select
    symbol,
    market,
    trade_date,
    prev_close,
    prev_close,
    prev_close,
    prev_close,
    0,
    0,
    prev_adj_factor,
    null,
    null,
    true
from missing
on conflict (symbol, market, trade_date) do nothing
returning symbol, market, trade_date
"""

    with _connect() as conn:
        with conn.cursor() as cur:
            segments = _query_all(cur, segments_sql, where_params + [int(args.max_gap_days)])
            plan_rows = _query_all(cur, repair_plan_sql, where_params + [int(args.max_gap_days)])

            inserted_rows: list[dict[str, Any]] = []
            if args.apply:
                inserted_rows = _query_all(cur, insert_sql, where_params + [int(args.max_gap_days)])
                conn.commit()
            else:
                conn.rollback()

    summary = {
        "scope": {
            "start": args.start,
            "end": args.end,
            "symbols_count": len(symbols),
            "symbols": symbols[:200],
            "max_gap_days": int(args.max_gap_days),
            "exclude_bj": bool(args.exclude_bj),
        },
        "segments_selected": len(segments),
        "rows_to_insert": len(plan_rows),
        "rows_inserted": len(inserted_rows),
        "mode": "apply" if args.apply else "dry_run",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(out_dir / "repair_segments.csv", segments)
    sample_rows = plan_rows if len(plan_rows) <= 5000 else plan_rows[:5000]
    _write_csv(out_dir / "repair_plan_sample.csv", sample_rows)
    if inserted_rows:
        _write_csv(out_dir / "inserted_rows.csv", inserted_rows)

    print(json.dumps(_jsonable({"output_dir": str(out_dir), **summary}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
