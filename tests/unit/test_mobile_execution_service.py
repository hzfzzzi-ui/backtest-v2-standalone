from __future__ import annotations

from backend.core.services.mobile_dashboard_service import build_mobile_dashboard
from backend.core.services.mobile_execution_service import (
    claim_approval_ticket,
    execution_active_ttl_seconds,
    list_executable_tickets,
    list_execution_events,
    list_execution_tickets,
    record_execution_update,
)
from backend.core.services.mobile_ops_service import create_ticket_from_confirmed_action
from tests.unit.test_mobile_dashboard_service import (
    _build_results_root,
    _sample_action_sheet,
    _seed_holdings_snapshot,
    _seed_reconcile,
)


def _seed_ready_results_root(tmp_path):
    results_root, exp_id = _build_results_root(tmp_path)
    snapshot = _seed_holdings_snapshot(
        results_root,
        trade_date="2026-03-11",
        positions=[
            {"symbol": "sh600000", "qty": 100, "sellable_qty": 100, "avg_cost": 10.5, "name": "浦发银行"},
            {"symbol": "sh600036", "qty": 200, "sellable_qty": 200, "avg_cost": 42.0, "name": "招商银行"},
        ],
    )
    _seed_reconcile(results_root, exp_id=exp_id, snapshot=snapshot, action_sheet=_sample_action_sheet())
    return results_root


def _create_buy_ticket(results_root):
    payload = build_mobile_dashboard(results_root)
    buy_card = next(card for card in payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    ticket, created = create_ticket_from_confirmed_action(
        results_root,
        card=buy_card,
        decision="approve",
        operator="mobile@test",
        idempotency_key="idem-exec-001",
        confirm_payload={"final_qty": 100, "nonce": "nonce-exec-1"},
    )
    assert created is True
    return ticket["ticket_id"]


def test_mobile_execution_service_runs_ticket_lifecycle(tmp_path) -> None:
    results_root = _seed_ready_results_root(tmp_path)
    ticket_id = _create_buy_ticket(results_root)

    queue = list_executable_tickets(results_root)
    assert [item["ticket_id"] for item in queue] == [ticket_id]
    assert queue[0]["status"] == "approved_pending"

    claimed = claim_approval_ticket(results_root, ticket_id=ticket_id, executor_id="desktop-sim")
    assert claimed["status"] == "claimed"
    assert claimed["executor_id"] == "desktop-sim"

    submitted = record_execution_update(
        results_root,
        ticket_id=ticket_id,
        status="submitted",
        executor_id="desktop-sim",
    )
    assert submitted["status"] == "submitted"
    assert submitted["submitted_at"]

    partially_filled = record_execution_update(
        results_root,
        ticket_id=ticket_id,
        status="partially_filled",
        executor_id="desktop-sim",
        filled_qty=40,
        avg_fill_price=1498.0,
        message="首笔成交",
    )
    assert partially_filled["status"] == "partially_filled"
    assert partially_filled["filled_qty"] == 40
    assert partially_filled["remaining_qty"] == 60

    filled = record_execution_update(
        results_root,
        ticket_id=ticket_id,
        status="filled",
        executor_id="desktop-sim",
        filled_qty=100,
        avg_fill_price=1499.2,
    )
    assert filled["status"] == "filled"
    assert filled["filled_qty"] == 100
    assert filled["remaining_qty"] == 0
    assert filled["completed_at"]

    events = list_execution_events(results_root, ticket_id)
    assert [item["status"] for item in events] == ["claimed", "submitted", "partially_filled", "filled"]


def test_mobile_execution_service_surfaces_execution_tickets_in_dashboard(tmp_path) -> None:
    results_root = _seed_ready_results_root(tmp_path)
    ticket_id = _create_buy_ticket(results_root)

    claim_approval_ticket(results_root, ticket_id=ticket_id, executor_id="desktop-sim")
    record_execution_update(
        results_root,
        ticket_id=ticket_id,
        status="partially_filled",
        executor_id="desktop-sim",
        filled_qty=30,
        avg_fill_price=1497.8,
        message="盘中部分成交",
    )

    payload = build_mobile_dashboard(results_root)

    assert payload["guidance"]["pending_count"] == 0
    assert payload["guidance"]["execution_count"] == 1
    item = payload["guidance"]["execution_tickets"][0]
    assert item["ticket_id"] == ticket_id
    assert item["status"] == "partially_filled"
    assert item["executor_id"] == "desktop-sim"
    assert item["filled_qty"] == 30
    assert item["recent_events"][-1]["status"] == "partially_filled"
    assert payload["briefing"]["execution_anomalies"]["count"] == 1
    assert payload["briefing"]["execution_anomalies"]["items"][0]["anomaly_type"] == "partially_filled"
    assert payload["briefing"]["post_close"]["confirmed_count"] == 1
    assert payload["briefing"]["post_close"]["executed_count"] == 1
    assert payload["briefing"]["post_close"]["unfinished_count"] == 1
    assert payload["briefing"]["post_close"]["holding_change_count"] == 1
    assert len(payload["briefing"]["post_close"]["source_exp_ids"]) == 1


def test_mobile_execution_service_handles_reject_and_timeout(tmp_path) -> None:
    results_root = _seed_ready_results_root(tmp_path)

    first_ticket_id = _create_buy_ticket(results_root)
    claim_approval_ticket(results_root, ticket_id=first_ticket_id, executor_id="desktop-sim")
    rejected = record_execution_update(
        results_root,
        ticket_id=first_ticket_id,
        status="rejected",
        executor_id="desktop-sim",
        message="交易通道拒单",
        error_code="broker_reject",
    )
    assert rejected["status"] == "rejected"
    assert rejected["last_error_code"] == "broker_reject"

    payload = build_mobile_dashboard(results_root)
    buy_card = next(card for card in payload["guidance"]["approval_cards"] if card["symbol"] == "sh600519")
    second_ticket, created = create_ticket_from_confirmed_action(
        results_root,
        card=buy_card,
        decision="approve",
        operator="mobile@test",
        idempotency_key="idem-exec-timeout",
        confirm_payload={"final_qty": 100, "nonce": "nonce-exec-2"},
        now_ts=1_000_000,
    )
    assert created is True
    claim_approval_ticket(results_root, ticket_id=second_ticket["ticket_id"], executor_id="desktop-sim", now_ts=1_000_100)

    timed_out = list_execution_tickets(
        results_root,
        now_ts=1_000_100 + execution_active_ttl_seconds() + 1,
    )
    timeout_item = next(item for item in timed_out if item["ticket_id"] == second_ticket["ticket_id"])
    assert timeout_item["status"] == "expired"
    assert timeout_item["last_error_code"] == "execution_timeout"

    payload_after_timeout = build_mobile_dashboard(results_root)
    anomaly_types = {item["anomaly_type"] for item in payload_after_timeout["briefing"]["execution_anomalies"]["items"]}
    assert {"rejected", "expired"} <= anomaly_types
