from __future__ import annotations

import json

from backend.core.services.mobile_dashboard_service import build_mobile_dashboard
from backend.core.services.mobile_ops_service import create_ticket_from_confirmed_action
from backend.core.services.sim_account_service import store_holdings_snapshot


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_results_root(tmp_path, *, label: str = "鎵嬫満鐪嬫澘鏍锋湰"):
    results_root = tmp_path / "outputs"
    exp_id = "exp_mobile_001"
    exp_dir = results_root / "experiments" / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        results_root / "experiments" / "index.json",
        [
            {
                "exp_id": exp_id,
                "label": label,
                "created_at": "2026-03-12T10:00:00",
                "status": "OK",
                "cagr": 0.18,
                "sharpe": 1.12,
                "max_drawdown": -0.15,
                "total_return": 0.82,
                "trades": 42,
                "universe_mode": "HS300_ZZ500",
            }
        ],
    )
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": exp_id,
            "artifacts": {
                "stock_names": "stock_names.json",
                "perf": "perf.json",
            },
        },
    )
    _write_json(
        exp_dir / "perf.json",
        {
            "cagr": 0.18,
            "sharpe": 1.12,
            "max_drawdown": -0.15,
            "total_return": 0.82,
            "trades": 42,
        },
    )
    _write_json(exp_dir / "run_meta.json", {"data": {"universe_mode": "HS300_ZZ500"}})
    _write_json(
        exp_dir / "resolved_config.json",
        {
            "config_json": {
                "mode": "experiment",
                "strategy_pack": "BREAKOUT_TREND",
                "universe_mode": "HS300_ZZ500",
                "universe": {"start": "2025-01-01", "end": "2026-03-11"},
                "position_risk": {
                    "max_positions": 10,
                    "single_stock_cap": 0.1,
                    "cost_model": {"matching": "next_open"},
                },
            }
        },
    )
    _write_json(
        exp_dir / "stock_names.json",
        {
            "sh600000": "娴﹀彂閾惰",
            "sh600036": "鎷涘晢閾惰",
            "sh600519": "璐靛窞鑼呭彴",
        },
    )
    (exp_dir / "portfolio_daily.csv").write_text(
        "\n".join(
            [
                "date,nav,cash,market_state,trade_mode,benchmark_regime_on",
                "2026-03-10,1200000.0,220000.0,WARM,TREND_MAIN,True",
                "2026-03-11,1234567.8,234567.8,BULL,TREND_MAIN,True",
            ]
        ),
        encoding="utf-8",
    )
    (exp_dir / "portfolio_trades.csv").write_text(
        "\n".join(
            [
                "date,symbol,side,fill_price,qty,reason_code",
                "2026-03-10,sh600000,BUY,10.50,100,BREAKOUT_HIGH",
                "2026-03-10,sh600036,BUY,42.00,200,BREAKOUT_HIGH",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        results_root / "market_snapshots" / "2026-03-11" / "market_snapshot.json",
        {
            "trade_date": "2026-03-11",
            "generated_at": "2026-03-11T15:10:00+08:00",
            "build_status": "ok",
            "warnings": [{"code": "SNAPSHOT_WARN", "message": "閲忚兘杞诲井鍥炶惤"}],
            "sentiment_layer": {
                "sentiment_regime": "WARM",
                "sentiment_score": 0.62,
            },
            "liquidity_layer": {"market_amount_heat": 1.18},
            "risk_layer": {"drawdown_from_60d_high": -0.04},
        },
    )
    return results_root, exp_id


def _seed_holdings_snapshot(results_root, *, trade_date: str, positions: list[dict], cash: float = 120000.0):
    return store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": trade_date,
            "source_type": "manual_import",
            "cash": cash,
            "positions": positions,
        },
    )


def _seed_reconcile(
    results_root,
    *,
    exp_id: str,
    snapshot: dict,
    action_sheet: list[dict],
    reconcile_id: str = "rc_unit_001",
    as_of_date: str | None = None,
):
    buy = [item for item in action_sheet if item.get("action_type") == "buy"]
    sell = [item for item in action_sheet if item.get("action_type") == "sell"]
    hold = [item for item in action_sheet if item.get("action_type") == "hold"]
    payload = {
        "schema_version": "sim_account_reconcile_run@1",
        "account_id": "paper_a_share_main",
        "reconcile_id": reconcile_id,
        "generated_at": "2026-03-11T15:15:00+08:00",
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_trade_date": snapshot["trade_date"],
        "snapshot_synced_at": snapshot["synced_at"],
        "as_of_date": as_of_date or snapshot["trade_date"],
        "source_mode": "position_aware_reconcile",
        "strategy_source": {
            "exp_id": exp_id,
            "created_at": "2026-03-12T10:00:00",
            "config_hash": "cfg_unit_001",
            "asset_scope": "cn_a_equity",
        },
        "execution_assumptions": {
            "signal_clock": "POST_CLOSE",
            "execution_clock": "NEXT_OPEN",
            "reference_price_basis": "latest_close",
        },
        "summary": {
            "action_count": len(action_sheet),
            "buy_count": len(buy),
            "sell_count": len(sell),
            "hold_count": len(hold),
            "blocked_count": len([item for item in action_sheet if item.get("blocked")]),
        },
        "actions": {
            "buy": buy,
            "sell": sell,
            "hold": hold,
        },
        "action_sheet": action_sheet,
        "diagnostics": {
            "reason_counts": {},
            "order_reject_reason_counts": {},
            "blocked_count": len([item for item in action_sheet if item.get("blocked")]),
            "market_state": "BULL",
            "trade_mode": "TREND_MAIN",
            "effective_max_positions": 10,
        },
    }
    account_root = results_root / "ops" / "sim_account" / "paper_a_share_main" / "reconcile"
    _write_json(account_root / "latest.json", payload)
    _write_json(account_root / "history" / f"{reconcile_id}.json", payload)
    return payload


def _sample_action_sheet():
    return [
        {
            "symbol": "sh600519",
            "name": "璐靛窞鑼呭彴",
            "action_type": "buy",
            "current_qty": 0,
            "sellable_qty": 0,
            "suggested_qty": 100,
            "target_qty": 100,
            "delta_qty": 100,
            "reference_price": 1500.0,
            "reference_price_basis": "latest_close",
            "reason_code": "BUY_BREAKOUT",
            "reason_tags": ["breakout", "rank=1"],
            "blocked": False,
            "blocked_reason": "",
            "target_weight": 0.2,
        },
        {
            "symbol": "sh600036",
            "name": "鎷涘晢閾惰",
            "action_type": "sell",
            "current_qty": 200,
            "sellable_qty": 200,
            "suggested_qty": 200,
            "target_qty": 0,
            "delta_qty": -200,
            "reference_price": 42.5,
            "reference_price_basis": "latest_close",
            "reason_code": "SELL_EXIT",
            "reason_tags": ["exit"],
            "blocked": False,
            "blocked_reason": "",
            "target_weight": 0.0,
        },
        {
            "symbol": "sh600000",
            "name": "娴﹀彂閾惰",
            "action_type": "hold",
            "current_qty": 100,
            "sellable_qty": 100,
            "suggested_qty": 0,
            "target_qty": 100,
            "delta_qty": 0,
            "reference_price": 10.8,
            "reference_price_basis": "latest_close",
            "reason_code": "HOLD",
            "reason_tags": ["currently_held"],
            "blocked": False,
            "blocked_reason": "",
            "target_weight": 0.12,
        },
    ]


def test_build_mobile_dashboard_returns_reconcile_surface(tmp_path) -> None:
    results_root, exp_id = _build_results_root(tmp_path)
    snapshot = _seed_holdings_snapshot(
        results_root,
        trade_date="2026-03-11",
        positions=[
            {"symbol": "sh600000", "qty": 100, "sellable_qty": 100, "avg_cost": 10.5, "name": "娴﹀彂閾惰"},
            {"symbol": "sh600036", "qty": 200, "sellable_qty": 200, "avg_cost": 42.0, "name": "鎷涘晢閾惰"},
        ],
    )
    reconcile = _seed_reconcile(results_root, exp_id=exp_id, snapshot=snapshot, action_sheet=_sample_action_sheet())

    payload = build_mobile_dashboard(results_root)

    assert payload["status"] == "ok"
    assert payload["source_mode"] == "position_aware_reconcile"
    assert payload["reconcile"]["cash"] == 120000.0
    assert payload["experiment"]["daily_pnl"] == 34567.8
    assert abs(payload["experiment"]["daily_return"] - (34567.8 / 1200000.0)) < 1e-9
    assert payload["holding_sync"]["latest_snapshot_id"] == snapshot["snapshot_id"]
    assert payload["reconcile"]["reconcile_id"] == reconcile["reconcile_id"]
    assert [item["symbol"] for item in payload["positions"]] == ["sh600000", "sh600036"]
    assert [item["symbol"] for item in payload["guidance"]["buy"]] == ["sh600519"]
    assert [item["symbol"] for item in payload["guidance"]["sell"]] == ["sh600036"]
    assert [item["symbol"] for item in payload["guidance"]["hold"]] == ["sh600000"]
    assert payload["briefing"]["pre_open"]["pending_confirmation_count"] == 2
    assert payload["briefing"]["pre_open"]["unfinished_ticket_count"] == 0
    assert payload["briefing"]["post_close"]["status"] == "empty"
    assert (results_root / "mobile_ops" / "daily_briefings" / "latest.json").exists()
    buy_card = next(card for card in payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    assert buy_card["snapshot_id"] == snapshot["snapshot_id"]
    assert buy_card["reconcile_id"] == reconcile["reconcile_id"]
    assert buy_card["system_suggestion"]["reference_price"] == 1500.0
    assert buy_card["system_suggestion"]["suggested_qty"] == 100
    assert buy_card["can_confirm"] is True


def test_build_mobile_dashboard_preserves_row_signal_dates_for_reconcile_cards(tmp_path) -> None:
    results_root, exp_id = _build_results_root(tmp_path)
    snapshot = _seed_holdings_snapshot(
        results_root,
        trade_date="2026-03-09",
        positions=[
            {"symbol": "sh600000", "qty": 100, "sellable_qty": 100, "avg_cost": 10.5, "name": "濞达箑褰傞柧鎯邦攽"},
        ],
    )
    action_sheet = [
        {
            "symbol": "sh600519",
            "name": "鐠愰潧绐為懠鍛酱",
            "action_type": "buy",
            "signal_date": "2026-03-10",
            "as_of_date": "2026-03-10",
            "current_qty": 0,
            "sellable_qty": 0,
            "suggested_qty": 100,
            "target_qty": 100,
            "delta_qty": 100,
            "reference_price": 1500.0,
            "reference_price_basis": "latest_close",
            "reason_code": "BUY_BREAKOUT",
            "reason_tags": ["breakout"],
            "blocked": False,
            "blocked_reason": "",
            "target_weight": 0.2,
        },
        {
            "symbol": "sh600036",
            "name": "閹锋稑鏅㈤柧鎯邦攽",
            "action_type": "sell",
            "signal_date": "2026-03-12",
            "as_of_date": "2026-03-12",
            "current_qty": 100,
            "sellable_qty": 100,
            "suggested_qty": 100,
            "target_qty": 0,
            "delta_qty": -100,
            "reference_price": 42.5,
            "reference_price_basis": "latest_close",
            "reason_code": "SELL_EXIT",
            "reason_tags": ["exit"],
            "blocked": False,
            "blocked_reason": "",
            "target_weight": 0.0,
        },
    ]
    _seed_reconcile(
        results_root,
        exp_id=exp_id,
        snapshot=snapshot,
        action_sheet=action_sheet,
        reconcile_id="rc_row_dates",
        as_of_date="2026-03-12",
    )

    payload = build_mobile_dashboard(results_root)

    assert payload["reconcile"]["as_of_date"] == "2026-03-12"
    cards = payload["guidance"]["approval_cards"]
    assert [item["symbol"] for item in cards] == ["sh600519", "sh600036"]
    first_card = cards[0]
    second_card = cards[1]
    assert first_card["signal_date"] == "2026-03-10"
    assert first_card["as_of_date"] == "2026-03-10"
    assert second_card["signal_date"] == "2026-03-12"
    assert second_card["as_of_date"] == "2026-03-12"
    assert first_card["suggestion_id"] != second_card["suggestion_id"]


def test_build_mobile_dashboard_fallback_no_longer_uses_experiment_positions(tmp_path) -> None:
    results_root, _exp_id = _build_results_root(tmp_path)

    payload = build_mobile_dashboard(results_root)

    assert payload["status"] == "ok"
    assert payload["source_mode"] == "experiment_fallback"
    assert payload["holding_sync"]["status"] == "unsynced"
    assert payload["positions"] == []
    assert payload["guidance"]["approval_cards"] == []
    assert payload["guidance"]["buy"] == []
    assert "latest holdings snapshot is missing" in payload["warnings"]


def test_build_mobile_dashboard_surfaces_latest_user_decision(tmp_path) -> None:
    results_root, exp_id = _build_results_root(tmp_path)
    snapshot = _seed_holdings_snapshot(
        results_root,
        trade_date="2026-03-11",
        positions=[
            {"symbol": "sh600000", "qty": 100, "sellable_qty": 100, "avg_cost": 10.5, "name": "娴﹀彂閾惰"},
            {"symbol": "sh600036", "qty": 200, "sellable_qty": 200, "avg_cost": 42.0, "name": "鎷涘晢閾惰"},
        ],
    )
    _seed_reconcile(results_root, exp_id=exp_id, snapshot=snapshot, action_sheet=_sample_action_sheet())

    first_payload = build_mobile_dashboard(results_root)
    buy_card = next(card for card in first_payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    ticket, created = create_ticket_from_confirmed_action(
        results_root,
        card=buy_card,
        decision="approve",
        operator="mobile@test",
        idempotency_key="idem-001",
        confirm_payload={"final_qty": 200, "nonce": "n-1"},
    )

    assert created is True
    assert ticket["status"] == "approved_pending"

    second_payload = build_mobile_dashboard(results_root)
    second_buy_card = next(card for card in second_payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")

    assert second_buy_card["user_decision"]["status"] == "approved_pending"
    assert second_buy_card["user_decision"]["manual_adjusted"] is True
    assert any(blocker["code"] == "duplicate_submission" for blocker in second_buy_card["blockers"])


def test_build_mobile_dashboard_invalidates_pending_after_snapshot_changes(tmp_path) -> None:
    results_root, exp_id = _build_results_root(tmp_path)
    first_snapshot = _seed_holdings_snapshot(
        results_root,
        trade_date="2026-03-11",
        positions=[
            {"symbol": "sh600000", "qty": 100, "sellable_qty": 100, "avg_cost": 10.5, "name": "娴﹀彂閾惰"},
            {"symbol": "sh600036", "qty": 200, "sellable_qty": 200, "avg_cost": 42.0, "name": "鎷涘晢閾惰"},
        ],
    )
    _seed_reconcile(results_root, exp_id=exp_id, snapshot=first_snapshot, action_sheet=_sample_action_sheet(), reconcile_id="rc_v1")

    first_payload = build_mobile_dashboard(results_root)
    first_buy_card = next(card for card in first_payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    create_ticket_from_confirmed_action(
        results_root,
        card=first_buy_card,
        decision="approve",
        operator="mobile@test",
        idempotency_key="idem-old",
        confirm_payload={"final_qty": 100, "nonce": "n-old"},
    )

    second_snapshot = _seed_holdings_snapshot(
        results_root,
        trade_date="2026-03-12",
        positions=[
            {"symbol": "sh600000", "qty": 100, "sellable_qty": 100, "avg_cost": 10.5, "name": "娴﹀彂閾惰"},
        ],
    )
    _write_json(
        results_root / "market_snapshots" / "2026-03-12" / "market_snapshot.json",
        {
            "trade_date": "2026-03-12",
            "generated_at": "2026-03-12T15:10:00+08:00",
            "build_status": "ok",
            "warnings": [],
            "sentiment_layer": {"sentiment_regime": "HOT", "sentiment_score": 0.71},
            "liquidity_layer": {"market_amount_heat": 1.22},
            "risk_layer": {"drawdown_from_60d_high": -0.03},
        },
    )
    _seed_reconcile(results_root, exp_id=exp_id, snapshot=second_snapshot, action_sheet=_sample_action_sheet(), reconcile_id="rc_v2")

    second_payload = build_mobile_dashboard(results_root)
    second_buy_card = next(card for card in second_payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")

    assert second_buy_card["suggestion_id"] != first_buy_card["suggestion_id"]
    assert second_buy_card["user_decision"]["status"] == "none"
    assert not any(blocker["code"] == "duplicate_submission" for blocker in second_buy_card["blockers"])
    assert second_payload["guidance"]["pending_tickets"][0]["surface_status"] == "stale_surface"


def test_build_mobile_dashboard_exposes_all_preconfirm_blockers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_SIGNAL_STALENESS_DAYS", "0")
    results_root, exp_id = _build_results_root(tmp_path)
    snapshot = _seed_holdings_snapshot(
        results_root,
        trade_date="2026-03-11",
        positions=[
            {"symbol": "sh600000", "qty": 100, "sellable_qty": 100, "avg_cost": 10.5, "name": "娴﹀彂閾惰"},
            {"symbol": "sh600036", "qty": 200, "sellable_qty": 200, "avg_cost": 42.0, "name": "鎷涘晢閾惰"},
        ],
    )
    _seed_reconcile(results_root, exp_id=exp_id, snapshot=snapshot, action_sheet=_sample_action_sheet())
    _write_json(
        results_root / "market_snapshots" / "2026-03-12" / "market_snapshot.json",
        {
            "trade_date": "2026-03-12",
            "generated_at": "2026-03-12T15:10:00+08:00",
            "build_status": "ok",
            "warnings": [],
            "sentiment_layer": {"sentiment_regime": "HOT", "sentiment_score": 0.71},
            "liquidity_layer": {"market_amount_heat": 1.22},
            "risk_layer": {"drawdown_from_60d_high": -0.03},
        },
    )
    _write_json(results_root / "mobile_ops" / "risk_lock.json", {"locked": True, "reason": "risk stop"})
    _write_json(results_root / "mobile_ops" / "executor_status.json", {"available": False, "reason": "desktop offline"})

    initial_payload = build_mobile_dashboard(results_root)
    buy_card = next(card for card in initial_payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    create_ticket_from_confirmed_action(
        results_root,
        card=buy_card,
        decision="approve",
        operator="mobile@test",
        idempotency_key="idem-duplicate",
        confirm_payload={"final_qty": 100, "nonce": "n-2"},
    )

    payload = build_mobile_dashboard(results_root)
    buy_card = next(card for card in payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    blocker_codes = {item["code"] for item in buy_card["blockers"]}

    assert {"stale_data", "duplicate_submission", "risk_locked", "executor_unavailable"} <= blocker_codes
    assert buy_card["can_confirm"] is False


def test_build_mobile_dashboard_exposes_notification_feed_with_downgrade(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_PRIVATE_NOTIFICATION_CHANNEL", "pwa_push")
    results_root, exp_id = _build_results_root(tmp_path)
    snapshot = _seed_holdings_snapshot(
        results_root,
        trade_date="2026-03-11",
        positions=[
            {"symbol": "sh600000", "qty": 100, "sellable_qty": 100, "avg_cost": 10.5, "name": "娴﹀彂閾惰"},
            {"symbol": "sh600036", "qty": 200, "sellable_qty": 200, "avg_cost": 42.0, "name": "鎷涘晢閾惰"},
        ],
    )
    _seed_reconcile(results_root, exp_id=exp_id, snapshot=snapshot, action_sheet=_sample_action_sheet())

    payload = build_mobile_dashboard(results_root)

    assert payload["notifications"]["preferred_channel"] == "pwa_push"
    assert payload["notifications"]["active_channel"] == "in_app_feed"
    assert payload["notifications"]["downgraded"] is True
    assert payload["notifications"]["downgrade_reason"] == "channel_not_available"
    assert payload["notifications"]["count"] >= 1
