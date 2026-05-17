"""Universe resolver — 根据 mode + as_of 日期从 DB 查询 symbols 列表。

支持模式: ALL_A / HS300_ZZ500 / CSI1000 / HS300_ZZ500_CSI1000 / INDUSTRY / CUSTOM
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd

from backend.core.config.asset_profiles import resolve_asset_profile
from backend.core.config.etf_beta_contract import (
    CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS,
    CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES,
)
from backend.core.config.models import DBConfig, DBRuntimeConfig
from backend.core.data.cn_etf_catalog import (
    build_shadow_pool_promotion_gates,
    deferred_etf_research_reason,
    expand_etf_preset,
    is_research_shadow_pool,
    normalize_cn_etf_ts_code,
    preset_batch_id,
    require_catalog_entry,
    shadow_pool_role_map,
)
from backend.core.data.mapping import normalize_stock_symbol
from backend.core.universe.hs300_csi500 import UniverseLoadError, load_constituents_from_db
from backend.core.universe.lineage import (
    ALL_A_SYMBOLS_SOURCE,
    INDEX_CONSTITUENTS_SYMBOLS_SOURCE,
    INDUSTRY_HISTORY_SYMBOLS_SOURCE,
    USER_INPUT_SYMBOLS_SOURCE,
)

try:
    import psycopg
except ImportError:
    psycopg = None

if TYPE_CHECKING:  # pragma: no cover
    from backend.core.data.market_data_access import MarketDataAccess


_PIT_INDEX_CODES_BY_UNIVERSE: dict[str, tuple[str, ...]] = {
    "HS300_ZZ500": ("000906.SH",),
    "CSI1000": ("000852.SH",),
    "HS300_ZZ500_CSI1000": ("000906.SH", "000852.SH"),
}


def _query_pit_symbols(
    db: DBConfig,
    runtime: DBRuntimeConfig,
    sql: str,
    params: tuple,
) -> list[str]:
    """执行 PIT 查询并返回标准化 symbol 列表。"""
    if psycopg is None:
        raise UniverseLoadError(
            status="ERROR:PSYCOPG_MISSING",
            message="psycopg not available",
        )
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
            cur.execute(sql, params)
            rows = cur.fetchall()
    return sorted({normalize_stock_symbol(str(r[0])) for r in rows if r and r[0]})


def _resolve_all_a(
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    universe_limit: int | None = None,
    market_data_access: MarketDataAccess | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """ALL_A 模式: 返回截至 as_of 全部活跃 CN_A 股票。"""
    if market_data_access is not None:
        symbols, meta = market_data_access.load_active_cn_a_symbols(
            as_of_date=as_of,
            universe_limit=universe_limit,
        )
        return symbols, {
            **meta,
            "universe_mode": "ALL_A",
            "symbols_source": str(meta.get("symbols_source") or ALL_A_SYMBOLS_SOURCE),
        }
    symbols, meta = load_constituents_from_db(db, runtime, as_of, universe_limit)
    return symbols, {
        **meta,
        "universe_mode": "ALL_A",
        "symbols_source": ALL_A_SYMBOLS_SOURCE,
    }


def _resolve_pit_index_union(
    mode: str,
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    universe_limit: int | None = None,
    market_data_access: MarketDataAccess | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """从一个或多个 PIT index_code 解析 as-of 成分 union。"""
    mode_upper = str(mode or "").strip().upper()
    index_codes = _PIT_INDEX_CODES_BY_UNIVERSE.get(mode_upper)
    if not index_codes:
        raise UniverseLoadError(
            status=f"ERROR:UNKNOWN_PIT_INDEX_UNIVERSE:{mode_upper}",
            message=f"unknown PIT index universe mode: {mode_upper}",
            meta={"universe_mode": mode_upper, "raw_count": 0},
        )

    all_symbols: set[str] = set()
    canonical_objects: list[str] = []
    per_index_raw_counts: dict[str, int] = {}
    for index_code in index_codes:
        if market_data_access is not None:
            result = market_data_access.load_pit_constituents_snapshot(
                index_code=index_code,
                as_of_date=as_of,
            )
            index_symbols = sorted(
                {
                    normalize_stock_symbol(str(value))
                    for value in result.frame.get("symbol", pd.Series(dtype=str)).tolist()
                    if str(value).strip()
                }
            )
            canonical_objects.extend(list(result.audit.canonical_objects))
        else:
            sql = """
                SELECT DISTINCT symbol
                FROM public.pit_index_constituents
                WHERE index_code = %s
                  AND start_date <= %s
                  AND (end_date IS NULL OR end_date > %s)
                ORDER BY symbol
            """
            index_symbols = _query_pit_symbols(db, runtime, sql, (index_code, as_of, as_of))
            canonical_objects.append("pit_index_constituents")
        per_index_raw_counts[index_code] = len(index_symbols)
        all_symbols.update(index_symbols)

    if not all_symbols:
        raise UniverseLoadError(
            status="EMPTY:INDEX_CONSTITUENTS",
            message="pit_index_constituents has no matching records for requested PIT index universe",
            meta={
                "universe_mode": mode_upper,
                "index_codes": list(index_codes),
                "raw_count": 0,
                "per_index_raw_counts": per_index_raw_counts,
            },
        )

    symbols = sorted(all_symbols)
    raw_count = len(symbols)
    if universe_limit is not None:
        symbols = symbols[:universe_limit]

    canonical_objects = sorted(set(canonical_objects or ["pit_index_constituents"]))
    return symbols, {
        "universe_mode": mode_upper,
        "symbols_source": INDEX_CONSTITUENTS_SYMBOLS_SOURCE,
        "raw_count": raw_count,
        "union_symbol_count": raw_count,
        "constituents_load_status": "OK",
        "load_table": "+".join(canonical_objects),
        "index_code": "+".join(index_codes),
        "index_codes": list(index_codes),
        "per_index_raw_counts": per_index_raw_counts,
        "as_of": str(as_of),
        "canonical_objects": canonical_objects,
    }


def _resolve_hs300_zz500(
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    universe_limit: int | None = None,
    market_data_access: MarketDataAccess | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """HS300_ZZ500 模式: 从 pit_index_constituents 查询中证800成分。"""
    return _resolve_pit_index_union(
        "HS300_ZZ500",
        as_of,
        db,
        runtime,
        universe_limit,
        market_data_access,
    )


def _resolve_csi1000(
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    universe_limit: int | None = None,
    market_data_access: MarketDataAccess | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """CSI1000 mode: query CSI1000 constituents from pit_index_constituents."""
    return _resolve_pit_index_union(
        "CSI1000",
        as_of,
        db,
        runtime,
        universe_limit,
        market_data_access,
    )


def _resolve_hs300_zz500_csi1000(
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    universe_limit: int | None = None,
    market_data_access: MarketDataAccess | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Research-only union of CSI800 and CSI1000 PIT constituents."""
    return _resolve_pit_index_union(
        "HS300_ZZ500_CSI1000",
        as_of,
        db,
        runtime,
        universe_limit,
        market_data_access,
    )


def _resolve_industry(
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    industries: list[str],
    universe_limit: int | None = None,
    market_data_access: MarketDataAccess | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """INDUSTRY 模式: 从 pit_industry_history 查询所选行业的股票。"""
    if not industries:
        raise UniverseLoadError(
            status="ERROR:NO_INDUSTRIES",
            message="INDUSTRY 模式需要选择至少一个行业",
            meta={"universe_mode": "INDUSTRY", "raw_count": 0},
        )

    if market_data_access is not None:
        result = market_data_access.load_pit_industry_snapshot(
            as_of_date=as_of,
            industries=list(industries),
        )
        symbols = sorted(
            {
                normalize_stock_symbol(str(value))
                for value in result.frame.get("symbol", pd.Series(dtype=str)).tolist()
                if str(value).strip()
            }
        )
        canonical_objects = list(result.audit.canonical_objects)
    else:
        placeholders = ",".join(["%s"] * len(industries))
        sql = f"""
            SELECT DISTINCT ts_code
            FROM public.pit_industry_history
            WHERE industry_l1 IN ({placeholders})
              AND start_date <= %s
              AND (end_date IS NULL OR end_date > %s)
            ORDER BY ts_code
        """
        params = tuple(industries) + (as_of, as_of)
        symbols = _query_pit_symbols(db, runtime, sql, params)
        canonical_objects = ["pit_industry_history"]

    if not symbols:
        raise UniverseLoadError(
            status="EMPTY:INDUSTRY_HISTORY",
            message="pit_industry_history 为空或所选行业无匹配记录，请先运行数据导入: "
                    "python -m backend.core.universe.ingest_universe --industry",
            meta={"universe_mode": "INDUSTRY", "industries": industries, "raw_count": 0},
        )

    raw_count = len(symbols)
    if universe_limit is not None:
        symbols = symbols[:universe_limit]

    return symbols, {
        "universe_mode": "INDUSTRY",
        "symbols_source": INDUSTRY_HISTORY_SYMBOLS_SOURCE,
        "raw_count": raw_count,
        "constituents_load_status": "OK",
        "load_table": "+".join(canonical_objects),
        "industries": industries,
        "as_of": str(as_of),
        "canonical_objects": canonical_objects,
    }


def _resolve_custom(
    symbols: list[str] | None,
    universe_limit: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """CUSTOM 模式: 直接使用用户提供的 symbols 列表。"""
    if not symbols:
        raise UniverseLoadError(
            status="ERROR:NO_SYMBOLS",
            message="CUSTOM 模式需要提供 symbols 列表",
            meta={"universe_mode": "CUSTOM", "raw_count": 0},
        )

    normalized = sorted({normalize_stock_symbol(s) for s in symbols if s.strip()})
    raw_count = len(normalized)
    if universe_limit is not None:
        normalized = normalized[:universe_limit]

    return normalized, {
        "universe_mode": "CUSTOM",
        "symbols_source": USER_INPUT_SYMBOLS_SOURCE,
        "raw_count": raw_count,
        "constituents_load_status": "OK",
    }


def _resolve_cn_etf_custom(
    symbols: list[str] | None,
    universe_limit: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    if not symbols:
        raise UniverseLoadError(
            status="ERROR:NO_SYMBOLS",
            message="cn_etf CUSTOM 模式需要至少一个 ETF symbol",
            meta={"universe_mode": "CUSTOM", "raw_count": 0},
        )

    resolved_entries = []
    preset_name = ""
    deferred_reason_codes: dict[str, list[str]] = {}
    for raw in symbols:
        text = str(raw or "").strip()
        if not text:
            continue
        if text.startswith("cn_etf_"):
            preset_name = text
            try:
                preset_symbols = expand_etf_preset(text)
            except ValueError as exc:
                raise UniverseLoadError(
                    status="ERROR:UNSUPPORTED_CN_ETF_PRESET",
                    message=str(exc),
                    meta={
                        "universe_mode": "CUSTOM",
                        "requested_preset": text,
                        "raw_count": 0,
                    },
                ) from exc
            resolved_entries.extend(require_catalog_entry(symbol) for symbol in preset_symbols)
            continue
        deferred_reason = deferred_etf_research_reason(text)
        if deferred_reason:
            deferred_symbol = normalize_cn_etf_ts_code(text)
            deferred_reason_codes[deferred_symbol] = [deferred_reason]
            continue
        try:
            resolved_entries.append(require_catalog_entry(text))
        except ValueError as exc:
            requested_symbol = normalize_cn_etf_ts_code(text)
            raise UniverseLoadError(
                status="ERROR:UNSUPPORTED_CN_ETF_SYMBOL",
                message=str(exc),
                meta={
                    "universe_mode": "CUSTOM",
                    "requested_symbol": requested_symbol,
                    "raw_count": 0,
                },
            ) from exc

    if deferred_reason_codes:
        raise UniverseLoadError(
            status="ERROR:DEFERRED_CN_ETF_SYMBOL",
            message="cn_etf shadow pool v1 does not include deferred ETF candidates",
            meta={
                "universe_mode": "CUSTOM",
                "deferred_symbols": sorted(deferred_reason_codes),
                "deferred_reason_codes": deferred_reason_codes,
                "raw_count": len(resolved_entries),
            },
        )

    dedup = {entry.ts_code: entry for entry in resolved_entries}
    ts_codes = sorted(dedup)
    if universe_limit is not None:
        ts_codes = ts_codes[:universe_limit]
    entries = [dedup[ts_code] for ts_code in ts_codes]
    resolved_preset_id = preset_name or preset_batch_id(preset_name, ts_codes)
    formal_scope = set(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS) | set(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES)
    shadow_roles = shadow_pool_role_map(resolved_preset_id) if is_research_shadow_pool(resolved_preset_id) else {}
    shadow_symbols = [entry.ts_code for entry in entries if entry.ts_code in shadow_roles]
    symbol_classification = {
        entry.ts_code: (
            "formal"
            if entry.ts_code in formal_scope
            else ("shadow" if entry.ts_code in shadow_roles else "research_only")
        )
        for entry in entries
    }
    promotion_gates = build_shadow_pool_promotion_gates(tuple(shadow_symbols), pool_name=resolved_preset_id)
    return [entry.symbol for entry in entries], {
        "universe_mode": "CUSTOM",
        "symbols_source": "cn_etf_catalog_whitelist",
        "raw_count": len(dedup),
        "constituents_load_status": "OK",
        "preset_id": resolved_preset_id,
        "pool_version": resolved_preset_id,
        "research_only": bool(is_research_shadow_pool(resolved_preset_id)),
        "etf_symbols": [entry.ts_code for entry in entries],
        "etf_internal_symbols": [entry.symbol for entry in entries],
        "etf_batch": resolved_preset_id,
        "formal_scope_symbols": [entry.ts_code for entry in entries if entry.ts_code in formal_scope],
        "shadow_symbols": shadow_symbols,
        "shadow_role_map": {symbol: shadow_roles[symbol] for symbol in shadow_symbols},
        "deferred_symbols": [],
        "deferred_reason_codes": {},
        "research_classification_by_symbol": symbol_classification,
        "promotion_gate_by_symbol": promotion_gates,
        "formal_eligibility_by_symbol": {
            symbol: bool(gate.get("formal_eligible", False))
            for symbol, gate in promotion_gates.items()
        },
        "catalog_table": "pit_cn_etf_master",
    }


def resolve_universe_by_mode(
    mode: str,
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    asset_scope: str | None = None,
    industries: list[str] | None = None,
    symbols: list[str] | None = None,
    universe_limit: int | None = None,
    market_data_access: MarketDataAccess | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """根据 universe_mode 解析出 PIT-safe 的 symbols 列表。

    返回 (symbols, meta) 元组。
    """
    mode_upper = (mode or "CUSTOM").strip().upper()
    asset_profile = resolve_asset_profile(asset_scope)
    canonical_scope = asset_profile.asset_scope
    common_meta = {
        "asset_scope": canonical_scope,
        "asset_profile_id": asset_profile.asset_profile_id,
        "market_profile_id": asset_profile.market_profile.profile_id,
        "asset_family": asset_profile.asset_family,
    }

    if canonical_scope == "cn_etf":
        if mode_upper != "CUSTOM":
            raise UniverseLoadError(
                status="ERROR:UNSUPPORTED_MODE",
                message=f"cn_etf universe resolver only supports CUSTOM mode, got {mode_upper}",
                meta={
                    **common_meta,
                    "universe_mode": mode_upper,
                    "raw_count": 0,
                },
            )
        resolved_symbols, meta = _resolve_cn_etf_custom(symbols, universe_limit)
        meta.update(common_meta)
        return resolved_symbols, meta

    if canonical_scope != "cn_a_equity":
        raise UniverseLoadError(
            status="ERROR:UNSUPPORTED_ASSET_SCOPE",
            message=f"universe resolver adapter unavailable for asset_scope={canonical_scope}",
            meta={
                **common_meta,
                "universe_mode": mode_upper,
                "raw_count": 0,
            },
        )

    if mode_upper == "ALL_A":
        resolved_symbols, meta = _resolve_all_a(as_of, db, runtime, universe_limit, market_data_access)
        meta.update(common_meta)
        return resolved_symbols, meta
    elif mode_upper == "HS300_ZZ500":
        resolved_symbols, meta = _resolve_hs300_zz500(as_of, db, runtime, universe_limit, market_data_access)
        meta.update(common_meta)
        return resolved_symbols, meta
    elif mode_upper == "CSI1000":
        resolved_symbols, meta = _resolve_csi1000(as_of, db, runtime, universe_limit, market_data_access)
        meta.update(common_meta)
        return resolved_symbols, meta
    elif mode_upper == "HS300_ZZ500_CSI1000":
        resolved_symbols, meta = _resolve_hs300_zz500_csi1000(
            as_of,
            db,
            runtime,
            universe_limit,
            market_data_access,
        )
        meta.update(common_meta)
        return resolved_symbols, meta
    elif mode_upper == "INDUSTRY":
        resolved_symbols, meta = _resolve_industry(
            as_of,
            db,
            runtime,
            industries or [],
            universe_limit,
            market_data_access,
        )
        meta.update(common_meta)
        return resolved_symbols, meta
    elif mode_upper == "CUSTOM":
        resolved_symbols, meta = _resolve_custom(symbols, universe_limit)
        meta.update(common_meta)
        return resolved_symbols, meta
    else:
        raise UniverseLoadError(
            status=f"ERROR:UNKNOWN_MODE:{mode_upper}",
            message=f"未知的 universe_mode: {mode_upper}",
            meta={
                **common_meta,
                "universe_mode": mode_upper,
                "raw_count": 0,
            },
        )
