from __future__ import annotations

import json
from pathlib import Path

from backend.core.tools import baseline_access


def _write_baseline_files(root: Path, record: dict) -> None:
    baseline_dir = root / "baselines" / str(record["baseline_id"])
    baseline_dir.mkdir(parents=True, exist_ok=True)
    meta = {k: v for k, v in record.items() if k != "config_json"}
    (baseline_dir / "baseline.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    config_payload = json.dumps(record["config_json"], ensure_ascii=False, indent=2)
    (baseline_dir / "baseline_config_snapshot.json").write_text(config_payload, encoding="utf-8")
    (baseline_dir / "config.json").write_text(config_payload, encoding="utf-8")


def _write_experiment_execution_contract(root: Path, exp_id: str, execution_contract: dict) -> None:
    exp_dir = root / "experiments" / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "execution_contract.json").write_text(
        json.dumps(execution_contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_list_baseline_records_does_not_auto_create_default_fixture(
    tmp_path: Path,
    monkeypatch,
) -> None:
    results_root = tmp_path / "outputs"
    results_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(baseline_access, "_results_root", lambda: results_root)

    rows = baseline_access.list_baseline_records()

    assert rows == []
    assert not (results_root / "baselines" / baseline_access.DEFAULT_BASELINE_ID).exists()


def test_load_baseline_record_falls_back_to_config_alias_when_snapshot_missing(tmp_path: Path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"
    results_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(baseline_access, "_results_root", lambda: results_root)

    record = {
        "baseline_id": "baseline_alias_only",
        "name": "baseline_alias_only",
        "display_name": "baseline_alias_only",
        "owner": "manual",
        "locked": True,
        "linked_exp_id": None,
        "config_json": {
            "mode": "experiment",
            "universe_mode": "HS300_ZZ500",
            "universe": {"start": "2021-01-04", "end": "2026-03-20"},
        },
    }
    _write_baseline_files(results_root, record)
    snapshot_path = results_root / "baselines" / "baseline_alias_only" / "baseline_config_snapshot.json"
    snapshot_path.unlink()

    loaded = baseline_access.load_baseline_record("baseline_alias_only")

    assert loaded is not None
    assert loaded["baseline_id"] == "baseline_alias_only"
    assert loaded["config_json"]["universe"]["start"] == "2021-01-04"


def test_load_baseline_record_prefers_snapshot_over_config_alias(tmp_path: Path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"
    results_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(baseline_access, "_results_root", lambda: results_root)

    record = {
        "baseline_id": "baseline_snapshot_preferred",
        "name": "baseline_snapshot_preferred",
        "display_name": "baseline_snapshot_preferred",
        "owner": "manual",
        "locked": True,
        "linked_exp_id": None,
        "config_json": {
            "mode": "experiment",
            "universe_mode": "HS300_ZZ500",
            "universe": {"start": "2021-01-04", "end": "2026-03-20"},
        },
    }
    _write_baseline_files(results_root, record)
    alias_path = results_root / "baselines" / "baseline_snapshot_preferred" / "config.json"
    alias_path.write_text(
        json.dumps(
            {
                "mode": "experiment",
                "universe_mode": "HS300_ZZ500",
                "universe": {"start": "2012-01-04", "end": "2026-03-20"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    loaded = baseline_access.load_baseline_record("baseline_snapshot_preferred")

    assert loaded is not None
    assert loaded["config_json"]["universe"]["start"] == "2021-01-04"


def test_list_baseline_records_exposes_ledger_metrics_when_linked_experiment_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    results_root = tmp_path / "outputs"
    results_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(baseline_access, "_results_root", lambda: results_root)

    _write_baseline_files(
        results_root,
        {
            "baseline_id": "baseline_missing_exp",
            "name": "baseline_missing_exp",
            "display_name": "baseline_missing_exp",
            "owner": "manual",
            "locked": True,
            "linked_exp_id": "exp_missing",
            "config_json": {
                "mode": "experiment",
                "universe_mode": "HS300_ZZ500",
                "universe": {"start": "2012-01-04", "end": "2026-03-20"},
            },
        },
    )
    ledger_dir = results_root / "baselines" / "baseline_missing_exp" / "machine"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    (ledger_dir / "experiment_ledger.jsonl").write_text(
        json.dumps(
            {
                "baseline_id": "baseline_missing_exp",
                "exp_id": "exp_missing",
                "summary": {
                    "perf": {
                        "cagr": 0.1449,
                        "max_drawdown": -0.3648,
                        "sharpe": 0.7039,
                        "trades": 628,
                    }
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    row = baseline_access.list_baseline_records()[0]
    record = baseline_access.load_baseline_record("baseline_missing_exp")

    assert record is not None
    assert record["has_result"] is False
    assert record["linked_exp_missing"] is True
    assert row["has_result"] is False
    assert row["linked_exp_missing"] is True
    assert row["metric_snapshot_available"] is True
    assert row["result_source"] == "baseline_ledger_snapshot"
    assert row["cagr"] == 0.1449
    assert row["max_drawdown"] == -0.3648


def test_load_baseline_execution_contract_resolves_ref_and_verifies_hash(tmp_path: Path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"
    results_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(baseline_access, "_results_root", lambda: results_root)

    contract = {
        "contract_version": "backtest_execution_contract@1",
        "contract_type": "unified_combo",
        "asset_scope": "cn_a_multi_sleeve",
        "components": {},
    }
    _write_experiment_execution_contract(results_root, "exp_contract", contract)
    expected_ref = baseline_access._execution_contract_ref_from_payload(
        contract,
        artifact_rel="execution_contract.json",
    )
    _write_baseline_files(
        results_root,
        {
            "baseline_id": "baseline_contract",
            "name": "baseline_contract",
            "display_name": "baseline_contract",
            "owner": "manual",
            "locked": True,
            "linked_exp_id": "exp_contract",
            "execution_contract_ref": expected_ref,
            "config_json": {"asset_scope": "cn_a_multi_sleeve", "unified_runtime": {"enabled": True}},
        },
    )

    loaded = baseline_access.load_baseline_execution_contract("baseline_contract")

    assert loaded == contract


def test_write_baseline_record_rejects_second_active_baseline_for_same_effective_period(tmp_path: Path, monkeypatch) -> None:
    results_root = tmp_path / "outputs"
    results_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(baseline_access, "_results_root", lambda: results_root)

    first = baseline_access.write_baseline_record(
        {
            "baseline_id": "baseline_one",
            "name": "baseline_one",
            "display_name": "baseline_one",
            "owner": "manual",
            "locked": True,
            "linked_exp_id": None,
            "status": "active",
            "effective_period": "cn_a_equity:2012-2026",
            "config_json": {"universe": {"start": "2012-01-04", "end": "2026-03-20"}},
        }
    )

    assert first["status"] == "active"
    try:
        baseline_access.write_baseline_record(
            {
                "baseline_id": "baseline_two",
                "name": "baseline_two",
                "display_name": "baseline_two",
                "owner": "manual",
                "locked": True,
                "linked_exp_id": None,
                "status": "active",
                "effective_period": "cn_a_equity:2012-2026",
                "config_json": {"universe": {"start": "2012-01-04", "end": "2026-03-20"}},
            }
        )
    except ValueError as exc:
        assert "active baseline already exists" in str(exc)
    else:
        raise AssertionError("expected duplicate active baseline write to fail")
