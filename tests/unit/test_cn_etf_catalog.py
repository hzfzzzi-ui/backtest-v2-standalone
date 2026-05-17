from __future__ import annotations

from backend.core.data.cn_etf_catalog import (
    CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1,
    CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_ROLE_MAP,
    CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_SYMBOLS,
    CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2,
    CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_NEW_SYMBOLS,
    CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_ROLE_MAP,
    CN_ETF_RESEARCH_REALWORLD_POOL_V1,
    CN_ETF_RESEARCH_REALWORLD_POOL_V1_ROLE_MAP,
    CN_ETF_RESEARCH_REALWORLD_POOL_V1_SYMBOLS,
    CN_ETF_RESEARCH_SHADOW_POOL_V1,
    CN_ETF_RESEARCH_SHADOW_POOL_V1_ROLE_MAP,
    CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2,
    CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_NEW_SYMBOLS,
    CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_ROLE_MAP,
    build_shadow_pool_promotion_gates,
    deferred_etf_research_reason,
    FIRST_WAVE_ALL,
    TEMPLATE_A_A1_CANDIDATES,
    expand_etf_preset,
    get_catalog_entry,
    shadow_pool_role_map,
    supported_etf_ts_codes,
)


def test_template_a_a1_symbols_are_supported_but_not_in_first_wave_all() -> None:
    supported = set(supported_etf_ts_codes())

    assert "159845.SZ" in supported
    assert "510880.SH" in supported

    first_wave_all = set(expand_etf_preset(FIRST_WAVE_ALL))
    assert "159845.SZ" not in first_wave_all
    assert "510880.SH" not in first_wave_all

    a1_candidates = set(expand_etf_preset(TEMPLATE_A_A1_CANDIDATES))
    assert a1_candidates == {"159845.SZ", "510880.SH"}


def test_new_standard_etf_entries_are_resolvable() -> None:
    csi1000_entry = get_catalog_entry("159845.SZ")
    dividend_entry = get_catalog_entry("510880.SH")

    assert csi1000_entry is not None
    assert csi1000_entry.symbol == "sz159845"
    assert csi1000_entry.batch_id == "template_a_a1"

    assert dividend_entry is not None
    assert dividend_entry.symbol == "sh510880"
    assert dividend_entry.batch_id == "template_a_a1"


def test_research_shadow_pool_v1_expands_expected_symbols_and_roles() -> None:
    symbols = expand_etf_preset(CN_ETF_RESEARCH_SHADOW_POOL_V1)

    assert symbols == [
        "510880.SH",
        "512890.SH",
        "518880.SH",
        "159915.SZ",
        "588000.SH",
        "159845.SZ",
    ]
    assert shadow_pool_role_map(CN_ETF_RESEARCH_SHADOW_POOL_V1) == CN_ETF_RESEARCH_SHADOW_POOL_V1_ROLE_MAP
    assert shadow_pool_role_map("cn_etf_first_wave_core") == {}


def test_research_realworld_pool_v1_expands_expected_symbols_and_roles() -> None:
    symbols = expand_etf_preset(CN_ETF_RESEARCH_REALWORLD_POOL_V1)

    assert symbols == list(CN_ETF_RESEARCH_REALWORLD_POOL_V1_SYMBOLS)
    assert len(symbols) == 33
    assert {"511880.SH", "512480.SH", "513100.SH", "159920.SZ"}.issubset(set(symbols))
    assert shadow_pool_role_map(CN_ETF_RESEARCH_REALWORLD_POOL_V1) == CN_ETF_RESEARCH_REALWORLD_POOL_V1_ROLE_MAP
    assert get_catalog_entry("512480.SH").symbol == "sh512480"
    assert get_catalog_entry("513050.SH").exposure_bucket == "cross_border_china_internet"


def test_research_industry_theme_pool_v2_extends_realworld_pool() -> None:
    symbols = expand_etf_preset(CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2)

    assert len(symbols) == 56
    assert {"159819.SZ", "562500.SH", "515880.SH", "512660.SH", "159755.SZ"}.issubset(set(symbols))
    assert set(CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_NEW_SYMBOLS).issubset(set(symbols))
    assert shadow_pool_role_map(CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2) == CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2_ROLE_MAP
    assert get_catalog_entry("159819.SZ").exposure_bucket == "sector_ai"
    assert get_catalog_entry("516780.SH").symbol == "sh516780"


def test_research_style_smart_beta_pool_v2_extends_industry_theme_pool() -> None:
    symbols = expand_etf_preset(CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2)

    assert len(symbols) == 99
    assert {
        "159905.SZ",
        "515300.SH",
        "159201.SZ",
        "512050.SH",
        "561990.SH",
        "159606.SZ",
    }.issubset(set(symbols))
    assert set(CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_NEW_SYMBOLS).issubset(set(symbols))
    assert shadow_pool_role_map(CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2) == CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2_ROLE_MAP
    assert get_catalog_entry("159201.SZ").exposure_bucket == "style_cashflow"
    assert get_catalog_entry("561990.SH").symbol == "sh561990"


def test_research_domestic_pool_base_v1_excludes_cross_border_only() -> None:
    symbols = expand_etf_preset(CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1)
    style_symbols = set(expand_etf_preset(CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2))
    cross_border = {"513100.SH", "513500.SH", "159920.SZ", "513180.SH", "513050.SH"}

    assert symbols == list(CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_SYMBOLS)
    assert len(symbols) == 94
    assert set(symbols) == style_symbols - cross_border
    assert cross_border.isdisjoint(symbols)
    assert {"511880.SH", "511260.SH", "518880.SH", "159201.SZ"}.issubset(set(symbols))
    assert shadow_pool_role_map(CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1) == CN_ETF_RESEARCH_DOMESTIC_POOL_BASE_V1_ROLE_MAP


def test_shadow_pool_promotion_gates_mark_short_history_candidates() -> None:
    gates = build_shadow_pool_promotion_gates(["510880.SH", "588000.SH", "159845.SZ"])

    assert gates["510880.SH"]["promotion_gate_status"] == "pending_shadow_validation"
    assert gates["510880.SH"]["reject_reason"] == "not_evaluated"
    assert gates["588000.SH"]["promotion_gate_status"] == "blocked"
    assert gates["588000.SH"]["reject_reason"] == "short_history"
    assert gates["159845.SZ"]["reject_reason"] == "short_history"


def test_realworld_pool_promotion_gates_mark_semantic_blockers() -> None:
    gates = build_shadow_pool_promotion_gates(
        ["510300.SH", "511880.SH", "511260.SH", "513100.SH", "512480.SH", "588000.SH", "510880.SH"],
        pool_name=CN_ETF_RESEARCH_REALWORLD_POOL_V1,
    )

    assert gates["510300.SH"]["promotion_gate_status"] == "already_formal_v1_member"
    assert gates["510300.SH"]["formal_eligible"] is True
    assert gates["511880.SH"]["reject_reason"] == "cash_equivalent_semantics"
    assert gates["511260.SH"]["reject_reason"] == "duration_layer_semantics"
    assert gates["513100.SH"]["reject_reason"] == "cross_border_qdii_currency_calendar"
    assert gates["512480.SH"]["reject_reason"] == "sector_theme_semantics"
    assert gates["588000.SH"]["reject_reason"] == "short_history"
    assert gates["510880.SH"]["promotion_gate_status"] == "pending_shadow_validation"


def test_industry_theme_pool_promotion_gates_block_added_theme_symbols() -> None:
    gates = build_shadow_pool_promotion_gates(
        ["159819.SZ", "562500.SH", "515880.SH", "512660.SH", "159755.SZ"],
        pool_name=CN_ETF_RESEARCH_INDUSTRY_THEME_POOL_V2,
    )

    assert gates["159819.SZ"]["reject_reason"] == "sector_theme_semantics"
    assert gates["562500.SH"]["reject_reason"] == "sector_theme_semantics"
    assert gates["515880.SH"]["reject_reason"] == "sector_theme_semantics"
    assert gates["512660.SH"]["reject_reason"] == "sector_theme_semantics"
    assert gates["159755.SZ"]["reject_reason"] == "sector_theme_semantics"


def test_style_smart_beta_pool_promotion_gates_mark_style_candidates() -> None:
    gates = build_shadow_pool_promotion_gates(
        ["159905.SZ", "510030.SH", "159201.SZ", "512050.SH", "159819.SZ"],
        pool_name=CN_ETF_RESEARCH_STYLE_SMART_BETA_POOL_V2,
    )

    assert gates["159905.SZ"]["promotion_gate_status"] == "pending_shadow_validation"
    assert gates["510030.SH"]["promotion_gate_status"] == "pending_shadow_validation"
    assert gates["159201.SZ"]["reject_reason"] == "short_history"
    assert gates["512050.SH"]["reject_reason"] == "short_history"
    assert gates["159819.SZ"]["reject_reason"] == "sector_theme_semantics"


def test_deferred_etf_candidates_have_explicit_reasons() -> None:
    assert deferred_etf_research_reason("511880.SH") == "deferred_cash_equivalent_semantics"
    assert deferred_etf_research_reason("511260.SH") == "deferred_duration_layer_semantics"
    assert deferred_etf_research_reason("513500.SH") == "deferred_cross_border_qdii_currency_calendar"
