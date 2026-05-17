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
TEMPLATE_A_A1_CANDIDATES = "cn_etf_template_a_a1_candidates"
TEMPLATE_A_A1_BATCH = "template_a_a1"
CN_ETF_RESEARCH_SHADOW_POOL_V1 = "cn_etf_research_shadow_pool_v1"
CN_ETF_RESEARCH_SHADOW_POOL_V1_BATCH = "research_shadow_v1"
CN_ETF_RESEARCH_SHADOW_POOL_V1_SYMBOLS = (
    "510880.SH",
    "512890.SH",
    "518880.SH",
    "159915.SZ",
    "588000.SH",
    "159845.SZ",
)
CN_ETF_RESEARCH_REALWORLD_POOL_V1 = "cn_etf_research_realworld_pool_v1"
CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH = "research_realworld_v1"
CN_ETF_RESEARCH_REALWORLD_POOL_V1_SYMBOLS = (
    "510050.SH",
    "510180.SH",
    "510300.SH",
    "510500.SH",
    "512100.SH",
    "159845.SZ",
    "159901.SZ",
    "159915.SZ",
    "159949.SZ",
    "588000.SH",
    "510880.SH",
    "512890.SH",
    "518880.SH",
    "511010.SH",
    "511260.SH",
    "511880.SH",
    "512000.SH",
    "512800.SH",
    "159928.SZ",
    "512690.SH",
    "512010.SH",
    "512170.SH",
    "512480.SH",
    "512760.SH",
    "515030.SH",
    "515790.SH",
    "515220.SH",
    "512400.SH",
    "513100.SH",
    "513500.SH",
    "159920.SZ",
    "513180.SH",
    "513050.SH",
)
CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2 = "cn_etf_research_industry_theme_pool_v2"
CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH = "research_industry_theme_v2"
CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_NEW_SYMBOLS = (
    "159819.SZ",
    "562500.SH",
    "512720.SH",
    "515230.SH",
    "516510.SH",
    "515880.SH",
    "512980.SH",
    "159869.SZ",
    "512660.SH",
    "159755.SZ",
    "159611.SZ",
    "512200.SH",
    "516950.SH",
    "516020.SH",
    "515210.SH",
    "516780.SH",
    "159865.SZ",
    "159930.SZ",
    "159790.SZ",
    "512580.SH",
    "159996.SZ",
    "159997.SZ",
    "159732.SZ",
)
CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_SYMBOLS = (
    CN_ETF_RESEARCH_REALWORLD_POOL_V1_SYMBOLS + CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_NEW_SYMBOLS
)
CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2 = "cn_etf_research_style_smart_beta_pool_v2"
CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH = "research_style_smart_beta_v2"
CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_NEW_SYMBOLS = (
    "159905.SZ",
    "515080.SH",
    "515180.SH",
    "515890.SH",
    "515300.SH",
    "512530.SH",
    "515450.SH",
    "515100.SH",
    "512260.SH",
    "512390.SH",
    "159758.SZ",
    "515910.SH",
    "560500.SH",
    "159201.SZ",
    "159399.SZ",
    "563900.SH",
    "510030.SH",
    "159913.SZ",
    "512040.SH",
    "159966.SZ",
    "159617.SZ",
    "562320.SH",
    "562530.SH",
    "159338.SZ",
    "512050.SH",
    "560570.SH",
    "159296.SZ",
    "510060.SH",
    "510270.SH",
    "512950.SH",
    "561580.SH",
    "561990.SH",
    "561300.SH",
    "561550.SH",
    "159610.SZ",
    "159680.SZ",
    "159675.SZ",
    "588370.SH",
    "515590.SH",
    "159906.SZ",
    "159967.SZ",
    "159606.SZ",
    "562520.SH",
)
CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_SYMBOLS = (
    CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_SYMBOLS + CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_NEW_SYMBOLS
)
CN_ETF_RESEARCH_SHADOW_POOL_V1_ROLE_MAP = {
    "510880.SH": "shadow_value_dividend",
    "512890.SH": "shadow_dividend_low_vol_overlap",
    "518880.SH": "shadow_defense_gold",
    "159915.SZ": "shadow_growth_chinext",
    "588000.SH": "shadow_technology_growth_star50",
    "159845.SZ": "shadow_csi1000_replacement_for_512100",
}
CN_ETF_RESEARCH_REALWORLD_POOL_V1_ROLE_MAP = {
    "510050.SH": "realworld_broad_sse50_large",
    "510180.SH": "realworld_broad_sse180_large_overlap",
    "510300.SH": "realworld_broad_hs300_core",
    "510500.SH": "realworld_broad_csi500_mid",
    "512100.SH": "realworld_broad_csi1000_first_wave",
    "159845.SZ": "realworld_broad_csi1000_alt_short_history",
    "159901.SZ": "realworld_broad_sz100",
    "159915.SZ": "realworld_growth_chinext",
    "159949.SZ": "realworld_growth_chinext50_short_history",
    "588000.SH": "realworld_growth_star50_short_history",
    "510880.SH": "realworld_style_dividend",
    "512890.SH": "realworld_style_dividend_low_vol_short_history",
    "518880.SH": "realworld_defense_gold",
    "511010.SH": "realworld_defense_treasury_5y",
    "511260.SH": "realworld_defense_treasury_10y_duration_layer",
    "511880.SH": "realworld_defense_money_etf_cash_equivalent",
    "512000.SH": "realworld_sector_broker",
    "512800.SH": "realworld_sector_bank",
    "159928.SZ": "realworld_sector_consumer",
    "512690.SH": "realworld_sector_liquor",
    "512010.SH": "realworld_sector_medicine",
    "512170.SH": "realworld_sector_medical",
    "512480.SH": "realworld_sector_semiconductor",
    "512760.SH": "realworld_sector_chip",
    "515030.SH": "realworld_sector_new_energy_vehicle",
    "515790.SH": "realworld_sector_photovoltaic",
    "515220.SH": "realworld_sector_coal",
    "512400.SH": "realworld_sector_nonferrous_metals",
    "513100.SH": "realworld_cross_border_nasdaq_qdii",
    "513500.SH": "realworld_cross_border_sp500_qdii",
    "159920.SZ": "realworld_cross_border_hang_seng",
    "513180.SH": "realworld_cross_border_hang_seng_tech_short_history",
    "513050.SH": "realworld_cross_border_china_internet",
}
CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_ROLE_MAP = {
    **CN_ETF_RESEARCH_REALWORLD_POOL_V1_ROLE_MAP,
    "159819.SZ": "industry_v2_ai",
    "562500.SH": "industry_v2_robotics",
    "512720.SH": "industry_v2_computer",
    "515230.SH": "industry_v2_software",
    "516510.SH": "industry_v2_cloud_computing",
    "515880.SH": "industry_v2_communication",
    "512980.SH": "industry_v2_media",
    "159869.SZ": "industry_v2_game",
    "512660.SH": "industry_v2_defense_military",
    "159755.SZ": "industry_v2_battery",
    "159611.SZ": "industry_v2_power",
    "512200.SH": "industry_v2_real_estate",
    "516950.SH": "industry_v2_infrastructure",
    "516020.SH": "industry_v2_chemical",
    "515210.SH": "industry_v2_steel",
    "516780.SH": "industry_v2_rare_earth",
    "159865.SZ": "industry_v2_breeding",
    "159930.SZ": "industry_v2_energy",
    "159790.SZ": "industry_v2_carbon_neutral",
    "512580.SH": "industry_v2_environmental_protection",
    "159996.SZ": "industry_v2_home_appliance",
    "159997.SZ": "industry_v2_electronics",
    "159732.SZ": "industry_v2_consumer_electronics",
}
CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_ROLE_MAP = {
    **CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_ROLE_MAP,
    "159905.SZ": "style_v2_dividend_alt",
    "515080.SH": "style_v2_csi_dividend",
    "515180.SH": "style_v2_csi_dividend_fee_low",
    "515890.SH": "style_v2_csi_dividend_fee_low",
    "515300.SH": "style_v2_hs300_dividend_low_vol",
    "512530.SH": "style_v2_hs300_dividend",
    "515450.SH": "style_v2_dividend_low_vol_50",
    "515100.SH": "style_v2_dividend_low_vol_100",
    "512260.SH": "style_v2_csi500_low_vol",
    "512390.SH": "style_v2_china_low_vol",
    "159758.SZ": "style_v2_dividend_quality",
    "515910.SH": "style_v2_quality",
    "560500.SH": "style_v2_csi500_quality_growth",
    "159201.SZ": "style_v2_free_cashflow_short_history",
    "159399.SZ": "style_v2_cashflow_short_history",
    "563900.SH": "style_v2_hs300_free_cashflow_short_history",
    "510030.SH": "style_v2_value",
    "159913.SZ": "style_v2_sz_value",
    "512040.SH": "style_v2_value_100",
    "159966.SZ": "style_v2_chinext_value",
    "159617.SZ": "style_v2_csi500_value",
    "562320.SH": "style_v2_hs300_value_short_history",
    "562530.SH": "style_v2_csi1000_value_short_history",
    "159338.SZ": "style_v2_a500_short_history",
    "512050.SH": "style_v2_a500_short_history",
    "560570.SH": "style_v2_a500_dividend_short_history",
    "159296.SZ": "style_v2_a500_dividend_low_vol_short_history",
    "510060.SH": "style_v2_central_soe",
    "510270.SH": "style_v2_state_owned",
    "512950.SH": "style_v2_central_soe_reform",
    "561580.SH": "style_v2_central_soe_dividend_short_history",
    "561990.SH": "style_v2_hs300_enhanced_short_history",
    "561300.SH": "style_v2_hs300_enhanced_short_history",
    "561550.SH": "style_v2_csi500_enhanced_short_history",
    "159610.SZ": "style_v2_csi500_enhanced_short_history",
    "159680.SZ": "style_v2_csi1000_enhanced_short_history",
    "159675.SZ": "style_v2_chinext_enhanced_short_history",
    "588370.SH": "style_v2_star50_enhanced_short_history",
    "515590.SH": "style_v2_csi500_equal_weight",
    "159906.SZ": "style_v2_sz_growth",
    "159967.SZ": "style_v2_chinext_growth",
    "159606.SZ": "style_v2_csi500_growth_short_history",
    "562520.SH": "style_v2_csi1000_growth_short_history",
}
CN_ETF_RESEARCH_SHADOW_POOL_V1_SHORT_HISTORY_SYMBOLS = frozenset({"588000.SH", "159845.SZ"})
CN_ETF_RESEARCH_REALWORLD_POOL_V1_FORMAL_ANCHOR_SYMBOLS = frozenset(
    {"510050.SH", "510300.SH", "510500.SH", "512100.SH", "511010.SH"}
)
CN_ETF_RESEARCH_REALWORLD_POOL_V1_SHORT_HISTORY_SYMBOLS = frozenset(
    {
        "159845.SZ",
        "159949.SZ",
        "588000.SH",
        "512890.SH",
        "512690.SH",
        "512170.SH",
        "512480.SH",
        "512760.SH",
        "515030.SH",
        "515790.SH",
        "515220.SH",
        "513180.SH",
    }
)
CN_ETF_RESEARCH_REALWORLD_POOL_V1_CASH_SEMANTICS_SYMBOLS = frozenset({"511880.SH"})
CN_ETF_RESEARCH_REALWORLD_POOL_V1_DURATION_LAYER_SYMBOLS = frozenset({"511260.SH"})
CN_ETF_RESEARCH_REALWORLD_POOL_V1_CROSS_BORDER_SYMBOLS = frozenset(
    {"513100.SH", "513500.SH", "159920.SZ", "513180.SH", "513050.SH"}
)
CN_ETF_RESEARCH_REALWORLD_POOL_V1_SECTOR_THEME_SYMBOLS = frozenset(
    {
        "512000.SH",
        "512800.SH",
        "159928.SZ",
        "512690.SH",
        "512010.SH",
        "512170.SH",
        "512480.SH",
        "512760.SH",
        "515030.SH",
        "515790.SH",
        "515220.SH",
        "512400.SH",
    }
)
CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_SECTOR_THEME_SYMBOLS = frozenset(
    set(CN_ETF_RESEARCH_REALWORLD_POOL_V1_SECTOR_THEME_SYMBOLS)
    | set(CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_NEW_SYMBOLS)
)
CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_SHORT_HISTORY_SYMBOLS = frozenset(
    set(CN_ETF_RESEARCH_REALWORLD_POOL_V1_SHORT_HISTORY_SYMBOLS)
    | {
        "515080.SH",
        "515180.SH",
        "515890.SH",
        "515300.SH",
        "512530.SH",
        "515450.SH",
        "515100.SH",
        "512260.SH",
        "512390.SH",
        "159758.SZ",
        "515910.SH",
        "560500.SH",
        "159201.SZ",
        "159399.SZ",
        "563900.SH",
        "512040.SH",
        "159966.SZ",
        "159617.SZ",
        "562320.SH",
        "562530.SH",
        "159338.SZ",
        "512050.SH",
        "560570.SH",
        "159296.SZ",
        "512950.SH",
        "561580.SH",
        "561990.SH",
        "561300.SH",
        "561550.SH",
        "159610.SZ",
        "159680.SZ",
        "159675.SZ",
        "588370.SH",
        "515590.SH",
        "159967.SZ",
        "159606.SZ",
        "562520.SH",
    }
)
CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1 = "cn_etf_research_domestic_pool_base_v1"
CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_BATCH = "research_domestic_pool_base_v1"
CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_SYMBOLS = tuple(
    symbol
    for symbol in CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_SYMBOLS
    if symbol not in CN_ETF_RESEARCH_REALWORLD_POOL_V1_CROSS_BORDER_SYMBOLS
)
CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_ROLE_MAP = {
    symbol: role
    for symbol, role in CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_ROLE_MAP.items()
    if symbol not in CN_ETF_RESEARCH_REALWORLD_POOL_V1_CROSS_BORDER_SYMBOLS
}
CN_ETF_RESEARCH_DEFERRED_CANDIDATE_REASONS = {
    "511880.SH": "deferred_cash_equivalent_semantics",
    "511260.SH": "deferred_duration_layer_semantics",
    "513500.SH": "deferred_cross_border_qdii_currency_calendar",
    "513100.SH": "deferred_cross_border_qdii_currency_calendar",
}


_FIRST_WAVE_CATALOG: tuple[CnEtfCatalogEntry, ...] = (
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

_TEMPLATE_A_A1_CATALOG: tuple[CnEtfCatalogEntry, ...] = (
    CnEtfCatalogEntry(
        "159845.SZ",
        "sz159845",
        "中证1000ETF",
        "SZSE",
        TEMPLATE_A_A1_BATCH,
        "small_cap_equity_standard",
        list_date="20210331",
    ),
    CnEtfCatalogEntry(
        "510880.SH",
        "sh510880",
        "红利ETF",
        "SSE",
        TEMPLATE_A_A1_BATCH,
        "dividend_standard",
        list_date="20070118",
    ),
)

_REALWORLD_EXTENSION_CATALOG: tuple[CnEtfCatalogEntry, ...] = (
    CnEtfCatalogEntry("510180.SH", "sh510180", "SSE 180 ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "broad_large_overlap", list_date="20060518"),
    CnEtfCatalogEntry("159901.SZ", "sz159901", "SZSE 100 ETF", "SZSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "broad_large_growth", list_date="20060424"),
    CnEtfCatalogEntry("159949.SZ", "sz159949", "ChiNext 50 ETF", "SZSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "growth_equity_chinext50", list_date="20160722"),
    CnEtfCatalogEntry("511260.SH", "sh511260", "10Y Treasury ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "bond_duration", list_date="20170824"),
    CnEtfCatalogEntry("511880.SH", "sh511880", "Money ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "cash_equivalent", list_date="20130418"),
    CnEtfCatalogEntry("512000.SH", "sh512000", "Broker ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_broker", list_date="20160914"),
    CnEtfCatalogEntry("512800.SH", "sh512800", "Bank ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_bank", list_date="20170803"),
    CnEtfCatalogEntry("159928.SZ", "sz159928", "Consumer ETF", "SZSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_consumer", list_date="20130916"),
    CnEtfCatalogEntry("512690.SH", "sh512690", "Liquor ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_liquor", list_date="20190506"),
    CnEtfCatalogEntry("512010.SH", "sh512010", "Medicine ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_medicine", list_date="20131028"),
    CnEtfCatalogEntry("512170.SH", "sh512170", "Medical ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_medical", list_date="20190617"),
    CnEtfCatalogEntry("512480.SH", "sh512480", "Semiconductor ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_semiconductor", list_date="20190612"),
    CnEtfCatalogEntry("512760.SH", "sh512760", "Chip ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_chip", list_date="20190612"),
    CnEtfCatalogEntry("515030.SH", "sh515030", "New Energy Vehicle ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_new_energy_vehicle", list_date="20200304"),
    CnEtfCatalogEntry("515790.SH", "sh515790", "Photovoltaic ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_photovoltaic", list_date="20201218"),
    CnEtfCatalogEntry("515220.SH", "sh515220", "Coal ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_coal", list_date="20200302"),
    CnEtfCatalogEntry("512400.SH", "sh512400", "Nonferrous Metals ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "sector_nonferrous_metals", list_date="20170901"),
    CnEtfCatalogEntry("513100.SH", "sh513100", "Nasdaq ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "cross_border_nasdaq", list_date="20130515"),
    CnEtfCatalogEntry("513500.SH", "sh513500", "S&P 500 ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "cross_border_sp500", list_date="20140115"),
    CnEtfCatalogEntry("159920.SZ", "sz159920", "Hang Seng ETF", "SZSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "cross_border_hang_seng", list_date="20121022"),
    CnEtfCatalogEntry("513180.SH", "sh513180", "Hang Seng Tech ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "cross_border_hang_seng_tech", list_date="20210525"),
    CnEtfCatalogEntry("513050.SH", "sh513050", "China Internet ETF", "SSE", CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH, "cross_border_china_internet", list_date="20170118"),
)

_INDUSTRY_THEME_EXTENSION_CATALOG: tuple[CnEtfCatalogEntry, ...] = (
    CnEtfCatalogEntry("159819.SZ", "sz159819", "AI ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_ai", list_date="20200923"),
    CnEtfCatalogEntry("562500.SH", "sh562500", "Robotics ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_robotics", list_date="20211229"),
    CnEtfCatalogEntry("512720.SH", "sh512720", "Computer ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_computer", list_date="20190816"),
    CnEtfCatalogEntry("515230.SH", "sh515230", "Software ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_software", list_date="20210302"),
    CnEtfCatalogEntry("516510.SH", "sh516510", "Cloud Computing ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_cloud_computing", list_date="20210407"),
    CnEtfCatalogEntry("515880.SH", "sh515880", "Communication ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_communication", list_date="20190906"),
    CnEtfCatalogEntry("512980.SH", "sh512980", "Media ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_media", list_date="20180119"),
    CnEtfCatalogEntry("159869.SZ", "sz159869", "Game ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_game", list_date="20210305"),
    CnEtfCatalogEntry("512660.SH", "sh512660", "Military ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_military", list_date="20160808"),
    CnEtfCatalogEntry("159755.SZ", "sz159755", "Battery ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_battery", list_date="20210624"),
    CnEtfCatalogEntry("159611.SZ", "sz159611", "Power ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_power", list_date="20220107"),
    CnEtfCatalogEntry("512200.SH", "sh512200", "Real Estate ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_real_estate", list_date="20170925"),
    CnEtfCatalogEntry("516950.SH", "sh516950", "Infrastructure ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_infrastructure", list_date="20210514"),
    CnEtfCatalogEntry("516020.SH", "sh516020", "Chemical ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_chemical", list_date="20210308"),
    CnEtfCatalogEntry("515210.SH", "sh515210", "Steel ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_steel", list_date="20200302"),
    CnEtfCatalogEntry("516780.SH", "sh516780", "Rare Earth ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_rare_earth", list_date="20210308"),
    CnEtfCatalogEntry("159865.SZ", "sz159865", "Breeding ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_breeding", list_date="20210308"),
    CnEtfCatalogEntry("159930.SZ", "sz159930", "Energy ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_energy", list_date="20130916"),
    CnEtfCatalogEntry("159790.SZ", "sz159790", "Carbon Neutral ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_carbon_neutral", list_date="20210806"),
    CnEtfCatalogEntry("512580.SH", "sh512580", "Environmental Protection ETF", "SSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_environmental_protection", list_date="20170228"),
    CnEtfCatalogEntry("159996.SZ", "sz159996", "Home Appliance ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_home_appliance", list_date="20200316"),
    CnEtfCatalogEntry("159997.SZ", "sz159997", "Electronics ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_electronics", list_date="20200320"),
    CnEtfCatalogEntry("159732.SZ", "sz159732", "Consumer Electronics ETF", "SZSE", CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH, "sector_consumer_electronics", list_date="20210823"),
)

_STYLE_SMART_BETA_EXTENSION_CATALOG: tuple[CnEtfCatalogEntry, ...] = (
    CnEtfCatalogEntry("159905.SZ", "sz159905", "Dividend ETF ICBC", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_dividend", list_date="20101105"),
    CnEtfCatalogEntry("515080.SH", "sh515080", "CSI Dividend ETF China Merchants", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_dividend", list_date="20191227"),
    CnEtfCatalogEntry("515180.SH", "sh515180", "CSI Dividend ETF E Fund", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_dividend", list_date="20191220"),
    CnEtfCatalogEntry("515890.SH", "sh515890", "CSI Dividend ETF Bosera", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_dividend", list_date="20200420"),
    CnEtfCatalogEntry("515300.SH", "sh515300", "HS300 Dividend Low Vol ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_dividend_low_vol", list_date="20190919"),
    CnEtfCatalogEntry("512530.SH", "sh512530", "HS300 Dividend ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_dividend", list_date="20190923"),
    CnEtfCatalogEntry("515450.SH", "sh515450", "Dividend Low Vol 50 ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_dividend_low_vol", list_date="20200226"),
    CnEtfCatalogEntry("515100.SH", "sh515100", "Dividend Low Vol 100 ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_dividend_low_vol", list_date="20200703"),
    CnEtfCatalogEntry("512260.SH", "sh512260", "CSI500 Low Vol ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_low_vol", list_date="20190111"),
    CnEtfCatalogEntry("512390.SH", "sh512390", "China Low Vol ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_low_vol", list_date="20180713"),
    CnEtfCatalogEntry("159758.SZ", "sz159758", "Dividend Quality ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_dividend_quality", list_date="20211228"),
    CnEtfCatalogEntry("515910.SH", "sh515910", "Quality ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_quality", list_date="20210115"),
    CnEtfCatalogEntry("560500.SH", "sh560500", "CSI500 Quality Growth ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_quality_growth", list_date="20210927"),
    CnEtfCatalogEntry("159201.SZ", "sz159201", "Free Cashflow ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_cashflow", list_date="20250227"),
    CnEtfCatalogEntry("159399.SZ", "sz159399", "Cashflow ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_cashflow", list_date="20250227"),
    CnEtfCatalogEntry("563900.SH", "sh563900", "HS300 Free Cashflow ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_cashflow", list_date="20250507"),
    CnEtfCatalogEntry("510030.SH", "sh510030", "Value ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_value", list_date="20100122"),
    CnEtfCatalogEntry("159913.SZ", "sz159913", "SZ Value ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_value", list_date="20110922"),
    CnEtfCatalogEntry("512040.SH", "sh512040", "Value 100 ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_value", list_date="20181129"),
    CnEtfCatalogEntry("159966.SZ", "sz159966", "ChiNext Value ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_value", list_date="20190715"),
    CnEtfCatalogEntry("159617.SZ", "sz159617", "CSI500 Value ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_value", list_date="20220624"),
    CnEtfCatalogEntry("562320.SH", "sh562320", "HS300 Value ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_value", list_date="20230112"),
    CnEtfCatalogEntry("562530.SH", "sh562530", "CSI1000 Value ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_value", list_date="20220812"),
    CnEtfCatalogEntry("159338.SZ", "sz159338", "CSI A500 ETF Guotai", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_a500", list_date="20241015"),
    CnEtfCatalogEntry("512050.SH", "sh512050", "CSI A500 ETF ChinaAMC", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_a500", list_date="20241115"),
    CnEtfCatalogEntry("560570.SH", "sh560570", "A500 Dividend ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_a500_dividend", list_date="20250918"),
    CnEtfCatalogEntry("159296.SZ", "sz159296", "A500 Dividend Low Vol ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_a500_dividend_low_vol", list_date="20250904"),
    CnEtfCatalogEntry("510060.SH", "sh510060", "Central SOE ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_central_soe", list_date="20090803"),
    CnEtfCatalogEntry("510270.SH", "sh510270", "State-Owned ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_state_owned", list_date="20110818"),
    CnEtfCatalogEntry("512950.SH", "sh512950", "Central SOE Reform ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_central_soe", list_date="20190118"),
    CnEtfCatalogEntry("561580.SH", "sh561580", "Central SOE Dividend ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_central_soe_dividend", list_date="20230530"),
    CnEtfCatalogEntry("561990.SH", "sh561990", "HS300 Enhanced ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_enhanced", list_date="20211210"),
    CnEtfCatalogEntry("561300.SH", "sh561300", "HS300 Enhanced ETF Guotai", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_enhanced", list_date="20211210"),
    CnEtfCatalogEntry("561550.SH", "sh561550", "CSI500 Enhanced ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_enhanced", list_date="20211210"),
    CnEtfCatalogEntry("159610.SZ", "sz159610", "CSI500 Enhanced ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_enhanced", list_date="20220110"),
    CnEtfCatalogEntry("159680.SZ", "sz159680", "CSI1000 Enhanced ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_enhanced", list_date="20221130"),
    CnEtfCatalogEntry("159675.SZ", "sz159675", "ChiNext Enhanced ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_enhanced", list_date="20221202"),
    CnEtfCatalogEntry("588370.SH", "sh588370", "STAR50 Enhanced ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_enhanced", list_date="20221201"),
    CnEtfCatalogEntry("515590.SH", "sh515590", "CSI500 Equal Weight ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_equal_weight", list_date="20200122"),
    CnEtfCatalogEntry("159906.SZ", "sz159906", "SZ Growth ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_growth", list_date="20110113"),
    CnEtfCatalogEntry("159967.SZ", "sz159967", "ChiNext Growth ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_growth", list_date="20190715"),
    CnEtfCatalogEntry("159606.SZ", "sz159606", "CSI500 Growth ETF", "SZSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_growth", list_date="20211229"),
    CnEtfCatalogEntry("562520.SH", "sh562520", "CSI1000 Growth ETF", "SSE", CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH, "style_growth", list_date="20210929"),
)

_CATALOG: tuple[CnEtfCatalogEntry, ...] = (
    _FIRST_WAVE_CATALOG
    + _TEMPLATE_A_A1_CATALOG
    + _REALWORLD_EXTENSION_CATALOG
    + _INDUSTRY_THEME_EXTENSION_CATALOG
    + _STYLE_SMART_BETA_EXTENSION_CATALOG
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
    FIRST_WAVE_ALL: tuple(entry.ts_code for entry in _FIRST_WAVE_CATALOG),
    TEMPLATE_A_A1_CANDIDATES: tuple(entry.ts_code for entry in _TEMPLATE_A_A1_CATALOG),
    CN_ETF_RESEARCH_SHADOW_POOL_V1: CN_ETF_RESEARCH_SHADOW_POOL_V1_SYMBOLS,
    CN_ETF_RESEARCH_REALWORLD_POOL_V1: CN_ETF_RESEARCH_REALWORLD_POOL_V1_SYMBOLS,
    CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2: CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_SYMBOLS,
    CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2: CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_SYMBOLS,
    CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1: CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_SYMBOLS,
}


def list_first_wave_entries() -> tuple[CnEtfCatalogEntry, ...]:
    return _FIRST_WAVE_CATALOG


def list_template_a_a1_entries() -> tuple[CnEtfCatalogEntry, ...]:
    return _TEMPLATE_A_A1_CATALOG


def list_seeded_entries() -> tuple[CnEtfCatalogEntry, ...]:
    return _CATALOG


def supported_etf_ts_codes() -> tuple[str, ...]:
    return tuple(entry.ts_code for entry in _CATALOG)


def is_research_shadow_pool(name: str) -> bool:
    return str(name or "").strip() in {
        CN_ETF_RESEARCH_SHADOW_POOL_V1,
        CN_ETF_RESEARCH_REALWORLD_POOL_V1,
        CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2,
        CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2,
        CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1,
    }


def shadow_pool_role_map(name: str = CN_ETF_RESEARCH_SHADOW_POOL_V1) -> dict[str, str]:
    key = str(name or "").strip()
    if key == CN_ETF_RESEARCH_SHADOW_POOL_V1:
        return dict(CN_ETF_RESEARCH_SHADOW_POOL_V1_ROLE_MAP)
    if key == CN_ETF_RESEARCH_REALWORLD_POOL_V1:
        return dict(CN_ETF_RESEARCH_REALWORLD_POOL_V1_ROLE_MAP)
    if key == CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2:
        return dict(CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_ROLE_MAP)
    if key == CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2:
        return dict(CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_ROLE_MAP)
    if key == CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1:
        return dict(CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_ROLE_MAP)
    return {}


def deferred_etf_research_reason(value: Any) -> str | None:
    ts_code = normalize_cn_etf_ts_code(value)
    return CN_ETF_RESEARCH_DEFERRED_CANDIDATE_REASONS.get(ts_code)


def build_shadow_pool_promotion_gates(
    symbols: list[str] | tuple[str, ...],
    pool_name: str = CN_ETF_RESEARCH_SHADOW_POOL_V1,
) -> dict[str, dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}
    role_map = shadow_pool_role_map(pool_name)
    for raw_symbol in symbols:
        symbol = normalize_cn_etf_ts_code(raw_symbol)
        if symbol not in role_map:
            continue
        formal_eligible = False
        pool_key = str(pool_name or "").strip()
        if pool_key in {
            CN_ETF_RESEARCH_REALWORLD_POOL_V1,
            CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2,
            CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2,
            CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1,
        }:
            sector_theme_symbols = (
                CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_SECTOR_THEME_SYMBOLS
                if pool_key
                in {
                    CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2,
                    CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2,
                    CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1,
                }
                else CN_ETF_RESEARCH_REALWORLD_POOL_V1_SECTOR_THEME_SYMBOLS
            )
            short_history_symbols = (
                CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_SHORT_HISTORY_SYMBOLS
                if pool_key
                in {
                    CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2,
                    CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1,
                }
                else CN_ETF_RESEARCH_REALWORLD_POOL_V1_SHORT_HISTORY_SYMBOLS
            )
            if symbol in CN_ETF_RESEARCH_REALWORLD_POOL_V1_FORMAL_ANCHOR_SYMBOLS:
                formal_eligible = True
                status = "already_formal_v1_member"
                reason = "formal_anchor"
            elif symbol in CN_ETF_RESEARCH_REALWORLD_POOL_V1_CASH_SEMANTICS_SYMBOLS:
                status = "blocked"
                reason = "cash_equivalent_semantics"
            elif symbol in CN_ETF_RESEARCH_REALWORLD_POOL_V1_DURATION_LAYER_SYMBOLS:
                status = "blocked"
                reason = "duration_layer_semantics"
            elif symbol in CN_ETF_RESEARCH_REALWORLD_POOL_V1_CROSS_BORDER_SYMBOLS:
                status = "blocked"
                reason = "cross_border_qdii_currency_calendar"
            elif symbol in sector_theme_symbols:
                status = "blocked"
                reason = "sector_theme_semantics"
            elif symbol in short_history_symbols:
                status = "blocked"
                reason = "short_history"
            else:
                status = "pending_shadow_validation"
                reason = "not_evaluated"
        elif symbol in CN_ETF_RESEARCH_SHADOW_POOL_V1_SHORT_HISTORY_SYMBOLS:
            status = "blocked"
            reason = "short_history"
        else:
            status = "pending_shadow_validation"
            reason = "not_evaluated"
        gates[symbol] = {
            "formal_eligible": formal_eligible,
            "promotion_gate_status": status,
            "reject_reason": reason,
            "shadow_role": role_map[symbol],
        }
    return gates


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
    if key == TEMPLATE_A_A1_CANDIDATES:
        return TEMPLATE_A_A1_BATCH
    if key == CN_ETF_RESEARCH_SHADOW_POOL_V1:
        return CN_ETF_RESEARCH_SHADOW_POOL_V1
    if key == CN_ETF_RESEARCH_REALWORLD_POOL_V1:
        return CN_ETF_RESEARCH_REALWORLD_POOL_V1
    if key == CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2:
        return CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2
    if key == CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2:
        return CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2
    if key == CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1:
        return CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1
    if len(symbols) == 1:
        return SINGLE_ASSET_TEMPLATE
    return FIRST_WAVE_BATCH


__all__ = [
    "CN_ETF_RESEARCH_DEFERRED_CANDIDATE_REASONS",
    "CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1",
    "CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_BATCH",
    "CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_ROLE_MAP",
    "CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_SYMBOLS",
    "CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2",
    "CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_BATCH",
    "CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_NEW_SYMBOLS",
    "CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_ROLE_MAP",
    "CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_SYMBOLS",
    "CN_ETF_RESEARCH_REALWORLD_POOL_V1",
    "CN_ETF_RESEARCH_REALWORLD_POOL_V1_BATCH",
    "CN_ETF_RESEARCH_REALWORLD_POOL_V1_ROLE_MAP",
    "CN_ETF_RESEARCH_REALWORLD_POOL_V1_SYMBOLS",
    "CN_ETF_RESEARCH_SHADOW_POOL_V1",
    "CN_ETF_RESEARCH_SHADOW_POOL_V1_BATCH",
    "CN_ETF_RESEARCH_SHADOW_POOL_V1_ROLE_MAP",
    "CN_ETF_RESEARCH_SHADOW_POOL_V1_SHORT_HISTORY_SYMBOLS",
    "CN_ETF_RESEARCH_SHADOW_POOL_V1_SYMBOLS",
    "CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2",
    "CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_BATCH",
    "CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_NEW_SYMBOLS",
    "CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_ROLE_MAP",
    "CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_SHORT_HISTORY_SYMBOLS",
    "CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_SYMBOLS",
    "CnEtfCatalogEntry",
    "FIRST_WAVE_ALL",
    "FIRST_WAVE_BATCH",
    "FIRST_WAVE_CORE",
    "SINGLE_ASSET_TEMPLATE",
    "TEMPLATE_A_A1_BATCH",
    "TEMPLATE_A_A1_CANDIDATES",
    "build_shadow_pool_promotion_gates",
    "deferred_etf_research_reason",
    "expand_etf_preset",
    "get_catalog_entry",
    "is_research_shadow_pool",
    "list_first_wave_entries",
    "list_seeded_entries",
    "list_template_a_a1_entries",
    "normalize_cn_etf_symbol",
    "normalize_cn_etf_ts_code",
    "preset_batch_id",
    "require_catalog_entry",
    "shadow_pool_role_map",
    "supported_etf_ts_codes",
]
