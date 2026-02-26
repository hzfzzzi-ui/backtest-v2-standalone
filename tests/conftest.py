from __future__ import annotations

from unittest.mock import MagicMock
from typing import Any

import pandas as pd
import pytest
from starlette.testclient import TestClient

from backend.main import app


@pytest.fixture()
def test_client():
    """FastAPI TestClient wired to the application."""
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def mock_db_provider():
    """Mock DataProvider that returns configurable DataFrames without a real database."""
    provider = MagicMock()
    provider.query_audit = []

    _responses: dict[str, pd.DataFrame] = {}

    def _set_response(method: str, df: pd.DataFrame) -> None:
        _responses[method] = df

    def _make_side_effect(method_name: str):
        def side_effect(*args: Any, **kwargs: Any) -> pd.DataFrame:
            return _responses.get(method_name, pd.DataFrame())
        return side_effect

    provider.set_response = _set_response
    provider.load_ohlcv_daily.side_effect = _make_side_effect("load_ohlcv_daily")
    provider.load_benchmark_daily.side_effect = _make_side_effect("load_benchmark_daily")
    provider.load_trading_calendar_cn.side_effect = lambda *a, **kw: pd.DatetimeIndex([])
    provider.get_previous_trading_day_cn.side_effect = lambda *a, **kw: None
    provider.load_instrument_rules.side_effect = lambda *a, **kw: pd.DataFrame()

    return provider
