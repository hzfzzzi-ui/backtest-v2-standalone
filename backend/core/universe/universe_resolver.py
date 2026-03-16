"""Universe resolver — 根据 mode + as_of 日期从 DB 查询 symbols 列表。

支持 4 种模式: ALL_A / HS300_ZZ500 / INDUSTRY / CUSTOM
"""
from __future__ import annotations

from datetime import date
from typing import Any

from backend.core.config.asset_profiles import canonical_asset_scope
from backend.core.config.models import DBConfig, DBRuntimeConfig
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
) -> tuple[list[str], dict[str, Any]]:
    """ALL_A 模式: 返回截至 as_of 全部活跃 CN_A 股票。"""
    symbols, meta = load_constituents_from_db(db, runtime, as_of, universe_limit)
    return symbols, {
        **meta,
        "universe_mode": "ALL_A",
        "symbols_source": ALL_A_SYMBOLS_SOURCE,
    }


def _resolve_hs300_zz500(
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    universe_limit: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """HS300_ZZ500 模式: 从 pit_index_constituents 查询中证800成分。"""
    sql = """
        SELECT DISTINCT symbol
        FROM public.pit_index_constituents
        WHERE index_code = '000906.SH'
          AND start_date <= %s
          AND (end_date IS NULL OR end_date > %s)
        ORDER BY symbol
    """
    symbols = _query_pit_symbols(db, runtime, sql, (as_of, as_of))

    if not symbols:
        raise UniverseLoadError(
            status="EMPTY:INDEX_CONSTITUENTS",
            message="pit_index_constituents 为空或无匹配记录，请先运行数据导入: "
                    "python -m backend.core.universe.ingest_universe --index",
            meta={"universe_mode": "HS300_ZZ500", "raw_count": 0},
        )

    raw_count = len(symbols)
    if universe_limit is not None:
        symbols = symbols[:universe_limit]

    return symbols, {
        "universe_mode": "HS300_ZZ500",
        "symbols_source": INDEX_CONSTITUENTS_SYMBOLS_SOURCE,
        "raw_count": raw_count,
        "constituents_load_status": "OK",
        "load_table": "pit_index_constituents",
        "index_code": "000906.SH",
        "as_of": str(as_of),
    }


def _resolve_csi1000(
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    universe_limit: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """CSI1000 mode: query CSI1000 constituents from pit_index_constituents."""
    sql = """
        SELECT DISTINCT symbol
        FROM public.pit_index_constituents
        WHERE index_code = '000852.SH'
          AND start_date <= %s
          AND (end_date IS NULL OR end_date > %s)
        ORDER BY symbol
    """
    symbols = _query_pit_symbols(db, runtime, sql, (as_of, as_of))

    if not symbols:
        raise UniverseLoadError(
            status="EMPTY:INDEX_CONSTITUENTS",
            message="pit_index_constituents has no matching 000852.SH records",
            meta={"universe_mode": "CSI1000", "raw_count": 0},
        )

    raw_count = len(symbols)
    if universe_limit is not None:
        symbols = symbols[:universe_limit]

    return symbols, {
        "universe_mode": "CSI1000",
        "symbols_source": INDEX_CONSTITUENTS_SYMBOLS_SOURCE,
        "raw_count": raw_count,
        "constituents_load_status": "OK",
        "load_table": "pit_index_constituents",
        "index_code": "000852.SH",
        "as_of": str(as_of),
    }


def _resolve_industry(
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    industries: list[str],
    universe_limit: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """INDUSTRY 模式: 从 pit_industry_history 查询所选行业的股票。"""
    if not industries:
        raise UniverseLoadError(
            status="ERROR:NO_INDUSTRIES",
            message="INDUSTRY 模式需要选择至少一个行业",
            meta={"universe_mode": "INDUSTRY", "raw_count": 0},
        )

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
        "load_table": "pit_industry_history",
        "industries": industries,
        "as_of": str(as_of),
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


def resolve_universe_by_mode(
    mode: str,
    as_of: date,
    db: DBConfig,
    runtime: DBRuntimeConfig,
    asset_scope: str = "cn_a_equity",
    industries: list[str] | None = None,
    symbols: list[str] | None = None,
    universe_limit: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """根据 universe_mode 解析出 PIT-safe 的 symbols 列表。

    返回 (symbols, meta) 元组。
    """
    mode_upper = (mode or "CUSTOM").strip().upper()
    canonical_scope = canonical_asset_scope(asset_scope)

    if mode_upper == "ALL_A":
        resolved_symbols, meta = _resolve_all_a(as_of, db, runtime, universe_limit)
        meta["asset_scope"] = canonical_scope
        return resolved_symbols, meta
    elif mode_upper == "HS300_ZZ500":
        resolved_symbols, meta = _resolve_hs300_zz500(as_of, db, runtime, universe_limit)
        meta["asset_scope"] = canonical_scope
        return resolved_symbols, meta
    elif mode_upper == "CSI1000":
        resolved_symbols, meta = _resolve_csi1000(as_of, db, runtime, universe_limit)
        meta["asset_scope"] = canonical_scope
        return resolved_symbols, meta
    elif mode_upper == "INDUSTRY":
        resolved_symbols, meta = _resolve_industry(as_of, db, runtime, industries or [], universe_limit)
        meta["asset_scope"] = canonical_scope
        return resolved_symbols, meta
    elif mode_upper == "CUSTOM":
        resolved_symbols, meta = _resolve_custom(symbols, universe_limit)
        meta["asset_scope"] = canonical_scope
        return resolved_symbols, meta
    else:
        raise UniverseLoadError(
            status=f"ERROR:UNKNOWN_MODE:{mode_upper}",
            message=f"未知的 universe_mode: {mode_upper}",
            meta={"universe_mode": mode_upper, "raw_count": 0},
        )
