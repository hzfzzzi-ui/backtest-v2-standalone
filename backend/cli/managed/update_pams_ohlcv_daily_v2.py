from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import cn_side_table_common as common
from . import pams_ohlcv_daily_v2_common as v2_common


MAIN_COLUMNS = [
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
    "turnover_rate",
    "turnover_rate_source",
    "turnover_rate_confidence",
    "turnover_rate_f",
    "volume_ratio",
    "float_share",
    "free_share",
    "circ_mv",
    "source_daily_present",
    "source_adj_factor_present",
    "source_daily_basic_present",
    "source_stk_limit_present",
    "source_suspend_present",
    "build_run_id",
    "build_version",
]


def _table_exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{common.safe_ident(table)}",))
    return cur.fetchone()[0] is not None


def _require_tables(cur) -> None:
    required = [
        v2_common.RAW_TRADE_CAL_TABLE,
        v2_common.RAW_DAILY_TABLE,
        v2_common.RAW_ADJ_FACTOR_TABLE,
        v2_common.RAW_DAILY_BASIC_TABLE,
        v2_common.RAW_SUSPEND_TABLE,
        v2_common.RAW_STK_LIMIT_TABLE,
        v2_common.V2_MAIN_TABLE,
        "pit_security_master",
    ]
    missing = [table for table in required if not _table_exists(cur, table)]
    if missing:
        joined = ", ".join(sorted(missing))
        raise RuntimeError(
            f"missing v2 dependencies: {joined}. Apply docs/db/pams_ohlcv_daily_v2_apply.sql and refresh security_master first."
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
    updates = ", ".join(
        f"{col} = EXCLUDED.{col}" for col in update_columns if col not in {"created_at", "updated_at"}
    )
    cur.executemany(
        f"""
        INSERT INTO public.{safe_table} ({", ".join(safe_columns)})
        VALUES ({placeholders})
        ON CONFLICT ({", ".join(safe_pk_columns)}) DO UPDATE SET
            {updates},
            updated_at = NOW()
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


def _delete_slice_rows(
    cur,
    *,
    table: str,
    start: date,
    end: date,
    symbols: set[str],
) -> int:
    if not symbols:
        return 0
    cur.execute(
        f"""
        DELETE FROM public.{common.safe_ident(table)}
        WHERE trade_date >= %s
          AND trade_date <= %s
          AND symbol = ANY(%s)
        """,
        (start, end, sorted(symbols)),
    )
    return int(cur.rowcount or 0)


def _delete_exception_slice_rows(
    cur,
    *,
    start: date,
    end: date,
    symbols: set[str],
) -> int:
    if not symbols:
        return 0
    cur.execute(
        f"""
        DELETE FROM public.{common.safe_ident(v2_common.V2_EXCEPTIONS_TABLE)}
        WHERE trade_date >= %s
          AND trade_date <= %s
          AND symbol = ANY(%s)
        """,
        (start, end, sorted(symbols)),
    )
    return int(cur.rowcount or 0)


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


def _load_security_master(conn, symbol_filter: set[str]) -> pd.DataFrame:
    frame = v2_common.df_from_query(
        conn,
        """
        SELECT ts_code, symbol, exchange, list_date, delist_date, market_type
        FROM public.pit_security_master
        WHERE market_type = 'CN_A'
        ORDER BY ts_code
        """,
    )
    if frame.empty:
        return pd.DataFrame(columns=["ts_code", "symbol", "exchange", "list_date", "delist_date", "market_type"])
    frame["symbol"] = frame["symbol"].astype(str).map(v2_common.normalize_stock_symbol)
    frame["list_date"] = pd.to_datetime(frame["list_date"], errors="coerce").dt.date
    frame["delist_date"] = pd.to_datetime(frame["delist_date"], errors="coerce").dt.date
    if symbol_filter:
        frame = frame[frame["symbol"].isin(symbol_filter)].copy()
    return frame.reset_index(drop=True)


def _load_prev_state(conn, table: str, start: date, symbol_filter: set[str]) -> dict[str, v2_common.PrevState]:
    query = f"""
        SELECT DISTINCT ON (symbol)
            symbol,
            close,
            adj_factor,
            float_share,
            free_share
        FROM public.{common.safe_ident(table)}
        WHERE trade_date < %s
        ORDER BY symbol, trade_date DESC
    """
    params: tuple[Any, ...] = (start,)
    if symbol_filter:
        query = f"""
            SELECT DISTINCT ON (symbol)
                symbol,
                close,
                adj_factor,
                float_share,
                free_share
            FROM public.{common.safe_ident(table)}
            WHERE trade_date < %s
              AND symbol = ANY(%s)
            ORDER BY symbol, trade_date DESC
        """
        params = (start, sorted(symbol_filter))
    frame = v2_common.df_from_query(conn, query, params)
    state: dict[str, v2_common.PrevState] = {}
    for row in frame.itertuples(index=False):
        symbol = v2_common.normalize_stock_symbol(str(row.symbol))
        state[symbol] = v2_common.PrevState(
            close=v2_common.to_float_or_none(row.close),
            adj_factor=v2_common.to_float_or_none(row.adj_factor),
            float_share=v2_common.to_float_or_none(row.float_share),
            free_share=v2_common.to_float_or_none(row.free_share),
        )
    return state


def _load_trade_date_source(conn, table: str, columns: list[str], trade_date: date) -> pd.DataFrame:
    frame = v2_common.df_from_query(
        conn,
        f"""
        SELECT {", ".join(common.safe_ident(col) for col in columns)}
        FROM public.{common.safe_ident(table)}
        WHERE trade_date = %s
        ORDER BY ts_code
        """,
        (trade_date,),
    )
    if frame.empty:
        return pd.DataFrame(columns=columns)
    frame["ts_code"] = frame["ts_code"].astype(str).str.upper().str.strip()
    frame["symbol"] = frame["ts_code"].map(v2_common.normalize_stock_symbol)
    return frame


def _load_bj_pre_evidence_dates(conn, symbol_filter: set[str]) -> dict[str, set[date]]:
    clauses = ["ts_code LIKE '%%.BJ'"]
    params: list[Any] = []
    if symbol_filter:
        bj_ts_codes = [v2_common.symbol_to_tushare_code(symbol) for symbol in sorted(symbol_filter) if symbol.startswith("bj")]
        if not bj_ts_codes:
            return {}
        clauses.append("ts_code = ANY(%s)")
        params.append(bj_ts_codes)
    where_clause = " AND ".join(clauses)
    evidence: dict[str, set[date]] = {}
    for table in (v2_common.RAW_DAILY_TABLE, v2_common.RAW_SUSPEND_TABLE):
        frame = v2_common.df_from_query(
            conn,
            f"""
            SELECT ts_code, trade_date
            FROM public.{common.safe_ident(table)}
            WHERE {where_clause}
            """,
            tuple(params),
        )
        if frame.empty:
            continue
        frame["symbol"] = frame["ts_code"].astype(str).map(v2_common.normalize_stock_symbol)
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
        frame = frame.dropna(subset=["symbol", "trade_date"])
        for row in frame.itertuples(index=False):
            evidence.setdefault(str(row.symbol), set()).add(row.trade_date)
    return evidence


def _is_st(st_periods: dict[str, list[tuple[date, date | None]]], symbol: str, trade_date: date) -> bool:
    return any(
        start_dt <= trade_date and (end_dt is None or trade_date <= end_dt)
        for start_dt, end_dt in st_periods.get(v2_common.normalize_stock_symbol(symbol), [])
    )


def _resolve_turnover_rate(
    *,
    trade_date: date,
    symbol: str,
    market_phase: str,
    basic_row: dict[str, Any],
    prev_state: v2_common.PrevState | None,
    row_status: str,
    volume: int,
    ak_cache: v2_common.AkShareTurnoverCache,
    exceptions: list[dict[str, Any]],
    ts_code: str,
) -> tuple[float, str, int]:
    if row_status == "suspended_confirmed":
        return 0.0, "suspended_zero", 3
    basic_turnover = v2_common.to_float_or_none(basic_row.get("turnover_rate"))
    if basic_turnover is not None:
        return float(basic_turnover), "tushare_daily_basic", 3
    ak_turnover, ak_source = ak_cache.get(symbol, trade_date, market_phase)
    if ak_turnover is not None:
        if float(ak_turnover) > 0 or volume <= 0 or row_status != "traded":
            ak_confidence = 2 if ak_source == "akshare_stock_zh_a_hist" else 1
            return float(ak_turnover), str(ak_source or "akshare_stock_zh_a_hist"), ak_confidence
    derived = v2_common.derive_turnover_rate(volume, basic_row.get("float_share"))
    if derived is not None:
        return float(derived), "formula_from_float_share", 1
    prev_float_share = prev_state.float_share if prev_state else None
    derived_from_prev = v2_common.derive_turnover_rate(volume, prev_float_share)
    if derived_from_prev is not None:
        return float(derived_from_prev), "formula_from_prev_float_share", 1
    if market_phase == "bj_pre_20211115":
        cause_class = "mapping_failure"
    elif row_status == "source_unresolved":
        cause_class = "missing_in_all_sources"
    else:
        cause_class = "fallback_available"
    exceptions.append(
        {
            "trade_date": trade_date,
            "symbol": symbol,
            "ts_code": ts_code,
            "issue_type": "turnover_rate_imputed_zero",
            "cause_class": cause_class,
            "issue_detail": f"turnover_rate missing after tushare, akshare, and formula fallback; market_phase={market_phase}; ak_source={ak_source or 'none'}; ak_value={ak_turnover}",
            "source_table": v2_common.RAW_DAILY_BASIC_TABLE,
        }
    )
    return 0.0, "imputed_zero", 0


def _resolve_anchor_price(
    *,
    prev_state: v2_common.PrevState | None,
    basic_row: dict[str, Any],
    daily_row: dict[str, Any],
    row_status: str,
    exceptions: list[dict[str, Any]],
    trade_date: date,
    symbol: str,
    ts_code: str,
) -> tuple[float, str, int]:
    candidates = [
        ("daily_pre_close", 3, daily_row.get("pre_close")),
        ("prev_close_carry", 2, prev_state.close if prev_state else None),
        ("basic_close_anchor", 1, basic_row.get("close")),
        ("daily_close_anchor", 1, daily_row.get("close")),
    ]
    for source, confidence, candidate in candidates:
        value = v2_common.to_float_or_none(candidate)
        if value is not None and value > 0:
            return value, source, confidence
    exceptions.append(
        {
            "trade_date": trade_date,
            "symbol": symbol,
            "ts_code": ts_code,
            "issue_type": "pre_close_imputed_zero",
            "cause_class": "source_present_low_confidence_fill",
            "issue_detail": f"failed to resolve anchor price for {row_status} row",
            "source_table": v2_common.RAW_DAILY_TABLE,
        }
    )
    return 0.0, "imputed_zero", 0


def _resolve_adj_factor(
    *,
    adj_value: Any,
    prev_state: v2_common.PrevState | None,
    exceptions: list[dict[str, Any]],
    trade_date: date,
    symbol: str,
    ts_code: str,
) -> tuple[float, str, int]:
    current = v2_common.to_float_or_none(adj_value)
    if current is not None and current > 0:
        return current, "tushare_adj_factor", 3
    previous = prev_state.adj_factor if prev_state else None
    if previous is not None and previous > 0:
        exceptions.append(
            {
                "trade_date": trade_date,
                "symbol": symbol,
                "ts_code": ts_code,
                "issue_type": "adj_factor_missing",
                "cause_class": "source_present_low_confidence_fill",
                "issue_detail": "adj_factor missing on trade_date; carried from previous v2 state",
                "source_table": v2_common.RAW_ADJ_FACTOR_TABLE,
            }
        )
        return previous, "prev_adj_factor_carry", 2
    exceptions.append(
            {
                "trade_date": trade_date,
                "symbol": symbol,
                "ts_code": ts_code,
                "issue_type": "adj_factor_missing",
                "cause_class": "missing_in_all_sources",
                "issue_detail": "adj_factor missing with no previous state; defaulted to 1.0",
                "source_table": v2_common.RAW_ADJ_FACTOR_TABLE,
            }
        )
    return 1.0, "default_1", 0


def _rows_to_upsert(rows: pd.DataFrame) -> list[tuple[Any, ...]]:
    values: list[tuple[Any, ...]] = []
    if rows.empty:
        return values
    now = datetime.now()
    for row in rows.itertuples(index=False):
        row_values: list[Any] = []
        for column in MAIN_COLUMNS:
            value = getattr(row, column)
            if pd.isna(value):
                value = None
            row_values.append(value)
        row_values.append(now)
        row_values.append(now)
        values.append(tuple(row_values))
    return values


def _exceptions_to_rows(exceptions: list[dict[str, Any]], build_run_id: str) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    now = datetime.now()
    for item in exceptions:
        rows.append(
            (
                item.get("trade_date"),
                item.get("symbol"),
                item.get("ts_code"),
                item["issue_type"],
                item.get("cause_class"),
                item.get("issue_detail"),
                item.get("source_table"),
                build_run_id,
                now,
            )
        )
    return rows


def _build_trade_date_rows(
    *,
    trade_date: date,
    eligible_frame: pd.DataFrame,
    daily_frame: pd.DataFrame,
    adj_frame: pd.DataFrame,
    basic_frame: pd.DataFrame,
    suspend_frame: pd.DataFrame,
    limit_frame: pd.DataFrame,
    st_periods: dict[str, list[tuple[date, date | None]]],
    prev_state: dict[str, v2_common.PrevState],
    ak_cache: v2_common.AkShareTurnoverCache,
    bj_pre_evidence_dates: dict[str, set[date]],
    build_run_id: str,
) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    daily_map = {
        row.symbol: row._asdict()
        for row in daily_frame.itertuples(index=False)
    }
    adj_map = {
        row.symbol: row._asdict()
        for row in adj_frame.itertuples(index=False)
    }
    basic_map = {
        row.symbol: row._asdict()
        for row in basic_frame.itertuples(index=False)
    }
    suspend_map = {
        row.symbol: row._asdict()
        for row in suspend_frame.itertuples(index=False)
    }
    limit_map = {
        row.symbol: row._asdict()
        for row in limit_frame.itertuples(index=False)
    }

    built_rows: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    traded_count = 0
    suspended_count = 0
    eligible_no_source_count = 0
    skipped_bj_pre_no_evidence_count = 0

    for sec in eligible_frame.itertuples(index=False):
        symbol = v2_common.normalize_stock_symbol(str(sec.symbol))
        ts_code = str(sec.ts_code).upper()
        current_state = prev_state.get(symbol, v2_common.PrevState())
        daily_row = daily_map.get(symbol, {})
        adj_row = adj_map.get(symbol, {})
        basic_row = basic_map.get(symbol, {})
        suspend_row = suspend_map.get(symbol, {})
        limit_row = limit_map.get(symbol, {})
        daily_present = bool(daily_row)
        suspend_present = bool(suspend_row)
        basic_present = bool(basic_row)
        limit_present = bool(limit_row)
        market_phase = v2_common.market_phase_for_symbol(symbol, trade_date)
        if market_phase == "bj_pre_20211115" and not daily_present and not suspend_present:
            evidence_dates = bj_pre_evidence_dates.get(symbol, set())
            if trade_date not in evidence_dates:
                skipped_bj_pre_no_evidence_count += 1
                continue
        if daily_present:
            row_status = "traded"
        elif suspend_present:
            row_status = "suspended_confirmed"
        else:
            row_status = "source_unresolved"
        if daily_present:
            traded_count += 1
        else:
            suspended_count += 1
            if not suspend_present:
                eligible_no_source_count += 1
                exceptions.append(
                    {
                        "trade_date": trade_date,
                        "symbol": symbol,
                        "ts_code": ts_code,
                        "issue_type": "eligible_no_source",
                        "cause_class": "mapping_failure" if market_phase == "bj_pre_20211115" else "missing_in_all_sources",
                        "issue_detail": "missing raw daily and suspend_d on eligible open trade_date",
                        "source_table": f"{v2_common.RAW_DAILY_TABLE},{v2_common.RAW_SUSPEND_TABLE}",
                    }
                )
        is_suspended = row_status == "suspended_confirmed"
        anchor_price, pre_close_source, pre_close_confidence = _resolve_anchor_price(
            prev_state=current_state,
            basic_row=basic_row,
            daily_row=daily_row,
            row_status=row_status,
            exceptions=exceptions,
            trade_date=trade_date,
            symbol=symbol,
            ts_code=ts_code,
        )
        if daily_present:
            missing_daily_fields = [
                field
                for field in ["open", "high", "low", "close", "pre_close", "vol", "amount"]
                if v2_common.to_float_or_none(daily_row.get(field)) is None
            ]
            if missing_daily_fields:
                exceptions.append(
                    {
                        "trade_date": trade_date,
                        "symbol": symbol,
                        "ts_code": ts_code,
                        "issue_type": "raw_daily_field_missing",
                        "cause_class": "build_rule_rejected",
                        "issue_detail": f"raw daily missing fields: {','.join(missing_daily_fields)}",
                        "source_table": v2_common.RAW_DAILY_TABLE,
                    }
                )
        close_value = v2_common.to_float_or_none(daily_row.get("close"))
        if close_value is None:
            close_value = anchor_price
        open_value = v2_common.to_float_or_none(daily_row.get("open")) if daily_present else anchor_price
        high_value = v2_common.to_float_or_none(daily_row.get("high")) if daily_present else anchor_price
        low_value = v2_common.to_float_or_none(daily_row.get("low")) if daily_present else anchor_price
        volume_value = v2_common.to_int_or_none(
            v2_common.to_float_or_none(daily_row.get("vol")) * 100.0 if daily_present else 0
        ) or 0
        turnover_value = (
            round(v2_common.to_float_or_none(daily_row.get("amount")) * 1000.0, 2)
            if daily_present and v2_common.to_float_or_none(daily_row.get("amount")) is not None
            else 0.0
        )
        adj_factor, adj_factor_source, adj_factor_confidence = _resolve_adj_factor(
            adj_value=adj_row.get("adj_factor"),
            prev_state=current_state,
            exceptions=exceptions,
            trade_date=trade_date,
            symbol=symbol,
            ts_code=ts_code,
        )
        is_st = _is_st(st_periods, symbol, trade_date)
        raw_limit_up = v2_common.to_float_or_none(limit_row.get("up_limit"))
        raw_limit_down = v2_common.to_float_or_none(limit_row.get("down_limit"))
        limit_up, limit_down = raw_limit_up, raw_limit_down
        if limit_up is None or limit_down is None:
            limit_up, limit_down = v2_common.compute_limit_prices(anchor_price, symbol, is_st=is_st)
        if limit_up is None or limit_down is None:
            limit_up = anchor_price
            limit_down = anchor_price
            exceptions.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "ts_code": ts_code,
                    "issue_type": "limit_price_imputed_anchor",
                    "cause_class": "source_present_low_confidence_fill",
                    "issue_detail": "failed to derive limit_up/down; anchored to pre_close",
                    "source_table": v2_common.RAW_STK_LIMIT_TABLE,
                }
            )

        turnover_rate, turnover_rate_source, turnover_rate_confidence = _resolve_turnover_rate(
            trade_date=trade_date,
            symbol=symbol,
            market_phase=market_phase,
            basic_row=basic_row,
            prev_state=current_state,
            row_status=row_status,
            volume=volume_value,
            ak_cache=ak_cache,
            exceptions=exceptions,
            ts_code=ts_code,
        )

        float_share = v2_common.to_float_or_none(basic_row.get("float_share"))
        if float_share is None:
            float_share = current_state.float_share
        if float_share is None and volume_value > 0:
            float_share = v2_common.derive_share_from_turnover_rate(volume_value, turnover_rate)
        free_share = v2_common.to_float_or_none(basic_row.get("free_share"))
        if free_share is None:
            free_share = current_state.free_share
        turnover_rate_f = v2_common.to_float_or_none(basic_row.get("turnover_rate_f"))
        if row_status == "suspended_confirmed" and free_share is not None and turnover_rate_f is None:
            turnover_rate_f = 0.0
        if turnover_rate_f is None and volume_value > 0 and free_share is not None:
            turnover_rate_f = v2_common.derive_turnover_rate(volume_value, free_share)
        if free_share is None and volume_value > 0 and turnover_rate_f is not None:
            free_share = v2_common.derive_share_from_turnover_rate(volume_value, turnover_rate_f)
        volume_ratio = v2_common.to_float_or_none(basic_row.get("volume_ratio"))
        circ_mv = v2_common.to_float_or_none(basic_row.get("circ_mv"))
        if circ_mv is None:
            circ_mv = v2_common.derive_circ_mv(close_value, float_share)

        built_rows.append(
            {
                "symbol": symbol,
                "ts_code": ts_code,
                "market": "CN_A",
                "market_phase": market_phase,
                "trade_date": trade_date,
                "row_status": row_status,
                "is_suspended": bool(is_suspended),
                "pre_close": round(anchor_price, 4),
                "pre_close_source": pre_close_source,
                "pre_close_confidence": int(pre_close_confidence),
                "open": round(open_value if open_value is not None else anchor_price, 4),
                "high": round(high_value if high_value is not None else anchor_price, 4),
                "low": round(low_value if low_value is not None else anchor_price, 4),
                "close": round(close_value if close_value is not None else anchor_price, 4),
                "volume": int(volume_value),
                "turnover": float(round(turnover_value, 2)),
                "adj_factor": round(adj_factor, 6),
                "adj_factor_source": adj_factor_source,
                "adj_factor_confidence": int(adj_factor_confidence),
                "limit_up": round(limit_up, 4),
                "limit_down": round(limit_down, 4),
                "turnover_rate": float(turnover_rate),
                "turnover_rate_source": str(turnover_rate_source),
                "turnover_rate_confidence": int(turnover_rate_confidence),
                "turnover_rate_f": turnover_rate_f,
                "volume_ratio": volume_ratio,
                "float_share": float_share,
                "free_share": free_share,
                "circ_mv": circ_mv,
                "source_daily_present": bool(daily_present),
                "source_adj_factor_present": bool(adj_row),
                "source_daily_basic_present": bool(basic_present),
                "source_stk_limit_present": bool(limit_present),
                "source_suspend_present": bool(suspend_present),
                "build_run_id": build_run_id,
                "build_version": v2_common.BUILD_VERSION,
            }
        )

        prev_state[symbol] = v2_common.PrevState(
            close=close_value,
            adj_factor=adj_factor,
            float_share=float_share,
            free_share=free_share,
        )

    frame = pd.DataFrame(built_rows, columns=MAIN_COLUMNS)
    stats = {
        "trade_date": trade_date.isoformat(),
        "eligible_symbol_count": int(len(eligible_frame)),
        "built_symbol_count": int(len(frame)),
        "traded_rows": int(traded_count),
        "suspended_rows": int(suspended_count),
        "eligible_no_source_rows": int(eligible_no_source_count),
        "skipped_bj_pre_no_evidence_rows": int(skipped_bj_pre_no_evidence_count),
        "turnover_rate_f_null_count": int(pd.to_numeric(frame["turnover_rate_f"], errors="coerce").isna().sum()) if not frame.empty else 0,
        "volume_ratio_null_count": int(pd.to_numeric(frame["volume_ratio"], errors="coerce").isna().sum()) if not frame.empty else 0,
        "float_share_null_count": int(pd.to_numeric(frame["float_share"], errors="coerce").isna().sum()) if not frame.empty else 0,
        "free_share_null_count": int(pd.to_numeric(frame["free_share"], errors="coerce").isna().sum()) if not frame.empty else 0,
        "circ_mv_null_count": int(pd.to_numeric(frame["circ_mv"], errors="coerce").isna().sum()) if not frame.empty else 0,
    }
    return frame, stats, exceptions


def build_update_args(
    *,
    start: str = "",
    end: str = "",
    table: str = v2_common.V2_MAIN_TABLE,
    symbols_csv: str = "",
    output_dir: str = "",
    heartbeat_path: str = "",
    heartbeat_label: str = "",
    apply: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        start=str(start or ""),
        end=str(end or ""),
        table=str(table or v2_common.V2_MAIN_TABLE),
        symbols_csv=str(symbols_csv or ""),
        output_dir=str(output_dir or ""),
        heartbeat_path=str(heartbeat_path or ""),
        heartbeat_label=str(heartbeat_label or ""),
        apply=bool(apply),
    )


def run_update(args: argparse.Namespace) -> dict[str, Any]:
    latest_before = common.get_latest_trade_date(str(args.table))
    start, latest_before = common.infer_start_date(str(args.start or ""), str(args.table))
    run_id = v2_common.build_run_id("v2_build")
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (v2_common.DEFAULT_OUTPUT_ROOT / f"pams_ohlcv_daily_v2_build_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)
    heartbeat_path = str(getattr(args, "heartbeat_path", "") or "").strip()
    heartbeat_label = str(getattr(args, "heartbeat_label", "") or "").strip() or "pams_ohlcv_daily_v2"

    summary: dict[str, Any]
    sample_frames: list[pd.DataFrame] = []
    exception_rows_all: list[dict[str, Any]] = []
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
                open_trade_dates = _load_open_trade_dates(conn, start, end)
                symbol_filter = common.parse_symbols_csv(str(args.symbols_csv or ""))
                security_master = _load_security_master(conn, symbol_filter)
                prev_state = _load_prev_state(conn, str(args.table), start, symbol_filter)
                st_periods = v2_common.load_st_periods(start, end)
                lineage_resolver = v2_common.SymbolLineageResolver.load_from_db(conn)
                ak_cache = v2_common.AkShareTurnoverCache(lineage_resolver=lineage_resolver)
                bj_pre_evidence_dates = _load_bj_pre_evidence_dates(conn, symbol_filter)

                summary = {
                    "status": "ok",
                    "apply": bool(args.apply),
                    "table": str(args.table),
                    "build_run_id": run_id,
                    "build_version": v2_common.BUILD_VERSION,
                    "date_range": {"start": start.isoformat(), "end": end.isoformat()},
                    "latest_trade_date_before": latest_before.isoformat() if latest_before else None,
                    "latest_trade_date_after": latest_before.isoformat() if latest_before else None,
                    "symbol_filter_count": int(len(symbol_filter)),
                    "open_trade_dates": [item.isoformat() for item in open_trade_dates],
                    "built_rows": 0,
                    "deleted_rows": 0,
                    "deleted_exception_rows": 0,
                    "exception_rows": 0,
                    "per_trade_date": [],
                    "notes": [
                        "v2 canonical build uses security_master x raw trade_cal open days as the eligible grid.",
                        "moneyflow is not merged into the main table and is built separately in pit_stock_moneyflow_v2.",
                    ],
                }
                if args.apply and symbol_filter:
                    summary["deleted_rows"] = _delete_slice_rows(
                        cur,
                        table=str(args.table),
                        start=start,
                        end=end,
                        symbols=symbol_filter,
                    )
                    summary["deleted_exception_rows"] = _delete_exception_slice_rows(
                        cur,
                        start=start,
                        end=end,
                        symbols=symbol_filter,
                    )
                    conn.commit()

                for trade_date in open_trade_dates:
                    try:
                        eligible = security_master[
                            (security_master["list_date"].isna() | (security_master["list_date"] <= trade_date))
                            & (security_master["delist_date"].isna() | (security_master["delist_date"] >= trade_date))
                        ].copy()
                        if eligible.empty:
                            continue
                        daily_frame = _load_trade_date_source(
                            conn,
                            v2_common.RAW_DAILY_TABLE,
                            ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"],
                            trade_date,
                        )
                        adj_frame = _load_trade_date_source(
                            conn,
                            v2_common.RAW_ADJ_FACTOR_TABLE,
                            ["ts_code", "trade_date", "adj_factor"],
                            trade_date,
                        )
                        basic_frame = _load_trade_date_source(
                            conn,
                            v2_common.RAW_DAILY_BASIC_TABLE,
                            ["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS],
                            trade_date,
                        )
                        suspend_frame = _load_trade_date_source(
                            conn,
                            v2_common.RAW_SUSPEND_TABLE,
                            ["ts_code", "trade_date", "suspend_timing", "suspend_type"],
                            trade_date,
                        )
                        limit_frame = _load_trade_date_source(
                            conn,
                            v2_common.RAW_STK_LIMIT_TABLE,
                            ["ts_code", "trade_date", "up_limit", "down_limit"],
                            trade_date,
                        )
                        built_frame, stats, exceptions = _build_trade_date_rows(
                            trade_date=trade_date,
                            eligible_frame=eligible,
                            daily_frame=daily_frame,
                            adj_frame=adj_frame,
                            basic_frame=basic_frame,
                            suspend_frame=suspend_frame,
                            limit_frame=limit_frame,
                            st_periods=st_periods,
                            prev_state=prev_state,
                            ak_cache=ak_cache,
                            bj_pre_evidence_dates=bj_pre_evidence_dates,
                            build_run_id=run_id,
                        )
                        rows = _rows_to_upsert(built_frame)
                        affected_rows = _upsert_rows(
                            cur,
                            table=str(args.table),
                            columns=[*MAIN_COLUMNS, "created_at", "updated_at"],
                            pk_columns=["symbol", "market", "trade_date"],
                            rows=rows,
                        )
                        exception_rows = _exceptions_to_rows(exceptions, run_id)
                        if exception_rows:
                            _insert_exception_rows(cur, exception_rows)
                            if len(exception_rows_all) < 500:
                                remaining = max(500 - len(exception_rows_all), 0)
                                exception_rows_all.extend(exceptions[:remaining])
                        summary["built_rows"] += affected_rows
                        summary["exception_rows"] += int(len(exceptions))
                        stats["built_rows"] = affected_rows
                        summary["per_trade_date"].append(stats)
                        common.append_sample_rows(sample_frames, built_frame)
                        if args.apply:
                            conn.commit()
                        else:
                            conn.rollback()
                        v2_common.touch_heartbeat(
                            heartbeat_path,
                            step=heartbeat_label,
                            trade_date=trade_date,
                            status="running",
                            extra={"build_run_id": run_id, "phase": "trade_date_committed"},
                        )
                    except Exception:
                        if args.apply:
                            conn.rollback()
                        raise

                if args.apply:
                    latest_after = common.get_latest_trade_date(str(args.table))
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
    sample_df = pd.concat(sample_frames, ignore_index=True) if sample_frames else pd.DataFrame(columns=MAIN_COLUMNS)
    sample_path = output_dir / "pams_ohlcv_daily_v2_sample.csv"
    sample_df.to_csv(sample_path, index=False)
    exceptions_path = output_dir / "pams_ohlcv_daily_v2_exceptions_sample.csv"
    pd.DataFrame(exception_rows_all).head(500).to_csv(exceptions_path, index=False)
    summary["sample_csv"] = str(sample_path)
    summary["exceptions_sample_csv"] = str(exceptions_path)
    v2_common.touch_heartbeat(
        heartbeat_path,
        step=heartbeat_label,
        status=summary["status"],
        extra={"build_run_id": run_id, "phase": "completed"},
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pams_ohlcv_daily_v2 from raw Tushare source tables")
    parser.add_argument("--start", default="", help="inclusive start date YYYY-MM-DD; default latest v2 date + 1 or 2007-01-04")
    parser.add_argument("--end", default="", help="inclusive end date YYYY-MM-DD; default latest open date in raw trade calendar")
    parser.add_argument("--table", default=v2_common.V2_MAIN_TABLE, help="target main table")
    parser.add_argument("--symbols-csv", default="", help="optional comma-separated symbols for smoke runs")
    parser.add_argument("--output-dir", default="", help="output directory for summary/sample artifacts")
    parser.add_argument("--heartbeat-path", default="", help="optional heartbeat JSON path updated during long-running build")
    parser.add_argument("--heartbeat-label", default="", help="optional logical step name written to heartbeat JSON")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    args = parser.parse_args()

    summary = run_update(args)
    output_dir = Path(summary["sample_csv"]).parent
    summary_path = output_dir / "summary.json"
    common.write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
