from __future__ import annotations

import json

from backend.core.services.mobile_cash_pool_service import deposit_cash_into_pool
from backend.core.services.sim_account_service import store_holdings_snapshot


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_deposit_cash_into_pool_records_cash_ledger_and_summary(tmp_path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"
    snapshot = store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": "2026-03-16",
            "synced_at": "2026-03-16T09:30:00+08:00",
            "cash": 1000.0,
            "positions": [
                {"symbol": "600000.SH", "qty": 100, "sellable_qty": 100, "avg_cost": 10.0},
            ],
        },
    )
    reconcile_payload = {
        "schema_version": "sim_account_reconcile_run@1",
        "account_id": "paper_a_share_main",
        "reconcile_id": "rc_cash_pool_001",
        "generated_at": "2026-03-16T15:10:00+08:00",
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_trade_date": snapshot["trade_date"],
        "snapshot_synced_at": snapshot["synced_at"],
        "as_of_date": snapshot["trade_date"],
        "source_mode": "position_aware_reconcile",
        "strategy_source": {"exp_id": "exp_cash_pool", "config_hash": "cfg_cash_pool"},
        "execution_assumptions": {},
        "summary": {"action_count": 0, "buy_count": 0, "sell_count": 0, "hold_count": 0, "blocked_count": 0},
        "actions": {"buy": [], "sell": [], "hold": []},
        "action_sheet": [],
        "diagnostics": {},
    }
    reconcile_root = results_root / "ops" / "sim_account" / "paper_a_share_main" / "reconcile"
    _write_json(reconcile_root / "latest.json", reconcile_payload)
    _write_json(reconcile_root / "history" / "rc_cash_pool_001.json", reconcile_payload)
    monkeypatch.setattr(
        "backend.core.services.mobile_cash_pool_service.request_reconcile_refresh",
        lambda *args, **kwargs: {"status": "queued"},
    )

    payload = deposit_cash_into_pool(results_root, amount=250.0, account_id="paper_a_share_main")

    account_root = results_root / "ops" / "sim_account" / "paper_a_share_main"
    assert payload["cash_after"] == 1250.0
    latest_cash_ledger = json.loads((account_root / "cash_ledger" / "latest.json").read_text(encoding="utf-8"))
    assert latest_cash_ledger["object_type"] == "cash_ledger"
    assert latest_cash_ledger["object_scope"] == "account_ops"
    latest_reconcile_summary = json.loads((account_root / "reconcile" / "summary" / "latest.json").read_text(encoding="utf-8"))
    assert latest_reconcile_summary["object_type"] == "reconcile_summary"
    assert latest_reconcile_summary["object_scope"] == "account_ops"
    assert latest_reconcile_summary["source_kind"] == "derived_summary"
    assert (account_root / "cash_ledger" / "latest.json").exists()
    assert (account_root / "cash_ledger" / "history").exists()
    assert (account_root / "sync_logs" / "latest.json").exists()
    assert (account_root / "reconcile" / "summary" / "latest.json").exists()
