from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any, Literal


ALL_A_SYMBOLS_SOURCE = "pit_security_master+pams_ohlcv_daily"
INDEX_CONSTITUENTS_SYMBOLS_SOURCE = "pit_index_constituents"
INDUSTRY_HISTORY_SYMBOLS_SOURCE = "pit_industry_history"
USER_INPUT_SYMBOLS_SOURCE = "user_input"

ResolveAsofPolicy = Literal["start_date", "end_date", "request_local"]


@dataclass(frozen=True, slots=True)
class UniverseLineage:
    mode: str
    symbols_source: str
    load_table: str | None
    resolver_entrypoint: str
    resolve_asof_policy: ResolveAsofPolicy
    dynamic_all_a_entry: bool
    import_assets: tuple[str, ...]
    notes: str = ""


UNIVERSE_LINEAGE: dict[str, UniverseLineage] = {
    "ALL_A": UniverseLineage(
        mode="ALL_A",
        symbols_source=ALL_A_SYMBOLS_SOURCE,
        load_table=ALL_A_SYMBOLS_SOURCE,
        resolver_entrypoint="backend.core.universe.universe_resolver._resolve_all_a",
        resolve_asof_policy="end_date",
        dynamic_all_a_entry=True,
        import_assets=(),
        notes="Runtime resolves active CN_A symbols from security master plus OHLCV availability; it does not read pit_index_constituents.",
    ),
    "HS300_ZZ500": UniverseLineage(
        mode="HS300_ZZ500",
        symbols_source=INDEX_CONSTITUENTS_SYMBOLS_SOURCE,
        load_table="pit_index_constituents",
        resolver_entrypoint="backend.core.universe.universe_resolver._resolve_hs300_zz500",
        resolve_asof_policy="start_date",
        dynamic_all_a_entry=False,
        import_assets=(
            "backend/scripts/fetch_csi800_pit_history.py",
            "backend/scripts/build_csi800_formal_history.py",
            "backend/scripts/import_csi800_pit.py",
            "backend/scripts/fetch_csi800_pit.py (fallback/approximate only)",
            "backend/core/universe/ingest_universe.py --index",
        ),
        notes=(
            "Runtime expects point-in-time CSI800 constituent rows under index_code=000906.SH. "
            "Formal lineage is long-history seed plus optional tushare trade_date tail -> "
            "formal history materialization -> replace import; "
            "monthly snapshots are fallback only."
        ),
    ),
    "CSI1000": UniverseLineage(
        mode="CSI1000",
        symbols_source=INDEX_CONSTITUENTS_SYMBOLS_SOURCE,
        load_table="pit_index_constituents",
        resolver_entrypoint="backend.core.universe.universe_resolver._resolve_csi1000",
        resolve_asof_policy="start_date",
        dynamic_all_a_entry=False,
        import_assets=(
            "data_cache/csi1000_rebalance_calendar.csv",
            "backend/scripts/fetch_csi1000_pit_by_calendar.py",
            "backend/scripts/import_csi1000_pit.py",
            "backend/scripts/fetch_csi1000_pit_monthly.py (fallback/approximate only)",
            "backend/scripts/fetch_csi1000_pit.py (fallback/static only)",
        ),
        notes=(
            "Runtime expects point-in-time CSI1000 constituent rows under index_code=000852.SH. "
            "Formal lineage is rebalance_calendar -> calendar snapshots -> changes -> import; "
            "historical monthly/static scripts are fallback only."
        ),
    ),
    "HS300_ZZ500_CSI1000": UniverseLineage(
        mode="HS300_ZZ500_CSI1000",
        symbols_source=INDEX_CONSTITUENTS_SYMBOLS_SOURCE,
        load_table="pit_index_constituents",
        resolver_entrypoint="backend.core.universe.universe_resolver._resolve_hs300_zz500_csi1000",
        resolve_asof_policy="start_date",
        dynamic_all_a_entry=False,
        import_assets=(
            "backend/scripts/fetch_csi800_pit_history.py",
            "backend/scripts/build_csi800_formal_history.py",
            "backend/scripts/import_csi800_pit.py",
            "data_cache/csi1000_rebalance_calendar.csv",
            "backend/scripts/fetch_csi1000_pit_by_calendar.py",
            "backend/scripts/import_csi1000_pit.py",
        ),
        notes=(
            "Research-only union of CSI800 (000906.SH, covering HS300+ZZ500) and "
            "CSI1000 (000852.SH) PIT constituent rows. Runtime must preserve PIT_DYNAMIC "
            "membership and audit the CSI1000 subset with refresh sidecar evidence."
        ),
    ),
    "INDUSTRY": UniverseLineage(
        mode="INDUSTRY",
        symbols_source=INDUSTRY_HISTORY_SYMBOLS_SOURCE,
        load_table="pit_industry_history",
        resolver_entrypoint="backend.core.universe.universe_resolver._resolve_industry",
        resolve_asof_policy="start_date",
        dynamic_all_a_entry=False,
        import_assets=(
            "backend/core/universe/ingest_universe.py --industry",
        ),
        notes="Runtime resolves symbols directly from pit_industry_history at the request as_of date.",
    ),
    "CUSTOM": UniverseLineage(
        mode="CUSTOM",
        symbols_source=USER_INPUT_SYMBOLS_SOURCE,
        load_table=None,
        resolver_entrypoint="backend.core.universe.universe_resolver._resolve_custom",
        resolve_asof_policy="request_local",
        dynamic_all_a_entry=False,
        import_assets=(),
        notes="Runtime uses user-provided symbols and does not require PIT universe tables.",
    ),
}


def normalize_universe_mode(mode: str | None) -> str:
    return str(mode or "CUSTOM").strip().upper() or "CUSTOM"


def get_universe_lineage(mode: str | None) -> UniverseLineage:
    key = normalize_universe_mode(mode)
    if key not in UNIVERSE_LINEAGE:
        raise ValueError(f"unknown universe mode: {key}")
    return UNIVERSE_LINEAGE[key]


def list_universe_lineage() -> list[UniverseLineage]:
    return [
        UNIVERSE_LINEAGE[key]
        for key in (
            "ALL_A",
            "HS300_ZZ500",
            "CSI1000",
            "HS300_ZZ500_CSI1000",
            "INDUSTRY",
            "CUSTOM",
        )
    ]


def resolve_universe_timing(
    mode: str | None,
    *,
    start: date,
    end: date,
) -> tuple[date, bool]:
    lineage = get_universe_lineage(mode)
    if lineage.resolve_asof_policy == "end_date":
        return end, lineage.dynamic_all_a_entry
    return start, lineage.dynamic_all_a_entry


def annotate_universe_meta(
    meta: dict[str, Any] | None,
    *,
    mode: str | None,
    start: date,
    end: date,
) -> dict[str, Any]:
    resolved_meta = dict(meta or {})
    lineage = get_universe_lineage(mode)
    resolve_asof, dynamic_all_a_entry = resolve_universe_timing(mode, start=start, end=end)
    resolved_meta["universe_mode"] = lineage.mode
    resolved_meta.setdefault("symbols_source", lineage.symbols_source)
    if lineage.load_table:
        resolved_meta.setdefault("load_table", lineage.load_table)
    resolved_meta["resolve_asof"] = str(resolve_asof)
    resolved_meta["dynamic_all_a_entry"] = bool(dynamic_all_a_entry)
    return resolved_meta


def lineage_to_dict(mode: str | None) -> dict[str, Any]:
    return asdict(get_universe_lineage(mode))
