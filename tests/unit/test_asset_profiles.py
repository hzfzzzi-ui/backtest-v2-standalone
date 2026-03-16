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


def test_canonical_asset_scope_rejects_unknown_scope() -> None:
    with pytest.raises(UnsupportedAssetScopeError):
        canonical_asset_scope("us_etf")


def test_build_asset_context_returns_current_mainline_profiles() -> None:
    context = build_asset_context("cn_a_equity")
    assert context["asset_scope"] == "cn_a_equity"
    assert context["asset_profile_id"] == "cn_a_equity_mainline"
    assert context["market_profile_id"] == "cn_a_mainland_equity_market"
    assert context["execution_profile_id"] == "cn_a_tplus1_next_open"
