from __future__ import annotations

import pytest

from backend.core.data.price_limits import (
    UnsupportedMarketProfileError,
    compute_limit_prices,
)
from backend.core.engine_vector.audit_collector import AuditCollector


def test_price_limits_reject_non_cn_asset_scope() -> None:
    with pytest.raises(UnsupportedMarketProfileError, match="us_equity"):
        compute_limit_prices(10.0, "AAPL", is_st=False, asset_scope="us_equity")


def test_audit_collector_rejects_non_cn_market_key() -> None:
    with pytest.raises(ValueError, match="US_EQUITY"):
        AuditCollector(initial_cash=1_000_000, max_positions=10, market_key="US_EQUITY")


def test_price_limits_support_cn_etf_tick_and_limit_pct() -> None:
    limit_up, limit_down = compute_limit_prices(1.0, "sh512100", is_st=False, asset_scope="cn_etf")

    assert limit_up == 1.1
    assert limit_down == 0.9


def test_audit_collector_accepts_cn_etf_market_key() -> None:
    collector = AuditCollector(initial_cash=1_000_000, max_positions=10, market_key="CN_ETF")
    assert collector._market_key == "CN_ETF"
