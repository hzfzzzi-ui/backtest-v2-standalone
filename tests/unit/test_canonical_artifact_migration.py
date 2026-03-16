from __future__ import annotations

import json
from pathlib import Path

from backend.core.tools import canonical_artifact_migration


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_migrate_experiment_dir_promotes_canonical_trades_and_counters(tmp_path: Path) -> None:
    exp_dir = tmp_path / "exp_case"
    exp_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": "exp_case",
            "artifacts": {
                "perf": "perf.json",
                "run_meta": "run_meta.json",
                "orders": "orders.csv",
                "trades": "trades.csv",
                "trades_alias": "trades.csv",
            },
            "core_artifacts": {
                "trades": "trades.csv",
            },
            "stage_pipeline": {
                "execution_shell": "stage_pipeline_shell_legacy_adapter",
            },
        },
    )
    _write_json(
        exp_dir / "run_meta.json",
        {
            "counters": {
                "raw_signal_count": 10,
                "blocked_count": 3,
                "orders_count": 7,
                "skipped_count": 1,
                "closed_trades_count": 6,
            },
            "stage_pipeline": {
                "execution_shell": "stage_pipeline_shell_legacy_adapter",
            },
        },
    )
    (exp_dir / "trades.csv").write_text("trade_date,symbol,side\n2024-01-03,sh600000,buy\n", encoding="utf-8")

    dry_run = canonical_artifact_migration.migrate_experiment_dir(exp_dir, dry_run=True)
    assert dry_run["needs_trade_migration"] is True
    assert dry_run["needs_counter_migration"] is True
    assert dry_run["needs_shell_label_migration"] is True
    assert (exp_dir / "trades.csv").exists()
    assert not (exp_dir / "portfolio_trades.csv").exists()

    applied = canonical_artifact_migration.migrate_experiment_dir(exp_dir, dry_run=False)
    assert applied["changed"] is True
    assert (exp_dir / "portfolio_trades.csv").exists()
    assert not (exp_dir / "trades.csv").exists()

    manifest = json.loads((exp_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"]["trades"] == "portfolio_trades.csv"
    assert "trades_alias" not in manifest["artifacts"]
    assert manifest["core_artifacts"]["trades"] == "portfolio_trades.csv"
    assert manifest["stage_pipeline"]["execution_shell"] == "stage_pipeline_shell_bridge"

    run_meta = json.loads((exp_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert run_meta["stage_pipeline"]["execution_shell"] == "stage_pipeline_shell_bridge"
    assert run_meta["counters"] == {
        "raw_signal": 10,
        "blocked": 3,
        "orders": 7,
        "skipped": 1,
        "closed_trades": 6,
    }


def test_migrate_experiment_tree_writes_audit_report(tmp_path: Path) -> None:
    experiments_root = tmp_path / "outputs" / "experiments"
    exp_dir = experiments_root / "exp_demo"
    exp_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": "exp_demo",
            "artifacts": {
                "run_meta": "run_meta.json",
                "trades": "trades.csv",
            },
        },
    )
    _write_json(exp_dir / "run_meta.json", {"counters": {"raw_signal_count": 1}})
    _write_json(
        exp_dir / "run_config.json",
        {
            "universe": {"benchmark": "000300.SH", "start": "2024-01-01", "end": "2024-12-31"},
        },
    )
    (exp_dir / "trades.csv").write_text("trade_date,symbol,side\n2024-01-03,sh600000,buy\n", encoding="utf-8")

    report_path = tmp_path / "migration_report.json"
    report = canonical_artifact_migration.migrate_experiment_tree(
        experiments_root,
        dry_run=True,
        report_path=report_path,
    )

    assert report["summary"]["experiments_scanned"] == 1
    assert report["summary"]["manifest_backfills"] == 1
    assert report["summary"]["trade_migrations"] == 1
    assert report["summary"]["counter_migrations"] == 1
    assert report_path.exists()
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "canonical_artifact_migration_report@2"


def test_migrate_experiment_dir_backfills_manifest_asset_context(tmp_path: Path) -> None:
    exp_dir = tmp_path / "exp_manifest_case"
    exp_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        exp_dir / "manifest.json",
        {
            "exp_id": "exp_manifest_case",
            "artifacts": {
                "run_meta": "run_meta.json",
            },
        },
    )
    _write_json(exp_dir / "run_meta.json", {"counters": {"raw_signal": 1}})
    _write_json(
        exp_dir / "run_config.json",
        {
            "universe": {"benchmark": "000300.SH", "start": "2024-01-01", "end": "2024-12-31"},
            "execution": {"lot_size": 100},
        },
    )

    dry_run = canonical_artifact_migration.migrate_experiment_dir(exp_dir, dry_run=True)
    assert dry_run["needs_manifest_asset_backfill"] is True
    assert "asset_scope" in dry_run["manifest_missing_fields"]

    applied = canonical_artifact_migration.migrate_experiment_dir(exp_dir, dry_run=False)
    assert applied["changed"] is True
    assert "backfilled_manifest_asset_context" in applied["changes"]

    manifest = json.loads((exp_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["asset_scope"] == "cn_a_equity"
    assert manifest["asset_profile_id"] == "cn_a_equity_mainline"
    assert manifest["market_profile_id"] == "cn_a_mainland_equity_market"
    assert manifest["execution_profile_id"] == "cn_a_tplus1_next_open"
    assert manifest["asset_context"]["asset_scope"] == "cn_a_equity"
