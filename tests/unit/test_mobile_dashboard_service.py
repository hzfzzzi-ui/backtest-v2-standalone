from __future__ import annotations

import json

from backend.core.services.mobile_dashboard_service import build_mobile_dashboard
from backend.core.services.mobile_ops_service import create_ticket_from_confirmed_action


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_results_root(tmp_path, *, label: str = "手机看板样本"):
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
    _write_json(
        exp_dir / "run_meta.json",
        {
            "data": {"universe_mode": "HS300_ZZ500"},
        },
    )
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
            "sh600000": "浦发银行",
            "sh600036": "招商银行",
            "sh600519": "贵州茅台",
        },
    )
    (exp_dir / "portfolio_daily.csv").write_text(
        "\n".join(
            [
                "date,nav,cash,market_state,trade_mode,benchmark_regime_on",
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
            "warnings": [{"code": "SNAPSHOT_WARN", "message": "量能轻微回落"}],
            "sentiment_layer": {
                "sentiment_regime": "WARM",
                "sentiment_score": 0.62,
            },
            "liquidity_layer": {"market_amount_heat": 1.18},
            "risk_layer": {"drawdown_from_60d_high": -0.04},
        },
    )
    return results_root, exp_id


def test_build_mobile_dashboard_returns_guidance(tmp_path) -> None:
    results_root, exp_id = _build_results_root(tmp_path)

    def preview_loader(config_json, request_exp_id, as_of_date):
        assert request_exp_id == exp_id
        assert config_json["universe_mode"] == "HS300_ZZ500"
        assert as_of_date == "2026-03-11"
        return {
            "as_of_date_used": "2026-03-11",
            "candidates": [
                {"symbol": "sh600000", "reasons": ["breakout", "rank=1"]},
                {"symbol": "sh600519", "reasons": ["breakout", "rank=2"]},
            ],
            "target_positions": [
                {"symbol": "sh600000", "target_weight": 0.2, "cap_reason": ""},
                {"symbol": "sh600519", "target_weight": 0.1, "cap_reason": ""},
            ],
        }

    payload = build_mobile_dashboard(results_root, preview_loader=preview_loader)

    assert payload["status"] == "ok"
    assert payload["experiment"]["exp_id"] == exp_id
    assert payload["experiment"]["title"] == "手机看板样本"
    assert payload["experiment"]["latest_trade_date"] == "2026-03-11"
    assert payload["market"]["summary"]["trade_date"] == "2026-03-11"
    assert [item["symbol"] for item in payload["guidance"]["buy"]] == ["sh600519"]
    assert [item["symbol"] for item in payload["guidance"]["hold"]] == ["sh600000"]
    assert [item["symbol"] for item in payload["guidance"]["sell"]] == ["sh600036"]
    assert [item["symbol"] for item in payload["positions"]] == ["sh600000", "sh600036"]
    assert payload["guidance"]["pending_count"] == 0
    assert any(card["symbol"] == "sh600519" for card in payload["guidance"]["approval_cards"])


def test_build_mobile_dashboard_summarizes_noisy_experiment_label(tmp_path) -> None:
    noisy_label = (
        "{'NAME': 'BREAKOUT_TREND', 'FAST': 5, 'SLOW': 20, 'ORDER_SIZE': 1000, "
        "'PARAMS': {'BREAKOUT_WINDOW': 45, 'ENABLE_ATR_STOP': TRUE}} | HS300_ZZ500"
    )
    results_root, _exp_id = _build_results_root(tmp_path, label=noisy_label)

    payload = build_mobile_dashboard(results_root)

    experiment = payload["experiment"]
    assert experiment["title"] == "突破趋势"
    assert "HS300_ZZ500" in experiment["subtitle"]
    assert "10持仓" in experiment["tags"]


def test_build_mobile_dashboard_empty_when_no_experiments(tmp_path) -> None:
    results_root = tmp_path / "outputs"
    results_root.mkdir(parents=True, exist_ok=True)

    payload = build_mobile_dashboard(results_root)

    assert payload["status"] == "empty"
    assert payload["experiment"] is None
    assert payload["guidance"]["buy"] == []


def test_build_mobile_dashboard_surfaces_latest_user_decision(tmp_path) -> None:
    results_root, exp_id = _build_results_root(tmp_path)

    def preview_loader(config_json, request_exp_id, as_of_date):
        assert request_exp_id == exp_id
        assert as_of_date == "2026-03-11"
        return {
            "as_of_date_used": "2026-03-11",
            "candidates": [
                {"symbol": "sh600519", "reasons": ["breakout", "rank=1"]},
            ],
            "target_positions": [
                {"symbol": "sh600519", "target_weight": 0.1, "cap_reason": ""},
            ],
        }

    first_payload = build_mobile_dashboard(results_root, preview_loader=preview_loader)
    buy_card = next(card for card in first_payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    ticket, created = create_ticket_from_confirmed_action(
        results_root,
        card=buy_card,
        decision="approve",
        operator="mobile@test",
        idempotency_key="idem-001",
        confirm_payload={"final_target_weight": 0.12, "nonce": "n-1"},
    )

    assert created is True
    assert ticket["status"] == "approved_pending"

    second_payload = build_mobile_dashboard(results_root, preview_loader=preview_loader)
    second_buy_card = next(card for card in second_payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")

    assert second_buy_card["user_decision"]["status"] == "approved_pending"
    assert second_buy_card["user_decision"]["manual_adjusted"] is True
    assert any(blocker["code"] == "duplicate_submission" for blocker in second_buy_card["blockers"])


def test_build_mobile_dashboard_exposes_all_preconfirm_blockers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOBILE_SIGNAL_STALENESS_DAYS", "0")
    results_root, exp_id = _build_results_root(tmp_path)
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

    def preview_loader(config_json, request_exp_id, as_of_date):
        assert request_exp_id == exp_id
        return {
            "as_of_date_used": "2026-03-11",
            "candidates": [{"symbol": "sh600519", "reasons": ["breakout", "rank=1"]}],
            "target_positions": [{"symbol": "sh600519", "target_weight": 0.1, "cap_reason": ""}],
        }

    initial_payload = build_mobile_dashboard(results_root, preview_loader=preview_loader)
    buy_card = next(card for card in initial_payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    create_ticket_from_confirmed_action(
        results_root,
        card=buy_card,
        decision="approve",
        operator="mobile@test",
        idempotency_key="idem-duplicate",
        confirm_payload={"final_target_weight": 0.1, "nonce": "n-2"},
    )

    payload = build_mobile_dashboard(results_root, preview_loader=preview_loader)
    buy_card = next(card for card in payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    blocker_codes = {item["code"] for item in buy_card["blockers"]}

    assert {"stale_data", "duplicate_submission", "risk_locked", "executor_unavailable"} <= blocker_codes
    assert buy_card["can_confirm"] is False
