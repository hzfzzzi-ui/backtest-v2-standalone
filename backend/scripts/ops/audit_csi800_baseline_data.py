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


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "ops"
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"
DEFAULT_BASELINE_ID = "baseline_V10"
DEFAULT_INDEX_CODE = "000906.SH"
CSI800_LAUNCH_DATE = date(2007, 1, 15)


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


def _baseline_config_path(baseline_id: str) -> Path:
    return ROOT / "outputs" / "baselines" / baseline_id / "config.json"


def _load_baseline_config(baseline_id: str) -> dict[str, Any]:
    path = _baseline_config_path(baseline_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _minus_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year - years)


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


def _init_temp_tables(cur, index_code: str) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE tmp_csi800_membership AS
        SELECT
            lower(
                CASE
                    WHEN symbol LIKE '%%.SH' THEN 'sh' || split_part(symbol, '.', 1)
                    WHEN symbol LIKE '%%.SZ' THEN 'sz' || split_part(symbol, '.', 1)
                    WHEN symbol LIKE '%%.BJ' THEN 'bj' || split_part(symbol, '.', 1)
                    ELSE symbol
                END
            ) AS symbol,
            start_date,
            COALESCE(end_date, CURRENT_DATE) AS end_date
        FROM public.pit_index_constituents
        WHERE index_code = %s
        """,
        (index_code,),
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tmp_csi800_membership_symbol_dates ON tmp_csi800_membership(symbol, start_date, end_date)")
    cur.execute(
        """
        CREATE TEMP TABLE tmp_csi800_symbols AS
        SELECT
            symbol AS ts_symbol,
            lower(
                CASE
                    WHEN symbol LIKE '%%.SH' THEN 'sh' || split_part(symbol, '.', 1)
                    WHEN symbol LIKE '%%.SZ' THEN 'sz' || split_part(symbol, '.', 1)
                    WHEN symbol LIKE '%%.BJ' THEN 'bj' || split_part(symbol, '.', 1)
                    ELSE symbol
                END
            ) AS symbol,
            MIN(start_date) AS first_constituent_date,
            MAX(COALESCE(end_date, CURRENT_DATE)) AS last_constituent_date
        FROM public.pit_index_constituents
        WHERE index_code = %s
        GROUP BY symbol
        """,
        (index_code,),
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tmp_csi800_symbols_symbol ON tmp_csi800_symbols(symbol)")
    cur.execute(
        """
        CREATE TEMP TABLE tmp_csi800_st AS
        SELECT
            lower(
                CASE
                    WHEN ts_code LIKE '%%.SH' THEN 'sh' || split_part(ts_code, '.', 1)
                    WHEN ts_code LIKE '%%.SZ' THEN 'sz' || split_part(ts_code, '.', 1)
                    WHEN ts_code LIKE '%%.BJ' THEN 'bj' || split_part(ts_code, '.', 1)
                    ELSE ts_code
                END
            ) AS symbol,
            start_date,
            end_date,
            st_type
        FROM public.pit_st_history
        WHERE lower(
                CASE
                    WHEN ts_code LIKE '%%.SH' THEN 'sh' || split_part(ts_code, '.', 1)
                    WHEN ts_code LIKE '%%.SZ' THEN 'sz' || split_part(ts_code, '.', 1)
                    WHEN ts_code LIKE '%%.BJ' THEN 'bj' || split_part(ts_code, '.', 1)
                    ELSE ts_code
                END
            ) IN (SELECT symbol FROM tmp_csi800_symbols)
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tmp_csi800_st_symbol_dates ON tmp_csi800_st(symbol, start_date, end_date)")


def _query_table_coverage(cur) -> dict[str, Any]:
    df = _fetchdf(
        cur,
        """
        SELECT 'pams_ohlcv_daily_cn_a' AS item, MIN(trade_date) AS min_date, MAX(trade_date) AS max_date, COUNT(*) AS rows
        FROM public.pams_ohlcv_daily WHERE market = 'CN_A'
        UNION ALL
        SELECT 'pams_ohlcv_daily_cn_index', MIN(trade_date), MAX(trade_date), COUNT(*)
        FROM public.pams_ohlcv_daily WHERE market = 'CN_INDEX'
        UNION ALL
        SELECT 'pit_index_daily', MIN(trade_date), MAX(trade_date), COUNT(*)
        FROM public.pit_index_daily
        UNION ALL
        SELECT 'pit_security_master', MIN(list_date), MAX(COALESCE(delist_date, CURRENT_DATE)), COUNT(*)
        FROM public.pit_security_master
        UNION ALL
        SELECT 'pit_st_history', MIN(start_date), MAX(COALESCE(end_date, CURRENT_DATE)), COUNT(*)
        FROM public.pit_st_history
        """,
    )
    return {
        str(row.item): {
            "min_date": None if pd.isna(row.min_date) else pd.Timestamp(row.min_date).date().isoformat(),
            "max_date": None if pd.isna(row.max_date) else pd.Timestamp(row.max_date).date().isoformat(),
            "rows": int(row.rows or 0),
        }
        for row in df.itertuples(index=False)
    }


def _query_constituent_audit(cur, index_code: str, audit_start: date, audit_end: date) -> dict[str, Any]:
    rows, _ = _fetchall(
        cur,
        """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT symbol) AS distinct_symbols,
            COUNT(*) FILTER (WHERE start_date IS NULL) AS null_start_rows,
            COUNT(*) FILTER (WHERE end_date IS NOT NULL AND end_date <= start_date) AS invalid_ranges
        FROM public.pit_index_constituents
        WHERE index_code = %s
        """,
        (index_code,),
    )
    row = rows[0]
    overlap_rows, _ = _fetchall(
        cur,
        """
        WITH ordered AS (
            SELECT
                symbol,
                start_date,
                end_date,
                LAG(COALESCE(end_date, DATE '9999-12-31')) OVER (
                    PARTITION BY symbol
                    ORDER BY start_date, COALESCE(end_date, DATE '9999-12-31')
                ) AS prev_end
            FROM public.pit_index_constituents
            WHERE index_code = %s
        )
        SELECT COUNT(*) AS overlap_rows
        FROM ordered
        WHERE prev_end IS NOT NULL
          AND start_date < prev_end
        """,
        (index_code,),
    )
    sources = _fetchdf(
        cur,
        """
        SELECT COALESCE(source, '<null>') AS source, COUNT(*) AS rows
        FROM public.pit_index_constituents
        WHERE index_code = %s
        GROUP BY 1
        ORDER BY 2 DESC, 1
        """,
        (index_code,),
    )
    check_dates = [
        CSI800_LAUNCH_DATE,
        date(2007, 2, 1),
        date(2008, 1, 1),
        date(2010, 1, 4),
        audit_start,
        audit_end,
    ]
    counts: list[dict[str, Any]] = []
    for check_date in check_dates:
        count_rows, _ = _fetchall(
            cur,
            """
            SELECT COUNT(DISTINCT symbol)
            FROM public.pit_index_constituents
            WHERE index_code = %s
              AND start_date <= %s
              AND (end_date IS NULL OR end_date > %s)
            """,
            (index_code, check_date, check_date),
        )
        counts.append({"date": check_date.isoformat(), "count": int(count_rows[0][0] or 0)})
    return {
        "index_code": index_code,
        "total_rows": int(row[0] or 0),
        "distinct_symbols": int(row[1] or 0),
        "null_start_rows": int(row[2] or 0),
        "invalid_ranges": int(row[3] or 0),
        "overlap_rows": int(overlap_rows[0][0] or 0),
        "source_breakdown": [
            {"source": str(item.source), "rows": int(item.rows or 0)}
            for item in sources.itertuples(index=False)
        ],
        "check_dates": counts,
    }


def _query_symbol_coverage(cur) -> tuple[dict[str, Any], pd.DataFrame]:
    coverage = _fetchdf(
        cur,
        """
        WITH ohlcv AS (
            SELECT symbol, MIN(trade_date) AS first_td, MAX(trade_date) AS last_td
            FROM public.pams_ohlcv_daily
            WHERE market = 'CN_A'
            GROUP BY symbol
        ),
        sm AS (
            SELECT symbol, MIN(list_date) AS list_date, MAX(delist_date) AS delist_date, MAX(name) AS name
            FROM public.pit_security_master
            GROUP BY symbol
        )
        SELECT
            COUNT(*) AS total_symbols,
            COUNT(*) FILTER (WHERE ohlcv.symbol IS NULL) AS no_ohlcv_symbols,
            COUNT(*) FILTER (WHERE sm.symbol IS NULL) AS no_security_master_symbols,
            COUNT(*) FILTER (WHERE ohlcv.first_td IS NOT NULL AND ohlcv.first_td > tmp.first_constituent_date) AS ohlcv_late_start_symbols,
            COUNT(*) FILTER (WHERE sm.list_date IS NOT NULL AND sm.list_date > tmp.first_constituent_date) AS security_master_late_list_symbols,
            COUNT(*) FILTER (
                WHERE ohlcv.last_td IS NOT NULL
                  AND ohlcv.last_td < tmp.last_constituent_date
                  AND tmp.last_constituent_date < CURRENT_DATE
            ) AS ohlcv_early_end_symbols,
            COUNT(*) FILTER (
                WHERE sm.list_date = DATE '2010-01-04'
                  AND tmp.first_constituent_date < DATE '2010-01-04'
            ) AS sentinel_2010_listdate_symbols
        FROM tmp_csi800_symbols AS tmp
        LEFT JOIN ohlcv USING(symbol)
        LEFT JOIN sm USING(symbol)
        """,
    )
    detail = _fetchdf(
        cur,
        """
        WITH ohlcv AS (
            SELECT symbol, MIN(trade_date) AS first_td, MAX(trade_date) AS last_td
            FROM public.pams_ohlcv_daily
            WHERE market = 'CN_A'
            GROUP BY symbol
        ),
        sm AS (
            SELECT symbol, MIN(list_date) AS list_date, MAX(delist_date) AS delist_date, MAX(name) AS name
            FROM public.pit_security_master
            GROUP BY symbol
        )
        SELECT
            tmp.ts_symbol,
            tmp.symbol,
            tmp.first_constituent_date,
            tmp.last_constituent_date,
            ohlcv.first_td,
            ohlcv.last_td,
            sm.list_date,
            sm.delist_date,
            sm.name
        FROM tmp_csi800_symbols AS tmp
        LEFT JOIN ohlcv USING(symbol)
        LEFT JOIN sm USING(symbol)
        WHERE ohlcv.symbol IS NULL
           OR sm.symbol IS NULL
           OR (ohlcv.first_td IS NOT NULL AND ohlcv.first_td > tmp.first_constituent_date)
           OR (sm.list_date IS NOT NULL AND sm.list_date > tmp.first_constituent_date)
           OR (
                ohlcv.last_td IS NOT NULL
                AND ohlcv.last_td < tmp.last_constituent_date
                AND tmp.last_constituent_date < CURRENT_DATE
           )
        ORDER BY tmp.first_constituent_date, tmp.ts_symbol
        """,
    )
    row = coverage.iloc[0]
    return {
        "total_symbols": int(row.total_symbols or 0),
        "no_ohlcv_symbols": int(row.no_ohlcv_symbols or 0),
        "no_security_master_symbols": int(row.no_security_master_symbols or 0),
        "ohlcv_late_start_symbols": int(row.ohlcv_late_start_symbols or 0),
        "security_master_late_list_symbols": int(row.security_master_late_list_symbols or 0),
        "ohlcv_early_end_symbols": int(row.ohlcv_early_end_symbols or 0),
        "sentinel_2010_listdate_symbols": int(row.sentinel_2010_listdate_symbols or 0),
    }, detail


def _query_ohlcv_quality(cur, audit_start: date, audit_end: date) -> dict[str, Any]:
    frame = _fetchdf(
        cur,
        """
        WITH base AS (
            SELECT
                o.symbol,
                o.trade_date,
                o.open,
                o.high,
                o.low,
                o.close,
                o.volume,
                o.turnover,
                o.adj_factor,
                o.limit_up,
                o.limit_down,
                o.is_suspended,
                ROW_NUMBER() OVER (PARTITION BY o.symbol ORDER BY o.trade_date) AS rn
            FROM public.pams_ohlcv_daily AS o
            JOIN tmp_csi800_membership AS m
              ON m.symbol = o.symbol
             AND o.trade_date >= m.start_date
             AND o.trade_date <= m.end_date
            WHERE o.market = 'CN_A'
              AND o.trade_date >= %s
              AND o.trade_date <= %s
        )
        SELECT
            COUNT(*) AS total_rows,
            COUNT(*) FILTER (WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0) AS nonpositive_price_rows,
            COUNT(*) FILTER (WHERE volume < 0 OR turnover < 0) AS negative_liquidity_rows,
            COUNT(*) FILTER (WHERE adj_factor IS NULL) AS missing_adj_factor_rows,
            COUNT(*) FILTER (WHERE adj_factor <= 0) AS nonpositive_adj_factor_rows,
            COUNT(*) FILTER (WHERE rn > 1 AND (limit_up IS NULL OR limit_down IS NULL)) AS missing_limit_price_rows_after_first_bar,
            COUNT(*) FILTER (WHERE limit_up IS NOT NULL AND limit_down IS NOT NULL AND limit_up <= limit_down) AS invalid_limit_band_rows,
            COUNT(*) FILTER (WHERE COALESCE(volume, 0) = 0 AND COALESCE(turnover, 0) = 0 AND COALESCE(is_suspended, FALSE) = FALSE) AS zero_activity_not_suspended_rows,
            COUNT(*) FILTER (WHERE COALESCE(is_suspended, FALSE) = TRUE AND (COALESCE(volume, 0) > 0 OR COALESCE(turnover, 0) > 0)) AS suspended_with_activity_rows
        FROM base
        """,
        (audit_start, audit_end),
    )
    row = frame.iloc[0]
    return {column: int(row[column] or 0) for column in frame.columns}


def _query_limit_audit(cur, audit_start: date, audit_end: date) -> tuple[dict[str, Any], pd.DataFrame]:
    summary = _fetchdf(
        cur,
        """
        WITH base AS (
            SELECT
                o.symbol,
                o.trade_date,
                o.close,
                o.adj_factor,
                o.limit_up,
                o.limit_down,
                LAG(o.close) OVER (PARTITION BY o.symbol ORDER BY o.trade_date) AS prev_close,
                LAG(o.adj_factor) OVER (PARTITION BY o.symbol ORDER BY o.trade_date) AS prev_adj_factor
            FROM public.pams_ohlcv_daily AS o
            JOIN tmp_csi800_membership AS m
              ON m.symbol = o.symbol
             AND o.trade_date >= m.start_date
             AND o.trade_date <= m.end_date
            WHERE o.market = 'CN_A'
              AND o.trade_date >= %s
              AND o.trade_date <= %s
        ),
        scored AS (
            SELECT
                b.*,
                EXISTS (
                    SELECT 1
                    FROM tmp_csi800_st AS st
                    WHERE st.symbol = b.symbol
                      AND st.start_date <= b.trade_date
                      AND (st.end_date IS NULL OR st.end_date >= b.trade_date)
                ) AS is_st
            FROM base AS b
            WHERE b.prev_close IS NOT NULL
        ),
        checked AS (
            SELECT
                *,
                CASE
                    WHEN prev_adj_factor IS NULL OR adj_factor IS NULL OR prev_adj_factor <= 0 OR adj_factor <= 0 THEN FALSE
                    WHEN ABS((adj_factor / prev_adj_factor) - 1.0) > 0.01 THEN TRUE
                    ELSE FALSE
                END AS has_adj_jump,
                CASE
                    WHEN symbol LIKE 'bj%%' AND trade_date >= DATE '2021-11-15' THEN 0.30
                    WHEN symbol LIKE 'sh688%%' AND trade_date >= DATE '2019-07-22' THEN 0.20
                    WHEN symbol LIKE 'sz301%%' THEN 0.20
                    WHEN symbol LIKE 'sz300%%' AND trade_date >= DATE '2020-08-24' THEN 0.20
                    WHEN is_st THEN 0.05
                    ELSE 0.10
                END AS limit_pct
            FROM scored
        )
        SELECT
            COUNT(*) FILTER (WHERE NOT has_adj_jump) AS comparable_rows,
            COUNT(*) FILTER (WHERE has_adj_jump) AS adj_jump_rows_excluded,
            COUNT(*) FILTER (
                WHERE NOT has_adj_jump
                  AND (
                        limit_up IS NULL
                     OR ABS(limit_up - ROUND(prev_close * (1.0 + limit_pct), 4)) > 0.011
                  )
            ) AS limit_up_mismatch_rows,
            COUNT(*) FILTER (
                WHERE NOT has_adj_jump
                  AND (
                        limit_down IS NULL
                     OR ABS(limit_down - ROUND(prev_close * (1.0 - limit_pct), 4)) > 0.011
                  )
            ) AS limit_down_mismatch_rows
        FROM checked
        """,
        (audit_start, audit_end),
    )
    detail = _fetchdf(
        cur,
        """
        WITH base AS (
            SELECT
                o.symbol,
                o.trade_date,
                o.close,
                o.adj_factor,
                o.limit_up,
                o.limit_down,
                LAG(o.close) OVER (PARTITION BY o.symbol ORDER BY o.trade_date) AS prev_close,
                LAG(o.adj_factor) OVER (PARTITION BY o.symbol ORDER BY o.trade_date) AS prev_adj_factor
            FROM public.pams_ohlcv_daily AS o
            JOIN tmp_csi800_membership AS m
              ON m.symbol = o.symbol
             AND o.trade_date >= m.start_date
             AND o.trade_date <= m.end_date
            WHERE o.market = 'CN_A'
              AND o.trade_date >= %s
              AND o.trade_date <= %s
        ),
        scored AS (
            SELECT
                b.*,
                EXISTS (
                    SELECT 1
                    FROM tmp_csi800_st AS st
                    WHERE st.symbol = b.symbol
                      AND st.start_date <= b.trade_date
                      AND (st.end_date IS NULL OR st.end_date >= b.trade_date)
                ) AS is_st
            FROM base AS b
            WHERE b.prev_close IS NOT NULL
        ),
        checked AS (
            SELECT
                *,
                CASE
                    WHEN prev_adj_factor IS NULL OR adj_factor IS NULL OR prev_adj_factor <= 0 OR adj_factor <= 0 THEN FALSE
                    WHEN ABS((adj_factor / prev_adj_factor) - 1.0) > 0.01 THEN TRUE
                    ELSE FALSE
                END AS has_adj_jump,
                CASE
                    WHEN symbol LIKE 'bj%%' AND trade_date >= DATE '2021-11-15' THEN 0.30
                    WHEN symbol LIKE 'sh688%%' AND trade_date >= DATE '2019-07-22' THEN 0.20
                    WHEN symbol LIKE 'sz301%%' THEN 0.20
                    WHEN symbol LIKE 'sz300%%' AND trade_date >= DATE '2020-08-24' THEN 0.20
                    WHEN is_st THEN 0.05
                    ELSE 0.10
                END AS limit_pct
            FROM scored
        )
        SELECT
            symbol,
            trade_date,
            prev_close,
            limit_up,
            ROUND(prev_close * (1.0 + limit_pct), 4) AS expected_limit_up,
            limit_down,
            ROUND(prev_close * (1.0 - limit_pct), 4) AS expected_limit_down,
            is_st
        FROM checked
        WHERE NOT has_adj_jump
          AND (
                limit_up IS NULL
             OR limit_down IS NULL
             OR ABS(limit_up - ROUND(prev_close * (1.0 + limit_pct), 4)) > 0.011
             OR ABS(limit_down - ROUND(prev_close * (1.0 - limit_pct), 4)) > 0.011
          )
        ORDER BY trade_date, symbol
        LIMIT 500
        """,
        (audit_start, audit_end),
    )
    row = summary.iloc[0]
    return {column: int(row[column] or 0) for column in summary.columns}, detail


def _query_list_delist_audit(cur, audit_start: date, audit_end: date) -> tuple[dict[str, Any], pd.DataFrame]:
    summary = _fetchdf(
        cur,
        """
        WITH sm AS (
            SELECT symbol, list_date, delist_date, name
            FROM public.pit_security_master
        )
        SELECT
            COUNT(*) FILTER (WHERE sm.list_date IS NOT NULL AND o.trade_date < sm.list_date) AS before_list_rows,
            COUNT(*) FILTER (WHERE sm.delist_date IS NOT NULL AND o.trade_date > sm.delist_date) AS after_delist_rows
        FROM public.pams_ohlcv_daily AS o
        JOIN tmp_csi800_membership AS m
          ON m.symbol = o.symbol
         AND o.trade_date >= m.start_date
         AND o.trade_date <= m.end_date
        LEFT JOIN sm
          ON sm.symbol = o.symbol
        WHERE o.market = 'CN_A'
          AND o.trade_date >= %s
          AND o.trade_date <= %s
        """,
        (audit_start, audit_end),
    )
    detail = _fetchdf(
        cur,
        """
        WITH sm AS (
            SELECT symbol, list_date, delist_date, name
            FROM public.pit_security_master
        )
        SELECT
            o.symbol,
            sm.name,
            o.trade_date,
            sm.list_date,
            sm.delist_date
        FROM public.pams_ohlcv_daily AS o
        JOIN tmp_csi800_membership AS m
          ON m.symbol = o.symbol
         AND o.trade_date >= m.start_date
         AND o.trade_date <= m.end_date
        LEFT JOIN sm
          ON sm.symbol = o.symbol
        WHERE o.market = 'CN_A'
          AND o.trade_date >= %s
          AND o.trade_date <= %s
          AND (
                (sm.list_date IS NOT NULL AND o.trade_date < sm.list_date)
             OR (sm.delist_date IS NOT NULL AND o.trade_date > sm.delist_date)
          )
        ORDER BY o.trade_date, o.symbol
        LIMIT 500
        """,
        (audit_start, audit_end),
    )
    row = summary.iloc[0]
    return {column: int(row[column] or 0) for column in summary.columns}, detail


def _query_st_audit(cur) -> dict[str, Any]:
    summary = _fetchdf(
        cur,
        """
        SELECT
            COUNT(*) AS total_records,
            COUNT(DISTINCT symbol) AS distinct_symbols,
            COUNT(*) FILTER (WHERE end_date IS NOT NULL AND end_date < start_date) AS invalid_ranges
        FROM tmp_csi800_st
        """,
    )
    overlap = _fetchdf(
        cur,
        """
        WITH ordered AS (
            SELECT
                symbol,
                start_date,
                end_date,
                LAG(COALESCE(end_date, DATE '9999-12-31')) OVER (
                    PARTITION BY symbol
                    ORDER BY start_date, COALESCE(end_date, DATE '9999-12-31')
                ) AS prev_end
            FROM tmp_csi800_st
        )
        SELECT COUNT(*) AS overlap_rows
        FROM ordered
        WHERE prev_end IS NOT NULL
          AND start_date <= prev_end
        """,
    )
    base = summary.iloc[0]
    return {
        "total_records": int(base.total_records or 0),
        "distinct_symbols": int(base.distinct_symbols or 0),
        "invalid_ranges": int(base.invalid_ranges or 0),
        "overlap_rows": int(overlap.iloc[0].overlap_rows or 0),
    }


def _query_benchmark_coverage(cur, audit_start: date, audit_end: date) -> dict[str, Any]:
    pit = _fetchdf(
        cur,
        """
        SELECT
            MIN(trade_date) AS min_date,
            MAX(trade_date) AS max_date,
            COUNT(*) AS rows
        FROM public.pit_index_daily
        WHERE index_code IN ('000300.SH', '000905.SH')
          AND trade_date >= %s
          AND trade_date <= %s
        """,
        (audit_start, audit_end),
    )
    cn_index = _fetchdf(
        cur,
        """
        SELECT
            MIN(trade_date) AS min_date,
            MAX(trade_date) AS max_date,
            COUNT(*) AS rows
        FROM public.pams_ohlcv_daily
        WHERE market = 'CN_INDEX'
          AND symbol IN ('sh000300', 'sh000905')
          AND trade_date >= %s
          AND trade_date <= %s
        """,
        (audit_start, audit_end),
    )
    return {
        "pit_index_daily": {
            "min_date": None if pd.isna(pit.iloc[0].min_date) else pd.Timestamp(pit.iloc[0].min_date).date().isoformat(),
            "max_date": None if pd.isna(pit.iloc[0].max_date) else pd.Timestamp(pit.iloc[0].max_date).date().isoformat(),
            "rows": int(pit.iloc[0].rows or 0),
        },
        "pams_ohlcv_daily_cn_index": {
            "min_date": None if pd.isna(cn_index.iloc[0].min_date) else pd.Timestamp(cn_index.iloc[0].min_date).date().isoformat(),
            "max_date": None if pd.isna(cn_index.iloc[0].max_date) else pd.Timestamp(cn_index.iloc[0].max_date).date().isoformat(),
            "rows": int(cn_index.iloc[0].rows or 0),
        },
    }


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    baseline_id = str(args.baseline_id or DEFAULT_BASELINE_ID).strip() or DEFAULT_BASELINE_ID
    baseline_cfg = _load_baseline_config(baseline_id)
    universe_cfg = dict((baseline_cfg.get("universe") or {}))
    baseline_start = date.fromisoformat(str(args.baseline_start or universe_cfg.get("start") or "2016-03-01"))
    baseline_end = date.fromisoformat(str(args.baseline_end or universe_cfg.get("end") or "2026-03-01"))
    requested_start = _minus_years(baseline_start, int(args.lookback_years))
    audit_start = max(requested_start, CSI800_LAUNCH_DATE)
    audit_end = baseline_end

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"csi800_baseline_data_audit_{ts}")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "baseline_id": baseline_id,
        "index_code": str(args.index_code),
        "baseline_window": {"start": baseline_start.isoformat(), "end": baseline_end.isoformat()},
        "requested_lookback_years": int(args.lookback_years),
        "requested_audit_start": requested_start.isoformat(),
        "effective_audit_window": {"start": audit_start.isoformat(), "end": audit_end.isoformat()},
        "csi800_launch_date": CSI800_LAUNCH_DATE.isoformat(),
        "facts": {},
        "artifacts": {},
    }

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '1200000ms'")
            _init_temp_tables(cur, str(args.index_code))

            summary["facts"]["table_coverage"] = _query_table_coverage(cur)
            summary["facts"]["constituents"] = _query_constituent_audit(cur, str(args.index_code), audit_start, audit_end)
            coverage_summary, coverage_detail = _query_symbol_coverage(cur)
            summary["facts"]["symbol_coverage"] = coverage_summary
            summary["facts"]["ohlcv_quality"] = _query_ohlcv_quality(cur, audit_start, audit_end)
            limit_summary, limit_detail = _query_limit_audit(cur, audit_start, audit_end)
            summary["facts"]["limit_price_audit"] = limit_summary
            list_delist_summary, list_delist_detail = _query_list_delist_audit(cur, audit_start, audit_end)
            summary["facts"]["list_delist_audit"] = list_delist_summary
            summary["facts"]["st_audit"] = _query_st_audit(cur)
            summary["facts"]["benchmark_coverage"] = _query_benchmark_coverage(cur, audit_start, audit_end)

    coverage_csv = output_dir / "coverage_issues.csv"
    coverage_detail.to_csv(coverage_csv, index=False)
    summary["artifacts"]["coverage_issues_csv"] = str(coverage_csv)

    limit_csv = output_dir / "limit_mismatch_examples.csv"
    limit_detail.to_csv(limit_csv, index=False)
    summary["artifacts"]["limit_mismatch_examples_csv"] = str(limit_csv)

    list_delist_csv = output_dir / "list_delist_issues.csv"
    list_delist_detail.to_csv(list_delist_csv, index=False)
    summary["artifacts"]["list_delist_issues_csv"] = str(list_delist_csv)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit CSI800 baseline data coverage and integrity")
    parser.add_argument("--baseline-id", default=DEFAULT_BASELINE_ID)
    parser.add_argument("--baseline-start", default="", help="override baseline start date YYYY-MM-DD")
    parser.add_argument("--baseline-end", default="", help="override baseline end date YYYY-MM-DD")
    parser.add_argument("--lookback-years", type=int, default=10, help="audit window extends this many years before baseline start")
    parser.add_argument("--index-code", default=DEFAULT_INDEX_CODE)
    parser.add_argument("--output-dir", default="", help="output directory for audit artifacts")
    args = parser.parse_args()

    summary = run_audit(args)
    summary_path = Path(summary["artifacts"]["coverage_issues_csv"]).parent / "audit_report.json"
    _write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"audit_json={summary_path}")


if __name__ == "__main__":
    main()
