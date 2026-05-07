from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.data.price_limits import (
    compute_limit_prices as _shared_compute_limit_prices,
    limit_pct_for_symbol as _shared_limit_pct_for_symbol,
)
from backend.core.data.pg_env import connect as pg_connect
from backend.core.data.pg_env import load_db_settings as load_shared_db_settings
from backend.core.data.pg_env import read_env_file as read_shared_env_file
from backend.core.data.mapping import normalize_index_symbol

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
UPSERT_COLUMNS = [
    "symbol",
    "market",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "turnover",
    "adj_factor",
    "limit_up",
    "limit_down",
    "is_suspended",
    "turnover_rate",
    "turnover_rate_f",
    "volume_ratio",
    "float_share",
    "free_share",
    "circ_mv",
]
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(slots=True)
class DbSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _safe_ident(name: str) -> str:
    if not IDENT_RE.match(name):
        raise ValueError(f"invalid SQL identifier: {name}")
    return name


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
    if text and text[0] in {"6", "5", "9"}:
        return f"sh{text}"
    if text.startswith(("4", "8")):
        return f"bj{text}"
    return f"sz{text}"


def _load_env_file() -> dict[str, str]:
    return read_shared_env_file(ROOT)


def _load_db_settings() -> DbSettings:
    settings = load_shared_db_settings(config_path=DEFAULT_CONFIG_PATH, root=ROOT)
    return DbSettings(settings.host, settings.port, settings.dbname, settings.user, settings.password)


def _connect():
    if psycopg is None:  # pragma: no cover
        raise RuntimeError("psycopg is required")
    return pg_connect(config_path=DEFAULT_CONFIG_PATH, root=ROOT, autocommit=False)


def _iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _to_float_or_none(value: Any) -> float | None:
    series = pd.to_numeric(pd.Series([value]), errors="coerce")
    number = series.iloc[0]
    if pd.isna(number):
        return None
    return float(number)


def _to_int_or_none(value: Any) -> int | None:
    series = pd.to_numeric(pd.Series([value]), errors="coerce")
    number = series.iloc[0]
    if pd.isna(number):
        return None
    return int(round(float(number)))


def _limit_pct_for_symbol(symbol: str, *, is_st: bool) -> float:
    return _shared_limit_pct_for_symbol(symbol, is_st=is_st)


def _compute_limit_prices(prev_close: Any, symbol: str, *, is_st: bool) -> tuple[float | None, float | None]:
    return _shared_compute_limit_prices(prev_close, symbol, is_st=is_st)


def _load_tushare_client(token: str):
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is required via --token or env TUSHARE_TOKEN")
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api(token)


def _load_akshare():
    import akshare as ak

    return ak


def _load_cn_index_daily_tushare(pro: Any, symbol: str, *, start: date, end: date) -> pd.DataFrame:
    raw = pro.index_daily(
        ts_code=normalize_index_symbol(symbol),
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        fields="ts_code,trade_date,open,high,low,close,vol,amount",
    )
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    return raw.rename(columns={"trade_date": "date", "vol": "volume"}).copy()


def _normalize_daily_basic_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["symbol", "trade_date", *DAILY_BASIC_FIELDS])
    df = raw.copy()
    keep_cols = [c for c in ["ts_code", "trade_date", *DAILY_BASIC_FIELDS] if c in df.columns]
    df = df.loc[:, keep_cols].copy()
    df["symbol"] = df["ts_code"].astype(str).map(_normalize_stock_symbol).astype(str).str.lower()
    df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce").dt.date
    for col in DAILY_BASIC_FIELDS:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return (
        df[["symbol", "trade_date", *DAILY_BASIC_FIELDS]]
        .dropna(subset=["symbol", "trade_date"])
        .drop_duplicates(subset=["symbol", "trade_date"], keep="last")
        .sort_values(["trade_date", "symbol"])
        .reset_index(drop=True)
    )


def _normalize_cn_a_rows(
    *,
    trade_date: date,
    daily_raw: pd.DataFrame,
    adj_raw: pd.DataFrame,
    basic_raw: pd.DataFrame,
    st_periods: dict[str, list[tuple[date, date | None]]],
    prev_close_map: dict[str, float],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    daily = pd.DataFrame(columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "turnover", "pre_close"])
    if daily_raw is not None and not daily_raw.empty:
        daily = daily_raw.copy()
        keep_cols = [c for c in ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount", "pre_close"] if c in daily.columns]
        daily = daily.loc[:, keep_cols].copy()
        daily["symbol"] = daily["ts_code"].astype(str).map(_normalize_stock_symbol).astype(str).str.lower()
        daily["trade_date"] = pd.to_datetime(daily["trade_date"].astype(str), format="%Y%m%d", errors="coerce").dt.date
        for col in ["open", "high", "low", "close", "vol", "amount", "pre_close"]:
            if col not in daily.columns:
                daily[col] = pd.NA
            daily[col] = pd.to_numeric(daily[col], errors="coerce")
        daily["volume"] = pd.to_numeric(daily["vol"], errors="coerce").mul(100.0)
        daily["turnover"] = pd.to_numeric(daily["amount"], errors="coerce").mul(1000.0)
        daily = daily[["symbol", "trade_date", "open", "high", "low", "close", "volume", "turnover", "pre_close"]]

    adj = pd.DataFrame(columns=["symbol", "trade_date", "adj_factor"])
    if adj_raw is not None and not adj_raw.empty:
        adj = adj_raw.copy()
        adj = adj.loc[:, [c for c in ["ts_code", "trade_date", "adj_factor"] if c in adj.columns]].copy()
        adj["symbol"] = adj["ts_code"].astype(str).map(_normalize_stock_symbol).astype(str).str.lower()
        adj["trade_date"] = pd.to_datetime(adj["trade_date"].astype(str), format="%Y%m%d", errors="coerce").dt.date
        adj["adj_factor"] = pd.to_numeric(adj["adj_factor"], errors="coerce")
        adj = (
            adj[["symbol", "trade_date", "adj_factor"]]
            .dropna(subset=["symbol", "trade_date"])
            .drop_duplicates(subset=["symbol", "trade_date"], keep="last")
        )

    basic = _normalize_daily_basic_frame(basic_raw)
    expected_symbols = sorted(set(daily["symbol"].tolist()) | set(adj["symbol"].tolist()) | set(basic["symbol"].tolist()))
    if not expected_symbols:
        empty = pd.DataFrame(columns=UPSERT_COLUMNS)
        return empty, {"trade_date": trade_date.isoformat(), "rows": 0}

    out = daily.merge(adj, on=["symbol", "trade_date"], how="left")
    out = out.merge(basic, on=["symbol", "trade_date"], how="left")
    out["market"] = "CN_A"
    out["is_suspended"] = False
    daily_symbols = set(out["symbol"].tolist())

    limit_up_values: list[float | None] = []
    limit_down_values: list[float | None] = []
    missing_prev_close = 0
    st_count = 0
    for row in out.itertuples(index=False):
        symbol = str(row.symbol).lower()
        is_st = any(
            start_dt <= trade_date and (end_dt is None or trade_date <= end_dt)
            for start_dt, end_dt in st_periods.get(symbol, [])
        )
        if is_st:
            st_count += 1
        prev_close_for_limit = _to_float_or_none(getattr(row, "pre_close", None))
        if prev_close_for_limit is None:
            prev_close_for_limit = prev_close_map.get(symbol)
        limit_up, limit_down = _compute_limit_prices(prev_close_for_limit, symbol, is_st=is_st)
        if limit_up is None or limit_down is None:
            missing_prev_close += 1
        limit_up_values.append(limit_up)
        limit_down_values.append(limit_down)
        close_value = _to_float_or_none(row.close)
        if close_value is not None and close_value > 0.0:
            prev_close_map[symbol] = close_value
    out["limit_up"] = limit_up_values
    out["limit_down"] = limit_down_values

    suspended_rows: list[dict[str, Any]] = []
    extra_symbols = [symbol for symbol in expected_symbols if symbol not in daily_symbols]
    if extra_symbols:
        adj_map = {
            str(row.symbol).lower(): _to_float_or_none(row.adj_factor)
            for row in adj.itertuples(index=False)
        }
        basic_map = {
            str(row.symbol).lower(): {
                "turnover_rate": _to_float_or_none(row.turnover_rate),
                "turnover_rate_f": _to_float_or_none(row.turnover_rate_f),
                "volume_ratio": _to_float_or_none(row.volume_ratio),
                "float_share": _to_float_or_none(row.float_share),
                "free_share": _to_float_or_none(row.free_share),
                "circ_mv": _to_float_or_none(row.circ_mv),
            }
            for row in basic.itertuples(index=False)
        }
        for symbol in extra_symbols:
            prev_close = prev_close_map.get(symbol)
            if prev_close is None or prev_close <= 0.0:
                missing_prev_close += 1
                continue
            is_st = any(
                start_dt <= trade_date and (end_dt is None or trade_date <= end_dt)
                for start_dt, end_dt in st_periods.get(symbol, [])
            )
            if is_st:
                st_count += 1
            limit_up, limit_down = _compute_limit_prices(prev_close, symbol, is_st=is_st)
            extras = basic_map.get(symbol, {})
            suspended_rows.append(
                {
                    "symbol": symbol,
                    "market": "CN_A",
                    "trade_date": trade_date,
                    "open": prev_close,
                    "high": prev_close,
                    "low": prev_close,
                    "close": prev_close,
                    "volume": 0,
                    "turnover": 0.0,
                    "adj_factor": adj_map.get(symbol),
                    "limit_up": limit_up,
                    "limit_down": limit_down,
                    "is_suspended": True,
                    "turnover_rate": extras.get("turnover_rate"),
                    "turnover_rate_f": extras.get("turnover_rate_f"),
                    "volume_ratio": extras.get("volume_ratio"),
                    "float_share": extras.get("float_share"),
                    "free_share": extras.get("free_share"),
                    "circ_mv": extras.get("circ_mv"),
                }
            )

    if suspended_rows:
        out = pd.concat([out[UPSERT_COLUMNS], pd.DataFrame(suspended_rows, columns=UPSERT_COLUMNS)], ignore_index=True)
    else:
        out = out[UPSERT_COLUMNS]

    out = out[UPSERT_COLUMNS].drop_duplicates(subset=["symbol", "market", "trade_date"], keep="last")
    return out.sort_values(["trade_date", "symbol"]).reset_index(drop=True), {
        "trade_date": trade_date.isoformat(),
        "rows": int(len(out)),
        "suspended_rows": int(pd.Series(out["is_suspended"]).fillna(False).sum()),
        "st_rows": int(st_count),
        "missing_prev_close_rows": int(missing_prev_close),
        "missing_adj_factor_rows": int(pd.to_numeric(out["adj_factor"], errors="coerce").isna().sum()),
        "missing_turnover_rate_rows": int(pd.to_numeric(out["turnover_rate"], errors="coerce").isna().sum()),
    }


def _normalize_cn_index_rows(
    symbol: str,
    raw: pd.DataFrame,
    *,
    start: date,
    end: date,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if raw is None or raw.empty:
        empty = pd.DataFrame(columns=UPSERT_COLUMNS)
        return empty, {"symbol": symbol, "rows": 0}
    rename_map = {
        "date": "trade_date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }
    if "date" in raw.columns:
        df = raw.rename(columns=rename_map).copy()
    else:
        df = raw.rename(
            columns={
                "日期": "trade_date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
            }
        ).copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
    df = df[(df["trade_date"] >= start) & (df["trade_date"] <= end)].copy()
    if df.empty:
        empty = pd.DataFrame(columns=UPSERT_COLUMNS)
        return empty, {"symbol": symbol, "rows": 0}
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["symbol"] = str(symbol).lower()
    df["market"] = "CN_INDEX"
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").mul(100.0)
    df["turnover"] = 0.0
    df["adj_factor"] = pd.NA
    df["limit_up"] = pd.NA
    df["limit_down"] = pd.NA
    df["is_suspended"] = False
    for col in DAILY_BASIC_FIELDS:
        df[col] = pd.NA
    out = df[UPSERT_COLUMNS].drop_duplicates(subset=["symbol", "market", "trade_date"], keep="last")
    return out.sort_values(["trade_date"]).reset_index(drop=True), {
        "symbol": symbol,
        "rows": int(len(out)),
        "start": out["trade_date"].min().isoformat(),
        "end": out["trade_date"].max().isoformat(),
    }


def _load_existing_prev_close_map(table: str, start: date) -> dict[str, float]:
    table_name = _safe_ident(table)
    query = f"""
        SELECT DISTINCT ON (symbol)
            symbol,
            close
        FROM public.{table_name}
        WHERE market = 'CN_A'
          AND trade_date < %s
        ORDER BY symbol, trade_date DESC
    """
    out: dict[str, float] = {}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (start,))
            for symbol, close in cur.fetchall():
                close_value = _to_float_or_none(close)
                if close_value is not None and close_value > 0.0:
                    out[str(symbol).lower()] = close_value
    return out


def _load_st_periods(start: date, end: date) -> dict[str, list[tuple[date, date | None]]]:
    out: dict[str, list[tuple[date, date | None]]] = {}
    query = """
        SELECT ts_code, start_date, end_date
        FROM public.pit_st_history
        WHERE start_date <= %s
          AND (end_date IS NULL OR end_date >= %s)
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (end, start))
            for ts_code, start_date, end_date in cur.fetchall():
                symbol = _normalize_stock_symbol(str(ts_code or "").strip())
                if not symbol:
                    continue
                out.setdefault(symbol, []).append(
                    (
                        pd.Timestamp(start_date).date(),
                        None if end_date is None else pd.Timestamp(end_date).date(),
                    )
                )
    return out


def _load_index_symbols(table: str) -> list[str]:
    table_name = _safe_ident(table)
    query = f"""
        SELECT DISTINCT symbol
        FROM public.{table_name}
        WHERE market = 'CN_INDEX'
        ORDER BY symbol
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [str(row[0]).lower() for row in cur.fetchall()]


def _get_latest_trade_date(table: str, market: str) -> date | None:
    table_name = _safe_ident(table)
    query = f"SELECT MAX(trade_date) FROM public.{table_name} WHERE market = %s"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (market,))
            row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return pd.Timestamp(row[0]).date()


def _load_cn_a_null_adj_factor_audit(table: str, *, start: date, end: date) -> dict[str, Any]:
    if start > end:
        return {"dates": [], "rows": 0, "per_trade_date": [], "ok": True}
    table_name = _safe_ident(table)
    query = f"""
        SELECT trade_date, COUNT(*) AS missing_rows
        FROM public.{table_name}
        WHERE market = 'CN_A'
          AND trade_date >= %s
          AND trade_date <= %s
          AND adj_factor IS NULL
        GROUP BY trade_date
        ORDER BY trade_date
    """
    per_trade_date: list[dict[str, Any]] = []
    missing_rows = 0
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (start, end))
            for trade_date, row_count in cur.fetchall():
                trade_dt = pd.Timestamp(trade_date).date()
                count = int(row_count or 0)
                per_trade_date.append({"trade_date": trade_dt.isoformat(), "rows": count})
                missing_rows += count
    return {
        "dates": [item["trade_date"] for item in per_trade_date],
        "rows": missing_rows,
        "per_trade_date": per_trade_date,
        "ok": missing_rows == 0,
    }


def _fetch_daily_basic_safe(pro: Any, trade_date: date) -> tuple[pd.DataFrame | None, str | None]:
    try:
        return pro.daily_basic(
            trade_date=trade_date.strftime("%Y%m%d"),
            fields="ts_code,trade_date," + ",".join(DAILY_BASIC_FIELDS),
        ), None
    except Exception as exc:
        return None, str(exc)


def _init_temp_table(cur) -> None:
    cur.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS tmp_pams_ohlcv_daily_upsert (
            symbol text NOT NULL,
            market text NOT NULL,
            trade_date date NOT NULL,
            open numeric,
            high numeric,
            low numeric,
            close numeric,
            volume bigint,
            turnover numeric,
            adj_factor numeric,
            limit_up numeric,
            limit_down numeric,
            is_suspended boolean,
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
    cur.execute("TRUNCATE TABLE tmp_pams_ohlcv_daily_upsert")
    if batch.empty:
        return
    rows = []
    for row in batch.itertuples(index=False):
        rows.append(
            (
                str(row.symbol),
                str(row.market),
                row.trade_date,
                _to_float_or_none(row.open),
                _to_float_or_none(row.high),
                _to_float_or_none(row.low),
                _to_float_or_none(row.close),
                _to_int_or_none(row.volume),
                _to_float_or_none(row.turnover),
                _to_float_or_none(row.adj_factor),
                _to_float_or_none(row.limit_up),
                _to_float_or_none(row.limit_down),
                bool(row.is_suspended),
                _to_float_or_none(row.turnover_rate),
                _to_float_or_none(row.turnover_rate_f),
                _to_float_or_none(row.volume_ratio),
                _to_float_or_none(row.float_share),
                _to_float_or_none(row.free_share),
                _to_float_or_none(row.circ_mv),
            )
        )
    cur.executemany(
        """
        INSERT INTO tmp_pams_ohlcv_daily_upsert (
            symbol,
            market,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            turnover,
            adj_factor,
            limit_up,
            limit_down,
            is_suspended,
            turnover_rate,
            turnover_rate_f,
            volume_ratio,
            float_share,
            free_share,
            circ_mv
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )


def _count_batch_state(cur, table: str) -> tuple[int, int]:
    table_name = _safe_ident(table)
    cur.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE target.symbol IS NULL) AS insert_rows,
            COUNT(*) FILTER (WHERE target.symbol IS NOT NULL) AS update_rows
        FROM tmp_pams_ohlcv_daily_upsert AS src
        LEFT JOIN public.{table_name} AS target
          ON target.symbol = src.symbol
         AND target.market = src.market
         AND target.trade_date = src.trade_date
        """
    )
    row = cur.fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def _upsert_batch(cur, table: str) -> int:
    table_name = _safe_ident(table)
    cur.execute(
        f"""
        INSERT INTO public.{table_name} (
            symbol,
            market,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            turnover,
            adj_factor,
            limit_up,
            limit_down,
            is_suspended,
            turnover_rate,
            turnover_rate_f,
            volume_ratio,
            float_share,
            free_share,
            circ_mv
        )
        SELECT
            symbol,
            market,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            turnover,
            adj_factor,
            limit_up,
            limit_down,
            is_suspended,
            turnover_rate,
            turnover_rate_f,
            volume_ratio,
            float_share,
            free_share,
            circ_mv
        FROM tmp_pams_ohlcv_daily_upsert
        ON CONFLICT (symbol, market, trade_date) DO UPDATE
        SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            turnover = EXCLUDED.turnover,
            adj_factor = COALESCE(EXCLUDED.adj_factor, {table_name}.adj_factor),
            limit_up = COALESCE(EXCLUDED.limit_up, {table_name}.limit_up),
            limit_down = COALESCE(EXCLUDED.limit_down, {table_name}.limit_down),
            is_suspended = EXCLUDED.is_suspended,
            turnover_rate = COALESCE(EXCLUDED.turnover_rate, {table_name}.turnover_rate),
            turnover_rate_f = COALESCE(EXCLUDED.turnover_rate_f, {table_name}.turnover_rate_f),
            volume_ratio = COALESCE(EXCLUDED.volume_ratio, {table_name}.volume_ratio),
            float_share = COALESCE(EXCLUDED.float_share, {table_name}.float_share),
            free_share = COALESCE(EXCLUDED.free_share, {table_name}.free_share),
            circ_mv = COALESCE(EXCLUDED.circ_mv, {table_name}.circ_mv)
        """
    )
    return int(cur.rowcount or 0)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _infer_start_date(args_start: str, table: str, end: date) -> tuple[date, date | None, date | None]:
    latest_cn_a = _get_latest_trade_date(table, "CN_A")
    latest_cn_index = _get_latest_trade_date(table, "CN_INDEX")
    if args_start:
        return date.fromisoformat(args_start), latest_cn_a, latest_cn_index
    candidates = [item for item in (latest_cn_a, latest_cn_index) if item is not None]
    if not candidates:
        raise RuntimeError("--start is required when target table is empty")
    start = min(candidates) + timedelta(days=1)
    if start > end:
        return start, latest_cn_a, latest_cn_index
    return start, latest_cn_a, latest_cn_index


def run_update(args: argparse.Namespace) -> dict[str, Any]:
    requested_start = str(args.start or "").strip()
    repair_null_adj_factor = bool(getattr(args, "repair_null_adj_factor", False))
    if repair_null_adj_factor and not requested_start:
        raise RuntimeError("--start is required when --repair-null-adj-factor is enabled")
    end = date.fromisoformat(args.end)
    start, latest_cn_a, latest_cn_index = _infer_start_date(requested_start, str(args.table), end)
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"ohlcv_update_{ts_label}")
    output_dir.mkdir(parents=True, exist_ok=True)
    before_adj_factor_audit = _load_cn_a_null_adj_factor_audit(str(args.table), start=start, end=end)

    summary: dict[str, Any] = {
        "status": "ok",
        "apply": bool(args.apply),
        "table": str(args.table),
        "repair_null_adj_factor": repair_null_adj_factor,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "latest_cn_a_before": latest_cn_a.isoformat() if latest_cn_a else None,
        "latest_cn_index_before": latest_cn_index.isoformat() if latest_cn_index else None,
        "open_trade_dates": [],
        "cn_a_rows": 0,
        "cn_index_rows": 0,
        "rows_total": 0,
        "insert_rows": 0,
        "update_rows": 0,
        "upserted_rows": 0,
        "batch_size": int(args.batch_size),
        "daily_basic_status": {"available": True, "message": None},
        "repair_target_trade_dates": [],
        "adj_factor_integrity": {
            "before_dates": list(before_adj_factor_audit["dates"]),
            "after_dates": list(before_adj_factor_audit["dates"]),
            "before_rows": int(before_adj_factor_audit["rows"]),
            "remaining_rows": int(before_adj_factor_audit["rows"]),
            "ok": bool(before_adj_factor_audit["ok"]),
        },
        "per_trade_date": [],
        "index_symbol_stats": [],
        "notes": [
            "CN_A uses Tushare daily + adj_factor and optionally daily_basic, executed per trade_date to avoid range row caps.",
            "CN_INDEX uses Tushare index_daily and preserves existing table convention: turnover=0, adj_factor/limit_up/limit_down are null.",
            "limit_up/limit_down are computed from previous close only; if previous close is unavailable they remain null.",
        ],
    }
    target_trade_dates: list[date] = []
    if repair_null_adj_factor:
        target_trade_dates = [date.fromisoformat(item) for item in before_adj_factor_audit["dates"]]
        summary["repair_target_trade_dates"] = [item.isoformat() for item in target_trade_dates]
        summary["notes"].append(
            "repair_null_adj_factor mode only refetches CN_A trade dates that still have raw adj_factor gaps in the requested range."
        )
    elif start <= end:
        target_trade_dates = list(_iter_dates(start, end))

    if not target_trade_dates:
        summary["status"] = "noop"
        summary["latest_cn_a_after"] = latest_cn_a.isoformat() if latest_cn_a else None
        summary["latest_cn_index_after"] = latest_cn_index.isoformat() if latest_cn_index else None
        if repair_null_adj_factor:
            summary["notes"].append("repair_null_adj_factor found no CN_A rows with adj_factor gaps in the requested range.")
        _write_json(output_dir / "summary.json", summary)
        return summary

    token = str(args.token or os.environ.get("TUSHARE_TOKEN") or "").strip()
    pro = _load_tushare_client(token)
    prev_close_map = _load_existing_prev_close_map(str(args.table), start)
    st_periods = _load_st_periods(start, end)
    daily_basic_enabled = True

    stock_frames: list[pd.DataFrame] = []
    for trade_date in target_trade_dates:
        daily_raw = pro.daily(
            trade_date=trade_date.strftime("%Y%m%d"),
            fields="ts_code,trade_date,open,high,low,close,pre_close,vol,amount",
        )
        adj_raw = pro.adj_factor(
            trade_date=trade_date.strftime("%Y%m%d"),
            fields="ts_code,trade_date,adj_factor",
        )
        basic_raw = pd.DataFrame()
        if daily_basic_enabled:
            basic_raw, basic_error = _fetch_daily_basic_safe(pro, trade_date)
            if basic_error:
                daily_basic_enabled = False
                summary["daily_basic_status"] = {"available": False, "message": basic_error}
                summary["notes"].append("daily_basic unavailable; turnover_rate/volume_ratio/circ_mv fields are left null.")
                basic_raw = pd.DataFrame()
        normalized, per_day = _normalize_cn_a_rows(
            trade_date=trade_date,
            daily_raw=daily_raw,
            adj_raw=adj_raw,
            basic_raw=basic_raw,
            st_periods=st_periods,
            prev_close_map=prev_close_map,
        )
        if normalized.empty:
            continue
        stock_frames.append(normalized)
        summary["open_trade_dates"].append(trade_date.isoformat())
        summary["per_trade_date"].append(per_day)
        summary["cn_a_rows"] += int(len(normalized))

    index_frames: list[pd.DataFrame] = []
    if repair_null_adj_factor:
        summary["notes"].append("CN_INDEX refresh is skipped in repair_null_adj_factor mode.")
    else:
        for symbol in _load_index_symbols(str(args.table)):
            try:
                raw = _load_cn_index_daily_tushare(pro, symbol, start=start, end=end)
                normalized, per_symbol = _normalize_cn_index_rows(symbol, raw, start=start, end=end)
                if not normalized.empty:
                    index_frames.append(normalized)
                    summary["cn_index_rows"] += int(len(normalized))
                summary["index_symbol_stats"].append(per_symbol)
            except Exception as exc:
                summary["index_symbol_stats"].append({"symbol": str(symbol).lower(), "rows": 0, "error": str(exc)})
                summary["notes"].append(f"CN_INDEX fetch failed for {symbol}; skipped index backfill for this run.")

    combined = pd.concat([*(stock_frames or []), *(index_frames or [])], ignore_index=True) if (stock_frames or index_frames) else pd.DataFrame(columns=UPSERT_COLUMNS)
    combined = combined.drop_duplicates(subset=["symbol", "market", "trade_date"], keep="last").sort_values(["trade_date", "market", "symbol"]).reset_index(drop=True)
    summary["rows_total"] = int(len(combined))

    sample_path = output_dir / "ohlcv_update_sample.csv"
    combined.head(200).to_csv(sample_path, index=False)
    summary["sample_csv"] = str(sample_path)

    if not combined.empty:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '1200000ms'")
                _init_temp_table(cur)
                for batch_start in range(0, len(combined), int(args.batch_size)):
                    batch = combined.iloc[batch_start : batch_start + int(args.batch_size)].copy()
                    _load_batch_into_temp(cur, batch)
                    insert_rows, update_rows = _count_batch_state(cur, str(args.table))
                    upserted_rows = _upsert_batch(cur, str(args.table))
                    summary["insert_rows"] += insert_rows
                    summary["update_rows"] += update_rows
                    summary["upserted_rows"] += upserted_rows
                if args.apply:
                    conn.commit()
                else:
                    conn.rollback()
                    summary["status"] = "dry_run"
    else:
        summary["status"] = "noop"

    latest_cn_a_after = _get_latest_trade_date(str(args.table), "CN_A") if args.apply else latest_cn_a
    latest_cn_index_after = _get_latest_trade_date(str(args.table), "CN_INDEX") if args.apply else latest_cn_index
    summary["latest_cn_a_after"] = latest_cn_a_after.isoformat() if latest_cn_a_after else None
    summary["latest_cn_index_after"] = latest_cn_index_after.isoformat() if latest_cn_index_after else None
    after_adj_factor_audit = (
        _load_cn_a_null_adj_factor_audit(str(args.table), start=start, end=end)
        if args.apply
        else before_adj_factor_audit
    )
    summary["adj_factor_integrity"] = {
        "before_dates": list(before_adj_factor_audit["dates"]),
        "after_dates": list(after_adj_factor_audit["dates"]),
        "before_rows": int(before_adj_factor_audit["rows"]),
        "remaining_rows": int(after_adj_factor_audit["rows"]),
        "ok": bool(after_adj_factor_audit["ok"]),
    }
    return summary


def build_update_args(
    *,
    end: str,
    start: str = "",
    token: str = "",
    table: str = DEFAULT_TABLE,
    batch_size: int = 5000,
    output_dir: str = "",
    apply: bool = True,
    repair_null_adj_factor: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        start=str(start or ""),
        end=str(end or "").strip(),
        token=str(token or os.environ.get("TUSHARE_TOKEN", "")),
        table=str(table or DEFAULT_TABLE),
        batch_size=int(batch_size),
        output_dir=str(output_dir or ""),
        apply=bool(apply),
        repair_null_adj_factor=bool(repair_null_adj_factor),
    )


def run_update_to_target(
    *,
    end: str,
    start: str = "",
    token: str = "",
    table: str = DEFAULT_TABLE,
    batch_size: int = 5000,
    output_dir: str = "",
    apply: bool = True,
    repair_null_adj_factor: bool = False,
) -> dict[str, Any]:
    return run_update(
        build_update_args(
            start=start,
            end=end,
            token=token,
            table=table,
            batch_size=batch_size,
            output_dir=output_dir,
            apply=apply,
            repair_null_adj_factor=repair_null_adj_factor,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Update pams_ohlcv_daily CN_A/CN_INDEX rows to a target date")
    parser.add_argument("--start", default="", help="inclusive start date YYYY-MM-DD; default is latest CN_A date + 1")
    parser.add_argument("--end", required=True, help="inclusive end date YYYY-MM-DD")
    parser.add_argument("--token", default=os.environ.get("TUSHARE_TOKEN", ""))
    parser.add_argument("--table", default=DEFAULT_TABLE, help="target PostgreSQL table")
    parser.add_argument("--batch-size", type=int, default=5000, help="DB upsert batch size")
    parser.add_argument("--output-dir", default="", help="output directory for summary/sample artifacts")
    parser.add_argument("--apply", action="store_true", help="commit DB writes; default is dry-run rollback")
    parser.add_argument(
        "--repair-null-adj-factor",
        action="store_true",
        help="only refetch CN_A trade dates in the requested range that still have adj_factor NULL gaps",
    )
    args = parser.parse_args()

    summary = run_update(args)
    output_dir = Path(summary["sample_csv"]).parent if summary.get("sample_csv") else (Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_ROOT)
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_json={summary_path}")


if __name__ == "__main__":
    main()
