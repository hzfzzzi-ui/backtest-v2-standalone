from __future__ import annotations

from backend.core.services.mobile_dashboard_service import build_mobile_dashboard
from backend.core.services.mobile_execution_service import (
    claim_approval_ticket,
    list_execution_events,
    record_execution_update,
)
from backend.core.services.mobile_ops_service import create_ticket_from_confirmed_action, revoke_ticket
from backend.core.services import transaction_lifecycle_service
from tests.unit.test_mobile_dashboard_service import _build_results_root


def _seed_ready_results_root(tmp_path):
    results_root, _ = _build_results_root(tmp_path)
    return results_root


def _buy_card():
    return {
        "suggestion_id": "sg_test_001", "exp_id": "exp_mobile_001",
        "account_id": "test-account", "symbol": "sh600519", "name": "synthetic",
        "action_type": "buy", "bucket": "buy", "signal_date": "2026-03-11",
        "system_suggestion": {"suggested_qty": 100, "target_weight": 0.2},
    }


def _create_buy_ticket(results_root):
    buy_card = _buy_card()
    ticket, created = create_ticket_from_confirmed_action(
        results_root,
        card=buy_card,
        decision="approve",
        operator="mobile@test",
        idempotency_key="idem-lifecycle-001",
        confirm_payload={"final_qty": 100, "nonce": "nonce-lifecycle-1"},
    )
    assert created is True
    return ticket["ticket_id"]


def test_mobile_approval_syncs_transaction_lifecycle_summary(tmp_path) -> None:
    results_root = _seed_ready_results_root(tmp_path)
    ticket_id = _create_buy_ticket(results_root)

    summary = transaction_lifecycle_service.get_summary(results_root, ticket_id)

    assert summary is not None
    assert summary["transaction_id"] == ticket_id
    assert summary["status"] == "approved_pending"
    assert summary["lifecycle_status"] == "approved_pending"
    assert summary["status_group"] == "active"
    assert summary["account_id"] == "test-account"
    assert summary["source_intent_id"].startswith("sg_")
    assert summary["approval_source"] == "mobile@test"
    assert summary["requested_qty"] == 100
    assert summary["failure_reason_codes"] == []
    assert summary["approval_status"] == "approve"

    record = transaction_lifecycle_service.get_record(results_root, ticket_id)
    assert record is not None
    assert record["lifecycle_status"] == "approved_pending"
    assert record["status_group"] == "active"
    assert record["source_intent_id"] == summary["source_intent_id"]
    assert record["approval_source"] == "mobile@test"
    assert record["status_history"][0] == "approved_pending"


def test_mobile_reject_syncs_failure_reason_codes(tmp_path) -> None:
    results_root = _seed_ready_results_root(tmp_path)
    buy_card = _buy_card()
    ticket, created = create_ticket_from_confirmed_action(
        results_root,
        card=buy_card,
        decision="reject",
        operator="mobile@test",
        idempotency_key="idem-lifecycle-reject",
        confirm_payload={"reject_reason": "risk_rejected", "nonce": "nonce-lifecycle-reject"},
    )
    assert created is True

    summary = transaction_lifecycle_service.get_summary(results_root, ticket["ticket_id"])

    assert summary is not None
    assert summary["status"] == "rejected"
    assert summary["lifecycle_status"] == "rejected"
    assert summary["status_group"] == "final"
    assert summary["approval_status"] == "reject"
    assert summary["approval_source"] == "mobile@test"
    assert summary["source_intent_id"] == ticket["suggestion_id"]
    assert "risk_rejected" in summary["failure_reason_codes"]
    assert summary["reject_reason"] == "risk_rejected"

    record = transaction_lifecycle_service.get_record(results_root, ticket["ticket_id"])
    assert record is not None
    assert record["lifecycle_status"] == "rejected"
    assert record["status_group"] == "final"
    assert "risk_rejected" in record["failure_reason_codes"]


def test_mobile_revoke_syncs_failure_reason_codes(tmp_path) -> None:
    results_root = _seed_ready_results_root(tmp_path)
    ticket_id = _create_buy_ticket(results_root)
    revoked = revoke_ticket(
        results_root,
        ticket_id=ticket_id,
        operator="mobile@test",
        reason="manual_rollback",
    )

    summary = transaction_lifecycle_service.get_summary(results_root, ticket_id)

    assert revoked["status"] == "revoked"
    assert summary is not None
    assert summary["status"] == "revoked"
    assert summary["lifecycle_status"] == "revoked"
    assert summary["status_group"] == "final"
    assert "manual_rollback" in summary["failure_reason_codes"]
    assert summary["revoke_reason"] == "manual_rollback"

    record = transaction_lifecycle_service.get_record(results_root, ticket_id)
    assert record is not None
    assert record["lifecycle_status"] == "revoked"
    assert record["status_group"] == "final"
    assert "manual_rollback" in record["failure_reason_codes"]


def test_dashboard_and_execution_can_read_from_lifecycle_store_when_compat_files_are_missing(tmp_path) -> None:
    results_root = _seed_ready_results_root(tmp_path)
    ticket_id = _create_buy_ticket(results_root)

    claim_approval_ticket(results_root, ticket_id=ticket_id, executor_id="desktop-sim")
    record_execution_update(
        results_root,
        ticket_id=ticket_id,
        status="submitted",
        executor_id="desktop-sim",
    )
    record_execution_update(
        results_root,
        ticket_id=ticket_id,
        status="filled",
        executor_id="desktop-sim",
        filled_qty=100,
        avg_fill_price=1499.5,
    )

    approval_path = results_root / "mobile_ops" / "approval_tickets" / f"{ticket_id}.json"
    execution_path = results_root / "mobile_ops" / "execution_events" / f"{ticket_id}.jsonl"
    if approval_path.exists():
        approval_path.unlink()
    if execution_path.exists():
        execution_path.unlink()

    payload = build_mobile_dashboard(results_root)
    execution_items = payload["guidance"]["execution_tickets"]
    assert execution_items[0]["ticket_id"] == ticket_id
    assert execution_items[0]["status"] == "filled"
    assert payload["briefing"]["post_close"]["confirmed_count"] == 1
    assert payload["briefing"]["post_close"]["executed_count"] == 1

    events = list_execution_events(results_root, ticket_id)
    assert [item["status"] for item in events] == ["claimed", "submitted", "filled"]
