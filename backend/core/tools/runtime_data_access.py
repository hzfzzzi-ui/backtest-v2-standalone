from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.config.asset_profiles import UnsupportedAssetScopeError, resolve_asset_profile
from backend.core.config.loader import load_config
from backend.core.config.models import BacktestConfig
from backend.core.data.cn_etf_catalog import normalize_cn_etf_symbol, normalize_cn_etf_ts_code
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.data.provider import DataProvider
from backend.core.universe.hs300_csi500 import (
    UniverseFilterConfig,
    apply_symbol_level_universe_filters,
    apply_universe_filters,
    build_candidates_from_ohlcv,
    is_turnover_rate_filter_enabled,
)
from backend.core.universe.lineage import annotate_universe_meta, resolve_universe_timing
from backend.core.universe.universe_resolver import resolve_universe_by_mode


_ST_NAME_PAT = re.compile(r"(^\*?ST)|(^ST)|退", re.IGNORECASE)


@dataclass(slots=True)
class RuntimeDataAccess:
    bt_root: Path
    cfg_obj: BacktestConfig
    cfg_path: Path
    provider: DataProvider


@dataclass(slots=True)
class ValidationUniverseSnapshot:
    access: RuntimeDataAccess
    universe_mode: str
    resolved_symbols: list[str]
    resolved_meta: dict[str, Any]
    resolve_asof: date
    dynamic_all_a_entry: bool
    universe_filters_raw: dict[str, Any]


def _to_ts_symbol(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith(("sh", "sz")) and len(lower) == 8:
        return f"{lower[2:]}.{lower[:2].upper()}"
    if "." in text:
        code, exch = text.split(".", 1)
        exch_u = exch.upper()
        if len(code) == 6 and exch_u in {"SH", "SZ"}:
            return f"{code}.{exch_u}"
    return text.upper()


def _ts_to_internal_symbol(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lower = text.lower()
    if "." in lower:
        code, exch = lower.split(".", 1)
        if len(code) == 6 and exch in {"sh", "sz"}:
            return f"{exch}{code}"
    return lower


def _default_bt_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in current.parents:
        if (candidate / "configs" / "pams_cn_pg.json").exists():
            return candidate
        if (candidate.parent / "configs" / "pams_cn_pg.json").exists():
            return candidate.parent
    return current.parents[3]


def _inject_db_env(cfg_obj: BacktestConfig) -> None:
    db = cfg_obj.db
    if not db.password:
        db.password = os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", ""))
    if os.environ.get("PGHOST"):
        db.host = os.environ["PGHOST"]
    if os.environ.get("PGPORT"):
        db.port = int(os.environ["PGPORT"])
    if os.environ.get("PGUSER"):
        db.user = os.environ["PGUSER"]
    if os.environ.get("PGDATABASE"):
        db.dbname = os.environ["PGDATABASE"]


def load_runtime_data_access(
    bt_root: str | Path | None = None,
    *,
    asset_scope: str | None = None,
) -> RuntimeDataAccess:
    asset_profile = resolve_asset_profile(asset_scope)
    if asset_profile.asset_scope not in {"cn_a_equity", "cn_etf"}:
        raise UnsupportedAssetScopeError(
            f"runtime data access adapter unavailable for asset_scope: {asset_profile.asset_scope}"
        )
    root = Path(bt_root).resolve() if bt_root is not None else _default_bt_root()
    cfg_path = root / "configs" / "pams_cn_pg.json"
    if not cfg_path.exists():
        cfg_path = root.parent / "configs" / "pams_cn_pg.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config not found: {cfg_path}")
    cfg_obj, _ = load_config(str(cfg_path))
    _inject_db_env(cfg_obj)
    provider = PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=cfg_path.parent / "instrument_rules_cn.csv",
    )
    return RuntimeDataAccess(
        bt_root=root,
        cfg_obj=cfg_obj,
        cfg_path=cfg_path,
        provider=provider,
    )


def load_benchmark_series_frame(
    *,
    symbol: str,
    start: date,
    end: date,
    access: RuntimeDataAccess | None = None,
    bt_root: str | Path | None = None,
    asset_scope: str | None = None,
) -> pd.DataFrame:
    runtime_access = access or load_runtime_data_access(bt_root, asset_scope=asset_scope)
    return runtime_access.provider.load_benchmark_daily(symbol, start, end)


def load_symbol_series_frame(
    *,
    symbol: str,
    start: date,
    end: date,
    access: RuntimeDataAccess | None = None,
    bt_root: str | Path | None = None,
    asset_scope: str | None = None,
) -> pd.DataFrame:
    runtime_access = access or load_runtime_data_access(bt_root, asset_scope=asset_scope)
    return runtime_access.provider.load_ohlcv_daily([symbol], start, end, source="stocks")


def list_runtime_industries(
    *,
    access: RuntimeDataAccess | None = None,
    bt_root: str | Path | None = None,
    asset_scope: str | None = None,
) -> list[str]:
    runtime_access = access or load_runtime_data_access(bt_root, asset_scope=asset_scope)
    profile = resolve_asset_profile(asset_scope)
    if profile.asset_scope == "cn_etf":
        return []
    try:
        import psycopg

        conn = psycopg.connect(
            host=runtime_access.cfg_obj.db.host,
            port=runtime_access.cfg_obj.db.port,
            dbname=runtime_access.cfg_obj.db.dbname,
            user=runtime_access.cfg_obj.db.user,
            password=runtime_access.cfg_obj.db.password or os.environ.get("PGPASSWORD", "") or os.environ.get("POSTGRES_PASSWORD", ""),
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT industry_l1 FROM public.pit_industry_history ORDER BY industry_l1")
            rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def resolve_validation_universe(
    *,
    bt_root: str | Path | None,
    asset_scope: str | None = None,
    universe_mode: str,
    symbols: list[str],
    industries: list[str],
    universe_limit: int | None,
    start: date,
    end: date,
    exclude_st: bool,
    exclude_suspended: bool,
    min_list_days: int,
    min_avg_turnover_20d: float,
    min_avg_turnover_rate_20d: float,
    turnover_rate_field: str,
    price_min: float,
    price_max: float,
    limit_rule: str,
    exclude_star_market: bool = False,
) -> ValidationUniverseSnapshot:
    asset_profile = resolve_asset_profile(asset_scope)
    access = load_runtime_data_access(bt_root, asset_scope=asset_profile.asset_scope)
    resolve_asof, dynamic_all_a_entry = resolve_universe_timing(
        universe_mode,
        start=start,
        end=end,
    )
    resolved_symbols, resolved_meta = resolve_universe_by_mode(
        mode=universe_mode,
        as_of=resolve_asof,
        db=access.cfg_obj.db,
        runtime=access.cfg_obj.db_runtime,
        asset_scope=asset_profile.asset_scope,
        industries=industries,
        symbols=symbols,
        universe_limit=universe_limit,
    )
    resolved_meta = annotate_universe_meta(
        resolved_meta,
        mode=universe_mode,
        start=start,
        end=end,
    )
    resolved_meta["asset_scope"] = asset_profile.asset_scope
    resolved_meta["asset_profile_id"] = asset_profile.asset_profile_id
    resolved_meta["market_profile_id"] = asset_profile.market_profile.profile_id
    resolved_meta["asset_family"] = asset_profile.asset_family
    resolved_meta.setdefault("tradable_symbols", int(len(resolved_symbols)))
    resolved_meta.setdefault("after_filters_symbols", int(len(resolved_symbols)))
    if asset_profile.asset_scope == "cn_etf":
        catalog_df = access.provider.load_cn_etf_catalog(resolved_symbols)
        coverage_df = access.provider.load_cn_etf_coverage(resolved_symbols)
        resolved_meta["etf_symbols"] = sorted(
            {
                normalize_cn_etf_ts_code(value)
                for value in catalog_df.get("ts_code", pd.Series(dtype=str)).astype(str).tolist()
                if str(value).strip()
            }
        ) or [normalize_cn_etf_ts_code(symbol) for symbol in resolved_symbols]
        resolved_meta["etf_internal_symbols"] = sorted(
            {
                normalize_cn_etf_symbol(value)
                for value in catalog_df.get("symbol", pd.Series(dtype=str)).astype(str).tolist()
                if str(value).strip()
            }
        ) or [normalize_cn_etf_symbol(symbol) for symbol in resolved_symbols]
        if not coverage_df.empty:
            coverage_start = pd.to_datetime(coverage_df.get("coverage_start"), errors="coerce").dropna()
            coverage_end = pd.to_datetime(coverage_df.get("coverage_end"), errors="coerce").dropna()
            resolved_meta["coverage_start"] = coverage_start.min().date().isoformat() if not coverage_start.empty else None
            resolved_meta["coverage_end"] = coverage_end.max().date().isoformat() if not coverage_end.empty else None
            resolved_meta["daily_table"] = str(
                coverage_df.get("daily_table", pd.Series(["pams_cn_etf_daily"])).iloc[0]
            )
            resolved_meta["price_series_semantics"] = str(
                coverage_df.get(
                    "price_series_semantics",
                    pd.Series(["executable_price_only_not_total_return"]),
                ).iloc[0]
            )
        return ValidationUniverseSnapshot(
            access=access,
            universe_mode=universe_mode,
            resolved_symbols=[normalize_cn_etf_symbol(symbol) for symbol in resolved_symbols],
            resolved_meta=dict(resolved_meta),
            resolve_asof=resolve_asof,
            dynamic_all_a_entry=False,
            universe_filters_raw={},
        )

    universe_filters_raw = {
        "exclude_st": exclude_st,
        "exclude_delisted": True,
        "exclude_suspended": exclude_suspended,
        "exclude_star_market": exclude_star_market,
        "min_list_days": min_list_days,
        "min_avg_turnover_20d": min_avg_turnover_20d,
        "min_avg_turnover_rate_20d": min_avg_turnover_rate_20d,
        "turnover_rate_field": turnover_rate_field,
        "price_min": price_min,
        "price_max": price_max,
        "limit_rule": limit_rule,
    }
    resolved_meta["filters_config"] = dict(universe_filters_raw)
    filter_cfg = UniverseFilterConfig(
        exclude_st=exclude_st,
        exclude_delisted=True,
        exclude_suspended=exclude_suspended,
        exclude_star_market=exclude_star_market,
        min_list_days=min_list_days,
        min_avg_turnover_20d=min_avg_turnover_20d,
        min_avg_turnover_rate_20d=min_avg_turnover_rate_20d,
        turnover_rate_field=turnover_rate_field,
        exclude_limit_lock=limit_rule in {"forbid", "skip"},
        min_price=price_min,
    )

    if universe_filters_raw and not dynamic_all_a_entry and resolved_symbols:
        filter_asof = pd.Timestamp(start)
        history_for_filter = access.provider.load_ohlcv_daily(
            resolved_symbols,
            start,
            end,
            source="stocks",
        )
        need_lookback = bool(
            min_list_days > 1
            or min_avg_turnover_20d > 0.0
            or min_avg_turnover_rate_20d > 0.0
        )
        if need_lookback:
            lookback_days = max(260, min_list_days * 3)
            filter_start = (filter_asof - pd.Timedelta(days=lookback_days)).date()
            history_for_filter = access.provider.load_ohlcv_daily(
                resolved_symbols,
                filter_start,
                start,
                source="stocks",
            )
        filter_asof_date = filter_asof.date()
        try:
            st_history_for_filter = access.provider.load_st_history(resolved_symbols, filter_asof_date, filter_asof_date)
        except Exception:
            st_history_for_filter = pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"])
        try:
            security_master = access.provider.load_security_master(resolved_symbols)
        except Exception:
            security_master = pd.DataFrame(columns=["symbol", "list_date", "delist_date"])

        candidates = build_candidates_from_ohlcv(
            history_for_filter,
            filter_asof,
            st_history=st_history_for_filter,
            security_master=security_master,
            turnover_rate_field=turnover_rate_field,
        )
        if is_turnover_rate_filter_enabled(filter_cfg) and turnover_rate_field not in history_for_filter.columns:
            raise ValueError(f"turnover rate filter field unavailable in history frame: {turnover_rate_field}")
        filtered_candidates, _snapshot, excluded_counts = apply_universe_filters(candidates, filter_cfg)
        filtered_symbols = sorted(
            {
                str(s).strip().lower()
                for s in filtered_candidates.get("symbol", pd.Series(dtype=str)).tolist()
                if str(s).strip()
            }
        )
        before_count = int(len(resolved_symbols))
        after_count = int(len(filtered_symbols))
        resolved_meta["excluded_counts"] = excluded_counts
        resolved_meta["tradable_symbols"] = after_count
        resolved_meta["after_filters_symbols"] = after_count
        if after_count > 0:
            resolved_symbols = filtered_symbols
        else:
            resolved_meta["filter_warning"] = "all symbols filtered out; fallback to pre-filter universe"
            resolved_meta["after_filters_symbols"] = before_count
    elif universe_filters_raw and dynamic_all_a_entry:
        filtered_symbols, excluded_counts = apply_symbol_level_universe_filters(resolved_symbols, filter_cfg)
        before_count = int(len(resolved_symbols))
        after_count = int(len(filtered_symbols))
        resolved_meta["excluded_counts"] = excluded_counts
        resolved_meta["tradable_symbols"] = after_count
        resolved_meta["after_filters_symbols"] = after_count
        resolved_meta["filter_mode"] = "dynamic_daily_gate"
        if after_count > 0:
            resolved_symbols = filtered_symbols
        else:
            resolved_meta["filter_warning"] = "all symbols filtered out; fallback to pre-filter universe"
            resolved_meta["after_filters_symbols"] = before_count

    return ValidationUniverseSnapshot(
        access=access,
        universe_mode=universe_mode,
        resolved_symbols=list(resolved_symbols),
        resolved_meta=dict(resolved_meta),
        resolve_asof=resolve_asof,
        dynamic_all_a_entry=bool(dynamic_all_a_entry),
        universe_filters_raw=dict(universe_filters_raw),
    )


def _connect_runtime_db(access: RuntimeDataAccess):
    import psycopg

    return psycopg.connect(
        host=access.cfg_obj.db.host,
        port=access.cfg_obj.db.port,
        dbname=access.cfg_obj.db.dbname,
        user=access.cfg_obj.db.user,
        password=access.cfg_obj.db.password or os.environ.get("PGPASSWORD", "") or os.environ.get("POSTGRES_PASSWORD", ""),
        autocommit=True,
    )


def resolve_stock_names(
    symbols: list[str],
    *,
    access: RuntimeDataAccess | None = None,
    bt_root: str | Path | None = None,
) -> dict[str, str]:
    if not symbols:
        return {}
    runtime_access = access or load_runtime_data_access(bt_root)
    try:
        conn = _connect_runtime_db(runtime_access)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT symbol, name FROM pit_security_master WHERE symbol = ANY(%s) AND name IS NOT NULL AND name != ''",
                (list(symbols),),
            )
            rows = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()
        return rows
    except Exception:
        return {}


def resolve_trade_st_flags(
    trades_df: pd.DataFrame,
    stock_names: dict[str, str],
    *,
    access: RuntimeDataAccess | None = None,
    bt_root: str | Path | None = None,
) -> dict[str, str]:
    if trades_df.empty or "date" not in trades_df.columns or "symbol" not in trades_df.columns:
        return {}
    runtime_access = access or load_runtime_data_access(bt_root)
    tdf = trades_df.copy()
    tdf["date"] = pd.to_datetime(tdf["date"], errors="coerce").dt.date
    tdf["symbol"] = tdf["symbol"].astype(str).str.lower()
    tdf = tdf.dropna(subset=["date", "symbol"])
    if tdf.empty:
        return {}

    out: dict[str, str] = {}
    for row in tdf.itertuples(index=False):
        out[f"{row.date.isoformat()}|{str(row.symbol).lower()}"] = "-"

    symbol_map = {
        str(sym).lower(): _to_ts_symbol(sym)
        for sym in sorted(set(tdf["symbol"].astype(str).tolist()))
    }
    ts_symbols = sorted({ts for ts in symbol_map.values() if ts})
    min_d = tdf["date"].min()
    max_d = tdf["date"].max()
    st_periods: dict[str, list[tuple[Any, Any]]] = {}

    try:
        conn = _connect_runtime_db(runtime_access)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ts_code, start_date, end_date
                FROM pit_st_history
                WHERE ts_code = ANY(%s)
                  AND start_date <= %s
                  AND (end_date IS NULL OR end_date >= %s)
                """,
                (ts_symbols, max_d, min_d),
            )
            for sym, sdt, edt in cur.fetchall():
                internal = _ts_to_internal_symbol(sym)
                if internal:
                    st_periods.setdefault(internal, []).append((sdt, edt))
        conn.close()
    except Exception:
        st_periods = {}

    for row in tdf.itertuples(index=False):
        sym = str(row.symbol).lower()
        d = row.date
        key = f"{d.isoformat()}|{sym}"
        for sdt, edt in st_periods.get(sym, []):
            s = pd.to_datetime(sdt, errors="coerce").date() if sdt is not None else None
            e = pd.to_datetime(edt, errors="coerce").date() if edt is not None else None
            if s is None:
                continue
            if d >= s and (e is None or d <= e):
                out[key] = "PIT_ST"
                break
    return out
