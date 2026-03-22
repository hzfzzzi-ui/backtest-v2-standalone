from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import cn_side_table_common as common
from . import pams_ohlcv_daily_v2_common as v2_common


AUDIT_COLUMNS = [
    "trade_date",
    "build_run_id",
    "eligible_symbol_count",
    "raw_daily_count",
    "v2_count",
    "daily_basic_join_count",
    "moneyflow_join_count",
    "eligible_missing_daily_count",
    "daily_basic_missing_count",
    "moneyflow_missing_count",
    "turnover_rate_f_null_count",
    "volume_ratio_null_count",
    "float_share_null_count",
    "free_share_null_count",
    "circ_mv_null_count",
    "v1_count",
    "v2_minus_v1",
]


def _frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    records: list[dict[str, Any]] = []
    for item in frame.to_dict(orient="records"):
        normalized: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, (date, datetime)):
                normalized[str(key)] = value.isoformat()
            else:
                normalized[str(key)] = value
        records.append(normalized)
    return records


def _table_exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{common.safe_ident(table)}",))
    return cur.fetchone()[0] is not None


def _require_tables(cur) -> None:
    required = [
        v2_common.V2_MAIN_TABLE,
        v2_common.V2_MONEYFLOW_TABLE,
        v2_common.V2_AUDIT_DAILY_TABLE,
        v2_common.V2_EXCEPTIONS_TABLE,
        v2_common.RAW_DAILY_TABLE,
        v2_common.RAW_MONEYFLOW_TABLE,
        v2_common.RAW_TRADE_CAL_TABLE,
        "pit_security_master",
        "pams_ohlcv_daily",
    ]
    missing = [table for table in required if not _table_exists(cur, table)]
    if missing:
        joined = ", ".join(sorted(missing))
        raise RuntimeError(
            f"missing v2 audit dependencies: {joined}. Build v2 main/side tables first."
        )


def _upsert_rows(
    cur,
    *,
    table: str,
    columns: list[str],
    pk_columns: list[str],
    rows: list[tuple[Any, ...]],
) -> int:
    if not rows:
        return 0
    safe_table = common.safe_ident(table)
    safe_columns = [common.safe_ident(col) for col in columns]
    safe_pk_columns = [common.safe_ident(col) for col in pk_columns]
    update_columns = [col for col in safe_columns if col not in safe_pk_columns]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{col} = EXCLUDED.{col}" for col in update_columns if col not in {"created_at"})
    cur.executemany(
        f"""
        INSERT INTO public.{safe_table} ({", ".join(safe_columns)})
        VALUES ({placeholders})
        ON CONFLICT ({", ".join(safe_pk_columns)}) DO UPDATE SET
            {updates}
        """,
        rows,
    )
    return int(len(rows))


def _insert_exception_rows(cur, rows: list[tuple[Any, ...]]) -> int:
    if not rows:
        return 0
    cur.executemany(
        f"""
        INSERT INTO public.{common.safe_ident(v2_common.V2_EXCEPTIONS_TABLE)} (
            trade_date, symbol, ts_code, issue_type, cause_class, issue_detail, source_table, build_run_id, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    return int(len(rows))


def _load_security_master(conn, symbol_filter: set[str]) -> pd.DataFrame:
    frame = v2_common.df_from_query(
        conn,
        """
        SELECT ts_code, symbol, list_date, delist_date
        FROM public.pit_security_master
        WHERE market_type = 'CN_A'
        ORDER BY ts_code
        """,
    )
    if frame.empty:
        return pd.DataFrame(columns=["ts_code", "symbol", "list_date", "delist_date"])
    frame["symbol"] = frame["symbol"].astype(str).map(v2_common.normalize_stock_symbol)
    frame["list_date"] = pd.to_datetime(frame["list_date"], errors="coerce").dt.date
    frame["delist_date"] = pd.to_datetime(frame["delist_date"], errors="coerce").dt.date
    if symbol_filter:
        frame = frame[frame["symbol"].isin(symbol_filter)].copy()
    return frame.reset_index(drop=True)


def _load_open_trade_dates(conn, start: date, end: date) -> list[date]:
    frame = v2_common.df_from_query(
        conn,
        f"""
        SELECT cal_date
        FROM public.{common.safe_ident(v2_common.RAW_TRADE_CAL_TABLE)}
        WHERE exchange = 'SSE'
          AND cal_date >= %s
          AND cal_date <= %s
          AND is_open = TRUE
        ORDER BY cal_date
        """,
        (start, end),
    )
    if frame.empty:
        return []
    return [item for item in pd.to_datetime(frame["cal_date"], errors="coerce").dt.date.tolist() if item is not None]


def _load_main_rows(conn, trade_date: date, symbol_filter: set[str]) -> pd.DataFrame:
    query = f"""
        SELECT symbol, ts_code, market, market_phase, trade_date, row_status, is_suspended,
               pre_close, pre_close_source, pre_close_confidence,
               open, high, low, close, volume, turnover, adj_factor, adj_factor_source, adj_factor_confidence,
               limit_up, limit_down, source_daily_present, source_daily_basic_present, source_suspend_present,
               turnover_rate, turnover_rate_source, turnover_rate_confidence,
               turnover_rate_f, volume_ratio, float_share, free_share, circ_mv
        FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
        WHERE trade_date = %s
        ORDER BY symbol
    """
    params: tuple[Any, ...] = (trade_date,)
    if symbol_filter:
        query = f"""
            SELECT symbol, ts_code, market, market_phase, trade_date, row_status, is_suspended,
                   pre_close, pre_close_source, pre_close_confidence,
                   open, high, low, close, volume, turnover, adj_factor, adj_factor_source, adj_factor_confidence,
                   limit_up, limit_down, source_daily_present, source_daily_basic_present, source_suspend_present,
                   turnover_rate, turnover_rate_source, turnover_rate_confidence,
                   turnover_rate_f, volume_ratio, float_share, free_share, circ_mv
            FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
            WHERE trade_date = %s
              AND symbol = ANY(%s)
            ORDER BY symbol
        """
        params = (trade_date, sorted(symbol_filter))
    frame = v2_common.df_from_query(conn, query, params)
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "ts_code",
                "market",
                "market_phase",
                "trade_date",
                "row_status",
                "is_suspended",
                "pre_close",
                "pre_close_source",
                "pre_close_confidence",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "turnover",
                "adj_factor",
                "adj_factor_source",
                "adj_factor_confidence",
                "limit_up",
                "limit_down",
                "source_daily_present",
                "source_daily_basic_present",
                "source_suspend_present",
                "turnover_rate",
                "turnover_rate_source",
                "turnover_rate_confidence",
                "turnover_rate_f",
                "volume_ratio",
                "float_share",
                "free_share",
                "circ_mv",
            ]
        )
    frame["symbol"] = frame["symbol"].astype(str).map(v2_common.normalize_stock_symbol)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
    return frame


def _load_side_rows(conn, trade_date: date, symbol_filter: set[str]) -> pd.DataFrame:
    query = f"""
        SELECT symbol, trade_date, source_moneyflow_present, net_fields_present
        FROM public.{common.safe_ident(v2_common.V2_MONEYFLOW_TABLE)}
        WHERE trade_date = %s
        ORDER BY symbol
    """
    params: tuple[Any, ...] = (trade_date,)
    if symbol_filter:
        query = f"""
            SELECT symbol, trade_date, source_moneyflow_present, net_fields_present
            FROM public.{common.safe_ident(v2_common.V2_MONEYFLOW_TABLE)}
            WHERE trade_date = %s
              AND symbol = ANY(%s)
            ORDER BY symbol
        """
        params = (trade_date, sorted(symbol_filter))
    frame = v2_common.df_from_query(conn, query, params)
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "trade_date", "source_moneyflow_present", "net_fields_present"])
    frame["symbol"] = frame["symbol"].astype(str).map(v2_common.normalize_stock_symbol)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
    return frame


def _count_raw_daily(conn, trade_date: date, symbol_filter: set[str]) -> int:
    query = f"SELECT COUNT(*) AS rows FROM public.{common.safe_ident(v2_common.RAW_DAILY_TABLE)} WHERE trade_date = %s"
    params: tuple[Any, ...] = (trade_date,)
    if symbol_filter:
        ts_codes = [v2_common.symbol_to_tushare_code(symbol) for symbol in sorted(symbol_filter)]
        query += " AND ts_code = ANY(%s)"
        params = (trade_date, ts_codes)
    frame = v2_common.df_from_query(conn, query, params)
    return int(frame.iloc[0]["rows"]) if not frame.empty else 0


def _count_v1_rows(conn, trade_date: date, symbol_filter: set[str]) -> int:
    query = "SELECT COUNT(*) AS rows FROM public.pams_ohlcv_daily WHERE market = 'CN_A' AND trade_date = %s"
    params: tuple[Any, ...] = (trade_date,)
    if symbol_filter:
        query += " AND symbol = ANY(%s)"
        params = (trade_date, sorted(symbol_filter))
    frame = v2_common.df_from_query(conn, query, params)
    return int(frame.iloc[0]["rows"]) if not frame.empty else 0


def _load_raw_only_moneyflow_samples(conn, trade_date: date, symbol_filter: set[str], limit: int = 20) -> pd.DataFrame:
    query = f"""
        SELECT rm.ts_code
        FROM public.{common.safe_ident(v2_common.RAW_MONEYFLOW_TABLE)} AS rm
        LEFT JOIN public.{common.safe_ident(v2_common.V2_MAIN_TABLE)} AS v2
          ON v2.ts_code = rm.ts_code
         AND v2.trade_date = rm.trade_date
        WHERE rm.trade_date = %s
          AND v2.ts_code IS NULL
        ORDER BY rm.ts_code
        LIMIT %s
    """
    params: tuple[Any, ...] = (trade_date, limit)
    if symbol_filter:
        ts_codes = [v2_common.symbol_to_tushare_code(symbol) for symbol in sorted(symbol_filter)]
        query = f"""
            SELECT rm.ts_code
            FROM public.{common.safe_ident(v2_common.RAW_MONEYFLOW_TABLE)} AS rm
            LEFT JOIN public.{common.safe_ident(v2_common.V2_MAIN_TABLE)} AS v2
              ON v2.ts_code = rm.ts_code
             AND v2.trade_date = rm.trade_date
            WHERE rm.trade_date = %s
              AND rm.ts_code = ANY(%s)
              AND v2.ts_code IS NULL
            ORDER BY rm.ts_code
            LIMIT %s
        """
        params = (trade_date, ts_codes, limit)
    frame = v2_common.df_from_query(conn, query, params)
    if frame.empty:
        return pd.DataFrame(columns=["ts_code"])
    frame["ts_code"] = frame["ts_code"].astype(str).str.upper().str.strip()
    return frame


def _count_distinct_exception_rows(
    conn,
    *,
    start: date,
    end: date,
    issue_types: set[str],
    symbol_filter: set[str],
) -> int:
    if not issue_types:
        return 0
    query = f"""
        SELECT COUNT(*) AS rows
        FROM (
            SELECT DISTINCT trade_date, COALESCE(symbol, ''), issue_type
            FROM public.{common.safe_ident(v2_common.V2_EXCEPTIONS_TABLE)}
            WHERE trade_date >= %s
              AND trade_date <= %s
              AND issue_type = ANY(%s)
              AND COALESCE(symbol, '') <> ''
        ) AS dedup
    """
    params: tuple[Any, ...] = (start, end, sorted(issue_types))
    if symbol_filter:
        query = f"""
            SELECT COUNT(*) AS rows
            FROM (
                SELECT DISTINCT trade_date, COALESCE(symbol, ''), issue_type
                FROM public.{common.safe_ident(v2_common.V2_EXCEPTIONS_TABLE)}
                WHERE trade_date >= %s
                  AND trade_date <= %s
                  AND issue_type = ANY(%s)
                  AND COALESCE(symbol, '') <> ''
                  AND symbol = ANY(%s)
            ) AS dedup
        """
        params = (start, end, sorted(issue_types), sorted(symbol_filter))
    frame = v2_common.df_from_query(conn, query, params)
    return int(frame.iloc[0]["rows"]) if not frame.empty else 0


def _load_exception_breakdown(
    conn,
    *,
    start: date,
    end: date,
    symbol_filter: set[str],
) -> pd.DataFrame:
    query = f"""
        SELECT
            COALESCE(v2.market_phase,
                CASE
                    WHEN e.symbol LIKE 'sh%%' THEN 'sh'
                    WHEN e.symbol LIKE 'sz%%' THEN 'sz'
                    WHEN e.symbol LIKE 'bj%%' AND e.trade_date < DATE '2021-11-15' THEN 'bj_pre_20211115'
                    WHEN e.symbol LIKE 'bj%%' THEN 'bj_post_20211115'
                    ELSE 'unknown'
                END
            ) AS market_phase,
            e.issue_type,
            COALESCE(e.cause_class, 'unknown') AS cause_class,
            COUNT(*) AS rows
        FROM public.{common.safe_ident(v2_common.V2_EXCEPTIONS_TABLE)} e
        LEFT JOIN public.{common.safe_ident(v2_common.V2_MAIN_TABLE)} v2
          ON v2.symbol = e.symbol
         AND v2.trade_date = e.trade_date
        WHERE e.trade_date >= %s
          AND e.trade_date <= %s
          AND COALESCE(e.symbol, '') <> ''
        GROUP BY 1,2,3
        ORDER BY 1,2,3
    """
    params: tuple[Any, ...] = (start, end)
    if symbol_filter:
        query = f"""
            SELECT
                COALESCE(v2.market_phase,
                    CASE
                        WHEN e.symbol LIKE 'sh%%' THEN 'sh'
                        WHEN e.symbol LIKE 'sz%%' THEN 'sz'
                        WHEN e.symbol LIKE 'bj%%' AND e.trade_date < DATE '2021-11-15' THEN 'bj_pre_20211115'
                        WHEN e.symbol LIKE 'bj%%' THEN 'bj_post_20211115'
                        ELSE 'unknown'
                    END
                ) AS market_phase,
                e.issue_type,
                COALESCE(e.cause_class, 'unknown') AS cause_class,
                COUNT(*) AS rows
            FROM public.{common.safe_ident(v2_common.V2_EXCEPTIONS_TABLE)} e
            LEFT JOIN public.{common.safe_ident(v2_common.V2_MAIN_TABLE)} v2
              ON v2.symbol = e.symbol
             AND v2.trade_date = e.trade_date
            WHERE e.trade_date >= %s
              AND e.trade_date <= %s
              AND COALESCE(e.symbol, '') <> ''
              AND e.symbol = ANY(%s)
            GROUP BY 1,2,3
            ORDER BY 1,2,3
        """
        params = (start, end, sorted(symbol_filter))
    return v2_common.df_from_query(conn, query, params)


def _load_key_exception_drilldown(
    conn,
    *,
    start: date,
    end: date,
    symbol_filter: set[str],
) -> dict[str, pd.DataFrame]:
    issue_types = [
        "eligible_no_source",
        "turnover_rate_imputed_zero",
        "pre_close_imputed_zero",
    ]
    base_where = """
        WHERE e.trade_date >= %s
          AND e.trade_date <= %s
          AND e.issue_type = ANY(%s)
          AND COALESCE(e.symbol, '') <> ''
    """
    base_params: list[Any] = [start, end, issue_types]
    symbol_clause = ""
    if symbol_filter:
        symbol_clause = " AND e.symbol = ANY(%s)"
        base_params.append(sorted(symbol_filter))
    by_year = v2_common.df_from_query(
        conn,
        f"""
        SELECT
            EXTRACT(YEAR FROM e.trade_date)::INT AS year,
            e.issue_type,
            COUNT(*) AS rows
        FROM public.{common.safe_ident(v2_common.V2_EXCEPTIONS_TABLE)} e
        {base_where}
        {symbol_clause}
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        tuple(base_params),
    )
    by_phase = v2_common.df_from_query(
        conn,
        f"""
        SELECT
            COALESCE(v2.market_phase,
                CASE
                    WHEN e.symbol LIKE 'sh%%' THEN 'sh'
                    WHEN e.symbol LIKE 'sz%%' THEN 'sz'
                    WHEN e.symbol LIKE 'bj%%' AND e.trade_date < DATE '2021-11-15' THEN 'bj_pre_20211115'
                    WHEN e.symbol LIKE 'bj%%' THEN 'bj_post_20211115'
                    ELSE 'unknown'
                END
            ) AS market_phase,
            e.issue_type,
            COUNT(*) AS rows
        FROM public.{common.safe_ident(v2_common.V2_EXCEPTIONS_TABLE)} e
        LEFT JOIN public.{common.safe_ident(v2_common.V2_MAIN_TABLE)} v2
          ON v2.symbol = e.symbol
         AND v2.trade_date = e.trade_date
        {base_where}
        {symbol_clause}
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        tuple(base_params),
    )
    top_symbols = v2_common.df_from_query(
        conn,
        f"""
        SELECT
            e.issue_type,
            e.symbol,
            COUNT(*) AS rows
        FROM public.{common.safe_ident(v2_common.V2_EXCEPTIONS_TABLE)} e
        {base_where}
        {symbol_clause}
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC, 2
        LIMIT 200
        """,
        tuple(base_params),
    )
    return {
        "by_year": by_year,
        "by_phase": by_phase,
        "top_symbols": top_symbols,
    }


def _load_runtime_exclusion_breakdown(
    conn,
    *,
    start: date,
    end: date,
    symbol_filter: set[str],
) -> pd.DataFrame:
    base_where = """
        WHERE trade_date >= %s
          AND trade_date <= %s
    """
    params: list[Any] = [start, end]
    if symbol_filter:
        base_where += " AND symbol = ANY(%s)"
        params.append(sorted(symbol_filter))
    return v2_common.df_from_query(
        conn,
        f"""
        SELECT market_phase, exclusion_reason, COUNT(*) AS rows
        FROM (
            SELECT
                market_phase,
                CASE
                    WHEN row_status = 'source_unresolved' THEN 'row_status_source_unresolved'
                    WHEN row_status = 'synthetic_gap_fill' THEN 'row_status_synthetic_gap_fill'
                    WHEN pre_close_confidence < 1 THEN 'low_pre_close_confidence'
                    WHEN adj_factor_confidence < 1 THEN 'low_adj_factor_confidence'
                    WHEN turnover_rate_confidence < 1 AND is_suspended = FALSE THEN 'low_turnover_rate_confidence'
                    ELSE 'runtime_eligible'
                END AS exclusion_reason
            FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
            {base_where}
        ) t
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        tuple(params),
    )


def _load_runtime_quality_drilldown(
    conn,
    *,
    start: date,
    end: date,
    symbol_filter: set[str],
) -> dict[str, pd.DataFrame]:
    base_where = """
        WHERE trade_date >= %s
          AND trade_date <= %s
    """
    params: list[Any] = [start, end]
    if symbol_filter:
        base_where += " AND symbol = ANY(%s)"
        params.append(sorted(symbol_filter))

    low_turnover_by_source = v2_common.df_from_query(
        conn,
        f"""
        SELECT
            market_phase,
            turnover_rate_source,
            row_status,
            COUNT(*) AS rows
        FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
        {base_where}
          AND turnover_rate_confidence < 1
          AND is_suspended = FALSE
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
        """,
        tuple(params),
    )
    low_turnover_top_symbols = v2_common.df_from_query(
        conn,
        f"""
        SELECT
            market_phase,
            turnover_rate_source,
            symbol,
            COUNT(*) AS rows
        FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
        {base_where}
          AND turnover_rate_confidence < 1
          AND is_suspended = FALSE
        GROUP BY 1, 2, 3
        ORDER BY rows DESC, market_phase, turnover_rate_source, symbol
        LIMIT 200
        """,
        tuple(params),
    )
    low_turnover_samples = v2_common.df_from_query(
        conn,
        f"""
        SELECT
            trade_date,
            symbol,
            ts_code,
            market_phase,
            row_status,
            turnover_rate_source,
            turnover_rate_confidence,
            source_daily_present,
            source_daily_basic_present,
            source_suspend_present,
            volume,
            turnover_rate,
            float_share,
            free_share
        FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
        {base_where}
          AND turnover_rate_confidence < 1
          AND is_suspended = FALSE
        ORDER BY trade_date, symbol
        LIMIT 500
        """,
        tuple(params),
    )
    unresolved_by_year = v2_common.df_from_query(
        conn,
        f"""
        SELECT
            EXTRACT(YEAR FROM trade_date)::INT AS year,
            market_phase,
            COUNT(*) AS rows
        FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
        {base_where}
          AND row_status = 'source_unresolved'
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        tuple(params),
    )
    unresolved_top_symbols = v2_common.df_from_query(
        conn,
        f"""
        SELECT
            market_phase,
            symbol,
            COUNT(*) AS rows
        FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
        {base_where}
          AND row_status = 'source_unresolved'
        GROUP BY 1, 2
        ORDER BY rows DESC, market_phase, symbol
        LIMIT 200
        """,
        tuple(params),
    )
    unresolved_samples = v2_common.df_from_query(
        conn,
        f"""
        SELECT
            trade_date,
            symbol,
            ts_code,
            market_phase,
            pre_close_source,
            pre_close_confidence,
            adj_factor_source,
            adj_factor_confidence,
            turnover_rate_source,
            turnover_rate_confidence,
            source_daily_present,
            source_adj_factor_present,
            source_daily_basic_present,
            source_stk_limit_present,
            source_suspend_present
        FROM public.{common.safe_ident(v2_common.V2_MAIN_TABLE)}
        {base_where}
          AND row_status = 'source_unresolved'
        ORDER BY trade_date, symbol
        LIMIT 500
        """,
        tuple(params),
    )
    return {
        "low_turnover_by_source": low_turnover_by_source,
        "low_turnover_top_symbols": low_turnover_top_symbols,
        "low_turnover_samples": low_turnover_samples,
        "unresolved_by_year": unresolved_by_year,
        "unresolved_top_symbols": unresolved_top_symbols,
        "unresolved_samples": unresolved_samples,
    }


def _build_trade_date_audit(
    *,
    trade_date: date,
    eligible_count: int,
    raw_daily_count: int,
    main_frame: pd.DataFrame,
    side_frame: pd.DataFrame,
    v1_count: int,
) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    merged = main_frame.merge(side_frame, on=["symbol", "trade_date"], how="left")
    v2_count = int(len(main_frame))
    source_daily_present = pd.Series(merged.get("source_daily_present", False), index=merged.index).fillna(False).astype(bool)
    source_daily_basic_present = (
        pd.Series(merged.get("source_daily_basic_present", False), index=merged.index).fillna(False).astype(bool)
    )
    source_suspend_present = pd.Series(merged.get("source_suspend_present", False), index=merged.index).fillna(False).astype(bool)
    source_moneyflow_present = pd.Series(merged.get("source_moneyflow_present", False), index=merged.index).fillna(False).astype(bool)
    hard_field_null_count = 0
    if not merged.empty:
        hard_field_null_mask = pd.Series(False, index=merged.index)
        for column in v2_common.HARD_FIELDS:
            if column not in merged.columns:
                hard_field_null_mask = pd.Series(True, index=merged.index)
                break
            hard_field_null_mask = hard_field_null_mask | merged[column].isna()
        hard_field_null_count = int(hard_field_null_mask.sum())
    row_status_series = merged["row_status"].astype(str)
    traded_mask = row_status_series == "traded"
    daily_basic_join_count = int(source_daily_basic_present.sum())
    moneyflow_join_count = int(source_moneyflow_present.loc[traded_mask].sum())
    eligible_missing_daily_count = int(
        (
            row_status_series.isin(["synthetic_gap_fill", "source_unresolved"])
            & (~source_daily_present)
            & (~source_suspend_present)
        ).sum()
    )
    daily_basic_missing_count = int((~source_daily_basic_present).sum())
    moneyflow_missing_count = int((traded_mask & ~source_moneyflow_present).sum())
    turnover_rate_f_null_count = int(pd.to_numeric(merged["turnover_rate_f"], errors="coerce").isna().sum())
    volume_ratio_null_count = int(pd.to_numeric(merged["volume_ratio"], errors="coerce").isna().sum())
    float_share_null_count = int(pd.to_numeric(merged["float_share"], errors="coerce").isna().sum())
    free_share_null_count = int(pd.to_numeric(merged["free_share"], errors="coerce").isna().sum())
    circ_mv_null_count = int(pd.to_numeric(merged["circ_mv"], errors="coerce").isna().sum())
    row = {
        "trade_date": trade_date,
        "eligible_symbol_count": int(eligible_count),
        "raw_daily_count": int(raw_daily_count),
        "v2_count": v2_count,
        "daily_basic_join_count": daily_basic_join_count,
        "moneyflow_join_count": moneyflow_join_count,
        "eligible_missing_daily_count": eligible_missing_daily_count,
        "daily_basic_missing_count": daily_basic_missing_count,
        "moneyflow_missing_count": moneyflow_missing_count,
        "hard_field_null_count": hard_field_null_count,
        "turnover_rate_f_null_count": turnover_rate_f_null_count,
        "volume_ratio_null_count": volume_ratio_null_count,
        "float_share_null_count": float_share_null_count,
        "free_share_null_count": free_share_null_count,
        "circ_mv_null_count": circ_mv_null_count,
        "v1_count": int(v1_count),
        "v2_minus_v1": int(v2_count - v1_count),
        "market_phase_counts": (
            merged["market_phase"].astype(str).value_counts(dropna=False).sort_index().to_dict()
            if "market_phase" in merged.columns and not merged.empty
            else {}
        ),
        "row_status_counts": row_status_series.value_counts(dropna=False).sort_index().to_dict() if not merged.empty else {},
    }
    exception_rows: list[tuple[Any, ...]] = []
    now = datetime.now()
    if eligible_missing_daily_count > 0:
        exception_rows.append(
            (
                trade_date,
                None,
                None,
                "eligible_no_source",
                "missing_in_all_sources",
                f"eligible_missing_daily_count={eligible_missing_daily_count}",
                v2_common.V2_MAIN_TABLE,
                "",
                now,
            )
        )
    if daily_basic_missing_count > 0:
        exception_rows.append(
            (
                trade_date,
                None,
                None,
                "daily_basic_missing",
                "fallback_available",
                f"daily_basic_missing_count={daily_basic_missing_count}",
                v2_common.V2_MAIN_TABLE,
                "",
                now,
            )
        )
    if moneyflow_missing_count > 0:
        exception_rows.append(
            (
                trade_date,
                None,
                None,
                "moneyflow_missing",
                "missing_in_all_sources",
                f"moneyflow_missing_count={moneyflow_missing_count}",
                v2_common.V2_MONEYFLOW_TABLE,
                "",
                now,
            )
        )
    if hard_field_null_count > 0:
        exception_rows.append(
            (
                trade_date,
                None,
                None,
                "hard_field_null_after_build",
                "build_rule_rejected",
                f"hard_field_null_count={hard_field_null_count}",
                v2_common.V2_MAIN_TABLE,
                "",
                now,
            )
        )
    soft_total = turnover_rate_f_null_count + volume_ratio_null_count + float_share_null_count + free_share_null_count + circ_mv_null_count
    if soft_total > 0:
        detail = (
            f"turnover_rate_f={turnover_rate_f_null_count}, "
            f"volume_ratio={volume_ratio_null_count}, "
            f"float_share={float_share_null_count}, "
            f"free_share={free_share_null_count}, "
            f"circ_mv={circ_mv_null_count}"
        )
        exception_rows.append(
            (
                trade_date,
                None,
                None,
                "soft_field_null_after_build",
                "source_present_low_confidence_fill",
                detail,
                v2_common.V2_MAIN_TABLE,
                "",
                now,
            )
        )
    return row, exception_rows


def _build_runtime_gate(
    runtime_breakdown: pd.DataFrame,
    *,
    row_status_totals: dict[str, int],
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in runtime_breakdown.itertuples(index=False):
        reason = str(row.exclusion_reason)
        if reason == "runtime_eligible":
            continue
        counts[reason] = counts.get(reason, 0) + int(row.rows)
    runtime_eligible_rows = 0
    if not runtime_breakdown.empty:
        eligible_rows = runtime_breakdown[runtime_breakdown["exclusion_reason"] == "runtime_eligible"]
        runtime_eligible_rows = int(eligible_rows["rows"].sum()) if not eligible_rows.empty else 0
    return {
        "unresolved_rows": int(row_status_totals.get("source_unresolved", 0)),
        "synthetic_gap_fill_rows": int(row_status_totals.get("synthetic_gap_fill", 0)),
        "excluded_low_pre_close_confidence_rows": int(counts.get("low_pre_close_confidence", 0)),
        "excluded_low_adj_factor_confidence_rows": int(counts.get("low_adj_factor_confidence", 0)),
        "excluded_low_turnover_rate_confidence_rows": int(counts.get("low_turnover_rate_confidence", 0)),
        "runtime_eligible_rows": int(runtime_eligible_rows),
        "exclusion_breakdown": counts,
        "can_consume_v10_1": bool(not counts),
    }


def build_update_args(
    *,
    start: str = "",
    end: str = "",
    symbols_csv: str = "",
    output_dir: str = "",
    heartbeat_path: str = "",
    heartbeat_label: str = "",
    apply: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        start=str(start or ""),
        end=str(end or ""),
        symbols_csv=str(symbols_csv or ""),
        output_dir=str(output_dir or ""),
        heartbeat_path=str(heartbeat_path or ""),
        heartbeat_label=str(heartbeat_label or ""),
        apply=bool(apply),
    )


def run_update(args: argparse.Namespace) -> dict[str, Any]:
    latest_before = common.get_latest_trade_date(v2_common.V2_AUDIT_DAILY_TABLE)
    start, latest_before = common.infer_start_date(str(args.start or ""), v2_common.V2_AUDIT_DAILY_TABLE)
    run_id = v2_common.build_run_id("v2_audit")
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (v2_common.DEFAULT_OUTPUT_ROOT / f"pams_ohlcv_daily_v2_audit_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)
    heartbeat_path = str(getattr(args, "heartbeat_path", "") or "").strip()
    heartbeat_label = str(getattr(args, "heartbeat_label", "") or "").strip() or "pams_ohlcv_daily_v2_audit"

    summary: dict[str, Any]
    latest_after: date | None = latest_before

    v2_common.touch_heartbeat(
        heartbeat_path,
        step=heartbeat_label,
        status="running",
        extra={"build_run_id": run_id, "phase": "start"},
    )

    try:
        with common.connect() as conn:
            with conn.cursor() as cur:
                _require_tables(cur)
                cur.execute("SET statement_timeout = '1200000ms'")
                if str(args.end or "").strip():
                    end = date.fromisoformat(str(args.end).strip())
                else:
                    open_dates = _load_open_trade_dates(conn, start, date.today())
                    end = max(open_dates) if open_dates else start
                symbol_filter = common.parse_symbols_csv(str(args.symbols_csv or ""))
                trade_dates = _load_open_trade_dates(conn, start, end)
                security_master = _load_security_master(conn, symbol_filter)

                summary = {
                    "status": "ok",
                    "apply": bool(args.apply),
                    "build_run_id": run_id,
                    "date_range": {"start": start.isoformat(), "end": end.isoformat()},
                    "latest_trade_date_before": latest_before.isoformat() if latest_before else None,
                    "latest_trade_date_after": latest_before.isoformat() if latest_before else None,
                    "open_trade_dates": [item.isoformat() for item in trade_dates],
                    "symbol_filter_count": int(len(symbol_filter)),
                    "per_trade_date": [],
                    "exception_rows": 0,
                    "gate": {},
                }

                audit_rows: list[tuple[Any, ...]] = []
                exception_rows: list[tuple[Any, ...]] = []
                for trade_date in trade_dates:
                    eligible_count = int(
                        len(
                            security_master[
                                (security_master["list_date"].isna() | (security_master["list_date"] <= trade_date))
                                & (security_master["delist_date"].isna() | (security_master["delist_date"] >= trade_date))
                            ]
                        )
                    )
                    raw_daily_count = _count_raw_daily(conn, trade_date, symbol_filter)
                    main_frame = _load_main_rows(conn, trade_date, symbol_filter)
                    side_frame = _load_side_rows(conn, trade_date, symbol_filter)
                    v1_count = _count_v1_rows(conn, trade_date, symbol_filter)
                    row, aggregate_exceptions = _build_trade_date_audit(
                        trade_date=trade_date,
                        eligible_count=eligible_count,
                        raw_daily_count=raw_daily_count,
                        main_frame=main_frame,
                        side_frame=side_frame,
                        v1_count=v1_count,
                    )
                    summary["per_trade_date"].append({k: (v.isoformat() if isinstance(v, date) else v) for k, v in row.items()})
                    audit_rows.append(
                        (
                            row["trade_date"],
                            run_id,
                            row["eligible_symbol_count"],
                            row["raw_daily_count"],
                            row["v2_count"],
                            row["daily_basic_join_count"],
                            row["moneyflow_join_count"],
                            row["eligible_missing_daily_count"],
                            row["daily_basic_missing_count"],
                            row["moneyflow_missing_count"],
                            row["turnover_rate_f_null_count"],
                            row["volume_ratio_null_count"],
                            row["float_share_null_count"],
                            row["free_share_null_count"],
                            row["circ_mv_null_count"],
                            row["v1_count"],
                            row["v2_minus_v1"],
                            datetime.now(),
                        )
                    )
                    for raw_only in _load_raw_only_moneyflow_samples(conn, trade_date, symbol_filter).itertuples(index=False):
                        aggregate_exceptions.append(
                            (
                                trade_date,
                                v2_common.normalize_stock_symbol(str(raw_only.ts_code)),
                                str(raw_only.ts_code).upper(),
                                "raw_only_not_in_master",
                                "build_rule_rejected",
                                "raw moneyflow row exists without v2 main key",
                                v2_common.RAW_MONEYFLOW_TABLE,
                                "",
                                datetime.now(),
                            )
                        )
                    exception_rows.extend(aggregate_exceptions)
                    v2_common.touch_heartbeat(
                        heartbeat_path,
                        step=heartbeat_label,
                        trade_date=trade_date,
                        status="running",
                        extra={"build_run_id": run_id, "phase": "trade_date_scanned"},
                    )

                if audit_rows:
                    _upsert_rows(
                        cur,
                        table=v2_common.V2_AUDIT_DAILY_TABLE,
                        columns=[*AUDIT_COLUMNS, "created_at"],
                        pk_columns=["trade_date", "build_run_id"],
                        rows=audit_rows,
                    )
                if exception_rows:
                    exception_rows = [
                        (
                            item[0],
                            item[1],
                            item[2],
                            item[3],
                            item[4],
                            item[5],
                            item[6],
                            run_id,
                            item[8],
                        )
                        for item in exception_rows
                    ]
                    _insert_exception_rows(cur, exception_rows)
                summary["exception_rows"] = int(len(exception_rows))
                critical_exception_rows = _count_distinct_exception_rows(
                    conn,
                    start=start,
                    end=end,
                    issue_types=v2_common.CRITICAL_BUILD_ISSUE_TYPES,
                    symbol_filter=symbol_filter,
                )
                exception_breakdown = _load_exception_breakdown(
                    conn,
                    start=start,
                    end=end,
                    symbol_filter=symbol_filter,
                )
                key_exception_drilldown = _load_key_exception_drilldown(
                    conn,
                    start=start,
                    end=end,
                    symbol_filter=symbol_filter,
                )
                runtime_exclusion_breakdown = _load_runtime_exclusion_breakdown(
                    conn,
                    start=start,
                    end=end,
                    symbol_filter=symbol_filter,
                )
                runtime_quality_drilldown = _load_runtime_quality_drilldown(
                    conn,
                    start=start,
                    end=end,
                    symbol_filter=symbol_filter,
                )

                market_phase_totals: dict[str, int] = {}
                row_status_totals: dict[str, int] = {}
                for item in summary["per_trade_date"]:
                    for key, value in (item.get("market_phase_counts") or {}).items():
                        market_phase_totals[str(key)] = market_phase_totals.get(str(key), 0) + int(value)
                    for key, value in (item.get("row_status_counts") or {}).items():
                        row_status_totals[str(key)] = row_status_totals.get(str(key), 0) + int(value)

                canonical_gate = {
                    "eligible_no_source_rows": int(
                        sum(int(item["eligible_missing_daily_count"]) for item in summary["per_trade_date"])
                    ),
                    "v2_minus_v1_total": int(sum(int(item["v2_minus_v1"]) for item in summary["per_trade_date"])),
                    "hard_field_null_rows": int(
                        sum(int(item.get("hard_field_null_count", 0)) for item in summary["per_trade_date"])
                    ),
                    "critical_exception_rows": int(critical_exception_rows),
                    "has_full_window": bool(start == v2_common.DEFAULT_BACKFILL_START and end == v2_common.OFFICIAL_END_DATE),
                    "market_phase_totals": market_phase_totals,
                    "row_status_totals": row_status_totals,
                }
                canonical_gate["can_promote_shadow"] = bool(
                    canonical_gate["eligible_no_source_rows"] == 0 and canonical_gate["hard_field_null_rows"] == 0
                )
                runtime_gate = _build_runtime_gate(
                    runtime_exclusion_breakdown,
                    row_status_totals=row_status_totals,
                )
                summary["gate"] = {
                    "canonical": canonical_gate,
                    "runtime": runtime_gate,
                }
                summary["exception_breakdown_by_phase"] = (
                    _frame_to_records(exception_breakdown)
                )
                summary["runtime_exclusion_breakdown"] = (
                    _frame_to_records(runtime_exclusion_breakdown)
                )
                summary["key_exception_drilldown"] = {
                    name: _frame_to_records(frame)
                    for name, frame in key_exception_drilldown.items()
                }
                summary["runtime_quality_drilldown"] = {
                    name: _frame_to_records(frame)
                    for name, frame in runtime_quality_drilldown.items()
                }

                if args.apply:
                    conn.commit()
                    latest_after = common.get_latest_trade_date(v2_common.V2_AUDIT_DAILY_TABLE)
                else:
                    conn.rollback()
                    summary["status"] = "dry_run"
    except Exception:
        v2_common.touch_heartbeat(
            heartbeat_path,
            step=heartbeat_label,
            status="failed",
            extra={"build_run_id": run_id, "phase": "failed"},
        )
        raise

    summary["latest_trade_date_after"] = latest_after.isoformat() if latest_after else None
    audit_path = output_dir / "pams_ohlcv_daily_v2_audit_daily.csv"
    pd.DataFrame(summary["per_trade_date"]).to_csv(audit_path, index=False)
    summary["audit_csv"] = str(audit_path)
    exception_breakdown_path = output_dir / "pams_ohlcv_daily_v2_exception_breakdown_by_phase.csv"
    pd.DataFrame(summary.get("exception_breakdown_by_phase", [])).to_csv(exception_breakdown_path, index=False)
    summary["exception_breakdown_csv"] = str(exception_breakdown_path)
    runtime_exclusion_path = output_dir / "pams_ohlcv_daily_v2_runtime_exclusion_breakdown.csv"
    pd.DataFrame(summary.get("runtime_exclusion_breakdown", [])).to_csv(runtime_exclusion_path, index=False)
    summary["runtime_exclusion_breakdown_csv"] = str(runtime_exclusion_path)
    key_exception_by_year_path = output_dir / "pams_ohlcv_daily_v2_key_exception_by_year.csv"
    pd.DataFrame(summary.get("key_exception_drilldown", {}).get("by_year", [])).to_csv(key_exception_by_year_path, index=False)
    summary["key_exception_by_year_csv"] = str(key_exception_by_year_path)
    key_exception_by_phase_path = output_dir / "pams_ohlcv_daily_v2_key_exception_by_phase.csv"
    pd.DataFrame(summary.get("key_exception_drilldown", {}).get("by_phase", [])).to_csv(key_exception_by_phase_path, index=False)
    summary["key_exception_by_phase_csv"] = str(key_exception_by_phase_path)
    key_exception_top_symbols_path = output_dir / "pams_ohlcv_daily_v2_key_exception_top_symbols.csv"
    pd.DataFrame(summary.get("key_exception_drilldown", {}).get("top_symbols", [])).to_csv(key_exception_top_symbols_path, index=False)
    summary["key_exception_top_symbols_csv"] = str(key_exception_top_symbols_path)
    low_turnover_by_source_path = output_dir / "pams_ohlcv_daily_v2_low_turnover_confidence_by_source.csv"
    pd.DataFrame(summary.get("runtime_quality_drilldown", {}).get("low_turnover_by_source", [])).to_csv(low_turnover_by_source_path, index=False)
    summary["low_turnover_by_source_csv"] = str(low_turnover_by_source_path)
    low_turnover_top_symbols_path = output_dir / "pams_ohlcv_daily_v2_low_turnover_confidence_top_symbols.csv"
    pd.DataFrame(summary.get("runtime_quality_drilldown", {}).get("low_turnover_top_symbols", [])).to_csv(low_turnover_top_symbols_path, index=False)
    summary["low_turnover_top_symbols_csv"] = str(low_turnover_top_symbols_path)
    low_turnover_samples_path = output_dir / "pams_ohlcv_daily_v2_low_turnover_confidence_samples.csv"
    pd.DataFrame(summary.get("runtime_quality_drilldown", {}).get("low_turnover_samples", [])).to_csv(low_turnover_samples_path, index=False)
    summary["low_turnover_samples_csv"] = str(low_turnover_samples_path)
    unresolved_by_year_path = output_dir / "pams_ohlcv_daily_v2_source_unresolved_by_year.csv"
    pd.DataFrame(summary.get("runtime_quality_drilldown", {}).get("unresolved_by_year", [])).to_csv(unresolved_by_year_path, index=False)
    summary["unresolved_by_year_csv"] = str(unresolved_by_year_path)
    unresolved_top_symbols_path = output_dir / "pams_ohlcv_daily_v2_source_unresolved_top_symbols.csv"
    pd.DataFrame(summary.get("runtime_quality_drilldown", {}).get("unresolved_top_symbols", [])).to_csv(unresolved_top_symbols_path, index=False)
    summary["unresolved_top_symbols_csv"] = str(unresolved_top_symbols_path)
    unresolved_samples_path = output_dir / "pams_ohlcv_daily_v2_source_unresolved_samples.csv"
    pd.DataFrame(summary.get("runtime_quality_drilldown", {}).get("unresolved_samples", [])).to_csv(unresolved_samples_path, index=False)
    summary["unresolved_samples_csv"] = str(unresolved_samples_path)
    summary_path = output_dir / "summary.json"
    common.write_json(summary_path, summary)
    v2_common.touch_heartbeat(
        heartbeat_path,
        step=heartbeat_label,
        status=summary["status"],
        extra={"build_run_id": run_id, "phase": "completed"},
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit pams_ohlcv_daily_v2 coverage and promotion gates")
    parser.add_argument("--start", default="", help="inclusive start date YYYY-MM-DD; default latest audit date + 1 or 2007-01-04")
    parser.add_argument("--end", default="", help="inclusive end date YYYY-MM-DD; default latest open date from raw trade calendar")
    parser.add_argument("--symbols-csv", default="", help="optional comma-separated symbols for smoke runs")
    parser.add_argument("--output-dir", default="", help="output directory for summary/audit artifacts")
    parser.add_argument("--heartbeat-path", default="", help="optional heartbeat JSON path updated during long-running audit")
    parser.add_argument("--heartbeat-label", default="", help="optional logical step name written to heartbeat JSON")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_update(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={Path(summary['audit_csv']).parent / 'summary.json'}")


if __name__ == "__main__":
    main()
