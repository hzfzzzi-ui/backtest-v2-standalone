from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import pandas as pd

from backend.core.config.models import DBConfig, DBRuntimeConfig
from backend.core.data.mapping import normalize_stock_symbol

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None


class UniverseLoadError(RuntimeError):
    def __init__(self, status: str, message: str, meta: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.meta = meta or {}


@dataclass(frozen=True)
class UniverseFilterConfig:
    exclude_st: bool = True
    exclude_suspended: bool = True
    min_list_days: int = 120
    min_avg_turnover_20d: float = 1e8
    exclude_limit_lock: bool = False


def load_constituents_from_db(
    db: DBConfig,
    runtime: DBRuntimeConfig,
    as_of: date,
    universe_limit: int | None = None,
    index_codes: tuple[str, str] = ("000300.SH", "000905.SH"),
) -> tuple[list[str], dict[str, Any]]:
    if psycopg is None:  # pragma: no cover
        raise UniverseLoadError(
            status="ERROR:PSYCOPG_MISSING",
            message="psycopg not available",
            meta={
                "symbols_source": "db_index_constituents",
                "constituents_load_status": "ERROR:PSYCOPG_MISSING",
                "universe_limit": universe_limit,
                "raw_count": 0,
            },
        )

    # Local DB schema (verified): no index-constituent table is available.
    # Use active CN_A stock universe from pit_security_master, constrained to
    # symbols with available OHLCV at/before `as_of` in pams_ohlcv_daily.
    try:
        with psycopg.connect(
            host=db.host,
            port=db.port,
            dbname=db.dbname,
            user=db.user,
            password=db.password,
            autocommit=False,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(f"SET LOCAL statement_timeout = '{int(runtime.statement_timeout_ms)}ms'")
                sql = """
                WITH available AS (
                  SELECT DISTINCT symbol
                  FROM public.pams_ohlcv_daily
                  WHERE market = 'CN_A' AND trade_date <= %s
                )
                SELECT DISTINCT sm.symbol AS symbol
                FROM public.pit_security_master sm
                JOIN available a ON a.symbol = sm.symbol
                WHERE sm.market_type = 'CN_A'
                  AND sm.exchange IN ('SH', 'SZ')
                  AND (sm.list_date IS NULL OR sm.list_date <= %s)
                  AND (sm.delist_date IS NULL OR sm.delist_date > %s)
                ORDER BY sm.symbol
                """
                cur.execute(sql, (as_of, as_of, as_of))
                rows = cur.fetchall()
    except Exception as exc:
        err = f"{type(exc).__name__}:{str(exc).replace(chr(10), ' ').replace(chr(13), ' ')}"
        meta = {
            "symbols_source": "db_index_constituents",
            "constituents_load_status": f"ERROR:{err[:120]}",
            "universe_limit": universe_limit,
            "raw_count": 0,
            "load_table": "pit_security_master+pams_ohlcv_daily",
            "load_detail": "active_cn_a_with_ohlcv",
            "index_codes_requested": list(index_codes),
        }
        raise UniverseLoadError(status=meta["constituents_load_status"], message="failed to load constituents from db", meta=meta)

    symbols = sorted(
        {
            normalize_stock_symbol(str(r[0]))
            for r in rows
            if r and r[0]
        }
    )
    raw_count = int(len(symbols))
    if universe_limit is not None:
        symbols = symbols[: int(universe_limit)]

    meta = {
        "symbols_source": "db_index_constituents",
        "constituents_load_status": "OK" if raw_count > 0 else "EMPTY",
        "universe_limit": universe_limit,
        "raw_count": raw_count,
        "load_table": "pit_security_master+pams_ohlcv_daily",
        "load_detail": "active_cn_a_with_ohlcv",
        "index_codes_requested": list(index_codes),
    }
    if not symbols:
        raise UniverseLoadError("EMPTY", "no symbols from pit_security_master+pams_ohlcv_daily", meta=meta)
    return symbols, meta


def resolve_universe_symbols(
    *,
    as_of: date,
    db_loader: Callable[[date, int | None], tuple[list[str], dict[str, Any]]],
    user_symbols: list[str] | None = None,
    allow_user_override: bool = False,
    universe_limit: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    if allow_user_override and user_symbols:
        symbols = sorted({normalize_stock_symbol(str(s)) for s in user_symbols if str(s).strip()})
        meta = {
            "symbols_source": "user_override",
            "constituents_load_status": "OK",
            "universe_limit": universe_limit,
            "raw_count": int(len(symbols)),
        }
        return symbols, meta
    symbols, meta = db_loader(as_of, universe_limit)
    if not symbols:
        status = str(meta.get("constituents_load_status", "EMPTY"))
        raise UniverseLoadError(status=status, message=f"empty universe: {status}", meta=meta)
    return symbols, meta


def apply_universe_filters(
    candidates: pd.DataFrame,
    cfg: UniverseFilterConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    cfg = cfg or UniverseFilterConfig()
    if candidates.empty:
        cols = [
            "date",
            "symbol",
            "in_hs300",
            "in_csi500",
            "tradable",
            "excluded_reason",
        ]
        return pd.DataFrame(columns=cols), pd.DataFrame(columns=cols), {}

    df = candidates.copy()
    for col, default in [
        ("date", ""),
        ("symbol", ""),
        ("in_hs300", False),
        ("in_csi500", False),
        ("is_st", False),
        ("is_suspended", False),
        ("list_days", 9999),
        ("avg_turnover_20d", 0.0),
        ("limit_lock", False),
    ]:
        if col not in df.columns:
            df[col] = default

    reasons: list[str] = []
    tradable = []
    for _, r in df.iterrows():
        reason = ""
        if cfg.exclude_st and bool(r.get("is_st", False)):
            reason = "EXCLUDE_ST"
        elif cfg.exclude_suspended and bool(r.get("is_suspended", False)):
            reason = "EXCLUDE_SUSPENDED"
        elif int(r.get("list_days", 0) or 0) < int(cfg.min_list_days):
            reason = "EXCLUDE_LIST_DAYS"
        elif float(r.get("avg_turnover_20d", 0.0) or 0.0) < float(cfg.min_avg_turnover_20d):
            reason = "EXCLUDE_LOW_TURNOVER"
        elif cfg.exclude_limit_lock and bool(r.get("limit_lock", False)):
            reason = "EXCLUDE_LIMIT_LOCK"
        reasons.append(reason)
        tradable.append(reason == "")

    df["excluded_reason"] = reasons
    df["tradable"] = tradable
    snapshot = df[
        ["date", "symbol", "in_hs300", "in_csi500", "tradable", "excluded_reason"]
    ].copy()
    filtered = df[df["tradable"]].copy()
    excluded_counts = (
        df.loc[~df["tradable"], "excluded_reason"].value_counts().to_dict()
        if (~df["tradable"]).any()
        else {}
    )
    excluded_counts = {str(k): int(v) for k, v in excluded_counts.items()}
    return filtered, snapshot, excluded_counts


def build_candidates_from_ohlcv(ohlcv: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    if ohlcv.empty:
        return pd.DataFrame()
    df = ohlcv.copy()
    df["date"] = pd.to_datetime(df["date"])
    use = df[df["date"] <= as_of].copy()
    if use.empty:
        return pd.DataFrame()
    out_rows: list[dict[str, Any]] = []
    for symbol, g in use.groupby("symbol"):
        g = g.sort_values("date")
        list_days = int(len(g))
        avg_turnover = float(g.tail(20).get("amount", pd.Series([0.0] * min(20, len(g)))).fillna(0.0).mean())
        last = g.iloc[-1]
        is_suspended = bool(float(last.get("volume", 0.0) or 0.0) <= 0.0)
        out_rows.append(
            {
                "date": as_of.date().isoformat(),
                "symbol": str(symbol),
                "in_hs300": True,
                "in_csi500": True,
                "is_st": False,
                "is_suspended": is_suspended,
                "list_days": list_days,
                "avg_turnover_20d": avg_turnover,
                "limit_lock": False,
            }
        )
    return pd.DataFrame(out_rows)
