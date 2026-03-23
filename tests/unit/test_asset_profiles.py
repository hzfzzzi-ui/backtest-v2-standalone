from __future__ import annotations

import pytest

from backend.core.config.asset_profiles import (
    UnsupportedAssetScopeError,
    build_asset_context,
    canonical_asset_scope,
)


def test_canonical_asset_scope_maps_current_aliases_to_cn_a_equity() -> None:
    for value in ("cn_a_equity", "cn_a", "cn_a_stock", "a_share", "a_shares"):
        assert canonical_asset_scope(value) == "cn_a_equity"


def test_canonical_asset_scope_maps_etf_aliases_to_cn_etf() -> None:
    for value in ("cn_etf", "a_share_etf", "a_shares_etf", "cn_fund_etf"):
        assert canonical_asset_scope(value) == "cn_etf"


def test_canonical_asset_scope_maps_us_aliases_to_us_equity() -> None:
    for value in ("us_equity", "us_stock", "us_stocks", "us_equities"):
        assert canonical_asset_scope(value) == "us_equity"


def test_canonical_asset_scope_rejects_unknown_scope() -> None:
    with pytest.raises(UnsupportedAssetScopeError):
        canonical_asset_scope("us_etf")


def test_build_asset_context_returns_current_mainline_profiles() -> None:
    context = build_asset_context("cn_a_equity")
    assert context["asset_scope"] == "cn_a_equity"
    assert context["asset_profile_id"] == "cn_a_equity_mainline"
    assert context["market_profile_id"] == "cn_a_mainland_equity_market"
    assert context["execution_profile_id"] == "cn_a_tplus1_next_open"


def test_build_asset_context_returns_us_prepare_profiles() -> None:
    context = build_asset_context("us_equity")
    assert context["asset_scope"] == "us_equity"
    assert context["asset_profile_id"] == "us_equity_prepare_mainline"
    assert context["market_profile_id"] == "us_equity_primary_market"
    assert context["execution_profile_id"] == "us_equity_tplus1_next_open"
    assert context["asset_family"] == "equity"
    assert context["asset_class"] == "equity"


def test_build_asset_context_returns_cn_etf_profiles() -> None:
    context = build_asset_context("cn_etf")
    assert context["asset_scope"] == "cn_etf"
    assert context["asset_profile_id"] == "cn_etf_first_wave_research"
    assert context["market_profile_id"] == "cn_etf_mainland_fund_market"
    assert context["execution_profile_id"] == "cn_etf_tplus1_next_open"
    assert context["asset_family"] == "fund"
    assert context["asset_class"] == "etf"
