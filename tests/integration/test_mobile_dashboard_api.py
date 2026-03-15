from __future__ import annotations

import json

from backend.api.mobile import impl as mobile_mod


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
                "label": "手机 API 样本",
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
    _write_json(exp_dir / "resolved_config.json", {"config_json": {"mode": "experiment", "universe_mode": "HS300_ZZ500"}})
    _write_json(exp_dir / "stock_names.json", {"sh600000": "浦发银行", "sh600519": "贵州茅台"})
    (exp_dir / "portfolio_daily.csv").write_text(
        "\n".join(
            [
                "date,nav,cash,market_state,trade_mode,benchmark_regime_on",
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
    assert "回测手机看板" in response.text


def test_mobile_login_dashboard_and_logout(test_client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MOBILE_DASHBOARD_PASSWORD", "secret-pass")
    monkeypatch.setenv("MOBILE_AUTH_SECRET", "signing-secret")
    monkeypatch.setenv("RESULTS_ROOT", _prepare_outputs(tmp_path))
    monkeypatch.setattr(
        mobile_mod,
        "_preview_execution",
        lambda config_json, exp_id, as_of_date: {
            "as_of_date_used": as_of_date,
            "candidates": [{"symbol": "sh600519", "reasons": ["breakout", "rank=1"]}],
            "target_positions": [{"symbol": "sh600519", "target_weight": 0.2, "cap_reason": ""}],
        },
    )

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

    login = test_client.post(
        "/api/mobile/login",
        json={"password": "secret-pass"},
        headers={"host": "192.168.1.8"},
    )
    assert login.status_code == 200
    assert login.json()["authenticated"] is True

    dashboard = test_client.get("/api/mobile/dashboard", headers={"host": "192.168.1.8"})
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["status"] == "ok"
    assert payload["experiment"]["exp_id"] == "exp_mobile_api_001"
    assert payload["experiment"]["title"] == "手机 API 样本"
    assert [item["symbol"] for item in payload["guidance"]["buy"]] == ["sh600519"]
    assert [item["symbol"] for item in payload["guidance"]["sell"]] == ["sh600000"]
    assert any(card["symbol"] == "sh600519" for card in payload["guidance"]["approval_cards"])

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
    monkeypatch.setattr(
        mobile_mod,
        "_preview_execution",
        lambda config_json, exp_id, as_of_date: {
            "as_of_date_used": as_of_date,
            "candidates": [
                {"symbol": "sh600519", "reasons": ["breakout", "rank=1"]},
                {"symbol": "sh600000", "reasons": ["trim", "rebalance"]},
            ],
            "target_positions": [{"symbol": "sh600519", "target_weight": 0.2, "cap_reason": ""}],
        },
    )

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
    assert commit_buy.json()["ticket"]["manual_adjusted"] is False

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
