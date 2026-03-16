from __future__ import annotations

from backend.api.backtest_v2 import impl as backtest_impl


def test_market_data_sync_status_endpoint_returns_thin_status_payload(test_client, monkeypatch) -> None:
    monkeypatch.setattr(
        backtest_impl,
        "get_market_data_sync_status",
        lambda: {
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
