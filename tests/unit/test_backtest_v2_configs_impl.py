from __future__ import annotations

from backend.api.backtest_v2 import configs_impl


def test_save_backtest_v2_baseline_forwards_execution_contract_ref(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_write_baseline_record(record: dict[str, object]) -> dict[str, object]:
        captured["record"] = record
        return {**record, "baseline_id": "baseline_demo", "config_hash": "hash_demo"}

    monkeypatch.setattr(configs_impl, "write_baseline_record", fake_write_baseline_record)

    body = configs_impl.BacktestV2BaselineSaveRequest(
        baseline_id="baseline_demo",
        name="baseline_demo",
        display_name="baseline_demo",
        config_json={"universe_mode": "HS300_ZZ500"},
        linked_exp_id="exp_123",
        execution_contract_ref={
            "artifact": "execution_contract.json",
            "contract_version": "backtest_execution_contract@1",
            "contract_type": "single_run",
            "asset_scope": "cn_a_equity",
            "hash": "abc123",
        },
        owner="manual",
        locked=True,
    )

    result = configs_impl.save_backtest_v2_baseline(body)

    assert captured["record"]["execution_contract_ref"]["hash"] == "abc123"
    assert captured["record"]["linked_exp_id"] == "exp_123"
    assert result["baseline_id"] == "baseline_demo"
    assert result["execution_contract_ref"]["artifact"] == "execution_contract.json"
