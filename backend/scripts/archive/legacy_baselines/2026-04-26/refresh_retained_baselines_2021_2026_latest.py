from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.core.services.experiment_history_service import delete_experiment
from backend.core.services.market_data_sync_service import build_market_data_sync_status
from backend.core.tools.baseline_access import (
    baseline_dir,
    baseline_config_snapshot_path,
    baseline_index_path,
    load_baseline_record,
    sanitize_json,
    write_baseline_record,
)
from backend.core.tools.experiment_runtime_access import run_experiment_sync

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"
EXPERIMENT_INDEX_PATH = EXPERIMENT_ROOT / "index.json"
OPS_ROOT = ROOT / "outputs" / "ops"
SUMMARY_PATH = OPS_ROOT / "refresh_retained_baselines_2021_2026_latest.json"

DEFAULT_TARGET_START = "2021-01-04"
ASSET_SCOPE = "cn_a_equity"

BASELINES: list[dict[str, Any]] = [
    {
        "baseline_id": "baseline_V10",
        "start": "2021-01-04",
        "label": "baseline_V10 | CSI800_PIT | 2021-2026",
    },
    {
        "baseline_id": "baseline_V10_1",
        "start": "2021-01-04",
        "label": "baseline_V10.1 | CSI800_PIT | 2021-2026",
    },
    {
        "baseline_id": "baseline_V10_2",
        "start": "2012-01-04",
        "label": "baseline_V10.2 | CSI800_PIT | 2012-2026",
    },
]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json root: {path}")
    return payload


def _read_experiment_index() -> list[dict[str, Any]]:
    if not EXPERIMENT_INDEX_PATH.exists():
        return []
    try:
        payload = json.loads(EXPERIMENT_INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _write_experiment_index(rows: list[dict[str, Any]]) -> None:
    EXPERIMENT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPERIMENT_INDEX_PATH.write_text(
        json.dumps(sanitize_json(rows), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _latest_display_trade_date() -> tuple[str, dict[str, Any]]:
    status = build_market_data_sync_status()
    latest_display_trade_date = str(status.get("latest_display_trade_date") or "").strip()
    if not latest_display_trade_date:
        raise RuntimeError(f"market_data_sync_status missing latest_display_trade_date: {status!r}")
    return latest_display_trade_date, sanitize_json(status)


def _baseline_config_path(baseline_id: str) -> Path:
    snapshot = baseline_config_snapshot_path(baseline_id)
    if snapshot.exists():
        return snapshot
    return baseline_dir(baseline_id) / "config.json"


def _baseline_meta(baseline_id: str) -> dict[str, Any]:
    record = load_baseline_record(baseline_id)
    if not isinstance(record, dict):
        raise RuntimeError(f"baseline missing: {baseline_id}")
    return record


def _target_config(source_cfg: dict[str, Any], *, start_date: str, end_date: str) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["start"] = start_date
    universe["end"] = end_date
    universe["membership_mode"] = "PIT_DYNAMIC"
    cfg["universe"] = universe
    return sanitize_json(cfg)


def _run_experiment(cfg: dict[str, Any]) -> dict[str, Any]:
    result = run_experiment_sync(
        {
            "preset": "single",
            "asset_scope": ASSET_SCOPE,
            "workbench_config": cfg,
        }
    )
    if not isinstance(result, dict):
        raise RuntimeError("runtime service returned non-dict result")
    exp_id = str(result.get("exp_id") or "").strip()
    status = str(result.get("status") or "").strip().upper()
    if not exp_id or status != "OK":
        raise RuntimeError(f"experiment failed: {result!r}")
    return result


def _experiment_dir(exp_id: str) -> Path:
    path = (EXPERIMENT_ROOT / exp_id).resolve()
    if not path.exists():
        raise RuntimeError(f"experiment directory missing: {path}")
    return path


def _rewrite_labels(label_map: dict[str, str]) -> None:
    rows = _read_experiment_index()
    changed = False
    for row in rows:
        exp_id = str(row.get("exp_id") or "").strip()
        desired = label_map.get(exp_id)
        if desired and str(row.get("label") or "") != desired:
            row["label"] = desired
            changed = True
    if changed:
        _write_experiment_index(rows)


def _register_baseline(*, baseline_meta: dict[str, Any], config_json: dict[str, Any], exp_id: str) -> dict[str, Any]:
    payload = {
        "baseline_id": baseline_meta.get("baseline_id"),
        "name": baseline_meta.get("name"),
        "display_name": baseline_meta.get("display_name"),
        "owner": baseline_meta.get("owner"),
        "locked": baseline_meta.get("locked", False),
        "linked_exp_id": exp_id,
        "config_json": config_json,
    }
    return write_baseline_record(payload)


def _remove_old_experiments(old_exp_ids: set[str], new_exp_ids: set[str]) -> list[str]:
    removed: list[str] = []
    stale_ids = sorted(exp_id for exp_id in old_exp_ids if exp_id and exp_id not in new_exp_ids)
    for exp_id in stale_ids:
        delete_experiment(exp_id)
        removed.append(exp_id)
    return removed


def main() -> None:
    latest_end, sync_status = _latest_display_trade_date()
    OPS_ROOT.mkdir(parents=True, exist_ok=True)

    old_exp_ids: set[str] = set()
    new_exp_ids: set[str] = set()
    label_map: dict[str, str] = {}
    run_rows: list[dict[str, Any]] = []

    for item in BASELINES:
        baseline_id = str(item["baseline_id"])
        baseline_meta = _baseline_meta(baseline_id)
        old_exp_id = str(baseline_meta.get("linked_exp_id") or "").strip()
        if old_exp_id:
            old_exp_ids.add(old_exp_id)
        source_cfg = _load_json(_baseline_config_path(baseline_id))
        target_start = str(item.get("start") or DEFAULT_TARGET_START)
        target_cfg = _target_config(source_cfg, start_date=target_start, end_date=latest_end)
        runtime_result = _run_experiment(target_cfg)
        exp_id = str(runtime_result.get("exp_id") or "").strip()
        new_exp_ids.add(exp_id)
        label_map[exp_id] = str(item["label"])
        exp_dir = _experiment_dir(exp_id)
        perf = _load_json(exp_dir / "perf.json")
        run_meta = _load_json(exp_dir / "run_meta.json")
        baseline_record = _register_baseline(
            baseline_meta=baseline_meta,
            config_json=target_cfg,
            exp_id=exp_id,
        )
        run_rows.append(
            {
                "baseline_id": baseline_id,
                "display_name": baseline_meta.get("display_name"),
                "old_exp_id": old_exp_id or None,
                "new_exp_id": exp_id,
                "label": item["label"],
                "window_start": ((run_meta.get("data") or {}).get("start") if isinstance(run_meta.get("data"), dict) else None),
                "window_end": ((run_meta.get("data") or {}).get("end") if isinstance(run_meta.get("data"), dict) else None),
                "data_role": (
                    (((run_meta.get("report_consistency") or {}).get("data_role")) if isinstance(run_meta.get("report_consistency"), dict) else None)
                    or (((run_meta.get("data") or {}).get("data_role")) if isinstance(run_meta.get("data"), dict) else None)
                ),
                "membership_mode": ((run_meta.get("universe") or {}).get("membership_mode") if isinstance(run_meta.get("universe"), dict) else None),
                "total_return": perf.get("total_return"),
                "cagr": perf.get("cagr"),
                "sharpe": perf.get("sharpe"),
                "max_drawdown": perf.get("max_drawdown"),
                "trades": perf.get("trades"),
                "baseline_record": {
                    "baseline_id": baseline_record.get("baseline_id"),
                    "linked_exp_id": baseline_record.get("linked_exp_id"),
                    "execution_contract_ref": baseline_record.get("execution_contract_ref"),
                    "updated_at": baseline_record.get("updated_at"),
                },
            }
        )

    _rewrite_labels(label_map)
    removed_exp_ids = _remove_old_experiments(old_exp_ids, new_exp_ids)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "target_starts": {str(item["baseline_id"]): str(item.get("start") or DEFAULT_TARGET_START) for item in BASELINES},
        "target_end": latest_end,
        "sync_status": sync_status,
        "baseline_index_path": str(baseline_index_path()),
        "experiment_index_path": str(EXPERIMENT_INDEX_PATH),
        "runs": run_rows,
        "removed_old_exp_ids": removed_exp_ids,
    }
    SUMMARY_PATH.write_text(
        json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
