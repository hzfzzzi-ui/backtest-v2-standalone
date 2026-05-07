
"""Public data access surface for backend.core.data.

Prefer `MarketDataAccess` for cross-module market reads. Legacy provider
modules remain available as compatibility/internal implementations.
"""

from .market_data_access import (
    CALENDAR_VERSION,
    DIRECT_CANONICAL_CACHE_VERSION,
    MarketDataAccess,
    MarketDataAudit,
    MarketDataFrameResult,
    MarketDataRequest,
    build_market_data_access,
    load_market_data_access,
)

__all__ = [
    "CALENDAR_VERSION",
    "DIRECT_CANONICAL_CACHE_VERSION",
    "MarketDataAccess",
    "MarketDataAudit",
    "MarketDataFrameResult",
    "MarketDataRequest",
    "build_market_data_access",
    "load_market_data_access",
]
