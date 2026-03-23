from __future__ import annotations

from backend.api.backtest_v2 import impl as backtest_impl


def test_market_data_sync_status_endpoint_returns_thin_status_payload(test_client, monkeypatch) -> None:
    monkeypatch.setattr(
        backtest_impl,
        "get_market_data_sync_status",
        lambda asset_scope=None: {
            "sync_key": "cn_a_ohlcv_daily",
            "asset_scope": "cn_a_equity",
            "status": "fresh",
            "latest_success_trade_date": "2026-03-14",
            "latest_display_trade_date": "2026-03-14",
            "target_trade_date": "2026-03-14",
            "lag_days": 0,
            "message": "已同步至 2026-03-14",
        },
    )

    response = test_client.get("/api/backtest_v2/market_data/sync_status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "fresh"
    assert payload["latest_success_trade_date"] == "2026-03-14"
    assert payload["target_trade_date"] == "2026-03-14"


def test_market_data_sync_status_endpoint_passes_asset_scope_query(test_client, monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    def _fake_status(asset_scope=None):
        captured["asset_scope"] = asset_scope
        return {
            "sync_key": "us_equity_daily",
            "asset_scope": "us_equity",
            "status": "unsupported",
            "latest_success_trade_date": None,
            "latest_display_trade_date": None,
            "target_trade_date": None,
            "lag_days": None,
            "message": "market data sync adapter unavailable for asset_scope=us_equity",
        }

    monkeypatch.setattr(backtest_impl, "get_market_data_sync_status", _fake_status)

    response = test_client.get("/api/backtest_v2/market_data/sync_status?asset_scope=us_equity")

    assert response.status_code == 200
    payload = response.json()
    assert captured["asset_scope"] == "us_equity"
    assert payload["status"] == "unsupported"
    assert payload["asset_scope"] == "us_equity"


def test_market_data_sync_status_endpoint_supports_cn_etf_query(test_client, monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    def _fake_status(asset_scope=None):
        captured["asset_scope"] = asset_scope
        return {
            "sync_key": "cn_etf_daily",
            "asset_scope": "cn_etf",
            "status": "fresh",
            "latest_success_trade_date": "2026-03-20",
            "latest_display_trade_date": "2026-03-20",
            "target_trade_date": "2026-03-20",
            "lag_days": 0,
            "coverage_symbol_count": 9,
            "message": "已同步至 2026-03-20",
        }

    monkeypatch.setattr(backtest_impl, "get_market_data_sync_status", _fake_status)

    response = test_client.get("/api/backtest_v2/market_data/sync_status?asset_scope=cn_etf")

    assert response.status_code == 200
    payload = response.json()
    assert captured["asset_scope"] == "cn_etf"
    assert payload["status"] == "fresh"
    assert payload["asset_scope"] == "cn_etf"
    assert payload["coverage_symbol_count"] == 9
