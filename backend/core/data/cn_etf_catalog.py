from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


_TS_TO_INTERNAL_EXCHANGE = {
    "SH": "sh",
    "SZ": "sz",
}
_INTERNAL_TO_TS_EXCHANGE = {
    "sh": "SH",
    "sz": "SZ",
}


@dataclass(frozen=True, slots=True)
class CnEtfCatalogEntry:
    ts_code: str
    symbol: str
    name: str
    exchange: str
    batch_id: str
    exposure_bucket: str
    list_date: str | None = None
    delist_date: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


FIRST_WAVE_CORE = "cn_etf_first_wave_core"
FIRST_WAVE_ALL = "cn_etf_first_wave_all"
SINGLE_ASSET_TEMPLATE = "cn_etf_single_asset_template"
FIRST_WAVE_BATCH = "first_wave"


_CATALOG: tuple[CnEtfCatalogEntry, ...] = (
    CnEtfCatalogEntry("510300.SH", "sh510300", "沪深300ETF", "SSE", FIRST_WAVE_BATCH, "broad_equity"),
    CnEtfCatalogEntry("510500.SH", "sh510500", "中证500ETF", "SSE", FIRST_WAVE_BATCH, "mid_cap_equity"),
    CnEtfCatalogEntry("510050.SH", "sh510050", "上证50ETF", "SSE", FIRST_WAVE_BATCH, "large_cap_equity"),
    CnEtfCatalogEntry("518880.SH", "sh518880", "黄金ETF", "SSE", FIRST_WAVE_BATCH, "gold"),
    CnEtfCatalogEntry("511010.SH", "sh511010", "5年国债ETF", "SSE", FIRST_WAVE_BATCH, "bond"),
    CnEtfCatalogEntry("512100.SH", "sh512100", "中证1000ETF", "SSE", FIRST_WAVE_BATCH, "small_cap_equity"),
    CnEtfCatalogEntry("512890.SH", "sh512890", "红利低波ETF", "SSE", FIRST_WAVE_BATCH, "dividend_low_vol"),
    CnEtfCatalogEntry("588000.SH", "sh588000", "科创50ETF", "SSE", FIRST_WAVE_BATCH, "technology_growth"),
    CnEtfCatalogEntry("159915.SZ", "sz159915", "创业板ETF", "SZSE", FIRST_WAVE_BATCH, "growth_equity"),
)


CATALOG_BY_TS_CODE = {entry.ts_code: entry for entry in _CATALOG}
CATALOG_BY_INTERNAL_SYMBOL = {entry.symbol: entry for entry in _CATALOG}

PRESET_GROUPS: dict[str, tuple[str, ...]] = {
    FIRST_WAVE_CORE: (
        "510300.SH",
        "510500.SH",
        "510050.SH",
        "518880.SH",
        "511010.SH",
        "512100.SH",
    ),
    FIRST_WAVE_ALL: tuple(entry.ts_code for entry in _CATALOG),
}


def list_first_wave_entries() -> tuple[CnEtfCatalogEntry, ...]:
    return _CATALOG


def supported_etf_ts_codes() -> tuple[str, ...]:
    return tuple(entry.ts_code for entry in _CATALOG)


def normalize_cn_etf_ts_code(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if "." in upper:
        code, exch = upper.split(".", 1)
        if len(code) == 6 and exch in _TS_TO_INTERNAL_EXCHANGE:
            return f"{code}.{exch}"
    lower = text.lower()
    if len(lower) == 8 and lower[:2] in _INTERNAL_TO_TS_EXCHANGE and lower[2:].isdigit():
        return f"{lower[2:]}.{_INTERNAL_TO_TS_EXCHANGE[lower[:2]]}"
    if len(text) == 6 and text.isdigit():
        if text.startswith(("5", "6")):
            return f"{text}.SH"
        return f"{text}.SZ"
    return upper


def normalize_cn_etf_symbol(value: Any) -> str:
    ts_code = normalize_cn_etf_ts_code(value)
    if "." in ts_code:
        code, exch = ts_code.split(".", 1)
        prefix = _TS_TO_INTERNAL_EXCHANGE.get(exch.upper())
        if prefix:
            return f"{prefix}{code}".lower()
    lower = str(value or "").strip().lower()
    if len(lower) == 8 and lower[:2] in _INTERNAL_TO_TS_EXCHANGE and lower[2:].isdigit():
        return lower
    return lower


def get_catalog_entry(value: Any) -> CnEtfCatalogEntry | None:
    ts_code = normalize_cn_etf_ts_code(value)
    if ts_code in CATALOG_BY_TS_CODE:
        return CATALOG_BY_TS_CODE[ts_code]
    internal = normalize_cn_etf_symbol(value)
    if internal in CATALOG_BY_INTERNAL_SYMBOL:
        return CATALOG_BY_INTERNAL_SYMBOL[internal]
    return None


def require_catalog_entry(value: Any) -> CnEtfCatalogEntry:
    entry = get_catalog_entry(value)
    if entry is None:
        raise ValueError(f"unsupported cn_etf symbol: {value}")
    return entry


def expand_etf_preset(name: str) -> list[str]:
    key = str(name or "").strip()
    if not key:
        return []
    symbols = PRESET_GROUPS.get(key)
    if symbols is None:
        raise ValueError(f"unsupported cn_etf preset: {name}")
    return list(symbols)


def preset_batch_id(name: str, symbols: list[str]) -> str:
    key = str(name or "").strip()
    if key == FIRST_WAVE_CORE:
        return FIRST_WAVE_CORE
    if key == FIRST_WAVE_ALL:
        return FIRST_WAVE_ALL
    if len(symbols) == 1:
        return SINGLE_ASSET_TEMPLATE
    return FIRST_WAVE_BATCH


__all__ = [
    "CnEtfCatalogEntry",
    "FIRST_WAVE_ALL",
    "FIRST_WAVE_BATCH",
    "FIRST_WAVE_CORE",
    "SINGLE_ASSET_TEMPLATE",
    "expand_etf_preset",
    "get_catalog_entry",
    "list_first_wave_entries",
    "normalize_cn_etf_symbol",
    "normalize_cn_etf_ts_code",
    "preset_batch_id",
    "require_catalog_entry",
    "supported_etf_ts_codes",
]
