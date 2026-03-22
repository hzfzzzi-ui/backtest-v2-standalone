from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from backend.core.config.asset_profiles import canonical_asset_scope
from backend.core.config.models import BacktestConfig
from backend.core.data.pg_provider import PostgresDataProvider
from backend.core.data.price_adjust import apply_price_adjustment
from backend.core.data.provider import DataProvider
from backend.core.universe.membership_audit import audit_membership_history, should_block_static_fallback
from backend.core.universe.hs300_csi500 import (
    UniverseFilterConfig,
    apply_symbol_level_universe_filters,
    apply_universe_filters,
    build_candidates_from_ohlcv,
    is_turnover_rate_filter_enabled,
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
    membership_history: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["index_code", "symbol", "start_date", "end_date"])
    )
    industry_history: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            columns=["ts_code", "start_date", "end_date", "standard", "industry_l1", "industry_l2"]
        )
    )


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


def _extract_universe_membership_mode(cfg_merged: dict[str, Any]) -> str:
    try:
        return str((cfg_merged.get("universe") or {}).get("membership_mode") or "").strip().upper()
    except Exception:
        return ""


def _extract_allow_low_fidelity_history(cfg_merged: dict[str, Any]) -> bool:
    try:
        return bool((cfg_merged.get("universe") or {}).get("allow_low_fidelity_history", False))
    except Exception:
        return False


def _index_code_for_dynamic_membership(universe_mode: str) -> str | None:
    return {
        "HS300_ZZ500": "000906.SH",
        "CSI1000": "000852.SH",
    }.get(str(universe_mode or "").strip().upper())


def _load_dynamic_index_membership_bundle(
    *,
    provider: DataProvider,
    universe_mode: str,
    start: date,
    end: date,
    universe_limit: int | None,
) -> tuple[list[str], pd.DataFrame, dict[str, Any]]:
    index_code = _index_code_for_dynamic_membership(universe_mode)
    if not index_code:
        raise ValueError(f"membership_mode PIT_DYNAMIC not supported for universe_mode={universe_mode}")

    membership_history = provider.load_index_constituent_history(index_code, start, end)
    if membership_history is None or membership_history.empty:
        raise ValueError(
            f"pit dynamic universe requires historical constituent rows: mode={universe_mode}, index_code={index_code}"
        )

    membership_history = membership_history.copy()
    membership_history["symbol"] = membership_history["symbol"].astype(str).str.lower()
    membership_history["start_date"] = pd.to_datetime(membership_history["start_date"], errors="coerce").dt.normalize()
    membership_history["end_date"] = pd.to_datetime(membership_history["end_date"], errors="coerce").dt.normalize()
    membership_history = membership_history.dropna(subset=["symbol", "start_date"]).reset_index(drop=True)
    if membership_history.empty:
        raise ValueError(
            f"pit dynamic universe has no valid membership rows after normalization: mode={universe_mode}, index_code={index_code}"
        )

    overlap_mask = membership_history["start_date"].le(pd.Timestamp(end))
    overlap_mask &= membership_history["end_date"].isna() | membership_history["end_date"].gt(pd.Timestamp(start))
    membership_history = membership_history.loc[overlap_mask].reset_index(drop=True)
    if membership_history.empty:
        raise ValueError(
            f"pit dynamic universe has no rows overlapping backtest window: mode={universe_mode}, index_code={index_code}"
        )

    symbols = sorted(membership_history["symbol"].dropna().astype(str).unique().tolist())
    if universe_limit is not None:
        symbols = symbols[:universe_limit]
        membership_history = membership_history.loc[
            membership_history["symbol"].astype(str).isin(set(symbols))
        ].reset_index(drop=True)
    if not symbols:
        raise ValueError(
            f"pit dynamic universe produced zero union symbols: mode={universe_mode}, index_code={index_code}"
        )

    return symbols, membership_history, {
        "universe_mode": universe_mode,
        "symbols_source": "pit_index_constituents",
        "load_table": "pit_index_constituents",
        "index_code": index_code,
        "membership_mode": "PIT_DYNAMIC",
        "membership_history_mode": "PIT_DYNAMIC",
        "historical_membership_dynamic": True,
        "pit_dynamic": True,
        "dynamic_membership": True,
        "membership_history_rows": int(len(membership_history)),
        "union_symbol_count": int(len(symbols)),
        "constituents_load_status": "OK",
        "as_of": "dynamic_history_range",
        "resolve_asof": "dynamic_history_range",
        "filter_mode": "dynamic_membership_gate",
    }


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
    industry_history: pd.DataFrame,
    price_adj_mode: str,
    dynamic_all_a_entry: bool,
    membership_history: pd.DataFrame,
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
        "industry_history_rows": int(len(industry_history)),
        "price_adj_mode": str(price_adj_mode),
        "dynamic_all_a_entry": bool(dynamic_all_a_entry),
        "membership_mode": str(universe_meta.get("membership_mode") or "SNAPSHOT"),
        "historical_membership_dynamic": bool(universe_meta.get("historical_membership_dynamic")),
        "membership_history_rows": int(len(membership_history)),
        "membership_source": str(universe_meta.get("membership_source") or "unknown"),
        "membership_data_quality": str(universe_meta.get("membership_data_quality") or "unknown"),
        "audit_status": str(universe_meta.get("audit_status") or ""),
        "audit_reason": str(universe_meta.get("audit_reason") or ""),
        "distinct_start_dates": int(universe_meta.get("distinct_start_dates") or 0),
        "open_rows": int(universe_meta.get("open_rows") or 0),
        "closed_rows": int(universe_meta.get("closed_rows") or 0),
        "covers_required_start": universe_meta.get("covers_required_start"),
        "covers_required_end": universe_meta.get("covers_required_end"),
        "rebalance_calendar_version": universe_meta.get("rebalance_calendar_version"),
        "rebalance_calendar_source": universe_meta.get("rebalance_calendar_source"),
        "rebalance_calendar_generated_at": universe_meta.get("rebalance_calendar_generated_at"),
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
    membership_mode = _extract_universe_membership_mode(cfg_merged)
    allow_low_fidelity_history = _extract_allow_low_fidelity_history(cfg_merged)

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

    universe_limit = int(overrides.get("universe_limit") or 0) or None
    asset_scope = canonical_asset_scope(overrides.get("asset_scope") or cfg_merged.get("asset_scope") or "cn_a_equity")
    membership_history = pd.DataFrame(columns=["index_code", "symbol", "start_date", "end_date"])
    dynamic_membership_entry = membership_mode == "PIT_DYNAMIC"

    _emit_progress(progress_hook, 10, f"Resolving universe ({universe_mode})")
    if dynamic_membership_entry:
        symbols, membership_history, universe_meta = _load_dynamic_index_membership_bundle(
            provider=provider,
            universe_mode=universe_mode,
            start=cfg_obj.universe.start,
            end=cfg_obj.universe.end,
            universe_limit=universe_limit,
        )
    else:
        symbols, universe_meta = resolve_universe_by_mode(
            mode=universe_mode,
            as_of=resolve_asof,
            db=cfg_obj.db,
            runtime=cfg_obj.db_runtime,
            asset_scope=asset_scope,
            industries=universe_industries,
            symbols=user_symbols,
            universe_limit=universe_limit,
        )
    universe_meta = annotate_universe_meta(
        universe_meta,
        mode=universe_mode,
        start=cfg_obj.universe.start,
        end=cfg_obj.universe.end,
    )
    universe_meta["asset_scope"] = asset_scope
    if dynamic_membership_entry:
        universe_meta["membership_mode"] = "PIT_DYNAMIC"
        universe_meta["membership_history_mode"] = "PIT_DYNAMIC"
        universe_meta["historical_membership_dynamic"] = True
        universe_meta["pit_dynamic"] = True
        universe_meta["dynamic_membership"] = True
        universe_meta["membership_history_rows"] = int(len(membership_history))
        universe_meta["union_symbol_count"] = int(len(symbols))
        universe_meta["resolve_asof"] = "dynamic_history_range"
        universe_meta["as_of"] = "dynamic_history_range"
        universe_meta["filter_mode"] = "dynamic_membership_gate"
        universe_meta["allow_low_fidelity_history"] = bool(allow_low_fidelity_history)
        membership_audit = audit_membership_history(
            membership_history,
            required_start=cfg_obj.universe.start,
            required_end=cfg_obj.universe.end,
            require_calendar_metadata=bool(universe_mode == "CSI1000"),
        )
        universe_meta.update(membership_audit)
        if should_block_static_fallback(
            universe_mode=universe_mode,
            membership_mode=membership_mode,
            membership_data_quality=str(membership_audit.get("membership_data_quality") or ""),
            allow_low_fidelity_history=bool(allow_low_fidelity_history),
        ):
            raise ValueError(
                "csi1000 PIT_DYNAMIC membership history was classified as static_fallback; "
                f"audit_reason={membership_audit.get('audit_reason')} "
                f"distinct_start_dates={membership_audit.get('distinct_start_dates')} "
                f"open_rows={membership_audit.get('open_rows')} "
                f"covers_required_start={membership_audit.get('covers_required_start')} "
                f"covers_required_end={membership_audit.get('covers_required_end')} "
                f"rebalance_calendar_version={membership_audit.get('rebalance_calendar_version')} "
                "set universe.allow_low_fidelity_history=true only for explicit low-fidelity research"
            )

    uf_cfg = None
    if universe_filters_raw:
        uf_cfg = UniverseFilterConfig(
            exclude_st=bool(universe_filters_raw.get("exclude_st", True)),
            exclude_delisted=bool(universe_filters_raw.get("exclude_delisted", True)),
            exclude_suspended=bool(universe_filters_raw.get("exclude_suspended", True)),
            exclude_star_market=bool(universe_filters_raw.get("exclude_star_market", False)),
            min_list_days=int(universe_filters_raw.get("min_list_days", 120)),
            min_avg_turnover_20d=float(universe_filters_raw.get("min_avg_turnover_20d", 1e8)),
            min_avg_turnover_rate_20d=float(universe_filters_raw.get("min_avg_turnover_rate_20d", 0.0) or 0.0),
            turnover_rate_field=str(universe_filters_raw.get("turnover_rate_field", "turnover_rate_f") or "turnover_rate_f"),
            exclude_limit_lock=str(universe_filters_raw.get("limit_rule", "ignore")).strip().lower() in {"forbid", "skip"},
            min_price=float(
                universe_filters_raw.get(
                    "price_min",
                    universe_filters_raw.get("min_price", 0.0),
                )
                or 0.0
            ),
        )

    dynamic_universe_entry = dynamic_all_a_entry or dynamic_membership_entry
    if universe_filters_raw and dynamic_universe_entry and uf_cfg is not None:
        filtered_symbols, excluded_counts = apply_symbol_level_universe_filters(symbols, uf_cfg)
        before_count = int(len(symbols))
        after_count = int(len(filtered_symbols))
        universe_meta["filters_config"] = dict(universe_filters_raw)
        universe_meta["excluded_counts"] = excluded_counts
        universe_meta["tradable_symbols"] = after_count
        universe_meta["after_filters_symbols"] = after_count
        universe_meta["filter_mode"] = "dynamic_membership_gate" if dynamic_membership_entry else "dynamic_daily_gate"
        if after_count > 0:
            symbols = filtered_symbols
            if dynamic_membership_entry and not membership_history.empty:
                membership_history = membership_history.loc[
                    membership_history["symbol"].astype(str).isin(set(filtered_symbols))
                ].reset_index(drop=True)
                universe_meta["membership_history_rows"] = int(len(membership_history))
        else:
            universe_meta["filter_warning"] = "all symbols filtered out; fallback to pre-filter universe"
            universe_meta["after_filters_symbols"] = before_count

    _emit_progress(progress_hook, 20, f"Loading OHLCV for {len(symbols)} symbols ({universe_mode})")
    history = provider.load_ohlcv_daily(symbols, cfg_obj.universe.start, cfg_obj.universe.end, source="stocks")

    if universe_filters_raw and not dynamic_universe_entry:
        _emit_progress(progress_hook, 30, "Applying static universe filters")
        filter_asof = pd.Timestamp(cfg_obj.universe.start)
        history_for_filter = history
        need_lookback = bool(
            int(universe_filters_raw.get("min_list_days", 120) or 0) > 1
            or float(universe_filters_raw.get("min_avg_turnover_20d", 0.0) or 0.0) > 0.0
            or float(universe_filters_raw.get("min_avg_turnover_rate_20d", 0.0) or 0.0) > 0.0
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
            turnover_rate_field=uf_cfg.turnover_rate_field,
        )
        if is_turnover_rate_filter_enabled(uf_cfg) and uf_cfg.turnover_rate_field not in history_for_filter.columns:
            raise ValueError(f"turnover rate filter field unavailable in history frame: {uf_cfg.turnover_rate_field}")
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
    elif universe_filters_raw and dynamic_universe_entry:
        universe_meta["filter_mode"] = "dynamic_membership_gate" if dynamic_membership_entry else "dynamic_daily_gate"

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

    _emit_progress(progress_hook, 40, "Loading auxiliary data")
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
    industry_history = provider.load_industry_history(symbols, cfg_obj.universe.start, cfg_obj.universe.end)

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
        industry_history=industry_history,
        price_adj_mode=price_adj_mode,
        dynamic_all_a_entry=dynamic_all_a_entry,
        membership_history=membership_history,
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
        industry_history=industry_history,
        price_adj_mode=price_adj_mode,
        adj_factor_stats=adj_factor_stats,
        summary=summary,
        membership_history=membership_history,
    )
