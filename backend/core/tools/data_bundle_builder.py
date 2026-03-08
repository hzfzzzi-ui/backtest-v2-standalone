from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from backend.core.config.models import BacktestConfig
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.data.price_adjust import apply_price_adjustment
from backend.core.data.provider import DataProvider
from backend.core.universe.hs300_csi500 import (
    UniverseFilterConfig,
    apply_universe_filters,
    build_candidates_from_ohlcv,
)
from backend.core.universe.lineage import annotate_universe_meta, resolve_universe_timing
from backend.core.universe.universe_resolver import resolve_universe_by_mode


@dataclass(slots=True)
class DataBundle:
    provider: DataProvider
    universe_mode: str
    symbols: list[str]
    universe_meta: dict[str, Any]
    universe_filters_raw: dict[str, Any]
    resolve_asof: date
    dynamic_all_a_entry: bool
    raw_history: pd.DataFrame
    signal_history: pd.DataFrame
    benchmark: pd.DataFrame
    trading_days: list[date]
    st_history: pd.DataFrame
    sector_data: dict[str, pd.DataFrame]
    industry_map: dict[str, str]
    price_adj_mode: str
    adj_factor_stats: dict[str, Any]
    summary: dict[str, Any]


def _emit_progress(progress_hook: Callable[[int, str], None] | None, pct: int, message: str) -> None:
    if progress_hook is None:
        return
    try:
        progress_hook(int(max(0, min(100, pct))), str(message))
    except Exception:
        pass


def _extract_universe_filters_raw(cfg_merged: dict[str, Any]) -> dict[str, Any]:
    try:
        return dict((cfg_merged.get("universe") or {}).get("filters") or {})
    except Exception:
        return {}


def _create_data_provider(cfg_obj: BacktestConfig, rules_path: str | Path) -> DataProvider:
    pg_provider = PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=rules_path,
    )
    try:
        from backend.core.data.cached_provider import CachedDataProvider

        return CachedDataProvider(pg_provider)
    except ImportError:
        return pg_provider


def _build_data_bundle_summary(
    *,
    symbols: list[str],
    universe_meta: dict[str, Any],
    universe_filters_raw: dict[str, Any],
    raw_history: pd.DataFrame,
    signal_history: pd.DataFrame,
    benchmark: pd.DataFrame,
    trading_days: list[date],
    st_history: pd.DataFrame,
    sector_data: dict[str, pd.DataFrame],
    industry_map: dict[str, str],
    price_adj_mode: str,
    dynamic_all_a_entry: bool,
) -> dict[str, Any]:
    history_date_min = None
    history_date_max = None
    if not raw_history.empty and "date" in raw_history.columns:
        history_date_min = str(pd.to_datetime(raw_history["date"], errors="coerce").min().date())
        history_date_max = str(pd.to_datetime(raw_history["date"], errors="coerce").max().date())

    benchmark_date_min = None
    benchmark_date_max = None
    if not benchmark.empty and "date" in benchmark.columns:
        benchmark_date_min = str(pd.to_datetime(benchmark["date"], errors="coerce").min().date())
        benchmark_date_max = str(pd.to_datetime(benchmark["date"], errors="coerce").max().date())

    calendar_start = str(trading_days[0]) if trading_days else None
    calendar_end = str(trading_days[-1]) if trading_days else None
    missing_history_close = int(raw_history["close"].isna().sum()) if "close" in raw_history.columns else 0
    missing_benchmark_close = int(benchmark["close"].isna().sum()) if "close" in benchmark.columns else 0

    return {
        "universe_mode": str(universe_meta.get("universe_mode") or ""),
        "symbols_count": int(len(symbols)),
        "raw_history_rows": int(len(raw_history)),
        "signal_history_rows": int(len(signal_history)),
        "benchmark_rows": int(len(benchmark)),
        "trading_days": int(len(trading_days)),
        "st_rows": int(len(st_history)),
        "sector_series_count": int(len(sector_data)),
        "industry_map_count": int(len(industry_map)),
        "price_adj_mode": str(price_adj_mode),
        "dynamic_all_a_entry": bool(dynamic_all_a_entry),
        "history_date_start": history_date_min,
        "history_date_end": history_date_max,
        "benchmark_date_start": benchmark_date_min,
        "benchmark_date_end": benchmark_date_max,
        "calendar_start": calendar_start,
        "calendar_end": calendar_end,
        "missing_history_close_rows": missing_history_close,
        "missing_benchmark_close_rows": missing_benchmark_close,
        "filter_mode": str(universe_meta.get("filter_mode") or "static_preload"),
        "filters_config_present": bool(universe_filters_raw),
    }


def build_data_bundle(
    *,
    cfg_obj: BacktestConfig,
    cfg_merged: dict[str, Any],
    overrides: dict[str, Any],
    rules_path: str | Path,
    provider: DataProvider | None = None,
    progress_hook: Callable[[int, str], None] | None = None,
    default_experiment_symbols: list[str] | None = None,
) -> DataBundle:
    provider = provider or _create_data_provider(cfg_obj, rules_path)
    universe_filters_raw = _extract_universe_filters_raw(cfg_merged)

    universe_mode = str(overrides.get("universe_mode", "CUSTOM")).strip().upper()
    universe_industries = list(overrides.get("industries") or [])
    user_symbols = list(cfg_obj.universe.symbols or [])
    if universe_mode == "CUSTOM" and not user_symbols:
        user_symbols = list(default_experiment_symbols or [])

    resolve_asof, dynamic_all_a_entry = resolve_universe_timing(
        universe_mode,
        start=cfg_obj.universe.start,
        end=cfg_obj.universe.end,
    )

    _emit_progress(progress_hook, 10, f"解析 Universe ({universe_mode})")
    symbols, universe_meta = resolve_universe_by_mode(
        mode=universe_mode,
        as_of=resolve_asof,
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        industries=universe_industries,
        symbols=user_symbols,
        universe_limit=int(overrides.get("universe_limit") or 0) or None,
    )
    universe_meta = annotate_universe_meta(
        universe_meta,
        mode=universe_mode,
        start=cfg_obj.universe.start,
        end=cfg_obj.universe.end,
    )

    _emit_progress(progress_hook, 20, f"加载行情数据: {len(symbols)} 标的 ({universe_mode})")
    history = provider.load_ohlcv_daily(symbols, cfg_obj.universe.start, cfg_obj.universe.end, source="stocks")

    if universe_filters_raw and not dynamic_all_a_entry:
        _emit_progress(progress_hook, 30, "应用 Universe 过滤器")
        uf_cfg = UniverseFilterConfig(
            exclude_st=bool(universe_filters_raw.get("exclude_st", True)),
            exclude_delisted=bool(universe_filters_raw.get("exclude_delisted", True)),
            exclude_suspended=bool(universe_filters_raw.get("exclude_suspended", True)),
            min_list_days=int(universe_filters_raw.get("min_list_days", 120)),
            min_avg_turnover_20d=float(universe_filters_raw.get("min_avg_turnover_20d", 1e8)),
            exclude_limit_lock=str(universe_filters_raw.get("limit_rule", "ignore")).strip().lower() in {"forbid", "skip"},
            min_price=float(
                universe_filters_raw.get(
                    "price_min",
                    universe_filters_raw.get("min_price", 0.0),
                )
                or 0.0
            ),
        )
        filter_asof = pd.Timestamp(cfg_obj.universe.start)
        history_for_filter = history
        need_lookback = bool(
            int(universe_filters_raw.get("min_list_days", 120) or 0) > 1
            or float(universe_filters_raw.get("min_avg_turnover_20d", 0.0) or 0.0) > 0.0
        )
        if need_lookback:
            lookback_days = max(260, int(universe_filters_raw.get("min_list_days", 120) or 120) * 3)
            filter_start = (filter_asof - pd.Timedelta(days=lookback_days)).date().isoformat()
            history_for_filter = provider.load_ohlcv_daily(
                symbols,
                filter_start,
                cfg_obj.universe.start,
                source="stocks",
            )
        filter_asof_date = pd.Timestamp(filter_asof).date()
        try:
            st_history_for_filter = provider.load_st_history(symbols, filter_asof_date, filter_asof_date)
        except Exception:
            st_history_for_filter = pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"])
        try:
            security_master = provider.load_security_master(symbols)
        except Exception:
            security_master = pd.DataFrame(columns=["symbol", "list_date", "delist_date"])

        candidates = build_candidates_from_ohlcv(
            history_for_filter,
            filter_asof,
            st_history=st_history_for_filter,
            security_master=security_master,
        )
        filtered_candidates, _snapshot, excluded_counts = apply_universe_filters(candidates, uf_cfg)
        filtered_symbols = sorted(
            {
                str(s).strip().lower()
                for s in filtered_candidates.get("symbol", pd.Series(dtype=str)).tolist()
                if str(s).strip()
            }
        )
        before_count = int(len(symbols))
        after_count = int(len(filtered_symbols))
        universe_meta["filters_config"] = dict(universe_filters_raw)
        universe_meta["excluded_counts"] = excluded_counts
        universe_meta["tradable_symbols"] = after_count
        universe_meta["after_filters_symbols"] = after_count
        if after_count > 0:
            symbols = filtered_symbols
            history = history[history["symbol"].astype(str).str.lower().isin(set(filtered_symbols))].copy()
        else:
            universe_meta["filter_warning"] = "all symbols filtered out; fallback to pre-filter universe"
            universe_meta["after_filters_symbols"] = before_count
    elif universe_filters_raw and dynamic_all_a_entry:
        universe_meta["filters_config"] = dict(universe_filters_raw)
        universe_meta["excluded_counts"] = {}
        universe_meta["tradable_symbols"] = int(len(symbols))
        universe_meta["after_filters_symbols"] = int(len(symbols))
        universe_meta["filter_mode"] = "dynamic_daily_gate"

    benchmark = provider.load_benchmark_daily(cfg_obj.universe.benchmark, cfg_obj.universe.start, cfg_obj.universe.end)
    calendar = provider.load_trading_calendar_cn(cfg_obj.universe.start, cfg_obj.universe.end)
    trading_days = [d.date() for d in calendar]

    price_adj_mode = str(overrides.get("price_adj", "hfq")).strip().lower()
    if price_adj_mode not in ("hfq", "qfq", "none"):
        price_adj_mode = "hfq"
    raw_history = history
    adj_factor_stats: dict[str, Any] = {}
    if "adj_factor" in history.columns:
        af = history["adj_factor"]
        adj_factor_stats = {
            "min": float(af.min()),
            "max": float(af.max()),
            "null_count": int(af.isna().sum()),
        }
    signal_history = apply_price_adjustment(history, price_adj_mode) if price_adj_mode != "none" else history

    _emit_progress(progress_hook, 40, "加载辅助数据 (ST/行业)")
    st_history = provider.load_st_history(symbols, cfg_obj.universe.start, cfg_obj.universe.end)
    sector_data: dict[str, pd.DataFrame] = {}
    try:
        sec_df = provider.load_sector_indices(cfg_obj.universe.start, cfg_obj.universe.end)
        sector_col = "index_code" if "index_code" in sec_df.columns else "symbol"
        if not sec_df.empty and sector_col in sec_df.columns:
            for sym, grp in sec_df.groupby(sector_col):
                sector_data[str(sym)] = grp.reset_index(drop=True)
    except Exception:
        pass
    industry_map = provider.load_industry_mapping(symbols)

    summary = _build_data_bundle_summary(
        symbols=symbols,
        universe_meta=universe_meta,
        universe_filters_raw=universe_filters_raw,
        raw_history=raw_history,
        signal_history=signal_history,
        benchmark=benchmark,
        trading_days=trading_days,
        st_history=st_history,
        sector_data=sector_data,
        industry_map=industry_map,
        price_adj_mode=price_adj_mode,
        dynamic_all_a_entry=dynamic_all_a_entry,
    )

    return DataBundle(
        provider=provider,
        universe_mode=universe_mode,
        symbols=symbols,
        universe_meta=universe_meta,
        universe_filters_raw=universe_filters_raw,
        resolve_asof=resolve_asof,
        dynamic_all_a_entry=dynamic_all_a_entry,
        raw_history=raw_history,
        signal_history=signal_history,
        benchmark=benchmark,
        trading_days=trading_days,
        st_history=st_history,
        sector_data=sector_data,
        industry_map=industry_map,
        price_adj_mode=price_adj_mode,
        adj_factor_stats=adj_factor_stats,
        summary=summary,
    )
