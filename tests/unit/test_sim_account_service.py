from __future__ import annotations

import json
from datetime import UTC, datetime

from backend.core.services.sim_account_service import (
    get_holdings_sync_status,
    load_latest_holdings_snapshot,
    store_holdings_snapshot,
)


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_store_holdings_snapshot_writes_latest_and_history(tmp_path) -> None:
    results_root = tmp_path / "outputs"
    snapshot = store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": "2026-03-16",
            "synced_at": "2026-03-16T09:30:00+08:00",
            "source_type": "manual_import",
            "cash": 123456.78,
            "positions": [
                {"symbol": "600000.SH", "qty": 300, "sellable_qty": 200, "avg_cost": 10.5, "name": "浦发银行"},
                {"symbol": "000001.SZ", "qty": 100, "sellable_qty": 100, "avg_cost": 12.3, "name": "平安银行"},
            ],
        },
    )

    account_root = results_root / "ops" / "sim_account" / "paper_a_share_main"
    latest_path = account_root / "holdings" / "latest.json"
    history_path = account_root / "holdings" / "history" / f"{snapshot['snapshot_id']}.json"
    audit_path = account_root / "audit_log.jsonl"

    assert latest_path.exists()
    assert history_path.exists()
    latest_payload = _read_json(latest_path)
    assert latest_payload["schema_version"] == "sim_account_holdings_snapshot@1"
    assert latest_payload["snapshot_id"] == snapshot["snapshot_id"]
    assert [item["symbol"] for item in latest_payload["positions"]] == ["sh600000", "sz000001"]
    assert latest_payload["summary"]["position_count"] == 2
    assert audit_path.exists()
    audit_lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert any('"event_type":"snapshot_synced"' in line for line in audit_lines)


def test_store_holdings_snapshot_invalid_payload_does_not_override_latest(tmp_path) -> None:
    results_root = tmp_path / "outputs"
    first_snapshot = store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": "2026-03-16",
            "synced_at": "2026-03-16T09:30:00+08:00",
            "cash": 1000,
            "positions": [
                {"symbol": "600000.SH", "qty": 100, "sellable_qty": 100, "avg_cost": 10.0},
            ],
        },
    )

    latest_path = results_root / "ops" / "sim_account" / "paper_a_share_main" / "holdings" / "latest.json"
    try:
        store_holdings_snapshot(
            results_root,
            {
                "account_id": "paper_a_share_main",
                "trade_date": "2026-03-16",
                "synced_at": "2026-03-16T10:30:00+08:00",
                "cash": 1000,
                "positions": [
                    {"symbol": "600000.SH", "qty": -1, "sellable_qty": 0, "avg_cost": 10.0},
                ],
            },
        )
    except ValueError as exc:
        assert "qty must be > 0" in str(exc)
    else:
        raise AssertionError("expected invalid payload to raise ValueError")

    latest_payload = _read_json(latest_path)
    assert latest_payload["snapshot_id"] == first_snapshot["snapshot_id"]
    history_root = results_root / "ops" / "sim_account" / "paper_a_share_main" / "holdings" / "history"
    assert len(list(history_root.glob("*.json"))) == 1
    audit_path = results_root / "ops" / "sim_account" / "paper_a_share_main" / "audit_log.jsonl"
    audit_lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert any('"event_type":"snapshot_sync_failed"' in line for line in audit_lines)


def test_get_holdings_sync_status_returns_unsynced_and_stale(tmp_path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"

    unsynced = get_holdings_sync_status(results_root, "paper_a_share_main")
    assert unsynced["status"] == "unsynced"
    assert unsynced["latest_snapshot_id"] == ""

    monkeypatch.setenv("SIM_ACCOUNT_SYNC_STALE_SECONDS", "60")
    store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": "2026-03-16",
            "synced_at": "2026-03-16T01:30:00+00:00",
            "cash": 1000,
            "positions": [
                {"symbol": "600000.SH", "qty": 100, "sellable_qty": 100, "avg_cost": 10.0},
            ],
        },
    )

    base_ts = int(datetime(2026, 3, 16, 1, 30, tzinfo=UTC).timestamp())

    fresh = get_holdings_sync_status(results_root, "paper_a_share_main", now_ts=base_ts)
    assert fresh["status"] == "fresh"
    assert fresh["age_seconds"] == 0

    stale = get_holdings_sync_status(results_root, "paper_a_share_main", now_ts=base_ts + 300)
    assert stale["status"] == "stale"
    assert any("过期" in warning for warning in stale["warnings"])


def test_store_holdings_snapshot_records_drift_and_pending_ticket_overlap(tmp_path) -> None:
    results_root = tmp_path / "outputs"
    store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": "2026-03-16",
            "synced_at": "2026-03-16T09:30:00+08:00",
            "cash": 1000,
            "positions": [
                {"symbol": "600000.SH", "qty": 100, "sellable_qty": 100, "avg_cost": 10.0},
            ],
        },
    )
    _write_json(
        results_root / "mobile_ops" / "approval_tickets" / "mt_pending.json",
        {
            "ticket_id": "mt_pending",
            "suggestion_id": "sg_pending",
            "status": "approved_pending",
            "created_at": "2026-03-16T09:40:00+08:00",
            "updated_at": "2026-03-16T09:40:00+08:00",
            "expires_at": "2099-03-16T09:40:00+08:00",
            "symbol": "sh600000",
            "action_type": "sell",
            "signal_snapshot": {
                "suggestion_id": "sg_pending",
                "signal_date": "2026-03-16",
                "symbol": "sh600000",
                "name": "浦发银行",
                "action_type": "sell",
            },
            "approval": {
                "decision": "approve",
                "operator": "mobile@test",
                "original_values": {"qty": 100, "target_weight": None},
                "final_values": {"qty": 100, "target_weight": None},
            },
        },
    )

    second_snapshot = store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": "2026-03-16",
            "synced_at": "2026-03-16T10:30:00+08:00",
            "cash": 1000,
            "positions": [
                {"symbol": "600000.SH", "qty": 200, "sellable_qty": 200, "avg_cost": 10.0},
                {"symbol": "000001.SZ", "qty": 100, "sellable_qty": 100, "avg_cost": 12.0},
            ],
        },
    )

    drift_summary = second_snapshot["drift_summary"]
    assert drift_summary["has_previous_snapshot"] is True
    assert drift_summary["has_drift"] is True
    assert drift_summary["pending_ticket_count"] == 1
    assert drift_summary["pending_ticket_drift"] is True
    assert drift_summary["added_symbols"] == ["sz000001"]
    assert drift_summary["qty_changed"] == [{"symbol": "sh600000", "previous_qty": 100, "current_qty": 200}]

    latest_snapshot = load_latest_holdings_snapshot(results_root, "paper_a_share_main")
    assert latest_snapshot is not None
    assert latest_snapshot["snapshot_id"] == second_snapshot["snapshot_id"]

    status = get_holdings_sync_status(results_root, "paper_a_share_main", now_ts=1770000000)
    assert status["drift_summary"]["pending_ticket_drift"] is True
