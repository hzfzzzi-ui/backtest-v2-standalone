from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.core.universe.hs300_csi500 import UniverseLoadError
from backend.core.universe.universe_resolver import resolve_universe_by_mode


class _FakeMarketDataAccess:
    def load_active_cn_a_symbols(self, *, as_of_date, universe_limit=None):
        symbols = ["sh600000", "sz000001", "sh600519"]
        if universe_limit is not None:
            symbols = symbols[:universe_limit]
        return symbols, {
            "symbols_source": "market_data_access:pit_security_master+canonical_market",
            "constituents_load_status": "OK",
            "raw_count": 3,
            "canonical_objects": ["pit_security_master", "pams_ohlcv_daily_v2"],
        }


class _FakePitMarketDataAccess:
    def load_pit_constituents_snapshot(self, *, index_code, as_of_date):
        rows = {
            "000906.SH": ["sh600000", "sz000001"],
            "000852.SH": ["sz000001", "sz300001"],
        }[index_code]
        return SimpleNamespace(
            frame=pd.DataFrame({"symbol": rows}),
            audit=SimpleNamespace(canonical_objects=["pit_index_constituents"]),
        )


def test_resolve_universe_by_mode_rejects_unsupported_asset_scope() -> None:
    with pytest.raises(UniverseLoadError) as exc_info:
        resolve_universe_by_mode(
            mode="CUSTOM",
            as_of=date(2026, 3, 20),
            db=SimpleNamespace(),
            runtime=SimpleNamespace(),
            asset_scope="us_equity",
            symbols=["AAPL"],
        )

    exc = exc_info.value
    assert exc.status == "ERROR:UNSUPPORTED_ASSET_SCOPE"
    assert exc.meta["asset_scope"] == "us_equity"
    assert exc.meta["asset_profile_id"] == "us_equity_prepare_mainline"


def test_resolve_universe_by_mode_supports_cn_etf_custom_catalog_symbols() -> None:
    symbols, meta = resolve_universe_by_mode(
        mode="CUSTOM",
        as_of=date(2026, 3, 20),
        db=SimpleNamespace(),
        runtime=SimpleNamespace(),
        asset_scope="cn_etf",
        symbols=["512100.SH", "cn_etf_first_wave_core"],
    )

    assert "sh512100" in symbols
    assert meta["asset_scope"] == "cn_etf"
    assert meta["symbols_source"] == "cn_etf_catalog_whitelist"
    assert meta["catalog_table"] == "pit_cn_etf_master"
    assert "512100.SH" in meta["etf_symbols"]
    assert meta["preset_id"] == "cn_etf_first_wave_core"
    assert meta["etf_batch"] == "cn_etf_first_wave_core"
    assert meta["formal_scope_symbols"]
    assert meta["shadow_symbols"] == []
    assert meta["deferred_symbols"] == []


def test_resolve_universe_by_mode_rejects_non_custom_mode_for_cn_etf() -> None:
    with pytest.raises(UniverseLoadError) as exc_info:
        resolve_universe_by_mode(
            mode="ALL_A",
            as_of=date(2026, 3, 20),
            db=SimpleNamespace(),
            runtime=SimpleNamespace(),
            asset_scope="cn_etf",
            symbols=["512100.SH"],
        )

    exc = exc_info.value
    assert exc.status == "ERROR:UNSUPPORTED_MODE"
    assert exc.meta["asset_scope"] == "cn_etf"


def test_resolve_universe_by_mode_emits_cn_etf_shadow_pool_metadata() -> None:
    symbols, meta = resolve_universe_by_mode(
        mode="CUSTOM",
        as_of=date(2026, 5, 8),
        db=SimpleNamespace(),
        runtime=SimpleNamespace(),
        asset_scope="cn_etf",
        symbols=["cn_etf_research_shadow_pool_v1"],
    )

    assert symbols == ["sz159845", "sz159915", "sh510880", "sh512890", "sh518880", "sh588000"]
    assert meta["pool_version"] == "cn_etf_research_shadow_pool_v1"
    assert meta["research_only"] is True
    assert meta["formal_scope_symbols"] == []
    assert meta["shadow_symbols"] == ["159845.SZ", "159915.SZ", "510880.SH", "512890.SH", "518880.SH", "588000.SH"]
    assert meta["shadow_role_map"]["510880.SH"] == "shadow_value_dividend"
    assert meta["promotion_gate_by_symbol"]["588000.SH"]["reject_reason"] == "short_history"
    assert meta["formal_eligibility_by_symbol"]["159845.SZ"] is False
    assert meta["research_classification_by_symbol"]["510880.SH"] == "shadow"


def test_resolve_universe_by_mode_emits_cn_etf_realworld_pool_metadata() -> None:
    symbols, meta = resolve_universe_by_mode(
        mode="CUSTOM",
        as_of=date(2026, 5, 8),
        db=SimpleNamespace(),
        runtime=SimpleNamespace(),
        asset_scope="cn_etf",
        symbols=["cn_etf_research_realworld_pool_v1"],
    )

    assert len(symbols) == 33
    assert {"sh512480", "sh513100", "sz159920", "sh511880"}.issubset(set(symbols))
    assert meta["pool_version"] == "cn_etf_research_realworld_pool_v1"
    assert meta["research_only"] is True
    assert "510300.SH" in meta["formal_scope_symbols"]
    assert "513100.SH" in meta["shadow_symbols"]
    assert meta["shadow_role_map"]["512480.SH"] == "realworld_sector_semiconductor"
    assert meta["promotion_gate_by_symbol"]["511880.SH"]["reject_reason"] == "cash_equivalent_semantics"
    assert meta["promotion_gate_by_symbol"]["513100.SH"]["reject_reason"] == "cross_border_qdii_currency_calendar"
    assert meta["promotion_gate_by_symbol"]["510300.SH"]["promotion_gate_status"] == "already_formal_v1_member"
    assert meta["formal_eligibility_by_symbol"]["510300.SH"] is True
    assert meta["research_classification_by_symbol"]["512480.SH"] == "shadow"


def test_resolve_universe_by_mode_emits_cn_etf_industry_theme_pool_metadata() -> None:
    symbols, meta = resolve_universe_by_mode(
        mode="CUSTOM",
        as_of=date(2026, 5, 8),
        db=SimpleNamespace(),
        runtime=SimpleNamespace(),
        asset_scope="cn_etf",
        symbols=["cn_etf_research_industry_theme_pool_v2"],
    )

    assert len(symbols) == 56
    assert {"sz159819", "sh562500", "sh515880", "sh512660", "sz159755"}.issubset(set(symbols))
    assert meta["pool_version"] == "cn_etf_research_industry_theme_pool_v2"
    assert meta["research_only"] is True
    assert meta["shadow_role_map"]["159819.SZ"] == "industry_v2_ai"
    assert meta["shadow_role_map"]["562500.SH"] == "industry_v2_robotics"
    assert meta["promotion_gate_by_symbol"]["159819.SZ"]["reject_reason"] == "sector_theme_semantics"
    assert meta["research_classification_by_symbol"]["159819.SZ"] == "shadow"


def test_resolve_universe_by_mode_emits_cn_etf_style_smart_beta_pool_metadata() -> None:
    symbols, meta = resolve_universe_by_mode(
        mode="CUSTOM",
        as_of=date(2026, 5, 8),
        db=SimpleNamespace(),
        runtime=SimpleNamespace(),
        asset_scope="cn_etf",
        symbols=["cn_etf_research_style_smart_beta_pool_v2"],
    )

    assert len(symbols) == 99
    assert {"sz159905", "sh515300", "sz159201", "sh512050", "sh561990"}.issubset(set(symbols))
    assert meta["pool_version"] == "cn_etf_research_style_smart_beta_pool_v2"
    assert meta["research_only"] is True
    assert meta["shadow_role_map"]["159905.SZ"] == "style_v2_dividend_alt"
    assert meta["shadow_role_map"]["159201.SZ"] == "style_v2_free_cashflow_short_history"
    assert meta["promotion_gate_by_symbol"]["159201.SZ"]["reject_reason"] == "short_history"
    assert meta["promotion_gate_by_symbol"]["159819.SZ"]["reject_reason"] == "sector_theme_semantics"
    assert meta["research_classification_by_symbol"]["159905.SZ"] == "shadow"


def test_resolve_universe_by_mode_rejects_deferred_cn_etf_candidate() -> None:
    with pytest.raises(UniverseLoadError) as exc_info:
        resolve_universe_by_mode(
            mode="CUSTOM",
            as_of=date(2026, 5, 8),
            db=SimpleNamespace(),
            runtime=SimpleNamespace(),
            asset_scope="cn_etf",
            symbols=["511880.SH"],
        )

    exc = exc_info.value
    assert exc.status == "ERROR:DEFERRED_CN_ETF_SYMBOL"
    assert exc.meta["deferred_symbols"] == ["511880.SH"]
    assert exc.meta["deferred_reason_codes"]["511880.SH"] == ["deferred_cash_equivalent_semantics"]


def test_resolve_universe_by_mode_all_a_uses_market_data_access_when_provided() -> None:
    symbols, meta = resolve_universe_by_mode(
        mode="ALL_A",
        as_of=date(2026, 3, 20),
        db=SimpleNamespace(),
        runtime=SimpleNamespace(),
        asset_scope="cn_a_equity",
        universe_limit=2,
        market_data_access=_FakeMarketDataAccess(),
    )

    assert symbols == ["sh600000", "sz000001"]
    assert meta["asset_scope"] == "cn_a_equity"
    assert meta["universe_mode"] == "ALL_A"
    assert meta["raw_count"] == 3
    assert meta["symbols_source"] == "market_data_access:pit_security_master+canonical_market"
    assert meta["canonical_objects"] == ["pit_security_master", "pams_ohlcv_daily_v2"]


def test_resolve_universe_by_mode_supports_hs300_zz500_csi1000_pit_union() -> None:
    symbols, meta = resolve_universe_by_mode(
        mode="HS300_ZZ500_CSI1000",
        as_of=date(2026, 3, 20),
        db=SimpleNamespace(),
        runtime=SimpleNamespace(),
        asset_scope="cn_a_equity",
        market_data_access=_FakePitMarketDataAccess(),
    )

    assert symbols == ["sh600000", "sz000001", "sz300001"]
    assert meta["universe_mode"] == "HS300_ZZ500_CSI1000"
    assert meta["index_codes"] == ["000906.SH", "000852.SH"]
    assert meta["per_index_raw_counts"] == {"000906.SH": 2, "000852.SH": 2}
    assert meta["union_symbol_count"] == 3
