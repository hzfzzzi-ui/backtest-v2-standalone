from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable
import re

import pandas as pd

from backend.core.config.models import DBConfig, DBRuntimeConfig
from backend.core.data.mapping import normalize_stock_symbol
from backend.core.universe.lineage import ALL_A_SYMBOLS_SOURCE

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
    exclude_delisted: bool = True
    exclude_suspended: bool = True
    min_list_days: int = 120
    min_avg_turnover_20d: float = 1e8
    min_avg_turnover_rate_20d: float = 0.0
    turnover_rate_field: str = "turnover_rate_f"
    exclude_limit_lock: bool = False
    min_price: float = 5.0


_ST_NAME_PAT = re.compile(r"(^\*?ST)|(^ST)|退", re.IGNORECASE)
_TURNOVER_RATE_FIELDS = {"turnover_rate", "turnover_rate_f"}


def normalize_turnover_rate_field(value: Any) -> str:
    text = str(value or "turnover_rate_f").strip().lower()
    if text not in _TURNOVER_RATE_FIELDS:
        raise ValueError(f"unsupported turnover_rate_field: {value}")
    return text


def is_turnover_rate_filter_enabled(cfg: UniverseFilterConfig | None) -> bool:
    if cfg is None:
        return False
    return float(cfg.min_avg_turnover_rate_20d or 0.0) > 0.0


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
                "symbols_source": ALL_A_SYMBOLS_SOURCE,
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
            "symbols_source": ALL_A_SYMBOLS_SOURCE,
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
        "symbols_source": ALL_A_SYMBOLS_SOURCE,
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
        ("is_delisted", False),
        ("is_suspended", False),
        ("list_days", 9999),
        ("avg_turnover_20d", 0.0),
        ("avg_turnover_rate_20d", pd.NA),
        ("last_close", 0.0),
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
        elif cfg.exclude_delisted and bool(r.get("is_delisted", False)):
            reason = "EXCLUDE_DELISTED"
        elif cfg.exclude_suspended and bool(r.get("is_suspended", False)):
            reason = "EXCLUDE_SUSPENDED"
        elif int(r.get("list_days", 0) or 0) < int(cfg.min_list_days):
            reason = "EXCLUDE_LIST_DAYS"
        elif float(r.get("avg_turnover_20d", 0.0) or 0.0) < float(cfg.min_avg_turnover_20d):
            reason = "EXCLUDE_LOW_TURNOVER"
        elif is_turnover_rate_filter_enabled(cfg):
            avg_turnover_rate = pd.to_numeric(pd.Series([r.get("avg_turnover_rate_20d")]), errors="coerce").iloc[0]
            if pd.isna(avg_turnover_rate):
                reason = "EXCLUDE_TURNOVER_RATE_UNAVAILABLE"
            elif float(avg_turnover_rate) < float(cfg.min_avg_turnover_rate_20d):
                reason = "EXCLUDE_LOW_TURNOVER_RATE"
        elif cfg.exclude_limit_lock and bool(r.get("limit_lock", False)):
            reason = "EXCLUDE_LIMIT_LOCK"
        elif cfg.min_price > 0 and float(r.get("last_close", 0.0) or 0.0) < cfg.min_price:
            reason = "EXCLUDE_LOW_PRICE"
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


def _to_internal_symbol(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return ""
    if s.startswith(("sh", "sz")) and len(s) == 8:
        return s
    if "." in s:
        code, exch = s.split(".", 1)
        if exch in {"sh", "sz"} and len(code) == 6:
            return f"{exch}{code}"
    try:
        return normalize_stock_symbol(s)
    except Exception:
        return s


def _build_active_st_symbols(st_history: pd.DataFrame, as_of: pd.Timestamp) -> set[str]:
    if st_history is None or st_history.empty:
        return set()
    active: set[str] = set()
    as_of_ts = pd.Timestamp(as_of).normalize()
    for row in st_history.itertuples(index=False):
        ts_code = getattr(row, "ts_code", getattr(row, "symbol", ""))
        symbol = _to_internal_symbol(ts_code)
        if not symbol:
            continue
        start_date = pd.to_datetime(getattr(row, "start_date", None), errors="coerce")
        end_date = pd.to_datetime(getattr(row, "end_date", None), errors="coerce")
        if pd.isna(start_date):
            continue
        if pd.notna(end_date):
            if start_date <= as_of_ts <= end_date:
                active.add(symbol)
        elif start_date <= as_of_ts:
            active.add(symbol)
    return active


def _build_security_master_map(security_master: pd.DataFrame) -> dict[str, tuple[pd.Timestamp | None, pd.Timestamp | None]]:
    if security_master is None or security_master.empty:
        return {}
    out: dict[str, tuple[pd.Timestamp | None, pd.Timestamp | None]] = {}
    for row in security_master.itertuples(index=False):
        symbol = _to_internal_symbol(getattr(row, "symbol", ""))
        if not symbol:
            continue
        list_date = pd.to_datetime(getattr(row, "list_date", None), errors="coerce")
        delist_date = pd.to_datetime(getattr(row, "delist_date", None), errors="coerce")
        out[symbol] = (
            None if pd.isna(list_date) else pd.Timestamp(list_date).normalize(),
            None if pd.isna(delist_date) else pd.Timestamp(delist_date).normalize(),
        )
    return out


def _build_security_name_map(security_master: pd.DataFrame) -> dict[str, str]:
    if security_master is None or security_master.empty or "name" not in security_master.columns:
        return {}
    out: dict[str, str] = {}
    for row in security_master.itertuples(index=False):
        symbol = _to_internal_symbol(getattr(row, "symbol", ""))
        if not symbol:
            continue
        name = str(getattr(row, "name", "") or "").strip()
        if name:
            out[symbol] = name
    return out


def build_candidates_from_ohlcv(
    ohlcv: pd.DataFrame,
    as_of: pd.Timestamp,
    st_history: pd.DataFrame | None = None,
    security_master: pd.DataFrame | None = None,
    turnover_rate_field: str = "turnover_rate_f",
) -> pd.DataFrame:
    if ohlcv.empty:
        return pd.DataFrame()
    df = ohlcv.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["symbol"] = df["symbol"].astype(str).map(_to_internal_symbol)
    turnover_rate_field = normalize_turnover_rate_field(turnover_rate_field)
    use = df[df["date"] <= as_of].copy()
    if use.empty:
        return pd.DataFrame()
    st_symbols = _build_active_st_symbols(st_history if st_history is not None else pd.DataFrame(), as_of)
    sm_map = _build_security_master_map(security_master if security_master is not None else pd.DataFrame())
    sm_name_map = _build_security_name_map(security_master if security_master is not None else pd.DataFrame())
    as_of_ts = pd.Timestamp(as_of).normalize()
    out_rows: list[dict[str, Any]] = []
    for symbol, g in use.groupby("symbol"):
        g = g.sort_values("date")
        list_days = int(len(g))
        turn_col = "amount" if "amount" in g.columns else ("turnover" if "turnover" in g.columns else "")
        if turn_col:
            avg_turnover = float(pd.to_numeric(g.tail(20)[turn_col], errors="coerce").fillna(0.0).mean())
        else:
            avg_turnover = 0.0
        avg_turnover_rate: float | Any = pd.NA
        if turnover_rate_field in g.columns:
            turnover_rate_window = pd.to_numeric(g.tail(20)[turnover_rate_field], errors="coerce")
            if len(turnover_rate_window) == 20 and turnover_rate_window.notna().all():
                avg_turnover_rate = float(turnover_rate_window.mean())
        last = g.iloc[-1]
        sm_list_date, sm_delist_date = sm_map.get(str(symbol), (None, None))
        if sm_list_date is not None:
            list_days = max(0, int((as_of_ts - sm_list_date).days) + 1)
        is_suspended = bool(float(last.get("volume", 0.0) or 0.0) <= 0.0)
        last_close = float(last.get("close", 0.0) or 0.0)
        sec_name = sm_name_map.get(str(symbol), "")
        is_st = str(symbol) in st_symbols
        is_delisted = bool(sm_delist_date is not None and sm_delist_date <= as_of_ts)
        out_rows.append(
            {
                "date": as_of.date().isoformat(),
                "symbol": str(symbol),
                "in_hs300": True,
                "in_csi500": True,
                "is_st": is_st,
                "is_delisted": is_delisted,
                "security_name": sec_name,
                "is_suspended": is_suspended,
                "list_days": list_days,
                "avg_turnover_20d": avg_turnover,
                "avg_turnover_rate_20d": avg_turnover_rate,
                "last_close": last_close,
                "limit_lock": False,
            }
        )
    return pd.DataFrame(out_rows)
