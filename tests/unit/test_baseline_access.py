from __future__ import annotations

import json
from pathlib import Path

from backend.core.tools import baseline_access


def _write_experiment_workbench_config(root: Path, exp_id: str, workbench_config: dict) -> None:
    exp_dir = root / "experiments" / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "config.json").write_text(
        json.dumps({"workbench_config": workbench_config}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_baseline_files(root: Path, record: dict) -> None:
    baseline_dir = root / "baselines" / str(record["baseline_id"])
    baseline_dir.mkdir(parents=True, exist_ok=True)
    meta = {k: v for k, v in record.items() if k != "config_json"}
    (baseline_dir / "baseline.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (baseline_dir / "config.json").write_text(
        json.dumps(record["config_json"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_ensure_default_baseline_v1_refreshes_to_new_pit_dynamic_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    results_root = tmp_path / "outputs"
    results_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(baseline_access, "_results_root", lambda: results_root)
    monkeypatch.setattr(baseline_access, "DEFAULT_BASELINE_EXP_ID", "exp_new_default")

    legacy_cfg = {
        "mode": "experiment",
        "universe_mode": "HS300_ZZ500",
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
        },
    }
    pit_cfg = {
        "mode": "experiment",
        "universe_mode": "HS300_ZZ500",
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
            "membership_mode": "PIT_DYNAMIC",
        },
    }
    _write_experiment_workbench_config(results_root, "exp_old_default", legacy_cfg)
    _write_experiment_workbench_config(results_root, "exp_new_default", pit_cfg)

    stale_record = baseline_access.normalize_baseline_record(
        {
            "baseline_id": baseline_access.DEFAULT_BASELINE_ID,
            "name": baseline_access.DEFAULT_BASELINE_ID,
            "display_name": baseline_access.DEFAULT_BASELINE_ID,
            "owner": "manual",
            "locked": True,
            "linked_exp_id": "exp_old_default",
            "config_json": legacy_cfg,
        }
    )
    _write_baseline_files(results_root, stale_record)

    refreshed = baseline_access.ensure_default_baseline_v1()

    assert refreshed is not None
    assert refreshed.get("linked_exp_id") == "exp_new_default"
    assert ((refreshed.get("config_json") or {}).get("universe") or {}).get("membership_mode") == "PIT_DYNAMIC"

    meta = baseline_access.baseline_meta_view(baseline_access.DEFAULT_BASELINE_ID)
    assert meta is not None
    assert meta.get("membership_mode") == "PIT_DYNAMIC"
