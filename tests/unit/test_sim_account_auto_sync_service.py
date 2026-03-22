from __future__ import annotations

import json

from backend.core.services import sim_account_auto_sync_service as mod
from backend.core.services.sim_account_service import load_latest_holdings_snapshot, store_holdings_snapshot


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_auto_sync_returns_disabled_when_source_path_is_not_configured(tmp_path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"
    monkeypatch.delenv("SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH", raising=False)
    monkeypatch.delenv("SIM_ACCOUNT_AUTO_SYNC_ENABLED", raising=False)

    payload = mod.run_auto_sync(results_root, target_trade_date="2026-03-16")

    assert payload["status"] == "disabled"
    assert payload["message"] == "auto sync source path is not configured"
    status_path = results_root / "ops" / "sim_account" / "paper_a_share_main" / "auto_sync_status.json"
    assert status_path.exists()


def test_run_auto_sync_invalid_payload_does_not_override_latest_snapshot(tmp_path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"
    initial = store_holdings_snapshot(
        results_root,
        {
            "account_id": "paper_a_share_main",
            "trade_date": "2026-03-16",
            "cash": 1000,
            "positions": [{"symbol": "600000.SH", "qty": 100, "sellable_qty": 100, "avg_cost": 10.0}],
        },
    )
    source_path = tmp_path / "holdings.json"
    _write_json(
        source_path,
        {
            "trade_date": "2026-03-16",
            "cash": 1000,
            "positions": [{"symbol": "600000.SH", "qty": -1, "sellable_qty": 0, "avg_cost": 10.0}],
        },
    )
    monkeypatch.setenv("SIM_ACCOUNT_AUTO_SYNC_ENABLED", "true")
    monkeypatch.setenv("SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH", str(source_path))

    payload = mod.run_auto_sync(results_root, target_trade_date="2026-03-16")

    assert payload["status"] == "failed"
    latest = load_latest_holdings_snapshot(results_root, "paper_a_share_main")
    assert latest is not None
    assert latest["snapshot_id"] == initial["snapshot_id"]


def test_run_auto_sync_writes_stale_snapshot_without_reconcile(tmp_path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"
    source_path = tmp_path / "holdings.json"
    _write_json(
        source_path,
        {
            "trade_date": "2026-03-15",
            "cash": 12345,
            "positions": [{"symbol": "600000.SH", "qty": 200, "sellable_qty": 200, "avg_cost": 10.0}],
        },
    )
    monkeypatch.setenv("SIM_ACCOUNT_AUTO_SYNC_ENABLED", "true")
    monkeypatch.setenv("SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH", str(source_path))
    seen = {"called": False}
    monkeypatch.setattr(
        mod,
        "run_position_aware_reconcile",
        lambda *args, **kwargs: seen.__setitem__("called", True) or {"reconcile_id": "rc_should_not_happen"},
    )

    payload = mod.run_auto_sync(results_root, target_trade_date="2026-03-16")

    assert payload["status"] == "stale_input"
    assert payload["trade_date"] == "2026-03-15"
    assert seen["called"] is False
    latest = load_latest_holdings_snapshot(results_root, "paper_a_share_main")
    assert latest is not None
    assert latest["trade_date"] == "2026-03-15"


def test_run_auto_sync_success_writes_snapshot_and_reconcile(tmp_path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"
    source_path = tmp_path / "holdings.json"
    _write_json(
        source_path,
        {
            "trade_date": "2026-03-16",
            "cash": 54321,
            "positions": [{"symbol": "000001.SZ", "qty": 300, "sellable_qty": 300, "avg_cost": 12.3}],
        },
    )
    monkeypatch.setenv("SIM_ACCOUNT_AUTO_SYNC_ENABLED", "true")
    monkeypatch.setenv("SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH", str(source_path))
    seen = {}

    def _fake_reconcile(results_root_arg, account_id_arg, *, strategy_as_of_date=None, now_ts=None):
        seen["account_id"] = account_id_arg
        seen["strategy_as_of_date"] = strategy_as_of_date
        return {"reconcile_id": "rc_auto_sync"}

    monkeypatch.setattr(mod, "run_position_aware_reconcile", _fake_reconcile)

    payload = mod.run_auto_sync(results_root, target_trade_date="2026-03-16")

    assert payload["status"] == "success"
    assert payload["reconcile_id"] == "rc_auto_sync"
    assert seen == {"account_id": "paper_a_share_main", "strategy_as_of_date": "2026-03-16"}
    latest = load_latest_holdings_snapshot(results_root, "paper_a_share_main")
    assert latest is not None
    assert latest["trade_date"] == "2026-03-16"
