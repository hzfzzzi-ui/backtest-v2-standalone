from __future__ import annotations

import json

from backend.core.services.mobile_dashboard_service import build_mobile_dashboard
from backend.core.services.mobile_ops_service import create_ticket_from_confirmed_action


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


def _sample_ticket_card():
    return {
        "suggestion_id": "sg_test_001", "exp_id": "exp_mobile_001",
        "account_id": "test-account", "symbol": "sh600519", "name": "synthetic",
        "action_type": "buy", "bucket": "buy", "signal_date": "2026-03-11",
        "system_suggestion": {"suggested_qty": 100, "target_weight": 0.2},
    }


def test_dashboard_marks_account_data_unavailable_without_fabricated_zero(tmp_path) -> None:
    results_root, _ = _build_results_root(tmp_path)
    payload = build_mobile_dashboard(results_root)
    assert payload["holding_sync"]["status"] == "unavailable"
    assert payload["reconcile"]["status"] == "unavailable"
    assert payload["reconcile"]["cash"] is None
    assert payload["positions"] is None
    assert payload["guidance"]["status"] == "fallback_read_only"
    assert payload["guidance"]["approval_cards"] == []
    assert payload["experiment"]["exp_id"] == "exp_mobile_001"


def test_dashboard_preserves_pending_ticket_when_account_unavailable(tmp_path) -> None:
    results_root, _ = _build_results_root(tmp_path)
    ticket, created = create_ticket_from_confirmed_action(
        results_root, card=_sample_ticket_card(), decision="approve", operator="mobile@test",
        idempotency_key="manual-ticket", confirm_payload={"final_qty": 100, "nonce": "n-1"},
    )
    payload = build_mobile_dashboard(results_root)
    assert created is True
    assert payload["guidance"]["pending_count"] == 1
    assert payload["guidance"]["pending_tickets"][0]["ticket_id"] == ticket["ticket_id"]
    assert payload["guidance"]["approval_cards"] == []


def test_preconfirm_blockers_remain_independent_of_simulation_account() -> None:
    from backend.core.services.mobile_dashboard_service import _build_blockers
    blockers = _build_blockers(
        suggestion_id="sg_test_001", freshness={"status": "stale"},
        ops_snapshot={"active_pending_by_suggestion": {"sg_test_001": {"ticket_id": "t1"}},
                      "risk_lock": {"locked": True}, "executor": {"declared": True, "available": False}},
    )
    assert {row["code"] for row in blockers} == {"stale_data", "duplicate_submission", "risk_locked", "executor_unavailable"}


def test_dashboard_notification_channel_downgrades_when_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_PRIVATE_NOTIFICATION_CHANNEL", "pwa_push")
    results_root, _ = _build_results_root(tmp_path)
    payload = build_mobile_dashboard(results_root)
    assert payload["notifications"]["preferred_channel"] == "pwa_push"
    assert payload["notifications"]["active_channel"] == "in_app_feed"
    assert payload["notifications"]["downgraded"] is True
    assert payload["notifications"]["downgrade_reason"] == "channel_not_available"
