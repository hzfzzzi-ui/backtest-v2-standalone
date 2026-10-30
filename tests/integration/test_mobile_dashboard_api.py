from __future__ import annotations

import json

from backend.api.mobile import impl as mobile_mod
from backend.core.services.mobile_execution_service import (
    claim_approval_ticket,
    record_execution_update,
)


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_outputs(tmp_path) -> str:
    results_root = tmp_path / "outputs"
    exp_id = "exp_mobile_api_001"
    exp_dir = results_root / "experiments" / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        results_root / "experiments" / "index.json",
        [
            {
                "exp_id": exp_id,
                "label": "鎵嬫満 API 鏍锋湰",
                "created_at": "2026-03-12T12:00:00",
                "status": "OK",
                "cagr": 0.16,
                "sharpe": 0.98,
                "max_drawdown": -0.19,
                "total_return": 0.76,
                "trades": 35,
                "universe_mode": "HS300_ZZ500",
            }
        ],
    )
    _write_json(exp_dir / "manifest.json", {"exp_id": exp_id, "artifacts": {"stock_names": "stock_names.json"}})
    _write_json(exp_dir / "perf.json", {"cagr": 0.16, "sharpe": 0.98, "max_drawdown": -0.19, "total_return": 0.76, "trades": 35})
    _write_json(exp_dir / "run_meta.json", {"data": {"universe_mode": "HS300_ZZ500"}})
    _write_json(
        exp_dir / "resolved_config.json",
        {"config_json": {"mode": "experiment", "strategy_pack": "BREAKOUT_TREND", "universe_mode": "HS300_ZZ500"}},
    )
    _write_json(exp_dir / "stock_names.json", {"sh600000": "娴﹀彂閾惰", "sh600519": "璐靛窞鑼呭彴"})
    (exp_dir / "portfolio_daily.csv").write_text(
        "\n".join(
            [
                "date,nav,cash,market_state,trade_mode,benchmark_regime_on",
                "2026-03-11,1400000.0,330000.0,WARM,TREND_MAIN,True",
                "2026-03-12,1456789.0,345678.0,BULL,TREND_MAIN,True",
            ]
        ),
        encoding="utf-8",
    )
    (exp_dir / "portfolio_trades.csv").write_text(
        "\n".join(
            [
                "date,symbol,side,fill_price,qty,reason_code",
                "2026-03-12,sh600000,BUY,11.0,100,BREAKOUT_HIGH",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        results_root / "market_snapshots" / "2026-03-12" / "market_snapshot.json",
        {
            "trade_date": "2026-03-12",
            "generated_at": "2026-03-12T15:10:00+08:00",
            "build_status": "ok",
            "warnings": [],
            "sentiment_layer": {"sentiment_regime": "HOT", "sentiment_score": 0.75},
            "liquidity_layer": {"market_amount_heat": 1.34},
            "risk_layer": {"drawdown_from_60d_high": -0.02},
        },
    )
    return str(results_root)






def _synthetic_approval_cards(monkeypatch):
    """Exercise retained approval API with explicit synthetic input, not an account integration."""
    original_dashboard = mobile_mod._current_mobile_dashboard
    state = {"snapshot_id": "fixture-snapshot"}
    def dashboard():
        payload = original_dashboard()
        cards = []
        for symbol, action in [("sh600519", "buy"), ("sh600000", "sell")]:
            cards.append({"suggestion_id": "fixture-" + action, "symbol": symbol, "name": "fixture",
                          "action_type": action, "bucket": action, "source_mode": "explicit_test_fixture",
                          "exp_id": "exp_mobile_api_001", "signal_date": "2026-03-13",
                          "as_of_date": "2026-03-13", "snapshot_id": state["snapshot_id"],
                          "reconcile_id": "fixture-context", "account_id": "test-account",
                          "system_suggestion": {"suggested_qty": 100, "target_weight": 0.2},
                          "blockers": [], "user_decision": {"status": "none"}})
        payload["guidance"]["approval_cards"] = cards
        return payload
    monkeypatch.setattr(mobile_mod, "_current_mobile_dashboard", dashboard)
    return state


def _login_mobile(test_client) -> None:
    login = test_client.post(
        "/api/mobile/login",
        json={"password": "secret-pass"},
        headers={"host": "192.168.1.8"},
    )
    assert login.status_code == 200
    assert login.json()["authenticated"] is True


def test_mobile_paths_reject_public_host(test_client, monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_DASHBOARD_PASSWORD", "secret-pass")
    monkeypatch.setenv("MOBILE_AUTH_SECRET", "signing-secret")

    response = test_client.get("/api/mobile/session", headers={"host": "public.example.com"})

    assert response.status_code == 403


def test_mobile_page_is_available_on_private_host(test_client, monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_DASHBOARD_PASSWORD", "secret-pass")
    monkeypatch.setenv("MOBILE_AUTH_SECRET", "signing-secret")

    response = test_client.get("/mobile", headers={"host": "192.168.1.8"})

    assert response.status_code == 200
    assert "mobile-dashboard.js" in response.text
    assert 'id="mdViewHost"' in response.text
    assert 'id="mdAuthTemplate"' in response.text
    assert 'id="mdDashboardTemplate"' in response.text
    assert 'id="mdTradeIneffectiveCount"' in response.text
    assert 'id="mdDepositBtn"' not in response.text


def test_mobile_pwa_assets_follow_private_host_restrictions(test_client, monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_DASHBOARD_PASSWORD", "secret-pass")
    monkeypatch.setenv("MOBILE_AUTH_SECRET", "signing-secret")

    manifest_public = test_client.get("/assets/manifest.webmanifest", headers={"host": "public.example.com"})
    sw_public = test_client.get("/mobile-service-worker.js", headers={"host": "public.example.com"})
    js_public = test_client.get("/assets/js/mobile-dashboard.js", headers={"host": "public.example.com"})

    assert manifest_public.status_code == 403
    assert sw_public.status_code == 403
    assert js_public.status_code == 403

    manifest_private = test_client.get("/assets/manifest.webmanifest", headers={"host": "192.168.1.8"})
    sw_private = test_client.get("/mobile-service-worker.js", headers={"host": "192.168.1.8"})

    assert manifest_private.status_code == 200
    assert '"display":"standalone"' in manifest_private.text.replace(" ", "")
    assert sw_private.status_code == 200
    assert "serviceWorker" in sw_private.text or "self.addEventListener" in sw_private.text


def test_mobile_login_dashboard_and_logout(test_client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MOBILE_DASHBOARD_PASSWORD", "secret-pass")
    monkeypatch.setenv("MOBILE_AUTH_SECRET", "signing-secret")
    monkeypatch.setenv("RESULTS_ROOT", _prepare_outputs(tmp_path))

    session_before = test_client.get("/api/mobile/session", headers={"host": "192.168.1.8"})
    assert session_before.status_code == 200
    assert session_before.json()["authenticated"] is False
    assert session_before.json()["configured"] is True

    wrong_login = test_client.post(
        "/api/mobile/login",
        json={"password": "wrong"},
        headers={"host": "192.168.1.8"},
    )
    assert wrong_login.status_code == 401

    _login_mobile(test_client)

    dashboard = test_client.get("/api/mobile/dashboard", headers={"host": "192.168.1.8"})
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["holding_sync"]["status"] == "unavailable"
    assert payload["source_mode"] == "experiment_fallback"
    assert payload["reconcile"]["cash"] is None
    assert payload["positions"] is None
    assert payload["experiment"]["exp_id"] == "exp_mobile_api_001"
    assert payload["notifications"]["active_channel"] == "in_app_feed"
    assert payload["guidance"]["status"] == "fallback_read_only"
    assert payload["guidance"]["approval_cards"] == []

    session_after = test_client.get("/api/mobile/session", headers={"host": "192.168.1.8"})
    assert session_after.status_code == 200
    assert session_after.json()["authenticated"] is True

    logout = test_client.post("/api/mobile/logout", headers={"host": "192.168.1.8"})
    assert logout.status_code == 200

    session_final = test_client.get("/api/mobile/session", headers={"host": "192.168.1.8"})
    assert session_final.status_code == 200
    assert session_final.json()["authenticated"] is False

    dashboard_after_logout = test_client.get("/api/mobile/dashboard", headers={"host": "192.168.1.8"})
    assert dashboard_after_logout.status_code == 401


def test_mobile_approval_commit_revoke_and_reject_flow(test_client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MOBILE_DASHBOARD_PASSWORD", "secret-pass")
    monkeypatch.setenv("MOBILE_AUTH_SECRET", "signing-secret")
    monkeypatch.setenv("RESULTS_ROOT", _prepare_outputs(tmp_path))

    _synthetic_approval_cards(monkeypatch)
    _login_mobile(test_client)

    dashboard = test_client.get("/api/mobile/dashboard", headers={"host": "192.168.1.8"})
    assert dashboard.status_code == 200
    payload = dashboard.json()
    buy_card = next(card for card in payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    sell_card = next(card for card in payload["guidance"]["approval_cards"] if card["symbol"] == "sh600000")

    prepare_buy = test_client.post(
        "/api/mobile/approvals/prepare",
        json={"suggestion_id": buy_card["suggestion_id"], "decision": "approve"},
        headers={"host": "192.168.1.8"},
    )
    assert prepare_buy.status_code == 200
    buy_token = prepare_buy.json()["confirm_token"]

    commit_buy = test_client.post(
        "/api/mobile/approvals/commit",
        json={"confirm_token": buy_token, "idempotency_key": "idem-buy-001"},
        headers={"host": "192.168.1.8"},
    )
    assert commit_buy.status_code == 200
    assert commit_buy.json()["created"] is True
    assert commit_buy.json()["ticket"]["status"] == "approved_pending"
    assert commit_buy.json()["ticket"]["snapshot_id"] == buy_card["snapshot_id"]
    assert commit_buy.json()["ticket"]["reconcile_id"] == buy_card["reconcile_id"]

    dashboard_after_buy = test_client.get("/api/mobile/dashboard", headers={"host": "192.168.1.8"})
    assert dashboard_after_buy.status_code == 200
    assert dashboard_after_buy.json()["positions"] is None
    assert dashboard_after_buy.json()["guidance"]["pending_count"] == 1

    commit_buy_duplicate = test_client.post(
        "/api/mobile/approvals/commit",
        json={"confirm_token": buy_token, "idempotency_key": "idem-buy-001"},
        headers={"host": "192.168.1.8"},
    )
    assert commit_buy_duplicate.status_code == 200
    assert commit_buy_duplicate.json()["created"] is False
    assert commit_buy_duplicate.json()["ticket"]["ticket_id"] == commit_buy.json()["ticket"]["ticket_id"]

    revoke_buy = test_client.post(
        f"/api/mobile/approval-tickets/{commit_buy.json()['ticket']['ticket_id']}/revoke",
        json={"reason": "manual reset"},
        headers={"host": "192.168.1.8"},
    )
    assert revoke_buy.status_code == 200
    assert revoke_buy.json()["ticket"]["status"] == "revoked"

    prepare_sell = test_client.post(
        "/api/mobile/approvals/prepare",
        json={"suggestion_id": sell_card["suggestion_id"], "decision": "approve", "final_qty": 50},
        headers={"host": "192.168.1.8"},
    )
    assert prepare_sell.status_code == 200

    commit_sell = test_client.post(
        "/api/mobile/approvals/commit",
        json={"confirm_token": prepare_sell.json()["confirm_token"], "idempotency_key": "idem-sell-001"},
        headers={"host": "192.168.1.8"},
    )
    assert commit_sell.status_code == 200
    assert commit_sell.json()["ticket"]["status"] == "approved_pending"
    assert commit_sell.json()["ticket"]["manual_adjusted"] is True
    assert commit_sell.json()["ticket"]["final_qty"] == 50

    pending = test_client.get(
        "/api/mobile/approval-tickets?status=approved_pending",
        headers={"host": "192.168.1.8"},
    )
    assert pending.status_code == 200
    assert pending.json()["count"] == 1
    assert pending.json()["items"][0]["ticket_id"] == commit_sell.json()["ticket"]["ticket_id"]

    revoke_sell = test_client.post(
        f"/api/mobile/approval-tickets/{commit_sell.json()['ticket']['ticket_id']}/revoke",
        json={"reason": "cancel sell"},
        headers={"host": "192.168.1.8"},
    )
    assert revoke_sell.status_code == 200
    assert revoke_sell.json()["ticket"]["status"] == "revoked"

    prepare_reject = test_client.post(
        "/api/mobile/approvals/prepare",
        json={
            "suggestion_id": buy_card["suggestion_id"],
            "decision": "reject",
            "reject_reason": "manual reject",
        },
        headers={"host": "192.168.1.8"},
    )
    assert prepare_reject.status_code == 200

    commit_reject = test_client.post(
        "/api/mobile/approvals/commit",
        json={"confirm_token": prepare_reject.json()["confirm_token"], "idempotency_key": "idem-reject-001"},
        headers={"host": "192.168.1.8"},
    )
    assert commit_reject.status_code == 200
    assert commit_reject.json()["ticket"]["status"] == "rejected"
    assert commit_reject.json()["ticket"]["reject_reason"] == "manual reject"

    pending_after = test_client.get(
        "/api/mobile/approval-tickets?status=approved_pending",
        headers={"host": "192.168.1.8"},
    )
    assert pending_after.status_code == 200
    assert pending_after.json()["count"] == 0


def test_mobile_commit_rejects_when_surface_changes(test_client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MOBILE_DASHBOARD_PASSWORD", "secret-pass")
    monkeypatch.setenv("MOBILE_AUTH_SECRET", "signing-secret")
    monkeypatch.setenv("RESULTS_ROOT", _prepare_outputs(tmp_path))

    synthetic_state = _synthetic_approval_cards(monkeypatch)
    _login_mobile(test_client)

    dashboard = test_client.get("/api/mobile/dashboard", headers={"host": "192.168.1.8"})
    buy_card = next(card for card in dashboard.json()["guidance"]["approval_cards"] if card["symbol"] == "sh600519")

    prepare_buy = test_client.post(
        "/api/mobile/approvals/prepare",
        json={"suggestion_id": buy_card["suggestion_id"], "decision": "approve"},
        headers={"host": "192.168.1.8"},
    )
    assert prepare_buy.status_code == 200

    synthetic_state["snapshot_id"] = "changed-snapshot"
    _write_json(
        mobile_mod._results_root() / "market_snapshots" / "2026-03-13" / "market_snapshot.json",
        {
            "trade_date": "2026-03-13",
            "generated_at": "2026-03-13T15:10:00+08:00",
            "build_status": "ok",
            "warnings": [],
            "sentiment_layer": {"sentiment_regime": "HOT", "sentiment_score": 0.75},
            "liquidity_layer": {"market_amount_heat": 1.34},
            "risk_layer": {"drawdown_from_60d_high": -0.02},
        },
    )

    commit_buy = test_client.post(
        "/api/mobile/approvals/commit",
        json={"confirm_token": prepare_buy.json()["confirm_token"], "idempotency_key": "idem-buy-old"},
        headers={"host": "192.168.1.8"},
    )
    assert commit_buy.status_code == 409
    assert commit_buy.json()["detail"] in {
        "suggestion snapshot changed",
        "holding snapshot changed",
        "reconcile surface changed",
        "as_of_date changed",
    }


def test_mobile_dashboard_surfaces_execution_ticket_lifecycle(test_client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MOBILE_DASHBOARD_PASSWORD", "secret-pass")
    monkeypatch.setenv("MOBILE_AUTH_SECRET", "signing-secret")
    monkeypatch.setenv("RESULTS_ROOT", _prepare_outputs(tmp_path))

    _synthetic_approval_cards(monkeypatch)
    _login_mobile(test_client)

    dashboard = test_client.get("/api/mobile/dashboard", headers={"host": "192.168.1.8"})
    assert dashboard.status_code == 200
    buy_card = next(card for card in dashboard.json()["guidance"]["approval_cards"] if card["symbol"] == "sh600519")

    prepare_buy = test_client.post(
        "/api/mobile/approvals/prepare",
        json={"suggestion_id": buy_card["suggestion_id"], "decision": "approve"},
        headers={"host": "192.168.1.8"},
    )
    assert prepare_buy.status_code == 200

    commit_buy = test_client.post(
        "/api/mobile/approvals/commit",
        json={"confirm_token": prepare_buy.json()["confirm_token"], "idempotency_key": "idem-buy-exec"},
        headers={"host": "192.168.1.8"},
    )
    assert commit_buy.status_code == 200
    ticket_id = commit_buy.json()["ticket"]["ticket_id"]

    claim_approval_ticket(mobile_mod._results_root(), ticket_id=ticket_id, executor_id="desktop-sim")
    record_execution_update(
        mobile_mod._results_root(),
        ticket_id=ticket_id,
        status="partially_filled",
        executor_id="desktop-sim",
        filled_qty=40,
        avg_fill_price=1498.6,
        message="盘中部分成交",
    )

    updated_dashboard = test_client.get("/api/mobile/dashboard", headers={"host": "192.168.1.8"})
    assert updated_dashboard.status_code == 200
    payload = updated_dashboard.json()
    assert payload["guidance"]["pending_count"] == 0
    assert payload["guidance"]["execution_count"] == 1
    execution_item = payload["guidance"]["execution_tickets"][0]
    assert execution_item["ticket_id"] == ticket_id
    assert execution_item["status"] == "partially_filled"
    assert execution_item["executor_id"] == "desktop-sim"
    assert execution_item["filled_qty"] == 40
    assert execution_item["avg_fill_price"] == 1498.6
    assert [event["status"] for event in execution_item["recent_events"]] == ["claimed", "partially_filled"]
    assert payload["briefing"]["execution_anomalies"]["count"] == 1
    assert payload["briefing"]["execution_anomalies"]["items"][0]["anomaly_type"] == "partially_filled"
    assert payload["briefing"]["post_close"]["confirmed_count"] == 1
    assert payload["briefing"]["post_close"]["executed_count"] == 1




def test_removed_cash_pool_routes_are_unavailable(test_client, monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_DASHBOARD_PASSWORD", "secret-pass")
    monkeypatch.setenv("MOBILE_AUTH_SECRET", "signing-secret")
    _login_mobile(test_client)
    assert test_client.get("/api/mobile/cash-pool/status", headers={"host": "192.168.1.8"}).status_code == 404
    assert test_client.post("/api/mobile/cash-pool/deposit", json={"amount": 10}, headers={"host": "192.168.1.8"}).status_code == 404
    spec = test_client.get("/openapi.json").json()
    assert not any(path.startswith("/api/mobile/cash-pool") for path in spec["paths"])
